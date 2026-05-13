"""
Data freshness audit.

Run after a BSData refresh to spot drift before it bites. Reports:

  1. Cached `.cat` / `.gst` files that are NOT registered in
     `code/factions.py::CODEX_TO_FACTION`. Without a faction tag a unit drops
     out of the UI's faction filter, so this is the first thing to catch when
     a new codex lands.

  2. Units whose stats have moved by more than a configurable threshold since
     `data/bsdata/parsed.json` was last committed (compared against git HEAD).
     This catches both:
       - upstream balance dataslates (the BSData files changed)
       - mapper changes that altered our derived stats
     Either way it surfaces deltas that may invalidate overrides.

  3. Units present in the current parsed.json but missing from git HEAD's
     parsed.json (new) and vice versa (removed).

Usage:
    python -m code.bsdata.audit                 # default 10% threshold
    python -m code.bsdata.audit --threshold 5   # tighter
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .fetch import CACHE_DIR
from ..factions import CODEX_TO_FACTION

REPO_ROOT = Path(__file__).resolve().parents[2]
PARSED_PATH = REPO_ROOT / "data" / "bsdata" / "parsed.json"

# Fields whose drift is worth flagging. Booleans and string fields are
# compared exactly; numeric fields use the percentage threshold.
NUMERIC_FIELDS = (
    "health", "damage", "hit_probability", "ap", "save",
    "strength", "toughness", "attacks", "weapon_damage_per_shot",
    "min_models", "max_models", "invuln_save", "points_listed",
)
FLAG_FIELDS = (
    "lethal_hits", "sustained_hits", "twin_linked", "devastating_wounds",
    "enabled",
)


def _git_show(path_in_repo: str) -> Optional[str]:
    """Return the contents of `path_in_repo` at git HEAD, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path_in_repo}"],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, check=True,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _load_units_dict(payload_text: str) -> Dict[str, dict]:
    payload = json.loads(payload_text)
    return {u["key"]: u for u in payload.get("units", [])}


def audit_codex_coverage() -> List[str]:
    """List cached .cat/.gst files that aren't in CODEX_TO_FACTION."""
    if not CACHE_DIR.exists():
        return []
    files = sorted(p.name for p in CACHE_DIR.glob("*.cat"))
    return [f for f in files if f not in CODEX_TO_FACTION]


def _significant_drift(old_value, new_value, threshold_pct: float) -> bool:
    """True if values differ meaningfully — abs for non-numeric, pct for numeric."""
    if isinstance(old_value, bool) or isinstance(new_value, bool):
        return old_value != new_value
    try:
        old_f, new_f = float(old_value), float(new_value)
    except (TypeError, ValueError):
        return old_value != new_value
    if old_f == 0 and new_f == 0:
        return False
    if old_f == 0:
        return abs(new_f) >= 0.01
    return abs(new_f - old_f) / abs(old_f) * 100 >= threshold_pct


def audit_stat_drift(threshold_pct: float = 10.0) -> Tuple[Dict, List[str], List[str]]:
    """
    Compare current parsed.json against git HEAD's parsed.json.

    Returns (drift_by_key, added_keys, removed_keys).
      drift_by_key: {unit_key: [(field, old, new), ...]}
    """
    if not PARSED_PATH.exists():
        return {}, [], []

    current = _load_units_dict(PARSED_PATH.read_text(encoding="utf-8"))
    old_text = _git_show("data/bsdata/parsed.json")
    if old_text is None:
        return {}, [], []     # nothing to compare against

    previous = _load_units_dict(old_text)

    current_keys = set(current)
    previous_keys = set(previous)
    added = sorted(current_keys - previous_keys)
    removed = sorted(previous_keys - current_keys)

    drift: Dict[str, List[Tuple[str, object, object]]] = {}
    for key in sorted(current_keys & previous_keys):
        old_u = previous[key]
        new_u = current[key]
        changes: List[Tuple[str, object, object]] = []
        for f in NUMERIC_FIELDS:
            if _significant_drift(old_u.get(f), new_u.get(f), threshold_pct):
                changes.append((f, old_u.get(f), new_u.get(f)))
        for f in FLAG_FIELDS:
            if old_u.get(f) != new_u.get(f):
                changes.append((f, old_u.get(f), new_u.get(f)))
        if changes:
            drift[key] = changes
    return drift, added, removed


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description="BSData freshness audit")
    p.add_argument("--threshold", type=float, default=10.0,
                   help="Percent change to flag for numeric stat drift (default 10)")
    args = p.parse_args(argv)

    print(f"\n=== BSData audit  (drift threshold {args.threshold:.0f}%) ===\n")

    # 1. Codex coverage
    unrecognised = audit_codex_coverage()
    if unrecognised:
        print(f"[!] {len(unrecognised)} cached codex file(s) NOT in CODEX_TO_FACTION:")
        for f in unrecognised:
            print(f"     {f}")
        print("    Fix: add an entry in code/factions.py")
    else:
        print("[OK] All cached codex files registered in CODEX_TO_FACTION.")

    # 2. Stat drift
    drift, added, removed = audit_stat_drift(threshold_pct=args.threshold)
    print()
    if drift:
        print(f"[!] {len(drift)} unit(s) drifted >={args.threshold:.0f}% since last commit:")
        for key, changes in list(drift.items())[:20]:
            print(f"     {key}")
            for field, old, new in changes:
                print(f"        {field}: {old} -> {new}")
        if len(drift) > 20:
            print(f"     (... and {len(drift) - 20} more)")
    else:
        print("[OK] No significant stat drift since last commit.")

    if added:
        print(f"\n[+] {len(added)} unit(s) added since last commit:")
        for k in added[:10]:
            print(f"     {k}")
        if len(added) > 10:
            print(f"     (... and {len(added) - 10} more)")
    if removed:
        print(f"\n[-] {len(removed)} unit(s) removed since last commit:")
        for k in removed[:10]:
            print(f"     {k}")
        if len(removed) > 10:
            print(f"     (... and {len(removed) - 10} more)")

    print()
    if not (unrecognised or drift or added or removed):
        print("All clean. Safe to ship.\n")


if __name__ == "__main__":
    main(sys.argv[1:])
