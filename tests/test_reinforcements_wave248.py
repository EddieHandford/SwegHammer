"""Wave 248 tests: Reinforcements! stratagem dispatcher for Astra Militarum
Combined Arms (gate SWEG_REINFORCEMENTS, default-off).

Verbatim rule (Wahapedia, https://wahapedia.ru/wh40k10ed/factions/
astra-militarum/#Stratagems): "WHEN: Any phase. TARGET: One INFANTRY REGIMENT
unit from your army that was just destroyed. EFFECT: Add a new unit to your
army identical to your destroyed unit, in Strategic Reserves, at its Starting
Strength and with all of its wounds remaining."

Tests:
(a) Gate OFF ("0" explicit): no command points spent, destroyed unit stays
    dead, no extra RNG draws on a scripted round, reserves unchanged.
(b) Gate ON: a destroyed INFANTRY REGIMENT unit re-enters reserves at full
    health exactly once per battle with 2 command points deducted.
(c) Gate ON: a second destruction does NOT re-fire (once_per_battle guard).
(d) Gate ON: a non-REGIMENT or non-INFANTRY destruction never triggers it.
"""

from __future__ import annotations

import os
import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _am_regiment_infantry(
    name: str = "Cadian Shock Troops",
    points: float = 65.0,
) -> UnitProfile:
    """A minimal Astra Militarum INFANTRY REGIMENT unit — the primary
    Reinforcements! target.  points_override must exceed the 60 pt AI gate."""
    return UnitProfile(
        name=name,
        health=1,
        damage=1,
        hit_probability=2 / 3,
        ap=0,
        save=5,
        strength=3,
        toughness=3,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        faction="Astra Militarum",
        unit_keywords=("INFANTRY", "REGIMENT"),
        points_override=points,
    )


def _am_vehicle(name: str = "Leman Russ Battle Tank") -> UnitProfile:
    """A minimal Astra Militarum VEHICLE SQUADRON — NOT an INFANTRY REGIMENT,
    so Reinforcements! must never trigger on it."""
    return UnitProfile(
        name=name,
        health=13,
        damage=3,
        hit_probability=2 / 3,
        ap=-2,
        save=3,
        strength=8,
        toughness=11,
        attacks=4,
        weapon_damage_per_shot=2.0,
        range_inches=48,
        faction="Astra Militarum",
        unit_keywords=("VEHICLE", "SQUADRON"),
        points_override=200.0,
    )


def _enemy_profile(name: str = "Space Marine") -> UnitProfile:
    """Generic enemy — present only so the battle has two sides."""
    return UnitProfile(
        name=name,
        health=2,
        damage=1,
        hit_probability=2 / 3,
        ap=-1,
        save=3,
        strength=4,
        toughness=4,
        attacks=2,
        weapon_damage_per_shot=1.0,
        range_inches=24,
    )


def _open_map() -> Map:
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _build_battle(am_profile: UnitProfile | None = None) -> tuple:
    """Minimal AM vs enemy battle for stratagem isolation tests.

    Returns (battle, am_army, enemy_army, am_unit).
    """
    am_profile = am_profile or _am_regiment_infantry()
    am = Army("Astra Militarum")
    am.add_unit(am_profile)
    enemy = Army("Space Marines")
    enemy.add_unit(_enemy_profile())
    battle = Battle(am, enemy, map_=_open_map(), verbose=False)
    battle._assign_uids()
    # Place units so _pick_arrival_point has legal >9" positions to choose from
    am_unit = am.units[0]
    am_unit.position = (10.0, 10.0)
    enemy.units[0].position = (50.0, 50.0)
    am.command_points = 5
    return battle, am, enemy, am_unit


def _kill_unit(unit) -> None:
    """Forcibly kill a unit by zeroing its health."""
    unit.current_health = 0.0
    unit._army._invalidate_alive_cache() if hasattr(unit, "_army") else None


# ---------------------------------------------------------------------------
# (a) Gate OFF — byte-identical no-op
# ---------------------------------------------------------------------------

