"""Coarse integer-inch grid A* pathfinder for big-base movement (avenue-2).

docs/PATHFINDING_PLAN.md Stage 1. This module is the CORE search only — it is
imported by `simulator._move_toward` at Stage 2 but, on its own, changes nothing
(no caller wired here). It imports ONLY `code.map` so there is no import cycle with
the simulator.

WHY THIS EXISTS: board-wide no-overlap collision crashed big-base (170mm Knight)
reach 62% -> 16% because the deployed local 6-angle sidestep (`_move_toward`) dead-ends
against a wall of blockers (screen + ruins). A coarse grid A* searches the connected
free space and routes a multi-cell detour, restoring reach while keeping the move legal.

PERF (Stage-0 spike): at a 3" cell the per-call cost is ~0.32 ms (39 expansions on a
boxed-in Knight, path found); the pathfinder REPLACES the sidestep so the net add is
~break-even. Containment: COARSE cells (3-4", not 1-2"), a bounded window
(move + slack around start/goal), and a hard expansion cap → graceful, never hangs.

DETERMINISM: zero RNG; the A* frontier tie-breaks on `(f, g, cell_index)` via heapq;
neighbours are visited in a fixed order. Identical inputs → identical output under
PYTHONHASHSEED=0. This is required so the gated A/B stays reproducible.
"""
from __future__ import annotations

import heapq
import math
from typing import List, Optional, Sequence, Tuple

from .map import Map, Wall

Point = Tuple[float, float]
# An occupant is (x, y, footprint_radius, is_enemy) — the same shape the collision
# helper passes; is_enemy is unused by the geometry (every body is an obstacle to
# route around) but kept so the caller can pass its list verbatim.
Occupant = Tuple[float, float, float, bool]

# Stage-0 spike picked these: a 3" cell keeps per-call cost low while still finding the
# detour; the cap bounds the worst case (boxed-in Knight) so a call never hangs.
_DEFAULT_CELL = 3.0
_DEFAULT_SLACK = 3.0
_DEFAULT_MAX_EXPANSIONS = 250
# 8-connected neighbour offsets in a FIXED order (determinism — no set iteration).
_NEIGHBOURS = (
    (-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1),
)
_SQRT2 = math.sqrt(2.0)


