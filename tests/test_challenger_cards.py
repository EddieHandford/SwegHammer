"""Challenger cards — Chapter Approved 2025-26 trailing-player catch-up draw.

Env-gated SWEG_CHALLENGER_CARDS (default OFF, byte-identical). At the START of a
battle round the side trailing by 6+ victory points draws ONE extra scoring card
for that round and scores it through the SAME achievement machinery the Tactical
deck uses (Battle._score_one_card → Battle._score_board_secondaries). An army that
cannot physically achieve the drawn objective scores 0 from it; the lifetime
challenger contribution per side is capped at ~12 VP.

These tests are fast (no sim run): they drive the two new Battle methods
(_decide_challenger_draw, _score_challenger_card) on a hand-built one-objective
Battle and assert the trigger gap, the trailing-side selection, the reuse of the
existing achievement scorer (a non-achieving army scores 0), the lifetime cap
truncation, and the OFF-path inertness (no draw, no VP, no challenger state, no
RNG consumed).

Cited `simulator.challenger_cards`
(data/rule_citations.d/core_challenger_cards.json).
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Fixtures (same shape as tests/test_command_phase_score.py).
# ---------------------------------------------------------------------------

def _holder(name: str = "Holder", oc: int = 4) -> UnitProfile:
    return UnitProfile(
        name=name, health=4.0, damage=1.0, hit_probability=0.5, ap=0, save=4,
        strength=4, toughness=4, attacks=1, weapon_damage_per_shot=1.0,
        range_inches=12, unit_keywords=("INFANTRY",), oc=oc,
        melee_attacks=1, melee_hit_probability=0.5, melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _battle_one_nml_objective():
    """A Battle with a single objective in No Man's Land (the midboard centre,
    outside both deployment zones). The Secure No Man's Land challenger card the
    draw selects scores only for a side that CONTROLS this marker."""
    # 60x44 board; deployment_width default leaves y=22 (centre) in No Man's Land.
    obj = Objective("Centre", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
    army_a = Army("A"); army_a.add_unit(_holder())
    army_b = Army("B"); army_b.add_unit(_holder())
    battle = Battle(army_a, army_b, map_=Map("T", 60.0, 44.0, objectives=(obj,)))
    battle._assign_uids()
    battle._current_round = 2
    battle._a_vp = 0
    battle._b_vp = 0
    battle._a_secondary_vp = 0
    battle._b_secondary_vp = 0
    battle._a_challenger_vp = 0
    battle._b_challenger_vp = 0
    battle._sticky_owner = {}
    # Round-start objective-control snapshot (consumed by Storm Hostile
    # Objective); recompute after positioning when a test needs it.
    battle._obj_controller_at_round_start = {}
    return battle, obj


def _a_controls(battle, obj):
    """Put A on the centre objective, B far away → A controls the marker."""
    battle.a.units[0].position = (30.0, 22.0)
    battle.b.units[0].position = (5.0, 40.0)
    battle._obj_controller_at_round_start = battle._objective_controllers()


def _nobody_near(battle, obj):
    """Put both armies in corners → neither controls any objective."""
    battle.a.units[0].position = (3.0, 3.0)
    battle.b.units[0].position = (57.0, 41.0)
    battle._obj_controller_at_round_start = battle._objective_controllers()


class _Gate:
    """Context manager: set/clear SWEG_CHALLENGER_CARDS deterministically."""

    def __init__(self, value):
        self.value = value
        self._prev = None

    def __enter__(self):
        self._prev = os.environ.get("SWEG_CHALLENGER_CARDS")
        if self.value is None:
            os.environ.pop("SWEG_CHALLENGER_CARDS", None)
        else:
            os.environ["SWEG_CHALLENGER_CARDS"] = self.value
        return self

    def __exit__(self, *exc):
        if self._prev is None:
            os.environ.pop("SWEG_CHALLENGER_CARDS", None)
        else:
            os.environ["SWEG_CHALLENGER_CARDS"] = self._prev
        return False


# ---------------------------------------------------------------------------
# Trigger gap: 6+ fires, 5 does not.
# ---------------------------------------------------------------------------

class TriggerGapTests(unittest.TestCase):
    def test_triggers_at_gap_6(self):
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            # B leads by 6 → A is trailing by 6 → A draws.
            battle._a_vp = 0
            battle._b_vp = 6
            battle._decide_challenger_draw(round_num=2)
            self.assertIsNotNone(battle._challenger_card_this_round)
            side, card = battle._challenger_card_this_round
            self.assertEqual(side, "a")   # the TRAILING side, not the leader

    def test_does_not_trigger_at_gap_5(self):
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            battle._a_vp = 0
            battle._b_vp = 5   # gap of 5 — below the 6 threshold
            battle._decide_challenger_draw(round_num=2)
            self.assertIsNone(battle._challenger_card_this_round)

    def test_trailing_side_is_the_one_behind_not_the_leader(self):
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            # A leads by 9 → B is trailing → B draws (never the leader A).
            battle._a_vp = 12
            battle._b_vp = 3
            battle._decide_challenger_draw(round_num=2)
            self.assertIsNotNone(battle._challenger_card_this_round)
            side, _card = battle._challenger_card_this_round
            self.assertEqual(side, "b")

    def test_no_draw_in_round_1(self):
        # Challenger scoring opens in round 2 (no meaningful round-1 gap).
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            battle._a_vp = 0
            battle._b_vp = 20
            battle._decide_challenger_draw(round_num=1)
            self.assertIsNone(battle._challenger_card_this_round)


# ---------------------------------------------------------------------------
# Reuse-machinery proof: a non-achieving army scores 0; an achieving one scores.
# ---------------------------------------------------------------------------

class ReuseMachineryTests(unittest.TestCase):
    def test_army_that_cannot_achieve_card_scores_zero(self):
        """The draw goes through _score_one_card → the existing board scorer.
        Force the drawn card to a take-and-hold card the trailing army cannot
        complete (it controls no objective) and assert it banks 0 — proof the
        VP comes from the achievement machinery, NOT a flat injection."""
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            battle._a_vp = 0
            battle._b_vp = 10   # A trails by 10 → A draws.
            _nobody_near(battle, obj)   # A controls NOTHING.
            # Force a deterministic, position-dependent take-and-hold card so the
            # "cannot achieve" path is exercised regardless of the crc draw.
            battle._challenger_card_this_round = ("a", "secure_no_mans_land")
            a_before = battle._a_vp
            battle._score_challenger_card(round_num=2)
            # A controls no No Man's Land objective → the board scorer returns 0.
            self.assertEqual(battle._a_vp, a_before)
            self.assertEqual(battle._a_challenger_vp, 0)

    def test_army_that_achieves_card_scores_through_existing_scorer(self):
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            battle._a_vp = 0
            battle._b_vp = 10   # A trails → A draws.
            _a_controls(battle, obj)   # A controls the No Man's Land centre.
            battle._challenger_card_this_round = ("a", "secure_no_mans_land")
            # Cross-check against the existing scorer directly: the challenger
            # award must equal exactly what _score_one_card yields (reuse, not
            # a parallel formula).
            expected = battle._score_one_card(
                "secure_no_mans_land", battle.a, battle.b,
                own_is_army_a=True, round_num=2)
            self.assertGreater(expected, 0)   # one NML objective → 2 VP
            a_before = battle._a_vp
            battle._score_challenger_card(round_num=2)
            self.assertEqual(battle._a_vp - a_before, expected)
            self.assertEqual(battle._a_challenger_vp, expected)


# ---------------------------------------------------------------------------
# Lifetime cap truncates further awards.
# ---------------------------------------------------------------------------

class LifetimeCapTests(unittest.TestCase):
    def test_cap_truncates_award(self):
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            _a_controls(battle, obj)
            cap = Battle._CHALLENGER_LIFETIME_CAP
            # A already one VP short of the lifetime cap.
            battle._a_challenger_vp = cap - 1
            battle._a_vp = battle._a_challenger_vp   # keep totals consistent
            battle._b_vp = battle._a_vp + 10         # A still trails by 10
            battle._challenger_card_this_round = ("a", "secure_no_mans_land")
            battle._score_challenger_card(round_num=2)
            # The 2-VP achievement is truncated to the 1 VP of headroom.
            self.assertEqual(battle._a_challenger_vp, cap)

    def test_no_award_once_cap_reached(self):
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            _a_controls(battle, obj)
            cap = Battle._CHALLENGER_LIFETIME_CAP
            battle._a_challenger_vp = cap   # already maxed
            battle._a_vp = cap
            battle._b_vp = cap + 10
            # The round-start draw should not even draw a card for a maxed side.
            battle._decide_challenger_draw(round_num=2)
            self.assertIsNone(battle._challenger_card_this_round)
            # And scoring a forced card adds nothing past the cap.
            a_before = battle._a_vp
            battle._challenger_card_this_round = ("a", "secure_no_mans_land")
            battle._score_challenger_card(round_num=2)
            self.assertEqual(battle._a_vp, a_before)
            self.assertEqual(battle._a_challenger_vp, cap)


# ---------------------------------------------------------------------------
# OFF path: no challenger scoring, no state mutation, no RNG consumed.
# ---------------------------------------------------------------------------

class OffPathTests(unittest.TestCase):
    def test_off_gate_unset_no_draw_no_score(self):
        # Gate UNSET → fully inert even with a huge gap.
        with _Gate(None):
            battle, obj = _battle_one_nml_objective()
            _a_controls(battle, obj)
            battle._a_vp = 0
            battle._b_vp = 30
            a0, b0 = battle._a_vp, battle._b_vp
            battle._decide_challenger_draw(round_num=2)
            self.assertIsNone(battle._challenger_card_this_round)
            battle._score_challenger_card(round_num=2)
            self.assertEqual((battle._a_vp, battle._b_vp), (a0, b0))
            self.assertEqual(battle._a_challenger_vp, 0)
            self.assertEqual(battle._b_challenger_vp, 0)

    def test_off_gate_zero_no_draw_no_score(self):
        # Gate explicitly "0" → identical inert behaviour.
        with _Gate("0"):
            battle, obj = _battle_one_nml_objective()
            _a_controls(battle, obj)
            battle._a_vp = 0
            battle._b_vp = 30
            battle._decide_challenger_draw(round_num=2)
            self.assertIsNone(battle._challenger_card_this_round)
            battle._score_challenger_card(round_num=2)
            self.assertEqual(battle._a_vp, 0)
            self.assertEqual(battle._a_challenger_vp, 0)

    def test_off_path_consumes_no_rng(self):
        # The OFF draw + score must touch neither the global random stream
        # (byte-identical downstream combat) nor any challenger state.
        with _Gate(None):
            battle, obj = _battle_one_nml_objective()
            _a_controls(battle, obj)
            battle._a_vp = 0
            battle._b_vp = 30
            state_before = random.getstate()
            battle._decide_challenger_draw(round_num=2)
            battle._score_challenger_card(round_num=2)
            self.assertEqual(random.getstate(), state_before)

    def test_on_draw_consumes_no_global_rng(self):
        # Even ON, the deterministic crc draw must not touch the global RNG
        # stream (so the ON path's downstream combat RNG is unperturbed).
        with _Gate("1"):
            battle, obj = _battle_one_nml_objective()
            _a_controls(battle, obj)
            battle._a_vp = 0
            battle._b_vp = 30
            state_before = random.getstate()
            battle._decide_challenger_draw(round_num=2)
            battle._score_challenger_card(round_num=2)
            self.assertEqual(random.getstate(), state_before)


if __name__ == "__main__":
    unittest.main()
