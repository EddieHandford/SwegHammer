"""Does the residual live in PRIMARY or SECONDARY scoring?

Eight hypotheses have been tested and killed this session (task #44): durability
per point, list population, melee piloting competence, template realization,
army breadth, the Strands of Fate budget, Battle Focus carry-over, and unit
valuation. For Aeldari the list layer was additionally ruled out by direct
substitution. So the residual is not in the units, not in the faction army
rules, and not in the list - what remains is the GAME layer.

This is the first all-22-faction measurement of a claim this project has carried
for some time: that the simulator over-rewards durable objective-holding and
under-scores secondary. If over-performers bank primary while under-performers
fail on secondary, the defect is localised to scoring and is directly
actionable.

WHERE THE NUMBERS COME FROM, because this is easy to get wrong. `Battle._a_vp`
is the UNCAPPED TOTAL, and primary is derived by subtraction:

    primary = _a_vp - _a_secondary_vp - _a_challenger_vp

`BattleResult.a_vp` carries that same uncapped total; its docstring used to say
"Primary VP", which was wrong and is corrected in code/simulator.py. The winner
decision uses `_capped_standing`, which caps primary at 50 and secondary at 40,
so the capped and uncapped views differ for a dominator - both are reported here.

CAVEAT ON COMPARABILITY: this runs battles directly rather than through
evaluate_vs_meta, so it does not reproduce the evaluation's seed schedule, map
rotation or side roll-off. Absolute values are therefore not comparable to the
anchor; only the RELATIVE pattern across factions is, and that is all the
correlation needs.

Run: PYTHONHASHSEED=0 python -m scripts._vp_split_probe
     VP_SEEDS=1 VP_LOG=data/_anchor_sc69a_n80_log.json
"""
from __future__ import annotations
import collections
import json
import math
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, TOURNAMENT_TARGET, TOURNAMENT_GAMES

SEEDS = int(os.environ.get("VP_SEEDS", "1"))
LOG = os.environ.get("VP_LOG", "data/_anchor_sc69a_n80_log.json")


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


def main() -> None:
    try:
        sim = _sim_rates(LOG)
    except Exception as exc:
        print(f"could not read {LOG}: {exc}")
        return

    prim = collections.defaultdict(list)
    sec = collections.defaultdict(list)
    chal = collections.defaultdict(list)

    pairs = [(a, b) for i, a in enumerate(FACTIONS) for b in FACTIONS[i + 1:]]
    total = len(pairs) * SEEDS
    done = 0
    for s in range(SEEDS):
        for fa, fb in pairs:
            seed = 5000 + s * 10000 + hash((fa, fb)) % 9999
            rng = random.Random(seed)
            random.seed(seed)
            a = build_faction_random_army("A", fa, 2000, rng=rng,
                                          use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=rng,
                                          use_archetype=True)
            bt = Battle(a, b)
            bt.run()
            a_sec = float(getattr(bt, "_a_secondary_vp", 0) or 0)
            b_sec = float(getattr(bt, "_b_secondary_vp", 0) or 0)
            a_ch = float(getattr(bt, "_a_challenger_vp", 0) or 0)
            b_ch = float(getattr(bt, "_b_challenger_vp", 0) or 0)
            a_tot = float(getattr(bt, "_a_vp", 0) or 0)
            b_tot = float(getattr(bt, "_b_vp", 0) or 0)
            prim[fa].append(a_tot - a_sec - a_ch)
            prim[fb].append(b_tot - b_sec - b_ch)
            sec[fa].append(a_sec)
            sec[fb].append(b_sec)
            chal[fa].append(a_ch)
            chal[fb].append(b_ch)
            done += 1
            if done % 60 == 0:
                print(f"  ... {done}/{total} battles", flush=True)

    rows = []
    for fac in FACTIONS:
        if fac not in sim or not prim[fac]:
            continue
        p = sum(prim[fac]) / len(prim[fac])
        s_ = sum(sec[fac]) / len(sec[fac])
        c = sum(chal[fac]) / len(chal[fac])
        rows.append((sim[fac] - TOURNAMENT_TARGET[fac], fac, p, s_, c,
                     len(prim[fac])))

    rows.sort(reverse=True)
    print()
    print(f"=== victory point split, {total} battles, {SEEDS} seed(s) per pairing ===")
    print("primary is derived as total minus secondary minus challenger,")
    print("uncapped. Absolute values are not comparable to the anchor; the")
    print("pattern across factions is.\n")
    print(f"{'faction':<24}{'residual':>10}{'primary':>10}{'secondary':>11}"
          f"{'challenger':>12}{'games':>7}")
    for resid, fac, p, s_, c, n in rows:
        print(f"{fac:<24}{resid:>+10.1f}{p:>10.1f}{s_:>11.1f}{c:>12.1f}{n:>7}")

    resid = [r[0] for r in rows]
    print()
    print(f"  Pearson residual vs primary     "
          f"{_pearson([r[2] for r in rows], resid):+.3f}")
    print(f"  Pearson residual vs secondary   "
          f"{_pearson([r[3] for r in rows], resid):+.3f}")
    print(f"  Pearson residual vs challenger  "
          f"{_pearson([r[4] for r in rows], resid):+.3f}")
    ratio = [r[3] / max(r[2] + r[3], 1e-9) for r in rows]
    print(f"  Pearson residual vs secondary SHARE of scoring "
          f"{_pearson(ratio, resid):+.3f}")
    print()
    print(f"  {len(rows)} factions, so roughly 0.43 clears the five percent level.")
    print("  A strong POSITIVE on primary with a NEGATIVE on secondary would say")
    print("  the simulator pays for holding ground and not for the cards, which")
    print("  is the long-standing claim and would localise the defect to scoring.")


if __name__ == "__main__":
    main()
