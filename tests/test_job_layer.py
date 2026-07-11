"""Fixture sanity for SWEG_JOB_LAYER — the job/commitment layer (movement v1).

docs/JOB_LAYER_PROPOSAL.md. Each unit prices three channels in the value field's
victory-point currency and takes the argmax (never the additive sum, never the
classify() label):

  HOLD    = best value_projection over reachable markers,
  KILL    = best value_offense over reachable firing/charging positions,
  SURVIVE = value-at-risk reduction (threat-field frac dropped by repositioning).

An army-level greedy pass assigns holders once per marker (the pile-on fix) and
commitments persist unless strictly dominated. These fixtures pin the channel
derivations and the assignment/persistence logic; the six enumerated cases in the
build brief are one test method each. Byte-identity of the OFF path is proved
separately by the fixed-seed event digest (scripts/sim_motion_proof.py), not here.
"""
from __future__ import annotations

import os
import unittest

from code.map import TerrainType
from code.strategy import (
    _MEASURED_VP_PER_POINT,
    _deny_ds_value,
    _deny_marker_value,
    _job_channel_deny,
    _job_channel_hold,
    _job_channel_kill,
    _job_channel_survive,
    _job_deny_ds_precompute,
    _job_hold_urgency_bonus,
    _job_hold_value_and_threat_at,
    _job_layer_move_intent,
    _threat_field_at,
    _threat_projectors,
    _value_scoring_rounds_remaining,
    assign_jobs,
    classify,
    value_offense,
)
from code.units import UnitProfile


# --------------------------------------------------------------------------
# Minimal stand-ins exposing exactly what the job-layer functions read.
# --------------------------------------------------------------------------
class _Unit:
    def __init__(self, profile, position, current_health=None, uid=0):
        self.profile = profile
        self.position = position
        self.current_health = (profile.health if current_health is None
                               else current_health)
        self.uid = uid
        self.transient_assault_this_round = False
        self.transient_charge_after_advance = False


class _Army:
    def __init__(self, units, is_a=True):
        self.units = list(units)
        self.job_assignments = {}
        self.chosen_secondaries = ()
        self.battle_focus_tokens = 0
        self._battle_ref = None
        self._is_a = is_a

    @property
    def alive_units(self):
        return [u for u in self.units if u.current_health > 0]

    def resolve_detachment(self):
        return None


class _Obj:
    def __init__(self, x, y, control_radius=3.0, vp_per_round=5.0):
        self.x = x
        self.y = y
        self.control_radius = control_radius
        self.vp_per_round = vp_per_round


class _Map:
    def __init__(self, objectives, width=60.0, height=44.0):
        self.objectives = objectives
        self.width = width
        self.height = height
        self.terrain = ()                 # no terrain -> everywhere is OPEN

    def cover_at(self, point):
        return TerrainType.OPEN

    def is_blocked(self, point):
        return False


# --------------------------------------------------------------------------
# Profile builders (all with points_override so the exchange rate is exact).
# --------------------------------------------------------------------------
def _cheap_holder():
    """OC-5, cheap, near-worthless guns — a classic screen/hold body."""
    return UnitProfile(
        name="Holder", health=5, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3, move=6.0, oc=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        points_override=60,
    )


def _eradicator():
    """Short-range melta brick — huge single-target output, OC 1."""
    return UnitProfile(
        name="MeltaBrick", health=6, damage=1, hit_probability=0.5,
        ap=-4, save=3, strength=9, toughness=6, move=5.0, oc=1,
        attacks=6, weapon_damage_per_shot=4.0, range_inches=18,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=3, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=100,
    )


def _fragile_target():
    return UnitProfile(
        name="Softie", health=8, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=5, move=6.0, oc=1,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=90,
    )


def _juicy_tank():
    """A dear, high-wound, low-output tank — worth a lot to kill, barely a
    threat itself (so KILL out-prices SURVIVE cleanly)."""
    return UnitProfile(
        name="JuicyTank", health=16, damage=1, hit_probability=0.5,
        ap=0, save=3, strength=5, toughness=9, move=8.0, oc=1,
        attacks=3, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=8, faction="Generic", unit_keywords=("VEHICLE",),
        melee_attacks=3, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=5, melee_ap=0,
        points_override=400,
    )


def _expensive_fragile():
    """Dear body, short-ranged, no melee reach — the SURVIVE archetype."""
    return UnitProfile(
        name="Centrepiece", health=12, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=5, toughness=6, move=6.0, oc=2,
        attacks=3, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=5, melee_ap=0,
        points_override=250,
    )


def _long_range_gun():
    """A hard-hitting medium-range shooter used to project lethal threat."""
    return UnitProfile(
        name="Sniper", health=6, damage=1, hit_probability=0.667,
        ap=-3, save=3, strength=10, toughness=5, move=6.0, oc=1,
        attacks=12, weapon_damage_per_shot=3.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=150,
    )


def _melee_monster():
    """A centrepiece MELEE monster whose classify() label is HEAVY/DUAL (health
    >= 8, save <= 3), not MELEE — the recorded Mortarion misclassification. Its
    KILL channel must derive from the melee arithmetic, never the label."""
    return UnitProfile(
        name="Monster", health=16, damage=1, hit_probability=0.5,
        ap=-2, save=2, strength=6, toughness=10, move=8.0, oc=4,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=0,
        leadership=8, faction="Generic", unit_keywords=("MONSTER",),
        melee_attacks=10, melee_damage_per_shot=3.0,
        melee_hit_probability=0.667, melee_strength=14, melee_ap=-3,
        points_override=350,
    )


def _heavy_gunline():
    """A Heavy-weapon fire platform with no melee — the zero-value-routing
    gunline archetype for fixture (g)."""
    return UnitProfile(
        name="GunlineHeavy", health=8, damage=1, hit_probability=0.5,
        ap=-1, save=3, strength=6, toughness=5, move=6.0, oc=2,
        attacks=6, weapon_damage_per_shot=2.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        heavy=True, points_override=150,
    )


