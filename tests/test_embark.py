"""EMBARK-V1 tests — the minimum 10e core embark / disembark contract.

This file complements `tests/test_transports.py` (the broader Transport
suite). EMBARK-V1 is the structural fix for the simulator gap acknowledged
in the prior detachments.py / archetypes.py comments — every cited rule
here was implemented in commit c84e4db (#156) and audited again in this
wave (2026-05-28).

Tests required by the EMBARK-V1 spec:

  1. A passenger embarked in a transport at deploy time has `is_embarked`
     True and `embarked_in` pointing at the carrier.
  2. An embarked unit's attack pipeline is a no-op — _do_shoot,
     _do_charge, and _do_fight all return early when the attacker is
     embarked.
  3. After voluntary disembark, the unit is no longer embarked (so its
     `is_embarked` reads False) and a subsequent Unit.attack call (the
     simulator's shoot helper) produces non-zero expected damage.
  4. When the transport is destroyed, every passenger is placed within
     3" of the transport's last position and the `embarked_in` back-
     pointer is cleared.

Cited as `simulator.embark`, `simulator.disembark`,
`simulator.destroyed_transport`.
"""

from __future__ import annotations

import unittest
from unittest import mock

from code.army import Army
from code.events import EventLog
from code.simulator import Battle
from code.units import UnitProfile


def _transport_profile(name: str = "Test Transport") -> UnitProfile:
    """A vanilla TRANSPORT chassis (VEHICLE + TRANSPORT keywords).

    Faction is left as Adeptus Astartes so the embark eligibility check
    (which prefers same-army INFANTRY passengers) lights up against the
    paired _infantry_profile below.
    """
    return UnitProfile(
        name=name, faction="Adeptus Astartes",
        health=10, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=6, toughness=9,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        move=12.0, unit_keywords=("VEHICLE", "TRANSPORT"),
    )


def _infantry_profile(name: str = "Test Trooper") -> UnitProfile:
    """A vanilla INFANTRY passenger profile.

    Carries ranged + melee statlines so the no-op tests in #2 can verify
    BOTH gates (the shoot gate AND the fight gate) trigger when the unit
    is embarked. `save=7` (no save) makes the damage easy to verify in #3
    when the mocked dice all land on 6.
    """
    return UnitProfile(
        name=name, faction="Adeptus Astartes",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=7, strength=4, toughness=4,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        # Melee profile so _do_fight has something to resolve once the
        # embark gate is lifted.
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        move=6.0, unit_keywords=("INFANTRY",),
    )


def _enemy_profile(name: str = "Test Enemy") -> UnitProfile:
    """A high-HP brick on the opposing side — used as the target of every
    attack-pipeline test. Healthy enough that mocked-6 dice still leave
    it alive, so we can assert HP-changed deltas rather than is_alive
    transitions.
    """
    return UnitProfile(
        name=name, faction="Test",
        health=200, damage=1, hit_probability=0.5,
        ap=0, save=7, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        unit_keywords=("INFANTRY",),
    )


def _new_battle() -> tuple:
    """Build a fresh Battle with one army on each side and the event log
    wired as a subscriber so emitted events can be asserted in tests.
    """
    a = Army("A")
    b = Army("B")
    log = EventLog()
    battle = Battle(a, b, subscribers=[log])
    return battle, a, b, log


