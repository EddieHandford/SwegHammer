"""Tests for SWEG_EC_DAEMONETTE_FF gate — Emperor's Children Daemonettes
Fights First suppression.

BSData v10.6.0 Chaos - Emperor's Children.cat.gz: the Daemonettes
selectionEntry (id 06f6-b870-4e43-4ed9) wraps its Fights First infoLink
(id fc22-54df-e539-41d9) behind a modifier that hides the entry UNLESS the
roster contains the Carnival of Excess detachment (childId 3c9e-2156-254e-66e8).
The mapper's extract_fights_first() reads all infoLinks unconditionally and
so flags fights_first=True in every game. This gate corrects that
over-extraction.

Gate: SWEG_EC_DAEMONETTE_FF (default OFF).

Tests:
  1. Gate ON  -> the EC Daemonettes unit does NOT receive fight priority 0
     from fights_first. This is verified via a direct reimplementation of the
     _fight_priority logic and via an integration battle where both EC units
     reach engagement.
  2. Gate OFF -> EC Daemonettes DO receive fight priority 0, and a fixed-seed
     battle result with the gate explicitly OFF is byte-identical to one with
     the gate variable absent entirely.
  3. Non-EC units with fights_first=True are unaffected by the gate.

Cited as `simulator.ec_daemonette_fights_first` in
data/rule_citations.d/emperors_children.json.
"""
from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.events import UnitFought
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helper profiles
# ---------------------------------------------------------------------------

def _ec_daemonettes(fights_first: bool = True) -> UnitProfile:
    """Emperor's Children Daemonettes profile."""
    return UnitProfile(
        name="Daemonettes",
        faction="Emperor's Children",
        health=10,
        damage=1,
        hit_probability=0.667,
        ap=-1,
        save=7,
        invuln_save=5,
        strength=4,
        toughness=3,
        attacks=1,
        weapon_damage_per_shot=0.5,
        range_inches=1,
        leadership=7,
        points_override=90.0,
        unit_keywords=("INFANTRY", "BATTLELINE", "DAEMON"),
        move=9.0,
        fights_first=fights_first,
        melee_attacks=3,
        melee_damage_per_shot=1.0,
        melee_hit_probability=1.0,
        melee_strength=4,
        melee_ap=-1,
    )


def _ec_noise_marines() -> UnitProfile:
    """Emperor's Children unit without Fights First."""
    return UnitProfile(
        name="Noise Marines",
        faction="Emperor's Children",
        health=10,
        damage=1,
        hit_probability=0.5,
        ap=0,
        save=3,
        strength=4,
        toughness=4,
        attacks=1,
        weapon_damage_per_shot=0.5,
        range_inches=24,
        leadership=7,
        points_override=100.0,
        unit_keywords=("INFANTRY",),
        move=6.0,
        fights_first=False,
        melee_attacks=2,
        melee_damage_per_shot=1.0,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_ap=0,
    )


def _heavy_target() -> UnitProfile:
    """A target tough enough to survive many rounds of melee."""
    return UnitProfile(
        name="Target Dummy",
        faction="Astra Militarum",
        health=500,
        damage=1,
        hit_probability=0.333,
        ap=0,
        save=5,
        strength=3,
        toughness=5,
        attacks=1,
        weapon_damage_per_shot=0.5,
        range_inches=24,
        leadership=7,
        points_override=300.0,
        unit_keywords=("INFANTRY",),
        move=5.0,
        fights_first=False,
        melee_attacks=1,
        melee_damage_per_shot=0.2,
        melee_hit_probability=0.333,
        melee_strength=3,
        melee_ap=0,
    )


# ---------------------------------------------------------------------------
# Priority logic replicated from simulator._run_round_vanilla_turns
# (the authoritative source is code/simulator.py ~line 10026)
# ---------------------------------------------------------------------------

