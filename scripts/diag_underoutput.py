"""Under-output FIELD-AVERAGE re-measure (#86, wave 198).

The watchdog caught that wave-194's "AM/AdMech deal 55-62 vs field 79" came from
a 3-opponent round-robin slice — the SAME slice whose "taken 109" we dismissed as
a matchup artifact. So re-measure damage DEALT and TAKEN on a FIELD-AVERAGE basis
(each test faction vs ALL 21 other factions) before calling under-output the floor.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_underoutput
"""
from __future__ import annotations

import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

ALL = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
TEST = ["Astra Militarum", "Adeptus Mechanicus", "Adeptus Astartes",
        "Emperor's Children", "World Eaters"]
SEEDS = [1, 2]


def _snap(a):
    return {id(u): u.current_health for u in a.units}


def _taken(a, before):
    return sum(max(0.0, before.get(id(u), 0.0) - u.current_health) for u in a.units)


def main():
    print("=== FIELD-AVERAGE damage dealt vs taken (each test faction vs all 21) ===")
    print(f"{'faction':24} {'dealt/g':>8} {'taken/g':>8} {'net/g':>7} {'games':>6}")
    for fa in TEST:
        dealt = taken = 0.0
        games = 0
        for fb in ALL:
            if fb == fa:
                continue
            for seed in SEEDS:
                a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 5000), use_archetype=True)
                if not a.units or not b.units:
                    continue
                sa, sb = _snap(a), _snap(b)
                Battle(a, b, map_=_pick_rotation_map(seed)).run()
                dealt += _taken(b, sb)
                taken += _taken(a, sa)
                games += 1
        g = max(1, games)
        print(f"{fa:24} {dealt/g:>8.0f} {taken/g:>8.0f} {(dealt-taken)/g:>7.0f} {games:>6}")
    print()
    print("Reading: if AM/AdMech dealt is STILL low vs the Astartes control (field-")
    print("average), under-output is real -> probe the screening/melee-avoidance AI.")
    print("If dealt ~= control, the wave-194 under-output was a slice artifact too.")


if __name__ == "__main__":
    main()
