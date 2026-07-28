"""Paired A/B: does AM do BETTER vs a GUNLINE with the adopted holds OFF?
Hypothesis from the board read: ADVANCE_DISCIPLINE / fire-support-hold /
artillery-hold keep AM parked in its corner, which helps vs melee over-poles
(they come to you) but may HURT vs a gunline (Astartes/GSC) where AM must move
onto the midfield to score. Faithful winner determination (matches the anchor).
Paired on seed (deterministic), so effect = win-flips.

Run: PYTHONHASHSEED=0 python -m scripts._am_holds_ab <N> "<over>"
"""
from __future__ import annotations
import os, sys, random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

HOLD_GATES = ["SWEG_AM_ADVANCE_DISCIPLINE", "SWEG_AM_FIRE_SUPPORT_HOLD",
              "SWEG_ARTILLERY_HOLD", "SWEG_AM_STAGING"]


def winner(under, over, seed, off_gates):
    for g in HOLD_GATES:
        os.environ[g] = "0" if g in off_gates else "1"
    random.seed(seed)
    a = build_faction_random_army("A", under, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", over, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    res = Battle(a, b, map_=_pick_rotation_map(seed),
                 primary_mission=_pick_primary_mission(seed)).run()
    return res.winner, res.a_vp, res.b_vp


def arm(under, over, seeds, off_gates):
    return {s: winner(under, over, s, off_gates) for s in seeds}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    over = sys.argv[2] if len(sys.argv) > 2 else "Adeptus Astartes"
    under = "Astra Militarum"
    seeds = list(range(n))
    configs = [
        ("baseline (all holds ON)", set()),
        ("advance_discipline OFF",  {"SWEG_AM_ADVANCE_DISCIPLINE"}),
        ("all 3 holds OFF",         {"SWEG_AM_ADVANCE_DISCIPLINE", "SWEG_AM_FIRE_SUPPORT_HOLD", "SWEG_ARTILLERY_HOLD"}),
        ("holds+staging OFF",       set(HOLD_GATES)),
    ]
    base = arm(under, over, seeds, set())
    bw = sum(1 for s in seeds if base[s][0] == "A")
    print(f"# AM vs {over}  N={n}   (paired, faithful winner)")
    print(f"{'config':28} {'Awin%':>6} {'Δpp':>5} {'L>W':>4} {'W>L':>4} {'meanVP_A':>8}")
    for name, off in configs:
        w = base if not off else arm(under, over, seeds, off)
        aw = sum(1 for s in seeds if w[s][0] == "A")
        lw = sum(1 for s in seeds if base[s][0] != "A" and w[s][0] == "A")
        wl = sum(1 for s in seeds if base[s][0] == "A" and w[s][0] != "A")
        avp = sum(w[s][1] for s in seeds) / n
        print(f"{name:28} {100*aw/n:6.1f} {100*(aw-bw)/n:+5.1f} {lw:4d} {wl:4d} {avp:8.1f}")
    # reset
    for g in HOLD_GATES:
        os.environ[g] = "1"


if __name__ == "__main__":
    main()
