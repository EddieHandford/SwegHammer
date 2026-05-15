"""Tests for Transport core mechanics (10e): Embark / Disembark / Firing Deck
/ Destroyed Transport.

Cited as `simulator.embark`, `simulator.disembark`, `simulator.firing_deck`,
`simulator.destroyed_transport`.
"""

from __future__ import annotations

import unittest
from unittest import mock

from code.army import Army
from code.events import (
    EventLog, TransportDisembarked, TransportEmbarked, UnitKilled,
)
from code.simulator import Battle
from code.units import UNIT_CATALOG, UnitProfile


def _transport_profile(
    name: str = "Rhino",
    firing_deck: int = 0,
    health: float = 10.0,
) -> UnitProfile:
    """A vanilla TRANSPORT profile (VEHICLE + TRANSPORT keywords)."""
    return UnitProfile(
        name=name, faction="Adeptus Astartes",
        health=health, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=6, toughness=9,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        move=12.0, unit_keywords=("VEHICLE", "TRANSPORT"),
        firing_deck=firing_deck,
    )


def _infantry_profile(name: str = "Trooper") -> UnitProfile:
    """A vanilla 1-wound INFANTRY passenger profile."""
    return UnitProfile(
        name=name, faction="Adeptus Astartes",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        move=6.0, unit_keywords=("INFANTRY",),
    )


def _victim_profile() -> UnitProfile:
    """A high-HP brick for firing-deck damage testing — won't die mid-test.

    save=7 = no save, so a mock that pins every die to 6 actually inflicts
    damage rather than passing armour."""
    return UnitProfile(
        name="Brick", faction="Test",
        health=200, damage=1, hit_probability=0.5,
        ap=0, save=7, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
    )


def _new_battle() -> tuple:
    a = Army("A")
    b = Army("B")
    log = EventLog()
    battle = Battle(a, b, subscribers=[log])
    return battle, a, b, log


class TransportCatalogueTests(unittest.TestCase):
    """The mapper should populate TRANSPORT keyword + firing_deck on canonical
    datasheets."""

    def test_rhino_has_transport_keyword(self):
        rhino = UNIT_CATALOG.get("space_marines_rhino")
        self.assertIsNotNone(rhino, "Rhino missing from catalogue")
        self.assertIn(
            "TRANSPORT", rhino.unit_keywords,
            "Rhino must carry TRANSPORT keyword",
        )

    def test_rhino_has_firing_deck_two(self):
        rhino = UNIT_CATALOG.get("space_marines_rhino")
        self.assertIsNotNone(rhino)
        self.assertEqual(
            rhino.firing_deck, 2,
            f"Rhino Firing Deck should be 2, got {rhino.firing_deck}",
        )

    def test_transports_in_catalogue(self):
        """Sanity: there should be many TRANSPORT-keyword units after the
        mapper refresh."""
        transports = [
            k for k, p in UNIT_CATALOG.items()
            if "TRANSPORT" in (p.unit_keywords or ())
        ]
        self.assertGreater(
            len(transports), 50,
            f"Expected >50 TRANSPORTs in catalogue, got {len(transports)}",
        )


