"""Fit the wounds-to-victory-points exchange rate from a margins-extended game log.

The exchange-rate grounding lane (docs/DECISION_LEDGER.md, pre-registered
2026-07-10, method amended 2026-07-11 before data): every layer composition
inherits `_trade_vp_per_wound`, an ASSERTED constant converting damage dealt
into victory-point-equivalents. This tool measures it instead.

Method (the amended, well-posed form):
  * Data: a `--log-games` file written with `--log-margins` — per game the
    final capped victory points of both sides and the points-value destroyed
    on both sides.
  * Fit: ordinary-least-squares slope of final victory-point margin
    (a_vp - b_vp) on kill margin (b_points_lost - a_points_lost, army A's
    kills minus its losses). The slope beta is the measured victory-point
    value of destroying one enemy point. The intercept absorbs the known
    A-frame positional bias and is reported, not suppressed.
  * Stability: the same slope per faction (games pooled from both slots with
    signs flipped for slot B) and a win-rate-by-kill-margin-decile table as
    the direction check (no logistic fit — the registered logistic form was
    degenerate and is not computed).
  * Confounding caveat (registered in advance): the observational slope
    conflates "killing causes scoring" with "winning armies do both"; the
    number is a grounded decision-heuristic price, not a causal estimate.

Usage:
  python -m scripts.fit_exchange_rate data/_margins_sc62a_n40_log.json

No simulator imports, no random draws — pure log analysis.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict


def _ols(xs: list, ys: list):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return 0.0, my, 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    beta = cov / var
    alpha = my - beta * mx
    ss_res = sum((y - (alpha + beta * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return beta, alpha, r2


def main() -> None:
    path = sys.argv[1]
    d = json.load(open(path, encoding="utf-8"))
    games = d["games"]
    margins = d.get("margins")
    if not margins:
        raise SystemExit(
            f"{path} has no 'margins' key - re-run the evaluation with "
            "--log-margins (scripts/evaluate_vs_meta.py)."
        )
    assert len(margins) == len(games), "margins/games misaligned"

    xs, ys = [], []                      # kill margin -> vp margin, A view
    per_faction = defaultdict(lambda: ([], []))
    wins_by_x = []                       # (kill margin, A won) for deciles
    for (a_fac, b_fac, _seed, winner), m in zip(games, margins):
        a_vp, b_vp, a_lost, b_lost = m[0], m[1], m[2], m[3]
        vp_margin = a_vp - b_vp
        kill_margin = b_lost - a_lost
        xs.append(kill_margin)
        ys.append(vp_margin)
        wins_by_x.append((kill_margin, 1.0 if winner == "A" else 0.0))
        fa_x, fa_y = per_faction[a_fac]
        fa_x.append(kill_margin); fa_y.append(vp_margin)
        fb_x, fb_y = per_faction[b_fac]
        fb_x.append(-kill_margin); fb_y.append(-vp_margin)

    beta, alpha, r2 = _ols(xs, ys)
    print(f"games: {len(xs)}")
    print(f"HEADLINE  beta = {beta:.6f} victory points per enemy point destroyed")
    print(f"          intercept (A-frame bias absorber) = {alpha:.3f} vp,  R^2 = {r2:.3f}")
    print()
    print("Per-faction slope stability (pooled both slots, signs flipped for slot B):")
    rows = []
    for fac, (fx, fy) in sorted(per_faction.items()):
        fb, fa_, fr2 = _ols(fx, fy)
        rows.append((fac, fb, fa_, fr2, len(fx)))
    for fac, fb, fa_, fr2, n in rows:
        print(f"  {fac:<24} beta={fb:.6f}  intercept={fa_:+7.2f}  R^2={fr2:.3f}  n={n}")
    betas = [r[1] for r in rows]
    mean_b = sum(betas) / len(betas)
    sd_b = (sum((b - mean_b) ** 2 for b in betas) / len(betas)) ** 0.5
    print(f"  spread: mean {mean_b:.6f}, sd {sd_b:.6f}, "
          f"min {min(betas):.6f}, max {max(betas):.6f}")
    print()
    print("Direction check - win rate by kill-margin decile:")
    wins_by_x.sort(key=lambda t: t[0])
    n = len(wins_by_x)
    for dec in range(10):
        lo, hi = dec * n // 10, (dec + 1) * n // 10
        chunk = wins_by_x[lo:hi]
        if not chunk:
            continue
        wr = sum(w for _, w in chunk) / len(chunk)
        print(f"  decile {dec}: kill margin [{chunk[0][0]:+8.1f}, {chunk[-1][0]:+8.1f}]  "
              f"win rate {wr:.3f}  (n={len(chunk)})")


if __name__ == "__main__":
    main()
