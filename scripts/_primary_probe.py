"""Scratch probe (read-only, no production edits): per-round objective-control
trajectory, DG vs field, for the primary-over-score investigation.
PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._primary_probe
"""
from __future__ import annotations
import os, sys, random
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts._primary_probe"] + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army
from code.events import EventLog, ObjectiveScored, RoundEnded, RoundStarted
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

MATCHUPS_DG = [("Death Guard", "Adeptus Astartes"), ("Death Guard", "Astra Militarum"),
               ("Death Guard", "Tyranids")]
MATCHUPS_FIELD = [("Imperial Knights", "Tyranids"), ("Aeldari", "Chaos Space Marines"),
                   ("T'au Empire", "World Eaters"), ("Adepta Sororitas", "Leagues of Votann")]

def run_one(a_fac, b_fac, seed):
    rng_a = random.Random(seed)
    rng_b = random.Random(seed + 10_000)
    a_army = build_faction_random_army("A", a_fac, 2000, rng=rng_a, use_archetype=True)
    b_army = build_faction_random_army("B", b_fac, 2000, rng=rng_b, use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    battle = Battle(a_army, b_army, subscribers=[log], map_=map_)
    result = battle.run()

    # per-round: for each ObjectiveScored, is a_oc>0 / b_oc>0 (contested) and who scored.
    round_num = 0
    per_round = {}  # round -> dict(a_controls, b_controls, contested, uncontested_a, uncontested_b, n_obj)
    for ev in log.events:
        n = type(ev).__name__
        if n == "RoundStarted":
            round_num = ev.round_num
            per_round.setdefault(round_num, {"a_ctrl": 0, "b_ctrl": 0, "contested_wins": 0,
                                              "uncontested_wins": 0, "neither": 0, "n_obj": 0})
        elif n == "ObjectiveScored":
            d = per_round.setdefault(round_num, {"a_ctrl": 0, "b_ctrl": 0, "contested_wins": 0,
                                                  "uncontested_wins": 0, "neither": 0, "n_obj": 0})
            d["n_obj"] += 1
            if ev.army_name == a_army.name:
                d["a_ctrl"] += 1
                if ev.b_oc > 0:
                    d["contested_wins"] += 1
                else:
                    d["uncontested_wins"] += 1
            elif ev.army_name == b_army.name:
                d["b_ctrl"] += 1
                if ev.a_oc > 0:
                    d["contested_wins"] += 1
                else:
                    d["uncontested_wins"] += 1
            else:
                d["neither"] += 1
    return a_fac, b_fac, seed, per_round, result

def summarize(label, matchups, seeds):
    print(f"\n=== {label} ===")
    agg = {}  # round -> [a_ctrl_list, b_ctrl_list, contested, uncontested]
    for a_fac, b_fac in matchups:
        for seed in seeds:
            a_fac_r, b_fac_r, seed_r, per_round, result = run_one(a_fac, b_fac, seed)
            for rnd in sorted(per_round):
                if rnd == 1:
                    continue
                d = per_round[rnd]
                bucket = agg.setdefault(rnd, {"ctrl_sum": 0, "n_side": 0, "contested": 0,
                                                "uncontested": 0, "neither": 0, "games": 0})
                bucket["ctrl_sum"] += d["a_ctrl"] + d["b_ctrl"]
                bucket["n_side"] += 2
                bucket["contested"] += d["contested_wins"]
                bucket["uncontested"] += d["uncontested_wins"]
                bucket["neither"] += d["neither"]
                bucket["games"] += 1
            print(f"  {a_fac} vs {b_fac} seed={seed}: "
                  f"A={result.a_vp} B={result.b_vp} winner={result.winner} "
                  f"round-ctrl(a,b,neither)="
                  + " ".join(f"r{r}:({per_round[r]['a_ctrl']},{per_round[r]['b_ctrl']},{per_round[r]['neither']})"
                             for r in sorted(per_round) if r != 1))
    print(f"  -- {label} per-round mean objectives controlled per side, and win-type split --")
    for rnd in sorted(agg):
        b = agg[rnd]
        mean_ctrl_per_side = b["ctrl_sum"] / b["n_side"] if b["n_side"] else 0
        tot_wins = b["contested"] + b["uncontested"]
        pct_uncontested = (b["uncontested"] / tot_wins * 100) if tot_wins else 0
        print(f"    round {rnd}: mean objectives controlled/side={mean_ctrl_per_side:.2f}  "
              f"wins that were uncontested={pct_uncontested:.0f}%  (n_games={b['games']})")

def main():
    seeds = [0, 1]
    summarize("DEATH GUARD (as side A)", MATCHUPS_DG, seeds)
    summarize("FIELD (non-DG, both sides)", MATCHUPS_FIELD, seeds)

if __name__ == "__main__":
    main()
