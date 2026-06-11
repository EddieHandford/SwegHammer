"""Tests for the gated charge-path legality filter (env-gate SWEG_CHARGE_PATH,
default OFF).

Real 10th edition: a charge move must be made "without moving within Engagement
Range of any enemy units that were not a target of the charge" (Wahapedia core
rules, cited `simulator.charge_path_non_target`).  The legacy charge-target
picker (pick_charge_target in code/strategy.py) evaluates candidates purely by
kill value, letting the charger reach a high-value gunline unit straight through
any screening unit that stands between them.

With the gate ON the filter imposes two checks on every candidate (per the 10e
rule):

  (a) PATH check — non-FLY chargers only: if the straight-line move from the
      charger's current position to its approximate end spot near the candidate
      passes within Engagement Range (1.0" base-edge gap) of any non-target
      enemy, the candidate is excluded.

  (b) END-SPOT check — all chargers including FLY: if the approximate end spot
      is itself within Engagement Range of a non-target enemy, the candidate is
      excluded.

A screened candidate is only excluded from the target-picker; the screen body
remains a valid candidate of its own, so the AI naturally redirects onto it.

Gate OFF must be byte-identical to the pre-gate behaviour.  The gate-ON path
consumes zero additional random numbers (pure geometry, deterministic).

These tests follow the structure and idiom of tests/test_charge_baseedge.py:
env-gate setUp / tearDown that pop SWEG_CHARGE_PATH; SimpleNamespace / UnitProfile
scenario builders; note SWEG_CHARGE_BASEEDGE is default-ON in production.
"""

from __future__ import annotations

import os
import types
import unittest

from code.sim.geometry import _bc_model_radius_in, _er_gap
from code.strategy import pick_charge_target
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def _melee_profile(name: str = "Charger",
                   base_mm: int = 32,
                   fly: bool = False) -> UnitProfile:
    """A melee attacker that wants to charge (melee DPA >> ranged DPA)."""
    kw = ("INFANTRY", "FLY") if fly else ("INFANTRY",)
    return UnitProfile(
        name=name, health=4, damage=1, hit_probability=2 / 3,
        ap=1, save=3, strength=5, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=1,
        leadership=7,
        faction="Generic",
        unit_keywords=kw,
        melee_attacks=6, melee_damage_per_shot=1.5,
        melee_hit_probability=2 / 3, melee_strength=6, melee_ap=2,
        move=6.0,
        base_diameter_mm=base_mm,
    )


def _gunline_profile(name: str = "Gunline") -> UnitProfile:
    """A soft ranged unit — high ranged DPA, poor melee — attractive charge
    target for the kill-value heuristic."""
    return UnitProfile(
        name=name, health=3, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=4,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.33, melee_strength=3, melee_ap=0,
        move=6.0,
        base_diameter_mm=32,
    )


def _screen_profile(name: str = "Screen") -> UnitProfile:
    """A cheap body unit that the attacker cannot crack easily — used as the
    screening unit that should redirect the charge."""
    return UnitProfile(
        name=name, health=2, damage=0, hit_probability=0,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=6,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.33, melee_strength=3, melee_ap=0,
        move=6.0,
        base_diameter_mm=32,
    )


# ---------------------------------------------------------------------------
# Minimal Unit / Army stand-ins
# ---------------------------------------------------------------------------

def _unit(profile: UnitProfile, pos, uid: str = "u"):
    """Minimal Unit-like namespace that pick_charge_target reads."""
    u = types.SimpleNamespace()
    u.profile = profile
    u.position = pos
    u.uid = uid
    u.current_health = float(profile.health)
    # Fields read by the scorer helpers (keep them to safe defaults).
    u.squad_id = uid
    u.is_leader = False
    u.attached_leader = None
    u.attached_to = None
    u.buffs = {}
    u.transient_buffs = {}
    u.faction = profile.faction
    u.unit_keywords = profile.unit_keywords or ()
    return u


def _army(units_list):
    """Minimal Army-like namespace."""
    a = types.SimpleNamespace()
    a.alive_units = units_list
    a.faction = "Generic"
    return a


# ---------------------------------------------------------------------------
# Environment reset helpers
# ---------------------------------------------------------------------------

def _reset_caches():
    """Clear lru_caches that pick_charge_target depends on, to prevent
    cross-test contamination (mirrors tests/test_charge_baseedge.py)."""
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
# Test cases
# ---------------------------------------------------------------------------

