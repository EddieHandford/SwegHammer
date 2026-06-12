"""
Diagnostic for iter #11 — TSON template-walk Rubric Marines seeding.

Builds 30 Thousand Sons archetype armies at 1000pt and counts how many
include Rubric Marines vs Tzaangors vs Scarab Occult Terminators.

Pre-fix expectation per task: Rubrics ~0/30, Tzaangors ~25/30.
Post-fix expectation: Rubrics ~25/30+.
"""

from __future__ import annotations

import random

from code.archetypes import build_archetype_army


FACTION = "Thousand Sons"
ARCHETYPE = "Cult of Magic"
BUDGET = 1000.0
TRIALS = 30


def main() -> None:
    tracked = {
        "Rubric Marines": 0,
        "Tzaangors": 0,
        "Scarab Occult Terminators": 0,
        "Exalted Sorcerer": 0,
        "Infernal Master": 0,
        "Helbrute": 0,
    }
    for seed in range(TRIALS):
        rng = random.Random(seed)
        army = build_archetype_army(
            name=f"TSON-{seed}",
            faction=FACTION,
            points_budget=BUDGET,
            rng=rng,
            archetype_name=ARCHETYPE,
        )
        names = {u.profile.name for u in army.units}
        for tracked_name in tracked:
            if tracked_name in names:
                tracked[tracked_name] += 1

    print(f"TSON archetype seeding diag — {TRIALS} trials at {BUDGET:.0f}pt")
    print("-" * 60)
    for name, count in tracked.items():
        pct = 100.0 * count / TRIALS
        print(f"  {name:<32}  {count:>3}/{TRIALS}  ({pct:.1f}%)")


if __name__ == "__main__":
    main()
