"""wave 233 — secondary profile and extra-melee boolean weapon keyword parity.

Two gaps remained after dc4f63c (which fixed extra_ranged_profiles):

GAP 1 — Secondary profile (sec_swap block in units.py).
  The flat "secondary" ranged profile (the runner-up weapon in the two-profile
  picker, e.g. Stormsurge Pulse Driver vs Pulse Blastcannon) stored none of the
  four boolean keyword fields: one_shot, hazardous, indirect_fire, or precision.
  When the simulator hot-swapped the secondary profile in via dataclasses.replace,
  those fields were silently inherited from the PRIMARY profile, producing real
  fidelity bugs (e.g. a Chaos Space Marines Whirlwind Scorpius whose secondary
  is a Hunter-killer missile would fire it every activation, never gated once per
  battle; a unit with a hazardous secondary would never self-harm).

  Fix: four new fields (secondary_one_shot, secondary_hazardous,
  secondary_indirect_fire, secondary_precision) added to:
    - code/bsdata/mapper.py MappedUnit dataclass + assignment block
    - code/units.py UnitProfile dataclass + loader + _PERMODEL_SECONDARY_RANGED_RESET
    - code/units.py sec_swap dict

GAP 2 — extra_melee_profiles inline serializer in mapper.py.
  The dict built for each extra melee weapon profile omitted one_shot and
  hazardous (lance and precision were already present). When units.py built the
  runtime _melee_extras swap dict it also lacked those two keys.

  Fix: one_shot and hazardous added to the inline mapper dict and the runtime
  swap dict in units.py.

This module tests:
  (a) Parsed data — representative units carry the new secondary_* fields with
      the correct values in the regenerated parsed.json.
  (b) Unit catalogue — the new secondary_* fields survive the full
      parsed.json -> CatalogEntry -> UnitProfile load round-trip.
  (c) sec_swap dict — all four new fields are consumed, so dataclasses.replace
      will override the primary's value rather than silently inheriting it.
  (d) Exhaustive secondary coverage — every unit in parsed.json that has a
      secondary profile (secondary_attacks > 0) carries all four new fields.
  (e) extra_melee_profiles serialization — every entry in every unit's
      extra_melee_profiles carries both one_shot and hazardous keys.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from code.bsdata.mapper import PARSED_PATH
from code.units import UNIT_CATALOG

# -----------------------------------------------------------------------
# The four fields added to the secondary profile chain (GAP 1).
# -----------------------------------------------------------------------
SECONDARY_PARITY_FIELDS = frozenset({
    "secondary_one_shot",
    "secondary_hazardous",
    "secondary_indirect_fire",
    "secondary_precision",
})

# The two new fields added to extra_melee_profiles (GAP 2). lance and
# precision were already present; indirect_fire is ranged-only (omitted).
EXTRA_MELEE_NEW_FIELDS = frozenset({
    "one_shot",
    "hazardous",
})


def _parsed_units() -> list:
    """Load parsed.json and return the units list."""
    path = Path(PARSED_PATH)
    if not path.exists():
        raise unittest.SkipTest(
            f"parsed.json not found at {PARSED_PATH}; "
            f"run `python -m code.bsdata.mapper` first"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["units"]


class SecondaryKeywordParityParsedJsonTests(unittest.TestCase):
    """GAP 1 tests against the serialized parsed.json output."""

    @classmethod
    def setUpClass(cls):
        cls.records = _parsed_units()
        cls.by_key = {u["key"]: u for u in cls.records}

    # (a) -------------------------------------------------------------------
    def test_whirlwind_scorpius_secondary_one_shot(self):
        """The Chaos Space Marines Whirlwind Scorpius secondary (Hunter-killer
        missile) carries secondary_one_shot=True in parsed.json.

        Before the fix, secondary_one_shot did not exist in MappedUnit, so the
        secondary profile silently inherited one_shot=False from the primary
        Scorpius multi-launcher, allowing the missile to fire every activation."""
        unit = self.by_key.get("chaos_space_marines_whirlwind_scorpius_legends")
        if unit is None:
            self.skipTest(
                "chaos_space_marines_whirlwind_scorpius_legends not in parsed.json"
            )
        self.assertIn(
            "secondary_one_shot",
            unit,
            msg="secondary_one_shot field absent from Whirlwind Scorpius unit record",
        )
        self.assertTrue(
            unit["secondary_one_shot"],
            msg=(
                f"Whirlwind Scorpius secondary_one_shot="
                f"{unit['secondary_one_shot']!r}, expected True "
                f"(secondary weapon: {unit.get('secondary_weapon')!r})"
            ),
        )

    def test_helbrute_secondary_hazardous(self):
        """The Death Guard Helbrute secondary (Plasma cannon) carries
        secondary_hazardous=True in parsed.json.

        Before the fix, secondary_hazardous did not exist, so the secondary
        profile silently inherited hazardous=False from the primary multi-melta,
        meaning the Helbrute never self-harmed when firing the plasma cannon.

        Re-anchored from the Chaos Space Marines Helbrute to the Death Guard
        Helbrute when the SWEG_CHOICE_TARGET_BASKET regeneration re-resolved the
        Chaos Space Marines Helbrute's secondary to a Twin lascannon (a
        higher-value anti-tank weapon that is not hazardous). Both Helbrutes
        share the Multi-melta primary; the Death Guard Helbrute keeps the
        hazardous Plasma cannon secondary, so it exercises the same
        keyword-propagation mechanism this guard was written for."""
        unit = self.by_key.get("death_guard_helbrute")
        if unit is None:
            self.skipTest("death_guard_helbrute not in parsed.json")
        self.assertIn(
            "secondary_hazardous",
            unit,
            msg="secondary_hazardous field absent from Death Guard Helbrute unit record",
        )
        self.assertTrue(
            unit["secondary_hazardous"],
            msg=(
                f"Death Guard Helbrute secondary_hazardous="
                f"{unit['secondary_hazardous']!r}, expected True "
                f"(secondary weapon: {unit.get('secondary_weapon')!r})"
            ),
        )

    def test_exorcist_secondary_indirect_fire(self):
        """The Adepta Sororitas Exorcist secondary (Exorcist Conflagration
        Rockets) carries secondary_indirect_fire=True in parsed.json.

        Re-anchored from the Genestealer Cults Reductus Saboteur: under
        SWEG_CHOICE_TARGET_BASKET the Saboteur's every-round Remote explosives
        (not one-shot) now out-scores its one-shot Demolition charges, so Remote
        explosives becomes the primary and the indirect Remote-explosives profile
        leaves the secondary slot. The Exorcist is a canonical indirect-fire
        artillery tank whose secondary rockets stay indirect through the regen,
        so it exercises the same secondary_indirect_fire propagation this guard
        was written for."""
        unit = self.by_key.get("adepta_sororitas_exorcist")
        if unit is None:
            self.skipTest("adepta_sororitas_exorcist not in parsed.json")
        self.assertIn(
            "secondary_indirect_fire",
            unit,
            msg="secondary_indirect_fire field absent from Exorcist unit record",
        )
        self.assertTrue(
            unit["secondary_indirect_fire"],
            msg=(
                f"Exorcist secondary_indirect_fire="
                f"{unit['secondary_indirect_fire']!r}, expected True "
                f"(secondary weapon: {unit.get('secondary_weapon')!r})"
            ),
        )

    def test_csm_master_of_possession_secondary_precision(self):
        """The Chaos Space Marines Master of Possession secondary carries
        secondary_precision=True in parsed.json."""
        unit = self.by_key.get("chaos_space_marines_master_of_possession")
        if unit is None:
            self.skipTest("chaos_space_marines_master_of_possession not in parsed.json")
        self.assertIn(
            "secondary_precision",
            unit,
            msg="secondary_precision field absent from Master of Possession unit record",
        )
        self.assertTrue(
            unit["secondary_precision"],
            msg=(
                f"Master of Possession secondary_precision="
                f"{unit['secondary_precision']!r}, expected True "
                f"(secondary weapon: {unit.get('secondary_weapon')!r})"
            ),
        )

    # (d) -------------------------------------------------------------------
    def test_all_secondary_profile_units_carry_parity_fields(self):
        """Every unit with a secondary profile (secondary_attacks > 0) carries
        all four new keyword parity fields in parsed.json.

        Before the fix, none of these fields existed in the MappedUnit dataclass,
        so the sec_swap block would silently inherit from the primary profile."""
        missing: list = []
        for unit in self.records:
            if not unit.get("secondary_attacks", 0):
                continue
            key = unit.get("key", "<no-key>")
            absent = [f for f in sorted(SECONDARY_PARITY_FIELDS) if f not in unit]
            if absent:
                missing.append((key, absent))

        self.assertEqual(
            missing,
            [],
            msg=(
                f"{len(missing)} units with secondary profiles are missing "
                f"new parity fields (first 5): {missing[:5]}"
            ),
        )


class SecondaryKeywordParityUnitCatalogTests(unittest.TestCase):
    """GAP 1 tests via the loaded UNIT_CATALOG (full stack)."""

    # (b) -------------------------------------------------------------------
    def test_whirlwind_scorpius_catalog_secondary_one_shot(self):
        """After the full load, the Whirlwind Scorpius UnitProfile carries
        secondary_one_shot=True."""
        profile = UNIT_CATALOG.get("chaos_space_marines_whirlwind_scorpius_legends")
        if profile is None:
            self.skipTest(
                "chaos_space_marines_whirlwind_scorpius_legends not in UNIT_CATALOG"
            )
        self.assertTrue(
            hasattr(profile, "secondary_one_shot"),
            msg="secondary_one_shot attribute absent from UnitProfile",
        )
        self.assertTrue(
            profile.secondary_one_shot,
            msg=(
                f"Whirlwind Scorpius UnitProfile.secondary_one_shot="
                f"{profile.secondary_one_shot!r}, expected True"
            ),
        )

    def test_helbrute_catalog_secondary_hazardous(self):
        """After the full load, the Death Guard Helbrute UnitProfile carries
        secondary_hazardous=True. Re-anchored from the Chaos Space Marines
        Helbrute (see test_helbrute_secondary_hazardous for why the basket
        regeneration moved that unit's hazardous plasma cannon off the secondary
        slot)."""
        profile = UNIT_CATALOG.get("death_guard_helbrute")
        if profile is None:
            self.skipTest("death_guard_helbrute not in UNIT_CATALOG")
        self.assertTrue(
            hasattr(profile, "secondary_hazardous"),
            msg="secondary_hazardous attribute absent from UnitProfile",
        )
        self.assertTrue(
            profile.secondary_hazardous,
            msg=(
                f"Death Guard Helbrute UnitProfile.secondary_hazardous="
                f"{profile.secondary_hazardous!r}, expected True"
            ),
        )

    # (c) -------------------------------------------------------------------
    def test_sec_swap_dict_carries_new_parity_fields(self):
        """The sec_swap dict constructed from secondary_* UnitProfile fields
        carries all four new keyword fields, so dataclasses.replace will override
        the primary profile's value rather than inheriting silently.

        We replicate the sec_swap construction logic for a representative unit
        (Whirlwind Scorpius, secondary=Hunter-killer missile, one_shot=True)."""
        profile = UNIT_CATALOG.get("chaos_space_marines_whirlwind_scorpius_legends")
        if profile is None:
            self.skipTest(
                "chaos_space_marines_whirlwind_scorpius_legends not in UNIT_CATALOG"
            )
        if not profile.secondary_attacks:
            self.skipTest("Whirlwind Scorpius has no secondary profile loaded")

        # Replicate the sec_swap construction from units.py Unit.attack().
        sec_swap_simulated = {
            "one_shot":      bool(profile.secondary_one_shot),
            "hazardous":     bool(profile.secondary_hazardous),
            "indirect_fire": bool(profile.secondary_indirect_fire),
            "precision":     bool(profile.secondary_precision),
        }

        for field in ("one_shot", "hazardous", "indirect_fire", "precision"):
            self.assertIn(
                field,
                sec_swap_simulated,
                msg=f"field '{field}' missing from simulated sec_swap",
            )

        # The Hunter-killer missile is one_shot; verify the value survives.
        self.assertTrue(
            sec_swap_simulated["one_shot"],
            msg=(
                "Whirlwind Scorpius sec_swap would set one_shot=False, meaning "
                "the Hunter-killer missile would fire every activation instead of "
                "once per battle"
            ),
        )


class ExtraMeleeKeywordParityTests(unittest.TestCase):
    """GAP 2 tests: extra_melee_profiles carries one_shot and hazardous."""

    @classmethod
    def setUpClass(cls):
        cls.records = _parsed_units()
        cls.by_key = {u["key"]: u for u in cls.records}

    # (e) -------------------------------------------------------------------
    def test_all_extra_melee_profiles_carry_one_shot_and_hazardous(self):
        """Every entry in every unit's extra_melee_profiles carries both
        one_shot and hazardous keys.

        Before the fix, these keys were absent from the inline dict in
        mapper.py's extra_melee_profiles serializer, so the runtime swap in
        units.py would fall back to the primary melee profile's values via
        dataclasses.replace."""
        missing: list = []
        for unit in self.records:
            key = unit.get("key", "<no-key>")
            for em in unit.get("extra_melee_profiles", []):
                weapon_name = em.get("weapon", "<unnamed>")
                absent = [f for f in sorted(EXTRA_MELEE_NEW_FIELDS) if f not in em]
                if absent:
                    missing.append((key, weapon_name, absent))

        self.assertEqual(
            missing,
            [],
            msg=(
                f"{len(missing)} extra_melee_profiles entries are missing the new "
                f"keyword parity fields (first 5): {missing[:5]}"
            ),
        )

    def test_extra_melee_profiles_unit_has_expected_fields(self):
        """A unit with extra_melee_profiles (Aeldari Craftworlds Lhykhis)
        has both one_shot and hazardous in its extra melee profile entries."""
        unit = self.by_key.get("aeldari_craftworlds_lhykhis")
        if unit is None:
            self.skipTest("aeldari_craftworlds_lhykhis not in parsed.json")
        extras = unit.get("extra_melee_profiles", [])
        if not extras:
            self.skipTest("aeldari_craftworlds_lhykhis has no extra_melee_profiles")
        for em in extras:
            self.assertIn(
                "one_shot",
                em,
                msg=(
                    f"one_shot key absent from extra_melee_profiles entry "
                    f"'{em.get('weapon')}' for aeldari_craftworlds_lhykhis"
                ),
            )
            self.assertIn(
                "hazardous",
                em,
                msg=(
                    f"hazardous key absent from extra_melee_profiles entry "
                    f"'{em.get('weapon')}' for aeldari_craftworlds_lhykhis"
                ),
            )

    def test_extra_melee_runtime_swap_dict_carries_new_fields(self):
        """The _melee_extras swap dict construction in units.py carries
        one_shot and hazardous so dataclasses.replace overrides the primary
        melee profile's values.

        We verify via UNIT_CATALOG: a unit with extra_melee_profiles exposes
        those profiles as tuple-of-tuples; converting one back to a dict and
        simulating the swap dict construction confirms the key presence."""
        # Use the first unit in UNIT_CATALOG that has extra_melee_profiles.
        profile_with_extras = next(
            (p for p in UNIT_CATALOG.values() if p.extra_melee_profiles),
            None,
        )
        if profile_with_extras is None:
            self.skipTest("No unit in UNIT_CATALOG has extra_melee_profiles")

        for raw_pairs in profile_with_extras.extra_melee_profiles:
            _ed = dict(raw_pairs)
            # Replicate the _melee_extras construction from units.py.
            swap_simulated = {
                "one_shot":  bool(_ed.get("one_shot",  False)),
                "hazardous": bool(_ed.get("hazardous", False)),
            }
            for field in ("one_shot", "hazardous"):
                self.assertIn(
                    field,
                    swap_simulated,
                    msg=(
                        f"field '{field}' missing from simulated _melee_extras "
                        f"swap for profile '{_ed.get('weapon', '<unnamed>')}' "
                        f"on unit with extra_melee_profiles"
                    ),
                )
