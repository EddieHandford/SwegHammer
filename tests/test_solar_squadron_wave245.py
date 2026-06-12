"""
Wave 245 lever 2: Lord Solar SQUADRON order reach (gated SWEG_SOLAR_SQUADRON,
default-off).

Tests:

(a) Gate-off (SWEG_SOLAR_SQUADRON=0): Lord Solar's host_keys contains only
    the seven infantry catalog keys — no SQUADRON vehicle keys appended.

(b) Gate-on (SWEG_SOLAR_SQUADRON=1): Lord Solar's host_keys contains both the
    seven infantry keys AND the five SQUADRON vehicle keys.

(c) Gate-on: Lord Solar with no in-range infantry host but an unattended
    Basilisk within reach generates a move intent directed toward the Basilisk.

(d) Gate-off: Lord Solar with no in-range infantry host but a Basilisk within
    reach does NOT seek the Basilisk (behaviour byte-identical to pre-wave-245).
"""

from __future__ import annotations

import os
import importlib
import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(name: str):
    """Build a minimal UnitProfile with the given name."""
    from code.units import UnitProfile
    return UnitProfile(
        name=name, health=1, damage=2, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0,
        range_inches=24,
    )


def _make_army(name: str, profiles_and_positions):
    """Build an army from (profile, position) pairs."""
    from code.army import Army
    army = Army(name)
    for i, (profile, pos) in enumerate(profiles_and_positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[:2]}{i}"
        u.position = pos
    return army


def _empty_map():
    from code.map import Map
    return Map(name="test", width=60.0, height=60.0, objectives=())


def _reload_leaders():
    """Force leaders module to re-evaluate all module-level gates."""
    import code.leaders as leaders_mod
    importlib.reload(leaders_mod)
    return leaders_mod


# ---------------------------------------------------------------------------
# (a) Gate-off: Lord Solar has only the seven infantry host keys
# ---------------------------------------------------------------------------

class TestSolarSquadronGateOff(unittest.TestCase):

    def setUp(self):
        # Pin SWEG_SOLAR_SQUADRON=0 explicitly; also ensure OFFICER_FOLLOW is on
        # so the AM officer registry entries are present (tests the Solar entry).
        os.environ["SWEG_SOLAR_SQUADRON"] = "0"
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_SOLAR_SQUADRON", None)
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_lord_solar_has_only_infantry_hosts_when_gate_off(self):
        leaders_mod = _reload_leaders()

        registry_dict = dict(leaders_mod._REGISTRY)
        self.assertIn("Lord Solar Leontus", registry_dict,
                      "Lord Solar Leontus entry must be present (SWEG_OFFICER_FOLLOW=1)")
        ability = registry_dict["Lord Solar Leontus"]

        squadron_keys = {
            "astra_militarum_leman_russ_battle_tank",
            "astra_militarum_leman_russ_demolisher",
            "astra_militarum_rogal_dorn_battle_tank",
            "astra_militarum_basilisk",
            "astra_militarum_manticore",
        }
        infantry_keys = {
            "astra_militarum_attilan_rough_riders",
            "astra_militarum_cadian_shock_troops",
            "astra_militarum_catachan_jungle_fighters",
            "astra_militarum_death_korps_of_krieg",
            "astra_militarum_death_riders",
            "astra_militarum_kasrkin",
            "astra_militarum_krieg_combat_engineers",
        }
        actual = set(ability.host_keys)
        # Must have all seven infantry keys
        self.assertEqual(
            actual, infantry_keys,
            f"Gate-off: Lord Solar host_keys must be only the seven infantry keys.\n"
            f"  Missing infantry: {infantry_keys - actual}\n"
            f"  Extra/SQUADRON: {actual - infantry_keys}",
        )
        # Must not have any SQUADRON vehicle keys
        found_squadron = actual.intersection(squadron_keys)
        self.assertEqual(
            found_squadron, set(),
            f"Gate-off must not include SQUADRON vehicle keys: {found_squadron}",
        )


# ---------------------------------------------------------------------------
# (b) Gate-on: Lord Solar has infantry + SQUADRON vehicle host keys
# ---------------------------------------------------------------------------

