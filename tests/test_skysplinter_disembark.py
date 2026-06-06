"""DRK-SKYSPLINTER-DISEMBARK tests — Skysplinter Assault detachment
Rain of Cruelty disembark-turn LANCE + IGNORES COVER wiring.

Real 10e codex text (Wahapedia, Drukhari Skysplinter Assault):
  "Each time a DRUKHARI unit from your army disembarks from a TRANSPORT,
  until the end of the turn, ranged weapons equipped by models in that
  unit have the [IGNORES COVER] ability and melee weapons equipped by
  models in that unit have the [LANCE] ability."

Wave 45 wiring lives in two places:
  * `simulator._disembark` sets `transient_lance_this_turn` and
    `transient_ignores_cover_this_turn` on the passenger when the
    passenger is Drukhari AND the army's detachment is Skysplinter
    Assault.
  * `simulator._clear_transient_stratagem_flags` clears both flags at
    the next round start (matches the "until the end of the turn"
    wording).
  * `Unit.attack` composes the LANCE flag via OR with `profile.lance`
    at the lance eligibility gate (still gated on `is_charging`
    because LANCE itself only fires on the charge turn) and composes
    the IGNORES COVER flag via OR with `profile.ignores_cover` at the
    ranged ignore_cover gate.

These tests cover three legs:

  1. Disembarking a Drukhari unit while the army's detachment is
     Skysplinter Assault sets both transient flags True (and the same
     disembark with a non-Drukhari unit or a non-Skysplinter detachment
     leaves the flags False).
  2. With the transient flags set, the attack pipeline picks up the
     keyword grants — IGNORES COVER bypasses the target's Benefits of
     Cover save bonus on a ranged attack; LANCE adds +1 to wound on a
     melee attack made on a turn the bearer's unit declared a charge.
  3. The flags clear at the next round start via the standard
     transient-flag reset.

Cited as `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark` /
`simulator.skysplinter_rain_of_cruelty`.
"""

from __future__ import annotations

import unittest
from unittest import mock

from code.army import Army
from code.detachments import SKYSPLINTER_ASSAULT, KABALITE_CARTEL
from code.events import EventLog
from code.simulator import Battle
from code.units import UnitProfile


def _drukhari_transport_profile(name: str = "Test Venom") -> UnitProfile:
    """A Drukhari transport stand-in (VEHICLE + TRANSPORT)."""
    return UnitProfile(
        name=name, faction="Drukhari",
        health=10, damage=2, hit_probability=2 / 3,
        ap=-1, save=4, strength=6, toughness=6,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        move=14.0, unit_keywords=("VEHICLE", "TRANSPORT"),
    )


def _drukhari_passenger_profile(name: str = "Test Kabalite") -> UnitProfile:
    """A Drukhari passenger (INFANTRY) profile with both ranged + melee
    so we can exercise the IGNORES COVER and LANCE legs independently."""
    return UnitProfile(
        name=name, faction="Drukhari",
        health=10, damage=1, hit_probability=2 / 3,
        ap=0, save=5, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        move=6.0, unit_keywords=("INFANTRY",),
    )


def _non_drukhari_passenger_profile() -> UnitProfile:
    """An Adeptus Astartes passenger profile — same shape as the Drukhari
    one but a different faction, used to assert the Drukhari faction gate
    on the disembark hook."""
    return UnitProfile(
        name="Test Marine", faction="Adeptus Astartes",
        health=10, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        move=6.0, unit_keywords=("INFANTRY",),
    )


def _enemy_profile(in_cover: bool = False, save: int = 5) -> UnitProfile:
    """High-HP target. `save` controls how much room cover has to make
    the save easier — save 5 + cover = save 4, leaving headroom for the
    IGNORES COVER bypass to bite. INFANTRY keyword so the cover cap
    rules engage."""
    return UnitProfile(
        name="Test Enemy", faction="Test",
        health=200, damage=1, hit_probability=0.5,
        ap=0, save=save, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        unit_keywords=("INFANTRY",),
    )


def _new_battle(detachment) -> tuple:
    a = Army("A")
    a.detachment = detachment
    b = Army("B")
    log = EventLog()
    battle = Battle(a, b, subscribers=[log])
    return battle, a, b, log


