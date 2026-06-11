"""Wave 236 regression tests: First Rank, Fire! Second Rank, Fire! corrected from
a wrong-stat plus-one-to-hit proxy to a faithful attack-count uplift on Rapid Fire
weapons.

Verbatim rule (Wahapedia Astra Militarum faction page + BSData Library cache,
cross-checked 2026-06-11):
    "Improve the Attacks characteristic of Rapid Fire weapons equipped by models
    in this unit by 1."

The rule text has no range condition, so the +1 applies at all ranges.

Assertions:
1. _apply_order(ORDER_FRFSRF) sets transient_frfsrf_active = True and does NOT
   set transient_plus_one_to_hit_shooting (the old wrong-stat proxy).
2. A Rapid Fire 1 weapon with the flag yields +1 attack at long range:
   base attacks 1 -> 2 expected kills (with all dice forced to pass).
3. A Rapid Fire 1 weapon with the flag yields +1 attack at half range in
   ADDITION to the normal half-range Rapid Fire bonus:
   base 1 + RF 1 + FRFSRF 1 = 3 expected kills (all dice forced to pass).
4. A non-rapid-fire weapon is unchanged when the flag is set (rapid_fire == 0).
5. _clear_transient_stratagem_flags resets transient_frfsrf_active to False
   (one-round scope verified).
"""

from __future__ import annotations

import unittest
import unittest.mock

from code.army import Army
from code.map import Map, Objective
from code.orders import (
    AM_OFFICER_NAMES,
    OFFICER_ORDER_COUNTS,
    ORDER_FRFSRF,
    ORDER_TAKE_AIM,
    _apply_order,
    dispatch_orders,
)
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _lasgun_profile(name: str = "Cadian") -> UnitProfile:
    """A Lasgun-style profile: Rapid Fire 1, 1 attack, Ballistic Skill 4+.

    With all dice forced to 4 (passes BS 4+, wounds on S10 vs T3 at 2+,
    fails save at 7+), each attack produces exactly 1.0 expected damage,
    so the total damage count equals n_attacks.
    """
    return UnitProfile(
        name=name,
        health=1,
        damage=1,
        hit_probability=0.5,      # BS 4+ (die >= 4 hits)
        ap=0,
        save=7,                   # 7+ = auto-fail save, every wound gets through
        strength=10,              # S10 vs T3 = 2+ wound (die >= 2 wounds)
        toughness=3,
        attacks=1,                # base 1 attack
        weapon_damage_per_shot=1.0,
        range_inches=24,
        rapid_fire=1,             # Rapid Fire 1 — canonical Lasgun profile
        points_override=10.0,
        faction="Astra Militarum",
        unit_keywords=("INFANTRY", "BATTLELINE"),
    )


def _non_rf_profile(name: str = "NonRF") -> UnitProfile:
    """A non-Rapid-Fire profile (rapid_fire=0) with 2 base attacks.

    Used to verify the FRFSRF flag only fires on Rapid Fire weapons.
    """
    return UnitProfile(
        name=name,
        health=1,
        damage=1,
        hit_probability=0.5,
        ap=0,
        save=7,
        strength=10,
        toughness=3,
        attacks=2,                # 2 base attacks, no Rapid Fire
        weapon_damage_per_shot=1.0,
        range_inches=24,
        rapid_fire=0,             # NOT a Rapid Fire weapon
        points_override=10.0,
        faction="Astra Militarum",
        unit_keywords=("INFANTRY", "BATTLELINE"),
    )


def _sponge_target(name: str = "Target") -> UnitProfile:
    """A high-health target that will not die during a single attack call.

    With save=7+ and all dice forced to 4, every attack lands — total damage
    returned equals n_attacks exactly (no early-death truncation).
    """
    return UnitProfile(
        name=name,
        health=1000,
        damage=0,
        hit_probability=0.5,
        attacks=0,
        range_inches=0,
        save=7,
        toughness=3,
        strength=3,
        ap=0,
        weapon_damage_per_shot=0.0,
        points_override=100.0,
    )


def _make_battle_pair(attacker_profile: UnitProfile) -> tuple:
    """Build an Army pair and a Battle around attacker_profile.

    Returns (battle, attacker_unit, defender_unit).
    """
    a = Army("Attacker")
    a.add_unit(attacker_profile)
    b = Army("Defender")
    b.add_unit(_sponge_target())
    battle = Battle(a, b, verbose=False)
    battle._assign_uids()
    return battle, a.units[0], b.units[0]


# ---------------------------------------------------------------------------
# Test group 1: Order routing
# ---------------------------------------------------------------------------

