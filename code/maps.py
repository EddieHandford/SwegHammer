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
            type=TerrainType.RUIN,
        ),
        Terrain(
            name="Ruin Bravo",
            x=28.0, y=36.0, width=8.0, height=6.0,
            type=TerrainType.RUIN,
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
        Terrain("Ruin North",  x=6.0,  y=68.0, width=10.0, height=8.0, type=TerrainType.RUIN),
        Terrain("Ruin South",  x=28.0, y=14.0, width=10.0, height=8.0, type=TerrainType.RUIN),
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


# ---------------------------------------------------------------------------
# 10e mission-deployment maps with genuine asymmetry
# ---------------------------------------------------------------------------

CRUCIBLE_OF_BATTLE = Map(
    name="Crucible of Battle",
    width=44.0,
    height=60.0,
    objectives=_quincunx_objectives(44.0, 60.0),
    # Diagonal asymmetry: heavy terrain on the NE-SW diagonal, light on NW-SE.
    # Large ruin top-right, wooded copse mid-left, two short barricade ridges
    # bridging them, one impassable wall blocking centre.
    terrain=(
        Terrain("Top-Right Ruin",      x=30.0, y=44.0, width=10.0, height=10.0, type=TerrainType.RUIN),
        Terrain("Mid-Left Copse",      x=4.0,  y=26.0, width=8.0,  height=10.0, type=TerrainType.OBSCURING),
        Terrain("NE Barricade Ridge",  x=22.0, y=38.0, width=8.0,  height=2.0,  type=TerrainType.LIGHT_COVER),
        Terrain("SW Barricade Ridge",  x=12.0, y=20.0, width=8.0,  height=2.0,  type=TerrainType.LIGHT_COVER),
        Terrain("Central Wall",        x=20.0, y=28.0, width=4.0,  height=4.0,  type=TerrainType.IMPASSABLE),
    ),
    deployment_width=12.0,
)


def _search_and_destroy_objectives(width: float, height: float) -> tuple:
    """
    Search & Destroy: opposing-corner deployment with terrain massed in the
    NW and SE quadrants. Objectives bias toward those heavy-terrain zones:
    one centre, two NW (deeper into the heavy-terrain zone), two SE.
    """
    cx, cy = width / 2.0, height / 2.0
    return (
        Objective(name="Centre",          x=cx, y=cy),
        Objective(name="NW Inner",        x=width * 0.30, y=height * 0.65),
        Objective(name="NW Outer",        x=width * 0.18, y=height * 0.80),
        Objective(name="SE Inner",        x=width * 0.70, y=height * 0.35),
        Objective(name="SE Outer",        x=width * 0.82, y=height * 0.20),
    )


SEARCH_AND_DESTROY = Map(
    name="Search and Destroy",
    width=44.0,
    height=60.0,
    objectives=_search_and_destroy_objectives(44.0, 60.0),
    # Corner deployment: NW and SE clusters of terrain, central no-man's-land
    # mostly open. Players push out of corners across exposed ground to
    # contest mid-board objectives.
    terrain=(
        # NW cluster
        Terrain("NW Ruin",         x=4.0,  y=42.0, width=10.0, height=8.0, type=TerrainType.RUIN),
        Terrain("NW Wood",         x=14.0, y=48.0, width=8.0,  height=8.0, type=TerrainType.OBSCURING),
        Terrain("NW Barricade",    x=6.0,  y=36.0, width=10.0, height=2.0, type=TerrainType.LIGHT_COVER),
        # SE cluster
        Terrain("SE Ruin",         x=30.0, y=10.0, width=10.0, height=8.0, type=TerrainType.RUIN),
        Terrain("SE Wood",         x=22.0, y=4.0,  width=8.0,  height=8.0, type=TerrainType.OBSCURING),
        Terrain("SE Barricade",    x=28.0, y=22.0, width=10.0, height=2.0, type=TerrainType.LIGHT_COVER),
        # Lone central feature breaking the open no-man's-land
        Terrain("Centre Crater",   x=20.0, y=28.0, width=4.0,  height=4.0, type=TerrainType.LIGHT_COVER),
    ),
    deployment_width=12.0,
)


def _sweeping_engagement_objectives(width: float, height: float) -> tuple:
    """
    Sweeping Engagement (Strike Force, long-axis): three central objectives
    strung along the long axis plus two corner objectives.
    """
    cx = width / 2.0
    return (
        Objective(name="South Spine",  x=cx,           y=height * 0.30),
        Objective(name="Centre Spine", x=cx,           y=height * 0.50),
        Objective(name="North Spine",  x=cx,           y=height * 0.70),
        Objective(name="NW Corner",    x=width * 0.18, y=height * 0.85),
        Objective(name="SE Corner",    x=width * 0.82, y=height * 0.15),
    )


SWEEPING_ENGAGEMENT = Map(
    name="Sweeping Engagement",
    width=44.0,
    height=90.0,
    objectives=_sweeping_engagement_objectives(44.0, 90.0),
    # Long-axis Strike Force layout: two parallel ruin lines running down the
    # middle channel the fight, woods clusters anchor each short edge.
    terrain=(
        # Two parallel ruins lines down the centre
        Terrain("West Ruin Line North", x=16.0, y=58.0, width=4.0, height=12.0, type=TerrainType.RUIN),
        Terrain("West Ruin Line South", x=16.0, y=22.0, width=4.0, height=12.0, type=TerrainType.RUIN),
        Terrain("East Ruin Line North", x=24.0, y=58.0, width=4.0, height=12.0, type=TerrainType.RUIN),
        Terrain("East Ruin Line South", x=24.0, y=22.0, width=4.0, height=12.0, type=TerrainType.RUIN),
        # Woods clusters at each short edge
        Terrain("South Wood West", x=6.0,  y=4.0,  width=8.0, height=8.0, type=TerrainType.OBSCURING),
        Terrain("South Wood East", x=30.0, y=4.0,  width=8.0, height=8.0, type=TerrainType.OBSCURING),
        Terrain("North Wood West", x=6.0,  y=78.0, width=8.0, height=8.0, type=TerrainType.OBSCURING),
        Terrain("North Wood East", x=30.0, y=78.0, width=8.0, height=8.0, type=TerrainType.OBSCURING),
        # Central spine wall to break direct line down the middle
        Terrain("Central Spine Wall", x=20.0, y=43.0, width=4.0, height=4.0, type=TerrainType.IMPASSABLE),
    ),
    deployment_width=12.0,
)


STOCK_MAPS = {
    "combat_patrol":       COMBAT_PATROL_BASIC,
    "open_plains":         OPEN_PLAINS,
    "urban_sprawl":        URBAN_SPRAWL,
    "crucible_of_battle":  CRUCIBLE_OF_BATTLE,
    "search_and_destroy":  SEARCH_AND_DESTROY,
    "sweeping_engagement": SWEEPING_ENGAGEMENT,
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
    "combat_patrol":       (250, 1250),   # 44 x 60, ruin + barricade — Combat Patrol / Incursion
    "open_plains":         (500, 2000),   # 44 x 60, sparse terrain — Strike Force friendly
    "urban_sprawl":        (1500, 3500),  # 44 x 90, asymmetric — Strike Force / Onslaught
    "crucible_of_battle":  (750, 2000),   # 44 x 60, diagonal asymmetry — Incursion / Strike Force
    "search_and_destroy":  (750, 2000),   # 44 x 60, corner deployment — Incursion / Strike Force
    "sweeping_engagement": (1500, 3500),  # 44 x 90, long-axis Strike Force — Strike Force / Onslaught
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
