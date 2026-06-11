"""
Pillow top-down renderer for SwegHammer battles.

Given a Map and an event log, ``render_frame(map, events, frame)`` returns a
PIL Image showing the world state at the end of the given replay frame. A
frame is a contiguous slice of events that represents one logical beat of the
battle — typically a full unit activation (move + shoot + charge + fight
collapsed into a single visual). Boundary events (round start/end, objective
scoring, battleshock) each occupy their own frame.

Frames are built by ``aggregate_activations(events)``; this shrinks the
slider from "one tick per event" to "one tick per activation". The renderer
is read-only: it never mutates the simulator state, so the same event log
can be scrubbed forwards and backwards.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

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

COL_FIG_BG    = "#0e1117"
COL_BOARD_BG  = "#3a3530"
COL_GRID      = "#5a5550"

TERRAIN_COLORS = {
    TerrainType.LIGHT_COVER: "#8b6f47",
    TerrainType.HEAVY_COVER: "#6e6e6e",
    TerrainType.RUIN:        "#7a5a3a",
    TerrainType.OBSCURING:   "#3f5c3a",
    TerrainType.IMPASSABLE:  "#1a1a1a",
}

COL_ARMY_A        = "#4e9af1"
COL_ARMY_B        = "#e05c5c"
COL_DEAD          = "#444444"
COL_MOVE_ARROW    = "#cccccc"
COL_SHOT_ARROW    = "#f7d147"
COL_CHARGE_ARROW  = "#ff7f3f"
COL_MELEE_FLASH   = "#e05c5c"
COL_OBJECTIVE     = "#ffd700"
COL_REANIMATE     = "#5cd65c"

# Legacy shape tags — kept for _shape_for backward compatibility.
SHAPE_LARGE_RECT       = "large_rect"
SHAPE_MEDIUM_RECT      = "medium_rect"
SHAPE_LARGE_CIRCLE     = "large_circle"
SHAPE_ELLIPSE          = "ellipse"
SHAPE_SWARM            = "swarm"
SHAPE_CHARACTER_CIRCLE = "character_circle"
SHAPE_SMALL_CIRCLE     = "small_circle"

MM_PER_INCH = 25.4

_RENDER_DPI  = 90
_TITLE_H_PX  = 42   # pixels reserved for the title bar above the board


# ---------------------------------------------------------------------------
# Frame aggregation — collapse one unit's activation into one replay frame
# ---------------------------------------------------------------------------

def _activation_actor(event) -> Optional[str]:
    """The uid of the unit *acting* in this event, if any."""
    if isinstance(event, (UnitActivated, UnitMoved, UnitAdvanced, UnitCharged)):
        return event.unit_uid
    if isinstance(event, (UnitShot, UnitFought)):
        return event.attacker_uid
    return None


def aggregate_activations(events: List) -> List[Tuple[int, int]]:
    """Group consecutive events of the same activating unit into frames.

    A "frame" is a (start_idx, end_idx) inclusive event range that should be
    rendered as a single visual beat in the replay.
    """
    frames: List[Tuple[int, int]] = []
    n = len(events)
    i = 0
    while i < n:
        ev = events[i]
        actor = _activation_actor(ev)
        if actor is None:
            frames.append((i, i))
            i += 1
            continue
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
                break
            if isinstance(nxt, UnitKilled):
                end = j
                j += 1
                continue
            break
        frames.append((start, end))
        i = end + 1
    return frames


# ---------------------------------------------------------------------------
# State reconstruction
# ---------------------------------------------------------------------------

def reconstruct_state(events: List, tick: int) -> Dict[str, dict]:
    """Replay events[:tick+1] and return uid -> state dict."""
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


def reconstruct_score(
    events: List, tick: int,
) -> Tuple[int, int, Dict[str, Optional[str]]]:
    """Replay events[:tick+1] → (a_vp, b_vp, last_scorer_by_objective).

    Victory points accumulate from per-marker ``ObjectiveScored`` events and
    snap to the authoritative ``RoundEnded`` running totals as those pass —
    the round totals fold in secondary-mission VP, which has no per-card
    event in the stream yet. The snap uses ``max()`` rather than assignment
    so legacy event logs (recorded before ``RoundEnded`` carried vp totals,
    deserialising with the default 0/0) keep their accumulated counts: VP
    never decreases, so max() is always the truer of the two.

    ``last_scorer_by_objective`` maps objective name → army name of the most
    recent scoring tick (None = contested at its last tick / never scored).
    """
    a_name, b_name = _army_names(events)
    a_vp = b_vp = 0
    last_scorer: Dict[str, Optional[str]] = {}
    for ev in events[: tick + 1]:
        if isinstance(ev, ObjectiveScored):
            last_scorer[ev.objective_name] = ev.army_name
            if ev.army_name == a_name:
                a_vp += ev.vp_awarded
            elif ev.army_name == b_name:
                b_vp += ev.vp_awarded
        elif isinstance(ev, RoundEnded):
            a_vp = max(a_vp, ev.a_vp_total)
            b_vp = max(b_vp, ev.b_vp_total)
    return a_vp, b_vp, last_scorer


def _army_names(events: List) -> tuple:
    for ev in events:
        if isinstance(ev, BattleStarted):
            return ev.army_a_name, ev.army_b_name
    return "Army A", "Army B"


# ---------------------------------------------------------------------------
# Model base footprint — real-world GW dimensions in world inches
# ---------------------------------------------------------------------------

def _mm_to_inches(mm: float) -> float:
    return float(mm) / MM_PER_INCH


def _shape_for(unit_keywords) -> tuple:
    """Legacy: map a unit's 10e keyword set to a (shape_tag, size_hint) pair.

    Superseded by the data-driven ``base_shape`` path in ``render_frame``.
    Retained for backward compatibility with callers that only have keywords.
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


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgba(h: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    r, g, b = _hex_to_rgb(h)
    return (r, g, b, alpha)


def _blend(col: str, alpha: float, bg: str) -> Tuple[int, int, int, int]:
    """Pre-multiply col over bg at alpha (0–1), returning an opaque RGBA tuple."""
    r1, g1, b1 = _hex_to_rgb(col)
    r2, g2, b2 = _hex_to_rgb(bg)
    return (
        int(r1 * alpha + r2 * (1 - alpha)),
        int(g1 * alpha + g2 * (1 - alpha)),
        int(b1 * alpha + b2 * (1 - alpha)),
        255,
    )


# ---------------------------------------------------------------------------
# Font loader
# ---------------------------------------------------------------------------

def _load_font(size: int) -> ImageFont.ImageFont:
    for path in (
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_text_centered(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int,
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple,
) -> None:
    """Draw text centered at pixel (cx, cy), compatible with both font types."""
    try:
        draw.text((cx, cy), text, fill=fill, font=font, anchor="mm")
        return
    except TypeError:
        pass
    try:
        bbox = font.getbbox(text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = font.getsize(text)  # type: ignore[attr-defined]
    draw.text((cx - tw // 2, cy - th // 2), text, fill=fill, font=font)


# ---------------------------------------------------------------------------
# Pixel-space drawing primitives
# ---------------------------------------------------------------------------

def _dashed_line(
    draw: ImageDraw.ImageDraw,
    x0: float, y0: float, x1: float, y1: float,
    color: tuple, width: int = 1, dash: int = 7, gap: int = 4,
) -> None:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1:
        return
    nx, ny = dx / length, dy / length
    t, drawing = 0.0, True
    while t < length:
        t2 = min(t + (dash if drawing else gap), length)
        if drawing:
            draw.line(
                [(int(x0 + nx * t), int(y0 + ny * t)),
                 (int(x0 + nx * t2), int(y0 + ny * t2))],
                fill=color, width=width,
            )
        t, drawing = t2, not drawing


def _arrow(
    draw: ImageDraw.ImageDraw,
    x0: float, y0: float, x1: float, y1: float,
    color: tuple, width: int = 2, head: int = 9, dashed: bool = False,
) -> None:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 2:
        return
    nx, ny = dx / length, dy / length
    sx, sy = x1 - nx * head, y1 - ny * head
    if dashed:
        _dashed_line(draw, x0, y0, sx, sy, color, width)
    else:
        draw.line([(int(x0), int(y0)), (int(sx), int(sy))], fill=color, width=width)
    px, py = -ny * head * 0.45, nx * head * 0.45
    draw.polygon([
        (int(x1), int(y1)),
        (int(sx + px), int(sy + py)),
        (int(sx - px), int(sy - py)),
    ], fill=color)


def _star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: float, color: tuple) -> None:
    pts = []
    for i in range(10):
        angle = math.pi * i / 5 - math.pi / 2
        radius = r if i % 2 == 0 else r * 0.4
        pts.append((int(cx + radius * math.cos(angle)), int(cy + radius * math.sin(angle))))
    draw.polygon(pts, fill=color)


def _plus(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: tuple, width: int = 3) -> None:
    draw.line([(cx - r, cy), (cx + r, cy)], fill=color, width=width)
    draw.line([(cx, cy - r), (cx, cy + r)], fill=color, width=width)


def _cross(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: tuple, width: int = 2) -> None:
    draw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=color, width=width)
    draw.line([(cx + r, cy - r), (cx - r, cy + r)], fill=color, width=width)


def _draw_unit_base(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int,
    color: tuple,
    base_shape: str,
    w_px: float, h_px: float,
) -> None:
    """Draw a unit base centred at pixel (cx, cy)."""
    white = (255, 255, 255, 255)
    shape = (base_shape or "circle").lower()
    hw, hh = max(4, int(w_px / 2)), max(4, int(h_px / 2))
    if shape == "rect":
        draw.rectangle([cx - hw, cy - hh, cx + hw, cy + hh],
                       fill=color, outline=white, width=1)
    elif shape == "oval":
        draw.ellipse([cx - hw, cy - hh, cx + hw, cy + hh],
                     fill=color, outline=white, width=1)
    else:
        r = max(4, hw)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=color, outline=white, width=1)


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
) -> Image.Image:
    """Render the replay state at the given FRAME index.

    ``frame`` indexes into ``aggregate_activations(events)`` (NOT the raw
    event list). Pass ``frames=`` to skip recomputing the aggregation.

    Returns a PIL RGBA Image. ``figsize`` sets the output size at
    ``_RENDER_DPI`` pixels per inch (e.g. (5.5, 7.0) → 495 × 630 px).
    """
    if frames is None:
        frames = aggregate_activations(events)
    if not frames:
        start_idx = end_idx = 0
    else:
        frame = max(0, min(frame, len(frames) - 1))
        start_idx, end_idx = frames[frame]

    state = reconstruct_state(events, end_idx)
    a_name, b_name = _army_names(events)
    frame_events: List = events[start_idx : end_idx + 1] if events else []
    pre_state = reconstruct_state(events, start_idx - 1) if start_idx > 0 else {}

    # --- Canvas ---
    img_w = int(figsize[0] * _RENDER_DPI)
    img_h = int(figsize[1] * _RENDER_DPI)
    img = Image.new("RGBA", (img_w, img_h), _rgba(COL_FIG_BG))
    draw = ImageDraw.Draw(img, "RGBA")
    font_title = _load_font(13)
    font_name  = _load_font(8)

    # --- Coordinate transform: world inches → pixel (y-flipped) ---
    pad = 1.0
    board_h_px = img_h - _TITLE_H_PX
    world_w = map_.width + 2 * pad
    world_h = map_.height + 2 * pad
    scale = min(img_w / world_w, board_h_px / world_h)
    board_px_w = int(world_w * scale)
    board_px_h = int(world_h * scale)
    x_off = (img_w - board_px_w) // 2
    y_off = _TITLE_H_PX + (board_h_px - board_px_h) // 2

    def to_px(wx: float, wy: float) -> Tuple[int, int]:
        px = x_off + int((wx + pad) * scale)
        py = y_off + board_px_h - int((wy + pad) * scale)
        return px, py

    # --- Board background ---
    draw.rectangle([x_off, y_off, x_off + board_px_w, y_off + board_px_h],
                   fill=_rgba(COL_BOARD_BG))

    # --- Deployment zone hint lines ---
    grid_col = _blend(COL_GRID, 0.45, COL_BOARD_BG)
    for wy in (map_.deployment_width, map_.height - map_.deployment_width):
        lx0, ly = to_px(0.0, wy)
        lx1, _  = to_px(map_.width, wy)
        _dashed_line(draw, lx0, ly, lx1, ly, grid_col, width=1, dash=6, gap=4)

    # --- Terrain ---
    font_terrain = _load_font(7)
    for t in map_.terrain:
        color = TERRAIN_COLORS.get(t.type, "#555555")
        # World rectangle (t.x, t.y)..(t.x+w, t.y+h) → pixel box. to_px flips y,
        # so the top-left pixel corner comes from the world TOP edge (t.y+height).
        tx0, ty0 = to_px(t.x, t.y + t.height)
        tx1, ty1 = to_px(t.x + t.width, t.y)
        draw.rectangle([tx0, ty0, tx1, ty1],
                       fill=_blend(color, 0.85, COL_BOARD_BG),
                       outline=_rgba("#222222", 217), width=1)
        # Terrain names are background context, not foreground — kept small and
        # faded so a unit shape always wins the pixel. (Units are drawn after,
        # so they paint over this.)
        tcx, tcy = to_px(t.x + t.width / 2, t.y + t.height / 2)
        _draw_text_centered(draw, tcx, tcy, t.name, font_terrain,
                            _rgba("#bdb6aa", 97))

    # Draw every visual effect emitted during this frame's activation. Shot
    # arcs are deliberately faded so multiple-target activations stay legible
    # (a Boyz mob shooting into three different Marine squads paints three
    # arrows from the same unit; without alpha the latest would obscure the
    # rest). Charge arrow and melee burst use full opacity since each
    # activation has at most one.
    n_shots = sum(1 for ev in frame_events if isinstance(ev, UnitShot))
    shot_alpha = int(255 * (0.85 if n_shots <= 1 else max(0.35, 0.85 / n_shots ** 0.5)))
    shot_col = _rgba(COL_SHOT_ARROW, shot_alpha)

    for ev in frame_events:
        if isinstance(ev, UnitMoved):
            p0 = to_px(*ev.from_pos)
            p1 = to_px(*ev.to_pos)
            _arrow(draw, p0[0], p0[1], p1[0], p1[1],
                   _rgba(COL_MOVE_ARROW, 204), width=2)

        elif isinstance(ev, UnitShot):
            ap = state.get(ev.attacker_uid, {}).get("position")
            tp = (pre_state.get(ev.target_uid) or state.get(ev.target_uid, {})).get("position")
            if ap and tp:
                p0 = to_px(*ap)
                p1 = to_px(*tp)
                _arrow(draw, p0[0], p0[1], p1[0], p1[1],
                       shot_col, width=1, dashed=True)

        elif isinstance(ev, UnitCharged):
            if ev.unit_uid in state and ev.target_uid in state:
                ap = (pre_state.get(ev.unit_uid) or state[ev.unit_uid])["position"]
                tp = state[ev.target_uid]["position"]
                alpha = 230 if ev.succeeded else 102
                p0 = to_px(*ap)
                p1 = to_px(*tp)
                _arrow(draw, p0[0], p0[1], p1[0], p1[1],
                       _rgba(COL_CHARGE_ARROW, alpha), width=2, head=11)

        elif isinstance(ev, UnitFought):
            if ev.target_uid in state:
                cx, cy = to_px(*state[ev.target_uid]["position"])
                _star(draw, cx, cy, 9.0, _rgba(COL_MELEE_FLASH, 230))

        elif isinstance(ev, UnitReanimated):
            cx, cy = to_px(*ev.position)
            _plus(draw, cx, cy, 8, _rgba(COL_REANIMATE, 242))

    # --- Objective markers ---
    # Marker + control ring tinted by the army that scored it at its LAST
    # scoring tick (gold = never scored / contested at last tick), so "who is
    # holding this marker" reads at a glance between scoring frames. The
    # diamond is drawn at the physical 40mm marker footprint — the old 3.5"
    # diamond out-sized its own 3" control ring and read as a giant unit.
    a_vp, b_vp, last_scorer = reconstruct_score(events, end_idx)
    obj_px: Dict[str, Tuple[int, int, int]] = {}   # name -> (cx, cy, ring_r_px)
    for obj in map_.objectives:
        cx, cy = to_px(obj.x, obj.y)
        r = max(3, int(obj.control_radius * scale))
        obj_px[obj.name] = (cx, cy, r)
        holder = last_scorer.get(obj.name)
        col = (colour_a if holder == a_name
               else colour_b if holder == b_name
               else COL_OBJECTIVE)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=None, outline=_rgba(col, 165),
                     width=2 if holder else 1)
        # Held markers fill solid in the holder's colour (white outline keeps
        # them distinct from unit bases); unheld markers stay gold. At the
        # physical footprint the diamond is small, so a gold outline on a
        # held marker would drown the holder colour.
        dr = max(5, int(_mm_to_inches(40) / 2 * scale))
        draw.polygon(
            [(cx, cy - dr), (cx + dr, cy), (cx, cy + dr), (cx - dr, cy)],
            fill=_rgba(col, 240),
            outline=_rgba("#ffffff" if holder else COL_OBJECTIVE, 220),
        )

    # Units — drawn at their real-world GW base footprint. The state dict
    # carries base_shape + dimensions sourced from UnitProfile via the
    # BattleStarted snapshot; missing fields default to a 32mm round so
    # legacy / synthetic event logs keep rendering.
    legend_armies: Dict[str, str] = {}   # army name -> colour, for the legend
    labelled: List[tuple] = []           # (army, name, x, y) placed tags — de-dup squad clusters
    for uid, s in state.items():
        color = colour_a if s["army"] == a_name else colour_b
        legend_armies.setdefault(s["army"], color)
        x, y = s["position"]
        cx, cy = to_px(x, y)
        if s["alive"]:
            bs = s.get("base_shape", "circle")
            if bs in ("rect", "oval"):
                w_px = _mm_to_inches(s.get("base_width_mm", 32)) * scale
                h_px = _mm_to_inches(s.get("base_length_mm", 32)) * scale
            else:
                diam = _mm_to_inches(s.get("base_diameter_mm", 32)) * scale
                w_px = h_px = diam

            _draw_unit_base(draw, cx, cy, color, bs, w_px, h_px)

            # HP bar: small white inner circle when wounded; radius scales with
            # the remaining health fraction so a near-dead unit shows a tiny pip.
            if s["max_hp"] > 1 and s["current_hp"] < s["max_hp"]:
                hp_frac = max(0.05, s["current_hp"] / s["max_hp"])
                r_hp = max(2, int(2 + 5 * hp_frac))
                draw.ellipse([cx - r_hp, cy - r_hp, cx + r_hp, cy + r_hp],
                             fill=_rgba("#ffffff", 128))
            # Name-tag the LARGE / distinct units (vehicles, monsters, titanic,
            # big-base characters). Small infantry are left untagged so hordes
            # stay legible — colour + size + the legend identify those. De-dup
            # so a clustered multi-model squad gets ONE tag, not one per model.
            shape = (s.get("base_shape") or "circle").lower()
            is_big = shape in ("rect", "oval") or int(s.get("base_diameter_mm", 32)) >= 50
            if is_big:
                name = s.get("name") or ""
                near = any(
                    la == s["army"] and ln == name
                    and (lx - x) ** 2 + (ly - y) ** 2 < 49.0
                    for la, ln, lx, ly in labelled
                )
                if name and not near:
                    tag = (name[:15] + "…") if len(name) > 16 else name
                    tb = font_name.getbbox(tag)
                    tw, th = tb[2] - tb[0], tb[3] - tb[1]
                    draw.rectangle(
                        [cx - tw // 2 - 3, cy - th // 2 - 2,
                         cx + tw // 2 + 3, cy + th // 2 + 2],
                        fill=_rgba("#0e1117", 158), outline=_rgba(color, 200),
                        width=1,
                    )
                    _draw_text_centered(draw, cx, cy, tag, font_name,
                                        _rgba("#ffffff", 235))
                    labelled.append((s["army"], name, x, y))
        else:
            r = max(4, int(_mm_to_inches(32) / 2 * scale))
            _cross(draw, cx, cy, r, _rgba(COL_DEAD, 178))

    # --- Scoring flash: this frame IS a scoring tick ---
    # ObjectiveScored events are boundary frames (one per marker), so when the
    # scrubber lands on one we pulse the scored marker's control ring and tag
    # it "+N VP" in the scoring army's colour ("contested" in grey when no one
    # scores). This is the explicit when-and-how of every primary VP award.
    font_flash = _load_font(10)
    for ev in frame_events:
        if not isinstance(ev, ObjectiveScored):
            continue
        hit = obj_px.get(ev.objective_name)
        if hit is None:
            # Synthetic/legacy log naming a marker not on this map — the
            # renderer is display-only and must keep scrubbing old replays,
            # so skip the highlight (the legend VP totals still update).
            continue
        fx, fy, fr = hit
        if ev.army_name is None:
            fcol = "#b0b0b0"
            txt = f"contested  OC {ev.a_oc}–{ev.b_oc}"
        else:
            fcol = colour_a if ev.army_name == a_name else colour_b
            txt = f"+{ev.vp_awarded} VP  (OC {ev.a_oc}–{ev.b_oc})"
        draw.ellipse([fx - fr - 2, fy - fr - 2, fx + fr + 2, fy + fr + 2],
                     fill=None, outline=_rgba(fcol, 255), width=3)
        tb = font_flash.getbbox(txt)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        ty = fy - fr - th - 8
        draw.rectangle(
            [fx - tw // 2 - 4, ty - 3, fx + tw // 2 + 4, ty + th + 3],
            fill=_rgba("#0e1117", 200), outline=_rgba(fcol, 230), width=1,
        )
        _draw_text_centered(draw, fx, ty + th // 2, txt, font_flash,
                            _rgba("#ffffff", 245))

    # Army colour legend + running VP — reinforces which colour is which army
    # and shows the live score (primary + secondary, reconstructed up to this
    # frame). The name tags above identify the individual big units. Drawn as
    # a small panel in the board's upper-left corner.
    if legend_armies:
        font_legend = _load_font(11)
        vp_by_army = {a_name: a_vp, b_name: b_vp}
        rows = [
            (f"{nm} · {vp_by_army[nm]} VP" if nm in vp_by_army else nm, c)
            for nm, c in legend_armies.items()
        ]
        sw = 11          # colour-swatch size
        row_h = sw + 5
        label_w = 0
        for nm, _c in rows:
            lb = font_legend.getbbox(nm)
            label_w = max(label_w, lb[2] - lb[0])
        panel_w = sw + 6 + label_w + 12
        panel_h = len(rows) * row_h + 6
        lx0 = x_off + 8
        ly0 = y_off + 8
        draw.rectangle([lx0 - 5, ly0 - 5, lx0 - 5 + panel_w, ly0 - 5 + panel_h],
                       fill=_rgba("#0e1117", 184), outline=_rgba("#555555", 200),
                       width=1)
        ly = ly0
        for nm, c in rows:
            draw.rectangle([lx0, ly, lx0 + sw, ly + sw],
                           fill=_rgba(c), outline=_rgba("#ffffff", 200), width=1)
            _draw_text_centered(draw, lx0 + sw + 6 + (label_w // 2), ly + sw // 2,
                                nm, font_legend, _rgba("#ffffff", 235))
            ly += row_h

    # Scale bar — a 6" reference so the true-base-size shapes read at a known
    # scale (a Knight base really is ~3x a Marine's).
    bar_len = 6.0
    bx0 = map_.width - bar_len - 1.0
    bary = 0.6
    sx0, sy0 = to_px(bx0, bary)
    sx1, _sy1 = to_px(bx0 + bar_len, bary)
    draw.line([sx0, sy0, sx1, sy0], fill=_rgba("#ffffff", 235), width=2)
    scx, _scy = to_px(bx0 + bar_len / 2.0, bary)
    _draw_text_centered(draw, scx, sy0 - 8, '6"', _load_font(9),
                        _rgba("#ffffff", 235))

    # Round-end banner — secondary-mission VP has no per-card event in the
    # stream, so the award only becomes visible as the delta between the
    # accumulated primary count and the authoritative RoundEnded totals.
    # Surface that delta on the RoundEnded frame itself.
    for ev in frame_events:
        if isinstance(ev, RoundEnded):
            pre_a, pre_b, _ls = (
                reconstruct_score(events, start_idx - 1) if start_idx > 0
                else (0, 0, {})
            )
            sec_a = max(0, ev.a_vp_total - pre_a)
            sec_b = max(0, ev.b_vp_total - pre_b)
            banner = (
                f"End of round {ev.round_num} — secondary VP:  "
                f"{a_name} +{sec_a}   {b_name} +{sec_b}"
            )
            font_banner = _load_font(10)
            bb = font_banner.getbbox(banner)
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            # Below the legend panel's vertical extent so the two never collide.
            bcx, bcy = img_w // 2, y_off + 56
            draw.rectangle(
                [bcx - bw // 2 - 6, bcy - bh // 2 - 4,
                 bcx + bw // 2 + 6, bcy + bh // 2 + 4],
                fill=_rgba("#0e1117", 210), outline=_rgba(COL_OBJECTIVE, 220),
                width=1,
            )
            _draw_text_centered(draw, bcx, bcy, banner, font_banner,
                                _rgba("#ffffff", 245))
            break

    # Title — show frame index (one per activation / boundary), not raw
    # event index, so the slider value matches what the viewer sees. The
    # running score rides in the title so it is visible on every frame.
    total_frames = max(0, len(frames) - 1)
    title = (
        f"Round {_current_round(events, end_idx)}  │  "
        f"Frame {frame if frames else 0}/{total_frames}  │  "
        f"{a_name} {a_vp} – {b_vp} {b_name}"
    )
    _draw_text_centered(draw, img_w // 2, _TITLE_H_PX // 2, title,
                        font_title, (255, 255, 255, 255))

    return img


# ---------------------------------------------------------------------------
# Text helpers (unchanged)
# ---------------------------------------------------------------------------

def event_description(event) -> str:
    """One-liner suitable for a scrolling event log."""
    if isinstance(event, BattleStarted):
        return f"Battle started: {event.army_a_name} vs {event.army_b_name} on '{event.map_name}'"
    if isinstance(event, RoundStarted):
        return f"--- Round {event.round_num} ---"
    if isinstance(event, RoundEnded):
        return (f"--- End of round {event.round_num} "
                f"(VP {event.a_vp_total}–{event.b_vp_total}) ---")
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
    """Multi-line summary of a replay frame."""
    start, end = frame_range
    if start == end:
        return event_description(events[start])
    return "\n".join(event_description(events[i]) for i in range(start, end + 1))
