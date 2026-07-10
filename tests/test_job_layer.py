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
    _job_channel_hold,
    _job_channel_kill,
    _job_channel_survive,
    _job_layer_move_intent,
    _threat_projectors,
    _value_scoring_rounds_remaining,
    assign_jobs,
    classify,
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
                                           None, SRR)
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
                                           None, SRR)
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
        kill_v, kdest, kintent = _job_channel_kill(
            u, friendly, None, enemy.alive_units, None, SRR)
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


if __name__ == "__main__":
    unittest.main()
