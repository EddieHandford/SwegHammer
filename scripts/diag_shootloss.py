"""Screening / melee-avoidance shoot-loss probe (#86, wave 198).

Under-output is real field-average (AM 56 / AdMech 49 vs control 80). The guns +
keywords are at parity (wave 191) and durability is faithful (wave 197), so a
-30-40% output gap, if not "weak guns," may be the AI letting gunlines get CHARGED
and silenced. This probe (gated SWEG_SHOOTLOSS_INSTR) measures, per faction, the
shooting OUTPUT (attacks x hit x dmg) reaching the shoot gate, split by free /
pistol / big-gun-penalty / engagement-BLOCKED. A high blocked% for AM/AdMech vs the
field = the screening/melee-avoidance lever (real gunlines screen + fall-back-shoot).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_shootloss
"""
from __future__ import annotations

import os
import random

os.environ["SWEG_SHOOTLOSS_INSTR"] = "1"

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
    simulator.SHOOTLOSS_STATS.clear()
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
    for fac, d in simulator.SHOOTLOSS_STATS.items():
        tot = d["free"] + d["pistol"] + d["biggun_penalty"] + d["blocked"]
        if tot <= 0:
            continue
        lost = d["blocked"] + 0.33 * d["biggun_penalty"]  # blocked = full loss; -1 penalty ~ 1/3 output
        rows.append((100 * lost / tot, fac, 100 * d["blocked"] / tot, 100 * d["biggun_penalty"] / tot))
    print("=== shooting output lost to engagement, per faction ===")
    print(f"{'faction':24} {'lost%':>6} {'blocked%':>9} {'biggunPen%':>11}  under?")
    for lost, fac, blk, bg in sorted(rows, reverse=True):
        tag = "UNDER" if fac in UNDER else ""
        print(f"{fac:24} {lost:>6.0f} {blk:>9.0f} {bg:>11.0f}  {tag}")
    print()
    und = [r for r in rows if r[1] in UNDER]
    rest = [r for r in rows if r[1] not in UNDER]
    def avg(rs, k): return sum(r[k] for r in rs) / max(1, len(rs))
    print(f"UNDER (AM/AdMech)  lost%={avg(und,0):.0f}  blocked%={avg(und,2):.0f}  biggunPen%={avg(und,3):.0f}")
    print(f"REST               lost%={avg(rest,0):.0f}  blocked%={avg(rest,2):.0f}  biggunPen%={avg(rest,3):.0f}")
    print()
    print("Reading: AM/AdMech lost% FAR above the field -> the screening/melee-")
    print("avoidance AI gap is the under-output lever. ~Field-level -> not the lever;")
    print("the guns under-deal for another reason (or it's near the floor).")


if __name__ == "__main__":
    main()
