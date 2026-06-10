"""Scout-destination AI (gated SWEG_SCOUT_AI) — the pre-game Scouts move's
DESTINATION is a ROLE-classified AI tactical choice (v2).

The Scouts move itself is the real 10e rule (cited `simulator.scout`); these
tests pin the v2 DESTINATION policy:

  * Gate OFF (default): every scout moves toward the NEAREST ENEMY (legacy).
  * Gate ON, classified by role:
      (a) MELEE-oriented (`_is_melee_class`)  -> pressure FORWARD toward the
          nearest enemy (a War Dog / assault scout wants to close).
      (b) LONG-range shooty (range >= 24")    -> HOLD (a long gun already
          threatens the midboard from its own zone; advancing only exposes it).
      (c) SHORT-range / fragile shooty        -> move toward the nearest
          FORWARD-BUT-SAFE contestable objective, never into a worse position.

v1 (send-every-scout-to-an-objective) was flat-to-worse at N=40 because it
pulled aggressive melee scouts off their pressure (Chaos Knights War Dog
-4.17) and stranded long-range gunline scouts on open markers (Adeptus
Mechanicus Skitarii -3.66). v2 fixes both while keeping the short-fragile case
that helped Astra Militarum (+2.08).

Scenario: the scout sits on its own side; the only enemy is placed BEHIND it
(toward its own home edge), so "toward the enemy" and "toward the centreline
objective" point in opposite directions and the test is decisive.
"""
from __future__ import annotations

import os
import unittest

from code.army import Army
from code.simulator import Battle, _distance
from code.units import UnitProfile


def _base(**overrides) -> dict:
    d = dict(
        name="Scout",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7, faction="Astra Militarum",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        scout_distance=9,
    )
    d.update(overrides)
    return d


def _short_shooty(**o) -> UnitProfile:
    # ranged-DPA 1.0 > melee-DPA 0.5, range 18 < 24  -> case (c) objective.
    return UnitProfile(**_base(name="Kasrkin", range_inches=18, **o))


def _melee(**o) -> UnitProfile:
    # melee-DPA 4.0 > ranged-DPA 0.5  -> case (a) forward pressure.
    return UnitProfile(**_base(
        name="War Dog", attacks=1, weapon_damage_per_shot=1.0,
        melee_attacks=4, melee_damage_per_shot=2.0, melee_hit_probability=0.5,
        range_inches=18, scout_distance=6, **o))


def _long_shooty(**o) -> UnitProfile:
    # ranged-DPA 2.0 > melee-DPA 0.5, range 36 >= 24  -> case (b) HOLD.
    return UnitProfile(**_base(
        name="Skitarii", attacks=4, weapon_damage_per_shot=1.0,
        range_inches=36, scout_distance=6, **o))


def _plain(name: str = "Enemy", **o) -> UnitProfile:
    return UnitProfile(**_base(
        name=name, faction="Orks", scout_distance=0,
        attacks=1, **o))


class ScoutDestinationAIv2Tests(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("SWEG_SCOUT_AI")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("SWEG_SCOUT_AI", None)
        else:
            os.environ["SWEG_SCOUT_AI"] = self._prev

    def _battle(self, scout_profile):
        a = Army("ScoutForce")
        a.add_unit(scout_profile)
        b = Army("EnemyForce")
        b.add_unit(_plain("Ork Boy"))
        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()
        cx = battle.map.width / 2.0
        cy = battle.map.height / 2.0
        scout = a.units[0]
        enemy = b.units[0]
        # Scout 20" back on its own side; enemy 25" back (further from the
        # centreline). Nearest enemy is BEHIND; the Centre objective is forward.
        scout.position = (cx, cy - 20.0)
        enemy.position = (cx, cy - 25.0)
        battle._fresh_arrivals = set()
        return battle, scout, enemy, cx, cy

    # ---- case (c): short-range fragile shooty -> forward objective ----
    def test_short_shooty_moves_forward_to_objective(self):
        os.environ["SWEG_SCOUT_AI"] = "1"
        battle, scout, enemy, cx, cy = self._battle(_short_shooty())
        start_y = scout.position[1]
        battle._run_scout_phase()
        end_y = scout.position[1]
        self.assertGreater(end_y, start_y,
            "short-range shooty scout should advance to the forward objective")
        self.assertLessEqual(end_y, cy + 3.0 + 1e-6,
            "must not end more than the safe margin past the midline")

    # ---- case (a): melee scout -> pressure forward toward the enemy ----
    def test_melee_scout_pressures_toward_enemy(self):
        os.environ["SWEG_SCOUT_AI"] = "1"
        battle, scout, enemy, cx, cy = self._battle(_melee())
        start_y = scout.position[1]
        battle._run_scout_phase()
        end_y = scout.position[1]
        # Enemy is behind -> melee pressure walks the scout backward toward it.
        self.assertLess(end_y, start_y,
            "melee scout should pressure toward the nearest enemy, not an "
            "objective")

    # ---- case (b): long-range shooty -> HOLD ----
    def test_long_range_shooty_holds(self):
        os.environ["SWEG_SCOUT_AI"] = "1"
        battle, scout, enemy, cx, cy = self._battle(_long_shooty())
        start = scout.position
        battle._run_scout_phase()
        self.assertEqual(scout.position, start,
            "long-range shooty scout should hold its firing position")
        self.assertNotIn(scout.uid, battle._fresh_arrivals)

    # ---- gate OFF: legacy nearest-enemy for every role ----
    def test_gate_off_moves_toward_nearest_enemy(self):
        os.environ["SWEG_SCOUT_AI"] = "0"
        for prof in (_short_shooty(), _melee(), _long_shooty()):
            battle, scout, enemy, cx, cy = self._battle(prof)
            start_y = scout.position[1]
            battle._run_scout_phase()
            self.assertLess(scout.position[1], start_y,
                f"legacy scout ({prof.name}) moves toward the nearest enemy "
                f"(here, backward)")


if __name__ == "__main__":
    unittest.main()
