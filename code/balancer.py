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

from .army_builder import build_attached_army, build_homogeneous_army
from .maps import DEFAULT_MAP
from .roles import baseline_key_for, classify, pick_host_for_leader
from .simulator import Battle
from .units import UNIT_CATALOG, UnitProfile

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATED_PATH = REPO_ROOT / "data" / "calibrated_points.json"

DEFAULT_BASELINE = "space_marines_intercessor_squad"

# Sentinel value used by the CLI / programmatic callers to request that the
# balancer choose a same-role baseline automatically rather than forcing a
# single hard-coded one. Kept as a literal string so it round-trips through
# argparse without bespoke type-coercion.
AUTO_BASELINE = "auto"


def resolve_baseline(unit_key: str, baseline_key: Optional[str]) -> str:
    """
    Pick the baseline catalogue key for calibrating `unit_key`.

    Rules:
      * Explicit non-auto `baseline_key` always wins.
      * `None` or "auto" -> look up the unit's role and use
        `baseline_key_for(role)`.
      * If the role-baseline is the unit itself (e.g. calibrating Intercessor
        Squad which is also the SHOOTY/DUAL baseline), fall back to the
        DEFAULT_BASELINE; if that is also the unit, fall back to the first
        catalogue key with the same role that isn't the unit. As a last
        resort, return DEFAULT_BASELINE so callers still get a string.
    """
    if baseline_key and baseline_key != AUTO_BASELINE:
        return baseline_key

    unit_profile = UNIT_CATALOG[unit_key]
    role = classify(unit_profile)
    candidate = baseline_key_for(role)

    if candidate != unit_key:
        return candidate

    # Unit IS the role baseline. Try the global default first.
    if DEFAULT_BASELINE != unit_key and DEFAULT_BASELINE in UNIT_CATALOG:
        return DEFAULT_BASELINE

    # Otherwise hunt for a same-role peer.
    for other_key, other_profile in UNIT_CATALOG.items():
        if other_key == unit_key:
            continue
        if classify(other_profile) == role:
            return other_key

    return DEFAULT_BASELINE


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


def measure_win_rate_leader_attached(
    leader_profile: UnitProfile,
    host_profile: UnitProfile,
    baseline_host_profile: UnitProfile,
    points_budget: float,
    n_battles: int = 200,
    rng: Optional[random.Random] = None,
) -> float:
    """
    Win rate for (host + leader) pairs vs the baseline host alone at equal
    points. Exercises the leader's aura on a real bodyguard squad rather than
    against copies of itself — used by the leader-attached calibration mode.
    """
    if rng is None:
        rng = random.Random()
    a_wins = 0
    b_wins = 0
    for _ in range(n_battles):
        a = build_attached_army("Test", host_profile, leader_profile, points_budget)
        b = build_homogeneous_army("Baseline", baseline_host_profile, points_budget)
        if not a.units or not b.units:
            continue
        result = Battle(a, b, map_=DEFAULT_MAP).run()
        if result.winner == "Test":
            a_wins += 1
        elif result.winner == "Baseline":
            b_wins += 1
    settled = a_wins + b_wins
    if settled == 0:
        return 0.5
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
    # #90 — mobility covariates: report alongside the cost so post-hoc analysis
    # can spot whether speed is systematically under- or over-rewarded.
    move: float = 0.0
    scout_distance: int = 0
    deep_strike: bool = False
    infiltrator: bool = False
    # #88 — leader-attached calibration metadata (empty / 0 for normal mode)
    host_key: str = ""
    attached_mode: bool = False


