"""Which catalogue units would change role if melee-only units were classed MELEE?

`code/roles.py::classify` runs its HORDE test BEFORE the capability tests:

    if p.health == 1 and p.save >= 4 and total < 1.5:
        return "HORDE"
    ...
    if r == 0:
        return "MELEE"

So a model with ZERO ranged output is still labelled HORDE whenever it has one
wound — and `pick_move_intent` only routes the MELEE role into the engage branch,
so such a unit is piloted to objectives and never into combat. Measured on
Tyranids: Hormagaunts (ranged damage 0.000, melee 0.250, health 1) are HORDE and
take 0 percent ENGAGE intents, 227 points a game for 1.7 melee wounds, 11 percent
of charges connecting; Tyrant Guard (ranged 0.000, melee 1.111, health 4) is
MELEE and takes 82.8 percent ENGAGE. Wound count decides, not capability.

Before changing a shared classifier this prints EVERY catalogue unit that would
flip, so the blast radius across all twenty-two factions is visible first. A
faction whose horde is genuinely a screening body rather than an assault unit
should not be quietly converted into an assault unit.

Read-only. Run: python -m scripts._role_flip_report
"""
from __future__ import annotations
import collections

from code.roles import classify, combat_profile, expected_melee_dpa
from code.units import UNIT_CATALOG


def would_flip(p) -> bool:
    """True iff the unit is HORDE today but is MELEE_ONLY by capability.

    An earlier version tested `expected_ranged_dpa(p) <= 0.0` and found ZERO
    flips, because a melee-only catalogue entry stores its talons in the ranged
    slot with `range_inches = 1` — so it never reads as zero-ranged at catalogue
    level. `combat_profile` uses reach instead.
    """
    return classify(p) == "HORDE" and combat_profile(p) == "MELEE_ONLY"


def main() -> None:
    by_faction = collections.defaultdict(list)
    horde_total = collections.Counter()
    for key, p in UNIT_CATALOG.items():
        role = classify(p)
        if role == "HORDE":
            horde_total[(p.faction or "?")] += 1
        if would_flip(p):
            by_faction[p.faction or "?"].append(
                (p.name or key, expected_melee_dpa(p), float(p.points_cost or 0))
            )

    flips = sum(len(v) for v in by_faction.values())
    print(f"catalogue units: {len(UNIT_CATALOG)}")
    print(f"currently HORDE: {sum(horde_total.values())}")
    print(f"WOULD FLIP to MELEE (HORDE today, zero ranged output): {flips}\n")
    for fac in sorted(by_faction, key=lambda f: -len(by_faction[f])):
        rows = by_faction[fac]
        print(f"{fac}  ({len(rows)} of {horde_total[fac]} horde units)")
        for name, m, pts in sorted(rows, key=lambda r: -r[1]):
            print(f"    {name[:38]:38s} melee {m:5.3f}  {pts:6.1f} pts/model")
        print()


if __name__ == "__main__":
    main()
