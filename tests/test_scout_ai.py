"""Scout-destination AI (gated SWEG_SCOUT_AI) — the pre-game Scouts move's
DESTINATION is an AI tactical choice.

The Scouts move itself is the real 10e rule (cited `simulator.scout`); these
tests pin the DESTINATION policy:

  * Gate OFF (default): the scout moves toward the NEAREST ENEMY (legacy).
  * Gate ON: the scout moves toward the nearest FORWARD-BUT-SAFE contestable
    objective (board control), never ending past the midline by more than the
    safe margin, and never in a strictly worse position than it started — it
    HOLDS instead of charging the enemy when no forward-but-safe marker exists.

Scenario: the scout sits on its own side; the only enemy is placed BEHIND it
(toward its own home edge). Legacy then walks the scout backward toward the
enemy; the AI walks it forward toward the centreline objective. The two
policies move the scout in opposite directions, so the test is decisive.
"""
from __future__ import annotations

import os
import unittest

from code.army import Army
from code.simulator import Battle, _distance
from code.units import UnitProfile


def _scout_profile(name: str = "Scout", scout: int = 9, **overrides) -> UnitProfile:
    base = dict(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Astra Militarum",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        scout_distance=scout,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _plain_profile(name: str = "Enemy", **overrides) -> UnitProfile:
    base = dict(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Orks",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        scout_distance=0,
    )
    base.update(overrides)
    return UnitProfile(**base)


class ScoutDestinationAITests(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("SWEG_SCOUT_AI")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("SWEG_SCOUT_AI", None)
        else:
            os.environ["SWEG_SCOUT_AI"] = self._prev

    def _battle_with_scout_behind_enemy(self):
        a = Army("ScoutForce")
        a.add_unit(_scout_profile("Kasrkin", scout=9))
        b = Army("EnemyForce")
        b.add_unit(_plain_profile("Ork Boy"))
        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()
        cx = battle.map.width / 2.0
        cy = battle.map.height / 2.0
        scout = a.units[0]
        enemy = b.units[0]
        # Scout 20" back on its own (low-y) side; enemy 25" back (further from
        # the centreline). Nearest enemy is BEHIND the scout; the Centre
        # objective sits forward at the midline.
        scout.position = (cx, cy - 20.0)
        enemy.position = (cx, cy - 25.0)
        battle._fresh_arrivals = set()
        return battle, scout, enemy, cx, cy

    def test_gate_on_moves_forward_to_objective_not_toward_enemy(self):
        os.environ["SWEG_SCOUT_AI"] = "1"
        battle, scout, enemy, cx, cy = self._battle_with_scout_behind_enemy()
        start_y = scout.position[1]
        battle._run_scout_phase()
        end_y = scout.position[1]
        # Moved FORWARD (toward the centreline / objective), not backward toward
        # the behind-enemy.
        self.assertGreater(end_y, start_y,
            "AI scout should advance toward the forward objective, not the "
            "behind-enemy")
        # Did not overshoot deep into enemy territory.
        self.assertLessEqual(end_y, cy + 3.0 + 1e-6,
            "AI scout must not end more than the safe margin past the midline")
        # Ended at least as close to the forward Centre marker as it started.
        centre = min(battle.map.objectives,
                     key=lambda o: _distance((cx, cy), (o.x, o.y)))
        self.assertLess(
            _distance(scout.position, (centre.x, centre.y)),
            _distance((cx, start_y), (centre.x, centre.y)),
        )

    def test_gate_off_moves_toward_nearest_enemy(self):
        os.environ["SWEG_SCOUT_AI"] = "0"
        battle, scout, enemy, cx, cy = self._battle_with_scout_behind_enemy()
        start_y = scout.position[1]
        battle._run_scout_phase()
        end_y = scout.position[1]
        # Legacy: walks backward toward the behind-enemy.
        self.assertLess(end_y, start_y,
            "Legacy scout moves toward the nearest enemy (here, backward)")

    def test_scout_destination_excludes_backward_and_deep_markers(self):
        os.environ["SWEG_SCOUT_AI"] = "1"
        battle, scout, enemy, cx, cy = self._battle_with_scout_behind_enemy()
        goal = battle._scout_destination(scout, cy, 3.0)
        self.assertIsNotNone(goal)
        # The chosen objective is forward (>= the scout's y) and within the
        # safe band (not past the midline + margin).
        self.assertGreaterEqual(goal[1], scout.position[1] - 1e-6)
        self.assertLessEqual(goal[1], cy + 3.0 + 1e-6)


if __name__ == "__main__":
    unittest.main()
