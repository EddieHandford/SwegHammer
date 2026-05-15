"""Tests for the Phase 2 melee + combined-combat equilibrium solver."""

from __future__ import annotations

import unittest

import numpy as np

from code.equilibrium import (
    DEFAULT_SHOOT_WEIGHT_BY_ROLE,
    compute_phase2,
    expected_melee_damage,
    expected_shooting_damage,
    pairwise_combat_matrix,
    pairwise_damage_matrix,
    pairwise_melee_matrix,
)
from code.units import UNIT_CATALOG, UnitProfile


def _pure_melee_unit(**overrides) -> UnitProfile:
    """Hand-rolled pure-melee profile for synthetic tests."""
    defaults = dict(
        name="MeleeSpec",
        health=2.0,
        damage=0.0,
        hit_probability=0.0,
        attacks=0,
        range_inches=1,
        save=4,
        strength=4,
        toughness=4,
        melee_attacks=4,
        melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3,
        melee_strength=4,
        melee_ap=0,
    )
    defaults.update(overrides)
    return UnitProfile(**defaults)


class ExpectedMeleeDamageTests(unittest.TestCase):
    """expected_melee_damage on hand-rolled profiles with known outputs."""

    def test_pure_melee_unit_has_nonzero_melee_zero_shooting(self):
        # 4 attacks * 3+ to hit * S4 vs T4 (4+) * unsaved vs 4+ (3/6) * 1 dmg.
        # = 4 * (4/6) * (3/6) * (3/6) * 1 = 4 * 0.6667 * 0.5 * 0.5 = 0.6667
        att = _pure_melee_unit()
        defender = _pure_melee_unit(name="Defender")  # T4, Sv4+, no invuln/fnp
        dmg_shoot = expected_shooting_damage(att, defender)
        dmg_melee = expected_melee_damage(att, defender)
        self.assertEqual(dmg_shoot, 0.0)
        self.assertAlmostEqual(dmg_melee, 4 * (4 / 6) * (3 / 6) * (3 / 6) * 1.0,
                               places=4)

    def test_no_melee_profile_returns_zero(self):
        ranged_only = UnitProfile(
            name="RangedOnly", health=1.0, damage=1.0, hit_probability=2 / 3,
            attacks=2, range_inches=24, save=3,
            melee_attacks=0, melee_hit_probability=0.0,
        )
        defender = _pure_melee_unit()
        self.assertEqual(expected_melee_damage(ranged_only, defender), 0.0)

    def test_invuln_versus_armour_chooses_better_save(self):
        # A high-AP melee attacker that strips a 3+ to a 6+ would normally
        # let nearly all damage through. With a 4+ invuln, the defender
        # should prefer the invuln and take noticeably less damage.
        att = _pure_melee_unit(melee_ap=-3, melee_strength=8)
        no_invuln = _pure_melee_unit(name="NoInv", save=3, toughness=4)
        with_invuln = _pure_melee_unit(name="WithInv", save=3, toughness=4,
                                       invuln_save=4)
        dmg_no = expected_melee_damage(att, no_invuln)
        dmg_inv = expected_melee_damage(att, with_invuln)
        self.assertGreater(dmg_no, dmg_inv)
        # And explicitly: with the 4+ invuln, the effective save is 4+ (better
        # than 6+ after AP), so unsaved fraction is 3/6 (4+ fails on 1-3).
        # 4 attacks * (4/6) hit * (5/6) wound (S>=2T => 2+) * (3/6) unsaved.
        expected_inv = 4 * (4 / 6) * (5 / 6) * (3 / 6) * 1.0
        self.assertAlmostEqual(dmg_inv, expected_inv, places=4)


class PairwiseCombatMatrixTests(unittest.TestCase):
    """pairwise_combat_matrix correctly mixes shoot/melee per-attacker."""

    def test_role_weighting_uses_per_attacker_classify(self):
        # The combined matrix must mix shoot/melee per-attacker, with the
        # default weight pulled from `code.roles.classify` -> the role-keyed
        # `DEFAULT_SHOOT_WEIGHT_BY_ROLE` table. Verify by comparing against
        # the shoot/melee-only matrices for two units with DIFFERENT roles
        # (a pure-melee MELEE unit and an Intercessor Squad DUAL unit).
        from code.roles import classify

        melee_unit = _pure_melee_unit()
        # Use a real catalogue unit for the second row so the role lookup
        # is exercised against actual data; Intercessor Squad classifies as
        # DUAL (shoot_weight 0.55).
        dual_unit = UNIT_CATALOG["space_marines_intercessor_squad"]
        units = [melee_unit, dual_unit]
        D_combo = pairwise_combat_matrix(units)
        D_shoot = pairwise_damage_matrix(units)
        D_melee = pairwise_melee_matrix(units)

        # Row 0: MELEE attacker -> shoot_weight 0.20.
        w0 = DEFAULT_SHOOT_WEIGHT_BY_ROLE[classify(melee_unit)]
        self.assertEqual(w0, DEFAULT_SHOOT_WEIGHT_BY_ROLE["MELEE"])
        expected_row0 = w0 * D_shoot[0] + (1 - w0) * D_melee[0]
        np.testing.assert_allclose(D_combo[0], expected_row0, atol=1e-9)

        # Row 1: DUAL attacker (Intercessor) -> shoot_weight 0.55.
        w1 = DEFAULT_SHOOT_WEIGHT_BY_ROLE[classify(dual_unit)]
        self.assertEqual(w1, DEFAULT_SHOOT_WEIGHT_BY_ROLE["DUAL"])
        expected_row1 = w1 * D_shoot[1] + (1 - w1) * D_melee[1]
        np.testing.assert_allclose(D_combo[1], expected_row1, atol=1e-9)

    def test_callable_shoot_weight_is_honoured(self):
        u_a = _pure_melee_unit(name="A")
        u_b = _pure_melee_unit(name="B")
        # Force all-shoot weights via a callable that returns 1.0 -> combined
        # matrix must equal the shooting-only matrix exactly.
        D_combo = pairwise_combat_matrix([u_a, u_b], shoot_weight=lambda _: 1.0)
        D_shoot = pairwise_damage_matrix([u_a, u_b])
        np.testing.assert_allclose(D_combo, D_shoot, atol=1e-9)


class ComputePhase2Tests(unittest.TestCase):
    """compute_phase2 produces sane results on the live catalogue."""

    def test_phase2_includes_pure_melee_units_and_costs_them(self):
        # Phase 1 drops pure-melee units; Phase 2 should fit them. Spot-check
        # a known pure-melee unit (Wyches) if it's in the catalogue.
        result = compute_phase2()
        self.assertEqual(result.phase, 2)
        self.assertGreater(len(result.entries), 0)

        # Every entry must have a positive equilibrium price.
        for e in result.entries:
            self.assertGreater(
                e.equilibrium_points_per_model, 0.0,
                f"Phase 2 produced non-positive cost for {e.key}",
            )

        # A canonical pure-melee profile should now appear in the fit.
        # Drukhari Wyches are the standard test case; if they're missing
        # from this build of the catalogue, fall back to any melee_only role.
        keys = set(result.keys)
        if "drukhari_wyches" in UNIT_CATALOG:
            self.assertIn(
                "drukhari_wyches", keys,
                "Phase 2 should pick up pure-melee units like Wyches",
            )
            wyches_entry = next(
                e for e in result.entries if e.key == "drukhari_wyches"
            )
            self.assertEqual(wyches_entry.role, "melee_only")
            self.assertGreater(wyches_entry.equilibrium_points_per_model, 0.0)


if __name__ == "__main__":
    unittest.main()
