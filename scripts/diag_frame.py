"""Frame-integrity diagnostic — A-frame vs B-frame vs SYMMETRIZED win rates.

The calibration frame (`paired_delta._frame`) scores each faction from its
ARMY-A cells only. But the simulator has measurable positional artifacts —
per-faction A-vs-B win-rate gaps up to ~9 points (Chaos Daemons −9.3,
Imperial Knights +7.2 on sc57a) and a going-first win rate of ~62% vs the
real ~50% — while the Warp Friends TARGET is position-agnostic. The A-frame
is therefore a BIASED estimator of a faction's sim strength: a faction the
sim's positional artifacts punish as army A reads too low, and vice versa.

The unbiased estimator of the same quantity averages the two orientations of
each matchup: for faction f vs opponent o, sym_wr = (wr[f as A vs o] +
wr[f as B vs o-as-A]) / 2. Every ordered pair exists in a full-matrix anchor,
so this needs no new games — it re-reads the standing anchor.

This script prints, per faction: the standing A-frame, the B-frame, the
asymmetry, the symmetrized frame, and the noise-gated error under BOTH
estimators, plus both gated MAEs. Use it (a) to see how much of a pole is
frame artifact vs real sim-vs-reality discrepancy, and (b) alongside any
lever screen that touches tempo / going-first / positional behaviour, where
an A-frame-only verdict may be confounded.

NOTE: adopting the symmetrized frame as the official metric is a FRAME
CHANGE (invalidates prior verdict comparability, requires a re-anchor and
owner sign-off). Until then this is a diagnostic lens only.

Run:
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_frame \
      data/_anchor_sc57a_n80_log.json [--faction "Chaos Daemons"]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

from scripts.evaluate_vs_meta import (
    FACTIONS,
    _load_noise_floor,
    _load_tournament_games,
    _load_tournament_target,
    _noise_gated_error,
)
from scripts.paired_delta import _frame


def _cells(games_list):
    """Per ordered cell (a_fac, b_fac): (A-wins, B-wins, games)."""
    aw = defaultdict(int)
    bw = defaultdict(int)
    n = defaultdict(int)
    for a, b, _s, w in games_list:
        n[(a, b)] += 1
        if w == "A":
            aw[(a, b)] += 1
        elif w == "B":
            bw[(a, b)] += 1
    return aw, bw, n


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("anchor", help="full-matrix game-log JSON (a standing anchor)")
    p.add_argument("--faction", help="also print this faction's per-opponent A/B/sym rows")
    args = p.parse_args()

    games_list = json.load(open(args.anchor))["games"]
    aw, bw, n = _cells(games_list)
    weights = _load_tournament_games()
    target = _load_tournament_target()
    noise = _load_noise_floor()

    # Cross-check our A-frame replication against the canonical _frame.
    frame_ref = _frame({(a, b, s): w for a, b, s, w in games_list}, weights)

    def wr_as_a(f, o):
        c = n[(f, o)]
        return 100.0 * aw[(f, o)] / c if c else None

    def wr_as_b(f, o):
        c = n[(o, f)]
        return 100.0 * bw[(o, f)] / c if c else None

    total_a = sum(aw.values())
    total_b = sum(bw.values())
    total_n = sum(n.values())
    print(f"# {args.anchor}: {total_n} games; global A-win {100*total_a/total_n:.1f}% "
          f"B-win {100*total_b/total_n:.1f}% draw {100*(total_n-total_a-total_b)/total_n:.1f}%")

    rows = []
    gated_a = gated_sym = 0.0
    max_ref_diff = 0.0
    for f in FACTIONS:
        num_a = num_sym = den = 0.0
        for o in FACTIONS:
            if o == f:
                continue
            a_wr = wr_as_a(f, o)
            if a_wr is None:
                continue
            b_wr = wr_as_b(f, o)
            sym = a_wr if b_wr is None else (a_wr + b_wr) / 2.0
            wgt = float(weights[o])
            num_a += wgt * a_wr
            num_sym += wgt * sym
            den += wgt
        if not den:
            continue
        fa = num_a / den
        fs = num_sym / den
        max_ref_diff = max(max_ref_diff, abs(fa - frame_ref[f]))
        ea = _noise_gated_error(fa, target[f], noise[f])
        es = _noise_gated_error(fs, target[f], noise[f])
        gated_a += ea
        gated_sym += es
        rows.append((ea, f, target[f], noise[f], fa, fs, fs - fa, es))

    if max_ref_diff > 0.05:
        print(f"!! A-frame replication differs from paired_delta._frame by up to "
              f"{max_ref_diff:.2f} — treat sym numbers as approximate.")

    rows.sort(reverse=True)
    print(f"{'faction':24s} {'tgt':>5s} {'noise':>5s} {'A-frame':>8s} {'sym':>6s} "
          f"{'A/B-bias':>8s} {'gatedA':>6s} {'gatedSym':>8s}")
    for ea, f, tgt, nz, fa, fs, dbias, es in rows:
        print(f"{f:24s} {tgt:5.1f} {nz:5.1f} {fa:8.1f} {fs:6.1f} {dbias:+8.1f} "
              f"{ea:6.2f} {es:8.2f}")
    nf = len(FACTIONS)
    print(f"\ngated MAE  A-frame: {gated_a/nf:.2f}   symmetrized: {gated_sym/nf:.2f}")

    if args.faction:
        f = args.faction
        print(f"\n# per-opponent detail — {f}")
        print(f"{'opponent':24s} {'asA%':>6s} {'asB%':>6s} {'sym%':>6s} {'weight':>7s}")
        det = []
        for o in FACTIONS:
            if o == f or not n[(f, o)]:
                continue
            a_wr = wr_as_a(f, o)
            b_wr = wr_as_b(f, o)
            sym = a_wr if b_wr is None else (a_wr + b_wr) / 2.0
            det.append((sym, o, a_wr, b_wr, float(weights[o])))
        det.sort()
        for sym, o, a_wr, b_wr, wgt in det:
            b_txt = f"{b_wr:6.1f}" if b_wr is not None else "   n/a"
            print(f"{o:24s} {a_wr:6.1f} {b_txt} {sym:6.1f} {wgt:7.0f}")


if __name__ == "__main__":
    main()
