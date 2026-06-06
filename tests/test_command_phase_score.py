"""Per-Command-phase primary scoring — wave 116, env-gated SWEG_CMDSCORE.

The eval runs vanilla 10e I-go-you-go turns (Battle._run_round_vanilla_turns).
The baseline scores Primary VP ONCE per round, at end of round after BOTH players'
turns, which credits only the post-combat survivor (the durable holder). 10e
instead scores each player's Primary at its own Command phase (the start of its
turn). This layer, gated ON, scores per player at its Command phase via
Battle._score_objectives(only_for=<that army>) and skips the end-of-round score.

These tests pin the core piece — the only_for award filter — and the gate flag.
Cited `simulator.primary_vp_command_phase` (data/rule_citations.d/core_primary_vp_cap.json).
"""

from __future__ import annotations

import os
import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


def _holder(name: str = "Holder", oc: int = 4) -> UnitProfile:
    return UnitProfile(
        name=name, health=4.0, damage=1.0, hit_probability=0.5, ap=0, save=4,
        strength=4, toughness=4, attacks=1, weapon_damage_per_shot=1.0,
        range_inches=12, unit_keywords=("INFANTRY",), oc=oc,
        melee_attacks=1, melee_hit_probability=0.5, melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _battle_one_objective():
    obj = Objective("Centre", 30.0, 22.0, control_radius=3.0, vp_per_round=5)
    army_a = Army("A"); army_a.add_unit(_holder())
    army_b = Army("B"); army_b.add_unit(_holder())
    battle = Battle(army_a, army_b, map_=Map("T", 60.0, 44.0, objectives=(obj,)))
    battle._assign_uids()
    battle._current_round = 2
    battle._a_vp = 0; battle._b_vp = 0
    battle._sticky_owner = {}
    return battle, obj


class OnlyForAwardFilterTests(unittest.TestCase):
    def test_only_for_awards_just_that_army(self):
        battle, obj = _battle_one_objective()
        # A stands on the objective; B is far away → A controls it.
        battle.a.units[0].position = (30.0, 22.0)
        battle.b.units[0].position = (5.0, 40.0)

        # Score for A only → A gains 5, B unchanged.
        a0, b0 = battle._a_vp, battle._b_vp
        battle._score_objectives(only_for="A")
        self.assertEqual(battle._a_vp, a0 + 5)
        self.assertEqual(battle._b_vp, b0)

        # Score for B only → nobody on B's side controls → no change.
        a1, b1 = battle._a_vp, battle._b_vp
        battle._score_objectives(only_for="B")
        self.assertEqual(battle._a_vp, a1)
        self.assertEqual(battle._b_vp, b1)

    def test_none_scores_both_as_before(self):
        battle, obj = _battle_one_objective()
        battle.a.units[0].position = (30.0, 22.0)   # A controls
        battle.b.units[0].position = (5.0, 40.0)
        a0 = battle._a_vp
        battle._score_objectives()   # baseline both-sides path
        self.assertEqual(battle._a_vp, a0 + 5)

    def test_per_round_cap_applies_per_call(self):
        # A holds three objectives → 15 VP; only_for still caps at 15/round.
        objs = tuple(
            Objective(f"O{i}", 10.0 + i * 8, 22.0, 3.0, 5) for i in range(4)
        )
        army_a = Army("A")
        for i in range(4):
            army_a.add_unit(_holder())
        army_b = Army("B"); army_b.add_unit(_holder())
        battle = Battle(army_a, army_b, map_=Map("T", 60.0, 44.0, objectives=objs))
        battle._assign_uids(); battle._current_round = 2
        battle._a_vp = 0; battle._b_vp = 0; battle._sticky_owner = {}
        for i, u in enumerate(battle.a.units):
            u.position = (10.0 + i * 8, 22.0)        # one A unit on each of 4 objs
        battle.b.units[0].position = (5.0, 40.0)
        a0 = battle._a_vp
        battle._score_objectives(only_for="A")
        self.assertEqual(battle._a_vp - a0, 15, "primary capped at 15/round")


class GateFlagTests(unittest.TestCase):
    def test_gate_flag_reads_env(self):
        battle, _ = _battle_one_objective()
        self.assertFalse(battle._cmd_score)
        os.environ["SWEG_CMDSCORE"] = "1"
        try:
            army_a = Army("A"); army_a.add_unit(_holder())
            army_b = Army("B"); army_b.add_unit(_holder())
            b2 = Battle(army_a, army_b, map_=Map("T", 60.0, 44.0))
            self.assertTrue(b2._cmd_score)
        finally:
            os.environ.pop("SWEG_CMDSCORE", None)


if __name__ == "__main__":
    unittest.main()
