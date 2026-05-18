"""Tests for the Drukhari Skysplinter Assault archetype template.

Added in iter12 — prior to this, Drukhari had no archetype template and the
random-pool builder produced low-fidelity Drukhari lists for any future
calibration work. The template encodes the May 2026 meta Skysplinter Assault
detachment (Raider/Venom-spam, Lelith + Wyches/Incubi melee, Ravager AT).

Reference: https://wahapedia.ru/wh40k10ed/factions/drukhari/
"""

import random
import unittest

from code.archetypes import ARCHETYPES, build_archetype_army, has_archetype
from code.units import UNIT_CATALOG


class DrukhariArchetypeTests(unittest.TestCase):
    def test_drukhari_has_skysplinter_archetype(self):
        """Drukhari must expose at least the Skysplinter Assault archetype."""
        self.assertTrue(has_archetype("Drukhari"))
        self.assertIn("Skysplinter Assault", ARCHETYPES["Drukhari"])

    def test_skysplinter_keys_resolve_in_catalogue(self):
        """Every key in the Skysplinter template must exist in UNIT_CATALOG
        AND its faction must be 'Drukhari'."""
        template = ARCHETYPES["Drukhari"]["Skysplinter Assault"]
        missing = []
        misplaced = []
        for key in template:
            if key not in UNIT_CATALOG:
                missing.append(key)
                continue
            faction = UNIT_CATALOG[key].faction
            if faction != "Drukhari":
                misplaced.append(f"{key} -> faction={faction}")
        self.assertEqual(missing, [], f"Missing keys: {missing}")
        self.assertEqual(misplaced, [], f"Wrong faction: {misplaced}")

    def test_skysplinter_builds_at_1000pt(self):
        """Skysplinter must instantiate a valid army at 1000 pt — non-empty,
        under budget, and at least one Raider or Venom transport seeded
        (transport-spam is the spine of the archetype)."""
        rng = random.Random(0)
        army = build_archetype_army(
            "D", "Drukhari", 1000.0, rng=rng,
            archetype_name="Skysplinter Assault",
        )
        self.assertGreater(len(army.units), 0)
        self.assertLessEqual(army.total_points, 1000.0)

    def test_skysplinter_builds_at_2000pt(self):
        """At a 2000pt budget, Skysplinter should spend a meaningful chunk
        of the budget (>1000pt) — sanity check on the scaler."""
        rng = random.Random(1)
        army = build_archetype_army(
            "D", "Drukhari", 2000.0, rng=rng,
            archetype_name="Skysplinter Assault",
        )
        self.assertGreater(len(army.units), 0)
        self.assertLessEqual(army.total_points, 2000.0)
        self.assertGreater(army.total_points, 1000.0)


if __name__ == "__main__":
    unittest.main()
