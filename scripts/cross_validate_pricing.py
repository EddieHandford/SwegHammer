"""
SwegHammer task #132 — Cross-validate the Sweg-balancer (MC bisection) against
the Equilibrium Phase 5 solver.

We have two independent pricing signals:

  1. **Equilibrium Phase 5** (``data/equilibrium_points_phase5.json``) — analytic,
     meta-weighted log-LSQ over the residual matrix.

  2. **Sweg-balancer MC bisection** (``scripts/sweg_balance_mc.py``) — eval-data
     driven, +/-10% per-pass shifts applied to ``data/overrides.json`` for the
     two over-strong and two under-strong factions (T'au Empire, Aeldari,
     Necrons, Thousand Sons in the May 2026 pass).

These should AGREE on direction (and roughly on magnitude) for any unit they
both flag as mispriced.  Where they DISAGREE one of them is wrong.  This script
emits a report so the human reviewer can adjudicate.

Comparison rules
----------------
For every unit in the Phase 5 output:

  * ``phase5_mispricing_pct = (eq_per_model - gw_per_model) / gw_per_model``
    Positive = solver thinks unit should be MORE expensive than GW lists it
    (i.e. GW under-cost the unit).  Negative = solver thinks it should be
    CHEAPER.

  * ``mc_shift_pct = (current_override - gw_per_model) / gw_per_model``
    Positive = MC raised the cost (treated as under-cost).  Negative = MC
    lowered the cost.  No override => 0 (MC said nothing about this unit).

  * **DISAGREEMENT** when ``sign(phase5_mispricing_pct) != sign(mc_shift_pct)``
    AND ``|phase5_mispricing_pct| > 5%`` AND ``|mc_shift_pct| > 5%``.

  * **CONFIRMING** when the signs match AND both magnitudes > 10%.

Run
---
::

    PYTHONIOENCODING=utf-8 python -m scripts.cross_validate_pricing

Pass ``--save`` to also write ``data/pricing_cross_validation.json``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE5_PATH = REPO_ROOT / "data" / "equilibrium_points_phase5.json"
OVERRIDES_PATH = REPO_ROOT / "data" / "overrides.json"
DEFAULT_OUT_PATH = REPO_ROOT / "data" / "pricing_cross_validation.json"

# Thresholds (see module docstring).
DISAGREEMENT_MIN_PCT = 5.0
CONFIRMATION_MIN_PCT = 10.0


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def load_phase5(path: Path = PHASE5_PATH) -> Dict[str, Dict[str, Any]]:
    """Return the phase5 ``units`` map keyed by unit key."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("units", {})


def load_overrides(path: Path = OVERRIDES_PATH) -> Dict[str, Dict[str, Any]]:
    """Return the overrides ``units`` map keyed by unit key.

    Missing file is treated as an empty map (cross-val should still run on a
    clean checkout).
    """
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("units", {})