def _point_segment_dist2(px: float, py: float, wall: Wall) -> float:
    """Squared distance from point (px, py) to the wall line segment."""
    x1, y1, x2, y2 = wall.x1, wall.y1, wall.x2, wall.y2
    dx, dy = x2 - x1, y2 - y1
    seg2 = dx * dx + dy * dy
    if seg2 <= 1e-12:
        return (px - x1) ** 2 + (py - y1) ** 2
    t = ((px - x1) * dx + (py - y1) * dy) / seg2
    t = max(0.0, min(1.0, t))
    cx, cy = x1 + t * dx, y1 + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def find_path(
    start: Point,
    goal: Point,
    max_dist: float,
    mover_radius: float,
    occupants: Optional[Sequence[Occupant]],
    walls: Sequence[Wall] = (),
    map_: Optional[Map] = None,
    cell_size: float = _DEFAULT_CELL,
    slack: float = _DEFAULT_SLACK,
    max_expansions: int = _DEFAULT_MAX_EXPANSIONS,
) -> Point:
    """Return the furthest point toward `goal` reachable from `start` within
    `max_dist` inches, routing a big mover (footprint `mover_radius`) around
    `occupants` (config-space: each inflated by `mover_radius`), `walls`
    (a non-INFANTRY mover cannot cross — the caller decides who passes that in),
    and `map_` impassable terrain.

    Config-space A* on a coarse grid bounded to a window around start/goal. On a
    boxed-in mover (cap hit / no path) returns the best partial progress point;
    if no candidate is strictly closer to goal than `start`, returns `start`
    unchanged (never oscillates, never returns an illegal/None point).
    """
    sx, sy = start
    gx, gy = goal
    if not occupants and not walls:
        # Nothing to route around — caller should not have invoked us, but be safe:
        # straight clamp toward goal.
        return _clamp_toward(start, goal, max_dist)

    # --- window bounds (clamped to map if provided) -------------------------
    pad = max_dist + slack + mover_radius
    minx = min(sx, gx) - pad
    maxx = max(sx, gx) + pad
    miny = min(sy, gy) - pad
    maxy = max(sy, gy) + pad
    if map_ is not None:
        minx = max(0.0, minx)
        miny = max(0.0, miny)
        maxx = min(map_.width, maxx)
        maxy = min(map_.height, maxy)
    nx = max(1, int((maxx - minx) / cell_size) + 1)
    ny = max(1, int((maxy - miny) / cell_size) + 1)

    def center(cx: int, cy: int) -> Point:
        return (minx + (cx + 0.5) * cell_size, miny + (cy + 0.5) * cell_size)

    def cell_of(p: Point) -> Tuple[int, int]:
        cx = int((p[0] - minx) / cell_size)
        cy = int((p[1] - miny) / cell_size)
        return (max(0, min(nx - 1, cx)), max(0, min(ny - 1, cy)))

    sc = cell_of(start)
    gc = cell_of(goal)

    # --- blocked-cell set (config-space) ------------------------------------
    blocked = set()
    if occupants:
        for (ox, oy, orad, _enemy) in occupants:
            rr = orad + mover_radius
            c0x = int((ox - rr - minx) / cell_size)
            c1x = int((ox + rr - minx) / cell_size)
            c0y = int((oy - rr - miny) / cell_size)
            c1y = int((oy + rr - miny) / cell_size)
            rr2 = rr * rr
            for cx in range(max(0, c0x), min(nx, c1x + 1)):
                for cy in range(max(0, c0y), min(ny, c1y + 1)):
                    px, py = center(cx, cy)
                    if (px - ox) ** 2 + (py - oy) ** 2 <= rr2:
                        blocked.add((cx, cy))
    if walls:
        mr2 = mover_radius * mover_radius
        for cx in range(nx):
            for cy in range(ny):
                if (cx, cy) in blocked:
                    continue
                px, py = center(cx, cy)
                for w in walls:
                    if _point_segment_dist2(px, py, w) <= mr2:
                        blocked.add((cx, cy))
                        break
    if map_ is not None:
        for cx in range(nx):
            for cy in range(ny):
                if (cx, cy) in blocked:
                    continue
                if map_.is_blocked(center(cx, cy)):
                    blocked.add((cx, cy))
    # The mover stands legally at start now, so never treat the start cell as
    # blocked (a rounding artifact must not trap it).
    blocked.discard(sc)

    if sc == gc:
        return _clamp_toward(start, goal, max_dist)

    # --- A* (deterministic) -------------------------------------------------
    def h(cx: int, cy: int) -> float:
        return math.hypot(cx - gc[0], cy - gc[1]) * cell_size

    came: dict = {}
    gscore = {sc: 0.0}
    start_idx = sc[0] * 100003 + sc[1]
    openh: List[Tuple[float, float, int, Tuple[int, int]]] = [
        (h(*sc), 0.0, start_idx, sc)
    ]
    closed = set()
    expansions = 0
    reached = sc
    best_h = h(*sc)
    best_cell = sc
    while openh and expansions < max_expansions:
        f, g, _idx, cur = heapq.heappop(openh)
        if cur in closed:
            continue
        closed.add(cur)
        expansions += 1
        ch = h(*cur)
        if ch < best_h:
            best_h = ch
            best_cell = cur
        if cur == gc:
            reached = gc
            break
        cx, cy = cur
        for dx, dy in _NEIGHBOURS:
            nc = (cx + dx, cy + dy)
            if not (0 <= nc[0] < nx and 0 <= nc[1] < ny):
                continue
            if nc in blocked or nc in closed:
                continue
            step = cell_size * (_SQRT2 if dx and dy else 1.0)
            ng = g + step
            if ng < gscore.get(nc, 1e18):
                gscore[nc] = ng
                came[nc] = cur
                heapq.heappush(
                    openh, (ng + h(*nc), ng, nc[0] * 100003 + nc[1], nc)
                )
    else:
        reached = best_cell
    if reached == sc:
        reached = best_cell

    # --- reconstruct cell path, walk it out to max_dist ---------------------
    cells: List[Tuple[int, int]] = [reached]
    node = reached
    guard = 0
    while node in came and guard < nx * ny:
        node = came[node]
        cells.append(node)
        guard += 1
    cells.reverse()  # start ... reached
    # World points: exact start, then cell centers.
    pts: List[Point] = [start]
    for c in cells[1:]:
        pts.append(center(*c))
    return _walk_path(pts, start, goal, max_dist)


def _walk_path(pts: Sequence[Point], start: Point, goal: Point, max_dist: float) -> Point:
    """Advance along the poly-line `pts` from `start`, stopping at `max_dist`
    inches of travel; return that point. Oscillation guard: if it is not
    strictly closer to `goal` than `start`, return `start` unchanged."""
    budget = max_dist
    cur = start
    result = start
    for nxt in pts[1:]:
        seg = math.hypot(nxt[0] - cur[0], nxt[1] - cur[1])
        if seg <= 1e-9:
            continue
        if seg <= budget:
            result = nxt
            budget -= seg
            cur = nxt
        else:
            frac = budget / seg
            result = (cur[0] + (nxt[0] - cur[0]) * frac,
                      cur[1] + (nxt[1] - cur[1]) * frac)
            cur = result
            budget = 0.0
            break
    # Never return a point further from goal than start (no ping-pong).
    d_start = (start[0] - goal[0]) ** 2 + (start[1] - goal[1]) ** 2
    d_res = (result[0] - goal[0]) ** 2 + (result[1] - goal[1]) ** 2
    if d_res >= d_start:
        return start
    return result


def _clamp_toward(start: Point, goal: Point, max_dist: float) -> Point:
    """Straight move from start toward goal, capped at max_dist."""
    dx, dy = goal[0] - start[0], goal[1] - start[1]
    dist = math.hypot(dx, dy)
    if dist <= max_dist or dist == 0.0:
        return goal
    scale = max_dist / dist
    return (start[0] + dx * scale, start[1] + dy * scale)
