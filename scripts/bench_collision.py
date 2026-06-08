"""Quick perf benchmark: collision OFF vs ON on the worst case (Knight vs horde).

Times K battles single-process (no eval pool) so the per-battle cost is clear.
Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.bench_collision
"""
from __future__ import annotations

import os
import random
import time

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

K = 20


def _run(tag: str) -> float:
    t0 = time.perf_counter()
    for seed in range(1, K + 1):
        a = build_faction_random_army("A", "Imperial Knights", 2000,
                                      rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", "Tyranids", 2000,
                                      rng=random.Random(seed + 9000), use_archetype=True)
        if not a.units or not b.units:
            continue
        Battle(a, b, map_=_pick_rotation_map(seed)).run()
    dt = time.perf_counter() - t0
    print(f"{tag}: {K} battles in {dt:.1f}s ({dt / K:.2f}s/battle)")
    return dt


def main() -> None:
    for g in ("SWEG_COLLISION", "SWEG_PATHFIND", "SWEG_OCCGRID"):
        os.environ.pop(g, None)
    off = _run("OFF       ")
    os.environ["SWEG_COLLISION"] = "1"
    os.environ["SWEG_PATHFIND"] = "1"
    os.environ["SWEG_OCCGRID"] = "1"
    on = _run("ON (full) ")
    print(f"slowdown: {on / off:.2f}x")


if __name__ == "__main__":
    main()