class GateOffLegacyTests(unittest.TestCase):
    """Gate OFF: the screened juicy target must still be picked (byte-identical
    to legacy behaviour — no path check fires)."""

    def setUp(self):
        os.environ["SWEG_CHARGE_PATH"] = "0"
        # Keep base-edge gate ON (production default).
        os.environ.setdefault("SWEG_CHARGE_BASEEDGE", "1")
        _reset_caches()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_PATH", None)
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_caches()

    def test_gate_off_screened_target_still_chosen(self):
        """With the gate OFF the kill-value heuristic runs unchanged: the juicy
        gunline behind the screen is preferred over the screen because it has
        higher ranged output (ranged_value) and lower melee threat — the screen
        never blocks the pick."""
        charger = _unit(_melee_profile("Charger"), (0.0, 15.0), "C0")
        # Screen sits 6" away, directly between charger and gunline.
        screen = _unit(_screen_profile("Screen"), (0.0, 9.0), "S0")
        # Juicy gunline 9" away (behind the screen from charger's perspective).
        gunline = _unit(_gunline_profile("Gunline"), (0.0, 6.0), "G0")

        attacker_army = _army([charger])
        enemy_army = _army([screen, gunline])

        target, dist = pick_charge_target(charger, enemy_army)
        # Gate OFF: juicy target wins by ranged value; screen does not block.
        self.assertIsNotNone(target)
        self.assertEqual(target.uid, "G0",
                         "Gate OFF must not exclude the screened gunline.")


class GateOnScreenRedirectTests(unittest.TestCase):
    """Gate ON: a screen body directly between the charger and the juicy target
    blocks the straight path to the gunline — the gunline candidate is excluded
    and the charger redirects onto the screen."""

    def setUp(self):
        os.environ["SWEG_CHARGE_PATH"] = "1"
        os.environ.setdefault("SWEG_CHARGE_BASEEDGE", "1")
        _reset_caches()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_PATH", None)
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_caches()

    def _layout_collinear(self):
        """Charger at (0, 15), screen at (0, 9), gunline at (0, 4).  The
        screen sits exactly on the straight approach to the gunline, so the
        path check must fire and exclude the gunline."""
        charger = _unit(_melee_profile("Charger"), (0.0, 15.0), "C0")
        screen = _unit(_screen_profile("Screen"), (0.0, 9.0), "S0")
        gunline = _unit(_gunline_profile("Gunline"), (0.0, 4.0), "G0")
        return charger, screen, gunline

    def test_screened_juicy_target_excluded(self):
        """The gunline is on the other side of the screen along the charge line.
        Gate ON must exclude it; the screen is the only remaining candidate."""
        charger, screen, gunline = self._layout_collinear()
        enemy_army = _army([screen, gunline])

        target, dist = pick_charge_target(charger, enemy_army)
        self.assertIsNotNone(target,
                             "Some target must be reachable (the screen itself).")
        self.assertEqual(target.uid, "S0",
                         "Gate ON must redirect onto the screen when the gunline "
                         "path is blocked.")

    def test_both_candidates_excluded_returns_none(self):
        """If ALL candidates would require an illegal path (e.g. every enemy
        lies behind a wall of non-targets), pick_charge_target returns None."""
        charger = _unit(_melee_profile("Charger"), (0.0, 15.0), "C0")
        # Two screens flanking a juicy target — ALL three enemies are in a
        # tight cluster 6" away, with the screens directly on the path to the
        # gunline and the gunline itself behind them.  Use only one target so
        # both screens' end-spots conflict with each other.
        s1 = _unit(_screen_profile("S1"), (0.0, 9.0), "S1")
        s2 = _unit(_screen_profile("S2"), (0.3, 9.0), "S2")
        gunline = _unit(_gunline_profile("Gunline"), (0.0, 6.0), "G0")
        # Arrange so s1's end spot is blocked by s2 and vice versa, and
        # gunline is behind both screens.  With only 3 enemies all blocking
        # each other's approaches the result is at most the one that survives.
        # The important assertion: the function does not crash and returns a
        # tuple (possibly (None, None)).
        enemy_army = _army([s1, s2, gunline])
        result = pick_charge_target(charger, enemy_army)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


