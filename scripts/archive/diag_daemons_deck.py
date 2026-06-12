"""Localize the per-model Daemons crater by DECK MISSION (verify-before-flip).

The N=80 deck eval craters Daemons (47.5%->34.1%) under SWEG_PERMODEL, but a non-deck
(Take-and-Hold) probe showed Daemons FINE — so the crater is a per-model x deck-mission
interaction. This runs Daemons vs a cross-section on EACH distinct deck mission, OFF vs
ON, to find which mission(s) crater them (and whether it's broad or one-mission).
Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_daemons_deck
"""
from __future__ import annotations
import os, random
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

MISSIONS = ["take_and_hold", "terraform", "purge_the_foe", "scorched_earth", "the_ritual"]
OPP = ["Imperial Knights", "Adeptus Astartes", "Orks", "Tyranids"]
SEEDS = list(range(1, 5))


def winrate(mission, perm):
    if perm:
        os.environ["SWEG_PERMODEL"] = "1"
    else:
        os.environ.pop("SWEG_PERMODEL", None)
    g = w = 0
    for opp in OPP:
        for s in SEEDS:
            for side in ("A", "B"):
                af = "Chaos Daemons" if side == "A" else opp
                bf = opp if side == "A" else "Chaos Daemons"
                a = build_faction_random_army("A", af, 2000, rng=random.Random(s), use_archetype=True)
                b = build_faction_random_army("B", bf, 2000, rng=random.Random(s + 99), use_archetype=True)
                if not a.units or not b.units:
                    continue
                r = Battle(a, b, map_=_pick_rotation_map(s), primary_mission=mission).run()
                g += 1
                if r.winner == ("A" if side == "A" else "B"):
                    w += 1
    return 100.0 * w / max(1, g), g


def main():
    print("=== Daemons crater by DECK MISSION (OFF vs ON SWEG_PERMODEL) ===")
    print(f"{'mission':16s} {'OFF win%':>9s} {'ON win%':>9s} {'delta':>7s}")
    for m in MISSIONS:
        off, _ = winrate(m, False)
        on, g = winrate(m, True)
        print(f"{m:16s} {off:9.0f} {on:9.0f} {on-off:+7.0f}   (n={g}/side)")
    print("\nReading: the mission(s) with a big NEGATIVE delta localize the per-model x")
    print("deck interaction; a broad negative = systemic; one mission = that scorer's bug.")


if __name__ == "__main__":
    main()
