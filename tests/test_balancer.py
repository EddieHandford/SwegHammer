"""Tests for the empirical points balancer.

The balancer runs real Monte-Carlo battles, so we keep budgets and counts
small. Tiny budgets give the cleanest signal: at points_override=5 a side
fields ~40 squads vs the baseline's 3, which crushes; at points_override=200
the same budget can't even afford one squad, which loses outright.
"""

from __future__ import annotations

import random
import unittest
from dataclasses import replace

from code.balancer import (
    AUTO_BASELINE,
    DEFAULT_BASELINE,
    find_balanced_points,
    measure_win_rate,
    resolve_baseline,
)
from code.roles import baseline_key_for, classify
from code.units import UNIT_CATALOG


_BASELINE_KEY = "space_marines_intercessor_squad"
# A canonical HEAVY-role unit used as the "previously-untunable" target
# in auto-baseline coverage. Knight Errant is itself the HEAVY baseline,
# but the C'tan-shard is sv=4 and lands in MELEE — we only need *any*
# unit whose role baseline isn't the default Intercessor.
_HEAVY_UNIT_KEY = "imperial_knights_library_knight_paladin"


class MeasureWinRateTests(unittest.TestCase):

    def test_returns_float_in_unit_interval(self):
        baseline = UNIT_CATALOG[_BASELINE_KEY]
        rng = random.Random(42)
        wr = measure_win_rate(baseline, baseline, 200, n_battles=5, rng=rng)
        self.assertIsInstance(wr, float)
        self.assertGreaterEqual(wr, 0.0)
        self.assertLessEqual(wr, 1.0)

    def test_severely_undercosted_unit_dominates(self):
        baseline = UNIT_CATALOG[_BASELINE_KEY]
        cheap = replace(baseline, points_override=5.0)
        rng = random.Random(42)
        wr = measure_win_rate(cheap, baseline, 200, n_battles=10, rng=rng)
        self.assertGreater(wr, 0.55)

    def test_severely_overcosted_unit_loses(self):
        baseline = UNIT_CATALOG[_BASELINE_KEY]
        # Baseline Intercessor is ~65 pts. At pts=200, budget=200 can field
        # exactly 1 squad while the baseline fields 3 — the lone squad gets
        # mauled.
        expensive = replace(baseline, points_override=200.0)
        rng = random.Random(42)
        wr = measure_win_rate(expensive, baseline, 200, n_battles=10, rng=rng)
        self.assertLess(wr, 0.45)


class ResolveBaselineTests(unittest.TestCase):
    """The baseline-picker should respect explicit overrides, fall back to
    role baselines when asked for auto, and never return self-vs-self."""

    def test_explicit_baseline_wins(self):
        # Even for a HEAVY unit, an explicit key passes straight through.
        self.assertEqual(
            resolve_baseline(_HEAVY_UNIT_KEY, "orks_boyz"),
            "orks_boyz",
        )

    def test_auto_uses_role_baseline(self):
        unit = UNIT_CATALOG[_HEAVY_UNIT_KEY]
        expected = baseline_key_for(classify(unit))
        self.assertEqual(resolve_baseline(_HEAVY_UNIT_KEY, AUTO_BASELINE), expected)

    def test_none_baseline_uses_role_baseline(self):
        unit = UNIT_CATALOG[_HEAVY_UNIT_KEY]
        expected = baseline_key_for(classify(unit))
        self.assertEqual(resolve_baseline(_HEAVY_UNIT_KEY, None), expected)

    def test_auto_avoids_self_vs_self(self):
        # The Intercessor Squad IS the DUAL/SHOOTY role baseline; calibrating
        # it under auto must not pick itself. Falls back to DEFAULT_BASELINE
        # (also itself in this case) -> the same-role-peer search kicks in.
        result = resolve_baseline(_BASELINE_KEY, AUTO_BASELINE)
        self.assertNotEqual(result, _BASELINE_KEY)
        self.assertIn(result, UNIT_CATALOG)


class FindBalancedPointsAutoBaselineTests(unittest.TestCase):
    """Cheap smoke coverage: a single iteration is enough to prove the
    auto-baseline plumbing flows through to the CalibrationResult."""

    def _quick(self, key, **kwargs):
        return find_balanced_points(
            key,
            n_battles=2,
            max_iters=1,
            points_budget=500.0,
            rng=random.Random(0),
            **kwargs,
        )

    def test_auto_baseline_for_heavy_unit_does_not_crash(self):
        r = self._quick(_HEAVY_UNIT_KEY, auto_baseline=True)
        self.assertIn(r.baseline_key, UNIT_CATALOG)

    def test_auto_baseline_matches_role_lookup(self):
        unit = UNIT_CATALOG[_HEAVY_UNIT_KEY]
        expected = baseline_key_for(classify(unit))
        r = self._quick(_HEAVY_UNIT_KEY, auto_baseline=True)
        self.assertEqual(r.baseline_key, expected)

    def test_explicit_baseline_overrides_auto(self):
        # Explicit baseline wins even when auto_baseline=True.
        r = self._quick(
            _HEAVY_UNIT_KEY,
            baseline_key="orks_boyz",
            auto_baseline=True,
        )
        self.assertEqual(r.baseline_key, "orks_boyz")

    def test_default_baseline_when_auto_disabled(self):
        r = self._quick(_HEAVY_UNIT_KEY, auto_baseline=False)
        self.assertEqual(r.baseline_key, DEFAULT_BASELINE)


if __name__ == "__main__":
    unittest.main()