def find_balanced_points(
    unit_key: str,
    baseline_key: Optional[str] = None,
    target_win_rate: float = 0.5,
    tolerance: float = 0.05,
    n_battles: int = 200,
    max_iters: int = 8,
    points_budget: float = 1000.0,
    rng: Optional[random.Random] = None,
    auto_baseline: bool = True,
) -> CalibrationResult:
    """
    Find the points-per-model that lands `unit_key`'s win rate within
    `target ± tolerance` against the baseline over `n_battles` simulations.

    Baseline selection:
      * Explicit `baseline_key` (anything other than "auto") is used verbatim.
      * If `baseline_key` is None / "auto" AND `auto_baseline=True`, the
        baseline is chosen by role via `code.roles.baseline_key_for` so a
        Knight-class HEAVY is compared against another HEAVY rather than
        a chaff-tier Intercessor squad.
      * If `auto_baseline=False` and no explicit key, the legacy
        DEFAULT_BASELINE is used.

    Self-vs-self degeneracy (calibrating the role baseline itself) is avoided
    by `resolve_baseline`, which falls back to a peer.

    Uses bisection on a multiplicative scale (factor 1.5 step initially,
    halving the step on each direction reversal). Cheap and good enough for
    Phase-1 calibration; can be replaced with a cleaner search later.
    """
    if rng is None:
        rng = random.Random()

    if baseline_key and baseline_key != AUTO_BASELINE:
        resolved_baseline = baseline_key
    elif auto_baseline:
        resolved_baseline = resolve_baseline(unit_key, baseline_key)
    else:
        resolved_baseline = DEFAULT_BASELINE

    unit_profile = UNIT_CATALOG[unit_key]
    baseline_profile = UNIT_CATALOG[resolved_baseline]
    starting = max(1.0, unit_profile.points_cost)

    mobility_kwargs = dict(
        move=unit_profile.move,
        scout_distance=unit_profile.scout_distance,
        deep_strike=unit_profile.deep_strike,
        infiltrator=unit_profile.infiltrator,
    )

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
                unit_key=unit_key, baseline_key=resolved_baseline,
                starting_points=starting, balanced_points=round(current, 2),
                final_win_rate=wr, iterations=iters, converged=True,
                samples_per_iter=n_battles, points_budget=points_budget,
                **mobility_kwargs,
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
        unit_key=unit_key, baseline_key=resolved_baseline,
        starting_points=starting, balanced_points=round(current, 2),
        final_win_rate=last_wr, iterations=iters, converged=False,
        samples_per_iter=n_battles, points_budget=points_budget,
        notes=f"did not converge to {target_win_rate}+/-{tolerance} in {max_iters} iters",
        **mobility_kwargs,
    )


# ---------------------------------------------------------------------------
# Leader-attached calibration (#88)
# ---------------------------------------------------------------------------

