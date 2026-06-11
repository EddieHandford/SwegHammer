"""Tests for the Paragon Warsuits "Righteous Paragons" datasheet ability.

Wahapedia verbatim: "Each time a model in this unit makes an attack that
targets a MONSTER or VEHICLE unit, add 1 to the Hit roll and add 1 to the
Wound roll."

Source: https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/Paragon-Warsuits

The ability is gated on the attacker having the `righteous_paragons` flag
(set via data/overrides.json for the Paragon Warsuits unit) and the target
having MONSTER or VEHICLE in its unit_keywords. Both a +1 to Hit and a +1 to
Wound apply simultaneously, so damage against a qualifying target must be
materially greater than against an INFANTRY target (which never receives the
bonus).

These tests use Unit.attack directly with fixed random seeds and high trial
counts so the statistical comparison is decisive (both hit and wound improve
by +1 step, which is a large effect).
"""
from __future__ import annotations

import random
import unittest

from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _paragon_warsuits_profile() -> UnitProfile:
    """Paragon Warsuits attacker with righteous_paragons=True.

    Stats chosen to sit in the middle of the wound table so both the +1 to Hit
    and +1 to Wound shifts are measurable:
      - Ballistic Skill 3+ (hit_probability = 4/6 ≈ 0.667)
      - Strength 8 vs Toughness 9 target: normally wounds on 5+ (2/6), with
        +1 wounds on 4+ (3/6) — a 50% uplift in wound probability.
      - 6 attacks per activation for a clear signal at reasonable trial counts.
    """
    return UnitProfile(
        name="Paragon Warsuits",
        health=6,
        damage=1,
        hit_probability=4 / 6,
        ap=-2,
        save=3,
        strength=8,
        toughness=7,
        attacks=6,
        weapon_damage_per_shot=2.0,
        range_inches=24,
        leadership=7,
        faction="Adepta Sororitas",
        unit_keywords=("VEHICLE", "WALKER"),
        righteous_paragons=True,
    )


def _paragon_warsuits_no_ability() -> UnitProfile:
    """Identical attacker but with righteous_paragons=False (control)."""
    return UnitProfile(
        name="Paragon Warsuits (no ability)",
        health=6,
        damage=1,
        hit_probability=4 / 6,
        ap=-2,
        save=3,
        strength=8,
        toughness=7,
        attacks=6,
        weapon_damage_per_shot=2.0,
        range_inches=24,
        leadership=7,
        faction="Adepta Sororitas",
        unit_keywords=("VEHICLE", "WALKER"),
        righteous_paragons=False,
    )


def _vehicle_target() -> UnitProfile:
    """A VEHICLE target: Toughness 9, 3+ save, large health pool.

    Toughness 9 means a Strength 8 attacker normally wounds on 5+ (2/6).
    With Righteous Paragons active (+1 to Wound) it wounds on 4+ (3/6).
    """
    return UnitProfile(
        name="Test Vehicle",
        health=10_000.0,
        damage=1,
        hit_probability=4 / 6,
        ap=0,
        save=3,
        strength=6,
        toughness=9,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("VEHICLE",),
    )


def _monster_target() -> UnitProfile:
    """A MONSTER target: same stats as the VEHICLE target but with MONSTER
    keyword. Righteous Paragons applies to both."""
    return UnitProfile(
        name="Test Monster",
        health=10_000.0,
        damage=1,
        hit_probability=4 / 6,
        ap=0,
        save=3,
        strength=6,
        toughness=9,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        leadership=7,
        faction="Tyranids",
        unit_keywords=("MONSTER",),
    )


def _infantry_target() -> UnitProfile:
    """An INFANTRY target: same Toughness 9, 3+ save but no MONSTER or
    VEHICLE keyword. Righteous Paragons must NOT apply here."""
    return UnitProfile(
        name="Test Infantry",
        health=10_000.0,
        damage=1,
        hit_probability=4 / 6,
        ap=0,
        save=3,
        strength=6,
        toughness=9,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
    )


