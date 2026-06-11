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
    """A simple, non-character infantry profile.

    iter22 note: when the unit needs to be a legal bodyguard for a leader
    aura to apply through the host_keys gate in `effective_buffs`, pass a
    `name` that matches a UNIT_CATALOG entry — e.g. "Boyz" (Ork Warboss
    host), "Necron Warriors" (Necron Overlord host), "Plague Marines"
    (Lord of Contagion / Typhus host). For aura tests that intentionally
    need to verify the host gate REJECTS, leave the default "Grunt" name —
    `_name_to_catalog_key('Grunt')` returns None, which fails any
    non-empty `host_keys` tuple.
    """
    return UnitProfile(
        name=name, health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0,
        unit_keywords=("INFANTRY",),
    )


def _boyz_profile() -> UnitProfile:
    """A grunt named 'Boyz' — matches the Ork Warboss `host_keys=('orks_boyz', 'orks_nobz')`
    via UNIT_CATALOG's `orks_boyz` entry. Use this whenever a test needs
    Warboss's Might-is-Right aura to actually pass the iter22 host gate.
    """
    return _grunt_profile(name="Boyz")


def _tactical_squad_profile() -> UnitProfile:
    """A grunt named 'Tactical Squad' — matches the Marines leader hosts
    via UNIT_CATALOG's `space_marines_tactical_squad` entry. Use for
    tests that need Captain / Chaplain / Apothecary / Librarian auras to
    pass the iter22 host gate.
    """
    return _grunt_profile(name="Tactical Squad")


def _skitarii_vanguard_profile() -> UnitProfile:
    """A grunt named 'Skitarii Vanguard' — matches Tech-Priest Dominus's
    `host_keys=('adeptus_mechanicus_skitarii_vanguard', 'adeptus_mechanicus_skitarii_rangers')`
    via UNIT_CATALOG. Use for tests that need Dominus's reroll-1s aura to
    pass the iter22 host gate.
    """
    return _grunt_profile(name="Skitarii Vanguard")


def _strike_team_profile() -> UnitProfile:
    """A grunt named 'Strike Team' — matches T'au leader hosts
    (Cadre Fireblade, Ethereal). Use for tests that need their auras to
    pass the iter22 host gate.
    """
    return _grunt_profile(name="Strike Team")


