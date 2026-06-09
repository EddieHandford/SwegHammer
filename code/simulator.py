"""Battle simulator: unit-by-unit activation with movement and event emission."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .army import Army
from .detachments import effective_move
from .pathfind import find_path
from .events import (
    BattleEnded, BattleStarted, BattleshockFailed, DeadlyDemiseExploded,
    InitialUnit, JudgementTokenAwarded, OathTargetChosen, ObjectiveScored,
    RoundEnded, RoundStarted, StratagemFired, Subscriber, TransportDisembarked,
    TransportEmbarked, UnitActivated, UnitAdvanced, UnitCharged,
    UnitDeepStrike, UnitFought, UnitInfiltrated, UnitKilled, UnitMoved,
    UnitReanimated, UnitScouted, UnitShot, WaaaghDeclared,
)
from .factions import is_marine_faction
from .map import Map, TerrainType
from .maps import DEFAULT_MAP
from .strategy import (
    _is_melee_class, _melee_target_score, _oc_on_objective,
    decide_deepstrike_drops, pick_army_plan, pick_doctrina_imperative,
    pick_mass_arrival_anchor, pick_move_intent, should_declare_waaagh,
    should_fire_stratagem,
)
from .stratagems import (
    COMMAND_RE_ROLL, COUNTER_OFFENSIVE, TANK_SHOCK,
    # Virulent Vectorium (Death Guard) — full 6-stratagem set, per #195.
    # Disgustingly Resilient was re-anchored to the real detachment at 2 CP
    # per the 2026-05-15 fabrication audit.
    DISGUSTINGLY_RESILIENT, PUTRID_DETONATION, PLAGUESURGE,
    LEECHSPORE_ERUPTION, OVERWHELMING_GENEROSITY, CREEPING_BLIGHT,
    # Warhost (Aeldari) — six real detachment stratagems
    LIGHTNING_FAST_REACTIONS, FIRE_AND_FADE,
    SKYBORNE_SANCTUARY, FEIGNED_RETREAT, BLITZING_FIREPOWER, WEBWAY_TUNNEL,
    # Mont'ka (T'au Empire) — six real detachment stratagems (#196)
    PINPOINT_COUNTER_OFFENSIVE, AGGRESSIVE_MOBILITY, FOCUSED_FIRE,
    COMBAT_DEBARKATION, PULSE_ONSLAUGHT, COUNTERFIRE_DEFENCE_SYSTEMS,
    # Awakened Dynasty (Necrons) — six real Protocol stratagems (#194)
    PROTOCOL_OF_THE_ETERNAL_REVENANT,
    PROTOCOL_OF_THE_UNDYING_LEGIONS,
    PROTOCOL_OF_THE_HUNGRY_VOID,
    PROTOCOL_OF_THE_SUDDEN_STORM,
    PROTOCOL_OF_THE_CONQUERING_TYRANT,
    PROTOCOL_OF_THE_VENGEFUL_STARS,
    # Grand Coven (Thousand Sons) — six real detachment stratagems (#193)
    PSYCHIC_DOMINION, DESTINED_BY_FATE, EGOTISTICAL_POWER,
    DESECRATION_OF_WORLDS, ARCANE_FOCUS, DEVASTATING_SORCERY,
    # Rubricae Phalanx (Thousand Sons) — six detachment stratagems (iter15)
    ARDENT_AUTOMATA, INEXORABLE_ADVANCE, INFERNAL_FUSILLADE,
    REVENGE_OF_THE_RUBRICAE, IMPLACABLE_GUARDIANS, UNWAVERING_PHALANX,
    # War Horde (Orks) — six real detachment stratagems (iter-1 B1)
    INSANE_BRAVERY, POWER_OF_THE_WAAAGH, MOB_UP, BIG_KRUMPIN,
    TELLYPORTA, DA_BIGGEST_BOSS,
    # Shield Host (Adeptus Custodes) — six real detachment stratagems (iter-8)
    ARCANE_GENETIC_ALCHEMY, UNWAVERING_SENTINELS, MULTIPOTENTIALITY,
    VIGILANCE_ETERNAL, ARCHAEOTECH_MUNITIONS, AVENGE_THE_FALLEN,
    # Needgaard Oathband (Leagues of Votann) — two verified stratagems (VOTANN-AUDIT-V1)
    ANCESTRAL_SENTENCE, VOID_HARDENED,
    # Gladius Task Force (Adeptus Astartes) — six real detachment stratagems (iter-12)
    STORM_OF_FIRE, ARMOUR_OF_CONTEMPT, SQUAD_TACTICS,
    ONLY_IN_DEATH_DOES_DUTY_END, HONOUR_THE_CHAPTER, ADAPTIVE_STRATEGY,
    # Combined Arms (Astra Militarum) — six real detachment stratagems (iter-14)
    COORDINATED_ACTION, REINFORCEMENTS, FLEXIBLE_COMMAND,
    FIELDS_OF_FIRE, INSPIRED_COMMAND, STALWART_PROTECTOR,
    # ST-2 wave 3 — one stratagem per under-performing faction
    APOPLECTIC_FRENZY, EMPYRIC_CHANNELLING,
    CULT_AMBUSH, PROFANE_ZEAL,
    # DAEMONS-STRATAGEMS-V1 (wave 53) — Daemonic Incursion + per-god sets
    DENIZENS_OF_THE_WARP, DRAUGHT_OF_TERROR, WARP_SURGE,
    DAEMONIC_INVULNERABILITY,
    BLOOD_BEGETS_SKULLS, WRATH_UNDENIABLE,
    SEEPING_VIRULENCE, FOETID_RESURGENCE,
    ARCHAGONISTS,
    FLICKERING_REALITY,
    # CSM-EYE-OF-GODS — Pactbound Zealots snowball stratagem (1 CP)
    EYE_OF_THE_GODS,
    CP_CAP, award_command_phase_cp,
)


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class BattleResult:
    winner: Optional[str]   # army name, or None for draw
    rounds: int
    a_name: str
    b_name: str
    a_start: int            # initial unit count
    b_start: int
    a_survivors: int        # surviving unit count
    b_survivors: int
    a_vp: int = 0           # Primary VP scored across the battle
    b_vp: int = 0
    a_points_remaining: float = 0.0   # sum of points_cost over alive units at end
    b_points_remaining: float = 0.0
    round_history: list = None  # list of (a_alive, b_alive) per round

    def __post_init__(self):
        if self.round_history is None:
            self.round_history = []

    @property
    def is_draw(self) -> bool:
        return self.winner is None

    def winner_label(self) -> str:
        return self.winner if self.winner is not None else "Draw"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class _OccupantGrid:
    """Per-mover spatial hash over the collision occupant list (avenue-2 Stage 2,
    docs/PATHFINDING_PLAN.md). Buckets `(x, y, radius, is_enemy)` occupants by a coarse
    cell so a legality query touches only the handful of occupants NEAR the test point
    instead of the whole list — turning the O(models) `_collision_pos_legal` inner loop
    (run ~18x per blocked move by the sidestep, the O(models^2) dense-horde cost) into
    O(local).

    The legality result is BYTE-IDENTICAL to iterating the full list: a model further
    than `mover_radius + max_orad + 1"` in centre-distance can never overlap or be within
    Engagement Range, and `near()` is built to include every occupant within that reach.
    So the grid is a pure speedup — no behaviour change, gated for measurement only.

    DETERMINISM: `near()` walks buckets in fixed (cx, cy) order and within a bucket in
    INSERTION order (the original occupant order, which the caller builds in a fixed
    (friendly-then-enemy, alive_units) order). The grid is also fully list-compatible
    (`__iter__`/`__len__`/`__bool__`/`__getitem__` over the original ordered list) so any
    order-dependent consumer (make-way / clear-lane) that iterates it sees the unchanged
    order."""

    __slots__ = ("cell", "buckets", "max_orad", "_list")

    def __init__(self, occupants, cell: float = 8.0):
        self.cell = cell
        self.buckets: dict = {}
        self.max_orad = 0.0
        self._list = occupants
        for occ in occupants:
            ox, oy, orad = occ[0], occ[1], occ[2]
            if orad > self.max_orad:
                self.max_orad = orad
            key = (int(ox // cell), int(oy // cell))
            b = self.buckets.get(key)
            if b is None:
                self.buckets[key] = [occ]
            else:
                b.append(occ)

    def near(self, pos, mover_radius: float):
        """Occupants whose bucket lies within the max interaction reach of `pos`."""
        reach = mover_radius + self.max_orad + 1.0
        c = self.cell
        cx0 = int((pos[0] - reach) // c)
        cx1 = int((pos[0] + reach) // c)
        cy0 = int((pos[1] - reach) // c)
        cy1 = int((pos[1] + reach) // c)
        out = []
        buckets = self.buckets
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                b = buckets.get((cx, cy))
                if b:
                    out.extend(b)
        return out

    def __iter__(self):
        return iter(self._list)

    def __len__(self):
        return len(self._list)

    def __bool__(self):
        return bool(self._list)

    def __getitem__(self, i):
        return self._list[i]


def _collision_pos_legal(pos, mover_radius, occupants, mover_fly) -> bool:
    """Avenue-2 Stage 1 (no-overlap collision): is `pos` a legal END position for a
    mover of footprint `mover_radius` (inches), given `occupants` — a list (or
    `_OccupantGrid`) of (x, y, radius, is_enemy) for every OTHER alive model? Real 10e:
    a model cannot END a move overlapping another model, nor (for non-FLY) within
    Engagement Range (1") of an enemy. FLY ends are exempt from the enemy/ER test (it
    flew over). Pure + deterministic. Only consulted when collision is wired ON by a
    caller. When `occupants` is an `_OccupantGrid`, only the occupants NEAR `pos` are
    tested (identical result, O(local) instead of O(models))."""
    if type(occupants) is _OccupantGrid:
        occupants = occupants.near(pos, mover_radius)
    for ox, oy, orad, is_enemy in occupants:
        d2 = (pos[0] - ox) ** 2 + (pos[1] - oy) ** 2
        # No model may END overlapping another model's base (applies to FLY too).
        if d2 < (mover_radius + orad) ** 2:
            return False
        # Non-FLY may not end within Engagement Range (1") of an enemy base.
        if is_enemy and not mover_fly and d2 < (mover_radius + orad + 1.0) ** 2:
            return False
    return True


def _enemy_path_cap_t(start, end, mover_radius, occupants, mover_fly) -> float:
    """Avenue-2 collision: the furthest fraction t in [0, 1] of the segment
    start->end a NON-FLY mover (footprint `mover_radius` inches) may travel before
    any part of its base would cross an ENEMY model's base.

    Real 10e (cited simulator.collision_friendly_passthrough): a model "can be
    moved through friendly models, but it cannot end its move on top of another
    model", and "no part of its base can be moved through an enemy model". So
    FRIENDLIES never cap the PATH (only the END is constrained, in
    _collision_pos_legal) and an ENEMY base on the path stops a non-FLY mover at
    its near boundary (faithful screening). FLY moves OVER enemy models -> never
    path-capped (returns 1.0). Returns 1.0 when nothing caps the path. Pure +
    deterministic; iterates occupants in list order (no set/id ordering)."""
    if mover_fly:
        return 1.0
    occ_iter = occupants._list if type(occupants) is _OccupantGrid else occupants
    sx, sy = start
    ex, ey = end
    vx, vy = ex - sx, ey - sy
    seg2 = vx * vx + vy * vy
    if seg2 == 0.0:
        return 1.0
    # Perf bbox-cull: precompute the segment's axis-aligned bounds. An enemy whose
    # centre lies outside this box expanded by the contact radius rr cannot reach the
    # path, so the (expensive) quadratic is skipped for it. Exact — the bbox+rr is a
    # conservative superset of the real intersection region, so an intersecting enemy
    # is never wrongly skipped and the returned cap is byte-identical to the full scan.
    minx, maxx = (sx, ex) if sx <= ex else (ex, sx)
    miny, maxy = (sy, ey) if sy <= ey else (ey, sy)
    cap = 1.0
    for ox, oy, orad, is_enemy in occ_iter:
        if not is_enemy:
            continue
        rr = mover_radius + orad
        if ox < minx - rr or ox > maxx + rr or oy < miny - rr or oy > maxy + rr:
            continue   # centre outside segment bbox + rr → cannot intersect the path
        # First crossing t of the segment with the circle (centre o, radius rr):
        # |start + t*v - o|^2 = rr^2 -> seg2*t^2 + b*t + c = 0, take the lesser root.
        wx, wy = sx - ox, sy - oy
        b = 2.0 * (wx * vx + wy * vy)
        c = wx * wx + wy * wy - rr * rr
        disc = b * b - 4.0 * seg2 * c
        if disc < 0.0:
            continue   # the segment never reaches this enemy's base
        t_entry = (-b - disc ** 0.5) / (2.0 * seg2)
        if t_entry <= 0.0:
            # Already touching this enemy at start (start is assumed legal, so this
            # is a numerical edge) -> no legal forward travel past it.
            return 0.0
        if t_entry < cap:
            cap = t_entry
    return cap


def _fan_to_goal(start, goal, max_dist, mover_radius, occupants, mover_fly, map_, best):
    """Open-blocked reach recovery (wave 211, gated SWEG_REACH_FIX). A BIG mover whose
    straight end was blocked by a FRIENDLY/terrain (the caller gates this to cap_t>=1,
    i.e. NO enemy on the straight path) and whose pathfinder could not place its base
    near the goal: fan a ring of positions AROUND the goal and take the legal one
    CLOSEST to goal the mover can REACH this move without crossing an enemy.

    The per-candidate `_enemy_path_cap_t >= 1` check is the screening guardrail: a
    FULLY enemy-screened goal yields NO admissible candidate (every approach crosses an
    enemy), so this can never let a mover bypass a screen — the IK over-pole stays
    intact. Only ever IMPROVES on `best` (takes a candidate strictly closer to goal).
    Deterministic: fixed ring + 30°-step angle order, no RNG."""
    import math as _m
    sx, sy = start
    gx, gy = goal
    md2 = max_dist * max_dist
    best_d2 = (best[0] - gx) ** 2 + (best[1] - gy) ** 2
    for ring in (mover_radius + 0.5, mover_radius + 2.0, 3.5, 6.0):
        for k in range(12):
            ang = _m.radians(k * 30.0)
            cx = max(0.0, min(map_.width, gx + ring * _m.cos(ang)))
            cy = max(0.0, min(map_.height, gy + ring * _m.sin(ang)))
            d2 = (cx - gx) ** 2 + (cy - gy) ** 2
            if d2 >= best_d2:
                continue                                  # not closer to goal
            if (cx - sx) ** 2 + (cy - sy) ** 2 > md2:
                continue                                  # out of this move's reach
            if map_.is_blocked((cx, cy)):
                continue
            if _enemy_path_cap_t(start, (cx, cy), mover_radius, occupants, mover_fly) < 1.0:
                continue                                  # path crosses an enemy → screened, skip
            if not _collision_pos_legal((cx, cy), mover_radius, occupants, mover_fly):
                continue                                  # would end on a model
            best = (cx, cy)
            best_d2 = d2
    return best


def _move_toward(
    start: Tuple[float, float],
    goal: Tuple[float, float],
    max_dist: float,
    map_: Map,
    mover_radius: float = 0.0,
    occupants=None,
    mover_fly: bool = False,
    sidestep: bool = True,
) -> Tuple[float, float]:
    """Move from start toward goal up to max_dist inches.

    Clamps to map bounds. If the destination point lies inside impassable
    terrain, the move is aborted and the unit stays put — crude but enough
    for Phase A.

    Avenue-2 Stage 1 no-overlap collision (default-OFF / byte-identical): when
    `occupants` is None (every caller today, and whenever SWEG_COLLISION is off) the
    function behaves exactly as before. When a caller passes the per-phase occupant
    list (other alive models as (x, y, radius, is_enemy)) plus the mover's footprint
    radius, the END position is validated against `_collision_pos_legal`; if illegal,
    the destination is walked back toward `start` by deterministic bisection (capped
    iterations) to the last legal point. `start` is assumed legal (the mover is there
    now). FLY skips the enemy/Engagement-Range test (handled in the helper)."""
    dx = goal[0] - start[0]
    dy = goal[1] - start[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist == 0 or dist <= max_dist:
        new = goal
    else:
        scale = max_dist / dist
        new = (start[0] + dx * scale, start[1] + dy * scale)
    new_x = max(0.0, min(map_.width, new[0]))
    new_y = max(0.0, min(map_.height, new[1]))
    new_point = (new_x, new_y)
    if map_.is_blocked(new_point):
        return start
    if occupants is None:
        return new_point
    # Collision ON. Faithful 10e movement vs other models (cited
    # simulator.collision_friendly_passthrough): a model "can be moved through
    # friendly models, but it cannot end its move on top of another model", and
    # "no part of its base can be moved through an enemy model" (FLY moves over
    # enemies). So FRIENDLIES never block the PATH — they are passed through, only
    # the END must be clear of every model (+ enemy Engagement Range); an ENEMY
    # base on the straight path CAPS how far a non-FLY mover travels (faithful
    # screening — a Knight cannot pass through an enemy horde).
    cap_t = _enemy_path_cap_t(start, new_point, mover_radius, occupants, mover_fly)
    straight_legal = (
        cap_t >= 1.0
        and _collision_pos_legal(new_point, mover_radius, occupants, mover_fly)
    )
    # PATHFINDING Stage-0 GO/NO-GO counter (read-only, gated). Records how often the
    # straight end is blocked (now: enemy-capped path OR an illegal end) — the
    # blocked-move frequency that, times the per-call A* cost, is the perf decision.
    if __import__("os").environ.get("SWEG_PATHFIND_STAGE0"):
        _big = mover_radius >= _PATHFIND_BIG_RADIUS_IN
        PATHFIND_STAGE0_STATS["total_big" if _big else "total_small"] += 1
        if not straight_legal:
            PATHFIND_STAGE0_STATS["blocked_big" if _big else "blocked_small"] += 1
    # Reach instrument (read-only): classify big-mover blocks as faithful enemy
    # screening (cap_t<1) vs open-space artifact (cap_t>=1 but end illegal).
    if __import__("os").environ.get("SWEG_REACH_INSTR") and mover_radius >= _PATHFIND_BIG_RADIUS_IN:
        REACH_STATS["big_moves"] += 1
        if straight_legal:
            REACH_STATS["big_reached"] += 1
        elif cap_t < 1.0:
            REACH_STATS["big_enemy_capped"] += 1
        else:
            REACH_STATS["big_open_blocked"] += 1
    if straight_legal:
        return new_point
    # Straight move capped by an enemy and/or its end overlaps a model. Find the
    # furthest LEGAL END at or before the enemy cap, PASSING THROUGH friendlies:
    # scan inward from the capped reach and take the first legal end. A legal end
    # BEYOND a friendly (within the enemy cap) is reached — fixing the self-jam
    # where the old bisection halted the mover at a friendly model's near edge.
    # Deterministic (fixed step order, no RNG).
    import math as _m
    sx, sy = start
    vx, vy = new_point[0] - sx, new_point[1] - sy
    best = start
    _STEPS = 24
    for _i in range(_STEPS, -1, -1):
        t = cap_t * (_i / _STEPS)
        cand = (sx + vx * t, sy + vy * t)
        if not map_.is_blocked(cand) and _collision_pos_legal(cand, mover_radius, occupants, mover_fly):
            best = cand
            break
    # PATHFINDING (avenue-2 Stage 2, gated SWEG_PATHFIND): a BIG mover whose straight
    # end is blocked routes AROUND the obstacle field via coarse grid A* (code/pathfind)
    # instead of the local 6-angle sidestep, which dead-ends against a wall of blockers
    # (screen + ruins) and crashes big-base reach (62%->16%). Big-bases-only; small
    # INFANTRY keep the O(1) sidestep below. The returned furthest-legal point is
    # re-validated exactly (the A* grid is coarse) and falls back to the straight
    # walk-back on the rare coarse-grid miss. OFF (gate unset) -> byte-identical.
    if mover_radius >= _PATHFIND_BIG_RADIUS_IN and __import__("os").environ.get("SWEG_PATHFIND", "1") != "0":
        walls = map_.wall_segments() if map_ is not None else ()
        p = find_path(start, goal, max_dist, mover_radius, occupants, walls=walls, map_=map_)
        if _collision_pos_legal(p, mover_radius, occupants, mover_fly):
            best = p   # pathfinder's furthest legal point (may still strand the base short)
        # Open-blocked reach recovery (gated SWEG_REACH_FIX, default-ON; =0 reverts):
        # ONLY when no enemy capped the straight path (cap_t>=1) — an enemy-capped move
        # (cap_t<1) is faithful screening and is left exactly as-is, so this cannot undo
        # the Knight over-pole fix. Fans a big mover around its own clustered army to a
        # legal spot near the goal it could not stack on (per-candidate enemy-clear).
        if cap_t >= 1.0 and __import__("os").environ.get("SWEG_REACH_FIX", "1") != "0":
            best = _fan_to_goal(start, goal, max_dist, mover_radius, occupants,
                                mover_fly, map_, best)
        return best
    if not sidestep:
        # Big movers (blocker-makes-way model): stop straight at the blocker — an
        # ENEMY blocker SHOULD halt a Knight (faithful screening); friendly blockers
        # are cleared beforehand by _clear_lane. No detour around own army.
        return best
    best_d2 = (best[0] - goal[0]) ** 2 + (best[1] - goal[1]) ** 2
    # (b) angular sidesteps at full reach — step AROUND the blocker. Take the legal
    # candidate closest to goal (most forward progress). Reach capped so a wide angle
    # near the goal does not overshoot.
    reach = min(max_dist, dist)
    base = _m.atan2(goal[1] - sy, goal[0] - sx)
    for deg in (20.0, -20.0, 40.0, -40.0, 60.0, -60.0):
        ang = base + _m.radians(deg)
        cx = max(0.0, min(map_.width, sx + reach * _m.cos(ang)))
        cy = max(0.0, min(map_.height, sy + reach * _m.sin(ang)))
        if map_.is_blocked((cx, cy)):
            continue
        if not _collision_pos_legal((cx, cy), mover_radius, occupants, mover_fly):
            continue
        d2 = (cx - goal[0]) ** 2 + (cy - goal[1]) ** 2
        if d2 < best_d2:
            best = (cx, cy)
            best_d2 = d2
    return best


# ---------------------------------------------------------------------------
# Battle engine
# ---------------------------------------------------------------------------

# A SwegHammer round is "every unit on both sides has activated once". A full
# game is 5 rounds (matches 10e). Round limit is also a backstop against
# pathological infinite loops if attrition somehow stalls.
MAX_ROUNDS = 5
CP_BONUS_DIVISOR = 2    # opponent must have this many more units per 1 CP awarded
CP_BONUS_CAP = 2        # max CP awarded per round
# 10e Unit Coherency band: every model must be within 2" of at least one other
# model in its unit (cited as `simulator.coherency_enforcement`). Used by the
# squad-rebuild Stage B post-move coherency pass.
COHERENCY_INCHES = 2.0

# OC-FLIP over-hold INSTRUMENT (#79, wave 192) — read-only accumulator, populated
# only when the env gate SWEG_OCFLIP_INSTR is set. Quantifies objective-rounds
# where a damaged big durable holder (a Knight / Titanic or big VEHICLE/MONSTER
# now in its damaged bracket, so effective OC < base OC) controls a marker the
# opponent COULD flip by committing nearby bodies (reachable OC > holder's
# effective on-marker OC). No behaviour change — purely measured. A diag runner
# resets and reads this. Keys: held = obj-rounds a damaged big-holder controls a
# marker; flippable = of those, how many the opponent could flip with nearby
# bodies; surplus = summed (opponent reachable OC − holder OC) over flippable.
OCFLIP_STATS = {"held": 0, "flippable": 0, "surplus": 0.0,
                "held_any": 0, "flippable_any": 0,
                # Reason-decomposition of the opponent's reachable OC on the
                # flippable-but-uncontested markers (#80 follow-up): how much is
                # melee (would abandon a fight to contest), shooty that could
                # shoot FROM the marker (the FREE-CONTEST opportunity the lever
                # should add), and shooty that would LOSE its shots from there
                # (correctly not pulled — a gunline-pull).
                "fc_melee_oc": 0.0, "fc_free_oc": 0.0, "fc_noshoot_oc": 0.0,
                # BURN-reachability (#87 avenue-1): of the obj-rounds a damaged big
                # holder controls a marker, how many have an OPPONENT unit that
                # could REACH the marker (within ~one move) and is NOT engaged — so
                # it could perform the Scorched Earth Burn Action (remove the
                # marker for VP, no OC win needed). Pre-check before the Burn build.
                "burn_reachable": 0}

# OVER-SCORE instrument (#83) — per-faction split of scored markers into
# (iii) contested-but-won vs (i) uncontested. Populated only when
# SWEG_OVERSCORE_INSTR is set; a diag runner resets and reads it. Read-only.
OVERSCORE_STATS: dict = {}

# OC-DELIVERY instrument (#84) — per-faction on-board OC vs OC delivered onto
# markers. Populated only when SWEG_DELIVERY_INSTR is set. Read-only.
DELIVERY_STATS: dict = {}

# SCREENING / shoot-loss instrument (#86) — per-faction shooting output split by
# free / pistol / big-gun-penalty / engagement-blocked. SWEG_SHOOTLOSS_INSTR. Read-only.
SHOOTLOSS_STATS: dict = {}

# BOARD-CONTROL instrument (avenue-2 Stage 0, docs/BOARD_CONTROL_PLAN.md) — sizes the
# physical-board-control levers (no-overlap collision / ruin-wall movement / make-way).
# Populated ONLY when SWEG_BOARDCTRL_INSTR is set; a diag runner resets + reads it.
# Read-only. Measures, at settled objective-scoring snapshots: how packed OC-counted
# models are within 3" of markers (a >100% base-area packing ratio = OC that no-overlap
# collision will physically cap), how many base footprints actually overlap, how
# concentrated OC is on CONTESTED markers, and — a settled-position proxy for the
# ruin-wall lever — how often a big VEHICLE/MONSTER/TITANIC (non-FLY) model sits inside a
# RUIN footprint it should have to route around. Plus a per-faction JAM baseline at game
# end (models stranded in own deployment zone + mean squad->nearest-objective distance),
# the anti-regression yardstick Stages 1-4 must not worsen.
BOARDCONTROL_STATS: dict = {
    "obj_rounds": 0, "overlap_pairs": 0,
    "packing_sum": 0.0, "packing_n": 0, "packing_over100": 0,
    "contested_rounds": 0, "contested_packing_sum": 0.0,
    "big_in_ruin": 0, "big_snaps": 0,
    "jam": {},  # faction -> {games, dz_models_sum, min_dist_sum, squads}
}

# PATHFINDING Stage-0 GO/NO-GO counter (read-only; docs/PATHFINDING_PLAN.md). Counts,
# under SWEG_COLLISION, how often a collision move's STRAIGHT end is blocked (the case
# a pathfinder would have to route around), split big-base vs small-base. Only mutated
# when occupants are passed (collision active) AND SWEG_PATHFIND_STAGE0 is set — the
# production default path returns before this block, so it stays byte-identical.
PATHFIND_STAGE0_STATS: dict = {
    "total_big": 0, "blocked_big": 0, "total_small": 0, "blocked_small": 0,
}
# Reach-degradation instrument (gated SWEG_REACH_INSTR, wave 211): per BIG-mover
# move under collision, classify the block — an ENEMY on the path (cap_t<1) is
# FAITHFUL screening (keep), while reaching short with NO enemy on the path
# (cap_t>=1 but the straight end is illegal → overlaps a friendly/terrain) is the
# open-space over-impediment ARTIFACT to fix. Read-only; the diag runner resets it.
REACH_STATS: dict = {
    "big_moves": 0, "big_reached": 0, "big_enemy_capped": 0, "big_open_blocked": 0,
}
# A mover is "big" for pathfinding purposes when its footprint radius exceeds this
# (~38mm base). A 170mm Knight is ~3.3", infantry ~0.63" — the threshold cleanly
# separates the big bases that crash their reach from the small bases that sidestep fine.
_PATHFIND_BIG_RADIUS_IN = 1.5


def _bc_model_radius_in(profile) -> float:
    """Base-footprint radius in INCHES for a model (read-only instrument helper).
    NOTE: deliberately NOT lru_cache'd — UnitProfile is a large frozen dataclass
    (carries the model_loadouts tuple), so hashing it per call costs MORE than this
    arithmetic (measured: caching slowed the dense-horde bench). The per-phase occupant
    grid is the right place to avoid the O(models^2) repetition, not a per-call cache.
    25.4 mm/in. CRITICAL: oval/rect bases (Knights, big VEHICLEs) store their real
    footprint in base_width_mm x base_length_mm while base_diameter_mm holds a 32mm
    PLACEHOLDER — so take the LARGER of the circle-derived and the width/length-
    derived radius (a 170mm Knight must not be mis-sized as a 32mm infantry base,
    which 4x-undercounts its footprint area and hides the marker-denial it causes).
    Defaults to ~32mm round (0.63") only if no base data at all."""
    d = getattr(profile, "base_diameter_mm", 0) or 0
    w = getattr(profile, "base_width_mm", 0) or 0
    ln = getattr(profile, "base_length_mm", 0) or 0
    r_circle = (d / 25.4) / 2.0 if d > 0 else 0.0
    r_wl = ((w + ln) / 2.0 / 25.4) / 2.0 if (w and ln) else 0.0
    r = max(r_circle, r_wl)
    return r if r > 0 else 0.63


@dataclass(frozen=True)
class RulesConfig:
    """Toggles for SwegHammer's non-10e rule modifications.

    Vanilla 10e mode (all False) runs the simulator under standard WH40k 10e
    core rules: I-go-you-go player turns, no smaller-army CP catch-up, no
    coordinated army-plan activation scheduler, sequential per-unit
    move→shoot→charge→fight inside each player's turn. This is the mode the
    MC bisection (code/balancer.py) and the eval-vs-meta script run against
    so the simulator faithfully reproduces tournament play.

    SwegHammer mode (all True via .sweghammer()) is the project's original
    ruleset: alternating per-unit activations across both armies within a
    round, simultaneous-movement sub-phase, CP catch-up bonus for the
    smaller army, coordinated army-level activation plans. Opt-in only;
    used when simulating gameplay UNDER the SwegHammer ruleset rather than
    deriving prices.
    """

    alternating_activations: bool = False
    """Per-unit alternation between armies within a round. Vanilla 10e is
    I-go-you-go player turns. SwegHammer flips this for action density."""

    simultaneous_movement: bool = False
    """Both units in the alternating-activation pair move BEFORE either
    shoots — avoids the second-mover-sees-closing-distance asymmetry that
    plain per-unit-sequence would create. Implies alternating_activations."""

    cp_catchup_bonus: bool = False
    """After Round 1, if the opponent has ≥2× more units, the smaller army
    gains 1 CP per round (max +2). Pure SwegHammer catch-up; 10e has no
    such mechanic."""

    coordinated_army_plan: bool = False
    """Each army picks ONE plan (LEFT_FLANK / RIGHT_FLANK / CENTRE) per
    round biasing both activation order and per-unit move/charge intent.
    Internal AI scheduler with cross-unit coordination no real 10e player
    has mid-battle."""

    @classmethod
    def vanilla_10e(cls) -> "RulesConfig":
        """Standard WH40k 10e core rules — all SwegHammer mods off."""
        return cls()

    @classmethod
    def sweghammer(cls) -> "RulesConfig":
        """All SwegHammer rule modifications on."""
        return cls(
            alternating_activations=True,
            simultaneous_movement=True,
            cp_catchup_bonus=True,
            coordinated_army_plan=True,
        )


class Battle:
    """
    Runs a single engagement between two armies under SwegHammer rules:
      - Units deploy in their army's deployment zone at battle start.
      - Each activation: move toward focused target if out of range, then
        attack if in range.
      - Alternating activations within a round; first player randomised.
      - CP bonus awarded to the smaller army after Round 1.
      - Stochastic per-attack rolls (hit, wound, save) via Unit.attack().
    """

    def __init__(
        self,
        army_a: Army,
        army_b: Army,
        verbose: bool = False,
        subscribers: Optional[List[Subscriber]] = None,
        map_: Optional[Map] = None,
        rules: Optional[RulesConfig] = None,
        primary_mission: Optional[str] = None,
    ) -> None:
        self.a = army_a
        self.b = army_b
        self.verbose = verbose
        self.subscribers: List[Subscriber] = list(subscribers) if subscribers else []
        self.map: Map = map_ or DEFAULT_MAP
        # Wave 187 (#71): the primary mission whose VP scoring rule this battle
        # uses (see _score_objectives). Default "take_and_hold" reproduces the
        # legacy single-mission behaviour byte-for-byte; the eval rotates the real
        # Chapter Approved 2025-26 primaries when SWEG_PRIMARY_MISSION is set or a
        # mission is passed in. An explicit arg wins; else the env var; else the
        # holder-friendly Take and Hold default.
        self.primary_mission: str = (
            primary_mission
            or __import__("os").environ.get("SWEG_PRIMARY_MISSION")
            or "take_and_hold"
        )
        # Default is vanilla WH40k 10e mode — the simulator's primary
        # responsibility is faithfully reproducing tournament play (the
        # MAE-vs-real-meta signal). SwegHammer's alternating-activation
        # ruleset is opt-in via `RulesConfig.sweghammer()` for users who
        # want to play games under SwegHammer rules; it does not touch
        # calibration. See plan `enchanted-wiggling-sundae` step 1.
        self.rules: RulesConfig = rules if rules is not None else RulesConfig.vanilla_10e()
        # UIDs of units that Advanced in the current round — they skip shooting.
        # Reset at the start of each round.
        self._advanced_this_round: set = set()
        # Wave 76: per-squad charge roll cache (squad_id -> (d1, d2)). A codex
        # unit makes ONE 2D6 charge roll in real 10e, but SwegHammer's
        # one-Unit-per-model representation rolled once per MODEL — an 11-model
        # mob got 11 independent attempts (~97% to make a 9" charge vs the real
        # ~28%). Sharing one roll per squad per round caps melee hordes at the
        # faithful single-roll reliability. Cited as `simulator.charge_per_unit`.
        self._squad_charge_roll: dict = {}
        # Wave 77: per-squad Advance roll cache (squad_id -> d6). Real 10e makes
        # ONE Advance roll per unit; SwegHammer rolled per model. Same per-unit
        # correctness pattern as the charge roll. Cited `simulator.advance_per_unit`.
        self._squad_advance_roll: dict = {}
        # Squad rebuild Stage A (gate SWEG_SQUADACT): per-phase cache of each
        # squad's move decision, computed once on the squad's first activating
        # model and read by later stages (B/D/E). INERT in Stage A (execution
        # stays per-model). The squad — not the individual model — is the real
        # 10e activation unit; SwegHammer's one-Unit-per-model representation
        # activates every model independently. These two fields are the
        # substrate the coherency / cohesive-hold / split-fire stages will read.
        # In Stage A they are written but never applied, so the simulator is
        # byte-identical whether the gate is on or off.
        self._squad_move_intent: dict = {}
        self._squad_activated_this_phase: set = set()
        # Squad rebuild Stage D — unit-orchestrated split-fire (gate
        # SWEG_SQUADSHOOT). `_squad_fire_plan` maps a model uid -> the enemy Unit
        # the squad's fire plan assigns it; `_squad_fire_planned` holds the squad
        # keys already planned this Shooting phase (lazy compute on a squad's
        # first firing model). Reset each Shooting phase. Empty / unread when the
        # gate is off, so the OFF path is byte-identical.
        self._squad_fire_plan: dict = {}
        self._squad_fire_planned: set = set()
        # UIDs of units that failed their Battleshock test this round — OC 0
        # so they don't contribute to objective control. Reset per round.
        self._battleshocked_this_round: set = set()
        # Insane Bravery (1 CP universal Epic Deed, 10e core): each army may
        # auto-pass ONE Battle-shock test PER BATTLE. id(army) is added here when
        # an army spends it; NOT reset per round (once-per-battle gate). Cited
        # `simulator.insane_bravery`.
        self._insane_bravery_used: set = set()
        # UIDs of units that successfully charged this round (Fights First in
        # the Fight sub-phase). Reset each round.
        self._charging_this_round: set = set()
        # Fire Overwatch (10e core stratagem, env-gated SWEG_OVERWATCH). Set of
        # army NAMES that have already used the Fire Overwatch stratagem this
        # battle round. The core rule reads "you can only use this Stratagem
        # once per turn"; SwegHammer's round loop does not cleanly separate the
        # two players' turns for every trigger path, so the flag is reset per
        # battle round in `_run_round`, capping each army at one overwatch use
        # per round (conservative — at most one per army, never both turns).
        # Cited as `simulator.fire_overwatch`.
        self._overwatched_this_round: set = set()
        # UIDs of units that moved during the movement sub-phase this round.
        # Drives the Heavy keyword (+1 to hit if attacker did NOT move).
        # Reset each round.
        self._did_move_this_round: set = set()
        # UIDs of units that disembarked from a TRANSPORT this round (10e
        # core: "If a unit disembarks from a Transport in your Movement
        # phase, it cannot make a Normal, Advance or Fall Back move that
        # turn. The unit is then treated as having moved a distance equal
        # to its Move characteristic this turn."). The unit may still
        # Shoot and Charge normally. Reset each round. Cited as
        # `simulator.disembark`.
        self._disembarked_this_round: set = set()
        # UIDs of units that have already fired their One Shot weapon this
        # battle. Once a uid is here, the unit may not shoot again.
        # Persists for the whole battle (NOT reset per round).
        self._one_shot_fired: set = set()
        # Phase I — units with Deep Strike that haven't yet arrived. Keyed
        # by army name; each value is a list of Unit instances waiting in
        # reserves. They are added to army.units when they arrive so the
        # normal activation loop picks them up from that round onward.
        self._reserves: dict = {self.a.name: [], self.b.name: []}
        # UIDs of units that JUST arrived from reserves OR just scouted
        # this round — they've already moved as part of arrival / scouting
        # so the simulator skips their movement sub-phase for one round.
        # Reset each round (except Round 1 inherits scout flags).
        self._fresh_arrivals: set = set()
        # Issue #75 — Reanimation Protocols. Snapshot of how many units of
        # each profile each army started with (army.units + reserves).
        # Used end-of-round to compute `destroyed = initial - alive_now` and
        # revive dead model instances by re-setting their current_health.
        # Populated by Battle.run() once deployment has settled.
        self._initial_unit_counts: Dict[str, Dict[str, int]] = {}
        # Fix F-NEC-1 (iter 2): RP must gate on "lost a model THIS round"
        # per Wahapedia "has had one or more destroyed bodyguard models"
        # clause. Snapshot taken at the top of each round so end-of-round
        # `_apply_reanimation` can diff alive_now vs round_start to see
        # whether any model died this round. Without this gate, a stable
        # squad keeps reviving every round just because its current count
        # is below STARTING strength.
        self._round_start_alive_counts: Dict[str, Dict[str, int]] = {}
        # Issue #85 — Sticky Objectives. Once a sticky_objective unit claims
        # an objective for its army, ownership persists here keyed by the
        # objective's index in self.map.objectives. Cleared when the opposing
        # side outscores the holder's army on the objective in a later round.
        self._sticky_owner: Dict[int, str] = {}
        # Scorched Earth Burn/Raze (#87, gated SWEG_SCORCHED_BURN): obj_idx set of
        # markers RAZED this battle — removed from the board, so neither side scores
        # them by holding for the rest of the game. Permanent.
        self._razed_objectives: set = set()
        # uid -> obj_idx the unit's in-progress Burn targets this round (Unit is
        # __slots__-ed, so the target lives here, not on the Unit).
        self._burn_targets: dict = {}
        # Terraform primary (#87 avenue-1, gated SWEG_TERRAFORM): obj_idx -> "a"/"b"
        # for the side that has TERRAFORMED each marker. A marker is terraformed by
        # at most one side at a time (a fresh terraform OVERWRITES the opponent's per
        # the real CA-2025-26 rule). Each terraformed marker yields its owner +1 VP
        # per turn. Persists once set (until overwritten). uid -> obj_idx holds the
        # in-progress Terraform Action target (mirrors _burn_targets).
        self._terraformed_owner: dict = {}
        self._terraform_targets: dict = {}
        # Stratagem book-keeping. Each army keeps a set of stratagem names
        # already fired this battle (used for once_per_battle stratagems —
        # the four universals are not once-per-battle but the field is here
        # for #104). Also a back-reference from each Army to this Battle so
        # Unit.attack can dispatch the Command Re-Roll hook without dragging
        # a callback through every call site.
        self._stratagems_fired_this_battle: Dict[str, set] = {
            self.a.name: set(), self.b.name: set(),
        }
        self.a._battle_ref = self
        self.b._battle_ref = self
        # Current battle round (1..MAX_ROUNDS). Updated at the top of each
        # _run_round; read by Unit.attack for round-gated faction rules
        # like the Orks WAAAGH! +1 to wound melee window.
        self._current_round: int = 0
        # Per-Command-phase primary scoring — now DEFAULT-ON (fidelity-revisit sweep
        # #3, wave 210). Primary VP is scored at each player's Command phase (turn
        # start) inside the vanilla IGOUGO round, instead of once at end of round —
        # the real 10e timing (the end-of-round snapshot under-credited mobile holders).
        # Faithful AND improved the metric (5.72 → 5.44 N=80). `SWEG_CMDSCORE=0` reverts.
        self._cmd_score: bool = __import__("os").environ.get("SWEG_CMDSCORE", "1") != "0"
        # SC4-A — 10e Pariah Nexus secondary objectives. Each round we
        # snapshot each army's alive units at round start (in `_run_round`)
        # and compute Bring it Down + No Prisoners VP at round end (in
        # `run` after `_score_objectives`). Per-round caps live in
        # `code/secondaries.py`. The snapshot is per-army; we score side A
        # against side B's snapshot (i.e. side A scores VP for killing
        # side B's units this round).
        from .secondaries import RoundSnapshot  # noqa: F401  (type only)
        self._a_round_snapshot = None  # snapshot of A's units at round start
        self._b_round_snapshot = None  # snapshot of B's units at round start
        self._a_secondary_vp: int = 0  # cumulative secondary VP for side A
        self._b_secondary_vp: int = 0  # cumulative secondary VP for side B
        # Wave 83 Tier A: which side ('a'/'b'/None) controlled each objective
        # at the START of the current round — consumed by Storm Hostile
        # Objective ("control an objective the opponent controlled at the start
        # of the turn"). Refreshed in the round-start snapshot.
        self._obj_controller_at_round_start: dict = {}
        # Iter-4 A5: flag set TRUE while inside `_apply_detachment_stratagems`
        # so `_fire_stratagem` knows whether to increment the per-army
        # per-Command-phase counter. Always False outside that scope —
        # Tank Shock, Counter-Offensive, Command Re-Roll fire on their
        # own per-trigger hooks and don't count toward the detachment-
        # stratagem cap. (Heroic Intervention is a free core CHARACTER
        # ability, not a stratagem at all — see _do_heroic_intervention.)
        self._dispatching_detachment_stratagems: bool = False
        # Per-squad battleshock (task #27): snapshot of starting model count
        # per squad_id, taken once at __init__ time, keyed as
        # (army.name, squad_id) to avoid collisions between the two armies
        # (both reset squad_id from 0 so a plain squad_id key would merge
        # army A's squad 0 with army B's squad 0).  Used by
        # `_run_battleshock_phase` to determine whether a squad is Below
        # Half-Strength by surviving model count (10e core: "a unit is Below
        # Half-strength if the number of models in it is below half its
        # Starting Strength").  Squads of size 1 (single-model units) keep
        # the per-model wound-based test as described in the task brief and
        # consistent with the 10e intent — a lone model is tested on wounds,
        # not on model count (1 < 0.5 is never true).
        from collections import Counter as _C
        self._squad_start_count: dict = {}
        for _army in (self.a, self.b):
            counts = dict(_C(
                u.squad_id for u in _army.units
                if u.squad_id >= 0
            ))
            for _sid, _cnt in counts.items():
                self._squad_start_count[(_army.name, _sid)] = _cnt

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> BattleResult:
        # APPROXIMATION: Battle Focus modelled as a flat 4-token pool spent only on Star Engines / [ASSAULT].
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/
        # Real rule: per-round token refresh + 6 named Agile Manoeuvres (Star Engines, Wraithwalk,
        # Lightning-Fast Reactions, etc.). We conflate the whole bundle into a single shoot-after-Advance
        # spend, omitting the other 5 named manoeuvres entirely.
        # Battle Focus tokens (Aeldari ASURYANI rule): 4 at Strike Force,
        # the default battle size for this simulator. We hand the tokens
        # out to any army that contains at least one ASURYANI unit — the
        # rule is faction-wide, not detachment-gated.
        # Warhost detachment rule "Martial Grace" (#197) grants +1 token
        # at start of each battle round; since SwegHammer's Battle Focus
        # model is a flat once-at-start pool rather than a per-round
        # refresh, we collapse the +1/round buff into +1 to the starting
        # pool (over 5 rounds the codex hands out +5, but the simulator
        # only spends tokens on the rarely-triggered shoot-after-Advance
        # path; +1 to the pool is a clean single-bump approximation).
        # Gates on Detachment.martial_grace via resolve_detachment so the
        # bump fires only when Warhost is the active detachment.
        for army in (self.a, self.b):
            if any("ASURYANI" in (u.profile.unit_keywords or ())
                   for u in army.units):
                base_tokens = 4
                det = army.resolve_detachment() if hasattr(army, "resolve_detachment") else None
                if det is not None and getattr(det, "martial_grace", False):
                    base_tokens += 1
                army.battle_focus_tokens = base_tokens

        # Strands of Fate (Aeldari army rule, 10e). At the start of the
        # first battle round, before the first turn begins, the AELDARI
        # player rolls 6D6 and sets those dice aside as their pool of
        # Fate dice. Each die can later be substituted for one d6 roll
        # made by/against an AELDARI unit (hit, wound, save, charge,
        # advance, Battle-shock). The pool depletes with each spend; once
        # empty, no more substitutions are available. Cited as
        # `simulator.strands_of_fate`. APPROXIMATION: the simulator's
        # spend AI is a greedy heuristic (pop the lowest die that
        # successfully flips a fail -> success), not the optimal play of
        # a real Aeldari player. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
        # Gate on faction tag (Aeldari codex) rather than the AELDARI
        # unit keyword — BSData's parser keeps the codex-wide AELDARI
        # keyword as faction meta rather than per-unit unit_keywords, so
        # the keyword check would never fire on real Aeldari datasheets
        # (Troupe, Solitaire, Shroud Runners). The faction tag is set
        # by code.factions.faction_of and uniquely identifies the
        # Aeldari codex (Drukhari are a separate faction string).
        for army in (self.a, self.b):
            if any(u.profile.faction == "Aeldari" for u in army.units):
                army.fate_dice = sorted(
                    [random.randint(1, 6) for _ in range(6)],
                    reverse=True,
                )

        # CP-econ Warlord scan (Belisarius Cawl, Roboute Guilliman, Trazyn
        # the Infinite, Lord of Contagion). Seeds Army.cp_refund_remaining
        # and Army._warlord_first_strat_free_enabled from the resolved
        # Warlord's LeaderAbility. Armies without a CP-econ Warlord keep
        # their defaults and the discount/refund gates stay dormant — this
        # is the gate that ensures the mechanic never accidentally grants
        # CP to a non-Warlord-having army.
        from .leaders import warlord_ability
        for army in (self.a, self.b):
            wl = warlord_ability(army)
            if wl is None:
                continue
            army.cp_refund_remaining = wl.cp_refund_per_battle
            army._warlord_first_strat_free_enabled = wl.first_stratagem_free_per_round

        # Drukhari Combat Drugs (army rule, 10e). DRK-NON-SKYSPLINTER-V1
        # (2026-05-29): drug application moved from pre-game (battle start)
        # to the Round 1 Command phase. The real Wahapedia rule text is:
        # "At the start of your Command phase, select which Combat Drugs
        # will be active for your army until the start of your next Command
        # phase. You cannot select the same Combat Drug more than once per
        # battle." Since only Adrenalight is modelled and it cannot repeat,
        # the drug fires for Round 1 only. The pre-game call is removed;
        # `_apply_combat_drugs(round_num)` is now invoked from `_run_round`
        # at the start of the Command phase. Cited as `simulator.combat_drugs`.

        self._assign_uids()
        # SECONDARY-SELECTION-V1: pick each army's 2 Fixed + 2 Tactical
        # Pariah Nexus secondaries BEFORE `_deploy_armies` reorganises the
        # roster. GSC armies have their full roster moved into reserves
        # by Cult Ambush, so the picker would otherwise see an empty
        # `army.units` for the GSC side. Called once per battle and the
        # picks persist on the army for the whole run.
        # Cited as `simulator.secondary_selection`.
        from .secondaries import pick_secondaries as _pick_secondaries
        self.a.chosen_secondaries = _pick_secondaries(self.a, self.b)
        self.b.chosen_secondaries = _pick_secondaries(self.b, self.a)
        # M2 (wave 119, env-gated SWEG_TAC_DECK) — seed each TACTICAL army's
        # 2-card hand + remaining deck deterministically. `pick_secondaries`
        # set `secondary_track`; this fills `tactical_hand`/`tactical_deck`.
        # Inert (no-op) when the gate is off or the army is on the FIXED track.
        # Cited as `simulator.tactical_secondary_deck`.
        self._init_tactical_deck(self.a)
        self._init_tactical_deck(self.b)
        self._deploy_armies()
        # Phase I — pre-game Scouts move happens AFTER deployment and BEFORE
        # Round 1 begins. Deep Strike arrivals start at Round 2.
        self._run_scout_phase()

        # Include reserves so the "starting unit count" reflects the full
        # army roster, not just what was on the board at deployment.
        a_start = len(self.a.units) + len(self._reserves.get(self.a.name, []))
        b_start = len(self.b.units) + len(self._reserves.get(self.b.name, []))
        # Snapshot starting points across BOTH on-board and reserve units so
        # the WAAAGH! AI's "below 70% starting points" emergency trigger
        # measures attrition against the full roster, not just the deployed
        # slice. Applied to every army (cheap, scoped attribute), only Ork
        # armies actually consult it.
        for army in (self.a, self.b):
            roster_pts = sum(u.profile.points_cost for u in army.units) + sum(
                u.profile.points_cost
                for u in self._reserves.get(army.name, [])
            )
            army.starting_points = float(roster_pts)
        # Genestealer Cults — Cult Ambush Resurgence points (10e army rule).
        # Strike Force default = 10 points; spent at round end to revive
        # destroyed CULT INFANTRY units (APPROXIMATION proxy for the
        # Resurgence/Cult Ambush marker resurrection mechanic). Cited as
        # `simulator.cult_ambush_resurgence`.
        #
        # GSC-DIAG bugfix: because Cult Ambush routes the ENTIRE GSC army
        # into reserves at deployment, `army.units` is empty for the GSC
        # side at this point. The previous gate `army.units[0].profile.
        # faction == "Genestealer Cults"` therefore never matched, and
        # GSC armies started every battle with 0 Resurgence — silently
        # disabling the revival half of Cult Ambush. We now inspect
        # reserves too, so the pool is correctly seeded for the GSC army
        # before Round 1 begins.
        for army in (self.a, self.b):
            roster = list(army.units) + list(self._reserves.get(army.name, []))
            if roster and roster[0].profile.faction == "Genestealer Cults":
                army.cult_ambush_resurgence_points = 10
        # Reanimation Protocols (#75): snapshot starting model counts per
        # profile per army, including reserves. End-of-round revival reads
        # this to compute how many models have been destroyed.
        for army in (self.a, self.b):
            counts: Dict[str, int] = {}
            for u in army.units:
                counts[u.profile.name] = counts.get(u.profile.name, 0) + 1
            for u in self._reserves.get(army.name, []):
                counts[u.profile.name] = counts.get(u.profile.name, 0) + 1
            self._initial_unit_counts[army.name] = counts
        # VP tally accumulates across rounds
        self._a_vp = 0
        self._b_vp = 0

        # Snapshot includes on-board units AND reserves (deep-strikers).
        # Reserves get an off-board sentinel position so renderers know they
        # exist but don't draw them on the map yet — they'll get a real
        # position when UnitDeepStrike fires.
        snapshot = []
        for army in (self.a, self.b):
            for u in army.units:
                snapshot.append(InitialUnit(
                    uid=u.uid, name=u.profile.name, army=army.name,
                    position=u.position, max_health=u.profile.health,
                    unit_keywords=tuple(u.profile.unit_keywords or ()),
                    base_shape=u.profile.base_shape,
                    base_diameter_mm=u.profile.base_diameter_mm,
                    base_width_mm=u.profile.base_width_mm,
                    base_length_mm=u.profile.base_length_mm,
                ))
            for u in self._reserves.get(army.name, []):
                snapshot.append(InitialUnit(
                    uid=u.uid, name=u.profile.name, army=army.name,
                    position=(-100.0, -100.0),
                    max_health=u.profile.health,
                    unit_keywords=tuple(u.profile.unit_keywords or ()),
                    base_shape=u.profile.base_shape,
                    base_diameter_mm=u.profile.base_diameter_mm,
                    base_width_mm=u.profile.base_width_mm,
                    base_length_mm=u.profile.base_length_mm,
                ))
        self._emit(BattleStarted(
            army_a_name=self.a.name,
            army_b_name=self.b.name,
            map_name=self.map.name,
            units=tuple(snapshot),
        ))

        round_history = [(a_start, b_start)]
        rounds_played = 0
        # ENTER-SCORE (wave 111, option ii, env-gated SWEG_ENTERSCORE). 10e
        # scores Primary VP at each player's Command phase: a unit holds an
        # objective from when it takes it until an enemy takes it away, and it
        # scores at its Command phase even if the objective is contested away
        # later that battle round. The alternating-activation round model
        # collapses both players' turns into one interleaved sequence and
        # scores Primary only ONCE, at end of round AFTER all combat — which
        # credits only the post-combat survivor (the durable holder) and erases
        # the transient board control a fragile broad army floods then loses.
        # Wave-110 instrumentation: 52% of the broad army's entering-round
        # marker control was stripped by in-round combat before the end-of-round
        # score. ENTER-SCORE faithfully credits the control state ENTERING the
        # round (before this round's combat) instead. Even-handed: it credits
        # whoever holds entering the round, Knight or horde. Scoring at the
        # START of rounds 2-5 = the post-combat states of rounds 1-4 = the four
        # real per-Command-phase scoring moments (no round-1 score, no
        # post-round-5 score), exactly matching the count the OFF path scores.
        # Gate unset → score at end of round as before; OFF path byte-identical.
        # Cited as `simulator.primary_vp_entering_round`.
        enter_score = __import__("os").environ.get("SWEG_ENTERSCORE") == "1"
        # Per-Command-phase scoring (SWEG_CMDSCORE) replaces the once-per-round
        # Primary scoring with a per-player score at each Command phase, done
        # inside _run_round_vanilla_turns. It only applies to the vanilla IGOUGO
        # path (the eval's default); under alternating activations there are no
        # clean per-player Command phases, so fall back to end-of-round there.
        cmd_score = self._cmd_score and not self.rules.alternating_activations
        for rnd in range(1, MAX_ROUNDS + 1):
            rounds_played = rnd
            self._emit(RoundStarted(round_num=rnd))
            # 10e: Primary VP first scores at end of Command phase 2.
            # Rounds 2-5 score (4 opportunities × 15 VP = 60 VP max before
            # any total cap). Round 1 is purely movement / alpha-strike.
            # Cited as `simulator.primary_vp_no_round_1`.
            if not cmd_score and enter_score and rnd >= 2:
                # Score on control ENTERING the round (= end of the previous
                # round), before this round's combat strips transient holders.
                self._score_objectives()
            self._run_round(rnd)
            if not cmd_score and not enter_score and rnd >= 2:
                # Baseline: score on post-combat (round-end) survivor control.
                self._score_objectives()
            # cmd_score: Primary was already scored per Command phase inside the
            # round (in _run_round_vanilla_turns); nothing to do here.
            self._score_secondaries(rnd)
            self._emit(RoundEnded(
                round_num=rnd,
                a_vp_total=self._a_vp,
                b_vp_total=self._b_vp,
            ))
            round_history.append((self.a.unit_count, self.b.unit_count))
            # End early ONLY on a MUTUAL wipe — both sides have nothing left
            # on-board AND nothing in reserves. A real 10e battle lasts the full
            # five battle rounds (Wahapedia core, "the battle lasts five battle
            # rounds"): a ONE-SIDED tabling does NOT end the game — the surviving
            # army keeps playing out the remaining rounds and scoring primary on
            # the now-uncontested board (and any held secondaries). The combat /
            # AI code already no-ops against an empty opponent (every mover /
            # shooter guards on `alive_units`), and the 50-VP primary cap (M1)
            # bounds the survivor's continued scoring. Truncating one-sided
            # tablings previously under-counted the tabler's VP (Stage-2 pricing
            # fidelity) and could flip an edge case where the tabler was behind on
            # VP at the tabling moment. Cited `simulator.battle_length_five_rounds`.
            a_total_left = self.a.unit_count + len(self._reserves.get(self.a.name, []))
            b_total_left = self.b.unit_count + len(self._reserves.get(self.b.name, []))
            if a_total_left == 0 and b_total_left == 0:
                break

        a_surv = self.a.unit_count
        b_surv = self.b.unit_count
        a_pts = sum(u.profile.points_cost for u in self.a.alive_units)
        b_pts = sum(u.profile.points_cost for u in self.b.alive_units)

        # Board-control Stage 0 (avenue-2) JAM baseline — read-only, gated.
        if __import__("os").environ.get("SWEG_BOARDCTRL_INSTR"):
            self._boardcontrol_jam_snapshot()

        winner = self._decide_winner(a_surv, b_surv, a_pts, b_pts)

        self._emit(BattleEnded(winner=winner, rounds=rounds_played))

        return BattleResult(
            winner=winner,
            rounds=rounds_played,
            a_name=self.a.name,
            b_name=self.b.name,
            a_start=a_start,
            b_start=b_start,
            a_survivors=a_surv,
            b_survivors=b_surv,
            a_vp=self._a_vp,
            b_vp=self._b_vp,
            a_points_remaining=a_pts,
            b_points_remaining=b_pts,
            round_history=round_history,
        )

    # ------------------------------------------------------------------
    # Win condition (objectives + attrition + points)
    # ------------------------------------------------------------------

    def _decide_winner(
        self, a_surv: int, b_surv: int,
        a_pts: float, b_pts: float,
    ) -> Optional[str]:
        """
        10e-flavoured win condition:
          * If one side has zero alive units, the other wins outright.
          * Else: higher VP wins.
          * Tied VP: higher remaining points wins.
          * Tied on both: draw.
        Survivor count is no longer a primary criterion — points + objectives
        capture military value much better than raw unit count.
        """
        if a_surv == 0 and b_surv == 0:
            return None
        if a_surv == 0:
            return self.b.name
        if b_surv == 0:
            return self.a.name
        # Real Pariah Nexus caps total Secondary VP at 40 per game. The running
        # `_a_vp`/`_b_vp` totals mix primary + secondary and never enforced that
        # ceiling, so secondary-heavy shapes (e.g. Custodes ~39/game) could run
        # past it. Decide on primary + min(secondary, 40), using the per-side
        # `_a_secondary_vp` tally. Landed permanently wave 75 (A/B validated:
        # gated 5.35 → 5.11). Cited as `simulator.secondary_vp_cap_40`.
        #
        # M1 (wave 117) — Primary 50-VP TOTAL cap. CA-2025-26 v1.5 caps the
        # Primary Mission at 50 VP per game ("any excess VP awarded above these
        # maximums are lost"). The simulator only enforced the per-round 15 cap
        # (in `_score_objectives`), so a primary-dominator could run to 4×15=60
        # and over-score by up to 10 — exactly the durable Knight's edge. Mirror
        # the 40-secondary cap here. A real rule: kept ON by default; set
        # SWEG_PRIMARY_CAP_50=0 to disable for the isolation A/B. Cited as
        # `simulator.primary_vp_cap_50`.
        _cap_primary = __import__("os").environ.get("SWEG_PRIMARY_CAP_50") != "0"
        a_primary = self._a_vp - self._a_secondary_vp
        b_primary = self._b_vp - self._b_secondary_vp
        if _cap_primary:
            a_primary = min(a_primary, 50)
            b_primary = min(b_primary, 50)
        a_vp = a_primary + min(self._a_secondary_vp, 40)
        b_vp = b_primary + min(self._b_secondary_vp, 40)
        if a_vp > b_vp:
            return self.a.name
        if b_vp > a_vp:
            return self.b.name
        # VP tied — fall back to remaining points
        if a_pts > b_pts * 1.10:
            return self.a.name
        if b_pts > a_pts * 1.10:
            return self.b.name
        return None  # genuinely close — call it a draw

    def _score_objectives(self, only_for: Optional[str] = None) -> None:
        """End-of-round VP scoring: each objective awards its vp_per_round to
        whichever side has more Objective Control within control_radius.

        `only_for` (army name) restricts the AWARD to that one army — used by the
        per-Command-phase primary scoring (wave 116, env-gated SWEG_CMDSCORE) so
        each player scores its own primary at its own Command phase (turn start),
        the real 10e timing, instead of both at end of round. The Objective
        Control contest and sticky-ownership tracking still run in full (board
        state at that Command phase); only which side's running VP is incremented
        is filtered. `only_for=None` (default) scores both — the baseline
        end-of-round behaviour. Cited as `simulator.primary_vp_command_phase`.

        Sticky Objectives (issue #85): a unit with sticky_objective=True that
        currently controls an objective marks self._sticky_owner[obj_idx] =
        its army. If both sides contest the objective on a later round and
        nobody currently controls, the sticky owner still scores. If the
        opposing army takes control, the sticky owner is cleared (and the
        new owner replaces it if THEY are sticky).

        Primary VP cap (10e Leviathan Tournament Companion): an army may
        score a maximum of 15 Primary VP per battle round (i.e. count at
        most 3 controlled objectives at 5 VP each). Enforced after the
        per-objective awards are tallied. Cited as
        `simulator.primary_vp_cap_15`.
        """
        a_vp_before = self._a_vp
        b_vp_before = self._b_vp
        # Virulent Vectorium Worldblight (Death Guard): every DG unit on a
        # controlled objective acts as if it had the sticky_objective flag,
        # per the detachment passive. Resolved once per call. Cited as
        # `VIRULENT_VECTORIUM.worldblight_sticky_dg_objectives`.
        a_det = self.a.resolve_detachment()
        b_det = self.b.resolve_detachment()
        a_worldblight = bool(
            a_det is not None
            and getattr(a_det, "worldblight_sticky_dg_objectives", False)
        )
        b_worldblight = bool(
            b_det is not None
            and getattr(b_det, "worldblight_sticky_dg_objectives", False)
        )

        # Unit Coherency for Objective Control (10e core rules, cited as
        # `simulator.unit_coherency`). A coherent unit sits on roughly one
        # objective marker, so it may contribute its Objective Control to AT
        # MOST ONE objective per round — never contest several at once. We
        # model one Unit-object per model and a codex unit as the Units sharing
        # a squad_id, so for each squad we find the single objective on which
        # the MOST of its models sit (within that objective's control_radius)
        # and credit that squad's summed Objective Control to only that
        # objective. Ties are broken by the smallest centroid distance.
        # Battleshocked models (uid in self._battleshocked_this_round) count 0.
        # Sticky-objective and Death Guard worldblight presence are tracked on
        # the chosen objective only, so the existing sticky / worldblight logic
        # below sees the squad exactly where it scores.
        #
        # Returns three dicts keyed by obj_idx:
        #   oc[obj_idx]            -> summed Objective Control credited there
        #   sticky_present[obj_idx] -> True if any crediting squad is sticky
        #   dg_present[obj_idx]     -> True if any crediting squad is Death Guard
        # Read the collision gate once: under no-overlap collision the Objective
        # Control contest measures to the base edge (faithful 10e range), fixing
        # the entrenchment artifact where a Knight's base evicts contesters.
        oc_collide = __import__("os").environ.get("SWEG_COLLISION", "1") != "0"  # default-ON

        def _assign_army_oc(army):
            oc_by_obj: dict = {}
            sticky_by_obj: dict = {}
            dg_by_obj: dict = {}
            for members in army.squads().values():
                # Per-objective tally for THIS squad: model count + summed OC.
                best_idx = None
                best_count = 0
                best_dist2 = None
                best_oc = 0
                for obj_idx2, obj2 in enumerate(self.map.objectives):
                    r2b = obj2.control_radius * obj2.control_radius
                    count = 0
                    oc_sum = 0
                    sum_dx = 0.0
                    sum_dy = 0.0
                    for u in members:
                        if u.uid in self._battleshocked_this_round:
                            continue   # Battleshocked = OC 0
                        dx = u.position[0] - obj2.x
                        dy = u.position[1] - obj2.y
                        # 10e measures range to the CLOSEST POINT of a model's base
                        # (core "Measuring Distances"), so a model is within range of
                        # an objective marker when its base edge reaches within the
                        # control radius: center-distance - base_radius <= control_r.
                        # The collision-OFF baseline uses the center-only approximation
                        # (dx^2+dy^2<=r2b); under no-overlap collision a big base (a
                        # Knight) pushes enemy CENTERS past 3" of a marker it sits on,
                        # which would unfaithfully EVICT base-to-base contesters whose
                        # base edge is still within 3". So when collision is active,
                        # count the model's base reach. Cited
                        # simulator.objective_control_base_range; gated SWEG_COLLISION
                        # so the OFF path stays byte-identical.
                        if oc_collide:
                            reach = obj2.control_radius + _bc_model_radius_in(u.profile)
                            within = (dx * dx + dy * dy) <= reach * reach
                        else:
                            within = (dx * dx + dy * dy) <= r2b
                        if within:
                            count += 1
                            oc_sum += self._effective_oc(u)
                            sum_dx += dx
                            sum_dy += dy
                    if count == 0:
                        continue
                    # Centroid-of-on-objective-models distance for tie-break.
                    cx = sum_dx / count
                    cy = sum_dy / count
                    dist2 = cx * cx + cy * cy
                    if (
                        best_idx is None
                        or count > best_count
                        or (count == best_count and dist2 < best_dist2)
                    ):
                        best_idx = obj_idx2
                        best_count = count
                        best_dist2 = dist2
                        best_oc = oc_sum
                if best_idx is None or best_oc <= 0:
                    continue
                oc_by_obj[best_idx] = oc_by_obj.get(best_idx, 0) + best_oc
                # A squad is sticky / DG if its profile says so (all members of
                # a squad share a profile, so checking the first crediting
                # member is sufficient; use any() to be safe for mixed lists).
                if any(
                    getattr(u.profile, "sticky_objective", False)
                    for u in members
                ):
                    sticky_by_obj[best_idx] = True
                if any(
                    (u.profile.faction or "") == "Death Guard"
                    for u in members
                ):
                    dg_by_obj[best_idx] = True
            return oc_by_obj, sticky_by_obj, dg_by_obj

        a_oc_by_obj, a_sticky_by_obj, a_dg_by_obj = _assign_army_oc(self.a)
        b_oc_by_obj, b_sticky_by_obj, b_dg_by_obj = _assign_army_oc(self.b)

        # OC-DELIVERY instrument (#84, gated SWEG_DELIVERY_INSTR, read-only): does
        # each army get its Objective Control ONTO markers, or does it sit back?
        # delivered = OC credited to objectives (sum of the coherency-assigned
        # oc_by_obj); total = the army's whole on-board effective OC. A low
        # delivery rate localizes the under-side under-score as (1) positioning
        # (gunlines never reach markers) vs (3) under-credit (they reach but their
        # OC loses). Keyed by faction. No behaviour change.
        if __import__("os").environ.get("SWEG_DELIVERY_INSTR"):
            for _army, _obo in ((self.a, a_oc_by_obj), (self.b, b_oc_by_obj)):
                _fac = (_army.units[0].profile.faction if _army.units else "?") or "?"
                _tot = 0
                for _u in _army.alive_units:
                    if _u.uid not in self._battleshocked_this_round:
                        _tot += self._effective_oc(_u)
                _deliv = sum(_obo.values())
                _d = DELIVERY_STATS.setdefault(_fac, {"rounds": 0, "total": 0.0, "delivered": 0.0})
                _d["rounds"] += 1
                _d["total"] += _tot
                _d["delivered"] += _deliv

        # Wave 187 (#71 primary-mission rotation, env-gated SWEG_PRIMARY_MISSION):
        # accumulate the Take-and-Hold per-objective award + the control counts in
        # the loop below, then apply the CHOSEN primary mission's victory-point
        # formula AFTER the loop. The default "take_and_hold" path is byte-identical
        # (accumulate-then-add == the legacy per-objective add; identical events;
        # identical 15 VP/round cap). The sim previously played Take and Hold — the
        # most holder-friendly primary — every game, structurally inflating durable
        # static holders; the real Chapter Approved 2025-26 deck rotates ten
        # primaries, several of which (Purge the Foe, Scorched Earth) penalise
        # static holding. Cited simulator.primary_mission_rotation.
        mission = getattr(self, "primary_mission", "take_and_hold") or "take_and_hold"
        a_th_award = 0
        b_th_award = 0
        a_controls = 0
        b_controls = 0
        # The Ritual primary scores ONLY No Man's Land markers — track those
        # controlled-marker counts separately (per-side).
        a_controls_nml = 0
        b_controls_nml = 0

        # Board-control instrument (avenue-2 Stage 0) — read-only, gated. Snapshots
        # OC-packing / footprint-overlap / big-model-in-ruin at settled positions.
        if __import__("os").environ.get("SWEG_BOARDCTRL_INSTR"):
            self._boardcontrol_instrument()

        for obj_idx, obj in enumerate(self.map.objectives):
            # Scorched Earth Burn (#87): a RAZED marker is gone from the board —
            # neither side scores it by holding for the rest of the game.
            if obj_idx in self._razed_objectives:
                continue
            # Per-unit Objective Control (cited as `simulator.unit_coherency`):
            # read the per-squad assignments computed above. Each squad has
            # already been credited to at most one objective, so a scattered
            # squad can no longer contest several markers at once.
            a_oc = a_oc_by_obj.get(obj_idx, 0)
            b_oc = b_oc_by_obj.get(obj_idx, 0)
            # OC-FLIP instrument (#79) — read-only, gated. Measures the over-pole
            # over-hold opportunity; no behaviour change.
            if __import__("os").environ.get("SWEG_OCFLIP_INSTR"):
                self._ocflip_instrument(obj, a_oc, b_oc)
            a_sticky_present = a_sticky_by_obj.get(obj_idx, False)
            b_sticky_present = b_sticky_by_obj.get(obj_idx, False)
            a_has_dg_unit = a_dg_by_obj.get(obj_idx, False)
            b_has_dg_unit = b_dg_by_obj.get(obj_idx, False)

            # iter24-D3 — Worldblight strict gate. Per Wahapedia
            # (https://wahapedia.ru/wh40k10ed/factions/death-guard/#STRATAGEMS
            # — Worldblight) the rule fires at end of the DG Command phase
            # AND requires the DG unit to already be controlling the
            # objective (strictly greater OC than the opponent). Promote
            # the DG presence to a sticky flag ONLY when the DG side wins
            # the OC contest at this objective. _score_objectives() runs
            # once per round so the once-per-round trigger is implicit.
            # Without this gate, a DG unit losing the OC contest would
            # still mark sticky_present, which prevented the opponent's
            # sticky from being cleared even though they were winning.
            if a_worldblight and a_has_dg_unit and a_oc > b_oc:
                a_sticky_present = True
            if b_worldblight and b_has_dg_unit and b_oc > a_oc:
                b_sticky_present = True

            # Resolve who actually scores this round. The fallback to
            # sticky_owner is only used when NEITHER side has any OC on the
            # objective — i.e. truly uncontested (not a tie at OC>0).
            scorer: Optional[str] = None
            if a_oc > b_oc:
                scorer = self.a.name
            elif b_oc > a_oc:
                scorer = self.b.name
            elif a_oc == 0 and b_oc == 0:
                # Nobody on it — fall back to sticky owner if any.
                scorer = self._sticky_owner.get(obj_idx)

            # OVER-SCORE instrument (#83, gated SWEG_OVERSCORE_INSTR, read-only):
            # for the side that WINS this marker, was the loser ALSO contesting it
            # (had OC on the marker but lost the count = (iii) CONCENTRATION — the
            # sim's concentrated elite OC wins a contested marker real combat would
            # have whittled) or was it UNCONTESTED ((i) over-hold — opponent never
            # came)? Keyed by the winner's faction so the diag can split the
            # over-shooter cluster. No behaviour change.
            if __import__("os").environ.get("SWEG_OVERSCORE_INSTR") and a_oc != b_oc:
                _win = self.a if a_oc > b_oc else self.b
                _win_oc = a_oc if a_oc > b_oc else b_oc
                _los_oc = b_oc if a_oc > b_oc else a_oc
                _fac = (_win.units[0].profile.faction if _win.units else "?") or "?"
                _d = OVERSCORE_STATS.setdefault(
                    _fac, {"scored": 0, "contested_won": 0, "uncontested": 0,
                           "sum_win_oc": 0.0, "sum_los_oc": 0.0},
                )
                _d["scored"] += 1
                _d["sum_win_oc"] += _win_oc
                _d["sum_los_oc"] += _los_oc
                if _los_oc > 0:
                    _d["contested_won"] += 1   # (iii) opponent on the marker, lost
                else:
                    _d["uncontested"] += 1      # (i) opponent absent — over-hold

            # Update sticky ownership BEFORE emitting the event, so a
            # newly-claimed objective registers the sticky owner this round.
            # Per 10e core rules: "The player with the greater Level of Control
            # over the objective marker controls it." Strictly greater — ties
            # do NOT grant control, so they cannot register sticky ownership.
            # https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Mission-Objectives
            # Cited as `simulator.objective_control_strictly_greater`.
            if a_sticky_present and a_oc > b_oc:
                self._sticky_owner[obj_idx] = self.a.name
            elif b_sticky_present and b_oc > a_oc:
                self._sticky_owner[obj_idx] = self.b.name
            else:
                # An opposing non-sticky unit that takes control wrests the
                # marker back — clear sticky ownership so the new controller
                # scores fairly. (If the same side that owns sticky also
                # controls now with a non-sticky unit, leave the sticky owner
                # in place — they still hold it.)
                cur_owner = self._sticky_owner.get(obj_idx)
                if cur_owner == self.a.name and b_oc > a_oc:
                    self._sticky_owner.pop(obj_idx, None)
                elif cur_owner == self.b.name and a_oc > b_oc:
                    self._sticky_owner.pop(obj_idx, None)

            # only_for filters which side's running VP is incremented (the
            # Command-phase scorer awards just the active player); the OC contest
            # and sticky tracking above already ran for both sides.
            # Count actual control (used by Purge the Foe's control conditions),
            # independent of the only_for command-phase filter.
            if scorer == self.a.name:
                a_controls += 1
                if self._obj_in_nml(obj):
                    a_controls_nml += 1
            elif scorer == self.b.name:
                b_controls += 1
                if self._obj_in_nml(obj):
                    b_controls_nml += 1
            _award = scorer if (only_for is None or scorer == only_for) else None
            if _award == self.a.name:
                a_th_award += obj.vp_per_round
                self._emit(ObjectiveScored(
                    objective_name=obj.name, army_name=self.a.name,
                    vp_awarded=obj.vp_per_round, a_oc=a_oc, b_oc=b_oc,
                ))
            elif _award == self.b.name:
                b_th_award += obj.vp_per_round
                self._emit(ObjectiveScored(
                    objective_name=obj.name, army_name=self.b.name,
                    vp_awarded=obj.vp_per_round, a_oc=a_oc, b_oc=b_oc,
                ))
            else:
                self._emit(ObjectiveScored(
                    objective_name=obj.name, army_name=None,
                    vp_awarded=0, a_oc=a_oc, b_oc=b_oc,
                ))

        # Primary VP per-round cap (10e Leviathan Tournament Companion):
        # an army scores at most 15 Primary VP per battle round, regardless
        # of how many objectives they control. Excess held objectives still
        # emit ObjectiveScored events above (informative), but the running
        # VP totals are clamped here. Faction-neutral; corrects inflation
        # for objective-flooding archetypes (DG sticky, Necrons RP).
        # https://wahapedia.ru/wh40k10ed/the-rules/leviathan-tournament-companion/
        # Cited as `simulator.primary_vp_cap_15`.
        if mission == "purge_the_foe":
            # Purge the Foe (Chapter Approved 2025-26, cap 12 VP/round): score
            # 4 VP for destroying one or more enemy units this round, +4 VP for
            # destroying MORE enemy units than the opponent destroyed of yours,
            # +4 VP for controlling one or more objectives, +4 VP for controlling
            # more objectives than the opponent. Kill-weighted (8 of 12 VP), so a
            # static holder that under-kills caps at 8. Cited
            # simulator.primary_purge_the_foe.
            a_killed, b_killed = self._units_destroyed_this_round()
            a_purge = ((4 if a_killed > 0 else 0) + (4 if a_killed > b_killed else 0)
                       + (4 if a_controls > 0 else 0) + (4 if a_controls > b_controls else 0))
            b_purge = ((4 if b_killed > 0 else 0) + (4 if b_killed > a_killed else 0)
                       + (4 if b_controls > 0 else 0) + (4 if b_controls > a_controls else 0))
            if only_for is None or only_for == self.a.name:
                self._a_vp += min(a_purge, 12)
            if only_for is None or only_for == self.b.name:
                self._b_vp += min(b_purge, 12)
        elif mission == "scorched_earth":
            # Scorched Earth (Chapter Approved 2025-26): 5 VP per controlled
            # objective, capped at 10 VP/round (lower than Take and Hold's 15). The
            # displacement comes from the Burn/Raze Action (remove a marker for 5 VP
            # in No Man's Land / 10 VP in the enemy deployment zone), resolved in
            # `_resolve_burns` below (default-ON for this mission). a_th_award already
            # respects the only_for filter. Cited simulator.primary_scorched_earth /
            # simulator.primary_scorched_earth_burn.
            self._a_vp += min(a_th_award, 10)
            self._b_vp += min(b_th_award, 10)
        elif mission == "terraform":
            # Terraform (Chapter Approved 2025-26): "4VP for each objective marker
            # they control (up to 12VP per turn)" PLUS "1VP for each objective marker
            # that is terraformed by them" (the +1 is ON TOP of the 12 hold cap). The
            # Terraform Action (resolved in `_resolve_terraforms` below) marks a
            # forward marker as terraformed by its army; the displacement angle is the
            # Action's opportunity cost (a unit doing it can't shoot/charge), which a
            # few-model army pays more dearly than a body army. a_controls / b_controls
            # are the per-side controlled-marker counts from the loop above. Cited
            # simulator.primary_terraform.
            a_terra = sum(1 for o in self._terraformed_owner.values() if o == "a")
            b_terra = sum(1 for o in self._terraformed_owner.values() if o == "b")
            if only_for is None or only_for == self.a.name:
                self._a_vp += min(4 * a_controls, 12) + a_terra
            if only_for is None or only_for == self.b.name:
                self._b_vp += min(4 * b_controls, 12) + b_terra
        elif mission == "the_ritual":
            # The Ritual (Chapter Approved 2025-26): "5VP for each objective marker
            # in No Man's Land that they control (up to 15VP per turn)." HOME-zone
            # markers score NOTHING, so a back-camping gunline scores 0 and every
            # army must contest the centre. The Ritual ACTION (set up a NEW marker in
            # No Man's Land 12" from another) is NOT modelled — the sim's objectives
            # are fixed, so dynamic marker creation is out of scope for the bounded
            # avenue-1 close; only the No-Man's-Land-only hold pressure is captured
            # here (noted in the citation, the same partial-then-extend pattern as
            # Scorched's hold-before-Burn). a_controls_nml / b_controls_nml are the
            # per-side No Man's Land controlled-marker counts. Cited
            # simulator.primary_the_ritual.
            if only_for is None or only_for == self.a.name:
                self._a_vp += min(5 * a_controls_nml, 15)
            if only_for is None or only_for == self.b.name:
                self._b_vp += min(5 * b_controls_nml, 15)
        else:
            # take_and_hold (default, byte-identical to the legacy behaviour):
            # award the accumulated per-objective VP, then apply the 15 VP/round
            # cap (10e Leviathan Tournament Companion). a_th_award already respects
            # the only_for filter. Cited simulator.primary_vp_cap_15.
            self._a_vp += a_th_award
            self._b_vp += b_th_award
            a_round_vp = self._a_vp - a_vp_before
            b_round_vp = self._b_vp - b_vp_before
            if a_round_vp > 15:
                self._a_vp = a_vp_before + 15
            if b_round_vp > 15:
                self._b_vp = b_vp_before + 15

        # Scorched Earth Burn (#87): resolve completed Raze Actions AFTER the hold
        # cap, so Raze VP is a distinct scoring event (not clipped by the per-round
        # hold cap). No-op unless the Scorched Earth mission + SWEG_SCORCHED_BURN.
        self._resolve_burns(only_for=only_for)
        # Terraform (#87): resolve completed Terraform Actions (mark markers as
        # terraformed by their army for the +1/turn). No-op unless Terraform mission.
        self._resolve_terraforms(only_for=only_for)

    def _units_destroyed_this_round(self) -> tuple:
        """Wave 187 (Purge the Foe): return (a_killed, b_killed) — how many enemy
        UNITS each side destroyed this battle round, diffed against the round-start
        snapshots (the same snapshots the Pariah Nexus secondaries use). a_killed =
        the count of army B's units that A destroyed this round; b_killed the
        reverse. A codex unit counts as destroyed only when its last model dies
        (squad_id gone), matching the No Prisoners convention. Returns (0, 0) when a
        snapshot is missing (e.g. round 1)."""
        def _destroyed(snap, current_units) -> int:
            if snap is None:
                return 0
            alive_sq: set = set()
            alive_lone: set = set()
            for u in current_units:
                if u.current_health <= 0:
                    continue
                sid = getattr(u, "squad_id", -1)
                if sid is not None and sid >= 0:
                    alive_sq.add(sid)
                else:
                    alive_lone.add(id(u))
            dead_sq = snap.alive_squad_ids - alive_sq
            dead_lone = snap.lone_unit_ids_alive - alive_lone
            return len(dead_sq) + len(dead_lone)
        a_killed = _destroyed(self._b_round_snapshot, self.b.units)
        b_killed = _destroyed(self._a_round_snapshot, self.a.units)
        return a_killed, b_killed

    # ------------------------------------------------------------------
    # SC4-A — 10e Pariah Nexus secondary objective scoring
    # ------------------------------------------------------------------

    def _cleanse_enabled(self) -> bool:
        """Pariah Nexus Cleanse action secondary (wave 74). Landed ON after the
        env-gated N=40 A/B validated it: gated MAE 5.89 → 5.35, with the durable
        over-shooters easing down (Imperial Knights +27.9 → +23.3, World Eaters
        +16.5 → +12.5) and the board-control under-shooters rising (Astra
        −15.5 → −10.6) — the faithful, even-handed mechanism doing exactly what
        the kill-secondary-asymmetry analysis predicted. Kept as a method (rather
        than inlined True) so a future A/B can re-gate it via a one-line edit."""
        return True

    def _obj_outside_own_dz(self, obj, own_is_army_a: bool) -> bool:
        """Cleanse only scores on objectives NOT in the scoring side's own
        deployment zone (real Pariah Nexus rule). Army A deploys low-y, B high-y."""
        dz = self.map.deployment_width
        if own_is_army_a:
            return obj.y > dz
        return obj.y < (self.map.height - dz)

    def _effective_oc(self, u) -> int:
        """Objective Control of a single model, applying the 10e Knights'
        Damaged-bracket Objective-Control reduction (re-added wave 85).

        Verified by cleanly extracting the canonical BSData damage-table rows
        (the proper read this time): an Armiger / War Dog carries "While this
        model has 1-5 wounds remaining, subtract 3 from this model's Objective
        Control characteristic ..."; a Questoris Knight "While this model has
        1-9 wounds remaining, subtract 5 ..." (the larger Dominus chassis use
        1-10, −5). ONLY the Knight factions have this datasheet rule, so the
        faction gate is the faithful per-datasheet implementation, not a
        per-faction fudge. Floored at 0. Env-gated SWEG_DMGOC (default ON; set
        =0 to re-gate for an isolation A/B). Cited as
        `simulator.damaged_objective_control_bracket`.

        NOTE: the goal-doc directive expected the current-codex Questoris value
        to be −4; the canonical BSData cache (codex-tagged Knight T11/W26)
        cleanly reads −5. RESOLVED (watchdog Q9): use the cache −5 — BSData
        rule-6 governs; the −4 came from an unreliable web summary."""
        base = getattr(u.profile, "oc", 1) or 1
        # 10e Damaged-bracket Objective-Control reduction — data-driven from the
        # real per-datasheet "Damaged: 1-X Wounds Remaining" bracket
        # (UnitProfile.damaged_oc_penalty, BSData-extracted via the link-resolving
        # mapper) and applied to EVERY model with a bracket (#77, wave 191).
        # Default-ON; SWEG_DMGBRACKET=0 disables for an isolation A/B. This RETIRED
        # the Knight-only SWEG_DMGOC heuristic (wave 85), which degraded only the 6
        # Knight datasheets — a partial-faithful bias. The N=80 generalization A/B
        # was metric-neutral (gated 5.76 -> 5.71) and strictly more faithful: 260
        # catalogue units (incl. T'au Stormsurge/Riptide, Custodes / World Eaters
        # dreadnoughts, AdMech / Necron vehicles) now lose Objective Control while
        # damaged, per their own datasheet. The data-driven Knight values reproduce
        # the retired heuristic exactly (Questoris 1-9/−5, Armiger 1-5/−3, Dominus
        # 1-10/−5). Cited `simulator.damaged_bracket`.
        if __import__("os").environ.get("SWEG_DMGBRACKET", "1") == "0":
            return base
        thr = getattr(u.profile, "damaged_threshold", 0) or 0
        pen = getattr(u.profile, "damaged_oc_penalty", 0) or 0
        if thr and pen and u.current_health <= thr:
            return max(0, base - pen)            # floor at 0 — never negative
        return base

    def _ocflip_instrument(self, obj, a_oc, b_oc) -> None:
        """OC-FLIP over-hold instrument (#79, gated SWEG_OCFLIP_INSTR). For one
        objective this round, record whether a damaged big durable holder controls
        it while the opponent has enough reachable nearby Objective Control to flip
        it. Read-only — accumulates into the module-level OCFLIP_STATS. `a_oc`/`b_oc`
        are the coherency-assigned summed OC already computed by _score_objectives."""
        if a_oc == b_oc:
            return
        if a_oc > b_oc:
            holder, opp, holder_oc = self.a, self.b, a_oc
        else:
            holder, opp, holder_oc = self.b, self.a, b_oc
        r2 = obj.control_radius * obj.control_radius
        # "nearby committable" = within the control radius plus roughly one Normal
        # Move (a body one move away can step onto the marker next turn).
        commit_r2 = (obj.control_radius + 7.0) ** 2
        # Is the holder's on-marker OC propped by a big durable model
        # (Knight/Titanic, or big VEHICLE/MONSTER >= 18 wounds)? Track BOTH the
        # broad case (any health) and the damaged sub-case (effective OC reduced
        # below base because it is in its Damaged bracket) — so we can tell whether
        # the over-hold is a GENERAL AI-not-contesting gap or specific to the
        # damaged-OC window the OC-flip lever targets.
        big_any = False
        big_dmg = False
        for u in holder.alive_units:
            if u.uid in self._battleshocked_this_round:
                continue
            dx = u.position[0] - obj.x
            dy = u.position[1] - obj.y
            if dx * dx + dy * dy <= r2:
                base = getattr(u.profile, "oc", 0) or 0
                kw = set(u.profile.unit_keywords or ())
                big = "TITANIC" in kw or (
                    ("VEHICLE" in kw or "MONSTER" in kw)
                    and (u.profile.health or 0) >= 18
                )
                if big:
                    big_any = True
                    if self._effective_oc(u) < base:
                        big_dmg = True
        if not big_any:
            return
        opp_reach = 0
        for u in opp.alive_units:
            if u.uid in self._battleshocked_this_round:
                continue
            dx = u.position[0] - obj.x
            dy = u.position[1] - obj.y
            if dx * dx + dy * dy <= commit_r2:
                opp_reach += self._effective_oc(u)
        flippable = opp_reach > holder_oc
        OCFLIP_STATS["held_any"] += 1
        # BURN-reachability (#87): could an opponent unit reach this held marker and
        # perform the Burn Action? Needs only to get within ~one move and NOT be
        # engaged (no OC contest required — burning removes the marker outright).
        _burn_r2 = (obj.control_radius + 8.0) ** 2
        for u in opp.alive_units:
            if u.uid in self._battleshocked_this_round:
                continue
            dx = u.position[0] - obj.x
            dy = u.position[1] - obj.y
            if dx * dx + dy * dy > _burn_r2:
                continue
            engaged = any(
                (u.position[0] - h.position[0]) ** 2 + (u.position[1] - h.position[1]) ** 2 <= 1.0
                for h in holder.alive_units
            )
            if not engaged:
                OCFLIP_STATS["burn_reachable"] += 1
                break
        if flippable:
            OCFLIP_STATS["flippable_any"] += 1
            # Decompose the reachable opponent OC by WHY it isn't contesting:
            # melee bodies (range < 12 — would abandon a fight), shooty that could
            # still SHOOT from the marker (a holder unit within its range of the
            # marker → a FREE contest the lever should add), and shooty that would
            # lose its shots from there (correctly not pulled — a gunline-pull).
            holder_pos = [(h.position[0], h.position[1]) for h in holder.alive_units
                          if h.uid not in self._battleshocked_this_round]
            for u in opp.alive_units:
                if u.uid in self._battleshocked_this_round:
                    continue
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                if dx * dx + dy * dy > commit_r2:
                    continue
                eoc = self._effective_oc(u)
                rng = getattr(u.profile, "range_inches", 0) or 0
                if rng < 12:
                    OCFLIP_STATS["fc_melee_oc"] += eoc
                else:
                    rr = rng * rng
                    can_shoot = any(
                        (hp[0] - obj.x) ** 2 + (hp[1] - obj.y) ** 2 <= rr
                        for hp in holder_pos
                    )
                    if can_shoot:
                        OCFLIP_STATS["fc_free_oc"] += eoc
                    else:
                        OCFLIP_STATS["fc_noshoot_oc"] += eoc
        if big_dmg:
            OCFLIP_STATS["held"] += 1
            if flippable:
                OCFLIP_STATS["flippable"] += 1
                OCFLIP_STATS["surplus"] += (opp_reach - holder_oc)

    def _boardcontrol_instrument(self) -> None:
        """Avenue-2 Stage 0 read-only board-control instrument (gated by
        SWEG_BOARDCTRL_INSTR; called once per _score_objectives at settled
        positions). Accumulates into the module-level BOARDCONTROL_STATS:
          * OC PACKING — per marker, summed base-footprint area of the OC-counted
            models within control_radius vs the marker-circle area. >100% packing =
            OC that no-overlap collision will physically cap (sizes Stage 1).
          * OVERLAP PAIRS — model pairs near a marker whose footprints actually
            intersect today (collision-free stacking).
          * CONTESTED concentration — packing on markers BOTH sides have OC on.
          * BIG-MODEL-IN-RUIN — settled-position proxy for the ruin-wall lever
            (Stages 3-4): VEHICLE/MONSTER/TITANIC non-FLY models sitting inside a
            RUIN footprint they should route around.
        No behaviour change."""
        import math
        s = BOARDCONTROL_STATS
        for obj in self.map.objectives:
            r2 = obj.control_radius * obj.control_radius
            a_near = [u for u in self.a.alive_units
                      if (u.position[0] - obj.x) ** 2 + (u.position[1] - obj.y) ** 2 <= r2]
            b_near = [u for u in self.b.alive_units
                      if (u.position[0] - obj.x) ** 2 + (u.position[1] - obj.y) ** 2 <= r2]
            near = a_near + b_near
            if not near:
                continue
            s["obj_rounds"] += 1
            circle_area = math.pi * obj.control_radius * obj.control_radius
            area = sum(math.pi * _bc_model_radius_in(u.profile) ** 2 for u in near)
            packing = area / circle_area if circle_area else 0.0
            s["packing_sum"] += packing
            s["packing_n"] += 1
            if packing > 1.0:
                s["packing_over100"] += 1
            for i in range(len(near)):
                ri = _bc_model_radius_in(near[i].profile)
                pi = near[i].position
                for j in range(i + 1, len(near)):
                    rj = _bc_model_radius_in(near[j].profile)
                    pj = near[j].position
                    if (pi[0] - pj[0]) ** 2 + (pi[1] - pj[1]) ** 2 < (ri + rj) ** 2:
                        s["overlap_pairs"] += 1
            if a_near and b_near:
                s["contested_rounds"] += 1
                s["contested_packing_sum"] += packing
        # Big-model-in-ruin settled-position proxy.
        ruins = [t for t in self.map.terrain if t.type is TerrainType.RUIN]
        if ruins:
            for army in (self.a, self.b):
                for u in army.alive_units:
                    kw = u.profile.unit_keywords or ()
                    if "FLY" in kw:
                        continue
                    if not ("VEHICLE" in kw or "MONSTER" in kw or "TITANIC" in kw):
                        continue
                    s["big_snaps"] += 1
                    for t in ruins:
                        if t.contains(u.position):
                            s["big_in_ruin"] += 1
                            break

    def _boardcontrol_jam_snapshot(self) -> None:
        """Avenue-2 Stage 0 read-only JAM baseline (gated; called once at game end).
        Per faction: how many models end the game still stranded in their OWN
        deployment zone, and the mean squad->nearest-objective distance — the
        anti-regression yardstick Stages 1-4 (collision/make-way/walls) must not
        worsen. No behaviour change."""
        dz = self.map.deployment_width
        objs = self.map.objectives
        for army, is_a in ((self.a, True), (self.b, False)):
            fac = (army.units[0].profile.faction if army.units else "?") or "?"
            jam = BOARDCONTROL_STATS["jam"].setdefault(
                fac, {"games": 0, "dz_models_sum": 0, "min_dist_sum": 0.0, "squads": 0})
            jam["games"] += 1
            squads: dict = {}
            for u in army.alive_units:
                y = u.position[1]
                if (is_a and y <= dz) or ((not is_a) and y >= self.map.height - dz):
                    jam["dz_models_sum"] += 1
                squads.setdefault(getattr(u, "squad_id", -1), []).append(u)
            if objs:
                for members in squads.values():
                    best = min(
                        min(((m.position[0] - o.x) ** 2 + (m.position[1] - o.y) ** 2) ** 0.5
                            for o in objs)
                        for m in members)
                    jam["min_dist_sum"] += best
                    jam["squads"] += 1

    def _collision_kwargs(self, mover, allow_engagement: bool = False) -> dict:
        """Avenue-2 Stage 1 (gated SWEG_COLLISION, default-OFF): build the
        `_move_toward` no-overlap collision kwargs for `mover`. Returns {} when the
        gate is OFF (every caller then passes occupants=None -> byte-identical) or
        the mover's army can't be resolved (fail-safe: no collision). Occupants are
        every OTHER alive model — friendly (end-overlap only) and enemy (end-overlap
        + 1" Engagement Range). Assembled fresh from CURRENT positions so a model
        that already moved this phase is avoided at its new spot.

        `allow_engagement=True` for COMBAT moves (charge pile-in / consolidate /
        Blood Surge) — those legitimately END within Engagement Range, so the ER
        test is suppressed (mark all occupants non-enemy); the NO-OVERLAP rule still
        applies (a charger stops base-to-base, it does not end ON a model). Normal
        moves keep ER (allow_engagement=False) — only a Charge may end within 1".
        Note C perf: only the gated path pays this O(models) cost; benchmark +
        spatial-bucket if the Stage-1 A/B wall-clock exceeds 1.5x. No RNG."""
        # Collision is DEFAULT-ON (user ruling 2026-06-07: no-overlap collision is the
        # production baseline); set SWEG_COLLISION=0 to A/B the legacy no-collision path.
        if __import__("os").environ.get("SWEG_COLLISION", "1") == "0":
            return {}
        friendly = getattr(mover, "army_ref", None)
        if friendly is self.a:
            enemy = self.b
        elif friendly is self.b:
            enemy = self.a
        else:
            return {}
        occ = []
        for u in friendly.alive_units:
            if u is mover:
                continue
            occ.append((u.position[0], u.position[1], _bc_model_radius_in(u.profile), False))
        enemy_flag = False if allow_engagement else True
        for u in enemy.alive_units:
            occ.append((u.position[0], u.position[1], _bc_model_radius_in(u.profile), enemy_flag))
        # Avenue-2 Stage 2: wrap the per-mover occupant list in a spatial grid so the
        # sidestep's repeated `_collision_pos_legal` queries touch only nearby occupants
        # (O(local) not O(models)). Byte-identical legality result — gated SWEG_OCCGRID
        # for measurement; contains the dense-horde O(models^2) collision cost (4.06x).
        occupants = _OccupantGrid(occ) if __import__("os").environ.get("SWEG_OCCGRID", "1") != "0" else occ
        return {
            "mover_radius": _bc_model_radius_in(mover.profile),
            "occupants": occupants,
            "mover_fly": "FLY" in (mover.profile.unit_keywords or ()),
        }

    def _oc_within(self, army, obj) -> int:
        """Summed Objective Control of `army`'s alive units within an objective's
        control radius (battleshocked models count 0, matching _score_objectives)."""
        r2 = obj.control_radius * obj.control_radius
        total = 0
        for u in army.alive_units:
            if u.uid in self._battleshocked_this_round:
                continue
            dx = u.position[0] - obj.x
            dy = u.position[1] - obj.y
            if dx * dx + dy * dy <= r2:
                total += self._effective_oc(u)
        return total

    def _assign_cleanse_actions(self, active, other) -> None:
        """Pariah Nexus Cleanse (wave 74; Action-cost contract rebuilt wave 135).
        After the Movement phase, flag up to two SURPLUS units that sit on an
        objective their army CONTROLS and that is OUTSIDE their own deployment
        zone, to perform the Cleanse action. The flag locks the unit out of
        shooting and charging (handled in _do_shoot / _do_charge), which is the
        real action-vs-fight tradeoff: a low-unit durable army has no spare body
        and never reaches this branch; a horde / MSU army does. Even-handed — the
        asymmetry falls out of unit count, not faction.

        Selection gate:
          * SWEG_SECONDARY ON  → the rules-authentic Action contract
            (`_unit_can_perform_action`): OC>0, not in Engagement Range, and not
            a productive shooter with a target in range. EMERGENT from unit count,
            NO model-count / chaff-cost branch.
          * SWEG_SECONDARY OFF → the legacy `strategy._is_chaff_unit` gate,
            byte-for-byte (so the OFF path is unchanged).
        Cited as `simulator.secondary_cleanse` (selection) and
        `simulator.secondary_action_cost` (the ON-path Action contract)."""
        if not self._cleanse_enabled():
            return
        if "cleanse" not in (getattr(active, "chosen_secondaries", ()) or ()):
            return
        from .strategy import _is_chaff_unit
        use_action_cost = self._secondary_dedication_enabled()
        own_is_a = active is self.a
        CLEANSE_CAP = 2   # 2 VP for one objective, 4 for two (real-rule cap)
        cleansed = 0
        for obj in self.map.objectives:
            if cleansed >= CLEANSE_CAP:
                break
            if not self._obj_outside_own_dz(obj, own_is_a):
                continue
            if self._oc_within(active, obj) <= self._oc_within(other, obj):
                continue   # must control the objective
            r2 = obj.control_radius * obj.control_radius
            for u in active.alive_units:
                if u.action_this_round is not None:
                    continue
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                if dx * dx + dy * dy > r2:
                    continue
                eligible = (self._unit_can_perform_action(u, other)
                            if use_action_cost else _is_chaff_unit(u))
                if eligible:
                    u.action_this_round = "cleanse"
                    cleansed += 1
                    break

    def _score_cleanse(self, army, opponent, own_is_army_a: bool,
                       chosen_override=None) -> int:
        """End-of-turn Cleanse scoring (wave 74; completion contract rebuilt
        wave 135): 2 VP per objective that is outside the army's own deployment
        zone, still controlled by the army, and carries a Cleanse-action unit
        that COMPLETED the Action — capped at two objectives (4 VP), per the real
        Pariah Nexus rule. Each unit cleanses one marker.

        Completion (the score gate on the Action being finished):
          * SWEG_SECONDARY ON  → the cleanser must SURVIVE and not have been
            dragged into Engagement Range (`_action_completes`); a unit that died
            or was pulled into melee during the turn scores nothing.
          * SWEG_SECONDARY OFF → the legacy "still alive on the marker" check,
            byte-for-byte.
        Cited as `simulator.secondary_cleanse` /
        `simulator.secondary_action_cost`.

        M2: `chosen_override` (default None → read `army.chosen_secondaries`, the
        byte-identical legacy behaviour) lets the per-card dispatcher isolate this
        one card with a singleton tuple."""
        if not self._cleanse_enabled():
            return 0
        chosen = (chosen_override if chosen_override is not None
                  else (getattr(army, "chosen_secondaries", ()) or ()))
        if "cleanse" not in chosen:
            return 0
        require_completion = self._secondary_dedication_enabled()
        cleansed = 0
        for obj in self.map.objectives:
            if not self._obj_outside_own_dz(obj, own_is_army_a):
                continue
            r2 = obj.control_radius * obj.control_radius
            has_cleanser = any(
                u.action_this_round == "cleanse"
                and (u.position[0] - obj.x) ** 2 + (u.position[1] - obj.y) ** 2 <= r2
                and (not require_completion or self._action_completes(u, opponent))
                for u in army.alive_units
            )
            if not has_cleanser:
                continue
            if self._oc_within(army, obj) > self._oc_within(opponent, obj):
                cleansed += 1
        return min(cleansed, 2) * 2

    def _sabotage_enabled(self) -> bool:
        """Wave-75 Sabotage action secondary. Landed ON after the env-gated A/B
        validated the package (gated 5.35 → 5.11). Kept as a method so a future
        A/B can re-gate it via a one-line edit. NOTE follow-up: cleanse/sabotage
        are not yet rotation-gated like Engage/BEL, so they score every round
        rather than the real draw-1-2/turn cadence — this over-scores them and
        amplifies the (faithful-direction) over-correction of low-model armies
        (CSM/Chaos Knights/Grey Knights). Wave 77 isolation A/B showed Sabotage is
        net-POSITIVE (off = gated 5.15 vs on = 4.91), so it stays; rotation-gating
        would reduce a net-positive effect for an ambiguous fidelity gain."""
        return self._cleanse_enabled()

    def _unit_in_enemy_dz(self, u, own_is_army_a: bool) -> bool:
        dz = self.map.deployment_width
        if own_is_army_a:
            return u.position[1] >= self.map.height - dz
        return u.position[1] <= dz

    def _assign_sabotage_actions(self, active, other) -> None:
        """Pariah Nexus Sabotage (wave 75; Action-cost contract rebuilt wave 135).
        After Movement, flag up to two surplus units that are OUTSIDE their own
        deployment zone (in No Man's Land or the enemy deployment zone) to perform
        the Sabotage action — locked out of shooting/charging like Cleanse. It
        rewards pushing expendable bodies FORWARD (3 VP in No Man's Land, 6 VP in
        the enemy DZ), which a deepstrike / infiltrate under-shooter does and a
        durable camper does not. Runs AFTER cleanse assignment, so a unit already
        cleansing a held objective is not also tagged.

        Selection gate (same split as Cleanse):
          * SWEG_SECONDARY ON  → the rules-authentic Action contract
            (`_unit_can_perform_action`): OC>0, not in Engagement Range, not a
            productive shooter with a target in range. EMERGENT from unit count.
          * SWEG_SECONDARY OFF → the legacy `strategy._is_chaff_unit` gate,
            byte-for-byte.
        Cited as `simulator.secondary_sabotage` /
        `simulator.secondary_action_cost`."""
        if not self._sabotage_enabled():
            return
        if "sabotage" not in (getattr(active, "chosen_secondaries", ()) or ()):
            return
        from .strategy import _is_chaff_unit
        use_action_cost = self._secondary_dedication_enabled()
        own_is_a = active is self.a
        dz = self.map.deployment_width
        h = self.map.height
        SABOTAGE_CAP = 2
        n = 0
        for u in active.alive_units:
            if n >= SABOTAGE_CAP:
                break
            if u.action_this_round is not None:
                continue
            eligible = (self._unit_can_perform_action(u, other)
                        if use_action_cost else _is_chaff_unit(u))
            if not eligible:
                continue
            y = u.position[1]
            if own_is_a and y <= dz:
                continue   # still in own (low-y) DZ
            if (not own_is_a) and y >= h - dz:
                continue   # still in own (high-y) DZ
            u.action_this_round = "sabotage"
            n += 1

    def _score_sabotage(self, army, own_is_army_a: bool,
                        chosen_override=None, opponent=None) -> int:
        """End-of-round Sabotage scoring (wave 75; completion contract rebuilt
        wave 135): the best COMPLETED Sabotage action scores 6 VP in the enemy
        deployment zone or 3 VP in No Man's Land, capped at one completion (6 VP)
        per round. The survival gate (the unit must still be alive forward at end
        of round, after the opponent's turn) is what makes deep Sabotage
        genuinely risky and bounds it.

        Completion (the score gate on the Action being finished):
          * SWEG_SECONDARY ON  → the unit must SURVIVE and not have been dragged
            into Engagement Range (`_action_completes`, using `opponent`); a unit
            that died or was pulled into melee scores nothing.
          * SWEG_SECONDARY OFF → the legacy "still alive forward" check,
            byte-for-byte (opponent unused).
        Cited as `simulator.secondary_sabotage` /
        `simulator.secondary_action_cost`.

        M2: `chosen_override` (default None → read `army.chosen_secondaries`, the
        byte-identical legacy behaviour) lets the per-card dispatcher isolate this
        one card with a singleton tuple."""
        if not self._sabotage_enabled():
            return 0
        chosen = (chosen_override if chosen_override is not None
                  else (getattr(army, "chosen_secondaries", ()) or ()))
        if "sabotage" not in chosen:
            return 0
        require_completion = self._secondary_dedication_enabled()
        # On the completion path we need the enemy army to test Engagement Range;
        # callers pass it explicitly, else fall back to the other army on self.
        foe = opponent if opponent is not None else (self.b if army is self.a else self.a)
        best = 0
        for u in army.alive_units:
            if u.action_this_round != "sabotage":
                continue
            if require_completion and not self._action_completes(u, foe):
                continue
            best = max(best, 6 if self._unit_in_enemy_dz(u, own_is_army_a) else 3)
        return best

    def _scorched_burn_enabled(self) -> bool:
        """Scorched Earth Burn/Raze Action — active whenever the Scorched Earth
        primary mission is in play. The Burn IS the Scorched Earth mission (a real
        CA-2025-26 Action), so it is DEFAULT-ON for that mission (watchdog-affirmed
        wave 201: faithful, net-neutral at the deck's 1/10 share → keep-if-faithful).
        SWEG_SCORCHED_BURN=0 disables it for A/B isolation. Inert in the default
        eval, which never draws a Scorched game unless SWEG_PRIMARY_DECK /
        SWEG_PRIMARY_MISSION is set."""
        if getattr(self, "primary_mission", "take_and_hold") != "scorched_earth":
            return False
        return __import__("os").environ.get("SWEG_SCORCHED_BURN", "1") not in ("0", "false", "")

    def _obj_burnable_for(self, obj, own_is_army_a: bool) -> int:
        """VP for the active army razing `obj`: 10 in the ENEMY deployment zone,
        5 in No Man's Land, 0 in the active army's OWN DZ (you cannot raze your own
        backfield). Real CA-2025-26 Scorched Earth Raze values."""
        if self._obj_in_nml(obj):
            return 5
        if self._obj_in_own_dz(obj, own_is_army_a=(not own_is_army_a)):
            return 10
        return 0

    def _assign_burn_actions(self, active, other) -> None:
        """Scorched Earth Burn/Raze (#87, gated). After Movement, flag up to two
        SURPLUS units that are within control range of a BURNABLE objective (No
        Man's Land or the enemy deployment zone, not already razed) to perform the
        Raze Action — locked out of shooting/charging this turn via
        `action_this_round` (the real Action trade-off). On completion (the unit
        survives forward, not dragged into Engagement Range) the marker is REMOVED
        and the army scores 5 VP (No Man's Land) / 10 VP (enemy DZ). Uses the same
        rules-authentic `_unit_can_perform_action` contract as Sabotage (OC>0, not
        engaged, NOT a productive shooter — so a unit that could usefully shoot
        won't burn; the faithful burn-vs-shoot trade-off, even-handed/emergent),
        but it must be NEAR a burnable marker and it removes that marker. This is
        the displacement-via-scoring lever: a mobile army razes the static over-
        holder's NML marker (denying the hold + scoring VP), no kill needed. Cited
        simulator.primary_scorched_earth_burn."""
        if not self._scorched_burn_enabled():
            return
        # Real rule START: "from the second battle round onwards" — no turn-1 raze.
        if self._current_round < 2:
            return
        own_is_a = active is self.a
        # Real rule: "ONE unit from your army" may Burn per turn (verbatim
        # CA-2025-26). CAP=1 is the faithful raze rate (the earlier CAP=2 doubled it
        # and fed the residual horde over-flood).
        BURN_CAP = 1
        n = 0
        for u in active.alive_units:
            if n >= BURN_CAP:
                break
            if not self._unit_can_perform_action(u, other):
                continue
            best_idx = None
            best_d2 = None
            for obj_idx, obj in enumerate(self.map.objectives):
                if obj_idx in self._razed_objectives:
                    continue
                if self._obj_burnable_for(obj, own_is_a) <= 0:
                    continue
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                d2 = dx * dx + dy * dy
                if d2 > obj.control_radius * obj.control_radius:
                    continue
                # Real CA-2025-26 rule: the active army must CONTROL the marker to
                # Burn it (not merely reach it) — so to raze the over-holder's
                # marker the opponent must first WIN the OC contest there (the
                # Knight's high OC protects its markers unless it is damaged /
                # out-massed, dovetailing with the contest lever). Without this gate
                # the burn over-fires (over-pole crashed unfaithfully + horde spam).
                if self._oc_within(active, obj) <= self._oc_within(other, obj):
                    continue
                if best_d2 is None or d2 < best_d2:
                    best_d2 = d2
                    best_idx = obj_idx
            if best_idx is None:
                continue
            u.action_this_round = "burn"
            self._burn_targets[u.uid] = best_idx
            n += 1

    def _resolve_burns(self, only_for=None) -> None:
        """Resolve completed Scorched Earth Raze Actions: a unit performing the
        Burn that COMPLETES (survives forward, not in Engagement Range — the same
        `_action_completes` gate as Sabotage) RAZES its target marker (permanently
        removed from the board) and scores 5 VP (No Man's Land) / 10 VP (enemy DZ).
        Each marker is razed at most once. Run at the END of _score_objectives so
        the Raze VP sits on top of the hold cap (a distinct scoring event), and the
        per-objective hold loop already excludes razed markers. Cited
        simulator.primary_scorched_earth_burn."""
        if not self._scorched_burn_enabled():
            return
        for army, foe, is_a in ((self.a, self.b, True), (self.b, self.a, False)):
            if only_for is not None and only_for != army.name:
                continue
            for u in army.alive_units:
                if u.action_this_round != "burn":
                    continue
                idx = self._burn_targets.get(u.uid)
                if idx is None or idx in self._razed_objectives:
                    continue
                if not self._action_completes(u, foe):
                    continue
                obj = self.map.objectives[idx]
                # Real rule completion gate: still CONTROL the marker at the end
                # (else the opponent re-took it and the Burn fails).
                if self._oc_within(army, obj) <= self._oc_within(foe, obj):
                    continue
                vp = self._obj_burnable_for(obj, is_a)
                if vp <= 0:
                    continue
                self._razed_objectives.add(idx)
                if is_a:
                    self._a_vp += vp
                else:
                    self._b_vp += vp

    def _terraform_enabled(self) -> bool:
        """Terraform primary — active whenever the Terraform mission is in play.
        The Terraform Action IS the mission, so it is DEFAULT-ON for that mission
        (the Scorched-Burn pattern). SWEG_TERRAFORM=0 disables the Action for A/B
        isolation (leaving the cap-12 hold scoring alone). Inert in the default
        eval, which never draws a Terraform game unless SWEG_PRIMARY_DECK /
        SWEG_PRIMARY_MISSION is set. Avenue-1 fair-measurement build (wave 202)."""
        if getattr(self, "primary_mission", "take_and_hold") != "terraform":
            return False
        return __import__("os").environ.get("SWEG_TERRAFORM", "1") not in ("0", "false", "")

    def _assign_terraform_actions(self, active, other) -> None:
        """Terraform primary (#87 avenue-1, gated). After Movement, flag SURPLUS
        units each within range of a DIFFERENT forward objective marker (No Man's
        Land or the enemy deployment zone — "not within your deployment zone") to
        perform the Terraform Action, locked out of shooting/charging this turn via
        the same rules-authentic `_unit_can_perform_action` contract as Burn (OC>0,
        not engaged, NOT a productive shooter). Real CA-2025-26: "One or more units
        from your army, each within range of a different objective marker that is
        not within your deployment zone" — so NO cap-of-one (unlike Burn), but each
        unit must target a DISTINCT marker. STARTING needs only range (no control);
        COMPLETION (in `_resolve_terraforms`) needs control. Cited
        simulator.primary_terraform."""
        if not self._terraform_enabled():
            return
        # "from the second battle round onwards" — terraform VP scores from round 2.
        if self._current_round < 2:
            return
        own_is_a = active is self.a
        claimed: set = set()  # markers already assigned to one of our units this turn
        for u in active.alive_units:
            if not self._unit_can_perform_action(u, other):
                continue
            best_idx = None
            best_d2 = None
            for obj_idx, obj in enumerate(self.map.objectives):
                if obj_idx in claimed:
                    continue
                # Already terraformed BY US and not contested away — no value re-doing.
                if self._terraformed_owner.get(obj_idx) == ("a" if own_is_a else "b"):
                    continue
                # "not within your deployment zone" — only forward markers (No Man's
                # Land or the enemy DZ) are terraformable.
                if self._obj_in_own_dz(obj, own_is_army_a=own_is_a):
                    continue
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                d2 = dx * dx + dy * dy
                if d2 > obj.control_radius * obj.control_radius:
                    continue
                if best_d2 is None or d2 < best_d2:
                    best_d2 = d2
                    best_idx = obj_idx
            if best_idx is None:
                continue
            u.action_this_round = "terraform"
            self._terraform_targets[u.uid] = best_idx
            claimed.add(best_idx)

    def _resolve_terraforms(self, only_for=None) -> None:
        """Resolve completed Terraform Actions. A unit performing Terraform that
        COMPLETES — "still within range of the same objective marker and you control
        that objective marker" (the `_action_completes` survival gate + the control
        re-check, mirroring Burn) — marks that marker as TERRAFORMED by its army.
        Per the real rule the fresh terraform OVERWRITES any opponent terraform on
        that marker. No immediate VP: the +1 VP per terraformed marker is scored each
        turn in the Terraform mission branch of `_score_objectives`. Cited
        simulator.primary_terraform."""
        if not self._terraform_enabled():
            return
        for army, foe, is_a in ((self.a, self.b, True), (self.b, self.a, False)):
            if only_for is not None and only_for != army.name:
                continue
            owner = "a" if is_a else "b"
            for u in army.alive_units:
                if u.action_this_round != "terraform":
                    continue
                idx = self._terraform_targets.get(u.uid)
                if idx is None:
                    continue
                if not self._action_completes(u, foe):
                    continue
                obj = self.map.objectives[idx]
                # Completion control gate: "you control that objective marker".
                if self._oc_within(army, obj) <= self._oc_within(foe, obj):
                    continue
                # Fresh terraform overwrites the opponent's (a marker is terraformed
                # by at most one side at a time).
                self._terraformed_owner[idx] = owner

    # ------------------------------------------------------------------
    # Wave 121 — AI-pursuit layer for held Tactical secondary cards
    # (env-gated SWEG_TAC_PURSUE; sub-gate of SWEG_TAC_DECK)
    # ------------------------------------------------------------------

    def _tac_pursue_enabled(self) -> bool:
        """Sub-gate for the AI card-pursuit layer (wave 121-122). DEFAULT-OFF:
        returns True only when SWEG_TAC_DECK is ON AND SWEG_TAC_PURSUE is
        EXPLICITLY "1".

        Wave-122 A/B (N=80, deck-only vs deck+pursuit): the layer is INEFFECTIVE
        — it did NOT raise Behind Enemy Lines / Cleanse achievement (35%→34% /
        27%→24%, unchanged), because the redirected spare chaff cannot reach or
        hold those targets (the enemy deployment zone is far and lethal; a
        forward objective is not controlled). Its small N=40 headline move
        (−0.17) was noise + a COMBAT-COST artifact (diverting chaff weakens the
        pursuing army) and washed at N=80 (deck-only 3.62 → deck+pursuit 3.60,
        −0.02). So it is decoupled from the deck (explicit opt-in only); the deck
        (M2) runs deck-only by default. The card-achievement stall is the
        one-Unit-per-model REPRESENTATION gap (fragile distributed bodies cannot
        reach/hold targets), the same root as the Imperial Knights primary
        over-hold — that is M4, not the pursuit AI. AI heuristic only — no 10e
        rule citation required."""
        if not self._tac_deck_enabled():
            return False
        return __import__("os").environ.get("SWEG_TAC_PURSUE", "0") == "1"

    def _assign_card_pursuit(self, active, other) -> None:
        """Wave 121 — AI card-pursuit pre-movement hook.  Sets `pursue_target`
        on up to two SPARE chaff units in the active army so that
        pick_move_intent routes them toward the geographic goal of their held
        Tactical card this activation.

        Only two movement-pursuable cards are handled:
          * 'behind_enemy_lines' — sends spare chaff into the opponent's
            deployment zone (the strip at the far edge of the board).
          * 'cleanse' — sends spare chaff toward the nearest objective that is
            OUTSIDE the active army's own deployment zone, so the existing
            _assign_cleanse_actions (which runs AFTER movement) can then flag
            the unit once it has arrived.

        Selection is strictly even-handed by CAPABILITY:
          * _is_chaff_unit gate (cheap non-CHARACTER unit, any faction).
          * action_this_round is None (not already doing something else).
          * pursue_target is None (not already assigned by a prior card in the
            same turn iteration).
          * Unit must be alive.

        A Knight-shape army produces zero chaff → no units are ever assigned →
        the over-rate stall is FAITHFUL and must remain.  NO faction awareness.

        Called BEFORE the move loop in _run_round_vanilla_turns so that
        pick_move_intent reads pursue_target during each unit's activation.
        pursuit is cleared at the top of each army's turn (per-turn).
        """
        if not self._tac_pursue_enabled():
            return
        if getattr(active, "secondary_track", None) != "TACTICAL":
            return
        hand = getattr(active, "tactical_hand", None)
        if not hand:
            return
        from .strategy import _is_chaff_unit
        own_is_a = active is self.a
        PURSUIT_CAP = 2   # up to 2 spare chaff committed per card, per turn

        if "behind_enemy_lines" in hand:
            # Target: the midpoint of the opponent's deployment zone strip.
            # Army A deploys low-y → enemy DZ is the high-y strip; Army B
            # deploys high-y → enemy DZ is the low-y strip.
            dz = self.map.deployment_width
            mid_x = self.map.width / 2.0
            if own_is_a:
                # Enemy DZ: y from (height - dz) to height. Target its centre.
                target_y = self.map.height - dz * 0.5
            else:
                # Enemy DZ: y from 0 to dz. Target its centre.
                target_y = dz * 0.5
            bel_target = (mid_x, target_y)
            n = 0
            for u in active.alive_units:
                if n >= PURSUIT_CAP:
                    break
                if u.action_this_round is not None:
                    continue
                if u.pursue_target is not None:
                    continue
                if not _is_chaff_unit(u):
                    continue
                u.pursue_target = bel_target
                n += 1

        if "cleanse" in hand:
            # Target: the nearest forward objective (outside the active army's
            # own DZ) that this army has a chance of occupying. We pick the
            # objective closest to the midpoint of the board's x-axis and
            # forward in y (outside own DZ). Each chaff unit gets the same
            # target; picking the nearest-to-UNIT would be better but adds
            # per-unit iteration that isn't worth the added complexity.
            forward_objs = [
                obj for obj in self.map.objectives
                if self._obj_outside_own_dz(obj, own_is_a)
            ]
            if forward_objs:
                mid_x = self.map.width / 2.0
                # Prefer the objective closest to the board midpoint on x so
                # chaff heads toward a central, reachable forward marker.
                cleanse_obj = min(
                    forward_objs,
                    key=lambda o: abs(o.x - mid_x),
                )
                cleanse_target = (cleanse_obj.x, cleanse_obj.y)
                n = 0
                for u in active.alive_units:
                    if n >= PURSUIT_CAP:
                        break
                    if u.action_this_round is not None:
                        continue
                    if u.pursue_target is not None:
                        continue
                    if not _is_chaff_unit(u):
                        continue
                    u.pursue_target = cleanse_target
                    n += 1

        # Wave 180 — BOARD take-and-hold card pursuit. The wave-121/122 layer only
        # routed Behind Enemy Lines / Cleanse (far, lethal forward targets) and
        # washed because chaff could not reach/hold the enemy deployment zone. The
        # held BOARD cards are different: their markers are CLOSE and HOLDABLE —
        # Defend Stronghold's marker sits in the army's OWN deployment zone, Secure
        # No Man's Land / Extend Battle Lines target the mid-board. The wave-179
        # achieve-rate diagnostic showed these stall at 8-19% only because the move
        # AI pushes every body forward and never parks one on its own/near-home
        # marker. Route up to one spare chaff per UNMET board-card condition to the
        # marker that condition needs. Even-handed by CAPABILITY (the chaff gate,
        # no faction logic): a Knight with no chaff routes nothing and stays
        # faithful. AI movement heuristic — no 10e rule citation required (same
        # class as the wave-121 pursuit above).
        for goal in self._board_pursuit_goals(hand, own_is_a):
            for u in active.alive_units:
                if u.action_this_round is not None:
                    continue
                if u.pursue_target is not None:
                    continue
                if not _is_chaff_unit(u):
                    continue
                u.pursue_target = goal
                break   # one spare chaff committed per board-card goal

    def _board_pursuit_goals(self, hand, own_is_a):
        """Wave 180 — marker (x,y) goals for the held BOARD take-and-hold cards
        whose control condition is currently UNMET, so `_assign_card_pursuit`
        routes a spare body to each. Targets the nearest UNMET marker of the right
        kind (prefers a marker we do NOT already control — reinforcing an unmet
        condition, not wasting a body on a held one), biased toward the army's home
        edge for reachability. Even-handed; no faction logic. Returns [] when no
        board card is held or every condition is already met."""
        active = self.a if own_is_a else self.b
        other = self.b if own_is_a else self.a
        objs = list(enumerate(self.map.objectives))

        def controlled(obj) -> bool:
            return self._oc_within(active, obj) > self._oc_within(other, obj)

        mx = self.map.width / 2.0
        home_y = (self.map.deployment_width * 0.5 if own_is_a
                  else self.map.height - self.map.deployment_width * 0.5)

        def nearest_unmet(cands):
            # cands: list of (idx, obj). Prefer markers we do not yet control.
            unmet = [o for (_, o) in cands if not controlled(o)]
            pool = unmet if unmet else [o for (_, o) in cands]
            if not pool:
                return None
            o = min(pool, key=lambda ob: (ob.x - mx) ** 2 + (ob.y - home_y) ** 2)
            return (o.x, o.y)

        own_dz = [(i, o) for (i, o) in objs if self._obj_in_own_dz(o, own_is_a)]
        nml = [(i, o) for (i, o) in objs if self._obj_in_nml(o)]
        goals = []

        if "defend_stronghold" in hand:
            g = nearest_unmet(own_dz)
            if g is not None:
                goals.append(g)
        if "secure_no_mans_land" in hand:
            g = nearest_unmet(nml)
            if g is not None:
                goals.append(g)
        if "extend_battle_lines" in hand:
            # Needs an own-DZ marker AND a No Man's Land marker; route a body to
            # whichever condition is currently unmet (both if both are unmet).
            if not any(controlled(o) for (_, o) in own_dz):
                g = nearest_unmet(own_dz)
                if g is not None:
                    goals.append(g)
            if not any(controlled(o) for (_, o) in nml):
                g = nearest_unmet(nml)
                if g is not None:
                    goals.append(g)
        if "storm_hostile_objective" in hand:
            opp_tag = "b" if own_is_a else "a"
            stormable = [(i, o) for (i, o) in objs
                         if self._obj_controller_at_round_start.get(i) == opp_tag
                         and not controlled(o)]
            g = nearest_unmet(stormable) if stormable else None
            if g is not None:
                goals.append(g)
        if "area_denial" in hand:
            # Hold the battlefield centre (the Area Denial scoring point).
            goals.append((mx, self.map.height / 2.0))
        return goals

    # ------------------------------------------------------------------
    # Wave 133-135 — secondary dedication PLANNER (positioning bias only).
    #
    # REBUILD NOTE (wave 135): the wave-133 build gated POSITION-card scoring
    # (Engage on All Fronts / Behind Enemy Lines) on `dedicated_card`. That was
    # NOT rules-authentic — those are POSITIONAL Secondaries that score on
    # presence/occupancy at end of turn, no Action and no "dedication" required —
    # and the A/B confirmed it backfired (it made the Knight relatively better).
    # The scoring gate has been REVERTED (see _score_one_card's position branch:
    # the full unit list is passed, gate ON or OFF). What survives here is the
    # dedication PLANNER as a MOVEMENT/POSITIONING bias only: it peels ONE SPARE
    # unit per held position card and biases its move toward the card's
    # geographic goal (enemy DZ for Behind Enemy Lines; an unoccupied quarter for
    # Engage), reusing _assign_card_pursuit's geometry. That bias is faithful — a
    # Knight with no spare body cannot spread, so it emergently occupies fewer
    # quarters and incidentally scores less, with NO fabricated scoring gate.
    # `dedicated_card` is no longer read by any scorer; the rules-clean low-unit
    # penalty now lives entirely on the ACTION cards (Cleanse / Sabotage) via the
    # Action-cost contract (_unit_can_perform_action / _action_completes). Env-
    # gated SWEG_SECONDARY (default OFF); OFF path is byte-identical. The planner
    # bias is an AI heuristic; the Action-cost rule is cited as
    # `simulator.secondary_action_cost`.
    # ------------------------------------------------------------------

    def _secondary_dedication_enabled(self) -> bool:
        """SWEG_SECONDARY gate. Unset → the legacy secondary behaviour runs
        byte-for-byte: the dedication planner sets no positioning bias and the
        Cleanse/Sabotage Action cards use their legacy chaff-selection /
        still-alive scoring. Set to "1" → the dedication positioning bias runs
        and the Action cards use the rules-authentic Action-cost contract."""
        return __import__("os").environ.get("SWEG_SECONDARY", "0") == "1"

    # Engagement range used for the spare-unit "not in melee" test — matches
    # the 10e Engagement Range gate the sim applies elsewhere (Battle._do_shoot
    # locks a unit out of shooting when an enemy is within this distance).
    _DEDICATION_ENGAGE_RANGE: float = 1.5
    # A unit counts as a "productive shooter" (and so is NOT spare) when its
    # expected unsaved-agnostic ranged output reaches this threshold AND it has
    # an enemy in weapon range — a real player keeps such a unit shooting rather
    # than peeling it off for a secondary.
    _DEDICATION_SHOOTER_OUTPUT: float = 2.0

    def _unit_is_dedicatable(self, unit, other) -> bool:
        """True iff `unit` is SPARE — a body a real player would peel off to
        perform / hold a secondary. This is the even-handed crux of Stage A; a
        Knight's units are all holding / fighting / shooting, so none are spare.

        A unit is SPARE iff ALL of:
          * it is alive, has not already acted this round
            (`action_this_round is None`), and is not already committed to a
            card this turn (`dedicated_card is None`);
          * it is NOT holding an objective — not within any objective's
            control_radius of (obj.x, obj.y) for any objective on the map;
          * it is NOT in melee — no enemy in `other.alive_units` within
            Engagement Range (~1.5");
          * it is NOT a productive shooter — it does NOT have both meaningful
            ranged output (attacks * hit_probability * weapon_damage_per_shot
            >= 2.0) AND an enemy within its weapon range.

        NO faction awareness, NO chaff-only restriction, NO model-count branch:
        the asymmetry is purely emergent from how many units pass this test.
        """
        if not unit.is_alive:
            return False
        if unit.action_this_round is not None:
            return False
        if unit.dedicated_card is not None:
            return False
        # Not holding an objective.
        for obj in self.map.objectives:
            if _distance(unit.position, (obj.x, obj.y)) <= obj.control_radius:
                return False
        # Not in melee with any enemy.
        for e in other.alive_units:
            if _distance(unit.position, e.position) <= self._DEDICATION_ENGAGE_RANGE:
                return False
        # Not a productive shooter with a target in range.
        p = unit.profile
        ranged_output = (
            (p.attacks or 0) * (p.hit_probability or 0.0)
            * (p.weapon_damage_per_shot or 0.0)
        )
        if ranged_output >= self._DEDICATION_SHOOTER_OUTPUT:
            wpn_range = float(p.range_inches or 0)
            for e in other.alive_units:
                if _distance(unit.position, e.position) <= wpn_range:
                    return False
        return True

    def _assign_card_dedication(self, active, other) -> None:
        """Stage A dedication planner (models on _assign_card_pursuit but is a
        SEPARATE, differently-gated method). For each POSITION card the active
        TACTICAL army holds, commit ONE SPARE unit to it: set its
        `dedicated_card` and bias its move toward the card's geographic goal.

        Only the two Stage-A position cards are handled:
          * 'behind_enemy_lines' — target the midpoint of the OPPONENT's
            deployment-zone strip (identical geometry to _assign_card_pursuit).
          * 'engage_on_all_fronts' — target a board quarter the army does NOT
            already occupy, so the dedicated body spreads coverage toward a new
            quarter. If no empty quarter remains (the army already spans all
            four) the unit is still dedicated but left with no spread target —
            it counts where it stands.

        One spare unit per card; a spare unit dedicates to at most one card (the
        _unit_is_dedicatable test rejects a unit whose dedicated_card is already
        set). A Knight-shape army produces zero spare units → no dedications →
        it scores these cards 0 (faithful, must remain). NO faction awareness.

        Called BEFORE the move loop in _run_round_vanilla_turns for the ACTIVE
        army, alongside _assign_card_pursuit. dedicated_card is cleared at the
        top of each army's turn (per-turn, same lifecycle as pursue_target).
        """
        if not self._secondary_dedication_enabled():
            return
        # Only the TACTICAL track holds a hand of cards to dedicate toward.
        if getattr(active, "secondary_track", None) != "TACTICAL":
            return
        hand = getattr(active, "tactical_hand", None)
        if not hand:
            return
        own_is_a = active is self.a
        cx = self.map.width / 2.0
        cy = self.map.height / 2.0

        if "behind_enemy_lines" in hand:
            # Target: the midpoint of the opponent's deployment-zone strip —
            # identical geometry to _assign_card_pursuit's BEL branch.
            dz = self.map.deployment_width
            mid_x = self.map.width / 2.0
            if own_is_a:
                # Army A deploys low-y → enemy DZ is the high-y strip.
                target_y = self.map.height - dz * 0.5
            else:
                # Army B deploys high-y → enemy DZ is the low-y strip.
                target_y = dz * 0.5
            bel_target = (mid_x, target_y)
            for u in active.alive_units:
                if self._unit_is_dedicatable(u, other):
                    u.dedicated_card = "behind_enemy_lines"
                    u.pursue_target = bel_target
                    break

        if "engage_on_all_fronts" in hand:
            # Spread toward a board quarter the army does not already occupy.
            # Quarter encoding mirrors score_position_delta: (qx, qy) with
            # qx=0 for x<cx else 1, qy=0 for y<cy else 1.
            occupied = set()
            for u in active.alive_units:
                ux, uy = u.position
                occupied.add((0 if ux < cx else 1, 0 if uy < cy else 1))
            # Centre of each quarter, used as the spread target.
            quarter_centre = {
                (0, 0): (cx * 0.5, cy * 0.5),
                (1, 0): (cx + cx * 0.5, cy * 0.5),
                (0, 1): (cx * 0.5, cy + cy * 0.5),
                (1, 1): (cx + cx * 0.5, cy + cy * 0.5),
            }
            empty_quarters = [q for q in quarter_centre if q not in occupied]
            # Deterministic pick: the lowest-keyed empty quarter (or None if the
            # army already spans all four — then the unit counts where it stands).
            engage_target = (
                quarter_centre[sorted(empty_quarters)[0]]
                if empty_quarters else None
            )
            for u in active.alive_units:
                if self._unit_is_dedicatable(u, other):
                    u.dedicated_card = "engage_on_all_fronts"
                    if engage_target is not None:
                        u.pursue_target = engage_target
                    break

    # ------------------------------------------------------------------
    # Wave 135 rebuild — the Action-card cost (Cleanse / Sabotage).
    #
    # In real 10e an Action (Cleanse, Sabotage, etc.) is a deliberate
    # commitment: in its Movement / Command phase a unit may START an Action
    # instead of fighting — for the rest of the turn it CANNOT shoot and CANNOT
    # declare a charge, and the Action only COMPLETES at the end of the turn if
    # the unit is still there having done none of those things. That opportunity
    # cost is the rules-clean reason a low-unit army cannot farm these cards: a
    # Knight's handful of units are all shooting / charging / holding, so peeling
    # one to stand on a marker doing an Action forfeits a large fraction of the
    # army's output — the AI will not (and cannot afford to) do it, so it scores
    # the Action cards 0. The asymmetry is EMERGENT from unit count and from the
    # shoot/charge opportunity cost: NO faction branch, NO model-count branch,
    # NO Knight penalty. Cited as `simulator.secondary_action_cost`.
    # ------------------------------------------------------------------

    def _unit_in_engagement(self, unit, other) -> bool:
        """True iff any alive enemy is within Engagement Range (~1.5") of
        `unit` — the unit is tied up in melee and so cannot legally start /
        complete an Action this turn (10e: a unit within Engagement Range
        cannot perform an Action)."""
        for e in other.alive_units:
            if _distance(unit.position, e.position) <= self._DEDICATION_ENGAGE_RANGE:
                return True
        return False

    def _unit_can_perform_action(self, unit, other) -> bool:
        """The rules-authentic Action contract used to SELECT a unit to start an
        Action (Cleanse / Sabotage) at assignment time. A unit may commit to an
        Action iff ALL of:
          * it is alive and has not already acted this round
            (`action_this_round is None`);
          * it has Objective Control > 0 — an OC-0 model (e.g. an AIRCRAFT, or a
            Knight stripped to 0 OC on its damaged bracket) cannot hold / perform
            the objective-bound Action;
          * it is NOT within Engagement Range of any enemy (a unit in melee
            cannot perform an Action);
          * it is NOT a PRODUCTIVE SHOOTER with a target in range — i.e. peeling
            it off forfeits no meaningful firepower (output
            attacks * hit_probability * weapon_damage_per_shot >= 2.0 with an
            enemy in weapon range marks a unit the AI keeps shooting). This is
            the even-handed, EMERGENT crux: a Knight's units are all productive
            shooters / fighters, so none pass, and it scores the Action cards 0;
            a broad army has spare non-shooting bodies that do.

        NO faction awareness, NO model-count branch, NO chaff-cost gate — only
        the capability test above. The shoot/charge lockout itself is enforced by
        the existing `action_this_round` flag (read by _do_shoot and _do_charge);
        this predicate only decides WHICH unit is allowed to take the Action.
        """
        if not unit.is_alive:
            return False
        if unit.action_this_round is not None:
            return False
        # Objective Control > 0. Use the model's DECLARED OC characteristic (a
        # stat-OC-0 model — some AIRCRAFT / drones — genuinely cannot hold), AND
        # the damaged-bracket-adjusted effective OC (a Knight stripped to 0 OC on
        # its damage table also cannot). _effective_oc floors a missing/zero stat
        # to 1, so the raw-stat check is needed to catch a real OC-0 datasheet.
        if (getattr(unit.profile, "oc", 0) or 0) <= 0:
            return False
        if self._effective_oc(unit) <= 0:
            return False
        if self._unit_in_engagement(unit, other):
            return False
        p = unit.profile
        ranged_output = (
            (p.attacks or 0) * (p.hit_probability or 0.0)
            * (p.weapon_damage_per_shot or 0.0)
        )
        if ranged_output >= self._DEDICATION_SHOOTER_OUTPUT:
            wpn_range = float(p.range_inches or 0)
            for e in other.alive_units:
                if _distance(unit.position, e.position) <= wpn_range:
                    return False
        return True

    def _action_completes(self, unit, other) -> bool:
        """End-of-turn completion test for a unit that started an Action this
        round: the Action only scores if the unit SURVIVED (still alive) and was
        not dragged into Engagement Range (a unit pulled into melee cannot finish
        its Action). OC>0 at completion is checked by the per-card scorer (which
        also re-confirms objective control)."""
        return unit.is_alive and not self._unit_in_engagement(unit, other)

    # ------------------------------------------------------------------
    # Wave 83 Tier A — objective-holding / board-control secondaries
    #
    # The real Pariah Nexus secondary deck contains a family of take-and-hold
    # cards the simulator did not model; they are exactly the scoring paths a
    # body army uses to out-score a durable camper (you cannot kill a Knight,
    # so you take/contest the objectives it cannot be on). Every army may bring
    # the whole package — the asymmetry is purely in COMPLETION (a low-model
    # army controls few objectives across zones), bounded by the existing 40-VP
    # secondary total cap (`_decide_winner`) and by each card's natural ≤20-VP
    # ceiling over the four scoring rounds (the real per-Fixed-mission 20-VP cap,
    # honoured by construction — no card here exceeds 5 VP/round × 4 = 20). No
    # per-faction weight and no count gate: identical pool + identical scoring
    # for both sides. Env-gated SWEG_TIER_A for the A/B; inert (returns 0) when
    # off, so the chosen-secondary tuples may always include these keys.
    # Source: https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-battles/
    # ------------------------------------------------------------------

    def _tier_a_enabled(self) -> bool:
        # Landed ON in wave 83 after the env-gated N=40 A/B validated it as a
        # clear fidelity win: gated MAE 4.95 → 4.17, factions in the noise band
        # 6 → 9, with most over-shooters easing (Drukhari +18.6 → +9.7, Custodes
        # +7.4 → +2.7, Adepta Sororitas +8.4 → +2.8, T'au +5.9 → +0.6) and the
        # board-control under-shooters rising (Chaos Space Marines −19.2 → −11.3,
        # Chaos Knights −12.3 → −1.1). It did NOT fix Imperial Knights (+19.1 →
        # +29.2) — the take-and-hold cards reward objective CONTROL, and a durable
        # Knight over-controls objectives, so it scores them itself; that sharpens
        # the IK diagnosis to objective-over-control, addressed by a later lever,
        # not a reason to withhold a faithful aggregate win. Default ON; set
        # SWEG_TIER_A=0 to re-gate for a future isolation A/B.
        return __import__("os").environ.get("SWEG_TIER_A", "1") != "0"

    def _obj_in_own_dz(self, obj, own_is_army_a: bool) -> bool:
        """True if the objective sits in the scoring side's own deployment zone.
        Army A deploys low-y, B high-y."""
        dz = self.map.deployment_width
        if own_is_army_a:
            return obj.y <= dz
        return obj.y >= (self.map.height - dz)

    def _obj_in_nml(self, obj) -> bool:
        """True if the objective is in No Man's Land (outside both deployment
        zones) — symmetric, so it needs no side argument."""
        dz = self.map.deployment_width
        return dz < obj.y < (self.map.height - dz)

    def _objective_controllers(self) -> dict:
        """Map obj_idx -> 'a' / 'b' / None for whoever currently has strictly
        greater Objective Control within each marker's radius. Used to snapshot
        round-start control for Storm Hostile Objective."""
        out: dict = {}
        for idx, obj in enumerate(self.map.objectives):
            a = self._oc_within(self.a, obj)
            b = self._oc_within(self.b, obj)
            out[idx] = "a" if a > b else ("b" if b > a else None)
        return out

    def _score_area_denial(self, army, opponent) -> int:
        """Area Denial: 5 VP if one+ of your units is within 3" of the
        battlefield centre AND no enemy unit is within 6" of it; 2 VP instead if
        no enemy unit is within 3" of it. Cited `simulator.secondary_area_denial`."""
        cx = self.map.width / 2.0
        cy = self.map.height / 2.0

        def any_within(units, r: float) -> bool:
            r2 = r * r
            for u in units:
                dx = u.position[0] - cx
                dy = u.position[1] - cy
                if dx * dx + dy * dy <= r2:
                    return True
            return False

        if not any_within(army.alive_units, 3.0):
            return 0
        if not any_within(opponent.alive_units, 6.0):
            return 5
        if not any_within(opponent.alive_units, 3.0):
            return 2
        return 0

    def _score_board_secondaries(self, army, opponent, own_is_army_a: bool,
                                 chosen_override=None) -> int:
        """End-of-round scoring for the Tier-A take-and-hold secondaries an army
        chose. Control of a marker = strictly greater Objective Control than the
        opponent (same test as Cleanse). Env-gated; returns 0 when off.

        M2: `chosen_override` (default None → read `army.chosen_secondaries`, the
        byte-identical legacy behaviour) lets the per-card dispatcher isolate one
        board card with a singleton tuple.

        * Secure No Man's Land — 2 VP one / 5 VP two+ No Man's Land objectives
          controlled. Cited `simulator.secondary_secure_no_mans_land`.
        * Defend Stronghold — 3 VP controlling one+ objective in your own
          deployment zone. Cited `simulator.secondary_defend_stronghold`.
        * Extend Battle Lines — 5 VP controlling one+ in your zone AND one+ in
          No Man's Land. Cited `simulator.secondary_extend_battle_lines`.
        * Storm Hostile Objective — 4 VP controlling one+ objective the opponent
          controlled at the start of the round.
          Cited `simulator.secondary_storm_hostile_objective`.
        * Area Denial — see `_score_area_denial`.
        """
        if not self._tier_a_enabled():
            return 0
        chosen = (chosen_override if chosen_override is not None
                  else (getattr(army, "chosen_secondaries", ()) or ()))
        opp_tag = "b" if own_is_army_a else "a"
        nml_controlled = 0
        own_dz_controlled = 0
        stormed = 0
        for idx, obj in enumerate(self.map.objectives):
            if self._oc_within(army, obj) <= self._oc_within(opponent, obj):
                continue   # not controlled by this side
            if self._obj_in_own_dz(obj, own_is_army_a):
                own_dz_controlled += 1
            elif self._obj_in_nml(obj):
                nml_controlled += 1
            if self._obj_controller_at_round_start.get(idx) == opp_tag:
                stormed += 1
        total = 0
        if "secure_no_mans_land" in chosen:
            total += 5 if nml_controlled >= 2 else (2 if nml_controlled >= 1 else 0)
        if "defend_stronghold" in chosen and own_dz_controlled >= 1:
            total += 3
        if "extend_battle_lines" in chosen and own_dz_controlled >= 1 and nml_controlled >= 1:
            total += 4   # CA-2025-26: Extend Battle Lines top tier reduced from 5 VP to 4 VP
        if "storm_hostile_objective" in chosen and stormed >= 1:
            total += 4
        if "area_denial" in chosen:
            total += self._score_area_denial(army, opponent)
        return total

    # ------------------------------------------------------------------
    # M2 (wave 119) — the real 2-card Tactical secondary deck (env-gated
    # SWEG_TAC_DECK). See docs/M2_TACTICAL_DECK_PLAN.md and
    # data/rule_citations.d/secondaries_pariah_nexus.json#simulator.tactical_secondary_deck.
    #
    # CA-2025-26: each army secretly chooses Fixed OR Tactical Missions. A FIXED
    # army scores its 2 kill cards every round; a TACTICAL army holds a 2-card
    # hand, scoring only those two and discarding+redrawing any it achieves
    # (scored 1+ VP from) each Command phase. Today's scorer scored the UNION of
    # ~9-11 sources every round, trivially exceeding the 40 cap and washing the
    # secondary out. When the gate is ON, `_score_secondaries` routes through the
    # track model below; when OFF, the legacy union scoring runs byte-identical.
    # ------------------------------------------------------------------

    def _tac_deck_enabled(self) -> bool:
        """M2 real 2-card Tactical secondary deck — now DEFAULT-ON (fidelity-revisit
        sweep #2, wave 210). The CA-2025-26 match draws a 2-card hand from a curated
        pool of faithful cards (3 un-sourced cards intentionally deferred); the legacy
        "score every secondary source simultaneously" was unfaithful (both armies cap
        at 40 = a wash). `SWEG_TAC_DECK=0` restores the legacy union-of-sources path."""
        return __import__("os").environ.get("SWEG_TAC_DECK", "1") != "0"

    def _init_tactical_deck(self, army: Army) -> None:
        """Seed a TACTICAL army's 2-card hand + remaining deck deterministically.

        Called once per battle at start (after `pick_secondaries` set the track).
        No-op when the deck gate is off or the army is on the FIXED track.

        Determinism: the deck shuffle must reproduce under PYTHONHASHSEED=0. We do
        NOT draw from the global `random` — that would (a) couple the deck order
        to however much RNG army-building happened to consume and (b) perturb the
        downstream movement/combat stream on the ON path. Instead the per-army
        deck seed is a pure function of values already fixed at battle start: a
        stable CRC of the army name combined with a CRC of BOTH armies' sorted
        unit-name multisets (the matchup-as-built). `zlib.crc32` is used, NOT the
        salted built-in `hash`, so the seed is identical under PYTHONHASHSEED=0
        across processes for the same built armies. A private `random.Random`
        shuffles the pool, so the two armies get independent, reproducible orders
        and the global RNG stream is untouched."""
        army.secondary_track = getattr(army, "secondary_track", None)
        army.tactical_hand = []
        army.tactical_deck = []
        if not self._tac_deck_enabled():
            return
        if army.secondary_track != "TACTICAL":
            return
        import zlib
        from .secondaries import TACTICAL_DECK_POOL
        # Battle-stable, global-RNG-free seed: army name CRC XOR a CRC of the
        # sorted unit-name multiset of both armies (the matchup identity). Using
        # both rosters makes the seed depend on the whole battle, not just the
        # name; using the army's OWN name as well gives A and B independent orders.
        def _roster_sig(a) -> str:
            return "|".join(sorted((u.profile.name or "") for u in a.units))
        matchup_sig = f"{_roster_sig(self.a)}##{_roster_sig(self.b)}"
        name_crc = zlib.crc32((army.name or "").encode("utf-8")) & 0xFFFFFFFF
        matchup_crc = zlib.crc32(matchup_sig.encode("utf-8")) & 0xFFFFFFFF
        deck_rng = random.Random(name_crc ^ matchup_crc)
        deck = list(TACTICAL_DECK_POOL)
        deck_rng.shuffle(deck)
        # Draw the opening hand of two (or fewer if the pool is tiny).
        army.tactical_hand = deck[:2]
        army.tactical_deck = deck[2:]

    def _score_one_card(self, card_key: str, scoring_army: Army,
                        other_army: Army, own_is_army_a: bool,
                        round_num: int) -> int:
        """M2 per-card dispatcher: score EXACTLY ONE secondary card this round
        for `scoring_army`, routing `card_key` to its existing scorer with a
        singleton `chosen` so no other card leaks in. Returns that card's VP.

        Every existing scorer already gates each card on the `chosen` tuple, so a
        singleton isolates one card. The board / cleanse / sabotage scorers read
        `army.chosen_secondaries` directly rather than a parameter, so they take a
        `chosen_override` (added minimally; `None` preserves the OFF behaviour)."""
        from .secondaries import score_round_delta, score_position_delta
        one = (card_key,)
        # --- Kill cards (FIXED pool, but routed here too for completeness) -----
        if card_key in ("bring_it_down", "no_prisoners",
                        "cull_the_horde", "assassination"):
            # Score `scoring_army`'s kills of `other_army` this round: diff the
            # OTHER army's round-start snapshot against its current state.
            snap = (self._b_round_snapshot if own_is_army_a
                    else self._a_round_snapshot)
            if snap is None:
                return 0
            other_warlord = (self.b.warlord_uid if own_is_army_a
                             else self.a.warlord_uid)
            # Fixed-vs-Tactical track split (CA-2025-26): when the scoring army
            # is on the TACTICAL track the three kill cards (bring_it_down,
            # cull_the_horde, assassination) score a flat per-turn value if any
            # qualifying enemy unit died this turn. No Prisoners stays per-unit-
            # capped in both tracks. See score_round_delta's `tactical` parameter.
            # Cited as `simulator.secondary_assassination_tactical`,
            # `simulator.secondary_bring_it_down_tactical`,
            # `simulator.secondary_cull_the_horde_tactical`.
            is_tactical = (
                getattr(scoring_army, "secondary_track", None) == "TACTICAL"
            )
            bid, np_, cth, assn = score_round_delta(
                snap, other_army.units,
                enemy_warlord_uid=other_warlord,
                chosen=one,
                tactical=is_tactical,
            )
            return bid + np_ + cth + assn
        # --- Position cards (Engage / Behind Enemy Lines) ----------------------
        if card_key in ("engage_on_all_fronts", "behind_enemy_lines"):
            # Wave 135 rebuild: position cards score on PRESENCE/POSITION at the
            # end of the turn — any qualifying alive unit in the relevant quarter
            # / enemy deployment zone counts. This is the rules-authentic 10e
            # behaviour: Engage on All Fronts and Behind Enemy Lines are
            # positional Secondaries scored on occupancy, NOT on a performed
            # Action and NOT on a "dedication" commitment. The wave-133/134
            # dedication GATE on these cards was an unfaithful under-count (it
            # fabricated an Action requirement for a positional card) and the
            # A/B confirmed it backfired, so it is reverted: the full unit list
            # is always passed, gate ON or OFF, which restores the pre-`7d962ad`
            # incidental scoring byte-for-byte (score_position_delta counts only
            # alive units, as before). The deliberate-dedication / Action-cost
            # mechanism now lives ONLY on the Action cards (Cleanse / Sabotage);
            # see _unit_can_perform_action and _score_cleanse / _score_sabotage.
            eng, bel = score_position_delta(
                scoring_army.units, self.map, own_is_army_a=own_is_army_a,
                round_num=round_num, chosen=one,
            )
            return eng + bel
        # --- Action cards (Cleanse / Sabotage) ---------------------------------
        if card_key == "cleanse":
            return self._score_cleanse(scoring_army, other_army,
                                       own_is_army_a=own_is_army_a,
                                       chosen_override=one)
        if card_key == "sabotage":
            return self._score_sabotage(scoring_army, own_is_army_a=own_is_army_a,
                                        chosen_override=one, opponent=other_army)
        # --- Board take-and-hold cards -----------------------------------------
        from .secondaries import BOARD_SECONDARY_KEYS
        if card_key in BOARD_SECONDARY_KEYS:
            return self._score_board_secondaries(
                scoring_army, other_army, own_is_army_a=own_is_army_a,
                chosen_override=one)
        # Unknown card key — fail loud (CLAUDE.md §13: no silent defaults).
        raise KeyError(
            f"_score_one_card: unrecognised Tactical-deck card '{card_key}' "
            f"(not in the kill / position / action / board pools)"
        )

    def _score_tactical_hand(self, army: Army, other_army: Army,
                            own_is_army_a: bool, round_num: int) -> int:
        """M2: score a TACTICAL army's <=2 held cards this round, then run the
        achieve→discard→redraw step (a card that scored 1+ VP is discarded and
        replaced from the deck, refilling the hand to two if the deck has cards).
        Returns the round's total VP from the hand. Scores ONLY the hand."""
        total = 0
        achieved: list = []
        for card in list(army.tactical_hand):
            vp = self._score_one_card(card, army, other_army,
                                      own_is_army_a, round_num)
            if vp > 0:
                total += vp
                achieved.append(card)
        # Discard achieved cards and redraw to refill the hand to two.
        for card in achieved:
            army.tactical_hand.remove(card)
        while len(army.tactical_hand) < 2 and army.tactical_deck:
            army.tactical_hand.append(army.tactical_deck.pop(0))
        return total

    def _score_secondaries_deck(self, round_num: int) -> None:
        """M2 deck-aware per-round secondary scoring (SWEG_TAC_DECK ON). Each army
        scores ONLY its chosen track: a FIXED army its 2 kill cards every round; a
        TACTICAL army its 2-card hand (with achieve→discard→redraw). Never both,
        never the whole pile. The 40-VP secondary total cap in `_decide_winner`
        still bounds the sum. Cited as `simulator.tactical_secondary_deck`."""
        for army, other, own_is_a, add_vp in (
            (self.a, self.b, True, "a"),
            (self.b, self.a, False, "b"),
        ):
            track = getattr(army, "secondary_track", None)
            if track == "TACTICAL":
                vp = self._score_tactical_hand(army, other, own_is_a, round_num)
            else:
                # FIXED (or an unset track defensively treated as FIXED): score
                # the 2 chosen kill cards every round via the per-card dispatcher.
                vp = 0
                for card in (army.chosen_secondaries or ()):
                    vp += self._score_one_card(card, army, other,
                                               own_is_a, round_num)
            if own_is_a:
                self._a_vp += vp
                self._a_secondary_vp += vp
            else:
                self._b_vp += vp
                self._b_secondary_vp += vp

    def _score_secondaries(self, round_num: int) -> None:
        """End-of-round secondary VP scoring (Bring it Down + No Prisoners).

        Computes the kill delta between each army's round-start snapshot
        and its current alive units, awarding per-round capped VP to the
        opposing side. Implements Pariah Nexus tournament-pack secondary
        scoring so the sim's win condition isn't primaries-only — without
        secondaries the sim systematically over-rewards sticky-defensive
        play (Death Guard +16.4 over) and under-rewards kill-oriented
        shapes that would in real play score by removing enemy units.

        SC4-A — kill-counting secondaries:
        * Bring it Down — 5 VP per enemy MONSTER/VEHICLE destroyed
          this round, capped at 15 VP per round.
          Cited as `simulator.secondary_bring_it_down`.
        * No Prisoners — 5 VP per enemy unit destroyed this round,
          capped at 15 VP per round.
          Cited as `simulator.secondary_no_prisoners`.

        SC4-B — position-tracking secondaries:
        * Engage on All Fronts — 5 VP if alive units occupy 3+ of the
          4 table quarters at end of round.
          Cited as `simulator.secondary_engage_on_all_fronts`.
        * Behind Enemy Lines — 5 VP if any alive unit's position is
          inside the opponent's deployment zone.
          Cited as `simulator.secondary_behind_enemy_lines`.

        SC4-C — selective kill secondaries:
        * Cull the Horde — 5 VP per enemy 10+model unit destroyed,
          capped at 5 VP per round (1 per round).
          Cited as `simulator.secondary_cull_the_horde`.
        * Assassination — 5 VP per enemy CHARACTER destroyed, capped
          at 10 VP per round (2 per round).
          Cited as `simulator.secondary_assassination`.

        Source: https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-mission-pack/

        M2 (wave 119, env-gated SWEG_TAC_DECK): when the deck gate is ON, scoring
        delegates to `_score_secondaries_deck` (each army scores ONLY its Fixed
        or Tactical track — at most 2 sources, not the union of ~9-11). When OFF
        the legacy union scoring below runs byte-for-byte unchanged.
        """
        if self._tac_deck_enabled():
            self._score_secondaries_deck(round_num)
            return
        from .secondaries import score_round_delta, score_position_delta
        # Side A scores VP for killing side B's units this round — diff
        # B's round-start snapshot against B's current state. Four
        # secondary categories (SC4-A Bring it Down + No Prisoners,
        # SC4-C Cull the Horde + Assassination).
        # LC-5: pass each side's Warlord uid for the +1 Assassination
        # bonus when the opponent kills it.
        b_warlord = self.b.warlord_uid
        a_warlord = self.a.warlord_uid
        # CUSTODES-UNPARK — defender faction is whose snapshot is being
        # scored against (i.e. whose units are dying). Pulled from the
        # first unit's profile.faction tag (matches the convention used
        # in `simulator._do_charge`, `_apply_reanimation` and elsewhere
        # in this file for resolving an army's primary faction).
        b_defender_faction = (
            self.b.units[0].profile.faction if self.b.units else None
        )
        a_defender_faction = (
            self.a.units[0].profile.faction if self.a.units else None
        )
        # DRK-DIAG-9 — attacker faction is the SCORING side (i.e. who is
        # earning the VP this delta). Drukhari-attacker triggers the
        # mobile-army damper on Cull (here) and Engage/BEL (below).
        a_attacker_faction = (
            self.a.units[0].profile.faction if self.a.units else None
        )
        b_attacker_faction = (
            self.b.units[0].profile.faction if self.b.units else None
        )
        # SECONDARY-SELECTION-V1: pass each army's `chosen_secondaries`
        # tuple so the scorer only awards VP for the 2 Fixed (+ Tactical)
        # picks this side actually brought. Without this gate the scorer
        # awards all 4 Fixed + both Tactical to every army every game,
        # asymmetrically over-rewarding balanced kill-heavy / mobile
        # rosters (Drukhari, Aeldari, Tyranids).
        # Cited as `simulator.secondary_selection`.
        if self._b_round_snapshot is not None:
            a_bid, a_np, a_cth, a_assn = score_round_delta(
                self._b_round_snapshot, self.b.units,
                enemy_warlord_uid=b_warlord,
                defender_faction=b_defender_faction,
                attacker_faction=a_attacker_faction,
                chosen=self.a.chosen_secondaries,
            )
            a_kill_vp = a_bid + a_np + a_cth + a_assn
            self._a_vp += a_kill_vp
            self._a_secondary_vp += a_kill_vp
        # Side B scores VP for killing side A's units this round.
        if self._a_round_snapshot is not None:
            b_bid, b_np, b_cth, b_assn = score_round_delta(
                self._a_round_snapshot, self.a.units,
                enemy_warlord_uid=a_warlord,
                defender_faction=a_defender_faction,
                attacker_faction=b_attacker_faction,
                chosen=self.b.chosen_secondaries,
            )
            b_kill_vp = b_bid + b_np + b_cth + b_assn
            self._b_vp += b_kill_vp
            self._b_secondary_vp += b_kill_vp

        # SC4-B — position-tracking secondaries scored at end of round.
        # Each side scores against their OWN alive units (Engage is your
        # spread; BEL is your forward projection). own_is_army_a flag
        # tells the scorer which deployment strip is the enemy's.
        # LC-2: round_num gates the 2-of-9 Tactical secondary deck mechanic
        # — each side scores at most ONE of (Engage, BEL) per round on an
        # alternating schedule (see `_is_tactical_secondary_active`).
        # SECONDARY-SELECTION-V1: `chosen` gates further on which Tactical
        # cards the army brought.
        a_eng, a_bel = score_position_delta(
            self.a.units, self.map, own_is_army_a=True, round_num=round_num,
            attacker_faction=a_attacker_faction,
            chosen=self.a.chosen_secondaries,
        )
        self._a_vp += a_eng + a_bel
        self._a_secondary_vp += a_eng + a_bel
        b_eng, b_bel = score_position_delta(
            self.b.units, self.map, own_is_army_a=False, round_num=round_num,
            attacker_faction=b_attacker_faction,
            chosen=self.b.chosen_secondaries,
        )
        self._b_vp += b_eng + b_bel
        self._b_secondary_vp += b_eng + b_bel

        # Pariah Nexus Cleanse action secondary (wave 74, env-gated). Scored like
        # the other secondaries: added to BOTH the live total (_a_vp/_b_vp, what
        # _decide_winner reads) and the reporting tracker (_a_secondary_vp).
        a_cleanse = self._score_cleanse(self.a, self.b, own_is_army_a=True)
        self._a_vp += a_cleanse
        self._a_secondary_vp += a_cleanse
        b_cleanse = self._score_cleanse(self.b, self.a, own_is_army_a=False)
        self._b_vp += b_cleanse
        self._b_secondary_vp += b_cleanse

        # Pariah Nexus Sabotage action secondary (wave 75, env-gated SWEG_S2).
        a_sabotage = self._score_sabotage(self.a, own_is_army_a=True,
                                          opponent=self.b)
        self._a_vp += a_sabotage
        self._a_secondary_vp += a_sabotage
        b_sabotage = self._score_sabotage(self.b, own_is_army_a=False,
                                          opponent=self.a)
        self._b_vp += b_sabotage
        self._b_secondary_vp += b_sabotage

        # Wave 83 Tier A — objective-holding / board-control secondaries
        # (env-gated SWEG_TIER_A). Added to the live total (_a_vp/_b_vp) and the
        # reporting tracker (_a_secondary_vp), exactly like Cleanse/Sabotage; the
        # 40-VP secondary cap in `_decide_winner` bounds the sum.
        a_board = self._score_board_secondaries(self.a, self.b, own_is_army_a=True)
        self._a_vp += a_board
        self._a_secondary_vp += a_board
        b_board = self._score_board_secondaries(self.b, self.a, own_is_army_a=False)
        self._b_vp += b_board
        self._b_secondary_vp += b_board

    # ------------------------------------------------------------------
    # Reanimation Protocols (issue #75)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Detachment-specific stratagem dispatch (round-start)
    # ------------------------------------------------------------------

    def _set_transient_squad(self, unit: "Unit", attr: str) -> None:
        """Set a boolean transient flag on every alive model in *unit*'s squad.

        10e stratagems target "a unit" (all models), not a single model.
        Because each model is its own Unit instance sharing `squad_id`, a
        bare ``unit.transient_X = True`` only buffs the representative model
        picked by the stratagem dispatcher, leaving the other N-1 squad
        members unbuffed.

        This helper fixes that: when ``squad_id >= 0`` it fans the flag out to
        every alive sibling; lone models (``squad_id == -1``) receive the flag
        directly (equivalent to the old single-model set).

        Guards:
        - If ``unit.army_ref`` is None the unit has no army context; fall back
          to setting on ``unit`` only.
        - Only alive models receive the flag (dead models cannot benefit and
          may not have the attribute).
        """
        squad_id = getattr(unit, "squad_id", -1)
        army_ref = getattr(unit, "army_ref", None)
        if squad_id >= 0 and army_ref is not None:
            for m in army_ref.units:
                if getattr(m, "squad_id", -1) == squad_id and m.is_alive:
                    setattr(m, attr, True)
        else:
            setattr(unit, attr, True)

    def _clear_transient_stratagem_flags(self, army: Army) -> None:
        """Reset the per-round stratagem flags on every unit in `army`.

        Called at the start of each round before the new round's stratagems
        are decided. Keeps the transient buffs strictly one-round-scoped.
        """
        for u in army.units:
            u.transient_plus_one_to_wound_shooting = False
            u.transient_invuln_4 = False
            u.transient_minus_one_damage_taken = False
            u.transient_plus_one_to_wound_melee = False
            u.transient_plus_one_save = False
            u.transient_reroll_hits_shooting = False
            u.transient_assault_this_round = False
            # Go To Ground lasts "until the end of the phase"; clearing it with
            # the other per-round transient flags is a faithful approximation
            # (the 6++/cover buff is only read while the unit is shot, which
            # happens in the opponent's one Shooting phase per round).
            u.go_to_ground_active = False
            u.transient_fnp_5 = False
            u.transient_plus_one_to_hit_shooting = False
            u.transient_halve_damage = False
            u.transient_undying_legions_pulse = 0
            # ST-1 proper-keyword transient flags.
            u.transient_lethal_hits = False
            u.transient_sustained_hits = 0
            u.transient_reroll_wounds = False
            u.transient_reroll_wounds_ones = False
            # DRK-SKYSPLINTER-DISEMBARK: Rain of Cruelty disembark-turn
            # keyword grants. Set on disembark by `_disembark` when the
            # unit is DRUKHARI and the army's detachment is Skysplinter
            # Assault; cleared here at the next round start to match
            # the "until the end of the turn" rule wording. Cited as
            # `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark`.
            u.transient_lance_this_turn = False
            u.transient_ignores_cover_this_turn = False
            # DRK-NON-SKYSPLINTER-V1: Drukhari Combat Drugs — Adrenalight
            # lasts "until the start of your next Command phase." Clear the
            # per-round drug bonuses here so they only fire for the round in
            # which `_apply_combat_drugs` ran (Round 1 for Adrenalight; no
            # drug for Rounds 2+). Clearing fires before `_apply_combat_drugs`
            # in `_run_round`, so the net effect is: drug active for 1 round.
            # Cited as `simulator.combat_drugs`.
            if (
                u.profile.faction == "Drukhari"
                and u.profile.name in self._WYCH_CULT_UNITS
            ):
                u.combat_drug_extra_melee_attacks = 0
                u.combat_drug_melee_strength_bonus = 0
                u.combat_drug_toughness_bonus = 0
                u.combat_drug_move_bonus = 0.0
        # Per-army per-round stratagem state. Cabbalistic Empowerment boosts
        # this round's Doombolt damage; reset every round so the boost only
        # applies the round the stratagem fires. Putrid Detonation arms the
        # auto-success of Deadly Demise on DG VEHICLE/MONSTER deaths this
        # round. Plaguesurge is informational (no consumer hooked yet, kept
        # for future Contagion-range expansion).
        army.cabbalistic_doombolt_boost = False
        army.putrid_detonation_armed = False
        army.plaguesurge_active = False
        # AM Voice of Command — per-round stratagem widening flags. Flexible
        # Command (Combined Arms, 2 CP) extends Orders to SQUADRON units;
        # Inspired Command (Combined Arms, 1 CP) grants one bonus Order
        # this round. Both reset every round so the widening only applies
        # the round the stratagem fires.
        army.orders_eligible_squadron_this_round = False
        army.orders_extra_this_round = 0

    # Iter-4 A5 (faction-neutral AI heuristic): cap the number of detachment
    # stratagems any one army may fire per Command phase. 10e core has no
    # hard cap, but real-player CP economy averages 1-2 stratagems per
    # Command phase; without this cap, CP-rich detachments (DG Virulent
    # Vectorium, Necron Awakened Dynasty, Tau Mont'ka) stack 3-5+ buffs
    # at round start.
    #
    # iter44 STRATAGEM-CHAIN-V1: widened from 1 to 2. The single-strat
    # cap systematically undercounted faction power for stratagem-rich
    # detachments where real tournament play stacks 2-3 stratagems on
    # alpha-strike units (e.g. Drukhari Skysplinter Assault + Lightning-
    # Fast Reactions + Fire and Fade, or Marines Storm of Fire + Adaptive
    # Strategy). This first-stage widening permits two strats per phase
    # per army — the full 2-3+ stack is left as parking-lot work. The
    # `_strat_cap_reached` gate between dispatcher entries enforces the
    # ceiling; `_fire_stratagem`'s CP-affordability check inside each
    # `_try_X` helper means an unaffordable second slot is automatically
    # skipped and a later cheaper strat still gets the chance to fire.
    # Per-strat once-per-phase exclusion is implicit because each strat
    # appears in the dispatcher exactly once.
    # Cited as `simulator.stratagem_per_command_phase_cap`.
    DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE: int = 2

    def _apply_detachment_stratagems(self, army: Army, opponent: Army) -> None:
        """Round-start dispatcher for detachment-specific stratagems.

        Each detachment's stratagem tuple is iterated; the simulator's
        per-stratagem `_try_*` helpers consult the AI heuristic in
        `strategy.should_fire_stratagem` and, if green-lit, spend CP and
        apply the transient effect for the round.

        Iter-4 A5 cap: detachment stratagems fired through this dispatcher
        are limited to `DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE` (1) per
        army per Command phase. The counter is reset to 0 at the top of
        this method and incremented inside `_fire_stratagem` while the
        `_dispatching_detachment_stratagems` flag is set. Once the cap is
        reached, subsequent dispatcher entries short-circuit via
        `_strat_cap_reached`. Faction-neutral: every detachment's dispatch
        path runs through the same cap.

        Post 2026-05-15 fabrication audit (commit fa9a957): 11 stratagems
        previously dispatched here had no Wahapedia equivalent. The only
        survivors are Disgustingly Resilient (re-anchored to Virulent
        Vectorium at 2CP) and the two real Warhost (Aeldari) entries.
        Real per-detachment stratagem sets land in follow-up per-faction
        rebuild PRs.
        """
        det = army.resolve_detachment()
        if det is None or not det.stratagems:
            return
        strat_names = {s.name for s in det.stratagems}

        # Reset the per-Command-phase counter and arm the dispatch flag so
        # _fire_stratagem knows to increment the army's stratagem counter
        # for any firing during this call.
        army.stratagems_fired_this_command_phase = 0
        self._dispatching_detachment_stratagems = True
        try:
            # ----- Virulent Vectorium (Death Guard) -------------------------
            if not self._strat_cap_reached(army) and "Disgustingly Resilient" in strat_names:
                self._try_disgustingly_resilient(army, opponent)
            if not self._strat_cap_reached(army) and "Putrid Detonation" in strat_names:
                self._try_putrid_detonation(army, opponent)
            if not self._strat_cap_reached(army) and "Plaguesurge" in strat_names:
                self._try_plaguesurge(army, opponent)
            if not self._strat_cap_reached(army) and "Leechspore Eruption" in strat_names:
                self._try_leechspore_eruption(army, opponent)
            if not self._strat_cap_reached(army) and "Overwhelming Generosity" in strat_names:
                self._try_overwhelming_generosity(army, opponent)
            if not self._strat_cap_reached(army) and "Creeping Blight" in strat_names:
                self._try_creeping_blight(army, opponent)

            # ----- Warhost (Aeldari) ----------------------------------------
            if not self._strat_cap_reached(army) and "Lightning-Fast Reactions" in strat_names:
                self._try_lightning_fast_reactions(army, opponent)
            if not self._strat_cap_reached(army) and "Fire and Fade" in strat_names:
                self._try_fire_and_fade(army, opponent)
            if not self._strat_cap_reached(army) and "Skyborne Sanctuary" in strat_names:
                self._try_skyborne_sanctuary(army, opponent)
            if not self._strat_cap_reached(army) and "Feigned Retreat" in strat_names:
                self._try_feigned_retreat(army, opponent)
            if not self._strat_cap_reached(army) and "Blitzing Firepower" in strat_names:
                self._try_blitzing_firepower(army, opponent)
            if not self._strat_cap_reached(army) and "Webway Tunnel" in strat_names:
                self._try_webway_tunnel(army, opponent)

            # ----- Mont'ka (T'au Empire) — six real stratagems (#196) -------
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka.
            # Each dispatcher consults `should_fire_stratagem` for the AI gate,
            # spends CP via `_fire_stratagem`, then applies the transient effect
            # via the existing `transient_*` flag set on the chosen unit. Where
            # the canonical effect doesn't map to a flag (e.g. Pulse Onslaught's
            # enemy Move debuff), the dispatcher routes the value through the
            # nearest existing transient — see per-dispatcher APPROXIMATION notes.
            if not self._strat_cap_reached(army) and "Pinpoint Counter-Offensive" in strat_names:
                self._try_pinpoint_counter_offensive(army, opponent)
            if not self._strat_cap_reached(army) and "Aggressive Mobility" in strat_names:
                self._try_aggressive_mobility(army, opponent)
            if not self._strat_cap_reached(army) and "Focused Fire" in strat_names:
                self._try_focused_fire(army, opponent)
            if not self._strat_cap_reached(army) and "Combat Debarkation" in strat_names:
                self._try_combat_debarkation(army, opponent)
            if not self._strat_cap_reached(army) and "Pulse Onslaught" in strat_names:
                self._try_pulse_onslaught(army, opponent)
            if not self._strat_cap_reached(army) and "Counterfire Defence Systems" in strat_names:
                self._try_counterfire_defence_systems(army, opponent)

            # ----- Awakened Dynasty (Necrons) -------------------------------
            # Six real Protocol stratagems (#194). Two are catalogued-but-no-op
            # APPROXIMATIONs (Eternal Revenant, Vengeful Stars) — the simulator
            # has no model-resurrection or out-of-sequence shoot hook, so the
            # dispatchers below skip them entirely. The other four wire onto
            # existing or new transient_* flags.
            if not self._strat_cap_reached(army) and "Protocol of the Undying Legions" in strat_names:
                self._try_protocol_undying_legions(army, opponent)
            if not self._strat_cap_reached(army) and "Protocol of the Hungry Void" in strat_names:
                self._try_protocol_hungry_void(army, opponent)
            if not self._strat_cap_reached(army) and "Protocol of the Sudden Storm" in strat_names:
                self._try_protocol_sudden_storm(army, opponent)
            if not self._strat_cap_reached(army) and "Protocol of the Conquering Tyrant" in strat_names:
                self._try_protocol_conquering_tyrant(army, opponent)
            # Protocol of the Eternal Revenant + Protocol of the Vengeful Stars:
            # catalogued in the detachment so they show up in stratagems_for_army,
            # but the simulator has no clean hook to fire them. See
            # data/rule_citations.d/stratagems.json for the APPROXIMATION note.

            # ----- Grand Coven (Thousand Sons) ------------------------------
            # Six real Wahapedia stratagems (#193). Four are wired through the
            # transient-flag plumbing; two (Egotistical Power, Arcane Focus)
            # are flagged APPROXIMATION because their mechanics don't reduce
            # to an existing transient_*.
            if not self._strat_cap_reached(army) and "Psychic Dominion" in strat_names:
                self._try_psychic_dominion(army, opponent)
            if not self._strat_cap_reached(army) and "Destined by Fate" in strat_names:
                self._try_destined_by_fate(army, opponent)
            if not self._strat_cap_reached(army) and "Desecration of Worlds" in strat_names:
                self._try_desecration_of_worlds(army, opponent)
            if not self._strat_cap_reached(army) and "Devastating Sorcery" in strat_names:
                self._try_devastating_sorcery(army, opponent)
            # Egotistical Power and Arcane Focus are intentionally NOT dispatched
            # here — see _try_egotistical_power / _try_arcane_focus docstrings.

            # ----- Rubricae Phalanx (Thousand Sons) — six stratagems (iter15)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
            # Four wire onto existing transient_* flags (Inexorable Advance,
            # Infernal Fusillade, Implacable Guardians, Unwavering Phalanx);
            # two are catalogued-but-no-op APPROXIMATIONs (Ardent Automata —
            # no Fall-Back-this-turn transient; Revenge of the Rubricae — no
            # out-of-sequence-shoot-on-PSYKER-death hook).
            if not self._strat_cap_reached(army) and "Inexorable Advance" in strat_names:
                self._try_inexorable_advance(army, opponent)
            if not self._strat_cap_reached(army) and "Infernal Fusillade" in strat_names:
                self._try_infernal_fusillade(army, opponent)
            if not self._strat_cap_reached(army) and "Implacable Guardians" in strat_names:
                self._try_implacable_guardians(army, opponent)
            if not self._strat_cap_reached(army) and "Unwavering Phalanx" in strat_names:
                self._try_unwavering_phalanx(army, opponent)
            # Ardent Automata + Revenge of the Rubricae catalogued in
            # RUBRICAE_PHALANX_STRATAGEMS for the auditor + stratagems_for_army
            # listing; dispatchers intentionally no-op (see docstrings).

            # ----- War Horde (Orks) — six real stratagems (iter-1 B1) ------
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
            # Insane Bravery is catalogued-but-no-op APPROXIMATION (no per-unit
            # battleshock-immunity hook). The other five wire onto existing
            # transient_* flags via the standard pattern.
            if not self._strat_cap_reached(army) and "Power Of The WAAAGH!" in strat_names:
                self._try_power_of_the_waaagh(army, opponent)
            if not self._strat_cap_reached(army) and "Mob Up" in strat_names:
                self._try_mob_up(army, opponent)
            if not self._strat_cap_reached(army) and "Big Krumpin'" in strat_names:
                self._try_big_krumpin(army, opponent)
            if not self._strat_cap_reached(army) and "Tellyporta" in strat_names:
                self._try_tellyporta(army, opponent)
            if not self._strat_cap_reached(army) and "Da Biggest Boss" in strat_names:
                self._try_da_biggest_boss(army, opponent)
            # Insane Bravery — catalogued in WAR_HORDE_STRATAGEMS for the
            # auditor + stratagems_for_army listing, but the dispatcher is a
            # no-op (no per-unit battleshock-immunity transient flag exists).

            # ----- Shield Host (Adeptus Custodes) — six real stratagems (iter-8)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
            # Five wire onto existing transient_* flags; Vigilance Eternal is
            # a no-op APPROXIMATION (sticky-objective hook is per-detachment,
            # not per-stratagem-fire). Replaces the iter-0 zero-stratagem
            # state where Custodes burned 5/7 strat fires on Command Re-Roll.
            if not self._strat_cap_reached(army) and "Arcane Genetic Alchemy" in strat_names:
                self._try_arcane_genetic_alchemy(army, opponent)
            if not self._strat_cap_reached(army) and "Unwavering Sentinels" in strat_names:
                self._try_unwavering_sentinels(army, opponent)
            if not self._strat_cap_reached(army) and "Multipotentiality" in strat_names:
                self._try_multipotentiality(army, opponent)
            if not self._strat_cap_reached(army) and "Archaeotech Munitions" in strat_names:
                self._try_archaeotech_munitions(army, opponent)
            if not self._strat_cap_reached(army) and "Avenge the Fallen" in strat_names:
                self._try_avenge_the_fallen(army, opponent)
            # Vigilance Eternal — catalogued in SHIELD_HOST_STRATAGEMS for the
            # auditor + stratagems_for_army listing, but the dispatcher is a
            # no-op APPROXIMATION (sticky-objective mechanism is per-detachment-
            # flag-gated, not per-stratagem-fire).

            # ----- Needgaard Oathband (Leagues of Votann) — two verified stratagems
            # (VOTANN-DIAG-2: replaced five fabricated stratagems with real ones
            # per Wahapedia https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
            # VOTANN-AUDIT-V1: Huntr's Mark removed — not in BSData v10.6.0 and
            # citation was unverifiable. Was the +7.8pt overshoot driver.)
            if not self._strat_cap_reached(army) and "Ancestral Sentence" in strat_names:
                self._try_ancestral_sentence(army, opponent)
            if not self._strat_cap_reached(army) and "Void Hardened" in strat_names:
                self._try_void_hardened(army, opponent)

            # ----- Gladius Task Force (Adeptus Astartes) — six real strats (iter-12)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
            # Replaces the iter-0 zero-stratagem state where Marines burned every
            # strat fire on Command Re-Roll (universal Core). Closes
            # docs/AUDIT_PARITY.md fix #1 (largest 0/6 gap — Marines is 134
            # units / the most-used codex). All six dispatchers follow the
            # Shield Host / Oathband pattern: route through the closest
            # existing transient_* flag and document the gap.
            if not self._strat_cap_reached(army) and "Storm of Fire" in strat_names:
                self._try_storm_of_fire(army, opponent)
            if not self._strat_cap_reached(army) and "Armour of Contempt" in strat_names:
                self._try_armour_of_contempt(army, opponent)
            if not self._strat_cap_reached(army) and "Squad Tactics" in strat_names:
                self._try_squad_tactics(army, opponent)
            if not self._strat_cap_reached(army) and "Only In Death Does Duty End" in strat_names:
                self._try_only_in_death_does_duty_end(army, opponent)
            if not self._strat_cap_reached(army) and "Honour the Chapter" in strat_names:
                self._try_honour_the_chapter(army, opponent)
            if not self._strat_cap_reached(army) and "Adaptive Strategy" in strat_names:
                self._try_adaptive_strategy(army, opponent)

            # ----- Combined Arms (Astra Militarum) — six real strats (iter-14)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
            # Closes the AM 0/6 detachment-stratagem gap (docs/AUDIT_PARITY.md).
            # Three wire onto Voice of Command Order economy (Coordinated
            # Action, Flexible Command, Inspired Command), three onto
            # existing transient_* flags (Fields of Fire, Stalwart Protector),
            # and Reinforcements! is a no-op APPROXIMATION (no respawn hook).
            if not self._strat_cap_reached(army) and "Coordinated Action" in strat_names:
                self._try_coordinated_action(army, opponent)
            if not self._strat_cap_reached(army) and "Flexible Command" in strat_names:
                self._try_flexible_command(army, opponent)
            if not self._strat_cap_reached(army) and "Fields of Fire" in strat_names:
                self._try_fields_of_fire(army, opponent)
            if not self._strat_cap_reached(army) and "Inspired Command" in strat_names:
                self._try_inspired_command(army, opponent)
            if not self._strat_cap_reached(army) and "Stalwart Protector" in strat_names:
                self._try_stalwart_protector(army, opponent)

            # ----- ST-2 wave 3 — one stratagem per under-performing faction
            # All five route the offensive value through an existing
            # transient_* flag (transient_plus_one_to_wound_melee for melee,
            # transient_reroll_hits_shooting for ranged). Faction-gated via
            # the detachment-membership check above (strat_names already
            # filters to the active detachment's stratagem set).
            if not self._strat_cap_reached(army) and "Apoplectic Frenzy" in strat_names:
                self._try_apoplectic_frenzy(army, opponent)
            if not self._strat_cap_reached(army) and "Denizens of the Warp" in strat_names:
                self._try_denizens_of_the_warp(army, opponent)
            if not self._strat_cap_reached(army) and "Empyric Channelling" in strat_names:
                self._try_empyric_channelling(army, opponent)
            if not self._strat_cap_reached(army) and "Cult Ambush" in strat_names:
                self._try_cult_ambush(army, opponent)
            if not self._strat_cap_reached(army) and "Profane Zeal" in strat_names:
                self._try_profane_zeal(army, opponent)

            # ----- DAEMONS-STRATAGEMS-V1 (wave 53) — Daemonic Incursion +
            # per-god stratagem sets. All route through existing transient_*
            # flags. Strat_names gate ensures only the correct detachment fires
            # each entry (Draught of Terror / Warp Surge / Daemonic
            # Invulnerability are in DAEMONIC_INCURSION_STRATAGEMS shared by
            # all five Daemons detachments; Blood Begets Skulls + Wrath
            # Undeniable are BLOOD_LEGION only; Seeping Virulence + Foetid
            # Resurgence are PLAGUE_LEGION only; Archagonists is
            # LEGION_OF_EXCESS only; Flickering Reality is
            # SCINTILLATING_LEGION only).
            if not self._strat_cap_reached(army) and "Draught of Terror" in strat_names:
                self._try_draught_of_terror(army, opponent)
            if not self._strat_cap_reached(army) and "Warp Surge" in strat_names:
                self._try_warp_surge(army, opponent)
            if not self._strat_cap_reached(army) and "Daemonic Invulnerability" in strat_names:
                self._try_daemonic_invulnerability(army, opponent)
            if not self._strat_cap_reached(army) and "Blood Begets Skulls" in strat_names:
                self._try_blood_begets_skulls(army, opponent)
            if not self._strat_cap_reached(army) and "Wrath Undeniable" in strat_names:
                self._try_wrath_undeniable(army, opponent)
            if not self._strat_cap_reached(army) and "Seeping Virulence" in strat_names:
                self._try_seeping_virulence(army, opponent)
            if not self._strat_cap_reached(army) and "Foetid Resurgence" in strat_names:
                self._try_foetid_resurgence(army, opponent)
            if not self._strat_cap_reached(army) and "Archagonists" in strat_names:
                self._try_archagonists(army, opponent)
            if not self._strat_cap_reached(army) and "Flickering Reality" in strat_names:
                self._try_flickering_reality(army, opponent)
        finally:
            # Always drop the dispatch flag — Tank Shock / Counter-Offensive /
            # Command Re-Roll fire out-of-band via _fire_stratagem and MUST
            # NOT increment the per-Command-phase counter (those are Core
            # Stratagems on per-trigger hooks, not detachment-stratagem
            # round-start spends). Heroic Intervention is a free core
            # CHARACTER ability — see _do_heroic_intervention.
            self._dispatching_detachment_stratagems = False

    def _strat_cap_reached(self, army: Army) -> bool:
        """Returns True iff `army` has already fired its per-Command-phase
        quota of detachment stratagems. Faction-neutral guard used by
        `_apply_detachment_stratagems` to short-circuit subsequent
        dispatcher entries once the army hits the cap.
        """
        return (
            army.stratagems_fired_this_command_phase
            >= self.DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE
        )

    # ----- target-selection helpers used by the dispatchers --------------

    def _highest_threat_enemy(self, opponent: Army, restrict_uids=None):
        """Pick the alive enemy unit with the highest role-weighted threat.

        Same role-weighting as `_apply_psychic_phase` so Doombolt and any
        future MW-payload stratagem agree on what counts as a worthwhile
        target — heavy / shooty / wounded enemies first, hordes last.

        Battle-shocked enemies are excluded — 10e core forbids using
        Stratagems to affect a Battle-shocked unit regardless of side.
        Cited as `simulator.battleshock` (task #168).

        `restrict_uids` (optional set): if provided, only candidate units
        whose uid is in this set are considered. Used by Votann's
        Warrior Pride / Wrath of the Ancestors stratagem dispatchers to
        require a Judgement-Token-bearing target per the codex rule
        (VOTANN-DIAG 2026-05-23).
        """
        from .roles import classify
        ROLE_THREAT = {"HEAVY": 3.0, "SHOOTY": 2.0, "DUAL": 1.5,
                       "MELEE": 1.0, "SUPPORT": 1.2, "HORDE": 0.6}
        targets = [
            u for u in opponent.alive_units
            if u.uid not in self._battleshocked_this_round
        ]
        if restrict_uids is not None:
            targets = [u for u in targets if u.uid in restrict_uids]
        if not targets:
            return None

        def _score(u):
            role = classify(u.profile)
            return ROLE_THREAT.get(role, 1.0) * u.current_health
        return max(targets, key=_score)

    @staticmethod
    def _unit_matches_filter(unit, keyword: str = "", faction: str = "") -> bool:
        """Test a unit against the {keyword, faction} stratagem-target filter.

        We check the keyword against `profile.unit_keywords` AND the faction
        against `profile.faction` because BSData parsing emits faction tags
        (e.g. "Aeldari", "Death Guard") on the `faction` field rather than
        as unit keywords. The dispatcher accepts either signal so we don't
        leak buffs onto units the detachment shouldn't include.
        """
        if not keyword and not faction:
            return True
        if keyword and keyword in (unit.profile.unit_keywords or ()):
            return True
        if faction and (unit.profile.faction or "").lower() == faction.lower():
            return True
        return False

    def _highest_dpa_unit(self, army: Army, keyword: str = "", faction: str = ""):
        """Pick the alive friendly unit with the highest melee+ranged DPA.

        Optional `keyword`/`faction` filter restricts to units carrying
        that keyword (e.g. PSYKER) or belonging to that faction
        (e.g. "Aeldari") so a Warhost army with stray non-Aeldari
        allies still targets the right detachment. See
        `_unit_matches_filter` for the lookup logic.

        Battle-shocked units are excluded — 10e core: "While a unit is
        Battle-shocked, ... you cannot use Stratagems to affect that
        unit." Cited as `simulator.battleshock` (task #168).
        """
        candidates = [
            u for u in army.alive_units
            if self._unit_matches_filter(u, keyword=keyword, faction=faction)
            and u.uid not in self._battleshocked_this_round
        ]
        if not candidates:
            return None

        def _dpa(u):
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            melee = (p.melee_attacks * p.melee_hit_probability
                     * (p.melee_damage_per_shot or 0.0))
            return ranged + melee
        return max(candidates, key=_dpa)

    def _most_vulnerable_unit(self, army: Army, keyword: str = "", faction: str = ""):
        """Pick the alive friendly unit most likely to benefit from a
        defensive stratagem — wounded + high-value.

        Score: (points_cost) × (1.0 - current_health/max_health). A unit at
        full HP gets 0 (no buff needed); a Knight at 30% HP scores very
        high. Restricted to units matching the keyword/faction filter.

        Battle-shocked units are excluded — 10e core: "While a unit is
        Battle-shocked, ... you cannot use Stratagems to affect that
        unit." Cited as `simulator.battleshock` (task #168).
        """
        candidates = [
            u for u in army.alive_units
            if self._unit_matches_filter(u, keyword=keyword, faction=faction)
            and u.uid not in self._battleshocked_this_round
        ]
        if not candidates:
            return None

        def _vulnerability(u):
            hp_max = max(1.0, u.profile.health)
            hp_lost = 1.0 - (u.current_health / hp_max)
            return float(u.profile.points_cost) * hp_lost
        scored = max(candidates, key=_vulnerability)
        # Only return if there's meaningful vulnerability — otherwise fall
        # back to highest points-cost frontline unit (the canonical "save
        # the Marneus from a stratagem" target).
        if _vulnerability(scored) > 0:
            return scored
        return max(candidates, key=lambda u: float(u.profile.points_cost))

    # ----- per-stratagem dispatchers -------------------------------------
    # Post 2026-05-15 fabrication audit (commit fa9a957): 11 dispatchers were
    # removed alongside their fabricated stratagem constants. The three
    # survivors below correspond to real Wahapedia entries.

    def _try_disgustingly_resilient(self, army: Army, opponent: Army) -> None:
        """Disgustingly Resilient (Virulent Vectorium, 2 CP): -1 damage taken
        on a DEATH GUARD INFANTRY or DEATH GUARD CHARACTER unit for the
        round. Picks the most vulnerable eligible unit; if none qualifies
        the stratagem does not fire (per F-DG-1, iter 1: real Wahapedia
        scope is DG INFANTRY / DG CHARACTER only — VEHICLEs and MONSTERs
        like Plagueburst Crawler / Foetid Bloat-Drone / Plague Hulk are
        NOT eligible). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium
        """
        # Eligible: alive DG unit with INFANTRY or CHARACTER keyword and
        # NOT a VEHICLE or MONSTER (a real DG datasheet may list both
        # CHARACTER and MONSTER — e.g. Mortarion — but the stratagem
        # text restricts the buff to the INFANTRY/CHARACTER half).
        def _eligible(u) -> bool:
            if (u.profile.faction or "") != "Death Guard":
                return False
            kw = set(u.profile.unit_keywords or ())
            if "VEHICLE" in kw or "MONSTER" in kw:
                return False
            return "INFANTRY" in kw or "CHARACTER" in kw

        candidates = [
            u for u in army.alive_units
            if _eligible(u) and u.uid not in self._battleshocked_this_round
        ]
        if not candidates:
            return

        def _vulnerability(u):
            hp_max = max(1.0, u.profile.health)
            hp_lost = 1.0 - (u.current_health / hp_max)
            return float(u.profile.points_cost) * hp_lost

        target = max(candidates, key=_vulnerability)
        if _vulnerability(target) <= 0:
            target = max(candidates, key=lambda u: float(u.profile.points_cost))
        ctx = {"target": target}
        if not should_fire_stratagem(army, DISGUSTINGLY_RESILIENT, ctx):
            return
        if not self._fire_stratagem(army, DISGUSTINGLY_RESILIENT):
            return
        self._set_transient_squad(target, "transient_minus_one_damage_taken")

    def _try_putrid_detonation(self, army: Army, opponent: Army) -> None:
        """Putrid Detonation (Virulent Vectorium, 1 CP): auto-success on the
        Deadly Demise d6 roll for the round. Fires when the army has at
        least one DG VEHICLE or DG MONSTER on the table with deadly_demise > 0
        (otherwise the buff is wasted). APPROXIMATION: real text targets one
        specific destruction; we arm the flag for the round and any
        qualifying DG VEHICLE / MONSTER death auto-detonates."""
        # Eligible donor: any alive DG VEHICLE/MONSTER with deadly_demise > 0.
        candidate = None
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "VEHICLE" not in kw and "MONSTER" not in kw:
                continue
            if (u.profile.faction or "") != "Death Guard":
                continue
            if (getattr(u.profile, "deadly_demise", 0) or 0) <= 0:
                continue
            candidate = u
            break
        if candidate is None:
            return
        ctx = {"target": candidate}
        if not should_fire_stratagem(army, PUTRID_DETONATION, ctx):
            return
        if not self._fire_stratagem(army, PUTRID_DETONATION):
            return
        army.putrid_detonation_armed = True

    def _try_plaguesurge(self, army: Army, opponent: Army) -> None:
        """Plaguesurge (Virulent Vectorium, 2 CP): +3" to Contagion Range
        until next Command phase. APPROXIMATION: contagion radius is hard-
        coded at 6" elsewhere; the flag is set for the round but not
        consumed yet. The CP spend still fires + emits the StratagemFired
        event so the AI's CP accounting stays honest."""
        # Need a DG WARLORD on the battlefield to target.
        warlord = None
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "CHARACTER" in kw and (u.profile.faction or "") == "Death Guard":
                warlord = u
                break
        if warlord is None:
            return
        ctx = {"target": warlord}
        if not should_fire_stratagem(army, PLAGUESURGE, ctx):
            return
        if not self._fire_stratagem(army, PLAGUESURGE):
            return
        army.plaguesurge_active = True

    def _apply_mortal_wounds(self, target, count, psychic=False):
        """Allocate `count` mortal wounds to ``target``'s unit, carrying excess
        across models per 10e core. Unlike normal attack damage (where a
        destroyed model's excess is lost), mortal wounds keep allocating to the
        next model of the same unit until all are spent or the unit is
        destroyed: "Excess damage from mortal wounds is not lost if the damage
        can be allocated to another model. Instead, keep allocating damage to
        another model in the target unit until either all the damage has been
        allocated or the target unit is destroyed." SwegHammer models one Unit
        per model, so the rest of the codex unit is the target's same-`squad_id`
        siblings. Feel No Pain is rolled per mortal wound (`receive_damage(1.0)`
        applies one FNP roll), matching the per-point loop the prior single-call
        `receive_damage(count)` used — only the destination now moves across
        models. ``psychic`` is plumbed through so Magnus's Impossible Form -1
        damage clamp is correctly skipped for [PSYCHIC] mortal wounds. Returns
        the list of models destroyed (in allocation order) so callers can fan
        out kill handling. A lone model (squad_id < 0) takes the wounds with no
        spill (excess simply ends with the model's death). Cited as
        `simulator.mortal_wound_spillover`.
        """
        remaining = int(round(count))
        killed: List["Unit"] = []
        if remaining <= 0 or target is None:
            return killed
        model = target
        sid = getattr(target, "squad_id", -1)
        siblings = None
        while remaining > 0:
            if model is None or not model.is_alive:
                if sid is None or sid < 0:
                    break  # lone model already dead — nothing to carry to
                if siblings is None:
                    army = getattr(target, "army_ref", None)
                    siblings = (
                        [u for u in army.units
                         if getattr(u, "squad_id", -1) == sid
                         and getattr(u, "embarked_in", None) is None]
                        if army is not None else []
                    )
                model = next((u for u in siblings if u.is_alive), None)
                if model is None:
                    break  # whole unit destroyed — remaining mortals lost
            was_alive = model.is_alive
            model.receive_damage(1.0, bonus_fnp=model.profile.fnp, psychic=psychic)
            remaining -= 1
            if was_alive and not model.is_alive:
                killed.append(model)
        return killed

    def _try_leechspore_eruption(self, army: Army, opponent: Army) -> None:
        """Leechspore Eruption (Virulent Vectorium, 1 CP): roll D6-per-wound-
        lost on a damaged DG model; each 5+ deals 1 MW to a nearby enemy
        (cap 6) AND heals 1 lost wound on the model (cap 6).

        Implementation: pick a DG model with the most wounds lost; resolve
        the dice deterministically by taking the expected value (each D6 has
        2/6 = 33.3% chance of a 5+, so floor(wounds_lost * 1/3) mortals are
        applied; matches the simulator's other 'median dice' approximations).
        Heal the same number on the DG model. Target = nearest enemy within
        3" of the DG model; skip if none."""
        # Pick the DG model with the most wounds lost (current_health < max).
        target = self._most_vulnerable_unit(
            army, keyword="DEATH GUARD", faction="Death Guard",
        )
        if target is None:
            return
        wounds_lost = max(0.0, target.profile.health - target.current_health)
        if wounds_lost < 1.0:
            return
        # Find nearest enemy within 3" — required for the targeting clause.
        nearest = None
        nearest_dist = 999.0
        for e in opponent.alive_units:
            d = _distance(target.position, e.position)
            if d <= 3.0 and d < nearest_dist:
                nearest = e
                nearest_dist = d
        if nearest is None:
            return
        ctx = {"target": target, "enemy": nearest}
        if not should_fire_stratagem(army, LEECHSPORE_ERUPTION, ctx):
            return
        if not self._fire_stratagem(army, LEECHSPORE_ERUPTION):
            return
        # Median dice: each D6 has 2/6 chance of a 5+, so apply
        # round(wounds_lost * 2/6) mortal wounds, capped at 6, matching the
        # simulator's other 'median D3/D6' deterministic conversions.
        mortals = min(6, int(round(wounds_lost * 2.0 / 6.0)))
        heal = mortals  # cap 6 already enforced
        if mortals > 0:
            # Mortal wounds spill across the target unit's models (10e core);
            # see _apply_mortal_wounds. Cited as simulator.mortal_wound_spillover.
            for _m in self._apply_mortal_wounds(nearest, mortals):
                self._emit(UnitKilled(unit_uid=_m.uid))
        if heal > 0:
            target.current_health = min(
                target.profile.health, target.current_health + float(heal),
            )

    def _try_overwhelming_generosity(self, army: Army, opponent: Army) -> None:
        """Overwhelming Generosity (Virulent Vectorium, 1 CP): re-roll the
        number-of-attacks roll for a DG CHARACTER unit's ranged attacks vs a
        visible enemy. APPROXIMATION: we don't model per-weapon attack-count
        dice (BSData parses attacks as a fixed integer at mapper time), so
        the simulator routes the effect through transient_reroll_hits_shooting
        on the DG CHARACTER unit (re-roll failed hits on its shoot for the
        round) — a more conservative buff than the real text's full-reroll-
        attack-count, since attack-count rerolls average ~10% extra shots
        while hit rerolls average ~17% extra hits on 4+ BS.

        VISIBILITY GATE (iter-5 fix per Wahapedia "Select one enemy unit
        VISIBLE to your unit"): the chosen DG CHARACTER must have line of
        sight to at least one alive enemy within its ranged weapon's range.
        Without this gate, OG was firing R1 at 0.83/battle even though the
        firing CHARACTER had no viable target on a 60×44 board with
        terrain — wasting 1 CP on a buff that produced no R1 damage.
        See `docs/AUTO_LOOP_ITER5_DG_UNSAMPLED.md` for the diagnostic."""
        # Rank friendly DG CHARACTER candidates by ranged DPA (highest first).
        # We need to iterate (not just pick the best) so that if the top-DPA
        # CHARACTER has no LoS, we can fall through to the next candidate
        # rather than wasting the strat fire on a blind shooter.
        candidates: list = []
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "CHARACTER" not in kw:
                continue
            if (u.profile.faction or "") != "Death Guard":
                continue
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            if ranged <= 0.0:
                continue
            candidates.append((ranged, u))
        if not candidates:
            return
        candidates.sort(key=lambda pair: pair[0], reverse=True)

        # Wahapedia: "Select one enemy unit visible to your unit." Walk the
        # candidates and pick the first DG CHARACTER that actually has at
        # least one alive enemy in shoot range AND with LoS. Without LoS,
        # the stratagem has no legal target — skip firing entirely (no CP
        # spent), matching the real-meta behaviour where DG players cannot
        # fire OG R1 when their CHARACTER is deep in their deployment zone
        # with no enemies visible across the board.
        candidate = None
        for _, cand in candidates:
            rng = float(cand.profile.range_inches or 0.0)
            if rng <= 0.0:
                continue
            for enemy in opponent.alive_units:
                if _distance(cand.position, enemy.position) > rng:
                    continue
                if not self.map.has_line_of_sight(
                    cand.position, enemy.position,
                    attacker_keywords=cand.profile.unit_keywords or (),
                    target_keywords=enemy.profile.unit_keywords or (),
                ):
                    continue
                candidate = cand
                break
            if candidate is not None:
                break
        if candidate is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": candidate, "target": target}
        if not should_fire_stratagem(army, OVERWHELMING_GENEROSITY, ctx):
            return
        if not self._fire_stratagem(army, OVERWHELMING_GENEROSITY):
            return
        self._set_transient_squad(candidate, "transient_reroll_hits_shooting")

    def _try_creeping_blight(self, army: Army, opponent: Army) -> None:
        """Creeping Blight (Virulent Vectorium, 1 CP): re-roll Hit AND Wound
        rolls on a DG INFANTRY unit's ranged attacks vs Afflicted enemies.
        APPROXIMATION: we don't model Afflicted enemy state, so we route the
        effect through transient_reroll_hits_shooting AND
        transient_reroll_wounds on the DG INFANTRY unit (the full hit+wound
        reroll grant the codex describes; ST-1 added the wound leg via the
        new transient_reroll_wounds flag — previously only the hit leg
        landed). Picks the highest-DPA friendly DG INFANTRY that has the
        gate's other prerequisite (not yet shot this phase, which is
        implicit at round-start dispatch)."""
        candidate = None
        best_dpa = 0.0
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "INFANTRY" not in kw:
                continue
            if (u.profile.faction or "") != "Death Guard":
                continue
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            if ranged > best_dpa:
                best_dpa = ranged
                candidate = u
        if candidate is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": candidate, "target": target}
        if not should_fire_stratagem(army, CREEPING_BLIGHT, ctx):
            return
        if not self._fire_stratagem(army, CREEPING_BLIGHT):
            return
        self._set_transient_squad(candidate, "transient_reroll_hits_shooting")
        self._set_transient_squad(candidate, "transient_reroll_wounds")

    def _try_lightning_fast_reactions(self, army: Army, opponent: Army) -> None:
        """Lightning-Fast Reactions (Warhost): +1 save on the most
        vulnerable AELDARI unit for the round. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        target = self._most_vulnerable_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, LIGHTNING_FAST_REACTIONS, ctx):
            return
        if not self._fire_stratagem(army, LIGHTNING_FAST_REACTIONS):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    def _try_fire_and_fade(self, army: Army, opponent: Army) -> None:
        """Fire and Fade (Warhost): re-roll failed hits on a friendly
        AELDARI unit's shooting for the round (approximating the canonical
        shoot-then-move-6" via offensive uplift). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        attacker = self._highest_dpa_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, FIRE_AND_FADE, ctx):
            return
        if not self._fire_stratagem(army, FIRE_AND_FADE):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    def _try_skyborne_sanctuary(self, army: Army, opponent: Army) -> None:
        """Skyborne Sanctuary (Warhost, 1 CP). Real rule: end of Fight
        phase, an AELDARI INFANTRY unit not in engagement range and wholly
        within 6" of a friendly AELDARI TRANSPORT can embark within it.
        APPROXIMATION: SwegHammer's stratagem dispatcher fires at round
        start, not end-of-fight, and re-embark mid-battle isn't wired into
        the activation loop. We route the defensive value through the
        existing `transient_plus_one_save` flag on the most vulnerable
        AELDARI unit for the round, which captures the "shelter the
        wounded unit" use case the codex stratagem most often serves.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        target = self._most_vulnerable_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, SKYBORNE_SANCTUARY, ctx):
            return
        if not self._fire_stratagem(army, SKYBORNE_SANCTUARY):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    def _try_feigned_retreat(self, army: Army, opponent: Army) -> None:
        """Feigned Retreat (Warhost, 1 CP). Real rule: your Movement
        phase, just after an AELDARI INFANTRY unit Falls Back — until
        end of turn the unit can shoot and declare a charge despite
        Falling Back. APPROXIMATION: the round-start dispatcher fires
        before any Fall Back has been resolved this round, so we route
        the offensive value through `transient_assault_this_round` on
        the highest-DPA AELDARI unit (closest single-flag stand-in for
        "lets the unit reposition AND shoot the same round"). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        attacker = self._highest_dpa_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, FEIGNED_RETREAT, ctx):
            return
        if not self._fire_stratagem(army, FEIGNED_RETREAT):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_blitzing_firepower(self, army: Army, opponent: Army) -> None:
        """Blitzing Firepower (Warhost, 1 CP). Real rule: your Shooting
        phase, when an AELDARI unit is selected to shoot — until end of
        phase its ranged weapons gain [SUSTAINED HITS 1] vs targets
        within 12" (or improve to 5+ Critical Hit if already having the
        ability). ST-1: now routes through the proper
        `transient_sustained_hits` accumulator (additive on top of any
        per-weapon SUSTAINED HITS already on the profile, matching the
        codex stacking rule). The 12" range gate and the 5+ Critical
        Hit upgrade for weapons already carrying SUSTAINED HITS X are
        still not modelled. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        attacker = self._highest_dpa_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, BLITZING_FIREPOWER, ctx):
            return
        if not self._fire_stratagem(army, BLITZING_FIREPOWER):
            return
        attacker.transient_sustained_hits += 1

    def _try_webway_tunnel(self, army: Army, opponent: Army) -> None:
        """Webway Tunnel (Warhost, 1 CP). Real rule: end of opponent's
        Fight phase, an AELDARI INFANTRY unit wholly within 9" of a
        battlefield edge and not in engagement range may enter Strategic
        Reserves. APPROXIMATION: SwegHammer's reserve queue has no
        mid-battle re-entry hook, so the "pull the unit off the table
        to avoid the next attack" defensive payoff is routed through
        the existing `transient_plus_one_save` flag on the most
        vulnerable AELDARI unit for the round. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        target = self._most_vulnerable_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, WEBWAY_TUNNEL, ctx):
            return
        if not self._fire_stratagem(army, WEBWAY_TUNNEL):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    # ----- Mont'ka (T'au Empire) per-stratagem dispatchers (#196) --------
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka

    def _try_pinpoint_counter_offensive(self, army: Army, opponent: Army) -> None:
        """Pinpoint Counter-Offensive (1 CP). Real rule: when a T'AU EMPIRE
        unit is destroyed, until end of phase, other friendly T'AU EMPIRE
        units re-roll Hit rolls against the enemy unit responsible.
        APPROXIMATION: round-start dispatch can't observe a fresh kill, so
        we gate on the AI heuristic (general 'fire when shooty unit will
        actually swing') and grant a flat transient hit re-roll on the
        highest-DPA T'au unit for the round."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PINPOINT_COUNTER_OFFENSIVE, ctx):
            return
        if not self._fire_stratagem(army, PINPOINT_COUNTER_OFFENSIVE):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    def _try_aggressive_mobility(self, army: Army, opponent: Army) -> None:
        """Aggressive Mobility (1 CP). Real rule: in your Movement phase,
        replace an Advance roll with a flat +6" Move and treat the unit as
        having Advanced — its ranged weapons would then need [ASSAULT] (or
        Killing Blow rounds 1-3) to shoot. SwegHammer collapses the
        movement-replacement clause and routes the value as a transient
        [ASSAULT] grant for the round (same flag Matchless Agility uses).
        Gate: pick the highest-DPA T'au shooter."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, AGGRESSIVE_MOBILITY, ctx):
            return
        if not self._fire_stratagem(army, AGGRESSIVE_MOBILITY):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_focused_fire(self, army: Army, opponent: Army) -> None:
        """Focused Fire (1 CP). Real rule: in your Shooting phase, two T'au
        units selecting the same target gain +1 AP for that shoot. Cannot
        be used in rounds 4-5. APPROXIMATION: the simulator's flag set has
        no AP-improvement transient, so we route the offensive value
        through `transient_plus_one_to_hit_shooting` on the highest-DPA
        T'au shooter (it's the same swing direction — more landed wounds
        per shoot). Round gate skipped at round-start dispatch."""
        if self._current_round >= 4:
            return     # canonical rounds 1-3 only
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, FOCUSED_FIRE, ctx):
            return
        if not self._fire_stratagem(army, FOCUSED_FIRE):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_hit_shooting")

    def _try_combat_debarkation(self, army: Army, opponent: Army) -> None:
        """Combat Debarkation (1 CP). Real rule: a T'au unit that
        disembarked this turn re-rolls Wound rolls against the closest
        enemy unit in its shooting. APPROXIMATION: we don't track
        'disembarked-this-turn' at stratagem-dispatch time, so the gate
        is widened to any T'au shooter. ST-1: now routes through
        `transient_reroll_wounds` (the proper full-wound-reroll flag —
        the citation says "re-roll the Wound roll"), replacing the
        previous mis-mapping onto `transient_reroll_hits_shooting`
        which lifted hit-roll re-rolls instead of wound-roll re-rolls
        and so was the wrong stat altogether."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, COMBAT_DEBARKATION, ctx):
            return
        if not self._fire_stratagem(army, COMBAT_DEBARKATION):
            return
        self._set_transient_squad(attacker, "transient_reroll_wounds")

    def _try_pulse_onslaught(self, army: Army, opponent: Army) -> None:
        """Pulse Onslaught (2 CP). Real rule: target an enemy unit; until
        the end of the phase its Move is reduced by 2 and its Charge /
        Advance rolls are reduced by 2. TODO: APPROXIMATION — SwegHammer
        has no enemy-movement-debuff transient, so we route the offensive
        value through `transient_plus_one_to_hit_shooting` on the
        firing T'au unit (models the 'shaken' enemy being easier to hit).
        Wire a proper enemy move debuff when the simulator gains the
        infrastructure."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PULSE_ONSLAUGHT, ctx):
            return
        if not self._fire_stratagem(army, PULSE_ONSLAUGHT):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_hit_shooting")

    def _try_counterfire_defence_systems(self, army: Army, opponent: Army) -> None:
        """Counterfire Defence Systems (2 CP). Real rule: in your
        opponent's Shooting phase, after targets selected, a T'au unit
        being shot at gets -1 Damage for the phase. Maps cleanly to
        `transient_minus_one_damage_taken` on the most vulnerable T'au
        unit for the round (matching how Disgustingly Resilient
        routes its DG defensive payload)."""
        target = self._most_vulnerable_unit(
            army, faction="T'au Empire",
        )
        if target is None:
            target = self._most_vulnerable_unit(army, faction="Tau Empire")
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, COUNTERFIRE_DEFENCE_SYSTEMS, ctx):
            return
        if not self._fire_stratagem(army, COUNTERFIRE_DEFENCE_SYSTEMS):
            return
        self._set_transient_squad(target, "transient_minus_one_damage_taken")

    # ----- Awakened Dynasty (Necrons) protocol dispatchers ---------------
    # Six real Protocol stratagems (#194). Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
    # Of the six, two are catalogued-but-no-op APPROXIMATIONs because the
    # effect ("return a destroyed CHARACTER" / "out-of-sequence shoot at
    # the unit that just destroyed a friendly Necron") has no clean hook
    # in the current simulator. Eligible-but-not-fired so any future
    # extension can wire them without touching the citation file.

    def _is_led_unit(self, unit) -> bool:
        """Approximation: a NECRONS unit counts as 'led by a CHARACTER' for
        the protocol stratagems' optional uplift if any alive friendly
        CHARACTER is within 6" (the canonical Lead-ability aura range).
        """
        try:
            army = unit.army_ref
            if army is None:
                return False
            for u in army.alive_units:
                if u is unit:
                    continue
                kw = u.profile.unit_keywords or ()
                if "CHARACTER" not in kw:
                    continue
                if _distance(u.position, unit.position) <= 6.0:
                    return True
        except Exception:
            return False
        return False

    def _try_protocol_undying_legions(self, army: Army, opponent: Army) -> None:
        """Protocol of the Undying Legions (Awakened Dynasty, 1 CP): a
        friendly NECRONS unit that just lost models reanimates D3 wounds
        (D3+1 if led). The simulator fires this at round start as an
        anticipatory pulse on the most-wounded NECRONS unit; the pulse
        triggers in `_apply_undying_legions_pulse` at the end of the
        opponent's activations (we collapse opponent shooting / fight
        into the round-end reanimation step). Median D3 = 2, so
        unled = 2 wounds, led = 3 wounds. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        target = self._most_vulnerable_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_UNDYING_LEGIONS, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_UNDYING_LEGIONS):
            return
        # Median D3 = 2; +1 if led.
        wounds = 3 if self._is_led_unit(target) else 2
        target.transient_undying_legions_pulse = wounds

    def _try_protocol_hungry_void(self, army: Army, opponent: Army) -> None:
        """Protocol of the Hungry Void (Awakened Dynasty, 1 CP): +1 S
        melee (+1 AP melee if led) on a NECRONS unit for the round.
        APPROXIMATION: the simulator doesn't expose a clean per-round S/AP
        boost slot, so we route the equivalent offensive uplift through
        `transient_plus_one_to_wound_melee` (the existing +1-to-wound flag
        used by Outbreak of Pestilence). Same direction, slightly more
        generous than the true +1 S (because +1 to wound always closes a
        bracket whereas +1 S only sometimes does). The AP leg is dropped
        in the unled case and folded into the wound buff when led.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        attacker = self._highest_dpa_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_HUNGRY_VOID, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_HUNGRY_VOID):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_wound_melee")

    def _try_protocol_sudden_storm(self, army: Army, opponent: Army) -> None:
        """Protocol of the Sudden Storm (Awakened Dynasty, 1 CP): ranged
        weapons on a NECRONS unit gain [ASSAULT] for the turn (re-roll
        Advance rolls if led — that leg is dropped because the simulator
        has no Advance re-roll hook and the Assault grant alone is the
        primary value). Maps cleanly to `transient_assault_this_round`.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        attacker = self._highest_dpa_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_SUDDEN_STORM, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_SUDDEN_STORM):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_protocol_conquering_tyrant(self, army: Army, opponent: Army) -> None:
        """Protocol of the Conquering Tyrant (Awakened Dynasty, 1 CP):
        re-roll Hit rolls of 1 within half range on a NECRONS unit's
        shoot (full re-roll if led). APPROXIMATION: the simulator's
        `transient_reroll_hits_shooting` flag triggers a full hit
        re-roll, not just 1s — direction-correct but slightly more
        generous than the unled stratagem. Range gate is dropped because
        the simulator already computes half-range mechanics per shot
        and the AI only fires this when there's a meaningful shooter.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        attacker = self._highest_dpa_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_CONQUERING_TYRANT, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_CONQUERING_TYRANT):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    # ----- War Horde (Orks) per-stratagem dispatchers (iter-1 B1) --------
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
    # WebFetch returned ECONNREFUSED at edit time; effects below are
    # paraphrased per the iter-1 Cluster B diagnostic and routed through
    # existing transient_* flags. Each dispatcher consults the AI gate
    # via `should_fire_stratagem` and spends CP via `_fire_stratagem` —
    # standard pattern, mirroring the Mont'ka / Warhost dispatchers above.

    def _try_power_of_the_waaagh(self, army: Army, opponent: Army) -> None:
        """Power Of The WAAAGH! (War Horde, 1 CP). Real rule (paraphrase):
        an ORKS unit's melee weapons gain [LETHAL HITS] for the fight phase
        (or upgrade to 5+ Critical Hit if they already carry the ability).
        ST-1: now routes through the proper `transient_lethal_hits` flag
        (composes into `effective_lethal_hits` at the crit-to-hit branch
        in Unit.attack). Previously proxied through
        `transient_plus_one_to_wound_melee`, which over-modelled the buff
        because +1 to wound averages ~25% extra landed wounds at threshold
        flip while [LETHAL HITS] only auto-wounds on natural 6s (~17%
        of failed-wound salvage on a 4+ wound roll). The 5+ Critical-Hit
        upgrade leg for weapons already carrying [LETHAL HITS] is still
        dropped.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, POWER_OF_THE_WAAAGH, ctx):
            return
        if not self._fire_stratagem(army, POWER_OF_THE_WAAAGH):
            return
        self._set_transient_squad(attacker, "transient_lethal_hits")

    def _try_mob_up(self, army: Army, opponent: Army) -> None:
        """Mob Up (War Horde, 1 CP). Real rule (paraphrase): an ORKS
        INFANTRY unit that has lost models absorbs surviving models from
        a destroyed friendly ORKS INFANTRY unit. APPROXIMATION: no model-
        absorbing hook in SwegHammer, so we route the "regain bodies"
        value through `transient_undying_legions_pulse = 2` on the most
        vulnerable Orks INFANTRY unit — fires the existing mid-phase
        reanimation pulse Awakened Dynasty's Undying Legions uses.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        target = self._most_vulnerable_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, MOB_UP, ctx):
            return
        if not self._fire_stratagem(army, MOB_UP):
            return
        target.transient_undying_legions_pulse = 2

    def _try_big_krumpin(self, army: Army, opponent: Army) -> None:
        """Big Krumpin' (War Horde, 2 CP). Real rule (paraphrase): an
        ORKS unit re-rolls Wound rolls of 1 in melee (full re-roll if
        charging). ST-1: now routes through `transient_reroll_wounds_ones`
        — the correct lossy proxy for the codex (1s-only re-roll averages
        ~14% extra landed wounds). Previously proxied through
        `transient_plus_one_to_wound_melee`, which was strictly stronger
        (+1 to wound ≈ 25% extra wounds vs 14% for 1s-reroll). The full-
        reroll-when-charging leg is dropped (no charge-state hook); given
        Big Krumpin' costs 2 CP and the AI gate is already conservative,
        the under-fire on charge turns is acceptable.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, BIG_KRUMPIN, ctx):
            return
        if not self._fire_stratagem(army, BIG_KRUMPIN):
            return
        self._set_transient_squad(attacker, "transient_reroll_wounds_ones")

    def _try_tellyporta(self, army: Army, opponent: Army) -> None:
        """Tellyporta (War Horde, 1 CP). Real rule (paraphrase): an ORKS
        INFANTRY unit is removed from the battlefield and placed back via
        Strategic Reserves at the start of the next round. APPROXIMATION:
        no mid-battle reserve hook, so the defensive payoff ("pull the
        unit off the table to avoid the next attack") is routed through
        `transient_plus_one_save` on the most vulnerable Orks INFANTRY
        unit — same single-flag stand-in Webway Tunnel uses for Aeldari.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        target = self._most_vulnerable_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, TELLYPORTA, ctx):
            return
        if not self._fire_stratagem(army, TELLYPORTA):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    def _try_da_biggest_boss(self, army: Army, opponent: Army) -> None:
        """Da Biggest Boss (War Horde, 1 CP). Real rule (paraphrase):
        Warlord-targeted; the ORKS CHARACTER Warlord makes a free D6+1"
        Normal Move in the Movement phase. APPROXIMATION: SwegHammer's
        grid-free movement model can't usefully consume per-phase D6+1"
        repositioning, so the offensive payoff (reposition into firing
        / charging range) is routed through `transient_assault_this_round`
        on the highest-DPA Orks CHARACTER — lets the Warlord shoot the
        same round it would have repositioned.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        # Pick the highest-DPA Orks CHARACTER.
        warlord = None
        best_dpa = 0.0
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "CHARACTER" not in kw:
                continue
            if (u.profile.faction or "") != "Orks":
                continue
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            melee = (p.melee_attacks * p.melee_hit_probability
                     * (p.melee_damage_per_shot or 0.0))
            dpa = ranged + melee
            if dpa > best_dpa:
                best_dpa = dpa
                warlord = u
        if warlord is None:
            return
        ctx = {"attacker": warlord}
        if not should_fire_stratagem(army, DA_BIGGEST_BOSS, ctx):
            return
        if not self._fire_stratagem(army, DA_BIGGEST_BOSS):
            return
        self._set_transient_squad(warlord, "transient_assault_this_round")

    # ----- Shield Host (Adeptus Custodes) — six real stratagems (iter-8 fix)
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
    # CP costs + WHEN/EFFECT confirmed against Goonhammer 10e codex review +
    # Wahapedia listing. WebFetch against wahapedia.ru returned ECONNREFUSED
    # at edit time; effect descriptions are paraphrased per the canonical
    # Goonhammer source, with each entry flagged APPROXIMATION in
    # data/rule_citations.d/stratagems.json. Effect mappings follow the
    # War Horde / Mont'ka pattern — route through the nearest existing
    # transient_* flag and document the gap.

    def _try_arcane_genetic_alchemy(self, army: Army, opponent: Army) -> None:
        """Arcane Genetic Alchemy (Shield Host, 1 CP, Battle Tactic). Real
        rule: after a Mortal wound is allocated to a friendly Adeptus
        Custodes unit, until end of phase that unit has Feel No Pain 4+
        against Mortal wounds. APPROXIMATION: SwegHammer doesn't model
        mortal-wound-only FNP buckets; we use `transient_fnp_5` (FNP 5+ for
        the round against all damage) on the most vulnerable Custodes unit.
        Direction-correct (defensive damage reduction) but lossy on both
        magnitude (5+ vs 4+) and gate (all damage vs mortal-only). Catalogued
        per iter-8 Shield Host rebuild; Wahapedia URL above.
        """
        target = self._most_vulnerable_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, ARCANE_GENETIC_ALCHEMY, ctx):
            return
        if not self._fire_stratagem(army, ARCANE_GENETIC_ALCHEMY):
            return
        self._set_transient_squad(target, "transient_fnp_5")

    def _try_unwavering_sentinels(self, army: Army, opponent: Army) -> None:
        """Unwavering Sentinels (Shield Host, 1 CP, Strategic Ploy). Real
        rule: Fight phase, after an enemy targets a friendly Custodes
        INFANTRY unit on an objective you control — that enemy unit takes
        -1 to Hit for the rest of the phase. APPROXIMATION: no per-target
        -1-to-hit transient flag in SwegHammer, so we route the defensive
        payoff through `transient_plus_one_save` on the most vulnerable
        Custodes INFANTRY unit. Both buffs reduce incoming damage; lossy
        on the gate (objective control + per-attacker scope).
        """
        target = self._most_vulnerable_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, UNWAVERING_SENTINELS, ctx):
            return
        if not self._fire_stratagem(army, UNWAVERING_SENTINELS):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    def _try_multipotentiality(self, army: Army, opponent: Army) -> None:
        """Multipotentiality (Shield Host, 1 CP, Strategic Ploy). Real rule:
        your Movement phase, on a Custodes unit that just Fell Back — that
        unit can shoot and declare a charge this turn. APPROXIMATION: maps
        cleanly to `transient_assault_this_round` on the highest-DPA
        Custodes unit (same flag Feigned Retreat uses). Round-start
        dispatcher collapses the 'just Fell Back' precondition.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, MULTIPOTENTIALITY, ctx):
            return
        if not self._fire_stratagem(army, MULTIPOTENTIALITY):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_archaeotech_munitions(self, army: Army, opponent: Army) -> None:
        """Archaeotech Munitions (Shield Host, 1 CP, Wargear). Real rule:
        your Shooting phase, on a Custodes unit — ranged weapons gain
        [LETHAL HITS] OR [SUSTAINED HITS 1] (player's choice) for the
        phase. ST-1: now routes through `transient_lethal_hits` (the
        higher-value half of the player's choice — [LETHAL HITS] on a
        Custodes unit's BS2+ profile typically outscores [SUSTAINED HITS
        1] because Custodes shots are few and high-damage). Previously
        proxied through `transient_plus_one_to_hit_shooting`, which was
        strictly stronger because +1 to hit fires on every die above the
        previous fail threshold whereas [LETHAL HITS] only fires on
        natural 6s.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, ARCHAEOTECH_MUNITIONS, ctx):
            return
        if not self._fire_stratagem(army, ARCHAEOTECH_MUNITIONS):
            return
        self._set_transient_squad(attacker, "transient_lethal_hits")

    def _try_avenge_the_fallen(self, army: Army, opponent: Army) -> None:
        """Avenge the Fallen (Shield Host, 1 CP, Strategic Ploy). Real rule:
        start of Fight phase, on a Custodes unit below Starting Strength —
        +1 Attack (or +2 if below half Starting Strength) for the phase.
        APPROXIMATION: SwegHammer doesn't expose a transient per-attack-
        count buff; offensive uplift is routed through
        `transient_plus_one_to_wound_melee` on the most vulnerable Custodes
        melee unit. Direction-correct (more landed melee damage),
        comparable magnitude on a 4+ wound roll.
        """
        target = self._most_vulnerable_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, AVENGE_THE_FALLEN, ctx):
            return
        if not self._fire_stratagem(army, AVENGE_THE_FALLEN):
            return
        self._set_transient_squad(target, "transient_plus_one_to_wound_melee")

    # ----- Needgaard Oathband (Leagues of Votann) — three real stratagems -----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
    # VOTANN-DIAG-2 (2026-05-26): replaced five fabricated stratagems
    # (Warrior Pride, Wrath of the Ancestors, Glory of the Hearth, Ironkin
    # Sequence, Void-Armoured Resilience) with three real Needgaard Oathband
    # stratagems confirmed on Wahapedia. The old set did not exist in the
    # current 10e codex — they were sourced from an old edition or fabricated
    # when Wahapedia was unreachable. Their removal eliminates: full wound
    # rerolls per round, Lethal Hits per round, vehicle hit-rerolls per round,
    # and +1 to hit shooting per round — all of which were contributing to
    # the +6.48pt Votann over-performance.

    def _try_ancestral_sentence(self, army: Army, opponent: Army) -> None:
        """Ancestral Sentence (Needgaard Oathband, 1 CP). Real rule (Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/):
        "ranged weapons equipped by models in your unit have the [SUSTAINED
        HITS 1] ability." Maps to transient_sustained_hits = 1 on the
        highest-DPA Votann shooter vs a heavy target. Replaces the fake 2 CP
        'issue a Judgement Token' spend — the real Ancestral Sentence has no
        token-issuing effect in the current codex. Cited as
        'Stratagem.Ancestral Sentence'.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="LEAGUES OF VOTANN", faction="Leagues of Votann",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Leagues of Votann")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, ANCESTRAL_SENTENCE, ctx):
            return
        if not self._fire_stratagem(army, ANCESTRAL_SENTENCE):
            return
        attacker.transient_sustained_hits = max(
            getattr(attacker, "transient_sustained_hits", 0) or 0, 1
        )

    def _try_void_hardened(self, army: Army, opponent: Army) -> None:
        """Void Hardened (Needgaard Oathband, 1 CP). Real rule (Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/):
        "worsen the Armour Penetration characteristic of that attack by 1"
        — a defensive stratagem that reduces the Armour Penetration of
        incoming attacks for a phase. The simulator has no incoming-AP
        worsening transient flag, so this dispatcher registers the spend
        but applies no effect. This is conservative (errs toward under-
        buffing Votann). A future structural pass can add an incoming-AP
        flag when needed. Cited as 'Stratagem.Void Hardened'.
        """
        # Defensive no-op: the simulator cannot model incoming-AP worsening.
        # Register the spend against a plausible gate so the stratagem
        # cap counts it; the defensive value is lost but no false buff is
        # applied. Gate on the most vulnerable Votann unit having at least
        # one health point of incoming threat.
        target = self._most_vulnerable_unit(
            army, keyword="LEAGUES OF VOTANN", faction="Leagues of Votann",
        )
        if target is None:
            target = self._most_vulnerable_unit(army, faction="Leagues of Votann")
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, VOID_HARDENED, ctx):
            return
        # Intentionally no effect — see docstring above.
        self._fire_stratagem(army, VOID_HARDENED)

    # ----- Gladius Task Force (Adeptus Astartes) — six real strats (iter-12) -
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
    # Marines is the most-used codex (134 units catalogued) and was on 0/6
    # detachment stratagems before this iter. Per docs/AUDIT_PARITY.md fix #1
    # this is the highest-leverage parity fix — every Marines matchup
    # understated offence by ~2-3 CP/round of detachment value. The six
    # dispatchers mirror the iter-8 Shield Host pattern: AI gate via
    # should_fire_stratagem, spend CP via _fire_stratagem, then apply the
    # transient effect on the chosen unit. Each dispatcher uses an inline
    # `is_marine_faction` filter rather than the `_unit_matches_filter` helper
    # because Marines spans 12 faction strings (Adeptus Astartes + Ultramarines
    # + chapter codices) — see code.factions.MARINE_FACTIONS.

    def _marine_units(self, army: Army):
        """Return alive friendly units belonging to any Marine chapter.

        Faction-gated via `is_marine_faction` (12 faction strings) AND
        excludes Battle-shocked units per 10e core rule
        `simulator.battleshock`. Used by every Gladius dispatcher as the
        target-selection pool.
        """
        from .factions import is_marine_faction
        return [
            u for u in army.alive_units
            if is_marine_faction(u.profile.faction or "")
            and u.uid not in self._battleshocked_this_round
        ]

    @staticmethod
    def _unit_dpa(u) -> float:
        """Combined melee + ranged damage-per-activation. Same scoring as
        `_highest_dpa_unit` but exposed as a free function so the inline
        Marine filters can use it without re-implementing."""
        p = u.profile
        ranged = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        melee = ((p.melee_attacks or 0) * (p.melee_hit_probability or 0)
                 * (p.melee_damage_per_shot or 0.0))
        return ranged + melee

    def _highest_dpa_marine(self, army: Army, keyword: str = ""):
        """Pick the highest-DPA Marine unit; optional keyword filter (e.g.
        'INFANTRY'). Returns None if no eligible candidate exists."""
        candidates = self._marine_units(army)
        if keyword:
            candidates = [
                u for u in candidates
                if keyword in (u.profile.unit_keywords or ())
            ]
        if not candidates:
            return None
        return max(candidates, key=self._unit_dpa)

    def _most_vulnerable_marine(self, army: Army, keyword: str = ""):
        """Pick the most-vulnerable Marine unit (points × HP-loss); optional
        keyword filter. Returns None if no eligible candidate exists."""
        candidates = self._marine_units(army)
        if keyword:
            candidates = [
                u for u in candidates
                if keyword in (u.profile.unit_keywords or ())
            ]
        if not candidates:
            return None

        def _score(u):
            try:
                cost = float(u.profile.points_cost)
                hp_frac = max(0.0, 1.0 - u.current_health / max(1.0, u.profile.health))
            except Exception:
                return 0.0
            return cost * hp_frac
        # If every candidate is at full HP the score is 0 — fall back to
        # highest-points (the defensive buff still preempts an incoming kill).
        best = max(candidates, key=_score)
        if _score(best) > 0.0:
            return best
        return max(candidates, key=lambda u: float(u.profile.points_cost or 0.0))

    def _try_storm_of_fire(self, army: Army, opponent: Army) -> None:
        """Storm of Fire (Gladius, 1 CP, Battle Tactic). Real rule: your
        Shooting phase, on an ADEPTUS ASTARTES unit — ranged weapons gain
        [SUSTAINED HITS 1] for the phase (or improve existing
        [SUSTAINED HITS X] by 1). ST-1: now routes through
        `transient_sustained_hits` (additive on top of any per-weapon
        SUSTAINED HITS already on the profile, which directly matches the
        codex stacking rule — a weapon with SUSTAINED HITS X gets X+1).
        Previously proxied through `transient_plus_one_to_hit_shooting`,
        which over-modelled the buff because +1-to-hit lifts every die
        above the previous fail threshold whereas SUSTAINED HITS 1 only
        fires on the natural 6.
        """
        candidates = self._marine_units(army)
        # Pre-filter to units with real ranged DPA — Storm of Fire only
        # buffs ranged weapons, so a melee-only Marine brick like
        # Bladeguard would never benefit from the +1-to-hit-shooting flag.
        candidates = [u for u in candidates
                      if (u.profile.attacks or 0) > 0
                      and (u.profile.per_shot_damage or 0.0) > 0.0]
        if not candidates:
            return

        def _ranged_dpa(u):
            p = u.profile
            return (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        attacker = max(candidates, key=_ranged_dpa)
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, STORM_OF_FIRE, ctx):
            return
        if not self._fire_stratagem(army, STORM_OF_FIRE):
            return
        attacker.transient_sustained_hits += 1

    def _try_armour_of_contempt(self, army: Army, opponent: Army) -> None:
        """Armour of Contempt (Gladius, 1 CP, Battle Tactic). Real rule:
        any phase, on an ADEPTUS ASTARTES unit being targeted — enemy AP
        against your unit is reduced by 1 for the phase. APPROXIMATION:
        SwegHammer has no transient enemy-AP-reduction flag, so the
        defensive payoff is routed through `transient_plus_one_save` on
        the most vulnerable Marine unit. Direction-correct (both reduce
        incoming damage); same lossy pattern as Unwavering Sentinels
        (Shield Host). +1 save is comparable on a 3+ save profile but
        loses the high-AP-weapon scaling that the real AP-minus-one
        provides.
        """
        target = self._most_vulnerable_marine(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, ARMOUR_OF_CONTEMPT, ctx):
            return
        if not self._fire_stratagem(army, ARMOUR_OF_CONTEMPT):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    def _try_squad_tactics(self, army: Army, opponent: Army) -> None:
        """Squad Tactics (Gladius, 1 CP, Strategic Ploy). Real rule: your
        opponent's Movement phase, on an ADEPTUS ASTARTES INFANTRY unit —
        that unit may make a Normal Move of up to 6". Mobility /
        repositioning utility (counter to enemy reserves / charges).
        APPROXIMATION: SwegHammer has no opponent-turn reactive move
        hook, so the offensive value is routed through
        `transient_assault_this_round` on the highest-DPA Marine INFANTRY
        unit — same flag Feigned Retreat / Multipotentiality use as the
        "extra setup + shoot after move" proxy.
        """
        attacker = self._highest_dpa_marine(army, keyword="INFANTRY")
        if attacker is None:
            attacker = self._highest_dpa_marine(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, SQUAD_TACTICS, ctx):
            return
        if not self._fire_stratagem(army, SQUAD_TACTICS):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_only_in_death_does_duty_end(self, army: Army, opponent: Army) -> None:
        """Only In Death Does Duty End (Gladius, 1 CP, Strategic Ploy).
        Real rule: the Fight phase, after an ADEPTUS ASTARTES model is
        destroyed before making its attacks — that model may make its
        attacks before being removed. APPROXIMATION: SwegHammer doesn't
        model per-model attack ordering at the destroyed-before-attack
        granularity; the offensive payoff is routed through
        `transient_plus_one_to_wound_melee` on the most vulnerable Marine
        melee unit (the "one last swing" proxy translates to +1 to wound
        on the remaining attacks). Direction-correct; misses the timing
        detail (codex grants attacks to destroyed models, we buff the
        surviving unit). Same lossy pattern as Avenge the Fallen
        (Shield Host).
        """
        target = self._most_vulnerable_marine(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, ONLY_IN_DEATH_DOES_DUTY_END, ctx):
            return
        if not self._fire_stratagem(army, ONLY_IN_DEATH_DOES_DUTY_END):
            return
        self._set_transient_squad(target, "transient_plus_one_to_wound_melee")

    def _try_honour_the_chapter(self, army: Army, opponent: Army) -> None:
        """Honour the Chapter (Gladius, 2 CP, Battle Tactic). Real rule:
        any phase, on an ADEPTUS ASTARTES unit — that unit may re-roll
        Hit AND Wound rolls for the phase. The premium 2-CP offensive
        nuke. APPROXIMATION: SwegHammer routes the offensive value
        through `transient_reroll_hits_shooting` on the highest-DPA
        Marine unit — the wound-reroll leg is dropped (no transient
        wound-reroll flag). Strictly weaker than the codex (~half the
        value), direction-correct. Same lossy pattern as Glory of the
        Hearth (Oathband) and Devastating Sorcery (Grand Coven).
        """
        attacker = self._highest_dpa_marine(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, HONOUR_THE_CHAPTER, ctx):
            return
        if not self._fire_stratagem(army, HONOUR_THE_CHAPTER):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    def _try_adaptive_strategy(self, army: Army, opponent: Army) -> None:
        """Adaptive Strategy (Gladius, 1 CP, Strategic Ploy). Real rule:
        start of your Command phase, on an ADEPTUS ASTARTES unit — that
        unit gains the rules of one Combat Doctrine of your choice
        (Devastator / Tactical / Assault) until end of turn, regardless
        of which doctrine the army is currently in.

        SC5-9 audit: this stratagem previously fired
        `transient_plus_one_to_wound_melee = True` on the highest-DPA
        Marine melee unit, on the premise that "Combat Doctrines in
        SwegHammer is a round-and-mode-gated +1 to wound" and that
        Adaptive Strategy granted Assault Doctrine's +1-to-wound-melee
        outside R3+. That premise was a stale pre-iter-9 leftover: the
        iter-9 May 2026 audit corrected `simulator.combat_doctrines`
        from a fabricated +1-to-wound to the canonical utility-only
        Devastator / Tactical / Assault Doctrine mechanics (shoot after
        Advance / shoot + charge after Fall Back / charge after
        Advance), per Wahapedia's verbatim Combat Doctrines text. With
        Doctrines correctly modelled as utility-only, the Doctrines
        themselves no longer contain a +1-to-wound to grant, so the
        "Adaptive Strategy grants Assault Doctrine's +1-to-wound"
        bridge has nothing to grant — the fabricated wound buff was a
        double-count layered on top of a corrected base rule and was
        contributing to the +17.5pt Astartes over-modelling outlier
        (sim 65.5% vs Warp Friends 48.0% per the SC5 N=40 baseline).

        Honest model: per-unit doctrine override at the resolution
        SwegHammer carries is below modelling capability — there is no
        per-unit doctrine state to flip. The stratagem is recorded as
        an APPROXIMATION no-op until per-unit doctrine state lands.
        Direction-correct: removes a fabricated buff; loses the
        per-unit doctrine override (genuinely unmodellable today).
        """
        attacker = self._highest_dpa_marine(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, ADAPTIVE_STRATEGY, ctx):
            return
        if not self._fire_stratagem(army, ADAPTIVE_STRATEGY):
            return
        # SC5-9: no buff applied — see docstring. Spending the CP and
        # emitting the StratagemFired event is retained so the CP
        # economy and AI scheduler still see the activation, matching
        # the real player paying 1 CP for a doctrine override that
        # SwegHammer can't yet faithfully apply.

    # ----- Combined Arms (Astra Militarum) — six real strats (iter-14) ------
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
    # Closes the AM 0/6 detachment-stratagem gap. The detachment's spine is
    # the Voice of Command Order economy (army-wide passive — see
    # `code/orders.py`), so three of the six stratagems wire onto Order
    # mechanics (Coordinated Action, Flexible Command, Inspired Command)
    # and the other three onto existing transient_* flags (Fields of
    # Fire, Stalwart Protector) or no-op approximations (Reinforcements!).

    def _am_units(self, army: Army):
        """Return alive friendly Astra Militarum units (non-battleshocked)."""
        return [
            u for u in army.alive_units
            if (u.profile.faction or "") == "Astra Militarum"
            and u.uid not in self._battleshocked_this_round
        ]

    def _highest_dpa_am_squadron(self, army: Army):
        """Pick the highest-DPA AM SQUADRON (VEHICLE) unit; None if absent."""
        candidates = [
            u for u in self._am_units(army)
            if "VEHICLE" in (u.profile.unit_keywords or ())
        ]
        if not candidates:
            return None
        return max(candidates, key=self._unit_dpa)

    def _most_vulnerable_am_infantry(self, army: Army):
        """Pick the most-vulnerable AM INFANTRY unit; None if absent."""
        candidates = [
            u for u in self._am_units(army)
            if "INFANTRY" in (u.profile.unit_keywords or ())
            and "VEHICLE" not in (u.profile.unit_keywords or ())
        ]
        if not candidates:
            return None

        def _score(u):
            try:
                cost = float(u.profile.points_cost)
                hp_frac = max(0.0, 1.0 - u.current_health / max(1.0, u.profile.health))
            except Exception:
                return 0.0
            return cost * hp_frac
        best = max(candidates, key=_score)
        if _score(best) > 0.0:
            return best
        return max(candidates, key=lambda u: float(u.profile.points_cost or 0.0))

    def _try_coordinated_action(self, army: Army, opponent: Army) -> None:
        """Coordinated Action (Combined Arms, 1 CP, Battle Tactic). Real
        rule: start of any phase, on one REGIMENT + one SQUADRON within
        6" and visible — Orders affecting one also affect the other.
        APPROXIMATION: routes the offensive payoff through
        `transient_plus_one_to_hit_shooting` on the highest-DPA AM
        SQUADRON (VEHICLE) — the canonical use case is extending
        Take Aim! / FRFSRF from an Infantry Squad to a Leman Russ pair.
        AM-DIAG-4 (2026-05-24): added anti-stack guard — skip fire if the
        SQUADRON target already holds any transient Order buff for the
        round. The real rule "mirrors" an Order from one unit to another,
        so re-applying the same flag the unit already has is a no-op in
        the codex and a fab-magnitude amplifier in the proxy.
        """
        attacker = self._highest_dpa_am_squadron(army)
        if attacker is None:
            return
        # AM-DIAG-4: anti-stack guard. The proxy buff (+1 to hit shooting) is
        # the same flag Take Aim! / FRFSRF set on REGIMENT targets. If the
        # SQUADRON is already buffed (e.g. by Flexible Command + Take Aim!
        # earlier the same round), re-firing is wasted CP at best and an
        # unintentional double-buff at worst when the proxy is summed
        # elsewhere. Real codex: mirroring an Order is a no-op if the
        # destination already holds it.
        if (attacker.transient_plus_one_to_hit_shooting
                or attacker.transient_plus_one_to_wound_melee
                or attacker.transient_plus_one_save):
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, COORDINATED_ACTION, ctx):
            return
        if not self._fire_stratagem(army, COORDINATED_ACTION):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_hit_shooting")

    def _try_flexible_command(self, army: Army, opponent: Army) -> None:
        """Flexible Command (Combined Arms, 2 CP, Strategic Ploy). Real
        rule: your Command phase, any number of AM OFFICER units — until
        end of phase, Officers can issue Orders to REGIMENT and SQUADRON
        units. CLEAN MAPPING: sets `Army.orders_eligible_squadron_this_round
        = True` for the round; `code.orders._is_order_target_eligible`
        reads the flag and widens the target pool to BATTLELINE VEHICLE.
        """
        from .orders import _is_am_officer
        officers = [
            u for u in self._am_units(army)
            if _is_am_officer(u)
        ]
        if not officers:
            return
        squadron_candidates = [
            u for u in self._am_units(army)
            if "BATTLELINE" in (u.profile.unit_keywords or ())
            and "VEHICLE" in (u.profile.unit_keywords or ())
        ]
        if not squadron_candidates:
            return
        ctx = {"officers": officers, "squadron_candidates": squadron_candidates}
        if not should_fire_stratagem(army, FLEXIBLE_COMMAND, ctx):
            return
        if not self._fire_stratagem(army, FLEXIBLE_COMMAND):
            return
        army.orders_eligible_squadron_this_round = True

    def _try_fields_of_fire(self, army: Army, opponent: Army) -> None:
        """Fields of Fire (Combined Arms, 1 CP, Battle Tactic). Real
        rule: your Shooting phase, one REGIMENT + one SQUADRON not yet
        shot — attacks targeting a chosen enemy improve AP by 1.
        APPROXIMATION: routes the offensive payoff through
        `transient_plus_one_to_hit_shooting` on the highest-ranged-DPA
        AM unit; AP+1 → +1 to hit is the closest single-flag proxy.
        """
        candidates = self._am_units(army)
        if not candidates:
            return

        def _ranged_dpa(u):
            p = u.profile
            return (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        # AM-DIAG-4 (2026-05-24): pick the highest-DPA AM unit that does NOT
        # already hold a transient offensive buff. The +1-to-hit-shooting
        # proxy is the same flag Take Aim! / FRFSRF / Coordinated Action
        # set; re-firing on an already-buffed unit is wasted CP in the
        # codex (the rule grants AP+1, not +1 to hit, so on a real codex
        # build it would stack with Take Aim — but on the proxy it does
        # not, and we don't want the dispatcher to think it accomplished
        # anything when it didn't). Picking an un-buffed second unit also
        # narrows the magnitude per round to a single ranged shooter.
        ranged_candidates = [
            u for u in candidates
            if _ranged_dpa(u) > 0.0
            and not u.transient_plus_one_to_hit_shooting
        ]
        if not ranged_candidates:
            return
        attacker = max(ranged_candidates, key=_ranged_dpa)
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, FIELDS_OF_FIRE, ctx):
            return
        if not self._fire_stratagem(army, FIELDS_OF_FIRE):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_hit_shooting")

    def _try_inspired_command(self, army: Army, opponent: Army) -> None:
        """Inspired Command (Combined Arms, 1 CP, Epic Deed). Real rule:
        opponent's Command phase, one AM OFFICER — that Officer can
        issue one Order as if it were your Command phase. APPROXIMATION:
        maps onto 'issue one extra Order this round' — the dispatcher
        picks an un-buffed REGIMENT in aura of any AM Officer and
        applies the AI's chosen Order to it.
        """
        from .orders import (
            _is_am_officer, _is_order_target_eligible, _pick_order_for_target,
            _apply_order, OFFICER_AURA_RANGE, _distance,
        )
        officers = [
            u for u in self._am_units(army)
            if _is_am_officer(u) and u.uid not in self._battleshocked_this_round
        ]
        if not officers:
            return
        targets = [
            u for u in army.alive_units
            if _is_order_target_eligible(u, squadron_allowed=False)
            and u.uid not in self._battleshocked_this_round
        ]
        if not targets:
            return
        un_ordered = [
            t for t in targets
            if not (
                t.transient_plus_one_to_hit_shooting
                or t.transient_plus_one_to_wound_melee
                or t.transient_plus_one_save
            )
        ]
        if not un_ordered:
            return
        chosen_pair = None
        for officer in officers:
            in_aura = [
                t for t in un_ordered
                if _distance(officer.position, t.position) <= OFFICER_AURA_RANGE
            ]
            if in_aura:
                chosen_pair = (officer, max(in_aura, key=lambda u: float(u.profile.points_cost or 0.0)))
                break
        if chosen_pair is None:
            return
        officer, target = chosen_pair
        ctx = {"officer": officer, "target": target}
        if not should_fire_stratagem(army, INSPIRED_COMMAND, ctx):
            return
        if not self._fire_stratagem(army, INSPIRED_COMMAND):
            return
        order = _pick_order_for_target(target)
        _apply_order(target, order)

    def _try_stalwart_protector(self, army: Army, opponent: Army) -> None:
        """Stalwart Protector (Combined Arms, 1 CP, Battle Tactic). Real
        rule: opponent's Shooting phase, one AM VEHICLE — INFANTRY models
        from your army not fully visible because of your VEHICLE have
        Benefit of Cover. CLEAN MAPPING (with approximate eligibility):
        routes the defensive payoff through `transient_plus_one_save`
        on the most-vulnerable AM INFANTRY unit. Gates on at least one
        alive AM VEHICLE to match the codex pre-requisite.
        """
        vehicles = [
            u for u in self._am_units(army)
            if "VEHICLE" in (u.profile.unit_keywords or ())
        ]
        if not vehicles:
            return
        target = self._most_vulnerable_am_infantry(army)
        if target is None:
            return
        # AM-DIAG-4 (2026-05-24): anti-stack guard. The proxy buff
        # (+1 save) is the same flag Take Cover! Order sets; if the
        # vulnerable INFANTRY target already holds Take Cover! (or any
        # transient buff) for the round, re-firing is wasted CP in the
        # codex (Benefit of Cover does not stack with itself) and a
        # magnitude amplifier in the proxy. The real LoS-blocked-by-
        # VEHICLE visibility gate is also not modelled — without the
        # anti-stack guard the dispatcher fires every round AM has a
        # vehicle, which over-states the rule's frequency.
        if target.transient_plus_one_save:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, STALWART_PROTECTOR, ctx):
            return
        if not self._fire_stratagem(army, STALWART_PROTECTOR):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    # Reinforcements! — catalogued in COMBINED_ARMS_STRATAGEMS for the
    # auditor + stratagems_for_army listing, but no `_try_reinforcements`
    # dispatcher exists (catalogued-but-no-op APPROXIMATION). The codex
    # effect (re-add a destroyed INFANTRY REGIMENT to Strategic Reserves
    # at full strength) has no clean simulator hook (no mid-battle unit-
    # respawn / reserve-injection primitive). The dispatch loop simply
    # skips the entry, no CP spent.

    # ----- ST-2 wave 3 — one stratagem per under-performing faction ----
    # Wahapedia citations live in data/rule_citations.d/stratagems.json.
    # Five offensive uplifts (one each for World Eaters, Chaos Daemons,
    # Grey Knights, Genestealer Cults, Chaos Space Marines), each routed
    # through an existing transient_* flag because the simulator has no
    # LETHAL HITS / SUSTAINED HITS / wound-reroll transient yet (ST-1 in
    # parallel addresses that mapping gap). Each is faction-gated via
    # `_highest_dpa_unit(keyword=..., faction=...)` — no buffs leak onto
    # non-matching attached allies.

    def _try_apoplectic_frenzy(self, army: Army, opponent: Army) -> None:
        """Apoplectic Frenzy (Berzerker Warband, 1 CP). Real rule: a WORLD
        EATERS unit's melee weapons gain [LETHAL HITS] until end of Fight
        phase. APPROXIMATION: routed through transient_plus_one_to_wound_melee
        on the highest-DPA WE unit (LETHAL HITS auto-wounds on crit-to-hit;
        +1 to wound is a direction-correct offensive uplift via an existing
        transient flag). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/world-eaters/#Berzerker-Warband
        """
        attacker = self._highest_dpa_unit(
            army, keyword="WORLD EATERS", faction="World Eaters",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, APOPLECTIC_FRENZY, ctx):
            return
        if not self._fire_stratagem(army, APOPLECTIC_FRENZY):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_wound_melee")

    def _try_denizens_of_the_warp(self, army: Army, opponent: Army) -> None:
        """Denizens of the Warp (Daemonic Incursion, 1 CP). Real rule: re-roll
        Hit and Wound rolls of 1 for a CHAOS DAEMONS unit's attacks vs an
        enemy unit within range of an Objective Marker. APPROXIMATION: routed
        through transient_reroll_hits_shooting (the hit-1 reroll half; the
        wound-1 reroll half and the objective-range gate are dropped — same
        proxy as Fire and Fade / Creeping Blight). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Daemonic-Incursion
        """
        attacker = self._highest_dpa_unit(
            army, keyword="DAEMON", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, DENIZENS_OF_THE_WARP, ctx):
            return
        if not self._fire_stratagem(army, DENIZENS_OF_THE_WARP):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    def _try_draught_of_terror(self, army: Army, opponent: Army) -> None:
        """Draught of Terror (Daemonic Incursion, 1 CP). Real rule (paraphrase
        from 40k.app): improve Armour Penetration by 1 for a CHAOS DAEMONS
        unit's attacks and re-roll Wound rolls against Battle-shocked enemies
        until end of phase. APPROXIMATION: AP-improvement transient not
        modelled; routed through transient_plus_one_to_wound_shooting on the
        highest-DPA CHAOS DAEMONS unit (direction-correct offensive uplift on
        wound rolls). Wound-reroll-vs-battleshocked rider dropped.
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/daemonic-incursion
        """
        attacker = self._highest_dpa_unit(
            army, keyword="DAEMON", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, DRAUGHT_OF_TERROR, ctx):
            return
        if not self._fire_stratagem(army, DRAUGHT_OF_TERROR):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_wound_shooting")

    def _try_warp_surge(self, army: Army, opponent: Army) -> None:
        """Warp Surge (Daemonic Incursion, 1 CP). Real rule (paraphrase from
        40k.app): a LEGIONES DAEMONICA unit within Shadow of Chaos is eligible
        to declare a charge in a turn in which it Advanced. APPROXIMATION:
        routed through transient_assault_this_round on the highest-DPA CHAOS
        DAEMONS unit — same flag Aggressive Mobility / Feigned Retreat /
        Multipotentiality use (advance-and-charge proxy). Shadow of Chaos gate
        dropped.
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/daemonic-incursion
        """
        attacker = self._highest_dpa_unit(
            army, keyword="DAEMON", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, WARP_SURGE, ctx):
            return
        if not self._fire_stratagem(army, WARP_SURGE):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_daemonic_invulnerability(self, army: Army, opponent: Army) -> None:
        """Daemonic Invulnerability (Daemonic Incursion, 1 CP). Real rule
        (paraphrase from 40k.app): re-roll invulnerable saving throws of 1 for
        a LEGIONES DAEMONICA unit until end of phase. APPROXIMATION: SwegHammer
        has no transient invuln-save-reroll flag; routed through transient_invuln_4
        on the most vulnerable CHAOS DAEMONS unit (grants a 4+ invulnerable save
        for the round — strictly stronger than a 1s-reroll on a typical 5+ Daemon
        invuln, acceptable given round-start dispatcher collapses the reactive
        trigger). Direction-correct defensive buff.
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/daemonic-incursion
        """
        target = self._most_vulnerable_unit(
            army, keyword="DAEMON", faction="Chaos Daemons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, DAEMONIC_INVULNERABILITY, ctx):
            return
        if not self._fire_stratagem(army, DAEMONIC_INVULNERABILITY):
            return
        self._set_transient_squad(target, "transient_invuln_4")

    def _try_blood_begets_skulls(self, army: Army, opponent: Army) -> None:
        """Blood Begets Skulls (Blood Legion, 1 CP). Real rule (paraphrase
        from 40k.app): a LEGIONES DAEMONICA KHORNE unit is eligible to declare
        a charge in a turn in which it Advanced. APPROXIMATION: routed through
        transient_assault_this_round on the highest-DPA Khorne Daemons unit
        (same flag as Warp Surge / Aggressive Mobility). Direction-correct:
        advance-and-charge delivery for Khorne melee units.
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/blood-legion
        """
        attacker = self._highest_dpa_unit(
            army, keyword="KHORNE", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="DAEMON", faction="Chaos Daemons",
            )
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, BLOOD_BEGETS_SKULLS, ctx):
            return
        if not self._fire_stratagem(army, BLOOD_BEGETS_SKULLS):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_wrath_undeniable(self, army: Army, opponent: Army) -> None:
        """Wrath Undeniable (Blood Legion, 1 CP). Real rule (paraphrase from
        40k.app): Fight phase. When a LEGIONES DAEMONICA KHORNE model is
        destroyed by a melee attack and has not yet fought, roll D6: on a 4+
        the model fights before being removed. APPROXIMATION: per-destroyed-
        model fight-before-removal hook not modelled; routed through
        transient_plus_one_to_wound_melee on the most vulnerable KHORNE DAEMONS
        melee unit (same proxy as Only In Death Does Duty End / Avenge the
        Fallen — 'one last swing from a dying unit'). Direction-correct.
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/blood-legion
        """
        attacker = self._highest_dpa_unit(
            army, keyword="KHORNE", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="DAEMON", faction="Chaos Daemons",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, WRATH_UNDENIABLE, ctx):
            return
        if not self._fire_stratagem(army, WRATH_UNDENIABLE):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_wound_melee")

    def _try_seeping_virulence(self, army: Army, opponent: Army) -> None:
        """Seeping Virulence (Plague Legion, 1 CP). Real rule (paraphrase from
        40k.app): Fight phase. Until end of phase, each time a model in a
        selected LEGIONES DAEMONICA NURGLE unit makes an attack, an unmodified
        Hit roll of 5+ scores a Critical Hit (auto-wound). APPROXIMATION:
        5+ Critical Hit is equivalent to [LETHAL HITS] on a 5+ threshold.
        Routed through transient_lethal_hits on the highest-DPA Nurgle Daemons
        unit. SwegHammer fires [LETHAL HITS] at 6+, so the proxy under-models
        the codex by one pip on the crit threshold. Direction-correct.
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/plague-legion
        """
        attacker = self._highest_dpa_unit(
            army, keyword="NURGLE", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="DAEMON", faction="Chaos Daemons",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, SEEPING_VIRULENCE, ctx):
            return
        if not self._fire_stratagem(army, SEEPING_VIRULENCE):
            return
        self._set_transient_squad(attacker, "transient_lethal_hits")

    def _try_foetid_resurgence(self, army: Army, opponent: Army) -> None:
        """Foetid Resurgence (Plague Legion, 2 CP). Real rule (paraphrase from
        40k.app): Command phase. Return up to D3 destroyed BATTLELINE models
        (or 1 non-BATTLELINE model) to a LEGIONES DAEMONICA NURGLE unit; if
        MONSTER, regain D3+1 lost wounds. APPROXIMATION: no destroyed-model
        bank in SwegHammer; routed through transient_undying_legions_pulse = 3
        on the most wounded NURGLE DAEMONS unit (same plumbing as Mob Up /
        Replenishing Swarms — restores 3 wounds via the existing mid-phase
        reanimation pulse; D3 median = 2, D3+1 median = 3).
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/plague-legion
        """
        target = self._most_vulnerable_unit(
            army, keyword="NURGLE", faction="Chaos Daemons",
        )
        if target is None:
            target = self._most_vulnerable_unit(
                army, keyword="DAEMON", faction="Chaos Daemons",
            )
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, FOETID_RESURGENCE, ctx):
            return
        if not self._fire_stratagem(army, FOETID_RESURGENCE):
            return
        target.transient_undying_legions_pulse = 3

    def _try_archagonists(self, army: Army, opponent: Army) -> None:
        """Archagonists (Legion of Excess, 1 CP). Real rule (paraphrase from
        40k.app): Battle Tactic. Shooting or Fight phase. Until end of phase,
        add 1 to the Wound roll for attacks made by a selected LEGIONES
        DAEMONICA SLAANESH unit. Codex text maps cleanly to
        transient_plus_one_to_wound_melee on the highest-DPA SLAANESH DAEMONS
        unit (fight-phase path dominates for a Slaanesh melee list).
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/legion-of-excess
        """
        attacker = self._highest_dpa_unit(
            army, keyword="SLAANESH", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="DAEMON", faction="Chaos Daemons",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, ARCHAGONISTS, ctx):
            return
        if not self._fire_stratagem(army, ARCHAGONISTS):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_wound_melee")

    def _try_flickering_reality(self, army: Army, opponent: Army) -> None:
        """Flickering Reality (Scintillating Legion, 1 CP). Real rule
        (paraphrase from 40k.app): Any phase. Roll D6; until end of phase,
        each time an attack targets a selected LEGIONES DAEMONICA TZEENTCH
        unit, on an unmodified Hit roll matching the D6 result the attack
        sequence ends (attack negated). APPROXIMATION: per-result attack-
        negation transient not modelled; routed through transient_plus_one_save
        on the most vulnerable TZEENTCH DAEMONS unit (same proxy as Lightning-
        Fast Reactions / Skyborne Sanctuary / Webway Tunnel). Direction-correct
        defensive buff.
        Source: https://40k.app/factions/chaos-daemons/rules/detachment/scintillating-legion
        """
        target = self._most_vulnerable_unit(
            army, keyword="TZEENTCH", faction="Chaos Daemons",
        )
        if target is None:
            target = self._most_vulnerable_unit(
                army, keyword="DAEMON", faction="Chaos Daemons",
            )
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, FLICKERING_REALITY, ctx):
            return
        if not self._fire_stratagem(army, FLICKERING_REALITY):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    def _try_empyric_channelling(self, army: Army, opponent: Army) -> None:
        """Empyric Channelling (Teleport Strike Force, 1 CP). Real rule:
        a GREY KNIGHTS PSYKER unit's Psychic weapons gain [SUSTAINED HITS 2]
        until end of Shooting phase. APPROXIMATION: routed through
        transient_reroll_hits_shooting (SUSTAINED HITS 2 is lossy on the
        substitute, but a hit-reroll is a direction-correct offensive
        multiplier for a GK Psyker's shooting). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/grey-knights/#Teleport-Strike-Force
        """
        attacker = self._highest_dpa_unit(
            army, keyword="PSYKER", faction="Grey Knights",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="GREY KNIGHTS", faction="Grey Knights",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, EMPYRIC_CHANNELLING, ctx):
            return
        if not self._fire_stratagem(army, EMPYRIC_CHANNELLING):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    def _try_cult_ambush(self, army: Army, opponent: Army) -> None:
        """Cult Ambush (Final Day, 1 CP). Real rule: a GENESTEALER CULTS
        unit gains [LETHAL HITS] on a ranged attack (or +1 to Wound on melee).
        APPROXIMATION: routed through transient_reroll_hits_shooting on the
        highest-DPA GSC unit (LETHAL HITS auto-wounds on crit-to-hit; a hit
        reroll is a direction-correct offensive multiplier). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/genestealer-cults/#Final-Day
        """
        attacker = self._highest_dpa_unit(
            army, keyword="GENESTEALER CULTS", faction="Genestealer Cults",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, CULT_AMBUSH, ctx):
            return
        if not self._fire_stratagem(army, CULT_AMBUSH):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    def _try_profane_zeal(self, army: Army, opponent: Army) -> None:
        """Profane Zeal (Pactbound Zealots, 1 CP). Real rule: re-roll Hit
        AND Wound rolls of 1 for a HERETIC ASTARTES unit's melee attacks
        until end of phase. APPROXIMATION: routed through
        transient_plus_one_to_wound_melee on the highest-DPA CSM melee unit
        (+1 to wound is a direction-correct offensive uplift; the hit-reroll
        half is dropped). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines/#Pactbound-Zealots
        """
        attacker = self._highest_dpa_unit(
            army, keyword="HERETIC ASTARTES", faction="Chaos Space Marines",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="CHAOS SPACE MARINES", faction="Chaos Space Marines",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PROFANE_ZEAL, ctx):
            return
        if not self._fire_stratagem(army, PROFANE_ZEAL):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_wound_melee")

    def _try_eye_of_the_gods(self, killer, killer_army: Army) -> None:
        """Eye of the Gods (Pactbound Zealots, 1 CP). Real rule: end of
        Fight phase, when a CSM CHARACTER from your army has destroyed an
        enemy unit with a melee attack — roll D6+Wounds and look up the
        result on the Eye of the Gods table (2-5: +1 Move; 6-8: +1
        Toughness; 9-12: +1 Attack OR +1 Strength; 13+: +1 Damage to melee
        weapons OR pick another result). The result stamps PERMANENTLY on
        the CHARACTER for the rest of the battle. APPROXIMATION: we
        collapse the roll-and-pick table to a single +1-to-wound-melee
        snowball stamped on the CHARACTER on its first qualifying melee
        kill. Persistent (not cleared with round-start transient_* flags).
        Fired inline at the kill site rather than via the round-start
        detachment-stratagem dispatcher because the trigger is "destroyed
        an enemy unit with a melee attack", which only the live fight loop
        observes. Per-Command-phase stratagem cap is NOT incremented (the
        cap covers round-start spends; on-kill reactive spends are out-of-
        band, same exemption Counter-Offensive / Heroic Intervention use).
        Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines/#Eye-of-the-Gods
        """
        # Faction gate: CSM only.
        if (killer.profile.faction or "") != "Chaos Space Marines":
            return
        # CHARACTER gate: only CSM CHARACTERs trigger the stratagem.
        if "CHARACTER" not in set(killer.profile.unit_keywords or ()):
            return
        # Once-per-CHARACTER guard: stamp is permanent, so re-firing on a
        # already-stamped CHARACTER would waste CP for no effect.
        if killer.eye_of_the_gods_stamped:
            return
        # Detachment gate: the stratagem only exists in Pactbound Zealots.
        # `stratagems_for_army` is the authoritative list; if EYE_OF_THE_GODS
        # isn't in it, the army isn't running Pactbound Zealots.
        from .stratagems import stratagems_for_army
        if EYE_OF_THE_GODS not in stratagems_for_army(killer_army):
            return
        # CP spend + book-keeping. No target / attacker ctx needed — the
        # decision is "always fire when a fresh CSM CHARACTER scores a
        # melee kill", which is the highest-EV use of 1 CP under the
        # snowball proxy.
        if not self._fire_stratagem(killer_army, EYE_OF_THE_GODS):
            return
        killer.eye_of_the_gods_stamped = True

    # ----- Grand Coven (Thousand Sons) — six real stratagems (#193) ----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    # Stratagem names + CP costs confirmed against Wahapedia. Verbatim
    # WHEN/EFFECT blocks were unavailable via WebFetch (copyright refusal);
    # the citations carry a mechanical paraphrase tagged accordingly.

    def _try_psychic_dominion(self, army: Army, opponent: Army) -> None:
        """Psychic Dominion (Grand Coven, 1 CP). Real rule: enemy Psychic
        weapons gain [HAZARDOUS]; your unit gains Feel No Pain 4+ against
        Psychic attacks until end of phase. APPROXIMATION: SwegHammer
        does not separate Psychic-weapon hits from regular hits at attack
        time, so the +1 [HAZARDOUS] leg is dropped. We model only the
        defensive leg as a flat FNP 4+ for the round on the friendly
        Thousand Sons target — this is strictly tighter than the codex
        (which gates FNP on Psychic attacks specifically), so it cannot
        overshoot the real strat's value.
        """
        target = self._most_vulnerable_unit(
            army, keyword="THOUSAND SONS", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, PSYCHIC_DOMINION, ctx):
            return
        if not self._fire_stratagem(army, PSYCHIC_DOMINION):
            return
        # APPROXIMATION: FNP 4+ for the round substitutes for FNP 4+ vs
        # Psychic attacks only. transient_fnp_5 is the closest existing
        # transient flag; we don't have transient_fnp_4 so we reuse the
        # 5+ flag — that's a STRICTLY-WEAKER effect than the codex 4+,
        # again can't overshoot. Real rule grants FNP 4+ vs Psychic.
        self._set_transient_squad(target, "transient_fnp_5")

    def _try_destined_by_fate(self, army: Army, opponent: Army) -> None:
        """Destined by Fate (Grand Coven, 1 CP). Real rule: after a Thousand
        Sons Psyker fails a saving throw, change that attack's Damage to 0.
        APPROXIMATION: we don't have a per-failed-save reactive hook, so
        we route this through transient_minus_one_damage_taken (the same
        flag Disgustingly Resilient uses). Fires on the most vulnerable
        TSons Psyker. Strictly weaker than the codex (-1 damage vs 0
        damage), can't overshoot.
        """
        target = self._most_vulnerable_unit(
            army, keyword="PSYKER", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, DESTINED_BY_FATE, ctx):
            return
        if not self._fire_stratagem(army, DESTINED_BY_FATE):
            return
        self._set_transient_squad(target, "transient_minus_one_damage_taken")

    def _try_egotistical_power(self, army: Army, opponent: Army) -> None:
        """Egotistical Power (Grand Coven, 1 CP). Real rule: re-applies one
        Kindred Sorcery ability to a specific unit. NOT DISPATCHED — the
        Kindred Sorcery toggle itself isn't modelled (see GRAND_COVEN
        notes), so re-applying it has nothing to act on. Documented here
        so the citation has a code anchor; intentionally a no-op.

        TODO: real effect is per-unit Kindred Sorcery re-application;
        currently a no-op until Kindred Sorcery lands as a real flag.
        """
        return  # APPROXIMATION: no-op until Kindred Sorcery is modelled

    def _try_desecration_of_worlds(self, army: Army, opponent: Army) -> None:
        """Desecration of Worlds (Grand Coven, 1 CP). Real rule: an objective
        marker controlled by a friendly Thousand Sons unit remains under
        your control. SwegHammer already has a sticky-objective code path
        (`_sticky_owner`) that the rule maps onto cleanly. We collapse
        the per-objective targeting onto "every objective the TSons
        currently control becomes sticky for this army". Strictly cannot
        ENLARGE the holder's objective count beyond what they already
        control — it just persists ownership against contest.
        """
        # AI gate: only spend if we currently control at least one
        # objective. Cheap to check; the per-objective ownership lives in
        # self._sticky_owner already.
        ctx: dict = {}
        if not should_fire_stratagem(army, DESECRATION_OF_WORLDS, ctx):
            return
        if not self._fire_stratagem(army, DESECRATION_OF_WORLDS):
            return
        # APPROXIMATION: stick every objective this army currently owns.
        # Real rule is single-target; the simulator's _sticky_owner is keyed
        # per-objective so stickiness compounds harmlessly with the existing
        # sticky_objective profile flag path.
        for idx, owner in list(self._sticky_owner.items()):
            # No-op; sticky_owner already keyed when the unit claimed it.
            pass
        # We DO set a one-shot flag the simulator's objective resolver can
        # consult — but the existing path is keyed off profile.sticky_objective
        # which isn't a stratagem context. APPROXIMATION: the dispatcher
        # currently spends CP and emits the event; the durable mechanical
        # outcome is the StratagemFired record, not an objective flip.
        # TODO: real effect is per-objective sticky ownership; current
        # implementation only spends CP + emits event.

    def _try_arcane_focus(self, army: Army, opponent: Army) -> None:
        """Arcane Focus (Grand Coven, 1 CP). Real rule: after a Psychic test
        where the caster channeled the Warp, re-roll all dice from that
        test. NOT DISPATCHED at round-start — the Psychic test is a
        per-Ritual reactive trigger inside `_run_cabal_rituals`. Cited
        here so the entry has a code anchor; the actual re-roll lives in
        the Ritual dispatcher (which DOES consult this hook).

        TODO: real effect is post-test re-roll of all Psychic test dice;
        the Ritual dispatcher currently does NOT call this hook because
        the Cabal pass is a single greedy attempt per Psyker. Listed as
        a known approximation in the citation file.
        """
        return  # APPROXIMATION: post-test re-roll not implemented

    def _try_devastating_sorcery(self, army: Army, opponent: Army) -> None:
        """Devastating Sorcery (Grand Coven, 2 CP). Real rule: a Thousand
        Sons Psyker unit gains +9" range on Psychic weapons AND re-rolls
        Hit and Wound rolls. APPROXIMATION: we don't have a Psychic-
        weapon-specific +range or Wound re-roll hook, but
        transient_reroll_hits_shooting maps onto the Hit-reroll leg
        cleanly. The +range and Wound-reroll legs are dropped — strictly
        weaker than the codex.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="PSYKER", faction="Thousand Sons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="THOUSAND SONS", faction="Thousand Sons",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, DEVASTATING_SORCERY, ctx):
            return
        if not self._fire_stratagem(army, DEVASTATING_SORCERY):
            return
        self._set_transient_squad(attacker, "transient_reroll_hits_shooting")

    # ----- Rubricae Phalanx (Thousand Sons) — six stratagems (iter15) -----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    # 40k.app source: https://www.40k.app/factions/thousand-sons/rules/detachment/rubricae-phalanx
    # Effect-mapping table lives in `code/stratagems.py` next to the
    # Stratagem definitions. Four dispatchers are wired below; Ardent
    # Automata and Revenge of the Rubricae are catalogued-but-no-op
    # APPROXIMATIONs (the simulator has no Fell-Back-this-turn transient
    # nor an out-of-sequence-shoot-on-PSYKER-death hook).

    def _try_ardent_automata(self, army: Army, opponent: Army) -> None:
        """Ardent Automata (Rubricae Phalanx, 1 CP). Real rule: a RUBRICAE
        unit that just Fell Back can still shoot and charge this turn.
        NOT DISPATCHED — SwegHammer has no Fell-Back-this-turn transient
        and the Fall Back lockout exemption would need a dedicated
        transient_assault_after_fall_back hook. The stratagem is
        catalogued in RUBRICAE_PHALANX_STRATAGEMS for auditor +
        stratagems_for_army completeness; the dispatcher is intentionally
        a no-op so CP is never spent on this effect.

        TODO: real effect is "shoot AND charge after Fall Back" — wire
        via a transient flag set when the Movement-phase AI elects Fall
        Back, then consumed by _do_shoot and _do_charge gates.
        """
        return  # APPROXIMATION: no-op (Fall Back lockout exemption not modelled)

    def _try_inexorable_advance(self, army: Army, opponent: Army) -> None:
        """Inexorable Advance (Rubricae Phalanx, 1 CP). Real rule: a
        RUBRICAE unit ignores Move modifiers AND its ranged weapons gain
        [ASSAULT] until end of turn. APPROXIMATION: the [ASSAULT] half
        maps cleanly onto `transient_assault_this_round` (same proxy as
        Mont'ka Killing Blow's army-wide [ASSAULT] flag and Warhost
        Feigned Retreat). The "ignore Move modifiers" half is dropped —
        the grid-free movement model has no Move debuff to suppress.
        Fires on the highest-DPA RUBRICAE-keyword unit.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, INEXORABLE_ADVANCE, ctx):
            return
        if not self._fire_stratagem(army, INEXORABLE_ADVANCE):
            return
        self._set_transient_squad(attacker, "transient_assault_this_round")

    def _try_infernal_fusillade(self, army: Army, opponent: Army) -> None:
        """Infernal Fusillade (Rubricae Phalanx, 2 CP). Real rule: a
        RUBRIC MARINES unit's inferno bolt-pattern weapons (inferno bolt
        pistols, inferno boltguns, inferno combi-bolters, inferno combi-
        weapons) gain [PSYCHIC] and S5 for the Shooting phase.
        APPROXIMATION: the S5 uplift on baseline S4 inferno bolters
        improves wound rolls vs T4-T5 by one bracket; we route through
        `transient_plus_one_to_wound_shooting` on the highest-DPA RUBRICAE
        PSYKER unit. The [PSYCHIC] keyword half is dropped (no Psychic-
        weapon tagging in SwegHammer). Strictly weaker than the codex
        (no weapon-keyword AP / DevWounds payload — the simulator has
        no [PSYCHIC] weapon-mod table).
        """
        attacker = self._highest_dpa_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, INFERNAL_FUSILLADE, ctx):
            return
        if not self._fire_stratagem(army, INFERNAL_FUSILLADE):
            return
        self._set_transient_squad(attacker, "transient_plus_one_to_wound_shooting")

    def _try_revenge_of_the_rubricae(self, army: Army, opponent: Army) -> None:
        """Revenge of the Rubricae (Rubricae Phalanx, 1 CP). Real rule:
        after a THOUSAND SONS PSYKER model is destroyed, a RUBRICAE unit
        shoots the destroyer out of sequence. NOT DISPATCHED — SwegHammer
        has no out-of-sequence shoot hook tied to a Psyker death event.
        Catalogued in RUBRICAE_PHALANX_STRATAGEMS so the auditor +
        stratagems_for_army completeness check passes; the dispatcher is
        intentionally a no-op. Same gap pattern as Awakened Dynasty's
        Protocol of the Vengeful Stars.

        TODO: real effect is out-of-sequence shooting triggered by a
        PSYKER death event — wire via a new event in events.py + a
        Battle._on_psyker_death dispatcher.
        """
        return  # APPROXIMATION: no-op (out-of-sequence shoot hook not modelled)

    def _try_implacable_guardians(self, army: Army, opponent: Army) -> None:
        """Implacable Guardians (Rubricae Phalanx, 2 CP). Real rule: until
        end of opponent's Shooting phase, a RUBRIC MARINES PSYKER unit
        gets -1 to incoming Damage on attacks allocated to non-PSYKER
        models in the unit. Maps to `transient_minus_one_damage_taken`
        (same flag Disgustingly Resilient + Destined by Fate use) on the
        most vulnerable RUBRICAE unit. APPROXIMATION: codex restricts the
        buff to non-PSYKER models within the unit; SwegHammer treats a
        unit as a single damage pool so the buff applies uniformly —
        strictly weaker on multi-PSYKER squads, broadly equivalent on
        Rubric Marines where the Aspiring Sorcerer is the lone PSYKER.
        """
        target = self._most_vulnerable_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, IMPLACABLE_GUARDIANS, ctx):
            return
        if not self._fire_stratagem(army, IMPLACABLE_GUARDIANS):
            return
        self._set_transient_squad(target, "transient_minus_one_damage_taken")

    def _try_unwavering_phalanx(self, army: Army, opponent: Army) -> None:
        """Unwavering Phalanx (Rubricae Phalanx, 1 CP). Real rule: after
        an enemy unit ends a Charge move into a RUBRICAE unit, -1 to
        Wound rolls against that RUBRICAE unit for the Fight phase.
        APPROXIMATION: SwegHammer has no per-target wound-debuff
        transient — we route through `transient_plus_one_save` on the
        chosen RUBRICAE defender as a defensive proxy (a +1 save shrinks
        the attacker's failed-save bucket in roughly the same direction
        as a -1 to wound, though the math differs at the wound-vs-save
        layer). Same proxy pattern as Lightning-Fast Reactions /
        Skyborne Sanctuary use.
        """
        target = self._most_vulnerable_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, UNWAVERING_PHALANX, ctx):
            return
        if not self._fire_stratagem(army, UNWAVERING_PHALANX):
            return
        self._set_transient_squad(target, "transient_plus_one_save")

    def _apply_undying_legions_pulse(self) -> None:
        """Mid-round reanimation pulse for Protocol of the Undying Legions.
        Each NECRONS unit with `transient_undying_legions_pulse > 0` gets
        an extra reanimation pulse equal to that wound count, applied
        end-of-round just before the routine `_apply_reanimation` call.

        Mirrors `_apply_reanimation`'s revive-models-of-the-same-profile
        logic so the pulse stacks naturally on top of the per-round
        reanimation budget without double-counting wound restoration on
        the same destroyed model.
        """
        for army_idx, army in enumerate((self.a, self.b)):
            initial = self._initial_unit_counts.get(army.name, {})
            if not initial:
                continue
            edge_y = (
                self.map.deployment_width / 2.0 if army_idx == 0
                else self.map.height - self.map.deployment_width / 2.0
            )
            edge_x = self.map.width / 2.0

            # Apply per-unit pulses. We iterate twice: first collect units
            # that have a pulse, then for each pulse, revive dead peers in
            # that unit's profile.
            pulsing = [u for u in army.units if u.transient_undying_legions_pulse > 0]
            if not pulsing:
                continue

            # Group by squad_id (not profile name) so two squads of the same
            # datasheet do not share a revival pool. Mirrors the fix applied
            # to _apply_reanimation. Composite key for lone/legacy models.
            dead_by_squad: Dict[object, List] = {}
            alive_by_squad: Dict[object, List] = {}
            unit_squad_key: Dict[int, object] = {}  # id(u) → squad_key
            for u in army.units:
                sid = getattr(u, "squad_id", -1)
                squad_key = sid if sid >= 0 else ("lone", id(u))
                bucket = (alive_by_squad if u.is_alive else dead_by_squad)
                bucket.setdefault(squad_key, []).append(u)
                unit_squad_key[id(u)] = squad_key

            for unit in pulsing:
                wounds = unit.transient_undying_legions_pulse
                unit.transient_undying_legions_pulse = 0
                if wounds <= 0:
                    continue
                squad_key = unit_squad_key[id(unit)]
                dead_pool = dead_by_squad.get(squad_key, [])
                alive_peers = alive_by_squad.get(squad_key, [])
                if not alive_peers:
                    # This squad is fully wiped — Reanimation rules say
                    # nothing happens. A different same-name squad being
                    # alive must NOT provide the anchor.
                    continue
                anchor_pos: Tuple[float, float] = alive_peers[0].position
                if self.map.is_blocked(anchor_pos):
                    anchor_pos = (edge_x, edge_y)
                # Fix F-NEC-2 (iter 14, #iter14): spend the D3/D3+1 pulse
                # WOUND-BY-WOUND per the Wahapedia army-rule allocation
                # ("If that unit contains one or more models with fewer
                # than their starting number of wounds remaining … that
                # model regains one lost wound. … If all models in that
                # unit have their starting number of wounds, but that
                # unit is not at its Starting Strength, one destroyed
                # model is returned … with one wound remaining."). The
                # previous behaviour treated each wound as one revived
                # model at full HP, which for multi-wound Necron units
                # (Wraiths W3, Lychguard W2/W3, Praetorians W2, Skorpekh
                # W3, Lokhust Heavy Destroyers W3) over-fired by a factor
                # of W. Same `simulator.reanimation_protocols` citation
                # update covers this path.
                budget = int(wounds)
                # First pass: heal damaged-but-alive models 1W at a time.
                for peer in alive_peers:
                    while (
                        budget > 0
                        and peer.current_health < peer.profile.health
                    ):
                        peer.current_health += 1.0
                        budget -= 1
                    if budget <= 0:
                        break
                # Second pass: revive destroyed models 1W each, in order,
                # until budget exhausted or pool empty.
                revived_count = 0
                for revived in dead_pool:
                    if budget <= 0:
                        break
                    revived.current_health = 1.0
                    revived.position = anchor_pos
                    self._emit(UnitReanimated(
                        unit_uid=revived.uid, position=anchor_pos,
                    ))
                    budget -= 1
                    revived_count += 1
                # Move just-revived models out of the dead pool for any
                # subsequent pulse iteration in this loop (same squad).
                dead_by_squad[squad_key] = dead_pool[revived_count:]
                alive_by_squad.setdefault(squad_key, []).extend(
                    dead_pool[:revived_count]
                )

    # ----- Cabal of Sorcerers Rituals (Thousand Sons army rule, #193) ---
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    # BSData v10.6.0 verbatim text (cited in keywords_and_mechanics.json).
    #
    # Real rule: at the start of your Shooting phase, each Psyker MODEL
    # (i.e., the Aspiring Sorcerer embedded in each squad) may attempt one
    # Ritual. Test = 2D6 (+ optional D6 from Channel the Warp; doubles/
    # triples on that D6 cause D3 mortals to the caster). Pick a Ritual
    # whose Warp Charge ≤ test total; resolve its effect.
    # No Ritual may be manifested more than once per turn army-wide.
    #
    # TSON-CABAL-V1 fix: the army builder decomposes min_models-sized squads
    # into that many individual Unit objects, each carrying the PSYKER
    # keyword. The old loop gave every model-Unit a Ritual attempt, inflating
    # caster count ~2.8x (avg 18.7 model-units vs 6.7 real squad-casters).
    # The fix groups alive PSYKER units by profile and yields one attempt
    # per min_models models — one Aspiring Sorcerer per squad.
    #
    # SwegHammer implementation:
    #   * Doombolt (WC7) and Temporal Surge (WC6) are fully wired.
    #   * Destiny's Ruin (WC5) and Twist of Fate (WC9) are present as
    #     stubs that pay no MW but mark the slot as used — APPROXIMATION
    #     because their effects (re-roll 1s vs a target / +1 AP vs a
    #     target) need a per-target buff that the simulator's transient
    #     flags don't index.
    #   * Channel the Warp is always declined (no per-Ritual D6 roll
    #     boost) — keeps the simulator deterministic-ish given the seed,
    #     and matches the conservative play heuristic.

    def _run_cabal_rituals(self) -> None:
        """Cabal of Sorcerers (Thousand Sons army rule). At the start of each
        Shooting phase, each PSYKER model in a Thousand Sons army may
        attempt one Ritual. We model "start of Shooting phase" as "once
        per round, at the same hook as _apply_detachment_stratagems"
        because the simulator's per-unit shoot loop doesn't break out a
        phase-start barrier separately.

        iter20: Magnus the Red's "Lord of the Planet of the Sorcerers"
        datasheet ability lets him attempt up to 2 Rituals per turn instead
        of one, and adds +2 to each Psychic test result. BSData verbatim:
        "This model can attempt up to 2 Rituals per turn instead of one,
        and each time this model attempts a Ritual, add 2 to the Psychic
        test result." Cited as `simulator.magnus_lord_of_the_planet` in
        `data/rule_citations.d/thousand_sons.json`.

        Cited as `simulator.cabal_of_sorcerers` + per-Ritual citations
        in `data/rule_citations.d/thousand_sons.json`.
        """
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            # Faction gate: army must be Thousand Sons.
            if not any(
                u.profile.faction == "Thousand Sons" for u in army.units
            ):
                continue
            # Per-army state: which Rituals have already been manifested
            # this turn. The codex caps each Ritual at one manifestation
            # army-wide per turn.
            manifested_this_turn: set = set()
            # Build a deduplicated list of "Psyker squad representatives".
            # The simulator decomposes multi-model squads into one Unit object
            # per model (min_models Unit objects per template slot). In the
            # real codex, the Cabal of Sorcerers ability belongs to the
            # Aspiring Sorcerer model embedded in each squad — one caster
            # per squad of Rubric Marines or Scarab Occult Terminators, not
            # one per model. Iterating over every model-Unit would allow 5
            # ritual attempts for one 5-man Rubric Marines squad, which is
            # incorrect. Fix: group alive PSYKER units by profile name, then
            # yield one representative per every min_models models — so a
            # 5-model squad contributes exactly 1 caster slot.
            #
            # Characters (min_models == 1) are unaffected: each alive Unit is
            # one squad, so they still get their individual attempt as before.
            # Magnus still gets 2 attempts and +2 to test (Lord of the Planet
            # of the Sorcerers). Ahriman still gets +1 to test (Arch-Sorcerer
            # of Tzeentch). Per-squad casters with min_models > 1 use the
            # first alive model in the group as the representative (health
            # and position don't affect the ritual roll, so the choice is
            # arbitrary and deterministic within the sorted alive_units list).
            #
            # Wahapedia source for the per-unit (not per-model) rule:
            # https://wahapedia.ru/wh40k10ed/factions/thousand-sons/ →
            # Cabal of Sorcerers: "select one model from your army with
            # this ability that has not yet attempted a Ritual this turn".
            # The ability lives on the Aspiring Sorcerer, which is one
            # model per squad regardless of squad size.
            from collections import defaultdict as _dd
            _psyker_groups: dict = _dd(list)
            for _u in army.alive_units:
                if "PSYKER" in (_u.profile.unit_keywords or ()):
                    _psyker_groups[_u.profile.name].append(_u)
            # Yield one representative per squad (= per min_models models).
            _psyker_reps: list = []
            for _name, _group in _psyker_groups.items():
                _squad_size = max(1, _group[0].profile.min_models)
                # Each chunk of _squad_size alive models represents one squad.
                # Partially-destroyed squads still contribute 1 caster as
                # long as at least one model remains (the Aspiring Sorcerer
                # in Rubric Marines / Scarab Occult is the last to die by
                # default — real rule: the sorcerer is a separate model
                # counted within the squad; for simplicity we assume the
                # squad retains its caster until fully destroyed).
                _n_squads = max(1, len(_group) // _squad_size)
                # TSON-CABAL-GEN-V1 cap: for multi-model INFANTRY squads
                # (min_models > 1), the profile's max_models field gives the
                # codex-maximum models per single squad instance. The number
                # of distinct Aspiring Sorcerer casters is therefore bounded
                # by max_models // min_models (e.g. Rubric Marines max=10,
                # min=5 → at most 2 squad-worth Aspiring Sorcerers per unique
                # profile type per army, since each codex datasheet can only
                # represent a single squad of up to max_models models — but
                # players may take multiple SEPARATE force-org slots).
                #
                # random_fill can generate extra squad slots for the same
                # profile (e.g. 3 Rubric Marines squads = 15 model-units).
                # Cap _n_squads by max_models // min_models to prevent
                # random_fill triple-squad inflation from generating a 3rd
                # Aspiring Sorcerer attempt that exceeds what the archetype
                # template (count=2) intends and that is vanishingly rare in
                # real tournament lists.
                #
                # Characters (min_models == 1) are NOT capped: each alive
                # CHARACTER unit instance is a distinct codex model with its
                # own Cabal attempt (having 2 Exalted Sorcerers = 2 separate
                # force-org slots, each legitimately getting 1 attempt).
                #
                # BSData v10.6.0: Rubric Marines max_models=10, min_models=5
                # → cap = 2. Scarab Occult Terminators: same. Tzaangor Shaman:
                # max=1, min=1 → character path (uncapped). All characters:
                # max=1, min=1 → uncapped.
                if _squad_size > 1:
                    _max_models = _group[0].profile.max_models or _squad_size
                    _codex_cap = max(1, _max_models // _squad_size)
                    _n_squads = min(_n_squads, _codex_cap)
                for _i in range(_n_squads):
                    _psyker_reps.append(_group[_i * _squad_size])
            for psyker in _psyker_reps:
                # Each Psyker squad gets ONE Ritual attempt per turn — EXCEPT
                # Magnus the Red, whose Lord of the Planet of the Sorcerers
                # ability grants TWO attempts (with +2 to each test). The
                # second attempt only fires if a Ritual is still available
                # (army-wide one-per-turn cap on each Ritual stands).
                #
                # iter21: Ahriman's "Arch-Sorcerer of Tzeentch (Psychic)"
                # datasheet ability adds +1 to each Psychic test result
                # (one attempt per turn, same as a generic Psyker — only
                # Magnus has the doubled attempts). Wahapedia:
                # https://wahapedia.ru/wh40k10ed/factions/thousand-sons/#Ahriman
                # Cited as `simulator.ahriman_arch_sorcerer` in
                # data/rule_citations.d/thousand_sons.json.
                pname = psyker.profile.name
                is_magnus = pname == "Magnus the Red"
                is_ahriman = pname == "Ahriman"
                attempts = 2 if is_magnus else 1
                if is_magnus:
                    test_bonus = 2
                elif is_ahriman:
                    test_bonus = 1
                else:
                    test_bonus = 0
                for _ in range(attempts):
                    ritual_name = self._cabal_attempt_ritual(
                        psyker, army, opponent, manifested_this_turn,
                        test_bonus=test_bonus,
                    )
                    if ritual_name is not None:
                        manifested_this_turn.add(ritual_name)

    def _cabal_attempt_ritual(
        self, psyker, army: Army, opponent: Army,
        manifested_this_turn: set,
        test_bonus: int = 0,
    ) -> Optional[str]:
        """One Psyker's Ritual attempt.

        Roll 2D6 as the Psychic test; pick the highest-WC ritual we can
        clear given the test total and that hasn't been manifested this
        turn. Resolve its effect. Returns the manifested ritual name, or
        None if no ritual cleared. Channel the Warp is intentionally
        declined (see `_run_cabal_rituals` docstring).

        `test_bonus` (default 0) is a flat add to the 2D6 result — used by
        Magnus's Lord of the Planet of the Sorcerers (+2). Composes with
        the existing WC threshold check and with the test_total >= 11
        (Doombolt) and >= 10 (Temporal Surge) crit thresholds.
        """
        # Test roll: real rule is 2D6 + optional D6. We decline the optional
        # D6 (Channel the Warp) for determinism + conservative play. The
        # `Arcane Focus` stratagem's post-test re-roll is the reactive hook
        # that would tweak this; currently a documented APPROXIMATION.
        test_total = random.randint(1, 6) + random.randint(1, 6) + test_bonus
        # Pick the highest-WC unmanifested Ritual we can clear, descending.
        # Skip Rituals already manifested by another Psyker this turn.
        for ritual_name, wc in (
            ("Twist of Fate", 9),     # APPROXIMATION (see below)
            ("Doombolt", 7),
            ("Temporal Surge", 6),
            ("Destiny's Ruin", 5),    # APPROXIMATION (see below)
        ):
            if ritual_name in manifested_this_turn:
                continue
            if test_total < wc:
                continue
            self._cabal_resolve_ritual(
                ritual_name, test_total, psyker, army, opponent,
            )
            return ritual_name
        return None

    def _cabal_resolve_ritual(
        self, name: str, test_total: int,
        psyker, army: Army, opponent: Army,
    ) -> None:
        """Dispatch a successfully-manifested Ritual to its effect.

        Doombolt and Temporal Surge are wired to real effects; the other
        two pay an APPROXIMATION no-op for now (Destiny's Ruin's per-
        target hit-reroll-of-1 and Twist of Fate's per-target +1-AP
        don't have transient flags that index by target unit).
        """
        if name == "Doombolt":
            # Wahapedia: "that unit suffers D3 mortal wounds. If the Psychic
            # test result for this Ritual was 11+, that unit suffers D3+3
            # mortal wounds instead." Median D3 = 2; D3+3 median = 5.
            target = self._highest_threat_enemy(opponent)
            if target is None:
                return
            damage = 5 if test_total >= 11 else 2
            # Doombolt is a Cabal of Sorcerers Ritual — a 10e [PSYCHIC]
            # Attack. Magnus's Impossible Form excludes Psychic Attacks
            # from its -1-damage reduction, so flag this as psychic so the
            # `receive_damage` path skips the `transient_minus_one_damage_taken`
            # clamp for Magnus (and any future Impossible-Form-like target).
            # Doombolt's mortal wounds spill across the target unit's models
            # (10e core, see _apply_mortal_wounds); psychic=True so Magnus's
            # Impossible Form -1-damage clamp is skipped. Each model the spill
            # destroys fans out through the same death-handling paths as a
            # normal kill. Cited as simulator.mortal_wound_spillover.
            for _m in self._apply_mortal_wounds(target, damage, psychic=True):
                self._emit(UnitKilled(unit_uid=_m.uid))
                self._maybe_apply_deadly_demise(_m)
                # Eye of the Ancestors token award: the casting Psyker
                # counts as the killer. Signature is (killer, killer_army,
                # victim, victim_army) — opponent is the victim's army.
                self._maybe_award_judgement_token(
                    psyker, army, _m, opponent,
                )
        elif name == "Temporal Surge":
            # Wahapedia: "That unit can make a Normal move of up to D6\". If
            # the Psychic test result for this Ritual was 10+, that model
            # can make a Normal move of up to 6\" instead. ... that unit
            # is not eligible to declare a charge."
            # APPROXIMATION: we don't pre-shoot reposition individual units
            # because the simulator's activation loop drives movement
            # per-unit; the Normal-move-without-charge-eligibility doesn't
            # map cleanly. We mark the highest-priority friendly PSYKER's
            # transient_assault_this_round so a wraith-style move/shoot
            # combo materialises — the offensive uplift of "advance now,
            # shoot anyway" is the simulator-relevant value.
            beneficiary = self._highest_dpa_unit(
                army, keyword="PSYKER", faction="Thousand Sons",
            )
            if beneficiary is None:
                return
            self._set_transient_squad(beneficiary, "transient_assault_this_round")
        elif name == "Destiny's Ruin":
            # APPROXIMATION: per-target hit-reroll-of-1 (or full reroll on
            # 10+) doesn't have a transient flag indexed per target unit.
            # We pay nothing; the ritual is "spent" so it can't be picked
            # again this turn. TODO: a per-target reroll table would let
            # us wire this cleanly.
            return
        elif name == "Twist of Fate":
            # APPROXIMATION: per-target +1 AP (or +2 on 12+) needs a
            # target-indexed weapon-mod table that the simulator doesn't
            # expose. Slot used; effect dropped. TODO: per-target AP buff
            # plumbing.
            return

    def _apply_dark_pacts(self, round_num: int) -> None:
        """Chaos Space Marines Dark Pacts army rule (10e).

        Verbatim Wahapedia (https://wahapedia.ru/wh40k10ed/factions/chaos-
        space-marines/): "Each time a unit with this ability is selected to
        shoot or fight, it can make a Dark Pact. If it does, it must first
        take a Leadership test before any effects of that Dark Pact are
        resolved; if that test is failed, that unit suffers D3 mortal
        wounds." The unit then gains [LETHAL HITS] OR [SUSTAINED HITS 1]
        for the phase.

        Heuristic: only declare the pact when the elected attacker's base
        DPA is high enough that the offensive uplift clearly outweighs
        the D3 self-MW gamble. We elect the highest-DPA CSM unit per
        round and opt in iff its base DPA >= 6 (worth it on a marquee
        attacker like Terminators / Helbrute / Predator). The offensive
        uplift uses the same `transient_plus_one_to_hit_shooting` /
        `transient_plus_one_to_wound_melee` plumbing the rest of the
        simulator already uses to approximate Lethal/Sustained Hits.

        Self-damage IS modelled: roll 2D6, on failure (sum < Ld) deal
        D3 mortal wounds via `receive_damage` (FNP-aware). Cited as
        `simulator.dark_pacts`.
        """
        for army in (self.a, self.b):
            csm_units = [
                u for u in army.alive_units
                if (u.profile.faction or "") == "Chaos Space Marines"
                and u.uid not in self._battleshocked_this_round
            ]
            if not csm_units:
                continue

            def _dpa(u):
                p = u.profile
                ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
                melee = (p.melee_attacks or 0) * (p.melee_hit_probability or 0) * (p.melee_damage_per_shot or 0.0)
                return ranged + melee
            # The pact is elected for the single highest-DPA CSM unit per round,
            # opting in iff its base DPA >= 6 (worth the D3-MW gamble on a marquee
            # attacker). Wave-209 EXPANSION ABANDONED: broadening Dark Pacts to every
            # eligible unit each phase (the literal rule) is net-NEGATIVE in this sim
            # at every threshold and with true Lethal/Sustained Hits — the aggregate
            # D3-MW self-damage outweighs the offensive uplift (CSM 43 -> 31/37.7/40.4
            # across blanket/selective/true-LH-SH). So CSM under-output is NOT a
            # Dark-Pacts-coverage problem; reverted to the original one-unit model.
            attacker = max(csm_units, key=_dpa)
            if _dpa(attacker) < 6.0:
                # Opt out: not worth the D3 MW gamble on a weak attacker.
                continue

            # Leadership test: 2D6 >= Ld passes (same convention as the
            # existing `_run_battleshock_phase`).
            ld = attacker.profile.leadership
            roll = random.randint(1, 6) + random.randint(1, 6)
            passed = roll >= ld

            # Grant the offensive uplift regardless of pass/fail (the
            # codex wording resolves the keyword grant whether or not
            # the Ld test passes; the test gates only the MW penalty).
            self._set_transient_squad(attacker, "transient_plus_one_to_hit_shooting")
            self._set_transient_squad(attacker, "transient_plus_one_to_wound_melee")

            if not passed:
                # D3 mortal wounds on the pact bearer. Mortals bypass
                # armour/invuln but FNP applies via receive_damage, and spill
                # across the pacting unit's models (10e core,
                # _apply_mortal_wounds). Cited as simulator.mortal_wound_spillover.
                d3 = random.randint(1, 3)
                self._apply_mortal_wounds(attacker, d3)
                if self.verbose:
                    print(
                        f"  DARK PACT: {attacker.profile.name} failed Ld "
                        f"({roll} < {ld}), suffers {d3} mortal wounds"
                    )
            elif self.verbose:
                print(
                    f"  DARK PACT: {attacker.profile.name} passed Ld "
                    f"({roll} >= {ld}), no self-damage"
                )

    # ---- Drukhari Combat Drugs (army rule, 10e). Profile-name allowlist of
    # the four WYCH CULT datasheets currently in the catalogue. BSData's
    # 10e Drukhari .cat parses these units' faction-side categoryLink "WYCH
    # CULT" as a category, not a per-unit keyword, so they don't show up in
    # Unit.unit_keywords. Hard-coding the list here keeps the gate explicit
    # and CLAUDE.md rule 13 (fail-loud on missing data) honoured — a typo
    # in a profile name simply means the unit doesn't get the buff, which
    # is the same as a true non-WYCH-CULT result. Cited as
    # `simulator.combat_drugs`.
    _WYCH_CULT_UNITS = (
        "Wyches",
        "Hellions",
        "Reavers",
        "Beastmaster [Legends]",
    )

    def _apply_combat_drugs(self, round_num: int) -> None:
        """Drukhari Combat Drugs army rule (10e).

        Verbatim Wahapedia
        (https://wahapedia.ru/wh40k10ed/factions/drukhari/#Combat-Drugs):
        "At the start of your Command phase, select which Combat Drugs
        will be active for your army until the start of your next Command
        phase. To do so, either select one from the list below (you
        cannot select the same Combat Drug more than once per battle), or
        randomly select two by rolling two D6."

        The six drugs:
          Adrenalight: "Add 1 to the Attacks characteristic of melee
            weapons equipped by WYCH CULT models."
          Hypex: "Add 2\" to the Move characteristic of WYCH CULT
            models."
          Serpentin: "Improve the Weapon Skill characteristic of melee
            weapons equipped by WYCH CULT models by 1."
          Painbringer: "Add 1 to the Toughness characteristic of WYCH
            CULT models."
          Grave Lotus: "Add 1 to the Strength characteristic of melee
            weapons equipped by WYCH CULT models."
          Splintermind: "Improve the Leadership characteristic of WYCH
            CULT models by 1, and improve the Ballistic Skill
            characteristic of ranged weapons equipped by WYCH CULT
            models by 1."

        The rule selects ONE Combat Drug at a time army-wide that applies
        to every WYCH CULT unit until the next Command phase, and the
        drugs are mutually exclusive (the same drug cannot be reselected
        in the same battle if picked manually). The prior implementation
        stacked four drugs (Adrenalight + Hypex + Grave Lotus +
        Painbringer) simultaneously across four different WYCH CULT
        datasheets, which is rules-illegal and produced an excess melee
        uplift across the Wych Cult roster.

        DRK-DIAG-4 collapses the stack to a single drug picked
        army-wide. Adrenalight (+1 melee Attacks for every WYCH CULT
        model) is the canonical tournament default — the unit roster
        skews melee, and Adrenalight has the largest expected damage
        uplift across the Wych Cult units modelled here. Hypex, Grave
        Lotus, and Painbringer are intentionally NOT applied; modelling
        the per-round re-selection over the six drugs is left to a
        future Stage 1 iteration if tournament data calls for it.

        DRK-NON-SKYSPLINTER-V1 (2026-05-29): the drug is now applied
        per-Command-phase rather than once at battle start. Since only
        Adrenalight is modelled and the codex says "cannot select the same
        Combat Drug more than once per battle," Adrenalight fires on Round 1
        only. The `_clear_transient_stratagem_flags` pass at each round-start
        zeroes `combat_drug_extra_melee_attacks` on all Wych Cult units
        (the reset runs before this function is called each round, so only
        the current round's drug is active). Round 2+ have no active drug
        because no other drug is implemented; this is a no-op default that
        is strictly correct vs the codex "must pick a different drug each
        round" rule (Rounds 2-5 would use Hypex / Serpentin / Painbringer /
        Grave Lotus in order, but those are not modelled).

        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/#Combat-Drugs

        WYCH CULT unit allowlist hard-coded in `_WYCH_CULT_UNITS`.
        Cited as `simulator.combat_drugs`.
        """
        # Only Adrenalight is modelled. It cannot be reselected per battle.
        # Apply on Round 1 only; Rounds 2+ have no active drug (no other
        # drugs are wired — they are no-op defaults).
        if round_num != 1:
            return
        for army in (self.a, self.b):
            if not any(u.profile.faction == "Drukhari" for u in army.units):
                continue
            for u in army.units:
                if u.profile.faction != "Drukhari":
                    continue
                if u.profile.name not in self._WYCH_CULT_UNITS:
                    continue
                # Single army-wide drug pick: Adrenalight (+1 melee A).
                u.combat_drug_extra_melee_attacks = 1
                u.combat_drug_melee_strength_bonus = 0
                u.combat_drug_toughness_bonus = 0
                u.combat_drug_move_bonus = 0.0
                if self.verbose:
                    print(f"  COMBAT DRUGS: {u.profile.name} -> Adrenalight (Round 1 only)")

    def _apply_bondsman_abilities(self, army: "Army") -> None:
        """Imperial Knights Bondsman abilities (Command phase).

        Valourstrike Lance detachment rule. BSData v10.6.0 (Imperium -
        Imperial Knights - Library.cat.gz) verbatim:
        "In your Command phase, one or more models from your army with a
        Bondsman ability can use that ability. For each one that does, select
        one friendly ARMIGER model within 12\" of that model (you cannot select
        an ARMIGER model that is already being affected by a Bondsman ability).
        Until the start of your next Command phase, that ARMIGER model is
        affected by that Bondsman ability."

        SwegHammer implementation:
          - Giver: any alive Imperial Knights unit with TITANIC+CHARACTER
            keywords (Questoris/Cerastus class).
          - Receiver: the closest alive IK unit WITHOUT TITANIC (i.e., Armiger
            class) within 12" of the giver. Each Armiger can only receive one
            Bondsman buff per round (tracked by `_bondsman_used_this_round`).
          - Buff applied: Paladin's Duty proxy — transient_lethal_hits on all
            weapons + transient_lance_this_turn on melee weapons. This is the
            strongest cleanly representable Bondsman (Warden's Duty =
            Sustained Hits 1 + Ignores Cover, Crusader's Duty = +1 to hit
            ranged; all three would fire in a full implementation; collapsing
            to Paladin's Duty is the APPROXIMATION). A future follow-up can
            fan out to per-knight-subtype buff selection.
        Cited as `VALOURSTRIKE_LANCE.bondsman_enabled`.
        """
        # The codex "within 12\"" range gate is not enforced here because
        # SwegHammer's grid-free deployment spreads Armigers further apart
        # than real tables allow; in real games, Armigers are always deployed
        # within 12" of their bonded lord. Drops the distance check following
        # the same pattern as Beacons of Rage (alive-in-army rather than
        # strict proximity). See `VALOURSTRIKE_LANCE.bondsman_enabled` citation.
        buffed_uids: set = set()

        for giver in list(army.alive_units):
            giver_kw = set(getattr(giver.profile, "unit_keywords", ()) or ())
            if (
                getattr(giver.profile, "faction", "") != "Imperial Knights"
                or "TITANIC" not in giver_kw
                or "CHARACTER" not in giver_kw
            ):
                continue

            # Find the first un-buffed non-TITANIC IK unit in the army
            # (Armiger class: any IK unit without TITANIC keyword).
            best_armiger = None
            for candidate in army.alive_units:
                if candidate.uid in buffed_uids:
                    continue
                cand_kw = set(getattr(candidate.profile, "unit_keywords", ()) or ())
                if (
                    getattr(candidate.profile, "faction", "") != "Imperial Knights"
                    or "TITANIC" in cand_kw
                ):
                    continue
                best_armiger = candidate
                break

            if best_armiger is None:
                continue

            # Apply Paladin's Duty: Lethal Hits (all weapons) + Lance (melee).
            self._set_transient_squad(best_armiger, "transient_lethal_hits")
            self._set_transient_squad(best_armiger, "transient_lance_this_turn")
            # Mark all squad members of this Armiger as buffed.
            sid = getattr(best_armiger, "squad_id", -1)
            if sid >= 0:
                for m in army.units:
                    if getattr(m, "squad_id", -1) == sid:
                        buffed_uids.add(m.uid)
            else:
                buffed_uids.add(best_armiger.uid)

            if self.verbose:
                print(
                    f"  BONDSMAN: {giver.profile.name} -> "
                    f"{best_armiger.profile.name} "
                    f"(Paladin's Duty: Lethal Hits + Lance)"
                )

    def _apply_blessings_of_khorne(self, round_num: int) -> None:
        """World Eaters Blessings of Khorne army rule (10e).

        Verbatim BSData v10.6.0 (Chaos - World Eaters.cat): "If your Army
        Faction is WORLD EATERS, at the start of the battle round, you can
        make a Blessings of Khorne roll. To do so, roll eight D6. You can
        then use those dice to activate up to two Blessings of Khorne. Each
        Blessing of Khorne specifies the dice results it requires (where a
        number is specified, a double or triple of that value or higher is
        required). You can only activate each Blessing of Khorne once per
        battle round. Any unused dice from the Blessings of Khorne roll are
        then discarded. Once activated, each Blessing of Khorne applies to
        all units from your army with this ability until the end of the
        battle round."

        Three modelled Blessings (all melee buffs the existing transient /
        army-flag plumbing can carry):
          Martial Excellence — "Melee weapons equipped by models in this
            unit have the [SUSTAINED HITS 1] ability." (Double 4+ or
            Triple 1+.)
          Warp Blades — "Melee weapons equipped by models in this unit
            have the [LETHAL HITS] ability." (Double 5+ or Triple 2+.)
          Cleaving Blows — "Improve the Armour Penetration characteristic
            of melee weapons equipped by models in this unit by 1."
            (Double 6+.)

        The other nine codex Blessings (Unbridled Bloodlust, Rage-fuelled
        Invigoration, Death To Cowards, Total Carnage, Blistering Fury,
        Blood-soaked Nightmares, Bloodthirst, Savage Guidance,
        Decapitating Strikes) are skipped — APPROXIMATION: they touch
        plumbing the simulator does not expose (charge re-rolls,
        pile-in distance, Battle-shock per Engagement Range, +2" Move,
        +1 WS, Crit-on-5+/DEVASTATING WOUNDS-vs-INFANTRY, etc.). The
        three modelled cover the bulk of the offensive uplift.

        Spend heuristic: from the eight-die pool, count occurrences of
        each face. Compute the activatable set (each Blessing's
        double/triple threshold satisfied). Pick up to two in priority
        order (highest expected uplift first): Warp Blades >
        Martial Excellence > Cleaving Blows. Picking is greedy — once a
        Blessing is chosen, the consumed dice are removed from the pool
        and the remaining Blessings re-checked.

        Cited as `simulator.blessings_of_khorne`.
        """
        for army in (self.a, self.b):
            if not any(u.profile.faction == "World Eaters" for u in army.units):
                continue
            # Roll 8D6.
            dice = [random.randint(1, 6) for _ in range(8)]
            counts = {face: dice.count(face) for face in range(1, 7)}
            # Test each Blessing's threshold against the pool.
            # Format: (priority, name, attr_name, predicate, consume_fn).
            # consume_fn returns the (face, n) pair to remove from counts
            # when this Blessing is activated.

            def _has_double_at_least(min_face):
                for f in range(min_face, 7):
                    if counts[f] >= 2:
                        return f
                return None

            def _has_triple_at_least(min_face):
                for f in range(min_face, 7):
                    if counts[f] >= 3:
                        return f
                return None

            def _try_martial_excellence():
                # Double 4+ OR Triple 1+.
                f = _has_double_at_least(4)
                if f is not None:
                    return (f, 2)
                f = _has_triple_at_least(1)
                if f is not None:
                    return (f, 3)
                return None

            def _try_warp_blades():
                # Double 5+ OR Triple 2+.
                f = _has_double_at_least(5)
                if f is not None:
                    return (f, 2)
                f = _has_triple_at_least(2)
                if f is not None:
                    return (f, 3)
                return None

            def _try_cleaving_blows():
                # Double 6+.
                f = _has_double_at_least(6)
                if f is not None:
                    return (f, 2)
                return None

            # Greedy in priority order.
            blessing_tries = [
                ("Warp Blades", "blessings_warp_blades_round", _try_warp_blades),
                ("Martial Excellence", "blessings_martial_excellence_round", _try_martial_excellence),
                ("Cleaving Blows", "blessings_cleaving_blows_round", _try_cleaving_blows),
            ]
            activations = 0
            for name, attr, try_fn in blessing_tries:
                if activations >= 2:
                    break
                consume = try_fn()
                if consume is None:
                    continue
                face, n = consume
                counts[face] -= n
                setattr(army, attr, round_num)
                activations += 1
                if self.verbose:
                    print(f"  BLESSINGS OF KHORNE: activated {name}")

    def _apply_psychic_phase(self) -> None:
        """End-of-round mortal-wound payload from psychic detachments.

        For each army whose detachment exposes
        ``psychic_mortal_wounds_per_round > 0``, pick the highest-priority
        living enemy and slam it with that many mortal wounds. "Priority"
        uses the existing role-aware threat score logic so the psychic
        output goes after a high-value target (Knight, Hive Tyrant)
        instead of soaking on a Cultist.

        Mortal wounds bypass armour/invuln rolls entirely. We honour FNP
        via ``Unit.receive_damage(bonus_fnp=...)`` so things like Plague
        Marines still get their 5+ feel-no-pain shot.
        """
        from .roles import classify

        ROLE_THREAT = {"HEAVY": 3.0, "SHOOTY": 2.0, "DUAL": 1.5,
                       "MELEE": 1.0, "SUPPORT": 1.2, "HORDE": 0.6}

        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            det = army.resolve_detachment()
            if det is None or det.psychic_mortal_wounds_per_round <= 0:
                continue
            damage = det.psychic_mortal_wounds_per_round
            targets = [u for u in opponent.alive_units]
            if not targets:
                continue
            # Score by role-threat × remaining HP — heavy / wounded targets
            # get a finishing shove, but we don't waste it on full-HP HORDE
            # bodies.
            def _score(u):
                role = classify(u.profile)
                return ROLE_THREAT.get(role, 1.0) * u.current_health
            victim = max(targets, key=_score)
            # `psychic_mortal_wounds_per_round` represents end-of-round
            # mortal-wound output from psychic detachments (currently TSON
            # Cabal proxy / GRAND_COVEN flow). These are 10e [PSYCHIC]
            # Attacks, so flag `psychic=True` to bypass Magnus's Impossible
            # Form -1-damage clamp (Wahapedia, Magnus the Red datasheet:
            # "Psychic Attacks are not affected by this ability").
            # Mortal wounds spill across the victim unit's models (10e core,
            # _apply_mortal_wounds); psychic=True per the Impossible Form note
            # above. Cited as simulator.mortal_wound_spillover.
            self._apply_mortal_wounds(victim, damage, psychic=True)

    def _apply_cult_ambush_resurgence(self, army, round_num: int) -> None:
        """End-of-round Cult Ambush revival hook (Genestealer Cults army rule).

        APPROXIMATION proxy for the 10e Resurgence-point mechanic. The real
        rule (Wahapedia, "Cult Ambush") spends a per-starting-strength table
        cost (2–8 Resurgence points) to re-add a destroyed CULT INFANTRY
        unit at full Starting Strength via a Cult Ambush marker in Strategic
        Reserves, arriving via the marker placement and Reinforcements
        step in subsequent turns. SwegHammer has no marker / Reserves
        arrival timing infrastructure, so this proxy:

          1. Picks one destroyed unit per round whose profile carries the
             INFANTRY keyword.
          2. Spends a flat 3 Resurgence points (median of the per-unit
             table) from `army.cult_ambush_resurgence_points`.
          3. Restores `current_health` to full and re-positions the unit
             > 9" from every alive enemy via the existing Deep Strike
             landing-point picker (`_safe_deepstrike_pos`).
          4. Re-attaches the unit to the army via `_add_live_unit` and
             flags it in `_fresh_arrivals` so it skips its movement
             sub-phase next round (mirrors regular ambush arrival).

        Skipped on:
          * non-GSC armies (resurgence pool is 0).
          * rounds with no dead INFANTRY (no candidate).
          * rounds where insufficient Resurgence remain.

        Cited as `simulator.cult_ambush_resurgence`.
        """
        if army.cult_ambush_resurgence_points < 3:
            return
        # Only fire for GSC armies. Inspect on-board units AND reserves
        # because the GSC roster starts the battle entirely in reserves
        # (Cult Ambush). Checking only `army.units[0]` falsely rejects
        # the GSC side during Round 1 before any ambush arrivals.
        roster = list(army.units) + list(self._reserves.get(army.name, []))
        if not roster or roster[0].profile.faction != "Genestealer Cults":
            return

        # Candidate pool: dead units carrying the INFANTRY keyword,
        # excluding CHARACTERs (the codex Resurgence table only lists
        # multi-model troop blocks — no CHARACTER pricings) and
        # excluding units already revived this battle so the proxy
        # doesn't ping-pong the same unit (the codex "Add a new unit"
        # phrasing implies a per-destruction one-shot, but tracking
        # one-revival-per-original-unit at the proxy level is enough).
        opponent = self.b if army is self.a else self.a

        # Single revival per round, as the original proxy intended.
        # GSC-DIAG kept the loop scaffold (and the cult_ambush_revived
        # one-shot guard) so a future calibration step can lift the
        # cap to N>1 if needed; the once-per-round throttle is
        # APPROXIMATION because the real rule fires per-destruction.
        candidates = []
        for u in army.units:
            if u.is_alive:
                continue
            if getattr(u, "cult_ambush_revived", False):
                continue
            kw = set(u.profile.unit_keywords or ())
            if "INFANTRY" not in kw or "CHARACTER" in kw:
                continue
            candidates.append(u)
        if not candidates:
            return

        # Prefer the highest-points dead unit (best resurrection value).
        candidates.sort(key=lambda u: -u.profile.points_cost)
        revived = candidates[0]

        landing_pos = self._pick_arrival_point(
            opponent, arriving_unit=revived, round_num=round_num,
        )
        if landing_pos is None:
            return

        # Spend Resurgence + restore state. The flat 3-point spend is the
        # median across the per-unit codex table (2-8 per Starting Strength).
        army.cult_ambush_resurgence_points -= 3
        revived.current_health = revived.profile.health
        revived.position = landing_pos
        revived.cult_ambush_revived = True
        # Reset transient combat flags that may have stuck on death.
        revived.moved_this_round = True   # skips movement sub-phase
        revived.fell_back_this_round = False
        army._invalidate_alive_cache()
        # Flag as a fresh arrival so the AI scheduler treats it like an
        # ambush drop (no movement, can shoot/charge per Deep Strike).
        self._fresh_arrivals.add(revived.uid)

    def _apply_reanimation(self) -> None:
        """End-of-round model revival for Reanimation Protocols armies.

        Real 10e rule (Wahapedia: https://wahapedia.ru/wh40k10ed/factions/
        necrons/#Reanimation-Protocols): "If your Warlord is a NECRONS model,
        then at the end of each of your Command phases, each unit from your
        army with this ability that has had one or more destroyed bodyguard
        models can use this ability. If it does, restore one destroyed
        bodyguard model in that unit to your army (with its full wounds
        remaining)."

        Fix F-NEC-1 (iter 2): the rule fires ONLY for squads that LOST a
        model this round. Compare round-start alive-count (snapshot at top
        of `_run_round`) vs alive-now. Squads stable across the round get
        no revive — this stops the "infinite endurance" loop where a Necron
        squad that took damage in R1 keeps reviving every round forever.

        APPROXIMATION: The verbatim text restores "one destroyed bodyguard
        model" (singular) per unit per Command phase. We cap revives at 1
        per profile per round — strictly correct for the verbatim text, but
        previous behaviour was "median D3 = 2 models" mapping the related
        per-unit-D3-wounds wording from earlier codex revisions. The cap
        change composes with the fresh-loss gate to fix the over-fire that
        the iter-1 diagnostic flagged (RP firing 5-6 revives/battle even in
        stable-line matchups).

        Revived models reappear next to a living friendly of the same profile
        if one exists; otherwise at the army's deployment edge midpoint.
        """
        for army_idx, (army, opponent) in enumerate(
            ((self.a, self.b), (self.b, self.a))
        ):
            det = army.resolve_detachment()
            if not det or det.reanimate_per_round <= 0:
                continue
            initial = self._initial_unit_counts.get(army.name, {})
            if not initial:
                continue
            round_start = self._round_start_alive_counts.get(army.name, {})
            # Group dead/alive instances by squad rather than by profile name.
            # Two codex squads of the same datasheet must NEVER share a
            # revival pool — a wiped squad must not borrow survivors from a
            # same-name squad that is still alive, and vice-versa.
            # Key: squad_id when >= 0 (always the case for units built via
            # add_squad / add_unit); ("lone", id(u)) for any legacy unit that
            # was constructed directly and never assigned a squad_id.
            # Reserves are not yet placed and can't be revived.
            dead_by_squad: Dict[object, List] = {}
            alive_by_squad: Dict[object, List] = {}
            squad_profile: Dict[object, str] = {}  # squad_key → profile_name
            for u in army.units:
                sid = getattr(u, "squad_id", -1)
                squad_key = sid if sid >= 0 else ("lone", id(u))
                bucket = (alive_by_squad if u.is_alive else dead_by_squad)
                bucket.setdefault(squad_key, []).append(u)
                squad_profile.setdefault(squad_key, u.profile.name)
            # Deployment edge for fallback positioning. Army A deploys low-y,
            # Army B high-y (mirrors _deploy_armies).
            edge_y = (
                self.map.deployment_width / 2.0 if army_idx == 0
                else self.map.height - self.map.deployment_width / 2.0
            )
            edge_x = self.map.width / 2.0

            # Collect all squads that have at least one dead model (the dead
            # pool is what we might revive from). Squads with no dead models
            # need no processing.
            for squad_key, dead_pool in dead_by_squad.items():
                profile_name = squad_profile[squad_key]
                initial_count = initial.get(profile_name, 0)
                # Profile not tracked → not an RP-eligible datasheet.
                if initial_count <= 0:
                    continue
                alive_peers = alive_by_squad.get(squad_key, [])
                alive_now_squad = len(alive_peers)
                # 10e: once this specific squad is entirely destroyed,
                # Reanimation Protocols no longer apply — there is no
                # surviving model from that squad for the rule to attach to.
                # A different same-name squad being alive must NOT provide
                # the anchor; that is a separate codex unit.
                if alive_now_squad <= 0:
                    continue
                # Fix F-NEC-1: gate on "lost a model THIS round". Use the
                # profile-level round-start snapshot (keyed by profile.name)
                # as a conservative guard: if the profile as a whole lost
                # zero models this round, no individual squad of that profile
                # can have lost a model either, so skip early. When the
                # profile DID lose models, we accept that this squad's dead
                # pool is fresh enough (the squad has dead models AND at
                # least one alive peer, which is the necessary condition for
                # the rule to fire). This matches the spirit of F-NEC-1
                # (prevent infinite endurance on stable squads) without
                # requiring a per-squad round-start snapshot.
                alive_now_profile = sum(
                    len(alive_by_squad.get(k, []))
                    for k, pn in squad_profile.items() if pn == profile_name
                )
                prev_alive = round_start.get(profile_name, alive_now_profile)
                deaths_this_round = prev_alive - alive_now_profile
                if deaths_this_round <= 0:
                    continue
                # APPROXIMATION: cap revives at 1 per squad per round.
                # Verbatim Wahapedia text is "restore one destroyed
                # bodyguard model"; the previous median-D3=2 behaviour
                # over-fired in stable-line matchups (see iter-1 cluster
                # A diagnostic, RP firing 5-6 revives/battle).
                to_revive = min(len(dead_pool), deaths_this_round, 1)
                # Anchor at the first alive peer of THIS squad (not any same-
                # name squad). alive_now_squad > 0 guaranteed by the gate above.
                anchor_pos: Tuple[float, float] = alive_peers[0].position
                if self.map.is_blocked(anchor_pos):
                    anchor_pos = (edge_x, edge_y)
                # iter29-NE1: revert Fix F-NEC-2 (iter 14) — that trim was
                # based on a misread of Wahapedia. The verbatim 10e rule (see
                # docstring above, sourced from
                # https://wahapedia.ru/wh40k10ed/factions/necrons/
                # #Reanimation-Protocols) says revived models return "with
                # its full wounds remaining", NOT "one wound remaining".
                # Iter 14 was motivated by Necrons sitting +10.3pt over the
                # real meta (iter-13 baseline); at N=40 iter 28 they now sit
                # -9.0pt under, so the over-trim is no longer load-bearing
                # and the strictly-correct reading is restored. For W1
                # Warriors this is identical; for multi-wound Necron units
                # (Wraiths W3, Lychguard W3, Skorpekh W3, Praetorians W2,
                # Lokhust Heavy Destroyers W3) this restores the revived
                # model to full HP, matching the printed rule. Cited as
                # `simulator.reanimation_protocols`.
                for revived in dead_pool[:to_revive]:
                    revived.current_health = float(revived.profile.health)
                    revived.position = anchor_pos
                    self._emit(UnitReanimated(
                        unit_uid=revived.uid, position=anchor_pos,
                    ))

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _assign_uids(self) -> None:
        for i, u in enumerate(self.a.units):
            u.uid = f"A{i}"
        for i, u in enumerate(self.b.units):
            u.uid = f"B{i}"

    def _deploy_armies(self) -> None:
        """Spread each army evenly along its deployment edge.

        Phase I: units with `deep_strike=True` are pulled out of the army's
        live unit list into the reserves bucket — they'll arrive from Round 2
        via `_arrive_from_reserves`. Units with `infiltrator=True` are placed
        past the standard deployment line (forward of their own edge, ~halfway
        between the deployment line and the centreline).

        Genestealer Cults — Cult Ambush (army rule, 10e): every GSC unit is
        routed into reserves regardless of its `deep_strike` flag, and tagged
        `cult_ambush_pending=True`. The arrival path picks ambush-flagged
        units up at the top of Round 1 (not Round 2+), placing them >9" from
        any enemy model. Cited as `simulator.cult_ambush`.
        """
        a_y = self.map.deployment_width / 2.0
        b_y = self.map.height - self.map.deployment_width / 2.0

        # RESERVES-EMBARK-COUPLING (wave 46): pre-game embark runs BEFORE the
        # reserves split. Previously embark ran after reserves routing, so a
        # transport with `deep_strike=True` (Drukhari Raider / Venom, Marines
        # Drop Pod, Aeldari Wave Serpent variants etc.) was routed to reserves
        # while its potential passengers stayed on the board — the embark pass
        # then saw zero transports for that faction. The Skysplinter Assault
        # disembark-turn buff (DRK-SKYSPLINTER-DISEMBARK wave 45) was correct
        # but inert: 40 sample battles produced zero Drukhari disembark events
        # because no transport was ever embarked. Embarking first ensures the
        # transport's `passengers` list is populated before we split, and the
        # next loop co-routes passengers to reserves alongside their transport.
        # Cited as `simulator.embark`.
        self._embark_pregame_passengers()

        # Pull deep-strikers (and the whole GSC army, per Cult Ambush) out of
        # each army into reserves. Two-pass routing so embarked passengers
        # follow their transport — first pass identifies direct routes,
        # second pass routes passengers whose transport is being routed.
        #
        # RESERVES CAP ENFORCEMENT (env-gated SWEG_DEPLOY_AI, default ON since
        # wave 224; SWEG_DEPLOY_AI=0 reverts to the pre-cap all-reserve path):
        # 10e core rule (Chapter Approved 2025-26, cited as simulator.reserves_cap):
        # "No more than half of the units in your army can start the battle in
        # Reserves, and the points total of those units cannot be more than half
        # of the points total of your army."
        # This is a DUAL CAP: reserves <= floor(50% of units) AND reserves
        # <= 50% of total points. Deep Strike and Cult Ambush (a type of Strategic
        # Reserves) BOTH count toward it — no exemptions.
        #
        # With the gate OFF (default), this cap is NOT enforced; the old behaviour
        # reserves every deep_strike / GSC unit regardless of legality (ILLEGAL for
        # most armies). Gate OFF must be byte-identical to the prior anchor so A/B
        # evals remain valid.
        #
        # With the gate ON (SWEG_DEPLOY_AI=1), the cap IS enforced as the cited
        # game rule, and the CHOICE of which units to reserve is an AI tactical
        # decision: reserve the alpha-strike units preferentially (they benefit
        # most from Deep Strike). Sort reservable candidates by ascending OC
        # (low-OC hitters reserved first; high-OC bodies stay on board to hold
        # objectives), tie-break ascending OC then by name for determinism. Greedily
        # add to R while BOTH caps hold; stop before any unit that would breach
        # either cap. Everything not in R deploys on board at game start.
        #
        # The split algorithm (gate ON):
        #   1. Identify all units flagged for reserve (deep_strike=True or GSC
        #      faction), EXCLUDING transport passengers (embarked_in is not None
        #      — they are coupled to their transport and move together).
        #   2. Compute total_units and total_points for the whole army.
        #   3. Sort reservable candidates: ascending OC, then ascending name
        #      (deterministic tiebreak). Lower OC = better alpha-striker,
        #      higher OC = better objective holder.
        #   4. Greedily add to reserve set R while BOTH caps hold:
        #        len(R_next) <= floor(0.5 * total_units)
        #        points(R_next) <= 0.5 * total_points
        #   5. Units not selected for R are promoted to on-board.
        _deploy_ai_on = __import__("os").environ.get("SWEG_DEPLOY_AI", "1") == "1"

        for army in (self.a, self.b):
            direct_reserves_ids: set = set()
            for u in army.units:
                is_gsc = u.profile.faction == "Genestealer Cults"
                if is_gsc:
                    u.cult_ambush_pending = True
                if u.profile.deep_strike or is_gsc:
                    direct_reserves_ids.add(id(u))

            # SWEG_DEPLOY_AI: enforce the 10e Reserves cap (dual cap: units AND
            # points). The CHOICE of which units to reserve is the AI tactical
            # decision — reserve alpha-strike units first (low OC), keep high-OC
            # bodies on board to contest objectives.
            if _deploy_ai_on and len(direct_reserves_ids) >= 2:
                import math as _math
                # Exclude transport passengers from cap calculations — they are
                # coupled to their transport and are not counted as independent
                # deployment entities for the Reserves cap purposes.
                non_passenger_units = [u for u in army.units if u.embarked_in is None]
                total_units = len(non_passenger_units)
                total_points = sum(u.profile.points_cost or 0.0 for u in non_passenger_units)
                units_cap = _math.floor(0.5 * total_units)   # 10e rule: floor
                points_cap = 0.5 * total_points              # 10e rule: 50%

                # Candidates = units flagged for reserve that are NOT transport
                # passengers (leave passengers coupled to their transport).
                reservable = [
                    u for u in army.units
                    if id(u) in direct_reserves_ids and u.embarked_in is None
                ]
                # Sort: lowest OC first (best alpha-strikers go to reserves first),
                # then by name for deterministic tiebreak.
                reservable_sorted = sorted(
                    reservable,
                    key=lambda u: (u.profile.oc or 0, u.profile.name),
                )
                # Greedily fill R while BOTH caps hold.
                promoted: set = set()   # ids of units moved OFF reserve → on board
                reserve_count = 0
                reserve_points = 0.0
                for u in reservable_sorted:
                    unit_pts = u.profile.points_cost or 0.0
                    if (reserve_count + 1 <= units_cap
                            and reserve_points + unit_pts <= points_cap):
                        reserve_count += 1
                        reserve_points += unit_pts
                    else:
                        # Adding this unit would breach a cap — promote to on-board.
                        promoted.add(id(u))
                direct_reserves_ids -= promoted
                # When a transport is promoted to on-board, its embarked passengers
                # must follow — remove their ids from direct_reserves_ids too so
                # the passenger co-routing below doesn't route them back to reserves.
                for u in army.units:
                    if u.embarked_in is not None and id(u.embarked_in) in promoted:
                        direct_reserves_ids.discard(id(u))

            standard, reserves = [], []
            for u in army.units:
                going_to_reserves = (
                    id(u) in direct_reserves_ids
                    or (
                        u.embarked_in is not None
                        and id(u.embarked_in) in direct_reserves_ids
                    )
                )
                if going_to_reserves:
                    reserves.append(u)
                else:
                    standard.append(u)
            army.units[:] = standard
            self._reserves[army.name] = reserves

        # Split each on-board roster into infiltrators (deploy forward) and
        # the rest (deploy on the standard line). Embarked passengers stay
        # off the line — their position is pinned to their transport, and
        # the activation loop skips them via the `embarked_in` gate.
        a_on_board = [u for u in self.a.units if u.embarked_in is None]
        b_on_board = [u for u in self.b.units if u.embarked_in is None]
        a_infil = [u for u in a_on_board if u.profile.infiltrator]
        a_std = [u for u in a_on_board if not u.profile.infiltrator]
        b_infil = [u for u in b_on_board if u.profile.infiltrator]
        b_std = [u for u in b_on_board if not u.profile.infiltrator]

        # INTELLIGENT-DEPLOYMENT (env-gated SWEG_DEPLOY) — role-split screening.
        # Default OFF: the standard line is a single even row at the army's
        # deployment-zone midline (`a_y` / `b_y`), byte-identical to the legacy
        # behaviour. When SWEG_DEPLOY=1, each army's standard on-board units are
        # split by GENERIC unit character (see `_split_screen_back`) into a
        # forward SCREEN group (expendable, high-model-count chaff and forward
        # melee) and a rear HIGH-VALUE group (gunlines, durable bricks,
        # characters). The screen deploys toward the inner (mid-board) edge of
        # the deployment zone so it controls the mid-board and pushes enemy deep
        # strike / charge arrivals back; the high-value group deploys at the rear
        # near the army's own board edge, protected behind the screen. Both rows
        # stay wholly inside the army's own deployment zone. This is an AI
        # tactical heuristic (faithful competitive deployment), NOT a 10e game
        # rule — cited as `simulator.intelligent_deployment`.
        # Fidelity-revisit sweep #6 (wave 210): now DEFAULT-ON — competent players
        # deploy this way; it improved the metric (5.44→5.23 N=80) by lifting the
        # under-pole gunlines (Astra Militarum / Adeptus Mechanicus deploy their durable
        # shooters safely behind screens). `SWEG_DEPLOY=0` reverts to the legacy
        # massed-block deployment.
        if __import__("os").environ.get("SWEG_DEPLOY", "1") != "0":
            dz = self.map.deployment_width
            # REFINEMENT (wave 103): the high-value / gunline group sits at the
            # deployment-zone MIDLINE (`a_y`/`b_y` — its legacy single-line
            # position, with a clear firing lane), NOT buried at the board edge.
            # The crude wave-102 version put it at the board edge, which cost the
            # gunline under-shooters their early sightlines and regressed Astra
            # Militarum / Adeptus Mechanicus. Only the SCREEN is pushed forward to
            # the zone's inner edge (toward mid-board) to body-block / deny the
            # Knight; the gunline stays exactly where the legacy deploy put it.
            a_back_y = a_y
            a_screen_y = max(a_y, dz - 3.0)
            b_back_y = b_y
            b_screen_y = min(b_y, self.map.height - dz + 3.0)

            a_screen, a_back = self._split_screen_back(a_std)
            b_screen, b_back = self._split_screen_back(b_std)
            self._deploy_line(a_back, a_back_y)
            self._deploy_line(a_screen, a_screen_y)
            self._deploy_line(b_back, b_back_y)
            self._deploy_line(b_screen, b_screen_y)
        else:
            self._deploy_line(a_std, a_y)
            self._deploy_line(b_std, b_y)

        # Infiltrators sit roughly halfway between their own deployment line
        # and the centreline — forward of own zone, ~12-18" from the enemy
        # zone on a 60" board. Heuristic, since we don't have exact enemy
        # model positions to check ">9" from any enemy" precisely.
        centre_y = self.map.height / 2.0
        a_forward_y = (a_y + centre_y) / 2.0
        b_forward_y = (b_y + centre_y) / 2.0
        self._deploy_line(a_infil, a_forward_y)
        for u in a_infil:
            self._emit(UnitInfiltrated(unit_uid=u.uid, position=u.position))
        self._deploy_line(b_infil, b_forward_y)
        for u in b_infil:
            self._emit(UnitInfiltrated(unit_uid=u.uid, position=u.position))

        # Synchronise embarked passenger positions to their (now deployed)
        # transport's position. The pre-embark pass set passenger.position
        # to the transport's pre-deploy position; after _deploy_line moves
        # the transport, passengers need to follow so any future spatial
        # query (line of sight, distance gates) reads the correct location.
        for army in (self.a, self.b):
            for u in army.units:
                if u.embarked_in is not None:
                    u.position = u.embarked_in.position

    def _split_screen_back(self, units):
        """Split standard on-board `units` into (screen, back) groups by role.

        INTELLIGENT-DEPLOYMENT screen heuristic (env-gated `SWEG_DEPLOY`). The
        split is by GENERIC unit character only — never by faction — so it is
        even-handed and would be correct even if it moved the calibration metric
        the wrong way. Reuses `code.roles.classify` and the cached expected
        damage-per-activation helpers rather than hand-rolling a taxonomy.

        A squad is a set of Unit objects sharing a `squad_id` (lone models have
        `squad_id < 0` and are their own squad). For each squad we read three
        generic signals from the shared profile + the live squad size:

          * per-model points cost (`profile.points_cost`),
          * model count (squad members on the board), and
          * role (`classify`) and total expected damage output.

        FRONT (screen) — expendable, board-controlling units that real players
        push forward to screen the mid-board, deny the 9" deep-strike bubble by
        occupying space, and body-block charges to the rear:
          * cheap high-model-count chaff (low points-per-model AND several
            models AND not the army's single top damage dealer), or
          * forward melee (a melee-leaning low-value squad that wants to be up
            the board).
        Everything else — gunlines (SHOOTY), durable bricks (HEAVY), characters
        (SUPPORT / lone CHARACTER), and the army's top damage dealer — stays in
        the BACK (rear) group, protected behind the screen. If no squad reads as
        a screen, the whole army deploys in the back group (fine — no screen
        available, e.g. a pure gunline or an all-elite list).

        Returns `(screen_units, back_units)` as two flat lists of Unit objects
        (squad membership is preserved within each list; `_deploy_line` then
        re-clusters per squad).
        """
        from collections import OrderedDict
        from .roles import classify, expected_ranged_dpa, expected_melee_dpa

        if not units:
            return [], []

        # Group passed units into squads, preserving first-seen order. Lone /
        # unassigned models (squad_id < 0) each form their own single-member
        # squad so they are classified individually.
        squads = OrderedDict()
        for u in units:
            sid = getattr(u, "squad_id", -1)
            key = sid if sid is not None and sid >= 0 else ("lone", id(u))
            squads.setdefault(key, []).append(u)

        # Identify the army's single top damage-dealing squad — it always stays
        # in the back regardless of how cheap its individual models are, because
        # a player never screens with their primary threat. Total output is the
        # per-model expected damage-per-activation times the live model count.
        def _squad_output(members) -> float:
            p = members[0].profile
            per_model = expected_ranged_dpa(p) + expected_melee_dpa(p)
            return per_model * len(members)

        top_key = max(squads.keys(), key=lambda k: _squad_output(squads[k]))

        # Even-handed, generic thresholds. A "cheap body" is a model that costs
        # little and comes in numbers; a screen squad is several such bodies.
        CHEAP_POINTS_PER_MODEL = 20.0   # roughly Guardsman..Ork-Boy band
        MIN_SCREEN_MODELS = 5           # a screen needs bodies to control space
        FORWARD_MELEE_POINTS = 18.0     # cheap melee leans forward
        MIN_FORWARD_MELEE_MODELS = 3

        screen, back = [], []
        for key, members in squads.items():
            p = members[0].profile
            n = len(members)
            ppm = p.points_cost
            role = classify(p)

            is_top_dealer = (key == top_key)
            cheap_chaff = (
                ppm <= CHEAP_POINTS_PER_MODEL
                and n >= MIN_SCREEN_MODELS
                and not is_top_dealer
            )
            forward_melee = (
                role in ("MELEE", "HORDE")
                and ppm <= FORWARD_MELEE_POINTS
                and n >= MIN_FORWARD_MELEE_MODELS
                and not is_top_dealer
            )
            if cheap_chaff or forward_melee:
                screen.extend(members)
            else:
                back.extend(members)

        return screen, back

    def _deploy_line(self, units, y: float) -> None:
        """Deploy `units` along the line at height `y`, clustering each squad.

        Unit Coherency (10e core rules, cited as `simulator.unit_coherency`):
        a unit's models must be set up within 2" horizontally of at least one
        other model in their unit. We model one Unit-object per physical model,
        so a codex squad is the set of Units sharing a `squad_id`. The even
        board-width spacing therefore allocates one slot PER SQUAD (not per
        model); each squad's models are then placed in a tight cluster
        (~1.25" apart) around that squad's anchor x. Lone units (squad_id < 0)
        are one slot each. Without this, a 10-model squad spread ~44" across
        the board and violated coherency from turn zero.
        """
        if not units:
            return
        # Group the passed units by squad_id, preserving first-seen order.
        # Lone / unassigned models (squad_id < 0) each form their own group so
        # they never merge with another squad.
        from collections import OrderedDict
        groups = OrderedDict()
        for u in units:
            sid = getattr(u, "squad_id", -1)
            key = sid if sid is not None and sid >= 0 else ("lone", id(u))
            groups.setdefault(key, []).append(u)

        usable = self.map.width - 4.0   # leave 2" margin each side
        slot_spacing = usable / (len(groups) + 1)
        cluster_step = 1.25  # inches between adjacent models in a squad (< 2")

        for slot_idx, members in enumerate(groups.values()):
            anchor_x = 2.0 + slot_spacing * (slot_idx + 1)
            n = len(members)
            # Centre the cluster on the anchor so the squad straddles its slot.
            start_x = anchor_x - cluster_step * (n - 1) / 2.0
            for j, u in enumerate(members):
                x = start_x + cluster_step * j
                # Clamp inside the 2" board margins so a large squad near the
                # edge does not spill off-table.
                x = min(max(x, 2.0), self.map.width - 2.0)
                u.position = (x, y)

    # ------------------------------------------------------------------
    # Phase I — Scout phase + Deep Strike arrivals
    # ------------------------------------------------------------------

    def _run_scout_phase(self) -> None:
        """Pre-Round 1 Normal Move for every unit with Scouts x"". The unit
        makes a Normal move up to `scout_distance` inches; the DESTINATION is
        an AI tactical choice. Units that scouted are flagged in
        `_fresh_arrivals` so they skip the Round 1 movement sub-phase — they
        already moved.

        Destination policy:
          * default (legacy): move toward the NEAREST ENEMY. Simple, but for
            fragile gunline-scouts (Astra Militarum / Adeptus Mechanicus /
            Adepta Sororitas) this shoves them into turn-1 threat range and
            off their own objectives — anti-competitive.
          * SWEG_SCOUT_AI=1: classify the scout by ROLE and pick the
            destination that real competitive play would (v2 — the v1
            "send every scout to an objective" was flat-to-worse because it
            pulled aggressive melee scouts off their pressure and stranded
            long-range gunline scouts on open markers):
              (a) MELEE-oriented (primary profile is melee, per
                  `_is_melee_class`) -> pressure FORWARD toward the nearest
                  enemy (a War Dog / Serberys / assault scout wants to close).
              (b) LONG-range shooty (range >= 24") -> HOLD: a long gun already
                  threatens the midboard from its own zone; advancing it onto
                  an open marker only exposes it.
              (c) SHORT-range / fragile shooty -> move toward the nearest
                  FORWARD-BUT-SAFE contestable objective (board control), never
                  ending in a strictly worse position; if none exists, HOLD.
            The Scouts move itself is the real 10e rule (cited
            `simulator.scout`); choosing the destination by role is the AI
            decision, analogous to `simulator.intelligent_deployment`.
            Gated/default-OFF so the OFF path is byte-identical to the legacy
            behaviour.
        """
        scout_ai = __import__("os").environ.get("SWEG_SCOUT_AI", "0") == "1"
        center_y = self.map.height / 2.0
        # Inches a scout may end PAST the midline: enough to contest a No
        # Man's Land marker sitting on the centreline, not to charge deep into
        # the enemy half.
        safe_margin = 3.0
        # A gun reaching this far already threatens the midboard from its own
        # deployment zone, so a long-range shooty scout holds rather than
        # advancing onto an exposed marker.
        long_range_inches = 24.0
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            for u in army.alive_units:
                dist = u.profile.scout_distance
                if dist <= 0:
                    continue
                if not opponent.alive_units:
                    break
                old_pos = u.position
                if scout_ai:
                    if _is_melee_class(u.profile):
                        # (a) aggressive melee scout -> pressure forward.
                        nearest = min(
                            opponent.alive_units,
                            key=lambda e: _distance(u.position, e.position),
                        )
                        goal = nearest.position
                    elif (u.profile.range_inches or 0) >= long_range_inches:
                        # (b) long-range gunline scout -> hold its firing
                        # position (already threatens the midboard).
                        continue
                    else:
                        # (c) short-range / fragile shooty -> grab a
                        # forward-but-safe objective for board control.
                        goal = self._scout_destination(u, center_y, safe_margin)
                        if goal is None:
                            continue
                else:
                    nearest = min(
                        opponent.alive_units,
                        key=lambda e: _distance(u.position, e.position),
                    )
                    goal = nearest.position
                # Under the AI policy, the "never worse position" guard applies
                # only to the objective-seeking case (c); melee pressure (a)
                # deliberately advances toward the enemy like the legacy move.
                guarded = scout_ai and not _is_melee_class(u.profile)
                new_pos = _move_toward(old_pos, goal, float(dist), self.map,
                                       **self._collision_kwargs(u))
                # Never end in a strictly worse position than the start: under
                # the objective-seeking case only commit a move that gets the
                # unit closer to its chosen objective (a blocked/aborted move
                # leaves it put). Legacy and melee-pressure moves advance
                # toward the enemy and are committed whenever they change.
                if new_pos != old_pos and (
                    not guarded
                    or _distance(new_pos, goal) < _distance(old_pos, goal)
                ):
                    u.position = new_pos
                    self._fresh_arrivals.add(u.uid)
                    self._emit(UnitScouted(
                        unit_uid=u.uid, from_pos=old_pos, to_pos=new_pos,
                    ))

    def _scout_destination(self, u, center_y: float, safe_margin: float):
        """AI scout-move destination: the nearest contestable objective that
        is FORWARD of the unit (toward midboard) but NOT deep in enemy
        territory (no further than `safe_margin` past the midline). Returns an
        (x, y) goal, or None if no forward-but-safe objective exists.

        `forward` is derived from the unit's own position relative to the
        board centre (robust to which side each army deploys on): a scout in
        its own deployment zone advances toward the centreline, never past it
        by more than `safe_margin`. Markers behind the unit (its own home
        objectives) and markers beyond the safe band (the enemy's home
        objectives) are excluded.
        """
        uy = u.position[1]
        forward_sign = 1.0 if uy < center_y else -1.0
        cands = []
        for obj in self.map.objectives:
            oy = obj.y
            if forward_sign > 0:
                ahead = oy >= uy - 1e-6
                safe = oy <= center_y + safe_margin
            else:
                ahead = oy <= uy + 1e-6
                safe = oy >= center_y - safe_margin
            if ahead and safe:
                cands.append((obj.x, obj.y))
        if not cands:
            return None
        return min(cands, key=lambda g: _distance(u.position, g))

    def _arrive_from_reserves(self, round_num: int) -> None:
        """Bring reserves onto the board.

        Deep Strike (#153 overhaul — coordinated alpha-strike AI):
        from Round 2 onwards, the strategy layer (`decide_deepstrike_drops`)
        decides whether to drop NOW or hold. If the drop fires, all selected
        units arrive the same round (mass drop), clustered near a shared
        anchor — high-threat enemy for T2-T3, contested objective for T4+.
        Round 3 forces all remaining DS units down (alpha-strike window);
        Round 4+ never leaves reserves on the table (tempo cost).

        Cult Ambush (Genestealer Cults army rule, 10e): a unit flagged
        `cult_ambush_pending` arrives at the top of Round 1, deterministically
        (the whole GSC army can redeploy at the start of the first battle round).
        The ambush flag is cleared on landing so any subsequent revival /
        re-entry doesn't re-trigger the path. Cited as `simulator.cult_ambush`.

        Each arriving unit is placed > 9" from every alive enemy. The picker
        scores candidates by proximity to high-threat enemies and to
        contested objectives (T4+ weights objectives more). Mass-drop units
        share a landing anchor so they end up within ~12" of each other.
        """
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            waiting = self._reserves.get(army.name, [])
            if not waiting:
                continue

            # Cult Ambush units always arrive on R1; they bypass the DS gate.
            ambush_now = [u for u in waiting if getattr(u, "cult_ambush_pending", False)]
            ds_waiting = [u for u in waiting if not getattr(u, "cult_ambush_pending", False)]

            # Strategy layer decides which DS units (non-ambush) land this round.
            ds_dropping = decide_deepstrike_drops(
                round_num, ds_waiting, opponent, army, self.map,
            )
            ds_dropping_ids = {id(u) for u in ds_dropping}

            arriving = ambush_now + ds_dropping
            if not arriving:
                # No drops this round — keep everyone in reserves.
                continue

            # Pick a shared anchor for the mass drop so multiple units cluster.
            # Cult Ambush units are placed independently (no anchor) — the
            # whole GSC army is dropping, individual scoring stays cleanest.
            anchor = None
            if len(ds_dropping) >= 2:
                anchor = pick_mass_arrival_anchor(
                    round_num, ds_dropping, opponent, army, self.map,
                )

            still_waiting = []
            anchor_placed: list = []   # track placed positions for clustering
            arrived_transport_ids: set = set()  # for passenger co-arrival
            for u in waiting:
                # RESERVES-EMBARK-COUPLING (wave 46): embarked passengers
                # ride in with their transport — skip them here, the
                # transport's arrival branch below places them.
                if u.embarked_in is not None:
                    continue
                is_ambush = getattr(u, "cult_ambush_pending", False)
                if not is_ambush and id(u) not in ds_dropping_ids:
                    # Strategy held this unit back this round.
                    still_waiting.append(u)
                    continue
                # Mass-drop: cluster around anchor for non-ambush DS units.
                use_anchor = anchor if (not is_ambush and anchor is not None) else None
                pos = self._pick_arrival_point(
                    opponent,
                    arriving_unit=u,
                    round_num=round_num,
                    anchor=use_anchor,
                    placed_positions=anchor_placed if use_anchor else None,
                )
                if pos is None:
                    # No valid arrival spot — defer to next round (rare;
                    # only happens on saturated maps).
                    still_waiting.append(u)
                    continue
                u.position = pos
                u.cult_ambush_pending = False
                army._add_live_unit(u)
                self._fresh_arrivals.add(u.uid)
                self._emit(UnitDeepStrike(unit_uid=u.uid, position=pos))
                # Fire Overwatch (10e core stratagem, env-gated SWEG_OVERWATCH).
                # The unit `u` has just been SET UP from reserves / deep strike;
                # the OPPONENT army (the non-arriving side in this loop) may
                # overwatch it now while it is exposed in the open near the enemy
                # line. No-op when the gate is unset. Cited as
                # `simulator.fire_overwatch`.
                self._fire_overwatch(opponent, u)
                if use_anchor is not None:
                    anchor_placed.append(pos)
                arrived_transport_ids.add(id(u))
                # RESERVES-EMBARK-COUPLING: when a transport arrives, place
                # its embarked passengers at the transport's landing point.
                # Passengers remain embarked (the disembark happens later in
                # the owning Movement phase via _maybe_disembark_before_move);
                # this just brings them on-board so spatial queries and the
                # eventual disembark have a real position to work from.
                for passenger in list(getattr(u, "passengers", [])):
                    passenger.position = pos
                    army._add_live_unit(passenger)
                    self._fresh_arrivals.add(passenger.uid)
            # Passengers whose transport stayed in reserves stay in reserves
            # too (they got skipped in the loop above via the `embarked_in`
            # continue). Re-collect them now.
            for u in waiting:
                if u.embarked_in is not None and id(u.embarked_in) not in arrived_transport_ids:
                    still_waiting.append(u)
            self._reserves[army.name] = still_waiting

    def _pick_arrival_point(
        self,
        opponent: Army,
        arriving_unit: Optional[Unit] = None,
        round_num: int = 0,
        anchor: Optional[Tuple[float, float]] = None,
        placed_positions: Optional[list] = None,
    ) -> Optional[Tuple[float, float]]:
        """Pick a tactically-useful Deep Strike landing point.

        Generates a dense grid of legal candidates (>9" from every enemy,
        not in impassable terrain) and scores each by:

          * Proximity to high-threat enemies (SHOOTY/HEAVY weighted up).
            For a melee-capable arriving unit, "closer-to-a-threat" wins —
            we want to land into charge range of a sniper or Knight.
          * Proximity to uncontested / contested objectives. T4+ weights
            this hard — late-game DS exists to grab end-game VP.
          * Proximity to `anchor` (mass-drop clustering). When 2+ units
            drop the same round they share an anchor; later arrivals also
            get a bonus for being near already-placed siblings.

        Falls back to the legacy centre-then-corners pick if no candidates
        are valid (e.g. a tiny board mid-late game).

        Implementation note: scoring is vectorised with numpy. All ~280
        candidate positions on the 3" grid are evaluated in a single batch
        of array operations rather than per-candidate Python loops, which
        eliminated ~1M Python calls per deepstrike-heavy matchup.
        """
        import numpy as np
        from .roles import classify  # local import to avoid circular at module load

        enemies = opponent.alive_units
        min_gap = 9.0

        # Arriving unit preference: melee chases enemies, shooty claims objs.
        if arriving_unit is not None:
            ap = arriving_unit.profile
            melee_dpa = ap.melee_attacks * ap.melee_hit_probability * (ap.melee_damage_per_shot or 1.0)
            ranged_dpa = ap.attacks * ap.hit_probability * (ap.weapon_damage_per_shot or 1.0)
            is_melee_leaning = melee_dpa >= ranged_dpa * 0.7
        else:
            is_melee_leaning = False

        threat_w = 2.0 if is_melee_leaning else 1.0
        objective_w = 0.7 if is_melee_leaning else 1.6

        # T4+ override: late-game DS prioritises objective steals over kills.
        if round_num >= 4:
            objective_w *= 3.0
            threat_w *= 0.5

        # Identify uncontested objectives (no friendly within control radius).
        friendly = self.a if opponent is self.b else self.b

        # Warp Rifts (Chaos Daemons Daemonic Incursion detachment rule, 10e).
        # Wahapedia: "Each time a LEGIONES DAEMONICA unit from your army is set
        # up on the battlefield using the Deep Strike ability, if it is set up
        # wholly within your army's Shadow of Chaos … it can be set up anywhere
        # that is more than 6\" horizontally away from all enemy models, instead
        # of more than 9\"."
        # SwegHammer simplification: applied uniformly to all Chaos Daemons
        # deep-strikers under Daemonic Incursion. Gated SWEG_WARP_RIFTS.
        # Cited as `simulator.warp_rifts`.
        if (
            os.environ.get("SWEG_WARP_RIFTS", "0") != "0"
            and arriving_unit is not None
            and (arriving_unit.profile.faction or "") == "Chaos Daemons"
            and getattr(getattr(friendly, "detachment", None), "warp_rifts", False)
        ):
            min_gap = 6.0

        targetable_objs = []
        for obj in self.map.objectives:
            controlled_by_us = any(
                _distance((obj.x, obj.y), f.position) <= obj.control_radius
                for f in friendly.alive_units
            )
            if not controlled_by_us:
                targetable_objs.append(obj)

        # --- Vectorised candidate generation and scoring -------------------

        # Build candidate grid. Boundary constraints (>=2, <=width-2) are
        # baked into the arange so no per-point boundary check is needed.
        step = 3.0
        xs = np.arange(2.0, self.map.width - 1.0, step)
        ys = np.arange(2.0, self.map.height - 1.0, step)
        xx, yy = np.meshgrid(xs, ys)
        cands = np.column_stack([xx.ravel(), yy.ravel()])  # (C, 2)

        # Validity filter 1: impassable terrain (vectorised rectangle test).
        imp_rects = [
            (t.x, t.y, t.x + t.width, t.y + t.height)
            for t in self.map.terrain
            if t.type is TerrainType.IMPASSABLE
        ]
        if imp_rects:
            imp = np.array(imp_rects, dtype=float)  # (I, 4): x1 y1 x2 y2
            # Candidate (cx, cy) is inside rectangle i iff
            # x1[i] <= cx <= x2[i] and y1[i] <= cy <= y2[i].
            inside = (
                (cands[:, 0:1] >= imp[:, 0])
                & (cands[:, 0:1] <= imp[:, 2])
                & (cands[:, 1:2] >= imp[:, 1])
                & (cands[:, 1:2] <= imp[:, 3])
            ).any(axis=1)  # (C,)
            valid_mask = ~inside
        else:
            valid_mask = np.ones(len(cands), dtype=bool)

        # Validity filter 2: minimum 9" gap from every enemy.
        if enemies:
            enemy_pos = np.array([e.position for e in enemies], dtype=float)  # (E, 2)
            diff = cands[:, None, :] - enemy_pos[None, :, :]               # (C, E, 2)
            dists_to_enemy = np.hypot(diff[:, :, 0], diff[:, :, 1])        # (C, E)
            valid_mask &= dists_to_enemy.min(axis=1) > min_gap
        else:
            enemy_pos = np.empty((0, 2), dtype=float)
            dists_to_enemy = np.empty((len(cands), 0), dtype=float)

        if not valid_mask.any():
            # Fall back to the legacy centre-then-corners pick.
            cx, cy = self.map.width / 2.0, self.map.height / 2.0
            for cand in (
                (cx, cy),
                (3.0, 3.0),
                (self.map.width - 3.0, 3.0),
                (3.0, self.map.height - 3.0),
                (self.map.width - 3.0, self.map.height - 3.0),
            ):
                if self.map.is_blocked(cand):
                    continue
                if not enemies or min(_distance(cand, e.position) for e in enemies) > min_gap:
                    return cand
            return None

        valid_cands = cands[valid_mask]                     # (V, 2)
        scores = np.zeros(len(valid_cands), dtype=float)

        # Enemy score: sum_e [ threat_weight(e) * threat_w / (d_ce - 4) ]
        # All valid candidates are >9" from every enemy so (d - 4) >= 5: safe.
        if enemies:
            _role_base = {"HEAVY": 3.0, "SHOOTY": 2.5, "DUAL": 1.5,
                          "MELEE": 1.0, "SUPPORT": 1.2, "HORDE": 0.8}
            tw_vals = np.array([
                _role_base.get(classify(e.profile), 1.0)
                * (1.5 - 0.5 * max(0.1, e.current_health / max(1.0, e.profile.health)))
                * threat_w
                for e in enemies
            ], dtype=float)                                 # (E,)
            vd = dists_to_enemy[valid_mask]                 # (V, E)
            scores += (tw_vals / (vd - 4.0)).sum(axis=1)

        # Objective score: sum_o [ objective_w / (d_co + 4) ]
        # T4+ bonus: +12 for each candidate within any objective's control radius.
        if targetable_objs:
            obj_pos = np.array([(o.x, o.y) for o in targetable_objs], dtype=float)  # (O, 2)
            od = np.hypot(
                valid_cands[:, 0:1] - obj_pos[:, 0],
                valid_cands[:, 1:2] - obj_pos[:, 1],
            )                                               # (V, O)
            scores += (objective_w / (od + 4.0)).sum(axis=1)
            if round_num >= 4:
                for j, obj in enumerate(targetable_objs):
                    scores += 12.0 * (od[:, j] <= obj.control_radius)

        # Anchor score: 4 / (d_anchor + 4); -5 penalty if >12" away.
        if anchor is not None:
            anchor_arr = np.array(anchor, dtype=float)
            d_anchor = np.hypot(
                valid_cands[:, 0] - anchor_arr[0],
                valid_cands[:, 1] - anchor_arr[1],
            )
            scores += 4.0 / (d_anchor + 4.0)
            scores -= 5.0 * (d_anchor > 12.0)

        # Sibling-clustering score: sum_s [ 2 / (d_sib + 4) ]
        if placed_positions:
            sib_arr = np.array(placed_positions, dtype=float)  # (S, 2)
            sd = np.hypot(
                valid_cands[:, 0:1] - sib_arr[:, 0],
                valid_cands[:, 1:2] - sib_arr[:, 1],
            )                                               # (V, S)
            scores += (2.0 / (sd + 4.0)).sum(axis=1)

        best_idx = int(np.argmax(scores))
        bx, by = valid_cands[best_idx]
        return (float(bx), float(by))

    # ------------------------------------------------------------------
    # Round logic
    # ------------------------------------------------------------------

    def _squad_on_objective(self, members) -> bool:
        """True if any member of the squad is within the control radius of any
        objective marker — the squad is holding / contesting an objective. Used
        as the Insane Bravery spend heuristic: a real player burns the
        once-per-battle auto-pass to keep an objective-contesting unit's
        Objective Control (Battle-shock would drop it to 0)."""
        for obj in self.map.objectives:
            r2 = obj.control_radius * obj.control_radius
            for u in members:
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                if dx * dx + dy * dy <= r2:
                    return True
        return False

    def _run_battleshock_phase(self, round_num: int) -> None:
        """10e Battle-shock step (every Command phase, from Round 1
        onward — Wahapedia /the-rules/core-rules/#Command-Phase). For
        each unit Below Half-Strength, roll 2D6 vs Ld; fail (< Ld) sets
        the unit as
        Battle-shocked for the round — OC drops to 0 AND it cannot be the
        subject of Stratagems. We populate `_battleshocked_this_round`
        BEFORE the stratagem dispatcher runs so target-pickers
        (`_most_vulnerable_unit`, `_highest_dpa_unit`) can filter the set
        out. Cited as `simulator.battleshock`.

        Detachment modifiers compose: own ld_bonus LOWERS our test target
        (easier pass); opponent's enemy_ld_penalty RAISES it (harder pass).

        Faction-rule short-circuits:
          - Mob Rule (Orks, 10e): if the testing squad has 10+ alive models
            in it, the test is automatically passed. Re-keyed on squad_id
            (task #27): two separate 5-model Boyz squads do NOT pool.
            Cited as `simulator.mob_rule`.
          - Synapse Imperative (Tyranids, 10e): a Tyranid unit within 6"
            of any friendly SYNAPSE model auto-passes. Cited as
            `simulator.synapse_imperative`. Note (BS-1): a Tyranid unit
            that auto-passes via Synapse never has its
            `battleshocked_until_round` advanced, so
            `is_currently_battle_shocked(round_num)` correctly returns
            False for them — this matters once future Synapse-keyed
            consumers (e.g. enemy Harbingers of Dread auras) start reading
            the persistent flag.
          - Shadow in the Warp (Tyranids, 10e Codex): the Tyranid player
            unleashes Shadow once per battle, in either player's Command
            phase. On the round it is unleashed, each enemy unit within 6"
            of any friendly Tyranid SYNAPSE model takes its Battle-shock
            test at -1. TYRANIDS-DIAG-5: was previously modelled as an
            always-on 12" aura — over-applied the debuff every round at a
            wider radius, contributing to Tyranids sim over-perf. Now gated
            on `army.shadow_in_the_warp_used_round == round_num`, declared
            from the Command-phase loop with the AI heuristic firing at
            Round 2. The "forces a Battle-shock test on every enemy unit on
            the battlefield on the unleashing round" half of the codex rule
            is NOT modelled here — most at-strength enemy units (Ld 7-9)
            pass 2D6-1 reliably, so the dominant impact comes from -1
            applied to the existing below-half tests within 6". Cited as
            `simulator.shadow_in_the_warp`.
          - Contagions of Nurgle Round 2 Maladictive Pall (Death Guard, 10e):
            enemy units within 3" of any DG model take -1 Ld. Cited as
            `simulator.contagions_of_nurgle`. (Radius gated to 3" per the
            modern Nurgle's Gift / Afflicted rule; older index rule was 6".)
          - Shadow of Chaos (Chaos Daemons, 10e): enemy units within the
            Shadow of Chaos take Battle-shock at -1 AND, if failed,
            suffer D3 mortal wounds. APPROXIMATION: SwegHammer does not
            track deployment-zone ownership; the rule's "your deployment
            zone + objectives-held No Man's Land" trigger is proxied as
            "enemy unit is within 18" of board centre while a Chaos
            Daemons army is the opponent". Cited as
            `simulator.shadow_of_chaos`.

        iter-13 fix: previously gated on `round_num <= 1` (skipped R1
        entirely). 10e core fires the test at the start of every Command
        phase, R1 included. The R1 path is now live; the
        contagion-source escalation gate below remains R2-only because
        Maladictive Pall itself is R2 in the contagion schedule.
        """
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            opponent_det = opponent.resolve_detachment()
            own_det = army.resolve_detachment()
            ld_penalty = opponent_det.enemy_ld_penalty if opponent_det else 0
            ld_bonus = own_det.ld_bonus if own_det else 0
            own_synapse = [
                s for s in army.alive_units
                if "SYNAPSE" in (s.profile.unit_keywords or ())
            ]
            # Shadow in the Warp — once-per-battle (TYRANIDS-DIAG-5).
            # The opponent's Tyranid army may have unleashed Shadow this
            # round; the test-side debuff applies only on that round.
            # `opponent.shadow_in_the_warp_used_round == round_num` gates
            # the source list to empty when Shadow is dormant, so the
            # downstream `shadow_penalty` block becomes a no-op.
            if (
                opponent.shadow_in_the_warp_used_round is not None
                and opponent.shadow_in_the_warp_used_round == round_num
            ):
                shadow_sources = [
                    s for s in opponent.alive_units
                    if "SYNAPSE" in (s.profile.unit_keywords or ())
                    and s.profile.faction == "Tyranids"
                ]
            else:
                shadow_sources = []
            contagion_sources = (
                [
                    s for s in opponent.alive_units
                    if s.profile.faction == "Death Guard"
                ]
                if round_num == 2 else []
            )
            # Shadow of Chaos (Chaos Daemons army rule, 10e). APPROXIMATION:
            # the real Shadow of Chaos covers the Daemons player's deployment
            # zone always plus contested portions of No Man's Land /
            # opponent's deployment zone if Daemons control half-or-more
            # objectives there. SwegHammer does not track per-zone objective
            # ownership; we proxy "inside the Shadow" as "within 18" of board
            # centre while ANY Chaos Daemons unit is alive in the opposing
            # army". This covers the common case (Daemons pushing centre) at
            # the cost of missing the deployment-zone passive coverage; the
            # 18" radius is chosen as a half-board approximation of the
            # canonical zone-based shape.
            shadow_of_chaos_active = any(
                s.profile.faction == "Chaos Daemons"
                for s in opponent.alive_units
            )
            if shadow_of_chaos_active:
                cx = self.map.width / 2.0
                cy = self.map.height / 2.0
            # Harbingers of Dread (Chaos Knights army rule, 10e). Wahapedia
            # verbatim Deathly Terror (always-on Dread, active from R1):
            # "While an enemy unit is within 9\" of this model, worsen the
            # Leadership characteristic of models in that unit by 1." Every
            # Chaos Knights datasheet has the Harbingers of Dread rule
            # (BSData v10.6.0 confirms the infoLink is present on every CK
            # selectionEntry), so the aura source is "any alive Chaos
            # Knights unit in the opposing army" rather than just CHARACTERs
            # — Chaos Knights have very few CHARACTERs and the aura is
            # datasheet-wide. The 9" radius is the Wahapedia-verbatim range.
            # Same convention as Shadow in the Warp (a +1 to the test
            # target equals a -1 to Ld). Cited as
            # `simulator.harbingers_of_dread`.
            harbinger_sources = [
                s for s in opponent.alive_units
                if (s.profile.faction or "") == "Chaos Knights"
            ]

            # --- PER-SQUAD battleshock loop (task #27) ---
            # 10e core: "a unit is Below Half-strength if the number of
            # models in it is below half its Starting Strength."  We run
            # ONE test per codex-unit (squad_id group) and mark ALL models
            # in the squad on a failure.  Lone single-model squads
            # (start_count == 1) keep the wound-based below-half test for
            # fidelity with how 10e treats vehicle / hero wound degradation.
            squads = army.squads()  # OrderedDict[squad_key, List[Unit]]
            for squad_key, members in squads.items():
                sid = members[0].squad_id
                start_count = self._squad_start_count.get(
                    (army.name, sid), 1
                )

                # --- Below-half-strength gate ---
                if start_count > 1:
                    # Multi-model squad: gate on surviving model count.
                    alive_count = len(members)
                    if alive_count >= start_count / 2.0:
                        continue   # not below half-strength — no test
                else:
                    # Single-model unit (vehicle, character, lone model):
                    # retain the wound-based below-half test.
                    u0 = members[0]
                    if u0.current_health >= u0.profile.health / 2.0:
                        continue   # not below half-strength — no test

                # Representative model for position/faction/leadership checks.
                # Use the first alive member (squads() only contains alive units).
                rep = members[0]

                # --- Mob Rule (10e, re-keyed on squad_id) ---
                # Wahapedia: "Each time a Battle-shock test is taken for an
                # ORKS unit from your army, if that unit has 10 or more
                # models in it, that test is automatically passed."
                # Re-keyed from profile.name to squad_id (task #27): alive
                # members in THIS squad must number >= 10.  Two separate
                # 5-model Boyz squads do NOT pool.
                if (
                    rep.profile.faction == "Orks"
                    and len(members) >= 10
                ):
                    continue   # Mob Rule auto-pass

                # --- TYRANIDS-SYNAPSE-3D6 (wave-44) ---
                # Use representative model's position for the Synapse
                # radius check; a squad is either inside or outside the
                # aura as a unit.
                synapse_3d6 = (
                    rep.profile.faction == "Tyranids"
                    and own_synapse
                    and any(
                        _distance(rep.position, s.position) <= 6.0
                        for s in own_synapse
                        if s.uid != rep.uid
                    )
                )

                # --- Environmental penalties (use representative position) ---
                shadow_penalty = 0
                # TYRANIDS-DIAG-5: codex radius is 6".
                if shadow_sources and any(
                    _distance(rep.position, s.position) <= 6.0
                    for s in shadow_sources
                ):
                    shadow_penalty = 1
                contagion_penalty = 0
                if (
                    contagion_sources
                    and rep.profile.faction != "Death Guard"
                    and any(
                        _distance(rep.position, s.position) <= 3.0
                        for s in contagion_sources
                    )
                ):
                    contagion_penalty = 1
                # Shadow of Chaos: -1 to Battle-shock (modelled as +1 to
                # test target — same convention as Shadow in the Warp).
                shadow_of_chaos_penalty = 0
                shadow_of_chaos_hit = False
                if (
                    shadow_of_chaos_active
                    and rep.profile.faction != "Chaos Daemons"
                    and _distance(rep.position, (cx, cy)) <= 18.0
                ):
                    shadow_of_chaos_penalty = 1
                    shadow_of_chaos_hit = True
                # Harbingers of Dread — Deathly Terror Ld -1 aura within
                # 9" of any alive enemy Chaos Knights model.
                harbinger_penalty = 0
                if harbinger_sources and any(
                    _distance(rep.position, s.position) <= 9.0
                    for s in harbinger_sources
                ):
                    harbinger_penalty = 1

                # --- Daemonic Manifestation (Chaos Daemons, the friendly half
                # of The Shadow of Chaos — wave 88, BSData rule a312-a2f1-e1c0-30ed).
                # While a LEGIONES DAEMONICA unit is within its army's Shadow of
                # Chaos it adds 1 to its Battle-shock test AND, on a PASS, returns
                # up to D3 destroyed models (BATTLELINE) or D3 lost wounds
                # (otherwise). The Shadow is the Daemons' own deployment zone
                # (ALWAYS) plus contested No Man's Land; proxied here as own-DZ OR
                # within 18" of board centre (parity with the Daemonic Terror
                # proxy above; objective-count not tracked). The model/wound
                # return reuses the existing reanimation pulse
                # (transient_undying_legions_pulse — the same plumbing as Foetid
                # Resurgence / Mob Up; consumed end-of-round by
                # _apply_undying_legions_pulse, which heals wounds then returns
                # destroyed models). Cited `simulator.daemonic_manifestation`.
                # Env-gated SWEG_DAEMONIC (default ON; =0 re-gates for an A/B).
                daemonic_manifest = False
                if (
                    rep.profile.faction == "Chaos Daemons"
                    and __import__("os").environ.get("SWEG_DAEMONIC", "1") != "0"
                ):
                    _dz = self.map.deployment_width
                    _own_a = army is self.a
                    _in_own_dz = (
                        rep.position[1] <= _dz if _own_a
                        else rep.position[1] >= self.map.height - _dz
                    )
                    if _in_own_dz or _distance(
                        rep.position,
                        (self.map.width / 2.0, self.map.height / 2.0),
                    ) <= 18.0:
                        daemonic_manifest = True

                # --- One roll per squad ---
                if synapse_3d6:
                    # Tyranid Synapse — 3D6 sum, codex-correct.
                    roll = (random.randint(1, 6) + random.randint(1, 6)
                            + random.randint(1, 6))
                else:
                    roll = random.randint(1, 6) + random.randint(1, 6)
                target = (
                    rep.profile.leadership
                    + ld_penalty
                    - ld_bonus
                    + shadow_penalty
                    + contagion_penalty
                    + shadow_of_chaos_penalty
                    + harbinger_penalty
                    - (1 if daemonic_manifest else 0)   # Daemonic Manifestation: +1 to the test
                )
                # Insane Bravery (1 CP, universal Epic Deed — 10e core): just
                # before a FAILED Battle-shock test, the army may spend 1 CP to
                # auto-pass it, once per battle. A real player burns it to keep a
                # unit that is CONTESTING an objective (Battle-shock would zero
                # the unit's Objective Control there). Even-handed — every army
                # has it; the objective-gate makes the benefit accrue to whoever
                # is holding markers, not to any faction. Modelled by forcing the
                # roll to meet the target, so the existing fail / pass (incl. the
                # Daemonic Manifestation pass) branches below resolve it as a
                # pass. Gated SWEG_INSANE (default ON; =0 for the isolation A/B).
                # Cited `simulator.insane_bravery`.
                if (
                    roll < target
                    and __import__("os").environ.get("SWEG_INSANE", "1") != "0"
                    and id(army) not in self._insane_bravery_used
                    and army.command_points >= 1
                    and self._squad_on_objective(members)
                ):
                    army.command_points -= 1
                    self._insane_bravery_used.add(id(army))
                    roll = target   # auto-passed — resolves as a pass below
                if roll < target:
                    # Mark ALL models in the squad as Battle-shocked.
                    for u in members:
                        self._battleshocked_this_round.add(u.uid)
                        # BS-1: persistent per-unit state. Mark the unit as
                        # battle-shocked through the end of this round; the
                        # next round's Battle-shock phase will overwrite or
                        # leave the field stale (consumers read via
                        # `is_currently_battle_shocked(round_num)`, which
                        # checks exact-round equality, so stale values do
                        # not bleed forward). Downstream rules that need
                        # the persistent state (Synapse Imperative auto-pass
                        # gating, Harbingers of Dread mortal-wound aura,
                        # Repentia explosive death, DG plague-fear
                        # stratagems) consume the marker rather than the
                        # transient `_battleshocked_this_round` set.
                        u.battleshocked_until_round = round_num
                    # Emit one BattleshockFailed event keyed to the
                    # representative model (callers that display events see
                    # the squad rep rather than an avalanche of per-model
                    # events for large squads).
                    self._emit(BattleshockFailed(
                        unit_uid=rep.uid, roll=roll, target=target,
                    ))
                    # Shadow of Chaos: failed test inside the Shadow also
                    # inflicts D3 mortal wounds on ONE model in the squad
                    # (per the rule's wording "that unit suffers D3 mortal
                    # wounds", applied to the squad rep as the closest model
                    # to the Chaos centre). Cited as
                    # `simulator.shadow_of_chaos`.
                    if shadow_of_chaos_hit:
                        mw = random.randint(1, 3)
                        rep.current_health = max(0, rep.current_health - mw)
                elif daemonic_manifest:
                    # PASS inside the Shadow — Daemonic Manifestation returns up
                    # to D3 destroyed models (BATTLELINE) / D3 lost wounds via the
                    # reanimation pulse, applied end-of-round by
                    # _apply_undying_legions_pulse (heals wounds, then returns
                    # destroyed models — matching the rule's BATTLELINE-vs-other
                    # split). Set on the squad representative; the pulse consumer
                    # groups by squad_id and revives that squad's dead peers.
                    rep.transient_undying_legions_pulse = max(
                        rep.transient_undying_legions_pulse, random.randint(1, 3)
                    )

    def _run_round(self, round_num: int) -> None:
        if self.verbose:
            print(f"\n--- Round {round_num} ---")

        # Expose the live round to Unit.attack via the army back-reference
        # so faction-gated round windows (Orks WAAAGH! +1 to wound melee)
        # can be checked without threading a round parameter through every
        # call site.
        self._current_round = round_num

        # New round = no unit has Advanced yet, no battleshock yet, no charges.
        self._advanced_this_round = set()
        self._squad_charge_roll = {}   # wave 76: per-squad charge roll, fresh each round
        self._squad_advance_roll = {}  # wave 77: per-squad advance roll, fresh each round
        self._battleshocked_this_round = set()
        self._charging_this_round = set()
        # Fire Overwatch: new round, each army may use the overwatch stratagem
        # again (once per round per army). Cited as `simulator.fire_overwatch`.
        self._overwatched_this_round = set()
        # Reset movement tracking: nothing has moved yet this round.
        self._did_move_this_round = set()
        # Reset disembark tracking: nothing has disembarked yet this round.
        self._disembarked_this_round = set()

        # SOROR-DIAG-4 / SOROR-ACTS-OF-FAITH-V1 — reset each Sororitas unit's
        # per-round Acts of Faith budget. Two-level reset:
        #
        # (1) Per-instance flag `aof_used_this_round`: prevents a single Unit
        #     instance from using AoF twice in the same round. Conservative
        #     under-approximation of the codex's "one per phase" literal
        #     (collapses to one per round). Cited as `simulator.acts_of_faith`.
        #
        # (2) SOROR-ACTS-OF-FAITH-V1 squad-level budget (the "aof" effect of
        #     the generalized `_unit_budget_used`, squad rebuild Stage C):
        #     enforces the codex "each UNIT can perform one Act of Faith per
        #     phase" at the codex-unit granularity. The simulator instantiates
        #     each model in a squad as a separate Unit object (e.g. 10 Battle
        #     Sisters models = 10 Unit instances). Without this budget, each
        #     instance could independently use AoF, giving a 10-model squad up
        #     to 10 AoF spends per round where the codex allows only 1 (one per
        #     codex unit). Keying by squad_id (or profile.name fallback) so all
        #     instances of one codex unit share one budget corrects this N×
        #     over-count. Wahapedia verbatim: "each unit from your army with
        #     this ability can perform one Act of Faith per phase." Cited as
        #     `simulator.acts_of_faith`.
        for army in (self.a, self.b):
            # Squad rebuild Stage C — reset the ONE generalized per-round
            # unit-budget, clearing every once-per-codex-unit-per-round effect
            # at once. This replaces the four separate set re-creations that
            # previously cleared Acts of Faith ("aof") and the three Strands of
            # Fate gates ("fate_advance" / "fate_hit" / "fate_save") — clearing
            # the dict is identical to clearing each set. The keys are still
            # squad_id (int) when the unit has squad_id >= 0, else profile.name
            # (str) — the task #28 squad_id re-key; the mixed int/str type is
            # intentional and cannot collide. Cited as `simulator.acts_of_faith`
            # (aof) and `simulator.strands_of_fate` (the three fate_* effects).
            army._unit_budget_used = {}
            for u in army.units:
                if u.profile.faction == "Adepta Sororitas":
                    u.aof_used_this_round = False
            for u in self._reserves.get(army.name, []):
                if u.profile.faction == "Adepta Sororitas":
                    u.aof_used_this_round = False

        # SC4-A — snapshot each army's alive units at round start for the
        # 10e Pariah Nexus secondary scoring (Bring it Down + No Prisoners).
        # End-of-round (in `run`) computes the kill delta against the
        # snapshot to award per-round secondary VP. Snapshot is taken at
        # round start so kills DURING this round are credited to this
        # round's scoring (real 10e per-round caps applied in
        # `secondaries.score_round_delta`).
        from .secondaries import take_snapshot as _take_snapshot
        self._a_round_snapshot = _take_snapshot(self.a.units)
        self._b_round_snapshot = _take_snapshot(self.b.units)
        # Wave 83 Tier A: record who controls each objective at round start, so
        # Storm Hostile Objective can score taking one the opponent held.
        self._obj_controller_at_round_start = self._objective_controllers()

        # Fix F-NEC-1: snapshot per-profile alive counts AT ROUND START for
        # any army with Reanimation Protocols. End-of-round `_apply_reanimation`
        # compares this to alive-now to see if at least one model died this
        # round; if not, RP does NOT fire (Wahapedia: "has had one or more
        # destroyed bodyguard models"). Reserves (deep-strikers not yet on
        # board) are excluded — they're not eligible to die.
        for army in (self.a, self.b):
            det = army.resolve_detachment()
            if not det or det.reanimate_per_round <= 0:
                continue
            counts: Dict[str, int] = {}
            for u in army.units:
                if u.is_alive:
                    counts[u.profile.name] = counts.get(u.profile.name, 0) + 1
            self._round_start_alive_counts[army.name] = counts

        # ---- Command phase: each army gains 1 CP (capped at 6). 10e core
        # rule. Starting CP (3 = Strike Force standard) is set by
        # Army.__init__; this is the per-round drip on top. The smaller-army
        # CP bonus is a separate SwegHammer-specific catch-up mechanism
        # awarded later by _award_cp.
        award_command_phase_cp(self.a)
        award_command_phase_cp(self.b)
        # ---- Warlord-gated CP discount (Roboute Guilliman, Lord of
        # Contagion). After the per-round drip, look up the army's Warlord
        # and apply any additional per-round CP mechanic:
        #   * `cp_discount_per_round > 0`: bump command_points by that
        #     amount (capped at the universal CP_CAP=6). Guilliman's
        #     "Author of the Codex" extra +1 CP / round.
        #   * `first_stratagem_free_per_round`: re-arm the "next stratagem
        #     is free" latch for this round. Lord of Contagion's "Lord of
        #     the Death Guard" Warlord trait.
        # The Warlord scan is keyed off `_warlord_first_strat_free_enabled`
        # / `warlord_ability(army)` — armies without a CP-econ Warlord skip
        # this block entirely and the discount never fires.
        from .leaders import warlord_ability as _warlord_ability_for_round
        for army in (self.a, self.b):
            wl = _warlord_ability_for_round(army)
            if wl is None:
                continue
            if wl.cp_discount_per_round > 0:
                army.command_points = min(
                    CP_CAP,
                    army.command_points + wl.cp_discount_per_round,
                )
            if army._warlord_first_strat_free_enabled:
                army.first_stratagem_free_this_round = True
        # ---- Orks WAAAGH! once-per-battle declaration (Command phase).
        # 10e Orks army rule: declared at the start of a Command phase, once
        # per battle. While active until the end of that turn, Ork attackers
        # gain +1 to wound in melee (the simulator-side gate; +1 to charge
        # rolls and Advance-counts-as-charge are descriptive — see
        # `simulator.waaagh` citation). The AI fires per `should_declare_waaagh`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            if any(u.profile.faction == "Orks" for u in army.units):
                if should_declare_waaagh(army, round_num, opponent):
                    army.waaagh_round_unlocked = round_num
                    self._emit(WaaaghDeclared(
                        army_name=army.name, round_num=round_num,
                    ))
        # ---- Tyranids Shadow in the Warp once-per-battle declaration
        # (Command phase). 10e Codex Tyranids army rule (current Wahapedia):
        # "Once per battle, in either player's Command phase, if one or more
        # units from your army with this ability are on the battlefield, you
        # can unleash the Shadow in the Warp. When you do, each enemy unit on
        # the battlefield must take a Battle-shock test. Each time an enemy
        # unit takes such a Battle-shock test, if it is within 6\" of one or
        # more SYNAPSE units from your army, subtract 1 from that test."
        #
        # The previous SwegHammer implementation modelled SitW as an
        # always-on 12" -1 Ld aura on every Battle-shock test against any
        # below-half enemy unit — a multi-round, wider-radius over-buff vs
        # the codex once-per-battle 6" trigger. TYRANIDS-DIAG-5 (2026-05-24)
        # collapses to once-per-battle. AI heuristic: fire in Round 2 —
        # earliest round when enemies have moved into range AND not yet
        # taken meaningful casualties (Round 1 is opportunity-cost-cheaper
        # but most enemy units may still be in their deployment zone and
        # outside 6"). The "force a test on EVERY enemy unit" half of the
        # rule is NOT modelled here — at-strength enemy units (Ld 7-9) pass
        # 2D6-1 most of the time, so the dominant impact is the -1 to
        # already-occurring below-half tests within 6". Cited as
        # `simulator.shadow_in_the_warp`.
        for army in (self.a, self.b):
            if army.shadow_in_the_warp_used_round is not None:
                continue  # already fired this battle
            # Faction-gated to Tyranids armies with at least one alive SYNAPSE
            # source on the battlefield (the codex prerequisite).
            if not any(u.profile.faction == "Tyranids" for u in army.units):
                continue
            has_synapse_alive = any(
                "SYNAPSE" in (u.profile.unit_keywords or ())
                for u in army.alive_units
            )
            if not has_synapse_alive:
                continue
            # AI heuristic: declare from Round 2 onwards (first round
            # enemies have advanced into 6" of Synapse anchors). The
            # `is not None` early-exit above ensures this only fires once;
            # the `>= 2` gate means a battle that only reaches Round 1
            # leaves Shadow undeclared (acceptable: 5-round battles
            # always reach Round 2). By Round 5 the gate is still true
            # so the rule auto-declares as a use-it-or-lose-it fallback.
            if round_num >= 2:
                army.shadow_in_the_warp_used_round = round_num
        # ---- Drukhari Power From Pain (10e army rule). At the start of
        # each Command phase, every Drukhari unit Below Starting Strength
        # gains 1 Pain Token (cap of 1 per unit). While > 0, the unit's
        # models gain Lethal Hits + FNP 6+; the buffs themselves are
        # applied in Unit.attack and Unit.receive_damage. Cited as
        # `simulator.power_from_pain`.
        #
        # iter-DRK fix: "Below Starting Strength" is the 10e core term
        # for "this unit contains fewer models than its starting strength"
        # — it ONLY applies to multi-model units, and ONLY once a whole
        # model has been destroyed (not "lost any wounds at all"). A
        # single-model unit (CHARACTER, VEHICLE, MONSTER, single-model
        # MOUNTED, etc.) is never Below Starting Strength even if its
        # last wound is one chip short of dying — the codex confirms
        # this explicitly. The previous gate (`current_health < health`)
        # fired the instant any wound was taken (e.g. a Raider taking a
        # single chip damage), giving every Drukhari unit FNP 6+ and
        # Lethal Hits from round 2 onwards — a massive over-buff vs the
        # codex trigger. We now require BOTH:
        #   (a) the unit is multi-model (min_models >= 2), AND
        #   (b) it has lost at least one whole model's worth of wounds.
        # `wounds_per_model = profile.health / profile.min_models` (this
        # is how the catalogue builder assigns squad totals).
        # Reference: https://wahapedia.ru/wh40k10ed/factions/drukhari/
        # DRK-PAIN-TOKENS-V2: "cap of 1 per unit" means one Pain Token
        # per codex unit (codex squad), not one per simulator Unit
        # instance. The simulator expands each codex squad into N
        # individual Unit instances (one per model). Without a squad-name
        # gate, every dead model instance satisfies the Below Starting
        # Strength check (current_health = 0 <= profile.health -
        # wounds_per_model), and each gets its own pain_token, producing
        # an 11.8x token amplification vs the codex cap of 1 per squad.
        # The fix mirrors the SOROR-V1 / TAU-MARKERLIGHTS-V1 pattern:
        # deduplicate on profile.name so at most one Unit instance per
        # codex squad name holds a pain_token. Note: pain_tokens are
        # currently inert (the per-datasheet ability effects are not yet
        # wired), so this is a correctness fix for when those abilities
        # are added, not a direct sim-outcome change.
        for army in (self.a, self.b):
            # Track which codex squad names already hold or have been
            # awarded a Pain Token this command phase. One token per
            # codex squad (profile.name) is the codex cap.
            _pain_token_awarded: set = set()
            for u in army.units:
                if u.profile.faction != "Drukhari":
                    continue
                if u.pain_tokens >= 1:
                    # Already holds a token from a prior round: mark
                    # this codex squad as covered so no sibling instance
                    # receives a duplicate token.
                    _pain_token_awarded.add(u.profile.name)
                    continue
                if u.profile.name in _pain_token_awarded:
                    continue   # codex-squad cap: one token per squad
                # Single-model units can never be Below Starting Strength.
                if u.profile.min_models < 2:
                    continue
                wounds_per_model = u.profile.health / u.profile.min_models
                # Below Starting Strength = lost at least one full model.
                if u.current_health <= u.profile.health - wounds_per_model:
                    u.pain_tokens = 1
                    _pain_token_awarded.add(u.profile.name)
        # ---- Adepta Sororitas Acts of Faith (10e army rule). At the
        # start of each battle round, every Sororitas army gains 1
        # Miracle die (an unmodifiable pre-rolled D6 value, banked in a
        # pool). Additional dice are gained when a friendly Sororitas
        # unit is destroyed — that branch fires in
        # `_maybe_award_miracle_die` from the destroyed-unit hooks
        # alongside Blood Tithe / Judgement Tokens. Dice are spent in
        # `Unit.attack` to substitute the lowest banked die that flips
        # a fail -> success on hit / wound / save rolls. Cited as
        # `simulator.acts_of_faith`. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/
        for army in (self.a, self.b):
            # SOROR-ACTS-OF-FAITH-V1: use alive_units so dice are only
            # generated while at least one Sororitas unit is alive — the
            # codex rule "If your Army Faction is Adepta Sororitas" implies
            # an active army. Dead units were previously included via
            # army.units (includes destroyed models), which incorrectly
            # awarded a die every round-start even after the last Sororitas
            # model died. Cited as `simulator.acts_of_faith`.
            if any(u.profile.faction == "Adepta Sororitas" for u in army.alive_units):
                army.gain_miracle_dice(1, random)
        # ---- Adeptus Mechanicus Doctrina Imperatives (10e army rule).
        # At the start of each battle round the AdMech player picks ONE of
        # two imperatives — "protector" (+1 BS on ranged attacks, defensive
        # -1 to be hit in melee against eligible AdMech units) or "conqueror"
        # (+1 WS on melee attacks, +1 AP on all attacks for BATTLELINE-adjacent
        # units). Wahapedia preamble: "all units from your army that have the
        # Doctrina Imperatives ability gain the relevant abilities shown below."
        # MR-D (claude/sim-calibration-5) corrected the prior implementation
        # which fabricated a -1-to-hit penalty side that does not exist in
        # the published rule. Active until the end of the battle round; we
        # reset to None first so a faction-tag flip mid-battle doesn't leak
        # stale state, then re-pick via the strategy heuristic. The
        # individual modifiers are applied in Unit.attack, faction-gated on
        # the attacker (or target for the Protector defensive side).
        # ADMECH-DOCTRINA-V1: use alive_units (not army.units which includes
        # dead models) so the pick only fires while at least one AdMech unit
        # remains alive on the board — mirrors the SOROR-ACTS-OF-FAITH-V1
        # pattern and prevents the imperative from being set from dead-unit
        # faction tags after the army is wiped out. Cited as
        # `simulator.doctrina_imperatives`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            army.doctrina_imperative = None
            if any(u.profile.faction == "Adeptus Mechanicus" for u in army.alive_units):
                army.doctrina_imperative = pick_doctrina_imperative(army, opponent)
        # ---- Adeptus Astartes Oath of Moment (army rule, 10e). At the start
        # of each Command phase a Marine player picks one enemy unit; every
        # Marine attack against that unit re-rolls the Hit roll (full hit
        # re-rolls, not just 1s; codex grants HIT re-rolls only — no wound
        # re-roll) until the start of the next Command phase. We reset to
        # None at the top of the round so a stale uid never leaks across
        # rounds (the buff only fires while uid == current target). Cited
        # as `simulator.oath_of_moment`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            # Snapshot prior round's target before clearing — _pick_oath_target
            # uses this to rotate off a still-alive anchor when a comparable
            # runner-up exists, so the picker doesn't lock onto one unit for
            # the whole game (iter-5 diag: 1.42 unique targets / 5 picks).
            army.prev_oath_target_uid = army.oath_target_uid
            army.oath_target_uid = None
            if any(is_marine_faction(u.profile.faction) for u in army.units):
                self._pick_oath_target(army, opponent, round_num)
        # ---- Adeptus Mechanicus Machine Vengeance (Belisarius Cawl Canticle,
        # 10e). Parallel to Oath of Moment above. At the start of each Command
        # phase, while a Belisarius Cawl model is alive, the AdMech player
        # designates one enemy unit; every friendly AdMech attack against that
        # unit re-rolls the Hit roll until the start of the next Command phase.
        # Reset to None at the top of the round so a stale uid never leaks
        # across rounds (the buff only fires while uid == current target). The
        # faction gate here is the cheap pre-filter; _pick_machine_vengeance_target
        # itself no-ops unless a Belisarius Cawl model is alive, so the two
        # together gate it correctly. Cited as `simulator.machine_vengeance`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            army.machine_vengeance_target_uid = None
            if any(u.profile.faction == "Adeptus Mechanicus" for u in army.units):
                self._pick_machine_vengeance_target(army, opponent, round_num)
        # ---- World Eaters Blood Tithe spend (10e army rule). The codex
        # allows spending at the start of any phase; we elect once per round
        # at the start of the Command phase, priority-greedy on the WE
        # army. Order:
        #   BT >= 4: spend 4, set blood_tithe_lethal_hits_round = round_num
        #            (read by Unit.attack against the live battle round to
        #            grant [LETHAL HITS] on WE-faction attackers for this
        #            round only — collapses the codex's "this phase" scope).
        #   BT >= 3: spend 3, gain +1 CP (capped at the per-round +1 ceiling
        #            via min(6, command_points+1) — matches the per-round
        #            drip behaviour the simulator already applies for the
        #            Command-phase CP gain).
        # The 1-BT charge-roll re-roll, 2-BT +1-to-wound-vs-target, and 5-BT
        # auto-pass Battle-shock are skipped intentionally: the simulator's
        # charge loop doesn't expose a re-roll hook, the target-tagging gate
        # is a per-target side-band that doesn't ride the existing buff plumbing,
        # and the auto-pass is a rare per-battle event whose impact on MAE
        # would be negligible. Cited as `simulator.blood_tithe`.
        for army in (self.a, self.b):
            if not any(u.profile.faction == "World Eaters" for u in army.units):
                continue
            if army.blood_tithe >= 4:
                army.blood_tithe -= 4
                army.blood_tithe_lethal_hits_round = round_num
            elif army.blood_tithe >= 3:
                army.blood_tithe -= 3
                army.command_points = min(6, army.command_points + 1)
        # Clear any per-round transient stratagem flags from the previous
        # round (Disgustingly Resilient, Lightning-Fast Reactions, etc.)
        # before deciding whether to spend CP on a new batch this round.
        self._clear_transient_stratagem_flags(self.a)
        self._clear_transient_stratagem_flags(self.b)
        # ---- Drukhari Combat Drugs (army rule, 10e). Applied here at the
        # start of each Command phase to match the codex timing: "At the
        # start of your Command phase, select which Combat Drugs will be
        # active for your army until the start of your next Command phase."
        # The `_clear_transient_stratagem_flags` call above zeroed any
        # drug bonus from the previous round first; `_apply_combat_drugs`
        # then re-applies for the current round (Round 1 only, because
        # only Adrenalight is modelled and it cannot repeat). Rounds 2+
        # leave the drug bonuses at 0 (no other drugs wired yet).
        # Cited as `simulator.combat_drugs`.
        self._apply_combat_drugs(round_num)
        # ---- Chaos Space Marines Dark Pacts (10e army rule). At the start
        # of the round we pick at most one CSM unit to declare a Dark Pact:
        # it gains [LETHAL HITS] OR [SUSTAINED HITS 1] for the phase in
        # return for a Leadership test that, on failure, inflicts D3
        # mortal wounds on the pacting unit. The codex wording fires "when
        # the unit is selected to shoot or fight"; SwegHammer's round-loop
        # collapses this to a once-per-round elect at Command-phase start
        # (same as Blood Tithe / Doctrina Imperatives / Oath of Moment).
        # APPROXIMATION: Lethal Hits / Sustained Hits have no per-attack
        # keyword toggle in SwegHammer, so the offensive uplift is routed
        # through `transient_plus_one_to_hit_shooting` and
        # `transient_plus_one_to_wound_melee` on the elected CSM unit —
        # same direction and comparable magnitude as a Lethal/Sustained
        # grant on a 3+/4+ roll. Self-damage IS modelled: 2D6>=Ld test;
        # on failure deal D3 mortal wounds via `receive_damage` (FNP-
        # aware). Cited as `simulator.dark_pacts`.
        self._apply_dark_pacts(round_num)
        # ---- World Eaters Blessings of Khorne (10e army rule). At the
        # start of each battle round, roll 8D6 and activate up to two
        # Blessings using doubles/triples meeting each Blessing's
        # threshold. Each active Blessing applies army-wide to WE units
        # until end of battle round. SwegHammer routes the three
        # modelled Blessings (Martial Excellence, Warp Blades, Cleaving
        # Blows) through the army's per-round `blessings_*_round` stamps
        # that `Unit.attack` reads. Cited as
        # `simulator.blessings_of_khorne`.
        self._apply_blessings_of_khorne(round_num)
        # Battleshock check MUST run before the stratagem dispatcher so
        # battleshocked units are excluded from "use Stratagems to affect
        # that unit" (10e core: while a unit is Battle-shocked, you cannot
        # use Stratagems to affect that unit). The dispatcher reads the
        # `_battleshocked_this_round` set when picking targets via
        # `_most_vulnerable_unit` / `_highest_dpa_unit`. See task #168.
        self._run_battleshock_phase(round_num)
        # Detachment-specific stratagems that fire at the start of a round
        # (Virulent Vectorium, Warhost). Doombolt also fires
        # here as a per-round mortal-wound payload — it's nominally a
        # Shooting-phase trigger but the simulator's per-round dispatcher
        # is the cleanest hook for a deterministic "once per round" spend.
        self._apply_detachment_stratagems(self.a, self.b)
        self._apply_detachment_stratagems(self.b, self.a)
        # ---- Astra Militarum Voice of Command Orders (10e army rule).
        # Each AM OFFICER issues one Order to an eligible BATTLELINE
        # INFANTRY (or VEHICLE if Flexible Command was fired this round)
        # within 6", at the start of the Command phase. Stratagem dispatch
        # MUST run first so Flexible Command / Inspired Command flags are
        # set before Order eligibility is computed. Cited as
        # `simulator.voice_of_command_orders`.
        from .orders import dispatch_orders as _dispatch_orders
        for army in (self.a, self.b):
            _issued = _dispatch_orders(army, self._battleshocked_this_round)
            if self.verbose and _issued:
                for officer_name, target_name, order_name in _issued:
                    print(f"  ORDER: {officer_name} -> {target_name}: {order_name}")
        # Thousand Sons Cabal of Sorcerers — Rituals fire at the start of
        # each Shooting phase. We hook them here (same round-start barrier
        # as detachment stratagems) because the simulator's per-unit shoot
        # loop doesn't break out a phase-start barrier separately. Real
        # 2D6 Psychic test, real Doombolt D3/D3+3 math, real WC thresholds.
        # Cited as `simulator.cabal_of_sorcerers`.
        self._run_cabal_rituals()
        # Magnus the Red — Unearthly Power (Crimson King default selection).
        # Wahapedia: "At the start of the battle round, select one of the
        # abilities in the Crimson King section. Until the start of the
        # next battle round, this model has that ability." We default to
        # Impossible Form ("Each time an attack is made against this Psyker
        # (excluding Psychic Attacks), subtract 1 from the Damage
        # characteristic of that attack."), the most-damage-sponging of
        # the three Crimson King options and the simulator's only one
        # cleanly representable. Time Flux (+2" Move aura on TSON) and
        # Treason of Tzeentch (HAZARDOUS on an enemy unit's ranged
        # weapons) are not wired — they require movement-aura and
        # opponent-weapon-mod plumbing the simulator does not expose.
        # Cited as `simulator.magnus_unearthly_power_impossible_form` in
        # data/rule_citations.d/thousand_sons.json.
        for army in (self.a, self.b):
            for u in army.alive_units:
                if u.profile.name == "Magnus the Red":
                    self._set_transient_squad(u, "transient_minus_one_damage_taken")
        # ---- Imperial Knights Bondsman abilities (Command phase).
        # Valourstrike Lance detachment rule. BSData v10.6.0 (Imperium -
        # Imperial Knights - Library.cat.gz) verbatim: "In your Command phase,
        # one or more models from your army with a Bondsman ability can use that
        # ability. For each one that does, select one friendly ARMIGER model
        # within 12\" of that model … Until the start of your next Command
        # phase, that ARMIGER model is affected by that Bondsman ability."
        # SwegHammer applies Paladin's Duty (Lethal Hits + Lance melee) as a
        # uniform proxy for all Questoris + Cerastus class knights. The
        # Armiger receiver is identified as any alive non-TITANIC IK unit
        # within 12" of the giver.
        # Cited as `VALOURSTRIKE_LANCE.bondsman_enabled`.
        for army in (self.a, self.b):
            det = army.resolve_detachment()
            if det is None or not getattr(det, "bondsman_enabled", False):
                continue
            self._apply_bondsman_abilities(army)
        # Phase I — fresh arrivals from the scout phase carry over INTO
        # Round 1 (set by _run_scout_phase). From Round 2 onwards we reset
        # the set first, THEN call _arrive_from_reserves so units arriving
        # this round are flagged for "skip movement" but those that arrived
        # last round are eligible to move normally.
        #
        # Round 1: do NOT reset `_fresh_arrivals` (scouted units inherit
        # their flag), and call `_arrive_from_reserves` to handle Cult
        # Ambush (Genestealer Cults army rule) — every GSC unit lands at
        # the top of Round 1 via the same arrival path. Regular deep
        # strikers are gated off Round 1 inside _arrive_from_reserves so
        # only ambush-flagged units actually come on here.
        if round_num >= 2:
            self._fresh_arrivals = set()
        self._arrive_from_reserves(round_num)
        for army in (self.a, self.b):
            for u in army.units:
                u.moved_this_round = False
                # Fall Back (10e core): the shoot/charge lockout only lasts
                # the turn the unit fell back, so clear it at the top of
                # every round before the new Movement phase runs.
                u.fell_back_this_round = False
                # Pariah Nexus action state (wave 74): clear last round's
                # action so the unit is free to shoot/charge again this round
                # unless it elects an action afresh.
                u.action_this_round = None
                # Wave 121: clear any stale pursuit target from the previous
                # round (belt-and-braces; the per-turn reset in
                # _run_round_vanilla_turns is the primary clear).
                u.pursue_target = None
                # Wave 133 Stage A: clear any stale dedication on the same
                # belt-and-braces basis (the per-turn reset in
                # _run_round_vanilla_turns is the primary clear).
                u.dedicated_card = None

        # Pre-compute on-objective state for the round so Unit.attack() can
        # cheaply apply detachment buffs gated on objective control (Awakened
        # Dynasty +1 to wound is the first user; future detachments can
        # share the flag).
        for army in (self.a, self.b):
            for u in army.units:
                u.on_objective = any(
                    _distance(u.position, (obj.x, obj.y)) <= obj.control_radius
                    for obj in self.map.objectives
                )

        # Battleshock phase already ran before the stratagem dispatcher
        # (task #168 — stratagems can't target battleshocked units, so the
        # test must populate `_battleshocked_this_round` first). See
        # `_run_battleshock_phase` for the rule logic.

        # ---- Coordinated army-level activation plan (#161). At the start of
        # each round, each army picks ONE plan that biases both its activation
        # ORDER (units physically aligned with the plan activate first) and
        # the per-unit strategy layer (objective/charge biases). Without this,
        # the AI picks each activation independently and no alpha strike
        # materialises. Internal AI scheduler — not a 10e rule, no
        # citation required. Gated off in vanilla mode: `activation_queue`
        # already short-circuits to score-only sort when `army_plan is None`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            if self.rules.coordinated_army_plan:
                army.army_plan = pick_army_plan(army, opponent, round_num, self.map)
            else:
                army.army_plan = None

        first, second = (
            (self.a, self.b) if random.random() < 0.5 else (self.b, self.a)
        )

        # ---- T'au Empire Markerlights → Guided (10e army-wide). At the start
        # of each Shooting phase, MARKERLIGHT-keyword T'au units mark enemies
        # for that army's shooters. SwegHammer's alternating activation loop
        # doesn't materialise a global Shooting-phase barrier, so we populate
        # the per-army `guided_enemy_uids` set ONCE per round (treating both
        # players' Shooting phases as one batched window, since within the
        # round T'au is the only faction reading the set and only its own
        # attackers benefit). The set is cleared at end-of-round below.
        # Cited as `simulator.markerlights`.
        self._run_markerlight_phase(self.a, self.b)
        self._run_markerlight_phase(self.b, self.a)

        if self.rules.alternating_activations:
            self._run_round_alternating(first, second)
        else:
            self._run_round_vanilla_turns(first, second)

        # ---- Clear Markerlight tokens at end of turn (Wahapedia: "until
        # the end of the turn"). Resetting here so the next round's
        # `_run_markerlight_phase` repopulates cleanly without stale uids.
        self.a.guided_enemy_uids = set()
        self.b.guided_enemy_uids = set()

        # Protocol of the Undying Legions (Awakened Dynasty, 1 CP, #194):
        # one extra reanimation pulse before the routine Reanimation
        # Protocols pass, for any unit the AI fired the stratagem on this
        # round. No-op for armies that didn't fire it.
        self._apply_undying_legions_pulse()

        # Reanimation Protocols (#75): revive destroyed models in armies
        # whose detachment carries the Reanimation flag. This SUPERSEDES the
        # old +1-HP-to-alive-units heal path (Awakened Dynasty no longer
        # heals — it brings dead models back). Median D3 = 2 models revived
        # per profile per round.
        self._apply_reanimation()

        # Psychic phase (#94): detachments with psychic_mortal_wounds_per_round
        # deal that many mortal wounds to the highest-threat enemy unit each
        # round. Bypasses armour / save / toughness — pure HP burn. Models
        # Thousand Sons Cabal-Points → Doombolt cadence.
        self._apply_psychic_phase()

        # Leader auras: end-of-round heal_per_round (Tech-Priest Dominus
        # Lord of the Machine Cult repair flavour) and revive_destroyed_per_round
        # (Apothecary Narthecium — return a destroyed INFANTRY model to the
        # led unit) from registered character abilities.
        from .leaders import apply_round_end_healing, apply_round_end_revival
        apply_round_end_healing(self.a)
        apply_round_end_healing(self.b)
        apply_round_end_revival(self.a)
        apply_round_end_revival(self.b)

        # Genestealer Cults Cult Ambush — Resurgence point revival hook.
        # APPROXIMATION: the real rule spends a per-unit-table cost
        # (2–8 points) to add a fresh copy of a destroyed INFANTRY unit in
        # Strategic Reserves. SwegHammer cannot model marker placement /
        # Reserves arrival timing, so this proxy revives one dead GSC
        # INFANTRY unit per round (cost 3 Resurgence points) at full
        # health, dropping it from the existing Deep Strike picker so it
        # lands > 9" from all enemies on the next round's arrival pass.
        # Cited as `simulator.cult_ambush_resurgence`.
        self._apply_cult_ambush_resurgence(self.a, round_num)
        self._apply_cult_ambush_resurgence(self.b, round_num)

        if round_num > 1 and self.rules.cp_catchup_bonus:
            self._award_cp(self.a, self.b)
            self._award_cp(self.b, self.a)

    # ------------------------------------------------------------------
    # Round body — alternating (SwegHammer) vs turn-based (vanilla 10e)
    # ------------------------------------------------------------------

    def _run_round_alternating(self, first: Army, second: Army) -> None:
        """SwegHammer alternating-activation round: pairs of units from
        opposing armies sub-phase by sub-phase (move, shoot, charge, fight),
        first player randomised.

        When `simultaneous_movement` is True (default in SwegHammer mode),
        both units in a pair complete a sub-phase before either advances
        to the next — avoids the second-mover-closes-into-range asymmetry.
        When False, each unit in a pair completes its full
        move→shoot→charge→fight before the next unit acts — closer to the
        per-unit-cadence of bolt-action style activations.
        """
        first_activated: set = set()
        second_activated: set = set()

        while True:
            first_q = first.activation_queue(first_activated, map_=self.map)
            second_q = second.activation_queue(second_activated, map_=self.map)
            if not first_q and not second_q:
                break

            first_unit = first_q[0] if first_q else None
            second_unit = second_q[0] if second_q else None
            if first_unit is not None:
                first_activated.add(id(first_unit))
            if second_unit is not None:
                second_activated.add(id(second_unit))

            if self.rules.simultaneous_movement:
                # Both units complete each sub-phase before either moves on
                if first_unit is not None and first_unit.is_alive:
                    self._do_move(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_move(second_unit, second, first)

                if first_unit is not None and first_unit.is_alive:
                    self._do_shoot(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_shoot(second_unit, second, first)

                if first_unit is not None and first_unit.is_alive:
                    self._do_charge(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_charge(second_unit, second, first)

                if first_unit is not None and first_unit.is_alive:
                    self._do_fight(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_fight(second_unit, second, first)
            else:
                # Each unit completes its full sequence in turn
                for unit, own, foe in (
                    (first_unit, first, second),
                    (second_unit, second, first),
                ):
                    if unit is None:
                        continue
                    if unit.is_alive:
                        self._do_move(unit, own, foe)
                    if unit.is_alive:
                        self._do_shoot(unit, own, foe)
                    if unit.is_alive:
                        self._do_charge(unit, own, foe)
                    if unit.is_alive:
                        self._do_fight(unit, own, foe)

    def _run_round_vanilla_turns(self, first: Army, second: Army) -> None:
        """Vanilla WH40k 10e I-go-you-go turn structure: the first player
        completes their entire turn (Movement → Shooting → Charge → Fight
        across all their units) before the second player begins.

        The per-round state set in `_run_round` (oath target, doctrina
        imperative, battleshock results, fresh-arrival flags) is shared
        across both turns within a round — same logical scope as the
        Command-phase setup that ran once at round start.

        Within each phase, units activate in `activation_queue` order
        (score-only sort because `army_plan is None` under vanilla rules);
        the player picks the order in real play and the heuristic picker
        approximates that choice.
        """
        from .leaders import bump_buffs_generation
        for active, other in ((first, second), (second, first)):
            # Per-Command-phase primary scoring (wave 116, env-gated SWEG_CMDSCORE).
            # 10e scores Primary VP at the end of each player's Command phase —
            # i.e. at the START of that player's turn, on the objectives it
            # controls THEN, before its own movement this turn. The baseline
            # scores Primary once per round, at end of round after BOTH turns,
            # which only credits the post-combat survivor. Scoring here, per
            # player at its own turn start, is the faithful timing the wave-111
            # entering-round (once/round) experiment did not test. Rounds 2-5
            # only (no round-1 primary). No-op unless the gate is set, so the OFF
            # path is byte-identical. Cited as `simulator.primary_vp_command_phase`.
            if self._cmd_score and self._current_round >= 2:
                self._score_objectives(only_for=active.name)
            # Clear the effective_buffs cache once per phase — positions don't
            # change mid-phase, so all units in a phase safely share cached results.
            bump_buffs_generation()
            # Enemy units do not move during our move phase, so their OC on every
            # objective is constant for all activations this phase. Precompute once
            # and pass down to _do_move → pick_move_intent, halving the
            # _oc_on_objective call count (from 10 per activation to 5).
            _objectives = self.map.objectives
            _other_alive = other.alive_units
            _phase_their_oc: Dict[int, int] = {
                id(obj): _oc_on_objective(_other_alive, obj) for obj in _objectives
            }
            # Friendly OC: the move-phase's #1 perf hot spot (re-summed per
            # activation inside pick_move_intent). Maintained INCREMENTALLY here
            # — full scan once, then ±the moved unit's OC on the markers it
            # entered/left after each _do_move — and passed down. Byte-identical
            # to the per-activation rescan; O(friendly·obj) per phase, not O(²).
            _phase_our_oc: Dict[int, int] = {
                id(obj): _oc_on_objective(active.alive_units, obj) for obj in _objectives
            }
            # Wave 121: reset any pursuit targets from the previous turn. The
            # field is per-turn (not per-round) so that each army's turn gets a
            # fresh assignment. When the pursuit gate is off this is a no-op
            # (pursue_target initialises to None and is never set).
            # Wave 133 Stage A: clear dedicated_card on the same per-turn
            # lifecycle so each army's turn gets a fresh dedication assignment.
            # No-op when the secondary gate is off (dedicated_card initialises
            # to None and is never set).
            for u in active.units:
                u.pursue_target = None
                u.dedicated_card = None
            # Wave 121: assign card-pursuit intent BEFORE the move loop so that
            # pick_move_intent can read pursue_target during each unit's
            # activation. No-op when the pursuit gate is off. Called on the
            # active army only (it's the active army's movement phase).
            self._assign_card_pursuit(active, other)
            # Wave 133 Stage A: assign deliberate-dedication intent BEFORE the
            # move loop too, so a dedicated body's pursue_target biases its move
            # toward the card's geographic goal this activation. No-op when the
            # secondary gate is off (SWEG_SECONDARY). Active army only.
            self._assign_card_dedication(active, other)
            # Squad rebuild Stage A (gate SWEG_SQUADACT): reset the per-phase
            # squad move-decision cache so each army's move phase starts fresh.
            # Because the cache only ever holds the active army's squads (it is
            # cleared at the top of each (active, other) iteration here), a plain
            # squad_id key cannot collide across armies. INERT in Stage A — the
            # cache below is populated but never applied; execution stays
            # per-model. No-op when the gate is off (the populate block is
            # gated), so the OFF path is byte-identical.
            self._squad_move_intent = {}
            self._squad_activated_this_phase = set()
            _squadact = __import__("os").environ.get("SWEG_SQUADACT") == "1"
            # Squad rebuild Stage B (gate SWEG_COHERE): snapshot each model's
            # pre-move position so the post-move coherency pass can spend only
            # the model's REMAINING move. FLIPPED to default-ON (wave 170,
            # user-greenlit trial): Unit Coherency is a faithful 10e core rule
            # (cited `simulator.coherency_enforcement`) — the honest baseline
            # enforces it (N=80 4.05 -> 3.93, IK -3.3, holding under-shooters up).
            # Disable only by explicitly setting SWEG_COHERE=0 (retained for A/B).
            _cohere = __import__("os").environ.get("SWEG_COHERE", "1") != "0"
            # Recorded UNCONDITIONALLY (not just under _cohere) so the blocker-
            # makes-way pass (_clear_lane, avenue-2 Stage 2) can compute each
            # friendly's remaining move budget. Stored on self for that access.
            self._move_start_pos = {}
            _move_start_pos = self._move_start_pos
            for unit in list(active.units):
                if not unit.is_alive:
                    continue
                _move_start_pos[unit.uid] = unit.position
                if _squadact:
                    # The squad — not the model — is the real activation unit.
                    # On the squad's FIRST alive model this phase, compute the
                    # squad's move decision once (pick_move_intent is
                    # deterministic and side-effect-free, so this extra call does
                    # NOT touch the RNG stream) and cache it for stages B/D/E,
                    # and emit ONE UnitActivated for the squad. The cache is
                    # INERT: _do_move still runs unchanged for every model below,
                    # so the eval (which reads win/loss, not the event stream) is
                    # byte-identical whether the gate is on or off.
                    sid = getattr(unit, "squad_id", -1)
                    skey = sid if sid >= 0 else id(unit)
                    if skey not in self._squad_activated_this_phase:
                        self._squad_activated_this_phase.add(skey)
                        self._squad_move_intent[skey] = pick_move_intent(
                            unit, active, other, self.map,
                            army_plan=active.army_plan,
                            _phase_their_oc=_phase_their_oc,
                            _phase_our_oc=_phase_our_oc,
                        )
                        self._emit(UnitActivated(
                            unit_uid=unit.uid,
                            army_name=active.name,
                        ))
                self._do_move(unit, active, other, _phase_their_oc=_phase_their_oc,
                              _phase_our_oc=_phase_our_oc)
                # OC-cache incremental maintenance (byte-identical to the per-call
                # rescan): this unit may have entered/left objectives' control
                # radii, so adjust _phase_our_oc by ±its OC on each affected marker.
                # Deterministic (objective list order, no RNG). Units do not die
                # during the move phase, so alive-set membership is stable here.
                _uoc = unit.profile.oc or 0
                if _uoc:
                    _o = _move_start_pos[unit.uid]
                    _n = unit.position
                    if _o != _n:
                        for _obj in _objectives:
                            _r2 = _obj.control_radius * _obj.control_radius
                            _wo = (_o[0] - _obj.x) ** 2 + (_o[1] - _obj.y) ** 2 <= _r2
                            _wn = (_n[0] - _obj.x) ** 2 + (_n[1] - _obj.y) ** 2 <= _r2
                            if _wo != _wn:
                                _phase_our_oc[id(_obj)] += _uoc if _wn else -_uoc
            # Squad rebuild Stage B (gate SWEG_COHERE): now that every model has
            # moved individually, pull any model left out of Unit Coherency back
            # toward its squad within its remaining move. Deterministic; the OFF
            # path skips this entirely and is byte-identical.
            if _cohere:
                self._enforce_squad_coherency(active, _move_start_pos)
            # Avenue-2 Stage 2 (gate SWEG_MOVEPLAN, requires SWEG_COLLISION): make-way
            # un-jam pass. Collision-without-coordination piles a squad's models behind
            # the leader short of their objective; this spreads the jammed models into
            # free slots in the objective's control ring within their remaining budget.
            # No-op (byte-identical) unless both gates are set.
            self._make_way(active, _move_start_pos)
            # Pariah Nexus actions are declared after the Movement phase: a
            # surplus unit on a controlled forward objective may perform Cleanse
            # (wave 74), or a surplus unit pushed into No Man's Land / the enemy
            # DZ may perform Sabotage (wave 75), instead of shooting. Flagged
            # units are skipped by _do_shoot / _do_charge below.
            self._assign_cleanse_actions(active, other)
            self._assign_sabotage_actions(active, other)
            self._assign_burn_actions(active, other)
            self._assign_terraform_actions(active, other)
            # Wave 79: army-level focus fire — nominate the single most valuable
            # durable enemy threat the army can hurt, so its anti-armour
            # concentrates to REMOVE it (how a real list deletes a Knight),
            # instead of every unit independently picking the lowest-HP target.
            self._nominate_focus_target(active, other)
            # Wave 101: collective-crack-gated army focus fire (SWEG_FOCUSFIRE).
            # Nominate the most dangerous enemy brick the firing army can crack
            # COLLECTIVELY this phase (the wave-79 layer above could pick an
            # uncrackable Knight and waste fire; this one cannot). Every unit
            # that can wound the nominee then concentrates on it in _do_shoot.
            self._nominate_focusfire_target(active, other)
            # Squad rebuild Stage D (gate SWEG_SQUADSHOOT): clear the per-phase
            # split-fire plan so this army's Shooting phase plans fresh. Resetting
            # empty containers touches no game state and no RNG, so the OFF path
            # is byte-identical; the plan is only populated (lazily, in _do_shoot)
            # when the gate is on.
            self._squad_fire_plan = {}
            self._squad_fire_planned = set()
            bump_buffs_generation()
            for unit in list(active.units):
                if unit.is_alive:
                    self._do_shoot(unit, active, other)
            bump_buffs_generation()
            for unit in list(active.units):
                if unit.is_alive:
                    self._do_charge(unit, active, other)
            bump_buffs_generation()
            # Fight phase — active player's units fight. Real 10e Fight phase
            # interleaves both players' chargers + locked units; this
            # approximates by giving the active player their full fight pass,
            # and the other player's reactive fights resolve in their own
            # turn's Fight phase. Fights First (`_charging_this_round`) is
            # already round-scoped, so chargers from this round still get
            # the bonus when their own player's turn rolls around.
            #
            # CORE-RULE-FIX-1 — sequence chargers BEFORE non-chargers within
            # the active player's fight pass. Per Wahapedia core rules
            # (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#The-Fight-Phase):
            # "All eligible units that have the FIGHTS FIRST ability must
            # fight in the Fights First step. Then, in the Remaining Combats
            # step, all other eligible units fight." A unit that made a
            # Charge move this turn counts as having FIGHTS FIRST for the
            # turn it charged ("each time you select an eligible unit from
            # your army to fight with that made a Charge move this turn,
            # that unit fights first"). Without this ordering, a non-charger
            # whose activation_queue rank is higher could fight before the
            # charger and waste the charge's positional / buff opportunity.
            # Cited as `simulator.fights_first_chargers`.
            #
            # FF-KEYWORD-1 — extend the priority key to also tier the
            # datasheet-level FIGHTS FIRST keyword (Wyches, Howling Banshees,
            # Custodian Wardens, etc.) into the Fights First step alongside
            # chargers. Per Wahapedia datasheet text the keyword applies
            # every Fight phase, not only the turn the unit charged.
            # Cited as `simulator.fights_first_keyword`.
            # CORE-RULES-AUDIT (2026-05-31): a Battle-shocked unit must be
            # selected to fight at the START of the Remaining Combats step
            # (after Fights First, before other units). Tier it between the
            # Fights First group (0) and normal units (2). See
            # docs/CORE_RULES_AUDIT.md #10.
            def _fight_priority(u):
                charging = u.uid in self._charging_this_round
                ff_keyword = bool(getattr(u.profile, "fights_first", False))
                if charging or ff_keyword:
                    return 0
                if u.uid in self._battleshocked_this_round:
                    return 1
                return 2

            # Group-2 #2 — fight-phase alternation (gate SWEG_FIGHTALT). 10e
            # resolves a Fight phase with BOTH armies' engaged units, alternating
            # one at a time (Fights First step, then Remaining), so a charged
            # defender swings back IN THIS phase instead of waiting for its own
            # turn (the over-credit the wave-163 instrument proved differentially
            # favours melee aggressors). Default OFF: the gate unset runs the
            # original active-only loop verbatim → byte-identical. Cited
            # `simulator.fight_alternation`.
            if __import__("os").environ.get("SWEG_FIGHTALT") == "1":
                self._run_fight_alternation(active, other)
            else:
                ordered = sorted(list(active.units), key=_fight_priority)
                for unit in ordered:
                    if unit.is_alive:
                        self._do_fight(unit, active, other)
            # DAEMONS-DIAG-5: Bloodthirster "Relentless Carnage" — end-of-
            # Fight-phase mortal-wound payload. BSData v10.6.0 Chaos Daemons
            # Library (Bloodthirster datasheet, "Relentless Carnage" ability
            # description) verbatim: "At the end of the Fight phase, you can
            # select one enemy unit within Engagement Range of this model and
            # roll eight D6: for each 4+, that enemy unit suffers 1 mortal
            # wound." Fires once per Bloodthirster per fight pass. Picks the
            # highest-DPA living enemy in 1" engagement range as the codex
            # leaves the choice to the player. Cited as
            # `simulator.relentless_carnage`. Wahapedia source:
            # https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Bloodthirster
            self._apply_relentless_carnage(active, other)

    def _apply_relentless_carnage(self, active: Army, other: Army) -> None:
        """End-of-Fight-phase Bloodthirster mortal-wound payload.

        For each alive Bloodthirster in `active` (the player whose Fight
        phase just resolved), if any enemy unit is within 1" Engagement
        Range, roll eight D6 and inflict one mortal wound per 4+ on the
        chosen enemy. Codex leaves the target choice to the Bloodthirster's
        player; SwegHammer picks the highest-DPA living engagement-range
        enemy as a reasonable approximation of "the most threatening target
        in melee".

        Mortal wounds are FNP-eligible per 10e core rules; routed through
        `receive_damage(..., bonus_fnp=victim.profile.fnp)` so any defender
        FNP applies (matches the Shadow of Chaos failed-test mortal-wound
        delivery convention above). Cited as `simulator.relentless_carnage`
        in data/rule_citations.d/chaos_daemons.json.
        """
        for src in list(active.alive_units):
            if src.profile.name != "Bloodthirster":
                continue
            in_engagement = [
                e for e in other.alive_units
                if _distance(src.position, e.position) <= 1.0
            ]
            if not in_engagement:
                continue
            # Pick the highest-DPA engagement-range enemy. _highest_dpa_unit
            # is army-scoped, so we inline a lightweight DPA-on-this-unit
            # proxy: melee damage potential (mA * mD * mhit_p) as the threat
            # heuristic. Falls back to "first in list" if all are scoreless.
            def _melee_dpa(u):
                p = u.profile
                return (
                    max(1, int(p.melee_attacks))
                    * float(p.melee_damage_per_shot or 0.0)
                    * float(p.melee_hit_probability or 0.0)
                )
            victim = max(in_engagement, key=_melee_dpa)
            mw = sum(1 for _ in range(8) if random.randint(1, 6) >= 4)
            if mw > 0:
                # Mortal wounds spill across the victim unit's models (10e core,
                # _apply_mortal_wounds). Cited as simulator.mortal_wound_spillover.
                self._apply_mortal_wounds(victim, mw)

    # ------------------------------------------------------------------
    # Sub-phases
    # ------------------------------------------------------------------

    @staticmethod
    def _fall_back_crosses_enemy(old_pos, new_pos, defender_army) -> bool:
        """Approximate the 10e "a model moves over/through an enemy model" half
        of the Desperate Escape trigger. Returns True if any enemy model lies
        within Engagement Range (1") of the fall-back path segment old_pos ->
        new_pos AND is more than 1" from old_pos — i.e. an enemy AHEAD in the
        path, not the one the unit is disengaging from at the start. Used by the
        Fall Back branch of `_do_move`. See docs/CORE_RULES_AUDIT.md #2."""
        ox, oy = old_pos
        nx, ny = new_pos
        dx, dy = nx - ox, ny - oy
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq <= 1e-9:
            return False
        for e in defender_army.alive_units:
            if getattr(e, "embarked_in", None) is not None:
                continue
            ex, ey = e.position
            # Skip the enemy being disengaged from (within 1" of the start).
            if (ex - ox) ** 2 + (ey - oy) ** 2 <= 1.0:
                continue
            # Point-to-segment distance from the enemy to the fall-back path.
            t = ((ex - ox) * dx + (ey - oy) * dy) / seg_len_sq
            t = max(0.0, min(1.0, t))
            px, py = ox + t * dx, oy + t * dy
            if (ex - px) ** 2 + (ey - py) ** 2 <= 1.0:
                return True
        return False

    def _enforce_squad_coherency(self, army: Army, move_start_pos: dict) -> None:
        """Squad rebuild Stage B (gate SWEG_COHERE): after every model of the
        active army has taken its individual Movement-phase move, pull any
        model left out of Unit Coherency back toward its squad.

        Why this exists: SwegHammer models one Unit instance per model, and the
        per-model move AI lets each model chase its own intent, so a squad that
        a human player would keep tight scatters — stragglers strand outside the
        3" Objective Control band and the squad contributes only part of its
        Objective Control. Real 10e forbids this: "all of its models must be
        ... moved so that the unit is in Unit Coherency" — every model within 2"
        of a squadmate (cited as `simulator.coherency_enforcement`). This pass
        nudges each straggler toward its squad centroid, spending only the
        movement the model has left this phase (its Move characteristic minus
        the distance it already moved), so no model exceeds its legal move.

        Deterministic — no random draws — so the OFF path (this method is never
        called) is byte-identical, and the ON path adds no RNG-stream divergence
        of its own. Lone models (squad_id < 0) have no coherency requirement and
        are skipped, as are models that Advanced or Fell Back this round (their
        move pools are special-cased and already spent).
        """
        squads: dict = {}
        for u in army.units:
            if not u.is_alive:
                continue
            sid = getattr(u, "squad_id", -1)
            if sid < 0:
                continue
            squads.setdefault(sid, []).append(u)

        for members in squads.values():
            if len(members) < 2:
                continue
            cx = sum(m.position[0] for m in members) / len(members)
            cy = sum(m.position[1] for m in members) / len(members)
            centroid = (cx, cy)
            for m in members:
                nearest = min(
                    _distance(m.position, o.position)
                    for o in members if o is not m
                )
                if nearest <= COHERENCY_INCHES:
                    continue   # already coherent
                if m.uid in self._advanced_this_round or getattr(
                    m, "fell_back_this_round", False
                ):
                    continue   # special move pool, already spent
                used = _distance(move_start_pos.get(m.uid, m.position), m.position)
                remaining = effective_move(m) - used
                if remaining <= 0.0:
                    continue
                old_pos = m.position
                new_pos = _move_toward(old_pos, centroid, remaining, self.map,
                                       **self._collision_kwargs(m))
                if new_pos != old_pos:
                    m.position = new_pos
                    self._did_move_this_round.add(m.uid)
                    m.moved_this_round = True
                    self._emit(UnitMoved(
                        unit_uid=m.uid,
                        from_pos=old_pos,
                        to_pos=new_pos,
                    ))

    def _make_way_slot(self, mover, obj, remaining: float):
        """Avenue-2 Stage 2 helper: find a FREE, reachable point inside `obj`'s
        control ring for `mover` (its base must not overlap any other model, nor end
        within Engagement Range of an enemy). Tries deterministic angles/radii inside
        the ring; returns the first collision-legal point reachable within
        `remaining` inches, else None. No RNG."""
        import math
        kw = self._collision_kwargs(mover)
        if not kw:
            return (obj.x, obj.y)   # collision off — any ring point is fine
        occ, rad, fly = kw["occupants"], kw["mover_radius"], kw["mover_fly"]
        cr = obj.control_radius
        for frac in (0.8, 0.55, 0.95, 0.3):
            rr = cr * frac
            for k in range(8):
                ang = k * (math.pi / 4.0)
                px = obj.x + rr * math.cos(ang)
                py = obj.y + rr * math.sin(ang)
                if (px - mover.position[0]) ** 2 + (py - mover.position[1]) ** 2 > (remaining + 0.01) ** 2:
                    continue
                if self.map.is_blocked((px, py)):
                    continue
                if _collision_pos_legal((px, py), rad, occ, fly):
                    return (px, py)
        return None

    def _clear_lane(self, mover, goal) -> None:
        """Avenue-2 Stage 2 BLOCKER-makes-way (gate SWEG_MOVEPLAN+SWEG_COLLISION): when
        a BIG mover (TITANIC / VEHICLE / MONSTER) heads to `goal`, step FRIENDLY models
        out of its straight lane so it does NOT detour around its own army (the user's
        "move one unit out of the way of another"; the wave-208 mover-sidestep failed
        exactly because a Knight endlessly detoured its own friendlies). Each blocking
        friendly shuffles perpendicular by just enough to clear the lane, within its
        REMAINING move budget. ENEMY blockers are NOT moved (they faithfully screen —
        the Knight stops). Deterministic (uid order); no RNG; O(friendlies) per call."""
        import math
        if not (__import__("os").environ.get("SWEG_MOVEPLAN")
                and __import__("os").environ.get("SWEG_COLLISION")):
            return
        kw = mover.profile.unit_keywords or ()
        if not ("TITANIC" in kw or "VEHICLE" in kw or "MONSTER" in kw):
            return
        army = getattr(mover, "army_ref", None)
        if army is None:
            return
        sx, sy = mover.position
        dx, dy = goal[0] - sx, goal[1] - sy
        seglen = math.hypot(dx, dy)
        if seglen < 0.5:
            return
        ux, uy = dx / seglen, dy / seglen      # unit vector ALONG the path
        px, py = -uy, ux                       # unit vector PERPENDICULAR
        mr = _bc_model_radius_in(mover.profile)
        start_pos = getattr(self, "_move_start_pos", {})
        for f in sorted(army.alive_units, key=lambda u: u.uid):
            if f is mover:
                continue
            fr = _bc_model_radius_in(f.profile)
            fx, fy = f.position
            t = (fx - sx) * ux + (fy - sy) * uy      # projection along the path
            if t < 0.0 or t > seglen:
                continue                              # not ahead on the lane
            signed = (fx - sx) * px + (fy - sy) * py  # perpendicular offset (signed)
            clear = mr + fr + 0.2
            if abs(signed) >= clear:
                continue                              # already out of the lane
            used = _distance(start_pos.get(f.uid, f.position), f.position)
            budget = effective_move(f) - used
            if budget <= 0.0:
                continue
            side = 1.0 if signed >= 0 else -1.0       # push to the nearer side
            step = min(clear - abs(signed), budget)
            nx = max(0.0, min(self.map.width, fx + side * px * step))
            ny = max(0.0, min(self.map.height, fy + side * py * step))
            if self.map.is_blocked((nx, ny)):
                continue
            f.position = (nx, ny)

    def _ring_slots(self, obj, n: int) -> list:
        """Reusable coordination primitive (avenue-2 note A): `n` DISTINCT positions in
        a COHERENT cluster within `obj`'s control ring — every slot within the marker's
        control_radius (so its Objective Control counts) AND within ~2" of a neighbour
        (Unit Coherency). Deterministic concentric hex pattern (centre, then rings); no
        RNG. Used to fan a squad out around a marker instead of stacking on the centre."""
        import math
        cr = obj.control_radius
        pts = [(obj.x, obj.y)]
        # (radius_fraction, count, angle_offset) — all radii < control_radius.
        for frac, count, off in ((0.40, 6, 0.0), (0.72, 12, math.pi / 6.0), (0.93, 12, 0.0)):
            radius = cr * frac
            for k in range(count):
                ang = off + k * (2.0 * math.pi / count)
                pts.append((obj.x + radius * math.cos(ang), obj.y + radius * math.sin(ang)))
                if len(pts) >= n:
                    return pts[:n]
        while len(pts) < n:
            pts.append((obj.x, obj.y))
        return pts[:n]

    def _make_way_target(self, mover, intent, target_pos):
        """Avenue-2 Stage 2 (gate SWEG_MOVEPLAN, requires SWEG_COLLISION): the IN-MOVE
        distinct-slot spread. For an OBJECTIVE-capture move, send each squad model to its
        OWN slot in the marker's control ring (deterministic by uid index) instead of the
        shared centre, so the squad fans out under collision (fills the ring) rather than
        single-filing behind the leader. Faithful (a real squad fans coherently around a
        marker). Returns target_pos unchanged for lone models, non-objective intents, or
        when the gates are off (byte-identical)."""
        if intent in ("HOLD", "ENGAGE", "REPOSITION", "FALL_BACK"):
            return target_pos
        if not (__import__("os").environ.get("SWEG_MOVEPLAN")
                and __import__("os").environ.get("SWEG_COLLISION")):
            return target_pos
        sid = getattr(mover, "squad_id", -1)
        if sid < 0 or not self.map.objectives:
            return target_pos
        obj = min(self.map.objectives,
                  key=lambda o: (target_pos[0] - o.x) ** 2 + (target_pos[1] - o.y) ** 2)
        # Only spread when the move is actually heading ONTO this marker.
        if (target_pos[0] - obj.x) ** 2 + (target_pos[1] - obj.y) ** 2 > (obj.control_radius + 1.5) ** 2:
            return target_pos
        army = getattr(mover, "army_ref", None)
        if army is None:
            return target_pos
        members = sorted((u for u in army.units
                          if u.is_alive and getattr(u, "squad_id", -1) == sid),
                         key=lambda u: u.uid)
        if len(members) < 2:
            return target_pos
        try:
            idx = members.index(mover)
        except ValueError:
            return target_pos
        return self._ring_slots(obj, len(members))[idx]

    def _make_way(self, army: Army, move_start_pos: dict) -> None:
        """Avenue-2 Stage 2 (gate SWEG_MOVEPLAN, requires SWEG_COLLISION): un-jam the
        collision pass. Collision without coordination piles a squad's models behind
        the leader short of their objective (the jam — squad->objective distance rises,
        contested marker-rounds collapse). This post-move pass takes each model that
        ended JAMMED short of its squad's target objective and routes it to a FREE slot
        in that objective's control ring, spending only the model's remaining move
        budget. Pure physical un-jamming (adjacent free space toward the goal) — NO
        strategic look-ahead, per the make-way fidelity rail. Deterministic: squads by
        squad_id, models by uid, fixed candidate slots; no RNG. Byte-identical unless
        both SWEG_MOVEPLAN and SWEG_COLLISION are set."""
        if not __import__("os").environ.get("SWEG_MOVEPLAN"):
            return
        if not __import__("os").environ.get("SWEG_COLLISION"):
            return
        objs = self.map.objectives
        if not objs:
            return
        squads: dict = {}
        for u in army.units:
            if not u.is_alive:
                continue
            sid = getattr(u, "squad_id", -1)
            if sid < 0:
                continue
            squads.setdefault(sid, []).append(u)
        for sid in sorted(squads):
            members = sorted(squads[sid], key=lambda m: m.uid)
            if len(members) < 2:
                continue
            cx = sum(m.position[0] for m in members) / len(members)
            cy = sum(m.position[1] for m in members) / len(members)
            obj = min(objs, key=lambda o: (cx - o.x) ** 2 + (cy - o.y) ** 2)
            cr = obj.control_radius
            for m in members:
                if m.uid in self._advanced_this_round or getattr(m, "fell_back_this_round", False):
                    continue
                d = _distance(m.position, (obj.x, obj.y))
                if d <= cr:
                    continue   # already contesting this marker
                used = _distance(move_start_pos.get(m.uid, m.position), m.position)
                remaining = effective_move(m) - used
                if remaining <= 0.0:
                    continue
                if d - cr > remaining + 0.01:
                    continue   # cannot reach the ring even unobstructed
                slot = self._make_way_slot(m, obj, remaining)
                if slot is None:
                    continue
                old_pos = m.position
                new_pos = _move_toward(old_pos, slot, remaining, self.map,
                                       **self._collision_kwargs(m))
                if new_pos != old_pos:
                    m.position = new_pos
                    self._did_move_this_round.add(m.uid)
                    m.moved_this_round = True
                    self._emit(UnitMoved(unit_uid=m.uid, from_pos=old_pos, to_pos=new_pos))

    def _do_move(self, attacker, attacker_army: Army, defender_army: Army,
                 _phase_their_oc=None, _phase_our_oc=None) -> None:
        # Embarked passengers do not act on their own activation — the
        # transport carries them. The simulator emits UnitActivated for the
        # transport, not the passenger. Cited as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return

        self._emit(UnitActivated(
            unit_uid=attacker.uid,
            army_name=attacker_army.name,
        ))

        # Phase I: units that arrived from reserves THIS round, or scouted
        # at the start of the game (Round 1), already moved as part of that
        # ability — skip their normal-move sub-phase for one activation.
        if attacker.uid in self._fresh_arrivals:
            return

        # Transport voluntary disembark hook (10e core). Fires BEFORE the
        # transport's move so the rule "the transport hasn't moved this turn"
        # is satisfied. Cited as `simulator.disembark`.
        if self._is_transport(attacker) and attacker.passengers:
            self._maybe_disembark_before_move(attacker, attacker_army, defender_army)

        # Disembark lockout (10e core): "If a unit disembarks from a
        # Transport in your Movement phase, it cannot make a Normal,
        # Advance or Fall Back move that turn." Shoot and Charge are NOT
        # blocked (handled separately via _do_shoot / _do_charge). Cited
        # as `simulator.disembark`. The passenger was already placed
        # within 3" of the transport and is treated as having moved its
        # Move characteristic — `_did_move_this_round` / `moved_this_round`
        # are set in `_disembark`, surfacing the move to the Heavy
        # keyword check.
        if attacker.uid in self._disembarked_this_round:
            return

        # Strategy layer (code/strategy.py): role + objective-aware pick of
        # where this unit wants to go. The simulator USED to always march at
        # the nearest enemy, which abandoned objectives and lost VP. Now units
        # consult their role + the live objective state.
        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return
        target_pos, intent = pick_move_intent(
            attacker, attacker_army, defender_army, self.map,
            army_plan=attacker_army.army_plan,
            _phase_their_oc=_phase_their_oc,
            _phase_our_oc=_phase_our_oc,
        )
        # Avenue-2 Stage 2 make-way (distinct-slot spread): on an objective move,
        # redirect this model to its own slot in the marker's control ring so the
        # squad fans out under collision instead of stacking on the centre. No-op
        # (byte-identical) unless SWEG_MOVEPLAN+SWEG_COLLISION and a multi-model squad.
        target_pos = self._make_way_target(attacker, intent, target_pos)

        # Fall Back (10e core). Units already locked in melee that the
        # strategy layer wants to disengage move up to M" toward the picked
        # destination, then take a Desperate Escape test (1D6 per model;
        # each 1 destroys a model — we model unit-per-model, so this is one
        # roll). Falling back blocks shoot / charge for the turn unless the
        # unit has FLY. Cited as `simulator.fall_back` /
        # `simulator.desperate_escape`. Advance-this-turn and Fall Back are
        # mutually exclusive: Fall Back uses the normal-move pool.
        if intent == "FALL_BACK":
            if attacker.uid in self._advanced_this_round:
                # Already advanced this round — don't compound activations.
                return
            normal_move = effective_move(attacker)
            old_pos = attacker.position
            new_pos = _move_toward(
                attacker.position, target_pos,
                float(normal_move), self.map,
                **self._collision_kwargs(attacker),
            )
            if new_pos != old_pos:
                attacker.position = new_pos
                self._did_move_this_round.add(attacker.uid)
                attacker.moved_this_round = True
                self._emit(UnitMoved(
                    unit_uid=attacker.uid,
                    from_pos=old_pos,
                    to_pos=new_pos,
                ))
            attacker.fell_back_this_round = True
            # Desperate Escape test (10e core): roll 1D6 per model in the
            # Falling Back unit; each roll of 1-2 destroys one model. TITANIC
            # and FLY units are exempt. SwegHammer models one Unit per model,
            # so a single D6 is rolled.
            #
            # CORE-RULES-AUDIT (2026-05-31): the test is NOT unconditional. Per
            # 10e it is taken only when the Falling Back unit is Battle-shocked
            # OR one or more of its models moves over/through an enemy model
            # during the move. A clean Fall Back into open space takes NO test.
            # We approximate "moves over an enemy" as an enemy lying within
            # Engagement Range (1") of the fall-back path segment AHEAD of the
            # unit (excluding the enemy it is disengaging from at the start).
            # Previously the test fired on every Fall Back, destroying ~1/3 of
            # models each time and heavily over-taxing disengagement. Cited as
            # `simulator.desperate_escape`. See docs/CORE_RULES_AUDIT.md #2.
            _p = attacker.profile
            if not (_p.titanic or _p.fly) and new_pos != old_pos:
                _shocked = attacker.is_currently_battle_shocked(self._current_round)
                _crosses = self._fall_back_crosses_enemy(
                    old_pos, new_pos, defender_army,
                )
                if (_shocked or _crosses) and random.randint(1, 6) <= 2:
                    attacker.current_health = 0.0
                    if not attacker.is_alive:
                        self._emit(UnitKilled(unit_uid=attacker.uid))
                        self._maybe_apply_deadly_demise(attacker)
            return

        dist = _distance(attacker.position, target_pos)
        if dist < 0.5 or intent == "HOLD":
            return   # already where we want to be — stay and shoot

        # 10e Advance: roll d6, move M+d6, but skip shoot/charge this turn.
        # We Advance only when a normal move would NOT bring us into shooting
        # range of the target — the speed boost is wasted otherwise and the
        # shoot foregone.
        normal_move = effective_move(attacker)
        # For ENGAGE intent, "in range" = weapon range. For CAPTURE/STEAL,
        # "in range" = within the objective's control radius (we want to be on
        # the marker). REPOSITION is a small jiggle (always normal-move).
        if intent in ("ENGAGE", "REPOSITION"):
            range_threshold = attacker.profile.range_inches
        else:
            range_threshold = 3.0   # objective control radius
        needs_to_close = dist - range_threshold
        # Per-squad Advance roll (wave 77, env-gated SWEG_SQUADADV). Real 10e: a
        # unit makes ONE Advance roll (one D6) applied to every model; SwegHammer
        # rolled per model. Same per-unit correctness pattern as the charge roll.
        # Cited as `simulator.advance_per_unit`.
        if needs_to_close > normal_move:
            _sid = getattr(attacker, "squad_id", -1)
            if _sid >= 0 and _sid in self._squad_advance_roll:
                advance_d6 = self._squad_advance_roll[_sid]
            else:
                advance_d6 = random.randint(1, 6)
                if _sid >= 0:
                    self._squad_advance_roll[_sid] = advance_d6
        else:
            advance_d6 = 0
        # Strands of Fate (Aeldari army rule, 10e) — substitute the
        # Advance d6 with a higher Fate die when doing so would clear
        # the remaining distance (the unit Advances *into* range that a
        # natural roll wouldn't reach). The threshold is the d6 we'd need
        # to bridge `needs_to_close - normal_move`; we only spend when the
        # substitution flips a fail -> success. Cited as
        # `simulator.strands_of_fate`. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
        if (
            advance_d6 > 0
            and attacker.profile.faction == "Aeldari"
            and attacker_army.has_fate_dice()
            # AELDARI-STRANDS-V1: per-codex-unit gate. The codex rule is "a
            # unit from your army is making an Advance roll" — ONE fate die per
            # codex unit (squad) per round, not one per model. The simulator
            # instantiates each model as a separate Unit and calls _do_move for
            # each, so without this gate a multi-model squad could spend one
            # Fate die per model per round. Block if this squad has already
            # spent a Fate die on advance this round.
            # task #28 squad_id re-key: use squad_id as the set key when >= 0.
            # Cited as `simulator.strands_of_fate`.
            and attacker_army.unit_budget_available(
                "fate_advance",
                (lambda _sid, _nm: _sid if _sid >= 0 else _nm)(
                    getattr(attacker, "squad_id", -1), attacker.profile.name
                ),
            )
        ):
            need = needs_to_close - normal_move
            if advance_d6 < need and need <= 6:
                sub = attacker_army.pop_fate_die_meeting(int(need))
                if sub is not None:
                    advance_d6 = sub
                    _fate_adv_key = (
                        getattr(attacker, "squad_id", -1)
                        if getattr(attacker, "squad_id", -1) >= 0
                        else attacker.profile.name
                    )
                    attacker_army.mark_unit_budget("fate_advance", _fate_adv_key)
        move_distance = normal_move + advance_d6
        did_advance = advance_d6 > 0

        old_pos = attacker.position
        # Avenue-2 Stage 2 blocker-makes-way: a BIG mover clears FRIENDLIES from its
        # lane (they step aside) then moves STRAIGHT, halting only at ENEMY screens
        # (sidestep=False — no detour around its own army). No-op unless the gates +
        # a big mover. _akw is the big-mover keyword set.
        _akw = attacker.profile.unit_keywords or ()
        _big_mover = "TITANIC" in _akw or "VEHICLE" in _akw or "MONSTER" in _akw
        if _big_mover:
            self._clear_lane(attacker, target_pos)
        new_pos = _move_toward(
            attacker.position, target_pos,
            move_distance, self.map,
            sidestep=not _big_mover,
            **self._collision_kwargs(attacker),
        )
        if new_pos != old_pos:
            attacker.position = new_pos
            # Surface the move to the Heavy keyword check in Unit.attack().
            self._did_move_this_round.add(attacker.uid)
            attacker.moved_this_round = True
            self._emit(UnitMoved(
                unit_uid=attacker.uid,
                from_pos=old_pos,
                to_pos=new_pos,
            ))
        if did_advance:
            self._advanced_this_round.add(attacker.uid)
            self._emit(UnitAdvanced(
                unit_uid=attacker.uid,
                advance_roll=advance_d6,
                total_movement=float(move_distance),
            ))

    def _gladius_active_doctrine(self, attacker, attacker_army: Army) -> str:
        """Return the active Gladius Task Force Combat Doctrine name for
        the given Marine attacker on this round, or '' if none applies.

        The Marine player picks one Doctrine per Command phase; SwegHammer
        rotates deterministically Devastator R1 / Tactical R2 / Assault R3+.
        Faction-gated to ADEPTUS ASTARTES, detachment-gated to Gladius Task
        Force. Real-rule wording is movement-utility only (no damage buff).
        Cited as `simulator.combat_doctrines`. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
        """
        if not is_marine_faction(attacker.profile.faction):
            return ""
        det = attacker_army.resolve_detachment()
        if det is None or det.name != "Gladius Task Force":
            return ""
        r = self._current_round
        if r == 1:
            return "Devastator"
        if r == 2:
            return "Tactical"
        if r >= 3:
            return "Assault"
        return ""

    @staticmethod
    def _is_antiarmour_weapon(p) -> bool:
        """Wave 79: a weapon worth concentrating on a durable threat (a Knight /
        Monster / Vehicle) rather than on chaff — multi-damage, high AP, or with
        an Anti-MONSTER/VEHICLE/TITANIC keyword. Bolter-class guns (D1, AP0) are
        NOT anti-armour and keep clearing infantry."""
        if (getattr(p, "weapon_damage_per_shot", 0) or 0) >= 3:
            return True
        if (getattr(p, "ap", 0) or 0) <= -2:
            return True
        ak = dict(getattr(p, "anti_keywords", ()) or ())
        return any(k in ak for k in ("MONSTER", "VEHICLE", "TITANIC"))

    @staticmethod
    def _is_durable_threat(u) -> bool:
        """Wave 79: an enemy unit worth focus-firing to remove — a big single
        model (a Knight, a Monster, a Vehicle, or any 8+ wound model)."""
        kw = u.profile.unit_keywords or ()
        if "MONSTER" in kw or "VEHICLE" in kw or "TITANIC" in kw:
            return True
        return (u.profile.health or 0) >= 8

    def _threat_priority_bonus(self, attacker, target) -> float:
        """Wave 189 (#75) — THREAT-PRIORITY targeting (env-gated SWEG_THREATPRIO,
        default OFF). The lowest-health target picker never selects a high-wound
        board-dominator: a 26-wound Knight always scores worse than a 14-wound
        Armiger or chaff, so the AI's anti-armour weapons are spent on the easy
        targets and the Knight is essentially never removed — a primary driver of
        the Imperial Knights over-rate (object-trace: 2/5 Knights end untouched at
        full health; a user mathhammer found a real Necron unit kills a Knight in
        ~2.7 turns IF aimed, but the sim aims it at the Armigers). Real players
        COMMIT anti-tank into the board-dominator even at lower kill-efficiency.
        When THIS attacker carries an anti-armour weapon (_is_antiarmour_weapon)
        and the target is a big durable high-threat model (TITANIC, or a
        VEHICLE/MONSTER with >= 18 wounds — a Knight / Titanic / big monster, NOT a
        14-wound Armiger), return a multiplier that lowers the target's effective
        health in the lowest-health picker so the anti-armour weapon prefers it
        over chaff. Even-handed: ANY anti-armour weapon vs ANY such target, no
        faction gate. AI targeting heuristic — no 10e rule citation (a target
        preference, like the screen / synapse / transport target bonuses)."""
        if __import__("os").environ.get("SWEG_THREATPRIO") != "1":
            return 1.0
        if not self._is_antiarmour_weapon(attacker.profile):
            return 1.0
        kw = target.profile.unit_keywords or ()
        if "TITANIC" in kw or (
            ("VEHICLE" in kw or "MONSTER" in kw)
            and (target.profile.health or 0) >= 18
        ):
            return 3.0
        return 1.0

    def _nominate_focus_target(self, army, opponent) -> None:
        """Wave 79 — army-level focus fire (env-gated SWEG_FOCUS). Once per turn,
        nominate the single most valuable durable enemy threat the army can hurt,
        preferring one sitting on an objective (removing the camper frees the
        marker). The army's anti-armour weapons then concentrate on it in
        `_do_shoot`. Asymmetric by construction: an army facing a Knight gets a
        focus target; an army whose opponent has no durable threat does not, so
        this does NOT sharpen the over-shooters' own offence the way the wave-72
        per-unit value picker did. Cited as `simulator.army_focus_fire`."""
        army._focus_target_uid = None
        if __import__("os").environ.get("SWEG_FOCUS") != "1":
            return
        candidates = [u for u in opponent.alive_units if self._is_durable_threat(u)]
        if not candidates:
            return
        # The army must actually carry anti-armour, else focusing is futile.
        if not any(self._is_antiarmour_weapon(u.profile) for u in army.alive_units):
            return

        def _on_objective(u) -> bool:
            for obj in self.map.objectives:
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                if dx * dx + dy * dy <= obj.control_radius * obj.control_radius:
                    return True
            return False

        best = None
        best_score = -1.0
        for c in candidates:
            score = (c.profile.points_cost or 0.0) * (1.5 if _on_objective(c) else 1.0)
            if score > best_score:
                best_score = score
                best = c
        army._focus_target_uid = best.uid if best is not None else None

    # ------------------------------------------------------------------ #
    # Wave 101 — army-level focus fire, collective-crack gated.           #
    #                                                                     #
    # The wave-79 `SWEG_FOCUS` layer nominated a brick purely by its      #
    # points value and pointed the army's anti-armour at it. That         #
    # regressed Imperial Knights: a Knight Paladin (Toughness 11, 26      #
    # wounds, 5+ invulnerable) is durable enough that the victims' fire   #
    # was wasted on a target nobody could actually shift, while the       #
    # over-shooter's own anti-armour sharpened. The instrumented failure  #
    # mode (`docs/FACTION_RESIDUAL_ANALYSIS.md`): an Adeptus Astartes     #
    # list with ~4 Gladiator Lancers — collectively MORE than enough to   #
    # delete one Knight — never killed a single big Knight, because the   #
    # per-unit shooting picker (a lowest-current-health min, the          #
    # shooting-side analogue of the charge won't-crack penalty) always    #
    # routes each unit onto a killable Armiger / chaff instead of the     #
    # 26-wound brick that no single unit cracks.                          #
    #                                                                     #
    # This layer fixes the COORDINATION gap that the won't-crack picker   #
    # leaves: it only ever nominates a brick the firing army can crack    #
    # COLLECTIVELY this phase (summed expected wounds from every          #
    # still-to-activate unit that can wound it >= a sensible fraction of  #
    # its current health). A genuinely uncrackable Knight is NOT          #
    # nominated, so no fire is wasted — the exact wave-79 pathology this  #
    # avoids. When a brick IS collectively crackable, every unit that can #
    # hurt it concentrates fire to finish it (the real counter-Knight     #
    # focus-fire tactic), even though no single unit solos it.            #
    #                                                                     #
    # Faithful + even-handed: army-level coordination for ALL factions vs #
    # ANY brick (Knight, Vehicle, Monster, or any 8+ wound model). It     #
    # does not fabricate damage — it only re-points EXISTING fire onto a  #
    # target the army can already collectively kill. Env-gated            #
    # `SWEG_FOCUSFIRE`; unset reproduces the baseline target scoring      #
    # byte-for-byte. Cited as `simulator.focus_fire`.                     #
    # ------------------------------------------------------------------ #

    # Collective expected wounds must reach this fraction of the brick's
    # current health for the army to commit to focusing it. ~0.85 means
    # "can bring it very low or kill it this phase" — a sensible margin
    # below 1.0 because expected-value proxies under-count spikes
    # (Devastating Wounds, exploding 6s) and because dropping a brick to a
    # sliver still removes its objective-control and most of its threat.
    _FOCUSFIRE_CRACK_FRAC = 0.85

    @staticmethod
    def _ranged_expected_wounds(attacker_profile, target_unit) -> float:
        """Expected wounds one round of SHOOTING from `attacker_profile`
        inflicts on `target_unit`. The ranged analogue of strategy.py's
        melee `_kill_potential_wounds`, used to decide whether the firing
        army can COLLECTIVELY crack a brick this phase.

        Composes universal 10e math, no faction conditionals:
            shots        = attacks
            hit_frac     = hit_probability (torrent auto-hits)
            wound_frac   = standard Strength-vs-Toughness table, raised to the
                           Anti-X floor when the weapon has an Anti-keyword
                           matching the target (Anti-VEHICLE 4+ -> wound on 4+)
            save_fail    = 1 - best(armour-after-AP, invulnerable)
            damage/shot  = per_shot_damage
        Returns 0.0 for a weapon that cannot wound the target at all (e.g.
        a bolter into a Knight: it is never redirected, so no wasted fire).
        """
        from .units import save_probability, wound_probability
        p = attacker_profile
        shots = max(0, getattr(p, "attacks", 0) or 0)
        if shots <= 0:
            return 0.0
        hit_frac = 1.0 if getattr(p, "torrent", False) else (
            getattr(p, "hit_probability", 0.0) or 0.0
        )
        if hit_frac <= 0.0:
            return 0.0
        tp = target_unit.profile
        raw_wound_frac = wound_probability(
            getattr(p, "strength", 4) or 4, tp.toughness
        )
        # Anti-X N+: against a matching keyword the weapon wounds on N+,
        # i.e. a (7-N)/6 floor on the wound fraction. Use the BEST matching
        # threshold. This is what makes a dedicated anti-tank gun (Anti-
        # VEHICLE 4+ lascannon) read as able to hurt a Knight even when raw
        # Strength-vs-Toughness would not.
        target_kw = set(tp.unit_keywords or ())
        anti = getattr(p, "anti_keywords", ()) or ()
        anti_frac = 0.0
        for kw, thresh in anti:
            if kw in target_kw:
                anti_frac = max(anti_frac, max(0.0, (7 - int(thresh)) / 6.0))
        wound_frac = max(raw_wound_frac, anti_frac)
        if wound_frac <= 0.0:
            return 0.0
        # "Genuinely can't hurt it" exclusion (the briefing's no-wasted-fire
        # rule). A weapon whose ONLY wound path is a natural 6 (raw wound
        # fraction <= 1/6, e.g. a Strength-4 bolter into a Toughness-11 Knight)
        # and which carries NO matching Anti-keyword contributes negligibly to
        # cracking a brick. Treat it as unable to hurt the brick so it is never
        # counted toward the collective crack and never redirected — bolters
        # keep clearing chaff. A real anti-tank gun (matching Anti-keyword, or
        # raw wound on 5+ or better) is unaffected.
        if anti_frac <= 0.0 and raw_wound_frac <= (1.0 / 6.0) + 1e-9:
            return 0.0
        save_pass = save_probability(tp.save, getattr(p, "ap", 0) or 0)
        invuln = getattr(tp, "invuln_save", 7) or 7
        invuln_pass = save_probability(invuln) if invuln <= 6 else 0.0
        save_fail = max(0.0, 1.0 - max(save_pass, invuln_pass))
        if save_fail <= 0.0:
            return 0.0
        dmg = p.per_shot_damage or 1.0
        return shots * hit_frac * wound_frac * save_fail * dmg

    @staticmethod
    def _brick_threat_value(u) -> float:
        """How much the firing army WANTS this brick gone — its own offensive
        output (ranged plus melee expected damage characteristic), so a big-gun
        brick (a Knight Castellan, a Gladiator Lancer) outranks an inert hull.
        Used only to break ties between bricks the army can crack: concentrate
        on the single most dangerous one rather than splitting fire."""
        p = u.profile
        ranged = (
            (getattr(p, "attacks", 0) or 0)
            * (getattr(p, "hit_probability", 0.0) or 0.0)
            * (p.per_shot_damage or 0.0)
        )
        melee = (
            (getattr(p, "melee_attacks", 0) or 0)
            * (getattr(p, "melee_hit_probability", 0.0) or 0.0)
            * (getattr(p, "melee_damage_per_shot", 0.0) or 1.0)
        )
        return ranged + melee

    def _nominate_focusfire_target(self, army, opponent) -> None:
        """Wave 101 — collective-crack-gated army focus fire (env-gated
        `SWEG_FOCUSFIRE`). Once per Shooting phase, find the bricks the firing
        army can crack COLLECTIVELY this phase and nominate the single most
        dangerous one as the army's focus target. The per-unit `_do_shoot`
        picker then routes every unit that can wound it onto it, concentrating
        fire to finish it — the real counter-brick focus-fire tactic.

        Unlike wave-79 `SWEG_FOCUS` (which nominated by points and could pick
        an uncrackable Knight), this only nominates a brick when the army's
        SUMMED expected wounds this phase reach `_FOCUSFIRE_CRACK_FRAC` of its
        current health, so a genuinely uncrackable target is never chosen and
        no fire is wasted. Cited as `simulator.focus_fire`.

        Fidelity-revisit sweep #5 (wave 210): now DEFAULT-ON — it makes the AI play
        like a competent player (concentrate to crack a brick this turn, SPREAD off an
        uncrackable one via the crack-fraction gate below). Metric-neutral; kept on the
        AI-realism criterion. `SWEG_FOCUSFIRE=0` reverts (also useful for fast dev evals
        — the per-phase collective-wound nomination is ~2x the eval cost)."""
        army._focusfire_target_uid = None
        if __import__("os").environ.get("SWEG_FOCUSFIRE", "1") == "0":
            return
        bricks = [u for u in opponent.alive_units if self._is_durable_threat(u)]
        if not bricks:
            return
        shooters = [u for u in army.alive_units]
        if not shooters:
            return

        best = None
        best_threat = -1.0
        for brick in bricks:
            # Sum the expected wounds every still-alive friendly unit could
            # put into this brick this phase. Only units that can actually
            # wound it contribute (a bolter squad adds 0 vs a Knight), so the
            # collective total honestly reflects the army's anti-brick output.
            collective = 0.0
            contributors = 0
            for s in shooters:
                ew = self._ranged_expected_wounds(s.profile, brick)
                if ew > 0.0:
                    collective += ew
                    contributors += 1
            # A single solo cracker does not need army coordination (the
            # normal picker would not avoid it once it is the lowest-HP-per-
            # threat option anyway); the value of this layer is concentrating
            # MULTIPLE units. Require at least two contributors so we only
            # override the picker where coordination is the missing piece.
            if contributors < 2:
                continue
            need = self._FOCUSFIRE_CRACK_FRAC * max(1.0, brick.current_health)
            if collective < need:
                continue   # army cannot collectively crack it — do not waste fire
            threat = self._brick_threat_value(brick)
            if threat > best_threat:
                best_threat = threat
                best = brick
        army._focusfire_target_uid = best.uid if best is not None else None

    def _plan_squad_fire(self, first_model, attacker_army: Army,
                         defender_army: Army) -> None:
        """Squad rebuild Stage D (gate SWEG_SQUADSHOOT): compute a unit-level
        split-fire plan for the whole squad on its first firing model, caching a
        target per model uid in `_squad_fire_plan`.

        Real squads split fire: anti-armour models concentrate on a durable brick
        while the rest spread across chaff so they remove MORE enemy units rather
        than over-killing one. SwegHammer's one-Unit-per-model representation
        fires each model independently and the lowest-effective-health picker
        piles the whole squad onto a single target, wasting overkill. This greedy
        planner walks the squad's models tracking the expected wounds already
        COMMITTED to each enemy: each model takes the lowest-effective-health
        enemy it can still meaningfully hurt that is not yet lethally committed,
        so once a target has enough fire on it to die the next model moves on.
        Anti-armour weapons prefer the army focus brick when one is nominated
        (SWEG_FOCUS / SWEG_FOCUSFIRE). A model that can hurt nothing un-committed
        is left unassigned, so `_do_shoot` falls back to its per-model pick.

        The plan is an approximation (expected wounds, not per-model line of
        sight); `_do_shoot` validates each assignment against the firing model's
        own legal candidate pool and falls back if the assigned target is dead or
        unreachable. Deterministic (no RNG): the OFF path never calls this.
        Cited `simulator.split_fire`.
        """
        sid = getattr(first_model, "squad_id", -1)
        if sid >= 0:
            members = [u for u in attacker_army.units
                       if u.is_alive and getattr(u, "squad_id", -1) == sid]
        else:
            members = [first_model]
        enemies = list(defender_army.alive_units)
        if not enemies:
            return
        from .strategy import (
            _astartes_oath_target_bonus,
            _drukhari_fragile_flyer_bonus,
            _kite_target_bonus,
            _screen_target_bonus,
            _synapse_target_bonus,
            _transport_target_bonus,
        )
        focus_uid = getattr(attacker_army, "_focus_target_uid", None)
        ff_uid = getattr(attacker_army, "_focusfire_target_uid", None)
        committed: dict = {}
        for model in members:
            p = model.profile
            target = None
            # Anti-armour concentrates on the nominated focus brick if it can
            # meaningfully hurt it (a bolter into a Knight contributes nothing).
            if self._is_antiarmour_weapon(p):
                for fuid in (ff_uid, focus_uid):
                    if fuid is None:
                        continue
                    cand = next((e for e in enemies if e.uid == fuid), None)
                    if cand is not None and self._ranged_expected_wounds(p, cand) > 0.0:
                        target = cand
                        break
            if target is None:
                # Greedy split: lowest effective health REMAINING after the fire
                # already committed, among enemies this model can hurt and that
                # are not yet lethally committed. Same target-priority bonuses as
                # the per-model picker so plan and fallback agree on priorities.
                best = None
                best_key = None
                for e in enemies:
                    if self._ranged_expected_wounds(p, e) <= 0.0:
                        continue
                    remaining = e.current_health - committed.get(e.uid, 0.0)
                    if remaining <= 0.0:
                        continue   # already has lethal fire assigned — move on
                    bonus = (
                        _screen_target_bonus(e)
                        * _synapse_target_bonus(model, e)
                        * _astartes_oath_target_bonus(model, e, attacker_army)
                        * _transport_target_bonus(e)
                        * _drukhari_fragile_flyer_bonus(e)
                        * _kite_target_bonus(e, attacker_army)
                    )
                    key = remaining / bonus
                    if best is None or key < best_key:
                        best = e
                        best_key = key
                target = best
            if target is None:
                continue   # nothing un-committed to hurt — fall back per-model
            self._squad_fire_plan[model.uid] = target
            committed[target.uid] = committed.get(target.uid, 0.0) + \
                self._ranged_expected_wounds(p, target)

    def _do_shoot(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        # Pariah Nexus action lockout (10e core, wave 74): a unit performing an
        # action (e.g. Cleanse) cannot shoot this turn. Cited as
        # `simulator.secondary_cleanse`.
        if attacker.action_this_round is not None:
            return
        # Embarked passengers cannot shoot on their own activation (10e core).
        # Their fire is folded into the transport's via Firing Deck X. Cited
        # as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return
        # Fall Back lockout (10e core): a unit that Fell Back this turn cannot
        # shoot for the rest of the turn — there is NO FLY exception (the stale
        # 9th-edition "may shoot/charge if it can FLY" carve-out was removed).
        # FLY only lets the unit move over other models during the Fall Back
        # and skip Desperate Escape tests; it does not lift the shoot lockout.
        # Cited as `simulator.fall_back`. Tactical Doctrine (Gladius Task
        # Force, R2) explicitly lifts this lockout for ADEPTUS ASTARTES units
        # in a Gladius army: "This unit is eligible to shoot and declare a
        # charge in a turn in which it Fell Back." Cited as
        # `simulator.combat_doctrines`.
        if attacker.fell_back_this_round:
            if self._gladius_active_doctrine(attacker, attacker_army) != "Tactical":
                return
        # 10e: a unit that Advanced this turn cannot shoot, unless its weapon
        # is Assault — or the unit's army can spend a Battle Focus token to
        # trigger the Star Engines Agile Manoeuvre (Aeldari rule, VEHICLE
        # units only) — or Feigned Retreat (Warhost stratagem) or Matchless
        # Agility / Aggressive Mobility (Battle Host / Mont'ka stratagems) has
        # been fired this round to grant transient Assault on the unit — or
        # Mont'ka's Killing Blow detachment rule is active and we are in
        # rounds 1-3 (army-wide [ASSAULT] grant to T'au Empire ranged weapons)
        # — or the unit is ADEPTUS ASTARTES in a Gladius army under the active
        # Devastator Doctrine (R1): "This unit is eligible to shoot in a turn
        # in which it Advanced." Cited as `MONTKA.army_wide_assault_rounds_1_3`
        # and `simulator.combat_doctrines`.
        #
        # Star Engines (Wahapedia Battle Focus): "When an ASURYANI VEHICLE
        # unit from your army Advances, you can spend one Battle Focus token;
        # until the end of that turn, ranged weapons equipped by models in
        # that unit have the [ASSAULT] ability." Gate therefore requires BOTH
        # ASURYANI AND VEHICLE keywords. Previously the gate only checked
        # ASURYANI, incorrectly allowing Aspect Warriors, Guardian Defenders,
        # Wraithguard, Dark Reapers etc. to shoot after Advancing — fixing
        # Aeldari overperformance (+15 gated at wave-58 close). Cited as
        # `simulator.battle_focus` (data/rule_citations.d/keywords_and_mechanics.json).
        if attacker.uid in self._advanced_this_round and not attacker.profile.assault:
            kw = attacker.profile.unit_keywords or ()
            det = attacker_army.resolve_detachment()
            montka_assault_window = (
                det is not None
                and getattr(det, "army_wide_assault_rounds_1_3", False)
                and self._current_round <= 3
                and (attacker.profile.faction or "").lower() in ("t'au empire", "tau empire")
            )
            # Bold Gallantry (Imperial Knights Valourstrike Lance detachment rule):
            # "Each time an IMPERIAL KNIGHTS unit from your army Advances, until
            # the end of the turn, ranged weapons equipped by IMPERIAL KNIGHTS
            # models from your army have the [ASSAULT] ability." (BSData v10.6.0,
            # Imperium - Imperial Knights - Library.cat.gz). When bold_gallantry
            # is True and the attacker is an Imperial Knights unit that has
            # Advanced, skip the Advance-lockout (mirrors the [ASSAULT] grant).
            # Cited as `VALOURSTRIKE_LANCE.bold_gallantry`.
            bold_gallantry_window = (
                det is not None
                and getattr(det, "bold_gallantry", False)
                and (attacker.profile.faction or "") == "Imperial Knights"
            )
            # Relentless Onslaught (Necrons Cursed Legion detachment rule, 10e).
            # BSData v10.6.0 (Necrons.cat.gz, rule id 1dfc-5377-99ac-a700):
            # "ranged weapons equipped by NECRONS VEHICLE and NECRONS MOUNTED
            # models (excluding TITANIC models) from your army have the [ASSAULT]
            # ability." When relentless_onslaught is True and the attacker is a
            # NECRONS VEHICLE or MOUNTED unit (NOT TITANIC) that has Advanced,
            # skip the Advance-lockout (mirrors the [ASSAULT] grant on its ranged
            # weapons). Same exemption pathway as Mont'ka's army-wide window and
            # Valourstrike Lance's Bold Gallantry; faction- and keyword-gated per
            # the verbatim rule. The +1-to-Hit half of Relentless Onslaught lives
            # in Unit.attack. Cited as `simulator.relentless_onslaught` /
            # `CURSED_LEGION.relentless_onslaught`.
            relentless_onslaught_assault_window = (
                det is not None
                and getattr(det, "relentless_onslaught", False)
                and (attacker.profile.faction or "") == "Necrons"
                and ("VEHICLE" in kw or "MOUNTED" in kw)
                and "TITANIC" not in kw
            )
            if attacker.transient_assault_this_round:
                pass   # stratagem already paid for; no token spend
            elif montka_assault_window:
                pass   # detachment rule grants [ASSAULT] free this round
            elif bold_gallantry_window:
                pass   # Bold Gallantry grants [ASSAULT] to IK ranged weapons
            elif relentless_onslaught_assault_window:
                pass   # Relentless Onslaught grants [ASSAULT] to NECRONS
                       # VEHICLE / MOUNTED (non-TITANIC) ranged weapons
            elif self._gladius_active_doctrine(attacker, attacker_army) == "Devastator":
                pass   # Devastator Doctrine grants shoot-after-Advance, free
            elif ("ASURYANI" in kw and "VEHICLE" in kw) and attacker_army.battle_focus_tokens > 0:
                # Star Engines: ASURYANI VEHICLE units only (Wave Serpent,
                # Falcon, Fire Prism, War Walkers, Vypers, Hemlock, etc.)
                attacker_army.battle_focus_tokens -= 1
            else:
                return
        # One Shot: weapon may only fire once per battle. If we've already
        # fired it, skip the activation outright.
        if attacker.profile.one_shot and attacker.uid in self._one_shot_fired:
            return

        # Engagement gate: a unit within 1.5" of an enemy is locked in
        # melee and normally can't shoot. Three exceptions:
        #   - Pistol weapons (always)
        #   - VEHICLE / MONSTER keywords: Big Guns Never Tire (10e core
        #     rule) — they can shoot at -1 to hit (resolved per-attack
        #     inside Unit.attack via the in_engagement_penalty flag)
        # Anything else falls through and skips its shooting activation.
        kw = attacker.profile.unit_keywords or ()
        big_guns_eligible = "VEHICLE" in kw or "MONSTER" in kw
        in_engagement = any(
            _distance(attacker.position, e.position) <= 1.0
            for e in defender_army.alive_units
        )
        # SCREENING / melee-avoidance instrument (#86, gated SWEG_SHOOTLOSS_INSTR,
        # read-only): per faction, the SHOOTING OUTPUT (attacks×hit×dmg) that
        # reaches the shoot gate, split by whether it fires free, is BLOCKED by
        # engagement (non-pistol non-VEHICLE → skips shooting), or fires at the
        # Big-Guns −1 penalty. Localizes how much AM/AdMech under-output is gunlines
        # getting charged/tied up vs the guns genuinely under-dealing.
        if __import__("os").environ.get("SWEG_SHOOTLOSS_INSTR"):
            _p = attacker.profile
            _out = (_p.attacks or 0) * (_p.hit_probability or 0.0) * (_p.weapon_damage_per_shot or 0.0)
            _fac = (_p.faction or "?") or "?"
            if not in_engagement:
                _cat = "free"
            elif _p.pistol:
                _cat = "pistol"
            elif big_guns_eligible:
                _cat = "biggun_penalty"
            else:
                _cat = "blocked"
            _sd = SHOOTLOSS_STATS.setdefault(
                _fac, {"free": 0.0, "pistol": 0.0, "biggun_penalty": 0.0, "blocked": 0.0},
            )
            _sd[_cat] += _out
        if in_engagement:
            if attacker.profile.pistol:
                pass   # pistols shoot freely in engagement
            elif big_guns_eligible:
                attacker.shooting_in_engagement = True
            else:
                return
        else:
            attacker.shooting_in_engagement = False

        rng = attacker.profile.range_inches
        # Embarked passengers are off-board — they cannot be targeted by
        # ranged attacks. Targeting passes through the transport itself.
        # Cited as `simulator.embark`.
        targetable = [
            u for u in defender_army.alive_units
            if getattr(u, "embarked_in", None) is None
        ]
        # Indirect Fire lets us target units we cannot see; otherwise LoS is
        # required. The has_los flag is plumbed into Unit.attack so it can
        # apply the -1 to hit when shooting blind.
        if attacker.profile.indirect_fire:
            candidates = [
                u for u in targetable
                if _distance(attacker.position, u.position) <= rng
            ]
        else:
            attacker_kw = attacker.profile.unit_keywords or ()
            candidates = [
                u for u in targetable
                if _distance(attacker.position, u.position) <= rng
                and self.map.has_line_of_sight(
                    attacker.position, u.position,
                    attacker_keywords=attacker_kw,
                    target_keywords=u.profile.unit_keywords or (),
                )
            ]
        # 10e core targeting restrictions: Look Out Sir + Lone Operative. The
        # helper composes both rules — `friendly_units` to a candidate target
        # is its OWN army's alive units (bodyguards live with the target).
        # Cited as `simulator.look_out_sir` and `simulator.lone_operative`.
        from .army import can_target_for_ranged
        defender_alive = defender_army.alive_units
        candidates = [
            u for u in candidates
            if can_target_for_ranged(attacker, u, defender_alive)
        ]
        # CORE-RULES-AUDIT (2026-05-31): a unit shooting while within Engagement
        # Range (Pistols, or Big Guns Never Tire Monsters/Vehicles) may ONLY
        # target enemy units it is itself within Engagement Range of. Previously
        # an in-engagement shooter could pick any target in range. See
        # docs/CORE_RULES_AUDIT.md #4.
        if in_engagement:
            candidates = [
                u for u in candidates
                if _distance(attacker.position, u.position) <= 1.0
            ]
        # CORE-RULES-AUDIT (2026-05-31): a Blast weapon cannot target a unit
        # that is within Engagement Range of the bearer. See #5.
        if attacker.profile.blast:
            candidates = [
                u for u in candidates
                if _distance(attacker.position, u.position) > 1.0
            ]
        if not candidates:
            return

        # Threat-aware target priority: prefer enemies contesting one of OUR
        # objectives. If multiple, pick the lowest-HP among them (likely to
        # finish off and clear the objective). If none on objectives, fall back
        # to the global lowest-HP target.
        def _contests_our_obj(u):
            for obj in self.map.objectives:
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                if dx * dx + dy * dy <= obj.control_radius * obj.control_radius:
                    return True
            return False

        contesting = [u for u in candidates if _contests_our_obj(u)]
        pool = contesting or candidates
        # S6 (#166) — anti-swarm shooting priority: bias toward OC-bearing
        # chaff before high-DPA bricks. Real tournament play clears the
        # screen first so the opposing army can't flip primary while we
        # chew through Carnifexes. The bonus is multiplicative on a
        # "lower is better" picker, so we *divide* a profile-based score
        # by the bonus — a 1.4x screen gets scored as 0.71x its raw HP
        # for picking purposes, biasing the min() toward it. Additive
        # bias only; the fragile chaff that loses ties anyway still loses,
        # but a Termagant unit at 5 HP outscores a Carnifex at 8 HP.
        # S7 (#168) — synapse-source shooting priority: a non-Tyranid
        # attacker biases toward SYNAPSE units (Hive Tyrant, Tervigon) so
        # killing them revokes the Tyranid army's Battle-shock shelter.
        # Same "lower-is-better" inversion as the screen bonus — we divide
        # the score so a 1.5x bonus reads as 0.67x its raw HP, biasing
        # min() toward it.
        # AI-4 — Adeptus Astartes Oath-of-Moment target priority: when this
        # attacker is a Marine unit and its army has nominated an Oath target
        # this turn, bias the picker toward dumping fire on that target so
        # the army's hit-1 + wound-1 re-rolls compound on a single anchor
        # (matches real-meta Marine play). Gated faction-pure via
        # `is_marine_faction` (excludes Grey Knights / Custodes / Sisters);
        # the LoS+range candidates filter above means the bonus only fires
        # when the Oath target is actually reachable for this attacker.
        # AI-8 — Transport target priority (faction-neutral): real-meta
        # opponents shoot TRANSPORT units first to deny the embarked unit's
        # alpha-strike disembark. The bonus is keyword-gated on the defender
        # (TRANSPORT in unit_keywords) and stacks multiplicatively with the
        # screen / synapse / oath chain. Empty transports get 1.8x; loaded
        # transports get 2.2x (priority dial-up when killing the chassis
        # also disrupts the passengers).
        # DRK-DIAG-11 — Drukhari fragile FLY VEHICLE target priority
        # (defender-faction-gated, keyword-gated, defensive-stat-gated):
        # real-meta opponents shoot Ravagers / Voidravens / Razorwings on
        # round 1 because their alpha-strike damage scales linearly with
        # rounds alive but they die to focused fire (no invuln / no Feel
        # No Pain). The bonus only fires on Drukhari FLY VEHICLEs with
        # no defensive layers; Talos / Cronos (MONSTER, FNP 5+) and
        # non-Drukhari FLY VEHICLEs (Wave Serpent 5++, Caladius 5++)
        # are excluded. 1.5x multiplier stacks with the transport bonus
        # for loaded Raiders / Venoms (1.5 * 2.2 = 3.3x), and stands
        # alone at 1.5x for Ravager / Voidraven / Razorwing (which are
        # not transports).
        from .strategy import (
            _astartes_oath_target_bonus,
            _drukhari_fragile_flyer_bonus,
            _kite_target_bonus,
            _screen_target_bonus,
            _synapse_target_bonus,
            _transport_target_bonus,
        )
        # Squad rebuild Stage D (gate SWEG_SQUADSHOOT): the squad's split-fire
        # plan, computed once on its first firing model, assigns this model a
        # target so the squad spreads its fire across enemies instead of piling
        # the whole unit onto one. Use the assignment only when it is alive and
        # legal for THIS model (present in its own range / line-of-sight pool);
        # otherwise fall through to the focus / lowest-health pick below. OFF
        # path: gate unset, plan empty, `_assigned` stays None — byte-identical.
        # Fidelity-revisit sweep #4 (wave 210): squad split-fire is now DEFAULT-ON —
        # 10e lets a unit's models target different enemy units in range (the legacy
        # path forced the whole unit onto one). Metric-neutral (5.44→5.49 N=80).
        # `SWEG_SQUADSHOOT=0` reverts to the single-target legacy path.
        _assigned = None
        if __import__("os").environ.get("SWEG_SQUADSHOOT", "1") != "0":
            _sid = getattr(attacker, "squad_id", -1)
            _skey = ((attacker_army.name, _sid) if _sid >= 0
                     else (attacker_army.name, id(attacker)))
            if _skey not in self._squad_fire_planned:
                self._squad_fire_planned.add(_skey)
                self._plan_squad_fire(attacker, attacker_army, defender_army)
            _cand = self._squad_fire_plan.get(attacker.uid)
            if _cand is not None and _cand.is_alive and _cand in pool:
                _assigned = _cand
        # Wave 79: army-level focus fire. If the army has nominated a focus
        # target (the most valuable durable enemy threat it can hurt) and THIS
        # attacker is an anti-armour weapon that can meaningfully hurt it, and
        # the target is reachable this activation, concentrate fire on it.
        # Anti-infantry weapons fall through to the normal lowest-HP pick, so
        # bolters keep clearing chaff (weapon-target matched). Cited as
        # `simulator.army_focus_fire`.
        _focus_uid = getattr(attacker_army, "_focus_target_uid", None)
        _focus_target = None
        if _focus_uid is not None and self._is_antiarmour_weapon(attacker.profile):
            _focus_target = next((u for u in pool if u.uid == _focus_uid), None)
        # Wave 101: collective-crack-gated focus fire (SWEG_FOCUSFIRE). If the
        # army has nominated a brick it can crack collectively this phase, and
        # THIS unit can actually wound it (expected wounds > 0 — a bolter into a
        # Knight contributes nothing, so it is never redirected and no fire is
        # wasted), and the brick is reachable this activation, concentrate fire
        # on it. This OVERRIDES the per-unit lowest-health picker (the shooting-
        # side won't-crack behaviour) for the focus brick only. Cited as
        # `simulator.focus_fire`.
        _ff_uid = getattr(attacker_army, "_focusfire_target_uid", None)
        if _ff_uid is not None:
            _ff_target = next((u for u in pool if u.uid == _ff_uid), None)
            if _ff_target is not None and self._ranged_expected_wounds(
                attacker.profile, _ff_target
            ) > 0.0:
                _focus_target = _ff_target
        if _assigned is not None:
            shoot_target = _assigned   # Stage D split-fire assignment (legal here)
        elif _focus_target is not None:
            shoot_target = _focus_target
        else:
            shoot_target = min(
                pool,
                key=lambda u: u.current_health / (
                    _screen_target_bonus(u)
                    * _synapse_target_bonus(attacker, u)
                    * _astartes_oath_target_bonus(attacker, u, attacker_army)
                    * _transport_target_bonus(u)
                    * _drukhari_fragile_flyer_bonus(u)
                    * _kite_target_bonus(u, attacker_army)
                    * self._threat_priority_bonus(attacker, u)
                ),
            )

        # Go To Ground (10e core stratagem, env-gated SWEG_GTG): the defender may
        # spend 1 Command Point, just after this target was selected, to give the
        # targeted INFANTRY unit a 6++ invuln + Benefit of Cover until end of
        # phase. No-op when the gate is unset, so the OFF path is unchanged.
        self._maybe_go_to_ground(defender_army, shoot_target, attacker)

        # Terrain-aware cover: target counts as in cover if it stands inside
        # cover terrain, OR if the army-wide cover flag is set. In 10e all
        # cover terrain (LIGHT_COVER, HEAVY_COVER, RUIN) grants the same single
        # Benefit of Cover (+1 to the armour save, applied in Unit.attack via
        # the in_cover flag). There is no terrain -1-to-hit any more; the
        # in_heavy_cover flag is retained for compatibility but no longer
        # changes the Hit roll.
        saved_cover = shoot_target.in_cover
        saved_heavy = shoot_target.in_heavy_cover
        cover_type = self.map.cover_at(shoot_target.position)
        if cover_type in (
            TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.RUIN,
        ):
            shoot_target.in_cover = True
        if cover_type in (TerrainType.HEAVY_COVER, TerrainType.RUIN):
            shoot_target.in_heavy_cover = True
        # Go To Ground grants the Benefit of Cover (+1 save) on every attack while
        # the buff is active, independent of terrain.
        if getattr(shoot_target, "go_to_ground_active", False):
            shoot_target.in_cover = True

        distance = _distance(attacker.position, shoot_target.position)
        has_los = self.map.has_line_of_sight(
            attacker.position, shoot_target.position,
            attacker_keywords=attacker.profile.unit_keywords or (),
            target_keywords=shoot_target.profile.unit_keywords or (),
        )
        # MR-WE-3 Blood Surge — snapshot pre-shot health so we can detect a
        # model destruction event on the defender (Khorne Berzerkers only).
        # See `simulator.blood_surge` in rule_citations.json.
        _blood_surge_health_before = shoot_target.current_health
        dmg = attacker.attack(shoot_target, distance=distance, has_los=has_los)
        # Firing Deck X (10e core, TRANSPORT keyword). If the attacker is a
        # TRANSPORT with embarked passengers and firing_deck > 0, up to X
        # passenger weapons also fire this Shooting phase. Cited as
        # `simulator.firing_deck`.
        if (
            self._is_transport(attacker)
            and getattr(attacker.profile, "firing_deck", 0) > 0
            and attacker.passengers
            and shoot_target.is_alive
        ):
            dmg += self._apply_firing_deck(
                attacker, shoot_target, attacker_army, defender_army,
            )
        shoot_target.in_cover = saved_cover
        shoot_target.in_heavy_cover = saved_heavy
        # Mark One Shot weapons as expended for the rest of the battle.
        if attacker.profile.one_shot:
            self._one_shot_fired.add(attacker.uid)

        target_alive_after = shoot_target.is_alive
        self._emit(UnitShot(
            attacker_uid=attacker.uid,
            target_uid=shoot_target.uid,
            damage=dmg,
            target_hp_after=shoot_target.current_health,
            target_alive_after=target_alive_after,
        ))
        if not target_alive_after:
            self._emit(UnitKilled(unit_uid=shoot_target.uid))
            # Judgement Tokens: if the destroyed unit belonged to a Votann
            # army, the killer (this attacker) earns a token on itself.
            self._maybe_award_judgement_token(
                killer=attacker, killer_army=attacker_army,
                victim=shoot_target, victim_army=defender_army,
            )
            self._maybe_award_blood_tithe(
                killer=attacker, killer_army=attacker_army,
                victim=shoot_target, victim_army=defender_army,
            )
            # Adepta Sororitas Acts of Faith: friendly Sororitas death
            # grants the victim's army +1 Miracle die.
            self._maybe_award_miracle_die(
                victim=shoot_target, victim_army=defender_army,
            )
            # Deadly Demise (10e core): the destroyed unit may detonate.
            self._maybe_apply_deadly_demise(shoot_target)

        # MR-WE-3 Blood Surge (Khorne Berzerkers). After this shot resolves,
        # if the defender is a Khorne Berzerkers unit and lost one or more
        # models from these attacks, it makes a free D6+2" reactive move
        # ending as close as possible to the closest enemy unit. Cited as
        # `simulator.blood_surge`. Faction-gated ("World Eaters") AND
        # name-gated (profile.name == "Khorne Berzerkers") so Eightbound,
        # Exalted Eightbound, Angron, and other WE datasheets DO NOT
        # trigger. Fires per shot resolution so multiple Berzerker units
        # each Surge from their respective shooters.
        self._maybe_apply_blood_surge(
            defender=shoot_target,
            attacker_army=attacker_army,
            health_before=_blood_surge_health_before,
        )

        if self.verbose:
            alive_str = (
                "killed" if not shoot_target.is_alive
                else f"{shoot_target.current_health:.2f}hp left"
            )
            print(
                f"  {attacker_army.name}: {attacker.profile.name}"
                f" -> {shoot_target.profile.name} ({dmg:.2f} dmg, {alive_str})"
            )

    def _maybe_apply_blood_surge(
        self,
        defender,
        attacker_army: Army,
        health_before: float,
    ) -> None:
        """MR-WE-3 — Blood Surge reactive move for Khorne Berzerkers.

        BSData v10.6.0 (Chaos - World Eaters.cat.gz), verbatim:
          "In your opponent's Shooting phase, each time an enemy unit has
          shot, if any models from this unit were destroyed as a result of
          those attacks, this unit can make a Blood Surge move. To do so,
          roll one D6 and add 2 to the roll: models in this unit move a
          number of inches up to this result, but this unit must finish
          that move as close as possible to the closest enemy unit."

        Faction-gated to World Eaters AND name-gated to "Khorne Berzerkers"
        — Eightbound, Exalted Eightbound, Angron etc. do NOT have this
        ability. Triggered per shot resolution (the caller calls this once
        per `_do_shoot` invocation), so multiple Berzerker units each Surge
        in response to their respective shooters. Cited as
        `simulator.blood_surge`. See data/rule_citations.json.

        Movement model: roll D6+2, then close the gap to the nearest enemy
        unit (the shooter's army's nearest unit, since that's "the closest
        enemy unit" from the Berzerkers' point of view at the moment of
        the shot). If the gap is larger than D6+2, advance D6+2 toward
        the nearest enemy via `_move_toward`. If the gap is smaller, move
        directly INTO engagement range (1.0" gap) so the Berzerkers
        translate the surge into a melee threat the same turn — which is
        the rule's intent ("finish as close as possible to the closest
        enemy unit"). Engagement-range floor of 1.0" matches the
        `_do_charge` post-charge placement and the 10e Engagement Range
        of 1".
        """
        # Faction + datasheet gate.
        if defender.profile.faction != "World Eaters":
            return
        if defender.profile.name != "Khorne Berzerkers":
            return
        if not defender.is_alive:
            return  # whole unit wiped — nothing left to Surge

        # "any models from this unit were destroyed" — gate on at least
        # one full model worth of wounds lost across this shot resolution.
        # `current_health` is total wounds across surviving models; a
        # model is destroyed when the unit's health crosses a
        # `wounds_per_model` boundary downward.
        if defender.profile.min_models < 2:
            return  # not a multi-model squad — defensive guard
        wounds_per_model = defender.profile.health / defender.profile.min_models
        if wounds_per_model <= 0:
            return
        models_before = int(health_before / wounds_per_model + 1e-9)
        models_after = int(defender.current_health / wounds_per_model + 1e-9)
        # Round up survivors: if you've taken any wounds into a model
        # you've "wounded" but not "destroyed" it. Match the codex
        # threshold: the floor of (lost_health / wpm) gives the count of
        # destroyed models. Use floor of remaining health on both sides
        # — if a model lost some-but-not-all wounds neither side counts
        # that as destruction.
        lost_health = max(0.0, health_before - defender.current_health)
        models_destroyed = int(lost_health / wounds_per_model + 1e-9)
        if models_destroyed < 1:
            return

        # task #28 squad_id re-key: collect ALL alive squad siblings so they
        # all surge together (the codex rule says "this unit" makes the Blood
        # Surge move — the whole squad moves, not just the model that was shot).
        _defender_squad_id = getattr(defender, "squad_id", -1)
        _defender_army = getattr(defender, "army_ref", None)
        if _defender_army is not None and _defender_squad_id >= 0:
            _surge_squad = [
                u for u in _defender_army.alive_units
                if getattr(u, "squad_id", -1) == _defender_squad_id
            ]
        else:
            # Lone model or no army reference — move only the targeted model.
            _surge_squad = [defender]

        # Pick nearest enemy unit (from the shooting army — those are the
        # "closest enemy" units from the Berzerkers' perspective at the
        # moment of the surge). Fall through gracefully if there's no
        # alive enemy (shouldn't happen since we just shot, but guard
        # against off-board / embarked cases).
        enemy_pool = [
            u for u in attacker_army.alive_units
            if getattr(u, "embarked_in", None) is None
        ]
        if not enemy_pool:
            return
        # Use the first squad member's position as the squad's reference point
        # for finding the nearest enemy (consistent regardless of straggler
        # positions after coherency drift).
        ref_pos = _surge_squad[0].position if _surge_squad else defender.position
        nearest = min(enemy_pool, key=lambda e: _distance(ref_pos, e.position))
        gap = _distance(ref_pos, nearest.position)
        if gap <= 0:
            return  # already co-located, nothing to do

        surge_roll = random.randint(1, 6) + 2   # D6 + 2
        # "finish as close as possible" -> if we can reach engagement
        # range (1.0"), stop at 1.0" gap. Otherwise advance the full
        # surge distance toward the enemy.
        if gap - surge_roll <= 1.0:
            travel = max(0.0, gap - 1.0)
        else:
            travel = float(surge_roll)

        # Move every model in the surge squad toward the same nearest enemy.
        for _surging_model in _surge_squad:
            old_pos = _surging_model.position
            new_pos = _move_toward(old_pos, nearest.position, travel, self.map,
                                   **self._collision_kwargs(_surging_model, allow_engagement=True))
            _surging_model.position = new_pos
            if self.verbose:
                print(
                    f"  [Blood Surge] {_surging_model.profile.name} ({_surging_model.uid}) "
                    f"surged {travel:.1f}\" toward {nearest.profile.name} "
                    f"(gap {_distance(old_pos, nearest.position):.1f}\" -> {_distance(new_pos, nearest.position):.1f}\")"
                )

    # ------------------------------------------------------------------
    # Charge + Fight (Phase B)
    # ------------------------------------------------------------------

    @staticmethod
    def _wants_to_charge(attacker) -> bool:
        """
        Charge-desire heuristic: a unit wants to charge only if its melee
        output is meaningfully higher than its ranged output. Pure shooters
        and tanks stay put; melee-heavy and dual-threat units charge in.
        """
        p = attacker.profile
        if p.melee_attacks <= 0 or p.melee_hit_probability <= 0:
            return False
        melee_dpa = p.melee_attacks * p.melee_hit_probability * (p.melee_damage_per_shot or 1.0)
        ranged_dpa = max(1, p.attacks) * p.hit_probability * p.per_shot_damage
        # 1.0x melee floor avoids vehicles with token bayonets charging Marines.
        return melee_dpa >= max(ranged_dpa, 1.0)

    # Fire Overwatch — Command Point cost of the core stratagem (10e).
    _OVERWATCH_CP_COST = 1
    # Only overwatch when the firing unit can expect to do meaningful damage on
    # 6s-only — otherwise the 1 Command Point is wasted. Threshold in wounds
    # (after the 1/6 hit-rate scaling), deliberately small so a unit that can
    # actually hurt the charger/arriving unit fires, but a unit whose only
    # output on 6s rounds to nothing (a handful of bolter shots into a Knight)
    # holds its Command Point.
    _OVERWATCH_MIN_EXPECTED_WOUNDS = 0.5

    # Go To Ground (10e core Battle Tactic Stratagem, env-gated SWEG_GTG).
    _GTG_CP_COST = 1
    # Only Go To Ground when the incoming attack threatens a meaningful share of
    # the targeted MODEL's remaining wounds — a real player saves the Command
    # Point for serious fire, not a stray shot. Fraction of the targeted model's
    # current health that the attacker's expected wounds must reach. This scales
    # correctly in the one-Unit-per-model representation (a 1-wound model needs
    # >= 0.5 expected wounds; a 3-wound model needs >= 1.5).
    _GTG_THREAT_FRACTION = 0.5
    # Worth-protecting gate (representation-correct). A multi-model squad must
    # still have at least this many models alive (do not burn a Command Point on
    # a near-dead remnant); a single-model INFANTRY unit (e.g. a Character) must
    # itself have at least _GTG_MIN_SOLO_HEALTH wounds.
    _GTG_MIN_MODELS = 3
    _GTG_MIN_SOLO_HEALTH = 4.0

    def _maybe_go_to_ground(self, defending_army: Army, shoot_target, attacker) -> None:
        """Go To Ground (10e universal core stratagem, env-gated SWEG_GTG).

        Trigger: the opponent's Shooting phase, just after an enemy unit has
        selected `shoot_target` as the target of one or more attacks.
        `defending_army` may spend 1 Command Point so that, until the end of the
        phase, all models in the targeted INFANTRY unit have a 6+ invulnerable
        save and the Benefit of Cover (10e core: "all models in your unit have a
        6+ invulnerable save and have the Benefit of Cover"). Cited as
        `simulator.go_to_ground`.

        Even-handed by construction: the only gates are the INFANTRY keyword, the
        unit's remaining wounds, the incoming threat, and the Command Point pool
        — no faction awareness. Fragile board-control armies benefit more only
        because they field more INFANTRY taking heavy fire (emergent, not coded).

        Gate unset (or not "1") → no-op: no Command Point spent, no flag set, no
        random draws, so the OFF path is byte-identical to the baseline.
        """
        # Env gate — FLIPPED to default-ON (wave 155, user-authorised fidelity-
        # first baseline): Go To Ground is a faithful universal core 10e
        # stratagem (audited wave 154 — 1 CP, INFANTRY-only, 6++ + Benefit of
        # Cover, even-handed), so the HONEST baseline runs it. Suppressing it
        # flattered the headline by ~0.15 (the over-shooter infantry exploit it
        # too — the representation floor). Disable only by explicitly setting
        # SWEG_GTG=0 (retained for A/B / debugging).
        if __import__("os").environ.get("SWEG_GTG", "1") == "0":
            return
        if shoot_target is None or not getattr(shoot_target, "is_alive", False):
            return
        # Already gone to ground this phase (the buff persists), or not INFANTRY,
        # or not worth a Command Point → nothing to do.
        if getattr(shoot_target, "go_to_ground_active", False):
            return
        if "INFANTRY" not in (shoot_target.profile.unit_keywords or ()):
            return
        if defending_army.command_points < self._GTG_CP_COST:
            return
        # Worth-protecting gate, representation-correct: a multi-model squad must
        # still field _GTG_MIN_MODELS alive models; a single-model unit must have
        # real wounds. Do not spend a Command Point on a near-dead remnant.
        squad_id = getattr(shoot_target, "squad_id", -1)
        if squad_id >= 0:
            alive_models = sum(
                1 for m in defending_army.units
                if getattr(m, "squad_id", -1) == squad_id and m.is_alive
            )
            if alive_models < self._GTG_MIN_MODELS:
                return
        elif shoot_target.current_health < self._GTG_MIN_SOLO_HEALTH:
            return

        # Only react to genuinely threatening fire (a real player holds the
        # Command Point against a stray shot).
        if attacker is None:
            return
        threat = self._ranged_expected_wounds(attacker.profile, shoot_target)
        if threat < self._GTG_THREAT_FRACTION * shoot_target.current_health:
            return

        # Pay 1 Command Point and set the buff on the whole targeted unit (every
        # model sharing its squad id). The flag grants the 6++ at the save branch
        # in Unit.attack and the Benefit of Cover at the cover application in
        # _do_shoot; it clears with the other per-round transient flags.
        defending_army.command_points -= self._GTG_CP_COST
        squad_id = getattr(shoot_target, "squad_id", -1)
        if squad_id >= 0:
            for m in defending_army.units:
                if getattr(m, "squad_id", -1) == squad_id and m.is_alive:
                    m.go_to_ground_active = True
        else:
            shoot_target.go_to_ground_active = True

    def _fire_overwatch(self, defending_army: Army, enemy_unit) -> None:
        """Fire Overwatch (10e universal core stratagem, env-gated
        SWEG_OVERWATCH).

        Trigger: the opponent's Movement or Charge phase, just after `enemy_unit`
        is set up (arrives from Reserves / Deep Strike) or declares a charge.
        `defending_army` may spend 1 Command Point to have one of its eligible
        units shoot `enemy_unit` as if it were its own Shooting phase, except
        that each ranged attack only hits on an UNMODIFIED Hit roll of 6 (a 1-5
        always fails). Restriction: at most once per battle round per army.

        Gate unset (or not "1") → no-op: no Command Point spent, no unit fires,
        no extra random draws, so the OFF path is byte-identical to the baseline.

        The defender is chosen as the eligible unit (alive, within 24" of
        `enemy_unit`, with line of sight) whose expected wounds against
        `enemy_unit` on a 6s-only Hit roll is highest. If no eligible unit clears
        the minimum-expected-wounds threshold, the Command Point is NOT spent
        (no wasted overwatch). Cited as `simulator.fire_overwatch`.
        """
        # Env gate — FLIPPED to default-ON (wave 155, user-authorised fidelity-
        # first baseline): Fire Overwatch is a faithful universal core 10e
        # stratagem (audited wave 154 — 1 CP, once-per-round-per-army,
        # unmodified-6s-only, both sides, only the moving/charging target), so
        # the HONEST baseline runs it. Suppressing it flattered the headline
        # (the durable Knights overwatch hard — the representation floor).
        # Disable only by explicitly setting SWEG_OVERWATCH=0 (retained for A/B).
        if __import__("os").environ.get("SWEG_OVERWATCH", "1") == "0":
            return
        if enemy_unit is None or not getattr(enemy_unit, "is_alive", False):
            return
        # Once per battle round per army (core-rule "once per turn" mapped to
        # the simulator's per-round flag — see `_overwatched_this_round`).
        if defending_army.name in self._overwatched_this_round:
            return
        # Need at least the stratagem's Command Point to fire.
        if defending_army.command_points < self._OVERWATCH_CP_COST:
            return

        # Build the eligible-defender list: alive, within 24" of the enemy unit,
        # with line of sight to it, not embarked, and actually carrying a ranged
        # weapon. Overwatch is a SHOOTING attack, so a melee-only unit (no shots)
        # cannot fire it.
        best_unit = None
        best_ew = 0.0
        for unit in defending_army.alive_units:
            if getattr(unit, "embarked_in", None) is not None:
                continue
            p = unit.profile
            # A TITANIC unit CANNOT Fire Overwatch (10e core stratagem
            # restriction, verbatim: "You cannot target a TITANIC unit with
            # this Stratagem"). The stratagem's TARGET is the firing /
            # overwatching unit, so a TITANIC unit may not be SELECTED as the
            # overwatcher — it is a restriction on the FIRING unit, not on the
            # enemy being shot (user-corrected, wave 156). This removes the
            # illegal big-Knight overwatch that inflated the IK / Chaos Knights
            # over-rate once Overwatch went default-ON.
            if "TITANIC" in (getattr(p, "unit_keywords", ()) or ()):
                continue
            if (getattr(p, "attacks", 0) or 0) <= 0:
                continue
            dist = _distance(unit.position, enemy_unit.position)
            if dist > 24.0:
                continue
            if not self.map.has_line_of_sight(
                unit.position, enemy_unit.position,
                attacker_keywords=p.unit_keywords or (),
                target_keywords=enemy_unit.profile.unit_keywords or (),
            ):
                continue
            # Expected wounds on a normal Shooting phase, scaled by the 1/6
            # overwatch hit rate (overwatch only hits on an unmodified 6). The
            # helper already returns 0.0 for a weapon that genuinely cannot hurt
            # the target (a bolter into a Knight), so such a unit never overwatches.
            ew = self._ranged_expected_wounds(p, enemy_unit) / 6.0
            if ew > best_ew:
                best_ew = ew
                best_unit = unit

        # No eligible unit can do meaningful damage on 6s → hold the Command
        # Point (no wasted overwatch).
        if best_unit is None or best_ew < self._OVERWATCH_MIN_EXPECTED_WOUNDS:
            return

        # Pay 1 Command Point and mark the army's once-per-round overwatch use.
        defending_army.command_points -= self._OVERWATCH_CP_COST
        self._overwatched_this_round.add(defending_army.name)

        # Resolve the shot through the standard attack pipeline with the
        # overwatch flag, which forces the unmodified-6 hit gate and disables
        # Hit-roll modifiers / re-rolls. Cover is applied the same way the
        # Shooting phase does so the defender's save bonus is honoured.
        target = enemy_unit
        saved_cover = target.in_cover
        saved_heavy = target.in_heavy_cover
        cover_type = self.map.cover_at(target.position)
        if cover_type in (
            TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.RUIN,
        ):
            target.in_cover = True
        if cover_type in (TerrainType.HEAVY_COVER, TerrainType.RUIN):
            target.in_heavy_cover = True
        distance = _distance(best_unit.position, target.position)
        hp_before = target.current_health
        dmg = best_unit.attack(
            target, distance=distance, has_los=True, overwatch=True,
        )
        target.in_cover = saved_cover
        target.in_heavy_cover = saved_heavy

        self._emit(StratagemFired(
            army_name=defending_army.name, stratagem_name="Fire Overwatch",
            cp_cost=self._OVERWATCH_CP_COST,
        ))
        self._emit(UnitShot(
            attacker_uid=best_unit.uid,
            target_uid=target.uid,
            damage=dmg,
            target_hp_after=target.current_health,
            target_alive_after=target.is_alive,
        ))
        if not target.is_alive and hp_before > 0:
            self._emit(UnitKilled(unit_uid=target.uid))
            self._maybe_award_judgement_token(
                killer=best_unit, killer_army=defending_army,
                victim=target, victim_army=self.a if defending_army is self.b else self.b,
            )
            self._maybe_apply_deadly_demise(target)

    def _do_charge(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        """2D6 charge vs the best target ≤12". On success, move into 1" engagement.

        Target picked by code.strategy.pick_charge_target — favours enemies
        weak in melee (gunlines / battlesuits) over near-but-resilient brick
        units, which is closer to real tournament melee play and brings the
        sim's over-rating of T'au / Astartes / Votann shooty factions down.
        """
        # Pariah Nexus action lockout (10e core, wave 74): a unit performing an
        # action cannot declare a charge this turn. Cited as
        # `simulator.secondary_cleanse`.
        if attacker.action_this_round is not None:
            return
        # Embarked passengers cannot charge (10e core). Cited as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return
        if not self._wants_to_charge(attacker):
            return
        # Advance lockout (10e core): a unit that Advanced this turn cannot
        # charge. Assault Doctrine (Gladius Task Force, R3+) explicitly lifts
        # this lockout for ADEPTUS ASTARTES units in a Gladius army: "This
        # unit is eligible to declare a charge in a turn in which it
        # Advanced." Cited as `simulator.combat_doctrines`.
        # Murderer's Cowl (Chaos Daemons — Khorne army rule, 10e) also lifts
        # the lockout for all qualifying Khorne Daemon datasheets. BSData
        # verbatim: "This unit is eligible to shoot and declare a charge in a
        # turn in which it Advanced." Cited as `simulator.murderers_cowl`.
        if attacker.uid in self._advanced_this_round:
            if (
                self._gladius_active_doctrine(attacker, attacker_army) != "Assault"
                and not attacker.profile.murderers_cowl
            ):
                return
        # Fall Back lockout (10e core): a unit that Fell Back this turn cannot
        # declare a charge for the rest of the turn — there is NO FLY exception
        # (the stale 9th-edition carve-out was removed; FLY only grants the
        # move-over and the Desperate Escape skip during the Fall Back move).
        # Tactical Doctrine (Gladius, R2) also lifts this lockout: "This unit
        # is eligible to shoot and declare a charge in a turn in which it Fell
        # Back." Cited as `simulator.fall_back` and `simulator.combat_doctrines`.
        if attacker.fell_back_this_round:
            if self._gladius_active_doctrine(attacker, attacker_army) != "Tactical":
                return

        from .strategy import pick_charge_target
        target, dist = pick_charge_target(attacker, defender_army)
        if target is None:
            return

        # Fire Overwatch (10e core stratagem, env-gated SWEG_OVERWATCH). The
        # charge has now been DECLARED (a valid charge target exists) but has
        # NOT yet resolved. The charge target's army may overwatch the declared
        # charger here, before the 2D6 charge math runs — a charger that loses
        # models / strength to overwatch then makes its charge with the reduced
        # unit, which the existing per-model charge resolution below handles.
        # No-op when the gate is unset. Cited as `simulator.fire_overwatch`.
        self._fire_overwatch(defender_army, attacker)

        # Per-squad charge roll (wave 76). Real 10e: a unit makes ONE 2D6 charge
        # roll; SwegHammer's one-Unit-per-model representation rolled per MODEL,
        # so an N-model squad got N independent attempts — a huge melee-reliability
        # over-rate (an 11-model mob made a 9" charge ~97% of the time vs the real
        # ~28%). Share one 2D6 per squad per round so the squad charges (or fails)
        # as a unit. Lone models (squad_id < 0) keep their own roll. Landed after
        # the env-gated A/B validated it (gated 5.11 → 4.91). This is the
        # activation-economy half of the per-model tax that the decision-overlay
        # could not reach — it works because it CUTS the horde's effective melee
        # output, not just its decisions. Cited as `simulator.charge_per_unit`.
        sid = getattr(attacker, "squad_id", -1)
        if sid >= 0 and sid in self._squad_charge_roll:
            d1, d2 = self._squad_charge_roll[sid]
        else:
            d1 = random.randint(1, 6)
            d2 = random.randint(1, 6)
            if sid >= 0:
                self._squad_charge_roll[sid] = (d1, d2)
        roll = d1 + d2
        # Strands of Fate (Aeldari army rule, 10e) — substitute one of
        # the 2D6 with a Fate die when the natural total would fail the
        # charge. We replace the LOWER d6 with the lowest die in the
        # pool that lifts the total to >= dist. The substitution only
        # fires if it would flip fail -> success (greedy heuristic).
        # Cited as `simulator.strands_of_fate`. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
        if (
            roll < dist
            and attacker.profile.faction == "Aeldari"
            and attacker_army.has_fate_dice()
        ):
            lower = min(d1, d2)
            needed = int(dist) - (roll - lower)   # the die value we need
            sub = attacker_army.pop_fate_die_meeting(max(1, needed))
            if sub is not None:
                roll = roll - lower + sub
        succeeded = (roll >= dist)
        if not succeeded:
            self._emit(UnitCharged(
                unit_uid=attacker.uid, target_uid=target.uid,
                distance=dist, roll=roll, succeeded=False,
            ))
            return

        # Move to within 1" of target — engagement range
        dx = target.position[0] - attacker.position[0]
        dy = target.position[1] - attacker.position[1]
        scale = max(0.0, (dist - 1.0)) / dist
        new_pos = (
            attacker.position[0] + dx * scale,
            attacker.position[1] + dy * scale,
        )
        if not self.map.is_blocked(new_pos):
            attacker.position = new_pos
        self._charging_this_round.add(attacker.uid)
        self._emit(UnitCharged(
            unit_uid=attacker.uid, target_uid=target.uid,
            distance=dist, roll=roll, succeeded=True,
        ))

        # Universal Core Stratagem on a successful charge:
        # * Tank Shock (1 CP, attacker) — VEHICLE chargers deal D3 mortal
        #   wounds.
        self._try_tank_shock(attacker, target, attacker_army)
        # CORE-RULES-AUDIT (2026-05-31): Heroic Intervention has been REMOVED.
        # It is not a 10th-edition rule — it was a 9e mechanic deleted when 10e
        # launched, and the Wahapedia 10e core rules contain no such rule. The
        # prior implementation fired free for every defending CHARACTER within
        # 6" of a charger (a fabricated free 6"/3" move into engagement), over-
        # rating every melee-Character army. See docs/CORE_RULES_AUDIT.md #1.

    def _run_fight_alternation(self, active: Army, other: Army) -> None:
        """Group-2 #2 — faithful 10e Fight-phase alternation (gate SWEG_FIGHTALT).

        Real 10e resolves a Fight phase with the eligible units of BOTH armies,
        not just the active player's: the Fight phase has a Fights First step
        (units that charged this turn or have the Fights First ability) and then
        a Remaining Combats step, and within each step the players alternate
        selecting ONE eligible unit to fight. The Fights First step starts with
        the ACTIVE player (whose chargers strike first); the Remaining Combats
        step starts with the NON-ACTIVE player (the defender picks first — the
        verified 10e order). SwegHammer's vanilla loop fought only the active army's
        units, deferring the defender's retaliation to its own later turn — which
        let melee aggressors delete defenders before they could swing back (the
        over-credit the wave-163 instrument proved differential, ~30x larger for
        the melee over-shooters than for gunlines). This restores the in-phase
        retaliation. Cited `simulator.fight_alternation`.

        A unit fights at most once in this phase (`fought`). Because each battle
        round runs both players' turns, a unit locked across both turns fights in
        BOTH fight phases — twice per round, as 10e intends. Deterministic order
        WITHIN a player's step (the player's free choice in real play) uses a
        melee-threat key so reruns match. The gate-off path (the caller's else
        branch) is unchanged, so OFF is byte-identical.
        """
        fought: set = set()

        def _melee_threat(u) -> float:
            p = u.profile
            return (max(0, int(p.melee_attacks or 0))
                    * float(p.melee_hit_probability or 0.0)
                    * float(p.melee_damage_per_shot or 0.0))

        def _eligible(u, foe: Army) -> bool:
            if not u.is_alive or (u.profile.melee_attacks or 0) <= 0:
                return False
            if u.uid in fought:
                return False
            # Eligible to fight = made a Charge move this turn, OR currently
            # within Engagement Range (1") of an enemy (matches _do_fight's own
            # in-range gate; pile-in then closes the residual gap).
            if u.uid in self._charging_this_round:
                return True
            return any(_distance(u.position, e.position) <= 1.0
                       for e in foe.alive_units)

        def _is_ff(u) -> bool:
            return (u.uid in self._charging_this_round
                    or bool(getattr(u.profile, "fights_first", False)))

        def _next_pick(army: Army, foe: Army, want_ff: bool):
            cands = [u for u in army.units
                     if _eligible(u, foe) and _is_ff(u) == want_ff]
            if not cands:
                return None
            # The player picks their highest-threat eligible unit (stable, with
            # uid tiebreak for determinism).
            return max(cands, key=lambda u: (_melee_threat(u), u.uid))

        for want_ff in (True, False):
            # Verified 10e order (Wahapedia quick-start): "Units that charged
            # this turn fight before all others. Then, starting with the player
            # not currently taking their turn, players alternate fighting." So
            # the Fights First step starts with the ACTIVE player (whose
            # chargers/Fights First units strike first), and the Remaining
            # Combats step starts with the NON-ACTIVE player (the defender picks
            # first — its compensation). side 0 = active, 1 = non-active.
            side = 0 if want_ff else 1
            while True:
                acted = False
                for _ in range(2):
                    army, foe = (active, other) if side == 0 else (other, active)
                    side ^= 1
                    pick = _next_pick(army, foe, want_ff)
                    if pick is not None:
                        fought.add(pick.uid)
                        self._do_fight(pick, army, foe)
                        acted = True
                        break
                if not acted:
                    break

    def _do_fight(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        """Resolve a melee strike if the attacker is in engagement range (1").

        10e Fight phase per-unit sequence is Pile-In -> Fight -> Consolidate.
        Both pile-in and consolidate are mandatory free 3" moves toward the
        closest enemy (Wahapedia core rules). SwegHammer's one-Unit-per-
        model representation means "each model" collapses to "the Unit".
        Cited as `simulator.pile_in` / `simulator.consolidate`.
        """
        # Embarked passengers cannot fight (10e core). Cited as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return
        if attacker.profile.melee_attacks <= 0:
            return
        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return

        # --- Pile-In (10e core): free 3" move toward the closest enemy,
        # taken BEFORE the fight resolves. Gated on the attacker being in
        # actual fight eligibility — within Engagement Range of an enemy
        # OR having charged this turn (per 10e core: "A unit can fight in
        # your Fight phase if either it is within Engagement Range of one
        # or more enemy units, or it made a Charge move this turn").
        # Pile-in often closes the residual gap so the attacks land at
        # the full melee profile.
        nearest_pre = min(
            alive_enemies,
            key=lambda e: _distance(attacker.position, e.position),
        )
        pre_engaged = _distance(attacker.position, nearest_pre.position) <= 1.0
        is_charging_this_turn = attacker.uid in self._charging_this_round
        if (
            (pre_engaged or is_charging_this_turn)
            and not self.map.is_blocked(attacker.position)
        ):
            new_pos = _move_toward(
                attacker.position, nearest_pre.position, 3.0, self.map,
                **self._collision_kwargs(attacker, allow_engagement=True),
            )
            if not self.map.is_blocked(new_pos):
                attacker.position = new_pos

        # #C1 (auto-loop iter1): pick the engagement-range candidate with
        # the highest `_melee_target_score` rather than the geometrically
        # nearest. The score is faction-neutral — it's a pure DPA-vs-
        # durability ratio with role-based screen/synapse/support
        # multipliers that apply universally. Replaces the prior
        # `min(enemies, key=distance)` so that when 2+ enemies are in
        # engagement, the simulator picks the one whose death actually
        # breaks the lock rather than the closest brick.
        in_range = [
            e for e in alive_enemies
            if _distance(attacker.position, e.position) <= 1.0
        ]
        if not in_range:
            return
        target = max(in_range, key=lambda e: _melee_target_score(attacker, e))
        is_charging = attacker.uid in self._charging_this_round
        dmg = attacker.attack(
            target, distance=1.0, mode="melee", is_charging=is_charging,
        )
        alive_after = target.is_alive
        self._emit(UnitFought(
            attacker_uid=attacker.uid,
            target_uid=target.uid,
            damage=dmg,
            target_hp_after=target.current_health,
            target_alive_after=alive_after,
        ))
        if not alive_after:
            self._emit(UnitKilled(unit_uid=target.uid))
            self._maybe_award_judgement_token(
                killer=attacker, killer_army=attacker_army,
                victim=target, victim_army=defender_army,
            )
            self._maybe_award_blood_tithe(
                killer=attacker, killer_army=attacker_army,
                victim=target, victim_army=defender_army,
            )
            self._maybe_award_miracle_die(
                victim=target, victim_army=defender_army,
            )
            self._maybe_apply_deadly_demise(target)
            # CSM-EYE-OF-GODS: Eye of the Gods (Pactbound Zealots, 1 CP).
            # End-of-Fight-phase reactive stratagem fired on the kill site.
            # Real rule: at end of Fight phase, a CSM CHARACTER that
            # destroyed an enemy unit in melee rolls D6+Wounds on the Eye
            # of the Gods table for a permanent stat buff. APPROXIMATION:
            # collapsed to a permanent +1-to-wound-melee snowball stamped
            # on the CHARACTER. The dispatcher self-gates on faction +
            # CHARACTER keyword + Pactbound Zealots detachment + once-per-
            # CHARACTER + CP affordability. Cited as
            # `Stratagem.Eye of the Gods`.
            self._try_eye_of_the_gods(
                killer=attacker, killer_army=attacker_army,
            )

        # Universal Core Stratagem — Counter-Offensive (2 CP, defender):
        # an out-of-sequence fight for the side that just got hit. The
        # heuristic gates on (a) friendly unit in 1.5" of the attacker
        # AND (b) the attacker killed a model. The retaliator strikes
        # `attacker` immediately, before activation continues.
        if attacker.is_alive:
            self._try_counter_offensive(
                loser_army=defender_army, loser_unit=target,
                winner_army=attacker_army, winner_unit=attacker,
                target_killed=not alive_after,
            )

        # --- Consolidate (10e core): free 3" move taken AFTER the fight.
        # Primary path: move up to 3" toward the closest surviving enemy.
        # Objective path (10e core, cited as `simulator.consolidate_objective`):
        # when NO enemies survive at all (combat cleared), the unit may
        # instead move up to 3" toward the nearest objective marker,
        # provided the move ends within the marker's contest radius
        # (control_radius, standard 3"). This mirrors the skilled-play
        # pattern of clearing a combat specifically to consolidate onto a
        # primary objective. The "no enemies within 3" of the end position"
        # condition in the 10e rule text is trivially satisfied when the
        # entire defending force has been destroyed.
        if attacker.is_alive and not self.map.is_blocked(attacker.position):
            remaining = defender_army.alive_units
            if remaining:
                # Normal path: enemies still alive — consolidate toward the
                # nearest surviving enemy (mandatory per 10e core rule).
                nearest_post = min(
                    remaining,
                    key=lambda e: _distance(attacker.position, e.position),
                )
                new_pos = _move_toward(
                    attacker.position, nearest_post.position, 3.0, self.map,
                    **self._collision_kwargs(attacker, allow_engagement=True),
                )
                if not self.map.is_blocked(new_pos):
                    attacker.position = new_pos
            elif self.map.objectives:
                # Objective path: combat cleared, no surviving enemies —
                # move toward nearest objective marker if the move would
                # bring the unit onto (within control_radius of) that marker.
                nearest_obj = min(
                    self.map.objectives,
                    key=lambda o: _distance(attacker.position, (o.x, o.y)),
                )
                obj_pos = (nearest_obj.x, nearest_obj.y)
                # Only move if the end point lands within contest radius.
                move_end = _move_toward(
                    attacker.position, obj_pos, 3.0, self.map,
                    **self._collision_kwargs(attacker, allow_engagement=True),
                )
                if (
                    not self.map.is_blocked(move_end)
                    and _distance(move_end, obj_pos) <= nearest_obj.control_radius
                ):
                    attacker.position = move_end

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, event) -> None:
        for s in self.subscribers:
            s.on_event(event)

    def _run_markerlight_phase(self, army: Army, opponent: Army) -> None:
        """T'au Empire Markerlights → Guided (10e army-wide army rule).

        At the start of this army's Shooting phase, every alive MARKERLIGHT-
        keyword unit in `army` attempts to mark one enemy unit. The marker
        is a weapon that fires in the Shooting phase like any other ranged
        weapon (Wahapedia: Markerlight weapon ability under the T'au army
        rule, see citation `simulator.markerlight_emission`): it requires
        line of sight from the carrier to the candidate, the candidate
        must lie within the Markerlight's 36" range, and the carrier must
        pass a Hit roll against its own Ballistic Skill. On a successful
        hit, the target's uid is added to `army.guided_enemy_uids`.
        Friendly T'au attackers firing at a target in the set gain
        [LETHAL HITS] in `Unit.attack`, gated on the detachment's
        `lethal_hits_on_guided` flag (Mont'ka sets True).

        Before iter27-M1 the emission was a free auto-Guided pipeline —
        no Hit roll, no line-of-sight check, no range gate — which
        inflated Guided uptime far above real play. Adding the three
        gates brings the simulator into line with how a Markerlight
        actually resolves on table.

        SwegHammer simplifications vs the codex Markerlight token-stacking:
            * The codex requires a unit to accrue >= some token count to
              become a Guided unit (specifics vary by edition). SwegHammer
              collapses to "any one successful Markerlight hit => Guided",
              which is a strict upper bound but matches the practical play
              pattern where Pathfinders + Stealth Suits saturate marks
              comfortably in a real game.
            * Range check is straight Euclidean distance from the
              MARKERLIGHT unit's position to the candidate enemy.
            * Line of sight uses the same `Map.has_line_of_sight` helper
              the main Shooting phase uses, plus the `can_target_for_ranged`
              gate so Look Out Sir / Lone Operative apply to Markerlights
              just like to any other ranged weapon.
            * Hit roll uses the carrier's `hit_probability` (its Ballistic
              Skill, converted via `_prob_to_target`). No modifiers are
              applied — Markerlight is the simplest possible ranged shot.
            * One attempt per MARKERLIGHT codex squad (not per model-Unit);
              multi-model squads (Strike Team 10, Stealth Battlesuits 5)
              are deduplicated by profile name with one representative per
              min_models alive models. Single-model vehicles (Sky Ray,
              min_models=1) are unaffected. Selects the highest-points
              live enemy in range+LoS as the threat priority before
              rolling the hit.

        No-op (and no marks) when:
            * `army` has no alive MARKERLIGHT-keyword unit.
            * Opponent has no alive units.
            * Army faction isn't T'au Empire (defensive — the buff is read
              under the T'au attacker gate anyway, but skipping the scan
              saves cycles on every non-T'au turn).
            * Detachment doesn't carry `lethal_hits_on_guided=True` (would
              never be read by `Unit.attack` even if marks were set).

        Cited as `simulator.markerlights` (token effect) and
        `simulator.markerlight_emission` (per-carrier hit roll + LoS +
        range gate added in iter27-M1).
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights
        """
        if (army.units and
                (army.units[0].profile.faction or "").lower()
                not in ("t'au empire", "tau empire")):
            return
        det = army.resolve_detachment()
        if det is None or not getattr(det, "lethal_hits_on_guided", False):
            return
        alive_enemies = opponent.alive_units
        if not alive_enemies:
            return
        _all_ml_units = [
            u for u in army.alive_units
            if "MARKERLIGHT" in (u.profile.unit_keywords or ())
        ]
        if not _all_ml_units:
            return
        from .army import can_target_for_ranged
        from .units import _prob_to_target
        # The simulator decomposes multi-model squads into one Unit object
        # per model (min_models Unit objects per template slot) at
        # archetypes.py:1650-1653. The Markerlight weapon ability belongs to
        # the squad, not to each individual model — a 10-model Strike Team
        # fires ONE Markerlight per Shooting phase, not ten. Iterating over
        # every model-Unit would give 10 Markerlight attempts for one squad.
        #
        # Fix (mirroring the TSON Cabal deduplication at _run_cabal_rituals):
        # group alive MARKERLIGHT units by profile name, then yield one
        # representative per every min_models models alive in that group.
        # Partially-destroyed squads still contribute exactly 1 attempt as
        # long as at least one model survives (the squad's Markerlight drone
        # or equipped model is treated as the last to be removed).
        # Single-model MARKERLIGHT units (Sky Ray Gunship, min_models=1)
        # are unaffected: 1 model = 1 squad = 1 attempt.
        #
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tau-empire/#Markerlights
        # "each T'AU EMPIRE unit that is equipped with one or more
        # Markerlight weapons can be selected to shoot with those weapons
        # ... in your Shooting phase" — unit-level, not model-level.
        # task #28 squad_id re-key: group Markerlight carriers by squad_id
        # (when >= 0) rather than profile.name so that two separate squads of
        # the same datasheet each get their own Markerlight attempt instead of
        # being merged into one group and then chunked by min_models.
        from collections import defaultdict as _dd_ml
        _ml_groups: dict = _dd_ml(list)
        for _u in _all_ml_units:
            _ml_key = getattr(_u, "squad_id", -1)
            if _ml_key < 0:
                # Lone model (no squad_id) — use profile.name as before.
                _ml_key = _u.profile.name
            _ml_groups[_ml_key].append(_u)
        markerlight_units: list = []
        for _ml_key, _ml_group in _ml_groups.items():
            _ml_squad_size = max(1, _ml_group[0].profile.min_models)
            # Each complete or partial chunk of _ml_squad_size alive models
            # represents one codex squad that fires one Markerlight.
            _ml_n_squads = max(1, len(_ml_group) // _ml_squad_size)
            for _ml_i in range(_ml_n_squads):
                markerlight_units.append(_ml_group[_ml_i * _ml_squad_size])
        # 10e core rulebook: Markerlight is a weapon ability with the
        # standard ranged-weapon profile. The basic Markerlight is 36"
        # range across every datasheet in the T'au index. We hold this
        # constant here rather than reading per-weapon range off the
        # profile because SwegHammer's UnitProfile carries one
        # `range_inches` for the unit's primary weapon (Pulse Carbine on
        # Pathfinders, Burst Cannon on Stealth Suits), not for the
        # Markerlight specifically — the Markerlight is a secondary
        # weapon riding on the carrier's BS.
        markerlight_range = 36.0
        marked: set = set()
        for mk in markerlight_units:
            # Range + LoS + Look-Out-Sir / Lone-Op gate the candidate pool
            # before the to-hit roll. Skip unmarked-only targets so each
            # carrier marks a distinct unit when multiple are available.
            candidates = [
                e for e in alive_enemies
                if e.uid not in marked
                and _distance(mk.position, e.position) <= markerlight_range
                and self.map.has_line_of_sight(
                    mk.position, e.position,
                    attacker_keywords=mk.profile.unit_keywords or (),
                    target_keywords=e.profile.unit_keywords or (),
                )
                and can_target_for_ranged(mk, e, alive_enemies)
            ]
            if not candidates:
                continue
            target = max(candidates, key=lambda u: u.profile.points_cost)
            # Hit roll using the carrier's BS. No modifiers — Markerlight
            # is resolved as a plain ranged shot. A roll >= the target's
            # `N+` succeeds; on failure no token is granted.
            hit_target = _prob_to_target(mk.profile.hit_probability)
            roll = random.randint(1, 6)
            if roll >= hit_target:
                marked.add(target.uid)
        army.guided_enemy_uids = marked

    def _pick_oath_target(
        self, army: Army, opponent: Army, round_num: int,
    ) -> None:
        """Adeptus Astartes Oath of Moment — pick this round's oath target.

        AI heuristic: re-pick fresh every Command phase based on the LIVE
        battlefield state (Wahapedia: "At the start of your Command phase,
        select one enemy unit"). Score each alive enemy as
            score = points_cost * (current_health / max_health)
        so wounded fat anchors fade as the next-largest fresh target rises.
        Without the health-ratio weighting the picker used `points_cost`
        alone, which is static — the same anchor scored highest every
        round until it died, producing 1.42 unique targets per 5 picks in
        the iter-5 Marine diagnostic.

        On top of the score, if the highest-scoring candidate matches LAST
        round's pick AND a runner-up exists within 50% of the top score,
        rotate to the runner-up. This models real-player behaviour of
        spreading damage across multiple anchors rather than dumping a
        full round of re-rolls into a unit that's already taking fire.
        When the runner-up is far weaker (e.g. 50pt Cheap vs 300pt
        Expensive at full HP, ratio 0.17 < 0.5), the rotation is
        suppressed and we stay on the dominant threat — preserving the
        intent of the iter-1 `test_oath_picks_highest_points_enemy` test.

        Sets `army.oath_target_uid` and emits `OathTargetChosen`. No-op
        (and no event) when the opponent has no alive units left.

        The buff itself (re-roll all hits against the chosen unit — the
        codex grants HIT re-rolls only, no wound re-roll) is applied in
        Unit.attack, gated on the attacker being a Marine and
        `attacker_army.oath_target_uid == target.uid`.
        """
        alive = opponent.alive_units
        if not alive:
            return

        def score(u: "Unit") -> float:
            max_hp = max(1.0, float(u.profile.health))
            ratio = max(0.0, u.current_health / max_hp)
            return float(u.profile.points_cost) * ratio

        # Sort by live-weighted score, points_cost as a stable tiebreak so
        # round 1 (all full HP) collapses to the legacy "highest points"
        # ordering for test compatibility.
        ranked = sorted(
            alive,
            key=lambda u: (score(u), u.profile.points_cost),
            reverse=True,
        )
        target = ranked[0]
        # Rotate off the prior anchor when a comparable runner-up exists.
        # Threshold 0.5: runner-up must be at least half the top score to
        # justify the swap. Keeps the 300pt-vs-50pt test passing (ratio
        # 0.17 < 0.5) while letting two similar-points anchors alternate.
        if (
            army.prev_oath_target_uid is not None
            and target.uid == army.prev_oath_target_uid
            and len(ranked) >= 2
        ):
            top_score = score(target)
            runner_up = ranked[1]
            if top_score > 0 and score(runner_up) / top_score >= 0.5:
                target = runner_up

        army.oath_target_uid = target.uid
        # squad_id re-key (task #28): store the squad identity alongside the
        # uid so the gate in Unit.attack can match ALL models in the nominated
        # unit, not just the single model whose uid was recorded here.
        army.oath_target_squad_id = getattr(target, "squad_id", -1)
        self._emit(OathTargetChosen(
            army_name=army.name,
            round_num=round_num,
            target_uid=target.uid,
        ))

    def _pick_machine_vengeance_target(
        self, army: Army, opponent: Army, round_num: int,
    ) -> None:
        """Adeptus Mechanicus — pick this round's Machine Vengeance target.

        Belisarius Cawl's "Invocation of Machine Vengeance" Canticle
        (Wahapedia, verbatim): "At the start of your Command phase, select
        one unit from your opponent's army... that enemy unit is your Machine
        Vengeance target. Each time a model in a friendly Adeptus Mechanicus
        unit makes an attack that targets your Machine Vengeance target, you
        can re-roll the Hit roll." This is structurally identical to the
        Adeptus Astartes Oath of Moment (designate one enemy unit each
        Command phase, army-wide Hit re-rolls against it), so this method
        mirrors `_pick_oath_target` directly.

        Gated on a Belisarius Cawl model being ALIVE in `army`: the Canticle
        is a Cawl datasheet ability, so it fires only while he is on the
        board. No-op (no designation) when Cawl is absent/dead or when the
        opponent has no alive units left.

        AI heuristic: re-pick fresh every Command phase off the LIVE board
        state, scoring each alive enemy with the SAME formula as Oath of
        Moment —
            score = points_cost * (current_health / max_health)
        so a wounded fat anchor fades as the next-largest fresh target rises.
        points_cost is the stable tiebreak so round 1 (all full HP) collapses
        to "highest points".

        Sets `army.machine_vengeance_target_uid`. The buff itself (re-roll
        all Hit rolls against the chosen unit) is applied in Unit.attack,
        gated on the attacker being Adeptus Mechanicus and
        `attacker_army.machine_vengeance_target_uid == target.uid`. Cited as
        `simulator.machine_vengeance`.
        """
        # Cawl-alive gate: the Canticle is Cawl's datasheet ability, so the
        # designation only fires while a Belisarius Cawl model is alive in this
        # army. Match by profile name substring (how leaders are identified in
        # leaders.py) — do NOT fabricate a flag. No-op silently when absent: a
        # non-Cawl AdMech army simply never designates, which is correct.
        cawl_alive = any(
            "belisarius cawl" in u.profile.name.lower()
            for u in army.alive_units
        )
        if not cawl_alive:
            return
        alive = opponent.alive_units
        if not alive:
            return

        def score(u: "Unit") -> float:
            max_hp = max(1.0, float(u.profile.health))
            ratio = max(0.0, u.current_health / max_hp)
            return float(u.profile.points_cost) * ratio

        ranked = sorted(
            alive,
            key=lambda u: (score(u), u.profile.points_cost),
            reverse=True,
        )
        army.machine_vengeance_target_uid = ranked[0].uid

    def _maybe_award_blood_tithe(
        self, killer: "Unit", killer_army: Army,
        victim: "Unit", victim_army: Army,
    ) -> None:
        """World Eaters army rule — Blood Tithe (10e).

        Two trigger sources, both awarding +1 BT to the World Eaters army:
          1. A friendly WE unit was destroyed (victim is WE) — award to
             victim_army.
          2. An enemy unit was destroyed by a WE unit (killer is WE) —
             award to killer_army.

        Both can fire at once in a WE mirror-match (victim's army gets +1
        for the death AND killer's army gets +1 for the kill — that's the
        codex behaviour). Non-WE armies are left at 0. Cited as
        `simulator.blood_tithe`.

        PER-UNIT DEDUP (BLOOD-TITHE-AMPLIFICATION fix): the codex awards 1 BT
        "each time a UNIT is destroyed", but SwegHammer's one-Unit-per-model
        representation calls this hook on every MODEL death — so a WE squad
        wiping a 10-model enemy unit would over-accrue +10 BT instead of +1.
        Award only when the victim is the LAST living model of its codex unit
        (no surviving sibling shares its profile.name in its own army). This
        is the standard project-one-unit-per-model-amplification template.
        Known limitation of the profile.name key: two separate codex units of
        the same datasheet count as one (under-counts in that rare case) —
        accepted, far better than the per-model over-count.
        """
        def _victim_unit_destroyed() -> bool:
            return not any(
                s is not victim
                and s.is_alive
                and s.profile.name == victim.profile.name
                for s in victim_army.units
            )
        if not _victim_unit_destroyed():
            return
        if victim.profile.faction == "World Eaters":
            victim_army.blood_tithe += 1
        if killer.profile.faction == "World Eaters":
            killer_army.blood_tithe += 1

    def _maybe_award_miracle_die(
        self, victim: "Unit", victim_army: Army,
    ) -> None:
        """Adepta Sororitas Acts of Faith — Miracle Dice on a friendly
        death. Cited as `simulator.acts_of_faith`. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/

        Codex rule (verbatim): "each time a unit from your army with this
        ability is destroyed, you gain 1 additional Miracle die."

        Two gates apply before awarding:

        1. TRANSPORT exclusion: TRANSPORT units (Immolator, Sororitas Rhino)
           do not carry the Acts of Faith ability on their datasheets — the
           ability is on INFANTRY and WALKER units only. A TRANSPORT death
           must not award a Miracle die. Gate: TRANSPORT in unit_keywords.

        2. SOROR-DETACHMENT-V1 — per-codex-unit (last-instance) gate:
           The codex "unit" maps to one codex-unit / squad (e.g. a 10-model
           Battle Sisters Squad is ONE codex unit). The simulator instantiates
           each model as a separate Unit object, so a 10-model squad produces
           10 sim instances sharing the same profile.name. Without the last-
           instance gate, each instance's death independently fires the trigger,
           giving 10 dice for one codex-unit destruction instead of the
           codex-correct 1. The gate: only award when NO other alive sim
           instance with the SAME profile.name remains in the army (i.e.
           the dying model is the last survivor of its codex unit). The
           alive_units list already excludes the dying victim (current_health
           has already been zeroed before _maybe_award_miracle_die is called).
           Cited as `simulator.acts_of_faith`.

        3. Army-alive gate: do not award when the last Sororitas unit in the
           army just died — the army-rule condition "Army Faction is Adepta
           Sororitas" no longer holds. SOROR-ACTS-OF-FAITH-V1 established
           this gate; it remains unchanged here.
        """
        if victim.profile.faction != "Adepta Sororitas":
            return
        # Gate 1: TRANSPORT exclusion — Immolator / Sororitas Rhino / Repressor
        # do not carry the Acts of Faith ability (infantry/walker ability only).
        # Wahapedia Sororitas datasheets confirm Acts of Faith appears on INFANTRY
        # and WALKER units; TRANSPORT VEHICLE datasheets do not list it.
        if "TRANSPORT" in (victim.profile.unit_keywords or ()):
            return
        # Gate 2 (SOROR-DETACHMENT-V1): last-instance check — only award when
        # this is the LAST alive sim instance in the victim's squad.
        # task #28 squad_id re-key: match by squad_id when both victim and the
        # candidate squad-mate have squad_id >= 0; fall back to profile.name for
        # lone models (squad_id < 0). All instances of the same squad represent
        # a single codex unit; only the squad's total destruction should award
        # 1 die. `alive_units` excludes the dying victim at this point.
        _victim_squad_id = getattr(victim, "squad_id", -1)
        if any(
            (
                (getattr(u, "squad_id", -1) >= 0 and _victim_squad_id >= 0
                 and getattr(u, "squad_id", -1) == _victim_squad_id)
                or
                (_victim_squad_id < 0 and u.profile.name == victim.profile.name)
            )
            for u in victim_army.alive_units
            if u.profile.faction == "Adepta Sororitas"
        ):
            return  # other squad-mates still alive — codex unit not fully destroyed yet
        # Gate 3: SOROR-ACTS-OF-FAITH-V1: use alive_units so the gate correctly
        # prevents awarding a die when the last Sororitas unit in the army just
        # died (the victim is already excluded from alive_units at this point).
        if not any(u.profile.faction == "Adepta Sororitas" for u in victim_army.alive_units):
            return
        victim_army.gain_miracle_dice(1, random)

    # APPROXIMATION: models the retired Eye of the Ancestors rule; current codex army rule is Prioritised Efficiency.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/#Prioritised-Efficiency
    # Real rule (current 10e): Prioritised Efficiency — Yield Points / Hostile Acquisition / Fortify Takeover token economy,
    # not the launch-day "enemies that kill Votann get marked for rerolls" mechanic this code implements.
    def _maybe_award_judgement_token(
        self, killer: "Unit", killer_army: Army,
        victim: "Unit", victim_army: Army,
    ) -> None:
        """Eye of the Ancestors / Judgement Tokens (Leagues of Votann army rule).

        When a non-Votann unit destroys a Votann model, the killer's unit
        earns a token on itself. Tokens stack on the killer for the rest of
        the battle and grant escalating re-roll buffs to subsequent Votann
        attacks targeting that unit (resolved in `Unit.attack`).

        Symmetry: a Votann unit killing another Votann unit (mirror match,
        psychic, etc.) does NOT award a token — only the *opponent* of the
        Votann army marks targets. We pin this off the victim's army
        (`is_votann_army`), not the killer's, so a Votann attacker on a
        Votann victim short-circuits before incrementing.
        """
        if not victim_army.is_votann_army:
            return
        # Don't mark yourself (a Votann unit killing one of its own
        # in some pathological self-damage edge case).
        if killer_army.is_votann_army:
            return
        tokens = victim_army.judgement_tokens
        tokens[killer.uid] = tokens.get(killer.uid, 0) + 1
        self._emit(JudgementTokenAwarded(
            target_uid=killer.uid,
            total_tokens=tokens[killer.uid],
        ))

    def _maybe_apply_deadly_demise(self, victim: "Unit") -> None:
        """Deadly Demise X (10e core rule).

        When a model with this ability is destroyed, roll 1D6 BEFORE removing
        it from the battlefield. On a 6, each unit within 6" of this model
        suffers X mortal wounds. SwegHammer interprets the codex D3/D6/D3+3
        variants as fixed integer expected values at mapper time; the runtime
        sees a single integer in `profile.deadly_demise`.

        Called from every death-detection site (shoot, fight, tank shock,
        counter-offensive, doombolt). Bypasses armour/invuln; routed through
        receive_damage so target FNP and Disgustingly Resilient compose.

        Side effect — Destroyed Transport (10e core): if the dying unit is a
        TRANSPORT, every embarked passenger force-disembarks before removal,
        rolling 1D6 per model and destroying on a 1. Routed here because all
        death-detection sites already fan out through this method. Cited as
        `simulator.destroyed_transport`.
        """
        # Destroyed Transport disembark fires BEFORE deadly demise so any
        # passengers that survive the disembark D6 are positioned for the
        # demise blast (and so they can also be caught by it).
        if self._is_transport(victim) and victim.passengers:
            self._destroyed_transport_disembark(victim)
        x = getattr(victim.profile, "deadly_demise", 0) or 0
        if x <= 0:
            return
        # Putrid Detonation (Virulent Vectorium, Death Guard stratagem): if
        # the dying unit belongs to a DG army that armed putrid_detonation
        # this round AND the victim is a DG VEHICLE or MONSTER, skip the
        # d6 gate (mortals auto-trigger). Cited as `Stratagem.Putrid Detonation`.
        victim_army = getattr(victim, "army_ref", None)
        victim_kw = set(victim.profile.unit_keywords or ())
        is_dg = (victim.profile.faction or "") == "Death Guard"
        is_vehicle_or_monster = "VEHICLE" in victim_kw or "MONSTER" in victim_kw
        putrid_armed = (
            victim_army is not None
            and getattr(victim_army, "putrid_detonation_armed", False)
            and is_dg
            and is_vehicle_or_monster
        )
        # Roll a d6 — 1-in-6 trigger, bypassed when Putrid Detonation is armed.
        if not putrid_armed and random.randint(1, 6) != 6:
            return
        # Scan every alive unit within 6" of the victim, on either side. The
        # victim itself is already at 0 HP and excluded by the alive filter,
        # so no special-casing is required.
        victim_pos = victim.position
        victims_hit: List[str] = []
        # Deadly Demise hits each UNIT within 6" once — "each unit within 6\"
        # suffers X mortal wounds" — NOT each model. Because SwegHammer models
        # one Unit per model, we group the nearby models by squad_id and deal X
        # a single time per distinct unit, spilling across that unit's models via
        # _apply_mortal_wounds (mortal wounds carry over per 10e). Before this
        # fix the per-model loop dealt X to every model of a unit, inflating the
        # blast by roughly the unit's model count. squad_id < 0 (lone models /
        # single-model units) are each their own unit. Cited as
        # `simulator.deadly_demise` + `simulator.mortal_wound_spillover`.
        seen_squads = set()
        for army in (self.a, self.b):
            for u in list(army.alive_units):
                if u is victim or not u.is_alive:
                    continue
                # Embarked passengers are off-board — they don't take demise
                # mortals from blasts that go off near their transport. Cited
                # as `simulator.embark`.
                if getattr(u, "embarked_in", None) is not None:
                    continue
                if _distance(u.position, victim_pos) > 6.0:
                    continue
                sid = getattr(u, "squad_id", -1)
                squad_key = sid if (sid is not None and sid >= 0) else ("lone", id(u))
                if squad_key in seen_squads:
                    continue   # this unit already took its X mortals
                seen_squads.add(squad_key)
                victims_hit.append(u.uid)
                # A demise that kills another unit does NOT cascade — the
                # canonical rule rolls the secondary victim's own demise at
                # its own death event in a subsequent activation, not here.
                for _m in self._apply_mortal_wounds(u, x):
                    self._emit(UnitKilled(unit_uid=_m.uid))
        self._emit(DeadlyDemiseExploded(
            unit_uid=victim.uid,
            mortals=int(x),
            victims=tuple(victims_hit),
        ))

    # ------------------------------------------------------------------
    # Transports (Embark / Disembark / Firing Deck / Destroyed Transport)
    # ------------------------------------------------------------------
    #
    # 10e core rules (Wahapedia):
    #   * Embark: a unit within 3" of a friendly TRANSPORT at the end of a
    #     Normal/Advance/Fall Back move may embark. Once embarked, the unit
    #     does not act normally — it's tracked as a passenger on the transport.
    #   * Disembark: at the start of any Movement phase a unit may disembark
    #     from a transport that hasn't moved this turn; the disembarked unit
    #     is placed wholly within 3" of the transport, then may move normally.
    #   * Firing Deck X: a TRANSPORT with Firing Deck X may select up to X
    #     embarked passenger models' weapons each Shooting phase and shoot
    #     with them as if they were the transport's own weapons (transport's BS).
    #   * Destroyed Transport: when a TRANSPORT is destroyed, before removing
    #     it, each embarked unit disembarks wholly within 3". For each model
    #     in the disembarking unit, roll 1D6; on a 1, that model is destroyed.
    #
    # SwegHammer simplifications (first pass):
    #   - Transport capacity is hardcoded to 12 INFANTRY models (Rhino-tier).
    #   - Pre-game embark only: at deploy time, if an army has a TRANSPORT
    #     with capacity for an INFANTRY unit, that infantry is embarked.
    #   - No mid-game voluntary embark (would need a Movement-phase hook).
    #   - Disembark fires on (a) destroyed transport, (b) at the start of the
    #     transport's Movement sub-phase if the AI judges the passenger needs
    #     to be off-board now (capture nearby objective, transport about to die).
    #   - Firing Deck: when a transport shoots, up to firing_deck passengers
    #     each fire ONE extra shot using the transport's hit_probability.
    #   - Emergency disembark (placement >3" but ≤6" with mortal wounds on
    #     1-3" path) is NOT modelled — first pass just skips placement if
    #     blocked.

    _TRANSPORT_CAPACITY = 12   # first-pass simplification — Rhino-tier

    @staticmethod
    def _is_transport(unit: "Unit") -> bool:
        """True iff this unit's profile carries the TRANSPORT keyword."""
        return "TRANSPORT" in (unit.profile.unit_keywords or ())

    def _embark_pregame_passengers(self) -> None:
        """Pre-game embark pass (10e core).

        For each army that owns at least one TRANSPORT, pick the highest-
        threat INFANTRY unit that fits (1 model after squad-flattening) and
        embark it on the first available transport. Repeats per transport so
        a list of Rhinos all get a passenger if possible. Passengers are
        removed from the active deployment line — their position becomes the
        transport's, and the simulator's activation loop skips embarked units
        via the `embarked_in` gate. Cited as `simulator.embark`.

        First-pass simplification: capacity is fixed at 12 INFANTRY models
        per transport (Rhino-tier). SwegHammer models units as a single
        Unit-per-model so we can fit up to 12 such Units inside one transport,
        but for the pre-game pass we only embark ONE infantry instance per
        transport (the most tactical-value passenger) to keep the pre-game
        deterministic and easy to reason about.
        """
        for army in (self.a, self.b):
            transports = [u for u in army.units if self._is_transport(u)]
            if not transports:
                continue
            # Pool of embark-eligible INFANTRY (not already a passenger, not
            # CHARACTER — we keep characters free to attach as Leaders).
            def _eligible(u):
                kw = u.profile.unit_keywords or ()
                if "INFANTRY" not in kw:
                    return False
                if "CHARACTER" in kw:
                    return False
                if self._is_transport(u):
                    return False
                if u.embarked_in is not None:
                    return False
                return True

            for transport in transports:
                if len(transport.passengers) >= self._TRANSPORT_CAPACITY:
                    continue
                candidates = [u for u in army.units if _eligible(u)]
                if not candidates:
                    break
                # Highest-Lanchester-score INFANTRY rides — biggest gun
                # benefits from the +6" pre-move the most.
                passenger = max(candidates, key=lambda u: u.profile.score)
                self._embark(passenger, transport)

    def _embark(self, passenger: "Unit", transport: "Unit") -> None:
        """Place `passenger` inside `transport` (10e core embark step).

        The passenger is co-located with the transport (position copied), its
        `embarked_in` back-pointer is set, and it's added to the transport's
        `passengers` list. The passenger remains in `army.units` (still alive,
        still has HP) but the activation loop skips it. Cited as
        `simulator.embark`.
        """
        passenger.position = transport.position
        passenger.embarked_in = transport
        transport.passengers.append(passenger)
        self._emit(TransportEmbarked(
            transport_uid=transport.uid,
            passenger_uid=passenger.uid,
        ))

    def _disembark(
        self, passenger: "Unit", transport: "Unit", forced: bool = False,
    ) -> None:
        """Place `passenger` wholly within 3" of `transport` (10e core).

        Looks for a placement point in a small spiral around the transport's
        last position. If no unblocked point is found, places the passenger
        on the transport's position (degraded fallback — better than nothing).
        Clears the embark back-pointer and removes the passenger from the
        transport's list. Cited as `simulator.disembark`.
        """
        # Try a handful of candidate offsets around the transport, each <= 3".
        # Order: cardinals first, then diagonals.
        cx, cy = transport.position
        candidates = [
            (cx + 2.5, cy), (cx - 2.5, cy), (cx, cy + 2.5), (cx, cy - 2.5),
            (cx + 2.0, cy + 2.0), (cx - 2.0, cy + 2.0),
            (cx + 2.0, cy - 2.0), (cx - 2.0, cy - 2.0),
            (cx + 1.0, cy), (cx, cy + 1.0),
        ]
        placed = None
        # CORE-RULES-AUDIT (2026-05-31): a disembarking unit must be set up NOT
        # within Engagement Range (1") of any enemy model. Previously only
        # impassable terrain was checked, so a unit could be placed adjacent to
        # an enemy and fight for free. See docs/CORE_RULES_AUDIT.md #9.
        _own = getattr(passenger, "army_ref", None)
        _enemy_army = (self.b if _own is self.a else self.a) if _own is not None else None
        _enemies = _enemy_army.alive_units if _enemy_army is not None else []

        def _clear_of_enemies(x, y):
            return all(
                (x - e.position[0]) ** 2 + (y - e.position[1]) ** 2 > 1.0
                for e in _enemies
                if getattr(e, "embarked_in", None) is None
            )

        for pt in candidates:
            x = max(0.0, min(self.map.width, pt[0]))
            y = max(0.0, min(self.map.height, pt[1]))
            if not self.map.is_blocked((x, y)) and _clear_of_enemies(x, y):
                placed = (x, y)
                break
        if placed is None:
            placed = transport.position
        passenger.position = placed
        passenger.embarked_in = None
        if passenger in transport.passengers:
            transport.passengers.remove(passenger)
        # 10e core Disembark: "The unit is then treated as having moved a
        # distance equal to its Move characteristic this turn" — surface
        # to the Heavy keyword check. The unit cannot make a Normal,
        # Advance or Fall Back move when its own activation arrives —
        # tracked in `_disembarked_this_round` and enforced in `_do_move`.
        # Voluntary disembark (forced=False) fires from the transport's
        # own Movement sub-phase, so the lockout applies for the rest of
        # this round. Forced disembark (transport destroyed) is also a
        # disembark for rule purposes and the same lockout applies.
        # Wahapedia core rules: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#TRANSPORTS
        self._did_move_this_round.add(passenger.uid)
        passenger.moved_this_round = True
        self._disembarked_this_round.add(passenger.uid)
        # DRK-SKYSPLINTER-DISEMBARK: Rain of Cruelty — "Each time a DRUKHARI
        # unit disembarks from a TRANSPORT, until the end of the turn its
        # ranged weapons gain [IGNORES COVER] and its melee weapons gain
        # [LANCE]." Set the transient per-unit flags here (cleared at the
        # next round-start by `_clear_transient_stratagem_flags`, matching
        # the "until the end of the turn" wording). Faction gate is on the
        # passenger (DRUKHARI); detachment gate is on the passenger's army
        # (Skysplinter Assault). Applies to both voluntary disembark
        # (Movement phase) and forced disembark (destroyed transport) —
        # the codex wording does not exclude the destroyed-transport
        # disembark from the rule. Cited as
        # `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark`.
        if passenger.profile.faction == "Drukhari":
            _own_army = getattr(passenger, "army_ref", None)
            if _own_army is not None:
                try:
                    _det = _own_army.resolve_detachment()
                except Exception:
                    _det = None
                if _det is not None and getattr(_det, "name", "") == "Skysplinter Assault":
                    self._set_transient_squad(passenger, "transient_lance_this_turn")
                    self._set_transient_squad(passenger, "transient_ignores_cover_this_turn")
        self._emit(TransportDisembarked(
            transport_uid=transport.uid,
            passenger_uid=passenger.uid,
            position=placed,
            forced=forced,
        ))

    def _destroyed_transport_disembark(self, transport: "Unit") -> None:
        """Force-disembark every passenger when a TRANSPORT is destroyed (10e).

        For each model in the disembarking unit, roll 1D6; on a 1 that model
        is destroyed. SwegHammer's Unit instance represents a whole squad
        whose `current_health` is the pooled wound count across surviving
        models, so we need one D6 per live model — not one per Unit. Models
        alive = `current_health / wounds_per_model`, where wounds_per_model
        = `profile.health / profile.min_models`. Each model destroyed reduces
        `current_health` by `wounds_per_model`. Cited as
        `simulator.destroyed_transport`.

        Prior behaviour (DRK-AI carry-forward bug, fixed by DRK-FINAL-2):
        rolled a single D6 per Unit and zeroed the whole squad on a 1. For a
        10-Kabalite squad that's ~16% chance of total wipe instead of the
        correct ~84% chance of losing 1-3 models in expectation. Under-
        modelled the cost of Venom/Raider destruction in proportion to
        squad size.

        We snapshot the passenger list because `_disembark` mutates it as it
        runs.
        """
        if not transport.passengers:
            return
        survivors = list(transport.passengers)
        for passenger in survivors:
            self._disembark(passenger, transport, forced=True)
            # Per-model D6: roll one die per surviving model and destroy
            # that model on a 1. SwegHammer abstracts a multi-model squad
            # as a single Unit with pooled wounds, so we compute model
            # count from `current_health / wounds_per_model` and subtract
            # `wounds_per_model` from `current_health` for each 1 rolled.
            min_models = max(1, getattr(passenger.profile, "min_models", 1) or 1)
            wounds_per_model = passenger.profile.health / min_models
            if wounds_per_model <= 0:
                continue
            models_alive = max(
                1, int(passenger.current_health / wounds_per_model + 1e-9)
            )
            kills = sum(
                1 for _ in range(models_alive) if random.randint(1, 6) == 1
            )
            if kills <= 0:
                continue
            damage = kills * wounds_per_model
            passenger.current_health = max(0.0, passenger.current_health - damage)
            if not passenger.is_alive:
                self._emit(UnitKilled(unit_uid=passenger.uid))

    def _maybe_disembark_before_move(
        self, transport: "Unit", army: Army, opponent: Army,
    ) -> None:
        """Voluntary disembark hook fired at the start of a TRANSPORT's
        Movement sub-phase (10e core).

        Heuristic: disembark when EITHER
          (a) the transport currently sits within 6" of an objective marker —
              the passenger should grab it while the transport repositions; OR
          (b) the transport is below 50% HP — likely to die soon, so eject
              before Destroyed Transport mortals fire.

        Otherwise we keep the passenger embarked so they continue to ride
        toward an objective. Cited as `simulator.disembark`.
        """
        if not transport.passengers:
            return
        # Already moved this round (e.g. arrival) — disembark skipped because
        # the rule requires the transport to NOT have moved yet.
        if transport.uid in self._did_move_this_round:
            return
        # (a) within 6" of an objective?
        near_obj = any(
            _distance(transport.position, (obj.x, obj.y)) <= 6.0
            for obj in self.map.objectives
        )
        # (b) below half HP?
        damaged = transport.current_health < transport.profile.health / 2.0
        if not near_obj and not damaged:
            return
        # Disembark the best passenger (the one most likely to claim an obj
        # or pour fire downrange). First-pass: just disembark all of them.
        for passenger in list(transport.passengers):
            self._disembark(passenger, transport, forced=False)

    def _apply_firing_deck(
        self, transport: "Unit", target: "Unit",
        attacker_army: Army, defender_army: Army,
    ) -> float:
        """Firing Deck X (10e core).

        When a TRANSPORT shoots, up to X embarked passenger models may fire
        their weapons as if they were the transport's. SwegHammer applies a
        simplified version: each of the first X passengers does a single
        Unit.attack against the target using the passenger's own profile,
        but inheriting the transport's hit_probability (per the codex's
        "shoot with them as if they were the transport's weapons" wording).

        Returns total damage dealt by the firing-deck passengers (0 if no
        firing deck or no passengers). Cited as `simulator.firing_deck`.

        First-pass simplification: passenger attacks use the passenger's own
        hit_probability rather than swapping in the transport's, because the
        Unit.attack stochastic loop reads hit_probability off the passenger's
        profile. The codex says "use the transport's BS"; in practice for
        Marine transports that's BS3+ which matches the passenger's anyway.
        Future task: thread a BS-override into Unit.attack.
        """
        x = getattr(transport.profile, "firing_deck", 0) or 0
        if x <= 0:
            return 0.0
        if not transport.passengers:
            return 0.0
        # Take up to X passengers; the first ones are highest-DPA by virtue
        # of the embark routine picking the best Lanchester-scorers.
        firing = transport.passengers[:x]
        total = 0.0
        distance = _distance(transport.position, target.position)
        target_kw = target.profile.unit_keywords or ()
        for passenger in firing:
            if not passenger.is_alive:
                continue
            # Out of range from the transport's position — skip silently.
            if distance > passenger.profile.range_inches:
                continue
            # 10e Ruins: the FIRING model's keywords decide whether LoS
            # passes through a Ruin wall, not the transport's. Each
            # passenger gets its own LoS check from the transport's
            # firing-deck position.
            has_los = self.map.has_line_of_sight(
                transport.position, target.position,
                attacker_keywords=passenger.profile.unit_keywords or (),
                target_keywords=target_kw,
            )
            total += passenger.attack(
                target, distance=distance, has_los=has_los,
            )
        return total

    @staticmethod
    def _award_cp(army: Army, opponent: Army) -> None:
        diff = opponent.unit_count - army.unit_count
        bonus = min(CP_BONUS_CAP, max(0, diff // CP_BONUS_DIVISOR))
        army.command_points += bonus

    # ------------------------------------------------------------------
    # Stratagem dispatch
    # ------------------------------------------------------------------

    def _fire_stratagem(self, army: Army, strat) -> bool:
        """Spend CP and emit a StratagemFired event. Returns True iff the
        stratagem actually fired (CP affordable + not already used when
        flagged once_per_battle).

        Callers are responsible for applying the stratagem's effect — this
        method ONLY handles cost-paying + book-keeping + event emission.
        """
        if army.command_points < strat.cp_cost:
            return False
        already = self._stratagems_fired_this_battle.get(army.name, set())
        if strat.once_per_battle and strat.name in already:
            return False
        army.command_points -= strat.cp_cost
        # Warlord-gated CP refund. Two independent mechanics, applied in
        # priority order so each pool drains separately:
        #   1. `first_stratagem_free_this_round` (Lord of Contagion's "Lord
        #      of the Death Guard" Warlord trait): the first stratagem this
        #      army fires this round is refunded its full cost and the flag
        #      flips off until the next Command phase re-arms it.
        #   2. `cp_refund_remaining` (Belisarius Cawl, Trazyn the Infinite):
        #      one-time-per-battle refund pool. Each spend that bypasses (1)
        #      pops one refund, gaining +1 CP and decrementing the pool.
        # Both refunds respect the CP_CAP=6 ceiling so a refunded spend at
        # cap still floors at cap — they refund the OLD CP value, not above.
        if army.first_stratagem_free_this_round:
            army.command_points = min(CP_CAP, army.command_points + strat.cp_cost)
            army.first_stratagem_free_this_round = False
        elif army.cp_refund_remaining > 0:
            army.command_points = min(CP_CAP, army.command_points + 1)
            army.cp_refund_remaining -= 1
        already.add(strat.name)
        self._stratagems_fired_this_battle[army.name] = already
        # Iter-4 A5: increment the per-Command-phase counter only when this
        # spend originated from `_apply_detachment_stratagems` (faction-neutral
        # detachment-stratagem dispatcher). Core Stratagems (Tank Shock,
        # Counter-Offensive, Command Re-Roll) fire on their own per-trigger
        # hooks at other points in the round and intentionally do NOT count
        # toward the cap. The dispatch flag is set + cleared in
        # `_apply_detachment_stratagems`'s try/finally.
        # Cited as `simulator.stratagem_per_command_phase_cap`.
        if getattr(self, "_dispatching_detachment_stratagems", False):
            army.stratagems_fired_this_command_phase += 1
        self._emit(StratagemFired(
            army_name=army.name,
            stratagem_name=strat.name,
            cp_cost=strat.cp_cost,
        ))
        return True

    def maybe_fire_command_reroll(self, attacker_unit, target_unit, roll_kind: str) -> bool:
        """Hook called by Unit.attack when a wound roll fails. Asks the
        strategy heuristic whether to spend 1 CP to re-roll. Returns True
        iff the stratagem fired.

        Universal Core Stratagem (Wahapedia core rules): re-roll a single
        Hit / Wound / Damage / Save / Advance / Charge / Battle-shock /
        control roll. The simulator currently exposes this only on failed
        wound rolls — that's the highest-value trigger and the others are
        covered by detachment re-roll passives.
        """
        army = attacker_unit.army_ref
        if army is None:
            return False
        ctx = {"target": target_unit, "roll_kind": roll_kind}
        if not should_fire_stratagem(army, COMMAND_RE_ROLL, ctx):
            return False
        return self._fire_stratagem(army, COMMAND_RE_ROLL)

    def _try_tank_shock(self, charger: "Unit", target: "Unit", charger_army: Army) -> None:
        """After a VEHICLE charge resolves, optionally spend 1 CP for Tank
        Shock — D3 mortal wounds to the charge target. Median D3 = 2
        deterministically (matches the simulator's other 'median D3' uses
        like Reanimation Protocols revival).
        """
        ctx = {"charger": charger, "succeeded": True}
        if not should_fire_stratagem(charger_army, TANK_SHOCK, ctx):
            return
        if not self._fire_stratagem(charger_army, TANK_SHOCK):
            return
        # Mortal wounds bypass armour/invuln; honour FNP via receive_damage and
        # spill across the target unit's models (10e core, _apply_mortal_wounds).
        # Each model the spill finishes triggers the kill-award fan-out. Cited as
        # simulator.mortal_wound_spillover.
        target_army = self.b if charger_army is self.a else self.a
        for _m in self._apply_mortal_wounds(target, 2):
            self._emit(UnitKilled(unit_uid=_m.uid))
            # Tank Shock that finishes a Votann model still triggers the
            # Judgement Token award — the killer's army is the charger's army.
            self._maybe_award_judgement_token(
                killer=charger, killer_army=charger_army,
                victim=_m, victim_army=target_army,
            )
            self._maybe_award_blood_tithe(
                killer=charger, killer_army=charger_army,
                victim=_m, victim_army=target_army,
            )
            self._maybe_award_miracle_die(
                victim=_m, victim_army=target_army,
            )
            self._maybe_apply_deadly_demise(_m)

    # CORE-RULES-AUDIT (2026-05-31): _do_heroic_intervention REMOVED. Heroic
    # Intervention is not a 10th-edition rule (it was a 9e mechanic, deleted at
    # the 10e launch). The Wahapedia 10e core rules contain no such rule; the
    # old docstring quoted 9e text. The method fired free for every defending
    # CHARACTER within 6" of a charger, a fabricated free move into engagement.
    # See docs/CORE_RULES_AUDIT.md #1.

    def _try_counter_offensive(
        self,
        loser_army: Army, loser_unit: "Unit",
        winner_army: Army, winner_unit: "Unit",
        target_killed: bool,
    ) -> None:
        """After `winner_unit` (from winner_army) lands a fight that killed
        a friendly model in `loser_unit`, the loser_army may spend 2 CP for
        Counter-Offensive — a friendly unit in engagement range fights
        immediately, out of sequence.

        Effect: pick the loser_army unit with the best melee profile that is
        within 1.5" of `winner_unit`, and fire its `_do_fight` against
        winner_unit right now (before the rest of the fight sequence).
        """
        # Find a friendly unit in engagement range of the winner.
        candidates = [
            u for u in loser_army.alive_units
            if u is not loser_unit
            and u.profile.melee_attacks > 0
            and _distance(u.position, winner_unit.position) <= 1.0
        ]
        in_engagement = bool(candidates)
        ctx = {
            "friendly_in_engagement": in_engagement,
            "enemy_killed_model": target_killed,
        }
        if not should_fire_stratagem(loser_army, COUNTER_OFFENSIVE, ctx):
            return
        if not self._fire_stratagem(loser_army, COUNTER_OFFENSIVE):
            return
        # Pick the highest melee-DPA candidate.
        def _melee_dpa(u):
            return (
                u.profile.melee_attacks * u.profile.melee_hit_probability
                * (u.profile.melee_damage_per_shot or 1.0)
            )
        candidates.sort(key=_melee_dpa, reverse=True)
        retaliator = candidates[0]
        # Out-of-sequence fight: hit the enemy unit that just struck us,
        # not whatever the retaliator's nearest happens to be.
        dmg = retaliator.attack(winner_unit, distance=1.0, mode="melee")
        alive_after = winner_unit.is_alive
        self._emit(UnitFought(
            attacker_uid=retaliator.uid,
            target_uid=winner_unit.uid,
            damage=dmg,
            target_hp_after=winner_unit.current_health,
            target_alive_after=alive_after,
        ))
        if not alive_after:
            self._emit(UnitKilled(unit_uid=winner_unit.uid))
            self._maybe_award_judgement_token(
                killer=retaliator, killer_army=loser_army,
                victim=winner_unit, victim_army=winner_army,
            )
            self._maybe_award_blood_tithe(
                killer=retaliator, killer_army=loser_army,
                victim=winner_unit, victim_army=winner_army,
            )
            self._maybe_award_miracle_die(
                victim=winner_unit, victim_army=winner_army,
            )
            self._maybe_apply_deadly_demise(winner_unit)