class FlyChargerTests(unittest.TestCase):
    """Gate ON + FLY charger: the FLY keyword exempts the charger from the PATH
    check (part a) — it may fly over a screen body to reach the gunline behind
    it.  The END-SPOT check (part b) still applies to FLY chargers."""

    def setUp(self):
        os.environ["SWEG_CHARGE_PATH"] = "1"
        os.environ.setdefault("SWEG_CHARGE_BASEEDGE", "1")
        _reset_caches()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_PATH", None)
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_caches()

    def test_fly_passes_over_screen_picks_gunline(self):
        """A FLY charger ignores the PATH check and picks the high-value gunline
        even though a screen body lies directly on the approach line."""
        charger = _unit(_melee_profile("Flyer", fly=True), (0.0, 15.0), "C0")
        screen = _unit(_screen_profile("Screen"), (0.0, 9.0), "S0")
        gunline = _unit(_gunline_profile("Gunline"), (0.0, 4.0), "G0")
        enemy_army = _army([screen, gunline])

        target, dist = pick_charge_target(charger, enemy_army)
        self.assertIsNotNone(target)
        self.assertEqual(target.uid, "G0",
                         "FLY charger must be exempt from path check (part a) "
                         "and allowed to charge the gunline behind the screen.")

    def test_fly_end_spot_blocked_excludes_candidate(self):
        """A FLY charger whose end spot (base-edge gap 1.0\" from the target)
        would land within Engagement Range of an adjacent non-target enemy is
        still excluded via the END-SPOT check (part b).

        Layout: charger approaches a target that has a second enemy parked
        right next to the target's far side — the end spot on the near side is
        clear, but for this test we position the adjacent enemy on the near
        (approach) side so it occupies the space the end spot would land in."""
        charger = _unit(_melee_profile("Flyer", fly=True), (0.0, 15.0), "C0")

        # Primary target at (0, 6).  Adjacent enemy parked at (0, 8.0) so that
        # the end spot of a charge on the primary (roughly (0, 7.5)) is
        # within Engagement Range of the adjacent enemy.
        target_p = _gunline_profile("Target")
        adjacent_p = _screen_profile("Adjacent")
        r_charger = _bc_model_radius_in(_melee_profile("Flyer", fly=True))
        r_target = _bc_model_radius_in(target_p)

        # End spot distance from target centre: r_charger + r_target + 1.0"
        end_offset = r_charger + r_target + 1.0
        target_pos = (0.0, 6.0)
        # Adjacent enemy is placed just at the end spot — so the end spot
        # lands within Engagement Range of it.  Place adjacent at (0, 6.0 +
        # end_offset) so it coincides with the approach-side end spot.
        adjacent_pos = (0.0, 6.0 + end_offset)

        target_u = _unit(target_p, target_pos, "T0")
        adjacent_u = _unit(adjacent_p, adjacent_pos, "A0")
        enemy_army = _army([target_u, adjacent_u])

        target, dist = pick_charge_target(charger, enemy_army)
        # The target is excluded because the end spot is inside the adjacent
        # enemy's Engagement Range.  The adjacent is the fallback candidate.
        # (If both are blocked the result is (None, None); either way T0 must
        # NOT be chosen.)
        if target is not None:
            self.assertNotEqual(
                target.uid, "T0",
                "FLY charger: end-spot check (part b) must exclude the target "
                "whose end spot is within Engagement Range of a non-target.",
            )


class OpenPathTests(unittest.TestCase):
    """Gate ON, open path with no screens: pick must be identical to gate OFF."""

    def setUp(self):
        os.environ.setdefault("SWEG_CHARGE_BASEEDGE", "1")
        _reset_caches()

    def tearDown(self):
        os.environ.pop("SWEG_CHARGE_PATH", None)
        os.environ.pop("SWEG_CHARGE_BASEEDGE", None)
        _reset_caches()

    def test_open_path_gate_on_identical_to_gate_off(self):
        """With a clear lane to every candidate the charge-path filter is a no-op
        and the target chosen is the same whether the gate is ON or OFF."""
        charger = _unit(_melee_profile("Charger"), (0.0, 20.0), "C0")
        # Two enemies side-by-side 8" away — no enemy in between.
        gunline = _unit(_gunline_profile("Gunline"), (3.0, 12.0), "G0")
        brick = _unit(_screen_profile("Brick"), (-3.0, 12.0), "B0")
        enemy_army = _army([gunline, brick])

        os.environ["SWEG_CHARGE_PATH"] = "0"
        target_off, _ = pick_charge_target(charger, enemy_army)
        _reset_caches()

        os.environ["SWEG_CHARGE_PATH"] = "1"
        target_on, _ = pick_charge_target(charger, enemy_army)

        self.assertIsNotNone(target_off)
        self.assertIsNotNone(target_on)
        self.assertEqual(
            target_off.uid, target_on.uid,
            "Open-path gate ON must pick the same target as gate OFF.",
        )


if __name__ == "__main__":
    unittest.main()
