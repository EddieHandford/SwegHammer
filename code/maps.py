"""
Stock maps shipped with SwegHammer.

Add new maps here and register them in STOCK_MAPS so the front end can
pick them up automatically.
"""

import os

from .map import Map, Objective, Terrain, TerrainType

# ---------------------------------------------------------------------------
# REAL Pariah Nexus deployment geometry, read off the official deployment cards
# (https://wahapedia.ru/wh40k10ed/img/maps/cards/) on 2026-07-29 and measured
# from the printed dimension arrows. SWEG_MAP_REAL_GEOMETRY is ADOPTED
# default-on ("0" is the kill-switch), under the owner ruling to adopt on
# fidelity first. This is a FRAME change: it re-bases the metric and cannot be
# paired against an older anchor, so every figure predating it is on a different
# frame and a fresh re-anchor is mandatory.
#
# MEASURED, 22 factions, geometry off versus on, against real primary 29.1 and
# secondary 22.7:
#   mean primary   34.27 -> 31.78  (error +5.17 -> +2.68, roughly HALF removed)
#   mean secondary 12.50 -> 12.30  (error -10.20 -> -10.40, flat)
# So it halves the primary over-scoring and does NOTHING for secondary. The
# hypothesis that objective geometry starved the home-objective secondary cards
# is FALSIFIED — that gap is behavioural, not geometric.
#
# It also moves the headline the "wrong" way, and that is expected rather than a
# regression: gated mean absolute error 2.78 -> 3.35, because primary and
# secondary errors had been CANCELLING and correcting one exposed the other.
# Spearman rank correlation, which this project treats as the real signal,
# IMPROVED +0.375 -> +0.396 and Pearson +0.270 -> +0.334.
#
# The cards draw the long axis horizontally; this board is 44 wide by 60 high,
# so card-long maps to y and card-short to x. Army A holds low y.
#
# WHY IT MATTERS: every one of the five real cards places an objective INSIDE
# each player's deployment zone. The simulator's own layouts place none on three
# of five rotation maps, so Defend Stronghold (control an objective in your own
# zone) and Extend Battle Lines (own zone AND no-man's-land) cannot be scored by
# either player there. That is a geometric ceiling on secondary scoring which no
# piloting can lift, against a simulator scoring 11.8 secondary victory points
# versus a real 22.7. Confirms the wave-185 hypothesis at the quincunx docstring
# below, which until now rested on reasoning rather than on the cards.
_REAL_GEOMETRY = os.environ.get("SWEG_MAP_REAL_GEOMETRY", "1") != "0"

# Crucible of Battle — DIAGONAL triangles, not strips.
_CRUCIBLE_REAL_A = ((0.0, 0.0), (44.0, 0.0), (44.0, 30.0))
_CRUCIBLE_REAL_B = ((0.0, 30.0), (0.0, 60.0), (44.0, 60.0))
_CRUCIBLE_REAL_OBJ = (
    Objective(name="Centre",    x=22.0, y=30.0),
    Objective(name="A Home",    x=34.0, y=14.0),
    Objective(name="A Forward", x=8.0,  y=20.0),
    Objective(name="B Home",    x=10.0, y=46.0),
    Objective(name="B Forward", x=36.0, y=40.0),
)

# Tipping Point — STEPPED 12 and 20 inches. The objective layout is NOT
# identical to Crucible of Battle: two satellites match exactly and two differ
# by two inches (22 against 20), correcting a secondary source that called them
# the same layout.
_TIPPING_REAL_A = ((0.0, 0.0), (0.0, 12.0), (22.0, 12.0),
                   (22.0, 20.0), (44.0, 20.0), (44.0, 0.0))
_TIPPING_REAL_B = ((44.0, 60.0), (44.0, 48.0), (22.0, 48.0),
                   (22.0, 40.0), (0.0, 40.0), (0.0, 60.0))
_TIPPING_REAL_OBJ = (
    Objective(name="The Tipping Point", x=22.0, y=30.0),
    Objective(name="A Home",            x=34.0, y=14.0),
    Objective(name="A Forward",         x=8.0,  y=22.0),
    Objective(name="B Home",            x=10.0, y=46.0),
    Objective(name="B Forward",         x=36.0, y=38.0),
)

# Hammer and Anvil — flat strips EIGHTEEN inches deep, not twelve, and the
# objectives form a CROSS rather than the straight line the legacy layout uses.
_HAMMER_REAL_A = ((0.0, 0.0), (44.0, 0.0), (44.0, 18.0), (0.0, 18.0))
_HAMMER_REAL_B = ((0.0, 42.0), (44.0, 42.0), (44.0, 60.0), (0.0, 60.0))
_HAMMER_REAL_OBJ = (
    Objective(name="Centre",     x=22.0, y=30.0),
    Objective(name="A Home",     x=22.0, y=10.0),
    Objective(name="B Home",     x=22.0, y=50.0),
    Objective(name="West Flank", x=6.0,  y=30.0),
    Objective(name="East Flank", x=38.0, y=30.0),
)

