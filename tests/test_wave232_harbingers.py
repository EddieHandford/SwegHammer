"""Tests for wave 232: Harbingers of Dread additional Dread abilities
(gated SWEG_HARBINGERS, default-ON since wave 232).

Abilities tested:
  Despair   — stacking Ld -1 aura (cumulative with Deathly Terror), wired in
              code/simulator.py _run_battleshock_phase as despair_penalty.
  Darkness  — -1 to the attacker's Hit roll when the defender is Chaos Knights
              and the attacker is Battle-shocked or more than 18\" away, wired in
              code/units.py Unit.attack as hit_mod_delta -= 1.
  Dismay    — forces Battle-shock tests on multi-model enemy squads that are
              below Starting Strength (even if not yet below Half-Strength)
              within 9\" of a Chaos Knights model, wired in
              code/simulator.py _run_battleshock_phase loop eligibility gate.
  Delirium  — D3 mortal wounds applied to a Below Half-Strength enemy squad
              representative when it fails a Battle-shock test within 9\" of
              a Chaos Knights model, wired in code/simulator.py immediately
              after the battle-shock-failure path.

OFF-path byte-identical contract
---------------------------------
Each test that sets SWEG_HARBINGERS resets it in tearDown. The OFF path must
produce the same numbers as the committed baseline (hermetic hermeticity
requirement from the global smoke suite).
"""

from __future__ import annotations

import os
import random
import unittest
from dataclasses import replace
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _open_map() -> Map:
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _generic_profile(
    name: str = "Target",
    faction: str = "Generic",
    leadership: int = 7,
    health: float = 10.0,
    min_models: int = 1,
) -> UnitProfile:
    return UnitProfile(
        name=name,
        faction=faction,
        health=health,
        damage=1,
        hit_probability=0.5,
        ap=0,
        save=4,
        strength=4,
        toughness=4,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        leadership=leadership,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_damage_per_shot=1.0,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_ap=0,
        move=6.0,
        min_models=min_models,
    )


def _chaos_knights_profile(
    name: str = "Chaos Knight",
    health: float = 20.0,
) -> UnitProfile:
    return UnitProfile(
        name=name,
        faction="Chaos Knights",
        health=health,
        damage=10,
        hit_probability=2 / 3,
        ap=-3,
        save=3,
        strength=14,
        toughness=10,
        attacks=4,
        weapon_damage_per_shot=6.0,
        range_inches=24,
        leadership=6,
        unit_keywords=("VEHICLE", "TITANIC"),
        melee_attacks=4,
        melee_damage_per_shot=6.0,
        melee_hit_probability=2 / 3,
        melee_strength=14,
        melee_ap=-3,
        move=10.0,
        min_models=1,
    )


def _make_battle_from_profiles(
    a_profile: UnitProfile,
    b_profile: UnitProfile,
    a_pos: tuple = (20.0, 30.0),
    b_pos: tuple = (40.0, 30.0),
) -> tuple[Battle, "Unit", "Unit"]:
    """Build a two-unit battle and return (battle, a_unit, b_unit)."""
    a = Army("A")
    b = Army("B")
    a.add_unit(a_profile)
    b.add_unit(b_profile)
    a_unit = a.units[0]
    b_unit = b.units[0]
    a_unit.position = a_pos
    b_unit.position = b_pos
    battle = Battle(a, b, map_=_open_map())
    # Back-link units to their armies and the battle so round-dependent
    # gates work.
    a_unit.army_ref = a
    b_unit.army_ref = b
    a._battle_ref = battle
    b._battle_ref = battle
    return battle, a_unit, b_unit


# ---------------------------------------------------------------------------
# Despair tests
# ---------------------------------------------------------------------------

