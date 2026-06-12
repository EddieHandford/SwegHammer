"""PATHFINDING Stage-0 GO/NO-GO spike (read-only; docs/PATHFINDING_PLAN.md).

Produces two of the three Stage-0 numbers (the third, Knight-reach% ~62% OFF, comes
from diag_entrench.py):

  2. BLOCKED-MOVE FREQUENCY — under SWEG_COLLISION, how often a move's straight end is
     blocked (the case a pathfinder must route around), split big-base vs small-base.
     Read from simulator.PATHFIND_STAGE0_STATS after a Knight-vs-body sample.
  3. PER-CALL COARSE-A* COST — a THROWAWAY prototype of the planned coarse integer-inch
     grid A* (8-connected, config-space, bounded), timed over 1000 calls on a boxed-in
     Knight. This is NOT the real module (that is Stage 1) — only a cost probe.

GO/NO-GO (note B): blocked-big-move frequency x per-call A* cost must fit the <=1.5x
perf budget, else board-wide collision-via-pathfinding is infeasible for the loop.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_pathfind_stage0
"""
from __future__ import annotations

import heapq
import os
import random
import time

# Activate collision (so occupants are passed -> the move walk-back path runs) and the
# Stage-0 counter, BEFORE importing the simulator. Read per-call from os.environ.
os.environ["SWEG_COLLISION"] = "1"
os.environ["SWEG_MOVEPLAN"] = "1"
os.environ["SWEG_PATHFIND_STAGE0"] = "1"

from code import simulator
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

OPPONENTS = ["Astra Militarum", "Adeptus Mechanicus", "Tyranids", "Orks"]
SEEDS = list(range(1, 6))


