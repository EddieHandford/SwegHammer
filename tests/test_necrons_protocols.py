"""Tests for the Awakened Dynasty (Necrons) six real Protocol stratagems.

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty

Replaces the deleted Implacable Onslaught / Methodical Destruction tests
(those stratagems were fabricated and removed in commit fa9a957). These
tests verify:
  * All 6 Protocol stratagem constants are registered on the Awakened
    Dynasty detachment with the correct CP costs.
  * The four mappable Protocols (Undying Legions, Hungry Void, Sudden
    Storm, Conquering Tyrant) wire to the right transient_* flag when
    the AI greenlights firing.
  * The two no-op APPROXIMATION Protocols (Eternal Revenant, Vengeful
    Stars) are catalogued but their dispatcher exits cleanly.

Task #194.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import AWAKENED_DYNASTY, DETACHMENTS
from code.simulator import Battle
from code.stratagems import (
    AWAKENED_DYNASTY_STRATAGEMS,
    PROTOCOL_OF_THE_CONQUERING_TYRANT,
    PROTOCOL_OF_THE_ETERNAL_REVENANT,
    PROTOCOL_OF_THE_HUNGRY_VOID,
    PROTOCOL_OF_THE_SUDDEN_STORM,
    PROTOCOL_OF_THE_UNDYING_LEGIONS,
    PROTOCOL_OF_THE_VENGEFUL_STARS,
    stratagems_for_army,
)
from code.strategy import should_fire_stratagem
from code.units import Unit, UnitProfile


def _necron_warriors_profile() -> UnitProfile:
    """A canonical NECRONS unit: multi-wound, with both ranged + melee
    output. Cost 90 so it clears the >=80pt thresholds the protocol
    heuristics use to greenlight firing."""
    return UnitProfile(
        name="Necron Warriors",
        faction="Necrons",
        health=10, damage=1, hit_probability=2 / 3,
        ap=-1, save=4, strength=4, toughness=4,
        attacks=10, weapon_damage_per_shot=1.0,
        melee_attacks=10, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        range_inches=24,
        unit_keywords=("NECRONS", "INFANTRY"),
        points_override=90.0,
    )


def _heavy_target_profile() -> UnitProfile:
    """HEAVY target — required by Hungry Void / Conquering Tyrant heuristic gates."""
    return UnitProfile(
        name="Knight",
        faction="Imperial Knights",
        health=22, damage=6, hit_probability=2 / 3,
        ap=-3, save=2, strength=10, toughness=12,
        attacks=4, weapon_damage_per_shot=1.5,
        range_inches=48,
        unit_keywords=("VEHICLE", "TITANIC"),
        points_override=400.0,
    )


def _build_necron_army_with_detachment(profiles):
    army = Army("Necrons")
    for p in profiles:
        army.add_unit(p)
    army.detachment = AWAKENED_DYNASTY
    return army


class ProtocolRegistryTests(unittest.TestCase):

    def test_six_protocols_on_detachment(self):
        self.assertEqual(len(AWAKENED_DYNASTY_STRATAGEMS), 6)
        names = {s.name for s in AWAKENED_DYNASTY_STRATAGEMS}
        self.assertEqual(
            names,
            {
                "Protocol of the Eternal Revenant",
                "Protocol of the Undying Legions",
                "Protocol of the Hungry Void",
                "Protocol of the Sudden Storm",
                "Protocol of the Conquering Tyrant",
                "Protocol of the Vengeful Stars",
            },
        )

    def test_canonical_cp_costs(self):
        # Five 1CP + one 2CP (Vengeful Stars) verbatim from Wahapedia.
        self.assertEqual(PROTOCOL_OF_THE_ETERNAL_REVENANT.cp_cost, 1)
        self.assertEqual(PROTOCOL_OF_THE_UNDYING_LEGIONS.cp_cost, 1)
        self.assertEqual(PROTOCOL_OF_THE_HUNGRY_VOID.cp_cost, 1)
        self.assertEqual(PROTOCOL_OF_THE_SUDDEN_STORM.cp_cost, 1)
        self.assertEqual(PROTOCOL_OF_THE_CONQUERING_TYRANT.cp_cost, 1)
        self.assertEqual(PROTOCOL_OF_THE_VENGEFUL_STARS.cp_cost, 2)

    def test_protocols_wired_into_awakened_dynasty(self):
        det = DETACHMENTS["awakened_dynasty"]
        names = {s.name for s in det.stratagems}
        for s in AWAKENED_DYNASTY_STRATAGEMS:
            self.assertIn(s.name, names)

    def test_stratagems_for_army_includes_protocols(self):
        army = _build_necron_army_with_detachment([_necron_warriors_profile()])
        strats = stratagems_for_army(army)
        names = {s.name for s in strats}
        # 4 universals + 6 protocols.
        for s in AWAKENED_DYNASTY_STRATAGEMS:
            self.assertIn(s.name, names)


class ProtocolHeuristicTests(unittest.TestCase):
    """Each AI heuristic should greenlight firing on a sensible Necron context
    and refuse to fire without CP."""

    def setUp(self):
        self.army = Army("Necrons")
        self.army.command_points = 5
        # Necron unit damaged enough to clear hp_frac > 0.2 (Undying Legions)
        # but not full-wiped.
        self.necron = Unit(_necron_warriors_profile())
        self.necron.uid = "N0"
        self.necron.current_health = self.necron.profile.health * 0.5
        self.target = Unit(_heavy_target_profile())
        self.target.uid = "T0"

    def test_undying_legions_fires_on_wounded_necron_unit(self):
        ctx = {"target": self.necron}
        self.assertTrue(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_UNDYING_LEGIONS, ctx,
        ))

    def test_undying_legions_skips_full_health_unit(self):
        self.necron.current_health = self.necron.profile.health
        ctx = {"target": self.necron}
        self.assertFalse(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_UNDYING_LEGIONS, ctx,
        ))

    def test_hungry_void_fires_on_melee_attacker_vs_heavy(self):
        ctx = {"attacker": self.necron, "target": self.target}
        self.assertTrue(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_HUNGRY_VOID, ctx,
        ))

    def test_sudden_storm_fires_for_meaningful_shooter(self):
        ctx = {"attacker": self.necron}
        self.assertTrue(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_SUDDEN_STORM, ctx,
        ))

    def test_conquering_tyrant_fires_on_ranged_attacker_vs_heavy(self):
        ctx = {"attacker": self.necron, "target": self.target}
        self.assertTrue(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_CONQUERING_TYRANT, ctx,
        ))

    def test_no_protocol_fires_without_cp(self):
        self.army.command_points = 0
        ctx = {"target": self.necron, "attacker": self.necron, "target_extra": self.target}
        # All four heuristics must refuse when CP = 0.
        self.assertFalse(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_UNDYING_LEGIONS, {"target": self.necron},
        ))
        self.assertFalse(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_HUNGRY_VOID,
            {"attacker": self.necron, "target": self.target},
        ))
        self.assertFalse(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_SUDDEN_STORM, {"attacker": self.necron},
        ))
        self.assertFalse(should_fire_stratagem(
            self.army, PROTOCOL_OF_THE_CONQUERING_TYRANT,
            {"attacker": self.necron, "target": self.target},
        ))


class ProtocolDispatcherTests(unittest.TestCase):
    """End-to-end: a Necron army with damaged units, given enough CP, should
    fire mappable protocols at round start and set the right transient flag.
    """

    def _make_battle(self):
        random.seed(0)
        a = Army("Necrons")
        a.add_unit(_necron_warriors_profile())
        a.add_unit(_necron_warriors_profile())   # second squad so reanimation has something to anchor on
        a.detachment = AWAKENED_DYNASTY
        a.command_points = 6
        b = Army("Enemy")
        b.add_unit(_heavy_target_profile())
        return Battle(a, b), a, b

    def test_sudden_storm_sets_assault_flag(self):
        battle, a, b = self._make_battle()
        battle._assign_uids()
        attacker = a.units[0]
        # Stratagem hook directly — bypass the round-start dispatcher to
        # isolate the flag-setting behaviour.
        battle._try_protocol_sudden_storm(a, b)
        # At least one Necron unit should have the assault flag set.
        self.assertTrue(any(
            u.transient_assault_this_round for u in a.units
        ))

    def test_hungry_void_sets_plus_one_to_wound_melee(self):
        battle, a, b = self._make_battle()
        battle._assign_uids()
        battle._try_protocol_hungry_void(a, b)
        self.assertTrue(any(
            u.transient_plus_one_to_wound_melee for u in a.units
        ))

    def test_conquering_tyrant_sets_reroll_hits_shooting(self):
        battle, a, b = self._make_battle()
        battle._assign_uids()
        battle._try_protocol_conquering_tyrant(a, b)
        self.assertTrue(any(
            u.transient_reroll_hits_shooting for u in a.units
        ))

    def test_undying_legions_sets_pulse_on_wounded_unit(self):
        battle, a, b = self._make_battle()
        battle._assign_uids()
        # Damage the first Necron unit so it's the most-vulnerable target.
        a.units[0].current_health = a.units[0].profile.health * 0.4
        battle._try_protocol_undying_legions(a, b)
        # The wounded unit should have a non-zero pulse (2 or 3 wounds).
        self.assertEqual(a.units[0].transient_undying_legions_pulse, 2)

    def test_undying_legions_pulse_revives_destroyed_peer(self):
        """The undying legions pulse should revive a dead peer of the same
        profile when applied at end of round."""
        battle, a, b = self._make_battle()
        battle._assign_uids()
        # Initialise per-army initial counts (mirroring Battle.run setup).
        battle._initial_unit_counts = {
            a.name: {"Necron Warriors": 2},
            b.name: {"Knight": 1},
        }
        # Kill the second Necron Warriors unit.
        a.units[1].current_health = 0.0
        self.assertFalse(a.units[1].is_alive)
        # Set the pulse on the surviving Necron unit.
        a.units[0].transient_undying_legions_pulse = 1
        battle._apply_undying_legions_pulse()
        # The dead peer should be revived (current_health > 0).
        self.assertTrue(a.units[1].is_alive)
        # Pulse slot should be cleared after firing.
        self.assertEqual(a.units[0].transient_undying_legions_pulse, 0)


class NoOpProtocolTests(unittest.TestCase):
    """Eternal Revenant + Vengeful Stars are catalogued but have no clean
    simulator hook. Verify they're registered (so CP economy / stratagem
    listings see them) and the dispatcher doesn't crash even though there's
    no `_try_*` for them."""

    def test_eternal_revenant_constant_exists(self):
        self.assertEqual(
            PROTOCOL_OF_THE_ETERNAL_REVENANT.name,
            "Protocol of the Eternal Revenant",
        )

    def test_vengeful_stars_constant_exists(self):
        self.assertEqual(
            PROTOCOL_OF_THE_VENGEFUL_STARS.name,
            "Protocol of the Vengeful Stars",
        )
        # Note: 2 CP — the only non-1-CP Protocol in the set.
        self.assertEqual(PROTOCOL_OF_THE_VENGEFUL_STARS.cp_cost, 2)

    def test_round_start_dispatcher_does_not_crash(self):
        random.seed(0)
        a = Army("Necrons")
        a.add_unit(_necron_warriors_profile())
        a.detachment = AWAKENED_DYNASTY
        a.command_points = 6
        b = Army("Enemy")
        b.add_unit(_heavy_target_profile())
        battle = Battle(a, b)
        battle._assign_uids()
        # No-op stratagems are part of the detachment.stratagems tuple — the
        # dispatcher must skip them cleanly without raising.
        battle._apply_detachment_stratagems(a, b)
        battle._apply_detachment_stratagems(b, a)


if __name__ == "__main__":
    unittest.main()
