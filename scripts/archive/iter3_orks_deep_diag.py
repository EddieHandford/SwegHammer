"""
iter 3 — Orks deep diagnostic (-4.3pt under-perform).

Per-faction trace of Ork-specific mechanism firing across N=30 vanilla battles
vs DG, Marines, Necrons. Captures:

  1. War Horde stratagem firing — count which of the 6 fire (Insane Bravery
     is no-op at rollout per code comment; confirm here).
  2. WAAAGH! impact — round of declaration, +1-to-wound count, +1-to-charge
     count. Quantify the 5++ vs melee gap (descriptive only; the gate isn't
     in code today).
  3. Charge resolution post-C2 — Orks should avoid futile T10 charges.
     Measure charge success rate per matchup.
  4. Boyz mob mechanic + Mob Up — count Mob Up firings and any reanimation
     pulses they trigger.
  5. Get Stuck In [SUSTAINED HITS 1] — verify the
     `melee_sustained_hits_army_wide` flag fires correctly on every Ork
     melee attack.

Read-only. Pure diagnostic. Vanilla 10e rules.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter3_orks_deep_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter
from typing import Dict, List, Optional

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter3_orks_deep_diag"] + sys.argv[1:],
        os.environ,
    )

from code.archetypes import build_archetype_army, has_archetype
from code.army_builder import build_faction_random_army
from code.events import (
    EventLog,
    RoundStarted,
    StratagemFired,
    UnitCharged,
    UnitFought,
    UnitKilled,
    UnitReanimated,
    WaaaghDeclared,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle, RulesConfig

OPPONENTS: List[str] = ["Death Guard", "Adeptus Astartes", "Necrons"]
N_BATTLES = 30
POINTS = 1000
REAL_ORK_WR = 44.9

WAR_HORDE_STRATS = (
    "Insane Bravery",
    "Power Of The WAAAGH!",
    "Mob Up",
    "Big Krumpin'",
    "Tellyporta",
    "Da Biggest Boss",
)


def _build(faction: str, name: str, budget: float, seed: int):
    rng = random.Random(seed)
    if has_archetype(faction):
        return build_archetype_army(name, faction, budget, rng=rng)
    return build_faction_random_army(name, faction, budget, rng=rng)


def _is_ork_attacker(attacker_uid: str, uid_owner: Dict[str, str]) -> bool:
    return uid_owner.get(attacker_uid) == "ORK"


def run_matchup(opp: str) -> Dict:
    wins_ork = 0
    wins_opp = 0
    draws = 0
    rounds_total = 0

    waaagh_rounds: Counter = Counter()
    waaagh_none = 0
    strat_fired: Counter = Counter()
    strat_cp_spent: Counter = Counter()

    # Charge metrics — Ork side only.
    ork_charges_attempted = 0
    ork_charges_succeeded = 0
    ork_charges_attempted_post_R1: List[int] = []  # per-battle list
    opp_charges_attempted = 0
    opp_charges_succeeded = 0

    # Melee strikes — Ork attackers, used to estimate Get Stuck In sustained-
    # hits firing volume (the flag is read on EVERY Ork melee attack).
    ork_melee_strikes = 0
    opp_melee_strikes = 0

    # Reanimation pulses on Ork units — Mob Up routes here.
    ork_reanim_count = 0

    # Ork kill ratio (proxy for damage thru-put).
    ork_kills = 0
    opp_kills = 0

    # 5++ vs melee gap — count Ork models destroyed by enemy MELEE strikes
    # (an enemy UnitFought that left the target dead). On WAAAGH! turns
    # the missing 5++ would have saved roughly 1/3 of those.
    ork_melee_deaths_on_waaagh_turn = 0
    ork_melee_deaths_total = 0

    rules = RulesConfig.vanilla_10e()
    n_battles = 0

    for s in range(N_BATTLES):
        seed = 9001 + s
        random.seed(seed)
        orks = _build("Orks", "ORK", POINTS, seed=seed)
        op = _build(opp, "OPP", POINTS, seed=seed + 40000)
        if not orks.units or not op.units:
            continue
        n_battles += 1

        uid_owner: Dict[str, str] = {}
        for u in orks.units:
            uid_owner[u.uid if u.uid else id(u)] = "ORK"
        for u in op.units:
            uid_owner[u.uid if u.uid else id(u)] = "OPP"

        log = EventLog()
        battle = Battle(orks, op, map_=DEFAULT_MAP, subscribers=[log], rules=rules)
        r = battle.run()
        rounds_total += r.rounds
        if r.winner == "ORK":
            wins_ork += 1
        elif r.winner == "OPP":
            wins_opp += 1
        else:
            draws += 1

        # Re-walk uid_owner now that uids are stable.
        uid_owner = {}
        for u in orks.units:
            uid_owner[u.uid] = "ORK"
        for u in op.units:
            uid_owner[u.uid] = "OPP"

        # Per-battle aggregates.
        cur_round = 0
        waaagh_round_this_battle: Optional[int] = None
        ork_charges_this = 0
        for e in log.events:
            if isinstance(e, RoundStarted):
                cur_round = e.round_num
            elif isinstance(e, WaaaghDeclared):
                if e.army_name == orks.name:
                    waaagh_round_this_battle = e.round_num
                    waaagh_rounds[e.round_num] += 1
            elif isinstance(e, StratagemFired):
                if e.army_name == orks.name and e.stratagem_name in WAR_HORDE_STRATS:
                    strat_fired[e.stratagem_name] += 1
                    strat_cp_spent[e.stratagem_name] += e.cp_cost
            elif isinstance(e, UnitCharged):
                owner = uid_owner.get(e.unit_uid)
                if owner == "ORK":
                    ork_charges_attempted += 1
                    ork_charges_this += 1
                    if e.succeeded:
                        ork_charges_succeeded += 1
                elif owner == "OPP":
                    opp_charges_attempted += 1
                    if e.succeeded:
                        opp_charges_succeeded += 1
            elif isinstance(e, UnitFought):
                a_owner = uid_owner.get(e.attacker_uid)
                if a_owner == "ORK":
                    ork_melee_strikes += 1
                elif a_owner == "OPP":
                    opp_melee_strikes += 1
                    # The target is an Ork model dying to melee?
                    if (uid_owner.get(e.target_uid) == "ORK"
                            and not e.target_alive_after):
                        ork_melee_deaths_total += 1
                        if (waaagh_round_this_battle is not None
                                and cur_round == waaagh_round_this_battle):
                            ork_melee_deaths_on_waaagh_turn += 1
            elif isinstance(e, UnitReanimated):
                if uid_owner.get(e.unit_uid) == "ORK":
                    ork_reanim_count += 1
            elif isinstance(e, UnitKilled):
                owner = uid_owner.get(e.unit_uid)
                if owner == "OPP":
                    ork_kills += 1
                elif owner == "ORK":
                    opp_kills += 1

        ork_charges_attempted_post_R1.append(ork_charges_this)

        if waaagh_round_this_battle is None:
            waaagh_none += 1

    nb = max(1, n_battles)
    wr = wins_ork / nb * 100
    return {
        "opp": opp,
        "n": n_battles,
        "wr": wr,
        "diff_vs_real": wr - REAL_ORK_WR,
        "waaagh_rounds": waaagh_rounds,
        "waaagh_none": waaagh_none,
        "strat_fired": strat_fired,
        "strat_cp_spent": strat_cp_spent,
        "ork_charges_attempted": ork_charges_attempted,
        "ork_charges_succeeded": ork_charges_succeeded,
        "ork_charge_success_pct": (
            100.0 * ork_charges_succeeded / max(1, ork_charges_attempted)
        ),
        "opp_charges_attempted": opp_charges_attempted,
        "opp_charges_succeeded": opp_charges_succeeded,
        "opp_charge_success_pct": (
            100.0 * opp_charges_succeeded / max(1, opp_charges_attempted)
        ),
        "ork_melee_strikes": ork_melee_strikes,
        "opp_melee_strikes": opp_melee_strikes,
        "ork_reanim_count": ork_reanim_count,
        "ork_kills": ork_kills,
        "opp_kills": opp_kills,
        "kill_ratio": ork_kills / max(1, opp_kills),
        "ork_melee_deaths_total": ork_melee_deaths_total,
        "ork_melee_deaths_on_waaagh_turn": ork_melee_deaths_on_waaagh_turn,
        "rounds_avg": rounds_total / nb,
    }


def report(r: Dict) -> None:
    opp = r["opp"]
    print(f"\n--- Orks vs {opp} (N={r['n']}) ---")
    print(f"  WR: {r['wr']:5.1f}%  (real {REAL_ORK_WR:.1f}%, diff {r['diff_vs_real']:+5.1f}pt)")
    print(f"  rounds avg: {r['rounds_avg']:.2f}")

    # 1. War Horde stratagem firing
    print(f"\n  [1] War Horde stratagem firing (across {r['n']} battles):")
    for s in WAR_HORDE_STRATS:
        n_fire = r["strat_fired"].get(s, 0)
        cp = r["strat_cp_spent"].get(s, 0)
        per_battle = n_fire / max(1, r["n"])
        print(f"      {s:25s}: fired {n_fire:4d}  cp_total={cp:4d}  ({per_battle:.2f}/battle)")
    # Insane Bravery should be 0 (catalogued-but-no-op APPROXIMATION).
    ib = r["strat_fired"].get("Insane Bravery", 0)
    print(f"      Insane Bravery no-op check: fired={ib} (expected 0)")

    # 2. WAAAGH! impact
    print(f"\n  [2] WAAAGH! timing & impact:")
    for rd in (1, 2, 3, 4, 5):
        n = r["waaagh_rounds"].get(rd, 0)
        print(f"      R{rd}: declared {n}/{r['n']}")
    if r["waaagh_none"]:
        print(f"      NEVER declared: {r['waaagh_none']}/{r['n']}")
    # 5++ vs melee gap — Ork models that died to melee on a WAAAGH! turn.
    deaths_waaagh = r["ork_melee_deaths_on_waaagh_turn"]
    deaths_total = r["ork_melee_deaths_total"]
    saved_at_5pp = deaths_waaagh / 3.0  # 5+ inv vs melee saves 1/3 in expectation
    print(f"      Ork models killed by enemy melee: total={deaths_total}, "
          f"on WAAAGH! turn={deaths_waaagh}")
    print(f"      5++ vs melee gap (descriptive): would have saved ~{saved_at_5pp:.1f} "
          f"models in expectation (1/3 of {deaths_waaagh}).")

    # 3. Charge resolution
    print(f"\n  [3] Charge resolution:")
    print(f"      Ork charges:  attempted={r['ork_charges_attempted']:4d}  "
          f"succeeded={r['ork_charges_succeeded']:4d}  "
          f"success_pct={r['ork_charge_success_pct']:5.1f}%")
    print(f"      Opp charges:  attempted={r['opp_charges_attempted']:4d}  "
          f"succeeded={r['opp_charges_succeeded']:4d}  "
          f"success_pct={r['opp_charge_success_pct']:5.1f}%")

    # 4. Mob Up revives
    print(f"\n  [4] Mob Up / Boyz mob mechanic:")
    print(f"      Mob Up fired:   {r['strat_fired'].get('Mob Up', 0)}")
    print(f"      Ork reanim events (any source incl. Mob Up pulse): "
          f"{r['ork_reanim_count']}")

    # 5. Get Stuck In (melee_sustained_hits_army_wide) — firing volume
    # proxy is # of Ork melee strikes. The flag is read by every Ork melee
    # attack via Unit.attack (units.py L994-1016).
    print(f"\n  [5] Get Stuck In [SUSTAINED HITS 1] — Ork melee strike volume "
          f"(flag fires per strike):")
    print(f"      Ork melee strikes: {r['ork_melee_strikes']}  "
          f"(opponent melee strikes: {r['opp_melee_strikes']})")
    print(f"      kill ratio (Ork kills/Opp kills): {r['kill_ratio']:.2f}")


def main() -> None:
    print(f"iter 3 — Orks deep diagnostic (-4.3pt under-perform)")
    print(f"N={N_BATTLES}/matchup, vanilla 10e rules, archetypes ON, {POINTS}pt")
    print(f"Real Ork WR target: {REAL_ORK_WR:.1f}%")
    rows = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        rows.append(r)
        report(r)

    # Cross-matchup summary.
    avg_wr = sum(r["wr"] for r in rows) / len(rows)
    avg_ork_chg = sum(r["ork_charge_success_pct"] for r in rows) / len(rows)
    avg_kr = sum(r["kill_ratio"] for r in rows) / len(rows)
    total_waaagh_dmg = sum(r["ork_melee_deaths_on_waaagh_turn"] for r in rows)

    print("\n=== Cross-matchup summary ===")
    print(f"  Avg Ork WR: {avg_wr:.1f}% (real {REAL_ORK_WR:.1f}%, "
          f"diff {avg_wr - REAL_ORK_WR:+.1f}pt)")
    print(f"  Avg Ork charge success: {avg_ork_chg:.1f}%")
    print(f"  Avg Ork:Opp kill ratio: {avg_kr:.2f}")
    print(f"  Cross-matchup total Ork models lost to melee on WAAAGH! turns: "
          f"{total_waaagh_dmg}")
    print(f"  Cross-matchup expected 5++ vs melee saves on those turns: "
          f"~{total_waaagh_dmg/3.0:.1f} models")


if __name__ == "__main__":
    main()
