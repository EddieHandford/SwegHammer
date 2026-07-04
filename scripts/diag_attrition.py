"""Attrition-curve diagnostic.

The game-shape signature #6 shows sim primary scoring is FLAT across rounds 2-5
(8.7 -> 9.7), where real games are "attrition-constrained by round 5" (scoring
falls as models die). This measures whether the sim actually thins armies out:
per round, the cumulative fraction of each army's models destroyed, and the
end-of-game survival fraction.

Two questions:
  (1) Does the sim under-kill overall (too many models alive at round 5 ->
      flat trajectory, positional standoff)?
  (2) Is killing LOP-SIDED by durability — do fragile armies get wiped while
      durable armies persist (the killing-efficiency imbalance that would make
      durable=over / fragile=under)?

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_attrition [mode]
  mode "curve"  (default): a few illustrative matchups, per-round kill curve.
  mode "byfac":  every faction as A vs a fixed spread, end-round survival + err.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from statistics import mean

from code.army_builder import build_faction_random_army
from code.events import EventLog, BattleStarted, RoundStarted, UnitKilled, RoundEnded
from code.simulator import Battle
from scripts.evaluate_vs_meta import (
    FACTIONS, _pick_rotation_map, _pick_primary_mission,
    _load_tournament_target, _load_tournament_games,
)
from scripts.paired_delta import _frame


def _play(under: str, over: str, seed: int):
    random.seed(seed)
    a = build_faction_random_army("A", under, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", over, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    log = EventLog()
    Battle(a, b, subscribers=[log], map_=_pick_rotation_map(seed),
           primary_mission=_pick_primary_mission(seed)).run()
    ev = log.events
    # uid -> army
    uid_army = {}
    a_start = b_start = 0
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                uid_army[u.uid] = u.army
                if u.army == "A":
                    a_start += 1
                else:
                    b_start += 1
    # cumulative kills per army by round
    cur_round = 0
    a_killed = defaultdict(int)   # round -> A models lost cumulatively
    b_killed = defaultdict(int)
    a_cum = b_cum = 0
    for e in ev:
        if isinstance(e, RoundStarted):
            cur_round = e.round_num
        elif isinstance(e, UnitKilled):
            army = uid_army.get(e.unit_uid)
            if army == "A":
                a_cum += 1
            elif army == "B":
                b_cum += 1
        elif isinstance(e, RoundEnded):
            a_killed[e.round_num] = a_cum
            b_killed[e.round_num] = b_cum
    if not a_start or not b_start:
        return None
    # fraction of each army destroyed at each round (1..5)
    a_frac = {r: a_killed.get(r, a_cum) / a_start for r in range(1, 6)}
    b_frac = {r: b_killed.get(r, b_cum) / b_start for r in range(1, 6)}
    return a_frac, b_frac, a_start, b_start


CURVE_MATCHUPS = [
    ("Death Guard", "Astra Militarum"),      # durable over vs fragile under
    ("Imperial Knights", "Orks"),            # durable over vs horde under
    ("Astra Militarum", "Death Guard"),      # mirror (fragile as A)
    ("Aeldari", "Astra Militarum"),          # fragile-over vs fragile-under
    ("Chaos Daemons", "Death Guard"),        # fragile-under vs durable-over
]
SPREAD = ["Death Guard", "Imperial Knights", "Aeldari", "Astra Militarum",
          "Orks", "Tyranids", "Necrons", "Adeptus Custodes"]
SEEDS = [0, 1, 2, 3]


def curve():
    print("# per-round cumulative % of army DESTROYED (mean over 4 seeds)")
    print(f"{'matchup (A vs B)':34s} {'side':4s}  r1   r2   r3   r4   r5")
    for under, over in CURVE_MATCHUPS:
        af = defaultdict(list); bf = defaultdict(list)
        for s in SEEDS:
            res = _play(under, over, s)
            if not res:
                continue
            a_frac, b_frac, _, _ = res
            for r in range(1, 6):
                af[r].append(a_frac[r]); bf[r].append(b_frac[r])
        aline = "  ".join(f"{100*mean(af[r]):3.0f}" for r in range(1, 6))
        bline = "  ".join(f"{100*mean(bf[r]):3.0f}" for r in range(1, 6))
        print(f"{under+' vs '+over:34s} A(under) {aline}")
        print(f"{'':34s} B(over)  {bline}")


def byfac():
    d = json.load(open("data/_anchor_sc57a_n80_log.json"))
    games = {(a, b, s): w for a, b, s, w in d["games"]}
    weights = _load_tournament_games(); target = _load_tournament_target()
    fr = _frame(games, weights)
    rows = []
    for f in FACTIONS:
        own_surv = []   # own fraction ALIVE at round 5
        enemy_kill = []  # enemy fraction DESTROYED at round 5
        for opp in SPREAD:
            if opp == f:
                continue
            for s in SEEDS:
                res = _play(f, opp, s)
                if not res:
                    continue
                a_frac, b_frac, _, _ = res
                own_surv.append(1 - a_frac[5])
                enemy_kill.append(b_frac[5])
        if not own_surv:
            continue
        err = fr[f] - target[f]
        rows.append((err, f, 100 * mean(own_surv), 100 * mean(enemy_kill)))
    rows.sort(reverse=True)
    print(f"# own-survival & enemy-kill at round 5, by faction ({len(SPREAD)} opps x {len(SEEDS)} seeds)")
    print(f"{'faction':22s} {'err':>6s} {'ownAlive%':>9s} {'enemyKilled%':>12s}")
    for err, f, surv, kill in rows:
        print(f"{f:22s} {err:+6.1f} {surv:9.1f} {kill:12.1f}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "curve"
    if mode == "byfac":
        byfac()
    else:
        curve()
