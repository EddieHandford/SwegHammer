"""DG-CRATER objective trace (read-only): for a handful of Death Guard vs
Thousand Sons anchor games (Death Guard wins), dump per-round objective control
(Objective Control on each marker, who scored) and the end-of-battle survivor
composition on each side, split by whether the survivor is a scoring body sitting
on an objective or a stranded/back-line unit.

The point: test whether the elite-infantry side (which starts with MORE bodies
than Death Guard and often ends with MORE survivors) actually converts those
bodies into objective control, or whether its surviving units are stranded off
the objectives while Death Guard's durable Plague Marines camp them.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dgcrater_objtrace [opp] [seed ...]
"""
from __future__ import annotations
import json, os, random, sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._dgcrater_objtrace"] + sys.argv[1:],
        env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.events import (BattleStarted, RoundStarted, RoundEnded, ObjectiveScored,
                         UnitKilled, EventLog)
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

DG = "Death Guard"
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}


def _dist(a, b):
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5


def replay(a_fac, b_fac, s):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    ps = (ai*1000+bi)*100+s
    random.seed(ps)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s+10000), use_archetype=True)
    bm = _pick_rotation_map(s); pm = _pick_primary_mission(ps)
    log = EventLog()
    battle = Battle(a, b, map_=bm, rules=None, primary_mission=pm, subscribers=[log])
    res = battle.run()
    return res, log, battle


def trace(a_fac, b_fac, s):
    res, log, battle = replay(a_fac, b_fac, s)
    dg_side = "A" if a_fac == DG else "B"
    opp_side = "B" if dg_side == "A" else "A"
    opp_fac = b_fac if a_fac == DG else a_fac
    print(f"\n############ DG vs {opp_fac}  seed={s}  winner={res.winner} "
          f"({'DG WIN' if res.winner==dg_side else 'opp win'})  rounds={res.rounds} "
          f"plague={getattr(battle.a if dg_side=='A' else battle.b,'dg_chosen_plague',None)}")
    # per round: objective scoring
    cur = 0
    for e in log.events:
        if isinstance(e, RoundStarted):
            cur = e.round_num
            print(f"  --- round {cur} ---")
        elif isinstance(e, ObjectiveScored):
            dg_oc = e.a_oc if dg_side == "A" else e.b_oc
            opp_oc = e.b_oc if dg_side == "A" else e.a_oc
            scorer = "DG" if e.army_name == (battle.a.name if dg_side=="A" else battle.b.name) else \
                     ("opp" if e.army_name else "contested/none")
            print(f"     {e.objective_name:<14} scored_by={scorer:<14} OC  DG {dg_oc:2d} : {opp_oc:2d} opp   (+{e.vp_awarded})")
    # end survivor composition, on/off objective
    objs = getattr(battle, "objectives", None) or getattr(battle.map, "objectives", [])
    dg_army = battle.a if dg_side == "A" else battle.b
    opp_army = battle.b if dg_side == "A" else battle.a
    def on_obj(u):
        if not objs:
            return False
        for o in objs:
            op = getattr(o, "position", None) or (getattr(o, "x", None), getattr(o, "y", None))
            if op and op[0] is not None and _dist(u.position, op) <= 3.0:
                return True
        return False
    for label, army in (("DG", dg_army), ("opp", opp_army)):
        alive = [u for u in army.units if u.is_alive]
        on = [u for u in alive if on_obj(u)]
        print(f"  END {label}: {len(alive)} alive, {len(on)} ON an objective (<=3in). "
              f"on-obj units: {[u.profile.name for u in on][:8]}")


def main():
    args = sys.argv[1:]
    opp = args[0] if args else "Thousand Sons"
    seeds = [int(x) for x in args[1:]] if len(args) > 1 else [0, 1, 2]
    for s in seeds:
        trace(DG, opp, s)


if __name__ == "__main__":
    main()
