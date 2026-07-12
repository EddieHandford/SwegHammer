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
    _job_marker_transit_net,
    _job_projected_contest_oc,
    _job_squad_health,
    _job_squad_value_vp,
    _job_squad_view,
    _job_threat_precompute,
    _job_threat_scan,
    _job_transit_survival,
    _job_value_fallback_net,
    _threat_field_at,
    _threat_projectors,
    _value_scoring_rounds_remaining,
    assign_jobs,
    classify,
    value_net_score,
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

    def has_line_of_sight(self, attacker, target,
                          attacker_keywords=None, target_keywords=None):
        return True     # open synthetic board — no blocking terrain


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
        SURVIVE, and (in range) it stays put to shoot.

        Iteration-5 update: the marker option is now a PEER for unassigned
        units, and the original bare far marker (uncontested, zero threat)
        priced net 25 — beating the kill. A Sniper battery guards the far
        marker so its job-path net goes NEGATIVE (the battery's 13.34 expected
        wounds against the lone six-wound Eradicator saturate frac to 1, so
        v = 0 and the net is minus its own value at stake), preserving this
        fixture's original intent: with no WORTHWHILE marker, the in-range
        kill wins the peer argmax and the unit stays to shoot. The battery is
        270 inches from the Eradicator — outside every kill/survive
        interaction."""
        u = _Unit(_eradicator(), (10.0, 10.0), uid=1)
        target = _Unit(_juicy_tank(), (22.0, 10.0), uid=99)   # 12" -> in 18" range
        battery = _Unit(_long_range_gun(), (200.0, 206.0), uid=98)  # marker guard
        friendly = _Army([u])
        enemy = _Army([target, battery], is_a=False)
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

    def test_f_hold_tie_and_deny_repricing_exact(self):
        """(f, iteration-3 fix 1) The HOLD price for a marker where my presence
        stops the enemy's scoring adds the denial obj.vp_per_round*srr*(1-frac)
        on top of value_projection's own-scoring bracket.

        HAND COMPUTATION (no projectors -> t=0, frac=0; srr=5; vp_per_round=5):
          TIE case: their_oc 5, our_other 0, own_oc 5 -> prospective 5.
            value_projection: control=0.5 (tie), v = 25*0.5*1.0 = 12.5.
            Denial bracket: 5 > 0 (they held) and 5 <= 5 (stopped) -> +25*(1-0)
            = +25.  Total = 37.5 exactly.
          WIN case: their_oc 3, our_other 0, own_oc 5 -> prospective 5.
            control=1.0, v = 25.  Denial: 3 > 0 and 3 <= 5 -> +25.  Total = 50
            (the full swing: our +25 gain and their -25 loss).
          CANNOT-FLIP case: their_oc 20 -> 20 > 5 after me too -> no denial;
            control=0.2 -> v = 5 exactly.
          Gate OFF: the tie case prices 12.5 exactly (byte-identical arm).
          own_oc None (legacy signature): 12.5 even with the gate on."""
        u = _Unit(_cheap_holder(), (30.0, 22.0), uid=1)   # OC 5, on the marker
        marker = _Obj(30.0, 22.0)
        map_ = _Map([marker])
        proj = _threat_projectors(_Army([], is_a=False))  # no threat -> frac 0

        os.environ["SWEG_JOB_DENY"] = "1"
        try:
            v_tie, _t = _job_hold_value_and_threat_at(
                u, marker, 5, 5, proj, map_, SRR, True, (), own_oc=5)
            self.assertAlmostEqual(v_tie, 12.5 + 25.0, delta=1e-9)
            v_win, _t = _job_hold_value_and_threat_at(
                u, marker, 5, 3, proj, map_, SRR, True, (), own_oc=5)
            self.assertAlmostEqual(v_win, 25.0 + 25.0, delta=1e-9)
            v_cant, _t = _job_hold_value_and_threat_at(
                u, marker, 5, 20, proj, map_, SRR, True, (), own_oc=5)
            self.assertAlmostEqual(v_cant, 5.0, delta=1e-9)
            v_legacy, _t = _job_hold_value_and_threat_at(
                u, marker, 5, 5, proj, map_, SRR, True, ())   # own_oc omitted
            self.assertAlmostEqual(v_legacy, 12.5, delta=1e-9)
        finally:
            del os.environ["SWEG_JOB_DENY"]

        # Gate off: no denial term even with own_oc supplied.
        v_off, _t = _job_hold_value_and_threat_at(
            u, marker, 5, 5, proj, map_, SRR, True, (), own_oc=5)
        self.assertAlmostEqual(v_off, 12.5, delta=1e-9)

    def test_g_value_fallback_spreads_across_markers(self):
        """(g, iteration-3 fix 2; updated by the iteration-5 promotion) Two
        zero-channel units whose marker argmax agrees on the same best marker
        SPREAD: the first claims marker A (its effective objective control 5
        exceeds the enemy's 0 there — sufficiently claimed), the second is
        filtered to the next-best marker B. Since iteration 5 the spread
        claims are job-path standard, so the dedup applies with or without
        SWEG_JOB_DENY (both cases below assert the spread).

        Geometry (all channels priced zero): markers ~20 inches away — beyond
        the move+6 hold/deny reach and the 12-inch gun (after a 6-inch move,
        14 inches to the nearest enemy: out of range and out of the 2D6+1.5
        melee reach), the blocker projects no threat (zero attacks), the far
        enemy is at 200 inches, and there are no reserves. Fallback nets:
        A uncontested = 25 exactly; B enemy-blocked (their 8 > prospective 5)
        = 0.2 x 25 = 5 exactly. Both positive, A strictly best."""
        def _build():
            u1 = _Unit(_cheap_holder(), (10.0, 10.0), uid=1)
            u2 = _Unit(_cheap_holder(), (10.0, 14.0), uid=2)
            blocker = _Unit(_oc_blocker(), (30.0, 30.0), uid=98)  # on B, inert
            far = _Unit(_fragile_target(), (200.0, 200.0), uid=99)
            friendly = _Army([u1, u2])
            enemy = _Army([blocker, far], is_a=False)
            mk_a = _Obj(30.0, 10.0)               # uncontested, net 25
            mk_b = _Obj(30.0, 30.0)               # blocked (oc 8), net 5
            map_ = _Map([mk_a, mk_b])
            return u1, u2, mk_a, mk_b, friendly, enemy, map_

        def _near(dest, mk):
            return (((dest[0] - mk.x) ** 2 + (dest[1] - mk.y) ** 2) ** 0.5
                    <= mk.control_radius + 1e-9)

        # Gate ON: u1 claims A; u2 is filtered to B (next-best).
        os.environ["SWEG_JOB_LAYER"] = "1"
        os.environ["SWEG_JOB_DENY"] = "1"
        try:
            u1, u2, mk_a, mk_b, friendly, enemy, map_ = _build()
            d1, i1 = _job_layer_move_intent(u1, friendly, enemy, map_, None, 1)
            d2, i2 = _job_layer_move_intent(u2, friendly, enemy, map_, None, 1)
            self.assertEqual(i1, "CAPTURE")
            self.assertEqual(i2, "CAPTURE")
            self.assertTrue(_near(d1, mk_a))
            self.assertTrue(_near(d2, mk_b))       # spread, not pile
            self.assertEqual(friendly.job_value_claims[id(mk_a)], 5)
            self.assertEqual(friendly.job_value_claims[id(mk_b)], 5)
        finally:
            del os.environ["SWEG_JOB_DENY"]
            del os.environ["SWEG_JOB_LAYER"]

        # JOB_LAYER only (no SWEG_JOB_DENY): since the iteration-5
        # marker-as-peer routing promoted the spread claims to job-path
        # standard, the dedup applies on EVERY job arm — both units spread
        # here too (in iteration 3 this case still piled onto A).
        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            u1, u2, mk_a, mk_b, friendly, enemy, map_ = _build()
            d1, _i1 = _job_layer_move_intent(u1, friendly, enemy, map_, None, 1)
            d2, _i2 = _job_layer_move_intent(u2, friendly, enemy, map_, None, 1)
            self.assertTrue(_near(d1, mk_a))
            self.assertTrue(_near(d2, mk_b))       # spread on the plain job arm
        finally:
            del os.environ["SWEG_JOB_LAYER"]


def _one_wound_body():
    """A one-wound, six-point Guard-infantry-like body — the profile whose
    per-model frac_at_risk always saturated to certain death (the iteration-4
    root defect)."""
    return UnitProfile(
        name="OneWound", health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3, move=6.0, oc=2,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        points_override=6,
    )


def _light_gun():
    """A shooter whose expected wounds onto _one_wound_body are EXACTLY 2.0:
    8 attacks x 0.5 hit x wound_probability(3,3)=0.5 x (1 -
    save_probability(5,-2)=0) x damage 1 = 2.0. No melee (melee_attacks 0),
    so the threat field at the marker is the ranged term alone."""
    return UnitProfile(
        name="LightGun", health=4, damage=1, hit_probability=0.5,
        ap=-2, save=4, strength=3, toughness=4, move=6.0, oc=1,
        attacks=8, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        points_override=50,
    )


class SquadSurvivalPricing(unittest.TestCase):
    """Iteration-4 root fix: the job path prices frac_at_risk against the
    SQUAD's pooled health (and the squad's points at stake), not one model's.
    All numbers hand-computed to 1e-9."""

    def _board(self, squad_size):
        """`squad_size` one-wound bodies sharing squad_id 7 on the marker at
        (30,22), a LightGun 20 inches away (within its move 6 + range 24
        reach), no terrain. T at the marker = 2.0 exactly."""
        friendly = _Army([])
        members = []
        for i in range(squad_size):
            u = _Unit(_one_wound_body(), (30.0, 22.0), uid=10 + i)
            u.squad_id = 7
            u.army_ref = friendly
            members.append(u)
        friendly.units = list(members)
        gun = _Unit(_light_gun(), (30.0, 42.0), uid=99)
        enemy = _Army([gun], is_a=False)
        marker = _Obj(30.0, 22.0)
        map_ = _Map([marker])
        proj = _threat_projectors(enemy)
        return members, marker, map_, proj

    def test_h_squad_contestability_exact(self):
        """(h) HAND COMPUTATION (srr=5, vp_per_round=5, T=2.0, our 20 vs
        their 0 -> control 1.0):

          SQUAD of 10 (pooled health 10): frac = 2.0/10 = 0.2,
            contestability 0.8 -> V = 25 x 1.0 x 0.8 = 20.0 exactly.
            The 330-point-equivalent marker trade is finally visible.
          ONE-MODEL squad (the real lone-model convention, pooled health 1):
            frac = min(1, 2.0/1) = 1 -> V = 0.0 exactly — identical to the
            old per-model behaviour (solo unchanged).
          Hand-built unit (no army back-reference, defensive default):
            V = 0.0 exactly, same as before."""
        members, marker, map_, proj = self._board(10)
        self.assertAlmostEqual(_job_squad_health(members[0]), 10.0, delta=1e-9)
        v, t = _job_hold_value_and_threat_at(
            members[0], marker, 20, 0, proj, map_, SRR, True, ())
        self.assertAlmostEqual(t, 2.0, delta=1e-9)
        self.assertAlmostEqual(v, 20.0, delta=1e-9)

        solo_members, marker_s, map_s, proj_s = self._board(1)
        self.assertAlmostEqual(_job_squad_health(solo_members[0]), 1.0,
                               delta=1e-9)
        v_solo, _t = _job_hold_value_and_threat_at(
            solo_members[0], marker_s, 20, 0, proj_s, map_s, SRR, True, ())
        self.assertAlmostEqual(v_solo, 0.0, delta=1e-9)   # old behaviour

        bare = _Unit(_one_wound_body(), (30.0, 22.0), uid=50)  # no refs
        v_bare, _t = _job_hold_value_and_threat_at(
            bare, marker_s, 20, 0, proj_s, map_s, SRR, True, ())
        self.assertAlmostEqual(v_bare, 0.0, delta=1e-9)   # defensive default

    def test_i_fallback_net_measured_dual_exact(self):
        """(i) The job path's fallback net prices the squad's MEASURED points
        at stake, not the flat twenty-five-victory-point dual:

          squad_vp = 10 x 6 points x _MEASURED_VP_PER_POINT = 0.91488
          net = V - squad_vp x frac = 20.0 - 0.91488 x 0.2 = 19.817024

        while the untouched SWEG_VALUE_MOVE consumer (value_net_score on the
        raw per-model unit) still prices the same marker at
        0 - 25 x 1.0 = -25.0 — the ~250x exposure overprice the instrument
        measured, preserved on its own path (scope guard)."""
        members, marker, map_, proj = self._board(10)
        view = _job_squad_view(members[0])
        squad_vp = _job_squad_value_vp(members[0], SRR)
        self.assertAlmostEqual(squad_vp, 60.0 * _MEASURED_VP_PER_POINT,
                               delta=1e-9)
        net = _job_value_fallback_net(
            view, squad_vp, marker, 20, 0, proj, map_, SRR, True, ())
        self.assertAlmostEqual(
            net, 20.0 - 60.0 * _MEASURED_VP_PER_POINT * 0.2, delta=1e-9)

        old_net = value_net_score(
            members[0], marker, 20, 0, proj, map_, SRR, True, ())
        self.assertAlmostEqual(old_net, -25.0, delta=1e-9)  # shared path intact


def _pistol_body():
    """A ranged-only one-wound enemy for the marker-peer fixtures: one attack
    at 0.5 hit, S3 AP0 D1, 12-inch range, NO melee — so its threat field is
    the ranged term alone (a clean hand number: expected wounds onto a T3/5+
    body = 1 x 0.5 x wound_probability(3,3)=0.5 x (1 - save_probability(5,0)
    = 1/3) x 1 = 1/6 exactly, everywhere within its move 6 + range 12 = 18
    reach)."""
    return UnitProfile(
        name="PistolBody", health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3, move=6.0, oc=2,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        points_override=6,
    )


class MarkerPeerRouting(unittest.TestCase):
    """Iteration-5 marker-as-peer routing (owner-sanctioned under the
    canary-loop registration): for an UNASSIGNED unit the argmax is
    max(KILL, SURVIVE, DENY, MARKER). These pin the two brief-mandated cases —
    the instrument shape (micro-positive channels lose to a double-digit
    marker net) and the claimed-marker next-best/micro routing. All numbers
    hand-computed to 1e-9."""

    def _board(self, with_second_marker=False):
        """Ten one-wound bodies (squad 7) at (10,22); a PistolBody enemy at
        (20,22) — 10 inches, inside the squad's 12-inch guns (a REAL positive
        KILL) and projecting T = 1/6 onto every cell in play (my position,
        every retreat ring cell, and both markers are within its 18-inch
        reach, so SURVIVE prices exactly 0). Marker M1 at (30,22) is 20 inches
        away — APPROACHABLE, not reachable this turn (move 6 + 6 advance = 12
        < 20), exercising the no-reach-filter rule. Optional M2 at (30,34)
        carries an inert OC-8 blocker (enemy-held -> 0.2 bracket)."""
        friendly = _Army([])
        members = []
        for i in range(10):
            u = _Unit(_one_wound_body(), (10.0, 22.0), uid=10 + i)
            u.squad_id = 7
            u.army_ref = friendly
            members.append(u)
        friendly.units = list(members)
        pistol = _Unit(_pistol_body(), (20.0, 22.0), uid=99)
        enemies = [pistol]
        mk1 = _Obj(30.0, 22.0)
        objs = [mk1]
        mk2 = None
        if with_second_marker:
            mk2 = _Obj(30.0, 34.0)
            blocker = _Unit(_oc_blocker(), (30.0, 34.0), uid=98)
            enemies.append(blocker)
            objs.append(mk2)
        enemy = _Army(enemies, is_a=False)
        map_ = _Map(objs)
        return members, mk1, mk2, friendly, enemy, map_

    def test_j_marker_peer_beats_micro_channels(self):
        """(h-new) The instrument case's shape, hand-pinned: an unassigned
        unit with a small-but-POSITIVE KILL, SURVIVE exactly 0, DENY 0, and a
        marker netting in the double digits must choose the MARKER — before
        iteration 5 the positive KILL blocked the marker route entirely (the
        fallback required every channel <= 0).

        HAND COMPUTATION (srr=5; squad health 10; squad value
        60 x _MEASURED_VP_PER_POINT = 0.91488):
          KILL: best target = the PistolBody, expected wounds 1/6 (in the
            12-inch gun at 10 inches; own melee 1/6 x reach-probability never
            exceeds it), capped by its 1 wound -> 1/6; times its value per
            wound 6 x rate; risk discount at the firing cell
            (1 - (1/6)/10):
              kill = (1/6) x 6 x rate x (1 - 1/60) = 0.0904 x 59/60 ~ 0.0150
          SURVIVE: T = 1/6 at the current cell AND at every retreat ring cell
            (all within the pistol's 18-inch reach) -> delta-frac 0 -> 0.0.
          DENY: no reserves, no marker within the deny reach -> 0.0.
          MARKER M1: T at the centre = 1/6 -> frac = 1/60 ->
              v   = 25 x 1.0 x (59/60) = 24.5833...
              net = v - 0.91488 x (1/60) = 24.5680...
        The peer argmax takes M1 (CAPTURE toward it), and the squad claims it
        with its whole effective objective control (10 x 2 = 20)."""
        members, mk1, _mk2, friendly, enemy, map_ = self._board()
        u0 = members[0]
        proj = _threat_projectors(enemy)

        rate = _MEASURED_VP_PER_POINT
        expected_kill = ((1.0 / 6.0) * (6.0 * rate)) * (1.0 - (1.0 / 6.0) / 10.0)
        kill_v, _kd, _ki = _job_channel_kill(
            u0, friendly, None, enemy.alive_units, map_, SRR, proj)
        self.assertAlmostEqual(kill_v, expected_kill, delta=1e-9)
        self.assertGreater(kill_v, 0.0)           # a REAL positive micro-channel

        survive_v, _sd = _job_channel_survive(u0, proj, map_, SRR)
        self.assertEqual(survive_v, 0.0)

        expected_net = (25.0 * (1.0 - (1.0 / 6.0) / 10.0)
                        - (60.0 * rate) * ((1.0 / 6.0) / 10.0))
        net = _job_value_fallback_net(
            _job_squad_view(u0), _job_squad_value_vp(u0, SRR), mk1, 2, 0,
            proj, map_, SRR, True, ())
        self.assertAlmostEqual(net, expected_net, delta=1e-9)

        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            dest, intent = _job_layer_move_intent(
                u0, friendly, enemy, map_, None, CUR_ROUND)
        finally:
            del os.environ["SWEG_JOB_LAYER"]
        self.assertEqual(intent, "CAPTURE")       # marker beats the positive KILL
        self.assertLessEqual(
            ((dest[0] - mk1.x) ** 2 + (dest[1] - mk1.y) ** 2) ** 0.5,
            mk1.control_radius + 1e-9)
        self.assertEqual(friendly.job_value_claims[id(mk1)], 20)

    def test_k_marker_peer_claimed_next_best_then_micro(self):
        """(i-new) With the best marker already claimed by another squad, the
        unit takes its NEXT-BEST marker; with EVERY marker claimed, it takes
        its best micro-channel (KILL here — no markers remain).

        HAND COMPUTATION: M2 is enemy-held (blocker objective control 8 >
        prospective 2 -> 0.2 bracket) and inside the pistol's reach:
            v(M2) = 25 x 0.2 x (59/60) = 4.9167 - dual 0.91488/60
            net(M2) = 4.9014... — still far above the 0.0150 kill.
        M1 claimed by "another squad" (claims 20 > enemy effective 0) -> the
        unit is filtered to M2. Then M2 claimed too (20 > blocker's 8) -> no
        markers remain and the positive KILL wins: the unit stays at its own
        cell to shoot (REPOSITION)."""
        members, mk1, mk2, friendly, enemy, map_ = self._board(
            with_second_marker=True)
        u0 = members[0]
        proj = _threat_projectors(enemy)

        rate = _MEASURED_VP_PER_POINT
        expected_net2 = (25.0 * 0.2 * (1.0 - (1.0 / 6.0) / 10.0)
                         - (60.0 * rate) * ((1.0 / 6.0) / 10.0))
        net2 = _job_value_fallback_net(
            _job_squad_view(u0), _job_squad_value_vp(u0, SRR), mk2, 2, 8,
            proj, map_, SRR, True, ())
        self.assertAlmostEqual(net2, expected_net2, delta=1e-9)

        # M1 claimed by another squad -> next-best M2.
        friendly.job_value_claims = {id(mk1): 20}
        friendly.job_value_squad_pick = {}
        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            dest, intent = _job_layer_move_intent(
                u0, friendly, enemy, map_, None, CUR_ROUND)
            self.assertEqual(intent, "CAPTURE")
            self.assertLessEqual(
                ((dest[0] - mk2.x) ** 2 + (dest[1] - mk2.y) ** 2) ** 0.5,
                mk2.control_radius + 1e-9)

            # EVERY marker claimed -> the positive micro-channel (KILL) wins.
            friendly.job_value_claims = {id(mk1): 20, id(mk2): 20}
            friendly.job_value_squad_pick = {}
            dest, intent = _job_layer_move_intent(
                u0, friendly, enemy, map_, None, CUR_ROUND)
            self.assertEqual(intent, "REPOSITION")
            self.assertEqual(dest, u0.position)   # stays to shoot
        finally:
            del os.environ["SWEG_JOB_LAYER"]


def _mine_body():
    """A short-range lethal blocker for the lethal-waypoint fixture: sixty
    attacks at 0.5 hit, S3 AP0 D1, THREE-inch range, move 0, no melee. Onto a
    T3/5+ one-wound body its expected wounds are 60 x 0.5 x 0.5 x (2/3) x 1 =
    10.0 exactly — the whole ten-model squad pool. The threat projector
    floors its move at six inches, so its projected reach is 6 + 3 = 9 inches
    — the fixture places it 8 inches from waypoint one (covered), 10 from
    waypoint two and 12 from the destination (both uncovered)."""
    return UnitProfile(
        name="MineBody", health=4, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=3, toughness=4, move=0.0, oc=1,
        attacks=60, weapon_damage_per_shot=1.0, range_inches=3,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        points_override=50,
    )


class TemporalMarkerPricing(unittest.TestCase):
    """Iteration-6 temporal pricing of the marker peer: the arrival-delay
    discount (vp x max(0, srr - turns), the real scoring rule applied to the
    itinerary) and the approach-exposure survival product over the transit
    waypoints. All numbers hand-computed to 1e-9."""

    def _board(self, with_mine=False):
        """Ten one-wound bodies (squad 7, pooled health 10) at (10,22); a
        PistolBody at (20,22) projecting T = 1/6 everywhere within its
        18-inch reach (both waypoints and the destination); the marker at
        (25,22) is 15 inches away -> turns = ceil(15/6) = 3, i.e. TWO transit
        waypoints at (16,22) and (22,22). Optional MineBody at (16,30), eight
        inches above waypoint one: T = 10.0 exactly there (the whole squad
        pool, inside its 9-inch projected reach), unreachable at waypoint two
        (10 inches) and the destination (12 inches)."""
        friendly = _Army([])
        members = []
        for i in range(10):
            u = _Unit(_one_wound_body(), (10.0, 22.0), uid=10 + i)
            u.squad_id = 7
            u.army_ref = friendly
            members.append(u)
        friendly.units = list(members)
        enemies = [_Unit(_pistol_body(), (20.0, 22.0), uid=99)]
        if with_mine:
            enemies.append(_Unit(_mine_body(), (16.0, 30.0), uid=98))
        enemy = _Army(enemies, is_a=False)
        marker = _Obj(25.0, 22.0)
        map_ = _Map([marker])
        return members, marker, friendly, enemy, map_

    def test_l_transit_discount_and_survival_exact(self):
        """(j-new) A marker three move-turns away at srr=4 prices
        vp x max(0, 4 - 3) = vp x 1, times the two-waypoint survival product —
        NOT vp x 4.

        HAND COMPUTATION (squad pool 10; T = 1/6 at both waypoints and the
        destination; prospective 2 vs their 0 -> control 1.0):
          survival: frac_1 = (1/6)/10 = 1/60; health_2 = 10 - 1/6 = 59/6;
                    frac_2 = (1/6)/(59/6) = 1/59;
                    survival = (59/60) x (58/59) = 58/60 = 29/30.
          net(srr_eff=1) = 5 x 1 x 1.0 x (59/60) - (60 x rate) x (1/60)
          temporal net  = net x 29/30
        and the UNdiscounted srr=4 price (5 x 4 x (59/60) - dual) is more than
        four times larger — the discount is the arithmetic under test."""
        members, marker, friendly, enemy, map_ = self._board()
        u0 = members[0]
        proj = _threat_projectors(enemy)
        srr4 = _value_scoring_rounds_remaining(2)
        self.assertEqual(srr4, 4)
        rows = _job_threat_precompute(u0, proj)

        surv = _job_transit_survival(
            u0, (marker.x, marker.y), 3, map_, rows, None, 10.0)
        self.assertAlmostEqual(surv, 29.0 / 30.0, delta=1e-9)

        rate = _MEASURED_VP_PER_POINT
        expected_net1 = (5.0 * 1.0 * (1.0 - (1.0 / 6.0) / 10.0)
                         - (60.0 * rate) * ((1.0 / 6.0) / 10.0))
        expected = expected_net1 * (29.0 / 30.0)
        got = _job_marker_transit_net(
            u0, _job_squad_view(u0), _job_squad_value_vp(u0, srr4), 10.0,
            marker, 2, 0, proj, map_, srr4, 3, lambda: (rows, None),
            True, ())
        self.assertAlmostEqual(got, expected, delta=1e-9)

        # NOT vp x 4: the undiscounted iteration-5 net is > 4x the priced one.
        undiscounted = _job_value_fallback_net(
            _job_squad_view(u0), _job_squad_value_vp(u0, srr4), marker, 2, 0,
            proj, map_, srr4, True, ())
        self.assertGreater(undiscounted, 4.0 * got)

    def test_m_lethal_waypoint_prices_zero(self):
        """(k-new) The same marker with a LETHAL first waypoint (the MineBody's
        10.0 expected wounds equal the squad pool -> frac_1 = 1) prices
        exactly 0: the survival product hits zero and the temporal net with it
        — even though the destination itself is barely threatened (the mine's
        9-inch projected reach ends 3 inches short of it, so the pre-survival
        net is the same positive 4.90 as the j-fixture's)."""
        members, marker, friendly, enemy, map_ = self._board(with_mine=True)
        u0 = members[0]
        proj = _threat_projectors(enemy)
        srr4 = _value_scoring_rounds_remaining(2)
        rows = _job_threat_precompute(u0, proj)

        surv = _job_transit_survival(
            u0, (marker.x, marker.y), 3, map_, rows, None, 10.0)
        self.assertAlmostEqual(surv, 0.0, delta=1e-9)

        got = _job_marker_transit_net(
            u0, _job_squad_view(u0), _job_squad_value_vp(u0, srr4), 10.0,
            marker, 2, 0, proj, map_, srr4, 3, lambda: (rows, None),
            True, ())
        self.assertAlmostEqual(got, 0.0, delta=1e-9)

    def test_n_turns_leq_one_identical_to_iteration5(self):
        """(l-new) turns_to_reach of 0 or 1 is byte-identical to the
        iteration-5 pricing: full srr, no transit survival, and the lazy
        threat context is NEVER built (a raising context proves it)."""
        members, marker, friendly, enemy, map_ = self._board()
        u0 = members[0]
        proj = _threat_projectors(enemy)
        srr4 = _value_scoring_rounds_remaining(2)

        def _boom():
            raise AssertionError("threat context built for turns <= 1")

        it5 = _job_value_fallback_net(
            _job_squad_view(u0), _job_squad_value_vp(u0, srr4), marker, 2, 0,
            proj, map_, srr4, True, ())
        for turns in (0, 1):
            got = _job_marker_transit_net(
                u0, _job_squad_view(u0), _job_squad_value_vp(u0, srr4), 10.0,
                marker, 2, 0, proj, map_, srr4, turns, _boom, True, ())
            self.assertAlmostEqual(got, it5, delta=1e-9)

    def test_o_enemy_projection_expands_waypoint_reach(self):
        """(m-new, iteration 7) The j-new synthetic with the PistolBody moved
        to (36,22): TWENTY inches from waypoint one — JUST outside its
        18-inch current-position reach (6 move + 12 range) but inside it
        after ONE turn of its own move (18 + 6 = 24) — and 14 inches from
        waypoint two (inside either way).

        HAND-PINNED, both pricings:
          iteration-6 (current-position reach at every waypoint):
            waypoint one COLD (T = 0), waypoint two hot with NO prior
            depletion -> survival = 1 x (1 - (1/6)/10) = 59/60.
          iteration-7 (reach expanded by t x enemy move at waypoint t):
            waypoint one HOT at t=1 (20 <= 24) -> frac 1/60;
            health depletes to 59/6 -> waypoint-two frac 1/59;
            survival = (59/60) x (58/59) = 29/30."""
        members, marker, friendly, enemy, map_ = self._board()
        u0 = members[0]
        # Move the pistol to the m-new position (just outside wp1's reach).
        pistol = enemy.units[0]
        pistol.position = (36.0, 22.0)
        proj = _threat_projectors(enemy)
        rows = _job_threat_precompute(u0, proj)
        wp1 = (16.0, 22.0)

        # The reach expansion itself, pinned at the scan level.
        self.assertEqual(
            _job_threat_scan(rows, u0, wp1, map_, None), 0.0)      # cold at t=0
        self.assertAlmostEqual(
            _job_threat_scan(rows, u0, wp1, map_, None, advance_turns=1),
            1.0 / 6.0, delta=1e-9)                                 # hot at t=1

        # The iteration-6 product (current-position reach), reconstructed
        # from the unexpanded scans: 1 x (1 - (1/6)/10) = 59/60.
        t1_old = _job_threat_scan(rows, u0, wp1, map_, None)
        t2_old = _job_threat_scan(rows, u0, (22.0, 22.0), map_, None)
        old_surv = (1.0 - min(1.0, t1_old / 10.0)) * (
            1.0 - min(1.0, t2_old / (10.0 - t1_old)))
        self.assertAlmostEqual(old_surv, 59.0 / 60.0, delta=1e-9)

        # The iteration-7 transit survival prices the waypoint hot.
        surv = _job_transit_survival(
            u0, (marker.x, marker.y), 3, map_, rows, None, 10.0)
        self.assertAlmostEqual(surv, 29.0 / 30.0, delta=1e-9)


def _reserve_evictor():
    """A 250-point, objective-control-8 reserve unit for the garrison-depth
    fixtures: two of them are the brief's five hundred points of enemy
    reserves pending, projecting sixteen effective objective control onto
    every reserve-contestable marker."""
    return UnitProfile(
        name="ReserveEvictor", health=6, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=5, move=6.0, oc=8,
        attacks=3, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=250,
    )


class GarrisonDepth(unittest.TestCase):
    """Iteration-9 garrison sufficiency: the greedy pile-on cap compares the
    assigned objective control against the PROJECTED contest pressure
    (`_job_projected_contest_oc`) — enemy control that can reach the marker
    within one enemy move, plus the whole reserve pool where a legal
    deep-strike arrival cell exists — instead of the enemy control standing
    on the marker now (zero for home markers, hence the measured
    single-squad garrisons evicted 0.7 to 1.0 times per game)."""

    def test_r_reserves_deepen_the_garrison(self):
        """(r) A marker with five hundred points of enemy reserves pending
        (two objective-control-8 units -> projected contest 16) deepens the
        garrison beyond one squad: three OC-5 holders assign (5 <= 16,
        10 <= 16, 15 <= 16 — candidates run out), where iteration-8's cap
        (enemy control AT the marker = 0) stopped after one."""
        marker = _Obj(30.0, 22.0)
        map_ = _Map([marker])
        holders = [_Unit(_cheap_holder(), (30.0, 12.0), uid=1 + i)
                   for i in range(3)]           # 10 inches: reachable (6+6)
        far_enemy = _Unit(_fragile_target(), (200.0, 200.0), uid=99)
        friendly = _Army(holders)
        enemy = _Army([far_enemy], is_a=False)
        enemy.name = "Enemy"
        reserves = [_Unit(_reserve_evictor(), (0.0, 0.0), uid=201),
                    _Unit(_reserve_evictor(), (0.0, 0.0), uid=202)]
        battle = _Battle(friendly, enemy, {"Enemy": reserves})
        friendly._battle_ref = battle

        projected = _job_projected_contest_oc(
            marker, enemy.alive_units, friendly.alive_units, battle, enemy)
        self.assertEqual(projected, 16)         # the pinned arithmetic

        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            assign_jobs(friendly, enemy, map_, CUR_ROUND)
            assigned = [uid for uid, oid in friendly.job_assignments.items()
                        if oid == id(marker)]
            self.assertEqual(len(assigned), 3)  # deepened, candidates ran out
        finally:
            del os.environ["SWEG_JOB_LAYER"]

    def test_s_no_pressure_single_squad_unchanged(self):
        """(s) No reserves and the only enemy three-plus turns away (38
        inches, move 6 — outside the one-enemy-move projection horizon):
        projected contest is exactly 0 and the garrison stays ONE squad —
        identical to the iteration-8 behaviour (the guard: real pressure
        deepens garrisons, absent pressure must not recreate the turtle)."""
        marker = _Obj(30.0, 22.0)
        map_ = _Map([marker])
        holders = [_Unit(_cheap_holder(), (30.0, 12.0), uid=1 + i)
                   for i in range(3)]
        slow_enemy = _Unit(_fragile_target(), (30.0, 60.0), uid=99)  # 38 in
        friendly = _Army(holders)
        enemy = _Army([slow_enemy], is_a=False)
        enemy.name = "Enemy"
        battle = _Battle(friendly, enemy, {"Enemy": []})
        friendly._battle_ref = battle

        projected = _job_projected_contest_oc(
            marker, enemy.alive_units, friendly.alive_units, battle, enemy)
        self.assertEqual(projected, 0)

        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            assign_jobs(friendly, enemy, map_, CUR_ROUND)
            assigned = [uid for uid, oid in friendly.job_assignments.items()
                        if oid == id(marker)]
            self.assertEqual(len(assigned), 1)  # iteration-8 behaviour intact
        finally:
            del os.environ["SWEG_JOB_LAYER"]

    def test_t_deepening_never_evicts_the_midfield_claim(self):
        """(t) The deepened garrison's extra squad comes from the next-best
        candidates — a third squad standing on the midfield marker keeps its
        own assignment (the midfield disc is arrival-denied by that squad
        standing on it, so the reserve pressure deepens only the home
        garrison)."""
        home = _Obj(30.0, 12.0)
        mid = _Obj(30.0, 40.0)
        map_ = _Map([home, mid])
        # Ten inches from home: within assignment reach (move 6 + 6) AND far
        # enough that the home disc keeps a legal arrival cell (the garrison
        # standing closer would deny it — the projection's self-regulation,
        # exercised by the s3/midfield half of this fixture).
        s1 = _Unit(_cheap_holder(), (30.0, 2.0), uid=1)    # near home only
        s2 = _Unit(_cheap_holder(), (30.0, 2.0), uid=2)
        s3 = _Unit(_cheap_holder(), (30.0, 40.0), uid=3)   # ON the midfield
        far_enemy = _Unit(_fragile_target(), (200.0, 200.0), uid=99)
        friendly = _Army([s1, s2, s3])
        enemy = _Army([far_enemy], is_a=False)
        enemy.name = "Enemy"
        reserves = [_Unit(_reserve_evictor(), (0.0, 0.0), uid=201),
                    _Unit(_reserve_evictor(), (0.0, 0.0), uid=202)]
        battle = _Battle(friendly, enemy, {"Enemy": reserves})
        friendly._battle_ref = battle

        os.environ["SWEG_JOB_LAYER"] = "1"
        try:
            assign_jobs(friendly, enemy, map_, CUR_ROUND)
            self.assertEqual(friendly.job_assignments.get(s1.uid), id(home))
            self.assertEqual(friendly.job_assignments.get(s2.uid), id(home))
            self.assertEqual(friendly.job_assignments.get(s3.uid), id(mid))
        finally:
            del os.environ["SWEG_JOB_LAYER"]


if __name__ == "__main__":
    unittest.main()