def _mean_damage(
    attacker: Unit,
    defender: Unit,
    trials: int = 5000,
    seed: int = 2026,
    mode: str = "ranged",
) -> float:
    """Average per-activation damage over `trials` Unit.attack invocations."""
    random.seed(seed)
    total = 0.0
    for _ in range(trials):
        defender.current_health = float(defender.profile.health)
        total += attacker.attack(defender, distance=12.0, mode=mode, has_los=True)
    return total / trials


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class RighteousParagonsTests(unittest.TestCase):
    """Paragon Warsuits Righteous Paragons ability — attacker-side +1 to Hit
    and +1 to Wound when the target has the MONSTER or VEHICLE keyword."""

    def test_vehicle_target_gets_bonus(self):
        """Attacking a VEHICLE target with righteous_paragons=True must deal
        materially more damage than without the ability, because both hit
        probability (3+ vs 4+) and wound probability (4+ vs 5+) improve."""
        attacker_with = Unit(_paragon_warsuits_profile())
        attacker_without = Unit(_paragon_warsuits_no_ability())
        vehicle = Unit(_vehicle_target())

        dmg_with = _mean_damage(attacker_with, vehicle)
        dmg_without = _mean_damage(attacker_without, vehicle)

        # The combined hit and wound uplift is large (hit 5/6 vs 4/6, wound
        # 3/6 vs 2/6 against Toughness 9): expect at least 30% more damage.
        self.assertGreater(
            dmg_with, dmg_without * 1.25,
            msg=(
                f"Righteous Paragons vs VEHICLE: expected meaningful damage "
                f"uplift. With ability: {dmg_with:.3f}, without: "
                f"{dmg_without:.3f}."
            ),
        )

    def test_monster_target_gets_bonus(self):
        """Attacking a MONSTER target must also receive the bonus — Righteous
        Paragons applies to both MONSTER and VEHICLE targets."""
        attacker_with = Unit(_paragon_warsuits_profile())
        attacker_without = Unit(_paragon_warsuits_no_ability())
        monster = Unit(_monster_target())

        dmg_with = _mean_damage(attacker_with, monster)
        dmg_without = _mean_damage(attacker_without, monster)

        self.assertGreater(
            dmg_with, dmg_without * 1.25,
            msg=(
                f"Righteous Paragons vs MONSTER: expected meaningful damage "
                f"uplift. With ability: {dmg_with:.3f}, without: "
                f"{dmg_without:.3f}."
            ),
        )

    def test_infantry_target_gets_no_bonus(self):
        """Attacking an INFANTRY target (no MONSTER or VEHICLE keyword) must
        give the same damage with or without the righteous_paragons flag,
        because the gate does not fire."""
        attacker_with = Unit(_paragon_warsuits_profile())
        attacker_without = Unit(_paragon_warsuits_no_ability())
        infantry = Unit(_infantry_target())

        dmg_with = _mean_damage(attacker_with, infantry)
        dmg_without = _mean_damage(attacker_without, infantry)

        # Allow a 5% tolerance for random noise; they should be essentially
        # equal because the gate does not fire for INFANTRY.
        self.assertAlmostEqual(
            dmg_with, dmg_without, delta=dmg_without * 0.05,
            msg=(
                f"Righteous Paragons must NOT apply vs INFANTRY. "
                f"With flag: {dmg_with:.3f}, without flag: {dmg_without:.3f} "
                f"— these should be equal within noise."
            ),
        )

    def test_flag_loaded_from_catalog(self):
        """The live catalogue entry for adepta_sororitas_paragon_warsuits must
        have righteous_paragons=True (set via data/overrides.json)."""
        from code.units import UNIT_CATALOG

        key = "adepta_sororitas_paragon_warsuits"
        self.assertIn(
            key, UNIT_CATALOG,
            "adepta_sororitas_paragon_warsuits must exist in the unit catalogue",
        )
        entry = UNIT_CATALOG[key]
        self.assertTrue(
            entry.righteous_paragons,
            f"UNIT_CATALOG['{key}'].righteous_paragons must be True "
            f"(set via data/overrides.json SOROR-F4); got False.",
        )
