"""
Wave 244 lever 3: Astra Militarum officer leader-attachment registry +
stay-near piloting (gated SWEG_OFFICER_FOLLOW, default-on since the
wave-244 adoption; =0 is the kill-switch).

Four tests:

(a) Gate-off (kill-switch, SWEG_OFFICER_FOLLOW=0): _REGISTRY has NO Astra
    Militarum officer entries and pick_move_intent output is unchanged for
    an officer-named unit.

(b) Gate-on: exactly the four expected entries are present in _REGISTRY with
    correct host_keys.

(c) Gate-on: a drifted AM OFFICER beyond OFFICER_AURA_RANGE returns the
    officer_follow intent directed toward the nearest host squad.

(d) Gate-on: an AM OFFICER already within OFFICER_AURA_RANGE does NOT trigger
    the follow hook (returns a normal movement intent, not officer_follow).
"""

from __future__ import annotations

import os
import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_shooty_profile(name: str = "Cadian Shock Troops"):
    """A ranged unit profile named after a real UNIT_CATALOG entry."""
    from code.units import UnitProfile
    return UnitProfile(
        name=name, health=1, damage=2, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
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


# ---------------------------------------------------------------------------
# (a) Gate-off: no AM entries, pick_move_intent unchanged
# ---------------------------------------------------------------------------

class TestGateOff(unittest.TestCase):

    def setUp(self):
        # Pin the gate off explicitly — since the wave-244 default flip an
        # UNSET environment means gate-ON, so the off-arm needs "0".
        os.environ["SWEG_OFFICER_FOLLOW"] = "0"

    def tearDown(self):
        # Restore the unset (default-on) state for the rest of the suite.
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_registry_has_no_astra_militarum_officer_entries_when_gate_off(self):
        # Reload leaders so the module-level gate re-evaluates.
        import importlib
        import code.leaders as leaders_mod
        importlib.reload(leaders_mod)

        am_officer_names = {
            "Cadian Castellan", "Cadian Command Squad",
            "Ursula Creed", "Lord Solar Leontus",
        }
        registry_keys = {k for k, _ in leaders_mod._REGISTRY}
        found = registry_keys.intersection(am_officer_names)
        self.assertEqual(
            found, set(),
            f"Expected no AM officer entries in _REGISTRY when gate is off, "
            f"but found: {found}",
        )

    def test_pick_move_intent_unchanged_for_officer_named_unit_when_gate_off(self):
        """An officer-named unit should NOT get officer_follow intent when gate is off."""
        from code.strategy import pick_move_intent

        officer_profile = _make_shooty_profile("Cadian Castellan")
        host_profile = _make_shooty_profile("Cadian Shock Troops")

        # Officer at (30, 30), host squad far away at (0, 0)
        officer_army = _make_army("A", [
            (officer_profile, (30.0, 30.0)),
            (host_profile, (0.0, 0.0)),
        ])
        enemy_army = _make_army("B", [(host_profile, (55.0, 30.0))])
        map_ = _empty_map()

        _, intent = pick_move_intent(
            officer_army.units[0], officer_army, enemy_army, map_,
        )
        self.assertNotEqual(intent, "officer_follow",
                            "Gate-off must not produce officer_follow intent")


# ---------------------------------------------------------------------------
# (b) Gate-on: 4 entries present with correct host_keys
# ---------------------------------------------------------------------------

class TestGateOnRegistry(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_four_am_officer_entries_present_when_gate_on(self):
        import importlib
        import code.leaders as leaders_mod
        importlib.reload(leaders_mod)

        registry_dict = dict(leaders_mod._REGISTRY)

        expected_officers = {
            "Cadian Castellan", "Cadian Command Squad",
            "Ursula Creed", "Lord Solar Leontus",
        }
        found = expected_officers.intersection(set(registry_dict.keys()))
        self.assertEqual(
            found, expected_officers,
            f"Missing AM officer entries in _REGISTRY: "
            f"{expected_officers - found}",
        )

    def test_cadian_castellan_host_keys(self):
        import importlib
        import code.leaders as leaders_mod
        importlib.reload(leaders_mod)

        registry_dict = dict(leaders_mod._REGISTRY)
        ability = registry_dict["Cadian Castellan"]
        self.assertIn("astra_militarum_cadian_shock_troops", ability.host_keys)
        self.assertIn("astra_militarum_kasrkin", ability.host_keys)

    def test_cadian_command_squad_host_keys(self):
        import importlib
        import code.leaders as leaders_mod
        importlib.reload(leaders_mod)

        registry_dict = dict(leaders_mod._REGISTRY)
        ability = registry_dict["Cadian Command Squad"]
        self.assertIn("astra_militarum_cadian_shock_troops", ability.host_keys)
        # Command Squad only attaches to Cadian Shock Troops (per BSData Leader text)
        self.assertNotIn("astra_militarum_kasrkin", ability.host_keys,
                         "Cadian Command Squad should only attach to Cadian Shock Troops")

    def test_ursula_creed_host_keys(self):
        import importlib
        import code.leaders as leaders_mod
        importlib.reload(leaders_mod)

        registry_dict = dict(leaders_mod._REGISTRY)
        ability = registry_dict["Ursula Creed"]
        self.assertIn("astra_militarum_cadian_shock_troops", ability.host_keys)
        self.assertIn("astra_militarum_kasrkin", ability.host_keys)

    def test_lord_solar_leontus_host_keys(self):
        import importlib
        import code.leaders as leaders_mod
        importlib.reload(leaders_mod)

        registry_dict = dict(leaders_mod._REGISTRY)
        ability = registry_dict["Lord Solar Leontus"]
        expected_hosts = {
            "astra_militarum_attilan_rough_riders",
            "astra_militarum_cadian_shock_troops",
            "astra_militarum_catachan_jungle_fighters",
            "astra_militarum_death_korps_of_krieg",
            "astra_militarum_death_riders",
            "astra_militarum_kasrkin",
            "astra_militarum_krieg_combat_engineers",
        }
        actual = set(ability.host_keys)
        self.assertEqual(
            actual, expected_hosts,
            f"Lord Solar Leontus host_keys mismatch.\n"
            f"  Missing: {expected_hosts - actual}\n"
            f"  Extra:   {actual - expected_hosts}",
        )


# ---------------------------------------------------------------------------
# (c) Gate-on: drifted officer beyond 6" returns officer_follow intent
# ---------------------------------------------------------------------------

class TestOfficerFollowDrifted(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"
        # Reload leaders so gate takes effect in _maybe_officer_follow
        import importlib
        import code.leaders
        importlib.reload(code.leaders)

    def tearDown(self):
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_drifted_castellan_returns_officer_follow(self):
        from code.strategy import _maybe_officer_follow

        officer_profile = _make_shooty_profile("Cadian Castellan")
        host_profile = _make_shooty_profile("Cadian Shock Troops")

        # Officer at (30, 30), host squad models at (0, 0) and (1, 0) —
        # centroid (0.5, 0) is ~29.5" away, well beyond OFFICER_AURA_RANGE.
        army = _make_army("A", [
            (officer_profile, (30.0, 30.0)),
            (host_profile, (0.0, 0.0)),
            (host_profile, (1.0, 0.0)),
        ])
        officer_unit = army.units[0]
        # Assign the host models to the same squad_id so centroid grouping works
        army.units[1].squad_id = 10
        army.units[2].squad_id = 10

        result = _maybe_officer_follow(officer_unit, army)
        self.assertIsNotNone(result, "Expected a move-target for a drifted officer")
        # The returned position should be near the host squad centroid (0.5, 0)
        tx, ty = result
        self.assertAlmostEqual(tx, 0.5, places=1)
        self.assertAlmostEqual(ty, 0.0, places=1)

    def test_pick_move_intent_returns_officer_follow_intent_when_drifted(self):
        from code.strategy import pick_move_intent

        officer_profile = _make_shooty_profile("Cadian Castellan")
        host_profile = _make_shooty_profile("Cadian Shock Troops")
        enemy_profile = _make_shooty_profile("Some Enemy")

        # Officer far from host, both armies present
        friendly = _make_army("A", [
            (officer_profile, (30.0, 30.0)),  # officer, drifted
            (host_profile, (0.0, 0.0)),       # host squad
        ])
        enemy = _make_army("B", [(enemy_profile, (55.0, 30.0))])
        map_ = _empty_map()

        _, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertEqual(intent, "officer_follow",
                         "Drifted AM officer should return officer_follow intent")


# ---------------------------------------------------------------------------
# (d) Gate-on: officer within 6" does NOT trigger follow hook
# ---------------------------------------------------------------------------

class TestOfficerFollowAlreadyNear(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_OFFICER_FOLLOW"] = "1"
        import importlib
        import code.leaders
        importlib.reload(code.leaders)

    def tearDown(self):
        os.environ.pop("SWEG_OFFICER_FOLLOW", None)

    def test_officer_within_aura_range_does_not_trigger_follow(self):
        from code.strategy import _maybe_officer_follow

        officer_profile = _make_shooty_profile("Cadian Castellan")
        host_profile = _make_shooty_profile("Cadian Shock Troops")

        # Officer at (5, 5), host squad at (8, 5) — exactly 3" away, inside 6"
        army = _make_army("A", [
            (officer_profile, (5.0, 5.0)),
            (host_profile, (8.0, 5.0)),
        ])
        officer_unit = army.units[0]

        result = _maybe_officer_follow(officer_unit, army)
        self.assertIsNone(result,
                          "Officer within OFFICER_AURA_RANGE should return None "
                          "(no follow needed)")

    def test_pick_move_intent_not_officer_follow_when_already_near(self):
        from code.strategy import pick_move_intent

        officer_profile = _make_shooty_profile("Cadian Castellan")
        host_profile = _make_shooty_profile("Cadian Shock Troops")
        enemy_profile = _make_shooty_profile("Some Enemy")

        # Officer 3" from host squad — within OFFICER_AURA_RANGE
        friendly = _make_army("A", [
            (officer_profile, (5.0, 5.0)),   # officer
            (host_profile, (8.0, 5.0)),       # host, 3" away
        ])
        enemy = _make_army("B", [(enemy_profile, (55.0, 30.0))])
        map_ = _empty_map()

        _, intent = pick_move_intent(
            friendly.units[0], friendly, enemy, map_,
        )
        self.assertNotEqual(intent, "officer_follow",
                            "Officer already within aura range must not return "
                            "officer_follow intent")


if __name__ == "__main__":
    unittest.main()