def _captain_profile() -> UnitProfile:
    """Carries the 'Captain' substring → matches the Captain registry entry.

    iter21 note: Captain's LeaderAbility no longer carries an offensive
    aura proxy — Rites of Battle is a Strat-CP discount, not a re-roll.
    Tests that historically relied on Captain to trigger an aura now use
    the Warboss profile (real +1-to-hit codex aura) instead.
    """
    return UnitProfile(
        name="Captain",
        health=4, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _warboss_profile() -> UnitProfile:
    """Carries the 'Warboss' substring → +1-to-hit aura (Might is Right).
    Used by tests that need an actually-buffing leader after the iter21
    Marines fab audit pruned Captain/Chaplain's proxy aura flags.
    """
    return UnitProfile(
        name="Warboss",
        health=6, damage=2, hit_probability=2 / 3,
        ap=-1, save=4, strength=7, toughness=6,
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
        # iter21 fabrication audit — Captain's "Rites of Battle" is a
        # once-per-round 1 CP discount on a Stratagem, NOT a hit-re-roll
        # aura. The entry remains in the registry (so host_keys still
        # resolves Captain for proximity / `is_actually_led` gates), but
        # the offensive `reroll_hit_ones=True` proxy was dropped. The
        # entry now contributes no buff flags.
        ab = lookup_ability("Captain")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_hit_ones)
        self.assertEqual(ab.aura_range, 6.0)

    def test_captain_in_terminator_armour_substring(self):
        # Real BSData name — substring match must hit "Captain".
        # The variant inherits the iter21 fab-dropped flags.
        ab = lookup_ability("Captain in Terminator Armour")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_hit_ones)

    def test_chaplain(self):
        # iter21 fabrication audit — Chaplain's "Spiritual Leader" is a
        # once-per-battle Battle-shock removal, NOT a re-roll-wound-1s
        # aura. The entry remains for host_keys / proximity gates but
        # no longer carries the offensive proxy.
        ab = lookup_ability("Chaplain")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_wound_ones)

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
        # Aeldari — Farseer reroll_wound_ones removed in wave 236 (Branching Fates
        # is once-per-phase set-one-roll-to-6, not an always-on wound-reroll aura).
        # Absence locked in AeldariFabricationLockInTests.test_farseer_has_no_wound_reroll.
        # T'au — Ethereal Failure Is Not an Option grants FNP 5+ (defensive)
        ("Ethereal",                "fnp"),
        # NOTE: the "Commander in <variant> Battlesuit" Coordinated Fire Plan
        # used to assert plus_one_to_hit here; wave 212 removed that fabricated
        # proxy (the real rule grants [ASSAULT] + Move 12" to the led unit, no
        # Hit bonus). The absence is now locked by
        # CoordinatedFirePlanFidelityTests below.
        # Cadre Fireblade Volley Fire: +1 Attack to ranged weapons
        ("Cadre Fireblade",         "plus_one_attack"),
        # Chaos Space Marines — Sorcerer Prescience is -1 to Hit on attacks
        # against the led unit; FNP 5+ is our defensive proxy.
        ("Sorcerer",                "fnp"),
        ("Dark Apostle",            "reroll_hit_ones"),
        # Chaos Lord plus_one_to_wound removed in wave 236 (Lord of Chaos is a
        # once-per-battle-round Stratagem command-point-discount, not a wound-roll
        # aura). Absence locked in ChaosLordLordOfChaosRemovalTests in
        # tests/test_leader_fabrications_wave236.py.
        # Registry entry retained; assert the structural no-op (aura_range still 6.0).
        ("Chaos Lord",              "aura_range"),
        # Adeptus Custodes
        # CUSTODES-AUDIT (claude/sim-calibration-6): Shield-Captain's
        # reroll_hit_ones proxy was removed — "Master of the Stances" is a
        # once-per-battle Ka'tah stance ability, not a hit-reroll aura.
        # The entry is retained in the registry for host-key gating. Updated
        # to assert the structural no-op (aura_range still 6.0).
        # audited away in CUSTODES-AUDIT (claude/sim-calibration-6)
        ("Shield-Captain",          "aura_range"),
        # Trajann Valoris removed from this assertion list in SC5-3: his
        # Captain-General ability is modifier-cancellation (negates -1-to-hit),
        # not +1-to-hit, so the LeaderAbility carries no offensive aura field.
        # The Blade Champion entry above is the established precedent — keep
        # the leader registered for host-key gating without a flat buff.
        # Adeptus Mechanicus
        # ADMECH-DIAG-3 (2026-05-26): Dominus reroll_hit_ones and heal_per_round
        # were fabrications. The real "Lord of the Machine Cult" ability grants
        # Feel No Pain 5+ to the led unit. Updated assertion to fnp.
        # audited away in ADMECH-DIAG-3 (2026-05-26)
        ("Tech-Priest Dominus",     "fnp"),
        # Death Guard — Typhus Destroyer Hive is -1 to Hit on melee against
        # the led unit; FNP 5+ is our defensive proxy.
        ("Lord of Contagion",       "plus_one_to_wound"),
        ("Typhus",                  "fnp"),
        # Grey Knights
        ("Brother-Captain",         "reroll_hit_ones"),
        ("Grand Master",            "plus_one_to_wound"),
        # Drukhari
        # DRK-DIAG-3 (2026-05-23): Archon's plus_one_to_hit and Succubus's
        # reroll_hit_ones were fabrications. Archon "Hatred Eternal" is a
        # Pain-token-gated Empower mechanic (not always-on +1-to-hit).
        # Succubus "Storm of Blades" grants [SUSTAINED HITS 1] (a weapon
        # keyword), not a Hit-roll re-roll aura. Both dropped to NO-FLAG.
        # Both entries retained in registry for host-key gating; assertions
        # updated to check the aura_range structural field (always 6.0) so
        # the entry still exercises lookup_ability resolution.
        # audited away in DRK-DIAG-3 (2026-05-23)
        ("Archon",                  "aura_range"),
        ("Succubus",                "aura_range"),
        # Genestealer Cults
        # GSC-BUFF-V1 (2026-05-31): Patriarch "Might From Beyond" grants
        # [DEVASTATING WOUNDS] to melee weapons of the led Purestrain
        # Genestealers unit. BSData v10.6.0 confirmed.
        ("Patriarch",               "grants_devastating_wounds_melee"),
        # GSC-BUFF-V1 (2026-05-31): Primus Cult Demagogue corrected from
        # reroll_hit_ones (prior fabricated "Meticulous Uprising" proxy) to
        # plus_one_to_hit (codex-accurate: "add 1 to the Hit roll").
        # BSData v10.6.0 Genestealer Cults.cat.gz confirmed.
        ("Primus",                  "plus_one_to_hit"),
        # Leagues of Votann
        # VOTANN-JUDGEMENT-TOKENS-V1 (2026-05-28): Kâhl's aura was downgraded
        # from plus_one_to_hit to reroll_hit_ones. The codex rule grants
        # [LETHAL HITS] to the led unit's weapons; reroll_hit_ones is a closer
        # numerical proxy than plus_one_to_hit (~17% vs ~33% wound uplift on BS4+).
        # audited/narrowed in VOTANN-JUDGEMENT-TOKENS-V1 (2026-05-28)
        ("Kâhl",                    "reroll_hit_ones"),
        # Chaos Space Marines — three new leaders (wave 237).
        # Master of Possession and Warpsmith have no expressible led-unit aura
        # (both abilities are Movement-phase roll modifiers or Command-phase
        # vehicle-targeting abilities). Registry entries exist for CLAUDE.md
        # rule 13 (fail loud on missing data). Assert structural aura_range.
        ("Master of Possession",    "aura_range"),
        ("Warpsmith",               "aura_range"),
        # Dark Commune: Faithful Flock grants extra_invuln=5 to the led unit
        # (Accursed Cultists / Cultist Mob) while a Cult Demagogue is present.
        ("Dark Commune",            "extra_invuln"),
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
        # ADMECH-DIAG-3 (2026-05-26): heal_per_round was removed from Dominus.
        # The real "Lord of the Machine Cult" ability grants Feel No Pain 5+
        # to the led unit — there is no heal-per-round component in the codex
        # text. The prior heal proxy was an unanchored vehicle-repair flavour
        # stand-in. Updated: assert fnp=5 (the faithful codex mechanic) and
        # assert heal_per_round == 0 (the audited-away proxy) as a regression
        # pin. audited away in ADMECH-DIAG-3 (2026-05-26)
        ab = lookup_ability("Tech-Priest Dominus")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.fnp, 5,
            "Dominus Lord of the Machine Cult grants Feel No Pain 5+ — "
            "see ADMECH-DIAG-3 audit in claude/sim-calibration-6")
        self.assertEqual(ab.heal_per_round, 0,
            "Dominus heal_per_round was a fabrication — audited away in "
            "ADMECH-DIAG-3 (2026-05-26); must remain 0 as regression pin")

    def test_archon_not_false_positive(self):
        # 'Archon' must resolve. Confirm Arch-style substring collisions don't
        # cause unrelated entries to leak through (no 'Arch' substring entries).
        self.assertIsNotNone(lookup_ability("Archon"))
        # Drazhar / Archons-on-Raider variants still match "Archon".
        self.assertIsNotNone(lookup_ability("Archon on Skyboard"))

    def test_registry_size(self):
        # Sanity check: wave 237 added three new CSM leaders; minimum bumped
        # from 25 to 28 to pin all three as regression guards.
        from code.leaders import _REGISTRY
        self.assertGreaterEqual(len(_REGISTRY), 28)


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
        # Warboss 5" away from Boyz (within 6") -> plus_one_to_hit_melee_only True.
        # iter21: Captain's proxy aura was dropped, so this test uses the Warboss.
        # iter22: attacker must be in Warboss's host_keys (`orks_boyz` /
        # `orks_nobz`) for the aura to fire — use `_boyz_profile()` so
        # `_name_to_catalog_key('Boyz') == 'orks_boyz'` passes the gate.
        # ORKS-DIAG-3 (e52695f): Warboss "Might is Right" is melee-only per the
        # codex verbatim. The aura moved from plus_one_to_hit to
        # plus_one_to_hit_melee_only. Assertion updated accordingly.
        # narrowed in ORKS-DIAG-3 (e52695f)
        army = _make_army(
            "Side",
            [_boyz_profile(), _warboss_profile()],
            [(0.0, 0.0), (5.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertTrue(buffs["plus_one_to_hit_melee_only"])
        self.assertFalse(buffs["plus_one_to_hit"],
            "Warboss plus_one_to_hit was over-broad — audited to melee-only "
            "in ORKS-DIAG-3 (e52695f); must remain False as regression pin")

    def test_leader_aura_out_of_range(self):
        # Warboss 12" away from grunt (outside 6") -> NO aura.
        # iter22: even with a legal Boyz host attacker, the leader is
        # out of aura_range so in_range_leaders returns [] before the
        # host_keys gate is consulted.
        army = _make_army(
            "Side",
            [_boyz_profile(), _warboss_profile()],
            [(0.0, 0.0), (12.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertFalse(buffs["plus_one_to_hit"])

    def test_dead_leader_does_not_buff(self):
        # Warboss in range but dead -> no aura.
        # iter22: Boyz host attacker so the gate would PASS if the
        # Warboss were alive; the test isolates the alive-leader gate.
        army = _make_army(
            "Side",
            [_boyz_profile(), _warboss_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        army.units[1].current_health = 0.0
        buffs = effective_buffs(army.units[0])
        self.assertFalse(buffs["plus_one_to_hit"])

    def test_merge_detachment_and_leader(self):
        # Detachment gives reroll_wound_ones; Warboss leader gives
        # plus_one_to_hit_melee_only. The merged dict should carry BOTH flags.
        # iter22: use Boyz attacker so the Warboss aura passes host gate.
        # ORKS-DIAG-3 (e52695f): Warboss "Might is Right" is melee-only; the
        # aura moved from plus_one_to_hit to plus_one_to_hit_melee_only.
        # Assertion updated accordingly. narrowed in ORKS-DIAG-3 (e52695f)
        det = Detachment(name="Test", faction="X", reroll_wound_ones=True)
        army = _make_army(
            "Side",
            [_boyz_profile(), _warboss_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        army.detachment = det
        buffs = effective_buffs(army.units[0])
        self.assertTrue(buffs["plus_one_to_hit_melee_only"])
        self.assertFalse(buffs["plus_one_to_hit"],
            "Warboss plus_one_to_hit was audited to melee-only in ORKS-DIAG-3 "
            "(e52695f) — regression pin: must remain False")
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
        # ADMECH-DIAG-3 (2026-05-26): Dominus heal_per_round was a fabrication.
        # The real "Lord of the Machine Cult" grants Feel No Pain 5+ (not a
        # heal-per-round). apply_round_end_healing now has no effect from Dominus.
        # This test is repurposed to pin that Dominus does NOT heal and instead
        # grants fnp=5 — a regression guard against re-introducing the proxy.
        # audited away in ADMECH-DIAG-3 (2026-05-26); heal_per_round removed.
        #
        # Use a Skitarii Vanguard host name so we can check effective_buffs via
        # a Corpuscarii Electro-Priests stand-in. But because UNIT_CATALOG does
        # not list Dominus with Skitarii in its current host_keys (ADMECH-DIAG-6
        # stripped Skitarii from host_keys to fix broadcast over-application),
        # we simply verify the heal-pipeline no-ops and the ability state.
        army = _make_army(
            "Side",
            [_grunt_profile(), _dominus_profile()],
            [(0.0, 0.0), (4.0, 0.0)],
        )
        army.units[0].current_health = 1.0
        apply_round_end_healing(army)
        # Dominus has no heal_per_round — health must be unchanged.
        self.assertEqual(army.units[0].current_health, 1.0,
            "Dominus heal_per_round is 0 after ADMECH-DIAG-3 audit — "
            "apply_round_end_healing must leave grunt health unchanged")
        # Confirm the ability itself carries fnp=5 as the faithful proxy.
        ab = lookup_ability("Tech-Priest Dominus")
        self.assertEqual(ab.fnp, 5,
            "Dominus Lord of the Machine Cult grants Feel No Pain 5+; "
            "confirmed no heal_per_round — audited in ADMECH-DIAG-3")

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

    def test_warboss_aura_lifts_hits(self):
        # iter21 fab audit: the legacy Captain-aura damage-lift test was
        # invalidated by dropping Captain's `reroll_hit_ones=True` proxy
        # (Rites of Battle is a Strat-CP discount, not an offensive aura).
        # Use the Ork Warboss, whose +1-to-hit aura IS the codex's "Might
        # is Right" (verbatim "add 1 to the Hit roll" on melee — direction-
        # correct offensive buff), to assert the aura wiring still lifts
        # damage when a real offensive aura is in range.
        random.seed(0)
        n = 600

        target_p = UnitProfile(
            name="Tgt", health=1e9, damage=0, hit_probability=0,
            toughness=4, save=7,
        )

        # iter22: attacker must be a legal Warboss bodyguard (`orks_boyz` /
        # `orks_nobz`) for the +1-to-hit aura to pass the host gate. Use
        # the "Boyz" UNIT_CATALOG name on the synthetic shooter profile so
        # `_name_to_catalog_key('Boyz') == 'orks_boyz'`. Keep the
        # streamlined stat-line (auto-wound vs T4) for math clarity; only
        # the .name changes.
        atk_p = UnitProfile(
            name="Boyz", health=1, damage=0,
            hit_probability=0.5,           # 4+ to hit
            attacks=2, weapon_damage_per_shot=1.0,
            strength=10,                   # auto-wound vs T4
            unit_keywords=("INFANTRY",),
        )

        warboss_p = UnitProfile(
            name="Warboss",
            health=6, damage=2, hit_probability=2 / 3,
            ap=-1, save=4, strength=7, toughness=6,
            unit_keywords=("INFANTRY", "CHARACTER"),
        )

        # Without leader
        no_leader_army = _make_army("NoLeader", [atk_p], [(0.0, 0.0)])
        total_no = 0.0
        for _ in range(n):
            tgt = Unit(target_p)
            total_no += no_leader_army.units[0].attack(tgt, distance=6.0)

        # With Warboss leader 3" away
        leader_army = _make_army(
            "WithLeader", [atk_p, warboss_p],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        total_with = 0.0
        for _ in range(n):
            tgt = Unit(target_p)
            total_with += leader_army.units[0].attack(tgt, distance=6.0)

        # +1-to-hit on a 4+ hit lifts hit chance from 3/6 -> 4/6.
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
        # iter22: Librarian's host_keys lists `_MARINE_HOSTS` — the attacker
        # must be a legal Marines bodyguard (Tactical Squad / Assault
        # Intercessor Squad) for the FNP aura to pass the host gate.
        army = _make_army(
            "Side",
            [_tactical_squad_profile(), self._librarian_profile()],
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
        # ORKS-DIAG-3 (e52695f): Warboss "Might is Right" is a melee-only
        # +1-to-hit per the codex verbatim ("each time a model in that unit
        # makes a melee attack, add 1 to the Hit roll"). The aura moved from
        # plus_one_to_hit (all-phases) to plus_one_to_hit_melee_only.
        # plus_one_to_hit must now be False as a regression pin against the
        # over-broad proxy being re-introduced.
        # narrowed in ORKS-DIAG-3 (e52695f)
        ab = lookup_ability("Warboss")
        self.assertIsNotNone(ab)
        self.assertTrue(ab.plus_one_to_hit_melee_only,
            "Warboss Might is Right grants +1 to Hit on melee attacks only")
        self.assertFalse(ab.plus_one_to_hit,
            "Warboss plus_one_to_hit was over-broad — audited to melee-only "
            "in ORKS-DIAG-3 (e52695f); regression pin: must remain False")
        self.assertFalse(ab.plus_one_to_wound)

    def test_warboss_aura_lifts_hit(self):
        # iter22: Warboss's host_keys lists `orks_boyz` / `orks_nobz` — use
        # a Boyz attacker so the aura passes the host gate.
        # ORKS-DIAG-3 (e52695f): Warboss "Might is Right" is melee-only; the
        # aura moved from plus_one_to_hit to plus_one_to_hit_melee_only.
        # Assertion updated accordingly. narrowed in ORKS-DIAG-3 (e52695f)
        army = _make_army(
            "Side",
            [_boyz_profile(), self._warboss_profile()],
            [(0.0, 0.0), (3.0, 0.0)],
        )
        buffs = effective_buffs(army.units[0])
        self.assertTrue(buffs["plus_one_to_hit_melee_only"],
            "Warboss Might is Right must fire for a Boyz host attacker in range")
        self.assertFalse(buffs["plus_one_to_hit"],
            "Warboss plus_one_to_hit was audited to melee-only in ORKS-DIAG-3 "
            "(e52695f) — regression pin: must remain False")
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
        # iter22: Cadre Fireblade's host_keys lists Strike Team / Breacher
        # Team — use a Strike Team attacker so the aura passes the gate.
        army = _make_army(
            "Side",
            [_strike_team_profile(), self._fireblade_profile()],
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
        # Neither grants a hit-roll buff. plus_one_to_hit was audited away
        # in iter21 fab audit (commit b50533e TSON-FINISH / 347b8f9 iter21 Aeldari).
        self.assertFalse(ab.plus_one_to_hit, "Yncarne plus_one_to_hit is a fab — see iter21 citation")
        # heal_per_round MUST stay as a legitimate D3-median proxy of Ethereal Form.
        # AELDARI-DIAG-3 (2026-05-24): cut from 2 to 1 — the real rule fires
        # on-unit-kill (not every round end); heal_per_round=2 was a 3x over-proxy
        # of the codex median over a 5-round game. Regression pin: must be 1, not 2.
        # narrowed in AELDARI-DIAG-3 (2026-05-24)
        self.assertEqual(ab.heal_per_round, 1,
            "Yncarne heal_per_round was cut from 2 to 1 in AELDARI-DIAG-3 "
            "(2026-05-24) — see code/leaders.py comment for derivation")

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

    def test_farseer_has_no_wound_reroll(self):
        """wave 236 fab audit: Branching Fates is once-per-phase set-one-roll-to-6,
        NOT an always-on wound-reroll aura. reroll_wound_ones must be absent."""
        ab = lookup_ability("Farseer")
        self.assertIsNotNone(ab, "Farseer entry must remain in the registry")
        self.assertFalse(
            ab.reroll_wound_ones,
            "Farseer reroll_wound_ones was a fabricated always-on proxy — "
            "wave 236 audit removed it; the real Branching Fates is a "
            "once-per-phase set-one-roll-to-6 ability with no simulator field",
        )
        # All other offensive flags must also be off.
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)
        self.assertFalse(ab.reroll_hit_ones)
        self.assertEqual(ab.plus_one_attack, 0)
        # Registry entry must be retained (host_keys gating still needed).
        self.assertEqual(ab.aura_range, 6.0)

# ---------------------------------------------------------------------------
# iter21 fabrication-audit lock-ins — Marines leader aura proxies
# ---------------------------------------------------------------------------

class MarinesFabricationLockInTests(unittest.TestCase):
    """Lock-ins for the iter21 Marines leader fabrication audit. Each test
    asserts that a previously-fabricated offensive aura proxy is NOT
    present on the LeaderAbility. The real codex effect for each character
    is a CP-economy / battle-shock-removal mechanic that the simulator
    does NOT model as a damage-side aura — so the entries are deliberately
    flag-free below.

    These tests are tripwires: if someone re-adds a proxy aura flag
    without first wiring the real codex mechanic, the test fails and
    points at this audit comment.
    """

    def test_captain_no_offensive_aura_proxy(self):
        # Rites of Battle (Wahapedia /space-marines/Captain): "Once per
        # battle round, one unit from your army with this ability can use
        # it when its unit is targeted with a Stratagem. If it does,
        # reduce the CP cost of that use of that Stratagem by 1CP."
        # CP-discount on a Stratagem — NOT a +1-to-hit / reroll-1s aura.
        ab = lookup_ability("Captain")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_hit_ones,
            "Captain Rites of Battle is a Strat CP discount, not a "
            "reroll-1s aura — see iter21 fabrication audit.")
        self.assertFalse(ab.reroll_wound_ones)
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)
        self.assertEqual(ab.plus_one_attack, 0)
        self.assertEqual(ab.fnp, 7)
        self.assertEqual(ab.extra_invuln, 7)

    def test_chaplain_no_offensive_aura_proxy(self):
        # Spiritual Leader (Wahapedia /space-marines/Chaplain): "Once per
        # battle, at the start of any phase, you can select one friendly
        # ADEPTUS ASTARTES unit that is Battle-shocked and within 12\" of
        # this model. That unit is no longer Battle-shocked."
        # Battle-shock removal — NOT a reroll-wound-1s aura.
        ab = lookup_ability("Chaplain")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_wound_ones,
            "Chaplain Spiritual Leader is a once-per-battle Battle-shock "
            "removal, not a reroll-wound-1s aura — see iter21 audit.")
        self.assertFalse(ab.reroll_hit_ones)
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)
        self.assertEqual(ab.plus_one_attack, 0)

    def test_guilliman_author_of_codex_cp_only(self):
        # Author of the Codex (Wahapedia /space-marines/Roboute-Guilliman):
        # "While this model is on the battlefield, at the start of each of
        # your Command phases, you gain 1CP." Pure CP gain — no aura buff.
        # The faithful `cp_discount_per_round=1` mechanic is preserved;
        # the proxy `reroll_hit_ones=True` was dropped in iter21.
        ab = lookup_ability("Roboute Guilliman")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.cp_discount_per_round, 1,
            "Guilliman's Author of the Codex grants +1 CP per Command phase")
        self.assertFalse(ab.reroll_hit_ones,
            "Guilliman has NO reroll-1s aura in 10e — Author of the Codex "
            "is a pure CP gain. The proxy was dropped in iter21.")
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)

    def test_librarian_defensive_proxy_preserved(self):
        # Librarian's fnp=5 stays — it is the direction-correct DEFENSIVE
        # proxy for the codex's "FNP 4+ vs PSYCHIC attacks + 4+ invuln
        # from Mental Fortress (Psychic)". Both halves are defensive; the
        # proxy is strictly weaker and aligned-direction. iter21 audit
        # explicitly preserves this entry.
        ab = lookup_ability("Librarian")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.fnp, 5,
            "Librarian Mental Fortress is defensive — keep fnp=5 as the "
            "direction-correct proxy.")
        self.assertFalse(ab.plus_one_to_wound)
        self.assertFalse(ab.reroll_hit_ones)
        self.assertFalse(ab.reroll_wound_ones)

    def test_apothecary_narthecium_preserved(self):
        # Apothecary's revive_destroyed_per_round=1 is the faithful match
        # to the codex Narthecium rule and remains untouched.
        ab = lookup_ability("Apothecary")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.revive_destroyed_per_round, 1)
        self.assertEqual(ab.heal_per_round, 0)
        # No spurious offensive aura on the Apothecary.
        self.assertFalse(ab.reroll_hit_ones)
        self.assertFalse(ab.reroll_wound_ones)
        self.assertFalse(ab.plus_one_to_hit)
        self.assertFalse(ab.plus_one_to_wound)


# ---------------------------------------------------------------------------
# iter22 host_keys gating — faction-neutral structural lock-ins
# ---------------------------------------------------------------------------

class HostKeysGatingTests(unittest.TestCase):
    """Iter 22 fix: `effective_buffs` per-leader merge now consults
    `LeaderAbility.host_keys`. The codex Leader rule says a CHARACTER aura
    applies to the attached bodyguard squad ("While this model is leading
    a unit..."), NOT to every friendly within aura range. Pre-iter22,
    Typhus's Destroyer Hive FNP fired on every Death Guard unit within 6";
    same structural bug affected every faction's character auras.

    The fix: non-empty `host_keys` requires the attacker's UNIT_CATALOG
    key to be in the tuple. Empty `host_keys = ()` is the army-wide /
    broadcast aura convention (Hive Tyrant's Onslaught, Avatar's
    Bloody-Handed).

    Each test below builds a tiny army: ONE leader + TWO attackers, one
    that IS a legal bodyguard host and one that ISN'T. The host gate
    must let the aura through on the first and block it on the second.
    """

    # --- Faction-specific gated auras (non-empty host_keys) ------------------

    def _character(self, name: str) -> UnitProfile:
        return UnitProfile(
            name=name, health=4, damage=1, hit_probability=2 / 3,
            ap=-1, save=3, strength=4, toughness=4,
            unit_keywords=("INFANTRY", "CHARACTER"),
        )

    def _non_character(self, name: str) -> UnitProfile:
        return UnitProfile(
            name=name, health=2, damage=1, hit_probability=0.5,
            ap=0, save=4, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0,
            unit_keywords=("INFANTRY",),
        )

    def test_warboss_aura_only_buffs_boyz_host(self):
        # Warboss host_keys = ('orks_boyz', 'orks_nobz', 'orks_meganobz').
        # Buffs Boyz with melee-only +1-to-hit, not a non-host attacker.
        # ORKS-DIAG-3 (e52695f): Warboss "Might is Right" is melee-only;
        # the aura moved from plus_one_to_hit to plus_one_to_hit_melee_only.
        # plus_one_to_hit must be False for both host and non-host (regression
        # pin). plus_one_to_hit_melee_only must be True for Boyz, False for
        # the bystander. narrowed in ORKS-DIAG-3 (e52695f)
        leader = self._character("Warboss")
        boyz = self._non_character("Boyz")             # legal host
        bystander = self._non_character("Grunt")       # no catalog key
        army = _make_army(
            "Orks",
            [boyz, bystander, leader],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
        )
        boyz_buffs = effective_buffs(army.units[0])
        bystander_buffs = effective_buffs(army.units[1])
        self.assertTrue(boyz_buffs["plus_one_to_hit_melee_only"],
            "Warboss Might is Right (melee-only) must pass the gate for Boyz")
        self.assertFalse(bystander_buffs["plus_one_to_hit_melee_only"],
            "Warboss aura must NOT fire on a non-host bystander attacker")
        # Regression pins: the old over-broad proxy must stay False.
        self.assertFalse(boyz_buffs["plus_one_to_hit"],
            "Warboss plus_one_to_hit was audited to melee-only in ORKS-DIAG-3 "
            "(e52695f) — regression pin: must remain False even for Boyz")
        self.assertFalse(bystander_buffs["plus_one_to_hit"],
            "Warboss aura must NOT grant plus_one_to_hit to any attacker")

    def test_typhus_fnp_only_to_plague_marines(self):
        # Typhus host_keys = ('death_guard_plague_marines',). His
        # Destroyer Hive FNP 5+ proxy must apply ONLY to a Plague Marines
        # attacker, NOT to e.g. Poxwalkers or a hand-rolled grunt.
        # Pre-iter22, Typhus's FNP fired on every Death Guard unit within
        # 6" — the headline structural bug iter22 fixes.
        leader = self._character("Typhus")
        plague = self._non_character("Plague Marines")  # legal host
        bystander = self._non_character("Grunt")        # no catalog key
        army = _make_army(
            "DG",
            [plague, bystander, leader],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
        )
        plague_buffs = effective_buffs(army.units[0])
        bystander_buffs = effective_buffs(army.units[1])
        self.assertEqual(plague_buffs["fnp"], 5,
            "Typhus FNP must reach Plague Marines (the codex-led unit)")
        self.assertEqual(bystander_buffs["fnp"], 7,
            "Typhus FNP must NOT leak onto a non-host bystander — this "
            "is the iter22 structural bug fix")

    def test_overlord_grants_no_plus_one_to_hit(self):
        # Wave 235: the Overlord's plus_one_to_hit was a fabrication. The
        # real "My Will Be Done" is a once-per-round free-Stratagem ability
        # (a command-point discount), not a hit aura. The fabricated flag
        # was removed; this test is repurposed as a regression pin against
        # re-adding it (same pattern as test_dominus_aura_only_to_skitarii
        # below). See tests/test_necron_leaders_wave235.py for the full
        # removal coverage.
        leader = self._character("Overlord")
        warriors = self._non_character("Necron Warriors")   # legal host
        ctan = self._non_character("C'tan Shard of the Nightbringer")  # not in host_keys
        army = _make_army(
            "Necrons",
            [warriors, ctan, leader],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
        )
        warriors_buffs = effective_buffs(army.units[0])
        ctan_buffs = effective_buffs(army.units[1])
        self.assertFalse(warriors_buffs["plus_one_to_hit"],
            "Overlord must NOT grant +1-to-hit — My Will Be Done is a "
            "free-Stratagem ability, not a hit aura (wave 235 fabrication "
            "removal)")
        self.assertFalse(ctan_buffs["plus_one_to_hit"],
            "Overlord must NOT buff a non-leadable C'tan Shard")

    def test_dominus_aura_only_to_skitarii(self):
        # ADMECH-DIAG-3 (2026-05-26): Dominus reroll_hit_ones was a fabrication;
        # real "Lord of the Machine Cult" grants Feel No Pain 5+.
        # ADMECH-DIAG-6 (2026-05-26): Skitarii Vanguard and Rangers were removed
        # from Dominus's host_keys to fix broadcast over-application (the
        # proximity-broadcast model was firing Feel No Pain 5+ on all four
        # Skitarii squads simultaneously, far beyond the one-attached-unit rule).
        # host_keys now lists only Electro-Priests (who have native Feel No Pain 5+
        # making the Dominus aura a calibration no-op for them).
        # This test is repurposed: verify the Skitarii Vanguard name now falls
        # OUTSIDE host_keys (regression pin against re-adding the over-broadcast),
        # and that neither Skitarii nor bystander receive a reroll_hit_ones aura.
        # audited away in ADMECH-DIAG-3 + ADMECH-DIAG-6 (2026-05-26)
        leader = self._character("Tech-Priest Dominus")
        skitarii = self._non_character("Skitarii Vanguard")  # previously legal host; now outside host_keys
        bystander = self._non_character("Grunt")              # no catalog key
        army = _make_army(
            "AdMech",
            [skitarii, bystander, leader],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
        )
        ab = lookup_ability("Tech-Priest Dominus")
        self.assertIsNotNone(ab)
        self.assertNotIn("adeptus_mechanicus_skitarii_vanguard", ab.host_keys,
            "Skitarii Vanguard was removed from Dominus host_keys in "
            "ADMECH-DIAG-6 (2026-05-26) — regression pin")
        # reroll_hit_ones was the audited-away fabricated aura.
        skitarii_buffs = effective_buffs(army.units[0])
        bystander_buffs = effective_buffs(army.units[1])
        self.assertFalse(skitarii_buffs["reroll_hit_ones"],
            "Dominus reroll_hit_ones was audited away in ADMECH-DIAG-3 — "
            "must remain False for all attackers including Skitarii")
        self.assertFalse(bystander_buffs["reroll_hit_ones"],
            "Dominus aura must NOT grant reroll_hit_ones to any unit")

    def test_archon_aura_only_to_kabalites(self):
        # Archon host_keys = ('aeldari_drukhari_kabalite_warriors',).
        # DRK-DIAG-3 (2026-05-23): Archon's plus_one_to_hit was a fabrication.
        # "Hatred Eternal" is a Pain-token-gated Empower mechanic, not an
        # always-on +1-to-hit aura. The proxy was dropped (no offensive flag).
        # This test is repurposed: verify (a) the host_keys gate is intact
        # (regression pin against the proxy being re-added without the gate),
        # (b) no offensive flag leaks through regardless of host membership,
        # and (c) the entry still resolves (CLAUDE.md §13 fail-loud).
        # audited away in DRK-DIAG-3 (2026-05-23)
        leader = self._character("Archon")
        kabalites = self._non_character("Kabalite Warriors")  # legal host
        bystander = self._non_character("Grunt")              # no catalog key
        army = _make_army(
            "Drukhari",
            [kabalites, bystander, leader],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
        )
        ab = lookup_ability("Archon")
        self.assertIsNotNone(ab, "Archon must remain in the registry (CLAUDE.md §13)")
        self.assertEqual(ab.host_keys, ("aeldari_drukhari_kabalite_warriors",),
            "Archon host_keys must stay intact for future restoration when "
            "Pain-token economy is modelled — DRK-DIAG-3 regression pin")
        # The audit removed the offensive flag — neither host nor bystander
        # should receive any offensive buff from the Archon currently.
        kabalite_buffs = effective_buffs(army.units[0])
        bystander_buffs = effective_buffs(army.units[1])
        self.assertFalse(kabalite_buffs["plus_one_to_hit"],
            "Archon plus_one_to_hit was audited away in DRK-DIAG-3 (2026-05-23) "
            "— regression pin: must remain False for all attackers")
        self.assertFalse(bystander_buffs["plus_one_to_hit"],
            "Archon aura must NOT reach a non-host bystander")

    def test_lord_of_contagion_aura_only_to_terminator_bodyguards(self):
        # iter24-D1: Lord of Contagion host_keys was corrected to
        # ('death_guard_blightlord_terminators',
        #  'death_guard_deathshroud_terminators') per the Wahapedia
        # datasheet Bodyguard list — Plague Marines are NOT a legal
        # bodyguard. Plus_one_to_wound must pass the host gate exactly
        # once — to the Blightlord Terminators attacker. (The
        # first_stratagem_free_per_round field is a Warlord-trait
        # CP-econ flag, not consumed here.)
        leader = self._character("Lord of Contagion")
        blightlord = self._non_character("Blightlord Terminators")  # legal host
        bystander = self._non_character("Grunt")                    # no catalog key
        army = _make_army(
            "DG",
            [blightlord, bystander, leader],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
        )
        blightlord_buffs = effective_buffs(army.units[0])
        bystander_buffs = effective_buffs(army.units[1])
        self.assertTrue(blightlord_buffs["plus_one_to_wound"],
            "Lord of Contagion aura must reach Blightlord Terminators")
        self.assertFalse(bystander_buffs["plus_one_to_wound"],
            "Lord of Contagion aura must NOT reach a non-host bystander")

    # --- Army-wide / broadcast auras (empty host_keys) ----------------------

    def test_hive_tyrant_aura_applies_army_wide(self):
        # Hive Tyrant Onslaught (Wahapedia /tyranids/Hive-Tyrant): "While
        # a friendly TYRANIDS unit is within 6" of this model, ranged
        # weapons equipped by models in that unit have the [ASSAULT] and
        # [LETHAL HITS] abilities." — broadcast aura, NO led-unit gate.
        # iter22: host_keys widened to () so `effective_buffs` applies
        # the proxy to any Tyranids attacker in range regardless of whether
        # it's a formal Hive Tyrant bodyguard.
        # TYRANIDS-DIAG-7 (2026-05-26): reroll_wound_ones proxy was removed.
        # The real Onslaught rule grants [LETHAL HITS] on ranged only;
        # reroll_wound_ones over-applied to melee and was the wrong mechanic.
        # The entry now ships NO-FLAG + host_keys=() (same structural pattern
        # as Avatar of Khaine / Autarch / Custodes Blade Champion). The
        # reroll_wound_ones assertions are flipped to assertFalse regression
        # pins. host_keys must remain empty (broadcast convention). The test
        # retains its army-wide structure to lock in that the broadcast
        # convention (host_keys=()) still holds even after the flag drop.
        # audited away in TYRANIDS-DIAG-7 (2026-05-26)
        ab = lookup_ability("Hive Tyrant")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.host_keys, (),
            "Hive Tyrant codex aura is broadcast — host_keys must be empty")
        self.assertFalse(ab.reroll_wound_ones,
            "Hive Tyrant reroll_wound_ones was audited away in TYRANIDS-DIAG-7 "
            "(2026-05-26) — regression pin: must remain False")

        leader_p = UnitProfile(
            name="Hive Tyrant", health=12, damage=4, hit_probability=2 / 3,
            ap=-2, save=2, strength=10, toughness=9,
            unit_keywords=("MONSTER", "CHARACTER", "EPIC HERO"),
        )
        # Two unrelated Tyranids attackers — gants, warriors — both
        # within 6" of the Tyrant. host_keys=() means the gate is skipped
        # for every attacker — but since the aura carries no flag, no buff
        # is received.
        gant = self._non_character("Termagants")
        warrior = self._non_character("Tyranid Warriors with Melee Bio-Weapons")
        scratch = self._non_character("Grunt")    # no catalog key
        army = _make_army(
            "Tyranids",
            [gant, warrior, scratch, leader_p],
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)],
        )
        # None of the three attackers should receive reroll_wound_ones now
        # that the proxy flag was audited away. These assertions serve as
        # regression pins against the flag being re-added without the
        # matching [LETHAL HITS] ranged-only plumbing.
        self.assertFalse(effective_buffs(army.units[0])["reroll_wound_ones"],
            "Hive Tyrant reroll_wound_ones must not apply to Termagants after "
            "TYRANIDS-DIAG-7 audit — regression pin")
        self.assertFalse(effective_buffs(army.units[1])["reroll_wound_ones"],
            "Hive Tyrant reroll_wound_ones must not apply to Tyranid Warriors "
            "after TYRANIDS-DIAG-7 audit — regression pin")
        self.assertFalse(effective_buffs(army.units[2])["reroll_wound_ones"],
            "Hive Tyrant reroll_wound_ones must not apply to any attacker "
            "after TYRANIDS-DIAG-7 audit — regression pin")

    def test_avatar_of_khaine_host_keys_empty(self):
        # Avatar of Khaine — codex "While a friendly AELDARI unit is
        # within 6"" — broadcast wording, host_keys=(). The registry
        # entry carries no offensive flags after iter21, so the aura
        # is a structural placeholder; this test just locks in that
        # the host_keys remain empty (iter22 broadcast convention).
        ab = lookup_ability("Avatar of Khaine")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.host_keys, (),
            "Avatar of Khaine codex aura is broadcast — host_keys must "
            "be empty per the iter22 convention")

    def test_yncarne_host_keys_empty(self):
        # The Yncarne — MONSTER, no formal Leader attachment in 10e.
        # heal_per_round is applied via apply_round_end_healing, not
        # effective_buffs, so the host_keys field doesn't gate any aura
        # buff. Still lock in that host_keys is empty so future code that
        # might wire an offensive flag onto Yncarne handles the broadcast
        # case correctly.
        ab = lookup_ability("The Yncarne")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.host_keys, (),
            "The Yncarne is a MONSTER with no Leader attachment — "
            "host_keys must be empty (iter22 broadcast convention)")


