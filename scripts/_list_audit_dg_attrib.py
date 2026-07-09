"""LIST AUDIT (Death Guard) scratch: attribution. Replay sc52a Death Guard
wins and check whether the sim wins with real-list units or with durable
PHANTOMS the real tournament list would not field.

Mirrors scripts._dura_audit_d_winshape's exact reconstruction (same seeds,
maps, missions). For a stratified subset it confirms winner reproduction,
then for a handful of DG WINS it dumps the DG roster, the DG survivors at
battle end, and classifies every DG unit as REAL-LIST (in the sourced
competitive template) vs OFF-TEMPLATE.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._list_audit_dg_attrib
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts._list_audit_dg_attrib"] + sys.argv[1:],
        env=os.environ).returncode)

import random
from code.army_builder import build_faction_random_army
from code.events import BattleStarted, UnitKilled, EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

DG = "Death Guard"
FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}

# Units that appear in the SOURCED May-2026 competitive Death Guard lists
# (Virulent Vectorium Mortarion-brick + Mortarion's Hammer vehicle-swarm).
REAL_LIST_NAMES = {
    "Mortarion",
    "Daemon Prince of Nurgle",
    "Daemon Prince of Nurgle with Wings",
    "Lord of Contagion",
    "Lord of Virulence",
    "Deathshroud Terminators",
    "Plague Marines",
    "Poxwalkers",
    "Foetid Bloat-drone",
    "Foetid Bloat-drone with heavy blight launcher",
    "Myphitic Blight-hauler",
    "Plagueburst Crawler",
}
# Durable pillars (the platforms that carry primary-objective uptime).
DURABLE_PILLARS = {
    "Mortarion", "Daemon Prince of Nurgle", "Daemon Prince of Nurgle with Wings",
    "Plagueburst Crawler", "Foetid Bloat-drone",
    "Foetid Bloat-drone with heavy blight launcher", "Myphitic Blight-hauler",
    "Deathshroud Terminators", "Lord of Contagion", "Lord of Virulence",
}


def load_dg_games(path):
    d = json.load(open(path, encoding="utf-8"))
    return [(a, b, s, w) for a, b, s, w in d["games"] if DG in (a, b)]


def replay_one(a_fac, b_fac, s):
    ai, bi = FAC_IDX[a_fac], FAC_IDX[b_fac]
    pair_seed = (ai * 1000 + bi) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    log = EventLog()
    if not a.units or not b.units:
        return None, log, None
    bm = _pick_rotation_map(s)
    pm = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, map_=bm, rules=None, primary_mission=pm, subscribers=[log])
    res = battle.run()
    return res, log, battle


def roster_and_survivors(a_fac, b_fac, s, log, res):
    ev = log.events
    info = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                info[u.uid] = {"name": u.name, "army": u.army}
    dg_side = "A" if a_fac == DG else "B"
    killed = {e.unit_uid for e in ev if isinstance(e, UnitKilled)}
    roster = Counter(i["name"] for i in info.values() if i["army"] == dg_side)
    survivors = Counter(i["name"] for uid, i in info.items()
                        if i["army"] == dg_side and uid not in killed)
    return dg_side, roster, survivors


def classify(roster):
    off = {n: c for n, c in roster.items() if n not in REAL_LIST_NAMES}
    real_pts_models = sum(c for n, c in roster.items() if n in REAL_LIST_NAMES)
    off_models = sum(off.values())
    return off, real_pts_models, off_models


def main():
    path = "data/_anchor_sc52a_n80_log.json"
    games = load_dg_games(path)
    # stratified reproduction check: first 5 seeds vs each opponent
    by_opp = {}
    for a, b, s, w in games:
        opp = b if a == DG else a
        by_opp.setdefault(opp, []).append((a, b, s, w))
    subset = []
    for opp, lst in by_opp.items():
        lst.sort(key=lambda x: x[2])
        subset.extend(lst[:5])

    matched = total = 0
    wins = []
    for a, b, s, w in subset:
        res, log, battle = replay_one(a, b, s)
        if battle is None:
            continue
        total += 1
        if res.winner == w:
            matched += 1
        dg_side = "A" if a == DG else "B"
        if res.winner == dg_side:
            wins.append((a, b, s, w, res, log))
    print(f"sc52a REPRODUCTION (stratified {total} games): {matched}/{total} "
          f"= {100*matched/total:.1f}%")

    # aggregate off-template presence across ALL subset DG games
    agg_off = Counter()
    agg_real_models = agg_off_models = 0
    for a, b, s, w in subset:
        res, log, battle = replay_one(a, b, s)
        if battle is None:
            continue
        dg_side, roster, surv = roster_and_survivors(a, b, s, log, res)
        off, rm, om = classify(roster)
        agg_off.update(off)
        agg_real_models += rm
        agg_off_models += om
    tot_models = agg_real_models + agg_off_models
    print(f"\nAcross {total} DG games: {agg_real_models} real-list models, "
          f"{agg_off_models} off-template models "
          f"({100*agg_off_models/tot_models:.1f}% off-template by model count)")
    print("Off-template units drafted (all cheap support, no durable phantom):")
    for n, c in agg_off.most_common():
        p = 0.0
        print(f"   {n:34s} x{c}")

    # DETAIL: 4 DG wins across opponent classes
    print("\n=== ATTRIBUTION DETAIL: DG WINS (roster / survivors / classification) ===")
    seen_opp = set()
    shown = 0
    for a, b, s, w, res, log in wins:
        opp = b if a == DG else a
        if opp in seen_opp:
            continue
        seen_opp.add(opp)
        dg_side, roster, surv = roster_and_survivors(a, b, s, log, res)
        off, rm, om = classify(roster)
        pillars_start = sum(c for n, c in roster.items() if n in DURABLE_PILLARS)
        pillars_surv = sum(c for n, c in surv.items() if n in DURABLE_PILLARS)
        print(f"\n-- DG vs {opp} seed={s}  WIN (winner={res.winner}, rec={w}, "
              f"reproduced={res.winner==w})  rounds={res.rounds}")
        print(f"   DG roster ({sum(roster.values())} models): "
              + ", ".join(f"{n} x{c}" for n, c in roster.most_common()))
        print(f"   DG survivors ({sum(surv.values())} models): "
              + (", ".join(f"{n} x{c}" for n, c in surv.most_common()) or "none"))
        print(f"   durable pillars: {pillars_start} started, {pillars_surv} survived")
        print(f"   off-template models: {om} "
              + (f"({off})" if off else "(none)"))
        shown += 1
        if shown >= 4:
            break


if __name__ == "__main__":
    main()
