"""Tests for the matplotlib replay renderer.

The renderer is mostly graphical and exercised end-to-end in `run.py`, but
two pure pieces are worth pinning down with tests:

  1. The shape-dispatch logic (``_shape_for``) — a TITANIC unit must read as
     a large rectangle, a MONSTER as a large circle, etc.
  2. The activation-frame aggregator (``aggregate_activations``) — consecutive
     events from the same active unit must collapse into a single replay
     frame, while a different unit's event interrupts the chain.
"""

from __future__ import annotations

import unittest

from code.events import (
    BattleStarted, BattleshockFailed, InitialUnit, ObjectiveScored,
    RoundEnded, RoundStarted, UnitActivated, UnitAdvanced, UnitCharged,
    UnitFought, UnitKilled, UnitMoved, UnitShot,
)
from code.renderer import (
    SHAPE_CHARACTER_CIRCLE,
    SHAPE_ELLIPSE,
    SHAPE_LARGE_CIRCLE,
    SHAPE_LARGE_RECT,
    SHAPE_MEDIUM_RECT,
    SHAPE_SMALL_CIRCLE,
    SHAPE_SWARM,
    _shape_for,
    aggregate_activations,
)


class ShapeDispatcherTests(unittest.TestCase):

    def test_vehicle_is_medium_rectangle(self):
        tag, size = _shape_for(("VEHICLE",))
        self.assertEqual(tag, SHAPE_MEDIUM_RECT)
        # Rectangle hints are (width, height) tuples in world inches.
        self.assertIsInstance(size, tuple)
        self.assertEqual(len(size), 2)

    def test_walker_is_medium_rectangle(self):
        tag, _ = _shape_for(("WALKER",))
        self.assertEqual(tag, SHAPE_MEDIUM_RECT)

    def test_titanic_is_large_rectangle(self):
        # Largest silhouette wins even alongside VEHICLE.
        tag, size = _shape_for(("TITANIC", "VEHICLE"))
        self.assertEqual(tag, SHAPE_LARGE_RECT)
        self.assertIsInstance(size, tuple)
        big_w, big_h = size
        # Sanity: large rect strictly bigger than medium.
        med_tag, med_size = _shape_for(("VEHICLE",))
        med_w, med_h = med_size
        self.assertGreater(big_w, med_w)
        self.assertGreater(big_h, med_h)

    def test_towering_is_large_rectangle(self):
        tag, _ = _shape_for(("TOWERING",))
        self.assertEqual(tag, SHAPE_LARGE_RECT)

    def test_monster_is_large_circle(self):
        tag, size = _shape_for(("MONSTER",))
        self.assertEqual(tag, SHAPE_LARGE_CIRCLE)
        # Large circles use a scatter `s=` value > the default small circle.
        _, small_size = _shape_for(("INFANTRY",))
        self.assertGreater(size, small_size)

    def test_bike_is_ellipse(self):
        tag, size = _shape_for(("BIKE",))
        self.assertEqual(tag, SHAPE_ELLIPSE)
        self.assertIsInstance(size, tuple)

    def test_mounted_is_ellipse(self):
        tag, _ = _shape_for(("MOUNTED",))
        self.assertEqual(tag, SHAPE_ELLIPSE)

    def test_swarm_is_swarm_cluster(self):
        tag, _ = _shape_for(("SWARM",))
        self.assertEqual(tag, SHAPE_SWARM)

    def test_character_is_outlined_circle(self):
        tag, _ = _shape_for(("CHARACTER",))
        self.assertEqual(tag, SHAPE_CHARACTER_CIRCLE)

    def test_infantry_is_default_small_circle(self):
        tag, size = _shape_for(("INFANTRY",))
        self.assertEqual(tag, SHAPE_SMALL_CIRCLE)
        # Size hint is a scalar scatter `s=` value, not a tuple.
        self.assertIsInstance(size, (int, float))

    def test_empty_keywords_falls_through_to_default(self):
        tag, _ = _shape_for(())
        self.assertEqual(tag, SHAPE_SMALL_CIRCLE)

    def test_none_keywords_falls_through_to_default(self):
        tag, _ = _shape_for(None)
        self.assertEqual(tag, SHAPE_SMALL_CIRCLE)

    def test_vehicle_character_reads_as_vehicle(self):
        # Bigger silhouette wins: a vehicle character (e.g. a Land Raider
        # with a CHARACTER tag) should still draw as a vehicle.
        tag, _ = _shape_for(("CHARACTER", "VEHICLE"))
        self.assertEqual(tag, SHAPE_MEDIUM_RECT)


# ---------------------------------------------------------------------------
# aggregate_activations — collapse one unit's full activation into one frame
# ---------------------------------------------------------------------------

def _shot(attacker_uid: str, target_uid: str = "target") -> UnitShot:
    """Tiny constructor — shot-resolution numbers are irrelevant to grouping."""
    return UnitShot(
        attacker_uid=attacker_uid,
        target_uid=target_uid,
        damage=1.0,
        target_hp_after=2.0,
        target_alive_after=True,
    )


def _fight(attacker_uid: str, target_uid: str = "target") -> UnitFought:
    return UnitFought(
        attacker_uid=attacker_uid,
        target_uid=target_uid,
        damage=1.0,
        target_hp_after=2.0,
        target_alive_after=True,
    )


def _moved(unit_uid: str) -> UnitMoved:
    return UnitMoved(unit_uid=unit_uid, from_pos=(0.0, 0.0), to_pos=(1.0, 1.0))


