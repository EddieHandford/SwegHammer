"""Fire Overwatch on a Normal/Advance move — env-gated SWEG_OVERWATCH_MOVE.

The 10e Fire Overwatch core stratagem triggers verbatim "just after an enemy
unit is set up or starts or ends a Normal, Advance, Fall Back or Charge move"
(`simulator.fire_overwatch`, data/rule_citations.d/core_overwatch.json). The
simulator only hooked the charge-declaration point (`_do_charge`) and the
reserves-arrival point, so a unit Normal-/Advance-moving onto a midboard
objective within 24" of an enemy gunline drew no reactive fire — a partial
implementation that under-credits the going-second player (a documented
contributor to the going-first over-reward).

`SWEG_OVERWATCH_MOVE` (default-off) completes the cited trigger: just after a
Normal/Advance move finishes in `_do_move`, the opponent may Fire Overwatch at
the unit that moved, through the SAME once-per-round / 24" / unmodified-6s
`_fire_overwatch` path. Off path is byte-identical (the gate guards the whole
call; no Command Point spent, no random draw).

Rides on the existing citation `simulator.fire_overwatch` (no new rule key).
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import Unit, UnitProfile


def _gunline(name: str = "Gunline", attacks: int = 12) -> UnitProfile:
    """A shooty unit with a real anti-infantry gun (24" range) that can Fire
    Overwatch. Strength 10 / AP-4 so the wound + save legs pass and the variable
    under test is the trigger, not the damage roll."""
    return UnitProfile(
        name=name, health=8.0, damage=1.0, hit_probability=2 / 3, ap=-4, save=3,
        strength=10, toughness=4, attacks=attacks, weapon_damage_per_shot=1.0,
        range_inches=24, unit_keywords=("INFANTRY",), melee_attacks=1,
        melee_hit_probability=0.5, melee_strength=4, melee_damage_per_shot=1.0,
    )


def _mover(name: str = "Mover", health: float = 40.0) -> UnitProfile:
    """A melee unit that Normal-/Advance-moves toward the gunline (ENGAGE intent)
    and ends within 24" — the unit that should draw move-triggered overwatch."""
    return UnitProfile(
        name=name, health=health, damage=4.0, hit_probability=2 / 3, ap=0, save=6,
        strength=8, toughness=4, attacks=0, range_inches=1,
        unit_keywords=("INFANTRY",), melee_attacks=6, melee_hit_probability=2 / 3,
        melee_strength=8, melee_damage_per_shot=2.0,
    )


def _build(cp: int = 3, gun_pos=(0.0, 0.0), mover_pos=(0.0, 18.0)):
    """Battle on a clean (terrain-free, objective-free) Map. Army A owns the
    gunline that may overwatch; army B owns the mover. _do_move(mover, B, A) is
    the unit under test — B's mover ends a Normal/Advance move and A overwatches.
    """
    army_a = Army("Defenders")
    army_a.add_unit(_gunline())
    army_a.command_points = cp
    army_b = Army("Attackers")
    army_b.add_unit(_mover())
    battle = Battle(army_a, army_b, map_=Map("Test", 60.0, 44.0))
    battle._assign_uids()
    battle._current_round = 2
    battle._advanced_this_round = set()
    battle._overwatched_this_round = set()
    army_a.units[0].position = gun_pos
    army_b.units[0].position = mover_pos
    return battle


class OverwatchMoveTriggerTests(unittest.TestCase):
    def setUp(self):
        self._saved_ow = os.environ.get("SWEG_OVERWATCH")
        self._saved_move = os.environ.get("SWEG_OVERWATCH_MOVE")
        os.environ["SWEG_OVERWATCH"] = "1"

    def tearDown(self):
        for k, v in (("SWEG_OVERWATCH", self._saved_ow),
                     ("SWEG_OVERWATCH_MOVE", self._saved_move)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_gate_on_move_triggers_overwatch(self):
        """Gate ON: the mover ends a Normal/Advance move within 24" of the
        gunline, the gunline spends 1 Command Point on Fire Overwatch, and the
        once-per-round flag is set."""
        os.environ["SWEG_OVERWATCH_MOVE"] = "1"
        random.seed(7)
        battle = _build(cp=3)
        mover = battle.b.units[0]
        old = mover.position
        cp0 = battle.a.command_points
        battle._do_move(mover, battle.b, battle.a)
        self.assertNotEqual(mover.position, old, "mover should have moved")
        self.assertEqual(battle.a.command_points, cp0 - 1,
                         "move-triggered overwatch must cost exactly 1 Command Point")
        self.assertIn(battle.a.name, battle._overwatched_this_round)

    def test_gate_off_move_does_not_trigger_overwatch(self):
        """Gate OFF (default): the same move happens but no overwatch fires —
        no Command Point spent, once-per-round flag untouched."""
        os.environ["SWEG_OVERWATCH_MOVE"] = "0"
        random.seed(7)
        battle = _build(cp=3)
        mover = battle.b.units[0]
        old = mover.position
        cp0 = battle.a.command_points
        battle._do_move(mover, battle.b, battle.a)
        self.assertNotEqual(mover.position, old, "mover should still move with gate off")
        self.assertEqual(battle.a.command_points, cp0,
                         "no Command Point spent with gate off")
        self.assertNotIn(battle.a.name, battle._overwatched_this_round)

    def test_gate_on_move_ending_out_of_range_no_overwatch(self):
        """Gate ON but the mover ends its move more than 24" from the gunline:
        no eligible overwatcher, so no Command Point is spent (no wasted fire)."""
        os.environ["SWEG_OVERWATCH_MOVE"] = "1"
        random.seed(7)
        # 45" apart — a Normal+Advance move (<=~12") cannot close inside 24".
        battle = _build(cp=3, gun_pos=(0.0, 0.0), mover_pos=(0.0, 45.0))
        mover = battle.b.units[0]
        cp0 = battle.a.command_points
        battle._do_move(mover, battle.b, battle.a)
        self.assertGreater(_dist(mover.position, (0.0, 0.0)), 24.0,
                           "mover should still be beyond 24\"")
        self.assertEqual(battle.a.command_points, cp0,
                         "no Command Point spent when the move ends out of range")
        self.assertNotIn(battle.a.name, battle._overwatched_this_round)

    def test_gate_off_byte_identical_rng(self):
        """Gate OFF consumes exactly the same random draws as a run in which
        `_fire_overwatch` is stubbed to a pure no-op — i.e. the move-overwatch
        hook adds zero draws on the OFF path (anchor-validity proof)."""
        os.environ["SWEG_OVERWATCH_MOVE"] = "0"

        # Reference: stub _fire_overwatch to a no-op.
        battle_ref = _build(cp=3)
        random.seed(99)
        state0 = random.getstate()
        orig = Battle._fire_overwatch
        try:
            Battle._fire_overwatch = lambda self, a, e: None
            battle_ref._do_move(battle_ref.b.units[0], battle_ref.b, battle_ref.a)
        finally:
            Battle._fire_overwatch = orig
        ref_state = random.getstate()
        ref_cp = battle_ref.a.command_points

        # Live (gate-off) run with the real _fire_overwatch.
        battle_live = _build(cp=3)
        random.setstate(state0)
        battle_live._do_move(battle_live.b.units[0], battle_live.b, battle_live.a)
        live_state = random.getstate()
        live_cp = battle_live.a.command_points

        self.assertEqual(live_state, ref_state,
                         "gate-off move must consume identical random draws")
        self.assertEqual(live_cp, ref_cp,
                         "gate-off move must spend no extra Command Points")


def _dist(p, q):
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


if __name__ == "__main__":
    unittest.main()
