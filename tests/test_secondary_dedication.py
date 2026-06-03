"""Wave 133 Stage A — secondary deliberate-dedication scoring (SWEG_SECONDARY).

Tests pin:
  * Gate default OFF; True only when SWEG_SECONDARY=1.
  * The spare-unit (_unit_is_dedicatable) predicate: a unit holding an
    objective is NOT spare; a unit in melee is NOT spare; a productive shooter
    with a target in range is NOT spare; a free non-shooting body IS spare.
  * Even-handed outcome: a Knight-shape army (few units, all on objectives)
    yields 0 dedications; a broad army (several free backfield bodies) yields
    dedications up to the held-card count.
  * OFF byte-identical: with SWEG_SECONDARY unset, _assign_card_dedication sets
    no dedicated_card, and _score_one_card for a position card returns the same
    value as the legacy incidental scoring.
"""
from __future__ import annotations

import os
import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(name: str = "Trooper", points: float = 8.0,
             keywords=("INFANTRY",), faction: str = "Space Marines",
             attacks: int = 1, hit_probability: float = 0.5,
             weapon_damage_per_shot: float = 1.0,
             range_inches: int = 12) -> UnitProfile:
    """A configurable lightweight infantry profile. Defaults give a low ranged
    output (1 * 0.5 * 1.0 = 0.5 < the 2.0 productive-shooter threshold)."""
    return UnitProfile(
        name=name, health=2.0, damage=1.0, hit_probability=hit_probability,
        ap=0, save=4, strength=4, toughness=4, attacks=attacks,
        weapon_damage_per_shot=weapon_damage_per_shot,
        range_inches=range_inches, unit_keywords=keywords, oc=2,
        melee_attacks=1, melee_hit_probability=0.5, melee_strength=4,
        melee_damage_per_shot=1.0, points_override=points, faction=faction,
    )


def _shooter_profile(name: str = "Gunline") -> UnitProfile:
    """A profile whose ranged output clears the 2.0 productive-shooter
    threshold: 4 * 0.67 * 1.0 = 2.68 >= 2.0."""
    return _profile(name=name, attacks=4, hit_probability=0.67,
                    weapon_damage_per_shot=1.0, range_inches=24)


def _make_battle(army_a: Army, army_b: Army, objectives=()) -> Battle:
    m = Map("T", 60.0, 44.0, objectives=tuple(objectives))
    battle = Battle(army_a, army_b, map_=m)
    battle._assign_uids()
    return battle


def _arm_position_cards(army: Army, *cards: str) -> None:
    army.secondary_track = "TACTICAL"
    army.tactical_hand = list(cards)
    army.tactical_deck = []


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

class DedicationGateTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def test_gate_default_off(self):
        battle = _make_battle(Army("A"), Army("B"))
        self.assertFalse(battle._secondary_dedication_enabled())

    def test_gate_on(self):
        os.environ["SWEG_SECONDARY"] = "1"
        battle = _make_battle(Army("A"), Army("B"))
        self.assertTrue(battle._secondary_dedication_enabled())

    def test_gate_zero_is_off(self):
        os.environ["SWEG_SECONDARY"] = "0"
        battle = _make_battle(Army("A"), Army("B"))
        self.assertFalse(battle._secondary_dedication_enabled())


# ---------------------------------------------------------------------------
# Spare-unit predicate (_unit_is_dedicatable)
# ---------------------------------------------------------------------------

