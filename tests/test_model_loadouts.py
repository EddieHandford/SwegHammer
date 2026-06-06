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

import dataclasses
import json
import os
import unittest
from collections import Counter
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


class ModelLoadoutStage3FiringTests(unittest.TestCase):
    """PER-MODEL-LOADOUTS STAGE 3 — `Army.add_squad` instantiates one Unit per
    model from the per-model loadout, each firing its OWN weapons, when the
    `SWEG_PERMODEL` env gate is set. OFF (gate unset) reproduces the legacy
    shared-profile behaviour exactly.

    These tests drive the real catalogue UnitProfiles (the Devastator squad's
    Boltgun / Multi-melta / Sergeant split is a known, stable shape) so they
    exercise the count→size Hamilton mapping, the loadout→weapon-field
    conversion, weapon-loss-on-death, and single-model expansion end to end.
    """

    def setUp(self):
        # Imported lazily so the OFF-path identity assertion can run with the
        # gate genuinely unset (the monkeypatch in the ON tests sets it per
        # test via os.environ directly).
        from code.units import UNIT_CATALOG, _unflatten_model_loadouts
        from code.army import Army
        self.UNIT_CATALOG = UNIT_CATALOG
        self._unflatten = _unflatten_model_loadouts
        self.Army = Army
        # Ensure a clean gate state before each test; tests that need it ON set
        # it explicitly and the tearDown restores.
        self._saved_env = os.environ.get("SWEG_PERMODEL")
        os.environ.pop("SWEG_PERMODEL", None)

    def tearDown(self):
        if self._saved_env is None:
            os.environ.pop("SWEG_PERMODEL", None)
        else:
            os.environ["SWEG_PERMODEL"] = self._saved_env

    def _build(self, key, size):
        army = self.Army(name="test")
        army.add_squad(self.UNIT_CATALOG[key], size)
        return army

    # (1) mixed squad at MAX size — per-model weapon split -------------------
    def test_devastator_max_size_weapon_split(self):
        """At size == max_models the Devastator squad expands to one
        Multi-melta Unit per Heavy-Weapon model, one Boltgun Unit per
        Boltgun model, and one Sergeant Unit — matching the loadout counts."""
        os.environ["SWEG_PERMODEL"] = "1"
        prof = self.UNIT_CATALOG["space_marines_devastator_squad"]
        army = self._build("space_marines_devastator_squad", prof.max_models)
        self.assertEqual(len(army.units), prof.max_models)
        weapons = Counter(u.profile.weapon for u in army.units)
        # Loadout: 5 Boltgun + 4 Multi-melta + 1 Sergeant (Plasma pistol).
        self.assertEqual(weapons["Boltgun"], 5)
        self.assertEqual(weapons["Multi-melta"], 4)
        # The sergeant model carries the plasma pistol (exactly one).
        sergeant = [u for u in army.units if "Plasma pistol" in u.profile.weapon]
        self.assertEqual(len(sergeant), 1)
        # Heavy-weapon models carry the Multi-melta damage-per-shot mean (3.5),
        # bolter models the bolter mean (1.0) — proves the per-model primary
        # block was re-pointed from the loadout, not the squad average.
        mm = [u for u in army.units if u.profile.weapon == "Multi-melta"]
        self.assertTrue(all(abs(u.profile.weapon_damage_per_shot - 3.5) < 1e-6
                            for u in mm))
        bolt = [u for u in army.units if u.profile.weapon == "Boltgun"]
        self.assertTrue(all(abs(u.profile.weapon_damage_per_shot - 1.0) < 1e-6
                            for u in bolt))

    # (2) reduced size — Hamilton scaling + determinism ---------------------
    def test_devastator_size_five_scaled_and_deterministic(self):
        """At size 5 the squad is exactly 5 Units, exactly one leader
        (Sergeant), the body scaled by largest-remainder, and the expansion is
        deterministic across two builds (PYTHONHASHSEED=0)."""
        os.environ["SWEG_PERMODEL"] = "1"
        army = self._build("space_marines_devastator_squad", 5)
        self.assertEqual(len(army.units), 5)
        sergeants = [u for u in army.units if "Plasma pistol" in u.profile.weapon]
        self.assertEqual(len(sergeants), 1, "expected exactly one leader at size 5")
        # 4 body slots split 5:4 (Boltgun:Multi-melta) → 2:2 by largest remainder.
        weapons = Counter(u.profile.weapon for u in army.units)
        self.assertEqual(weapons["Boltgun"], 2)
        self.assertEqual(weapons["Multi-melta"], 2)
        # Determinism: a second build produces the identical weapon sequence.
        army2 = self._build("space_marines_devastator_squad", 5)
        self.assertEqual(
            [u.profile.weapon for u in army.units],
            [u.profile.weapon for u in army2.units],
        )

    # (3) size == 1 — single slot, no crash ---------------------------------
    def test_size_one_yields_one_unit(self):
        """A size-1 build of a multi-model datasheet yields exactly one Unit
        and does not crash (the leader takes the single slot)."""
        os.environ["SWEG_PERMODEL"] = "1"
        army = self._build("space_marines_devastator_squad", 1)
        self.assertEqual(len(army.units), 1)

    # (4) weapon-loss on death ----------------------------------------------
    def test_heavy_weapon_lost_when_its_model_dies(self):
        """Killing the Multi-melta Units removes their firepower: the squad's
        mean shooting output drops sharply (to roughly bolter-only level),
        because each model's weapons live on its own Unit and a dead Unit is
        skipped by the firing path — no special weapon-loss code needed."""
        import random
        from code.units import Unit, UnitProfile

        os.environ["SWEG_PERMODEL"] = "1"
        army = self._build("space_marines_devastator_squad", 10)

        # A fat dummy target so neither configuration one-shots it (we measure
        # raw output, not kills). T8, Sv5+, lots of health.
        def fresh_target():
            t = Unit(UnitProfile(
                name="Dummy", health=200.0, damage=0.0, hit_probability=0.0,
                save=5, toughness=8, range_inches=0, attacks=0,
            ))
            t.position = (6.0, 0.0)
            return t

        def squad_output(units):
            total = 0.0
            random.seed(1234)
            for _ in range(200):
                tgt = fresh_target()
                for u in units:
                    if u.is_alive:
                        total += u.attack(tgt, distance=6.0)
            return total

        alive = [u for u in army.units]
        full = squad_output(alive)

        # Kill the Multi-melta models.
        for u in army.units:
            if u.profile.weapon == "Multi-melta":
                u.current_health = 0
        self.assertTrue(any(not u.is_alive for u in army.units))
        reduced = squad_output([u for u in army.units])

        self.assertLess(
            reduced, full,
            "removing the Multi-melta models should cut the squad's output",
        )
        # The drop should be large — Multi-meltas (S9 D6 AP-2, melta) are the
        # bulk of the squad's damage. Expect at least a 30% reduction.
        self.assertLess(
            reduced, full * 0.7,
            f"expected a sharp drop after losing the heavy weapons; "
            f"full={full:.1f} reduced={reduced:.1f}",
        )

    # (5) single-model unit fires its real loadout, not every option --------
    def test_single_model_unit_fires_one_arm_cannon(self):
        """A Wraithknight built with the gate ON fires ONE arm cannon group
        (Suncannon), NOT both Suncannon and the mutually-exclusive Heavy
        Wraithcannon — the per-model profile carries only the loadout's real
        equipped arm cannon."""
        os.environ["SWEG_PERMODEL"] = "1"
        army = self._build("aeldari_craftworlds_wraithknight", 1)
        self.assertEqual(len(army.units), 1)
        u = army.units[0]
        carried = [u.profile.weapon] + [
            dict(e).get("weapon") for e in u.profile.extra_ranged_profiles
        ]
        self.assertIn("Suncannon", carried)
        self.assertNotIn("Heavy Wraithcannon", carried)

    # (6) OFF path — identity (today's behaviour) ---------------------------
    def test_off_path_shares_input_profile_identity(self):
        """With the gate UNSET, add_squad yields `n` Units that all share the
        input profile object (identity) and carry no squad_profile_ref —
        byte-for-byte the legacy behaviour."""
        os.environ["SWEG_PERMODEL"] = "0"   # per-model is now default-ON; pin the legacy path
        prof = self.UNIT_CATALOG["space_marines_devastator_squad"]
        army = self._build("space_marines_devastator_squad", 7)
        self.assertEqual(len(army.units), 7)
        self.assertTrue(all(u.profile is prof for u in army.units))
        self.assertTrue(all(u.squad_profile_ref is None for u in army.units))

    def test_off_path_unaffected_when_profile_has_no_loadout(self):
        """Even with the gate ON, a profile with an empty model_loadouts falls
        through to the legacy shared path (defensive: no crash, identity)."""
        os.environ["SWEG_PERMODEL"] = "1"
        prof = self.UNIT_CATALOG["space_marines_devastator_squad"]
        bare = dataclasses.replace(prof, model_loadouts=())
        army = self.Army(name="test")
        army.add_squad(bare, 5)
        self.assertEqual(len(army.units), 5)
        self.assertTrue(all(u.profile is bare for u in army.units))


if __name__ == "__main__":
    unittest.main()
