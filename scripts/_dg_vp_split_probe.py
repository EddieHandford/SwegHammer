"""Read-only probe: decompose Death Guard's victory points into primary vs
secondary per game, vs a spread of opponents, split by going-first/going-second.

Scratch probe per LENS instructions — does NOT touch production code.
Reuses the event-parsing machinery from scripts/diag_signatures.py.

Usage:
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._dg_vp_split_probe
"""
from __future__ import annotations

import os
import random
import statistics
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts._dg_vp_split_probe"] + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army  # noqa: E402
from code.events import EventLog  # noqa: E402
from code.simulator import Battle  # noqa: E402
from scripts.evaluate_vs_meta import _pick_rotation_map  # noqa: E402
from scripts.diag_signatures import _parse_event_log  # noqa: E402

OPPONENTS = [
    "Adeptus Astartes",
    "Orks",
    "Tyranids",
    "T'au Empire",
    "Necrons",
    "Aeldari",
]
SEEDS = [0, 1, 2, 3]

rows = []  # per player-game dicts

for opp in OPPONENTS:
    for seed in SEEDS:
        rng_a = random.Random(seed)
        rng_b = random.Random(seed + 10_000)
        dg = build_faction_random_army("A", "Death Guard", 2000, rng=rng_a, use_archetype=True)
        oppo = build_faction_random_army("B", opp, 2000, rng=rng_b, use_archetype=True)
        log = EventLog()
        map_ = _pick_rotation_map(seed)
        battle = Battle(dg, oppo, subscribers=[log], map_=map_)
        result = battle.run()
        rec = _parse_event_log(log, result)

        a_prim_raw = sum(rec.a_round_primary)
        b_prim_raw = sum(rec.b_round_primary)
        a_sec_raw = max(0, rec.a_uncapped_total - a_prim_raw)
        b_sec_raw = max(0, rec.b_uncapped_total - b_prim_raw)
        a_prim = min(a_prim_raw, 50)
        b_prim = min(b_prim_raw, 50)
        a_sec = min(a_sec_raw, 40)
        b_sec = min(b_sec_raw, 40)

        dg_first = (rec.first_player == rec.a_name)
        dg_won = (rec.winner == rec.a_name)

        # Round-2 primary (index 1) split for the going-first winner question.
        r2_a = rec.a_round_primary[1] if len(rec.a_round_primary) > 1 else None
        r2_b = rec.b_round_primary[1] if len(rec.b_round_primary) > 1 else None

        rows.append(dict(
            opp=opp, seed=seed,
            dg_first=dg_first, dg_won=dg_won,
            winner=rec.winner,
            dg_prim=a_prim, dg_sec=a_sec, dg_total=a_prim + a_sec,
            opp_prim=b_prim, opp_sec=b_sec, opp_total=b_prim + b_sec,
            r2_dg=r2_a, r2_opp=r2_b,
            first_player=rec.first_player,
            dg_round_prim=list(rec.a_round_primary),
            opp_round_prim=list(rec.b_round_primary),
        ))
        print(f"  DG vs {opp:20s} seed={seed} first={'DG' if dg_first else opp[:12]:12s} "
              f"DG={a_prim+a_sec:3d}(p{a_prim}+s{a_sec}) {opp[:16]:16s}={b_prim+b_sec:3d}(p{b_prim}+s{b_sec}) "
              f"winner={result.winner or 'Draw'} r2[DG={r2_a},{opp[:4]}={r2_b}]")

print()
print("=" * 78)
n = len(rows)
dg_prim_mean = statistics.mean(r["dg_prim"] for r in rows)
dg_sec_mean = statistics.mean(r["dg_sec"] for r in rows)
opp_prim_mean = statistics.mean(r["opp_prim"] for r in rows)
opp_sec_mean = statistics.mean(r["opp_sec"] for r in rows)
field_prim_mean = statistics.mean([r["dg_prim"] for r in rows] + [r["opp_prim"] for r in rows])
field_sec_mean = statistics.mean([r["dg_sec"] for r in rows] + [r["opp_sec"] for r in rows])

print(f"N games = {n}")
print(f"Death Guard   mean primary = {dg_prim_mean:.2f}   mean secondary = {dg_sec_mean:.2f}   mean total = {dg_prim_mean+dg_sec_mean:.2f}")
print(f"Opponents     mean primary = {opp_prim_mean:.2f}   mean secondary = {opp_sec_mean:.2f}   mean total = {opp_prim_mean+opp_sec_mean:.2f}")
print(f"Field average mean primary = {field_prim_mean:.2f}   mean secondary = {field_sec_mean:.2f}")
print(f"DG primary  edge over opponents: {dg_prim_mean - opp_prim_mean:+.2f}")
print(f"DG secondary edge over opponents: {dg_sec_mean - opp_sec_mean:+.2f}")

