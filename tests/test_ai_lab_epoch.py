"""Epoch loop, promotion gate, and persistence tests for the AI Lab.

All synthetic — run_generation and evaluate_fitness are mocked so no battles
run. The AI Lab is an exploratory sandbox outside the Stage 1 / Stage 2
calibration pipeline.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from code.ai_lab.ga import (
    FitnessResult, GenerationStats, PromotionRecord, evolve_lineage,
)
from code.ai_lab.genome import DuelGenome, NEUTRAL_GENOME
from code.ai_lab.history import (
    RunRecorder, append_lineage_row, read_lineage,
)

CHAMPION = DuelGenome(charge_aggression=1.7)


def _fr(win_rate: float, n: int = 10) -> FitnessResult:
    return FitnessResult(fitness=win_rate, win_rate=win_rate,
                         mean_margin=0.0, wins=int(win_rate * n),
                         losses=n - int(win_rate * n), draws=0, n=n)


def _stats(epoch: int, generation: int, win_rate: float) -> GenerationStats:
    return GenerationStats(
        epoch=epoch, generation=generation, best_genome=CHAMPION,
        best=_fr(win_rate), mean_fitness=win_rate * 0.8,
        mean_win_rate=win_rate * 0.8, scored=[(CHAMPION, _fr(win_rate))],
    )


def _drive(gen_win_rates, confirmation_results, **kw):
    """Run evolve_lineage with mocked generation/confirmation evaluators.

    gen_win_rates: per-call best win rates for successive run_generation
    calls. confirmation_results: FitnessResults for successive confirmation
    evaluate_fitness calls.
    """
    gen_calls = []
    conf_iter = iter(confirmation_results)

    def fake_run_generation(population, baseline, epoch, generation,
                            duels_per_genome, ga_rng, **kwargs):
        gen_calls.append({"baseline": baseline, "epoch": epoch,
                          "generation": generation,
                          "population": list(population)})
        wr = gen_win_rates[len(gen_calls) - 1]
        return list(population), _stats(epoch, generation, wr)

    def fake_evaluate_fitness(genome, baseline, epoch, generation, n_duels,
                              **kwargs):
        return next(conf_iter)

    params = dict(seed_base=1, population_size=4, generations_per_epoch=3,
                  duels_per_genome=2, max_epochs=3)
    params.update(kw)
    with mock.patch("code.ai_lab.ga.run_generation",
                    side_effect=fake_run_generation), \
         mock.patch("code.ai_lab.ga.evaluate_fitness",
                    side_effect=fake_evaluate_fitness):
        events = list(evolve_lineage(**params))
    return events, gen_calls


class PromotionGateTests(unittest.TestCase):
    def test_low_win_rate_never_confirms(self):
        events, _ = _drive([0.50, 0.52, 0.54] , [])
        kinds = [k for k, _ in events]
        self.assertNotIn("confirmation", kinds)
        self.assertNotIn("promotion", kinds)
        self.assertEqual(kinds[-1], "epoch_exhausted")

    def test_confirmation_below_threshold_blocks_promotion(self):
        # Generation clears the cheap gate but the confirmation read at
        # n=200 comes back under the threshold: no promotion.
        events, _ = _drive([0.60, 0.50, 0.50], [_fr(0.52, n=200)])
        kinds = [k for k, _ in events]
        self.assertIn("confirmation", kinds)
        self.assertNotIn("promotion", kinds)

    def test_noisy_confirmation_blocks_promotion(self):
        # Point estimate clears the threshold but at tiny n the Wilson lower
        # bound stays below 0.5: "not just noise" fails.
        events, _ = _drive([0.60, 0.50, 0.50], [_fr(0.60, n=10)])
        kinds = [k for k, _ in events]
        self.assertIn("confirmation", kinds)
        self.assertNotIn("promotion", kinds)

    def test_promotion_switches_baseline_and_reseeds(self):
        # Epoch 0 gen 0 promotes (0.60 at n=200 -> wilson ~0.53 > 0.5);
        # epoch 1 then runs its generations against the NEW baseline.
        events, gen_calls = _drive(
            [0.60, 0.50, 0.50, 0.50],
            [_fr(0.60, n=200)],
        )
        kinds = [k for k, _ in events]
        self.assertIn("promotion", kinds)
        promo = next(p for k, p in events if k == "promotion")
        self.assertIsInstance(promo, PromotionRecord)
        self.assertEqual(promo.champion, CHAMPION)
        # First epoch ran against the neutral baseline...
        self.assertEqual(gen_calls[0]["baseline"], NEUTRAL_GENOME)
        # ...and every epoch-1 generation runs against the champion.
        epoch1_calls = [c for c in gen_calls if c["epoch"] == 1]
        self.assertTrue(epoch1_calls)
        for call in epoch1_calls:
            self.assertEqual(call["baseline"], CHAMPION)
        # The reseeded population is fresh (not the epoch-0 population).
        self.assertNotEqual(epoch1_calls[0]["population"],
                            gen_calls[0]["population"])

    def test_exhausted_epoch_ends_lineage(self):
        # max_epochs=3 but epoch 0 never promotes: exactly one
        # epoch_exhausted event and the generator stops.
        events, gen_calls = _drive([0.50, 0.50, 0.50], [])
        self.assertEqual([k for k, _ in events].count("epoch_exhausted"), 1)
        self.assertEqual(len(gen_calls), 3)   # only epoch 0's generations


class PromotionGateStartupValidationTests(unittest.TestCase):
    """Regression guard: evolve_lineage must refuse to run (not silently
    exhaust every epoch) when confirmation_n is too small for
    promotion_threshold to ever mathematically clear the Wilson lower
    bound — the exact "no matter what" bug found in manual testing."""

    def test_rejects_default_200_at_default_threshold(self):
        # This is the precise combination that shipped broken: n=200 can
        # never clear the Wilson bound for a 0.55 confirmation win rate.
        gen = evolve_lineage(
            seed_base=1, population_size=4, generations_per_epoch=3,
            duels_per_genome=2, max_epochs=1,
            promotion_threshold=0.55, confirmation_n=200,
        )
        with self.assertRaises(ValueError) as ctx:
            next(gen)
        self.assertIn("confirmation_n", str(ctx.exception))
        self.assertIn("385", str(ctx.exception))   # names the fix

    def test_accepts_current_defaults(self):
        # Should get PAST the validation (raise nothing on next()) even
        # though there's no real evaluate_fitness backing it here — use a
        # mock so we only assert the validation gate itself, not the loop.
        with mock.patch("code.ai_lab.ga.run_generation",
                        side_effect=lambda pop, *a, **k: (
                            pop, _stats(0, 0, 0.5))):
            gen = evolve_lineage(
                seed_base=1, population_size=4, generations_per_epoch=1,
                duels_per_genome=2, max_epochs=1,
            )
            kind, _ = next(gen)   # no ValueError
        self.assertEqual(kind, "generation")


class LineageCsvTests(unittest.TestCase):
    def test_append_and_read_round_trip(self):
        record = PromotionRecord(
            epoch=1, generation=4, champion=CHAMPION,
            confirmation=_fr(0.61, n=200), wilson_lower=0.5405,
            generations_to_promote=5,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lineage.csv")
            append_lineage_row(record, label="first strain", csv_path=path)
            rows = read_lineage(path)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["epoch"], "1")
        self.assertEqual(row["parent_epoch"], "0")
        self.assertEqual(row["confirmation_n"], "200")
        self.assertEqual(row["label"], "first strain")
        self.assertEqual(
            DuelGenome.from_dict(json.loads(row["champion_genome_json"])),
            CHAMPION)

    def test_missing_file_reads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                read_lineage(os.path.join(tmp, "absent.csv")), [])


class RunRecorderTests(unittest.TestCase):
    def test_snapshot_shape(self):
        recorder = RunRecorder({"population_size": 4}, run_id="run_test")
        recorder.on_event("generation", _stats(0, 0, 0.58), NEUTRAL_GENOME)
        recorder.on_event("generation", _stats(0, 1, 0.61), NEUTRAL_GENOME)
        promo = PromotionRecord(
            epoch=0, generation=1, champion=CHAMPION,
            confirmation=_fr(0.61, n=200), wilson_lower=0.541,
            generations_to_promote=2,
        )
        recorder.on_event("promotion", promo, NEUTRAL_GENOME)
        recorder.on_event("generation", _stats(1, 0, 0.45), CHAMPION)
        with tempfile.TemporaryDirectory() as tmp:
            path = recorder.save(runs_dir=tmp)
            with open(path, encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["run_id"], "run_test")
        self.assertIn("built_at", snap)
        self.assertEqual(snap["params"], {"population_size": 4})
        self.assertEqual(len(snap["epochs"]), 2)
        epoch0 = snap["epochs"][0]
        self.assertEqual(len(epoch0["generations"]), 2)
        self.assertEqual(epoch0["baseline_genome"],
                         NEUTRAL_GENOME.as_dict())
        self.assertEqual(epoch0["promoted"]["confirmation_n"], 200)
        epoch1 = snap["epochs"][1]
        self.assertEqual(epoch1["baseline_genome"], CHAMPION.as_dict())
        self.assertIsNone(epoch1["promoted"])


if __name__ == "__main__":
    unittest.main()
