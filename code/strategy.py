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

from .detachments import effective_move
from .roles import classify


_HOLD_INTENT = "HOLD"
_CAPTURE_INTENT = "CAPTURE"
_STEAL_INTENT = "STEAL"
_ENGAGE_INTENT = "ENGAGE"
_REPOSITION_INTENT = "REPOSITION"


# ---------------------------------------------------------------------------
# S1 — Faction strategic posture (AI tuning, not a 10e rule)
# ---------------------------------------------------------------------------
# IRL top-faction play biases very differently per army: T'au alpha-strike,
# Aeldari shimmy-step, Necrons grind objectives, Custodes elite-control, etc.
# Our previous AI applied the same heuristic to every faction. This dict
# tags each faction with a strategic posture; per-posture modifier helpers
# below adjust the existing intent scoring without replacing the core logic.
#
# This is AI behaviour-shaping, NOT a 10e rule — no rule_citations entry is
# required (see docs/STRATEGY_ANALYSIS.md S1 for the design rationale).
FACTION_POSTURE: dict = {
    # Aeldari — shimmy-step (Battle Focus, never sit still).
    "Aeldari":              "shimmy",
    "Aeldari (Craftworlds)": "shimmy",
    # Drukhari — fast strike, mobile alpha, low-toughness raiders.
    "Drukhari":             "fast_strike",
    "Ynnari":               "fast_strike",
    # T'au — Mont'ka alpha-strike gunline.
    "T'au Empire":          "alpha_strike",
    # Custodes — elite control, hold the middle.
    "Adeptus Custodes":     "objective_hold",
    # Necrons — Awakened Dynasty objective grind.
    "Necrons":              "objective_hold",
    # Death Guard — spread Plague Marines to every objective.
    "Death Guard":          "attrition",
    # Thousand Sons — psychic attrition + Rubric durability.
    "Thousand Sons":        "psychic_attrition",
    # Orks / Tyranids — horde alpha.
    "Orks":                 "horde_push",
    "Tyranids":             "horde_push",
    # Genestealer Cults — Cult Ambush turn-1 close-in.
    "Genestealer Cults":    "ambush_alpha",
    # Marines — baseline (no posture-specific bias).
    "Adeptus Astartes":     "balanced",
    "Ultramarines":         "balanced",
    "Blood Angels":         "balanced",
    "Dark Angels":          "balanced",
    "Space Wolves":         "balanced",
    "Black Templars":       "balanced",
    "Imperial Fists":       "balanced",
    "Iron Hands":           "balanced",
    "Raven Guard":          "balanced",
    "Salamanders":          "balanced",
    "White Scars":          "balanced",
    "Deathwatch":           "balanced",
    "Grey Knights":         "balanced",
}


def _posture_for(faction: str) -> str:
    """Return the strategic posture for `faction`, defaulting to 'balanced'.

    Unknown / approximate factions fall through to 'balanced' so the AI's
    existing behaviour is preserved on anything we haven't explicitly tuned.
    """
    return FACTION_POSTURE.get(faction or "", "balanced")


# S5 — Aeldari shimmy-step config. SHOOTY/HEAVY Aeldari units actively pick
# a NEW position each round (not the cover-snap to current spot) so they
# threat-range from a different vector and don't sit still. Sample circle
# radius = shimmy_distance inches around the unit.
_SHIMMY_DISTANCE: float = 4.0


def _shimmy_target(unit, nearest_enemy, map_) -> Optional[Tuple[float, float]]:
    """Pick a NEW position for an Aeldari shimmy-step.

    Constraints:
      1. Stays in range of `nearest_enemy` (so we can still shoot next phase).
      2. Sits in cover at least as strong as our current cover (prefer better).
      3. Is at least `_SHIMMY_DISTANCE * 0.75` from the unit's current pos so
         we actually move (avoids the cover-snap returning the same spot).

    Falls back to None if no point satisfies (1) & (3); the caller then
    drops back to the existing REPOSITION branch.
    """
    if map_ is None or nearest_enemy is None:
        return None
    rng = unit.profile.range_inches or 24
    px, py = unit.position
    ex, ey = nearest_enemy.position
    cur_cover_prio = _COVER_PRIORITY.get(map_.cover_at(unit.position).value, 0)
    min_move = _SHIMMY_DISTANCE * 0.75

    # Sample a ring at _SHIMMY_DISTANCE; pick the candidate with the highest
    # cover priority that's still in weapon range AND >=min_move away from us.
    best = None
    best_score = -1.0
    for i in range(16):
        angle = (2.0 * math.pi * i) / 16
        cx = px + _SHIMMY_DISTANCE * math.cos(angle)
        cy = py + _SHIMMY_DISTANCE * math.sin(angle)
        cx = max(0.0, min(map_.width, cx))
        cy = max(0.0, min(map_.height, cy))
        cand = (cx, cy)
        if map_.is_blocked(cand):
            continue
        if _dist(cand, (ex, ey)) > rng:
            continue
        if _dist(cand, unit.position) < min_move:
            continue
        cover_prio = _COVER_PRIORITY.get(map_.cover_at(cand).value, 0)
        # Weight cover heavily, then distance moved (so among equal-cover
        # candidates we prefer the one furthest from the previous spot).
        score = cover_prio * 10.0 + _dist(cand, unit.position)
        if score > best_score:
            best_score = score
            best = cand
    # Only accept the shimmy if we can STRICTLY improve our cover priority.
    # On a bare map with no terrain, every candidate has the same cover priority
    # as the current spot — fall back to the cover-snap branch (which on bare
    # terrain returns the unit's current position, i.e. no move). This keeps
    # the shimmy behaviour conservative: only step out when there's a cover
    # uplift to gain.
    if best is not None:
        new_prio = _COVER_PRIORITY.get(map_.cover_at(best).value, 0)
        if new_prio > cur_cover_prio:
            return best
    return None
# Fall Back (10e core): a unit within Engagement Range of an enemy may move
# up to M" away, passing through enemy models, but cannot shoot or charge
# this turn unless it has the FLY keyword. SHOOTY / HEAVY units that get
# tagged in melee prefer disengaging so they can resume shooting next round.
# Cited as `simulator.fall_back`.
_FALL_BACK_INTENT = "FALL_BACK"

