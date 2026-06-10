"""Rolling regression sentinel — ledger of per-wave paired-eval deltas + drift check.

Records one calibration_ledger.json entry per wave (subcommand: record) and
checks for faction-level regressions across the ledger history (subcommand:
check).  Both subcommands are designed for use in the auto-loop after a paired
A/B has completed.

Usage:
    # After a paired A/B run has produced off.json and on.json:
    python -m scripts.regression_sentinel record --wave wave123 \
        --off data/off.json --on data/on.json --note "some description"

    # At any time to check for regressions vs earlier confirmed frames:
    python -m scripts.regression_sentinel check --threshold 1.0
"""
from __future__ import annotations

import os

# evaluate_vs_meta re-execs itself at import time unless PYTHONHASHSEED == "0"
# (to lock set-iteration order for the simulator).  Mirror the guard used in
# paired_delta.py so this module is safe to import without an env prefix.
os.environ["PYTHONHASHSEED"] = "0"

import argparse
import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional

from scripts.evaluate_vs_meta import (  # noqa: E402
    FACTIONS,
    _load_noise_floor,
    _load_tournament_games,
    _load_tournament_target,
    _noise_gated_error,
)
from scripts.paired_delta import (  # noqa: E402
    _load_log,
    compute_paired,
)

LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "calibration_ledger.json"


# ---------------------------------------------------------------------------
# Pure, testable drift-detection logic — no I/O, no data-file dependency.
# ---------------------------------------------------------------------------

def detect_drift(
    entries: List[dict],
    threshold: float = 1.0,
) -> List[str]:
    """Scan a list of ledger entries and return a list of human-readable drift findings.

    Findings are ASCII-only strings (no unicode glyphs).  Two checks are run:

    1. Per-faction regression: a faction that was IN-BAND (frame_gated_on value
       == 0.0) in at least one earlier entry but is OUT-OF-BAND
       (frame_gated_on value > threshold) in the LATEST entry is flagged as a
       DRIFT.  The report names the FIRST entry where the faction went
       out-of-band (the bisect hint).

    2. Headline creep: if the latest entry's gated_on crept upward by more
       than <threshold> vs the MINIMUM gated_on across all entries, flag
       cumulative creep.

    Returns an empty list when nothing drifted.
    """
    if len(entries) < 2:
        return []

    findings: List[str] = []

    latest = entries[-1]
    earlier = entries[:-1]

    # ---------- per-faction regression check ----------
    # Build the set of factions that were EVER in-band in earlier entries.
    ever_in_band: set = set()
    for entry in earlier:
        for fac in entry.get("in_band", []):
            ever_in_band.add(fac)

    # For each such faction, check if it is now out-of-band in the latest entry.
    latest_frame = latest.get("frame_gated_on", {})
    for fac in ever_in_band:
        latest_gated = latest_frame.get(fac, 0.0)
        if latest_gated > threshold:
            # Find the FIRST entry (across ALL entries, including earlier) where
            # the faction went out-of-band.
            first_out_wave = _first_out_of_band_wave(entries, fac, threshold)
            findings.append(
                f"DRIFT {fac}: was in-band, now gated_on={latest_gated:.2f} "
                f"(first out-of-band wave: {first_out_wave})"
            )

    # ---------- headline creep check ----------
    all_gated = [e.get("gated_on", 0.0) for e in entries]
    min_gated = min(all_gated)
    latest_gated_on = latest.get("gated_on", 0.0)
    creep = latest_gated_on - min_gated
    if creep > threshold:
        min_wave = entries[all_gated.index(min_gated)].get("wave", "unknown")
        findings.append(
            f"CREEP: headline gated_on {latest_gated_on:.2f} is {creep:.2f} pts "
            f"above the ledger minimum {min_gated:.2f} (set at wave {min_wave})"
        )

    return findings


def _first_out_of_band_wave(entries: List[dict], fac: str, threshold: float) -> str:
    """Return the wave name of the FIRST ledger entry where fac is out-of-band.

    Scans forward through all entries.  Returns 'unknown' if not found
    (should not happen in practice when called after confirming out-of-band in
    the latest entry).
    """
    for entry in entries:
        gated = entry.get("frame_gated_on", {}).get(fac, 0.0)
        if gated > threshold:
            return entry.get("wave", "unknown")
    return "unknown"


# ---------------------------------------------------------------------------
# Ledger I/O helpers.
# ---------------------------------------------------------------------------

