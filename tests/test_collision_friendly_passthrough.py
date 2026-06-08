"""Friendly pass-through / enemy path-block collision movement — wave 211.

10e "Making a Move": a model "can be moved through friendly models, but it
cannot end its move on top of another model", and "no part of its base can be
moved through an enemy model" (FLY moves over enemies). So under no-overlap
collision the mover's PATH is capped only by ENEMY bases (faithful screening),
FRIENDLIES are passed through (only the END must be clear), and FLY ignores
enemy bodies mid-move. This pins `_move_toward` + `_enemy_path_cap_t`.

These call the module-level movement helpers directly (no Battle needed); the
OFF path (occupants=None) is exercised to confirm byte-identical behaviour.
Cited simulator.collision_friendly_passthrough.
"""

from __future__ import annotations

import unittest

from code.map import Map
from code.pathfind import find_path
from code.simulator import _move_toward, _enemy_path_cap_t


def _map() -> Map:
    return Map(name="T", width=60.0, height=44.0, deployment_width=12.0,
               terrain=(), objectives=())


# occupants are (x, y, radius_in, is_enemy)
START = (10.0, 22.0)
FAR_GOAL = (40.0, 22.0)


class EnemyPathCapTests(unittest.TestCase):
    def test_enemy_on_path_caps_before_it(self):
        # enemy base centred at x=25 (r=1), mover r=1 → first crossing at x=23,
        # fraction (23-10)/30... wait the segment is 0..? cap is along start->end.
        occ = [(25.0, 22.0, 1.0, True)]
        t = _enemy_path_cap_t(START, FAR_GOAL, 1.0, occ, False)
        # crossing where centre-dist == mover_r+orad = 2 → x = 23 → t = 13/30.
        self.assertAlmostEqual(t, 13.0 / 30.0, places=4)

    def test_friendly_never_caps_path(self):
        occ = [(25.0, 22.0, 1.0, False)]   # friendly mid-path
        self.assertEqual(_enemy_path_cap_t(START, FAR_GOAL, 1.0, occ, False), 1.0)

    def test_fly_ignores_enemy_on_path(self):
        occ = [(25.0, 22.0, 1.0, True)]
        self.assertEqual(_enemy_path_cap_t(START, FAR_GOAL, 1.0, occ, True), 1.0)

    def test_enemy_off_path_does_not_cap(self):
        occ = [(25.0, 35.0, 1.0, True)]    # far off the y=22 line
        self.assertEqual(_enemy_path_cap_t(START, FAR_GOAL, 1.0, occ, False), 1.0)


class MoveTowardCollisionTests(unittest.TestCase):
    def test_enemy_mid_path_stops_the_mover(self):
        # An enemy at (25,22) blocks the straight path → a non-FLY mover stops
        # before it (cannot move through an enemy / cannot end within 1" ER),
        # well short of the clear end at (40,22).
        occ = [(25.0, 22.0, 1.0, True)]
        end = _move_toward(START, FAR_GOAL, 30.0, _map(),
                           mover_radius=1.0, occupants=occ, mover_fly=False,
                           sidestep=False)
        self.assertLess(end[0], 23.0, "mover halted at the enemy, not through it")

    def test_friendly_mid_path_is_passed_through_to_clear_end(self):
        # A friendly at (25,22) does NOT block the path → the mover reaches its
        # clear destination (passes through the friendly).
        occ = [(25.0, 22.0, 1.0, False)]
        end = _move_toward(START, FAR_GOAL, 30.0, _map(),
                           mover_radius=1.0, occupants=occ, mover_fly=False,
                           sidestep=False)
        self.assertEqual(end, FAR_GOAL)

    def test_fly_passes_over_enemy_to_clear_end(self):
        occ = [(25.0, 22.0, 1.0, True)]
        end = _move_toward(START, FAR_GOAL, 30.0, _map(),
                           mover_radius=1.0, occupants=occ, mover_fly=True,
                           sidestep=False)
        self.assertEqual(end, FAR_GOAL)

    def test_cannot_end_on_a_friendly_model(self):
        # Destination occupied by a friendly → mover stops before it (cannot end
        # on top of another model), but is NOT capped (it could pass it).
        goal = (25.0, 22.0)
        occ = [(25.0, 22.0, 1.0, False)]
        end = _move_toward(START, goal, 15.0, _map(),
                           mover_radius=1.0, occupants=occ, mover_fly=False,
                           sidestep=False)
        self.assertLess(end[0], 24.0)
        self.assertNotEqual(end, goal)

    def test_off_path_is_byte_identical(self):
        # occupants=None → no collision → straight destination, unchanged.
        goal = (25.0, 22.0)
        end = _move_toward(START, goal, 15.0, _map(),
                           mover_radius=1.0, occupants=None, mover_fly=False)
        self.assertEqual(end, goal)

    def test_clear_path_reaches_destination(self):
        # No occupants near the line → straight end returned.
        end = _move_toward(START, FAR_GOAL, 30.0, _map(),
                           mover_radius=1.0, occupants=[], mover_fly=False,
                           sidestep=False)
        self.assertEqual(end, FAR_GOAL)


class FindPathFriendlyTransparencyTests(unittest.TestCase):
    """find_path (big-mover routing) must block only ENEMY bases on the path —
    friendlies are path-transparent (consistent with _move_toward). Otherwise a
    Knight pathfinds AROUND its own friendlies (the DZ-blob)."""

    def _wall(self, is_enemy):
        # A FULL board-height line of 1" bases across the lane at x=20: with a 1"
        # mover the inflated radius (2") leaves no gap top or bottom → a solid wall
        # with no way around (board is 44" tall).
        return [(20.0, float(y), 1.0, is_enemy) for y in range(2, 43, 2)]

    def test_friendly_wall_is_passed_through(self):
        p = find_path((10.0, 22.0), (40.0, 22.0), 30.0, 1.0,
                      self._wall(False), walls=(), map_=_map())
        self.assertGreater(p[0], 34.0, "friendly wall is path-transparent")

    def test_enemy_wall_with_no_way_around_blocks_the_path(self):
        p = find_path((10.0, 22.0), (40.0, 22.0), 30.0, 1.0,
                      self._wall(True), walls=(), map_=_map())
        self.assertLess(p[0], 20.0, "an un-flankable enemy wall stops the mover before it")


if __name__ == "__main__":
    unittest.main()
