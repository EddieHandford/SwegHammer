"""Pin the #C1 (auto-loop iter1) fight-picker change.

Previously `Battle._do_fight` picked `min(enemies, key=distance)` — the
geometrically nearest enemy in engagement range, regardless of how
useful that fight actually was. The auto-loop Cluster C diagnostic
showed that when 2+ enemies are within 1.5", "geometrically nearest"
can be the wrong call: a squishy gunline / screen / support character
adjacent to a tougher brick is often the higher-leverage kill.

After #C1 the picker uses `_melee_target_score` — a faction-neutral
score composed from attacker DPA-vs-target durability + role-based
screen/synapse/support multipliers — and selects the highest scorer
among engagement-range candidates.

These tests pin the new behaviour with two synthetic enemy units
positioned so the nearest is the WRONG pick under the scoring rule.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.events import UnitFought
from code.simulator import Battle
from code.strategy import _melee_target_score
from code.units import UnitProfile


def _brawler_profile() -> UnitProfile:
    """A neutral melee attacker (no faction triggers)."""
    return UnitProfile(
        name="Brawler", health=4, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5, melee_ap=1,
    )


def _squishy_gunner_profile() -> UnitProfile:
    """Low-T fragile shooter — the high-`_melee_target_score` candidate.

    T3, save 5+, 1W: melts on contact. Has a real ranged threat so
    `_melee_target_score`'s `ranged_value` term kicks in — extra
    pressure to engage this one over the brick.
    """
    return UnitProfile(
        name="Gunner", health=1, damage=1, hit_probability=2 / 3,
        ap=-1, save=5, strength=3, toughness=3,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Generic",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
    )


def _heavy_brick_profile() -> UnitProfile:
    """High-T, multi-wound, strong save — the LOW-score candidate.

    Even though it's the nearest, killing it is unlikely this swing,
    so `_melee_target_score` rates it well below the squishy gunner.
    """
    return UnitProfile(
        name="Brick", health=8, damage=2, hit_probability=2 / 3,
        ap=-2, save=2, strength=8, toughness=10,
        attacks=2, weapon_damage_per_shot=2.0, range_inches=12,
        leadership=8,
        faction="Generic",
        unit_keywords=("MONSTER",),
        melee_attacks=4, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=8, melee_ap=2,
    )


class FightPickerScoreTests(unittest.TestCase):
    """The score helper must rank the squishy gunner above the brick."""

    def test_squishy_gunner_outscores_heavy_brick(self):
        """Sanity-check the helper before driving _do_fight."""
        attacker_army = Army("A")
        attacker_army.add_unit(_brawler_profile())
        defender_army = Army("D")
        defender_army.add_unit(_squishy_gunner_profile())
        defender_army.add_unit(_heavy_brick_profile())

        attacker = attacker_army.units[0]
        gunner, brick = defender_army.units[0], defender_army.units[1]

        score_gunner = _melee_target_score(attacker, gunner)
        score_brick = _melee_target_score(attacker, brick)

        self.assertGreater(
            score_gunner, score_brick,
            "Squishy gunner should be the higher-leverage melee target than"
            " the T10 multi-wound brick.",
        )


class FightPickerDoFightTests(unittest.TestCase):
    """End-to-end: _do_fight must pick the higher-score enemy even when
    the other one is geometrically closer."""

    def _setup(self):
        """Two enemies, both in 1.5" engagement of the attacker.

        Brick is the GEOMETRICALLY NEAREST (0.5" away). Gunner is
        slightly further (1.2") but still inside the 1.5" engagement
        range, and `_melee_target_score(attacker, gunner)` is higher.
        Under the old `min(key=distance)` picker, the brick would
        always win the fight. Under #C1, the gunner wins.
        """
        a = Army("A")
        a.add_unit(_brawler_profile())
        d = Army("D")
        d.add_unit(_squishy_gunner_profile())
        d.add_unit(_heavy_brick_profile())
        battle = Battle(a, d, verbose=False)
        battle._assign_uids()
        battle._deploy_armies()

        attacker = a.units[0]
        gunner, brick = d.units[0], d.units[1]
        # Place attacker between brick (very near) and gunner (still in
        # engagement). All Y aligned for clarity.
        attacker.position = (30.0, 30.0)
        brick.position = (30.5, 30.0)   # 0.5" away
        gunner.position = (31.2, 30.0)  # 1.2" away — still <= 1.5"
        return battle, attacker, gunner, brick

    def test_picker_targets_higher_score_not_nearest(self):
        # Pin to legacy no-collision movement: collision is now default-ON,
        # but this test is about fight-picker geometry, not collision.
        os.environ["SWEG_COLLISION"] = "0"
        try:
            battle, attacker, gunner, brick = self._setup()
            # Subscribe an event capture so we can read the UnitFought target.
            captured = []
            battle.subscribers.append(_Recorder(captured))

            # Deterministic seed — outcome is the picker's choice, not the dice.
            random.seed(0)
            battle._do_fight(attacker, battle.a, battle.b)

            # Filter to fights INITIATED BY our attacker — Counter-Offensive
            # may emit a retaliatory UnitFought from the defender side.
            fights = [
                e for e in captured
                if isinstance(e, UnitFought) and e.attacker_uid == attacker.uid
            ]
            self.assertEqual(
                len(fights), 1,
                "Expected exactly one attacker-initiated UnitFought event.",
            )
            self.assertEqual(
                fights[0].target_uid, gunner.uid,
                "Picker should attack the squishy gunner (highest"
                " `_melee_target_score`), NOT the nearer heavy brick.",
            )
        finally:
            del os.environ["SWEG_COLLISION"]

    def test_picker_respects_engagement_range(self):
        """A high-score enemy outside 1.5" must be ignored — the picker
        is still gated by engagement range."""
        battle, attacker, gunner, brick = self._setup()
        # Push the gunner well outside engagement range.
        gunner.position = (50.0, 30.0)
        captured = []
        battle.subscribers.append(_Recorder(captured))

        random.seed(0)
        battle._do_fight(attacker, battle.a, battle.b)

        fights = [
            e for e in captured
            if isinstance(e, UnitFought) and e.attacker_uid == attacker.uid
        ]
        self.assertEqual(len(fights), 1)
        self.assertEqual(
            fights[0].target_uid, brick.uid,
            "With the gunner out of engagement, only the brick is in"
            " range and must be the picked target.",
        )

    def test_picker_no_op_when_no_enemy_in_range(self):
        battle, attacker, gunner, brick = self._setup()
        gunner.position = (50.0, 30.0)
        brick.position = (50.5, 30.0)
        captured = []
        battle.subscribers.append(_Recorder(captured))

        random.seed(0)
        battle._do_fight(attacker, battle.a, battle.b)

        fights = [
            e for e in captured
            if isinstance(e, UnitFought) and e.attacker_uid == attacker.uid
        ]
        self.assertEqual(
            fights, [],
            "No enemy in engagement range — no UnitFought event should fire.",
        )


class _Recorder:
    """Minimal subscriber that appends every event to a list."""

    def __init__(self, sink):
        self.sink = sink

    def on_event(self, event):
        self.sink.append(event)


if __name__ == "__main__":
    unittest.main()
