"""Tests for the real-world base-footprint renderer path.

The renderer draws each unit using its `base_shape` + millimetre dimensions
sourced from `UnitProfile`, converted to world inches at 25.4 mm/inch and then
to pixels. The renderer is Pillow-based: `_draw_unit_base` draws onto an
`ImageDraw` canvas (no matplotlib), and `render_frame` returns a PIL `Image`.
These tests assert that:

  - circle profiles -> a square-bounded `draw.ellipse` sized by `base_diameter_mm`
  - rect profiles   -> a `draw.rectangle` sized by `base_width_mm` x `base_length_mm`
  - oval profiles   -> a rectangular-bounded `draw.ellipse`
  - an unknown shape falls back to a circle
  - the default UnitProfile (no override) renders as a 32mm round
  - `render_frame` completes end-to-end and returns a PIL image (regression
    guard for the half-migrated renderer that referenced an undefined `cx`)

The tests build a minimal event log by hand (one `BattleStarted` carrying an
`InitialUnit` per scenario) so they're independent of the simulator and the
BSData catalogue.
"""

from __future__ import annotations

import unittest
from unittest import mock

from PIL import Image

import code.renderer as renderer
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


class MmToInchesTests(unittest.TestCase):

    def test_one_inch_is_25_4_mm(self):
        # GW scale: 25.4 mm/inch. A 25.4mm base is exactly 1 world inch.
        self.assertAlmostEqual(_mm_to_inches(MM_PER_INCH), 1.0, places=6)

    def test_32mm_marine_is_just_over_an_inch(self):
        # Standard Marine 32mm -> ~1.26 world inches.
        self.assertAlmostEqual(_mm_to_inches(32), 32 / 25.4, places=6)


class DrawUnitBaseTests(unittest.TestCase):
    """Unit-test the Pillow shape dispatcher directly via a recording mock.

    `_draw_unit_base(draw, cx, cy, color, base_shape, w_px, h_px)` takes
    pre-computed pixel half-extents and issues exactly one Pillow primitive:
    `draw.rectangle` for rect, `draw.ellipse` for oval / circle / fallback.
    """

    def test_circle_shape_draws_square_bounded_ellipse(self):
        draw = mock.Mock()
        # 20px diameter base centred at (50, 70) -> half-extent 10.
        _draw_unit_base(draw, 50, 70, (255, 0, 0, 255), "circle",
                        w_px=20, h_px=20)
        draw.ellipse.assert_called_once()
        draw.rectangle.assert_not_called()
        bbox = draw.ellipse.call_args[0][0]
        self.assertEqual(list(bbox), [40, 60, 60, 80])

    def test_rect_shape_draws_rectangle_with_correct_bbox(self):
        # Rhino-ish footprint: 40px wide x 80px tall, centred at (100, 100).
        draw = mock.Mock()
        _draw_unit_base(draw, 100, 100, (0, 255, 0, 255), "rect",
                        w_px=40, h_px=80)
        draw.rectangle.assert_called_once()
        draw.ellipse.assert_not_called()
        bbox = draw.rectangle.call_args[0][0]
        self.assertEqual(list(bbox), [80, 60, 120, 140])

    def test_oval_shape_draws_rectangular_bounded_ellipse(self):
        # GW small flying oval: distinct width vs length -> rectangular bbox.
        draw = mock.Mock()
        _draw_unit_base(draw, 100, 100, (0, 0, 255, 255), "oval",
                        w_px=30, h_px=60)
        draw.ellipse.assert_called_once()
        draw.rectangle.assert_not_called()
        bbox = draw.ellipse.call_args[0][0]
        self.assertEqual(list(bbox), [85, 70, 115, 130])
        # rectangular, not square
        self.assertNotEqual(bbox[2] - bbox[0], bbox[3] - bbox[1])

    def test_unknown_shape_falls_back_to_circle(self):
        # A bad override value shouldn't take the renderer down — it falls back
        # to a square-bounded ellipse (circle) sized by the width.
        draw = mock.Mock()
        _draw_unit_base(draw, 100, 100, (255, 255, 255, 255), "bogus",
                        w_px=50, h_px=50)
        draw.ellipse.assert_called_once()
        draw.rectangle.assert_not_called()
        bbox = draw.ellipse.call_args[0][0]
        self.assertEqual(list(bbox), [75, 75, 125, 125])


class RenderFrameBaseShapeTests(unittest.TestCase):
    """End-to-end: build a minimal event log, render it, and capture the
    (base_shape, w_px, h_px) that reaches `_draw_unit_base`. Also asserts the
    frame renders to a PIL image — the regression guard for the unbound-`cx`
    crash in the half-migrated renderer."""

    def _render_capturing(self, initial_unit: InitialUnit):
        events = [_battle_started([initial_unit])]
        frames = aggregate_activations(events)
        calls: list = []
        real = renderer._draw_unit_base

        def _spy(draw, cx, cy, color, base_shape, w_px, h_px):
            calls.append((base_shape, w_px, h_px))
            return real(draw, cx, cy, color, base_shape, w_px, h_px)

        with mock.patch.object(renderer, "_draw_unit_base", _spy):
            img = render_frame(_empty_map(), events, frame=0, frames=frames)
        return img, calls

    def test_default_profile_renders_as_32mm_circle(self):
        # Default InitialUnit (no base overrides) -> 32mm round.
        u = InitialUnit(
            uid="u1", name="default", army="A",
            position=(5.0, 5.0), max_health=1.0,
        )
        img, calls = self._render_capturing(u)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(len(calls), 1)
        shape, w_px, h_px = calls[0]
        self.assertEqual(shape, "circle")
        # circle -> square footprint
        self.assertAlmostEqual(w_px, h_px, places=6)
        self.assertGreater(w_px, 0)

    def test_rect_profile_reaches_renderer_with_rhino_ratio(self):
        # Rhino-ish footprint via the InitialUnit overrides (89 x 152 mm).
        u = InitialUnit(
            uid="u1", name="vehicle", army="A",
            position=(10.0, 10.0), max_health=10.0,
            base_shape="rect", base_diameter_mm=32,
            base_width_mm=89, base_length_mm=152,
        )
        img, calls = self._render_capturing(u)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(len(calls), 1)
        shape, w_px, h_px = calls[0]
        self.assertEqual(shape, "rect")
        # the mm aspect ratio is preserved through the mm->inch->px pipeline
        self.assertAlmostEqual(w_px / h_px, 89 / 152, places=5)

    def test_oval_profile_reaches_renderer_with_flyer_ratio(self):
        # 60x35mm GW small flying oval.
        u = InitialUnit(
            uid="u1", name="flyer", army="A",
            position=(15.0, 15.0), max_health=4.0,
            base_shape="oval", base_diameter_mm=32,
            base_width_mm=35, base_length_mm=60,
        )
        img, calls = self._render_capturing(u)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(len(calls), 1)
        shape, w_px, h_px = calls[0]
        self.assertEqual(shape, "oval")
        self.assertAlmostEqual(w_px / h_px, 35 / 60, places=5)


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