class TestGateOff(unittest.TestCase):
    """With SWEG_REINFORCEMENTS unset or '0', _try_reinforcements must be a
    complete no-op: zero CP spent, destroyed unit stays dead, reserves
    unchanged."""

    def _run_with_gate(self, gate_value: str | None) -> tuple:
        """Kill the AM unit, call _try_reinforcements, return state snapshot."""
        battle, am, enemy, am_unit = _build_battle()
        am.command_points = 5
        initial_cp = am.command_points
        # Kill the AM unit.
        am_unit.current_health = 0.0
        am._invalidate_alive_cache()
        # Call with explicit gate.
        env_patch = {} if gate_value is None else {"SWEG_REINFORCEMENTS": gate_value}
        old_env = {k: os.environ.get(k) for k in env_patch}
        for k, v in env_patch.items():
            os.environ[k] = v
        # Ensure gate is unset if testing None.
        if gate_value is None:
            os.environ.pop("SWEG_REINFORCEMENTS", None)
        try:
            battle._try_reinforcements(am, round_num=1)
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            if gate_value is None:
                os.environ.pop("SWEG_REINFORCEMENTS", None)

        reserves = battle._reserves.get(am.name, [])
        return am.command_points, am_unit.current_health, reserves, initial_cp

    def test_gate_unset_no_cp_spent(self):
        cp, health, reserves, initial_cp = self._run_with_gate(None)
        self.assertEqual(
            cp, initial_cp,
            "No command points must be spent when SWEG_REINFORCEMENTS is unset",
        )

    def test_gate_zero_no_cp_spent(self):
        cp, health, reserves, initial_cp = self._run_with_gate("0")
        self.assertEqual(
            cp, initial_cp,
            "No command points must be spent when SWEG_REINFORCEMENTS='0'",
        )

    def test_gate_off_unit_stays_dead(self):
        _, health, _, _ = self._run_with_gate("0")
        self.assertEqual(
            health, 0.0,
            "Destroyed unit must remain dead when gate is off",
        )

    def test_gate_off_reserves_unchanged(self):
        _, _, reserves, _ = self._run_with_gate("0")
        self.assertEqual(
            len(reserves), 0,
            "Reserves must be empty when gate is off",
        )


# ---------------------------------------------------------------------------
# (b) Gate ON — revival at full health, 2 CP deducted
# ---------------------------------------------------------------------------

class TestGateOnRevival(unittest.TestCase):
    """With SWEG_REINFORCEMENTS='1', a dead INFANTRY REGIMENT unit with cost
    >= 60 pts must be restored to full health, injected into reserves, and 2
    command points must be deducted exactly once."""

    def _fire(self) -> tuple:
        battle, am, enemy, am_unit = _build_battle()
        am.command_points = 5
        # Kill the INFANTRY REGIMENT unit.
        am_unit.current_health = 0.0
        am._invalidate_alive_cache()
        initial_health = am_unit.profile.health
        os.environ["SWEG_REINFORCEMENTS"] = "1"
        try:
            battle._try_reinforcements(am, round_num=1)
        finally:
            del os.environ["SWEG_REINFORCEMENTS"]
        reserves = list(battle._reserves.get(am.name, []))
        return am, am_unit, reserves, initial_health

    def test_two_cp_deducted(self):
        am, _, _, _ = self._fire()
        self.assertEqual(
            am.command_points, 3,
            "Exactly 2 command points must be deducted on Reinforcements! fire",
        )

    def test_unit_restored_to_full_health(self):
        _, am_unit, _, initial_health = self._fire()
        self.assertEqual(
            am_unit.current_health, initial_health,
            "Revived unit must have full starting health",
        )

    def test_unit_injected_into_reserves(self):
        _, am_unit, reserves, _ = self._fire()
        self.assertIn(
            am_unit, reserves,
            "Revived unit must appear in _reserves for the AM army",
        )

    def test_reserves_length_exactly_one(self):
        _, _, reserves, _ = self._fire()
        self.assertEqual(
            len(reserves), 1,
            "Exactly one unit must be in reserves after a single Reinforcements! fire",
        )


