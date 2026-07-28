"""Astra Militarum -17.5 diagnostic, instrument 1: list composition (list-realism).

Builds AM armies through the eval's own entry point
(build_faction_random_army(use_archetype=True), 2000 pts) over many seeds and
reports the POINTS split by unit class (vehicle / infantry / mounted / other)
plus the on-board body/vehicle counts. The watchdog's board-read suggested the
real AM meta runs ~60% of its points in vehicles (tanks + support); if the
sim's archetype lists field a fraction of that, the AM under-pole is partly a
list-realism gap (the durable shooty-vehicle core that carries AM is
under-fielded) rather than stats or positioning.
"""
from __future__ import annotations

import random
import statistics
from collections import defaultdict

from code.army_builder import build_faction_random_army

N = 30
FAC = "Astra Militarum"


def _class_of(p) -> str:
    kw = set(getattr(p, "unit_keywords", ()) or ())
    if "VEHICLE" in kw:
        return "vehicle"
    if "MOUNTED" in kw:
        return "mounted"
    if "INFANTRY" in kw:
        return "infantry"
    return "other"


def main() -> None:
    pts_by_class = defaultdict(list)
    frac_by_class = defaultdict(list)
    n_units = []
    for s in range(N):
        army = build_faction_random_army("A", FAC, 2000, rng=random.Random(s),
                                         use_archetype=True)
        tot = sum(u.profile.points_cost or 0.0 for u in army.units) or 1.0
        cls_pts = defaultdict(float)
        for u in army.units:
            cls_pts[_class_of(u.profile)] += (u.profile.points_cost or 0.0)
        for c in ("vehicle", "infantry", "mounted", "other"):
            pts_by_class[c].append(cls_pts.get(c, 0.0))
            frac_by_class[c].append(cls_pts.get(c, 0.0) / tot)
        n_units.append(len(army.units))

    print(f"Astra Militarum list composition (2000 pts, N={N} archetype armies)")
    print(f"  mean units fielded: {statistics.mean(n_units):.1f}")
    print(f"  {'class':10s} {'mean pts':>9s} {'mean % of army':>15s}")
    for c in ("vehicle", "infantry", "mounted", "other"):
        print(f"  {c:10s} {statistics.mean(pts_by_class[c]):9.0f} "
              f"{statistics.mean(frac_by_class[c])*100:14.1f}%")
    print(f"  --- real AM meta hypothesis: ~60% vehicle points ---")


if __name__ == "__main__":
    main()
