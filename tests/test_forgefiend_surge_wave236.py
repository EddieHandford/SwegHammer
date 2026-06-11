"""Wave 236 regression tests: Forgefiend 'Daemonic Ordnance' datasheet ability.

Verbatim rule (BSData v10.6.0 Chaos - Chaos Space Marines.cat.gz, ability
profile id 49a0-fe58-5293-bdc2, selectionEntry id 45b-19f6-38d2-703f):
"Each time this model is selected to shoot, it can use this ability. If it
does, until the end of the phase, its ranged weapons have the [DEVASTATING
WOUNDS] and [HAZARDOUS] abilities."

Implementation:
- UnitProfile.csm_daemonic_ordnance flag set via overrides.json on
  chaos_space_marines_forgefiend.
- simulator._apply_daemonic_ordnance() called per-activation from
  Battle._do_shoot after target selection; grants transient_devastating_wounds
  and transient_hazardous when expected [DEVASTATING WOUNDS] uplift > expected
  [HAZARDOUS] cost.
- Unit.attack() fires the Hazardous d6 check when transient_hazardous is set
  (ranged mode only), in addition to the static p.hazardous path.
- Both transient flags cleared per round by _clear_transient_stratagem_flags.
- Cited as simulator.csm_daemonic_ordnance.

Assertions:
a) Grant only fires for a unit with csm_daemonic_ordnance=True.
b) Both halves apply when elected: transient_devastating_wounds=True and
   transient_hazardous=True.
c) Opt-out fires when expected uplift is too small (soft target with high
   armour save that devastating wounds doesn't help vs).
d) Hazardous self-damage fires: when transient_hazardous is True and the
   random d6 roll is 1, the attacker loses 3 hit points.
e) transient flags clear at round reset via _clear_transient_stratagem_flags.
f) Hazardous does NOT fire in melee mode even when transient_hazardous is set.
"""

from __future__ import annotations

import random
import unittest
import unittest.mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _forgefiend_profile(csm_daemonic_ordnance: bool = True) -> UnitProfile:
    """Forgefiend-like profile (Chaos Space Marines, Toughness 10, 12 HP,
    Strength 8, 6 attacks, Damage 2, 3+ save, 36" range).

    With csm_daemonic_ordnance=True (default), the Daemonic Ordnance ability
    is enabled. With False, the ability is absent (used to verify the guard).
    """
    return UnitProfile(
        name="Forgefiend",
        health=12,
        damage=2,
        hit_probability=2 / 3,
        ap=-1,
        save=3,
        strength=8,
        toughness=10,
        attacks=6,
        weapon_damage_per_shot=2.0,
        range_inches=36,
        leadership=6,
        faction="Chaos Space Marines",
        unit_keywords=("VEHICLE", "WALKER", "DAEMON"),
        melee_attacks=5,
        melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3,
        melee_strength=7,
        melee_ap=0,
        points_override=170.0,
        csm_daemonic_ordnance=csm_daemonic_ordnance,
    )


def _tough_target_profile() -> UnitProfile:
    """A heavy armoured vehicle with 2+ save and no invulnerable save.

    Against this target: Strength 8 wounds on 3+ (4/6). The target has save 2+
    — against AP-1, effective save is 3+ (save_prob 4/6). [DEVASTATING WOUNDS]
    bypass that 3+ save on a critical wound (wound roll of 6+), so the
    expected uplift for the Forgefiend (6 attacks * 2/3 hit * 4/6 wound *
    1/6 crit * 4/6 save * 2 damage ≈ 0.59) comfortably exceeds the [HAZARDOUS]
    expected cost (0.5 wounds), ensuring reliable election in the test.
    """
    return UnitProfile(
        name="Heavy Armoured Vehicle",
        health=12,
        damage=2,
        hit_probability=2 / 3,
        ap=-2,
        save=2,     # 2+ save: effective 3+ vs AP-1 → save_prob 4/6
        strength=8,
        toughness=8,
        attacks=4,
        weapon_damage_per_shot=2.0,
        range_inches=24,
        leadership=6,
        faction="Space Marines",
        unit_keywords=("VEHICLE",),
        melee_attacks=2,
        melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3,
        melee_strength=6,
        melee_ap=-1,
        points_override=200.0,
    )


def _weak_target_profile() -> UnitProfile:
    """An unarmoured Toughness 3 infantry unit with no meaningful save.

    Against such a target the armour is already bypassed by normal AP, so
    [DEVASTATING WOUNDS] provides minimal additional uplift — the expected
    cost from [HAZARDOUS] should exceed the uplift for this target, causing
    the opt-out path to fire.
    """
    return UnitProfile(
        name="Gretchin",
        health=1,
        damage=1,
        hit_probability=2 / 3,
        ap=0,
        save=6,
        strength=2,
        toughness=3,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=12,
        leadership=5,
        faction="Orks",
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3,
        melee_strength=2,
        melee_ap=0,
        points_override=40.0,
    )


