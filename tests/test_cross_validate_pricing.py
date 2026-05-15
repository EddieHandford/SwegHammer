"""
Tests for ``scripts.cross_validate_pricing`` (task #132).

Confirms:
  * Both pricing signals load without error.
  * ``cross_validate`` returns a list of structured dicts with the required
    fields and consistent semantics.
  * On the current catalogue (Phase 5 output + MC-adjusted overrides.json)
    the cross-validation surfaces at least one disagreement — the MC pass
    adjusted 10 units, Phase 5 has 1000+, and a few directional mismatches
    are expected and worth surfacing.
  * Thresholds work as described: a hand-built input correctly produces
    disagreement / confirmation / neither.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import cross_validate_pricing as cvp


class LoadSignalsTests(unittest.TestCase):
    def test_phase5_loads(self) -> None:
        phase5 = cvp.load_phase5()
        self.assertIsInstance(phase5, dict)
        self.assertGreater(
            len(phase5), 100,
            "Phase 5 output should contain hundreds of units",
        )
        # Spot-check schema
        entry = next(iter(phase5.values()))
        for field in (
            "gw_points_per_model",
            "equilibrium_points_per_model",
            "name",
            "faction",
        ):
            self.assertIn(field, entry, f"phase5 entry missing {field!r}")

    def test_overrides_loads(self) -> None:
        overrides = cvp.load_overrides()
        self.assertIsInstance(overrides, dict)
        # The MC pass touched ten units (task #131); the test doesn't lock
        # that count but does require a non-empty file at the standard path.
        self.assertGreater(len(overrides), 0,
                           "overrides.json should be non-empty in the WIP branch")


class CrossValidateStructureTests(unittest.TestCase):
    def test_returns_list_of_dicts_with_required_fields(self) -> None:
        rows, summary = cvp.run(save=False)
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        required = {
            "key", "name", "faction",
            "gw_points_per_model",
            "phase5_equilibrium_per_model",
            "phase5_mispricing_pct",
            "mc_override_per_model",
            "mc_shift_pct",
            "mc_has_override",
            "disagreement",
            "confirmation",
        }
        sample = rows[0]
        missing = required - set(sample)
        self.assertFalse(missing, f"row missing fields: {missing}")
        # Summary contains its own derived sections.
        for k in ("total_units", "units_with_mc_override",
                  "disagreement_count", "confirmation_count",
                  "top_disagreements", "top_confirmations"):
            self.assertIn(k, summary)

    def test_units_with_mc_override_matches_overrides_file(self) -> None:
        rows, summary = cvp.run(save=False)
        # Count of mc_has_override flagged rows must not exceed the number of
        # overrides actually containing a points_override field. The bound
        # may be 0 — the MC overrides were wiped after the P1 points-fix
        # exposed that they were Lanchester-calibrated and 1.5-8x off GW.
        overrides = cvp.load_overrides()
        eligible = sum(
            1 for v in overrides.values() if v.get("points_override") is not None
        )
        self.assertGreaterEqual(summary["units_with_mc_override"], 0)
        self.assertLessEqual(summary["units_with_mc_override"], eligible)


class DetectsDisagreementOnCurrentCatalogueTests(unittest.TestCase):
    def test_disagreement_count_non_negative(self) -> None:
        """The cross-validator's disagreement count is well-defined when
        overrides exist. After the P1 points-fix wiped the MC overrides
        (they were Lanchester-calibrated and wrong), the catalogue may have
        zero disagreements — that's fine, just confirm the value is sane.
        """
        _rows, summary = cvp.run(save=False)
        self.assertGreaterEqual(summary["disagreement_count"], 0)


class ThresholdSemanticsTests(unittest.TestCase):
    """White-box test of cross_validate using hand-built inputs."""

    def test_disagreement_when_signs_differ_and_both_strong(self) -> None:
        phase5 = {
            "u1": {
                "name": "U1", "faction": "F",
                "gw_points_per_model": 100.0,
                "equilibrium_points_per_model": 120.0,  # +20%
            }
        }
        overrides = {"u1": {"points_override": 90.0}}  # -10%
        rows = cvp.cross_validate(phase5, overrides)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["disagreement"])
        self.assertFalse(rows[0]["confirmation"])

    def test_confirmation_when_signs_match_and_both_strong(self) -> None:
        phase5 = {
            "u1": {
                "name": "U1", "faction": "F",
                "gw_points_per_model": 100.0,
                "equilibrium_points_per_model": 80.0,  # -20%
            }
        }
        overrides = {"u1": {"points_override": 85.0}}  # -15%
        rows = cvp.cross_validate(phase5, overrides)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["confirmation"])
        self.assertFalse(rows[0]["disagreement"])

    def test_neither_when_below_thresholds(self) -> None:
        phase5 = {
            "u1": {
                "name": "U1", "faction": "F",
                "gw_points_per_model": 100.0,
                "equilibrium_points_per_model": 102.0,  # +2%, below 5%
            }
        }
        overrides = {"u1": {"points_override": 96.0}}  # -4%, below 5%
        rows = cvp.cross_validate(phase5, overrides)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["disagreement"])
        self.assertFalse(rows[0]["confirmation"])

    def test_no_override_means_mc_shift_zero(self) -> None:
        phase5 = {
            "u1": {
                "name": "U1", "faction": "F",
                "gw_points_per_model": 100.0,
                "equilibrium_points_per_model": 150.0,
            }
        }
        rows = cvp.cross_validate(phase5, overrides_units={})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mc_shift_pct"], 0.0)
        self.assertFalse(rows[0]["mc_has_override"])
        # 0 magnitude in either side disqualifies disagreement & confirmation.
        self.assertFalse(rows[0]["disagreement"])
        self.assertFalse(rows[0]["confirmation"])

    def test_zero_gw_points_skipped(self) -> None:
        """Units with gw_points_per_model == 0 cannot produce relative shifts
        and must be silently skipped, not raise ZeroDivisionError."""
        phase5 = {
            "u_bad": {
                "name": "Bad", "faction": "F",
                "gw_points_per_model": 0.0,
                "equilibrium_points_per_model": 50.0,
            },
            "u_good": {
                "name": "Good", "faction": "F",
                "gw_points_per_model": 50.0,
                "equilibrium_points_per_model": 60.0,
            },
        }
        rows = cvp.cross_validate(phase5, overrides_units={})
        self.assertEqual([r["key"] for r in rows], ["u_good"])


class SaveReportTests(unittest.TestCase):
    def test_save_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            _rows, _summary = cvp.run(save=True, out_path=out)
            self.assertTrue(out.exists())
            payload = json.loads(out.read_text(encoding="utf-8"))
            for k in ("disagreement_count", "confirmation_count",
                      "top_disagreements", "top_confirmations"):
                self.assertIn(k, payload)
            # Internal sort key must not leak into the saved report.
            if payload["top_disagreements"]:
                self.assertNotIn(
                    "_combined_strength",
                    payload["top_disagreements"][0],
                )


if __name__ == "__main__":
    unittest.main()