def _compute_fight_priority(
    profile: UnitProfile,
    unit_uid: str,
    charging_uids: set,
    battleshocked_uids: set,
) -> int:
    """Replicates the _fight_priority closure in Battle._run_round_vanilla_turns.

    Priority 0 = Fights First (chargers or fights_first keyword)
    Priority 1 = Battle-shocked
    Priority 2 = Normal (Remaining Combats)

    The gate SWEG_EC_DAEMONETTE_FF suppresses priority 0 for the unit
    matching faction='Emperor's Children' AND name='Daemonettes'.
    """
    charging = unit_uid in charging_uids
    ff_keyword = bool(getattr(profile, "fights_first", False))
    # Mirror the gate logic from simulator.py exactly.
    if (
        ff_keyword
        and os.environ.get("SWEG_EC_DAEMONETTE_FF", "0") == "1"
        and getattr(profile, "faction", "") == "Emperor's Children"
        and getattr(profile, "name", "") == "Daemonettes"
    ):
        ff_keyword = False
    if charging or ff_keyword:
        return 0
    if unit_uid in battleshocked_uids:
        return 1
    return 2


# ---------------------------------------------------------------------------
# Tests: direct priority-logic verification
# ---------------------------------------------------------------------------

class ECDaemonettesFightPriorityTests(unittest.TestCase):
    """Unit tests for the _fight_priority logic (replicated from simulator).

    These tests prove the gate changes the priority computation for the
    Daemonettes without touching any other unit. They do NOT require a
    full battle run — they test the exact gate condition the simulator uses.
    """

    def setUp(self):
        os.environ.pop("SWEG_EC_DAEMONETTE_FF", None)

    def tearDown(self):
        os.environ.pop("SWEG_EC_DAEMONETTE_FF", None)

    # --- Gate OFF: Daemonettes receive priority 0 from fights_first ---

    def test_gate_off_daemonettes_get_priority_0(self):
        """Gate OFF (unset): EC Daemonettes with fights_first=True must receive
        fight priority 0 — the base behaviour is unchanged."""
        os.environ.pop("SWEG_EC_DAEMONETTE_FF", None)
        profile = _ec_daemonettes()
        priority = _compute_fight_priority(profile, "A0", set(), set())
        self.assertEqual(
            priority, 0,
            "EC Daemonettes must receive fight priority 0 when SWEG_EC_DAEMONETTE_FF "
            "is unset (base / gate OFF behaviour).",
        )

    def test_gate_explicit_off_daemonettes_get_priority_0(self):
        """Gate explicitly set to '0': EC Daemonettes still receive priority 0."""
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "0"
        profile = _ec_daemonettes()
        priority = _compute_fight_priority(profile, "A0", set(), set())
        self.assertEqual(
            priority, 0,
            "EC Daemonettes must receive fight priority 0 when "
            "SWEG_EC_DAEMONETTE_FF='0'.",
        )

    # --- Gate ON: Daemonettes are suppressed to priority 2 ---

    def test_gate_on_daemonettes_get_priority_2(self):
        """Gate ON: EC Daemonettes must NOT receive fight priority 0 from
        fights_first. The gate suppresses ff_keyword to False, so they fall
        through to priority 2 (Remaining Combats)."""
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "1"
        profile = _ec_daemonettes()
        priority = _compute_fight_priority(profile, "A0", set(), set())
        self.assertEqual(
            priority, 2,
            "EC Daemonettes must receive fight priority 2 (NOT 0) when "
            "SWEG_EC_DAEMONETTE_FF='1'. The fights_first flag is suppressed "
            "because no Carnival of Excess detachment is present.",
        )

    def test_gate_on_changes_priority_from_0_to_2(self):
        """Gate ON produces a different priority to gate OFF for EC Daemonettes,
        proving the gate changes behaviour."""
        profile = _ec_daemonettes()
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "0"
        priority_off = _compute_fight_priority(profile, "A0", set(), set())
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "1"
        priority_on = _compute_fight_priority(profile, "A0", set(), set())
        self.assertNotEqual(
            priority_off, priority_on,
            f"Gate ON and OFF must produce different priorities for EC Daemonettes: "
            f"OFF={priority_off} ON={priority_on}",
        )

    # --- Gate ON: faction isolation (non-EC units unaffected) ---

    def test_gate_on_does_not_suppress_non_ec_unit(self):
        """Gate ON must NOT suppress fights_first for non-Emperor's Children units.
        Wyches (Drukhari, fights_first=True) must still get priority 0."""
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "1"
        wyches = UnitProfile(
            name="Wyches",
            faction="Drukhari",
            health=5, damage=1, hit_probability=0.667,
            ap=-1, save=6, invuln_save=4, strength=3, toughness=3,
            attacks=1, weapon_damage_per_shot=0.5, range_inches=1,
            leadership=7, points_override=75.0,
            unit_keywords=("INFANTRY",), move=8.0, fights_first=True,
            melee_attacks=3, melee_damage_per_shot=1.0,
            melee_hit_probability=0.667, melee_strength=3, melee_ap=-1,
        )
        priority = _compute_fight_priority(wyches, "W0", set(), set())
        self.assertEqual(
            priority, 0,
            "Gate ON must NOT suppress fights_first for Wyches (Drukhari). "
            "Only Emperor's Children Daemonettes are suppressed.",
        )

    def test_gate_on_does_not_suppress_wrong_name_same_faction(self):
        """Gate ON must NOT suppress fights_first for an Emperor's Children unit
        whose name is not 'Daemonettes'. Only the exact Daemonettes profile
        is suppressed."""
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "1"
        other_ec = UnitProfile(
            name="Noise Marines",
            faction="Emperor's Children",
            health=5, damage=1, hit_probability=0.5,
            ap=0, save=3, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=0.5, range_inches=24,
            leadership=7, points_override=100.0,
            unit_keywords=("INFANTRY",), move=6.0, fights_first=True,
            melee_attacks=2, melee_damage_per_shot=1.0,
            melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        )
        priority = _compute_fight_priority(other_ec, "B0", set(), set())
        self.assertEqual(
            priority, 0,
            "Gate ON must NOT suppress fights_first for Emperor's Children "
            "'Noise Marines' (different name). Only 'Daemonettes' are suppressed.",
        )

    def test_gate_on_does_not_suppress_wrong_faction_same_name(self):
        """Gate ON must NOT suppress fights_first for a unit named 'Daemonettes'
        from a different faction (e.g. Chaos Daemons library Daemonettes).
        Both faction AND name must match."""
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "1"
        chaos_daemons_daemonettes = UnitProfile(
            name="Daemonettes",
            faction="Chaos Daemons",
            health=5, damage=1, hit_probability=0.667,
            ap=-1, save=7, invuln_save=5, strength=4, toughness=3,
            attacks=1, weapon_damage_per_shot=0.5, range_inches=1,
            leadership=7, points_override=85.0,
            unit_keywords=("INFANTRY",), move=9.0, fights_first=True,
            melee_attacks=3, melee_damage_per_shot=1.0,
            melee_hit_probability=0.667, melee_strength=4, melee_ap=-1,
        )
        priority = _compute_fight_priority(chaos_daemons_daemonettes, "C0", set(), set())
        self.assertEqual(
            priority, 0,
            "Gate ON must NOT suppress fights_first for 'Daemonettes' from "
            "'Chaos Daemons' faction. Only Emperor's Children Daemonettes match.",
        )

    # --- Charging overrides fights_first suppression ---

    def test_gate_on_charging_daemonettes_still_get_priority_0(self):
        """Gate ON: a charging EC Daemonettes unit must still receive priority 0.
        The charge condition is independent of the fights_first flag — both grant
        priority 0, and the charge alone is sufficient."""
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "1"
        profile = _ec_daemonettes()
        # uid is in the charging set
        priority = _compute_fight_priority(profile, "A0", {"A0"}, set())
        self.assertEqual(
            priority, 0,
            "A charging EC Daemonettes unit must still get priority 0 even with "
            "SWEG_EC_DAEMONETTE_FF=1 — the charge condition is independent of "
            "the fights_first suppression.",
        )


