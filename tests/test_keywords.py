"""Tests for the weapon-keyword parser and range-dependent keyword effects."""

from __future__ import annotations

import random
import unittest

from code.bsdata.mapper import _torrent_from_name, parse_weapon_keywords
from code.units import Unit, UnitProfile


class ParseWeaponKeywordsTests(unittest.TestCase):

    def test_rapid_fire(self):
        out = parse_weapon_keywords("Rapid Fire 2")
        self.assertEqual(out.get("rapid_fire"), 2)

    def test_melta(self):
        out = parse_weapon_keywords("Melta 4")
        self.assertEqual(out.get("melta"), 4)

    def test_ignores_cover(self):
        out = parse_weapon_keywords("Ignores Cover")
        self.assertTrue(out.get("ignores_cover"))

    def test_anti_uppercase(self):
        out = parse_weapon_keywords("Anti-INFANTRY 4+")
        self.assertEqual(out.get("anti_keywords"), {"INFANTRY": 4})

    def test_anti_case_forgiving(self):
        # Lowercase variant must yield the same normalized result.
        out = parse_weapon_keywords("anti-infantry 4+")
        self.assertEqual(out.get("anti_keywords"), {"INFANTRY": 4})

    def test_heavy(self):
        self.assertTrue(parse_weapon_keywords("Heavy").get("heavy"))

    def test_assault(self):
        self.assertTrue(parse_weapon_keywords("Assault").get("assault"))

    def test_torrent(self):
        self.assertTrue(parse_weapon_keywords("Torrent").get("torrent"))

    def test_hazardous(self):
        self.assertTrue(parse_weapon_keywords("Hazardous").get("hazardous"))

    def test_blast(self):
        self.assertTrue(parse_weapon_keywords("Blast").get("blast"))

    def test_lance(self):
        self.assertTrue(parse_weapon_keywords("Lance").get("lance"))

    def test_precision(self):
        self.assertTrue(parse_weapon_keywords("Precision").get("precision"))

    def test_pistol(self):
        self.assertTrue(parse_weapon_keywords("Pistol").get("pistol"))

    def test_indirect_fire(self):
        self.assertTrue(parse_weapon_keywords("Indirect Fire").get("indirect_fire"))

    def test_one_shot_with_and_without_hyphen(self):
        # Wahapedia variously prints "One Shot" and "One-Shot"; both must parse.
        self.assertTrue(parse_weapon_keywords("One Shot").get("one_shot"))
        self.assertTrue(parse_weapon_keywords("One-Shot").get("one_shot"))

    def test_stealth(self):
        # Phase H: Stealth is parsed by the same regex sweep. Although the
        # canonical source is a unit-level infoLink in BSData, the parser
        # also accepts it as a bareword keyword on a weapon line.
        self.assertTrue(parse_weapon_keywords("Stealth").get("stealth"))

    def test_combo(self):
        # A mix of keywords on a single line must all parse out.
        out = parse_weapon_keywords("Rapid Fire 1, Anti-VEHICLE 2+, Heavy")
        self.assertEqual(out.get("rapid_fire"), 1)
        self.assertEqual(out.get("anti_keywords"), {"VEHICLE": 2})
        self.assertTrue(out.get("heavy"))


class TorrentNameDetectionTests(unittest.TestCase):
    """BSData seldom tags flamer-family weapons with a literal "Torrent"
    keyword token — the rule is implied by the weapon noun. The mapper's
    `_torrent_from_name` helper fills the gap."""

    def test_burna_implies_torrent(self):
        self.assertTrue(_torrent_from_name("Burna"))
        self.assertTrue(_torrent_from_name("Burna-Bommer Skorcha"))

    def test_inferno_cannon_implies_torrent(self):
        self.assertTrue(_torrent_from_name("Inferno Cannon"))

    def test_heavy_flamer_implies_torrent(self):
        self.assertTrue(_torrent_from_name("Heavy Flamer"))

    def test_flamestorm_implies_torrent(self):
        self.assertTrue(_torrent_from_name("Flamestorm Cannon"))

    def test_incinerator_implies_torrent(self):
        self.assertTrue(_torrent_from_name("Incinerator"))

    def test_bolter_does_not_imply_torrent(self):
        self.assertFalse(_torrent_from_name("Bolter"))
        self.assertFalse(_torrent_from_name("Boltgun"))
        self.assertFalse(_torrent_from_name("Plasma Pistol"))

    def test_empty_name_does_not_imply_torrent(self):
        self.assertFalse(_torrent_from_name(""))
        self.assertFalse(_torrent_from_name(None or ""))

    def test_case_insensitive(self):
        # Detection must be robust to BSData's mixed casing.
        self.assertTrue(_torrent_from_name("FLAMER"))
        self.assertTrue(_torrent_from_name("inferno cannon"))


