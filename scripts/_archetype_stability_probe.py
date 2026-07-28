"""How much of each faction's army is the template, and how much is random fill?

A template that declares 700 points of a 2000-point army leaves the builder to
choose the other 65 percent by random fill. Real competitive lists are not
random: two players bringing the same archetype bring nearly the same army. If
the simulator's army varies wildly between seeds, then no single game is playing
the meta list even when the template itself is correctly sourced.

Two numbers per faction:

  declared share   template points as a fraction of the 2000-point budget
  instability      mean pairwise Jaccard DISTANCE between the datasheet sets
                   fielded across seeds (0 = every seed fields the same units,
                   1 = no two seeds share a single datasheet)

This is a fidelity question distinct from task #32's provenance question: a
template can cite the right list and still be too thin to enforce it.

Run: PYTHONHASHSEED=0 python -m scripts._archetype_stability_probe
"""
from __future__ import annotations
import itertools
import os
import random

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG
from scripts.evaluate_vs_meta import FACTIONS

SEEDS = [int(s) for s in os.environ.get("AS_SEEDS", "0,1,2,3,4").split(",")]
PTS = int(os.environ.get("AS_POINTS", "2000"))


def _declared_points(fac) -> float:
    best = 0.0
    for entries in ARCHETYPES.get(fac, {}).values():
        tot = 0.0
        for k, v in entries.items():
            p = UNIT_CATALOG.get(k)
            if p:
                tot += p.points_cost * max(1, getattr(p, "min_models", 1) or 1) * v
        best = max(best, tot)
    return best


def main() -> None:
    rows = []
    for fac in FACTIONS:
        sets = []
        for seed in SEEDS:
            army = build_faction_random_army("A", fac, PTS, rng=random.Random(seed),
                                             use_archetype=True)
            sets.append(frozenset(u.profile.name for u in army.units))
        dists = []
        for a, b in itertools.combinations(sets, 2):
            union = len(a | b)
            dists.append(1.0 - (len(a & b) / union) if union else 0.0)
        instability = sum(dists) / len(dists) if dists else 0.0
        dec = _declared_points(fac)
        rows.append((instability, fac, dec, dec / PTS, len(sets[0])))

    rows.sort(reverse=True)
    print(f"=== archetype grip: declared share versus seed-to-seed instability "
          f"({len(SEEDS)} seeds, {PTS} points) ===")
    print(f"{'faction':<24}{'declared':>9}{'share':>8}{'instability':>13}"
          f"{'datasheets':>12}")
    for inst, fac, dec, share, ndat in rows:
        flag = ""
        if inst >= 0.45:
            flag = "   <-- army barely repeats between seeds"
        elif share < 0.45:
            flag = "   <-- template covers under half the budget"
        print(f"{fac:<24}{dec:>9.0f}{share:>8.0%}{inst:>13.2f}{ndat:>12}{flag}")
    print()
    mean_inst = sum(r[0] for r in rows) / len(rows)
    print(f"  mean instability across factions: {mean_inst:.2f}")
    print("  (0 = every seed fields the same datasheets; 1 = no overlap at all)")


if __name__ == "__main__":
    main()
