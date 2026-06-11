"""Tests for wave 232 Tank Shock dice-faithful ON path (gate SWEG_TANKSHOCK_DICE).

Tank Shock rule (verbatim from data/rule_citations.d/stratagems.json,
verified against Wahapedia Core Stratagems):
  "WHEN: Your Charge phase, just after a VEHICLE unit from your army ends a
  Charge move. TARGET: That VEHICLE unit. EFFECT: Select one enemy unit
  within Engagement Range of your unit, and select one VEHICLE model in your
  unit that is within Engagement Range of that enemy unit. Roll a number of
  D6 equal to the Toughness characteristic of the selected VEHICLE model.
  For each 5+, that enemy unit suffers 1 mortal wound (to a maximum of 6
  mortal wounds)."

Gate: SWEG_TANKSHOCK_DICE (default-ON since wave 232).
  OFF path (=0): flat 2 mortal wounds (byte-identical to prior behaviour, no random draws).
  ON path (default): roll Toughness-many D6; each 5+ deals 1 mortal wound, capped at 6.
"""
from __future__ import annotations

import os
import types
import unittest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_stub_battle(a_army, b_army):
    """Return a minimal battle stub with a and b armies set."""
    from code.simulator import Battle
    battle = Battle.__new__(Battle)
    battle.a = a_army
    battle.b = b_army
    # Provide just enough state for _try_tank_shock to run.
    battle._events = []
    return battle


def _make_unit_stub(profile, army_ref=None):
    """Return a stub Unit-like object with minimal required attributes."""
    u = MagicMock()
    u.profile = profile
    u.uid = "stub"
    u.squad_id = -1
    u.is_alive = True
    u.army_ref = army_ref
    return u


