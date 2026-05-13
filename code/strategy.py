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

from typing import Tuple

from .roles import classify


_HOLD_INTENT = "HOLD"
_CAPTURE_INTENT = "CAPTURE"
_STEAL_INTENT = "STEAL"
_ENGAGE_INTENT = "ENGAGE"
_REPOSITION_INTENT = "REPOSITION"


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


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
        if own_oc > 0 and our_oc_no_self <= their_oc < our_oc_no_self + own_oc:
            return unit.position, _HOLD_INTENT

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
            # In range — don't drift around. But if we're ALSO on an objective,
            # we should hold (caught earlier in case 1 anyway).
            return unit.position, _REPOSITION_INTENT

    # MELEE always closes on the nearest enemy (range = 1, can never shoot far)
    if role == "MELEE" and nearest_enemy is not None:
        return nearest_enemy.position, _ENGAGE_INTENT

    # ----- 4. Pick objective target if one scored well; else engage enemy -----
    if best is not None and best[0] > 0.2:
        _, intent, obj, _ = best
        return (obj.x, obj.y), intent

    if nearest_enemy is not None:
        return nearest_enemy.position, _ENGAGE_INTENT

    # No enemies left — sit still
    return unit.position, _HOLD_INTENT


__all__ = ["pick_move_intent"]
