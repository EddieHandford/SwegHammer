"""Tests for Thousand Sons invulnerable-save overrides (task #171).

BSData WH40k 10e does not encode Invulnerable-Save infoLinks on Thousand
Sons datasheets, so every TSON unit ships from the mapper with
``invuln_save=7`` (no invuln). The canonical 10e datasheets on Wahapedia
list specific invulnerable saves for the army's HQs, elites, and
monsters. This test pins the override values in ``data/overrides.json``
so a regression (e.g. mapper rerun clobbering them) is caught loudly.

Source for every value: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
"""

from __future__ import annotations

import unittest

from code.units import UNIT_CATALOG


# (key, expected ++ save). Keys that don't currently exist in the
# catalogue (e.g. Ahriman on Disc has no BSData datasheet at this
# tag) are intentionally absent.
EXPECTED_INVULNS = [
    ("thousand_sons_magnus_the_red", 4),
    ("thousand_sons_ahriman", 4),
    ("thousand_sons_infernal_master", 5),
    ("thousand_sons_exalted_sorcerer", 5),
    ("thousand_sons_exalted_sorcerer_on_disc_of_tzeentch", 5),
    ("thousand_sons_daemon_prince_of_tzeentch", 4),
    ("thousand_sons_daemon_prince_of_tzeentch_with_wings", 4),
    ("thousand_sons_rubric_marines", 5),
    ("thousand_sons_scarab_occult_terminators", 4),
    ("thousand_sons_tzaangor_shaman", 5),
    ("thousand_sons_kairos_fateweaver", 4),
    ("thousand_sons_lord_of_change", 4),
]


class ThousandSonsInvulnSavesTest(unittest.TestCase):
    def test_canonical_tson_units_have_expected_invuln(self) -> None:
        for key, expected in EXPECTED_INVULNS:
            with self.subTest(unit=key):
                self.assertIn(
                    key,
                    UNIT_CATALOG,
                    f"{key} missing from catalogue — override target gone",
                )
                got = UNIT_CATALOG[key].invuln_save
                self.assertEqual(
                    got,
                    expected,
                    f"{key} invuln_save={got}, expected {expected}++ per Wahapedia",
                )


if __name__ == "__main__":
    unittest.main()