class SkysplinterDisembarkFlagSetTests(unittest.TestCase):
    """Test #1 — `_disembark` sets the transient flags on the right
    passenger/detachment combinations and not on the wrong ones."""

    def _setup(self, detachment, passenger_profile):
        battle, a, b, _log = _new_battle(detachment)
        a.add_unit(_drukhari_transport_profile())
        a.add_unit(passenger_profile)
        b.add_unit(_enemy_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (20.0, 20.0)
        battle._embark_pregame_passengers()
        return battle, a, b, a.units[0], a.units[1]

    def test_drukhari_passenger_skysplinter_sets_both_flags(self):
        """Drukhari passenger disembarking while the army's detachment
        is Skysplinter Assault must have both transient flags set."""
        battle, _a, _b, transport, passenger = self._setup(
            SKYSPLINTER_ASSAULT, _drukhari_passenger_profile(),
        )
        # Pre-disembark sanity.
        self.assertFalse(passenger.transient_lance_this_turn)
        self.assertFalse(passenger.transient_ignores_cover_this_turn)
        # Disembark.
        battle._disembark(passenger, transport, forced=False)
        # Post-disembark: both flags True.
        self.assertTrue(
            passenger.transient_lance_this_turn,
            "Drukhari disembarking in Skysplinter must gain transient LANCE",
        )
        self.assertTrue(
            passenger.transient_ignores_cover_this_turn,
            "Drukhari disembarking in Skysplinter must gain transient IGNORES COVER",
        )

    def test_drukhari_passenger_non_skysplinter_does_not_set_flags(self):
        """Drukhari passenger disembarking while the army's detachment
        is some other Drukhari detachment (Kabalite Cartel) must NOT
        gain the transient buffs — the rule is Skysplinter-specific."""
        battle, _a, _b, transport, passenger = self._setup(
            KABALITE_CARTEL, _drukhari_passenger_profile(),
        )
        battle._disembark(passenger, transport, forced=False)
        self.assertFalse(
            passenger.transient_lance_this_turn,
            "Non-Skysplinter detachment must not grant transient LANCE",
        )
        self.assertFalse(
            passenger.transient_ignores_cover_this_turn,
            "Non-Skysplinter detachment must not grant transient IGNORES COVER",
        )

    def test_non_drukhari_passenger_skysplinter_does_not_set_flags(self):
        """The detachment is Drukhari-faction-locked at the registry
        level so this configuration is unusual in practice, but the
        faction gate on `_disembark` is what makes the flags safe to
        check inside the hot loop — verify it explicitly."""
        battle, _a, _b, transport, passenger = self._setup(
            SKYSPLINTER_ASSAULT, _non_drukhari_passenger_profile(),
        )
        battle._disembark(passenger, transport, forced=False)
        self.assertFalse(
            passenger.transient_lance_this_turn,
            "Non-Drukhari faction passenger must not gain transient LANCE",
        )
        self.assertFalse(
            passenger.transient_ignores_cover_this_turn,
            "Non-Drukhari faction passenger must not gain transient IGNORES COVER",
        )

    def test_forced_disembark_also_sets_flags(self):
        """Codex wording does not exclude the destroyed-transport
        disembark from Rain of Cruelty — the rule fires on any
        disembark. Verify `_disembark(forced=True)` sets the flags."""
        battle, _a, _b, transport, passenger = self._setup(
            SKYSPLINTER_ASSAULT, _drukhari_passenger_profile(),
        )
        battle._disembark(passenger, transport, forced=True)
        self.assertTrue(passenger.transient_lance_this_turn)
        self.assertTrue(passenger.transient_ignores_cover_this_turn)


class SkysplinterFlagAttackComposeTests(unittest.TestCase):
    """Test #2 — the transient flags compose into Unit.attack."""

    def _setup(self):
        battle, a, b, _log = _new_battle(SKYSPLINTER_ASSAULT)
        a.add_unit(_drukhari_transport_profile())
        a.add_unit(_drukhari_passenger_profile())
        # Enemy sits in cover with save 5 so cover grants 4+ vs ranged.
        b.add_unit(_enemy_profile(save=5))
        b.units[0].in_cover = True
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (15.0, 10.0)
        battle._embark_pregame_passengers()
        return battle, a, b, a.units[0], a.units[1], b.units[0]

    def test_transient_ignores_cover_bypasses_cover_save(self):
        """When the disembarked unit fires ranged with the transient
        IGNORES COVER flag set, the target's Benefits of Cover +1 to
        save is bypassed. The cleanest observable signal is that
        expected damage rises versus the same call with the flag off
        — we drive every die to a roll that hits + wounds + fails the
        non-cover save (4 on the save die fails 5+) but passes the
        cover-improved 4+ save."""
        battle, _a, _b, transport, passenger, enemy = self._setup()
        battle._disembark(passenger, transport, forced=False)
        self.assertTrue(passenger.transient_ignores_cover_this_turn)
        # Hit (6), wound (6), save roll = 4 — fails 5+ (no cover) but
        # passes 4+ (cover). With IGNORES COVER set, the save target
        # stays at 5+ so the 4 is a fail and the wound applies.
        roll_sequence = iter([6, 6, 4] * 200)
        with mock.patch(
            "code.units.random.randint",
            side_effect=lambda lo, hi: next(roll_sequence),
        ):
            dealt = passenger.attack(
                enemy, distance=5.0, mode="ranged", has_los=True,
            )
        self.assertGreater(
            dealt, 0.0,
            "Disembarked Drukhari unit with transient IGNORES COVER "
            "should land damage through the target's cover save",
        )

    def test_transient_ignores_cover_off_is_blocked_by_cover(self):
        """Mirror of the previous test: with the flag NOT set (no
        disembark), the same hit/wound/save sequence is blocked by the
        cover-improved 4+ save."""
        _battle, _a, _b, _transport, passenger, enemy = self._setup()
        # No disembark — flag stays False.
        self.assertFalse(passenger.transient_ignores_cover_this_turn)
        # Drop the passenger out of the transport manually so it can
        # shoot. Unit.attack does NOT itself check `is_embarked` (that's
        # _do_shoot's job), so clearing the embark pointer is enough to
        # let the attack pipeline run.
        passenger.embarked_in = None
        roll_sequence = iter([6, 6, 4] * 200)
        with mock.patch(
            "code.units.random.randint",
            side_effect=lambda lo, hi: next(roll_sequence),
        ):
            dealt = passenger.attack(
                enemy, distance=5.0, mode="ranged", has_los=True,
            )
        self.assertEqual(
            dealt, 0.0,
            "Without IGNORES COVER the cover-improved save (4+) should "
            "block every wound at this roll sequence",
        )

    def test_transient_lance_adds_plus_one_to_wound_on_charge(self):
        """Melee LANCE keyword grants +1 to wound when the attack is
        made on the turn the bearer's unit declared a charge. The
        clearest deterministic observation is the wound-roll target:
        S4 vs T4 wounds on 4+; with LANCE the effective wound target
        becomes 3+. Driving the wound die to a 3 produces damage with
        the LANCE flag set, and produces zero damage without it."""
        battle, _a, _b, transport, passenger, enemy = self._setup()
        battle._disembark(passenger, transport, forced=False)
        self.assertTrue(passenger.transient_lance_this_turn)
        # Roll sequence per melee attack: hit (6), wound (3),
        # save (1 — auto-fail).
        roll_sequence = iter([6, 3, 1] * 200)
        with mock.patch(
            "code.units.random.randint",
            side_effect=lambda lo, hi: next(roll_sequence),
        ):
            dealt = passenger.attack(
                enemy, distance=1.0, mode="melee",
                has_los=True, is_charging=True,
            )
        self.assertGreater(
            dealt, 0.0,
            "Disembarked Drukhari unit with transient LANCE and is_charging "
            "should have +1 to wound applied (4+ -> 3+ wound roll)",
        )

    def test_transient_lance_does_nothing_without_charge(self):
        """LANCE only fires when the attack was made on the charge turn
        — without `is_charging=True` even the transient flag is inert.
        Same wound roll of 3 vs the 4+ wound target should fail."""
        battle, _a, _b, transport, passenger, enemy = self._setup()
        battle._disembark(passenger, transport, forced=False)
        self.assertTrue(passenger.transient_lance_this_turn)
        roll_sequence = iter([6, 3, 1] * 200)
        with mock.patch(
            "code.units.random.randint",
            side_effect=lambda lo, hi: next(roll_sequence),
        ):
            dealt = passenger.attack(
                enemy, distance=1.0, mode="melee",
                has_los=True, is_charging=False,
            )
        self.assertEqual(
            dealt, 0.0,
            "Without is_charging the transient LANCE flag must not fire",
        )


class SkysplinterFlagClearAtRoundStartTests(unittest.TestCase):
    """Test #3 — the transient flags clear at the next round start."""

    def test_flags_cleared_by_clear_transient_stratagem_flags(self):
        battle, a, b, _log = _new_battle(SKYSPLINTER_ASSAULT)
        a.add_unit(_drukhari_transport_profile())
        a.add_unit(_drukhari_passenger_profile())
        b.add_unit(_enemy_profile())
        battle._assign_uids()
        a.units[0].position = (10.0, 10.0)
        a.units[1].position = (10.0, 10.0)
        b.units[0].position = (20.0, 20.0)
        battle._embark_pregame_passengers()
        passenger = a.units[1]
        battle._disembark(passenger, a.units[0], forced=False)
        # Flags True after disembark.
        self.assertTrue(passenger.transient_lance_this_turn)
        self.assertTrue(passenger.transient_ignores_cover_this_turn)
        # Run the round-start clear hook.
        battle._clear_transient_stratagem_flags(a)
        # Flags False after clear.
        self.assertFalse(
            passenger.transient_lance_this_turn,
            "_clear_transient_stratagem_flags must clear "
            "transient_lance_this_turn",
        )
        self.assertFalse(
            passenger.transient_ignores_cover_this_turn,
            "_clear_transient_stratagem_flags must clear "
            "transient_ignores_cover_this_turn",
        )


if __name__ == "__main__":
    unittest.main()
