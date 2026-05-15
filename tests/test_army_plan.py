"""Tests for the coordinated army-level activation plan (#161 / S3).

The plan picker / activation order / strategy biases work together to make
real coordinated alpha strikes materialise out of the AI's per-activation
picks. These tests exercise each layer independently.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.map import Map, Objective
from code.strategy import pick_army_plan, pick_move_intent
from code.units import UnitProfile


def _dual_profile(name: str = "Dual") -> UnitProfile:
    """DUAL-role profile so neither MELEE nor SHOOTY short-circuits the
    objective-scoring branch in pick_move_intent."""
    return UnitProfile(
        name=name, health=2, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, attacks=2, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
    )


def _make_army(name: str, positions, profile=None) -> Army:
    profile = profile or _dual_profile()
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


def _map(*objectives: Objective) -> Map:
    return Map(name="t", width=60.0, height=60.0, objectives=tuple(objectives))


class PickArmyPlanTests(unittest.TestCase):

    def test_t1_picks_aggressive_plan(self):
        """T1 with full armies should pick LEFT/RIGHT/MID — never HOME_HOLD."""
        army = _make_army("A", [(30.0, 10.0)])
        opp = _make_army("B", [(30.0, 50.0)])
        plan = pick_army_plan(army, opp, round_num=1, map_=_map())
        self.assertIn(plan, ("LEFT_FLANK", "RIGHT_FLANK", "MID_PUSH"))

    def test_t1_picks_left_when_enemy_centre_of_mass_left(self):
        army = _make_army("A", [(30.0, 10.0)])
        # Enemy bulk on the left half (x < 30).
        opp = _make_army("B", [(10.0, 50.0), (12.0, 50.0)])
        plan = pick_army_plan(army, opp, round_num=1, map_=_map())
        self.assertEqual(plan, "LEFT_FLANK")

    def test_t1_picks_right_when_enemy_centre_of_mass_right(self):
        army = _make_army("A", [(30.0, 10.0)])
        opp = _make_army("B", [(50.0, 50.0), (48.0, 50.0)])
        plan = pick_army_plan(army, opp, round_num=1, map_=_map())
        self.assertEqual(plan, "RIGHT_FLANK")

    def test_t5_winning_picks_home_hold(self):
        """T5 with a 10-VP lead -> HOME_HOLD (lock in the win)."""

        army = _make_army("A", [(30.0, 10.0)])
        opp = _make_army("B", [(30.0, 50.0)])

        # Mock battle ref so pick_army_plan can read VP differential.
        class _FakeBattle:
            pass

        battle = _FakeBattle()
        battle.a = army
        battle.b = opp
        battle._a_vp = 30
        battle._b_vp = 20
        army._battle_ref = battle
        opp._battle_ref = battle

        plan = pick_army_plan(army, opp, round_num=5, map_=_map())
        self.assertEqual(plan, "HOME_HOLD")

    def test_t5_losing_picks_counter(self):
        """T5 down by 10 VP -> COUNTER (salvage by killing the biggest brick)."""

        army = _make_army("A", [(30.0, 10.0)])
        opp = _make_army("B", [(30.0, 50.0)])

        class _FakeBattle:
            pass

        battle = _FakeBattle()
        battle.a = army
        battle.b = opp
        battle._a_vp = 10
        battle._b_vp = 25
        army._battle_ref = battle
        opp._battle_ref = battle

        plan = pick_army_plan(army, opp, round_num=5, map_=_map())
        self.assertEqual(plan, "COUNTER")


class PlanBiasesObjectiveScoringTests(unittest.TestCase):

    def test_left_flank_plan_biases_left_objective(self):
        """With LEFT_FLANK plan, a left-side objective beats an identical
        right-side objective the unit would otherwise pick by distance alone.

        Setup: unit sits dead-centre with two equidistant tied (a_oc == b_oc)
        objectives — one on the left half, one on the right half. Without a
        plan the destination is whichever the score comparator picks first
        (ties broken by Python's max stability). With LEFT_FLANK the
        left-side objective's 1.5x multiplier flips the comparison decisively.
        """
        # Tied OC by leaving both objectives uncontested (neither side has
        # any unit within 3").
        left_obj = Objective(name="L", x=15.0, y=30.0, control_radius=3.0)
        right_obj = Objective(name="R", x=45.0, y=30.0, control_radius=3.0)
        map_ = _map(left_obj, right_obj)
        # Unit at centre, equidistant from both objectives.
        friendly = _make_army("F", [(30.0, 30.0)])
        enemy = _make_army("E", [(30.0, 55.0)])  # far away, no contest
        unit = friendly.units[0]

        # Without a plan, with both at exactly 15 inches the destination is
        # determined by max's tie-break. With LEFT_FLANK the left should win.
        target_with_plan, intent = pick_move_intent(
            unit, friendly, enemy, map_, army_plan="LEFT_FLANK",
        )
        # The plan should drive the unit to the left objective's vicinity.
        self.assertEqual(intent, "CAPTURE")
        self.assertLess(
            target_with_plan[0], 30.0,
            f"LEFT_FLANK plan should pick the left objective, got {target_with_plan}",
        )

    def test_right_flank_plan_biases_right_objective(self):
        left_obj = Objective(name="L", x=15.0, y=30.0, control_radius=3.0)
        right_obj = Objective(name="R", x=45.0, y=30.0, control_radius=3.0)
        map_ = _map(left_obj, right_obj)
        friendly = _make_army("F", [(30.0, 30.0)])
        enemy = _make_army("E", [(30.0, 55.0)])
        unit = friendly.units[0]
        target_with_plan, _ = pick_move_intent(
            unit, friendly, enemy, map_, army_plan="RIGHT_FLANK",
        )
        self.assertGreater(
            target_with_plan[0], 30.0,
            f"RIGHT_FLANK plan should pick the right objective, got {target_with_plan}",
        )


class ActivationOrderTests(unittest.TestCase):

    def test_units_activated_first_match_plan(self):
        """With LEFT_FLANK, units on the left half activate before right-side units."""
        # Map width = 60 -> left half is x < 30, right half x >= 30.
        map_ = _map()
        # Mixed positions: alternate left and right.
        army = _make_army("A", [
            (10.0, 10.0),   # left
            (40.0, 10.0),   # right
            (15.0, 25.0),   # left
            (50.0, 25.0),   # right
        ])
        # No plan -> sorted by score only.
        baseline = army.activation_queue(excluded_ids=set(), map_=map_)
        self.assertEqual(len(baseline), 4)
        # With LEFT_FLANK plan -> left-side units (x < 30) come first.
        army.army_plan = "LEFT_FLANK"
        plan_order = army.activation_queue(excluded_ids=set(), map_=map_)
        self.assertEqual(len(plan_order), 4)
        # First two units in queue must both be on the left half.
        self.assertLess(plan_order[0].position[0], 30.0)
        self.assertLess(plan_order[1].position[0], 30.0)
        # Last two units in queue must both be on the right half.
        self.assertGreaterEqual(plan_order[2].position[0], 30.0)
        self.assertGreaterEqual(plan_order[3].position[0], 30.0)

    def test_no_plan_legacy_score_order(self):
        """Without a plan, activation_queue collapses to score-descending."""
        map_ = _map()
        army = _make_army("A", [
            (10.0, 10.0), (40.0, 10.0), (15.0, 25.0), (50.0, 25.0),
        ])
        # army.army_plan is None by default.
        q = army.activation_queue(excluded_ids=set(), map_=map_)
        # All scores equal (same profile), so result is stable order by score.
        scores = [u.profile.score for u in q]
        self.assertEqual(scores, sorted(scores, reverse=True))


class BackwardCompatTests(unittest.TestCase):

    def test_no_plan_default_unchanged(self):
        """pick_move_intent with no army_plan arg matches the no-plan call.

        This is the baseline-preservation contract — pre-#161 callers that
        never supply a plan see the exact same (target_pos, intent) tuple
        whether they pass `army_plan=None` or omit the kwarg.
        """
        obj = Objective(name="O", x=30.0, y=30.0, control_radius=3.0)
        map_ = _map(obj)
        friendly = _make_army("F", [(20.0, 20.0)])
        enemy = _make_army("E", [(40.0, 40.0)])
        unit = friendly.units[0]

        legacy = pick_move_intent(unit, friendly, enemy, map_)
        with_none = pick_move_intent(unit, friendly, enemy, map_, army_plan=None)
        self.assertEqual(legacy, with_none)


if __name__ == "__main__":
    unittest.main()
