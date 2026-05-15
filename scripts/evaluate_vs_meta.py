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
from typing import Dict, List, Tuple

# Lock Python's hash randomisation off so set() / dict-of-string iteration
# order is reproducible across runs — without this the sim's internal sets
# (advance/battleshock/fresh-arrival trackers) shuffle and the MAE drifts
# by ~3 pts between back-to-back invocations.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.evaluate_vs_meta"] + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army
from code.maps import DEFAULT_MAP
from code.simulator import Battle, RulesConfig

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


def run_matrix(n: int, rules: RulesConfig = None) -> Dict[str, float]:
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
                r = Battle(a, b, map_=DEFAULT_MAP, rules=rules).run()
                winners[r.winner] += 1
            sim_wr[(a_fac, b_fac)] = winners.get("A", 0) / n * 100

    out: Dict[str, float] = {}
    for fac in FACTIONS:
        rates = [v for (a, _), v in sim_wr.items() if a == fac]
        out[fac] = sum(rates) / len(rates)
    return out


def report(sim: Dict[str, float]) -> Tuple[float, float]:
    """Print the sim-vs-real table and return (mae_real, mae_sweg).

    Returns a dual headline:
      * `mae_real` — MAE between simulator and the real-meta tournament
        target. This is the calibration-against-GW signal that adding
        more faction rules can move.
      * `mae_sweg` — MAE between simulator and 50% across all factions.
        This is the Sweg-balanced target: a perfectly balanced rule set
        produces 50/50 cross-faction win rates. SwegHammer's "minimal
        rule changes" (alternating activation, CP-for-fewer-units) drift
        from real 10e by design, so `mae_real` has a structural floor that
        `mae_sweg` does not. Once the Sweg-balancer settles, `mae_sweg`
        should converge to ~0 while `mae_real` plateaus at the design
        floor.
    """
    print(f"{'Faction':22s}  {'Sim%':>6s}  {'Real%':>6s}  {'Diff':>6s}  {'vs50':>6s}")
    print("-" * 55)
    diffs_real = []
    diffs_sweg = []
    for fac in FACTIONS:
        target = TOURNAMENT_TARGET[fac]
        diff_real = sim[fac] - target
        diff_sweg = sim[fac] - 50.0
        marker = "" if fac not in APPROX_FACTIONS else " (~)"
        print(f"{fac:22s}  {sim[fac]:6.1f}  {target:6.1f}  "
              f"{diff_real:+6.1f}  {diff_sweg:+6.1f}{marker}")
        diffs_real.append(abs(diff_real))
        diffs_sweg.append(abs(diff_sweg))
    mae_real = statistics.mean(diffs_real)
    mae_sweg = statistics.mean(diffs_sweg)
    print("-" * 55)
    print(f"MAE vs real meta:    {mae_real:6.2f} pts  (target ≤ 2.0; "
          f"the calibration-against-GW signal)")
    print(f"MAE vs Sweg-balanced: {mae_sweg:6.2f} pts  (target ≤ 2.0; "
          f"the rule-internal-balance signal — 50/50 across factions)")
    return mae_real, mae_sweg


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--battles", type=int, default=20)
    p.add_argument(
        "--vanilla-10e",
        action="store_true",
        help="Run under vanilla WH40k 10e rules (no alternating activations, "
             "no simultaneous-movement sub-phase, no CP catch-up bonus, no "
             "coordinated army-plan). Default is SwegHammer mode.",
    )
    args = p.parse_args()
    rules = RulesConfig.vanilla_10e() if args.vanilla_10e else None
    if args.vanilla_10e:
        print("Mode: vanilla WH40k 10e\n")
    sim = run_matrix(args.battles, rules=rules)
    mae_real, mae_sweg = report(sim)
    sys.exit(0)   # informational only — never error-exit


if __name__ == "__main__":
    main()
