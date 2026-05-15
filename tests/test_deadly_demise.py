"""Tests for Deadly Demise X (10e core rule).

When a model with this ability is destroyed, roll 1D6 BEFORE removing it from
the battlefield. On a 6, each unit within 6" suffers X mortal wounds.

SwegHammer collapses the codex D3 / D6 / D3+3 / integer variants to a fixed
integer expected value at mapper time (D3->2, D6->3, D3+3->5, N->N) so the
runtime sees a single integer; the 1-in-6 trigger rate is preserved.

Cited as `simulator.deadly_demise`.
"""

from __future__ import annotations

import random
import unittest
from unittest import mock

from code.army import Army
from code.events import DeadlyDemiseExploded, EventLog
from code.simulator import Battle
from code.units import UNIT_CATALOG, UnitProfile


def _trooper(name: str = "Trooper", faction: str = "Adeptus Astartes") -> UnitProfile:
    """A vanilla 1-wound profile used as a victim of Deadly Demise."""
    return UnitProfile(
        name=name, faction=faction,
        health=5, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
    )


def _bomb_unit(dd_value: int = 3, name: str = "Bomb") -> UnitProfile:
    """A profile that detonates on death with deadly_demise=dd_value."""
    return UnitProfile(
        name=name, faction="Test Faction",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        deadly_demise=dd_value,
    )


def _new_battle() -> tuple[Battle, Army, Army, EventLog]:
    """Spin up a minimal Battle with both armies populated, but skip the
    run loop so tests can drive the demise hook by hand."""
    a = Army("A")
    b = Army("B")
    log = EventLog()
    battle = Battle(a, b, subscribers=[log])
    return battle, a, b, log


class DeadlyDemiseMapperTests(unittest.TestCase):
    """Spot-check that the BSData mapper actually populates `deadly_demise`
    for canonical vehicle / monster datasheets."""

    def test_dd_field_parsed_from_bsdata(self):
        keys = [
            "space_marines_repulsor",
            "necrons_doomsday_ark",
            "adeptus_custodes_caladius_grav_tank",
        ]
        for k in keys:
            self.assertIn(k, UNIT_CATALOG, f"{k} missing from catalog")
            p = UNIT_CATALOG[k]
            self.assertGreater(
                p.deadly_demise, 0,
                f"{k} expected deadly_demise > 0, got {p.deadly_demise}",
            )

    def test_dd_zero_for_infantry(self):
        """Infantry stand-ins must not pick up DD by accident."""
        for k, p in UNIT_CATALOG.items():
            if "tactical_squad" in k:
                self.assertEqual(
                    p.deadly_demise, 0,
                    f"{k} should not have deadly_demise; got {p.deadly_demise}",
                )
                break