def _load_ledger(path: Path) -> List[dict]:
    """Load the JSON ledger, returning an empty list if the file does not exist yet."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _save_ledger(path: Path, entries: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2)


# ---------------------------------------------------------------------------
# Subcommand implementations.
# ---------------------------------------------------------------------------

def cmd_record(args: argparse.Namespace) -> None:
    """Join two game-log files via compute_paired and append one ledger entry."""
    off_path = args.off
    on_path = args.on

    if not Path(off_path).exists():
        raise FileNotFoundError(
            f"OFF game-log not found: {off_path} "
            f"(CLAUDE.md rule 13: fail loud on missing data)"
        )
    if not Path(on_path).exists():
        raise FileNotFoundError(
            f"ON game-log not found: {on_path} "
            f"(CLAUDE.md rule 13: fail loud on missing data)"
        )

    _n_off, off_games = _load_log(off_path)
    _n_on, on_games = _load_log(on_path)

    weights = _load_tournament_games()
    target = _load_tournament_target()
    noise = _load_noise_floor()

    result = compute_paired(off_games, on_games, weights, target, noise)

    # compute_paired gives us gated_off/gated_on as the MEAN over all factions
    # and per-faction onwr in result["factions"][fac]["onwr"].  We need the
    # per-faction gated error for the ON frame so detect_drift can track
    # individual faction trajectories.
    per_fac_gated_on: Dict[str, float] = {}
    in_band: List[str] = []
    decisive: List[str] = []

    for fac in FACTIONS:
        fdata = result["factions"][fac]
        onwr = fdata["onwr"]
        gated = _noise_gated_error(onwr, target[fac], noise[fac])
        per_fac_gated_on[fac] = gated
        if gated == 0.0:
            in_band.append(fac)
        v = fdata["verdict"]
        if v != "flat":
            delta = fdata["delta"]
            decisive.append(f"{fac} {v} {delta:+.2f}")

    entry: dict = {
        "wave": args.wave,
        "timestamp": datetime.datetime.now().isoformat(),
        "matched": result["matched"],
        "gated_off": result["gated_off"],
        "gated_on": result["gated_on"],
        "decisive": decisive,
        "in_band": in_band,
        "frame_gated_on": per_fac_gated_on,
    }
    if args.note:
        entry["note"] = args.note

    ledger = _load_ledger(LEDGER_PATH)
    ledger.append(entry)
    _save_ledger(LEDGER_PATH, ledger)

    print(f"Recorded wave {args.wave!r} -> {LEDGER_PATH}")
    print(f"  matched={result['matched']}  gated_off={result['gated_off']:.2f}  "
          f"gated_on={result['gated_on']:.2f}")
    print(f"  in-band factions ({len(in_band)}): {', '.join(in_band) if in_band else 'none'}")
    if decisive:
        print(f"  decisive movers: {', '.join(decisive)}")
    else:
        print("  no decisive movers")


def cmd_check(args: argparse.Namespace) -> None:
    """Read the ledger and print a drift report."""
    threshold: float = args.threshold
    ledger = _load_ledger(LEDGER_PATH)

    if not ledger:
        print(f"no regression detected (0 waves in ledger)")
        return

    n = len(ledger)
    findings = detect_drift(ledger, threshold)

    if not findings:
        print(f"no regression detected ({n} waves in ledger)")
    else:
        print(f"REGRESSION REPORT ({n} waves in ledger, threshold={threshold:.2f})")
        print("-" * 60)
        for finding in findings:
            print(f"  {finding}")
        print("-" * 60)
        print(f"  {len(findings)} issue(s) found")


# ---------------------------------------------------------------------------
# CLI entry-point.
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Rolling regression sentinel for calibration wave ledger."
    )
    sub = p.add_subparsers(dest="subcommand", required=True)

    rec = sub.add_parser("record", help="Append a wave entry to the ledger.")
    rec.add_argument("--wave", required=True, help="Wave label (e.g. wave123)")
    rec.add_argument("--off", required=True, help="Path to OFF arm game-log JSON")
    rec.add_argument("--on", required=True, help="Path to ON arm game-log JSON")
    rec.add_argument("--note", default="", help="Optional free-text note")

    chk = sub.add_parser("check", help="Print a drift report from the ledger.")
    chk.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Gated-error threshold for out-of-band classification (default 1.0)",
    )

    return p


def main() -> None:
    p = _build_parser()
    args = p.parse_args()
    if args.subcommand == "record":
        cmd_record(args)
    else:
        cmd_check(args)


if __name__ == "__main__":
    main()