def _melee_brute():
    """A melee-only high-OC brute used as the distant enemy in fixture (g):
    it projects no threat at long range and makes its own marker unappealing
    (contested at high objective control, lethal to stand next to)."""
    return UnitProfile(
        name="Brute", health=10, damage=1, hit_probability=0.0,
        ap=0, save=4, strength=8, toughness=8, move=6.0, oc=8,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=0,
        leadership=7, faction="Generic", unit_keywords=("MONSTER",),
        melee_attacks=8, melee_damage_per_shot=2.0,
        melee_hit_probability=0.667, melee_strength=8, melee_ap=-2,
        points_override=200,
    )


def _modest_killer():
    """A MIDDLING shooter — not an Eradicator-class melta brick (contrast
    _eradicator): OC-4, 6 shots at 4+, S5 AP-1 D1, 12in range, 75 points. Used
    by the exchange-rate-reprice fixture below: a plausible, modest amount of
    output, not a dominant one."""
    return UnitProfile(
        name="ModestKiller", health=5, damage=1, hit_probability=0.5,
        ap=-1, save=5, strength=5, toughness=3, move=6.0, oc=4,
        attacks=6, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        points_override=75,
    )


def _modest_prize():
    """A dear, fragile 2-wound target — 300 points over 2 wounds (150
    points-per-wound), dear enough per wound that the OLD asserted exchange
    rate over-priced even a MODEST kill above a marker's real HOLD value; the
    MEASURED rate does not. See ExchangeRateReprice for the hand-computation."""
    return UnitProfile(
        name="ModestPrize", health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4, move=6.0, oc=1,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=300,
    )


def _flanker():
    """A 12"-gun skirmisher with no melee — used by the risk-discount fixture
    (j): out of range standing still, it must pick a move cell, and two cells
    offer IDENTICAL raw offense against identical prey."""
    return UnitProfile(
        name="Flanker", health=6, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4, move=6.0, oc=1,
        attacks=6, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        points_override=80,
    )


def _inert_prey():
    """A harmless, identical target pair for fixture (j): zero guns, zero
    melee, so it projects NO threat and only exists to be shot. Two of these
    at mirrored positions give two candidate cells the SAME raw offense."""
    return UnitProfile(
        name="InertPrey", health=4, damage=1, hit_probability=0.0,
        ap=0, save=4, strength=3, toughness=4, move=6.0, oc=1,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=0,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        points_override=100,
    )


def _guard_brute():
    """A melee-only T8 bodyguard for fixture (j): the Flanker's S4 gun cannot
    wound it better than 6s (the no-wasted-fire exclusion prices it at zero as
    a TARGET), but its melee reach projects heavy threat over the cells near
    the prey it guards — the asymmetry the risk discount must price."""
    return UnitProfile(
        name="GuardBrute", health=12, damage=1, hit_probability=0.0,
        ap=0, save=3, strength=8, toughness=8, move=6.0, oc=2,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=0,
        leadership=7, faction="Generic", unit_keywords=("MONSTER",),
        melee_attacks=8, melee_damage_per_shot=2.0,
        melee_hit_probability=0.5, melee_strength=8, melee_ap=-2,
        points_override=200,
    )


def _reserve_body():
    """A 250-point reserve unit for the deep-strike-denial fixtures: two of these
    make exactly 500 points pending so the DENY_DS reserve factor is exact
    (500 * _MEASURED_VP_PER_POINT)."""
    return UnitProfile(
        name="ReserveBody", health=6, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=5, move=6.0, oc=2,
        attacks=3, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=250,
    )


