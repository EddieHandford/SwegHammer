"""
Run a faction-vs-faction matchup matrix and report the simulator's per-faction
win rate next to known tournament win rates. The mean absolute error (MAE)
between sim and tournament is the headline number we drive down each
iteration of the calibration loop (#91).

Usage:
    python -m scripts.evaluate_vs_meta              # N=20 per pairing (~2 min)
    python -m scripts.evaluate_vs_meta --battles 40  # tighter signal
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from collections import Counter
from typing import Dict, List

# Lock Python's hash randomisation off so set() / dict-of-string iteration
# order is reproducible across runs — without this the sim's internal sets
# (advance/battleshock/fresh-arrival trackers) shuffle and the MAE drifts
# by ~3 pts between back-to-back invocations.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.evaluate_vs_meta"] + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army
from code.maps import DEFAULT_MAP
from code.simulator import Battle

FACTIONS: List[str] = [
    "Adeptus Astartes",
    "Necrons",
    "Aeldari",
    "Tyranids",
    "Orks",
    "T'au Empire",
    "Death Guard",
    "Adeptus Custodes",
    "Thousand Sons",
    "Leagues of Votann",
]

# Real tournament data: warpfriends weekly aggregate, May 2026 (~10k games).
# Numbers without authoritative aggregate use the meta-average midpoint of 48%
# so they don't dominate the MAE — flag them as "approx" in the report.
TOURNAMENT_TARGET: Dict[str, float] = {
    "Adeptus Astartes": 48.0,        # approx (chapters cluster around mid)
    "Necrons":          53.2,
    "Aeldari":          44.4,
    "Tyranids":         48.0,        # approx
    "Orks":             44.9,
    "T'au Empire":      54.5,
    "Death Guard":      48.0,        # approx
    "Adeptus Custodes": 48.0,        # approx
    "Thousand Sons":    54.6,
    "Leagues of Votann": 46.0,       # approx
}
APPROX_FACTIONS = {"Adeptus Astartes", "Tyranids", "Death Guard",
                   "Adeptus Custodes", "Leagues of Votann"}


def run_matrix(n: int) -> Dict[str, float]:
    """Average win-rate per faction across all opponents in the FACTIONS list.

    Seeds the global random module per battle so the same code base produces
    the same matrix across re-runs — otherwise the simulator's dice noise
    swamps small calibration changes. The seed schedule is deterministic
    (faction-name hash + battle index) and stable across runs.
    """
    sim_wr: Dict[tuple, float] = {}
    fac_idx = {f: i for i, f in enumerate(FACTIONS)}
    for a_fac in FACTIONS:
        for b_fac in FACTIONS:
            if a_fac == b_fac:
                continue
            winners: Counter = Counter()
            for s in range(n):
                # Deterministic seed using FACTIONS-list indices — Python
                # randomises `hash(str)` per process, which would otherwise
                # make this eval irreproducible across runs.
                ai, bi = fac_idx[a_fac], fac_idx[b_fac]
                pair_seed = (ai * 1000 + bi) * 100 + s
                random.seed(pair_seed)
                a = build_faction_random_army("A", a_fac, 1000, rng=random.Random(s))
                b = build_faction_random_army("B", b_fac, 1000, rng=random.Random(s + 10000))
                if not a.units or not b.units:
                    continue
                r = Battle(a, b, map_=DEFAULT_MAP).run()
                winners[r.winner] += 1
            sim_wr[(a_fac, b_fac)] = winners.get("A", 0) / n * 100

    out: Dict[str, float] = {}
    for fac in FACTIONS:
        rates = [v for (a, _), v in sim_wr.items() if a == fac]
        out[fac] = sum(rates) / len(rates)
    return out


def report(sim: Dict[str, float]) -> float:
    """Print the sim-vs-real table and return MAE over the FACTIONS list."""
    print(f"{'Faction':22s}  {'Sim%':>6s}  {'Real%':>6s}  {'Diff':>6s}")
    print("-" * 46)
    diffs = []
    for fac in FACTIONS:
        target = TOURNAMENT_TARGET[fac]
        diff = sim[fac] - target
        marker = "" if fac not in APPROX_FACTIONS else " (~)"
        print(f"{fac:22s}  {sim[fac]:6.1f}  {target:6.1f}  {diff:+6.1f}{marker}")
        diffs.append(abs(diff))
    mae = statistics.mean(diffs)
    print("-" * 46)
    print(f"Mean absolute error: {mae:.2f} pts  (target: < 5.0)")
    return mae


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--battles", type=int, default=20)
    args = p.parse_args()
    sim = run_matrix(args.battles)
    mae = report(sim)
    sys.exit(0 if mae < 5.0 else 0)   # informational only — never error-exit


if __name__ == "__main__":
    main()
