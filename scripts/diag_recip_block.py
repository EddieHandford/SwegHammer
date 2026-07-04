"""Quantify how much of a faction's under-pole the reciprocal shooting-into-
engagement rule (SWEG_BGNT_RECIPROCAL) can own via blocked shooting.

For each opponent class it runs N archetype games (default faction: Astra
Militarum, the frame's biggest under-pole) with the read-only SWEG_RECIP_INSTR
instrument on, and reports, per game:

  * activations reaching the reciprocal filter, and how many had a legal target;
  * activations the filter fully EMPTIED (a lost shooting activation);
  * activations where it dropped the single best target for a weaker shot
    (a focus-fire DOWNGRADE), and the expected wounds surrendered.

The pairing with a direct win-rate counterfactual is the existing kill-switch:
run evaluate_vs_meta with SWEG_BGNT_RECIPROCAL=0 and paired_delta against the
standing anchor to read the rule's net win-rate ownership (no code needed).

Run: SWEG_RECIP_INSTR=1 PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 \
     python -m scripts.diag_recip_block <n_games> <faction> <opp1> [opp2 ...]
"""
from __future__ import annotations

import os
import random
import sys

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from code.sim.constants import RECIP_INSTR_STATS
from scripts.evaluate_vs_meta import _pick_rotation_map

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
FAC = sys.argv[2] if len(sys.argv) > 2 else "Astra Militarum"
OPPS = sys.argv[3:] if len(sys.argv) > 3 else [
    "Emperor's Children", "World Eaters", "Imperial Knights",
]

if not os.environ.get("SWEG_RECIP_INSTR"):
    raise SystemExit("Set SWEG_RECIP_INSTR=1 to populate the instrument.")


def _run_one(seed, opp):
    # Pin the global RNG the Battle draws from so the mechanism footprint is
    # reproducible run-to-run (the diag is mechanism evidence, never rate
    # evidence — the seed scheme is not a win-rate sample).
    random.seed(seed)
    a = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    Battle(a, b, map_=_pick_rotation_map(seed)).run()


print(f"### Reciprocal-block footprint on {FAC}  ({N} games/opponent)")
for opp in OPPS:
    RECIP_INSTR_STATS.clear()
    for s in range(N):
        _run_one(s, opp)
    d = RECIP_INSTR_STATS.get(FAC, {})
    reach = d.get("reaching_filter", 0)
    had = d.get("had_target", 0)
    lost = d.get("lost_all", 0)
    partial = d.get("partial_retarget", 0)
    dropped = d.get("targets_dropped", 0)
    downg = d.get("downgraded_shot", 0)
    downg_ew = d.get("downgrade_ew_lost", 0.0)
    print(f"\n=== {FAC} vs {opp} ===")
    print(f"  activations reaching reciprocal filter : {reach:5d}  ({reach/N:5.1f}/game)")
    print(f"  ... with >=1 legal target before it    : {had:5d}  ({had/N:5.1f}/game)")
    print(f"  ... FULLY LOST to reciprocal           : {lost:5d}  ({lost/N:5.1f}/game)")
    print(f"  ... partial re-target (dropped some)   : {partial:5d}  ({partial/N:5.1f}/game)")
    print(f"  candidate-targets dropped              : {dropped:5d}  ({dropped/N:5.1f}/game)")
    print(f"  focus-fire DOWNGRADES (best dropped)   : {downg:5d}  ({downg/N:5.1f}/game)")
    print(f"  expected wounds lost to downgrade      : {downg_ew:7.1f}  ({downg_ew/N:5.2f}/game)")
    if had:
        print(f"  share of targeted activations lost     : {100.0*lost/had:5.1f}%")
        print(f"  share of targeted activations downgraded: {100.0*downg/had:4.1f}%")