class DespairTests(unittest.TestCase):
    """Despair stacks Ld -1 with Deathly Terror so the combined penalty
    within 9\" of a Chaos Knights model is -2 (target raised by 2)."""

    def setUp(self) -> None:
        os.environ["SWEG_HARBINGERS"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("SWEG_HARBINGERS", None)

    def test_despair_raises_battle_shock_target_by_two(self) -> None:
        """With SWEG_HARBINGERS=1, a unit within 9\" of a CK model must
        have its Battle-shock target raised by 2 (Deathly Terror +
        Despair = combined Ld -2)."""
        # Enemy (Generic) unit is below half-strength so it will be tested.
        # Chaos Knights model sits 8\" away (within the 9\" aura).
        enemy_profile = _generic_profile(leadership=7, health=10.0)
        ck_profile = _chaos_knights_profile()

        a = Army("CK")
        b = Army("Enemy")
        a.add_unit(ck_profile)
        b.add_unit(enemy_profile)
        a_unit = a.units[0]
        b_unit = b.units[0]
        a_unit.position = (30.0, 30.0)
        b_unit.position = (22.0, 30.0)  # 8" away — within aura

        battle = Battle(a, b, map_=_open_map())
        a._battle_ref = battle
        b._battle_ref = battle

        # Wound the enemy below half.
        b_unit.current_health = 3.0  # 3/10 < 5

        # Capture the roll and target when _run_battleshock_phase runs.
        # With Ld 7, Deathly Terror (+1) and Despair (+1) the target = 9.
        # Force 2D6 = 10 so the test PASSES (10 >= 9) — we can't inspect the
        # computed target variable directly, but we CAN verify that the
        # two-point gap is respected by checking pass/fail with forced dice.
        # 2D6 = 9 (4+5): should PASS target of 9? No, 10e pass = roll >= target.
        # Actually target = Ld + penalties: 7 + 2 = 9. Passes if roll >= 9.
        # Force roll = 8 (below 9) → fail; force roll = 9 → pass.
        with mock.patch("code.simulator.random.randint") as m:
            m.side_effect = [4, 5]  # 2D6 = 9 = target → PASS
            battle._run_battleshock_phase(round_num=1)
        self.assertNotIn(
            b_unit.uid,
            battle._battleshocked_this_round,
            "Roll 9 vs target 9 should PASS (not battle-shocked): "
            "Despair brings target to 7+1+1=9.",
        )

        # Reset and try roll=8 (below 9) → FAIL.
        # The unit is still below half (3/10), so Delirium will also fire
        # after the failure — need to provide the D3 call in side_effect too.
        b_unit.current_health = 3.0
        b_unit.battleshocked_until_round = 0
        battle._battleshocked_this_round = set()
        b.command_points = 0  # no Insane Bravery escape
        with mock.patch("code.simulator.random.randint") as m:
            # 2D6 = 3+5 = 8 < 9 → FAIL; Delirium D3 = 1 (we don't care about
            # the exact wound value, just need the call consumed).
            m.side_effect = [3, 5, 1]
            battle._run_battleshock_phase(round_num=2)
        self.assertIn(
            b_unit.uid,
            battle._battleshocked_this_round,
            "Roll 8 vs target 9 should FAIL: Despair raises target to 9.",
        )

    def test_despair_off_when_gate_disabled(self) -> None:
        """With SWEG_HARBINGERS=0 (explicit OFF; default-ON since wave 232),
        only Deathly Terror (-1) should fire, so target = 7 + 1 = 8; a roll
        of 8 should PASS."""
        os.environ["SWEG_HARBINGERS"] = "0"

        enemy_profile = _generic_profile(leadership=7, health=10.0)
        ck_profile = _chaos_knights_profile()

        a = Army("CK")
        b = Army("Enemy")
        a.add_unit(ck_profile)
        b.add_unit(enemy_profile)
        a_unit = a.units[0]
        b_unit = b.units[0]
        a_unit.position = (30.0, 30.0)
        b_unit.position = (22.0, 30.0)

        battle = Battle(a, b, map_=_open_map())
        b._battle_ref = battle
        b.command_points = 0

        b_unit.current_health = 3.0

        with mock.patch("code.simulator.random.randint") as m:
            m.side_effect = [3, 5]  # 2D6 = 8 = target → PASS (no Despair)
            battle._run_battleshock_phase(round_num=1)
        self.assertNotIn(
            b_unit.uid,
            battle._battleshocked_this_round,
            "With gate OFF, roll 8 vs Ld 7 + Deathly Terror only (target=8) "
            "should PASS — Despair must not fire.",
        )


# ---------------------------------------------------------------------------
# Darkness tests
# ---------------------------------------------------------------------------

class DarknessTests(unittest.TestCase):
    """Darkness: -1 to the attacker's Hit roll when attacking a Chaos
    Knights model and the attacker is Battle-shocked OR more than 18\" away."""

    def setUp(self) -> None:
        os.environ["SWEG_HARBINGERS"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("SWEG_HARBINGERS", None)

    def _avg_damage_vs_ck(
        self,
        attacker_profile: UnitProfile,
        ck_profile: UnitProfile,
        distance: float,
        battle_shocked: bool,
        n: int = 400,
        seed: int = 7,
    ) -> float:
        """Average ranged damage dealt by attacker_profile to ck_profile
        over n trials, with the attacker at `distance` from the target.
        If battle_shocked is True the attacker's battleshocked_until_round
        is set to 1 (the current round used by the battle_ref)."""
        random.seed(seed)
        a = Army("Attacker")
        b = Army("CK")
        a.add_unit(attacker_profile)
        b.add_unit(ck_profile)
        a_unit = a.units[0]
        b_unit = b.units[0]

        # Use a real Battle so the full attack pipeline has all needed hooks
        # (maybe_fire_command_reroll, etc.).
        battle = Battle(a, b, map_=_open_map())
        a._battle_ref = battle
        b._battle_ref = battle
        battle._current_round = 1
        a_unit.army_ref = a
        b_unit.army_ref = b

        if battle_shocked:
            a_unit.battleshocked_until_round = 1

        total = 0.0
        for _ in range(n):
            b_unit.current_health = float(ck_profile.health)
            total += a_unit.attack(b_unit, distance=distance, mode="ranged")
        return total / n

    def test_darkness_reduces_hits_when_shocked_attacker(self) -> None:
        """Attacker that is Battle-shocked must deal less damage vs Chaos
        Knights under SWEG_HARBINGERS=1 (Darkness fires -1 to hit)."""
        attacker = _generic_profile(
            name="Generic Attacker",
            faction="Generic",
            health=10.0,
        )
        ck = _chaos_knights_profile(health=500.0)

        dmg_shocked = self._avg_damage_vs_ck(
            attacker, ck, distance=12.0, battle_shocked=True,
        )
        dmg_normal = self._avg_damage_vs_ck(
            attacker, ck, distance=12.0, battle_shocked=False,
        )
        self.assertLess(
            dmg_shocked,
            dmg_normal,
            f"A Battle-shocked attacker should deal less damage vs Chaos "
            f"Knights (Darkness -1 to hit). Got shocked={dmg_shocked:.3f} "
            f"vs normal={dmg_normal:.3f}.",
        )

    def test_darkness_reduces_hits_when_beyond_18_inches(self) -> None:
        """Attacker at distance > 18\" from a Chaos Knights model must deal
        less damage under SWEG_HARBINGERS=1 (Darkness fires because range
        condition is met even without Battle-shock)."""
        attacker = _generic_profile(
            name="Generic Attacker",
            faction="Generic",
            health=10.0,
        )
        ck = _chaos_knights_profile(health=500.0)

        dmg_far = self._avg_damage_vs_ck(
            attacker, ck, distance=24.0, battle_shocked=False,
        )
        dmg_close = self._avg_damage_vs_ck(
            attacker, ck, distance=12.0, battle_shocked=False,
        )
        self.assertLess(
            dmg_far,
            dmg_close,
            f"Attacker at 24\" should deal less damage vs Chaos Knights "
            f"(Darkness >18\" trigger). Got far={dmg_far:.3f} "
            f"vs close={dmg_close:.3f}.",
        )

    def test_darkness_off_no_penalty_for_non_ck_target(self) -> None:
        """Darkness must NOT apply when the target is not Chaos Knights,
        regardless of the attacker's Battle-shock status."""
        attacker = _generic_profile(
            name="Generic Attacker",
            faction="Generic",
            health=10.0,
        )
        non_ck = _generic_profile(
            name="Non-CK Target",
            faction="Adeptus Astartes",
            health=500.0,
        )

        # With SWEG_HARBINGERS on but the target is not CK, a Battle-shocked
        # attacker should produce the same damage as a normal one.
        dmg_shocked = self._avg_damage_vs_ck(
            attacker, non_ck, distance=12.0, battle_shocked=True,
        )
        dmg_normal = self._avg_damage_vs_ck(
            attacker, non_ck, distance=12.0, battle_shocked=False,
        )
        self.assertAlmostEqual(
            dmg_shocked,
            dmg_normal,
            delta=0.5,
            msg="Darkness must not apply to non-Chaos-Knights targets.",
        )

    def test_darkness_off_when_gate_disabled(self) -> None:
        """With SWEG_HARBINGERS=0 (explicit OFF; default-ON since wave 232),
        a Battle-shocked attacker at 24\" must deal the same expected damage
        as a normal attacker vs a Chaos Knights target (Darkness gate OFF)."""
        os.environ["SWEG_HARBINGERS"] = "0"
        attacker = _generic_profile(
            name="Generic Attacker",
            faction="Generic",
            health=10.0,
        )
        ck = _chaos_knights_profile(health=500.0)

        dmg_shocked = self._avg_damage_vs_ck(
            attacker, ck, distance=24.0, battle_shocked=True,
        )
        dmg_normal = self._avg_damage_vs_ck(
            attacker, ck, distance=24.0, battle_shocked=False,
        )
        self.assertAlmostEqual(
            dmg_shocked,
            dmg_normal,
            delta=0.5,
            msg=(
                "With SWEG_HARBINGERS off, Darkness must not apply: "
                f"shocked={dmg_shocked:.3f} normal={dmg_normal:.3f}."
            ),
        )


# ---------------------------------------------------------------------------
# Dismay tests
# ---------------------------------------------------------------------------

class DismayTests(unittest.TestCase):
    """Dismay forces Battle-shock tests on multi-model squads that are below
    Starting Strength but NOT yet below Half-Strength, when within 9\" of a
    Chaos Knights model (SWEG_HARBINGERS=1)."""

    def setUp(self) -> None:
        os.environ["SWEG_HARBINGERS"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("SWEG_HARBINGERS", None)

    def _run_with_forced_roll(
        self,
        alive_count: int,
        start_count: int,
        ck_position: tuple,
        enemy_position: tuple,
        roll_value: int,
        leadership: int = 7,
    ) -> set:
        """Set up a multi-model squad at `alive_count` out of `start_count`
        start models and a single Chaos Knights model. Run the battleshock
        phase with a forced 2D6 roll and return _battleshocked_this_round."""
        # Build a health total that represents `start_count` models, each
        # with 1 wound.  Set current health to alive_count.
        # The per-model wound count must be integer-clean for the
        # start-count lookup logic.
        total_health = float(start_count)
        enemy_profile = _generic_profile(
            name="Multi-model",
            faction="Generic",
            leadership=leadership,
            health=total_health,
            min_models=start_count,
        )
        ck_profile = _chaos_knights_profile()

        ck_army = Army("CK")
        enemy_army = Army("Enemy")

        # Add `alive_count` individual Unit instances (squad_id=0 for all).
        for _ in range(alive_count):
            enemy_army.add_unit(enemy_profile)
            u = enemy_army.units[-1]
            u.position = enemy_position
            u.squad_id = 0
            u.current_health = 1.0  # 1 wound each

        ck_army.add_unit(ck_profile)
        ck_army.units[0].position = ck_position

        battle = Battle(ck_army, enemy_army, map_=_open_map())
        enemy_army._battle_ref = battle
        ck_army._battle_ref = battle

        # Manually inject the start count so the battleshock loop knows the
        # original squad size.  Key format: (army.name, squad_id).
        battle._squad_start_count[("Enemy", 0)] = start_count

        # No command points so Insane Bravery cannot rescue the squad.
        enemy_army.command_points = 0

        with mock.patch("code.simulator.random.randint") as m:
            m.return_value = roll_value
            battle._run_battleshock_phase(round_num=1)

        return battle._battleshocked_this_round

    def test_dismay_forces_test_on_below_starting_not_below_half(self) -> None:
        """A squad at 4 out of 6 models (below Starting Strength but above
        Half-Strength) must be forced to Battle-shock when within 9\" of a
        CK model under SWEG_HARBINGERS=1."""
        # 4/6 alive: above half (3), below starting (6). Dismay forces test.
        # Leadership 7; forced 2D6 = 2 (lowest possible) → fails.
        bsr = self._run_with_forced_roll(
            alive_count=4,
            start_count=6,
            ck_position=(30.0, 30.0),
            enemy_position=(27.0, 30.0),  # 3" away — inside 9" aura
            roll_value=1,  # 1+1 = 2 < 7 → fail
        )
        self.assertTrue(
            len(bsr) > 0,
            "Dismay must force a Battle-shock test on a squad below "
            "Starting Strength (4/6 alive) within 9\" of a CK model. "
            "The squad should appear in _battleshocked_this_round after "
            "a forced low roll.",
        )

    def test_dismay_does_not_force_test_beyond_9_inches(self) -> None:
        """A squad below Starting Strength that is MORE than 9\" from any
        Chaos Knights model must NOT be forced to test (outside aura range).
        Placed 10\" away, forced minimum roll."""
        bsr = self._run_with_forced_roll(
            alive_count=4,
            start_count=6,
            ck_position=(30.0, 30.0),
            enemy_position=(20.0, 30.0),  # 10" away — outside 9" aura
            roll_value=1,  # would fail if tested
        )
        self.assertEqual(
            bsr,
            set(),
            "Dismay must NOT force a test on a squad outside the 9\" aura.",
        )

    def test_dismay_off_when_gate_disabled(self) -> None:
        """With SWEG_HARBINGERS=0 (explicit OFF; default-ON since wave 232),
        a below-Starting-Strength squad must NOT be forced to test (only the
        below-Half-Strength path fires)."""
        os.environ["SWEG_HARBINGERS"] = "0"
        bsr = self._run_with_forced_roll(
            alive_count=4,
            start_count=6,
            ck_position=(30.0, 30.0),
            enemy_position=(27.0, 30.0),
            roll_value=1,  # would fail if tested
        )
        self.assertEqual(
            bsr,
            set(),
            "With SWEG_HARBINGERS off, Dismay must not force tests on "
            "non-below-Half-Strength squads.",
        )


# ---------------------------------------------------------------------------
# Delirium tests
# ---------------------------------------------------------------------------

class DeliriumTests(unittest.TestCase):
    """Delirium: D3 mortal wounds applied to a Below Half-Strength squad
    representative on a failed Battle-shock test when within 9\" of a Chaos
    Knights model (SWEG_HARBINGERS=1)."""

    def setUp(self) -> None:
        os.environ["SWEG_HARBINGERS"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("SWEG_HARBINGERS", None)

    def test_delirium_deals_mortal_wounds_on_failed_test(self) -> None:
        """A Below Half-Strength unit within 9\" that fails its Battle-shock
        test must suffer at least 1 mortal wound (Delirium fires)."""
        enemy_profile = _generic_profile(
            name="Fragile",
            faction="Generic",
            leadership=7,
            health=10.0,
        )
        ck_profile = _chaos_knights_profile()

        a = Army("CK")
        b = Army("Enemy")
        a.add_unit(ck_profile)
        b.add_unit(enemy_profile)
        a.units[0].position = (30.0, 30.0)
        b.units[0].position = (27.0, 30.0)   # 3" — inside aura

        battle = Battle(a, b, map_=_open_map())
        a._battle_ref = battle
        b._battle_ref = battle
        b.command_points = 0  # no Insane Bravery escape

        b_unit = b.units[0]
        b_unit.current_health = 3.0   # below half (5)

        health_before = b_unit.current_health

        # Force 2D6 = 2 (fail) and Delirium D3 = 3 (max MWs).
        # Side-effect sequence: first two calls are the 2D6 roll (1+1=2 < 7),
        # next call is the Delirium D3 (return 3).
        with mock.patch("code.simulator.random.randint") as m:
            m.side_effect = [1, 1, 3]  # 2D6=2 fails, D3=3 MWs
            battle._run_battleshock_phase(round_num=1)

        self.assertIn(
            b_unit.uid,
            battle._battleshocked_this_round,
            "The unit must have failed the Battle-shock test.",
        )
        self.assertLess(
            b_unit.current_health,
            health_before,
            "Delirium must deal mortal wounds after a failed Battle-shock "
            f"test (health before={health_before:.1f}, after="
            f"{b_unit.current_health:.1f}).",
        )

    def test_delirium_does_not_fire_when_above_half(self) -> None:
        """Delirium must NOT deal mortal wounds when the unit is above Half-
        Strength (even if below Starting Strength and within 9\")."""
        enemy_profile = _generic_profile(
            name="Sturdy",
            faction="Generic",
            leadership=5,   # low Ld so the test fails without cheating
            health=10.0,
        )
        ck_profile = _chaos_knights_profile()

        a = Army("CK")
        b = Army("Enemy")
        a.add_unit(ck_profile)
        b.add_unit(enemy_profile)
        a.units[0].position = (30.0, 30.0)
        b.units[0].position = (27.0, 30.0)

        battle = Battle(a, b, map_=_open_map())
        a._battle_ref = battle
        b._battle_ref = battle
        b.command_points = 0

        b_unit = b.units[0]
        # 7 wounds out of 10: above Half-Strength (5), so Delirium cannot fire.
        b_unit.current_health = 7.0

        health_before = b_unit.current_health

        # Force 2D6 = 2 (fail). No D3 call should be made.
        with mock.patch("code.simulator.random.randint") as m:
            m.side_effect = [1, 1]
            battle._run_battleshock_phase(round_num=1)

        self.assertEqual(
            b_unit.current_health,
            health_before,
            "Delirium must NOT fire when the unit is above Half-Strength "
            "(7/10 wounds).",
        )

    def test_delirium_does_not_fire_outside_aura(self) -> None:
        """Delirium must NOT deal mortal wounds when the target is outside
        the 9\" aura range."""
        enemy_profile = _generic_profile(
            name="OutoRange",
            faction="Generic",
            leadership=7,
            health=10.0,
        )
        ck_profile = _chaos_knights_profile()

        a = Army("CK")
        b = Army("Enemy")
        a.add_unit(ck_profile)
        b.add_unit(enemy_profile)
        a.units[0].position = (30.0, 30.0)
        b.units[0].position = (20.0, 30.0)  # 10" away — outside aura

        battle = Battle(a, b, map_=_open_map())
        a._battle_ref = battle
        b._battle_ref = battle
        b.command_points = 0

        b_unit = b.units[0]
        b_unit.current_health = 3.0  # below half

        health_before = b_unit.current_health

        with mock.patch("code.simulator.random.randint") as m:
            m.side_effect = [1, 1]  # 2D6 = 2 (fail), no D3 drawn
            battle._run_battleshock_phase(round_num=1)

        self.assertEqual(
            b_unit.current_health,
            health_before,
            "Delirium must not deal MWs when the unit is outside the 9\" "
            "Chaos Knights aura.",
        )

    def test_delirium_off_when_gate_disabled(self) -> None:
        """With SWEG_HARBINGERS=0 (explicit OFF; default-ON since wave 232),
        a Below Half-Strength unit within 9\" that fails its Battle-shock
        test must NOT receive any extra mortal wounds from Delirium."""
        os.environ["SWEG_HARBINGERS"] = "0"

        enemy_profile = _generic_profile(
            name="Off-Fragile",
            faction="Generic",
            leadership=7,
            health=10.0,
        )
        ck_profile = _chaos_knights_profile()

        a = Army("CK")
        b = Army("Enemy")
        a.add_unit(ck_profile)
        b.add_unit(enemy_profile)
        a.units[0].position = (30.0, 30.0)
        b.units[0].position = (27.0, 30.0)

        battle = Battle(a, b, map_=_open_map())
        a._battle_ref = battle
        b._battle_ref = battle
        b.command_points = 0

        b_unit = b.units[0]
        b_unit.current_health = 3.0

        health_before = b_unit.current_health

        with mock.patch("code.simulator.random.randint") as m:
            m.side_effect = [1, 1]  # 2D6 = 2 (fail), no D3 drawn
            battle._run_battleshock_phase(round_num=1)

        self.assertEqual(
            b_unit.current_health,
            health_before,
            "With gate OFF, Delirium must not deal mortal wounds.",
        )


# ---------------------------------------------------------------------------
# Doom suppression tests
# ---------------------------------------------------------------------------

class DoomSuppressionTests(unittest.TestCase):
    """With SWEG_HARBINGERS OFF the sim's standing Dread pick is Doom
    (+1 to Wound vs Battle-shocked targets, wired in code/units.py).
    With SWEG_HARBINGERS ON, Despair replaces Doom as the round-1 pick,
    so Doom must be SUPPRESSED — otherwise the army would hold more
    selected Dread abilities than the rule's three picks grant."""

    def tearDown(self) -> None:
        os.environ.pop("SWEG_HARBINGERS", None)

    def _avg_ck_damage_vs_target(
        self,
        target_shocked: bool,
        n: int = 400,
        seed: int = 11,
    ) -> float:
        """Average ranged damage from a Chaos Knights attacker (strength 4,
        so the Wound roll is 4+ vs toughness 4 and Doom's +1 matters) into a
        Generic target, optionally Battle-shocked. Same seed both arms —
        identical RNG streams make the comparison paired."""
        random.seed(seed)
        ck_attacker = _generic_profile(
            name="Dread Host",   # must NOT start with "War Dog" (Dread Tyrants)
            faction="Chaos Knights",
            health=20.0,
        )
        target_profile = _generic_profile(
            name="Doom Target",
            faction="Generic",
            health=500.0,
        )

        a = Army("CK")
        b = Army("Enemy")
        a.add_unit(ck_attacker)
        b.add_unit(target_profile)
        a_unit = a.units[0]
        b_unit = b.units[0]
        a_unit.position = (20.0, 30.0)
        b_unit.position = (32.0, 30.0)

        battle = Battle(a, b, map_=_open_map())
        a._battle_ref = battle
        b._battle_ref = battle
        battle._current_round = 1
        a_unit.army_ref = a
        b_unit.army_ref = b

        if target_shocked:
            b_unit.battleshocked_until_round = 1

        total = 0.0
        for _ in range(n):
            b_unit.current_health = float(target_profile.health)
            total += a_unit.attack(b_unit, distance=12.0, mode="ranged")
        return total / n

    def test_doom_fires_with_gate_off(self) -> None:
        """Gate explicitly OFF (default-ON since wave 232): a Chaos Knights
        attacker must deal MORE damage into a Battle-shocked target (Doom +1
        to Wound, 4+ → 3+)."""
        os.environ["SWEG_HARBINGERS"] = "0"
        dmg_shocked = self._avg_ck_damage_vs_target(target_shocked=True)
        dmg_normal = self._avg_ck_damage_vs_target(target_shocked=False)
        self.assertGreater(
            dmg_shocked,
            dmg_normal,
            f"With SWEG_HARBINGERS off, Doom must fire vs a Battle-shocked "
            f"target: shocked={dmg_shocked:.3f} normal={dmg_normal:.3f}.",
        )

    def test_doom_suppressed_with_gate_on(self) -> None:
        """Gate ON: Doom is replaced by Despair as the round-1 pick, so a
        Battle-shocked target must take the SAME damage as a normal one
        (paired RNG streams — exact equality expected)."""
        os.environ["SWEG_HARBINGERS"] = "1"
        dmg_shocked = self._avg_ck_damage_vs_target(target_shocked=True)
        dmg_normal = self._avg_ck_damage_vs_target(target_shocked=False)
        self.assertEqual(
            dmg_shocked,
            dmg_normal,
            f"With SWEG_HARBINGERS on, Doom must be suppressed (Despair "
            f"replaces it as the round-1 pick): shocked={dmg_shocked:.3f} "
            f"normal={dmg_normal:.3f} should be identical on paired seeds.",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
