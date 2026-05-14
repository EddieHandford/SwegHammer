"""
Map and Terrain primitives.

Phase A keeps terrain simple: axis-aligned rectangles with a TerrainType
tag. That's enough to render, to gate movement (impassable), and to look
up cover for a unit standing inside. Polygon terrain can come later if
the rectangles feel too crude.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class TerrainType(Enum):
    OPEN = "open"
    LIGHT_COVER = "light_cover"     # +1 save vs ranged
    HEAVY_COVER = "heavy_cover"     # +1 save and -1 to hit
    OBSCURING = "obscuring"         # blocks line of sight
    IMPASSABLE = "impassable"       # blocks movement


@dataclass(frozen=True)
class Terrain:
    """An axis-aligned rectangle of terrain on the board."""

    name: str
    x: float            # bottom-left corner, inches from board origin
    y: float
    width: float
    height: float
    type: TerrainType

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
        """Return the strongest cover the point sits inside, OPEN if none."""
        result = TerrainType.OPEN
        priority = {
            TerrainType.OPEN: 0,
            TerrainType.LIGHT_COVER: 1,
            TerrainType.OBSCURING: 2,
            TerrainType.HEAVY_COVER: 3,
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
    ) -> bool:
        """True if a straight line from attacker to target is not blocked
        by any OBSCURING terrain that doesn't contain either endpoint.

        Units standing inside obscuring terrain can still shoot out and be
        shot at (we exclude any rectangle containing one of the endpoints
        from the intersection test)."""
        for t in self.terrain:
            if t.type is not TerrainType.OBSCURING:
                continue
            if t.contains(attacker) or t.contains(target):
                continue
            if _segment_rect_intersects(attacker, target, t):
                return False
        return True


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
