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

import functools
import math
import os
from typing import Dict, Optional, Tuple

from .detachments import effective_move
from .map import _terrain_epoch
from .roles import classify
from .units import save_probability, wound_probability


_HOLD_INTENT = "HOLD"
_CAPTURE_INTENT = "CAPTURE"
_STEAL_INTENT = "STEAL"
_ENGAGE_INTENT = "ENGAGE"
_REPOSITION_INTENT = "REPOSITION"
# AI-9 — sacrificial chaff intent: cheap unit deliberately pushed into the
# enemy backline to score Engage on All Fronts / Behind Enemy Lines secondary
# victory points. Reuses _ENGAGE_INTENT-like semantics for the simulator
# (a directed move target); the distinct label is so logs / tests can spot
# the heuristic firing.
_SACRIFICIAL_INTENT = "SACRIFICIAL"

# AI-9 — chaff detection threshold (per-model points cost). Real-meta chaff:
# Gretchin (3.6), Termagants (6), Cultists (5), Conscripts / Cadians /
# Neophytes (6.5), Battle Sisters / Kroot / Strike Teams (7-10). 15 catches
# the universe of squad-bodies-sold-cheap without tagging Intercessors (20+)
# or even slightly-elite-but-numerous units like Tactical Marines.
_CHAFF_MAX_POINTS_PER_MODEL: float = 15.0
# AI-9 — only enable for units with squad of 5+ models (per-model points cost
# of a CHARACTER under 15 is essentially impossible, but guard anyway —
# Custodian Guard sacrifice would be terrible).
_CHAFF_MIN_SQUAD_SIZE: int = 5


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
    cur_cover_prio = _cover_prio(map_, unit.position[0], unit.position[1])
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
        cover_prio = _cover_prio(map_, cand[0], cand[1])
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
        new_prio = _cover_prio(map_, best[0], best[1])
        if new_prio > cur_cover_prio:
            return best
    return None
# Fall Back (10e core): a unit within Engagement Range of an enemy may move
# up to M" away, passing through enemy models, but cannot shoot or charge
# this turn unless it has the FLY keyword. SHOOTY / HEAVY units that get
# tagged in melee prefer disengaging so they can resume shooting next round.
# Cited as `simulator.fall_back`.
_FALL_BACK_INTENT = "FALL_BACK"

# Engagement Range in SwegHammer's continuous model. 10e core: 1" horizontal
# (vertical 5" not modelled — sim is 2D). Mirrors the simulator's in-engagement
# check inside _do_shoot. Source: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Engagement-Range
_ENGAGEMENT_RANGE = 1.0

# Terrain-strength ranking used by the cover-bias helper. Higher wins when
# scoring candidate hold points around an objective. Imported lazily so this
# module stays import-cheap when map / TerrainType aren't needed.
_COVER_PRIORITY = {
    "open": 0,
    "light_cover": 1,
    "obscuring": 2,
    "heavy_cover": 3,
    "ruin": 3,          # 10e Ruin: Heavy Cover save bonus + LoS shield vs non-INFANTRY shooters
    "impassable": -1,   # never stand in impassable
}

# Per-map cover-priority lookup cache.
# Key: integer `epoch * 1_000_000 + ix * 1000 + iy` — avoids 3-tuple
# allocation and hash on every lookup. ix/iy are positions rounded to the
# 0.5" grid (max ~240 for a 120" board) so the encoding never collides.
# terrain_epoch is a cheap stable int from map._terrain_epoch(); it avoids
# both the GC id-reuse hazard of id(map_) and the cost of hashing the full
# terrain tuple as a key.
_cover_prio_cache: Dict[int, int] = {}


def _cover_prio(map_, px: float, py: float, _epoch: int = -1) -> int:
    """Return the integer cover priority at (px, py), using a per-map cache.

    Callers that invoke this in a tight loop (e.g. `_best_nearby_cover_point`)
    should pre-compute the epoch via `_terrain_epoch(map_.terrain)` and pass
    it as `_epoch` to avoid repeating the epoch dict lookup on every sample.
    """
    if _epoch < 0:
        _epoch = _terrain_epoch(map_.terrain)
    ix = round(px * 2)
    iy = round(py * 2)
    key = _epoch * 1_000_000 + ix * 1000 + iy
    try:
        return _cover_prio_cache[key]
    except KeyError:
        ct = map_.cover_at((ix * 0.5, iy * 0.5))
        p = _COVER_PRIORITY.get(ct.value, 0)
        _cover_prio_cache[key] = p
        return p


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


# Precomputed unit-circle offsets for n_samples=12 to avoid per-call trig.
_N_COVER_SAMPLES = 12
_COVER_SAMPLE_COS = [math.cos(2.0 * math.pi * i / _N_COVER_SAMPLES)
                     for i in range(_N_COVER_SAMPLES)]
_COVER_SAMPLE_SIN = [math.sin(2.0 * math.pi * i / _N_COVER_SAMPLES)
                     for i in range(_N_COVER_SAMPLES)]


def _best_nearby_cover_point(
    map_,
    base_pos: Tuple[float, float],
    search_radius: float = 3.0,
    n_samples: int = _N_COVER_SAMPLES,
) -> Tuple[float, float]:
    """Return a point within search_radius of base_pos sitting in the
    strongest cover terrain available (HEAVY > OBSCURING > LIGHT > OPEN).

    Cheap circular sampling: n_samples points evenly spaced on a circle of
    radius search_radius, plus base_pos itself. Ties resolve by proximity
    to base_pos. Skips IMPASSABLE candidates.
    """
    if map_ is None:
        return base_pos
    # Extract terrain epoch once — _cover_prio can reuse it for all 12+1
    # samples without repeating the terrain_epoch dict lookup each time.
    epoch = _terrain_epoch(map_.terrain)
    bx, by = base_pos
    best_prio = _cover_prio(map_, bx, by, _epoch=epoch)
    best_pt = base_pos
    best_d2 = 0.0
    mw, mh = map_.width, map_.height
    for cos_a, sin_a in zip(_COVER_SAMPLE_COS, _COVER_SAMPLE_SIN):
        px = bx + search_radius * cos_a
        py = by + search_radius * sin_a
        # Clamp inside the board
        if px < 0.0: px = 0.0
        elif px > mw: px = mw
        if py < 0.0: py = 0.0
        elif py > mh: py = mh
        prio = _cover_prio(map_, px, py, _epoch=epoch)
        if prio < 0:   # IMPASSABLE terrain has priority -1
            continue
        dx = px - bx
        dy = py - by
        d2 = dx * dx + dy * dy
        # Higher prio wins; tie-break by smaller d2 (closer to base_pos).
        if prio > best_prio or (prio == best_prio and d2 < best_d2):
            best_prio = prio
            best_pt = (px, py)
            best_d2 = d2
    return best_pt


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


# Per-faction OC-contest instrument (#79 follow-up). Populated only when
# SWEG_CONTEST_INSTR is set; a diag runner resets and reads it. Read-only.
CONTEST_STATS: dict = {}


def _oc_on_objective(units, obj, exclude_uid: str = "") -> int:
    """Sum the OC values of `units` within obj.control_radius (excluding one)."""
    r2 = obj.control_radius * obj.control_radius
    ox = obj.x
    oy = obj.y
    total = 0
    for u in units:
        if u.uid == exclude_uid:
            continue
        dx = u.position[0] - ox
        dy = u.position[1] - oy
        if dx * dx + dy * dy <= r2:
            total += u.profile.oc or 0
    return total


def _effective_oc_value(u) -> int:
    """Bracket-aware Objective Control of one model — mirrors Battle._effective_oc
    so the OC-contest AI (#79) reads the SAME effective OC the scorer awards on:
    a model in its 10e Damaged bracket contributes its reduced OC (a damaged Knight
    is OC 5, not 10). Respects the SWEG_DMGBRACKET gate."""
    base = u.profile.oc or 0
    if __import__("os").environ.get("SWEG_DMGBRACKET", "1") == "0":
        return base
    thr = getattr(u.profile, "damaged_threshold", 0) or 0
    pen = getattr(u.profile, "damaged_oc_penalty", 0) or 0
    if thr and pen and u.current_health <= thr:
        return max(0, base - pen)
    return base


def _effective_oc_on_objective(units, obj, exclude_uid: str = "") -> int:
    """Like `_oc_on_objective` but bracket-aware (uses `_effective_oc_value`).
    Used by the SWEG_CONTEST winnability check so a damaged enemy holder reads at
    its real reduced Objective Control."""
    r2 = obj.control_radius * obj.control_radius
    ox = obj.x
    oy = obj.y
    total = 0
    for u in units:
        if u.uid == exclude_uid:
            continue
        dx = u.position[0] - ox
        dy = u.position[1] - oy
        if dx * dx + dy * dy <= r2:
            total += _effective_oc_value(u)
    return total


# Speed lever #2 (PART A) — per-profile durability memoisation gate.
# `SWEG_DURCACHE` (default "1" = ON) controls the pure-core caches in the
# `_durability` hot path. When set to "0" the helpers fall through to the exact
# pre-existing uncached arithmetic, so a validation A/B can confirm the caches
# are byte-identical (they MUST be — these are memoisations of pure functions of
# immutable scalar inputs, not behaviour changes). Read once at import; an A/B
# run sets the variable in the environment before the process starts.
_DURCACHE_ON: bool = os.environ.get("SWEG_DURCACHE", "1") != "0"


def _unsaved_fraction_uncached(save: int, invuln_save: int, attacker_ap: int) -> float:
    """Exact pre-existing save+AP portion of _durability (uncached OFF path)."""
    save_pass = save_probability(save, attacker_ap)
    invuln_pass = save_probability(invuln_save) if invuln_save <= 6 else 0.0
    return max(0.05, 1.0 - max(save_pass, invuln_pass))


_unsaved_fraction_cached = functools.lru_cache(maxsize=4096)(_unsaved_fraction_uncached)


def _unsaved_fraction(save: int, invuln_save: int, attacker_ap: int) -> float:
    """Cached save+AP portion of _durability. Only ~200 distinct inputs possible.

    Pure function of three small ints, so memoisation is byte-identical. Gated by
    `SWEG_DURCACHE` (default ON); the OFF path is the byte-identical uncached
    arithmetic above."""
    if _DURCACHE_ON:
        return _unsaved_fraction_cached(save, invuln_save, attacker_ap)
    return _unsaved_fraction_uncached(save, invuln_save, attacker_ap)


def _fnp_resolved(profile, defender_unit) -> int:
    """Resolve the defender's effective FNP value: lower of profile.fnp and
    any leader-aura / detachment FNP granted via `effective_buffs`. Returns
    7 (no FNP) when neither source applies.

    Cited as `simulator.fnp_in_threat_score` in `data/rule_citations.json`.
    Quoted core rule (Wahapedia 10e):
        "Each time a model with this ability would lose a wound, roll one
         D6: if the result equals or exceeds the Feel No Pain value, that
         wound is not lost."
    Without folding FNP into the AI threat heuristic, opponent units see
    FNP-bearing defenders (Death Guard Plague Marines / Mortarion,
    Custodian Wardens, Necron units under Reanimation Protocols when
    granted by stratagem, Tyranid Tervigon, Nurgle daemons, Typhus-led
    Plague Marines with the Destroyer Hive 5+) as soft and pick them
    over harder targets — bouncing off the FNP wall in practice.
    """
    base_fnp = getattr(profile, "fnp", 7) or 7
    if defender_unit is None:
        return base_fnp
    # Look up aura-granted FNP (Typhus 5+ to Plague Marines, Mortarion's
    # detachment aura, etc.). Lower value wins (better roll).
    try:
        from .leaders import effective_buffs
        aura_fnp = effective_buffs(defender_unit).get("fnp", 7) or 7
    except Exception:
        # Defender has no army context (synthetic test profile) — fall back
        # to profile-only. effective_buffs raises when army_ref is missing
        # under certain test paths.
        aura_fnp = 7
    return min(base_fnp, aura_fnp)


def _fnp_pass_fraction_uncached(fnp: int) -> float:
    """Exact pre-existing FNP-pass arithmetic (uncached OFF path)."""
    if fnp >= 7:
        return 0.0
    if fnp <= 2:
        # FNP 2+ ignores 5/6 — theoretical floor; no 10e datasheet has it
        # but keep the formula consistent.
        return 5.0 / 6.0
    return (7 - fnp) / 6.0


_fnp_pass_fraction_cached = functools.lru_cache(maxsize=16)(_fnp_pass_fraction_uncached)


def _fnp_pass_fraction(fnp: int) -> float:
    """Probability a single unsaved wound is ignored by FNP. fnp=7 -> 0.0
    (no FNP), fnp=5 -> 2/6, fnp=4 -> 3/6. Mirrors the (7 - fnp) / 6 math
    from the core rule (roll equals or exceeds fnp on a D6).

    Pure function of one small int (fnp in 2..7), so memoisation is
    byte-identical. Gated by `SWEG_DURCACHE` (default ON); the OFF path is the
    byte-identical uncached arithmetic above."""
    if _DURCACHE_ON:
        return _fnp_pass_fraction_cached(fnp)
    return _fnp_pass_fraction_uncached(fnp)


# Iter 31-S1R — squad-size durability factor. AI heuristic, NOT a 10e rule.
# Compensation paired with the iter26-S1 FNP re-land: folding FNP into
# `_durability` caused opponent AI to correctly avoid FNP-bearing defenders
# and divert fire to soft no-FNP targets (Orks regressed +5.7 -> +10.1 at
# N=20). The mechanism: a 10-model Boyz squad still threatens return fire
# after losing 4 models — losing 4 of 10 is NOT the same single-attack
# decision as losing 4 of 4. The AI should treat high-model-count squads
# as effectively more durable from a per-shot allocation perspective.
#
# Formula (faction-neutral, linear in sibling count):
#   squad_factor = 1.0 + max(0, sibling_count - 1) * SQUAD_SIZE_FACTOR_PER_SIBLING
# A lone model has factor 1.0; 10-model squad has 1.45; 20-model Boyz 1.95.
# Cited as `simulator.squad_size_durability_factor`. Defender-allocation
# tie-in: the 10e core rule lets the defender allocate per-attack wounds
# across models in the unit (Make Allocation Roll), so a single fire
# decision against one model is not equivalent to wiping the whole unit.
SQUAD_SIZE_FACTOR_PER_SIBLING: float = 0.05


def _squad_size_factor(defender_unit) -> float:
    """Multiplicative durability bonus from sibling models in the defender's
    unit. A lone model returns 1.0; each additional alive sibling adds
    SQUAD_SIZE_FACTOR_PER_SIBLING. Faction-neutral.

    Sibling detection: same `profile.name` in `defender.army_ref.alive_units`
    with positive `current_health`. Falls back to 1.0 when no army context.
    """
    if defender_unit is None:
        return 1.0
    army = getattr(defender_unit, "army_ref", None)
    if army is None:
        return 1.0
    own_name = getattr(defender_unit.profile, "name", None)
    if not own_name:
        return 1.0
    try:
        sibling_count = army.squad_sibling_count(own_name)
    except Exception:
        return 1.0
    extras = max(0, sibling_count - 1)
    return 1.0 + extras * SQUAD_SIZE_FACTOR_PER_SIBLING


def _durability(profile, current_health: float, attacker_ap: int,
                defender_unit=None) -> float:
    """Effective durability against an attacker with the given AP.

    Combines remaining HP, toughness, the fraction of unsaved wounds
    after armour / invuln (whichever is better) and AP modifier, AND the
    Feel No Pain mitigation factor (`1 / (1 - fnp_pass_fraction)`). A
    Custodian Guard (T6, 3W, 2+/4++) is much tougher vs an AP0 melee weapon
    than HP alone suggests; a Fire Warrior (T3, 1W, 4+) is much frailer
    against AP-1 than a flat (T+HP) hides. Without folding the save in,
    high-Sv elite units register as "squishy melee targets" because their
    HP is low — exactly the T'au Battlesuit / Custodian over-rating we saw
    after the #96 charge AI landed.

    Iter 26 (S1): folded FNP into the durability score. Pass `defender_unit`
    so leader-aura / stratagem-granted FNP (Typhus 5+ to Plague Marines,
    transient Awakened Dynasty 5+, Drukhari 6+ from Pain Token) is
    resolved through `leaders.effective_buffs`. Cited as
    `simulator.fnp_in_threat_score`.

    Iter 31 (S1R): added a multiplicative squad-size durability bonus so
    high-model-count units (Boyz mobs, Termagant broods, Cultist swarms)
    look harder to wipe from a single-attack-decision perspective. This
    compensates for the iter26-S1 re-land's side effect of opponent AI
    diverting fire from FNP-bearing defenders to no-FNP horde armies.
    Cited as `simulator.squad_size_durability_factor`.
    """
    # Perf note (speed lever #2 / PART A): `_durability` and `_fnp_resolved` are
    # NOT memoised whole — they depend on MUTABLE per-unit runtime state
    # (`current_health` and `defender_unit`'s live army context: detachment,
    # in-range leader auras, sibling count). lru_cache-ing them keyed on those
    # would return stale durability after a unit takes wounds or a leader dies.
    # The PURE sub-cores are factored out and cached instead: `_unsaved_fraction`
    # (save+AP, pure ints) and `_fnp_pass_fraction` (pure int), both gated by
    # SWEG_DURCACHE; `effective_buffs` carries its own per-activation `_buffs_cache`.
    # Toughness adds the wound-roll difficulty (already in attacker's DPA via
    # hit*wound math). Keep T as a multiplier rather than additive so a T8
    # Knight reads multiplicatively harder than a T4 Marine of equal HP.
    fnp = _fnp_resolved(profile, defender_unit)
    fnp_mitigation = max(0.05, 1.0 - _fnp_pass_fraction(fnp))
    squad_factor = _squad_size_factor(defender_unit)
    return (profile.toughness * max(1.0, current_health) * squad_factor
            / (_unsaved_fraction(profile.save, profile.invuln_save, attacker_ap)
               * fnp_mitigation))


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