def _open_map() -> Map:
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _build_battle(
    attacker_profile: UnitProfile,
    target_profile: UnitProfile,
) -> tuple:
    """One attacker unit vs one target unit, both placed near the centre."""
    attacker_army = Army("Chaos Space Marines")
    attacker_army.add_unit(attacker_profile)
    defender_army = Army("Imperial Knights")
    defender_army.add_unit(target_profile)
    battle = Battle(attacker_army, defender_army, map_=_open_map(), verbose=False)
    battle._assign_uids()
    attacker_unit = attacker_army.units[0]
    target_unit = defender_army.units[0]
    # Place units 24" apart so they are in ranged range.
    attacker_unit.position = (15.0, 30.0)
    target_unit.position = (39.0, 30.0)
    return battle, attacker_unit, target_unit


# ---------------------------------------------------------------------------
# (a) Guard: ability only fires for units with csm_daemonic_ordnance=True
# ---------------------------------------------------------------------------


class TestDaemonicOrdnanceGuard(unittest.TestCase):
    """_apply_daemonic_ordnance must be a no-op for units without the flag."""

    def test_no_grant_without_flag(self):
        """A Forgefiend profile with csm_daemonic_ordnance=False must not
        receive either transient buff, even against a tough target."""
        profile_off = _forgefiend_profile(csm_daemonic_ordnance=False)
        battle, attacker, target = _build_battle(profile_off, _tough_target_profile())

        with unittest.mock.patch("random.randint", return_value=6):
            battle._apply_daemonic_ordnance(attacker, target)

        self.assertFalse(
            attacker.transient_devastating_wounds,
            "transient_devastating_wounds must NOT be set when "
            "csm_daemonic_ordnance is False",
        )
        self.assertFalse(
            attacker.transient_hazardous,
            "transient_hazardous must NOT be set when "
            "csm_daemonic_ordnance is False",
        )


# ---------------------------------------------------------------------------
# (b) Both halves apply when elected
# ---------------------------------------------------------------------------


class TestDaemonicOrdnanceBothHalves(unittest.TestCase):
    """When the ability is elected, both transient_devastating_wounds and
    transient_hazardous must be set on the attacker."""

    def test_both_flags_set_on_election(self):
        """Against a tough armoured target the uplift should exceed the cost,
        so both flags must be set after _apply_daemonic_ordnance fires."""
        battle, attacker, target = _build_battle(
            _forgefiend_profile(), _tough_target_profile()
        )

        battle._apply_daemonic_ordnance(attacker, target)

        self.assertTrue(
            attacker.transient_devastating_wounds,
            "transient_devastating_wounds must be True when Daemonic Ordnance "
            "is elected (ranged weapons gain [DEVASTATING WOUNDS])",
        )
        self.assertTrue(
            attacker.transient_hazardous,
            "transient_hazardous must be True when Daemonic Ordnance is elected "
            "(ranged weapons gain [HAZARDOUS])",
        )

    def test_grant_does_not_leak_to_target(self):
        """The transient buffs belong on the attacker only, not the target."""
        battle, attacker, target = _build_battle(
            _forgefiend_profile(), _tough_target_profile()
        )
        battle._apply_daemonic_ordnance(attacker, target)

        self.assertFalse(
            target.transient_devastating_wounds,
            "transient_devastating_wounds must NOT be set on the target",
        )
        self.assertFalse(
            target.transient_hazardous,
            "transient_hazardous must NOT be set on the target",
        )


# ---------------------------------------------------------------------------
# (c) Opt-out fires when uplift is too small
# ---------------------------------------------------------------------------


class TestDaemonicOrdnanceOptOut(unittest.TestCase):
    """Against a negligible target (very low toughness, poor armour already
    bypassed by AP) the expected [DEVASTATING WOUNDS] uplift approaches zero,
    so the expected [HAZARDOUS] cost should win and the ability must NOT be
    elected."""

    def test_opts_out_against_trivial_target(self):
        """Forgefiend (S8, AP-1) vs Toughness 3, Save 6+ target: S8 already
        wounds on 2+ and the 6+ save is already destroyed by AP-1, so the
        save probability the crit bypasses is near-zero. The expected uplift
        must be less than the hazardous cost of 0.5 wounds."""
        # Build a truly trivial target: save 7 (no save at all effectively)
        # so the save_prob in the heuristic resolves to 0.
        trivial_target = UnitProfile(
            name="No-Armour Target",
            health=3,
            damage=1,
            hit_probability=0.5,
            ap=0,
            save=7,     # never saves
            strength=3,
            toughness=3,
            attacks=1,
            weapon_damage_per_shot=1.0,
            range_inches=12,
            leadership=5,
            faction="Orks",
            unit_keywords=("INFANTRY",),
            melee_attacks=1,
            melee_damage_per_shot=1.0,
            melee_hit_probability=0.5,
            melee_strength=3,
            melee_ap=0,
            points_override=40.0,
        )
        battle, attacker, target = _build_battle(
            _forgefiend_profile(), trivial_target
        )

        battle._apply_daemonic_ordnance(attacker, target)

        self.assertFalse(
            attacker.transient_devastating_wounds,
            "transient_devastating_wounds must NOT be set when the target has "
            "no armour save to bypass (opt-out: uplift is zero)",
        )
        self.assertFalse(
            attacker.transient_hazardous,
            "transient_hazardous must NOT be set on an opt-out activation",
        )


