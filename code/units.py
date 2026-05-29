"""Unit profiles and battle-instance unit class."""

from __future__ import annotations

import functools
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .factions import is_marine_faction

# ---------------------------------------------------------------------------
# Baseline calibration constants — Space Marine is the reference unit
# ---------------------------------------------------------------------------

BASELINE_HEALTH: float = 1.0
BASELINE_DAMAGE: float = 1.0
BASELINE_HIT_PROB: float = 2 / 3       # 3+ to hit on a d6
BASELINE_AP: int = 0
BASELINE_SAVE: int = 3                  # 3+ armour save
BASELINE_STRENGTH: int = 4              # bolter S4
BASELINE_TOUGHNESS: int = 4             # Marine T4
BASELINE_POINTS: float = 15.0


@functools.lru_cache(maxsize=256)
def wound_probability(strength: int, toughness: int) -> float:
    """
    Standard 40K wound table:

      S >= 2T : wound on 2+ (5/6)
      S > T   : wound on 3+ (4/6)
      S == T  : wound on 4+ (3/6)
      S < T   : wound on 5+ (2/6)
      2S <= T : wound on 6+ (1/6)
    """
    if strength >= 2 * toughness:
        return 5 / 6
    if 2 * strength <= toughness:
        return 1 / 6
    if strength > toughness:
        return 4 / 6
    if strength == toughness:
        return 3 / 6
    return 2 / 6   # strength < toughness but not 2S <= T


def _prob_to_target(prob: float) -> int:
    """
    Invert a "succeed on N+" d6 probability back to its target. Clamped to [2,7]
    because a 1 always fails and 7+ is the canonical "no save / no hit".
    """
    target = int(round(7 - prob * 6))
    return max(2, min(7, target))


# APPROXIMATION: 3-round escalating model is the older index/launch-day Contagions shape.
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/death-guard/
# Real rule (current 10e): Nurgle's Gift / Afflicted — Skullsquirm Blight, Rattlejoint Ague,
# Scabrous Soulrot variants applied per unit, not a fixed -1T R1 / -1Ld R2 / -1 to hit R3+
# sequence. Direction-correct (still debuffs enemies near DG models) but mechanics differ.
def _contagion_round_for(unit: "Unit") -> int:
    """Return the active Death Guard Contagion round for the army that opposes
    `unit`'s army, or 0 when no DG army is on the opposing side / no battle is
    active. Used by `Unit.attack` to gate the 3" Nurgle's Gift aura.

    Contagions of Nurgle (Death Guard army rule, 10e — post iter-4 shape):
      Round 1 — (no debuff; the legacy Virulent Rot -1 T branch was dropped
                in iter-4 — it had no anchor in the modern codex)
      Round 2 — Maladictive Pall:   -1 Ld on enemy units within 3" (battleshock)
      Round 3+ — Fulminating Plague: -1 to hit on enemy units within 3"
    """
    own_army = getattr(unit, "army_ref", None)
    if own_army is None:
        return 0
    battle = getattr(own_army, "_battle_ref", None)
    if battle is None:
        return 0
    cur_round = getattr(battle, "_current_round", 0)
    return int(cur_round) if cur_round > 0 else 0


def _is_near_enemy_dg_model(unit: "Unit", radius: float = 6.0) -> bool:
    """True iff any DEATH GUARD model from the army opposing `unit` is within
    `radius` inches of `unit.position`. The aura is projected by every DG
    model ("Each model in your army has the following aura ability"), so we
    scan the full opposing roster, not just CHARACTERS / SYNAPSE-style sources.

    Returns False when `unit` has no army / no live battle / the opposing army
    contains no DG units. Cited as `simulator.contagions_of_nurgle`.
    """
    own_army = getattr(unit, "army_ref", None)
    if own_army is None:
        return False
    battle = getattr(own_army, "_battle_ref", None)
    if battle is None:
        return False
    # Identify the OPPOSING army — the one that's NOT unit.army_ref.
    if own_army is getattr(battle, "a", None):
        opposing = getattr(battle, "b", None)
    elif own_army is getattr(battle, "b", None):
        opposing = getattr(battle, "a", None)
    else:
        return False
    if opposing is None:
        return False
    # Aura source = any DG model on the opposing side.
    ux, uy = unit.position
    r2 = radius * radius
    for m in opposing.alive_units:
        if m.profile.faction != "Death Guard":
            continue
        mx, my = m.position
        dx = mx - ux
        dy = my - uy
        if dx * dx + dy * dy <= r2:
            return True
    return False


def _doctrina_battleline_proximity_met(unit: "Unit") -> bool:
    """True iff `unit` satisfies the Doctrina Imperatives BATTLELINE proximity
    gate: it has the BATTLELINE keyword itself, OR it is within 6" of any
    friendly ADEPTUS MECHANICUS BATTLELINE unit.

    Wahapedia verbatim
    (https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus/):
        "...if this unit has the BATTLELINE keyword and/or it is within 6"
        of one or more friendly ADEPTUS MECHANICUS BATTLELINE units..."

    This gate scopes the Protector defensive -1 to Hit (melee attacks
    targeting the AdMech unit) and the Conqueror +1 AP buff to the
    AdMech-side units that are themselves BATTLELINE (Skitarii Rangers,
    Skitarii Vanguard) or which are coordinating with one within 6".
    The +1 BS / WS portion of each imperative is genuinely army-wide and
    is NOT gated by this helper.

    Cited as `simulator.doctrina_imperatives`. Returns False when the unit
    has no army_ref (defensive) — the gate fails-closed in that edge case
    so a stray test profile cannot silently receive the gated bonus.
    """
    kws = unit.profile.unit_keywords or ()
    if "BATTLELINE" in kws:
        return True
    own_army = getattr(unit, "army_ref", None)
    if own_army is None:
        return False
    ux, uy = unit.position
    r2 = 6.0 * 6.0
    for ally in own_army.alive_units:
        if ally is unit:
            continue
        if ally.profile.faction != "Adeptus Mechanicus":
            continue
        if "BATTLELINE" not in (ally.profile.unit_keywords or ()):
            continue
        ax, ay = ally.position
        dx = ax - ux
        dy = ay - uy
        if dx * dx + dy * dy <= r2:
            return True
    return False


def save_probability(
    save: int, ap: int = 0, in_cover: bool = False, is_infantry: bool = True
) -> float:
    """
    Probability of passing an armour save roll on a d6.

    save:         the unit's base save characteristic (e.g. 3 means 3+)
    ap:           weapon AP modifier (negative integer, e.g. -1 degrades save by 1)
    in_cover:     cover improves save by 1 pip (e.g. 4+ → 3+)
    is_infantry:  whether the model has the INFANTRY keyword. Per 10e
                  Benefits of Cover (Wahapedia core rules — Terrain Features
                  / Benefits of Cover): "INFANTRY models cannot improve
                  their Save characteristic to better than 3+ by virtue of
                  this rule." Vehicles / monsters / mounted models do not
                  share the 3+ cap. Hard armour-save floor (2+) still
                  applies regardless. Defaults to True so legacy callers
                  that did not pass the flag keep the rule-correct
                  behaviour for the typical case.
    """
    effective = save - ap                       # AP-1 on a 3+ → 4+
    if in_cover:
        improved = effective - 1                # cover: improve by 1 pip
        if is_infantry:
            # Cover cannot improve an INFANTRY save to better than 3+.
            # If the model's effective save is already 3+ or better, cover
            # adds nothing (and must NOT degrade the save). Otherwise
            # clamp the improvement at 3+.
            improved = max(improved, 3)
        improved = max(2, improved)              # universal 2+ armour floor
        # Cover never makes a save worse than it already was.
        effective = min(effective, improved)
    if effective > 6:
        return 0.0                              # save negated entirely
    return max(0.0, (7 - effective) / 6)


def _baseline_survival() -> float:
    """Fraction of hits that get through against a baseline Marine (no AP, no cover)."""
    return 1.0 - save_probability(BASELINE_SAVE, BASELINE_AP)


def points_for(
    health: float,
    damage: float,
    hit_prob: float,
    ap: int = 0,
    save: int = 7,
    strength: int = BASELINE_STRENGTH,
    toughness: int = BASELINE_TOUGHNESS,
) -> float:
    """
    Points cost relative to the baseline Space Marine.

    Offensive ratio: expected unsaved damage this unit does to a baseline Marine
    (hit × wound vs T4 × unsaved vs 3+) divided by what a Marine does.

    Defensive ratio: expected hits-to-kill this unit by a baseline Marine, vs
    the baseline against itself.

    The two ratios are averaged (not multiplied) to prevent runaway costs for
    units that are dominant on both axes.
    """
    attacker_wound = wound_probability(strength, BASELINE_TOUGHNESS)
    offensive = damage * hit_prob * attacker_wound * (1.0 - save_probability(BASELINE_SAVE, ap))

    baseline_wound = wound_probability(BASELINE_STRENGTH, BASELINE_TOUGHNESS)
    baseline_offensive = BASELINE_DAMAGE * BASELINE_HIT_PROB * baseline_wound * _baseline_survival()
    off_ratio = offensive / baseline_offensive

    incoming_wound = wound_probability(BASELINE_STRENGTH, toughness)
    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    if incoming_wound <= 0:
        incoming_wound = 1e-6
    durability = health / (incoming_wound * survive_chance)

    baseline_incoming_wound = wound_probability(BASELINE_STRENGTH, BASELINE_TOUGHNESS)
    baseline_survive = 1.0 - save_probability(BASELINE_SAVE)
    baseline_durability = BASELINE_HEALTH / (baseline_incoming_wound * baseline_survive)
    dur_ratio = durability / baseline_durability

    effectiveness = (off_ratio + dur_ratio) / 2.0
    return round(BASELINE_POINTS * effectiveness, 1)


def lanchester_score(
    health: float,
    damage: float,
    hit_prob: float,
    ap: int = 0,
    save: int = 7,
    strength: int = BASELINE_STRENGTH,
    toughness: int = BASELINE_TOUGHNESS,
) -> float:
    """Lanchester priority score: dps × durability (used for activation order)."""
    attacker_wound = wound_probability(strength, BASELINE_TOUGHNESS)
    dps = damage * hit_prob * attacker_wound * (1.0 - save_probability(BASELINE_SAVE, ap))

    incoming_wound = wound_probability(BASELINE_STRENGTH, toughness)
    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    if incoming_wound <= 0:
        incoming_wound = 1e-6
    durability = health / (incoming_wound * survive_chance)
    return dps * durability


# ---------------------------------------------------------------------------
# Astra Militarum SQUADRON allowlist — see the SQUADRON-leg gate in
# Unit.attack() for the Born Soldiers Combined Arms detachment rule. BSData
# v10.6.0 does not tag datasheets with the codex SQUADRON keyword, so we
# match on `UnitProfile.name`. Per Wahapedia AM datasheets (see
# https://wahapedia.ru/wh40k10ed/factions/astra-militarum/ ), the SQUADRON
# keyword belongs to the Leman Russ family, the Rogal Dorn family, the
# Hellhound (Bane Wolf / Devil Dog are weapon-loadout variants of the
# Hellhound datasheet in BSData v10.6.0), and the Sentinels.
# ---------------------------------------------------------------------------
_AM_BORN_SOLDIERS_SQUADRON_NAMES = frozenset({
    # Leman Russ family
    "Leman Russ Battle Tank",
    "Leman Russ Demolisher",
    "Leman Russ Eradicator",
    "Leman Russ Executioner",
    "Leman Russ Exterminator",
    "Leman Russ Punisher",
    "Leman Russ Vanquisher",
    "Leman Russ Commander",
    # Rogal Dorn family
    "Rogal Dorn Battle Tank",
    "Rogal Dorn Commander",
    # Hellhound family (Bane Wolf / Devil Dog are weapon-loadout variants
    # of the Hellhound datasheet in BSData v10.6.0 — no separate entry).
    "Hellhound",
    # Sentinels
    "Armoured Sentinels",
    "Scout Sentinels",
    "Sentinel Commander [Crucible]",
})


# ---------------------------------------------------------------------------
# UnitProfile — immutable stat block
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnitProfile:
    """Immutable stat block for a unit type."""

    name: str
    health: float
    damage: float                              # damage per unsaved hit
    hit_probability: float                     # probability of landing a hit (e.g. 2/3 for 3+)
    ap: int = 0                                # armour penetration modifier (0, -1, -2, -3 …)
    save: int = 7                              # armour save characteristic (7 = no save)
    strength: int = BASELINE_STRENGTH          # weapon strength used in the wound roll
    toughness: int = BASELINE_TOUGHNESS        # unit toughness defended in the wound roll
    move: float = 6.0                          # movement allowance in inches per activation
    range_inches: int = 24                     # weapon range; melee-only units use 1
    faction: str = ""                          # canonical faction tag for UI grouping / colours
    min_models: int = 1                        # smallest legal squad size (1 for single-model units)
    max_models: int = 1                        # largest legal squad size
    points_per_squad: float = 0.0              # BSData cost for a min-size squad (informational)
    # Per-shot damage decomposition — Unit.attack() loops `attacks` times per
    # activation, applying weapon_damage_per_shot each time. `damage` stays as
    # the per-activation total (= attacks * weapon_damage_per_shot) so the
    # points formula and UI displays don't change.
    attacks: int = 1
    weapon_damage_per_shot: float = 0.0        # 0 = derive damage / attacks at use site
    # Weapon abilities (parsed from BSData Keywords field by the mapper)
    lethal_hits: bool = False                  # critical hit (6 to hit) auto-wounds
    sustained_hits: int = 0                    # critical hit generates N extra normal hits (RANGED weapon)
    # Melee-side SUSTAINED HITS — populated by the mapper from the chosen
    # melee weapon's keywords. Read by Unit.attack when `mode == "melee"` so
    # a ranged-only SUSTAINED HITS N does not leak into melee resolution.
    melee_sustained_hits: int = 0
    twin_linked: bool = False                  # re-roll failed wound rolls
    devastating_wounds: bool = False           # critical wound (6 to wound) bypasses saves
    invuln_save: int = 7                       # invulnerable save (7 = none); use better of save-after-AP or invuln
    leadership: int = 7                        # Ld target for Battleshock tests (10e: 2D6 >= Ld passes)
    oc: int = 1                                # Objective Control characteristic (10e)
    # Phase A2 + A3 weapon keywords (carried from the unit's chosen ranged weapon)
    rapid_fire: int = 0                        # +N attacks at half range
    melta: int = 0                             # +N damage per shot at half range
    ignores_cover: bool = False                # target cover save bonus does not apply
    anti_keywords: Tuple[Tuple[str, int], ...] = ()  # ((keyword, threshold), ...) — tuple for hashability
    heavy: bool = False                        # +1 to hit if attacker did not move this turn
    assault: bool = False                      # can shoot after Advance
    torrent: bool = False                      # attacks auto-hit (skip to-hit roll)
    hazardous: bool = False                    # d6 self-harm on activation (1 = 3 mortal wounds)
    blast: bool = False                        # +1 attack per 5 enemy models in target unit
    # Phase F — niche 10e weapon keywords
    lance: bool = False                        # +1 to wound on melee if the unit charged this turn
    precision: bool = False                    # bypass cover when shooting a CHARACTER target
    pistol: bool = False                       # can shoot while in engagement (1.5") range
    # MAP-MULTIFIRE-VALIDATE — name of the primary ranged weapon (BSData
    # weapon profile name on the unit's best-legal ranged loadout entry).
    # Stamped by the mapper from `primary.name` so the simulator's
    # multi-profile picker can detect mode-alternates (sibling weapon
    # profiles whose names differ only by a trailing mode suffix like
    # `" - focused mode"`, `" - dispersed mode"`, `" - standard"`,
    # `" - supercharge"`, etc.). 10e core rule: a weapon with multiple
    # firing modes fires ONE mode per Shooting phase, not all of them
    # together. Empty string = legacy profile that predates the field.
    # Cited as `simulator.multi_profile_weapon_selection`.
    weapon: str = ""
    # MAP-MULTIFIRE-VALIDATE — Pistol keyword carried on the SECONDARY
    # ranged profile (the primary's pistol flag lives in `pistol` above).
    # 10e core rule (Wahapedia, Core Rules → Weapons → Pistols): "A model
    # armed with one or more Pistols cannot shoot any non-Pistol weapons
    # in the same turn (and vice versa)." The picker partitions profiles
    # into pistol / non-pistol groups and fires exactly one group per
    # activation. Cited as `simulator.pistol_exclusivity`.
    secondary_pistol: bool = False
    indirect_fire: bool = False                # ignores LoS; -1 to hit vs non-visible targets
    one_shot: bool = False                     # weapon fires once per battle
    # Phase H — Stealth (-1 to be hit when shot at)
    stealth: bool = False
    # Lone Operative (10e core ability). A unit with this ability can only be
    # targeted by a ranged attack if the attacking model is within 12" of it.
    # Parsed from BSData by the mapper when a "Lone Operative" infoLink /
    # profile is attached to the datasheet. Cited as
    # `simulator.lone_operative`.
    lone_operative: bool = False
    # FIGHTS FIRST datasheet keyword (10e core, Fight phase priority). When
    # True, this unit fights in the Fights First step of the Fight phase
    # alongside chargers, ahead of the Remaining Combats step. Parsed from
    # BSData by the mapper via `extract_fights_first`. Cited as
    # `simulator.fights_first_keyword`.
    fights_first: bool = False
    # Phase I — deployment abilities (decided pre-Round 1 by the simulator)
    deep_strike: bool = False                  # starts in Reserves; arrives from Round 2
    scout_distance: int = 0                    # pre-game Normal Move up to N inches
    infiltrator: bool = False                  # deploys past the standard deployment line
    fnp: int = 7                               # Feel No Pain target (7 = none); roll after each unsaved wound
    deadly_demise: int = 0                     # Deadly Demise X (10e core): when destroyed, d6; on 6, each unit within 6" suffers X mortal wounds. Integer expected value (D3→2, D6→3, D3+3→5, N→N). Cited as `simulator.deadly_demise`.
    firing_deck: int = 0                       # Firing Deck X (10e core, TRANSPORT keyword): up to X embarked passenger models may also shoot using the transport's BS each Shooting phase. 0 = no Firing Deck. Cited as `simulator.firing_deck`.
    sticky_objective: bool = False             # 10e Objective Secured / "remains controlled when the unit leaves" — once this unit claims an objective, ownership persists until an opposing unit takes it back
    # 10e datasheet ability — Resolute Will (Custodian Wardens).
    # Wahapedia: "While a CHARACTER is leading this unit, each time an
    # attack targets this unit, if the Strength characteristic of that
    # attack is greater than the Toughness characteristic of this unit,
    # subtract 1 from the Wound roll." Wired in Unit.attack as a
    # defender-side wound_mod_delta -1 gated by: (a) defender carries
    # this flag, (b) defender is actually led (host_keys check via
    # leaders.is_actually_led), (c) attack.strength > defender.toughness.
    # Cited as `simulator.resolute_will`.
    resolute_will: bool = False
    # NECRONS-CTAN — Necrodermis (C'tan datasheet ability). Each time an
    # attack is allocated to this model, halve the Damage characteristic
    # (rounding up); D1 attacks deal 0 damage. Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/necrons/. Applied at the
    # per-shot damage allocation sites in Unit.attack (both the
    # devastating-wounds bypass path and the failed-save path). Cited as
    # `UnitProfile.necrodermis`.
    necrodermis: bool = False
    # MAP-4 — per-unit Reanimation Protocols eligibility flag.
    # 10e Necron datasheets all CARRY the "Reanimation Protocols" ability, but
    # the ability text excludes CHARACTER / MONSTER / VEHICLE models from
    # benefiting (the bodyguard-led-by-character case is handled separately
    # downstream when leader attachments resolve). True iff the datasheet
    # carries the Reanimation Protocols infoLink AND is not a CHARACTER,
    # MONSTER, or VEHICLE. Populated by the BSData mapper. Read by
    # opponent-side target-priority logic so non-reanimating Necron units
    # (C'tan Shards, Doomstalker, Doomsday Ark, Lokhust Heavy Destroyers,
    # Monolith, Tesseract Vault, etc.) are not penalised the way reanimating
    # bodies are. Cited as `simulator.reanimation_protocols`.
    # Source: https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols
    reanimates_with_army: bool = False
    unit_keywords: Tuple[str, ...] = ()        # 10e keywords (INFANTRY, VEHICLE, etc.) for Anti-X targeting
    # Phase B — melee profile (engagement range 1"). 0 = no usable melee profile.
    melee_attacks: int = 0
    melee_damage_per_shot: float = 0.0
    melee_hit_probability: float = 0.0
    melee_strength: int = 4
    melee_ap: int = 0
    melee_weapon: str = ""
    # ---- Phase 2 / iter33 — secondary RANGED weapon profile -----------------
    # Datasheets like the Stormsurge (Pulse Driver Cannon 72" Heavy D6+3 shots
    # of D3 dmg vs Pulse Blastcannon-focused 18" 2-shot D12) carry two distinct
    # ranged profiles that real 10e play picks between based on range / target.
    # The mapper records the runner-up profile here; Unit.attack's ranged
    # branch picks whichever profile has higher expected damage against the
    # current target at the current distance. `secondary_attacks == 0` means
    # no secondary profile is available (most units). Cited as
    # `simulator.multi_profile_weapon_selection`.
    secondary_attacks: int = 0
    secondary_weapon_damage_per_shot: float = 0.0
    secondary_hit_probability: float = 0.0
    secondary_ap: int = 0
    secondary_strength: int = 4
    secondary_range_inches: int = 0
    secondary_weapon: str = ""
    secondary_anti_keywords: Tuple[Tuple[str, int], ...] = ()
    secondary_lethal_hits: bool = False
    secondary_sustained_hits: int = 0
    secondary_twin_linked: bool = False
    secondary_devastating_wounds: bool = False
    secondary_rapid_fire: int = 0
    secondary_melta: int = 0
    secondary_ignores_cover: bool = False
    secondary_heavy: bool = False
    secondary_assault: bool = False
    secondary_torrent: bool = False
    secondary_blast: bool = False
    # ---- MAP-1 — TERTIARY and beyond RANGED weapon profiles ------------------
    # Generalises the multi-profile picker from 2 to N. Knight Castellan fires
    # five ranged weapons (Volcano Lance + Plasma Decimator + Twin Meltagun +
    # Shieldbreaker Missiles + Twin Siegebreaker Cannon) in real 10e games;
    # the primary/secondary fields above carry the two strongest, this tuple
    # carries the rest. Each entry is a tuple of (key, value) pairs (so the
    # field stays hashable / dataclass-friendly) holding the same stat fields
    # as the secondary block plus the weapon name. The simulator's per-shot
    # picker iterates over every available profile (primary, secondary,
    # extras) and routes to the profile with the highest expected damage
    # against the current target at the current range. Empty tuple = no
    # extra profiles (most units). Cited as
    # `simulator.multi_profile_weapon_selection`.
    extra_ranged_profiles: Tuple[Tuple[Tuple[str, Any], ...], ...] = ()
    # ---- KNIGHTS-MULTIPROFILE-2 — ADDITIONAL melee weapon profiles ----------
    # Knight Abominant fires its Electroscourge AND its Balemace in the same
    # Fight phase (balemace carries the [EXTRA ATTACKS] core-rules keyword,
    # which means it is resolved IN ADDITION to the model's other melee
    # attacks rather than replacing them). Knight Rampager carries BOTH a
    # Reaper chainsword AND a Warpstrike claw as datasheet wargear; both
    # fire in the same Fight phase. The primary melee_* block above carries
    # ONE such weapon's profile (the one BSData picks first); this tuple
    # carries the rest. Each entry is a tuple of (key, value) pairs (so the
    # field stays hashable / dataclass-friendly) holding the melee weapon-
    # attack contract: weapon, attacks, weapon_damage_per_shot,
    # hit_probability, ap, strength, plus keyword flags (sustained_hits_1,
    # lethal_hits, devastating_wounds, lance, anti_keywords, precision,
    # twin_linked, extra_attacks). Empty tuple = no extras (most units).
    # Unlike the RANGED extra_ranged_profiles list (which is MUTEX — the
    # picker chooses one alt-mode per group), extra_melee_profiles is
    # ADDITIVE: every entry fires alongside the primary melee attack in
    # the same Fight phase against the same engaged target. Cited as
    # `simulator.extra_melee_profiles`.
    extra_melee_profiles: Tuple[Tuple[Tuple[str, Any], ...], ...] = ()
    # MAP-3-FIX — basket-fraction gating for partial-coverage weapon keywords.
    # The MAP-3 UNION (any-weapon-in-basket carries the keyword) inflates
    # damage for heterogeneous squads (Rubric Marines, Skyweavers, Beast
    # Snagga Boyz, AdMech Skitarii) because every shot in the synthetic
    # average inherits the keyword. These fractions tell Unit.attack what
    # fraction of basket weight legitimately carries the keyword, so a
    # Bernoulli draw can gate each shot. Default 1.0 = legacy behaviour:
    # the keyword fires on every shot. Set < 1.0 only by the mapper for
    # heterogeneous squads. Cited as `simulator.basket_fraction_gating`.
    devastating_wounds_basket_fraction: float = 1.0
    lance_basket_fraction: float = 1.0
    anti_keyword_basket_fractions: Tuple[Tuple[str, float], ...] = ()
    points_override: float = 0.0               # 0 = use derived points_cost; >0 wins (used by the balancer)
    # ---- Renderer-only: real-world GW model base footprint ---------------
    # Informational only — the simulator's collision / range logic still
    # uses the 0.5" abstraction. Three shape families:
    #   "circle" — INFANTRY / most CHARACTERs (GW round bases: 25-170mm)
    #   "rect"   — most VEHICLEs (rectangular footprint, no GW standard size)
    #   "oval"   — flying / monstrous / BIKE (GW oval bases: 60x35..170x105mm)
    # Default = 32mm round (standard Marine). The renderer maps mm to world
    # inches at 25.4 mm/inch via `code.renderer._mm_to_inches`.
    base_shape: str = "circle"
    base_diameter_mm: int = 32                 # used when base_shape == "circle"
    base_width_mm: int = 32                    # used when base_shape == "rect" or "oval"
    base_length_mm: int = 32                   # used when base_shape == "rect" or "oval"

    @property
    def fly(self) -> bool:
        """True if this unit has the FLY keyword (10e). Derived from
        ``unit_keywords`` so the mapper does not need a separate field —
        BSData already tags every FLY datasheet with the keyword. Used by
        the simulator's Fall Back gate (units with FLY may still shoot /
        charge after Falling Back; everyone else may not). Cited as
        ``simulator.fall_back``.
        """
        return "FLY" in (self.unit_keywords or ())

    @property
    def avg_damage_per_action(self) -> float:
        """Expected damage dealt per activation against a baseline Marine."""
        wound_p = wound_probability(self.strength, BASELINE_TOUGHNESS)
        unsaved = 1.0 - save_probability(BASELINE_SAVE, self.ap)
        return self.damage * self.hit_probability * wound_p * unsaved

    @property
    def per_shot_damage(self) -> float:
        """Damage per individual to-hit roll. Derived if not set explicitly."""
        if self.weapon_damage_per_shot > 0:
            return self.weapon_damage_per_shot
        return self.damage / max(1, self.attacks)

    @property
    def points_cost(self) -> float:
        """Per-model points cost in the simulator's currency.

        Resolution order:
          1. Sweg-balancer override (`points_override > 0`) wins outright.
          2. GW canonical: `points_per_squad / min_models` when BSData
             populated both. This is the printed datasheet cost.
          3. Fallback: Lanchester-derived `points_for(...)` — used for
             synthetic test profiles that have no BSData provenance.

        The 2026-05 fix (Ed's TODO in PROJECT.tex `\eddie` commit
        `a0d7702`): the property previously returned the Lanchester score
        always, so every sim-side army budget ran in wrong-currency.
        Sub-1 GW costs are clamped to 1.0 so degenerate cases (a hypothetical
        free unit) don't divide-by-zero in downstream callers.
        """
        if self.points_override and self.points_override > 0:
            return float(self.points_override)
        if self.points_per_squad > 0 and self.min_models > 0:
            return max(1.0, self.points_per_squad / self.min_models)
        # Clamp the Lanchester fallback to 1.0 like the GW branch above. A
        # zero-cost profile would be eternally affordable in
        # build_random_army's affordability loop, leaking memory until OOM.
        return max(1.0, points_for(
            self.health, self.damage, self.hit_probability,
            self.ap, self.save, self.strength, self.toughness,
        ))

    @property
    def score(self) -> float:
        return lanchester_score(
            self.health, self.damage, self.hit_probability,
            self.ap, self.save, self.strength, self.toughness,
        )

    def __str__(self) -> str:
        save_str = f"{self.save}+" if self.save <= 6 else "none"
        ap_str = str(self.ap) if self.ap != 0 else "0"
        return (
            f"{self.name} "
            f"[H:{self.health} D:{self.damage} Hit:{self.hit_probability:.0%} "
            f"S:{self.strength} T:{self.toughness} AP:{ap_str} Sv:{save_str} "
            f"Pts:{self.points_cost}]"
        )