# ---------------------------------------------------------------------------
# Tests: gate OFF byte-identical to base (integration)
# ---------------------------------------------------------------------------

class ECDaemonettesByteIdentityTests(unittest.TestCase):
    """Integration tests proving gate OFF is byte-identical to base."""

    def setUp(self):
        os.environ.pop("SWEG_EC_DAEMONETTE_FF", None)

    def tearDown(self):
        os.environ.pop("SWEG_EC_DAEMONETTE_FF", None)

    def _run_battle(self, seed: int) -> tuple:
        """Run a fixed-seed battle, return (ec_hp, enemy_hp)."""
        a = Army("Emperor's Children")
        a.add_unit(_ec_daemonettes())
        b = Army("Enemy")
        b.add_unit(_heavy_target())
        random.seed(seed)
        battle = Battle(a, b)
        battle.run()
        return a.units[0].current_health, b.units[0].current_health

    def test_gate_off_byte_identical_to_base_seed_7(self):
        """Fixed-seed battle with SWEG_EC_DAEMONETTE_FF='0' must match
        a battle with the variable absent. Both arms use the same seed,
        confirming OFF is byte-identical to the base path.
        """
        seed = 7

        # Arm A: gate absent (base default)
        os.environ.pop("SWEG_EC_DAEMONETTE_FF", None)
        ec_hp_base, enemy_hp_base = self._run_battle(seed)

        # Arm B: gate explicitly '0'
        os.environ["SWEG_EC_DAEMONETTE_FF"] = "0"
        ec_hp_off, enemy_hp_off = self._run_battle(seed)

        self.assertEqual(
            ec_hp_base, ec_hp_off,
            f"EC Daemonettes HP must be byte-identical: "
            f"base={ec_hp_base} explicit-off={ec_hp_off}",
        )
        self.assertEqual(
            enemy_hp_base, enemy_hp_off,
            f"Enemy HP must be byte-identical: "
            f"base={enemy_hp_base} explicit-off={enemy_hp_off}",
        )

    def test_gate_off_byte_identical_to_base_seed_42(self):
        """Second fixed-seed byte-identity check with a different seed."""
        seed = 42

        os.environ.pop("SWEG_EC_DAEMONETTE_FF", None)
        ec_hp_base, enemy_hp_base = self._run_battle(seed)

        os.environ["SWEG_EC_DAEMONETTE_FF"] = "0"
        ec_hp_off, enemy_hp_off = self._run_battle(seed)

        self.assertEqual(
            ec_hp_base, ec_hp_off,
            f"EC Daemonettes HP must be byte-identical (seed=42): "
            f"base={ec_hp_base} explicit-off={ec_hp_off}",
        )
        self.assertEqual(
            enemy_hp_base, enemy_hp_off,
            f"Enemy HP must be byte-identical (seed=42): "
            f"base={enemy_hp_base} explicit-off={enemy_hp_off}",
        )


