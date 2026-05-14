"""Tests for the role classifier in code/roles.py."""

from __future__ import annotations

import unittest

from code.roles import baseline_key_for, classify
from code.units import UNIT_CATALOG, UnitProfile


class CatalogueRoleTests(unittest.TestCase):
    """Spot-check that key catalogue units land in their expected roles."""

    def test_intercessor_squad_is_dual(self):
        p = UNIT_CATALOG["space_marines_intercessor_squad"]
        self.assertEqual(classify(p), "DUAL")

    def test_knight_errant_is_heavy(self):
        p = UNIT_CATALOG["imperial_knights_library_knight_errant"]
        self.assertEqual(classify(p), "HEAVY")

    def test_necron_warriors_are_horde(self):
        p = UNIT_CATALOG["necrons_necron_warriors"]
        self.assertEqual(classify(p), "HORDE")


class SyntheticRoleTests(unittest.TestCase):

    def test_pure_melee_profile_is_melee(self):
        # No ranged attacks at all, decent melee output -> MELEE.
        p = UnitProfile(
            name="MeleeSpec", health=2, damage=0, hit_probability=0,
            attacks=0, range_inches=1,
            melee_attacks=4, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=5,
            melee_ap=-1,
        )
        self.assertEqual(classify(p), "MELEE")


class BaselineKeyTests(unittest.TestCase):

    def test_baseline_key_for_heavy_exists_in_catalogue(self):
        key = baseline_key_for("HEAVY")
        self.assertIn(key, UNIT_CATALOG)

    def test_baseline_key_for_unknown_role_falls_back(self):
        key = baseline_key_for("WHATEVER")
        self.assertIn(key, UNIT_CATALOG)


if __name__ == "__main__":
    unittest.main()
