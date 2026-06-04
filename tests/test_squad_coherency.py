"""Squad rebuild Stage B — mid-game Unit Coherency enforcement (gate SWEG_COHERE).

SwegHammer models one Unit instance per model, and the per-model move AI lets
each model chase its own intent, so a squad a human player would keep tight can
scatter — stragglers strand outside the 3" Objective Control band. Real 10e
forbids this: every model must end its move within 2" of a squadmate. Stage B's
`Battle._enforce_squad_coherency` runs after the Movement phase and pulls each
straggler back toward its squad centroid, spending only the move it has left.

These tests exercise the method directly (it is deterministic — no RNG):
a straggler is pulled in, a coherent squad is untouched, a lone model is exempt,
a model with no remaining move stays put, and Advanced / Fell-Back models are
skipped. Cited as `simulator.coherency_enforcement`.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle, COHERENCY_INCHES, _distance
from code.units import Unit, UnitProfile


def _trooper(name: str = "Trooper", move: float = 6.0) -> UnitProfile:
    return UnitProfile(
        name=name,
        health=1.0,
        damage=1.0,
        hit_probability=0.5,
        ap=0,
        save=5,
        strength=4,
        toughness=3,
        invuln_save=7,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        move=move,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _squad_army(n: int, squad_id: int = 7) -> Army:
    army = Army("Sq")
    for _ in range(n):
        army.add_unit(_trooper())
    for u in army.units:
        u.squad_id = squad_id
        u.army_ref = army
    return army


class SquadCoherencyTests(unittest.TestCase):
    def _battle(self, army: Army) -> Battle:
        other = Army("Foe")
        other.add_unit(_trooper("Foe"))
        battle = Battle(army, other, map_=Map("Test", 60.0, 44.0))
        battle._assign_uids()
        return battle

    def test_straggler_pulled_toward_squad(self):
        army = _squad_army(3)
        army.units[0].position = (10.0, 10.0)
        army.units[1].position = (11.0, 10.0)
        straggler = army.units[2]
        straggler.position = (25.0, 10.0)   # 14" from nearest squadmate
        battle = self._battle(army)

        before = _distance(
            straggler.position,
            min((u for u in army.units if u is not straggler),
                key=lambda u: _distance(straggler.position, u.position)).position,
        )
        # start == current → full 6" of move remaining
        start = {u.uid: u.position for u in army.units}
        battle._enforce_squad_coherency(army, start)

        after = _distance(
            straggler.position,
            min((u for u in army.units if u is not straggler),
                key=lambda u: _distance(straggler.position, u.position)).position,
        )
        self.assertLess(straggler.position[0], 25.0, "straggler should move toward squad")
        self.assertLess(after, before, "straggler should be closer to its squad")
        # moved at most its 6" Move allowance
        self.assertLessEqual(_distance(straggler.position, (25.0, 10.0)), 6.0 + 1e-9)

    def test_coherent_squad_untouched(self):
        army = _squad_army(3)
        army.units[0].position = (10.0, 10.0)
        army.units[1].position = (11.0, 10.0)
        army.units[2].position = (12.0, 10.0)   # all within 2"
        battle = self._battle(army)
        start = {u.uid: u.position for u in army.units}
        before = [u.position for u in army.units]
        battle._enforce_squad_coherency(army, start)
        self.assertEqual([u.position for u in army.units], before)

    def test_lone_model_exempt(self):
        army = _squad_army(1, squad_id=-1)   # lone model, no coherency need
        army.units[0].squad_id = -1
        army.units[0].position = (30.0, 30.0)
        battle = self._battle(army)
        start = {u.uid: u.position for u in army.units}
        battle._enforce_squad_coherency(army, start)
        self.assertEqual(army.units[0].position, (30.0, 30.0))

    def test_no_remaining_move_stays_put(self):
        army = _squad_army(3)
        army.units[0].position = (10.0, 10.0)
        army.units[1].position = (11.0, 10.0)
        straggler = army.units[2]
        straggler.position = (25.0, 10.0)
        battle = self._battle(army)
        # start far away → the straggler already spent its whole 6" move
        start = {u.uid: u.position for u in army.units}
        start[straggler.uid] = (18.0, 10.0)   # used 7" > 6" Move → no budget left
        battle._enforce_squad_coherency(army, start)
        self.assertEqual(straggler.position, (25.0, 10.0))

    def test_advanced_or_fell_back_skipped(self):
        army = _squad_army(3)
        army.units[0].position = (10.0, 10.0)
        army.units[1].position = (11.0, 10.0)
        straggler = army.units[2]
        straggler.position = (25.0, 10.0)
        battle = self._battle(army)
        battle._advanced_this_round.add(straggler.uid)   # special move pool
        start = {u.uid: u.position for u in army.units}
        battle._enforce_squad_coherency(army, start)
        self.assertEqual(straggler.position, (25.0, 10.0))
        # and a fell-back model is skipped too
        straggler2 = army.units[1]
        straggler2.position = (25.0, 20.0)
        straggler2.fell_back_this_round = True
        start = {u.uid: u.position for u in army.units}
        battle._enforce_squad_coherency(army, start)
        self.assertEqual(straggler2.position, (25.0, 20.0))


if __name__ == "__main__":
    unittest.main()
