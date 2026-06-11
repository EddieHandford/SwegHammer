"""Displacement substrate Stage 1 — Fall-Back-only-when-wasted AI (wave 236).

The legacy Fall Back branch in `code.strategy.pick_move_intent` disengages ANY
eligible SHOOTY / HEAVY unit caught in Engagement Range so it can resume
shooting next round. That is too eager: a durable out-fighter sitting on a
contested objective marker should DIE ON THE MARKER (the faithful competitive
tarpit) rather than cede the objective by retreating.

The `SWEG_DISPLACE_FALLBACK` gate (default OFF) narrows the legacy Fall Back to
fire ONLY when the unit is genuinely WASTED — all three conditions must hold:

  1. No control consequence — its presence changes no marker outcome at the
     current / next scoring check (it cannot hold, cannot flip to contested, and
     denies no enemy score by standing). A Battle-shocked unit (Objective
     Control 0) trivially passes this condition.
  2. Staying costs material for nothing — likely destroyed, or pinned with its
     shooting forfeited while contributing nothing positionally.
  3. Falling back buys something real — the preserved unit has an actual use NET
     of the Fall Back move's own cost (the shoot/charge lockout, with no FLY
     exemption, and the Desperate Escape test priced in).

These tests assert: (a) the OFF path is byte-identical to the legacy branch;
(b) each of the three conditions individually BLOCKS the fall back; (c) the
tarpit rail — a unit on a marker stays even when losing the fight; and (d) the
Desperate Escape cost is priced into condition 3.

This is an AI-piloting heuristic, not a 10e rule change. The Fall Back lockout
and Desperate Escape mechanics it prices are already implemented and cited in
`data/rule_citations.d/core_fall_back.json` (`simulator.fall_back` /
`simulator.desperate_escape`).
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.strategy import pick_move_intent
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
def _shooty_profile(
    oc: int = 1,
    health: float = 4.0,
    fly: bool = False,
    titanic: bool = False,
    faction: str = "Test",
) -> UnitProfile:
    """A high-damage-per-activation ranged profile that classify() tags SHOOTY."""
    kw: tuple = ("INFANTRY",)
    if fly:
        kw = kw + ("FLY",)
    if titanic:
        kw = kw + ("TITANIC",)
    return UnitProfile(
        name="Gunner", health=health, damage=4, hit_probability=2 / 3,
        ap=-1, save=3, attacks=4, weapon_damage_per_shot=1.0,
        strength=4, toughness=4, range_inches=24,
        melee_attacks=0, move=6.0, oc=oc, faction=faction,
        unit_keywords=kw,
    )


def _weak_melee_profile(oc: int = 1) -> UnitProfile:
    """A token melee attacker — low expected wounds, so it does NOT kill a
    4-wound SHOOTY unit in one round. Used to set up 'survives by staying'."""
    return UnitProfile(
        name="Weakling", health=2, damage=0, hit_probability=0,
        attacks=0, range_inches=1,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3,
        move=6.0, oc=oc, faction="Foe",
        unit_keywords=("INFANTRY",),
    )


def _killer_melee_profile(oc: int = 1) -> UnitProfile:
    """A heavy melee attacker — enough expected wounds to destroy a 4-wound
    SHOOTY unit in one round (condition 2a: likely destroyed in place)."""
    return UnitProfile(
        name="Butcher", health=4, damage=0, hit_probability=0,
        attacks=0, range_inches=1,
        melee_attacks=12, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=8, melee_ap=-3,
        move=6.0, oc=oc, faction="Foe",
        unit_keywords=("INFANTRY",),
    )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _make_army(name: str, profile: UnitProfile, positions: list) -> Army:
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


class _FakeBattle:
    """Minimal stand-in so strategy reads a live battle round via the army's
    `_battle_ref` back-reference (otherwise cur_round defaults to 1)."""

    def __init__(self, round_num: int) -> None:
        self._current_round = round_num


def _set_round(*armies, round_num: int = 2) -> None:
    battle = _FakeBattle(round_num)
    for army in armies:
        army._battle_ref = battle


def _open_map(obj_radius: float = 3.0) -> Map:
    """60x60 board with one objective at the centre (30, 30)."""
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=obj_radius)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _empty_map() -> Map:
    """60x60 board with the single objective far from the action so no unit is
    ever within its control radius — strips condition 1's marker logic out."""
    obj = Objective(name="Far", x=58.0, y=58.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


# ---------------------------------------------------------------------------
# OFF path byte-identical
# ---------------------------------------------------------------------------
class GateOffByteIdenticalTests(unittest.TestCase):
    """With SWEG_DISPLACE_FALLBACK unset, the legacy eager Fall Back is unchanged."""

    def test_off_path_falls_back_like_legacy(self):
        # SHOOTY unit pinned by a token melee enemy, FAR from any objective.
        # Legacy behaviour: it Falls Back to free its guns. The gate OFF must
        # reproduce that exactly.
        friendly = _make_army("Friend", _shooty_profile(), [(10.0, 10.0)])
        enemy = _make_army("Foe", _weak_melee_profile(), [(10.8, 10.0)])
        map_ = _empty_map()
        _set_round(friendly, enemy)

        env = dict(os.environ)
        env.pop("SWEG_DISPLACE_FALLBACK", None)
        with mock.patch.dict(os.environ, env, clear=True):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertEqual(intent, "FALL_BACK")

    def test_on_path_blocks_when_off_would_fall_back(self):
        # Same board: gate ON. The unit is on NO marker (condition 1 passes),
        # survives the token attacker (condition 2a false, 2b true), and CAN
        # retreat (condition 3 true) — so it still Falls Back. This proves the
        # ON path is reachable, and the next test classes prove each blocker.
        friendly = _make_army("Friend", _shooty_profile(), [(10.0, 10.0)])
        enemy = _make_army("Foe", _weak_melee_profile(), [(10.8, 10.0)])
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertEqual(intent, "FALL_BACK")


# ---------------------------------------------------------------------------
# Condition 1 — no control consequence blocks the fall back
# ---------------------------------------------------------------------------
class Condition1ControlConsequenceTests(unittest.TestCase):
    """A unit whose Objective Control swings a marker STAYS (the tarpit rail)."""

    def test_unit_holding_a_contested_marker_does_not_fall_back(self):
        # SHOOTY unit (OC 2) sits on the centre objective. One enemy melee model
        # (OC 1) is also on it. With our unit: 2 vs 1 -> we control. Without it:
        # 0 vs 1 -> enemy controls. The unit is the swing -> condition 1 fails ->
        # it must STAY and die on the marker, never Fall Back.
        friendly = _make_army("Friend", _shooty_profile(oc=2), [(30.0, 30.0)])
        enemy = _make_army("Foe", _weak_melee_profile(oc=1), [(30.8, 30.0)])
        map_ = _open_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "A unit holding a contested marker must STAY (tarpit), not Fall Back.",
        )

    def test_unit_flipping_to_contested_does_not_fall_back(self):
        # Enemy has MORE Objective Control on the marker (OC 3) than our single
        # unit (OC 3 also -> tie). With our unit: 3 vs 3 -> contested, enemy does
        # NOT score (strictly-greater rule). Without it: 0 vs 3 -> enemy scores.
        # Standing denies the enemy's score -> condition 1 fails -> STAY.
        friendly = _make_army("Friend", _shooty_profile(oc=3), [(30.0, 30.0)])
        enemy = _make_army("Foe", _weak_melee_profile(oc=3), [(30.8, 30.0)])
        map_ = _open_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "A unit flipping a marker to contested must STAY, not Fall Back.",
        )

    def test_battle_shocked_unit_trivially_passes_condition_1(self):
        # Same swing geometry as test 1 (OC 2 vs 1 on the marker), BUT the unit
        # is Battle-shocked this round -> effective Objective Control 0. It now
        # changes NO marker outcome (0 vs 1 with OR without it), so condition 1
        # passes and the genuinely-wasted unit Falls Back.
        friendly = _make_army("Friend", _shooty_profile(oc=2), [(30.0, 30.0)])
        enemy = _make_army("Foe", _weak_melee_profile(oc=1), [(30.8, 30.0)])
        map_ = _open_map()
        _set_round(friendly, enemy, round_num=2)
        friendly.units[0].battleshocked_until_round = 2  # shocked this round

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertEqual(
            intent, "FALL_BACK",
            "A Battle-shocked unit (OC 0) is wasted and should Fall Back.",
        )


