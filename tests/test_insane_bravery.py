"""Tests for the universal Insane Bravery stratagem wiring (wave 126).

10e core (Wahapedia /the-rules/core-stratagems/#Insane-Bravery): 1 Command
Point, in the Battle-shock step, just before a friendly unit takes a
Battle-shock test, that test is automatically passed — at most once per battle.

The simulator wires this in `Battle._run_battleshock_phase`: when a squad would
FAIL (roll < target), the owning army spends 1 CP to auto-pass it, gated on
(a) SWEG_INSANE not disabled, (b) the once-per-battle flag `_insane_bravery_used`,
(c) `command_points >= 1`, and (d) the squad contesting an objective
(`_squad_on_objective` — the case a real player burns it, since Battle-shock
would drop the unit's Objective Control to 0). Cited `simulator.insane_bravery`.

These tests pin the gates: a failing on-objective unit with CP auto-passes; the
save is once per battle; SWEG_INSANE=0 disables it; off-objective or zero-CP
units fail normally.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


def _fragile_profile(leadership: int = 7) -> UnitProfile:
    """5-wound chassis pre-wounded Below Half-Strength; Ld 7 fails a 2D6=2."""
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


class InsaneBraveryTests(unittest.TestCase):
    """The auto-pass gates (objective, once-per-battle, CP, env)."""

    def setUp(self):
        os.environ.pop("SWEG_INSANE", None)   # default ON

    def tearDown(self):
        os.environ.pop("SWEG_INSANE", None)

    def _setup_on_objective(self, cp: int = 3):
        # A-side coward sits ON the centre objective (within 3").
        a = _make_army("A", _fragile_profile(leadership=7), [(30.0, 30.0)])
        b = _make_army("B", _fragile_profile(leadership=7), [(45.0, 30.0)])
        a.command_points = cp
        b.command_points = cp
        battle = Battle(a, b, map_=_open_map())
        a.units[0].current_health = 2.0   # Below Half-Strength
        return battle, a

    def test_on_objective_failing_unit_auto_passes(self):
        battle, a = self._setup_on_objective(cp=3)
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)
        self.assertNotIn(
            a.units[0].uid, battle._battleshocked_this_round,
            "An on-objective unit failing its test with CP available should "
            "auto-pass via Insane Bravery, not be Battle-shocked.",
        )
        self.assertEqual(a.command_points, 2, "Insane Bravery costs 1 CP.")
        self.assertIn(id(a), battle._insane_bravery_used)

    def test_once_per_battle(self):
        battle, a = self._setup_on_objective(cp=3)
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)
        self.assertNotIn(a.units[0].uid, battle._battleshocked_this_round)
        self.assertEqual(a.command_points, 2)
        # Round 2: the (still Below-Half) unit fails again, but the once-per-
        # battle save is spent, so it is now Battle-shocked.
        battle._battleshocked_this_round = set()
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=2)
        self.assertIn(
            a.units[0].uid, battle._battleshocked_this_round,
            "Insane Bravery may be used at most once per battle; the second "
            "failed test must NOT be auto-passed.",
        )
        self.assertEqual(a.command_points, 2, "No second CP spend.")

    def test_disabled_by_env_gate(self):
        os.environ["SWEG_INSANE"] = "0"
        battle, a = self._setup_on_objective(cp=3)
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)
        self.assertIn(
            a.units[0].uid, battle._battleshocked_this_round,
            "SWEG_INSANE=0 disables the auto-pass; the unit is Battle-shocked.",
        )
        self.assertEqual(a.command_points, 3, "No CP spent when disabled.")

    def test_off_objective_unit_is_not_saved(self):
        # A-side coward is in the backfield corner, NOT on the objective.
        a = _make_army("A", _fragile_profile(leadership=7), [(5.0, 5.0)])
        b = _make_army("B", _fragile_profile(leadership=7), [(45.0, 30.0)])
        a.command_points = 3
        b.command_points = 3
        battle = Battle(a, b, map_=_open_map())
        a.units[0].current_health = 2.0
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)
        self.assertIn(
            a.units[0].uid, battle._battleshocked_this_round,
            "An off-objective unit is not worth the once-per-battle save, so "
            "it fails normally (the heuristic gate).",
        )
        self.assertEqual(a.command_points, 3, "No CP spent off-objective.")

    def test_no_cp_no_save(self):
        battle, a = self._setup_on_objective(cp=0)
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._run_battleshock_phase(round_num=1)
        self.assertIn(
            a.units[0].uid, battle._battleshocked_this_round,
            "With 0 CP the army cannot pay for Insane Bravery; the unit fails.",
        )


if __name__ == "__main__":  # pragma: no cover - convenience runner
    unittest.main()
