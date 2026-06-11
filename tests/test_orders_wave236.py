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
from code.orders import ORDER_FRFSRF, ORDER_TAKE_AIM, _apply_order
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


if __name__ == "__main__":
    unittest.main()
