"""Base-edge Objective Control range under collision — wave 211, gated SWEG_COLLISION.

10e measures range to the CLOSEST POINT of a model's base ("Measuring Distances"),
so a model is within an objective marker's control range when its base edge reaches
within the radius: centre-distance - base_radius <= control_radius. The collision-OFF
baseline keeps the centre-only approximation; under no-overlap collision a big base
(a 170mm Imperial Knight) physically pushes enemy CENTRES past 3" of a marker it sits
on, which under the centre-only check would unfaithfully evict base-to-base contesters
whose base edge is still within range. This pins the gated fix in `_assign_army_oc`.

Cited simulator.objective_control_base_range (data/rule_citations.d/keywords_and_mechanics.json).
"""

from __future__ import annotations

import os
import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


def _knight(oc: int = 5) -> UnitProfile:
    # Imperial-Knight-sized oval base (170 x 105 mm). base_radius ~= 2.71".
    return UnitProfile(
        name="Knight", health=22.0, damage=6.0, hit_probability=0.66, ap=2, save=3,
        strength=12, toughness=12, attacks=4, weapon_damage_per_shot=6.0,
        range_inches=36, unit_keywords=("VEHICLE", "TITANIC"), oc=oc,
        melee_attacks=4, melee_hit_probability=0.66, melee_strength=12,
        melee_damage_per_shot=6.0,
        base_shape="oval", base_width_mm=170, base_length_mm=105,
    )


def _trooper(oc: int = 1) -> UnitProfile:
    # Default 32mm round base. base_radius ~= 0.63".
    return UnitProfile(
        name="Trooper", health=2.0, damage=1.0, hit_probability=0.5, ap=0, save=4,
        strength=4, toughness=4, attacks=1, weapon_damage_per_shot=1.0,
        range_inches=24, unit_keywords=("INFANTRY",), oc=oc,
        melee_attacks=1, melee_hit_probability=0.5, melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _battle():
    obj = Objective("Centre", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
    army_a = Army("A"); army_a.add_unit(_knight(oc=5))      # Knight on the marker
    army_b = Army("B"); army_b.add_unit(_trooper(oc=6))     # bodies just outside 3" centre
    battle = Battle(army_a, army_b, map_=Map("T", 60.0, 44.0, objectives=(obj,)))
    battle._assign_uids()
    battle._current_round = 2
    battle._a_vp = 0; battle._b_vp = 0
    battle._sticky_owner = {}
    battle._battleshocked_this_round = set()
    # Knight centred on the marker; trooper centre 3.4" away (centre OUTSIDE 3",
    # but base edge 3.4 - 0.63 = 2.77" <= 3" → within range when base-aware).
    battle.a.units[0].position = (30.0, 22.0)
    battle.b.units[0].position = (30.0, 25.4)
    return battle


class BaseRangeContestTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SWEG_COLLISION", None)

    def test_off_centre_only_knight_holds_uncontested(self):
        # Collision OFF (SWEG_COLLISION=0 — collision is DEFAULT-ON now, so OFF must
        # be set explicitly): the trooper's CENTRE is 3.4" out → not within 3" → it
        # does not contest → the Knight (OC 5 > 0) controls and A scores 5.
        os.environ["SWEG_COLLISION"] = "0"
        b = _battle()
        a0 = b._a_vp
        b._score_objectives()
        self.assertEqual(b._a_vp, a0 + 5, "Knight holds uncontested under centre-only OC")

    def test_on_base_edge_trooper_contests_and_out_controls(self):
        # Collision ON: base-aware range → the trooper's base edge (2.77") is
        # within 3" → it contests with OC 6 > the Knight's 5 → B controls →
        # A does NOT score its primary.
        os.environ["SWEG_COLLISION"] = "1"
        b = _battle()
        a0 = b._a_vp
        b._score_objectives()
        self.assertEqual(b._a_vp, a0, "base-to-base bodies contest the Knight's marker under collision")

    def test_gate_default_on_zero_reverts(self):
        # Collision is DEFAULT-ON (user ruling 2026-06-07): the base-aware OC contest
        # fires by default and SWEG_COLLISION=0 reverts to the legacy centre-only OC,
        # consistent with the movement collision gate (_bc_collision_kwargs uses the
        # same `!= "0"` default-on convention).
        os.environ["SWEG_COLLISION"] = "0"                       # revert → centre-only
        b = _battle()
        a0 = b._a_vp
        b._score_objectives()
        self.assertEqual(b._a_vp, a0 + 5, "=0 reverts to legacy centre-only OC (Knight holds)")
        os.environ.pop("SWEG_COLLISION", None)                  # default → base-aware ON
        b2 = _battle()
        a0 = b2._a_vp
        b2._score_objectives()
        self.assertEqual(b2._a_vp, a0, "default-ON: base-to-base bodies contest the marker")


if __name__ == "__main__":
    unittest.main()
