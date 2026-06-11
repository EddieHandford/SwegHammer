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


def _u(pos, *, attacks=0, hit=0.0, dmg=0.0, rng=0.0):
    """Unit stand-in with a profile carrying just the ranged fields the
    gunline-disruption exemption reads. Defaults = a non-shooter (zero output)."""
    return SimpleNamespace(
        position=pos,
        profile=SimpleNamespace(
            attacks=attacks, hit_probability=hit,
            weapon_damage_per_shot=dmg, range_inches=rng,
        ),
    )


class M4ClusterIntentTests(unittest.TestCase):
    """The clustering heuristic gates (helper is gate-independent; the gate is
    checked at the pick_move_intent call site)."""

    def test_near_marker_oc_model_clusters_into_band(self):
        m = _map()
        # 4" from the centre — in the 3"-6" strand band, OC not scoring.
        unit = _u((34.0, 30.0))
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
        unit = _u((31.0, 30.0))   # 1" from centre
        self.assertIsNone(_m4_cluster_intent(unit, 2, [], m.objectives, m))

    def test_zero_oc_model_not_repositioned(self):
        m = _map()
        unit = _u((34.0, 30.0))
        self.assertIsNone(
            _m4_cluster_intent(unit, 0, [], m.objectives, m),
            "A 0-OC support model contributes no Objective Control, so it is "
            "left to shoot, not dragged onto the marker.",
        )

    def test_locked_in_melee_no_move(self):
        m = _map()
        unit = _u((34.0, 30.0))
        # Enemy stand-ins need a profile since wave 241: the melee-lock check
        # measures Engagement Range base-edge to base-edge (`_er_gap`), which
        # reads the base footprint off the profile (absent base data defaults
        # to a 32mm round base).
        enemy = _u((34.4, 30.0))   # within Engagement Range
        self.assertIsNone(
            _m4_cluster_intent(unit, 2, [enemy], m.objectives, m),
            "A model locked in melee is left to the fight / fall-back logic.",
        )

    def test_far_from_any_marker_no_move(self):
        m = _map()
        unit = _u((50.0, 30.0))   # 20" away
        self.assertIsNone(
            _m4_cluster_intent(unit, 2, [], m.objectives, m),
            "Only models already committed near a marker (<=6\") tighten in; a "
            "distant unit is not dragged across the board.",
        )

    def test_move_costs_a_shot_exempts(self):
        # Wave 132: a heavy weapon whose target is in range NOW but OUT of range
        # from the marker (the move breaks the shot) holds its firing line.
        m = _map()   # marker at (30, 30)
        heavy = _u((34.0, 30.0), attacks=1, hit=0.6, dmg=6.0, rng=12.0)
        enemy = _u((44.0, 30.0))   # 10" from heavy (in range), 14" from marker (out)
        self.assertIsNone(
            _m4_cluster_intent(heavy, 2, [enemy], m.objectives, m),
            "A shooter that would LOSE its shot by moving to the marker holds "
            "its firing line (the move costs a shot).",
        )

    def test_hold_and_shoot_still_pulled(self):
        # A long-range gun that can shoot its target FROM the marker too is
        # pulled — it holds the objective AND keeps firing.
        m = _map()   # marker at (30, 30)
        gun = _u((34.0, 30.0), attacks=1, hit=0.6, dmg=6.0, rng=48.0)
        enemy = _u((45.0, 30.0))   # 15" from marker, within 48"
        self.assertIsNotNone(
            _m4_cluster_intent(gun, 2, [enemy], m.objectives, m),
            "A hold-and-shoot model (target in range from the marker) is pulled "
            "— it both holds and fires, not stranded off the objective.",
        )

    def test_shooter_with_no_target_pulled(self):
        m = _map()
        heavy = _u((34.0, 30.0), attacks=1, hit=0.6, dmg=6.0, rng=12.0)
        enemy = _u((55.0, 55.0))   # far out of any range
        self.assertIsNotNone(
            _m4_cluster_intent(heavy, 2, [enemy], m.objectives, m),
            "A gun with no eligible target loses nothing by holding — pull it.",
        )

    def test_cheap_trooper_still_massed(self):
        # A lasgun trooper (low output) near the marker tightens in regardless.
        m = _map()
        trooper = _u((34.0, 30.0), attacks=1, hit=0.5, dmg=1.0, rng=24.0)  # ~0.5 output
        enemy = _u((44.0, 30.0))
        self.assertIsNotNone(
            _m4_cluster_intent(trooper, 2, [enemy], m.objectives, m),
            "A low-output trooper is not a gunline piece — it masses on the "
            "marker even with an enemy in lasgun range.",
        )


if __name__ == "__main__":  # pragma: no cover - convenience runner
    unittest.main()
