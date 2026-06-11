"""Tests for the gated base-edge charge-end placement (env-gate
SWEG_CHARGE_BASEEDGE, wave 240 lever 1).

Real 10th edition: a charge move must end within Engagement Range of every
target unit, and Engagement Range — like every other distance — is measured
between the CLOSEST POINTS OF THE BASES of the two models (Wahapedia core
rules, cited `simulator.charge_end_base_to_base`). SwegHammer's legacy charge
placement instead stopped the charger so its CENTRE sat 1.0" from the target's
CENTRE, which drives the charger's base 2-3" INTO a big-based target (tank,
monster, Knight) — the proven root cause of the real base overlap measured by
scripts/diag_overlap_audit.py.

The gate (default ON since wave 240 — adopted with SWEG_DEPLOY_COLLISION as the
collision pair on the metric-neutral N=80 paired confirm; set =0 for the legacy
centre-distance path) places the charger so its BASE EDGE finishes within 1.0"
of the target's base edge, validates the spot against the no-overlap collision
predicate, and searches deterministically around the target for a legal spot
when the straight approach is blocked, falling back to the legacy placement
(never cancelling a successful charge) when fully surrounded.

Wave 241 added the MEASUREMENT half of the same rule (cited
`simulator.engagement_range_base_edge`): the gate now also controls how the
Engagement-Range distance is measured everywhere — fight eligibility, the
shooting melee-lock, the charge-roll requirement. Placement and measurement
are two halves of one rule; wave 240 shipped placement alone, which parked a
32mm charger at centre ~2.26" and stranded it outside every then-centre-based
fight gate, so charges landed but melee never resolved
(scripts/diag_fightgate_check.py: 18 successful charges, 0 swings).

These tests cover:
  * default fixed-seed battle-outcome identity (unset == explicit "1"),
  * gate-off charge placement is the exact legacy centre-1" formula,
  * gate-on the charger ends within 1" base-edge of its target and overlaps no
    other model,
  * gate-on a big-base target (Knight/tank footprint) is no longer
    interpenetrated,
  * deterministic legacy fallback when the target is fully surrounded,
  * `_er_gap` returns the base-edge gap with the gate on and the plain centre
    distance with the gate off (wave 241),
  * gate-on a unit parked at the gated charge-end spot IS inside the fight
    gate (the wave-241 regression — placement and measurement must agree),
  * gate-on the shooting melee-lock sees a base-contact engagement the centre
    measure would miss,
  * gate-on the 2D6 charge requirement against a big base is the real move
    needed (base-edge gap minus 1"), not the centre distance,
  * battle-level: the 4v4 melee scenario from scripts/diag_fightgate_check.py
    produces melee swings under the gate.
"""

from __future__ import annotations

import os
import random
import unittest
from unittest import mock

from code.army import Army
from code.events import EventLog, UnitCharged, UnitFought, UnitShot
from code.map import Map, Objective
from code.simulator import Battle, _distance
from code.sim.geometry import _bc_model_radius_in, _er_gap
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def _charger_profile() -> UnitProfile:
    """Melee bruiser on a default 32mm base that WANTS to charge (melee output
    strictly exceeds its ranged output, so `_wants_to_charge` is True)."""
    return UnitProfile(
        name="Charger", health=4, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=0, weapon_damage_per_shot=0.0, range_inches=1,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5, melee_ap=1,
        move=6.0,
        base_diameter_mm=32,
    )


def _small_target_profile() -> UnitProfile:
    """A tough 32mm-base target that survives a round of melee (so the charger's
    end position can be inspected — a dead target would be removed)."""
    return UnitProfile(
        name="SmallTarget", health=12, damage=0, hit_probability=0,
        ap=0, save=2, strength=4, toughness=9,
        attacks=0, range_inches=1,
        leadership=8,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        move=6.0,
        base_diameter_mm=32,
    )


