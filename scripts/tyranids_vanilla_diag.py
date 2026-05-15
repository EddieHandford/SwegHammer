"""
Tyranids vanilla-10e diagnostic — re-diagnose +9.2pt over-performance.

After the simulator default flipped to vanilla WH40k 10e mode, Tyranids dropped
from +10.3 (SwegHammer) to +9.2 (vanilla) — only marginal. The G1 anti-swarm
target-priority bias (SYNAPSE +1.5x bonus) and other G-series mitigations
already shipped, yet sim WR is 57.2 vs real 48.0. This script tests three
hypotheses for the residual gap in vanilla mode:

  H_SwarmKills    Tyranid model kills per battle — does the swarm out-trade?
  H_SynapseExploit  Frac of battles where ALL SYNAPSE attackers (Hive Tyrant)
                    survive 5 rounds — under vanilla turn structure, do swarms
                    shield Synapse so the auto-pass blanket never lifts?
  H_ChargeWave    Sum of melee strikes (UnitFought) per battle, by side —
                  vanilla 10e charges are simultaneous within the charging
                  player's turn. Is the Tyranid charge wave ≥3x opponent's?

Run: PYTHONIOENCODING=utf-8 python -m scripts.tyranids_vanilla_diag

Read-only — does NOT modify catalogue or simulator. N=30/matchup, vanilla mode.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from typing import Dict, List

from code.archetypes import build_archetype_army, has_archetype
from code.army_builder import build_faction_random_army
from code.events import (
    BattleshockFailed, EventLog, ObjectiveScored, RoundEnded, UnitCharged,
    UnitFought, UnitKilled,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle, RulesConfig

OPPONENTS = ["Adeptus Astartes", "T'au Empire", "Aeldari"]
REAL_TYRANID_WR = 48.0
N = 30
POINTS = 1000


def _build(faction: str, name: str, budget: float, seed: int):
    rng = random.Random(seed)
    if has_archetype(faction):
        return build_archetype_army(name, faction, budget, rng=rng)
    return build_faction_random_army(name, faction, budget, rng=rng)


def _is_synapse(unit) -> bool:
    return "SYNAPSE" in (unit.profile.unit_keywords or ())


def run_pairing(opp: str, n: int) -> dict:
    wins_tyr = 0
    wins_opp = 0
    draws = 0
    tyr_kills_total = 0       # OPP units killed by TYR (i.e. TYR model losses on the OPP roster) — actually we count UnitKilled where uid belonged to OPP. To count Tyranid MODEL kills (kills BY tyranids), we track the killed unit's owning army from the snapshot.
    opp_kills_total = 0
    synapse_all_survived = 0  # battles where every TYR SYNAPSE unit was alive at end
    tyr_melee_strikes_total = 0
    opp_melee_strikes_total = 0
    tyr_charges_succeeded = 0
    opp_charges_succeeded = 0
    tyr_final_vp = 0
    opp_final_vp = 0
    n_battles = 0
    rounds_total = 0

    rules = RulesConfig.vanilla_10e()

    for s in range(n):
        random.seed(1000 + s)
        tyr = _build("Tyranids", "TYR", POINTS, seed=s)
        op = _build(opp, "OPP", POINTS, seed=s + 50000)
        if not tyr.units or not op.units:
            continue
        # uid -> owning army name; populated from initial deploy roster
        uid_owner: Dict[str, str] = {}
        # uid -> is SYNAPSE flag
        uid_is_synapse: Dict[str, bool] = {}
        for u in tyr.units:
            uid_owner[u.uid if u.uid else id(u)] = "TYR"
        for u in op.units:
            uid_owner[u.uid if u.uid else id(u)] = "OPP"

        log = EventLog()
        battle = Battle(tyr, op, map_=DEFAULT_MAP, subscribers=[log], rules=rules)
        r = battle.run()
        n_battles += 1
        rounds_total += r.rounds
        if r.winner == "TYR":
            wins_tyr += 1
        elif r.winner == "OPP":
            wins_opp += 1
        else:
            draws += 1
        tyr_final_vp += r.a_vp
        opp_final_vp += r.b_vp

        # Re-scan uid_owner now that uids are assigned (Battle._assign_uids
        # runs in run()). Walk both armies post-battle to map uid -> side and
        # SYNAPSE flag — uids are stable for the life of the unit instance.
        uid_owner = {}
        uid_is_synapse = {}
        for u in tyr.units:
            uid_owner[u.uid] = "TYR"
            uid_is_synapse[u.uid] = _is_synapse(u)
        for u in op.units:
            uid_owner[u.uid] = "OPP"
            uid_is_synapse[u.uid] = False  # only TYR-side SYNAPSE matters

        # H_SwarmKills — count UnitKilled by side of the killed unit.
        # The unit_uid is the VICTIM, so an OPP victim = a TYR kill.
        tyr_kills = 0
        opp_kills = 0
        # H_ChargeWave — count UnitFought strikes by attacker side.
        tyr_strikes = 0
        opp_strikes = 0
        tyr_charges_ok = 0
        opp_charges_ok = 0
        # H_SynapseExploit — count Tyranid SYNAPSE units killed during battle.
        # If 0 SYNAPSE-killed → all SYNAPSE survived 5 rounds.
        synapse_uids_killed: set = set()
        synapse_uids_total = {uid for uid, syn in uid_is_synapse.items() if syn and uid_owner.get(uid) == "TYR"}

        for e in log.events:
            if isinstance(e, UnitKilled):
                owner = uid_owner.get(e.unit_uid)
                if owner == "OPP":
                    tyr_kills += 1
                elif owner == "TYR":
                    opp_kills += 1
                    if uid_is_synapse.get(e.unit_uid):
                        synapse_uids_killed.add(e.unit_uid)
            elif isinstance(e, UnitFought):
                owner = uid_owner.get(e.attacker_uid)
                if owner == "TYR":
                    tyr_strikes += 1
                elif owner == "OPP":
                    opp_strikes += 1
            elif isinstance(e, UnitCharged):
                if e.succeeded:
                    owner = uid_owner.get(e.unit_uid)
                    if owner == "TYR":
                        tyr_charges_ok += 1
                    elif owner == "OPP":
                        opp_charges_ok += 1

        tyr_kills_total += tyr_kills
        opp_kills_total += opp_kills
        tyr_melee_strikes_total += tyr_strikes
        opp_melee_strikes_total += opp_strikes
        tyr_charges_succeeded += tyr_charges_ok
        opp_charges_succeeded += opp_charges_ok

        # Synapse exploit — did ALL synapse-keyword TYR units survive?
        if synapse_uids_total and not synapse_uids_killed:
            synapse_all_survived += 1
        elif not synapse_uids_total:
            # No SYNAPSE in roster (shouldn't happen — Hive Tyrant is seeded);
            # don't count toward the metric either way.
            pass

    nb = max(1, n_battles)
    return {
        "opp": opp,
        "n": n_battles,
        "wins_tyr": wins_tyr,
        "wins_opp": wins_opp,
        "draws": draws,
        "wr_tyr": wins_tyr / nb * 100,
        "diff_vs_real": wins_tyr / nb * 100 - REAL_TYRANID_WR,
        "tyr_kills_avg": tyr_kills_total / nb,
        "opp_kills_avg": opp_kills_total / nb,
        "kill_ratio": tyr_kills_total / max(1, opp_kills_total),
        "synapse_all_survived_frac": synapse_all_survived / nb,
        "tyr_melee_strikes_avg": tyr_melee_strikes_total / nb,
        "opp_melee_strikes_avg": opp_melee_strikes_total / nb,
        "melee_ratio": tyr_melee_strikes_total / max(1, opp_melee_strikes_total),
        "tyr_charges_avg": tyr_charges_succeeded / nb,
        "opp_charges_avg": opp_charges_succeeded / nb,
        "tyr_final_vp_avg": tyr_final_vp / nb,
        "opp_final_vp_avg": opp_final_vp / nb,
        "rounds_avg": rounds_total / nb,
    }


def main() -> None:
    print(f"=== Tyranids vanilla-10e diag — N={N}/matchup, archetypes ON, {POINTS}pt ===")
    print(f"Real Tyranid WR target: {REAL_TYRANID_WR:.1f}%  |  rules: vanilla WH40k 10e")
    print()
    print(f"{'Opponent':22s}  {'WR':>6s}  {'dWR':>6s}  "
          f"{'TYR_k':>6s}  {'OPP_k':>6s}  {'k_rat':>5s}  "
          f"{'syn_alive':>9s}  {'TYR_mel':>7s}  {'OPP_mel':>7s}  {'m_rat':>5s}  "
          f"{'TYR_chg':>7s}  {'OPP_chg':>7s}  {'VP_T/O':>11s}")

    rows = []
    for opp in OPPONENTS:
        r = run_pairing(opp, N)
        rows.append(r)
        print(f"{opp:22s}  "
              f"{r['wr_tyr']:5.1f}%  "
              f"{r['diff_vs_real']:+5.1f}  "
              f"{r['tyr_kills_avg']:6.2f}  "
              f"{r['opp_kills_avg']:6.2f}  "
              f"{r['kill_ratio']:5.2f}  "
              f"{r['synapse_all_survived_frac']*100:7.1f}%  "
              f"{r['tyr_melee_strikes_avg']:7.2f}  "
              f"{r['opp_melee_strikes_avg']:7.2f}  "
              f"{r['melee_ratio']:5.2f}  "
              f"{r['tyr_charges_avg']:7.2f}  "
              f"{r['opp_charges_avg']:7.2f}  "
              f"{r['tyr_final_vp_avg']:4.1f}/{r['opp_final_vp_avg']:4.1f}")
    print()

    avg_wr = sum(r["wr_tyr"] for r in rows) / len(rows)
    avg_synapse = sum(r["synapse_all_survived_frac"] for r in rows) / len(rows)
    avg_kill_ratio = sum(r["kill_ratio"] for r in rows) / len(rows)
    avg_melee_ratio = sum(r["melee_ratio"] for r in rows) / len(rows)
    avg_tyr_kills = sum(r["tyr_kills_avg"] for r in rows) / len(rows)
    avg_opp_kills = sum(r["opp_kills_avg"] for r in rows) / len(rows)
    avg_tyr_strikes = sum(r["tyr_melee_strikes_avg"] for r in rows) / len(rows)
    avg_opp_strikes = sum(r["opp_melee_strikes_avg"] for r in rows) / len(rows)

    print(f"AVG WR across 3 matchups: {avg_wr:.1f}%  (real {REAL_TYRANID_WR:.1f}%, "
          f"diff {avg_wr-REAL_TYRANID_WR:+.1f}pt)")
    print()
    print("=== Hypothesis tests ===")
    print(f"H_SwarmKills:    TYR kills/battle {avg_tyr_kills:.2f}  vs  OPP kills/battle {avg_opp_kills:.2f}  "
          f"(ratio {avg_kill_ratio:.2f}x)")
    print(f"H_SynapseExploit: fraction of battles where ALL TYR SYNAPSE units survive R1-R5: "
          f"{avg_synapse*100:.1f}%")
    print(f"H_ChargeWave:    TYR melee strikes/battle {avg_tyr_strikes:.2f}  vs  "
          f"OPP melee strikes/battle {avg_opp_strikes:.2f}  (ratio {avg_melee_ratio:.2f}x)")


if __name__ == "__main__":
    main()
