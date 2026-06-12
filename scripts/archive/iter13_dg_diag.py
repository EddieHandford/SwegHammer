"""Auto-loop iter 13 — DG random_fill diag: Mortarion / Foetid Bloat-drone
appearance rate.

Real-meta DG lists are built around Mortarion (EPIC HERO Warlord) + 1-2
Foetid Bloat-Drones, but our random_fill rarely picks them. This script
samples 30 generated DG armies and reports the include-rate for both
profiles (before/after the iter13 seed in `build_faction_random_army`).

Usage:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.iter13_dg_diag

Read-only — no catalogue / strategy / simulator mutation. N=30.
"""
from __future__ import annotations

import os
import random
import sys
from collections import Counter

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter13_dg_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army


N_BUILDS = 30
POINTS = 1000
FACTION = "Death Guard"


def main() -> None:
    mortarion_seen = 0
    drone_count_per_build = []
    profile_counter: Counter = Counter()

    for s in range(N_BUILDS):
        seed = 12345 + s
        army = build_faction_random_army(
            "DG-diag",
            FACTION,
            POINTS,
            rng=random.Random(seed),
        )
        names = [u.profile.name for u in army.units]
        has_mort = "Mortarion" in names
        n_drones = sum(1 for n in names if n == "Foetid Bloat-drone")
        if has_mort:
            mortarion_seen += 1
        drone_count_per_build.append(n_drones)
        for n in set(names):
            profile_counter[n] += 1

    n_with_drone = sum(1 for c in drone_count_per_build if c > 0)
    total_drones = sum(drone_count_per_build)
    print(
        f"Iter 13 — DG random_fill diagnostic. N={N_BUILDS}, {POINTS} pts."
    )
    print("-" * 72)
    print(f"Mortarion appearance rate:      {mortarion_seen}/{N_BUILDS}"
          f" = {100.0*mortarion_seen/N_BUILDS:.1f}%")
    print(f"Foetid Bloat-drone (>=1) rate:  {n_with_drone}/{N_BUILDS}"
          f" = {100.0*n_with_drone/N_BUILDS:.1f}%")
    print(f"Total Foetid Bloat-drones drafted: {total_drones}"
          f"  (avg {total_drones/N_BUILDS:.2f}/build)")
    print()
    print("Top 12 profile include-rates across builds:")
    for name, c in profile_counter.most_common(12):
        print(f"  {name:48s} {c:3d}/{N_BUILDS}  ({100.0*c/N_BUILDS:.1f}%)")


if __name__ == "__main__":
    main()