# ---------------------------------------------------------------------------
# Unit — mutable battle instance
# ---------------------------------------------------------------------------

class Unit:
    """A live unit on the battlefield, tracking current health and position."""

    __slots__ = (
        "profile", "_current_health", "in_cover", "in_heavy_cover", "uid", "position",
        "army_ref", "moved_this_round", "on_objective", "shooting_in_engagement",
        # Set by Battle._do_move when the unit elects the FALL_BACK intent.
        # While True, _do_shoot and _do_charge refuse to fire the unit unless
        # its profile has the FLY keyword. Cleared at the top of each round.
        # Cited as `simulator.fall_back`.
        "fell_back_this_round",
        # ----- transient stratagem flags (cleared each round by Battle) -----
        # Cult of Magic (Thousand Sons):
        #   transient_plus_one_to_wound_shooting — Twist of Fate. Attacker buff:
        #       +1 to wound on ranged attacks made by this unit for the round.
        #   transient_invuln_4 — Glamour of Tzeentch. Defender buff: target gets
        #       a transient 4++ invulnerable save for the round.
        # Plague Company (Death Guard):
        #   transient_minus_one_damage_taken — Disgustingly Resilient. Defender
        #       buff: each per-shot damage reduced by 1 (floor 1) for the round.
        #   transient_plus_one_to_wound_melee — Outbreak of Pestilence. Attacker
        #       buff: +1 to wound on melee attacks for the round.
        # Warhost (Aeldari, was "Battle Host" pre-#197):
        #   transient_plus_one_save — Lightning-Fast Reactions (also reused by
        #       Skyborne Sanctuary and Webway Tunnel as defensive proxies).
        #       Defender buff: +1 to armour save (cap 2+) for the round.
        #   transient_reroll_hits_shooting — Fire and Fade. Attacker buff: failed
        #       hit rolls in shooting are re-rolled (once) for the round.
        #   transient_plus_one_to_hit_shooting — Blitzing Firepower (Warhost
        #       proxy for Sustained Hits 1). Attacker buff: +1 to hit on ranged
        #       attacks for the round. Reused by Methodical Destruction too.
        #   transient_assault_this_round — Feigned Retreat (Warhost), Strike
        #       Swiftly (T'au Mont'ka). Movement buff: unit may shoot in the
        #       same round it advanced.
        # Awakened Dynasty (Necrons):
        #   transient_fnp_5 — (legacy slot, retained for stable layout) was
        #       Implacable Onslaught, deleted in the fabrication audit. Now
        #       reused if a future Necron stratagem grants FNP 5+.
        #   transient_plus_one_to_hit_shooting — (legacy slot, retained) was
        #       Methodical Destruction, deleted in the fabrication audit. Now
        #       a generic +1-to-hit-shooting slot any stratagem can set.
        #   transient_undying_legions_pulse — Protocol of the Undying Legions
        #       (Awakened Dynasty, 1 CP). When set, the affected NECRONS unit
        #       gets one extra mid-round reanimation pulse equal to this
        #       integer wound count. Consumed + reset by
        #       Battle._apply_undying_legions_pulse and the round-clear hook.
        # Saim-Hann (Aeldari):
        #   transient_halve_damage — Spirit Stones. Defender buff: each per-shot
        #       damage is halved (rounded up) for the round.
        "transient_plus_one_to_wound_shooting",
        "transient_invuln_4",
        "transient_minus_one_damage_taken",
        "transient_plus_one_to_wound_melee",
        "transient_plus_one_save",
        "transient_reroll_hits_shooting",
        "transient_assault_this_round",
        "transient_fnp_5",
        "transient_plus_one_to_hit_shooting",
        "transient_halve_damage",
        "transient_undying_legions_pulse",
        # ST-1: proper transient keyword-grant slots. Replace the over-strong
        # +1-to-hit / +1-to-wound proxies that were standing in for stratagems
        # which actually grant LETHAL HITS / SUSTAINED HITS / wound re-rolls.
        # transient_lethal_hits: critical hit (6 to hit) auto-wounds for the
        # round, composed via OR with profile.lethal_hits and the other
        # army-rule lethal_hits sources at the crit-to-hit branch.
        # transient_sustained_hits: extra hits on crit, additive to
        # effective_sustained_hits (matches detachment / army-wide stacking).
        # transient_reroll_wounds: full failed-wound re-roll for the round.
        # transient_reroll_wounds_ones: 1s-only wound re-roll for the round
        # (lossy but correctly weaker proxy for "reroll 1s" stratagems).
        "transient_lethal_hits",
        "transient_sustained_hits",
        "transient_reroll_wounds",
        "transient_reroll_wounds_ones",
        # Skysplinter Assault (Drukhari detachment) — Rain of Cruelty. Set
        # True on a DRUKHARI unit when it disembarks from a TRANSPORT this
        # turn while the army's detachment is Skysplinter Assault. Persists
        # until the standard transient-flag reset at the next round start
        # (rule wording: "until the end of the turn"). The LANCE flag is
        # composed via OR with `profile.lance` at the lance eligibility
        # gate; the IGNORES-COVER flag is composed via OR with
        # `profile.ignores_cover` at the ranged ignore_cover gate (melee
        # already always ignores cover). Cited as
        # `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark`.
        "transient_lance_this_turn",
        "transient_ignores_cover_this_turn",
        # Drukhari Power From Pain (army rule, 10e). Awarded at the start of
        # each Command phase to any Drukhari unit below Starting Strength;
        # capped at 1 per unit. While > 0, the unit's models gain Lethal Hits
        # and FNP 6+. Persists across rounds (not cleared with the transient
        # stratagem flags). Cited as `simulator.power_from_pain`.
        "pain_tokens",
        # Genestealer Cults Cult Ambush (army rule, 10e). Flagged True at
        # deployment time for every GSC unit; the Battle._arrive_from_reserves
        # path consumes it at the top of Round 1 to place the unit > 9"
        # from any enemy model (regular Deep Strikers still wait until
        # Round 2). Cleared once the unit lands. Cited as
        # `simulator.cult_ambush`.
        "cult_ambush_pending",
        # GSC-DIAG: True once this unit has been revived via Cult Ambush
        # Resurgence (the per-destruction revival half of the army rule).
        # Prevents the proxy from ping-ponging a single unit through
        # multiple revivals when one unit dies, revives, and dies again
        # in the same battle. The codex "Add a new unit identical to
        # your destroyed unit" phrasing implies the revived unit is a
        # fresh entity, but at the proxy level we collapse this to
        # one-revival-per-original-unit so the same slot doesn't churn
        # the entire Resurgence pool by itself.
        "cult_ambush_revived",
        # 10e Enhancement (Warlord upgrade). Assigned to a single CHARACTER
        # per army by the army builder; None on every other unit. Read by
        # `leaders.effective_buffs` when this unit is an in-range friendly
        # CHARACTER to merge its aura flags into the attacker's buff dict.
        # See `code/enhancements.py` for the dataclass + registry.
        "enhancement",
        # Drukhari Combat Drugs (army rule, 10e). One drug is assigned per
        # WYCH CULT unit at battle start; the buff persists for the entire
        # battle (Wahapedia: drug stays active once selected). The four
        # SwegHammer-modelled drugs map to per-unit integer/float deltas
        # applied in `Unit.attack` (melee branch) and
        # `detachments.effective_move`:
        #   combat_drug_extra_melee_attacks — Adrenalight (+1 Attack on melee weapons).
        #   combat_drug_melee_strength_bonus — Grave Lotus (+1 Strength on melee weapons).
        #   combat_drug_toughness_bonus — Painbringer (+1 Toughness, defensive).
        #   combat_drug_move_bonus — Hypex (+2" Move).
        # Serpentin (+1 WS) and Splintermind (+1 Ld / +1 BS) are NOT modelled —
        # APPROXIMATION: the existing per-unit Hit profile already encodes the
        # post-improvement hit chance for stock loadouts and the simulator has
        # no Leadership-driven gating outside Battle-shock thresholds the four
        # WYCH CULT units already beat. Cited as `simulator.combat_drugs`.
        "combat_drug_extra_melee_attacks",
        "combat_drug_melee_strength_bonus",
        "combat_drug_toughness_bonus",
        "combat_drug_move_bonus",
        # Transport state (10e core). `passengers` is a list of Unit instances
        # currently embarked inside this transport (only populated when the
        # owning profile has TRANSPORT in its unit_keywords). Passengers are
        # removed from the live battlefield (army.alive_units still returns
        # them because they're still alive HP-wise, but their position is the
        # transport's position and the simulator skips their activations
        # while they're embarked). `embarked_in` is the back-pointer set on
        # the passenger pointing at its carrier; None when not embarked.
        # Cited as `simulator.embark` / `simulator.disembark`.
        "passengers",
        "embarked_in",
        # BS-1: per-unit persistent battleshock state. Populated by
        # `simulator._run_battleshock_phase` when this unit fails its test in
        # the Command phase. The value stored is the round_num through which
        # the unit is battle-shocked (the test fires at the start of a
        # Command phase and the status lasts "until the start of your next
        # Command phase" — i.e. for the rest of that round). Downstream
        # consumers (Synapse Imperative, future Harbingers of Dread, future
        # Repentia explosive death, etc.) read via
        # `is_currently_battle_shocked(round_num)`. Default 0 = never failed
        # a test. Cleared by the next round's Battle-shock phase (the same
        # call that re-tests the unit). Cited as `simulator.battleshock`.
        "battleshocked_until_round",
        # SOROR-DIAG-4: Adepta Sororitas Acts of Faith per-round budget.
        # The codex caps Acts of Faith at one per phase per unit; SOROR-DIAG-3
        # left the substitution gated only by a per-attack() local flag, which
        # let a defender spend one Miracle die per ATTACKING ENEMY across a
        # whole shooting / fight phase (each enemy attacker enters attack()
        # with a fresh flag, so the defender's defensive substitution branch
        # could fire dozens of times per phase). SOROR-DIAG-4 promotes the
        # flag onto the Unit itself and resets it once per round in
        # `Battle._run_round`, capping each Sororitas unit at one Act of
        # Faith per round across BOTH offensive (its own attack() calls) and
        # defensive (incoming attack() calls on this unit). Tighter than the
        # codex literal (which would permit one per phase, i.e. up to four
        # per round across Move / Shoot / Charge / Fight), chosen
        # conservatively because SOROR-DIAG-3 left Sororitas at +14.39pt
        # over-performance after the bank cap was already tightened to 5.
        # Cited as `simulator.acts_of_faith`.
        "aof_used_this_round",
        # CSM-EYE-OF-GODS: Eye of the Gods stratagem stamp (Pactbound Zealots,
        # 1 CP). Set True the first time this CHARACTER destroys an enemy
        # unit with a melee attack AND the stratagem fires. While True, the
        # CHARACTER gains a persistent +1 to wound on its own melee attacks
        # for the rest of the battle. APPROXIMATION: the real Eye of the
        # Gods rolls D6+Wounds on a table that grants +M / +T / +A/+S /
        # +D melee depending on the roll; we collapse to +1-to-wound-melee
        # because that's the closest single-flag analogue to the snowball.
        # Persistent (NOT cleared with the round-start transient_* flags).
        # Cited as `Stratagem.Eye of the Gods`.
        "eye_of_the_gods_stamped",
    )

    def __init__(self, profile: UnitProfile, in_cover: bool = False) -> None:
        self.profile = profile
        self._current_health: float = profile.health
        self.in_cover: bool = in_cover
        # Set by Battle._do_shoot when the target stands in HEAVY_COVER terrain.
        # Drives the -1-to-hit penalty (in addition to the +1-to-save the
        # plain in_cover flag already grants). Restored to False after shot.
        self.in_heavy_cover: bool = False
        self.uid: str = ""                              # assigned by Battle at start
        self.position: tuple = (0.0, 0.0)               # (x, y) in inches
        # Back-reference to owning army (set by Army.add_unit). Lets
        # Unit.attack() resolve the army-wide detachment + check squad size
        # for keywords like Blast.
        self.army_ref = None
        # Set by Battle each round: True iff this unit moved during the
        # current round's movement sub-phase. Drives the Heavy keyword
        # (+1 to hit if attacker did NOT move).
        self.moved_this_round: bool = False
        # Set per round by Battle._run_round: True if the unit's position
        # is within control range of any objective marker. Read by
        # Unit.attack() to gate detachment buffs like Awakened Dynasty's
        # objective_holder_bonus_to_wound.
        self.on_objective: bool = False
        # Toggled by Battle._do_shoot: True if this VEHICLE/MONSTER unit
        # is firing while inside an enemy's engagement range (Big Guns
        # Never Tire). Triggers a -1 to hit modifier per 10e core rules.
        self.shooting_in_engagement: bool = False
        # Transient stratagem flags. Cleared every round by Battle._run_round
        # before the new round's stratagems are decided. Documented on the
        # __slots__ tuple above; default False on construction.
        self.transient_plus_one_to_wound_shooting: bool = False
        self.transient_invuln_4: bool = False
        self.transient_minus_one_damage_taken: bool = False
        self.transient_plus_one_to_wound_melee: bool = False
        self.transient_plus_one_save: bool = False
        self.transient_reroll_hits_shooting: bool = False
        self.transient_assault_this_round: bool = False
        # Awakened Dynasty (Necrons) per-round stratagem flags.
        self.transient_fnp_5: bool = False
        self.transient_plus_one_to_hit_shooting: bool = False
        # Saim-Hann (Aeldari) per-round stratagem flag.
        self.transient_halve_damage: bool = False
        # Awakened Dynasty (Necrons) Protocol of the Undying Legions: integer
        # number of wounds to reanimate in a follow-up pulse. 0 = no pulse.
        self.transient_undying_legions_pulse: int = 0
        # ST-1 proper-keyword transient flags (see __slots__ above for the
        # full rationale and citation linkage).
        self.transient_lethal_hits: bool = False
        self.transient_sustained_hits: int = 0
        self.transient_reroll_wounds: bool = False
        self.transient_reroll_wounds_ones: bool = False
        # Skysplinter Assault (Drukhari detachment) Rain of Cruelty:
        # disembark-turn LANCE on melee weapons + IGNORES COVER on ranged
        # weapons. Set in `simulator._disembark` when the disembarking
        # unit is Drukhari AND the army's detachment is Skysplinter
        # Assault; cleared with the other transient flags at the next
        # round-start by `simulator._clear_transient_stratagem_flags`.
        # Cited as `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark`.
        self.transient_lance_this_turn: bool = False
        self.transient_ignores_cover_this_turn: bool = False
        # Power From Pain (Drukhari army rule). 0 = none, 1 = active (cap).
        self.pain_tokens: int = 0
        # Cult Ambush (Genestealer Cults army rule). True means the unit is
        # waiting to land at the top of Round 1 via the simulator's reserves
        # path; cleared the moment it arrives on the battlefield. See
        # `simulator.cult_ambush` citation for the verbatim Wahapedia quote.
        self.cult_ambush_pending: bool = False
        # GSC-DIAG: Cult Ambush Resurgence one-shot guard. See __slots__ comment.
        self.cult_ambush_revived: bool = False
        # Fall Back (10e core). Set True by Battle._do_move when the unit
        # elects the FALL_BACK intent; gates _do_shoot / _do_charge unless
        # the profile has FLY. Reset at the top of each round.
        self.fell_back_this_round: bool = False
        # 10e Enhancement (Warlord upgrade). Defaults to None; the army
        # builder sets this on exactly one CHARACTER per army at construction
        # time. `leaders.effective_buffs` reads this field through any
        # in-range friendly CHARACTER to compose its aura into the attacker's
        # buff dict.
        from typing import Optional
        self.enhancement = None  # type: ignore[assignment]
        # Drukhari Combat Drugs (army rule). Defaults are zero / no-op. The
        # simulator's `_apply_combat_drugs` hook stamps these at battle start
        # on WYCH CULT units only. Cited as `simulator.combat_drugs`.
        self.combat_drug_extra_melee_attacks: int = 0
        self.combat_drug_melee_strength_bonus: int = 0
        self.combat_drug_toughness_bonus: int = 0
        self.combat_drug_move_bonus: float = 0.0
        # Transport bookkeeping. `passengers` is a fresh list on every Unit so
        # mutating it on one transport doesn't leak into another. `embarked_in`
        # is the carrier pointer for a passenger; both default to empty / None.
        self.passengers: list = []
        self.embarked_in = None  # type: ignore[assignment]
        # BS-1: persistent battleshock-until-round marker (see __slots__ for
        # rationale). 0 = never failed; otherwise = the round_num during
        # which the unit is currently battle-shocked.
        self.battleshocked_until_round: int = 0
        # SOROR-DIAG-4: per-round Acts of Faith budget. Reset at the top of
        # every round in Battle._run_round for every Sororitas unit on both
        # armies. While True, no further offensive OR defensive Miracle die
        # substitution may fire on this unit until the next round-reset.
        # See __slots__ for full rationale and citation linkage.
        self.aof_used_this_round: bool = False
        # CSM-EYE-OF-GODS: persistent CHARACTER snowball flag. See __slots__
        # for full rationale; default False on construction. Stamped True by
        # `Battle._try_eye_of_the_gods` after a melee kill by a CSM CHARACTER
        # consumes 1 CP via the Pactbound Zealots stratagem.
        self.eye_of_the_gods_stamped: bool = False

    @property
    def current_health(self) -> float:
        return self._current_health

    @current_health.setter
    def current_health(self, value: float) -> None:
        was_alive = self._current_health > 1e-9
        self._current_health = value
        is_alive_now = value > 1e-9
        if was_alive != is_alive_now:
            army = getattr(self, "army_ref", None)
            if army is not None:
                army._invalidate_alive_cache()

    @property
    def is_alive(self) -> bool:
        return self._current_health > 1e-9

    @property
    def is_embarked(self) -> bool:
        """True iff this unit is currently inside a TRANSPORT (10e core).

        Convenience accessor that mirrors `embarked_in is not None`. Provided
        so call sites can read the embark state without repeating the
        identity check, and so test code can assert on a positive boolean
        rather than the back-pointer's identity. The two are kept
        deliberately in sync: `is_embarked` is True iff `embarked_in` is a
        live Unit, and falsified by `_disembark` setting `embarked_in =
        None`. Cited as `simulator.embark`.
        """
        return self.embarked_in is not None

    def is_currently_battle_shocked(self, round_num: int) -> bool:
        """BS-1: True iff this unit failed its Battle-shock test at the
        start of `round_num`'s Command phase and the status has not yet
        expired. The 10e rule wording is "until the start of your next
        Command phase", so the marker `battleshocked_until_round` is set
        to the failing round in `simulator._run_battleshock_phase` and
        compared exactly here. Downstream consumers that need to fire on
        the persisting state (Synapse Imperative tarpit gating, future
        Chaos Knights Harbingers of Dread mortal-wound aura, future
        Sororitas Repentia explosive death, etc.) should route through
        this method rather than touching the field directly so the
        round-window semantics stay in one place. Cited as
        `simulator.battleshock`.
        """
        return self.battleshocked_until_round == round_num

    def receive_damage(self, amount: float, bonus_fnp: int = 7, psychic: bool = False) -> None:
        """
        Apply damage. If this unit has Feel No Pain X+, each point of damage
        gets a d6 roll; on X+, it's ignored. Mortal wounds applied via this
        method also get FNP'd by default (matches 10e default behaviour).

        `bonus_fnp` lets the caller pass in a transient FNP value from a
        leader aura (lower of profile.fnp and bonus_fnp wins). 7 = no aura.

        `psychic` lets the caller flag the incoming attack as a 10e
        [PSYCHIC] Attack. Magnus the Red's Impossible Form ("Each time an
        attack is allocated to this model, subtract 1 from the Damage
        characteristic of that attack — Psychic Attacks are not affected by
        this ability") excludes Psychic Attacks from the -1 damage
        reduction, so when `psychic=True` the `transient_minus_one_damage_taken`
        clamp is skipped for ALL units carrying the flag. We pass it
        per-call from psychic-source sites: Cabal of Sorcerers Doombolt
        (`_dispatch_ritual`) and the end-of-round psychic-detachment mortal
        wound payload (`_apply_psychic_phase`). Cited as
        `simulator.magnus_unearthly_power_impossible_form` in
        data/rule_citations.d/thousand_sons.json.

        Disgustingly Resilient (Plague Company stratagem): if the target
        has `transient_minus_one_damage_taken` set for the round, subtract
        1 from the per-call damage characteristic (to a minimum of 1). The
        rule fires per-attack in the codex; receive_damage is called per
        per-shot in Unit.attack, so the floor lives here.
        """
        if self.transient_minus_one_damage_taken and amount > 0 and not psychic:
            amount = max(1.0, amount - 1.0)
        # Saim-Hann Spirit Stones (Aeldari stratagem, 1 CP): halve incoming
        # damage (rounded up) for the round. Applied per receive_damage call —
        # mirrors the per-attack codex wording since receive_damage is called
        # per-shot from Unit.attack. Cited as `Stratagem.Spirit Stones`.
        if self.transient_halve_damage and amount > 0:
            amount = math.ceil(amount / 2.0)
        effective_fnp = min(self.profile.fnp, bonus_fnp)
        # Awakened Dynasty Implacable Onslaught (Necron stratagem, 1 CP):
        # transient FNP 5+ for the round. Composes with the unit's existing
        # FNP / leader-aura FNP by taking the lower (better) value, identical
        # to the Death Guard / Drukhari composition pattern below. Cited as
        # `Stratagem.Implacable Onslaught`.
        if self.transient_fnp_5:
            effective_fnp = min(effective_fnp, 5)
        # Death Guard 10e: there is NO army-wide Feel No Pain 5+ rule.
        # Per the May 2026 Death Guard codex on Wahapedia (and confirmed by
        # Goonhammer "Hammer of Math: New Disgustingly Resilient" + the
        # 10e codex review): the army rule is Nurgle's Gift / Contagions
        # of Nurgle (a -1 T / -1 Ld / -1 to hit aura, per round), NOT a
        # codex-level FNP. Disgustingly Resilient in 10e is ONLY the 2 CP
        # Virulent Vectorium stratagem (-1 damage per allocated attack for
        # the phase), wired via `transient_minus_one_damage_taken` above.
        # The previous unconditional `min(effective_fnp, 5)` block was a
        # fabrication that overpriced every DG VEHICLE / Terminator / non-
        # PM datasheet with phantom FNP 5+. Per-datasheet innate FNP (e.g.
        # Plague Marines fnp=5, Deathshroud fnp=4, Mortarion fnp=5) is
        # carried on profile.fnp via overrides.json / parsed.json and is
        # already honoured by the `min(self.profile.fnp, bonus_fnp)` line
        # above. Removed in iter 15.
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/death-guard/
        # Goonhammer: https://www.goonhammer.com/hammer-of-math-new-disgustingly-resilient/
        # Drukhari Power From Pain (10e codex, current Wahapedia text): the
        # army rule does NOT grant a passive FNP from holding a Pain Token.
        # Tokens accrue into a pool and can be SPENT to Empower a unit,
        # whereupon that unit's per-datasheet "Pain ability" takes effect
        # until the end of the phase. Per-datasheet Pain abilities are not
        # catalogued in SwegHammer yet, so no token-driven defensive buff
        # fires here. The previous unconditional `min(effective_fnp, 6)`
        # branch was a fabrication that overbuffed every multi-model
        # Drukhari unit that had lost one model — it gave army-wide free
        # FNP 6+ that has no basis in the current Wahapedia rule. Removed
        # in DRK-PAIN-TOKENS. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/drukhari/
        if effective_fnp < 7 and amount > 0:
            survived = 0
            for _ in range(int(round(amount))):
                if random.randint(1, 6) >= effective_fnp:
                    continue   # ignored
                survived += 1
            amount = survived + (amount - int(round(amount)))   # preserve fractional
        self.current_health = max(0.0, self.current_health - amount)

    def attack(
        self,
        target: "Unit",
        distance: float = 0.0,
        mode: str = "ranged",
        is_charging: bool = False,
        has_los: bool = True,
    ) -> float:
        """
        Full stochastic 10e attack sequence. For each of `attacks` shots:
          1. Roll d6 vs hit_target. Crit = 6.
          2. Sustained Hits N: crit-to-hit generates N extra normal hits.
          3. Lethal Hits: crit-to-hit auto-wounds (only the original crit, not
             its sustained extras).
          4. For each resulting hit, roll d6 vs wound_target. Twin-Linked
             re-rolls a failed wound roll once. Crit-to-wound = 6.
          5. Devastating Wounds: crit-to-wound bypasses saves (mortal wound).
          6. Otherwise roll d6 save vs better of (armour-after-AP) and invuln.

        Army-wide detachment rules and the Heavy keyword feed in as modifiers
        on hit_target, wound_target, n_attacks, save_target and the effective
        invuln before the loop runs.

        is_charging  - the attacker declared a charge this turn (Lance: +1 wound in melee)
        has_los      - the defender is visible from the attacker (Indirect Fire: -1 hit if False)
        """
        p = self.profile

        # SOROR-DIAG-2 (2026-05-23) — Acts of Faith one-per-phase-per-unit gate.
        # Wahapedia (verbatim): "each unit from your army with this ability can
        # perform one Act of Faith per phase" (citation: simulator.acts_of_faith).
        # Prior implementation substituted a Miracle die on EVERY failed hit /
        # wound / save across the unit's entire attack call (potentially dozens
        # of substitutions per phase). The local boolean short-circuits the
        # three substitution branches inside ONE attack() call after the first
        # fire.
        #
        # SOROR-DIAG-4 (2026-05-24) — promote the budget to the Unit. The
        # SOROR-DIAG-2 local-only gate fixed within-one-attack-call double
        # spending but did NOT cap cross-call spending: a Sororitas defender
        # could spend one defensive Miracle die per ATTACKING enemy across an
        # entire phase, because each enemy attacker entered attack() with a
        # fresh local flag. Likewise an attacking Sororitas unit firing
        # multiple weapon profiles routes through attack() once per target,
        # each call fresh. Now we read AND write
        # `self.aof_used_this_round` (offensive side, this unit) and
        # `target.aof_used_this_round` (defensive side, the target unit) at
        # each substitution gate, capping each Sororitas unit at one Act of
        # Faith per round across both directions. Round-level reset happens
        # in `Battle._run_round`. Cited as `simulator.acts_of_faith`.
        attack_aof_substitution_used = False

        # ---- Buff lookups (detachment + in-range leader auras) -------------
        # Attacker side: detachment passives + every in-range friendly leader
        # whose aura covers this unit (re-rolls, +1 to hit/wound).
        # Target side: detachment passives + leader auras covering the target
        # (army-wide invuln, FNP). All composed via leaders.effective_buffs().
        from .leaders import effective_buffs
        att_buffs = effective_buffs(self)
        tgt_buffs = effective_buffs(target)

        # ---- MAP-MULTIFIRE — Build the list of ranged weapon profiles that
        # will fire this activation. 10e core rule: a unit must fire ALL its
        # weapons in its Shooting phase (it may split-fire targets per
        # weapon, but every weapon resolves). Prior to this change the
        # simulator's MAP-1 picker selected the single highest-EV profile
        # per activation — that left ~80% of a Knight Castellan's gun
        # rack idle each turn. This block builds the list of in-range
        # profile-swap dicts; the resolution loop below iterates over the
        # list, applying each swap to the local `p` and accumulating
        # damage. For single-profile units (the vast majority) the list
        # contains a single `None` sentinel and the loop runs exactly
        # once — preserving legacy behaviour. Melee mode always uses the
        # single melee profile (10e has no melee multi-profile chassis in
        # the simulator's catalogue), so the list is forced to `[None]`
        # before the melee branch runs. Cited as
        # `simulator.multi_profile_weapon_selection`.
        #
        # MAP-MULTIFIRE-VALIDATE — gate the fire-all loop on TWO 10e core
        # rules the original MAP-MULTIFIRE picker ignored:
        #   (a) Multi-mode weapons fire ONE mode per Shooting phase (a
        #       Stormsurge's Pulse Blastcannon "focused mode" and
        #       "dispersed mode" are alternatives, not both-at-once;
        #       plasma weapons pick "standard" or "supercharge", not
        #       both; Tau Burst Cannons pick "strike" or "sweep").
        #       Detected by stripping a small set of BSData mode-suffix
        #       patterns (" - focused", " - dispersed", " - standard",
        #       " - supercharge", " strike", " sweep") off each
        #       profile's weapon name and grouping by the stripped root.
        #   (b) Pistol exclusivity (Wahapedia core rules, Pistols
        #       section, verbatim): "A model armed with one or more
        #       Pistols cannot shoot any non-Pistol weapons in the same
        #       turn (and vice versa)." We partition the per-group
        #       picks into pistol and non-pistol sets and fire the
        #       side whose summed expected damage is higher.
        # Cited as `simulator.pistol_exclusivity` (citation entry holds
        # the Wahapedia rule text) plus the existing
        # `simulator.multi_profile_weapon_selection`.
        _profiles_to_fire: list = [None]
        # KNIGHTS-MULTIPROFILE-2 — ADDITIVE melee multi-weapon resolution.
        # Datasheets like Knight Abominant (Electroscourge + Balemace) or
        # Knight Rampager (Reaper chainsword + Warpstrike claw) carry MORE
        # THAN ONE melee weapon profile. The primary p.melee_* block carries
        # whichever weapon BSData picked first; any others live on
        # p.extra_melee_profiles. Each extra profile fires AS AN ADDITIONAL
        # attack-resolution pass alongside the primary in the same Fight
        # phase. This is the OPPOSITE convention from extra_ranged_profiles,
        # which is a MUTEX picker (alt-modes of one weapon). The melee case
        # is additive because (a) 10e Extra Attacks core rule says weapons
        # with [EXTRA ATTACKS] resolve in addition to the model's other
        # melee attacks, and (b) a model carrying two distinct datasheet
        # melee weapons (Rampager) fights with both, not one. Cited as
        # `simulator.extra_melee_profiles`.
        if mode == "melee" and p.extra_melee_profiles:
            # The dataclasses.replace hot-swap fires inside the existing
            # `for _swap_profile in _profiles_to_fire` loop below — we just
            # populate the list with the swap dicts here.
            _melee_extras: list = []
            for _extra in p.extra_melee_profiles:
                _ed = dict(_extra)
                # Translate the extra-melee dict into the dataclass field
                # names so a single replace(_p_base, **swap) hot-swaps every
                # melee_* attribute that the melee resolution branch reads.
                _melee_extras.append({
                    "melee_attacks": max(1, int(_ed.get("attacks", 1) or 1)),
                    "melee_damage_per_shot": float(
                        _ed.get("weapon_damage_per_shot", 1.0) or 1.0
                    ),
                    "melee_hit_probability": float(
                        _ed.get("hit_probability", 0.0) or 0.0
                    ),
                    "melee_ap": int(_ed.get("ap", 0) or 0),
                    "melee_strength": int(_ed.get("strength", 4) or 4),
                    "melee_weapon": str(_ed.get("weapon", "") or ""),
                    "melee_sustained_hits": int(
                        _ed.get("sustained_hits", 0) or 0
                    ),
                    # Weapon-level keyword flags reuse the same UnitProfile
                    # field names that Unit.attack reads in the melee branch.
                    "lethal_hits": bool(_ed.get("lethal_hits", False)),
                    "devastating_wounds": bool(
                        _ed.get("devastating_wounds", False)
                    ),
                    "twin_linked": bool(_ed.get("twin_linked", False)),
                    "lance": bool(_ed.get("lance", False)),
                    "precision": bool(_ed.get("precision", False)),
                    # anti_keywords merges into the existing primary
                    # anti_keywords dict; the swap replaces it for the
                    # extra's resolution pass.
                    "anti_keywords": dict(_ed.get("anti_keywords") or {}),
                })
            # Primary fires first (None) then each extra fires once.
            _profiles_to_fire = [None] + _melee_extras
        elif mode != "melee" and (
            p.secondary_attacks > 0 or p.extra_ranged_profiles
        ):
            # Mode-suffix patterns the BSData mapper emits for
            # alternative-mode weapon profiles. Stripped case-insensitively
            # off the trailing edge of the weapon name; whatever remains
            # is the "root" that groups siblings together.
            #
            # MODE-SUFFIX-SWEEP: SOROR-DIAG-5 (commit 90bb1a3) traced
            # Morvenn Vahl firing both prioris- and sanctorum-mode shots
            # of her Paragon missile launcher to this list being a tiny
            # allowlist that only knew the plasma/Stormsurge/Burst-cannon
            # mode tokens. A parsed.json survey of every weapon name with
            # a " - " separator (BSData's canonical alt-mode delimiter)
            # found 317 such names across 70+ distinct mode tokens —
            # krak/frag/starshot/witchfire/contained/overcharge/neurolance
            # /foehammer/rift/prioris/sanctorum and many more. Every one
            # of those names is a mutex alt-mode of the same underlying
            # weapon (10e core: multi-profile weapons pick ONE mode per
            # Shooting phase), so the safe structural rule is to strip
            # everything after the last " - " when forming the group
            # root. The allowlist below is kept for the legacy non-dash
            # cases (BSData has occasionally emitted ", standard" or a
            # bare " strike" suffix without the em-dash), then the
            # em-dash fallback below catches the long tail. Verified on
            # the live catalogue: collapses 114 units' profile lists, no
            # regressions where a unit's root count INCREASES.
            _MODE_SUFFIXES = (
                " - focused mode", " - dispersed mode",
                " - focused", " - dispersed",
                " - standard", " - supercharge", " - supercharged",
                ", focused mode", ", dispersed mode",
                ", standard", ", supercharge",
                " strike", " sweep",
                " - strike", " - sweep",
            )

            def _strip_mode_suffix(name: str) -> str:
                if not name:
                    return ""
                low = name.lower().strip()
                # Drop the BSData "➤ " bullet that prefixes
                # alternative-mode entries in the cache.
                if low.startswith("➤ "):
                    low = low[2:]
                if low.startswith("> "):
                    low = low[2:]
                for suf in _MODE_SUFFIXES:
                    if low.endswith(suf):
                        return low[: -len(suf)].rstrip(" -,")
                # Generalised fallback: every alt-mode profile BSData
                # emits today uses the " - <mode>" separator (e.g.
                # "Ballistus Missile Launcher - Krak",
                # "Phantasmagoria - witchfire",
                # "Paragon missile launcher - prioris"). Treating the
                # text before the LAST " - " as the root collapses all
                # alt-mode siblings of the same weapon into one mutex
                # group without enumerating every individual mode token.
                if " - " in low:
                    low = low.rsplit(" - ", 1)[0].rstrip(" -,")
                return low

            # Each candidate carries:
            #   (group_key, pistol_flag, ev, swap_or_none)
            # where swap_or_none is None for the primary or a dict for
            # secondary/extra. EV is a lightweight expected-damage proxy
            # used only for tie-breaking within a group; the actual
            # damage roll happens in the resolution loop below.
            _candidates: list = []

            def _ev_proxy(
                attacks: float,
                dmg_per_shot: float,
                hit_prob: float,
                twin_linked: bool,
            ) -> float:
                base = max(0.0, float(attacks)) * max(0.0, float(dmg_per_shot)) \
                    * max(0.0, float(hit_prob))
                # twin_linked re-rolls failed wounds ≈ 1.33x effective
                # wound probability; tiny bump to the EV proxy.
                return base * (1.33 if twin_linked else 1.0)

            # Primary profile
            primary_in_range = (
                distance <= 0 or distance <= float(p.range_inches or 24)
            )
            if primary_in_range:
                _candidates.append((
                    _strip_mode_suffix(p.weapon or ""),
                    bool(p.pistol),
                    _ev_proxy(
                        p.attacks, p.weapon_damage_per_shot,
                        p.hit_probability, p.twin_linked,
                    ),
                    None,
                ))

            # Secondary profile
            if p.secondary_attacks > 0:
                sec_in_range = (
                    distance <= 0
                    or distance <= float(p.secondary_range_inches or 0)
                )
                if sec_in_range:
                    sec_swap = {
                        "attacks": max(1, int(p.secondary_attacks)),
                        "weapon_damage_per_shot": p.secondary_weapon_damage_per_shot,
                        "hit_probability": p.secondary_hit_probability,
                        "ap": p.secondary_ap,
                        "strength": p.secondary_strength,
                        "range_inches": p.secondary_range_inches or p.range_inches,
                        "lethal_hits": p.secondary_lethal_hits,
                        "sustained_hits": p.secondary_sustained_hits,
                        "twin_linked": p.secondary_twin_linked,
                        "devastating_wounds": p.secondary_devastating_wounds,
                        "rapid_fire": p.secondary_rapid_fire,
                        "melta": p.secondary_melta,
                        "ignores_cover": p.secondary_ignores_cover,
                        "heavy": p.secondary_heavy,
                        "assault": p.secondary_assault,
                        "torrent": p.secondary_torrent,
                        "blast": p.secondary_blast,
                        "anti_keywords": tuple(p.secondary_anti_keywords or ()),
                    }
                    _candidates.append((
                        _strip_mode_suffix(p.secondary_weapon or ""),
                        bool(p.secondary_pistol),
                        _ev_proxy(
                            sec_swap["attacks"],
                            sec_swap["weapon_damage_per_shot"],
                            sec_swap["hit_probability"],
                            sec_swap["twin_linked"],
                        ),
                        sec_swap,
                    ))

            # MAP-1: extra ranged profiles (3rd, 4th, 5th, ...).
            for extra in (p.extra_ranged_profiles or ()):
                ed_fields = dict(extra)
                ex_range = float(ed_fields.get("range_inches", 0) or 0)
                if not (distance <= 0 or distance <= ex_range):
                    continue
                ex_attacks = max(1, int(ed_fields.get("attacks", 1) or 1))
                ex_swap = {
                    "attacks": ex_attacks,
                    "weapon_damage_per_shot": float(
                        ed_fields.get("weapon_damage_per_shot", 1.0) or 1.0
                    ),
                    "hit_probability": float(
                        ed_fields.get("hit_probability", 0.0) or 0.0
                    ),
                    "ap": int(ed_fields.get("ap", 0) or 0),
                    "strength": int(ed_fields.get("strength", 4) or 4),
                    "range_inches": int(
                        ed_fields.get("range_inches", p.range_inches)
                        or p.range_inches
                    ),
                    "lethal_hits": bool(ed_fields.get("lethal_hits", False)),
                    "sustained_hits": int(ed_fields.get("sustained_hits", 0) or 0),
                    "twin_linked": bool(ed_fields.get("twin_linked", False)),
                    "devastating_wounds": bool(
                        ed_fields.get("devastating_wounds", False)
                    ),
                    "rapid_fire": int(ed_fields.get("rapid_fire", 0) or 0),
                    "melta": int(ed_fields.get("melta", 0) or 0),
                    "ignores_cover": bool(ed_fields.get("ignores_cover", False)),
                    "heavy": bool(ed_fields.get("heavy", False)),
                    "assault": bool(ed_fields.get("assault", False)),
                    "torrent": bool(ed_fields.get("torrent", False)),
                    "blast": bool(ed_fields.get("blast", False)),
                    "anti_keywords": tuple(
                        (ed_fields.get("anti_keywords") or {}).items()
                        if isinstance(ed_fields.get("anti_keywords"), dict)
                        else (ed_fields.get("anti_keywords") or ())
                    ),
                }
                _candidates.append((
                    _strip_mode_suffix(str(ed_fields.get("weapon", "")) or ""),
                    bool(ed_fields.get("pistol", False)),
                    _ev_proxy(
                        ex_swap["attacks"],
                        ex_swap["weapon_damage_per_shot"],
                        ex_swap["hit_probability"],
                        ex_swap["twin_linked"],
                    ),
                    ex_swap,
                ))

            # Group by (root_name, pistol_flag). Profiles with EMPTY root
            # name (no weapon-name metadata, e.g. units predating the
            # field) get a unique placeholder per index so they NEVER
            # collapse into another profile. Each non-empty group picks
            # its single best-EV member.
            groups: dict = {}
            for idx, (root, pistol_flag, ev, swap) in enumerate(_candidates):
                if not root:
                    key = ("__no_name__", idx, pistol_flag)
                else:
                    key = (root, pistol_flag)
                cur = groups.get(key)
                if cur is None or ev > cur[0]:
                    groups[key] = (ev, swap)

            # Pistol exclusivity (10e core): partition into pistol /
            # non-pistol sets, fire whichever side has higher total EV.
            pistol_picks = []
            nonpistol_picks = []
            for key, (ev, swap) in groups.items():
                # key is (root, pistol_flag) OR ("__no_name__", idx,
                # pistol_flag). Pistol flag is always the LAST element.
                pistol_flag = key[-1]
                if pistol_flag:
                    pistol_picks.append((ev, swap))
                else:
                    nonpistol_picks.append((ev, swap))
            pistol_total = sum(e for e, _ in pistol_picks)
            nonpistol_total = sum(e for e, _ in nonpistol_picks)
            if pistol_picks and nonpistol_picks:
                # Choose the side with higher summed EV; drop the other.
                chosen = pistol_picks if pistol_total >= nonpistol_total \
                    else nonpistol_picks
            else:
                chosen = pistol_picks or nonpistol_picks

            _profiles_to_fire = [swap for _ev, swap in chosen]

            # Defensive fallback: if NOTHING is in range (caller passed a
            # huge distance), still iterate once with the primary so the
            # activation does not silently no-op. The primary's in-range
            # check inside the body will then end up firing 0 damage
            # because all the ranged gates fail — same outcome as the
            # legacy picker which returned 0 expected damage for every
            # candidate.
            if not _profiles_to_fire:
                _profiles_to_fire = [None]

        # Save the primary profile so we can reset before each iteration of
        # the multi-profile loop applies a fresh swap. `p_base` stays the
        # immutable primary; the local `p` is rebuilt per profile.
        _p_base = p
        total_damage = 0.0
        for _swap_profile in _profiles_to_fire:
            # Reset to the primary profile, then apply this iteration's
            # swap (None means "fire the primary as-is").
            p = _p_base
            if _swap_profile is not None:
                from dataclasses import replace
                p = replace(_p_base, **_swap_profile)

            if mode == "melee" and p.melee_attacks > 0:
                # Substitute the melee stat block for this resolution
                per_shot_dmg = p.melee_damage_per_shot or 1.0
                n_attacks = max(1, int(p.melee_attacks))
                hit_target = _prob_to_target(p.melee_hit_probability)
                strength = p.melee_strength
                ap = p.melee_ap
                ignore_cover = True   # melee always ignores cover
                # LEADERABILITY-SCHEMA: Keeper of Secrets "Daemon Lord of
                # Slaanesh" aura — improve the Armour Penetration of melee
                # weapons in friendly Slaanesh Legiones Daemonica units within
                # 6" of the KoS by 1. Wahapedia / BSData verbatim:
                # "While a friendly Slaanesh Legiones Daemonica unit is within
                # 6" of this model, improve the Armour Penetration of melee
                # weapons in that unit by 1."
                # Cited as `LeaderAbility.Daemon Lord of Slaanesh`. AP is
                # encoded as 0/-1/-2/-3 — "improve by 1" makes the value MORE
                # negative, so we subtract 1. Same convention as SHIELD_HOST
                # `melee_ap_plus_one` and Necrons Hungry Void. Boolean read
                # from att_buffs which has already host-gated the merge to
                # Slaanesh-keyed attackers.
                if att_buffs["plus_one_ap_melee"]:
                    ap = ap - 1
                # Drukhari Combat Drugs (army rule): Adrenalight grants +1 Attack
                # and Grave Lotus grants +1 Strength on WYCH CULT melee weapons.
                # The simulator's `_apply_combat_drugs` hook stamps these per-unit
                # at battle start; defaults to 0 on every non-Drukhari unit so the
                # add is safe. Cited as `simulator.combat_drugs`.
                n_attacks += int(getattr(self, "combat_drug_extra_melee_attacks", 0))
                strength += int(getattr(self, "combat_drug_melee_strength_bonus", 0))
                # ---- World Eaters Exalted Eightbound — Rend and Tear (datasheet
                # ability, BSData v10.6.0 verbatim): "Each time a model in this
                # unit makes a melee attack that targets a Monster or Vehicle
                # unit, until the end of the phase, improve the Damage
                # characteristic of that attack by 1." Faction-gated to World
                # Eaters AND unit name == "Exalted Eightbound"; target must have
                # MONSTER or VEHICLE keyword. Cited as `simulator.rend_and_tear`.
                if (
                    p.faction == "World Eaters"
                    and p.name == "Exalted Eightbound"
                ):
                    _tgt_kws_rt = set(target.profile.unit_keywords or ())
                    if "MONSTER" in _tgt_kws_rt or "VEHICLE" in _tgt_kws_rt:
                        per_shot_dmg += 1.0
            else:
                per_shot_dmg = p.per_shot_damage
                n_attacks = max(1, int(p.attacks))
                hit_target = None     # set below
                strength = p.strength
                ap = p.ap
                # DRK-SKYSPLINTER-DISEMBARK: Rain of Cruelty grants transient
                # IGNORES COVER on a DRUKHARI unit's ranged weapons "until
                # the end of the turn" after it disembarks from a TRANSPORT
                # (set by `simulator._disembark` and cleared by the standard
                # transient-flag reset). Composed via OR with the per-weapon
                # `profile.ignores_cover` keyword. Cited as
                # `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark`.
                ignore_cover = bool(
                    p.ignores_cover
                    or getattr(self, "transient_ignores_cover_this_turn", False)
                )
                # LEADERABILITY-SCHEMA: Lord of Change "Daemon Lord of
                # Tzeentch" aura — +1 to the Strength characteristic of
                # ranged attacks from any TZEENTCH Legiones Daemonica unit
                # within 6". Wahapedia / BSData verbatim:
                # "While a friendly TZEENTCH LEGIONES DAEMONICA unit is
                # within 6" of this model, each time a model in that unit
                # makes a ranged attack, add 1 to the Strength characteristic
                # of that attack."
                # Cited as `LeaderAbility.Daemon Lord of Tzeentch`. Boolean
                # OR-merged in effective_buffs from any in-range Lord of
                # Change with host_keys gated to Tzeentch Daemonica units.
                # The merge already filters to the right host; this gate
                # just reads the merged buff and applies the +1.
                if att_buffs["plus_one_strength_ranged"]:
                    strength += 1

            # ---- Adeptus Custodes Shield Host — Martial Ka'tah / Martial Mastery:
            # melee AP+1 portion. Wahapedia verbatim: "Improve the Armour
            # Penetration characteristic of melee weapons equipped by ADEPTUS
            # CUSTODES models from your army with the Martial Ka'tah ability
            # by 1." Gate: mode == "melee" AND attacker faction ==
            # "Adeptus Custodes" AND detachment carries `melee_ap_plus_one`
            # (set by SHIELD_HOST) AND the current battle round is ODD.
            # AP is encoded as 0/-1/-2/-3 — improving AP by 1 makes the value
            # MORE negative (AP-1 becomes AP-2 etc).
            # C1 (claude/sim-calibration-4): codex picks ONE bullet per battle
            # round. To match real codex pacing, the two bullets alternate by
            # round parity — AP+1 fires on ODD rounds (1, 3, 5), Crit-on-5+
            # fires on EVEN rounds (2, 4). This averages to one bullet per
            # round (matching codex) rather than the prior always-on dual
            # uplift (strictly stronger than codex). Cited as
            # `SHIELD_HOST.melee_ap_plus_one`.
            if mode == "melee" and p.faction == "Adeptus Custodes":
                _own_army_mk = getattr(self, "army_ref", None)
                if _own_army_mk is not None:
                    try:
                        _det_mk = _own_army_mk.resolve_detachment()
                    except Exception:
                        _det_mk = None
                    if _det_mk is not None and getattr(
                        _det_mk, "melee_ap_plus_one", False,
                    ):
                        _battle_mk = getattr(_own_army_mk, "_battle_ref", None)
                        _round_mk = (
                            getattr(_battle_mk, "_current_round", 0)
                            if _battle_mk is not None else 0
                        )
                        # Odd round (1, 3, 5) -> AP+1 bullet active. Round 0
                        # (pre-battle / no battle ref) treated as inactive so
                        # standalone tests without a battle round set see no
                        # buff unless they configure the round explicitly.
                        if _round_mk % 2 == 1:
                            ap = ap - 1

            # ---- Necrons Awakened Dynasty — Protocol of the Hungry Void
            # (army-wide melee AP+1). AD-PR (claude/sim-calibration-4): the
            # detachment-rule rotation of Command Protocols is approximated
            # by alternating Hungry Void (this flag) and Vengeful Stars by
            # battle-round parity. Hungry Void fires on EVEN rounds (2, 4)
            # so the parity matches the SHIELD_HOST AP+1 convention but
            # inverted (Custodes AP+1 = ODD, Necrons AP+1 = EVEN; they don't
            # collide because the faction gate keeps the two detachments
            # apart). Gate: mode == "melee" AND attacker faction == "Necrons"
            # AND detachment carries `necrons_melee_ap_plus_one_army_wide`
            # (set by AWAKENED_DYNASTY) AND current battle round is even.
            # Cited as `AWAKENED_DYNASTY.necrons_melee_ap_plus_one_army_wide`.
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/
            # #Command-Protocols.
            if mode == "melee" and p.faction == "Necrons":
                _own_army_hv = getattr(self, "army_ref", None)
                if _own_army_hv is not None:
                    try:
                        _det_hv = _own_army_hv.resolve_detachment()
                    except Exception:
                        _det_hv = None
                    if _det_hv is not None and getattr(
                        _det_hv, "necrons_melee_ap_plus_one_army_wide", False,
                    ):
                        _battle_hv = getattr(_own_army_hv, "_battle_ref", None)
                        _round_hv = (
                            getattr(_battle_hv, "_current_round", 0)
                            if _battle_hv is not None else 0
                        )
                        # Even round (2, 4) -> Hungry Void active. Round 0
                        # (pre-battle / no battle ref) treated as inactive
                        # so standalone tests without a battle round set
                        # see no buff unless they configure the round.
                        if _round_hv > 0 and _round_hv % 2 == 0:
                            ap = ap - 1

            # ---- World Eaters Blessings of Khorne (10e army rule) —
            # Cleaving Blows grants army-wide melee AP+1 (more negative AP)
            # for the battle round. Gate: mode == "melee" AND attacker
            # faction == "World Eaters" AND the army's
            # `blessings_cleaving_blows_round` stamp matches the live battle
            # round. AP+1 maps to subtracting 1 from `ap` (AP-1 -> AP-2
            # etc.) — same convention as SHIELD_HOST.melee_ap_plus_one.
            # Cited as `simulator.blessings_of_khorne`.
            if mode == "melee" and p.faction == "World Eaters":
                _own_army_cb = getattr(self, "army_ref", None)
                if _own_army_cb is not None:
                    _cb_round = getattr(
                        _own_army_cb, "blessings_cleaving_blows_round", None,
                    )
                    _battle_cb = getattr(_own_army_cb, "_battle_ref", None)
                    _cur_round_cb = (
                        getattr(_battle_cb, "_current_round", 0)
                        if _battle_cb is not None else 0
                    )
                    if _cb_round is not None and _cb_round == _cur_round_cb:
                        ap = ap - 1

            # ---- Adeptus Mechanicus Doctrina Imperatives — Conqueror AP+1.
            # Wahapedia verbatim: "Each time a model in this unit makes an
            # attack, if this unit has the BATTLELINE keyword and/or it is
            # within 6\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE
            # units, improve the Armour Penetration characteristic of that
            # attack by 1." ADMECH-DIAG-2 (2026-05-24) replaced the prior
            # army-wide approximation with the real BATTLELINE-or-within-6"
            # proximity gate (see `_doctrina_battleline_proximity_met`).
            # Only 2 of 42 AdMech datasheets carry BATTLELINE (Skitarii
            # Vanguard / Rangers), so the army-wide approximation was
            # over-applying the AP buff to ~95% of AdMech units that the
            # codex does not actually grant it to. Gate: attacker faction
            # == "Adeptus Mechanicus" AND active imperative is Conqueror
            # AND the attacker passes the BATTLELINE proximity check.
            # AP is encoded 0/-1/-2/-3 so "improve by 1" subtracts 1.
            # Cited as `simulator.doctrina_imperatives`.
            if p.faction == "Adeptus Mechanicus":
                _own_army_di_ap = getattr(self, "army_ref", None)
                _imp_di_ap = (
                    getattr(_own_army_di_ap, "doctrina_imperative", None)
                    if _own_army_di_ap is not None else None
                )
                if (
                    _imp_di_ap == "conqueror"
                    and _doctrina_battleline_proximity_met(self)
                ):
                    ap = ap - 1

            # ---- Range-dependent weapon keywords (Phase A2, ranged mode only) ----
            if mode != "melee":
                half_range = (p.range_inches or 24) / 2.0
                at_half_range = distance > 0 and distance <= half_range
                if at_half_range:
                    n_attacks += int(p.rapid_fire)           # Rapid Fire X
                    per_shot_dmg += float(p.melta)           # Melta X

            # ---- Blast: +1 attack per 5 enemy models in the target unit ----
            if p.blast and target.profile.blast is not None:  # always true; null-guard
                try:
                    same_squad = sum(
                        1 for u in target.army_ref.alive_units
                        if u.profile.name == target.profile.name
                    ) if target.army_ref is not None else 1
                except Exception:
                    same_squad = 1
                n_attacks += same_squad // 5

            # ---- Buffs: +N extra attacks per weapon (detachment-only field) ----
            if att_buffs["plus_one_attack"]:
                n_attacks += int(att_buffs["plus_one_attack"])

            if hit_target is None:
                hit_target = _prob_to_target(p.hit_probability)
            # Drukhari Combat Drugs (army rule): Painbringer grants +1 Toughness
            # on WYCH CULT models defensively. The simulator's `_apply_combat_drugs`
            # hook stamps a per-unit bonus on the target's Unit instance; defaults
            # to 0 on every non-Drukhari unit. Cited as `simulator.combat_drugs`.
            _drug_toughness = int(getattr(target, "combat_drug_toughness_bonus", 0))
            _effective_toughness = target.profile.toughness + _drug_toughness
            # LEADERABILITY-SCHEMA: Great Unclean One "Daemon Lord of Nurgle"
            # aura — +1 to the Toughness characteristic of models in any
            # friendly NURGLE Legiones Daemonica unit within 6" of the GUO.
            # Wahapedia / BSData verbatim:
            # "While a friendly Nurgle Legiones Daemonica unit is within 6"
            # of this model, add 1 to the Toughness characteristic of models
            # in that unit."
            # Cited as `LeaderAbility.Daemon Lord of Nurgle`. Buff is DEFENDER-
            # side: reads tgt_buffs (computed from the target's own army's
            # in-range Great Unclean One with host_keys covering the target).
            # The codex grants this army-wide-within-6", not a led-unit
            # restriction, so the +1 T applies to whichever Nurgle unit is
            # closest to the GUO. host_keys narrows the eligible defenders.
            if tgt_buffs["plus_one_toughness"]:
                _effective_toughness += 1
            wound_p = wound_probability(strength, _effective_toughness)
            wound_target = _prob_to_target(wound_p)

            # ---- 10e core-rules modifier cap (Wahapedia core rules / Hit Roll &
            # Wound Roll): "Hit roll modifiers are cumulative, but the Hit roll
            # for an attack can never be modified by more than -1 or +1." Same
            # wording for the Wound roll. Cited as
            # `simulator.modifier_cap_plus_minus_one`.
            #
            # Each per-source +1 / -1 modifier is added to `hit_mod_delta` /
            # `wound_mod_delta` instead of being applied directly to
            # hit_target / wound_target. After all sources have contributed,
            # we clamp the delta to [-1, +1] (see `_apply_modifier_cap` block
            # at the end of this section) and apply the clamped delta to the
            # base targets. This keeps multiple +1-to-hit sources (Oath of
            # Moment is a re-roll, but e.g. detachment-aura +1 to hit +
            # stratagem +1 to hit) from netting to +2.
            hit_mod_delta: int = 0
            wound_mod_delta: int = 0

            # ---- Buffs: +1 to hit / +1 to wound (any of leader aura, detachment,
            # enhancement — all merged to a single bool by leaders.effective_buffs).
            if att_buffs["plus_one_to_hit"]:
                hit_mod_delta += 1
            # `plus_one_to_hit_melee_only` fires only in the Fight phase (melee).
            # Used for leader auras whose codex text reads "each time a model in
            # that unit makes a melee attack" — e.g. Warboss "Might is Right".
            # Cited as `WARBOSS.plus_one_to_hit_melee_only`.
            if att_buffs.get("plus_one_to_hit_melee_only") and mode == "melee":
                hit_mod_delta += 1
            if att_buffs["plus_one_to_wound"]:
                wound_mod_delta += 1

            # ---- Chaos Knights — Harbingers of Dread (army rule, 10e). Verbatim
            # Wahapedia (https://wahapedia.ru/wh40k10ed/factions/chaos-knights/):
            # "The Deathly Terror ability is active for your army from the start
            # of the battle." Plus one additional Dread ability is selected at
            # battle start; SwegHammer always picks Doom — the offensive Dread
            # ("Each time this model makes an attack, if the target of that attack
            # is Battle-shocked, add 1 to the Wound roll.") because Doom is the
            # only Dread the attack pipeline can directly express; the auras
            # (Despair / Deathly Terror, Ld debuffs within 9") are wired into the
            # Battle-shock phase in code/simulator.py. The R1/R3/R5 bonus
            # additional-Dread pick is NOT modelled here (the wound bonus already
            # represents the "selected additional ability" slot, and the two
            # always-on Ld auras saturate the battleshock side). Faction-gated to
            # Chaos Knights so Imperial Knights' Code Chivalric handling is
            # untouched. Cited as `simulator.harbingers_of_dread`.
            if (
                mode in ("melee", "ranged")
                and (p.faction or "") == "Chaos Knights"
                and target.is_currently_battle_shocked(
                    getattr(
                        getattr(getattr(self, "army_ref", None), "_battle_ref", None),
                        "_current_round",
                        0,
                    )
                )
            ):
                wound_mod_delta += 1

            # ---- World Eaters Eightbound — Beacons of Rage (datasheet aura,
            # BSData v10.6.0 verbatim): "While a friendly World Eaters unit is
            # within 6\" of this unit, each time a model in that unit makes a
            # melee attack that targets a unit (excluding Monsters and
            # Vehicles), add 1 to the Hit roll. If that attack targets a unit
            # that is Below Half-strength, add 1 to the Wound roll as well."
            # Faction-gated to World Eaters attacker. Aura check: any friendly
            # Eightbound (or Exalted Eightbound) unit alive in the same army
            # (the simulator does not model precise 6" positions for auras,
            # see leaders.effective_buffs for the same approximation). Melee
            # only; target must NOT be MONSTER/VEHICLE. Below Half-strength
            # gates the wound bonus: target.current_health < target.profile
            # .health / 2. Cited as `simulator.beacons_of_rage`.
            if mode == "melee" and p.faction == "World Eaters":
                _own_army_bor = getattr(self, "army_ref", None)
                if _own_army_bor is not None:
                    _tgt_kws_bor = set(target.profile.unit_keywords or ())
                    _tgt_is_vm_bor = (
                        "MONSTER" in _tgt_kws_bor or "VEHICLE" in _tgt_kws_bor
                    )
                    if not _tgt_is_vm_bor:
                        _eb_present = any(
                            u.profile.name in ("Eightbound", "Exalted Eightbound")
                            for u in _own_army_bor.alive_units
                        )
                        if _eb_present:
                            hit_mod_delta += 1
                            _tgt_hp_bor = float(target.profile.health) or 1.0
                            if target.current_health < _tgt_hp_bor / 2.0:
                                wound_mod_delta += 1

            # NOTE: Adeptus Astartes Combat Doctrines (Gladius Task Force,
            # 10e) live in the SIMULATOR'S movement gates, not here. Iter-9
            # audit (May 2026) found that the previous +1-to-wound-per-round
            # implementation was fabricated — the real Doctrines (Wahapedia
            # https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force,
            # cross-confirmed via newrecruit.eu Gladius entry) grant only
            # movement utility:
            #   Devastator (R1): "This unit is eligible to shoot in a turn
            #     in which it Advanced." — bypasses the Advance shoot-lockout.
            #   Tactical (R2):   "This unit is eligible to shoot and declare
            #     a charge in a turn in which it Fell Back." — bypasses both
            #     the Fall Back shoot-lockout AND the Fall Back charge-lockout.
            #   Assault (R3+):   "This unit is eligible to declare a charge
            #     in a turn in which it Advanced." — bypasses the Advance
            #     charge-lockout.
            # No wound buff. The gates are implemented in simulator._do_shoot
            # and simulator._do_charge as Advance/Fall-Back lockout exemptions.
            # Cited as `simulator.combat_doctrines`.

            # ---- Transient stratagem buffs (attacker side) ------------------
            # Plague Weapons (Plague Company): +1 to wound on ranged attacks.
            # Twist of Fate (Cult of Magic): +1 to wound on attacks for the
            # round; we route both through the same shooting flag because the
            # simulator's Twist of Fate trigger fires on a TSons unit about to
            # shoot. Outbreak of Pestilence (Plague Company): +1 to wound on
            # melee attacks for the round.
            if (
                mode != "melee"
                and self.transient_plus_one_to_wound_shooting
            ):
                wound_mod_delta += 1
            if (
                mode == "melee"
                and self.transient_plus_one_to_wound_melee
            ):
                wound_mod_delta += 1
            # CSM-EYE-OF-GODS: Eye of the Gods (Pactbound Zealots, 1 CP).
            # Persistent +1 to wound on melee attacks once this CHARACTER
            # has stamped the buff via a prior melee kill. APPROXIMATION:
            # real Eye of the Gods rolls D6+Wounds on a table for +M / +T /
            # +A/+S / +D melee — we collapse to a single +1-to-wound-melee
            # snowball. Stacks at the delta level with transient_plus_one_to_
            # wound_melee (Profane Zeal) before the 10e ±1 modifier cap. The
            # stamp persists across rounds (not cleared with round-start
            # transient_* flags). Cited as `Stratagem.Eye of the Gods`.
            if mode == "melee" and self.eye_of_the_gods_stamped:
                wound_mod_delta += 1
            # Methodical Destruction (Awakened Dynasty, 1 CP): +1 to hit on the
            # selected NECRON unit's ranged attacks for the round. Stacks at the
            # delta level so the post-clamp behaviour matches 10e (e.g. layered
            # with Awakened Dynasty's bonus_to_hit_when_led both wanting +1 to
            # hit, the clamp keeps the net at +1). Cited as
            # `Stratagem.Methodical Destruction`.
            if (
                mode != "melee"
                and self.transient_plus_one_to_hit_shooting
            ):
                hit_mod_delta += 1

            # ---- Death Guard Contagions of Nurgle (army rule, 10e) — Round 1
            # DROPPED (iter-4): the Round-1 Virulent Rot (-1 T) branch was the
            # launch-index wording. The current 10e codex replaces it with
            # randomly-assigned Afflictions (Skullsquirm Blight / Rattlejoint
            # Ague / Scabrous Soulrot). The strongest of those — Scabrous
            # Soulrot's -1 to hit — is already modelled by the R3+ branch
            # below, and Rattlejoint Ague's direction (debuff to enemy unit's
            # action economy) maps onto the R2 -1 Ld battleshock penalty in
            # Battle._run_round. So the R1 -1 T effect has no modern-rule
            # anchor and is removed entirely. R2 -1 Ld and R3+ -1 to hit are
            # preserved (see comment further down in this function for R3+,
            # and code/simulator.py:_run_round for R2 battleshock).
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/death-guard/
            # Cited as `simulator.contagions_of_nurgle` (approximation flag
            # remains true; effect text in the citation reflects the 2-round
            # shape post-removal).

            # ---- Orks WAAAGH! once-per-battle window: +1 to wound in melee for
            # Ork attackers on the turn WAAAGH! was declared. Cited as
            # `simulator.waaagh`. The army-level field `waaagh_round_unlocked`
            # stores the round in which the AI declared; we compare against the
            # live battle round via the army's _battle_ref so the buff applies
            # ONLY on that turn (not the rest of the battle).
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#WAAAGH
            # Real rule: +1 to wound (melee) AND +1 to Charge rolls AND
            # army-wide 5+ invuln vs melee AND Advance-counts-as-Charge.
            # Modelled: +1-to-wound-melee (here) and +1-to-charge-roll
            # (simulator._do_charge).
            # APPROXIMATION: army-wide 5++ vs melee + Advance-counts-as-Charge
            # legs are NOT yet modelled — deferred to future iterations.
            if mode == "melee" and p.faction == "Orks":
                own_army = getattr(self, "army_ref", None)
                if own_army is not None:
                    waaagh_round = getattr(own_army, "waaagh_round_unlocked", None)
                    battle = getattr(own_army, "_battle_ref", None)
                    cur_round = getattr(battle, "_current_round", 0) if battle else 0
                    if waaagh_round is not None and waaagh_round == cur_round:
                        wound_mod_delta += 1

            # ---- Thousand Sons "All Is Dust" (Rubricae Phalanx detachment rule,
            # 10e current codex). Wahapedia verbatim: "Each time an attack with
            # an unmodified Damage characteristic of 1 is allocated to a RUBRICAE
            # model from your army, add 1 to any armour saving throw made against
            # that attack." Applied as a +1 to the target's armour save when the
            # incoming attack has weapon_damage_per_shot == 1 AND the defender
            # carries the RUBRICAE unit-keyword (Rubric Marines, Scarab Occult
            # Terminators — both have RUBRICAE set via data/overrides.json since
            # BSData's mapper does not extract sub-faction keywords).
            #
            # iter15: the buff is now gated on the defender's army carrying the
            # Rubricae Phalanx detachment (Detachment.all_is_dust). Real-meta
            # TSON tournament lists in May 2026 are Rubricae Phalanx, so
            # `DEFAULT_BY_FACTION["Thousand Sons"] = "rubricae_phalanx"` keeps
            # the unconditional path working for the common case; armies that
            # explicitly pick Grand Coven (psyker-heavy lists) lose the save buff
            # — same outcome the codex enforces.
            #
            # APPROXIMATION vs the codex text (only one remaining after iter15):
            #   The codex says "unmodified Damage 1". SwegHammer reads the
            #   per-shot weapon damage AFTER Melta range bonuses have been
            #   composed (Melta is a +damage range modifier; the only
            #   "modifier to damage" in 10e). The two reconverge in the common
            #   case — a D1 bolter never picks up Melta — but a D1 Melta weapon
            #   (very rare in 10e) would lose the save buff under our reading
            #   even if the codex would keep it.
            # The save buff stacks at the save-modifier layer rather than the
            # wound-modifier layer used by the prior implementation (which
            # incorrectly modelled All Is Dust as a -1 to wound; that was the
            # 10e launch-index datasheet ability, removed when the codex landed
            # and replaced with the Rubricae Phalanx detachment +1 save rule).
            # The new behaviour is applied below at the `save_after_ap` reduction
            # step — see `_all_is_dust_save_buff` boolean computed here, consumed
            # ~25 lines down where save_after_ap is finalised.
            _all_is_dust_save_buff = False
            if (
                target.profile.faction == "Thousand Sons"
                and per_shot_dmg == 1.0
                and "RUBRICAE" in (target.profile.unit_keywords or ())
            ):
                _tgt_army = getattr(target, "army_ref", None)
                if _tgt_army is not None:
                    try:
                        _tgt_det = _tgt_army.resolve_detachment()
                    except Exception:
                        _tgt_det = None
                    if _tgt_det is not None and getattr(
                        _tgt_det, "all_is_dust", False,
                    ):
                        _all_is_dust_save_buff = True

            # ---- Thousand Sons "Rites of Coalescence" (Scarab Occult Terminators
            # datasheet ability, 10e current codex). Wahapedia verbatim: "While
            # this unit contains one or more PSYKER models, each time an attack
            # targets this unit, subtract 1 from the Wound roll." The Aspiring
            # Sorcerer is mandatory in a Scarab Occult squad and is the PSYKER
            # carrier, so the buff is effectively always-on as long as the squad
            # has at least one model left. We gate on profile name to be precise
            # (the rule is unique to Scarab Occult Terminators — no other TSON
            # datasheet carries it) plus the PSYKER unit-keyword as a sanity
            # check that the squad still contains its Sorcerer. Cited as
            # `simulator.rites_of_coalescence`.
            if (
                target.profile.name == "Scarab Occult Terminators"
                and "PSYKER" in (target.profile.unit_keywords or ())
            ):
                wound_mod_delta -= 1

            # ---- Resolute Will (Custodian Wardens datasheet, 10e Adeptus
            # Custodes codex). Wahapedia / BSData verbatim: "While a CHARACTER
            # is leading this unit, each time an attack targets this unit, if
            # the Strength characteristic of that attack is greater than the
            # Toughness characteristic of this unit, subtract 1 from the
            # Wound roll." Three-way gate:
            #   1. defender carries the `resolute_will` flag (set on the
            #      Custodian Wardens UnitProfile via overrides.json),
            #   2. defender is actually led — `leaders.is_actually_led` checks
            #      proximity AND that an in-range CHARACTER's host_keys lists
            #      the defender (a CHARACTER cannot be 'leading' a unit it
            #      can't legally attach to per the leader datasheet),
            #   3. attack Strength > defender Toughness.
            # Cited as `simulator.resolute_will`. iter24 fix to close part of
            # the Custodes -22.2pt under-performer gap.
            if target.profile.resolute_will and strength > target.profile.toughness:
                try:
                    from . import leaders as _leaders
                    if _leaders.is_actually_led(target):
                        wound_mod_delta -= 1
                except Exception:
                    pass

            # ---- Adeptus Mechanicus Doctrina Imperatives (10e army rule).
            # MR-D (claude/sim-calibration-5): rewritten to match the published
            # rule. The 10e rule is BUFF-ONLY — there is no -1-to-hit penalty
            # side; the prior implementation that gave +1 to one mode and -1 to
            # the other was a fabrication (caught during the MR audit). Real
            # rule (Wahapedia
            # https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus/):
            #   Protector: "Improve the Ballistic Skill characteristic of ranged
            #     weapons equipped by models in this unit by 1." (Heavy keyword
            #     uplift on ranged weapons skipped — the simulator does not track
            #     stationary state. The defensive -1 to be hit in melee is
            #     applied below in the defender block.)
            #   Conqueror: "Improve the Weapon Skill characteristic of melee
            #     weapons equipped by models in this unit by 1." (Assault keyword
            #     uplift on ranged weapons skipped — Advance-and-shoot is not
            #     a feature the simulator models. The +1 AP for battleline-
            #     adjacent attacks is applied below in the AP block.)
            # The rule's BATTLELINE-or-within-6"-of-BATTLELINE proximity gate is
            # approximated as army-wide here: most AdMech infantry are Skitarii
            # BATTLELINE and the simulator's abstracted positioning does not
            # resolve 6" aura adjacency for non-battleline support units.
            # Faction-gated on the attacker. Cited as
            # `simulator.doctrina_imperatives`.
            if p.faction == "Adeptus Mechanicus":
                own_army = getattr(self, "army_ref", None)
                imperative = (
                    getattr(own_army, "doctrina_imperative", None)
                    if own_army is not None else None
                )
                if imperative == "protector" and mode != "melee":
                    hit_mod_delta += 1
                elif imperative == "conqueror" and mode == "melee":
                    hit_mod_delta += 1

            # ---- Doctrina Imperatives — Protector defensive side. When the
            # TARGET unit is Adeptus Mechanicus and the active imperative is
            # Protector, melee attacks against it take -1 to Hit. Real-rule
            # gate is BATTLELINE or within 6" of friendly AdMech BATTLELINE.
            # ADMECH-DIAG-2 (2026-05-24) replaced the prior army-wide
            # approximation with the real proximity check (see
            # `_doctrina_battleline_proximity_met`). Only 2 of 42 AdMech
            # datasheets carry BATTLELINE (Skitarii Vanguard / Rangers),
            # so the army-wide approximation was making ~95% of AdMech
            # units more durable in melee than the codex grants them.
            # Cited as `simulator.doctrina_imperatives`.
            if mode == "melee" and target.profile.faction == "Adeptus Mechanicus":
                _tgt_army_di = getattr(target, "army_ref", None)
                _tgt_imp_di = (
                    getattr(_tgt_army_di, "doctrina_imperative", None)
                    if _tgt_army_di is not None else None
                )
                if (
                    _tgt_imp_di == "protector"
                    and _doctrina_battleline_proximity_met(target)
                ):
                    hit_mod_delta -= 1

            # CORE-RULE-FIX-2 — "Indirect Fire attack" trigger: ranged attack
            # from an Indirect Fire weapon against a target not visible to the
            # attacker. Per 10e core, such attacks (a) take -1 to Hit, (b)
            # cannot benefit from the Heavy keyword, and (c) cannot score
            # Critical Hits. The first leg is the standard indirect penalty;
            # the latter two are gated on this flag and consulted further down
            # at the crit-to-hit branch. Wahapedia:
            # https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Indirect-Fire
            indirect_fire_attack = (
                p.indirect_fire and mode != "melee" and not has_los
            )

            # ---- Heavy keyword: +1 to hit when shooting and the attacker did
            # NOT move this round. Melee never benefits. Indirect Fire attacks
            # (target not visible) cannot benefit from Heavy per 10e core.
            if (
                p.heavy
                and mode != "melee"
                and not self.moved_this_round
                and not indirect_fire_attack
            ):
                hit_mod_delta += 1

            # ---- Big Guns Never Tire: VEHICLE / MONSTER units that shoot
            # while in engagement range pay -1 to hit. Ranged only.
            if mode != "melee" and self.shooting_in_engagement:
                hit_mod_delta -= 1

            # ---- Indirect Fire: -1 to hit when target is not visible. Ranged only.
            if indirect_fire_attack:
                hit_mod_delta -= 1

            # ---- Lance: +1 to wound when this melee attack happens on a turn
            # the attacker declared a charge.
            # MAP-3-FIX — basket-fraction gating. Defer lance's wound modifier to
            # per-shot so heterogeneous squads (Beast Snagga Boyz, Skyweavers)
            # don't grant every shot the keyword. We record whether lance is
            # eligible here and apply it per-shot below via Bernoulli draw against
            # `p.lance_basket_fraction`. Single-weapon units have fraction = 1.0
            # so the Bernoulli always fires and behaviour matches the legacy gate.
            # Cited as `simulator.basket_fraction_gating`.
            # DRK-SKYSPLINTER-DISEMBARK: Rain of Cruelty grants transient
            # LANCE to a DRUKHARI unit's melee weapons "until the end of the
            # turn" after it disembarks from a TRANSPORT (set by
            # `simulator._disembark` and cleared by the standard
            # transient-flag reset). Composed via OR with the per-weapon
            # `profile.lance` keyword. The charge gate still applies —
            # LANCE itself is "+1 to wound when this attack was made on
            # the turn the bearer's unit declared a charge", and the
            # transient keyword grant does not bypass that. Cited as
            # `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark`.
            _lance_keyword_active = bool(
                p.lance or getattr(self, "transient_lance_this_turn", False)
            )
            _lance_eligible = bool(_lance_keyword_active and mode == "melee" and is_charging)
            # Basket-fraction gating only applies to the per-weapon profile
            # lance keyword (some specialist weapon in a heterogeneous
            # squad). The transient detachment grant covers ALL melee
            # weapons in the unit, so when the transient flag is the only
            # source we use fraction = 1.0 (every shot benefits).
            if getattr(self, "transient_lance_this_turn", False):
                _lance_fraction = 1.0
            else:
                _lance_fraction = float(getattr(p, "lance_basket_fraction", 1.0) or 1.0)

            # ---- Heavy cover: -1 to hit (in addition to the +1 to save which
            # the plain in_cover flag already grants below). Ranged shots only;
            # melee always ignores cover. Ignores Cover bypasses both effects.
            if (
                mode != "melee"
                and target.in_heavy_cover
                and not ignore_cover
            ):
                hit_mod_delta -= 1

            # ---- Stealth keyword: shooters take -1 to hit against the target.
            # Melee is unaffected (Stealth is a ranged defence).
            if mode != "melee" and target.profile.stealth:
                hit_mod_delta -= 1

            # ---- DAEMONS-DIAG-9: Daemon Prince "Prince of Darkness" aura —
            # grants Stealth to nearby LEGIONES DAEMONICA units. Read from
            # tgt_buffs (the target's defender-side buff dict). Same -1 ranged
            # hit modifier as static Stealth above; the two sources collapse to
            # a single -1 via the ±1 modifier cap below. Melee is unaffected.
            # Cited as LeaderAbility.Prince of Darkness in
            # data/rule_citations.d/leaders.json.
            if mode != "melee" and tgt_buffs.get("grants_stealth_aura"):
                hit_mod_delta -= 1

            # ---- Death Guard Contagions of Nurgle — Round 3+ Fulminating Plague:
            # an enemy unit (the ATTACKER here) within 3" of any DG model takes
            # -1 to its Hit rolls. We gate on `self` (the attacker) being near a
            # DG model on the opposing side, and on the attacker NOT being a DG
            # model itself (the aura debuffs *enemy* units). The ±1 cap below
            # subsumes the old "skip if already capped" gate — adding -1 here
            # when the delta is already -1 is harmless because the clamp
            # collapses the net to -1 anyway. Radius gated to 3" per the modern
            # Nurgle's Gift / Afflicted rule (Wahapedia). Cited as
            # `simulator.contagions_of_nurgle`.
            if (
                _contagion_round_for(self) >= 3
                and p.faction != "Death Guard"
                and _is_near_enemy_dg_model(self, radius=3.0)
            ):
                hit_mod_delta -= 1

            # ---- Apply the ±1 modifier cap (Wahapedia core rules: "Hit roll
            # modifiers are cumulative, but the Hit roll for an attack can
            # never be modified by more than -1 or +1." Same for Wound rolls).
            # `hit_target` was already set to its base value; positive delta =
            # +1 to hit = LOWER target (easier roll); negative delta = -1 to
            # hit = HIGHER target (harder roll). Symmetric for wound. The
            # arithmetic clamps to [2, 7] which preserves existing semantics
            # (target 7 = auto-miss, target 2 = always succeeds bar nat-1).
            # Cited as `simulator.modifier_cap_plus_minus_one`.
            hit_mod_clamped = max(-1, min(1, hit_mod_delta))
            wound_mod_clamped = max(-1, min(1, wound_mod_delta))
            hit_target = max(2, min(7, hit_target - hit_mod_clamped))
            wound_target = max(2, min(7, wound_target - wound_mod_clamped))
            # MAP-3-FIX — pre-compute the lance-on variant of the wound target so
            # the per-shot Bernoulli draw can pick between them without redoing
            # the clamp math each shot. wound_target_lance applies the lance +1
            # to the underlying delta (still subject to the ±1 cap) and clamps.
            if _lance_eligible:
                _wound_mod_lance_clamped = max(-1, min(1, wound_mod_delta + 1))
                wound_target_with_lance = max(
                    2, min(7, (wound_target + wound_mod_clamped) - _wound_mod_lance_clamped),
                )
            else:
                wound_target_with_lance = wound_target

            # ---- Anti-X: lower the crit-wound threshold against matching keywords ----
            # MAP-3-FIX — basket-fraction gating. The MAP-3 UNION lets a single
            # specialist weapon (Skyweaver Haywire Cannon, Beast Snagga Klaw)
            # tag the whole synthetic basket with Anti-X. Without gating, every
            # shot in the squad's volley would benefit from the lowered crit
            # threshold. We collect every applicable (kw, thresh, fraction)
            # tuple here and resolve the per-shot threshold inside the loop via
            # a Bernoulli draw on fraction. Single-weapon units have fraction
            # = 1.0 so the gate always fires (legacy behaviour preserved).
            # Cited as `simulator.basket_fraction_gating`.
            _anti_applicable: list = []  # list of (thresh:int, fraction:float)
            if p.anti_keywords and target.profile.unit_keywords:
                target_kw = set(target.profile.unit_keywords)
                _anti_fractions = dict(getattr(p, "anti_keyword_basket_fractions", ()) or ())
                for kw, thresh in p.anti_keywords:
                    if kw in target_kw:
                        _frac = float(_anti_fractions.get(kw, 1.0) or 1.0)
                        _anti_applicable.append((int(thresh), _frac))

            save_after_ap = target.profile.save - ap
            # Precision: a ranged shot at a CHARACTER target pierces concealment —
            # cover does not improve the save. Same effect as Ignores Cover, but
            # gated on the target's keywords.
            precision_pierces_cover = (
                p.precision
                and mode != "melee"
                and "CHARACTER" in (target.profile.unit_keywords or ())
            )
            # ---- Benefits of Cover (10e core rule). Ranged-only: melee
            # attacks never benefit from cover. +1 to the armour save (one
            # pip better). INFANTRY models cannot improve their save to
            # better than 3+ by virtue of this rule; vehicles / monsters /
            # mounted models lack the 3+ cap (only the universal 2+ floor
            # applies). Wahapedia core rules — Terrain Features / Benefits
            # of Cover. Cited as `simulator.benefits_of_cover`.
            if (
                mode != "melee"
                and target.in_cover
                and not ignore_cover
                and not precision_pierces_cover
            ):
                improved = save_after_ap - 1
                target_is_infantry = "INFANTRY" in (target.profile.unit_keywords or ())
                if target_is_infantry:
                    # INFANTRY cannot improve their save below 3+ by virtue
                    # of cover; if already 3+ or better, cover does nothing.
                    improved = max(improved, 3)
                improved = max(2, improved)  # universal 2+ armour floor
                # Cover never makes a save worse than it already was.
                save_after_ap = min(save_after_ap, improved)
            # ---- Target's buffs: +1 to armour save ----
            # 10e core rule (Wahapedia core rules, "Modifiers"): the modified
            # Save characteristic cannot be more than +1 better or -1 worse
            # than the unmodified value. AP is NOT a modifier — it acts on
            # the attack's AP characteristic, not on the defender's Save
            # characteristic — so AP stacks freely with one +1 save buff.
            # Multiple ability-sourced +1-save sources (army-wide
            # plus_one_save + Lightning-Fast Reactions + All Is Dust) must
            # clamp to a single net +1 per the ±1 cap.
            # Cited as `simulator.save_modifier_cap_plus_minus_one`.
            save_buff_sources = 0
            if tgt_buffs["plus_one_save"]:
                save_buff_sources += 1
            # Lightning-Fast Reactions (Warhost) — transient +1 save on the
            # target unit for the round.
            if target.transient_plus_one_save:
                save_buff_sources += 1
            # ---- Necrons Awakened Dynasty — Protocol of the Eternal Conquerors
            # (army-wide +1 save, round-gated). NECRONS-CLOSE
            # (claude/sim-calibration-6): wires the fourth Command Protocol as
            # a single-round defensive uplift on round 3 only. Real codex text
            # auto-passes the first failed armour save per NECRONS unit per
            # phase; the closest clean simulator hook is +1 to the armour
            # save, contributed into the same `save_buff_sources` counter so
            # the existing ±1 save-modifier cap clamps it as a single net +1
            # alongside any other +1-save source. Gate: defender faction ==
            # "Necrons" AND defender's detachment carries
            # `necrons_army_wide_plus_one_save_command_protocol` (set by
            # AWAKENED_DYNASTY) AND current battle round == 3.
            # Cited as
            # `AWAKENED_DYNASTY.necrons_army_wide_plus_one_save_command_protocol`.
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/
            # #Command-Protocols.
            if target.profile.faction == "Necrons":
                _own_army_ec = getattr(target, "army_ref", None)
                if _own_army_ec is not None:
                    try:
                        _det_ec = _own_army_ec.resolve_detachment()
                    except Exception:
                        _det_ec = None
                    if _det_ec is not None and getattr(
                        _det_ec,
                        "necrons_army_wide_plus_one_save_command_protocol",
                        False,
                    ):
                        _battle_ec = getattr(_own_army_ec, "_battle_ref", None)
                        _round_ec = (
                            getattr(_battle_ec, "_current_round", 0)
                            if _battle_ec is not None else 0
                        )
                        # Round 3 only — single-round defensive uplift to
                        # keep the Command Protocol rotation approximately
                        # one-protocol-per-round on average.
                        if _round_ec == 3:
                            save_buff_sources += 1
            # All Is Dust (Rubricae Phalanx, see boolean computed in the
            # wound-modifier block above). +1 to the armour save when the
            # incoming attack is Damage 1 AND the defender carries the RUBRICAE
            # keyword. Cited as `simulator.all_is_dust`.
            if _all_is_dust_save_buff:
                save_buff_sources += 1
            if save_buff_sources > 0:
                # Clamp net save-modifier to +1 (the ±1 cap). The 2+ floor
                # remains as a hard armour-save floor independent of the cap.
                save_after_ap = max(2, save_after_ap - 1)
            invuln = target.profile.invuln_save
            # ---- Target's buffs: army-wide invuln. Only overrides if better
            # (lower number) than what the target already has. 7 = unset.
            tgt_invuln_buff = int(tgt_buffs["extra_invuln"])
            if tgt_invuln_buff <= 6 and tgt_invuln_buff < invuln:
                invuln = tgt_invuln_buff
            # Glamour of Tzeentch (Cult of Magic) — transient 4++ invuln on the
            # target unit for the round. Same "only override if better" rule.
            if target.transient_invuln_4 and invuln > 4:
                invuln = 4
            effective_save = min(save_after_ap, invuln) if invuln <= 6 else save_after_ap
            save_target = effective_save  # 7 = no save

            # Re-roll flags from attacker's buffs.
            att_reroll_hit_ones = bool(att_buffs["reroll_hit_ones"])
            att_reroll_wound_ones = bool(att_buffs["reroll_wound_ones"])
            # "Re-roll ALL failed hits" defaults to off — only the Votann
            # Judgement Tokens path (below) and Marines Oath of Moment turn
            # it on.
            att_reroll_all_hits = False
            # "Re-roll ALL failed wounds" defaults to off. Set by Oath of
            # Moment for a Marine attacker firing at the army's oath target.
            # Distinct from `att_reroll_wound_ones` (1s only): the rule grants
            # a full failure re-roll, not just nat-1s.
            att_reroll_all_wounds = False

            # Resolve the attacker's owning Army once; downstream gates
            # (Oath of Moment, Votann tokens) all read it.
            own_army = getattr(self, "army_ref", None)

            # ---- Leagues of Votann — Eye of the Ancestors (RETIRED) ----
            # iter25-V1: the launch-day Eye of the Ancestors rule granted
            # escalating re-roll buffs (hit 1s at 1 token, full hit re-rolls +
            # wound 1s at 3 tokens) to Votann attacks against marked targets.
            # That rule has been REPLACED in the current 10e codex by
            # Prioritised Efficiency, which is purely an objective-token
            # economy (Yield Points / Hostile Acquisition / Fortify Takeover)
            # and grants NO re-roll buffs on attacks. Modelling the retired
            # buffs on top of the simulator's other Votann uplifts was the
            # largest single contributor to the +16.8 pt Leagues of Votann
            # over-performance in the iter25 evaluation.
            #
            # The token bookkeeping itself (`_maybe_award_judgement_token`,
            # `Army.judgement_tokens`) is kept in place because the Ancestral
            # Sentence Oathband stratagem still references it as the place to
            # record "this enemy unit has been marked", and downstream gates
            # may use the marker for token-only triggers (no buff effect).
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/#Prioritised-Efficiency
            # The re-roll branch is intentionally removed — do not re-add
            # without a verbatim Wahapedia citation per CLAUDE.md §10.

            # ---- Adeptus Astartes Oath of Moment (army rule, 10e). When the
            # attacker is a Marine (any chapter) AND its army has declared
            # this round's oath target on this defender's uid, every attack
            # against that defender re-rolls the HIT roll only. The codex
            # rule (Wahapedia, verbatim) reads: "each time an attack made by
            # a model from your army targets the unit selected as the target
            # of the Oath of Moment, you can re-roll the Hit roll." There is
            # no wound-roll re-roll — the prior implementation that set
            # `att_reroll_all_wounds = True` was a fabrication (it stacked
            # the codex hit re-roll with a non-existent wound re-roll,
            # roughly doubling the buff). Wound re-rolls only enter via
            # detachment-specific stratagems / leader abilities. The flag
            # composes with the existing 1s-only re-rolls but the
            # `att_reroll_all_hits` branch takes priority in the loop below
            # (one re-roll per die — never stacks). Cited as
            # `simulator.oath_of_moment`.
            if (
                own_army is not None
                and is_marine_faction(p.faction)
                and getattr(own_army, "oath_target_uid", None) == target.uid
            ):
                att_reroll_all_hits = True

            # ---- Imperial Knights — Code Chivalric (army rule, 10e). The army
            # rule lets the controller pick one Quality at battle start; the
            # "martial valour" Quality (Wahapedia verbatim, https://wahapedia.ru/
            # wh40k10ed/factions/imperial-knights/): "Each time this model is
            # selected to shoot or fight, you can re-roll one Hit roll and you
            # can re-roll one Wound roll." SwegHammer models the army rule by
            # always taking the martial-valour pick (the offensive Quality —
            # the other two Qualities are movement / objective-OC bumps the sim
            # cannot express). APPROXIMATION: "re-roll one die of choice" is
            # mapped to "re-roll natural 1s" — strictly weaker (re-roll one is
            # ~+0.17 vs +0.5 for re-roll-of-choice on a 3+/4+ swing), erring on
            # the under-buff side per the SC5 audit's preference against
            # fabricated upbuffs. Faction-gated to Imperial Knights so Chaos
            # Knights (whose army rule is Harbingers of Dread; that rule is now
            # implemented separately above and in simulator._run_battleshock_phase)
            # is untouched.
            # Cited as `simulator.code_chivalric`.
            if (
                own_army is not None
                and (p.faction or "") == "Imperial Knights"
            ):
                att_reroll_hit_ones = True
                att_reroll_wound_ones = True

            # Fire and Fade (Aeldari Warhost stratagem) — transient
            # re-roll hit rolls of 1 on shooting attacks for the round.
            att_reroll_hits_shooting_ones = (
                mode != "melee" and getattr(self, "transient_reroll_hits_shooting", False)
            )
            if att_reroll_hits_shooting_ones:
                att_reroll_hit_ones = True

            # ST-1: transient wound-reroll grants from stratagems that actually
            # cite "re-roll Wound rolls" (Warrior Pride, Combat Debarkation,
            # Creeping Blight wound leg) — full failed-wound re-roll for the
            # round. Composes with att_reroll_all_wounds (Oath of Moment) via
            # OR; the wound-loop only ever fires one re-roll per die.
            # transient_reroll_wounds_ones is the weaker "1s only" variant for
            # stratagems that grant a wound-1 re-roll (Big Krumpin'); composes
            # with att_reroll_wound_ones via OR.
            if getattr(self, "transient_reroll_wounds", False):
                att_reroll_all_wounds = True
            if getattr(self, "transient_reroll_wounds_ones", False):
                att_reroll_wound_ones = True

            # Drukhari Power From Pain (10e codex, current Wahapedia text):
            # the army rule does NOT grant passive LETHAL HITS from holding a
            # Pain Token. Tokens accrue into a pool and can be SPENT to
            # Empower a unit, whereupon that unit's per-datasheet "Pain
            # ability" takes effect until the end of the phase. Per-datasheet
            # Pain abilities are not catalogued in SwegHammer yet, so no
            # token-driven offensive buff fires here. The previous unconditional
            # `p.lethal_hits or (self.pain_tokens > 0 and faction == 'Drukhari')`
            # branch was a fabrication that gave army-wide free LETHAL HITS
            # to every multi-model Drukhari unit that had lost one model. This
            # was the largest non-structural driver of Drukhari's +33pt sim-vs-
            # meta overshoot in wave 42 (DRK-PAIN-TOKENS). Wahapedia:
            # https://wahapedia.ru/wh40k10ed/factions/drukhari/
            effective_lethal_hits = p.lethal_hits
            # ST-1: per-round transient LETHAL HITS grant from stratagems that
            # actually cite [LETHAL HITS] (Wrath of the Ancestors, Power Of The
            # WAAAGH!, Archaeotech Munitions). Composes via OR with profile and
            # army-rule sources; the crit branch fires the lethal auto-wound
            # exactly once per crit-to-hit. Faction-unrestricted because the
            # stratagem dispatcher gates faction at the firing site.
            if getattr(self, "transient_lethal_hits", False):
                effective_lethal_hits = True
            # World Eaters Blood Tithe — 4-BT spend grants [LETHAL HITS] on a
            # WE unit for the phase. SwegHammer collapses "this phase" to "this
            # round" since the activation loop doesn't break phases out. The
            # army-level flag stores the round in which BT-4 fired; we compare
            # against the live battle round so the buff lapses next round even
            # if we skip clearing it. Faction-gated to keep allies clean.
            # Composes with profile.lethal_hits via OR (never double-fires —
            # the gate is at the crit-to-hit branch below, fires once per crit).
            if p.faction == "World Eaters" and not effective_lethal_hits:
                own_army = getattr(self, "army_ref", None)
                if own_army is not None:
                    bt_round = getattr(own_army, "blood_tithe_lethal_hits_round", None)
                    battle = getattr(own_army, "_battle_ref", None)
                    cur_round = getattr(battle, "_current_round", 0) if battle else 0
                    if bt_round is not None and bt_round == cur_round:
                        effective_lethal_hits = True

            # ---- World Eaters Blessings of Khorne (10e army rule) — Warp
            # Blades grants army-wide melee LETHAL HITS for the battle round.
            # Gate: mode == "melee" AND attacker faction == "World Eaters"
            # AND the army's `blessings_warp_blades_round` stamp matches the
            # current battle round. Composes with `p.lethal_hits` via OR.
            # Cited as `simulator.blessings_of_khorne`.
            if (
                mode == "melee"
                and p.faction == "World Eaters"
                and not effective_lethal_hits
            ):
                _own_army_bok = getattr(self, "army_ref", None)
                if _own_army_bok is not None:
                    _wb_round = getattr(
                        _own_army_bok, "blessings_warp_blades_round", None,
                    )
                    _battle_bok = getattr(_own_army_bok, "_battle_ref", None)
                    _cur_round_bok = (
                        getattr(_battle_bok, "_current_round", 0)
                        if _battle_bok is not None else 0
                    )
                    if _wb_round is not None and _wb_round == _cur_round_bok:
                        effective_lethal_hits = True

            # ---- T'au Empire Mont'ka Killing Blow — Guided [LETHAL HITS]
            # (rounds 1-3). Wahapedia (Mont'ka, Killing Blow) verbatim:
            # "During the first, second and third battle rounds, while a
            # unit is a Guided unit, its ranged weapons have the [LETHAL
            # HITS] ability." T-AU-DIAG-2 (2026-05-23) corrects the prior
            # APPROXIMATION which fired this army-wide every round; the
            # detachment text is explicit about the rounds 1-3 window.
            # Guided population still happens every round in
            # Battle._run_markerlight_phase (the Marked/Guided base status
            # is granted by the army rule with no round gate), but the
            # [LETHAL HITS] keyword interaction is the detachment effect
            # and only applies in rounds 1-3. Shooting branch only — melee
            # Guided does not exist in 10e. Composes with profile.lethal_hits
            # via OR (one re-roll branch in the loop, no double-fire).
            # Cited as `MONTKA.lethal_hits_on_guided`.
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka
            if (
                mode != "melee"
                and not effective_lethal_hits
                and own_army is not None
                and target.uid in getattr(own_army, "guided_enemy_uids", set())
                and (p.faction or "").lower() in ("t'au empire", "tau empire")
            ):
                det = own_army.resolve_detachment()
                if det is not None and getattr(det, "lethal_hits_on_guided", False):
                    _battle_ref_tau = getattr(own_army, "_battle_ref", None)
                    _cur_round_tau = (
                        getattr(_battle_ref_tau, "_current_round", 0)
                        if _battle_ref_tau is not None else 0
                    )
                    if 1 <= _cur_round_tau <= 3:
                        effective_lethal_hits = True

            # ---- Astra Militarum Combined Arms detachment — Born Soldiers
            # (army-wide ranged [LETHAL HITS] gated on REGIMENT-vs-non-V/M and
            # SQUADRON-vs-V/M matchups). Wahapedia verbatim: "Each time a model
            # in a REGIMENT unit from your army makes a ranged attack that
            # targets a visible unit (excluding MONSTERS and VEHICLES), that
            # attack has the [LETHAL HITS] ability. Each time a model in a
            # SQUADRON unit from your army makes a ranged attack that targets
            # a visible MONSTER or VEHICLE unit, that attack has the [LETHAL
            # HITS] ability."
            # APPROXIMATION: BSData v10.6.0 doesn't tag datasheets with the
            # codex's REGIMENT / SQUADRON keywords. AM-DIAG-2 (2026-05-24)
            # narrowed the REGIMENT proxy from INFANTRY → BATTLELINE after
            # the INFANTRY mapping was found to massively over-grant LETHAL
            # HITS: it pulled in 40+ non-REGIMENT AM INFANTRY units
            # (Tempestus Scions, Kasrkin, Tempestus Aquilons, Ratlings,
            # Ogryns, Bullgryns, all Commissars / Commissar Yarrick /
            # Commissar Graves on Foot, Tech-Priest Enginseer, Primaris
            # Psyker, Sly Marbo, Ursula Creed, Cadian Castellan, Lord Solar
            # Leontus, Krieg/Cadian/Catachan/Tempestus Command Squads,
            # Inquisition agents, Heavy Weapons Squads, etc.) — none of
            # which carry the codex REGIMENT keyword. The BATTLELINE proxy
            # catches the three core REGIMENT troop choices that the rule
            # was clearly written for (Cadian Shock Troops, Catachan Jungle
            # Fighters, Death Korps of Krieg). Trade-off: this also
            # under-covers a handful of non-BATTLELINE REGIMENT squads
            # (Heavy Weapons Squads, Command Squads), which is the much
            # smaller error vs the over-firing the INFANTRY proxy caused.
            # AM-DIAG-3 (2026-05-24) followed up by narrowing SQUADRON
            # from "any VEHICLE-keyword AM attacker" to an explicit name
            # allowlist of the codex SQUADRON datasheets — see
            # `_AM_BORN_SOLDIERS_SQUADRON_NAMES` above for the contents
            # and the citation.
            # Composes with profile.lethal_hits via OR (one re-roll branch
            # in the loop, no double-fire).
            # Cited as `COMBINED_REGIMENT.am_born_soldiers_lethal_hits`.
            if (
                mode != "melee"
                and not effective_lethal_hits
                and own_army is not None
                and (p.faction or "") == "Astra Militarum"
            ):
                det = own_army.resolve_detachment()
                if det is not None and getattr(det, "am_born_soldiers_lethal_hits", False):
                    attacker_kws = set(p.unit_keywords or ())
                    target_kws = set((target.profile.unit_keywords or ()) if target else ())
                    target_is_vm = (
                        "VEHICLE" in target_kws or "MONSTER" in target_kws
                    )
                    # REGIMENT leg: BATTLELINE-keyword attacker (the three
                    # core Cadian / Catachan / Krieg troop squads, which all
                    # carry the codex REGIMENT keyword) vs non-VEHICLE/MONSTER
                    # target.
                    if (
                        "BATTLELINE" in attacker_kws
                        and "VEHICLE" not in attacker_kws
                        and "MONSTER" not in attacker_kws
                        and not target_is_vm
                    ):
                        effective_lethal_hits = True
                    # SQUADRON leg: attacker is on the explicit AM SQUADRON
                    # roster vs VEHICLE/MONSTER target. AM-DIAG-3 (2026-05-24)
                    # narrowed the SQUADRON proxy from "any VEHICLE-keyword AM
                    # attacker" to a curated allowlist after the VEHICLE proxy
                    # was found to over-grant LETHAL HITS to transports
                    # (Chimera, Taurox, Taurox Prime, Centaur RSV, Storm
                    # Chimera), flyers (Valkyrie, Vendetta, Avenger Strike
                    # Fighter, Vulture, Marauder, Voss-pattern Lightning,
                    # Arvus Lighter, Aquila Lander), self-propelled HEAVY
                    # artillery (Basilisk, Manticore, Wyvern, Deathstrike,
                    # Hydra, Colossus, Medusa, Griffon), super-heavies
                    # (Baneblade / Banehammer / Banesword / Doomhammer /
                    # Hellhammer / Shadowsword / Stormblade / Stormlord /
                    # Stormsword), Knights, and vehicle CHARACTERS that don't
                    # carry the SQUADRON keyword — none of which are in the
                    # codex SQUADRON keyword list. Per Wahapedia Astra
                    # Militarum datasheets, the SQUADRON keyword belongs to:
                    # Leman Russ Battle Tank + all Russ variants
                    # (Demolisher, Eradicator, Executioner, Exterminator,
                    # Punisher, Vanquisher) + Leman Russ Commander; Rogal
                    # Dorn Battle Tank + Rogal Dorn Commander; Hellhound
                    # (Bane Wolf / Devil Dog are weapon-loadout variants of
                    # the same datasheet, not separate datasheets in BSData
                    # v10.6.0); Armoured Sentinels, Scout Sentinels, and the
                    # Sentinel Commander [Crucible]. Match on
                    # `UnitProfile.name` because BSData v10.6.0 does not
                    # surface a SQUADRON unit keyword and the profile has
                    # no datasheet-key field. See
                    # https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
                    # (each Leman Russ / Rogal Dorn / Hellhound / Sentinel
                    # datasheet carries the SQUADRON keyword in its header).
                    elif (
                        p.name in _AM_BORN_SOLDIERS_SQUADRON_NAMES
                        and target_is_vm
                    ):
                        effective_lethal_hits = True

            # ---- Orks War Horde detachment — Get Stuck In (army-wide melee
            # SUSTAINED HITS 1). BSData v10.6.0 verbatim: "Melee weapons equipped
            # by ORKS models from your army have the [SUSTAINED HITS 1] ability."
            # Gate: mode == "melee" AND attacker faction == "Orks" AND the
            # attacker's army's detachment carries the `melee_sustained_hits
            # _army_wide` flag (set by WAR_HORDE). The effective sustained-hits
            # multiplier is incremented by 1 for the duration of this attack
            # resolution; stacks additively with any per-weapon `sustained_hits`
            # already on the profile (a SUSTAINED HITS 1 weapon would compound
            # to SUSTAINED HITS 2, matching codex behaviour). Cited as
            # `WAR_HORDE.melee_sustained_hits_army_wide`.
            #
            # Route the per-weapon SUSTAINED HITS value by attack mode. Before
            # iter28-MS1 the simulator read `p.sustained_hits` unconditionally,
            # but that field is populated from the RANGED primary weapon (see
            # `code/bsdata/mapper.py`). Reading it in melee mode fabricated
            # ranged SUSTAINED HITS values onto Orks Choppas and several other
            # mixed-loadout units. `p.melee_sustained_hits` is sourced from the
            # melee weapon and defaults to 0 — the correct value for vanilla
            # Choppas (BSData v10.6.0 Keywords: -).
            if mode == "melee":
                effective_sustained_hits = int(p.melee_sustained_hits or 0)
            else:
                effective_sustained_hits = int(p.sustained_hits or 0)
            # LC1-A — generalised gate: any faction whose detachment carries
            # the `melee_sustained_hits_army_wide` flag triggers SUSTAINED
            # HITS 1 on melee. Previously Orks-only; widened so Adeptus
            # Custodes Auric Champions (alt to Shield Host) can re-use the
            # same plumbing. The detachment IS the faction-specific gate —
            # only WAR_HORDE (Orks) and AURIC_CHAMPIONS (Custodes) set the
            # flag; the gate verifies the attacker's army's resolved
            # detachment matches the attacker's faction.
            if mode == "melee":
                _own_army = getattr(self, "army_ref", None)
                if _own_army is not None:
                    try:
                        _det = _own_army.resolve_detachment()
                    except Exception:
                        _det = None
                    if (_det is not None
                            and getattr(_det, "melee_sustained_hits_army_wide", False)
                            and getattr(_det, "faction", None) == p.faction):
                        effective_sustained_hits += 1

            # ---- World Eaters Blessings of Khorne (10e army rule) — Martial
            # Excellence grants army-wide melee SUSTAINED HITS 1 for the
            # battle round. Gate: mode == "melee" AND attacker faction ==
            # "World Eaters" AND the army's
            # `blessings_martial_excellence_round` stamp matches the live
            # battle round. Stacks additively with any per-weapon
            # `melee_sustained_hits` already on the profile, matching the
            # WAR_HORDE compositional convention. Cited as
            # `simulator.blessings_of_khorne`.
            if mode == "melee" and p.faction == "World Eaters":
                _own_army_me = getattr(self, "army_ref", None)
                if _own_army_me is not None:
                    _me_round = getattr(
                        _own_army_me, "blessings_martial_excellence_round", None,
                    )
                    _battle_me = getattr(_own_army_me, "_battle_ref", None)
                    _cur_round_me = (
                        getattr(_battle_me, "_current_round", 0)
                        if _battle_me is not None else 0
                    )
                    if _me_round is not None and _me_round == _cur_round_me:
                        effective_sustained_hits += 1

            # ---- Necrons Awakened Dynasty — Protocol of the Vengeful Stars
            # (army-wide ranged SUSTAINED HITS 1). AD-PR (claude/sim-cal-4):
            # alternates with Hungry Void by battle-round parity. Vengeful
            # Stars fires on ODD rounds (1, 3, 5) — opposite parity to
            # Hungry Void (EVEN). Gate: mode != "melee" AND attacker faction
            # == "Necrons" AND detachment carries `necrons_ranged_sustained
            # _hits_army_wide` (set by AWAKENED_DYNASTY) AND current battle
            # round is odd. Stacks additively with per-weapon
            # `sustained_hits` already on the profile, matching the
            # melee_sustained_hits_army_wide compositional behaviour above.
            # Cited as
            # `AWAKENED_DYNASTY.necrons_ranged_sustained_hits_army_wide`.
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/
            # #Command-Protocols.
            if mode != "melee" and p.faction == "Necrons":
                _own_army_vs = getattr(self, "army_ref", None)
                if _own_army_vs is not None:
                    try:
                        _det_vs = _own_army_vs.resolve_detachment()
                    except Exception:
                        _det_vs = None
                    if _det_vs is not None and getattr(
                        _det_vs, "necrons_ranged_sustained_hits_army_wide", False,
                    ):
                        _battle_vs = getattr(_own_army_vs, "_battle_ref", None)
                        _round_vs = (
                            getattr(_battle_vs, "_current_round", 0)
                            if _battle_vs is not None else 0
                        )
                        # Odd round (1, 3, 5) -> Vengeful Stars active.
                        # Round 0 (pre-battle / no battle ref) treated as
                        # inactive so standalone tests without a battle
                        # round set see no buff unless they configure the
                        # round explicitly.
                        if _round_vs % 2 == 1 and _round_vs > 0:
                            effective_sustained_hits += 1

            # ST-1 transient SUSTAINED HITS grant — stratagems that cite
            # [SUSTAINED HITS 1] (Blitzing Firepower, Storm of Fire) used to
            # proxy via transient_plus_one_to_hit_shooting, which is strictly
            # stronger because +1-to-hit triggers extra-hit gains on every
            # die above the previous fail threshold whereas SUSTAINED HITS 1
            # only fires on the natural 6. Routes through the same
            # `effective_sustained_hits` accumulator as the army-wide /
            # detachment sources so all the downstream crit-extra-hit
            # accounting is shared.
            _ts_h = int(getattr(self, "transient_sustained_hits", 0) or 0)
            if _ts_h > 0:
                effective_sustained_hits += _ts_h

            # DAEMONS-LOCUS-V1 follow-up — leader aura SUSTAINED HITS grants
            # (Locus of Change / Locus of Putrescence / Locus of Slaanesh).
            # `att_buffs` is populated by `effective_buffs` (code/leaders.py)
            # when an attacker is within aura range of a friendly Locus-bearing
            # Herald and the host_keys gate passes. Mode-routed so the ranged
            # Locus doesn't leak into melee resolution and vice versa.
            if mode == "melee":
                _aura_sh_m = int(att_buffs.get("sustained_hits_melee", 0) or 0)
                if _aura_sh_m > 0:
                    effective_sustained_hits += _aura_sh_m
            else:
                _aura_sh_r = int(att_buffs.get("sustained_hits_ranged", 0) or 0)
                if _aura_sh_r > 0:
                    effective_sustained_hits += _aura_sh_r

            # ---- Adeptus Custodes Shield Host — Martial Ka'tah / Martial Mastery:
            # Crit-on-5+ portion. The AP+1 portion is applied EARLIER (before
            # `save_after_ap` is computed) — see the block tagged
            # `SHIELD_HOST.melee_ap_plus_one` above. This block only sets the
            # crit threshold that gates `crit_hit = (roll == 6)` later in the
            # attack loop. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/
            # adeptus-custodes/#Shield-Host.
            # C1 (claude/sim-calibration-4): Crit-on-5+ fires on EVEN battle
            # rounds (2, 4). AP+1 fires on ODD battle rounds (1, 3, 5). This
            # alternation averages to one bullet active per round, matching
            # the codex "pick one bullet at the start of each battle round"
            # rule (prior implementation applied both always-on, strictly
            # stronger than codex). Cited as
            # `SHIELD_HOST.melee_crit_on_5_plus_hits`.
            melee_crit_threshold = 6   # canonical 10e: nat 6 to-hit = Critical Hit
            if mode == "melee" and p.faction == "Adeptus Custodes":
                _own_army = getattr(self, "army_ref", None)
                if _own_army is not None:
                    try:
                        _det = _own_army.resolve_detachment()
                    except Exception:
                        _det = None
                    if _det is not None and getattr(
                        _det, "melee_crit_on_5_plus_hits", False,
                    ):
                        _battle_c5 = getattr(_own_army, "_battle_ref", None)
                        _round_c5 = (
                            getattr(_battle_c5, "_current_round", 0)
                            if _battle_c5 is not None else 0
                        )
                        # Even round (2, 4) -> Crit-on-5+ bullet active. Round
                        # 0 (pre-battle / no battle ref) treated as inactive
                        # so standalone tests without a battle round set see
                        # no buff unless they configure the round explicitly.
                        if _round_c5 > 0 and _round_c5 % 2 == 0:
                            melee_crit_threshold = 5

            for _ in range(n_attacks):
                # MAP-3-FIX — per-shot Bernoulli gating for partial-coverage
                # weapon keywords. Lance and Anti-X resolve their per-shot value
                # here so a heterogeneous squad's specialist-weapon keyword fires
                # on the right proportion of shots rather than every shot. The
                # Devastating Wounds gate is applied at its consumption site
                # below (inside the wound-resolution branch).
                #
                # Lance: pick which pre-computed wound_target applies this shot.
                if _lance_eligible and random.random() < _lance_fraction:
                    _shot_wound_target = wound_target_with_lance
                else:
                    _shot_wound_target = wound_target
                # Anti-X: among applicable (kw, thresh, fraction) entries, take
                # the LOWEST threshold whose Bernoulli draw fires. If none fires,
                # fall back to 6 (the default crit-wound threshold).
                anti_crit_threshold = 6
                for _thresh, _frac in _anti_applicable:
                    if _thresh < anti_crit_threshold and random.random() < _frac:
                        anti_crit_threshold = _thresh
                # ---- Torrent: skip the to-hit roll, attack auto-hits ----
                if p.torrent:
                    crit_hit = False   # torrent has no crit-on-hit
                else:
                    roll = random.randint(1, 6)
                    # CORE-RULE-FIX-5 — track the unmodified physical roll
                    # separately so Crit-Hit gating only fires on the original
                    # die. 10e core: "an unmodified Hit roll of 6 is always a
                    # successful hit, and is known as a Critical Hit." Dice
                    # *substituted* in by faction rules (Strands of Fate, Acts
                    # of Faith Miracle Dice, Command Re-Roll) are replacements,
                    # NOT original rolls, so a substituted 6 must NOT crit.
                    # Rerolls (Twin-Linked, Oath of Moment, Fire-and-Fade)
                    # behave differently: 10e treats the rerolled die's value
                    # as the roll, so unmodified_roll updates after a reroll.
                    unmodified_roll = roll
                    # Re-roll handling. Two compatible flags:
                    #   att_reroll_hit_ones: replace a natural 1 (detachment /
                    #     Judgement Tokens tier-1).
                    #   att_reroll_all_hits: replace ANY failure (Judgement
                    #     Tokens tier-3; superset of reroll_hit_ones).
                    # Only one re-roll per die — `att_reroll_all_hits` takes
                    # priority and a fired re-roll under it does not stack
                    # another re-roll under reroll_hit_ones.
                    if att_reroll_all_hits and roll < hit_target:
                        roll = random.randint(1, 6)
                        unmodified_roll = roll
                    elif att_reroll_hit_ones and roll == 1:
                        roll = random.randint(1, 6)
                        unmodified_roll = roll
                    # Fire and Fade (Warhost) — transient re-roll natural 1s
                    # to hit on shooting attacks. Compose with reroll_hit_ones
                    # above but never re-roll the same die twice — both flags
                    # target the natural-1 case so the first that triggered the
                    # re-roll has already swapped the value.
                    if (
                        att_reroll_hits_shooting_ones
                        and roll == 1
                        and not att_reroll_hit_ones
                    ):
                        roll = random.randint(1, 6)
                        unmodified_roll = roll
                    # Strands of Fate (Aeldari army rule, 10e) — Fate dice
                    # substitution on a failed Hit roll. If the attacker is an
                    # AELDARI model from an army with at least one Fate die
                    # in pool, and the natural roll is a miss, we pop the
                    # lowest die in the pool that still hits and substitute.
                    # No die is spent if substitution wouldn't convert the
                    # miss to a hit (greedy floor at hit_target). Cited as
                    # `simulator.strands_of_fate`. Wahapedia:
                    # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
                    if (
                        roll < hit_target
                        and p.faction == "Aeldari"
                    ):
                        own_army = getattr(self, "army_ref", None)
                        if own_army is not None and own_army.has_fate_dice():
                            # AI-5: gate spending by stakes. Only treat the
                            # hit as "high value" if the weapon's per-shot
                            # damage is >= 2 (a lascannon-shot miss is worth
                            # a Fate die; a shuriken-catapult miss is not).
                            sub = own_army.pop_fate_die_meeting(
                                hit_target,
                                high_value=(per_shot_dmg >= 2.0),
                            )
                            if sub is not None:
                                roll = sub
                    # Adepta Sororitas Acts of Faith — Miracle Dice
                    # substitution on a failed Hit roll. Mirrors the Strands
                    # of Fate branch above: if the attacker is a Sororitas
                    # model and the natural roll missed, pop the lowest
                    # banked die that still hits. The greedy heuristic only
                    # spends when the substitution converts miss -> hit.
                    # Cited as `simulator.acts_of_faith`. Wahapedia:
                    # https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/
                    #
                    # SOROR-ACTS-OF-FAITH-V1: squad-level gate. The codex
                    # rule is "each unit can perform one Act of Faith per
                    # phase." In the simulator each model in a squad is a
                    # separate Unit instance; without the squad gate, a
                    # 10-model squad would get 10 independent AoF spends per
                    # round. `own_army.aof_squad_available(p.name)` enforces
                    # one spend per profile.name per round (= one per codex
                    # unit). Cited as `simulator.acts_of_faith`.
                    if (
                        roll < hit_target
                        and p.faction == "Adepta Sororitas"
                        and not attack_aof_substitution_used
                        and not self.aof_used_this_round  # SOROR-DIAG-4 per-round cap
                    ):
                        own_army = getattr(self, "army_ref", None)
                        if (
                            own_army is not None
                            and own_army.has_miracle_dice()
                            and own_army.aof_squad_available(p.name)  # SOROR-ACTS-OF-FAITH-V1
                        ):
                            sub = own_army.pop_miracle_die_meeting(hit_target)
                            if sub is not None:
                                roll = sub
                                attack_aof_substitution_used = True
                                self.aof_used_this_round = True  # SOROR-DIAG-4
                                own_army.aof_squad_mark_used(p.name)  # SOROR-ACTS-OF-FAITH-V1
                    if roll < hit_target:
                        continue   # missed
                    # Crit-to-hit threshold defaults to 6 (canonical 10e); the
                    # Shield Host Martial Ka'tah Crit-on-5+ branch lowers it to
                    # 5 for Adeptus Custodes melee attackers (see
                    # `melee_crit_threshold` setup above).
                    # CORE-RULE-FIX-2 — Indirect Fire attacks (ranged shot
                    # against a target not visible to the attacker) cannot
                    # score Critical Hits per 10e core, so the nat-6 path is
                    # gated off here. Direct-LoS shots from an Indirect Fire
                    # weapon still crit normally.
                    # CORE-RULE-FIX-5 — gate Crit-Hit on the UNMODIFIED roll.
                    # Strands of Fate / Acts of Faith substituted a banked die
                    # into `roll`; per 10e core, only the original physical die
                    # (or a rerolled replacement) can produce a Critical Hit.
                    if mode == "melee":
                        crit_hit = (unmodified_roll >= melee_crit_threshold)
                    elif indirect_fire_attack:
                        crit_hit = False
                    else:
                        crit_hit = (unmodified_roll == 6)
                n_hits = 1 + (effective_sustained_hits if crit_hit else 0)

                for hit_i in range(n_hits):
                    if effective_lethal_hits and crit_hit and hit_i == 0:
                        wound_succeeded = True
                        crit_wound = False
                    else:
                        wroll = random.randint(1, 6)
                        # CORE-RULE-FIX-5 — track the unmodified wound roll
                        # separately so Crit-Wound gating only fires on the
                        # original physical die (or a rerolled replacement).
                        # 10e core: "An unmodified Wound roll of 6 is always
                        # considered to be a successful Wound roll ... This is
                        # known as a Critical Wound." Acts of Faith / Strands
                        # of Fate substitutions overwrite `wroll` but must NOT
                        # update unmodified_wroll — a substituted 6 cannot crit.
                        unmodified_wroll = wroll
                        rerolled = False
                        # Re-roll handling for wounds. Two compatible flags:
                        #   att_reroll_all_wounds: replace ANY failure (Marines
                        #     Oath of Moment; superset of reroll_wound_ones).
                        #   att_reroll_wound_ones: replace a natural 1 only
                        #     (Gladius / detachment / Votann tier-3).
                        # Only one re-roll per die — `att_reroll_all_wounds`
                        # takes priority and a fired re-roll under it does not
                        # stack another re-roll under reroll_wound_ones or
                        # Twin-Linked.
                        if att_reroll_all_wounds and wroll < _shot_wound_target:
                            wroll = random.randint(1, 6)
                            unmodified_wroll = wroll
                            rerolled = True
                        elif att_reroll_wound_ones and wroll == 1:
                            wroll = random.randint(1, 6)
                            unmodified_wroll = wroll
                            rerolled = True
                        wound_succeeded = (wroll >= _shot_wound_target)
                        if not wound_succeeded and p.twin_linked and not rerolled:
                            wroll = random.randint(1, 6)
                            unmodified_wroll = wroll
                            wound_succeeded = (wroll >= _shot_wound_target)
                            rerolled = True
                        # Universal Core Stratagem — Command Re-Roll (1 CP):
                        # if the wound roll is still a miss AND no re-roll has
                        # already been used on this die AND our army's battle
                        # reference has a stratagem hook AND the heuristic
                        # green-lights the spend, re-roll once more.
                        if (
                            not wound_succeeded and not rerolled
                            and self.army_ref is not None
                            and getattr(self.army_ref, "_battle_ref", None) is not None
                        ):
                            battle = self.army_ref._battle_ref
                            if battle.maybe_fire_command_reroll(self, target, "wound"):
                                wroll = random.randint(1, 6)
                                unmodified_wroll = wroll
                                wound_succeeded = (wroll >= _shot_wound_target)
                                rerolled = True
                        # Anti-X (10e core): "Each time an attack is made with such
                        # a weapon against a target that has the keyword after the
                        # word 'Anti-', an unmodified Wound roll of 'x+' scores a
                        # Critical Wound." A Critical Wound is by definition a
                        # successful Wound roll (10e core: "An unmodified Wound
                        # roll of 6 is always considered to be a successful Wound
                        # roll, irrespective of the attack's Strength and the
                        # target's Toughness characteristic. This is known as a
                        # Critical Wound."). So a roll of >= anti_crit_threshold
                        # auto-succeeds AND is a Critical Wound — even if the
                        # roll would otherwise fail the normal S-vs-T target.
                        # Cited as `weapon.anti_x`. Anti-X wording explicitly
                        # references an "unmodified Wound roll of x+", so the
                        # gate uses unmodified_wroll (CORE-RULE-FIX-5).
                        # Wahapedia: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#ANTI-X
                        if unmodified_wroll >= anti_crit_threshold:
                            wound_succeeded = True
                            crit_wound = True
                        else:
                            crit_wound = False
                    # Adepta Sororitas Acts of Faith — Miracle Dice
                    # substitution on a failed Wound roll. Same greedy
                    # heuristic as the hit-roll branch: only spend a banked
                    # die if it converts fail -> success. Cited as
                    # `simulator.acts_of_faith`. CORE-RULE-FIX-5: the
                    # substituted die is a replacement, NOT an unmodified
                    # roll, so it can succeed the wound but cannot crit.
                    # SOROR-ACTS-OF-FAITH-V1: squad-level gate — see hit
                    # branch above for rationale.
                    if (
                        not wound_succeeded
                        and p.faction == "Adepta Sororitas"
                        and not attack_aof_substitution_used
                        and not self.aof_used_this_round  # SOROR-DIAG-4 per-round cap
                    ):
                        own_army = getattr(self, "army_ref", None)
                        if (
                            own_army is not None
                            and own_army.has_miracle_dice()
                            and own_army.aof_squad_available(p.name)  # SOROR-ACTS-OF-FAITH-V1
                        ):
                            sub = own_army.pop_miracle_die_meeting(_shot_wound_target)
                            if sub is not None:
                                wroll = sub
                                wound_succeeded = True
                                crit_wound = False
                                attack_aof_substitution_used = True
                                self.aof_used_this_round = True  # SOROR-DIAG-4
                                own_army.aof_squad_mark_used(p.name)  # SOROR-ACTS-OF-FAITH-V1
                    if not wound_succeeded:
                        continue

                    tgt_fnp_buff = int(tgt_buffs["fnp"])
                    # MAP-3-FIX — Devastating Wounds basket-fraction gate. The
                    # MAP-3 UNION lets a single specialist weapon (Rubric Marines'
                    # Soulreaper Cannon, AdMech Skitarii Plasma Calivers) tag the
                    # whole squad with DW. Without gating, every crit-wound shot
                    # in the synthetic basket would skip the save. The Bernoulli
                    # draw against `devastating_wounds_basket_fraction` fires the
                    # bypass on the proportion of shots whose underlying weapon
                    # legitimately carries DW. Single-weapon units have
                    # fraction = 1.0 (legacy behaviour preserved).
                    # Cited as `simulator.basket_fraction_gating`.
                    #
                    # DAEMONS-DIAG-7: Skulltaker "Lord of Decapitations" leader
                    # aura grants [DEVASTATING WOUNDS] to the led unit's melee
                    # weapons (mode == "melee" gate enforced here). Composed into
                    # `effective_dw` so the save-bypass path below is shared.
                    # Fraction gate still applies for DW from the weapon profile;
                    # leader-granted DW fires unconditionally on every melee
                    # critical wound (the leader-granted flag treats all shots as
                    # fully covered — fraction = 1.0). Cited as
                    # `LeaderAbility.Lord of Decapitations`.
                    _leader_dw_melee = (
                        mode == "melee"
                        and bool(att_buffs.get("grants_devastating_wounds_melee", False))
                    )
                    effective_dw = p.devastating_wounds or _leader_dw_melee
                    _dw_fraction = (
                        1.0 if _leader_dw_melee and not p.devastating_wounds
                        else float(
                            getattr(p, "devastating_wounds_basket_fraction", 1.0) or 1.0
                        )
                    )
                    if (
                        effective_dw
                        and crit_wound
                        and random.random() < _dw_fraction
                    ):
                        # NECRONS-CTAN: Necrodermis halves Damage characteristic
                        # (rounding up); D1 attacks deal 0. Wahapedia C'tan
                        # datasheet ability. Cited as `UnitProfile.necrodermis`.
                        _dw_dmg = per_shot_dmg
                        if target.profile.necrodermis:
                            if _dw_dmg <= 1.0:
                                _dw_dmg = 0.0
                            else:
                                _dw_dmg = math.ceil(_dw_dmg / 2.0)
                            _dw_dmg = max(0.0, _dw_dmg)
                        target.receive_damage(_dw_dmg, bonus_fnp=tgt_fnp_buff)
                        total_damage += _dw_dmg
                        continue

                    if save_target <= 6:
                        sroll = random.randint(1, 6)
                        # Strands of Fate (Aeldari army rule, 10e) — defensive
                        # substitution on a failed save. If the DEFENDER is an
                        # AELDARI model from an army with at least one Fate
                        # die in pool, and the natural save fails, pop the
                        # lowest die that still passes the save and use it.
                        # Cited as `simulator.strands_of_fate`. Wahapedia:
                        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
                        if (
                            sroll < save_target
                            and target.profile.faction == "Aeldari"
                        ):
                            tgt_army = getattr(target, "army_ref", None)
                            if tgt_army is not None and tgt_army.has_fate_dice():
                                # AI-5: defensive saves are high-stakes when
                                # the incoming attack does >=2 damage (a save
                                # against a melta or lascannon is worth a
                                # Fate die; a save against a 1-damage bolter
                                # shot is not — the model might shrug the
                                # other shots and the bank should be saved
                                # for the next big swing).
                                sub = tgt_army.pop_fate_die_meeting(
                                    save_target,
                                    high_value=(per_shot_dmg >= 2.0),
                                )
                                if sub is not None:
                                    sroll = sub
                        # Adepta Sororitas Acts of Faith — defensive Miracle
                        # Dice substitution on a failed save. Same greedy
                        # heuristic — only spend if it flips fail -> save.
                        # Cited as `simulator.acts_of_faith`. SOROR-DIAG-2:
                        # gated by the per-attack-call AoF-used flag too — the
                        # real rule caps the *defender* at one substitution per
                        # phase, but the simulator's attack() runs per
                        # attacker so this is an UNDER-approximation (a
                        # Sororitas defender can still use one AoF save sub
                        # per attacker attacking it). That's consistent with
                        # the SOROR-DIAG-2 over-buff fix erring conservative.
                        #
                        # SOROR-DIAG-4: the per-attack-call flag did NOT cap
                        # cross-attacker spending. We now ALSO consult / set
                        # `target.aof_used_this_round` so a Sororitas defender
                        # spends at most one Miracle die across all attackers
                        # attacking it in a single round — across offensive
                        # AND defensive directions combined.
                        #
                        # SOROR-ACTS-OF-FAITH-V1: squad-level gate for the
                        # defensive path. Same rationale as offensive hit/wound
                        # branches — all sim instances of the same profile.name
                        # (e.g. all "Battle Sisters Squad" models) count as ONE
                        # codex unit for AoF purposes. Cited as
                        # `simulator.acts_of_faith`.
                        if (
                            sroll < save_target
                            and target.profile.faction == "Adepta Sororitas"
                            and not attack_aof_substitution_used
                            and not target.aof_used_this_round  # SOROR-DIAG-4
                        ):
                            tgt_army = getattr(target, "army_ref", None)
                            if (
                                tgt_army is not None
                                and tgt_army.has_miracle_dice()
                                and tgt_army.aof_squad_available(target.profile.name)  # SOROR-ACTS-OF-FAITH-V1
                            ):
                                sub = tgt_army.pop_miracle_die_meeting(save_target)
                                if sub is not None:
                                    sroll = sub
                                    attack_aof_substitution_used = True
                                    target.aof_used_this_round = True  # SOROR-DIAG-4
                                    tgt_army.aof_squad_mark_used(target.profile.name)  # SOROR-ACTS-OF-FAITH-V1
                        if sroll >= save_target:
                            continue   # saved
                    # NECRONS-CTAN: Necrodermis halves Damage characteristic
                    # (rounding up); D1 attacks deal 0. Wahapedia C'tan
                    # datasheet ability. Cited as `UnitProfile.necrodermis`.
                    _alloc_dmg = per_shot_dmg
                    if target.profile.necrodermis:
                        if _alloc_dmg <= 1.0:
                            _alloc_dmg = 0.0
                        else:
                            _alloc_dmg = math.ceil(_alloc_dmg / 2.0)
                        _alloc_dmg = max(0.0, _alloc_dmg)
                    target.receive_damage(_alloc_dmg, bonus_fnp=tgt_fnp_buff)
                    total_damage += _alloc_dmg

        # ---- Hazardous: d6 after firing; on a 1, take 3 mortal wounds ----
        if p.hazardous:
            if random.randint(1, 6) == 1:
                self.receive_damage(3.0)

        return total_damage

    def __repr__(self) -> str:
        return f"{self.profile.name}({self.current_health:.1f}/{self.profile.health}hp)"


