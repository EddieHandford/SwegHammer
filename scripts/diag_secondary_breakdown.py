"""Secondary-VP gap decomposition by card type (#1 lever, instrument-first).

Wave 177 found the durable-shooty-vehicle under-shooters (Astra Militarum /
AdMech / CSM) lose the SECONDARY game by -22 to -25 VP — the biggest, most
consistent component. The watchdog asked two questions before any fix:
  (1) decompose the gap by card TYPE (kill cards vs positional cards), and
  (2) check the gap is DISPROPORTIONATE — bigger than a losing army naturally
      concedes — i.e. a real low-model-count BIAS, not a losing-army artifact.

Note the eval runs the DEFAULT secondary path (SWEG_TAC_DECK unset), so the M2
Fixed-vs-Tactical *track* mechanism is NOT active. The scored secondaries are:
  KILL cards   — bring_it_down / no_prisoners / cull_the_horde / assassination
  POSITIONAL   — engage_on_all_fronts / behind_enemy_lines
(action/board cards are internally gated off). This probe wraps the two scoring
functions (`code.secondaries.score_round_delta` / `score_position_delta`) to
attribute every VP to the SCORING faction and split kill vs positional, for the
under-shooter vs its opponents. If the gap is mostly KILL, it's attrition-driven
(the under-shooter dying + the faithful Bring-It-Down concession on its
vehicles); if mostly POSITIONAL, it's the low-count spread/projection bias.

Read-only, single process. Run with PYTHONHASHSEED=0.
"""
import random
from collections import defaultdict

import code.secondaries as S
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

UNDER = ["Astra Militarum", "Adeptus Mechanicus", "Chaos Space Marines"]
OPPONENTS = ["Imperial Knights", "World Eaters", "Necrons", "T'au Empire",
             "Tyranids", "Adeptus Astartes", "Aeldari"]
SEEDS = [1, 2, 3, 4, 5]

# Per-battle routing set before each run; the patched scorers read this.
_DIAG = {"me_units": None, "opp_units": None, "bucket": None}
_real_round = S.score_round_delta
_real_pos = S.score_position_delta

from code.simulator import Battle as _Battle
_real_cleanse = _Battle._score_cleanse
_real_sabotage = _Battle._score_sabotage
_real_board = _Battle._score_board_secondaries


def _credit_obj(army, vp):
    """Attribute an objective-control/action-card VP (cleanse/sabotage/board) to
    the scoring side's bucket. `army` is the scoring army."""
    b = _DIAG["bucket"]
    if b is None or not vp:
        return
    if army.units is _DIAG["me_units"]:
        b["me_obj"] += vp
    elif army.units is _DIAG["opp_units"]:
        b["opp_obj"] += vp


def _patched_cleanse(self, army, opponent, own_is_army_a, *a, **k):
    vp = _real_cleanse(self, army, opponent, own_is_army_a, *a, **k)
    _credit_obj(army, vp)
    return vp


def _patched_sabotage(self, army, own_is_army_a, *a, **k):
    vp = _real_sabotage(self, army, own_is_army_a, *a, **k)
    _credit_obj(army, vp)
    return vp


def _patched_board(self, army, opponent, own_is_army_a, *a, **k):
    vp = _real_board(self, army, opponent, own_is_army_a, *a, **k)
    _credit_obj(army, vp)
    return vp


def _patched_round(snapshot, enemy_units_now, *a, **k):
    bid, np_, cth, assn = _real_round(snapshot, enemy_units_now, *a, **k)
    b = _DIAG["bucket"]
    if b is not None:
        # enemy_units_now is the side being KILLED; scorer is the other side.
        if enemy_units_now is _DIAG["opp_units"]:      # me killing opp -> me scores
            b["me_kill"] += bid + np_ + cth + assn
            b["me_bid"] += bid; b["me_np"] += np_; b["me_cth"] += cth; b["me_assn"] += assn
        elif enemy_units_now is _DIAG["me_units"]:     # opp killing me -> opp scores
            b["opp_kill"] += bid + np_ + cth + assn
            b["opp_bid"] += bid; b["opp_np"] += np_; b["opp_cth"] += cth; b["opp_assn"] += assn
    return bid, np_, cth, assn


