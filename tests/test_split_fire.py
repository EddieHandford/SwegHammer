"""Squad rebuild Stage D — unit-orchestrated split-fire (gate SWEG_SQUADSHOOT).

`Battle._plan_squad_fire` computes a unit-level fire plan once on a squad's first
firing model: anti-armour models concentrate on the nominated focus brick, the
rest split greedily across enemies (each takes the lowest-effective-health target
it can still hurt that is not yet lethally committed) so the squad removes more
enemy units instead of over-killing one. These tests drive the planner directly
(it is deterministic and gate-independent; the gate is checked at the _do_shoot
call site, with the OFF path leaving the plan empty and unread). Cited
`simulator.split_fire`.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import Unit, UnitProfile


def _shooter(name: str) -> UnitProfile:
    # 3 ranged shots, always hit, Strength 5 vs Toughness 3, AP-2: kills a
    # 1-wound chaff model handily (~2 expected wounds), so one model is lethal.
    return UnitProfile(
        name=name,
        health=1.0,
        damage=1.0,
        hit_probability=1.0,
        ap=-2,
        save=3,
        strength=5,
        toughness=3,
        attacks=3,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _chaff(name: str) -> UnitProfile:
    return UnitProfile(
        name=name,
        health=1.0,
        damage=1.0,
        hit_probability=0.5,
        ap=0,
        save=6,
        strength=3,
        toughness=3,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=12,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=3,
        melee_damage_per_shot=1.0,
    )


def _squad(n: int, profile_factory, squad_id: int = 3) -> Army:
    army = Army("Shooters")
    for i in range(n):
        army.add_unit(profile_factory(f"S{i}"))
    for u in army.units:
        u.squad_id = squad_id
        u.army_ref = army
    return army


class SplitFireTests(unittest.TestCase):
    def _battle(self, attackers: Army, defenders: Army) -> Battle:
        battle = Battle(attackers, defenders, map_=Map("Test", 60.0, 44.0))
        battle._assign_uids()
        return battle

    def test_two_shooters_split_across_two_chaff(self):
        atk = _squad(2, _shooter)
        for u in atk.units:
            u.position = (10.0, 10.0)
        dfn = Army("Chaff")
        dfn.add_unit(_chaff("A"))
        dfn.add_unit(_chaff("B"))
        for i, u in enumerate(dfn.units):
            u.position = (20.0 + i, 10.0)
        battle = self._battle(atk, dfn)

        battle._plan_squad_fire(atk.units[0], atk, dfn)
        targets = {atk.units[0].uid: battle._squad_fire_plan.get(atk.units[0].uid),
                   atk.units[1].uid: battle._squad_fire_plan.get(atk.units[1].uid)}
        self.assertIsNotNone(targets[atk.units[0].uid])
        self.assertIsNotNone(targets[atk.units[1].uid])
        # The whole point: the two lethal shooters split, they do not both pile
        # onto one chaff unit and waste the second model's fire.
        self.assertNotEqual(
            targets[atk.units[0].uid].uid, targets[atk.units[1].uid].uid,
            "Two lethal shooters should split across the two chaff units.",
        )

    def test_single_enemy_no_split_possible(self):
        atk = _squad(2, _shooter)
        for u in atk.units:
            u.position = (10.0, 10.0)
        dfn = Army("Chaff")
        dfn.add_unit(_chaff("only"))
        dfn.units[0].position = (20.0, 10.0)
        battle = self._battle(atk, dfn)

        battle._plan_squad_fire(atk.units[0], atk, dfn)
        only_uid = dfn.units[0].uid
        # Both models can only hurt the one enemy: the first commits lethal fire,
        # the second finds nothing un-committed and is left unassigned (it falls
        # back to its per-model pick in _do_shoot).
        self.assertEqual(battle._squad_fire_plan.get(atk.units[0].uid).uid, only_uid)
        self.assertIsNone(battle._squad_fire_plan.get(atk.units[1].uid))

    def test_no_enemies_is_noop(self):
        atk = _squad(2, _shooter)
        dfn = Army("Empty")
        dfn.add_unit(_chaff("dead"))
        dfn.units[0].current_health = 0.0   # not alive
        battle = self._battle(atk, dfn)
        battle._plan_squad_fire(atk.units[0], atk, dfn)
        self.assertEqual(battle._squad_fire_plan, {})


if __name__ == "__main__":
    unittest.main()
