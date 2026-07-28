"""LENS: kill exchange / where AM's bodies die, AM vs Death Guard.
Read-only probe. Reproduces games exactly like scripts/_am_advance_probe.py /
the eval harness (real archetype armies, dense terrain default-on).

Per seed, per round: AM models alive vs DG models alive, AM units destroyed
that round + role/name + position (near an objective marker or in the open),
and whether AM commits piecemeal (few units advance into DG guns each round)
or together. Also tallies UnitShot/UnitFought damage landing on AM broken
down by DG source-unit name, to see if a small number of DG units are doing
outsized grinding.
"""
from __future__ import annotations
import random, sys
from collections import defaultdict
from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, UnitShot, UnitFought,
    UnitKilled, UnitMoved, UnitAdvanced, ObjectiveScored, EventLog,
)
from code.simulator import Battle
from code.roles import classify
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
_idx = {f: i for i, f in enumerate(FACTIONS)}

def dist(p, q):
    return ((p[0]-q[0])**2 + (p[1]-q[1])**2) ** 0.5

results = []

for seed in range(N):
    ps = (_idx['Astra Militarum']*1000 + _idx['Death Guard'])*100 + seed
    random.seed(ps)
    a = build_faction_random_army('A', 'Astra Militarum', 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army('B', 'Death Guard', 2000, rng=random.Random(seed+10000), use_archetype=True)
    lg = EventLog(); map_ = _pick_rotation_map(seed); pr = _pick_primary_mission(ps)
    battle = Battle(a, b, subscribers=[lg], map_=map_, primary_mission=pr)
    r = battle.run()
    ev = lg.events

    name_of = {}; army_of = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                name_of[u.uid] = u.name
                army_of[u.uid] = u.army

    role_of = {u.uid: classify(u.profile) for u in a.units}
    role_of.update({u.uid: classify(u.profile) for u in b.units})
    pos_at_death = {}  # unit_uid -> last known position before death
    last_pos = {}

    cur_round = 0
    alive_a = set(u.uid for u in a.units)
    alive_b = set(u.uid for u in b.units)
    killed_this_round = defaultdict(list)  # round -> [uid,...] (any army)
    dmg_to_a_by_source = defaultdict(float)  # dg unit name -> damage dealt to AM units
    moved_a_by_round = defaultdict(set)
    advanced_a_by_round = defaultdict(set)
    round_alive_counts = []  # (round, a_alive, b_alive)
    objs = map_.objectives

    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, UnitMoved):
            last_pos[e.unit_uid] = e.to_pos
            if army_of.get(e.unit_uid) == 'A':
                moved_a_by_round[cur_round].add(e.unit_uid)
        elif isinstance(e, UnitAdvanced):
            if army_of.get(e.unit_uid) == 'A':
                advanced_a_by_round[cur_round].add(e.unit_uid)
        elif isinstance(e, (UnitShot, UnitFought)):
            if army_of.get(e.target_uid) == 'A' and army_of.get(e.attacker_uid) == 'B':
                dmg_to_a_by_source[name_of.get(e.attacker_uid, e.attacker_uid)] += e.damage
            if not e.target_alive_after:
                pos_at_death.setdefault(e.target_uid, last_pos.get(e.target_uid))
        elif isinstance(e, UnitKilled):
            killed_this_round[cur_round].append(e.unit_uid)
            if e.unit_uid in alive_a: alive_a.discard(e.unit_uid)
            if e.unit_uid in alive_b: alive_b.discard(e.unit_uid)
        elif isinstance(e, RoundEnded):
            round_alive_counts.append((cur_round, len(alive_a), len(alive_b)))

    print(f"\n=== seed {seed}  map={getattr(map_,'name',map_)}  primary={pr if isinstance(pr,str) else getattr(pr,'name',pr)} ===")
    print(f"  winner={r.winner}  a_vp={getattr(r,'a_vp',None)} b_vp={getattr(r,'b_vp',None)}")
    print(f"  alive-count curve (round, A_alive, B_alive): {round_alive_counts}")

    for rnd in sorted(killed_this_round):
        a_dead = [uid for uid in killed_this_round[rnd] if army_of.get(uid) == 'A']
        b_dead = [uid for uid in killed_this_round[rnd] if army_of.get(uid) == 'B']
        if a_dead:
            details = []
            for uid in a_dead:
                p = pos_at_death.get(uid)
                near = None
                if p:
                    for o in objs:
                        d = dist(p, (o.x, o.y))
                        if d <= o.control_radius + 3:
                            near = f"obj@({o.x:.0f},{o.y:.0f}) d={d:.1f}"
                            break
                details.append(f"{name_of.get(uid,uid)}[{role_of.get(uid,'?')}] pos={p} {near or 'OPEN'}")
            print(f"  R{rnd} AM LOST {len(a_dead)}: " + " | ".join(details))
        if b_dead:
            print(f"  R{rnd} DG lost {len(b_dead)}: " + ", ".join(name_of.get(uid,uid) for uid in b_dead))
        a_moved = moved_a_by_round.get(rnd, set())
        a_adv = advanced_a_by_round.get(rnd, set())
        if a_moved:
            print(f"  R{rnd} AM moved {len(a_moved)} units, {len(a_adv)} of them Advanced")

    top_src = sorted(dmg_to_a_by_source.items(), key=lambda kv: -kv[1])[:6]
    print(f"  damage-to-AM by DG source unit (top6): {[(n, round(d,1)) for n,d in top_src]}")

    results.append({
        'seed': seed, 'winner': r.winner,
        'curve': round_alive_counts,
    })

print("\n\n## SUMMARY across seeds")
for r in results:
    print(r)
