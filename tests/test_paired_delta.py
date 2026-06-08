"""Speed lever #1 — paired / Common-Random-Numbers A/B math (scripts/paired_delta).

Exercises the pure paired-statistics helpers on synthetic matched arms (no eval,
no data files): the flip count, the McNemar per-cell delta+variance, the
field-weighted combination, and the keep/reject verdict. Also checks the frame
reconstruction (_frame) on a tiny synthetic game set with explicit weights.
"""
from __future__ import annotations

import math
import unittest

from scripts.paired_delta import (
    _cell_delta_var,
    _cell_flips,
    _frame,
    _verdict,
    _weighted_delta,
)
from scripts.evaluate_vs_meta import FACTIONS


class CellFlipsTests(unittest.TestCase):
    def test_flip_to_a_win(self):
        # A-side wins games 0-4 OFF; 0-6 ON → games 5,6 flipped toward A-win.
        off = ["A"] * 5 + ["B"] * 5
        on = ["A"] * 7 + ["B"] * 3
        self.assertEqual(_cell_flips(off, on), (2, 0, 10))

    def test_identical_arms_no_flips(self):
        arm = ["A", "B", None, "A", "B"]
        self.assertEqual(_cell_flips(arm, list(arm)), (0, 0, 5))

    def test_all_flip_to_loss(self):
        off = ["A"] * 6
        on = ["B"] * 6
        self.assertEqual(_cell_flips(off, on), (0, 6, 6))

    def test_draws_are_not_a_wins(self):
        # None (draw) counts as "not an A-win"; A→None is a flip to loss.
        off = ["A", "A", None]
        on = [None, "A", "A"]
        # game0 A→None = flip-to-loss (c); game2 None→A = flip-to-win (b).
        self.assertEqual(_cell_flips(off, on), (1, 1, 3))

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            _cell_flips(["A"], ["A", "B"])


class CellDeltaVarTests(unittest.TestCase):
    def test_delta_and_variance(self):
        # b=8, c=0, n=40 → delta = +20 pts; var = (8 - 64/40)/1600*1e4 = 40.
        delta, var = _cell_delta_var(8, 0, 40)
        self.assertAlmostEqual(delta, 20.0, places=6)
        self.assertAlmostEqual(var, 40.0, places=6)

    def test_zero_n(self):
        self.assertEqual(_cell_delta_var(0, 0, 0), (0.0, 0.0))

    def test_symmetric_discordant_zero_delta(self):
        # Equal flips both ways → zero net delta, positive variance.
        delta, var = _cell_delta_var(5, 5, 50)
        self.assertAlmostEqual(delta, 0.0, places=6)
        self.assertGreater(var, 0.0)


class WeightedDeltaTests(unittest.TestCase):
    def test_equal_weights_mean(self):
        # cell1 +20 (var 40), cell2 0 (var 0), equal weights → delta 10.
        delta, se, disc = _weighted_delta([(8, 0, 40, 1.0), (0, 0, 40, 1.0)])
        self.assertAlmostEqual(delta, 10.0, places=6)
        self.assertAlmostEqual(se, math.sqrt(40.0) / 2.0, places=6)
        self.assertEqual(disc, 8)

    def test_field_weighting(self):
        # cell1 +20 weight 3, cell2 0 weight 1 → delta = 60/4 = 15.
        delta, se, disc = _weighted_delta([(8, 0, 40, 3.0), (0, 0, 40, 1.0)])
        self.assertAlmostEqual(delta, 15.0, places=6)
        self.assertAlmostEqual(se, math.sqrt(9 * 40.0) / 4.0, places=6)

    def test_empty(self):
        self.assertEqual(_weighted_delta([]), (0.0, 0.0, 0))


class VerdictTests(unittest.TestCase):
    def test_up_down_flat(self):
        self.assertEqual(_verdict(20.0, 12.0), "UP")
        self.assertEqual(_verdict(-20.0, 12.0), "DOWN")
        self.assertEqual(_verdict(5.0, 12.0), "flat")
        # CI exactly touching zero is NOT decisive.
        self.assertEqual(_verdict(12.0, 12.0), "flat")


class FrameTests(unittest.TestCase):
    def test_field_weighted_a_position_win_rate(self):
        fac, opp = FACTIONS[0], FACTIONS[1]
        # 4 games of fac (A-side) vs opp: A wins 3 → 75% A-position win rate.
        games = {
            (fac, opp, 0): "A",
            (fac, opp, 1): "A",
            (fac, opp, 2): "A",
            (fac, opp, 3): "B",
        }
        weights = {f: 1 for f in FACTIONS}
        out = _frame(games, weights)
        self.assertAlmostEqual(out[fac], 75.0, places=6)
        # A faction with no logged games scores 0 (no cells).
        self.assertEqual(out[FACTIONS[5]], 0.0)


if __name__ == "__main__":
    unittest.main()