class EmbarkV1Tests(unittest.TestCase):
    """Minimum-contract embark / disembark tests for EMBARK-V1.

    These four tests verify the structural fix listed in the EMBARK-V1
    spec — every test should pass once the simulator has an embark /
    disembark cycle, which is the post-#156 state of the worktree as of
    2026-05-28.
    """

    def _setup_embarked(self):
        """Shared fixture: one transport with one embarked passenger on
        the A side, one enemy on the B side, all positioned in the same
        small box so range / engagement checks pass. Returns the Battle
        plus the three Unit handles.
        """
        battle, a, b, log = _new_battle()
        a.add_unit(_transport_profile())
        a.add_unit(_infantry_profile())
        b.add_unit(_enemy_profile())
        battle._assign_uids()
        # Co-locate transport + passenger so the pre-game embark routine
        # picks the passenger up. Enemy sits in shoot range of both.
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (12.0, 10.0)   # 2" away — engaged on melee
        battle._embark_pregame_passengers()
        return battle, a, b, log, a.units[0], a.units[1], b.units[0]

    # ------------------------------------------------------------------
    # Test 1 — Embarked at deploy
    # ------------------------------------------------------------------
    def test_passenger_embarked_at_deploy(self):
        """A co-located INFANTRY unit must end up embarked after the
        pre-game embark pass runs at the end of deployment.

        Spec leg: "Drukhari Kabalite embarked in Venom at deploy:
        is_embarked True". The spec phrasing names a Drukhari example,
        but the rule is faction-neutral — every TRANSPORT carries
        passengers via the same Wahapedia core path. We use the generic
        Adeptus Astartes Rhino-tier fixtures here to keep the test
        independent of the Drukhari codex data.
        """
        _battle, _a, _b, _log, transport, passenger, _enemy = (
            self._setup_embarked()
        )
        self.assertTrue(
            passenger.is_embarked,
            "passenger.is_embarked must be True after pre-game embark",
        )
        self.assertIs(
            passenger.embarked_in, transport,
            "passenger.embarked_in must point at the carrier transport",
        )
        self.assertIn(
            passenger, transport.passengers,
            "transport.passengers must contain the embarked passenger",
        )

    # ------------------------------------------------------------------
    # Test 2 — Embarked attack gates are no-ops
    # ------------------------------------------------------------------
    def test_embarked_unit_attack_pipeline_is_noop(self):
        """While embarked, the passenger's _do_shoot / _do_charge /
        _do_fight gates must all early-return without applying any
        damage to the enemy.

        Spec leg: "embarked unit's _do_shoot / _do_charge / _do_fight
        is a no-op".
        """
        battle, a, b, _log, _transport, passenger, enemy = (
            self._setup_embarked()
        )
        hp_before = enemy.current_health
        # Force every per-attack die to land on 6 — if any of the three
        # gates leaks through, the enemy's HP will visibly drop. The
        # mock covers both the simulator-side rolls and the per-attack
        # rolls inside Unit.attack.
        with (
            mock.patch("code.simulator.random.randint", return_value=6),
            mock.patch("code.units.random.randint", return_value=6),
        ):
            battle._do_shoot(passenger, a, b)
            battle._do_charge(passenger, a, b)
            battle._do_fight(passenger, a, b)
        self.assertEqual(
            enemy.current_health, hp_before,
            "Embarked passenger should not have damaged the enemy via "
            "any of shoot / charge / fight",
        )

    # ------------------------------------------------------------------
    # Test 3 — After disembark the unit can shoot
    # ------------------------------------------------------------------
    def test_after_disembark_unit_can_shoot(self):
        """Once the passenger disembarks, `is_embarked` flips to False
        and the next Unit.attack call lands real damage.

        Spec leg: "after disembark turn 1: can shoot". We call
        Unit.attack() directly (not _do_shoot) because _do_shoot is
        constrained by the disembark-turn movement lockout — the rule-
        correct lockout blocks the unit's own movement, not its
        shooting. The disembarked unit may still shoot in the same turn
        (10e core: disembark forbids the Normal / Advance / Fall Back
        move only). Unit.attack() exercises the same damage pipeline
        that _do_shoot calls into, with no movement gate.
        """
        battle, _a, _b, _log, transport, passenger, enemy = (
            self._setup_embarked()
        )
        # Sanity: still embarked before disembark.
        self.assertTrue(passenger.is_embarked)
        # Manually voluntary-disembark.
        battle._disembark(passenger, transport, forced=False)
        self.assertFalse(
            passenger.is_embarked,
            "passenger.is_embarked must be False after disembark",
        )
        self.assertIsNone(passenger.embarked_in)
        self.assertNotIn(passenger, transport.passengers)
        # Roll a 6 on every die — guarantees a hit, a wound, and a
        # failed save (target save=7 means no save anyway). One
        # weapon_damage_per_shot * 4 attacks worth of damage should
        # land on the enemy.
        hp_before = enemy.current_health
        with mock.patch("code.units.random.randint", return_value=6):
            dealt = passenger.attack(
                enemy,
                distance=2.0,
                mode="ranged",
                has_los=True,
            )
        self.assertGreater(
            dealt, 0.0,
            "Disembarked passenger's shooting attack should deal damage",
        )
        self.assertLess(
            enemy.current_health, hp_before,
            "Enemy HP should have dropped after disembarked unit shot it",
        )

    # ------------------------------------------------------------------
    # Test 4 — Transport destroyed places cargo at transport position
    # ------------------------------------------------------------------
    def test_transport_destroyed_places_cargo_within_three_inches(self):
        """When the carrier dies with passengers aboard, every passenger
        must be force-disembarked: placed within 3" of the transport's
        last position, `is_embarked` False, and removed from the
        transport's passengers list.

        Spec leg: "transport destroyed: cargo placed at transport
        position, not embarked". The destroyed-transport disembark path
        also rolls 1 D6 per surviving passenger model with a 1 destroying
        the model — we pin the D6 to 6 here to isolate the placement /
        unembark contract from the model-loss side-channel (the model-
        loss leg is covered by `test_transports.py
        ::DestroyedTransportTests::test_destroyed_transport_d6_mortal
        _per_model_on_1`).
        """
        battle, _a, _b, _log, transport, passenger, _enemy = (
            self._setup_embarked()
        )
        last_pos = transport.position
        # Kill the transport.
        transport.current_health = 0.0
        # Force the disembark D6 to a 6 — no model loss, just clean
        # placement.
        with mock.patch("code.simulator.random.randint", return_value=6):
            battle._maybe_apply_deadly_demise(transport)
        # Passenger must no longer be embarked.
        self.assertFalse(
            passenger.is_embarked,
            "passenger.is_embarked must be False once the carrier dies",
        )
        self.assertIsNone(passenger.embarked_in)
        self.assertNotIn(passenger, transport.passengers)
        # Placement: within 3" of the transport's last position.
        dx = passenger.position[0] - last_pos[0]
        dy = passenger.position[1] - last_pos[1]
        d = (dx * dx + dy * dy) ** 0.5
        self.assertLessEqual(
            d, 3.0 + 1e-6,
            f"Force-disembark placement {d:.2f}\" exceeds the 3\" cap",
        )


if __name__ == "__main__":
    unittest.main()
