"""Tests for CP reservation by predicted-pivotal-turn (#160).

Top players RESERVE CP for known-pivotal rounds — Counter-Offensive on T2-T3
opponent alpha strike, +1-to-wound stratagems on offensive burst rounds,
Heroic Intervention reactively whenever a heavy enemy charges. The strategy
layer adds a deferral check on top of the existing trigger heuristic in
`should_fire_stratagem`:

  * If `current_round < pivotal_turn` AND `cost > 0` AND CP not abundant:
    hold (return False).
  * If `current_round >= pivotal_turn`, `cost == 0`, abundant CP, or T5:
    fire (subject to the existing trigger logic).

Reactive stratagems (Counter-Offensive, Heroic Intervention, Tank Shock,
Spirit Stones) are exempt — they have no predictable pivotal turn and must
fire whenever the trigger event happens.

Note: the original suite covered METHODICAL_DESTRUCTION and PLAGUE_WEAPONS
as offensive-deferral exemplars. Both stratagems were removed per the
2026-05-15 fabrication audit (commit fa9a957). The deferral plumbing is
unchanged; the tests below substitute COMMAND_RE_ROLL — also a T2 pivotal
stratagem under `_predict_pivotal_turn` — to keep the same coverage.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.stratagems import (
    COMMAND_RE_ROLL, COUNTER_OFFENSIVE, HEROIC_INTERVENTION,
)
from code.strategy import (
    _predict_pivotal_turn, should_fire_stratagem,
)
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeBattle:
    """Minimal stand-in for code.simulator.Battle exposing `_current_round`.

    `should_fire_stratagem` reads the round via `army._battle_ref._current_round`;
    we don't need a real Battle, only a holder with that attribute.
    """
    def __init__(self, current_round: int):
        self._current_round = current_round


def _attach_round(army: Army, round_num: int) -> None:
    army._battle_ref = _FakeBattle(round_num)


def _heavy_profile() -> UnitProfile:
    return UnitProfile(
        name="Knight",
        health=22, damage=6, hit_probability=2 / 3,
        ap=-3, save=2, strength=10, toughness=12,
        attacks=4, weapon_damage_per_shot=1.5,
        range_inches=48,
        unit_keywords=("VEHICLE", "TITANIC"),
    )


def _character_profile() -> UnitProfile:
    return UnitProfile(
        name="Captain",
        health=4, damage=1, hit_probability=2 / 3,
        ap=-2, save=3, strength=4, toughness=4,
        attacks=4, weapon_damage_per_shot=1.0,
        melee_attacks=5, melee_damage_per_shot=2.0,
        melee_hit_probability=5 / 6, melee_strength=8,
        melee_ap=-2,
        range_inches=12,
        unit_keywords=("CHARACTER", "INFANTRY"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class PredictPivotalTurnTests(unittest.TestCase):

    def test_counter_offensive_is_reactive(self):
        # Reactive stratagems return 0 — no preferred turn.
        self.assertEqual(_predict_pivotal_turn(COUNTER_OFFENSIVE), 0)

    def test_heroic_intervention_is_reactive(self):
        self.assertEqual(_predict_pivotal_turn(HEROIC_INTERVENTION), 0)

    def test_command_reroll_pivots_at_T2(self):
        # Universal — pivots at the alpha-strike window.
        self.assertEqual(_predict_pivotal_turn(COMMAND_RE_ROLL), 2)


class CounterOffensiveReactivityTests(unittest.TestCase):
    """Counter-Offensive is reactive — it must fire whenever the trigger
    event happens regardless of the current round."""

    def _make_ctx(self):
        # Trigger ctx for Counter-Offensive: opponent just killed a model in
        # the fight phase AND we have a friendly unit in engagement to
        # retaliate.
        return {"friendly_in_engagement": True, "enemy_killed_model": True}

    def test_counter_offensive_fires_at_T1(self):
        army = Army("Test")
        army.command_points = 4    # cost is 2 — well-funded
        _attach_round(army, 1)
        self.assertTrue(
            should_fire_stratagem(army, COUNTER_OFFENSIVE, self._make_ctx()),
            "Counter-Offensive must fire reactively at T1, not be held",
        )

    def test_counter_offensive_fires_at_T2_T3(self):
        for rnd in (2, 3):
            army = Army("Test")
            army.command_points = 4
            _attach_round(army, rnd)
            self.assertTrue(
                should_fire_stratagem(army, COUNTER_OFFENSIVE, self._make_ctx()),
                f"Counter-Offensive should fire at T{rnd}",
            )

    def test_heroic_intervention_always_reactive(self):
        # T1 charge incoming — Heroic Intervention must fire regardless.
        army = Army("Test")
        army.command_points = 3
        _attach_round(army, 1)
        character = Unit(_character_profile())
        character.uid = "C0"
        charger = Unit(_heavy_profile())
        charger.uid = "X0"
        ctx = {"character": character, "charge_target": charger, "distance": 4.0}
        self.assertTrue(
            should_fire_stratagem(army, HEROIC_INTERVENTION, ctx),
            "Heroic Intervention must fire reactively at T1 regardless of turn",
        )


class OffensiveStratagemDeferralTests(unittest.TestCase):
    """Offensive stratagems (T2 pivotal) defer at T1 when CP is scarce,
    then fire once we reach the pivotal turn.

    Exemplar swapped from METHODICAL_DESTRUCTION (deleted, fabricated) to
    COMMAND_RE_ROLL — also T2 pivotal under `_predict_pivotal_turn`.
    """

    def _make_cr_ctx(self):
        """ctx for Command Re-Roll: HEAVY target so the heuristic green-lights."""
        target = Unit(_heavy_profile())
        target.uid = "T0"
        return {"target": target, "roll_kind": "wound"}

    def test_command_reroll_holds_at_T1_with_scarce_cp(self):
        army = Army("Test")
        # Just enough CP to afford — but not abundant (cp <= 2 * cost = 2).
        army.command_points = 1
        _attach_round(army, 1)
        self.assertFalse(
            should_fire_stratagem(army, COMMAND_RE_ROLL, self._make_cr_ctx()),
            "Should HOLD CP at T1 with only 1 CP — pivotal is T2",
        )

    def test_command_reroll_fires_at_T2(self):
        army = Army("Test")
        army.command_points = 1
        _attach_round(army, 2)
        self.assertTrue(
            should_fire_stratagem(army, COMMAND_RE_ROLL, self._make_cr_ctx()),
            "Should FIRE at the pivotal turn (T2)",
        )

    def test_abundant_cp_overrides_deferral(self):
        # remaining CP > 2 * cost (cost is 1, so CP > 2) — fire even at T1.
        army = Army("Test")
        army.command_points = 5
        _attach_round(army, 1)
        self.assertTrue(
            should_fire_stratagem(army, COMMAND_RE_ROLL, self._make_cr_ctx()),
            "Abundant CP (5 > 2*1) should override the T1 deferral",
        )


class CommandRerollT5EscapeHatchTests(unittest.TestCase):
    """At T5 (final round), if CP would otherwise go to waste, fire — don't
    leave it on the table."""

    def test_command_reroll_T5_fires_to_avoid_waste(self):
        army = Army("Test")
        army.command_points = 1
        _attach_round(army, 5)
        target = Unit(_heavy_profile())
        target.uid = "T0"
        ctx = {"target": target, "roll_kind": "wound"}
        self.assertTrue(
            should_fire_stratagem(army, COMMAND_RE_ROLL, ctx),
            "Command Re-Roll at T5 must fire — pivotal escape hatch",
        )


class LowCpHoldsForPivotalTests(unittest.TestCase):
    """Low CP + competing eligibles: only the pivotal-aligned one fires."""

    def test_low_cp_holds_for_pivotal_turn(self):
        # At T1 with 1 CP, an offensive stratagem (T2 pivotal) should
        # defer. A reactive Counter-Offensive ctx at the same time would
        # fire (but we'd need 2 CP for that — so just check the deferral
        # half: offensive holds at T1, fires at T2 with the same CP).
        army = Army("Test")
        army.command_points = 1
        _attach_round(army, 1)
        target = Unit(_heavy_profile())
        target.uid = "T0"
        cr_ctx = {"target": target, "roll_kind": "wound"}
        # T1 with scarce CP — hold.
        self.assertFalse(
            should_fire_stratagem(army, COMMAND_RE_ROLL, cr_ctx),
            "Should hold the only CP at T1 for the pivotal turn",
        )
        # Advance to T2 (pivotal) — same CP, now we fire.
        _attach_round(army, 2)
        self.assertTrue(
            should_fire_stratagem(army, COMMAND_RE_ROLL, cr_ctx),
            "Should release the held CP at the pivotal turn",
        )


if __name__ == "__main__":
    unittest.main()
