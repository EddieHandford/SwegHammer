"""Over-score mechanism localization (#83, wave 195).

Wave 194 resolved that the over-shooter cluster over-shoots dominantly via the
OBJECTIVE GAME (out-scores ~20 primary VP/game without out-fighting). This probe
splits HOW each faction scores its markers, to distinguish the watchdog's three:

  (i)  UNCONTESTED over-hold — the marker is scored with the opponent ABSENT
       (no OC on it). The contest-AI didn't reach it. -> more contest fidelity.
  (iii) CONCENTRATION — the marker is CONTESTED (opponent HAS OC on it) but the
       faction's concentrated OC WINS the count. The sim over-credits concentrated
       elite OC that real combat would have whittled / displaced. -> the harder
       per-model representation question.

For every faction (round-robin), with ``SWEG_OVERSCORE_INSTR=1``, we count its
scored markers and the share that were contested-but-won (iii) vs uncontested (i),
plus the mean winning vs losing OC on the marker. A cluster that scores mostly
UNCONTESTED markers = (i); mostly CONTESTED-WON = (iii).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_overscore
"""
from __future__ import annotations

import os
import random

os.environ["SWEG_OVERSCORE_INSTR"] = "1"

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
OVERSHOOTERS = {
    "Thousand Sons", "Emperor's Children", "World Eaters", "Adeptus Custodes",
    "Adepta Sororitas", "Leagues of Votann", "Drukhari", "Imperial Knights",
}
SEEDS = [1, 2, 3]
OPP_OFFSETS = [5, 11, 17]


def main():
    simulator.OVERSCORE_STATS.clear()
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
    for fac, d in simulator.OVERSCORE_STATS.items():
        sc = max(1, d["scored"])
        rows.append((
            100 * d["contested_won"] / sc, fac, d["scored"],
            100 * d["uncontested"] / sc,
            d["sum_win_oc"] / sc, d["sum_los_oc"] / sc,
        ))
    print("=== how each faction SCORES its markers (contested-won = (iii), uncontested = (i)) ===")
    print(f"{'faction':24} {'scored':>7} {'cont-won%':>10} {'uncont%':>8} {'winOC':>6} {'losOC':>6}  over?")
    for cw, fac, scored, uc, woc, loc in sorted(rows, reverse=True):
        tag = "OVER" if fac in OVERSHOOTERS else ""
        print(f"{fac:24} {scored:>7} {cw:>10.0f} {uc:>8.0f} {woc:>6.1f} {loc:>6.1f}  {tag}")
    print()
    over = [r for r in rows if r[1] in OVERSHOOTERS]
    rest = [r for r in rows if r[1] not in OVERSHOOTERS]
    def avg(rs, k): return sum(r[k] for r in rs) / max(1, len(rs))
    print(f"OVER-SHOOTERS  contested-won%={avg(over,0):.0f}  uncontested%={avg(over,3):.0f}  winOC={avg(over,4):.1f} losOC={avg(over,5):.1f}")
    print(f"REST           contested-won%={avg(rest,0):.0f}  uncontested%={avg(rest,3):.0f}  winOC={avg(rest,4):.1f} losOC={avg(rest,5):.1f}")
    print()
    print("Reading: high UNCONTESTED% -> (i) over-hold (extend the contest). High")
    print("CONTESTED-WON% with a big winOC-vs-losOC gap -> (iii) concentration (sim")
    print("over-credits concentrated elite OC real combat would have stripped).")


if __name__ == "__main__":
    main()
