"""Unit profiles and battle-instance unit class."""

from __future__ import annotations

import functools
import math
import random
from dataclasses import dataclass
from typing import Dict, Tuple

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


def save_probability(save: int, ap: int = 0, in_cover: bool = False) -> float:
    """
    Probability of passing an armour save roll on a d6.

    save:      the unit's base save characteristic (e.g. 3 means 3+)
    ap:        weapon AP modifier (negative integer, e.g. -1 degrades save by 1)
    in_cover:  cover improves save by 1 pip (e.g. 4+ → 3+), capped at 2+
    """
    effective = save - ap                       # AP-1 on a 3+ → 4+
    if in_cover:
        effective = max(2, effective - 1)       # cover: improve by 1, cap at 2+
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
    unit_keywords: Tuple[str, ...] = ()        # 10e keywords (INFANTRY, VEHICLE, etc.) for Anti-X targeting
    # Phase B — melee profile (engagement range 1"). 0 = no usable melee profile.
    melee_attacks: int = 0
    melee_damage_per_shot: float = 0.0
    melee_hit_probability: float = 0.0
    melee_strength: int = 4
    melee_ap: int = 0
    melee_weapon: str = ""
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
        return points_for(
            self.health, self.damage, self.hit_probability,
            self.ap, self.save, self.strength, self.toughness,
        )

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
        # 10e Enhancement (Warlord upgrade). Assigned to a single CHARACTER
        # per army by the army builder; None on every other unit. Read by
        # `leaders.effective_buffs` when this unit is an in-range friendly
        # CHARACTER to merge its aura flags into the attacker's buff dict.
        # See `code/enhancements.py` for the dataclass + registry.
        "enhancement",
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
        # Power From Pain (Drukhari army rule). 0 = none, 1 = active (cap).
        self.pain_tokens: int = 0
        # Cult Ambush (Genestealer Cults army rule). True means the unit is
        # waiting to land at the top of Round 1 via the simulator's reserves
        # path; cleared the moment it arrives on the battlefield. See
        # `simulator.cult_ambush` citation for the verbatim Wahapedia quote.
        self.cult_ambush_pending: bool = False
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
        # Transport bookkeeping. `passengers` is a fresh list on every Unit so
        # mutating it on one transport doesn't leak into another. `embarked_in`
        # is the carrier pointer for a passenger; both default to empty / None.
        self.passengers: list = []
        self.embarked_in = None  # type: ignore[assignment]

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

    def receive_damage(self, amount: float, bonus_fnp: int = 7) -> None:
        """
        Apply damage. If this unit has Feel No Pain X+, each point of damage
        gets a d6 roll; on X+, it's ignored. Mortal wounds applied via this
        method also get FNP'd by default (matches 10e default behaviour).

        `bonus_fnp` lets the caller pass in a transient FNP value from a
        leader aura (lower of profile.fnp and bonus_fnp wins). 7 = no aura.

        Disgustingly Resilient (Plague Company stratagem): if the target
        has `transient_minus_one_damage_taken` set for the round, subtract
        1 from the per-call damage characteristic (to a minimum of 1). The
        rule fires per-attack in the codex; receive_damage is called per
        per-shot in Unit.attack, so the floor lives here.
        """
        if self.transient_minus_one_damage_taken and amount > 0:
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
        # Drukhari Power From Pain: while the defender holds a Pain Token,
        # treat the unit as having FNP 6+ (lowest "active" target = best
        # roll). Composes with any pre-existing FNP profile / leader aura
        # by taking the lower (better) value. Faction-gated to avoid ever
        # lighting up on a non-Drukhari unit that somehow carries a token.
        if self.pain_tokens > 0 and self.profile.faction == "Drukhari":
            effective_fnp = min(effective_fnp, 6)
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

        # ---- Buff lookups (detachment + in-range leader auras) -------------
        # Attacker side: detachment passives + every in-range friendly leader
        # whose aura covers this unit (re-rolls, +1 to hit/wound).
        # Target side: detachment passives + leader auras covering the target
        # (army-wide invuln, FNP). All composed via leaders.effective_buffs().
        from .leaders import effective_buffs
        att_buffs = effective_buffs(self)
        tgt_buffs = effective_buffs(target)

        if mode == "melee" and p.melee_attacks > 0:
            # Substitute the melee stat block for this resolution
            per_shot_dmg = p.melee_damage_per_shot or 1.0
            n_attacks = max(1, int(p.melee_attacks))
            hit_target = _prob_to_target(p.melee_hit_probability)
            strength = p.melee_strength
            ap = p.melee_ap
            ignore_cover = True   # melee always ignores cover
        else:
            per_shot_dmg = p.per_shot_damage
            n_attacks = max(1, int(p.attacks))
            hit_target = None     # set below
            strength = p.strength
            ap = p.ap
            ignore_cover = p.ignores_cover

        # ---- Adeptus Custodes Shield Host — Martial Ka'tah / Martial Mastery:
        # melee AP+1 portion. Wahapedia verbatim: "Improve the Armour
        # Penetration characteristic of melee weapons equipped by ADEPTUS
        # CUSTODES models from your army with the Martial Ka'tah ability
        # by 1." Gate: mode == "melee" AND attacker faction ==
        # "Adeptus Custodes" AND detachment carries `melee_ap_plus_one`
        # (set by SHIELD_HOST). AP is encoded as 0/-1/-2/-3 — improving
        # AP by 1 makes the value MORE negative (AP-1 becomes AP-2 etc).
        # APPROXIMATION: codex picks ONE Martial Mastery bullet per round;
        # SwegHammer applies BOTH always-on (this AP+1 plus the
        # Crit-on-5+ block below). Cited as `SHIELD_HOST.melee_ap_plus_one`.
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
        wound_p = wound_probability(strength, target.profile.toughness)
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
        if att_buffs["plus_one_to_wound"]:
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
        # The army picks an imperative each Command phase; one mode gets
        # +1 to hit, the opposite mode gets -1 to hit. Cited as
        # `simulator.doctrina_imperatives`. Faction-gated on the attacker.
        if p.faction == "Adeptus Mechanicus":
            own_army = getattr(self, "army_ref", None)
            imperative = (
                getattr(own_army, "doctrina_imperative", None)
                if own_army is not None else None
            )
            if imperative == "protector":
                hit_mod_delta += 1 if mode != "melee" else -1
            elif imperative == "conqueror":
                hit_mod_delta += 1 if mode == "melee" else -1

        # ---- Heavy keyword: +1 to hit when shooting and the attacker did
        # NOT move this round. Melee never benefits.
        if p.heavy and mode != "melee" and not self.moved_this_round:
            hit_mod_delta += 1

        # ---- Big Guns Never Tire: VEHICLE / MONSTER units that shoot
        # while in engagement range pay -1 to hit. Ranged only.
        if mode != "melee" and self.shooting_in_engagement:
            hit_mod_delta -= 1

        # ---- Indirect Fire: -1 to hit when target is not visible. Ranged only.
        if p.indirect_fire and mode != "melee" and not has_los:
            hit_mod_delta -= 1

        # ---- Lance: +1 to wound when this melee attack happens on a turn
        # the attacker declared a charge.
        if p.lance and mode == "melee" and is_charging:
            wound_mod_delta += 1

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

        # ---- Anti-X: lower the crit-wound threshold against matching keywords ----
        anti_crit_threshold = 6
        if p.anti_keywords and target.profile.unit_keywords:
            target_kw = set(target.profile.unit_keywords)
            for kw, thresh in p.anti_keywords:
                if kw in target_kw and thresh < anti_crit_threshold:
                    anti_crit_threshold = thresh

        save_after_ap = target.profile.save - ap
        # Precision: a ranged shot at a CHARACTER target pierces concealment —
        # cover does not improve the save. Same effect as Ignores Cover, but
        # gated on the target's keywords.
        precision_pierces_cover = (
            p.precision
            and mode != "melee"
            and "CHARACTER" in (target.profile.unit_keywords or ())
        )
        if target.in_cover and not ignore_cover and not precision_pierces_cover:
            save_after_ap = max(2, save_after_ap - 1)
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
        # against that defender re-rolls BOTH the hit roll and the wound
        # roll. The flag composes with the existing 1s-only re-rolls but
        # the `att_reroll_all_*` branches take priority in the loop below
        # (one re-roll per die — never stacks). Cited as
        # `simulator.oath_of_moment`.
        if (
            own_army is not None
            and is_marine_faction(p.faction)
            and getattr(own_army, "oath_target_uid", None) == target.uid
        ):
            att_reroll_all_hits = True
            att_reroll_all_wounds = True

        # Fire and Fade (Aeldari Warhost stratagem) — transient
        # re-roll hit rolls of 1 on shooting attacks for the round.
        att_reroll_hits_shooting_ones = (
            mode != "melee" and getattr(self, "transient_reroll_hits_shooting", False)
        )
        if att_reroll_hits_shooting_ones:
            att_reroll_hit_ones = True

        # Drukhari Power From Pain (army rule). While the attacker holds a
        # Pain Token, treat every attack from this unit as having Lethal
        # Hits for the duration of this resolution. Faction-gated to avoid
        # ever lighting up if another codex has a same-named field someday.
        effective_lethal_hits = p.lethal_hits or (
            self.pain_tokens > 0 and p.faction == "Drukhari"
        )
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

        # ---- T'au Empire Markerlights → Guided (10e army-wide army rule).
        # While a unit is a Guided unit, its ranged weapons have the
        # [LETHAL HITS] ability. The detachment flag `lethal_hits_on_guided`
        # gates the simulator wiring (Mont'ka sets it True). The mark is
        # populated at the start of the marker-spotting army's Shooting
        # phase by Battle._run_markerlight_phase. Shooting branch only —
        # melee Guided does not exist in 10e. Composes with profile.lethal_hits
        # via OR (one re-roll branch in the loop, no double-fire).
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights
        if (
            mode != "melee"
            and not effective_lethal_hits
            and own_army is not None
            and target.uid in getattr(own_army, "guided_enemy_uids", set())
            and (p.faction or "").lower() in ("t'au empire", "tau empire")
        ):
            det = own_army.resolve_detachment()
            if det is not None and getattr(det, "lethal_hits_on_guided", False):
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
        # codex's REGIMENT / SQUADRON keywords, so we map REGIMENT →
        # attacker has INFANTRY (and not VEHICLE/MONSTER), SQUADRON →
        # attacker has VEHICLE. This captures the codex split: AM infantry
        # squads (Cadians, Krieg, Scions, Ogryns) trigger the anti-troop
        # leg; AM vehicle squadrons (Leman Russ, Rogal Dorn, Sentinels)
        # trigger the anti-armour leg. Composes with profile.lethal_hits
        # via OR (one re-roll branch in the loop, no double-fire).
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
                # REGIMENT leg: INFANTRY-keyword attacker (and not VEHICLE/
                # MONSTER) vs non-VEHICLE/MONSTER target.
                if (
                    "INFANTRY" in attacker_kws
                    and "VEHICLE" not in attacker_kws
                    and "MONSTER" not in attacker_kws
                    and not target_is_vm
                ):
                    effective_lethal_hits = True
                # SQUADRON leg: VEHICLE-keyword attacker vs VEHICLE/MONSTER
                # target.
                elif "VEHICLE" in attacker_kws and target_is_vm:
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
        if mode == "melee" and p.faction == "Orks":
            _own_army = getattr(self, "army_ref", None)
            if _own_army is not None:
                try:
                    _det = _own_army.resolve_detachment()
                except Exception:
                    _det = None
                if _det is not None and getattr(
                    _det, "melee_sustained_hits_army_wide", False,
                ):
                    effective_sustained_hits += 1

        # ---- Adeptus Custodes Shield Host — Martial Ka'tah / Martial Mastery:
        # Crit-on-5+ portion. The AP+1 portion is applied EARLIER (before
        # `save_after_ap` is computed) — see the block tagged
        # `SHIELD_HOST.melee_ap_plus_one` above. This block only sets the
        # crit threshold that gates `crit_hit = (roll == 6)` later in the
        # attack loop. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/
        # adeptus-custodes/#Shield-Host.
        # Cited as `SHIELD_HOST.melee_crit_on_5_plus_hits`.
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
                    melee_crit_threshold = 5

        total_damage = 0.0
        for _ in range(n_attacks):
            # ---- Torrent: skip the to-hit roll, attack auto-hits ----
            if p.torrent:
                crit_hit = False   # torrent has no crit-on-hit
            else:
                roll = random.randint(1, 6)
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
                elif att_reroll_hit_ones and roll == 1:
                    roll = random.randint(1, 6)
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
                        sub = own_army.pop_fate_die_meeting(hit_target)
                        if sub is not None:
                            roll = sub
                if roll < hit_target:
                    continue   # missed
                # Crit-to-hit threshold defaults to 6 (canonical 10e); the
                # Shield Host Martial Ka'tah Crit-on-5+ branch lowers it to
                # 5 for Adeptus Custodes melee attackers (see
                # `melee_crit_threshold` setup above).
                crit_hit = (roll >= melee_crit_threshold) if mode == "melee" else (roll == 6)
            n_hits = 1 + (effective_sustained_hits if crit_hit else 0)

            for hit_i in range(n_hits):
                if effective_lethal_hits and crit_hit and hit_i == 0:
                    wound_succeeded = True
                    crit_wound = False
                else:
                    wroll = random.randint(1, 6)
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
                    if att_reroll_all_wounds and wroll < wound_target:
                        wroll = random.randint(1, 6)
                        rerolled = True
                    elif att_reroll_wound_ones and wroll == 1:
                        wroll = random.randint(1, 6)
                        rerolled = True
                    wound_succeeded = (wroll >= wound_target)
                    if not wound_succeeded and p.twin_linked and not rerolled:
                        wroll = random.randint(1, 6)
                        wound_succeeded = (wroll >= wound_target)
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
                            wound_succeeded = (wroll >= wound_target)
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
                    # Cited as `weapon.anti_x`.
                    # Wahapedia: https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#ANTI-X
                    if wroll >= anti_crit_threshold:
                        wound_succeeded = True
                        crit_wound = True
                    else:
                        crit_wound = False
                if not wound_succeeded:
                    continue

                tgt_fnp_buff = int(tgt_buffs["fnp"])
                if p.devastating_wounds and crit_wound:
                    target.receive_damage(per_shot_dmg, bonus_fnp=tgt_fnp_buff)
                    total_damage += per_shot_dmg
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
                            sub = tgt_army.pop_fate_die_meeting(save_target)
                            if sub is not None:
                                sroll = sub
                    if sroll >= save_target:
                        continue   # saved
                target.receive_damage(per_shot_dmg, bonus_fnp=tgt_fnp_buff)
                total_damage += per_shot_dmg

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
            indirect_fire=entry.indirect_fire,
            one_shot=entry.one_shot,
            stealth=entry.stealth,
            lone_operative=entry.lone_operative,
            deep_strike=entry.deep_strike,
            scout_distance=entry.scout_distance,
            infiltrator=entry.infiltrator,
            fnp=entry.fnp,
            deadly_demise=entry.deadly_demise,
            firing_deck=entry.firing_deck,
            sticky_objective=entry.sticky_objective,
            resolute_will=entry.resolute_will,
            unit_keywords=tuple(entry.unit_keywords or []),
            melee_attacks=entry.melee_attacks,
            melee_damage_per_shot=entry.melee_damage_per_shot,
            melee_hit_probability=entry.melee_hit_probability,
            melee_strength=entry.melee_strength,
            melee_ap=entry.melee_ap,
            melee_weapon=entry.melee_weapon,
            range_inches=entry.range_inches,
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
