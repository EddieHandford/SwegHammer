"""Behavioural test for COUNTERPLAY_BEHAVIOR_SPEC Behaviour 1: does the sim's
Death Guard hold FEW objectives with a DECLINING round trajectory (the tape),
or MANY with a rising one (the sim defect)?

Measures, from ObjectiveScored events over eval-faithful Death-Guard games:
  B1a  mean objectives Death Guard controls per round (rounds 2-5)   [tape ~1.5-2.0]
  B1b  round trajectory: control at R5 vs R3 (tape DECLINES: R5 <= R3)
  B1c  15-VP cap-hit fraction of Death Guard player-rounds           [field ~13%]

Optionally toggles a lever env flag (argv[1]) to compare OFF vs ON. Read-only,
single process. Run: PYTHONHASHSEED=0 python -m scripts._behavior_check [FLAG]
"""
from __future__ import annotations
import os, sys, random
from collections import defaultdict
from code.army_builder import build_faction_random_army
from code.events import EventLog, RoundStarted, ObjectiveScored
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

DG = "Death Guard"
OPPS = ["Astra Militarum", "Adepta Sororitas", "Aeldari", "Adeptus Astartes"]
N = int(os.environ.get("BCHECK_N", "3"))
_idx = {f: i for i, f in enumerate(FACTIONS)}


def measure(flag_on: bool, flag: str | None):
    if flag:
        if flag_on:
            os.environ[flag] = "1"
        else:
            os.environ.pop(flag, None)
    per_round_objs = defaultdict(list)   # round -> [count of DG-controlled objs per game]
    per_round_prim = defaultdict(list)   # round -> [DG primary VP that round per game]
    cap_hits = 0
    cap_tot = 0
    measure._dg_scored = 0           # DG objective-scores total
    measure._dg_sticky_scored = 0    # DG scores where enemy OC >= DG OC (sticky-only)
    measure._flip_a = 0              # DG took a marker the enemy last held
    measure._flip_b = 0              # enemy broke DG's lock (out-controlled a DG marker)
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[DG] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", DG, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            lg = EventLog()
            Battle(a, b, subscribers=[lg], map_=_pick_rotation_map(seed),
                   primary_mission=_pick_primary_mission(ps)).run()
            cur = 0
            objs_this = defaultdict(int)
            prim_this = defaultdict(int)
            controller = {}          # objective_name -> last army to CONTROL it
            for e in lg.events:
                if isinstance(e, RoundStarted):
                    cur = e.round_num
                elif isinstance(e, ObjectiveScored):
                    if e.army_name == "A":
                        objs_this[cur] += 1
                        prim_this[cur] += (e.vp_awarded or 0)
                        # sticky evidence: DG scores a marker the enemy TIES or
                        # OUT-controls (a_oc <= b_oc) -> only possible via Worldblight
                        measure._dg_scored += 1
                        if e.a_oc <= e.b_oc:
                            measure._dg_sticky_scored += 1
                        # flip tracking: did DG take a marker the enemy last held?
                        if controller.get(e.objective_name) == "B":
                            measure._flip_a += 1
                        controller[e.objective_name] = "A"
                    elif e.army_name == "B":
                        # opponent broke DG's lock (out-controlled a DG marker)?
                        if controller.get(e.objective_name) == "A":
                            measure._flip_b += 1
                        controller[e.objective_name] = "B"
            for rnd in range(2, 6):
                per_round_objs[rnd].append(objs_this.get(rnd, 0))
                p = prim_this.get(rnd, 0)
                per_round_prim[rnd].append(p)
                cap_tot += 1
                if p >= 15:
                    cap_hits += 1
    mean_objs = sum(sum(v) for v in per_round_objs.values()) / max(1, sum(len(v) for v in per_round_objs.values()))
    def rmean(r):
        v = per_round_objs.get(r, [0]); return sum(v) / max(1, len(v))
    traj = {r: rmean(r) for r in range(2, 6)}
    capfrac = cap_hits / max(1, cap_tot)
    return mean_objs, traj, capfrac


def report(tag, mean_objs, traj, capfrac):
    print(f"[{tag}] B1a mean DG objs/round = {mean_objs:.2f}  (tape ~1.5-2.0)")
    print(f"      B1b trajectory R2..R5 = " + " -> ".join(f"{traj[r]:.2f}" for r in range(2, 6)) +
          f"   ({'DECLINE' if traj[5] <= traj[3] + 1e-9 else 'RISE'}; tape declines)")
    print(f"      B1c 15-VP cap-hit frac = {capfrac*100:.0f}%  (field ~13%)")
    ds = getattr(measure, "_dg_scored", 0) or 1
    print(f"      STICKY: {measure._dg_sticky_scored}/{measure._dg_scored} "
          f"({measure._dg_sticky_scored/ds*100:.0f}%) of DG scores are on markers the "
          f"enemy TIED/out-OC'd (Worldblight-only scores)")
    print(f"      LOCK-BREAKS: enemy out-Controlled a DG marker {measure._flip_b}x  |  "
          f"DG took an enemy marker {measure._flip_a}x")


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    flag = sys.argv[1] if len(sys.argv) > 1 else None
    off = measure(False, flag)
    report("OFF / main baseline", *off)
    if flag:
        on = measure(True, flag)
        print()
        report(f"ON  ({flag}=1)", *on)
        print(f"\nDELTA mean objs/round: {on[0]-off[0]:+.2f}  (want NEGATIVE = holds fewer, like the tape)")
