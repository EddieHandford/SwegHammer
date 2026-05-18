"""Tests for the Aeldari Battle Host (Warhost) archetype template.

History:
  * iter13 (879daf6) added Yvraine + Yncarne EPIC HERO pair to the template
    after evaluation showed the previous Farseer + Autarch only template
    under-evaluated Aeldari by ~4pt.
  * iter15 (c35790e) wired the Yvraine + Yncarne datasheet abilities into
    code/leaders.py (revive_destroyed=2, heal_per_round=2, plus_one_to_hit
    aura).
  * iter17 (this commit) trimmed the template after archetype eval showed
    Aeldari at sim 55.6% vs real 44.4% (+11.2pt over). Yvraine was dropped
    (her Word-of-the-Phoenix revival compounded with Yncarne's heal under
    the round-end pipeline, and she's an Ynnari-detachment centerpiece —
    real-meta Warhost lists field Avatar of Khaine + Farseer instead).
    Yncarne stays as the flagship MONSTER spine but with heal_per_round
    scaled from 2 to 1 (the codex per-kill heal was being modelled as a
    steady per-round buff). Avatar of Khaine added as the canonical real-
    meta Warhost MONSTER CHARACTER centerpiece.

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

    def test_template_includes_yncarne_and_avatar(self):
        """Template must reference Yncarne (Ynnari MONSTER spine) and
        Avatar of Khaine (canonical Warhost centerpiece). iter17 dropped
        Yvraine in favour of Avatar — the EPIC HERO pair is now Yncarne +
        Avatar rather than the iter13 Yvraine + Yncarne triumvirate."""
        template = ARCHETYPES["Aeldari"]["Battle Host"]
        self.assertIn("aeldari_ynnari_the_yncarne", template)
        self.assertIn("aeldari_craftworlds_avatar_of_khaine", template)
        # iter17 drop — Yvraine should NOT be templated; she's Ynnari-
        # detachment-flavour and over-stacked with Yncarne's heal.
        self.assertNotIn("aeldari_ynnari_yvraine", template)

    def test_yncarne_and_avatar_seed_in_90pct_of_trials_at_2000pt(self):
        """At 2000 pts both Yncarne (260pt) and Avatar (280pt) must seed in
        >=90% of 30 trials. The (-template_count, -squad_cost) anchor sort
        places both EH MONSTERs at the top of the seed walk (count=2 each),
        and the 600pt seed slice (0.3 * 2000) easily accommodates both
        (260 + 280 = 540pt total).

        The 1500pt seed slice (450pt) only fits ONE of the two, so the
        threshold here uses 2000pt; both pair fit in. Real-meta Aeldari
        Warhost lists are 2000pt by definition (GW tournament format)."""
        yncarne_name = UNIT_CATALOG["aeldari_ynnari_the_yncarne"].name
        avatar_name = UNIT_CATALOG["aeldari_craftworlds_avatar_of_khaine"].name

        trials = 30
        yncarne_hits = 0
        avatar_hits = 0
        for seed in range(trials):
            rng = random.Random(seed)
            army = build_archetype_army(
                "A", "Aeldari", 2000.0, rng=rng,
                archetype_name="Battle Host",
            )
            names = {u.profile.name for u in army.units}
            if yncarne_name in names:
                yncarne_hits += 1
            if avatar_name in names:
                avatar_hits += 1

        threshold = int(trials * 0.9)
        self.assertGreaterEqual(
            yncarne_hits, threshold,
            f"Yncarne seeded only {yncarne_hits}/{trials} times "
            f"(need >= {threshold})",
        )
        self.assertGreaterEqual(
            avatar_hits, threshold,
            f"Avatar of Khaine seeded only {avatar_hits}/{trials} times "
            f"(need >= {threshold})",
        )


if __name__ == "__main__":
    unittest.main()
