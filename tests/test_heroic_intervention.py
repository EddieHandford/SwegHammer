"""Tests for the 10e core Heroic Intervention CHARACTER move (#iter12).

Heroic Intervention is a FREE core CHARACTER ability per Wahapedia 10e
core rules (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#CHARGE-PHASE):

  > "Heroic Intervention: After the opposing player has resolved their
  > charges, you can select any of your CHARACTER models that are within
  > 6\" of any enemy units. Each of those models can move up to 6\"
  > (3\" if WALKER) — they must end the move within Engagement Range of
  > one of those enemy units."

Previously SwegHammer modelled this as a 1 CP Core Stratagem. iter12
replaces that with a free core mechanic in
`code.simulator._do_heroic_intervention`, fired unconditionally at the
end of every successful charge.

Coverage:
  * CHARACTER within 6" of the charger intervenes up to 6" toward the
    charger; no CP is spent.
  * WALKER CHARACTER intervenes only up to 3" toward the charger.
  * CHARACTER more than 6" from the charger does not intervene at all.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle, _distance
from code.stratagems import STARTING_CP
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _charger_profile() -> UnitProfile:
    """A fast melee charger — high move + reach, big melee profile so it
    actually wants to declare a charge under the simulator's heuristic."""
    return UnitProfile(
        name="Charger",
        health=4, damage=1, hit_probability=2 / 3,
        ap=-1, save=3, strength=5, toughness=4,
        move=12.0, attacks=1, weapon_damage_per_shot=1.0,
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=5 / 6, melee_strength=5,
        range_inches=12,
    )


def _charge_target_profile() -> UnitProfile:
    return UnitProfile(
        name="ChargeTarget",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0,
        range_inches=24,
    )


def _character_profile() -> UnitProfile:
    return UnitProfile(
        name="Captain",
        health=4, damage=1, hit_probability=2 / 3,
        ap=-2, save=3, strength=4, toughness=4,
        attacks=4, weapon_damage_per_shot=1.0,
        melee_attacks=5, melee_damage_per_shot=2.0,
        melee_hit_probability=5 / 6, melee_strength=8,
        melee_ap=-2,
        range_inches=12,
        unit_keywords=("CHARACTER", "INFANTRY"),
    )


def _walker_character_profile() -> UnitProfile:
    return UnitProfile(
        name="Walker Captain",
        health=10, damage=1, hit_probability=2 / 3,
        ap=-2, save=2, strength=6, toughness=8,
        attacks=4, weapon_damage_per_shot=1.0,
        melee_attacks=5, melee_damage_per_shot=3.0,
        melee_hit_probability=2 / 3, melee_strength=10,
        melee_ap=-3,
        range_inches=12,
        unit_keywords=("CHARACTER", "VEHICLE", "WALKER"),
    )


def _build_battle() -> Battle:
    """Build a 1-vs-1 battle with deterministic seeding for the position math."""
    random.seed(0)
    attacker_army = Army("Attacker")
    defender_army = Army("Defender")
    # Placeholder units are added in the individual tests so we control
    # exact positions; here we hand back the Battle skeleton.
    attacker_army.add_unit(_charger_profile())
    defender_army.add_unit(_charge_target_profile())
    battle = Battle(attacker_army, defender_army)
    battle._assign_uids()
    # Strip the placeholder units before the test populates real ones.
    attacker_army.units.clear()
    defender_army.units.clear()
    return battle


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class HeroicInterventionCoreTests(unittest.TestCase):

    def test_character_within_6_inches_intervenes_no_cp_spent(self):
        """A CHARACTER within 6" of the charger moves up to 6" toward the
        charger and no CP is spent — Heroic Intervention is FREE."""
        battle = _build_battle()
        # Charger ends its charge at (10, 10); defender CHARACTER stands
        # 5" away at (15, 10) — well inside the 6" eligibility window.
        battle.a.add_unit(_charger_profile())
        charger = battle.a.units[-1]
        charger.uid = "ATK0"
        charger.position = (10.0, 10.0)
        battle.b.add_unit(_character_profile())
        character = battle.b.units[-1]
        character.uid = "CHAR0"
        character.position = (15.0, 10.0)
        battle.b.command_points = STARTING_CP
        cp_before = battle.b.command_points
        old_pos = character.position

        battle._do_heroic_intervention(charger, battle.b)

        # The CHARACTER moved toward the charger up to its 6" budget.
        # Distance closed: full 5" gap (less than the 6" cap) so it lands
        # on / at the charger's position (engagement range).
        self.assertNotEqual(character.position, old_pos)
        new_d = _distance(character.position, charger.position)
        # Engagement range is 1" in 10e; SwegHammer's _move_toward closes
        # the gap fully when max_dist >= distance, so we expect ~0.
        self.assertLess(new_d, 1.5,
                        "CHARACTER must end within engagement range of the charger")
        # Crucially, the move costs zero CP — Heroic Intervention is free.
        self.assertEqual(battle.b.command_points, cp_before,
                         "Heroic Intervention is a free core ability, not a stratagem")

    def test_walker_character_capped_at_3_inches(self):
        """A WALKER CHARACTER intervenes at most 3" — half the standard
        Heroic Intervention move. We place the WALKER 5" from the charger
        and verify it cannot fully close the gap (it would need 6")."""
        battle = _build_battle()
        battle.a.add_unit(_charger_profile())
        charger = battle.a.units[-1]
        charger.uid = "ATK1"
        charger.position = (10.0, 10.0)
        battle.b.add_unit(_walker_character_profile())
        walker = battle.b.units[-1]
        walker.uid = "WALK0"
        walker.position = (15.0, 10.0)   # 5" away
        old_pos = walker.position

        battle._do_heroic_intervention(charger, battle.b)

        # WALKER capped at 3" — moves to (12.0, 10.0).
        moved = _distance(old_pos, walker.position)
        self.assertAlmostEqual(moved, 3.0, places=5,
                               msg="WALKER CHARACTER must be capped at a 3\" Heroic Intervention move")
        # And lands 2" from the charger — outside engagement range, because
        # the WALKER simply cannot reach in one 3" move.
        residual = _distance(walker.position, charger.position)
        self.assertAlmostEqual(residual, 2.0, places=5,
                               msg="WALKER should end 5\" - 3\" = 2\" from the charger")

    def test_character_beyond_6_inches_does_not_intervene(self):
        """A CHARACTER more than 6" from the charger is ineligible — it
        must not move at all."""
        battle = _build_battle()
        battle.a.add_unit(_charger_profile())
        charger = battle.a.units[-1]
        charger.uid = "ATK2"
        charger.position = (10.0, 10.0)
        battle.b.add_unit(_character_profile())
        character = battle.b.units[-1]
        character.uid = "CHAR2"
        # 8" away — outside the 6" eligibility window.
        character.position = (18.0, 10.0)
        old_pos = character.position

        battle._do_heroic_intervention(charger, battle.b)

        self.assertEqual(character.position, old_pos,
                         "CHARACTER more than 6\" away must not perform Heroic Intervention")


if __name__ == "__main__":
    unittest.main()