# Engagement Range in SwegHammer's continuous model. Mirrors the simulator's
# in-engagement check inside _do_shoot.
_ENGAGEMENT_RANGE = 1.5

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


# S4 — Support / leader target priority bonus.
#
# Real top-faction play kills the buff aura first: a 95-pt Captain providing
# +1-to-hit to a 500-pt squad is worth more than its raw kill value. Our old
# scoring was kill_potential + ranged_value / threat_back, which under-rated
# support-role characters AND CHARACTER units carrying a leader aura.
#
# Multiplier applies when the defender's role is SUPPORT OR the defender has
# the CHARACTER keyword AND a registered LeaderAbility (i.e. a real aura).
_SUPPORT_TARGET_BONUS: float = 1.3


def _support_target_bonus(defender) -> float:
    """Return 1.3x when `defender` is a SUPPORT-role unit or a CHARACTER
    leader with a registered aura, else 1.0.

    The CHARACTER-with-aura branch uses `code.leaders.lookup_ability` so the
    bonus matches the in-sim leader registry (Captain / Farseer / Overlord /
    Cadre Fireblade / Lord of Contagion / etc.). A bare CHARACTER without
    an entry in the registry does NOT receive the bonus — it has no aura
    to take down. Imported lazily to avoid a strategy ↔ leaders cycle.
    """
    try:
        role = classify(defender.profile)
    except Exception:
        role = ""
    if role == "SUPPORT":
        return _SUPPORT_TARGET_BONUS
    kw = (defender.profile.unit_keywords or ()) if hasattr(defender, "profile") else ()
    if "CHARACTER" in kw:
        try:
            from .leaders import lookup_ability
            ability = lookup_ability(defender.profile.name)
        except Exception:
            ability = None
        if ability is not None:
            return _SUPPORT_TARGET_BONUS
    return 1.0


# ---------------------------------------------------------------------------
# S6 — Anti-swarm / screen-target priority (task #166)
# ---------------------------------------------------------------------------
# Tournament play prioritises CHAFF first: kill the OC-bearing swarm before
# the big-DPA target. Tyranids in particular over-perform in our sim because
# the opposing AI shoots at Carnifexes while Termagants drown the board and
# score primary. The bonus fires on profiles that are simultaneously:
#   - OC-relevant (oc >= 2) — the swarm exists to flip objectives
#   - Fragile (health <= 5 per model OR role classifies as HORDE)
# A 2-wound 0-OC unit (e.g. a non-OC tag-along) gets nothing; only OC-bearing
# chaff. The bonus is a 1.4x multiplier on the existing kill-potential score,
# stacking multiplicatively with `_gunline_charge_bonus` and
# `_support_target_bonus` — additive in the colloquial sense (it never
# *replaces* the underlying kill-potential math).
_SCREEN_TARGET_BONUS: float = 1.4


def _is_screen_target(profile) -> bool:
    """True when `profile` represents OC-bearing CHAFF that should be cleared
    before higher-DPA targets.

    Gated tightly:
      - profile.oc >= 2                                 # objective-relevant
      - per-model health <= 5 OR role classify == HORDE  # fragile / swarm
    """
    oc = getattr(profile, "oc", 0) or 0
    if oc < 2:
        return False
    health = getattr(profile, "health", 0) or 0
    if health <= 5:
        return True
    try:
        return classify(profile) == "HORDE"
    except Exception:
        return False


def _screen_target_bonus(defender) -> float:
    """Return 1.4x when `defender.profile` is a screen / chaff target, else 1.0.

    Applied as a multiplier on melee target-score and on ranged target
    priority. Additive bias only — never replaces the kill-potential calc.
    """
    profile = getattr(defender, "profile", None)
    if profile is None:
        return 1.0
    if _is_screen_target(profile):
        return _SCREEN_TARGET_BONUS
    return 1.0


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
    # S4: also apply a SUPPORT / leader-aura priority bonus so melee bricks
    # bias toward killing the buff character before the bodyguard squad.
    # S6 (#166): screen-target bonus biases attackers toward OC-bearing
    # chaff (Termagants, Cultists, Boyz) before high-DPA bricks. Tightly
    # gated to oc>=2 + (low W per-model OR HORDE role); see
    # `_is_screen_target`.
    return (base
            * _gunline_charge_bonus(p, tp)
            * _support_target_bonus(defender)
            * _screen_target_bonus(defender))


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
        # S4 — SUPPORT / leader-aura priority bonus: real play kills the
        # buff character before the bodyguard squad.
        support_bonus = _support_target_bonus(e)
        # S6 (#166) — screen-target bonus: bias charges into OC-bearing
        # chaff before high-DPA bricks.
        screen_bonus = _screen_target_bonus(e)
        score = (((kill_potential + 0.5 * ranged_value)
                  / (1.0 + threat_against))
                 * charge_p * gunline_bonus * support_bonus * screen_bonus)
        candidates.append((score, d, e))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, dist, target = candidates[0]
    return target, dist


