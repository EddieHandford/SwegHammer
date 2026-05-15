"""Tests for Phase 6 — Nash equilibrium for mixed strategies.

Phase 6 solves the symmetric zero-sum game over the trade-ratio matrix
M[i, j] = (T[j,i] - T[i,j]) / (T[i,j] + T[j,i]). The row player's optimal
mixed strategy sigma is then used as a defender-column weight in the same
closed-form weighted LSQ Phase 5 uses, plus the tactical-utility overlay.

What we check:
  * End-to-end Phase 6 runs on the live catalogue in <60s and produces a
    Phase6NashResult with the inner result tagged phase=6.
  * sigma is a valid distribution on the simplex (non-negative, sums to 1).
  * The trade-ratio payoff matrix is antisymmetric: M[i, j] == -M[j, i].
  * Phase 6 prices correlate strongly with Phase 5 prices (Pearson r > 0.7)
    on a random 50-unit sample — Nash should be in the same ball-park as the
    LSQ-with-meta solution, not a wildly different planet.
  * A synthetic high-DPS unit gets a higher sigma weight than a synthetic
    low-DPS unit — the LP isn't doing something perverse with strong/weak
    inputs.
"""

from __future__ import annotations

import random
import time
import unittest

import numpy as np

from code.equilibrium import (
    DEFAULT_ANCHOR_KEY,
    Phase6NashResult,
    _build_nash_payoff_matrix,
    compute_phase5,
    compute_phase6_nash,
    solve_nash_mixed_strategy,
)
from code.units import UnitProfile


# Cached Phase 6 run on the live catalogue — full pipeline is the most
# expensive thing the suite touches, so we share it across tests.
_PHASE6_LIVE = None


def _get_phase6_live():
    global _PHASE6_LIVE
    if _PHASE6_LIVE is None:
        _PHASE6_LIVE = compute_phase6_nash()
    return _PHASE6_LIVE


def _simple_shooty(**overrides) -> UnitProfile:
    """Minimal shooty UnitProfile for synthetic-catalogue tests."""
    defaults = dict(
        name="Synth",
        health=1.0,
        damage=1.0,
        hit_probability=2 / 3,
        attacks=2,
        range_inches=24,
        save=4,
        strength=4,
        toughness=4,
        move=6.0,
        oc=1,
        points_per_squad=10.0,
        min_models=1,
        faction="Adeptus Astartes",
    )
    defaults.update(overrides)
    return UnitProfile(**defaults)


class Phase6EndToEndTests(unittest.TestCase):
    def test_phase6_runs_endtoend(self):
        start = time.perf_counter()
        bundle = compute_phase6_nash()
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 60.0,
            f"Phase 6 took {elapsed:.2f}s on {len(bundle.result.keys)} units, "
            f"budget 60s",
        )
        self.assertIsInstance(bundle, Phase6NashResult)
        self.assertEqual(bundle.result.phase, 6)
        self.assertGreater(len(bundle.result.entries), 0)
        # Every priced unit must have a positive equilibrium price.
        for e in bundle.result.entries:
            self.assertGreater(
                e.equilibrium_points_per_model, 0.0,
                f"Phase 6 must produce positive cost for {e.key}",
            )
        # Anchor must remain pinned to its configured per-model price.
        anchor = next(
            e for e in bundle.result.entries if e.key == DEFAULT_ANCHOR_KEY
        )
        self.assertAlmostEqual(
            anchor.equilibrium_points_per_model,
            bundle.result.anchor_per_model,
            places=2,
        )


class Phase6NashStrategyTests(unittest.TestCase):
    def test_nash_strategy_on_simplex(self):
        bundle = _get_phase6_live()
        sigma = bundle.nash_strategy
        self.assertEqual(sigma.shape, (len(bundle.result.keys),))
        # All entries non-negative (within numerical slack).
        self.assertGreaterEqual(float(sigma.min()), -1e-9)
        # Sums to 1.
        self.assertAlmostEqual(float(sigma.sum()), 1.0, places=6)

    def test_anti_symmetric_payoff_matrix(self):
        bundle = _get_phase6_live()
        M = _build_nash_payoff_matrix(bundle.result.T)
        # Antisymmetry M == -M^T, to numerical precision.
        self.assertTrue(
            np.allclose(M, -M.T, atol=1e-12),
            "Trade-ratio payoff matrix must be antisymmetric",
        )
        # Diagonal exactly zero.
        self.assertTrue(np.all(np.diag(M) == 0.0))
        # Entries in [-1, 1].
        self.assertLessEqual(float(np.max(np.abs(M))), 1.0 + 1e-12)


