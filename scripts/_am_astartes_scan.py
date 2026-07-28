"""Scratch: scan AM vs Astartes across seeds, print per-seed capped VP + winner +
secondary breakdown, to pick the most diagnostic (close) AM loss for a board-read.
Uses the EXACT diag_pilot_am_vs_ik game construction (pair_seed packing) so the
seed I pick renders the same game. Read-only. Not committed."""
from __future__ import annotations
import random
import sys

from code.army_builder import build_faction_random_army
from code.events import RoundEnded, EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import (
    _pick_rotation_map, _pick_primary_mission, FACTIONS,
)

A_FAC = "Astra Militarum"
B_FAC = sys.argv[1] if len(sys.argv) > 1 else "Adeptus Astartes"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 16
_fac_idx = {f: i for i, f in enumerate(FACTIONS)}

print(f"# scan {A_FAC} (A) vs {B_FAC} (B)  N={N}")
print(f"{'seed':>4} {'winner':>7} {'A_cap':>6} {'B_cap':>6} {'margin':>7} {'A_raw':>6} {'B_raw':>6}")
rows = []
for seed in range(N):
    pair_seed = (_fac_idx[A_FAC] * 1000 + _fac_idx[B_FAC]) * 100 + seed
    random.seed(pair_seed)
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, subscribers=[log], map_=map_, primary_mission=primary).run()
    res = [e for e in log.events if isinstance(e, RoundEnded)]
    if not res:
        continue
    last = res[-1]
    ac, bc = last.a_vp_capped, last.b_vp_capped
    ar, br = last.a_vp_total, last.b_vp_total
    winner = "A" if ac > bc else ("B" if bc > ac else "draw")
    rows.append((seed, winner, ac, bc, ac - bc, ar, br))
    print(f"{seed:>4} {winner:>7} {ac:>6} {bc:>6} {ac-bc:>+7} {ar:>6} {br:>6}")

losses = [r for r in rows if r[1] == "B"]
losses.sort(key=lambda r: r[4], reverse=True)  # smallest deficit (closest loss) first
print(f"\n# AM wins {sum(1 for r in rows if r[1]=='A')}/{len(rows)}")
print("# closest AM losses (seed, margin):", [(r[0], r[4]) for r in losses[:5]])