def _pick_fall_back_destination(unit, enemies, map_) -> Optional[Tuple[float, float]]:
    """Pick a point up to ``M`` inches from ``unit`` that sits outside the
    engagement range (1.5") of every enemy in ``enemies``.

    Strategy: average the directions from each in-engagement enemy to the
    unit (i.e. the "away from the swarm" vector), step out by the unit's
    full Move characteristic, and verify the result clears every enemy by
    more than the engagement range. If the primary point is still inside an
    enemy's engagement bubble, sample a handful of points around the unit
    and return the first that clears all enemies. Returns None if no point
    on or near the unit can break engagement — caller falls through to the
    normal-move pick.

    Helper for the Fall Back move (10e core). Cited as ``simulator.fall_back``.
    """
    move = float(effective_move(unit))
    if move <= 0.0:
        return None
    px, py = unit.position

    # Direction "away from enemies": sum of unit_pos - enemy_pos vectors,
    # weighted by 1/distance so closer enemies dominate the retreat heading.
    dx_sum = 0.0
    dy_sum = 0.0
    for e in enemies:
        ddx = px - e.position[0]
        ddy = py - e.position[1]
        d = (ddx * ddx + ddy * ddy) ** 0.5
        if d < 1e-6:
            continue
        dx_sum += ddx / d
        dy_sum += ddy / d
    mag = (dx_sum * dx_sum + dy_sum * dy_sum) ** 0.5

    def _candidate(angle: float) -> Optional[Tuple[float, float]]:
        cx = px + move * math.cos(angle)
        cy = py + move * math.sin(angle)
        if map_ is not None:
            cx = max(0.0, min(map_.width, cx))
            cy = max(0.0, min(map_.height, cy))
            if map_.is_blocked((cx, cy)):
                return None
        # Must clear every enemy's engagement bubble by a small margin so
        # the simulator's strict `< 1.5` check actually flips to False.
        for e in enemies:
            if _dist((cx, cy), e.position) <= _ENGAGEMENT_RANGE + 0.01:
                return None
        return (cx, cy)

    # Primary heading: averaged away-vector.
    if mag > 1e-6:
        base_angle = math.atan2(dy_sum, dx_sum)
        cand = _candidate(base_angle)
        if cand is not None:
            return cand
    else:
        base_angle = 0.0

    # Fallback sweep: 12 angles around the unit. First clearing candidate wins.
    for i in range(12):
        offset = (2.0 * math.pi * i) / 12
        cand = _candidate(base_angle + offset)
        if cand is not None:
            return cand
    return None


_PLAN_LEFT = "LEFT_FLANK"
_PLAN_RIGHT = "RIGHT_FLANK"
_PLAN_MID = "MID_PUSH"
_PLAN_HOME = "HOME_HOLD"
_PLAN_COUNTER = "COUNTER"
_VALID_PLANS = (_PLAN_LEFT, _PLAN_RIGHT, _PLAN_MID, _PLAN_HOME, _PLAN_COUNTER)


def pick_army_plan(army, opponent, round_num: int, map_) -> str:
    """Pick the army's coordinated activation plan for this round.

    Real tournament armies don't pick each activation independently — they
    commit a round's worth of activations to a single objective: alpha-strike
    one flank, counter-charge the biggest threat, fall back to home objectives
    in the closing turns when ahead. Without an army-level plan the per-unit
    strategy picks scatter activations across the board and no alpha strike
    materialises.

    Decision logic:
      1. Round 1-2: aggressive push. Pick the flank where the opponent's
         centre of mass sits. T1-T2 want to engage before the gunline finishes
         setting up.
      2. Round 3-5: posture depends on score and threat:
         - Winning by >= 5 VP at this point AND in T4-T5: HOME_HOLD (lock in
           the win, protect own objectives).
         - Losing by >= 5 VP at T4-T5: COUNTER (target opponent's biggest
           threat, salvage VP).
         - Otherwise: continue the aggressive push, but COUNTER on T3+
           if the opponent has a clear high-DPA brick (Knight, Wraithlord,
           Battlesuit pile) worth committing to.

    Internal AI heuristic — not a 10e rule, no citation required (the
    auditor only enforces citations on simulator gates that implement GW
    rules; this is purely an activation scheduler).
    """
    # Round 1: pure push. Pick LEFT/RIGHT/MID based on opponent centre of mass.
    enemy_alive = list(opponent.alive_units) if opponent is not None else []
    if not enemy_alive:
        return _PLAN_MID

    # Centre of mass — point-weighted average of enemy positions.
    total_pts = 0.0
    sum_x = 0.0
    sum_y = 0.0
    for e in enemy_alive:
        w = max(1.0, float(getattr(e.profile, "points_cost", 1.0) or 1.0))
        sum_x += e.position[0] * w
        sum_y += e.position[1] * w
        total_pts += w
    enemy_com_x = sum_x / total_pts if total_pts > 0 else map_.width / 2.0

    half_x = map_.width / 2.0
    quarter = map_.width / 4.0

    # T4-T5 endgame: posture flips based on VP differential.
    if round_num >= 4:
        a_vp = getattr(getattr(army, "_battle_ref", None), "_a_vp", 0)
        b_vp = getattr(getattr(army, "_battle_ref", None), "_b_vp", 0)
        battle = getattr(army, "_battle_ref", None)
        if battle is not None:
            own_vp = a_vp if army is battle.a else b_vp
            other_vp = b_vp if army is battle.a else a_vp
            vp_diff = own_vp - other_vp
            if vp_diff >= 5:
                return _PLAN_HOME
            if vp_diff <= -5:
                return _PLAN_COUNTER

    # T3+: opt into COUNTER if the opponent has a single brick that dominates
    # their DPA contribution (Knight, Battlesuit pile, Wraithlord). Threshold:
    # one unit accounts for >= 40% of opponent's total points cost.
    if round_num >= 3:
        total_enemy_pts = sum(
            float(getattr(e.profile, "points_cost", 0.0) or 0.0)
            for e in enemy_alive
        )
        if total_enemy_pts > 0:
            biggest = max(
                enemy_alive,
                key=lambda e: float(getattr(e.profile, "points_cost", 0.0) or 0.0),
            )
            biggest_pts = float(getattr(biggest.profile, "points_cost", 0.0) or 0.0)
            if biggest_pts / total_enemy_pts >= 0.40:
                return _PLAN_COUNTER

    # Default: aggressive push aligned with enemy centre of mass.
    if enemy_com_x < half_x - quarter * 0.25:
        return _PLAN_LEFT
    if enemy_com_x > half_x + quarter * 0.25:
        return _PLAN_RIGHT
    return _PLAN_MID


