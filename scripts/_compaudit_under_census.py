"""
Read-only sim census for the under-pole list-composition audit.

Samples 20 archetype builds per target under-pole faction and reports, per
faction: the archetype template chosen (Daemons rotate), the detachment
received, the aggregate unit composition (squads / models / points share),
body count, total wounds, wounds-per-point, and which EPIC HERO / centerpiece
units are actually fielded. No evaluation sweep — archetype-build sampling only.

Run:
  PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts._compaudit_under_census
"""
from __future__ import annotations

import collections
import os
import random

from code.army_builder import build_faction_random_army, is_epic_hero
from code.units import UNIT_CATALOG

FACTIONS = [
    "Astra Militarum",
    "Orks",
    "Chaos Daemons",
    "Genestealer Cults",
]

N = 20
BUDGET = 2000.0


def _wounds(profile):
    for attr in ("health", "wounds", "hp"):
        v = getattr(profile, attr, None)
        if v:
            return float(v)
    return 1.0


def census_faction(faction: str):
    det_counter = collections.Counter()
    arch_counter = collections.Counter()
    unit_squads = collections.Counter()      # name -> total squads across builds
    unit_models = collections.Counter()      # name -> total models across builds
    unit_points = collections.Counter()      # name -> total points across builds
    unit_appears = collections.Counter()     # name -> builds in which it appears
    epic_hero_appears = collections.Counter()
    centerpiece_counter = collections.Counter()

    body_counts = []
    wound_totals = []
    point_totals = []

    for s in range(N):
        army = build_faction_random_army(
            "A", faction, BUDGET, rng=random.Random(s), use_archetype=True
        )
        det = getattr(army, "detachment", None)
        det_name = getattr(det, "name", None) if det is not None else "NONE"
        det_counter[det_name] += 1

        # Aggregate by squad (units sharing squad_id are one squad).
        squads = collections.defaultdict(lambda: [0, 0.0])  # name -> [models, points]
        squad_ids_seen = {}
        models_total = 0
        wounds_total = 0.0
        per_build_names = set()
        per_build_eh = set()

        # group models into squads by squad_id
        sq_map = collections.defaultdict(list)
        for u in army.units:
            sid = getattr(u, "squad_id", None)
            key = (sid, u.profile.name) if sid is not None else (id(u), u.profile.name)
            sq_map[key].append(u)

        max_squad_points = 0.0
        max_squad_name = None
        for (sid, pname), members in sq_map.items():
            prof = members[0].profile
            n_models = len(members)
            pts = prof.points_cost * n_models
            squads[pname][0] += n_models
            squads[pname][1] += pts
            models_total += n_models
            wounds_total += _wounds(prof) * n_models
            per_build_names.add(pname)
            if is_epic_hero(prof):
                per_build_eh.add(pname)
            if pts > max_squad_points:
                max_squad_points = pts
                max_squad_name = pname

        for pname, (m, pts) in squads.items():
            unit_squads[pname] += 1
            unit_models[pname] += m
            unit_points[pname] += pts
        for pname in per_build_names:
            unit_appears[pname] += 1
        for eh in per_build_eh:
            epic_hero_appears[eh] += 1
        if max_squad_name:
            centerpiece_counter[max_squad_name] += 1

        body_counts.append(models_total)
        wound_totals.append(wounds_total)
        point_totals.append(army.total_points)

    print("=" * 78)
    print(f"FACTION: {faction}   (N={N} builds @ {int(BUDGET)}pts)")
    print("-" * 78)
    print("Detachment received:")
    for name, c in det_counter.most_common():
        print(f"    {c:2d}/{N}  {name}")
    if len(arch_counter):
        pass
    avg_body = sum(body_counts) / len(body_counts)
    avg_wounds = sum(wound_totals) / len(wound_totals)
    avg_pts = sum(point_totals) / len(point_totals)
    print(f"Avg body count : {avg_body:6.1f} models "
          f"(min {min(body_counts)}, max {max(body_counts)})")
    print(f"Avg wounds     : {avg_wounds:6.1f}  "
          f"| wounds/point = {avg_wounds/avg_pts:.4f}")
    print(f"Avg points     : {avg_pts:6.1f}")
    print("Centerpiece (most-expensive squad) frequency:")
    for name, c in centerpiece_counter.most_common(6):
        print(f"    {c:2d}/{N}  {name}")
    print("EPIC HERO units fielded (build appearance count):")
    if epic_hero_appears:
        for name, c in epic_hero_appears.most_common():
            print(f"    {c:2d}/{N}  {name}")
    else:
        print("    (none)")
    print("Top units by total points share across all builds:")
    ranked = sorted(unit_points.items(), key=lambda kv: -kv[1])
    for name, pts in ranked[:18]:
        appears = unit_appears[name]
        models = unit_models[name]
        print(f"    {pts:8.0f}pt  {appears:2d}/{N} builds  "
              f"{models:3d} models total  {name}")
    print()


def main():
    for fac in FACTIONS:
        census_faction(fac)


if __name__ == "__main__":
    main()
