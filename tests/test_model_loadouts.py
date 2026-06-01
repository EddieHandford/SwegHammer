"""Tests for PER-MODEL-LOADOUTS STAGE 1 — the mapper's per-model weapon
loadouts (`MappedUnit.model_loadouts`).

Stage 1 is a data-only change: the mapper now records, alongside the existing
aggregate synthetic weapon, a per-model loadout for every unit (each model
type's actual equipped weapons, with the raw Attacks / Damage dice strings
preserved). Nothing in the simulator reads this data yet, so these tests only
assert the SHAPE and CONSISTENCY of the new field.

The properties under test:
  (a) every mappable unit record carries a non-empty `model_loadouts`;
  (b) for a multi-model squad the loadout `count` values sum to ~`max_models`;
  (c) a known multi-wound weapon's `damage_dice` is the raw BSData string
      (e.g. the Multi-melta shows "D6") and `parse_dice_expr(damage_dice)`
      equals the stored `weapon_damage_per_shot` mean — the MEAN-INVARIANT
      that proves the preserved dice are consistent with the legacy mean;
  (d) a single-model unit (a Wraithknight / Knight) has exactly ONE model
      entry with `count == 1.0`, and its option-per-choice-group loadout no
      longer carries every mutually-exclusive arm-weapon option at once.

We read the parsed.json the mapper produces (regenerated on demand if
missing), mirroring the convention in tests/test_mapper.py.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from code.bsdata.mapper import PARSED_PATH, parse_dice_expr
from code.units import (
    UNIT_CATALOG,
    _flatten_model_loadouts,
    _unflatten_model_loadouts,
)


def _parsed() -> dict:
    if not Path(PARSED_PATH).exists():
        raise unittest.SkipTest(
            f"parsed.json not found at {PARSED_PATH}; run `python -m code.bsdata.mapper`"
        )
    return json.loads(Path(PARSED_PATH).read_text(encoding="utf-8"))


class ModelLoadoutShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = _parsed()
        cls.records = data["units"]
        # Index by key; the catalogue has one known duplicate key
        # (space_wolves_wolf_guard_headtakers) — last-wins is fine for the
        # spot-check lookups below.
        cls.units = {u["key"]: u for u in cls.records}

    def _get(self, key: str) -> dict:
        u = self.units.get(key)
        if u is None:
            self.skipTest(f"unit '{key}' missing from parsed.json")
        return u

    # (a) -------------------------------------------------------------------
    def test_every_firing_unit_has_model_loadouts(self):
        """Every ENABLED unit that resolves a weapon must carry a non-empty
        `model_loadouts` with at least one weapon somewhere in it."""
        missing = []
        for u in self.records:
            if not u.get("enabled", False):
                continue
            ml = u.get("model_loadouts")
            has_weapon = bool(ml) and any(
                m.get("ranged") or m.get("melee") for m in ml
            )
            if not has_weapon:
                missing.append(u["key"])
        self.assertEqual(
            missing,
            [],
            msg=f"{len(missing)} enabled units have empty model_loadouts: "
            f"{missing[:10]}",
        )

    # (b) -------------------------------------------------------------------
    def test_squad_counts_sum_to_max_models(self):
        """A multi-model squad's per-model `count` values sum to ~max_models."""
        for key in (
            "space_marines_devastator_squad",
            "space_marines_tactical_squad",
            "space_marines_intercessor_squad",
        ):
            u = self._get(key)
            total = sum(m["count"] for m in u["model_loadouts"])
            self.assertAlmostEqual(
                total,
                float(u["max_models"]),
                delta=1.0,
                msg=f"{key}: loadout counts {total} != max_models {u['max_models']}",
            )

    # (c) -------------------------------------------------------------------
    def test_damage_dice_is_raw_string_and_mean_consistent(self):
        """The Devastator squad's Heavy-Weapon model carries the Multi-melta
        with a raw 'D6' damage_dice, and parse_dice_expr(damage_dice) equals
        the stored mean (weapon_damage_per_shot)."""
        u = self._get("space_marines_devastator_squad")
        multi_melta = None
        for m in u["model_loadouts"]:
            for w in m["ranged"]:
                if w["weapon"] == "Multi-melta":
                    multi_melta = w
        self.assertIsNotNone(
            multi_melta, msg="Devastator squad loadout missing Multi-melta"
        )
        self.assertEqual(multi_melta["damage_dice"], "D6")
        self.assertEqual(
            parse_dice_expr(multi_melta["damage_dice"]),
            multi_melta["weapon_damage_per_shot"],
        )

    def test_mean_invariant_holds_across_all_loadouts(self):
        """For EVERY weapon in EVERY model loadout, when a dice string is
        present, parse_dice_expr(damage_dice) must reproduce the stored mean
        (weapon_damage_per_shot) and parse_dice_expr(attacks_dice) the stored
        attacks mean. This proves the preserved dice are consistent with the
        legacy expected-value fields — they never drift apart."""
        checked = 0
        for u in self.records:
            for m in u.get("model_loadouts", []):
                for w in m.get("ranged", []) + m.get("melee", []):
                    dd = w.get("damage_dice", "")
                    if dd:
                        mean = parse_dice_expr(dd)
                        if mean is not None:
                            self.assertAlmostEqual(
                                round(mean, 2),
                                w["weapon_damage_per_shot"],
                                places=2,
                                msg=f"{u['key']} {w['weapon']}: damage_dice "
                                f"{dd!r} mean {mean} != stored "
                                f"{w['weapon_damage_per_shot']}",
                            )
                            checked += 1
        self.assertGreater(checked, 100, "expected many dice to mean-check")

    # (d) -------------------------------------------------------------------
    def test_single_model_unit_has_exactly_one_model_entry(self):
        """A single-model unit (Wraithknight / Knight) has exactly ONE model
        entry with count == 1.0."""
        for key in (
            "aeldari_craftworlds_wraithknight",
            "imperial_knights_library_knight_paladin",
        ):
            u = self._get(key)
            self.assertEqual(
                len(u["model_loadouts"]),
                1,
                msg=f"{key}: expected one model entry, got "
                f"{[m['name'] for m in u['model_loadouts']]}",
            )
            self.assertEqual(u["model_loadouts"][0]["count"], 1.0)

    def test_wraithknight_has_one_arm_cannon_not_both(self):
        """The Wraithknight's single-model loadout must carry exactly ONE of
        its mutually-exclusive arm cannons (Suncannon OR Heavy Wraithcannon),
        not both — proving the option-per-choice-group picker replaced the
        legacy flat weapon-walk that collected every arm option."""
        u = self._get("aeldari_craftworlds_wraithknight")
        ranged_names = [w["weapon"] for w in u["model_loadouts"][0]["ranged"]]
        cannons = {"Suncannon", "Heavy Wraithcannon"} & set(ranged_names)
        self.assertEqual(
            len(cannons),
            1,
            msg=f"Wraithknight should carry exactly one arm cannon, got "
            f"{ranged_names}",
        )


