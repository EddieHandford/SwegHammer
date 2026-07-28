"""Does the Astra Militarum package trade objective control for shooting?

`SWEG_AM_INFANTRY_FIRE` suppresses the Advance so the infantry keeps its Shooting
phase — but a suppressed Advance is a shorter move, so the infantry may reach
objectives later, and `SWEG_CHAFF_COMMIT_CAP` changes where the bodies go. The
corrected victory-point split says primary and secondary are EQUAL halves of the
remaining gap, so a primary regression would matter.

Reuses the existing read-only over-score instrument (`SWEG_OVERSCORE_INSTR`,
`simulator.OVERSCORE_STATS`), which records per faction how many objective
markers it won, and whether the loser was contesting (opponent on the marker and
out-counted) or absent. Applies the SWEG_SIDE_ROLLOFF re-orientation the
evaluation uses, so the frame matches (see `scripts/_am_vp_probe.py`).

Run: PYTHONHASHSEED=0 VP_OPPS=ALL python -m scripts._am_objective_probe
"""
from __future__ import annotations
import os
import random

os.environ.setdefault("SWEG_OVERSCORE_INSTR", "1")

import code.simulator as SIM
from code.simulator import OVERSCORE_STATS
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = "Astra Militarum"
N = int(os.environ.get("OB_N", "2"))
_opps = os.environ.get("VP_OPPS", "ALL")
OPPS = ([f for f in FACTIONS if f != FAC] if _opps.strip().upper() == "ALL"
        else [f.strip() for f in _opps.split(",") if f.strip()])
_idx = {f: i for i, f in enumerate(FACTIONS)}

if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    games = 0
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            fa, fb = (opp, FAC) if swap else (FAC, opp)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()
            games += 1

    d = OVERSCORE_STATS.get(FAC)
    if not d:
        print("no data for", FAC)
        raise SystemExit(0)
    tot = sum(v["scored"] for v in OVERSCORE_STATS.values())
    print(f"=== objective markers won, {games} games ===")
    print(f"  Astra Militarum markers won : {d['scored']/games:.2f}/game "
          f"({100*d['scored']/max(1,tot):.1f}% of all markers won in these games)")
    print(f"     of which CONTESTED wins  : {100*d['contested_won']/max(1,d['scored']):.0f}%")
    print(f"     of which UNCONTESTED     : {100*d['uncontested']/max(1,d['scored']):.0f}%")
    print(f"     mean winning objective control {d['sum_win_oc']/max(1,d['scored']):.1f} "
          f"vs loser {d['sum_los_oc']/max(1,d['scored']):.1f}")
    print("\n  opponents, markers won per game:")
    for f, v in sorted(OVERSCORE_STATS.items(), key=lambda kv: -kv[1]["scored"]):
        if f == FAC:
            continue
        print(f"     {v['scored']/games:5.2f}  {f}")
