"""Tests for datasheet-level FNP infoLink extraction (#151).

The 10e BSData encodes a unit's Feel No Pain threshold on the unit's
selectionEntry as:

    <infoLink name="Feel No Pain" type="rule" targetId="...">
      <modifiers>
        <modifier type="append" field="name" value="5+"/>
      </modifiers>
    </infoLink>

The linked "Feel No Pain" rule body itself just says
"Feel No Pain x+" with no number, so the only place to recover the
per-unit threshold is the modifier-append value. ~107 entries across
27 catalogue files use this shape, including Poxwalkers, Wracks,
Wulfen, Repentia, Death Company.

These tests assert that the parsed.json produced by the mapper
exposes the correct FNP threshold for a representative sample of
those previously-dropped units, and that the Plague Marines override
from #142 still resolves to FNP 5 once the loader has merged
overrides on top of parsed.json.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from code.bsdata.mapper import PARSED_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _parsed_units() -> dict:
    """Load parsed.json, regenerating it on demand if missing."""
    if not PARSED_PATH.exists():
        # Build it; the mapper writes to PARSED_PATH.
        from code.bsdata.mapper import main as mapper_main

        mapper_main()
    with PARSED_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {u["key"]: u for u in data["units"]}


class FnpInfoLinkExtractionTest(unittest.TestCase):
    """The five canonical units called out in #151."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.units = _parsed_units()

    def _assert_fnp(self, key: str, expected: int) -> None:
        self.assertIn(
            key,
            self.units,
            f"unit key {key!r} missing from parsed.json — was the mapper run?",
        )
        actual = self.units[key].get("fnp")
        self.assertEqual(
            actual,
            expected,
            f"{key}: expected fnp={expected}, got fnp={actual} "
            "(datasheet-level FNP infoLink modifier-append not honoured)",
        )

    def test_poxwalkers_have_fnp_5(self) -> None:
        self._assert_fnp("death_guard_poxwalkers", 5)

    def test_wracks_have_fnp_5(self) -> None:
        # BSData defines Wracks in the Aeldari Library catalogue, but the
        # parser credits the Drukhari importing codex (see parser.py
        # iter_unit_entries). Source: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Wracks
        self._assert_fnp("aeldari_drukhari_wracks", 5)

    def test_wulfen_have_fnp_5(self) -> None:
        # BSData main upgrades Wulfen FNP 6+ → FNP 5+ per post-v10.6.0
        # dataslate (Curse of the Wulfen). v10.6.0 still had 6+.
        self._assert_fnp("space_wolves_wulfen", 5)

    def test_repentia_have_fnp_5(self) -> None:
        self._assert_fnp("adepta_sororitas_repentia_squad", 5)

    def test_death_company_have_fnp_6(self) -> None:
        # Bonus coverage — Death Company are the canonical Blood Angels
        # FNP unit that broke previously.
        self._assert_fnp("blood_angels_death_company_marines", 6)


class FnpNoRegressionTest(unittest.TestCase):
    """Pre-existing fixes must continue to work."""

    def test_plague_marines_resolve_to_fnp_5_via_overrides(self) -> None:
        # Plague Marines' FNP isn't carried by a unit-direct infoLink in
        # BSData — #142 patched them via data/overrides.json. After loader
        # merges parsed.json + overrides, the catalogue must still see 5+.
        from code.units import UNIT_CATALOG

        for key in ("death_guard_plague_marines", "chaos_space_marines_plague_marines"):
            self.assertIn(key, UNIT_CATALOG, f"{key} missing from catalogue")
            self.assertEqual(
                UNIT_CATALOG[key].fnp,
                5,
                f"{key}: Plague Marines override (#142) regressed; expected fnp=5",
            )

    def test_no_regression_on_already_fixed_units(self) -> None:
        """Alias for the brief's named test — same assertion."""
        self.test_plague_marines_resolve_to_fnp_5_via_overrides()


if __name__ == "__main__":
    unittest.main()
