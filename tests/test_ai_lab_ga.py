"""Genetic-algorithm operator tests for code/ai_lab/ga.py.

Everything except the determinism check runs on synthetic fitness data or
mocked duels — no full battles — so the suite stays fast. The AI Lab is an
exploratory sandbox outside the Stage 1 / Stage 2 calibration pipeline.
"""

from __future__ import annotations

import random
import unittest
from unittest import mock

from code.ai_lab.genome import (
    DuelGenome, GENE_SPECS, NEUTRAL_GENOME, crossover, mutate, random_genome,
)
from code.ai_lab.ga import (
    DEFAULT_CONFIRMATION_N, FitnessResult, evaluate_fitness,
    min_confirmation_n_for_threshold, run_generation, tournament_select,
    wilson_lower_bound,
)


def _fr(fitness: float) -> FitnessResult:
    return FitnessResult(fitness=fitness, win_rate=fitness, mean_margin=0.0,
                         wins=0, losses=0, draws=0, n=10)


class GenomeOperatorTests(unittest.TestCase):
    def test_mutation_respects_bounds_and_is_reproducible(self):
        rng_a = random.Random(7)
        rng_b = random.Random(7)
        genome = NEUTRAL_GENOME
        for _ in range(200):
            child_a = mutate(genome, rng_a)
            child_b = mutate(genome, rng_b)
            self.assertEqual(child_a, child_b)   # same rng seed, same child
            for spec in GENE_SPECS:
                v = getattr(child_a, spec.name)
                self.assertGreaterEqual(v, spec.low, spec.name)
                self.assertLessEqual(v, spec.high, spec.name)
            genome = child_a

    def test_crossover_stays_on_parent_segment(self):
        rng = random.Random(11)
        a = random_genome(rng)
        b = random_genome(rng)
        for _ in range(50):
            child = crossover(a, b, rng)
            for spec in GENE_SPECS:
                lo = min(getattr(a, spec.name), getattr(b, spec.name))
                hi = max(getattr(a, spec.name), getattr(b, spec.name))
                v = getattr(child, spec.name)
                self.assertGreaterEqual(v, lo - 1e-12, spec.name)
                self.assertLessEqual(v, hi + 1e-12, spec.name)

    def test_random_genome_centers_on_given_genome(self):
        rng = random.Random(13)
        center = DuelGenome(charge_aggression=2.0)
        samples = [random_genome(rng, center=center) for _ in range(300)]
        mean = sum(s.charge_aggression for s in samples) / len(samples)
        # Mean should sit near the center, not near the neutral 1.0.
        self.assertGreater(mean, 1.7)


class TournamentSelectTests(unittest.TestCase):
    def test_selection_favours_higher_fitness(self):
        rng = random.Random(3)
        weak = DuelGenome(charge_aggression=0.5)
        strong = DuelGenome(charge_aggression=2.0)
        scored = [(weak, _fr(0.2)), (strong, _fr(0.8))]
        picks = [tournament_select(scored, rng, k=2) for _ in range(400)]
        strong_share = sum(1 for p in picks if p == strong) / len(picks)
        # k=2 over two entrants: strong wins unless both draws are weak
        # (probability 1/4) -> expected share 0.75.
        self.assertGreater(strong_share, 0.65)

    def test_empty_population_fails_loud(self):
        with self.assertRaises(ValueError):
            tournament_select([], random.Random(1))


class FitnessFormulaTests(unittest.TestCase):
    """Hand-computed fitness on mocked duels — no real battles."""

    def _mock_result(self, winner, a_pts, b_pts):
        return mock.Mock(winner=winner, a_name="A", b_name="B",
                         a_points_remaining=a_pts, b_points_remaining=b_pts)

    def test_fitness_matches_hand_computation(self):
        # 4 duels; challenger is A on even indices, B on odd.
        # Duel 0 (chal=A): A wins, margin (80-0)/80 = +1.0
        # Duel 1 (chal=B): A wins -> challenger loses, margin (0-80)/80 = -1.0
        # Duel 2 (chal=A): draw, margin (40-40)/80 = 0.0
        # Duel 3 (chal=B): B wins -> challenger wins, margin (48-0)/80 = +0.6
        results = [
            self._mock_result("A", 80.0, 0.0),
            self._mock_result("A", 80.0, 0.0),
            self._mock_result(None, 40.0, 40.0),
            self._mock_result("B", 0.0, 48.0),
        ]
        with mock.patch("code.ai_lab.ga.run_duel", side_effect=results), \
             mock.patch("code.ai_lab.ga.UNIT_CATALOG",
                        {"space_marines_intercessor_squad":
                         mock.Mock(points_cost=16.0)}):
            fr = evaluate_fitness(NEUTRAL_GENOME, NEUTRAL_GENOME,
                                  epoch=0, generation=0, n_duels=4,
                                  margin_weight=0.2)
        self.assertEqual((fr.wins, fr.losses, fr.draws), (2, 1, 1))
        self.assertAlmostEqual(fr.win_rate, (2 + 0.5) / 4)
        self.assertAlmostEqual(fr.mean_margin, (1.0 - 1.0 + 0.0 + 0.6) / 4)
        self.assertAlmostEqual(fr.fitness, fr.win_rate + 0.2 * fr.mean_margin)

    def test_zero_starting_points_fails_loud(self):
        with mock.patch("code.ai_lab.ga.UNIT_CATALOG",
                        {"space_marines_intercessor_squad":
                         mock.Mock(points_cost=0.0)}):
            with self.assertRaises(ValueError):
                evaluate_fitness(NEUTRAL_GENOME, NEUTRAL_GENOME,
                                 epoch=0, generation=0, n_duels=2)