# ---------------------------------------------------------------------------
# S7 — Synapse-source target priority (task #168)
# ---------------------------------------------------------------------------
# Experienced opponents KILL the synapse-source unit (Hive Tyrant, Tervigon,
# Tyranid Prime) before the cheap chaff: dropping the SYNAPSE umbrella revokes
# the swarm's auto-pass Battle-shock shelter and opens every wounded Termagant
# brick to a real Ld test. This is a different mechanism from `_is_screen_target`
# — synapse sources are HIGH-W BRICKS (Hive Tyrant T9 W12), not chaff. The
# bonus stacks multiplicatively with screen / support / gunline biases.
#
# Gated:
#   - target carries the SYNAPSE keyword (`"SYNAPSE" in unit_keywords`)
#   - attacker is NOT Tyranids (intra-faction Tyranid combats don't get it —
#     two Tyranid armies in a mirror would otherwise both bias toward each
#     other's brood-lord, which is fine for non-mirror play but a no-op /
#     wash for mirror — easier to just hard-gate on attacker faction).
_SYNAPSE_TARGET_BONUS: float = 1.5


def _is_synapse_source(profile) -> bool:
    """True when `profile` carries the SYNAPSE keyword (Hive Tyrant, Tervigon,
    Tyranid Prime, Neurotyrant, etc.)."""
    return "SYNAPSE" in (getattr(profile, "unit_keywords", ()) or ())


def _synapse_target_bonus(attacker, defender) -> float:
    """Return 1.5x when `defender` is a SYNAPSE source AND `attacker` is
    non-Tyranid; else 1.0. See module docstring for motivation."""
    a_profile = getattr(attacker, "profile", None)
    d_profile = getattr(defender, "profile", None)
    if a_profile is None or d_profile is None:
        return 1.0
    if a_profile.faction == "Tyranids":
        return 1.0
    if not _is_synapse_source(d_profile):
        return 1.0
    return _SYNAPSE_TARGET_BONUS


# ---------------------------------------------------------------------------
# AI-4 — Adeptus Astartes Oath-of-Moment ranged target priority
# ---------------------------------------------------------------------------
# The Oath of Moment army rule (Adeptus Astartes chapters only — Codex
# Space Marines and its successor codices) nominates ONE enemy unit per
# turn against which every Marine attack re-rolls hit-1s and wound-1s.
# Real tournament Marine play DUMPS the whole army's firepower on the Oath
# target to compound those re-rolls — a Lieutenant + Devastators + Heavy
# Intercessor brick all firing into the same anchor, finishing it in one
# Shooting phase. The simulator's stock target-priority picks per-unit
# locally (lowest HP among candidates), which scatters Marine fire onto
# whatever's closest-to-dead per gun rather than concentrating on the
# Oath nomination. This bonus biases ranged target-score so that, when
# the Oath target is among the LoS+range candidates, it wins the pick.
#
# Gates:
#   - attacker is an Adeptus Astartes faction (per `is_marine_faction`,
#     which is the canonical membership test in `code/factions.py` and
#     EXCLUDES Grey Knights, Adeptus Custodes, Adepta Sororitas — they
#     are power-armour but don't share Oath of Moment).
#   - attacker_army.oath_target_uid is set (the army's Command-phase
#     pick exists for this round — see `_pick_oath_target`).
#   - defender.uid == oath_target_uid (the defender IS the Oath target).
#   - defender is alive (implicit — the caller filters for alive units
#     before scoring, but checked defensively here too).
#
# When all gates pass, return a 2.0x bonus. The shooting picker uses
# `current_health / (... * oath_bonus)` so a 2.0x bonus scores the Oath
# target at 0.5x its raw HP, biasing the `min(...)` pick toward it.
#
# Implicit gating via the candidates pool:
#   - LoS is enforced by the simulator's `has_line_of_sight` filter on
#     `candidates` BEFORE this bonus is consulted. A unit out of LoS
#     never reaches the scoring loop, so the 2x bias never fires for an
#     unreachable Oath target — exactly the behaviour the briefing asks
#     for. Same for range (the `_distance <= rng` filter).
#
# AI heuristic only — the Oath of Moment rule itself is already cited
# (`simulator.oath_of_moment`); this commit just teaches the AI to USE
# that nomination by concentrating fire on it. No new rule_citations
# entry needed.
_ASTARTES_OATH_TARGET_BONUS: float = 2.0


def _astartes_oath_target_bonus(attacker, defender, attacker_army) -> float:
    """Return 2.0x when `attacker` is an Adeptus Astartes unit whose army has
    nominated `defender` as its current Oath of Moment target; else 1.0.

    Caller (the shooting picker in `simulator._do_shoot`) divides the
    target-score by this bonus, so 2.0x reads as 0.5x raw HP — biasing
    the `min(...)` pick toward the Oath target.

    See module-section docstring for the full gate list and design.
    """
    # Local import to avoid the strategy <-> factions cycle at module
    # load time (factions module is small and free of strategy imports
    # so the cycle wouldn't actually fire, but the project standard is
    # to import locally inside per-call helpers).
    from .factions import is_marine_faction

    a_profile = getattr(attacker, "profile", None)
    if a_profile is None:
        return 1.0
    if not is_marine_faction(a_profile.faction):
        return 1.0
    if attacker_army is None:
        return 1.0
    oath_uid = getattr(attacker_army, "oath_target_uid", None)
    if oath_uid is None:
        return 1.0
    if getattr(defender, "uid", None) != oath_uid:
        return 1.0
    # Defensive alive-check; the caller already filters for alive units,
    # but a stale Oath target uid from earlier in the turn could survive
    # a casualty resolution mid-phase. Don't bias toward a corpse.
    if not getattr(defender, "is_alive", True):
        return 1.0
    return _ASTARTES_OATH_TARGET_BONUS


# ---------------------------------------------------------------------------
# AI-8 — Transport target priority (faction-neutral, AI play-style)
# ---------------------------------------------------------------------------
# Real tournament opponents always shoot TRANSPORT units first. The reason
# is structural: every 10e transport carries an embarked unit that will
# disembark and alpha-strike on a future turn (Wych Cult out of a Raider /
# Venom, Custodes Wardens out of a Land Raider, Incubi out of a Venom,
# Sisters Battle Sisters out of an Immolator, Astartes Intercessors out of
# a Repulsor, etc.). Destroying the transport BEFORE the disembark either
# kills the passengers outright (if they fail the emergency disembark)
# or strands them in an unhelpful position, denying the alpha-strike.
# Letting the transport live for one more turn gives the embarked unit a
# fresh delivery vector — a 50-point Raider that survives until turn 3 is
# worth maybe 200 points of effective threat from the unit it dropped.
#
# The DRK-DIAG (agent a599761a1e95a00e6) audit found Drukhari over-
# performing by +34.6 points in the simulator because opponents scored
# the 4x Raider + 2x Venom transports the same as any other ranged target,
# often leaving them alive into turn 3 when the Wych Cult disembarked at
# full strength. Real-meta opponents prioritise transports as their
# top-priority shooting target before the disembark window.
#
# This is a PLAY HEURISTIC, not a 10e rule, so it lives in the AI layer
# and has no rule_citations entry. The "rule" is the universal tournament
# play-pattern of bracketing the disembark, not any codex text.
#
# Gate (faction-neutral attacker, defender-keyword-gated):
#   - defender has TRANSPORT keyword in unit_keywords
#   - attacker is any faction (no faction gate — every army benefits from
#     killing the enemy's transports before the passengers disembark)
#
# Effect: base 1.8x bonus on the target-priority score, escalated to 2.2x
# when the transport is currently carrying at least one passenger (the
# "loaded" case where killing the transport disrupts the embarked unit).
# Stacks multiplicatively with the existing screen / synapse / oath chain.
_TRANSPORT_TARGET_BONUS: float = 1.8
_TRANSPORT_TARGET_BONUS_LOADED: float = 2.2


def _transport_target_bonus(defender) -> float:
    """Return a target-priority multiplier when `defender` is a TRANSPORT.

    Faction-neutral on the attacker side: every army should prioritise
    enemy transports before their passengers disembark.

    - 1.8x when defender has TRANSPORT keyword (catches the "empty
      transport" case where the passengers already disembarked but the
      transport itself remains a screening / firing-deck threat).
    - 2.2x when the transport additionally has at least one passenger
      (the alpha-strike-disrupt case — destroying the transport here
      either kills or strands the embarked unit).
    - 1.0x otherwise.

    Returned bonus is multiplicative on the shooting picker's
    `current_health / (... * bonus_chain)` score: a 2.2x bonus reads as
    0.45x raw HP, biasing the `min(...)` pick toward the transport.
    """
    profile = getattr(defender, "profile", None)
    if profile is None:
        return 1.0
    keywords = getattr(profile, "unit_keywords", ()) or ()
    if "TRANSPORT" not in keywords:
        return 1.0
    # `passengers` is a list on every Unit instance (see Unit.__init__ in
    # code/units.py). An empty list means the transport is currently un-
    # loaded — still worth the base 1.8x bias to deny screen / firing-deck
    # value, but not the escalated 2.2x.
    passengers = getattr(defender, "passengers", None) or ()
    if passengers:
        return _TRANSPORT_TARGET_BONUS_LOADED
    return _TRANSPORT_TARGET_BONUS


# ---------------------------------------------------------------------------
# DRK-DIAG-11 — Drukhari fragile flyer / gun-skimmer shooting target priority
# ---------------------------------------------------------------------------
# Real tournament opponents facing a Drukhari list prioritise the army's
# fragile high-output gun-skimmers and flyers BEFORE wading into the
# infantry, alongside the AI-8 transport priority that already biases
# toward Raiders / Venoms. The targets in question are:
#
#   Ravager           — three lances or disintegrators on a T9 W11 sv4+
#                       chassis with no invuln / no Feel No Pain
#   Voidraven Bomber  — Void mine + two void lances on T9 W12 sv4+, no
#                       invuln / no Feel No Pain
#   Razorwing Jetfighter — twin lances + missile rack on T8 W10 sv4+, no
#                          invuln / no Feel No Pain
#   Reaper / Raven Strike Fighter (Legends) — equivalent profiles
#
# These chassis pump out alpha-strike damage that scales linearly with
# rounds alive but die in a single focused-fire round to most mid-tier
# anti-tank weaponry (no invuln to soak Lascannons, no Feel No Pain
# 6+/5+ to chip wounds). Real-meta opponents always shoot them in the
# first opportunity — letting a Ravager live to round 2 costs ~6
# damage-per-shot more than killing it on round 1. The simulator's
# default current_health-min picker chews through tougher TRANSPORT
# targets first (Tantalus T10 W18) when the right play is to remove the
# fragile high-damage chassis.
#
# DRK-DIAG-9 (mobility VP damper) and DRK-DIAG-10 (offensive VP damper)
# attacked the residual at the secondary-scoring envelope. DRK-DIAG-5
# fixed dual-firing on Raider / Ravager / Razorwing. DRK-DIAG-7 audited
# Combat Drugs clean. The remaining lever per the DRK-DIAG-7 carry-
# forward note in docs/AUTO_LOOP_LOG.md is "AI target-priority bias
# toward fast skimmers" — this commit lands that lever.
#
# Gate (defender-keyword-gated, faction-gated, no attacker gate):
#   - defender.profile.faction == "Drukhari"
#   - defender has BOTH VEHICLE AND FLY keywords (catches the skimmer /
#     flyer subset, excludes Talos / Cronos MONSTERs and the foot
#     infantry)
#   - defender has no invulnerable save (invuln_save >= 7) AND no Feel
#     No Pain (fnp >= 7). This is what makes them FRAGILE — Knights /
#     Custodes Caladius Grav-tanks are also FLY VEHICLE but carry 5++
#     and FNP layers that change the calculus.
#
# Effect: 1.5x target-priority multiplier. Smaller than the
# TRANSPORT_TARGET_BONUS (1.8x empty / 2.2x loaded) because Raiders /
# Venoms which ARE transports get the higher bonus first via
# _transport_target_bonus, and this bonus stacks on top for the loaded
# Raider case (which is exactly the alpha-strike-disrupt case we want
# to reinforce). For Ravagers / Voidravens (NON-transport flyers), this
# is the only bonus, and 1.5x is enough to overtake the default
# current_health-min pick against a tougher non-skimmer alternative
# without overshooting into "always shoot the Ravager regardless".
#
# This is a PLAY HEURISTIC, not a 10e rule, so it lives in the AI layer
# and has no rule_citations entry. The "rule" is the universal
# tournament play-pattern of bracketing the alpha-strike chassis on
# round 1, not any codex text.
_DRUKHARI_FRAGILE_FLYER_BONUS: float = 1.5


def _drukhari_fragile_flyer_bonus(defender) -> float:
    """Return a target-priority multiplier when `defender` is a fragile
    Drukhari FLY VEHICLE (Ravager, Voidraven, Razorwing, etc.).

    Defender-faction-gated AND keyword-gated AND defensive-stat-gated so
    the bonus never lights up on a Custodes Caladius (FLY VEHICLE + 5++)
    or an Aeldari Wave Serpent (FLY VEHICLE + 5++) — only on the
    no-invuln / no-FNP Drukhari subset. Faction-neutral on the attacker
    side: every opposing army benefits from clearing the alpha-strike
    chassis before they bleed wounds across multiple rounds.

    - 1.5x when defender meets ALL gates.
    - 1.0x otherwise.

    Stacks multiplicatively with the existing screen / synapse / oath /
    transport chain; for loaded Raiders / Venoms the cumulative bonus
    is 1.5 * 2.2 = 3.3x, which is the right priority order (the loaded
    transport-flyer is the highest-value target on the board for a
    non-Drukhari shooter).
    """
    profile = getattr(defender, "profile", None)
    if profile is None:
        return 1.0
    if (profile.faction or "") != "Drukhari":
        return 1.0
    keywords = getattr(profile, "unit_keywords", ()) or ()
    if "VEHICLE" not in keywords or "FLY" not in keywords:
        return 1.0
    # Fragile gate: no invuln save (invuln_save >= 7 means "no invuln")
    # AND no Feel No Pain (fnp >= 7 means "no FNP"). Excludes any
    # Drukhari FLY VEHICLE that might carry defensive layers via
    # override / leader buff / detachment — though no such unit
    # currently exists in the catalogue, future-proofing the gate
    # keeps the bonus tightly scoped to the alpha-strike chassis
    # described in the rationale block.
    invuln = getattr(profile, "invuln_save", 7) or 7
    fnp = getattr(profile, "fnp", 7) or 7
    if invuln <= 6 or fnp <= 6:
        return 1.0
    return _DRUKHARI_FRAGILE_FLYER_BONUS