# Search and Destroy — OPPOSING QUADRANTS, one objective 14 and 10 inches into
# each of the four quadrants plus a centre marker. The card also prints a 9-inch
# deployment-exclusion radius around the centre, which is NOT modelled here.
_SEARCH_REAL_A = ((22.0, 0.0), (44.0, 0.0), (44.0, 30.0), (22.0, 30.0))
_SEARCH_REAL_B = ((0.0, 30.0), (22.0, 30.0), (22.0, 60.0), (0.0, 60.0))
_SEARCH_REAL_OBJ = (
    Objective(name="Centre",       x=22.0, y=30.0),
    Objective(name="A Home",       x=34.0, y=14.0),
    Objective(name="B Home",       x=10.0, y=46.0),
    Objective(name="Neutral West", x=10.0, y=14.0),
    Objective(name="Neutral East", x=34.0, y=46.0),
)

# NOT CONVERTED, with the reasons recorded rather than guessed:
#   Take and Hold is a MISSION, not a deployment, so no card defines its marker
#   placement; the layout there is the simulator's own design.
#   Sweeping Engagement deploys from the LONG edges, so its zones split along
#   the short axis (x) rather than along y. The deployment convention throughout
#   this project, including code/secondaries.py, assumes A is low-y, so
#   representing it needs that convention generalised first. It is already out
#   of the rotation for an unrelated reason (wrong footprint), so nothing
#   regresses by leaving it.
# ---------------------------------------------------------------------------


def _quincunx_objectives(width: float, height: float) -> tuple:
    """
    Five-objective layout common to most 10e missions (Take and Hold, Crucible,
    Tipping Point, etc.): one in the centre and four equidistant points roughly
    a third of the way in from each board edge.

    Wave 185 (#66 map-objective fidelity, env-gated SWEG_OBJ_HOME): the legacy
    quincunx places ALL five markers in No Man's Land (inset_y=0.25 â†’ y=15/45 on a
    44x60 board whose 12" deployment zones are y<=12 / y>=48), so a HOME objective
    in a player's own deployment zone NEVER exists. That makes the real
    Chapter Approved 2025-26 board secondaries Defend Stronghold (control an
    objective in your OWN deployment zone) and Extend Battle Lines (own zone AND
    No Man's Land) mathematically UNACHIEVABLE â€” a scoring-fidelity gap, not a
    rule the real game has (those cards are scored in real play, so real
    deployment maps DO place home objectives in deployment zones). The gated layout
    re-lays the four outer markers to the faithful HOME + FLANK pattern: one home
    objective inside each deployment zone (on the centre line) plus two mid-board
    flank markers in No Man's Land, keeping the centre. Even-handed by 180-degree
    rotational symmetry (home-A <-> home-B, flank-left <-> flank-right). The OFF
    path is byte-identical. Cited `terrain.objective_home_markers`.
    """
    cx, cy = width / 2.0, height / 2.0
    if os.environ.get("SWEG_OBJ_HOME") == "1":
        # Home objective ~8" from each short edge â†’ inside the 12"-deep
        # deployment zone, as on the real Pariah Nexus deployment maps; two flank
        # markers at mid-board (No Man's Land); centre unchanged.
        home_inset = 8.0
        flank_x = width * 0.30
        return (
            Objective(name="Centre",      x=cx, y=cy),
            Objective(name="Home A",      x=cx, y=home_inset),
            Objective(name="Home B",      x=cx, y=height - home_inset),
            Objective(name="West Flank",  x=cx - flank_x, y=cy),
            Objective(name="East Flank",  x=cx + flank_x, y=cy),
        )
    inset_x = width * 0.30
    inset_y = height * 0.25
    return (
        Objective(name="Centre",    x=cx, y=cy),
        Objective(name="NW Marker", x=cx - inset_x, y=cy + inset_y),
        Objective(name="NE Marker", x=cx + inset_x, y=cy + inset_y),
        Objective(name="SW Marker", x=cx - inset_x, y=cy - inset_y),
        Objective(name="SE Marker", x=cx + inset_x, y=cy - inset_y),
    )


