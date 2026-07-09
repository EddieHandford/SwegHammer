"""DG-CRATER diagnostic (read-only): reproduce and instrument the Death Guard
elite-infantry crater cells from the standing anchor (data/_anchor_sc54a_n80_log.json).

For each requested opponent faction, replays EVERY anchor game in BOTH orderings
(Death Guard as A vs opp as B, and opp as A vs Death Guard as B) -- 80 seeds each,
160 games per cell -- verifies the replayed winner matches the anchor's recorded
winner (the mandatory reproduction gate), and collects the loss-mechanism data:

  * scoring vs attrition: capped VP split (primary / secondary), survivor counts
  * kill sources: which Death Guard unit killed each opponent unit, ranged vs melee
  * round-by-round opponent casualties and Death Guard casualties
  * Death Guard damage TAKEN per round (does the opponent gunline ever hurt it?)
  * the chosen Plague Death Guard's AI selected against this opponent

Optionally ablates the DURA-AUDIT-D1/D2/D3 Death Guard contagion gates
(SWEG_DG_CONTAGION_ESCALATION / SWEG_DG_AFFLICTED_TOUGHNESS / SWEG_DG_CHOSEN_PLAGUE)
per config to measure each piece's contribution to the Death Guard win rate in the
crater cells. Ablation runs are anchor-seeded counterfactuals on the SAME games, not
a new sweep.

Mirrors scripts._ec_crater_replay's exact reconstruction (pair_seed, archetype
build, map rotation, primary draw).

Run:
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dgcrater_replay \
      "Thousand Sons" "Grey Knights" "Genestealer Cults" "T'au Empire"

  # gate-ablation contribution table for one or two cells:
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dgcrater_replay \
      --ablate "Thousand Sons" "Grey Knights" "Genestealer Cults" "T'au Empire"

Writes data/_dgcrater_<mode>.json.
"""
from __future__ import annotations

import json
import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._dgcrater_replay"] + sys.argv[1:],
        env=os.environ).returncode)

import multiprocessing as mp

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, UnitShot, UnitFought,
    UnitKilled, ObjectiveScored, EventLog,
)
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

DG = "Death Guard"
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

# The DURA-AUDIT D-pieces, by env gate.
GATE_D1 = "SWEG_DG_CONTAGION_ESCALATION"   # 3"/6"/9" round escalation
GATE_D2 = "SWEG_DG_AFFLICTED_TOUGHNESS"    # Afflicted -1 Toughness (always-on)
GATE_D3 = "SWEG_DG_CHOSEN_PLAGUE"          # chosen Plague (Rattlejoint/Skullsquirm/Scabrous)

# Every config sets ALL THREE gates explicitly. Pool workers are reused across
# configs, and the gates are read live from os.environ at combat-resolution time,
# so a config that left a gate unset would inherit whatever a prior job on that
# worker set -- baseline must actively restore "1", not pass an empty dict.
ABLATION_CONFIGS = [
    ("baseline", {GATE_D1: "1", GATE_D2: "1", GATE_D3: "1"}),
    ("D1_off (no 3/6/9 escalation)", {GATE_D1: "0", GATE_D2: "1", GATE_D3: "1"}),
    ("D2_off (no Afflicted -1T)", {GATE_D1: "1", GATE_D2: "0", GATE_D3: "1"}),
    ("D3_off (no chosen plague)", {GATE_D1: "1", GATE_D2: "1", GATE_D3: "0"}),
    ("D1D2D3_off (all three)", {GATE_D1: "0", GATE_D2: "0", GATE_D3: "0"}),
]


def load_cell_games(path, opp):
    d = json.load(open(path, encoding="utf-8"))
    return [(a, b, s, w) for a, b, s, w in d["games"]
            if {a, b} == {DG, opp}]


def _replay(a_fac, b_fac, s, gate_env):
    for k, v in gate_env.items():
        os.environ[k] = v
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None, None, None, None
    bm = _pick_rotation_map(s)
    pm = _pick_primary_mission(pair_seed)
    log = EventLog()
    battle = Battle(a, b, map_=bm, rules=None, primary_mission=pm, subscribers=[log])
    res = battle.run()
    return res, log, battle, a


