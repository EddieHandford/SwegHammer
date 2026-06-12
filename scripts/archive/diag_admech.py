"""AdMech under-shooter deep diagnostic (UNDERSHOOTER_PLAN Thread B).

AdMech is the biggest under-shooter (gated ~8 at N=80) and structural — its
abilities washed and Go To Ground did not close it. Watchdog rail: instrument
WHERE it loses BEFORE proposing any fix, don't pre-judge. This read-only probe
runs AdMech across its matchups and segments the loss:
  - primary VP   (objectives held over the game — positioning / holding)
  - secondary VP (actions / deliberate dedication)
  - attrition    (models/units it removes vs loses — out-dealt damage)
so we can see whether AdMech loses on the objective game (a positioning /
holding fix), the secondary game, or raw attrition (an output / durability fix).

Reads battle._a_vp / _a_secondary_vp (primary = total - secondary) and the
surviving-unit counts post-run. Runs single-process (no eval-matrix workers).
Run with PYTHONHASHSEED=0.
"""
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

ADMECH = "Adeptus Mechanicus"
# A spread of opponents: over-shooters, gunlines, durable midfield, hordes.
OPPONENTS = ["Imperial Knights", "World Eaters", "Necrons", "T'au Empire",
             "Tyranids", "Adeptus Astartes", "Astra Militarum", "Aeldari"]
SEEDS = [1, 2, 3, 4, 5]


def _vp(battle, side):
    total = battle._a_vp if side == "A" else battle._b_vp
    sec = battle._a_secondary_vp if side == "A" else battle._b_secondary_vp
    return (total - sec), sec   # (primary, secondary)


def run_pair(admech_side, opp_fac, seed, agg):
    # admech_side: "A" => AdMech is A vs opp B; "B" => opp is A, AdMech is B.
    a_fac = ADMECH if admech_side == "A" else opp_fac
    b_fac = opp_fac if admech_side == "A" else ADMECH
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    a_start, b_start = len(a.units), len(b.units)
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    res = battle.run()

    am = admech_side
    opp = "B" if am == "A" else "A"
    am_prim, am_sec = _vp(battle, am)
    opp_prim, opp_sec = _vp(battle, opp)
    am_alive = len([u for u in (a.units if am == "A" else b.units) if u.is_alive])
    opp_alive = len([u for u in (b.units if am == "A" else a.units) if u.is_alive])
    am_start = a_start if am == "A" else b_start
    opp_start = b_start if am == "A" else a_start
    am_name = a.name if am == "A" else b.name
    won = 1 if res.winner == am_name else 0

    d = agg[opp_fac]
    d["n"] += 1
    d["am_prim"] += am_prim; d["opp_prim"] += opp_prim
    d["am_sec"] += am_sec;   d["opp_sec"] += opp_sec
    d["am_surv"] += am_alive / max(1, am_start)
    d["opp_surv"] += opp_alive / max(1, opp_start)
    d["wins"] += won


if __name__ == "__main__":
    agg = defaultdict(lambda: defaultdict(float))
    for opp in OPPONENTS:
        for s in SEEDS:
            run_pair("A", opp, s, agg)
            run_pair("B", opp, s + 100, agg)

    print(f"{'vs Opponent':<18} {'win%':>5} {'AMprim':>7} {'OPPprim':>7} {'dPrim':>6} "
          f"{'AMsec':>6} {'OPPsec':>6} {'AMsurv':>7} {'OPPsurv':>7}")
    print("-" * 78)
    tot = defaultdict(float); N = 0
    for opp in OPPONENTS:
        d = agg[opp]; n = d["n"] or 1
        amp, opp_p = d["am_prim"]/n, d["opp_prim"]/n
        ams, opp_s = d["am_sec"]/n, d["opp_sec"]/n
        print(f"{opp:<18} {100*d['wins']/n:>4.0f}% {amp:>7.1f} {opp_p:>7.1f} {amp-opp_p:>6.1f} "
              f"{ams:>6.1f} {opp_s:>6.1f} {100*d['am_surv']/n:>6.0f}% {100*d['opp_surv']/n:>6.0f}%")
        for k in ("am_prim","opp_prim","am_sec","opp_sec","am_surv","opp_surv","wins","n"):
            tot[k]+=d[k]
        N += 1
    n = tot["n"] or 1
    print("-" * 78)
    print(f"{'ALL':<18} {100*tot['wins']/n:>4.0f}% {tot['am_prim']/n:>7.1f} {tot['opp_prim']/n:>7.1f} "
          f"{(tot['am_prim']-tot['opp_prim'])/n:>6.1f} {tot['am_sec']/n:>6.1f} {tot['opp_sec']/n:>6.1f} "
          f"{100*tot['am_surv']/n:>6.0f}% {100*tot['opp_surv']/n:>6.0f}%")
    print()
    print("dPrim = AdMech primary VP minus opponent primary VP (negative => out-scored on")
    print("objectives = positioning/holding loss). Compare to the secondary gap and the")
    print("survival gap to locate where AdMech actually loses.")