def _competitive_terrain(width: float, height: float, dense_layout=None) -> tuple:
    """Build a competitive-density Pariah Nexus terrain layout for a board of the
    given size, EVEN-HANDED by construction via 180-degree rotational symmetry
    about the board centre (so neither deployment zone gets a terrain advantage).

    ``dense_layout`` (a stock-map key such as ``"crucible_of_battle"``) selects one
    of the SOURCED published tournament layouts used by the env-gated
    ``SWEG_TERRAIN_DENSE`` path below. It is IGNORED on the default (gate-off) path,
    so the argument never changes the byte-identical baseline.

    SWEG_TERRAIN_DENSE (default-off, byte-identical off): the Wave-97 default layout
    below is a homebrew competitive-density approximation built from eleven SMALL
    ruins (five-to-six-inch footprints); dense fields of small pieces still leave
    firing lanes between them, so the static Chaos / Imperial Knights gunline can
    fire across the board and the sim over-credits it (a diagnostic measured
    72.8 percent of the opponent's shots into a Knights gunline dealing zero damage
    while the opponent walked through open ground). The real published Pariah Nexus
    tournament layouts instead use a FEW LARGE line-of-sight-blocking ruins (roughly
    six-to-ten-inch footprints, about eight ruins plus two to three Woods per board)
    arranged as a central ruin mass with flanking ruins so there is no clean
    deployment-zone-to-deployment-zone sightline. When ``SWEG_TERRAIN_DENSE`` is set
    to ``"1"`` this function returns those sourced layouts (see
    ``_dense_competitive_terrain``); when unset it returns the Wave-97 layout below
    unchanged. Cited ``terrain.competitive_density``.

    Reproduces the published competitive standard rather than tuning a metric:
    the Games Workshop Pariah Nexus Tournament Companion ships eight measured
    layouts on a 44 by 60 inch board, each a dense field of large two-storey
    L-shaped ruins (roughly five-to-six inch footprints, which block line of
    sight under the current 10e Ruins rule) plus smaller scatter pieces, placed
    as a central ruin mass with flanking ruins so that there is no clean
    deployment-zone-to-deployment-zone sightline. Our previous stock maps carried
    only three to seven small pieces (about eight percent coverage with little
    line-of-sight blocking), which let table-wide shooters fire across an open
    board and starved advancing armies of cover. Cited as
    `terrain.competitive_pariah_nexus_layout`.

    PRIME-DIRECTIVE / EVEN-HANDED: terrain is faction-neutral. The structure is
    the published competitive pattern (central plus flanking, rotationally
    symmetric); it is NOT tuned to favour or disfavour any faction, and the
    objectives are left exactly where each mission places them. Correct even if
    it moved the metric the wrong way, because it matches the real layouts.

    Seed pieces are defined for one half of the board as
    ``(name, fx, fy, w, h, type)`` where ``fx``/``fy`` are fractions of the board
    (so the pattern scales to 44x60 and 44x90 alike) and ``w``/``h`` are physical
    inches (ruins stay roughly five-to-six inches regardless of board length).
    Each non-central seed is emitted together with its 180-degree partner.
    """
    # ADOPTED DEFAULT-ON (2026-07-14): the sourced GW Pariah Nexus competitive
    # layouts are the faithful terrain (correctly-shaped large line-of-sight
    # blockers, no clean deployment-zone-to-deployment-zone sightline) versus the
    # homebrew Wave-97 approximation below (small scatter pieces that leave clean
    # firing lanes and over-credit the static gunline). Adopted fidelity-first per
    # the owner's doctrine: it is the real competitive standard, so it is the
    # default even though the paired re-anchor read a metric regression (gated
    # 2.30 -> 3.00, N=40 vs sc66a) whose new craters (T'au -9.1, Necrons +8.1) and
    # the favourable Astra Militarum nudge (+2.6) become the next residuals to
    # work. SWEG_TERRAIN_DENSE=0 is the byte-identical kill-switch back to the
    # Wave-97 homebrew layout. Cited `terrain.competitive_density`.
    if os.environ.get("SWEG_TERRAIN_DENSE", "1") != "0":
        return _dense_competitive_terrain(width, height, dense_layout)
    R = TerrainType.RUIN
    O = TerrainType.OBSCURING
    L = TerrainType.LIGHT_COVER
    # Lower/left-half seeds; partners are generated by 180-degree rotation.
    seeds = (
        # Flanking ruins near the deployment-zone corners (break the long
        # diagonal and edge sightlines). Mirrors cover the opposite corners.
        ("Corner Ruin",     0.07, 0.20, 6.0, 6.0, R),
        ("Corner Ruin",     0.71, 0.18, 6.0, 6.0, R),
        # Mid-field ruins flanking the central mass (break the lateral lanes).
        ("Flank Ruin",      0.25, 0.33, 5.0, 6.0, R),
        ("Flank Ruin",      0.56, 0.30, 5.0, 6.0, R),
        # A ruin sealing the central vertical lane near each deployment zone.
        ("Approach Ruin",   0.43, 0.16, 5.0, 5.0, R),
        # Woods (Obscuring) on the wings for advancing cover.
        ("Flank Wood",      0.03, 0.40, 5.0, 6.0, O),
        # Barricade lines (light cover) ahead of each deployment zone.
        ("Forward Barricade", 0.28, 0.12, 8.0, 2.0, L),
        ("Mid Barricade",   0.10, 0.46, 6.0, 2.0, L),
    )
    out = []
    # A large central ruin mass, self-symmetric about the centre â€” the spine
    # that denies the dead-centre cross-table sightline.
    cw, ch = 8.0, 8.0
    out.append(Terrain("Central Ruin", width / 2.0 - cw / 2.0,
                       height / 2.0 - ch / 2.0, cw, ch, TerrainType.RUIN))
    for (name, fx, fy, w, h, t) in seeds:
        x, y = fx * width, fy * height
        out.append(Terrain(name, x, y, w, h, t))
        rx, ry = width - x - w, height - y - h
        # Skip a degenerate self-overlapping partner (none here, but guard it).
        if abs(rx - x) < 1e-6 and abs(ry - y) < 1e-6:
            continue
        out.append(Terrain(name + " (mirror)", rx, ry, w, h, t))
    return tuple(out)