def _instrument(a_fac, b_fac, s, rec_winner, res, log, battle, opp_name):
    ev = log.events
    info = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                info[u.uid] = {"name": u.name, "army": u.army}
    dg_side = "A" if a_fac == DG else "B"
    opp_side = "B" if dg_side == "A" else "A"

    dg_start = sum(1 for i in info.values() if i["army"] == dg_side)
    opp_start = sum(1 for i in info.values() if i["army"] == opp_side)

    cur_round = 0
    last_hit_on = {}       # target_uid -> (attacker_uid, mode)
    opp_deaths_by_round = {}
    dg_deaths_by_round = {}
    opp_kills_by_dg_unit = {}   # dg unit name -> count of opp units it finished
    opp_kills_ranged = 0
    opp_kills_melee = 0
    dg_dmg_taken_by_round = {}  # round -> damage opp dealt to DG
    opp_dmg_taken_by_round = {} # round -> damage DG dealt to opp
    round_capped = []           # (round, dg_capped, opp_capped)

    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, (UnitShot, UnitFought)):
            mode = "ranged" if isinstance(e, UnitShot) else "melee"
            last_hit_on[e.target_uid] = (e.attacker_uid, mode)
            atk = info.get(e.attacker_uid, {})
            tgt = info.get(e.target_uid, {})
            if atk.get("army") == opp_side and tgt.get("army") == dg_side:
                dg_dmg_taken_by_round[cur_round] = dg_dmg_taken_by_round.get(cur_round, 0.0) + e.damage
            elif atk.get("army") == dg_side and tgt.get("army") == opp_side:
                opp_dmg_taken_by_round[cur_round] = opp_dmg_taken_by_round.get(cur_round, 0.0) + e.damage
        elif isinstance(e, UnitKilled):
            v = info.get(e.unit_uid, {})
            if v.get("army") == opp_side:
                opp_deaths_by_round[cur_round] = opp_deaths_by_round.get(cur_round, 0) + 1
                src = last_hit_on.get(e.unit_uid)
                if src is not None and info.get(src[0], {}).get("army") == dg_side:
                    si = info.get(src[0], {})
                    opp_kills_by_dg_unit[si["name"]] = opp_kills_by_dg_unit.get(si["name"], 0) + 1
                    if src[1] == "ranged":
                        opp_kills_ranged += 1
                    else:
                        opp_kills_melee += 1
            elif v.get("army") == dg_side:
                dg_deaths_by_round[cur_round] = dg_deaths_by_round.get(cur_round, 0) + 1
        elif isinstance(e, RoundEnded):
            dc = e.a_vp_capped if dg_side == "A" else e.b_vp_capped
            oc = e.b_vp_capped if dg_side == "A" else e.a_vp_capped
            round_capped.append((e.round_num, dc, oc))

    a_primary = battle._a_vp - battle._a_secondary_vp - battle._a_challenger_vp
    b_primary = battle._b_vp - battle._b_secondary_vp - battle._b_challenger_vp
    a_capped, b_capped = battle._capped_vp_pair()

    def pick(av, bv):
        return av if dg_side == "A" else bv

    dg_surv = pick(res.a_survivors, res.b_survivors)
    opp_surv = pick(res.b_survivors, res.a_survivors)
    dg_army = battle.a if dg_side == "A" else battle.b
    chosen_plague = getattr(dg_army, "dg_chosen_plague", None)

    return {
        "opp": opp_name, "s": s, "dg_side": dg_side,
        "rec": rec_winner, "rep": res.winner, "match": res.winner == rec_winner,
        "dg_win": res.winner == dg_side, "rounds": res.rounds,
        "dg_start": dg_start, "opp_start": opp_start,
        "dg_surv": dg_surv, "opp_surv": opp_surv,
        "dg_primary": pick(a_primary, b_primary), "opp_primary": pick(b_primary, a_primary),
        "dg_sec": pick(battle._a_secondary_vp, battle._b_secondary_vp),
        "opp_sec": pick(battle._b_secondary_vp, battle._a_secondary_vp),
        "dg_capped": pick(a_capped, b_capped), "opp_capped": pick(b_capped, a_capped),
        "opp_deaths_by_round": opp_deaths_by_round,
        "dg_deaths_by_round": dg_deaths_by_round,
        "opp_kills_by_dg_unit": opp_kills_by_dg_unit,
        "opp_kills_ranged": opp_kills_ranged, "opp_kills_melee": opp_kills_melee,
        "dg_dmg_taken_by_round": dg_dmg_taken_by_round,
        "opp_dmg_taken_by_round": opp_dmg_taken_by_round,
        "chosen_plague": chosen_plague,
    }


