"""Tests for ``code.compare_view``.

These tests pin the DataFrame schema and the NaN-tolerant behaviour around
missing phase files, so future re-runs of the equilibrium solvers can't
silently break the Streamlit Compare tab.
"""

from __future__ import annotations

import json
import unittest
from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory

from code.compare_view import (
    PHASE_FILES,
    build_comparison_df,
)


def _write_phase(path: Path, phase: int, units: dict) -> None:
    payload = {
        "_comment": "test fixture",
        "phase": phase,
        "method": "test",
        "anchor": "test_unit",
        "units": units,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class BuildComparisonDfTests(unittest.TestCase):
    def test_loads_real_data_and_has_expected_columns(self) -> None:
        df = build_comparison_df()
        # Must have at least one row from production fixtures.
        self.assertGreater(len(df), 0)

        expected_static = {
            "unit_key",
            "name",
            "faction",
            "role",
            "gw_points_per_model",
            "sweghammer_override",
        }
        self.assertTrue(expected_static.issubset(df.columns))

        for label in PHASE_FILES:
            self.assertIn(f"eq_{label}", df.columns)
            self.assertIn(f"mispricing_pct_{label}", df.columns)

    def test_sweghammer_override_flag_is_bool(self) -> None:
        df = build_comparison_df()
        # All True/False — never NaN, never str.
        self.assertTrue(df["sweghammer_override"].dtype == bool)
        # There IS at least one override in production overrides.json.
        self.assertTrue(df["sweghammer_override"].any())

    def test_handles_missing_phase_file_gracefully(self) -> None:
        with TemporaryDirectory() as tmp:
            data = Path(tmp)
            # Only one phase file present.
            _write_phase(
                data / "equilibrium_points.json",
                phase=1,
                units={
                    "test_a": {
                        "key": "test_a",
                        "name": "Test A",
                        "faction": "TestFac",
                        "gw_points_per_squad": 50.0,
                        "gw_points_per_model": 50.0,
                        "min_models": 1,
                        "equilibrium_points_per_model": 60.0,
                        "equilibrium_points_per_squad": 60.0,
                        "mispricing_pct": -16.7,
                        "valid_matchups": 100,
                        "role": "dual",
                    }
                },
            )
            (data / "overrides.json").write_text(
                json.dumps({"_comment": "", "units": {}}), encoding="utf-8"
            )

            phases = OrderedDict(
                [
                    ("phase1", "equilibrium_points.json"),
                    ("phase6", "equilibrium_points_phase6.json"),  # missing
                ]
            )
            df = build_comparison_df(phase_files=phases, data_dir=data)

            self.assertEqual(len(df), 1)
            row = df.iloc[0]
            self.assertEqual(row["unit_key"], "test_a")
            self.assertEqual(row["name"], "Test A")
            self.assertEqual(row["faction"], "TestFac")
            self.assertEqual(row["gw_points_per_model"], 50.0)
            self.assertEqual(row["eq_phase1"], 60.0)
            # Missing phase yields NaN/None.
            self.assertTrue(row["eq_phase6"] is None or row["eq_phase6"] != row["eq_phase6"])
            self.assertFalse(row["sweghammer_override"])

    def test_override_flag_set_when_key_present(self) -> None:
        with TemporaryDirectory() as tmp:
            data = Path(tmp)
            _write_phase(
                data / "equilibrium_points.json",
                phase=1,
                units={
                    "overridden_unit": {
                        "key": "overridden_unit",
                        "name": "Overridden",
                        "faction": "F",
                        "gw_points_per_model": 10.0,
                        "equilibrium_points_per_model": 12.0,
                        "mispricing_pct": -16.0,
                        "role": "shooty",
                    },
                    "vanilla_unit": {
                        "key": "vanilla_unit",
                        "name": "Vanilla",
                        "faction": "F",
                        "gw_points_per_model": 10.0,
                        "equilibrium_points_per_model": 9.0,
                        "mispricing_pct": 11.0,
                        "role": "shooty",
                    },
                },
            )
            (data / "overrides.json").write_text(
                json.dumps(
                    {
                        "_comment": "",
                        "units": {"overridden_unit": {"notes": "tuned"}},
                    }
                ),
                encoding="utf-8",
            )
            phases = OrderedDict([("phase1", "equilibrium_points.json")])
            df = build_comparison_df(phase_files=phases, data_dir=data)
            df_indexed = df.set_index("unit_key")
            self.assertTrue(df_indexed.loc["overridden_unit", "sweghammer_override"])
            self.assertFalse(df_indexed.loc["vanilla_unit", "sweghammer_override"])


if __name__ == "__main__":
    unittest.main()