# ---------------------------------------------------------------------------
# Kiting counter-play — move (2): focus the EXPOSED melee threat (SWEG_KITE)
# ---------------------------------------------------------------------------
# The faithful kiting counter to melee over-shooters (World Eaters / elite
# combat armies): once a friendly unit Falls Back to un-stick from an enemy
# melee unit — move (1), already wired at the Fall Back branch in
# pick_move_destination — the rest of the army concentrates fire on that
# now-EXPOSED melee threat, shooting it down in the open before it can
# re-charge. This is a TARGET-PRIORITY bias ONLY: no extra shots and no
# re-shoot by the fallen-back unit (a unit that Fell Back still cannot shoot
# per 10e core, so this is faithful — NOT the "fall back and re-shoot" knob
# the watchdog flagged). Even-handed: every army applies it, so it favours
# shooting armies over melee armies exactly as real tournament counter-play
# does. Stage-1 AI play-style heuristic (target selection, not a rule — no
# citation, same class as the screen / synapse / oath biases above).
#
# Env-gated default-OFF (SWEG_KITE): when OFF, returns 1.0 so the ranged
# target picker's denominator is byte-identical (x1.0 is the exact float
# identity). This is the wave-153 bounded probe of whether the over-side has
# any faithful counter-play headroom left.
_KITE_TARGET_BONUS: float = 1.5


def _kite_enabled() -> bool:
    return __import__("os").environ.get("SWEG_KITE") == "1"


def _kite_target_bonus(defender, attacker_army) -> float:
    """Return ``_KITE_TARGET_BONUS`` when ``defender`` is an EXPOSED enemy
    melee-class unit — a melee threat (melee damage-per-activation >= ranged)
    that is NOT currently within Engagement Range of any unit of the shooting
    army (so it sits in the open after move (1)'s Fall Back, rather than
    tarpitting a friendly). 1.0 otherwise, and always 1.0 when SWEG_KITE is
    unset (OFF path byte-identical)."""
    if not _kite_enabled():
        return 1.0
    profile = getattr(defender, "profile", None)
    if profile is None or not _is_melee_class(profile):
        return 1.0
    for f in attacker_army.alive_units:
        if _dist(f.position, defender.position) <= _ENGAGEMENT_RANGE:
            return 1.0  # still tarpitted by a friendly — move (1) un-sticks first
    return _KITE_TARGET_BONUS


# ---------------------------------------------------------------------------
# AI-1 — Orks tarpit-engage charge heuristic (AI play-style, NOT a rule)
# ---------------------------------------------------------------------------
# Real tournament Orks (volume melee, low damage-per-attack, abundant bodies)
# don't always charge the highest damage-per-attack target. Against Custodes,
# Knights or Vehicles they often charge to TIE THE TARGET UP — denying the
# enemy their Movement and Objective Control phases — even though Boyz
# won't actually kill the Wardens / Knight / Repulsor in the combat. The
# "expected value" of the charge is in the lock-down, not the wounds.
#
# This is a PLAY HEURISTIC, not a 10e rule, so it lives in the AI layer
# (`code/strategy.py`) and has no rule_citations entry. Cited motivation:
# Goonhammer tournament reports on Orks meta playstyle (May 2026).
#
# Gate (mandatory): only fires when `attacker.profile.faction == "Orks"`.
# Other factions' tarpit calculus is different and will be addressed in
# separate AI commits (World Eaters trade differently; Tyranids run synapse
# anchors; Daemons play deep-strike anvils).
#
# Trigger: an Orks unit looking at a candidate target whose expected wounds
# inflicted this round is < 25% of the target's current_health (i.e. the
# top-DPA pick is a "won't-crack" charge anyway) AND a tarpit-candidate
# alternative is within charge range — bias the score of the tarpit
# candidate up by a flat multiplier so it can overtake the nominal top
# pick on the existing scoring function. The heuristic NEVER replaces the
# existing kill_potential / threat_back math; it just biases it.
_ORK_TARPIT_BONUS: float = 1.6
_ORK_LOW_DAMAGE_FRAC: float = 0.25  # "won't actually kill" threshold

# AI-2C — Chaos Daemons deep-strike tarpit-engage bias.
_DAEMONS_TARPIT_BONUS: float = 1.4
_DAEMONS_DEEPSTRIKE_NAMES = frozenset({
    "Bloodletters", "Plaguebearers", "Daemonettes", "Pink Horrors",
})

# AI-3 — elite-army objective-priority play-style constants. Custodes /
# Drukhari / Votann refuse damage trades that don't translate to position.
# Each gate is faction-pure and stacks multiplicatively with the existing
# target-score chain.
_CUSTODES_HORDE_TARGET_PENALTY: float = 0.4
_DRUKHARI_ENGAGE_BONUS: float = 0.5
_DRUKHARI_DECISIVE_FRAC: float = 0.5
# DRK-DIAG-12 — list-integrity gate constants.
# Real Skysplinter pilots protect depleted squads: a Wyches / Incubi /
# Mandrakes unit below half starting strength is too fragile to absorb
# a full counter-fight after charging — real players fall back or hold
# position rather than burning the remaining models on a trade. The
# sim's greedy melee AI charges every round regardless of squad health.
# 0.5x multiplier applied in BOTH the MOVE planner (_melee_target_score)
# and the CHARGE planner (pick_charge_target) when the Drukhari unit is
# INFANTRY (not VEHICLE/MONSTER/CHARACTER) and its current_health is below
# 50% of profile.health. Stacks multiplicatively with the existing
# _drukhari_decisive_strike_penalty so a depleted unit facing a non-
# decisive target gets 0.5 * 0.5 = 0.25x — strongly discouraging the
# charge while leaving a small residual for rare forced situations.
# This is a PLAY HEURISTIC, not a 10e rule, so it lives in the AI layer
# and has no rule_citations entry.
_DRUKHARI_LIST_INTEGRITY_PENALTY: float = 0.5
_DRUKHARI_LIST_INTEGRITY_HP_FRAC: float = 0.5
_VOTANN_FALLBACK_FACTIONS: tuple = ("Leagues of Votann",)

# ---------------------------------------------------------------------------
# AI-5 — Knight melee commitment heuristic (AI play-style, NOT a rule)
# ---------------------------------------------------------------------------
# Real tournament Imperial Knights / Chaos Knights players commit melee-focused
# chassis aggressively into combat even at attrition cost. A Knight Gallant or
# Knight Rampager is a pure melee monster — holding it at range forfeits most
# of its damage output. The sim's generic AI, which scores targets on expected
# kill-potential vs threat-back, treats Knights like heavy vehicles and keeps
# them at range shooting. This produces the wrong play pattern: the Reaper
# chainsword / Thunderstrike gauntlet / Balemace never fires because the Knight
# never charges.
#
# The fix: a 2.5x attacker-side score multiplier applied in BOTH the MOVE
# planner (_melee_target_score, controls which enemy the Knight closes on) and
# the CHARGE planner (pick_charge_target, controls whether it charges this
# activation) whenever the attacker is a melee-focused Knight chassis.
#
# Gate (attacker-only, mandatory): fires when ALL hold:
#   - attacker.profile.faction in ("Imperial Knights", "Chaos Knights")
#   - attacker.profile.extra_melee_profiles is not None and non-empty
#     (this is the natural flag for melee-focused chassis — Gallant, Rampager,
#     Despoiler, Abominant, Karnivore all have it set; Castellan, Valiant,
#     Crusader, Tyrant do NOT, so ranged-platform Knights are automatically
#     excluded without needing a hard-coded name list)
#
# Explicitly excluded (no extra_melee_profiles in overrides.json):
#   - Knight Castellan, Knight Crusader, Knight Valiant (ranged platforms)
#   - Knight Tyrant, War Dog Stalker, War Dog Brigand (ranged War Dogs)
#
# This is a PLAY HEURISTIC, not a 10e rule, so it lives in the AI layer and
# has no rule_citations entry. Motivation: Goonhammer meta reports on Knights
# melee play-pattern (May 2026 tournament data).
_KNIGHT_MELEE_COMMIT_FACTIONS: frozenset = frozenset({
    "Imperial Knights",
    "Chaos Knights",
})
_KNIGHT_MELEE_COMMIT_BONUS: float = 2.5


def _knight_melee_commitment_bonus(attacker) -> float:
    """Return 2.5x when `attacker` is a melee-focused Imperial Knights or
    Chaos Knights chassis (detected via non-empty extra_melee_profiles).

    - 2.5x when attacker.profile.faction is in _KNIGHT_MELEE_COMMIT_FACTIONS
      AND attacker.profile.extra_melee_profiles is truthy.
    - 1.0x otherwise.

    Applied as an attacker-side multiplier in BOTH _melee_target_score (MOVE
    planner) and pick_charge_target (CHARGE planner) so the Knight both closes
    on AND charges melee targets rather than staying at range.

    Ranged-platform Knights (Castellan, Valiant, Crusader, Tyrant, ranged War
    Dogs) do not have extra_melee_profiles populated so they are never boosted.
    """
    profile = getattr(attacker, "profile", None)
    if profile is None:
        return 1.0
    if (profile.faction or "") not in _KNIGHT_MELEE_COMMIT_FACTIONS:
        return 1.0
    emp = getattr(profile, "extra_melee_profiles", None)
    if not emp:
        return 1.0
    return _KNIGHT_MELEE_COMMIT_BONUS


def _is_tarpit_candidate(defender) -> bool:
    """True when `defender` is a mobile elite worth locking down.

    Criteria (all must hold):
      - profile.move >= 6                                    (mobile)
      - profile.health >= 3                                  (multi-W per model)
      - objective-relevant: oc >= 1 OR has CHARACTER /
        MONSTER / VEHICLE in unit_keywords

    Real 10e: a 3+W mobile unit is either a CHARACTER, an elite squad
    (Wardens, Terminators) or a MONSTER/VEHICLE. Tying any of those up
    costs the opponent their best mover.
    """
    profile = getattr(defender, "profile", None)
    if profile is None:
        return False
    move = getattr(profile, "move", 0) or 0
    if move < 6:
        return False
    health = getattr(profile, "health", 0) or 0
    if health < 3:
        return False
    oc = getattr(profile, "oc", 0) or 0
    kw = getattr(profile, "unit_keywords", ()) or ()
    if oc >= 1:
        return True
    if "CHARACTER" in kw or "MONSTER" in kw or "VEHICLE" in kw:
        return True
    return False


def _ork_tarpit_charge_bonus(attacker, defender) -> float:
    """Return 1.6x when:
      - attacker is an Orks unit, AND
      - this Ork unit's expected wounds inflicted on `defender` this round
        is < 25% of `defender.current_health` (i.e. the charge won't kill),
        AND
      - defender is a tarpit candidate (mobile + multi-W + objective-relevant).

    Else 1.0. Stacks multiplicatively with `_gunline_charge_bonus`,
    `_support_target_bonus`, `_screen_target_bonus`, `_synapse_target_bonus`.

    The won't-kill gate is the key — we only override the highest-DPA
    pick when the Ork unit ISN'T going to crack it anyway. If a Mega
    Nob mob can actually delete the Repulsor, the existing scoring
    keeps that pick; the bias only fires for the Boyz-into-Wardens
    case the user wants to model.
    """
    a_profile = getattr(attacker, "profile", None)
    d_profile = getattr(defender, "profile", None)
    if a_profile is None or d_profile is None:
        return 1.0
    if a_profile.faction != "Orks":
        return 1.0
    if not _is_tarpit_candidate(defender):
        return 1.0
    expected_wounds = _kill_potential_wounds(a_profile, d_profile)
    current_hp = max(1.0, getattr(defender, "current_health", 1.0))
    if expected_wounds >= _ORK_LOW_DAMAGE_FRAC * current_hp:
        return 1.0  # we can actually crack it — let normal scoring decide
    return _ORK_TARPIT_BONUS


# AI-2C — Chaos Daemons deep-strike tarpit bonus constants.
_DAEMONS_TARPIT_BONUS: float = 1.4
_DAEMONS_DEEPSTRIKE_NAMES = frozenset({
    "Bloodletters", "Plaguebearers", "Daemonettes", "Pink Horrors",
})


# AI-2A — World Eaters glory-driven charge bias. WE's play-style is
# fundamentally different from Orks: Berzerkers / Eightbound / Angron etc.
# charge for KHORNE GLORY, not because they can't crack the target. Real meta
# WE Berzerkers DON'T sit and shoot — they close into melee with anything
# breathing. AI-2A bias fires on EVERY enemy in charge range for a WE
# melee-class attacker, regardless of kill potential, because the in-game
# decision is always "charge". Smaller multiplier than Orks (1.5 vs 1.6)
# because WE want to KILL not just tarpit — the bias just outweighs gunline /
# screen / etc. picks slightly without overriding "kill the buff character"
# math entirely. AI heuristic; no rule citation (Khorne berzerker fluff is
# play-style, not a printed rule).
_WE_GLORY_BONUS: float = 1.5


def _is_melee_class(attacker_profile) -> bool:
    """True when `attacker_profile`'s primary weapon profile is melee.

    Detection: melee-DPA (attacks * hit_p * dmg/shot) >= ranged-DPA on the
    same stat-line. Berzerkers / Eightbound / Angron / Daemon Prince /
    Lord Invocatus all have minimal ranged output and heavy melee, so they
    pass; a hypothetical WE shooting unit (none exist in 10e but the gate
    is robust to overrides) would fail.
    """
    if attacker_profile is None:
        return False
    melee_dpa = (attacker_profile.melee_attacks
                 * attacker_profile.melee_hit_probability
                 * (attacker_profile.melee_damage_per_shot or 1.0))
    ranged_dpa = (attacker_profile.attacks
                  * attacker_profile.hit_probability
                  * (attacker_profile.weapon_damage_per_shot or 0.0))
    return melee_dpa >= ranged_dpa


def _we_glory_charge_bonus(attacker, defender) -> float:
    """Return 1.5x when:
      - attacker is a World Eaters unit, AND
      - attacker is melee-class (primary profile is melee per
        `_is_melee_class`).

    Else 1.0. Unlike `_ork_tarpit_charge_bonus`, this fires on ANY
    enemy — WE always charge, kill potential is irrelevant to the decision.
    Stacks multiplicatively with all other bonuses.
    """
    a_profile = getattr(attacker, "profile", None)
    if a_profile is None:
        return 1.0
    if a_profile.faction != "World Eaters":
        return 1.0
    if not _is_melee_class(a_profile):
        return 1.0
    return _WE_GLORY_BONUS


# ---------------------------------------------------------------------------
# AI-2B — Tyranids Synapse-anchored tarpit-engage charge heuristic (AI play-
# style, NOT a rule). Companion to AI-1 (Orks tarpit) and AI-2A (WE glory).
# ---------------------------------------------------------------------------
# Real Tyranid play distinguishes "lesser bugs" (Hormagaunts, Termagants,
# Genestealers, Tyranid Warriors) from "big bugs" (Hive Tyrant, Tervigon,
# Norn Emissary). The lesser bugs are battleshock-fragile — they only press
# the aggressive tarpit-engage charge when WITHIN Synapse range of a friendly
# SYNAPSE-keyword model. This is a PLAY HEURISTIC, not a 10e rule (the
# rule-side Synapse Imperative auto-pass already lives in `code/simulator.py`
# `_resolve_battleshock`). No rule_citations entry.
_TYRANID_SYNAPSE_TARPIT_BONUS: float = 1.5
_SYNAPSE_RANGE_INCHES: float = 6.0


def _is_in_synapse_range(attacker) -> bool:
    """True when `attacker` is a Tyranid unit within 6" of a DIFFERENT friendly
    SYNAPSE-keyword model in the same army.

    Mirrors the Synapse Imperative check in `simulator._resolve_battleshock`
    — same 6" radius, same "different uid" exclusion so a SYNAPSE unit isn't
    counted as its own anchor. Returns False if the attacker has no
    `army_ref` (synthetic test profile) or no friendly SYNAPSE models are
    alive.
    """
    a_profile = getattr(attacker, "profile", None)
    if a_profile is None or a_profile.faction != "Tyranids":
        return False
    army = getattr(attacker, "army_ref", None)
    if army is None:
        return False
    a_uid = getattr(attacker, "uid", None)
    for s in army.alive_units:
        if s.uid == a_uid:
            continue
        s_kw = getattr(s.profile, "unit_keywords", ()) or ()
        if "SYNAPSE" not in s_kw:
            continue
        if _dist(attacker.position, s.position) <= _SYNAPSE_RANGE_INCHES:
            return True
    return False


def _tyranids_synapse_tarpit_bonus(attacker, defender) -> float:
    """Return 1.5x when:
      - attacker is a Tyranids unit, AND
      - attacker is NOT itself a SYNAPSE source, AND
      - attacker IS within 6" of a friendly SYNAPSE model, AND
      - defender is a tarpit candidate (mobile + multi-W + objective-relevant).
    Else 1.0.
    """
    a_profile = getattr(attacker, "profile", None)
    if a_profile is None or a_profile.faction != "Tyranids":
        return 1.0
    a_kw = getattr(a_profile, "unit_keywords", ()) or ()
    if "SYNAPSE" in a_kw:
        return 1.0  # big bug — doesn't need the tarpit bias
    if not _is_tarpit_candidate(defender):
        return 1.0
    if not _is_in_synapse_range(attacker):
        return 1.0  # orphaned lesser bug — play cautiously, no override
    return _TYRANID_SYNAPSE_TARPIT_BONUS


