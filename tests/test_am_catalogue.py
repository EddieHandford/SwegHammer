"""Tests for the Astra Militarum BATTLELINE infantry catalogue.

Regression for the iter11 mapper-depth bug: Cadian Shock Troops, Catachan
Jungle Fighters, and Death Korps of Krieg are 10e BATTLELINE units, but the
mapper's `_walk(..., max_depth=3)` was too shallow to traverse AM's
``upgrade``-wrapped squad shape (unit → Unit Composition group → upgrade
selectionEntry → optional inner group → model → weapon entryLink). All three
units fell out of UNIT_CATALOG with skip_reason = "no ranged OR melee
weapons resolvable in tree" (Cadian / Catachan) or "no unit profile" (Krieg
— even deeper, nested-group layout). The fix bumps ``max_depth`` to 5.

Wahapedia datasheets:
  - https://wahapedia.ru/wh40k10ed/factions/astra-militarum/cadian-shock-troops
  - https://wahapedia.ru/wh40k10ed/factions/astra-militarum/catachan-jungle-fighters
  - https://wahapedia.ru/wh40k10ed/factions/astra-militarum/death-korps-of-krieg
"""

import random
import unittest

from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG


class AMBattlelineCatalogueTest(unittest.TestCase):
    """The three AM BATTLELINE infantry datasheets must reach the catalogue."""

    REQUIRED_KEYS = (
        "astra_militarum_cadian_shock_troops",
        "astra_militarum_catachan_jungle_fighters",
        "astra_militarum_death_korps_of_krieg",
    )

    def test_cadian_shock_troops_present(self):
        self.assertIn(
            "astra_militarum_cadian_shock_troops", UNIT_CATALOG,
            "Cadian Shock Troops missing from UNIT_CATALOG — mapper depth regression?",
        )
        u = UNIT_CATALOG["astra_militarum_cadian_shock_troops"]
        # Wahapedia: M 6", T 3, Sv 5+, OC 2.
        self.assertEqual(u.move, 6.0, f"Cadian M expected 6\", got {u.move}")
        self.assertEqual(u.toughness, 3, f"Cadian T expected 3, got {u.toughness}")
        self.assertEqual(u.save, 5, f"Cadian Sv expected 5+, got {u.save}+")
        self.assertEqual(u.oc, 2, f"Cadian OC expected 2, got {u.oc}")
        self.assertIn(
            "BATTLELINE", u.unit_keywords or (),
            f"Cadian BATTLELINE keyword missing — got {u.unit_keywords}",
        )

    def test_all_three_am_battleline_units_present(self):
        for key in self.REQUIRED_KEYS:
            with self.subTest(unit=key):
                self.assertIn(
                    key, UNIT_CATALOG,
                    f"{key} missing from UNIT_CATALOG — mapper failed to resolve "
                    "the upgrade-wrapped squad shape (depth>3 needed)",
                )
                u = UNIT_CATALOG[key]
                self.assertIn(
                    "BATTLELINE", u.unit_keywords or (),
                    f"{key} should carry BATTLELINE keyword, got {u.unit_keywords}",
                )
                self.assertEqual(u.faction, "Astra Militarum")

    def test_am_catalogue_has_battleline(self):
        """The AM faction must have at least 3 BATTLELINE units in the
        catalogue — Cadian, Catachan, Krieg. Before iter11 there were zero,
        making any AM list-building broken."""
        am_battleline = [
            k for k, u in UNIT_CATALOG.items()
            if u.faction == "Astra Militarum"
            and "BATTLELINE" in (u.unit_keywords or ())
        ]
        self.assertGreaterEqual(
            len(am_battleline), 3,
            f"AM should have >=3 BATTLELINE units, got {len(am_battleline)}: "
            f"{am_battleline}",
        )

    def test_build_faction_random_army_am_non_empty(self):
        """The AM army builder must return a non-empty army at 1000pts now
        that the mapper surfaces the BATTLELINE pool."""
        rng = random.Random(0)
        # build_faction_random_army uses the module-level RNG; seed it.
        random.seed(0)
        army = build_faction_random_army("AM-Test", "Astra Militarum", 1000)
        self.assertGreater(
            len(army.units), 0,
            "AM random army should be non-empty at 1000pts",
        )


if __name__ == "__main__":
    unittest.main()
