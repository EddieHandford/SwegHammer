"""Tests for the Deep Strike arrival AI (#153).

The pre-#153 behaviour rolled a 66% per-unit per-round gate, which meant a
reserves pool of 4+ units trickled in over 3-4 rounds and got picked off
piecemeal. Real tournament deep-strike is a coordinated alpha-strike. The new
AI:

  * Round 2: hold unless the gunline is exposed OR an objective steal is open.
  * Round 3: drop ALL remaining DS units (alpha-strike window).
  * Round 4+: drop ALL remaining; lands cluster near contested objectives.

Plus mass-drop clustering: when 2+ units arrive together their landing
positions are within ~12" of each other.

These tests pin the strategy-layer decision (`decide_deepstrike_drops`,
`pick_mass_arrival_anchor`) and the simulator-side coordination
(`_arrive_from_reserves` + `_pick_arrival_point`).
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.map import Map, Objective, Terrain, TerrainType
from code.simulator import Battle
from code.strategy import (
    _has_objective_steal_open,
    _is_gunline_screened,
    decide_deepstrike_drops,
    pick_mass_arrival_anchor,
)
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile builders
# ---------------------------------------------------------------------------

def _ds_profile(name: str = "Terminator", **overrides) -> UnitProfile:
    """A deep-strike-flagged Marine-ish stand-in: melee/ranged dual, OC 2."""
    base = dict(
        name=name,
        health=3, damage=1, hit_probability=0.667,
        ap=2, save=2, strength=4, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=8, oc=2,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY", "TERMINATOR"),
        melee_attacks=3, melee_damage_per_shot=2.0,
        melee_hit_probability=0.667, melee_strength=8, melee_ap=2,
        deep_strike=True,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _shooty_profile(name: str = "Devastator", **overrides) -> UnitProfile:
    """A SHOOTY-classified backline gunner — high ranged DPA, no melee."""
    base = dict(
        name=name,
        health=2, damage=1, hit_probability=0.667,
        ap=2, save=3, strength=4, toughness=4,
        attacks=4, weapon_damage_per_shot=2.0, range_inches=48,
        leadership=7, oc=1,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.333, melee_strength=4, melee_ap=0,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _screen_profile(name: str = "Conscript", **overrides) -> UnitProfile:
    """A HORDE/SUPPORT screen unit — cheap bodies, low DPA, OC 2."""
    base = dict(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=6, oc=2,
        faction="Astra Militarum",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _add(army, profile, position=None):
    """Add a unit to `army` and return the Unit instance (Army.add_unit
    returns None). Optionally sets its position."""
    army.add_unit(profile)
    u = army.units[-1]
    if position is not None:
        u.position = position
    return u


def _flat_map(objectives=()):
    """Open 60x60 board with optional objectives."""
    return Map(
        name="open",
        width=60.0, height=60.0,
        terrain=(),
        objectives=tuple(objectives),
        deployment_width=12.0,
    )


# ---------------------------------------------------------------------------
# Strategy-layer unit tests
# ---------------------------------------------------------------------------

class DeepstrikeDropDecisionTests(unittest.TestCase):
    """Direct unit tests on `decide_deepstrike_drops` without involving a
    full Battle. Faster and pins the decision table tightly."""

    def setUp(self):
        random.seed(0)
        self.map = _flat_map([Objective("Centre", 30.0, 30.0)])

    def _setup(self, enemy_screened: bool):
        """Build an opponent with a SHOOTY backline, optionally screened."""
        opp = Army("Enemy")
        _add(opp, _shooty_profile("Devastator A"), (20.0, 50.0))
        _add(opp, _shooty_profile("Devastator B"), (40.0, 50.0))
        if enemy_screened:
            _add(opp, _screen_profile("Screen A"), (20.0, 45.0))
            _add(opp, _screen_profile("Screen B"), (40.0, 45.0))

        friendly = Army("Us")
        _add(friendly, _shooty_profile("Friend"), (30.0, 10.0))
        return opp, friendly

    def test_t2_can_hold_if_gunline_screened(self):
        """Round 2, gunline screened, no objective steal: hold."""
        opp, fr = self._setup(enemy_screened=True)
        # Friendly already controls Centre — remove the steal option so the
        # decision rests on the screen check.
        # (Friendly is at (30,10), 20" from objective — does NOT control it.)
        # Move objective close to friendly so we DO control it.
        self.map = _flat_map([Objective("ClaimedByUs", 30.0, 10.0)])
        waiting = [Battle.__new__(Battle).__class__]  # placeholder — we won't use it
        # Build real Unit instances via an Army (cleaner than poking internals).
        ds_army = Army("DSArmy")
        u1 = _add(ds_army, _ds_profile("Termie 1"))
        u2 = _add(ds_army, _ds_profile("Termie 2"))
        u3 = _add(ds_army, _ds_profile("Termie 3"))
        result = decide_deepstrike_drops(
            round_num=2, waiting_units=[u1, u2, u3],
            opponent=opp, friendly=fr, map_=self.map,
        )
        self.assertEqual(result, [],
            "Round 2 + screened gunline + no objective steal must hold all DS units")

    def test_t2_drops_if_gunline_exposed(self):
        """Round 2, gunline NOT screened: drop all (alpha strike)."""
        opp, fr = self._setup(enemy_screened=False)
        ds_army = Army("DSArmy")
        u1 = _add(ds_army, _ds_profile("Termie 1"))
        u2 = _add(ds_army, _ds_profile("Termie 2"))
        u3 = _add(ds_army, _ds_profile("Termie 3"))
        result = decide_deepstrike_drops(
            round_num=2, waiting_units=[u1, u2, u3],
            opponent=opp, friendly=fr, map_=self.map,
        )
        self.assertEqual(len(result), 3,
            f"Round 2 + exposed gunline must drop all DS units, got {len(result)}")

    def test_t3_drops_remaining_unless_objective_play(self):
        """Round 3: alpha-strike window forces all remaining units down."""
        opp, fr = self._setup(enemy_screened=True)
        ds_army = Army("DSArmy")
        u1 = _add(ds_army, _ds_profile("Termie 1"))
        u2 = _add(ds_army, _ds_profile("Termie 2"))
        result = decide_deepstrike_drops(
            round_num=3, waiting_units=[u1, u2],
            opponent=opp, friendly=fr, map_=self.map,
        )
        self.assertEqual(len(result), 2,
            "Round 3 alpha-strike window: all remaining DS units MUST drop")

    def test_t5_never_holds(self):
        """Round 5: never leave a DS unit in reserves — wasted points."""
        opp, fr = self._setup(enemy_screened=True)
        ds_army = Army("DSArmy")
        u1 = _add(ds_army, _ds_profile("Termie 1"))
        u2 = _add(ds_army, _ds_profile("Termie 2"))
        u3 = _add(ds_army, _ds_profile("Termie 3"))
        result = decide_deepstrike_drops(
            round_num=5, waiting_units=[u1, u2, u3],
            opponent=opp, friendly=fr, map_=self.map,
        )
        self.assertEqual(len(result), 3,
            "Round 5 must drop ALL remaining DS units")


# ---------------------------------------------------------------------------
# Battle-level integration tests
# ---------------------------------------------------------------------------

class DeepstrikeArrivalIntegrationTests(unittest.TestCase):
    """End-to-end tests: build a Battle, call _arrive_from_reserves at a
    chosen round_num, assert on the post-arrival state."""

    def _build_battle(self, n_ds: int, *, with_screens: bool, objectives):
        random.seed(0)
        ds_army = Army("Strike Force")
        for i in range(n_ds):
            ds_army.add_unit(_ds_profile(f"Termie {i}"))
        opp = Army("Defenders")
        # SHOOTY backline up north.
        _add(opp, _shooty_profile("Backline A"), (20.0, 50.0))
        _add(opp, _shooty_profile("Backline B"), (40.0, 50.0))
        if with_screens:
            _add(opp, _screen_profile("Screen A"), (20.0, 45.0))
            _add(opp, _screen_profile("Screen B"), (40.0, 45.0))
        battle = Battle(ds_army, opp, map_=_flat_map(objectives))
        battle._assign_uids()
        battle._deploy_armies()
        # _deploy_armies repositions non-DS opp units to deployment line. We
        # MUST reset them to our scenario positions AFTER deployment.
        for u in opp.units:
            name = u.profile.name
            if name == "Backline A":
                u.position = (20.0, 50.0)
            elif name == "Backline B":
                u.position = (40.0, 50.0)
            elif name == "Screen A":
                u.position = (20.0, 45.0)
            elif name == "Screen B":
                u.position = (40.0, 45.0)
        return battle, ds_army, opp

    def test_t4_objective_focus(self):
        """Round 4: a DS unit must land within control radius of a
        contested objective rather than blob onto an enemy at a non-objective
        location."""
        # One contested objective near board centre, no friendlies on it.
        obj = Objective("Centre", 30.0, 30.0, control_radius=3.0)
        battle, ds_army, opp = self._build_battle(
            n_ds=1, with_screens=False, objectives=[obj],
        )
        # Empty fresh-arrivals first (Battle.run() would do this for R>=2).
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=4)

        # The unit landed.
        self.assertEqual(len(ds_army.units), 1)
        u = ds_army.units[0]
        # Within 3" of the contested objective.
        dx = u.position[0] - obj.x
        dy = u.position[1] - obj.y
        d = (dx * dx + dy * dy) ** 0.5
        self.assertLessEqual(d, obj.control_radius + 0.5,
            f"T4 DS should land on contested objective ({obj.x},{obj.y}); "
            f"landed at {u.position} (d={d:.2f}\")")

    def test_mass_drop_clustering(self):
        """Round 3 forces reserved DS units down the same round. Their landing
        positions must lie within ~18" of each other (mass-drop cluster).
        Without #153 they could end up scattered across the board.

        With the 10e Reserves cap enforced (SWEG_DEPLOY_AI=1), a 4-unit
        all-deep-strike army caps at 2 units in reserves (floor(50% of 4) = 2)
        while 2 go on-board. Only the 2 reserved units arrive at Round 3.
        The clustering assertion covers only the arriving units.
        """
        import os as _os
        prev = _os.environ.get("SWEG_DEPLOY_AI")
        _os.environ["SWEG_DEPLOY_AI"] = "1"
        try:
            battle, ds_army, opp = self._build_battle(
                n_ds=4, with_screens=False, objectives=[],
            )
        finally:
            if prev is None:
                _os.environ.pop("SWEG_DEPLOY_AI", None)
            else:
                _os.environ["SWEG_DEPLOY_AI"] = prev

        # With the Reserves cap, only 2 of 4 DS units are reserved; 2 are on-board.
        n_reserved = len(battle._reserves[ds_army.name])
        self.assertGreaterEqual(n_reserved, 1,
            "At least 1 DS unit must be in reserves after capped deployment")

        battle._fresh_arrivals = set()
        arriving_before = set(id(u) for u in battle._reserves[ds_army.name])
        battle._arrive_from_reserves(round_num=3)

        # All reserved units must have arrived.
        self.assertEqual(len(battle._reserves[ds_army.name]), 0,
            "Round 3 must empty reserves (alpha-strike window)")

        # The arrived units (those whose id was in arriving_before) must cluster.
        arrived = [u for u in ds_army.units if id(u) in arriving_before]
        self.assertGreaterEqual(len(arrived), 1,
            "At least 1 unit must have arrived from reserves at Round 3")
        if len(arrived) >= 2:
            positions = [u.position for u in arrived]
            max_d = 0.0
            for i, p in enumerate(positions):
                for q in positions[i + 1:]:
                    d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
                    if d > max_d:
                        max_d = d
            self.assertLessEqual(max_d, 18.0,
                f"Mass-drop landings should cluster within ~18\" of each other "
                f"(allowing for >9\" enemy-gap forcing some spread); got max "
                f"pairwise d={max_d:.2f}\"")

    def test_t5_never_holds(self):
        """Round 5 must empty the DS reserves entirely (no held units)."""
        battle, ds_army, opp = self._build_battle(
            n_ds=3, with_screens=True, objectives=[],
        )
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=5)
        self.assertEqual(
            len(battle._reserves[ds_army.name]), 0,
            "Round 5 must leave nothing in reserves",
        )
        self.assertEqual(len(ds_army.units), 3)

    def test_t2_hold_keeps_reserves(self):
        """Round 2, screened opponent, no objective steal: units stay in
        reserves to alpha-strike later.

        With the 10e Reserves cap enforced (SWEG_DEPLOY_AI=1), a 4-unit army
        (3 DS + 1 HomeGuard) has units_cap = floor(50% of 4) = 2 and
        points_cap = 50% of total Lanchester-derived army points. Because each
        Terminator profile has substantial Lanchester value (~67 pts), only 1
        terminator fits within the points cap ("Termie 0", alphabetically first
        among the equal-OC candidates). Round 2 hold (screened + no steal) must
        leave that 1 reserved unit still in reserves after _arrive_from_reserves.
        """
        import os as _os
        prev = _os.environ.get("SWEG_DEPLOY_AI")
        _os.environ["SWEG_DEPLOY_AI"] = "1"
        try:
            random.seed(0)
            ds_army = Army("Strike Force")
            for i in range(3):
                ds_army.add_unit(_ds_profile(f"Termie {i}"))
            # Non-DS friendly to claim the objective so it's not a steal target.
            ds_army.add_unit(_screen_profile("HomeGuard"))
            opp = Army("Defenders")
            _add(opp, _shooty_profile("Backline A"), (20.0, 50.0))
            _add(opp, _screen_profile("Screen A"), (20.0, 45.0))
            _add(opp, _shooty_profile("Backline B"), (40.0, 50.0))
            _add(opp, _screen_profile("Screen B"), (40.0, 45.0))

            # Friendly HomeGuard sits on the deployment line at y~6; place
            # objective right there so the AI considers it claimed.
            obj = Objective("Home", 30.0, 6.0, control_radius=3.0)
            battle = Battle(ds_army, opp, map_=_flat_map([obj]))
            battle._assign_uids()
            battle._deploy_armies()
        finally:
            if prev is None:
                _os.environ.pop("SWEG_DEPLOY_AI", None)
            else:
                _os.environ["SWEG_DEPLOY_AI"] = prev

        # _deploy_armies repositions opp units to the deployment line; reset.
        for u in opp.units:
            nm = u.profile.name
            if nm == "Backline A":
                u.position = (20.0, 50.0)
            elif nm == "Screen A":
                u.position = (20.0, 45.0)
            elif nm == "Backline B":
                u.position = (40.0, 50.0)
            elif nm == "Screen B":
                u.position = (40.0, 45.0)
        # Force HomeGuard (now on-board) onto the objective deterministically.
        for u in ds_army.units:
            if u.profile.name == "HomeGuard":
                u.position = (30.0, 6.0)
                break

        # Snapshot reserves BEFORE running the arrival decision.
        # With the Reserves cap applied, the greedy selector fills R until BOTH
        # caps hold: units_cap = floor(50% of 4) = 2, points_cap = 50% of total
        # army points. The Lanchester-derived points for a Terminator profile
        # (health=3, oc=2) means only the first terminator fits within the
        # points cap (adding a second would exceed 50% of army points), so
        # exactly 1 DS unit ("Termie 0", alphabetically first among equal-OC
        # candidates) is in reserves after deployment.
        before_arrive = [u.profile.name for u in battle._reserves[ds_army.name]]
        self.assertGreaterEqual(len(before_arrive), 1,
            "At least 1 DS unit must be in reserves after capped deployment")
        self.assertIn("Termie 0", before_arrive,
            "Termie 0 (alphabetically first among equal-OC candidates) must be "
            "the cap-selected reserve unit")

        # Round 2 + screened gunline + no objective steal: the hold decision
        # must leave the reserved unit still in reserves (none arrive).
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=2)

        after_arrive = [u.profile.name for u in battle._reserves[ds_army.name]]
        self.assertEqual(
            sorted(after_arrive), sorted(before_arrive),
            "T2 + screened gunline + no objective steal: cap-selected DS unit "
            "must still be in reserves after Round 2 hold decision",
        )


# ---------------------------------------------------------------------------
# Helper-function unit tests (gunline-screen detector + anchor picker)
# ---------------------------------------------------------------------------

class StrategyHelperTests(unittest.TestCase):

    def test_gunline_screen_detected(self):
        random.seed(0)
        opp = Army("E")
        _add(opp, _shooty_profile("Gunner"), (30.0, 50.0))
        _add(opp, _screen_profile("Screen"), (30.0, 45.0))   # 5" — inside 9"
        self.assertTrue(_is_gunline_screened(opp))

    def test_gunline_naked_not_screened(self):
        random.seed(0)
        opp = Army("E")
        _add(opp, _shooty_profile("Gunner"), (30.0, 50.0))
        # No screener at all.
        self.assertFalse(_is_gunline_screened(opp))

    def test_anchor_picks_objective_at_t4(self):
        """T4 anchor must be the contested objective, not the heavy threat."""
        opp = Army("E")
        _add(opp, _shooty_profile("Tank", health=12, toughness=11), (10.0, 50.0))
        fr = Army("U")
        _add(fr, _screen_profile("F"), (30.0, 6.0))

        obj = Objective("Contested", 30.0, 30.0, control_radius=3.0)
        m = _flat_map([obj])
        ds = Army("D")
        u = _add(ds, _ds_profile("Terminator"))
        anchor = pick_mass_arrival_anchor(
            round_num=4, units_dropping=[u], opponent=opp, friendly=fr, map_=m,
        )
        self.assertEqual(anchor, (30.0, 30.0),
            f"T4 anchor must be the contested objective; got {anchor}")

    def test_anchor_picks_heavy_threat_at_t2(self):
        """T2 anchor must be the heavy enemy, not an objective."""
        opp = Army("E")
        heavy = _add(opp, _shooty_profile("Tank", health=12, toughness=11),
                     (10.0, 50.0))
        fr = Army("U")
        _add(fr, _screen_profile("F"), (30.0, 6.0))

        obj = Objective("Contested", 30.0, 30.0, control_radius=3.0)
        m = _flat_map([obj])
        ds = Army("D")
        u = _add(ds, _ds_profile("Terminator"))
        anchor = pick_mass_arrival_anchor(
            round_num=2, units_dropping=[u, u], opponent=opp, friendly=fr, map_=m,
        )
        # At T2 the anchor is the threat (Tank position), not the objective.
        self.assertEqual(anchor, heavy.position,
            f"T2 anchor must be the heavy threat; got {anchor}")


if __name__ == "__main__":
    unittest.main()
