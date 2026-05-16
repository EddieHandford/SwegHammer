"""Pin the #C2 (auto-loop iter 2) charge "won't-crack" penalty.

Audit (`docs/AUTO_LOOP_ITER1_CLUSTER_C.md` fix #2): 27.8% of charges in a
30-battle vanilla-10e run landed on T8+ S<=3 bricks the attacker could
not dent — wasted activations because counter-fight reverses on the
attacker next turn.

After #C2, `pick_charge_target` checks expected wounds inflicted vs
target remaining HP. If `_kill_potential_wounds(attacker, target)`
is below 20% of `target.current_health`, the candidate's score is
multiplied by 0.3 — heavy downweight.

Faction-neutral: the penalty composes only the universal 10e S-vs-T
wound table, AP-vs-save math, and melee DPA. Knights, Wraithlords,
Carnifexes and Custodian Guard are gated identically.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.strategy import (
    _WONT_CRACK_HP_FRAC,
    _WONT_CRACK_PENALTY,
    _kill_potential_wounds,
    pick_charge_target,
)
from code.units import UnitProfile


def _light_brawler() -> UnitProfile:
    """Low-S, low-AP attacker. 6 attacks, S4, AP0, dmg 1 — fine vs
    Marines, totally inadequate vs a T10 multi-wound brick."""
    return UnitProfile(
        name="LightBrawler", health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _t4_w1_squishy() -> UnitProfile:
    """T4 W1 4+ save — light brawler eats this for breakfast."""
    return UnitProfile(
        name="Squishy", health=1, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
    )


def _t10_w12_brick() -> UnitProfile:
    """T10, 12 wounds, 2+/4++ — light brawler can't dent it.

    S4 vs T10 wounds on 6+ (1/6). 6 attacks * 2/3 hits * 1/6 wounds *
    save_fail(2+ vs AP0)=1/6 * 1 dmg = ~0.018 wounds/round. 12 HP. Far
    below the 20% (=2.4 HP) won't-crack threshold."""
    return UnitProfile(
        name="Brick", health=12, damage=4, hit_probability=2 / 3,
        ap=-3, save=2, strength=12, toughness=10,
        invuln_save=4,
        attacks=2, weapon_damage_per_shot=4.0, range_inches=12,
        leadership=8, faction="Generic", unit_keywords=("MONSTER",),
        melee_attacks=4, melee_damage_per_shot=4.0,
        melee_hit_probability=2 / 3, melee_strength=12, melee_ap=3,
    )


def _t10_w8_lighter_brick() -> UnitProfile:
    """Still T10, but 8 HP and 3+/no invuln. The "most damageable"
    among T10 alternatives — picker should prefer this when forced
    to choose between two un-crackables."""
    return UnitProfile(
        name="LighterBrick", health=8, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=10, toughness=10,
        invuln_save=7,
        attacks=2, weapon_damage_per_shot=2.0, range_inches=12,
        leadership=8, faction="Generic", unit_keywords=("MONSTER",),
        melee_attacks=3, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=10, melee_ap=1,
    )


class KillPotentialMathTests(unittest.TestCase):
    """Sanity-check the helper before driving the picker."""

    def test_kill_potential_high_vs_t4(self):
        brawler = _light_brawler()
        squishy = _t4_w1_squishy()
        # 6 * 2/3 * 0.5 * (1 - 2/6) * 1 = ~1.33 wounds. Far above the
        # 0.20 * 1 = 0.20 threshold.
        ew = _kill_potential_wounds(brawler, squishy)
        self.assertGreater(ew, 0.20 * squishy.health)

    def test_kill_potential_low_vs_t10_brick(self):
        brawler = _light_brawler()
        brick = _t10_w12_brick()
        # 6 * 2/3 * 1/6 * (1 - 5/6) * 1 = ~0.11 wounds. Below 0.20 * 12.
        ew = _kill_potential_wounds(brawler, brick)
        self.assertLess(ew, _WONT_CRACK_HP_FRAC * brick.health)


class ChargePickerPrefersDamageableTargets(unittest.TestCase):
    """Given a T4 W1 squishy AND a T10 W12 brick both in range, the
    light brawler must charge the squishy. The penalty must keep the
    crackable target on top."""

    def test_squishy_preferred_over_uncrackable_brick(self):
        a = Army("A")
        a.add_unit(_light_brawler())
        d = Army("D")
        d.add_unit(_t10_w12_brick())
        d.add_unit(_t4_w1_squishy())

        attacker = a.units[0]
        brick, squishy = d.units[0], d.units[1]
        # Both inside 12" charge range, both > 1" so not engaged.
        attacker.position = (30.0, 30.0)
        brick.position = (33.0, 30.0)
        squishy.position = (35.0, 30.0)

        target, dist = pick_charge_target(attacker, d)
        self.assertIsNotNone(target)
        self.assertEqual(
            target.uid, squishy.uid,
            "Should charge the T4 W1 squishy, not the T10 W12 brick the"
            " brawler can't dent.",
        )

    def test_squishy_preferred_even_when_brick_is_closer(self):
        """The won't-crack penalty must beat distance — the brick is
        a much shorter charge but cracking it is impossible."""
        a = Army("A")
        a.add_unit(_light_brawler())
        d = Army("D")
        d.add_unit(_t10_w12_brick())
        d.add_unit(_t4_w1_squishy())

        attacker = a.units[0]
        brick, squishy = d.units[0], d.units[1]
        attacker.position = (30.0, 30.0)
        brick.position = (32.0, 30.0)    # 2" — trivially short charge
        squishy.position = (36.0, 30.0)  # 6" — moderate charge
        target, _ = pick_charge_target(attacker, d)
        self.assertEqual(target.uid, squishy.uid)


class ChargePickerAllUncrackableFallsBack(unittest.TestCase):
    """When EVERY candidate is below the won't-crack threshold the
    penalty is applied to all of them — relative ordering survives, so
    the picker still returns the *most* damageable one. It must NOT
    return None just because no target is crackable."""

    def test_picks_most_damageable_when_all_uncrackable(self):
        a = Army("A")
        a.add_unit(_light_brawler())
        d = Army("D")
        d.add_unit(_t10_w12_brick())
        d.add_unit(_t10_w8_lighter_brick())

        attacker = a.units[0]
        heavy_brick, lighter = d.units[0], d.units[1]
        attacker.position = (30.0, 30.0)
        heavy_brick.position = (33.0, 30.0)
        lighter.position = (35.0, 30.0)

        # Both below threshold — confirm preconditions.
        self.assertLess(
            _kill_potential_wounds(attacker.profile, heavy_brick.profile),
            _WONT_CRACK_HP_FRAC * heavy_brick.current_health,
        )
        self.assertLess(
            _kill_potential_wounds(attacker.profile, lighter.profile),
            _WONT_CRACK_HP_FRAC * lighter.current_health,
        )

        target, _ = pick_charge_target(attacker, d)
        self.assertIsNotNone(
            target,
            "Picker should still pick SOMEONE when all candidates are"
            " un-crackable — the penalty downweights but doesn't veto.",
        )
        self.assertEqual(
            target.uid, lighter.uid,
            "Among T10 alternatives the lighter brick (3+ save, 8 HP)"
            " is the most damageable — picker should prefer it.",
        )

    def test_penalty_constant_is_lt_one(self):
        """Guardrail: the penalty must be a *downweight*, not a boost."""
        self.assertLess(_WONT_CRACK_PENALTY, 1.0)
        self.assertGreater(_WONT_CRACK_PENALTY, 0.0)


if __name__ == "__main__":
    unittest.main()