def worker(job):
    a_fac, b_fac, s, rec, opp_name, gate_env = job
    res, log, battle, dg_army = _replay(a_fac, b_fac, s, gate_env or {})
    if res is None:
        return {"opp": opp_name, "s": s, "empty": True, "match": rec is None,
                "dg_win": None, "rep": None, "rec": rec}
    return _instrument(a_fac, b_fac, s, rec, res, log, battle, opp_name)


def run_cell(anchor, opp, gate_env, pool):
    games = load_cell_games(anchor, opp)
    jobs = [(a, b, s, w, opp, gate_env) for (a, b, s, w) in games]
    results = pool.map(worker, jobs, chunksize=4)
    return results


def summarize_cell(opp, results):
    played = [r for r in results if not r.get("empty")]
    matched = sum(1 for r in results if r.get("match"))
    wins = [r for r in played if r["dg_win"]]
    n = len(played)
    wr = 100 * len(wins) / n if n else 0
    return {
        "opp": opp, "n_games": len(results), "n_played": n,
        "matched": matched, "dg_wr": wr, "n_dg_wins": len(wins),
    }


def avg(lst, k):
    vals = [x[k] for x in lst if k in x and x[k] is not None]
    return sum(vals) / len(vals) if vals else 0.0


def main():
    args = sys.argv[1:]
    ablate = False
    if args and args[0] == "--ablate":
        ablate = True
        args = args[1:]
    opps = args or ["Thousand Sons", "Grey Knights", "Genestealer Cults", "T'au Empire"]
    anchor = "data/_anchor_sc54a_n80_log.json"

    with mp.Pool(processes=12) as pool:
        if not ablate:
            out = {"mode": "instrument", "cells": {}}
            for opp in opps:
                results = run_cell(anchor, opp, {}, pool)
                summ = summarize_cell(opp, results)
                print(f"\n=== Death Guard vs {opp} ===")
                print(f"  reproduction: {summ['matched']}/{summ['n_games']} winners matched")
                print(f"  Death Guard win rate (replayed): {summ['dg_wr']:.1f}% "
                      f"({summ['n_dg_wins']}/{summ['n_played']})")
                played = [r for r in results if not r.get("empty")]
                wins = [r for r in played if r["dg_win"]]
                losses = [r for r in played if not r["dg_win"]]
                pl = {c: sum(1 for r in played if r.get("chosen_plague") == c)
                      for c in ("Rattlejoint Ague", "Skullsquirm Blight", "Scabrous Soulrot")}
                print(f"  chosen plague distribution (Death Guard side): {pl}")
                print(f"  -- over ALL played (n={len(played)}):")
                print(f"     DG capped {avg(played,'dg_capped'):.1f} vs opp capped {avg(played,'opp_capped'):.1f}"
                      f"   (primary DG {avg(played,'dg_primary'):.1f}/{avg(played,'opp_primary'):.1f},"
                      f" secondary DG {avg(played,'dg_sec'):.1f}/{avg(played,'opp_sec'):.1f})")
                print(f"     DG survivors {avg(played,'dg_surv'):.1f}/{avg(played,'dg_start'):.1f}"
                      f" ({100*avg(played,'dg_surv')/max(avg(played,'dg_start'),1e-9):.0f}%)"
                      f"   opp survivors {avg(played,'opp_surv'):.1f}/{avg(played,'opp_start'):.1f}"
                      f" ({100*avg(played,'opp_surv')/max(avg(played,'opp_start'),1e-9):.0f}%)")
                print(f"     opp kills by DG: ranged {avg(played,'opp_kills_ranged'):.1f}"
                      f"  melee {avg(played,'opp_kills_melee'):.1f}")
                def sumdict(r, k):
                    return sum(r.get(k, {}).values())
                dg_taken = sum(sumdict(r, "dg_dmg_taken_by_round") for r in played) / max(len(played),1)
                opp_taken = sum(sumdict(r, "opp_dmg_taken_by_round") for r in played) / max(len(played),1)
                print(f"     avg damage DG dealt to opp {opp_taken:.0f}"
                      f"   avg damage opp dealt to DG {dg_taken:.0f}")
                maxr = 5
                opp_cas = []; dg_cas = []; dg_dmg_r = []
                for rd in range(1, maxr + 1):
                    opp_cas.append(sum(r.get("opp_deaths_by_round", {}).get(rd, 0) for r in played) / max(len(played),1))
                    dg_cas.append(sum(r.get("dg_deaths_by_round", {}).get(rd, 0) for r in played) / max(len(played),1))
                    dg_dmg_r.append(sum(r.get("dg_dmg_taken_by_round", {}).get(rd, 0) for r in played) / max(len(played),1))
                print(f"     opp casualties by round:  " + "  ".join(f"R{i+1}:{v:.1f}" for i, v in enumerate(opp_cas)))
                print(f"     DG  casualties by round:  " + "  ".join(f"R{i+1}:{v:.1f}" for i, v in enumerate(dg_cas)))
                print(f"     DG dmg TAKEN by round:    " + "  ".join(f"R{i+1}:{v:.0f}" for i, v in enumerate(dg_dmg_r)))
                if wins:
                    print(f"  -- DG WINS (n={len(wins)}): capped {avg(wins,'dg_capped'):.1f}-{avg(wins,'opp_capped'):.1f}"
                          f"  opp surv {100*avg(wins,'opp_surv')/max(avg(wins,'opp_start'),1e-9):.0f}%")
                if losses:
                    print(f"  -- DG LOSSES (n={len(losses)}): capped {avg(losses,'dg_capped'):.1f}-{avg(losses,'opp_capped'):.1f}"
                          f"  opp surv {100*avg(losses,'opp_surv')/max(avg(losses,'opp_start'),1e-9):.0f}%")
                out["cells"][opp] = {"summary": summ, "games": results}
            json.dump(out, open("data/_dgcrater_instrument.json", "w", encoding="utf-8"))
            print("\nwrote data/_dgcrater_instrument.json")
        else:
            out = {"mode": "ablate", "cells": {}}
            print("\n=== GATE ABLATION: Death Guard win rate by config ===")
            for opp in opps:
                row = {"opp": opp, "configs": {}}
                cells = []
                for name, gate_env in ABLATION_CONFIGS:
                    results = run_cell(anchor, opp, gate_env, pool)
                    summ = summarize_cell(opp, results)
                    played = [r for r in results if not r.get("empty")]
                    opp_surv_pct = 100 * avg(played, "opp_surv") / max(avg(played, "opp_start"), 1e-9)
                    row["configs"][name] = {"dg_wr": summ["dg_wr"],
                                            "opp_surv_pct": opp_surv_pct,
                                            "matched": summ["matched"],
                                            "n_games": summ["n_games"]}
                    cells.append((name, summ["dg_wr"], opp_surv_pct, summ["matched"], summ["n_games"]))
                print(f"\n=== Death Guard vs {opp} ===")
                for name, wr, surv, matched, ng in cells:
                    tag = "  (reproduction gate)" if name == "baseline" else ""
                    print(f"  {name:<32} DG win {wr:5.1f}%   opp surv {surv:4.0f}%"
                          f"   matched {matched}/{ng}{tag}")
                out["cells"][opp] = row
            json.dump(out, open("data/_dgcrater_ablate.json", "w", encoding="utf-8"))
            print("\nwrote data/_dgcrater_ablate.json")


if __name__ == "__main__":
    main()
