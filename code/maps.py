"""
Stock maps shipped with SwegHammer.

Add new maps here and register them in STOCK_MAPS so the front end can
pick them up automatically.
"""

from __future__ import annotations

from .map import Map, Objective, Terrain, TerrainType


def _quincunx_objectives(width: float, height: float) -> tuple:
    """
    Five-objective layout common to most 10e missions (Take and Hold, Crucible,
    Tipping Point, etc.): one in the centre and four equidistant points roughly
    a third of the way in from each board edge.
    """
    cx, cy = width / 2.0, height / 2.0
    inset_x = width * 0.30
    inset_y = height * 0.25
    return (
        Objective(name="Centre",    x=cx, y=cy),
        Objective(name="NW Marker", x=cx - inset_x, y=cy + inset_y),
        Objective(name="NE Marker", x=cx + inset_x, y=cy + inset_y),
        Objective(name="SW Marker", x=cx - inset_x, y=cy - inset_y),
        Objective(name="SE Marker", x=cx + inset_x, y=cy - inset_y),
    )


COMBAT_PATROL_BASIC = Map(
    name="Combat Patrol - Open Field",
    width=44.0,
    height=60.0,
    objectives=_quincunx_objectives(44.0, 60.0),
    terrain=(
        Terrain(
            name="Ruin Alpha",
            x=8.0, y=18.0, width=8.0, height=6.0,
            type=TerrainType.HEAVY_COVER,
        ),
        Terrain(
            name="Ruin Bravo",
            x=28.0, y=36.0, width=8.0, height=6.0,
            type=TerrainType.HEAVY_COVER,
        ),
        Terrain(
            name="Woods",
            x=18.0, y=26.0, width=8.0, height=8.0,
            type=TerrainType.OBSCURING,
        ),
        Terrain(
            name="South Barricades",
            x=14.0, y=14.0, width=16.0, height=2.0,
            type=TerrainType.LIGHT_COVER,
        ),
        Terrain(
            name="North Barricades",
            x=14.0, y=44.0, width=16.0, height=2.0,
            type=TerrainType.LIGHT_COVER,
        ),
    ),
    deployment_width=12.0,
)


URBAN_SPRAWL = Map(
    name="Strike Force - Urban Sprawl",
    width=44.0,
    height=90.0,
    objectives=_quincunx_objectives(44.0, 90.0),
    terrain=(
        Terrain("Ruin North",  x=6.0,  y=68.0, width=10.0, height=8.0, type=TerrainType.HEAVY_COVER),
        Terrain("Ruin South",  x=28.0, y=14.0, width=10.0, height=8.0, type=TerrainType.HEAVY_COVER),
        Terrain("Central Wall", x=20.0, y=43.0, width=4.0,  height=4.0, type=TerrainType.IMPASSABLE),
        Terrain("West Wood",   x=4.0,  y=38.0, width=8.0,  height=10.0, type=TerrainType.OBSCURING),
        Terrain("East Wood",   x=32.0, y=52.0, width=8.0,  height=10.0, type=TerrainType.OBSCURING),
        Terrain("West Barricade", x=10.0, y=52.0, width=2.0,  height=10.0, type=TerrainType.LIGHT_COVER),
        Terrain("East Barricade", x=32.0, y=30.0, width=2.0,  height=10.0, type=TerrainType.LIGHT_COVER),
    ),
    deployment_width=12.0,
)


OPEN_PLAINS = Map(
    name="Combat Patrol - Open Plains",
    width=44.0,
    height=60.0,
    objectives=_quincunx_objectives(44.0, 60.0),
    terrain=(
        Terrain("Lone Wood",       x=18.0, y=26.0, width=8.0, height=8.0, type=TerrainType.OBSCURING),
        Terrain("South Ridge",     x=6.0,  y=20.0, width=12.0, height=3.0, type=TerrainType.LIGHT_COVER),
        Terrain("North Ridge",     x=26.0, y=37.0, width=12.0, height=3.0, type=TerrainType.LIGHT_COVER),
    ),
    deployment_width=12.0,
)


STOCK_MAPS = {
    "combat_patrol": COMBAT_PATROL_BASIC,
    "open_plains":   OPEN_PLAINS,
    "urban_sprawl":  URBAN_SPRAWL,
}

DEFAULT_MAP = COMBAT_PATROL_BASIC


# ---------------------------------------------------------------------------
# Battle-size tagging (10e battle sizes)
# ---------------------------------------------------------------------------
#
# 10e standard battle sizes:
#   Combat Patrol  500 pts, 30" x 40"
#   Incursion     1000 pts, 44" x 60"
#   Strike Force  2000 pts, 44" x 60"
#   Onslaught     3000 pts, 44" x 90"
#
# Our stock maps don't all match those exact footprints, but we tag each with
# a sensible points range so the front end can auto-select or filter.
MAP_POINTS_RANGE = {
    "combat_patrol": (250, 1250),   # 44 x 60, ruin + barricade — Combat Patrol / Incursion
    "open_plains":   (500, 2000),   # 44 x 60, sparse terrain — Strike Force friendly
    "urban_sprawl":  (1500, 3500),  # 44 x 90, asymmetric — Strike Force / Onslaught
}


def auto_select_map_key(points: float) -> str:
    """Pick the stock map whose recommended range best fits this points budget."""
    candidates = []
    for key, (lo, hi) in MAP_POINTS_RANGE.items():
        if lo <= points <= hi:
            # Prefer the band whose centre is closest to the budget
            centre = (lo + hi) / 2.0
            candidates.append((abs(centre - points), key))
    if candidates:
        return min(candidates)[1]
    # Out-of-range: fall back to the closest band edge
    closest = min(
        MAP_POINTS_RANGE.items(),
        key=lambda kv: min(abs(kv[1][0] - points), abs(kv[1][1] - points)),
    )
    return closest[0]


def maps_fitting(points: float) -> "list[str]":
    """All stock map keys whose recommended range includes `points`."""
    fits = [k for k, (lo, hi) in MAP_POINTS_RANGE.items() if lo <= points <= hi]
    return fits or list(MAP_POINTS_RANGE.keys())
