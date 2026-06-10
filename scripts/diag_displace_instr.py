"""Displacement Stage-0 FIGHT-OUTCOME instrument runner (gate SWEG_DISPLACE_INSTR).

READ-ONLY. Sizes, per faction and per game, how many primary victory points the
simulator's raw-summed-Objective-Control marker model awards in board states real
play would resolve differently — the displacement gap — BEFORE any behavioural build.

It runs the four diagnostic matchups (both army orders) at 2000 points with curated
tournament archetypes, seeds 3..7, with SWEG_DISPLACE_INSTR on, and prints a per-
faction table of mean addressable victory points per game in BOTH directions plus the
faithful-tarpit baseline (informational, not addressable):

  under-pole  (vp_addressable_underpole)  — this faction holds a marker it was out-
              fought on locally; a real opponent would displace it off and take the tick.
  over-pole   (vp_addressable_overpole)    — this faction parks a single durable holder
              on an UNCONTESTED marker that nearby enemy bodies could swarm/contest.
  tarpit      (tarpit_vp_denied)           — this faction faithfully dies on a marker in
              engagement range to deny the holder; CORRECT play, counted separately.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_displace_instr
"""
from __future__ import annotations

import os
import random
from collections import defaultdict

os.environ["SWEG_DISPLACE_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

# The four diagnostic matchups (over-pole lives in the Knight rows, under-pole in the
# durable-winner rows). Each is run in BOTH army orders so a faction is sampled as both
# A and B and the per-faction means are not deployment-zone biased.
MATCHUPS = [
    ("Imperial Knights", "Astra Militarum"),
    ("Imperial Knights", "Tyranids"),
    ("Chaos Space Marines", "Adeptus Astartes"),
    ("Adeptus Mechanicus", "Orks"),
]
SEEDS = [3, 4, 5, 6, 7]
POINTS = 2000


def _accumulate(side_summary: dict, agg: dict) -> None:
    agg["games"] += 1
    agg["underpole"] += side_summary["vp_addressable_underpole"]
    agg["overpole"] += side_summary["vp_addressable_overpole"]
    agg["tarpit"] += side_summary["tarpit_vp_denied"]
    agg["under_ticks"] += side_summary["underpole_ticks"]
    agg["over_ticks"] += side_summary["overpole_ticks"]
    agg["tarpit_ticks"] += side_summary["tarpit_ticks"]
    agg["contested_ticks"] += side_summary["contested_ticks"]


def main() -> None:
    # faction -> running totals across every game it appeared in (either side)
    per_fac: dict = defaultdict(lambda: {
        "games": 0, "underpole": 0.0, "overpole": 0.0, "tarpit": 0.0,
        "under_ticks": 0, "over_ticks": 0, "tarpit_ticks": 0, "contested_ticks": 0,
    })
    games = 0
    for fa, fb in MATCHUPS:
        for a_fac, b_fac in ((fa, fb), (fb, fa)):
            for seed in SEEDS:
                a = build_faction_random_army(
                    "A", a_fac, POINTS, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army(
                    "B", b_fac, POINTS, rng=random.Random(seed + 10000), use_archetype=True)
                if not a.units or not b.units:
                    print(f"  (skipped {a_fac} vs {b_fac} seed {seed}: empty army)")
                    continue
                res = Battle(a, b, map_=_pick_rotation_map(seed)).run()
                games += 1
                d = res.displace
                if d is None:
                    raise RuntimeError(
                        "SWEG_DISPLACE_INSTR is set but BattleResult.displace is None — "
                        "the instrument did not attach its summary")
                _accumulate(d["a"], per_fac[a_fac])
                _accumulate(d["b"], per_fac[b_fac])

    print()
    print("=== Displacement Stage-0 FIGHT-OUTCOME instrument ===")
    print(f"matchups: {len(MATCHUPS)} (both orders)   seeds: {SEEDS}   points: {POINTS}   games: {games}")
    print("mean victory points per game (addressable both directions + faithful tarpit):")
    print(f"  {'faction':22s} {'games':>5s} {'under-pole':>11s} {'over-pole':>10s} {'tarpit':>8s}"
          f"  {'u/o/t/c ticks (mean)':>22s}")
    for fac in sorted(per_fac):
        a = per_fac[fac]
        g = max(1, a["games"])
        print(
            f"  {fac:22s} {a['games']:>5d} "
            f"{a['underpole']/g:>11.2f} {a['overpole']/g:>10.2f} {a['tarpit']/g:>8.2f}"
            f"  {a['under_ticks']/g:>5.1f}/{a['over_ticks']/g:>4.1f}/"
            f"{a['tarpit_ticks']/g:>4.1f}/{a['contested_ticks']/g:>4.1f}"
        )
    print()
    print("Reading: high UNDER-POLE = the faction holds markers it was out-fought on")
    print("(real play displaces it off — Astra Militarum / durable winners). High OVER-POLE")
    print("= a single durable holder parks on an uncontested marker nearby bodies could")
    print("swarm (Imperial Knights). TARPIT is faithful denial, counted but NOT addressable.")


if __name__ == "__main__":
    main()
