"""
Matplotlib top-down renderer for SwegHammer battles.

Given a Map and an event log, ``render_frame(map, events, frame)`` returns a
matplotlib Figure showing the world state at the end of the given replay
frame. A frame is a contiguous slice of events that represents one logical
beat of the battle — typically a full unit activation (move + shoot + charge
+ fight collapsed into a single visual). Boundary events (round start/end,
objective scoring, battleshock) each occupy their own frame.

Frames are built by ``aggregate_activations(events)``; this is what shrinks
the slider in the Replay tab from "one tick per event" (painful) to "one tick
per activation" (watchable). The renderer is read-only: it never mutates the
simulator state, so the same event log can be scrubbed forwards and backwards.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse, Rectangle

from .events import (
    BattleEnded, BattleStarted, BattleshockFailed, ObjectiveScored,
    RoundEnded, RoundStarted, UnitActivated, UnitAdvanced, UnitCharged,
    UnitDeepStrike, UnitFought, UnitInfiltrated, UnitKilled, UnitMoved,
    UnitReanimated, UnitScouted, UnitShot,
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
COL_REANIMATE = "#5cd65c"      # green — Necron Reanimation Protocols revival


# ---------------------------------------------------------------------------
# Frame aggregation — collapse one unit's activation into one replay frame
# ---------------------------------------------------------------------------

def _activation_actor(event) -> Optional[str]:
    """The uid of the unit *acting* in this event, if any.

    Only events that are part of a unit's normal-turn activation
    (UnitActivated / UnitMoved / UnitAdvanced / UnitShot / UnitCharged /
    UnitFought) return a uid. Everything else — round boundaries, scoring,
    battleshock, deployment abilities — returns None and breaks the
    aggregation chain, so those events each get their own frame.
    """
    if isinstance(event, (UnitActivated, UnitMoved, UnitAdvanced, UnitCharged)):
        return event.unit_uid
    if isinstance(event, (UnitShot, UnitFought)):
        return event.attacker_uid
    return None


def aggregate_activations(events: List) -> List[Tuple[int, int]]:
    """Group consecutive events of the same activating unit into frames.

    A "frame" is a (start_idx, end_idx) inclusive event range that should be
    rendered as a single visual beat in the replay. Within one activation a
    unit may move, shoot multiple targets, charge and fight — without this
    aggregation each of those is its own slider tick, which makes any
    non-trivial battle painful to watch. With it, the move/shoots/charge/
    fight collapse into ONE tick that draws the final position plus every
    arc/arrow/burst emitted along the way.

    Aggregation rules:
      - Consecutive events sharing the same actor uid (the active unit)
        merge into one frame.
      - A UnitKilled that immediately follows an event of the current frame
        (its target died) is pulled into that frame.
      - A different actor's event ends the current frame.
      - Any non-activation event (round boundary, objective scoring,
        battleshock, deployment ability, BattleStarted, BattleEnded) gets
        its own frame and never absorbs neighbours.
    """
    frames: List[Tuple[int, int]] = []
    n = len(events)
    i = 0
    while i < n:
        ev = events[i]
        actor = _activation_actor(ev)
        if actor is None:
            # Boundary / standalone event — own frame, no merging.
            frames.append((i, i))
            i += 1
            continue

        # Open a new activation frame and pull in subsequent same-actor
        # events plus their UnitKilled tails.
        start = i
        end = i
        j = i + 1
        while j < n:
            nxt = events[j]
            nxt_actor = _activation_actor(nxt)
            if nxt_actor == actor:
                end = j
                j += 1
                continue
            if nxt_actor is not None:
                break  # different unit's activation — close ours
            if isinstance(nxt, UnitKilled):
                end = j
                j += 1
                continue
            break  # round boundary / objective / battleshock / deployment
        frames.append((start, end))
        i = end + 1
    return frames


# ---------------------------------------------------------------------------
# State reconstruction
# ---------------------------------------------------------------------------

def reconstruct_state(events: List, tick: int) -> Dict[str, dict]:
    """Replay events[:tick+1] and return uid -> state dict.

    Note: ``tick`` here is an EVENT index, not a frame index. ``render_frame``
    translates a frame index into the event index of the frame's last event
    before calling this, so the function still operates on a raw event prefix
    (which makes it composable for callers that want intermediate snapshots).

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
                    # Renderer-only base footprint snapshot — see UnitProfile.
                    "base_shape": getattr(u, "base_shape", "circle"),
                    "base_diameter_mm": int(getattr(u, "base_diameter_mm", 32)),
                    "base_width_mm": int(getattr(u, "base_width_mm", 32)),
                    "base_length_mm": int(getattr(u, "base_length_mm", 32)),
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
        elif isinstance(ev, UnitReanimated):
            # A previously-destroyed model is back on the board — flip it
            # back to alive at full HP and update its position to wherever
            # the simulator placed it.
            if ev.unit_uid in state:
                state[ev.unit_uid]["position"] = ev.position
                state[ev.unit_uid]["alive"] = True
                state[ev.unit_uid]["current_hp"] = state[ev.unit_uid]["max_hp"]
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
# Model base footprint — real-world GW dimensions in world inches
# ---------------------------------------------------------------------------
#
# Each `UnitProfile` carries a `base_shape` ("circle" / "rect" / "oval") plus
# the relevant millimetre dimensions (diameter for circles, width+length for
# rect/oval). The renderer converts those to world inches at the 25.4 mm/inch
# scale and draws a matching matplotlib patch. This replaces the previous
# keyword-driven "TITANIC = big rectangle, MONSTER = big circle" dispatcher
# with a data-driven path that respects each unit's actual model footprint
# (e.g. Repulsor 102x178mm rect, Riptide 80mm circle, Hive Tyrant 80mm).
#
# The keyword dispatcher below (``_shape_for``) is retained as a legacy
# fallback for callers that only have keyword data — primarily the existing
# tests, and any consumer that hasn't been ported to ``base_shape`` yet.

