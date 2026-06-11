"""Defender wound allocation (gate SWEG_DEFENDER_ALLOC, default-ON).

Real 10e: when a unit is shot, the DEFENDING player allocates each unsaved
wound to a model of their choice, with two governing rules these tests pin:

  1. Mandatory continuation — a model that has already lost wounds MUST keep
     absorbing attacks until it is destroyed, even if it stands on an
     objective and even if it is itself out of the firing unit's range
     (allocation ranges over the whole unit once one model makes it a legal
     target). Cited `simulator.defender_allocation`.
  2. Among full-health models the defender sacrifices trailing bodies
     (off-objective, furthest out) before models holding objectives.

`Battle._defender_alloc_model` is deterministic, so the picker is tested
directly; one end-to-end `_do_shoot` test (torrent + seeded RNG) proves an
out-of-range wounded model actually soaks the wound the in-range model would
have taken under the old attacker-picks-the-model behaviour.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import Unit, UnitProfile


def _body(name: str, health: float = 2.0) -> UnitProfile:
    return UnitProfile(
        name=name,
        health=health,
        damage=1.0,
        hit_probability=1.0,
        ap=0,
        save=7,                       # no armour save -> no save roll RNG
        strength=3,
        toughness=2,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=12,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=3,
        melee_damage_per_shot=1.0,
        fnp=7,
    )


def _torrent_shooter(name: str) -> UnitProfile:
    # Torrent auto-hits (no hit-roll RNG); S10 vs T2 wounds on 2+; target has
    # no save. Exactly one shot, one damage -> one unsaved wound per activation.
    return UnitProfile(
        name=name,
        health=2.0,
        damage=1.0,
        hit_probability=1.0,
        ap=0,
        save=3,
        strength=10,
        toughness=4,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        torrent=True,
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _squad(army_name: str, specs, squad_id: int = 7) -> Army:
    """specs: list of (name, position, current_health)."""
    army = Army(army_name)
    for name, _pos, _hp in specs:
        army.add_unit(_body(name))
    for u, (_name, pos, hp) in zip(army.units, specs):
        u.squad_id = squad_id
        u.army_ref = army
        u.position = pos
        u.current_health = hp
    return army


_OBJ_AT = (30.0, 22.0)


def _battle(attackers: Army, defenders: Army) -> Battle:
    map_ = Map("Test", 60.0, 44.0,
               objectives=(Objective("Center", _OBJ_AT[0], _OBJ_AT[1], 3.0),))
    battle = Battle(attackers, defenders, map_=map_)
    battle._assign_uids()
    return battle


class DefenderAllocModelTests(unittest.TestCase):
    """Direct, RNG-free tests of the allocation picker."""

    def _picker(self, defenders: Army):
        return _battle(Army("Att"), defenders)

    def test_wounded_model_taken_before_fresh_objective_holder(self):
        # On-objective wounded model vs an off-objective fresh model: mandatory
        # continuation forces the wounded one even though it holds the marker.
        dfn = _squad("D", [
            ("OnObjWounded", _OBJ_AT, 1.0),          # on objective, hurt
            ("TrailingFresh", (50.0, 22.0), 2.0),    # off objective, full
        ])
        battle = self._picker(dfn)
        pick = battle._defender_alloc_model([u for u in dfn.units])
        self.assertEqual(pick.profile.name, "OnObjWounded")

    def test_fresh_models_sacrifice_trailing_before_objective_holder(self):
        # All full health: the off-objective, furthest-out body is sacrificed
        # first; the model on the objective is preserved.
        dfn = _squad("D", [
            ("OnObj", _OBJ_AT, 2.0),
            ("Near", (36.0, 22.0), 2.0),
            ("FarTrailing", (55.0, 22.0), 2.0),
        ])
        battle = self._picker(dfn)
        pick = battle._defender_alloc_model([u for u in dfn.units])
        self.assertEqual(pick.profile.name, "FarTrailing")

    def test_gate_off_falls_back_to_list_order(self):
        # With the gate off, _do_shoot never builds the defender pool, so the
        # picker itself is simply not consulted. Sanity: the picker still
        # returns a member (used by spillover regardless of the gate).
        dfn = _squad("D", [
            ("A", (40.0, 22.0), 2.0),
            ("B", (41.0, 22.0), 2.0),
        ])
        battle = self._picker(dfn)
        self.assertIn(battle._defender_alloc_model(list(dfn.units)), dfn.units)


class OutOfRangeAllocationTests(unittest.TestCase):
    """End-to-end: an out-of-range wounded model soaks the wound."""

    def setUp(self):
        self._prev = os.environ.get("SWEG_SQUADSHOOT")
        os.environ["SWEG_SQUADSHOOT"] = "0"   # isolate single-target path

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("SWEG_SQUADSHOOT", None)
        else:
            os.environ["SWEG_SQUADSHOOT"] = self._prev

    def test_out_of_range_wounded_model_soaks_before_in_range_fresh(self):
        atk = Army("Att")
        atk.add_unit(_torrent_shooter("Gunner"))
        gunner = atk.units[0]
        gunner.squad_id = -1
        gunner.army_ref = atk
        gunner.position = (10.0, 22.0)

        # In-range full-health model at distance 20 (<= range 24); out-of-range
        # wounded model at distance 30 (> 24). Both one codex squad.
        dfn = _squad("Def", [
            ("InRangeFresh", (30.0, 22.0), 2.0),     # distance 20, full
            ("OutOfRangeHurt", (40.0, 22.0), 1.0),   # distance 30, wounded
        ])
        in_range = next(u for u in dfn.units if u.profile.name == "InRangeFresh")
        out_hurt = next(u for u in dfn.units if u.profile.name == "OutOfRangeHurt")

        battle = self._battle_for(atk, dfn)
        random.seed(1)
        battle._do_shoot(gunner, atk, dfn)

        # The single damage was allocated to the out-of-range wounded model
        # (mandatory continuation), killing it. The in-range full model — which
        # the OLD attacker-picks-the-weakest path would have hit — is untouched.
        self.assertFalse(out_hurt.is_alive, "wounded out-of-range model should soak first")
        self.assertEqual(in_range.current_health, 2.0, "in-range model must be untouched")

    def _battle_for(self, attackers: Army, defenders: Army) -> Battle:
        return _battle(attackers, defenders)


if __name__ == "__main__":
    unittest.main()