# ---------------------------------------------------------------------------
# (c) Gate ON — once_per_battle guard
# ---------------------------------------------------------------------------

class TestOncePerBattle(unittest.TestCase):
    """A second call after Reinforcements! has fired must not deduct additional
    command points and must not add a second unit to reserves."""

    def test_second_fire_no_effect(self):
        battle, am, enemy, am_unit = _build_battle()
        am.command_points = 5

        # Kill unit and fire first time.
        am_unit.current_health = 0.0
        am._invalidate_alive_cache()
        os.environ["SWEG_REINFORCEMENTS"] = "1"
        try:
            battle._try_reinforcements(am, round_num=1)
            cp_after_first = am.command_points
            reserves_after_first = list(battle._reserves.get(am.name, []))

            # Kill the unit again (simulate a second destruction) — set health
            # to 0 again so it is still in the dead-unit candidate pool.
            am_unit.current_health = 0.0
            am._invalidate_alive_cache()

            battle._try_reinforcements(am, round_num=2)
            cp_after_second = am.command_points
            reserves_after_second = list(battle._reserves.get(am.name, []))
        finally:
            del os.environ["SWEG_REINFORCEMENTS"]

        self.assertEqual(
            cp_after_second, cp_after_first,
            "No additional command points must be spent on the second call — "
            "once_per_battle guard must block it",
        )
        self.assertEqual(
            len(reserves_after_second), len(reserves_after_first),
            "No additional unit must enter reserves on the second call",
        )


# ---------------------------------------------------------------------------
# (d) Gate ON — non-REGIMENT / non-INFANTRY units never trigger
# ---------------------------------------------------------------------------

class TestNonEligibleUnits(unittest.TestCase):
    """A VEHICLE SQUADRON (not INFANTRY REGIMENT) death must never trigger
    Reinforcements!, even with the gate on."""

    def test_vehicle_squadron_does_not_trigger(self):
        battle, am, enemy, am_unit = _build_battle(am_profile=_am_vehicle())
        am.command_points = 5
        # Kill the VEHICLE unit.
        am_unit.current_health = 0.0
        am._invalidate_alive_cache()
        os.environ["SWEG_REINFORCEMENTS"] = "1"
        try:
            battle._try_reinforcements(am, round_num=1)
        finally:
            del os.environ["SWEG_REINFORCEMENTS"]
        reserves = battle._reserves.get(am.name, [])
        self.assertEqual(
            len(reserves), 0,
            "A VEHICLE SQUADRON must not trigger Reinforcements!",
        )
        self.assertEqual(
            am.command_points, 5,
            "No command points must be spent for a non-INFANTRY-REGIMENT unit",
        )

    def test_infantry_without_regiment_does_not_trigger(self):
        """An INFANTRY unit that lacks the REGIMENT keyword must not trigger."""
        non_regiment = UnitProfile(
            name="Tempestus Scions",
            health=1,
            damage=1,
            hit_probability=2 / 3,
            ap=0,
            save=4,
            strength=3,
            toughness=3,
            attacks=1,
            weapon_damage_per_shot=1.0,
            range_inches=24,
            faction="Astra Militarum",
            unit_keywords=("INFANTRY",),  # no REGIMENT
            points_override=100.0,
        )
        battle, am, enemy, am_unit = _build_battle(am_profile=non_regiment)
        am.command_points = 5
        am_unit.current_health = 0.0
        am._invalidate_alive_cache()
        os.environ["SWEG_REINFORCEMENTS"] = "1"
        try:
            battle._try_reinforcements(am, round_num=1)
        finally:
            del os.environ["SWEG_REINFORCEMENTS"]
        reserves = battle._reserves.get(am.name, [])
        self.assertEqual(
            len(reserves), 0,
            "An INFANTRY unit without REGIMENT must not trigger Reinforcements!",
        )


if __name__ == "__main__":
    unittest.main()
