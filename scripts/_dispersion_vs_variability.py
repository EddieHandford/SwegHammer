"""Is matchup dispersion explained by how much a faction's army varies?

Combines the two halves of the argument in one place so the correlation is
computed from source rather than eyeballed off two separate tables:

  matchup dispersion  standard deviation of a faction's 21 symmetrized
                      matchup win rates in the standing anchor
  army turnover       mean fraction of models that differ between two
                      independently seeded builds of that faction's army

The distinction that matters is WHICH KIND of variation is present. Every
faction already gets some variation from `_random_fill` topping up the budget
after the template is seeded - that is filler churn, and it runs 0.24 to 0.39
across the single-list factions. Chaos Daemons additionally samples among five
genuinely different lists and runs at 0.82.

So the correlation is reported twice: across all factions, and across the
single-list factions alone. If filler churn drove dispersion, the second
correlation would be strong too. If only the multi-list faction breaks away,
then it is strategic difference between real lists that compresses matchups,
not shuffling the filler - and those are very different engineering tasks.

Run: PYTHONHASHSEED=0 python -m scripts._dispersion_vs_variability
     DV_LOG=data/_anchor_sc69a_n80_log.json DV_SEEDS=12
"""
from __future__ import annotations
import collections
import json
import math
import os
import random

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import FACTIONS

LOG = os.environ.get("DV_LOG", "data/_anchor_sc69a_n80_log.json")
N_SEEDS = int(os.environ.get("DV_SEEDS", "12"))


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def _matchup_sd(games):
    wins = collections.defaultdict(collections.Counter)
    played = collections.Counter()
    for g in games:
        fa, fb, _i, win = g[0], g[1], g[2], g[3]
        played[(fa, fb)] += 1
        if win is not None:
            wins[(fa, fb)][win] += 1

    def sym(a, b):
        n_ab, n_ba = played.get((a, b), 0), played.get((b, a), 0)
        if not n_ab or not n_ba:
            return None
        return 0.5 * (wins[(a, b)].get("A", 0) / n_ab * 100.0
                      + 100.0 - wins[(b, a)].get("A", 0) / n_ba * 100.0)

    out = {}
    for fac in FACTIONS:
        vals = [v for b in FACTIONS if b != fac
                for v in (sym(fac, b),) if v is not None]
        if len(vals) >= 3:
            m = sum(vals) / len(vals)
            out[fac] = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))
    return out


def _turnover(fac: str, seeds) -> float:
    comps = []
    for s in seeds:
        army = build_faction_random_army("A", fac, 2000, rng=random.Random(s),
                                         use_archetype=True)
        c = collections.Counter()
        for u in army.units:
            c[u.profile.name or "?"] += 1
        comps.append(c)
    pairs = [(i, j) for i in range(len(comps)) for j in range(i + 1, len(comps))]
    tot = 0.0
    for i, j in pairs:
        a, b = comps[i], comps[j]
        denom = (sum(a.values()) + sum(b.values())) / 2.0
        if denom > 0:
            tot += (sum((a - b).values()) + sum((b - a).values())) / (2.0 * denom)
    return tot / max(len(pairs), 1)


def main() -> None:
    try:
        d = json.load(open(LOG, encoding="utf-8"))
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return
    sd = _matchup_sd(d["games"] if isinstance(d, dict) else d)

    seeds = list(range(N_SEEDS))
    rows = []
    for fac in FACTIONS:
        if fac not in sd:
            continue
        rows.append((fac, len(ARCHETYPES.get(fac, {})), _turnover(fac, seeds), sd[fac]))

    rows.sort(key=lambda r: -r[2])
    print(f"=== army turnover against matchup dispersion ({LOG}) ===")
    print(f"{'faction':<24}{'lists':>6}{'turnover':>10}{'matchup sd':>12}")
    for fac, ntmpl, turn, s in rows:
        mark = "   <-- samples among real lists" if ntmpl > 1 else ""
        print(f"{fac:<24}{ntmpl:>6}{turn:>10.3f}{s:>12.1f}{mark}")

    allr = _pearson([r[2] for r in rows], [r[3] for r in rows])
    single = [r for r in rows if r[1] == 1]
    singr = _pearson([r[2] for r in single], [r[3] for r in single])
    print()
    print(f"  correlation, all {len(rows)} factions          {allr:+.3f}")
    print(f"  correlation, {len(single)} single-list factions  {singr:+.3f}")
    print()
    if singr > -0.25 and allr < -0.25:
        print("  Filler churn does NOT predict dispersion; the multi-list faction alone")
        print("  breaks the pattern. Compression comes from sampling among genuinely")
        print("  DIFFERENT lists, not from varying which filler units top up the budget.")
        print("  Adding more filler variance would therefore buy nothing.")
    elif singr <= -0.25:
        print("  Dispersion falls with variability among single-list factions too, so")
        print("  the effect is not specific to having multiple templates.")
    else:
        print("  No clear relationship in either grouping; the single-list explanation")
        print("  for over-dispersion is not supported by this evidence.")


if __name__ == "__main__":
    main()