def _knight_target_profile() -> UnitProfile:
    """A big-base target — an oval Knight-class footprint (170mm x 110mm). Tough
    enough to survive a round of melee so its base interpenetration can be
    inspected after the charge."""
    return UnitProfile(
        name="KnightTarget", health=22, damage=0, hit_probability=0,
        ap=0, save=2, strength=8, toughness=12,
        attacks=0, range_inches=1,
        leadership=9,
        faction="Generic",
        unit_keywords=("VEHICLE", "TITANIC"),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=8, melee_ap=0,
        move=10.0,
        base_shape="oval",
        base_width_mm=170,
        base_length_mm=110,
    )


def _blocker_profile() -> UnitProfile:
    """A passive 32mm body used to fully ring a target so the base-edge search
    finds no legal spot (forcing the legacy fallback)."""
    return UnitProfile(
        name="Blocker", health=3, damage=0, hit_probability=0,
        ap=0, save=4, strength=3, toughness=4,
        attacks=0, range_inches=1,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=0, melee_damage_per_shot=0.0,
        melee_hit_probability=0.0, melee_strength=3, melee_ap=0,
        move=6.0,
        base_diameter_mm=32,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_map() -> Map:
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _make_army(name: str, profile: UnitProfile, positions: list) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


def _force_charge_roll_12():
    """Patch random.randint so the per-squad 2D6 charge roll is 6+6 = 12 — a
    guaranteed success for any in-range target — without depending on a seed.
    Only the (1, 6) call (the d6) is overridden; any other randint call passes
    through unchanged."""
    real_randint = random.randint

    def fake(a, b):
        if (a, b) == (1, 6):
            return 6
        return real_randint(a, b)

    return mock.patch("random.randint", side_effect=fake)


def _reset_process_globals():
    """HERMETIC GUARD (mirrors tests/test_vanilla_rules.py::VanillaSmokeTests):
    these charge tests construct transient UnitProfiles and run battles, which
    populate the module-level lru_caches and bump the buffs-generation counter.
    The win-rate-balance smokes elsewhere in the suite are sensitive to that
    accumulated process-global state, so reset it on setUp and tearDown here to
    keep this file order-independent and prevent it perturbing other tests.
    See [[project-classify-cache-flakiness]]."""
    from code import leaders, roles, strategy, units
    for _fn in (
        getattr(leaders, "lookup_ability", None),
        getattr(units, "wound_probability", None),
        getattr(roles, "classify", None),
        getattr(roles, "expected_ranged_dpa", None),
        getattr(roles, "expected_melee_dpa", None),
        getattr(strategy, "_unsaved_fraction_cached", None),
        getattr(strategy, "_fnp_pass_fraction_cached", None),
    ):
        _cc = getattr(_fn, "cache_clear", None)
        if _cc is not None:
            _cc()
    _bump = getattr(leaders, "bump_buffs_generation", None)
    if _bump is not None:
        _bump()


# ---------------------------------------------------------------------------
# Gate-OFF byte-identity
# ---------------------------------------------------------------------------

class GateOffIdentityTests(unittest.TestCase):
    """With the gate explicitly "0" the simulator must behave exactly as the
    legacy centre-to-centre placement; with the gate UNSET the default is now
    the base-edge path (default ON since the wave-240 adoption)."""

    def setUp(self):
        # Explicit opt-out: the gate is default-ON, so the legacy-path tests
        # must set "0" themselves (mirrors tests/test_bof_assault.py).
        os.environ["SWEG_CHARGE_BASEEDGE"] = "0"
        _reset_process_globals()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_process_globals()

    def _run_outcome(self):
        a = _make_army("A", _charger_profile(),
                       [(20.0, 30.0), (22.0, 28.0), (24.0, 32.0)])
        b = _make_army("B", _small_target_profile(),
                       [(26.0, 30.0), (30.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        res = battle.run()
        return (res.winner, res.rounds, res.a_vp, res.b_vp)

    def test_default_unset_matches_explicit_on(self):
        """Default (env unset) and SWEG_CHARGE_BASEEDGE=1 produce the identical
        fixed-seed battle outcome — the gate is default-ON since the wave-240
        adoption (unset now runs the base-edge branch)."""
        random.seed(12345)
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        unset_outcome = self._run_outcome()

        random.seed(12345)
        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"
        on_outcome = self._run_outcome()

        self.assertEqual(unset_outcome, on_outcome)

    def test_gate_off_uses_legacy_centre_placement(self):
        """With the gate OFF, a successful charge ends with the charger's CENTRE
        exactly 1.0" from the target's CENTRE — the legacy formula, unchanged."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "0"
        a = _make_army("A", _charger_profile(), [(20.0, 30.0)])
        b = _make_army("B", _small_target_profile(), [(24.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, target = a.units[0], b.units[0]

        with _force_charge_roll_12():
            battle._do_charge(attacker, battle.a, battle.b)

        # Legacy placement: scale = (dist - 1)/dist along the centre line, so the
        # charger ends 1.0" from the target CENTRE (deep inside any large base).
        self.assertAlmostEqual(
            _distance(attacker.position, target.position), 1.0, places=5,
            msg="Gate-off placement must keep the legacy centre-1\" formula.",
        )


# ---------------------------------------------------------------------------
# Gate-ON base-edge placement
# ---------------------------------------------------------------------------

class GateOnBaseEdgeTests(unittest.TestCase):
    """With the gate ON, a successful charge ends within 1" base-edge of the
    target and overlaps no other model."""

    def setUp(self):
        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"
        # Collision must be ON for the gated path's legality validation; it is
        # the production default, but pin it explicitly for the test.
        os.environ.pop("SWEG_COLLISION", None)
        _reset_process_globals()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_process_globals()

    def test_charger_ends_within_one_inch_base_edge(self):
        """The charger's BASE EDGE finishes within 1.0" of the target's base
        edge (centre distance ~= 1 + r_attacker + r_target)."""
        a = _make_army("A", _charger_profile(), [(20.0, 30.0)])
        b = _make_army("B", _small_target_profile(), [(25.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, target = a.units[0], b.units[0]

        with _force_charge_roll_12():
            battle._do_charge(attacker, battle.a, battle.b)

        r_a = _bc_model_radius_in(attacker.profile)
        r_t = _bc_model_radius_in(target.profile)
        gap = _distance(attacker.position, target.position) - (r_a + r_t)
        self.assertGreaterEqual(
            gap, -1e-6, "Charger base must not overlap the target base.")
        self.assertLessEqual(
            gap, 1.0 + 1e-6,
            "Charger base edge must finish within 1\" of the target base edge.")

    def test_charger_does_not_overlap_other_models(self):
        """With a second enemy model sitting beside the target, the gated end
        position overlaps NEITHER the target nor the bystander."""
        a = _make_army("A", _charger_profile(), [(20.0, 30.0)])
        # Target at (25,30); a bystander parked right where the straight base-edge
        # approach point would land, forcing the deterministic angular search.
        b = _make_army("B", _small_target_profile(),
                       [(25.0, 30.0), (23.6, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, target, bystander = a.units[0], b.units[0], b.units[1]

        with _force_charge_roll_12():
            battle._do_charge(attacker, battle.a, battle.b)

        r_a = _bc_model_radius_in(attacker.profile)
        for other in (target, bystander):
            r_o = _bc_model_radius_in(other.profile)
            self.assertGreaterEqual(
                _distance(attacker.position, other.position),
                r_a + r_o - 1e-6,
                f"Charger overlaps {other.profile.name} after a gated charge.",
            )
        # Still ends in Engagement Range of the chosen target.
        r_t = _bc_model_radius_in(target.profile)
        gap = _distance(attacker.position, target.position) - (r_a + r_t)
        self.assertLessEqual(gap, 1.0 + 1e-6)

    def test_big_base_target_not_interpenetrated(self):
        """A big-base Knight target is no longer driven into: under the legacy
        placement the charger centre sat 1" from the Knight centre (3-4" inside
        its ~2.76" base radius). The gated placement keeps the bases apart."""
        a = _make_army("A", _charger_profile(), [(10.0, 30.0)])
        b = _make_army("B", _knight_target_profile(), [(18.0, 30.0)])
        battle = Battle(a, b, map_=_open_map())
        attacker, knight = a.units[0], b.units[0]

        with _force_charge_roll_12():
            battle._do_charge(attacker, battle.a, battle.b)

        r_a = _bc_model_radius_in(attacker.profile)
        r_k = _bc_model_radius_in(knight.profile)
        self.assertGreater(
            r_k, 2.0,
            "Test fixture sanity: the Knight footprint must be a big base.")
        centre_dist = _distance(attacker.position, knight.position)
        # No interpenetration: centre distance >= sum of radii (bases touch at
        # worst, never overlap).
        self.assertGreaterEqual(
            centre_dist, r_a + r_k - 1e-6,
            "Charger base is interpenetrating the Knight base.")
        # And it is genuinely an improvement over the legacy 1.0" centre gap.
        self.assertGreater(
            centre_dist, 1.0 + 1e-6,
            "Gated placement should sit further out than the legacy centre-1\".")


# ---------------------------------------------------------------------------
# Deterministic legacy fallback when surrounded
# ---------------------------------------------------------------------------

class SurroundedFallbackTests(unittest.TestCase):
    """When the target is fully ringed so no legal base-edge spot exists, the
    gated path falls back to the legacy placement — a successful charge is never
    cancelled — and the result is deterministic across reruns."""

    def setUp(self):
        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"
        os.environ.pop("SWEG_COLLISION", None)
        _reset_process_globals()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_process_globals()

    def _build(self):
        """A charger at (20,30) and a target at (30,30), with a friendly body
        of the target's army occupying every base-edge candidate position the
        deterministic search would try — so no legal spot exists at the
        base-edge distance and the search must fall back to the legacy
        placement. The blockers are placed EXACTLY on the 19 candidate points
        the search visits (the approach bearing +/-10..+/-90 in 10-degree steps,
        at the candidate radius), so each candidate coincides with a blocker
        centre and is rejected by the no-overlap predicate."""
        import math
        ax, ay = 20.0, 30.0
        tx, ty = 30.0, 30.0
        r_a = _bc_model_radius_in(_charger_profile())
        r_t = _bc_model_radius_in(_small_target_profile())
        cand_r = 1.0 + r_a + r_t   # the radius the search places candidates at
        # Approach bearing (target -> attacker), matching `_charge_baseedge_end`.
        base_ang = math.atan2(ay - ty, ax - tx)
        offsets = [0.0]
        for deg in range(10, 91, 10):
            offsets.append(float(deg))
            offsets.append(float(-deg))

        b = Army("B")
        b.add_unit(_small_target_profile())
        b.units[-1].uid = "B0"
        b.units[-1].position = (tx, ty)
        for i, off in enumerate(offsets, start=1):
            ang = base_ang + math.radians(off)
            pos = (tx + math.cos(ang) * cand_r, ty + math.sin(ang) * cand_r)
            b.add_unit(_blocker_profile())
            b.units[-1].uid = f"B{i}"
            b.units[-1].position = pos

        a = _make_army("A", _charger_profile(), [(ax, ay)])
        battle = Battle(a, b, map_=_open_map())
        return battle

    def test_surrounded_falls_back_to_legacy_and_is_deterministic(self):
        # Call the placement helper directly so the target is unambiguous (the
        # full `_do_charge` picker could otherwise pick a softer blocker). The
        # helper derives the centre distance itself (wave 241: the caller's
        # charge distance is the REQUIRED 2D6 move, not the centre distance).
        positions = []
        for _ in range(2):
            battle = self._build()
            attacker = battle.a.units[0]
            target = battle.b.units[0]
            with _force_charge_roll_12():
                end = battle._charge_baseedge_end(attacker, target)
            positions.append(end)

        # Deterministic: the two reruns return exactly the same position (the
        # angular search consumes no random numbers).
        self.assertEqual(positions[0], positions[1])

        # The fallback is the LEGACY placement: centre 1.0" from the target
        # centre (a successful charge is never cancelled by a placement
        # failure — 10e has no "no room, charge fails" clause once the roll is
        # made).
        self.assertAlmostEqual(
            _distance(positions[0], (30.0, 30.0)), 1.0, places=5,
            msg="Fully-surrounded charge must fall back to the legacy "
                "centre-1\" placement, never be cancelled.",
        )

    def test_surrounded_full_charge_still_completes(self):
        """End to end through `_do_charge`: even when the chosen target is
        ringed, the charge resolves (the charger is recorded as charging) — the
        placement fallback must never cancel a successful charge."""
        battle = self._build()
        attacker = battle.a.units[0]
        with _force_charge_roll_12():
            battle._do_charge(attacker, battle.a, battle.b)
        self.assertIn(
            attacker.uid, battle._charging_this_round,
            "A successful charge must complete even when placement falls back.",
        )


# ---------------------------------------------------------------------------
# Engagement-Range MEASUREMENT (wave 241): the same gate controls how the
# Engagement-Range distance is MEASURED everywhere, not just where a charge
# ends. Cited `simulator.engagement_range_base_edge`.
# ---------------------------------------------------------------------------

def _shooter_profile() -> UnitProfile:
    """An INFANTRY gunner — non-pistol, non-VEHICLE/MONSTER — whose shooting
    is subject to the melee lock (used to test the gate-aware shooting gate)."""
    return UnitProfile(
        name="Shooter", health=4, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        move=6.0,
        base_diameter_mm=32,
    )


class EngagementMeasurementTests(unittest.TestCase):
    """Wave-241 regression suite: with the gate ON, Engagement Range is
    MEASURED base-edge to base-edge everywhere (fight eligibility, the
    shooting melee-lock, the charge-roll requirement); with the gate OFF every
    site is the byte-identical legacy centre measure. Placement and
    measurement must agree — wave 240 shipped placement alone and melee never
    resolved under the adopted default."""

    def setUp(self):
        _reset_process_globals()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_process_globals()

    # -- 1. the primitive ---------------------------------------------------

    def test_er_gap_on_is_base_edge_gap_off_is_centre_distance(self):
        """`_er_gap` subtracts both base radii with the gate on (plus a tiny
        epsilon so the exactly-1"-gap charge-end spot counts as engaged
        despite float reconstruction error) and is the plain centre distance
        with the gate off."""
        pa = _charger_profile()
        pk = _knight_target_profile()
        r_a = _bc_model_radius_in(pa)
        r_k = _bc_model_radius_in(pk)
        pos_a, pos_k = (10.0, 10.0), (16.0, 10.0)

        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"
        self.assertAlmostEqual(
            _er_gap(pos_a, pa, pos_k, pk), 6.0 - (r_a + r_k), places=6,
            msg="Gate-on gap must be centre distance minus both radii.")

        os.environ["SWEG_CHARGE_BASEEDGE"] = "0"
        self.assertAlmostEqual(
            _er_gap(pos_a, pa, pos_k, pk), 6.0, places=9,
            msg="Gate-off must be the plain centre distance, byte-identical "
                "to the legacy measure.")

    # -- 2. the fight gate (THE wave-241 bug) --------------------------------

    def _fight_events_at_charge_end_spot(self):
        """Park a charger at EXACTLY the gated charge-end spot (base-edge gap
        = 1.0", centre = 1 + r_a + r_t) and run the fight routine. Returns the
        UnitFought events emitted."""
        r_a = _bc_model_radius_in(_charger_profile())
        r_t = _bc_model_radius_in(_small_target_profile())
        centre = 1.0 + r_a + r_t
        a = _make_army("A", _charger_profile(), [(20.0, 30.0)])
        b = _make_army("B", _small_target_profile(), [(20.0 + centre, 30.0)])
        log = EventLog()
        battle = Battle(a, b, map_=_open_map(), subscribers=[log])
        random.seed(99)
        battle._do_fight(a.units[0], battle.a, battle.b)
        return [ev for ev in log.events if isinstance(ev, UnitFought)]

    def test_fight_resolves_at_gated_charge_end_spot(self):
        """THE wave-241 regression: a unit standing where the gated charge
        placement puts it (base-edge gap exactly 1") must be INSIDE the fight
        gate — `_do_fight` emits a UnitFought. Before the fix the fight gate
        measured centre distance (~2.26" here) and the swing never happened:
        charges landed, melee never resolved."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"
        fought = self._fight_events_at_charge_end_spot()
        self.assertGreaterEqual(
            len(fought), 1,
            "A charger at the gated charge-end spot must be able to fight — "
            "placement and measurement must agree.")

    def test_fight_gate_off_keeps_legacy_centre_measure(self):
        """Same positions with the gate OFF: centre ~2.26" > 1.0", so the
        legacy fight gate correctly sees the unit as NOT engaged (byte-
        identical legacy behaviour)."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "0"
        fought = self._fight_events_at_charge_end_spot()
        self.assertEqual(
            len(fought), 0,
            "Gate-off fight eligibility must keep the legacy centre measure.")

    # -- 3. the shooting melee-lock ------------------------------------------

    def _shoot_events_at_base_contact(self):
        """A non-pistol INFANTRY gunner at centre 1.3" from an enemy: base
        edges nearly touch (gap ~0.04") but the centres are over 1" apart —
        the case where the two measures disagree. Returns UnitShot events."""
        a = _make_army("A", _shooter_profile(), [(20.0, 30.0)])
        b = _make_army("B", _small_target_profile(), [(21.3, 30.0)])
        log = EventLog()
        battle = Battle(a, b, map_=_open_map(), subscribers=[log])
        random.seed(99)
        battle._do_shoot(a.units[0], battle.a, battle.b)
        return [ev for ev in log.events if isinstance(ev, UnitShot)]

    def test_shooting_lock_sees_base_contact_engagement(self):
        """Gate ON: the shooter is within Engagement Range base-edge to
        base-edge, so the melee lock fires and a non-pistol INFANTRY unit may
        not shoot. The lock and the fight gate must share one definition, or
        a base-contact-engaged gunner could shoot (or fall back) freely while
        simultaneously being meleeable."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"
        shots = self._shoot_events_at_base_contact()
        self.assertEqual(
            len(shots), 0,
            "Base-contact engagement must lock a non-pistol INFANTRY shooter.")

    def test_shooting_lock_gate_off_uses_centre_measure(self):
        """Gate OFF: centre 1.3" > 1.0", so the legacy lock sees the shooter
        as free and it shoots (byte-identical legacy behaviour)."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "0"
        shots = self._shoot_events_at_base_contact()
        self.assertGreaterEqual(
            len(shots), 1,
            "Gate-off shooting lock must keep the legacy centre measure.")

    # -- 4. the charge-roll requirement ---------------------------------------

    @staticmethod
    def _force_charge_roll(d1: int, d2: int):
        """Patch random.randint so the FIRST TWO (1, 6) calls — the per-squad
        2D6 charge roll — return d1 then d2; everything else passes through.
        (No overwatch RNG precedes the roll here: the Knight defender has
        attacks=0, so it is never selected as an overwatcher.)"""
        real_randint = random.randint
        rolls = iter((d1, d2))

        def fake(a, b):
            if (a, b) == (1, 6):
                try:
                    return next(rolls)
                except StopIteration:
                    return real_randint(a, b)
            return real_randint(a, b)

        return mock.patch("random.randint", side_effect=fake)

    def _charge_knight_at_eleven_inches(self):
        """A 32mm charger 11" (centre) from a Knight. Base-edge gap ~7.61",
        so the real move needed to reach Engagement Range is ~6.61" — a 2D6
        roll of 7 makes it. The legacy centre measure demanded the full 11.
        Returns (battle, attacker, UnitCharged events)."""
        a = _make_army("A", _charger_profile(), [(20.0, 30.0)])
        b = _make_army("B", _knight_target_profile(), [(31.0, 30.0)])
        log = EventLog()
        battle = Battle(a, b, map_=_open_map(), subscribers=[log])
        attacker = a.units[0]
        with self._force_charge_roll(4, 3):   # 2D6 = 7
            battle._do_charge(attacker, battle.a, battle.b)
        charges = [ev for ev in log.events if isinstance(ev, UnitCharged)]
        return battle, attacker, charges

    def test_charge_requirement_is_real_move_not_centre_distance(self):
        """Gate ON: the 2D6 must meet the base-edge gap minus 1" (~6.61"
        against this Knight at 11" centre), so a roll of 7 succeeds — the
        faithful 10e charge a centre measure wrongly made near-impossible."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"
        battle, attacker, charges = self._charge_knight_at_eleven_inches()
        self.assertEqual(len(charges), 1)
        self.assertTrue(charges[0].succeeded)
        self.assertIn(attacker.uid, battle._charging_this_round)
        # The emitted requirement is the REAL move (gap - 1"), not the centre
        # distance: 11 - (r_a + r_k) - 1 ~= 6.61.
        self.assertGreater(charges[0].distance, 6.0)
        self.assertLess(charges[0].distance, 7.0)

    def test_charge_requirement_gate_off_is_centre_distance(self):
        """Gate OFF: the same roll of 7 fails against the legacy centre-11"
        requirement (byte-identical legacy behaviour)."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "0"
        battle, attacker, charges = self._charge_knight_at_eleven_inches()
        self.assertEqual(len(charges), 1)
        self.assertFalse(charges[0].succeeded)
        self.assertNotIn(attacker.uid, battle._charging_this_round)
        self.assertAlmostEqual(charges[0].distance, 11.0, places=6)

    # -- 5. battle-level: the diagnostic scenario ------------------------------

    def test_diag_scenario_melee_resolves_under_gate(self):
        """Mirror of scripts/diag_fightgate_check.py (4v4 32mm melee armies,
        seed 7): with the gate ON the battle must produce successful charges
        AND melee swings. Before the wave-241 fix this scenario produced 18
        successful charges and ZERO swings — melee was structurally disabled
        under the adopted default."""
        os.environ["SWEG_CHARGE_BASEEDGE"] = "1"

        def melee_profile(name: str) -> UnitProfile:
            return UnitProfile(
                name=name, health=8, damage=1, hit_probability=0.5,
                ap=0, save=3, strength=4, toughness=4,
                attacks=1, weapon_damage_per_shot=1.0, range_inches=12,
                leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
                melee_attacks=6, melee_damage_per_shot=1.0,
                melee_hit_probability=0.66, melee_strength=5, melee_ap=1,
                move=6.0, base_diameter_mm=32,
            )

        random.seed(7)
        a = Army("A")
        b = Army("B")
        for _ in range(4):
            a.add_unit(melee_profile("Bruiser"))
            b.add_unit(melee_profile("Brawler"))
        log = EventLog()
        battle = Battle(a, b, map_=_open_map(), subscribers=[log])
        battle.run()

        charges = [ev for ev in log.events
                   if isinstance(ev, UnitCharged) and ev.succeeded]
        swings = [ev for ev in log.events if isinstance(ev, UnitFought)]
        self.assertGreater(
            len(charges), 0,
            "The melee scenario must produce successful charges.")
        self.assertGreater(
            len(swings), 0,
            "Successful charges must produce melee swings under the gate — "
            "zero swings is the wave-240 structural-melee-disable bug.")


if __name__ == "__main__":
    unittest.main()