def _oc_blocker():
    """A near-indestructible, weaponless high-OC body used to plant a fixed
    enemy objective-control total on a marker in the flip-release fixture: OC 8,
    no ranged or melee output (projects zero threat, so contestability stays 1
    and the control brackets are clean) and so tanky that the released holder's
    KILL channel against it stays far below its HOLD value."""
    return UnitProfile(
        name="OcBlocker", health=40, damage=1, hit_probability=0.0,
        ap=0, save=2, strength=3, toughness=14, move=6.0, oc=8,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=0,
        leadership=8, faction="Generic", unit_keywords=("VEHICLE",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        points_override=100,
    )


def _strong_holder():
    """An OC-10 holder for the flip-release fixture: strong enough that its
    reclaim of a marker the enemy holds at objective control 8 gives the marker
    strict majority (5 + 10 > 8), pile-on-skipping the weaker released holder."""
    return UnitProfile(
        name="StrongHolder", health=6, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=3, toughness=4, move=6.0, oc=10,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=8, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        points_override=120,
    )


class _Battle:
    """Minimal Battle stand-in exposing exactly what the DENY channel reads:
    the two armies and the reserve dict keyed by army name (as
    simulator.Battle._reserves is)."""
    def __init__(self, a, b, reserves):
        self.a = a
        self.b = b
        self._reserves = dict(reserves)


CUR_ROUND = 1
SRR = _value_scoring_rounds_remaining(CUR_ROUND)


class ChannelDerivation(unittest.TestCase):
    def test_a_hold_derived_for_cheap_high_oc_unit(self):
        """(a) A cheap high-OC unit near an uncontested marker derives HOLD: it is
        the assigned holder and its move routes to the marker as CAPTURE."""
        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            u = _Unit(_cheap_holder(), (10.0, 10.0), uid=1)
            far_enemy = _Unit(_fragile_target(), (200.0, 200.0), uid=99)
            friendly = _Army([u])
            enemy = _Army([far_enemy], is_a=False)
            marker = _Obj(11.0, 11.0)             # 1.4" away, uncontested
            map_ = _Map([marker])
            assign_jobs(friendly, enemy, map_, CUR_ROUND)
            self.assertEqual(friendly.job_assignments.get(u.uid), id(marker))
            dest, intent = _job_layer_move_intent(
                u, friendly, enemy, map_, None, CUR_ROUND)
            self.assertEqual(intent, "CAPTURE")   # HOLD channel -> claim marker
            # destination lands within the marker's control radius.
            self.assertLessEqual(
                ((dest[0] - marker.x) ** 2 + (dest[1] - marker.y) ** 2) ** 0.5,
                marker.control_radius + 1e-9)
        finally:
            del os.environ["SWEG_JOB_LAYER"]

    def test_b_kill_derived_for_eradicator_with_juicy_target(self):
        """(b) An Eradicator-class unit with a juicy in-range target and no
        holdable marker in reach derives KILL: its KILL price beats HOLD and
        SURVIVE, and (in range) it stays put to shoot."""
        u = _Unit(_eradicator(), (10.0, 10.0), uid=1)
        target = _Unit(_juicy_tank(), (22.0, 10.0), uid=99)   # 12" -> in 18" range
        friendly = _Army([u])
        enemy = _Army([target], is_a=False)
        marker = _Obj(200.0, 200.0)              # unreachable -> HOLD unavailable
        map_ = _Map([marker])
        proj = _threat_projectors(enemy)
        hold_v, hold_obj = _job_channel_hold(
            u, u.profile.oc, [marker], {id(marker): 0}, {id(marker): 0},
            set(), proj, None, SRR, True, ())
        kill_v, _d, _i = _job_channel_kill(u, friendly, None, enemy.alive_units,
                                           None, SRR, proj)
        survive_v, _sd = _job_channel_survive(u, proj, None, SRR)
        self.assertIsNone(hold_obj)               # nothing holdable in reach
        self.assertEqual(hold_v, 0.0)
        self.assertGreater(kill_v, hold_v)
        self.assertGreater(kill_v, survive_v)
        # unassigned (assign_jobs did not run) -> the decision is KILL; in range
        # so it stays and shoots (REPOSITION at its own cell).
        dest, intent = _job_layer_move_intent(
            u, friendly, enemy, map_, None, CUR_ROUND)
        self.assertEqual(intent, "REPOSITION")
        self.assertEqual(dest, u.position)

    def test_c_survive_derived_for_wounded_expensive_unit(self):
        """(c) A wounded dear unit under lethal threat with nothing in range
        derives SURVIVE: its value-at-risk reduction beats HOLD and KILL."""
        u = _Unit(_expensive_fragile(), (30.0, 28.0), current_health=3.0, uid=1)
        # A hard gun 28" away: threatens (move 6 + range 24 = 30" reach) and hits
        # far above 3 remaining wounds -> frac_at_risk == 1 at the current cell,
        # but a full Normal move away (to 34") clears the 30" reach entirely.
        gun = _Unit(_long_range_gun(), (30.0, 0.0), uid=99)
        friendly = _Army([u])
        enemy = _Army([gun], is_a=False)
        map_ = _Map([])                           # no markers -> HOLD unavailable
        proj = _threat_projectors(enemy)
        kill_v, _d, _i = _job_channel_kill(u, friendly, None, enemy.alive_units,
                                           None, SRR, proj)
        survive_v, sdest = _job_channel_survive(u, proj, None, SRR)
        self.assertGreater(survive_v, 0.0)
        self.assertGreater(survive_v, kill_v)     # can't reach the gun -> KILL ~ 0
        dest, intent = _job_layer_move_intent(
            u, friendly, enemy, map_, None, CUR_ROUND)
        self.assertEqual(intent, "REPOSITION")    # SURVIVE retreat
        # the retreat moves AWAY from the gun (increases the separation).
        d_before = ((u.position[0] - gun.position[0]) ** 2
                    + (u.position[1] - gun.position[1]) ** 2) ** 0.5
        d_after = ((dest[0] - gun.position[0]) ** 2
                   + (dest[1] - gun.position[1]) ** 2) ** 0.5
        self.assertGreater(d_after, d_before)

    def test_d_mortarion_case_kill_via_melee_never_reads_classify(self):
        """(d) THE MORTARION CASE: a centrepiece melee monster derives KILL from
        its melee output arithmetic, and the job path NEVER consults classify()."""
        monster = _melee_monster()
        # The coarse label misclassifies it (NOT "MELEE") — the precedent.
        self.assertNotEqual(classify(monster), "MELEE")
        u = _Unit(monster, (10.0, 10.0), uid=1)
        prey = _Unit(_fragile_target(), (24.0, 10.0), uid=99)  # 14" -> a move + charge
        friendly = _Army([u])
        enemy = _Army([prey], is_a=False)
        map_ = _Map([])
        proj = _threat_projectors(enemy)
        kill_v, kdest, kintent = _job_channel_kill(
            u, friendly, None, enemy.alive_units, None, SRR, proj)
        self.assertGreater(kill_v, 0.0)           # melee arithmetic priced it

        # Assert the label is not read on the job path: make classify() explode.
        import code.strategy as strat
        original = strat.classify
        strat.classify = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("classify must not be consulted on the job path"))
        try:
            dest, intent = _job_layer_move_intent(
                u, friendly, enemy, map_, None, CUR_ROUND)
        finally:
            strat.classify = original
        self.assertEqual(intent, "ENGAGE")        # closes to melee the prey


class AssignmentAndPersistence(unittest.TestCase):
    def test_e_pile_on_one_holder_only(self):
        """(e) Two OC units, one marker needing one holder: exactly one is
        assigned; the other is unassigned and falls to another channel."""
        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            u1 = _Unit(_cheap_holder(), (10.0, 10.0), uid=1)
            u2 = _Unit(_cheap_holder(), (10.5, 10.0), uid=2)
            far_enemy = _Unit(_fragile_target(), (200.0, 200.0), uid=99)
            friendly = _Army([u1, u2])
            enemy = _Army([far_enemy], is_a=False)
            marker = _Obj(11.0, 10.0)             # uncontested -> one holder wins
            map_ = _Map([marker])
            assign_jobs(friendly, enemy, map_, CUR_ROUND)
            holders = [uid for uid, oid in friendly.job_assignments.items()
                       if oid == id(marker)]
            self.assertEqual(len(holders), 1)     # pile-on fix: exactly one
        finally:
            del os.environ["SWEG_JOB_LAYER"]

    def test_f_persistence_keeps_marker_when_values_unchanged(self):
        """(f) A committed holder keeps its marker across two activations when the
        priced values are unchanged (strict-domination persistence)."""
        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            u = _Unit(_cheap_holder(), (11.0, 10.0), uid=1)   # sits on marker
            far_enemy = _Unit(_fragile_target(), (200.0, 200.0), uid=99)
            friendly = _Army([u])
            enemy = _Army([far_enemy], is_a=False)
            marker = _Obj(11.0, 10.0)
            map_ = _Map([marker])
            assign_jobs(friendly, enemy, map_, CUR_ROUND)    # round 1
            first = friendly.job_assignments.get(u.uid)
            self.assertEqual(first, id(marker))
            assign_jobs(friendly, enemy, map_, CUR_ROUND + 1)  # round 2, unchanged
            self.assertEqual(friendly.job_assignments.get(u.uid), id(marker))
            # and the move-time decision is HOLD both times.
            dest, intent = _job_layer_move_intent(
                u, friendly, enemy, map_, None, CUR_ROUND + 1)
            self.assertEqual(intent, "CAPTURE")
        finally:
            del os.environ["SWEG_JOB_LAYER"]


