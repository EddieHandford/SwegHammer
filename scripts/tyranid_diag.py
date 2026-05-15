"""
Tyranid Invasion Fleet archetype diagnostic.

Runs Tyranids vs each of the other 9 faction archetypes at N=30 with archetype-
enabled army building. Reports per-matchup WR and aggregate event counts so we
can locate where the +38pt sim-vs-real over-performance is coming from.

Usage: PYTHONIOENCODING=utf-8 python -m scripts.tyranid_diag
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter

# Hash-seed is set via env var by the caller; we don't re-exec here to keep
# the script simple to run inline from a worktree shell.

from code.archetypes import build_archetype_army, has_archetype
from code.army_builder import build_faction_random_army
from code.events import (
    BattleshockFailed, EventLog, ObjectiveScored, RoundEnded, UnitCharged,
    UnitKilled, UnitDeepStrike, UnitScouted, UnitInfiltrated,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
]

REAL_TYRANID_WR = 48.0  # tournament target
N = 30


def _build(faction: str, name: str, budget: float, seed: int) -> "Army":
    rng = random.Random(seed)
    if has_archetype(faction):
        return build_archetype_army(name, faction, budget, rng=rng)
    return build_faction_random_army(name, faction, budget, rng=rng)


def run_pairing(opp: str, n: int) -> dict:
    wins_tyr = 0
    wins_opp = 0
    draws = 0
    ev: Counter = Counter()
    tyr_vp_per_round_total = Counter()
    opp_vp_per_round_total = Counter()
    final_vp = {"tyr": 0, "opp": 0}
    n_rounds = 0
    n_battles = 0
    for s in range(n):
        random.seed(1000 + s)
        tyr = _build("Tyranids", "TYR", 1000, seed=s)
        op = _build(opp, "OPP", 1000, seed=s + 50000)
        if not tyr.units or not op.units:
            continue
        log = EventLog()
        battle = Battle(tyr, op, map_=DEFAULT_MAP, subscribers=[log])
        r = battle.run()
        n_battles += 1
        n_rounds += r.rounds
        if r.winner == "TYR":
            wins_tyr += 1
        elif r.winner == "OPP":
            wins_opp += 1
        else:
            draws += 1
        final_vp["tyr"] += r.a_vp
        final_vp["opp"] += r.b_vp
        # Per-round VP curves and event counts.
        for e in log.events:
            if isinstance(e, UnitKilled):
                ev["UnitKilled"] += 1
            elif isinstance(e, BattleshockFailed):
                ev["BattleshockFailed"] += 1
            elif isinstance(e, UnitCharged):
                ev["UnitCharged_attempted"] += 1
                if e.succeeded:
                    ev["UnitCharged_succeeded"] += 1
            elif isinstance(e, ObjectiveScored):
                if e.army_name == "TYR":
                    ev["TYR_obj_scored"] += e.vp_awarded
                elif e.army_name == "OPP":
                    ev["OPP_obj_scored"] += e.vp_awarded
            elif isinstance(e, RoundEnded):
                tyr_vp_per_round_total[e.round_num] += e.a_vp_total
                opp_vp_per_round_total[e.round_num] += e.b_vp_total
    return {
        "opp": opp,
        "n": n_battles,
        "wins_tyr": wins_tyr,
        "wins_opp": wins_opp,
        "draws": draws,
        "wr_tyr": wins_tyr / max(1, n_battles) * 100,
        "wr_real": REAL_TYRANID_WR,
        "events": ev,
        "tyr_vp_avg_final": final_vp["tyr"] / max(1, n_battles),
        "opp_vp_avg_final": final_vp["opp"] / max(1, n_battles),
        "tyr_vp_curve": {r: tyr_vp_per_round_total[r] / max(1, n_battles) for r in sorted(tyr_vp_per_round_total)},
        "opp_vp_curve": {r: opp_vp_per_round_total[r] / max(1, n_battles) for r in sorted(opp_vp_per_round_total)},
        "rounds_avg": n_rounds / max(1, n_battles),
    }


def main() -> None:
    print(f"Tyranid Invasion Fleet diagnostic (N={N}/matchup, archetypes ON)")
    print(f"Real Tyranid WR target: {REAL_TYRANID_WR:.1f}%")
    print()
    rows = []
    for opp in OPPONENTS:
        r = run_pairing(opp, N)
        rows.append(r)
        ev = r["events"]
        print(
            f"vs {opp:22s}  TYR {r['wr_tyr']:5.1f}%  diff_real {r['wr_tyr']-REAL_TYRANID_WR:+5.1f}  "
            f"VP T/O {r['tyr_vp_avg_final']:4.1f}/{r['opp_vp_avg_final']:4.1f}  "
            f"kills {ev.get('UnitKilled',0):4d}  "
            f"BS_fail {ev.get('BattleshockFailed',0):3d}  "
            f"chrg {ev.get('UnitCharged_succeeded',0):3d}/{ev.get('UnitCharged_attempted',0):3d}  "
            f"rounds {r['rounds_avg']:4.1f}"
        )
    avg_wr = sum(r["wr_tyr"] for r in rows) / len(rows)
    print()
    print(f"Tyranid AVG WR across opponents: {avg_wr:.1f}%  (real {REAL_TYRANID_WR:.1f}%, diff {avg_wr-REAL_TYRANID_WR:+.1f}pt)")
    print()
    print("Worst (most over-performing) matchups:")
    rows_sorted = sorted(rows, key=lambda r: -(r["wr_tyr"] - REAL_TYRANID_WR))
    for r in rows_sorted[:5]:
        print(
            f"  vs {r['opp']:22s} TYR {r['wr_tyr']:5.1f}%  diff {r['wr_tyr']-REAL_TYRANID_WR:+5.1f}pt  "
            f"VP {r['tyr_vp_avg_final']:.1f} vs {r['opp_vp_avg_final']:.1f}"
        )
    # VP curves for top 3 worst.
    print()
    print("VP curves (TYR / OPP per round) for worst 3 matchups:")
    for r in rows_sorted[:3]:
        print(f"  vs {r['opp']}: ", end="")
        for rd in sorted(r["tyr_vp_curve"]):
            print(f"R{rd}={r['tyr_vp_curve'][rd]:.1f}/{r['opp_vp_curve'][rd]:.1f}  ", end="")
        print()


if __name__ == "__main__":
    main()
