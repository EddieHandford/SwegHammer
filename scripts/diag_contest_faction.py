"""Per-faction OC-contest instrument (#79 follow-up, wave 193).

The wave-192 balanced contest lever moved the over-pole down but Thousand Sons
(gated 2.0 -> 5.4) and Emperor's Children (4.6 -> 8.0) ROSE — the contest helps
body-aggressive elite armies. This probe asks whether that is the FAITHFUL
body-army reward (they hold spare bodies that genuinely out-Control an enemy
marker, so the winnable-contest boost legitimately fires for them) or the contest
over-helping them. We run every faction across a spread of opponents with
``SWEG_CONTEST=1 SWEG_CONTEST_INSTR=1`` and report, per faction (normalized per
game it appears in):

  winnable   = times the contest's x1.7 boost fired (a SPARE body that can win an
               enemy-held marker by committing — the faithful contest)
  unwinnable = times the x0.3 drop fired (offered a steal it cannot win)
  already    = times the x0.6 just-enough fired (already winnably contesting)

If TSons/EC's winnable/game is HIGH and broadly in line with other durable-body
armies (Death Guard, Sororitas, Tyranids), the contest is faithfully rewarding the
midboard-control archetype and their over-shoot is a SEPARATE pre-existing residual.
If TSons/EC are clear outliers above comparable body armies, the contest over-helps.

Run with: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_contest_faction
"""
from __future__ import annotations

import os
import random
from collections import defaultdict

os.environ["SWEG_CONTEST"] = "1"
os.environ["SWEG_CONTEST_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code import strategy
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
SEEDS = [1, 2, 3]


def main() -> None:
    strategy.CONTEST_STATS.clear()
    appearances: dict = defaultdict(int)
    n = len(FACTIONS)
    for i, fa in enumerate(FACTIONS):
        fb = FACTIONS[(i + 7) % n]  # fixed offset spread of opponents
        for seed in SEEDS:
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 9999), use_archetype=True)
            if not a.units or not b.units:
                continue
            appearances[fa] += 1
            appearances[fb] += 1
            Battle(a, b, map_=_pick_rotation_map(seed)).run()

    print("=== per-faction OC-contest winnable-boost (normalized per game) ===")
    print(f"{'faction':24} {'winnable/g':>11} {'unwin/g':>9} {'already/g':>10}")
    rows = []
    for fac, d in strategy.CONTEST_STATS.items():
        g = max(1, appearances.get(fac, 1))
        rows.append((d["winnable"] / g, fac, d, g))
    for w_per_g, fac, d, g in sorted(rows, reverse=True):
        print(f"{fac:24} {w_per_g:>11.1f} {d['unwinnable']/g:>9.1f} {d['already']/g:>10.1f}")
    print()
    print("Reading: TSons/EC HIGH but in line with other durable-body armies (DG,")
    print("Sororitas, Tyranids) = faithful body-army reward (over-shoot is a separate")
    print("residual). TSons/EC clear outliers above comparable armies = contest over-helps.")


if __name__ == "__main__":
    main()
