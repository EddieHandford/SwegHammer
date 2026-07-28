"""LENS: target selection & durability-crack, AM vs Death Guard.
Read-only probe. Not committed to production.

Instruments 10 seeds of AM-vs-DeathGuard using the eval-faithful
reproduction from scripts/_am_advance_probe.py. For each game, tally:
  - which AM unit shot at which DG unit, how much damage, and DG unit's
    remaining/starting health (durability-crack signal)
  - DG unit destroyed counts and who killed them
  - final state of AM's expensive units (Rogal Dorn, Basilisk, Manticore)
  - DG's targeting of AM's characters / tanks / command squads
"""
from __future__ import annotations
import random, sys
from collections import defaultdict
from code.army_builder import build_faction_random_army
from code.events import (BattleStarted, RoundStarted, UnitShot, UnitKilled,
                          UnitFought, EventLog)
from code.simulator import Battle
from code.roles import classify
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
_idx = {f: i for i, f in enumerate(FACTIONS)}

KEY_AM_NAMES = ("Rogal Dorn", "Basilisk", "Manticore", "Lord Solar", "Leman Russ",
                "Tank Commander", "Command Squad")

for seed in range(N):
    ps = (_idx['Astra Militarum']*1000 + _idx['Death Guard'])*100 + seed
    random.seed(ps)
    a = build_faction_random_army('A', 'Astra Militarum', 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army('B', 'Death Guard', 2000, rng=random.Random(seed+10000), use_archetype=True)
    lg = EventLog(); map_ = _pick_rotation_map(seed); pr = _pick_primary_mission(ps)
    Battle(a, b, subscribers=[lg], map_=map_, primary_mission=pr).run()
    ev = lg.events

    name_of = {}; army_of = {}; maxhp_of = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                name_of[u.uid] = u.name
                army_of[u.uid] = u.army
                maxhp_of[u.uid] = u.max_health

    a_win = None
    a_hp_start = sum(u.current_health for u in a.units)  # placeholder, replaced below
    a_alive_end = sum(1 for u in a.units if u.current_health > 0)
    b_alive_end = sum(1 for u in b.units if u.current_health > 0)

    # figure winner via final objective VP - approximate via ObjectiveScored totals
    from code.events import ObjectiveScored
    vp_a = 0; vp_b = 0
    for e in ev:
        if isinstance(e, ObjectiveScored):
            if e.army_name == 'A':
                vp_a += e.vp_awarded
            elif e.army_name == 'B':
                vp_b += e.vp_awarded
    winner = 'A' if vp_a > vp_b else ('B' if vp_b > vp_a else 'TIE')

    if winner != 'A':
        print(f"\n===== seed {seed}  AM LOSES ({vp_a} vp vs {vp_b} vp)  map={map_.name if hasattr(map_,'name') else '?'} =====")
    else:
        print(f"\n===== seed {seed}  AM WINS ({vp_a} vp vs {vp_b} vp) =====")

    # per-round shooting tally: AM shots at DG targets, DG shots at AM targets
    cur_round = 0
    am_dmg_to_target = defaultdict(float)   # target_uid -> total damage from AM
    dg_dmg_to_target = defaultdict(float)
    am_shots_by_attacker_target = defaultdict(float)  # (attacker_name, target_name)-> dmg
    dg_shots_by_attacker_target = defaultdict(float)
    kills = []  # (round, victim_uid, army)

    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, (UnitShot, UnitFought)):
            att_army = army_of.get(e.attacker_uid)
            tgt_army = army_of.get(e.target_uid)
            att_name = name_of.get(e.attacker_uid, '?')
            tgt_name = name_of.get(e.target_uid, '?')
            if att_army == 'A':
                am_dmg_to_target[e.target_uid] += e.damage
                am_shots_by_attacker_target[(att_name, tgt_name)] += e.damage
            elif att_army == 'B':
                dg_dmg_to_target[e.target_uid] += e.damage
                dg_shots_by_attacker_target[(att_name, tgt_name)] += e.damage
        elif isinstance(e, UnitKilled):
            kills.append((cur_round, e.unit_uid, army_of.get(e.unit_uid)))

    # Only detail the losing seeds heavily; still print a compact kill list always
    print(f"  kills: {[(r, name_of.get(u,'?'), army) for r,u,army in kills]}")

    if winner != 'A':
        print("  -- AM weapons -> DG targets (total damage) --")
        for (att, tgt), dmg in sorted(am_shots_by_attacker_target.items(), key=lambda kv: -kv[1])[:15]:
            print(f"    {att:28s} -> {tgt:28s} : {dmg:6.1f} dmg")
        print("  -- DG weapons -> AM targets (total damage) --")
        for (att, tgt), dmg in sorted(dg_shots_by_attacker_target.items(), key=lambda kv: -kv[1])[:15]:
            print(f"    {att:28s} -> {tgt:28s} : {dmg:6.1f} dmg")

        # key AM units status at end
        print("  -- key AM unit end-state --")
        for u in a.units:
            if any(k in u.profile.name for k in KEY_AM_NAMES):
                dmg_taken = maxhp_of.get(u.uid, u.current_health) - u.current_health
                print(f"    {u.profile.name:28s} hp {u.current_health:.0f}/{maxhp_of.get(u.uid,'?')}"
                      f"  dmg_taken={dmg_taken:.1f}  alive={u.current_health>0}  pos={u.position}")

        # DG durable units status at end (Plagueburst / Terminators / etc)
        print("  -- DG unit end-state (all) --")
        for u in b.units:
            print(f"    {u.profile.name:28s} hp {u.current_health:.0f}/{maxhp_of.get(u.uid,'?')}"
                  f"  alive={u.current_health>0}")
