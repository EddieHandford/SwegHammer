"""Does the combat model over-value the units one faction fields?

Task #43 redirected here. Aeldari over-perform by eleven to thirteen points
across two structurally different real lists, and their army rules are measurably
INERT in this simulator - Strands of Fate is pool-bounded and correct, Battle
Focus banks two dozen unspent tokens, five of six Agile Manoeuvres are not
modelled. So the over-valuation is not in the faction's special rules. The
remaining candidates are the datasheet profiles as the combat model evaluates
them, or something in movement and target selection.

This tests the first. The Stage 2 solvers already answer "what would this unit
cost if it were priced to win half its equal-points fights under THIS combat
model" - that is exactly a measurement of how the simulator values a unit. If
the simulator over-values a faction, its units' sim-fair prices should exceed
their real points, and the per-faction mean of that ratio should track the
faction's win-rate residual.

  ratio > 1   the simulator thinks the unit is worth MORE than it costs, so an
              army of them gets more than it paid for
  ratio < 1   the simulator under-values it

STALENESS WARNING, and it is the reason this is a first look rather than a
verdict. The equilibrium outputs are dated May and June 2026 while the standing
anchor sc69a is from 26 July, so roughly two months of simulator changes sit
between them. CLAUDE.md also records Stage 2 outputs as provisional because they
were fitted against a non-converged Stage 1. A strong signal here justifies a
fresh solver run; a weak one proves nothing either way.

Run: PYTHONHASHSEED=0 python -m scripts._valuation_bias_probe
     VB_FILE=data/equilibrium_points.json VB_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import collections
import json
import math
import os

from code.units import UNIT_CATALOG
from scripts.evaluate_vs_meta import FACTIONS, TOURNAMENT_TARGET, TOURNAMENT_GAMES

FILE = os.environ.get("VB_FILE", "data/equilibrium_points.json")
LOG = os.environ.get("VB_LOG", "data/_anchor_sc69a_n80_log.json")


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


def _sim_rates(path):
    d = json.load(open(path, encoding="utf-8"))
    games = d["games"] if isinstance(d, dict) else d
    wins = collections.defaultdict(collections.Counter)
    played = collections.Counter()
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


def _load_prices(path):
    """Return [(faction, sim_fair_per_model, real_per_model), ...].

    The equilibrium files carry `faction` and `gw_points_per_model` on each
    entry, so the ratio is computed from the file itself rather than joined
    through UNIT_CATALOG - a join would silently drop every unit whose key has
    drifted, and a silent partial match is exactly the failure this project
    keeps hitting.
    """
    raw = json.load(open(path, encoding="utf-8"))
    if isinstance(raw, dict) and "units" in raw:
        raw = raw["units"]
    out = []
    for k, v in raw.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        fair = None
        for field in ("equilibrium_points_per_model", "balanced_points",
                      "equilibrium_points", "points", "fair_points"):
            if isinstance(v.get(field), (int, float)):
                fair = float(v[field])
                break
        real = v.get("gw_points_per_model")
        fac = v.get("faction")
        if fair is None or not isinstance(real, (int, float)):
            # Fall back to the catalogue only when the file lacks the price.
            p = UNIT_CATALOG.get(k)
            if p is None or fair is None:
                continue
            real = float(getattr(p, "points_cost", 0) or 0)
            fac = fac or getattr(p, "faction", None)
        if not fac or fair <= 0 or real <= 0:
            continue
        out.append((fac, fair, float(real)))
    return out


def main() -> None:
    try:
        prices = _load_prices(FILE)
    except Exception as exc:
        print(f"could not read {FILE}: {exc}")
        return
    if not prices:
        print(f"{FILE}: no per-unit prices recognised; inspect its shape")
        return
    try:
        sim = _sim_rates(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return

    per_fac = collections.defaultdict(list)
    matched = 0
    for fac, fair, real in prices:
        if fac not in TOURNAMENT_TARGET:
            continue
        per_fac[fac].append(fair / real)
        matched += 1

    rows = []
    for fac, ratios in per_fac.items():
        if fac not in sim or len(ratios) < 4:
            continue
        ratios_sorted = sorted(ratios)
        med = ratios_sorted[len(ratios_sorted) // 2]
        rows.append((sim[fac] - TOURNAMENT_TARGET[fac], fac,
                     sum(ratios) / len(ratios), med, len(ratios)))

    if len(rows) < 4:
        print(f"only {len(rows)} factions matched — too few to correlate")
        return

    rows.sort(reverse=True)
    print(f"=== simulator valuation bias ({FILE}) ===")
    print(f"    {matched} units matched to the catalogue, "
          f"{len(rows)} factions with 4+ units")
    print("    ratio = sim-fair points / real points. Above 1 = over-valued.\n")
    print(f"{'faction':<24}{'residual':>10}{'mean ratio':>12}{'median':>9}{'units':>7}")
    for resid, fac, mean_r, med_r, n in rows:
        print(f"{fac:<24}{resid:>+10.1f}{mean_r:>12.2f}{med_r:>9.2f}{n:>7}")

    resid = [r[0] for r in rows]
    print()
    print(f"  Pearson  residual vs mean ratio    "
          f"{_pearson([r[2] for r in rows], resid):+.3f}")
    print(f"  Pearson  residual vs median ratio  "
          f"{_pearson([r[3] for r in rows], resid):+.3f}")
    print(f"  Spearman residual vs median ratio  "
          f"{_spearman([r[3] for r in rows], resid):+.3f}")
    print()
    print(f"  With {len(rows)} factions a correlation needs roughly 0.43 to clear")
    print("  the five percent level. And these prices are STALE - fitted against")
    print("  a simulator two months older than the anchor - so a weak result")
    print("  here is uninformative rather than exculpatory. Only a strong one")
    print("  means anything, and it would justify a fresh solver run.")


if __name__ == "__main__":
    main()
