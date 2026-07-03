"""Persistent multi-round focus nomination (env-gated SWEG_PERSISTENT_NOMINATION).

The capstone activation-allocation decomposition (docs/DECISION_LEDGER.md,
2026-07-03) found the wave-101 collective focus-fire nominator effectively never
fires against a durable brick: its gate demands the army crack ~0.85 of the
brick's wounds in a SINGLE Shooting phase (~22 expected wounds against a
26-wound Knight), so fire falls through to the lowest-current-health picker and
scatters. Real players commit their anti-tank to ONE Knight ACROSS rounds until
it dies. The persistent reshape (`Battle._nominate_persistent_target`) nominates
a brick the army can crack within three rounds of sustained fire, PERSISTS the
nomination across rounds on `Army._persistent_nom_uid` until the brick dies or
becomes un-woundable, then re-nominates the next brick. The contest-pool filter
in `_do_shoot` (`pool = contesting or candidates`), which would drop an
off-objective nominee, re-admits it under the same gate.

Cited as `simulator.persistent_nomination`
(data/rule_citations.d/persistent_nomination.json).
"""

from __future__ import annotations

import os
import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle

from tests.test_focus_fire import (
    _antitank,
    _build,
    _chaff,
    _knight_brick,
)


class PersistentNominationGateTests(unittest.TestCase):
    """Gate discipline: unset never sets the persistent state; set replaces the
    one-phase crack bar with the three-round commitment."""

    def setUp(self):
        self._saved = os.environ.get("SWEG_PERSISTENT_NOMINATION")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("SWEG_PERSISTENT_NOMINATION", None)
        else:
            os.environ["SWEG_PERSISTENT_NOMINATION"] = self._saved

    def test_gate_unset_persistent_state_never_set(self):
        """Gate unset: the wave-101 path runs unchanged and the persistent
        state is never populated."""
        os.environ.pop("SWEG_PERSISTENT_NOMINATION", None)
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2")],
            [_knight_brick(), _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertIsNone(getattr(battle.a, "_persistent_nom_uid", None))

    def test_gate_on_nominates_brick_the_one_phase_bar_rejects(self):
        """THE RESHAPE: two anti-tank units (~8.9 expected wounds/phase) fall
        far short of the one-phase bar (0.85 x 26 = 22.1) — the wave-101 path
        does NOT nominate — but clear the three-round bar (8.9 x 3 = 26.7 >=
        26), so the persistent path DOES nominate the Knight."""
        # First confirm the wave-101 path rejects this army/brick pairing.
        os.environ.pop("SWEG_PERSISTENT_NOMINATION", None)
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2")],
            [_knight_brick(), _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertIsNone(getattr(battle.a, "_focusfire_target_uid", None))
        # Same board, gate on: the persistent path nominates the Knight.
        os.environ["SWEG_PERSISTENT_NOMINATION"] = "1"
        knight = targets[0]
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertEqual(getattr(battle.a, "_persistent_nom_uid", None), knight.uid)
        self.assertEqual(getattr(battle.a, "_focusfire_target_uid", None), knight.uid)

    def test_small_arms_only_army_never_nominates(self):
        """An army whose every weapon contributes zero expected wounds against
        the brick never nominates — no wasted fire, exactly as the wave-101
        gate promises."""
        os.environ["SWEG_PERSISTENT_NOMINATION"] = "1"
        battle, shooters, targets = _build(
            [_chaff("Inf1"), _chaff("Inf2"), _chaff("Inf3")],
            [_knight_brick(), _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertIsNone(getattr(battle.a, "_persistent_nom_uid", None))
        self.assertIsNone(getattr(battle.a, "_focusfire_target_uid", None))


class PersistentNominationPersistenceTests(unittest.TestCase):
    """The cross-round commitment: the nominee holds across repeated Shooting
    phases until it dies, then the next brick is re-nominated."""

    def setUp(self):
        os.environ["SWEG_PERSISTENT_NOMINATION"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_PERSISTENT_NOMINATION", None)

    def test_nomination_persists_across_phases(self):
        """Once committed, the army re-publishes the SAME nominee every phase
        even after the brick takes damage (the one-phase bar would drop a
        wounded brick's crack requirement, but persistence must not waver
        regardless)."""
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2")],
            [_knight_brick("Knight A"), _knight_brick("Knight B"),
             _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        first = getattr(battle.a, "_persistent_nom_uid", None)
        self.assertIsNotNone(first)
        # Damage the OTHER Knight below the nominee's health: a per-phase
        # lowest-health re-pick would flip; the persistent commitment must not.
        other = next(t for t in targets[:2] if t.uid != first)
        other.current_health = 3.0
        for _ in range(3):
            battle._nominate_focusfire_target(battle.a, battle.b)
            self.assertEqual(getattr(battle.a, "_persistent_nom_uid", None), first)
            self.assertEqual(getattr(battle.a, "_focusfire_target_uid", None), first)

    def test_renominates_next_brick_on_death(self):
        """When the nominee dies the commitment is released and the next
        crackable brick is nominated the following phase."""
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2")],
            [_knight_brick("Knight A"), _knight_brick("Knight B"),
             _chaff("Scout")],
        )
        battle._nominate_focusfire_target(battle.a, battle.b)
        first = getattr(battle.a, "_persistent_nom_uid", None)
        self.assertIsNotNone(first)
        nominee = next(t for t in targets if t.uid == first)
        nominee.current_health = 0.0   # dead
        battle._nominate_focusfire_target(battle.a, battle.b)
        second = getattr(battle.a, "_persistent_nom_uid", None)
        self.assertIsNotNone(second)
        self.assertNotEqual(second, first)


class PersistentNominationContestPoolTests(unittest.TestCase):
    """The contest-pool interaction fix: `pool = contesting or candidates` in
    `_do_shoot` drops an off-objective nominee whenever ANY enemy contests one
    of our objectives; under the gate the nominee is re-admitted so committed
    anti-tank fire still reaches it."""

    def setUp(self):
        os.environ["SWEG_PERSISTENT_NOMINATION"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_PERSISTENT_NOMINATION", None)

    def _build_with_objective(self):
        """A board with one objective. The chaff Scout stands ON the objective
        (so `contesting` is non-empty and the pool narrows to it); the Knight
        nominee stands OFF it. Without the fix, every shooter's pool is just
        the Scout and the committed anti-tank fire never reaches the Knight."""
        battle, shooters, targets = _build(
            [_antitank("AT1"), _antitank("AT2")],
            [_knight_brick(), _chaff("Scout")],
        )
        knight, scout = targets[0], targets[1]
        # One objective directly under the Scout, far from the Knight.
        battle.map = Map(
            "Test-With-Objective", 60.0, 44.0,
            objectives=(Objective("obj-under-scout",
                                  scout.position[0], scout.position[1]),),
        )
        return battle, shooters, knight, scout

    def test_off_objective_nominee_still_receives_committed_fire(self):
        import random
        battle, shooters, knight, scout = self._build_with_objective()
        battle._nominate_focusfire_target(battle.a, battle.b)
        self.assertEqual(getattr(battle.a, "_persistent_nom_uid", None), knight.uid)
        hp_before = knight.current_health
        random.seed(20260703)
        for s in shooters:
            if s.is_alive:
                battle._do_shoot(s, battle.a, battle.b)
        self.assertLess(
            knight.current_health, hp_before,
            "the off-objective nominee must be re-admitted to the contest-"
            "narrowed pool so committed anti-tank fire reaches it",
        )


if __name__ == "__main__":
    unittest.main()
