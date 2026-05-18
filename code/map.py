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
from typing import Iterable, Optional, Tuple


# 10e Ruins core rule (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Ruins):
# "Models can shoot through walls of a Ruin so long as both the firing model
# and the target model have the INFANTRY, BEAST or SWARM keyword. In all
# other cases, a wall blocks line of sight." Cited as
# `terrain.ruin_infantry_los` in scripts/audit_rules.py.
_RUIN_LOS_PASS_KEYWORDS = frozenset({"INFANTRY", "BEAST", "SWARM"})


class TerrainType(Enum):
    OPEN = "open"
    LIGHT_COVER = "light_cover"     # +1 save vs ranged
    HEAVY_COVER = "heavy_cover"     # +1 save and -1 to hit
    OBSCURING = "obscuring"         # blocks line of sight
    IMPASSABLE = "impassable"       # blocks movement
    RUIN = "ruin"                   # 10e Ruin: +1 save and -1 to hit (Heavy Cover),
                                    # blocks LoS through its walls UNLESS both shooter and
                                    # target are INFANTRY / BEAST / SWARM (10e core).


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
        """Return the strongest cover the point sits inside, OPEN if none.

        RUIN counts as Heavy Cover for the save / -1-to-hit bonus (10e
        treats a Ruin as Heavy Cover terrain); the through-walls LoS
        asymmetry is resolved separately in `has_line_of_sight`."""
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

        OBSCURING terrain always blocks LoS unless either endpoint stands
        inside the rectangle (the "see in / see out" allowance — fine for
        woods, blast walls, smoke).

        RUIN walls block LoS UNLESS both the attacker and the target carry
        the INFANTRY, BEAST, or SWARM keyword (10e core Ruins rule). When
        keyword tuples are not supplied (older call-sites), RUIN is
        treated as a full LoS blocker to stay safely conservative.

        Wahapedia: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Ruins
        > "Models can shoot through walls of a Ruin so long as both the
        > firing model and the target model have the INFANTRY, BEAST or
        > SWARM keyword. In all other cases, a wall blocks line of sight."
        """
        a_kw = frozenset(attacker_keywords or ())
        t_kw = frozenset(target_keywords or ())
        ruin_pass = bool(a_kw & _RUIN_LOS_PASS_KEYWORDS) and bool(
            t_kw & _RUIN_LOS_PASS_KEYWORDS
        )
        for t in self.terrain:
            if t.type is TerrainType.OBSCURING:
                if t.contains(attacker) or t.contains(target):
                    continue
                if _segment_rect_intersects(attacker, target, t):
                    return False
            elif t.type is TerrainType.RUIN:
                # Both endpoints inside still pass (you can see through
                # your own ruin's interior).
                if t.contains(attacker) or t.contains(target):
                    continue
                if not _segment_rect_intersects(attacker, target, t):
                    continue
                if ruin_pass:
                    continue
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
