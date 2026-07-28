"""How extreme are the simulator's individual matchups?

scripts/_skill_vs_null shows the simulated per-faction win rates are spread
about 1.75 times wider than the real ones (6.7 points against 3.8), and that
this over-dispersion, not bias, is what the headline mean absolute error is
mostly made of. Faction-level spread is built out of matchup-level spread, so
this looks one level down: the distribution of the 462 ordered pairings.

Real Warhammer per-matchup win rates cluster: a genuinely bad matchup in
tournament data sits near 35 to 40 percent, and near-unplayable pairings are
rare. If the simulator instead produces a mass of near-certain results, the
cause is structural rather than per-faction:

  * ONE archetype list per faction, where reality averages over hundreds of
    lists of widely varying quality
  * a deterministic policy on both sides, where reality has player skill
    variance that pulls every matchup toward the middle

Both make matchups more decisive than they really are, and neither is fixed by
tuning any individual faction. This prints the distribution so the claim can be
checked rather than asserted, and lists the most extreme pairings for spot
verification against the game log.

Run: PYTHONHASHSEED=0 python -m scripts._matchup_dispersion
     MD_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import json
import math
import os
from collections import Counter, defaultdict

from scripts.evaluate_vs_meta import FACTIONS

LOG = os.environ.get("MD_LOG", "data/_anchor_sc69a_n80_log.json")


def _load_games(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["games"] if isinstance(d, dict) else d


def main() -> None:
    try:
        games = _load_games(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return

    wins = defaultdict(Counter)
    played = Counter()
    for g in games:
        fa, fb, _i, win = g[0], g[1], g[2], g[3]
        played[(fa, fb)] += 1
        if win is not None:
            wins[(fa, fb)][win] += 1

    # Symmetrized matchup: average this faction's rate as army A with its rate
    # as army B in the mirrored cell, so positional bias cancels out.
    seen = set()
    rows = []
    for a in FACTIONS:
        for b in FACTIONS:
            if a == b or (b, a) in seen:
                continue
            n_ab, n_ba = played.get((a, b), 0), played.get((b, a), 0)
            if not n_ab or not n_ba:
                continue
            seen.add((a, b))
            ab = wins[(a, b)].get("A", 0) / n_ab * 100.0
            ba = 100.0 - wins[(b, a)].get("A", 0) / n_ba * 100.0
            rows.append((0.5 * (ab + ba), a, b, ab, ba))

    if not rows:
        print("no complete mirrored pairings in the log")
        return

    vals = [r[0] for r in rows]
    n = len(vals)
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
    print(f"=== matchup dispersion ({LOG}) ===")
    print(f"  {n} symmetrized pairings, mean {mean:.1f}, "
          f"standard deviation {sd:.1f} points\n")

    print("  distribution of symmetrized matchup win rates")
    edges = [0, 10, 20, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 101]
    for lo, hi in zip(edges, edges[1:]):
        c = sum(1 for v in vals if lo <= v < hi)
        bar = "#" * int(round(60.0 * c / n))
        print(f"    {lo:>3}-{hi - 1:<3} {c:>4} ({100.0 * c / n:>5.1f}%) {bar}")
    print()

    def frac(pred):
        return 100.0 * sum(1 for v in vals if pred(v)) / n

    print(f"  matchups decided 70/30 or harder     {frac(lambda v: v >= 70 or v <= 30):>5.1f}%")
    print(f"  matchups decided 80/20 or harder     {frac(lambda v: v >= 80 or v <= 20):>5.1f}%")
    print(f"  matchups decided 90/10 or harder     {frac(lambda v: v >= 90 or v <= 10):>5.1f}%")
    print(f"  matchups inside a real-looking 40-60 {frac(lambda v: 40 <= v <= 60):>5.1f}%")
    print()
    print("  In tournament data the great majority of pairings sit inside 40-60 and")
    print("  a 70/30 matchup is remarked upon. Whatever fraction sits beyond 80/20")
    print("  here is spread the simulator manufactures and reality does not have.")
    print()

    rows.sort()
    print("  ten most one-sided pairings (symmetrized, then each frame)")
    for v, a, b, ab, ba in rows[:5] + rows[-5:]:
        print(f"    {a:<22} vs {b:<22} {v:>5.1f}   "
              f"(as army A {ab:>5.1f}, as army B {ba:>5.1f})")


if __name__ == "__main__":
    main()