# ---------------------------------------------------------------------------
# SWEG_TERRAIN_DENSE â€” sourced competitive Pariah Nexus tournament layouts
# ---------------------------------------------------------------------------
#
# The Wave-97 default `_competitive_terrain` reproduces the competitive DENSITY
# with a homebrew field of eleven small (five-to-six-inch) ruins, but a dense
# field of small pieces still leaves clean firing lanes between them, so it did
# not close the static-gunline over-credit (the Chaos / Imperial Knights gunline
# still fires table-wide). The REAL published Pariah Nexus tournament layouts use
# a FEW LARGE line-of-sight-blocking ruins (about eight ruins of six-to-ten-inch
# footprints, plus two to three Woods) arranged as a central ruin mass with
# flanking ruins so there is no clean deployment-zone-to-deployment-zone sightline.
#
# SOURCE. The per-map layouts below reproduce the STRUCTURE of the eight numbered
# Games Workshop Pariah Nexus tournament terrain layouts as published by Glass
# Hammer Gaming's measured Pariah Nexus terrain guide (archived copy:
# https://web.archive.org/web/20250804222340/https://www.glasshammergaming.co.uk/GHG-TERRAIN-PARIAH-NEXUS.pdf),
# which draws each of the deployment-named layouts (Crucible of Battle, Hammer and
# Anvil, Tipping Point, Search and Destroy, Dawn of War, Sweeping Engagement) on a
# 44 by 60 inch board with roughly eight large L-shaped / block ruins plus two to
# three Woods. The GHG diagrams give board-edge measurements but are isometric-
# tinged top-downs, so exact per-piece coordinates are APPROXIMATED from the
# sourced piece counts, footprint sizes and placement pattern (central mass plus
# flanking ruins, per-deployment structure), NOT transcribed pixel-for-pixel â€” an
# approximation the citation records explicitly.
#
# EVEN-HANDED / PRIME DIRECTIVE. Each layout is built by 180-degree rotational
# symmetry about the board centre, exactly like `_competitive_terrain`. Army A
# always deploys along the bottom edge and Army B along the top edge
# (code.simulator.Battle._deploy_armies), so a 180-degree rotation maps one
# deployment zone onto the other and neither side gets a terrain advantage. The
# terrain is faction-neutral and is NOT tuned to move any faction's win rate; only
# the terrain changes, the mission's deployment zones and objectives are untouched.
# Ruins are the existing line-of-sight-blocking RUIN type (passable â€” the 10e
# INFANTRY/BEAST move-through-walls rule â€” and grant Benefit of Cover); no piece is
# IMPASSABLE, so no objective marker can ever fall inside impassable terrain.
#
# Each named layout is a list of LOWER-half seed pieces `(name, x, y, w, h, type)`
# in inches; every seed is emitted together with its 180-degree partner. Optional
# `centrals` are self-symmetric pieces placed on the board centre (their own
# 180-degree image, so they are emitted once). Cited `terrain.competitive_density`.

