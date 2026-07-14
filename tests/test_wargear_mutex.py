"""Tests for SWEG_WARGEAR_MUTEX — resolve the mutually-exclusive / optional
wargear catalogue defect.

The BSData mapper's flat weapon walk collects EVERY option of a single-model
unit's wargear groups as an independently-firing profile, so a vehicle fires
weapons no legal loadout can carry together: the Rogal Dorn fires its twin
battle cannon AND its replacement oppressor cannon, plus both optional sponson
multi-meltas and hull meltaguns; the Basilisk's aggregate carries its heavy
bolter AND the replacement heavy flamer. The gate (default OFF) drops the
mutex-alternative and optional-slot weapons named in _WARGEAR_MUTEX_DROPS,
leaving each corrected unit its legal datasheet-default loadout in BOTH the
aggregate and per-model representations.

Tests:
  (a) gate OFF (unset AND explicit values other than '1'): scoped units are
      byte-identical to base — the optional/mutex weapons are still present, and
      the two off-states produce equal UnitProfiles.
  (b) gate ON: the dropped weapons are gone from the aggregate AND per-model
      representations; the datasheet-default weapons remain.
  (c) gate ON differs from OFF for every scoped unit.
  (d) expected-wounds fixture: the gate-on Rogal Dorn aggregate lands on its
      hand-computed legal-loadout value (~9.2), far below the gate-off ~20.
  (e) _apply_wargear_mutex_drop fails loud (rule 13) on a primary drop and on a
      drop-list that matches nothing.

Cited per-unit in data/rule_citations.d/wargear_mutex.json.
"""
from __future__ import annotations

import os
import random
import dataclasses
import unittest

from code.units import (
    _build_catalog,
    _unflatten_model_loadouts,
    _apply_wargear_mutex_drop,
    _WARGEAR_MUTEX_DROPS,
    _PERMODEL_SECONDARY_RANGED_RESET,
    Unit,
)

_GATE = "SWEG_WARGEAR_MUTEX"
_PERMODEL = "SWEG_PERMODEL"
ROGAL = "astra_militarum_rogal_dorn_battle_tank"
BASILISK = "astra_militarum_basilisk"


def _aggregate_weapon_names(p):
    """Lowercased weapon names in the aggregate representation."""
    names = [p.weapon.lower(), p.secondary_weapon.lower()]
    for e in p.extra_ranged_profiles:
        names.append(str(dict(e).get("weapon", "")).lower())
    for e in p.extra_melee_profiles:
        names.append(str(dict(e).get("weapon", "")).lower())
    return [n for n in names if n]


def _model_weapon_names(p):
    names = []
    for m in _unflatten_model_loadouts(p.model_loadouts):
        for slot in ("ranged", "melee"):
            for w in (m.get(slot) or []):
                names.append(str(w.get("weapon", "")).lower())
    return names


class WargearMutexTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in (_GATE, _PERMODEL)}
        os.environ.pop(_GATE, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _catalog(self, gate):
        if gate is None:
            os.environ.pop(_GATE, None)
        else:
            os.environ[_GATE] = gate
        return _build_catalog()

    # (a) gate OFF — byte-identical to base ------------------------------------
    def test_gate_off_byte_identical(self):
        off_unset = self._catalog(None)
        off_zero = self._catalog("0")
        off_other = self._catalog("no")
        for key in _WARGEAR_MUTEX_DROPS:
            with self.subTest(key=key):
                self.assertIn(key, off_unset)
                # Any non-'1' value skips the block entirely (frozen-dataclass eq).
                self.assertEqual(off_unset[key], off_zero[key])
                self.assertEqual(off_unset[key], off_other[key])
        # The dropped weapons are still present when off.
        self.assertIn("twin battle cannon", _aggregate_weapon_names(off_unset[ROGAL]))
        self.assertIn("multi-melta", _model_weapon_names(off_unset[ROGAL]))
        self.assertIn("heavy flamer", _aggregate_weapon_names(off_unset[BASILISK]))

    # (b) gate ON — dropped weapons gone, defaults remain ----------------------
    def test_gate_on_drops_optional_and_mutex(self):
        on = self._catalog("1")
        # Rogal Dorn: twin battle cannon (mutex alt) + sponson multi-meltas +
        # hull meltaguns dropped; oppressor + coaxial + pulveriser + heavy
        # stubber (the legal default) kept.
        agg = _aggregate_weapon_names(on[ROGAL])
        models = _model_weapon_names(on[ROGAL])
        for gone in ("twin battle cannon", "multi-melta", "meltagun"):
            self.assertNotIn(gone, agg, f"{gone} should be dropped from aggregate")
            self.assertNotIn(gone, models, f"{gone} should be dropped from per-model")
        self.assertEqual(on[ROGAL].weapon.lower(), "oppressor cannon")
        self.assertIn("pulveriser cannon", models)
        self.assertIn("coaxial autocannon", models)
        self.assertIn("heavy stubber", models)
        # Basilisk: heavy flamer + hunter-killer dropped from aggregate; heavy
        # bolter (the default hull weapon) kept.
        b_agg = _aggregate_weapon_names(on[BASILISK])
        self.assertNotIn("heavy flamer", b_agg)
        self.assertNotIn("hunter-killer missile", b_agg)
        self.assertIn("heavy bolter", b_agg)
        self.assertEqual(on[BASILISK].weapon.lower(), "earthshaker cannon")

    # (c) gate ON differs from OFF for every scoped unit -----------------------
    def test_gate_on_differs_from_off(self):
        off = self._catalog(None)
        on = self._catalog("1")
        for key in _WARGEAR_MUTEX_DROPS:
            with self.subTest(key=key):
                self.assertNotEqual(
                    off[key], on[key],
                    f"{key}: gate ON must change the profile vs OFF",
                )

    # (d) expected-wounds fixture ---------------------------------------------
    def test_rogal_dorn_expected_wounds_deflated(self):
        """Aggregate-path (SWEG_PERMODEL=0) expected wounds vs a Marine (T4, 3+
        save, no cover / invuln / feel-no-pain). Hand-computed legal loadout:
          Oppressor cannon  6 x 1/2 hit x 5/6 wound(S12>=2T) x 4/6 fail(3+,AP-2) x 3 D = 5.00
          Pulveriser cannon 4 x 1/2 hit x 5/6 wound(S9>=2T)  x 5/6 fail(3+,AP-3) x 3 D = 4.17
          total = 9.17.  Gate off (adds twin battle cannon + multi-meltas +
          meltaguns) is ~20."""
        os.environ[_PERMODEL] = "0"
        off = self._catalog(None)
        on = self._catalog("1")
        target_src = off["space_marines_predator_destructor"]
        tgt = dataclasses.replace(
            target_src, name="ref-marine", health=1000, toughness=4, save=3,
            invuln_save=7, fnp=7, model_loadouts=(), extra_ranged_profiles=(),
            secondary_attacks=0, unit_keywords=("INFANTRY",),
            min_models=1, max_models=1,
        )

        def ev(profile, trials=2500, seed=5):
            random.seed(seed)
            return sum(
                Unit(profile).attack(Unit(tgt), distance=6.0, mode="ranged")
                for _ in range(trials)
            ) / trials

        ev_off = ev(off[ROGAL])
        ev_on = ev(on[ROGAL])
        self.assertGreater(ev_off, 16.0, f"gate-off should be ~20, got {ev_off:.2f}")
        self.assertTrue(
            8.3 < ev_on < 10.2,
            f"gate-on legal loadout should be ~9.2 (hand-computed 9.17), got {ev_on:.2f}",
        )
        self.assertLess(ev_on, ev_off * 0.6, "gate must deflate the tank materially")

    # (e) fail-loud (rule 13) --------------------------------------------------
    def test_fail_loud_on_primary_drop(self):
        cat = self._catalog(None)
        p = cat[BASILISK]  # primary = Earthshaker cannon
        with self.assertRaises(ValueError):
            _apply_wargear_mutex_drop(p, BASILISK, ("earthshaker cannon",))

    def test_fail_loud_on_no_match(self):
        cat = self._catalog(None)
        p = cat[BASILISK]
        with self.assertRaises(ValueError):
            _apply_wargear_mutex_drop(p, BASILISK, ("weapon that does not exist",))

    def test_secondary_reset_shape(self):
        """A dropped secondary weapon resets the whole secondary block."""
        on = self._catalog("1")
        # Rogal Dorn's secondary (twin battle cannon) is dropped -> block cleared.
        self.assertEqual(on[ROGAL].secondary_weapon, "")
        self.assertEqual(on[ROGAL].secondary_attacks,
                         _PERMODEL_SECONDARY_RANGED_RESET["secondary_attacks"])


if __name__ == "__main__":
    unittest.main()
