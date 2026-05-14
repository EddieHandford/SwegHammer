"""Tests for the core combat math primitives in code/units.py."""

from __future__ import annotations

import random
import unittest

from code.units import (
    Unit,
    UnitProfile,
    _prob_to_target,
    save_probability,
    wound_probability,
)


class WoundProbabilityTests(unittest.TestCase):
    """The 5 standard 40K wound-table edge cases."""

    def test_s_ge_double_t_wounds_on_2_plus(self):
        # S >= 2T -> 2+ -> 5/6
        self.assertAlmostEqual(wound_probability(8, 4), 5 / 6)
        self.assertAlmostEqual(wound_probability(10, 5), 5 / 6)

    def test_s_greater_than_t_wounds_on_3_plus(self):
        # S > T (but not >=2T) -> 3+ -> 4/6
        self.assertAlmostEqual(wound_probability(5, 4), 4 / 6)

    def test_s_equal_t_wounds_on_4_plus(self):
        # S == T -> 4+ -> 3/6
        self.assertAlmostEqual(wound_probability(4, 4), 3 / 6)

    def test_s_less_than_t_wounds_on_5_plus(self):
        # S < T (but 2S > T) -> 5+ -> 2/6
        self.assertAlmostEqual(wound_probability(3, 4), 2 / 6)

    def test_double_s_le_t_wounds_on_6_plus(self):
        # 2S <= T -> 6+ -> 1/6
        self.assertAlmostEqual(wound_probability(2, 4), 1 / 6)
        self.assertAlmostEqual(wound_probability(3, 10), 1 / 6)


class ProbToTargetTests(unittest.TestCase):
    """_prob_to_target should round-trip the standard d6 targets."""

    def test_round_trip(self):
        # 2+..6+ correspond to 5/6, 4/6, 3/6, 2/6, 1/6
        for target in (2, 3, 4, 5, 6):
            prob = (7 - target) / 6
            self.assertEqual(_prob_to_target(prob), target)


class SaveProbabilityTests(unittest.TestCase):
    """save_probability handles AP, cover, and the 2+ cap correctly."""

    def test_basic_save(self):
        # 3+ save, no AP, no cover -> 4/6
        self.assertAlmostEqual(save_probability(3), 4 / 6)

    def test_ap_degrades_save(self):
        # 3+ save with AP-1 becomes 4+ -> 3/6
        self.assertAlmostEqual(save_probability(3, ap=-1), 3 / 6)

    def test_ap_can_negate_save(self):
        # 6+ save with AP-3 becomes 9+ -> saved on impossible roll -> 0
        self.assertEqual(save_probability(6, ap=-3), 0.0)

    def test_cover_improves_save(self):
        # 4+ save in cover -> 3+ -> 4/6
        self.assertAlmostEqual(save_probability(4, ap=0, in_cover=True), 4 / 6)

    def test_cover_caps_at_two_plus(self):
        # 3+ save in cover would be 2+, capped at 2+ -> 5/6
        self.assertAlmostEqual(save_probability(3, ap=0, in_cover=True), 5 / 6)
        # 2+ save in cover stays 2+ (cap) -> 5/6
        self.assertAlmostEqual(save_probability(2, ap=0, in_cover=True), 5 / 6)


class LethalHitsTests(unittest.TestCase):
    """Lethal Hits: only the crit-to-hit (natural 6) skips the wound roll.

    With S=1, T=10 the wound roll is normally 6+ (1/6). With Lethal Hits and
    hit_probability=1.0 (auto-pass to-hit), each shot has probability:
      - 1/6 chance of crit-to-hit -> auto-wound (Lethal)
      - 5/6 chance of non-crit -> wound on 6+ -> 5/6 * 1/6
    Total expected wound rate = 1/6 + 5/36 = 11/36 (vs 6/36 without Lethal).
    """

    def test_lethal_hits_only_crits_skip_wound(self):
        rng_seed = 12345
        attacks = 1200

        # Lethal Hits enabled
        lethal_profile = UnitProfile(
            name="LH", health=1, damage=0, hit_probability=1.0,
            attacks=attacks, weapon_damage_per_shot=1.0,
            strength=1, lethal_hits=True,
        )
        # T10, no save -> only thing in play is wound roll
        target_profile = UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=10, save=7,
        )
        random.seed(rng_seed)
        lethal_dmg = Unit(lethal_profile).attack(Unit(target_profile), distance=12)

        # Same scenario without Lethal Hits
        plain_profile = UnitProfile(
            name="Plain", health=1, damage=0, hit_probability=1.0,
            attacks=attacks, weapon_damage_per_shot=1.0,
            strength=1, lethal_hits=False,
        )
        random.seed(rng_seed)
        plain_dmg = Unit(plain_profile).attack(Unit(target_profile), distance=12)

        # Lethal should yield clearly more wounds than plain.
        self.assertGreater(lethal_dmg, plain_dmg)
        # And the lethal hit rate should be in the ballpark of 11/36 (~0.305).
        rate = lethal_dmg / attacks
        self.assertGreater(rate, 0.20)
        self.assertLess(rate, 0.42)
        # Plain rate should be near 1/6 (~0.167)
        plain_rate = plain_dmg / attacks
        self.assertGreater(plain_rate, 0.08)
        self.assertLess(plain_rate, 0.26)


if __name__ == "__main__":
    unittest.main()
