"""Pin SWEG_VALUE_OFFENSE — the output term of the value field (rider on the
SWEG_VALUE_MOVE consumer, strategy.value_offense / _offense_eligibility).

Mechanism: a candidate move destination is priced not only by the marker's
value and the body's exposure but by the OUTPUT the unit can deliver from that
cell — expected wounds dealt, converted to victory points with the SAME
exchange rate the trade evaluator uses (_trade_vp_per_wound), taken as the BEST
single reachable target (iteration 2, mirroring _trade_our_return — the v1
sum-over-targets form over-credited multi-target platforms in the cell-1
screen), discounted over the scoring horizon. See the value_offense section
header in code/strategy.py for the full derivation.

These fixtures are hand-computed to 1e-9 against the universal 10e helpers
(wound_probability / save_probability / _prob_to_target), and check the
move-class conditioning the resolution engine enforces:

  * stationary  -> full ranged output INCLUDING the Heavy +1 to hit
  * normal move -> ranged output WITHOUT the Heavy bonus
  * advance     -> ranged only if a shoot-after-advance exemption holds; melee
                   only if an advance-charge exemption holds

Byte-identity of the OFF path is proved separately by the fixed-seed event
digest (see the commit body), not here.
"""
from __future__ import annotations

import math
import unittest

from code.strategy import (
    _OFFENSE_MAX_ADVANCE,
    _offense_charge_after_advance_ok,
    _offense_eligibility,
    _offense_move_class,
    _offense_shoot_after_advance_ok,
    _p_2d6_at_least,
    _trade_vp_per_wound,
    value_offense,
)
from code.units import UnitProfile, _prob_to_target, save_probability, wound_probability


def _mover(heavy: bool = True, assault: bool = False) -> UnitProfile:
    """Heavy (optionally Assault) ranged platform with a real melee profile.

    Ranged: 10 shots, 4+ to hit, S8 AP-2 D2, 24" range.
    Melee:  6 attacks, 4+, S6 AP-1 D1.
    200-point 10-wound body (points_override pins points_cost so the exchange
    rate is exact)."""
    return UnitProfile(
        name="HeavyGun", health=10, damage=1, hit_probability=0.5,
        ap=-2, save=3, strength=8, toughness=5,
        attacks=10, weapon_damage_per_shot=2.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=6, melee_ap=-1,
        heavy=heavy, assault=assault, points_override=200,
    )


def _target() -> UnitProfile:
    """T4 W10 3+ save, 100 points (points_override pins the exchange rate)."""
    return UnitProfile(
        name="Target", health=10, damage=1, hit_probability=0.5,
        ap=0, save=3, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=100,
    )


class _Stand:
    """Minimal unit stand-in exposing exactly what value_offense /
    _offense_eligibility read (profile, position, current_health, and the two
    transient stratagem flags). No squad_profile_ref -> _score_profile returns
    .profile."""

    def __init__(self, profile, position, current_health,
                 transient_assault=False, transient_charge=False):
        self.profile = profile
        self.position = position
        self.current_health = current_health
        self.transient_assault_this_round = transient_assault
        self.transient_charge_after_advance = transient_charge


class _NoDetArmy:
    """Army stand-in with no detachment and no Battle Focus tokens — every
    detachment/Star-Engines exemption is therefore inert."""

    def resolve_detachment(self):
        return None

    battle_focus_tokens = 0


SRR = 2   # scoring rounds remaining (horizon)


def _ranged_ew(mp, tp, extra_hit_mod):
    """Independent re-derivation of Battle._ranged_expected_wounds for these
    fixtures (S8 vs T4, AP-2 vs 3+, no anti / torrent / cover)."""
    hit = mp.hit_probability
    if extra_hit_mod:
        hit = (7 - max(2, min(7, _prob_to_target(hit) - extra_hit_mod))) / 6.0
    wound = wound_probability(mp.strength, tp.toughness)
    save_fail = 1.0 - save_probability(tp.save, mp.ap)
    return mp.attacks * hit * wound * save_fail * mp.per_shot_damage


def _vp_per_wound(tp):
    return (tp.points_cost / tp.health) * ((5.0 * SRR) / 175.0)


