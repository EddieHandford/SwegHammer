"""Tests for issue #75 — Reanimation Protocols proper model revival.

The old `reanimate_per_round` flag on the Necron `Awakened Dynasty` detachment
used to heal +1 HP on living units at end of round. 10e Reanimation Protocols
actually revives DESTROYED models — that's the new behaviour these tests pin.

Squads are modelled as N single-model Unit instances sharing a squad_id via
`Army.add_squad(profile, N)`. All N models in one codex squad share the same
squad_id so the revival pool is per-squad, not per-profile-name. Tests that
previously used `add_unit` in a loop (giving each model its own squad_id) have
been updated to use `add_squad` so each codex squad forms one shared pool.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import AWAKENED_DYNASTY
from code.events import EventLog, UnitReanimated
from code.simulator import Battle
from code.units import UnitProfile


def _necron_warrior_profile() -> UnitProfile:
    """A bare-bones Necron Warrior stand-in. We attach the faction string
    'Necrons' so Army.resolve_detachment() picks up Awakened Dynasty without
    requiring an explicit detachment kwarg."""
    return UnitProfile(
        name="Necron Warrior",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        faction="Necrons",
        unit_keywords=("INFANTRY", "REANIMATION"),
    )


def _vanilla_profile(name: str = "Trooper") -> UnitProfile:
    """A non-Necron stand-in used as the opposing army filler."""
    return UnitProfile(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        faction="Adeptus Astartes",
    )


class ReanimationProtocolsTests(unittest.TestCase):

    def test_dead_warriors_revive_at_round_end(self):
        """Kill 5 of 10 Necron Warriors manually, run one round, expect the
        alive count to go UP by exactly 1 — per Fix F-NEC-1, the cap is
        1 revive per squad per round (verbatim Wahapedia: 'restore one
        destroyed bodyguard model'), and the deaths happened this round
        (round-start snapshot was 10, alive-now is 5, deaths-this-round=5
        is greater than the 1 cap).

        Updated from the old `add_unit` loop: all 10 warriors are now added
        as a single codex squad via `add_squad(profile, 10)` so they share
        one squad_id and therefore one revival pool."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        # One codex squad of 10 Warriors — all share the same squad_id.
        necrons.add_squad(_necron_warrior_profile(), 10)
        marines = Army("Marines")
        # One filler unit so the battle doesn't terminate immediately.
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        # Drive the lifecycle by hand so we can kill models BEFORE the round
        # runs (otherwise the live combat would re-randomise everything).
        battle._assign_uids()
        battle._deploy_armies()

        # Snapshot the initial counts the way Battle.run() would do it, but
        # without invoking the full run loop (we only want to test the
        # end-of-round revival, not the full activation logic).
        battle._initial_unit_counts = {
            necrons.name: {"Necron Warrior": 10},
            marines.name: {"Marine": 1},
        }
        # Fix F-NEC-1: round-start alive-count snapshot. The 5 deaths happen
        # AFTER this snapshot in the manual lifecycle below.
        battle._round_start_alive_counts = {
            necrons.name: {"Necron Warrior": 10},
        }

        # Kill 5 warriors by zeroing their HP directly. They sit at the
        # standard deployment line so the revival anchor (their living
        # peers) is well-defined.
        for u in necrons.units[:5]:
            u.current_health = 0
        self.assertEqual(len([u for u in necrons.units if u.is_alive]), 5)

        # Invoke reanimation directly — this is what _run_round calls at
        # round end. Fix F-NEC-1 caps revives at 1/squad/round.
        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertGreater(
            alive_after, 5,
            f"Expected reanimation to revive some warriors; alive count stayed at {alive_after}.",
        )
        # Per Fix F-NEC-1 cap: 1 revive per squad per round.
        self.assertEqual(alive_after, 6)

        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(len(reanim_events), 1, "Expected 1 UnitReanimated event.")
        for ev in reanim_events:
            revived = next(u for u in necrons.units if u.uid == ev.unit_uid)
            self.assertEqual(revived.current_health, 1.0)

    def test_no_revival_without_reanimate_detachment(self):
        """A non-Necron army with no `reanimate_per_round` flag must NOT see
        any dead models flip back to alive."""
        random.seed(0)
        marines = Army("Marines")   # default Gladius — no reanimate
        marines.add_squad(_vanilla_profile("Marine"), 6)
        orks = Army("Orks")
        orks.add_unit(_vanilla_profile("Boy"))

        log = EventLog()
        battle = Battle(marines, orks, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            marines.name: {"Marine": 6},
            orks.name: {"Boy": 1},
        }

        for u in marines.units[:3]:
            u.current_health = 0

        battle._apply_reanimation()

        alive_after = len([u for u in marines.units if u.is_alive])
        self.assertEqual(alive_after, 3, "No detachment flag, no revival.")
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(reanim_events, [])

    def test_revival_caps_at_destroyed_count(self):
        """If only 1 warrior is dead and the death happened this round, we
        revive 1. Per Fix F-NEC-1 the cap is min(destroyed, deaths_this_round, 1).

        Updated: 4 warriors in one codex squad via add_squad."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(_necron_warrior_profile(), 4)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Necron Warrior": 4},
            marines.name: {"Marine": 1},
        }
        # Round-start snapshot: 4 alive. Then we kill 1.
        battle._round_start_alive_counts = {
            necrons.name: {"Necron Warrior": 4},
        }
        necrons.units[0].current_health = 0

        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(alive_after, 4)
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(len(reanim_events), 1)

    def test_no_revival_when_no_deaths_this_round(self):
        """Fix F-NEC-1: a squad with destroyed models from a PREVIOUS round
        but no new deaths this round must NOT reanimate. This is the gate
        that fixes the 'infinite endurance' over-fire in iter-1.

        Updated: 4 warriors in one codex squad via add_squad."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(_necron_warrior_profile(), 4)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Necron Warrior": 4},
            marines.name: {"Marine": 1},
        }
        # Two warriors were killed in a prior round — kill them BEFORE the
        # round-start snapshot is taken, so the snapshot only sees 2 alive.
        necrons.units[0].current_health = 0
        necrons.units[1].current_health = 0
        battle._round_start_alive_counts = {
            necrons.name: {"Necron Warrior": 2},
        }
        # No new deaths this round. Reanimation must NOT fire.
        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(alive_after, 2, "Stable squad must not reanimate.")
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(reanim_events, [], "No fresh deaths -> no UnitReanimated.")

    def test_squad_wipeout_short_circuits_revival(self):
        """10e: once every model in the squad is destroyed, Reanimation
        Protocols no longer apply — there's no surviving model for the rule
        to attach to. Kill ALL 3 Warriors; expect zero UnitReanimated events.

        Updated: 3 warriors in one codex squad via add_squad."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(_necron_warrior_profile(), 3)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Necron Warrior": 3},
            marines.name: {"Marine": 1},
        }
        battle._round_start_alive_counts = {
            necrons.name: {"Necron Warrior": 3},
        }
        for u in necrons.units:
            u.current_health = 0
        self.assertEqual(len([u for u in necrons.units if u.is_alive]), 0)

        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(alive_after, 0, "Wiped squad must not reanimate.")
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(reanim_events, [], "Expected zero UnitReanimated events.")

    def test_no_revival_when_no_dead(self):
        """Healthy army means no UnitReanimated events even with the detachment.

        Updated: 3 warriors in one codex squad via add_squad."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(_necron_warrior_profile(), 3)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Necron Warrior": 3},
            marines.name: {"Marine": 1},
        }

        battle._apply_reanimation()

        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(reanim_events, [])

    def test_revived_multiwound_model_returns_at_full_wounds(self):
        """A destroyed multi-wound NECRONS model (Wraith W3 stand-in)
        reanimates at `profile.health` (full wounds), not 1 HP.

        Iter 14 (`a3798e3`) originally capped revives at 1 HP citing
        a misread of the Wahapedia text. Iter 29-NE1 (`a359520`)
        reverted to full-HP per the verbatim rule: "...one destroyed
        bodyguard model in that unit is returned to your army, with
        its full wounds remaining." See
        https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols
        and the docstring of `_apply_reanimation` in
        `code/simulator.py` (lines 4172-4186).

        Updated: 3 Wraiths in one codex squad via add_squad."""

        def _wraith_profile() -> UnitProfile:
            return UnitProfile(
                name="Canoptek Wraith",
                health=3, damage=1, hit_probability=0.5,
                ap=0, save=3, strength=6, toughness=6,
                attacks=4, weapon_damage_per_shot=1.0, range_inches=12,
                faction="Necrons",
                unit_keywords=("CANOPTEK", "INFANTRY"),
            )

        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(_wraith_profile(), 3)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Canoptek Wraith": 3},
            marines.name: {"Marine": 1},
        }
        battle._round_start_alive_counts = {
            necrons.name: {"Canoptek Wraith": 3},
        }
        # Kill the first Wraith this round (deaths_this_round = 1).
        necrons.units[0].current_health = 0

        battle._apply_reanimation()

        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(len(reanim_events), 1)
        revived = necrons.units[0]
        self.assertEqual(
            revived.current_health, float(revived.profile.health),
            "Revived multi-wound model must come back at full wounds "
            "(iter 29-NE1 revert; see commit a359520 and Wahapedia).",
        )
        self.assertTrue(revived.is_alive)

    def test_cross_squad_isolation_wiped_squad_cannot_borrow_survivors(self):
        """Bug fixed in this wave: two codex squads of the same datasheet
        (e.g., Warriors A and Warriors B) must NOT share a revival pool.

        Scenario: Warriors squad A (squad_id 0) is fully wiped. Warriors
        squad B (squad_id 1) has 3 survivors. Under the old profile.name
        grouping, the dead Warriors from squad A would have borrowed the
        alive anchor from squad B and revived. Under the corrected squad_id
        grouping, squad A's dead pool sees zero alive peers of squad A and
        the wipeout gate fires — no revival from squad A."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        # Squad A: 3 Warriors, all will be wiped.
        necrons.add_squad(_necron_warrior_profile(), 3)
        squad_a_ids = {id(u) for u in necrons.units}
        # Squad B: 3 Warriors, all survive.
        necrons.add_squad(_necron_warrior_profile(), 3)

        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Necron Warrior": 6},
            marines.name: {"Marine": 1},
        }
        battle._round_start_alive_counts = {
            necrons.name: {"Necron Warrior": 6},
        }

        # Wipe squad A entirely.
        for u in necrons.units:
            if id(u) in squad_a_ids:
                u.current_health = 0

        alive_before = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(alive_before, 3, "Squad B survivors must still be alive.")

        battle._apply_reanimation()

        # Squad A is wiped — must NOT revive even though squad B's survivors
        # are alive with the same profile name.
        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(
            alive_after, 3,
            "Wiped squad A must not revive off squad B's survivors.",
        )
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(
            reanim_events, [],
            "No UnitReanimated expected: only source is the wiped squad.",
        )

    def test_two_squads_same_profile_revive_independently(self):
        """Two squads of the same datasheet both lose 1 model this round.
        Each squad revives 1 of its own dead — 2 total revivals (one per
        squad), not 0 (both blocked because pools got cross-merged) or 1
        (old code only revived once per profile)."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        # Squad A: 4 warriors.
        necrons.add_squad(_necron_warrior_profile(), 4)
        squad_a_units = list(necrons.units)
        # Squad B: 4 warriors.
        necrons.add_squad(_necron_warrior_profile(), 4)
        squad_b_units = [u for u in necrons.units if u not in squad_a_units]

        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Necron Warrior": 8},
            marines.name: {"Marine": 1},
        }
        battle._round_start_alive_counts = {
            necrons.name: {"Necron Warrior": 8},
        }

        # Kill 1 from each squad this round.
        squad_a_units[0].current_health = 0
        squad_b_units[0].current_health = 0

        alive_before = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(alive_before, 6)

        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        # Each squad had a fresh death + alive peers, so each revives 1.
        self.assertEqual(
            alive_after, 8,
            "Each squad should independently revive 1 model (2 total).",
        )
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(len(reanim_events), 2, "Expected 2 UnitReanimated events.")


