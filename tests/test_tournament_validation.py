"""Tests for the tournament-list validation module.

These tests use the real scraped JSON files in data/tournament_lists/ so we
catch regressions in the loader and matcher as that data evolves. The
regression-fit test uses real UNIT_CATALOG + equation, so this also acts as
a smoke test that the equation can run against tournament data end-to-end.
"""
from __future__ import annotations

import unittest

from code.equation_data_fit import (
    default_feature_specs,
    extract_features,
    fit as eqfit_fit,
)
from code.tournament_validation import (
    ListRecord,
    MatchResult,
    TournamentUnit,
    aggregate_by_faction,
    aggregate_unit_appearances,
    fit_winrate_model,
    load_tournament_lists,
    match_units,
    score_list,
)
from code.units import UNIT_CATALOG


class LoadTournamentListsTest(unittest.TestCase):

    def test_flattens_events_and_drops_partials(self):
        lists = load_tournament_lists()
        # ~25 non-partial lists across the three scraped Goonhammer
        # articles currently in the repo. Threshold deliberately well below
        # that so the test survives one article being temporarily removed.
        self.assertGreater(len(lists), 15,
                           "Expected at least 15 lists across the scraped "
                           "tournaments — the loader may be dropping valid "
                           "lists, or the data folder is empty.")
        # No partial lists should survive the loader.
        for lr in lists:
            self.assertTrue(lr.faction,
                            f"List for {lr.player!r} has no faction")
            self.assertGreater(len(lr.units), 0,
                               f"List for {lr.player!r} has no units")


class MatchUnitsTest(unittest.TestCase):

    def test_matches_obvious_aeldari_units(self):
        record = ListRecord(
            source_file="(synthetic)",
            event_name="Test Event",
            event_date="2026-05-01",
            event_size=20,
            player="Test Player",
            placement=1,
            wins=5, losses=1, draws=0,
            faction="Aeldari",
            detachment="Aspect Host",
            total_points=2000,
            units=[
                TournamentUnit("Fire Prism", 1, 150),
                TournamentUnit("Wave Serpent", 1, 125),
                TournamentUnit("Asurmen", 1, 135),
            ],
        )
        m = match_units(record)
        matched_keys = [k for k, _, _ in m.matched_units]
        self.assertIn("aeldari_craftworlds_fire_prism", matched_keys)
        self.assertIn("aeldari_craftworlds_wave_serpent", matched_keys)
        self.assertIn("aeldari_craftworlds_asurmen", matched_keys)
        self.assertEqual(m.unmatched, [],
                         f"Expected zero unmatched, got {m.unmatched}")

    def test_unmatched_unit_counted_in_coverage(self):
        record = ListRecord(
            source_file="(synthetic)",
            event_name="Test Event", event_date=None, event_size=None,
            player="", placement=None, wins=None, losses=None, draws=None,
            faction="Aeldari", detachment=None, total_points=200,
            units=[
                TournamentUnit("Fire Prism", 1, 150),
                TournamentUnit("Bogus Made Up Datasheet", 1, 50),
            ],
        )
        m = match_units(record)
        self.assertEqual(len(m.matched_units), 1)
        self.assertEqual(len(m.unmatched), 1)
        self.assertEqual(m.coverage_points, 150)
        self.assertEqual(m.total_points, 200)
        self.assertAlmostEqual(m.coverage_ratio, 0.75, places=3)


class ScoreListTest(unittest.TestCase):

    def test_score_handles_partial_coverage(self):
        feats = extract_features()
        result = eqfit_fit(feats)

        record = ListRecord(
            source_file="(synthetic)",
            event_name="Test Event", event_date=None, event_size=None,
            player="", placement=None, wins=None, losses=None, draws=None,
            faction="Aeldari", detachment=None, total_points=200,
            units=[
                TournamentUnit("Fire Prism", 1, 150),
                TournamentUnit("Bogus Made Up Datasheet", 1, 50),
            ],
        )
        m = match_units(record)
        score = score_list(m, result, feats, faction_multipliers={})
        self.assertIsNotNone(score)
        # Matched 75% of points; predicted_total only counts the matched unit.
        self.assertAlmostEqual(score.match.coverage_ratio, 0.75, places=3)
        self.assertEqual(score.gw_total, 150)
        self.assertGreater(score.predicted_total, 0.0)
        # overrun_per_2000 should scale the (matched + unmatched_paid) ratio
        # up to a 2000-pt budget. Sanity-check it's finite.
        self.assertTrue(score.overrun_per_2000 == score.overrun_per_2000)  # not NaN


class FitWinrateModelTest(unittest.TestCase):

    def test_end_to_end_regression_returns_finite_stats(self):
        feats = extract_features()
        result = eqfit_fit(feats)

        lists = load_tournament_lists()
        scores = []
        for lr in lists:
            m = match_units(lr)
            s = score_list(m, result, feats, faction_multipliers={})
            if s is not None:
                scores.append(s)

        self.assertGreater(len(scores), 10,
                           "Expected to score at least 10 tournament lists; "
                           "the matcher may be rejecting too many units.")

        wr_fit = fit_winrate_model(scores, target="winrate")
        if wr_fit is not None:
            self.assertTrue(-1.0 <= wr_fit.r_squared <= 1.0,
                            f"R² out of range: {wr_fit.r_squared}")
            self.assertGreater(wr_fit.n, 0)

        # Placement percentile is available for most lists; that fit should
        # almost certainly come back populated.
        pp_fit = fit_winrate_model(scores, target="placement")
        self.assertIsNotNone(pp_fit,
                             "Placement-percentile regression returned None "
                             "despite real tournament data having placements.")
        self.assertGreater(pp_fit.n, 5)


class AggregationTest(unittest.TestCase):

    def test_unit_appearances_aggregates_across_lists(self):
        feats = extract_features()
        result = eqfit_fit(feats)
        lists = load_tournament_lists()
        scores = []
        for lr in lists:
            s = score_list(match_units(lr), result, feats, faction_multipliers={})
            if s is not None:
                scores.append(s)
        agg = aggregate_unit_appearances(scores, feats)
        self.assertFalse(agg.empty, "Unit appearance aggregation produced no rows")
        self.assertIn("overrun_ratio", agg.columns)
        # Sorted by total_gw_points descending.
        gw = agg["total_gw_points"].to_numpy()
        self.assertTrue((gw[:-1] >= gw[1:]).all())

    def test_faction_aggregation_has_one_row_per_faction(self):
        feats = extract_features()
        result = eqfit_fit(feats)
        lists = load_tournament_lists()
        scores = []
        for lr in lists:
            s = score_list(match_units(lr), result, feats, faction_multipliers={})
            if s is not None:
                scores.append(s)
        fac_df = aggregate_by_faction(scores)
        # Number of unique factions in the scored sample.
        unique_facs = {s.match.list_record.faction for s in scores}
        self.assertEqual(len(fac_df), len(unique_facs))


if __name__ == "__main__":
    unittest.main()
