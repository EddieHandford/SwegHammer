"""Which declared archetype entries NEVER reach the table?

Task #31 records that the archetype builder fails to field declared entries
across 21 factions. This quantifies it per faction and, more usefully, NAMES the
dead entries — because a declared-but-never-built unit silently kills every
mechanic attached to it.

That is not hypothetical. Three separate leader abilities were found dead in one
session for exactly this reason:
  * Chaos Lord "Lord of Hosts"  — routed to units that ARE fielded, but the
    entry is a pure no-op (a different defect, found alongside).
  * Sorcerer "Prescience"       — the faithful rebuild is BYTE-INERT because
    the Chaos Space Marines archetype never fields a Sorcerer (#59).
  * Ironstrider Ballistarii     — the Adeptus Mechanicus anchor unit of every
    sourced May 2026 list, never fielded, while the template comment names it
    as fast support (#41).

A gate screened against a frame that cannot express it reads "no change", which
is indistinguishable from "no effect". Knowing which entries are dead tells you
which shelved work was never actually measured.

Builds real armies (session lesson #51 — never infer the fielded set from the
catalogue) and compares against the declared template keys.

Run: PYTHONHASHSEED=0 python -m scripts._declared_vs_fielded
     DVF_ARMIES=10
"""
from __future__ import annotations
import collections
import os
import random

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG

N = int(os.environ.get("DVF_ARMIES", "10"))


def main() -> None:
    rows = []
    total_declared = total_dead = 0
    dead_detail = []

    for faction in sorted(ARCHETYPES):
        templates = ARCHETYPES[faction]
        declared = {}
        for tmpl in templates.values():
            for key, count in tmpl.items():
                declared[key] = max(declared.get(key, 0), count)
        if not declared:
            continue

        fielded_names = collections.Counter()
        built = 0
        for seed in range(N):
            try:
                army = build_faction_random_army("A", faction, 2000,
                                                 rng=random.Random(seed),
                                                 use_archetype=True)
            except Exception as exc:            # a build failure is itself news
                rows.append((faction, len(declared), -1, "BUILD ERROR: %s" % exc))
                break
            built += 1
            for u in army.units:
                fielded_names[u.profile.name] += 1
        if built == 0:
            continue

        dead = []
        for key in sorted(declared):
            prof = UNIT_CATALOG.get(key)
            if prof is None:
                dead.append((key, "KEY NOT IN CATALOGUE"))
                continue
            if fielded_names.get(prof.name, 0) == 0:
                dead.append((key, prof.name))

        total_declared += len(declared)
        total_dead += len(dead)
        rows.append((faction, len(declared), len(dead), ""))
        if dead:
            dead_detail.append((faction, dead))

    print(f"=== declared archetype entries that are NEVER fielded "
          f"({N} armies per faction) ===\n")
    print(f"{'faction':<26}{'declared':>10}{'dead':>7}{'  share':>9}")
    for faction, ndecl, ndead, err in rows:
        if err:
            print(f"{faction[:25]:<26}{ndecl:>10}{'  ':>7}  {err}")
            continue
        share = (100.0 * ndead / ndecl) if ndecl else 0.0
        mark = "  <<<" if share >= 50.0 else ""
        print(f"{faction[:25]:<26}{ndecl:>10}{ndead:>7}{share:>8.0f}%{mark}")

    print()
    if total_declared:
        print(f"  TOTAL {total_dead} of {total_declared} declared entries never "
              f"reach the table ({100.0 * total_dead / total_declared:.0f}%)")
    print()
    print("=== the dead entries, by faction ===")
    for faction, dead in dead_detail:
        print(f"\n  {faction}")
        for key, name in dead:
            print(f"    {key:<52} {name}")


if __name__ == "__main__":
    main()