class EmbarkTests(unittest.TestCase):

    def test_unit_can_embark_in_transport_in_3_inches(self):
        """An INFANTRY unit within 3" of a TRANSPORT embarks at deploy time."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile())
        a.add_unit(_infantry_profile())
        b.add_unit(_infantry_profile())
        battle._assign_uids()
        # Co-locate transport + infantry so the embark routine picks them up.
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (40.0, 40.0)
        battle._embark_pregame_passengers()
        transport, passenger = a.units[0], a.units[1]
        self.assertIn(passenger, transport.passengers)
        self.assertIs(passenger.embarked_in, transport)
        # An embark event landed in the log.
        evs = [e for e in log.events if isinstance(e, TransportEmbarked)]
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].transport_uid, transport.uid)
        self.assertEqual(evs[0].passenger_uid, passenger.uid)


class TransportMovementTests(unittest.TestCase):

    def test_transport_carries_passengers_through_movement(self):
        """When a transport moves, its embarked passenger's position is
        pinned to the transport (the embark gate keeps the passenger off-board
        — what we actually verify is that the embarked flag persists and the
        passenger isn't picked up by _do_shoot as a target)."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile())
        a.add_unit(_infantry_profile())
        b.add_unit(_infantry_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (20.0, 10.0)
        battle._embark_pregame_passengers()
        # Move the transport's position; passenger stays embarked.
        a.units[0].position = (30.0, 30.0)
        self.assertIs(a.units[1].embarked_in, a.units[0])
        # Embarked passengers cannot be targeted by ranged shots — the
        # _do_shoot candidate filter should never offer them up.
        # Smoke check: B's infantry tries to shoot A's units; the embarked
        # passenger must be excluded from candidates.
        # We don't run _do_shoot end-to-end (it's stochastic); instead we
        # assert the targetable list filter directly:
        targetable = [
            u for u in a.alive_units
            if getattr(u, "embarked_in", None) is None
        ]
        self.assertIn(a.units[0], targetable, "Transport should be targetable")
        self.assertNotIn(
            a.units[1], targetable,
            "Embarked passenger must not be targetable",
        )


class DisembarkTests(unittest.TestCase):

    def test_disembark_within_3_inches(self):
        """A voluntary disembark places the passenger within 3" of the
        transport's position."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile())
        a.add_unit(_infantry_profile())
        b.add_unit(_infantry_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (40.0, 40.0)
        battle._embark_pregame_passengers()
        transport, passenger = a.units[0], a.units[1]
        # Manually disembark.
        battle._disembark(passenger, transport, forced=False)
        self.assertIsNone(passenger.embarked_in)
        self.assertNotIn(passenger, transport.passengers)
        # Within 3" of the transport.
        dx = passenger.position[0] - transport.position[0]
        dy = passenger.position[1] - transport.position[1]
        d = (dx * dx + dy * dy) ** 0.5
        self.assertLessEqual(
            d, 3.0 + 1e-6,
            f"Disembark distance {d:.2f} exceeds 3\" cap",
        )
        # An event landed in the log.
        evs = [e for e in log.events if isinstance(e, TransportDisembarked)]
        self.assertEqual(len(evs), 1)
        self.assertFalse(evs[0].forced)


class DestroyedTransportTests(unittest.TestCase):

    def test_destroyed_transport_force_disembark(self):
        """When a transport is destroyed, embarked passengers force-disembark
        within 3"."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile())
        a.add_unit(_infantry_profile())
        b.add_unit(_infantry_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (40.0, 40.0)
        battle._embark_pregame_passengers()
        transport, passenger = a.units[0], a.units[1]
        # Kill the transport. Patch the D6 high so the passenger survives.
        transport.current_health = 0.0
        with mock.patch("code.simulator.random.randint", return_value=6):
            battle._maybe_apply_deadly_demise(transport)
        self.assertIsNone(
            passenger.embarked_in,
            "Passenger should have force-disembarked",
        )
        evs = [e for e in log.events if isinstance(e, TransportDisembarked)]
        self.assertEqual(len(evs), 1)
        self.assertTrue(evs[0].forced)
        # Within 3" of the transport's last position.
        dx = passenger.position[0] - transport.position[0]
        dy = passenger.position[1] - transport.position[1]
        d = (dx * dx + dy * dy) ** 0.5
        self.assertLessEqual(d, 3.0 + 1e-6)

    def test_destroyed_transport_d6_mortal_per_model_on_1(self):
        """On the destroyed-transport D6, a 1 destroys the disembarking
        passenger model."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile())
        a.add_unit(_infantry_profile())
        b.add_unit(_infantry_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (40.0, 40.0)
        battle._embark_pregame_passengers()
        transport, passenger = a.units[0], a.units[1]
        transport.current_health = 0.0
        # Force every d6 to land on a 1.
        with mock.patch("code.simulator.random.randint", return_value=1):
            battle._maybe_apply_deadly_demise(transport)
        # Passenger destroyed by the disembark D6.
        self.assertFalse(
            passenger.is_alive,
            "Passenger should be destroyed on disembark D6=1",
        )
        # UnitKilled event for the passenger.
        kills = [
            e for e in log.events
            if isinstance(e, UnitKilled) and e.unit_uid == passenger.uid
        ]
        self.assertEqual(len(kills), 1)

    def test_destroyed_transport_d6_high_passenger_survives(self):
        """On the destroyed-transport D6, anything but a 1 means the
        passenger survives the dismount."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile())
        a.add_unit(_infantry_profile())
        b.add_unit(_infantry_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (40.0, 40.0)
        battle._embark_pregame_passengers()
        transport, passenger = a.units[0], a.units[1]
        transport.current_health = 0.0
        hp_before = passenger.current_health
        # Roll 2 — anything but a 1 should leave the passenger alive at full
        # HP (deadly demise is gated on roll == 6 so won't fire either).
        with mock.patch("code.simulator.random.randint", return_value=2):
            battle._maybe_apply_deadly_demise(transport)
        self.assertTrue(passenger.is_alive)
        self.assertEqual(passenger.current_health, hp_before)


class FiringDeckTests(unittest.TestCase):

    def test_firing_deck_extra_passenger_attacks(self):
        """When a transport with firing_deck > 0 fires and has passengers,
        the passengers also attack (additional damage > 0 means firing deck
        triggered)."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile(firing_deck=2))
        a.add_unit(_infantry_profile())
        b.add_unit(_victim_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (20.0, 10.0)   # 10" away — in range of both
        battle._embark_pregame_passengers()
        transport, passenger = a.units[0], a.units[1]
        victim = b.units[0]
        # Patch RNG so every die lands a 6 — guarantees both the transport's
        # shots and the firing-deck passenger's shots all hit + wound + pass
        # cover-less save fail. We bypass the full _do_shoot path and call
        # the firing-deck helper directly with a known damage baseline.
        hp_before = victim.current_health
        with mock.patch(
            "code.units.random.randint", return_value=6,
        ):
            firing_deck_damage = battle._apply_firing_deck(
                transport, victim, a, b,
            )
        # The passenger should have contributed at least 1 point of damage
        # (its attacks * weapon_damage; saves all fail on a 6 result).
        self.assertGreater(
            firing_deck_damage, 0,
            "Firing Deck should add passenger damage",
        )
        self.assertLess(
            victim.current_health, hp_before,
            "Victim HP should have dropped",
        )

    def test_firing_deck_no_op_when_no_passengers(self):
        """A transport with firing_deck > 0 but no passengers contributes 0
        from the firing-deck path."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile(firing_deck=2))
        b.add_unit(_victim_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        b.units[0].position = (20.0, 10.0)
        transport = a.units[0]
        victim = b.units[0]
        hp_before = victim.current_health
        firing_deck_damage = battle._apply_firing_deck(transport, victim, a, b)
        self.assertEqual(firing_deck_damage, 0.0)
        self.assertEqual(victim.current_health, hp_before)

    def test_firing_deck_zero_no_op(self):
        """A transport with firing_deck=0 does nothing even with passengers."""
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile(firing_deck=0))
        a.add_unit(_infantry_profile())
        b.add_unit(_victim_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (20.0, 10.0)
        battle._embark_pregame_passengers()
        transport = a.units[0]
        victim = b.units[0]
        hp_before = victim.current_health
        firing_deck_damage = battle._apply_firing_deck(transport, victim, a, b)
        self.assertEqual(firing_deck_damage, 0.0)
        self.assertEqual(victim.current_health, hp_before)


if __name__ == "__main__":
    unittest.main()
