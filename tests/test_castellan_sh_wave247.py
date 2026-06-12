"""
Wave 247 lever 2: Cadian Castellan "Senior Officer" sustained hits grant
(gated SWEG_CASTELLAN_SH, default-off).

BSData verbatim (Imperium - Astra Militarum - Library.cat.gz, Abilities
profile id a7f5-adb8-d1c9-2a2d):
  "While this model is leading a unit, ranged weapons equipped by models
   in that unit have the [SUSTAINED HITS 1] ability"

Three test classes:

(a) Gate "1": lookup_ability("Cadian Castellan").sustained_hits_ranged == 1,
    and effective_buffs on a Cadian Shock Troops unit led by the Castellan
    carries sustained_hits_ranged >= 1.

(b) Gate unset (default "0"): no grant — sustained_hits_ranged == 0.

(c) Gate "0": explicitly off — sustained_hits_ranged == 0.
"""

from __future__ import annotations

import os
import importlib
import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_leaders():
    """Reload code.leaders so the module-level SWEG_CASTELLAN_SH gate re-fires."""
    import code.leaders as leaders_mod
    importlib.reload(leaders_mod)
    # clear the lru_cache so lookup_ability reads the freshly loaded registry
    leaders_mod.lookup_ability.cache_clear()
    return leaders_mod


def _make_unit(name: str, position=(5.0, 5.0)):
    """Build a minimal Unit with the given name and position, no army_ref."""
    from code.units import UnitProfile
    from code.army import Army
    profile = UnitProfile(
        name=name, health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0,
        range_inches=24,
    )
    army = Army(name)
    army.add_unit(profile)
    u = army.units[-1]
    u.position = position
    return u, army


def _make_army_with_castellan_and_shock_troops():
    """
    Build a single Army containing both a Cadian Castellan and a Cadian Shock
    Troops model.  The Castellan is at (5, 5), the Shock Troops model at (8, 5)
    — 3" apart, inside the 6" aura_range.  army_ref is set on both units by
    Army.add_unit (via _add_live_unit).
    """
    from code.units import UnitProfile
    from code.army import Army

    castellan_profile = UnitProfile(
        name="Cadian Castellan", health=4, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0,
        range_inches=12,
        unit_keywords=("CHARACTER", "INFANTRY"),
    )
    shock_profile = UnitProfile(
        name="Cadian Shock Troops", health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0,
        range_inches=24,
    )

    army = Army("Astra Militarum")
    army.add_unit(castellan_profile)
    castellan = army.units[-1]
    castellan.position = (5.0, 5.0)

    army.add_unit(shock_profile)
    shock = army.units[-1]
    shock.position = (8.0, 5.0)   # 3" away — inside 6" aura

    return army, castellan, shock


# ---------------------------------------------------------------------------
# (a) Gate "1": grant is active
# ---------------------------------------------------------------------------

class TestGateOn(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_CASTELLAN_SH"] = "1"
        # Also ensure SWEG_OFFICER_FOLLOW is on so the Castellan entry reaches
        # _REGISTRY (it lives inside _AM_OFFICER_REGISTRY_ENTRIES which is
        # appended only when _AM_OFFICER_FOLLOW_GATE is True).
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"
        self._leaders_mod = _reload_leaders()

    def tearDown(self):
        os.environ.pop("SWEG_CASTELLAN_SH", None)
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)
        # Restore a clean default state for subsequent tests.
        _reload_leaders()

    def test_lookup_ability_sustained_hits_ranged_is_1_when_gate_on(self):
        ab = self._leaders_mod.lookup_ability("Cadian Castellan")
        self.assertIsNotNone(ab, "Cadian Castellan must resolve from the registry")
        self.assertEqual(
            ab.sustained_hits_ranged, 1,
            f"sustained_hits_ranged should be 1 when SWEG_CASTELLAN_SH=1, "
            f"got {ab.sustained_hits_ranged}",
        )

    def test_effective_buffs_carries_sustained_hits_ranged_when_gate_on(self):
        """
        A Cadian Shock Troops unit with a Castellan in aura range should see
        sustained_hits_ranged >= 1 in its effective_buffs dict.
        """
        _army, _castellan, shock = _make_army_with_castellan_and_shock_troops()
        # Reload leaders AFTER the army is built so the freshly reloaded
        # lookup_ability / effective_buffs functions are used.
        leaders_mod = _reload_leaders()
        leaders_mod.bump_buffs_generation()   # clear per-battle cache

        buffs = leaders_mod.effective_buffs(shock)
        sh_ranged = buffs.get("sustained_hits_ranged", 0)
        self.assertGreaterEqual(
            sh_ranged, 1,
            f"effective_buffs should carry sustained_hits_ranged >= 1 for "
            f"Cadian Shock Troops led by Castellan when SWEG_CASTELLAN_SH=1, "
            f"got {sh_ranged}",
        )


# ---------------------------------------------------------------------------
# (b) Gate unset (default "0"): no grant
# ---------------------------------------------------------------------------

class TestGateUnset(unittest.TestCase):

    def setUp(self):
        os.environ.pop("SWEG_CASTELLAN_SH", None)
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"
        self._leaders_mod = _reload_leaders()

    def tearDown(self):
        os.environ.pop("SWEG_CASTELLAN_SH", None)
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)
        _reload_leaders()

    def test_lookup_ability_sustained_hits_ranged_is_0_when_gate_unset(self):
        ab = self._leaders_mod.lookup_ability("Cadian Castellan")
        self.assertIsNotNone(ab, "Cadian Castellan must resolve from the registry")
        self.assertEqual(
            ab.sustained_hits_ranged, 0,
            f"sustained_hits_ranged should be 0 when SWEG_CASTELLAN_SH is unset "
            f"(default-off), got {ab.sustained_hits_ranged}",
        )


# ---------------------------------------------------------------------------
# (c) Gate "0": explicitly off — no grant
# ---------------------------------------------------------------------------

class TestGateExplicitOff(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_CASTELLAN_SH"] = "0"
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"
        self._leaders_mod = _reload_leaders()

    def tearDown(self):
        os.environ.pop("SWEG_CASTELLAN_SH", None)
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)
        _reload_leaders()

    def test_lookup_ability_sustained_hits_ranged_is_0_when_gate_explicit_off(self):
        ab = self._leaders_mod.lookup_ability("Cadian Castellan")
        self.assertIsNotNone(ab, "Cadian Castellan must resolve from the registry")
        self.assertEqual(
            ab.sustained_hits_ranged, 0,
            f"sustained_hits_ranged should be 0 when SWEG_CASTELLAN_SH=0, "
            f"got {ab.sustained_hits_ranged}",
        )

    def test_effective_buffs_no_sustained_hits_ranged_when_gate_off(self):
        """
        Gate-off must be byte-identical to the pre-wave-247 arm:
        effective_buffs must not carry any sustained_hits_ranged grant.
        """
        _army, _castellan, shock = _make_army_with_castellan_and_shock_troops()
        leaders_mod = _reload_leaders()
        leaders_mod.bump_buffs_generation()

        buffs = leaders_mod.effective_buffs(shock)
        sh_ranged = buffs.get("sustained_hits_ranged", 0)
        self.assertEqual(
            sh_ranged, 0,
            f"effective_buffs should carry sustained_hits_ranged == 0 for "
            f"Cadian Shock Troops when SWEG_CASTELLAN_SH=0 (gate off), "
            f"got {sh_ranged}",
        )


if __name__ == "__main__":
    unittest.main()
