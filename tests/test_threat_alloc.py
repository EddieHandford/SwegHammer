"""Fixture sanity for SWEG_THREAT_ALLOC — the allocation-aware threat field
(docs/DECISION_LEDGER.md "ALLOCATION-AWARE THREAT FIELD" registration).

The summed field counts every enemy's FULL output against every cell (the
measured 6x-301x predicted-to-realized saturation,
scripts/diag_threat_calibration.py). The owner's design rule: an enemy with
ONE eligible target sends everything at it; an enemy with several splits the
RISK across them. Gate ON, each enemy E's contribution c is weighted
attractiveness-proportionally AND by the measured OPPORTUNITY-CONDITIONED
attack-propensity step curve (docs/DECISION_LEDGER.md "THREAT-FIELD
PARTICIPATION RATE" and its funded fallback: the probability a living
activated enemy slot attempts output, conditioned on the enemy's own best
expected-wounds opportunity — fitted on the seed-base-0 battery: 0.003 at
zero opportunity, 0.393 on (0, 0.5], 0.525 on (0.5, 1.5], 0.510 on (1.5, 3],
0.614 above 3 — part of the allocated form, same gate):

    w_E(me@p) = c / (c + Sum over my OTHER alive units t of
                         ew(E -> t at t's current position))
    contribution = c * w_E(me@p) * _attack_propensity(opp_E)

where opp_E is E's best per-pair expected wounds over my units at current
positions (the max over the cached denominator terms).

These fixtures pin the registered cases by hand computation:
  (i)   one eligible target  -> the summed field TIMES the curve value
        for the enemy's opportunity bucket (allocation degeneracy: w = 1),
  (ii)  two identical eligible targets -> each contribution halves, times
        the curve value,
  (iii) the isolated-vs-supported pair (the two-Berzerker scenario class)
        re-priced: alone soaks the full melee threat (times the curve
        value), supported splits it,
  (iv)  the truly isolated lone-army case: allocation degeneracy times the
        curve value — the propensity applies even at one eligible target.

Byte-identity of the OFF path is proved separately by the fixed-seed event
digest (scripts/sim_motion_proof.py), not here.
"""
from __future__ import annotations

import os
import unittest

from code.map import TerrainType
from code.strategy import (
    _attack_propensity,
    _threat_field_at,
    _threat_projectors,
)
from code.units import UnitProfile


class _Unit:
    def __init__(self, profile, position, uid):
        self.profile = profile
        self.position = position
        self.uid = uid
        self.current_health = profile.health
        self.army_ref = None


class _Army:
    """Minimal army stand-in: alive_units + the army_ref back-pointer the
    allocation denominators read. No _battle_ref, so the gate helper falls
    back to the environment read (each test manages the env in try/finally)."""

    def __init__(self, name):
        self.name = name
        self.units = []
        self._battle_ref = None

    @property
    def alive_units(self):
        return [u for u in self.units if u.current_health > 0]

    def add(self, unit):
        self.units.append(unit)
        unit.army_ref = self
        return unit


class _Map:
    def __init__(self):
        self.objectives = []
        self.width = 60.0
        self.height = 44.0
        self.terrain = ()                 # no terrain -> everywhere OPEN

    def cover_at(self, point):
        return TerrainType.OPEN

    def is_blocked(self, point):
        return False


def _gun_enemy():
    """4 shots, 4+ to hit, S4 AP0 D1, 24" range, Move 6 — no melee."""
    return UnitProfile(
        name="Gun", health=6, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4, move=6.0, oc=1,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        points_override=100,
    )


def _berzerker():
    """Melee-only: 6 attacks, 4+ to hit, S6 AP-1 D1, Move 6 — no gun."""
    return UnitProfile(
        name="Berzerker", health=8, damage=1, hit_probability=0.0,
        ap=0, save=3, strength=4, toughness=5, move=6.0, oc=2,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=0,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=6, melee_ap=-1,
        points_override=120,
    )


def _body():
    """The measured unit: T4, 4+ save, 5 wounds."""
    return UnitProfile(
        name="Body", health=5, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4, move=6.0, oc=2,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        points_override=80,
    )


class _AllocGate:
    """Set/unset SWEG_THREAT_ALLOC around a block (try/finally discipline)."""

    def __enter__(self):
        os.environ["SWEG_THREAT_ALLOC"] = "1"

    def __exit__(self, *exc):
        del os.environ["SWEG_THREAT_ALLOC"]


