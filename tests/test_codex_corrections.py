"""Tests for the codex_corrections_<version>.json layer in
`code/bsdata/loader.py`.

The layer sits between BSData parsed.json and the SwegHammer
overrides.json, restoring canonical codex values for entries where
BSData has lagged behind an errata round. These tests pin the
behaviour so an accidental loader change can't silently revert
corrections to the BSData baked-in values.
"""
from __future__ import annotations

import unittest

from code.bsdata.loader import (
    DEFAULT_CODEX_VERSION,
    _codex_corrections_path,
    _load_codex_corrections,
    load_catalog,
)


class CodexCorrectionsLayerTests(unittest.TestCase):

    def test_default_codex_is_10e(self):
        self.assertEqual(DEFAULT_CODEX_VERSION, "10e")

    def test_10e_corrections_file_exists(self):
        self.assertTrue(_codex_corrections_path("10e").exists())

    def test_missing_codex_version_silently_returns_empty(self):
        # A nonexistent edition (e.g. "9e" or "11e" before 11e ships) is
        # a silent no-op, not an error. Load proceeds with overrides only.
        self.assertEqual(_load_codex_corrections("9e"), {})


class DrukhariSplinterCorrectionsTests(unittest.TestCase):
    """The Splinter weapons across Drukhari + Ynnari should land at
    ANTI-INFANTRY 4+ per the current Wahapedia codex (post-Sept-2024
    errata), regardless of the 3+ baked into BSData main."""

    def setUp(self):
        self.catalog = load_catalog()

    def _assert_anti_infantry(self, key: str, expected: int):
        entry = self.catalog[key]
        anti = dict(entry.anti_keywords or {})
        self.assertIn("INFANTRY", anti, f"{key}: missing INFANTRY anti-keyword")
        self.assertEqual(
            anti["INFANTRY"], expected,
            f"{key}: ANTI-INFANTRY expected {expected}+, got {anti['INFANTRY']}+",
        )

    def test_kabalite_warriors(self):
        self._assert_anti_infantry("aeldari_drukhari_kabalite_warriors", 4)

    def test_wyches(self):
        self._assert_anti_infantry("aeldari_drukhari_wyches", 4)

    def test_venom_primary_and_secondary(self):
        entry = self.catalog["aeldari_drukhari_venom"]
        prim = dict(entry.anti_keywords or {})
        sec = dict(entry.secondary_anti_keywords or {})
        self.assertEqual(prim.get("INFANTRY"), 4)
        self.assertEqual(sec.get("INFANTRY"), 4)

    def test_ynnari_mirror(self):
        # Ynnari pulls from the same Drukhari weapon profiles via
        # catalogueLink; the mirror entries must carry the corrected value.
        self._assert_anti_infantry(
            "aeldari_craftworlds_ynnari_kabalite_warriors", 4,
        )
        self._assert_anti_infantry("aeldari_craftworlds_ynnari_wyches", 4)


class DeathGuardPlagueCorrectionsTests(unittest.TestCase):

    def setUp(self):
        self.catalog = load_catalog()

    def test_plague_marines_anti_infantry_4(self):
        entry = self.catalog["death_guard_plague_marines"]
        self.assertEqual(dict(entry.anti_keywords or {}).get("INFANTRY"), 4)

    def test_blightlord_terminators_anti_infantry_4(self):
        entry = self.catalog["death_guard_blightlord_terminators"]
        self.assertEqual(dict(entry.anti_keywords or {}).get("INFANTRY"), 4)

    def test_csm_plague_marines_mirror(self):
        entry = self.catalog["chaos_space_marines_plague_marines"]
        self.assertEqual(dict(entry.anti_keywords or {}).get("INFANTRY"), 4)


class CorrectionsLayerOrderTests(unittest.TestCase):
    """Merge order: parsed -> codex_corrections -> overrides -> calibrated.
    Each later layer wins on overlapping fields."""

    def test_overrides_can_still_win_over_corrections(self):
        # Manually exercise the merge via _apply_override semantics.
        # Even though codex_corrections sets INFANTRY:4 for a key, if
        # overrides.json sets INFANTRY:5 for the same key, the override
        # should still take precedence (overrides land later in the merge).
        from code.bsdata.loader import _apply_override, _load_parsed
        base = _load_parsed().get("aeldari_drukhari_kabalite_warriors")
        self.assertIsNotNone(base)
        # corrections-level dict (would be applied first):
        corrections_layer = {"anti_keywords": {"INFANTRY": 4}}
        # imaginary overrides-level dict on top (would win):
        overrides_layer = {"anti_keywords": {"INFANTRY": 5}}
        merged = dict(corrections_layer)
        merged.update(overrides_layer)
        entry = _apply_override(base, merged, "aeldari_drukhari_kabalite_warriors")
        self.assertEqual(dict(entry.anti_keywords or {}).get("INFANTRY"), 5)


if __name__ == "__main__":
    unittest.main()
