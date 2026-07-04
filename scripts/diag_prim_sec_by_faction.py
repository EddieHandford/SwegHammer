"""Per-faction primary-vs-secondary VP decomposition.

Tests the mechanism hypothesis behind the over/under poles: the game-shape
signatures show the sim OVER-scores primary (holding objectives, +6.7) and
UNDER-scores secondary (kill + mobility, -10.3). If that drives the poles, the
OVER-poles should earn their VP disproportionately from PRIMARY (survive-to-hold)
and the UNDER-poles should be starved on SECONDARY.

For each faction as army A, play vs a fixed spread of opponents x seeds; record
mean primary VP, mean secondary VP, and win rate. Print alongside the sc57a
field-weighted error (sim - real).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_prim_sec_by_faction
"""
from __future__ import annotations

import json
import random
import sys
from statistics import mean

from code.army_builder import build_faction_random_army
from code.events import EventLog, ObjectiveScored, RoundEnded
from code.simulator import Battle
from scripts.evaluate_vs_meta import (
    FACTIONS, _pick_rotation_map, _pick_primary_mission,
    _load_tournament_target, _load_tournament_games,
)
from scripts.paired_delta import _frame

# A diverse opponent spread: durable over-poles + hordes + mid — enough to
# characterise each faction's VP shape without the full 21-wide matrix.
OPPONENTS = [
    "Death Guard", "Imperial Knights", "Aeldari", "Astra Militarum",
    "Orks", "Tyranids", "Necrons", "Adeptus Custodes",
]
SEEDS = [0, 1, 2, 3]


def _prim_sec(under: str, over: str, seed: int):
    random.seed(seed)
    a = build_faction_random_army("A", under, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", over, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None
    bat = Battle(a, b, map_=_pick_rotation_map(seed),
                 primary_mission=_pick_primary_mission(seed))
    r = bat.run()
    # Authoritative UNCAPPED tallies straight off the Battle (same decomposition
    # the cap logic uses at simulator.py:978): primary = total - secondary -
    # challenger. Reading the raw pressure (uncapped) is what shows the scoring
    # SHAPE; the capped standing only decides the winner.
    a_sec = bat._a_secondary_vp
    a_primary = bat._a_vp - bat._a_secondary_vp - bat._a_challenger_vp
    won = 1 if r.winner == "A" else 0
    return a_primary, a_sec, bat._a_vp, won


def main() -> None:
    d = json.load(open("data/_anchor_sc57a_n80_log.json"))
    games = {(a, b, s): w for a, b, s, w in d["games"]}
    weights = _load_tournament_games()
    target = _load_tournament_target()
    fr = _frame(games, weights)

    rows = []
    for f in FACTIONS:
        prim, sec, tot, wins = [], [], [], []
        for opp in OPPONENTS:
            if opp == f:
                continue
            for s in SEEDS:
                res = _prim_sec(f, opp, s)
                if res is None:
                    continue
                prim.append(res[0]); sec.append(res[1]); tot.append(res[2]); wins.append(res[3])
        if not prim:
            continue
        err = fr[f] - target[f]
        rows.append((err, f, mean(prim), mean(sec), mean(tot), 100 * mean(wins)))

    rows.sort(reverse=True)
    print(f"# per-faction VP shape vs a fixed opponent spread ({len(OPPONENTS)} opps x {len(SEEDS)} seeds)")
    print(f"{'faction':22s} {'err':>6s} {'primary':>8s} {'secondary':>9s} {'total':>6s} {'win%':>5s}")
    for err, f, p, sc, t, w in rows:
        print(f"{f:22s} {err:+6.1f} {p:8.1f} {sc:9.1f} {t:6.1f} {w:5.1f}")


if __name__ == "__main__":
    main()