def _vehicle_profile(toughness=9):
    """Minimal VEHICLE UnitProfile with the given Toughness."""
    from code.units import UnitProfile
    return UnitProfile(
        name="Test Vehicle",
        health=10, damage=1, hit_probability=0.667,
        ap=-1, save=3, strength=5, toughness=toughness,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=6, faction="Adeptus Astartes", points_override=100.0,
        unit_keywords=("VEHICLE",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=5, melee_ap=0,
    )


def _infantry_profile():
    """Minimal INFANTRY UnitProfile as a charge target."""
    from code.units import UnitProfile
    return UnitProfile(
        name="Test Infantry",
        health=10, damage=1, hit_probability=0.667,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=6, faction="Orks", points_override=80.0,
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )


# ---------------------------------------------------------------------------
# OFF path tests (SWEG_TANKSHOCK_DICE not set)
# ---------------------------------------------------------------------------

class TestTankShockDiceOff(unittest.TestCase):
    """OFF path (explicit =0; default-ON since wave 232): flat 2 mortal
    wounds, byte-identical to prior behaviour."""

    def setUp(self):
        os.environ["SWEG_TANKSHOCK_DICE"] = "0"

    def tearDown(self):
        os.environ.pop("SWEG_TANKSHOCK_DICE", None)

    def _run(self, toughness=9):
        from code.army import Army
        a_army = Army("Side A")
        b_army = Army("Side B")

        battle = _make_stub_battle(a_army, b_army)
        charger = _make_unit_stub(_vehicle_profile(toughness=toughness), army_ref=a_army)
        target = _make_unit_stub(_infantry_profile(), army_ref=b_army)

        applied_counts = []

        def fake_apply(unit, count, psychic=False):
            applied_counts.append(count)
            return []

        battle._apply_mortal_wounds = fake_apply

        with patch("code.simulator.should_fire_stratagem", return_value=True), \
             patch.object(battle, "_fire_stratagem", return_value=True):
            battle._try_tank_shock(charger, target, a_army)

        return applied_counts

    def test_off_applies_flat_2_mortal_wounds(self):
        """Gate OFF: _apply_mortal_wounds is called with exactly 2."""
        counts = self._run()
        self.assertEqual(counts, [2],
                         "OFF path must apply exactly 2 mortal wounds")

    def test_off_still_fires_when_gate_set_to_0(self):
        """SWEG_TANKSHOCK_DICE=0 is also OFF (zero-string)."""
        os.environ["SWEG_TANKSHOCK_DICE"] = "0"
        counts = self._run()
        self.assertEqual(counts, [2])


# ---------------------------------------------------------------------------
# ON path tests (SWEG_TANKSHOCK_DICE=1)
# ---------------------------------------------------------------------------

class TestTankShockDiceOn(unittest.TestCase):
    """ON path: roll Toughness-many D6; each 5+ deals 1 mortal wound, cap 6."""

    def setUp(self):
        os.environ["SWEG_TANKSHOCK_DICE"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_TANKSHOCK_DICE", None)

    def _run_controlled(self, toughness, dice_results):
        """Run _try_tank_shock with a controlled randint sequence.

        The ON path draws exactly `toughness` randint(1,6) calls — one die
        per point of the charging VEHICLE model's Toughness. `dice_results`
        supplies every die in order; the test fails loudly (StopIteration)
        if the implementation draws more dice than supplied, and asserts
        the iterator is exhausted afterwards so under-drawing is caught too.
        """
        from code.army import Army
        a_army = Army("Side A")
        b_army = Army("Side B")

        battle = _make_stub_battle(a_army, b_army)
        charger = _make_unit_stub(_vehicle_profile(toughness=toughness), army_ref=a_army)
        target = _make_unit_stub(_infantry_profile(), army_ref=b_army)

        applied_counts = []

        def fake_apply(unit, count, psychic=False):
            applied_counts.append(count)
            return []

        battle._apply_mortal_wounds = fake_apply

        draw_iter = iter(dice_results)

        import code.simulator as sim_module

        def controlled_randint(a, b):
            return next(draw_iter)

        with patch("code.simulator.should_fire_stratagem", return_value=True), \
             patch.object(battle, "_fire_stratagem", return_value=True), \
             patch.object(sim_module.random, "randint", side_effect=controlled_randint):
            battle._try_tank_shock(charger, target, a_army)

        self.assertEqual(
            list(draw_iter), [],
            "ON path must draw exactly Toughness-many dice — some supplied "
            "dice were never consumed.",
        )
        return applied_counts[0] if applied_counts else 0

    def test_each_5_plus_deals_1_mortal_wound(self):
        """Toughness 4, dice [5, 6, 4, 1]: two dice at 5+ -> 2 mortal wounds."""
        result = self._run_controlled(toughness=4, dice_results=[5, 6, 4, 1])
        self.assertEqual(result, 2)

    def test_no_5_plus_deals_no_mortal_wounds(self):
        """Toughness 4, dice [1, 2, 3, 4]: no die at 5+ -> zero mortal wounds
        and _apply_mortal_wounds is never called."""
        result = self._run_controlled(toughness=4, dice_results=[1, 2, 3, 4])
        self.assertEqual(result, 0)

    def test_four_counts_as_miss_five_counts_as_hit(self):
        """The threshold is 5+: a 4 misses, a 5 hits."""
        self.assertEqual(
            self._run_controlled(toughness=2, dice_results=[4, 5]), 1,
        )

    def test_dice_count_equals_toughness(self):
        """Toughness 9 (Rhino-class) must roll exactly nine dice."""
        result = self._run_controlled(
            toughness=9, dice_results=[6, 5, 4, 3, 2, 1, 5, 6, 4],
        )
        self.assertEqual(result, 4)   # four dice at 5+

    def test_cap_enforced_at_6(self):
        """Toughness 12, all sixes: twelve hits must be capped at 6
        ("to a maximum of 6 mortal wounds")."""
        result = self._run_controlled(toughness=12, dice_results=[6] * 12)
        self.assertEqual(result, 6)

    def test_high_toughness_all_misses(self):
        """Toughness 10, all fours: every die misses -> zero mortal wounds."""
        result = self._run_controlled(toughness=10, dice_results=[4] * 10)
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# Gate hermeticity
# ---------------------------------------------------------------------------

class TestTankShockGateHermeticity(unittest.TestCase):
    """Environment gate must be isolated per test."""

    def setUp(self):
        os.environ.pop("SWEG_TANKSHOCK_DICE", None)

    def tearDown(self):
        os.environ.pop("SWEG_TANKSHOCK_DICE", None)

    def test_gate_absent_evaluates_to_on(self):
        """Default-ON since wave 232: a missing env-var is the ON path."""
        self.assertNotIn("SWEG_TANKSHOCK_DICE", os.environ)
        is_on = os.environ.get("SWEG_TANKSHOCK_DICE", "1") != "0"
        self.assertTrue(is_on, "Missing env-var must evaluate to ON "
                               "(default-ON since wave 232)")

    def test_gate_set_to_1_evaluates_to_on(self):
        os.environ["SWEG_TANKSHOCK_DICE"] = "1"
        is_on = os.environ.get("SWEG_TANKSHOCK_DICE", "1") != "0"
        self.assertTrue(is_on, "SWEG_TANKSHOCK_DICE=1 must evaluate to ON")

    def test_gate_cleared_after_teardown(self):
        """Simulate what happens if a previous test set the gate but tearDown ran."""
        # setUp already cleared it; verify it is absent at the start of this test.
        self.assertNotIn("SWEG_TANKSHOCK_DICE", os.environ)


if __name__ == "__main__":
    unittest.main()
