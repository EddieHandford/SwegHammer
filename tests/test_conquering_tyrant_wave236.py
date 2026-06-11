"""Wave 236: Protocol of the Conquering Tyrant two-branch verification.

Verifies the led/unled split introduced in wave 236:
  - Led attacker (NECRONS CHARACTER within 6" leading the unit) → full hit
    re-roll via `transient_reroll_all_hits`; `transient_reroll_hits_shooting`
    must NOT be set.
  - Unled attacker (no CHARACTER present) → re-roll hit rolls of 1 only via
    `transient_reroll_hits_shooting`; `transient_reroll_all_hits` must NOT
    be set.
  - Both paths spend exactly 1 command point.

Codex source: Wahapedia https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import AWAKENED_DYNASTY
from code.simulator import Battle
from code.stratagems import PROTOCOL_OF_THE_CONQUERING_TYRANT
from code.units import UnitProfile


def _necron_warriors_profile() -> UnitProfile:
    """High-DPA NECRONS shooter — clears the >=2.0 ranged_dpa heuristic gate."""
    return UnitProfile(
        name="Necron Warriors",
        faction="Necrons",
        health=10, damage=1, hit_probability=2 / 3,
        ap=-1, save=4, strength=4, toughness=4,
        attacks=10, weapon_damage_per_shot=1.5,
        melee_attacks=5, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        range_inches=24,
        unit_keywords=("NECRONS", "INFANTRY"),
        points_override=90.0,
    )


def _necron_character_profile() -> UnitProfile:
    """NECRONS CHARACTER profile to trigger the led branch via _is_led_unit."""
    return UnitProfile(
        name="Necron Overlord",
        faction="Necrons",
        health=6, damage=4, hit_probability=2 / 3,
        ap=-2, save=3, strength=6, toughness=5,
        attacks=6, weapon_damage_per_shot=1.0,
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=6,
        range_inches=18,
        unit_keywords=("NECRONS", "CHARACTER", "INFANTRY"),
        points_override=90.0,
    )


def _heavy_target_profile() -> UnitProfile:
    """HEAVY/TITANIC target so the Conquering Tyrant heuristic greenlights."""
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


def _make_battle_unled():
    """Army with no CHARACTER — _is_led_unit returns False for the attacker."""
    random.seed(42)
    a = Army("Necrons")
    a.add_unit(_necron_warriors_profile())
    a.detachment = AWAKENED_DYNASTY
    a.command_points = 6
    b = Army("Enemy")
    b.add_unit(_heavy_target_profile())
    battle = Battle(a, b)
    battle._assign_uids()
    return battle, a, b


def _make_battle_led():
    """Army with a NECRONS CHARACTER at position (0,0) — the attacker starts at
    (0,0) too, so distance == 0 < 6", and _is_led_unit returns True."""
    random.seed(42)
    a = Army("Necrons")
    a.add_unit(_necron_warriors_profile())
    a.add_unit(_necron_character_profile())  # CHARACTER within 6" of the Warriors
    a.detachment = AWAKENED_DYNASTY
    a.command_points = 6
    b = Army("Enemy")
    b.add_unit(_heavy_target_profile())
    battle = Battle(a, b)
    battle._assign_uids()
    return battle, a, b


class ConqueringTyrantWave236Tests(unittest.TestCase):
    """Two-branch implementation: led → full re-roll; unled → re-roll 1s."""

    # ------------------------------------------------------------------
    # Unled branch
    # ------------------------------------------------------------------

    def test_unled_sets_reroll_hits_shooting(self):
        """Unled attacker must activate the re-roll-1s shooting flag."""
        battle, a, b = _make_battle_unled()
        cp_before = a.command_points
        battle._try_protocol_conquering_tyrant(a, b)
        self.assertTrue(
            any(getattr(u, "transient_reroll_hits_shooting", False) for u in a.units),
            "unled branch must set transient_reroll_hits_shooting on at least one unit",
        )

    def test_unled_does_not_set_reroll_all_hits(self):
        """Unled attacker must NOT activate the full-re-roll flag."""
        battle, a, b = _make_battle_unled()
        battle._try_protocol_conquering_tyrant(a, b)
        self.assertFalse(
            any(getattr(u, "transient_reroll_all_hits", False) for u in a.units),
            "unled branch must NOT set transient_reroll_all_hits",
        )

    def test_unled_spends_one_command_point(self):
        """Unled branch must spend exactly 1 command point."""
        battle, a, b = _make_battle_unled()
        cp_before = a.command_points
        battle._try_protocol_conquering_tyrant(a, b)
        # The stratagem fired (checked by flag above); confirm 1 CP spent.
        self.assertEqual(
            a.command_points, cp_before - PROTOCOL_OF_THE_CONQUERING_TYRANT.cp_cost,
            "unled branch must spend exactly 1 command point",
        )

    # ------------------------------------------------------------------
    # Led branch
    # ------------------------------------------------------------------

    def test_led_sets_reroll_all_hits(self):
        """Led attacker (CHARACTER within 6") must activate the full-re-roll flag."""
        battle, a, b = _make_battle_led()
        # Confirm the CHARACTER is present and _is_led_unit returns True for
        # the Warriors unit (the highest-DPA non-CHARACTER).
        attacker = next(
            u for u in a.units
            if "CHARACTER" not in (u.profile.unit_keywords or ())
        )
        self.assertTrue(
            battle._is_led_unit(attacker),
            "_is_led_unit must return True when a CHARACTER is within 6\"",
        )
        battle._try_protocol_conquering_tyrant(a, b)
        self.assertTrue(
            any(getattr(u, "transient_reroll_all_hits", False) for u in a.units),
            "led branch must set transient_reroll_all_hits on at least one unit",
        )

    def test_led_does_not_set_reroll_hits_shooting(self):
        """Led attacker must NOT activate the re-roll-1s flag."""
        battle, a, b = _make_battle_led()
        battle._try_protocol_conquering_tyrant(a, b)
        self.assertFalse(
            any(getattr(u, "transient_reroll_hits_shooting", False) for u in a.units),
            "led branch must NOT set transient_reroll_hits_shooting",
        )

    def test_led_spends_one_command_point(self):
        """Led branch must spend exactly 1 command point."""
        battle, a, b = _make_battle_led()
        cp_before = a.command_points
        battle._try_protocol_conquering_tyrant(a, b)
        self.assertEqual(
            a.command_points, cp_before - PROTOCOL_OF_THE_CONQUERING_TYRANT.cp_cost,
            "led branch must spend exactly 1 command point",
        )

    # ------------------------------------------------------------------
    # No firing without command points
    # ------------------------------------------------------------------

    def test_no_flag_set_without_cp(self):
        """When command points are 0 the stratagem must not fire and no flag is set."""
        battle, a, b = _make_battle_led()
        a.command_points = 0
        battle._try_protocol_conquering_tyrant(a, b)
        self.assertFalse(
            any(getattr(u, "transient_reroll_all_hits", False) for u in a.units),
        )
        self.assertFalse(
            any(getattr(u, "transient_reroll_hits_shooting", False) for u in a.units),
        )


if __name__ == "__main__":
    unittest.main()
