"""Go To Ground — 10e universal core stratagem (env-gated SWEG_GTG).

Go To Ground lets the defending army spend 1 Command Point, just after an enemy
unit selects a friendly INFANTRY unit as a shooting target, to give that unit a
6+ invulnerable save and the Benefit of Cover until the end of the phase. Its
absence under-protected fragile board-control infantry, which is shot off the
board before reaching objectives.

This layer, env-gated ON, applies the buff via the per-Unit `go_to_ground_active`
flag (6++ at the save branch in Unit.attack, +1 save via in_cover in
Battle._do_shoot) when a targeted INFANTRY unit is under genuinely threatening
fire and the squad is worth a Command Point. The heuristic is even-handed
(INFANTRY keyword + model count + threat + Command Points only — no faction
awareness). Gate unset reproduces the baseline byte-for-byte.

Cited as `simulator.go_to_ground` (data/rule_citations.d/core_go_to_ground.json).
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import Unit, UnitProfile


def _fragile_infantry(name: str = "Gaunts") -> UnitProfile:
    """A fragile INFANTRY model: Toughness 3, 1 wound, 5+ save, no invuln."""
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
        range_inches=12,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _ap_gun(name: str = "Lascannon team", attacks: int = 6) -> UnitProfile:
    """A high-Strength, high-AP shooter that strips a fragile unit's armour
    save (so the 6++ from Go To Ground is the variable under test)."""
    return UnitProfile(
        name=name,
        health=2.0,
        damage=1.0,
        hit_probability=2 / 3,
        ap=-4,
        save=3,
        strength=9,
        toughness=4,
        attacks=attacks,
        weapon_damage_per_shot=1.0,
        range_inches=48,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


class GoToGroundSaveEffectTests(unittest.TestCase):
    """The transient flag improves the targeted model's effective save."""

    def test_six_plus_invuln_reduces_damage_from_high_ap(self):
        attacker = Unit(_ap_gun(attacks=12))
        # Without Go To Ground: AP-4 strips the 5+ save → ~all hits wound and slay.
        random.seed(20260602)
        n = 4000
        base_total = 0.0
        for _ in range(n):
            tgt = Unit(_fragile_infantry())
            tgt._current_health = 1.0
            base_total += attacker.attack(tgt, distance=24.0)
        # With Go To Ground: a 6+ invuln save is available even though AP-4
        # strips the armour → roughly 1/6 of otherwise-fatal wounds are saved.
        random.seed(20260602)
        gtg_total = 0.0
        for _ in range(n):
            tgt = Unit(_fragile_infantry())
            tgt._current_health = 1.0
            tgt.go_to_ground_active = True
            gtg_total += attacker.attack(tgt, distance=24.0)
        self.assertLess(
            gtg_total, base_total,
            f"Go To Ground 6++ should reduce damage: base={base_total:.0f} "
            f"gtg={gtg_total:.0f}",
        )


def _build_squad_army(name: str, profile: UnitProfile, n: int, cp: int):
    """Build an army holding one n-model squad (shared squad id) of `profile`."""
    army = Army(name)
    for _ in range(n):
        army.add_unit(profile)
    army.command_points = cp
    sid = 7
    for u in army.units:
        u.squad_id = sid
        u.army_ref = army
    return army


class GoToGroundDecisionTests(unittest.TestCase):
    """`_maybe_go_to_ground` spends the Command Point and sets the flag only
    when the gates pass; the OFF path is inert."""

    def _battle(self, defender, attacker_army):
        battle = Battle(defender, attacker_army, map_=Map("Test", 60.0, 44.0))
        battle._assign_uids()
        battle._current_round = 2
        return battle

    def test_triggers_on_threatened_infantry_squad_when_gate_on(self):
        os.environ["SWEG_GTG"] = "1"
        try:
            defender = _build_squad_army("Def", _fragile_infantry(), n=5, cp=3)
            atk = Army("Atk")
            atk.add_unit(_ap_gun(attacks=12))
            battle = self._battle(defender, atk)
            target = defender.units[0]
            shooter = atk.units[0]
            cp_before = defender.command_points
            battle._maybe_go_to_ground(defender, target, shooter)
            self.assertTrue(
                target.go_to_ground_active,
                "a threatened INFANTRY squad should go to ground",
            )
            self.assertEqual(defender.command_points, cp_before - 1)
            # The whole squad gets the buff.
            self.assertTrue(all(u.go_to_ground_active for u in defender.units))
        finally:
            os.environ.pop("SWEG_GTG", None)

    def test_no_op_when_gate_off(self):
        os.environ.pop("SWEG_GTG", None)
        defender = _build_squad_army("Def", _fragile_infantry(), n=5, cp=3)
        atk = Army("Atk")
        atk.add_unit(_ap_gun(attacks=12))
        battle = self._battle(defender, atk)
        battle._maybe_go_to_ground(defender, defender.units[0], atk.units[0])
        self.assertFalse(defender.units[0].go_to_ground_active)
        self.assertEqual(defender.command_points, 3)

    def test_no_op_on_non_infantry(self):
        os.environ["SWEG_GTG"] = "1"
        try:
            import dataclasses
            veh = dataclasses.replace(
                _fragile_infantry(), unit_keywords=("VEHICLE",)
            )
            defender = _build_squad_army("Def", veh, n=5, cp=3)
            atk = Army("Atk")
            atk.add_unit(_ap_gun(attacks=12))
            battle = self._battle(defender, atk)
            battle._maybe_go_to_ground(defender, defender.units[0], atk.units[0])
            self.assertFalse(defender.units[0].go_to_ground_active)
            self.assertEqual(defender.command_points, 3)
        finally:
            os.environ.pop("SWEG_GTG", None)

    def test_no_op_when_no_command_points(self):
        os.environ["SWEG_GTG"] = "1"
        try:
            defender = _build_squad_army("Def", _fragile_infantry(), n=5, cp=0)
            atk = Army("Atk")
            atk.add_unit(_ap_gun(attacks=12))
            battle = self._battle(defender, atk)
            battle._maybe_go_to_ground(defender, defender.units[0], atk.units[0])
            self.assertFalse(defender.units[0].go_to_ground_active)
        finally:
            os.environ.pop("SWEG_GTG", None)

    def test_no_op_on_light_fire(self):
        """Genuinely light fire (a single weak pistol shot that is unlikely to
        even kill the targeted model) does not justify the Command Point."""
        os.environ["SWEG_GTG"] = "1"
        try:
            import dataclasses
            weak = dataclasses.replace(
                _ap_gun(attacks=1), strength=3, ap=0,   # ~0.17 expected wounds
            )
            defender = _build_squad_army("Def", _fragile_infantry(), n=5, cp=3)
            atk = Army("Atk")
            atk.add_unit(weak)
            battle = self._battle(defender, atk)
            battle._maybe_go_to_ground(defender, defender.units[0], atk.units[0])
            self.assertFalse(defender.units[0].go_to_ground_active)
            self.assertEqual(defender.command_points, 3)
        finally:
            os.environ.pop("SWEG_GTG", None)


if __name__ == "__main__":
    unittest.main()
