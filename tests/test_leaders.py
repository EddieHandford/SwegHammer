"""Tests for the leader-ability aura system (Phase G)."""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import Detachment
from code.leaders import (
    LeaderAbility, apply_round_end_healing, effective_buffs,
    in_range_leaders, lookup_ability,
)
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Test fixtures — tiny profiles to keep the math obvious
# ---------------------------------------------------------------------------

def _grunt_profile(name: str = "Grunt") -> UnitProfile:
    """A simple, non-character infantry profile."""
    return UnitProfile(
        name=name, health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0,
        unit_keywords=("INFANTRY",),
    )


def _captain_profile() -> UnitProfile:
    """Carries the 'Captain' substring → matches the Captain registry entry."""
    return UnitProfile(
        name="Captain",
        health=4, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _apothecary_profile() -> UnitProfile:
    """3" heal aura."""
    return UnitProfile(
        name="Apothecary",
        health=4, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _make_army(name: str, members: list, positions: list) -> Army:
    """Build an Army, manually placing units (Battle._deploy doesn't run here)."""
    army = Army(name)
    for profile, pos in zip(members, positions):
        army.add_unit(profile)
        army.units[-1].position = pos
    return army


# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------

class RegistryLookupTests(unittest.TestCase):
    """Substring matching against the leader registry."""

    def test_captain_exact(self):
        ab = lookup_ability("Captain")
        self.assertIsNotNone(ab)
        self.assertTrue(ab.reroll_hit_ones)
        self.assertEqual(ab.aura_range, 6.0)

    def test_captain_in_terminator_armour_substring(self):
        # Real BSData name — substring match must hit "Captain".
        ab = lookup_ability("Captain in Terminator Armour")
        self.assertIsNotNone(ab)
        self.assertTrue(ab.reroll_hit_ones)

    def test_chaplain(self):
        ab = lookup_ability("Chaplain")
        self.assertIsNotNone(ab)
        self.assertTrue(ab.reroll_wound_ones)

    def test_apothecary(self):
        ab = lookup_ability("Apothecary")
        self.assertIsNotNone(ab)
        self.assertGreaterEqual(ab.heal_per_round, 1)
        self.assertEqual(ab.aura_range, 3.0)

    def test_unknown_returns_none(self):
        self.assertIsNone(lookup_ability("Random Scrub"))
        self.assertIsNone(lookup_ability(""))


class ExpandedRegistryTests(unittest.TestCase):
    """Phase: leader-registry expansion across major factions."""

    # Each tuple is (profile-name to look up, expected flag attribute).
    NEW_LEADERS = (
        # Aeldari
        ("Farseer",                 "reroll_wound_ones"),
        ("Autarch",                 "plus_one_to_hit"),
        ("Avatar of Khaine",        "reroll_hit_ones"),
        # T'au
        ("Ethereal",                "reroll_wound_ones"),
        ("Commander in XV85 Enforcer Battlesuit", "plus_one_to_hit"),
        ("Cadre Fireblade",         "reroll_hit_ones"),
        # Chaos Space Marines
        ("Sorcerer",                "plus_one_to_wound"),
        ("Dark Apostle",            "reroll_hit_ones"),
        ("Chaos Lord",              "plus_one_to_wound"),
        # Adeptus Custodes
        ("Shield-Captain",          "reroll_hit_ones"),
        ("Trajann Valoris",         "plus_one_to_hit"),
        # Adeptus Mechanicus
        ("Tech-Priest Dominus",     "reroll_hit_ones"),
        # Death Guard
        ("Lord of Contagion",       "plus_one_to_wound"),
        ("Typhus",                  "reroll_wound_ones"),
        # Grey Knights
        ("Brother-Captain",         "reroll_hit_ones"),
        ("Grand Master",            "plus_one_to_wound"),
        # Drukhari
        ("Archon",                  "plus_one_to_hit"),
        ("Succubus",                "reroll_hit_ones"),
        # Genestealer Cults
        ("Primus",                  "reroll_hit_ones"),
        # Leagues of Votann
        ("Kâhl",                    "plus_one_to_hit"),
    )

    def test_each_new_leader_resolves(self):
        for name, flag in self.NEW_LEADERS:
            ab = lookup_ability(name)
            self.assertIsNotNone(ab, f"{name} did not resolve via lookup_ability")
            self.assertTrue(
                getattr(ab, flag),
                f"{name} resolved but the expected flag {flag!r} was not set",
            )

    def test_tech_priest_dominus_heals(self):
        # Dominus carries both an offensive aura AND a heal aura.
        ab = lookup_ability("Tech-Priest Dominus")
        self.assertIsNotNone(ab)
        self.assertGreaterEqual(ab.heal_per_round, 1)

    def test_archon_not_false_positive(self):
        # 'Archon' must resolve. Confirm Arch-style substring collisions don't
        # cause unrelated entries to leak through (no 'Arch' substring entries).
        self.assertIsNotNone(lookup_ability("Archon"))
        # Drazhar / Archons-on-Raider variants still match "Archon".
        self.assertIsNotNone(lookup_ability("Archon on Skyboard"))

    def test_registry_size(self):
        # Sanity check: we expanded from 11 to at least 25 entries.
        from code.leaders import _REGISTRY
        self.assertGreaterEqual(len(_REGISTRY), 25)


# ---------------------------------------------------------------------------
# effective_buffs — merge detachment + in-range leaders
# ---------------------------------------------------------------------------

class EffectiveBuffsTests(unittest.TestCase):
    """A unit's merged buffs should OR the bool flags and min the int values."""

    def test_no_buffs_when_alone(self):
        # Single grunt, no army_ref. effective_buffs returns the neutral dict.
        u = Unit(_grunt_profile())
        buffs = effective_buffs(u)
        self.assertFalse(buffs["reroll_hit_ones"])
        self.assertFalse(buffs["plus_one_to_wound"])
        self.assertEqual(buffs["extra_invuln"], 7)
        self.assertEqual(buffs["fnp"], 7)

    def test_detachment_flags_pass_through(self):
        # Detachment grants reroll_wound_ones; no leader present.
        det = Detachment(
            name="Test", faction="X", reroll_wound_ones=True, plus_one_save=True,
        )
        army = _make_army("Side", [_grunt_profile()], [(0.0, 0.0)])
        army.detachment = det
        buffs = effective_buffs(army.units[0])
        self.assertTrue(buffs["reroll_wound_ones"])
        self.assertTrue(buffs["plus_one_save"])
        # Leader-only fields stay off
        self.assertEqual(buffs["fnp"], 7)

    def test_leader_aura_in_range(self):
        # Captain 5" away from grunt (within 6") -> reroll_hit_ones True.
        army = _make_army(
            "Side",
            [_grunt_profile(), _captain_profile()],
            [(0.0, 0.0), (5.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertTrue(buffs["reroll_hit_ones"])

    def test_leader_aura_out_of_range(self):
        # Captain 12" away from grunt (outside 6") -> NO reroll.
        army = _make_army(
            "Side",
            [_grunt_profile(), _captain_profile()],
            [(0.0, 0.0), (12.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertFalse(buffs["reroll_hit_ones"])

    def test_dead_leader_does_not_buff(self):
        # Captain in range but dead -> no aura.
        army = _make_army(
            "Side",
            [_grunt_profile(), _captain_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        army.units[1].current_health = 0.0
        buffs = effective_buffs(army.units[0])
        self.assertFalse(buffs["reroll_hit_ones"])

    def test_merge_detachment_and_leader(self):
        # Detachment gives reroll_wound_ones; leader gives reroll_hit_ones.
        # The merged dict should carry BOTH flags.
        det = Detachment(name="Test", faction="X", reroll_wound_ones=True)
        army = _make_army(
            "Side",
            [_grunt_profile(), _captain_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        army.detachment = det
        buffs = effective_buffs(army.units[0])
        self.assertTrue(buffs["reroll_hit_ones"])
        self.assertTrue(buffs["reroll_wound_ones"])

    def test_in_range_leaders_excludes_self(self):
        # A Captain looking up its own buffs shouldn't see itself as a leader.
        army = _make_army(
            "Side",
            [_captain_profile(), _grunt_profile()],
            [(0.0, 0.0), (5.0, 0.0)],
        )
        leaders = in_range_leaders(army.units[0])
        self.assertEqual(leaders, [])


# ---------------------------------------------------------------------------
# Round-end heal
# ---------------------------------------------------------------------------

class HealTests(unittest.TestCase):

    def test_apothecary_heals_nearby_wounded(self):
        # Grunt at 1HP, Apothecary 2" away (within 3" aura). After one
        # round-end heal, grunt should have 2HP.
        army = _make_army(
            "Side",
            [_grunt_profile(), _apothecary_profile()],
            [(0.0, 0.0), (2.0, 0.0)],
        )
        army.units[0].current_health = 1.0
        apply_round_end_healing(army)
        self.assertEqual(army.units[0].current_health, 2.0)

    def test_heal_capped_at_max_hp(self):
        # Full-HP grunt next to Apothecary: no healing happens, leader self-heals
        # only if wounded itself. Both at full HP -> no-op.
        army = _make_army(
            "Side",
            [_grunt_profile(), _apothecary_profile()],
            [(0.0, 0.0), (2.0, 0.0)],
        )
        # All at full health; verify nothing exceeds max.
        apply_round_end_healing(army)
        self.assertEqual(army.units[0].current_health, 2.0)
        self.assertEqual(army.units[1].current_health, 4.0)

    def test_heal_out_of_range_no_effect(self):
        # Grunt at 1HP but 6" from Apothecary (outside 3" aura). Apothecary
        # itself is full HP. No healing.
        army = _make_army(
            "Side",
            [_grunt_profile(), _apothecary_profile()],
            [(0.0, 0.0), (6.0, 0.0)],
        )
        army.units[0].current_health = 1.0
        apply_round_end_healing(army)
        self.assertEqual(army.units[0].current_health, 1.0)


# ---------------------------------------------------------------------------
# Aura's actual effect on attack rolls (sanity check the wiring)
# ---------------------------------------------------------------------------

class AuraAttackEffectTests(unittest.TestCase):

    def test_captain_aura_lifts_hits(self):
        # An attacker on a 4+ hit with reroll-1s averages MORE damage than the
        # same attacker without the aura. Use enough trials for the gap to
        # exceed dice noise.
        random.seed(0)
        n = 600

        target_p = UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
        )

        atk_p = UnitProfile(
            name="Shooter", health=1, damage=0,
            hit_probability=0.5,           # 4+ to hit
            attacks=2, weapon_damage_per_shot=1.0,
            strength=10,                   # auto-wound vs T4
            unit_keywords=("INFANTRY",),
        )

        # Without leader
        no_leader_army = _make_army("NoLeader", [atk_p], [(0.0, 0.0)])
        total_no = 0.0
        for _ in range(n):
            tgt = Unit(target_p)
            total_no += no_leader_army.units[0].attack(tgt, distance=6.0)

        # With Captain leader 3" away
        leader_army = _make_army(
            "WithLeader", [atk_p, _captain_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        total_with = 0.0
        for _ in range(n):
            tgt = Unit(target_p)
            total_with += leader_army.units[0].attack(tgt, distance=6.0)

        # reroll-1s on a 4+ hit lifts hit chance from 3/6 -> ~3.5/6.
        # Margin should be visible at n=600 trials.
        self.assertGreater(total_with, total_no)


if __name__ == "__main__":
    unittest.main()
