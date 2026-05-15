"""Regression test for SwegHammer task #173 — Plague Weapons scope.

Wahapedia (Plague Company / Plague Weapons stratagem):
    "USE THIS STRATAGEM IN YOUR SHOOTING PHASE OR THE FIGHT PHASE, WHEN A
    DEATH GUARD UNIT FROM YOUR ARMY IS SELECTED TO SHOOT OR FIGHT. UNTIL
    THE END OF THE PHASE, EACH TIME A MODEL IN YOUR UNIT MAKES AN ATTACK
    WITH A PLAGUE WEAPON, ADD 1 TO THE WOUND ROLL."

The rule targets a SINGLE unit ("A DEATH GUARD UNIT") — not the whole army.
The stratagem firing audit (`docs/STRATAGEM_FIRING_AUDIT.md`) flagged a
concern that the simulator might be applying the +1-to-wound buff army-wide
rather than to one chosen attacker per fire. This test pins the scope: with
two DG units in the army, firing Plague Weapons must set the
`transient_plus_one_to_wound_shooting` flag on exactly ONE unit (the chosen
attacker), and leave every other DG unit's flag False.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.detachments import PLAGUE_COMPANY
from code.simulator import Battle
from code.units import UnitProfile


def _high_dpa_dg_profile() -> UnitProfile:
    """High-DPA DG shooter — the AI's `_highest_dpa_unit` should pick this
    one when scoring two DG candidates. Ranged DPA = 3 attacks * 2/3 hit *
    2 dmg = 4.0, well above the AI's 2.0 gate."""
    return UnitProfile(
        name="Plagueburst Crawler",
        health=12, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=6, toughness=11,
        attacks=3, weapon_damage_per_shot=2.0,
        range_inches=48,
        faction="Death Guard",
        unit_keywords=("VEHICLE", "DEATH GUARD"),
    )


def _low_dpa_dg_profile() -> UnitProfile:
    """Low-DPA DG shooter — should NOT be selected as the Plague Weapons
    attacker when a stronger DG shooter is also in the army. Ranged DPA =
    1 attack * 2/3 hit * 1 dmg = 0.67."""
    return UnitProfile(
        name="Poxwalker",
        health=1, damage=1, hit_probability=2 / 3,
        ap=0, save=7, strength=3, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=1 / 2, melee_strength=3,
        range_inches=12,
        faction="Death Guard",
        unit_keywords=("INFANTRY", "DEATH GUARD"),
    )


def _vehicle_target_profile() -> UnitProfile:
    """A heavy enemy unit so the AI's _is_heavy_target gate green-lights
    the spend."""
    return UnitProfile(
        name="Enemy Knight",
        health=22, damage=6, hit_probability=2 / 3,
        ap=-3, save=2, strength=10, toughness=12,
        attacks=4, weapon_damage_per_shot=1.5,
        range_inches=48,
        unit_keywords=("VEHICLE", "TITANIC"),
    )


def _build_army(name: str, profiles) -> Army:
    army = Army(name)
    for p in profiles:
        army.add_unit(p)
    return army


class PlagueWeaponsScopeTests(unittest.TestCase):
    """The stratagem buff lands on exactly one DG unit per fire, not the
    whole DG army."""

    def test_plague_weapons_buffs_only_one_dg_unit(self):
        # Two DG units: a high-DPA Plagueburst Crawler (should be picked)
        # and a low-DPA Poxwalker (should NOT be touched).
        a = _build_army(
            "Death Guard",
            [_high_dpa_dg_profile(), _low_dpa_dg_profile()],
        )
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = PLAGUE_COMPANY
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()

        # Pre-condition: neither unit has the flag set.
        self.assertFalse(a.units[0].transient_plus_one_to_wound_shooting)
        self.assertFalse(a.units[1].transient_plus_one_to_wound_shooting)

        battle._try_plague_weapons(a, b)

        # Post-condition: CP was spent (stratagem actually fired).
        self.assertEqual(
            a.command_points, 4,
            "Plague Weapons should have spent exactly 1 CP",
        )

        # Single-unit scope: exactly ONE of the two DG units gets the buff.
        flagged = [
            u for u in a.units
            if u.transient_plus_one_to_wound_shooting
        ]
        self.assertEqual(
            len(flagged), 1,
            "Plague Weapons must scope its +1 to wound to a single chosen "
            "DG unit (not the whole DG army). "
            f"Got {len(flagged)} buffed units instead of 1.",
        )

        # The high-DPA Plagueburst Crawler must be the one chosen — that's
        # the AI's `_highest_dpa_unit` pick. The Poxwalker must NOT be
        # buffed.
        self.assertTrue(
            a.units[0].transient_plus_one_to_wound_shooting,
            "Highest-DPA DG unit (Plagueburst Crawler) should have the "
            "+1-to-wound flag",
        )
        self.assertFalse(
            a.units[1].transient_plus_one_to_wound_shooting,
            "Low-DPA DG unit (Poxwalker) MUST NOT have the +1-to-wound "
            "flag — that would be the army-wide leakage the audit flagged",
        )

    def test_plague_weapons_does_not_leak_to_unbuffed_unit_attacks(self):
        """End-to-end: after Plague Weapons fires on unit A, unit B's
        attack() must still resolve with its base wound target — not the
        buffed one."""
        a = _build_army(
            "Death Guard",
            [_high_dpa_dg_profile(), _low_dpa_dg_profile()],
        )
        b = _build_army("Foes", [_vehicle_target_profile()])
        a.detachment = PLAGUE_COMPANY
        a.command_points = 5
        battle = Battle(a, b)
        battle._assign_uids()
        battle._try_plague_weapons(a, b)

        # The Poxwalker (units[1]) is not the chosen attacker. Verify its
        # flag is False so any downstream Unit.attack() call resolves with
        # the base wound roll, not the +1.
        self.assertFalse(
            a.units[1].transient_plus_one_to_wound_shooting,
            "Non-chosen DG unit must keep its transient flag False so its "
            "Unit.attack() resolves at the unbuffed wound target",
        )


if __name__ == "__main__":
    unittest.main()