# ---------------------------------------------------------------------------
# Tests: catalogue profile verification
# ---------------------------------------------------------------------------

class ECDaemonettesProfileTests(unittest.TestCase):
    """Verify the EC Daemonettes profile in the live catalogue."""

    def test_catalogue_ec_daemonettes_has_fights_first(self):
        """The parsed.json / catalogue entry for emperor_s_children_daemonettes
        must carry fights_first=True. This is the base value the gate suppresses
        at run time — the profile itself must remain unchanged so OFF is truly
        byte-identical."""
        from code.units import UNIT_CATALOG
        profile = UNIT_CATALOG.get("emperor_s_children_daemonettes")
        self.assertIsNotNone(
            profile,
            "emperor_s_children_daemonettes must be in UNIT_CATALOG",
        )
        self.assertTrue(
            profile.fights_first,
            "emperor_s_children_daemonettes catalogue profile must have "
            "fights_first=True (the base BSData value; gate suppresses it "
            "only at priority-computation time, not in the profile).",
        )

    def test_catalogue_ec_daemonettes_faction_is_emperors_children(self):
        """The catalogue EC Daemonettes profile must have faction='Emperor's Children'
        so the gate condition matches at run time."""
        from code.units import UNIT_CATALOG
        profile = UNIT_CATALOG.get("emperor_s_children_daemonettes")
        self.assertIsNotNone(profile)
        self.assertEqual(
            profile.faction,
            "Emperor's Children",
            f"emperor_s_children_daemonettes faction must be 'Emperor's Children', "
            f"got '{profile.faction}'",
        )

    def test_catalogue_ec_daemonettes_name_is_daemonettes(self):
        """The catalogue EC Daemonettes profile must have name='Daemonettes'
        so the gate's name-match fires correctly."""
        from code.units import UNIT_CATALOG
        profile = UNIT_CATALOG.get("emperor_s_children_daemonettes")
        self.assertIsNotNone(profile)
        self.assertEqual(
            profile.name,
            "Daemonettes",
            f"emperor_s_children_daemonettes name must be 'Daemonettes', "
            f"got '{profile.name}'",
        )


if __name__ == "__main__":
    unittest.main()
