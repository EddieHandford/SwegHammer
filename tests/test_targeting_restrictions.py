"""Tests for the 10e core ranged-targeting restrictions: Look Out Sir and
Lone Operative. Both gates are implemented in
`code.army.can_target_for_ranged`. Wahapedia citations live in
`data/rule_citations.d/core_targeting.json`.
"""

from __future__ import annotations

import unittest

from code.army import can_target_for_ranged
from code.units import Unit, UnitProfile


def _make_unit(
    name: str,
    position: tuple,
    unit_keywords: tuple = (),
    lone_operative: bool = False,
) -> Unit:
    """Build a barebones Unit instance for targeting-rule tests.

    The combat stats don't matter — only `position`, `unit_keywords`, and the
    `lone_operative` profile flag are read by `can_target_for_ranged`.
    """
    profile = UnitProfile(
        name=name,
        health=2.0,
        damage=1.0,
        hit_probability=2 / 3,
        ap=0,
        save=4,
        unit_keywords=tuple(unit_keywords),
        lone_operative=lone_operative,
    )
    u = Unit(profile)
    u.position = position
    return u


class LookOutSirTests(unittest.TestCase):
    """Look Out Sir: CHARACTERS (excluding MONSTER and VEHICLE) within 3" of a
    friendly non-CHARACTER unit cannot be shot from >12" away."""

    def test_character_protected_by_bodyguard(self):
        """CHARACTER within 3" of friendly INFANTRY, attacker 15" — NOT targetable."""
        character = _make_unit(
            "Captain", (0.0, 0.0), unit_keywords=("CHARACTER", "INFANTRY")
        )
        bodyguard = _make_unit(
            "Tactical Squad", (2.0, 0.0), unit_keywords=("INFANTRY",)
        )
        attacker = _make_unit("Sniper", (15.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertFalse(
            can_target_for_ranged(attacker, character, [character, bodyguard])
        )

    def test_character_targetable_within_12(self):
        """Same bodyguard setup, attacker 10" — IS targetable (inside 12")."""
        character = _make_unit(
            "Captain", (0.0, 0.0), unit_keywords=("CHARACTER", "INFANTRY")
        )
        bodyguard = _make_unit(
            "Tactical Squad", (2.0, 0.0), unit_keywords=("INFANTRY",)
        )
        attacker = _make_unit("Sniper", (10.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertTrue(
            can_target_for_ranged(attacker, character, [character, bodyguard])
        )

    def test_vehicle_character_unprotected(self):
        """A CHARACTER VEHICLE (Imperial Knight pilot) is excluded from LOS —
        the bodyguard provides no protection, so the >12" shot lands."""
        knight = _make_unit(
            "Imperial Knight",
            (0.0, 0.0),
            unit_keywords=("CHARACTER", "VEHICLE"),
        )
        bodyguard = _make_unit(
            "Tactical Squad", (2.0, 0.0), unit_keywords=("INFANTRY",)
        )
        attacker = _make_unit("Sniper", (15.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertTrue(
            can_target_for_ranged(attacker, knight, [knight, bodyguard])
        )

    def test_no_bodyguard_no_los_protection(self):
        """A solo CHARACTER with no friendlies within 3" is targetable at any range."""
        character = _make_unit(
            "Captain", (0.0, 0.0), unit_keywords=("CHARACTER", "INFANTRY")
        )
        # The only friendly in the defender's army is the character itself.
        attacker_close = _make_unit(
            "Sniper", (5.0, 0.0), unit_keywords=("INFANTRY",)
        )
        attacker_far = _make_unit(
            "Sniper", (30.0, 0.0), unit_keywords=("INFANTRY",)
        )
        self.assertTrue(
            can_target_for_ranged(attacker_close, character, [character])
        )
        self.assertTrue(
            can_target_for_ranged(attacker_far, character, [character])
        )


class LoneOperativeTests(unittest.TestCase):
    """Lone Operative: ranged attackers must be within 12"."""

    def test_lone_operative_blocks_long_range(self):
        """Lone Operative target, attacker 15" — NOT targetable."""
        target = _make_unit(
            "Eliminator", (0.0, 0.0),
            unit_keywords=("INFANTRY",), lone_operative=True,
        )
        attacker = _make_unit("Devastator", (15.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertFalse(can_target_for_ranged(attacker, target, [target]))

    def test_lone_operative_targetable_at_short_range(self):
        """Same target, attacker 8" — IS targetable (inside 12")."""
        target = _make_unit(
            "Eliminator", (0.0, 0.0),
            unit_keywords=("INFANTRY",), lone_operative=True,
        )
        attacker = _make_unit("Devastator", (8.0, 0.0), unit_keywords=("INFANTRY",))
        self.assertTrue(can_target_for_ranged(attacker, target, [target]))


if __name__ == "__main__":
    unittest.main()
