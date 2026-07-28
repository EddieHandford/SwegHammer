"""Does the simulator's per-faction win rate beat simply guessing the average?

The headline Stage-1 metric is the noise-gated mean absolute error against the
May 2026 Warp Friends per-faction win rates. Mean absolute error has a trap: it
can be driven down by making every prediction more similar to the average,
which is not the same as getting any faction right. The discipline against that
trap is to score the simulator against the NULL MODEL - a predictor that
ignores the simulator entirely and answers one constant for every faction.

The comparison is only honest if the null is scored in the SAME frame and
through the SAME gate as the simulator, so this reproduces the evaluation's own
aggregation exactly:

  * army-A cells only (`winners["A"] / n`), matching evaluate_vs_meta
  * field-weighted across opponents by TOURNAMENT_GAMES, not a uniform mean
  * scored through evaluate_vs_meta._noise_gated_error with the real
    per-faction NOISE_FLOOR

and then applies that identical treatment to the constant predictors. The
symmetrized both-sides frame is reported alongside because the army-A frame
carries per-faction positional bias of up to five points (docs/LEVER_PROTOCOL),
and a skill verdict that only holds in one frame is not a verdict.

  skill = 1 - simulator_error / null_error
          positive -> the simulator carries information reality agrees with
          zero or below -> the metric would improve by deleting the simulator

Run: PYTHONHASHSEED=0 python -m scripts._skill_vs_null
     SN_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import json
import math
import os
from collections import Counter, defaultdict

from scripts.evaluate_vs_meta import (
    FACTIONS, TOURNAMENT_TARGET, TOURNAMENT_GAMES, NOISE_FLOOR,
    _noise_gated_error,
)

LOG = os.environ.get("SN_LOG", "data/_anchor_sc69a_n80_log.json")


def _load_games(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["games"] if isinstance(d, dict) else d


def _pair_rates(games):
    """Ordered-pair army-A win rate, exactly as evaluate_vs_meta computes it."""
    wins = defaultdict(Counter)
    played = Counter()
    for g in games:
        fa, fb, _idx, win = g[0], g[1], g[2], g[3]
        played[(fa, fb)] += 1
        if win is not None:
            wins[(fa, fb)][win] += 1
    return {k: wins[k].get("A", 0) / played[k] * 100.0 for k in played}, played


def _field_weighted(rate_of_opponent, fac) -> float:
    """Average over opponents weighted by the real tournament game counts."""
    num = den = 0.0
    for b in FACTIONS:
        if b == fac:
            continue
        r = rate_of_opponent(fac, b)
        if r is None:
            continue
        w = TOURNAMENT_GAMES[b]
        num += r * w
        den += w
    return num / den if den else float("nan")


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def _spearman(xs, ys) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = float(pos)
        return r
    return _pearson(rank(xs), rank(ys))


def _stdev(v) -> float:
    n = len(v)
    m = sum(v) / n
    return math.sqrt(sum((x - m) ** 2 for x in v) / n)


def _score(sim, facs):
    """(raw, gated) mean absolute error for a per-faction prediction map."""
    raw = [abs(sim[f] - TOURNAMENT_TARGET[f]) for f in facs]
    gat = [_noise_gated_error(sim[f], TOURNAMENT_TARGET[f], NOISE_FLOOR[f])
           for f in facs]
    return sum(raw) / len(raw), sum(gat) / len(gat)


def _report_frame(label, sim, facs) -> None:
    real = [TOURNAMENT_TARGET[f] for f in facs]
    sim_v = [sim[f] for f in facs]
    real_mean = sum(real) / len(real)

    s_raw, s_gat = _score(sim, facs)
    nulls = {
        f"constant {real_mean:.1f} (real mean)": {f: real_mean for f in facs},
        "constant 50.0 (even)": {f: 50.0 for f in facs},
    }

    print(f"--- {label} ---")
    print(f"  real spread {_stdev(real):.2f}   simulated spread {_stdev(sim_v):.2f}")
    print(f"  {'predictor':<34}{'raw':>8}{'gated':>8}{'in band':>9}")
    inband = sum(1 for f in facs
                 if _noise_gated_error(sim[f], TOURNAMENT_TARGET[f],
                                       NOISE_FLOOR[f]) == 0.0)
    print(f"  {'SIMULATOR':<34}{s_raw:>8.2f}{s_gat:>8.2f}{inband:>6}/{len(facs)}")
    best_gat = s_gat
    for name, pred in nulls.items():
        n_raw, n_gat = _score(pred, facs)
        n_band = sum(1 for f in facs
                     if _noise_gated_error(pred[f], TOURNAMENT_TARGET[f],
                                           NOISE_FLOOR[f]) == 0.0)
        print(f"  {name:<34}{n_raw:>8.2f}{n_gat:>8.2f}{n_band:>6}/{len(facs)}")
        best_gat = min(best_gat, n_gat)
    for name, pred in nulls.items():
        _, n_gat = _score(pred, facs)
        skill_raw = 1.0 - s_raw / max(_score(pred, facs)[0], 1e-9)
        skill_gat = (1.0 - s_gat / n_gat) if n_gat > 1e-9 else float("nan")
        print(f"  skill vs {name:<25}{skill_raw:>+8.3f}{skill_gat:>+8.3f}")
    print(f"  Pearson simulated vs real {_pearson(sim_v, real):+.3f}   "
          f"Spearman {_spearman(sim_v, real):+.3f}")
    print()


def main() -> None:
    try:
        games = _load_games(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return
    rates, played = _pair_rates(games)

    def a_frame(fac, b):
        return rates.get((fac, b))

    def sym_frame(fac, b):
        """Both-sides: this faction's win rate as army A and as army B."""
        ab, ba = rates.get((fac, b)), rates.get((b, fac))
        if ab is None and ba is None:
            return None
        if ab is None:
            return 100.0 - ba
        if ba is None:
            return ab
        return 0.5 * (ab + (100.0 - ba))

    facs = [f for f in FACTIONS
            if f in TOURNAMENT_TARGET and not math.isnan(_field_weighted(a_frame, f))]

    print(f"=== simulator skill against the null model (log: {LOG}) ===")
    print(f"    {len(games)} games, {len(facs)} factions scored\n")
    _report_frame("army-A frame, field-weighted (the headline frame)",
                  {f: _field_weighted(a_frame, f) for f in facs}, facs)
    _report_frame("symmetrized both-sides frame, field-weighted",
                  {f: _field_weighted(sym_frame, f) for f in facs}, facs)

    sim = {f: _field_weighted(a_frame, f) for f in facs}
    _, s_gat = _score(sim, facs)
    real_mean = sum(TOURNAMENT_TARGET[f] for f in facs) / len(facs)
    _, n_gat = _score({f: real_mean for f in facs}, facs)
    if s_gat >= n_gat:
        print("  VERDICT: on the GATED headline the simulator does not beat answering")
        print("  'average' for every faction. Tuning that lowers the headline without")
        print("  raising the correlation is fitting noise.")
    else:
        print("  VERDICT: the simulator beats the constant null on the gated headline.")
        print(f"  Margin {n_gat - s_gat:.2f} points; judge levers against that margin,")
        print("  not against zero.")


if __name__ == "__main__":
    main()