class AggregateActivationsTests(unittest.TestCase):
    """The aggregator drives how many ticks the Replay slider has. The
    rules are simple: same-actor neighbours merge; a different actor
    interrupts; non-activation events (boundaries / scoring / battleshock)
    are always single-event frames."""

    def test_three_shots_then_fight_same_unit_collapse_to_one_frame(self):
        # The headline case from the spec: a single unit shoots three
        # targets and then fights. Without aggregation that's 4 slider
        # ticks of one unit doing things — painful to watch. With
        # aggregation it's a single visual beat.
        events = [
            _shot("A", "t1"),
            _shot("A", "t2"),
            _shot("A", "t3"),
            _fight("A"),
        ]
        frames = aggregate_activations(events)
        self.assertEqual(frames, [(0, 3)])

    def test_interrupting_unit_breaks_the_chain(self):
        # The other spec case: A moves, B shoots, A shoots. Even though
        # both A events are "the same unit", B sits between them, so
        # they're TWO separate activations of A with B's in the middle —
        # three frames total.
        events = [
            _moved("A"),
            _shot("B"),
            _shot("A"),
        ]
        frames = aggregate_activations(events)
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames, [(0, 0), (1, 1), (2, 2)])

    def test_lone_move_is_its_own_frame(self):
        # A unit that only moves still gets a frame — visualising the
        # repositioning matters even without firing.
        events = [_moved("A")]
        self.assertEqual(aggregate_activations(events), [(0, 0)])

    def test_unit_activated_anchors_subsequent_same_unit_events(self):
        # Mirrors the real simulator emission order: UnitActivated, then
        # move, then shoot. All belong to one activation.
        events = [
            UnitActivated(unit_uid="A", army_name="X"),
            _moved("A"),
            _shot("A"),
        ]
        self.assertEqual(aggregate_activations(events), [(0, 2)])

    def test_advance_event_groups_with_the_same_unit(self):
        # An advancing unit emits UnitMoved + UnitAdvanced (no shoot).
        events = [
            _moved("A"),
            UnitAdvanced(unit_uid="A", advance_roll=4, total_movement=10.0),
        ]
        self.assertEqual(aggregate_activations(events), [(0, 1)])

    def test_charge_groups_with_the_charging_unit(self):
        events = [
            _moved("A"),
            UnitCharged(unit_uid="A", target_uid="X", distance=8.0,
                        roll=9, succeeded=True),
            _fight("A", "X"),
        ]
        self.assertEqual(aggregate_activations(events), [(0, 2)])

    def test_unit_killed_pulled_into_the_killing_activation(self):
        # UnitKilled refers to the target, but always immediately follows
        # the shot/fight that killed it. We pull it into the killing
        # frame so the kill renders as part of that activation, not a
        # standalone tick.
        events = [
            _shot("A", "t1"),
            UnitKilled(unit_uid="t1"),
            _shot("A", "t2"),
        ]
        self.assertEqual(aggregate_activations(events), [(0, 2)])

    def test_round_boundary_breaks_the_chain(self):
        # Even if A acts in two consecutive rounds, the round boundary
        # separates them — a viewer needs to see the round change.
        events = [
            _shot("A"),
            RoundEnded(round_num=1),
            RoundStarted(round_num=2),
            _shot("A"),
        ]
        frames = aggregate_activations(events)
        self.assertEqual(len(frames), 4)
        # Boundary events are always single-event frames.
        self.assertEqual(frames[1], (1, 1))
        self.assertEqual(frames[2], (2, 2))

    def test_objective_score_is_its_own_frame(self):
        events = [
            _shot("A"),
            ObjectiveScored(objective_name="Centre", army_name="X",
                            vp_awarded=5, a_oc=3, b_oc=1),
            _shot("A"),
        ]
        frames = aggregate_activations(events)
        # Three frames: A's first activation, the score, A's second activation.
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[1], (1, 1))

    def test_battleshock_is_its_own_frame(self):
        events = [
            _shot("A"),
            BattleshockFailed(unit_uid="B", roll=11, target=8),
            _shot("A"),
        ]
        frames = aggregate_activations(events)
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[1], (1, 1))

    def test_battle_started_is_its_own_frame(self):
        # BattleStarted sets up the initial board — never merged with what
        # follows, otherwise the initial-deployment view is lost.
        bs = BattleStarted(
            army_a_name="A", army_b_name="B", map_name="Test",
            units=(InitialUnit(uid="u1", name="x", army="A",
                               position=(0.0, 0.0), max_health=1.0),),
        )
        events = [bs, _shot("u1")]
        frames = aggregate_activations(events)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0], (0, 0))
        self.assertEqual(frames[1], (1, 1))

    def test_empty_event_log_returns_empty_frames(self):
        self.assertEqual(aggregate_activations([]), [])

    def test_frames_partition_the_event_log(self):
        # Sanity property: frames must tile the event indices without
        # gaps or overlap, in order. If this ever fails the slider would
        # skip or repeat events.
        events = [
            _moved("A"), _shot("A"), _shot("A"),
            RoundEnded(round_num=1),
            _moved("B"), _fight("B"),
        ]
        frames = aggregate_activations(events)
        # Concatenate the [start, end] ranges and verify we cover 0..n-1
        # exactly once each.
        seen: list = []
        for s, e in frames:
            self.assertLessEqual(s, e)
            seen.extend(range(s, e + 1))
        self.assertEqual(seen, list(range(len(events))))

    def test_fewer_frames_than_events_for_aggregated_log(self):
        # The whole point of the change: aggregated frames must be
        # strictly fewer than raw events whenever any activation has
        # more than one event in it.
        events = [
            _moved("A"), _shot("A"), _shot("A"), _fight("A"),
            _moved("B"),
        ]
        frames = aggregate_activations(events)
        self.assertLess(len(frames), len(events))


if __name__ == "__main__":
    unittest.main()
