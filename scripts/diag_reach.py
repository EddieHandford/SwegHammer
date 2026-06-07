"""Reach-degradation localiser (wave 211). For a matchup, run K battles under
collision with SWEG_REACH_INSTR and report, for BIG movers, the split between
faithful enemy-screening (cap_t<1) and open-space over-impediment (cap_t>=1 but
end illegal). Run: PYTHONHASHSEED=0 python -m scripts.diag_reach "Astra Militarum" "Aeldari"
"""
from __future__ import annotations

import os
import random
import sys

os.environ["SWEG_REACH_INSTR"] = "1"

from code import simulator
from code.army_builder import build_faction_random_army
from code.simulator import Battle, REACH_STATS
from scripts.evaluate_vs_meta import _pick_rotation_map

A_FAC = sys.argv[1] if len(sys.argv) > 1 else "Astra Militarum"
B_FAC = sys.argv[2] if len(sys.argv) > 2 else "Aeldari"
K = int(sys.argv[3]) if len(sys.argv) > 3 else 6


def main() -> None:
    for k in REACH_STATS:
        REACH_STATS[k] = 0
    for seed in range(1, K + 1):
        a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(seed + 9000), use_archetype=True)
        if not a.units or not b.units:
            continue
        Battle(a, b, map_=_pick_rotation_map(seed)).run()
    m = REACH_STATS["big_moves"] or 1
    print(f"{A_FAC} vs {B_FAC}  ({K} battles)")
    print(f"  big-mover moves:        {REACH_STATS['big_moves']}")
    print(f"  reached straight:       {REACH_STATS['big_reached']}  ({100*REACH_STATS['big_reached']//m}%)")
    print(f"  ENEMY-capped (faithful): {REACH_STATS['big_enemy_capped']}  ({100*REACH_STATS['big_enemy_capped']//m}%)")
    print(f"  OPEN-blocked (ARTIFACT): {REACH_STATS['big_open_blocked']}  ({100*REACH_STATS['big_open_blocked']//m}%)")


if __name__ == "__main__":
    main()
