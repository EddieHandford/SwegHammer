"""Displacement substrate Stage 2 — Charge-to-contest the durable holder (wave 237).

This is the OVER-pole half of the displacement substrate
(docs/DISPLACEMENT_SUBSTRATE_PLAN.md §5 Stage 2). An Imperial Knight parks
concentrated Objective Control on a marker and the body army never plays the
contest game back (Stage 0 measured an Imperial Knights signature of 24.25
uncontested-hold victory points against only 0.75 tarpit). The default charge
picker SUPPRESSES the faithful answer — a chaff body cannot crack a Knight, so
the #C2 "won't-crack" penalty downweights the charge and the AI closes on
something it can kill instead.

The `SWEG_DISPLACE_SWARM` gate (default OFF) directs affordable bodies to CHARGE
the marker held by a concentrated durable unit, putting models into Engagement
Range to contest its Objective Control. The charge is biased in
`code.strategy.pick_charge_target`, and only when ALL hold:

  * the target is a concentrated durable marker-holder (the Knight pattern —
    high toughness / large wound pool AND Objective Control >= 2);
  * the target is actually contesting an objective marker; and
  * the NO-SUICIDE rail passes — charging at least TIES the FULL STACKED
    Objective Control of EVERY defending model within the marker's control
    radius (a Knight plus its Armiger escort), never the lone holder. A tie
    suffices because the 10e scorer awards a marker only on strictly-greater
    Objective Control, so tying flips the hold to contested and denies the
    holder's scoring tick.

These tests assert: (a) the OFF path leaves the legacy charge pick unchanged;
(b) the gate-ON charge fires (the durable holder becomes the picked target) in a
constructed contest-winnable scenario; (c) the no-suicide rail — insufficient
swarm Objective Control versus the defending cluster means no contest charge;
and (d) full-cluster accounting — a supporting defender within marker range is
counted into the contest evaluation (its extra Objective Control pushes the
cluster out of reach, suppressing the charge that was winnable against the lone
holder).

This is an AI-piloting heuristic, not a 10e rule change. It uses only
already-cited mechanics (the charge, the Engagement-Range Objective-Control
contest, the strictly-greater scorer) and adds no durability / output /
Objective-Control knob and no horde-nerf — so it carries no rule citation of its
own (same class as the Ork / kite / tarpit biases).
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.strategy import pick_charge_target
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
def _swarm_body_profile(oc: int = 2) -> UnitProfile:
    """A cheap horde body: many weak melee attacks that CANNOT crack a durable
    brick (so the won't-crack penalty would normally suppress charging a Knight),
    but carries Objective Control to contest a marker."""
    return UnitProfile(
        name="Gaunt", health=1, damage=0, hit_probability=0,
        attacks=0, range_inches=1,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        move=6.0, oc=oc, faction="Tyranids",
        unit_keywords=("INFANTRY",),
    )


def _knight_profile(oc: int = 10) -> UnitProfile:
    """A concentrated durable holder (the melee Imperial Knight / Gallant
    pattern): very tough, huge wound pool, no melee a swarm body can dent, high
    Objective Control, but LOW ranged output — so the default charge picker, with
    the #C2 won't-crack penalty, AVOIDS it in favour of a crackable soft target.
    Stage 2 must overtake that suppression when the marker contest is winnable.

    (A low-ranged-output holder is deliberate: the gunline Knight's enormous
    ranged_value term would dominate the default charge score and make it the
    pick regardless of the won't-crack penalty, which is the wrong test fixture.
    The over-pole Knight that over-holds a marker is exactly the melee chassis
    that parks on the objective, so this is also the faithful case.)"""
    return UnitProfile(
        name="Knight", health=22, damage=1, hit_probability=2 / 3,
        ap=0, save=3, invuln_save=5, attacks=1, weapon_damage_per_shot=1.0,
        strength=4, toughness=12, range_inches=6,
        melee_attacks=4, melee_damage_per_shot=3.0,
        melee_hit_probability=2 / 3, melee_strength=14, melee_ap=-3,
        move=10.0, oc=oc, faction="Imperial Knights",
        unit_keywords=("VEHICLE", "TITANIC", "IMPERIAL KNIGHTS"),
    )


def _armiger_profile(oc: int = 8) -> UnitProfile:
    """A supporting durable defender (the Armiger escort): also durable and
    Objective-Control-bearing, sat on the SAME marker as the Knight. Its
    Objective Control stacks into the cluster the no-suicide rail must count."""
    return UnitProfile(
        name="Armiger", health=12, damage=1, hit_probability=2 / 3,
        ap=0, save=3, invuln_save=5, attacks=1, weapon_damage_per_shot=1.0,
        strength=4, toughness=10, range_inches=6,
        melee_attacks=3, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=8, melee_ap=-2,
        move=12.0, oc=oc, faction="Imperial Knights",
        unit_keywords=("VEHICLE", "IMPERIAL KNIGHTS"),
    )


def _crackable_chaff_profile(oc: int = 1) -> UnitProfile:
    """A soft enemy the swarm CAN crack (low toughness, 1 wound). The default
    charge picker prefers this over the un-crackable Knight; Stage 2 must
    overtake it when the Knight's marker contest is winnable."""
    return UnitProfile(
        name="SoftGuy", health=1, damage=1, hit_probability=0.5,
        ap=0, save=6, attacks=1, weapon_damage_per_shot=1.0,
        strength=3, toughness=3, range_inches=12,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        move=6.0, oc=oc, faction="Foe",
        unit_keywords=("INFANTRY",),
    )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _make_army(name: str, specs: list) -> Army:
    """Build an army from a list of (profile, position) pairs."""
    army = Army(name)
    for i, (profile, pos) in enumerate(specs):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


class _FakeBattle:
    """Minimal stand-in exposing the two attributes Stage 2 reads off the
    army's `_battle_ref`: the current round (Battle-shock window) and the map
    (objectives)."""

    def __init__(self, map_, round_num: int = 2) -> None:
        self.map = map_
        self._current_round = round_num


def _wire(friendly: Army, enemy: Army, map_, round_num: int = 2) -> None:
    """Give both armies a shared _battle_ref so pick_charge_target can reach the
    objectives and the live round through the attacker's army back-reference."""
    battle = _FakeBattle(map_, round_num)
    friendly._battle_ref = battle
    enemy._battle_ref = battle


def _marker_map() -> Map:
    """60x60 board with one objective at the centre (30, 30), control radius 3"."""
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


# ---------------------------------------------------------------------------
# (a) OFF path byte-identical
# ---------------------------------------------------------------------------
class GateOffByteIdenticalTests(unittest.TestCase):
    """With SWEG_DISPLACE_SWARM unset / "0", the legacy charge pick is unchanged:
    the swarm avoids the un-crackable Knight and picks the crackable soft target."""

    def _scenario(self):
        # Five swarm bodies near the marker (OC 2 each = 10) face a Knight (OC
        # 10) ON the marker plus a crackable soft enemy just off it. Both enemies
        # are valid charge candidates — since wave 241 Engagement Range is
        # measured base-edge to base-edge (`_er_gap`), so "valid candidate"
        # means a base-edge gap over 1" (centre over ~2.26" for two default
        # 32mm bases), not the old centre-1" rule. The swarm row sits at 2.5"
        # centre (gap 1.24") — clear of engagement, still inside the marker's
        # 3" control radius so its Objective Control counts for the rail.
        # Default picker: the Knight is won't-crack-suppressed, so the
        # crackable soft target wins.
        map_ = _marker_map()
        swarm = _make_army("Swarm", [
            (_swarm_body_profile(oc=2), (30.0 + 0.3 * k, 32.5)) for k in range(5)
        ])
        enemy = _make_army("Foe", [
            (_knight_profile(oc=10), (30.0, 30.0)),       # on the marker (gap 1.24")
            (_crackable_chaff_profile(oc=1), (30.0, 35.0)),  # off the marker (gap 1.24")
        ])
        _wire(swarm, enemy, map_)
        return swarm, enemy

    def test_off_path_picks_crackable_target(self):
        swarm, enemy = self._scenario()
        charger = swarm.units[0]
        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_SWARM": "0"}):
            target, _ = pick_charge_target(charger, enemy)
        self.assertIsNotNone(target)
        self.assertEqual(
            target.profile.name, "SoftGuy",
            "OFF path: the swarm avoids the un-crackable Knight and charges the "
            "crackable soft target (legacy behaviour).",
        )

    def test_unset_matches_explicit_off(self):
        # Leaving the variable entirely unset must reproduce the explicit-"0"
        # pick exactly (default-OFF byte-identical).
        swarm, enemy = self._scenario()
        charger = swarm.units[0]
        env = dict(os.environ)
        env.pop("SWEG_DISPLACE_SWARM", None)
        with mock.patch.dict(os.environ, env, clear=True):
            target, _ = pick_charge_target(charger, enemy)
        self.assertEqual(target.profile.name, "SoftGuy")


# ---------------------------------------------------------------------------
# (b) Gate-ON charge fires in a contest-winnable scenario
# ---------------------------------------------------------------------------
class GateOnContestWinnableTests(unittest.TestCase):
    """With the gate ON and the contest winnable, the swarm charges the Knight
    to contest its marker instead of the crackable soft target."""

    def test_on_path_picks_the_durable_holder(self):
        # Same board as the OFF scenario: five swarm bodies (OC 2 each) already
        # near the marker (2.5" centre — base-edge gap 1.24", clear of
        # engagement under the wave-241 measure, inside the 3" control
        # radius). Once one charges in, friendly Objective Control on the
        # marker (>= 10) at least ties the Knight's lone OC 10 -> winnable -> the
        # Stage 2 bonus promotes the Knight over the crackable soft target.
        map_ = _marker_map()
        swarm = _make_army("Swarm", [
            (_swarm_body_profile(oc=2), (30.0 + 0.3 * k, 32.5)) for k in range(5)
        ])
        enemy = _make_army("Foe", [
            (_knight_profile(oc=10), (30.0, 30.0)),
            (_crackable_chaff_profile(oc=1), (30.0, 35.0)),
        ])
        _wire(swarm, enemy, map_)
        charger = swarm.units[0]
        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_SWARM": "1"}):
            target, _ = pick_charge_target(charger, enemy)
        self.assertIsNotNone(target)
        self.assertEqual(
            target.profile.name, "Knight",
            "ON path, winnable contest: the swarm charges the Knight to contest "
            "its marker rather than the crackable soft target.",
        )


# ---------------------------------------------------------------------------
# (c) No-suicide rail — insufficient swarm Objective Control blocks the charge
# ---------------------------------------------------------------------------
class NoSuicideRailTests(unittest.TestCase):
    """If charging cannot even TIE the defending cluster's stacked Objective
    Control, the contest is unwinnable and the bonus does NOT fire — the swarm
    falls back to the legacy pick (the crackable soft target), never a suicidal
    feed into the Knight."""

    def test_insufficient_oc_does_not_charge_the_knight(self):
        # A LONE swarm body (OC 1) versus a Knight holding OC 10 alone. Even
        # after it lands, friendly OC on the marker = 1 < 10 -> cannot tie ->
        # rail blocks -> legacy pick (the crackable soft target) stands.
        # (Positions per the wave-241 base-edge Engagement Range: 2.5" centre
        # = gap 1.24", a valid charge candidate, not already engaged.)
        map_ = _marker_map()
        swarm = _make_army("Swarm", [
            (_swarm_body_profile(oc=1), (30.0, 32.5)),
        ])
        enemy = _make_army("Foe", [
            (_knight_profile(oc=10), (30.0, 30.0)),
            (_crackable_chaff_profile(oc=1), (30.0, 35.0)),
        ])
        _wire(swarm, enemy, map_)
        charger = swarm.units[0]
        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_SWARM": "1"}):
            target, _ = pick_charge_target(charger, enemy)
        self.assertIsNotNone(target)
        self.assertEqual(
            target.profile.name, "SoftGuy",
            "No-suicide rail: a lone body that cannot tie the Knight's OC must "
            "NOT charge it — the legacy crackable pick stands.",
        )


# ---------------------------------------------------------------------------
# (d) Full-cluster accounting — a supporting defender is counted in
# ---------------------------------------------------------------------------
class FullClusterAccountingTests(unittest.TestCase):
    """The contest is evaluated against the FULL stacked Objective Control of
    EVERY defending model within marker range — a Knight plus its Armiger escort,
    never the lone holder. The Armiger's extra Objective Control can push the
    cluster out of reach of a swarm that WOULD have tied the Knight alone."""

    def _swarm_and_enemy(self, with_armiger: bool):
        map_ = _marker_map()
        # Five swarm bodies (OC 2 each = 10) — exactly ties a lone Knight (OC 10).
        # (Positions per the wave-241 base-edge Engagement Range: 2.5" centre
        # = gap 1.24", valid charge candidates, inside the control radius.)
        swarm = _make_army("Swarm", [
            (_swarm_body_profile(oc=2), (30.0 + 0.3 * k, 32.5)) for k in range(5)
        ])
        enemy_specs = [
            (_knight_profile(oc=10), (30.0, 30.0)),
            (_crackable_chaff_profile(oc=1), (30.0, 35.0)),
        ]
        if with_armiger:
            # Armiger ON the same marker — its OC 8 stacks into the cluster
            # (total defending OC 18), which the swarm's 10 can no longer tie.
            enemy_specs.append((_armiger_profile(oc=8), (30.0, 28.5)))
        enemy = _make_army("Foe", enemy_specs)
        _wire(swarm, enemy, map_)
        return swarm, enemy

    def test_lone_knight_is_contestable(self):
        # Control: without the Armiger the swarm ties the Knight (10 vs 10) and
        # charges it — establishes the scenario IS winnable absent the supporter.
        swarm, enemy = self._swarm_and_enemy(with_armiger=False)
        charger = swarm.units[0]
        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_SWARM": "1"}):
            target, _ = pick_charge_target(charger, enemy)
        self.assertEqual(
            target.profile.name, "Knight",
            "Lone Knight (OC 10) is tied by the swarm's OC 10 -> contestable.",
        )

    def test_supporting_armiger_pushes_cluster_out_of_reach(self):
        # WITH the Armiger on the marker the defending cluster is OC 18, which
        # the swarm's OC 10 cannot tie. Counting the supporter (full-cluster
        # accounting) suppresses the contest charge -> legacy crackable pick.
        swarm, enemy = self._swarm_and_enemy(with_armiger=True)
        charger = swarm.units[0]
        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_SWARM": "1"}):
            target, _ = pick_charge_target(charger, enemy)
        self.assertEqual(
            target.profile.name, "SoftGuy",
            "Full-cluster accounting: the Armiger's stacked OC puts the cluster "
            "(18) beyond the swarm's reach (10) -> no contest charge.",
        )


if __name__ == "__main__":
    unittest.main()
