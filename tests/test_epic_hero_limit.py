"""Tests for the 10e core EPIC HERO 1-per-army rule.

10e core: "EPIC HERO units can only be taken once per army." Universal across
every codex. Source:
https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Datasheets

This test exercises both the random-pool builder (build_faction_random_army)
and the archetype builder (build_archetype_army) for every faction that owns
at least one EPIC HERO datasheet in the catalogue, and asserts no army ever
contains 2+ copies of the same EPIC HERO profile.
"""

import random
import unittest
from collections import Counter

from code.archetypes import ARCHETYPES, build_archetype_army, has_archetype
from code.army_builder import (
    build_faction_random_army,
    build_random_army,
    is_epic_hero,
)
from code.units import UNIT_CATALOG


def _epic_hero_factions():
    """Return the set of factions that own at least one EPIC HERO datasheet."""
    factions = set()
    for profile in UNIT_CATALOG.values():
        if is_epic_hero(profile) and profile.faction:
            factions.add(profile.faction)
    return sorted(factions)


def _epic_hero_squad_counts(army, size_policy="max"):
    """Return {profile.name: squad_count} for EPIC HERO units in the army.

    `army.units` stores one `Unit` per model. Multi-model EPIC HERO datasheets
    (Silent King 3-model squad, Inquisitor Ostromandeus 2-model squad, Victrix
    Honour Guard 1-6 model squad) legitimately produce N>1 rows for one
    drafted squad. We normalise per-profile by dividing the model count by
    the squad-size the builder would have picked under its `size_policy`:

      * "max" (build_faction_random_army default) → max_models per squad
      * "min" (build_archetype_army seed) → min_models per squad

    Test failures of the 10e EPIC HERO 1-per-army rule manifest as
    squad_count >= 2 for some profile.
    """
    model_counts: Counter = Counter()
    profile_by_name = {}
    for u in army.units:
        if is_epic_hero(u.profile):
            model_counts[u.profile.name] += 1
            profile_by_name[u.profile.name] = u.profile
    squads: Counter = Counter()
    for name, n in model_counts.items():
        p = profile_by_name[name]
        if size_policy == "min":
            squad_size = max(1, p.min_models)
        else:
            squad_size = max(1, p.max_models)
        # Integer-divide and round up, so a partial squad (a duplicate pick
        # that landed under the size policy) still flags as a duplicate.
        squads[name] = (n + squad_size - 1) // squad_size
    return squads


class EpicHeroCatalogueTests(unittest.TestCase):
    """Sanity: confirm the catalogue carries the EPIC HERO keyword end-to-end."""

    def test_catalogue_contains_epic_heroes(self):
        """At least one EPIC HERO unit must exist in the catalogue. If this
        assertion fails the mapper isn't capturing the categoryLink — the
        rest of this suite would silently pass against an empty set."""
        epics = [k for k, u in UNIT_CATALOG.items() if is_epic_hero(u)]
        self.assertGreater(
            len(epics), 0,
            "No EPIC HERO units in UNIT_CATALOG — mapper not extracting the "
            "categoryLink? Check code.bsdata.mapper._TRACKED_UNIT_KEYWORDS."
        )

    def test_epic_hero_factions_are_non_empty(self):
        """Multiple factions should have at least one EPIC HERO datasheet."""
        factions = _epic_hero_factions()
        self.assertGreater(len(factions), 5, f"Got: {factions}")


class FactionRandomArmyEpicHeroTests(unittest.TestCase):
    """30 random armies per EPIC-HERO-owning faction; assert every army has
    at most one of each EPIC HERO."""

    TRIALS = 30
    POINTS = 2000.0

    def test_random_fill_caps_epic_heroes_at_one(self):
        violations = []
        for faction in _epic_hero_factions():
            for trial in range(self.TRIALS):
                rng = random.Random((hash(faction) ^ trial) & 0xFFFFFFFF)
                army = build_faction_random_army(
                    name=f"{faction}-trial-{trial}",
                    faction=faction,
                    points_budget=self.POINTS,
                    rng=rng,
                )
                counts = _epic_hero_squad_counts(army)
                for hero_name, n in counts.items():
                    if n > 1:
                        violations.append(
                            f"{faction} trial {trial}: {hero_name} x{n}"
                        )
        self.assertEqual(
            violations, [],
            f"EPIC HERO duplicate(s) found in random armies: {violations[:10]}"
        )


class ArchetypeArmyEpicHeroTests(unittest.TestCase):
    """30 archetype armies per faction with a curated archetype; assert
    template seed + random fill never produces duplicate EPIC HEROES."""

    TRIALS = 30
    POINTS = 2000.0

    def test_archetype_seed_plus_fill_caps_epic_heroes_at_one(self):
        violations = []
        for faction in sorted(ARCHETYPES.keys()):
            if not has_archetype(faction):
                continue
            for trial in range(self.TRIALS):
                rng = random.Random((hash(faction) ^ trial ^ 0xA5A5) & 0xFFFFFFFF)
                army = build_archetype_army(
                    name=f"{faction}-arch-{trial}",
                    faction=faction,
                    points_budget=self.POINTS,
                    rng=rng,
                )
                counts = _epic_hero_squad_counts(army)
                for hero_name, n in counts.items():
                    if n > 1:
                        violations.append(
                            f"{faction} arch trial {trial}: {hero_name} x{n}"
                        )
        self.assertEqual(
            violations, [],
            f"EPIC HERO duplicate(s) in archetype armies: {violations[:10]}"
        )


class GenericRandomArmyEpicHeroTests(unittest.TestCase):
    """build_random_army (faction-agnostic, draws from full UNIT_CATALOG)
    must also obey the 1-per-army cap."""

    TRIALS = 30
    POINTS = 2000.0

    def test_full_catalogue_random_caps_epic_heroes_at_one(self):
        violations = []
        for trial in range(self.TRIALS):
            rng = random.Random(0xBEEF ^ trial)
            army = build_random_army(
                name=f"global-trial-{trial}",
                points_budget=self.POINTS,
                rng=rng,
            )
            counts = _epic_hero_squad_counts(army)
            for hero_name, n in counts.items():
                if n > 1:
                    violations.append(f"global trial {trial}: {hero_name} x{n}")
        self.assertEqual(
            violations, [],
            f"EPIC HERO duplicate(s) in generic-random armies: {violations[:10]}"
        )


if __name__ == "__main__":
    unittest.main()
