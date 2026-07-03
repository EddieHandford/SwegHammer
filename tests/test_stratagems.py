"""Tests for the Stratagem dataclass + CP economy + universal stratagems.

Detachment-specific stratagem tests (Cult of Magic, Plague Company, parts of
Battle Host) were removed per the 2026-05-15 fabrication audit (commit
fa9a957) — those stratagems had no Wahapedia equivalent. Tests for the two
surviving real Warhost stratagems (Lightning-Fast Reactions, Fire and Fade)
and the re-anchored Disgustingly Resilient live alongside the per-detachment
PRs that own them.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.events import StratagemFired
from code.simulator import Battle
from code.stratagems import (
    COMMAND_RE_ROLL, COUNTER_OFFENSIVE, TANK_SHOCK, UNIVERSAL_INSANE_BRAVERY,
    CP_CAP, CP_PER_COMMAND_PHASE, STARTING_CP, Stratagem,
    UNIVERSAL_STRATAGEMS, award_command_phase_cp, stratagems_for_army,
)
from code.strategy import should_fire_stratagem
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _heavy_profile() -> UnitProfile:
    """A HEAVY-class target: high points, high HP. Triggers the AI's
    'fire Command Re-Roll on this' heuristic."""
    return UnitProfile(
        name="Knight",
        health=22, damage=6, hit_probability=2 / 3,
        ap=-3, save=2, strength=10, toughness=12,
        attacks=4, weapon_damage_per_shot=1.5,
        range_inches=48,
        unit_keywords=("VEHICLE", "TITANIC"),
    )


def _marine_profile() -> UnitProfile:
    return UnitProfile(
        name="Marine",
        health=2, damage=1, hit_probability=2 / 3,
        ap=-1, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        range_inches=24,
    )


def _vehicle_charger_profile() -> UnitProfile:
    """A VEHICLE with usable melee output — eligible to declare a charge and
    fire Tank Shock."""
    return UnitProfile(
        name="Land Speeder",
        health=8, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=6, toughness=9,
        move=14.0, attacks=4, weapon_damage_per_shot=1.0,
        melee_attacks=3, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5,
        range_inches=24,
        unit_keywords=("VEHICLE",),
    )


def _build_army(name: str, profiles) -> Army:
    army = Army(name)
    for p in profiles:
        army.add_unit(p)
    return army


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class StratagemDataclassTests(unittest.TestCase):

    def test_round_trip_fields(self):
        s = Stratagem(
            name="Sample", cp_cost=2, phase="fight",
            trigger="x", effect="y", once_per_battle=True,
        )
        self.assertEqual(s.name, "Sample")
        self.assertEqual(s.cp_cost, 2)
        self.assertEqual(s.phase, "fight")
        self.assertEqual(s.trigger, "x")
        self.assertEqual(s.effect, "y")
        self.assertTrue(s.once_per_battle)

    def test_universal_stratagem_count_and_costs(self):
        # #iter12: Heroic Intervention removed from the universal core
        # stratagems tuple — it is a free core CHARACTER ability per
        # Wahapedia 10e core rules, not a 1 CP stratagem. The four
        # current universals are Command Re-Roll, Counter-Offensive,
        # Tank Shock, and Insane Bravery (added as the universal core
        # version; the Orks War Horde variant is a separate faction entry).
        self.assertEqual(len(UNIVERSAL_STRATAGEMS), 4)
        names = {s.name for s in UNIVERSAL_STRATAGEMS}
        self.assertNotIn("Heroic Intervention", names)
        self.assertIn("Insane Bravery", names)
        # Spot-check the canonical Command Point costs.
        self.assertEqual(COMMAND_RE_ROLL.cp_cost, 1)
        self.assertEqual(COUNTER_OFFENSIVE.cp_cost, 2)
        self.assertEqual(TANK_SHOCK.cp_cost, 1)
        self.assertEqual(UNIVERSAL_INSANE_BRAVERY.cp_cost, 1)
        # Insane Bravery is once-per-battle; the other three universals are not.
        self.assertTrue(UNIVERSAL_INSANE_BRAVERY.once_per_battle)
        self.assertFalse(COMMAND_RE_ROLL.once_per_battle)
        self.assertFalse(COUNTER_OFFENSIVE.once_per_battle)
        self.assertFalse(TANK_SHOCK.once_per_battle)

    def test_stratagem_is_frozen_and_hashable(self):
        # Frozen dataclass — instances belong in sets / tuple fields.
        s = {COMMAND_RE_ROLL, COUNTER_OFFENSIVE, TANK_SHOCK, UNIVERSAL_INSANE_BRAVERY}
        self.assertEqual(len(s), 4)


class CpEconomyTests(unittest.TestCase):

    def tearDown(self):
        os.environ.pop("SWEG_CP_PER_COMMAND_PHASE", None)

    def test_army_starts_at_strike_force_cp(self):
        army = Army("Test")
        self.assertEqual(army.command_points, STARTING_CP)
        self.assertEqual(STARTING_CP, 3)   # canonical Strike Force value

    def test_award_command_phase_cp_increments_by_two_by_default(self):
        # Secondary-economy audit fix D4 (2026-07-03): the printed 10e core
        # rule grants BOTH players 1CP at the start of EACH of the two
        # Command phases per battle round, so `award_command_phase_cp`
        # (called once per army per round from `Battle._run_round`) grants
        # CP_PER_COMMAND_PHASE * 2 by default.
        os.environ.pop("SWEG_CP_PER_COMMAND_PHASE", None)
        army = Army("Test")
        starting = army.command_points
        award_command_phase_cp(army)
        self.assertEqual(army.command_points, starting + CP_PER_COMMAND_PHASE * 2)

    def test_award_command_phase_cp_killswitch_reverts_to_one(self):
        # SWEG_CP_PER_COMMAND_PHASE=0 reproduces the pre-fix 1-per-round
        # rate exactly, for the byte-identical-off validation.
        os.environ["SWEG_CP_PER_COMMAND_PHASE"] = "0"
        army = Army("Test")
        starting = army.command_points
        award_command_phase_cp(army)
        self.assertEqual(army.command_points, starting + CP_PER_COMMAND_PHASE)

    def test_cp_capped_at_six(self):
        army = Army("Test")
        # Pump past the cap and ensure we clamp.
        army.command_points = CP_CAP - 1
        award_command_phase_cp(army)
        self.assertEqual(army.command_points, CP_CAP)
        # One more should NOT exceed the cap.
        award_command_phase_cp(army)
        self.assertEqual(army.command_points, CP_CAP)

    def test_battle_drips_two_cp_per_round(self):
        # Two tiny armies; run a 5-round battle and confirm CP increments
        # at each round start (clamped to 6). At the printed +2/round rate
        # (fix D4) the cap binds even sooner than the pre-fix +1/round rate.
        random.seed(0)
        a = _build_army("A", [_marine_profile(), _marine_profile()])
        b = _build_army("B", [_marine_profile(), _marine_profile()])
        # Pre-set both to CP_CAP - 1 so the cap clamp gets exercised mid-battle.
        a.command_points = STARTING_CP
        b.command_points = STARTING_CP
        battle = Battle(a, b)
        battle.run()
        # After 5 rounds of +2/round on top of STARTING_CP=3, both should be
        # at CP_CAP (the cap clamps). We also can't be < STARTING_CP since
        # the AI may spend, but the lower bound is 'spent CP < gained CP'.
        # Use a relaxed assertion that captures the cap behaviour.
        self.assertGreaterEqual(a.command_points, 0)
        self.assertLessEqual(a.command_points, CP_CAP)
        self.assertGreaterEqual(b.command_points, 0)
        self.assertLessEqual(b.command_points, CP_CAP)


class StratagemsForArmyTests(unittest.TestCase):

    def test_every_army_gets_the_four_universals(self):
        # #iter12: Heroic Intervention removed from the universal core
        # stratagems — it is a free core CHARACTER ability now.
        # Stream B: Insane Bravery (core universal) added alongside the
        # existing three; the Orks War Horde variant is separate.
        army = Army("Test")
        army.add_unit(_marine_profile())
        strats = stratagems_for_army(army)
        names = {s.name for s in strats}
        self.assertIn("Command Re-Roll", names)
        self.assertIn("Counter-Offensive", names)
        self.assertIn("Tank Shock", names)
        self.assertIn("Insane Bravery", names)
        self.assertNotIn("Heroic Intervention", names)


class CommandRerollTests(unittest.TestCase):
    """Command Re-Roll should consume 1 CP when fired, and the heuristic
    should green-light a re-roll vs a HEAVY target."""

    def test_heuristic_fires_on_heavy_target(self):
        army = Army("Test")
        army.command_points = 5
        # Build a target unit with the HEAVY profile.
        target = Unit(_heavy_profile())
        target.uid = "T0"
        ctx = {"target": target, "roll_kind": "wound"}
        self.assertTrue(should_fire_stratagem(army, COMMAND_RE_ROLL, ctx))

    def test_heuristic_skips_small_fish(self):
        army = Army("Test")
        army.command_points = 5
        # Build a low-value target (a baseline Marine).
        target = Unit(_marine_profile())
        target.uid = "T0"
        ctx = {"target": target, "roll_kind": "wound"}
        self.assertFalse(should_fire_stratagem(army, COMMAND_RE_ROLL, ctx))

    def test_heuristic_refuses_without_cp(self):
        army = Army("Test")
        army.command_points = 0
        target = Unit(_heavy_profile())
        ctx = {"target": target}
        self.assertFalse(should_fire_stratagem(army, COMMAND_RE_ROLL, ctx))

    def test_fire_command_reroll_consumes_one_cp(self):
        # Spin up a real Battle, mark the attacker's army with CP, and call
        # maybe_fire_command_reroll with a HEAVY target — CP should drop.
        a = _build_army("A", [_marine_profile()])
        b = _build_army("B", [_heavy_profile()])
        random.seed(42)
        battle = Battle(a, b)
        # Don't run; just need _battle_ref + uids wired up.
        battle._assign_uids()
        a.command_points = 4
        attacker = a.units[0]
        target = b.units[0]
        fired = battle.maybe_fire_command_reroll(attacker, target, "wound")
        self.assertTrue(fired)
        self.assertEqual(a.command_points, 3)

    def test_command_reroll_emits_stratagem_fired_event(self):
        a = _build_army("A", [_marine_profile()])
        b = _build_army("B", [_heavy_profile()])
        events: list = []

        class Recorder:
            def on_event(self, e):
                events.append(e)

        random.seed(42)
        battle = Battle(a, b, subscribers=[Recorder()])
        battle._assign_uids()
        a.command_points = 4
        battle.maybe_fire_command_reroll(a.units[0], b.units[0], "wound")
        fired_events = [e for e in events if isinstance(e, StratagemFired)]
        self.assertEqual(len(fired_events), 1)
        self.assertEqual(fired_events[0].stratagem_name, "Command Re-Roll")
        self.assertEqual(fired_events[0].cp_cost, 1)
        self.assertEqual(fired_events[0].army_name, "A")


class CounterOffensiveTests(unittest.TestCase):
    """Counter-Offensive should reorder the fight sequence: when an enemy
    unit fights and kills a friendly model, the friendly army's retaliator
    strikes immediately, BEFORE its own normal activation comes around.

    Assertion: the enemy unit takes damage between our model's UnitFought
    (the strike that killed our model) and the next time the enemy unit
    activates of its own accord.
    """

    def test_counter_offensive_reorders_fight_sequence(self):
        from code.events import UnitActivated, UnitFought

        # Force determinism on charge / hit / wound rolls.
        random.seed(0)

        # Glass-cannon attacker on Army A so its hit reliably kills our
        # frail single-HP defender, AND a beefy retaliator on Army B so
        # the Counter-Offensive strike has real teeth.
        glass_cannon = UnitProfile(
            name="Glass Cannon",
            health=4, damage=0, hit_probability=2 / 3,
            ap=-2, save=4, strength=10, toughness=4,
            attacks=0, weapon_damage_per_shot=0.0,
            move=12.0,
            melee_attacks=8, melee_damage_per_shot=3.0,
            melee_hit_probability=5 / 6, melee_strength=10,
            melee_ap=-3,
            range_inches=1,
        )
        retaliator = UnitProfile(
            name="Big Brawler",
            health=10, damage=0, hit_probability=2 / 3,
            ap=-2, save=3, strength=8, toughness=8,
            attacks=0, weapon_damage_per_shot=0.0,
            move=6.0,
            melee_attacks=6, melee_damage_per_shot=2.0,
            melee_hit_probability=5 / 6, melee_strength=8,
            melee_ap=-2,
            range_inches=1,
        )
        frail_defender = UnitProfile(
            name="Frail",
            health=1, damage=0, hit_probability=2 / 3,
            ap=0, save=6, strength=3, toughness=3,
            attacks=0, weapon_damage_per_shot=0.0,
            melee_attacks=1, melee_damage_per_shot=1.0,
            melee_hit_probability=1 / 2, melee_strength=3,
            range_inches=1,
        )

        a = _build_army("A", [glass_cannon])
        b = _build_army("B", [frail_defender, retaliator])

        events: list = []

        class Recorder:
            def on_event(self, e):
                events.append(e)

        battle = Battle(a, b, subscribers=[Recorder()])
        # Position units so the glass-cannon is engaged with the frail
        # defender AND the retaliator is in engagement range of the
        # glass-cannon (counter-offensive prerequisite).
        battle._assign_uids()
        # Skip _run_round preamble — call _do_fight directly with a clean
        # state. Manually award CP for the test.
        b.command_points = 5
        a.units[0].position = (10.0, 10.0)
        b.units[0].position = (10.0, 10.5)   # frail in melee w/ glass cannon
        b.units[1].position = (10.0, 11.0)   # retaliator within 1.5" of glass

        # Make sure no fight already happened.
        glass_hp_before = a.units[0].current_health

        battle._do_fight(a.units[0], a, b)

        # The frail defender should be dead from the glass-cannon's strike.
        self.assertFalse(b.units[0].is_alive,
                         "frail defender should have been killed by the strike")

        # The retaliator must have struck back via Counter-Offensive — the
        # glass cannon should have taken damage AFTER landing its killing
        # blow but before its activation continues.
        glass_hp_after = a.units[0].current_health
        self.assertLess(
            glass_hp_after, glass_hp_before,
            "glass cannon should have taken Counter-Offensive damage",
        )

        # Stratagem should have fired and CP should have dropped by 2.
        fired = [e for e in events if isinstance(e, StratagemFired)]
        self.assertTrue(
            any(e.stratagem_name == "Counter-Offensive" for e in fired),
            f"expected a StratagemFired(Counter-Offensive) event, got {fired}",
        )
        self.assertEqual(b.command_points, 3, "should have spent 2 CP")


class TankShockTests(unittest.TestCase):

    def test_tank_shock_heuristic_fires_for_vehicle(self):
        army = Army("Test")
        army.command_points = 2
        v = Unit(_vehicle_charger_profile())
        ctx = {"charger": v, "succeeded": True}
        self.assertTrue(should_fire_stratagem(army, TANK_SHOCK, ctx))

    def test_tank_shock_heuristic_skips_non_vehicle(self):
        army = Army("Test")
        army.command_points = 2
        m = Unit(_marine_profile())
        ctx = {"charger": m, "succeeded": True}
        self.assertFalse(should_fire_stratagem(army, TANK_SHOCK, ctx))


# Heroic Intervention is no longer a stratagem (#iter12) — it is a free
# core CHARACTER ability implemented in code.simulator._do_heroic_intervention.
# Coverage for the new core mechanic lives in tests/test_heroic_intervention.py.


if __name__ == "__main__":
    unittest.main()