class ValueOffenseArithmetic(unittest.TestCase):
    def test_stationary_ranged_includes_heavy_bonus(self):
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        # target at 20" — in 24" range, well OUT of melee charge reach.
        e = _Stand(tp, (20.0, 0.0), 10.0)
        got = value_offense(me, me.position, True, True, True, [e], None, SRR)
        expect = _ranged_ew(mp, tp, 1) * _vp_per_wound(tp)   # +1 Heavy
        self.assertAlmostEqual(got, expect, delta=1e-9)

    def test_normal_ranged_excludes_heavy_bonus(self):
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        e = _Stand(tp, (20.0, 0.0), 10.0)
        got = value_offense(me, me.position, True, False, True, [e], None, SRR)
        expect = _ranged_ew(mp, tp, 0) * _vp_per_wound(tp)   # no Heavy
        self.assertAlmostEqual(got, expect, delta=1e-9)

    def test_stationary_strictly_exceeds_normal(self):
        """Heavy +1 makes the stationary candidate outscore the normal one from
        the same cell against the same target — the defect this rider fixes."""
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        e = _Stand(tp, (20.0, 0.0), 10.0)
        stat = value_offense(me, me.position, True, True, True, [e], None, SRR)
        norm = value_offense(me, me.position, True, False, True, [e], None, SRR)
        self.assertGreater(stat, norm)

    def test_advance_ranged_zero_when_not_eligible(self):
        """A non-Assault unit that has to Advance loses its shooting entirely."""
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        e = _Stand(tp, (20.0, 0.0), 10.0)   # out of melee range
        got = value_offense(me, me.position, False, False, False, [e], None, SRR)
        self.assertEqual(got, 0.0)

    def test_advance_assault_retains_ranged_equals_normal(self):
        """An Assault unit keeps its full (non-Heavy) ranged output on Advance."""
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        e = _Stand(tp, (20.0, 0.0), 10.0)
        adv = value_offense(me, me.position, True, False, False, [e], None, SRR)
        norm = value_offense(me, me.position, True, False, True, [e], None, SRR)
        self.assertAlmostEqual(adv, norm, delta=1e-9)   # melee inert at 20"
        self.assertGreater(adv, 0.0)

    def test_offense_identical_targets_price_as_one_not_double(self):
        """Iteration 2 (best single target): two identical reachable targets
        price exactly the same as one — no multi-target over-credit."""
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        e1 = _Stand(_target(), (18.0, 0.0), 10.0)
        e2 = _Stand(_target(), (0.0, 20.0), 10.0)
        one = value_offense(me, me.position, True, False, True, [e1], None, SRR)
        both = value_offense(me, me.position, True, False, True, [e1, e2], None, SRR)
        self.assertAlmostEqual(both, one, delta=1e-9)

    def test_offense_equals_better_single_target_not_sum(self):
        """Iteration 2 (cell-1 screen reprice): with two reachable targets of
        different value, the offense equals the BETTER single target's converted
        value — never the sum (the v1 form that over-credited multi-target
        platforms: Imperial Knights +5.30, Tyranids +6.59 wrong-direction)."""
        import dataclasses
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        cheap = _target()                       # 100 points, 10 wounds
        dear = dataclasses.replace(_target(), points_override=300)  # 3x pts/wound
        e_cheap = _Stand(cheap, (18.0, 0.0), 10.0)
        e_dear = _Stand(dear, (0.0, 20.0), 10.0)
        got = value_offense(
            me, me.position, True, False, True, [e_cheap, e_dear], None, SRR)
        cheap_only = value_offense(
            me, me.position, True, False, True, [e_cheap], None, SRR)
        dear_only = value_offense(
            me, me.position, True, False, True, [e_dear], None, SRR)
        self.assertGreater(dear_only, cheap_only)
        self.assertAlmostEqual(got, dear_only, delta=1e-9)      # the better one
        self.assertLess(got, cheap_only + dear_only - 1e-12)    # never the sum

    def test_per_target_capped_at_remaining_wounds(self):
        """A nearly-dead target caps removable value at its remaining wounds."""
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        e = _Stand(_target(), (20.0, 0.0), 1.0)   # 1 wound left
        got = value_offense(me, me.position, True, True, True, [e], None, SRR)
        expect = min(_ranged_ew(mp, tp, 1), 1.0) * _vp_per_wound(tp)
        self.assertAlmostEqual(got, expect, delta=1e-9)


