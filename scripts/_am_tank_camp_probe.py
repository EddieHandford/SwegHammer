"""Instrument-before-build probe (LEVER_PROTOCOL §1) for the proposed AM
HEAVY-VEHICLE forward-staging lever. Measures how often AM battle tanks camp off
all objective markers while a REACHABLE non-AM marker exists — the exact condition
the lever would fix. Splits battle tanks (HEAVY + VEHICLE + not indirect_fire) from
artillery (indirect — which SHOULD camp, a control). Reflects current defaults
(dedupe ON). Read-only. Not committed.

Usage: python -m scripts._am_tank_camp_probe [N_seeds]"""
from __future__ import annotations
import random, sys

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, UnitMoved, EventLog,
)
from code.simulator import Battle
from code.roles import classify
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC = "Astra Militarum"
OPPONENTS = ["Necrons", "Adeptus Astartes", "Adeptus Custodes", "Death Guard",
             "Thousand Sons", "Aeldari", "Orks", "Genestealer Cults"]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
_fac_idx = {f: i for i, f in enumerate(FACTIONS)}
SCORING_ROUNDS = (2, 3, 4, 5)


def _d(p, q):
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


def _oc(u):
    return getattr(u.profile, "oc", 0) or 0


def _controller(obj, a_units, b_units):
    a = sum(_oc(u) for u in a_units if u.current_health > 0 and _d(u.position, (obj.x, obj.y)) <= obj.control_radius)
    b = sum(_oc(u) for u in b_units if u.current_health > 0 and _d(u.position, (obj.x, obj.y)) <= obj.control_radius)
    return "A" if a > b else ("B" if b > a else "0")


# aggregate counters
agg = {"bt_tanks": 0, "bt_tank_games": 0, "bt_camp_all_game": 0, "bt_camp_all_with_work": 0,
       "bt_round_states": 0, "bt_camp_rounds": 0, "bt_camp_rounds_with_work": 0,
       "bt_moves_total": 0, "art_tanks": 0, "art_camp_all_game": 0}

for opp in OPPONENTS:
    for seed in range(N):
        pair_seed = (_fac_idx[A_FAC] * 1000 + _fac_idx[opp]) * 100 + seed
        random.seed(pair_seed)
        a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
        lg = EventLog()
        map_ = _pick_rotation_map(seed)
        primary = _pick_primary_mission(pair_seed)
        Battle(a, b, subscribers=[lg], map_=map_, primary_mission=primary).run()
        ev = lg.events
        objs = map_.objectives

        # AM HEAVY VEHICLE tanks
        tanks = []
        for u in a.units:
            kw = set(u.profile.unit_keywords or ())
            if classify(u.profile) == "HEAVY" and "VEHICLE" in kw:
                indirect = bool(getattr(u.profile, "indirect_fire", False))
                tanks.append((u, indirect))
        if not tanks:
            continue

        # reconstruct per-round positions per tank uid from UnitMoved
        tank_uids = {u.uid for u, _ in tanks}
        deploy = {}       # uid -> first from_pos
        moves = {}        # uid -> {round: to_pos}
        move_count = {u.uid: 0 for u, _ in tanks}
        cur = 0
        for e in ev:
            if isinstance(e, RoundStarted):
                cur = e.round_num
            elif isinstance(e, UnitMoved) and e.unit_uid in tank_uids:
                deploy.setdefault(e.unit_uid, e.from_pos)
                moves.setdefault(e.unit_uid, {})[cur] = e.to_pos
                move_count[e.unit_uid] += 1

        # final controller per objective (from final alive positions)
        final_ctrl = [_controller(o, a.units, b.units) for o in objs]

        for u, indirect in tanks:
            uid = u.uid
            start = deploy.get(uid, u.position)   # never moved -> final == deploy
            # per-round position by carry-forward
            pos_by_round = {}
            last = start
            for r in range(1, 6):
                if uid in moves and r in moves[uid]:
                    last = moves[uid][r]
                pos_by_round[r] = last
            all_positions = [start] + list((moves.get(uid) or {}).values())
            ever_on_marker = any(_d(p, (o.x, o.y)) <= o.control_radius for p in all_positions for o in objs)

            if indirect:
                agg["art_tanks"] += 1
                if not ever_on_marker:
                    agg["art_camp_all_game"] += 1
                continue

            # battle tank
            agg["bt_tanks"] += 1
            agg["bt_moves_total"] += move_count[uid]
            camped_all = not ever_on_marker
            # reachable non-AM marker at end (within 2*move of final position)
            mv = (getattr(u.profile, "move", 6) or 6)
            fpos = pos_by_round[5]
            reach_work = any(final_ctrl[i] != "A" and _d(fpos, (o.x, o.y)) <= 2 * mv
                             for i, o in enumerate(objs))
            if camped_all:
                agg["bt_camp_all_game"] += 1
                if reach_work:
                    agg["bt_camp_all_with_work"] += 1
            # per-round camping
            for r in SCORING_ROUNDS:
                agg["bt_round_states"] += 1
                p = pos_by_round[r]
                off_all = all(_d(p, (o.x, o.y)) > o.control_radius for o in objs)
                if off_all:
                    agg["bt_camp_rounds"] += 1
                    if any(final_ctrl[i] != "A" and _d(p, (o.x, o.y)) <= 2 * mv for i, o in enumerate(objs)):
                        agg["bt_camp_rounds_with_work"] += 1

bt = max(agg["bt_tanks"], 1)
rs = max(agg["bt_round_states"], 1)
art = max(agg["art_tanks"], 1)
camp_all = agg["bt_camp_all_game"]
print(f"# AM HEAVY-VEHICLE tank camping probe — {len(OPPONENTS)} opponents x {N} seeds")
print(f"# BATTLE TANKS (HEAVY+VEHICLE, not indirect): {agg['bt_tanks']} tank-instances")
print(f"  mean moves per tank over the game:           {agg['bt_moves_total']/bt:.2f}")
print(f"  camped ALL game (never touched a marker):    {camp_all}/{bt} = {100*camp_all/bt:.0f}%")
print(f"    ...of those, a reachable non-AM marker existed at end: {agg['bt_camp_all_with_work']}/{max(camp_all,1)} = {100*agg['bt_camp_all_with_work']/max(camp_all,1):.0f}%")
print(f"  per-round (scoring rounds 2-5) OFF all markers:       {agg['bt_camp_rounds']}/{rs} = {100*agg['bt_camp_rounds']/rs:.0f}%")
print(f"    ...AND a reachable non-AM marker existed (LEVER HEADROOM): {agg['bt_camp_rounds_with_work']}/{rs} = {100*agg['bt_camp_rounds_with_work']/rs:.0f}%")
print(f"# ARTILLERY control (HEAVY+VEHICLE, indirect — SHOULD camp): {agg['art_tanks']} instances, camped-all-game {100*agg['art_camp_all_game']/art:.0f}%")
