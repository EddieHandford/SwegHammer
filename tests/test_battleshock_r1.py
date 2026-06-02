"""Tests for 10e Battle-shock firing from Round 1 (iter-13 fix #5).

10e core (Wahapedia /the-rules/core-rules/#Command-Phase): the
Battle-shock test fires at the start of EVERY Command phase, including
Round 1. The simulator previously gated on `round_num <= 1` and
silently skipped the R1 test, so wounded R1 units never had their OC
denied even when Below Half-Strength.

These tests pin:
  1. A unit Below Half-Strength at R1 is actually tested (and can fail
     given a low Ld + high 2D6 roll).
  2. A failed R1 unit lands in `_battleshocked_this_round` so the
     downstream stratagem-target picker and OC-contribution gate both
     see it as Battle-shocked in R1, identical to R2+.

Cited as `simulator.battleshock`.
"""

from __future__ import annotations

import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


def _fragile_profile(leadership: int = 7) -> UnitProfile:
    """5-wound chassis we can pre-wound to Below Half-Strength for the
    R1 Battle-shock test. Ld defaults to 7 so a worst-case 2D6 roll
    fails the test cleanly."""
    return UnitProfile(
        name="Coward", health=5, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=leadership,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        move=6.0,
    )


def _open_map() -> Map:
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _make_army(name: str, profile: UnitProfile, positions: list) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


class BattleshockRoundOneTests(unittest.TestCase):
    """The R1 path must mirror the R2+ behaviour exactly."""

    def test_below_half_strength_unit_is_tested_in_round_one(self):
        """A wounded R1 unit triggers a 2D6 Battle-shock roll.

        We patch `random.randint` to return 1s (2D6 = 2) so any Ld >= 3
        unit fails the test, then assert the unit ends up in
        `_battleshocked_this_round`. If the R1 gate were still active
        the set would stay empty no matter what dice we forced.
        """
        a = _make_army("A", _fragile_profile(leadership=7), [(20.0, 30.0)])
        b = _make_army("B", _fragile_profile(leadership=7), [(40.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())

        # Wound the A-side unit to Below Half-Strength (2.0 / 5.0).
        attacker = a.units[0]
        attacker.current_health = 2.0
        self.assertLess(
            attacker.current_health, attacker.profile.health / 2.0,
            "Pre-condition: unit must be Below Half-Strength.",
        )

        # Force 2D6 = 2 (worst possible roll) so Ld 7 fails (2 < 7).
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)

        self.assertIn(
            attacker.uid, battle._battleshocked_this_round,
            "Round-1 Battle-shock test must fire and mark a failed "
            "wounded unit as Battle-shocked. The pre-fix simulator "
            "gated this phase on round_num >= 2, leaving the set empty "
            "and wounded R1 units immune to OC denial.",
        )

    def test_full_strength_unit_is_not_tested_in_round_one(self):
        """Full-strength unit is NOT eligible for the test even in R1.

        Confirms we only removed the round gate, not the half-strength
        gate. A healthy R1 unit must not appear in
        `_battleshocked_this_round` regardless of the dice.
        """
        a = _make_army("A", _fragile_profile(leadership=7), [(20.0, 30.0)])
        b = _make_army("B", _fragile_profile(leadership=7), [(40.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())

        # Force the worst possible roll — should still be a no-op
        # because the half-strength gate filters the unit out before
        # any dice get rolled.
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)

        self.assertEqual(
            battle._battleshocked_this_round, set(),
            "Full-strength units must NOT be Battle-shock-tested in R1.",
        )

    def test_failed_r1_unit_is_strat_excluded_both_sides(self):
        """Downstream gates already key off `_battleshocked_this_round`;
        the fix just feeds the R1 cohort in. Verify both stratagem-
        target pickers (friendly defensive + enemy offensive) see the
        failed unit as filtered out, identical to R2+ behaviour.
        """
        a = _make_army(
            "A", _fragile_profile(leadership=7), [(30.0, 30.0)],
        )
        b = _make_army(
            "B", _fragile_profile(leadership=7), [(40.0, 30.0)],
        )
        battle = Battle(a, b, map_=_open_map())

        # This unit sits ON the centre objective, so the wave-126 Insane Bravery
        # auto-pass (`_squad_on_objective`) could otherwise rescue it. This test
        # is about the stratagem-exclusion of a FAILED unit, not Insane Bravery,
        # so deny the CP to keep the unit on the failing path (the auto-pass is
        # exercised in tests/test_insane_bravery.py).
        a.command_points = 0

        attacker = a.units[0]
        attacker.current_health = 2.0

        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)
        self.assertIn(attacker.uid, battle._battleshocked_this_round)

        # Stratagem-target pickers both filter out
        # `_battleshocked_this_round`. Sample both to confirm A's
        # only unit is invisible to its own defensive strat AND to
        # B's offensive strat — 10e core: "you cannot use Stratagems
        # to affect that unit."
        friendly_pick = battle._most_vulnerable_unit(a)
        enemy_pick = battle._highest_threat_enemy(opponent=a)
        self.assertIsNone(
            friendly_pick,
            "A's only unit is Battle-shocked in R1; A-side defensive "
            "stratagem picker must skip it.",
        )
        self.assertIsNone(
            enemy_pick,
            "A's only unit is Battle-shocked in R1; B-side offensive "
            "stratagem picker (target = an A unit) must skip it.",
        )


if __name__ == "__main__":  # pragma: no cover - convenience runner
    unittest.main()
