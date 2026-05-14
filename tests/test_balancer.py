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

from code.balancer import measure_win_rate
from code.units import UNIT_CATALOG


_BASELINE_KEY = "space_marines_intercessor_squad"


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


if __name__ == "__main__":
    unittest.main()
