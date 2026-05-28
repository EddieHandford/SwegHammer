"""Tests for 10e Fight-phase Pile-In and Consolidate core moves.

Per the 10e core rules (Wahapedia /the-rules/core-rules/#FIGHT-PHASE):

* **Pile-In**: "Before a unit fights, each model in that unit can make a
  Pile-In move of up to 3\", but each model must end that move closer to
  the closest enemy model than it was at the start of the move."
* **Consolidate**: "After a unit fights, each model in that unit can
  make a Consolidation move of up to 3\", but each model must end that
  move either closer to the closest enemy model than it was at the
  start of the move, or within Engagement Range of one or more enemy
  units that it was in Engagement Range of at the start of the move."

SwegHammer's one-Unit-per-model representation collapses "each model"
to "the Unit" — so each fires once per `_do_fight` activation.

Cited as `simulator.pile_in` / `simulator.consolidate`.
"""

from __future__ import annotations

import random
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle, _distance
from code.units import UnitProfile


def _melee_profile() -> UnitProfile:
    """Tough melee bruiser with enough melee_attacks to actually fight."""
    return UnitProfile(
        name="Brawler", health=4, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=1,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5, melee_ap=1,
        move=6.0,
    )


def _victim_profile() -> UnitProfile:
    """Squishy target — dies in one round of melee from the Brawler."""
    return UnitProfile(
        name="Victim", health=1, damage=0, hit_probability=0,
        ap=0, save=5, strength=3, toughness=3,
        attacks=0, range_inches=1,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        move=6.0,
    )


def _open_map() -> Map:
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _make_army(name: str, profile: UnitProfile, positions: list) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