class TestFRFSRFOrderRouting(unittest.TestCase):
    """_apply_order sets the correct flag and not the old wrong-stat proxy."""

    def setUp(self) -> None:
        _, self.unit, _ = _make_battle_pair(_lasgun_profile())

    def test_frfsrf_sets_transient_frfsrf_active(self) -> None:
        self.assertFalse(
            self.unit.transient_frfsrf_active,
            "transient_frfsrf_active must start False",
        )
        _apply_order(self.unit, ORDER_FRFSRF)
        self.assertTrue(
            self.unit.transient_frfsrf_active,
            "transient_frfsrf_active must be True after ORDER_FRFSRF is applied "
            "(wave 236 fix: faithful +1 attack on Rapid Fire weapons)",
        )

    def test_frfsrf_does_not_set_plus_one_to_hit(self) -> None:
        _apply_order(self.unit, ORDER_FRFSRF)
        self.assertFalse(
            self.unit.transient_plus_one_to_hit_shooting,
            "transient_plus_one_to_hit_shooting must NOT be set by ORDER_FRFSRF — "
            "that was the wrong-stat proxy removed in wave 236",
        )

    def test_take_aim_still_sets_plus_one_to_hit(self) -> None:
        """Regression guard: Take Aim! still routes through the hit flag."""
        _apply_order(self.unit, ORDER_TAKE_AIM)
        self.assertTrue(
            self.unit.transient_plus_one_to_hit_shooting,
            "Take Aim! must still set transient_plus_one_to_hit_shooting "
            "(only FRFSRF changed in wave 236)",
        )
        self.assertFalse(
            self.unit.transient_frfsrf_active,
            "Take Aim! must NOT set transient_frfsrf_active",
        )


# ---------------------------------------------------------------------------
# Test group 2: Attack count — Rapid Fire weapon at long and half range
# ---------------------------------------------------------------------------

class TestFRFSRFAttackCountRapidFire(unittest.TestCase):
    """The flag adds exactly +1 attack for Rapid Fire weapons at ALL ranges.

    All dice are forced to 4 via unittest.mock.patch on random.randint so
    every hit/wound/save roll is deterministic (pass BS 4+ / wound S10 T3 2+ /
    fail save 7+), giving total damage == n_attacks without RNG noise.
    """

    def _dmg(self, attacker_unit, defender_unit, distance: float) -> float:
        """Roll the attack with all dice == 4 and return total damage."""
        with unittest.mock.patch("random.randint", return_value=4):
            return attacker_unit.attack(defender_unit, distance=distance)

    def test_rapid_fire_long_range_no_flag_one_attack(self) -> None:
        """Baseline: RF-1 weapon at long range (outside half range) fires 1 attack."""
        _, att, dfn = _make_battle_pair(_lasgun_profile())
        dmg = self._dmg(att, dfn, distance=30.0)
        self.assertEqual(
            dmg, 1.0,
            f"RF-1 weapon at 30\" without FRFSRF should fire 1 attack, got {dmg}",
        )

    def test_rapid_fire_long_range_with_flag_two_attacks(self) -> None:
        """FRFSRF flag adds +1 attack at long range (verbatim rule: no range condition)."""
        _, att, dfn = _make_battle_pair(_lasgun_profile())
        att.transient_frfsrf_active = True
        dmg = self._dmg(att, dfn, distance=30.0)
        self.assertEqual(
            dmg, 2.0,
            f"RF-1 weapon at 30\" WITH FRFSRF should fire 2 attacks (1 base + 1 FRFSRF), "
            f"got {dmg}. Rule text has no range condition.",
        )

    def test_rapid_fire_half_range_no_flag_two_attacks(self) -> None:
        """Baseline: RF-1 at half range fires 2 attacks (1 base + 1 RF half-range bonus)."""
        _, att, dfn = _make_battle_pair(_lasgun_profile())
        dmg = self._dmg(att, dfn, distance=5.0)
        self.assertEqual(
            dmg, 2.0,
            f"RF-1 weapon at 5\" without FRFSRF should fire 2 attacks (1 base + 1 RF), "
            f"got {dmg}",
        )

    def test_rapid_fire_half_range_with_flag_three_attacks(self) -> None:
        """FRFSRF adds +1 on top of the normal half-range Rapid Fire bonus."""
        _, att, dfn = _make_battle_pair(_lasgun_profile())
        att.transient_frfsrf_active = True
        dmg = self._dmg(att, dfn, distance=5.0)
        self.assertEqual(
            dmg, 3.0,
            f"RF-1 weapon at 5\" WITH FRFSRF should fire 3 attacks "
            f"(1 base + 1 RF half-range + 1 FRFSRF), got {dmg}",
        )


