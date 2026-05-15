"""Tests for the Thousand Sons army rule All Is Dust (task #145).

All Is Dust (10e Thousand Sons army rule, Wahapedia):
    "Each time an attack with a Damage characteristic of 1 is allocated to
     a model in this unit, subtract 1 from the Wound roll."

Implementation:
    * `Unit.attack` adds `wound_target = min(7, wound_target + 1)` when the
      target is faction Thousand Sons, the incoming attack has
      `per_shot_dmg <= 1.0`, and the target does NOT carry the DAEMON
      unit-keyword.
    * Cited as `simulator.all_is_dust`.

These tests use deterministic seeds and large attack volumes so the
empirical wound rate matches the analytical d6 distribution within a
loose statistical tolerance.
"""

from __future__ import annotations

import dataclasses
import random
import unittest

from code.army import Army
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helpers — minimal profiles wired with the canonical faction strings
# ---------------------------------------------------------------------------

def _rubric_marine(faction: str = "Thousand Sons",
                   keywords=("PSYKER", "INFANTRY")) -> UnitProfile:
    """A bulky T4 / 3+ save Rubric stand-in. Health is large so a single
    test trial cannot kill the unit and wash out the wound-rate signal."""
    return UnitProfile(
        name="Rubric Marine",
        health=10_000.0, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction=faction,
        unit_keywords=keywords,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _single_damage_attacker() -> UnitProfile:
    """An S4 / D1 attacker. Hits auto (we patch by counting wounds at the
    attack level), wounds T4 on 4+ baseline; All Is Dust pushes that to 5+."""
    return UnitProfile(
        name="D1 Bolter",
        health=2.0, damage=1, hit_probability=1.0,    # auto-hit via torrent
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        torrent=True,                                   # skip hit roll
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _multi_damage_attacker() -> UnitProfile:
    """Same chassis but D2 — All Is Dust must NOT fire."""
    return dataclasses.replace(
        _single_damage_attacker(),
        weapon_damage_per_shot=2.0,
        damage=2,
        name="D2 Plasma",
    )


# ---------------------------------------------------------------------------
# Empirical wound-rate harness. We assemble armies, hand off via Unit.attack,
# and count "wound landed and got past save" trials. The relative ratio
# between with-rule and without-rule is what we assert on.
# ---------------------------------------------------------------------------

def _wound_rate(attacker_profile: UnitProfile,
                defender_profile: UnitProfile,
                n_attacks: int = 8000,
                seed: int = 0) -> float:
    """Mean damage per attack (proxy for landed-and-failed-save rate). We
    don't decompose into hit/wound/save because Unit.attack already does
    that internally — we just need a stable empirical rate."""
    random.seed(seed)
    atk_army = Army("Atk")
    atk_army.add_unit(attacker_profile)
    def_army = Army("Def")
    def_army.add_unit(defender_profile)
    attacker = atk_army.units[0]
    attacker.uid = "atk0"
    defender = def_army.units[0]
    defender.uid = "def0"

    class _FakeBattle:
        _current_round = 1
        def maybe_fire_command_reroll(self, *args, **kwargs):
            return False
    fb = _FakeBattle()
    attacker.army_ref._battle_ref = fb
    defender.army_ref._battle_ref = fb

    total = 0.0
    for _ in range(n_attacks):
        total += attacker.attack(defender, distance=6.0, mode="ranged")
    return total / n_attacks


class AllIsDustTests(unittest.TestCase):
    """Cover the four canonical behaviours: rule fires on D1 vs TSons,
    rule doesn't fire for D2 attackers, rule doesn't fire for non-TSons,
    and the buff stacks with attacker-side +1 to wound."""

    def test_single_damage_attack_subtracts_1_to_wound(self):
        """D1 S4 attacker into T4 TSons defender. Baseline wounds on 4+
        (50%); All Is Dust pushes it to 5+ (~33%). Save 3+ passes 4/6, so
        damage past save: baseline ~3/6 * 2/6 = 1/6 ≈ 0.167; with rule
        ~2/6 * 2/6 = 4/36 ≈ 0.111. Net rate must drop ~30-40%."""
        atk = _single_damage_attacker()
        tson = _rubric_marine(faction="Thousand Sons")
        marine = _rubric_marine(faction="Adeptus Astartes")
        with_rule = _wound_rate(atk, tson, seed=0)
        without_rule = _wound_rate(atk, marine, seed=0)
        # Sanity: the no-rule rate should be ~0.167 (50% wound * 33% fail save).
        self.assertGreater(without_rule, with_rule,
                           f"All Is Dust must reduce damage taken: "
                           f"with={with_rule:.4f} without={without_rule:.4f}")
        # Ratio sanity: with-rule should be ~2/3 of without-rule (33%/50%
        # wound conversion). Loose tolerance to absorb seed noise.
        self.assertLess(with_rule / without_rule, 0.85,
                        f"All Is Dust drop too small: ratio={with_rule/without_rule:.3f}")

    def test_multi_damage_attack_unaffected(self):
        """D2 S4 attacker into T4 TSons defender. Wound roll baseline 4+;
        All Is Dust does NOT fire (damage > 1). Damage rate must match the
        non-TSons control (same wound math, same save, same damage)."""
        atk = _multi_damage_attacker()
        tson = _rubric_marine(faction="Thousand Sons")
        marine = _rubric_marine(faction="Adeptus Astartes")
        rate_tson = _wound_rate(atk, tson, seed=1)
        rate_marine = _wound_rate(atk, marine, seed=1)
        # Same seed + same math => rates must be very close. 5% tolerance.
        ratio = rate_tson / rate_marine if rate_marine else 0.0
        self.assertGreater(ratio, 0.92,
                           f"D2 attacker should be unaffected by All Is Dust: "
                           f"tson={rate_tson:.4f} marine={rate_marine:.4f}")
        self.assertLess(ratio, 1.08,
                        f"D2 attacker should be unaffected by All Is Dust: "
                        f"tson={rate_tson:.4f} marine={rate_marine:.4f}")

    def test_non_tson_target_unaffected(self):
        """D1 attacker vs vanilla Marine (faction != TSons). Wound rate
        must equal the no-rule baseline — verifies the faction gate.

        We swap the attacker's faction to "Chaos Space Marines" so the
        Adeptus Astartes Combat Doctrines +1-to-wound (Round 1 Devastator
        on ranged attacks) doesn't perturb the wound rate. The D1 attacker
        in this codepath ALWAYS rolls vs a 4+ wound target (S4 vs T4)."""
        atk = dataclasses.replace(
            _single_damage_attacker(),
            faction="Chaos Space Marines",
            name="D1 Bolter (CSM)",
        )
        marine = _rubric_marine(faction="Adeptus Astartes")
        rate = _wound_rate(atk, marine, seed=2)
        # Baseline ~0.167 (50% wound * 33% fail save). Wide bounds for noise.
        self.assertGreater(rate, 0.13,
                           f"Non-TSons baseline rate too low: {rate:.4f}")
        self.assertLess(rate, 0.21,
                        f"Non-TSons baseline rate too high: {rate:.4f}")

    def test_all_is_dust_stacks_with_detachment_plus_one(self):
        """A D1 attacker with `plus_one_to_wound` (a detachment buff like
        Outbreak of Pestilence) vs a TSons defender: the +1 and -1 cancel,
        so the net wound target equals the BASE wound target (no buffs, no
        rule, vs a non-TSons defender). We compare those two rates and they
        must match within seed-noise tolerance."""
        import code.leaders as leaders_mod

        atk = _single_damage_attacker()
        tson = _rubric_marine(faction="Thousand Sons")
        marine = _rubric_marine(faction="Adeptus Astartes")

        original = leaders_mod.effective_buffs

        def _buffs_with_plus_one(unit):
            base = dict(original(unit))
            base["plus_one_to_wound"] = True
            return base

        # Branch A: attacker has +1 to wound buff, target is TSons → buffs cancel.
        leaders_mod.effective_buffs = _buffs_with_plus_one
        try:
            rate_buffed_vs_tson = _wound_rate(atk, tson, seed=3)
        finally:
            leaders_mod.effective_buffs = original

        # Branch B: no buffs, target is a vanilla Marine → base wound target.
        rate_baseline_vs_marine = _wound_rate(atk, marine, seed=3)

        # Both branches resolve at the same wound_target (4+); same seed +
        # same RNG draws => rates should be very close. 12% tolerance for
        # any divergence in random.randint() ordering between branches.
        ratio = rate_buffed_vs_tson / rate_baseline_vs_marine
        self.assertGreater(ratio, 0.85,
                           f"All Is Dust + +1 to wound should net out: "
                           f"buffed_tson={rate_buffed_vs_tson:.4f} "
                           f"baseline={rate_baseline_vs_marine:.4f}")
        self.assertLess(ratio, 1.15,
                        f"All Is Dust + +1 to wound should net out: "
                        f"buffed_tson={rate_buffed_vs_tson:.4f} "
                        f"baseline={rate_baseline_vs_marine:.4f}")

    def test_wound_target_floor_at_2(self):
        """A +1 to wound that pushes wound_target down to 2 still clamps at
        2+ (10e core rules cap wound rolls). Then -1 from All Is Dust pushes
        it back to 3+, NOT below 2+. We verify this by setting a high-S
        attacker (S8 vs T4 = 2+ to wound baseline) and confirming the rate
        with All Is Dust corresponds to a 3+ wound target, not 1+."""
        # S8 vs T4 = wound on 2+ baseline (S >= 2T). With All Is Dust the
        # wound target becomes 3+. Save 3+, no AP, so save passes on 3+
        # (4/6 success). Landed damage per attack:
        #   baseline 5/6 wound * 2/6 fail save = 10/36 ≈ 0.278
        #   with rule 4/6 wound * 2/6 fail save = 8/36 ≈ 0.222
        atk = dataclasses.replace(
            _single_damage_attacker(), strength=8, name="High-S D1",
        )
        tson = _rubric_marine(faction="Thousand Sons")
        marine = _rubric_marine(faction="Adeptus Astartes")
        rate_tson = _wound_rate(atk, tson, seed=4)
        rate_marine = _wound_rate(atk, marine, seed=4)
        # 2+ vs 3+ wound is a 5/6 -> 4/6 step; ratio should be ~0.8.
        # Confirm the rule actually fires (rate dropped) AND the result is
        # consistent with a 3+ wound (not a 1+ no-op nor a 4+ over-clamp).
        ratio = rate_tson / rate_marine
        self.assertGreater(ratio, 0.65,
                           f"All Is Dust floor: too much damage lost — "
                           f"tson={rate_tson:.4f} marine={rate_marine:.4f}")
        self.assertLess(ratio, 0.95,
                        f"All Is Dust floor: rule didn't fire — "
                        f"tson={rate_tson:.4f} marine={rate_marine:.4f}")


if __name__ == "__main__":
    unittest.main()
