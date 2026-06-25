"""Unit profiles and battle-instance unit class."""

from __future__ import annotations

import functools
import math
import os
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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


# ---------------------------------------------------------------------------
# PER-MODEL-LOADOUTS (Stage 4) — per-weapon damage-dice rolling
# ---------------------------------------------------------------------------
#
# 10e core rule (Making Attacks → Inflict Damage): a weapon with a random
# Damage characteristic (D6, D3+3, 2D6, ...) rolls those dice when a save is
# failed to determine how many points of Damage the attack inflicts. SwegHammer
# historically used the expected-value MEAN of that characteristic (a D6 gun
# always dealt 3.5). That over-rates big single-shot guns: a real D6 against a
# 3-wound model kills it ~67% of the time, but at 3.5 it "reliably" kills it.
# Stage 4 rolls the real dice per shot, gated by `SWEG_ROLLDMG`, so the variance
# (and the over-/under-kill correction) is measurable in isolation from the
# Stage-3 per-model structural change.
#
# Cited as `simulator.rolled_damage`.

# Dice grammar — ported verbatim from code/bsdata/mapper.py::parse_dice_expr so
# the rolled distribution's MEAN matches the legacy expected-value field exactly
# (the mean-invariant the Stage-1 mapper tests assert). Matches "NdX" / "dX"
# (count optional → 1) anywhere in the string; the flat-modifier walk below adds
# any trailing/leading integers.
_DICE_RE = re.compile(r"(\d*)[dD](\d+)")
_INT_RE = re.compile(r"-?\d+")


def _rolldmg_enabled() -> bool:
    """True unless the `SWEG_ROLLDMG` env gate is explicitly "0" (kill-switch).
    Default ON since wave 247 (adopted per fidelity-first: real 10e rolls each
    weapon's Damage characteristic; the expected-value path was the sim's
    approximation). Read per-call (not cached at import) so tests can toggle it
    via os.environ within a process. When killed (=0), `roll_damage` draws
    NOTHING and returns the mean — keeping the OFF and per-model-mean RNG
    streams byte-identical to the legacy expected-value frame."""
    return os.environ.get("SWEG_ROLLDMG", "1") != "0"


def _tau_battlesuit_weapons_enabled() -> bool:
    """True when SWEG_TAU_BATTLESUIT_WEAPONS != '0' (adopted default-on, wave 256).
    Restores the BSData-dropped simultaneously-equipped battlesuit weapons:
    the Crisis Fireknife missile pod (a 2nd additive ranged profile alongside
    the plasma rifle) and the Crisis Sunforge second fusion blaster (modelled as
    attacks=2 on the single mapped fusion-blaster profile, because a duplicate
    'fusion blaster' extra_ranged_profile collapses into one mutex group under
    _strip_mode_suffix). Read per-build (not cached) so tests can toggle it via
    os.environ within a process; when set to 0, _build_catalog skips the injection
    block entirely and the two units are byte-identical to the legacy catalogue.
    See data/rule_citations.d/tau_empire.json keys simulator.tau_crisis_fireknife_missile_pod
    and simulator.tau_crisis_sunforge_second_fusion_blaster."""
    return os.environ.get("SWEG_TAU_BATTLESUIT_WEAPONS", "1") != "0"


def roll_damage(dice_str: str, mean_fallback: float) -> float:
    """Roll a weapon's real Damage characteristic for ONE shot.

    `dice_str` is the raw BSData Damage string ("2", "D6", "D3+3", "2D6", ...).
    Returns the summed roll: each `NdX` term contributes N independent d6/dX
    draws, each flat integer term is added verbatim. Uses the GLOBAL `random`
    (seeded per worker in scripts/evaluate_vs_meta.py), so the sequence is
    deterministic under PYTHONHASHSEED=0.

    DETERMINISM CONTRACT: when `dice_str == ""` (or the `SWEG_ROLLDMG` gate is
    unset), the function draws NOTHING from `random` and returns `mean_fallback`
    unchanged. This is what keeps the gate-OFF and per-model-mean streams
    byte-for-byte identical to the legacy expected-value path — the only time a
    `random` draw is consumed here is when both the gate is on AND a non-empty
    dice string is supplied.
    """
    if not dice_str or not _rolldmg_enabled():
        return mean_fallback
    s = dice_str.strip()
    if not s or s in {"-", "—", "N/A", "None"}:
        return mean_fallback
    total = 0.0
    rolled_any = False
    for count_str, sides_str in _DICE_RE.findall(s):
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        for _ in range(max(0, count)):
            total += random.randint(1, sides)
            rolled_any = True
    stripped = _DICE_RE.sub("", s)
    for n in _INT_RE.findall(stripped):
        total += int(n)
    # A pure-integer characteristic ("2") has no dice term but is a valid roll
    # result; only fall back to the mean when the grammar matched NOTHING at all
    # (unparseable string), so a flat "2" returns exactly 2 (and still draws no
    # random die — the determinism contract holds for constant-damage weapons).
    if not rolled_any and total == 0.0:
        return mean_fallback
    return total


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


# DURABILITY instrument (#85, gated SWEG_DURABILITY_INSTR) — per target-keyword
# class (VEHICLE / INFANTRY / other), the realized base-vs-effective save and the
# cover-applied rate during real shooting. Read-only; a diag resets and reads it.
DURABILITY_STATS: dict = {}

