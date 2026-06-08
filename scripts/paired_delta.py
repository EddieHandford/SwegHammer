"""Paired / Common-Random-Numbers A/B for the calibration eval (speed lever #1).

The eval runs the OFF and ON arms on the SAME deterministic ``pair_seed``
schedule (evaluate_vs_meta.py), so every ``(a_fac, b_fac, seed)`` battle is a
MATCHED PAIR. Subtracting two aggregate win-rates throws that pairing away; this
tool JOINS the two arms game-for-game and reports the low-variance PAIRED delta.

Why it is decisive at low N: for a gated *faithful* change most games are
IDENTICAL OFF-vs-ON (the change never fired, or fired without flipping the
result), so they carry zero delta-variance. The whole signal lives in the small
set of FLIPPED games — a low-variance count — so "did this change help/hurt, and
which factions" resolves at N=40 or even N=20, while the absolute win-rate frame
stays noisy at those N. (Research: Common Random Numbers gives up to ~90 %
variance reduction on the delta.) The benefit scales with OFF/ON correlation, so
BIG re-bases that restructure every army (random-fill) still want N=80.

Workflow (composes with the reuse-confirmed-frame method — log the OFF arm once,
reuse it across A/Bs):

    PYTHONHASHSEED=0 python -m scripts.evaluate_vs_meta --battles 40 --use-archetype --log-games off.json
    SWEG_NEW=1 PYTHONHASHSEED=0 python -m scripts.evaluate_vs_meta --battles 40 --use-archetype --log-games on.json
    python -m scripts.paired_delta off.json on.json

Per-faction it reports the OFF/ON field-weighted win rate (the existing frame
convention — faction as the A-side), the naive aggregate delta, and the PAIRED
delta with a 95 % confidence interval and a keep/reject verdict.
"""
from __future__ import annotations

import os

# evaluate_vs_meta re-execs itself at import time unless PYTHONHASHSEED == "0"
# (to lock set-iteration order for the *simulator*). This tool only does
# arithmetic on already-logged winners, so the real hash seed is irrelevant to
# its correctness — force the env so the import never mis-triggers that re-exec.
os.environ["PYTHONHASHSEED"] = "0"

import argparse
import json
import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from scripts.evaluate_vs_meta import (  # noqa: E402  (after the env guard above)
    FACTIONS,
    _load_noise_floor,
    _load_tournament_games,
    _load_tournament_target,
    _noise_gated_error,
)

Winner = Optional[str]  # "A" (a_fac won), "B" (b_fac won), or None (draw)


# ----------------------------------------------------------------------------
# Pure, testable paired-statistics helpers (no I/O, no data-file dependency).
# ----------------------------------------------------------------------------
def _cell_flips(off: List[Winner], on: List[Winner]) -> Tuple[int, int, int]:
    """Count A-position result flips between two arms of one matched cell.

    ``off`` and ``on`` are aligned per seed (same index = same pair_seed). From
    the A-side's perspective a game is a "win" iff the winner is ``"A"``.
    Returns ``(b, c, n)``:
      b = games the A-side did NOT win OFF but DID win ON (flip toward A-win),
      c = games the A-side won OFF but did NOT win ON (flip toward A-loss),
      n = matched games.
    The marginal A-win-rate change for the cell is ``(b - c) / n``; only the
    discordant games ``b + c`` carry variance (the McNemar structure).
    """
    if len(off) != len(on):
        raise ValueError(f"cell arm length mismatch: {len(off)} vs {len(on)}")
    b = c = 0
    for o, n_ in zip(off, on):
        o_win = (o == "A")
        n_win = (n_ == "A")
        if n_win and not o_win:
            b += 1
        elif o_win and not n_win:
            c += 1
    return b, c, len(off)


def _cell_delta_var(b: int, c: int, n: int) -> Tuple[float, float]:
    """McNemar paired-proportion delta and its variance for one cell, in pts.

    delta = (b - c) / n * 100. Variance of the paired difference of marginal
    proportions is (b + c - (b - c)**2 / n) / n**2 (clamped >= 0), scaled to
    percentage points. n == 0 yields (0, 0).
    """
    if n <= 0:
        return 0.0, 0.0
    delta = (b - c) / n * 100.0
    raw = (b + c) - (b - c) ** 2 / n
    var = max(0.0, raw) / (n ** 2) * (100.0 ** 2)
    return delta, var


def _weighted_delta(cells: List[Tuple[int, int, int, float]]) -> Tuple[float, float, int]:
    """Field-weighted paired delta across a faction's opponent cells.

    ``cells`` is a list of ``(b, c, n, weight)`` — one per opponent the faction
    fought as the A-side. Returns ``(delta_pts, se_pts, discordant)`` where the
    delta is the weight-normalised mean of the per-cell deltas and the standard
    error combines the per-cell McNemar variances under the field weights.
    """
    num = den = var_num = 0.0
    discordant = 0
    for b, c, n, w in cells:
        if n <= 0 or w <= 0:
            continue
        d, v = _cell_delta_var(b, c, n)
        num += w * d
        var_num += (w ** 2) * v
        den += w
        discordant += b + c
    if den <= 0:
        return 0.0, 0.0, discordant
    delta = num / den
    se = math.sqrt(var_num) / den
    return delta, se, discordant


def _verdict(delta: float, ci: float) -> str:
    """Keep/reject glyph: decisive up/down only when the 95% CI excludes zero."""
    if delta - ci > 0:
        return "UP"
    if delta + ci < 0:
        return "DOWN"
    return "flat"


