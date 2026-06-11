"""Tests for the Adepta Sororitas Hallowed Martyrs 'The Blood of Martyrs'
detachment rule (wave 234).

BSData v10.6.0 verbatim (Imperium - Adepta Sororitas.cat.gz, rule id
afa4-169c-3aaa-650): "Each time an ADEPTA SORORITAS model from your army
makes an attack, add 1 to the Hit roll if that model's unit is below its
Starting Strength, and add 1 to the Wound roll, as well, if that model's
unit is Below Half-strength."

Cited as HALLOWED_MARTYRS.soror_blood_of_martyrs.

Tests:
  (a) full-strength squad gets NO hit bonus
  (b) squad below starting strength gets +1 to hit
  (c) squad below half strength gets +1 hit AND +1 wound
  (d) a non-Hallowed-Martyrs Sororitas detachment gets nothing
  (e) the +1 hit bonus respects the 10e plus-or-minus-1 hit-modifier clamp
      when stacked with another existing +1-to-hit source

Measurement note: all tests use a ``_rate`` helper that totals damage over
n=4000 attack() calls against a target with health=1_000_000 (large enough
that the target never dies, so every call returns a real damage value and
divides cleanly by n).  The attacker profile has ``attacks=1`` (single shot)
so that ``damage / n`` is directly comparable to a per-shot expected value.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import HALLOWED_MARTYRS, BRINGERS_OF_FLAME
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Shared profile factories
# ---------------------------------------------------------------------------

def _sister_profile(num_models: int = 1) -> UnitProfile:
    """An Adepta Sororitas infantry unit with 1 ranged attack.
    hit_probability = 2/3 (BS 3+).  Using attacks=1 so that damage / n is
    a direct hit-rate proxy (wound target = 7+ on auto-wound target so saves
    and wounds do not confound the measurement; see _auto_target)."""
    return UnitProfile(
        name="Battle Sister", faction="Adepta Sororitas",
        health=1, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        min_models=num_models,
    )


def _auto_target() -> UnitProfile:
    """Target that auto-wounds and auto-fails saves.  toughness=1 so S3
    wounds on 2+; save=7 so always fails.  health=1_000_000 so it never
    dies across thousands of attack() calls, preventing the run-out-of-HP
    measurement bias."""
    return UnitProfile(
        name="Auto Target", faction="Adeptus Astartes",
        health=1_000_000, damage=1, hit_probability=0.5,
        ap=0, save=7, strength=1, toughness=1,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=1, melee_ap=0,
    )


def _resist_target() -> UnitProfile:
    """Target that is hard to wound (toughness=6, save=4+).  Used for the
    combined hit-and-wound bonus test (c): comparing full-strength baseline
    vs below-half-strength uplift.  health=1_000_000."""
    return UnitProfile(
        name="Resist Target", faction="Adeptus Astartes",
        health=1_000_000, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=6,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )


# ---------------------------------------------------------------------------
# Minimal Battle shim — supplies _squad_start_count and _current_round
# ---------------------------------------------------------------------------

class _FakeBattle:
    """Minimal shim so Unit.attack can reach _battle_ref._squad_start_count
    and _battle_ref._current_round without spinning up a full Battle."""
    _current_round: int = 1

    def __init__(self, squad_start_count: dict | None = None):
        self._squad_start_count: dict = squad_start_count or {}

    def maybe_fire_command_reroll(self, *args, **kwargs) -> bool:
        return False


def _wire(attacker: Unit, defender: Unit, battle: _FakeBattle) -> None:
    """Attach the fake battle shim to both armies' back-references."""
    attacker.army_ref._battle_ref = battle
    defender.army_ref._battle_ref = battle


# ---------------------------------------------------------------------------
# Core measurement helper
# ---------------------------------------------------------------------------