def measure_blocked_frequency() -> None:
    simulator.PATHFIND_STAGE0_STATS.update(
        total_big=0, blocked_big=0, total_small=0, blocked_small=0)
    games = 0
    for opp in OPPONENTS:
        for seed in SEEDS:
            for side in ("A", "B"):
                af = "Imperial Knights" if side == "A" else opp
                bf = opp if side == "A" else "Imperial Knights"
                a = build_faction_random_army("A", af, 2000, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", bf, 2000, rng=random.Random(seed + 99), use_archetype=True)
                if not a.units or not b.units:
                    continue
                Battle(a, b, map_=_pick_rotation_map(seed)).run()
                games += 1
    s = simulator.PATHFIND_STAGE0_STATS
    tb, bb = s["total_big"], s["blocked_big"]
    ts, bs = s["total_small"], s["blocked_small"]
    print("=== NUMBER 2 — blocked-move frequency (collision ON, Knight vs body) ===")
    print(f"  games sampled:                     {games}")
    print(f"  BIG-base moves:    total {tb:7d}   blocked {bb:7d}   ({100*bb/max(1,tb):.1f}%)")
    print(f"  small-base moves:  total {ts:7d}   blocked {bs:7d}   ({100*bs/max(1,ts):.1f}%)")
    print(f"  big blocked-moves PER GAME:        {bb/max(1,games):.1f}   <-- the A*-call frequency")
    return games, bb


# --------------------------------------------------------------------------
# NUMBER 3 — throwaway coarse-grid A* prototype + per-call timing
# --------------------------------------------------------------------------
def coarse_astar(start, goal, max_dist, mover_radius, occupants,
                 cell=2.0, slack=3.0, cap=400):
    """Prototype of the planned coarse integer-inch grid A* (NOT the real module).
    Config-space: occupants inflated by mover_radius so the mover is a point.
    8-connected, Euclidean heuristic, deterministic (f, g, cell_index), capped."""
    minx = min(start[0], goal[0]) - (max_dist + slack)
    maxx = max(start[0], goal[0]) + (max_dist + slack)
    miny = min(start[1], goal[1]) - (max_dist + slack)
    maxy = max(start[1], goal[1]) + (max_dist + slack)
    nx = max(1, int((maxx - minx) / cell) + 1)
    ny = max(1, int((maxy - miny) / cell) + 1)

    def center(cx, cy):
        return (minx + (cx + 0.5) * cell, miny + (cy + 0.5) * cell)

    def cell_of(p):
        return (int((p[0] - minx) / cell), int((p[1] - miny) / cell))

    blocked = set()
    for (ox, oy, orad, _e) in occupants:
        rr = orad + mover_radius
        c0x = int((ox - rr - minx) / cell); c1x = int((ox + rr - minx) / cell)
        c0y = int((oy - rr - miny) / cell); c1y = int((oy + rr - miny) / cell)
        for cx in range(max(0, c0x), min(nx, c1x + 1)):
            for cy in range(max(0, c0y), min(ny, c1y + 1)):
                px, py = center(cx, cy)
                if (px - ox) ** 2 + (py - oy) ** 2 <= rr * rr:
                    blocked.add((cx, cy))

    sc, gc = cell_of(start), cell_of(goal)
    openh = [(0.0, 0.0, sc[0] * 100003 + sc[1], sc)]
    closed = set()
    gscore = {sc: 0.0}
    expansions = 0
    found = False
    while openh and expansions < cap:
        f, g, _idx, cur = heapq.heappop(openh)
        if cur in closed:
            continue
        closed.add(cur)
        expansions += 1
        if cur == gc:
            found = True
            break
        cx, cy = cur
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nc = (cx + dx, cy + dy)
                if not (0 <= nc[0] < nx and 0 <= nc[1] < ny):
                    continue
                if nc in blocked or nc in closed:
                    continue
                step = cell * (1.41421356 if dx and dy else 1.0)
                ng = g + step
                if ng < gscore.get(nc, 1e18):
                    gscore[nc] = ng
                    h = ((nc[0] - gc[0]) ** 2 + (nc[1] - gc[1]) ** 2) ** 0.5 * cell
                    heapq.heappush(openh, (ng + h, ng, nc[0] * 100003 + nc[1], nc))
    return expansions, found


def time_astar() -> None:
    # Boxed-in Knight: a 170mm base (~3.3" radius) at (10,12), goal past a screen wall
    # of enemy blockers at x=22 spanning y=4..20, plus a couple of ruin-proxy blocks.
    mover_radius = 3.35
    start, goal, max_dist = (10.0, 12.0), (44.0, 12.0), 12.0
    occupants = []
    for y in range(4, 21):
        occupants.append((22.0, float(y), 0.63, True))   # infantry screen
    occupants += [(30.0, 6.0, 2.0, True), (30.0, 18.0, 2.0, True)]  # ruin-proxy blocks
    # warm up + correctness
    exp, found = coarse_astar(start, goal, max_dist, mover_radius, occupants)
    N = 1000
    t0 = time.perf_counter()
    for _ in range(N):
        coarse_astar(start, goal, max_dist, mover_radius, occupants)
    dt = time.perf_counter() - t0
    print("\n=== NUMBER 3 — per-call coarse-A* cost (throwaway prototype, boxed-in Knight) ===")
    print(f"  scenario: 170mm Knight, 12\" move, 17-model screen + 2 ruin blocks, routed around")
    print(f"  expansions/call: {exp}   path found: {found}")
    print(f"  {N} calls in {dt*1000:.1f} ms  ->  {dt/N*1e6:.1f} us/call  ({dt/N*1000:.3f} ms/call)")
    return dt / N


def main() -> None:
    print("PATHFINDING Stage-0 GO/NO-GO spike\n")
    games, big_blocked = measure_blocked_frequency()
    per_call = time_astar()
    big_per_game = big_blocked / max(1, games)
    print("\n=== GO/NO-GO synthesis ===")
    print(f"  big blocked-moves/game x per-call A* cost = {big_per_game:.1f} x {per_call*1000:.3f} ms"
          f" = {big_per_game*per_call*1000:.2f} ms/game of added A*")
    print("  Compare to baseline ms/game (bench_simulator) — must keep gated-ON <= 1.5x.")
    print("  (Knight-reach% baseline 62% OFF / 16% current-collision from diag_entrench = number 1.)")


if __name__ == "__main__":
    main()