def _daemons_deepstrike_tarpit_bonus(attacker, defender) -> float:
    """Return 1.4x when:
      - attacker is a Chaos Daemons unit, AND
      - attacker is one of the canonical deep-strike-arrival Daemon squads
        (Bloodletters / Plaguebearers / Daemonettes / Pink Horrors), AND
      - defender is a tarpit candidate.

    Else 1.0. No won't-crack gate (smaller 1.4x multiplier prevents
    overriding kill picks). Faction+class gate proxies for deep-strike
    state (canonical 10e tournament arrival roster).
    """
    a_profile = getattr(attacker, "profile", None)
    d_profile = getattr(defender, "profile", None)
    if a_profile is None or d_profile is None:
        return 1.0
    if a_profile.faction != "Chaos Daemons":
        return 1.0
    if getattr(a_profile, "name", "") not in _DAEMONS_DEEPSTRIKE_NAMES:
        return 1.0
    if not _is_tarpit_candidate(defender):
        return 1.0
    return _DAEMONS_TARPIT_BONUS


def _custodes_horde_penalty(attacker, defender) -> float:
    """Return 0.4x when attacker is Custodes and defender's role is HORDE.

    Real top Custodes lists hold the centre and never grind into Boyz /
    Termagant / Cultist chaff. Knock the AI's chase-the-horde bias down so
    Wardens/Custodian Guard prefer claiming objectives over chasing low-OC.
    """
    a_profile = getattr(attacker, "profile", None)
    d_profile = getattr(defender, "profile", None)
    if a_profile is None or d_profile is None:
        return 1.0
    if a_profile.faction != "Adeptus Custodes":
        return 1.0
    if classify(d_profile) != "HORDE":
        return 1.0
    return _CUSTODES_HORDE_TARGET_PENALTY


def _drukhari_decisive_strike_penalty(attacker, defender) -> float:
    """Return 0.5x when attacker is Drukhari/Ynnari AND expected wounds < 50%
    of defender.current_health (engagement isn't decisive). Models
    alpha-strike-then-fade play — Wyches/Incubi only engage when they can
    delete the target.
    """
    a_profile = getattr(attacker, "profile", None)
    d_profile = getattr(defender, "profile", None)
    if a_profile is None or d_profile is None:
        return 1.0
    if a_profile.faction not in ("Drukhari", "Ynnari"):
        return 1.0
    expected_wounds = _kill_potential_wounds(a_profile, d_profile)
    current_hp = max(1.0, getattr(defender, "current_health", 1.0))
    if expected_wounds >= _DRUKHARI_DECISIVE_FRAC * current_hp:
        return 1.0
    return _DRUKHARI_ENGAGE_BONUS


def _drukhari_depleted_unit_penalty(attacker) -> float:
    """Return _DRUKHARI_LIST_INTEGRITY_PENALTY (0.5x) when `attacker` is a
    Drukhari/Ynnari INFANTRY unit below half its starting health.

    Models real-tournament list-integrity play: Skysplinter pilots protect
    depleted Wyches / Incubi / Mandrakes rather than charging and losing the
    remaining models to a counter-fight. A unit at full strength charges
    freely; one at 40% starting health is pulled back.

    Gates (all required):
      - attacker.profile.faction in ("Drukhari", "Ynnari")
      - INFANTRY in attacker.profile.unit_keywords  (no VEHICLE/MONSTER/CHARACTER)
      - attacker.current_health < _DRUKHARI_LIST_INTEGRITY_HP_FRAC *
        attacker.profile.health

    Returns 1.0 otherwise. Applied in BOTH _melee_target_score (move planner)
    and pick_charge_target (charge planner) so the brake is consistent.

    This is a PLAY HEURISTIC, not a 10e rule — no rule_citations entry.
    DRK-DIAG-12.
    """
    a_profile = getattr(attacker, "profile", None)
    if a_profile is None:
        return 1.0
    if a_profile.faction not in ("Drukhari", "Ynnari"):
        return 1.0
    kw = getattr(a_profile, "unit_keywords", ()) or ()
    if "INFANTRY" not in kw:
        return 1.0
    # Exclude CHARACTER — leaders are often single-model and don't benefit
    # from the same herd-the-fragile logic.
    if "CHARACTER" in kw:
        return 1.0
    current_hp = getattr(attacker, "current_health", None)
    start_hp = getattr(a_profile, "health", None)
    if current_hp is None or start_hp is None or start_hp <= 0:
        return 1.0
    if current_hp < _DRUKHARI_LIST_INTEGRITY_HP_FRAC * start_hp:
        return _DRUKHARI_LIST_INTEGRITY_PENALTY
    return 1.0


def _score_profile(unit):
    """Per-model AI-isolation (per-model loadouts Stage 5). OFFENSIVE tactical scoring
    reads the SQUAD AGGREGATE profile, not a single model's narrowed per-model loadout.
    Under SWEG_PERMODEL each model-Unit carries only its own weapons (Stage 3); without
    this isolation the AI would value a whole squad by one model's gun and mis-target /
    mis-charge (the measured Daemons-crater confound). `squad_profile_ref` is stamped
    with the aggregate by Army.add_squad's per-model path; legacy / collision-OFF units
    leave it None, so this returns `unit.profile` and AI behaviour is byte-identical."""
    return getattr(unit, "squad_profile_ref", None) or unit.profile


def _melee_target_score(attacker, defender) -> float:
    """How attractive `defender` is as a melee target for `attacker`.

    Same shape as pick_charge_target's scoring but distance-independent —
    used by the MOVE planner to pick which enemy to close on, before we
    know whether a charge will be in range. Real tournament play: melee
    bricks pick fragile gunline targets (T'au Fire Warriors, Devastators,
    snipers) over near-but-tough enemies with strong saves.
    """
    p = _score_profile(attacker)
    tp = _score_profile(defender)

    a_melee_dpa = (p.melee_attacks * p.melee_hit_probability
                   * (p.melee_damage_per_shot or 1.0))
    kill_potential = a_melee_dpa / _durability(
        tp, defender.current_health, p.melee_ap, defender_unit=defender)

    # Threat back: their melee output divided by OUR effective durability
    # against THEIR AP. Same machinery — an opponent with AP-3 reads as
    # more dangerous to a Marine than the raw DPA suggests.
    threat_back = (
        tp.melee_attacks * tp.melee_hit_probability
        * (tp.melee_damage_per_shot or 1.0)
    ) / _durability(p, attacker.current_health, tp.melee_ap,
                    defender_unit=attacker)

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
    # S7 (#168): synapse-source bonus biases non-Tyranid attackers toward
    # killing the Hive Tyrant / Tervigon BEFORE the chaff so the swarm
    # loses its Synapse Imperative auto-pass shelter.
    return (base
            * _gunline_charge_bonus(p, tp)
            * _support_target_bonus(defender)
            * _screen_target_bonus(defender)
            * _synapse_target_bonus(attacker, defender)
            * _ork_tarpit_charge_bonus(attacker, defender)
            * _we_glory_charge_bonus(attacker, defender)
            * _tyranids_synapse_tarpit_bonus(attacker, defender)
            * _daemons_deepstrike_tarpit_bonus(attacker, defender)
            # AI-3 — elite over-performer debuffs.
            * _custodes_horde_penalty(attacker, defender)
            * _drukhari_decisive_strike_penalty(attacker, defender)
            # DRK-DIAG-12 — list-integrity gate: depleted Drukhari
            # INFANTRY squads (< 50% health) are discouraged from
            # committing to melee engagements.
            * _drukhari_depleted_unit_penalty(attacker)
            # AI-5 — melee-focused Knight chassis (Gallant, Rampager,
            # Despoiler, Abominant, Karnivore) strongly prefer committing
            # to melee over staying at range.
            * _knight_melee_commitment_bonus(attacker))


def _kill_potential_wounds(attacker_profile, target_profile) -> float:
    """Expected wounds inflicted by one round of melee from `attacker_profile`
    against `target_profile`. Pure stats — no faction conditionals.

    Composes universal 10e math:
        DPA          = melee_attacks * melee_hit_probability
        wound_prob   = standard S-vs-T table (`wound_probability`)
        save_fail    = 1 - best(armour_after_AP, invuln)
        damage/shot  = melee_damage_per_shot (defaults to 1)

    Used by `pick_charge_target` to detect "won't-crack" charges (#C2,
    iter 2). See `docs/AUTO_LOOP_ITER1_CLUSTER_C.md` fix #2.
    """
    dpa = attacker_profile.melee_attacks * attacker_profile.melee_hit_probability
    wound_p = wound_probability(
        attacker_profile.melee_strength, target_profile.toughness
    )
    save_pass = save_probability(target_profile.save, attacker_profile.melee_ap)
    invuln_pass = (
        save_probability(target_profile.invuln_save)
        if target_profile.invuln_save <= 6 else 0.0
    )
    save_fail = max(0.0, 1.0 - max(save_pass, invuln_pass))
    dmg = attacker_profile.melee_damage_per_shot or 1.0
    return dpa * wound_p * save_fail * dmg


# #C2 (iter 2) — Charge "won't-crack" penalty constants. A charge whose
# expected wounds inflicted is below WONT_CRACK_HP_FRAC of the target's
# remaining health is downweighted by WONT_CRACK_PENALTY. Faction-neutral:
# applies on the universal DPA-vs-HP ratio so Knights, Wraithlords, Tyrants
# and Custodian Guard are all gated identically.
_WONT_CRACK_HP_FRAC = 0.20
_WONT_CRACK_PENALTY = 0.3

# Anti-Knight stack component 2 (`SWEG_TARPIT`, default OFF) — general tarpit
# charge valuation. A charge that CANNOT crack a durable, high-ranged-threat
# brick (a Knight) is normally suppressed by the won't-crack penalty. But an
# EXPENDABLE (chaff) attacker pinning such a target is a real-play tarpit: an
# engaged target with Big Guns Never Tire may shoot only the unit it is tied up
# with at -1, or Fall Back and lose its shooting entirely (the sim already
# resolves this faithfully in `_do_shoot`). So the pin DENIES the target's
# ranged output to the rest of the army — value the charge by that denied
# output, not by the kill it cannot make. Even-handed: universal points +
# toughness, no faction branch (the existing per-faction tarpit bonuses are a
# separate, narrower play-style layer). AI heuristic exploiting the already-cited
# Big Guns Never Tire mechanic — no new rule_citation (same class as the Ork /
# World Eaters tarpit bonuses).
_TARPIT_MIN_TOUGHNESS = 9     # durable brick worth pinning (Knights T12, big vehicles T9-14)
_TARPIT_MIN_HP = 18.0        # or a large wound pool (a multi-wound vehicle/monster)
_TARPIT_PIN_WEIGHT = 0.6     # weight on the denied ranged output when valuing a pin


def _tarpit_enabled() -> bool:
    return __import__("os").environ.get("SWEG_TARPIT", "0") == "1"


def _is_tarpit_charge(attacker, target_unit, target_profile) -> bool:
    """A pin charge: an EXPENDABLE (chaff, non-CHARACTER) attacker into a DURABLE
    target. Even-handed — no faction branch; uses universal points + toughness.
    Called only inside the won't-crack branch, which already establishes the
    attacker cannot crack the target. The pin's value scales with the target's
    ranged output (computed at the call site), so a low-ranged melee brick yields
    a small pin value and is not tarpitted (correct — a melee Knight wants melee)."""
    if not _is_chaff_unit(attacker):
        return False
    tp = target_profile
    return (tp.toughness or 0) >= _TARPIT_MIN_TOUGHNESS or \
        (target_unit.current_health or 0.0) >= _TARPIT_MIN_HP


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

    p = _score_profile(attacker)
    # Attacker's per-activation melee output.
    a_melee_dpa = (p.melee_attacks * p.melee_hit_probability
                   * (p.melee_damage_per_shot or 1.0))

    candidates = []
    for e in alive_enemies:
        d = _dist(attacker.position, e.position)
        if d > 12.0 or d <= 1.0:
            continue   # out of charge range / already engaged
        tp = _score_profile(e)

        kill_potential = a_melee_dpa / _durability(
            tp, e.current_health, p.melee_ap, defender_unit=e)

        threat_against = (
            tp.melee_attacks * tp.melee_hit_probability
            * (tp.melee_damage_per_shot or 1.0)
        ) / _durability(p, attacker.current_health, tp.melee_ap,
                        defender_unit=attacker)

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
        # S7 (#168) — synapse-source bonus: bias non-Tyranid attackers
        # into the Hive Tyrant / Tervigon to revoke Synapse Imperative.
        synapse_bonus = _synapse_target_bonus(attacker, e)
        # AI-1 — Orks tarpit-engage bonus: when a low-damage Ork unit
        # can't crack the top-DPA pick, bias the score of mobile elite
        # alternatives so the AI charges to LOCK them out of Movement /
        # Objective Control instead. Faction-gated to Orks only — other
        # factions' tarpit play-style differs and is handled separately.
        tarpit_bonus = _ork_tarpit_charge_bonus(attacker, e)
        # AI-2A WE / AI-2B Tyranids / AI-2C Daemons tarpit bonuses.
        we_glory_bonus = _we_glory_charge_bonus(attacker, e)
        tyranids_tarpit_bonus = _tyranids_synapse_tarpit_bonus(attacker, e)
        daemons_tarpit_bonus = _daemons_deepstrike_tarpit_bonus(attacker, e)
        # AI-3 — Drukhari decisive-strike charge penalty. Symmetry fix
        # (DRK-DIAG-6, 2026-05-23): the penalty already gates the MOVE
        # planner (`_melee_target_score`) so Wyches/Incubi only CLOSE on
        # targets they can delete, but the CHARGE planner was unbraked
        # and re-engaged those same non-decisive targets once in range,
        # producing the alpha-strike-anyway play-pattern the bias was
        # meant to eliminate. Apply it here too so the brake is
        # consistent across move + charge. Same 50% expected-wounds
        # threshold, same 0.5x multiplier, same Drukhari/Ynnari gate.
        drk_decisive_penalty = _drukhari_decisive_strike_penalty(attacker, e)
        # DRK-DIAG-12 — list-integrity gate: depleted Drukhari INFANTRY
        # squads (< 50% starting health) are discouraged from charging.
        # Mirrors the _melee_target_score gate so the brake is symmetric.
        drk_integrity_penalty = _drukhari_depleted_unit_penalty(attacker)
        # AI-5 — melee-focused Knight chassis (Gallant, Rampager, Despoiler,
        # Abominant, Karnivore) strongly prefer committing to melee. The MOVE
        # planner gates use the same bonus so both close-on and charge
        # decisions are aligned. Ranged Knights (Castellan, Valiant, Crusader,
        # Tyrant) are automatically excluded because they lack extra_melee_profiles.
        knight_melee_bonus = _knight_melee_commitment_bonus(attacker)
        score = (((kill_potential + 0.5 * ranged_value)
                  / (1.0 + threat_against))
                 * charge_p * gunline_bonus * support_bonus
                 * screen_bonus * synapse_bonus * tarpit_bonus
                 * we_glory_bonus * tyranids_tarpit_bonus
                 * daemons_tarpit_bonus
                 * drk_decisive_penalty
                 * drk_integrity_penalty
                 * knight_melee_bonus)
        # #C2 (iter 2) — "won't-crack" penalty. If expected wounds inflicted
        # this round is below 20% of target's current HP, heavily downweight
        # the charge. Stops light melee attacking T8+ bricks they can't dent
        # before counter-fight reverses on them. Faction-neutral: uses only
        # universal stats (S/T wound table, AP-vs-save, DPA). 27.8% of
        # charges in the iter-1 audit landed on un-crackable targets.
        expected_wounds = _kill_potential_wounds(p, tp)
        if expected_wounds < _WONT_CRACK_HP_FRAC * max(1.0, e.current_health):
            if _tarpit_enabled() and _is_tarpit_charge(attacker, e, tp):
                # PIN charge (SWEG_TARPIT): an expendable unit tying up a durable
                # gun platform. Do NOT suppress — value the pin by the enemy
                # ranged output it DENIES (Big Guns Never Tire / engaged-can't-
                # shoot), added instead of the kill it cannot make. A melee brick
                # has little ranged_value, so it yields a small pin value and is
                # not tarpitted. Even-handed; AI heuristic on the cited pin rule.
                score += _TARPIT_PIN_WEIGHT * ranged_value * charge_p
            else:
                score *= _WONT_CRACK_PENALTY
        candidates.append((score, d, e))

    if not candidates:
        return None, None
    _, dist, target = max(candidates, key=lambda x: x[0])
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
        # the simulator's strict `< _ENGAGEMENT_RANGE` (1.0") check actually flips to False.
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