class PileInTests(unittest.TestCase):
    """Pile-In: free 3" toward closest enemy BEFORE the fight resolves."""

    def test_unit_just_out_of_engagement_piles_in_then_fights(self):
        """After a charge, an attacker 1.5" away (just outside the 1"
        Engagement Range gate) closes via pile-in and fights.

        10e Fight phase: a unit can fight if it is in Engagement Range
        (1") OR if it Charged this turn. Pile-in is a free 3" move
        toward the closest enemy taken BEFORE the fight resolves and
        is gated on that same eligibility. So an attacker that charged
        and ended its move at 1.5" (just out of engagement) gets to
        pile in down to 0" and then strike — verified here by adding
        the attacker to `_charging_this_round` before calling
        `_do_fight`.
        """
        a = _make_army("A", _melee_profile(), [(20.0, 30.0)])
        b = _make_army("B", _victim_profile(), [(21.5, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, victim = a.units[0], b.units[0]

        start_dist = _distance(attacker.position, victim.position)
        self.assertAlmostEqual(start_dist, 1.5, places=5)

        battle._charging_this_round.add(attacker.uid)

        # Deterministic enough — pile-in is geometry only, no dice.
        random.seed(0)
        battle._do_fight(attacker, battle.a, battle.b)

        # Pile-in moves 3" toward (21.5, 30.0) — attacker (20,30) is
        # 1.5" away so it lands on (21.5,30) i.e. distance 0. Then a
        # consolidate fires post-fight which doesn't move us (already
        # on top of the victim's old position) — but the victim may
        # have died, in which case the unit stays put with no other
        # enemies in play. Either way, the pile-in landed on/through
        # the target before the fight.
        # The assertion: at the moment of `attacker.attack`, attacker
        # was within engagement. We can verify by checking that the
        # victim took damage (fight resolved -> pile-in put us in
        # range).
        self.assertLess(
            victim.current_health, 1,
            "Pile-in should have placed attacker in engagement so "
            "the fight resolved and the victim took damage.",
        )

    def test_pile_in_distance_capped_at_3_inches(self):
        """Pile-in is 3" max. A CHARGING unit 4" away closes to 1"
        (engagement) and then fights. Not-charging non-engaged units
        do not fight at all (per 10e Fight phase eligibility), so the
        cap test is meaningful only for charge-eligible activations."""
        a = _make_army("A", _melee_profile(), [(20.0, 30.0)])
        b = _make_army("B", _victim_profile(), [(24.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, victim = a.units[0], b.units[0]
        # Mark as charging so the fight-eligibility gate passes — per
        # 10e core, a unit that made a Charge move this turn is
        # eligible to fight even if not currently in engagement.
        battle._charging_this_round.add(attacker.uid)

        random.seed(0)
        battle._do_fight(attacker, battle.a, battle.b)

        # Pile-in moves attacker exactly 3" toward (24, 30): from
        # (20, 30) to (23, 30) — distance 1" to victim, within the
        # 1.5" engagement floor. Fight resolves; victim dies; the
        # post-fight consolidate has no alive enemies to chase so
        # the attacker stays put at (23, 30). Total movement = 3"
        # — the cap.
        moved = abs(attacker.position[0] - 20.0)
        self.assertAlmostEqual(moved, 3.0, places=5)
        self.assertFalse(victim.is_alive)

    def test_unit_outside_engagement_and_not_charging_does_not_pile_in(self):
        """Per 10e Fight phase eligibility, a unit that is neither in
        engagement nor charging this turn does not fight, so no
        pile-in or consolidate fires. The attacker stays put."""
        a = _make_army("A", _melee_profile(), [(20.0, 30.0)])
        b = _make_army("B", _victim_profile(), [(25.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker = a.units[0]
        start_pos = attacker.position

        random.seed(0)
        battle._do_fight(attacker, battle.a, battle.b)

        self.assertEqual(
            attacker.position, start_pos,
            "Unit 5\" away and not charging this turn must not pile-in or"
            " consolidate — it's not eligible to fight at all.",
        )


class ConsolidateTests(unittest.TestCase):
    """Consolidate: free 3" toward closest enemy AFTER fight resolves."""

    def test_consolidate_chases_next_enemy_after_target_dies(self):
        """Brawler kills victim, then consolidates toward the next enemy.

        Setup: attacker engaged with victim at 0". A second enemy
        sits 4" away. Pile-in is a no-op (already on top of the
        nearest). Fight kills the victim. Consolidate then has only
        the far enemy to chase — moves up to 3" toward it.
        """
        a = _make_army("A", _melee_profile(), [(20.0, 30.0)])
        b = _make_army(
            "B", _victim_profile(),
            [(20.0, 30.0), (24.0, 30.0)],
        )
        battle = Battle(a, b, map_=_open_map())
        attacker = a.units[0]
        victim, far_enemy = b.units[0], b.units[1]

        random.seed(0)
        battle._do_fight(attacker, battle.a, battle.b)

        self.assertFalse(victim.is_alive)
        # After consolidate, attacker should have moved ~3" toward
        # (24, 30). Starting at (20, 30): pile-in toward closest enemy
        # (the victim at (20,30) → 0" away → no movement), fight kills
        # victim, consolidate toward remaining enemy at (24,30): 3"
        # toward → lands at (23, 30). Final distance to far_enemy = 1.
        final_dist = _distance(attacker.position, far_enemy.position)
        self.assertAlmostEqual(final_dist, 1.0, places=5)

    def test_consolidate_keeps_unit_engaged(self):
        """When target survives, consolidate keeps us on top of them."""
        # Use a tank victim to survive one round.
        tank = UnitProfile(
            name="Tank", health=20, damage=0, hit_probability=0,
            ap=0, save=2, strength=6, toughness=11,
            attacks=0, range_inches=1,
            leadership=8,
            faction="Generic",
            unit_keywords=("VEHICLE",),
            melee_attacks=1, melee_damage_per_shot=1.0,
            melee_hit_probability=0.5, melee_strength=6, melee_ap=0,
            move=6.0,
        )
        a = _make_army("A", _melee_profile(), [(20.0, 30.0)])
        b = _make_army("B", tank, [(20.5, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, victim = a.units[0], b.units[0]

        random.seed(0)
        battle._do_fight(attacker, battle.a, battle.b)

        # Tank survives the strike (20 wounds vs ~3 expected damage).
        self.assertTrue(victim.is_alive)
        # Pile-in put attacker at (20.5, 30) → distance 0. Fight, then
        # consolidate toward closest enemy (still the tank at the same
        # position) → no further movement. Attacker ends in engagement.
        self.assertAlmostEqual(
            _distance(attacker.position, victim.position), 0.0, places=5,
        )


class NoMovementWhenNoEnemyTests(unittest.TestCase):
    """Pile-in/consolidate must not move the unit when no enemy exists."""

    def test_no_movement_when_no_alive_enemies(self):
        a = _make_army("A", _melee_profile(), [(20.0, 30.0)])
        b = _make_army("B", _victim_profile(), [(40.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, enemy = a.units[0], b.units[0]
        # Kill the only enemy before the fight even starts.
        enemy.current_health = 0
        self.assertFalse(enemy.is_alive)

        start_pos = attacker.position
        battle._do_fight(attacker, battle.a, battle.b)

        self.assertEqual(
            attacker.position, start_pos,
            "Pile-in/consolidate must not move the unit when no enemy"
            " is alive on the defender side.",
        )


if __name__ == "__main__":
    unittest.main()
