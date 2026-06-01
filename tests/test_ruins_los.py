"""Tests for the 10e Ruins line-of-sight rule.

Current 10e core (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Ruins):
"Models cannot see over or through this terrain feature. AIRCRAFT models are
exceptions to this ... Models can see into this terrain feature normally, and
models that are wholly within this terrain feature can see out of it normally.
... TOWERING models that are within this terrain feature can also see out of it
normally."

So Ruin walls block line of sight for everyone except AIRCRAFT; a model wholly
within the Ruin can see out (which also covers a TOWERING model standing inside
it). The INFANTRY/BEAST exception is MOVEMENT ONLY in current 10e and grants no
line of sight — the old "INFANTRY/BEAST/SWARM may shoot through Ruin walls"
line-of-sight pass has been removed. TOWERING does NOT get a blanket see-over
for Ruins (unlike Woods/Obscuring).

Implemented in `code.map.Map.has_line_of_sight` via the
`attacker_keywords` / `target_keywords` kwargs; cited as
`terrain.ruin_infantry_los` and `simulator.towering_los`.
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
    AIRCRAFT = ("AIRCRAFT",)
    NONE = ()

    # ---- Ruin: walls block everyone except AIRCRAFT ---------------------

    def test_infantry_to_infantry_blocked_by_ruin(self):
        """Current 10e: the INFANTRY/BEAST/SWARM shoot-through-walls
        line-of-sight pass was removed (that exception is movement-only now).
        INFANTRY firing at INFANTRY through a Ruin wall is BLOCKED."""
        m = _ruin_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.INFANTRY,
                target_keywords=self.INFANTRY,
            ),
            "INFANTRY no longer shoots through Ruin walls in current 10e.",
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

    def test_beast_to_swarm_blocked_by_ruin(self):
        """BEAST and SWARM no longer get a line-of-sight pass through Ruin
        walls either — the keyword exception is movement-only in current 10e."""
        m = _ruin_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.BEAST,
                target_keywords=self.SWARM,
            ),
            "BEAST/SWARM no longer shoots through Ruin walls in current 10e.",
        )

    def test_aircraft_attacker_sees_through_ruin(self):
        """AIRCRAFT is the only blanket exception — visibility to/from an
        AIRCRAFT model is determined normally even through a Ruin wall."""
        m = _ruin_in_the_middle()
        self.assertTrue(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.AIRCRAFT,
                target_keywords=self.VEHICLE,
            ),
            "AIRCRAFT attacker must see through a Ruin wall (10e core).",
        )

    def test_aircraft_target_seen_through_ruin(self):
        m = _ruin_in_the_middle()
        self.assertTrue(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.AIRCRAFT,
            ),
            "An AIRCRAFT target must be seen through a Ruin wall (10e core).",
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


class ToweringLosTests(unittest.TestCase):
    """TOWERING keyword: either endpoint TOWERING ignores Woods / OBSCURING
    terrain for line of sight (10e core Woods rule). TOWERING does NOT get a
    blanket see-over for RUINS — per the Ruins rule a TOWERING model only sees
    out of a Ruin when it is itself within that Ruin; from OUTSIDE a Ruin it is
    blocked like anyone else.

    Wahapedia: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Woods
    "AIRCRAFT and TOWERING models are exceptions to this — visibility to and
    from such models is determined normally, even if this terrain feature is
    wholly in between them and the observing model."
    """

    A = (15.0, 30.0)
    B = (45.0, 30.0)

    TOWERING = ("TOWERING",)
    VEHICLE = ("VEHICLE",)
    INFANTRY = ("INFANTRY",)

    # ---- TOWERING attacker vs Obscuring ----------------------------------------

    def test_towering_attacker_ignores_obscuring(self):
        m = _obscuring_in_the_middle()
        self.assertTrue(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.TOWERING,
                target_keywords=self.VEHICLE,
            ),
            "TOWERING attacker must ignore Obscuring terrain for line of sight.",
        )

    def test_towering_target_ignores_obscuring(self):
        m = _obscuring_in_the_middle()
        self.assertTrue(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.TOWERING,
            ),
            "TOWERING target must ignore Obscuring terrain for line of sight.",
        )

    def test_both_towering_ignores_obscuring(self):
        m = _obscuring_in_the_middle()
        self.assertTrue(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.TOWERING,
                target_keywords=self.TOWERING,
            ),
        )

    def test_non_towering_still_blocked_by_obscuring(self):
        """Confirm the existing non-TOWERING path is not broken."""
        m = _obscuring_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.VEHICLE,
            ),
            "Non-TOWERING models must still be blocked by Obscuring terrain.",
        )

    # ---- TOWERING vs Ruin wall: blocked from OUTSIDE, sees out from INSIDE --

    def test_towering_attacker_blocked_by_ruin_from_outside(self):
        """A TOWERING model OUTSIDE a Ruin is blocked by the wall like anyone
        else — TOWERING is not a blanket Ruin see-over (only AIRCRAFT is)."""
        m = _ruin_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.TOWERING,
                target_keywords=self.VEHICLE,
            ),
            "TOWERING does not see through Ruin walls from outside the Ruin.",
        )

    def test_towering_target_blocked_by_ruin_from_outside(self):
        m = _ruin_in_the_middle()
        self.assertFalse(
            m.has_line_of_sight(
                self.A, self.B,
                attacker_keywords=self.VEHICLE,
                target_keywords=self.TOWERING,
            ),
            "A TOWERING target outside a Ruin is blocked by the wall.",
        )

    def test_towering_within_ruin_sees_out(self):
        """A TOWERING model standing WITHIN the Ruin can see out of it
        normally (per the Ruins rule). The endpoint-contained allowance in
        _los_query covers this."""
        m = _ruin_in_the_middle()
        inside = (30.0, 30.0)
        self.assertTrue(
            m.has_line_of_sight(
                inside, self.B,
                attacker_keywords=self.TOWERING,
                target_keywords=self.VEHICLE,
            ),
            "A TOWERING model within the Ruin must see out of it.",
        )


class RuinCoverTests(unittest.TestCase):
    """A model standing inside a RUIN rectangle gets the single Benefit of
    Cover (+1 save) — the same combat effect as LIGHT_COVER and HEAVY_COVER in
    current 10e. There is no terrain -1-to-hit any more. `cover_at` still
    reports the RUIN member so callers can tell the terrain kind apart."""

    def test_ruin_reports_cover(self):
        m = _ruin_in_the_middle()
        cover_inside = m.cover_at((30.0, 30.0))
        self.assertEqual(cover_inside, TerrainType.RUIN)
        cover_outside = m.cover_at((10.0, 10.0))
        self.assertEqual(cover_outside, TerrainType.OPEN)


if __name__ == "__main__":
    unittest.main()
