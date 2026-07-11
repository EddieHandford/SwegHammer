"""Fixture sanity for SWEG_SHOOT_VALUE — the shooting-phase target-value
consumer (iteration 8 of the canary loop, docs/DECISION_LEDGER.md "THE DENIAL
PROGRAM + CANARY LOOP").

score(target) = KILL VALUE + MARKER RELEVANCE (eviction) + THREAT RELEVANCE,
all in the measured victory-point currency, chosen by a REPLACEMENT argmax
when the gate is on. These fixtures hand-pin the three terms and the eviction
preference the iteration-7 victory-point ledger demanded (stop pouring fire
into Poxwalker-like chaff with no marker leverage; evict the squad whose loss
actually flips a marker). All numbers hand-computed to 1e-9; the measured
constants (_MEASURED_VP_PER_POINT, _attack_propensity) enter symbolically.
Byte-identity of the OFF path is proved by the fixed-seed event digests
(scripts/sim_motion_proof.py), reported with the build — fixture (q) here
pins only the gate reader itself.
"""
from __future__ import annotations

import os
import unittest

from code.simulator import Battle
from code.strategy import (
    _MEASURED_VP_PER_POINT,
    _attack_propensity,
    _kill_potential_wounds,
    _score_profile,
    _shoot_value_on,
    _shoot_value_score,
)
from code.units import UnitProfile
from tests.test_job_layer import (
    _Army,
    _Map,
    _Obj,
    _Unit,
    _light_gun,
    _one_wound_body,
)

RATE = _MEASURED_VP_PER_POINT
CUR_ROUND = 1        # srr = 5


