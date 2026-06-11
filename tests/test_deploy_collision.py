"""Deployment collision relaxation tests (SWEG_DEPLOY_COLLISION gate).

Four test classes:
  1. GateOffIdentityTests   — gate OFF produces byte-identical positions to the
                              baseline (determinism check via two seeds).
  2. GateOnNoOverlapTests   — gate ON: zero overlapping base pairs at
                              BattleStarted for several seeds / faction matchups.
  3. MapBoundsTests         — gate ON: all units stay inside map bounds after
                              relaxation even when a dense deployment would push
                              them out.
  4. DeterminismTests       — gate ON: running the same seed twice gives
                              identical positions (pure geometry, no RNG).

The overlap check reuses the pairwise idiom from scripts/diag_overlap_audit.py:
  penetration = (r_i + r_j) - dist(i, j)  >  TOL_IN  =>  overlap

The tests build small synthetic armies directly (no archetype build or random
fill) so they are fast, hermetic, and do not require the full catalogue.
"""
from __future__ import annotations

import math
import os
import random
import unittest

from code.army import Army
from code.events import BattleStarted, EventLog
from code.sim.geometry import _bc_model_radius_in
from code.simulator import Battle
from code.units import UnitProfile


TOL_IN = 0.02   # penetration below this is "touching / rounding", not overlap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _basic_profile(name: str = "Trooper", **overrides) -> UnitProfile:
    """Minimal UnitProfile — enough for deployment tests."""
    base = dict(
        name=name,
        health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _knight_profile(name: str = "Knight") -> UnitProfile:
    """Large-base model (170 mm oval base, like a Questoris Knight)."""
    return _basic_profile(
        name=name,
        health=24, save=3, toughness=10,
        base_diameter_mm=32,   # placeholder per _bc_model_radius_in convention
        base_width_mm=170, base_length_mm=109,
        unit_keywords=("VEHICLE", "WALKER", "TITANIC", "TOWERING"),
        oc=10,
    )


def _dense_army(name: str, size: int = 20,
                model_name: str = "Trooper") -> Army:
    """An army with `size` identical infantry models packed into a single squad.
    Dense enough that the default _deploy_line would produce many overlaps for
    large sizes on a narrow map."""
    a = Army(name)
    p = _basic_profile(name=model_name, base_diameter_mm=25)
    a.add_squad(p, size=size)
    return a


def _knight_army(name: str, count: int = 3) -> Army:
    """An army of large-base Knights — guaranteed overlaps with default spacing
    on a standard 44-wide map when count is large enough."""
    a = Army(name)
    for i in range(count):
        a.add_unit(_knight_profile(name=f"Knight_{i}"))
    return a


def _deploy_with_gate(a: Army, b: Army, *, gate_on: bool,
                      seed: int = 0) -> Battle:
    """Deploy armies with SWEG_DEPLOY_COLLISION set / unset. Returns the Battle
    after deployment + scout phase (positions are at their BattleStarted state)."""
    prev = os.environ.get("SWEG_DEPLOY_COLLISION")
    os.environ["SWEG_DEPLOY_COLLISION"] = "1" if gate_on else "0"
    try:
        random.seed(seed)
        b_obj = Battle(a, b)
        b_obj._assign_uids()
        b_obj._deploy_armies()
        return b_obj
    finally:
        if prev is None:
            os.environ.pop("SWEG_DEPLOY_COLLISION", None)
        else:
            os.environ["SWEG_DEPLOY_COLLISION"] = prev


def _count_overlaps(units: list) -> int:
    """Pairwise overlap count using the same radius the collision predicate uses."""
    count = 0
    for i, u in enumerate(units):
        ri = _bc_model_radius_in(u.profile)
        xi, yi = u.position
        for v in units[i + 1:]:
            rv = _bc_model_radius_in(v.profile)
            xv, yv = v.position
            pen = (ri + rv) - math.hypot(xi - xv, yi - yv)
            if pen > TOL_IN:
                count += 1
    return count


def _all_units(battle: Battle) -> list:
    """All on-board units from both armies (excluding reserves)."""
    return list(battle.a.units) + list(battle.b.units)


# ---------------------------------------------------------------------------
# 1. Gate-off identity
# ---------------------------------------------------------------------------

class GateOffIdentityTests(unittest.TestCase):
    """Gate OFF must produce byte-identical positions to the no-gate baseline."""

    def _positions_gate_off(self, seed: int) -> dict:
        a = _dense_army("A", size=5)
        b = _dense_army("B", size=5)
        battle = _deploy_with_gate(a, b, gate_on=False, seed=seed)
        return {u.uid: u.position for u in _all_units(battle)}

    def _positions_no_gate(self, seed: int) -> dict:
        """Reference: run with gate explicitly absent from the environment."""
        prev = os.environ.pop("SWEG_DEPLOY_COLLISION", None)
        try:
            random.seed(seed)
            a = _dense_army("A", size=5)
            b = _dense_army("B", size=5)
            battle = Battle(a, b)
            battle._assign_uids()
            battle._deploy_armies()
            return {u.uid: u.position for u in _all_units(battle)}
        finally:
            if prev is not None:
                os.environ["SWEG_DEPLOY_COLLISION"] = prev

    def test_seed_0_gate_off_matches_baseline(self):
        off = self._positions_gate_off(0)
        ref = self._positions_no_gate(0)
        self.assertEqual(off, ref,
            "Gate-OFF positions must be byte-identical to the unset baseline")

    def test_seed_7_gate_off_matches_baseline(self):
        off = self._positions_gate_off(7)
        ref = self._positions_no_gate(7)
        self.assertEqual(off, ref,
            "Gate-OFF positions must be byte-identical to the unset baseline")


# ---------------------------------------------------------------------------
# 2. Gate-on zero overlaps at BattleStarted
# ---------------------------------------------------------------------------

class GateOnNoOverlapTests(unittest.TestCase):
    """Gate ON must produce zero overlapping base pairs at BattleStarted."""

    def _assert_no_overlaps(self, a: Army, b: Army, seed: int = 0,
                            label: str = "") -> None:
        """Deploy with gate ON and assert zero pairwise overlaps."""
        battle = _deploy_with_gate(a, b, gate_on=True, seed=seed)
        units = _all_units(battle)
        n = _count_overlaps(units)
        self.assertEqual(n, 0,
            f"{label} seed={seed}: {n} overlapping base pairs remain at deployment")

    def test_small_infantry_armies_no_overlap(self):
        self._assert_no_overlaps(
            _dense_army("A", size=6),
            _dense_army("B", size=6),
            seed=0, label="small infantry")

    def test_dense_infantry_armies_no_overlap(self):
        """20-model squads on both sides — many squads packed into few slots."""
        self._assert_no_overlaps(
            _dense_army("A", size=15),
            _dense_army("B", size=15),
            seed=1, label="dense infantry")

    def test_knight_armies_no_overlap(self):
        """Large-base Knights — their wide radii mean default spacing overlaps."""
        self._assert_no_overlaps(
            _knight_army("A", count=4),
            _knight_army("B", count=4),
            seed=2, label="knight armies")

    def test_mixed_large_and_small_no_overlap(self):
        """Mix of large-base Knights and infantry in the same army."""
        a = Army("A")
        a.add_unit(_knight_profile("Knight_0"))
        a.add_unit(_knight_profile("Knight_1"))
        a.add_squad(_basic_profile("Trooper", base_diameter_mm=25), size=10)
        b = _dense_army("B", size=8)
        self._assert_no_overlaps(a, b, seed=3, label="mixed large+small")

    def test_multiple_seeds_no_overlap(self):
        """Verify across a range of seeds to catch ordering-dependent issues."""
        for seed in range(5):
            self._assert_no_overlaps(
                _dense_army("A", size=10),
                _dense_army("B", size=10),
                seed=seed, label=f"multi-seed army seed={seed}")

    def test_via_battlestarted_event_no_overlaps(self):
        """Verify using the BattleStarted event snapshot — positions that the
        replay renderer sees must also be overlap-free."""
        prev = os.environ.get("SWEG_DEPLOY_COLLISION")
        os.environ["SWEG_DEPLOY_COLLISION"] = "1"
        try:
            random.seed(0)
            a = _dense_army("A", size=8)
            b = _dense_army("B", size=8)
            log = EventLog()
            battle = Battle(a, b, subscribers=[log])
            battle.run()
            started = next(e for e in log.events if isinstance(e, BattleStarted))
            # Build a (x, y, radius) list from the snapshot (on-board units only;
            # reserves have sentinel position (-100, -100) and must be skipped).
            on_board = [u for u in started.units if u.position[0] >= 0]
            count = 0
            for i, u in enumerate(on_board):
                ri = u.base_diameter_mm / 25.4 / 2.0 if u.base_diameter_mm else 0.63
                # Use the same max-of-circle-and-wl radius as _bc_model_radius_in.
                w = u.base_width_mm or 0
                ln = u.base_length_mm or 0
                r_wl = ((w + ln) / 2.0 / 25.4) / 2.0 if (w and ln) else 0.0
                ri = max(ri, r_wl)
                xi, yi = u.position
                for v in on_board[i + 1:]:
                    rv = v.base_diameter_mm / 25.4 / 2.0 if v.base_diameter_mm else 0.63
                    w2 = v.base_width_mm or 0
                    ln2 = v.base_length_mm or 0
                    r_wl2 = ((w2 + ln2) / 2.0 / 25.4) / 2.0 if (w2 and ln2) else 0.0
                    rv = max(rv, r_wl2)
                    xv, yv = v.position
                    pen = (ri + rv) - math.hypot(xi - xv, yi - yv)
                    if pen > TOL_IN:
                        count += 1
            self.assertEqual(count, 0,
                f"BattleStarted snapshot has {count} overlapping pairs")
        finally:
            if prev is None:
                os.environ.pop("SWEG_DEPLOY_COLLISION", None)
            else:
                os.environ["SWEG_DEPLOY_COLLISION"] = prev


# ---------------------------------------------------------------------------
# 3. Map bounds
# ---------------------------------------------------------------------------

class MapBoundsTests(unittest.TestCase):
    """Gate ON: units must stay inside map bounds after relaxation."""

    def test_units_inside_map_bounds(self):
        """A dense army on a narrow map must not escape the map boundary."""
        prev = os.environ.get("SWEG_DEPLOY_COLLISION")
        os.environ["SWEG_DEPLOY_COLLISION"] = "1"
        try:
            random.seed(0)
            a = _dense_army("A", size=20)
            b = _dense_army("B", size=20)
            battle = Battle(a, b)
            battle._assign_uids()
            battle._deploy_armies()
            w = battle.map.width
            h = battle.map.height
            for u in _all_units(battle):
                r = _bc_model_radius_in(u.profile)
                x, y = u.position
                self.assertGreaterEqual(x, r - TOL_IN,
                    f"{u.profile.name} x={x:.3f} below left edge (radius={r:.3f})")
                self.assertLessEqual(x, w - r + TOL_IN,
                    f"{u.profile.name} x={x:.3f} beyond right edge (radius={r:.3f})")
                self.assertGreaterEqual(y, r - TOL_IN,
                    f"{u.profile.name} y={y:.3f} below bottom edge (radius={r:.3f})")
                self.assertLessEqual(y, h - r + TOL_IN,
                    f"{u.profile.name} y={y:.3f} beyond top edge (radius={r:.3f})")
        finally:
            if prev is None:
                os.environ.pop("SWEG_DEPLOY_COLLISION", None)
            else:
                os.environ["SWEG_DEPLOY_COLLISION"] = prev

    def test_non_infiltrators_inside_deployment_zones(self):
        """Standard (non-infiltrator) units must stay inside their army's
        deployment zone even after relaxation pushes them around."""
        prev = os.environ.get("SWEG_DEPLOY_COLLISION")
        os.environ["SWEG_DEPLOY_COLLISION"] = "1"
        try:
            random.seed(0)
            a = _dense_army("A", size=12)
            b = _dense_army("B", size=12)
            battle = Battle(a, b)
            battle._assign_uids()
            battle._deploy_armies()
            dz = battle.map.deployment_width
            h = battle.map.height
            # Army A deploys low-y (zone: [0, dz]); Army B high-y ([h-dz, h]).
            for u in battle.a.units:
                if u.embarked_in is not None or (u.profile.infiltrator or False):
                    continue
                _, y = u.position
                self.assertLessEqual(y, dz + TOL_IN,
                    f"Army A {u.profile.name} y={y:.3f} outside deployment zone [0, {dz}]")
            for u in battle.b.units:
                if u.embarked_in is not None or (u.profile.infiltrator or False):
                    continue
                _, y = u.position
                self.assertGreaterEqual(y, h - dz - TOL_IN,
                    f"Army B {u.profile.name} y={y:.3f} outside deployment zone [{h-dz}, {h}]")
        finally:
            if prev is None:
                os.environ.pop("SWEG_DEPLOY_COLLISION", None)
            else:
                os.environ["SWEG_DEPLOY_COLLISION"] = prev


# ---------------------------------------------------------------------------
# 4. Determinism
# ---------------------------------------------------------------------------

class DeterminismTests(unittest.TestCase):
    """Gate ON must be deterministic: same seed twice -> identical positions."""

    def _positions_gate_on(self, seed: int) -> dict:
        a = _dense_army("A", size=10)
        b = _dense_army("B", size=10)
        battle = _deploy_with_gate(a, b, gate_on=True, seed=seed)
        return {u.uid: u.position for u in _all_units(battle)}

    def test_same_seed_twice_identical(self):
        pos1 = self._positions_gate_on(42)
        pos2 = self._positions_gate_on(42)
        self.assertEqual(pos1, pos2,
            "Gate-ON deployment collision must be deterministic")

    def test_gate_on_differs_from_gate_off_when_overlaps_present(self):
        """When the default placement would produce overlaps, gate ON must
        produce different positions from gate OFF (it actually moves models).
        Use a large-base Knight army where overlaps are guaranteed."""
        a_on = _knight_army("A", count=6)
        b_on = _dense_army("B", size=4)
        battle_on = _deploy_with_gate(a_on, b_on, gate_on=True, seed=5)

        a_off = _knight_army("A", count=6)
        b_off = _dense_army("B", size=4)
        battle_off = _deploy_with_gate(a_off, b_off, gate_on=False, seed=5)

        pos_on = {u.uid: u.position for u in _all_units(battle_on)}
        pos_off = {u.uid: u.position for u in _all_units(battle_off)}

        # The gate-off placement has overlaps (Knights overlap on the default row).
        off_overlaps = _count_overlaps(list(battle_off.a.units) + list(battle_off.b.units))
        # Gate ON resolves those overlaps — positions must differ from gate OFF.
        if off_overlaps > 0:
            self.assertNotEqual(pos_on, pos_off,
                "Gate-ON must move models when overlaps exist in the gate-OFF placement")

    def test_knight_army_deterministic(self):
        """Determinism check for large-base units where relaxation does real work."""
        a1 = _knight_army("A", count=5)
        b1 = _dense_army("B", size=6)
        battle1 = _deploy_with_gate(a1, b1, gate_on=True, seed=99)
        pos1 = {u.uid: u.position for u in _all_units(battle1)}

        a2 = _knight_army("A", count=5)
        b2 = _dense_army("B", size=6)
        battle2 = _deploy_with_gate(a2, b2, gate_on=True, seed=99)
        pos2 = {u.uid: u.position for u in _all_units(battle2)}

        self.assertEqual(pos1, pos2,
            "Gate-ON Knight deployment must be deterministic across identical seeds")


if __name__ == "__main__":
    unittest.main()
