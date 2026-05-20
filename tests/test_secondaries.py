"""Tests for `code/secondaries.py` — 10e Pariah Nexus secondary objective
scoring layer (SC4-A: Bring it Down + No Prisoners).
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from code.secondaries import (
    ASSASSINATION_CAP_PER_ROUND,
    ASSASSINATION_VP_PER_CHAR,
    BEHIND_ENEMY_LINES_VP,
    BRING_IT_DOWN_CAP_PER_ROUND,
    BRING_IT_DOWN_VP_PER_KILL,
    CULL_THE_HORDE_CAP_PER_ROUND,
    CULL_THE_HORDE_VP_PER_UNIT,
    ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND,
    NO_PRISONERS_CAP_PER_ROUND,
    NO_PRISONERS_VP_PER_UNIT,
    score_position_delta,
    score_round_delta,
    take_snapshot,
)


def _make_unit(name: str, alive: bool, keywords: tuple = (),
               position: tuple = None,
               starting_strength: int = 1) -> SimpleNamespace:
    """Minimal Unit stand-in for the secondary scorer. The scorer reads
    `current_health > 0`, `profile.unit_keywords`, optionally `position`
    (position-tracking secondaries), and `profile.starting_strength`
    (Cull the Horde gate)."""
    ns = SimpleNamespace(
        current_health=1.0 if alive else 0.0,
        profile=SimpleNamespace(
            unit_keywords=keywords,
            starting_strength=starting_strength,
        ),
    )
    if position is not None:
        ns.position = position
    return ns


def _make_map(width: float = 44.0, height: float = 60.0,
              deployment_width: float = 12.0) -> SimpleNamespace:
    """Minimal Map stand-in for position scoring. `score_position_delta`
    only reads width / height / deployment_width."""
    return SimpleNamespace(
        width=width, height=height, deployment_width=deployment_width,
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
        bid, np_vp, cth, ass = score_round_delta(snap, [u1, u2])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, 0)
        self.assertEqual(cth, 0)
        self.assertEqual(ass, 0)

    def test_one_infantry_kill_grants_no_prisoners_not_bring_it_down(self):
        infantry = _make_unit("Plague Marines", alive=True, keywords=("INFANTRY",))
        snap = take_snapshot([infantry])
        infantry.current_health = 0.0
        bid, np_vp, cth, ass = score_round_delta(snap, [infantry])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)
        self.assertEqual(cth, 0)
        self.assertEqual(ass, 0)

    def test_one_monster_kill_grants_both(self):
        mortarion = _make_unit("Mortarion", alive=True,
                                keywords=("MONSTER", "CHARACTER"))
        snap = take_snapshot([mortarion])
        mortarion.current_health = 0.0
        bid, np_vp, cth, ass = score_round_delta(snap, [mortarion])
        # MONSTER + CHARACTER kill counts for Bring it Down, No Prisoners,
        # AND Assassination (Mortarion is also a CHARACTER). Cull stays
        # 0 since Mortarion is starting_strength=1 (single-model squad).
        self.assertEqual(bid, BRING_IT_DOWN_VP_PER_KILL)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)
        self.assertEqual(cth, 0)
        self.assertEqual(ass, ASSASSINATION_VP_PER_CHAR)

    def test_bring_it_down_caps_at_15_per_round(self):
        # Six MONSTER kills in one round = 30 VP raw, capped to 15.
        units = [
            _make_unit(f"Carnifex {i}", alive=True, keywords=("MONSTER",))
            for i in range(6)
        ]
        snap = take_snapshot(units)
        for u in units:
            u.current_health = 0.0
        bid, *_ = score_round_delta(snap, units)
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
        _, np_vp, *_ = score_round_delta(snap, units)
        self.assertEqual(np_vp, NO_PRISONERS_CAP_PER_ROUND)

    def test_dead_at_snapshot_not_credited(self):
        # A unit that was already dead at round start can't be credited.
        # (Avoids double-counting if some other rule resurrects then kills
        # the same unit within the same round.)
        already_dead = _make_unit("Plague Marines", alive=False)
        snap = take_snapshot([already_dead])
        bid, np_vp, cth, ass = score_round_delta(snap, [already_dead])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, 0)
        self.assertEqual(cth, 0)
        self.assertEqual(ass, 0)

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
        bid, np_vp, cth, ass = score_round_delta(snap, [warriors])
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, 0)
        self.assertEqual(cth, 0)
        self.assertEqual(ass, 0)

    def test_cull_the_horde_fires_on_10plus_squad_kill(self):
        # 10-model Boyz squad destroyed this round → Cull scores.
        boyz = _make_unit("Boyz", alive=True, keywords=("INFANTRY",),
                          starting_strength=10)
        snap = take_snapshot([boyz])
        boyz.current_health = 0.0
        _, np_vp, cth, _ = score_round_delta(snap, [boyz])
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)
        self.assertEqual(cth, CULL_THE_HORDE_VP_PER_UNIT)

    def test_cull_the_horde_does_not_fire_on_small_squad(self):
        # 5-model Intercessor squad destroyed → No Prisoners but no Cull.
        intercessors = _make_unit("Intercessors", alive=True,
                                  keywords=("INFANTRY",),
                                  starting_strength=5)
        snap = take_snapshot([intercessors])
        intercessors.current_health = 0.0
        _, np_vp, cth, _ = score_round_delta(snap, [intercessors])
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)
        self.assertEqual(cth, 0)

    def test_cull_caps_at_5_per_round(self):
        # Two 10+ squads killed = 10 VP raw, capped to 5.
        squads = [
            _make_unit(f"Boyz {i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=10)
            for i in range(2)
        ]
        snap = take_snapshot(squads)
        for u in squads:
            u.current_health = 0.0
        _, _, cth, _ = score_round_delta(snap, squads)
        self.assertEqual(cth, CULL_THE_HORDE_CAP_PER_ROUND)

    def test_assassination_fires_on_character_kill(self):
        ahriman = _make_unit("Ahriman", alive=True,
                             keywords=("CHARACTER", "INFANTRY"))
        snap = take_snapshot([ahriman])
        ahriman.current_health = 0.0
        _, _, _, ass = score_round_delta(snap, [ahriman])
        self.assertEqual(ass, ASSASSINATION_VP_PER_CHAR)

    def test_assassination_does_not_fire_on_non_character(self):
        # Plain INFANTRY squad → No Prisoners but no Assassination.
        squad = _make_unit("Tactical Squad", alive=True,
                           keywords=("INFANTRY",))
        snap = take_snapshot([squad])
        squad.current_health = 0.0
        _, _, _, ass = score_round_delta(snap, [squad])
        self.assertEqual(ass, 0)

    def test_assassination_caps_at_10_per_round(self):
        # Three CHARACTER kills = 15 VP raw, capped to 10.
        characters = [
            _make_unit(f"Captain {i}", alive=True,
                       keywords=("CHARACTER", "INFANTRY"))
            for i in range(3)
        ]
        snap = take_snapshot(characters)
        for u in characters:
            u.current_health = 0.0
        _, _, _, ass = score_round_delta(snap, characters)
        self.assertEqual(ass, ASSASSINATION_CAP_PER_ROUND)

    def test_lc5_warlord_kill_grants_bonus_vp(self):
        # LC-5: killing the enemy Warlord adds +1 VP on top of the
        # standard 3 VP per CHARACTER. One CHARACTER kill = 3 base VP;
        # if that CHARACTER was the Warlord, +1 = 4 total.
        from code.secondaries import (
            ASSASSINATION_VP_PER_CHAR,
            ASSASSINATION_WARLORD_BONUS_VP,
        )
        warlord = _make_unit("Trajann", alive=True,
                             keywords=("CHARACTER", "INFANTRY"))
        snap = take_snapshot([warlord])
        warlord.current_health = 0.0
        _, _, _, ass = score_round_delta(
            snap, [warlord], enemy_warlord_uid=id(warlord)
        )
        self.assertEqual(
            ass,
            ASSASSINATION_VP_PER_CHAR + ASSASSINATION_WARLORD_BONUS_VP,
        )

    def test_lc5_non_warlord_kill_no_bonus(self):
        # CHARACTER killed that isn't the Warlord — no bonus.
        from code.secondaries import ASSASSINATION_VP_PER_CHAR
        warlord = _make_unit("Trajann", alive=True,
                             keywords=("CHARACTER", "INFANTRY"))
        lieutenant = _make_unit("Lt", alive=True,
                                keywords=("CHARACTER", "INFANTRY"))
        snap = take_snapshot([warlord, lieutenant])
        lieutenant.current_health = 0.0
        # Warlord survives — only the lieutenant died.
        _, _, _, ass = score_round_delta(
            snap, [warlord, lieutenant], enemy_warlord_uid=id(warlord)
        )
        self.assertEqual(ass, ASSASSINATION_VP_PER_CHAR)


class ScorePositionDeltaTests(unittest.TestCase):
    """Engage on All Fronts + Behind Enemy Lines position scoring."""

    # LC-2 schedule reminder:
    #   side A round 1, 3, 5 (odd): Engage active, BEL inactive
    #   side A round 2, 4 (even):   BEL active, Engage inactive
    #   side B round 1, 3, 5 (odd): BEL active, Engage inactive
    #   side B round 2, 4 (even):   Engage active, BEL inactive
    # Tests use the round_num that makes their tested tactical active.

    def test_no_alive_units_scores_zero(self):
        eng, bel = score_position_delta([], _make_map(), own_is_army_a=True,
                                         round_num=1)
        self.assertEqual(eng, 0)
        self.assertEqual(bel, 0)

    def test_engage_one_quadrant_no_score(self):
        # All units in SW quadrant (low-x, low-y).
        units = [
            _make_unit(f"u{i}", alive=True, position=(10.0, 10.0))
            for i in range(5)
        ]
        # Side A round 1 = Engage active.
        eng, _ = score_position_delta(units, _make_map(), own_is_army_a=True,
                                       round_num=1)
        self.assertEqual(eng, 0)

    def test_engage_three_quadrants_scores_full_vp(self):
        # 44x60 map: cx=22, cy=30. Place units in SW (10,10), NW (10,40),
        # NE (30,40). Three quadrants — should score.
        units = [
            _make_unit("sw", alive=True, position=(10.0, 10.0)),
            _make_unit("nw", alive=True, position=(10.0, 40.0)),
            _make_unit("ne", alive=True, position=(30.0, 40.0)),
        ]
        eng, _ = score_position_delta(units, _make_map(), own_is_army_a=True,
                                       round_num=1)
        self.assertEqual(eng, ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND)

    def test_engage_four_quadrants_scores_same_capped_vp(self):
        # All four quadrants — same VP since we have a single threshold.
        units = [
            _make_unit("sw", alive=True, position=(10.0, 10.0)),
            _make_unit("nw", alive=True, position=(10.0, 40.0)),
            _make_unit("ne", alive=True, position=(30.0, 40.0)),
            _make_unit("se", alive=True, position=(30.0, 10.0)),
        ]
        eng, _ = score_position_delta(units, _make_map(), own_is_army_a=True,
                                       round_num=1)
        self.assertEqual(eng, ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND)

    def test_dead_units_excluded_from_quadrant_count(self):
        # 3 quadrants covered but only 1 unit alive.
        dead_se = _make_unit("se", alive=False, position=(30.0, 10.0))
        dead_nw = _make_unit("nw", alive=False, position=(10.0, 40.0))
        live_sw = _make_unit("sw", alive=True, position=(10.0, 10.0))
        eng, _ = score_position_delta(
            [dead_se, dead_nw, live_sw], _make_map(), own_is_army_a=True,
            round_num=1,
        )
        self.assertEqual(eng, 0)

    def test_behind_enemy_lines_army_a_perspective(self):
        # Army A's enemy DZ is the high-y strip (y >= height - deployment_width
        # = 60 - 12 = 48). Place one unit at y=50 (in enemy DZ). Side A
        # round 2 (even) = BEL active.
        unit = _make_unit("scout", alive=True, position=(22.0, 50.0))
        _, bel = score_position_delta(
            [unit], _make_map(), own_is_army_a=True, round_num=2,
        )
        self.assertEqual(bel, BEHIND_ENEMY_LINES_VP)

    def test_behind_enemy_lines_army_b_perspective(self):
        # Army B's enemy DZ is the low-y strip (y <= deployment_width = 12).
        # Place one unit at y=5 (in enemy DZ for Army B). Side B round 1
        # (odd) = BEL active.
        unit = _make_unit("scout", alive=True, position=(22.0, 5.0))
        _, bel = score_position_delta(
            [unit], _make_map(), own_is_army_a=False, round_num=1,
        )
        self.assertEqual(bel, BEHIND_ENEMY_LINES_VP)

    def test_behind_enemy_lines_own_dz_doesnt_score(self):
        # Army A unit at y=5 is in OWN DZ, not enemy DZ.
        unit = _make_unit("turtle", alive=True, position=(22.0, 5.0))
        _, bel = score_position_delta(
            [unit], _make_map(), own_is_army_a=True, round_num=2,
        )
        self.assertEqual(bel, 0)

    def test_unit_without_position_ignored(self):
        # Some test paths construct Units without setting position (the
        # `pos = getattr(u, 'position', None)` guard returns None and we
        # skip). Should not raise; just contribute nothing.
        unit = _make_unit("no-pos", alive=True)
        eng, bel = score_position_delta(
            [unit], _make_map(), own_is_army_a=True, round_num=1,
        )
        self.assertEqual(eng, 0)
        self.assertEqual(bel, 0)

    def test_lc2_tactical_deck_gates_engage_off_in_bel_turn(self):
        # LC-2: side A round 2 (even) = BEL active, Engage inactive.
        # Even though units occupy 3+ quadrants (would otherwise score
        # Engage), the deck-draw gate suppresses it.
        units = [
            _make_unit("sw", alive=True, position=(10.0, 10.0)),
            _make_unit("nw", alive=True, position=(10.0, 40.0)),
            _make_unit("ne", alive=True, position=(30.0, 40.0)),
        ]
        eng, _ = score_position_delta(units, _make_map(), own_is_army_a=True,
                                       round_num=2)
        self.assertEqual(eng, 0)

    def test_lc2_tactical_deck_gates_bel_off_in_engage_turn(self):
        # LC-2: side A round 1 (odd) = Engage active, BEL inactive.
        # Even though a unit sits in enemy DZ (would score BEL), the
        # deck-draw gate suppresses it.
        unit = _make_unit("scout", alive=True, position=(22.0, 50.0))
        _, bel = score_position_delta(
            [unit], _make_map(), own_is_army_a=True, round_num=1,
        )
        self.assertEqual(bel, 0)


if __name__ == "__main__":
    unittest.main()
