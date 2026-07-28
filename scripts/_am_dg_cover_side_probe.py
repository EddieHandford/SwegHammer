"""Lens: deployment & cover-side positioning in AM-vs-Death-Guard games.
Checks: deployment-centroid side (left/right half of board width), whether
both armies cluster on the same flank, whether AM shooting bodies sit in
cover terrain at deploy and rounds 2-3, cover footprint available per half,
and whether the AI ever picks the worse-cover side. Read-only scratch probe.
"""
from __future__ import annotations
import random, sys
from collections import defaultdict
from code.army_builder import build_faction_random_army
from code.events import BattleStarted, RoundStarted, UnitMoved, EventLog
from code.simulator import Battle
from code.map import TerrainType
from code.roles import classify
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC = "Astra Militarum"
B_FAC = "Death Guard"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
_idx = {f: i for i, f in enumerate(FACTIONS)}

COVER_TYPES = (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.RUIN)


def footprint_area(t):
    return t.width * t.height


def cover_area_by_half(map_):
    w = map_.width
    left = 0.0
    right = 0.0
    for t in map_.terrain:
        if t.type not in COVER_TYPES:
            continue
        # split rectangle area by the x = w/2 line (approx: assign by rect centre
        # if it doesn't straddle, else split proportionally)
        x0, x1 = t.x, t.x2
        area = footprint_area(t)
        if x1 <= w / 2:
            left += area
        elif x0 >= w / 2:
            right += area
        else:
            frac_left = (w / 2 - x0) / (x1 - x0)
            left += area * frac_left
            right += area * (1 - frac_left)
    return left, right


def in_cover_terrain(map_, pos):
    for t in map_.terrain:
        if t.type in COVER_TYPES and t.contains(pos):
            return True
    return False


def centroid_side(units, w):
    """units: list of (x,y) on-board positions only (reserve/deep-strike
    sentinel positions such as (-100,-100) are excluded by the caller)."""
    if not units:
        return None, None
    cx = sum(p[0] for p in units) / len(units)
    return cx, ("L" if cx < w / 2 else "R")


def on_board(pos, w, h):
    x, y = pos
    return 0.0 <= x <= w and 0.0 <= y <= h


for seed in range(N):
    ps = (_idx[A_FAC] * 1000 + _idx[B_FAC]) * 100 + seed
    random.seed(ps)
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    lg = EventLog()
    map_ = _pick_rotation_map(seed)
    pr = _pick_primary_mission(ps)
    battle = Battle(a, b, subscribers=[lg], map_=map_, primary_mission=pr)
    battle.run()
    ev = lg.events

    w = map_.width
    left_area, right_area = cover_area_by_half(map_)

    # deploy positions from BattleStarted snapshot (exclude reserve/deep-strike
    # sentinel positions like (-100,-100) which are not real on-board deployment)
    deploy_pos = {"A": [], "B": []}
    reserved = {"A": 0, "B": 0}
    name_of = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                name_of[u.uid] = u.name
                if on_board(u.position, w, map_.height):
                    deploy_pos[u.army].append(u.position)
                else:
                    reserved[u.army] += 1

    a_cx, a_side = centroid_side(deploy_pos["A"], w)
    b_cx, b_side = centroid_side(deploy_pos["B"], w)
    a_xs = [p[0] for p in deploy_pos["A"]]
    b_xs = [p[0] for p in deploy_pos["B"]]
    a_spread = (min(a_xs), max(a_xs)) if a_xs else (None, None)
    b_spread = (min(b_xs), max(b_xs)) if b_xs else (None, None)

    # AM shooting-body cover at deploy (from snapshot positions) and by round 2/3
    # (from live unit final round-2/3 positions requires tracking UnitMoved per round)
    a_shoot_uids = {u.uid for u in a.units if classify(u.profile) in ("SHOOTY", "HEAVY", "HORDE")}
    a_deploy_cover = 0
    a_deploy_total = 0
    for uid, name in name_of.items():
        pass
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                if u.army == "A" and u.uid in a_shoot_uids:
                    a_deploy_total += 1
                    if in_cover_terrain(map_, u.position):
                        a_deploy_cover += 1

    # track positions by round (last known position as of end of round N)
    pos_by_round = defaultdict(dict)  # round -> uid -> pos
    cur_round = 0
    last_pos = {}
    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, UnitMoved):
            last_pos[e.unit_uid] = e.to_pos
            pos_by_round[cur_round][e.unit_uid] = e.to_pos

    # snapshot cumulative last-known-pos as of end of round 2 and round 3
    def cover_at_round(rnd):
        snap = dict(last_pos)  # will overwrite below with correct cumulative
        cum = {}
        for r in range(1, rnd + 1):
            cum.update(pos_by_round.get(r, {}))
        cov = 0
        tot = 0
        for uid in a_shoot_uids:
            if uid in cum:
                tot += 1
                if in_cover_terrain(map_, cum[uid]):
                    cov += 1
        return cov, tot

    r2_cov, r2_tot = cover_at_round(2)
    r3_cov, r3_tot = cover_at_round(3)

    same_side = "SAME" if a_side == b_side else "DIFF"
    worse_side_A = "R" if left_area > right_area else "L"  # side with LESS cover
    worse_side_B = worse_side_A
    a_picked_worse = (a_side == worse_side_A) if a_side else None
    b_picked_worse = (b_side == worse_side_B) if b_side else None

    print(f"seed={seed} map={map_.name} width={w:.1f} left_cover_area={left_area:.1f} right_cover_area={right_area:.1f} "
          f"better_side={'L' if left_area>right_area else ('R' if right_area>left_area else 'TIE')}")
    print(f"  A(AM) centroid_x={a_cx:.1f} x_range={a_spread} side={a_side} reserved={reserved['A']} picked_worse_cover_side={a_picked_worse}")
    print(f"  B(DG) centroid_x={b_cx:.1f} x_range={b_spread} side={b_side} reserved={reserved['B']} picked_worse_cover_side={b_picked_worse}")
    print(f"  side_clustering={same_side}")
    print(f"  AM shooting-body cover: deploy={a_deploy_cover}/{a_deploy_total} "
          f"round2={r2_cov}/{r2_tot} round3={r3_cov}/{r3_tot}")