class ZeroValueRouting(unittest.TestCase):
    """Correction pass (the pre-registered single fix): channels all <= 0 for an
    unassigned unit route via the value field's marker argmax — never a
    nearest-enemy march."""

    def test_g_out_of_range_gunline_stays_near_held_marker(self):
        """(g) An out-of-range Heavy gunline unit with zero-priced channels whose
        current position is near a held marker STAYS (routes to that marker via
        the value argmax) instead of advancing toward the enemy."""
        u = _Unit(_heavy_gunline(), (10.0, 10.0), uid=1)
        brute = _Unit(_melee_brute(), (50.0, 10.0), uid=99)   # 40" away
        friendly = _Army([u])
        enemy = _Army([brute], is_a=False)
        marker_a = _Obj(10.0, 10.0)               # the unit stands on it — held
        marker_b = _Obj(50.0, 10.0)               # the brute's marker — lethal
        map_ = _Map([marker_a, marker_b])
        proj = _threat_projectors(enemy)
        # Zero-priced channels: no cell within Move (+ no Advance exemption)
        # reaches the 24" gun; the melee-only brute projects no threat at 40".
        kill_v, _kd, _ki = _job_channel_kill(
            u, friendly, None, enemy.alive_units, None, SRR, proj)
        survive_v, _sd = _job_channel_survive(u, proj, None, SRR)
        self.assertEqual(kill_v, 0.0)
        self.assertEqual(survive_v, 0.0)
        dest, intent = _job_layer_move_intent(
            u, friendly, enemy, map_, None, CUR_ROUND)
        # Routed to the value argmax: the held marker it already stands on.
        self.assertEqual(intent, "CAPTURE")
        self.assertLessEqual(
            ((dest[0] - marker_a.x) ** 2 + (dest[1] - marker_a.y) ** 2) ** 0.5,
            marker_a.control_radius + 1e-9)
        # It does NOT advance toward the enemy (the pre-fix march was a full
        # Normal move at the brute; staying keeps the whole 40" separation
        # minus at most the marker's control radius).
        d_before = ((u.position[0] - brute.position[0]) ** 2
                    + (u.position[1] - brute.position[1]) ** 2) ** 0.5
        d_after = ((dest[0] - brute.position[0]) ** 2
                   + (dest[1] - brute.position[1]) ** 2) ** 0.5
        self.assertGreaterEqual(
            d_after, d_before - marker_a.control_radius - 1e-9)

    def test_h_melee_at_long_range_routes_to_marker_not_enemy(self):
        """(h) A melee unit at long range with zero-priced KILL routes toward a
        marker, not the nearest enemy."""
        u = _Unit(_melee_monster(), (5.0, 5.0), uid=1)
        prey = _Unit(_fragile_target(), (55.0, 5.0), uid=99)   # 50" — out of reach
        friendly = _Army([u])
        enemy = _Army([prey], is_a=False)
        marker = _Obj(20.0, 25.0)                 # off the enemy's axis
        map_ = _Map([marker])
        proj = _threat_projectors(enemy)
        kill_v, _kd, _ki = _job_channel_kill(
            u, friendly, None, enemy.alive_units, None, SRR, proj)
        survive_v, _sd = _job_channel_survive(u, proj, None, SRR)
        self.assertEqual(kill_v, 0.0)             # nothing killable this turn
        self.assertEqual(survive_v, 0.0)          # nothing threatens it either
        dest, intent = _job_layer_move_intent(
            u, friendly, enemy, map_, None, CUR_ROUND)
        # Routes to the marker (value argmax), not the nearest enemy.
        self.assertEqual(intent, "CAPTURE")
        self.assertLessEqual(
            ((dest[0] - marker.x) ** 2 + (dest[1] - marker.y) ** 2) ** 0.5,
            marker.control_radius + 1e-9)
        # The pre-fix march destination was a full Normal move straight at the
        # prey: (13, 5). The routed destination must not be on that heading.
        pre_fix_march = (13.0, 5.0)
        self.assertGreater(
            ((dest[0] - pre_fix_march[0]) ** 2
             + (dest[1] - pre_fix_march[1]) ** 2) ** 0.5,
            1.0)


