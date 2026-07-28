"""How far does the FIELDED profile drift from the CATALOGUE entry?

Twice today a probe gave a confidently wrong answer by reading UNIT_CATALOG when
the question was about what the simulator sees at runtime. The gate reads
`attacker.profile`, which is the profile after per-model loadout promotion
(SWEG_PERMODEL, default-on), and that is not always the catalogue entry: the
Emperor's Children Defiler reads 12.00 damage at 12 inches in the catalogue and
12.01 at 48 inches once fielded.

This quantifies the gap so it is known how much to distrust a catalogue read,
rather than guessing. For every unit the archetype builder fields, it compares
the catalogue entry against the fielded profile on the fields probes actually
use, and reports which units differ and by how much.

The answer decides something concrete: several recorded findings rest on
catalogue reads. If drift is rare and small, those findings stand. If it is
common, they need re-checking - in particular the Leagues of Votann unit
profiles used to argue the simulator over-values that faction's chassis.

Run: PYTHONHASHSEED=0 python -m scripts._catalogue_vs_fielded
     CF_VERBOSE=1  list every differing unit
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG
from scripts.evaluate_vs_meta import FACTIONS

VERBOSE = os.environ.get("CF_VERBOSE") == "1"
SEEDS = [int(s) for s in os.environ.get("CF_SEEDS", "0,1,2").split(",")]

# The fields probes in scripts/ actually read off a profile.
FIELDS = ("attacks", "hit_probability", "weapon_damage_per_shot", "strength",
          "ap", "range_inches", "toughness", "health", "save", "points_cost",
          "melee_attacks", "melee_damage_per_shot", "melee_strength")


def _by_name():
    """Catalogue entries keyed by display name, as probes tend to match them."""
    out = {}
    for key, p in UNIT_CATALOG.items():
        out.setdefault(p.name, p)
    return out


def main() -> None:
    cat = _by_name()
    fielded = {}
    for fac in FACTIONS:
        for s in SEEDS:
            try:
                army = build_faction_random_army("A", fac, 2000,
                                                 rng=random.Random(s),
                                                 use_archetype=True)
            except Exception:
                continue
            for u in army.units:
                fielded.setdefault(u.profile.name, u.profile)

    checked = 0
    missing = 0
    diffs = []
    field_counts = collections.Counter()
    for name, fp in sorted(fielded.items()):
        cp = cat.get(name)
        if cp is None:
            missing += 1
            continue
        checked += 1
        changed = []
        for f in FIELDS:
            a = getattr(cp, f, None)
            b = getattr(fp, f, None)
            if a is None and b is None:
                continue
            try:
                same = abs(float(a or 0) - float(b or 0)) < 1e-9
            except (TypeError, ValueError):
                same = a == b
            if not same:
                changed.append((f, a, b))
                field_counts[f] += 1
        if changed:
            diffs.append((name, changed))

    print("=== catalogue entry versus fielded profile ===")
    print(f"    {checked} fielded units matched to a catalogue entry"
          f"{f', {missing} unmatched by name' if missing else ''}\n")
    print(f"  units whose fielded profile DIFFERS: {len(diffs)} of {checked}"
          f"  ({100.0 * len(diffs) / max(checked, 1):.0f}%)\n")

    if field_counts:
        print("  which fields drift, and how often:")
        for f, n in field_counts.most_common():
            print(f"    {f:<28}{n:>5} units")
        print()

    if VERBOSE and diffs:
        print("  --- differing units ---")
        for name, changed in diffs[:50]:
            bits = ", ".join(f"{f} {a}->{b}" for f, a, b in changed[:4])
            print(f"    {name[:34]:<36}{bits}")
        print()

    print("  A probe that reads UNIT_CATALOG is asking what the DATA says. A")
    print("  probe reasoning about simulator behaviour must build armies, since")
    print("  that is what `attacker.profile` resolves to at runtime. Where the")
    print("  two agree the distinction is harmless; the figure above says how")
    print("  often it is not.")


if __name__ == "__main__":
    main()
