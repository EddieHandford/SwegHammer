"""
Map and Terrain primitives.

Phase A keeps terrain simple: axis-aligned rectangles with a TerrainType
tag. That's enough to render, to gate movement (impassable), and to look
up cover for a unit standing inside. Polygon terrain can come later if
the rectangles feel too crude.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Tuple


# 10e Ruins core rule (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Ruins):
# "Models cannot see over or through this terrain feature. AIRCRAFT models are
# exceptions to this — visibility to and from such models is determined
# normally, even if this terrain feature is wholly in between them and the
# observing model. Models can see into this terrain feature normally, and
# models that are wholly within this terrain feature can see out of it
# normally." There is NO blanket INFANTRY/BEAST/SWARM see-through any more —
# in current 10e the INFANTRY/BEAST exception for Ruins is MOVEMENT ONLY
# ("can move through this terrain feature's walls, floors and ceilings"); it
# does not grant line of sight. Cited as `terrain.ruin_infantry_los` in
# scripts/audit_rules.py.
#
# AIRCRAFT is the only blanket line-of-sight exception for Ruins; a TOWERING
# model only sees OUT of a Ruin when it is itself within the Ruin (covered by
# the "endpoint contained" allowance in _los_query — TOWERING is not special
# for Ruins beyond that). Cited as `simulator.towering_los`.
_RUIN_LOS_BLANKET_KEYWORD = "AIRCRAFT"

# 10e core TOWERING keyword rule, as applied to Woods / the sim's OBSCURING
# terrain type (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Woods):
# "AIRCRAFT and TOWERING models are exceptions to this — visibility to and
# from such models is determined normally, even if this terrain feature is
# wholly in between them and the observing model." TOWERING (and AIRCRAFT) can
# therefore see over Obscuring/Woods terrain. TOWERING does NOT grant a
# blanket see-over for Ruins (see _RUIN_LOS_BLANKET_KEYWORD above).
# Cited as `simulator.towering_los` in scripts/audit_rules.py.
_TOWERING_KEYWORD = "TOWERING"


class TerrainType(Enum):
    # 10e has a single Benefit of Cover (+1 to the armour saving throw); there
    # is no Light/Heavy cover split and no terrain -1-to-hit any more. The
    # LIGHT_COVER / HEAVY_COVER members are retained because other modules
    # (maps.py, strategy.py) reference them by name, but they now grant the
    # SAME single Benefit of Cover as each other and as a Ruin.
    OPEN = "open"
    LIGHT_COVER = "light_cover"     # Benefit of Cover (+1 save vs ranged)
    HEAVY_COVER = "heavy_cover"     # Benefit of Cover (+1 save vs ranged) — same as LIGHT_COVER in 10e
    OBSCURING = "obscuring"         # Woods/Obscuring: blocks line of sight (AIRCRAFT/TOWERING see over)
    IMPASSABLE = "impassable"       # blocks movement
    RUIN = "ruin"                   # 10e Ruin: Benefit of Cover (+1 save vs ranged); its walls
                                    # block line of sight for everyone except AIRCRAFT, and a
                                    # model wholly within the Ruin can see out (10e core). The
                                    # INFANTRY/BEAST Ruin exception is MOVEMENT only, not sight.


@dataclass(frozen=True)
class Wall:
    """A line-segment barrier within a Terrain feature (avenue-2 Stage 3,
    walls-vs-area model). In 10e a Ruin's WALLS block line of sight (and, for
    non-INFANTRY, movement — Stage 4) while the footprint AREA grants Benefit of
    Cover and is standable: the two are distinct, and the gaps BETWEEN wall
    segments (doorways) are see-through + passable. A Wall is the segment from
    (x1, y1) to (x2, y2), inches from the board origin. Frozen + hashable so it
    can live in a frozen Terrain's tuple. An empty `Terrain.walls` (the default)
    preserves the legacy solid-rectangle behaviour byte-for-byte."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Terrain:
    """An axis-aligned rectangle of terrain on the board.

    `walls` (avenue-2 Stage 3) is an optional tuple of `Wall` line-segments — the
    feature's actual barriers (a Ruin's standing walls, with doorway gaps). It
    defaults to empty, so every existing map and the rectangle line-of-sight /
    cover behaviour are unchanged; the wall geometry is consulted only by the
    gated walls-vs-area line-of-sight + movement paths."""

    name: str
    x: float            # bottom-left corner, inches from board origin
    y: float
    width: float
    height: float
    type: TerrainType
    walls: Tuple["Wall", ...] = ()

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    def contains(self, point: Tuple[float, float]) -> bool:
        px, py = point
        return self.x <= px <= self.x2 and self.y <= py <= self.y2