_DENSE_LAYOUTS = {
    # Crucible of Battle â€” diagonal deployment: a heavier ruin mass on one
    # diagonal (big corner bastion) with a central knot sealing the centre lane.
    "crucible_of_battle": (
        (
            ("Corner Bastion", 5.0, 15.0, 9.0, 7.0, "R"),
            ("Centre Knot",   14.0, 23.0, 10.0, 6.0, "R"),
            ("Diagonal Flank", 30.0, 9.0, 8.0, 6.0, "R"),
            ("Front Ruin",    19.0, 4.0, 8.0, 5.0, "R"),
            ("Flank Wood",    33.0, 21.0, 5.0, 5.0, "O"),
        ),
        (),
    ),
    # Hammer and Anvil â€” two big central redoubts stacked across the centreline
    # with flanking ruins ahead of each deployment zone.
    "hammer_and_anvil": (
        (
            ("Central Redoubt", 15.0, 19.0, 10.0, 8.0, "R"),
            ("West Flank",       3.0, 14.0, 8.0, 6.0, "R"),
            ("East Flank",      33.0, 14.0, 8.0, 6.0, "R"),
            ("Front Bunker",     8.0, 4.0, 6.0, 5.0, "R"),
            ("Mid Wood",        30.0, 22.0, 5.0, 5.0, "O"),
        ),
        (
            ("Central Copse", 5.0, 5.0, "O"),
        ),
    ),
    # Tipping Point â€” three ruin columns (left / centre / right) ringing the
    # central objective, which sits in a central copse.
    "tipping_point": (
        (
            ("West Column",  4.0, 17.0, 8.0, 9.0, "R"),
            ("Centre Ruin", 15.0, 22.0, 9.0, 6.0, "R"),
            ("East Column", 32.0, 17.0, 8.0, 9.0, "R"),
            ("Front Ruin",  18.0, 5.0, 8.0, 5.0, "R"),
            ("Wing Wood",   33.0, 28.0, 5.0, 5.0, "O"),
        ),
        (
            ("Central Copse", 5.0, 5.0, "O"),
        ),
    ),
    # Search and Destroy â€” corner clusters of ruins with a central ruin sealing
    # the middle (opposing-corner push).
    "search_and_destroy": (
        (
            ("Corner Cluster A", 4.0, 7.0, 8.0, 6.0, "R"),
            ("Corner Cluster B", 6.0, 18.0, 7.0, 6.0, "R"),
            ("Centre Ruin",     16.0, 23.0, 9.0, 6.0, "R"),
            ("Flank Ruin",      31.0, 11.0, 8.0, 6.0, "R"),
            ("Mid Wood",        30.0, 22.0, 5.0, 5.0, "O"),
        ),
        (),
    ),
    # Take and Hold â€” the symmetric Dawn of War three-by-three grid of ruins with
    # a central copse over the middle no-man's-land.
    "take_and_hold": (
        (
            ("SW Ruin",       4.0, 6.0, 7.0, 6.0, "R"),
            ("SE Ruin",      33.0, 6.0, 7.0, 6.0, "R"),
            ("Mid-West Ruin", 4.0, 23.0, 7.0, 6.0, "R"),
            ("Centre Ruin",  16.0, 21.0, 9.0, 7.0, "R"),
            ("Wing Wood",    33.0, 26.0, 5.0, 5.0, "O"),
        ),
        (
            ("Central Copse", 5.0, 5.0, "O"),
        ),
    ),
    # Sweeping Engagement â€” long-axis spine: flanking ruins with a central ruin
    # and a forward chevron ahead of each deployment zone.
    "sweeping_engagement": (
        (
            ("West Ruin",    4.0, 14.0, 8.0, 6.0, "R"),
            ("Centre Ruin", 15.0, 22.0, 9.0, 6.0, "R"),
            ("East Ruin",   32.0, 12.0, 8.0, 6.0, "R"),
            ("Front Chevron", 18.0, 5.0, 8.0, 5.0, "R"),
            ("Flank Wood",   8.0, 26.0, 5.0, 5.0, "O"),
        ),
        (),
    ),
}


def _dense_generic_seeds(width: float, height: float):
    """Fallback dense layout for boards without a named sourced layout (e.g. the
    44x90 Onslaught boards). Positions scale with the board (fractions) while the
    ruin footprints stay physically large; structure is central-mass-plus-flanks
    like the named layouts, 180-degree symmetric, central copse sealing the centre."""
    w, h = width, height
    lower = (
        ("West Ruin",   0.10 * w, 0.22 * h, 8.0, 6.0, "R"),
        ("Centre Ruin", 0.34 * w, 0.35 * h, 9.0, 6.0, "R"),
        ("East Ruin",   0.72 * w, 0.20 * h, 8.0, 6.0, "R"),
        ("Front Ruin",  0.40 * w, 0.08 * h, 8.0, 5.0, "R"),
        ("Flank Wood",  0.75 * w, 0.40 * h, 5.0, 5.0, "O"),
    )
    centrals = (("Central Copse", 5.0, 5.0, "O"),)
    return lower, centrals