class HostKeysGatingFlaggedTests(unittest.TestCase):
    """iter22 flags (NOT in scope for this iteration, but recorded so the
    next pass can pick them up). These are LeaderAbility entries where
    `host_keys=()` (empty, currently treated as broadcast) but the codex
    wording is "While this model is leading a unit..." — meaning the
    correct iter22 behaviour would be a non-empty host_keys tuple.

    Each test below is `expectedFailure`-marked and serves purely as a
    machine-readable TODO. Removing the decorator + adding the right
    host_keys to the registry entry is the follow-up fix.
    """

    @unittest.expectedFailure
    def test_commander_in_battlesuit_has_proper_host_keys(self):
        # T'au "Commander in <variant> Battlesuit" — per the Wahapedia
        # Coldstar Commander datasheet
        # (https://wahapedia.ru/wh40k10ed/factions/t-au-empire/Commander-In-Coldstar-Battlesuit):
        # "While this model is leading a unit, models in that unit have a
        # Move characteristic of 12" and ranged weapons equipped by models
        # in that unit have the [ASSAULT] ability."
        # The "While this model is leading a unit" wording requires a
        # non-empty host_keys (Crisis Battlesuit / Stealth Battlesuit
        # squads per the codex Leader block). The current entry leaves
        # host_keys empty, which iter22 will now treat as ARMY-WIDE
        # broadcast — strictly stronger than the codex's led-unit-only
        # plus_one_to_hit proxy. Flagged for follow-up.
        ab = lookup_ability("Commander in XV85 Enforcer Battlesuit")
        self.assertNotEqual(ab.host_keys, (),
            "Commander in <Battlesuit>'s codex aura is led-unit-gated. "
            "host_keys=() is the broadcast convention — should be "
            "(crisis_battlesuit, stealth_battlesuit) per the 10e codex "
            "Leader block.")