class ExchangeRateReprice(unittest.TestCase):
    """docs/DECISION_LEDGER.md "EXCHANGE-RATE FIT RESULT (2026-07-11...)": the
    ASSERTED wounds-to-victory-points rate ((_VALUE_VP_PER_ROUND_REF * srr) /
    _TRADE_POINTS_REF, ~0.114-0.143 across the game) has been replaced by the
    MEASURED rate (_MEASURED_VP_PER_POINT = 0.015248, fitted from 18,480
    logged games). The KILL and SURVIVE channels both shrink by the SAME
    ~9.4x factor at round 1 (both route through _trade_vp_per_wound with the
    same scoring_rounds_remaining), so their relationship to EACH OTHER is
    unchanged (see the eight ChannelDerivation/AssignmentAndPersistence/
    ZeroValueRouting fixtures above, all still green) — but HOLD is priced
    from the marker's own real Take-and-Hold scoring rule (value_projection),
    which does NOT go through the exchange rate at all, so HOLD's size
    RELATIVE TO KILL/SURVIVE changes. This is the reprice's signature effect."""

    def test_i_modest_kill_near_uncontested_marker_now_derives_hold(self):
        """HAND-COMPUTATION (round 1, SRR=5, ModestKiller at (10,10), an
        uncontested marker 1.4" away at (11,11), ModestPrize 10" away at
        (20,10) — well within the ModestKiller's 12" gun range):

        KILL (exchange-rate-dependent — the arithmetic under test):
          ew = attacks(6) * hit(0.5)
               * wound_probability(str=5, toughness=4) = 2/3 (S5 > T4, not
                 >= 2T)
               * (1 - save_probability(save=4, ap=-1)) = (1 - 1/3) = 2/3
               * per_shot_damage(1.0)
             = 6 * 0.5 * (2/3) * (2/3) * 1.0 = 4/3 = 1.333333...
          points-per-wound of the ModestPrize = 300 / 2 = 150.0
          OLD (asserted, RETIRED — reconstructed here for illustration only,
              the formula no longer exists in the code):
              vp_per_wound_OLD = 150.0 * ((5.0 * 5) / 175.0) = 150.0 / 7
                               = 21.428571...
              kill_v_OLD = 1.333333... * 21.428571... = 28.571428...
          NEW (measured, shipped):
              vp_per_wound_NEW = 150.0 * 0.015248 = 2.2872
              kill_v_NEW = 1.333333... * 2.2872 = 3.0496

        RISK DISCOUNT on KILL (the consistency pass — the channel value is the
        raw offense times the SAME survival factor HOLD's value_projection
        applies, 1 - frac_at_risk at the chosen cell; stationary is the argmax
        cell here, the farthest candidate from the Prize hence least
        threatened):
          incoming threat at (10,10): the Prize's gun (1 shot * 0.5 hit *
          wound_probability(4,3)=2/3 * save-fail(save=5,ap=0)=2/3 * 1 dmg
          = 2/9) plus its melee reach (kill-potential 1*0.5*2/3*2/3 = 2/9,
          charge needed 10-6-1 = 3.0" -> P(2D6>=3) = 35/36):
              T = 2/9 + (2/9)(35/36) = 71/162 = 0.438271...
              frac_at_risk = T / wounds(5) = 71/810 = 0.087654...
              kill_v = 3.0496 * (739/810) = 2.782289382716049

        HOLD (exchange-rate-INDEPENDENT — value_projection's own real
        Take-and-Hold rule, unaffected by this reprice):
          marker_vp = vp_per_round(5.0) * srr(5) = 25.0; own OC 4 beats the
          Prize's OC 0 on an uncontested marker -> control = 1.0. The Prize's
          24" gun reaches the marker (9.06" away) and contributes a small
          threat field, so contestability is a hair under 1. Read directly
          from the production value_projection/_job_channel_hold (the
          threat-field arithmetic is untouched by this change and is not
          re-derived here): hold_v = 22.808641975308642.

        28.571 (kill_v_OLD, raw) > 22.809 (hold_v) > 2.782 (kill_v_NEW): the
        OLD asserted rate would have priced this MODEST kill ABOVE the
        marker's real value (unit derives KILL); the MEASURED rate prices it
        well BELOW (unit derives HOLD instead) — the reprice's named signature
        behaviour (docs/DECISION_LEDGER.md: "the HOLD share rises from ~2
        percent to material double digits")."""
        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            u = _Unit(_modest_killer(), (10.0, 10.0), uid=1)
            prize = _Unit(_modest_prize(), (20.0, 10.0), uid=99)   # 10" away
            friendly = _Army([u])
            enemy = _Army([prize], is_a=False)
            marker = _Obj(11.0, 11.0)             # 1.4" away, uncontested
            map_ = _Map([marker])
            proj = _threat_projectors(enemy)

            hold_v, _hobj = _job_channel_hold(
                u, u.profile.oc, [marker], {id(marker): 0}, {id(marker): 0},
                set(), proj, map_, SRR, True, ())
            kill_v, _kd, _ki = _job_channel_kill(
                u, friendly, None, enemy.alive_units, map_, SRR, proj)
            survive_v, _sd = _job_channel_survive(u, proj, map_, SRR)

            # Pin the hand-computed numbers above against the production code.
            # The RAW offense (pre-discount) is the reprice's own number; the
            # channel value carries the risk discount on top.
            raw_offense = value_offense(
                u, u.position, True, False, True, enemy.alive_units, map_, SRR)
            self.assertAlmostEqual(hold_v, 22.808641975308642, delta=1e-9)
            self.assertAlmostEqual(raw_offense, 3.0496, delta=1e-9)
            self.assertAlmostEqual(kill_v, 3.0496 * (739.0 / 810.0),
                                   delta=1e-9)

            # Reconstruct the OLD (retired) rate from the RAW offense — same
            # ew, same points-per-wound, only the multiplicative constant
            # differs — to show what the pre-reprice code would have priced
            # (the pre-reprice code was also risk-blind, so the raw value is
            # the honest reconstruction).
            kill_v_old_rate = raw_offense * ((5.0 * SRR) / 175.0) / 0.015248
            self.assertAlmostEqual(kill_v_old_rate, 28.571428571428573,
                                   delta=1e-6)

            # MEASURED rate (shipped): HOLD wins.
            self.assertGreater(hold_v, kill_v)
            self.assertGreater(hold_v, survive_v)
            # OLD rate (retired, reconstructed for illustration): KILL would
            # have out-priced HOLD — the exact defect the reprice fixes.
            self.assertGreater(kill_v_old_rate, hold_v)

            # End to end: the army-level assignment commits the unit to the
            # marker, and the move-time decision is CAPTURE (HOLD), not a
            # KILL-channel engage.
            assign_jobs(friendly, enemy, map_, CUR_ROUND)
            self.assertEqual(friendly.job_assignments.get(u.uid), id(marker))
            dest, intent = _job_layer_move_intent(
                u, friendly, enemy, map_, None, CUR_ROUND)
            self.assertEqual(intent, "CAPTURE")
        finally:
            del os.environ["SWEG_JOB_LAYER"]


