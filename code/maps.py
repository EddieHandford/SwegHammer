"""
Stock maps shipped with SwegHammer.

Add new maps here and register them in STOCK_MAPS so the front end can
pick them up automatically.
"""

from __future__ import annotations

from .map import Map, Terrain, TerrainType


COMBAT_PATROL_BASIC = Map(
    name="Combat Patrol - Open Field",
    width=44.0,
    height=60.0,
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