def _plan_objective_bias(
    plan: Optional[str], obj, map_, friendly,
) -> float:
    """Return the multiplier the plan applies to an objective's score.

    LEFT_FLANK / RIGHT_FLANK: objectives on that flank get 1.5x; others 1.0x.
    MID_PUSH: centre objectives get 1.4x; others 1.0x.
    HOME_HOLD: friendly-side objectives 2.0x; enemy-side objectives 0.5x.
    COUNTER: no per-objective bias (target selection handles it).
    None: 1.0x (legacy behaviour).
    """
    if plan is None or map_ is None:
        return 1.0
    half_x = map_.width / 2.0
    half_y = map_.height / 2.0
    quarter = map_.width / 4.0
    if plan == _PLAN_LEFT:
        return 1.5 if obj.x < half_x else 1.0
    if plan == _PLAN_RIGHT:
        return 1.5 if obj.x >= half_x else 1.0
    if plan == _PLAN_MID:
        return 1.4 if abs(obj.x - half_x) <= quarter else 1.0
    if plan == _PLAN_HOME:
        # "Friendly side" — the half of the map nearer the army's own bulk.
        # Use friendly centre-of-mass Y to pick the home half cleanly.
        if friendly is not None and friendly.alive_units:
            cy = sum(u.position[1] for u in friendly.alive_units) / len(
                friendly.alive_units
            )
            home_top = cy < half_y
            obj_top = obj.y < half_y
            return 2.0 if home_top == obj_top else 0.5
        return 1.0
    return 1.0


def _plan_engage_bias(
    plan: Optional[str], unit, target, map_,
) -> float:
    """Plan multiplier on engaging/charging a particular enemy.

    LEFT_FLANK / RIGHT_FLANK: enemies on the matching half get 1.2x; others 1.0x.
    MID_PUSH: centre enemies get 1.2x; flank enemies 1.0x.
    COUNTER: highest-DPA enemy unit gets 1.5x (handled at call site since it
             requires the full enemy list).
    HOME_HOLD: 1.0x (we'd rather not chase).
    """
    if plan is None or map_ is None:
        return 1.0
    half_x = map_.width / 2.0
    quarter = map_.width / 4.0
    tx = target.position[0]
    if plan == _PLAN_LEFT:
        return 1.2 if tx < half_x else 1.0
    if plan == _PLAN_RIGHT:
        return 1.2 if tx >= half_x else 1.0
    if plan == _PLAN_MID:
        return 1.2 if abs(tx - half_x) <= quarter else 1.0
    return 1.0


def _counter_priority_uid(plan: Optional[str], enemy) -> Optional[str]:
    """For COUNTER plan, return the uid of the opponent's highest-DPA unit.

    Returns None for any other plan or when the enemy has no units.
    """
    if plan != _PLAN_COUNTER or enemy is None:
        return None
    alive = list(enemy.alive_units)
    if not alive:
        return None
    def _dpa(u):
        p = u.profile
        ranged = p.attacks * p.hit_probability * (p.weapon_damage_per_shot or 0.0)
        melee = p.melee_attacks * p.melee_hit_probability * (
            p.melee_damage_per_shot or 0.0
        )
        return max(ranged, melee)
    return max(alive, key=_dpa).uid