class Phase6VsPhase5Tests(unittest.TestCase):
    def test_phase6_correlates_with_phase5(self):
        # Compute Phase 5 and Phase 6 from the SAME prior so the comparison
        # isn't muddied by RNG / catalogue drift between the two runs.
        phase5 = compute_phase5()
        phase6 = compute_phase6_nash(prior_result=phase5.result)

        p5_by_key = {
            e.key: e.equilibrium_points_per_model for e in phase5.result.entries
        }
        p6_by_key = {
            e.key: e.equilibrium_points_per_model for e in phase6.result.entries
        }
        common = sorted(set(p5_by_key) & set(p6_by_key))
        # Deterministic random 50-unit sample.
        rng = random.Random(2026)
        sample = rng.sample(common, k=min(50, len(common)))
        p5_arr = np.array([p5_by_key[k] for k in sample])
        p6_arr = np.array([p6_by_key[k] for k in sample])
        # Drop any zero/negative (shouldn't happen but defensive).
        mask = (p5_arr > 0) & (p6_arr > 0)
        p5_arr = p5_arr[mask]
        p6_arr = p6_arr[mask]
        self.assertGreater(len(p5_arr), 30, "need enough sample for correlation")
        # Pearson correlation in log-space (prices span orders of magnitude).
        r = float(np.corrcoef(np.log(p5_arr), np.log(p6_arr))[0, 1])
        self.assertGreater(
            r, 0.7,
            f"Phase 5 vs Phase 6 Pearson r = {r:.3f} on {len(p5_arr)} units; "
            f"expected > 0.7 (Nash should be in the same ball-park as LSQ).",
        )


class Phase6StrongUnitGetsWeightTests(unittest.TestCase):
    def test_strong_unit_has_higher_strategy_weight(self):
        # Build a minimal synthetic catalogue with a clearly strong unit (high
        # DPS, durable) and a clearly weak unit (low DPS, fragile) plus the
        # anchor. The Nash strategy must place strictly more weight on the
        # strong unit — if the LP put more weight on the weak one, something
        # is upside-down.
        anchor = _simple_shooty(
            name="Anchor",
            faction="Adeptus Astartes",
            points_per_squad=16.0,
            min_models=1,
        )
        strong = _simple_shooty(
            name="Strong",
            faction="Necrons",
            attacks=6,         # 3x as many shots
            strength=8,        # wounds T4 on 2+
            damage=2.0,        # 2 damage per shot
            health=3.0,        # 3W body
            save=2,
            points_per_squad=10.0,
            min_models=1,
        )
        weak = _simple_shooty(
            name="Weak",
            faction="Leagues of Votann",
            attacks=1,         # 1 shot
            strength=3,
            damage=1.0,
            health=1.0,
            save=6,
            points_per_squad=10.0,
            min_models=1,
        )
        # Two foils so the matrix isn't 3x3 sparse; same stats as anchor.
        foil_a = _simple_shooty(
            name="FoilA", faction="Tyranids", points_per_squad=10.0,
            min_models=1,
        )
        foil_b = _simple_shooty(
            name="FoilB", faction="Orks", points_per_squad=10.0,
            min_models=1,
        )
        synthetic = {
            "anchor_unit": anchor,
            "strong_unit": strong,
            "weak_unit": weak,
            "foil_a": foil_a,
            "foil_b": foil_b,
        }
        bundle = compute_phase6_nash(
            catalog=synthetic,
            anchor_key="anchor_unit",
            anchor_per_model=16.0,
        )
        idx = {k: i for i, k in enumerate(bundle.result.keys)}
        sigma = bundle.nash_strategy
        self.assertGreater(
            float(sigma[idx["strong_unit"]]),
            float(sigma[idx["weak_unit"]]),
            "Nash strategy must place more weight on the strong unit than "
            "the weak unit (sigma_strong={:.4f}, sigma_weak={:.4f}).".format(
                float(sigma[idx["strong_unit"]]),
                float(sigma[idx["weak_unit"]]),
            ),
        )


class Phase6LPHelperTests(unittest.TestCase):
    """Direct checks on the LP helper — verifies it solves a textbook game."""

    def test_lp_solves_trivial_zero_matrix(self):
        # Trivial degenerate game: M = 0. Any distribution is optimal; the
        # solver must return a valid simplex point with v = 0.
        M = np.zeros((4, 4), dtype=float)
        sigma, v, ok = solve_nash_mixed_strategy(M)
        self.assertTrue(ok)
        self.assertEqual(sigma.shape, (4,))
        self.assertAlmostEqual(float(sigma.sum()), 1.0, places=6)
        self.assertGreaterEqual(float(sigma.min()), -1e-9)
        self.assertAlmostEqual(v, 0.0, places=6)

    def test_lp_dominant_row_gets_all_weight(self):
        # 2x2 game with row 0 strictly dominating row 1:
        #   M = [[0.5, 0.3], [-0.5, -0.3]]  (antisymmetric? no — but the LP
        #   only needs M to be a payoff matrix; we don't require antisymmetry
        #   to test that the solver picks the dominating row).
        # Row player should pick row 0 entirely => sigma = [1, 0], v = 0.3.
        M = np.array([[0.5, 0.3], [-0.5, -0.3]], dtype=float)
        sigma, v, ok = solve_nash_mixed_strategy(M)
        self.assertTrue(ok)
        self.assertAlmostEqual(float(sigma[0]), 1.0, places=4)
        self.assertAlmostEqual(float(sigma[1]), 0.0, places=4)


if __name__ == "__main__":
    unittest.main()