def _measure_rate(
    *,
    squad_size: int,
    alive_count: int,
    detachment,
    target_profile: UnitProfile,
    n: int = 4000,
    seed: int = 0,
) -> float:
    """Return (total damage / n) for a Sororitas squad of ``squad_size``
    models with ``alive_count`` survivors attacking ``target_profile`` under
    ``detachment``.

    Uses attacks=1 profiles and health=1_000_000 targets so the result is
    a clean per-call expected-value comparable to a single-shot hit rate.
    """
    random.seed(seed)
    soror_army = Army("Sororitas")
    soror_army.detachment = detachment

    profile = _sister_profile(num_models=squad_size)
    soror_army.add_squad(profile, squad_size)
    all_units = soror_army.units[:]
    squad_id = all_units[0].squad_id

    # Simulate casualties.  Guard against units_to_kill == 0: Python treats
    # all_units[-0:] as all_units[0:] (the full list), so the slice must only
    # run when there are actually models to remove.
    units_to_kill = squad_size - alive_count
    if units_to_kill > 0:
        for unit in all_units[-units_to_kill:]:
            unit.current_health = 0

    def_army = Army("Defenders")
    def_army.add_unit(target_profile)
    target = def_army.units[0]
    target.uid = "tgt"

    attacker = all_units[0]
    attacker.uid = "sor0"

    battle = _FakeBattle(
        squad_start_count={(soror_army.name, squad_id): squad_size}
    )
    _wire(attacker, target, battle)

    total = 0.0
    for _ in range(n):
        total += attacker.attack(target, distance=12.0, mode="ranged")
    return total / n


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBloodOfMartyrsFullStrength(unittest.TestCase):
    """(a) Full-strength squad — no hit bonus."""

    def test_no_hit_bonus_at_full_strength(self):
        """A squad at full Starting Strength must NOT receive the Blood of
        Martyrs hit bonus.

        auto_target has toughness=1 so wounding is near-certain (2+).  With
        attacks=1 and no save (7+), the expected rate is hit_prob ≈ 2/3 × 5/6
        ≈ 0.556.  With +1 hit it would be 5/6 × 5/6 ≈ 0.694.  We assert the
        observed rate is below the midpoint."""
        rate = _measure_rate(
            squad_size=5, alive_count=5,
            detachment=HALLOWED_MARTYRS,
            target_profile=_auto_target(),
            n=5000, seed=1,
        )
        # no bonus ≈ 2/3 × 5/6 ≈ 0.556; with +1 hit ≈ 5/6 × 5/6 ≈ 0.694
        midpoint = (2 / 3 * 5 / 6 + 5 / 6 * 5 / 6) / 2  # ≈ 0.625
        self.assertLess(
            rate, midpoint,
            f"Full-strength squad must NOT receive Blood of Martyrs hit bonus: "
            f"observed {rate:.4f} should be < midpoint {midpoint:.4f}",
        )


class TestBloodOfMartyrsHitBonusOnly(unittest.TestCase):
    """(b) Below Starting Strength but NOT below Half-strength: +1 hit only."""

    def test_below_start_strength_grants_plus_one_hit(self):
        """squad_size=6, alive=5 (one casualty — below Starting Strength,
        still above Half-strength=3), expect rate ≈ 5/6 × 5/6 ≈ 0.694
        rather than the no-bonus 2/3 × 5/6 ≈ 0.556."""
        rate = _measure_rate(
            squad_size=6, alive_count=5,
            detachment=HALLOWED_MARTYRS,
            target_profile=_auto_target(),
            n=5000, seed=7,
        )
        # no-bonus ≈ 0.556; with +1 hit ≈ 0.694
        midpoint = (2 / 3 * 5 / 6 + 5 / 6 * 5 / 6) / 2  # ≈ 0.625
        self.assertGreater(
            rate, midpoint,
            f"Below Starting Strength must grant +1 Hit: observed {rate:.4f} "
            f"should exceed midpoint {midpoint:.4f}",
        )


class TestBloodOfMartyrsHitAndWound(unittest.TestCase):
    """(c) Below Half-strength: +1 hit AND +1 wound."""

    def test_below_half_grants_both_bonuses(self):
        """squad_size=6, alive=2 (below half=3), expect BOTH hit and wound
        bonuses on a resist target (T6, save 4+).

        Against resist_target (T6, AP0):
          no bonus   — hit=2/3, wound=1/6, save=1/2 → ≈ 0.0556
          +1 hit only — hit=5/6, wound=1/6, save=1/2 → ≈ 0.0694
          both bonuses — hit=5/6, wound=1/3, save=1/2 → ≈ 0.139

        The below-half combined uplift vs full-strength should be ≥ 1.8×."""
        rate_full = _measure_rate(
            squad_size=6, alive_count=6,
            detachment=HALLOWED_MARTYRS,
            target_profile=_resist_target(),
            n=8000, seed=13,
        )
        rate_half = _measure_rate(
            squad_size=6, alive_count=2,
            detachment=HALLOWED_MARTYRS,
            target_profile=_resist_target(),
            n=8000, seed=13,
        )
        self.assertGreater(
            rate_half, rate_full * 1.8,
            f"Below Half-strength must grant both +1 Hit and +1 Wound: "
            f"rate_full={rate_full:.4f}, rate_half={rate_half:.4f}; "
            f"expected rate_half > rate_full * 1.8",
        )


