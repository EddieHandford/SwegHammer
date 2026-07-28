"""Does template realization quality explain the ORDERING error?

Three faction audits have now found the same shape of defect by hand:

  Tyranids            the template cited a list and fielded a different army
                      (fixed, worth +9.49)
  Aeldari             the template cites two 2025 lists against a May 2026
                      target, and fields "universal" entries in half its armies
  Emperor's Children  the active template is a cost-infeasible union at 2,920
                      points against a 2,000 budget, so the builder fields
                      degraded random subsets

Three hand-found instances is a pattern worth testing rather than extrapolating.
This measures every faction's template realization and crosses it against rank
displacement under the new ordering headline.

Per faction:

  overrun       declared template cost over the SEED SLICE it is allowed to
                spend. The budget is NOT the right denominator: templates seed
                only SEED_FRACTION of the army (0.3, so 600 points of 2,000)
                and `_random_fill` spends the rest, so a template costing 1,460
                is over its slice by 860 even though it is well under budget.
                Measuring against 2,000 was an error in the first version of
                this probe and understated every faction. Above 1.0 means the
                seed walk must drop or shrink entries every build - the
                "realization lottery". Reported both as a distinct union (one
                minimum squad per entry) and by declared count.
  realization   mean share of armies in which a declared entry appears. 1.00
                means every declared entry is fielded every game.
  weak entries  declared entries appearing in under 70 percent of armies
  displacement  simulated rank minus real rank, from the standing anchor

If realization tracks displacement, the list layer is the dominant ordering
defect and the audit should continue faction by faction. If it does not, the
three hand-found cases are real but local, and ordering error has another
source - which is worth knowing before spending days on template sourcing.

Run: PYTHONHASHSEED=0 python -m scripts._realization_vs_ordering
     RV_LOG=data/_anchor_sc69a_n80_log.json RV_SEEDS=12
"""
from __future__ import annotations
import collections
import json
import math
import os
import random

from code.archetypes import (
    ARCHETYPES, _effective_template, _squad_cost, SEED_FRACTION,
)
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG
from scripts.evaluate_vs_meta import (
    FACTIONS, TOURNAMENT_TARGET, TOURNAMENT_GAMES, _spearman,
)

LOG = os.environ.get("RV_LOG", "data/_anchor_sc69a_n80_log.json")
N_SEEDS = int(os.environ.get("RV_SEEDS", "12"))
BUDGET = 2000.0


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


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


def _audit(fac):
    """(overrun_distinct, overrun_by_count, realization, weak, n, models)."""
    templates = ARCHETYPES.get(fac)
    if not templates:
        return None
    # Cost the WORST (largest) template — that is the one that cannot be met.
    worst_distinct = worst_by_count = 0.0
    declared_all = {}
    for entries in templates.values():
        eff = _effective_template(fac, entries)
        distinct = by_count = 0.0
        for key, count in eff.items():
            p = UNIT_CATALOG.get(key)
            if p is None:
                continue
            sc = _squad_cost(key)
            distinct += sc
            by_count += sc * count
            declared_all[key] = p.name
        worst_distinct = max(worst_distinct, distinct)
        worst_by_count = max(worst_by_count, by_count)

    name_to_key = {v: k for k, v in declared_all.items()}
    present = collections.Counter()
    models_total = 0
    for seed in range(N_SEEDS):
        army = build_faction_random_army("A", fac, 2000,
                                         rng=random.Random(seed),
                                         use_archetype=True)
        seen = set()
        for u in army.units:
            models_total += 1
            k = name_to_key.get(u.profile.name)
            if k:
                seen.add(k)
        for k in seen:
            present[k] += 1

    n_decl = len(declared_all)
    if not n_decl:
        return None
    rates = [present[k] / N_SEEDS for k in declared_all]
    slice_pts = max(1.0, SEED_FRACTION * BUDGET)
    return (worst_distinct / slice_pts, worst_by_count / slice_pts,
            sum(rates) / n_decl, sum(1 for r in rates if r < 0.70), n_decl,
            models_total / N_SEEDS)


def main() -> None:
    try:
        sim = _sim_rates(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return

    facs = [f for f in FACTIONS if f in sim and f in TOURNAMENT_TARGET]
    sim_rank = {f: i + 1 for i, f in enumerate(sorted(facs, key=lambda f: -sim[f]))}
    real_rank = {f: i + 1 for i, f in
                 enumerate(sorted(facs, key=lambda f: -TOURNAMENT_TARGET[f]))}

    rows = []
    for fac in facs:
        a = _audit(fac)
        if a is None:
            continue
        feas, feas_ct, real_z, weak, n_decl, models = a
        rows.append({
            "fac": fac, "feas": feas, "feas_ct": feas_ct,
            "realz": real_z, "weak": weak,
            "n": n_decl, "models": models,
            "disp": sim_rank[fac] - real_rank[fac],
            "resid": sim[fac] - TOURNAMENT_TARGET[fac],
        })

    rows.sort(key=lambda r: -abs(r["disp"]))
    print(f"=== template realization against ordering error ({LOG}) ===")
    print(f"overrun = declared cost / seed slice ({SEED_FRACTION:.2f} x 2000 = "
          f"{SEED_FRACTION * BUDGET:.0f} pts), NOT / budget")
    print("realization = mean share of armies containing each declared entry\n")
    print(f"{'faction':<24}{'entries':>8}{'overrun':>9}{'x count':>9}"
          f"{'realization':>12}{'weak':>6}{'models':>8}{'displaced':>11}"
          f"{'resid':>8}")
    for r in rows:
        print(f"{r['fac']:<24}{r['n']:>8}{r['feas']:>9.2f}{r['feas_ct']:>9.2f}"
              f"{r['realz']:>12.2f}{r['weak']:>6}{r['models']:>8.0f}"
              f"{r['disp']:>+11}{r['resid']:>+8.1f}")

    absd = [abs(r["disp"]) for r in rows]
    print()
    print(f"  {'axis':<26}{'Pearson vs |displacement|':>28}")
    for key, label in (("feas", "overrun (distinct)"), ("feas_ct", "overrun (by count)"),
                       ("realz", "realization"),
                       ("weak", "weak entry count"), ("models", "models fielded")):
        print(f"  {label:<26}{_pearson([r[key] for r in rows], absd):>+28.3f}")
    print(f"  {'realization (rank)':<26}"
          f"{_spearman([r['realz'] for r in rows], absd):>+28.3f}")

    infeas = [r for r in rows if r["feas"] > 1.0]
    feasible = [r for r in rows if r["feas"] <= 1.0]
    print()
    print(f"  templates whose DISTINCT union overruns the seed slice: "
          f"{len(infeas)} of {len(rows)}")
    if infeas and feasible:
        mi = sum(abs(r["disp"]) for r in infeas) / len(infeas)
        mf = sum(abs(r["disp"]) for r in feasible) / len(feasible)
        print(f"    overrunning ({len(infeas):>2})  mean displacement {mi:>5.1f}")
        print(f"    fitting     ({len(feasible):>2})  mean displacement {mf:>5.1f}")
        print(f"    gap {mi - mf:+.1f} places")
    elif not feasible:
        print("    EVERY template overruns its seed slice, so there is no")
        print("    contrast group and the lottery cannot explain differences")
        print("    BETWEEN factions — only a defect they all share.")
    print()
    print("  A flat correlation does NOT clear the list layer — it only says")
    print("  realization is not the axis. The Aeldari defect was a citation from")
    print("  the wrong YEAR, which realization cannot see at all.")


if __name__ == "__main__":
    main()
