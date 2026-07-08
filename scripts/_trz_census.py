"""
Read-only census for validating `SWEG_TEMPLATE_REALIZE` (the breadth-before-
depth seed-walk gate in `code/archetypes.py::_instantiate_template`).

Builds N archetype armies per target faction using the SAME per-build
random-number-generator seeding `scripts.evaluate_vs_meta` uses for slot A
(`rng=random.Random(seed)`, `points_budget=2000`), and reports two things:

  1. A byte-identical-off fingerprint: for every seed, the sorted list of
     (unit_name, squad_count, model_count) triples the build produced. Two
     runs of this script (before and after a code change) with the gate OFF
     must print an IDENTICAL fingerprint — that is the both-off validation
     the eval protocol requires before any screen.

  2. Per-faction template realization: for every entry in the faction's
     effective template (`archetypes._effective_template`), the number of
     builds (of N) that field >= 1 copy, and the mean squad count across
     all N builds — the number the `SWEG_TEMPLATE_REALIZE` gate is meant to
     move toward "every entry >= 1 in >= 95% of builds".

No evaluation sweep, no simulated battles — archetype-build sampling only.
Safe to run repeatedly; writes nothing outside `data/`.

Run:
  PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts._trz_census \
      --factions "Astra Militarum" "Emperor's Children" "Genestealer Cults" \
      --n 20 --fingerprint-out data/_trz_fp_off_pre.json
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys

from code.archetypes import ARCHETYPES, _effective_template
from code.units import UNIT_CATALOG

BUDGET = 2000.0


def _squad_map(army):
    """Group army.units into squads by squad_id, mirroring _compaudit's logic."""
    sq_map = collections.defaultdict(list)
    for u in army.units:
        sid = getattr(u, "squad_id", None)
        key = (sid, u.profile.name) if sid is not None else (id(u), u.profile.name)
        sq_map[key].append(u)
    per_name = collections.defaultdict(lambda: [0, 0])  # name -> [squads, models]
    for (_sid, pname), members in sq_map.items():
        per_name[pname][0] += 1
        per_name[pname][1] += len(members)
    return per_name


def census_faction(faction: str, n: int):
    from code.army_builder import build_faction_random_army

    archetype_names = list(ARCHETYPES.get(faction, {}).keys())
    if len(archetype_names) != 1:
        print(
            f"WARNING: {faction!r} has {len(archetype_names)} archetype "
            f"entries ({archetype_names}) — census assumes exactly one so "
            f"rng.choice never introduces cross-run archetype variance.",
            file=sys.stderr,
        )
    raw_template = ARCHETYPES[faction][archetype_names[0]]
    effective = _effective_template(faction, raw_template)

    fingerprints = []
    squad_totals = collections.Counter()   # name -> total squads across all N
    builds_present = collections.Counter()  # name -> builds with >=1 squad

    for s in range(n):
        army = build_faction_random_army(
            "A", faction, BUDGET, rng=random.Random(s), use_archetype=True
        )
        per_name = _squad_map(army)
        fp = sorted(
            (name, sq, mo) for name, (sq, mo) in per_name.items()
        )
        fingerprints.append(fp)
        for name, (sq, _mo) in per_name.items():
            squad_totals[name] += sq
            builds_present[name] += 1

    print("=" * 78)
    print(f"FACTION: {faction}   (N={n} @ {int(BUDGET)}pt, archetype="
          f"{archetype_names[0]!r})")
    print("-" * 78)
    print(f"Effective template ({len(effective)} entries, dict order):")
    for key, count in effective.items():
        prof = UNIT_CATALOG.get(key)
        name = prof.name if prof is not None else f"<MISSING:{key}>"
        present = builds_present.get(name, 0)
        mean_sq = squad_totals.get(name, 0) / n
        flag = "" if present >= (0.95 * n) else "  <-- UNDER 95%"
        print(
            f"    count={count}  present {present:2d}/{n}  "
            f"mean_squads={mean_sq:5.2f}  {name}{flag}"
        )
    return fingerprints


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factions", nargs="+", default=[
        "Astra Militarum", "Emperor's Children", "Genestealer Cults",
    ])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--fingerprint-out", default=None)
    args = ap.parse_args()

    all_fp = {}
    for fac in args.factions:
        all_fp[fac] = census_faction(fac, args.n)
        print()

    if args.fingerprint_out:
        with open(args.fingerprint_out, "w", encoding="utf-8") as f:
            json.dump(all_fp, f, indent=1)
        print(f"Fingerprint written to {args.fingerprint_out}")


if __name__ == "__main__":
    main()
