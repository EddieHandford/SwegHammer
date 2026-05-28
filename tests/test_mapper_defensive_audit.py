"""Defensive-audit regression tests (task #142).

Three classes of units were losing their canonical defensive characteristics
at the BSData → MappedUnit mapping step. The Phase 3 defensive audit caught
this and bypassed via in-memory `dataclasses.replace()` patches in the test
catalogue, but production sim battles still used the broken values. These
tests verify the fix sticks:

  - Plague Marines: FNP 5+ (army rule "Disgustingly Resilient", encoded as
    an `overrides.json` entry because the rule is codex-level army-wide and
    not visible on individual BSData datasheets).
  - All 31 Adeptus Custodes datasheets: 4++ (or 5++ for a handful of vehicle
    variants), recovered by the mapper now reading the linked Invuln-Save
    profile's Description characteristic — Custodes BSData encodes the
    digit there rather than in the infoLink name.
  - Wraithguard / Wraithblades: 4++ via `overrides.json` because BSData does
    not encode an Invuln-Save infoLink on either datasheet (verified by
    walking the entry tree).

Citations live in `data/overrides.json` and the mapper's `extract_invuln`
docstring. Wahapedia URLs are also in the override notes.
"""

from __future__ import annotations

import unittest

from code.units import UNIT_CATALOG


# Custodes datasheets that the catalogue exposes, paired with their canonical
# Invuln save value. Sourced from
# https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/ — the "Wisdom of
# the Aeons" wording on individual datasheets specifies 4+ for most infantry
# and bike units, 5+ for several vehicles and dreadnoughts, and 4+ for the
# named characters. Two outliers (Aleya, Knight-Centura) carry 5+. These
# expected values are pulled from each datasheet's Invulnerable Save
# Description characteristic in BSData (verified at v10.6.0).
_EXPECTED_CUSTODES_INVULN = {
    "adeptus_custodes_allarus_custodians": 4,
    "adeptus_custodes_custodian_guard": 4,
    "adeptus_custodes_aleya": 5,
    "adeptus_custodes_anathema_psykana_rhino": 7,  # Rhino transport — no invuln
    "adeptus_custodes_blade_champion": 4,
    "adeptus_custodes_custodian_wardens": 4,
    "adeptus_custodes_knight_centura": 5,
    "adeptus_custodes_prosecutors": 7,    # Sisters of Silence — no invuln on datasheet
    "adeptus_custodes_shield_captain": 4,
    "adeptus_custodes_shield_captain_in_allarus_terminator_armour": 4,
    "adeptus_custodes_shield_captain_on_dawneagle_jetbike": 4,
    "adeptus_custodes_trajann_valoris": 4,
    "adeptus_custodes_valerian": 4,
    "adeptus_custodes_venerable_contemptor_dreadnought": 5,
    "adeptus_custodes_venerable_land_raider": 7,    # Land Raider transport — no invuln
    "adeptus_custodes_vertus_praetors": 4,
    "adeptus_custodes_vigilators": 7,    # Sisters of Silence — no invuln
    "adeptus_custodes_witchseekers": 7,    # Sisters of Silence — no invuln
    "adeptus_custodes_custodian_guard_with_adrasite_and_pyrithite_spears": 4,
    "adeptus_custodes_sagittarum_custodians": 4,
    "adeptus_custodes_aquilon_custodians": 4,
    "adeptus_custodes_agamatus_custodians": 4,
    "adeptus_custodes_venatari_custodians": 4,
    "adeptus_custodes_contemptor_galatus_dreadnought": 4,
    "adeptus_custodes_contemptor_achillus_dreadnought": 5,
    "adeptus_custodes_pallas_grav_attack": 5,
    "adeptus_custodes_caladius_grav_tank": 5,
    "adeptus_custodes_telemon_heavy_dreadnought": 4,
    "adeptus_custodes_coronus_grav_carrier": 5,
    "adeptus_custodes_ares_gunship": 5,
    "adeptus_custodes_orion_assault_dropship": 5,
    # Crucible-detachment datasheets added on BSData main (post-v10.6.0).
    # Now parsed correctly by the wave-48 mapper invuln-prose-walk fix
    # (Shape 3 on extract_invuln). Null Maiden Crucible carries a 5+
    # ability profile in BSData even though the standard Null Maiden has
    # no invuln — appears to be a detachment-specific grant; Wahapedia
    # has not indexed the Crucible detachment yet so BSData is the
    # source of truth for now.
    "adeptus_custodes_kataphraktoi_exemplar_crucible": 4,
    "adeptus_custodes_guardian_of_the_throne_crucible": 4,
    "adeptus_custodes_null_maiden_crucible": 5,
}


