"""Hermetic tests for scripts/regression_sentinel.py.

No eval runs, no real game-log files, no data-file dependency (beyond what
paired_delta imports at module level, which are pure arithmetic helpers).
All assertions run against synthetic ledger dicts built inline.
"""
from __future__ import annotations

import unittest

from scripts.regression_sentinel import detect_drift, _first_out_of_band_wave


# ---------------------------------------------------------------------------
# Shared synthetic-ledger helpers.
# ---------------------------------------------------------------------------

def _make_entry(wave: str, gated_on: float, in_band: list, frame: dict) -> dict:
    """Build a minimal synthetic ledger entry for testing."""
    return {
        "wave": wave,
        "matched": 100,
        "gated_off": gated_on + 0.5,
        "gated_on": gated_on,
        "decisive": [],
        "in_band": in_band,
        "frame_gated_on": frame,
    }


# ---------------------------------------------------------------------------
# detect_drift tests.
# ---------------------------------------------------------------------------

class TestDetectDriftNoRegression(unittest.TestCase):
    """A clean ledger where no faction regresses should produce no findings."""

    def test_all_in_band_across_waves(self):
        # Three waves; same factions in-band throughout.
        entries = [
            _make_entry("wave1", 2.0, ["FacA", "FacB"],
                        {"FacA": 0.0, "FacB": 0.0, "FacC": 1.5}),
            _make_entry("wave2", 1.8, ["FacA", "FacB"],
                        {"FacA": 0.0, "FacB": 0.0, "FacC": 1.3}),
            _make_entry("wave3", 1.7, ["FacA", "FacB"],
                        {"FacA": 0.0, "FacB": 0.0, "FacC": 1.1}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        self.assertEqual(findings, [], msg=f"Expected no findings, got: {findings}")

    def test_single_entry_returns_empty(self):
        # With only one entry there is nothing to compare against.
        entries = [
            _make_entry("wave1", 3.0, ["FacA"], {"FacA": 0.0, "FacB": 2.5}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        self.assertEqual(findings, [])

    def test_empty_ledger_returns_empty(self):
        self.assertEqual(detect_drift([], threshold=1.0), [])

    def test_faction_never_in_band_not_flagged(self):
        # FacC was never in-band earlier, so even if it grows, it is not a regression.
        entries = [
            _make_entry("wave1", 2.0, ["FacA"],
                        {"FacA": 0.0, "FacC": 0.8}),
            _make_entry("wave2", 2.5, ["FacA"],
                        {"FacA": 0.0, "FacC": 1.5}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        self.assertEqual(findings, [])

    def test_no_headline_creep_when_stable(self):
        # Headline gated_on stays at 2.0 across waves — no creep.
        entries = [
            _make_entry("wave1", 2.0, [], {}),
            _make_entry("wave2", 2.0, [], {}),
            _make_entry("wave3", 2.0, [], {}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        self.assertEqual(findings, [])


class TestDetectDriftFactionRegression(unittest.TestCase):
    """Factions that were in-band then go out-of-band should be flagged."""

    def test_single_faction_regresses(self):
        entries = [
            # wave1: FacA is in-band
            _make_entry("wave1", 3.0, ["FacA"],
                        {"FacA": 0.0, "FacB": 1.5}),
            # wave2: FacA still in-band
            _make_entry("wave2", 2.5, ["FacA"],
                        {"FacA": 0.0, "FacB": 1.2}),
            # wave3 (latest): FacA has regressed out of band
            _make_entry("wave3", 3.2, [],
                        {"FacA": 1.8, "FacB": 1.0}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        self.assertEqual(len(findings), 1)
        # The finding should name FacA and the first-out-of-band wave (wave3).
        self.assertIn("FacA", findings[0])
        self.assertIn("wave3", findings[0])
        self.assertIn("DRIFT", findings[0])

    def test_bisect_hint_is_first_out_of_band_wave(self):
        # FacA goes out-of-band at wave2 (not wave3).  The bisect hint must
        # point to wave2, even though wave3 is the latest.
        entries = [
            _make_entry("wave1", 3.0, ["FacA"],
                        {"FacA": 0.0}),
            _make_entry("wave2", 3.5, [],       # FacA first goes out here
                        {"FacA": 2.0}),
            _make_entry("wave3", 3.8, [],       # still out
                        {"FacA": 2.5}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        self.assertEqual(len(findings), 1)
        self.assertIn("wave2", findings[0], msg="bisect hint should be wave2")
        self.assertNotIn("wave3", findings[0])

    def test_multiple_factions_regress(self):
        entries = [
            _make_entry("wave1", 2.0, ["FacA", "FacB"],
                        {"FacA": 0.0, "FacB": 0.0}),
            _make_entry("wave2", 4.0, [],
                        {"FacA": 1.5, "FacB": 2.0}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        fac_names = {f.split(":")[0].replace("DRIFT ", "").strip() for f in findings}
        self.assertIn("FacA", fac_names)
        self.assertIn("FacB", fac_names)

    def test_threshold_respected(self):
        # With threshold=2.0 a gated_on of 1.8 should NOT trigger.
        entries = [
            _make_entry("wave1", 2.0, ["FacA"], {"FacA": 0.0}),
            _make_entry("wave2", 3.0, [],       {"FacA": 1.8}),
        ]
        findings = detect_drift(entries, threshold=2.0)
        faction_drifts = [f for f in findings if "DRIFT" in f]
        self.assertEqual(faction_drifts, [])

    def test_threshold_boundary_exclusive(self):
        # gated_on exactly AT the threshold is NOT flagged (> not >=).
        entries = [
            _make_entry("wave1", 2.0, ["FacA"], {"FacA": 0.0}),
            _make_entry("wave2", 3.0, [],       {"FacA": 1.0}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        faction_drifts = [f for f in findings if "DRIFT" in f]
        self.assertEqual(faction_drifts, [])


class TestDetectDriftHeadlineCreep(unittest.TestCase):
    """Headline gated_on creeping upward by more than threshold should be flagged."""

    def test_creep_detected(self):
        entries = [
            _make_entry("wave1", 2.0, [], {}),
            _make_entry("wave2", 2.5, [], {}),
            _make_entry("wave3", 4.5, [], {}),  # +2.5 above minimum
        ]
        findings = detect_drift(entries, threshold=1.0)
        creep_findings = [f for f in findings if "CREEP" in f]
        self.assertEqual(len(creep_findings), 1)
        self.assertIn("wave1", creep_findings[0])  # minimum was at wave1

    def test_creep_not_flagged_when_small(self):
        entries = [
            _make_entry("wave1", 2.0, [], {}),
            _make_entry("wave2", 2.8, [], {}),  # +0.8, under threshold=1.0
        ]
        findings = detect_drift(entries, threshold=1.0)
        creep_findings = [f for f in findings if "CREEP" in f]
        self.assertEqual(creep_findings, [])

    def test_creep_threshold_respected(self):
        # With threshold=2.0 a creep of 1.5 should NOT trigger.
        entries = [
            _make_entry("wave1", 2.0, [], {}),
            _make_entry("wave2", 3.5, [], {}),
        ]
        findings = detect_drift(entries, threshold=2.0)
        creep_findings = [f for f in findings if "CREEP" in f]
        self.assertEqual(creep_findings, [])


class TestFirstOutOfBandWave(unittest.TestCase):
    """Unit test for the _first_out_of_band_wave helper."""

    def test_finds_correct_first_wave(self):
        entries = [
            {"wave": "w1", "frame_gated_on": {"FacA": 0.0}},
            {"wave": "w2", "frame_gated_on": {"FacA": 0.5}},
            {"wave": "w3", "frame_gated_on": {"FacA": 1.8}},
            {"wave": "w4", "frame_gated_on": {"FacA": 2.0}},
        ]
        result = _first_out_of_band_wave(entries, "FacA", 1.0)
        self.assertEqual(result, "w3")

    def test_returns_unknown_when_never_out(self):
        entries = [
            {"wave": "w1", "frame_gated_on": {"FacA": 0.5}},
        ]
        result = _first_out_of_band_wave(entries, "FacA", 1.0)
        self.assertEqual(result, "unknown")

    def test_missing_fac_in_entry_treated_as_zero(self):
        # An entry missing the faction key defaults to 0.0 (within band).
        entries = [
            {"wave": "w1", "frame_gated_on": {}},  # FacB absent -> 0.0
            {"wave": "w2", "frame_gated_on": {"FacB": 1.5}},
        ]
        result = _first_out_of_band_wave(entries, "FacB", 1.0)
        self.assertEqual(result, "w2")


class TestDetectDriftBothChecks(unittest.TestCase):
    """When both faction drift and headline creep are present, both are reported."""

    def test_both_findings_present(self):
        entries = [
            _make_entry("wave1", 1.5, ["FacA"], {"FacA": 0.0}),
            _make_entry("wave2", 4.5, [],        {"FacA": 2.0}),
        ]
        findings = detect_drift(entries, threshold=1.0)
        drift_found = any("DRIFT" in f for f in findings)
        creep_found = any("CREEP" in f for f in findings)
        self.assertTrue(drift_found, "Expected a DRIFT finding")
        self.assertTrue(creep_found, "Expected a CREEP finding")


if __name__ == "__main__":
    unittest.main()
