"""Tests for the Aeldari Warhost archetype template.

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
  * wave-240 (docs/AELDARI_LIST_REALISM_SPEC.md) replaced the Wraith-heavy
    iter17 template with the Phoenix Lord + Aspect Warrior spine confirmed
    by 6 tournament lists (Salt City Grand Tournament IV 7-0, Nova Open
    2025 1st, Michigan Grand Tournament 2025 1st, and three more). Renamed
    archetype key from "Battle Host" to "Warhost" (the actual detachment
    name). Yncarne and Avatar of Khaine removed: zero appearances in any
    confirmed Warhost or Aspect Host list. New twelve-key template centres
    on Fuegan + Jain Zar + Lhykhis (Phoenix Lords) and Warp Spiders + Fire
    Dragons + Dark Reapers + Howling Banshees + Swooping Hawks (Aspect
    Warriors).

Reference: https://wahapedia.ru/wh40k10ed/factions/aeldari/
"""

import random
import unittest

from code.archetypes import ARCHETYPES, build_archetype_army, has_archetype
from code.units import UNIT_CATALOG


class AeldariWarhostTemplateTests(unittest.TestCase):
    def test_aeldari_has_warhost_archetype(self):
        """Aeldari must expose the Warhost archetype."""
        self.assertTrue(has_archetype("Aeldari"))
        self.assertIn("Warhost", ARCHETYPES["Aeldari"])

    def test_warhost_keys_resolve_in_catalogue(self):
        """Every key in the Warhost template must exist in UNIT_CATALOG
        and its faction must be 'Aeldari' (all units are Craftworlds)."""
        template = ARCHETYPES["Aeldari"]["Warhost"]
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

    def test_template_includes_phoenix_lords_and_aspect_warriors(self):
        """Template must reference Fuegan + Jain Zar + Lhykhis (Phoenix
        Lords) and Warp Spiders + Fire Dragons + Dark Reapers + Howling
        Banshees + Swooping Hawks (Aspect Warriors) — the wave-240
        list-realism reshape. The Yncarne and Avatar of Khaine are
        explicitly NOT in the template (zero competitive appearances in
        confirmed Warhost lists)."""
        template = ARCHETYPES["Aeldari"]["Warhost"]
        # Phoenix Lord trio
        self.assertIn("aeldari_craftworlds_fuegan", template)
        self.assertIn("aeldari_craftworlds_jain_zar", template)
        self.assertIn("aeldari_craftworlds_lhykhis", template)
        # Aspect Warriors
        self.assertIn("aeldari_craftworlds_warp_spiders", template)
        self.assertIn("aeldari_craftworlds_fire_dragons", template)
        self.assertIn("aeldari_craftworlds_dark_reapers", template)
        self.assertIn("aeldari_craftworlds_howling_banshees", template)
        self.assertIn("aeldari_craftworlds_swooping_hawks", template)
        # Transport
        self.assertIn("aeldari_craftworlds_wave_serpent", template)
        # wave-240 drops — Yncarne and Avatar must NOT be in the template
        self.assertNotIn("aeldari_ynnari_the_yncarne", template)
        self.assertNotIn("aeldari_craftworlds_avatar_of_khaine", template)

    def test_phoenix_lords_seed_in_90pct_of_trials_at_2000pt(self):
        """At 2000 pts, Fuegan + Jain Zar + Lhykhis (all count=3, ~120-135pt
        each) must each seed in >= 90% of 30 trials. The (-template_count,
        -squad_cost) sort places all three Phoenix Lords ahead of count=2
        entries; the 600pt seed slice (0.3 * 2000) accommodates all three
        (120 + 120 + 135 = 375pt) plus a Wave Serpent (125pt = 500pt total)
        before filling.

        Real competitive Aeldari lists are 2000pt by definition (GW tournament
        format) and the Phoenix Lords are the list's backbone."""
        fuegan_name = UNIT_CATALOG["aeldari_craftworlds_fuegan"].name
        jain_zar_name = UNIT_CATALOG["aeldari_craftworlds_jain_zar"].name
        lhykhis_name = UNIT_CATALOG["aeldari_craftworlds_lhykhis"].name

        trials = 30
        fuegan_hits = 0
        jain_zar_hits = 0
        lhykhis_hits = 0
        for seed in range(trials):
            rng = random.Random(seed)
            army = build_archetype_army(
                "A", "Aeldari", 2000.0, rng=rng,
                archetype_name="Warhost",
            )
            names = {u.profile.name for u in army.units}
            if fuegan_name in names:
                fuegan_hits += 1
            if jain_zar_name in names:
                jain_zar_hits += 1
            if lhykhis_name in names:
                lhykhis_hits += 1

        threshold = int(trials * 0.9)
        self.assertGreaterEqual(
            fuegan_hits, threshold,
            f"Fuegan seeded only {fuegan_hits}/{trials} times "
            f"(need >= {threshold})",
        )
        self.assertGreaterEqual(
            jain_zar_hits, threshold,
            f"Jain Zar seeded only {jain_zar_hits}/{trials} times "
            f"(need >= {threshold})",
        )
        self.assertGreaterEqual(
            lhykhis_hits, threshold,
            f"Lhykhis seeded only {lhykhis_hits}/{trials} times "
            f"(need >= {threshold})",
        )


if __name__ == "__main__":
    unittest.main()
