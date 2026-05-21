"""
Fit the Bradley-Terry equilibrium equation using only simulator-calibrated
factions — those whose faction-level MAE vs tournament data is within a
configurable threshold.

Reads:
  data/meta_comparison_snapshot.json  — per-faction |diff| from evaluate_vs_meta
  code/units.UNIT_CATALOG             — full unit catalogue

Writes:
  data/equation_calibrated_points.json — per-unit price_per_model keyed by
    unit key, plus metadata (trusted factions, threshold, battle counts).

The equation is fit using cross-faction and intra-faction matchups between
all shooting-capable units from the trusted factions. Units outside the
trusted set inherit closed-form Phase 1 prices (stat-based, no faction rules).

Usage:
    python -m scripts.fit_equation_calibrated
    python -m scripts.fit_equation_calibrated --threshold 7.0
    python -m scripts.fit_equation_calibrated --threshold 10.0 --battles 20 --workers 8
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import random
import sys
from typing import Dict, List, Optional

# PYTHONHASHSEED guard — reproducible hash-based data structures inside workers.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.fit_equation_calibrated"] + sys.argv[1:],
        os.environ,
    )

from code.equilibrium_simdriven import (
    DEFAULT_ANCHOR_KEY,
    compute_phase_simdriven,
)
from code.equilibrium import DEFAULT_ANCHOR_PER_MODEL, _classify_role
from code.units import UNIT_CATALOG

_SNAPSHOT_PATH = pathlib.Path("data/meta_comparison_snapshot.json")
_OUT_PATH = pathlib.Path("data/equation_calibrated_points.json")

# Must stay in sync with FX_ALL_FACTIONS in scripts/evaluate_vs_meta.py and
# _FX_ALL_FACTIONS in app.py.
_FX_ALL_FACTIONS = frozenset({
    "Chaos Space Marines", "World Eaters", "Emperor's Children",
    "Chaos Daemons", "Astra Militarum", "Adeptus Mechanicus",
    "Adepta Sororitas", "Grey Knights", "Drukhari",
    "Genestealer Cults", "Imperial Knights", "Chaos Knights",
})


def load_trusted_factions(snapshot_path: pathlib.Path, threshold: float) -> List[str]:
    """Return factions with |diff| within the threshold that have real data."""
    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"Calibration snapshot not found: {snapshot_path}\n"
            "Build one first:\n"
            "  python -m scripts.evaluate_vs_meta --battles 100 "
            "--out data/meta_comparison_snapshot.json"
        )
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    trusted = []
    for row in snap.get("factions", []):
        faction = row["faction"]
        if faction in _FX_ALL_FACTIONS:
            continue
        if abs(row["diff"]) <= threshold:
            trusted.append(faction)
    return trusted


def get_faction_unit_keys(factions: List[str], max_per_faction: Optional[int] = None) -> List[str]:
    """Shooting-capable UNIT_CATALOG keys belonging to any of the given factions.

    If max_per_faction is set, caps each faction to that many units by taking
    an evenly-spaced sample sorted by GW points cost (cheapest to most expensive),
    which gives representative coverage across the cost spectrum.
    """
    faction_set = set(factions)
    result: List[str] = []
    for faction in factions:
        keys = [
            k for k, p in UNIT_CATALOG.items()
            if p.faction == faction
            and _classify_role(p) in ("shooty", "dual")
            and p.points_per_squad > 0
            and p.min_models > 0
        ]
        if not keys:
            continue
        if max_per_faction and len(keys) > max_per_faction:
            keys.sort(key=lambda k: UNIT_CATALOG[k].points_cost)
            step = len(keys) / max_per_faction
            keys = [keys[int(i * step)] for i in range(max_per_faction)]
        result.extend(keys)
    return result


def _progress(done: int, total: int, _key: str) -> None:
    pct = done * 100 // max(1, total)
    bar = "█" * (done * 30 // max(1, total)) + "░" * (30 - done * 30 // max(1, total))
    print(f"\r  [{bar}] {done}/{total}  ({pct}%)", end="", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fit the equilibrium equation using calibrated factions only."
    )
    ap.add_argument(
        "--threshold", type=float, default=10.0,
        help="Maximum |sim%% - tournament%%| for a faction to be included. Default 10.0.",
    )
    ap.add_argument(
        "--battles", type=int, default=20,
        help="Battles per unit pair. Default 20.",
    )
    ap.add_argument(
        "--budget", type=float, default=500.0,
        help="Points budget per side for unit matchups. Default 500.",
    )
    ap.add_argument(
        "--snapshot", type=str, default=str(_SNAPSHOT_PATH),
        help="Path to the calibration snapshot JSON.",
    )
    ap.add_argument(
        "--out", type=str, default=str(_OUT_PATH),
        help="Output path for the equation prices JSON.",
    )
    ap.add_argument(
        "--anchor-key", type=str, default=DEFAULT_ANCHOR_KEY,
        help=f"Anchor unit key (default: {DEFAULT_ANCHOR_KEY}).",
    )
    ap.add_argument(
        "--anchor-pts", type=float, default=DEFAULT_ANCHOR_PER_MODEL,
        help=f"Price per model for the anchor unit (default: {DEFAULT_ANCHOR_PER_MODEL}).",
    )
    ap.add_argument(
        "--workers", type=int, default=None,
        help="Worker processes. Default: os.cpu_count() - 1.",
    )
    ap.add_argument(
        "--max-per-faction", type=int, default=None,
        help=(
            "Cap the number of units sampled per faction. "
            "Units are sorted by GW points cost and evenly spaced, "
            "so the sample spans the cost spectrum. "
            "Dramatically reduces run time: 15 units/faction × 4 factions = "
            "60 units → 1,770 pairs vs the default 264 units → 34,716 pairs."
        ),
    )
    ap.add_argument(
        "--resume", action="store_true",
        help=(
            "Resume from an existing checkpoint at --checkpoint. The "
            "stored config hash must match the current --battles / --budget "
            "/ --anchor / measured-keys set, otherwise the run aborts."
        ),
    )
    ap.add_argument(
        "--checkpoint", type=str, default=None,
        help=(
            "Path to a JSONL checkpoint file. Defaults to <out>.checkpoint.jsonl. "
            "One line per completed pair is appended during the fit; "
            "deleted on successful completion."
        ),
    )
    ap.add_argument(
        "--progress", type=str, default=None,
        help=(
            "Path to a human-readable progress JSON file. Defaults to "
            "<out>.progress.json. Rewritten every 20 minutes during the fit "
            "with done / total / pct / elapsed_sec / eta_sec / battles_run."
        ),
    )
    args = ap.parse_args()

    snap_path = pathlib.Path(args.snapshot)
    out_path = pathlib.Path(args.out)
    checkpoint_path = (
        pathlib.Path(args.checkpoint) if args.checkpoint
        else out_path.with_suffix(".checkpoint.jsonl")
    )
    progress_path = (
        pathlib.Path(args.progress) if args.progress
        else out_path.with_suffix(".progress.json")
    )
    workers = args.workers if args.workers is not None else max(1, (os.cpu_count() or 2) - 1)

    trusted = load_trusted_factions(snap_path, args.threshold)
    if not trusted:
        print(
            f"No factions within {args.threshold} pt threshold. "
            "Run more calibration iterations or raise the threshold."
        )
        sys.exit(1)

    measured_keys = get_faction_unit_keys(trusted, max_per_faction=args.max_per_faction)
    # Ensure anchor is always present (compute_phase_simdriven requires it).
    if args.anchor_key not in measured_keys:
        measured_keys = [args.anchor_key] + measured_keys

    n_units = len(measured_keys)
    n_pairs = n_units * (n_units - 1) // 2
    est_battles = n_pairs * args.battles
    est_sec = est_battles * 0.10 / workers

    print(f"Threshold: {args.threshold} pts  |  Workers: {workers}")
    print(f"Trusted factions ({len(trusted)}): {', '.join(trusted)}")
    print(
        f"Units to measure: {n_units}  |  Pairs: {n_pairs}  |  "
        f"~{est_battles:,} battles  |  est. {est_sec/60:.0f} min"
    )
    print(f"Checkpoint: {checkpoint_path}  |  Progress: {progress_path}")
    if args.resume:
        print(f"Resume: ON (will skip pairs already in {checkpoint_path})")
    print()

    result = compute_phase_simdriven(
        catalog=UNIT_CATALOG,
        anchor_key=args.anchor_key,
        anchor_per_model=args.anchor_pts,
        measured_keys=measured_keys,
        n_battles=args.battles,
        points_budget=args.budget,
        progress_cb=_progress,
        rng=random.Random(42),
        max_workers=workers,
        checkpoint_path=checkpoint_path,
        progress_path=progress_path,
        resume=args.resume,
    )
    print()  # newline after progress bar

    prices: Dict[str, float] = {}
    sim_count = 0
    fallback_count = 0
    for entry in result.entries:
        prices[entry.key] = entry.equilibrium_points_per_model
        if entry.source == "sim":
            sim_count += 1
        else:
            fallback_count += 1

    payload = {
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "threshold": args.threshold,
        "trusted_factions": trusted,
        "n_battles_per_pair": args.battles,
        "budget_per_side": args.budget,
        "anchor_key": args.anchor_key,
        "anchor_per_model": args.anchor_pts,
        "units_sim_fitted": sim_count,
        "units_phase1_fallback": fallback_count,
        "prices": prices,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # Final write succeeded — drop the checkpoint + progress files so the
    # next run starts clean unless explicitly --resume'd.
    for _p in (checkpoint_path, progress_path):
        if _p.exists():
            try:
                _p.unlink()
            except OSError:
                pass
    print(
        f"Equation fitted: {sim_count} units from sim, "
        f"{fallback_count} via Phase 1 fallback"
    )
    print(
        f"{result.battles_run:,} battles in {result.wall_clock_sec:.1f} s  "
        f"({result.wall_clock_sec * 1000 / max(1, result.battles_run):.1f} ms/battle)"
    )
    print(f"Written → {out_path}")


if __name__ == "__main__":
    main()
