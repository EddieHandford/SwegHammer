"""Does the simulator reward TOOLBOX armies that reality punishes?

The Adeptus Mechanicus audit (task #38 target three) found a template that is a
codex inventory rather than a list: 17 entries covering both Skitarii types,
both Sicarians, both Pteraxii, both Serberys, both Kataphrons, three vehicles
and four characters, with 14 of the 17 fielded in 100 percent of armies. The
simulator ranks the faction 9th; reality ranks it 21st.

That suggests a mechanism worth testing rather than asserting. A broad army
always has an answer to whatever it faces. Real Warhammer punishes that: an
unfocused list lacks the concentrated force to break a focused one, and its
surplus support characters are points not spent on threat. A simulator whose
opponents never tailor their list and never adapt between games may instead
REWARD breadth.

Two candidate measures of breadth, taken from the army actually fielded:

  datasheets   distinct datasheets in the army
  characters   MODELS carrying the CHARACTER keyword - not units. The
               catalogue is one Unit per model, and some character datasheets
               have a minimum size above one (the Brokhyr Iron-master seats
               five), so this OVERSTATES the number of character units for any
               faction fielding those. Leagues of Votann reads 15.8 on 69
               models for exactly that reason and should not be quoted as a
               character count. The measure is retained only as a relative
               breadth proxy; it is not a roster statistic.

RESULT (2026-07-27, sc69a): dead. Distinct datasheets correlate -0.294 with
residual (Spearman -0.327) and characters +0.093 - and with 22 factions a
correlation needs roughly 0.43 to clear the five percent level, so neither is
distinguishable from noise. If anything the sign is BACKWARDS from the
hypothesis: broad armies mildly under-perform. Adeptus Mechanicus is against
even that weak trend. The codex-inventory template is a real defect in its own
right, but it is not why the faction is mis-ranked.

If breadth correlates with OVER-performance, the simulator is paying for
toolbox armies and a whole class of template (the codex-inventory kind) is
mis-specified in the same direction. If it does not, the Adeptus Mechanicus
observation is real but does not generalise, and this is a fifth dead axis.

Run: PYTHONHASHSEED=0 python -m scripts._breadth_vs_residual
     BR_LOG=data/_anchor_sc69a_n80_log.json BR_SEEDS=12
"""
from __future__ import annotations
import collections
import json
import math
import os
import random

from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import (
    FACTIONS, TOURNAMENT_TARGET, TOURNAMENT_GAMES, _spearman,
)

LOG = os.environ.get("BR_LOG", "data/_anchor_sc69a_n80_log.json")
N_SEEDS = int(os.environ.get("BR_SEEDS", "12"))


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


def _is_character(p) -> bool:
    """The catalogue stores datasheet keywords on `unit_keywords`.

    A first version of this probe read `keywords`, which does not exist on
    UnitProfile, so every faction scored zero characters and the correlation
    came back as not-a-number. Kept explicit here because a silently-empty
    keyword read is indistinguishable from a faction genuinely fielding no
    characters, and the code/leaders.py convention (`u.profile.unit_keywords`)
    is the one the simulator itself uses.
    """
    return "CHARACTER" in set(getattr(p, "unit_keywords", None) or ())


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
        sheets = chars = models = 0
        for seed in range(N_SEEDS):
            army = build_faction_random_army("A", fac, 2000,
                                             rng=random.Random(seed),
                                             use_archetype=True)
            names = set()
            for u in army.units:
                names.add(u.profile.name)
                models += 1
                if _is_character(u.profile):
                    chars += 1
            sheets += len(names)
        rows.append({
            "fac": fac,
            "sheets": sheets / N_SEEDS,
            "chars": chars / N_SEEDS,
            "models": models / N_SEEDS,
            "resid": sim[fac] - TOURNAMENT_TARGET[fac],
            "disp": sim_rank[fac] - real_rank[fac],
        })

    rows.sort(key=lambda r: -r["resid"])
    print(f"=== army breadth against residual ({LOG}, {N_SEEDS} seeds) ===\n")
    print(f"{'faction':<24}{'datasheets':>11}{'characters':>12}{'models':>8}"
          f"{'residual':>10}{'displaced':>11}")
    for r in rows:
        print(f"{r['fac']:<24}{r['sheets']:>11.1f}{r['chars']:>12.1f}"
              f"{r['models']:>8.0f}{r['resid']:>+10.1f}{r['disp']:>+11}")

    resid = [r["resid"] for r in rows]
    absd = [abs(r["disp"]) for r in rows]
    print()
    print(f"  {'axis':<22}{'vs residual':>14}{'vs |displacement|':>20}")
    for key, label in (("sheets", "distinct datasheets"),
                       ("chars", "characters"),
                       ("models", "models")):
        print(f"  {label:<22}{_pearson([r[key] for r in rows], resid):>+14.3f}"
              f"{_pearson([r[key] for r in rows], absd):>+20.3f}")
    print(f"  {'datasheets (rank)':<22}"
          f"{_spearman([r['sheets'] for r in rows], resid):>+14.3f}")
    print()
    print("  A positive residual correlation means broad armies over-perform,")
    print("  which would make every codex-inventory template wrong in the same")
    print("  direction. Flat means the Adeptus Mechanicus case does not")
    print("  generalise and breadth is a fifth dead axis.")


if __name__ == "__main__":
    main()