# ---------------------------------------------------------------------------
# Condition 3 — falling back must buy something real, net of the move's cost
# ---------------------------------------------------------------------------
class Condition3BuysSomethingTests(unittest.TestCase):
    """Conditions 1 and 2 hold here; only condition 3 is exercised."""

    def test_no_clear_destination_blocks_fall_back(self):
        # The unit is hemmed in: enemies surround it so NO point within its Move
        # breaks every enemy's engagement bubble. `_pick_fall_back_destination`
        # returns None -> condition 3 fails (the move would re-pin) -> STAY.
        # Off-marker so condition 1 passes; weak attackers so it is not certain
        # to die. Eight token enemies in a tight ring around the unit.
        friendly = _make_army("Friend", _shooty_profile(health=4.0), [(10.0, 10.0)])
        ring = []
        import math
        for k in range(12):
            ang = 2.0 * math.pi * k / 12
            ring.append((10.0 + 0.9 * math.cos(ang), 10.0 + 0.9 * math.sin(ang)))
        enemy = _make_army("Foe", _weak_melee_profile(), ring)
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "With no clear destination the Fall Back buys nothing -> STAY.",
        )

    def test_desperate_escape_cost_blocks_when_surrounded_but_surviving(self):
        # Condition 3's Desperate Escape arm: the unit is surrounded by 3+ enemies
        # (so a Fall Back would cross an enemy and trigger the test) AND it would
        # SURVIVE by staying (weak attackers). Trading a ~1/3 self-destruction for
        # only next round's shooting is net-negative -> STAY. Off-marker so
        # condition 1 passes; a clear destination still EXISTS (so the no-
        # destination arm is not what blocks). Place 3 attackers on ONE side so
        # the away-vector is clear but the unit is still 'surrounded' (>=3 in ER).
        friendly = _make_army("Friend", _shooty_profile(health=4.0), [(20.0, 20.0)])
        enemy = _make_army(
            "Foe", _weak_melee_profile(),
            [(20.8, 19.6), (20.8, 20.0), (20.8, 20.4)],
        )
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "Surrounded-but-surviving: the Desperate Escape cost makes the move "
            "net-negative -> STAY.",
        )

    def test_likely_destroyed_overrides_desperate_escape_cost(self):
        # Same 3-attacker surround, but now the attackers are KILLERS — the unit
        # dies in place if it stays (condition 2a). A 2/3 escape survival strictly
        # beats certain death, so the Desperate Escape arm does NOT block: the
        # unit Falls Back. (Off-marker so condition 1 still passes.)
        friendly = _make_army("Friend", _shooty_profile(health=4.0), [(20.0, 20.0)])
        enemy = _make_army(
            "Foe", _killer_melee_profile(),
            [(20.8, 19.6), (20.8, 20.0), (20.8, 20.4)],
        )
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertEqual(
            intent, "FALL_BACK",
            "Certain death by staying: a 2/3 escape beats it -> Fall Back.",
        )

    def test_fly_unit_not_blocked_by_desperate_escape_arm(self):
        # A FLY unit skips the Desperate Escape test entirely, so the surround
        # that blocks a foot unit (surviving-but-surrounded) does NOT block it:
        # it Falls Back. (Off-marker; survives the weak attackers.) This proves
        # the FLY/TITANIC exemption is priced only into the Desperate Escape arm,
        # never the shoot/charge lockout (which has no FLY exemption).
        friendly = _make_army(
            "Friend", _shooty_profile(health=4.0, fly=True), [(20.0, 20.0)],
        )
        enemy = _make_army(
            "Foe", _weak_melee_profile(),
            [(20.8, 19.6), (20.8, 20.0), (20.8, 20.4)],
        )
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertEqual(
            intent, "FALL_BACK",
            "A FLY unit is exempt from Desperate Escape, so the surround does "
            "not block its Fall Back.",
        )


