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


def _durability(profile, current_health: float, attacker_ap: int) -> float:
    """Effective durability against an attacker with the given AP.

    Combines remaining HP, toughness, and the fraction of unsaved wounds
    after armour / invuln (whichever is better) and AP modifier. A
    Custodian Guard (T6, 3W, 2+/4++) is much tougher vs an AP0 melee weapon
    than HP alone suggests; a Fire Warrior (T3, 1W, 4+) is much frailer
    against AP-1 than a flat (T+HP) hides. Without folding the save in,
    high-Sv elite units register as "squishy melee targets" because their
    HP is low — exactly the T'au Battlesuit / Custodian over-rating we saw
    after the #96 charge AI landed.
    """
    from .units import save_probability

    # Probability a single unsaved wound gets through (1 - best-save).
    save_pass = save_probability(profile.save, attacker_ap)
    invuln_pass = save_probability(profile.invuln_save) if profile.invuln_save <= 6 else 0.0
    best_pass = max(save_pass, invuln_pass)
    unsaved_fraction = max(0.05, 1.0 - best_pass)   # floor so divide stays sane
    # Toughness adds the wound-roll difficulty (already in attacker's DPA via
    # hit*wound math). Keep T as a multiplier rather than additive so a T8
    # Knight reads multiplicatively harder than a T4 Marine of equal HP.
    return profile.toughness * max(1.0, current_health) / unsaved_fraction


# Factions whose own melee units should NOT receive the gunline-charge bonus
# when scoring enemy targets. The bonus is a one-sided incentive: opponents
# should attack T'au-style gunlines because letting them shoot is worse than
# eating a counter-charge. But applied symmetrically, T'au's own melee units
# (Vespid Stingwings, Stealth Suits) game the bonus too — net helping T'au
# (the earlier #107 attempt actually moved T'au's calibration from +10.3 to
# +12.9 by being two-sided). Keep this list tight; expand only if a faction
# has the same shape (low-melee gunline army with token melee escorts).
_GUNLINE_ATTACKER_FACTIONS = frozenset({"T'au Empire"})


def _is_gunline_target(profile) -> bool:
    """True when `profile` is a 'gunline' — ranged DPA meaningfully exceeds
    melee DPA. Captures T'au Battlesuits / Pathfinders / Broadsides, Marine
    Devastators / Hellblasters, Sororitas Retributors, etc.

    A target's *role* is also gunline-ish if its melee profile is so thin
    that opponents are better off charging it than letting it shoot.
    """
    ranged_dpa = (
        profile.attacks * profile.hit_probability
        * (profile.weapon_damage_per_shot or 0.0)
    )
    melee_dpa = (
        profile.melee_attacks * profile.melee_hit_probability
        * (profile.melee_damage_per_shot or 0.0)
    )
    if ranged_dpa <= 0.5:
        return False
    # Ratio >= 2x of ranged over melee qualifies. The 0.5 floor on melee_dpa
    # protects against divide-by-zero and treats pure gunlines (no melee
    # profile at all) as fully ranged-dependent.
    return ranged_dpa >= 2.0 * max(0.5, melee_dpa)


def _gunline_charge_bonus(attacker_profile, defender_profile) -> float:
    """One-sided gunline-charge incentive: returns a multiplier in [1.0, 2.5]
    applied to the score of `defender` AS A MELEE TARGET.

    Only fires when (a) the attacker is NOT one of `_GUNLINE_ATTACKER_FACTIONS`
    AND (b) the defender is a gunline-style profile. This makes opponents
    prioritise charging T'au battlesuits / Marine Devastators / etc., while
    preventing T'au's own melee escorts from gaming the bonus when picking
    enemy heavies.

    Scale: ratio 2x ranged-over-melee -> 1.5x score; 4x -> 2.5x; cap 2.5x.
    """
    if attacker_profile.faction in _GUNLINE_ATTACKER_FACTIONS:
        return 1.0
    if not _is_gunline_target(defender_profile):
        return 1.0
    ranged_dpa = (
        defender_profile.attacks * defender_profile.hit_probability
        * (defender_profile.weapon_damage_per_shot or 0.0)
    )
    melee_dpa = (
        defender_profile.melee_attacks * defender_profile.melee_hit_probability
        * (defender_profile.melee_damage_per_shot or 0.0)
    )
    ratio = ranged_dpa / max(0.5, melee_dpa)
    # ratio 2x -> 1.5x; 4x -> 2.5x; cap at 2.5x.
    return min(2.5, 0.5 + ratio * 0.5)


