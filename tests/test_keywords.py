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
    """Current 10e: cover grants ONLY the single Benefit of Cover (+1 to the
    armour saving throw). There is no terrain -1-to-hit and no Light/Heavy
    cover split — HEAVY_COVER (and RUIN) give exactly the same effect as
    LIGHT_COVER. These tests confirm (a) heavy cover does nothing extra over a
    plain in_cover save bonus, and (b) with a no-save target (save=7) cover
    changes nothing at all (the stale -1-to-hit is gone).
    """

    def _attacker(self):
        # 4+ to hit, generous attacks so the dice average out fast.
        return UnitProfile(
            name="CoverShooter", health=1, damage=0,
            hit_probability=0.5, attacks=8, weapon_damage_per_shot=1.0,
            strength=10,                # auto-wound vs T4 (5/6)
            ap=-1,                      # AP-1 so the +1 save can actually bite
            range_inches=24,
        )

    def _no_save_target(self):
        # No save -> isolates the (now-removed) hit-roll effect from the save
        # effect. We toggle in_cover / in_heavy_cover on the Unit instance.
        return UnitProfile(
            name="NoSaveTgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
        )

    def _saved_target(self):
        # A 4+ save so the Benefit of Cover (+1 save) measurably reduces damage.
        return UnitProfile(
            name="SaveTgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=4, unit_keywords=("INFANTRY",),
        )

    def _avg_damage(self, attacker_p, target_p, n_trials, seed, heavy):
        random.seed(seed)
        total = 0.0
        for _ in range(n_trials):
            tgt = Unit(target_p)
            tgt.in_cover = True
            if heavy:
                tgt.in_heavy_cover = True
            total += Unit(attacker_p).attack(tgt, distance=12.0)
        return total

    def test_no_save_target_unaffected_by_cover(self):
        """With save=7 the +1 save does nothing, and there is no longer a
        -1-to-hit, so a target in HEAVY cover takes the SAME damage as in the
        open (the stale 9th-edition Heavy-Cover to-hit penalty was removed)."""
        n_trials = 400
        attacker_p = self._attacker()
        target_p = self._no_save_target()

        random.seed(101)
        open_total = sum(
            Unit(attacker_p).attack(Unit(target_p), distance=12.0)
            for _ in range(n_trials)
        )
        heavy_total = self._avg_damage(attacker_p, target_p, n_trials, 101, heavy=True)

        # No save bonus that bites and no to-hit penalty => identical damage.
        self.assertEqual(open_total, heavy_total)

    def test_heavy_cover_equals_light_cover(self):
        """HEAVY_COVER must give exactly the same combat effect as LIGHT_COVER
        in current 10e (the single Benefit of Cover, +1 save)."""
        n_trials = 400
        attacker_p = self._attacker()
        target_p = self._saved_target()

        light_total = self._avg_damage(attacker_p, target_p, n_trials, 202, heavy=False)
        heavy_total = self._avg_damage(attacker_p, target_p, n_trials, 202, heavy=True)

        self.assertEqual(
            light_total, heavy_total,
            "HEAVY cover must equal LIGHT cover — no extra -1-to-hit in 10e.",
        )

    def test_cover_save_bonus_still_reduces_damage(self):
        """Sanity: the Benefit of Cover (+1 save) does still reduce damage
        against a saveable target hit by an AP-bearing attack."""
        n_trials = 400
        attacker_p = self._attacker()
        target_p = self._saved_target()

        random.seed(303)
        open_total = sum(
            Unit(attacker_p).attack(Unit(target_p), distance=12.0)
            for _ in range(n_trials)
        )
        cover_total = self._avg_damage(attacker_p, target_p, n_trials, 303, heavy=False)
        self.assertGreater(open_total, cover_total)


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