def find_balanced_leader_points(
    leader_key: str,
    host_key: Optional[str] = None,
    target_win_rate: float = 0.5,
    tolerance: float = 0.05,
    n_battles: int = 200,
    max_iters: int = 8,
    points_budget: float = 1000.0,
    rng: Optional[random.Random] = None,
) -> CalibrationResult:
    """
    Bisect the leader's points-per-model so that an army of (host + leader)
    pairs lands within `target_win_rate ± tolerance` against a baseline army of
    the same host alone, at equal total points.

    `host_key` defaults to a same-faction battleline picked by
    `code.roles.pick_host_for_leader`. The host's own cost is held constant
    across iterations; only the leader's `points_override` moves.

    Returns the leader's balanced cost, plus mobility covariates and the
    resolved host_key in the CalibrationResult.
    """
    if rng is None:
        rng = random.Random()

    leader_profile = UNIT_CATALOG[leader_key]
    if host_key is None:
        host_key = pick_host_for_leader(leader_profile)
    host_profile = UNIT_CATALOG[host_key]

    mobility_kwargs = dict(
        move=leader_profile.move,
        scout_distance=leader_profile.scout_distance,
        deep_strike=leader_profile.deep_strike,
        infiltrator=leader_profile.infiltrator,
        host_key=host_key,
        attached_mode=True,
    )

    starting = max(1.0, leader_profile.points_cost)
    lo, hi = starting / 4.0, starting * 4.0
    current = starting
    last_direction = 0
    step_factor = 1.5
    iters = 0
    last_wr = 0.5

    for iters in range(1, max_iters + 1):
        tested_leader = replace(leader_profile, points_override=current)
        wr = measure_win_rate_leader_attached(
            tested_leader, host_profile, host_profile,
            points_budget, n_battles, rng,
        )
        last_wr = wr

        if abs(wr - target_win_rate) <= tolerance:
            return CalibrationResult(
                unit_key=leader_key, baseline_key=host_key,
                starting_points=starting, balanced_points=round(current, 2),
                final_win_rate=wr, iterations=iters, converged=True,
                samples_per_iter=n_battles, points_budget=points_budget,
                **mobility_kwargs,
            )

        if wr > target_win_rate:
            lo = current
            new_direction = +1
            current = min(hi, current * step_factor)
        else:
            hi = current
            new_direction = -1
            current = max(lo, current / step_factor)

        if last_direction != 0 and new_direction != last_direction:
            step_factor = max(1.05, 1.0 + (step_factor - 1.0) / 2.0)
        last_direction = new_direction

    return CalibrationResult(
        unit_key=leader_key, baseline_key=host_key,
        starting_points=starting, balanced_points=round(current, 2),
        final_win_rate=last_wr, iterations=iters, converged=False,
        samples_per_iter=n_battles, points_budget=points_budget,
        notes=f"did not converge to {target_win_rate}+/-{tolerance} in {max_iters} iters",
        **mobility_kwargs,
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
    p.add_argument("--baseline", type=str, default=AUTO_BASELINE,
                   help=(
                       "Baseline catalogue key, or 'auto' (default) for "
                       "role-stratified selection via code.roles."
                   ))
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
    p.add_argument("--leader-attached", action="store_true",
                   help=(
                       "Calibrate as an attached leader: bisect the leader's "
                       "cost while it sits with a bodyguard host (--host KEY "
                       "or auto-picked same-faction battleline)."
                   ))
    p.add_argument("--host", type=str, default=None,
                   help=(
                       "With --leader-attached, the bodyguard host's "
                       "catalogue key. Defaults to a same-faction battleline."
                   ))
    args = p.parse_args(argv)

    rng = random.Random(args.seed)

    if not args.unit and not args.all:
        p.error("Pass --unit <key> or --all")

    if args.unit:
        targets = [args.unit]
    else:
        # In sweep mode the only key we can never calibrate is one matching
        # a literal explicit baseline. With auto-baseline the per-unit
        # resolver handles self-vs-self by picking a peer instead.
        skip_key = args.baseline if args.baseline != AUTO_BASELINE else None
        targets = [k for k in UNIT_CATALOG if k != skip_key]
        if args.faction:
            targets = [k for k in targets if UNIT_CATALOG[k].faction == args.faction]
        if args.limit > 0:
            targets = targets[:args.limit]

    results: List[CalibrationResult] = []
    t0 = time.time()
    label = "auto (role-stratified)" if args.baseline == AUTO_BASELINE else args.baseline
    print(f"Calibrating {len(targets)} unit(s) against {label}\n")
    for i, key in enumerate(targets, 1):
        try:
            if args.leader_attached:
                r = find_balanced_leader_points(
                    key, host_key=args.host,
                    tolerance=args.tolerance,
                    n_battles=args.battles,
                    max_iters=args.iters,
                    points_budget=args.budget,
                    rng=rng,
                )
            else:
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
        baseline_suffix = (
            f"  vs {r.baseline_key[:32]}" if args.baseline == AUTO_BASELINE else ""
        )
        print(
            f"  [{i:>4}/{len(targets)}] {key[:48]:<48}  "
            f"{r.starting_points:>5.1f} -> {r.balanced_points:>5.1f} pts/model  "
            f"wr={r.final_win_rate:.2f}  it={r.iterations}  [{marker}]"
            f"{baseline_suffix}"
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