class KillChannelRiskDiscount(unittest.TestCase):
    """The KILL channel's risk discount (consistency pass — docs/
    DECISION_LEDGER.md "JOB LAYER + MEASURED EXCHANGE RATE" failure entry):
    each candidate cell's offense is multiplied by the SAME survival factor
    HOLD's value_projection applies to its marker value,

        discounted(p) = offense(p) * (1 - min(1, T(p) / max(1, wounds))),

    so the cross-channel argmax compares like with like instead of a
    risk-discounted HOLD against risk-blind KILL. These two fixtures pin the
    discount's two signature behaviours: equal-offense cells rank by safety
    (j), and an all-lethal offense collapses the channel to zero so the
    routing falls elsewhere (k)."""

    def test_j_equal_offense_cells_rank_by_safety(self):
        """(j) Two candidate cells with EQUAL raw offense — one under heavy
        melee threat, one safe — the safe cell must win the KILL argmax.

        HAND-COMPUTATION (round 1, SRR=5). Flanker at (30,20), move 6, gun
        12". Identical InertPrey at (46,20) [uid 12, east] and (14,20)
        [uid 13, west], both 16" away — OUT of range standing still, IN range
        (10") from the Normal-move cell toward either: east cell (36,20),
        west cell (24,20). A GuardBrute [uid 11] at (50,20) guards the east
        prey; its T8 makes it worthless as a target for the S4 gun (wound
        fraction 1/6, the no-wasted-fire exclusion prices it at zero) so it
        contributes ONLY threat.

        RAW OFFENSE at either cell (identical by symmetry):
          ew = attacks(6) * hit(0.5) * wound_probability(4,4)=1/2
               * (1 - save_probability(4,0)) = 1/2 * dmg(1.0)
             = 6 * 0.5 * 0.5 * 0.5 = 0.75, capped at prey health 4 -> 0.75
          vp_per_wound = (100/4) * 0.015248 = 0.3812
          O = 0.75 * 0.3812 = 0.2859        (both cells, exactly)

        THREAT at the east cell (36,20): the brute at (50,20) is 14" away;
        charge needed = 14 - move(6) - engage(1.0) = 7.0 -> P(2D6>=7) = 21/36.
          melee kill-potential = 8 attacks * 0.5 hit
              * wound_probability(8,4) = 5/6
              * (1 - save_probability(4,-2)) = 5/6 * dmg 2
              = 4 * (5/6) * (5/6) * 2 = 50/9
          T = (50/9) * (21/36) = 175/54 = 3.240740...
          frac_at_risk = min(1, T / wounds(6)) = 175/324 = 0.540123...
          discounted east = 0.2859 * (149/324) = 0.131478...
        THREAT at the west cell (24,20): brute 26" away, charge needed
        19 > 12 -> unreachable -> T = 0 -> discounted west = 0.2859 (raw).

        PRE-FIX the east cell won on ITERATION ORDER (uid 11 brute's step
        cell (36,20) reaches raw 0.2859 first; the west cell's equal raw
        cannot strictly beat it) — the unit walked into the brute's charge
        reach for zero gain. The discount makes the safe cell strictly
        better: 0.2859 > 0.131478."""
        u = _Unit(_flanker(), (30.0, 20.0), uid=1)
        brute = _Unit(_guard_brute(), (50.0, 20.0), uid=11)
        prey_e = _Unit(_inert_prey(), (46.0, 20.0), uid=12)
        prey_w = _Unit(_inert_prey(), (14.0, 20.0), uid=13)
        friendly = _Army([u])
        enemy = _Army([brute, prey_e, prey_w], is_a=False)
        map_ = _Map([])
        proj = _threat_projectors(enemy)

        # The two cells' RAW offense is identical (pinned to the hand number).
        raw_e = value_offense(u, (36.0, 20.0), True, False, True,
                              enemy.alive_units, map_, SRR)
        raw_w = value_offense(u, (24.0, 20.0), True, False, True,
                              enemy.alive_units, map_, SRR)
        self.assertAlmostEqual(raw_e, 0.2859, delta=1e-9)
        self.assertAlmostEqual(raw_w, 0.2859, delta=1e-9)

        # Threat asymmetry (pinned): east cell under the brute's reach.
        t_e = _threat_field_at(u, proj, (36.0, 20.0), map_)
        t_w = _threat_field_at(u, proj, (24.0, 20.0), map_)
        self.assertAlmostEqual(t_e, 175.0 / 54.0, delta=1e-9)
        self.assertEqual(t_w, 0.0)

        # The channel picks the SAFE cell at its undiscounted value.
        kill_v, kill_dest, kill_intent = _job_channel_kill(
            u, friendly, None, enemy.alive_units, map_, SRR, proj)
        self.assertEqual(kill_dest, (24.0, 20.0))     # west (safe), not east
        self.assertEqual(kill_intent, "ENGAGE")
        self.assertAlmostEqual(kill_v, 0.2859, delta=1e-9)
        # ... and the east cell's discounted value is the hand number.
        self.assertAlmostEqual(raw_e * (149.0 / 324.0), 0.13147870370370368,
                               delta=1e-9)

        # End to end: the KILL channel wins the argmax (nothing threatens the
        # current cell, so SURVIVE prices zero) and the move goes west.
        dest, intent = _job_layer_move_intent(
            u, friendly, enemy, map_, None, CUR_ROUND)
        self.assertEqual(intent, "ENGAGE")
        self.assertEqual(dest, (24.0, 20.0))

    def test_k_all_lethal_offense_collapses_kill_to_zero(self):
        """(k) A kill-job unit whose EVERY offense cell is lethal (frac_at_risk
        == 1 everywhere it could fire from) must see its KILL value collapse
        to zero so the routing falls to another channel or the value fallback.

        HAND-COMPUTATION (round 1, SRR=5). GunlineHeavy at (10,20) (8 wounds,
        move 6, 24" Heavy gun). A Softie prey at (28,20) [18", in range] and a
        Sniper battery at (28,24) guarding it. The battery's incoming fire is

          12 shots * 0.667 hit * wound_probability(10,5) = 5/6 (S >= 2T)
          * (1 - save_probability(3,-3)) = 5/6 * dmg 3 = 16.675 expected
          wounds >= the unit's 8 -> frac_at_risk = 1 at EVERY cell within its
          reach (move 6 + range 24 = 30").

        Geometry check: the battery is 18.4" from the unit, 12.7" from the
        Normal cell toward the prey (16,20) — every kill candidate AND every
        SURVIVE retreat cell (max 18.4 + 6 = 24.4") sits inside the 30"
        reach, so frac_at_risk = 1 everywhere:
          KILL    = raw * (1 - 1) = 0.0 exactly, at every candidate
          SURVIVE = (frac_cur 1 - best_frac 1) * value = 0.0

        The RAW stationary offense the discount collapses (best single
        target = the battery itself: Heavy-bonus hit 2/3, wound_probability
        (6,5) = 2/3, save-fail(3,-1) = 1/2, dmg 2 -> 6*(2/3)*(2/3)*(1/2)*2
        = 8/3 wounds, times (150/6)*0.015248 = 0.3812/wound):
          raw = (8/3) * 0.3812 = 1.016533...

        Pre-fix the unit stood at its maximum-offense cell and traded 8
        wounds for one shooting phase; post-fix the zero-value routing sends
        it to the safe marker at (54,42) (31.6" from the battery, outside
        the 30" reach) through the value-field argmax."""
        u = _Unit(_heavy_gunline(), (10.0, 20.0), uid=1)
        prey = _Unit(_fragile_target(), (28.0, 20.0), uid=21)
        battery = _Unit(_long_range_gun(), (28.0, 24.0), uid=22)
        marker = _Obj(54.0, 42.0)                 # outside the battery's reach
        friendly = _Army([u])
        enemy = _Army([prey, battery], is_a=False)
        map_ = _Map([marker])
        proj = _threat_projectors(enemy)

        # The raw offense the discount collapses (pinned to the hand number).
        raw_stationary = value_offense(u, u.position, True, True, True,
                                       enemy.alive_units, map_, SRR)
        self.assertAlmostEqual(raw_stationary, (8.0 / 3.0) * 0.3812,
                               delta=1e-9)
        self.assertGreater(raw_stationary, 1.0)   # a real kill was available

        # KILL collapses to exactly zero; SURVIVE has no escape either.
        kill_v, kill_dest, _ki = _job_channel_kill(
            u, friendly, None, enemy.alive_units, map_, SRR, proj)
        survive_v, _sd = _job_channel_survive(u, proj, map_, SRR)
        self.assertEqual(kill_v, 0.0)
        self.assertEqual(survive_v, 0.0)

        # Zero-value routing wins the argmax: CAPTURE toward the safe marker,
        # never a stand-and-shoot in the lethal cell.
        dest, intent = _job_layer_move_intent(
            u, friendly, enemy, map_, None, CUR_ROUND)
        self.assertEqual(intent, "CAPTURE")
        self.assertLessEqual(
            ((dest[0] - marker.x) ** 2 + (dest[1] - marker.y) ** 2) ** 0.5,
            marker.control_radius + 1e-9)


