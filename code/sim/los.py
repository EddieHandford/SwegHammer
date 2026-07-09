"""Terrain geometry substrate — line of sight + movement wall collision.

This module is the single geometric substrate the terrain-realism gates
(``SWEG_TERRAIN_COLLISION``, ``SWEG_TERRAIN_LOS``) and the future
threat-projection planner (``docs/THREAT_LAYER_PROPOSAL.md`` Stage T4) consult,
so planning and resolution agree on one occlusion geometry. It exposes two
primitives the proposal (``docs/TERRAIN_REALISM_PROPOSAL.md``) names, plus a
clamp helper the movement gate uses:

    has_los(pos_a, pos_b, map_)      -> bool  : is B visible from A?
    path_blocked(pos_a, pos_b, map_) -> bool  : does the straight move A->B cross a wall?
    wall_clamp(pos_a, pos_b, map_)   -> Point : A->B stopped at the first wall it hits.

Relationship to ``code.map`` (deliberate, documented — CLAUDE.md rule 13 warns
about silent divergence between two implementations of the same rule):
``Map.has_line_of_sight`` is the long-standing, cited, 0.5-inch-grid
line-of-sight engine ALREADY wired into shooting target selection
(``Battle._do_shoot``) and Fire Overwatch. Empirically it already denies ~45%
of candidate shots on a dense map, so line-of-sight target *legality* is not
missing from the simulator. Rather than fork a second, drift-prone copy of the
Ruins / Woods / AIRCRAFT / TOWERING rules, ``has_los`` here DELEGATES to that
single trusted engine (which carries its own per-map ``_los_cache`` keyed on the
quantized endpoints — the hot-loop cache the proposal asks for). What is
genuinely NEW is ``path_blocked`` / ``wall_clamp``: the movement question the
simulator never asked (open issue 52 — units path point-to-point through ruin
walls). Those get a fresh per-map blocker-rectangle precompute plus an LRU over
quantized endpoints here.

Terrain-type -> blocking mapping (cited verbatim vs Wahapedia in
``data/rule_citations.d/terrain_realism.json``):

    OPEN         : blocks neither sight nor movement.
    LIGHT_COVER  : Benefit of Cover only; blocks neither. (Barricades/craters.)
    HEAVY_COVER  : Benefit of Cover only; blocks neither. (10e has one cover pip.)
    OBSCURING    : Woods — block SIGHT (unless an endpoint is inside, or either
                   model is TOWERING / AIRCRAFT); do NOT block movement (passable).
    RUIN         : walls block SIGHT (unless an endpoint is inside, or either model
                   is AIRCRAFT) AND block MOVEMENT for non-INFANTRY movers
                   (INFANTRY / BEASTS move through ruin walls in 10e); the footprint
                   is passable and grants Benefit of Cover.
    IMPASSABLE   : blocks MOVEMENT for everyone. (No stock map places one; retained
                   for completeness. Its solid body would block sight too, but the
                   line-of-sight half defers to Map.has_line_of_sight, which — like
                   real 10e area terrain — treats only OBSCURING/RUIN as sight
                   blockers, so IMPASSABLE is a movement blocker only here.)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List, Optional, Tuple

from ..map import Map, TerrainType, _segment_rect_intersects

Point = Tuple[float, float]

# Small pull-back (as a fraction of the segment) so a clamped move stops JUST
# short of a wall rather than exactly on its face — keeps the mover outside the
# blocking rectangle for the next round's own checks.
_CLAMP_BACKOFF = 1e-6

# ---------------------------------------------------------------------------
# Per-map movement-blocker precompute (the proposal's "precompute per-map wall
# segment lists once"). Keyed by id(map.terrain); a strong ref is held so the id
# cannot be recycled to a different tuple — the same lifetime trick code.map uses
# for its terrain-epoch table. In practice a session has a handful of layouts.
# ---------------------------------------------------------------------------
_blocker_live: list = []           # strong refs; prevents id reuse
_epoch_map: dict = {}              # id(terrain tuple) -> stable small int (cache key)
_epoch_rects: dict = {}            # epoch -> (ruin, impassable, obscuring) rect tuples
_epoch_counter: list = [0]


def _terrain_epoch(map_: Map) -> int:
    """Stable small int for this terrain configuration; precomputes and caches
    the split blocker-rectangle lists the first time a layout is seen (the
    proposal's 'precompute per-map wall segment lists once')."""
    tid = id(map_.terrain)
    ep = _epoch_map.get(tid)
    if ep is not None:
        return ep
    _blocker_live.append(map_.terrain)      # keep alive so id() is stable
    ep = _epoch_counter[0]
    _epoch_counter[0] += 1
    _epoch_map[tid] = ep
    ruin: List = []
    impassable: List = []
    obscuring: List = []
    for t in map_.terrain:
        if t.type is TerrainType.RUIN:
            ruin.append(t)
        elif t.type is TerrainType.IMPASSABLE:
            impassable.append(t)
        elif t.type is TerrainType.OBSCURING:
            obscuring.append(t)
    _epoch_rects[ep] = (tuple(ruin), tuple(impassable), tuple(obscuring))
    return ep


def _blockers(map_: Map):
    """(ruin_rects, impassable_rects, obscuring_rects) for this map, cached."""
    return _epoch_rects[_terrain_epoch(map_)]


# ---------------------------------------------------------------------------
# Line of sight — the proposal's has_los(a, b, map_) primitive.
# ---------------------------------------------------------------------------
def has_los(
    pos_a: Point,
    pos_b: Point,
    map_: Map,
    attacker_keywords: Optional[Iterable[str]] = None,
    target_keywords: Optional[Iterable[str]] = None,
) -> bool:
    """True if B is visible from A (no OBSCURING/RUIN wall wholly between them).

    Delegates to the single trusted, cited, cached line-of-sight engine
    ``Map.has_line_of_sight`` (see the module docstring for why a second
    implementation is deliberately avoided). ``attacker_keywords`` /
    ``target_keywords`` carry the AIRCRAFT (blanket Ruin pass) and TOWERING
    (see-over-Woods) exceptions; omit them for a pure-geometry query, in which
    case a Ruin is treated as a full blocker (the conservative default the
    engine documents)."""
    return map_.has_line_of_sight(
        pos_a, pos_b,
        attacker_keywords=attacker_keywords,
        target_keywords=target_keywords,
    )


# ---------------------------------------------------------------------------
# Movement wall collision — the proposal's path_blocked(a, b, map_) primitive.
# ---------------------------------------------------------------------------
def path_blocked(pos_a: Point, pos_b: Point, map_: Map, block_ruins: bool = True) -> bool:
    """True if the straight move A->B passes into a movement-blocking wall.

    A wall is an IMPASSABLE rectangle (always) or, when ``block_ruins`` is True,
    a RUIN rectangle (the caller passes ``block_ruins=False`` for INFANTRY /
    BEAST movers, which move through ruin walls in 10e). OBSCURING (Woods) and
    cover pieces never block movement. A mover already standing INSIDE a wall is
    allowed to leave it (``pos_a`` inside -> not blocked by that rectangle), so a
    unit can never be frozen by the feature it occupies."""
    epoch = _terrain_epoch(map_)
    ruin, impassable, _ = _epoch_rects[epoch]
    if not impassable and not (block_ruins and ruin):
        return False
    return _path_blocked_cached(
        epoch,
        round(pos_a[0] * 2), round(pos_a[1] * 2),
        round(pos_b[0] * 2), round(pos_b[1] * 2),
        block_ruins,
    )


@lru_cache(maxsize=200_000)
def _path_blocked_cached(epoch: int, qax: int, qay: int, qbx: int, qby: int,
                         block_ruins: bool) -> bool:
    """LRU-cached boolean crossing test on the 0.5-inch grid (movement hot path).

    The blocker rectangles are fetched by ``epoch`` (a pure function of the
    terrain configuration), so the cache key is fully self-contained — the same
    quantized endpoints on the same layout always yield the same answer."""
    a = (qax * 0.5, qay * 0.5)
    b = (qbx * 0.5, qby * 0.5)
    ruin, impassable, _ = _epoch_rects[epoch]
    rects = impassable + (ruin if block_ruins else ())
    for t in rects:
        if t.contains(a):
            continue                              # leaving the feature we're in
        if _segment_rect_intersects(a, b, t):
            return True
    return False


def wall_clamp(pos_a: Point, pos_b: Point, map_: Map, block_ruins: bool = True) -> Point:
    """The furthest point along A->B that does not enter a movement-blocking wall.

    Returns ``pos_b`` unchanged when the segment crosses no wall. When it would
    cross one, returns the entry point on the near face (pulled back a hair so
    the mover sits just outside the wall). A mover starting inside a wall is not
    clamped by it (it may leave). Exact continuous geometry — no quantization —
    because the clamp position feeds directly back into the model's coordinates."""
    ruin, impassable, _ = _blockers(map_)
    rects = impassable + (ruin if block_ruins else ())
    if not rects:
        return pos_b
    ax, ay = pos_a
    bx, by = pos_b
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return pos_b
    best_t = 1.0
    for t in rects:
        if t.contains(pos_a):
            continue
        te = _segment_rect_entry_t(pos_a, pos_b, t)
        if te is not None and te < best_t:
            best_t = te
    if best_t >= 1.0:
        return pos_b
    best_t = max(0.0, best_t - _CLAMP_BACKOFF)
    return (ax + dx * best_t, ay + dy * best_t)


def _segment_rect_entry_t(p1: Point, p2: Point, rect) -> Optional[float]:
    """Liang-Barsky entry parameter t in [0, 1) where segment p1->p2 first enters
    the axis-aligned ``rect``; None if it never enters. Mirrors the clipping in
    ``code.map._segment_rect_intersects`` but returns the entry t instead of a
    bool, so the movement clamp can stop the mover exactly on the near face."""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    t_enter = 0.0
    t_exit = 1.0
    for p, q in (
        (-dx, x1 - rect.x),
        (dx, rect.x2 - x1),
        (-dy, y1 - rect.y),
        (dy, rect.y2 - y1),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t_enter:
                t_enter = t
        else:
            if t < t_exit:
                t_exit = t
        if t_enter > t_exit:
            return None
    if t_enter < t_exit:
        return t_enter
    return None


def _reset_caches() -> None:
    """Test hook — drop the per-map precompute and memo (never needed in a run)."""
    _blocker_live.clear()
    _epoch_map.clear()
    _epoch_rects.clear()
    _epoch_counter[0] = 0
    _path_blocked_cached.cache_clear()