# MELEE/RANGED output split (#86, gated SWEG_MODE_INSTR) — per attacker-faction
# damage dealt by mode. Read-only; a diag resets and reads it.
MODE_STATS: dict = {}


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
    # PER-MODEL-LOADOUTS (Stage 4) — raw BSData Damage characteristic string for
    # the PRIMARY ranged weapon (e.g. "D6", "D3+3", "2"). When the `SWEG_ROLLDMG`
    # env gate is set AND this is non-empty, Unit.attack rolls these dice fresh
    # per shot instead of using `weapon_damage_per_shot` (the expected-value
    # mean). Empty string ("") = roll nothing, use the mean — so every legacy /
    # aggregate profile (which never sets this) is byte-for-byte unchanged.
    # Populated only on per-model profiles (via _loadout_entry_to_weapon_fields
    # and the extra-profile swap), so dice rolling only happens on the per-model
    # firing path. Cited as `simulator.rolled_damage`.
    damage_dice: str = ""
    # Weapon abilities (parsed from BSData Keywords field by the mapper)
    lethal_hits: bool = False                  # critical hit (6 to hit) auto-wounds
    sustained_hits: int = 0                    # critical hit generates N extra normal hits (RANGED weapon)
    # Melee-side SUSTAINED HITS — populated by the mapper from the chosen
    # melee weapon's keywords. Read by Unit.attack when `mode == "melee"` so
    # a ranged-only SUSTAINED HITS N does not leak into melee resolution.
    melee_sustained_hits: int = 0
    # Melee-side [LETHAL HITS] — parallel split to melee_sustained_hits.
    # Wave-51 DAEMONS-GREATER-COMBAT-V1 surfaced this schema gap: Great
    # Unclean One's Bilesword carries [LETHAL HITS] in BSData but the field
    # `lethal_hits` was previously read from the RANGED primary weapon only.
    # Mode-routed in Unit.attack so a ranged-only LETHAL HITS doesn't leak
    # into melee resolution and vice versa.
    melee_lethal_hits: bool = False
    # Melee-side ANTI-X / DEVASTATING WOUNDS / TWIN-LINKED — the same split
    # as melee_lethal_hits / melee_sustained_hits, populated by the mapper
    # from the chosen MELEE weapon's keywords. Without these three fields the
    # simulator read the ranged-primary `anti_keywords` / `devastating_wounds`
    # / `twin_linked` in the Fight phase too, contaminating melee resolution
    # on every unit whose ranged weapon carried one of these (e.g. a Wave
    # Serpent's Twin Bright Lance leaking TWIN-LINKED into its melee, Howling
    # Banshees' ranged ANTI-INFANTRY appearing on the powerblade). Mode-routed
    # at the three Unit.attack resolution sites (`mode == "melee"`). The two
    # melee basket fractions mirror the ranged
    # `devastating_wounds_basket_fraction` / `anti_keyword_basket_fractions`
    # so heterogeneous squads Bernoulli-gate the melee keyword per shot.
    # Cited as `simulator.basket_fraction_gating` (the fraction gating) and
    # the per-keyword citations these melee fields re-route already carry.
    melee_anti_keywords: Tuple[Tuple[str, int], ...] = ()
    melee_devastating_wounds: bool = False
    melee_twin_linked: bool = False
    melee_devastating_wounds_basket_fraction: float = 1.0
    melee_anti_keyword_basket_fractions: Tuple[Tuple[str, float], ...] = ()
    twin_linked: bool = False                  # re-roll failed wound rolls
    devastating_wounds: bool = False           # critical wound (6 to wound) bypasses saves
    invuln_save: int = 7                       # invulnerable save (7 = none); use better of save-after-AP or invuln
    invuln_ranged_only: bool = False           # 10e Imperial Knight Ion Shield: invuln applies vs ranged attacks only (no invuln in melee)
    # Task #92 — per-attack-type invulnerable save (Stage 1, gate-inert: populated
    # but NOT YET read by the save step). Generalises the single `invuln_save` +
    # `invuln_ranged_only` bool into two values so 10e CONDITIONAL invulns model
    # faithfully — e.g. Wyches "6+ Invulnerable save, 4+ against melee attacks"
    # (ranged 6, melee 4); Imperial Knight Ion Shield (ranged 5, melee none=7).
    # Default 7 (none); the builder derives them from the existing fields so the
    # common case has both == invuln_save. Stage 2 switches the save step to read
    # these; Stage 1b adds the multi-VALUE mapper parse (Wyches melee 4).
    invuln_save_melee: int = 7                 # invuln vs melee attacks (7 = none)
    invuln_save_ranged: int = 7                # invuln vs ranged attacks (7 = none)
    # CSM Legionaries datasheet ability "Veterans of the Long War" (10e): in melee,
    # re-roll Wound rolls of 1; if the target is within range of an objective marker,
    # re-roll the full Wound roll instead. Override-only flag; read at the melee
    # wound step gated SWEG_VETERANS. Cited simulator.veterans_of_the_long_war.
    veterans_of_the_long_war: bool = False
    # CSM Chaos Terminator Squad datasheet ability "Despoilers" (10e): when this
    # unit makes a Dark Pact, until the end of the phase, each model may re-roll
    # the Hit roll. Override-only flag; applied in simulator._apply_dark_pacts
    # as a transient_reroll_all_hits grant, gated SWEG_CSM_ABILITIES.
    # Cited simulator.csm_despoilers.
    csm_despoilers: bool = False
    # CSM Possessed datasheet ability "Unholy Bloodshed" (10e): once per battle,
    # when this unit makes a Dark Pact, until the end of the phase, weapons
    # equipped by models in this unit have the [DEVASTATING WOUNDS] ability.
    # Override-only flag; applied in simulator._apply_dark_pacts as a
    # transient_devastating_wounds grant (once-per-battle guarded), gated
    # SWEG_CSM_ABILITIES. Cited simulator.csm_unholy_bloodshed.
    csm_unholy_bloodshed: bool = False
    # Adepta Sororitas Retributor Squad datasheet ability "Storm of Retribution"
    # (unconditional half, override-only). BSData v10.6.0 id 8eef-f65c-7895-183f:
    # "Each time a model in this unit makes a ranged attack, re-roll a Hit roll of 1
    # and re-roll a Wound roll of 1." Applied in Unit.attack when mode != "melee" by
    # setting att_reroll_hit_ones=True and att_reroll_wound_ones=True. Ranged-only;
    # the melee guard ensures it never fires in the Fight phase. Set via
    # overrides.json on adepta_sororitas_retributor_squad. The escalating half
    # (+1 to Hit/Wound vs an enemy that killed a friendly Adepta Sororitas unit)
    # is a follow-up code build. Cited as `simulator.storm_of_retribution`.
    storm_of_retribution: bool = False
    # Leagues of Votann native re-roll-a-Hit-roll-of-1 on ranged attacks
    # (override-only, per-datasheet). Panspectral Scanning (Hearthkyn),
    # Panspectral Scanner (Hekaton), Decisive Destruction (Einhyr — the
    # codex restricts that one to the closest eligible target; see the
    # read-site comment for the documented approximation). Read in
    # Unit.attack when mode != 'melee' behind SWEG_VOTANN_NATIVE_REROLL.
    # Cited as `simulator.votann_native_reroll_ranged`.
    votann_native_reroll_ranged: bool = False
    # CSM Forgefiend datasheet ability "Daemonic Ordnance" (10e): each time
    # this model is selected to shoot, it can use this ability. If it does,
    # until the end of the phase, its ranged weapons have the [DEVASTATING
    # WOUNDS] and [HAZARDOUS] abilities. Override-only flag; applied in
    # simulator._apply_daemonic_ordnance as transient_devastating_wounds +
    # transient_hazardous grants. Opt-in per activation: elected when the
    # expected [DEVASTATING WOUNDS] uplift on the chosen target exceeds the
    # expected [HAZARDOUS] self-damage cost. Cited simulator.csm_daemonic_ordnance.
    csm_daemonic_ordnance: bool = False
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
    # CHAOS DAEMONS — Murderer's Cowl (Khorne army rule, 10e). BSData verbatim:
    # "This unit is eligible to shoot and declare a charge in a turn in which it
    # Advanced." Grants advance-and-charge eligibility. Wired in simulator._do_charge
    # as an exemption from the _advanced_this_round lockout (parallel to Gladius
    # Assault Doctrine). The shoot-after-Advance half is covered separately by
    # profile.assault. Set per-unit via overrides.json.
    # Cited as `simulator.murderers_cowl`.
    murderers_cowl: bool = False
    # CHAOS DAEMONS — Gloam Rot (Nurgle army rule, 10e). BSData verbatim:
    # "Each time an attack targets this unit, if the Strength characteristic of that
    # attack is greater than this unit's Toughness characteristic, subtract 1 from
    # the Wound roll." Wired in Unit.attack as a defender-side wound_mod_delta -1
    # gated by: (a) defender carries this flag, (b) attacker Strength > defender
    # Toughness. No leader-attachment gate (the rule is unconditional). Set per-unit
    # via overrides.json. Cited as `simulator.gloam_rot`.
    gloam_rot: bool = False
    # NECRONS-CTAN — Necrodermis (C'tan datasheet ability). Each time an
    # attack is allocated to this model, halve the Damage characteristic
    # (rounding up); D1 attacks deal 0 damage. Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/necrons/. Applied at the
    # per-shot damage allocation sites in Unit.attack (both the
    # devastating-wounds bypass path and the failed-save path). Cited as
    # `UnitProfile.necrodermis`.
    necrodermis: bool = False
    # ADEPTA SORORITAS — Righteous Paragons (Paragon Warsuits datasheet
    # ability, 10e). Wahapedia verbatim: "Each time a model in this unit
    # makes an attack that targets a MONSTER or VEHICLE unit, add 1 to
    # the Hit roll and add 1 to the Wound roll." Attacker-side +1 to Hit
    # and +1 to Wound gated on: (a) attacker carries this flag (set on
    # the Paragon Warsuits UnitProfile via overrides.json), (b) the
    # target has the MONSTER or VEHICLE keyword in its unit_keywords.
    # The bonus applies to all attacks (both ranged and melee) this unit
    # makes against qualifying targets. Cited as
    # `simulator.righteous_paragons`.
    righteous_paragons: bool = False
    # T'AU EMPIRE — Sunforge (Crisis Sunforge Battlesuits datasheet ability,
    # 10e). Wahapedia verbatim: "Each time a model in this unit makes a ranged
    # attack that targets a MONSTER or VEHICLE unit, you can re-roll the Wound
    # roll and you can re-roll the Damage roll." Ranged-only, target-keyword-
    # gated. Wound re-roll reuses att_reroll_all_wounds; damage re-roll is a
    # per-shot Damage-dice re-roll. Set on the Crisis Sunforge Battlesuits
    # UnitProfile via overrides.json. Gated SWEG_TAU_SUNFORGE_HAMMERHEAD_ABILITIES
    # (adopted default-on, wave 256; set to 0 to disable). Cited as `simulator.tau_sunforge`.
    tau_sunforge: bool = False
    # T'AU EMPIRE — Armour Hunter (Hammerhead Gunship datasheet ability, 10e).
    # Wahapedia verbatim: "Each time this model makes an attack that targets a
    # MONSTER or VEHICLE, add 1 to the Hit roll." Mirrors righteous_paragons'
    # hit-half but +1-to-Hit ONLY (no wound bonus) and applies to both ranged
    # and melee. Set on the Hammerhead Gunship UnitProfile via overrides.json.
    # Gated SWEG_TAU_SUNFORGE_HAMMERHEAD_ABILITIES (adopted default-on, wave 256;
    # set to 0 to disable). Cited as `simulator.tau_armour_hunter`.
    tau_armour_hunter: bool = False
    # T'AU EMPIRE — Targeting Array (Hammerhead Gunship datasheet ability, 10e).
    # Wahapedia verbatim: "Each time this model is selected to shoot, you can
    # re-roll one Hit roll or you can re-roll one Wound roll when resolving
    # those attacks." One re-roll of a single Hit OR Wound die per shooting
    # activation — modelled by reusing the existing single-slot Code-Chivalric
    # re-roll machinery (one Wound-die re-roll per activation). Set on the
    # Hammerhead Gunship UnitProfile via overrides.json. Gated
    # SWEG_TAU_SUNFORGE_HAMMERHEAD_ABILITIES (adopted default-on, wave 256;
    # set to 0 to disable). Cited as `simulator.tau_targeting_array`.
    tau_targeting_array: bool = False
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
    # PER-MODEL-LOADOUTS (Stage 4) — raw BSData Damage characteristic string for
    # the PRIMARY melee weapon (e.g. "D3", "2"). Parallel to `damage_dice` for
    # the ranged side: under the `SWEG_ROLLDMG` gate Unit.attack rolls these dice
    # per melee attack instead of using `melee_damage_per_shot`. Empty = use the
    # mean (legacy / aggregate profiles never set it). Cited as
    # `simulator.rolled_damage`.
    melee_damage_dice: str = ""
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
    # SEC-KEYWORD-PARITY — four boolean weapon keywords missing from the
    # secondary profile block. Without these, dataclasses.replace inherits the
    # PRIMARY profile's value when the simulator hot-swaps the secondary in,
    # so a unit whose secondary has one_shot=True but whose primary does not
    # would fire the secondary weapon every activation (never gated once per
    # battle), and a unit whose secondary is hazardous but primary is not would
    # never self-harm. Defaults False (safe legacy behaviour pre-regen).
    secondary_one_shot: bool = False
    secondary_hazardous: bool = False
    secondary_indirect_fire: bool = False
    secondary_precision: bool = False
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
    # ---- PER-MODEL-LOADOUTS (Stage 2 plumbing — GATE-INERT) -----------------
    # The unit's actual per-model-type weapon loadout, carried verbatim from
    # the BSData mapper (CatalogEntry.model_loadouts). Where the aggregate
    # primary / secondary / extra_* blocks above collapse the whole squad into
    # one synthetic averaged weapon, THIS preserves who-carries-what: one entry
    # per distinct model type, each with that model's real equipped ranged /
    # melee weapons (including the raw `attacks_dice` / `damage_dice` strings).
    # A later stage will fire each model's real loadout from this field; in
    # Stage 2 NOTHING reads it for behaviour — it is purely carried so the
    # simulator's output is byte-for-byte unchanged.
    #
    # Stored as a RECURSIVELY (key, value)-flattened tuple so the frozen
    # dataclass stays HASHABLE (required by functools.lru_cache on the role /
    # damage helpers that key on UnitProfile). The nested shape mirrors the
    # extra_ranged_profiles flatten trick, one level deeper:
    #   model_loadouts  = ( per_model_tuple, ... )
    #   per_model_tuple = sorted (key, value) pairs of {name, count, ranged,
    #                     melee}, where the `ranged` / `melee` values are each a
    #                     tuple of flattened-weapon-dict tuples, and each
    #                     weapon-dict tuple is sorted (key, value) pairs with any
    #                     dict-valued field (anti_keywords) itself a tuple of
    #                     sorted items.
    # `_flatten_model_loadouts` builds this; `_unflatten_model_loadouts`
    # reverses it exactly (round-trips to the original list-of-dicts).
    # Empty tuple = no per-model loadout recorded (legacy entries).
    model_loadouts: Tuple[Tuple[Tuple[str, Any], ...], ...] = ()
    # DAMAGED-BRACKET (task #77) — the 10e "Damaged: 1-X Wounds Remaining"
    # datasheet bracket, extracted per-unit from BSData. `damaged_threshold == 0`
    # means the model has no bracket. While the model is at 1..threshold wounds,
    # the simulator (Stage 3, gated SWEG_DMGBRACKET) subtracts the penalties from
    # the model's Objective Control / Hit roll. Flat ints → trivially hashable for
    # the frozen dataclass + lru_cache. Cited `simulator.damaged_bracket`.
    damaged_threshold: int = 0
    damaged_oc_penalty: int = 0
    damaged_hit_penalty: int = 0
    damaged_attacks_penalty: int = 0
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
    def titanic(self) -> bool:
        """True if this unit has the TITANIC keyword (10e). Derived from
        ``unit_keywords``. TITANIC units are exempt from the Desperate
        Escape test when Falling Back, per core rules. Cited as
        ``simulator.desperate_escape``.
        """
        return "TITANIC" in (self.unit_keywords or ())

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
        "army_ref",
        # SQUAD-ACTIVATION (Lever 1, P1): stable per-squad id assigned at army-
        # build time. All model-Units of one instantiated codex squad share an
        # id (distinct even for two squads of the same datasheet). -1 = unassigned
        # / lone model. Consumed by the squad-level activation loop (P3) and the
        # squad-keyed dedup gates (P4). No behaviour change in P1.
        "squad_id",
        # PER-MODEL-LOADOUTS (Stage 3): the original aggregate squad UnitProfile
        # this model-Unit was expanded from, when SWEG_PERMODEL split the squad
        # into one Unit per model with its own narrowed weapon block. Unit-level
        # consumers that need the squad-wide view (AI scoring in a later stage)
        # read this; the firing path reads the per-model `profile`. None for
        # legacy / shared-profile units. Cited as `simulator.per_model_loadouts`.
        "squad_profile_ref",
        "moved_this_round", "on_objective", "shooting_in_engagement",
        # Pariah Nexus action state (wave 74). Set to an action name (e.g.
        # "cleanse") by Battle._assign_cleanse_actions when the unit performs a
        # 10e action this round; while set, _do_shoot and _do_charge refuse to
        # fire the unit (a unit performing an action cannot shoot or charge).
        # Cleared at the top of each round. Cited as `simulator.secondary_cleanse`.
        "action_this_round",
        # AI-pursuit target (wave 121, AI movement heuristic only — no 10e rule
        # citation required). Set per-turn by Battle._assign_card_pursuit when a
        # TACTICAL army holds a Behind Enemy Lines or Cleanse card and this unit
        # is a spare chaff body that can be sent to pursue it. While set,
        # pick_move_intent returns this position as a high-priority override so
        # the unit moves toward the card's geographic goal this activation.
        # Reset to None at the start of each army's turn in
        # _run_round_vanilla_turns (never persists across turns or rounds).
        # AI scheduler only — not gated by a rule citation.
        "pursue_target",
        # Secondary deliberate-dedication target (Stage A, env-gated
        # SWEG_SECONDARY). The card key (e.g. 'engage_on_all_fronts',
        # 'behind_enemy_lines') this unit was DELIBERATELY committed to this
        # turn by Battle._assign_card_dedication. Only units whose
        # dedicated_card matches a position card contribute to that card's
        # score, so incidental presence no longer scores — a low-unit army
        # with no spare bodies dedicates none and scores those cards 0. Reset
        # to None at the start of each army's turn (same lifecycle as
        # pursue_target). Cited as `simulator.secondary_dedication`.
        "dedicated_card",
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
        #   transient_charge_after_advance — Apoplectic Frenzy (Berzerker
        #       Warband, wave 235). Movement buff: unit is eligible to declare
        #       a charge in a round it Advanced (the [LETHAL HITS] reading was
        #       a fabricated paraphrase — the verbatim rule is advance-and-
        #       charge). Consumed by Battle._do_charge as an exemption from
        #       the _advanced_this_round lockout, parallel to Gladius Assault
        #       Doctrine and Murderer's Cowl, but transient (one round).
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
        # Astra Militarum (Voice of Command Order):
        #   transient_frfsrf_active — First Rank, Fire! Second Rank, Fire! Order
        #       (AM Order). While True, weapons with rapid_fire > 0 gain +1 to
        #       their Attacks characteristic (unconditional, any range). Set by
        #       `orders._apply_order`; cleared with all other transient flags.
        #       Cited as `Order.First Rank, Fire! Second Rank, Fire!`.
        "transient_frfsrf_active",
        # Astra Militarum Voice of Command Order — Duty and Honour!:
        #   transient_plus_one_oc — Duty and Honour! Order. While True, the
        #       affected unit's models add 1 to their Objective Control
        #       characteristic (and, in the faithful rule, Leadership — see
        #       note in _effective_oc; Leadership is not read by the scoring
        #       path so only the OC half is modelled). Set by
        #       `orders._apply_order`; cleared with all other transient flags.
        #       Read by `Battle._effective_oc` behind SWEG_AM_DUTY_AND_HONOUR.
        #       Cited as `Order.Duty and Honour!`.
        "transient_plus_one_oc",
        "transient_plus_one_to_wound_shooting",
        "transient_invuln_4",
        "transient_minus_one_damage_taken",
        "transient_plus_one_to_wound_melee",
        "transient_plus_one_save",
        "transient_reroll_hits_shooting",
        "transient_assault_this_round",
        "transient_charge_after_advance",
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
        # transient_reroll_all_hits: full re-roll of any failed Hit roll for
        # the round/phase (granted by Despoilers when making a Dark Pact,
        # gated SWEG_CSM_ABILITIES). Composes via OR with att_reroll_all_hits.
        # transient_devastating_wounds: unit's weapons gain [DEVASTATING WOUNDS]
        # for the round/phase (granted by Unholy Bloodshed when making a Dark
        # Pact, gated SWEG_CSM_ABILITIES). Composed into effective_dw.
        # transient_hazardous: unit's ranged weapons gain [HAZARDOUS] for this
        # shooting activation (granted by Daemonic Ordnance opt-in, together
        # with transient_devastating_wounds). d6 self-check fires in Unit.attack
        # after the ranged attack sequence, on a roll of 1 the unit takes 3
        # mortal wounds. Cleared per-round by _clear_transient_stratagem_flags.
        # Cited simulator.csm_daemonic_ordnance.
        "transient_lethal_hits",
        "transient_sustained_hits",
        "transient_reroll_wounds",
        "transient_reroll_wounds_ones",
        "transient_reroll_all_hits",
        "transient_devastating_wounds",
        "transient_hazardous",
        # Go To Ground (10e core Battle Tactic Stratagem, 1CP, env-gated
        # SWEG_GTG). Defender buff: a targeted INFANTRY unit gains a 6+
        # invulnerable save AND the Benefit of Cover until the end of the
        # opponent's Shooting phase. Set by Battle._maybe_go_to_ground, read at
        # the save-resolution branch (6++) and the cover application (+1 save),
        # cleared per round with the other transient stratagem flags. Cited as
        # `simulator.go_to_ground`.
        "go_to_ground_active",
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
        # SOROR-DIAG-4: Adepta Sororitas Acts of Faith budget.
        #
        # Two parallel flags support two paths (selected by SWEG_AOF_PER_PHASE):
        #
        # Legacy path (SWEG_AOF_PER_PHASE="0"): `aof_used_this_round`
        #   Prevents a single Unit instance from using Acts of Faith twice in
        #   the same round. Reset once per round in `Battle._run_round`.
        #   Conservative under-approximation of the codex's "one per phase"
        #   literal (collapses to one per round). Chosen conservatively when
        #   SOROR-DIAG-4 was introduced because SOROR-DIAG-3 left Sororitas at
        #   +14.39 pt over-performance; that over-performance has since been
        #   attributed to the broken invulnerable-save mapper (fixed,
        #   commit 299aefc), so the historical reason for the conservative cap
        #   is gone. Legacy path kept byte-identical when gate is OFF.
        #
        # Per-phase path (SWEG_AOF_PER_PHASE unset/"1" — the production default
        # since wave 239; metric-neutral in the N=80 paired A/B, adopted on
        # fidelity-first): `aof_used_this_phase`
        #   Codex-correct: "each unit from your army with this ability can
        #   perform one Act of Faith per phase." (Wahapedia Adepta Sororitas
        #   army rule, https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/).
        #   Reset at the start of the Shooting phase AND at the start of the
        #   Fight phase in `Battle._run_round_vanilla_turns` (and before the
        #   paired sub-phase blocks in `Battle._run_round_alternating`).
        #   The squad-level budget (Army._unit_budget_used["aof"]) is also
        #   cleared per-phase under this gate (instead of once per round).
        #   Cited as `simulator.acts_of_faith`.
        "aof_used_this_round",
        "aof_used_this_phase",
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
        # Set by Battle._do_shoot when the target stands in HEAVY_COVER / RUIN
        # terrain. In 10e this no longer changes the Hit roll (the stale
        # 9th-edition Heavy-Cover -1-to-hit was removed); HEAVY_COVER and RUIN
        # grant the same single Benefit of Cover (+1 save) as LIGHT_COVER, via
        # the in_cover flag. The flag is retained for compatibility with
        # call-sites that still toggle it. Restored to False after shot.
        self.in_heavy_cover: bool = False
        self.uid: str = ""                              # assigned by Battle at start
        self.position: tuple = (0.0, 0.0)               # (x, y) in inches
        # Back-reference to owning army (set by Army.add_unit). Lets
        # Unit.attack() resolve the army-wide detachment + check squad size
        # for keywords like Blast.
        self.army_ref = None
        # SQUAD-ACTIVATION (Lever 1, P1): per-squad id, stamped by
        # Army.add_squad at build time; -1 = lone/unassigned. See __slots__.
        self.squad_id: int = -1
        # PER-MODEL-LOADOUTS (Stage 3): aggregate squad profile when this Unit
        # was expanded per-model (SWEG_PERMODEL); None otherwise. See __slots__.
        self.squad_profile_ref: Optional[UnitProfile] = None
        # Set by Battle each round: True iff this unit moved during the
        # current round's movement sub-phase. Drives the Heavy keyword
        # (+1 to hit if attacker did NOT move).
        self.moved_this_round: bool = False
        # Pariah Nexus action state (wave 74): action name while performing a
        # 10e action this round, else None. See __slots__ note above.
        self.action_this_round: Optional[str] = None
        # AI-pursuit target (wave 121). See __slots__ note above. Cleared
        # per-turn by Battle._run_round_vanilla_turns; None means no active
        # pursuit goal and pick_move_intent falls through to existing logic.
        self.pursue_target = None  # type: Optional[Tuple[float, float]]
        # Secondary deliberate-dedication card key (Stage A). See __slots__
        # note above. Cleared per-turn by Battle._run_round_vanilla_turns;
        # None means this unit is not dedicated to any secondary card.
        self.dedicated_card = None  # type: Optional[str]
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
        self.transient_charge_after_advance: bool = False
        # Awakened Dynasty (Necrons) per-round stratagem flags.
        self.transient_fnp_5: bool = False
        self.transient_plus_one_to_hit_shooting: bool = False
        # First Rank, Fire! Second Rank, Fire! (AM Order): +1 Attacks for
        # Rapid Fire weapons (unconditional, any range). Cleared per round.
        self.transient_frfsrf_active: bool = False
        # Duty and Honour! (AM Order): +1 Objective Control on the affected
        # unit's models for the round. Read by Battle._effective_oc behind
        # SWEG_AM_DUTY_AND_HONOUR; cleared per round. Default False = no-op.
        self.transient_plus_one_oc: bool = False
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
        # CSM datasheet abilities: Despoilers (full hit re-roll during dark pact
        # phase) and Unholy Bloodshed (devastating wounds during dark pact phase,
        # once per battle). Both gated SWEG_CSM_ABILITIES; defaults off.
        # See simulator._apply_dark_pacts for the grant site.
        self.transient_reroll_all_hits: bool = False
        self.transient_devastating_wounds: bool = False
        # Daemonic Ordnance (Forgefiend datasheet ability): ranged weapons gain
        # [HAZARDOUS] for this shooting activation when the ability is elected.
        # Cleared per-round by _clear_transient_stratagem_flags. See
        # simulator._apply_daemonic_ordnance for the grant site.
        self.transient_hazardous: bool = False
        # Go To Ground (10e core stratagem). 6++ invuln + Benefit of Cover on a
        # targeted INFANTRY unit until end of the opponent's Shooting phase.
        self.go_to_ground_active: bool = False
        # Skysplinter Assault (Drukhari detachment) Rain of Cruelty:
        # disembark-turn LANCE on melee weapons + IGNORES COVER on ranged
        # weapons. Set in `simulator._disembark` when the disembarking
        # unit is Drukhari AND the army's detachment is Skysplinter
        # Assault; cleared with the other transient flags at the next
        # round-start by `simulator._clear_transient_stratagem_flags`.
        # Cited as `SKYSPLINTER_ASSAULT.rain_of_cruelty_disembark`.
        self.transient_lance_this_turn: bool = False
        self.transient_ignores_cover_this_turn: bool = False
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
        # SOROR-DIAG-4: Acts of Faith budget flags. See __slots__ for full
        # rationale and citation linkage.
        # Legacy path (SWEG_AOF_PER_PHASE="0"): reset once per round in
        # Battle._run_round.
        self.aof_used_this_round: bool = False
        # Per-phase path (unset/"1", the default): reset at the start of the
        # Shooting phase and again at the start of the Fight phase.
        self.aof_used_this_phase: bool = False
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
        overwatch: bool = False,
        alloc_next_fn=None,
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
        overwatch    - this is a Fire Overwatch shot (10e core stratagem). A
                       ranged attack made out of sequence (in the opponent's
                       Movement / Charge phase) at a charging or arriving enemy.
                       Per the rule, "each time a model in that unit makes a
                       ranged attack, an unmodified Hit roll of 6 is required for
                       it to score a hit" — i.e. an unmodified 1-5 ALWAYS fails.
                       To-hit modifiers and Hit-roll re-rolls do not apply (the
                       outcome is decided purely on the unmodified physical die);
                       Critical Hit effects (Sustained / Lethal Hits) still fire
                       on the unmodified 6. Cited as `simulator.fire_overwatch`.
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
        # each call fresh. Now we read AND write a per-unit budget flag
        # (offensive side: `self`; defensive side: `target`) at each
        # substitution gate. Which flag is read/written depends on the gate:
        #   Legacy (SWEG_AOF_PER_PHASE="0"): `aof_used_this_round` —
        #     reset once per round in `Battle._run_round`.
        #   Per-phase (unset/"1", the default): `aof_used_this_phase` —
        #     reset at the start of the Shooting phase and again at the start
        #     of the Fight phase in `Battle._run_round_vanilla_turns` (and
        #     before the paired sub-phase blocks in `_run_round_alternating`).
        # Cited as `simulator.acts_of_faith`.
        attack_aof_substitution_used = False
        # SOROR-AOF-PER-PHASE: which per-unit Acts of Faith budget flag to
        # consult and set. Unset/"1" (the default) uses the codex-correct
        # per-phase flag; "0" reverts to the legacy per-round flag.
        _aof_per_phase: bool = __import__("os").environ.get("SWEG_AOF_PER_PHASE", "1") == "1"

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
                    # PER-MODEL-LOADOUTS (Stage 4): carry the extra melee weapon's
                    # raw Damage dice onto melee_damage_dice so the per-shot roll
                    # reads it after this extra is hot-swapped in. Empty → mean.
                    "melee_damage_dice": str(_ed.get("damage_dice", "") or ""),
                    "melee_hit_probability": float(
                        _ed.get("hit_probability", 0.0) or 0.0
                    ),
                    "melee_ap": int(_ed.get("ap", 0) or 0),
                    "melee_strength": int(_ed.get("strength", 4) or 4),
                    "melee_weapon": str(_ed.get("weapon", "") or ""),
                    "melee_sustained_hits": int(
                        _ed.get("sustained_hits", 0) or 0
                    ),
                    # Weapon-level keyword flags route to the MELEE-side
                    # UnitProfile fields that Unit.attack reads in the Fight
                    # phase. WAVE-244 BUG FIX: pre-wave-244 these three wrote to
                    # the RANGED-named fields (lethal_hits / devastating_wounds /
                    # twin_linked). After the wave-244 melee mode guards, the
                    # melee resolution sites read melee_lethal_hits /
                    # melee_devastating_wounds / melee_twin_linked, so an extra
                    # melee weapon's LETHAL HITS / DEVASTATING WOUNDS / TWIN-
                    # LINKED never fired (the swap overwrote the unread ranged
                    # field). A single extra weapon is fully covered, so the
                    # melee basket fractions are pinned to 1.0 here.
                    "melee_lethal_hits": bool(_ed.get("lethal_hits", False)),
                    "melee_devastating_wounds": bool(
                        _ed.get("devastating_wounds", False)
                    ),
                    "melee_twin_linked": bool(_ed.get("twin_linked", False)),
                    "melee_devastating_wounds_basket_fraction": 1.0,
                    "lance": bool(_ed.get("lance", False)),
                    "precision": bool(_ed.get("precision", False)),
                    # EXTRA-MELEE-KEYWORD-PARITY — one_shot and hazardous were
                    # absent from the runtime swap dict, so dataclasses.replace
                    # silently inherited the PRIMARY melee profile's values.
                    # A melee weapon that is one_shot must be gated once per
                    # battle; if hazardous=True the fighter self-harms in the
                    # Fight phase. Default False so pre-regen profiles (which
                    # lack the key) behave identically to before the fix.
                    "one_shot": bool(_ed.get("one_shot", False)),
                    "hazardous": bool(_ed.get("hazardous", False)),
                    # anti_keywords on an extra MELEE weapon profile replaces
                    # the primary's melee anti_keywords during this extra's
                    # resolution pass. WAVE-244 BUG FIX: this routes to
                    # melee_anti_keywords now (the melee-mode guard at the
                    # Anti-X site reads the melee field), not the ranged
                    # `anti_keywords` it previously overwrote. UnitProfile's
                    # field is `Tuple[Tuple[str, int], ...]` (tuple-of-tuples
                    # for dataclass hashability); the downstream consumer
                    # (`for kw, thresh in p.melee_anti_keywords`) unpacks each
                    # element as a 2-tuple, so convert from the dict template
                    # here. A single extra weapon is fully covered → the melee
                    # anti basket fraction is 1.0 for each keyword.
                    "melee_anti_keywords": tuple(
                        (_ed.get("anti_keywords") or {}).items()
                    ) if isinstance(_ed.get("anti_keywords"), dict)
                    else tuple(_ed.get("anti_keywords") or ()),
                    "melee_anti_keyword_basket_fractions": tuple(
                        (kw, 1.0)
                        for kw in (_ed.get("anti_keywords") or {})
                    ) if isinstance(_ed.get("anti_keywords"), dict)
                    else tuple(
                        (kw, 1.0) for kw, _ in (_ed.get("anti_keywords") or ())
                    ),
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
                        # PER-MODEL-LOADOUTS (Stage 4): the secondary block is the
                        # aggregate two-profile picker and never carries a raw dice
                        # string, so swapping it in clears damage_dice (use the
                        # secondary mean). Per-model profiles reset the secondary
                        # block to empty, so this candidate never fires there.
                        "damage_dice": "",
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
                        # SEC-KEYWORD-PARITY — carry the four boolean fields so
                        # dataclasses.replace does not silently inherit the
                        # PRIMARY profile's values when the secondary is active.
                        # A secondary profile that is one_shot must be gated
                        # once per battle; if hazardous=True the shooter
                        # self-harms; if indirect_fire=True LoS is waived;
                        # if precision=True cover is bypassed vs CHARACTERs.
                        "one_shot": bool(p.secondary_one_shot),
                        "hazardous": bool(p.secondary_hazardous),
                        "indirect_fire": bool(p.secondary_indirect_fire),
                        "precision": bool(p.secondary_precision),
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
                    # PER-MODEL-LOADOUTS (Stage 4): map the extra profile's raw
                    # Damage dice onto the primary `damage_dice` field so that,
                    # once this extra is hot-swapped in via dataclasses.replace,
                    # the active firing profile exposes the right dice for the
                    # per-shot roll. Empty on aggregate extras (legacy) → mean.
                    "damage_dice": str(ed_fields.get("damage_dice", "") or ""),
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
                    # INDIRECT-PARITY-FIX — carry the five boolean weapon keywords
                    # that _weapon_to_dict now serializes but ex_swap previously
                    # omitted. Without these entries, dataclasses.replace inherits
                    # the PRIMARY profile's value for each field, which produces
                    # silent bugs: a Wyvern whose primary has indirect_fire=False
                    # fires its mortar stormshard with the wrong flag; a unit whose
                    # extra has hazardous=True but primary does not will never
                    # self-harm. Default-False so legacy profiles (pre-regen)
                    # that lack the key behave identically to before the fix.
                    "indirect_fire": bool(ed_fields.get("indirect_fire", False)),
                    "one_shot": bool(ed_fields.get("one_shot", False)),
                    "hazardous": bool(ed_fields.get("hazardous", False)),
                    "precision": bool(ed_fields.get("precision", False)),
                    "lance": bool(ed_fields.get("lance", False)),
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
        # PER-MODEL-LOADOUTS (Stage 4): read the SWEG_ROLLDMG gate once per
        # attack (not per shot). When it is off, the per-shot damage takes the
        # bit-identical mean fast path below, so OFF and per-model-mean are
        # byte-for-byte the legacy / Stage-3 result.
        _roll_dmg_active = _rolldmg_enabled()
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
                # PER-MODEL-LOADOUTS (Stage 4): capture the active melee weapon's
                # raw Damage dice and the mean of JUST that characteristic (before
                # any flat per-shot bonus like Rend and Tear is folded in below).
                # Per shot, `roll_damage` rolls the dice (or returns this mean
                # when the gate is off / dice empty — drawing nothing). The flat
                # bonus (per_shot_dmg - mean) is re-added per shot so the
                # roll-then-modify ordering matches the mean path exactly.
                _dmg_dice = p.melee_damage_dice
                _dmg_dice_mean = per_shot_dmg
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
                # PER-MODEL-LOADOUTS (Stage 4): capture the active ranged weapon's
                # raw Damage dice and the dice-only mean (before the Melta X flat
                # bonus is folded in below). Same roll-then-modify contract as the
                # melee branch above.
                _dmg_dice = p.damage_dice
                _dmg_dice_mean = per_shot_dmg
                n_attacks = max(1, int(p.attacks))
                # FRFSRF: "First Rank, Fire! Second Rank, Fire!" Order
                # (Astra Militarum Voice of Command). Verbatim rule text:
                # "Improve the Attacks characteristic of Rapid Fire weapons
                # equipped by models in this unit by 1." — no range condition,
                # so the +1 applies at all ranges. The half-range Rapid Fire X
                # bonus (line ~2010) is separate and unchanged.
                # Cited: `Order.First Rank, Fire! Second Rank, Fire!`
                if (
                    getattr(self, "transient_frfsrf_active", False)
                    and int(p.rapid_fire) > 0
                ):
                    n_attacks += 1
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
                # Blast adds 1 attack per 5 models in the TARGET UNIT (10e). Use
                # squad_id so two separate squads of the same datasheet are not
                # merged — the old profile.name count summed across every
                # same-name unit in the army, over-counting Blast badly against
                # armies running multiple identical squads. Fall back to the
                # profile.name count only for unassigned models (squad_id < 0).
                try:
                    _tsid = getattr(target, "squad_id", -1)
                    if target.army_ref is None:
                        same_squad = 1
                    elif _tsid is not None and _tsid >= 0:
                        same_squad = sum(
                            1 for u in target.army_ref.alive_units
                            if getattr(u, "squad_id", -1) == _tsid
                        )
                    else:
                        same_squad = sum(
                            1 for u in target.army_ref.alive_units
                            if u.profile.name == target.profile.name
                        )
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

            # ---- Wave 188 (#73) — Knight DAMAGED-bracket -1 to the Hit roll
            # (env-gated SWEG_DMGHIT; flipped DEFAULT-ON after the N=80 A/B showed it
            # faithful + right-direction, Imperial Knights 26.00->25.52; matches the
            # OC half SWEG_DMGOC which is also default-ON — the same datasheet rule.
            # Set SWEG_DMGHIT=0 to disable for an isolation A/B). Real 10e Knight
            # datasheets carry, in the SAME
            # damage-table row the simulator already reads for the Objective Control
            # reduction (Battle._effective_oc, wave 85): "While this model has 1-9
            # wounds remaining [Questoris] / 1-5 [Armiger] / 1-10 [Dominus],
            # subtract N from this model's Objective Control characteristic AND each
            # time this model makes an attack, subtract 1 from the Hit roll."
            # (Verbatim, Wahapedia Knight Paladin + Armiger Warglaive.) The sim
            # modelled only the OC half, so a damaged Knight kept full 3+ accuracy
            # when real 10e drops it to 4+ — it over-killed through the back half of
            # every game (the over-pole). Same faction gate + per-chassis thresholds
            # as _effective_oc; applies to BOTH shooting and melee ("makes an
            # attack"); composes with the +-1 Hit-modifier cap below. Cited
            # `simulator.damaged_hit_bracket`.
            # 10e Damaged-bracket −1 to the Hit roll — data-driven from the real
            # per-datasheet bracket (UnitProfile.damaged_hit_penalty, BSData-
            # extracted via the link-resolving mapper) and applied to EVERY model
            # with one (#77, wave 191). Default-ON; SWEG_DMGBRACKET=0 disables. This
            # RETIRED the Knight-only SWEG_DMGHIT heuristic (wave 188), which
            # degraded only the 6 Knight datasheets — a partial-faithful bias. The
            # wave-190b audit found 94 datasheets / 25 factions carry this Hit
            # penalty; the N=80 generalization A/B was metric-neutral (5.76 -> 5.71)
            # and the data-driven Knight values reproduce the retired heuristic
            # exactly. Applies to BOTH shooting and melee ("makes an attack").
            # Cited `simulator.damaged_bracket`.
            if __import__("os").environ.get("SWEG_DMGBRACKET", "1") != "0":
                _gthr = getattr(self.profile, "damaged_threshold", 0) or 0
                _ghp = getattr(self.profile, "damaged_hit_penalty", 0) or 0
                if _gthr and _ghp and self.current_health <= _gthr:
                    # ---- Leagues of Votann Hekaton Land Fortress — MultiCOG Targeting
                    # (datasheet ability, 10e). Wahapedia verbatim: "Each time this model
                    # makes a ranged attack, you can ignore any or all modifiers to the
                    # following: that attack's Ballistic Skill characteristic; the Hit
                    # roll." The model therefore ignores its OWN damaged-bracket -1-to-Hit
                    # on RANGED attacks (you always elect to ignore the negative modifier).
                    # SCOPE: ranged-only (the ability reads "makes a ranged attack"), so
                    # the damaged penalty STILL applies to the Hekaton's melee (Armoured
                    # wheels). Gated SWEG_VOTANN_HEKATON_MULTICOG — ADOPTED
                    # default-on (wave 257, data-correctness fidelity fix, metric-
                    # inert); SWEG_VOTANN_HEKATON_MULTICOG=0 restores the original
                    # `hit_mod_delta -= _ghp` byte-identically. Cited
                    # `simulator.hekaton_multicog_targeting`.
                    _multicog = (
                        mode != "melee"
                        and (p.faction or "") == "Leagues of Votann"
                        and getattr(p, "name", "") == "Hekaton Land Fortress"
                        and __import__("os").environ.get("SWEG_VOTANN_HEKATON_MULTICOG", "1") != "0"
                    )
                    if not _multicog:
                        hit_mod_delta -= _ghp

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
            # `plus_one_to_wound_melee_only` fires only in the Fight phase (melee).
            # Used for leader auras whose codex text reads "each time a model in
            # that unit makes a melee attack, add 1 to the Wound roll" (e.g. CSM
            # Dark Apostle "Dark Zealotry"). Gated SWEG_CSM_ABILITIES (OFF keeps
            # the prior reroll_hit_ones proxy unchanged). Cited as
            # `simulator.dark_apostle_dark_zealotry`.
            if (att_buffs.get("plus_one_to_wound_melee_only") and mode == "melee"
                    and __import__("os").environ.get("SWEG_CSM_ABILITIES", "1") != "0"):
                wound_mod_delta += 1

            # ---- Chaos Knights — Harbingers of Dread (army rule, 10e). Verbatim
            # Wahapedia (https://wahapedia.ru/wh40k10ed/factions/chaos-knights/):
            # "The Deathly Terror ability is active for your army from the start
            # of the battle." Additional Dread abilities are selected at the
            # start of battle rounds 1, 3 and 5. With SWEG_HARBINGERS OFF
            # (default), SwegHammer always picks Doom — the offensive Dread
            # ("Each time this model makes an attack, if the target of that attack
            # is Battle-shocked, add 1 to the Wound roll.") because Doom is the
            # only Dread the attack pipeline can directly express; the auras
            # (Despair / Deathly Terror, Ld debuffs within 9") are wired into the
            # Battle-shock phase in code/simulator.py. With SWEG_HARBINGERS ON,
            # Despair replaces Doom as the round-1 pick (and Dismay / Darkness /
            # Delirium fill the remaining picks — see code/simulator.py and the
            # Darkness block below), so Doom is SUPPRESSED here — leaving it on
            # would give the army more selected Dread abilities than the rule's
            # three picks grant. Faction-gated to Chaos Knights so Imperial
            # Knights' Code Chivalric handling is untouched. Cited as
            # `simulator.harbingers_of_dread`.
            if (
                mode in ("melee", "ranged")
                and (p.faction or "") == "Chaos Knights"
                and __import__("os").environ.get("SWEG_HARBINGERS", "1") == "0"
                and target.is_currently_battle_shocked(
                    getattr(
                        getattr(getattr(self, "army_ref", None), "_battle_ref", None),
                        "_current_round",
                        0,
                    )
                )
            ):
                wound_mod_delta += 1

            # ---- Chaos Knights Iconoclast Fiefdom — Dread Tyrants Aura (10e).
            # BSData v10.6.0 (Chaos - Chaos Knights Library.cat.gz) verbatim
            # (Iconoclast Fiefdom, Dreaded Masters rule): "Dread Tyrants (Aura):
            # While a friendly DAMNED unit is within 9\" of this unit, each
            # time a model in that unit makes an attack, re-roll a Hit roll of
            # 1 and re-roll a Wound roll of 1."
            # DAMNED units = War Dogs (Armiger-class Chaos Knights). The DAMNED
            # keyword is not captured by the BSData mapper; SwegHammer proxies
            # it by checking if the attacker's name starts with "War Dog".
            # The aura source is any TITANIC Chaos Knights unit within 9".
            # Cited as `ICONOCLAST_FIEFDOM.dread_tyrants_aura`.
            if (
                (p.faction or "") == "Chaos Knights"
                and (p.name or "").startswith("War Dog")
            ):
                _dta_army = getattr(self, "army_ref", None)
                if _dta_army is not None:
                    _dta_det = _dta_army.resolve_detachment()
                    if _dta_det is not None and getattr(
                        _dta_det, "dread_tyrants_aura", False
                    ):
                        _dta_x, _dta_y = self.position
                        _dta_r2 = 9.0 * 9.0
                        _dta_aura_present = False
                        for _dta_u in _dta_army.alive_units:
                            _dta_kw = set(
                                getattr(_dta_u.profile, "unit_keywords", ()) or ()
                            )
                            if "TITANIC" not in _dta_kw:
                                continue
                            if getattr(_dta_u.profile, "faction", "") != "Chaos Knights":
                                continue
                            _dta_ux, _dta_uy = _dta_u.position
                            _dx = _dta_ux - _dta_x
                            _dy = _dta_uy - _dta_y
                            if _dx * _dx + _dy * _dy <= _dta_r2:
                                _dta_aura_present = True
                                break
                        if _dta_aura_present:
                            att_reroll_hit_ones = True
                            att_reroll_wound_ones = True

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
                            # task #28 squad_id re-key: below-half-strength is a
                            # MODEL COUNT check for multi-model squads (10e core:
                            # "below Half-strength" = fewer models than half the
                            # unit's Starting Strength). Use alive model count vs
                            # profile.min_models as a starting-count proxy.
                            # For lone models (squad_id < 0) fall back to wounds.
                            _tgt_squad_id_bor = getattr(target, "squad_id", -1)
                            _tgt_army_bor = getattr(target, "army_ref", None)
                            if (
                                _tgt_squad_id_bor >= 0
                                and _tgt_army_bor is not None
                                and target.profile.min_models >= 2
                            ):
                                _alive_count = sum(
                                    1 for u in _tgt_army_bor.alive_units
                                    if getattr(u, "squad_id", -1) == _tgt_squad_id_bor
                                )
                                _start_count = float(target.profile.min_models)
                                _bor_below_half = _alive_count < _start_count / 2.0
                            else:
                                # Lone model or no army ref — use wound fraction.
                                _tgt_hp_bor = float(target.profile.health) or 1.0
                                _bor_below_half = target.current_health < _tgt_hp_bor / 2.0
                            if _bor_below_half:
                                wound_mod_delta += 1

            # ---- Necrons Cursed Legion — Relentless Onslaught (detachment rule,
            # 10e). BSData v10.6.0 (Necrons.cat.gz, rule id 1dfc-5377-99ac-a700)
            # verbatim: "Each time a NECRONS model from your army makes an attack
            # that targets a unit within range of one or more objective markers,
            # add 1 to the Hit roll. In addition, ranged weapons equipped by
            # NECRONS VEHICLE and NECRONS MOUNTED models (excluding TITANIC
            # models) from your army have the [ASSAULT] ability." This block
            # handles the FIRST clause (the +1 to Hit); the [ASSAULT] clause is
            # wired in simulator._do_shoot's Advance-lockout (it grants
            # shoot-after-Advance, not a hit/wound modifier). Three-way gate,
            # modelled on the World Eaters Beacons of Rage / Awakened Dynasty
            # bonus_to_hit_when_led pattern above:
            #   1. attacker is a NECRONS model (p.faction == "Necrons"),
            #   2. the attacker's army's resolved detachment carries
            #      `relentless_onslaught` (read via the army back-reference, the
            #      same army->detachment access Beacons of Rage / Iconoclast use),
            #   3. the TARGET unit is within range of an objective marker
            #      (`target.on_objective`, set per round in Battle._run_round —
            #      True when the unit is within an objective's control radius,
            #      which is exactly this rule's "within range of one or more
            #      objective markers" condition).
            # Applies to BOTH ranged and melee ("makes an attack", not ranged-
            # only). The +1 is added to `hit_mod_delta`; it composes with any
            # other +1-to-hit source through the existing 10e ±1 Hit-modifier cap
            # (hit_mod_clamped, ~line 2530) — if another +1 already applies the
            # clamp keeps the net at +1 rather than doubling. There is NO round
            # restriction. Cited as `simulator.relentless_onslaught` and
            # `CURSED_LEGION.relentless_onslaught`.
            if p.faction == "Necrons" and getattr(target, "on_objective", False):
                _own_army_ro = getattr(self, "army_ref", None)
                if _own_army_ro is not None:
                    try:
                        _det_ro = _own_army_ro.resolve_detachment()
                    except Exception:
                        _det_ro = None
                    if _det_ro is not None and getattr(
                        _det_ro, "relentless_onslaught", False
                    ):
                        hit_mod_delta += 1

            # ---- Leagues of Votann — Prioritised Efficiency (army rule,
            # current 10e codex). BSData v10.6.0 (Leagues of Votann.cat.gz,
            # rule id 351a-a702-9080-7f08) verbatim, Hostile Acquisition
            # clause: "Each time a model in this unit makes an attack that
            # targets an enemy unit within range of one or more objective
            # markers, add 1 to the Hit roll."
            #
            # This block re-introduces the army-wide combat buff the codex
            # actually grants Leagues of Votann — the simulator had run Votann
            # with NO army rule at all since the launch-day Eye of the
            # Ancestors mechanic was retired (see the RETIRED comment ~line
            # 3210 below and simulator._maybe_award_judgement_token). The
            # retired rule was a blanket marked-target re-roll that caused a
            # +16.8 pt Votann over-performance; THIS rule is the real printed
            # replacement and is deliberately conditional — the +1 to Hit only
            # fires when the TARGET is within range of an objective marker,
            # exactly the discriminator that keeps it moderate. It is the same
            # near-objective +1-to-Hit shape already proven for Necrons
            # Relentless Onslaught directly above (target.on_objective is set
            # per round in Battle._run_round — True when the unit is within an
            # objective's control radius, which is precisely "within range of
            # one or more objective markers").
            #
            # APPROXIMATION (documented in data/rule_citations.d/votann.json):
            #   1. Prioritised Efficiency has two states keyed off Yield Points
            #      (YP): Hostile Acquisition while YP < 7 (the start-of-battle
            #      and early/mid-game state) and Fortify Takeover at YP >= 7.
            #      The Yield-Point economy (1-4 YP gained at the end of each
            #      Command phase from objective control, reaching the 7-YP
            #      switch only in the back half of a winning game) is NOT
            #      modelled — there is no YP state machine in the simulator. We
            #      implement the HOSTILE ACQUISITION state only, which is the
            #      state units carry at the start of the battle and hold for
            #      most of a typical game. This errs on the moderate/under side:
            #      Fortify Takeover's extra defensive -1-to-Wound and the
            #      attacker-anchored (rather than target-anchored) +1 to Hit are
            #      NOT granted, and they only apply when the Votann player is
            #      already winning the objective game.
            #   2. The Hostile Acquisition Advance-and-Charge re-roll clause is
            #      NOT modelled (the simulator has no per-unit Advance/Charge
            #      re-roll plumbing tied to the army rule). Only the +1-to-Hit
            #      clause — the load-bearing combat effect — is implemented.
            #
            # Faction-gated on the attacker's army via Army.is_votann_army
            # (matches the project's existing Votann gate). Applies to BOTH
            # ranged and melee ("makes an attack", no mode restriction). The +1
            # is added to hit_mod_delta and composes with any other +1-to-hit
            # source through the existing 10e +/-1 Hit-modifier cap
            # (hit_mod_clamped, ~line 2976) — never doubles. Env-gated
            # SWEG_VOTANN_PRIORITISED_EFFICIENCY (default OFF); OFF leaves this
            # path dead so the retired-rule-zeroed Votann behaviour stays
            # byte-identical to the pre-change baseline. Cited as
            # `simulator.prioritised_efficiency`.
            if (
                os.environ.get("SWEG_VOTANN_PRIORITISED_EFFICIENCY", "1") != "0"
                and getattr(target, "on_objective", False)
            ):
                _own_army_pe = getattr(self, "army_ref", None)
                if _own_army_pe is not None and getattr(
                    _own_army_pe, "is_votann_army", False
                ):
                    hit_mod_delta += 1

            # ---- Adepta Sororitas Hallowed Martyrs — The Blood of Martyrs
            # (wave 234, detachment rule). BSData v10.6.0 verbatim (rule id
            # afa4-169c-3aaa-650): "Each time an ADEPTA SORORITAS model from
            # your army makes an attack, add 1 to the Hit roll if that model's
            # unit is below its Starting Strength, and add 1 to the Wound
            # roll, as well, if that model's unit is Below Half-strength."
            # Two-tier gate (both ranged and melee — the rule says "makes an
            # attack" with no mode restriction):
            #   Tier 1 — below Starting Strength: alive members < start_count
            #     (single-model units: current_health < profile.health)
            #     → hit_mod_delta += 1; routes through the 10e ±1 hit-modifier
            #     clamp at line ~2755 (hit_mod_clamped = max(-1, min(1, ...))).
            #   Tier 2 — below Half-strength (additionally): alive members <
            #     start_count / 2.0 (single-model: current_health < health/2.0)
            #     → wound_mod_delta += 1; same ±1 wound-modifier clamp.
            # Reach the squad substrate via the army back-reference and
            # _battle_ref._squad_start_count[(army.name, squad_id)] — same
            # access pattern as the Cursed Legion block immediately above.
            # If no army ref or no battle ref the buffs do not fire (pre-battle
            # standalone tests see no buff); no silent default for data that
            # should exist.
            # Cited as `HALLOWED_MARTYRS.soror_blood_of_martyrs`.
            if p.faction == "Adepta Sororitas":
                _own_army_bom = getattr(self, "army_ref", None)
                if _own_army_bom is not None:
                    try:
                        _det_bom = _own_army_bom.resolve_detachment()
                    except Exception:
                        _det_bom = None
                    if _det_bom is not None and getattr(
                        _det_bom, "soror_blood_of_martyrs", False
                    ):
                        _battle_bom = getattr(_own_army_bom, "_battle_ref", None)
                        _sid_bom = getattr(self, "squad_id", -1)
                        if _sid_bom >= 0 and _battle_bom is not None:
                            # Multi-model squad: use alive member count vs
                            # recorded starting count (10e core: "below
                            # [Starting] Strength" = fewer models than the
                            # unit's Starting Strength).
                            _start_bom = _battle_bom._squad_start_count.get(
                                (_own_army_bom.name, _sid_bom), 1
                            )
                            _alive_bom = sum(
                                1 for _u in _own_army_bom.alive_units
                                if getattr(_u, "squad_id", -1) == _sid_bom
                            )
                            if _start_bom > 1:
                                _below_start_bom = _alive_bom < _start_bom
                                _below_half_bom = _alive_bom < _start_bom / 2.0
                            else:
                                # Single-model unit: use wound-fraction gate
                                # (10e convention: vehicles / characters are
                                # never "below Starting Strength" per model
                                # count; wounds fraction is the canonical
                                # proxy, mirroring the Delirium / battleshock
                                # single-model path in simulator.py).
                                _hp_bom = float(p.health) or 1.0
                                _below_start_bom = self.current_health < _hp_bom
                                _below_half_bom = self.current_health < _hp_bom / 2.0
                        else:
                            # No battle ref or lone model without a squad —
                            # buffs do not fire (pre-battle tests, edge cases).
                            _below_start_bom = False
                            _below_half_bom = False
                        if _below_start_bom:
                            hit_mod_delta += 1
                        if _below_half_bom:
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

            # ---- Righteous Paragons (Paragon Warsuits datasheet ability,
            # 10e Adepta Sororitas codex). Wahapedia verbatim: "Each time a
            # model in this unit makes an attack that targets a MONSTER or
            # VEHICLE unit, add 1 to the Hit roll and add 1 to the Wound
            # roll." Two-way gate:
            #   1. attacker carries the `righteous_paragons` flag (set on the
            #      Paragon Warsuits UnitProfile via overrides.json),
            #   2. target has MONSTER or VEHICLE in its unit_keywords.
            # Applies to both ranged and melee attacks; no phase restriction
            # in the rule text. Cited as `simulator.righteous_paragons`.
            if p.righteous_paragons:
                _rp_tgt_kws = set(target.profile.unit_keywords or ())
                if "MONSTER" in _rp_tgt_kws or "VEHICLE" in _rp_tgt_kws:
                    hit_mod_delta += 1
                    wound_mod_delta += 1

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

            # ---- Gloam Rot (Chaos Daemons — Nurgle army rule, 10e). BSData
            # verbatim: "Each time an attack targets this unit, if the Strength
            # characteristic of that attack is greater than this unit's Toughness
            # characteristic, subtract 1 from the Wound roll." Two-way gate:
            #   1. defender carries the `gloam_rot` flag (set per-unit via
            #      overrides.json on Nurgle Daemon datasheets),
            #   2. attacker Strength > defender effective Toughness.
            # No leader-attachment gate — the rule is unconditional on all
            # qualifying datasheets. Cited as `simulator.gloam_rot`.
            if target.profile.gloam_rot and strength > _effective_toughness:
                wound_mod_delta -= 1

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
            # The rule's BATTLELINE-or-within-6"-of-BATTLELINE proximity gate
            # now uses the same `_doctrina_battleline_proximity_met` helper as
            # the Conqueror armour-penetration leg (~line 1968) and the
            # Protector defensive leg (~line 2565). Only 2 of 42 AdMech
            # datasheets carry BATTLELINE (Skitarii Vanguard / Rangers), so
            # applying the hit-modifier army-wide was granting the Ballistic
            # Skill / Weapon Skill bonus to ~95% of AdMech units that the
            # codex does not cover. The proximity helper mirrors the real-rule
            # "if this unit has the BATTLELINE keyword and/or it is within 6"
            # of one or more friendly ADEPTUS MECHANICUS BATTLELINE units"
            # gate. Faction-gated on the attacker. Cited as
            # `simulator.doctrina_imperatives`.
            if p.faction == "Adeptus Mechanicus":
                own_army = getattr(self, "army_ref", None)
                imperative = (
                    getattr(own_army, "doctrina_imperative", None)
                    if own_army is not None else None
                )
                if (
                    imperative == "protector"
                    and mode != "melee"
                    and _doctrina_battleline_proximity_met(self)
                ):
                    hit_mod_delta += 1
                elif (
                    imperative == "conqueror"
                    and mode == "melee"
                    and _doctrina_battleline_proximity_met(self)
                ):
                    hit_mod_delta += 1

            # ---- T'au Empire Markerlights — base army-rule offensive buff.
            # Verbatim (T'au Empire.cat, Markerlight ability): "Each time a
            # T'AU EMPIRE unit from your army (excluding KROOT units) is
            # selected to shoot, ranged weapons equipped by models in your
            # unit have their Ballistic Skill characteristic improved by 1 and
            # have the [SUSTAINED HITS 1] ability while targeting an enemy unit
            # that is visible to one or more friendly MARKERLIGHT units...".
            # Modelled as: a T'au ranged attacker firing at a Guided (Marked)
            # target gets +1 to Hit (here) and [SUSTAINED HITS 1] (at the
            # sustained accumulator below). This is the ARMY rule — applies in
            # every detachment, every round — and is DISTINCT FROM and STACKS
            # WITH the Mont'ka Killing Blow [LETHAL HITS] (rounds 1-3) handled
            # further below. The base effect was previously unmodelled: the
            # Marked/Guided status was populated each round by
            # Battle._run_markerlight_phase but only the Mont'ka [LETHAL HITS]
            # consumer read it. The sim marks the highest-points enemy per
            # MARKERLIGHT unit (a conservative under-approximation of "any
            # target visible to a Markerlight unit"). Cited as
            # `simulator.markerlights`.
            # GATE 2 — SWEG_TAU_MARKERLIGHT_BASE_LOS (ADOPTED default-on wave 254;
            # =0 is the byte-identical kill-switch). The base Guided buff (+1 to Hit here, [SUSTAINED HITS
            # 1] in the sustained-hits branch below) is gated on the Marked set
            # populated by Battle._run_markerlight_phase. The legacy sim gated it
            # on `guided_enemy_uids`, which is gated on a per-carrier Ballistic
            # Skill to-hit roll — firing the base buff only ~half the time the
            # real rule does. The verbatim rule grants the buff purely on the
            # line-of-sight / markerlight-token condition ("while targeting an
            # enemy unit that is visible to one or more friendly MARKERLIGHT
            # units"), with NO per-attacker to-hit roll, so the line-of-sight
            # set `guided_los_enemy_uids` (built without the to-hit roll) is the
            # faithful Marked set. ADOPTED default-on (wave 254): this completes
            # wave 252, which made the PRODUCER (simulator.py) build the
            # line-of-sight set default-on but left this CONSUMER gate-read at
            # `== "1"` (default-off), so the line-of-sight set was built every
            # Shooting phase and silently discarded at the production default.
            # Paired N=80 (T'au-scoped, merged into the sc14a anchor): gated mean
            # absolute error 4.20 -> 3.96 (-0.24); T'au +3.81 (43.6 -> 47.4),
            # moving the under-pole toward its real 54.3. SWEG_TAU_MARKERLIGHT_BASE_LOS=0
            # is the kill-switch restoring the legacy to-hit-gated `guided_enemy_uids`
            # (byte-identical to pre-adoption). Mont'ka [LETHAL HITS] still reads
            # `guided_enemy_uids` elsewhere, so only the base buff changes.
            # Cited as `simulator.tau_markerlight_base_los`.
            _ml_guided_attr = (
                "guided_los_enemy_uids"
                if __import__("os").environ.get(
                    "SWEG_TAU_MARKERLIGHT_BASE_LOS", "1"
                ) != "0"
                else "guided_enemy_uids"
            )
            _tau_markerlight_guided = (
                mode != "melee"
                and (p.faction or "").lower() in ("t'au empire", "tau empire")
                and target.uid in getattr(
                    getattr(self, "army_ref", None), _ml_guided_attr, set()
                )
            )
            if _tau_markerlight_guided:
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

            # ---- Fire Overwatch (10e core stratagem). A ranged shot taken out
            # of sequence at a charging / arriving enemy. The rule makes the
            # unmodified Hit roll the SOLE arbiter: an unmodified 1-5 always
            # fails, only an unmodified 6 hits. To-hit modifiers therefore have
            # no bearing on the result, so we suppress the +/-1 hit-modifier
            # accumulation for an overwatch shot (Heavy, Big Guns Never Tire,
            # Indirect, leader auras) — the gate at the to-hit roll forces the
            # nat-6 requirement regardless. Hit-roll re-rolls are likewise
            # disabled below. Melee can never be an overwatch shot. Cited as
            # `simulator.fire_overwatch`.
            overwatch_attack = bool(overwatch) and mode != "melee"

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

            # ---- Cover and the Hit roll (10e). Current 10e cover grants ONLY
            # the Benefit of Cover (+1 to the armour saving throw, applied
            # below via the in_cover flag). There is no terrain -1-to-hit and
            # no Light/Heavy cover split in the core rules — the stale
            # 9th-edition "Heavy Cover / Ruins impose -1 to hit" modifier has
            # been removed. The in_heavy_cover flag is therefore no longer read
            # here; HEAVY_COVER and RUIN grant the same single Benefit of Cover
            # as LIGHT_COVER. Cited as `simulator.benefits_of_cover` /
            # `simulator.cover_heavy`.

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

            # ---- Harbingers of Dread — Darkness (SWEG_HARBINGERS, default-ON since wave 232).
            # The TARGET model must be a Chaos Knights model; if the attacking
            # unit is Battle-shocked OR more than 18" away from the target, the
            # attacker suffers -1 to its Hit roll. Melee is included (the rule
            # text says "each time an attack is made against this model" with no
            # ranged-only restriction). The 18" range check uses the `distance`
            # parameter passed to Unit.attack (0.0 for melee calls means the
            # attacker is in engagement, which is always ≤ 18", so the
            # distance-gate never fires in melee — consistent with competitive
            # play where Darkness only matters at range for non-engaged targets).
            # BSData verbatim:
            # "3 - Darkness: Each time an attack is made against this model, if
            # the attacking model's unit is Battle-shocked or more than 18\" away,
            # subtract 1 from the Hit roll."
            # Cited as `simulator.harbingers_of_dread_darkness`.
            if (
                __import__("os").environ.get("SWEG_HARBINGERS", "1") != "0"
                and (target.profile.faction or "") == "Chaos Knights"
            ):
                _atk_army_dk = getattr(self, "army_ref", None)
                _battle_dk = (
                    getattr(_atk_army_dk, "_battle_ref", None)
                    if _atk_army_dk is not None else None
                )
                _cur_round_dk = (
                    getattr(_battle_dk, "_current_round", 0)
                    if _battle_dk is not None else 0
                )
                _atk_bs_dk = self.is_currently_battle_shocked(_cur_round_dk)
                if _atk_bs_dk or distance > 18.0:
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
            # Fire Overwatch (10e core stratagem): a nat-6 is the ONLY hit, so
            # to-hit modifiers are irrelevant — drop the accumulated hit delta
            # so the unmodified die alone decides the shot. The wound side is
            # unaffected (the rule only constrains the Hit roll). Cited as
            # `simulator.fire_overwatch`.
            if overwatch_attack:
                hit_mod_delta = 0
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
            # WAVE-244 melee mode-routing — Anti-X is a per-weapon keyword, so
            # the Fight phase must read the MELEE weapon's Anti-X, not the
            # ranged primary's. Pre-wave-244 this site read `p.anti_keywords`
            # unconditionally; that field is populated from the ranged primary,
            # so a ranged ANTI-INFANTRY (Howling Banshees' shuriken pistols)
            # leaked the lowered crit-wound threshold onto every melee attack.
            # `melee_anti_keywords` / `melee_anti_keyword_basket_fractions` are
            # sourced from the chosen melee weapon and default empty — mirrors
            # the melee_lethal_hits / melee_sustained_hits split.
            _mode_anti = p.melee_anti_keywords if mode == "melee" else p.anti_keywords
            _mode_anti_fractions = (
                getattr(p, "melee_anti_keyword_basket_fractions", ())
                if mode == "melee"
                else getattr(p, "anti_keyword_basket_fractions", ())
            )
            if _mode_anti and target.profile.unit_keywords:
                target_kw = set(target.profile.unit_keywords)
                _anti_fractions = dict(_mode_anti_fractions or ())
                for kw, thresh in _mode_anti:
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
            # ---- Benefit of Cover (10e core rule). Ranged-only: melee
            # attacks never benefit from cover. +1 to the armour save (one
            # pip better; cover can never improve a save by more than 1).
            # AP0 / 3+-save exception (applies to ALL models, not just
            # INFANTRY): "If a model has a Save characteristic of 3+ or
            # better, that model cannot have the Benefit of Cover against
            # attacks made with weapons that have an Armour Penetration
            # characteristic of 0." So a 3+-or-better model in cover gains
            # nothing against an AP0 attack — but still gains the +1 save
            # against an attack with any AP. Wahapedia core rules — Terrain
            # Features / Benefit of Cover. Cited as `simulator.benefits_of_cover`
            # and `simulator.cover_light`.
            # CORE-RULES-AUDIT (2026-05-31): an Indirect Fire attack made at a
            # target the bearer cannot see grants that target the Benefit of
            # Cover for this attack, regardless of terrain (the +1 save here).
            # See docs/CORE_RULES_AUDIT.md #3.
            cover_blocked_by_ap0_exception = (
                # `ap` is the attack's Armour Penetration as a non-positive
                # int (0, -1, -2, …); ap == 0 is the AP0 case. The model's
                # base Save characteristic is target.profile.save (3 means
                # 3+; a lower number is a better save).
                ap == 0 and target.profile.save <= 3
            )
            # Recon Element "Masters of Camouflage" (gated SWEG_AM_RECON, default-off
            # -> byte-identical). Detachment rule: "Astra Militarum Walker and
            # Regiment models from your army have the Benefit of Cover." (Recon
            # Element is the meta's top Guard detachment and the LVO XII champion's
            # list; the simulator otherwise models the offence detachment Combined
            # Arms, missing the durability that lets cheap T3 bodies survive on
            # objectives — the diagnosed driver of the Astra Militarum under-pole.)
            # APPROXIMATION: "Regiment" is not a BSData v10.6.0 keyword (same gap
            # Born Soldiers faces), so the proxy is Astra Militarum INFANTRY or
            # WALKER models; the big VEHICLE tanks are excluded (conservative), and
            # the in-cover stacking-to-3+ half is not modelled (the engine caps
            # cover at the single +1 pip). Ranged-only, like all Benefit of Cover.
            # Cited as `simulator.masters_of_camouflage`.
            _recon_cover = (
                (target.profile.faction or "") == "Astra Militarum"
                and ("INFANTRY" in (target.profile.unit_keywords or ())
                     or "WALKER" in (target.profile.unit_keywords or ()))
                and __import__("os").environ.get("SWEG_AM_RECON", "0") == "1"
            )
            if (
                mode != "melee"
                and (target.in_cover or indirect_fire_attack or _recon_cover)
                and not ignore_cover
                and not precision_pierces_cover
                and not cover_blocked_by_ap0_exception
            ):
                improved = save_after_ap - 1
                improved = max(2, improved)  # universal 2+ armour floor
                # Cover never makes a save worse than it already was, and the
                # +1 it grants here is already the single-pip cap.
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
            # Task #92 (gated SWEG_COND_INVULN, default-ON): use the per-attack-type
            # invulnerable save. 10e has CONDITIONAL invulns — Wyches 4+ vs melee /
            # 6+ vs ranged; ranged-only saves (Imperial Knight Ion Shield) give NO
            # invuln in melee. The per-attack values (invuln_save_melee /
            # invuln_save_ranged) are mapper-extracted + override-combined; this
            # generalises and subsumes the old invuln_ranged_only melee suppressor.
            # Cited as `simulator.conditional_invuln_save`. `=0` reverts to the
            # single value + the Ion-Shield-only special-case below.
            if __import__("os").environ.get("SWEG_COND_INVULN", "1") != "0":
                invuln = (target.profile.invuln_save_melee if mode == "melee"
                          else target.profile.invuln_save_ranged)
            else:
                invuln = target.profile.invuln_save
                # Imperial Knight Ion Shield (10e): ranged-only — suppress the
                # datasheet invuln for melee. Cited as `simulator.ion_shield_ranged_only`.
                if mode == "melee" and target.profile.invuln_ranged_only:
                    invuln = 7
            # ---- Target's buffs: army-wide invuln. Only overrides if better
            # (lower number) than what the target already has. 7 = unset.
            tgt_invuln_buff = int(tgt_buffs["extra_invuln"])
            if tgt_invuln_buff <= 6 and tgt_invuln_buff < invuln:
                invuln = tgt_invuln_buff
            # Glamour of Tzeentch (Cult of Magic) — transient 4++ invuln on the
            # target unit for the round. Same "only override if better" rule.
            if target.transient_invuln_4 and invuln > 4:
                invuln = 4
            # Go To Ground (10e core stratagem) — transient 6++ invuln on the
            # targeted INFANTRY unit until end of the opponent's Shooting phase.
            # The accompanying Benefit of Cover (+1 save) is applied via the
            # in_cover flag in Battle._do_shoot. Same "only override if better"
            # rule. Cited as `simulator.go_to_ground`.
            if getattr(target, "go_to_ground_active", False) and invuln > 6:
                invuln = 6
            effective_save = min(save_after_ap, invuln) if invuln <= 6 else save_after_ap
            save_target = effective_save  # 7 = no save

            # DURABILITY instrument (#85) — per target-keyword class, the realized
            # base save, AP-and-cover-modified effective save, cover-applied flag,
            # and AP faced. Localizes whether VEHICLE durability is under-applied
            # (worse effective save / lower cover rate than INFANTRY relative to
            # their base) vs genuinely fragile. Read-only, gated.
            if mode != "melee" and __import__("os").environ.get("SWEG_DURABILITY_INSTR"):
                _tkw = set(target.profile.unit_keywords or ())
                _cls = ("VEHICLE" if ("VEHICLE" in _tkw or "MONSTER" in _tkw)
                        else "INFANTRY" if "INFANTRY" in _tkw else "OTHER")
                _dd = DURABILITY_STATS.setdefault(
                    _cls, {"hits": 0, "base": 0.0, "eff": 0.0, "cover": 0, "ap": 0.0, "inv": 0},
                )
                _dd["hits"] += 1
                _dd["base"] += (target.profile.save or 7)
                _dd["eff"] += min(effective_save, 7)
                _dd["ap"] += -ap
                if target.in_cover:
                    _dd["cover"] += 1
                if invuln <= 6:
                    _dd["inv"] += 1

            # Re-roll flags from attacker's buffs.
            att_reroll_hit_ones = bool(att_buffs["reroll_hit_ones"])
            # TSON-AURA-V2 (iter60): shooting-phase-only re-roll 1s (Ahriman,
            # Infernal Master, Sorcerer in Terminator Armour). The codex rules
            # for these leaders restrict the hit-reroll to Psychic Attacks or
            # to "the Shooting phase" explicitly; we approximate by blocking
            # the buff in melee (mode == "melee"). Composes with the existing
            # att_reroll_hit_ones path — if either flag is set, the die re-rolls.
            if bool(att_buffs.get("reroll_hit_ones_shooting_only", False)) and mode != "melee":
                att_reroll_hit_ones = True
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

            # ---- T'au Empire Sunforge + Armour Hunter (datasheet abilities,
            # 10e). Gated SWEG_TAU_SUNFORGE_HAMMERHEAD_ABILITIES (adopted default-on,
            # wave 256; set to 0 to disable).
            # Sunforge (Crisis Sunforge Battlesuits): ranged attacks vs MONSTER/
            #   VEHICLE may re-roll the Wound roll AND re-roll the Damage roll.
            # Armour Hunter (Hammerhead Gunship): +1 to Hit vs MONSTER/VEHICLE
            #   (both ranged and melee), modelled exactly like Righteous Paragons'
            #   hit-half (no wound bonus).
            # _sunforge_vs_armour is set True here and consumed at the per-shot
            # damage-roll site below; it must start False so the damage re-roll
            # branch is skipped entirely when the gate is off.
            _sunforge_vs_armour = False
            if (p.tau_sunforge or p.tau_armour_hunter) and \
                    os.environ.get("SWEG_TAU_SUNFORGE_HAMMERHEAD_ABILITIES", "1") != "0":
                _tau_tgt_kws = set(target.profile.unit_keywords or ())
                _tau_vs_armour = ("MONSTER" in _tau_tgt_kws or "VEHICLE" in _tau_tgt_kws)
                if _tau_vs_armour:
                    if p.tau_armour_hunter:
                        hit_mod_delta += 1
                    if p.tau_sunforge and mode != "melee":
                        # Sunforge wound re-roll — reuse the existing full-failed-
                        # wound re-roll plumbing (consumed in the wound loop).
                        att_reroll_all_wounds = True
                        # Flag the per-shot Damage re-roll for the ranged damage
                        # loop (the one novel branch). Ranged-only per the rule.
                        _sunforge_vs_armour = True

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
            if own_army is not None and is_marine_faction(p.faction):
                # squad_id re-key (task #28): if the nominated target has a
                # valid squad_id (>= 0), match any model in the same squad so
                # all attacks against any squad-mate benefit from the re-roll,
                # not just attacks against the exact model whose uid was stored.
                # Fall back to uid equality for lone models (squad_id < 0).
                _oath_squad_id = getattr(own_army, "oath_target_squad_id", -1)
                _target_squad_id = getattr(target, "squad_id", -1)
                if (
                    _oath_squad_id >= 0
                    and _target_squad_id >= 0
                    and _oath_squad_id == _target_squad_id
                ) or getattr(own_army, "oath_target_uid", None) == target.uid:
                    att_reroll_all_hits = True

            # ---- Adeptus Mechanicus — Belisarius Cawl's "Invocation of
            # Machine Vengeance" Canticle (10e). Structurally identical to Oath
            # of Moment above: when the attacker is an AdMech unit AND its army
            # has designated this round's Machine Vengeance target on this
            # defender's uid, every attack against that defender re-rolls the
            # HIT roll (codex grants Hit re-rolls only — no wound re-roll). The
            # designation is set in Battle._pick_machine_vengeance_target, which
            # itself fires only while a Belisarius Cawl model is alive in the
            # army, so this gate already implies "Cawl alive". The OR composes
            # with the existing att_reroll_all_hits — it only ever sets the
            # flag True, never un-sets it. Cited as `simulator.machine_vengeance`.
            if own_army is not None and p.faction == "Adeptus Mechanicus":
                if getattr(own_army, "machine_vengeance_target_uid", None) == target.uid:
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
            #
            # WAVE 71 FIDELITY FIX: the rule is "Each time this model is selected
            # to shoot or fight, you can re-roll ONE Hit roll and ONE Wound roll"
            # — a SINGLE re-roll of each per activation. Because SwegHammer is
            # one-Unit-per-model, "each time this model is selected" maps exactly
            # onto one re-roll per Unit activation. The previous implementation set
            # att_reroll_hit_ones / att_reroll_wound_ones (re-roll EVERY natural 1),
            # which over-scales with shot volume: a Knight gun firing 20+ shots got
            # ~3-4 effective re-rolls instead of the rule's one, inflating Imperial
            # Knights' damage on the high-volume platforms. We now grant a single
            # per-activation re-roll budget, spent on the first failed die (the
            # optimal use of a "re-roll one of your choice").
            _chiv_hit_reroll = bool(
                own_army is not None
                and (p.faction or "") == "Imperial Knights"
            )
            _chiv_wound_reroll = _chiv_hit_reroll

            # T'au Empire Targeting Array (Hammerhead Gunship) — one Hit-or-Wound
            # re-roll per shooting activation. Reuse the single-slot Code-Chivalric
            # Wound re-roll: grant one per-activation Wound-die re-roll (ranged).
            # APPROXIMATION: the rule allows re-rolling EITHER one Hit OR one Wound
            # die; we always spend it on a Wound die (the higher-value choice for an
            # anti-armour Railgun where the wound roll is the bottleneck).
            # Gated SWEG_TAU_SUNFORGE_HAMMERHEAD_ABILITIES (adopted default-on, wave 256;
            # set to 0 to disable).
            if (mode != "melee" and p.tau_targeting_array and
                    os.environ.get("SWEG_TAU_SUNFORGE_HAMMERHEAD_ABILITIES", "1") != "0"):
                _chiv_wound_reroll = True

            # Fire and Fade (Aeldari Warhost stratagem) — transient
            # re-roll hit rolls of 1 on shooting attacks for the round.
            att_reroll_hits_shooting_ones = (
                mode != "melee" and getattr(self, "transient_reroll_hits_shooting", False)
            )
            if att_reroll_hits_shooting_ones:
                att_reroll_hit_ones = True

            # CSM Chaos Terminator Squad "Despoilers" (10e datasheet ability):
            # when this unit makes a Dark Pact, until the end of the phase, each
            # model may re-roll the Hit roll. Verbatim BSData v10.6.0 (Chaos -
            # Chaos Space Marines.cat.gz, ability id 13a2-57cd-83ff-2127):
            # "Each time this unit makes a Dark Pact, until the end of the
            # phase, each time a model in this unit makes an attack, you can
            # re-roll the Hit roll." Applied via transient_reroll_all_hits set in
            # simulator._apply_dark_pacts; gated SWEG_CSM_ABILITIES. Composes
            # via OR with att_reroll_all_hits (Oath of Moment, etc.).
            # Cited as `simulator.csm_despoilers`.
            if getattr(self, "transient_reroll_all_hits", False):
                att_reroll_all_hits = True

            # ---- Fire Overwatch (10e core stratagem): the shot only hits on an
            # unmodified 6, so Hit-roll re-rolls (Oath of Moment, Twin-Linked,
            # detachment / Code Chivalric / Fire and Fade) do not change the
            # outcome and are suppressed — the unmodified physical die alone
            # decides each shot. Done after every hit-reroll source above is
            # resolved so this clears all of them in one place. Wound re-rolls
            # are untouched (the rule constrains only the Hit roll). Cited as
            # `simulator.fire_overwatch`.
            if overwatch_attack:
                att_reroll_hit_ones = False
                att_reroll_all_hits = False
                att_reroll_hits_shooting_ones = False
                _chiv_hit_reroll = False

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

            # Chaos Space Marines Legionaries "Veterans of the Long War" (10e
            # datasheet ability). Verbatim, cross-checked (Wahapedia CSM
            # Legionaries datasheet + BSData ability a5ea-d708-db75-226c): "Each
            # time a model in this unit targets an enemy unit with a melee attack,
            # re-roll a Wound roll of 1. If that enemy unit is within range of an
            # objective marker, you can re-roll the Wound roll instead." So in
            # melee the unit always re-rolls wound 1s, upgraded to a full failed-
            # wound re-roll when the target is within range of any objective marker
            # (`target.on_objective`, set per round). Melee-only — the flags below
            # apply to both modes, so the `mode == "melee"` guard is required.
            # Composes with the 1s/all variants above via OR (one re-roll per die).
            # Gated SWEG_VETERANS (default-on; `=0` reverts). Cited as
            # `simulator.veterans_of_the_long_war`.
            if (mode == "melee" and getattr(p, "veterans_of_the_long_war", False)
                    and __import__("os").environ.get("SWEG_VETERANS", "1") != "0"):
                att_reroll_wound_ones = True
                if getattr(target, "on_objective", False):
                    att_reroll_all_wounds = True

            # Adepta Sororitas Retributor Squad datasheet ability "Storm of
            # Retribution" (unconditional half). BSData v10.6.0 id
            # 8eef-f65c-7895-183f verbatim: "Each time a model in this unit
            # makes a ranged attack, re-roll a Hit roll of 1 and re-roll a
            # Wound roll of 1." Ranged-only — the `mode != "melee"` guard
            # matches the codex wording. Composes with detachment-side and
            # leader-side re-roll-ones via OR (one re-roll per die). Cited as
            # `simulator.storm_of_retribution`.
            if mode != "melee" and getattr(p, "storm_of_retribution", False):
                att_reroll_hit_ones = True
                att_reroll_wound_ones = True

            # Leagues of Votann native per-datasheet re-roll-a-Hit-roll-of-1
            # on ranged attacks (Panspectral Scanning / Panspectral Scanner /
            # Decisive Destruction). Verbatim (Wahapedia, see
            # data/rule_citations.d/votann.json simulator.votann_native_reroll_ranged):
            # Hearthkyn/Hekaton "Each time a model in this unit makes a ranged
            # attack, re-roll a Hit roll of 1." Ranged-only via mode != 'melee'.
            # Einhyr Decisive Destruction adds 'that targets the closest
            # eligible target' — DOCUMENTED APPROXIMATION: Unit.attack has no
            # closest-target signal, so we apply it unconditionally to the
            # Einhyr key (a moderate, deliberate over-credit, following the
            # established Combat Debarkation precedent). Composes by OR with
            # detachment/leader re-roll-ones (one re-roll per die).
            # `and not overwatch_attack` is required: during overwatch fire
            # re-roll of Hit 1s is suppressed (the overwatch guard above
            # zeros att_reroll_hit_ones at ~line 3517). This block sits after
            # that guard, so we must not re-set it for overwatch shots.
            # COMPLEMENTS rank 7 (Kahl [LETHAL HITS]) — a led Hearthkyn unit
            # that gains [LETHAL HITS] from the Kahl loses its native re-roll
            # under the real rules; this unconditional per-unit flag restores
            # it. ADOPTED default-on (wave 257, Votann +3.77 -> into the noise
            # band of real 48.0); SWEG_VOTANN_NATIVE_REROLL=0 is the kill-switch.
            if (
                mode != "melee"
                and getattr(p, "votann_native_reroll_ranged", False)
                and not overwatch_attack
                and __import__("os").environ.get("SWEG_VOTANN_NATIVE_REROLL", "1") != "0"
            ):
                att_reroll_hit_ones = True

            # Drukhari Power From Pain (10e codex, wave 246): the army rule
            # grants LETHAL HITS per activation by SPENDING 1 Pain token from
            # the army-level pool (army.pain_token_pool). The spend fires in
            # Battle._apply_power_from_pain_spend (greedy, per-round) and sets
            # `transient_lethal_hits` on the selected unit via
            # `_set_transient_squad`. The old passive per-unit pain_tokens
            # grant (unconditional LETHAL HITS to below-Starting-Strength
            # multi-model units) was removed in wave 246 as a fabrication.
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/
            # Route the per-weapon LETHAL HITS value by attack mode, matching
            # the SUSTAINED HITS mode-routing convention above. Pre-wave-52
            # the simulator read `p.lethal_hits` unconditionally, but that
            # field is populated from the RANGED primary weapon (see
            # `code/bsdata/mapper.py`). Reading it in melee mode fabricated
            # ranged LETHAL HITS onto every melee weapon for any unit whose
            # ranged primary carried [LETHAL HITS]. `p.melee_lethal_hits`
            # is sourced from the melee weapon and defaults to False —
            # mirrors the wave-44 iter28-MS1 melee_sustained_hits split.
            if mode == "melee":
                effective_lethal_hits = bool(p.melee_lethal_hits)
            else:
                effective_lethal_hits = bool(p.lethal_hits)
            # ST-1: per-round transient LETHAL HITS grant from stratagems that
            # actually cite [LETHAL HITS] (Wrath of the Ancestors, Power Of The
            # WAAAGH!, Archaeotech Munitions). Composes via OR with profile and
            # army-rule sources; the crit branch fires the lethal auto-wound
            # exactly once per crit-to-hit. Faction-unrestricted because the
            # stratagem dispatcher gates faction at the firing site.
            if getattr(self, "transient_lethal_hits", False):
                effective_lethal_hits = True
            # Galvanic Field (AdMech Tech-Priest Manipulus) — "While this model
            # is leading a unit, weapons equipped by models in that unit have the
            # [Lethal Hits] ability." Modelled on the ranged side here (mirroring
            # the p.lethal_hits ranged-primary field); the mode != "melee" guard
            # keeps it off melee weapons. att_buffs is composed at the top of
            # attack() (line ~1326) and host_keys gates the aura to the single
            # attached unit (Kataphron Destroyers). Cited as
            # LeaderAbility.Galvanic Field.
            if mode != "melee" and att_buffs.get("lethal_hits_ranged"):
                effective_lethal_hits = True
            # Kindred Hero (Leagues of Votann Kâhl) — "weapons equipped by
            # models in that unit have the [LETHAL HITS] ability." Melee half
            # (the ranged half is the att_buffs.get("lethal_hits_ranged") block
            # above). att_buffs is composed by effective_buffs(); host_keys
            # gates the aura to the led unit. Cited as
            # LeaderAbility.Warrior-Forged Leadership.
            if mode == "melee" and att_buffs.get("lethal_hits_melee"):
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
                    # REGIMENT leg: attacker carries the REGIMENT keyword
                    # (the codex rule's literal gate) vs non-VEHICLE/MONSTER
                    # target.  BSData v10.6.0 verbatim (Astra Militarum -
                    # Library.cat.gz, rule id b65e-c54b-b8fe-e8e2): "Each
                    # time a model in a **^^Regiment^^** unit from your army
                    # makes a ranged attack that targets a visible unit
                    # (excluding **^^Monsters^^** and **^^Vehicles^^**) that
                    # attack has the **[LETHAL HITS]** ability."
                    #
                    # Wave 243 made REGIMENT a first-class tracked keyword
                    # (BSData categoryLinks, 31 units) so the codex check is
                    # now possible.  The env gate SWEG_BORN_REGIMENT selects
                    # which keyword is used — default ON since wave 247:
                    #   unset / "1": corrected REGIMENT check — the
                    #     codex-literal gate; covers all 31 REGIMENT
                    #     datasheets (Kasrkin, Heavy Weapons Squads, Attilan
                    #     Rough Riders, etc.).
                    #   "0" (kill-switch): legacy BATTLELINE proxy
                    #     (byte-identical to pre-wave-247 behaviour — catches
                    #     only the three core Cadian / Catachan / Krieg troop
                    #     squads that carry both keywords).
                    # Read inline per-call (matching nearby gate idiom).
                    # Cited as `COMBINED_REGIMENT.am_born_soldiers_lethal_hits`.
                    _use_regiment_kw = (
                        __import__("os").environ.get("SWEG_BORN_REGIMENT", "1") != "0"
                    )
                    _regiment_attacker = (
                        "REGIMENT" in attacker_kws
                        if _use_regiment_kw
                        else "BATTLELINE" in attacker_kws
                    )
                    if (
                        _regiment_attacker
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
            # WAVE-244 melee mode-routing — TWIN-LINKED (re-roll a failed Wound
            # roll) is a per-weapon keyword. Pre-wave-244 the per-shot wound
            # loop read `p.twin_linked` (the ranged-primary field) in the Fight
            # phase too, so a unit whose ranged weapon was TWIN-LINKED (e.g. a
            # Wave Serpent's Twin Bright Lance) got a free melee wound re-roll.
            # Resolve the mode-correct value once per attack here; the per-shot
            # loop reads `_effective_twin_linked`. Mirrors the melee_lethal_hits
            # / melee_sustained_hits split.
            _effective_twin_linked = bool(
                p.melee_twin_linked if mode == "melee" else p.twin_linked
            )
            # LC1-A — generalised gate: any faction whose detachment carries
            # the `melee_sustained_hits_army_wide` flag triggers SUSTAINED
            # HITS 1 on melee. Currently only WAR_HORDE (Orks) sets this
            # flag. CUSTODES-AURIC-CHAMPIONS (claude/sim-calibration-6):
            # AURIC_CHAMPIONS previously set this flag as a fabricated proxy
            # for 'Trail of Glory'; removed — the real detachment rule is
            # 'Assemblage of Might' (CHARACTER-only + single designated
            # enemy target), which cannot be proxied by this army-wide flag
            # without fabrication. The gate remains generic so any future
            # detachment can use it once a canonical army-wide SUSTAINED
            # HITS 1 melee rule is found.
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


            # T'au Markerlights base army rule — [SUSTAINED HITS 1] vs Guided
            # targets (the +1-to-Hit half is applied in the hit-modifier block
            # above; `_tau_markerlight_guided` was computed there). Routes
            # through the shared `effective_sustained_hits` accumulator so all
            # the crit-extra-hit accounting is shared. Cited as
            # `simulator.markerlights`.
            if _tau_markerlight_guided:
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

            # ---- melee_crit_on_5_plus_hits gate (generic) ----
            # CUSTODES-KATAH-V1 (claude/sim-calibration-6): no active
            # detachment sets this flag True — it was removed from SHIELD_HOST
            # because the "Crit-on-5+ melee" was a fabricated Ka'tah stance
            # with no codex counterpart (the three real Martial Ka'tah stances
            # are Kaptaris/Rendax/Dacatarai; none grants Crit-on-5+ melee).
            # The block is retained as a no-op so any future detachment with
            # a real codex citation for "crit-on-5+ melee" can set the flag
            # True without new plumbing. Gate: mode=="melee" AND the
            # attacker's detachment carries `melee_crit_on_5_plus_hits=True`.
            melee_crit_threshold = 6   # canonical 10e: nat 6 to-hit = Critical Hit
            if mode == "melee":
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
                        if _round_c5 > 0 and _round_c5 % 2 == 0:
                            melee_crit_threshold = 5

            # SQUAD-ACTIVATION (Lever 1) — damage-allocation spillover. In 10e a
            # destroyed model's excess damage is LOST ("If a model is destroyed
            # by an attack, any excess damage inflicted by that attack is lost"),
            # but the NEXT unsaved wound is allocated to the next alive model of
            # the same unit ("if a model has already lost wounds during this
            # phase, that model must have any further wounds allocated to it").
            # So kills are bounded by the number of unsaved wounds, never the
            # damage total: 3 unsaved wounds of Damage 6 kill at most 3 one-wound
            # models. We model one Unit per model, so the target's same-squad_id
            # siblings ARE the rest of the codex unit. `_alloc_model` is the
            # current model receiving wounds; it advances only when the current
            # model dies. Lone models (squad_id < 0) have no siblings, so excess
            # is simply lost — identical to the prior behaviour. The hit/wound/
            # save rolls are still computed against `target` (all squad members
            # share one profile, so saves are identical); only the destination of
            # the damage moves. Cited as `simulator.damage_allocation_spillover`.
            # NOTE: this is NORMAL damage allocation and so it also governs
            # [DEVASTATING WOUNDS] (current 10e: a save-bypassing normal hit, NOT
            # a mortal wound — excess still lost, no cross-model spill). True
            # mortal wounds (which DO carry over) are a separate mechanic and are
            # not routed through this pointer.
            _alloc_model = target
            _alloc_siblings = None  # built lazily on first model death

            def _alloc_target():
                """Return the model the next unsaved wound is allocated to, or
                None if the whole target unit is already destroyed."""
                nonlocal _alloc_model, _alloc_siblings
                if _alloc_model is not None and _alloc_model.is_alive:
                    return _alloc_model
                sid = getattr(target, "squad_id", -1)
                if sid is None or sid < 0:
                    return None  # lone model already dead — no spill, excess lost
                if _alloc_siblings is None:
                    tgt_army = getattr(target, "army_ref", None)
                    _alloc_siblings = (
                        [u for u in tgt_army.units
                         if getattr(u, "squad_id", -1) == sid
                         and getattr(u, "embarked_in", None) is None]
                        if tgt_army is not None else []
                    )
                alive = [u for u in _alloc_siblings if u.is_alive]
                if not alive:
                    return None  # whole unit destroyed — remaining damage lost
                # Defender picks which model absorbs the next wound. When
                # alloc_next_fn is supplied (SWEG_DEFENDER_ALLOC), use the
                # defender heuristic; otherwise fall back to list order.
                # Cited as `simulator.defender_allocation`.
                next_u = alloc_next_fn(alive) if alloc_next_fn is not None else alive[0]
                _alloc_model = next_u
                return next_u

            for _ in range(n_attacks):
                # PER-MODEL-LOADOUTS (Stage 4) — roll this shot's Damage. When the
                # `SWEG_ROLLDMG` gate is set AND the active weapon carries a raw
                # dice string, `roll_damage` rolls the real dice (a D6 gun rolls
                # 1-6, not a flat 3.5); otherwise it returns `_dmg_dice_mean` and
                # draws NOTHING from `random`, so the gate-OFF / per-model-mean
                # streams stay byte-identical to legacy. The rolled value REPLACES
                # the dice-only base; any flat per-shot bonus already folded into
                # `per_shot_dmg` (Rend and Tear, Melta X) is re-added here so the
                # roll-then-modify ordering matches the mean path. `per_shot_dmg`
                # itself stays the mean for all THRESHOLD / heuristic reads
                # (high_value, the == 1.0 branch); only the applied damage rolls.
                # Fast path when the gate is off OR no dice are present (every
                # legacy / aggregate profile, the whole gate-OFF run, and the
                # per-model-MEAN run): use `per_shot_dmg` directly so the applied
                # value is BIT-identical to the mean / Stage-3 path, not merely
                # arithmetically equal (avoids any a+(b-a) floating-point ulp and
                # any random draw).
                if not (_roll_dmg_active and _dmg_dice):
                    _shot_dmg = per_shot_dmg
                else:
                    _shot_dmg = (
                        roll_damage(_dmg_dice, _dmg_dice_mean)
                        + (per_shot_dmg - _dmg_dice_mean)
                    )
                # T'au Sunforge — re-roll the Damage roll vs MONSTER/VEHICLE
                # (ranged). 10e 'you can re-roll the Damage roll': re-roll once
                # and keep the new result. We exercise the option when the first
                # roll is below the dice mean (an attacker maximises damage), so
                # the re-roll is the optional 'you can'. Only fires when the
                # gate-set _sunforge_vs_armour flag is on AND real dice were
                # rolled (flat-damage weapons draw nothing and are untouched).
                if _sunforge_vs_armour and _roll_dmg_active and _dmg_dice:
                    _dice_only = _shot_dmg - (per_shot_dmg - _dmg_dice_mean)
                    if _dice_only < _dmg_dice_mean:
                        _shot_dmg = (
                            roll_damage(_dmg_dice, _dmg_dice_mean)
                            + (per_shot_dmg - _dmg_dice_mean)
                        )
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
                    elif _chiv_hit_reroll and roll < hit_target:
                        # Code Chivalric: spend the single per-activation Hit
                        # re-roll on the first failed die of this activation.
                        roll = random.randint(1, 6)
                        unmodified_roll = roll
                        _chiv_hit_reroll = False
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
                        if (
                            own_army is not None
                            and own_army.has_fate_dice()
                            # AELDARI-AUDIT-V1: squad-level hit gate. Strands
                            # of Fate "each time a unit is selected to make a
                            # Hit Roll" is a UNIT-level event — one substitution
                            # per codex unit per round (one squad = one unit).
                            # The simulator instantiates each model as a separate
                            # Unit; without this gate a 10-model squad with
                            # high-damage weapons could each spend a Fate die on
                            # their individual hit rolls, draining up to 10 dice
                            # where the codex allows only 1. Block if this squad
                            # has already spent a Fate die on a Hit roll this round.
                            # task #28 squad_id re-key: key on squad_id when >= 0.
                            # Cited as `simulator.strands_of_fate`.
                            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
                            and hasattr(own_army, "unit_budget_available")
                            and own_army.unit_budget_available(
                                "fate_hit",
                                (getattr(self, "squad_id", -1) if getattr(self, "squad_id", -1) >= 0 else p.name),
                            )
                        ):
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
                                if hasattr(own_army, "mark_unit_budget"):
                                    _fate_hit_key = (
                                        getattr(self, "squad_id", -1)
                                        if getattr(self, "squad_id", -1) >= 0
                                        else p.name
                                    )
                                    own_army.mark_unit_budget("fate_hit", _fate_hit_key)
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
                        # SOROR-AOF-PER-PHASE: use phase flag when gate ON,
                        # round flag on legacy path (byte-identical when OFF).
                        and not (self.aof_used_this_phase if _aof_per_phase else self.aof_used_this_round)
                    ):
                        own_army = getattr(self, "army_ref", None)
                        if (
                            own_army is not None
                            and own_army.has_miracle_dice()
                            # SOROR-ACTS-OF-FAITH-V1 / task #28: squad_id re-key
                            and own_army.aof_squad_available(p.name, getattr(self, "squad_id", -1))
                        ):
                            sub = own_army.pop_miracle_die_meeting(hit_target)
                            if sub is not None:
                                roll = sub
                                attack_aof_substitution_used = True
                                # SOROR-AOF-PER-PHASE: set phase flag (gate ON) or round flag.
                                if _aof_per_phase:
                                    self.aof_used_this_phase = True
                                else:
                                    self.aof_used_this_round = True  # SOROR-DIAG-4
                                own_army.aof_squad_mark_used(p.name, getattr(self, "squad_id", -1))  # SOROR-ACTS-OF-FAITH-V1
                    # Fire Overwatch (10e core stratagem): "each time a model in
                    # that unit makes a ranged attack, an unmodified Hit roll of
                    # 6 is required for it to score a hit" — i.e. an unmodified
                    # 1-5 ALWAYS fails, irrespective of the model's Ballistic
                    # Skill or any to-hit modifier. Gated on the unmodified
                    # physical die (faction substitutions set `roll` but never
                    # `unmodified_roll`, so a substituted die cannot satisfy the
                    # nat-6 requirement, matching the rule's "unmodified" wording).
                    # An unmodified 6 falls through to the standard crit-on-hit
                    # path below, so Sustained / Lethal Hits still resolve on it.
                    # See `simulator.fire_overwatch`.
                    if overwatch_attack and unmodified_roll != 6:
                        continue   # overwatch: only an unmodified 6 hits
                    # CORE-RULES-AUDIT (2026-05-31): Indirect Fire — when firing
                    # at a target the bearer cannot see, an unmodified Hit roll
                    # of 1-3 ALWAYS fails (in addition to the -1 to Hit). Applied
                    # on the unmodified physical die (post-reroll). Previously
                    # only the -1 was modelled, over-rating indirect/artillery.
                    # See docs/CORE_RULES_AUDIT.md #3.
                    if indirect_fire_attack and unmodified_roll <= 3:
                        continue   # indirect 1-3 auto-fail
                    # CORE-RULES-AUDIT (2026-05-31): an unmodified Hit roll of 6
                    # is ALWAYS a hit (a Critical Hit), even when modifiers push
                    # the to-hit target to 7+ (a base 6+ profile under -1).
                    # Previously `roll < hit_target` with hit_target clamped at 7
                    # made a natural 6 miss. See docs/CORE_RULES_AUDIT.md #6.
                    if unmodified_roll != 6 and roll < hit_target:
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
                        elif _chiv_wound_reroll and wroll < _shot_wound_target:
                            # Code Chivalric: spend the single per-activation
                            # Wound re-roll on the first failed die.
                            wroll = random.randint(1, 6)
                            unmodified_wroll = wroll
                            rerolled = True
                            _chiv_wound_reroll = False
                        wound_succeeded = (wroll >= _shot_wound_target)
                        # WAVE-244 — mode-routed TWIN-LINKED (computed once per
                        # attack above as `_effective_twin_linked`).
                        if not wound_succeeded and _effective_twin_linked and not rerolled:
                            wroll = random.randint(1, 6)
                            unmodified_wroll = wroll
                            wound_succeeded = (wroll >= _shot_wound_target)
                            rerolled = True
                        # Universal Core Stratagem — Command Re-Roll (1 CP):
                        # if the wound roll is still a miss AND no re-roll has
                        # already been used on this die AND our army's battle
                        # reference has a stratagem hook AND the heuristic
                        # green-lights the spend, re-roll once more.
                        # Fire Overwatch suppresses the auto Command Re-Roll: an
                        # overwatch shot is already a Command-Point-funded action
                        # fired out of sequence, and stacking a second Command
                        # Point onto its wound roll would double-spend the
                        # army's economy on one overwatch volley. Cited as
                        # `simulator.fire_overwatch`.
                        if (
                            not wound_succeeded and not rerolled
                            and not overwatch_attack
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
                        # SOROR-AOF-PER-PHASE: phase flag (gate ON) or round flag.
                        and not (self.aof_used_this_phase if _aof_per_phase else self.aof_used_this_round)
                    ):
                        own_army = getattr(self, "army_ref", None)
                        if (
                            own_army is not None
                            and own_army.has_miracle_dice()
                            # SOROR-ACTS-OF-FAITH-V1 / task #28: squad_id re-key
                            and own_army.aof_squad_available(p.name, getattr(self, "squad_id", -1))
                        ):
                            sub = own_army.pop_miracle_die_meeting(_shot_wound_target)
                            if sub is not None:
                                wroll = sub
                                wound_succeeded = True
                                crit_wound = False
                                attack_aof_substitution_used = True
                                # SOROR-AOF-PER-PHASE: set phase flag (gate ON) or round flag.
                                if _aof_per_phase:
                                    self.aof_used_this_phase = True
                                else:
                                    self.aof_used_this_round = True  # SOROR-DIAG-4
                                own_army.aof_squad_mark_used(p.name, getattr(self, "squad_id", -1))  # SOROR-ACTS-OF-FAITH-V1
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
                    # CSM Possessed "Unholy Bloodshed" (10e datasheet ability): once
                    # per battle, when this unit makes a Dark Pact, until the end of
                    # the phase, weapons equipped by models in this unit have the
                    # [DEVASTATING WOUNDS] ability. Applied as transient_devastating_wounds
                    # in simulator._apply_dark_pacts; gated SWEG_CSM_ABILITIES.
                    # Cited as `simulator.csm_unholy_bloodshed`.
                    _transient_dw = getattr(self, "transient_devastating_wounds", False)
                    # WAVE-244 melee mode-routing — DEVASTATING WOUNDS is a
                    # per-weapon keyword. Pre-wave-244 this read `p.devastating_wounds`
                    # (the ranged-primary field) in the Fight phase too, so a
                    # ranged DEVASTATING WOUNDS weapon (Daemonettes' contamination
                    # case is the inverse — a melee-only DW that was correctly
                    # sourced) leaked the save-bypass crit-wound onto melee. Read
                    # the melee-side field + its basket fraction when mode ==
                    # "melee". The leader-aura (`_leader_dw_melee`) and Dark-Pact
                    # (`_transient_dw`) grants are already melee-scoped and
                    # compose via OR. Mirrors the melee_lethal_hits split.
                    _profile_dw = (
                        p.melee_devastating_wounds if mode == "melee"
                        else p.devastating_wounds
                    )
                    effective_dw = _profile_dw or _leader_dw_melee or _transient_dw
                    _profile_dw_fraction = (
                        getattr(p, "melee_devastating_wounds_basket_fraction", 1.0)
                        if mode == "melee"
                        else getattr(p, "devastating_wounds_basket_fraction", 1.0)
                    )
                    _dw_fraction = (
                        1.0 if (_leader_dw_melee or _transient_dw) and not _profile_dw
                        else float(_profile_dw_fraction or 1.0)
                    )
                    if (
                        effective_dw
                        and crit_wound
                        and random.random() < _dw_fraction
                    ):
                        # NECRONS-CTAN: Necrodermis halves Damage characteristic
                        # (rounding up); D1 attacks deal 0. Wahapedia C'tan
                        # datasheet ability. Cited as `UnitProfile.necrodermis`.
                        # PER-MODEL-LOADOUTS (Stage 4): apply the halving to the
                        # ROLLED per-shot damage (10e: roll the Damage, THEN
                        # modify). `_shot_dmg` == `per_shot_dmg` when the gate is
                        # off / no dice, so the mean path is unchanged.
                        _dw_dmg = _shot_dmg
                        if target.profile.necrodermis:
                            if _dw_dmg <= 1.0:
                                _dw_dmg = 0.0
                            else:
                                _dw_dmg = math.ceil(_dw_dmg / 2.0)
                            _dw_dmg = max(0.0, _dw_dmg)
                        _dw_m = _alloc_target()
                        if _dw_m is not None:
                            _dw_m.receive_damage(_dw_dmg, bonus_fnp=tgt_fnp_buff)
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
                            if (
                                tgt_army is not None
                                and tgt_army.has_fate_dice()
                                # AELDARI-AUDIT-V1: squad-level save gate. Strands
                                # of Fate "each time a unit makes a Saving Throw"
                                # is a UNIT-level event — one substitution per
                                # codex unit per round. Without this gate, a
                                # 10-model squad (10 Unit instances) all defending
                                # against a high-damage weapon could each spend a
                                # Fate die on their individual save rolls, draining
                                # up to 10 dice where the codex allows only 1.
                                # task #28 squad_id re-key: key on squad_id when >= 0.
                                # Cited as `simulator.strands_of_fate`.
                                and hasattr(tgt_army, "unit_budget_available")
                                and tgt_army.unit_budget_available(
                                    "fate_save",
                                    (getattr(target, "squad_id", -1) if getattr(target, "squad_id", -1) >= 0 else target.profile.name),
                                )
                            ):
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
                                    if hasattr(tgt_army, "mark_unit_budget"):
                                        _fate_save_key = (
                                            getattr(target, "squad_id", -1)
                                            if getattr(target, "squad_id", -1) >= 0
                                            else target.profile.name
                                        )
                                        tgt_army.mark_unit_budget("fate_save", _fate_save_key)
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
                            # SOROR-AOF-PER-PHASE: phase flag (gate ON) or round flag.
                            and not (target.aof_used_this_phase if _aof_per_phase else target.aof_used_this_round)
                        ):
                            tgt_army = getattr(target, "army_ref", None)
                            if (
                                tgt_army is not None
                                and tgt_army.has_miracle_dice()
                                # SOROR-ACTS-OF-FAITH-V1 / task #28: squad_id re-key
                                and tgt_army.aof_squad_available(target.profile.name, getattr(target, "squad_id", -1))
                            ):
                                sub = tgt_army.pop_miracle_die_meeting(save_target)
                                if sub is not None:
                                    sroll = sub
                                    attack_aof_substitution_used = True
                                    # SOROR-AOF-PER-PHASE: set phase flag (gate ON) or round flag.
                                    if _aof_per_phase:
                                        target.aof_used_this_phase = True
                                    else:
                                        target.aof_used_this_round = True  # SOROR-DIAG-4
                                    tgt_army.aof_squad_mark_used(target.profile.name, getattr(target, "squad_id", -1))  # SOROR-ACTS-OF-FAITH-V1
                        if sroll >= save_target:
                            continue   # saved
                    # NECRONS-CTAN: Necrodermis halves Damage characteristic
                    # (rounding up); D1 attacks deal 0. Wahapedia C'tan
                    # datasheet ability. Cited as `UnitProfile.necrodermis`.
                    # PER-MODEL-LOADOUTS (Stage 4): apply the halving to the ROLLED
                    # per-shot damage (10e: roll the Damage, THEN modify). When the
                    # gate is off / no dice, `_shot_dmg` == `per_shot_dmg`, so the
                    # mean path is unchanged.
                    _alloc_dmg = _shot_dmg
                    if target.profile.necrodermis:
                        if _alloc_dmg <= 1.0:
                            _alloc_dmg = 0.0
                        else:
                            _alloc_dmg = math.ceil(_alloc_dmg / 2.0)
                        _alloc_dmg = max(0.0, _alloc_dmg)
                    _alloc_m = _alloc_target()
                    if _alloc_m is not None:
                        _alloc_m.receive_damage(_alloc_dmg, bonus_fnp=tgt_fnp_buff)
                        total_damage += _alloc_dmg

        # ---- Hazardous: d6 after firing; on a 1, take 3 mortal wounds ----
        # Fires when the weapon's static hazardous flag is set, OR when the
        # transient_hazardous flag is active (granted by Daemonic Ordnance for
        # the current shooting activation, ranged mode only).
        _hazardous_ranged = getattr(self, "transient_hazardous", False) and mode != "melee"
        if p.hazardous or _hazardous_ranged:
            if random.randint(1, 6) == 1:
                self.receive_damage(3.0)

        # MELEE/RANGED output split instrument (#86, gated SWEG_MODE_INSTR,
        # read-only): per attacker-faction damage dealt, split by mode — to test
        # whether World Eaters' melee output is over-credited per point vs the
        # field's melee armies (the last cheap over-side probe before the
        # displacement re-model fork).
        if total_damage > 0 and __import__("os").environ.get("SWEG_MODE_INSTR"):
            _mfac = (self.profile.faction or "?") or "?"
            _mk = "melee" if mode == "melee" else "ranged"
            _md = MODE_STATS.setdefault(_mfac, {"melee": 0.0, "ranged": 0.0})
            _md[_mk] += total_damage

        return total_damage

    def __repr__(self) -> str:
        return f"{self.profile.name}({self.current_health:.1f}/{self.profile.health}hp)"