class PlagueMarinesFNPTests(unittest.TestCase):
    """Death Guard Plague Marines have FNP 5+ via Disgustingly Resilient."""

    def test_plague_marines_have_fnp_5(self):
        u = UNIT_CATALOG["death_guard_plague_marines"]
        self.assertEqual(
            u.fnp,
            5,
            f"Plague Marines should have FNP 5+ via Disgustingly Resilient; "
            f"got {u.fnp}. Check data/overrides.json.",
        )

    def test_csm_plague_marines_have_fnp_5(self):
        """Cross-codex BSData listing also gets the FNP override."""
        u = UNIT_CATALOG["chaos_space_marines_plague_marines"]
        self.assertEqual(u.fnp, 5)


class CustodesInvulnTests(unittest.TestCase):
    """All 31 Adeptus Custodes datasheets carry their canonical invuln.

    Parametrised by hand — there's no `subTest` overhead, and the failure
    message identifies the specific unit that diverged. Three Custodes
    "datasheets" are actually transports or non-Custodes Sisters of
    Silence units with no invuln on their datasheet; those are explicitly
    listed with expected=7 (no invuln) so the test serves as a fixed-point
    check rather than a "everyone gets 4+" rubber stamp.
    """

    def test_custodes_all_have_4plus_invuln(self):
        # Verify every Custodes key in the catalogue is accounted for in
        # the expected map — otherwise BSData added a new datasheet and the
        # test silently passes a unit we don't actually check.
        custodes_keys_in_catalog = {
            k for k in UNIT_CATALOG
            if k.startswith("adeptus_custodes_")
            and k != "adeptus_custodes_detachments"
        }
        missing_from_expected = (
            custodes_keys_in_catalog - set(_EXPECTED_CUSTODES_INVULN)
        )
        self.assertFalse(
            missing_from_expected,
            f"Custodes datasheets in catalogue but not in test expectations: "
            f"{sorted(missing_from_expected)}",
        )
        for key, expected in _EXPECTED_CUSTODES_INVULN.items():
            if key not in UNIT_CATALOG:
                continue   # tolerate catalogue trims
            actual = UNIT_CATALOG[key].invuln_save
            self.assertEqual(
                actual,
                expected,
                f"{key}: expected invuln_save={expected}, got {actual}",
            )

    def test_custodes_with_4plus_count_at_least_15(self):
        """The 4+ Custodes population is the bulk of the codex.

        Sanity floor: at least 15 of the 31 Custodes datasheets have invuln=4.
        Catches regressions where the mapper's profile-following path breaks
        for a subset of datasheets (e.g. one shared Invuln profile changes
        shape upstream). The 17/31 figure at v10.6.0 mostly covers the
        infantry / jetbike / character lines; the rest are 5+ vehicles or
        non-Custodes transports.
        """
        fours = [
            k for k in UNIT_CATALOG
            if k.startswith("adeptus_custodes_")
            and UNIT_CATALOG[k].invuln_save == 4
        ]
        self.assertGreaterEqual(
            len(fours),
            15,
            f"Only {len(fours)} Custodes datasheets show invuln=4; expected >= 15. "
            f"Check code/bsdata/mapper.py extract_invuln.",
        )


class WraithguardInvulnTests(unittest.TestCase):
    """Wraithguard and Wraithblades have a 4++ via overrides."""

    def test_wraithguard_has_4plus_invuln(self):
        u = UNIT_CATALOG["aeldari_craftworlds_wraithguard"]
        self.assertEqual(
            u.invuln_save,
            4,
            f"Wraithguard should have a 4+ invulnerable save; got {u.invuln_save}. "
            f"Check data/overrides.json.",
        )

    def test_wraithblades_has_4plus_invuln(self):
        u = UNIT_CATALOG["aeldari_craftworlds_wraithblades"]
        self.assertEqual(u.invuln_save, 4)


# iter20: BSData per-variant infoLink encoding gaps. The Sunforge variant of
# the Crisis Battlesuit datasheet carries the Invulnerable-Save infoLink in
# BSData v10.6.0, but its Fireknife / Starscythe siblings do not — even
# though all three share the Battlesuit Shield Generator (4++) per Wahapedia.
# Same shape: Commander variants, Death Guard / Necron melee elites.
# Pinned via overrides until BSData encodes the infoLinks (or we extend the
# mapper with a keyword-based fallback table). See data/overrides.json
# `iter20` notes for the per-unit citation.
ITER20_VARIANT_INVULN_EXPECTATIONS = [
    ("t_au_empire_crisis_fireknife_battlesuits", 4),
    ("t_au_empire_crisis_starscythe_battlesuits", 4),
    ("t_au_empire_crisis_sunforge_battlesuits", 4),    # via mapper (BSData has it)
    ("t_au_empire_commander_in_enforcer_battlesuit", 4),
    ("t_au_empire_commander_in_coldstar_battlesuit", 4),
    ("death_guard_deathshroud_terminators", 4),
    ("death_guard_blightlord_terminators", 4),
    ("necrons_lychguard", 4),
]