class DeadlyDemiseSimulatorTests(unittest.TestCase):

    def test_dd_triggers_on_6(self):
        """Synthetic dying unit with deadly_demise=3, enemy within 6",
        seeded d6=6 -> 3 mortals applied."""
        battle, a, b, log = _new_battle()
        a.add_unit(_bomb_unit(3, "Bomb"))
        b.add_unit(_trooper("Victim"))
        battle._assign_uids()
        # Position: bomb at (10, 10), victim at (15, 10) -> 5" away (within 6")
        a.units[0].position = (10.0, 10.0)
        b.units[0].position = (15.0, 10.0)
        # Kill the bomb manually so demise can fire on a clean death.
        a.units[0].current_health = 0.0
        victim_hp_before = b.units[0].current_health
        with mock.patch("code.simulator.random.randint", return_value=6):
            battle._maybe_apply_deadly_demise(a.units[0])
        # 3 mortal wounds dealt (FNP=7, so all 3 land)
        self.assertEqual(
            b.units[0].current_health, victim_hp_before - 3.0,
            "Victim should have lost exactly 3 mortal wounds.",
        )

    def test_dd_no_trigger_below_6(self):
        """Same setup as the positive test but d6 in 1..5 — no mortals."""
        for roll in (1, 2, 3, 4, 5):
            battle, a, b, log = _new_battle()
            a.add_unit(_bomb_unit(3, "Bomb"))
            b.add_unit(_trooper("Victim"))
            battle._assign_uids()
            a.units[0].position = (10.0, 10.0)
            b.units[0].position = (15.0, 10.0)
            a.units[0].current_health = 0.0
            hp_before = b.units[0].current_health
            with mock.patch("code.simulator.random.randint", return_value=roll):
                battle._maybe_apply_deadly_demise(a.units[0])
            self.assertEqual(
                b.units[0].current_health, hp_before,
                f"roll={roll}: no mortals expected; HP changed.",
            )

    def test_dd_only_within_6_inches(self):
        """Enemy positioned at 7" — even on d6=6, no mortals applied."""
        battle, a, b, log = _new_battle()
        a.add_unit(_bomb_unit(3, "Bomb"))
        b.add_unit(_trooper("FarVictim"))
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        b.units[0].position = (17.0, 10.0)   # 7" away
        a.units[0].current_health = 0.0
        hp_before = b.units[0].current_health
        with mock.patch("code.simulator.random.randint", return_value=6):
            battle._maybe_apply_deadly_demise(a.units[0])
        self.assertEqual(
            b.units[0].current_health, hp_before,
            "Enemy beyond 6\" must not take demise mortals.",
        )

    def test_dd_event_emitted(self):
        """A DeadlyDemiseExploded event lands in the log on a successful trigger."""
        battle, a, b, log = _new_battle()
        a.add_unit(_bomb_unit(2, "Bomb"))
        b.add_unit(_trooper("V1"))
        b.add_unit(_trooper("V2"))
        battle._assign_uids()
        a.units[0].position = (20.0, 20.0)
        b.units[0].position = (22.0, 20.0)   # 2"
        b.units[1].position = (25.0, 20.0)   # 5"
        a.units[0].current_health = 0.0
        with mock.patch("code.simulator.random.randint", return_value=6):
            battle._maybe_apply_deadly_demise(a.units[0])
        evs = [e for e in log.events if isinstance(e, DeadlyDemiseExploded)]
        self.assertEqual(len(evs), 1, "Expected exactly one DeadlyDemiseExploded event.")
        ev = evs[0]
        self.assertEqual(ev.unit_uid, a.units[0].uid)
        self.assertEqual(ev.mortals, 2)
        self.assertEqual(set(ev.victims), {b.units[0].uid, b.units[1].uid})

    def test_non_dd_unit_does_not_trigger(self):
        """A unit with deadly_demise=0 must NOT roll a d6 or apply mortals."""
        battle, a, b, log = _new_battle()
        a.add_unit(_bomb_unit(0, "Inert"))   # NB: deadly_demise=0
        b.add_unit(_trooper("Bystander"))
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        b.units[0].position = (10.5, 10.0)
        a.units[0].current_health = 0.0
        hp_before = b.units[0].current_health
        # Patch randint to RAISE — proves we never roll.
        with mock.patch(
            "code.simulator.random.randint",
            side_effect=AssertionError("must not roll for non-DD unit"),
        ):
            battle._maybe_apply_deadly_demise(a.units[0])
        self.assertEqual(b.units[0].current_health, hp_before)
        evs = [e for e in log.events if isinstance(e, DeadlyDemiseExploded)]
        self.assertEqual(evs, [])

    def test_dd_hits_both_armies(self):
        """A demise blast catches friendly AND enemy units within 6"."""
        battle, a, b, log = _new_battle()
        a.add_unit(_bomb_unit(1, "Bomb"))
        a.add_unit(_trooper("Friend"))
        b.add_unit(_trooper("Foe"))
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (13.0, 10.0)   # friendly, 3" away
        b.units[0].position = (12.0, 10.0)   # enemy, 2" away
        a.units[0].current_health = 0.0
        friend_hp = a.units[1].current_health
        foe_hp = b.units[0].current_health
        with mock.patch("code.simulator.random.randint", return_value=6):
            battle._maybe_apply_deadly_demise(a.units[0])
        self.assertEqual(a.units[1].current_health, friend_hp - 1.0)
        self.assertEqual(b.units[0].current_health, foe_hp - 1.0)


if __name__ == "__main__":
    unittest.main()