class UndyingLegionsPulseAllocationTests(unittest.TestCase):
    """Fix F-NEC-2 (iter 14): the Undying Legions pulse spends its D3/D3+1
    wound budget per the army-rule allocation (heal damaged models first,
    then revive destroyed models with 1 wound each), NOT '1 model per
    wound at full HP' as the previous implementation did. Critical for
    multi-wound NECRONS units (Wraiths, Lychguard, Skorpekh).

    All tests updated to use add_squad so models of one codex squad share
    a squad_id and the pulse fires within the correct per-squad pool."""

    def _wraith_profile(self) -> UnitProfile:
        return UnitProfile(
            name="Canoptek Wraith",
            health=3, damage=1, hit_probability=0.5,
            ap=0, save=3, strength=6, toughness=6,
            attacks=4, weapon_damage_per_shot=1.0, range_inches=12,
            faction="Necrons",
            unit_keywords=("CANOPTEK", "INFANTRY"),
        )

    def test_pulse_heals_damaged_alive_before_reviving_dead(self):
        """Pulse heals damaged alive peers first before reviving dead ones.
        All 3 Wraiths are in the same codex squad (add_squad size 3)."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(self._wraith_profile(), 3)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Canoptek Wraith": 3},
            marines.name: {"Marine": 1},
        }
        # Damage Wraith #0 to 1 HP (lost 2W); leave #1 and #2 full.
        necrons.units[0].current_health = 1.0
        # Pulse of 2 wounds on the (still-alive) #0 — should top it up
        # rather than revive any dead peer (none dead yet anyway).
        necrons.units[0].transient_undying_legions_pulse = 2

        battle._apply_undying_legions_pulse()

        self.assertEqual(
            necrons.units[0].current_health, 3.0,
            "Pulse must heal the damaged alive Wraith back to full HP first.",
        )
        # No revivals (nobody dead).
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(reanim_events, [])

    def test_pulse_overflow_revives_dead_at_one_wound(self):
        """After healing alive peers, leftover budget revives dead models at
        1 wound each. All 3 Wraiths share a squad_id via add_squad."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(self._wraith_profile(), 3)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Canoptek Wraith": 3},
            marines.name: {"Marine": 1},
        }
        # Dead Wraith + a damaged living peer (1 HP missing).
        necrons.units[0].current_health = 0.0   # destroyed
        necrons.units[1].current_health = 2.0   # 1 wound missing
        # Pulse of 3 wounds -> 1W heals the live peer to full, 2W remain to
        # spend on revival; 1 dead model returns at 1W (no further dead
        # to revive with the extra wound, surplus wasted).
        necrons.units[2].transient_undying_legions_pulse = 3

        battle._apply_undying_legions_pulse()

        self.assertEqual(
            necrons.units[1].current_health, 3.0,
            "Damaged peer must be healed to full first.",
        )
        self.assertEqual(
            necrons.units[0].current_health, 1.0,
            "Revived dead model must come back at 1 wound (not full HP).",
        )
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(len(reanim_events), 1)

    def test_pulse_wipeout_short_circuit(self):
        """If the squad is fully wiped, the pulse does nothing — matches
        the wipeout short-circuit in the regular reanimation pass.
        Both Wraiths share a squad_id via add_squad."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        necrons.add_squad(self._wraith_profile(), 2)
        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Canoptek Wraith": 2},
            marines.name: {"Marine": 1},
        }
        # Wipe everyone. The pulse-carrier (units[0]) is dead too — the
        # pulse loop should skip because no alive peer exists in this squad.
        necrons.units[0].current_health = 0.0
        necrons.units[1].current_health = 0.0
        necrons.units[0].transient_undying_legions_pulse = 3

        battle._apply_undying_legions_pulse()

        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(reanim_events, [])
        self.assertEqual(necrons.units[0].current_health, 0.0)
        self.assertEqual(necrons.units[1].current_health, 0.0)

    def test_pulse_cross_squad_isolation(self):
        """The Undying Legions pulse must NOT revive dead models from a
        different squad. Squad A has a dead Wraith; squad B (same profile)
        carries the pulse and has alive models. The pulse must only look in
        squad B's dead pool (empty) — squad A's dead model must stay dead."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        # Squad A: 2 Wraiths, one will be killed.
        necrons.add_squad(self._wraith_profile(), 2)
        squad_a_units = list(necrons.units)
        # Squad B: 2 Wraiths, both alive, one carries the pulse.
        necrons.add_squad(self._wraith_profile(), 2)
        squad_b_units = [u for u in necrons.units if u not in squad_a_units]

        marines = Army("Marines")
        marines.add_unit(_vanilla_profile("Marine"))

        log = EventLog()
        battle = Battle(necrons, marines, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._initial_unit_counts = {
            necrons.name: {"Canoptek Wraith": 4},
            marines.name: {"Marine": 1},
        }

        # Kill one Wraith from squad A.
        squad_a_units[0].current_health = 0.0
        # Pulse is on squad B's first model.
        squad_b_units[0].transient_undying_legions_pulse = 3

        battle._apply_undying_legions_pulse()

        # Squad A's dead Wraith must remain dead — squad B's pulse only
        # draws from squad B's (empty) dead pool.
        self.assertEqual(
            squad_a_units[0].current_health, 0.0,
            "Squad A dead Wraith must not be revived by squad B's pulse.",
        )
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(
            reanim_events, [],
            "No revivals expected: dead model is in a different squad.",
        )


if __name__ == "__main__":
    unittest.main()