class Iter20VariantInvulnTests(unittest.TestCase):
    """Pin invulns added in iter20 against the BSData per-variant gap.

    See `data/overrides.json` `iter20:` notes for full citation chain.
    """

    def test_iter20_variant_invulns(self):
        for key, expected in ITER20_VARIANT_INVULN_EXPECTATIONS:
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


# Wave 47/48 mapper invuln-prose-walk fix (Shape 3).
#
# Before this fix, BSData encoded the invuln save as an inline
# <profile typeName="Abilities" name="Invulnerable Save"> on the selection
# entry — with the digit in its Description characteristic — for every unit
# in Chaos Daemons Library, Dark Angels, Library - Titans (Chaos Titans),
# Deathwatch, and several Aeldari characters. The mapper's earlier
# `extract_invuln` walked only infoLinks, so these all fell through to the
# loader's default of 7 (no invuln). Wave 47 audits found 20 such entries
# across 5 faction catalogues and patched them via
# `data/codex_corrections_10e.json`. The wave-48 mapper fix extends
# `extract_invuln` to also walk inline Abilities profiles whose name
# starts with "invulnerable save", retiring all 20 corrections in one pass.
WAVE47_SHAPE3_INVULN_EXPECTATIONS = [
    # Dark Angels (Imperium - Dark Angels .cat).
    ("dark_angels_azrael", 4),
    ("dark_angels_lion_el_jonson", 3),   # The Emperor's Shield
    ("dark_angels_belial", 4),
    ("dark_angels_asmodai", 4),
    ("dark_angels_sammael", 4),
    ("dark_angels_ezekiel", 4),
    ("dark_angels_deathwing_knights", 4),
    ("dark_angels_ravenwing_black_knights", 5),
    # Chaos Daemons (Chaos - Chaos Daemons Library .cat).
    ("chaos_daemons_library_bloodthirster", 4),
    ("chaos_daemons_library_lord_of_change", 4),
    ("chaos_daemons_library_great_unclean_one", 4),
    ("chaos_daemons_library_keeper_of_secrets", 4),
    ("chaos_daemons_library_skarbrand", 4),
    ("chaos_daemons_library_bloodletters", 5),
    ("chaos_daemons_library_karanak", 4),
    # Chaos Titans (Library - Titans .cat, surfaced via Titanicus Traitoris).
    # 5+ Ion Shield against ranged attacks only — modelled globally per the
    # mapper's "approximate but on the correct side" convention.
    ("titanicus_traitoris_warhound_titan", 5),
    ("titanicus_traitoris_reaver_titan", 5),
    ("titanicus_traitoris_warbringer_nemesis_titan", 5),
    ("titanicus_traitoris_warlord_titan", 5),
    # Deathwatch (Imperium - Deathwatch .cat).
    ("deathwatch_watch_master", 4),
    # Aeldari characters with parenthesised inline profile names (e.g.
    # "Invulnerable Save (Yvraine)"). Shape 3's name filter matches the
    # "invulnerable save" prefix so these are picked up correctly.
    ("aeldari_ynnari_yvraine", 4),
    ("aeldari_ynnari_the_visarch", 4),
    ("aeldari_craftworlds_autarch", 4),
]


class Wave47Shape3InvulnTests(unittest.TestCase):
    """Pin the wave-48 mapper invuln-prose-walk fix.

    Each entry below must parse with the listed invuln via the mapper
    alone — none of these keys carry an `invuln_save` correction in
    `data/codex_corrections_10e.json` or an `invuln_save` field in
    `data/overrides.json` once the mapper fix has landed. A regression in
    `extract_invuln` (e.g. Shape 3 filter narrowed too far) would surface
    here as 7+ on the affected catalogue.
    """

    def test_wave47_shape3_invuln_extraction(self):
        for key, expected in WAVE47_SHAPE3_INVULN_EXPECTATIONS:
            with self.subTest(unit=key):
                self.assertIn(
                    key,
                    UNIT_CATALOG,
                    f"{key} missing from catalogue — wave-47 audit target gone",
                )
                got = UNIT_CATALOG[key].invuln_save
                self.assertEqual(
                    got,
                    expected,
                    f"{key} invuln_save={got}, expected {expected}+ via mapper "
                    f"Shape 3 (inline <profile typeName='Abilities'>)",
                )


if __name__ == "__main__":
    unittest.main()
