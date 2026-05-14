"""Tests for issue #75 — Reanimation Protocols proper model revival.

The old `reanimate_per_round` flag on the Necron `Awakened Dynasty` detachment
used to heal +1 HP on living units at end of round. 10e Reanimation Protocols
actually revives DESTROYED models — that's the new behaviour these tests pin.

Squads are modelled as N single-model Unit instances, so "revive a destroyed
model" means flipping a dead Unit (current_health=0) back to alive with full HP.
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
        alive count to go UP — not stay flat. Median D3 = 2 revives per
        profile per round, so 5 alive -> 7 alive is the expected step."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        for _ in range(10):
            necrons.add_unit(_necron_warrior_profile())
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

        # Kill 5 warriors by zeroing their HP directly. They sit at the
        # standard deployment line so the revival anchor (their living
        # peers) is well-defined.
        for u in necrons.units[:5]:
            u.current_health = 0
        self.assertEqual(len([u for u in necrons.units if u.is_alive]), 5)

        # Invoke reanimation directly — this is what _run_round calls at
        # round end. Median D3 = 2 means we revive exactly 2.
        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertGreater(
            alive_after, 5,
            f"Expected reanimation to revive some warriors; alive count stayed at {alive_after}.",
        )
        # Specifically: median D3 = 2 means we should see 7 alive.
        self.assertEqual(alive_after, 7)

        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(len(reanim_events), 2, "Expected 2 UnitReanimated events.")
        # Revived units should be at full HP.
        for ev in reanim_events:
            revived = next(u for u in necrons.units if u.uid == ev.unit_uid)
            self.assertEqual(revived.current_health, revived.profile.health)

    def test_no_revival_without_reanimate_detachment(self):
        """A non-Necron army with no `reanimate_per_round` flag must NOT see
        any dead models flip back to alive."""
        random.seed(0)
        marines = Army("Marines")   # default Gladius — no reanimate
        for _ in range(6):
            marines.add_unit(_vanilla_profile("Marine"))
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
        """If only 1 warrior is dead, we revive 1 — not 2 (median D3)."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        for _ in range(4):
            necrons.add_unit(_necron_warrior_profile())
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
        necrons.units[0].current_health = 0

        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(alive_after, 4)
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(len(reanim_events), 1)

    def test_squad_wipeout_short_circuits_revival(self):
        """10e: once every model in the squad is destroyed, Reanimation
        Protocols no longer apply — there's no surviving model for the rule
        to attach to. Kill ALL 3 Warriors; expect zero UnitReanimated events."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        for _ in range(3):
            necrons.add_unit(_necron_warrior_profile())
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
        for u in necrons.units:
            u.current_health = 0
        self.assertEqual(len([u for u in necrons.units if u.is_alive]), 0)

        battle._apply_reanimation()

        alive_after = len([u for u in necrons.units if u.is_alive])
        self.assertEqual(alive_after, 0, "Wiped squad must not reanimate.")
        reanim_events = [e for e in log.events if isinstance(e, UnitReanimated)]
        self.assertEqual(reanim_events, [], "Expected zero UnitReanimated events.")

    def test_no_revival_when_no_dead(self):
        """Healthy army means no UnitReanimated events even with the detachment."""
        random.seed(0)
        necrons = Army("Necrons", detachment=AWAKENED_DYNASTY)
        for _ in range(3):
            necrons.add_unit(_necron_warrior_profile())
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


if __name__ == "__main__":
    unittest.main()
