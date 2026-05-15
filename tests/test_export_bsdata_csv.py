"""Tests for `scripts.export_bsdata_csv`.

Three contract checks:
  1. The header row contains the expected key columns.
  2. The data row count equals len(UNIT_CATALOG).
  3. A known unit (Intercessor Squad) has the expected per-field values.
"""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from code.units import UNIT_CATALOG
from scripts.export_bsdata_csv import COLUMNS, export_csv, row_for


_INTERCESSOR_KEY = "space_marines_intercessor_squad"


class ExportBsdataCsvTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.out_path = Path(self._tmpdir.name) / "units.csv"
        self.n_written = export_csv(self.out_path)
        with self.out_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            self.header = next(reader)
            self.rows = list(reader)

    def test_csv_has_expected_columns(self) -> None:
        """Header row must contain the spec's required columns."""
        # Exact match to the export contract …
        self.assertEqual(self.header, COLUMNS)
        # … and a sample of must-have columns the spec calls out explicitly.
        required = [
            "key", "name", "faction",
            "health", "toughness", "save", "invuln_save", "fnp",
            "move", "oc", "leadership",
            "attacks", "hit_probability", "strength", "ap",
            "weapon_damage_per_shot", "range_inches",
            "melee_attacks", "melee_hit_probability",
            "melee_strength", "melee_ap", "melee_damage_per_shot",
            "assault", "heavy", "pistol", "rapid_fire", "twin_linked",
            "ignores_cover", "torrent", "lethal_hits", "lance", "melta",
            "sustained_hits", "devastating_wounds", "precision", "blast",
            "indirect_fire", "hazardous", "one_shot",
            "stealth", "deep_strike", "scout_distance", "infiltrators",
            "sticky_objective", "lone_operative", "fly",
            "deadly_demise", "points_cost",
            "anti_keywords", "unit_keywords",
        ]
        for col in required:
            self.assertIn(col, self.header, f"missing column: {col}")

    def test_csv_row_count_matches_catalog(self) -> None:
        """Every catalogue entry produces exactly one data row."""
        self.assertEqual(self.n_written, len(UNIT_CATALOG))
        self.assertEqual(len(self.rows), len(UNIT_CATALOG))

    def test_known_unit_has_correct_stats(self) -> None:
        """Spot-check Intercessor Squad: name, faction, save, and the
        derived points_cost match the in-memory profile."""
        self.assertIn(
            _INTERCESSOR_KEY, UNIT_CATALOG,
            "Intercessor Squad missing from catalogue — pick another key",
        )
        profile = UNIT_CATALOG[_INTERCESSOR_KEY]
        # Pull the row from the rendered CSV by `key` column index.
        key_idx = self.header.index("key")
        match = [r for r in self.rows if r[key_idx] == _INTERCESSOR_KEY]
        self.assertEqual(len(match), 1)
        row = dict(zip(self.header, match[0]))
        self.assertEqual(row["name"], profile.name)
        self.assertEqual(row["faction"], profile.faction)
        self.assertEqual(int(row["save"]), profile.save)
        self.assertEqual(int(row["toughness"]), profile.toughness)
        self.assertAlmostEqual(float(row["health"]), profile.health)
        # points_cost is derived from points_for(...) at access time; the
        # CSV stores it stringified, so float-compare with the same source.
        self.assertAlmostEqual(
            float(row["points_cost"]), profile.points_cost, places=1,
        )

    def test_row_for_returns_column_width(self) -> None:
        """row_for must produce exactly len(COLUMNS) cells (regression guard)."""
        key, profile = next(iter(UNIT_CATALOG.items()))
        row = row_for(key, profile)
        self.assertEqual(len(row), len(COLUMNS))


if __name__ == "__main__":
    unittest.main()
