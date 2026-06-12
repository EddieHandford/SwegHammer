"""Under-side OC-delivery localization (#84, wave 196).

The watchdog pivoted to the under-side (Astra Militarum / Adeptus Mechanicus, the
biggest unattacked residual ~26 combined). Wave 195 showed they hold FEWER markers
(99/107 vs field ~127) but score them the SAME way (76% uncontested, normal
contested-won) — so when they ARE on a marker they win the contest normally. The
remaining question is whether they ever get their Objective Control ONTO markers.

This probe (gated SWEG_DELIVERY_INSTR) measures, per faction, the army's whole
on-board effective OC vs the OC it actually credits to objectives:

  delivery% = delivered_OC / total_OC

  LOW for AM/AdMech  -> (1) POSITIONING: their durable gunlines sit back and never
                        bring OC to markers (no spare bodies, low mobility).
  NORMAL             -> the under-score is (2) displacement or (3) under-credit,
                        not delivery.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_delivery
"""
from __future__ import annotations

import os
import random

os.environ["SWEG_DELIVERY_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code import simulator
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
UNDER = {"Astra Militarum", "Adeptus Mechanicus"}
SEEDS = [1, 2, 3]
OPP_OFFSETS = [5, 11, 17]


def main():
    simulator.DELIVERY_STATS.clear()
    n = len(FACTIONS)
    for i, fa in enumerate(FACTIONS):
        for off in OPP_OFFSETS:
            fb = FACTIONS[(i + off) % n]
            for seed in SEEDS:
                a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 5000), use_archetype=True)
                if not a.units or not b.units:
                    continue
                Battle(a, b, map_=_pick_rotation_map(seed)).run()

    rows = []
    for fac, d in simulator.DELIVERY_STATS.items():
        r = max(1, d["rounds"])
        tot = d["total"] / r
        deliv = d["delivered"] / r
        rate = 100 * deliv / tot if tot else 0.0
        rows.append((rate, fac, tot, deliv))
    print("=== per-faction OC delivery (delivered-to-markers / total on-board OC) ===")
    print(f"{'faction':24} {'totalOC/rd':>10} {'deliv/rd':>9} {'deliv%':>7}  under?")
    for rate, fac, tot, deliv in sorted(rows, reverse=True):
        tag = "UNDER" if fac in UNDER else ""
        print(f"{fac:24} {tot:>10.1f} {deliv:>9.1f} {rate:>7.0f}  {tag}")
    print()
    und = [r for r in rows if r[1] in UNDER]
    rest = [r for r in rows if r[1] not in UNDER]
    def avg(rs, k): return sum(r[k] for r in rs) / max(1, len(rs))
    print(f"UNDER (AM/AdMech)  totalOC/rd={avg(und,2):.1f} deliv/rd={avg(und,3):.1f} deliv%={avg(und,0):.0f}")
    print(f"REST               totalOC/rd={avg(rest,2):.1f} deliv/rd={avg(rest,3):.1f} deliv%={avg(rest,0):.0f}")
    print()
    print("Reading: AM/AdMech LOW total OC and/or LOW delivery% -> (1) POSITIONING")
    print("(durable gunlines never bring OC to markers). NORMAL delivery% -> the")
    print("under-score is displacement/under-credit, not reach.")


if __name__ == "__main__":
    main()
