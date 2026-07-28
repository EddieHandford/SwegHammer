"""Sweep every faction's archetype for build anomalies.

The Tyranid template was found to field an army sharing only three entries with
the list it cites (docs/TYRANID_LIST_FIDELITY.md). Citation fidelity cannot be
checked mechanically — that needs reading each source — but three MECHANICAL
symptoms can, across all twenty-two factions at once:

  DECLARED, NEVER BUILT   a template entry that no seed ever fields
  BUILT, NOT DECLARED     a unit the builder adds that the template never names
  OVER FILL CAP           squads per army above the documented declared+1 cap

Any of these means the fielded army is not the declared one, which is the same
class of defect as the Tyranid finding even where the source is fine.

Run: PYTHONHASHSEED=0 python -m scripts._archetype_sweep_all
"""
from __future__ import annotations
import collections
import os
import random

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG
from scripts.evaluate_vs_meta import FACTIONS

SEEDS = [int(s) for s in os.environ.get("AS_SEEDS", "0,1,2,3").split(",")]
PTS = int(os.environ.get("AS_POINTS", "2000"))


def main() -> None:
    ns = len(SEEDS)
    print(f"=== archetype build anomalies, {ns} seeds at {PTS} points ===")
    print()
    totals = collections.Counter()
    for fac in FACTIONS:
        templates = ARCHETYPES.get(fac, {})
        declared = {}
        for entries in templates.values():
            for k, v in entries.items():
                nm = UNIT_CATALOG[k].name if k in UNIT_CATALOG else None
                if nm is None:
                    print(f"  {fac}: template key {k} IS NOT IN THE CATALOGUE")
                    totals["missing catalogue key"] += 1
                    continue
                declared[nm] = max(declared.get(nm, 0), v)

        squads = collections.Counter()
        models = collections.Counter()
        for seed in SEEDS:
            army = build_faction_random_army("A", fac, PTS, rng=random.Random(seed),
                                             use_archetype=True)
            per = collections.defaultdict(set)
            lone = collections.Counter()
            for u in army.units:
                nm = u.profile.name or "?"
                sid = getattr(u, "squad_id", -1)
                models[nm] += 1
                if sid >= 0:
                    per[nm].add(sid)
                else:
                    lone[nm] += 1
            for nm in set(list(per) + list(lone)):
                squads[nm] += len(per[nm]) + lone[nm]

        # A faction with SEVERAL templates picks ONE per army, so an entry
        # belonging to an unpicked template is legitimately absent — flagging it
        # would be an artefact of merging declarations. Only Chaos Daemons has
        # more than one template (five); the other twenty-one have exactly one,
        # so the never-built test is valid for them.
        multi_template = len(templates) > 1
        issues = []
        for nm, dec in declared.items():
            if models[nm] == 0:
                if multi_template:
                    totals["skipped (multi-template faction)"] += 1
                    continue
                issues.append(f"DECLARED({dec}) NEVER BUILT   {nm}")
                totals["declared never built"] += 1
            elif squads[nm] / ns > dec + 1.01:
                issues.append(f"OVER FILL CAP  {squads[nm]/ns:.2f} squads vs "
                              f"declared {dec} (+1 fill)   {nm}")
                totals["over fill cap"] += 1
        for nm in models:
            if nm not in declared:
                issues.append(f"BUILT, NOT DECLARED  {models[nm]/ns:.1f} models/army"
                              f"   {nm}")
                totals["built not declared"] += 1
        if issues:
            print(f"  {fac}:")
            for i in sorted(issues):
                print(f"      {i}")
    print()
    print("  totals:", dict(totals))


if __name__ == "__main__":
    main()
