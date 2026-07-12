"""Terrain program phase 2b — the calibrated threat field consumes the
engine's line of sight (docs/DECISION_LEDGER.md "TERRAIN PROGRAM PHASE-1
VERDICT + PHASE 2"; ground-truth correction 055bcaa).

The resolution's shooting path has filtered candidates through
`Map.has_line_of_sight` since May, but the threat field priced ranged threat
with cover attenuation only — enemies behind blocking ruins projected threat
they cannot deliver. In the SWEG_THREAT_ALLOC (calibrated) form, a ranged
contribution is now zero without line of sight; melee is never blocked
(chargers route around); the allocation denominators shrink each enemy's
eligible-target set to the targets it can see. These fixtures hand-pin all
three properties on a synthetic ruin wall, using the REAL `code.map.Map` (the
engine line-of-sight function itself), to 1e-9. The measured constants
(_attack_propensity) enter symbolically.
"""
from __future__ import annotations

import os
import unittest

from code.map import Map, Terrain, TerrainType
from code.strategy import (
    _attack_propensity,
    _p_2d6_at_least,
    _threat_field_at,
    _threat_projectors,
)
from tests.test_job_layer import _Army, _Unit, _one_wound_body, _pistol_body


def _walled_map() -> Map:
    """A 60x44 board with ONE Ruin rectangle spanning x in [4, 6], y in
    [0, 6] — Ruins block line of sight for everyone (both endpoints outside
    the rectangle), per the cited 10e rule the engine implements."""
    wall = Terrain(name="ruin-wall", x=4.0, y=0.0, width=2.0, height=6.0,
                   type=TerrainType.RUIN)
    return Map(name="los-fixture", width=60.0, height=44.0, terrain=(wall,),
               objectives=())


class ThreatFieldLineOfSight(unittest.TestCase):
    def setUp(self):
        os.environ["SWEG_THREAT_ALLOC"] = "1"

    def tearDown(self):
        del os.environ["SWEG_THREAT_ALLOC"]

    def test_a_ranged_blocked_by_wall_full_when_exposed(self):
        """(a) A ranged-only enemy behind the blocking wall contributes
        EXACTLY 0 to a hidden cell, and its full allocated contribution to an
        exposed cell — while the summed (gate-off) field still prices the
        hidden cell (the line-of-sight consumption is folded into the
        calibrated form only).

        HAND COMPUTATION: the PistolBody's expected wounds onto a T3/5+
        one-wound body are 1/6 (1 attack x 0.5 hit x wound(3,3)=0.5 x
        fail(5+, AP0)=2/3), within its 6 move + 12 range = 18-inch reach.
        Exposed cell: the only eligible target -> allocation share 1,
        propensity keyed on 1/6 -> field = (1/6) x prop(1/6)."""
        map_ = _walled_map()

        # Hidden: the wall sits between (0,3) and (10,3).
        friendly = _Army([])
        me = _Unit(_one_wound_body(), (10.0, 3.0), uid=11)
        me.army_ref = friendly
        friendly.units = [me]
        enemy = _Army([_Unit(_pistol_body(), (0.0, 3.0), uid=91)], is_a=False)
        proj = _threat_projectors(enemy)
        self.assertEqual(
            _threat_field_at(me, proj, me.position, map_), 0.0)

        # The summed field (gate off) still prices it — the fold is gated.
        del os.environ["SWEG_THREAT_ALLOC"]
        try:
            summed = _threat_field_at(me, proj, me.position, map_)
        finally:
            os.environ["SWEG_THREAT_ALLOC"] = "1"
        self.assertAlmostEqual(summed, 1.0 / 6.0, delta=1e-9)

        # Exposed: the straight line (0,3)-(0,13) misses the wall entirely.
        friendly2 = _Army([])
        me2 = _Unit(_one_wound_body(), (0.0, 13.0), uid=12)
        me2.army_ref = friendly2
        friendly2.units = [me2]
        enemy2 = _Army([_Unit(_pistol_body(), (0.0, 3.0), uid=92)], is_a=False)
        proj2 = _threat_projectors(enemy2)
        expected = (1.0 / 6.0) * _attack_propensity(1.0 / 6.0)
        self.assertAlmostEqual(
            _threat_field_at(me2, proj2, me2.position, map_), expected,
            delta=1e-9)

    def test_b_melee_contribution_unchanged_by_wall(self):
        """(b) A melee-capable enemy behind the same wall keeps its FULL melee
        gradient at the hidden cell — chargers route around walls, so melee
        reach stays geometric.

        HAND COMPUTATION: the OneWound body's melee expected wounds are 1/6;
        at 10 inches its charge needs 10 - 6 move - 1.5 engagement = 2.5 on
        two dice; its ranged 1/6 is line-of-sight blocked. The single-target
        denominators reduce to the same melee-only contribution c ->
        share 1 -> field = c x prop(c), c = (1/6) x P(2D6 >= 2.5)."""
        map_ = _walled_map()
        friendly = _Army([])
        me = _Unit(_one_wound_body(), (10.0, 3.0), uid=21)
        me.army_ref = friendly
        friendly.units = [me]
        enemy = _Army([_Unit(_one_wound_body(), (0.0, 3.0), uid=93)],
                      is_a=False)
        proj = _threat_projectors(enemy)
        c = (1.0 / 6.0) * _p_2d6_at_least(2.5)
        expected = c * _attack_propensity(c)
        got = _threat_field_at(me, proj, me.position, map_)
        self.assertAlmostEqual(got, expected, delta=1e-9)
        self.assertGreater(got, 0.0)      # the wall does not stop chargers

    def test_c_allocation_weights_shrink_to_visible_targets(self):
        """(c) An enemy that can only SEE one of my two units allocates FULL
        weight to the visible one: the hidden unit is out of its
        eligible-target set (the denominators apply the same line-of-sight
        test), so the visible unit's share is 1 — not the half it would be if
        the walled-off unit still diluted the split. The hidden unit itself
        reads zero."""
        map_ = _walled_map()
        friendly = _Army([])
        visible = _Unit(_one_wound_body(), (0.0, 13.0), uid=31)
        hidden = _Unit(_one_wound_body(), (10.0, 3.0), uid=32)
        visible.army_ref = friendly
        hidden.army_ref = friendly
        friendly.units = [visible, hidden]
        enemy = _Army([_Unit(_pistol_body(), (0.0, 3.0), uid=94)], is_a=False)
        proj = _threat_projectors(enemy)

        expected_full = (1.0 / 6.0) * _attack_propensity(1.0 / 6.0)
        self.assertAlmostEqual(
            _threat_field_at(visible, proj, visible.position, map_),
            expected_full, delta=1e-9)     # share exactly 1, undiluted
        self.assertEqual(
            _threat_field_at(hidden, proj, hidden.position, map_), 0.0)


if __name__ == "__main__":
    unittest.main()