class RunGenerationTests(unittest.TestCase):
    def _patched_generation(self, fitness_by_genome, population, **kw):
        def fake_eval(genome, baseline, epoch, generation, n_duels, **kwargs):
            return _fr(fitness_by_genome[genome])
        with mock.patch("code.ai_lab.ga.evaluate_fitness",
                        side_effect=fake_eval):
            return run_generation(
                population, NEUTRAL_GENOME, epoch=0, generation=0,
                duels_per_genome=1, ga_rng=random.Random(5), **kw)

    def test_elitism_preserves_top_genomes(self):
        genomes = [DuelGenome(charge_aggression=1.0 + 0.1 * i)
                   for i in range(6)]
        fitness = {g: 0.1 * i for i, g in enumerate(genomes)}
        new_pop, stats = self._patched_generation(fitness, genomes,
                                                  elite_count=2)
        self.assertEqual(len(new_pop), len(genomes))
        self.assertEqual(new_pop[0], genomes[5])   # best carried unchanged
        self.assertEqual(new_pop[1], genomes[4])   # second-best too
        self.assertEqual(stats.best_genome, genomes[5])
        self.assertAlmostEqual(stats.best.fitness, 0.5)

    def test_elite_count_must_be_smaller_than_population(self):
        genomes = [NEUTRAL_GENOME, DuelGenome(charge_aggression=1.1)]
        with self.assertRaises(ValueError):
            self._patched_generation(
                {g: 0.5 for g in genomes}, genomes, elite_count=2)


class WilsonBoundTests(unittest.TestCase):
    def test_bound_below_point_estimate(self):
        self.assertLess(wilson_lower_bound(0.6, 100), 0.6)

    def test_bound_tightens_with_n(self):
        self.assertLess(wilson_lower_bound(0.6, 50),
                        wilson_lower_bound(0.6, 500))

    def test_known_value(self):
        # 0.55 at n=200, z=1.96: Wilson lower bound ~ 0.4808.
        self.assertAlmostEqual(wilson_lower_bound(0.55, 200), 0.4808,
                               places=3)

    def test_zero_n(self):
        self.assertEqual(wilson_lower_bound(0.5, 0), 0.0)


class PromotionGateConsistencyTests(unittest.TestCase):
    """Regression guard for a real bug found in manual testing: the shipped
    default confirmation_n=200 made a confirmation win rate sitting exactly
    at the default promotion_threshold=0.55 FAIL the Wilson lower-bound
    check (0.4808 < 0.5) — so no matter how good an evolved genome was, its
    confirmation could never mathematically pass, and every run reported
    "epoch exhausted without a promotion." min_confirmation_n_for_threshold
    and evolve_lineage's startup validation (tested in test_ai_lab_epoch.py)
    exist to make this class of misconfiguration fail loud instead."""

    def test_min_n_matches_known_crossover(self):
        # n=385 is the exact point where wr=0.55 first clears the Wilson
        # bound (n=300 -> 0.4934, still failing; n=400 -> 0.5010, passing;
        # the true minimum sits between those two coarse checkpoints).
        self.assertEqual(min_confirmation_n_for_threshold(0.55), 385)

    def test_returned_n_actually_clears_the_bound(self):
        for threshold in (0.51, 0.55, 0.60, 0.70):
            n = min_confirmation_n_for_threshold(threshold)
            self.assertGreater(wilson_lower_bound(threshold, n), 0.5)
            # And n - 1 must NOT clear it, confirming this is the minimum.
            self.assertLessEqual(wilson_lower_bound(threshold, n - 1), 0.5)

    def test_degenerate_threshold_rejected(self):
        with self.assertRaises(ValueError):
            min_confirmation_n_for_threshold(0.5)
        with self.assertRaises(ValueError):
            min_confirmation_n_for_threshold(0.4)

    def test_default_confirmation_n_covers_default_threshold(self):
        # The shipped defaults must themselves be self-consistent — this is
        # exactly the relationship that was broken (200 < 400) before the fix.
        self.assertGreaterEqual(
            DEFAULT_CONFIRMATION_N,
            min_confirmation_n_for_threshold(0.55),
        )


class DeterminismTests(unittest.TestCase):
    """Same schedule + same genomes -> identical FitnessResult (real duels)."""

    def test_evaluate_fitness_reproducible(self):
        genome = DuelGenome(charge_aggression=0.5, advance_vs_hold_bias=2.0)
        fr1 = evaluate_fitness(genome, NEUTRAL_GENOME,
                               epoch=1, generation=2, n_duels=4)
        fr2 = evaluate_fitness(genome, NEUTRAL_GENOME,
                               epoch=1, generation=2, n_duels=4)
        self.assertEqual(fr1, fr2)


if __name__ == "__main__":
    unittest.main()