class TestBloodOfMartyrsNonHallowedMartyrs(unittest.TestCase):
    """(d) Non-Hallowed-Martyrs Sororitas detachment gets nothing."""

    def test_bringers_of_flame_no_bonus(self):
        """A Sororitas squad below Starting Strength under Bringers of Flame
        must NOT receive the Blood of Martyrs hit bonus.  Compare both
        detachments at the same alive_count=4 out of squad_size=6."""
        rate_hallowed = _measure_rate(
            squad_size=6, alive_count=4,
            detachment=HALLOWED_MARTYRS,
            target_profile=_auto_target(),
            n=5000, seed=99,
        )
        rate_bringers = _measure_rate(
            squad_size=6, alive_count=4,
            detachment=BRINGERS_OF_FLAME,
            target_profile=_auto_target(),
            n=5000, seed=99,
        )
        midpoint = (2 / 3 * 5 / 6 + 5 / 6 * 5 / 6) / 2  # ≈ 0.625
        self.assertGreater(
            rate_hallowed, midpoint,
            f"Hallowed Martyrs below Starting Strength must grant +1 Hit "
            f"(rate {rate_hallowed:.4f} should exceed midpoint {midpoint:.4f})",
        )
        self.assertLess(
            rate_bringers, midpoint,
            f"Bringers of Flame must NOT grant +1 Hit from Blood of Martyrs "
            f"(rate {rate_bringers:.4f} should be < midpoint {midpoint:.4f})",
        )


class TestBloodOfMartyrsHitClamp(unittest.TestCase):
    """(e) The +1 hit bonus respects the 10e plus-or-minus-1 hit-modifier
    clamp when stacked with transient_plus_one_to_hit_shooting."""

    def test_hit_clamp_prevents_double_plus_one(self):
        """Stacking Blood of Martyrs (+1 hit) with
        transient_plus_one_to_hit_shooting (a second +1 hit) must yield the
        SAME hit rate as Blood of Martyrs alone — the 10e modifier cap clamps
        the net delta to +1 regardless of how many +1 sources contribute.

        With the clamp both should be ≈ 5/6 × 5/6 ≈ 0.694 vs auto_target.
        Without the clamp the double would approach 1.0 (automatic hits)."""

        def _rate_with_extra(extra_hit: bool, seed: int = 17) -> float:
            n = 5000
            random.seed(seed)
            soror_army = Army("Sororitas")
            soror_army.detachment = HALLOWED_MARTYRS
            p = _sister_profile(num_models=6)
            soror_army.add_squad(p, 6)
            all_units = soror_army.units[:]
            squad_id = all_units[0].squad_id
            # One casualty: below Starting Strength (triggers Blood of Martyrs)
            all_units[-1].current_health = 0

            def_army = Army("Def")
            def_army.add_unit(_auto_target())
            tgt = def_army.units[0]
            tgt.uid = "aw"

            attacker = all_units[0]
            attacker.uid = "s0"
            if extra_hit:
                attacker.transient_plus_one_to_hit_shooting = True

            battle = _FakeBattle(
                squad_start_count={(soror_army.name, squad_id): 6}
            )
            _wire(attacker, tgt, battle)
            return sum(
                attacker.attack(tgt, distance=12.0, mode="ranged")
                for _ in range(n)
            ) / n

        rate_bom_only = _rate_with_extra(extra_hit=False)
        rate_double = _rate_with_extra(extra_hit=True)

        # Both should be ≈ 5/6 × 5/6 ≈ 0.694.  With no clamp the double
        # would push toward 1.0.  Allow 5 % Monte Carlo tolerance.
        tolerance = 0.05
        self.assertAlmostEqual(
            rate_bom_only, rate_double, delta=tolerance,
            msg=(
                f"Hit-modifier clamp must cap the bonus at +1 even when "
                f"Blood of Martyrs and a second +1-to-hit source are both "
                f"active: rate_bom_only={rate_bom_only:.4f}, "
                f"rate_double={rate_double:.4f}, tolerance={tolerance}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