def _melee_target_score(attacker, defender) -> float:
    """How attractive `defender` is as a melee target for `attacker`.

    Same shape as pick_charge_target's scoring but distance-independent —
    used by the MOVE planner to pick which enemy to close on, before we
    know whether a charge will be in range. Real tournament play: melee
    bricks pick fragile gunline targets (T'au Fire Warriors, Devastators,
    snipers) over near-but-tough enemies with strong saves.
    """
    p = attacker.profile
    tp = defender.profile

    a_melee_dpa = (p.melee_attacks * p.melee_hit_probability
                   * (p.melee_damage_per_shot or 1.0))
    kill_potential = a_melee_dpa / _durability(tp, defender.current_health, p.melee_ap)

    # Threat back: their melee output divided by OUR effective durability
    # against THEIR AP. Same machinery — an opponent with AP-3 reads as
    # more dangerous to a Marine than the raw DPA suggests.
    threat_back = (
        tp.melee_attacks * tp.melee_hit_probability
        * (tp.melee_damage_per_shot or 1.0)
    ) / _durability(p, attacker.current_health, tp.melee_ap)

    ranged_value = (
        tp.attacks * tp.hit_probability * (tp.weapon_damage_per_shot or 0.0)
    ) * (tp.range_inches / 24.0)

    base = (kill_potential + 0.5 * ranged_value) / (1.0 + threat_back)
    # One-sided gunline incentive: opposing armies prioritise tying up
    # T'au-style gunlines. T'au's own melee units don't game the bonus —
    # see `_gunline_charge_bonus` for the asymmetry.
    return base * _gunline_charge_bonus(p, tp)


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

    candidates = []
    for e in alive_enemies:
        d = _dist(attacker.position, e.position)
        if d > 12.0 or d <= 1.0:
            continue   # out of charge range / already engaged
        tp = e.profile

        kill_potential = a_melee_dpa / _durability(tp, e.current_health, p.melee_ap)

        threat_against = (
            tp.melee_attacks * tp.melee_hit_probability
            * (tp.melee_damage_per_shot or 1.0)
        ) / _durability(p, attacker.current_health, tp.melee_ap)

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

        # One-sided gunline incentive — same multiplier used in
        # `_melee_target_score`. Only opposing-army attackers get the
        # bonus; T'au's own melee units don't game it.
        gunline_bonus = _gunline_charge_bonus(p, tp)
        score = ((kill_potential + 0.5 * ranged_value)
                 / (1.0 + threat_against)) * charge_p * gunline_bonus
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

    # MELEE closes on the BEST melee target (the gunline / battlesuit /
    # support character whose squishy melee profile we can crack open),
    # not just the nearest enemy. Without this bias, melee bricks waste
    # activations on hard-to-kill bricks and never engage the priorities
    # that under-rate our sim's T'au / Astartes / Votann shooty factions.
    if role == "MELEE" and enemy.alive_units:
        scored = sorted(
            enemy.alive_units,
            key=lambda e: _melee_target_score(unit, e),
            reverse=True,
        )
        return scored[0].position, _ENGAGE_INTENT

    # DUAL: if a high-value charge target is within potential charge range
    # next round (move + 12" threat), close on it; otherwise fall through
    # to objective logic. This is what real Intercessor / Boyz / similar
    # do — bias toward enemies with weak melee, not just the closest body.
    if role == "DUAL" and enemy.alive_units:
        move_dist = unit.profile.move or 6.0
        threat_range = move_dist + 12.0
        viable = [
            e for e in enemy.alive_units
            if _dist(unit.position, e.position) <= threat_range
        ]
        if viable:
            best_melee = max(viable, key=lambda e: _melee_target_score(unit, e))
            # Only engage if the target's score beats a neutral baseline —
            # otherwise the objective-grabbing fallback handles it better.
            if _melee_target_score(unit, best_melee) > 0.1:
                return best_melee.position, _ENGAGE_INTENT

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


