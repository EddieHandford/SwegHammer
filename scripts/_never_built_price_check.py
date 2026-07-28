"""Are the never-built archetype entries simply the expensive ones?

scripts/_archetype_sweep_all.py found 31 template entries that no seed ever
fields. The cheapest possible explanation is price: the seed-budget walk and the
per-name fill cap cannot afford them, so the builder silently substitutes. If the
never-built set is systematically dearer than the built set, that is one shared
bug rather than thirty-one separate ones.

Prints the minimum squad price of every declared entry, split by whether the
builder ever fields it.

Run: PYTHONHASHSEED=0 python -m scripts._never_built_price_check
"""
from __future__ import annotations
import collections
import os
import random
import statistics

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG
from scripts.evaluate_vs_meta import FACTIONS

SEEDS = [int(s) for s in os.environ.get("NB_SEEDS", "0,1,2,3").split(",")]
PTS = int(os.environ.get("NB_POINTS", "2000"))


def _min_squad_price(p) -> float:
    return p.points_cost * max(1, getattr(p, "min_models", 1) or 1)


def main() -> None:
    built_px, never_px = [], []
    never_rows = []
    for fac in FACTIONS:
        templates = ARCHETYPES.get(fac, {})
        if len(templates) > 1:
            continue          # multi-template faction: absence is not evidence
        declared = {}
        for entries in templates.values():
            for k in entries:
                if k in UNIT_CATALOG:
                    declared[UNIT_CATALOG[k].name] = UNIT_CATALOG[k]
        seen = collections.Counter()
        for seed in SEEDS:
            army = build_faction_random_army("A", fac, PTS, rng=random.Random(seed),
                                             use_archetype=True)
            for u in army.units:
                seen[u.profile.name or "?"] += 1
        for nm, p in declared.items():
            px = _min_squad_price(p)
            if seen[nm]:
                built_px.append(px)
            else:
                never_px.append(px)
                never_rows.append((px, fac, nm))

    print("=== declared archetype entries: price of built versus never built ===")
    for label, xs in (("BUILT      ", built_px), ("NEVER BUILT", never_px)):
        if not xs:
            continue
        xs_sorted = sorted(xs)
        print(f"  {label}  n={len(xs):<4} median={statistics.median(xs):6.0f}  "
              f"mean={statistics.mean(xs):6.0f}  min={xs_sorted[0]:5.0f}  "
              f"max={xs_sorted[-1]:5.0f}")
    if built_px and never_px:
        print(f"\n  the never-built set is "
              f"{statistics.median(never_px)/max(1,statistics.median(built_px)):.2f}x "
              f"the median price of the built set")
    print("\n  every never-built entry, dearest first:")
    for px, fac, nm in sorted(never_rows, reverse=True):
        print(f"      {px:6.0f}   {fac:<22} {nm}")


if __name__ == "__main__":
    main()
