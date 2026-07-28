"""Deployment-spread diagnostic — does the AI deploy clustered or wide, and does
it differ by army shape (go-wide horde vs go-tall elite)? Read-only.

For each faction vs a fixed opponent, capture the BattleStarted (post-deployment)
positions of the army's on-board units and report the X-spread (how much of the
board width it covers), the depth, and the number of distinct squad clusters.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_deploy
"""
from __future__ import annotations

import random

from code.army_builder import build_faction_random_army
from code.events import BattleStarted, EventLog
from code.simulator import Battle
from code.renderer import aggregate_activations, render_frame
from scripts.evaluate_vs_meta import _pick_rotation_map


def render_deploy(fac, opp, seed=0, path=None):
    """Save a render of `fac`'s DEPLOYMENT (BattleStarted positions, no movement)."""
    a = build_faction_random_army("A", fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    Battle(a, b, subscribers=[log], map_=map_).run()
    ev = log.events
    bs_idx = next(i for i, e in enumerate(ev) if isinstance(e, BattleStarted))
    deploy_ev = ev[:bs_idx + 1]                     # truncate: deployment only, no moves
    frames = aggregate_activations(deploy_ev)
    img = render_frame(map_, deploy_ev, frame=0, frames=frames)
    path = path or f"data/_deploy_{fac.split()[0].lower()}_v_{opp.split()[0].lower()}.png"
    img.save(path)
    return path

OPP = "Imperial Knights"
FACTIONS = [
    "Astra Militarum", "Tyranids", "Orks",            # go-wide hordes
    "Imperial Knights", "Adeptus Custodes",           # go-tall elites
    "T'au Empire", "Drukhari",                        # gunline / mobile
]


def _deploy(fac, seed=0):
    a = build_faction_random_army("A", fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", OPP if fac != OPP else "Astra Militarum", 2000,
                                  rng=random.Random(seed + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    Battle(a, b, subscribers=[log], map_=map_).run()
    bs = next(e for e in log.events if isinstance(e, BattleStarted))
    xs, ys, squads = [], [], set()
    for u in bs.units:
        if u.army != "A" or u.position[0] <= -50:   # skip reserves (off-board sentinel)
            continue
        xs.append(u.position[0])
        ys.append(u.position[1])
    return map_, xs, ys


def main():
    print(f"# Deployment spread (army A on-board units at BattleStarted, vs {OPP})")
    print(f"{'faction':20} {'board':>9} {'n':>4} {'x-range':>14} {'%width':>7} "
          f"{'y-rows(depth)':>16}")
    print("-" * 78)
    for fac in FACTIONS:
        map_, xs, ys = _deploy(fac)
        if not xs:
            print(f"{fac:20}  (all reserves?)")
            continue
        xr = max(xs) - min(xs)
        # distinct deployment rows = distinct rounded y values (screen line / back line)
        rows = sorted({round(y, 1) for y in ys})
        rowstr = "/".join(f"{r:.0f}" for r in rows[:4])
        print(f"{fac:20} {map_.width:.0f}x{map_.height:.0f}  {len(xs):>4} "
              f"[{min(xs):.0f},{max(xs):.0f}]={xr:>4.0f} {100*xr/map_.width:>6.0f}% "
              f"y={rowstr:>14}")
    print("-" * 78)
    print("x-range ~full width => deployed WIDE; small => CLUSTERED.")
    print("y-rows = number of depth lines (screen + back under SWEG_DEPLOY).")
    p1 = render_deploy("Astra Militarum", "Imperial Knights")
    p2 = render_deploy("Imperial Knights", "Astra Militarum")
    print(f"renders: {p1} , {p2}")


if __name__ == "__main__":
    main()