class ThreatAllocFixtures(unittest.TestCase):
    """HAND VALUES common to the fixtures. The gun enemy's per-pair ranged
    expected wounds onto a Body in the OPEN:

        rw = shots(4) * hit(0.5)
             * wound_probability(4,4) = 1/2 (S == T)
             * (1 - save_probability(4,0)) = 1/2
             * damage(1.0)
           = 4 * 0.5 * 0.5 * 0.5 = 0.5

    The Berzerker's melee kill-potential onto a Body:

        mw = attacks(6) * hit(0.5)
             * wound_probability(6,4) = 2/3 (S > T, not >= 2T)
             * (1 - save_probability(4,-1)) = 2/3 (5+ after AP)
             * damage(1.0)
           = 3 * (2/3) * (2/3) = 4/3
    """

    def test_i_single_eligible_target_summed_times_propensity(self):
        """(i) ALLOCATION DEGENERACY: I am the enemy's only eligible target —
        a second friendly stands at (55,40), 60.8" from the gun at (10,0),
        outside its Move(6) + range(24) = 30" reach, so its denominator term
        is ZERO and w = c/(c+0) = 1. The allocated contribution is the summed
        one times the curve value for the gun's opportunity bucket:

            summed = rw = 0.5      (the gun 10" from me, within its 30"
                                    reach, no melee half)
            BUCKET LOOKUP: the gun's best per-pair term over my units is
            ew(E->me@current) = 0.5 (the far friendly contributes 0), so
            opp_E = 0.5 -> bucket (0, 0.5] -> rho = 0.393
            allocated = 0.5 * 1.0 * 0.393 = 0.1965"""
        map_ = _Map()
        mine = _Army("mine")
        enemy = _Army("enemy")
        me = mine.add(_Unit(_body(), (0.0, 0.0), "A0"))
        mine.add(_Unit(_body(), (55.0, 40.0), "A1"))     # out of the gun's reach
        enemy.add(_Unit(_gun_enemy(), (10.0, 0.0), "B0"))
        proj = _threat_projectors(enemy)
        summed = _threat_field_at(me, proj, me.position, map_)
        with _AllocGate():
            allocated = _threat_field_at(me, proj, me.position, map_)
        self.assertAlmostEqual(summed, 0.5, delta=1e-9)          # hand value
        self.assertAlmostEqual(_attack_propensity(0.5), 0.393, delta=1e-12)
        self.assertAlmostEqual(allocated, 0.1965, delta=1e-9)    # x 1.0 x rho
        self.assertAlmostEqual(allocated, summed * 0.393, delta=1e-9)

    def test_ii_two_identical_eligible_targets_halve_each_contribution(self):
        """(ii) Two IDENTICAL eligible targets: a twin Body at (0,4) — 10.8"
        from the gun, inside its 30" reach, identical profile in identical
        OPEN cover, so ew(E->twin) = ew(E->me) = 0.5 (the ranged term is
        range-gated, not distance-scaled). w = 0.5/(0.5+0.5) = 1/2.
        BUCKET LOOKUP: opp_E = max(0.5, 0.5) = 0.5 -> bucket (0, 0.5] ->
        rho = 0.393:

            allocated = summed * 1/2 * 0.393 = 0.5 * 0.5 * 0.393 = 0.09825"""
        map_ = _Map()
        mine = _Army("mine")
        enemy = _Army("enemy")
        me = mine.add(_Unit(_body(), (0.0, 0.0), "A0"))
        mine.add(_Unit(_body(), (0.0, 4.0), "A1"))       # the identical twin
        enemy.add(_Unit(_gun_enemy(), (10.0, 0.0), "B0"))
        proj = _threat_projectors(enemy)
        summed = _threat_field_at(me, proj, me.position, map_)
        with _AllocGate():
            allocated = _threat_field_at(me, proj, me.position, map_)
        self.assertAlmostEqual(summed, 0.5, delta=1e-9)
        self.assertAlmostEqual(allocated, 0.09825, delta=1e-9)   # half x rho

    def test_iii_isolated_vs_supported_repriced(self):
        """(iii) The two-Berzerker scenario class, re-priced. A melee
        Berzerker at (10,0) projects onto a Body at the origin:

            c = mw(4/3) * P(2D6 >= 10 - Move(6) - engage(1.0) = 3.0)
              = (4/3) * (35/36) = 35/27 = 1.296296...

        ISOLATED (me the only friendly): w = 1. BUCKET LOOKUP: opp_E =
        ew(Z->me@current) = 35/27 = 1.296 -> bucket (0.5, 1.5] -> rho =
        0.525, so
            allocated = (35/27) * 0.525 = 0.680555...

        SUPPORTED (a friend at (12,0), 2" from the Berzerker — charge needed
        -5 -> reach probability 1, so its term = mw * 1 = 4/3 = 36/27):

            w_me = (35/27) / ((35/27) + (36/27)) = 35/71
            BUCKET LOOKUP: opp_E = max(35/27, 4/3) = 4/3 = 1.333 -> still
            bucket (0.5, 1.5] -> rho = 0.525
            allocated = (35/27) * (35/71) * 0.525
                      = (1225/1917) * 0.525 = 0.335485...

        Standing next to a supported friend roughly halves the priced threat,
        while the isolated body soaks the whole (propensity-scaled)
        projection — the exact asymmetry the summed field was blind to."""
        map_ = _Map()
        # ISOLATED
        mine_a = _Army("mine_a")
        enemy_a = _Army("enemy_a")
        me_a = mine_a.add(_Unit(_body(), (0.0, 0.0), "A0"))
        enemy_a.add(_Unit(_berzerker(), (10.0, 0.0), "B0"))
        proj_a = _threat_projectors(enemy_a)
        summed_alone = _threat_field_at(me_a, proj_a, me_a.position, map_)
        with _AllocGate():
            alloc_alone = _threat_field_at(me_a, proj_a, me_a.position, map_)
        self.assertAlmostEqual(summed_alone, 35.0 / 27.0, delta=1e-9)
        self.assertAlmostEqual(_attack_propensity(35.0 / 27.0), 0.525,
                               delta=1e-12)
        self.assertAlmostEqual(alloc_alone, (35.0 / 27.0) * 0.525,
                               delta=1e-9)

        # SUPPORTED
        mine_b = _Army("mine_b")
        enemy_b = _Army("enemy_b")
        me_b = mine_b.add(_Unit(_body(), (0.0, 0.0), "A0"))
        mine_b.add(_Unit(_body(), (12.0, 0.0), "A1"))    # the supported friend
        enemy_b.add(_Unit(_berzerker(), (10.0, 0.0), "B0"))
        proj_b = _threat_projectors(enemy_b)
        with _AllocGate():
            alloc_supported = _threat_field_at(me_b, proj_b, me_b.position,
                                               map_)
        self.assertAlmostEqual(_attack_propensity(4.0 / 3.0), 0.525,
                               delta=1e-12)
        self.assertAlmostEqual(alloc_supported, (1225.0 / 1917.0) * 0.525,
                               delta=1e-9)
        self.assertLess(alloc_supported, alloc_alone)    # support splits risk

    def test_iv_propensity_applies_even_at_one_eligible_target(self):
        """(iv) DESIGN POINT (docs/DECISION_LEDGER.md "THREAT-FIELD
        PARTICIPATION RATE"): the propensity is NOT part of the allocation
        split — it is the probability the enemy attempts output AT ALL, and
        the allocation weight is the split GIVEN an attempt. So even a truly
        isolated target (a lone-unit army, n = 1, allocation weight exactly
        1 by degeneracy) prices the enemy's threat at the summed value times
        the curve value for the enemy's opportunity: the isolated unit is
        still only shot if the enemy spends its activation on output rather
        than the objective game — the measured behaviour the decomposition
        instrument quantified.

            summed = rw = 0.5
            BUCKET LOOKUP: opp_E = ew(E->me@current) = 0.5 (I am its whole
            opportunity set) -> bucket (0, 0.5] -> rho = 0.393
            allocated = 0.5 * 1.0 * 0.393 = 0.1965"""
        map_ = _Map()
        mine = _Army("mine")
        enemy = _Army("enemy")
        me = mine.add(_Unit(_body(), (0.0, 0.0), "A0"))  # the ONLY friendly
        enemy.add(_Unit(_gun_enemy(), (10.0, 0.0), "B0"))
        proj = _threat_projectors(enemy)
        summed = _threat_field_at(me, proj, me.position, map_)
        with _AllocGate():
            allocated = _threat_field_at(me, proj, me.position, map_)
        self.assertAlmostEqual(summed, 0.5, delta=1e-9)
        self.assertAlmostEqual(allocated, summed * 1.0 * 0.393, delta=1e-9)
        self.assertAlmostEqual(allocated, 0.1965, delta=1e-9)


if __name__ == "__main__":
    unittest.main()
