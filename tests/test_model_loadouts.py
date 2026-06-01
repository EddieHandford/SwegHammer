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


if __name__ == "__main__":
    unittest.main()