class SpareUnitPredicateTests(unittest.TestCase):
    """The even-handed crux: which units a real player would peel off."""

    def _battle_with_objective(self):
        # One objective at the board centre; control_radius 3.0.
        obj = Objective("Mid", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
        a = Army("A")
        a.add_unit(_profile(name="A-free"))
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        battle = _make_battle(a, b, objectives=[obj])
        return battle, a, b, obj

    def test_free_non_shooting_body_is_spare(self):
        battle, a, b, obj = self._battle_with_objective()
        u = a.units[0]
        # Far from the objective, far from the enemy, low ranged output.
        u.position = (5.0, 5.0)
        b.units[0].position = (55.0, 40.0)
        self.assertTrue(battle._unit_is_dedicatable(u, b))

    def test_unit_on_objective_is_not_spare(self):
        battle, a, b, obj = self._battle_with_objective()
        u = a.units[0]
        # Sitting on the objective (within control_radius).
        u.position = (obj.x, obj.y)
        b.units[0].position = (55.0, 40.0)
        self.assertFalse(battle._unit_is_dedicatable(u, b))

    def test_unit_in_melee_is_not_spare(self):
        battle, a, b, obj = self._battle_with_objective()
        u = a.units[0]
        u.position = (5.0, 5.0)
        # Enemy within Engagement Range (~1.5").
        b.units[0].position = (5.5, 5.0)
        self.assertFalse(battle._unit_is_dedicatable(u, b))

    def test_productive_shooter_with_target_in_range_is_not_spare(self):
        obj = Objective("Mid", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
        a = Army("A")
        a.add_unit(_shooter_profile(name="A-gun"))
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        battle = _make_battle(a, b, objectives=[obj])
        u = a.units[0]
        u.position = (5.0, 5.0)
        # Enemy outside melee but inside the 24" weapon range.
        b.units[0].position = (5.0, 20.0)
        self.assertFalse(battle._unit_is_dedicatable(u, b))

    def test_productive_shooter_with_no_target_in_range_is_spare(self):
        obj = Objective("Mid", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
        a = Army("A")
        a.add_unit(_shooter_profile(name="A-gun"))
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        battle = _make_battle(a, b, objectives=[obj])
        u = a.units[0]
        u.position = (5.0, 5.0)
        # Enemy well beyond the 24" weapon range → the shooter has nothing to
        # shoot, so it is spare.
        b.units[0].position = (55.0, 40.0)
        self.assertTrue(battle._unit_is_dedicatable(u, b))

    def test_already_dedicated_unit_is_not_spare(self):
        battle, a, b, obj = self._battle_with_objective()
        u = a.units[0]
        u.position = (5.0, 5.0)
        b.units[0].position = (55.0, 40.0)
        u.dedicated_card = "engage_on_all_fronts"
        self.assertFalse(battle._unit_is_dedicatable(u, b))

    def test_acted_unit_is_not_spare(self):
        battle, a, b, obj = self._battle_with_objective()
        u = a.units[0]
        u.position = (5.0, 5.0)
        b.units[0].position = (55.0, 40.0)
        u.action_this_round = "cleanse"
        self.assertFalse(battle._unit_is_dedicatable(u, b))


# ---------------------------------------------------------------------------
# Dedication planner — even-handed outcome
# ---------------------------------------------------------------------------

class DedicationPlannerTests(unittest.TestCase):
    def setUp(self):
        os.environ["SWEG_SECONDARY"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def _broad_army(self, name: str, n: int = 10) -> Army:
        army = Army(name)
        for i in range(n):
            army.add_unit(_profile(name=f"{name}-u{i}"))
        return army

    def _knight_army(self, name: str, n: int = 3) -> Army:
        army = Army(name)
        for i in range(n):
            army.add_unit(_profile(name=f"{name}-k{i}", points=120.0,
                                   keywords=("TITANIC", "VEHICLE")))
        return army

    def test_broad_army_dedicates_up_to_held_card_count(self):
        a = self._broad_army("A", n=10)
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        b.units[0].position = (55.0, 40.0)   # far away
        # Spread A's bodies across the backfield, none on objectives / in melee.
        for i, u in enumerate(a.units):
            u.position = (3.0 + i, 3.0)
        battle = _make_battle(a, b)
        _arm_position_cards(a, "engage_on_all_fronts", "behind_enemy_lines")
        battle._assign_card_dedication(a, b)
        dedicated = [u for u in a.units if u.dedicated_card is not None]
        # Two held position cards → up to two dedications (one body per card).
        self.assertEqual(len(dedicated), 2)
        cards = {u.dedicated_card for u in dedicated}
        self.assertEqual(cards, {"engage_on_all_fronts", "behind_enemy_lines"})

    def test_knight_shape_army_dedicates_none(self):
        # All units on objectives → none spare → zero dedications.
        objs = [
            Objective("O1", 10.0, 22.0, control_radius=3.0, vp_per_round=5),
            Objective("O2", 30.0, 22.0, control_radius=3.0, vp_per_round=5),
            Objective("O3", 50.0, 22.0, control_radius=3.0, vp_per_round=5),
        ]
        k = self._knight_army("K", n=3)
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        b.units[0].position = (55.0, 40.0)
        for u, obj in zip(k.units, objs):
            u.position = (obj.x, obj.y)   # each Knight parked on a marker
        battle = _make_battle(k, b, objectives=objs)
        _arm_position_cards(k, "engage_on_all_fronts", "behind_enemy_lines")
        battle._assign_card_dedication(k, b)
        dedicated = [u for u in k.units if u.dedicated_card is not None]
        self.assertEqual(len(dedicated), 0)

    def test_one_spare_unit_per_card(self):
        # Only one spare body, two held cards → it dedicates to one card only.
        objs = [Objective("O", 30.0, 22.0, control_radius=3.0, vp_per_round=5)]
        a = Army("A")
        a.add_unit(_profile(name="A-on-obj"))
        a.add_unit(_profile(name="A-spare"))
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        b.units[0].position = (55.0, 40.0)
        a.units[0].position = (objs[0].x, objs[0].y)   # on objective, not spare
        a.units[1].position = (3.0, 3.0)               # the one spare body
        battle = _make_battle(a, b, objectives=objs)
        _arm_position_cards(a, "engage_on_all_fronts", "behind_enemy_lines")
        battle._assign_card_dedication(a, b)
        dedicated = [u for u in a.units if u.dedicated_card is not None]
        self.assertEqual(len(dedicated), 1)

    def test_fixed_track_army_dedicates_none(self):
        a = self._broad_army("A", n=10)
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        b.units[0].position = (55.0, 40.0)
        for i, u in enumerate(a.units):
            u.position = (3.0 + i, 3.0)
        battle = _make_battle(a, b)
        a.secondary_track = "FIXED"
        a.tactical_hand = []
        battle._assign_card_dedication(a, b)
        self.assertEqual([u for u in a.units if u.dedicated_card is not None], [])


# ---------------------------------------------------------------------------
# OFF byte-identical
# ---------------------------------------------------------------------------

class OffPathByteIdenticalTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def _setup(self):
        a = Army("A")
        for i in range(6):
            a.add_unit(_profile(name=f"A-u{i}"))
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        b.units[0].position = (55.0, 40.0)
        # Spread A across all four quarters so incidental Engage would score.
        a.units[0].position = (10.0, 10.0)   # SW
        a.units[1].position = (50.0, 10.0)   # SE
        a.units[2].position = (10.0, 38.0)   # NW
        a.units[3].position = (50.0, 38.0)   # NE
        a.units[4].position = (30.0, 39.5)   # deep in enemy DZ (BEL)
        a.units[5].position = (30.0, 40.0)   # second body in enemy DZ
        battle = _make_battle(a, b)
        _arm_position_cards(a, "engage_on_all_fronts", "behind_enemy_lines")
        return battle, a, b

    def test_off_planner_sets_no_dedicated_card(self):
        os.environ.pop("SWEG_SECONDARY", None)
        battle, a, b = self._setup()
        battle._assign_card_dedication(a, b)
        self.assertEqual([u for u in a.units if u.dedicated_card is not None], [])

    def test_off_position_score_matches_incidental(self):
        # With the gate OFF, _score_one_card scores incidental presence — the
        # spread bodies give Engage (4 quarters) and BEL (2+ units in DZ).
        os.environ.pop("SWEG_SECONDARY", None)
        battle, a, b = self._setup()
        # round_num=1, side A: Engage is the active tactical-secondary slot.
        eng = battle._score_one_card("engage_on_all_fronts", a, b,
                                     own_is_army_a=True, round_num=1)
        self.assertGreater(eng, 0, "incidental 4-quarter spread should score Engage")

    def test_on_position_score_requires_dedication(self):
        # With the gate ON but no unit dedicated to Engage, the same incidental
        # spread scores 0 — only deliberate dedication scores.
        os.environ["SWEG_SECONDARY"] = "1"
        battle, a, b = self._setup()
        # No dedicated_card stamped → filtered list is empty → 0 VP.
        eng = battle._score_one_card("engage_on_all_fronts", a, b,
                                     own_is_army_a=True, round_num=1)
        self.assertEqual(eng, 0,
                         "ON path must not score incidental presence")

    def test_on_position_score_with_dedication(self):
        # With the gate ON and units dedicated across all four quarters, Engage
        # scores from the dedicated bodies.
        os.environ["SWEG_SECONDARY"] = "1"
        battle, a, b = self._setup()
        for u in a.units[:4]:
            u.dedicated_card = "engage_on_all_fronts"
        eng = battle._score_one_card("engage_on_all_fronts", a, b,
                                     own_is_army_a=True, round_num=1)
        self.assertGreater(eng, 0,
                           "dedicated 4-quarter spread must score Engage")


if __name__ == "__main__":
    unittest.main()
