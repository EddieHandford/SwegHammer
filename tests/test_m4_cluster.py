"""Tests for M4-α squad-cluster positioning (anti-Knight stack component 1).

`SWEG_M4` (default OFF). A model carrying Objective Control that is near but not
tight on a marker, and not locked in melee, genuinely moves to a slot inside the
3" scoring band so a squad masses its surviving OC on the objective rather than
stranding half of it in the 3"-6" band. Faithful positioning (A1), even-handed
(a 1-model unit is unaffected — it already parks on the centre). Cited
`simulator.m4_squad_cluster`.
"""

from __future__ import annotations

import math
import os
import unittest
from types import SimpleNamespace

from code.map import Map, Objective
from code.strategy import _m4_cluster_intent, _m4_enabled, _CAPTURE_INTENT


def _map() -> Map:
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _d(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


class M4GateTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("SWEG_M4", None)

    def tearDown(self):
        os.environ.pop("SWEG_M4", None)

    def test_gate_default_off(self):
        self.assertFalse(_m4_enabled())

    def test_gate_on(self):
        os.environ["SWEG_M4"] = "1"
        self.assertTrue(_m4_enabled())


class M4ClusterIntentTests(unittest.TestCase):
    """The clustering heuristic gates (helper is gate-independent; the gate is
    checked at the pick_move_intent call site)."""

    def test_near_marker_oc_model_clusters_into_band(self):
        m = _map()
        # 4" from the centre — in the 3"-6" strand band, OC not scoring.
        unit = SimpleNamespace(position=(34.0, 30.0))
        res = _m4_cluster_intent(unit, 2, [], m.objectives, m)
        self.assertIsNotNone(res)
        slot, intent = res
        self.assertEqual(intent, _CAPTURE_INTENT)
        self.assertLessEqual(
            _d(slot, (30.0, 30.0)), 3.0,
            "The cluster slot must sit inside the 3\" scoring band.",
        )

    def test_already_tight_no_move(self):
        m = _map()
        unit = SimpleNamespace(position=(31.0, 30.0))   # 1" from centre
        self.assertIsNone(_m4_cluster_intent(unit, 2, [], m.objectives, m))

    def test_zero_oc_model_not_repositioned(self):
        m = _map()
        unit = SimpleNamespace(position=(34.0, 30.0))
        self.assertIsNone(
            _m4_cluster_intent(unit, 0, [], m.objectives, m),
            "A 0-OC support model contributes no Objective Control, so it is "
            "left to shoot, not dragged onto the marker.",
        )

    def test_locked_in_melee_no_move(self):
        m = _map()
        unit = SimpleNamespace(position=(34.0, 30.0))
        enemy = SimpleNamespace(position=(34.4, 30.0))   # within Engagement Range
        self.assertIsNone(
            _m4_cluster_intent(unit, 2, [enemy], m.objectives, m),
            "A model locked in melee is left to the fight / fall-back logic.",
        )

    def test_far_from_any_marker_no_move(self):
        m = _map()
        unit = SimpleNamespace(position=(50.0, 30.0))   # 20" away
        self.assertIsNone(
            _m4_cluster_intent(unit, 2, [], m.objectives, m),
            "Only models already committed near a marker (<=6\") tighten in; a "
            "distant unit is not dragged across the board.",
        )


if __name__ == "__main__":  # pragma: no cover - convenience runner
    unittest.main()
