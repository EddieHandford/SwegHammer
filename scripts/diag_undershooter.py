"""Durable-shooty-vehicle under-shooter segmentation (#1 lever, instrument-first).

Generalizes scripts/diag_admech.py to ALL THREE durable-vehicle under-shooters
(Astra Militarum / Adeptus Mechanicus / Chaos Space Marines). The cover hypothesis
was REFUTED (scripts/diag_vehicle_cover.py: durable vehicles are in cover 44-69%
of shots, not ~never), so the under-valuation is NOT a fragility/cover mechanic.
This probe segments each under-shooter's loss into:
  - primary VP   (objectives held — the OC-body-bias / positional axis)
  - secondary VP (actions / deliberate dedication)
  - attrition    (survival% self vs opponent — out-dealt damage / under-output)
to localize between the OC-body-bias (the positional under-side mirror of the
over-side Knight over-hold) and a raw combat under-output. Read-only, single
process. Run with PYTHONHASHSEED=0.
"""
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

UNDER = ["Astra Militarum", "Adeptus Mechanicus", "Chaos Space Marines"]
OPPONENTS = ["Imperial Knights", "World Eaters", "Necrons", "T'au Empire",
             "Tyranids", "Adeptus Astartes", "Aeldari"]
SEEDS = [1, 2, 3, 4, 5]


def _vp(battle, side):
    total = battle._a_vp if side == "A" else battle._b_vp
    sec = battle._a_secondary_vp if side == "A" else battle._b_secondary_vp
    return (total - sec), sec


def run_pair(me_fac, me_side, opp_fac, seed, agg):
    a_fac = me_fac if me_side == "A" else opp_fac
    b_fac = opp_fac if me_side == "A" else me_fac
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    a_start, b_start = len(a.units), len(b.units)
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    res = battle.run()

    me, opp = me_side, ("B" if me_side == "A" else "A")
    me_prim, me_sec = _vp(battle, me)
    opp_prim, opp_sec = _vp(battle, opp)
    me_units = a.units if me == "A" else b.units
    opp_units = b.units if me == "A" else a.units
    me_alive = len([u for u in me_units if u.is_alive])
    opp_alive = len([u for u in opp_units if u.is_alive])
    me_start = a_start if me == "A" else b_start
    opp_start = b_start if me == "A" else a_start
    me_name = a.name if me == "A" else b.name

    d = agg[me_fac]
    d["n"] += 1
    d["me_prim"] += me_prim; d["opp_prim"] += opp_prim
    d["me_sec"] += me_sec;   d["opp_sec"] += opp_sec
    d["me_surv"] += me_alive / max(1, me_start)
    d["opp_surv"] += opp_alive / max(1, opp_start)
    d["wins"] += 1 if res.winner == me_name else 0


if __name__ == "__main__":
    agg = defaultdict(lambda: defaultdict(float))
    for me in UNDER:
        for opp in OPPONENTS:
            if opp == me:
                continue
            for s in SEEDS:
                run_pair(me, "A", opp, s, agg)
                run_pair(me, "B", opp, s + 100, agg)

    print(f"{'Under-shooter':<20} {'win%':>5} {'MEprim':>7} {'OPPprim':>7} {'dPrim':>6} "
          f"{'dSec':>6} {'MEsurv':>7} {'OPPsurv':>7} {'dSurv':>6}")
    print("-" * 80)
    for me in UNDER:
        d = agg[me]; n = d["n"] or 1
        mep, oppp = d["me_prim"]/n, d["opp_prim"]/n
        mes, opps = d["me_sec"]/n, d["opp_sec"]/n
        msv, osv = 100*d["me_surv"]/n, 100*d["opp_surv"]/n
        print(f"{me:<20} {100*d['wins']/n:>4.0f}% {mep:>7.1f} {oppp:>7.1f} {mep-oppp:>6.1f} "
              f"{mes-opps:>6.1f} {msv:>6.0f}% {osv:>6.0f}% {msv-osv:>5.0f}%")
    print()
    print("dPrim = under-shooter primary VP minus opponent primary VP (negative => out-scored")
    print("on OBJECTIVES = the OC-body-bias / positional axis). dSurv = survival-rate gap")
    print("(negative => out-attrited = combat under-output/over-fragility). Whichever gap")
    print("dominates across all three localizes the #1 lever.")