class CoordinatedFirePlanFidelityTests(unittest.TestCase):
    """Wave 212 — the T'au "Coordinated Fire Plan" (Commander in Battlesuit /
    Coldstar) is faithful by default: it grants NO Hit-roll bonus. The real
    rule (cited verbatim in LeaderAbility.Coordinated Fire Plan) grants the led
    unit a Move characteristic of 12" and the [ASSAULT] ability on its ranged
    weapons — neither of which the simulator models — so the faithful default
    is offensively inert rather than the prior fabricated army-wide +1 to Hit.
    The fabricated proxy is reachable only via SWEG_TAU_CMD=0 for the A/B."""

    def test_default_grants_no_fabricated_hit_bonus(self):
        # Default registry (SWEG_TAU_CMD unset/on): the fabrication is gone.
        ab = lookup_ability("Commander in XV85 Enforcer Battlesuit")
        self.assertIsNotNone(ab, "Commander in <Battlesuit> must remain in the registry")
        self.assertFalse(
            ab.plus_one_to_hit,
            "Coordinated Fire Plan must NOT grant +1 to Hit by default — the real "
            "rule is [ASSAULT] + Move 12\" to the led unit, no Hit bonus (wave 212).",
        )


class CsmLeaderWave237Tests(unittest.TestCase):
    """Wave 237 — three new Chaos Space Marines leader entries.

    Master of Possession and Warpsmith have no expressible led-unit aura in the
    current LeaderAbility schema (their abilities are Movement-phase roll modifiers
    and Command-phase vehicle-targeting abilities respectively). Their registry
    entries exist solely so lookup_ability returns non-None per CLAUDE.md rule 13
    (fail loud on missing data).

    Dark Commune grants a 5+ invulnerable save (extra_invuln=5) to its led unit
    via Faithful Flock (always active while a Cult Demagogue model is present in
    the Dark Commune unit).
    """

    def test_master_of_possession_resolves(self):
        ab = lookup_ability("Master of Possession")
        self.assertIsNotNone(
            ab,
            "Master of Possession must resolve via lookup_ability — CLAUDE.md rule 13",
        )
        self.assertEqual(
            ab.name, "Daemonkin (Psychic)",
            "Master of Possession ability name must be 'Daemonkin (Psychic)'",
        )

    def test_master_of_possession_no_offensive_aura(self):
        # Daemonkin (Psychic) is an Advance/Charge roll modifier; Sacrificial Dagger
        # is a self-activation once-per-phase buff — neither is a led-unit aura.
        ab = lookup_ability("Master of Possession")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_hit_ones,       "Master of Possession has no hit-reroll aura")
        self.assertFalse(ab.plus_one_to_hit,       "Master of Possession has no +1 to Hit aura")
        self.assertFalse(ab.plus_one_to_wound,     "Master of Possession has no +1 to Wound aura")
        self.assertEqual(ab.extra_invuln, 7,       "Master of Possession confers no invuln aura")
        self.assertEqual(ab.fnp, 7,                "Master of Possession confers no feel no pain aura")
        # Structural check: registry entry is present (aura_range set)
        self.assertEqual(ab.aura_range, 6.0)

    def test_master_of_possession_host_keys(self):
        ab = lookup_ability("Master of Possession")
        self.assertIsNotNone(ab)
        self.assertIn("chaos_space_marines_chosen",      ab.host_keys)
        self.assertIn("chaos_space_marines_legionaries", ab.host_keys)
        self.assertIn("chaos_space_marines_possessed",   ab.host_keys)

    def test_warpsmith_resolves(self):
        ab = lookup_ability("Warpsmith")
        self.assertIsNotNone(
            ab,
            "Warpsmith must resolve via lookup_ability — CLAUDE.md rule 13",
        )
        self.assertEqual(
            ab.name, "Master of Mechanisms",
            "Warpsmith ability name must be 'Master of Mechanisms'",
        )

    def test_warpsmith_no_offensive_aura(self):
        # All Warpsmith abilities target the Warpsmith itself or a nearby Vehicle —
        # none are led-unit aura buffs expressible in the current LeaderAbility schema.
        ab = lookup_ability("Warpsmith")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.reroll_hit_ones,       "Warpsmith has no hit-reroll aura")
        self.assertFalse(ab.plus_one_to_hit,       "Warpsmith has no +1 to Hit aura")
        self.assertFalse(ab.plus_one_to_wound,     "Warpsmith has no +1 to Wound aura")
        self.assertEqual(ab.extra_invuln, 7,       "Warpsmith confers no invuln aura")
        self.assertEqual(ab.fnp, 7,                "Warpsmith confers no feel no pain aura")
        self.assertEqual(ab.heal_per_round, 0,     "Warpsmith has no round-end heal (vehicle repair is not wired)")
        self.assertEqual(ab.aura_range, 6.0)

    def test_warpsmith_host_keys(self):
        ab = lookup_ability("Warpsmith")
        self.assertIsNotNone(ab)
        self.assertIn("chaos_space_marines_chosen",      ab.host_keys)
        self.assertIn("chaos_space_marines_havocs",      ab.host_keys)
        self.assertIn("chaos_space_marines_legionaries", ab.host_keys)

    def test_dark_commune_resolves(self):
        ab = lookup_ability("Dark Commune")
        self.assertIsNotNone(
            ab,
            "Dark Commune must resolve via lookup_ability — CLAUDE.md rule 13",
        )
        self.assertEqual(
            ab.name, "Faithful Flock",
            "Dark Commune ability name must be 'Faithful Flock'",
        )

    def test_dark_commune_grants_invuln_five(self):
        # Faithful Flock: "models in that unit have a 5+ invulnerable save."
        # The Cult Demagogue is always present in the Dark Commune unit, so
        # extra_invuln=5 is the correct unconditional grant.
        ab = lookup_ability("Dark Commune")
        self.assertIsNotNone(ab)
        self.assertEqual(
            ab.extra_invuln, 5,
            "Dark Commune Faithful Flock must grant extra_invuln=5 to the led unit",
        )

    def test_dark_commune_no_dark_ritual_proxy(self):
        # Dark Ritual is once-per-battle on the Dark Commune's own attacks only;
        # it must NOT be proxied as an always-on hit/wound aura.
        ab = lookup_ability("Dark Commune")
        self.assertIsNotNone(ab)
        self.assertFalse(ab.plus_one_to_hit,   "Dark Ritual must not be proxied as a permanent +1 to Hit aura")
        self.assertFalse(ab.plus_one_to_wound, "Dark Ritual must not be proxied as a permanent +1 to Wound aura")
        self.assertEqual(ab.fnp, 7,            "Dark Commune confers no feel no pain aura")

    def test_dark_commune_host_keys(self):
        ab = lookup_ability("Dark Commune")
        self.assertIsNotNone(ab)
        self.assertIn("chaos_space_marines_accursed_cultists", ab.host_keys)
        self.assertIn("chaos_space_marines_cultist_mob",       ab.host_keys)

    def test_dark_commune_invuln_applies_via_effective_buffs(self):
        """Functional: Dark Commune's 5+ invuln merges into effective_buffs for
        the led Cultist Mob unit when the leader is within aura range."""
        # Create a Cultist Mob attacker with the correct catalogue name so the
        # host_keys gate passes (_name_to_catalog_keys("Cultist Mob") returns
        # "chaos_space_marines_cultist_mob" which is in Dark Commune.host_keys).
        army = _make_army(
            "csm_test",
            [
                _grunt_profile(name="Cultist Mob"),
                UnitProfile(
                    name="Dark Commune",
                    health=4, damage=1, hit_probability=0.5,
                    ap=0, save=6, strength=3, toughness=3,
                    attacks=1, weapon_damage_per_shot=1.0,
                    unit_keywords=("INFANTRY", "CHARACTER"),
                ),
            ],
            [(12.0, 12.0), (12.0, 12.0)],
        )
        attacker = army.units[0]
        buffs = effective_buffs(attacker)
        self.assertEqual(
            buffs["extra_invuln"], 5,
            "Dark Commune Faithful Flock must grant extra_invuln=5 to the led Cultist Mob",
        )


if __name__ == "__main__":
    unittest.main()
