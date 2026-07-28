"""Read-only probe: AM vs Death Guard objective PRESENCE & primary-VP trajectory
on the dense-terrain default. Reproduces games exactly per the orchestrator's
prescribed harness. Instruments per-round: ObjectiveScored (a_oc/b_oc per marker,
who scored) and RoundEnded VP totals (capped), plus AM unit deaths per round and
terrain occupancy at battle end. Not committed; scratch only."""
from __future__ import annotations
import random, sys
from collections import defaultdict
from code.army_builder import build_faction_random_army
from code.events import (
    EventLog, BattleStarted, RoundStarted, RoundEnded, ObjectiveScored,
    UnitKilled, UnitMoved,
)
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
_idx = {f: i for i, f in enumerate(FACTIONS)}
A_FAC, B_FAC = "Astra Militarum", "Death Guard"

def dist2(p, q):
    return (p[0]-q[0])**2 + (p[1]-q[1])**2

for seed in range(N):
    ps = (_idx[A_FAC]*1000 + _idx[B_FAC])*100 + seed
    random.seed(ps)
    a = build_faction_random_army('A', A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army('B', B_FAC, 2000, rng=random.Random(seed+10000), use_archetype=True)
    lg = EventLog()
    map_ = _pick_rotation_map(seed)
    pr = _pick_primary_mission(ps)
    battle = Battle(a, b, subscribers=[lg], map_=map_, primary_mission=pr)
    battle.run()
    ev = lg.events

    winner = None
    a_name_lookup = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                a_name_lookup[u.uid] = (u.army, u.name)

    cur_round = 0
    round_obj = defaultdict(list)  # round -> list of (obj_name, army_name_scored, a_oc, b_oc)
    round_vp = {}  # round -> (a_vp_capped, b_vp_capped)
    kills_by_round = defaultdict(lambda: [0, 0])  # round -> [A killed, B killed]

    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, ObjectiveScored):
            round_obj[cur_round].append((e.objective_name, e.army_name, e.a_oc, e.b_oc))
        elif isinstance(e, RoundEnded):
            round_vp[e.round_num] = (e.a_vp_capped, e.b_vp_capped)
        elif isinstance(e, UnitKilled):
            army, name = a_name_lookup.get(e.unit_uid, (None, None))
            if army == 'A':
                kills_by_round[cur_round][0] += 1
            elif army == 'B':
                kills_by_round[cur_round][1] += 1

    final_a_vp, final_b_vp = round_vp.get(max(round_vp) if round_vp else 0, (0, 0))
    outcome = "A-WIN" if final_a_vp > final_b_vp else ("B-WIN" if final_b_vp > final_a_vp else "DRAW")

    print(f"\n===== seed {seed}  map={map_.name if hasattr(map_,'name') else '?'} primary={pr}  outcome={outcome} (AM={final_a_vp} DG={final_b_vp}) =====")
    objs = map_.objectives
    print(f"  objectives: {[(o.x, o.y, o.control_radius) for o in objs]}")
    for rnd in sorted(round_obj.keys()):
        entries = round_obj[rnd]
        am_present_count = sum(1 for (_, army, a_oc, b_oc) in entries if a_oc > 0)
        am_control_count = sum(1 for (_, army, _, _) in entries if army == 'A')
        dg_control_count = sum(1 for (_, army, _, _) in entries if army == 'B')
        vp = round_vp.get(rnd, ('?', '?'))
        ak, bk = kills_by_round.get(rnd, [0,0])
        detail = "; ".join(f"{name}:A_oc={a_oc},B_oc={b_oc},scored={army}" for (name, army, a_oc, b_oc) in entries)
        print(f"  R{rnd}: AM controls {am_control_count}/{len(entries)} markers, AM-present(oc>0) {am_present_count}/{len(entries)}, DG controls {dg_control_count}  | VP so far AM={vp[0]} DG={vp[1]}  | kills-this-round AM_lost={ak} DG_lost={bk}")
        print(f"        {detail}")

    # end-of-game AM unit state: alive/dead, distance to nearest objective
    print("  end-of-game AM units:")
    for u in a.units:
        alive = u.current_health > 0
        if objs:
            best = min(objs, key=lambda o: dist2(u.position, (o.x, o.y)))
            d = dist2(u.position, (best.x, best.y)) ** 0.5
            on = d <= best.control_radius
        else:
            d, on = None, None
        print(f"    {u.profile.name:28s} alive={alive!s:5} hp={u.current_health:5.1f} pos={u.position} dist_to_nearest_obj={d:.1f} on_marker={on}")
