"""
Per-unit strategy layer — pick what each unit *wants to do* this activation
rather than always marching at the nearest enemy.

Five intents:
  HOLD     — already on an objective and we'd lose VP by leaving
  CAPTURE  — move to the nearest uncontested or enemy-held objective
  STEAL    — move to an objective the enemy is currently scoring
  ENGAGE   — close on a target enemy (default for melee / shooty when in range)
  REPOSITION — move within range of a target without leaving an objective

`pick_move_intent(unit, friendly, enemy, map_) -> (target_pos, intent)` is the
public entry. The simulator's `_do_move` calls it and uses target_pos as the
move destination instead of the nearest-enemy heuristic.

Decision principles:
  1. If standing on a vulnerable objective (uncontested win or losing the count
     by one of our worth), HOLD.
  2. Otherwise score each objective by (a) is it currently scoring for us?
     low priority (b) uncontested? medium (c) enemy-controlled and within
     range? high — that's a steal.
  3. Role bias: SHOOTY / HEAVY hold position when an enemy is already in
     weapon range. MELEE always closes on the nearest enemy. HORDE / DUAL
     prefer objectives.
  4. If no objective is sensibly reachable, fall back to nearest enemy.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from .roles import classify


_HOLD_INTENT = "HOLD"
_CAPTURE_INTENT = "CAPTURE"
_STEAL_INTENT = "STEAL"
_ENGAGE_INTENT = "ENGAGE"
_REPOSITION_INTENT = "REPOSITION"

# Terrain-strength ranking used by the cover-bias helper. Higher wins when
# scoring candidate hold points around an objective. Imported lazily so this
# module stays import-cheap when map / TerrainType aren't needed.
_COVER_PRIORITY = {
    "open": 0,
    "light_cover": 1,
    "obscuring": 2,
    "heavy_cover": 3,
    "impassable": -1,   # never stand in impassable
}


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def _best_nearby_cover_point(
    map_,
    base_pos: Tuple[float, float],
    search_radius: float = 3.0,
    n_samples: int = 12,
) -> Tuple[float, float]:
    """Return a point within search_radius of base_pos sitting in the
    strongest cover terrain available (HEAVY > OBSCURING > LIGHT > OPEN).

    Cheap circular sampling: n_samples points evenly spaced on a circle of
    radius search_radius, plus base_pos itself. Ties resolve by proximity
    to base_pos. Skips IMPASSABLE candidates.
    """
    if map_ is None:
        return base_pos
    candidates = [(base_pos, _COVER_PRIORITY.get(map_.cover_at(base_pos).value, 0), 0.0)]
    for i in range(n_samples):
        angle = (2.0 * math.pi * i) / n_samples
        px = base_pos[0] + search_radius * math.cos(angle)
        py = base_pos[1] + search_radius * math.sin(angle)
        # Clamp inside the board
        px = max(0.0, min(map_.width, px))
        py = max(0.0, min(map_.height, py))
        p = (px, py)
        if map_.is_blocked(p):
            continue
        cover = map_.cover_at(p).value
        prio = _COVER_PRIORITY.get(cover, 0)
        candidates.append((p, prio, _dist(base_pos, p)))
    # Highest cover priority wins; tie-break by closest to base_pos.
    best = max(candidates, key=lambda c: (c[1], -c[2]))
    return best[0]


def _nearest_obscuring_centre(map_, pos: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    """Return the centre of the nearest OBSCURING terrain piece, or None.

    Used by the wounded-unit branch: a hurting softer-role unit prefers to
    break LoS by huddling against an obscuring ruin centre.
    """
    if map_ is None:
        return None
    best = None
    best_d = float("inf")
    for t in getattr(map_, "terrain", ()) or ():
        if t.type.value != "obscuring":
            continue
        cx = t.x + t.width / 2.0
        cy = t.y + t.height / 2.0
        d = _dist(pos, (cx, cy))
        if d < best_d:
            best_d = d
            best = (cx, cy)
    return best


def _oc_on_objective(units, obj, exclude_uid: str = "") -> int:
    """Sum the OC values of `units` within obj.control_radius (excluding one)."""
    r2 = obj.control_radius * obj.control_radius
    total = 0
    for u in units:
        if u.uid == exclude_uid:
            continue
        dx = u.position[0] - obj.x
        dy = u.position[1] - obj.y
        if dx * dx + dy * dy <= r2:
            total += getattr(u.profile, "oc", 1) or 0
    return total


def pick_charge_target(attacker, enemy):
    """
    Pick the best enemy to charge from those within 12" range.

    Real 10e charges go into targets that are weak in melee (gunlines,
    battlesuits, support characters) so the attacker hopes to win the
    resulting fight on opponent's turn. The old nearest-enemy heuristic
    didn't account for this and meant melee attackers wasted activations
    on resilient brick units.

    Scoring per candidate:

        kill_potential = our melee DPA against them
                       / (their toughness + remaining HP)

        threat_against_us = their melee DPA back at us
                          / (our toughness + our remaining HP)

        ranged_value     = their ranged DPA we'd shut down by tying them up
                         × (their_range_inches / 24)

        charge_difficulty = 1 / charge_success_probability(2D6 >= distance)

    score = (kill_potential + 0.5 * ranged_value) / (1 + threat_against_us)
            / charge_difficulty

    Returns (target_unit, distance) or (None, None) if no legal charge.
    """
    alive_enemies = [e for e in enemy.alive_units]
    if not alive_enemies:
        return None, None

    p = attacker.profile
    # Attacker's per-activation melee output.
    a_melee_dpa = (p.melee_attacks * p.melee_hit_probability
                   * (p.melee_damage_per_shot or 1.0))
    a_dur = max(1.0, p.toughness + attacker.current_health)

    candidates = []
    for e in alive_enemies:
        d = _dist(attacker.position, e.position)
        if d > 12.0 or d <= 1.0:
            continue   # out of charge range / already engaged
        tp = e.profile

        kill_potential = a_melee_dpa / max(1.0, tp.toughness + e.current_health)

        threat_against = (
            tp.melee_attacks * tp.melee_hit_probability
            * (tp.melee_damage_per_shot or 1.0)
        ) / a_dur

        ranged_value = (
            tp.attacks * tp.hit_probability * (tp.weapon_damage_per_shot or 0.0)
        ) * (tp.range_inches / 24.0)

        # 2D6 >= d success probabilities (approx): 4=83%, 6=72%, 8=42%,
        # 10=17%, 12=2.7%. Use a coarse table to keep the math cheap.
        if d <= 5:
            charge_p = 0.92
        elif d <= 6:
            charge_p = 0.83
        elif d <= 7:
            charge_p = 0.72
        elif d <= 8:
            charge_p = 0.58
        elif d <= 9:
            charge_p = 0.42
        elif d <= 10:
            charge_p = 0.28
        elif d <= 11:
            charge_p = 0.17
        else:
            charge_p = 0.08

        score = ((kill_potential + 0.5 * ranged_value)
                 / (1.0 + threat_against)) * charge_p
        candidates.append((score, d, e))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, dist, target = candidates[0]
    return target, dist


def pick_move_intent(unit, friendly, enemy, map_) -> Tuple[Tuple[float, float], str]:
    """
    Decide where `unit` should move this activation, and label the reason.

    Returns (target_position, intent_string). The simulator's _do_move
    treats target_position as the goal point — if it's the same as the
    unit's current position, no move happens (HOLD).
    """
    role = classify(unit.profile)
    own_oc = getattr(unit.profile, "oc", 1) or 0

    # ----- 1. Are we currently on an objective whose loss is at stake? -----
    for obj in map_.objectives:
        if _dist(unit.position, (obj.x, obj.y)) > obj.control_radius:
            continue
        # We're within control radius. Count OC without us, both sides.
        our_oc_no_self = _oc_on_objective(friendly.alive_units, obj, exclude_uid=unit.uid)
        their_oc = _oc_on_objective(enemy.alive_units, obj)
        # If leaving would flip control (or contest from win → tie), hold.
        # Snap to a cover-rich point near where we already stand so the
        # HOLD has a defensive benefit (HEAVY cover > OBSCURING > LIGHT).
        if own_oc > 0 and our_oc_no_self <= their_oc < our_oc_no_self + own_oc:
            hold_pos = _best_nearby_cover_point(map_, unit.position, search_radius=3.0)
            return hold_pos, _HOLD_INTENT

    # ----- 2. Score every objective; pick the most worth visiting -----
    objs = []
    for obj in map_.objectives:
        a_oc = _oc_on_objective(friendly.alive_units, obj)
        b_oc = _oc_on_objective(enemy.alive_units, obj)
        d = _dist(unit.position, (obj.x, obj.y))
        if a_oc > b_oc:
            value = 1.0           # already scoring — low priority for more bodies
            intent = _CAPTURE_INTENT
        elif b_oc > a_oc:
            value = 3.5           # steal opportunity — best
            intent = _STEAL_INTENT
        else:
            value = 2.5           # uncontested or tied — claim it
            intent = _CAPTURE_INTENT
        # Distance-weighted: closer objectives win unless their value dominates
        score = value / (1.0 + d / 12.0)
        objs.append((score, intent, obj, d))

    best = max(objs, key=lambda t: t[0]) if objs else None

    # ----- 3. Role bias: shooty / heavy stay put when in firing range -----
    nearest_enemy = None
    nearest_enemy_dist = float("inf")
    for e in enemy.alive_units:
        d = _dist(unit.position, e.position)
        if d < nearest_enemy_dist:
            nearest_enemy_dist = d
            nearest_enemy = e

    if role in ("SHOOTY", "HEAVY") and nearest_enemy is not None:
        rng = unit.profile.range_inches or 24
        if nearest_enemy_dist <= rng:
            # In range — don't drift around. But snap to nearby cover when
            # available so we get the defensive uplift.
            repo_pos = _best_nearby_cover_point(map_, unit.position, search_radius=3.0)
            return repo_pos, _REPOSITION_INTENT

    # MELEE always closes on the nearest enemy (range = 1, can never shoot far)
    if role == "MELEE" and nearest_enemy is not None:
        return nearest_enemy.position, _ENGAGE_INTENT

    # ----- 4. Pick objective target if one scored well; else engage enemy -----
    if best is not None and best[0] > 0.2:
        _, intent, obj, _ = best
        # Wounded softer-role units bias toward OBSCURING terrain to break
        # line of sight rather than marching openly onto the marker.
        wounded_pos = _wounded_seek_obscuring(unit, role, (obj.x, obj.y), map_)
        if wounded_pos is not None:
            return wounded_pos, intent
        # Snap the destination to the strongest cover point within ~3" of
        # the objective marker. The control radius is 3" so any such point
        # still scores the objective.
        snap = _best_nearby_cover_point(map_, (obj.x, obj.y), search_radius=3.0)
        return snap, intent

    if nearest_enemy is not None:
        wounded_pos = _wounded_seek_obscuring(unit, role, nearest_enemy.position, map_)
        if wounded_pos is not None:
            return wounded_pos, _ENGAGE_INTENT
        return nearest_enemy.position, _ENGAGE_INTENT

    # No enemies left — sit still
    return unit.position, _HOLD_INTENT


def _wounded_seek_obscuring(unit, role: str, fallback_pos: Tuple[float, float], map_):
    """If `unit` is below half HP and is a softer role (HORDE / SUPPORT, or
    MELEE not yet in engagement), return the nearest OBSCURING-terrain
    centre as the new target — breaks line of sight while withdrawing.

    Returns None when the unit doesn't qualify or no OBSCURING terrain
    exists, in which case the caller keeps the original destination.
    """
    try:
        half = unit.profile.health / 2.0
    except Exception:
        return None
    if unit.current_health >= half:
        return None
    if role not in ("HORDE", "SUPPORT", "MELEE"):
        return None
    # MELEE units already in engagement (1" of fallback target) keep pushing.
    if role == "MELEE" and _dist(unit.position, fallback_pos) <= 1.5:
        return None
    nearest = _nearest_obscuring_centre(map_, unit.position)
    return nearest


__all__ = ["pick_move_intent"]