def _is_chaff_unit(unit) -> bool:
    """AI-9 — return True when `unit` is cheap-chaff that should be willing
    to sacrifice itself to score Engage on All Fronts / Behind Enemy Lines.

    Detection: per-model points cost under `_CHAFF_MAX_POINTS_PER_MODEL`
    AND CHARACTER keyword absent. The points threshold catches the
    universal real-meta chaff set across factions — Gretchin (3.6),
    Termagants (6), Cultists (5), Cadians / Neophytes (6.5), Battle
    Sisters / Kroot / Strike Teams (7-10). It excludes Intercessors
    (20+), Custodian Guard, Plague Marines, anything that isn't sold
    cheap. The CHARACTER guard is belt-and-braces: a sub-15-pt character
    is essentially impossible but we'd never want to sacrifice one.

    AI heuristic only — no rule_citations entry required.
    """
    p = unit.profile
    pts = float(getattr(p, "points_cost", 0.0) or 0.0)
    if pts <= 0.0 or pts >= _CHAFF_MAX_POINTS_PER_MODEL:
        return False
    keywords = p.unit_keywords or ()
    if "CHARACTER" in keywords:
        return False
    return True


def _friendly_already_in_enemy_dz(
    friendly_alive, map_, own_is_army_a: bool,
) -> bool:
    """AI-9 — return True if any friendly unit is already standing in the
    opponent's deployment zone. Behind Enemy Lines awards a flat 4 VP for
    one or more units in the enemy DZ — once that's satisfied, additional
    chaff sacrifices don't add BEL VP, so don't waste another chaff on the
    same secondary."""
    if not friendly_alive:
        return False
    if own_is_army_a:
        # Army A's enemy DZ is high-y.
        enemy_dz_lo = map_.height - map_.deployment_width
        for u in friendly_alive:
            if u.position[1] >= enemy_dz_lo:
                return True
    else:
        # Army B's enemy DZ is low-y.
        enemy_dz_hi = map_.deployment_width
        for u in friendly_alive:
            if u.position[1] <= enemy_dz_hi:
                return True
    return False


def _sacrificial_chaff_target(
    unit, friendly, friendly_alive, map_, unit_on_obj_ids,
) -> Optional[Tuple[float, float]]:
    """AI-9 — return a deep-into-enemy-territory target position when `unit`
    is chaff and should sacrifice itself to score Engage on All Fronts /
    Behind Enemy Lines, or None if the heuristic shouldn't fire this
    activation.

    Gates (all must pass):
      (a) unit is chaff (per `_is_chaff_unit`).
      (b) unit is NOT currently holding a contested objective (no
          `unit_on_obj_ids` membership). Hold-flip protection ran earlier
          in `pick_move_intent`; if we're past that branch, the unit is
          either on no objective or on one whose loss isn't at stake.
          We additionally bail when the unit IS on any objective so the
          chaff doesn't abandon a marker it could've kept claiming.
      (c) the enemy DZ side is known (battle back-reference present).
      (d) no friendly is already in the enemy DZ — once BEL is locked,
          additional chaff doesn't add VP (Engage may still benefit but
          the marginal VP is lower; conservative gate avoids over-tagging).

    Target: a point inside the enemy DZ, biased toward the half-x line
    that the unit is currently nearest (so chaff on the LEFT half of the
    table heads to the LEFT half of the enemy DZ, etc.). Pushing chaff
    diagonally across the table just stretches the move into uselessness.
    """
    if not _is_chaff_unit(unit):
        return None
    # Don't abandon any objective — even uncontested objectives have OC
    # value to friendly army positioning.
    if unit_on_obj_ids:
        return None
    battle = getattr(friendly, "_battle_ref", None)
    if battle is None:
        return None
    own_is_army_a = friendly is battle.a
    if _friendly_already_in_enemy_dz(friendly_alive, map_, own_is_army_a):
        return None
    # Aim for the middle of the enemy DZ on the unit's current x-side,
    # so the move stays on the unit's flank.
    half_x = map_.width / 2.0
    ux, _ = unit.position
    if ux < half_x:
        target_x = map_.width * 0.25
    else:
        target_x = map_.width * 0.75
    if own_is_army_a:
        # Army A's enemy DZ is the high-y strip. Aim for its midpoint.
        target_y = map_.height - (map_.deployment_width * 0.5)
    else:
        # Army B's enemy DZ is the low-y strip. Aim for its midpoint.
        target_y = map_.deployment_width * 0.5
    return (target_x, target_y)


def _m4_enabled() -> bool:
    """Anti-Knight stack component 1 (`SWEG_M4`). Default OFF — the stack
    components stay gated for the isolation A/B until the decisive full-stack
    run; the user's package decision sets the final default."""
    return __import__("os").environ.get("SWEG_M4", "0") == "1"


# M4-α refinement (wave 131-132) — gunline-disruption exemption. The wave-130
# N=80 regression included Astra Militarum dragging its heavy-weapon models onto
# markers. The faithful fix (watchdog rails, wave 132): exempt a model from the
# cluster-pull ONLY when moving onto the marker would COST it a productive shot —
# i.e. it has meaningful ranged output AND an eligible target in range NOW, but
# the marker is OUT of firing range of every target so the move breaks the shot.
# A model that can HOLD-AND-SHOOT (a target in range from the marker too) is
# STILL pulled — it both holds the objective and keeps firing. A model with no
# eligible target, or no gun, or that can shoot from the marker, is pulled. This
# is NOT a blanket shooter exemption (that strands OC + kills the IK fix, the
# wave-131 over-broad version); it gates strictly on the move costing a shot.
# Even-handed (universal output + range, no faction branch; a 1-model Knight is
# unaffected); wrong-way-test clean (a real player keeps the lascannon firing and
# holds the marker with spare / chaff / hold-and-shoot bodies).
_M4_SHOOTER_MIN_OUTPUT = 2.0   # per-model ranged DPA above a lasgun trooper (~0.5), at a heavy weapon (~3+)


def _m4_move_costs_a_shot(unit, enemy_alive, marker_xy) -> bool:
    """True if `unit` is a productive shooter with an eligible target in range
    NOW that it would LOSE by moving onto `marker_xy` (no target in range from
    the marker). Hold-and-shoot (a target in range from the marker) returns
    False → the model is pulled."""
    p = unit.profile
    ranged_out = (p.attacks or 0) * (p.hit_probability or 0.0) \
        * (p.weapon_damage_per_shot or 0.0)
    if ranged_out < _M4_SHOOTER_MIN_OUTPUT:
        return False
    rng = p.range_inches or 0.0
    if rng <= 0.0:
        return False
    has_shot_now = any(_dist(unit.position, e.position) <= rng for e in enemy_alive)
    if not has_shot_now:
        return False
    has_shot_from_marker = any(_dist(marker_xy, e.position) <= rng for e in enemy_alive)
    return not has_shot_from_marker


def _m4_cluster_intent(unit, own_oc, enemy_alive, objectives, map_):
    """M4-α: a model carrying Objective Control that is NEAR a marker but not
    yet tight on it genuinely MOVES to a clustered on-marker slot inside the 3"
    scoring band, so a squad's surviving models mass on the objective and
    contribute their whole Objective Control (instead of stranding in the
    3"-6" band, the wave-93 spread). Returns `(slot, _CAPTURE_INTENT)` or None.

    Faithful positioning (A1), NOT a coherency-footprint counting shortcut
    (the forbidden A2): the model really moves; OC is still scored per-model
    within 3" by `_score_objectives`, unchanged. Even-handed — a 1-model unit
    (a Knight) targets the marker centre too and is unaffected because it
    already parks there; the benefit accrues to multi-model squads because they
    have bodies to mass, not via any faction or model-count branch. Cited
    `simulator.m4_squad_cluster`.
    """
    if own_oc <= 0:
        return None   # no Objective Control to contribute — leave it to shoot
    # Locked in melee: leave it to the existing fight / fall-back logic, do not
    # waltz onto a marker while in Engagement Range.
    for e in enemy_alive:
        if _dist(unit.position, e.position) <= _ENGAGEMENT_RANGE:
            return None
    PULL_IN = 6.0          # only tighten models already committed near a marker
    INNER = 1.5            # already tight on the centre — no move needed
    in_range = [
        (obj, _dist(unit.position, (obj.x, obj.y)))
        for obj in objectives
    ]
    in_range = [(o, d) for o, d in in_range if d <= PULL_IN]
    if not in_range:
        return None
    obj, d = min(in_range, key=lambda od: od[1])
    if d <= INNER:
        return None        # already massed on the marker
    # Gunline-disruption exemption (wave 132, watchdog rails): exempt ONLY if the
    # move onto THIS marker would cost a productive shot — a hold-and-shoot model
    # (target in range from the marker too) is still pulled.
    if _m4_move_costs_a_shot(unit, enemy_alive, (obj.x, obj.y)):
        return None
    # A cover-rich point WITHIN the 3" scoring band of the marker centre, so the
    # model keeps both its Objective Control and (where available) a cover save.
    slot = _best_nearby_cover_point(map_, (obj.x, obj.y), search_radius=2.0)
    return slot, _CAPTURE_INTENT


