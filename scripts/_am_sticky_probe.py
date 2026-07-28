"""Does the Cadian Shock Troops sticky objective actually fire?

The victory-point decomposition says Astra Militarum's remaining deficit is
PRIMARY (23.2 against the opponent's 40.8), not secondary — and its starting
objective control is normal (111, the highest of its four worst matchups). So the
objective control must be dying. The real-world mechanism that makes Astra
Militarum's primary work anyway is the Cadian Shock Troops sticky objective: the
bodies die, the claim persists. If that is not firing, the primary collapse is
explained.

Counts objective-marker-rounds by sticky state.

Run: PYTHONHASHSEED=0 python -m scripts._am_sticky_probe
"""
from __future__ import annotations
import os
import random
from collections import Counter

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = "Astra Militarum"
OPPS = ["Genestealer Cults", "Adepta Sororitas", "Necrons", "Death Guard"]
N = int(os.environ.get("SP_N", "3"))
_idx = {f: i for i, f in enumerate(FACTIONS)}
C = Counter()

_real = SIM.Battle._assign_army_oc if hasattr(SIM.Battle, "_assign_army_oc") else None

if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            batt = SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                              primary_mission=_pick_primary_mission(ps))
            # count how many models carry the datasheet flag at all
            for u in a.units:
                if getattr(u.profile, "sticky_objective", False):
                    C["models carrying sticky_objective"] += 1
            batt.run()
            so = getattr(batt, "_sticky_owner", {}) or {}
            for _obj, owner in so.items():
                C[f"end-of-battle sticky markers owned by {owner}"] += 1
            C["games"] += 1
    print(f"=== Cadian sticky objective, {C['games']} games ===")
    for k, v in C.most_common():
        if k == "games":
            continue
        print(f"  {v:6d}  {k}   ({v/max(1,C['games']):.2f}/game)")
