"""Tests for the Aeldari Battle Host (Ynnari) archetype template.

Added in iter13 — the May 2026 real-meta Aeldari Battle Host mandates the
Yvraine + Yncarne Warlord pairing (Ynnari triumvirate). Before this change
the template seeded only Farseer + Autarch with no EPIC HERO spine and the
calibration under-evaluated Aeldari by ~4pt. This test guards against
regression: at 1500pt with the anchor-first seed sort, both Yvraine and
Yncarne should land in well over 90% of trials.

Reference: https://wahapedia.ru/wh40k10ed/factions/aeldari/
"""

import random
import unittest

from code.archetypes import ARCHETYPES, build_archetype_army, has_archetype
from code.units import UNIT_CATALOG


class AeldariWarhostTemplateTests(unittest.TestCase):
    def test_aeldari_has_battle_host_archetype(self):
        """Aeldari must expose the Battle Host archetype."""
        self.assertTrue(has_archetype("Aeldari"))
        self.assertIn("Battle Host", ARCHETYPES["Aeldari"])

    def test_battle_host_keys_resolve_in_catalogue(self):
        """Every key in the Battle Host template must exist in UNIT_CATALOG
        and its faction must be 'Aeldari' or 'Ynnari' (the Ynnari sub-
        faction is legal in any Aeldari army per the 10e Aeldari index)."""
        template = ARCHETYPES["Aeldari"]["Battle Host"]
        allowed = {"Aeldari", "Ynnari"}
        missing = []
        misplaced = []
        for key in template:
            if key not in UNIT_CATALOG:
                missing.append(key)
                continue
            faction = UNIT_CATALOG[key].faction
            if faction not in allowed:
                misplaced.append(f"{key} -> faction={faction}")
        self.assertEqual(missing, [], f"Missing keys: {missing}")
        self.assertEqual(misplaced, [], f"Wrong faction: {misplaced}")

    def test_template_includes_ynnari_triumvirate(self):
        """Template must reference Yvraine and Yncarne — the real-meta
        Ynnari Warlord pair that defines the archetype."""
        template = ARCHETYPES["Aeldari"]["Battle Host"]
        self.assertIn("aeldari_ynnari_yvraine", template)
        self.assertIn("aeldari_ynnari_the_yncarne", template)

    def test_yvraine_and_yncarne_seed_in_90pct_of_trials_at_1500pt(self):
        """At 1500 pts both Yvraine and Yncarne must seed in >=90% of 30
        trials. The (-template_count, -squad_cost) anchor-first sort places
        Yncarne (260pt) and Yvraine (100pt) ahead of cheap chaff, so a
        450pt seed slice (0.3 * 1500) comfortably accommodates both."""
        yvraine_name = UNIT_CATALOG["aeldari_ynnari_yvraine"].name
        yncarne_name = UNIT_CATALOG["aeldari_ynnari_the_yncarne"].name

        trials = 30
        yvraine_hits = 0
        yncarne_hits = 0
        for seed in range(trials):
            rng = random.Random(seed)
            army = build_archetype_army(
                "A", "Aeldari", 1500.0, rng=rng,
                archetype_name="Battle Host",
            )
            names = {u.profile.name for u in army.units}
            if yvraine_name in names:
                yvraine_hits += 1
            if yncarne_name in names:
                yncarne_hits += 1

        threshold = int(trials * 0.9)
        self.assertGreaterEqual(
            yvraine_hits, threshold,
            f"Yvraine seeded only {yvraine_hits}/{trials} times "
            f"(need >= {threshold})",
        )
        self.assertGreaterEqual(
            yncarne_hits, threshold,
            f"Yncarne seeded only {yncarne_hits}/{trials} times "
            f"(need >= {threshold})",
        )


if __name__ == "__main__":
    unittest.main()
