"""Which factions is the simulator ordering WRONGLY?

With rank correlation as the Stage 1 headline (docs/METRIC_SKILL_AND_DISPERSION.md),
the work queue should be ordered by rank displacement rather than by residual
size. The two disagree, and the disagreement is the point:

  * a faction can carry a large residual while sitting in almost the right
    place in the order - the whole table is shifted, and fixing it moves the
    distance but not the ordering
  * a faction can carry a small residual while being ranked ten places wrong,
    which is a genuine fidelity failure that distance-based scoring hides

This prints both orderings side by side so the queue can be re-prioritised, and
reports how much each faction contributes to the rank correlation - that is,
how much Spearman would improve if that one faction were placed correctly.

Run: PYTHONHASHSEED=0 python -m scripts._rank_error_table
     RE_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import json
import os
from collections import Counter, defaultdict

from scripts.evaluate_vs_meta import (
    FACTIONS, TOURNAMENT_TARGET, TOURNAMENT_GAMES, NOISE_FLOOR,
    _noise_gated_error, _spearman,
)

LOG = os.environ.get("RE_LOG", "data/_anchor_sc69a_n80_log.json")


def _sim_a_frame(path):
    """Field-weighted army-A win rate, the evaluation's own headline frame."""
    d = json.load(open(path, encoding="utf-8"))
    games = d["games"] if isinstance(d, dict) else d
    wins = defaultdict(Counter)
    played = Counter()
    for g in games:
        fa, fb, _i, win = g[0], g[1], g[2], g[3]
        played[(fa, fb)] += 1
        if win is not None:
            wins[(fa, fb)][win] += 1
    rate = {k: wins[k].get("A", 0) / played[k] * 100.0 for k in played}
    out = {}
    for fac in FACTIONS:
        num = den = 0.0
        for b in FACTIONS:
            if b == fac or (fac, b) not in rate:
                continue
            w = TOURNAMENT_GAMES[b]
            num += rate[(fac, b)] * w
            den += w
        if den:
            out[fac] = num / den
    return out


def main() -> None:
    try:
        sim = _sim_a_frame(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return

    facs = [f for f in FACTIONS if f in sim and f in TOURNAMENT_TARGET]
    # Rank 1 = strongest.
    sim_rank = {f: i + 1 for i, f in
                enumerate(sorted(facs, key=lambda f: -sim[f]))}
    real_rank = {f: i + 1 for i, f in
                 enumerate(sorted(facs, key=lambda f: -TOURNAMENT_TARGET[f]))}

    base = _spearman([sim[f] for f in facs],
                     [TOURNAMENT_TARGET[f] for f in facs])

    rows = []
    for f in facs:
        disp = sim_rank[f] - real_rank[f]
        resid = sim[f] - TOURNAMENT_TARGET[f]
        gated = _noise_gated_error(sim[f], TOURNAMENT_TARGET[f], NOISE_FLOOR[f])
        # How much would the rank correlation improve if this one faction were
        # moved to its correct win rate and everything else left alone?
        fixed = dict(sim)
        fixed[f] = TOURNAMENT_TARGET[f]
        gain = _spearman([fixed[g] for g in facs],
                         [TOURNAMENT_TARGET[g] for g in facs]) - base
        rows.append((abs(disp), gain, f, sim_rank[f], real_rank[f], disp,
                     resid, gated))

    rows.sort(key=lambda r: (-r[0], -r[1]))
    print(f"=== rank displacement ({LOG}) ===")
    print(f"    Spearman now {base:+.3f}\n")
    print(f"{'faction':<24}{'sim rank':>9}{'real rank':>10}{'displaced':>11}"
          f"{'residual':>10}{'gated':>7}{'Spearman gain':>15}")
    for _a, gain, f, sr, rr, disp, resid, gated in rows:
        print(f"{f:<24}{sr:>9}{rr:>10}{disp:>+11}{resid:>+10.1f}"
              f"{gated:>7.2f}{gain:>+15.3f}")

    print()
    print("  'Spearman gain' is what fixing that faction ALONE would add to the")
    print("  rank correlation. A faction with a large residual and a small gain")
    print("  is a distance problem; one with a large gain is an ordering problem")
    print("  and is worth more under the new headline.")
    print()
    top_gain = sorted(rows, key=lambda r: -r[1])[:5]
    top_resid = sorted(rows, key=lambda r: -abs(r[6]))[:5]
    print("  top five by ordering gain:  "
          + ", ".join(f"{r[2]} ({r[1]:+.3f})" for r in top_gain))
    print("  top five by residual size:  "
          + ", ".join(f"{r[2]} ({r[6]:+.1f})" for r in top_resid))
    overlap = {r[2] for r in top_gain} & {r[2] for r in top_resid}
    print(f"  overlap: {', '.join(sorted(overlap)) if overlap else 'NONE'}")


if __name__ == "__main__":
    main()