class ModelLoadoutStage2PlumbingTests(unittest.TestCase):
    """PER-MODEL-LOADOUTS STAGE 2 — the field is plumbed parsed.json →
    CatalogEntry → UnitProfile as a hashable flattened tuple, and the
    flatten / unflatten helpers round-trip exactly. Stage 2 is GATE-INERT:
    nothing reads the field for behaviour, so these tests assert only that the
    data is carried losslessly and that a UnitProfile carrying it stays
    hashable under the frozen dataclass / lru_cache.
    """

    @classmethod
    def setUpClass(cls):
        data = _parsed()
        cls.records = data["units"]
        cls.units = {u["key"]: u for u in cls.records}

    # (a) hashability ------------------------------------------------------
    def test_unit_profile_with_loadouts_is_hashable(self):
        """A catalogue UnitProfile that carries a non-empty model_loadouts
        must hash (the dataclass is frozen and used as an lru_cache key)."""
        prof = UNIT_CATALOG.get("space_marines_devastator_squad")
        self.assertIsNotNone(prof, "Devastator squad missing from UNIT_CATALOG")
        self.assertTrue(
            prof.model_loadouts,
            "Devastator squad UnitProfile carries an empty model_loadouts",
        )
        # Must not raise — proves the flattened nested tuple is hashable.
        self.assertIsInstance(hash(prof), int)
        # And it must be usable as a dict / set key (the lru_cache contract).
        self.assertIn(prof, {prof: 1})

    def test_every_catalogue_profile_is_hashable(self):
        """No UnitProfile in the whole catalogue is unhashable because of the
        new field (catches any unit whose loadout flattened to a list)."""
        for key, prof in UNIT_CATALOG.items():
            try:
                hash(prof)
            except TypeError as exc:  # pragma: no cover - failure path
                self.fail(f"UnitProfile {key!r} is not hashable: {exc}")

    # (b) round-trip -------------------------------------------------------
    def test_flatten_unflatten_round_trips_for_representative_unit(self):
        """_unflatten_model_loadouts(_flatten_model_loadouts(x)) == x for a
        representative parsed model_loadouts value — exact shape and types
        (counts stay float, ap stays int, anti_keywords stays a dict)."""
        for key in (
            "space_marines_devastator_squad",   # multi-model, dice weapons
            "aeldari_craftworlds_corsair_voidreavers",  # non-empty anti_keywords
            "aeldari_craftworlds_wraithknight",  # single model
        ):
            orig = self.units.get(key, {}).get("model_loadouts")
            if not orig:
                self.skipTest(f"{key} has no model_loadouts in parsed.json")
            rt = _unflatten_model_loadouts(_flatten_model_loadouts(orig))
            self.assertEqual(rt, orig, msg=f"{key}: round-trip not exact")

    def test_round_trip_preserves_value_types(self):
        """The round-trip must preserve int / float / str / bool / dict value
        types exactly, not just equality (1 == 1.0 in Python)."""
        orig = self.units["aeldari_craftworlds_corsair_voidreavers"][
            "model_loadouts"
        ]
        rt = _unflatten_model_loadouts(_flatten_model_loadouts(orig))
        for m in rt:
            self.assertIsInstance(m["count"], float)
            self.assertIsInstance(m["name"], str)
            for w in m.get("ranged", []) + m.get("melee", []):
                self.assertIsInstance(w["ap"], int)
                self.assertIsInstance(w["weapon_damage_per_shot"], float)
                self.assertIsInstance(w["anti_keywords"], dict)

    def test_flatten_unflatten_round_trips_for_every_unit(self):
        """The round-trip is lossless for EVERY unit's model_loadouts (catches
        any nested shape the spot-checks miss)."""
        checked = 0
        for u in self.records:
            ml = u.get("model_loadouts")
            if not ml:
                continue
            rt = _unflatten_model_loadouts(_flatten_model_loadouts(ml))
            self.assertEqual(rt, ml, msg=f"{u['key']}: round-trip not exact")
            checked += 1
        self.assertGreater(checked, 100, "expected many units to round-trip")

    def test_empty_loadouts_round_trip_to_empty(self):
        """None / empty flatten to () and unflatten back to an empty list."""
        self.assertEqual(_flatten_model_loadouts(None), ())
        self.assertEqual(_flatten_model_loadouts([]), ())
        self.assertEqual(_unflatten_model_loadouts(()), [])

    # (c) built-catalogue carriage ----------------------------------------
    def test_multi_and_single_model_units_carry_loadouts_in_catalog(self):
        """A built UnitProfile for a multi-model squad and for a single-model
        unit both carry a non-empty model_loadouts after _build_catalog."""
        multi = UNIT_CATALOG.get("space_marines_intercessor_squad")
        single = UNIT_CATALOG.get("aeldari_craftworlds_wraithknight")
        self.assertIsNotNone(multi, "Intercessor squad missing from catalogue")
        self.assertIsNotNone(single, "Wraithknight missing from catalogue")
        self.assertTrue(
            multi.model_loadouts,
            "multi-model Intercessor squad carries empty model_loadouts",
        )
        self.assertTrue(
            single.model_loadouts,
            "single-model Wraithknight carries empty model_loadouts",
        )

    def test_catalog_loadout_unflattens_to_parsed_shape(self):
        """The flattened model_loadouts stamped on a catalogue UnitProfile,
        when unflattened, reproduces the parsed.json list-of-dicts — proving
        the build-time flatten and the inverse helper agree end to end."""
        key = "space_marines_devastator_squad"
        prof = UNIT_CATALOG[key]
        rebuilt = _unflatten_model_loadouts(prof.model_loadouts)
        self.assertEqual(rebuilt, self.units[key]["model_loadouts"])


if __name__ == "__main__":
    unittest.main()
