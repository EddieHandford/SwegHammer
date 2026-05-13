"""
SwegHammer rule balancer — derive empirical points costs from simulated battles.

The pipeline:

  1. Pick a baseline unit (Intercessor Squad by default) and an army size.
  2. For each candidate unit U, simulate N battles of "armies of U" vs "armies
     of the baseline", both at the same total points budget.
  3. If U wins meaningfully more than 50%, U is undercosted — bisect its
     points-per-model UP until the win rate falls back into the target band.
     Conversely, undershooting means bisect DOWN.
  4. The settled points-per-model is the balanced cost. Write to
     `data/calibrated_points.json` so the catalogue and a future BSData XML
     export can both consume it.

This module deliberately uses the existing simulator and army builder rather
than fitting a closed-form cost surface — battlefield dynamics (movement,
target priority, terrain) are coupled enough that an analytical fit would lie.
Monte Carlo is honest.

Usage:
    python -m code.balancer --unit necrons_necron_warriors
    python -m code.balancer --all                  # sweep all enabled units (slow)
    python -m code.balancer --all --battles 100    # faster but noisier

Output:
    data/calibrated_points.json — {unit_key: {balanced_points: N, samples: M,
                                                final_win_rate: W, ...}}
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dataclasses import replace

from .army_builder import build_homogeneous_army
from .maps import DEFAULT_MAP
from .simulator import Battle
from .units import UNIT_CATALOG, UnitProfile

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATED_PATH = REPO_ROOT / "data" / "calibrated_points.json"

DEFAULT_BASELINE = "space_marines_intercessor_squad"


# ---------------------------------------------------------------------------
# Core measurement
# ---------------------------------------------------------------------------

def measure_win_rate(
    unit_profile: UnitProfile,
    baseline_profile: UnitProfile,
    points_budget: float,
    n_battles: int = 200,
    rng: Optional[random.Random] = None,
) -> float:
    """Fraction of battles `unit_profile` wins against `baseline_profile` at equal points."""
    if rng is None:
        rng = random.Random()
    a_wins = 0
    b_wins = 0
    for _ in range(n_battles):
        a = build_homogeneous_army("Test", unit_profile, points_budget)
        b = build_homogeneous_army("Baseline", baseline_profile, points_budget)
        if not a.units or not b.units:
            # Can't field even one model at this cost — degenerate; skip
            continue
        result = Battle(a, b, map_=DEFAULT_MAP).run()
        if result.winner == "Test":
            a_wins += 1
        elif result.winner == "Baseline":
            b_wins += 1
    settled = a_wins + b_wins
    if settled == 0:
        return 0.5   # all draws — treat as balanced
    return a_wins / settled


# ---------------------------------------------------------------------------
# Calibration loop
# ---------------------------------------------------------------------------

@dataclass
class CalibrationResult:
    unit_key: str
    baseline_key: str
    starting_points: float
    balanced_points: float
    final_win_rate: float
    iterations: int
    converged: bool
    samples_per_iter: int
    points_budget: float
    notes: str = ""


def find_balanced_points(
    unit_key: str,
    baseline_key: str = DEFAULT_BASELINE,
    target_win_rate: float = 0.5,
    tolerance: float = 0.05,
    n_battles: int = 200,
    max_iters: int = 8,
    points_budget: float = 1000.0,
    rng: Optional[random.Random] = None,
) -> CalibrationResult:
    """
    Find the points-per-model that lands `unit_key`'s win rate within
    `target ± tolerance` against `baseline_key` over `n_battles` simulations.

    Uses bisection on a multiplicative scale (factor 1.5 step initially,
    halving the step on each direction reversal). Cheap and good enough for
    Phase-1 calibration; can be replaced with a cleaner search later.
    """
    if rng is None:
        rng = random.Random()
    unit_profile = UNIT_CATALOG[unit_key]
    baseline_profile = UNIT_CATALOG[baseline_key]
    starting = max(1.0, unit_profile.points_cost)

    lo, hi = starting / 4.0, starting * 4.0
    current = starting
    last_direction = 0          # +1 = priced up last, -1 = priced down last
    step_factor = 1.5
    iters = 0
    last_wr = 0.5

    for iters in range(1, max_iters + 1):
        tested = replace(unit_profile, points_override=current)
        wr = measure_win_rate(tested, baseline_profile, points_budget, n_battles, rng)
        last_wr = wr

        if abs(wr - target_win_rate) <= tolerance:
            return CalibrationResult(
                unit_key=unit_key, baseline_key=baseline_key,
                starting_points=starting, balanced_points=round(current, 2),
                final_win_rate=wr, iterations=iters, converged=True,
                samples_per_iter=n_battles, points_budget=points_budget,
            )

        if wr > target_win_rate:
            # Undercosted — make it more expensive (fewer models per budget)
            lo = current
            new_direction = +1
            current = min(hi, current * step_factor)
        else:
            # Overcosted — cheaper
            hi = current
            new_direction = -1
            current = max(lo, current / step_factor)

        # Step damping: reverse direction means we overshot, halve the step
        if last_direction != 0 and new_direction != last_direction:
            step_factor = max(1.05, 1.0 + (step_factor - 1.0) / 2.0)
        last_direction = new_direction

    return CalibrationResult(
        unit_key=unit_key, baseline_key=baseline_key,
        starting_points=starting, balanced_points=round(current, 2),
        final_win_rate=last_wr, iterations=iters, converged=False,
        samples_per_iter=n_battles, points_budget=points_budget,
        notes=f"did not converge to {target_win_rate}+/-{tolerance} in {max_iters} iters",
    )


# ---------------------------------------------------------------------------
# Output writer + summary
# ---------------------------------------------------------------------------

def load_calibrated() -> Dict[str, dict]:
    if not CALIBRATED_PATH.exists():
        return {}
    return json.loads(CALIBRATED_PATH.read_text(encoding="utf-8")).get("units", {})


def write_calibrated(results: List[CalibrationResult]) -> None:
    CALIBRATED_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "Auto-generated by code/balancer.py. Each unit's balanced_points is "
            "the points-per-model that produced ~50% win rate against the baseline "
            "over the listed number of samples. Use as the source of truth for a "
            "future BSData export with re-balanced costs."
        ),
        "units": {r.unit_key: asdict(r) for r in results},
    }
    CALIBRATED_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description="SwegHammer points-balancer")
    p.add_argument("--unit", type=str, default=None,
                   help="Catalogue key to calibrate (omit + use --all for sweep)")
    p.add_argument("--baseline", type=str, default=DEFAULT_BASELINE)
    p.add_argument("--all", action="store_true",
                   help="Calibrate every enabled unit in the catalogue (slow)")
    p.add_argument("--battles", type=int, default=200,
                   help="Battles per iteration (default 200)")
    p.add_argument("--budget", type=float, default=1000.0,
                   help="Total points budget per side (default 1000)")
    p.add_argument("--iters", type=int, default=8,
                   help="Max bisection iterations per unit (default 8)")
    p.add_argument("--tolerance", type=float, default=0.05,
                   help="Win-rate tolerance band around 0.5 (default 0.05)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0,
                   help="With --all, cap how many units to calibrate (0 = no cap)")
    p.add_argument("--faction", type=str, default=None,
                   help="With --all, restrict to a single faction string")
    args = p.parse_args(argv)

    rng = random.Random(args.seed)

    if not args.unit and not args.all:
        p.error("Pass --unit <key> or --all")

    if args.unit:
        targets = [args.unit]
    else:
        targets = [k for k, u in UNIT_CATALOG.items() if k != args.baseline]
        if args.faction:
            targets = [k for k in targets if UNIT_CATALOG[k].faction == args.faction]
        if args.limit > 0:
            targets = targets[:args.limit]

    results: List[CalibrationResult] = []
    t0 = time.time()
    print(f"Calibrating {len(targets)} unit(s) against {args.baseline}\n")
    for i, key in enumerate(targets, 1):
        try:
            r = find_balanced_points(
                key, baseline_key=args.baseline,
                tolerance=args.tolerance,
                n_battles=args.battles,
                max_iters=args.iters,
                points_budget=args.budget,
                rng=rng,
            )
        except KeyError:
            print(f"  [{i}/{len(targets)}] {key} — MISSING from catalogue, skipping")
            continue
        marker = "OK" if r.converged else "no-conv"
        print(
            f"  [{i:>4}/{len(targets)}] {key[:48]:<48}  "
            f"{r.starting_points:>5.1f} -> {r.balanced_points:>5.1f} pts/model  "
            f"wr={r.final_win_rate:.2f}  it={r.iterations}  [{marker}]"
        )
        results.append(r)

    if args.all:
        write_calibrated(results)
        dt = time.time() - t0
        converged = sum(1 for r in results if r.converged)
        print(
            f"\nWrote {CALIBRATED_PATH} — "
            f"{converged}/{len(results)} converged in {dt:.0f}s"
        )


if __name__ == "__main__":
    main(sys.argv[1:])
