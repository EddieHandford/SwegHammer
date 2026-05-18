"""Tests for the 10e Ruins line-of-sight rule.

10e core: "Models can shoot through walls of a Ruin so long as both the
firing model and the target model have the INFANTRY, BEAST or SWARM
keyword. In all other cases, a wall blocks line of sight."
https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Ruins

Implemented in `code.map.Map.has_line_of_sight` via the
`attacker_keywords` / `target_keywords` kwargs; cited as
`terrain.ruin_infantry_los`.
"""

import unittest

from code.map import Map, Terrain, TerrainType


def _ruin_in_the_middle() -> Map:
    """A 60x60 board with one 4x4 Ruin wall straddling the centre."""
    return Map(
        name="Test - Single Ruin Block",
        width=60.0,
        height=60.0,
        terrain=(
            Terrain(
                name="Test Ruin",
                x=28.0, y=28.0, width=4.0, height=4.0,
                type=TerrainType.RUIN,
            ),
        ),
    )


def _obscuring_in_the_middle() -> Map:
    """A 60x60 board with one 4x4 Obscuring block straddling the centre."""
    return Map(
        name="Test - Single Obscuring Block",
        width=60.0,
        height=60.0,
        terrain=(
            Terrain(
                name="Test Wood",
                x=28.0, y=28.0, width=4.0, height=4.0,
                type=TerrainType.OBSCURING,
            ),
        ),
    )


class RuinLosTests(unittest.TestCase):
    """Endpoints at (15, 30) and (45, 30) — a horizontal line crossing the
    Ruin / Obscuring rectangle at y=30."""

    A = (15.0, 30.0)
    B = (45.0, 30.0)

    INFANTRY = ("INFANTRY",)
    VEHICLE = ("VEHICLE",)
    BEAST = ("BEAST",)
    SWARM = ("SWARM",)
    NONE = ()

    # ---- Ruin: keyword asymmetry ----------------------------------------

    def test_infantry_to_infantry_passes_through_ruin(self):
        m = _ruin_in_the_middle()
        self.assertTrue(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.INFANTRY,
                target_keywords=self.INFANTRY,
            ),
            "INFANTRY firing at INFANTRY through a Ruin wall must see (10e core).",
        )

    def test_vehicle_to_vehicle_blocked_by_ruin(self):
        m = _ruin_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.VEHICLE,
            ),
            "VEHICLE shooting at VEHICLE through a Ruin wall must be blocked.",
        )

    def test_infantry_to_vehicle_blocked_by_ruin(self):
        m = _ruin_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.INFANTRY,
                target_keywords=self.VEHICLE,
            ),
            "10e Ruins requires BOTH endpoints to be INFANTRY/BEAST/SWARM.",
        )

    def test_vehicle_to_infantry_blocked_by_ruin(self):
        m = _ruin_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.INFANTRY,
            ),
            "10e Ruins requires BOTH endpoints to be INFANTRY/BEAST/SWARM.",
        )

    def test_beast_to_swarm_passes_through_ruin(self):
        """BEAST and SWARM share the INFANTRY exception in 10e core."""
        m = _ruin_in_the_middle()
        self.assertTrue(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.BEAST,
                target_keywords=self.SWARM,
            ),
        )

    def test_no_keywords_blocked_by_ruin(self):
        """When keywords aren't supplied, treat ruin as a full LoS blocker."""
        m = _ruin_in_the_middle()
        self.assertFalse(m.has_line_of_sight(self.A, self.B))

    def test_endpoint_inside_ruin_always_sees_out(self):
        """A model standing inside the Ruin can see and be seen
        regardless of keyword (real rule: shooting from inside the
        Ruin / through the same Ruin's interior is unobstructed)."""
        m = _ruin_in_the_middle()
        inside = (30.0, 30.0)
        self.assertTrue(
            m.has_line_of_sight(
                inside, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.VEHICLE,
            ),
        )
        self.assertTrue(
            m.has_line_of_sight(
                self.A, inside,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.VEHICLE,
            ),
        )

    # ---- Obscuring: must still block ALL unit types ----------------------

    def test_obscuring_blocks_infantry(self):
        m = _obscuring_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.INFANTRY,
                target_keywords=self.INFANTRY,
            ),
            "Non-ruin obscuring terrain still blocks LoS for all unit types.",
        )

    def test_obscuring_blocks_vehicle(self):
        m = _obscuring_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.VEHICLE,
            ),
        )

    # ---- Open lane: nothing blocks --------------------------------------

    def test_no_blocker_clear_path(self):
        m = _ruin_in_the_middle()
        # Path well above the rectangle — never intersects.
        a = (15.0, 50.0)
        b = (45.0, 50.0)
        self.assertTrue(
            m.has_line_of_sight(
                a, b,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.VEHICLE,
            ),
            "A line that never touches the Ruin must always pass.",
        )


class RuinCoverTests(unittest.TestCase):
    """A model standing inside a RUIN rectangle gets Heavy Cover-grade
    benefits (+1 save, -1 to hit) — same combat effect as HEAVY_COVER."""

    def test_ruin_grants_heavy_cover(self):
        m = _ruin_in_the_middle()
        cover_inside = m.cover_at((30.0, 30.0))
        self.assertEqual(cover_inside, TerrainType.RUIN)
        cover_outside = m.cover_at((10.0, 10.0))
        self.assertEqual(cover_outside, TerrainType.OPEN)


if __name__ == "__main__":
    unittest.main()
