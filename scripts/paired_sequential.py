"""Sequential early-stop paired A/B (speed lever #1, part 2).

Runs an OFF/ON paired evaluation in disjoint seed batches and stops as soon as
the keep/reject question is resolved (decide_stop) instead of always paying a
full N. Because the paired delta is low-variance (most games are identical
OFF-vs-ON), most localized faithful changes resolve at N=20-40, so this often
runs a fraction of a full N=80 A/B.

Each batch runs both arms on a DISJOINT seed window (--seed-start) and unions the
per-game logs, so extending N never re-runs earlier seeds (the seeds compose
deterministically -> anytime-valid; peeking between batches is safe).

Usage:
    python -m scripts.paired_sequential \
        --on-env SWEG_VETERANS=1 --off-env SWEG_VETERANS=0 \
        --use-archetype --batch 20 --max 80 --threshold 1.0

The arms differ only by the env-gate vars given; everything else is identical and
on the same pair_seed schedule, so the games are matched pairs (Common Random
Numbers). Caps total seeds at <= the pair_seed two-digit budget (100).
"""
from __future__ import annotations

import os

os.environ["PYTHONHASHSEED"] = "0"  # defuse evaluate_vs_meta's import-time re-exec

import argparse
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

from scripts.paired_delta import (
    _load_log,
    _load_noise_floor,
    _load_tournament_games,
    _load_tournament_target,
    compute_paired,
    decide_stop,
)

Winner = Optional[str]


def _parse_env(spec: str) -> Dict[str, str]:
    """Parse "VAR=val,VAR2=val2" into a dict (empty string -> no overrides)."""
    out: Dict[str, str] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise SystemExit(f"bad --*-env entry (need VAR=val): {pair!r}")
        k, v = pair.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _run_arm(arm_env: Dict[str, str], batch: int, seed_start: int,
             use_archetype: bool, log_path: str) -> None:
    """Run one arm's batch as a subprocess, writing per-game winners to log_path."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(arm_env)
    cmd = [sys.executable, "-m", "scripts.evaluate_vs_meta",
           "--battles", str(batch), "--seed-start", str(seed_start),
           "--log-games", log_path]
    if use_archetype:
        cmd.append("--use-archetype")
    subprocess.run(cmd, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_sequential(off_env: Dict[str, str], on_env: Dict[str, str],
                   batch: int, max_n: int, threshold: float,
                   use_archetype: bool) -> dict:
    weights = _load_tournament_games()
    target = _load_tournament_target()
    noise = _load_noise_floor()
    off_games: Dict[Tuple[str, str, int], Winner] = {}
    on_games: Dict[Tuple[str, str, int], Winner] = {}
    seed_start = 0
    result: dict = {}
    while seed_start < max_n:
        b = min(batch, max_n - seed_start)
        with tempfile.TemporaryDirectory() as td:
            off_log = os.path.join(td, "off.json")
            on_log = os.path.join(td, "on.json")
            _run_arm(off_env, b, seed_start, use_archetype, off_log)
            _run_arm(on_env, b, seed_start, use_archetype, on_log)
            _, off_b = _load_log(off_log)
            _, on_b = _load_log(on_log)
        off_games.update(off_b)
        on_games.update(on_b)
        seed_start += b
        result = compute_paired(off_games, on_games, weights, target, noise)
        stop, reason = decide_stop(result, threshold)
        print(f"N={seed_start:<3} matched={result['matched']:<6} "
              f"gatedOFF={result['gated_off']:.2f} gatedON={result['gated_on']:.2f}  "
              f"-> {'STOP' if stop else 'cont'}: {reason}")
        if stop:
            result["stopped_at_n"] = seed_start
            return result
    result["stopped_at_n"] = seed_start
    print(f"reached max N={max_n} without a decisive verdict (treat as neutral "
          f"within +-{threshold:.1f} pts, or raise --max).")
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--off-env", default="", help='OFF-arm gates "VAR=val,..."')
    p.add_argument("--on-env", default="", help='ON-arm gates "VAR=val,..."')
    p.add_argument("--batch", type=int, default=20)
    p.add_argument("--max", type=int, default=80, dest="max_n")
    p.add_argument("--threshold", type=float, default=1.0,
                   help="keep/reject effect size in win-rate points (default 1.0)")
    p.add_argument("--use-archetype", action="store_true")
    args = p.parse_args()
    if args.max_n > 100:
        raise SystemExit("--max must be <= 100 (pair_seed two-digit seed budget).")
    run_sequential(_parse_env(args.off_env), _parse_env(args.on_env),
                   args.batch, args.max_n, args.threshold, args.use_archetype)


if __name__ == "__main__":
    main()