# ---------------------------------------------------------------------------
# PER-MODEL-LOADOUTS (Stage 2) — hashable flatten / inverse unflatten
# ---------------------------------------------------------------------------
#
# UnitProfile is a frozen dataclass used as an lru_cache key, so every field
# must be hashable — a list-of-dicts cannot be carried directly. The mapper's
# `model_loadouts` is a list of per-model dicts shaped
#   {"name": str, "count": float, "ranged": [wdict, ...], "melee": [wdict, ...]}
# where each `wdict` is a flat dict of scalar weapon fields plus the nested
# dict-valued `anti_keywords`. `_flatten_model_loadouts` turns that into a
# tuple-of-tuples (mirroring the extra_ranged_profiles flatten trick, one level
# deeper) so it can live on the frozen dataclass; `_unflatten_model_loadouts`
# is the exact inverse Stage 3 will call to rebuild the list-of-dicts and fire
# each model's real loadout. The round-trip is lossless: ints stay ints, floats
# stay floats, the empty anti_keywords dict comes back as `{}`.
#
# The two model-level list fields ("ranged", "melee") are recursed into; every
# OTHER model-level value (name, count) and every weapon-dict value is carried
# as-is, except a dict value (anti_keywords) which is flattened to a tuple of
# its sorted items and reconstructed by name on the way back.

