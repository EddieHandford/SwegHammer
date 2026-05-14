"""
Matplotlib top-down renderer for SwegHammer battles.

Given a Map and an event log, ``render_frame(map, events, tick)`` returns a
matplotlib Figure showing the world state after replaying ``events[:tick+1]``.
The renderer is read-only: it never mutates the simulator state, so the same
event log can be scrubbed forwards and backwards.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse, Rectangle

from .events import (
    BattleEnded, BattleStarted, BattleshockFailed, ObjectiveScored,
    RoundEnded, RoundStarted, UnitActivated, UnitAdvanced, UnitCharged,
    UnitDeepStrike, UnitFought, UnitInfiltrated, UnitKilled, UnitMoved,
    UnitScouted, UnitShot,
)
from .map import Map, TerrainType


# ---------------------------------------------------------------------------
# Visual palette
# ---------------------------------------------------------------------------

COL_FIG_BG = "#0e1117"
COL_BOARD_BG = "#3a3530"
COL_GRID = "#5a5550"

TERRAIN_COLORS = {
    TerrainType.LIGHT_COVER: "#8b6f47",   # brown barricades
    TerrainType.HEAVY_COVER: "#6e6e6e",   # grey ruins
    TerrainType.OBSCURING:   "#3f5c3a",   # dark green woods
    TerrainType.IMPASSABLE:  "#1a1a1a",   # black wall
}

COL_ARMY_A = "#4e9af1"   # blue
COL_ARMY_B = "#e05c5c"   # red
COL_DEAD   = "#444444"

COL_MOVE_ARROW = "#cccccc"
COL_SHOT_ARROW = "#f7d147"
COL_CHARGE_ARROW = "#ff7f3f"   # orange — charge declaration
COL_MELEE_FLASH = "#e05c5c"    # red — melee strike
COL_OBJECTIVE = "#ffd700"      # gold — objective marker


# ---------------------------------------------------------------------------
# State reconstruction
# ---------------------------------------------------------------------------

def reconstruct_state(events: List, tick: int) -> Dict[str, dict]:
    """Replay events[:tick+1] and return uid -> state dict.

    Each state dict carries: name, army, position, current_hp, max_hp, alive.
    """
    state: Dict[str, dict] = {}
    for ev in events:
        if isinstance(ev, BattleStarted):
            for u in ev.units:
                state[u.uid] = {
                    "name": u.name,
                    "army": u.army,
                    "position": u.position,
                    "current_hp": u.max_health,
                    "max_hp": u.max_health,
                    "alive": True,
                    "unit_keywords": tuple(getattr(u, "unit_keywords", ()) or ()),
                }
            break

    for ev in events[: tick + 1]:
        if isinstance(ev, UnitMoved):
            if ev.unit_uid in state:
                state[ev.unit_uid]["position"] = ev.to_pos
        elif isinstance(ev, UnitScouted):
            if ev.unit_uid in state:
                state[ev.unit_uid]["position"] = ev.to_pos
        elif isinstance(ev, (UnitDeepStrike, UnitInfiltrated)):
            if ev.unit_uid in state:
                state[ev.unit_uid]["position"] = ev.position
        elif isinstance(ev, UnitShot):
            if ev.target_uid in state:
                state[ev.target_uid]["current_hp"] = ev.target_hp_after
                if not ev.target_alive_after:
                    state[ev.target_uid]["alive"] = False
        elif isinstance(ev, UnitKilled):
            if ev.unit_uid in state:
                state[ev.unit_uid]["alive"] = False
                state[ev.unit_uid]["current_hp"] = 0.0
    return state


def _current_round(events: List, tick: int) -> int:
    r = 0
    for ev in events[: tick + 1]:
        if isinstance(ev, RoundStarted):
            r = ev.round_num
    return r


def _army_names(events: List) -> tuple:
    for ev in events:
        if isinstance(ev, BattleStarted):
            return ev.army_a_name, ev.army_b_name
    return "Army A", "Army B"


# ---------------------------------------------------------------------------
# Shape dispatcher — unit silhouette varies with 10e keywords
# ---------------------------------------------------------------------------

# Shape hint tags. The renderer interprets these when drawing a unit. We keep
# them as small inert strings so they're trivial to assert on in tests and
# easy to extend without touching the dispatcher.
SHAPE_LARGE_RECT = "large_rect"        # TITANIC / TOWERING
SHAPE_MEDIUM_RECT = "medium_rect"      # VEHICLE / WALKER (non-Titanic)
SHAPE_LARGE_CIRCLE = "large_circle"    # MONSTER
SHAPE_ELLIPSE = "ellipse"              # BIKE / MOUNTED
SHAPE_SWARM = "swarm"                  # SWARM — cluster of jittered dots
SHAPE_CHARACTER_CIRCLE = "character_circle"  # CHARACTER — small circle, thick outline
SHAPE_SMALL_CIRCLE = "small_circle"    # default INFANTRY


def _shape_for(unit_keywords) -> tuple:
    """Map a unit's 10e keyword set to a (shape_tag, size_hint) pair.

    Keywords are checked in priority order, biggest silhouettes first, so
    e.g. a "TITANIC, VEHICLE" unit renders as a large rectangle rather than
    a medium one. CHARACTER takes precedence over plain INFANTRY but loses
    to anything bigger (a Vehicle-CHARACTER reads as a vehicle).

    Returns:
        (shape_tag, size_hint) where size_hint is either a scatter ``s=``
        value for circle/swarm tags or a (width, height) tuple in world
        inches for rectangle/ellipse tags.
    """
    kw = set(k.upper() for k in (unit_keywords or ()))
    if "TITANIC" in kw or "TOWERING" in kw:
        return SHAPE_LARGE_RECT, (1.5, 2.0)
    if "VEHICLE" in kw or "WALKER" in kw:
        return SHAPE_MEDIUM_RECT, (0.8, 1.4)
    if "MONSTER" in kw:
        return SHAPE_LARGE_CIRCLE, 180
    if "BIKE" in kw or "MOUNTED" in kw:
        return SHAPE_ELLIPSE, (0.4, 0.7)
    if "SWARM" in kw:
        return SHAPE_SWARM, 30
    if "CHARACTER" in kw:
        return SHAPE_CHARACTER_CIRCLE, 100
    return SHAPE_SMALL_CIRCLE, 100


def _draw_unit_shape(ax, x: float, y: float, color: str,
                     shape_tag: str, size_hint) -> None:
    """Draw a single alive unit using the shape dispatcher's output."""
    if shape_tag == SHAPE_LARGE_RECT:
        w, h = size_hint
        ax.add_patch(Rectangle(
            (x - w / 2, y - h / 2), w, h,
            facecolor=color, edgecolor="white", linewidth=1.0, zorder=5,
        ))
    elif shape_tag == SHAPE_MEDIUM_RECT:
        w, h = size_hint
        ax.add_patch(Rectangle(
            (x - w / 2, y - h / 2), w, h,
            facecolor=color, edgecolor="white", linewidth=0.9, zorder=5,
        ))
    elif shape_tag == SHAPE_LARGE_CIRCLE:
        ax.scatter([x], [y], s=size_hint, c=color, edgecolors="white",
                   linewidths=1.0, zorder=5)
    elif shape_tag == SHAPE_ELLIPSE:
        w, h = size_hint
        ax.add_patch(Ellipse(
            (x, y), w, h,
            facecolor=color, edgecolor="white", linewidth=0.9, zorder=5,
        ))
    elif shape_tag == SHAPE_SWARM:
        # Cluster of 5 small dots jittered around the centre. Deterministic
        # offsets so the same unit always draws the same swarm pattern.
        offsets = [(0.0, 0.0), (0.3, 0.15), (-0.25, 0.2), (0.15, -0.3), (-0.2, -0.18)]
        xs = [x + dx for dx, _ in offsets]
        ys = [y + dy for _, dy in offsets]
        ax.scatter(xs, ys, s=size_hint, c=color, edgecolors="white",
                   linewidths=0.6, zorder=5)
    elif shape_tag == SHAPE_CHARACTER_CIRCLE:
        ax.scatter([x], [y], s=size_hint, c=color, edgecolors="white",
                   linewidths=1.6, zorder=5)
    else:  # SHAPE_SMALL_CIRCLE
        ax.scatter([x], [y], s=size_hint, c=color, edgecolors="white",
                   linewidths=0.9, zorder=5)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def render_frame(
    map_: Map,
    events: List,
    tick: int,
    figsize: tuple = (5.5, 7.0),
) -> Figure:
    """Render the world state at ``events[:tick+1]`` as a top-down map."""
    state = reconstruct_state(events, tick)
    a_name, b_name = _army_names(events)
    current_event: Optional[object] = events[tick] if 0 <= tick < len(events) else None

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(COL_FIG_BG)
    ax.set_facecolor(COL_BOARD_BG)

    pad = 1.0
    ax.set_xlim(-pad, map_.width + pad)
    ax.set_ylim(-pad, map_.height + pad)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#777")
        spine.set_linewidth(1.0)

    # Deployment zone hints
    for y in (map_.deployment_width, map_.height - map_.deployment_width):
        ax.axhline(y, color=COL_GRID, linestyle=":", linewidth=0.6, alpha=0.45, zorder=1)

    # Terrain
    for t in map_.terrain:
        color = TERRAIN_COLORS.get(t.type, "#555555")
        ax.add_patch(Rectangle(
            (t.x, t.y), t.width, t.height,
            facecolor=color, edgecolor="#222", linewidth=0.8, alpha=0.85, zorder=2,
        ))
        ax.text(
            t.x + t.width / 2, t.y + t.height / 2, t.name,
            color="white", fontsize=6, ha="center", va="center", alpha=0.7, zorder=3,
        )

    # Highlight the current event (arrow overlay)
    if isinstance(current_event, UnitMoved):
        fx, fy = current_event.from_pos
        tx, ty = current_event.to_pos
        ax.annotate(
            "", xy=(tx, ty), xytext=(fx, fy),
            arrowprops=dict(arrowstyle="->", color=COL_MOVE_ARROW, lw=1.3, alpha=0.8),
            zorder=4,
        )
    elif isinstance(current_event, UnitShot) and current_event.attacker_uid in state and current_event.target_uid in state:
        ax_pos = state[current_event.attacker_uid]["position"]
        tg_pos = state[current_event.target_uid]["position"]
        ax.annotate(
            "", xy=tg_pos, xytext=ax_pos,
            arrowprops=dict(arrowstyle="->", color=COL_SHOT_ARROW, lw=1.2, alpha=0.85, linestyle="--"),
            zorder=4,
        )
    elif isinstance(current_event, UnitCharged) and current_event.unit_uid in state and current_event.target_uid in state:
        ax_pos = state[current_event.unit_uid]["position"]
        tg_pos = state[current_event.target_uid]["position"]
        ax.annotate(
            "", xy=tg_pos, xytext=ax_pos,
            arrowprops=dict(arrowstyle="-|>", color=COL_CHARGE_ARROW, lw=2.0,
                            alpha=0.9 if current_event.succeeded else 0.4),
            zorder=4,
        )
    elif isinstance(current_event, UnitFought) and current_event.attacker_uid in state and current_event.target_uid in state:
        tg_pos = state[current_event.target_uid]["position"]
        ax.scatter([tg_pos[0]], [tg_pos[1]], s=220, c=COL_MELEE_FLASH,
                   marker="*", alpha=0.9, zorder=7)

    # Objective markers
    for obj in map_.objectives:
        circle = plt.Circle(
            (obj.x, obj.y), obj.control_radius,
            fill=False, edgecolor=COL_OBJECTIVE, linewidth=1.0, alpha=0.55, zorder=2,
        )
        ax.add_patch(circle)
        ax.scatter([obj.x], [obj.y], s=40, c=COL_OBJECTIVE, marker="D",
                   edgecolors="black", linewidths=0.5, alpha=0.75, zorder=3)

    # Units
    for uid, s in state.items():
        color = COL_ARMY_A if s["army"] == a_name else COL_ARMY_B
        x, y = s["position"]
        if s["alive"]:
            shape_tag, size_hint = _shape_for(s.get("unit_keywords", ()))
            _draw_unit_shape(ax, x, y, color, shape_tag, size_hint)
            # HP indicator: if wounded, smaller inner dot. Sized off a baseline
            # 100 marker so it remains a readable overlay across all shape
            # variants (rect/ellipse/circle).
            if s["max_hp"] > 1 and s["current_hp"] < s["max_hp"]:
                hp_frac = max(0.05, s["current_hp"] / s["max_hp"])
                ax.scatter([x], [y], s=100 * hp_frac, c="white", alpha=0.5, zorder=6)
        else:
            ax.scatter([x], [y], s=70, c=COL_DEAD, marker="x",
                       linewidths=1.3, zorder=4, alpha=0.7)

    # Title
    total = max(0, len(events) - 1)
    ax.set_title(
        f"Round {_current_round(events, tick)}   "
        f"|   Tick {tick}/{total}   "
        f"|   {a_name} (blue) vs {b_name} (red)",
        color="white", fontsize=9, pad=8,
    )

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def event_description(event) -> str:
    """One-liner suitable for a scrolling event log."""
    if isinstance(event, BattleStarted):
        return f"Battle started: {event.army_a_name} vs {event.army_b_name} on '{event.map_name}'"
    if isinstance(event, RoundStarted):
        return f"--- Round {event.round_num} ---"
    if isinstance(event, RoundEnded):
        return f"--- End of round {event.round_num} ---"
    if isinstance(event, UnitActivated):
        return f"  Activate  {event.unit_uid} ({event.army_name})"
    if isinstance(event, UnitMoved):
        fx, fy = event.from_pos
        tx, ty = event.to_pos
        return f"  Move      {event.unit_uid}: ({fx:.1f},{fy:.1f}) -> ({tx:.1f},{ty:.1f})"
    if isinstance(event, UnitShot):
        outcome = "killed" if not event.target_alive_after else f"{event.target_hp_after:.1f} hp"
        return f"  Shoot     {event.attacker_uid} -> {event.target_uid}  ({event.damage:.1f} dmg, {outcome})"
    if isinstance(event, UnitAdvanced):
        return f"  Advance!  {event.unit_uid}  rolled {event.advance_roll} (moves {event.total_movement:.1f}\" total — no shoot)"
    if isinstance(event, UnitCharged):
        if event.succeeded:
            return f"  Charge!   {event.unit_uid} -> {event.target_uid}  rolled {event.roll} vs {event.distance:.1f}\" — SUCCESS"
        return f"  Charge X  {event.unit_uid} -> {event.target_uid}  rolled {event.roll} vs {event.distance:.1f}\" — fail"
    if isinstance(event, UnitFought):
        outcome = "killed" if not event.target_alive_after else f"{event.target_hp_after:.1f} hp"
        return f"  Melee     {event.attacker_uid} -> {event.target_uid}  ({event.damage:.1f} dmg, {outcome})"
    if isinstance(event, BattleshockFailed):
        return f"  ! Battleshock failed: {event.unit_uid} rolled {event.roll} vs Ld{event.target}+ — OC 0 this round"
    if isinstance(event, ObjectiveScored):
        if event.army_name is None:
            return f"  Obj {event.objective_name}: contested (OC {event.a_oc}/{event.b_oc}) — no VP"
        return f"  Obj {event.objective_name}: {event.army_name} scores {event.vp_awarded} VP (OC {event.a_oc}/{event.b_oc})"
    if isinstance(event, UnitInfiltrated):
        px, py = event.position
        return f"  Infiltrate {event.unit_uid} -> ({px:.1f},{py:.1f})"
    if isinstance(event, UnitScouted):
        fx, fy = event.from_pos
        tx, ty = event.to_pos
        return f"  Scout     {event.unit_uid}: ({fx:.1f},{fy:.1f}) -> ({tx:.1f},{ty:.1f})"
    if isinstance(event, UnitDeepStrike):
        px, py = event.position
        return f"  Deep Strike {event.unit_uid} arrives at ({px:.1f},{py:.1f})"
    if isinstance(event, UnitKilled):
        return f"  KO        {event.unit_uid}"
    if isinstance(event, BattleEnded):
        winner = event.winner or "Draw"
        return f"Battle ended: {winner} in {event.rounds} rounds"
    return type(event).__name__
