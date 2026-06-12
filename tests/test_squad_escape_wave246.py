"""Wave 246 lever 3 — squad-aware Fall Back escape (SWEG_SQUAD_ESCAPE).

The lone-unit Desperate Escape suppression in `_displace_fall_back_buys_something`
is correct for a single model (a lone Land Raider risking ~1/3 self-destruction to
buy one round of shooting is net-negative) but wrong for multi-model squads.

SwegHammer is one-Unit-per-model. For a five-model Hellblaster squad surrounded by
three or more enemies the expected losses on Desperate Escape are approximately
five models times two-sixths equals 1.67 models, recovering the whole squad's
shooting next round — a trade real players take. Treating every squad member as
an independent lone vehicle locks all five in place and lets melee armies farm them.

The gate `SWEG_SQUAD_ESCAPE` (default ON since the wave-246 close adoption;
SWEG_SQUAD_ESCAPE=0 is the kill-switch) lifts the lone-unit suppression
for squad members (squad_id >= 0) while leaving lone models (squad_id < 0) with
the conservative block. Rail conditions 1 and 2 of the "fall back only when
wasted" rail are untouched by the gate — a unit that holds or denies a marker
still STAYS regardless of squad membership.

Tests:
  (a) kill-switch inertness: with =0 the 3+ block still suppresses a squad
      member (pre-wave-246 behaviour recoverable); unset now means ON.
  (b) gate-on, squad member: engaged by 3+ enemies, surviving by staying, with no
      marker consequence and a clear destination → gets FALL_BACK.
  (c) gate-on, lone model (squad_id < 0): same setup → still suppressed by the
      conservative block.
  (d) gate-on, squad member whose removal WOULD flip a marker → still STAYS
      (rail condition 1 intact).
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from code.army import Army
from code.map import Map, Objective
from code.strategy import pick_move_intent
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def _squad_shooty_profile(oc: int = 1, health: float = 4.0) -> UnitProfile:
    """A high-damage-per-activation ranged profile that classify() tags SHOOTY.
    Represents a generic multi-model squad member (Hellblasters, Heavy Intercessors).
    """
    return UnitProfile(
        name="SquadGunner", health=health, damage=4, hit_probability=2 / 3,
        ap=-1, save=3, attacks=4, weapon_damage_per_shot=1.0,
        strength=4, toughness=4, range_inches=24,
        melee_attacks=0, move=6.0, oc=oc, faction="Test",
        unit_keywords=("INFANTRY",),
    )


def _weak_melee_profile(oc: int = 1) -> UnitProfile:
    """Token melee attacker — low expected wounds, so it does NOT destroy a
    four-wound target in one round. Used to set up 'survives by staying'."""
    return UnitProfile(
        name="Weakling", health=2, damage=0, hit_probability=0,
        attacks=0, range_inches=1,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3,
        move=6.0, oc=oc, faction="Foe",
        unit_keywords=("INFANTRY",),
    )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _make_army_with_unit(name: str, profile: UnitProfile, pos: tuple) -> tuple[Army, Unit]:
    """Build a one-unit army and return the army and its first unit.

    Note: add_unit() makes a ONE-model squad (squad_id >= 0, single member),
    so units built here are LONE MODELS under the alive-member-count predicate."""
    army = Army(name)
    army.add_unit(profile)
    u = army.units[0]
    u.uid = f"{name[0]}0"
    u.position = pos
    return army, u


def _make_army_with_squad(
    name: str, profile: UnitProfile, positions: list
) -> tuple[Army, Unit]:
    """Build an army whose units form ONE genuine multi-model squad (a shared
    squad_id via add_squad, len(positions) alive members) and return the army
    and the FIRST member, positioned at positions[0]."""
    army = Army(name)
    army.add_squad(profile, len(positions))
    for i, (u, pos) in enumerate(zip(army.units, positions)):
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army, army.units[0]


def _make_enemy_at(*positions: tuple, profile: UnitProfile = None) -> Army:
    """Build an enemy army with one weak melee unit at each given position."""
    p = profile or _weak_melee_profile()
    army = Army("Foe")
    for i, pos in enumerate(positions):
        army.add_unit(p)
        u = army.units[-1]
        u.uid = f"E{i}"
        u.position = pos
    return army


def _empty_map() -> Map:
    """60x60 board with a single objective far from the action so no unit is
    ever within its control radius — strips condition 1's marker logic out."""
    obj = Objective(name="Far", x=58.0, y=58.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _open_map() -> Map:
    """60x60 board with one objective at the centre (30, 30)."""
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


class _FakeBattle:
    """Minimal stand-in so strategy reads a live battle round via the army's
    `_battle_ref` back-reference (otherwise cur_round defaults to 1)."""
    def __init__(self, round_num: int = 2) -> None:
        self._current_round = round_num


def _set_round(*armies, round_num: int = 2) -> None:
    battle = _FakeBattle(round_num)
    for army in armies:
        army._battle_ref = battle


# Three enemies placed on one side so the away-vector is clear (a destination
# exists) but the unit is 'surrounded' (three or more in Engagement Range).
_THREE_ENEMY_POSITIONS = [(20.8, 19.6), (20.8, 20.0), (20.8, 20.4)]
_UNIT_POS = (20.0, 20.0)
# Second squad member: un-engaged, clear of the escape vector (which points
# away from the enemies, toward -x), close enough to be the same fight.
_SQUADMATE_POS = (20.0, 26.0)


# ---------------------------------------------------------------------------
# (a) Kill-switch inertness — with SWEG_SQUAD_ESCAPE=0 the 3+ block still
#     suppresses a squad member (the pre-wave-246 behaviour is recoverable)
# ---------------------------------------------------------------------------

class GateOffInertTest(unittest.TestCase):
    """With SWEG_SQUAD_ESCAPE=0 (the kill-switch; the default flipped to ON at
    the wave-246 close), the existing surroundedness block fires for squad
    members just as it did pre-wave-246 — the old behaviour stays recoverable."""

    def test_gate_off_squad_member_still_suppressed(self):
        # A genuine two-member squad in the same three-attacker surround
        # that blocks a lone unit. Kill-switch must restore the suppression.
        friendly, unit = _make_army_with_squad(
            "Friend", _squad_shooty_profile(health=4.0),
            [_UNIT_POS, _SQUADMATE_POS],
        )
        enemy = _make_enemy_at(*_THREE_ENEMY_POSITIONS)
        map_ = _empty_map()
        _set_round(friendly, enemy)

        # Ensure the kill-switch is explicitly engaged.
        with mock.patch.dict(os.environ, {"SWEG_SQUAD_ESCAPE": "0",
                                          "SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "Kill-switch (=0): a surrounded-but-surviving squad member must "
            "still be suppressed (byte-identical to pre-wave-246 behaviour).",
        )

    def test_gate_unset_squad_member_escapes(self):
        # Same setup with the gate environment variable absent entirely:
        # the default is now ON (wave-246 close flip), so the squad member
        # must receive FALL_BACK exactly as in the explicit =1 case.
        friendly, unit = _make_army_with_squad(
            "Friend", _squad_shooty_profile(health=4.0),
            [_UNIT_POS, _SQUADMATE_POS],
        )
        enemy = _make_enemy_at(*_THREE_ENEMY_POSITIONS)
        map_ = _empty_map()
        _set_round(friendly, enemy)

        env = {k: v for k, v in os.environ.items() if k != "SWEG_SQUAD_ESCAPE"}
        env["SWEG_DISPLACE_FALLBACK"] = "1"
        with mock.patch.dict(os.environ, env, clear=True):
            _, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertEqual(
            intent, "FALL_BACK",
            "Gate unset (default ON since the wave-246 close): a surrounded-"
            "but-surviving squad member must now escape.",
        )


# ---------------------------------------------------------------------------
# (b) Gate-on, squad member — gets FALL_BACK when surrounded but surviving
# ---------------------------------------------------------------------------

class GateOnSquadMemberTest(unittest.TestCase):
    """With SWEG_SQUAD_ESCAPE=1, a multi-model squad member engaged by 3+ enemies
    that would survive by staying, with no marker consequence and a clear
    destination, now receives the FALL_BACK intent."""

    def test_gate_on_squad_member_falls_back_when_surrounded(self):
        # A genuine two-member squad: the engaged member is in the three-
        # attacker surround, off any marker (condition 1 passes), surviving
        # the token attackers (condition 2 satisfied via pinned-gun-platform
        # arm), clear destination exists. Gate ON: the lone-unit suppression
        # is lifted for genuine multi-model squad members.
        friendly, unit = _make_army_with_squad(
            "Friend", _squad_shooty_profile(health=4.0),
            [_UNIT_POS, _SQUADMATE_POS],
        )
        enemy = _make_enemy_at(*_THREE_ENEMY_POSITIONS)
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_SQUAD_ESCAPE": "1",
                                          "SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertEqual(
            intent, "FALL_BACK",
            "Gate ON, squad member, 3+ enemies, survives by staying, off marker, "
            "clear destination: must get FALL_BACK (lone-unit suppression lifted).",
        )


# ---------------------------------------------------------------------------
# (c) Gate-on, lone model (squad_id < 0) — still suppressed
# ---------------------------------------------------------------------------

class GateOnLoneModelTest(unittest.TestCase):
    """With SWEG_SQUAD_ESCAPE=1, a lone model (squad_id < 0) in the identical
    setup retains the conservative block — the gate only lifts suppression for
    confirmed squad members."""

    def test_gate_on_lone_model_still_suppressed(self):
        # Identical three-attacker surround, same off-marker position, but
        # the unit has squad_id = -1 (lone model / unassigned). Gate ON must
        # NOT lift its suppression.
        # Note: add_unit calls add_squad internally and assigns squad_id >= 0,
        # so a lone model must be marked explicitly (squad_id = -1 means
        # "unassigned / not part of a multi-model squad" — see units.py __init__
        # and the squad_id docs there). Simulates a Vehicle or CHARACTER not
        # built via add_squad with a count > 1.
        friendly, unit = _make_army_with_unit(
            "Friend", _squad_shooty_profile(health=4.0), _UNIT_POS,
        )
        unit.squad_id = -1  # mark as lone / unassigned
        self.assertLess(
            unit.squad_id, 0,
            "Precondition: unit must have squad_id < 0 (lone model).",
        )
        enemy = _make_enemy_at(*_THREE_ENEMY_POSITIONS)
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_SQUAD_ESCAPE": "1",
                                          "SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "Gate ON but lone model (squad_id < 0): the conservative block must "
            "remain — lone models are never lifted by SWEG_SQUAD_ESCAPE.",
        )

    def test_gate_on_one_model_squad_still_suppressed(self):
        # The realistic lone-model case: add_unit() makes a ONE-model squad
        # with squad_id >= 0 (a lone Land Raider is built exactly this way).
        # The predicate counts ALIVE members sharing the id, so a single-
        # member squad is on the lone-model math and keeps the block. This is
        # the regression the wave-236 rail tests caught when the predicate
        # was squad_id >= 0 alone.
        friendly, unit = _make_army_with_unit(
            "Friend", _squad_shooty_profile(health=4.0), _UNIT_POS,
        )
        self.assertGreaterEqual(
            unit.squad_id, 0,
            "Precondition: add_unit assigns a real squad_id (one-model squad).",
        )
        enemy = _make_enemy_at(*_THREE_ENEMY_POSITIONS)
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_SQUAD_ESCAPE": "1",
                                          "SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "Gate ON but one-model squad (single alive member): the "
            "conservative block must remain.",
        )

    def test_gate_on_last_survivor_of_squad_suppressed(self):
        # A two-member squad whittled down to its last alive model is back on
        # the lone-model math: the dead member must not count.
        friendly, unit = _make_army_with_squad(
            "Friend", _squad_shooty_profile(health=4.0),
            [_UNIT_POS, _SQUADMATE_POS],
        )
        friendly.units[1].current_health = 0.0  # squadmate dead
        friendly._invalidate_alive_cache()
        enemy = _make_enemy_at(*_THREE_ENEMY_POSITIONS)
        map_ = _empty_map()
        _set_round(friendly, enemy)

        with mock.patch.dict(os.environ, {"SWEG_SQUAD_ESCAPE": "1",
                                          "SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(unit, friendly, enemy, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "Gate ON but the squad's last alive member: the conservative "
            "block must remain (dead members do not count).",
        )


# ---------------------------------------------------------------------------
# (d) Gate-on, squad member on a marker — rail condition 1 intact
# ---------------------------------------------------------------------------

class GateOnCondition1RailTest(unittest.TestCase):
    """Even with SWEG_SQUAD_ESCAPE=1 a squad member whose departure WOULD flip a
    marker (condition 1 fails) still STAYS. The 'fall back only when wasted' rail
    is fully intact — the gate only touches the Desperate Escape surroundedness
    block inside condition 3."""

    def test_gate_on_squad_member_holding_marker_stays(self):
        # A genuine two-member squad whose engaged member sits on the centre
        # objective and IS the swing: with it we hold (4 vs 3); without it the
        # enemy holds (0 vs 3). Condition 1 fails → STAY, regardless of the
        # gate. Three attackers ensure the surroundedness block would fire
        # without condition 1 intercepting first. The second squad member sits
        # well outside the 3-inch control radius so the marker sums are
        # untouched by its presence.
        friendly2, unit2 = _make_army_with_squad(
            "Friend2", _squad_shooty_profile(oc=4, health=4.0),
            [(30.0, 30.0), (36.5, 30.0)],
        )
        enemy2 = _make_enemy_at(
            (30.8, 29.6), (30.8, 30.0), (30.8, 30.4),
            profile=_weak_melee_profile(oc=1),
        )
        map_ = _open_map()
        _set_round(friendly2, enemy2)

        with mock.patch.dict(os.environ, {"SWEG_SQUAD_ESCAPE": "1",
                                          "SWEG_DISPLACE_FALLBACK": "1"}):
            _, intent = pick_move_intent(unit2, friendly2, enemy2, map_)
        self.assertNotEqual(
            intent, "FALL_BACK",
            "Gate ON, squad member, but departure flips the marker: condition 1 "
            "must dominate and the unit must STAY (tarpit rail intact).",
        )


if __name__ == "__main__":
    unittest.main()
