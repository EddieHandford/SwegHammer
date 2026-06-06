"""Durability mis-application check (#85, wave 197).

The watchdog's unified hypothesis: the sim UNDER-credits VEHICLE durability (under-
side AM/AdMech over-fragile) + OVER-credits elite-INFANTRY durability (over-side EC
holds while out-fought). The RAIL: only a REAL mis-application (cover/save/invuln
under-applied to vehicles) is a faithful fix; if vehicles are genuinely as fragile
as their stats say, report + stop — do NOT buff.

This probe (gated SWEG_DURABILITY_INSTR) records, per target-keyword class
(VEHICLE / INFANTRY / OTHER) over real shooting across the field, the mean base
save, the AP-and-cover-modified EFFECTIVE save actually rolled, the cover-applied
rate, the mean AP faced, and the invuln-available rate. The code audit already
showed cover (target.in_cover, no VEHICLE gate), invuln, and AP all apply keyword-
neutrally — this quantifies whether VEHICLEs nonetheless end up with a worse
effective save than INFANTRY beyond what the AP they face explains, or get cover at
a much lower rate (a positional, plausibly-faithful effect for big models).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_durability
"""
from __future__ import annotations

import os
import random

os.environ["SWEG_DURABILITY_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code import units as units_mod
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
SEEDS = [1, 2, 3]
OPP_OFFSETS = [5, 11, 17]


def main():
    units_mod.DURABILITY_STATS.clear()
    n = len(FACTIONS)
    for i, fa in enumerate(FACTIONS):
        for off in OPP_OFFSETS:
            fb = FACTIONS[(i + off) % n]
            for seed in SEEDS:
                a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 5000), use_archetype=True)
                if not a.units or not b.units:
                    continue
                Battle(a, b, map_=_pick_rotation_map(seed)).run()

    print("=== realized durability per target keyword class (ranged hits) ===")
    print(f"{'class':10} {'hits':>8} {'baseSv':>7} {'effSv':>6} {'cover%':>7} {'AP':>5} {'inv%':>6}")
    for cls in ("VEHICLE", "INFANTRY", "OTHER"):
        d = units_mod.DURABILITY_STATS.get(cls)
        if not d:
            continue
        h = max(1, d["hits"])
        print(f"{cls:10} {d['hits']:>8} {d['base']/h:>7.2f} {d['eff']/h:>6.2f} "
              f"{100*d['cover']/h:>7.0f} {d['ap']/h:>5.2f} {100*d['inv']/h:>6.0f}")
    print()
    print("Reading: 'effSv' is the save actually rolled (base − AP + cover, w/ invuln).")
    print("If VEHICLE effSv is worse than INFANTRY MAINLY because AP is much higher,")
    print("that's FAITHFUL (anti-tank). If VEHICLE cover% is far below INFANTRY beyond")
    print("the big-model rule, or effSv degraded with no AP cause -> a mis-application.")


if __name__ == "__main__":
    main()