# ---------------------------------------------------------------------------
# Test group 3: Non-Rapid-Fire weapon unchanged
# ---------------------------------------------------------------------------

class TestFRFSRFAttackCountNonRapidFire(unittest.TestCase):
    """The flag must not affect weapons without the Rapid Fire keyword."""

    def test_non_rf_weapon_unchanged_at_long_range(self) -> None:
        _, att_no, dfn_no = _make_battle_pair(_non_rf_profile())
        _, att_yes, dfn_yes = _make_battle_pair(_non_rf_profile())
        att_yes.transient_frfsrf_active = True

        with unittest.mock.patch("random.randint", return_value=4):
            dmg_no = att_no.attack(dfn_no, distance=30.0)
            dmg_yes = att_yes.attack(dfn_yes, distance=30.0)

        self.assertEqual(
            dmg_no, dmg_yes,
            f"Non-Rapid-Fire weapon damage must not change when FRFSRF flag is set: "
            f"no-flag={dmg_no}, with-flag={dmg_yes}",
        )
        self.assertEqual(
            dmg_yes, 2.0,
            f"Non-RF weapon with 2 base attacks should still give 2.0 damage, "
            f"got {dmg_yes}",
        )


# ---------------------------------------------------------------------------
# Test group 4: Transient lifecycle
# ---------------------------------------------------------------------------

class TestFRFSRFTransientCleared(unittest.TestCase):
    """transient_frfsrf_active is one-round-scoped: cleared by _clear_transient_stratagem_flags."""

    def test_flag_cleared_by_round_reset(self) -> None:
        battle, att, _ = _make_battle_pair(_lasgun_profile())
        _apply_order(att, ORDER_FRFSRF)
        self.assertTrue(
            att.transient_frfsrf_active,
            "transient_frfsrf_active must be True after the Order is applied",
        )
        battle._clear_transient_stratagem_flags(battle.a)
        self.assertFalse(
            att.transient_frfsrf_active,
            "transient_frfsrf_active must be False after the round-start transient "
            "flag reset — it is a one-round-scoped buff (CLAUDE.md standing rule)",
        )


# ---------------------------------------------------------------------------
# Test group 5: Lord Solar Leontus order count (NE-9)
# ---------------------------------------------------------------------------

def _officer_profile(name: str, faction: str = "Astra Militarum") -> UnitProfile:
    """A minimal Officer profile: alive, correct faction, in the OFFICER allowlist."""
    return UnitProfile(
        name=name,
        health=8,
        damage=0,
        hit_probability=0.5,
        attacks=0,
        range_inches=0,
        save=3,
        toughness=4,
        strength=4,
        ap=0,
        weapon_damage_per_shot=0.0,
        points_override=130.0,
        faction=faction,
        # No BATTLELINE keyword so the officer is NOT in the target pool itself.
        unit_keywords=("CHARACTER", "OFFICER", "MOUNTED", "EPIC HERO"),
    )


def _regiment_target(name: str, idx: int) -> UnitProfile:
    """An AM BATTLELINE INFANTRY target eligible to receive Orders."""
    return UnitProfile(
        name=name,
        health=1,
        damage=1,
        hit_probability=0.5,
        attacks=1,
        range_inches=24,
        save=5,
        toughness=3,
        strength=4,
        ap=0,
        weapon_damage_per_shot=1.0,
        rapid_fire=1,
        points_override=10.0 + idx,  # distinct point costs so priority ranking is stable
        faction="Astra Militarum",
        unit_keywords=("INFANTRY", "BATTLELINE"),
    )


def _build_army_with_officer_and_targets(
    officer_name: str, n_targets: int
) -> Army:
    """Build an Army with one officer and n_targets eligible REGIMENT targets.

    All units are placed at (0.0, 0.0) so every target is within the
    6-inch Order aura of the officer.
    """
    army = Army("Test")
    army.add_unit(_officer_profile(officer_name))
    for i in range(n_targets):
        army.add_unit(_regiment_target(f"Squad{i}", i))

    # Assign sequential uids so dispatch_orders can use uid-based de-duplication.
    for idx, u in enumerate(army.units):
        u.uid = f"U{idx}"

    # Invalidate the alive cache so alive_units re-reads the full unit list.
    army._alive_cache = None
    return army