def pick_move_intent(
    unit, friendly, enemy, map_, army_plan: Optional[str] = None,
) -> Tuple[Tuple[float, float], str]:
    """
    Decide where `unit` should move this activation, and label the reason.

    Returns (target_position, intent_string). The simulator's _do_move
    treats target_position as the goal point — if it's the same as the
    unit's current position, no move happens (HOLD).

    `army_plan` (optional, default None) is the army's coordinated plan for
    the round (`LEFT_FLANK` / `RIGHT_FLANK` / `MID_PUSH` / `HOME_HOLD` /
    `COUNTER`). When set, objective and engage scoring receive plan-aware
    biases so units physically aligned with the plan push toward the
    plan's target zone. None preserves the legacy per-unit behaviour
    (callers that don't supply a plan see identical output to pre-#161).
    """
    role = classify(unit.profile)
    own_oc = getattr(unit.profile, "oc", 1) or 0

    # S1 — faction posture lookup. AI behaviour-shaping per faction, not a
    # 10e rule. `balanced` preserves the pre-S1 behaviour exactly.
    posture = _posture_for(unit.profile.faction)

    # S2 — round-weighted objective scoring. Late-game objective contests
    # (T4-T5) are worth more in real play than T2 sit-on-objective. Read
    # the live battle round via the army back-reference; default to 1 if
    # we're not running inside a Battle (catalogue tests, etc.).
    battle = getattr(friendly, "_battle_ref", None)
    cur_round = getattr(battle, "_current_round", 0) if battle is not None else 0
    if cur_round < 1:
        cur_round = 1
    round_weight = 1.0 + 0.15 * (cur_round - 1)

    # ----- 0. Fall Back (10e core) ------------------------------------------
    # A SHOOTY / HEAVY unit pinned inside enemy Engagement Range (1.5") loses
    # its activation — it can neither shoot nor (usefully) charge. The right
    # answer is to Fall Back: move up to M" away, eat a Desperate Escape test,
    # and resume shooting next round. Only run this when there's a viable
    # destination outside engagement of every enemy (otherwise the move would
    # just re-pin us). Cited as `simulator.fall_back` /
    # `simulator.desperate_escape`.
    if role in ("SHOOTY", "HEAVY"):
        enemies = enemy.alive_units
        in_engagement = any(
            _dist(unit.position, e.position) < _ENGAGEMENT_RANGE
            for e in enemies
        )
        if in_engagement and enemies:
            fall_back_pos = _pick_fall_back_destination(unit, enemies, map_)
            if fall_back_pos is not None:
                return fall_back_pos, _FALL_BACK_INTENT

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
    # S2: late-round contests dominate — multiply base value by `round_weight`
    # = 1 + 0.15*(round-1), so T5 stays-on-objective scores ~1.6x a T2 hold
    # and STEAL value at T5 (~5.6) easily beats sitting on a friendly-held
    # objective (~1.6). Round defaults to 1 when no Battle is active.
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
        value *= round_weight
        # S1 — posture bias: objective_hold / attrition / psychic_attrition
        # armies value CAPTURE more (they want to fill every objective);
        # horde_push only boosts CAPTURE for HORDE units (the bodies, not
        # the smashers).
        if posture in ("objective_hold", "attrition", "psychic_attrition"):
            value *= 1.3
        elif posture == "horde_push" and role == "HORDE":
            value *= 1.3
        elif posture == "ambush_alpha" and cur_round >= 2:
            # GSC: T1 close-in, T2+ pivot to objective focus.
            value *= 1.3
        # Distance-weighted: closer objectives win unless their value dominates
        score = value / (1.0 + d / 12.0)
        # Plan bias: LEFT/RIGHT/MID push tilt toward objectives on the plan's
        # target zone; HOME_HOLD doubles friendly-side and halves enemy-side.
        # No-op (1.0x) when army_plan is None.
        score *= _plan_objective_bias(army_plan, obj, map_, friendly)
        objs.append((score, intent, obj, d))

    # S1 — attrition: prefer the closest UNDER-DEFENDED objective over the
    # converged-on best one, so DG / Tsons spread Plague Marines onto every
    # marker. Implementation: bias scoring slightly toward objectives where
    # no friendly is already within control radius. This is a tie-breaker
    # multiplier, not a replacement.
    if posture in ("attrition", "psychic_attrition") and objs:
        new_objs = []
        for score, intent, obj, d in objs:
            our_count = _oc_on_objective(friendly.alive_units, obj, exclude_uid=unit.uid)
            if our_count == 0:
                score *= 1.25   # boost objectives no friend already covers
            new_objs.append((score, intent, obj, d))
        objs = new_objs

    best = max(objs, key=lambda t: t[0]) if objs else None

    # ----- 3. Role bias: shooty / heavy stay put when in firing range -----
    nearest_enemy = None
    nearest_enemy_dist = float("inf")
    for e in enemy.alive_units:
        d = _dist(unit.position, e.position)
        if d < nearest_enemy_dist:
            nearest_enemy_dist = d
            nearest_enemy = e

    # Aeldari Battle Focus — ASURYANI units bias toward advancing when:
    #   (a) the unit has a Battle Focus token available
    #   (b) the unit is OUT of weapon range of the nearest enemy
    # In that case, return an ENGAGE intent toward the enemy so the
    # simulator's Advance + token-spend logic fires. Without this branch the
    # SHOOTY/HEAVY in-range hold below traps Aeldari shooters into staying
    # put with tokens unspent. Token-spend itself is handled by _do_shoot.
    kw = unit.profile.unit_keywords or ()
    if (
        "ASURYANI" in kw
        and getattr(friendly, "battle_focus_tokens", 0) > 0
        and nearest_enemy is not None
    ):
        rng = unit.profile.range_inches or 24
        if nearest_enemy_dist > rng:
            # Out of range — advance + shoot is better than stay-and-skip.
            return nearest_enemy.position, _ENGAGE_INTENT

    if role in ("SHOOTY", "HEAVY") and nearest_enemy is not None:
        rng = unit.profile.range_inches or 24
        if nearest_enemy_dist <= rng:
            # S5 — Aeldari shimmy-step. ASURYANI / shimmy-posture SHOOTY/
            # HEAVY units actively pick a NEW position each round (different
            # cover, different firing lane) rather than sitting still. Falls
            # back to the cover-snap below if no shimmy candidate satisfies
            # the in-range constraint.
            if posture == "shimmy":
                shimmy_pos = _shimmy_target(unit, nearest_enemy, map_)
                if shimmy_pos is not None:
                    return shimmy_pos, _REPOSITION_INTENT
            # S1 — alpha_strike: at T1 a T'au gunline still wants to reposition
            # into a better fire-lane (find best cover within ~6" rather than
            # the tighter 3" snap). After T1 the unit holds. fast_strike same
            # shape but biased toward closer to the enemy backline.
            if posture == "alpha_strike" and cur_round == 1:
                repo_pos = _best_nearby_cover_point(map_, unit.position, search_radius=6.0)
                return repo_pos, _REPOSITION_INTENT
            if posture == "fast_strike" and cur_round == 1:
                # Step toward the enemy slightly to compress on the backline.
                ex, ey = nearest_enemy.position
                step_to = (
                    unit.position[0] + 0.3 * (ex - unit.position[0]),
                    unit.position[1] + 0.3 * (ey - unit.position[1]),
                )
                repo_pos = _best_nearby_cover_point(map_, step_to, search_radius=4.0)
                return repo_pos, _REPOSITION_INTENT
            # In range — don't drift around. But snap to nearby cover when
            # available so we get the defensive uplift.
            repo_pos = _best_nearby_cover_point(map_, unit.position, search_radius=3.0)
            return repo_pos, _REPOSITION_INTENT

    # COUNTER plan: precompute the highest-DPA enemy uid once, then weight
    # its score 1.5x in MELEE/DUAL pick.
    counter_uid = _counter_priority_uid(army_plan, enemy)

    def _plan_target_score(base: float, target) -> float:
        s = base * _plan_engage_bias(army_plan, unit, target, map_)
        if counter_uid is not None and target.uid == counter_uid:
            s *= 1.5
        return s

    # MELEE closes on the BEST melee target (the gunline / battlesuit /
    # support character whose squishy melee profile we can crack open),
    # not just the nearest enemy. Without this bias, melee bricks waste
    # activations on hard-to-kill bricks and never engage the priorities
    # that under-rate our sim's T'au / Astartes / Votann shooty factions.
    if role == "MELEE" and enemy.alive_units:
        scored = sorted(
            enemy.alive_units,
            key=lambda e: _plan_target_score(_melee_target_score(unit, e), e),
            reverse=True,
        )
        return scored[0].position, _ENGAGE_INTENT

    # DUAL: if a high-value charge target is within potential charge range
    # next round (move + 12" threat), close on it; otherwise fall through
    # to objective logic. This is what real Intercessor / Boyz / similar
    # do — bias toward enemies with weak melee, not just the closest body.
    if role == "DUAL" and enemy.alive_units:
        move_dist = effective_move(unit)
        threat_range = move_dist + 12.0
        viable = [
            e for e in enemy.alive_units
            if _dist(unit.position, e.position) <= threat_range
        ]
        if viable:
            best_melee = max(
                viable,
                key=lambda e: _plan_target_score(_melee_target_score(unit, e), e),
            )
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


