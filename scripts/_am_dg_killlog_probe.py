"""Read-only: per-round kill log (attacker name -> target name) + terrain rects,
for specific AM-vs-Death-Guard seeds, to see WHO is killing AM off-objective."""
from __future__ import annotations
import random, sys
from collections import defaultdict
from code.army_builder import build_faction_random_army
from code.events import EventLog, BattleStarted, RoundStarted, UnitShot, UnitFought, UnitKilled
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

SEEDS = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1, 2, 5, 7]
_idx = {f: i for i, f in enumerate(FACTIONS)}
A_FAC, B_FAC = "Astra Militarum", "Death Guard"

for seed in SEEDS:
    ps = (_idx[A_FAC]*1000 + _idx[B_FAC])*100 + seed
    random.seed(ps)
    a = build_faction_random_army('A', A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army('B', B_FAC, 2000, rng=random.Random(seed+10000), use_archetype=True)
    lg = EventLog()
    map_ = _pick_rotation_map(seed)
    pr = _pick_primary_mission(ps)
    Battle(a, b, subscribers=[lg], map_=map_, primary_mission=pr).run()
    ev = lg.events

    name_of = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                name_of[u.uid] = f"{u.army}:{u.name}"

    print(f"\n===== seed {seed} map={map_.name} =====")
    print("terrain rects (x,y,w,h,type):")
    for t in map_.terrain:
        print(f"   {t.x},{t.y},{t.width},{t.height},{t.terrain_type if hasattr(t,'terrain_type') else t}")

    cur = 0
    kill_log = defaultdict(list)  # round -> list of "killer -> victim"
    dmg_by_attacker_round = defaultdict(lambda: defaultdict(float))  # round -> attacker_name -> total dmg to A units
    for e in ev:
        if isinstance(e, RoundStarted):
            cur = e.round_num
        elif isinstance(e, (UnitShot, UnitFought)):
            atk = name_of.get(e.attacker_uid, e.attacker_uid)
            tgt = name_of.get(e.target_uid, e.target_uid)
            if tgt.startswith("A:"):
                dmg_by_attacker_round[cur][atk] += e.damage
            if not e.target_alive_after:
                kill_log[cur].append(f"{atk} -> {tgt}")

    for rnd in sorted(kill_log.keys()):
        print(f" R{rnd} kills: {kill_log[rnd]}")
    print(" damage dealt TO army A, by attacker, per round:")
    for rnd in sorted(dmg_by_attacker_round.keys()):
        top = sorted(dmg_by_attacker_round[rnd].items(), key=lambda kv: -kv[1])[:6]
        print(f"   R{rnd}: {top}")