class DenialAndReactive(unittest.TestCase):
    """SWEG_JOB_DENY (the fourth channel) and SWEG_HOLD_REACTIVE (committed-holder
    urgency + flipped-marker force-release). All numbers hand-computed to 1e-9."""

    def test_a_deny_ds_fraction_and_value_hand_computed(self):
        """(a) DENY_DS prices a candidate cell by the fraction of the enemy's
        currently-legal 3-inch landing grid its nine-inch exclusion disk removes,
        times the reserve-points factor.

        Synthetic grid: 7x7 all-legal cells at x,y in {2,5,8,11,14,17,20}
        (x0=2, step=3), total = 49 currently-legal cells; enemy reserves = 500
        points so factor = 500 * _MEASURED_VP_PER_POINT.

        A BACKFIELD-interior candidate at (11,11) has its full nine-inch disk on
        the board: the grid cells within 9 inches are those at index offset
        (di,dj) with (3di)^2+(3dj)^2 <= 81, i.e. di^2+dj^2 <= 9 — exactly 29
        cells (1 + 4 + 4 + 4 + 8 + 4 + 4). A MIDFIELD/corner candidate at (20,20)
        has three-quarters of its disk off-board; only 11 grid cells remain
        within nine inches. So:
            DENY_DS(11,11) = 29/49 * factor   (backfield denies more)
            DENY_DS(20,20) = 11/49 * factor
        """
        nx = ny = 7
        legal = [[True] * ny for _ in range(nx)]
        total = nx * ny                            # 49
        factor = 500.0 * _MEASURED_VP_PER_POINT
        ctx = (2.0, 2.0, 3.0, nx, ny, legal, total, factor)

        backfield = _deny_ds_value((11.0, 11.0), ctx)
        midfield = _deny_ds_value((20.0, 20.0), ctx)
        self.assertAlmostEqual(backfield, (29.0 / 49.0) * factor, delta=1e-9)
        self.assertAlmostEqual(midfield, (11.0 / 49.0) * factor, delta=1e-9)
        self.assertGreater(backfield, midfield)   # the canary fix: deny the backfield
        # A None context (self-extinguished) prices exactly zero.
        self.assertEqual(_deny_ds_value((11.0, 11.0), None), 0.0)

    def test_b_deny_ds_self_extinguishes_with_empty_reserves(self):
        """(b) The DENY_DS term self-extinguishes when the enemy has no reserves:
        the precompute returns None and the priced value is exactly 0. With 500
        points pending it returns a real grid with the exact reserve factor and a
        positive denial for a unit standing on the board."""
        mover = _Unit(_cheap_holder(), (10.0, 10.0), uid=1)
        friendly = _Army([mover])
        enemy = _Army([_Unit(_fragile_target(), (30.0, 30.0), uid=99)],
                      is_a=False)
        enemy.name = "Enemy"
        map_ = _Map([], width=44.0, height=44.0)

        r1 = _Unit(_reserve_body(), (0.0, 0.0), uid=201)   # 250 points
        r2 = _Unit(_reserve_body(), (0.0, 0.0), uid=202)   # 250 points -> 500
        battle = _Battle(friendly, enemy, {"Enemy": [r1, r2]})
        ctx = _job_deny_ds_precompute(mover, friendly, enemy, battle, map_)
        self.assertIsNotNone(ctx)
        self.assertAlmostEqual(ctx[7], 500.0 * _MEASURED_VP_PER_POINT, delta=1e-9)
        self.assertGreater(_deny_ds_value(mover.position, ctx), 0.0)
        # And the channel as a whole prices a positive denial from a backfield body.
        dv, _dd, _di = _job_channel_deny(
            mover, friendly, enemy, battle, [], {}, {}, set(), map_, SRR)
        self.assertGreater(dv, 0.0)

        # Empty reserves: the term self-extinguishes.
        battle_empty = _Battle(friendly, enemy, {"Enemy": []})
        ctx0 = _job_deny_ds_precompute(mover, friendly, enemy, battle_empty, map_)
        self.assertIsNone(ctx0)
        self.assertEqual(_deny_ds_value(mover.position, ctx0), 0.0)
        dv0, _d0, _i0 = _job_channel_deny(
            mover, friendly, enemy, battle_empty, [], {}, {}, set(), map_, SRR)
        self.assertEqual(dv0, 0.0)

    def test_c_deny_marker_flip_prices_full_denial(self):
        """(c) DENY_MARKER prices standing within contest range of an ENEMY-HELD
        marker by the enemy's score DROP. Enemy objective control 5, my other
        units 0, my mover OC 5: standing on the marker flips held (5 > 0) to
        contested (5 is NOT > 5, the strictly-greater scorer denies the tick), so
        the denial is the full obj.vp_per_round * srr = 5 * 5 = 25. Not standing
        within range prices 0; a bracket I cannot change (enemy OC 20) prices 0."""
        marker = _Obj(30.0, 22.0)                  # vp_per_round default 5
        own_oc = 5
        our_oc = {id(marker): 0}
        their_oc = {id(marker): 5}                 # enemy holds (5 > 0)

        v_on = _deny_marker_value((30.0, 22.0), own_oc, [marker], our_oc,
                                  their_oc, set(), SRR)
        self.assertAlmostEqual(v_on, marker.vp_per_round * SRR, delta=1e-9)
        self.assertAlmostEqual(v_on, 25.0, delta=1e-9)

        v_far = _deny_marker_value((100.0, 100.0), own_oc, [marker], our_oc,
                                   their_oc, set(), SRR)
        self.assertEqual(v_far, 0.0)               # not touching it -> 0

        their_big = {id(marker): 20}
        v_nochange = _deny_marker_value((30.0, 22.0), own_oc, [marker], our_oc,
                                        their_big, set(), SRR)
        self.assertEqual(v_nochange, 0.0)          # cannot change the bracket -> 0

        # A zero-OC unit cannot contest at all.
        self.assertEqual(
            _deny_marker_value((30.0, 22.0), 0, [marker], our_oc, their_oc,
                               set(), SRR),
            0.0)

    def test_d_hold_reactive_urgency_bonus_exact(self):
        """(d) The SWEG_HOLD_REACTIVE urgency bonus for a committed holder on a
        marker under threat t equal to half its health is exactly
        obj.vp_per_round * srr * 0.5. Health 12, t = 6 -> min(1, 6/12) = 0.5, so
        bonus = 5 * 5 * 0.5 = 12.5. Off, it is exactly 0.0 (byte-identical)."""
        marker = _Obj(30.0, 22.0)                  # vp_per_round 5
        unit = _Unit(_expensive_fragile(), (30.0, 22.0),
                     current_health=12.0, uid=1)   # health 12
        t = 6.0                                     # half of 12

        os.environ["SWEG_HOLD_REACTIVE"] = "1"
        try:
            bonus = _job_hold_urgency_bonus(marker, t, unit, SRR)
        finally:
            del os.environ["SWEG_HOLD_REACTIVE"]
        self.assertAlmostEqual(bonus, marker.vp_per_round * SRR * 0.5, delta=1e-9)
        self.assertAlmostEqual(bonus, 12.5, delta=1e-9)

        # Off -> exactly 0.0 (the SWEG_JOB_LAYER-only path is byte-identical).
        self.assertEqual(_job_hold_urgency_bonus(marker, t, unit, SRR), 0.0)

        # It threads value_projection's T through _job_hold_value_and_threat_at,
        # so V is unchanged and T is the field the bonus reads.
        proj = _threat_projectors(_Army([], is_a=False))
        v, t_out = _job_hold_value_and_threat_at(
            unit, marker, own_is_a=True, prospective_our_oc=5, their_oc=0,
            projectors=proj, map_=_Map([marker]), srr=SRR, chosen=())
        self.assertGreaterEqual(v, 0.0)
        self.assertEqual(t_out, 0.0)               # no projectors -> no threat

    def test_e_flip_release_re_tasks_the_flipped_marker(self):
        """(e) SWEG_HOLD_REACTIVE force-releases a committed holder whose marker
        has flipped to the enemy, so the greedy pass re-tasks the marker from
        scratch — here handing it to a stronger holder that can actually reclaim
        it — rather than the weak holder clinging on a contestability-discounted
        HOLD that still dominates its KILL/SURVIVE.

        Board: marker M with an enemy objective-control block of 8. Weak holder
        u1 (OC 5) sits on M and was committed to it last turn while it was ours
        (believed_held = True); it no longer holds it (5 <= 8 = flipped). Stronger
        u2 (OC 10) is off M but reachable. With the gate ON, u1 is released and
        the greedy pass assigns u2 (5+10 = 15 > 8, a real reclaim); u1 is then
        pile-on-skipped. With the gate OFF, u1 persists (its HOLD 25*0.2 = 5
        beats its ~0 KILL/SURVIVE) and clings to the lost marker."""
        def _build():
            u1 = _Unit(_cheap_holder(), (32.0, 22.0), uid=1)     # OC 5, on M (dist 2)
            u2 = _Unit(_strong_holder(), (38.0, 22.0), uid=2)    # OC 10, off M, reachable
            blocker = _Unit(_oc_blocker(), (30.0, 22.0), uid=99)  # enemy OC 8 on M
            friendly = _Army([u1, u2])
            enemy = _Army([blocker], is_a=False)
            marker = _Obj(30.0, 22.0)
            map_ = _Map([marker])
            # Simulate last turn's state: u1 committed to M and believed it held it.
            friendly.job_assignments = {u1.uid: id(marker)}
            friendly.job_believed_held = {u1.uid: True}
            return u1, u2, marker, friendly, enemy, map_

        # Gate ON: flip-release + re-task to the stronger holder.
        os.environ["SWEG_JOB_LAYER"] = "1"
        os.environ["SWEG_HOLD_REACTIVE"] = "1"
        try:
            u1, u2, marker, friendly, enemy, map_ = _build()
            assign_jobs(friendly, enemy, map_, CUR_ROUND + 1)
            self.assertNotIn(u1.uid, friendly.job_assignments)      # released
            self.assertEqual(friendly.job_assignments.get(u2.uid), id(marker))
        finally:
            del os.environ["SWEG_HOLD_REACTIVE"]
            del os.environ["SWEG_JOB_LAYER"]

        # Gate OFF: the weak holder clings to the flipped marker (persistence).
        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            u1, u2, marker, friendly, enemy, map_ = _build()
            assign_jobs(friendly, enemy, map_, CUR_ROUND + 1)
            self.assertEqual(friendly.job_assignments.get(u1.uid), id(marker))
        finally:
            del os.environ["SWEG_JOB_LAYER"]


if __name__ == "__main__":
    unittest.main()