__all__ = [
    "pick_move_intent", "should_fire_stratagem", "should_declare_waaagh",
    "pick_doctrina_imperative", "pick_army_plan",
]


# ---------------------------------------------------------------------------
# Adeptus Mechanicus Doctrina Imperatives AI (per-round pick)
# ---------------------------------------------------------------------------

# The simulator calls this once per Command phase for each AdMech army.
# Returns "protector" or "conqueror" — the imperative the army should run
# THIS round. The decision logic:
#   * Count "shooty" units (ranged DPA > 0) vs "melee" units (melee DPA > 0).
#     Most AdMech units are dual-profile, so we use a relative comparison.
#   * Count engaged units (within 12" of any enemy) — proxy for "the army is
#     committing to melee this turn".
#   * Rule: if engaged_count >= shooty_count, pick "conqueror" (the army has
#     committed; melee buff pays). Otherwise pick "protector" (default
#     gunline posture).
def pick_doctrina_imperative(army, enemy) -> str:
    """Return the imperative the AdMech AI should select THIS Command phase.

    Args:
        army: the AdMech Army whose imperative is being picked.
        enemy: the opposing Army (for engagement-range calculation).

    Returns:
        "protector" or "conqueror".
    """
    alive = army.alive_units
    if not alive:
        return "protector"   # nothing to buff; pick the default

    shooty_count = 0
    for u in alive:
        p = u.profile
        ranged_dpa = (
            p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
        )
        if ranged_dpa > 0.0:
            shooty_count += 1

    # Engagement-range count: units within 12" of any alive enemy unit.
    engaged_count = 0
    enemies = enemy.alive_units if enemy is not None else []
    for u in alive:
        ux, uy = u.position
        for e in enemies:
            ex, ey = e.position
            if ((ux - ex) ** 2 + (uy - ey) ** 2) ** 0.5 <= 12.0:
                engaged_count += 1
                break

    if engaged_count >= shooty_count:
        return "conqueror"
    return "protector"


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
# Deep Strike arrival AI (#153)
# ---------------------------------------------------------------------------
#
# Real tournament deep-strike is a coordinated alpha-strike, not a per-unit
# trickle. The simulator's old behaviour rolled a 66% gate per unit per round,
# which meant a 4-unit reserves pool dribbled in over 3-4 rounds and got
# picked off piecemeal. The new AI:
#
#   * Round 2: hold unless the enemy gunline is exposed (no screens within 9")
#     OR an objective steal is open. If holding, the units stay in reserves.
#   * Round 3: drop ALL remaining DS units (alpha strike window).
#   * Round 4-5: drop ALL remaining DS units, biased toward objective grabs
#     over max-threat targets. Never leave a unit in reserves past Round 4 —
#     it scores zero VP and contributes zero damage.
#
# The scoring inside `_pick_arrival_point` (simulator.py) handles the
# "what to land near" question; this module answers "should we land NOW"
# and (via `pick_mass_arrival_anchor`) "where is the squad's centre point
# when multiple units drop the same round".


def _is_gunline_screened(opponent) -> bool:
    """True iff the opponent's gunline (SHOOTY/HEAVY units) is screened.

    A gunline unit is "screened" if any friendly INFANTRY/HORDE/SUPPORT
    body sits within 9" of it — that body soaks the deep-strike charge and
    blocks LOS to the squishy shooters. Returns True iff EVERY shooty unit
    has at least one screen-eligible friend within 9".

    Used by `decide_deepstrike_drops` to decide whether an alpha strike is
    worthwhile at Round 2. If every shooter is screened, the DS unit can't
    reach the soft target without going through a tarpit — better to wait.
    """
    if opponent is None:
        return False
    shooters = []
    screeners = []
    for u in opponent.alive_units:
        try:
            role = classify(u.profile)
        except Exception:
            role = ""
        if role in ("SHOOTY", "HEAVY"):
            shooters.append(u)
        # A screener is anything cheap-bodied that isn't itself a primary
        # gunline piece: HORDE/SUPPORT/MELEE INFANTRY counts.
        if role in ("HORDE", "SUPPORT", "MELEE", "DUAL"):
            screeners.append(u)
    if not shooters:
        return False   # no gunline to screen
    if not screeners:
        return False   # gunline is naked
    for s in shooters:
        sx, sy = s.position
        protected = False
        for f in screeners:
            if f is s:
                continue
            fx, fy = f.position
            if ((sx - fx) ** 2 + (sy - fy) ** 2) ** 0.5 <= 9.0:
                protected = True
                break
        if not protected:
            return False
    return True


def _has_objective_steal_open(opponent, friendly, map_) -> bool:
    """True iff at least one objective is contested-or-enemy-held AND a DS
    landing point > 9" from every enemy can plausibly reach within 3"
    of it. Cheap heuristic — we check the objective is not friendly-only
    and that the legal-landing radius around it (12" annulus) is on the
    map. The actual landing-point picker will refuse impossible placements.
    """
    if map_ is None or not getattr(map_, "objectives", ()):
        return False
    friendly_units = list(getattr(friendly, "alive_units", ()) or ())
    enemy_units = list(getattr(opponent, "alive_units", ()) or ())
    for obj in map_.objectives:
        ox, oy = obj.x, obj.y
        f_oc = sum(
            getattr(u.profile, "oc", 1)
            for u in friendly_units
            if ((u.position[0] - ox) ** 2 + (u.position[1] - oy) ** 2) ** 0.5
            <= obj.control_radius
        )
        e_oc = sum(
            getattr(u.profile, "oc", 1)
            for u in enemy_units
            if ((u.position[0] - ox) ** 2 + (u.position[1] - oy) ** 2) ** 0.5
            <= obj.control_radius
        )
        if e_oc >= f_oc:
            # The enemy is currently winning (or tying) this objective —
            # a deep-strike onto it is a steal candidate. We don't try to
            # check >9"-from-every-enemy here; the landing picker enforces
            # that, and refusing the drop here would leave units stranded.
            return True
    return False


