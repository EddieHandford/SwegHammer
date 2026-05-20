"""Tests for `code/secondaries.py` — 10e Pariah Nexus secondary objective
scoring layer (SC4-A: Bring it Down + No Prisoners).
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from code.secondaries import (
    BRING_IT_DOWN_CAP_PER_ROUND,
    NO_PRISONERS_CAP_PER_ROUND,
    BRING_IT_DOWN_VP_PER_KILL,
    NO_PRISONERS_VP_PER_UNIT,
    score_round_delta,
    take_snapshot,
)


def _make_unit(name: str, alive: bool, keywords: tuple = ()) -> SimpleNamespace:
    """Minimal Unit stand-in for the secondary scorer. The scorer only
    reads `current_health > 0` and `profile.unit_keywords`."""
    return SimpleNamespace(
        current_health=1.0 if alive else 0.0,
        profile=SimpleNamespace(unit_keywords=keywords),
    )


class TakeSnapshotTests(unittest.TestCase):
    """The snapshot captures alive Units by object identity, MONSTER /
    VEHICLE units flagged separately for Bring it Down."""

    def test_empty_army_produces_empty_snapshot(self):
        snap = take_snapshot([])
        self.assertEqual(len(snap.unit_ids_alive), 0)
        self.assertEqual(len(snap.monster_vehicle_ids_alive), 0)

    def test_dead_units_excluded_from_snapshot(self):
        dead = _make_unit("Plague Marines", alive=False)
        alive = _make_unit("Plague Marines", alive=True)
        snap = take_snapshot([dead, alive])
        self.assertEqual(len(snap.unit_ids_alive), 1)
        self.assertIn(id(alive), snap.unit_ids_alive)
        self.assertNotIn(id(dead), snap.unit_ids_alive)

    def test_monster_keyword_flags_monster_vehicle_set(self):
        infantry = _make_unit("Plague Marine", alive=True, keywords=("INFANTRY",))
        monster = _make_unit("Mortarion", alive=True, keywords=("MONSTER", "CHARACTER"))
        vehicle = _make_unit("Plagueburst Crawler", alive=True, keywords=("VEHICLE",))
        snap = take_snapshot([infantry, monster, vehicle])
        self.assertEqual(len(snap.unit_ids_alive), 3)
        self.assertEqual(len(snap.monster_vehicle_ids_alive), 2)
        self.assertIn(id(monster), snap.monster_vehicle_ids_alive)
        self.assertIn(id(vehicle), snap.monster_vehicle_ids_alive)
        self.assertNotIn(id(infantry), snap.monster_vehicle_ids_alive)


class ScoreRoundDeltaTests(unittest.TestCase):
    """The scorer credits one side for killing the other's units this
    round. Per-round caps apply per the 10e Pariah Nexus rule text."""

    def test_no_kills_means_no_secondary_vp(self):
        u1 = _make_unit("Plague Marines", alive=True)
        u2 = _make_unit("Hellbrute", alive=True, keywords=("VEHICLE",))
        snap = take_snapshot([u1, u2])
        # Both still alive at end of round.
        bid, np_vp = score_round_delta(snap, [u1, u2])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, 0)

    def test_one_infantry_kill_grants_no_prisoners_not_bring_it_down(self):
        infantry = _make_unit("Plague Marines", alive=True, keywords=("INFANTRY",))
        snap = take_snapshot([infantry])
        infantry.current_health = 0.0
        bid, np_vp = score_round_delta(snap, [infantry])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)

    def test_one_monster_kill_grants_both(self):
        mortarion = _make_unit("Mortarion", alive=True,
                                keywords=("MONSTER", "CHARACTER"))
        snap = take_snapshot([mortarion])
        mortarion.current_health = 0.0
        bid, np_vp = score_round_delta(snap, [mortarion])
        # MONSTER kill counts for both Bring it Down AND No Prisoners
        # (the unit also counted as a destroyed unit).
        self.assertEqual(bid, BRING_IT_DOWN_VP_PER_KILL)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)

    def test_bring_it_down_caps_at_15_per_round(self):
        # Six MONSTER kills in one round = 30 VP raw, capped to 15.
        units = [
            _make_unit(f"Carnifex {i}", alive=True, keywords=("MONSTER",))
            for i in range(6)
        ]
        snap = take_snapshot(units)
        for u in units:
            u.current_health = 0.0
        bid, _ = score_round_delta(snap, units)
        self.assertEqual(bid, BRING_IT_DOWN_CAP_PER_ROUND)

    def test_no_prisoners_caps_at_15_per_round(self):
        # Six unit kills = 30 VP raw, capped to 15.
        units = [
            _make_unit(f"Termagants {i}", alive=True, keywords=("INFANTRY",))
            for i in range(6)
        ]
        snap = take_snapshot(units)
        for u in units:
            u.current_health = 0.0
        _, np_vp = score_round_delta(snap, units)
        self.assertEqual(np_vp, NO_PRISONERS_CAP_PER_ROUND)

    def test_dead_at_snapshot_not_credited(self):
        # A unit that was already dead at round start can't be credited.
        # (Avoids double-counting if some other rule resurrects then kills
        # the same unit within the same round.)
        already_dead = _make_unit("Plague Marines", alive=False)
        snap = take_snapshot([already_dead])
        bid, np_vp = score_round_delta(snap, [already_dead])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, 0)

    def test_revived_unit_not_counted_as_kill(self):
        # Necron Reanimation Protocols can revive a destroyed model. If a
        # unit was alive at round start, "killed" mid-round, then revived
        # by end-of-round, it should NOT be credited as destroyed —
        # because alive_now is True again.
        warriors = _make_unit("Necron Warriors", alive=True,
                              keywords=("INFANTRY",))
        snap = take_snapshot([warriors])
        # Damage to zero, then revival back to alive.
        warriors.current_health = 0.0
        # ... revival happens via _apply_reanimation in the real flow ...
        warriors.current_health = 1.0
        bid, np_vp = score_round_delta(snap, [warriors])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, 0)


if __name__ == "__main__":
    unittest.main()
