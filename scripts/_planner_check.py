"""Reframed planner behavioural test. The world-mechanics experiment showed Death
Guard's hold is FAITHFUL, so the counterplay is NOT 'Death Guard holds fewer' but
'the out-durabilitied opponent OUT-SCORES Death Guard on secondary and tempo and
WINS'. This measures that directly: with a lever off vs on, the opponent's (army B)
win-rate vs Death Guard and its secondary victory points per game.

Run: PYTHONHASHSEED=0 python -m scripts._planner_check [FLAG]
"""
from __future__ import annotations
import os, sys, random
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

DG = "Death Guard"
OPPS = ["Astra Militarum", "Adepta Sororitas", "Aeldari", "Adeptus Astartes"]
N = int(os.environ.get("BCHECK_N", "10"))
_idx = {f: i for i, f in enumerate(FACTIONS)}


def measure(flag, on):
    if flag:
        os.environ[flag] = "1" if on else os.environ.pop(flag, "") and ""
        if not on:
            os.environ.pop(flag, None)
    b_wins = draws = games = 0
    b_sec = a_sec = a_vp = b_vp = 0.0
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[DG] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", DG, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            batt = Battle(a, b, map_=_pick_rotation_map(seed), primary_mission=_pick_primary_mission(ps))
            r = batt.run()
            games += 1
            if r.winner == "B":
                b_wins += 1
            elif r.winner not in ("A", "B"):
                draws += 1
            b_sec += batt._b_secondary_vp
            a_sec += batt._a_secondary_vp
            a_vp += r.a_vp
            b_vp += r.b_vp
    return dict(b_winrate=b_wins / games, draws=draws / games, b_sec=b_sec / games,
                a_sec=a_sec / games, a_vp=a_vp / games, b_vp=b_vp / games, games=games)


def report(tag, m):
    print(f"[{tag}] opponent(B) win-rate vs DG = {m['b_winrate']*100:.1f}%  (draws {m['draws']*100:.0f}%)")
    print(f"      opp(B) secondary VP/game = {m['b_sec']:.1f}  (real reference ~22.7)")
    print(f"      totals: DG(A) {m['a_vp']:.1f} VP  vs  opp(B) {m['b_vp']:.1f} VP   | DG secondary {m['a_sec']:.1f}")


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    flag = sys.argv[1] if len(sys.argv) > 1 else None
    off = measure(flag, False)
    report("OFF / baseline", off)
    if flag:
        on = measure(flag, True)
        print()
        report(f"ON ({flag}=1)", on)
        print(f"\nDELTA opp win-rate: {(on['b_winrate']-off['b_winrate'])*100:+.1f}pp  |  "
              f"opp secondary: {on['b_sec']-off['b_sec']:+.1f}  (want BOTH positive = counterplay works)")
