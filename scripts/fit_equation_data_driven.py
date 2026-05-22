"""
Data-driven equation fit CLI.

Reads `data/bsdata/parsed.json` + `data/overrides.json` via the live
UNIT_CATALOG, fits a Generalized Additive Model on GW points using
`code.equation_data_fit`, applies per-faction tournament-meta
multipliers from `data/meta_comparison_snapshot.json`, and writes the
result to `data/equation_calibrated_points.json` in the same schema
the existing Streamlit Equilibrium tab consumes.

Usage:
    python -m scripts.fit_equation_data_driven
    python -m scripts.fit_equation_data_driven --alpha 1.5
    python -m scripts.fit_equation_data_driven --out data/custom.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys

# PYTHONHASHSEED guard isn't strictly needed (this script doesn't use the
# simulator or worker pool) but staying consistent with the rest of the
# scripts directory keeps tooling like the Streamlit launcher uniform.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.fit_equation_data_driven"] + sys.argv[1:],
        os.environ,
    )

import numpy as np

from code.equation_data_fit import (
    default_feature_specs,
    extract_features,
    faction_multipliers,
    fit,
)
from code.units import UNIT_CATALOG

_META_SNAPSHOT_PATH = pathlib.Path("data/meta_comparison_snapshot.json")
_OUT_PATH = pathlib.Path("data/equation_calibrated_points.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out", type=str, default=str(_OUT_PATH),
        help="Output JSON path (default: data/equation_calibrated_points.json).",
    )
    ap.add_argument(
        "--meta-snapshot", type=str, default=str(_META_SNAPSHOT_PATH),
        help="Path to the Warp Friends meta snapshot JSON.",
    )
    ap.add_argument(
        "--alpha", type=float, default=2.0,
        help=(
            "Sensitivity of the faction multiplier to win-rate deviation. "
            "multiplier = 1 + alpha * (winrate - 0.5). Default 2.0."
        ),
    )
    ap.add_argument(
        "--mult-min", type=float, default=0.5,
        help="Lower clamp on the faction multiplier.",
    )
    ap.add_argument(
        "--mult-max", type=float, default=2.0,
        help="Upper clamp on the faction multiplier.",
    )
    args = ap.parse_args()

    out_path = pathlib.Path(args.out)
    snap_path = pathlib.Path(args.meta_snapshot)

    # 1) Extract features.
    df = extract_features(UNIT_CATALOG)
    print(f"Features extracted: {len(df)} units")

    # 2) Run the regression with default feature set.
    specs = default_feature_specs()
    result = fit(df, specs)
    print(
        f"Fit: R² = {result.r_squared:.3f}  "
        f"MAE_log = {result.mae_log:.3f}  "
        f"MAE_price = {result.mae_price:.1f} pts/model"
    )

    # 3) Faction multipliers from the Warp Friends snapshot.
    if snap_path.exists():
        meta = json.loads(snap_path.read_text(encoding="utf-8"))
        mults = faction_multipliers(meta, alpha=args.alpha, clip=(args.mult_min, args.mult_max))
        print(f"Faction multipliers loaded: {len(mults)} factions with real data")
        for f in sorted(mults):
            print(f"  {f:<30} mult = {mults[f]:.3f}")
    else:
        print(f"WARNING: meta snapshot {snap_path} not found; no faction correction applied.")
        mults = {}

    # 4) Apply multipliers, build the per-unit prices dict.
    prices = {}
    for i, row in df.iterrows():
        faction = row["faction"]
        base = float(result.predicted_price[i])
        mult = mults.get(faction, 1.0)
        prices[row["key"]] = round(base * mult, 2)

    # 5) Output schema mirrors the sim-driven fit's so the existing
    # Equilibrium tab keeps working. Some fields don't apply (n_battles,
    # build_mode) — set them to sentinels so downstream code sees a
    # consistent shape.
    payload = {
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "data_driven_gam",
        "threshold": None,
        "trusted_factions": sorted(mults.keys()),
        "n_battles_per_pair": 0,
        "budget_per_side": 0,
        "anchor_key": "space_marines_intercessor_squad",
        "anchor_per_model": 16.0,
        "build_mode": "data_driven",
        "units_sim_fitted": len(prices),
        "units_phase1_fallback": 0,
        "fit_metrics": {
            "r_squared": result.r_squared,
            "mae_log": result.mae_log,
            "mae_price": result.mae_price,
            "intercept": result.intercept,
            "feature_count": len(result.feature_names),
        },
        "feature_coefficients": [
            {"name": n, "transform": t, "coefficient": float(c)}
            for n, t, c in zip(result.feature_names, result.transforms, result.coefficients)
        ],
        "faction_multipliers": {f: float(m) for f, m in sorted(mults.items())},
        "alpha": args.alpha,
        "prices": prices,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Written → {out_path}")


if __name__ == "__main__":
    main()