class RapidFireBehaviourTests(unittest.TestCase):
    """A synthetic UnitProfile at half range should fire MORE attacks."""

    def _attacker(self):
        # Rapid Fire 2 = +2 attacks at half range. Base attacks=1 -> 3 at half.
        return UnitProfile(
            name="RFGun", health=1, damage=0,
            hit_probability=1.0, attacks=1, weapon_damage_per_shot=1.0,
            strength=10,                # auto-wound vs T4 (5/6)
            rapid_fire=2, range_inches=24,
        )

    def _target(self):
        # No save -> every successful wound becomes damage. Hi HP so we don't
        # run out of HP before all shots resolve.
        return UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
        )

    def test_rapid_fire_more_attacks_at_half_range(self):
        # Use a deterministic seed and many "shooters" to average the dice.
        n_trials = 200
        attacker_p = self._attacker()
        target_p = self._target()

        random.seed(7)
        half_range_total = 0.0
        for _ in range(n_trials):
            target = Unit(target_p)
            half_range_total += Unit(attacker_p).attack(target, distance=6.0)

        random.seed(7)
        full_range_total = 0.0
        for _ in range(n_trials):
            target = Unit(target_p)
            full_range_total += Unit(attacker_p).attack(target, distance=18.0)

        # At half range with RF2 we resolve 3 attacks each; at full range, 1.
        # Expected: half-range damage > full-range damage by a clear margin.
        self.assertGreater(half_range_total, full_range_total * 1.5)


class HeavyCoverHitPenaltyTests(unittest.TestCase):
    """Phase H: HEAVY_COVER gives both +1 to save AND -1 to hit, so damage
    should drop strictly more than LIGHT cover (save bonus only) against
    the same attacker / target combo.
    """

    def _attacker(self):
        # 4+ to hit, generous attacks so the dice average out fast.
        return UnitProfile(
            name="CoverShooter", health=1, damage=0,
            hit_probability=0.5, attacks=8, weapon_damage_per_shot=1.0,
            strength=10,                # auto-wound vs T4 (5/6)
            range_inches=24,
        )

    def _target(self):
        # No save -> isolating the hit-roll effect from the save effect.
        # We toggle in_cover / in_heavy_cover on the Unit instance, not
        # the profile, so the same profile suffices.
        return UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
        )

    def test_heavy_cover_target_takes_strictly_less_damage_than_open(self):
        n_trials = 400
        attacker_p = self._attacker()
        target_p = self._target()

        random.seed(101)
        open_total = 0.0
        for _ in range(n_trials):
            tgt = Unit(target_p)
            open_total += Unit(attacker_p).attack(tgt, distance=12.0)

        random.seed(101)
        heavy_total = 0.0
        for _ in range(n_trials):
            tgt = Unit(target_p)
            tgt.in_cover = True
            tgt.in_heavy_cover = True
            heavy_total += Unit(attacker_p).attack(tgt, distance=12.0)

        # With save=7 the save-bonus part of cover does nothing; isolating
        # the -1 to hit. 4+ → 5+ drops expected hits by 33%.
        self.assertGreater(open_total, heavy_total * 1.2)


class StealthTargetTests(unittest.TestCase):
    """Phase H: a target with the Stealth ability soaks fewer hits because
    the attacker takes -1 to hit (capped at 7+).
    """

    def _attacker(self):
        return UnitProfile(
            name="Shooter", health=1, damage=0,
            hit_probability=0.5, attacks=8, weapon_damage_per_shot=1.0,
            strength=10, range_inches=24,
        )

    def test_stealth_target_takes_less_damage(self):
        n_trials = 400
        attacker_p = self._attacker()
        plain = UnitProfile(
            name="Plain", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
        )
        sneaky = UnitProfile(
            name="Sneaky", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7, stealth=True,
        )

        random.seed(202)
        plain_total = 0.0
        for _ in range(n_trials):
            plain_total += Unit(attacker_p).attack(Unit(plain), distance=12.0)

        random.seed(202)
        stealth_total = 0.0
        for _ in range(n_trials):
            stealth_total += Unit(attacker_p).attack(Unit(sneaky), distance=12.0)

        self.assertGreater(plain_total, stealth_total * 1.2)


if __name__ == "__main__":
    unittest.main()
