"""OC-FLIP over-hold instrument (#79, wave 192).

Quantifies the watchdog's over-pole hypothesis: the simulator's Imperial /
Chaos Knights over-HOLD objectives because, even when a Knight is chipped into
its Damaged bracket (effective Objective Control drops 10 -> 5 via the wave-191
generalized bracket), the opponent never commits nearby bodies to flip the
marker. We run Knight matchups with the read-only ``SWEG_OCFLIP_INSTR`` hook
(simulator.OCFLIP_STATS) and report, per objective-round:

  held      = a damaged big durable holder (Knight/Titanic, or big VEHICLE/
              MONSTER >= 18 wounds, now in its Damaged bracket) CONTROLS a marker
  flippable = of those, how many the opponent COULD flip with bodies within
              one Normal Move of the marker (their reachable OC > the holder's
              effective on-marker OC) but did not
  surplus   = mean (opponent reachable OC - holder OC) over the flippable cases

A high flippable/held ratio means the over-hold is an AI-not-contesting gap the
OC-flip lever can close; a low ratio means the over-hold is something else.

Run with: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_ocflip
"""
from __future__ import annotations

import os
import random

os.environ["SWEG_OCFLIP_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code import simulator
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

KNIGHTS = ["Imperial Knights", "Chaos Knights"]
OPPONENTS = [
    "Astra Militarum", "Adeptus Mechanicus", "Necrons", "Tyranids",
    "Adeptus Astartes", "Orks", "Chaos Space Marines", "Aeldari",
]
SEEDS = list(range(1, 6))


def run_pair(knight_fac: str, opp_fac: str, knight_side: str, seed: int) -> None:
    a_fac = knight_fac if knight_side == "A" else opp_fac
    b_fac = opp_fac if knight_side == "A" else knight_fac
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    Battle(a, b, map_=_pick_rotation_map(seed)).run()


def main() -> None:
    simulator.OCFLIP_STATS.update(held=0, flippable=0, surplus=0.0,
                                  held_any=0, flippable_any=0)
    games = 0
    for kf in KNIGHTS:
        for opp in OPPONENTS:
            for seed in SEEDS:
                for side in ("A", "B"):
                    run_pair(kf, opp, side, seed)
                    games += 1
    s = simulator.OCFLIP_STATS
    held_any, flip_any = s["held_any"], s["flippable_any"]
    held, flip = s["held"], s["flippable"]
    print("=== OC-FLIP over-hold instrument (Knight matchups) ===")
    print(f"games:                                          {games}")
    print("BROAD — any big durable holder (Knight/Titanic, full OR damaged):")
    print(f"  obj-rounds it CONTROLS a marker:              {held_any}")
    if held_any:
        print(f"  of those, opponent COULD flip with nearby OC: {flip_any}  ({100*flip_any/held_any:.0f}%)")
    print("NARROW — only when that holder is in its DAMAGED bracket (eff OC < base):")
    print(f"  obj-rounds held:                              {held}")
    if held:
        print(f"  of those, opponent COULD flip:                {flip}  ({100*flip/held:.0f}%)")
        if flip:
            print(f"  mean opponent OC surplus when flippable:      {s['surplus']/flip:.1f}")
    print()
    print("Reading: high BROAD flippable% = the over-hold is a GENERAL AI-not-")
    print("contesting gap; the damaged NARROW slice is the part the OC-flip lever's")
    print("damage-trigger specifically targets. Compare the two to size the lever.")


if __name__ == "__main__":
    main()