__all__ = ["pick_move_intent", "should_fire_stratagem", "should_declare_waaagh"]


# ---------------------------------------------------------------------------
# Orks WAAAGH! AI trigger (once-per-battle window)
# ---------------------------------------------------------------------------

# The simulator calls this at the start of each Ork player's Command phase
# (Round 1 onwards). It returns True iff the Ork player should declare WAAAGH!
# THIS round.
#
# Heuristic priorities (ranked):
#   1. Already declared? Never again — once per battle.
#   2. Round 4 fallback: force-fire so the buff isn't wasted entirely.
#   3. Emergency: Orks below 70% starting points and at least Round 2 — fire
#      now to hit back before the army crumbles further.
#   4. Default: Round 3. Middle of the game, melee waves should be in range
#      and a turn of +1 to wound melee turns the brawl.
def should_declare_waaagh(army, round_num: int) -> bool:
    """Decide whether the Ork player should declare WAAAGH! this round.

    Args:
        army: the Ork Army (must have `waaagh_round_unlocked` attribute).
        round_num: the current battle round (1..MAX_ROUNDS).

    Returns:
        True iff the army should declare WAAAGH! NOW. Caller is responsible
        for setting `army.waaagh_round_unlocked = round_num` and emitting
        the WaaaghDeclared event.
    """
    if getattr(army, "waaagh_round_unlocked", None) is not None:
        return False   # already used this battle

    starting = float(getattr(army, "starting_points", 0.0) or 0.0)
    current = float(sum(u.profile.points_cost for u in army.alive_units))

    # Round 4: force-fire fallback — don't leave the buff on the table.
    if round_num >= 4:
        return True

    # Emergency trigger: heavy losses, fire early to retaliate.
    if round_num >= 2 and starting > 0 and current < 0.70 * starting:
        return True

    # Default: Round 3 declaration — peak melee engagement window.
    if round_num == 3:
        return True

    return False


# ---------------------------------------------------------------------------
# Stratagem firing heuristic
# ---------------------------------------------------------------------------

# Approximate point-value swing the AI requires before it spends CP on a
# stratagem. 8 pts is roughly half a Marine — fire the universals when the
# expected delta clears that bar AND we can afford it.
_MIN_EXPECTED_SWING_PTS: float = 8.0


def _is_heavy_target(target) -> bool:
    """A 'heavy' target the AI prioritises Command Re-Roll on.

    Uses the role classifier so HEAVY / SHOOTY classes (Knights, Predators,
    Hammerheads, Devastators) qualify and frail HORDE / SUPPORT models do
    not. Falls back to a points-cost threshold so the heuristic still works
    on profiles without a clear classification.
    """
    if target is None:
        return False
    try:
        role = classify(target.profile)
    except Exception:
        role = ""
    if role in ("HEAVY", "SHOOTY", "DUAL"):
        return True
    # Anything 60+ points is treated as a worthwhile re-roll candidate
    # (Custodian Guard, Wraithlord, etc.) even if the role classifier
    # disagrees.
    try:
        return float(target.profile.points_cost) >= 60.0
    except Exception:
        return False