@dataclass(frozen=True)
class Objective:
    """A scoring objective. Side with more OC within control_radius scores it."""
    name: str
    x: float            # inches from board origin
    y: float
    control_radius: float = 3.0   # 10e standard: control range = 3"
    vp_per_round: int = 5         # 10e Primary VP per held objective per round


@dataclass(frozen=True)
class Map:
    """A battlefield map: dimensions, terrain pieces, deployment zones, objectives."""

    name: str
    width: float        # inches
    height: float
    terrain: Tuple[Terrain, ...] = ()
    objectives: Tuple[Objective, ...] = ()
    deployment_width: float = 12.0   # each side gets a strip of this depth

    def is_blocked(self, point: Tuple[float, float]) -> bool:
        """True if a unit cannot stand at this point (impassable terrain)."""
        for t in self.terrain:
            if t.type is TerrainType.IMPASSABLE and t.contains(point):
                return True
        return False

    def cover_at(self, point: Tuple[float, float]) -> TerrainType:
        """Return the strongest cover the point sits inside, OPEN if none.

        In 10e every cover terrain grants the same single Benefit of Cover
        (+1 to the armour saving throw): LIGHT_COVER, HEAVY_COVER and RUIN are
        equivalent for the combat effect. The distinct members are retained
        only because other modules reference them by name. The Ruin
        block-line-of-sight asymmetry is resolved separately in
        `has_line_of_sight`."""
        result = TerrainType.OPEN
        priority = {
            TerrainType.OPEN: 0,
            TerrainType.LIGHT_COVER: 1,
            TerrainType.OBSCURING: 2,
            TerrainType.HEAVY_COVER: 3,
            TerrainType.RUIN: 3,
            TerrainType.IMPASSABLE: 4,
        }
        for t in self.terrain:
            if t.contains(point) and priority[t.type] > priority[result]:
                result = t.type
        return result

    def has_line_of_sight(
        self,
        attacker: Tuple[float, float],
        target: Tuple[float, float],
        attacker_keywords: Optional[Iterable[str]] = None,
        target_keywords: Optional[Iterable[str]] = None,
    ) -> bool:
        """True if a straight line from attacker to target is not blocked.

        OBSCURING terrain (Woods) always blocks LoS unless either endpoint
        stands inside the rectangle (the "see in / see out" allowance — fine
        for woods, blast walls, smoke). Exception: when either the attacker or
        the target has the TOWERING or AIRCRAFT keyword, OBSCURING terrain
        does not block the line of sight (10e core Woods rule).

        RUIN walls block LoS for everyone, with two narrow exceptions:
          * a model wholly within the Ruin can see out, and can be seen
            (handled by the "endpoint contained" check in _los_query — this
            also covers a TOWERING model that is within the Ruin); and
          * AIRCRAFT is the only blanket exception — visibility to and from an
            AIRCRAFT model is determined normally even through Ruin walls.
        TOWERING does NOT grant a blanket see-over for Ruins (unlike Woods).
        When keyword tuples are not supplied (older call-sites), RUIN is
        treated as a full LoS blocker to stay safely conservative.

        Wahapedia: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Ruins
        > "Models cannot see over or through this terrain feature. AIRCRAFT
        > models are exceptions to this — visibility to and from such models
        > is determined normally, even if this terrain feature is wholly in
        > between them and the observing model. Models can see into this
        > terrain feature normally, and models that are wholly within this
        > terrain feature can see out of it normally. ... TOWERING models that
        > are within this terrain feature can also see out of it normally."

        Wahapedia: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Woods
        > "AIRCRAFT and TOWERING models are exceptions to this — visibility to
        > and from such models is determined normally, even if this terrain
        > feature is wholly in between them and the observing model."
        """
        towering = (
            _has_towering(attacker_keywords)
            or _has_towering(target_keywords)
        )
        # Only AIRCRAFT gets a blanket see-through for Ruin walls. A TOWERING
        # model that is within the Ruin is handled by the endpoint-contained
        # allowance in _los_query, not by this flag.
        ruin_pass = (
            _has_aircraft(attacker_keywords)
            or _has_aircraft(target_keywords)
        )
        # Avenue-2 Stage 3 doorway line of sight (gated SWEG_RUINWALLS): when set,
        # Ruins with encoded wall segments block sight only across those segments
        # (doorway gaps pass) instead of the whole rectangle. OFF (default) and any
        # Ruin without walls keep the legacy whole-rect block — byte-identical.
        walls_los = bool(__import__("os").environ.get("SWEG_RUINWALLS"))
        return _los_query(
            self,
            round(attacker[0] * 2), round(attacker[1] * 2),
            round(target[0] * 2), round(target[1] * 2),
            ruin_pass,
            towering,
            walls_los,
        )

    def wall_segments(self) -> Tuple["Wall", ...]:
        """All Ruin wall segments across the map's terrain (avenue-2 Stage 3) —
        used by the segment line-of-sight / movement paths and the renderer.
        Empty until per-ruin wall layouts are encoded."""
        out = []
        for t in self.terrain:
            out.extend(t.walls)
        return tuple(out)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _segment_rect_intersects(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    rect: Terrain,
) -> bool:
    """Liang-Barsky parametric clipping. Returns True iff the segment from
    p1 to p2 crosses the axis-aligned rectangle."""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1

    t_enter = 0.0
    t_exit = 1.0

    for p, q in (
        (-dx, x1 - rect.x),       # left edge
        ( dx, rect.x2 - x1),      # right edge
        (-dy, y1 - rect.y),       # bottom edge
        ( dy, rect.y2 - y1),      # top edge
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return False      # parallel and outside this slab
            continue
        t = q / p
        if p < 0:
            if t > t_enter:
                t_enter = t
        else:
            if t < t_exit:
                t_exit = t
        if t_enter > t_exit:
            return False

    return t_enter < t_exit


# ---------------------------------------------------------------------------
# Line-of-sight cache
# ---------------------------------------------------------------------------
# Keyed by (terrain_epoch, ax, ay, tx, ty, ruin_pass, towering).
# `terrain_epoch` is a cheap stable integer assigned per unique terrain tuple
# the first time it is seen.  Storing the tuple in `_terrain_live` prevents
# Python from garbage-collecting it and reusing its id for a different tuple,
# so id(terrain) is safe to use once the epoch is assigned.  In practice
# there are only a handful of distinct terrain configurations per session.
_los_cache: Dict[tuple, bool] = {}
_terrain_epoch_map: Dict[int, int] = {}   # id(terrain_tuple) → epoch int
_terrain_live: list = []                   # holds strong refs; prevents GC
_terrain_epoch_counter: list = [0]         # mutable int in a list for closure

# Speed lever #2 (PART B) — line-of-sight cache gate. `SWEG_LOSCACHE` (default
# "1" = ON) controls whether `_los_query` consults / fills `_los_cache`. The
# cache is keyed purely by terrain configuration + rounded endpoint positions +
# the keyword flags, none of which change for a given geometry, so it is
# byte-identical: the same query always yields the same answer. When set to "0"
# the OFF path runs the exact pre-existing geometry computation with no cache
# read or write, so a validation A/B can confirm identical line-of-sight (and
# therefore identical win rates). Read once at import.
_LOSCACHE_ON: bool = os.environ.get("SWEG_LOSCACHE", "1") != "0"


def _terrain_epoch(terrain) -> int:
    """Return a stable cheap int key for this terrain tuple configuration."""
    tid = id(terrain)
    try:
        return _terrain_epoch_map[tid]
    except KeyError:
        _terrain_live.append(terrain)   # keep alive so id is not reused
        epoch = _terrain_epoch_counter[0]
        _terrain_epoch_counter[0] += 1
        _terrain_epoch_map[tid] = epoch
        return epoch


def _has_aircraft(kw_iter: Optional[Iterable[str]]) -> bool:
    """True if any keyword in kw_iter is AIRCRAFT.

    AIRCRAFT is the only model type that gets a blanket line-of-sight pass
    through Ruin walls in current 10e (the old INFANTRY/BEAST/SWARM
    shoot-through-walls line-of-sight pass was removed — that keyword
    exception is movement-only now)."""
    if not kw_iter:
        return False
    for k in kw_iter:
        if k == _RUIN_LOS_BLANKET_KEYWORD:
            return True
    return False


def _has_towering(kw_iter: Optional[Iterable[str]]) -> bool:
    """True if any keyword in kw_iter is TOWERING."""
    if not kw_iter:
        return False
    for k in kw_iter:
        if k == _TOWERING_KEYWORD:
            return True
    return False


def _segment_segment_intersects(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    wall: "Wall",
) -> bool:
    """True iff the line-of-sight segment p1->p2 crosses the Wall segment
    (avenue-2 Stage 3 doorway line-of-sight). Standard orientation (ccw) test;
    collinear-overlap is treated as non-blocking, which is the conservative,
    rare edge case for grazing sight lines."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3, x4, y4 = wall.x1, wall.y1, wall.x2, wall.y2

    def _ccw(ax_, ay_, bx_, by_, cx_, cy_):
        return (cy_ - ay_) * (bx_ - ax_) - (by_ - ay_) * (cx_ - ax_)

    d1 = _ccw(x3, y3, x4, y4, x1, y1)
    d2 = _ccw(x3, y3, x4, y4, x2, y2)
    d3 = _ccw(x1, y1, x2, y2, x3, y3)
    d4 = _ccw(x1, y1, x2, y2, x4, y4)
    return (((d1 > 0) != (d2 > 0)) and (d1 != 0) and (d2 != 0)
            and ((d3 > 0) != (d4 > 0)) and (d3 != 0) and (d4 != 0))


def _los_query(
    map_: "Map",
    ax: int, ay: int,
    tx: int, ty: int,
    ruin_pass: bool,
    towering: bool = False,
    walls_los: bool = False,
) -> bool:
    """Line-of-sight check on a 0.5-inch grid, with per-map caching.

    When ``towering`` is True (either endpoint carries the TOWERING keyword),
    OBSCURING (Woods) terrain is ignored entirely — TOWERING models see over
    it (as do AIRCRAFT). TOWERING does NOT see through RUIN walls, however:
    only ``ruin_pass`` (set when either endpoint is AIRCRAFT) lifts the Ruin
    block, plus the per-terrain "endpoint contained" allowance below which lets
    any model wholly within the Ruin (including a TOWERING one) see out.

    Caching is gated by ``SWEG_LOSCACHE`` (default ON). The cache key is purely
    a function of the immutable terrain configuration, the rounded endpoint
    positions and the keyword flags, so a cached answer is byte-identical to a
    freshly computed one. With the gate OFF, the geometry is recomputed every
    call with no cache read or write — the exact pre-existing behaviour, so an
    A/B can confirm identical line-of-sight (and identical win rates).
    """
    if not _LOSCACHE_ON:
        return _los_compute(map_, ax, ay, tx, ty, ruin_pass, towering, walls_los)
    key = (_terrain_epoch(map_.terrain), ax, ay, tx, ty, ruin_pass, towering, walls_los)
    try:
        return _los_cache[key]
    except KeyError:
        pass
    result = _los_compute(map_, ax, ay, tx, ty, ruin_pass, towering, walls_los)
    _los_cache[key] = result
    return result


def _los_compute(
    map_: "Map",
    ax: int, ay: int,
    tx: int, ty: int,
    ruin_pass: bool,
    towering: bool = False,
    walls_los: bool = False,
) -> bool:
    """Pure line-of-sight geometry on a 0.5-inch grid (no caching).

    Factored out of `_los_query` so the cache and its OFF path share one exact
    implementation; see `_los_query` for the rule semantics."""
    a = (ax * 0.5, ay * 0.5)
    t = (tx * 0.5, ty * 0.5)
    result = True
    for terrain in map_.terrain:
        if terrain.type is TerrainType.OBSCURING:
            if towering:
                continue   # TOWERING ignores Obscuring terrain for LoS
            if terrain.contains(a) or terrain.contains(t):
                continue
            if _segment_rect_intersects(a, t, terrain):
                result = False
                break
        elif terrain.type is TerrainType.RUIN:
            if terrain.contains(a) or terrain.contains(t):
                continue
            if walls_los and terrain.walls:
                # Walls-vs-area line of sight (avenue-2 Stage 3): a Ruin blocks
                # the sight line only where it crosses an actual WALL segment;
                # gaps between segments (doorways) are see-through. A Ruin with
                # no encoded walls falls through to the legacy whole-rect block
                # below, so this is byte-identical until per-ruin walls land.
                if not any(_segment_segment_intersects(a, t, w) for w in terrain.walls):
                    continue
            elif not _segment_rect_intersects(a, t, terrain):
                continue
            if ruin_pass:
                continue
            result = False
            break
    return result
