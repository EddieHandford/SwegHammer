"""Sim (from the CALIBRATION anchor log) vs REAL (StatCheck) win% vs Imperial
Knights — the authoritative, side-balanced comparison.

The anchor log holds every round-robin game (both orientations). For each faction
X we average X-as-A-vs-IK and X-as-B-vs-IK (= 100 - IK-as-A-vs-X) to cancel any
army-side / first-player bias, giving the symmetric sim X-vs-IK win rate that is
directly comparable to StatCheck. No sim is run — pure arithmetic on logged winners.

Run: python -m scripts.diag_log_vs_ik [path-to-log]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

IK = "Imperial Knights"
LOG = sys.argv[1] if len(sys.argv) > 1 else "data/_anchor_sc17a_n80_log.json"

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
# StatCheck real win% vs Imperial Knights (~ = approximate / aggregated).
REAL = {
    "Genestealer Cults": 65, "Chaos Space Marines": 63, "Drukhari": 61,
    "Adepta Sororitas": 60, "World Eaters": 58, "Emperor's Children": 58,
    "Chaos Knights": 53, "Adeptus Custodes": 53, "Thousand Sons": 53,
    "Leagues of Votann": 52, "T'au Empire": 51, "Death Guard": 51, "Orks": 50,
    "Chaos Daemons": 47, "Aeldari": 47, "Adeptus Astartes": 50, "Necrons": 46,
    "Tyranids": 45, "Astra Militarum": 45, "Adeptus Mechanicus": 44, "Grey Knights": 39,
}


def main():
    d = json.load(open(LOG, encoding="utf-8"))
    n_ab = defaultdict(int)
    w_a = defaultdict(int)
    for a, b, _s, w in d["games"]:
        n_ab[(a, b)] += 1
        if w == "A":
            w_a[(a, b)] += 1

    def apct(a, b):
        n = n_ab[(a, b)]
        return (100.0 * w_a[(a, b)] / n) if n else None

    rows = []
    for fac in REAL:
        xa = apct(fac, IK)       # X as A vs IK
        ika = apct(IK, fac)      # IK as A vs X
        if xa is None or ika is None:
            continue
        xb = 100.0 - ika         # X as B vs IK = 100 - (IK-as-A win%)
        sym = (xa + xb) / 2.0
        rows.append((sym - REAL[fac], sym, xa, xb, REAL[fac], fac))
    rows.sort(key=lambda r: -abs(r[0]))

    print(f"# Sim (anchor log, side-balanced) vs REAL win% vs {IK}  [{LOG}]")
    print(f"{'faction':22} {'sim':>5} {'(A':>5} {'B)':>5} {'real':>5} {'delta':>7}")
    print("-" * 56)
    for d_, sym, xa, xb, real, fac in rows:
        print(f"{fac:22} {sym:5.1f} {xa:5.0f} {xb:5.0f} {real:5.0f} {d_:+7.1f}")
    print("-" * 56)
    # Sanity: IK aggregate (IK-as-A, unweighted) — should be ~mid (over-pole-ish).
    ikwr = [apct(IK, o) for o in FACTIONS if o != IK and apct(IK, o) is not None]
    others_vs_ik = [apct(o, IK) for o in FACTIONS if o != IK and apct(o, IK) is not None]
    print(f"SANITY  IK-as-A mean win% (unweighted): {sum(ikwr)/len(ikwr):5.1f}  "
          f"| field-as-A-vs-IK mean: {sum(others_vs_ik)/len(others_vs_ik):5.1f}")
    print("delta = sim - real. + => sim over-rates faction vs Knights; - => under-rates.")


if __name__ == "__main__":
    main()