def cross_validate(
    phase5_units: Dict[str, Dict[str, Any]],
    overrides_units: Dict[str, Dict[str, Any]],
    disagreement_min_pct: float = DISAGREEMENT_MIN_PCT,
    confirmation_min_pct: float = CONFIRMATION_MIN_PCT,
) -> List[Dict[str, Any]]:
    """Build a per-unit cross-validation record.

    One dict per Phase 5 unit, containing the GW reference points, the two
    signals' percentage shifts, their flagged status, and human-readable name.
    """
    rows: List[Dict[str, Any]] = []
    for key, entry in phase5_units.items():
        gw_pm = float(entry.get("gw_points_per_model") or 0.0)
        eq_pm = float(entry.get("equilibrium_points_per_model") or 0.0)
        if gw_pm <= 0:
            # Cannot compute relative shifts without a positive baseline.
            continue
        phase5_pct = (eq_pm - gw_pm) / gw_pm * 100.0

        override_entry = overrides_units.get(key) or {}
        override_pm: Optional[float] = override_entry.get("points_override")
        if override_pm is None:
            mc_pct = 0.0
            mc_has_override = False
        else:
            mc_pct = (float(override_pm) - gw_pm) / gw_pm * 100.0
            mc_has_override = True

        disagree = (
            _sign(phase5_pct) != _sign(mc_pct)
            and abs(phase5_pct) > disagreement_min_pct
            and abs(mc_pct) > disagreement_min_pct
        )
        confirm = (
            _sign(phase5_pct) == _sign(mc_pct)
            and _sign(phase5_pct) != 0
            and abs(phase5_pct) > confirmation_min_pct
            and abs(mc_pct) > confirmation_min_pct
        )

        rows.append({
            "key": key,
            "name": entry.get("name", key),
            "faction": entry.get("faction", ""),
            "gw_points_per_model": round(gw_pm, 2),
            "phase5_equilibrium_per_model": round(eq_pm, 2),
            "phase5_mispricing_pct": round(phase5_pct, 2),
            "mc_override_per_model": (
                round(float(override_pm), 2) if mc_has_override else None
            ),
            "mc_shift_pct": round(mc_pct, 2),
            "mc_has_override": mc_has_override,
            "disagreement": bool(disagree),
            "confirmation": bool(confirm),
            # Magnitude used for ranking top-N: combined strength of both
            # signals (geometric mean keeps a strong signal from being washed
            # out by a weak counterpart).
            "_combined_strength": (
                abs(phase5_pct) * abs(mc_pct)
            ) ** 0.5,
        })
    return rows


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return high-level counts plus the top-20 disagreements/confirmations."""
    disagreements = [r for r in rows if r["disagreement"]]
    confirmations = [r for r in rows if r["confirmation"]]

    disagreements.sort(key=lambda r: r["_combined_strength"], reverse=True)
    confirmations.sort(key=lambda r: r["_combined_strength"], reverse=True)

    return {
        "total_units": len(rows),
        "units_with_mc_override": sum(1 for r in rows if r["mc_has_override"]),
        "disagreement_count": len(disagreements),
        "confirmation_count": len(confirmations),
        "top_disagreements": disagreements[:20],
        "top_confirmations": confirmations[:20],
    }


def _fmt_row(r: Dict[str, Any]) -> str:
    return (
        f"  {r['faction'][:18]:18s}  {r['name'][:46]:46s}  "
        f"phase5={r['phase5_mispricing_pct']:+7.1f}%  "
        f"MC={r['mc_shift_pct']:+6.1f}%"
    )


def print_report(summary: Dict[str, Any]) -> None:
    print("=" * 100)
    print("SwegHammer pricing cross-validation: Equilibrium Phase 5 vs Sweg-balancer MC")
    print("=" * 100)
    print(
        f"Phase 5 units evaluated : {summary['total_units']}\n"
        f"Units with MC override  : {summary['units_with_mc_override']}\n"
        f"Disagreements (>5%, opposite sign) : {summary['disagreement_count']}\n"
        f"Confirmations (>10%, same sign)    : {summary['confirmation_count']}"
    )
    print("\nTop disagreements (Phase 5 and MC point opposite ways):")
    if not summary["top_disagreements"]:
        print("  (none)")
    else:
        for r in summary["top_disagreements"]:
            print(_fmt_row(r))
    print("\nTop confirmations (Phase 5 and MC agree, both strong):")
    if not summary["top_confirmations"]:
        print("  (none)")
    else:
        for r in summary["top_confirmations"]:
            print(_fmt_row(r))


def _strip_internal(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop the ``_combined_strength`` sort key from rows before serialising."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def save_report(summary: Dict[str, Any], out_path: Path) -> None:
    payload = {
        "_comment": (
            "Cross-validation of the Equilibrium Phase 5 analytic solver "
            "against the Sweg-balancer MC bisection. See "
            "scripts/cross_validate_pricing.py for thresholds and methodology."
        ),
        "thresholds": {
            "disagreement_min_pct": DISAGREEMENT_MIN_PCT,
            "confirmation_min_pct": CONFIRMATION_MIN_PCT,
        },
        "total_units": summary["total_units"],
        "units_with_mc_override": summary["units_with_mc_override"],
        "disagreement_count": summary["disagreement_count"],
        "confirmation_count": summary["confirmation_count"],
        "top_disagreements": _strip_internal(summary["top_disagreements"]),
        "top_confirmations": _strip_internal(summary["top_confirmations"]),
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out_path}")


def run(
    save: bool = False,
    out_path: Path = DEFAULT_OUT_PATH,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Programmatic entry point — load, compare, summarise, optionally save."""
    phase5 = load_phase5()
    overrides = load_overrides()
    rows = cross_validate(phase5, overrides)
    summary = summarise(rows)
    if save:
        save_report(summary, out_path)
    return rows, summary


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Cross-validate the Phase 5 equilibrium solver vs MC balancer.",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Also write the report to data/pricing_cross_validation.json",
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT_PATH,
        help="Output path when --save is given.",
    )
    args = parser.parse_args(argv)
    _rows, summary = run(save=args.save, out_path=args.out)
    print_report(summary)


if __name__ == "__main__":
    main()