MM_PER_INCH = 25.4


def _mm_to_inches(mm: float) -> float:
    """Convert millimetres to world inches at the GW scale (25.4 mm/inch)."""
    return float(mm) / MM_PER_INCH


# Shape hint tags. Legacy dispatcher output — kept for backward compatibility
# with `_shape_for`. The new draw path uses `base_shape` directly off the
# unit's state dict and ignores these tags.
SHAPE_LARGE_RECT = "large_rect"        # TITANIC / TOWERING
SHAPE_MEDIUM_RECT = "medium_rect"      # VEHICLE / WALKER (non-Titanic)
SHAPE_LARGE_CIRCLE = "large_circle"    # MONSTER
SHAPE_ELLIPSE = "ellipse"              # BIKE / MOUNTED
SHAPE_SWARM = "swarm"                  # SWARM — cluster of jittered dots
SHAPE_CHARACTER_CIRCLE = "character_circle"  # CHARACTER — small circle, thick outline
SHAPE_SMALL_CIRCLE = "small_circle"    # default INFANTRY


def _shape_for(unit_keywords) -> tuple:
    """Legacy: map a unit's 10e keyword set to a (shape_tag, size_hint) pair.

    Superseded by the data-driven ``base_shape`` path in ``render_frame``.
    Retained because the existing renderer tests assert on its dispatch
    behaviour and because callers that only have a keyword tuple (no real
    base size) still need a sensible fallback silhouette.

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


def _draw_unit_base(
    ax, x: float, y: float, color: str,
    base_shape: str,
    base_diameter_mm: int,
    base_width_mm: int,
    base_length_mm: int,
) -> None:
    """Draw a single alive unit using its real-world GW base footprint.

    All millimetre dimensions are converted to world inches at the
    ``MM_PER_INCH`` scale. The ``base_shape`` selects the matplotlib patch:

      - ``"circle"`` -> matplotlib ``Circle`` of diameter ``base_diameter_mm``
      - ``"rect"``   -> ``Rectangle`` sized ``base_width_mm`` x ``base_length_mm``
      - ``"oval"``   -> ``Ellipse`` sized ``base_width_mm`` x ``base_length_mm``

    Any unrecognised shape value silently falls back to a 32mm round so a
    bad override doesn't take the renderer down.
    """
    shape = (base_shape or "circle").lower()
    if shape == "rect":
        w = _mm_to_inches(base_width_mm)
        h = _mm_to_inches(base_length_mm)
        ax.add_patch(Rectangle(
            (x - w / 2, y - h / 2), w, h,
            facecolor=color, edgecolor="white", linewidth=0.9, zorder=5,
        ))
    elif shape == "oval":
        w = _mm_to_inches(base_width_mm)
        h = _mm_to_inches(base_length_mm)
        ax.add_patch(Ellipse(
            (x, y), w, h,
            facecolor=color, edgecolor="white", linewidth=0.9, zorder=5,
        ))
    else:  # "circle" or fallback
        r = _mm_to_inches(base_diameter_mm) / 2.0
        ax.add_patch(plt.Circle(
            (x, y), r,
            facecolor=color, edgecolor="white", linewidth=0.9, zorder=5,
        ))


def _draw_unit_shape(ax, x: float, y: float, color: str,
                     shape_tag: str, size_hint) -> None:
    """Legacy: draw a single alive unit using the shape dispatcher's output.

    Retained for backward compatibility; the new draw path is
    ``_draw_unit_base``. Both are kept in the public surface so external
    consumers (older notebooks, regression scripts) keep working.
    """
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
    frame: int,
    figsize: tuple = (5.5, 7.0),
    frames: Optional[List[Tuple[int, int]]] = None,
    colour_a: str = COL_ARMY_A,
    colour_b: str = COL_ARMY_B,
) -> Figure:
    """Render the replay state at the given FRAME index.

    ``frame`` indexes into ``aggregate_activations(events)`` (NOT the raw
    event list). A frame may span an entire activation — move + several
    shots + charge + fight — so the figure shows the unit at its final
    post-activation position plus every arc/arrow/burst emitted during the
    activation, all overlaid in one image.

    Pass ``frames=`` to skip the internal ``aggregate_activations`` call when
    you've already computed and cached it — meaningful speedup when the
    Streamlit slider re-invokes this on every tick.
    """
    if frames is None:
        frames = aggregate_activations(events)
    if not frames:
        # Empty event log — return a blank board so callers don't crash.
        start_idx = end_idx = 0
    else:
        # Clamp to valid range so a stale slider value doesn't blow up.
        frame = max(0, min(frame, len(frames) - 1))
        start_idx, end_idx = frames[frame]

    state = reconstruct_state(events, end_idx)
    a_name, b_name = _army_names(events)
    frame_events: List = events[start_idx:end_idx + 1] if events else []

    # Pre-compute pre-activation positions so we can draw the move arrow
    # from where the unit STARTED the activation to where it finished.
    pre_state = (
        reconstruct_state(events, start_idx - 1) if start_idx > 0 else {}
    )

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

    # Draw every visual effect emitted during this frame's activation. Shot
    # arcs are deliberately faded so multiple-target activations stay legible
    # (a Boyz mob shooting into three different Marine squads paints three
    # arrows from the same unit; without alpha the latest would obscure the
    # rest). Charge arrow and melee burst use full opacity since each
    # activation has at most one.
    n_shots = sum(1 for ev in frame_events if isinstance(ev, UnitShot))
    shot_alpha = 0.85 if n_shots <= 1 else max(0.35, 0.85 / n_shots ** 0.5)

    for ev in frame_events:
        if isinstance(ev, UnitMoved):
            fx, fy = ev.from_pos
            tx, ty = ev.to_pos
            ax.annotate(
                "", xy=(tx, ty), xytext=(fx, fy),
                arrowprops=dict(arrowstyle="->", color=COL_MOVE_ARROW,
                                lw=1.3, alpha=0.8),
                zorder=4,
            )
        elif isinstance(ev, UnitShot):
            attacker_pos = None
            if ev.attacker_uid in state:
                attacker_pos = state[ev.attacker_uid]["position"]
            target_pos = None
            if ev.target_uid in pre_state:
                target_pos = pre_state[ev.target_uid]["position"]
            elif ev.target_uid in state:
                target_pos = state[ev.target_uid]["position"]
            if attacker_pos and target_pos:
                ax.annotate(
                    "", xy=target_pos, xytext=attacker_pos,
                    arrowprops=dict(arrowstyle="->", color=COL_SHOT_ARROW,
                                    lw=1.2, alpha=shot_alpha, linestyle="--"),
                    zorder=4,
                )
        elif isinstance(ev, UnitCharged):
            if ev.unit_uid in state and ev.target_uid in state:
                attacker_pos = (
                    pre_state[ev.unit_uid]["position"]
                    if ev.unit_uid in pre_state
                    else state[ev.unit_uid]["position"]
                )
                target_pos = state[ev.target_uid]["position"]
                ax.annotate(
                    "", xy=target_pos, xytext=attacker_pos,
                    arrowprops=dict(arrowstyle="-|>", color=COL_CHARGE_ARROW,
                                    lw=2.0, alpha=0.9 if ev.succeeded else 0.4),
                    zorder=4,
                )
        elif isinstance(ev, UnitFought):
            if ev.attacker_uid in state and ev.target_uid in state:
                tg_pos = state[ev.target_uid]["position"]
                ax.scatter([tg_pos[0]], [tg_pos[1]], s=220, c=COL_MELEE_FLASH,
                           marker="*", alpha=0.9, zorder=7)
        elif isinstance(ev, UnitReanimated):
            # Green "+" where a destroyed model just got back up.
            px, py = ev.position
            ax.scatter([px], [py], s=260, c=COL_REANIMATE, marker="+",
                       linewidths=2.5, alpha=0.95, zorder=7)

    # Objective markers
    for obj in map_.objectives:
        circle = plt.Circle(
            (obj.x, obj.y), obj.control_radius,
            fill=False, edgecolor=COL_OBJECTIVE, linewidth=1.0, alpha=0.55, zorder=2,
        )
        ax.add_patch(circle)
        ax.scatter([obj.x], [obj.y], s=40, c=COL_OBJECTIVE, marker="D",
                   edgecolors="black", linewidths=0.5, alpha=0.75, zorder=3)

    # Units — drawn at their real-world GW base footprint. The state dict
    # carries base_shape + dimensions sourced from UnitProfile via the
    # BattleStarted snapshot; missing fields default to a 32mm round so
    # legacy / synthetic event logs keep rendering.
    for uid, s in state.items():
        color = colour_a if s["army"] == a_name else colour_b
        x, y = s["position"]
        if s["alive"]:
            _draw_unit_base(
                ax, x, y, color,
                base_shape=s.get("base_shape", "circle"),
                base_diameter_mm=int(s.get("base_diameter_mm", 32)),
                base_width_mm=int(s.get("base_width_mm", 32)),
                base_length_mm=int(s.get("base_length_mm", 32)),
            )
            # HP indicator: if wounded, smaller inner dot. Sized off a baseline
            # 100 marker so it remains a readable overlay across all shape
            # variants (rect/ellipse/circle).
            if s["max_hp"] > 1 and s["current_hp"] < s["max_hp"]:
                hp_frac = max(0.05, s["current_hp"] / s["max_hp"])
                ax.scatter([x], [y], s=100 * hp_frac, c="white", alpha=0.5, zorder=6)
        else:
            ax.scatter([x], [y], s=70, c=COL_DEAD, marker="x",
                       linewidths=1.3, zorder=4, alpha=0.7)

    # Title — show frame index (one per activation / boundary), not raw
    # event index, so the slider value matches what the viewer sees.
    total_frames = max(0, len(frames) - 1)
    ax.set_title(
        f"Round {_current_round(events, end_idx)}   "
        f"|   Frame {frame if frames else 0}/{total_frames}   "
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
    if isinstance(event, UnitReanimated):
        px, py = event.position
        return f"  Reanimate {event.unit_uid} rises again at ({px:.1f},{py:.1f})"
    if isinstance(event, UnitKilled):
        return f"  KO        {event.unit_uid}"
    if isinstance(event, BattleEnded):
        winner = event.winner or "Draw"
        return f"Battle ended: {winner} in {event.rounds} rounds"
    return type(event).__name__


def frame_description(events: List, frame_range: Tuple[int, int]) -> str:
    """Multi-line summary of a replay frame.

    Single-event frames render exactly like ``event_description``; multi-event
    activation frames list every event in the activation on its own line, so
    the log panel mirrors what the figure shows.
    """
    start, end = frame_range
    if start == end:
        return event_description(events[start])
    return "\n".join(event_description(events[i]) for i in range(start, end + 1))
