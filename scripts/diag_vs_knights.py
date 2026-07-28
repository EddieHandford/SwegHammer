"""Sim vs REAL (StatCheck) per-faction win% AGAINST Imperial Knights — localise
where the simulator's Knight matchups diverge from real tournament data.

Real values are StatCheck "armies vs Imperial Knights" Win Rate (2026), read from
the meta-overview table. Space-Marine chapters and Imperial Agents are not separate
sim factions; Adeptus Astartes real is chapter-dependent (~46-66) and Astra
Militarum real is detachment-dependent (25-63) — both flagged approximate.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_vs_knights [N]
"""
from __future__ import annotations

import sys

from scripts.pilot_manual import _winner   # seeds the global RNG per game

OVER = "Imperial Knights"

# StatCheck real win% vs Imperial Knights (approx where flagged).
REAL_VS_IK = {
    "Genestealer Cults": 65,
    "Chaos Space Marines": 63,
    "Drukhari": 61,
    "Adepta Sororitas": 60,
    "World Eaters": 58,
    "Emperor's Children": 58,
    "Chaos Knights": 53,
    "Adeptus Custodes": 53,
    "Thousand Sons": 53,
    "Leagues of Votann": 52,
    "T'au Empire": 51,
    "Death Guard": 51,
    "Orks": 50,
    "Chaos Daemons": 47,
    "Aeldari": 47,
    "Adeptus Astartes": 50,        # approx — chapter-dependent 46-66
    "Necrons": 46,
    "Tyranids": 45,
    "Astra Militarum": 45,         # approx — detachment-dependent 25-63
    "Adeptus Mechanicus": 44,
    "Grey Knights": 39,
}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    rows = []
    for fac, real in REAL_VS_IK.items():
        w = sum(1 for s in range(n) if _winner(fac, OVER, s)[0] == "A")
        sim = 100.0 * w / n
        rows.append((sim - real, sim, real, fac))
    rows.sort(key=lambda r: -abs(r[0]))
    print(f"# Sim vs REAL win% vs {OVER}  N={n}  (sorted by |divergence|)")
    print(f"{'faction':22} {'sim':>6} {'real':>6} {'delta':>7}")
    print("-" * 45)
    for d, sim, real, fac in rows:
        flag = " ~" if fac in ("Adeptus Astartes", "Astra Militarum") else ""
        print(f"{fac:22} {sim:6.1f} {real:6.0f} {d:+7.1f}{flag}")
    print("-" * 45)
    print("delta = sim - real. + => sim over-rates the faction vs Knights "
          "(Knights too weak / faction too strong); - => sim under-rates it.")


if __name__ == "__main__":
    main()