class ExemptionWeb(unittest.TestCase):
    """Advance-class melee is priced ONLY under an advance-charge exemption
    readable at decision time — the difference between a Khorne daemon (keeps
    melee threat after advancing) and a generic melee unit (loses it)."""

    def test_melee_on_advance_zero_without_exemption(self):
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0)   # no transient_charge_after_advance
        e = _Stand(tp, (6.0, 0.0), 10.0)    # 6" -> in charge reach
        _r, _h, _m = _offense_eligibility(me, _NoDetArmy(), None, "advance")
        self.assertFalse(_m)   # melee NOT allowed on advance
        got = value_offense(me, me.position, _r, _h, _m, [e], None, SRR)
        # ranged also 0 (non-Assault, no exemption); so total is 0.
        self.assertEqual(got, 0.0)

    def test_melee_on_advance_nonzero_with_transient_charge_flag(self):
        mp, tp = _mover(), _target()
        me = _Stand(mp, (0.0, 0.0), 10.0, transient_charge=True)
        e = _Stand(tp, (6.0, 0.0), 10.0)
        self.assertTrue(_offense_charge_after_advance_ok(me, _NoDetArmy(), None))
        _r, _h, _m = _offense_eligibility(me, _NoDetArmy(), None, "advance")
        self.assertTrue(_m)    # melee allowed via Apoplectic-Frenzy transient
        got = value_offense(me, me.position, _r, _h, _m, [e], None, SRR)
        # melee-only expected value (ranged still 0: non-Assault advance).
        from code.strategy import _kill_potential_wounds
        needed = 6.0 - 1.0   # dist - engagement range
        mw = _kill_potential_wounds(mp, tp) * _p_2d6_at_least(needed)
        expect = min(mw, 10.0) * _vp_per_wound(tp)
        self.assertGreater(got, 0.0)
        self.assertAlmostEqual(got, expect, delta=1e-9)

    def test_shoot_after_advance_assault_flag(self):
        assault_mp = _mover(assault=True)
        me = _Stand(assault_mp, (0.0, 0.0), 10.0)
        self.assertTrue(_offense_shoot_after_advance_ok(me, _NoDetArmy(), None))
        plain = _Stand(_mover(assault=False), (0.0, 0.0), 10.0)
        self.assertFalse(_offense_shoot_after_advance_ok(plain, _NoDetArmy(), None))


class MoveClassGeometry(unittest.TestCase):
    def test_move_class_boundaries(self):
        mp = _mover()
        me = _Stand(mp, (0.0, 0.0), 10.0)
        my_move = 6.0

        class _Obj:
            def __init__(self, x, y):
                self.x, self.y = x, y

        # on the marker it holds -> stationary, fires from its own cell.
        held = _Obj(3.0, 0.0)
        mc, cell = _offense_move_class(me, held, {id(held)}, my_move)
        self.assertEqual(mc, "stationary")
        self.assertEqual(cell, me.position)
        # within a Normal Move -> normal, fires from the centre.
        near = _Obj(5.0, 0.0)
        mc, cell = _offense_move_class(me, near, set(), my_move)
        self.assertEqual(mc, "normal")
        self.assertEqual(cell, (5.0, 0.0))
        # beyond Move but within Move + max Advance -> advance.
        far = _Obj(my_move + _OFFENSE_MAX_ADVANCE - 0.5, 0.0)
        mc, _ = _offense_move_class(me, far, set(), my_move)
        self.assertEqual(mc, "advance")
        # beyond Move + max Advance -> unreachable this turn (None).
        gone = _Obj(my_move + _OFFENSE_MAX_ADVANCE + 5.0, 0.0)
        mc, _ = _offense_move_class(me, gone, set(), my_move)
        self.assertIsNone(mc)

    def test_stationary_and_normal_eligibility(self):
        me = _Stand(_mover(), (0.0, 0.0), 10.0)
        r, h, m = _offense_eligibility(me, _NoDetArmy(), None, "stationary")
        self.assertEqual((r, h, m), (True, True, True))   # Heavy bonus on
        r, h, m = _offense_eligibility(me, _NoDetArmy(), None, "normal")
        self.assertEqual((r, h, m), (True, False, True))  # no Heavy bonus
        # a non-Heavy unit gets no stationary bonus.
        me2 = _Stand(_mover(heavy=False), (0.0, 0.0), 10.0)
        r, h, m = _offense_eligibility(me2, _NoDetArmy(), None, "stationary")
        self.assertEqual((r, h, m), (True, False, True))


if __name__ == "__main__":
    unittest.main()
