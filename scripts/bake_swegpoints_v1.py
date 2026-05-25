"""
Bake the v1.0 SwegHammer prices dataset.

Reads UNIT_CATALOG + the Warp Friends meta snapshot, runs the data-driven
equation fit (Track 4), multiplies by faction multipliers, rounds to the
nearest 5 points per model, and writes data/sweg_points_v1.json.

Super-heavy units (>500 pts/model — Titans, Thunderhawks, big strongpoints)
fall back to the GW printed price. The stats-only equation has a structural
~344-pt MAE at that weight class per ROADMAP.md and we'd rather a
defensible "GW had it right for the giant stuff" than a wild equation
output.

Usage:
    python3 scripts/bake_swegpoints_v1.py
        --out data/sweg_points_v1.json
        [--alpha 2.0] [--super-heavy-threshold 500]

The output file is committed; this script is run by hand when the
equation or the meta snapshot changes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

# Allow running as `python3 scripts/bake_swegpoints_v1.py` from repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from code.equation_data_fit import (  # noqa: E402
    default_feature_specs,
    extract_features,
    faction_multipliers,
    fit as eqfit_fit,
)
from code.units import UNIT_CATALOG  # noqa: E402


ROUND_TO = 5
DEFAULT_ALPHA = 2.0
DEFAULT_SUPER_HEAVY = 500.0
DEFAULT_OUT = Path(__file__).parent.parent / "data" / "sweg_points_v1.json"

# The newer equation_vs_meta_snapshot.json (refreshed 2026-05-23 to mark every
# faction is_approx=False per ROADMAP commit 2694a30) is preferred — it
# activates all 22 faction multipliers. We fall back to the older
# meta_comparison_snapshot.json if the newer one is missing.
META_SNAPSHOT_PRIMARY = Path(__file__).parent.parent / "data" / "equation_vs_meta_snapshot.json"
META_SNAPSHOT_FALLBACK = Path(__file__).parent.parent / "data" / "meta_comparison_snapshot.json"


def _round_to(value: float, step: int) -> int:
    """Round to the nearest multiple of `step`, minimum value `step`."""
    return max(step, int(step * round(value / step)))


def _per_unit_feature_contributions(
    features_row, fit_result, specs,
):
    """For one unit's feature row, return [(name, contribution), ...] sorted
    by absolute contribution descending.

    Contribution is coef * transform(feature_value) — the additive piece in
    log-price space.
    """
    spec_by_name = {s.name: s for s in specs}
    contribs = []
    for name, transform, coef in zip(
        fit_result.feature_names,
        fit_result.transforms,
        fit_result.coefficients,
    ):
        spec = spec_by_name.get(name)
        if spec is None:
            # Fallback — synthesize a spec so the transform applies.
            from code.equation_data_fit import FeatureSpec
            spec = FeatureSpec(name=name, transform=transform, include=True)
        value = float(features_row[name])
        transformed = float(spec.apply(np.array([value]))[0])
        contribs.append((name, float(coef) * transformed))
    contribs.sort(key=lambda kv: -abs(kv[1]))
    return contribs


def bake(
    out_path: Path,
    alpha: float = DEFAULT_ALPHA,
    super_heavy_threshold: float = DEFAULT_SUPER_HEAVY,
) -> dict:
    """Build the dataset dict. Caller writes the JSON."""
    print(f"[bake] extracting features from {len(UNIT_CATALOG)} units …",
          flush=True)
    features_df = extract_features()

    print("[bake] fitting equation with default feature spec …", flush=True)
    specs = default_feature_specs()
    fit_result = eqfit_fit(features_df, specs)
    print(f"[bake]   R²={fit_result.r_squared:.4f}  "
          f"MAE(log)={fit_result.mae_log:.4f}  "
          f"intercept={fit_result.intercept:.4f}  "
          f"features={len(fit_result.feature_names)}",
          flush=True)

    mults: dict[str, float] = {}
    snap_path = META_SNAPSHOT_PRIMARY if META_SNAPSHOT_PRIMARY.exists() else META_SNAPSHOT_FALLBACK
    if snap_path.exists():
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        mults = faction_multipliers(snap, alpha=alpha)
        print(f"[bake] loaded {len(mults)} active faction multipliers "
              f"(α={alpha}) from {snap_path.name}", flush=True)
    else:
        print(f"[bake] WARNING: no snapshot at {META_SNAPSHOT_PRIMARY} or "
              f"{META_SNAPSHOT_FALLBACK}; every faction defaults to 1.0× "
              "multiplier.", flush=True)

    n_super_heavy = 0
    n_priced = 0
    prices: dict[str, dict] = {}

    for idx, row in features_df.iterrows():
        key = row["key"]
        name = row["name"]
        faction = row["faction"]
        gw_pts = float(row["gw_points_per_model"])

        equation_per_model = float(fit_result.predicted_price[idx])
        mult = float(mults.get(faction, 1.0))
        adjusted = equation_per_model * mult

        if gw_pts > super_heavy_threshold:
            # Super-heavy fallback: trust GW.
            sweg_pts = _round_to(gw_pts, ROUND_TO)
            method = "gw_fallback_super_heavy"
            n_super_heavy += 1
        elif gw_pts <= 0:
            # No GW baseline (units priced 0 in the catalogue). Use equation.
            sweg_pts = _round_to(adjusted, ROUND_TO)
            method = "equation_no_gw_baseline"
            n_priced += 1
        else:
            sweg_pts = _round_to(adjusted, ROUND_TO)
            method = "equation_plus_faction_multiplier"
            n_priced += 1

        delta_pct = ((sweg_pts - gw_pts) / gw_pts * 100.0) if gw_pts > 0 else None

        contribs = _per_unit_feature_contributions(row, fit_result, specs)
        top3 = [[fname, round(val, 4)] for fname, val in contribs[:3]]

        prices[key] = {
            "name": name,
            "faction": faction,
            "gw_pts_per_model": round(gw_pts, 2),
            "sweg_pts_per_model": int(sweg_pts),
            "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
            "faction_multiplier": round(mult, 3),
            "method": method,
            "top_features": top3,
        }

    payload = {
        "version": "1.0.0",
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "method": "equation_data_fit + faction_multipliers",
        "alpha": alpha,
        "super_heavy_threshold_pts_per_model": super_heavy_threshold,
        "fit_metrics": {
            "r_squared": round(float(fit_result.r_squared), 4),
            "mae_log": round(float(fit_result.mae_log), 4),
            "mae_price": round(float(fit_result.mae_price), 2),
            "intercept": round(float(fit_result.intercept), 4),
        },
        "feature_count": len(fit_result.feature_names),
        "feature_coefficients": [
            {
                "name": n,
                "transform": t,
                "coefficient": round(float(c), 6),
            }
            for n, t, c in zip(
                fit_result.feature_names,
                fit_result.transforms,
                fit_result.coefficients,
            )
        ],
        "faction_multipliers_active": {
            f: round(float(m), 3) for f, m in sorted(mults.items())
        },
        "counts": {
            "total_units": len(prices),
            "priced_by_equation": n_priced,
            "super_heavy_fallback": n_super_heavy,
        },
        "prices": prices,
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Bake the v1 SwegHammer prices dataset.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA,
                        help="Faction-multiplier sensitivity α (default 2.0).")
    parser.add_argument("--super-heavy-threshold", type=float,
                        default=DEFAULT_SUPER_HEAVY,
                        help="GW pts/model above which to use GW prices "
                             "instead of the equation (default 500).")
    args = parser.parse_args()

    payload = bake(args.out, alpha=args.alpha,
                   super_heavy_threshold=args.super_heavy_threshold)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    n_total = payload["counts"]["total_units"]
    n_eq = payload["counts"]["priced_by_equation"]
    n_sh = payload["counts"]["super_heavy_fallback"]
    print(f"[bake] wrote {args.out}", flush=True)
    print(f"[bake]   {n_total} units priced "
          f"({n_eq} via equation, {n_sh} super-heavy fallback)", flush=True)
    print(f"[bake]   R²={payload['fit_metrics']['r_squared']}  "
          f"MAE(log)={payload['fit_metrics']['mae_log']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
