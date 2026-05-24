"""Tests for the SwegHammer v1 prices loader and applier."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code.sweg_points import (
    SWEG_POINTS_V1_PATH,
    apply_to_catalog,
    load_sweg_overrides,
    reset_catalog_overrides,
)
from code.units import UNIT_CATALOG, UnitProfile


class LoadSwegOverridesTest(unittest.TestCase):

    def test_loads_default_dataset(self):
        """The committed v1 dataset must load cleanly."""
        self.assertTrue(SWEG_POINTS_V1_PATH.exists(),
                        f"Expected {SWEG_POINTS_V1_PATH} on disk; rebake.")
        overrides = load_sweg_overrides()
        self.assertGreater(len(overrides), 1000,
                           "v1 dataset should price > 1000 units; got "
                           f"{len(overrides)}.")
        # Every value should be a positive float.
        for key, price in overrides.items():
            self.assertIsInstance(price, float)
            self.assertGreater(price, 0,
                               f"Non-positive price for {key!r}: {price}")

    def test_raises_when_dataset_missing(self):
        with self.assertRaises(FileNotFoundError):
            load_sweg_overrides(Path("/tmp/this_file_does_not_exist.json"))

    def test_raises_when_prices_block_missing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"version": "1.0.0"}, f)
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                load_sweg_overrides(path)
        finally:
            path.unlink()

    def test_raises_when_sweg_pts_field_missing(self):
        bad_payload = {"version": "1.0.0", "prices": {
            "fake_key": {"name": "Fake", "faction": "Test"},
        }}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bad_payload, f)
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                load_sweg_overrides(path)
        finally:
            path.unlink()


class ApplyToCatalogTest(unittest.TestCase):

    def test_applies_to_real_catalog(self):
        """Default dataset applies cleanly to UNIT_CATALOG."""
        overrides = load_sweg_overrides()
        touched = apply_to_catalog(UNIT_CATALOG, overrides)
        try:
            self.assertGreater(touched, 1000,
                               f"Expected > 1000 profiles touched; got {touched}.")
            # Spot-check: at least one unit's price now matches the override.
            sample_key = next(iter(overrides))
            self.assertAlmostEqual(
                UNIT_CATALOG[sample_key].points_override,
                overrides[sample_key],
                places=2,
            )
        finally:
            reset_catalog_overrides(UNIT_CATALOG)

    def test_strict_mode_raises_on_unknown_key(self):
        """Per CLAUDE.md rule 13 — silent fallback is banned."""
        overrides = {"this_key_does_not_exist_anywhere": 99.0}
        with self.assertRaises(KeyError):
            apply_to_catalog(UNIT_CATALOG, overrides, strict=True)

    def test_non_strict_mode_skips_unknown_keys(self):
        overrides = {"this_key_does_not_exist_anywhere": 99.0}
        # Should not raise; should touch 0 profiles.
        touched = apply_to_catalog(UNIT_CATALOG, overrides, strict=False)
        self.assertEqual(touched, 0)

    def test_reset_clears_overrides(self):
        """reset_catalog_overrides restores GW prices."""
        overrides = load_sweg_overrides()
        apply_to_catalog(UNIT_CATALOG, overrides)
        applied = sum(1 for u in UNIT_CATALOG.values()
                      if u.points_override and u.points_override > 0)
        self.assertGreater(applied, 0)
        cleared = reset_catalog_overrides(UNIT_CATALOG)
        self.assertEqual(cleared, applied)
        # After reset, no overrides remain.
        remaining = sum(1 for u in UNIT_CATALOG.values()
                        if u.points_override and u.points_override > 0)
        self.assertEqual(remaining, 0)


class IntegrationTest(unittest.TestCase):

    def test_apply_changes_points_cost(self):
        """points_cost should return the override after apply, not GW."""
        overrides = load_sweg_overrides()
        # Pick a unit whose Sweg price differs from GW.
        target_key = None
        for key, price in overrides.items():
            profile = UNIT_CATALOG.get(key)
            if profile is None or not profile.points_per_squad:
                continue
            gw_pm = profile.points_per_squad / max(1, profile.min_models)
            if abs(price - gw_pm) > 1.0:
                target_key = key
                break
        self.assertIsNotNone(target_key,
                             "Could not find a unit where Sweg != GW; "
                             "either the dataset is empty or rounding "
                             "is too aggressive.")
        try:
            apply_to_catalog(UNIT_CATALOG, overrides)
            self.assertAlmostEqual(
                UNIT_CATALOG[target_key].points_cost,
                overrides[target_key],
                places=2,
            )
        finally:
            reset_catalog_overrides(UNIT_CATALOG)


if __name__ == "__main__":
    unittest.main()
