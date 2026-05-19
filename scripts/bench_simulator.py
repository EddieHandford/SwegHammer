"""
Benchmark harness for the simulator hot path.

Runs a fixed set of representative matchups with a fixed seed and reports
total wall time plus per-matchup throughput. Designed to be re-run before
and after each optimisation tier so the speedup can be measured directly
rather than guessed at.

Usage:
    python -m scripts.bench_simulator              # default config
    python -m scripts.bench_simulator --battles 50 # smaller / quicker

The matchup set is deliberately diverse: a horde-on-horde fight, an
elite-on-elite fight, and a high-attack vehicle fight. The mix exercises
the per-shot loop at different attack counts so the benchmark doesn't
collapse onto a single regime.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import random
import time
from typing import Callable

from code.army_builder import build_homogeneous_army
from code.simulator import Battle
from code.units import UNIT_CATALOG


MATCHUPS = [
    ("space_marines_intercessor_squad", "orks_boyz", 300.0),
    ("space_marines_terminator_squad", "necrons_lychguard", 400.0),
    ("space_marines_intercessor_squad", "space_marines_intercessor_squad", 300.0),
]


def _run_one(a_key: str, b_key: str, points: float, battles: int, seed: int) -> float:
    """Run `battles` repeats of one matchup, return wall seconds."""
    a_profile = UNIT_CATALOG[a_key]
    b_profile = UNIT_CATALOG[b_key]
    random.seed(seed)
    t0 = time.perf_counter()
    for i in range(battles):
        a = build_homogeneous_army(f"A_{a_profile.name}", a_profile, points)
        b = build_homogeneous_army(f"B_{b_profile.name}", b_profile, points)
        battle = Battle(a, b, verbose=False)
        battle.run()
    return time.perf_counter() - t0


def bench(battles: int, seed: int, profile: bool) -> None:
    print(f"== SwegHammer simulator benchmark ==")
    print(f"battles per matchup: {battles}")
    print(f"matchups: {len(MATCHUPS)}")
    print(f"seed: {seed}")
    print()

    totals = []
    for a_key, b_key, points in MATCHUPS:
        if profile:
            pr = cProfile.Profile()
            pr.enable()
            elapsed = _run_one(a_key, b_key, points, battles, seed)
            pr.disable()
            s = io.StringIO()
            pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(20)
            print(f"--- {a_key} vs {b_key} @ {points:.0f} pts ---")
            print(s.getvalue())
        else:
            elapsed = _run_one(a_key, b_key, points, battles, seed)
        per_battle_ms = 1000.0 * elapsed / battles
        totals.append(elapsed)
        print(
            f"  {a_key:>40s}  vs  {b_key:<40s}"
            f"  {elapsed:7.2f}s total  ({per_battle_ms:5.1f} ms/battle)"
        )

    grand_total = sum(totals)
    print()
    print(f"TOTAL: {grand_total:.2f}s  ({grand_total / (battles * len(MATCHUPS)) * 1000:.1f} ms per battle averaged)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--battles", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--profile", action="store_true", help="emit cProfile output")
    args = parser.parse_args()
    bench(args.battles, args.seed, args.profile)


if __name__ == "__main__":
    main()
