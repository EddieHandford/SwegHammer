"""Board-control Stage-0 instrument (avenue 2, docs/BOARD_CONTROL_PLAN.md).

Read-only. Sizes the three physical-board-control levers BEFORE any behaviour
code, and records the JAM baseline (anti-regression yardstick) the later stages
must not worsen:

  1. OC PACKING on objectives — summed base-footprint area of the OC-counted
     models within a marker's control radius vs the marker-circle area. A >100%
     packing ratio is OC that the Stage-1 no-overlap collision will physically
     cap (you cannot fit that much base in a 3" circle). Sizes Stage 1.
  2. FOOTPRINT OVERLAP — how many model pairs near a marker actually have
     intersecting bases today (collision-free stacking).
  3. CONTESTED concentration — packing on markers BOTH sides have OC on (the
     Knight-vs-bodies contest the displacement lever targets).
  4. BIG-MODEL-IN-RUIN — settled-position proxy for the ruin-wall lever
     (Stages 3-4): how often a VEHICLE/MONSTER/TITANIC (non-FLY) model sits
     inside a RUIN footprint it should have to route around.
  5. JAM baseline — per faction, models ending the game stranded in their own
     deployment zone + mean squad->nearest-objective distance. Stages 1-4
     (collision/make-way/walls) must not move these the wrong way.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_boardcontrol
"""
from __future__ import annotations

import os
import random

os.environ["SWEG_BOARDCTRL_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code import simulator
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

# The over-pole lives in Knight matchups, but board packing is army-wide; sample
# the Knights against a representative cross-section (hordes pack hardest).
KNIGHTS = ["Imperial Knights", "Chaos Knights"]
OPPONENTS = [
    "Astra Militarum", "Adeptus Mechanicus", "Tyranids", "Orks",
    "Necrons", "Adeptus Astartes", "Chaos Space Marines", "Aeldari",
]
SEEDS = list(range(1, 6))


def run_pair(a_fac: str, b_fac: str, seed: int) -> None:
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    Battle(a, b, map_=_pick_rotation_map(seed)).run()


def main() -> None:
    simulator.BOARDCONTROL_STATS.update(
        obj_rounds=0, overlap_pairs=0, packing_sum=0.0, packing_n=0,
        packing_over100=0, contested_rounds=0, contested_packing_sum=0.0,
        big_in_ruin=0, big_snaps=0, jam={})
    games = 0
    for kf in KNIGHTS:
        for opp in OPPONENTS:
            for seed in SEEDS:
                run_pair(kf, opp, seed)
                run_pair(opp, kf, seed)
                games += 2
    s = simulator.BOARDCONTROL_STATS
    print("=== BOARD-CONTROL Stage-0 instrument (Knight matchups) ===")
    print(f"games:                                          {games}")
    n = max(1, s["packing_n"])
    orn = max(1, s["obj_rounds"])
    print("OC PACKING on markers (base-footprint area vs the 3\" circle):")
    print(f"  marker-rounds sampled (>=1 model on it):      {s['obj_rounds']}")
    print(f"  mean packing ratio:                           {100*s['packing_sum']/n:.0f}%")
    print(f"  marker-rounds OVER 100% (collision will cap):  {s['packing_over100']}  ({100*s['packing_over100']/n:.0f}%)")
    print(f"  footprint-overlapping model pairs (total):    {s['overlap_pairs']}  ({s['overlap_pairs']/orn:.1f}/marker-round)")
    cr = max(1, s["contested_rounds"])
    print("CONTESTED markers (both sides have OC — the displacement target):")
    print(f"  contested marker-rounds:                      {s['contested_rounds']}")
    print(f"  mean packing there:                           {100*s['contested_packing_sum']/cr:.0f}%")
    bs = max(1, s["big_snaps"])
    print("BIG-MODEL-IN-RUIN (settled proxy for the ruin-wall lever):")
    print(f"  big (VEHICLE/MONSTER/TITANIC, non-FLY) snaps:  {s['big_snaps']}")
    print(f"  of those, sitting INSIDE a ruin footprint:    {s['big_in_ruin']}  ({100*s['big_in_ruin']/bs:.0f}%)")
    print("JAM baseline (anti-regression yardstick — Stages 1-4 must not worsen):")
    print(f"  {'faction':22s} {'inDZ/game':>10s} {'sqd->obj(in)':>13s}")
    for fac in sorted(s["jam"]):
        j = s["jam"][fac]
        g = max(1, j["games"]); sq = max(1, j["squads"])
        print(f"  {fac:22s} {j['dz_models_sum']/g:10.1f} {j['min_dist_sum']/sq:13.1f}")
    print()
    print("Reading: high packing-over-100% = OC stacking the collision lever (Stage 1)")
    print("will cap; high contested packing = the Knight-vs-bodies stack the lever targets;")
    print("big-in-ruin% sizes the ruin-wall lever; JAM rows are the yardstick for later stages.")


if __name__ == "__main__":
    main()