dg_win_rate = statistics.mean(1.0 if r["dg_won"] else 0.0 for r in rows)
print(f"Death Guard win rate (this sample) = {dg_win_rate*100:.1f}%")

# going-first splits
dg_first_rows = [r for r in rows if r["dg_first"]]
dg_second_rows = [r for r in rows if not r["dg_first"]]
if dg_first_rows:
    wr_first = statistics.mean(1.0 if r["dg_won"] else 0.0 for r in dg_first_rows)
    print(f"DG going FIRST:  n={len(dg_first_rows)}  win rate={wr_first*100:.1f}%  "
          f"mean primary={statistics.mean(r['dg_prim'] for r in dg_first_rows):.2f}  "
          f"mean secondary={statistics.mean(r['dg_sec'] for r in dg_first_rows):.2f}")
if dg_second_rows:
    wr_second = statistics.mean(1.0 if r["dg_won"] else 0.0 for r in dg_second_rows)
    print(f"DG going SECOND: n={len(dg_second_rows)}  win rate={wr_second*100:.1f}%  "
          f"mean primary={statistics.mean(r['dg_prim'] for r in dg_second_rows):.2f}  "
          f"mean secondary={statistics.mean(r['dg_sec'] for r in dg_second_rows):.2f}")

# overall going-first win rate (field, both sides)
gf_total = 0
gf_wins = 0
for r in rows:
    if r["winner"] and r["winner"] != "Draw":
        gf_total += 1
        if r["first_player"] == r["winner"]:
            gf_wins += 1
print(f"Field going-first win rate (this sample) = {gf_wins}/{gf_total} = {gf_wins/gf_total*100:.1f}%")

# Round-2 primary: does the going-first side out-score round 2 primary?
r2_first_vals = []
r2_second_vals = []
for r in rows:
    if r["r2_dg"] is None or r["r2_opp"] is None:
        continue
    if r["dg_first"]:
        r2_first_vals.append(r["r2_dg"])
        r2_second_vals.append(r["r2_opp"])
    else:
        r2_first_vals.append(r["r2_opp"])
        r2_second_vals.append(r["r2_dg"])
print(f"Round-2 primary: going-first side mean = {statistics.mean(r2_first_vals):.2f}   "
      f"going-second side mean = {statistics.mean(r2_second_vals):.2f}   "
      f"(n={len(r2_first_vals)} games)")

# Cap-15 hit fraction (rounds 2-5), DG vs opponents.
dg_cap_hits = dg_cap_total = 0
opp_cap_hits = opp_cap_total = 0
dg_round_means = [[] for _ in range(5)]
opp_round_means = [[] for _ in range(5)]
for r in rows:
    for i, v in enumerate(r["dg_round_prim"]):
        dg_round_means[i].append(v)
        if i >= 1:
            dg_cap_total += 1
            if v >= 15:
                dg_cap_hits += 1
    for i, v in enumerate(r["opp_round_prim"]):
        opp_round_means[i].append(v)
        if i >= 1:
            opp_cap_total += 1
            if v >= 15:
                opp_cap_hits += 1
print()
print(f"DG cap15-hit fraction (rounds 2-5, per player-round): {dg_cap_hits}/{dg_cap_total} = "
      f"{dg_cap_hits/dg_cap_total*100:.1f}%" if dg_cap_total else "n/a")
print(f"Opponent cap15-hit fraction (rounds 2-5, per player-round): {opp_cap_hits}/{opp_cap_total} = "
      f"{opp_cap_hits/opp_cap_total*100:.1f}%" if opp_cap_total else "n/a")
print("DG per-round primary means:  " + "  ".join(
    f"R{i+1}={statistics.mean(v):.1f}" if v else f"R{i+1}=-" for i, v in enumerate(dg_round_means)))
print("Opp per-round primary means: " + "  ".join(
    f"R{i+1}={statistics.mean(v):.1f}" if v else f"R{i+1}=-" for i, v in enumerate(opp_round_means)))

print()
print("Per-opponent DG breakdown:")
for opp in OPPONENTS:
    opp_rows = [r for r in rows if r["opp"] == opp]
    dgp = statistics.mean(r["dg_prim"] for r in opp_rows)
    dgs = statistics.mean(r["dg_sec"] for r in opp_rows)
    op_p = statistics.mean(r["opp_prim"] for r in opp_rows)
    op_s = statistics.mean(r["opp_sec"] for r in opp_rows)
    wr = statistics.mean(1.0 if r["dg_won"] else 0.0 for r in opp_rows)
    print(f"  vs {opp:20s} DG win%={wr*100:5.1f}  DG prim={dgp:5.2f} sec={dgs:5.2f} total={dgp+dgs:5.2f}  |  "
          f"opp prim={op_p:5.2f} sec={op_s:5.2f} total={op_p+op_s:5.2f}")