# ---------------------------------------------------------------------------
# Unit catalogue
# ---------------------------------------------------------------------------
#
# Stats follow the SwegHammer abstraction (not 1:1 with any edition):
#   hit_probability: 1/2 = 4+, 2/3 = 3+, 5/6 = 2+ (on a d6)
#   ap:    0 = no AP,  -1 = AP1,  -2 = AP2,  -3 = AP3
#   save:  3 = 3+, 4 = 4+, 5 = 5+, 6 = 6+, 7 = no save
#   S / T: roughly aligned with 10th-edition datasheets, rounded for sanity
#
# UNIT_CATALOG is built at import time by merging:
#   data/bsdata/parsed.json — base stats from BSData WH40k 10th edition
#   data/overrides.json     — per-unit hand tuning
#
# To refresh the BSData base, run:
#     python -m code.bsdata.fetch --tag <release>
#     python -m code.bsdata.mapper
#
def _build_catalog(use_calibrated: bool = False) -> Dict[str, UnitProfile]:
    from .bsdata.loader import load_catalog
    from .factions import faction_of

    catalog: Dict[str, UnitProfile] = {}
    for key, entry in load_catalog(use_calibrated=use_calibrated).items():
        # entry.move > 0 means the loader saw a movement value (either set in
        # parsed.json or — more commonly — pinned via overrides.json). Fall
        # back to the UnitProfile default (6.0) when no value is supplied.
        _move = entry.move if entry.move and entry.move > 0 else 6.0
        catalog[key] = UnitProfile(
            name=entry.name,
            move=_move,
            health=entry.health,
            damage=entry.damage,
            hit_probability=entry.hit_probability,
            ap=entry.ap,
            save=entry.save,
            strength=entry.strength,
            toughness=entry.toughness,
            leadership=entry.leadership,
            oc=entry.oc,
            faction=faction_of(entry.codex),
            min_models=entry.min_models,
            max_models=entry.max_models,
            points_per_squad=entry.points_listed,
            attacks=entry.attacks,
            weapon_damage_per_shot=entry.weapon_damage_per_shot,
            lethal_hits=entry.lethal_hits,
            sustained_hits=entry.sustained_hits,
            melee_sustained_hits=entry.melee_sustained_hits,
            twin_linked=entry.twin_linked,
            devastating_wounds=entry.devastating_wounds,
            invuln_save=entry.invuln_save,
            rapid_fire=entry.rapid_fire,
            melta=entry.melta,
            ignores_cover=entry.ignores_cover,
            anti_keywords=tuple((k, v) for k, v in (entry.anti_keywords or {}).items()),
            heavy=entry.heavy,
            assault=entry.assault,
            torrent=entry.torrent,
            hazardous=entry.hazardous,
            blast=entry.blast,
            lance=entry.lance,
            precision=entry.precision,
            pistol=entry.pistol,
            weapon=getattr(entry, "weapon", "") or "",
            secondary_pistol=getattr(entry, "secondary_pistol", False),
            indirect_fire=entry.indirect_fire,
            one_shot=entry.one_shot,
            stealth=entry.stealth,
            lone_operative=entry.lone_operative,
            fights_first=getattr(entry, "fights_first", False),
            deep_strike=entry.deep_strike,
            scout_distance=entry.scout_distance,
            infiltrator=entry.infiltrator,
            fnp=entry.fnp,
            deadly_demise=entry.deadly_demise,
            firing_deck=entry.firing_deck,
            sticky_objective=entry.sticky_objective,
            resolute_will=entry.resolute_will,
            necrodermis=entry.necrodermis,
            reanimates_with_army=entry.reanimates_with_army,
            unit_keywords=tuple(entry.unit_keywords or []),
            melee_attacks=entry.melee_attacks,
            melee_damage_per_shot=entry.melee_damage_per_shot,
            melee_hit_probability=entry.melee_hit_probability,
            melee_strength=entry.melee_strength,
            melee_ap=entry.melee_ap,
            melee_weapon=entry.melee_weapon,
            range_inches=entry.range_inches,
            secondary_attacks=entry.secondary_attacks,
            secondary_weapon_damage_per_shot=entry.secondary_weapon_damage_per_shot,
            secondary_hit_probability=entry.secondary_hit_probability,
            secondary_ap=entry.secondary_ap,
            secondary_strength=entry.secondary_strength,
            secondary_range_inches=entry.secondary_range_inches,
            secondary_weapon=entry.secondary_weapon,
            secondary_anti_keywords=tuple(
                (k, v) for k, v in (entry.secondary_anti_keywords or {}).items()
            ),
            secondary_lethal_hits=entry.secondary_lethal_hits,
            secondary_sustained_hits=entry.secondary_sustained_hits,
            secondary_twin_linked=entry.secondary_twin_linked,
            secondary_devastating_wounds=entry.secondary_devastating_wounds,
            secondary_rapid_fire=entry.secondary_rapid_fire,
            secondary_melta=entry.secondary_melta,
            secondary_ignores_cover=entry.secondary_ignores_cover,
            secondary_heavy=entry.secondary_heavy,
            secondary_assault=entry.secondary_assault,
            secondary_torrent=entry.secondary_torrent,
            secondary_blast=entry.secondary_blast,
            # MAP-1: TERTIARY and beyond ranged profiles (Knight Castellan
            # 5-weapon, etc.). Stored on the CatalogEntry as a list of dicts;
            # flatten into a tuple-of-(key, value) pairs so the UnitProfile
            # dataclass stays HASHABLE (required by functools.lru_cache on
            # roles.expected_ranged_dpa et al). Any nested dict value (like
            # anti_keywords) is itself converted to a tuple of items.
            extra_ranged_profiles=tuple(
                tuple(
                    (k, (tuple(sorted(v.items())) if isinstance(v, dict) else v))
                    for k, v in prof.items()
                )
                for prof in (entry.extra_ranged_profiles or ())
            ),
            # KNIGHTS-MULTIPROFILE-2 — additional melee weapon profiles
            # (Knight Abominant balemace, Knight Rampager Reaper chainsword,
            # etc.). Same flatten-to-tuples trick as extra_ranged_profiles
            # so the UnitProfile dataclass stays HASHABLE for the lru_cache
            # decorators in code/roles.py. Cited as
            # `simulator.extra_melee_profiles`.
            extra_melee_profiles=tuple(
                tuple(
                    (k, (tuple(sorted(v.items())) if isinstance(v, dict) else v))
                    for k, v in prof.items()
                )
                for prof in (entry.extra_melee_profiles or ())
            ),
            # MAP-3-FIX — basket-fraction gating. Default 1.0 preserves legacy
            # single-weapon / non-heterogeneous behaviour; mapper sets < 1.0
            # for heterogeneous squads. Anti-keywords dict flattened to a
            # tuple of (kw, fraction) for hashability (same convention as
            # anti_keywords above).
            devastating_wounds_basket_fraction=entry.devastating_wounds_basket_fraction,
            lance_basket_fraction=entry.lance_basket_fraction,
            anti_keyword_basket_fractions=tuple(
                (k, float(v))
                for k, v in (entry.anti_keyword_basket_fractions or {}).items()
            ),
            points_override=entry.points_override,
            base_shape=entry.base_shape,
            base_diameter_mm=entry.base_diameter_mm,
            base_width_mm=entry.base_width_mm,
            base_length_mm=entry.base_length_mm,
        )
    return catalog


