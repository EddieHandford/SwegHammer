"""Tests for the real-world base-footprint renderer path.

The renderer now draws each unit using its `base_shape` + millimetre
dimensions sourced from `UnitProfile`, converted to world inches at
25.4 mm/inch. These tests assert that:

  - circle profiles -> matplotlib `Circle` patch sized by `base_diameter_mm`
  - rect profiles   -> `Rectangle` patch sized by `base_width_mm` x `base_length_mm`
  - oval profiles   -> `Ellipse` patch sized by `base_width_mm` x `base_length_mm`
  - the default UnitProfile (no override) renders as a 32mm round Circle

The tests build a minimal event log by hand (one `BattleStarted` carrying
an `InitialUnit` per scenario) so they're independent of the simulator and
the BSData catalogue.
"""

from __future__ import annotations

import unittest

import matplotlib
matplotlib.use("Agg")  # headless backend — no display required
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, Rectangle

from code.events import BattleStarted, InitialUnit
from code.map import Map
from code.renderer import (
    MM_PER_INCH,
    _draw_unit_base,
    _mm_to_inches,
    aggregate_activations,
    render_frame,
)


def _empty_map() -> Map:
    """A bare 30x60 board with no terrain or objectives."""
    return Map(name="test", width=30.0, height=60.0, deployment_width=12.0,
               terrain=(), objectives=())


def _battle_started(initial_units: list) -> BattleStarted:
    return BattleStarted(
        army_a_name="A", army_b_name="B", map_name="test",
        units=tuple(initial_units),
    )


def _patches_of(ax, cls):
    return [p for p in ax.patches if isinstance(p, cls)]


class MmToInchesTests(unittest.TestCase):

    def test_one_inch_is_25_4_mm(self):
        # GW scale: 25.4 mm/inch. A 25.4mm base is exactly 1 world inch.
        self.assertAlmostEqual(_mm_to_inches(MM_PER_INCH), 1.0, places=6)

    def test_32mm_marine_is_just_over_an_inch(self):
        # Standard Marine 32mm -> ~1.26 world inches.
        self.assertAlmostEqual(_mm_to_inches(32), 32 / 25.4, places=6)


class DrawUnitBaseTests(unittest.TestCase):
    """Unit-test the patch dispatcher directly — no full render_frame."""

    def _fresh_ax(self):
        fig, ax = plt.subplots(figsize=(2, 2))
        return fig, ax

    def test_circle_shape_produces_circle_patch(self):
        fig, ax = self._fresh_ax()
        _draw_unit_base(ax, 5.0, 7.0, "#ff0000",
                        base_shape="circle", base_diameter_mm=32,
                        base_width_mm=32, base_length_mm=32)
        circles = _patches_of(ax, Circle)
        self.assertEqual(len(circles), 1)
        # 32mm diameter -> 16mm radius -> 16/25.4 world inches
        self.assertAlmostEqual(circles[0].radius, 16 / 25.4, places=5)
        plt.close(fig)

    def test_rect_shape_produces_rectangle_patch_with_correct_size(self):
        # Rhino footprint reference: 89mm x 152mm
        fig, ax = self._fresh_ax()
        _draw_unit_base(ax, 0.0, 0.0, "#00ff00",
                        base_shape="rect", base_diameter_mm=32,
                        base_width_mm=89, base_length_mm=152)
        rects = _patches_of(ax, Rectangle)
        self.assertEqual(len(rects), 1)
        self.assertAlmostEqual(rects[0].get_width(), 89 / 25.4, places=5)
        self.assertAlmostEqual(rects[0].get_height(), 152 / 25.4, places=5)
        plt.close(fig)

    def test_oval_shape_produces_ellipse_patch_with_correct_size(self):
        # GW 60x35mm oval (small flying base)
        fig, ax = self._fresh_ax()
        _draw_unit_base(ax, 1.0, 2.0, "#0000ff",
                        base_shape="oval", base_diameter_mm=32,
                        base_width_mm=35, base_length_mm=60)
        ellipses = _patches_of(ax, Ellipse)
        self.assertEqual(len(ellipses), 1)
        self.assertAlmostEqual(ellipses[0].width, 35 / 25.4, places=5)
        self.assertAlmostEqual(ellipses[0].height, 60 / 25.4, places=5)
        plt.close(fig)

    def test_unknown_shape_falls_back_to_circle(self):
        # A bad override value shouldn't take the renderer down — it falls
        # back to the 32mm round (or whatever diameter the caller passed).
        fig, ax = self._fresh_ax()
        _draw_unit_base(ax, 0.0, 0.0, "#ffffff",
                        base_shape="bogus", base_diameter_mm=40,
                        base_width_mm=99, base_length_mm=99)
        circles = _patches_of(ax, Circle)
        self.assertEqual(len(circles), 1)
        self.assertAlmostEqual(circles[0].radius, 20 / 25.4, places=5)
        plt.close(fig)