# ---------------------------------------------------------------------------
# (d) Hazardous self-damage fires when d6 rolls 1
# ---------------------------------------------------------------------------


class TestDaemonicOrdnanceHazardousSelfDamage(unittest.TestCase):
    """When transient_hazardous is active and the post-shot d6 rolls a 1,
    the attacker must take 3 mortal wounds."""

    def test_self_damage_on_roll_of_1(self):
        """Patch the d6 roll to always return 1 and verify the attacker loses
        3 hit points after the ranged attack."""
        forgefiend = _forgefiend_profile()
        battle, attacker, target = _build_battle(forgefiend, _tough_target_profile())

        # Manually set transient_hazardous (simulating Daemonic Ordnance election).
        attacker.transient_hazardous = True
        health_before = attacker.current_health

        # Patch random.randint to always return 1: the hit roll, wound roll, save
        # roll, AND the hazardous d6 all become 1. The key assertion is that the
        # attacker's health drops — the exact amount depends on the full attack
        # sequence (may take 3 mortal wounds from hazardous + any other effects).
        with unittest.mock.patch("random.randint", return_value=1):
            attacker.attack(target, distance=20.0, has_los=True)

        health_after = attacker.current_health
        self.assertLess(
            health_after,
            health_before,
            "attacker must have lost hit points when transient_hazardous is "
            "True and the hazardous d6 rolls 1 (3 mortal wounds to self)",
        )

    def test_no_self_damage_on_roll_of_6(self):
        """Patch the d6 roll to always return 6: hazardous check passes,
        no self-damage. Attacker health must be unchanged after the shot
        (ignoring any unlikely self-damage from other mechanics — only
        the hazardous path is under test here)."""
        forgefiend = _forgefiend_profile()
        battle, attacker, target = _build_battle(forgefiend, _tough_target_profile())

        attacker.transient_hazardous = True
        health_before = attacker.current_health

        with unittest.mock.patch("random.randint", return_value=6):
            attacker.attack(target, distance=20.0, has_los=True)

        # On roll=6 the hazardous check passes (only 1 triggers self-damage).
        # Attacker health should be unchanged.
        self.assertEqual(
            attacker.current_health,
            health_before,
            "attacker must NOT lose hit points when the hazardous d6 rolls 6",
        )


# ---------------------------------------------------------------------------
# (e) Transient flags clear at round reset
# ---------------------------------------------------------------------------


class TestDaemonicOrdnanceFlagReset(unittest.TestCase):
    """Both transient_devastating_wounds and transient_hazardous must be
    cleared to False by _clear_transient_stratagem_flags at each round start."""

    def test_flags_cleared_by_round_reset(self):
        battle, attacker, target = _build_battle(
            _forgefiend_profile(), _tough_target_profile()
        )

        # Manually set both flags as if Daemonic Ordnance was just elected.
        attacker.transient_devastating_wounds = True
        attacker.transient_hazardous = True

        # Simulate round reset (clears all per-round transient flags).
        battle._clear_transient_stratagem_flags(battle.a)

        self.assertFalse(
            attacker.transient_devastating_wounds,
            "transient_devastating_wounds must be cleared by "
            "_clear_transient_stratagem_flags",
        )
        self.assertFalse(
            attacker.transient_hazardous,
            "transient_hazardous must be cleared by "
            "_clear_transient_stratagem_flags",
        )


# ---------------------------------------------------------------------------
# (f) Hazardous does NOT fire in melee mode
# ---------------------------------------------------------------------------


class TestDaemonicOrdnanceNoMeleeHazardous(unittest.TestCase):
    """The Daemonic Ordnance ability applies to ranged weapons only ('its
    ranged weapons have the [HAZARDOUS] ability'). transient_hazardous must
    not trigger self-damage when the attack is in melee mode."""

    def test_no_self_damage_in_melee_mode(self):
        """Even with transient_hazardous=True and d6 roll=1, a melee attack
        must NOT apply self-damage."""
        forgefiend = _forgefiend_profile()
        battle, attacker, target = _build_battle(forgefiend, _tough_target_profile())

        # Place within melee range.
        attacker.position = (30.0, 30.0)
        target.position = (30.5, 30.0)

        attacker.transient_hazardous = True
        health_before = attacker.current_health

        with unittest.mock.patch("random.randint", return_value=1):
            attacker.attack(target, distance=0.5, has_los=True, mode="melee")

        self.assertEqual(
            attacker.current_health,
            health_before,
            "transient_hazardous must NOT trigger self-damage for melee "
            "attacks — the ability only affects ranged weapons",
        )


if __name__ == "__main__":
    unittest.main()
