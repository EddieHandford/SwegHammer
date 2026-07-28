"""How often does each DECLARED template entry actually reach the table?

The Tyranid defect (docs/TYRANID_LIST_FIDELITY.md) was a template that cited one
army and fielded another, worth +9.49 once corrected. Task #38 makes Aeldari the
top target under the rank-correlation headline - the simulator ranks it 6th
strongest while reality ranks it LAST of 22 - and a two-seed dump showed its
Wave Serpent and Dark Reapers missing despite both being declared, the Wave
Serpent at count=2 with the comment "universal in all 6 lists".

Two seeds is not evidence. This builds many seeds and reports, per declared
entry, the share of armies containing it and the mean squad count when present,
alongside what the template asked for. An entry declared at count=2 that appears
in 0 percent of armies is a defect; one that appears in every army at five times
the intended squad count is the same defect pointing the other way.

Run: PYTHONHASHSEED=0 TF_FACTION=Aeldari python -m scripts._template_fill_rate
     TF_SEEDS=24
"""
from __future__ import annotations
import collections
import os
import random

from code.archetypes import ARCHETYPES, _effective_template
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG

FAC = os.environ.get("TF_FACTION", "Aeldari")
N_SEEDS = int(os.environ.get("TF_SEEDS", "24"))


def main() -> None:
    templates = ARCHETYPES.get(FAC)
    if not templates:
        print(f"{FAC}: no archetype")
        return

    # Map catalogue key -> display name so built armies can be matched back to
    # declared entries. Armies carry profile names, templates carry keys.
    declared = {}
    for tname, entries in templates.items():
        eff = _effective_template(FAC, entries)
        for key, count in eff.items():
            prof = UNIT_CATALOG.get(key)
            if prof is None:
                declared[key] = (count, None, None)
                continue
            declared[key] = (count, prof.name,
                             max(1, getattr(prof, "min_models", 1) or 1))

    present = collections.Counter()
    models = collections.Counter()
    extras = collections.Counter()
    name_to_key = {v[1]: k for k, v in declared.items() if v[1]}

    for seed in range(N_SEEDS):
        army = build_faction_random_army("A", FAC, 2000,
                                         rng=random.Random(seed),
                                         use_archetype=True)
        counts = collections.Counter()
        for u in army.units:
            counts[u.profile.name or "?"] += 1
        for nm, c in counts.items():
            key = name_to_key.get(nm)
            if key is None:
                extras[nm] += 1
                continue
            present[key] += 1
            models[key] += c

    print(f"=== {FAC}: declared template entries versus what is fielded "
          f"({N_SEEDS} seeds) ===")
    print(f"{'entry':<40}{'declared':>9}{'appears':>9}{'mean models':>13}"
          f"{'mean squads':>13}")
    rows = sorted(declared.items(), key=lambda kv: -kv[1][0])
    for key, (count, nm, minmod) in rows:
        seen = present[key]
        pct = 100.0 * seen / N_SEEDS
        mm = models[key] / seen if seen else 0.0
        squads = mm / minmod if (seen and minmod) else 0.0
        flag = ""
        if seen == 0:
            flag = "   <-- DECLARED BUT NEVER FIELDED"
        elif squads >= 3.0:
            flag = "   <-- over-fielded"
        label = nm or f"{key} (NOT IN CATALOGUE)"
        print(f"{label[:39]:<40}{count:>9}{pct:>8.0f}%{mm:>13.1f}"
              f"{squads:>13.1f}{flag}")

    if extras:
        print()
        print("  fielded but NOT declared (random fill topping up the budget):")
        for nm, c in extras.most_common():
            print(f"    {nm[:44]:<46} in {100.0 * c / N_SEEDS:>3.0f}% of armies")

    never = [declared[k][1] or k for k, _ in rows if present[k] == 0]
    print()
    print(f"  declared entries never fielded: {len(never)} of {len(rows)}")
    if never:
        print(f"    {', '.join(never)}")


if __name__ == "__main__":
    main()
