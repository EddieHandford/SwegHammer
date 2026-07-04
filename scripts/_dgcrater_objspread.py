"""DG-CRATER objective-spread quantifier (read-only): across a full anchor cell
(160 games, both orderings), measure how many objective markers each side SCORES
per round -- the objective-spread that decides the primary game -- and the
end-of-battle survivor split (on-objective vs stranded). Optionally toggles the
Thousand Sons ranged-hold (SWEG_TSONS_RANGED_HOLD) or the D1/D2/D3 contagion
gates to see whether either changes the objective-spread.

Run:
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dgcrater_objspread "Thousand Sons"
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dgcrater_objspread "Thousand Sons" TSONSHOLD_OFF
"""
from __future__ import annotations
import json, os, random, sys
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._dgcrater_objspread"] + sys.argv[1:],
        env=os.environ).returncode)

import multiprocessing as mp
from code.army_builder import build_faction_random_army
from code.events import (BattleStarted, RoundStarted, ObjectiveScored, EventLog)
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

DG = "Death Guard"
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

CONFIGS = {
    "baseline": {},
    "TSONSHOLD_OFF": {"SWEG_TSONS_RANGED_HOLD": "0"},
    "D1D2D3_OFF": {"SWEG_DG_CONTAGION_ESCALATION": "0",
                   "SWEG_DG_AFFLICTED_TOUGHNESS": "0",
                   "SWEG_DG_CHOSEN_PLAGUE": "0"},
    "GK_HOLD_ON": {"SWEG_GK_RANGED_HOLD": "1"},  # no-op if gate doesn't exist
}


def _dist(a, b):
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5


def worker(job):
    a_fac, b_fac, s, gate = job
    for k, v in gate.items():
        os.environ[k] = v
    # restore the gates this config does NOT set (worker reuse hygiene)
    for k in ("SWEG_TSONS_RANGED_HOLD", "SWEG_DG_CONTAGION_ESCALATION",
              "SWEG_DG_AFFLICTED_TOUGHNESS", "SWEG_DG_CHOSEN_PLAGUE"):
        if k not in gate:
            os.environ[k] = "1"
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    ps = (ai*1000+bi)*100+s
    random.seed(ps)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s+10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    bm = _pick_rotation_map(s); pm = _pick_primary_mission(ps)
    log = EventLog()
    battle = Battle(a, b, map_=bm, rules=None, primary_mission=pm, subscribers=[log])
    res = battle.run()
    dg_side = "A" if a_fac == DG else "B"
    dg_name = battle.a.name if dg_side == "A" else battle.b.name
    opp_name = battle.b.name if dg_side == "A" else battle.a.name
    # per-round markers scored by each side
    dg_marks_by_round = {}
    opp_marks_by_round = {}
    cur = 0
    for e in log.events:
        if isinstance(e, RoundStarted):
            cur = e.round_num
        elif isinstance(e, ObjectiveScored) and e.army_name:
            if e.army_name == dg_name:
                dg_marks_by_round[cur] = dg_marks_by_round.get(cur, 0) + 1
            elif e.army_name == opp_name:
                opp_marks_by_round[cur] = opp_marks_by_round.get(cur, 0) + 1
    rounds = res.rounds
    dg_marks = sum(dg_marks_by_round.values()) / max(rounds, 1)
    opp_marks = sum(opp_marks_by_round.values()) / max(rounds, 1)
    # end survivors on/off objective
    objs = getattr(battle, "objectives", None) or getattr(getattr(battle, "map", None), "objectives", []) or []
    def on_obj(u):
        for o in objs:
            op = getattr(o, "position", None)
            if op is None:
                x = getattr(o, "x", None); y = getattr(o, "y", None)
                op = (x, y) if x is not None else None
            if op and _dist(u.position, op) <= 3.0:
                return True
        return False
    dg_army = battle.a if dg_side == "A" else battle.b
    opp_army = battle.b if dg_side == "A" else battle.a
    dg_alive = [u for u in dg_army.units if u.is_alive]
    opp_alive = [u for u in opp_army.units if u.is_alive]
    dg_on = sum(1 for u in dg_alive if on_obj(u))
    opp_on = sum(1 for u in opp_alive if on_obj(u))
    return {
        "dg_win": res.winner == dg_side,
        "dg_marks": dg_marks, "opp_marks": opp_marks,
        "dg_alive": len(dg_alive), "opp_alive": len(opp_alive),
        "dg_on": dg_on, "opp_on": opp_on,
    }


def main():
    args = sys.argv[1:]
    opp = args[0] if args else "Thousand Sons"
    cfgs = args[1:] if len(args) > 1 else ["baseline"]
    anchor = "data/_anchor_sc54a_n80_log.json"
    d = json.load(open(anchor, encoding="utf-8"))
    games = [(a, b, s) for a, b, s, w in d["games"] if {a, b} == {DG, opp}]
    with mp.Pool(processes=12) as pool:
        for cfg in cfgs:
            gate = CONFIGS.get(cfg, {})
            jobs = [(a, b, s, gate) for (a, b, s) in games]
            res = [r for r in pool.map(worker, jobs, chunksize=4) if r]
            n = len(res)
            wr = 100*sum(r["dg_win"] for r in res)/n
            dgm = sum(r["dg_marks"] for r in res)/n
            opm = sum(r["opp_marks"] for r in res)/n
            dgon = sum(r["dg_on"] for r in res)/n
            opon = sum(r["opp_on"] for r in res)/n
            dgal = sum(r["dg_alive"] for r in res)/n
            opal = sum(r["opp_alive"] for r in res)/n
            print(f"\n=== DG vs {opp}  [{cfg}]  (n={n}) ===")
            print(f"  DG win rate: {wr:.1f}%")
            print(f"  markers scored per round:  DG {dgm:.2f}  vs opp {opm:.2f}   (spread {dgm-opm:+.2f})")
            print(f"  end alive:  DG {dgal:.1f}  opp {opal:.1f}")
            print(f"  end ON-objective units:  DG {dgon:.2f}  opp {opon:.2f}")


if __name__ == "__main__":
    main()