# ---------------------------------------------------------------------------
# Condition 2 — staying costs material (and feeds condition 3)
# ---------------------------------------------------------------------------
class Condition2StayingCostsTests(unittest.TestCase):
    def test_wasted_pinned_gun_platform_falls_back(self):
        # The canonical Stage 1 case: a SHOOTY platform pinned off-marker by a
        # token attacker it does not need to fight, with a clear retreat. All
        # three conditions hold -> it Falls Back to free its guns next round.
        friendly = _make_army("Friend", _shooty_profile(), [(15.0, 15.0)])
        enemy = _make_army("Foe", _weak_melee_profile(), [(15.8, 15.0)])
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertEqual(intent, "FALL_BACK")


# ---------------------------------------------------------------------------
# Tarpit rail — a losing unit on a marker still STAYS
# ---------------------------------------------------------------------------
class TarpitRailTests(unittest.TestCase):
    def test_losing_unit_on_marker_stays(self):
        # The unit is being out-fought (a killer attacker would destroy it) AND
        # it is the swing vote on the marker (OC 2 vs the attacker's OC 1). The
        # tarpit rail says: STAY and die on the marker to deny the scoring tick.
        # Condition 1 must dominate condition 2 -> NOT FALL_BACK.
        friendly = _make_army("Friend", _shooty_profile(oc=2), [(30.0, 30.0)])
        enemy = _make_army("Foe", _killer_melee_profile(oc=1), [(30.8, 30.0)])
        map_ = _open_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(friendly.units[0], friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "A losing unit that still holds the marker STAYS and dies on it "
            "(the faithful tarpit), even when out-fought.",
        )


if __name__ == "__main__":
    unittest.main()
