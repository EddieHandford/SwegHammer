"""Tests for the leader-ability aura system (Phase G)."""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import Detachment
from code.leaders import (
    LeaderAbility, apply_round_end_healing, apply_round_end_revival,
    effective_buffs, in_range_leaders, lookup_ability,
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
    """3" Narthecium aura — revive 1 destroyed friendly INFANTRY model / round."""
    return UnitProfile(
        name="Apothecary",
        health=4, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _dominus_profile() -> UnitProfile:
    """Tech-Priest Dominus — still carries a heal_per_round aura (6" range)."""
    return UnitProfile(
        name="Tech-Priest Dominus",
        health=7, damage=1, hit_probability=2 / 3,
        ap=0, save=2, strength=4, toughness=6,
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
        # 10e Narthecium: revives a destroyed model in the led unit each
        # Command Phase. SwegHammer maps this to `revive_destroyed_per_round`
        # since multi-model squads are represented as N single-model Units.
        ab = lookup_ability("Apothecary")
        self.assertIsNotNone(ab)
        self.assertGreaterEqual(ab.revive_destroyed_per_round, 1)
        self.assertEqual(ab.heal_per_round, 0)
        self.assertEqual(ab.aura_range, 3.0)

    def test_unknown_returns_none(self):
        self.assertIsNone(lookup_ability("Random Scrub"))
        self.assertIsNone(lookup_ability(""))


class ExpandedRegistryTests(unittest.TestCase):
    """Phase: leader-registry expansion across major factions."""

    # Each tuple is (profile-name to look up, expected flag attribute).
    # Some entries were flipped to defensive flags as part of the
    # direction-wrong aura sweep — see citations file for codex-real text.
    # iter21 fab audit removed Autarch (Path of Command is a CP-discount,
    # not an aura) and Avatar of Khaine (Bloody-Handed is +1 Advance/Charge,
    # a movement-phase buff). Both registry entries are kept but with no
    # offensive flags; see AeldariFabricationLockInTests below.
    NEW_LEADERS = (
        # Aeldari
        ("Farseer",                 "reroll_wound_ones"),
        # T'au — Ethereal Failure Is Not an Option grants FNP 5+ (defensive)
        ("Ethereal",                "fnp"),
        ("Commander in XV85 Enforcer Battlesuit", "plus_one_to_hit"),
        # Cadre Fireblade Volley Fire: +1 Attack to ranged weapons
        ("Cadre Fireblade",         "plus_one_attack"),
        # Chaos Space Marines — Sorcerer Prescience is -1 to Hit on attacks
        # against the led unit; FNP 5+ is our defensive proxy.
        ("Sorcerer",                "fnp"),
        ("Dark Apostle",            "reroll_hit_ones"),
        ("Chaos Lord",              "plus_one_to_wound"),
        # Adeptus Custodes
        ("Shield-Captain",          "reroll_hit_ones"),
        ("Trajann Valoris",         "plus_one_to_hit"),
        # Adeptus Mechanicus
        ("Tech-Priest Dominus",     "reroll_hit_ones"),
        # Death Guard — Typhus Destroyer Hive is -1 to Hit on melee against
        # the led unit; FNP 5+ is our defensive proxy.
        ("Lord of Contagion",       "plus_one_to_wound"),
        ("Typhus",                  "fnp"),
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
    """Heal-per-round aura — exercised via Tech-Priest Dominus (6" aura).

    Apothecary's old heal-per-round was reclassified as a revive aura
    (Narthecium) — see ReviveTests below.
    """

    def test_dominus_heals_nearby_wounded(self):
        # Grunt at 1HP, Dominus 4" away (within 6" aura). After one
        # round-end heal, grunt should have 2HP.
        army = _make_army(
            "Side",
            [_grunt_profile(), _dominus_profile()],
            [(0.0, 0.0), (4.0, 0.0)],
        )
        army.units[0].current_health = 1.0
        apply_round_end_healing(army)
        self.assertEqual(army.units[0].current_health, 2.0)

    def test_heal_capped_at_max_hp(self):
        # Full-HP grunt next to Dominus: no healing happens, leader self-heals
        # only if wounded itself. Both at full HP -> no-op.
        army = _make_army(
            "Side",
            [_grunt_profile(), _dominus_profile()],
            [(0.0, 0.0), (4.0, 0.0)],
        )
        # All at full health; verify nothing exceeds max.
        apply_round_end_healing(army)
        self.assertEqual(army.units[0].current_health, 2.0)
        self.assertEqual(army.units[1].current_health, 7.0)

    def test_heal_out_of_range_no_effect(self):
        # Grunt at 1HP but 10" from Dominus (outside 6" aura). Dominus
        # itself is full HP. No healing.
        army = _make_army(
            "Side",
            [_grunt_profile(), _dominus_profile()],
            [(0.0, 0.0), (10.0, 0.0)],
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


# ---------------------------------------------------------------------------
# Direction-corrected aura sweep — leader rewrites to match codex effects
# ---------------------------------------------------------------------------

class ApothecaryReviveTests(unittest.TestCase):
    """Apothecary Narthecium: return a destroyed friendly INFANTRY model
    to play each round end (proxy for the Command-phase return-a-model rule)."""

    def test_revive_brings_dead_infantry_back(self):
        # Two grunts + Apothecary. Kill one grunt; one revival call should
        # restore the destroyed grunt to full HP.
        army = _make_army(
            "Side",
            [_grunt_profile(), _grunt_profile(), _apothecary_profile()],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
        )
        army.units[0].current_health = 0.0   # destroyed
        apply_round_end_revival(army)
        self.assertEqual(army.units[0].current_health, 2.0)
        self.assertTrue(army.units[0].is_alive)

    def test_revive_skips_characters(self):
        # Captain (CHARACTER) is destroyed — Narthecium MUST NOT revive
        # characters per codex ("excluding CHARACTER models"). The Apothecary
        # also can't revive itself.
        army = _make_army(
            "Side",
            [_captain_profile(), _apothecary_profile()],
            [(0.0, 0.0), (1.0, 0.0)],
        )
        army.units[0].current_health = 0.0   # destroyed Captain
        apply_round_end_revival(army)
        self.assertEqual(army.units[0].current_health, 0.0)


class LibrarianDefensiveFlipTests(unittest.TestCase):
    """Librarian: real Mental Fortress is DEFENSIVE (FNP / invuln).
    The registry now grants fnp=5 to nearby friendlies and DOES NOT grant
    the old (wrong-direction) +1-to-wound offensive aura."""

    def _librarian_profile(self) -> UnitProfile:
        return UnitProfile(
            name="Librarian",
            health=4, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            unit_keywords=("INFANTRY", "CHARACTER"),
        )

    def test_librarian_grants_fnp(self):
        ab = lookup_ability("Librarian")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.fnp, 5)
        self.assertFalse(ab.plus_one_to_wound)

    def test_librarian_aura_applies_fnp_in_range(self):
        army = _make_army(
            "Side",
            [_grunt_profile(), self._librarian_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertEqual(buffs["fnp"], 5)
        self.assertFalse(buffs["plus_one_to_wound"])


class WarbossHitNotWoundTests(unittest.TestCase):
    """Warboss Might is Right: +1 to the Hit roll on melee — NOT +1 wound."""

    def _warboss_profile(self) -> UnitProfile:
        return UnitProfile(
            name="Warboss",
            health=6, damage=2, hit_probability=2 / 3,
            ap=-1, save=4, strength=7, toughness=6,
            unit_keywords=("INFANTRY", "CHARACTER"),
        )

    def test_warboss_grants_plus_one_hit_not_wound(self):
        ab = lookup_ability("Warboss")
        self.assertIsNotNone(ab)
        self.assertTrue(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)

    def test_warboss_aura_lifts_hit(self):
        army = _make_army(
            "Side",
            [_grunt_profile(), self._warboss_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertTrue(buffs["plus_one_to_hit"])
        self.assertFalse(buffs["plus_one_to_wound"])


class CadreFirebladeAttackTests(unittest.TestCase):
    """Cadre Fireblade Volley Fire: +1 Attack to ranged weapons in the led unit."""

    def _fireblade_profile(self) -> UnitProfile:
        return UnitProfile(
            name="Cadre Fireblade",
            health=4, damage=1, hit_probability=2 / 3,
            ap=0, save=4, strength=4, toughness=3,
            unit_keywords=("INFANTRY", "CHARACTER"),
        )

    def test_fireblade_grants_plus_one_attack(self):
        ab = lookup_ability("Cadre Fireblade")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.plus_one_attack, 1)
        self.assertFalse(ab.reroll_hit_ones)

    def test_fireblade_aura_stacks_attacks(self):
        # +1-attack from leader should appear in the merged buff dict and
        # additively stack with any detachment plus_one_attack.
        army = _make_army(
            "Side",
            [_grunt_profile(), self._fireblade_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertEqual(buffs["plus_one_attack"], 1)


class AeldariFabricationLockInTests(unittest.TestCase):
    """iter21 fab audit lock-ins.

    Three Aeldari registry entries had proxy flags with NO basis in their
    codex datasheets. Each proxy was dropped:

      * Autarch — Path of Command is a once-per-round Stratagem CP discount
        (same pattern as Necron Overlord's My Will Be Done, which iter20
        audited). The previous plus_one_to_hit aura was invented flavour;
        not a codex effect.

      * Avatar of Khaine — Bloody-Handed grants +1 to Advance and Charge
        rolls (a movement-phase buff). The previous reroll_hit_ones aura
        was an admitted wrong-buff-TYPE stand-in; nothing in the codex
        modifies hit rolls.

      * The Yncarne — Ethereal Form is on-kill D3 wound regain;
        Inevitable Death is a reactive teleport. The previous
        plus_one_to_hit aura was an admitted 'loose threat-mobility
        proxy' with no codex support. heal_per_round=2 is retained as
        a legitimate D3-median proxy of Ethereal Form.

    These tests lock the absence of those proxies so a regression that
    re-introduces them fails CI immediately.
    """

    def _aeldari_profile(self, name: str) -> UnitProfile:
        return UnitProfile(
            name=name, health=4, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=3,
            unit_keywords=("INFANTRY", "CHARACTER"),
        )

    def test_autarch_has_no_offensive_aura(self):
        ab = lookup_ability("Autarch")
        self.assertIsNotNone(ab, "Autarch entry must remain in the registry")
        # All offensive flags must be off — Path of Command is a CP-discount.
        self.assertFalse(ab.plus_one_to_hit, "Autarch plus_one_to_hit is a fab — see iter21 citation")
        self.assertFalse(ab.plus_one_to_wound)
        self.assertFalse(ab.reroll_hit_ones)
        self.assertFalse(ab.reroll_wound_ones)
        self.assertEqual(ab.plus_one_attack, 0)
        # Defensive flags must also be off
        self.assertEqual(ab.fnp, 7)
        self.assertEqual(ab.extra_invuln, 7)

    def test_avatar_of_khaine_has_no_offensive_aura(self):
        ab = lookup_ability("Avatar of Khaine")
        self.assertIsNotNone(ab, "Avatar of Khaine entry must remain in the registry")
        # Bloody-Handed is +1 Advance/Charge — a movement buff, not a hit buff.
        self.assertFalse(ab.reroll_hit_ones, "Avatar reroll_hit_ones is a wrong-buff-type fab — see iter21 citation")
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)
        self.assertFalse(ab.reroll_wound_ones)
        self.assertEqual(ab.plus_one_attack, 0)
        self.assertEqual(ab.fnp, 7)

    def test_yncarne_has_no_to_hit_aura(self):
        ab = lookup_ability("The Yncarne")
        self.assertIsNotNone(ab, "Yncarne entry must remain in the registry")
        # Ethereal Form is a self-heal; Inevitable Death is a teleport.
        # Neither grants a hit-roll buff.
        self.assertFalse(ab.plus_one_to_hit, "Yncarne plus_one_to_hit is a fab — see iter21 citation")
        # heal_per_round MUST stay (legitimate D3-median proxy of Ethereal Form).
        self.assertEqual(ab.heal_per_round, 2)

    def test_autarch_aura_grants_nothing_in_range(self):
        # Build an Aeldari unit + Autarch in range; the merged buff dict
        # must have ALL flags neutral (the registry entry is now a no-op).
        autarch_p = self._aeldari_profile("Autarch")
        army = _make_army(
            "Side",
            [_grunt_profile(), autarch_p],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertFalse(buffs["plus_one_to_hit"])
        self.assertFalse(buffs["reroll_hit_ones"])
        self.assertFalse(buffs["plus_one_to_wound"])
        self.assertEqual(buffs["fnp"], 7)

    def test_avatar_aura_grants_nothing_in_range(self):
        avatar_p = UnitProfile(
            name="Avatar of Khaine", health=12, damage=4, hit_probability=2 / 3,
            ap=-3, save=3, strength=10, toughness=10,
            unit_keywords=("MONSTER", "CHARACTER", "EPIC HERO"),
        )
        army = _make_army(
            "Side",
            [_grunt_profile(), avatar_p],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertFalse(buffs["reroll_hit_ones"])
        self.assertFalse(buffs["plus_one_to_hit"])

    def test_yncarne_aura_grants_nothing_in_range(self):
        # Aura should NOT grant plus_one_to_hit. heal_per_round is exercised
        # by HealTests via Dominus; we just confirm the merged offensive
        # dict is empty here.
        yncarne_p = UnitProfile(
            name="The Yncarne", health=10, damage=4, hit_probability=2 / 3,
            ap=-3, save=3, strength=8, toughness=8,
            unit_keywords=("MONSTER", "CHARACTER", "EPIC HERO"),
        )
        army = _make_army(
            "Side",
            [_grunt_profile(), yncarne_p],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertFalse(buffs["plus_one_to_hit"])
        self.assertFalse(buffs["reroll_hit_ones"])


if __name__ == "__main__":
    unittest.main()