# Weapon-dict keys whose value is itself a dict (so it must be flattened to a
# tuple of items for hashability and rebuilt to a dict on unflatten). Only
# `anti_keywords` qualifies in the current mapper output; listing it explicitly
# keeps the round-trip unambiguous rather than guessing from value shape.
_MODEL_LOADOUT_DICT_WEAPON_FIELDS = ("anti_keywords",)
# Model-level keys whose value is a LIST of weapon dicts (recursed into).
_MODEL_LOADOUT_WEAPON_LISTS = ("ranged", "melee")


def _flatten_weapon_dict(wdict: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    """Flatten one weapon dict to a sorted tuple of (key, value) pairs.

    Any dict-valued field (anti_keywords) becomes a tuple of its sorted items
    so the result is fully hashable. All other (scalar) values are carried
    verbatim, preserving their type (int vs float vs str vs bool).
    """
    out = []
    for k in sorted(wdict):
        v = wdict[k]
        if isinstance(v, dict):
            out.append((k, tuple(sorted(v.items()))))
        else:
            out.append((k, v))
    return tuple(out)


def _unflatten_weapon_dict(flat: Tuple[Tuple[str, Any], ...]) -> Dict[str, Any]:
    """Inverse of `_flatten_weapon_dict` — rebuild the original weapon dict.

    Fields listed in `_MODEL_LOADOUT_DICT_WEAPON_FIELDS` (anti_keywords) are
    rebuilt from their tuple-of-items back into a dict; everything else is
    carried verbatim.
    """
    out: Dict[str, Any] = {}
    for k, v in flat:
        if k in _MODEL_LOADOUT_DICT_WEAPON_FIELDS:
            out[k] = {ik: iv for ik, iv in v}
        else:
            out[k] = v
    return out


def _flatten_model_loadouts(
    list_of_dicts: Optional[List[Dict[str, Any]]],
) -> Tuple[Tuple[Tuple[str, Any], ...], ...]:
    """Flatten a `model_loadouts` list-of-dicts into a hashable tuple-of-tuples.

    Each per-model dict {name, count, ranged:[...], melee:[...]} becomes a
    sorted tuple of (key, value) pairs; the `ranged` / `melee` weapon-dict
    lists become tuples of flattened-weapon-dict tuples. `None` / empty → ().
    """
    out = []
    for model in (list_of_dicts or ()):
        pairs = []
        for k in sorted(model):
            v = model[k]
            if k in _MODEL_LOADOUT_WEAPON_LISTS:
                pairs.append((k, tuple(_flatten_weapon_dict(w) for w in (v or ()))))
            else:
                pairs.append((k, v))
        out.append(tuple(pairs))
    return tuple(out)


def _unflatten_model_loadouts(
    flattened: Tuple[Tuple[Tuple[str, Any], ...], ...],
) -> List[Dict[str, Any]]:
    """Inverse of `_flatten_model_loadouts` — rebuild the list-of-dicts.

    Exact round-trip: `_unflatten_model_loadouts(_flatten_model_loadouts(x))`
    reproduces `x` (same keys, same value types, same nested shape). Stage 3
    calls this to read a unit's real per-model loadout off the UnitProfile.
    """
    out: List[Dict[str, Any]] = []
    for model in (flattened or ()):
        d: Dict[str, Any] = {}
        for k, v in model:
            if k in _MODEL_LOADOUT_WEAPON_LISTS:
                d[k] = [_unflatten_weapon_dict(w) for w in v]
            else:
                d[k] = v
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# PER-MODEL-LOADOUTS (Stage 3) — loadout weapon-dicts → UnitProfile fields
# ---------------------------------------------------------------------------
#
# Stage 3 fires each model's OWN loadout. `add_squad` instantiates one Unit per
# model and replaces only the weapon fields of the shared aggregate profile with
# that model's real weapons. These helpers do the conversion:
#
#   _flatten_extra_profiles(list_of_dicts) — flatten a list of weapon-dicts into
#       the exact hashable tuple-of-(key, value) shape that
#       `extra_ranged_profiles` / `extra_melee_profiles` use on UnitProfile. This
#       is the SAME flatten the catalogue builder applies to the mapper's extra
#       profiles; both call sites share it so the loadout-derived extras are
#       byte-identical to mapper-derived ones (the `_profiles_to_fire` picker and
#       the additive-melee loop read them with `dict(extra)`).
#
#   _loadout_entry_to_weapon_fields(entry) — turn ONE per-model loadout entry
#       ({name, count, ranged:[wdict], melee:[wdict]}) into the dict of
#       `dataclasses.replace(profile, **fields)` keyword arguments that re-point
#       a model-Unit at its real weapons: the best ranged weapon by expected
#       value becomes the primary block, every other ranged weapon becomes an
#       `extra_ranged_profiles` entry (the picker groups them by weapon root, so
#       mutually-exclusive alt-modes still fire one mode); the best melee weapon
#       becomes the primary melee block, the rest become additive
#       `extra_melee_profiles`. Damage stays at the MEAN this stage (no dice are
#       rolled), so the structural firing change is measured in isolation.
#
#   _distribute_squad_slots(loadouts, size) — map the per-model loadout entries
#       (whose counts are for the MAX squad) onto `size` model slots via the
#       largest-remainder (Hamilton) method.

# Primary RANGED weapon fields written by _loadout_entry_to_weapon_fields. Every
# secondary_* field is cleared (set empty / zero) because a per-model profile
# carries its full weapon list in the primary + extra_ranged_profiles; the
# legacy secondary block is the aggregate-squad two-profile picker, which a
# single model never uses.
_PERMODEL_SECONDARY_RANGED_RESET: Dict[str, Any] = {
    "secondary_attacks": 0,
    "secondary_weapon_damage_per_shot": 0.0,
    "secondary_hit_probability": 0.0,
    "secondary_ap": 0,
    "secondary_strength": 4,
    "secondary_range_inches": 0,
    "secondary_weapon": "",
    "secondary_anti_keywords": (),
    "secondary_lethal_hits": False,
    "secondary_sustained_hits": 0,
    "secondary_twin_linked": False,
    "secondary_devastating_wounds": False,
    "secondary_rapid_fire": 0,
    "secondary_melta": 0,
    "secondary_ignores_cover": False,
    "secondary_heavy": False,
    "secondary_assault": False,
    "secondary_torrent": False,
    "secondary_blast": False,
    "secondary_pistol": False,
    # SEC-KEYWORD-PARITY — new fields; cleared to False on the per-model path
    # (per-model units reset the secondary block entirely; the keywords default
    # False which is safe for all four: no once-per-battle gating, no self-harm,
    # no line-of-sight exemption, no precision bypass).
    "secondary_one_shot": False,
    "secondary_hazardous": False,
    "secondary_indirect_fire": False,
    "secondary_precision": False,
}


def _flatten_extra_profiles(
    list_of_dicts: Optional[List[Dict[str, Any]]],
) -> Tuple[Tuple[Tuple[str, Any], ...], ...]:
    """Flatten a list of weapon-dicts into the hashable tuple-of-(key, value)
    shape carried by `extra_ranged_profiles` / `extra_melee_profiles`.

    Mirrors the exact flatten the catalogue builder applies to the mapper's
    extra profiles (any dict-valued field, e.g. anti_keywords, becomes a tuple
    of its sorted items; every other value is carried verbatim). `_build_catalog`
    and the Stage-3 loadout path both call this so a loadout-derived extra is
    indistinguishable from a mapper-derived one downstream.
    """
    return tuple(
        tuple(
            (k, (tuple(sorted(v.items())) if isinstance(v, dict) else v))
            for k, v in prof.items()
        )
        for prof in (list_of_dicts or ())
    )


def _ranged_weapon_ev(w: Dict[str, Any]) -> float:
    """Expected-value proxy for ranking a model's ranged weapons: attacks ×
    damage-per-shot × hit-probability (means; no dice rolled this stage)."""
    return (
        max(0.0, float(w.get("attacks", 0) or 0))
        * max(0.0, float(w.get("weapon_damage_per_shot", 0.0) or 0.0))
        * max(0.0, float(w.get("hit_probability", 0.0) or 0.0))
    )


def _melee_weapon_ev(w: Dict[str, Any]) -> float:
    """Expected-value proxy for ranking a model's melee weapons — same shape as
    the ranged proxy (the loadout melee dicts carry attacks/damage/hit too)."""
    return _ranged_weapon_ev(w)


def _loadout_entry_to_weapon_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ONE per-model loadout entry to the weapon-only field overrides for
    `dataclasses.replace(profile, **fields)`.

    The best ranged weapon (highest expected value) becomes the primary ranged
    block; the rest become `extra_ranged_profiles`. The best melee weapon becomes
    the primary melee block; the rest become additive `extra_melee_profiles`.
    No ranged weapons → `attacks=0` (and range 0, so the model finds no shooting
    target). No melee weapons → `melee_attacks=0`. Damage stays at the MEAN.
    """
    fields: Dict[str, Any] = {}

    # ---- RANGED -------------------------------------------------------------
    ranged = list(entry.get("ranged") or [])
    # Stable sort by descending expected value; ties keep loadout order so the
    # result is deterministic under PYTHONHASHSEED=0.
    ranged_ranked = sorted(ranged, key=_ranged_weapon_ev, reverse=True)
    fields.update(_PERMODEL_SECONDARY_RANGED_RESET)
    if ranged_ranked:
        best = ranged_ranked[0]
        ak = best.get("anti_keywords")
        fields.update({
            "weapon": str(best.get("weapon", "") or ""),
            "attacks": max(1, int(round(best.get("attacks", 1) or 1))),
            "weapon_damage_per_shot": float(
                best.get("weapon_damage_per_shot", 0.0) or 0.0
            ),
            # PER-MODEL-LOADOUTS (Stage 4): carry the raw Damage dice string so
            # Unit.attack can roll it per shot under SWEG_ROLLDMG. "" = use the
            # mean. The extra_ranged_profiles entries already carry damage_dice
            # via _flatten_extra_profiles (the loadout weapon-dicts include it).
            "damage_dice": str(best.get("damage_dice", "") or ""),
            "hit_probability": float(best.get("hit_probability", 0.0) or 0.0),
            "ap": int(best.get("ap", 0) or 0),
            "strength": int(best.get("strength", BASELINE_STRENGTH)
                            or BASELINE_STRENGTH),
            "range_inches": int(best.get("range_inches", 0) or 0),
            "lethal_hits": bool(best.get("lethal_hits", False)),
            "sustained_hits": int(best.get("sustained_hits", 0) or 0),
            "twin_linked": bool(best.get("twin_linked", False)),
            "devastating_wounds": bool(best.get("devastating_wounds", False)),
            "rapid_fire": int(best.get("rapid_fire", 0) or 0),
            "melta": int(best.get("melta", 0) or 0),
            "ignores_cover": bool(best.get("ignores_cover", False)),
            "heavy": bool(best.get("heavy", False)),
            "assault": bool(best.get("assault", False)),
            "torrent": bool(best.get("torrent", False)),
            "blast": bool(best.get("blast", False)),
            "pistol": bool(best.get("pistol", False)),
            # LOADOUT-FLAG-PARITY (wave 243): these three were silently dropped
            # from the promoted primary block, so the model kept whatever the
            # catalogue top-level (expected-value-picked) weapon had — e.g. the
            # Wyvern's promoted quad stormshard mortar lost Indirect Fire, and
            # Rhinos whose hunter-killer missile set top-level one_shot=True
            # fired their promoted storm bolter once per battle.
            "indirect_fire": bool(best.get("indirect_fire", False)),
            "one_shot": bool(best.get("one_shot", False)),
            "precision": bool(best.get("precision", False)),
            # Two flags are DELIBERATELY not copied (explicit-default rule):
            # - lance: the top-level UnitProfile field is MELEE semantics
            #   ("+1 to wound in melee if the unit charged"); every per-model
            #   ranged dict carries lance=False, which would clobber a real
            #   melee-derived True (Venatari lances, Achillus dreadspear).
            # - hazardous: choice-profile over-collection means a supercharge
            #   profile still fires from extra_ranged_profiles, so clearing
            #   the top-level flag would under-count real self-harm.
            "anti_keywords": (
                tuple(ak.items()) if isinstance(ak, dict) else tuple(ak or ())
            ),
            "extra_ranged_profiles": _flatten_extra_profiles(ranged_ranked[1:]),
        })
    else:
        # No ranged weapon on this model: zero shots, zero range so the
        # shooting-target search never selects it. weapon_damage_per_shot 0 too
        # so `per_shot_damage` derives 0 even if a shot were forced.
        fields.update({
            "weapon": "",
            "attacks": 0,
            "weapon_damage_per_shot": 0.0,
            "damage_dice": "",
            "hit_probability": 0.0,
            "range_inches": 0,
            "extra_ranged_profiles": (),
        })

    # ---- MELEE --------------------------------------------------------------
    melee = list(entry.get("melee") or [])
    melee_ranked = sorted(melee, key=_melee_weapon_ev, reverse=True)
    if melee_ranked:
        best_m = melee_ranked[0]
        # Wave-244 — the promoted per-model melee weapon's ANTI-X is stored as a
        # dict in the loadout weapon dict; convert to the tuple-of-tuples form
        # UnitProfile expects (dataclasses.replace sets the field directly, no
        # later conversion). Mirrors the ranged `ak` handling above.
        mak = best_m.get("anti_keywords")
        fields.update({
            "melee_weapon": str(best_m.get("weapon", "") or ""),
            "melee_attacks": max(1, int(round(best_m.get("attacks", 1) or 1))),
            "melee_damage_per_shot": float(
                best_m.get("weapon_damage_per_shot", 0.0) or 0.0
            ),
            # PER-MODEL-LOADOUTS (Stage 4): raw melee Damage dice for SWEG_ROLLDMG.
            "melee_damage_dice": str(best_m.get("damage_dice", "") or ""),
            "melee_hit_probability": float(
                best_m.get("hit_probability", 0.0) or 0.0
            ),
            "melee_strength": int(best_m.get("strength", BASELINE_STRENGTH)
                                  or BASELINE_STRENGTH),
            "melee_ap": int(best_m.get("ap", 0) or 0),
            "melee_sustained_hits": int(best_m.get("sustained_hits", 0) or 0),
            "melee_lethal_hits": bool(best_m.get("lethal_hits", False)),
            # Wave-244 melee mode-routing — promote the melee weapon's
            # TWIN-LINKED / DEVASTATING WOUNDS / ANTI-X onto the melee-side
            # fields so the per-model firing path reads them in the Fight phase.
            # No else-block zeroing (wave-243 ranged convention): a model with no
            # melee weapon relies on the UnitProfile defaults via replace.
            "melee_twin_linked": bool(best_m.get("twin_linked", False)),
            "melee_devastating_wounds": bool(best_m.get("devastating_wounds", False)),
            "melee_anti_keywords": (
                tuple(mak.items()) if isinstance(mak, dict) else tuple(mak or ())
            ),
            "extra_melee_profiles": _flatten_extra_profiles(melee_ranked[1:]),
        })
    else:
        fields.update({
            "melee_weapon": "",
            "melee_attacks": 0,
            "melee_damage_per_shot": 0.0,
            "melee_damage_dice": "",
            "melee_hit_probability": 0.0,
            "extra_melee_profiles": (),
        })

    return fields


def _distribute_squad_slots(
    loadouts: List[Dict[str, Any]],
    size: int,
) -> List[Dict[str, Any]]:
    """Map per-model loadout entries (counts for the MAX squad) onto `size`
    model slots via the largest-remainder (Hamilton) method.

    Returns a list of exactly `size` loadout-entry references (one per model
    slot to instantiate). Deterministic under PYTHONHASHSEED=0: leftover slots
    go by largest fractional remainder, ties broken by entry name ascending.

    Rules:
      - leaders = entries whose rounded count == 1; instantiate exactly one of
        each (loadout order), capped so leaders never exceed `size`.
      - the remaining slots are distributed across the body entries in
        proportion to their counts (floor each share, hand out leftovers by
        largest remainder); if still short, pad with the largest-count body
        entry; truncate to exactly `size`.
    """
    size = max(1, int(size))
    leaders = [e for e in loadouts if int(round(e.get("count", 0) or 0)) == 1]
    body = [e for e in loadouts if int(round(e.get("count", 0) or 0)) != 1]

    slots: List[Dict[str, Any]] = []
    # One of each leader, in loadout order, capped at `size`.
    for e in leaders:
        if len(slots) >= size:
            break
        slots.append(e)

    remaining = size - len(slots)
    if remaining > 0 and body:
        total_body = sum(max(0.0, float(e.get("count", 0) or 0)) for e in body)
        if total_body <= 0:
            # Degenerate: body counts all zero — spread evenly by repeating.
            i = 0
            while len(slots) < size:
                slots.append(body[i % len(body)])
                i += 1
        else:
            shares = [
                remaining * max(0.0, float(e.get("count", 0) or 0)) / total_body
                for e in body
            ]
            floors = [int(math.floor(s)) for s in shares]
            assigned = sum(floors)
            leftover = remaining - assigned
            # Largest fractional remainder; tie-break by entry name ascending.
            order = sorted(
                range(len(body)),
                key=lambda i: (-(shares[i] - floors[i]),
                               str(body[i].get("name", ""))),
            )
            counts = list(floors)
            for i in order[:max(0, leftover)]:
                counts[i] += 1
            for e, n in zip(body, counts):
                slots.extend([e] * n)
    elif remaining > 0 and not body and leaders:
        # No body entries (e.g. an all-character loadout): pad with the
        # largest-count leader so we still reach `size`.
        pad = max(leaders, key=lambda e: float(e.get("count", 0) or 0))
        while len(slots) < size:
            slots.append(pad)

    # Pad any shortfall with the largest-count body (or any) entry; truncate
    # overshoot to exactly `size`.
    if len(slots) < size and loadouts:
        pad_pool = body or loadouts
        pad = max(pad_pool, key=lambda e: float(e.get("count", 0) or 0))
        while len(slots) < size:
            slots.append(pad)
    return slots[:size]


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
            # Wave-244 melee mode-routing — the melee-side LETHAL HITS plus the
            # five new ANTI-X / DEVASTATING WOUNDS / TWIN-LINKED fields. dict→
            # tuple-of-tuples conversion mirrors the ranged `anti_keywords`
            # below (UnitProfile must stay hashable for the lru_cache in
            # code/roles.py). melee_lethal_hits was previously absent from the
            # aggregate load path (always False); it now round-trips.
            melee_lethal_hits=entry.melee_lethal_hits,
            melee_anti_keywords=tuple(
                (k, v) for k, v in (entry.melee_anti_keywords or {}).items()
            ),
            melee_devastating_wounds=entry.melee_devastating_wounds,
            melee_twin_linked=entry.melee_twin_linked,
            melee_devastating_wounds_basket_fraction=(
                entry.melee_devastating_wounds_basket_fraction
            ),
            melee_anti_keyword_basket_fractions=tuple(
                (k, float(v))
                for k, v in (entry.melee_anti_keyword_basket_fractions or {}).items()
            ),
            twin_linked=entry.twin_linked,
            devastating_wounds=entry.devastating_wounds,
            invuln_save=entry.invuln_save,
            invuln_ranged_only=entry.invuln_ranged_only,
            # Task #92 Stage 1b: per-attack-type invuln = the mapper-parsed
            # per-attack values, combined with the invuln_ranged_only override.
            # The mapper reads "X+ ... against melee/ranged attacks" clauses
            # directly (Wyches melee 4 / ranged 6; Chaos Knights ranged-only); the
            # Imperial Knight Ion Shield is encoded unconditionally in BSData and
            # its ranged-only-ness lives in invuln_ranged_only, so suppress melee
            # to 7 (none) when that flag is set. Inert until Stage 2 reads them.
            invuln_save_ranged=entry.invuln_save_ranged,
            invuln_save_melee=(7 if entry.invuln_ranged_only else entry.invuln_save_melee),
            veterans_of_the_long_war=entry.veterans_of_the_long_war,
            csm_despoilers=entry.csm_despoilers,
            csm_unholy_bloodshed=entry.csm_unholy_bloodshed,
            storm_of_retribution=entry.storm_of_retribution,
            votann_native_reroll_ranged=entry.votann_native_reroll_ranged,
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
            murderers_cowl=entry.murderers_cowl,
            gloam_rot=entry.gloam_rot,
            necrodermis=entry.necrodermis,
            righteous_paragons=entry.righteous_paragons,
            tau_sunforge=entry.tau_sunforge,
            tau_armour_hunter=entry.tau_armour_hunter,
            tau_targeting_array=entry.tau_targeting_array,
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
            # SEC-KEYWORD-PARITY — new fields read from parsed.json; default
            # False via getattr so pre-regen entries load cleanly.
            secondary_one_shot=bool(getattr(entry, "secondary_one_shot", False)),
            secondary_hazardous=bool(getattr(entry, "secondary_hazardous", False)),
            secondary_indirect_fire=bool(getattr(entry, "secondary_indirect_fire", False)),
            secondary_precision=bool(getattr(entry, "secondary_precision", False)),
            # MAP-1: TERTIARY and beyond ranged profiles (Knight Castellan
            # 5-weapon, etc.). Stored on the CatalogEntry as a list of dicts;
            # flatten into a tuple-of-(key, value) pairs so the UnitProfile
            # dataclass stays HASHABLE (required by functools.lru_cache on
            # roles.expected_ranged_dpa et al). Any nested dict value (like
            # anti_keywords) is itself converted to a tuple of items. The
            # Stage-3 per-model loadout path reuses the SAME flattener so a
            # loadout-derived extra is byte-identical to a mapper-derived one.
            extra_ranged_profiles=_flatten_extra_profiles(
                entry.extra_ranged_profiles
            ),
            # KNIGHTS-MULTIPROFILE-2 — additional melee weapon profiles
            # (Knight Abominant balemace, Knight Rampager Reaper chainsword,
            # etc.). Same flatten-to-tuples trick as extra_ranged_profiles
            # so the UnitProfile dataclass stays HASHABLE for the lru_cache
            # decorators in code/roles.py. Cited as
            # `simulator.extra_melee_profiles`.
            extra_melee_profiles=_flatten_extra_profiles(
                entry.extra_melee_profiles
            ),
            # PER-MODEL-LOADOUTS (Stage 2 plumbing — GATE-INERT). Carry the
            # mapper's per-model loadout list onto the frozen UnitProfile,
            # flattened to a hashable nested tuple via _flatten_model_loadouts.
            # Nothing reads this for behaviour in Stage 2; it is purely carried
            # so a later stage can rebuild it with _unflatten_model_loadouts and
            # fire each model's real loadout. Empty entry → () (no per-model
            # loadout recorded).
            model_loadouts=_flatten_model_loadouts(entry.model_loadouts),
            # DAMAGED-BRACKET (task #77) — flat ints, trivially hashable. Carried
            # from the CatalogEntry; nothing reads them for behaviour until the
            # gated application stage (Stage 3, SWEG_DMGBRACKET).
            damaged_threshold=entry.damaged_threshold,
            damaged_oc_penalty=entry.damaged_oc_penalty,
            damaged_hit_penalty=entry.damaged_hit_penalty,
            damaged_attacks_penalty=entry.damaged_attacks_penalty,
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

        # TAU-BATTLESUIT-WEAPONS (default-OFF, SWEG_TAU_BATTLESUIT_WEAPONS): the
        # BSData v10.6.0 mapper drops the simultaneously-equipped battlesuit
        # weapons. Fireknife models carry plasma rifle AND missile pod but only
        # the plasma rifle is mapped; Sunforge models carry 2 fusion blasters but
        # only 1 (attacks=1) is mapped. Re-add them here, GATED, so OFF is
        # byte-identical (this whole block is skipped when the env gate is unset).
        # Faithful per data/rule_citations.d/tau_empire.json. Done in code (not
        # overrides.json) because overrides merge unconditionally and could not be
        # held behind a default-off screening gate.
        if _tau_battlesuit_weapons_enabled():
            from dataclasses import replace
            if key == "t_au_empire_crisis_fireknife_battlesuits":
                # Missile pod as a 2nd ranged profile. Distinct weapon root from
                # 'plasma rifle' under _strip_mode_suffix, so the multi-root
                # firing loop in Unit.attack fires both additively (mirrors the
                # Hammerhead multi-weapon override). damage_dice='' -> mean D2.
                _missile_pod = _flatten_extra_profiles([{
                    "weapon": "missile pod",
                    "attacks": 2,
                    "weapon_damage_per_shot": 2.0,
                    "damage_dice": "",
                    "hit_probability": 0.5,
                    "ap": -1,
                    "strength": 7,
                    "range_inches": 30,
                }])
                catalog[key] = replace(
                    catalog[key],
                    extra_ranged_profiles=(
                        catalog[key].extra_ranged_profiles + _missile_pod
                    ),
                )
            elif key == "t_au_empire_crisis_sunforge_battlesuits":
                # Second fusion blaster = double the primary fusion-blaster
                # attacks (a duplicate 'fusion blaster' extra collapses into one
                # mutex group under _strip_mode_suffix and only the higher-EV copy
                # would fire). All other fusion-blaster characteristics unchanged.
                catalog[key] = replace(catalog[key], attacks=2)
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
