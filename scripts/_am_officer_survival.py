"""Does SWEG_OFFICER_STANDOFF keep Astra Militarum Officers alive without
costing Orders?

The standoff heuristic slides an Officer's move target away from the nearest
enemy while keeping every model it must order inside the 6-inch aura. Both halves
have to be checked: character survival must RISE and Orders per round must NOT
fall, or the lever has simply traded the army rule for safety.

Run: PYTHONHASHSEED=0 python -m scripts._am_officer_survival
"""
from __future__ import annotations
import os
import random
from collections import Counter

import code.orders as O
import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = "Astra Militarum"
N = int(os.environ.get("OS_N", "3"))
OPPS = ["Adeptus Astartes", "Necrons", "Adepta Sororitas",
        "Genestealer Cults", "Death Guard", "Aeldari"]
_idx = {f: i for i, f in enumerate(FACTIONS)}
C = Counter()
_real = O.dispatch_orders


def _probe(army, bs, enemy_army=None):
    issued = _real(army, bs, enemy_army=enemy_army)
    if any((u.profile.faction or "") == FAC for u in army.units):
        C["order_phases"] += 1
        C["orders"] += len(issued)
    return issued


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    O.dispatch_orders = _probe
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            fa, fb = (opp, FAC) if swap else (FAC, opp)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            batt = SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                              primary_mission=_pick_primary_mission(ps))
            batt.run()
            me = batt.b if swap else batt.a
            chars = [u for u in me.units if "CHARACTER" in (u.profile.unit_keywords or ())]
            C["chars"] += len(chars)
            C["chars_dead"] += sum(1 for u in chars if not u.is_alive)
            C["games"] += 1

    g = max(1, C["games"])
    print(f"=== Astra Militarum officers, {g} games ===")
    print(f"  characters/game          {C['chars']/g:.1f}")
    print(f"  character death rate     {100*C['chars_dead']/max(1,C['chars']):.0f}%")
    print(f"  Orders issued per round  {C['orders']/max(1,C['order_phases']):.2f}")