def _dense_competitive_terrain(width: float, height: float, layout=None) -> tuple:
    """Sourced competitive Pariah Nexus tournament layout (SWEG_TERRAIN_DENSE=1).

    See the module comment above for the source, the approximation note and the
    even-handedness construction. Returns a tuple of `Terrain`. Ruins are the
    line-of-sight-blocking RUIN type; Woods are OBSCURING. Every non-central seed
    is emitted with its 180-degree rotational partner about the board centre."""
    type_map = {"R": TerrainType.RUIN, "O": TerrainType.OBSCURING,
                "L": TerrainType.LIGHT_COVER}
    if layout in _DENSE_LAYOUTS:
        lower, centrals = _DENSE_LAYOUTS[layout]
    else:
        lower, centrals = _dense_generic_seeds(width, height)
    out = []
    for (name, x, y, w, h, tcode) in lower:
        t = type_map[tcode]
        out.append(Terrain(name, x, y, w, h, t))
        rx, ry = width - x - w, height - y - h
        # Guard against a degenerate self-overlapping partner (none in the
        # tuned layouts, but keep the invariant explicit).
        if abs(rx - x) < 1e-6 and abs(ry - y) < 1e-6:
            continue
        out.append(Terrain(name + " (mirror)", rx, ry, w, h, t))
    for (name, w, h, tcode) in centrals:
        t = type_map[tcode]
        out.append(Terrain(name, width / 2.0 - w / 2.0,
                           height / 2.0 - h / 2.0, w, h, t))
    return tuple(out)


COMBAT_PATROL_BASIC = Map(
    name="Combat Patrol - Open Field",
    width=44.0,
    height=60.0,
    objectives=_quincunx_objectives(44.0, 60.0),
    terrain=_competitive_terrain(44.0, 60.0),
    deployment_width=12.0,
)


URBAN_SPRAWL = Map(
    name="Strike Force - Urban Sprawl",
    width=44.0,
    height=90.0,
    objectives=_quincunx_objectives(44.0, 90.0),
    terrain=_competitive_terrain(44.0, 90.0),
    deployment_width=12.0,
)


OPEN_PLAINS = Map(
    name="Combat Patrol - Open Plains",
    width=44.0,
    height=60.0,
    objectives=_quincunx_objectives(44.0, 60.0),
    terrain=_competitive_terrain(44.0, 60.0),
    deployment_width=12.0,
)


# ---------------------------------------------------------------------------
# 10e mission-deployment maps with genuine asymmetry
# ---------------------------------------------------------------------------

CRUCIBLE_OF_BATTLE = Map(
    name="Crucible of Battle",
    width=44.0,
    height=60.0,
    objectives=(_CRUCIBLE_REAL_OBJ if _REAL_GEOMETRY
                else _quincunx_objectives(44.0, 60.0)),
    deployment_polygon_a=_CRUCIBLE_REAL_A if _REAL_GEOMETRY else (),
    deployment_polygon_b=_CRUCIBLE_REAL_B if _REAL_GEOMETRY else (),
    # Diagonal asymmetry: heavy terrain on the NE-SW diagonal, light on NW-SE.
    # Large ruin top-right, wooded copse mid-left, two short barricade ridges
    # bridging them, one impassable wall blocking centre.
    terrain=_competitive_terrain(44.0, 60.0, dense_layout="crucible_of_battle"),
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
    objectives=(_SEARCH_REAL_OBJ if _REAL_GEOMETRY
                else _search_and_destroy_objectives(44.0, 60.0)),
    deployment_polygon_a=_SEARCH_REAL_A if _REAL_GEOMETRY else (),
    deployment_polygon_b=_SEARCH_REAL_B if _REAL_GEOMETRY else (),
    # The card's printed 9-inch no-deployment radius around board centre. Needed
    # for correctness here, not flavour: the four quadrants meet at the centre,
    # so without it the central objective falls on a zone corner and is wrongly
    # credited to one side.
    deployment_exclusion_radius=9.0 if _REAL_GEOMETRY else 0.0,
    # Corner deployment: NW and SE clusters of terrain, central no-man's-land
    # mostly open. Players push out of corners across exposed ground to
    # contest mid-board objectives.
    terrain=_competitive_terrain(44.0, 60.0, dense_layout="search_and_destroy"),
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
    terrain=_competitive_terrain(44.0, 90.0),
    deployment_width=12.0,
)


