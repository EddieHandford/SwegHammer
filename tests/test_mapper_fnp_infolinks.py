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
those previously-dropped units.

DURA-AUDIT-D4 (docs/_DURA_AUDIT_D_DEATHGUARD.md divergence D4, 2026-07-03):
the #142 Plague Marines FNP-5 override this file used to pin as a
"no-regression" fixed point was itself a fabrication -- there is no
army-wide Feel No Pain in the 10th-edition Death Guard codex (Disgustingly
Resilient is the Virulent Vectorium 2-command-point stratagem, not an
army rule), confirmed by the durability fidelity audit and already
neutralised live by `code/bsdata/loader.py`'s SWEG_DG_PLAGUE_FNP_FAITHFUL
gate (default on since the iter-15 fabrication removal, well before this
2026-07-03 fix). `FnpNoRegressionTest` below now pins the CORRECT
fixed point (no Feel No Pain) instead.
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

    def test_wracks_have_no_fnp(self) -> None:
        # Wahapedia (https://wahapedia.ru/wh40k10ed/factions/drukhari/#Wracks)
        # confirms Wracks have no Feel No Pain ability. BSData v10.6.0 carried a
        # direct infoLink encoding Feel No Pain 5+ on the Wracks selectionEntry
        # but that encoding was removed in a later BSData main update. Current
        # Wahapedia Drukhari datasheet lists no Feel No Pain for Wracks; the
        # parser correctly returns the no-FNP sentinel (7). If an upstream codex
        # change re-adds FNP to Wracks, re-enable this assertion and add a
        # corrections entry citing the Wahapedia source.
        self._assert_fnp("aeldari_drukhari_wracks", 7)

    def test_wulfen_have_no_fnp(self) -> None:
        # Wahapedia (https://wahapedia.ru/wh40k10ed/factions/space-marines/Wulfen)
        # confirms Wulfen have no Feel No Pain ability. BSData v10.6.0 carried
        # Feel No Pain 6+ on the Wulfen selectionEntry (the "Death Frenzy"
        # ability); BSData main renamed the ability to "Savage Frenzy" and
        # removed the Feel No Pain infoLink. Current Wahapedia datasheet lists
        # no Feel No Pain for Wulfen; the parser correctly returns 7.
        self._assert_fnp("space_wolves_wulfen", 7)

    def test_repentia_have_fnp_5(self) -> None:
        self._assert_fnp("adepta_sororitas_repentia_squad", 5)

    def test_death_company_have_fnp_6(self) -> None:
        # Bonus coverage — Death Company are the canonical Blood Angels
        # FNP unit that broke previously.
        self._assert_fnp("blood_angels_death_company_marines", 6)


class FnpNoRegressionTest(unittest.TestCase):
    """Pre-existing fixes must continue to work."""

    def test_plague_marines_resolve_to_fnp_none_faithfully(self) -> None:
        # DURA-AUDIT-D4: the #142 override that used to patch Plague Marines
        # to FNP 5+ via data/overrides.json cited a Death Guard army-wide
        # Disgustingly Resilient rule that does not exist in 10th edition
        # (verified against BSData + Wahapedia: Plague Marines carry no
        # Feel No Pain ability at all). The override's fnp=5 was removed on
        # 2026-07-03 and `code/bsdata/loader.py`'s SWEG_DG_PLAGUE_FNP_FAITHFUL
        # gate (default on) already forced the faithful fnp=7 (none) before
        # that cleanup, so the live catalogue value is unchanged by the
        # override edit -- this test now pins the CORRECT fixed point.
        from code.units import UNIT_CATALOG

        for key in ("death_guard_plague_marines", "chaos_space_marines_plague_marines"):
            self.assertIn(key, UNIT_CATALOG, f"{key} missing from catalogue")
            self.assertEqual(
                UNIT_CATALOG[key].fnp,
                7,
                f"{key}: Plague Marines have no Feel No Pain per their 10e "
                f"datasheet (DURA-AUDIT-D4); expected fnp=7 (none)",
            )

    def test_no_regression_on_already_fixed_units(self) -> None:
        """Alias for the brief's named test — same assertion."""
        self.test_plague_marines_resolve_to_fnp_none_faithfully()


if __name__ == "__main__":
    unittest.main()
