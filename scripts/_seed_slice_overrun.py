"""Can each faction's archetype template actually FIT its seed budget?

Task #40 records that no faction's template fits its seed slice — all 22 overrun
by 1.17 to 6.51 times. If true it matters a great deal: the seed walk spends a
fraction of the points budget on the DECLARED list and hands the remainder to
`_random_fill`, so a template that overruns its slice is only partly realised and
the rest of the army is random. That is a direct cause of declared entries never
reaching the table (#31) and of mechanics attached to them being unmeasurable
(#59, #60).

This recomputes it from the code rather than repeating the figure: declared cost
is the sum over template entries of count x points_cost, and the seed budget is
the faction's seed fraction times the 2000-point game size.

Reports the ratio per faction so the claim can be checked, and flags the menu
factions separately — for those, partial realisation is the DESIGN (the ledger
records Imperial Knights, Chaos Knights, Chaos Daemons, Emperor's Children,
Aeldari and World Eaters as oversized menus from which the builder picks a
faithful subset), so an overrun there is expected and must not be "fixed".

Run: PYTHONHASHSEED=0 python -m scripts._seed_slice_overrun
"""
from __future__ import annotations

from code.archetypes import ARCHETYPES
from code.units import UNIT_CATALOG

GAME_POINTS = 2000.0

# Menu templates: oversized by design, partial realisation intended.
MENU = {
    "Imperial Knights", "Chaos Knights", "Chaos Daemons",
    "Emperor's Children", "Aeldari", "World Eaters",
}


def seed_fraction(faction: str) -> float:
    """The seed fraction actually applied, mirroring code/archetypes.py."""
    import code.archetypes as A
    for name in ("SEED_FRACTION_BY_FACTION_SEEDLEADERS",
                 "SEED_FRACTION_BY_FACTION"):
        table = getattr(A, name, None)
        if isinstance(table, dict) and faction in table:
            return float(table[faction])
    return float(getattr(A, "SEED_FRACTION", 0.3))


def main() -> None:
    rows = []
    for faction in sorted(ARCHETYPES):
        for tmpl_name, tmpl in ARCHETYPES[faction].items():
            cost = 0.0
            missing = 0
            for key, count in tmpl.items():
                p = UNIT_CATALOG.get(key)
                if p is None:
                    missing += 1
                    continue
                per_squad = getattr(p, "points_per_squad", None)
                if per_squad:
                    cost += count * float(per_squad)
                else:
                    cost += (count * float(p.points_cost)
                             * max(1, p.min_models))
            frac = seed_fraction(faction)
            budget = frac * GAME_POINTS
            rows.append((faction, tmpl_name, cost, frac, budget,
                         cost / budget if budget else 0.0, missing))

    rows.sort(key=lambda r: -r[5])
    print(f"{'faction':<24}{'template':<26}{'declared':>9}"
          f"{'frac':>6}{'budget':>8}{'ratio':>7}")
    for f, t, cost, frac, budget, ratio, missing in rows:
        tag = "  MENU (by design)" if f in MENU else ""
        if missing:
            tag += f"  [{missing} key(s) not in catalogue]"
        print(f"{f[:23]:<24}{t[:25]:<26}{cost:>9.0f}{frac:>6.2f}"
              f"{budget:>8.0f}{ratio:>7.2f}{tag}")

    non_menu = [r for r in rows if r[0] not in MENU]
    over = [r for r in non_menu if r[5] > 1.0]
    print()
    print(f"  non-menu templates: {len(non_menu)}, of which {len(over)} "
          f"exceed their seed budget")
    if over:
        worst = max(over, key=lambda r: r[5])
        print(f"  worst non-menu overrun: {worst[0]} {worst[5]:.2f}x")
    print()
    print("  A template costing more than its seed budget cannot be fully")
    print("  seeded: the walk takes what fits and _random_fill spends the")
    print("  remainder, so the realised army is only partly the declared list.")


if __name__ == "__main__":
    main()
