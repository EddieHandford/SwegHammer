"""Pure geometry helpers for the battle simulator.

Extracted verbatim from ``code/simulator.py`` by pure code motion (Stage A of
``docs/SIM_MODULARIZATION_PLAN.md``). Every helper here is free of ``Battle``
instance state: they take positions, a map, and an occupant list as plain
arguments. ``code/simulator.py`` re-imports these names so its public surface
is unchanged (tests and the melee / collision diagnostics import ``_distance``,
``_move_toward``, ``_OccupantGrid``, ``_collision_pos_legal`` and
``_enemy_path_cap_t`` from ``code.simulator``).

Dependencies: ``Map`` from ``code.map`` and ``find_path`` from ``code.pathfind``
(both already external to the simulator), plus the pathfinding threshold and the
two instrument dictionaries that ``_move_toward`` reads and mutates, imported
from ``code.sim.constants`` (the same shared objects the diagnostics reset).
"""

from __future__ import annotations

from typing import Tuple

from ..map import Map
from ..pathfind import find_path
from .constants import (
    _PATHFIND_BIG_RADIUS_IN,
    PATHFIND_STAGE0_STATS,
    REACH_STATS,
)


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class _OccupantGrid:
    """Per-mover spatial hash over the collision occupant list (avenue-2 Stage 2,
    docs/PATHFINDING_PLAN.md). Buckets `(x, y, radius, is_enemy)` occupants by a coarse
    cell so a legality query touches only the handful of occupants NEAR the test point
    instead of the whole list — turning the O(models) `_collision_pos_legal` inner loop
    (run ~18x per blocked move by the sidestep, the O(models^2) dense-horde cost) into
    O(local).

    The legality result is BYTE-IDENTICAL to iterating the full list: a model further
    than `mover_radius + max_orad + 1"` in centre-distance can never overlap or be within
    Engagement Range, and `near()` is built to include every occupant within that reach.
    So the grid is a pure speedup — no behaviour change, gated for measurement only.

    DETERMINISM: `near()` walks buckets in fixed (cx, cy) order and within a bucket in
    INSERTION order (the original occupant order, which the caller builds in a fixed
    (friendly-then-enemy, alive_units) order). The grid is also fully list-compatible
    (`__iter__`/`__len__`/`__bool__`/`__getitem__` over the original ordered list) so any
    order-dependent consumer (make-way / clear-lane) that iterates it sees the unchanged
    order."""

    __slots__ = ("cell", "buckets", "max_orad", "_list")

    def __init__(self, occupants, cell: float = 8.0):
        self.cell = cell
        self.buckets: dict = {}
        self.max_orad = 0.0
        self._list = occupants
        for occ in occupants:
            ox, oy, orad = occ[0], occ[1], occ[2]
            if orad > self.max_orad:
                self.max_orad = orad
            key = (int(ox // cell), int(oy // cell))
            b = self.buckets.get(key)
            if b is None:
                self.buckets[key] = [occ]
            else:
                b.append(occ)

    def near(self, pos, mover_radius: float):
        """Occupants whose bucket lies within the max interaction reach of `pos`."""
        reach = mover_radius + self.max_orad + 1.0
        c = self.cell
        cx0 = int((pos[0] - reach) // c)
        cx1 = int((pos[0] + reach) // c)
        cy0 = int((pos[1] - reach) // c)
        cy1 = int((pos[1] + reach) // c)
        out = []
        buckets = self.buckets
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                b = buckets.get((cx, cy))
                if b:
                    out.extend(b)
        return out

    def __iter__(self):
        return iter(self._list)

    def __len__(self):
        return len(self._list)

    def __bool__(self):
        return bool(self._list)

    def __getitem__(self, i):
        return self._list[i]


def _collision_pos_legal(pos, mover_radius, occupants, mover_fly) -> bool:
    """Avenue-2 Stage 1 (no-overlap collision): is `pos` a legal END position for a
    mover of footprint `mover_radius` (inches), given `occupants` — a list (or
    `_OccupantGrid`) of (x, y, radius, is_enemy) for every OTHER alive model? Real 10e:
    a model cannot END a move overlapping another model, nor (for non-FLY) within
    Engagement Range (1") of an enemy. FLY ends are exempt from the enemy/ER test (it
    flew over). Pure + deterministic. Only consulted when collision is wired ON by a
    caller. When `occupants` is an `_OccupantGrid`, only the occupants NEAR `pos` are
    tested (identical result, O(local) instead of O(models))."""
    if type(occupants) is _OccupantGrid:
        occupants = occupants.near(pos, mover_radius)
    for ox, oy, orad, is_enemy in occupants:
        d2 = (pos[0] - ox) ** 2 + (pos[1] - oy) ** 2
        # No model may END overlapping another model's base (applies to FLY too).
        if d2 < (mover_radius + orad) ** 2:
            return False
        # Non-FLY may not end within Engagement Range (1") of an enemy base.
        if is_enemy and not mover_fly and d2 < (mover_radius + orad + 1.0) ** 2:
            return False
    return True


def _enemy_path_cap_t(start, end, mover_radius, occupants, mover_fly) -> float:
    """Avenue-2 collision: the furthest fraction t in [0, 1] of the segment
    start->end a NON-FLY mover (footprint `mover_radius` inches) may travel before
    any part of its base would cross an ENEMY model's base.

    Real 10e (cited simulator.collision_friendly_passthrough): a model "can be
    moved through friendly models, but it cannot end its move on top of another
    model", and "no part of its base can be moved through an enemy model". So
    FRIENDLIES never cap the PATH (only the END is constrained, in
    _collision_pos_legal) and an ENEMY base on the path stops a non-FLY mover at
    its near boundary (faithful screening). FLY moves OVER enemy models -> never
    path-capped (returns 1.0). Returns 1.0 when nothing caps the path. Pure +
    deterministic; iterates occupants in list order (no set/id ordering)."""
    if mover_fly:
        return 1.0
    occ_iter = occupants._list if type(occupants) is _OccupantGrid else occupants
    sx, sy = start
    ex, ey = end
    vx, vy = ex - sx, ey - sy
    seg2 = vx * vx + vy * vy
    if seg2 == 0.0:
        return 1.0
    # Perf bbox-cull: precompute the segment's axis-aligned bounds. An enemy whose
    # centre lies outside this box expanded by the contact radius rr cannot reach the
    # path, so the (expensive) quadratic is skipped for it. Exact — the bbox+rr is a
    # conservative superset of the real intersection region, so an intersecting enemy
    # is never wrongly skipped and the returned cap is byte-identical to the full scan.
    minx, maxx = (sx, ex) if sx <= ex else (ex, sx)
    miny, maxy = (sy, ey) if sy <= ey else (ey, sy)
    cap = 1.0
    for ox, oy, orad, is_enemy in occ_iter:
        if not is_enemy:
            continue
        rr = mover_radius + orad
        if ox < minx - rr or ox > maxx + rr or oy < miny - rr or oy > maxy + rr:
            continue   # centre outside segment bbox + rr → cannot intersect the path
        # First crossing t of the segment with the circle (centre o, radius rr):
        # |start + t*v - o|^2 = rr^2 -> seg2*t^2 + b*t + c = 0, take the lesser root.
        wx, wy = sx - ox, sy - oy
        b = 2.0 * (wx * vx + wy * vy)
        c = wx * wx + wy * wy - rr * rr
        disc = b * b - 4.0 * seg2 * c
        if disc < 0.0:
            continue   # the segment never reaches this enemy's base
        t_entry = (-b - disc ** 0.5) / (2.0 * seg2)
        if t_entry <= 0.0:
            # Already touching this enemy at start (start is assumed legal, so this
            # is a numerical edge) -> no legal forward travel past it.
            return 0.0
        if t_entry < cap:
            cap = t_entry
    return cap


def _fan_to_goal(start, goal, max_dist, mover_radius, occupants, mover_fly, map_, best):
    """Open-blocked reach recovery (wave 211, gated SWEG_REACH_FIX). A BIG mover whose
    straight end was blocked by a FRIENDLY/terrain (the caller gates this to cap_t>=1,
    i.e. NO enemy on the straight path) and whose pathfinder could not place its base
    near the goal: fan a ring of positions AROUND the goal and take the legal one
    CLOSEST to goal the mover can REACH this move without crossing an enemy.

    The per-candidate `_enemy_path_cap_t >= 1` check is the screening guardrail: a
    FULLY enemy-screened goal yields NO admissible candidate (every approach crosses an
    enemy), so this can never let a mover bypass a screen — the IK over-pole stays
    intact. Only ever IMPROVES on `best` (takes a candidate strictly closer to goal).
    Deterministic: fixed ring + 30°-step angle order, no RNG."""
    import math as _m
    sx, sy = start
    gx, gy = goal
    md2 = max_dist * max_dist
    best_d2 = (best[0] - gx) ** 2 + (best[1] - gy) ** 2
    for ring in (mover_radius + 0.5, mover_radius + 2.0, 3.5, 6.0):
        for k in range(12):
            ang = _m.radians(k * 30.0)
            cx = max(0.0, min(map_.width, gx + ring * _m.cos(ang)))
            cy = max(0.0, min(map_.height, gy + ring * _m.sin(ang)))
            d2 = (cx - gx) ** 2 + (cy - gy) ** 2
            if d2 >= best_d2:
                continue                                  # not closer to goal
            if (cx - sx) ** 2 + (cy - sy) ** 2 > md2:
                continue                                  # out of this move's reach
            if map_.is_blocked((cx, cy)):
                continue
            if _enemy_path_cap_t(start, (cx, cy), mover_radius, occupants, mover_fly) < 1.0:
                continue                                  # path crosses an enemy → screened, skip
            if not _collision_pos_legal((cx, cy), mover_radius, occupants, mover_fly):
                continue                                  # would end on a model
            best = (cx, cy)
            best_d2 = d2
    return best


def _move_toward(
    start: Tuple[float, float],
    goal: Tuple[float, float],
    max_dist: float,
    map_: Map,
    mover_radius: float = 0.0,
    occupants=None,
    mover_fly: bool = False,
    sidestep: bool = True,
) -> Tuple[float, float]:
    """Move from start toward goal up to max_dist inches.

    Clamps to map bounds. If the destination point lies inside impassable
    terrain, the move is aborted and the unit stays put — crude but enough
    for Phase A.

    Avenue-2 Stage 1 no-overlap collision (default-OFF / byte-identical): when
    `occupants` is None (every caller today, and whenever SWEG_COLLISION is off) the
    function behaves exactly as before. When a caller passes the per-phase occupant
    list (other alive models as (x, y, radius, is_enemy)) plus the mover's footprint
    radius, the END position is validated against `_collision_pos_legal`; if illegal,
    the destination is walked back toward `start` by deterministic bisection (capped
    iterations) to the last legal point. `start` is assumed legal (the mover is there
    now). FLY skips the enemy/Engagement-Range test (handled in the helper)."""
    dx = goal[0] - start[0]
    dy = goal[1] - start[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist == 0 or dist <= max_dist:
        new = goal
    else:
        scale = max_dist / dist
        new = (start[0] + dx * scale, start[1] + dy * scale)
    new_x = max(0.0, min(map_.width, new[0]))
    new_y = max(0.0, min(map_.height, new[1]))
    new_point = (new_x, new_y)
    if map_.is_blocked(new_point):
        return start
    if occupants is None:
        return new_point
    # Collision ON. Faithful 10e movement vs other models (cited
    # simulator.collision_friendly_passthrough): a model "can be moved through
    # friendly models, but it cannot end its move on top of another model", and
    # "no part of its base can be moved through an enemy model" (FLY moves over
    # enemies). So FRIENDLIES never block the PATH — they are passed through, only
    # the END must be clear of every model (+ enemy Engagement Range); an ENEMY
    # base on the straight path CAPS how far a non-FLY mover travels (faithful
    # screening — a Knight cannot pass through an enemy horde).
    cap_t = _enemy_path_cap_t(start, new_point, mover_radius, occupants, mover_fly)
    straight_legal = (
        cap_t >= 1.0
        and _collision_pos_legal(new_point, mover_radius, occupants, mover_fly)
    )
    # PATHFINDING Stage-0 GO/NO-GO counter (read-only, gated). Records how often the
    # straight end is blocked (now: enemy-capped path OR an illegal end) — the
    # blocked-move frequency that, times the per-call A* cost, is the perf decision.
    if __import__("os").environ.get("SWEG_PATHFIND_STAGE0"):
        _big = mover_radius >= _PATHFIND_BIG_RADIUS_IN
        PATHFIND_STAGE0_STATS["total_big" if _big else "total_small"] += 1
        if not straight_legal:
            PATHFIND_STAGE0_STATS["blocked_big" if _big else "blocked_small"] += 1
    # Reach instrument (read-only): classify big-mover blocks as faithful enemy
    # screening (cap_t<1) vs open-space artifact (cap_t>=1 but end illegal).
    if __import__("os").environ.get("SWEG_REACH_INSTR") and mover_radius >= _PATHFIND_BIG_RADIUS_IN:
        REACH_STATS["big_moves"] += 1
        if straight_legal:
            REACH_STATS["big_reached"] += 1
        elif cap_t < 1.0:
            REACH_STATS["big_enemy_capped"] += 1
        else:
            REACH_STATS["big_open_blocked"] += 1
    if straight_legal:
        return new_point
    # Straight move capped by an enemy and/or its end overlaps a model. Find the
    # furthest LEGAL END at or before the enemy cap, PASSING THROUGH friendlies:
    # scan inward from the capped reach and take the first legal end. A legal end
    # BEYOND a friendly (within the enemy cap) is reached — fixing the self-jam
    # where the old bisection halted the mover at a friendly model's near edge.
    # Deterministic (fixed step order, no RNG).
    import math as _m
    sx, sy = start
    vx, vy = new_point[0] - sx, new_point[1] - sy
    best = start
    _STEPS = 24
    for _i in range(_STEPS, -1, -1):
        t = cap_t * (_i / _STEPS)
        cand = (sx + vx * t, sy + vy * t)
        if not map_.is_blocked(cand) and _collision_pos_legal(cand, mover_radius, occupants, mover_fly):
            best = cand
            break
    # PATHFINDING (avenue-2 Stage 2, gated SWEG_PATHFIND): a BIG mover whose straight
    # end is blocked routes AROUND the obstacle field via coarse grid A* (code/pathfind)
    # instead of the local 6-angle sidestep, which dead-ends against a wall of blockers
    # (screen + ruins) and crashes big-base reach (62%->16%). Big-bases-only; small
    # INFANTRY keep the O(1) sidestep below. The returned furthest-legal point is
    # re-validated exactly (the A* grid is coarse) and falls back to the straight
    # walk-back on the rare coarse-grid miss. OFF (gate unset) -> byte-identical.
    if mover_radius >= _PATHFIND_BIG_RADIUS_IN and __import__("os").environ.get("SWEG_PATHFIND", "1") != "0":
        walls = map_.wall_segments() if map_ is not None else ()
        p = find_path(start, goal, max_dist, mover_radius, occupants, walls=walls, map_=map_)
        if _collision_pos_legal(p, mover_radius, occupants, mover_fly):
            best = p   # pathfinder's furthest legal point (may still strand the base short)
        # Open-blocked reach recovery (gated SWEG_REACH_FIX, default-ON; =0 reverts):
        # ONLY when no enemy capped the straight path (cap_t>=1) — an enemy-capped move
        # (cap_t<1) is faithful screening and is left exactly as-is, so this cannot undo
        # the Knight over-pole fix. Fans a big mover around its own clustered army to a
        # legal spot near the goal it could not stack on (per-candidate enemy-clear).
        if cap_t >= 1.0 and __import__("os").environ.get("SWEG_REACH_FIX", "1") != "0":
            best = _fan_to_goal(start, goal, max_dist, mover_radius, occupants,
                                mover_fly, map_, best)
        return best
    if not sidestep:
        # Big movers (blocker-makes-way model): stop straight at the blocker — an
        # ENEMY blocker SHOULD halt a Knight (faithful screening); friendly blockers
        # are cleared beforehand by _clear_lane. No detour around own army.
        return best
    best_d2 = (best[0] - goal[0]) ** 2 + (best[1] - goal[1]) ** 2
    # (b) angular sidesteps at full reach — step AROUND the blocker. Take the legal
    # candidate closest to goal (most forward progress). Reach capped so a wide angle
    # near the goal does not overshoot.
    reach = min(max_dist, dist)
    base = _m.atan2(goal[1] - sy, goal[0] - sx)
    for deg in (20.0, -20.0, 40.0, -40.0, 60.0, -60.0):
        ang = base + _m.radians(deg)
        cx = max(0.0, min(map_.width, sx + reach * _m.cos(ang)))
        cy = max(0.0, min(map_.height, sy + reach * _m.sin(ang)))
        if map_.is_blocked((cx, cy)):
            continue
        if not _collision_pos_legal((cx, cy), mover_radius, occupants, mover_fly):
            continue
        d2 = (cx - goal[0]) ** 2 + (cy - goal[1]) ** 2
        if d2 < best_d2:
            best = (cx, cy)
            best_d2 = d2
    return best


def _charge_path_screen_gap(charger_pos, end_pos, charger_radius,
                             screen_pos, screen_radius) -> float:
    """Point-to-segment distance from a non-target enemy's centre to the straight
    path from *charger_pos* to *end_pos*, minus both base radii.

    Used by the charge-path legality filter (gate SWEG_CHARGE_PATH): a non-FLY
    charger's move is path-blocked by a screening enemy if this value is < 1.0
    (i.e. any part of the charger's base would pass within Engagement Range of
    the screen's base during the move).  Pure geometry, no RNG.

    The point-to-segment formula clamps the foot of the perpendicular to the
    segment end points so a screen that sits off to one side of the line
    extension is measured correctly to whichever end-point of the path it is
    nearest to.  Pure + deterministic."""
    sx, sy = charger_pos
    ex, ey = end_pos
    ox, oy = screen_pos
    vx, vy = ex - sx, ey - sy
    seg2 = vx * vx + vy * vy
    if seg2 == 0.0:
        # Charger is not moving; use direct centre distance.
        d = ((ox - sx) ** 2 + (oy - sy) ** 2) ** 0.5
    else:
        # t = clamped projection of screen centre onto segment [0,1].
        t = ((ox - sx) * vx + (oy - sy) * vy) / seg2
        t = max(0.0, min(1.0, t))
        px = sx + t * vx
        py = sy + t * vy
        d = ((ox - px) ** 2 + (oy - py) ** 2) ** 0.5
    return d - (charger_radius + screen_radius)


def _er_gap(pos_a, profile_a, pos_b, profile_b) -> float:
    """Engagement-Range distance between two models, in inches.

    Under SWEG_CHARGE_BASEEDGE (default ON since wave 240) this is the
    base-edge GAP — centre distance minus both models' base radii — per the
    10e core rule that Engagement Range, like every distance, is measured
    between the CLOSEST POINTS of the bases (the same measurement the gated
    charge-end placement `_charge_baseedge_end` and the collision predicate
    `_collision_pos_legal` already use). Cited as
    `simulator.engagement_range_base_edge`.

    A tiny epsilon (1e-9) is shaved off the gate-ON result so a charger
    parked at EXACTLY one inch of base-edge gap by `_charge_baseedge_end`
    still counts as engaged despite the cos/sin position-reconstruction
    float error. Gate OFF returns the legacy centre-to-centre distance
    unchanged — every `_er_gap(...) <= threshold` call site is byte-identical
    to its previous `_distance(...) <= threshold` form."""
    d = _distance(pos_a, pos_b)
    if __import__("os").environ.get("SWEG_CHARGE_BASEEDGE", "1") == "1":
        d -= (_bc_model_radius_in(profile_a) + _bc_model_radius_in(profile_b)
              + 1e-9)
    return d


def _bc_model_radius_in(profile) -> float:
    """Base-footprint radius in INCHES for a model (read-only instrument helper).
    NOTE: deliberately NOT lru_cache'd — UnitProfile is a large frozen dataclass
    (carries the model_loadouts tuple), so hashing it per call costs MORE than this
    arithmetic (measured: caching slowed the dense-horde bench). The per-phase occupant
    grid is the right place to avoid the O(models^2) repetition, not a per-call cache.
    25.4 mm/in. CRITICAL: oval/rect bases (Knights, big VEHICLEs) store their real
    footprint in base_width_mm x base_length_mm while base_diameter_mm holds a 32mm
    PLACEHOLDER — so take the LARGER of the circle-derived and the width/length-
    derived radius (a 170mm Knight must not be mis-sized as a 32mm infantry base,
    which 4x-undercounts its footprint area and hides the marker-denial it causes).
    Defaults to ~32mm round (0.63") only if no base data at all."""
    d = getattr(profile, "base_diameter_mm", 0) or 0
    w = getattr(profile, "base_width_mm", 0) or 0
    ln = getattr(profile, "base_length_mm", 0) or 0
    r_circle = (d / 25.4) / 2.0 if d > 0 else 0.0
    r_wl = ((w + ln) / 2.0 / 25.4) / 2.0 if (w and ln) else 0.0
    r = max(r_circle, r_wl)
    return r if r > 0 else 0.63