UNIT_CATALOG: Dict[str, UnitProfile] = _build_catalog()
# Same units, but with balancer-derived points overrides layered on (only
# converged calibration entries are applied). Lazily built when first
# requested so importing code.units stays cheap.
_BALANCED_CATALOG: Dict[str, UnitProfile] | None = None


def balanced_catalog() -> Dict[str, UnitProfile]:
    """Return the catalogue with calibrated_points.json applied as overrides."""
    global _BALANCED_CATALOG
    if _BALANCED_CATALOG is None:
        _BALANCED_CATALOG = _build_catalog(use_calibrated=True)
    return _BALANCED_CATALOG


# --- Dead code below: hand-rolled catalogue resurrected by an earlier merge
# conflict resolution. Kept for one beat in case anyone is mid-rebase, but
# the dict is immediately shadowed by `_build_catalog()` above and will be
# removed in a follow-up.
_LEGACY_HAND_ROLLED_CATALOG_SUPERSEDED: Dict[str, UnitProfile] = {
    # --- Space Marines ---
    "scout_marine": UnitProfile(
        name="Scout Marine",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "space_marine": UnitProfile(
        name="Space Marine",
        health=1, damage=1, hit_probability=2/3,
        ap=0, save=3, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "veteran_marine": UnitProfile(
        name="Veteran Marine",
        health=2, damage=1, hit_probability=2/3,
        ap=-1, save=3, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "terminator": UnitProfile(
        name="Terminator",
        health=3, damage=2, hit_probability=2/3,
        ap=-2, save=2, strength=5, toughness=5,
        move=5.0, range_inches=24,
    ),
    "dreadnought": UnitProfile(
        name="Dreadnought",
        health=8, damage=3, hit_probability=2/3,
        ap=-2, save=3, strength=7, toughness=10,
        move=6.0, range_inches=36,
    ),
    "predator_tank": UnitProfile(
        name="Predator Tank",
        health=11, damage=4, hit_probability=2/3,
        ap=-3, save=3, strength=9, toughness=10,
        move=10.0, range_inches=48,
    ),

    # --- Chaos ---
    "cultist": UnitProfile(
        name="Cultist",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=6, strength=3, toughness=3,
        move=6.0, range_inches=18,
    ),
    "chaos_space_marine": UnitProfile(
        name="Chaos Space Marine",
        health=2, damage=1, hit_probability=2/3,
        ap=-1, save=3, strength=4, toughness=4,
        move=6.0, range_inches=24,
    ),
    "chaos_terminator": UnitProfile(
        name="Chaos Terminator",
        health=3, damage=2, hit_probability=2/3,
        ap=-2, save=2, strength=5, toughness=5,
        move=5.0, range_inches=24,
    ),
    "chaos_dreadnought": UnitProfile(
        name="Chaos Dreadnought",
        health=8, damage=3, hit_probability=2/3,
        ap=-2, save=3, strength=7, toughness=10,
        move=6.0, range_inches=36,
    ),

    # --- Orks ---
    "gretchin": UnitProfile(
        name="Gretchin",
        health=1, damage=1, hit_probability=1/3,
        ap=0, save=6, strength=2, toughness=3,
        move=5.0, range_inches=12,
    ),
    "ork_boy": UnitProfile(
        name="Ork Boy",
        health=2, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=5,
        move=6.0, range_inches=12,
    ),
    "ork_nob": UnitProfile(
        name="Ork Nob",
        health=3, damage=2, hit_probability=0.5,
        ap=-1, save=4, strength=5, toughness=5,
        move=6.0, range_inches=12,
    ),
    "mek_gun": UnitProfile(
        name="Mek Gun",
        health=5, damage=3, hit_probability=0.5,
        ap=-2, save=4, strength=6, toughness=6,
        move=4.0, range_inches=36,
    ),

    # --- Tyranids ---
    "termagant": UnitProfile(
        name="Termagant",
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=3,
        move=6.0, range_inches=18,
    ),
    "hormagaunt": UnitProfile(
        name="Hormagaunt",
        health=1, damage=2, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=3,
        move=8.0, range_inches=1,
    ),
    "warrior": UnitProfile(
        name="Warrior",
        health=3, damage=2, hit_probability=2/3,
        ap=-1, save=4, strength=5, toughness=5,
        move=6.0, range_inches=24,
    ),
    "carnifex": UnitProfile(
        name="Carnifex",
        health=10, damage=4, hit_probability=2/3,
        ap=-3, save=3, strength=9, toughness=9,
        move=8.0, range_inches=18,
    ),
}
del _LEGACY_HAND_ROLLED_CATALOG_SUPERSEDED   # keep the symbol out of the namespace