def should_fire_stratagem(army, strat, ctx: Optional[dict] = None) -> bool:
    """Greedy heuristic: return True iff the army should spend CP on `strat`
    right now given the current battle context.

    `ctx` carries trigger-specific hints (e.g. the target of a failed wound
    roll, the friendly unit that's about to be charge-killed). The keys
    consulted per stratagem are documented inline below.

    Universal rule: never fire if `army.command_points < strat.cp_cost`.
    Specific stratagems also gate on a minimum expected swing of
    ~`_MIN_EXPECTED_SWING_PTS` points of value to avoid leaking CP into
    low-impact triggers.
    """
    if ctx is None:
        ctx = {}
    if army.command_points < strat.cp_cost:
        return False

    name = strat.name

    if name == "Command Re-Roll":
        # ctx expects {"target": Unit, "roll_kind": str}. Fire on a missed
        # wound vs HEAVY/SHOOTY/DUAL target (high value); skip small fish.
        target = ctx.get("target")
        if not _is_heavy_target(target):
            return False
        # Expected swing = per_shot_damage * (1 - rerolled_fail_prob).
        # Approximate with: the attack would have done per_shot_damage *
        # ~0.5 in expectation if rerolled, so fire when the per-shot damage
        # alone is meaningful. _MIN_EXPECTED_SWING_PTS is in points, but
        # one Knight wound (~12-15 raw HP) easily clears 8 pts of swing,
        # while a Cultist wound (~5 pts) doesn't.
        try:
            target_cost = float(target.profile.points_cost)
        except Exception:
            target_cost = 0.0
        # 1/health-fraction × points: a wound on a high-HP Knight is worth
        # less than a kill on a Devastator, so weight by remaining HP too.
        try:
            hp_frac = max(1.0, target.current_health) / max(1.0, target.profile.health)
            value = target_cost * hp_frac * 0.15   # ~15% of full value per wound
        except Exception:
            value = target_cost * 0.15
        return value >= _MIN_EXPECTED_SWING_PTS

    if name == "Counter-Offensive":
        # ctx expects {"friendly_in_engagement": bool, "enemy_killed_model": bool}.
        # Fire when both are true: we just lost a model to the enemy's fight
        # and we still have a unit in melee range to retaliate.
        if not ctx.get("friendly_in_engagement"):
            return False
        if not ctx.get("enemy_killed_model"):
            return False
        return True

    if name == "Tank Shock":
        # ctx expects {"charger": Unit, "succeeded": bool}. Fire when a
        # VEHICLE unit just succeeded its charge — D3 mortal wounds is
        # ~2 damage in expectation, comfortably worth 1 CP.
        charger = ctx.get("charger")
        if charger is None or not ctx.get("succeeded"):
            return False
        kw = (charger.profile.unit_keywords or ()) if hasattr(charger, "profile") else ()
        return "VEHICLE" in kw

    if name == "Heroic Intervention":
        # ctx expects {"character": Unit, "charge_target": Unit, "distance": float}.
        # Fire when a friendly CHARACTER is within 6" of an enemy's charge
        # target — pulls the character into the fight to soak / counter.
        character = ctx.get("character")
        if character is None:
            return False
        kw = (character.profile.unit_keywords or ()) if hasattr(character, "profile") else ()
        if "CHARACTER" not in kw:
            return False
        dist = ctx.get("distance", 999.0)
        return dist <= 6.0

    # ----- Cult of Magic (Thousand Sons) ---------------------------------

    if name == "Doombolt":
        # ctx expects {"target": Unit, "has_psyker": bool}. Doombolt is the
        # cheapest CP spend in the codex — 1 CP for ~2 mortal wounds (median
        # D3). Always fire when a target exists and we have a psyker.
        # Only gate on CP affordability (already checked above).
        target = ctx.get("target")
        if target is None:
            return False
        if not ctx.get("has_psyker", False):
            return False
        return True

    if name == "Twist of Fate":
        # ctx expects {"attacker": Unit, "target": Unit}. +1 to wound on a
        # whole round of shooting is worth it when the target is a HEAVY/
        # SHOOTY brick the +1 actually closes a 5+ to a 4+ against. Skip
        # on tiny chip targets (squad of Cultists) where the +1 doesn't
        # change the rolling bracket.
        target = ctx.get("target")
        attacker = ctx.get("attacker")
        if target is None or attacker is None:
            return False
        if not _is_heavy_target(target):
            return False
        # Cheap enough at 1 CP — fire whenever we have a real attacker and
        # a worthwhile target.
        return True

    if name == "Glamour of Tzeentch":
        # ctx expects {"target": Unit}. 2 CP for a transient 4++ on a unit
        # — expensive, only fire when the target is meaningfully damaged AND
        # high-value (otherwise we're insuring something not worth saving).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
        except Exception:
            hp_frac = 0.0
        try:
            cost = float(target.profile.points_cost)
        except Exception:
            cost = 0.0
        # ~8 pts of vulnerability swing required (matches _MIN_EXPECTED_SWING_PTS).
        return hp_frac > 0.0 and cost * hp_frac >= _MIN_EXPECTED_SWING_PTS

    # ----- Plague Company (Death Guard) ----------------------------------

    if name == "Disgustingly Resilient":
        # ctx expects {"target": Unit}. Cheap defensive — fire when a
        # meaningful DG unit has taken substantial damage (>20% HP loss).
        # Single-wound INFANTRY profiles don't benefit (damage 1 → max(1, 0)
        # is still 1 dmg), so we also require multi-wound or vehicle HP so
        # the floor-1 doesn't waste the CP.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            max_hp = float(target.profile.health)
        except Exception:
            return False
        # Multi-wound model and meaningful damage taken.
        return hp_frac > 0.2 and max_hp >= 4.0

    if name == "Plague Weapons":
        # ctx expects {"attacker": Unit, "target": Unit}. +1 to wound for a
        # whole round of shooting — fire when attacker has real DPA AND
        # the target is heavy. Tightened so we preserve CP for Command
        # Re-Roll: a single +1 wound on a 1-DPA attacker isn't worth 1 CP
        # compared to a re-rolled killing blow.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 2.0 and _is_heavy_target(target)

    if name == "Outbreak of Pestilence":
        # ctx expects {"attacker": Unit, "target": Unit}. +1 to wound in
        # melee — fire when the attacker has a real melee profile AND the
        # target is heavy. Same CP-conservation reasoning as Plague Weapons.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            melee_dpa = p.melee_attacks * p.melee_hit_probability * (p.melee_damage_per_shot or 0.0)
        except Exception:
            melee_dpa = 0.0
        return melee_dpa >= 3.0 and _is_heavy_target(target)

    # ----- Battle Host (Aeldari) -----------------------------------------

    if name == "Lightning-Fast Reactions":
        # ctx expects {"target": Unit}. Defensive — fire only on a
        # SUBSTANTIALLY-wounded high-value Aeldari unit. Aeldari already
        # overperforms by +7.5 vs the meta, so the threshold is tight:
        # require HP loss > 40% AND points cost >= 100 (the canonical
        # Wraithlord / Phoenix Lord / vehicle bracket).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.4 and cost >= 100.0

    if name == "Fire and Fade":
        # ctx expects {"attacker": Unit, "target": Unit}. Re-roll 1s to hit
        # — only fire when the attacker has serious ranged DPA AND the
        # target is a HEAVY/SHOOTY/DUAL brick AND the target has already
        # been softened (otherwise we're shoving CP into a long roll-in
        # that doesn't close the round). Aeldari already overperforms; a
        # re-roll on Guardians' lasguns isn't worth 1 CP/round.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            atk_cost = float(p.points_cost)
            tgt_hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
        except Exception:
            return False
        # Real shooter only — 150+ point Wraith / vehicle units, not basic
        # Guardian squads — and target must be a heavy threat ALREADY
        # softened by at least one full HP wound (the "killing-blow shot"
        # is when this rule earns its CP in real games too).
        return (
            ranged_dpa >= 2.0
            and atk_cost >= 150.0
            and _is_heavy_target(target)
            and tgt_hp_frac > 0.15
        )

    if name == "Matchless Agility":
        # ctx expects {"attacker": Unit}. Advance + still shoot — only fire
        # for non-ASURYANI Aeldari (ASURYANI already get free [ASSAULT] via
        # battle_focus_tokens, so this CP spend would be wasted). Wraith /
        # Harlequin / Drukhari units don't have ASURYANI and benefit
        # genuinely. Require a substantial unit cost so we don't pay 1 CP
        # to inch a Guardian squad forward one round.
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        kw = (attacker.profile.unit_keywords or ()) if hasattr(attacker, "profile") else ()
        if "ASURYANI" in kw:
            return False   # army-rule covers it
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            cost = 0.0
        # 150+ pts only — Voidweavers, Wraithlords, etc. — not Storm
        # Guardian squads. Higher than Lightning-Fast Reactions because
        # the buff is offensive (mobility into shoot) and we're already
        # over-rated.
        return cost >= 150.0

    # Unknown stratagem — let the simulator decide via its own dispatch.
    return False