def _closing_monster():
    """A closing high-threat monster for fixture (p): twelve S6 AP-2 shots at
    0.5 hit (5.0 expected wounds onto a T3/5+ one-wound body; 10/3 onto the
    T4/4+ gunner), 12 wounds, 300 points, no melee (keeps the reversed-field
    hand numbers to the ranged term alone)."""
    return UnitProfile(
        name="ClosingMonster", health=12, damage=1, hit_probability=0.5,
        ap=-2, save=4, strength=6, toughness=3, move=6.0, oc=2,
        attacks=12, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=8, faction="Generic", unit_keywords=("MONSTER",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=6, melee_ap=0,
        points_override=300,
    )


class ShootValueScore(unittest.TestCase):
    def test_n_chaff_squad_low_marker_relevance(self):
        """(n) A 10-model Poxwalker-like squad on a marker, expected 2 kills:
        the eviction term is prorated LOW — 2 expected kills against 10
        models needed to flip.

        HAND COMPUTATION (srr=5; the _light_gun's expected wounds onto a
        T3/5+ one-wound body: 8 x 0.5 hit x wound(3,3)=0.5 x AP-2 negating
        the 5+ save x damage 1 = 2.0 exactly; no terrain -> attenuation 1):
          KILL   = min(2.0, 1 wound) x (6 points / 1 wound) x rate = 6 x rate
          MARKER = their objective control 20 (10 models x 2) vs ours 0 ->
                   needed = ceil(20 / 2) = 10 models; expected models killed
                   = 2.0 / 1 wound = 2 -> proration 0.2 ->
                   5 vp x 5 srr x 0.2 = 5.0 exactly
          THREAT = 0 (the attacker at (0,0) is 37 inches from the squad —
                   outside its 18-inch ranged and 19.5-inch melee reach)
          total  = 5.0 + 6 x rate = 5.091488"""
        attacker = _Unit(_light_gun(), (0.0, 0.0), uid=1)
        attacker_army = _Army([attacker])
        targets = [_Unit(_one_wound_body(), (30.0, 22.0), uid=10 + i)
                   for i in range(10)]
        defender_army = _Army(targets, is_a=False)
        marker = _Obj(30.0, 22.0)
        map_ = _Map([marker])

        got = _shoot_value_score(attacker, targets[0], attacker_army,
                                 defender_army, map_, CUR_ROUND)
        expected = 5.0 + 6.0 * RATE
        self.assertAlmostEqual(got, expected, delta=1e-9)

    def test_o_evictable_squad_high_marker_relevance(self):
        """(o) A 5-model squad holding a marker where 2 expected kills FLIPS
        control: the eviction term prices the full 25 and the total towers
        over fixture (n)'s — the eviction preference, pinned.

        HAND COMPUTATION: their objective control 10 (5 x 2) vs ours 6
        (three of my own bodies inside the radius) -> needed = ceil(4/2) = 2
        models; expected kills 2.0 -> proration min(1, 2/2) = 1 ->
        MARKER = 25.0 exactly. KILL = 6 x rate as in (n). THREAT: the target
        (1 inch from my three bodies) projects c = 1/6 ranged + 1/6 melee
        = 1/3 onto each; allocation share (1/3)/1 = 1/3, propensity keyed on
        its best opportunity 1/3; per body min((1/3)(1/3)prop, 1 wound) x
        6 x rate; P(kill) = min(1, 2/1) = 1:
          THREAT = 3 x (prop/9) x 6 x rate = 2 x rate x prop(1/3)
          total  = 25 + 6 x rate + 2 x rate x prop(1/3)   >  total(n)"""
        attacker = _Unit(_light_gun(), (0.0, 0.0), uid=1)
        my_bodies = [_Unit(_one_wound_body(), (60.0, 22.0), uid=2 + i)
                     for i in range(3)]
        attacker_army = _Army([attacker] + my_bodies)
        targets = [_Unit(_one_wound_body(), (61.0, 22.0), uid=10 + i)
                   for i in range(5)]
        defender_army = _Army(targets, is_a=False)
        marker = _Obj(60.0, 22.0)
        map_ = _Map([marker])

        # Pin the reversed-field primitives first (guards the hand numbers).
        tp = _score_profile(targets[0])
        self.assertAlmostEqual(
            Battle._ranged_expected_wounds(tp, my_bodies[0]), 1.0 / 6.0,
            delta=1e-9)
        self.assertAlmostEqual(
            _kill_potential_wounds(tp, _score_profile(my_bodies[0])),
            1.0 / 6.0, delta=1e-9)

        got = _shoot_value_score(attacker, targets[0], attacker_army,
                                 defender_army, map_, CUR_ROUND)
        prop = _attack_propensity(1.0 / 3.0)
        expected = 25.0 + 6.0 * RATE + 2.0 * RATE * prop
        self.assertAlmostEqual(got, expected, delta=1e-9)

        # The eviction preference: (o) towers over (n).
        n_total = 5.0 + 6.0 * RATE
        self.assertGreater(got, n_total)

    def test_p_closing_monster_scores_threat_relevance(self):
        """(p) A closing high-threat monster scores its threat-relevance
        term: killing it removes the threat it projects onto the line.

        HAND COMPUTATION (attacker's expected wounds onto the T3/4+ monster:
        8 x 0.5 x wound(3,3)=0.5 x fail(4+ save at AP-2 -> 6+) = 5/6 -> ew =
        5/3; monster's reversed field: 10/3 onto the T4/4+ gunner, 5.0 onto
        each T3/5+ body, all within its 30-inch reach):
          KILL   = min(5/3, 12) x (300/12) x rate = (5/3) x 25 x rate
          MARKER = 0 (no markers on the map)
          THREAT: total c = 10/3 + 4 x 5 = 70/3; propensity keyed on max c
            = 5.0; gunner share (10/3)/(70/3) = 1/7 -> allocated (10/21)prop
            (under its 4 wounds) x (50/4) x rate; each body share 5/(70/3) =
            3/14 -> allocated (15/14)prop, capped at its 1 wound, x 6 x rate;
            P(kill) = min(1, (5/3)/12) = 5/36."""
        attacker = _Unit(_light_gun(), (0.0, 0.0), uid=1)
        bodies = [_Unit(_one_wound_body(), (10.0, 0.0), uid=2 + i)
                  for i in range(4)]
        attacker_army = _Army([attacker] + bodies)
        monster = _Unit(_closing_monster(), (20.0, 0.0), uid=99)
        defender_army = _Army([monster], is_a=False)
        map_ = _Map([])

        got = _shoot_value_score(attacker, monster, attacker_army,
                                 defender_army, map_, CUR_ROUND)
        prop = _attack_propensity(5.0)
        kill = (5.0 / 3.0) * 25.0 * RATE
        threat_vp = (min((10.0 / 21.0) * prop, 4.0) * 12.5 * RATE
                     + 4.0 * min((15.0 / 14.0) * prop, 1.0) * 6.0 * RATE)
        expected = kill + (5.0 / 36.0) * threat_vp
        self.assertAlmostEqual(got, expected, delta=1e-9)
        self.assertGreater(got, kill)     # the threat term is priced, not zero

    def test_q_gate_reader_default_off(self):
        """(q) The gate is off by default and reads on only at exactly "1".
        Byte-identity of every arm with the gate off is proved by the
        fixed-seed digests reported with the build (the gate-off code path in
        both wiring points is the untouched legacy picker)."""
        self.assertFalse(_shoot_value_on())
        os.environ["SWEG_SHOOT_VALUE"] = "1"
        try:
            self.assertTrue(_shoot_value_on())
        finally:
            del os.environ["SWEG_SHOOT_VALUE"]
        os.environ["SWEG_SHOOT_VALUE"] = "0"
        try:
            self.assertFalse(_shoot_value_on())
        finally:
            del os.environ["SWEG_SHOOT_VALUE"]


if __name__ == "__main__":
    unittest.main()
