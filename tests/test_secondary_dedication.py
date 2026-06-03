"""Wave 135 — authentic secondary economy (SWEG_SECONDARY).

The wave-133 build gated POSITION-card scoring (Engage on All Fronts / Behind
Enemy Lines) on a `dedicated_card` flag. That was reverted in wave 135 as
unfaithful: those are POSITIONAL Secondaries that score on presence/occupancy
at end of turn — no Action, no "dedication". The rules-clean low-unit penalty
now lives on the ACTION cards (Cleanse / Sabotage) via the 10e Actions cost:
performing an Action forfeits the unit's shooting and charge for the turn, and
the Action scores only if the unit completes it (survives, not dragged into
melee).

Tests pin:
  * Gate default OFF; True only when SWEG_SECONDARY=1.
  * The spare-unit (`_unit_is_dedicatable`) predicate — KEPT, even-handed: a
    unit holding an objective / in melee / a productive shooter is NOT spare.
  * The dedication planner sets a POSITIONING bias (`pursue_target`) and no
    longer gates scoring.
  * Position cards score on INCIDENTAL presence whether SWEG_SECONDARY is on or
    off (the reverted scoring gate).
  * The Action-card cost (`_unit_can_perform_action` / `_action_completes`):
    a committing unit must have Objective Control > 0, be outside Engagement
    Range, and survive to score; a Knight-shape army (no spare unit) scores the
    Action card 0, a broad army scores it.
  * OFF byte-identical: with SWEG_SECONDARY unset, position cards score
    incidentally AND the Action cards use the legacy chaff-selection /
    still-alive scoring.
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
             range_inches: int = 12, oc: int = 2) -> UnitProfile:
    """A configurable lightweight infantry profile. Defaults give a low ranged
    output (1 * 0.5 * 1.0 = 0.5 < the 2.0 productive-shooter threshold)."""
    return UnitProfile(
        name=name, health=2.0, damage=1.0, hit_probability=hit_probability,
        ap=0, save=4, strength=4, toughness=4, attacks=attacks,
        weapon_damage_per_shot=weapon_damage_per_shot,
        range_inches=range_inches, unit_keywords=keywords, oc=oc,
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
# Spare-unit predicate (_unit_is_dedicatable) — KEPT, even-handed.
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
# Dedication planner — now a POSITIONING bias only (sets pursue_target).
# ---------------------------------------------------------------------------

class DedicationPlannerBiasTests(unittest.TestCase):
    def setUp(self):
        os.environ["SWEG_SECONDARY"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def _broad_army(self, name: str, n: int = 10) -> Army:
        army = Army(name)
        for i in range(n):
            army.add_unit(_profile(name=f"{name}-u{i}"))
        return army

    def test_planner_sets_pursue_target_toward_card_goal(self):
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
        # The planner peels one spare unit per held card and BIASES its move
        # (pursue_target) toward the card's geography — a positioning bias, not
        # a scoring gate.
        biased = [u for u in a.units if u.pursue_target is not None]
        self.assertEqual(len(biased), 2)

    def test_knight_shape_army_gets_no_bias(self):
        # All units on objectives → none spare → no positioning bias set.
        objs = [
            Objective("O1", 10.0, 22.0, control_radius=3.0, vp_per_round=5),
            Objective("O2", 30.0, 22.0, control_radius=3.0, vp_per_round=5),
            Objective("O3", 50.0, 22.0, control_radius=3.0, vp_per_round=5),
        ]
        k = Army("K")
        for i in range(3):
            k.add_unit(_profile(name=f"K-k{i}", points=120.0,
                                keywords=("TITANIC", "VEHICLE")))
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        b.units[0].position = (55.0, 40.0)
        for u, obj in zip(k.units, objs):
            u.position = (obj.x, obj.y)   # each Knight parked on a marker
        battle = _make_battle(k, b, objectives=objs)
        _arm_position_cards(k, "engage_on_all_fronts", "behind_enemy_lines")
        battle._assign_card_dedication(k, b)
        self.assertEqual([u for u in k.units if u.pursue_target is not None], [])

    def test_fixed_track_army_gets_no_bias(self):
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
        self.assertEqual([u for u in a.units if u.pursue_target is not None], [])

    def test_planner_off_sets_no_bias(self):
        os.environ.pop("SWEG_SECONDARY", None)
        a = self._broad_army("A", n=10)
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        b.units[0].position = (55.0, 40.0)
        for i, u in enumerate(a.units):
            u.position = (3.0 + i, 3.0)
        battle = _make_battle(a, b)
        _arm_position_cards(a, "engage_on_all_fronts", "behind_enemy_lines")
        battle._assign_card_dedication(a, b)
        self.assertEqual([u for u in a.units if u.pursue_target is not None], [])


# ---------------------------------------------------------------------------
# Position-card scoring — REVERTED: incidental presence scores, gate or no gate.
# ---------------------------------------------------------------------------

class PositionCardIncidentalScoringTests(unittest.TestCase):
    """Engage / BEL are positional Secondaries; they score on incidental
    presence at end of turn, whether or not SWEG_SECONDARY is on. The wave-133
    dedication scoring gate was removed as unfaithful."""

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

    def test_off_position_score_is_incidental(self):
        os.environ.pop("SWEG_SECONDARY", None)
        battle, a, b = self._setup()
        eng = battle._score_one_card("engage_on_all_fronts", a, b,
                                     own_is_army_a=True, round_num=1)
        self.assertGreater(eng, 0, "incidental 4-quarter spread should score Engage")

    def test_on_position_score_still_incidental(self):
        # The KEY rebuild assertion: with the gate ON and NO unit dedicated to
        # Engage, the incidental spread STILL scores — the position-card scoring
        # gate was reverted. (Pre-rebuild this returned 0.)
        os.environ["SWEG_SECONDARY"] = "1"
        battle, a, b = self._setup()
        eng = battle._score_one_card("engage_on_all_fronts", a, b,
                                     own_is_army_a=True, round_num=1)
        self.assertGreater(eng, 0,
                           "ON path must score incidental presence (gate reverted)")

    def test_on_and_off_position_score_match(self):
        # Position scoring is identical ON vs OFF (byte-identical scoring path).
        os.environ.pop("SWEG_SECONDARY", None)
        battle_off, a_off, b_off = self._setup()
        off_eng = battle_off._score_one_card("engage_on_all_fronts", a_off, b_off,
                                             own_is_army_a=True, round_num=1)
        os.environ["SWEG_SECONDARY"] = "1"
        battle_on, a_on, b_on = self._setup()
        on_eng = battle_on._score_one_card("engage_on_all_fronts", a_on, b_on,
                                           own_is_army_a=True, round_num=1)
        self.assertEqual(off_eng, on_eng)


# ---------------------------------------------------------------------------
# Action-card cost — Cleanse / Sabotage require a genuine Action (SWEG_SECONDARY).
# ---------------------------------------------------------------------------

class ActionCostPredicateTests(unittest.TestCase):
    """`_unit_can_perform_action` / `_action_completes`: the rules-authentic
    Action contract — OC>0, outside Engagement Range, survive to score."""

    def _battle(self, a_oc: int = 2, attacks: int = 1):
        a = Army("A")
        a.add_unit(_profile(name="A-act", oc=a_oc, attacks=attacks,
                            hit_probability=0.67))
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        battle = _make_battle(a, b)
        return battle, a, b

    def test_clean_body_can_perform_action(self):
        battle, a, b = self._battle()
        a.units[0].position = (30.0, 22.0)
        b.units[0].position = (55.0, 40.0)   # far away
        self.assertTrue(battle._unit_can_perform_action(a.units[0], b))

    def test_oc_zero_cannot_perform_action(self):
        battle, a, b = self._battle(a_oc=0)
        a.units[0].position = (30.0, 22.0)
        b.units[0].position = (55.0, 40.0)
        self.assertFalse(battle._unit_can_perform_action(a.units[0], b))

    def test_in_engagement_cannot_perform_action(self):
        battle, a, b = self._battle()
        a.units[0].position = (30.0, 22.0)
        b.units[0].position = (31.0, 22.0)   # within ~1.5" Engagement Range
        self.assertFalse(battle._unit_can_perform_action(a.units[0], b))

    def test_productive_shooter_with_target_cannot_perform_action(self):
        battle, a, b = self._battle(attacks=4)   # 4 * 0.67 * 1.0 = 2.68 >= 2.0
        a.units[0].position = (30.0, 22.0)
        b.units[0].position = (30.0, 30.0)   # inside the 12" weapon range
        self.assertFalse(battle._unit_can_perform_action(a.units[0], b))

    def test_already_acted_cannot_perform_action(self):
        battle, a, b = self._battle()
        a.units[0].position = (30.0, 22.0)
        b.units[0].position = (55.0, 40.0)
        a.units[0].action_this_round = "cleanse"
        self.assertFalse(battle._unit_can_perform_action(a.units[0], b))

    def test_completion_requires_alive(self):
        battle, a, b = self._battle()
        u = a.units[0]
        u.position = (30.0, 22.0)
        b.units[0].position = (55.0, 40.0)
        self.assertTrue(battle._action_completes(u, b))
        u.current_health = 0.0   # died during the turn
        self.assertFalse(battle._action_completes(u, b))

    def test_completion_requires_not_in_engagement(self):
        battle, a, b = self._battle()
        u = a.units[0]
        u.position = (30.0, 22.0)
        b.units[0].position = (55.0, 40.0)
        self.assertTrue(battle._action_completes(u, b))
        b.units[0].position = (31.0, 22.0)   # dragged into melee
        self.assertFalse(battle._action_completes(u, b))


class CleanseActionCostTests(unittest.TestCase):
    """End-to-end Cleanse assignment + scoring under the Action-cost contract."""

    def setUp(self):
        os.environ["SWEG_SECONDARY"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def _battle(self, a_oc: int = 2, attacks: int = 1):
        # Forward objective (No Man's Land, outside A's low-y DZ).
        obj = Objective("Fwd", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
        a = Army("A")
        a.add_unit(_profile(name="A-act", oc=a_oc, attacks=attacks,
                            hit_probability=0.67))
        a.chosen_secondaries = ("cleanse",)
        b = Army("B")
        b.add_unit(_profile(name="B-1", oc=0))   # no enemy OC contest
        battle = _make_battle(a, b, objectives=[obj])
        a.units[0].position = (obj.x, obj.y)     # on the controlled marker
        b.units[0].position = (55.0, 40.0)       # far away
        return battle, a, b, obj

    def test_clean_commit_scores(self):
        battle, a, b, obj = self._battle()
        battle._assign_cleanse_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "cleanse")
        vp = battle._score_cleanse(a, b, own_is_army_a=True)
        self.assertEqual(vp, 2)

    def test_oc_zero_does_not_score(self):
        battle, a, b, obj = self._battle(a_oc=0)
        battle._assign_cleanse_actions(a, b)
        # OC-0 unit is not eligible to start the action.
        self.assertIsNone(a.units[0].action_this_round)
        vp = battle._score_cleanse(a, b, own_is_army_a=True)
        self.assertEqual(vp, 0)

    def test_dragged_into_engagement_does_not_score(self):
        battle, a, b, obj = self._battle()
        battle._assign_cleanse_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "cleanse")
        # The opponent's turn drags the cleanser into melee → action fails.
        b.units[0].position = (obj.x + 1.0, obj.y)
        vp = battle._score_cleanse(a, b, own_is_army_a=True)
        self.assertEqual(vp, 0)

    def test_death_does_not_score(self):
        battle, a, b, obj = self._battle()
        battle._assign_cleanse_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "cleanse")
        a.units[0].current_health = 0.0   # killed during the opponent's turn
        vp = battle._score_cleanse(a, b, own_is_army_a=True)
        self.assertEqual(vp, 0)


class SabotageActionCostTests(unittest.TestCase):
    """End-to-end Sabotage assignment + scoring under the Action-cost contract."""

    def setUp(self):
        os.environ["SWEG_SECONDARY"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def _battle(self, a_oc: int = 2):
        a = Army("A")
        a.add_unit(_profile(name="A-sab", oc=a_oc))
        a.chosen_secondaries = ("sabotage",)
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        battle = _make_battle(a, b)
        # No Man's Land (12 < y < 32 on a height-44 map), outside A's DZ.
        a.units[0].position = (30.0, 22.0)
        b.units[0].position = (55.0, 40.0)
        return battle, a, b

    def test_clean_commit_scores_nml(self):
        battle, a, b = self._battle()
        battle._assign_sabotage_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "sabotage")
        vp = battle._score_sabotage(a, own_is_army_a=True, opponent=b)
        self.assertEqual(vp, 3)   # 3 VP in No Man's Land

    def test_oc_zero_does_not_score(self):
        battle, a, b = self._battle(a_oc=0)
        battle._assign_sabotage_actions(a, b)
        self.assertIsNone(a.units[0].action_this_round)
        vp = battle._score_sabotage(a, own_is_army_a=True, opponent=b)
        self.assertEqual(vp, 0)

    def test_in_engagement_not_assigned(self):
        battle, a, b = self._battle()
        b.units[0].position = (31.0, 22.0)   # within Engagement Range
        battle._assign_sabotage_actions(a, b)
        self.assertIsNone(a.units[0].action_this_round)

    def test_dragged_into_engagement_does_not_score(self):
        battle, a, b = self._battle()
        battle._assign_sabotage_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "sabotage")
        b.units[0].position = (31.0, 22.0)   # dragged into melee
        vp = battle._score_sabotage(a, own_is_army_a=True, opponent=b)
        self.assertEqual(vp, 0)

    def test_death_does_not_score(self):
        battle, a, b = self._battle()
        battle._assign_sabotage_actions(a, b)
        a.units[0].current_health = 0.0
        vp = battle._score_sabotage(a, own_is_army_a=True, opponent=b)
        self.assertEqual(vp, 0)


class ActionCardEmergentAsymmetryTests(unittest.TestCase):
    """The headline: a Knight-shape army (no spare body) scores the Action card
    0; a broad army scores it. EMERGENT from unit count — no faction branch."""

    def setUp(self):
        os.environ["SWEG_SECONDARY"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def test_knight_shape_scores_cleanse_zero(self):
        # A single big unit that is a productive shooter with the enemy in range
        # — it cannot spare itself to perform the action.
        obj = Objective("Fwd", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
        k = Army("K")
        k.add_unit(_profile(name="K-knight", points=400.0, oc=4,
                            keywords=("TITANIC", "VEHICLE"),
                            attacks=12, hit_probability=0.67,
                            weapon_damage_per_shot=3.0, range_inches=36))
        k.chosen_secondaries = ("cleanse",)
        b = Army("B")
        b.add_unit(_profile(name="B-1", oc=0))
        battle = _make_battle(k, b, objectives=[obj])
        k.units[0].position = (obj.x, obj.y)
        b.units[0].position = (30.0, 30.0)   # in the Knight's 36" range
        battle._assign_cleanse_actions(k, b)
        self.assertIsNone(k.units[0].action_this_round,
                          "a productive Knight cannot spare itself for an action")
        vp = battle._score_cleanse(k, b, own_is_army_a=True)
        self.assertEqual(vp, 0)

    def test_broad_army_scores_cleanse(self):
        # A broad army has a spare non-shooting body on the marker → it scores.
        obj = Objective("Fwd", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
        a = Army("A")
        for i in range(8):
            a.add_unit(_profile(name=f"A-u{i}"))
        a.chosen_secondaries = ("cleanse",)
        b = Army("B")
        b.add_unit(_profile(name="B-1", oc=0))
        battle = _make_battle(a, b, objectives=[obj])
        # Put one body on the controlled marker; the rest in the backfield.
        a.units[0].position = (obj.x, obj.y)
        for i, u in enumerate(a.units[1:]):
            u.position = (3.0 + i, 3.0)
        b.units[0].position = (55.0, 40.0)
        battle._assign_cleanse_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "cleanse")
        vp = battle._score_cleanse(a, b, own_is_army_a=True)
        self.assertEqual(vp, 2)


# ---------------------------------------------------------------------------
# OFF byte-identical — Action cards use the legacy chaff-selection / still-alive
# scoring; position cards score incidentally (covered above).
# ---------------------------------------------------------------------------

class OffPathActionLegacyTests(unittest.TestCase):
    """With SWEG_SECONDARY unset, Cleanse / Sabotage use the legacy
    `_is_chaff_unit` selection and the still-alive (no Engagement-Range)
    completion check, exactly as before the rebuild."""

    def tearDown(self):
        os.environ.pop("SWEG_SECONDARY", None)

    def _cleanse_battle(self):
        obj = Objective("Fwd", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
        a = Army("A")
        # Cheap chaff (points < the chaff threshold) so the legacy gate selects it.
        a.add_unit(_profile(name="A-chaff", points=6.0))
        a.chosen_secondaries = ("cleanse",)
        b = Army("B")
        b.add_unit(_profile(name="B-1", oc=0))
        battle = _make_battle(a, b, objectives=[obj])
        a.units[0].position = (obj.x, obj.y)
        b.units[0].position = (55.0, 40.0)
        return battle, a, b, obj

    def test_off_cleanse_uses_legacy_chaff_selection(self):
        os.environ.pop("SWEG_SECONDARY", None)
        battle, a, b, obj = self._cleanse_battle()
        battle._assign_cleanse_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "cleanse")
        vp = battle._score_cleanse(a, b, own_is_army_a=True)
        self.assertEqual(vp, 2)

    def test_off_cleanse_scores_even_when_in_engagement(self):
        # The legacy completion check is "still alive on the marker" — it does
        # NOT require being outside Engagement Range. So a cleanser dragged into
        # melee STILL scores on the OFF path (byte-identical to pre-rebuild).
        os.environ.pop("SWEG_SECONDARY", None)
        battle, a, b, obj = self._cleanse_battle()
        battle._assign_cleanse_actions(a, b)
        b.units[0].position = (obj.x + 1.0, obj.y)   # dragged into melee
        vp = battle._score_cleanse(a, b, own_is_army_a=True)
        self.assertEqual(vp, 2, "OFF path keeps legacy still-alive scoring")

    def test_off_sabotage_uses_legacy_chaff_selection(self):
        os.environ.pop("SWEG_SECONDARY", None)
        a = Army("A")
        a.add_unit(_profile(name="A-chaff", points=6.0))
        a.chosen_secondaries = ("sabotage",)
        b = Army("B")
        b.add_unit(_profile(name="B-1"))
        battle = _make_battle(a, b)
        a.units[0].position = (30.0, 22.0)   # No Man's Land
        b.units[0].position = (55.0, 40.0)
        battle._assign_sabotage_actions(a, b)
        self.assertEqual(a.units[0].action_this_round, "sabotage")
        vp = battle._score_sabotage(a, own_is_army_a=True, opponent=b)
        self.assertEqual(vp, 3)


if __name__ == "__main__":
    unittest.main()
