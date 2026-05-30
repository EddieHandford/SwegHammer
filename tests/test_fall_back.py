"""Tests for the Fall Back move and Desperate Escape test (10e core rules).

A unit within Engagement Range of one or more enemy units may, in its
Movement phase, Fall Back: move up to M" away (through enemy models). It
cannot shoot or charge that turn unless it has the FLY keyword.

After a Fall Back that passed through enemy models, roll 1D6 per model in
the unit; each result of 1-2 destroys one model. SwegHammer is one Unit
per model, so a single d6 roll is taken and on a 1-2 the unit's health is
zeroed. TITANIC and FLY units are entirely exempt from the test.

Cited as `simulator.fall_back` / `simulator.desperate_escape`.
"""

from __future__ import annotations

import random
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.strategy import pick_move_intent
from code.units import Unit, UnitProfile


def _shooty_profile(fly: bool = False, titanic: bool = False) -> UnitProfile:
    """A high-DPA ranged profile that classify() will tag SHOOTY."""
    kw: tuple = ("INFANTRY",)
    if fly:
        kw = kw + ("FLY",)
    if titanic:
        kw = kw + ("TITANIC",)
    return UnitProfile(
        name="Gunner", health=4, damage=4, hit_probability=2 / 3,
        ap=-1, save=3, attacks=4, weapon_damage_per_shot=1.0,
        strength=4, toughness=4, range_inches=24,
        melee_attacks=0, move=6.0,
        unit_keywords=kw,
    )


def _melee_profile() -> UnitProfile:
    return UnitProfile(
        name="Brawler", health=2, damage=0, hit_probability=0,
        attacks=0, range_inches=1,
        melee_attacks=4, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5,
        move=6.0,
        unit_keywords=("INFANTRY",),
    )


def _make_army(name: str, profile: UnitProfile, positions: list) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


def _open_map() -> Map:
    """60x60 board with one objective in the centre so strategy has data."""
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