# Sweeping Engagement at the 2000-point Strike Force footprint (44x60). The
# original SWEEPING_ENGAGEMENT above is a 44x90 Onslaught-size board, which is
# the wrong footprint for the 2000-point rotation, so it was excluded from
# PARIAH_NEXUS_2K_ROTATION â€” leaving Sweeping Engagement, one of the five real
# Pariah Nexus deployments, untested at 2000 points. This 44x60 version restores
# it at the correct size so the full deployment set can be screened. Gated into
# the rotation via SWEG_FULL_DEPLOY_ROTATION (default-off, byte-identical) â€” see
# PARIAH_NEXUS_2K_ROTATION_FULL and evaluate_vs_meta._pick_rotation_map.
SWEEPING_ENGAGEMENT_2K = Map(
    name="Sweeping Engagement (2K)",
    width=44.0,
    height=60.0,
    objectives=_sweeping_engagement_objectives(44.0, 60.0),
    terrain=_competitive_terrain(44.0, 60.0, dense_layout="sweeping_engagement"),
    deployment_width=12.0,
)


def _take_and_hold_objectives(width: float, height: float) -> tuple:
    """
    Take and Hold (Pariah Nexus mission): 4 objectives in the no-man's-land,
    none on the deployment-zone centre-line. Forces players to push forward
    out of their DZ to score. Classic objective control test.
    """
    cx, cy = width / 2.0, height / 2.0
    return (
        Objective(name="South Centre", x=cx,            y=height * 0.33),
        Objective(name="North Centre", x=cx,            y=height * 0.67),
        Objective(name="West Mid",     x=width * 0.25,  y=cy),
        Objective(name="East Mid",     x=width * 0.75,  y=cy),
    )


TAKE_AND_HOLD = Map(
    name="Take and Hold",
    width=44.0,
    height=60.0,
    objectives=_take_and_hold_objectives(44.0, 60.0),
    # 4 mid-board objectives, no central; classic Pariah Nexus push-forward
    # mission. Light cover scattered across no-man's-land, two large ruins
    # at the wings.
    terrain=_competitive_terrain(44.0, 60.0, dense_layout="take_and_hold"),
    deployment_width=12.0,
)


def _hammer_and_anvil_objectives(width: float, height: float) -> tuple:
    """
    Hammer and Anvil (Pariah Nexus mission): short-edge deployment with the
    map's long axis running between the deployment zones. 5 objectives
    strung along the long axis. Long travel distance â€” slow factions
    struggle to project across the map.
    """
    cx = width / 2.0
    return (
        Objective(name="South DZ Edge",  x=cx,           y=height * 0.20),
        Objective(name="South Mid",      x=cx,           y=height * 0.35),
        Objective(name="Centre",         x=cx,           y=height * 0.50),
        Objective(name="North Mid",      x=cx,           y=height * 0.65),
        Objective(name="North DZ Edge",  x=cx,           y=height * 0.80),
    )


HAMMER_AND_ANVIL = Map(
    name="Hammer and Anvil",
    width=44.0,
    height=60.0,
    objectives=(_HAMMER_REAL_OBJ if _REAL_GEOMETRY
                else _hammer_and_anvil_objectives(44.0, 60.0)),
    deployment_polygon_a=_HAMMER_REAL_A if _REAL_GEOMETRY else (),
    deployment_polygon_b=_HAMMER_REAL_B if _REAL_GEOMETRY else (),
    # Short-edge deployment (DZ width=12.0 on each short edge, leaving a 36"
    # no-man's-land along the long axis). Terrain alternates side-to-side
    # along the long axis to channel movement.
    terrain=_competitive_terrain(44.0, 60.0, dense_layout="hammer_and_anvil"),
    deployment_width=12.0,
)


def _tipping_point_objectives(width: float, height: float) -> tuple:
    """
    Tipping Point (Pariah Nexus mission): one central objective plus four
    corner-ish objectives at midfield.

    NOT SOURCED. These coordinates are a designed layout, not the real
    deployment card's marker placement â€” nothing in this module cites a
    Pariah Nexus diagram (see task #62). Two specific doubts are on record and
    unresolved: Tabletop Battles describes Tipping Point as reusing "the
    objective positioning from Crucible of Battle", which this does not match
    (Crucible sits at y=45/15, this at y=39/21); and the real deployment zones
    are stepped rather than the flat 12-inch strip the Map object applies.

    An earlier version of this docstring said the central objective was "worth
    more than the rest". It never was â€” every objective here carries the
    default vp_per_round of 5, the centre included. Corrected rather than
    implemented, because the real per-marker value IS 5 in Pariah Nexus and
    the claim appears to have been intent that was never built.
    """
    cx, cy = width / 2.0, height / 2.0
    return (
        Objective(name="The Tipping Point", x=cx,           y=cy),
        Objective(name="NW Bastion",        x=width * 0.20, y=height * 0.65),
        Objective(name="NE Bastion",        x=width * 0.80, y=height * 0.65),
        Objective(name="SW Bastion",        x=width * 0.20, y=height * 0.35),
        Objective(name="SE Bastion",        x=width * 0.80, y=height * 0.35),
    )


