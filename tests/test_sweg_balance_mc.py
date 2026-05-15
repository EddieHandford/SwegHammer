"""
Tests for scripts.sweg_balance_mc (task #131 C1 retry).

Confirms:
  * The Intercessor anchor is never modified.
  * No single unit moves more than 25% in a single pass (the hard cap).
  * Updates apply ONLY to the four targeted factions
    (T'au Empire, Aeldari, Necrons, Thousand Sons).
  * Applied points_override values persist in data/overrides.json after
    running the script.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import sweg_balance_mc as sbm

REPO_ROOT = Path(__file__).resolve().parents[1]


class AnchorPreservedTests(unittest.TestCase):
    def test_intercessor_anchor_not_targeted(self) -> None:
        """The anchor unit must not appear in any faction's adjustment list."""
        for faction, (_direction, keys) in sbm.FACTION_ADJUSTMENTS.items():
            self.assertNotIn(sbm.ANCHOR_UNIT_KEY, keys,
                             f"Anchor unit appears in {faction} target list")

    def test_apply_skips_anchor_even_if_listed(self) -> None:
        """If the anchor accidentally appears in updates, apply_updates skips it."""
        fake = [
            {
                "faction": "Adeptus Astartes", "key": sbm.ANCHOR_UNIT_KEY,
                "direction": "up",
                "starting_points": 16.0, "proposed_points": 17.6,
                "capped_points": 17.6, "applied_points": 17.6,
                "skipped": False,
            },
        ]
        # Use a temp overrides file
        tmpdir = Path(tempfile.mkdtemp())
        try:
            tmp_overrides = tmpdir / "overrides.json"
            tmp_overrides.write_text('{"units": {}}', encoding="utf-8")
            with mock.patch.object(sbm, "OVERRIDES_PATH", tmp_overrides):
                doc = sbm.apply_updates_to_overrides(fake)
            self.assertNotIn(sbm.ANCHOR_UNIT_KEY, doc.get("units", {}))
        finally:
            shutil.rmtree(tmpdir)


class ShiftCapTests(unittest.TestCase):
    def test_no_unit_moves_more_than_25_percent_per_pass(self) -> None:
        """build_updates() must clamp every proposed shift to <= 25%."""
        updates = sbm.build_updates()
        for upd in updates:
            if upd.get("skipped"):
                continue
            start = float(upd["starting_points"])
            applied = float(upd["applied_points"])
            ratio = applied / start if start else 1.0
            self.assertGreaterEqual(
                ratio, 1.0 - sbm.MAX_SHIFT_FRACTION - 1e-9,
                f"{upd['key']} dropped below -25%: {ratio:.3f}")
            self.assertLessEqual(
                ratio, 1.0 + sbm.MAX_SHIFT_FRACTION + 1e-9,
                f"{upd['key']} rose above +25%: {ratio:.3f}")

    def test_default_pass_shift_is_within_cap(self) -> None:
        self.assertLessEqual(sbm.PASS_SHIFT_FRACTION, sbm.MAX_SHIFT_FRACTION)


class FactionScopeTests(unittest.TestCase):
    TARGET_FACTIONS = {"T'au Empire", "Aeldari", "Necrons", "Thousand Sons"}

    def test_only_targeted_factions_appear_in_adjustments(self) -> None:
        self.assertEqual(set(sbm.FACTION_ADJUSTMENTS), self.TARGET_FACTIONS)

    def test_every_targeted_unit_belongs_to_its_faction(self) -> None:
        """Each unit key listed under a faction must actually be that faction
        in the loaded catalogue — defends against typos that would silently
        leak adjustments into an unrelated faction."""
        from code.units import UNIT_CATALOG
        for faction, (_direction, keys) in sbm.FACTION_ADJUSTMENTS.items():
            for key in keys:
                profile = UNIT_CATALOG.get(key)
                self.assertIsNotNone(
                    profile, f"{key} missing from UNIT_CATALOG")
                self.assertEqual(
                    profile.faction, faction,
                    f"{key} faction={profile.faction!r} != target {faction!r}")


class PersistenceTests(unittest.TestCase):
    def test_updates_persist_to_overrides_file(self) -> None:
        """Running build_updates -> apply -> write produces a readable file
        whose ``points_override`` values match the applied points."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            tmp_overrides = tmpdir / "overrides.json"
            tmp_overrides.write_text('{"units": {}}', encoding="utf-8")
            with mock.patch.object(sbm, "OVERRIDES_PATH", tmp_overrides):
                updates = sbm.build_updates()
                doc = sbm.apply_updates_to_overrides(updates)
                sbm.write_overrides(doc)
                # Round-trip
                reloaded = json.loads(tmp_overrides.read_text(encoding="utf-8"))
            units_map = reloaded.get("units", {})
            applied_keys = [u["key"] for u in updates if not u.get("skipped")]
            self.assertGreater(len(applied_keys), 0,
                               "build_updates produced no applicable updates")
            for upd in updates:
                if upd.get("skipped"):
                    continue
                key = upd["key"]
                self.assertIn(key, units_map,
                              f"{key} not written to overrides")
                self.assertAlmostEqual(
                    units_map[key]["points_override"],
                    float(upd["applied_points"]),
                    places=2,
                )
        finally:
            shutil.rmtree(tmpdir)

    def test_existing_override_fields_preserved(self) -> None:
        """Pre-existing override fields (e.g. invuln_save on Wraithguard)
        must survive the points_override merge."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            tmp_overrides = tmpdir / "overrides.json"
            seed = {"units": {
                "aeldari_aeldari_library_wraithguard": {
                    "invuln_save": 4,
                    "notes": "preserve me",
                }
            }}
            tmp_overrides.write_text(json.dumps(seed), encoding="utf-8")
            with mock.patch.object(sbm, "OVERRIDES_PATH", tmp_overrides):
                updates = sbm.build_updates()
                doc = sbm.apply_updates_to_overrides(updates)
                sbm.write_overrides(doc)
                reloaded = json.loads(tmp_overrides.read_text(encoding="utf-8"))
            entry = reloaded["units"]["aeldari_aeldari_library_wraithguard"]
            self.assertEqual(entry["invuln_save"], 4)
            self.assertIn("points_override", entry)
            # Notes preserved (with tag appended)
            self.assertIn("preserve me", entry["notes"])
        finally:
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()