class RenderFrameBaseShapeTests(unittest.TestCase):
    """End-to-end: build a minimal event log, render it, inspect axes patches."""

    def _render(self, initial_unit: InitialUnit):
        events = [_battle_started([initial_unit])]
        frames = aggregate_activations(events)
        fig = render_frame(_empty_map(), events, frame=0, frames=frames)
        ax = fig.axes[0]
        return fig, ax

    def test_default_profile_renders_as_32mm_circle(self):
        # Default InitialUnit (no base overrides) -> 32mm round.
        u = InitialUnit(
            uid="u1", name="default", army="A",
            position=(5.0, 5.0), max_health=1.0,
        )
        fig, ax = self._render(u)
        # Filter to the unit's Circle (objective markers are unrelated and
        # we made the map empty, so there should be none).
        unit_circles = [
            c for c in _patches_of(ax, Circle)
            if c.get_facecolor()[3] > 0   # alpha > 0 (filled, not the outline-only objective rings)
        ]
        # The objective ring is `fill=False` so its facecolor alpha is 0;
        # the unit's base is filled. We also asserted no objectives above.
        self.assertGreaterEqual(len(unit_circles), 1)
        # 32mm diameter -> radius 16/25.4 in
        radii = [round(c.radius, 5) for c in unit_circles]
        self.assertIn(round(16 / 25.4, 5), radii)
        plt.close(fig)

    def test_rect_profile_renders_a_rectangle_patch(self):
        # Rhino-ish footprint via the InitialUnit overrides.
        u = InitialUnit(
            uid="u1", name="vehicle", army="A",
            position=(10.0, 10.0), max_health=10.0,
            base_shape="rect", base_diameter_mm=32,
            base_width_mm=89, base_length_mm=152,
        )
        fig, ax = self._render(u)
        rects = _patches_of(ax, Rectangle)
        # The board frame / terrain may add other rects; we filter to the
        # one matching our vehicle's dimensions.
        match = [
            r for r in rects
            if abs(r.get_width() - 89 / 25.4) < 1e-4
            and abs(r.get_height() - 152 / 25.4) < 1e-4
        ]
        self.assertEqual(len(match), 1)
        plt.close(fig)

    def test_oval_profile_renders_an_ellipse_patch(self):
        # 60x35mm GW small flying oval.
        u = InitialUnit(
            uid="u1", name="flyer", army="A",
            position=(15.0, 15.0), max_health=4.0,
            base_shape="oval", base_diameter_mm=32,
            base_width_mm=35, base_length_mm=60,
        )
        fig, ax = self._render(u)
        ellipses = _patches_of(ax, Ellipse)
        match = [
            e for e in ellipses
            if abs(e.width - 35 / 25.4) < 1e-4
            and abs(e.height - 60 / 25.4) < 1e-4
        ]
        self.assertEqual(len(match), 1)
        plt.close(fig)


class UnitProfileBaseSizeFieldsTests(unittest.TestCase):
    """UnitProfile must expose the new fields with sane defaults so existing
    callers building profiles by hand don't break."""

    def test_default_profile_has_circle_32mm(self):
        from code.units import UnitProfile
        p = UnitProfile(name="x", health=1.0, damage=1.0, hit_probability=2 / 3)
        self.assertEqual(p.base_shape, "circle")
        self.assertEqual(p.base_diameter_mm, 32)
        self.assertEqual(p.base_width_mm, 32)
        self.assertEqual(p.base_length_mm, 32)

    def test_profile_with_rect_override(self):
        from code.units import UnitProfile
        p = UnitProfile(
            name="rhino", health=10.0, damage=1.0, hit_probability=2 / 3,
            base_shape="rect", base_width_mm=89, base_length_mm=152,
        )
        self.assertEqual(p.base_shape, "rect")
        self.assertEqual(p.base_width_mm, 89)
        self.assertEqual(p.base_length_mm, 152)


if __name__ == "__main__":
    unittest.main()