# ----------------------------------------------------------------------------
# Game-log I/O + frame reconstruction.
# ----------------------------------------------------------------------------
def _load_log(path: str) -> Tuple[int, Dict[Tuple[str, str, int], Winner]]:
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    games: Dict[Tuple[str, str, int], Winner] = {}
    for a, b, s, w in d["games"]:
        games[(a, b, int(s))] = w
    return int(d["n"]), games


def _frame(games: Dict[Tuple[str, str, int], Winner],
           weights: Dict[str, int]) -> Dict[str, float]:
    """Field-weighted per-faction A-position win rate (matches run_matrix.out)."""
    pair_n: Dict[Tuple[str, str], int] = defaultdict(int)
    pair_awins: Dict[Tuple[str, str], int] = defaultdict(int)
    for (a, b, _s), w in games.items():
        pair_n[(a, b)] += 1
        if w == "A":
            pair_awins[(a, b)] += 1
    out: Dict[str, float] = {}
    for fac in FACTIONS:
        num = den = 0.0
        for opp in FACTIONS:
            if opp == fac:
                continue
            n = pair_n.get((fac, opp), 0)
            if n == 0:
                continue
            wr = pair_awins.get((fac, opp), 0) / n * 100.0
            w = weights[opp]
            num += wr * w
            den += w
        out[fac] = num / den if den else 0.0
    return out


def paired_report(off_path: str, on_path: str) -> None:
    n_off, off = _load_log(off_path)
    n_on, on = _load_log(on_path)
    weights = _load_tournament_games()
    target = _load_tournament_target()
    noise = _load_noise_floor()

    # Join on the intersection of matched (a, b, seed) keys (handles sequential
    # extension where one arm has more seeds — only matched games are paired).
    keys = off.keys() & on.keys()
    matched = len(keys)
    if matched == 0:
        raise SystemExit("No matched (a_fac, b_fac, seed) games between the two logs.")
    if off.keys() != on.keys():
        print(f"NOTE: arms differ in seed coverage (OFF {len(off)} / ON {len(on)} "
              f"games); pairing on the {matched} matched games.\n")

    off_m = {k: off[k] for k in keys}
    on_m = {k: on[k] for k in keys}
    off_frame = _frame(off_m, weights)
    on_frame = _frame(on_m, weights)

    # Per-faction paired delta over its A-side opponent cells.
    per_fac_cells: Dict[str, List[Tuple[int, int, int, float]]] = defaultdict(list)
    by_cell_off: Dict[Tuple[str, str], List[Winner]] = defaultdict(list)
    by_cell_on: Dict[Tuple[str, str], List[Winner]] = defaultdict(list)
    for (a, b, s) in sorted(keys):
        by_cell_off[(a, b)].append(off_m[(a, b, s)])
        by_cell_on[(a, b)].append(on_m[(a, b, s)])
    for fac in FACTIONS:
        for opp in FACTIONS:
            if opp == fac:
                continue
            cell = (fac, opp)
            if cell not in by_cell_off:
                continue
            bcell, ccell, ncell = _cell_flips(by_cell_off[cell], by_cell_on[cell])
            per_fac_cells[fac].append((bcell, ccell, ncell, float(weights[opp])))

    print(f"PAIRED / CRN A/B  —  OFF={off_path}  ON={on_path}")
    print(f"matched games: {matched}  (N_off={n_off}, N_on={n_on})\n")
    # ASCII-only output: Windows cp1252 stdout crashes on Unicode (delta/+-),
    # and eval tooling must print regardless of the console encoding.
    header = (f"{'Faction':<24}{'OFF':>7}{'ON':>7}{'aggD':>7}"
              f"{'pairedD':>9}{'ci95':>7}{'flips':>7}  verdict")
    print(header)
    print("-" * len(header))

    gated_off = gated_on = 0.0
    decisive: List[str] = []
    for fac in FACTIONS:
        offwr = off_frame[fac]
        onwr = on_frame[fac]
        aggd = onwr - offwr
        delta, se, disc = _weighted_delta(per_fac_cells.get(fac, []))
        ci = 1.96 * se
        v = _verdict(delta, ci)
        if v != "flat":
            decisive.append(f"{fac} {v} {delta:+.2f}")
        gated_off += _noise_gated_error(offwr, target[fac], noise[fac])
        gated_on += _noise_gated_error(onwr, target[fac], noise[fac])
        flag = " " if v == "flat" else "*"
        print(f"{fac:<24}{offwr:>7.1f}{onwr:>7.1f}{aggd:>+7.1f}"
              f"{delta:>+9.2f}{ci:>7.2f}{disc:>7}  {v}{flag}")

    nf = len(FACTIONS)
    print("-" * len(header))
    print(f"gated MAE:  OFF {gated_off / nf:.2f}   ON {gated_on / nf:.2f}   "
          f"delta {(gated_on - gated_off) / nf:+.2f}")
    if decisive:
        print(f"DECISIVE movers (95% CI clear of 0): {', '.join(decisive)}")
    else:
        print("No faction moved decisively at this N — paired CI spans 0 for all "
              "(either truly neutral, or extend seeds for a sharper verdict).")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("off_log", help="game-log JSON for the OFF arm (--log-games)")
    p.add_argument("on_log", help="game-log JSON for the ON arm (--log-games)")
    args = p.parse_args()
    paired_report(args.off_log, args.on_log)


if __name__ == "__main__":
    main()