def decide_deepstrike_drops(
    round_num: int,
    waiting_units,
    opponent,
    friendly,
    map_,
):
    """Return the subset of `waiting_units` that should land THIS round.

    Decision table:
      Round 1: never (deep-strikers can't arrive before Round 2; Cult
               Ambush is handled separately via cult_ambush_pending).
      Round 2: drop ALL only if the gunline is exposed OR an objective
               steal is open. Otherwise hold everything.
      Round 3: drop ALL remaining (alpha-strike window).
      Round 4+: drop ALL remaining (never waste reserves on a final round).

    The caller (`Battle._arrive_from_reserves`) is responsible for handling
    Cult Ambush separately — those units are flagged `cult_ambush_pending`
    and land deterministically on Round 1, bypassing this gate.

    Args:
        round_num: current battle round (1..MAX_ROUNDS).
        waiting_units: list of Unit instances in reserves (excluding any
            cult-ambush-pending units, which the caller drops directly).
        opponent: the enemy Army (alive_units used for screen detection).
        friendly: this Army (used for objective-control check).
        map_: the battlefield Map (objectives, dimensions).

    Returns:
        List of Unit instances to land this round. May be empty.
    """
    if not waiting_units:
        return []
    if round_num < 2:
        return []
    if round_num >= 3:
        # Alpha-strike window opens at T3. Empty reserves by end of T4 latest.
        return list(waiting_units)
    # Round 2: gated on enemy posture.
    gunline_exposed = not _is_gunline_screened(opponent)
    steal_open = _has_objective_steal_open(opponent, friendly, map_)
    if gunline_exposed or steal_open:
        return list(waiting_units)
    return []


def pick_mass_arrival_anchor(
    round_num: int,
    units_dropping,
    opponent,
    friendly,
    map_,
):
    """Pick a centre point for a coordinated mass-drop landing zone.

    When 2+ units arrive the same round, they should land near each other
    so they can charge / support the same target. This returns the anchor
    coordinate; the simulator's `_pick_arrival_point` is then asked to
    place each unit's actual landing point near this anchor (within ~12").

    For T2-T3 mass drops the anchor is the highest-threat enemy position.
    For T4+ drops the anchor is the centre of the nearest non-friendly
    objective — late-game DS exists to grab end-game VP.

    Returns None if no sensible anchor can be picked (no enemies, no
    objectives, or empty drop list).
    """
    if not units_dropping or opponent is None:
        return None
    enemies = list(getattr(opponent, "alive_units", ()) or ())
    friendly_units = list(getattr(friendly, "alive_units", ()) or ())

    # Round 4+: prefer an objective anchor (steal / contest endgame VP).
    if round_num >= 4 and map_ is not None and getattr(map_, "objectives", ()):
        best_obj = None
        best_d = float("inf")
        for obj in map_.objectives:
            ox, oy = obj.x, obj.y
            controlled_by_us = any(
                ((u.position[0] - ox) ** 2 + (u.position[1] - oy) ** 2) ** 0.5
                <= obj.control_radius
                for u in friendly_units
            )
            if controlled_by_us:
                continue
            # Distance from board centre as a tie-breaker — central
            # objectives are usually the contested ones.
            cx, cy = map_.width / 2.0, map_.height / 2.0
            d = ((ox - cx) ** 2 + (oy - cy) ** 2) ** 0.5
            if d < best_d:
                best_d = d
                best_obj = obj
        if best_obj is not None:
            return (best_obj.x, best_obj.y)

    # T2-T3 (and T4 fallback if no contestable objective): aim at the
    # heaviest enemy threat. We use the same role-weighted scoring as
    # the per-unit landing picker so the anchor sits where the DS scoring
    # function will agree.
    if not enemies:
        return None
    role_weight = {
        "HEAVY":   3.0,
        "SHOOTY":  2.5,
        "DUAL":    1.5,
        "MELEE":   1.0,
        "SUPPORT": 1.2,
        "HORDE":   0.8,
    }
    def _w(e):
        try:
            return role_weight.get(classify(e.profile), 1.0)
        except Exception:
            return 1.0
    best = max(enemies, key=_w)
    return best.position


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


# ---------------------------------------------------------------------------
# CP reservation by predicted-pivotal-turn (#160)
# ---------------------------------------------------------------------------
# Top players RESERVE CP for known-pivotal turns rather than burning it on the
# first eligible trigger. The greedy heuristic in should_fire_stratagem below
# is augmented with a deferral layer: if the current round is *before* the
# stratagem's pivotal turn AND the army doesn't have abundant CP, hold.
#
# Reactive stratagems (Counter-Offensive, Heroic Intervention, Tank Shock,
# Spirit Stones) have no predictable pivotal turn — they fire whenever the
# trigger is met. We model that by returning 0 from _predict_pivotal_turn,
# which the deferral layer treats as "no preferred turn — defer to the
# existing trigger heuristic".
#
# T5 escape hatch: if the battle is on its final round and the army still
# has CP for an offensive stratagem with no future opportunity to spend it,
# fire anyway rather than waste the CP.

_FINAL_ROUND: int = 5     # 10e core: 5-round Strike Force battle


def _predict_pivotal_turn(strat) -> int:
    """Return the round the stratagem is most valuable to fire on.

    0 means "reactive — no predictable pivotal turn; defer to trigger logic".
    Values 1..5 indicate the preferred firing round; earlier rounds defer
    unless CP is abundant.

    Pivotal-turn assignments by stratagem class (per task #160):
      * Counter-Offensive: reactive (opponent fight-phase kill triggers it).
      * Heroic Intervention: reactive (enemy charge near friendly CHARACTER).
      * Tank Shock: reactive (vehicle charge succeeds).
      * Spirit Stones: reactive (damage taken).
      * Command Re-Roll: T2 (highest-stakes early swing); T5 also escapes.
      * Implacable Onslaught (Necron, defensive FNP): T3 — alpha-strike
        recovery, mid-game wounded brick.
      * Methodical Destruction (Necron, offensive hit buff): T2 — alpha
        shooting window.
      * Cabbalistic Empowerment (TSons psychic +1 wound): T2.
      * Plague Weapons, Outbreak of Pestilence, Doombolt, Twist of Fate,
        Fire and Fade, Matchless Agility, Strike Swiftly,
        Methodical Destruction-class offensive: T2 — the alpha-strike
        window when shooting / fighting decides the game.
      * Disgustingly Resilient, Glamour of Tzeentch, Lightning-Fast
        Reactions: T3 — mid-game survival window.
    """
    name = strat.name
    # Reactive — no deferral; trigger-driven only.
    if name in (
        "Counter-Offensive", "Heroic Intervention", "Tank Shock",
        "Spirit Stones",
    ):
        return 0
    # Defensive mid-game (wounded high-value brick survival).
    if name in (
        "Disgustingly Resilient", "Glamour of Tzeentch",
        "Lightning-Fast Reactions", "Implacable Onslaught",
    ):
        return 3
    # Offensive alpha-strike window (T2 by default — the round where shooting
    # and combat decide the game). Command Re-Roll lives here too.
    return 2