TIPPING_POINT = Map(
    name="Tipping Point",
    width=44.0,
    height=60.0,
    objectives=(_TIPPING_REAL_OBJ if _REAL_GEOMETRY
                else _tipping_point_objectives(44.0, 60.0)),
    deployment_polygon_a=_TIPPING_REAL_A if _REAL_GEOMETRY else (),
    deployment_polygon_b=_TIPPING_REAL_B if _REAL_GEOMETRY else (),
    # Central objective surrounded by 4 satellite objectives. Terrain
    # forms a ring around the centre â€” taking it requires committing
    # through exposed lanes between the ring features.
    terrain=_competitive_terrain(44.0, 60.0, dense_layout="tipping_point"),
    deployment_width=12.0,
)



STOCK_MAPS = {
    "combat_patrol":       COMBAT_PATROL_BASIC,
    "open_plains":         OPEN_PLAINS,
    "urban_sprawl":        URBAN_SPRAWL,
    "crucible_of_battle":  CRUCIBLE_OF_BATTLE,
    "search_and_destroy":  SEARCH_AND_DESTROY,
    "sweeping_engagement": SWEEPING_ENGAGEMENT,
    # SC4-D â€” additional Pariah Nexus mission shapes for eval rotation.
    "take_and_hold":       TAKE_AND_HOLD,
    "hammer_and_anvil":    HAMMER_AND_ANVIL,
    "tipping_point":       TIPPING_POINT,
    "sweeping_engagement_2k": SWEEPING_ENGAGEMENT_2K,
}

# SC4-D â€” Pariah Nexus mission rotation. evaluate_vs_meta cycles through
# this list per (faction-pair, seed) so each pair sees variety. Keeps
# `DEFAULT_MAP` (COMBAT_PATROL_BASIC) for one-off battles / tests that
# don't need a curated rotation.
PARIAH_NEXUS_2K_ROTATION: tuple = (
    "crucible_of_battle",   # diagonal asymmetry, 44x60
    "take_and_hold",        # 4 mid-board objectives, no centre
    "hammer_and_anvil",     # short-edge deployment, long-axis fight
    "tipping_point",        # central objective with 4 satellites
    "search_and_destroy",   # opposing corners
)

# Full deployment rotation including Sweeping Engagement at the correct 2000-point
# 44x60 footprint â€” restores the fifth real Pariah Nexus deployment that the base
# rotation omits (the stock SWEEPING_ENGAGEMENT is 44x90, the wrong size for 2K).
# Gated via SWEG_FULL_DEPLOY_ROTATION (default-off) in
# evaluate_vs_meta._pick_rotation_map so the production frame is byte-identical
# until a deliberate re-anchor adopts the six-map rotation. Adoption is a
# frame-change (re-bases the metric) and must be screened with a full N=80
# re-anchor, per docs/EVAL_PROTOCOL.md.
PARIAH_NEXUS_2K_ROTATION_FULL: tuple = PARIAH_NEXUS_2K_ROTATION + (
    "sweeping_engagement_2k",   # long-axis spine, 44x60 (the restored 5th deployment)
)

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
    "combat_patrol":       (250, 1250),   # 44 x 60, ruin + barricade â€” Combat Patrol / Incursion
    "open_plains":         (500, 2000),   # 44 x 60, sparse terrain â€” Strike Force friendly
    "urban_sprawl":        (1500, 3500),  # 44 x 90, asymmetric â€” Strike Force / Onslaught
    "crucible_of_battle":  (750, 2000),   # 44 x 60, diagonal asymmetry â€” Incursion / Strike Force
    "search_and_destroy":  (750, 2000),   # 44 x 60, corner deployment â€” Incursion / Strike Force
    "sweeping_engagement": (1500, 3500),  # 44 x 90, long-axis Strike Force â€” Strike Force / Onslaught
    "take_and_hold":       (750, 2000),   # 44 x 60, 4 mid-board objectives â€” Strike Force
    "hammer_and_anvil":    (750, 2000),   # 44 x 60, short-edge deployment â€” Strike Force
    "tipping_point":       (750, 2000),   # 44 x 60, central + 4 satellites â€” Strike Force
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