class TestLordSolarOrderCount(unittest.TestCase):
    """Lord Solar Leontus issues exactly 3 Orders in one Command phase
    (wave 236 NE-9 fix).

    Verbatim source (BSData Library Astra Militarum cat.gz,
    Orders profile id 4768-11ce-3c8b-3ce4, cross-checked Wahapedia
    https://wahapedia.ru/wh40k10ed/factions/astra-militarum/Lord-Solar-Leontus):
        'This OFFICER can issue up to 3 Orders to: REGIMENT units,
         SQUADRON units, TITANIC units.'
    """

    def test_lord_solar_issues_three_orders(self) -> None:
        """With 4 eligible targets, Lord Solar issues exactly 3 Orders
        (the per-datasheet cap), leaving 1 target un-ordered."""
        army = _build_army_with_officer_and_targets(
            "Lord Solar Leontus", n_targets=4
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        self.assertEqual(
            len(issued), 3,
            f"Lord Solar Leontus must issue exactly 3 Orders per his datasheet; "
            f"got {len(issued)}: {issued}",
        )

    def test_lord_solar_targets_are_distinct(self) -> None:
        """Each of the 3 issued Orders goes to a different target unit."""
        army = _build_army_with_officer_and_targets(
            "Lord Solar Leontus", n_targets=4
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        target_names = [t for (_, t, _) in issued]
        self.assertEqual(
            len(target_names), len(set(target_names)),
            f"Each Order must go to a distinct target; got duplicates in {target_names}",
        )

    def test_lord_solar_targets_receive_transient_flags(self) -> None:
        """Each of the 3 ordered units has a transient buff set after dispatch."""
        army = _build_army_with_officer_and_targets(
            "Lord Solar Leontus", n_targets=4
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        ordered_names = {t for (_, t, _) in issued}
        for unit in army.alive_units:
            if unit.profile.name in ordered_names:
                has_buff = (
                    unit.transient_plus_one_to_hit_shooting
                    or unit.transient_frfsrf_active
                    or unit.transient_plus_one_to_wound_melee
                    or unit.transient_plus_one_save
                )
                self.assertTrue(
                    has_buff,
                    f"Unit {unit.profile.name!r} received an Order but has no "
                    f"transient buff set",
                )

    def test_lord_solar_cap_with_fewer_targets(self) -> None:
        """With only 2 eligible targets, Lord Solar issues 2 Orders
        (not 3 — the cap is a maximum, not a minimum)."""
        army = _build_army_with_officer_and_targets(
            "Lord Solar Leontus", n_targets=2
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        self.assertEqual(
            len(issued), 2,
            f"Lord Solar must issue min(cap, available targets) Orders; "
            f"got {len(issued)} with 2 targets",
        )


class TestRegularOfficerOrderCount(unittest.TestCase):
    """A regular officer (not in OFFICER_ORDER_COUNTS) issues exactly 1 Order
    per Command phase, matching the Voice of Command army rule default."""

    def test_cadian_castellan_issues_one_order(self) -> None:
        """Cadian Castellan is not in OFFICER_ORDER_COUNTS; must issue 1 Order."""
        army = _build_army_with_officer_and_targets(
            "Cadian Castellan", n_targets=4
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        self.assertEqual(
            len(issued), 1,
            f"Cadian Castellan must issue exactly 1 Order; got {len(issued)}: {issued}",
        )


class TestOfficerOrderCountsValidation(unittest.TestCase):
    """OFFICER_ORDER_COUNTS import-time validation: every key must be in
    AM_OFFICER_NAMES. This test guards the structural invariant directly
    by inspecting the module-level constants — no subprocess needed."""

    def test_all_keys_are_known_officers(self) -> None:
        """Every key in OFFICER_ORDER_COUNTS must appear in AM_OFFICER_NAMES.

        If this fails, either a new entry was added to OFFICER_ORDER_COUNTS
        with a mistyped name, or AM_OFFICER_NAMES was updated without a
        matching update here.
        """
        unknown = set(OFFICER_ORDER_COUNTS) - AM_OFFICER_NAMES
        self.assertEqual(
            unknown, set(),
            f"OFFICER_ORDER_COUNTS contains unknown officer key(s): {unknown!r}. "
            f"Each key must match a name in AM_OFFICER_NAMES exactly.",
        )

    def test_lord_solar_count_is_three(self) -> None:
        """Structural smoke test: Lord Solar's entry encodes the sourced count of 3."""
        self.assertEqual(
            OFFICER_ORDER_COUNTS.get("Lord Solar Leontus"), 3,
            "OFFICER_ORDER_COUNTS['Lord Solar Leontus'] must be 3 per his datasheet "
            "Orders profile (BSData cat.gz id 4768-11ce-3c8b-3ce4; Wahapedia "
            "https://wahapedia.ru/wh40k10ed/factions/astra-militarum/Lord-Solar-Leontus)",
        )


if __name__ == "__main__":
    unittest.main()