def _get_current_round(army) -> int:
    """Pull the live round from the army's back-reference to its Battle.

    Returns 0 if the round isn't available (e.g. unit tests instantiate the
    army without running a Battle) — which the deferral layer treats as
    "no round info, don't defer".
    """
    battle = getattr(army, "_battle_ref", None)
    if battle is None:
        return 0
    return int(getattr(battle, "_current_round", 0) or 0)


def _should_hold_for_pivotal_turn(army, strat) -> bool:
    """Return True if the army should DEFER firing this stratagem rather than
    spending CP now, based on the predicted pivotal turn.

    Rules:
      * pivotal_turn == 0 (reactive): never hold — defer to trigger logic.
      * cost <= 0 (refunded by an ability): never hold.
      * current_round == pivotal_turn or beyond: never hold.
      * current_round == final round (T5): never hold — use it or lose it.
      * remaining CP > 2 * cost: never hold (CP abundant).
      * current_round < pivotal_turn AND cost > 0 AND CP not abundant: HOLD.
    """
    cost = int(getattr(strat, "cp_cost", 0) or 0)
    if cost <= 0:
        return False
    pivotal = _predict_pivotal_turn(strat)
    if pivotal <= 0:
        return False
    current = _get_current_round(army)
    if current <= 0:
        # No live round (unit tests) — don't defer.
        return False
    if current >= _FINAL_ROUND:
        return False     # T5 escape hatch: spend or waste.
    if current >= pivotal:
        return False     # We've reached the pivotal turn (or later).
    # Abundant CP — fire anyway, we can afford it.
    cp = int(getattr(army, "command_points", 0) or 0)
    if cp > 2 * cost:
        return False
    return True


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

    # CP reservation by predicted-pivotal-turn (#160). Top players hold CP
    # for known-pivotal rounds rather than burning it on the first eligible
    # trigger. Reactive stratagems (Counter-Offensive, Heroic Intervention,
    # Tank Shock, Spirit Stones) and zero-cost stratagems are exempt.
    if _should_hold_for_pivotal_turn(army, strat):
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

    # ----- Saim-Hann (Aeldari) — Spirit Stones --------------------------

    if name == "Spirit Stones":
        # ctx expects {"target": Unit}. Defensive 1 CP — fire on a heavily
        # damaged Aeldari brick. Aeldari already over-rates by +7.5 vs the
        # meta in calibration, so the gate is intentionally tighter than
        # Lightning-Fast Reactions: require HP loss > 50% AND points cost
        # >= 150 (Wraithlord / Avatar / vehicle bracket). Halving damage
        # is a big swing on multi-wound models with serious HP left, so
        # this stratagem must be reserved for the canonical "save the
        # Knight-class unit" scenarios.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.5 and cost >= 150.0

    # ----- Awakened Dynasty (Necrons) -----------------------------------

    if name == "Implacable Onslaught":
        # ctx expects {"target": Unit}. 1 CP for a transient FNP 5+ on a
        # Necron unit. Cheap defensive — fire whenever a meaningful Necron
        # unit has taken any HP loss. FNP 5+ delivers ~33% damage reduction
        # in expectation, comfortably worth 1 CP on a multi-wound model.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        # Even at full HP the prophylactic value of FNP 5+ on a 100+ pt
        # Necron unit is worth 1 CP this round — Reanimation Protocols are
        # less effective against alpha strikes. Lowered HP gate to >= 0.0.
        return cost >= 80.0 and hp_frac >= 0.0

    if name == "Methodical Destruction":
        # ctx expects {"attacker": Unit, "target": Unit}. +1 to hit on a
        # NECRONS unit's shooting for the round — fire when the attacker
        # has serious DPA AND the target is heavy. The +1 closes a 4+ to
        # a 3+, lifting per-shot expected damage by ~25%. Worth 1 CP on a
        # real ranged threat hitting a real target.
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

    # ----- Cult of Magic (Thousand Sons) — Cabbalistic Empowerment ------

    if name == "Cabbalistic Empowerment":
        # ctx expects {"target": Unit, "has_psyker": bool}. 1 CP to boost
        # the round's Doombolt payload from 2 MW to 3 MW. Only fires if a
        # psyker exists AND the target is HEAVY-class (otherwise the extra
        # MW is wasted on chip damage). Doombolt itself fires whenever a
        # psyker + target exist, so this is "pay 2 CP combined this round
        # for 3 MW" — only worth it on a meaningful target.
        target = ctx.get("target")
        if target is None or not ctx.get("has_psyker", False):
            return False
        return _is_heavy_target(target)

    # ----- Mont'ka (T'au Empire) — Strike Swiftly -----------------------

    if name == "Strike Swiftly":
        # ctx expects {"attacker": Unit}. Advance + shoot — fire for a
        # high-cost T'au shooter currently out of weapon range. T'au already
        # over-rates by +12 in calibration so the gate matches Matchless
        # Agility (cost >= 150) — Crisis Battlesuits / Broadsides only, not
        # Fire Warrior squads or Pathfinders.
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            cost = 0.0
        return cost >= 150.0

    # Unknown stratagem — let the simulator decide via its own dispatch.
    return False