class FallBackStrategyTests(unittest.TestCase):
    """Strategy layer: SHOOTY unit pinned in melee asks to Fall Back."""

    def test_unit_in_engagement_falls_back(self):
        # SHOOTY unit at (20, 30) with a melee enemy 1" away (within 1.5"
        # engagement range). Strategy should return FALL_BACK with a
        # destination outside the enemy's engagement bubble.
        friendly = _make_army("Friend", _shooty_profile(), [(20.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(21.0, 30.0)])
        map_ = _open_map()

        target_pos, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertEqual(intent, "FALL_BACK")
        # Destination must clear the enemy's engagement range.
        dx = target_pos[0] - enemy.units[0].position[0]
        dy = target_pos[1] - enemy.units[0].position[1]
        self.assertGreater((dx * dx + dy * dy) ** 0.5, 1.5)

    def test_unit_not_in_engagement_does_not_fall_back(self):
        # SHOOTY unit far away from any enemy — should pick a normal intent,
        # never FALL_BACK.
        friendly = _make_army("Friend", _shooty_profile(), [(10.0, 30.0)])
        enemy = _make_army("Foe", _melee_profile(), [(50.0, 30.0)])
        map_ = _open_map()

        _, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertNotEqual(intent, "FALL_BACK")


class FallBackSimulatorTests(unittest.TestCase):
    """Simulator-side: Fall Back blocks shoot/charge for non-FLY; FLY exempt."""

    def _build_battle(self, fly: bool) -> tuple[Battle, Unit, Unit]:
        a = _make_army("A", _shooty_profile(fly=fly), [(20.0, 30.0)])
        b = _make_army("B", _melee_profile(), [(21.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        return battle, a.units[0], b.units[0]

    def test_fall_back_blocks_shooting_for_non_fly(self):
        battle, gunner, brawler = self._build_battle(fly=False)
        gunner.fell_back_this_round = True
        starting_hp = brawler.current_health
        # _do_shoot must return immediately without firing a shot.
        battle._do_shoot(gunner, battle.a, battle.b)
        self.assertEqual(brawler.current_health, starting_hp)

    def test_fly_unit_can_shoot_after_fall_back(self):
        battle, gunner, brawler = self._build_battle(fly=True)
        self.assertTrue(gunner.profile.fly)
        gunner.fell_back_this_round = True
        # Move out of engagement so the engagement-range gate isn't what
        # blocks us — we want to test ONLY the Fall Back gate here.
        gunner.position = (5.0, 30.0)
        brawler.position = (10.0, 30.0)
        starting_hp = brawler.current_health
        # Force the attack rolls to land for a deterministic damage tick.
        with mock.patch("random.random", return_value=0.0), \
                mock.patch("random.randint", return_value=6):
            battle._do_shoot(gunner, battle.a, battle.b)
        # A FLY unit must be able to shoot after Falling Back — damage > 0.
        self.assertLess(brawler.current_health, starting_hp)

    def test_fall_back_blocks_charging_for_non_fly(self):
        battle, gunner, brawler = self._build_battle(fly=False)
        # Put them >1.5" apart so the charge gate is the only thing blocking.
        gunner.position = (20.0, 30.0)
        brawler.position = (24.0, 30.0)
        gunner.fell_back_this_round = True
        # The charge attempt must early-return — no _charging_this_round entry.
        battle._do_charge(gunner, battle.a, battle.b)
        self.assertNotIn(gunner.uid, battle._charging_this_round)


class DesperateEscapeTests(unittest.TestCase):
    """Desperate Escape test: 1D6 per model; each result of 1-2 destroys a model.
    TITANIC and FLY units are entirely exempt from the test.
    """

    def _build_engagement(self, fly: bool = False, titanic: bool = False) -> tuple[Battle, Unit, Unit]:
        a = _make_army("A", _shooty_profile(fly=fly, titanic=titanic), [(20.0, 30.0)])
        b = _make_army("B", _melee_profile(), [(21.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        return battle, a.units[0], b.units[0]

    def test_desperate_escape_kills_on_1(self):
        battle, gunner, _ = self._build_engagement()
        starting_hp = gunner.current_health
        self.assertGreater(starting_hp, 0)
        # Force every random.randint call to return 1 — the d6 rolls 1 and
        # the gunner dies. Run a single move activation.
        with mock.patch("random.randint", return_value=1):
            battle._do_move(gunner, battle.a, battle.b)
        self.assertTrue(gunner.fell_back_this_round)
        self.assertFalse(gunner.is_alive)

    def test_desperate_escape_kills_on_2(self):
        """Roll of 2 destroys a model — threshold is 1-2, not just 1."""
        battle, gunner, _ = self._build_engagement()
        starting_hp = gunner.current_health
        self.assertGreater(starting_hp, 0)
        with mock.patch("random.randint", return_value=2):
            battle._do_move(gunner, battle.a, battle.b)
        self.assertTrue(gunner.fell_back_this_round)
        self.assertFalse(gunner.is_alive)

    def test_desperate_escape_safe_on_3_through_6(self):
        """Rolls of 3-6 are safe — model survives the Desperate Escape test."""
        for roll in (3, 4, 5, 6):
            with self.subTest(roll=roll):
                battle, gunner, _ = self._build_engagement()
                starting_hp = gunner.current_health
                with mock.patch("random.randint", return_value=roll):
                    battle._do_move(gunner, battle.a, battle.b)
                self.assertTrue(gunner.fell_back_this_round,
                                f"expected fell_back flag at d6={roll}")
                self.assertEqual(
                    gunner.current_health, starting_hp,
                    f"d6={roll} must not kill the unit",
                )

    def test_titanic_exempt_from_desperate_escape(self):
        """TITANIC units skip the Desperate Escape test entirely, even on a roll of 1."""
        battle, gunner, _ = self._build_engagement(titanic=True)
        self.assertTrue(gunner.profile.titanic)
        starting_hp = gunner.current_health
        # Even the worst possible roll must not harm a TITANIC unit.
        with mock.patch("random.randint", return_value=1):
            battle._do_move(gunner, battle.a, battle.b)
        self.assertTrue(gunner.fell_back_this_round)
        self.assertEqual(
            gunner.current_health, starting_hp,
            "TITANIC unit must not be harmed by Desperate Escape test",
        )

    def test_fly_exempt_from_desperate_escape(self):
        """FLY units skip the Desperate Escape test entirely, even on a roll of 1."""
        battle, gunner, _ = self._build_engagement(fly=True)
        self.assertTrue(gunner.profile.fly)
        starting_hp = gunner.current_health
        # Even the worst possible roll must not harm a FLY unit.
        with mock.patch("random.randint", return_value=1):
            battle._do_move(gunner, battle.a, battle.b)
        self.assertTrue(gunner.fell_back_this_round)
        self.assertEqual(
            gunner.current_health, starting_hp,
            "FLY unit must not be harmed by Desperate Escape test",
        )


if __name__ == "__main__":
    unittest.main()
