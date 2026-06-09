"""Warp Rifts — Chaos Daemons Daemonic Incursion detachment rule (wave 221).

10e rule (Wahapedia):
  "Each time a LEGIONES DAEMONICA unit from your army is set up on the
  battlefield using the Deep Strike ability, if it is set up wholly within
  your army's Shadow of Chaos [or within 6" of a matching Greater Daemon],
  it can be set up anywhere that is more than 6" horizontally away from all
  enemy models, instead of more than 9\"."

SwegHammer simplification: when SWEG_WARP_RIFTS=1, the min_gap in
_pick_arrival_point is reduced from 9.0 to 6.0 for Chaos Daemons units
arriving under a Daemonic Incursion detachment.

These tests pin the env-gate behaviour:
  - Gate OFF (default): the 9.0" gap is enforced; a point 7" from an enemy
    is invalid.
  - Gate ON: the 6.0" gap is enforced; a point 7" from an enemy IS valid
    (it clears 6.0 but not 9.0), and a point 5" from an enemy remains
    invalid.
Cited: simulator.warp_rifts, DAEMONIC_INCURSION.warp_rifts.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.detachments import DAEMONIC_INCURSION
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile builders
# ---------------------------------------------------------------------------

def _daemon_profile(name: str = "Bloodletters", **overrides) -> UnitProfile:
    """A Chaos Daemons deep-strike unit (LEGIONES DAEMONICA stand-in)."""
    base = dict(
        name=name,
        health=1, damage=4, hit_probability=0.667,
        ap=2, save=7, strength=5, toughness=4,
        attacks=2, weapon_damage_per_shot=2.0, range_inches=0,
        leadership=7, oc=2,
        faction="Chaos Daemons",
        unit_keywords=("INFANTRY", "LEGIONES DAEMONICA", "KHORNE"),
        melee_attacks=2, melee_damage_per_shot=2.0,
        melee_hit_probability=0.667, melee_strength=5, melee_ap=2,
        deep_strike=True,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _enemy_profile(name: str = "Space Marine", **overrides) -> UnitProfile:
    """A generic enemy unit — just needs to exist on the board."""
    base = dict(
        name=name,
        health=2, damage=1, hit_probability=0.667,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, oc=1,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _add(army: Army, profile: UnitProfile, position=None) -> object:
    army.add_unit(profile)
    u = army.units[-1]
    if position is not None:
        u.position = position
    return u


def _open_map():
    """A wide, obstacle-free board with no objectives."""
    return Map(
        name="open",
        width=60.0, height=60.0,
        terrain=(),
        objectives=(),
        deployment_width=12.0,
    )


# ---------------------------------------------------------------------------
# Helper: call _pick_arrival_point with a controlled setup
# ---------------------------------------------------------------------------

def _build_battle_and_call_arrival(daemon_army: Army, enemy_army: Army,
                                   arriving_unit=None) -> object:
    """Build a Battle, place both armies, and return the Battle instance."""
    random.seed(42)
    battle = Battle(daemon_army, enemy_army, map_=_open_map())
    battle._assign_uids()
    battle._deploy_armies()
    return battle


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class WarpRiftsGateTests(unittest.TestCase):
    """Pins the SWEG_WARP_RIFTS env-gate in Battle._pick_arrival_point."""

    def setUp(self):
        random.seed(42)
        # Enemy placed 7" from board centre, at (30, 37).  A candidate at
        # (30, 30) is ~7" from the enemy — valid at 6" gap, invalid at 9".
        self.enemy = Army("Space Marines")
        _add(self.enemy, _enemy_profile("Marine Squad"), (30.0, 37.0))

        # Daemon army with the Daemonic Incursion detachment.
        self.daemons = Army("Chaos Daemons", detachment=DAEMONIC_INCURSION)
        # One on-board (non-DS) unit so the army exists; the arriving unit
        # is constructed separately and NOT added to Army.units yet.
        _add(self.daemons, _daemon_profile("Anchor"), (30.0, 5.0))

        self.arriving = _daemon_profile("Bloodletters incoming")

    def _get_battle(self) -> Battle:
        random.seed(42)
        battle = Battle(self.daemons, self.enemy, map_=_open_map())
        battle._assign_uids()
        battle._deploy_armies()
        # Reset positions after deploy so the enemy is exactly at (30, 37).
        for u in self.enemy.units:
            u.position = (30.0, 37.0)
        return battle

    def _arrival_unit_from_profile(self, battle: Battle) -> object:
        """Wrap the arriving profile in a Unit by adding it to the Daemon army."""
        from code.units import Unit
        u = Unit(self.arriving)
        u.uid = "test_arriving_unit"
        u.position = (0.0, 0.0)
        u.army_ref = self.daemons
        return u

    def test_gate_off_point_at_7in_is_invalid(self):
        """With SWEG_WARP_RIFTS off, a candidate 7" from an enemy fails (need 9")."""
        env = os.environ.copy()
        env.pop("SWEG_WARP_RIFTS", None)
        old = os.environ.get("SWEG_WARP_RIFTS")
        os.environ.pop("SWEG_WARP_RIFTS", None)
        try:
            battle = self._get_battle()
            arriving = self._arrival_unit_from_profile(battle)
            # enemy at (30, 37); candidate (30, 30) is 7" away — invalid at 9" gap.
            import math
            dist = math.hypot(30.0 - 30.0, 30.0 - 37.0)
            self.assertAlmostEqual(dist, 7.0, places=1)
            # _pick_arrival_point must NOT return a point within 9" of the enemy.
            point = battle._pick_arrival_point(
                opponent=self.enemy,
                arriving_unit=arriving,
                round_num=2,
            )
            if point is not None:
                dist_from_enemy = math.hypot(
                    point[0] - 30.0, point[1] - 37.0
                )
                self.assertGreater(
                    dist_from_enemy, 9.0,
                    f"Gate OFF: arrival point {point} is only {dist_from_enemy:.2f}\" "
                    f"from enemy — must be >9\" when SWEG_WARP_RIFTS is off",
                )
        finally:
            if old is None:
                os.environ.pop("SWEG_WARP_RIFTS", None)
            else:
                os.environ["SWEG_WARP_RIFTS"] = old

    def test_gate_on_point_at_7in_is_valid(self):
        """With SWEG_WARP_RIFTS=1, a candidate 7" from an enemy is valid (need only 6")."""
        old = os.environ.get("SWEG_WARP_RIFTS")
        os.environ["SWEG_WARP_RIFTS"] = "1"
        try:
            battle = self._get_battle()
            arriving = self._arrival_unit_from_profile(battle)
            # At least one arrival point must be within [6", 9") of the enemy.
            point = battle._pick_arrival_point(
                opponent=self.enemy,
                arriving_unit=arriving,
                round_num=2,
            )
            self.assertIsNotNone(
                point,
                "Gate ON: _pick_arrival_point must return a valid landing point",
            )
            import math
            dist_from_enemy = math.hypot(
                point[0] - 30.0, point[1] - 37.0
            )
            # The point must be >= 6" from the enemy.
            self.assertGreater(
                dist_from_enemy, 6.0,
                f"Gate ON: arrival point {point} is only {dist_from_enemy:.2f}\" "
                f"from enemy — must be >6\" even with Warp Rifts",
            )
        finally:
            if old is None:
                os.environ.pop("SWEG_WARP_RIFTS", None)
            else:
                os.environ["SWEG_WARP_RIFTS"] = old

    def test_gate_on_point_at_5in_is_still_invalid(self):
        """Even with SWEG_WARP_RIFTS=1, a point 5" from an enemy is invalid."""
        old = os.environ.get("SWEG_WARP_RIFTS")
        os.environ["SWEG_WARP_RIFTS"] = "1"
        try:
            battle = self._get_battle()
            # Place enemy much closer to centre so all candidates are either
            # far away or blocked by the 6" gap.
            for u in self.enemy.units:
                u.position = (30.0, 30.0)
            arriving = self._arrival_unit_from_profile(battle)
            point = battle._pick_arrival_point(
                opponent=self.enemy,
                arriving_unit=arriving,
                round_num=2,
            )
            if point is not None:
                import math
                dist_from_enemy = math.hypot(
                    point[0] - 30.0, point[1] - 30.0
                )
                self.assertGreater(
                    dist_from_enemy, 6.0,
                    f"Gate ON: arrival point {point} is {dist_from_enemy:.2f}\" "
                    f"from enemy — must be >6\" even with Warp Rifts",
                )
        finally:
            if old is None:
                os.environ.pop("SWEG_WARP_RIFTS", None)
            else:
                os.environ["SWEG_WARP_RIFTS"] = old

    def test_non_daemon_faction_unaffected(self):
        """SWEG_WARP_RIFTS=1 must NOT reduce the gap for a non-Chaos-Daemons unit."""
        old = os.environ.get("SWEG_WARP_RIFTS")
        os.environ["SWEG_WARP_RIFTS"] = "1"
        try:
            battle = self._get_battle()
            # Arriving unit is Space Marines, not Chaos Daemons.
            from code.units import Unit
            marine_profile = _enemy_profile("Space Marine DS",
                                            faction="Adeptus Astartes",
                                            deep_strike=True)
            marine_unit = Unit(marine_profile)
            marine_unit.uid = "test_marine_arriving"
            marine_unit.position = (0.0, 0.0)
            marine_unit.army_ref = self.daemons
            point = battle._pick_arrival_point(
                opponent=self.enemy,
                arriving_unit=marine_unit,
                round_num=2,
            )
            if point is not None:
                import math
                dist_from_enemy = math.hypot(
                    point[0] - 30.0, point[1] - 37.0
                )
                self.assertGreater(
                    dist_from_enemy, 9.0,
                    f"Non-Daemon faction: arrival point {point} is "
                    f"{dist_from_enemy:.2f}\" from enemy — gate must NOT "
                    f"reduce the gap for non-Chaos-Daemons units",
                )
        finally:
            if old is None:
                os.environ.pop("SWEG_WARP_RIFTS", None)
            else:
                os.environ["SWEG_WARP_RIFTS"] = old

    def test_detachment_field_warp_rifts_set(self):
        """DAEMONIC_INCURSION.warp_rifts must be True."""
        self.assertTrue(
            DAEMONIC_INCURSION.warp_rifts,
            "DAEMONIC_INCURSION.warp_rifts must be True",
        )

    def test_other_detachments_warp_rifts_false(self):
        """All other detachments must have warp_rifts=False (default-off)."""
        from code import detachments as det_module
        from code.detachments import Detachment
        for var_name in dir(det_module):
            obj = getattr(det_module, var_name)
            if not isinstance(obj, Detachment):
                continue
            if obj is DAEMONIC_INCURSION:
                continue
            self.assertFalse(
                obj.warp_rifts,
                f"Detachment {var_name!r} must have warp_rifts=False; "
                f"only DAEMONIC_INCURSION sets it True",
            )


if __name__ == "__main__":
    unittest.main()