def _patched_pos(own_units, *a, **k):
    eng, bel = _real_pos(own_units, *a, **k)
    b = _DIAG["bucket"]
    if b is not None:
        if own_units is _DIAG["me_units"]:
            b["me_pos"] += eng + bel; b["me_eng"] += eng; b["me_bel"] += bel
        elif own_units is _DIAG["opp_units"]:
            b["opp_pos"] += eng + bel; b["opp_eng"] += eng; b["opp_bel"] += bel
    return eng, bel


def run_pair(me_fac, me_side, opp_fac, seed, agg):
    a_fac = me_fac if me_side == "A" else opp_fac
    b_fac = opp_fac if me_side == "A" else me_fac
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    me_units = a.units if me_side == "A" else b.units
    opp_units = b.units if me_side == "A" else a.units
    _DIAG["me_units"], _DIAG["opp_units"], _DIAG["bucket"] = me_units, opp_units, agg[me_fac]
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    battle.run()
    agg[me_fac]["n"] += 1
    _DIAG["bucket"] = None


if __name__ == "__main__":
    S.score_round_delta = _patched_round
    S.score_position_delta = _patched_pos
    _Battle._score_cleanse = _patched_cleanse
    _Battle._score_sabotage = _patched_sabotage
    _Battle._score_board_secondaries = _patched_board
    agg = defaultdict(lambda: defaultdict(float))
    for me in UNDER:
        for opp in OPPONENTS:
            if opp == me:
                continue
            for s in SEEDS:
                run_pair(me, "A", opp, s, agg)
                run_pair(me, "B", opp, s + 100, agg)

    print(f"{'Under-shooter':<20} {'dKill':>6} {'dPos':>6} {'dObj':>6} {'dTOT':>6}  "
          f"({'meObj':>6}/{'oppObj':>6})")
    print("-" * 70)
    for me in UNDER:
        d = agg[me]; n = d["n"] or 1
        dk = (d["me_kill"]-d["opp_kill"])/n
        dp = (d["me_pos"]-d["opp_pos"])/n
        mo, oo = d["me_obj"]/n, d["opp_obj"]/n
        do = mo-oo
        print(f"{me:<20} {dk:>6.1f} {dp:>6.1f} {do:>6.1f} {dk+dp+do:>6.1f}  "
              f"({mo:>6.1f}/{oo:>6.1f})")
    print()
    print("dKill = kill-card gap (Bring It Down / No Prisoners / Cull / Assassination):")
    print("        attrition + the faithful Bring-It-Down concession on the vehicles.")
    print("dPos  = Engage+BEL positional gap (small).")
    print("dObj  = objective-control/action card gap (Cleanse + Sabotage + 5 board cards,")
    print("        all DEFAULT-ON, scored EVERY round not the real 2-card-per-turn cadence).")
    print("        This is the low-OC count-bias candidate: body armies score these, low-")
    print("        model durable armies concede them. dTOT should ~ match the -22..-25 dSec.")
    # Per-kill-card detail to separate Bring It Down (vehicle concession) from the rest.
    print()
    print(f"{'Under-shooter':<20} {'dBID':>6} {'dNP':>6} {'dCull':>6} {'dAssn':>6} {'dEng':>6} {'dBEL':>6}")
    print("-" * 64)
    for me in UNDER:
        d = agg[me]; n = d["n"] or 1
        print(f"{me:<20} {(d['me_bid']-d['opp_bid'])/n:>6.1f} {(d['me_np']-d['opp_np'])/n:>6.1f} "
              f"{(d['me_cth']-d['opp_cth'])/n:>6.1f} {(d['me_assn']-d['opp_assn'])/n:>6.1f} "
              f"{(d['me_eng']-d['opp_eng'])/n:>6.1f} {(d['me_bel']-d['opp_bel'])/n:>6.1f}")
    print("dBID = Bring It Down gap (vehicle armies CONCEDE this — faithful). dNP/dCull =")
    print("No Prisoners / Cull (horde/body concession). dEng/dBEL = positional count-bias.")
