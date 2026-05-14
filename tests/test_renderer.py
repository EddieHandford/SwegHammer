"""Tests for the matplotlib replay renderer.

The renderer is mostly graphical and exercised end-to-end in `run.py`, but
the shape-dispatch logic is pure and worth pinning down: a TITANIC unit
must read as a large rectangle, a MONSTER as a large circle, and the
default INFANTRY as the small circle we've always used.
"""

from __future__ import annotations

import unittest

from code.renderer import (
    SHAPE_CHARACTER_CIRCLE,
    SHAPE_ELLIPSE,
    SHAPE_LARGE_CIRCLE,
    SHAPE_LARGE_RECT,
    SHAPE_MEDIUM_RECT,
    SHAPE_SMALL_CIRCLE,
    SHAPE_SWARM,
    _shape_for,
)


class ShapeDispatcherTests(unittest.TestCase):

    def test_vehicle_is_medium_rectangle(self):
        tag, size = _shape_for(("VEHICLE",))
        self.assertEqual(tag, SHAPE_MEDIUM_RECT)
        # Rectangle hints are (width, height) tuples in world inches.
        self.assertIsInstance(size, tuple)
        self.assertEqual(len(size), 2)

    def test_walker_is_medium_rectangle(self):
        tag, _ = _shape_for(("WALKER",))
        self.assertEqual(tag, SHAPE_MEDIUM_RECT)

    def test_titanic_is_large_rectangle(self):
        # Largest silhouette wins even alongside VEHICLE.
        tag, size = _shape_for(("TITANIC", "VEHICLE"))
        self.assertEqual(tag, SHAPE_LARGE_RECT)
        self.assertIsInstance(size, tuple)
        big_w, big_h = size
        # Sanity: large rect strictly bigger than medium.
        med_tag, med_size = _shape_for(("VEHICLE",))
        med_w, med_h = med_size
        self.assertGreater(big_w, med_w)
        self.assertGreater(big_h, med_h)

    def test_towering_is_large_rectangle(self):
        tag, _ = _shape_for(("TOWERING",))
        self.assertEqual(tag, SHAPE_LARGE_RECT)

    def test_monster_is_large_circle(self):
        tag, size = _shape_for(("MONSTER",))
        self.assertEqual(tag, SHAPE_LARGE_CIRCLE)
        # Large circles use a scatter `s=` value > the default small circle.
        _, small_size = _shape_for(("INFANTRY",))
        self.assertGreater(size, small_size)

    def test_bike_is_ellipse(self):
        tag, size = _shape_for(("BIKE",))
        self.assertEqual(tag, SHAPE_ELLIPSE)
        self.assertIsInstance(size, tuple)

    def test_mounted_is_ellipse(self):
        tag, _ = _shape_for(("MOUNTED",))
        self.assertEqual(tag, SHAPE_ELLIPSE)

    def test_swarm_is_swarm_cluster(self):
        tag, _ = _shape_for(("SWARM",))
        self.assertEqual(tag, SHAPE_SWARM)

    def test_character_is_outlined_circle(self):
        tag, _ = _shape_for(("CHARACTER",))
        self.assertEqual(tag, SHAPE_CHARACTER_CIRCLE)

    def test_infantry_is_default_small_circle(self):
        tag, size = _shape_for(("INFANTRY",))
        self.assertEqual(tag, SHAPE_SMALL_CIRCLE)
        # Size hint is a scalar scatter `s=` value, not a tuple.
        self.assertIsInstance(size, (int, float))

    def test_empty_keywords_falls_through_to_default(self):
        tag, _ = _shape_for(())
        self.assertEqual(tag, SHAPE_SMALL_CIRCLE)

    def test_none_keywords_falls_through_to_default(self):
        tag, _ = _shape_for(None)
        self.assertEqual(tag, SHAPE_SMALL_CIRCLE)

    def test_vehicle_character_reads_as_vehicle(self):
        # Bigger silhouette wins: a vehicle character (e.g. a Land Raider
        # with a CHARACTER tag) should still draw as a vehicle.
        tag, _ = _shape_for(("CHARACTER", "VEHICLE"))
        self.assertEqual(tag, SHAPE_MEDIUM_RECT)


if __name__ == "__main__":
    unittest.main()
