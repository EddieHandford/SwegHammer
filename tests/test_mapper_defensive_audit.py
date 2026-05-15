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
        u = UNIT_CATALOG["aeldari_aeldari_library_wraithguard"]
        self.assertEqual(
            u.invuln_save,
            4,
            f"Wraithguard should have a 4+ invulnerable save; got {u.invuln_save}. "
            f"Check data/overrides.json.",
        )

    def test_wraithblades_has_4plus_invuln(self):
        u = UNIT_CATALOG["aeldari_aeldari_library_wraithblades"]
        self.assertEqual(u.invuln_save, 4)


if __name__ == "__main__":
    unittest.main()
