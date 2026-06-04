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
    BEHIND_ENEMY_LINES_VP_SINGLE,
    BOARD_SECONDARY_KEYS,
    ENGAGE_VP_THREE_QUADRANTS,
    BRING_IT_DOWN_CAP_PER_ROUND,
    BRING_IT_DOWN_VP_PER_KILL,
    CULL_THE_HORDE_CAP_PER_ROUND,
    CULL_THE_HORDE_VP_PER_UNIT,
    ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND,
    FIXED_SECONDARY_KEYS,
    NO_PRISONERS_CAP_PER_ROUND,
    NO_PRISONERS_VP_PER_UNIT,
    TACTICAL_SECONDARY_KEYS,
    pick_secondaries,
    score_position_delta,
    score_round_delta,
    take_snapshot,
)


def _make_unit(name: str, alive: bool, keywords: tuple = (),
               position: tuple = None,
               starting_strength: int = 1,
               squad_id: int = -1,
               health: float = 1.0) -> SimpleNamespace:
    """Minimal Unit stand-in for the secondary scorer. The scorer reads
    `current_health > 0`, `profile.unit_keywords`, optionally `position`
    (position-tracking secondaries), `profile.starting_strength`
    (Cull the Horde gate), and `squad_id` (per-unit kill tracking).

    `squad_id` defaults to -1 (lone model) so existing tests are unchanged.
    Pass a non-negative integer to simulate squad members sharing the same
    codex unit — a kill is only credited when ALL members are destroyed.
    """
    ns = SimpleNamespace(
        current_health=1.0 if alive else 0.0,
        squad_id=squad_id,
        profile=SimpleNamespace(
            unit_keywords=keywords,
            starting_strength=starting_strength,
            health=health,
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

    def test_bring_it_down_no_per_round_cap_six_base_kills(self):
        # CA-2025-26 Bring It Down has NO per-round cap. Six MONSTER models with
        # under 15 wounds each (the test helper sets no health) score the 2-VP base
        # each = 12 VP, under the effectively-unbounded 18 ceiling.
        units = [
            _make_unit(f"Carnifex {i}", alive=True, keywords=("MONSTER",))
            for i in range(6)
        ]
        snap = take_snapshot(units)
        for u in units:
            u.current_health = 0.0
        bid, *_ = score_round_delta(snap, units)
        self.assertEqual(bid, 6 * BRING_IT_DOWN_VP_PER_KILL)

    def test_bring_it_down_wound_brackets(self):
        # CA-2025-26: 2 VP base, +2 at 15+ total wounds, +2 at 20+, max 6 per unit.
        from code.secondaries import BRING_IT_DOWN_VP_MAX_PER_UNIT
        knight = _make_unit("Knight Paladin", alive=True,
                            keywords=("VEHICLE", "TITANIC"), health=26)
        rhino = _make_unit("Rhino", alive=True, keywords=("VEHICLE",), health=10)
        snap = take_snapshot([knight, rhino])
        knight.current_health = 0.0
        rhino.current_health = 0.0
        bid, *_ = score_round_delta(snap, [knight, rhino])
        # Knight (26 W) = 6 (capped); Rhino (10 W) = base 2 → 8 total.
        self.assertEqual(bid, BRING_IT_DOWN_VP_MAX_PER_UNIT + BRING_IT_DOWN_VP_PER_KILL)

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

    def test_cull_the_horde_fires_on_13plus_squad_kill(self):
        # CA-2025-26: a 13+-model INFANTRY squad destroyed this round → Cull scores 5.
        boyz = _make_unit("Boyz", alive=True, keywords=("INFANTRY",),
                          starting_strength=20)
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

    def test_cull_two_kills_no_per_round_cap(self):
        # CA-2025-26 Cull has NO per-round cap: two 13+ squads killed = 2 x 5 = 10 VP
        # (under the effectively-unbounded 15 cap and the 40-VP secondary total cap).
        squads = [
            _make_unit(f"Boyz {i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=20)
            for i in range(2)
        ]
        snap = take_snapshot(squads)
        for u in squads:
            u.current_health = 0.0
        _, _, cth, _ = score_round_delta(snap, squads)
        self.assertEqual(cth, 2 * CULL_THE_HORDE_VP_PER_UNIT)

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

    def test_assassination_no_per_round_cap_and_wound_tier(self):
        # CA-2025-26: 4 VP for a 4+-wound CHARACTER, 3 for under 4; no per-round cap.
        from code.secondaries import ASSASSINATION_VP_4PLUS_WOUNDS
        big = _make_unit("Warlord", alive=True,
                         keywords=("CHARACTER", "INFANTRY"), health=6)
        small = _make_unit("Tech-Priest", alive=True,
                           keywords=("CHARACTER", "INFANTRY"), health=3)
        characters = [big, small]
        snap = take_snapshot(characters)
        for u in characters:
            u.current_health = 0.0
        _, _, _, ass = score_round_delta(snap, characters)
        # 6-wound = 4 VP, 3-wound = 3 VP → 7 total, under the 12 ceiling (no cap).
        self.assertEqual(ass, ASSASSINATION_VP_4PLUS_WOUNDS + ASSASSINATION_VP_PER_CHAR)

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


class PerUnitSecondaryTests(unittest.TestCase):
    """Per-unit kill counting for No Prisoners and Cull the Horde.

    The codex rules score VP per codex UNIT destroyed, not per model.
    Killing 2 of a 10-model Boyz squad should score 0 No Prisoners VP
    (the unit survives). Only when the LAST model of a squad_id dies is
    the unit considered destroyed.
    """

    def test_partial_squad_kill_scores_no_no_prisoners(self):
        # 5 Boyz models in one squad (squad_id=7). Only 3 are killed this
        # round; 2 survive. The codex unit is NOT destroyed — 0 VP.
        survivors = [
            _make_unit(f"Boyz{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=10, squad_id=7)
            for i in range(2)
        ]
        killed = [
            _make_unit(f"Boyz{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=10, squad_id=7)
            for i in range(3)
        ]
        all_models = survivors + killed
        snap = take_snapshot(all_models)
        # Kill 3 models but leave 2 alive.
        for u in killed:
            u.current_health = 0.0
        _, np_vp, cth, _ = score_round_delta(snap, all_models)
        self.assertEqual(np_vp, 0, "partial squad kill must not score No Prisoners")
        self.assertEqual(cth, 0, "partial squad kill must not score Cull the Horde")

    def test_full_squad_wipeout_scores_one_no_prisoners(self):
        # 5 Boyz models in one squad (squad_id=7), all killed this round.
        # The codex unit IS destroyed — 1 unit kill = 3 No Prisoners VP.
        squad = [
            _make_unit(f"Boyz{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=10, squad_id=7)
            for i in range(5)
        ]
        snap = take_snapshot(squad)
        for u in squad:
            u.current_health = 0.0
        _, np_vp, cth, _ = score_round_delta(snap, squad)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT,
                         "full squad wipeout must score exactly 1 No Prisoners unit")

    def test_full_horde_squad_wipeout_scores_cull(self):
        # CA-2025-26: a 13+-strength Boyz squad (squad_id=3), all killed →
        # No Prisoners (2 VP) AND Cull the Horde (5 VP).
        squad = [
            _make_unit(f"Boy{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=20, squad_id=3)
            for i in range(10)
        ]
        snap = take_snapshot(squad)
        for u in squad:
            u.current_health = 0.0
        _, np_vp, cth, _ = score_round_delta(snap, squad)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)
        self.assertEqual(cth, CULL_THE_HORDE_VP_PER_UNIT)

    def test_partial_horde_squad_kill_scores_no_cull(self):
        # 20-model Boyz squad (squad_id=5), only 10 killed. Unit survives.
        survivors = [
            _make_unit(f"Boy{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=20, squad_id=5)
            for i in range(10)
        ]
        killed = [
            _make_unit(f"Boy{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=20, squad_id=5)
            for i in range(10)
        ]
        all_models = survivors + killed
        snap = take_snapshot(all_models)
        for u in killed:
            u.current_health = 0.0
        _, np_vp, cth, _ = score_round_delta(snap, all_models)
        self.assertEqual(np_vp, 0, "surviving squad members keep unit alive for No Prisoners")
        self.assertEqual(cth, 0, "surviving squad members keep unit alive for Cull")

    def test_two_squads_both_wiped_scores_two_units(self):
        # Two separate squads (squad_id=1 and squad_id=2) both fully wiped.
        # Should score 2 unit kills for No Prisoners. 2 × 3 VP = 6, but the
        # per-round cap is NO_PRISONERS_CAP_PER_ROUND (5), so result is 5.
        squad_a = [
            _make_unit(f"Ork{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=5, squad_id=1)
            for i in range(3)
        ]
        squad_b = [
            _make_unit(f"Grot{i}", alive=True, keywords=("INFANTRY",),
                       starting_strength=5, squad_id=2)
            for i in range(3)
        ]
        all_models = squad_a + squad_b
        snap = take_snapshot(all_models)
        for u in all_models:
            u.current_health = 0.0
        _, np_vp, _, _ = score_round_delta(snap, all_models)
        # 2 units destroyed × 3 VP = 6, capped to NO_PRISONERS_CAP_PER_ROUND.
        self.assertEqual(np_vp, min(NO_PRISONERS_CAP_PER_ROUND,
                                    2 * NO_PRISONERS_VP_PER_UNIT))

    def test_one_squad_wiped_one_squad_partial_scores_one_unit(self):
        # Squad A (squad_id=10) fully wiped; Squad B (squad_id=11) has 1
        # survivor. Only Squad A counts as destroyed.
        squad_a = [
            _make_unit(f"Ma{i}", alive=True, keywords=("INFANTRY",),
                       squad_id=10)
            for i in range(3)
        ]
        squad_b_survivor = _make_unit("Mb0", alive=True,
                                      keywords=("INFANTRY",), squad_id=11)
        squad_b_killed = _make_unit("Mb1", alive=True,
                                    keywords=("INFANTRY",), squad_id=11)
        all_models = squad_a + [squad_b_survivor, squad_b_killed]
        snap = take_snapshot(all_models)
        for u in squad_a:
            u.current_health = 0.0
        squad_b_killed.current_health = 0.0
        _, np_vp, _, _ = score_round_delta(snap, all_models)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT,
                         "only fully wiped squad counts as a unit kill")


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
        self.assertEqual(eng, ENGAGE_VP_THREE_QUADRANTS)   # CA-2025-26: 2 VP for 3 quarters

    def test_engage_four_quadrants_scores_top_tier_vp(self):
        # All four quadrants — score the top-tier 5 VP per real Pariah Nexus
        # Engage on All Fronts (2/3/5 VP for 2/3/4 quadrants).
        from code.secondaries import ENGAGE_VP_FOUR_QUADRANTS
        units = [
            _make_unit("sw", alive=True, position=(10.0, 10.0)),
            _make_unit("nw", alive=True, position=(10.0, 40.0)),
            _make_unit("ne", alive=True, position=(30.0, 40.0)),
            _make_unit("se", alive=True, position=(30.0, 10.0)),
        ]
        eng, _ = score_position_delta(units, _make_map(), own_is_army_a=True,
                                       round_num=1)
        self.assertEqual(eng, ENGAGE_VP_FOUR_QUADRANTS)

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
        self.assertEqual(bel, BEHIND_ENEMY_LINES_VP_SINGLE)   # CA-2025-26: 3 VP for ONE unit

    def test_behind_enemy_lines_army_b_perspective(self):
        # Army B's enemy DZ is the low-y strip (y <= deployment_width = 12).
        # Place one unit at y=5 (in enemy DZ for Army B). Side B round 1
        # (odd) = BEL active.
        unit = _make_unit("scout", alive=True, position=(22.0, 5.0))
        _, bel = score_position_delta(
            [unit], _make_map(), own_is_army_a=False, round_num=1,
        )
        self.assertEqual(bel, BEHIND_ENEMY_LINES_VP_SINGLE)   # CA-2025-26: 3 VP for ONE unit

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


class ChosenSecondariesGateTests(unittest.TestCase):
    """SECONDARY-SELECTION-V1: `chosen` gates score_round_delta and
    score_position_delta to the army's picked 2 Fixed + 2 Tactical."""

    def test_round_delta_chosen_none_defaults_to_all_fixed(self):
        # Backward compatibility: passing chosen=None scores all four kill-card
        # secondaries (the three valid CA-2025-26 Fixed picks plus no_prisoners,
        # which is Tactical-only in tournament play but is still a real scoring
        # card that the scorer knows how to evaluate).
        boyz = _make_unit("Boyz", alive=True,
                          keywords=("INFANTRY", "CHARACTER"),
                          starting_strength=20)
        snap = take_snapshot([boyz])
        boyz.current_health = 0.0
        bid, np_vp, cth, ass = score_round_delta(snap, [boyz])
        # No MV → bid=0; INFANTRY kill → No Prisoners; 20-model → Cull (CA-2025-26 13+);
        # CHARACTER → Assassination.
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)
        self.assertEqual(cth, CULL_THE_HORDE_VP_PER_UNIT)
        self.assertEqual(ass, ASSASSINATION_VP_PER_CHAR)

    def test_round_delta_chosen_empty_scores_nothing(self):
        # An army with NO Fixed Secondary picks scores 0 across the board.
        boyz = _make_unit("Boyz", alive=True,
                          keywords=("INFANTRY", "CHARACTER"),
                          starting_strength=10)
        snap = take_snapshot([boyz])
        boyz.current_health = 0.0
        bid, np_vp, cth, ass = score_round_delta(snap, [boyz], chosen=())
        self.assertEqual(bid, 0)
        self.assertEqual(np_vp, 0)
        self.assertEqual(cth, 0)
        self.assertEqual(ass, 0)

    def test_round_delta_chosen_no_prisoners_only(self):
        # An army that picked only No Prisoners + Cull does NOT score
        # Bring it Down or Assassination on a Monster+Character kill.
        mortarion = _make_unit("Mortarion", alive=True,
                                keywords=("MONSTER", "CHARACTER"))
        snap = take_snapshot([mortarion])
        mortarion.current_health = 0.0
        bid, np_vp, cth, ass = score_round_delta(
            snap, [mortarion],
            chosen=("no_prisoners", "cull_the_horde"),
        )
        self.assertEqual(bid, 0)  # Bring it Down not picked
        self.assertEqual(np_vp, NO_PRISONERS_VP_PER_UNIT)
        self.assertEqual(cth, 0)  # not a horde kill (strength=1)
        self.assertEqual(ass, 0)  # Assassination not picked

    def test_round_delta_warlord_bonus_gated_on_assassination_pick(self):
        # If Assassination is not picked, the +1 Warlord bonus is also
        # zeroed (the bonus only stacks on top of Assassination VP).
        warlord = _make_unit("Trajann", alive=True,
                              keywords=("CHARACTER", "INFANTRY"))
        snap = take_snapshot([warlord])
        warlord.current_health = 0.0
        _, _, _, ass = score_round_delta(
            snap, [warlord],
            enemy_warlord_uid=id(warlord),
            chosen=("no_prisoners",),
        )
        self.assertEqual(ass, 0)

    def test_position_delta_chosen_none_defaults_to_both_tactical(self):
        # Backward compat: chosen=None scores both Engage and BEL.
        units = [
            _make_unit("sw", alive=True, position=(10.0, 10.0)),
            _make_unit("nw", alive=True, position=(10.0, 40.0)),
            _make_unit("ne", alive=True, position=(30.0, 40.0)),
        ]
        eng, _ = score_position_delta(
            units, _make_map(), own_is_army_a=True, round_num=1,
        )
        self.assertEqual(eng, ENGAGE_VP_THREE_QUADRANTS)   # CA-2025-26: 2 VP for 3 quarters

    def test_position_delta_chosen_empty_scores_zero(self):
        units = [
            _make_unit("sw", alive=True, position=(10.0, 10.0)),
            _make_unit("nw", alive=True, position=(10.0, 40.0)),
            _make_unit("ne", alive=True, position=(30.0, 40.0)),
        ]
        eng, bel = score_position_delta(
            units, _make_map(), own_is_army_a=True, round_num=1,
            chosen=(),
        )
        self.assertEqual(eng, 0)
        self.assertEqual(bel, 0)

    def test_position_delta_chosen_bel_only_no_engage(self):
        # 3-quadrant spread would normally score Engage. With chosen=BEL
        # only, Engage is zeroed.
        units = [
            _make_unit("sw", alive=True, position=(10.0, 10.0)),
            _make_unit("nw", alive=True, position=(10.0, 40.0)),
            _make_unit("ne", alive=True, position=(30.0, 40.0)),
        ]
        eng, _ = score_position_delta(
            units, _make_map(), own_is_army_a=True, round_num=1,
            chosen=("behind_enemy_lines",),
        )
        self.assertEqual(eng, 0)


class PickSecondariesTests(unittest.TestCase):
    """SECONDARY-SELECTION-V1: `pick_secondaries` chooses 2 Fixed + 2
    Tactical secondaries per army based on roster shape."""

    def _make_army(self, units):
        # Minimal Army stand-in: pick_secondaries reads `army.units` and
        # each unit's profile.unit_keywords. Avoid spinning up the real
        # Army class to keep the test free of detachment / catalogue side
        # effects.
        return SimpleNamespace(units=list(units))

    def test_picker_returns_fixed_tactical_and_board_keys(self):
        own = self._make_army([_make_unit("Marine", alive=True,
                                            keywords=("INFANTRY",))])
        enemy = self._make_army([_make_unit("Marine", alive=True,
                                              keywords=("INFANTRY",))])
        picks = pick_secondaries(own, enemy)
        # First two are Fixed, next two are Tactical (Engage/BEL). A single
        # non-chaff unit adds no Cleanse/Sabotage. Wave 83: the objective-
        # holding / board-control package is always appended (inert unless
        # SWEG_TIER_A is on at scoring time).
        self.assertEqual(len(picks), 2 + 2 + len(BOARD_SECONDARY_KEYS))
        for k in picks[:2]:
            self.assertIn(k, FIXED_SECONDARY_KEYS)
        self.assertIn("engage_on_all_fronts", picks)
        self.assertIn("behind_enemy_lines", picks)
        for k in BOARD_SECONDARY_KEYS:
            self.assertIn(k, picks)

    def test_picker_picks_bring_it_down_vs_vehicle_heavy_enemy(self):
        own = self._make_army([_make_unit("Marine", alive=True,
                                            keywords=("INFANTRY",))])
        enemy = self._make_army([
            _make_unit(f"Tank{i}", alive=True, keywords=("VEHICLE",))
            for i in range(3)
        ])
        picks = pick_secondaries(own, enemy)
        self.assertIn("bring_it_down", picks)

    def test_picker_picks_cull_the_horde_vs_infantry_enemy(self):
        # No Prisoners is a Tactical-only card in CA-2025-26 tournament play and
        # must NOT appear as a Fixed pick. Against an infantry-only enemy (no
        # MONSTER/VEHICLE, no CHARACTERs), both Fixed slots resolve to
        # cull_the_horde.
        own = self._make_army([_make_unit("Marine", alive=True,
                                            keywords=("INFANTRY",))])
        enemy = self._make_army([
            _make_unit(f"Boyz{i}", alive=True, keywords=("INFANTRY",))
            for i in range(5)
        ])
        picks = pick_secondaries(own, enemy)
        self.assertNotIn("no_prisoners", picks[:2])  # not in Fixed slots
        self.assertNotIn("bring_it_down", picks)
        self.assertIn("cull_the_horde", picks)  # fallback Fixed slot 1

    def test_picker_picks_bel_for_mobile_army(self):
        # 3+ FLY/MOUNT units → behind_enemy_lines comes first in tactical.
        own = self._make_army([
            _make_unit(f"Reaver{i}", alive=True, keywords=("FLY",))
            for i in range(3)
        ])
        enemy = self._make_army([_make_unit("Marine", alive=True,
                                              keywords=("INFANTRY",))])
        picks = pick_secondaries(own, enemy)
        self.assertIn("behind_enemy_lines", picks)
        self.assertIn("engage_on_all_fronts", picks)

    def test_picker_deterministic_for_same_input(self):
        own = self._make_army([_make_unit("Marine", alive=True,
                                            keywords=("INFANTRY",))])
        enemy = self._make_army([_make_unit("Marine", alive=True,
                                              keywords=("INFANTRY",))])
        picks_a = pick_secondaries(own, enemy)
        picks_b = pick_secondaries(own, enemy)
        self.assertEqual(picks_a, picks_b)


if __name__ == "__main__":
    unittest.main()
