"""Which Emperor's Children units does the advance-suppression filter hold?

SWEG_EC_RANGED_HOLD screened at +24.44 - Emperor's Children 39.7 to 64.1 against
a real 53.3, overshooting the target by 10.8. A faithful piloting correction
("Advancing forfeits non-ASSAULT shooting, so do not Advance a gun unit onto an
objective") should not move a faction twenty-four points. That magnitude is
evidence the shared filter is holding units it should not, not evidence the
lever is good.

The shared filter is ranged damage per activation >= 2.0 AND range >= 18 inches,
read from the PRIMARY weapon profile only. This prints every unit the Emperor's
Children archetype fields, with those two numbers and whether it qualifies, so
the membership can be judged by eye rather than inferred from a win rate.

Two things to look for:
  * a TRANSPORT in the held set. The gate's own comment says the filter holds
    "the Chaos Rhino transport (2.67 / 48 inches)". Holding a transport in place
    is not the modelled rule - the rule is about forfeiting shooting, and a
    Rhino's job is delivery. If it qualifies, the filter is over-broad.
  * units whose real firepower sits on a SECONDARY profile and so are invisible
    here. The gate's comment records exactly this for the Defiler: primary is a
    12-inch torrent, actual output is a 48-inch battle cannon at roughly 12.0
    damage per activation. That blind spot affects all eight entry points on the
    shared block, six of which are default-on.

Run: PYTHONHASHSEED=0 python -m scripts._ec_hold_membership
"""
from __future__ import annotations
import collections
import random

from code.army_builder import build_faction_random_army

FAC = "Emperor's Children"
RDPA_MIN = 2.0
RANGE_MIN = 18.0


def main() -> None:
    seen = {}
    counts = collections.Counter()
    for seed in range(8):
        army = build_faction_random_army("A", FAC, 2000,
                                         rng=random.Random(seed),
                                         use_archetype=True)
        for u in army.units:
            p = u.profile
            seen[p.name] = p
            counts[p.name] += 1

    print(f"=== {FAC}: advance-suppression filter membership ===")
    print(f"    held when ranged damage per activation >= {RDPA_MIN} "
          f"AND range >= {RANGE_MIN} inches, primary profile only\n")
    print(f"{'unit':<38}{'rDPA':>7}{'range':>8}{'assault':>9}"
          f"{'models':>8}  verdict")
    rows = []
    for name, p in seen.items():
        rdpa = ((p.attacks or 0) * (p.hit_probability or 0.0)
                * (p.weapon_damage_per_shot or 0.0))
        rng = float(getattr(p, "range_inches", 0) or 0)
        assault = bool(getattr(p, "assault", False))
        # The gate never suppresses a unit that can shoot after Advancing.
        held = (rdpa >= RDPA_MIN and rng >= RANGE_MIN and not assault)
        rows.append((held, rdpa, name, rng, assault, counts[name], p))
    rows.sort(key=lambda r: (not r[0], -r[1]))
    for held, rdpa, name, rng, assault, n, p in rows:
        kw = set(getattr(p, "unit_keywords", None) or ())
        tag = ""
        if held and ("TRANSPORT" in kw or "Rhino" in name or "Serpent" in name):
            tag = "   <-- TRANSPORT, should it hold?"
        elif held:
            tag = "   <-- HELD"
        extra = ""
        if getattr(p, "extra_ranged_profiles", None):
            extra = f"  [{len(p.extra_ranged_profiles)} extra profile(s) UNREAD]"
        print(f"{name[:37]:<38}{rdpa:>7.2f}{rng:>8.0f}"
              f"{('yes' if assault else 'no'):>9}{n:>8}{tag}{extra}")

    held_n = sum(1 for r in rows if r[0])
    print()
    print(f"  {held_n} of {len(rows)} fielded datasheets are held.")
    print()
    print("  A unit with unread extra profiles may have its real firepower")
    print("  hidden from this filter - the Defiler case the gate's own comment")
    print("  documents. That blind spot is shared by all eight entry points on")
    print("  the advance-suppression block, six of which are default-on.")


if __name__ == "__main__":
    main()
