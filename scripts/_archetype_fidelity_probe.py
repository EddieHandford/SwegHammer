"""Does the army builder field the archetype template it declares?

The Tyranid "Subterranean Assault" template declares:
    hive_tyrant 1, termagants 2, hormagaunts 2, ripper_swarms 1,
    zoanthropes 1, exocrine 1, tyrannofex 1
and its comment block describes "2 squads per type" of chaff, matching a
real-meta minimum-sized-unit shape.

This counts SQUADS (distinct squad_id groups), not models, per datasheet across
several seeds, and flags:
  * declared entries that never get built
  * built entries that are not declared at all
  * chaff squad counts above the documented cap

Run: PYTHONHASHSEED=0 AF_FACTION=Tyranids python -m scripts._archetype_fidelity_probe
"""
from __future__ import annotations
import collections
import os
import random

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG

FAC = os.environ.get("AF_FACTION", "Tyranids")
SEEDS = [int(s) for s in os.environ.get("AF_SEEDS", "0,1,2,3,4,5").split(",")]
PTS = int(os.environ.get("AF_POINTS", "2000"))


def main() -> None:
    templates = ARCHETYPES.get(FAC, {})
    print(f"=== {FAC}: declared templates ===")
    declared_names = {}
    for tname, entries in templates.items():
        print(f"  {tname}:")
        for k, v in entries.items():
            nm = UNIT_CATALOG[k].name if k in UNIT_CATALOG else f"<{k} NOT IN CATALOGUE>"
            declared_names[nm] = v
            print(f"      {v}x  {k:<34} -> {nm}")
    print()

    squads_seen = collections.Counter()
    models_seen = collections.Counter()
    appearances = collections.Counter()
    for seed in SEEDS:
        army = build_faction_random_army("A", FAC, PTS, rng=random.Random(seed),
                                         use_archetype=True)
        per = collections.defaultdict(set)
        mod = collections.Counter()
        lone = collections.Counter()
        for u in army.units:
            nm = u.profile.name or "?"
            sid = getattr(u, "squad_id", -1)
            mod[nm] += 1
            if sid >= 0:
                per[nm].add(sid)
            else:
                lone[nm] += 1
        for nm in set(list(per) + list(lone)):
            n_sq = len(per[nm]) + lone[nm]
            squads_seen[nm] += n_sq
            models_seen[nm] += mod[nm]
            appearances[nm] += 1

    ns = len(SEEDS)
    print(f"=== built armies at {PTS} points, {ns} seeds ===")
    print(f"{'unit':<34}{'declared':>9}{'squads/army':>13}{'models/army':>13}"
          f"{'seeds present':>15}")
    allnames = set(list(models_seen) + list(declared_names))
    for nm in sorted(allnames, key=lambda n: -models_seen[n]):
        dec = declared_names.get(nm, 0)
        flag = ""
        if dec and appearances[nm] == 0:
            flag = "   <-- DECLARED, NEVER BUILT"
        elif not dec and appearances[nm]:
            flag = "   <-- BUILT, NOT DECLARED"
        elif dec and squads_seen[nm] / ns > dec + 1.01:
            flag = f"   <-- squads exceed declared+1 fill cap ({dec}+1)"
        print(f"{nm[:34]:<34}{dec:>9}{squads_seen[nm]/ns:>13.2f}"
              f"{models_seen[nm]/ns:>13.1f}{appearances[nm]:>9}/{ns:<5}{flag}")


if __name__ == "__main__":
    main()
