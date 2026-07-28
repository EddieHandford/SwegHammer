"""Adjudicate the Emperor's Children template cost against the documented figure.

docs/DECISION_LEDGER.md and the SWEG_EC_LIST3 comment both state the ACTIVE
Emperor's Children template is a cost-infeasible union: 2,920 points at
competitive squad sizes and 2,480 even at the codebase's own minimum-size
seed-walk currency (`_squad_cost`), against a 2,000 budget.

scripts/_realization_vs_ordering measured 0.73 of budget - about 1,460 - using
that same `_squad_cost` convention. Those cannot both be right, and the claim is
load-bearing: task #39 recommends re-screening SWEG_EC_LIST3 partly BECAUSE what
it replaces is infeasible.

Three candidate readings of "the template's cost" are priced here:

  distinct    one minimum-sized squad per declared entry (a union)
  by count    each entry's declared count treated as a squad multiplier
  seed slice  what _instantiate_template is actually allowed to spend

The third is the one that decides feasibility in practice, because the template
only seeds a FRACTION of the budget and `_random_fill` spends the rest.

Run: PYTHONHASHSEED=0 python -m scripts._ec_cost_check
"""
from __future__ import annotations
import os

from code.archetypes import (
    ARCHETYPES, _effective_template, _squad_cost, SEED_FRACTION,
)
from code.units import UNIT_CATALOG

FAC = os.environ.get("EC_FACTION", "Emperor's Children")
BUDGET = 2000.0


def main() -> None:
    templates = ARCHETYPES.get(FAC)
    if not templates:
        print(f"{FAC}: no archetype")
        return

    for tname, entries in templates.items():
        eff = _effective_template(FAC, entries)
        print(f"=== {FAC} / {tname} — {len(eff)} effective entries ===")
        print(f"{'entry':<44}{'count':>7}{'min':>5}{'squad cost':>12}"
              f"{'x count':>10}")
        distinct = by_count = 0.0
        for key, count in sorted(eff.items(), key=lambda kv: -kv[1]):
            p = UNIT_CATALOG.get(key)
            if p is None:
                print(f"{key:<44}{count:>7}   NOT IN CATALOGUE")
                continue
            sc = _squad_cost(key)
            distinct += sc
            by_count += sc * count
            print(f"{p.name[:43]:<44}{count:>7}"
                  f"{max(1, p.min_models):>5}{sc:>12.0f}{sc * count:>10.0f}")
        print()
        print(f"  distinct (one min squad per entry): {distinct:>8.0f} "
              f"({distinct / BUDGET:.2f} of budget)")
        print(f"  by declared count:                  {by_count:>8.0f} "
              f"({by_count / BUDGET:.2f} of budget)")
        seed_slice = SEED_FRACTION * BUDGET
        print(f"  seed slice the template may spend:  {seed_slice:>8.0f} "
              f"(SEED_FRACTION {SEED_FRACTION})")
        print()
        if distinct > seed_slice:
            print(f"  The DISTINCT union alone exceeds the seed slice by "
                  f"{distinct - seed_slice:.0f} points, so the seed walk must")
            print("  drop entries every build — this is the realization lottery.")
        else:
            print("  The distinct union FITS the seed slice; every declared entry")
            print("  can be seeded, and any absence is a build-order effect")
            print("  rather than an affordability one.")
        print()


if __name__ == "__main__":
    main()