def pick_move_intent(
    unit, friendly, enemy, map_, army_plan: Optional[str] = None,
    _phase_their_oc: Optional[Dict] = None,
    _phase_our_oc: Optional[Dict] = None,
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
    # ----- Wave 121: card-pursuit override (AI movement heuristic) -----------
    # Battle._assign_card_pursuit stamps pursue_target onto spare chaff units
    # BEFORE the move loop runs. If set, this is a high-priority pre-commitment:
    # the unit heads straight to the card's geographic goal and skips all other
    # intent logic. The override is transparent on the OFF path (pursue_target
    # initialises to None and is never written when the gate is off).
    _pt = getattr(unit, "pursue_target", None)
    if _pt is not None:
        return _pt, "pursue_card"

    role = classify(_score_profile(unit))   # Stage 5: a unit's OWN movement role is its
    own_oc = unit.profile.oc or 0            # SQUAD role, not one per-model model's gun

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
    objectives = map_.objectives

    # ----- 0. Fall Back (10e core) ------------------------------------------
    # A SHOOTY / HEAVY unit pinned inside enemy Engagement Range (1.5") loses
    # its activation — it can neither shoot nor (usefully) charge. The right
    # answer is to Fall Back: move up to M" away, eat a Desperate Escape test,
    # and resume shooting next round. Only run this when there's a viable
    # destination outside engagement of every enemy (otherwise the move would
    # just re-pin us). Cited as `simulator.fall_back` /
    # `simulator.desperate_escape`.
    # AI-3 — Votann fall-back extension: real Hearthkyn / Hernkyn gunlines
    # fall back from melee aggressively to keep bolters firing. Hearthkyn
    # classify as DUAL because they pack a few melee attacks, but the
    # damage trade is heavily ranged-biased, so the right move when pinned
    # is to break engagement. Extend the standard SHOOTY/HEAVY fall-back
    # eligibility to DUAL specifically for Votann attackers. Stage-1 AI
    # only — no rule citation, this is heuristic play-style modelling.
    _fall_back_eligible_roles = ("SHOOTY", "HEAVY")
    if unit.profile.faction in _VOTANN_FALLBACK_FACTIONS:
        _fall_back_eligible_roles = ("SHOOTY", "HEAVY", "DUAL")
    # AI-MISPILOT-FALLBACK (task #7): a melee-PRIMARY unit caught in
    # engagement should STAY and fight, not Fall Back. Falling Back forfeits
    # its main (melee) weapon system for the turn, and for non-TITANIC units
    # risks a Desperate Escape casualty — a competent player never Falls Back
    # a melee Knight (Gallant/Rampager), Carnifex, Hive Tyrant or Daemon
    # Prince. `_is_melee_class` (melee DPA >= ranged DPA) keeps pure ranged
    # platforms (Knight Castellan/Valiant, gunline tanks, Votann Hearthkyn)
    # eligible to break off and free their guns. Stage-1 AI heuristic only —
    # no rule citation, this is play-style modelling.
    if role in _fall_back_eligible_roles and not _is_melee_class(_score_profile(unit)):
        enemies = enemy.alive_units
        in_engagement = any(
            _dist(unit.position, e.position) <= _ENGAGEMENT_RANGE
            for e in enemies
        )
        if in_engagement and enemies:
            fall_back_pos = _pick_fall_back_destination(unit, enemies, map_)
            if fall_back_pos is not None:
                return fall_back_pos, _FALL_BACK_INTENT

    # Precompute OC sums for all objectives — _oc_on_objective iterates
    # alive_units per call. our_oc is always fresh (friendly units may have
    # moved earlier this phase). their_oc is stable for the entire move phase
    # (enemy units don't move during our phase) so the caller may pass a
    # precomputed dict via _phase_their_oc to avoid re-scanning enemy units
    # for every activation.
    friendly_alive = friendly.alive_units
    enemy_alive = enemy.alive_units
    # Perf: friendly OC on every objective is the move-phase's #1 hot spot
    # (O(friendly·obj) re-summed per activation). The caller (Battle move loop)
    # may pass `_phase_our_oc`, a dict it maintains INCREMENTALLY as units move
    # (full scan once per phase, then ±this-unit's OC on the markers it entered/
    # left after each move) — byte-identical to the per-call rescan, just faster.
    # Under SWEG_OC_CACHE_VERIFY the cache is asserted == a fresh scan every call
    # (proves byte-identical). None (legacy callers) → recompute as before.
    if _phase_our_oc is not None:
        _our_oc = _phase_our_oc
        if __import__("os").environ.get("SWEG_OC_CACHE_VERIFY"):
            _check = {id(obj): _oc_on_objective(friendly_alive, obj) for obj in objectives}
            assert _our_oc == _check, "OC cache drift: %r != %r" % (_our_oc, _check)
    else:
        _our_oc = {id(obj): _oc_on_objective(friendly_alive, obj) for obj in objectives}
    if _phase_their_oc is not None:
        _their_oc = _phase_their_oc
    else:
        _their_oc = {id(obj): _oc_on_objective(enemy_alive, obj) for obj in objectives}

    # ----- M4-α (anti-Knight stack, SWEG_M4) — mass Objective Control onto the
    # markers ------------------------------------------------------------------
    # A model carrying Objective Control that is near (but not tight on) a marker
    # genuinely moves into the 3" scoring band, so a squad packs its surviving
    # OC on the objective instead of stranding half of it in the 3"-6" ring (the
    # wave-93 spread). Even-handed; a 1-model unit is unaffected (already parks
    # on the centre). Runs ahead of the on-objective/HOLD logic so an edge-holder
    # tightens onto the marker rather than drifting to off-marker cover. OFF path
    # (gate unset) is byte-identical. Cited `simulator.m4_squad_cluster`.
    if _m4_enabled():
        _m4 = _m4_cluster_intent(unit, own_oc, enemy_alive, objectives, map_)
        if _m4 is not None:
            return _m4

    # ----- 1. Are we currently on an objective whose loss is at stake? -----
    # Track which objectives the unit currently occupies; reused by the
    # attrition branch below to avoid extra _oc_on_objective(exclude_uid)
    # calls — `our_oc_no_self = _our_oc[obj] - own_oc` is correct when the
    # unit is on the objective.
    unit_on_obj_ids: set = set()
    for obj in objectives:
        if _dist(unit.position, (obj.x, obj.y)) > obj.control_radius:
            continue
        unit_on_obj_ids.add(id(obj))
        # Count OC without us: total minus this unit's own OC.
        our_oc_no_self = _our_oc[id(obj)] - own_oc
        their_oc = _their_oc[id(obj)]
        # If leaving would flip control (or contest from win → tie), hold.
        # Snap to a cover-rich point near where we already stand so the
        # HOLD has a defensive benefit (HEAVY cover > OBSCURING > LIGHT).
        if own_oc > 0 and our_oc_no_self <= their_oc < our_oc_no_self + own_oc:
            hold_pos = _best_nearby_cover_point(map_, unit.position, search_radius=3.0)
            return hold_pos, _HOLD_INTENT

    # AI-9 — sacrificial chaff toward enemy backline for Engage / BEL VP.
    # Cheap chaff (per-model points cost under `_CHAFF_MAX_POINTS_PER_MODEL`)
    # that isn't holding an objective should push deep into the enemy
    # deployment zone to score the position-tracking secondaries, rather
    # than camping mid-board. Gated so a non-chaff unit (Intercessors,
    # Custodian Guard, Plague Marines) never sacrifices.
    chaff_target = _sacrificial_chaff_target(
        unit, friendly, friendly_alive, map_, unit_on_obj_ids,
    )
    if chaff_target is not None:
        return chaff_target, _SACRIFICIAL_INTENT

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
    # not just the nearest enemy. Exit here — MELEE units never consult
    # `objs` or `nearest_enemy`, so we skip both the objectives scoring
    # loop and the nearest-enemy scan entirely.
    if role == "MELEE" and enemy_alive:
        return max(
            enemy_alive,
            key=lambda e: _plan_target_score(_melee_target_score(unit, e), e),
        ).position, _ENGAGE_INTENT

    # ----- 2. Score every objective; pick the most worth visiting -----
    # S2: late-round contests dominate — multiply base value by `round_weight`
    # = 1 + 0.15*(round-1), so T5 stays-on-objective scores ~1.6x a T2 hold
    # and STEAL value at T5 (~5.6) easily beats sitting on a friendly-held
    # objective (~1.6). Round defaults to 1 when no Battle is active.
    objs = []
    for obj in objectives:
        a_oc = _our_oc[id(obj)]
        b_oc = _their_oc[id(obj)]
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
        # OC-CONTEST (#79, gated SWEG_CONTEST) — make the STEAL value WINNABLE +
        # bracket-aware so idle/spare bodies are redirected to flip an enemy-held
        # marker they can actually out-Control (a damaged Knight at effective OC 5
        # is winnable — the wave-191 bracket substrate), JUST-ENOUGH (don't pile
        # onto a marker we already win), and never chase an unwinnable contest.
        # The AFFORDABLE guard is the hold-check above: a marginal holder of a
        # friendly scoring marker returns _HOLD_INTENT and never reaches here, so
        # the contest only ever draws SPARE bodies — the balanced contest, NOT the
        # rejected wave-95 Stage-E flood. Default-OFF => byte-identical.
        if intent == _STEAL_INTENT and __import__("os").environ.get("SWEG_CONTEST", "1") != "0":
            _enemy_eff = _effective_oc_on_objective(enemy_alive, obj)
            _our_cur_eff = _effective_oc_on_objective(
                friendly_alive, obj, exclude_uid=unit.uid,
            )
            _unit_eff = _effective_oc_value(unit)
            if _our_cur_eff > _enemy_eff:
                value *= 0.6          # already winnably contesting — don't pile on
                _contest_kind = "already"
            elif _our_cur_eff + _unit_eff > _enemy_eff:
                value *= 1.7          # WINNABLE by committing THIS body — prioritise
                _contest_kind = "winnable"
            else:
                value *= 0.3          # unwinnable even with this body — don't chase
                _contest_kind = "unwinnable"
            # Per-faction instrument (#79 follow-up, gated SWEG_CONTEST_INSTR,
            # read-only): which factions the contest's winnable-boost fires for —
            # to tell whether the TSons/EC rise is the faithful body-army reward
            # (they hold spare bodies that genuinely out-Control an enemy marker)
            # or the contest over-helping them.
            if __import__("os").environ.get("SWEG_CONTEST_INSTR"):
                _fac = unit.profile.faction or "?"
                _d = CONTEST_STATS.setdefault(
                    _fac, {"winnable": 0, "unwinnable": 0, "already": 0},
                )
                _d[_contest_kind] += 1
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
            # Subtract this unit's OC only when it is currently on the
            # objective (tracked by the hold-check loop above). Avoids an
            # extra _oc_on_objective(exclude_uid=...) call per objective.
            our_count = _our_oc[id(obj)] - (own_oc if id(obj) in unit_on_obj_ids else 0)
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

    # Q11 positional re-model — Candidate B (wave 95, env-gated SWEG_MASS). A unit
    # that holds NO objective AND is OUT of its own firing range of the nearest
    # enemy (it is idle / advancing, not a shooter holding a fire-lane) masses onto
    # the best holdable objective instead of drifting toward the enemy — the real
    # "play the objectives" tactic, addressing the DOMINANT sub-cause (wave 93: a
    # body army's Objective Control is nowhere near the markers). Gated on
    # out-of-range so it does NOT pull in-range shooters off their lanes (the
    # aggressive all-units version wrecked gunlines). Even-handed across factions;
    # NOT a per-faction or per-model-count knob — a low-model durable army simply
    # has few idle bodies to mass. LANDED wave 95 (default ON; SWEG_MASS=0 to
    # re-gate) after the env-gated N=40 A/B: gated MAE 4.15 → 3.81, the first
    # positional candidate to land — the dominant under-shooter Chaos Daemons
    # −22.7 → −16.4 (its idle Daemons reach the markers) and Imperial Knights
    # +27.0 → +25.5 (its opponents contest), with no gunline chaos (the aggressive
    # all-units version regressed to 6.50). The geometry candidate (w94) regressed
    # because it helped whoever already holds markers; this helps the non-reachers
    # reach them — the faithful "play the objectives" tactic.
    if (
        __import__("os").environ.get("SWEG_MASS", "1") != "0"
        and not unit_on_obj_ids
        and best is not None
        and best[1] in (_CAPTURE_INTENT, _STEAL_INTENT)
        and nearest_enemy_dist > (unit.profile.range_inches or 24)
    ):
        _bobj = best[2]
        # Snap to cover within the marker's control radius so the unit massing
        # onto the objective still arrives in cover (mirrors the CAPTURE
        # cover-snap below), not on bare ground.
        _mass_pos = _best_nearby_cover_point(
            map_, (_bobj.x, _bobj.y), search_radius=_bobj.control_radius,
        )
        return _mass_pos, best[1]

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
            # FREE-CONTEST (#81, gated SWEG_FREECONTEST) — a SPARE in-range
            # SHOOTY/HEAVY unit redirects onto a WINNABLE enemy-held marker it can
            # STILL SHOOT from, even when that marker is not its single best
            # objective. The wave-193 instrument found 86% of the reachable OC on
            # the still-flippable Knight markers is exactly this (shooty-can-shoot-
            # from-marker, 0% would lose its shots), but #12 below only repositions
            # onto the unit's SINGLE best objective, so a winnable enemy marker
            # that loses the distance-competition to a closer hold stays
            # uncontested. Guards (the wave-95 Stage-E rail): WINNABLE (our
            # potential EFFECTIVE OC > enemy EFFECTIVE OC — bracket-aware, a damaged
            # Knight at OC5 is flippable); REACHABLE this turn; SHOOTABLE from the
            # marker (an enemy in range — zero shot-cost, not a gunline-pull);
            # JUST-ENOUGH (skip a marker our side already winnably contests). The
            # AFFORDABLE guard is the hold-check above (a marginal friendly-marker
            # holder already returned _HOLD_INTENT and never reaches here, so this
            # only ever moves SPARE bodies). Default-OFF => byte-identical.
            if __import__("os").environ.get("SWEG_FREECONTEST", "1") != "0":
                _fc_move = effective_move(unit)
                _fc_unit_eff = _effective_oc_value(unit)
                _fc_best_obj = None
                _fc_best_d = float("inf")
                for _fc_obj in objectives:
                    _fc_e = _effective_oc_on_objective(enemy_alive, _fc_obj)
                    if _fc_e <= 0:
                        continue                 # not enemy-held — not a contest
                    _fc_o = _effective_oc_on_objective(
                        friendly_alive, _fc_obj, exclude_uid=unit.uid,
                    )
                    if _fc_o > _fc_e:
                        continue                 # JUST-ENOUGH: already winnably contesting
                    if _fc_o + _fc_unit_eff <= _fc_e:
                        continue                 # unwinnable even by committing this unit
                    _fc_pos = (_fc_obj.x, _fc_obj.y)
                    _fc_d = _dist(unit.position, _fc_pos)
                    if _fc_d > _fc_move + _fc_obj.control_radius:
                        continue                 # unreachable this turn
                    if not any(_dist(_fc_pos, e.position) <= rng for e in enemy_alive):
                        continue                 # can't shoot from there — would be a gunline-pull
                    if _fc_d < _fc_best_d:
                        _fc_best_d = _fc_d
                        _fc_best_obj = _fc_obj
                if _fc_best_obj is not None:
                    _fc_snap = _best_nearby_cover_point(
                        map_, (_fc_best_obj.x, _fc_best_obj.y), search_radius=3.0,
                    )
                    return _fc_snap, _STEAL_INTENT
            # #12 OBJECTIVE-AWARE REPOSITION (2026-05-31): a ranged unit that
            # can still shoot from an objective should move ONTO the best-scoring
            # objective — scoring VP while continuing to fire — rather than
            # holding in open ground. This is the board-control play durable
            # gunline bricks (Imperial / Chaos Knights, gun tanks) win with; the
            # kill-centric in-place reposition under-credited it, which is the
            # dominant source of the Knights' AI-positional residual (the blunt
            # "durable units always camp" experiment moved Chaos Knights
            # -38 -> -8.8 / Imperial Knights -21.8 -> +5.2 but over-buffed
            # gunlines and made melee monsters mis-camp). This is the clean
            # version: only SHOOTY/HEAVY units reach here (melee-primary units
            # never do, so they keep charging), it is gated OUT for the tuned
            # aggressive gunline postures (shimmy / alpha_strike / fast_strike —
            # Aeldari / T'au keep their fire-lane play, so the over-shooters are
            # not pushed further over), and it only diverts when an enemy is
            # still within firing range from the objective (the unit keeps its
            # shot — board control AND damage, not camping out of range).
            if (
                posture not in ("shimmy", "alpha_strike", "fast_strike")
                and best is not None and best[0] > 0.2
            ):
                _, _obj_intent, _obj, _ = best
                _obj_pos = (_obj.x, _obj.y)
                if any(_dist(_obj_pos, e.position) <= rng for e in enemy_alive):
                    _obj_snap = _best_nearby_cover_point(
                        map_, _obj_pos, search_radius=3.0,
                    )
                    return _obj_snap, _obj_intent
            # In range — don't drift around. But snap to nearby cover when
            # available so we get the defensive uplift.
            repo_pos = _best_nearby_cover_point(map_, unit.position, search_radius=3.0)
            return repo_pos, _REPOSITION_INTENT

    # DUAL: if a high-value charge target is within potential charge range
    # next round (move + 12" threat), close on it; otherwise fall through
    # to objective logic. This is what real Intercessor / Boyz / similar
    # do — bias toward enemies with weak melee, not just the closest body.
    if role == "DUAL" and enemy_alive:
        move_dist = effective_move(unit)
        threat_range = move_dist + 12.0
        viable = [
            e for e in enemy_alive
            if _dist(unit.position, e.position) <= threat_range
        ]
        if viable:
            # Pre-compute raw scores to avoid calling _melee_target_score
            # twice for the winning target (once in max(), once for the 0.1
            # threshold check).
            raw_scores = {id(e): _melee_target_score(unit, e) for e in viable}
            best_melee = max(
                viable,
                key=lambda e: _plan_target_score(raw_scores[id(e)], e),
            )
            if raw_scores[id(best_melee)] > 0.1:
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
    if role == "MELEE" and _dist(unit.position, fallback_pos) <= _ENGAGEMENT_RANGE:
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
#   2. Round 5 fallback: force-fire so the buff isn't wasted entirely.
#   3. First-charge trigger (#175 G9): declare on the first round where at
#      least one Ork unit has a chargeable target within 12" right now AND
#      Boyz remain at >= 40% of starting count. Pure shooters don't trigger
#      this — the gate uses the same `_wants_to_charge` melee/ranged DPA
#      ratio that the simulator's charge phase uses. This lines the +1 to
#      melee Wound up with the first turn the army actually swings melee,
#      instead of firing on a fixed R3 when most chargers have already
#      committed and the buff is wasted (the bug #175 fixes).
#   4. Emergency: Orks below 70% starting points and at least Round 2 — fire
#      now to hit back before the army crumbles further, regardless of Boyz.
#   5. Round 4 fallback: if nothing above triggered, fire — better late than
#      never.
def _has_chargeable_target(attacker, enemy) -> bool:
    """True iff `attacker` has at least one chargeable enemy within 12".

    Mirrors the cheap pre-checks `_do_charge` does at strike time: out of
    engagement range (>1") and within charge distance (<=12"). Pure
    distance gate — doesn't simulate the 2D6 roll itself.
    """
    if enemy is None:
        return False
    ax, ay = attacker.position
    for e in enemy.alive_units:
        ex, ey = e.position
        d = ((ax - ex) ** 2 + (ay - ey) ** 2) ** 0.5
        if 1.0 < d <= 12.0:
            return True
    return False


def _ork_wants_to_charge(attacker) -> bool:
    """Same melee-vs-ranged DPA gate the simulator uses (`_wants_to_charge`).

    Kept inline here so the strategy layer doesn't import simulator. If the
    formula drifts in `code.simulator.Battle._wants_to_charge`, update
    both — they need to agree so the AI declares WAAAGH on a round it
    actually plans to charge.
    """
    p = attacker.profile
    if p.melee_attacks <= 0 or p.melee_hit_probability <= 0:
        return False
    melee_dpa = p.melee_attacks * p.melee_hit_probability * (p.melee_damage_per_shot or 1.0)
    ranged_dpa = max(1, p.attacks) * p.hit_probability * p.per_shot_damage
    return melee_dpa >= max(ranged_dpa, 1.0)


def should_declare_waaagh(army, round_num: int, opponent=None) -> bool:
    """Decide whether the Ork player should declare WAAAGH! this round.

    Args:
        army: the Ork Army (must have `waaagh_round_unlocked` attribute).
        round_num: the current battle round (1..MAX_ROUNDS).
        opponent: the enemy Army. Optional — if omitted, the AI falls back
            to the old round-default heuristic (legacy callers without
            opponent context). The first-charge-round trigger needs the
            opponent to scan chargeable distances.

    Returns:
        True iff the army should declare WAAAGH! NOW. Caller is responsible
        for setting `army.waaagh_round_unlocked = round_num` and emitting
        the WaaaghDeclared event.
    """
    if getattr(army, "waaagh_round_unlocked", None) is not None:
        return False   # already used this battle

    starting = float(getattr(army, "starting_points", 0.0) or 0.0)
    current = float(sum(u.profile.points_cost for u in army.alive_units))

    # Round 5: hard force-fire — last command phase, use it or lose it.
    if round_num >= 5:
        return True

    # Emergency: heavy losses, fire now to retaliate before army crumbles.
    if round_num >= 2 and starting > 0 and current < 0.70 * starting:
        return True

    # First-charge-round trigger (#175 G9). Need opponent context AND Boyz
    # bench-strength to avoid firing on a turn-1 token charge or a turn-5
    # corpse-flail.
    if opponent is not None:
        starting_boyz = sum(
            1 for u in army.units if "Boyz" in u.profile.name
        )
        alive_boyz = sum(
            1 for u in army.units
            if u.is_alive and "Boyz" in u.profile.name
        )
        boyz_ok = (
            starting_boyz == 0   # no Boyz roster — Nobz/Meganobz core
            or alive_boyz >= 0.40 * starting_boyz
        )
        if boyz_ok:
            for u in army.alive_units:
                if u.profile.faction != "Orks":
                    continue
                if not _ork_wants_to_charge(u):
                    continue
                if _has_chargeable_target(u, opponent):
                    return True

    # Round 4 fallback: if no first-charge / emergency triggered, fire now.
    if round_num >= 4:
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
      * Tank Shock: reactive (vehicle charge succeeds).
      * Spirit Stones: reactive (damage taken).
      (Heroic Intervention is no longer a stratagem — #iter12 removed the
      1 CP entry and re-implemented it as a free core CHARACTER ability
      in code.simulator._do_heroic_intervention per Wahapedia 10e.)
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
        "Counter-Offensive", "Tank Shock",
        "Spirit Stones",
    ):
        return 0
    # Defensive mid-game (wounded high-value brick survival).
    if name in (
        "Disgustingly Resilient", "Glamour of Tzeentch",
        "Lightning-Fast Reactions", "Implacable Onslaught",
        # Warhost defensive proxies (#197): Skyborne Sanctuary and Webway
        # Tunnel both route their canonical "pull unit out of harm's way"
        # effect through transient_plus_one_save; they fire on the same
        # mid-game survival window as Lightning-Fast Reactions.
        "Skyborne Sanctuary", "Webway Tunnel",
        # Virulent Vectorium defensive/heal stratagems also belong to the
        # mid-game survival window: Putrid Detonation auto-detonates a
        # half-dead vehicle, Leechspore Eruption heals + chips an adjacent
        # foe, Plaguesurge widens the contagion bubble when CP is abundant.
        "Putrid Detonation", "Leechspore Eruption", "Plaguesurge",
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


_HIGH_VALUE_TARGET_PTS: float = 100.0    # iter5 C5: bypass pivotal-hold on premium targets


def _should_hold_for_pivotal_turn(army, strat, ctx: Optional[dict] = None) -> bool:
    """Return True if the army should DEFER firing this stratagem rather than
    spending CP now, based on the predicted pivotal turn.

    Rules:
      * pivotal_turn == 0 (reactive): never hold — defer to trigger logic.
      * cost <= 0 (refunded by an ability): never hold.
      * current_round == pivotal_turn or beyond: never hold.
      * current_round == final round (T5): never hold — use it or lose it.
      * remaining CP > 2 * cost: never hold (CP abundant).
      * High-value trigger override (iter5 C5, faction-neutral): if ctx
        carries a `target` whose `points_cost >= _HIGH_VALUE_TARGET_PTS` AND
        the army can afford a second spend (cp >= 2 * cost), bypass the
        pivotal hold. This stops CP leaking to R4/R5 when a premium target
        (Knight / Wraithlord / Custodian-tier brick) is on the table now.
        Applies uniformly across all factions — the threshold keys on the
        target's BSData points_cost, no faction lookup.
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
    # iter5 C5: high-value target override — burn-on-trigger for premium
    # rolls when we can afford the spend twice over (cp >= 2 * cost). This
    # is faction-neutral: the threshold is a universal points-cost bar, not
    # a faction- or keyword-specific bypass. Without this, CP held through
    # R1 for "pivotal R2" leaks to R4/R5 when R2 didn't produce a trigger.
    if ctx is not None and cp >= 2 * cost:
        target = ctx.get("target") or ctx.get("charge_target")
        if target is not None:
            try:
                tcost = float(target.profile.points_cost)
            except Exception:
                tcost = 0.0
            if tcost >= _HIGH_VALUE_TARGET_PTS:
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
    # trigger. Reactive stratagems (Counter-Offensive, Tank Shock,
    # Spirit Stones) and zero-cost stratagems are exempt.
    # iter5 C5: ctx is now consulted so a high-value trigger can bypass the
    # hold gate uniformly across factions (faction-neutral CP-leak cleanup).
    if _should_hold_for_pivotal_turn(army, strat, ctx):
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
        # iter5 C5: tighten the post-pivotal value bar so leaked CP doesn't
        # burn on R3-R4 marginal triggers. After the alpha-strike window
        # (R > pivotal_turn = R3+), require ~50% higher expected swing.
        # Faction-neutral: keys on round number + universal points-cost.
        bar = _MIN_EXPECTED_SWING_PTS
        cur = _get_current_round(army)
        pivot = _predict_pivotal_turn(strat)
        if cur > 0 and pivot > 0 and cur > pivot and cur < _FINAL_ROUND:
            bar = _MIN_EXPECTED_SWING_PTS * 1.5
        return value >= bar

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

    # Heroic Intervention was removed from the stratagem list in #iter12 —
    # it is a free core CHARACTER ability (no CP cost) implemented in
    # code.simulator._do_heroic_intervention. No should_fire_stratagem
    # branch is needed because the simulator never asks the strategy
    # layer about Heroic Intervention any more.

    # ----- Cult of Magic (Thousand Sons) ---------------------------------

    if name == "Doombolt":
        # ctx expects {"target": Unit, "has_psyker": bool}. Doombolt is the
        # cheapest CP spend in the codex — 1 CP for ~2 mortal wounds (median
        # D3). ST-3: tightened to skip near-dead targets where the 2 MW
        # payload is wasted on overkill (TSON over-performs by +17.5).
        target = ctx.get("target")
        if target is None:
            return False
        if not ctx.get("has_psyker", False):
            return False
        # ST-3: skip if target has < 30% HP remaining (overkill — 2 MW will
        # land but most of it is wasted on a model that's about to die).
        try:
            hp_remaining_frac = target.current_health / max(1.0, target.profile.health)
        except Exception:
            hp_remaining_frac = 1.0
        if hp_remaining_frac < 0.3:
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
        # ST-3: require real DPA on the attacker — a +1-to-wound on a
        # 0.5 DPA attacker is wasted CP (TSON over-performs by +17.5).
        try:
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5

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

    # ----- Virulent Vectorium (Death Guard) -------------------------------

    if name == "Putrid Detonation":
        # ctx expects {"target": Unit}. The target is the DG VEHICLE/MONSTER
        # donor with deadly_demise > 0. Fire prophylactically: as long as a
        # donor exists, the auto-success buff for the round is cheap (1 CP)
        # and the EV is ~2 mortals to nearby enemies if the donor dies.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            demise = int(getattr(target.profile, "deadly_demise", 0) or 0)
        except Exception:
            demise = 0
        # Only fire if the donor is meaningfully threatened — at full HP the
        # demise auto-success is a 5-round bet that may never pay off; at
        # below half HP the donor is likely to die this round and the spend
        # is justified.
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
        except Exception:
            hp_frac = 0.0
        return demise >= 2 and hp_frac > 0.3

    if name == "Plaguesurge":
        # ctx expects {"target": Unit} (DG WARLORD). 2 command points to add
        # +3" to Contagion Range for the round (wave 235: the flag is now
        # consumed by the Battle-shock phase; range becomes 6" instead of 3").
        # Fire from round 2 onwards (contagion sources only applied from R2)
        # when CP is not critically low. Holding to CP >= 3 leaves headroom for
        # reactive stratagems.
        cp = int(getattr(army, "command_points", 0) or 0)
        battle = getattr(army, "_battle_ref", None)
        round_num = getattr(battle, "_current_round", 0) if battle else 0
        return round_num >= 2 and cp >= 3

    if name == "Leechspore Eruption":
        # ctx expects {"target": Unit, "enemy": Unit}. Fire when the DG
        # model has lost a meaningful share of HP (>= 50%) AND a target
        # enemy exists within 3". The mortals payload + self-heal make this
        # worth 1 CP whenever the donor is at half-HP+.
        target = ctx.get("target")
        enemy = ctx.get("enemy")
        if target is None or enemy is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
        except Exception:
            return False
        return hp_frac >= 0.5

    if name == "Overwhelming Generosity":
        # ctx expects {"attacker": Unit, "target": Unit}. Same gates as Plague
        # Weapons / Fire and Fade for offensive shoot uplifts: real DG
        # CHARACTER shooter (ranged DPA >= 2) AND a HEAVY target.
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

    if name == "Creeping Blight":
        # ctx expects {"attacker": Unit, "target": Unit}. Same gate as
        # Overwhelming Generosity but for DG INFANTRY. The Afflicted gate is
        # APPROXIMATED away so the heuristic just requires the DG INFANTRY
        # unit have a real shooting profile and the target be HEAVY-class.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.0 and _is_heavy_target(target)

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

    # ----- Warhost (Aeldari) ---------------------------------------------
    # (Was "Battle Host" before #197 — codex renamed the launch-index name.
    # Heuristics here cover all six real codex stratagems.)

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

    if name == "Skyborne Sanctuary":
        # ctx expects {"target": Unit}. Defensive +1 save proxy for the
        # end-of-fight re-embark. Same gate as Lightning-Fast Reactions
        # (substantially-wounded high-value Aeldari unit) — both spend
        # 1 CP to shelter a survivor.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.4 and cost >= 100.0

    if name == "Feigned Retreat":
        # ctx expects {"attacker": Unit}. Transient Assault on a real
        # AELDARI shooter — fire for a high-cost shooter (the codex use
        # case is "pull a key shooter out of melee and still let it
        # shoot"). 150+ pts so we're not paying 1 CP on a Guardian squad.
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            cost = 0.0
        return cost >= 150.0

    if name == "Blitzing Firepower":
        # ctx expects {"attacker": Unit, "target": Unit}. +1 to hit
        # shooting proxy for Sustained Hits 1. Same gate as Fire and
        # Fade (real shooter, heavy target, target already softened).
        # Aeldari already overperforms vs the meta, so the gate is
        # intentionally tight.
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
        return (
            ranged_dpa >= 2.0
            and atk_cost >= 150.0
            and _is_heavy_target(target)
            and tgt_hp_frac > 0.15
        )

    if name == "Webway Tunnel":
        # ctx expects {"target": Unit}. Defensive +1 save proxy for the
        # end-of-enemy-fight Strategic Reserves pull. Same gate as
        # Lightning-Fast Reactions and Skyborne Sanctuary — defensive
        # spend on a wounded high-value Aeldari brick.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.4 and cost >= 100.0

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

    # ----- Awakened Dynasty (Necrons) — six real Protocols (#194) -------
    # Two Protocols (Eternal Revenant, Vengeful Stars) have no clean
    # simulator hook and are catalogued-but-no-op. The four below match the
    # four `_try_protocol_*` dispatchers in simulator.py.

    if name == "Protocol of the Undying Legions":
        # ctx expects {"target": Unit}. 1 CP defensive — fire when a real
        # NECRONS unit has taken meaningful HP loss so the extra D3 (+1
        # if led) reanimation pulse actually has dead peers to revive.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        # Wounded multi-model squad worth at least 80 pts — leans on the
        # canonical "Warrior brick blown apart by alpha strike" scenario.
        return hp_frac > 0.2 and cost >= 80.0

    if name == "Protocol of the Hungry Void":
        # ctx expects {"attacker": Unit, "target": Unit}. +1 S melee (+1
        # AP if led) — fire when the attacker has real melee DPA AND the
        # target is a heavy threat (a +1 S that closes T4→T8 wound bracket
        # is wasted on Cultists). Worth 1 CP on multi-attack melee Necrons.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            melee_dpa = p.melee_attacks * p.melee_hit_probability * (p.melee_damage_per_shot or 0.0)
        except Exception:
            melee_dpa = 0.0
        return melee_dpa >= 2.0 and _is_heavy_target(target)

    if name == "Protocol of the Sudden Storm":
        # ctx expects {"attacker": Unit}. [ASSAULT] for the round — fire
        # for a real ranged shooter that benefits from advancing-and-shooting
        # (move pressure into half range / clear a screen). Threshold 80 pts
        # so we don't burn CP for Warriors with gauss flayers.
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            cost = 0.0
        return cost >= 80.0

    if name == "Protocol of the Conquering Tyrant":
        # ctx expects {"attacker": Unit, "target": Unit}. Re-roll hits of 1
        # within half range (full re-roll if led) — fire when the attacker
        # has serious DPA AND the target is heavy. Direction-correct
        # ~25% damage uplift; cheap 1 CP gate matches Methodical Destruction's
        # old shape (which it replaces).
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

    # Legacy Awakened Dynasty heuristics (kept for backwards compatibility
    # with any external caller; the stratagem constants themselves were
    # deleted in the fabrication audit so these branches are unreachable
    # via the simulator's dispatcher).
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
        # ST-3: skip if target has < 40% HP remaining — the extra MW is
        # overkill on a near-dead model. Mirrors Doombolt's gate but
        # tighter (this is the 2 CP combined spend). TSON over-performs.
        target = ctx.get("target")
        if target is None or not ctx.get("has_psyker", False):
            return False
        if not _is_heavy_target(target):
            return False
        try:
            hp_remaining_frac = target.current_health / max(1.0, target.profile.health)
        except Exception:
            hp_remaining_frac = 1.0
        return hp_remaining_frac >= 0.4

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

    # ----- Mont'ka (T'au Empire) — six real detachment stratagems (#196)
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka
    # Same `cost >= 150` brick filter as Strike Swiftly / Matchless Agility —
    # T'au already over-rates so CP only ever fires on real shooters (Crisis
    # Battlesuits / Broadsides / Riptide), not Fire Warrior squads.

    if name in (
        "Pinpoint Counter-Offensive", "Aggressive Mobility", "Focused Fire",
        "Combat Debarkation", "Pulse Onslaught",
    ):
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            cost = 0.0
        return cost >= 150.0

    if name == "Counterfire Defence Systems":
        # Defensive 2 CP — fire on a wounded high-value T'au unit. Same
        # gate shape as Disgustingly Resilient / Lightning-Fast Reactions:
        # require visible HP loss AND points cost >= 150, so we don't
        # waste 2 CP keeping a Fire Warrior squad alive.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.25 and cost >= 150.0

    # ----- Grand Coven (Thousand Sons) — six real stratagems (#193) -----

    if name == "Psychic Dominion":
        # ctx: {"target": Unit}. Defensive FNP. Fire when the most vulnerable
        # TSons unit has taken any HP loss AND is a substantial threat
        # (>=100 pts — Scarab Occult Terminator brick, Magnus, etc.).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return cost >= 100.0 and hp_frac >= 0.0

    if name == "Destined by Fate":
        # ctx: {"target": Unit}. -1 damage taken (APPROXIMATION; real
        # rule sets one failed save's Damage to 0). Fire on a wounded
        # PSYKER — single-instance defensive spend.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.2 and cost >= 80.0

    if name == "Desecration of Worlds":
        # ctx: empty. Objective-control persistence. Fire from round 2
        # onwards once the army has had time to actually plant a flag.
        # Cheap to spend; the simulator currently treats this as a CP
        # tax with no mechanical follow-through (APPROXIMATION).
        battle = getattr(army, "_battle_ref", None)
        round_num = getattr(battle, "_current_round", 0) if battle else 0
        return round_num >= 2

    if name == "Devastating Sorcery":
        # ctx: {"attacker": Unit, "target": Unit}. 2 CP for a re-roll
        # hits buff on a PSYKER shooter. Higher gate than the 1-CP
        # variants: require real DPA AND a heavy target.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            atk_cost = float(p.points_cost)
        except Exception:
            return False
        return ranged_dpa >= 2.0 and atk_cost >= 80.0 and _is_heavy_target(target)

    # Egotistical Power and Arcane Focus are intentionally not dispatched
    # via the round-start path (APPROXIMATION — see simulator dispatchers).

    # ----- Rubricae Phalanx (Thousand Sons) — six stratagems (iter15) -----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    # Gates here mirror the Grand Coven shape — TSON has plentiful CP and a
    # single Stratagem-cap-per-Command-phase, so the gates should be
    # permissive enough that the army actually spends rather than hoarding.
    # Ardent Automata + Revenge of the Rubricae have no dispatcher (no-op
    # APPROXIMATIONs), so they're omitted from the AI list — the simulator's
    # dispatcher short-circuits before should_fire_stratagem is consulted.

    if name == "Inexorable Advance":
        # ctx: {"attacker": Unit}. Transient [ASSAULT] on a RUBRICAE
        # shooter. Fire when the attacker has real ranged DPA (>= 1.0)
        # AND a meaningful cost (>= 80 — Rubric Marines squad floor).
        # ST-3: tightened DPA bar to 1.5 — RUBRICAE squads with cheap
        # bolters don't earn the CP back from an [ASSAULT] proxy. TSON
        # over-performs by +17.5; tighter gates preserve CP for the
        # high-impact Doombolt / Devastating Sorcery spends.
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            atk_cost = float(p.points_cost)
        except Exception:
            return False
        return ranged_dpa >= 1.5 and atk_cost >= 80.0

    if name == "Infernal Fusillade":
        # ctx: {"attacker": Unit, "target": Unit}. 2 CP for a +1 to wound
        # shooting buff on a RUBRICAE PSYKER. Higher gate than 1-CP
        # variants: require real DPA AND a heavy target (so the wound
        # uplift translates to meaningful damage).
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            atk_cost = float(p.points_cost)
        except Exception:
            return False
        return ranged_dpa >= 1.5 and atk_cost >= 80.0 and _is_heavy_target(target)

    if name == "Implacable Guardians":
        # ctx: {"target": Unit}. 2 CP for -1 damage taken on a RUBRIC
        # MARINES / Scarab Occult unit. Defensive spend — fire when the
        # target has taken meaningful damage (HP loss >= 25%) AND is a
        # substantial threat (>= 100 pts, the Scarab Occult / Magnus
        # bracket where the durability uplift matters).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac >= 0.25 and cost >= 100.0

    if name == "Unwavering Phalanx":
        # ctx: {"target": Unit}. 1 CP for a +1 save defensive proxy on
        # a RUBRICAE unit. Cheaper than Implacable Guardians, so a
        # lower gate: any wounded RUBRICAE unit with >= 70 pts cost
        # (Rubric Marines squad floor).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac >= 0.2 and cost >= 70.0

    # ----- War Horde (Orks) — six real stratagems (iter-1 Cluster B B1)
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
    # Orks under-performed by -6.6pt at iter-0 baseline (docs/AUTO_LOOP
    # _ITER1_CLUSTER_B.md). Gates here are deliberately permissive —
    # Orks have plentiful CP and no other detachment to spend on, so
    # the army should be firing stratagems aggressively when its
    # melee-DPA bricks engage. Insane Bravery is intentionally not
    # listed (no-op dispatcher, never fires; no AI gate needed).

    if name == "Power Of The WAAAGH!":
        # ctx: {"attacker": Unit, "target": Unit}. +1-to-wound melee
        # approximation. Fire when the Orks attacker has real melee
        # DPA AND the target is HEAVY-class — matches the Outbreak of
        # Pestilence / Protocol of the Hungry Void heuristic shape.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            melee_dpa = p.melee_attacks * p.melee_hit_probability * (p.melee_damage_per_shot or 0.0)
        except Exception:
            melee_dpa = 0.0
        return melee_dpa >= 2.0 and _is_heavy_target(target)

    if name == "Mob Up":
        # ctx: {"target": Unit}. Reanimation-pulse approximation on a
        # wounded Orks unit. Fire when the target has lost meaningful HP
        # (>= 30%) AND the unit has a multi-model footprint (max HP >=
        # 4.0, i.e. Boyz squad / Lootas / Nobz — not single-wound
        # single-model squads like a Warboss).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            max_hp = float(target.profile.health)
        except Exception:
            return False
        return hp_frac >= 0.3 and max_hp >= 4.0

    if name == "Big Krumpin'":
        # ctx: {"attacker": Unit, "target": Unit}. 2 CP gate — tighter
        # than Power Of The WAAAGH!. Require real melee DPA AND a
        # HEAVY-class target AND a meaningfully large Orks attacker
        # (cost >= 80, i.e. a real brick — not a Grot squad).
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            melee_dpa = p.melee_attacks * p.melee_hit_probability * (p.melee_damage_per_shot or 0.0)
            cost = float(p.points_cost)
        except Exception:
            return False
        return melee_dpa >= 3.0 and cost >= 80.0 and _is_heavy_target(target)

    if name == "Tellyporta":
        # ctx: {"target": Unit}. Defensive +1 save approximation. Fire
        # on a wounded high-value Orks INFANTRY unit — same shape as
        # Lightning-Fast Reactions but with a lower point gate because
        # Orks bricks are cheaper per-point than Aeldari.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.3 and cost >= 80.0

    if name == "Da Biggest Boss":
        # ctx: {"attacker": Unit}. Warlord-only mobility approximation.
        # Fire whenever a real Orks CHARACTER exists — the [ASSAULT]-
        # for-the-round transient routes a single free shoot-after-move,
        # cheap at 1 CP. Gate the spend on the character being a real
        # contender (cost >= 60 covers Warboss, Ghazghkull, Beastboss
        # and shuts out the 35-pt Mek).
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            return False
        return cost >= 60.0

    # ----- Shield Host (Adeptus Custodes) — six real stratagems (iter-8) -
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
    # Custodes burns 5+ strat fires/battle on Command Re-Roll at iter-7
    # baseline (no detachment stratagems registered). Gates here are
    # permissive — Custodes has 6+ CP/battle and few units, so the AI
    # should fire stratagems aggressively when its bricks engage. Point
    # thresholds are LOW (cost >= 80 — Custodes profiles average 40+ pts
    # per model so a 5-model brick clears easily) since the army has no
    # cheap chaff to leak CP onto. Vigilance Eternal has no AI gate (no-op
    # dispatcher).

    if name == "Arcane Genetic Alchemy":
        # ctx: {"target": Unit}. Defensive FNP-5 approximation. Fire on a
        # wounded high-value Custodes unit. Same shape as Lightning-Fast
        # Reactions / Psychic Dominion: HP loss + meaningful cost.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.2 and cost >= 80.0

    if name == "Unwavering Sentinels":
        # ctx: {"target": Unit}. Defensive +1-save approximation. Fire on
        # a wounded high-value Custodes INFANTRY brick — same gate shape
        # as Lightning-Fast Reactions / Tellyporta.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.2 and cost >= 80.0

    if name == "Multipotentiality":
        # ctx: {"attacker": Unit}. Assault-this-round approximation. Fire
        # for a high-cost Custodes attacker — Custodes profiles are elite
        # so even a small brick is worth the [ASSAULT] proxy.
        # ST-3: tightened to require real ranged DPA (>= 1.0) — the
        # [ASSAULT] proxy only helps shooters that can capitalise on the
        # advance-and-shoot. Pure melee bricks already advance for free,
        # so CP is wasted on them. Custodes over-performs by +29.9 — the
        # tighter gate matches Strike Swiftly's shape but with a lower
        # cost bar (Custodes profiles are dense per-point).
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            return False
        return cost >= 80.0 and ranged_dpa >= 1.0

    if name == "Archaeotech Munitions":
        # ctx: {"attacker": Unit, "target": Unit}. Offensive +1-to-hit-
        # shooting approximation for [LETHAL HITS] / [SUSTAINED HITS 1].
        # Fire when the Custodes attacker has real ranged DPA AND target
        # is HEAVY-class (same gate shape as Focused Fire / Methodical
        # Destruction).
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Avenge the Fallen":
        # ctx: {"target": Unit}. +1-to-wound-melee approximation for the
        # +1 Attack codex effect. Fire on a wounded Custodes melee unit —
        # the codex gate "below Starting Strength" maps to "HP loss > 0".
        # Cost gate prevents firing on cheap units; Custodes elite unit
        # profile costs vary but 80+ pts covers everything that matters.
        # ST-3: tightened hp_frac to > 0.2 so we don't burn 1 CP for a
        # single-wound chip (the codex effect is mainly meaningful when
        # a model has actually died). Custodes over-performs by +29.9.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.2 and cost >= 80.0

    if name == "Vigilance Eternal":
        # ctx: empty. 1 command point to mark objectives held by Adeptus
        # Custodes BATTLELINE units as sticky. Fire from round 2 onwards
        # (round 1 is the push; sticky ownership is most valuable once the
        # army has planted flags and wants to hold them against contest).
        # CP gate: 1 CP is cheap; hold back only when nearly dry.
        battle = getattr(army, "_battle_ref", None)
        round_num = getattr(battle, "_current_round", 0) if battle else 0
        cp = int(getattr(army, "command_points", 0) or 0)
        return round_num >= 2 and cp >= 2

    # ----- Oathband (Leagues of Votann) — six real stratagems (iter-9) ----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
    # Replaces the iter-0 zero-stratagem state where Votann only fired
    # Command Re-Roll (universal Core). Gates are permissive — Votann lists
    # are typically 8-10 units with Hearthkyn / Hekaton anchors that easily
    # clear the 80-pt threshold.
    #
    # VOTANN-DIAG-2 (2026-05-26): Warrior Pride, Wrath of the Ancestors,
    # Glory of the Hearth, Ironkin Sequence, and Void-Armoured Resilience
    # do not exist in the current 10e codex. Their gate logic is removed.
    # Replaced with three real Needgaard Oathband stratagems below.

    # "Huntr's Mark" gate removed — VOTANN-AUDIT-V1 (2026-05-29): stratagem
    # absent from BSData v10.6.0, citation unverifiable, responsible for
    # +7.8pt overshoot. Stratagem definition deleted from stratagems.py.

    if name == "Ancestral Sentence":
        # ctx: {"attacker": Unit, "target": Unit}. Sustained Hits 1 on a
        # Votann ranged unit (Needgaard Oathband, 1 CP). Fire when the
        # attacker has real ranged DPA and target is heavy-class. 1 CP is
        # cheaper than the removed fake 2 CP token-issue version; gate
        # accordingly.
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Void Hardened":
        # ctx: {"target": Unit}. Defensive no-op (Needgaard Oathband, 1 CP).
        # The simulator cannot model incoming-AP worsening. Register a spend
        # only when the target is a high-value Votann unit under moderate
        # pressure — don't waste command points on undamaged units.
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.3 and cost >= 80.0

    # ----- Gladius Task Force (Adeptus Astartes) — six real strats (iter-12)
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
    # Closes docs/AUDIT_PARITY.md fix #1 (largest 0/6 gap). Gates are
    # tuned to typical Marine unit costs: a 95-pt Tactical Marine squad
    # / 100-pt Intercessor sits at the bottom of the offensive bar; a
    # 200-pt Land Raider / Repulsor sits at the top of the defensive bar.

    if name == "Storm of Fire":
        # ctx: {"attacker": Unit, "target": Unit}. Offensive +1-to-hit-
        # shooting approximation for [SUSTAINED HITS 1]. Fire when the
        # Marine attacker has real ranged DPA AND target is HEAVY-class.
        # Bar is 1.0 ranged-DPA (a 5-man Intercessor at 2A * 2/3 * 1D =
        # 1.33 just clears; 5-man Tactical at 1A * 2/3 * 1 = 0.67 misses,
        # which is intended — Tacticals shouldn't burn the 1 CP).
        # Slightly looser than Mont'ka's Focused Fire (1.5) because
        # Marine ranged profiles average lower per-model output.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.0 and _is_heavy_target(target)

    if name == "Armour of Contempt":
        # ctx: {"target": Unit}. Defensive +1-save approximation. Fire on
        # a wounded high-value Marine unit — same gate shape as
        # Lightning-Fast Reactions / Unwavering Sentinels. Marine bricks
        # (Terminators / Aggressors / Centurions) typically cost 80+ pts
        # so the threshold passes for the units worth protecting.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.2 and cost >= 80.0

    if name == "Squad Tactics":
        # ctx: {"attacker": Unit}. Repositioning approximation routed via
        # [ASSAULT] proxy. Fire for any meaningfully-costed Marine
        # INFANTRY attacker — extra move + shoot is broadly valuable at
        # 1 CP. Gate at 80 pts (covers Intercessors / Hellblasters /
        # Bladeguard) but not a stray 60-pt Scout squad.
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            return False
        return cost >= 80.0

    if name == "Only In Death Does Duty End":
        # ctx: {"target": Unit}. +1-to-wound-melee approximation for the
        # "destroyed-model attacks first" effect. Fire on a wounded
        # Marine unit — the codex gate is "model destroyed before
        # attacking", which we proxy as "unit is taking damage". Cost
        # gate prevents firing on Cultist-class chip targets.
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.0 and cost >= 80.0

    if name == "Honour the Chapter":
        # ctx: {"attacker": Unit, "target": Unit}. 2 CP for hit+wound
        # reroll (we drop the wound-reroll leg). The premium spend; gate
        # tighter than the 1-CP strats. Require real attacker DPA AND a
        # HEAVY target so the CP cashes in. Same gate shape as
        # Devastating Sorcery (Grand Coven) / Glory of the Hearth.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            dpa = (
                (attacker.profile.attacks or 0)
                * (attacker.profile.hit_probability or 0)
                * (attacker.profile.per_shot_damage or 0.0)
            ) + (
                (attacker.profile.melee_attacks or 0)
                * (attacker.profile.melee_hit_probability or 0)
                * (attacker.profile.melee_damage_per_shot or 0.0)
            )
        except Exception:
            dpa = 0.0
        return dpa >= 2.0 and _is_heavy_target(target)

    if name == "Adaptive Strategy":
        # ctx: {"attacker": Unit}. +1-to-wound-melee approximation for
        # an off-doctrine per-unit override. Fire whenever the army has
        # a meaningfully-costed Marine attacker — 1 CP, broadly useful
        # (the per-unit Assault Doctrine flip is value in R1/R2 when
        # the army is in Devastator/Tactical and a unit wants to swing).
        # Same shape as Avenge the Fallen but no hp_frac gate (the codex
        # effect fires at the START of the Command phase, no prior
        # damage required).
        attacker = ctx.get("attacker")
        if attacker is None:
            return False
        try:
            cost = float(attacker.profile.points_cost)
        except Exception:
            return False
        return cost >= 80.0

    # ----- Combined Arms (Astra Militarum) — six real strats (iter-14)
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
    # AM bricks are typically 65-pt squads (Cadians / Krieg / Catachan) or
    # 145-235-pt vehicles (Leman Russ / Rogal Dorn / Sentinel Squadron).

    if name == "Coordinated Action":
        # ctx: {"attacker": Unit, "target": Unit}. Offensive +1-to-hit-
        # shooting on the highest-DPA AM SQUADRON. Fire when SQUADRON
        # has real ranged DPA AND target is HEAVY/SHOOTY (Leman Russ vs
        # Repulsor canonical). Same shape as Mont'ka Focused Fire.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Flexible Command":
        # ctx: {"officers": list, "squadron_candidates": list}. 2 CP for
        # widening Order eligibility to SQUADRON for the round. Worth it
        # when at least one meaningfully-costed Officer + SQUADRON exist.
        officers = ctx.get("officers") or []
        squadron_candidates = ctx.get("squadron_candidates") or []
        if not officers or not squadron_candidates:
            return False
        def _max_cost(units):
            try:
                return max(float(u.profile.points_cost or 0.0) for u in units)
            except (ValueError, TypeError):
                return 0.0
        return _max_cost(officers) >= 50.0 and _max_cost(squadron_candidates) >= 100.0

    if name == "Fields of Fire":
        # ctx: {"attacker": Unit, "target": Unit}. Offensive +1-to-hit-
        # shooting proxy for AP+1 on the highest-ranged-DPA AM unit vs
        # HEAVY/SHOOTY target. Same shape as Storm of Fire.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Inspired Command":
        # ctx: {"officer": Unit, "target": Unit}. 1 CP for an extra
        # Order this round. Worth it when target is a meaningfully-
        # costed BATTLELINE INFANTRY (60+ pts covers Cadians/Krieg/
        # Catachan at 65pts).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return cost >= 60.0

    if name == "Stalwart Protector":
        # ctx: {"target": Unit}. Defensive +1-save on the most
        # vulnerable AM INFANTRY unit. Fire on wounded high-value
        # (hp_frac > 0.2, cost >= 60).
        target = ctx.get("target")
        if target is None:
            return False
        try:
            hp_frac = max(0.0, 1.0 - target.current_health / max(1.0, target.profile.health))
            cost = float(target.profile.points_cost)
        except Exception:
            return False
        return hp_frac > 0.2 and cost >= 60.0

    # Reinforcements! — no AI gate; dispatcher has no implementation
    # hook so should_fire return value never matters. Cataloguer-only.

    # ----- ST-2 wave 3 — one stratagem per under-performing faction -----

    if name == "Apoplectic Frenzy":
        # ctx: {"attacker": Unit, "target": Unit}. 1 CP advance-and-charge
        # delivery enabler for a WORLD EATERS unit (the unit becomes
        # eligible to charge in a turn it Advanced). Fire when a high-DPA
        # WE melee unit has a HEAVY-class target worth delivering into —
        # the gate keeps the spend on units whose charge actually matters.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            melee_dpa = (p.melee_attacks or 0) * (p.melee_hit_probability or 0) * (p.melee_damage_per_shot or 0.0)
        except Exception:
            melee_dpa = 0.0
        return melee_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Denizens of the Warp":
        # ctx: {"attacker": Unit, "target": Unit}. 1 CP shooting hit-reroll
        # uplift for a CHAOS DAEMONS unit. Same shape as Fire and Fade.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Empyric Channelling":
        # ctx: {"attacker": Unit, "target": Unit}. 1 CP shooting hit-reroll
        # uplift on a GREY KNIGHTS PSYKER unit (proxy for SUSTAINED HITS 2
        # on Psychic weapons). Same shape as Fire and Fade.
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Cult Ambush":
        # ctx: {"attacker": Unit, "target": Unit}. 1 CP shooting hit-reroll
        # uplift on a GSC unit (proxy for LETHAL HITS on ranged).
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            ranged_dpa = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        except Exception:
            ranged_dpa = 0.0
        return ranged_dpa >= 1.5 and _is_heavy_target(target)

    if name == "Profane Zeal":
        # ctx: {"attacker": Unit, "target": Unit}. 1 CP melee +1-to-wound
        # uplift on a CSM unit. Same melee-DPA/heavy-target gate shape as
        # Apoplectic Frenzy (the effects differ — this one is a wound buff).
        attacker = ctx.get("attacker")
        target = ctx.get("target")
        if attacker is None or target is None:
            return False
        try:
            p = attacker.profile
            melee_dpa = (p.melee_attacks or 0) * (p.melee_hit_probability or 0) * (p.melee_damage_per_shot or 0.0)
        except Exception:
            melee_dpa = 0.0
        return melee_dpa >= 1.5 and _is_heavy_target(target)

    # Unknown stratagem — let the simulator decide via its own dispatch.
    return False

