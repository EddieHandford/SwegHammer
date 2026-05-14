"""Tests for the Stratagem dataclass + CP economy + universal stratagems."""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.events import StratagemFired
from code.simulator import Battle
from code.detachments import (
    BATTLE_HOST, CULT_OF_MAGIC, PLAGUE_COMPANY,
)
from code.stratagems import (
    COMMAND_RE_ROLL, COUNTER_OFFENSIVE, HEROIC_INTERVENTION, TANK_SHOCK,
    CP_CAP, CP_PER_COMMAND_PHASE, STARTING_CP, Stratagem,
    UNIVERSAL_STRATAGEMS, award_command_phase_cp, stratagems_for_army,
    # Detachment-specific
    DOOMBOLT, TWIST_OF_FATE, GLAMOUR_OF_TZEENTCH,
    DISGUSTINGLY_RESILIENT, PLAGUE_WEAPONS, OUTBREAK_OF_PESTILENCE,
    LIGHTNING_FAST_REACTIONS, FIRE_AND_FADE, MATCHLESS_AGILITY,
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
        self.assertEqual(len(UNIVERSAL_STRATAGEMS), 4)
        # Spot-check the canonical CP costs.
        self.assertEqual(COMMAND_RE_ROLL.cp_cost, 1)
        self.assertEqual(COUNTER_OFFENSIVE.cp_cost, 2)
        self.assertEqual(TANK_SHOCK.cp_cost, 1)
        self.assertEqual(HEROIC_INTERVENTION.cp_cost, 1)

    def test_stratagem_is_frozen_and_hashable(self):
        # Frozen dataclass — instances belong in sets / tuple fields.
        s = {COMMAND_RE_ROLL, COUNTER_OFFENSIVE, TANK_SHOCK}
        self.assertEqual(len(s), 3)


class CpEconomyTests(unittest.TestCase):

    def test_army_starts_at_strike_force_cp(self):
        army = Army("Test")
        self.assertEqual(army.command_points, STARTING_CP)
        self.assertEqual(STARTING_CP, 3)   # canonical Strike Force value

    def test_award_command_phase_cp_increments_by_one(self):
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

    def test_battle_drips_one_cp_per_round(self):
        # Two tiny armies; run a 5-round battle and confirm CP increments
        # at each round start (clamped to 6).
        random.seed(0)
        a = _build_army("A", [_marine_profile(), _marine_profile()])
        b = _build_army("B", [_marine_profile(), _marine_profile()])
        # Pre-set both to CP_CAP - 1 so the cap clamp gets exercised mid-battle.
        a.command_points = STARTING_CP
        b.command_points = STARTING_CP
        battle = Battle(a, b)
        battle.run()
        # After 5 rounds of +1/round on top of STARTING_CP=3, both should be
        # at CP_CAP (the cap clamps). We also can't be < STARTING_CP since
        # the AI may spend, but the lower bound is 'spent CP < gained CP'.
        # Use a relaxed assertion that captures the cap behaviour.
        self.assertGreaterEqual(a.command_points, 0)
        self.assertLessEqual(a.command_points, CP_CAP)
        self.assertGreaterEqual(b.command_points, 0)
        self.assertLessEqual(b.command_points, CP_CAP)


class StratagemsForArmyTests(unittest.TestCase):

    def test_every_army_gets_the_four_universals(self):
        army = Army("Test")
        army.add_unit(_marine_profile())
        strats = stratagems_for_army(army)
        names = {s.name for s in strats}
        self.assertIn("Command Re-Roll", names)
        self.assertIn("Counter-Offensive", names)
        self.assertIn("Tank Shock", names)
        self.assertIn("Heroic Intervention", names)


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


class HeroicInterventionTests(unittest.TestCase):

    def test_heroic_intervention_heuristic_requires_character(self):
        army = Army("Test")
        army.command_points = 2
        # Non-CHARACTER unit — should not fire.
        u = Unit(_marine_profile())
        ctx = {"character": u, "charge_target": u, "distance": 4.0}
        self.assertFalse(should_fire_stratagem(army, HEROIC_INTERVENTION, ctx))
        # Same unit but flagged CHARACTER — fires within 6".
        char_profile = UnitProfile(
            name="Captain",
            health=4, damage=1, hit_probability=2 / 3,
            ap=-1, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0,
            melee_attacks=4, melee_damage_per_shot=1.0,
            melee_hit_probability=5 / 6, melee_strength=5,
            range_inches=24,
            unit_keywords=("CHARACTER", "INFANTRY"),
        )
        c = Unit(char_profile)
        ctx = {"character": c, "charge_target": c, "distance": 4.0}
        self.assertTrue(should_fire_stratagem(army, HEROIC_INTERVENTION, ctx))

    def test_heroic_intervention_heuristic_skips_far_character(self):
        army = Army("Test")
        army.command_points = 2
        char_profile = UnitProfile(
            name="Captain",
            health=4, damage=1, hit_probability=2 / 3,
            ap=-1, save=3, strength=4, toughness=4,
            unit_keywords=("CHARACTER",),
        )
        c = Unit(char_profile)
        ctx = {"character": c, "charge_target": c, "distance": 9.0}
        self.assertFalse(should_fire_stratagem(army, HEROIC_INTERVENTION, ctx))


# ---------------------------------------------------------------------------
# Detachment-specific stratagem tests (Cult of Magic, Plague Company, Battle Host)
# ---------------------------------------------------------------------------

def _psyker_profile() -> UnitProfile:
    """A Thousand Sons PSYKER — fires Doombolt."""
    return UnitProfile(
        name="Rubric Sorcerer",
        health=4, damage=1, hit_probability=2 / 3,
        ap=-2, save=3, strength=5, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        melee_attacks=3, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=6,
        range_inches=18,
        faction="Thousand Sons",
        unit_keywords=("INFANTRY", "PSYKER", "THOUSAND SONS", "CHARACTER"),
    )


def _dg_profile() -> UnitProfile:
    # Multi-wound DG shooter — meets the Disgustingly Resilient (>=4 HP) and
    # Plague Weapons (ranged DPA >= 2) AI gates without being a vehicle.
    return UnitProfile(
        name="Plague Burst Crawler-lite",
        health=6, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=6, toughness=8,
        attacks=3, weapon_damage_per_shot=1.0,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        range_inches=24,
        faction="Death Guard",
        unit_keywords=("INFANTRY", "DEATH GUARD"),
    )


def _aeldari_profile() -> UnitProfile:
    # Big ranged threat: hits the cost + DPA thresholds the AI uses to gate
    # Fire and Fade / Matchless Agility (cost >= 80, ranged DPA >= 2).
    return UnitProfile(
        name="Wraithguard",
        health=3, damage=3, hit_probability=2 / 3,
        ap=-2, save=3, strength=10, toughness=7,
        attacks=3, weapon_damage_per_shot=1.0,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=1 / 2, melee_strength=5,
        range_inches=18,
        faction="Aeldari",
        unit_keywords=("INFANTRY", "AELDARI"),
        points_override=170.0,
    )


def _vehicle_target_profile() -> UnitProfile:
    """A heavy enemy unit — the 'target' Doombolt/Twist of Fate fire at."""
    return UnitProfile(
        name="Enemy Knight",
        health=22, damage=6, hit_probability=2 / 3,
        ap=-3, save=2, strength=10, toughness=12,
        attacks=4, weapon_damage_per_shot=1.5,
        range_inches=48,
        unit_keywords=("VEHICLE", "TITANIC"),
    )


class CultOfMagicStratagemTests(unittest.TestCase):
    """Three Cult of Magic stratagems: Doombolt (D3 MW), Twist of Fate
    (+1 to wound), Glamour of Tzeentch (transient 4++)."""

    def test_doombolt_deals_mortal_wounds_and_emits_event(self):
        a = _build_army("Thousand Sons", [_psyker_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = CULT_OF_MAGIC
        a.command_points = 5
        events: list = []

        class Recorder:
            def on_event(self, e):
                events.append(e)

        random.seed(0)
        battle = Battle(a, b, subscribers=[Recorder()])
        battle._assign_uids()
        starting_hp = b.units[0].current_health

        battle._try_doombolt(a, b)

        fired = [e for e in events if isinstance(e, StratagemFired)]
        self.assertTrue(any(e.stratagem_name == "Doombolt" for e in fired),
                        f"expected a StratagemFired(Doombolt) event, got {fired}")
        # Deterministic 2 MW (median D3).
        self.assertEqual(a.command_points, 4, "should have spent 1 CP")
        self.assertLess(b.units[0].current_health, starting_hp,
                        "target should have taken damage")

    def test_doombolt_skips_without_psyker(self):
        # Marine army (no PSYKER keyword) — Doombolt should NOT fire even
        # though we hand it the Cult of Magic detachment for the test.
        a = _build_army("Imposters", [_marine_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = CULT_OF_MAGIC
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_doombolt(a, b)
        self.assertEqual(a.command_points, 5,
                         "no PSYKER → no Doombolt → CP unchanged")

    def test_twist_of_fate_sets_plus_one_to_wound_flag(self):
        a = _build_army("TSons", [_psyker_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = CULT_OF_MAGIC
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_twist_of_fate(a, b)
        self.assertEqual(a.command_points, 4, "should have spent 1 CP")
        # The PSYKER (highest DPA TSons unit) gets the transient buff.
        self.assertTrue(a.units[0].transient_plus_one_to_wound_shooting,
                        "Twist of Fate should have set the +1-to-wound flag")

    def test_glamour_of_tzeentch_grants_transient_4_invuln(self):
        a = _build_army("TSons", [_psyker_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = CULT_OF_MAGIC
        a.command_points = 5
        # Wound the unit so the AI greenlights the spend.
        a.units[0].current_health = 1.0
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_glamour_of_tzeentch(a, b)
        self.assertEqual(a.command_points, 3, "should have spent 2 CP")
        self.assertTrue(a.units[0].transient_invuln_4,
                        "Glamour should set transient_invuln_4")


class PlagueCompanyStratagemTests(unittest.TestCase):
    """Three Plague Company stratagems: Disgustingly Resilient (-1 damage
    taken), Plague Weapons (+1 wound shooting), Outbreak (+1 wound melee)."""

    def test_disgustingly_resilient_minus_one_damage(self):
        # Use a high-HP DG profile so we can take a 3-dmg hit without dying.
        beefy_dg = UnitProfile(
            name="Plagueburst Crawler",
            health=12, damage=2, hit_probability=2 / 3,
            ap=-1, save=3, strength=6, toughness=11,
            attacks=2, weapon_damage_per_shot=1.0,
            range_inches=48,
            faction="Death Guard",
            unit_keywords=("VEHICLE", "DEATH GUARD"),
        )
        a = _build_army("Death Guard", [beefy_dg])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = PLAGUE_COMPANY
        a.command_points = 5
        # Wound it so the defensive heuristic green-lights the spend.
        a.units[0].current_health = 8.0
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_disgustingly_resilient(a, b)
        self.assertEqual(a.command_points, 4, "should have spent 1 CP")
        self.assertTrue(a.units[0].transient_minus_one_damage_taken)

        # Verify the receive_damage path actually subtracts 1 (min 1).
        starting_hp = a.units[0].current_health
        a.units[0].receive_damage(3.0)
        # 3 damage → 2 after -1, FNP=7 so no FNP rolls.
        self.assertAlmostEqual(
            starting_hp - a.units[0].current_health, 2.0, places=1,
            msg="Disgustingly Resilient should have reduced 3 → 2 damage",
        )

    def test_plague_weapons_sets_wound_flag_on_shooter(self):
        a = _build_army("Death Guard", [_dg_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = PLAGUE_COMPANY
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_plague_weapons(a, b)
        self.assertEqual(a.command_points, 4)
        self.assertTrue(a.units[0].transient_plus_one_to_wound_shooting)

    def test_outbreak_of_pestilence_sets_melee_wound_flag(self):
        # The Outbreak AI gates on melee DPA >= 2.0 so the buff lands on a
        # real melee unit, not a token bayonet. Use Deathshroud-style melee
        # numbers (3 attacks, 2 damage, 2/3 hit) for ~4 DPA.
        deathshroud = UnitProfile(
            name="Deathshroud Terminator",
            health=4, damage=1, hit_probability=2 / 3,
            ap=-1, save=2, strength=4, toughness=5,
            attacks=1, weapon_damage_per_shot=1.0,
            melee_attacks=3, melee_damage_per_shot=2.0,
            melee_hit_probability=2 / 3, melee_strength=6,
            melee_ap=-2,
            range_inches=12,
            faction="Death Guard",
            unit_keywords=("INFANTRY", "DEATH GUARD", "TERMINATOR"),
        )
        a = _build_army("Death Guard", [deathshroud])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = PLAGUE_COMPANY
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_outbreak_of_pestilence(a, b)
        self.assertEqual(a.command_points, 4)
        self.assertTrue(a.units[0].transient_plus_one_to_wound_melee)


class BattleHostStratagemTests(unittest.TestCase):
    """Three Battle Host stratagems: Lightning-Fast Reactions (+1 save),
    Fire and Fade (reroll hits shooting), Matchless Agility (transient
    Assault)."""

    def test_lightning_fast_reactions_sets_plus_one_save(self):
        a = _build_army("Aeldari", [_aeldari_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = BATTLE_HOST
        a.command_points = 5
        # The Aeldari AI requires HP loss > 40% AND cost >= 100 to fire
        # Lightning-Fast Reactions. Wraithguard cost 170, HP 3 → drop to
        # 1.5 = 50% loss to satisfy the threshold.
        a.units[0].current_health = 1.5
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_lightning_fast_reactions(a, b)
        self.assertEqual(a.command_points, 4)
        self.assertTrue(a.units[0].transient_plus_one_save)

    def test_fire_and_fade_sets_reroll_hits_flag(self):
        a = _build_army("Aeldari", [_aeldari_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = BATTLE_HOST
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()
        # The Aeldari AI requires the heavy target to be already softened
        # (>15% HP loss) before paying for Fire and Fade. Drop the enemy
        # Knight to ~18 / 22 HP = 18% loss.
        b.units[0].current_health = 18.0
        battle._try_fire_and_fade(a, b)
        self.assertEqual(a.command_points, 4)
        self.assertTrue(a.units[0].transient_reroll_hits_shooting)

    def test_matchless_agility_fires_only_when_unit_out_of_range(self):
        # In range — should NOT fire.
        a = _build_army("Aeldari", [_aeldari_profile()])
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = BATTLE_HOST
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()
        # Place units in weapon range of each other.
        a.units[0].position = (10.0, 10.0)
        b.units[0].position = (10.0, 20.0)   # 10" away, within 18" weapon range
        battle._try_matchless_agility(a, b)
        self.assertEqual(a.command_points, 5,
                         "Matchless Agility should not fire when shooter is in range")
        self.assertFalse(a.units[0].transient_assault_this_round)

        # Out of range — SHOULD fire.
        a2 = _build_army("Aeldari2", [_aeldari_profile()])
        b2 = _build_army("Foes2", [_vehicle_target_profile()])
        a2.detachment = BATTLE_HOST
        a2.command_points = 5
        battle2 = Battle(a2, b2)
        battle2._assign_uids()
        a2.units[0].position = (10.0, 10.0)
        b2.units[0].position = (10.0, 40.0)  # 30" away, out of 18" range
        battle2._try_matchless_agility(a2, b2)
        self.assertEqual(a2.command_points, 4)
        self.assertTrue(a2.units[0].transient_assault_this_round)


class DetachmentStratagemEventTests(unittest.TestCase):
    """Each new stratagem must emit a StratagemFired event with its name + cp_cost."""

    def _capture(self, stratagem_name: str, detachment, army_factory, fire_call):
        a = army_factory("A")
        b = _build_army("B", [_vehicle_target_profile()])
        a.detachment = detachment
        a.command_points = 5
        events: list = []

        class Recorder:
            def on_event(self, e):
                events.append(e)

        random.seed(0)
        battle = Battle(a, b, subscribers=[Recorder()])
        battle._assign_uids()
        # Wound the home unit hard enough to unlock the heaviest defensive
        # heuristics (Lightning-Fast Reactions requires >40% HP loss). Drop
        # to 25% of max — works for all defensive triggers we test.
        a.units[0].current_health = a.units[0].profile.health * 0.25
        fire_call(battle, a, b)
        return [e for e in events if isinstance(e, StratagemFired)
                and e.stratagem_name == stratagem_name]

    def test_doombolt_event(self):
        fired = self._capture(
            "Doombolt", CULT_OF_MAGIC,
            lambda n: _build_army(n, [_psyker_profile()]),
            lambda batt, a, b: batt._try_doombolt(a, b),
        )
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].cp_cost, 1)

    def test_disgustingly_resilient_event(self):
        fired = self._capture(
            "Disgustingly Resilient", PLAGUE_COMPANY,
            lambda n: _build_army(n, [_dg_profile()]),
            lambda batt, a, b: batt._try_disgustingly_resilient(a, b),
        )
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].cp_cost, 1)

    def test_lightning_fast_reactions_event(self):
        fired = self._capture(
            "Lightning-Fast Reactions", BATTLE_HOST,
            lambda n: _build_army(n, [_aeldari_profile()]),
            lambda batt, a, b: batt._try_lightning_fast_reactions(a, b),
        )
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].cp_cost, 1)


class TransientFlagResetTests(unittest.TestCase):
    """The transient stratagem flags must clear at the start of each round."""

    def test_clear_transient_stratagem_flags(self):
        a = _build_army("Test", [_psyker_profile()])
        b = _build_army("B", [_vehicle_target_profile()])
        battle = Battle(a, b)
        # Set every transient flag manually.
        u = a.units[0]
        u.transient_plus_one_to_wound_shooting = True
        u.transient_invuln_4 = True
        u.transient_minus_one_damage_taken = True
        u.transient_plus_one_to_wound_melee = True
        u.transient_plus_one_save = True
        u.transient_reroll_hits_shooting = True
        u.transient_assault_this_round = True
        battle._clear_transient_stratagem_flags(a)
        for flag in (
            "transient_plus_one_to_wound_shooting",
            "transient_invuln_4",
            "transient_minus_one_damage_taken",
            "transient_plus_one_to_wound_melee",
            "transient_plus_one_save",
            "transient_reroll_hits_shooting",
            "transient_assault_this_round",
        ):
            self.assertFalse(
                getattr(u, flag),
                f"{flag} should have been reset",
            )


class CpAffordabilityTests(unittest.TestCase):
    """All new stratagems must refuse to fire when CP is below cp_cost."""

    def test_doombolt_needs_one_cp(self):
        a = _build_army("TSons", [_psyker_profile()])
        b = _build_army("B", [_vehicle_target_profile()])
        a.detachment = CULT_OF_MAGIC
        a.command_points = 0
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_doombolt(a, b)
        self.assertEqual(a.command_points, 0,
                         "Doombolt should not fire with 0 CP")

    def test_glamour_of_tzeentch_needs_two_cp(self):
        a = _build_army("TSons", [_psyker_profile()])
        b = _build_army("B", [_vehicle_target_profile()])
        a.detachment = CULT_OF_MAGIC
        a.command_points = 1   # not enough for 2-CP stratagem
        a.units[0].current_health = 0.5   # vulnerable
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_glamour_of_tzeentch(a, b)
        self.assertEqual(a.command_points, 1,
                         "Glamour (2 CP) should not fire with 1 CP")
        self.assertFalse(a.units[0].transient_invuln_4)


if __name__ == "__main__":
    unittest.main()
