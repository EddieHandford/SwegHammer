"""Tests for the weapon-keyword parser and range-dependent keyword effects."""

from __future__ import annotations

import random
import unittest

from code.bsdata.mapper import parse_weapon_keywords
from code.units import Unit, UnitProfile


class ParseWeaponKeywordsTests(unittest.TestCase):

    def test_rapid_fire(self):
        out = parse_weapon_keywords("Rapid Fire 2")
        self.assertEqual(out.get("rapid_fire"), 2)

    def test_melta(self):
        out = parse_weapon_keywords("Melta 4")
        self.assertEqual(out.get("melta"), 4)

    def test_ignores_cover(self):
        out = parse_weapon_keywords("Ignores Cover")
        self.assertTrue(out.get("ignores_cover"))

    def test_anti_uppercase(self):
        out = parse_weapon_keywords("Anti-INFANTRY 4+")
        self.assertEqual(out.get("anti_keywords"), {"INFANTRY": 4})

    def test_anti_case_forgiving(self):
        # Lowercase variant must yield the same normalized result.
        out = parse_weapon_keywords("anti-infantry 4+")
        self.assertEqual(out.get("anti_keywords"), {"INFANTRY": 4})

    def test_heavy(self):
        self.assertTrue(parse_weapon_keywords("Heavy").get("heavy"))

    def test_assault(self):
        self.assertTrue(parse_weapon_keywords("Assault").get("assault"))

    def test_torrent(self):
        self.assertTrue(parse_weapon_keywords("Torrent").get("torrent"))

    def test_hazardous(self):
        self.assertTrue(parse_weapon_keywords("Hazardous").get("hazardous"))

    def test_blast(self):
        self.assertTrue(parse_weapon_keywords("Blast").get("blast"))

    def test_lance(self):
        self.assertTrue(parse_weapon_keywords("Lance").get("lance"))

    def test_precision(self):
        self.assertTrue(parse_weapon_keywords("Precision").get("precision"))

    def test_pistol(self):
        self.assertTrue(parse_weapon_keywords("Pistol").get("pistol"))

    def test_indirect_fire(self):
        self.assertTrue(parse_weapon_keywords("Indirect Fire").get("indirect_fire"))

    def test_one_shot_with_and_without_hyphen(self):
        # Wahapedia variously prints "One Shot" and "One-Shot"; both must parse.
        self.assertTrue(parse_weapon_keywords("One Shot").get("one_shot"))
        self.assertTrue(parse_weapon_keywords("One-Shot").get("one_shot"))

    def test_combo(self):
        # A mix of keywords on a single line must all parse out.
        out = parse_weapon_keywords("Rapid Fire 1, Anti-VEHICLE 2+, Heavy")
        self.assertEqual(out.get("rapid_fire"), 1)
        self.assertEqual(out.get("anti_keywords"), {"VEHICLE": 2})
        self.assertTrue(out.get("heavy"))


class RapidFireBehaviourTests(unittest.TestCase):
    """A synthetic UnitProfile at half range should fire MORE attacks."""

    def _attacker(self):
        # Rapid Fire 2 = +2 attacks at half range. Base attacks=1 -> 3 at half.
        return UnitProfile(
            name="RFGun", health=1, damage=0,
            hit_probability=1.0, attacks=1, weapon_damage_per_shot=1.0,
            strength=10,                # auto-wound vs T4 (5/6)
            rapid_fire=2, range_inches=24,
        )

    def _target(self):
        # No save -> every successful wound becomes damage. Hi HP so we don't
        # run out of HP before all shots resolve.
        return UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
        )

    def test_rapid_fire_more_attacks_at_half_range(self):
        # Use a deterministic seed and many "shooters" to average the dice.
        n_trials = 200
        attacker_p = self._attacker()
        target_p = self._target()

        random.seed(7)
        half_range_total = 0.0
        for _ in range(n_trials):
            target = Unit(target_p)
            half_range_total += Unit(attacker_p).attack(target, distance=6.0)

        random.seed(7)
        full_range_total = 0.0
        for _ in range(n_trials):
            target = Unit(target_p)
            full_range_total += Unit(attacker_p).attack(target, distance=18.0)

        # At half range with RF2 we resolve 3 attacks each; at full range, 1.
        # Expected: half-range damage > full-range damage by a clear margin.
        self.assertGreater(half_range_total, full_range_total * 1.5)


if __name__ == "__main__":
    unittest.main()
