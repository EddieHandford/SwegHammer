"""Stranding-ratio drill (structural re-model plan, Step 2 — the wave-93 re-run).

Per faction, summed Objective Control within the control radius (three inches)
versus within twice it (six inches) of markers, at every scoring snapshot, across
a few Knight-versus-horde and under-pole-versus-over-pole matchups on the current
frame. A six-to-three ratio near 2 means half the near-marker control strands in
the three-to-six-inch ring (the M4-alpha target); near 1 means the default-on
movement changes (SWEG_MASS / SWEG_DISPLACE_FALLBACK / collision) already closed
it. The binding self-veto for M4-alpha. Read-only (the instrument never changes
behaviour; SWEG_STRAND_INSTR default-off keeps production byte-identical).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_stranding [K]
"""
from __future__ import annotations

import os
import random
import sys

os.environ["SWEG_STRAND_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code.simulator import Battle, STRAND_STATS
from scripts.evaluate_vs_meta import _pick_rotation_map

K = int(sys.argv[1]) if len(sys.argv) > 1 else 12

# Canonical Knight-versus-horde contest plus the dominant under-pole and a second
# durable-elite-versus-horde pair, to read the stranding for the factions the
# M4-alpha lever targets (the hordes Chaos Daemons / Astra Militarum / Necrons).
MATCHUPS = [
    ("Imperial Knights", "Chaos Daemons"),
    ("Astra Militarum", "World Eaters"),
    ("Necrons", "Adeptus Custodes"),
]


def main() -> None:
    STRAND_STATS.clear()
    for af, bf in MATCHUPS:
        for seed in range(1, K + 1):
            a = build_faction_random_army(
                "A", af, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army(
                "B", bf, 2000, rng=random.Random(seed + 9000), use_archetype=True)
            if not a.units or not b.units:
                continue
            Battle(a, b, map_=_pick_rotation_map(seed)).run()

    print(f"Stranding drill — {len(MATCHUPS)} matchups x {K} battles, SWEG_STRAND_INSTR")
    print(f"{'Faction':22s} {'OC<=3in':>9} {'OC<=6in':>9} {'6/3 ratio':>9} {'snaps':>6}")
    print("-" * 60)
    for fac in sorted(STRAND_STATS,
                      key=lambda f: -(STRAND_STATS[f]['oc6'] /
                                      max(STRAND_STATS[f]['oc3'], 1e-9))):
        s = STRAND_STATS[fac]
        ratio = s['oc6'] / s['oc3'] if s['oc3'] else float('inf')
        print(f"{fac:22s} {s['oc3']:9.0f} {s['oc6']:9.0f} {ratio:9.2f} {s['snaps']:6d}")
    print("-" * 60)
    print("Self-veto: a horde 6/3 ratio < ~1.3 => stranding already closed (M4-alpha")
    print("a no-op); ~2 => stranding still open, M4-alpha gap confirmed.")


if __name__ == "__main__":
    main()
