"""
T'au archetype seeding diagnostic — does the curated Kauyon template seed
battlesuit-heavy compositions, or does it default to Fire Warriors + Pathfinders?

Real meta (May 2026 Warp Friends weekly + Goonhammer top tables): T'au lists are
battlesuit-heavy (Riptides, Crisis suits, Stormsurges). If our archetype only
seeds Strike/Breacher/Pathfinder teams, calibration vs meta will read T'au as
under-performing because the simulated armies are missing the actual win-cons.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.tau_diag

Read-only — does NOT modify catalogue or simulator code.
"""
from __future__ import annotations

import random
import statistics
from collections import Counter
from typing import Dict, List

from code.archetypes import build_archetype_army

FACTION = "T'au Empire"
N_TRIALS = 30
POINTS = 2000

# Profile-name buckets we care about. Match by substring on profile.name to be
# robust to catalogue rephrasings (Crisis Fireknife / Sunforge / Starscythe all
# count as Crisis).
BATTLESUIT_BUCKETS: Dict[str, List[str]] = {
    "Riptide":     ["Riptide"],
    "Crisis":      ["Crisis"],          # any Crisis variant
    "Stormsurge":  ["Stormsurge"],
    "Broadside":   ["Broadside"],
    "Ghostkeel":   ["Ghostkeel"],
    "Stealth":     ["Stealth Battlesuit"],
    "Commander":   ["Commander in", "Commander Farsight", "Commander Shadowsun"],
}

INFANTRY_BUCKETS: Dict[str, List[str]] = {
    "FireWarriors":  ["Strike Team", "Breacher Team"],
    "Pathfinders":   ["Pathfinder Team"],
    "Kroot":         ["Kroot"],
}


def _bucketize(profile_name: str, buckets: Dict[str, List[str]]) -> str | None:
    for bucket, needles in buckets.items():
        for needle in needles:
            if needle in profile_name:
                return bucket
    return None


def main() -> None:
    print(f"=== T'au archetype seeding diag — {N_TRIALS} trials @ {POINTS}pt ===")
    print()

    # Per-trial battlesuit presence flags + infantry counts.
    bs_presence: Counter = Counter()       # bucket -> count of trials where present
    bs_model_counts: Dict[str, List[int]] = {k: [] for k in BATTLESUIT_BUCKETS}
    inf_model_counts: Dict[str, List[int]] = {k: [] for k in INFANTRY_BUCKETS}

    sample_army_units: List[str] | None = None

    for trial in range(N_TRIALS):
        rng = random.Random(trial + 4242)
        army = build_archetype_army(
            "A", FACTION, POINTS,
            rng=rng,
            archetype_name="Kauyon",
        )

        bs_this_trial: Counter = Counter()
        inf_this_trial: Counter = Counter()

        for u in army.units:
            pname = u.profile.name
            bs_bucket = _bucketize(pname, BATTLESUIT_BUCKETS)
            if bs_bucket:
                bs_this_trial[bs_bucket] += 1
            inf_bucket = _bucketize(pname, INFANTRY_BUCKETS)
            if inf_bucket:
                inf_this_trial[inf_bucket] += 1

        for bucket in BATTLESUIT_BUCKETS:
            count = bs_this_trial[bucket]
            bs_model_counts[bucket].append(count)
            if count > 0:
                bs_presence[bucket] += 1
        for bucket in INFANTRY_BUCKETS:
            inf_model_counts[bucket].append(inf_this_trial[bucket])

        if trial == 0:
            sample_army_units = [u.profile.name for u in army.units]

    print(f"{'Battlesuit':14s}  {'Present':>10s}  {'Mean models':>12s}  {'Max':>4s}")
    print("-" * 50)
    for bucket in BATTLESUIT_BUCKETS:
        present = bs_presence[bucket]
        counts = bs_model_counts[bucket]
        mean = statistics.mean(counts) if counts else 0.0
        mx = max(counts) if counts else 0
        print(f"{bucket:14s}  {present:>5d}/{N_TRIALS:<3d}  {mean:>12.2f}  {mx:>4d}")

    print()
    print(f"{'Infantry':14s}  {'Mean models':>12s}  {'Max':>4s}")
    print("-" * 40)
    for bucket in INFANTRY_BUCKETS:
        counts = inf_model_counts[bucket]
        mean = statistics.mean(counts) if counts else 0.0
        mx = max(counts) if counts else 0
        print(f"{bucket:14s}  {mean:>12.2f}  {mx:>4d}")

    print()
    print(f"Sample trial 0 army composition ({len(sample_army_units or [])} models):")
    if sample_army_units:
        comp = Counter(sample_army_units)
        for name, n in sorted(comp.items(), key=lambda x: -x[1]):
            print(f"  {n:3d}x {name}")

    print()
    print("Expected from May 2026 real meta:")
    print("  Riptide present in >= 20/30 trials")
    print("  Crisis present in >= 25/30 trials")
    print("  Stormsurge present in some trials (variable)")


if __name__ == "__main__":
    main()
