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

These tests cover:
  * default fixed-seed battle-outcome identity (unset == explicit "1"),
  * gate-off charge placement is the exact legacy centre-1" formula,
  * gate-on the charger ends within 1" base-edge of its target and overlaps no
    other model,
  * gate-on a big-base target (Knight/tank footprint) is no longer
    interpenetrated,
  * deterministic legacy fallback when the target is fully surrounded.
"""

from __future__ import annotations

import os
import random
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle, _distance
from code.sim.geometry import _bc_model_radius_in
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
        # dist argument is the centre-to-centre charge distance.
        positions = []
        for _ in range(2):
            battle = self._build()
            attacker = battle.a.units[0]
            target = battle.b.units[0]
            dist = _distance(attacker.position, target.position)
            with _force_charge_roll_12():
                end = battle._charge_baseedge_end(attacker, target, dist)
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


if __name__ == "__main__":
    unittest.main()