class TestSolarSquadronGateOn(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_SOLAR_SQUADRON"] = "1"
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_SOLAR_SQUADRON", None)
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_lord_solar_has_squadron_keys_when_gate_on(self):
        leaders_mod = _reload_leaders()

        registry_dict = dict(leaders_mod._REGISTRY)
        self.assertIn("Lord Solar Leontus", registry_dict)
        ability = registry_dict["Lord Solar Leontus"]
        actual = set(ability.host_keys)

        squadron_keys = {
            "astra_militarum_leman_russ_battle_tank",
            "astra_militarum_leman_russ_demolisher",
            "astra_militarum_rogal_dorn_battle_tank",
            "astra_militarum_basilisk",
            "astra_militarum_manticore",
        }
        infantry_keys = {
            "astra_militarum_attilan_rough_riders",
            "astra_militarum_cadian_shock_troops",
            "astra_militarum_catachan_jungle_fighters",
            "astra_militarum_death_korps_of_krieg",
            "astra_militarum_death_riders",
            "astra_militarum_kasrkin",
            "astra_militarum_krieg_combat_engineers",
        }
        expected = infantry_keys | squadron_keys
        self.assertEqual(
            actual, expected,
            f"Gate-on: Lord Solar host_keys must be infantry + SQUADRON keys.\n"
            f"  Missing: {expected - actual}\n"
            f"  Extra:   {actual - expected}",
        )

    def test_other_officers_unaffected_by_solar_squadron_gate(self):
        """SWEG_SOLAR_SQUADRON must not alter Cadian Castellan or Ursula Creed host_keys."""
        leaders_mod = _reload_leaders()
        registry_dict = dict(leaders_mod._REGISTRY)

        castellan_ability = registry_dict.get("Cadian Castellan")
        self.assertIsNotNone(castellan_ability, "Cadian Castellan must be in registry")
        castellan_hosts = set(castellan_ability.host_keys)
        # Castellan hosts only Cadian Shock Troops and Kasrkin — no SQUADRON vehicles
        self.assertNotIn("astra_militarum_basilisk", castellan_hosts,
                         "Cadian Castellan must not gain Basilisk as host")
        self.assertNotIn("astra_militarum_manticore", castellan_hosts,
                         "Cadian Castellan must not gain Manticore as host")

        creed_ability = registry_dict.get("Ursula Creed")
        self.assertIsNotNone(creed_ability, "Ursula Creed must be in registry")
        creed_hosts = set(creed_ability.host_keys)
        self.assertNotIn("astra_militarum_basilisk", creed_hosts,
                         "Ursula Creed must not gain Basilisk as host")


# ---------------------------------------------------------------------------
# (c) Gate-on: Lord Solar seeks a Basilisk when no infantry host is in range
# ---------------------------------------------------------------------------

class TestSolarSquadronFollowIntentGateOn(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_SOLAR_SQUADRON"] = "1"
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"
        _reload_leaders()

    def tearDown(self):
        os.environ.pop("SWEG_SOLAR_SQUADRON", None)
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_solar_seeks_basilisk_when_no_infantry_host_in_range(self):
        """
        Lord Solar at (30, 30), Basilisk at (5, 5) — no infantry hosts present.
        Gate-on: _maybe_officer_follow should return a move target toward
        the Basilisk (distance ~35.4\", well beyond 6\" aura range).
        """
        from code.strategy import _maybe_officer_follow

        solar_profile = _make_profile("Lord Solar Leontus")
        basilisk_profile = _make_profile("Basilisk")

        army = _make_army("A", [
            (solar_profile, (30.0, 30.0)),   # Lord Solar — no infantry hosts present
            (basilisk_profile, (5.0, 5.0)),  # Basilisk — SQUADRON vehicle
        ])
        # Assign distinct squad_ids to prevent centroid grouping confusion
        army.units[0].squad_id = 1
        army.units[1].squad_id = 2

        result = _maybe_officer_follow(army.units[0], army)
        self.assertIsNotNone(
            result,
            "Gate-on: Lord Solar with a distant Basilisk and no infantry hosts "
            "must get a move intent toward the Basilisk",
        )
        tx, ty = result
        # Result should be near the Basilisk at (5, 5)
        self.assertAlmostEqual(tx, 5.0, places=1)
        self.assertAlmostEqual(ty, 5.0, places=1)

    def test_pick_move_intent_returns_officer_follow_toward_basilisk(self):
        """End-to-end: pick_move_intent tags the intent as officer_follow."""
        from code.strategy import pick_move_intent

        solar_profile = _make_profile("Lord Solar Leontus")
        basilisk_profile = _make_profile("Basilisk")
        enemy_profile = _make_profile("Chaos Space Marines")

        friendly = _make_army("A", [
            (solar_profile, (30.0, 30.0)),
            (basilisk_profile, (5.0, 5.0)),
        ])
        enemy = _make_army("B", [(enemy_profile, (55.0, 30.0))])
        map_ = _empty_map()

        _, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertEqual(
            intent, "officer_follow",
            "Gate-on: Lord Solar drifted from SQUADRON vehicle must return "
            "officer_follow intent",
        )


# ---------------------------------------------------------------------------
# (d) Gate-off: Lord Solar does NOT seek a Basilisk
# ---------------------------------------------------------------------------

class TestSolarSquadronFollowIntentGateOff(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_SOLAR_SQUADRON"] = "0"
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"
        _reload_leaders()

    def tearDown(self):
        os.environ.pop("SWEG_SOLAR_SQUADRON", None)
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_solar_does_not_seek_basilisk_when_gate_off(self):
        """
        Gate-off: no infantry hosts present, Basilisk is the only companion.
        _maybe_officer_follow must return None — no SQUADRON-seeking.
        """
        from code.strategy import _maybe_officer_follow

        solar_profile = _make_profile("Lord Solar Leontus")
        basilisk_profile = _make_profile("Basilisk")

        army = _make_army("A", [
            (solar_profile, (30.0, 30.0)),
            (basilisk_profile, (5.0, 5.0)),
        ])
        army.units[0].squad_id = 1
        army.units[1].squad_id = 2

        result = _maybe_officer_follow(army.units[0], army)
        self.assertIsNone(
            result,
            "Gate-off: Lord Solar must NOT get a SQUADRON follow intent when "
            "SWEG_SOLAR_SQUADRON=0 (only infantry hosts are eligible)",
        )

    def test_pick_move_intent_not_officer_follow_for_basilisk_when_gate_off(self):
        """End-to-end gate-off: Basilisk does not trigger officer_follow."""
        from code.strategy import pick_move_intent

        solar_profile = _make_profile("Lord Solar Leontus")
        basilisk_profile = _make_profile("Basilisk")
        enemy_profile = _make_profile("Chaos Space Marines")

        friendly = _make_army("A", [
            (solar_profile, (30.0, 30.0)),
            (basilisk_profile, (5.0, 5.0)),
        ])
        enemy = _make_army("B", [(enemy_profile, (55.0, 30.0))])
        map_ = _empty_map()

        _, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertNotEqual(
            intent, "officer_follow",
            "Gate-off: Lord Solar must NOT return officer_follow intent toward "
            "a Basilisk when SWEG_SOLAR_SQUADRON=0",
        )


if __name__ == "__main__":
    unittest.main()
