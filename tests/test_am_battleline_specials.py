"""Tests for SWEG_AM_BATTLELINE_SPECIALS — restore the special weapons the
BSData v10.6.0 mapper drops from Cadian Shock Troops and Death Korps of Krieg.

The mapper collapses both core battleline squads to a single lasgun-only model
type (model_loadouts has one Lasgun + Close combat weapon entry), even though
each 10-model squad fields up to 2 special weapons per the datasheet. The gate
(default OFF) replaces their model_loadouts with a heterogeneous list — per 10
models: 8 lasgun troopers + 1 plasma gun + 1 meltagun — so the per-model
promotion in Army._add_squad_per_model builds the special-weapon models.

Tests:
  (a) gate OFF (unset AND explicit '0'): model_loadouts is byte-identical to
      base — exactly one lasgun-only model entry, no plasma / meltagun anywhere,
      and the two off-states produce equal UnitProfiles.
  (b) gate ON: model_loadouts has ~2 special-weapon models per 10 (8 lasgun +
      1 plasma + 1 meltagun, counts summing to 10), and a built 10-model squad
      contains exactly one plasma-armed and one meltagun-armed model with the
      cited weapon stats.

Cited as `simulator.am_battleline_special_weapons` in
data/rule_citations.d/astra_militarum.json.
"""
from __future__ import annotations

import os
import unittest

from code.army import Army
from code.units import _build_catalog, _unflatten_model_loadouts


CADIAN = "astra_militarum_cadian_shock_troops"
KRIEG = "astra_militarum_death_korps_of_krieg"
KEYS = (CADIAN, KRIEG)

_GATE = "SWEG_AM_BATTLELINE_SPECIALS"
_PERMODEL = "SWEG_PERMODEL"


def _ranged_weapon_names(models):
    """Every ranged weapon name across a list-of-dicts model_loadouts."""
    names = []
    for m in models:
        for w in (m.get("ranged") or []):
            names.append(w.get("weapon", ""))
    return names


class AmBattlelineSpecialsTests(unittest.TestCase):
    def setUp(self):
        # Snapshot and clear the gate so each test sets it explicitly.
        self._saved = {k: os.environ.get(k) for k in (_GATE, _PERMODEL)}
        os.environ.pop(_GATE, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _catalog(self, gate):
        """Build a fresh catalog with the gate set to `gate` (None = unset)."""
        if gate is None:
            os.environ.pop(_GATE, None)
        else:
            os.environ[_GATE] = gate
        return _build_catalog()

    # (a) gate OFF — byte-identical to the lasgun-only base ----------------
    def test_gate_off_byte_identical_lasgun_only(self):
        off_unset = self._catalog(None)
        off_zero = self._catalog("0")
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIn(key, off_unset, f"{key} missing from catalogue")
                # Unset and explicit '0' must produce the identical entry: the
                # gate block is skipped entirely when off (frozen-dataclass eq).
                self.assertEqual(
                    off_unset[key], off_zero[key],
                    "gate unset and gate=0 must be byte-identical",
                )
                models = _unflatten_model_loadouts(off_unset[key].model_loadouts)
                # Exactly one lasgun-only model type.
                self.assertEqual(
                    len(models), 1,
                    f"{key} off should have one lasgun-only model entry",
                )
                names = " ".join(_ranged_weapon_names(models)).lower()
                self.assertIn("lasgun", names)
                self.assertNotIn("plasma", names)
                self.assertNotIn("melta", names)

    # (b) gate ON — heterogeneous loadout, ~2 specials per 10 -------------
    def test_gate_on_two_specials_per_ten(self):
        on = self._catalog("1")
        for key in KEYS:
            with self.subTest(key=key):
                models = _unflatten_model_loadouts(on[key].model_loadouts)
                # 8 lasgun + 1 plasma + 1 meltagun = three model types.
                self.assertEqual(len(models), 3, f"{key} should have 3 model types")
                total = sum(float(m.get("count", 0) or 0) for m in models)
                self.assertEqual(total, 10.0, "counts should sum to the 10-model squad")
                names = [n.lower() for n in _ranged_weapon_names(models)]
                self.assertEqual(sum("plasma" in n for n in names), 1)
                self.assertEqual(sum("meltagun" in n for n in names), 1)
                self.assertEqual(sum(n.strip() == "lasgun" for n in names), 1)
                # The two special slots carry count 1 each (2 specials / 10).
                special_counts = [
                    float(m.get("count", 0) or 0)
                    for m in models
                    if any(
                        ("plasma" in (w.get("weapon", "").lower())
                         or "meltagun" in (w.get("weapon", "").lower()))
                        for w in (m.get("ranged") or [])
                    )
                ]
                self.assertEqual(sorted(special_counts), [1.0, 1.0])

    def test_gate_on_built_squad_has_special_models(self):
        os.environ[_PERMODEL] = "1"  # per-model promotion path (default on)
        on = self._catalog("1")
        for key in KEYS:
            with self.subTest(key=key):
                army = Army("AM")
                army.add_squad(on[key], 10)
                self.assertEqual(len(army.units), 10, "squad should build 10 models")
                weapons = [u.profile.weapon.lower() for u in army.units]
                plasma = [u for u in army.units
                          if "plasma" in u.profile.weapon.lower()]
                melta = [u for u in army.units
                         if "meltagun" in u.profile.weapon.lower()]
                self.assertEqual(len(plasma), 1, "exactly one plasma-armed model")
                self.assertEqual(len(melta), 1, "exactly one meltagun-armed model")
                self.assertEqual(
                    sum(w.strip() == "lasgun" for w in weapons), 8,
                    "remaining 8 models are lasgun troopers",
                )
                # Cited weapon stats land on the promoted primary block.
                p = plasma[0].profile
                self.assertEqual((p.strength, p.ap), (8, -3))
                self.assertEqual(p.weapon_damage_per_shot, 2.0)
                m = melta[0].profile
                self.assertEqual((m.strength, m.ap, m.melta), (9, -4, 2))
                self.assertEqual(m.weapon_damage_per_shot, 3.5)

    def test_gate_on_differs_from_off(self):
        off = self._catalog(None)
        on = self._catalog("1")
        for key in KEYS:
            with self.subTest(key=key):
                self.assertNotEqual(
                    off[key].model_loadouts, on[key].model_loadouts,
                    "gate ON must change the loadout vs OFF",
                )


if __name__ == "__main__":
    unittest.main()
