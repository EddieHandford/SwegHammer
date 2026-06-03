"""Tests for Belisarius Cawl's "Invocation of Machine Vengeance" Canticle
(Wave 148), a per-target designation mechanic that mirrors the Adeptus
Astartes Oath of Moment.

At the start of each Command phase, while a Belisarius Cawl model is alive in
the army, the Adeptus Mechanicus player designates one enemy unit as the
Machine Vengeance target; until the start of the next Command phase, every
friendly ADEPTUS MECHANICUS attack against that unit re-rolls the Hit roll.
Cited as `simulator.machine_vengeance`.

These tests assert the Command-phase designation:
  - it IS set (to an enemy uid) when a Belisarius Cawl model is alive in an
    Adeptus Mechanicus army; and
  - it is NOT set when no Belisarius Cawl is present (a plain Adeptus
    Mechanicus army that does not field Cawl never designates).
The re-roll application itself rides the same `att_reroll_all_hits` plumbing
as Oath of Moment (already covered by tests/test_marines.py).
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _admech_profile(
    name: str = "Skitarii Ranger",
    points: float = 100.0,
    health: int = 2,
) -> UnitProfile:
    """A generic Adeptus Mechanicus stand-in (no Cawl). Faction-tagged so the
    Machine Vengeance faction gate fires; the per-stat values are immaterial to
    the designation logic, which only reads faction + alive state. `health` is
    parameterised so a durable Cawl can survive into round 2 for the reset
    test."""
    return UnitProfile(
        name=name,
        health=health, damage=1, hit_probability=2 / 3,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=6,
        faction="Adeptus Mechanicus",
        points_override=float(points),
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _cawl_profile(points: float = 165.0, health: int = 40) -> UnitProfile:
    """Belisarius Cawl stand-in — the name substring is what
    _pick_machine_vengeance_target's alive-gate matches on (mirrors how
    leaders are identified by name in code/leaders.py). High default health so
    he survives the round and keeps the designation gate live (the real Cawl is
    a tough 9-wound character)."""
    return _admech_profile(name="Belisarius Cawl", points=points, health=health)


def _enemy_profile(
    name: str = "Cultist", points: float = 50.0, health: int = 1,
) -> UnitProfile:
    """Non-AdMech target unit. `health` is parameterised so durable enemies
    can be built that survive a full combat round (needed by the across-rounds
    reset test, where an enemy must still be alive at the start of round 2)."""
    return UnitProfile(
        name=name,
        health=health, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7,
        faction="Chaos Space Marines",
        points_override=float(points),
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )


class MachineVengeanceTargetPickerTests(unittest.TestCase):
    """Battle._pick_machine_vengeance_target sets
    army.machine_vengeance_target_uid at the start of every Command phase —
    but ONLY while a Belisarius Cawl model is alive in an Adeptus Mechanicus
    army."""

    def test_target_designated_when_cawl_alive(self):
        random.seed(0)
        a = Army("AdMech")
        a.add_unit(_cawl_profile())
        a.add_unit(_admech_profile())
        b = Army("Enemy")
        # Durable enemies (many wounds) so they remain alive through the round —
        # the designation is read off the LIVE board at the START of the Command
        # phase, but combat then resolves, so we snapshot the expected target
        # and the enemy uid set BEFORE running the round.
        b.add_unit(_enemy_profile(name="Cheap", points=50, health=12))
        b.add_unit(_enemy_profile(name="Expensive", points=300, health=12))
        battle = Battle(a, b)
        battle._assign_uids()
        enemy_uids = {u.uid for u in b.alive_units}
        # Heuristic mirrors Oath: at full health (round 1) it picks the
        # highest-points enemy.
        expected = max(b.alive_units, key=lambda u: u.profile.points_cost)
        battle._run_round(1)
        # A Machine Vengeance target must be designated, to one of the enemy
        # units that was alive at designation time.
        self.assertIsNotNone(a.machine_vengeance_target_uid)
        self.assertIn(a.machine_vengeance_target_uid, enemy_uids)
        self.assertEqual(a.machine_vengeance_target_uid, expected.uid)
        # The enemy side has no AdMech / Cawl, so it never designates.
        self.assertIsNone(b.machine_vengeance_target_uid)

    def test_no_target_without_cawl(self):
        """A plain Adeptus Mechanicus army that does NOT field Belisarius Cawl
        never designates a Machine Vengeance target — the Canticle is Cawl's
        datasheet ability."""
        random.seed(0)
        a = Army("AdMech (no Cawl)")
        a.add_unit(_admech_profile(name="Skitarii Ranger"))
        a.add_unit(_admech_profile(name="Kataphron Breacher"))
        b = Army("Enemy")
        b.add_unit(_enemy_profile(points=200))
        battle = Battle(a, b)
        battle._assign_uids()
        battle._run_round(1)
        self.assertIsNone(a.machine_vengeance_target_uid)

    def test_target_reset_each_command_phase(self):
        """machine_vengeance_target_uid is cleared at the top of every Command
        phase, so a stale uid never leaks across rounds. Cawl and the enemy are
        given enough wounds to survive into round 2 (the designation only
        re-fires while a Cawl model is alive AND an enemy remains)."""
        random.seed(0)
        a = Army("AdMech")
        a.add_unit(_cawl_profile(points=165.0))
        b = Army("Enemy")
        b.add_unit(_enemy_profile(points=200, health=40))
        battle = Battle(a, b)
        battle._assign_uids()
        battle._run_round(1)
        first = a.machine_vengeance_target_uid
        self.assertIsNotNone(first)
        # Plant a stale uid; the next Command phase must clear-and-repick it.
        a.machine_vengeance_target_uid = "STALE"
        battle._run_round(2)
        self.assertNotEqual(a.machine_vengeance_target_uid, "STALE")
        self.assertEqual(a.machine_vengeance_target_uid, first)


if __name__ == "__main__":
    unittest.main()
