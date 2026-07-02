"""
Merge parsed BSData stats with hand-tuned overrides, producing the SwegHammer
unit catalogue.

Lookup order for each unit:
  1. data/bsdata/parsed.json — base stats derived from BSData
  2. data/overrides.json     — per-unit modifications (any subset of fields)

Overrides are keyed by the canonical slug (`key`) emitted by the mapper, e.g.
`ultramarines_tactical_squad`. They can:
  - override any stat (health, damage, hit_probability, ap, save, name)
  - flip `enabled` to gate units in or out of the catalogue
  - add `notes` for documentation

Overrides can also define units that DON'T exist in parsed.json (entirely
hand-rolled). Those entries must include all required fields.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
PARSED_PATH = REPO_ROOT / "data" / "bsdata" / "parsed.json"
OVERRIDES_PATH = REPO_ROOT / "data" / "overrides.json"
CALIBRATED_PATH = REPO_ROOT / "data" / "calibrated_points.json"
# Codex corrections layer (added wave 47): per-codex-edition file that
# corrects BSData's lag against the live errata. Distinct from
# overrides.json because corrections are *not* SwegHammer hand-tuning —
# they restore the canonical codex value when BSData hasn't caught up yet.
# Filename templated by codex_version: codex_corrections_10e.json,
# codex_corrections_11e.json (etc.) so an 11e release can be selected at
# load time without touching overrides.json. Default is 10e.
def _codex_corrections_path(codex_version: str) -> "Path":
    return REPO_ROOT / "data" / f"codex_corrections_{codex_version}.json"
DEFAULT_CODEX_VERSION = "10e"

# ---------------------------------------------------------------------------
# SWEG_DEEP_STRIKE_TRIAGE — per-unit deployment-piloting correction for fast
# Aeldari/Drukhari skimmers, transports and gunships.
#
# BSData v10.6.0 attaches the standard Core Rules "Deep Strike" infoLink
# DIRECTLY and UNCONDITIONALLY to each of these unit entries. Deep Strike is
# ALWAYS an optional player choice ("you can set it up in Reserves instead of
# on the battlefield" — never mandatory). In 10th-edition competitive play
# these fast transports/gunships are deployed on-board from Turn 1 because
# their value is Turn-1 board presence, but the simulator's faction-blind
# deploy AI (SWEG_DEPLOY_AI) routes every deep_strike=True unit to strategic
# reserves on Turn 1, breaking their doctrine (the same faction-blind
# reserve-split flagged in docs/DECISION_LEDGER.md). Clearing deep_strike=False
# for these specific units is a DEPLOYMENT-PILOTING correction expressed
# through the only input the deploy AI reads — NOT a claim they lack the
# ability (they have the real, optional Core Rules Deep Strike). The more
# faithful long-term fix is a smarter deploy AI that keeps deep_strike=True and
# chooses on-board for these units; this per-unit gate is the scoped,
# only-improves interim (a global deploy-AI change would also deploy over-pole
# factions such as Emperor's Children on-board, wrong-direction for the metric).
#
# NB an earlier draft of this comment and the citations invented ability names
# ("Webway Portal", "Webway Assault", "Phantasm", "Webway Gate") — these do NOT
# appear on any of these datasheets (0 occurrences in the Aeldari Library
# cache); the only mechanism is the standard Core Rules Deep Strike. See the
# adversarial verification at data/_deepstrike_verify_report.md.
#
# This set lists ONLY units the triage audit + adversarial verification
# confirmed as fast transports/skimmers/gunships whose competitive default is
# on-board deployment. CONSERVATIVE RULE: when uncertain, the unit is NOT in
# this set (never remove a genuine deep-strike use case). Uncertain units are
# adjudicated in data/_deepstrike_verify_report.md.
#
# Gate: SWEG_DEEP_STRIKE_TRIAGE, default-ON ("1").  Set to "0" to restore
# pre-triage behaviour byte-identically (no units are cleared).
_DEEP_STRIKE_TRIAGE_CLEAR_KEYS: frozenset = frozenset({
    # ── Drukhari ──────────────────────────────────────────────────────────
    # Skysplinter Assault deploys Raiders/Venom/Ravager on-board Turn 1 to run
    # Rain of Cruelty + the alpha-strike; reserving them Turn 1 breaks the
    # faction doctrine (data/_drukhari_strategy_investigation.md). All carry a
    # direct unconditional Core Rules Deep Strike infoLink in the Aeldari
    # Library cache. Cited in data/rule_citations.d/deep_strike_triage.json.
    "aeldari_drukhari_raider",
    "aeldari_drukhari_venom",
    "aeldari_drukhari_ravager",
    # Hellions: MOUNTED/FLY 14" objective-racers; competitive default is
    # on-board Turn-1 tempo, not deep-strike ambush.
    "aeldari_drukhari_hellions",
    # ── Ynnari (same Raider/Venom chassis, SEPARATE selectionEntries) ──────
    # Verified as distinct entries (ids 8e15-3c74-d36f-7669 / 5443-6671-baeb-77a3),
    # not shared with the Drukhari entries; same on-board competitive default.
    "aeldari_craftworlds_ynnari_raider",
    "aeldari_craftworlds_ynnari_venom",
    # ── Craftworlds ───────────────────────────────────────────────────────
    # Falcon: mobile TRANSPORT (Fire Dragons / Wraithguard delivery) deployed
    # on-board Turn 1, using Battle Focus to shoot after moving. Direct
    # unconditional Deep Strike infoLink (no "Webway Gate" ability exists on it).
    "aeldari_craftworlds_falcon",
    # ── Drukhari Legends (CLEAR-CONFIRMED by the adversarial verification) ──
    # Identical infoLink structure to the cleared Ravager (Reaper) and Raider
    # (Tantalus). Legends units — almost certainly inert in the current
    # tournament-archetype lists, cleared for completeness/faithfulness.
    "aeldari_drukhari_reaper_legends",
    "aeldari_drukhari_tantalus_legends",
})


@dataclass
class CatalogEntry:
    key: str
    name: str
    health: float
    damage: float
    hit_probability: float
    ap: int
    save: int
    codex: str = ""
    points_listed: float = 0.0
    min_models: int = 1
    max_models: int = 1
    strength: int = 4
    toughness: int = 4
    leadership: int = 7
    oc: int = 1
    attacks: int = 1
    weapon_damage_per_shot: float = 0.0
    lethal_hits: bool = False
    sustained_hits: int = 0
    # Melee-side SUSTAINED HITS — sourced from the best-legal MELEE weapon by
    # the mapper. Routed separately from `sustained_hits` (ranged-side) so
    # the simulator can pick the correct value per attack mode. See
    # MappedUnit.melee_sustained_hits for the iter28-MS1 rationale.
    melee_sustained_hits: int = 0
    # Melee-side [LETHAL HITS] — present in MappedUnit / parsed.json and on
    # the per-model promotion path since wave-52, but PRE-WAVE-244 it was
    # MISSING from this CatalogEntry, so the aggregate (squad-average) load
    # path always carried melee_lethal_hits=False (only the per-model path at
    # code.units._loadout_entry_to_weapon_fields read it). Added here so the
    # aggregate path round-trips the real value. See MappedUnit.melee_lethal_hits.
    melee_lethal_hits: bool = False
    # Wave-244 melee mode-routing — ANTI-X / DEVASTATING WOUNDS / TWIN-LINKED
    # sourced from the chosen MELEE weapon, kept distinct from the ranged-side
    # fields below so the simulator can route by attack mode. Without these the
    # five melee keyword values are dead data on the aggregate path. Basket
    # fractions mirror the ranged devastating_wounds_basket_fraction /
    # anti_keyword_basket_fractions. See MappedUnit for the contamination
    # rationale.
    melee_anti_keywords: Optional[Dict[str, int]] = None
    melee_devastating_wounds: bool = False
    melee_twin_linked: bool = False
    melee_devastating_wounds_basket_fraction: float = 1.0
    melee_anti_keyword_basket_fractions: Optional[Dict[str, float]] = None
    twin_linked: bool = False
    devastating_wounds: bool = False
    invuln_save: int = 7
    invuln_ranged_only: bool = False
    invuln_save_melee: int = 7    # Task #92: per-attack invuln (default set in from_dict = invuln_save)
    invuln_save_ranged: int = 7
    # CSM Legionaries datasheet ability "Veterans of the Long War" (override-only,
    # not a mapper output). Set via overrides.json; read at the melee wound step.
    veterans_of_the_long_war: bool = False
    # CSM Chaos Terminator Squad "Despoilers" (override-only). Set via overrides.json.
    csm_despoilers: bool = False
    # CSM Possessed "Unholy Bloodshed" (override-only). Set via overrides.json.
    csm_unholy_bloodshed: bool = False
    # Adepta Sororitas Retributor Squad datasheet ability "Storm of Retribution"
    # (unconditional half, override-only). BSData v10.6.0 id 8eef-f65c-7895-183f:
    # "Each time a model in this unit makes a ranged attack, re-roll a Hit roll of 1
    # and re-roll a Wound roll of 1." Ranged-only; applies via att_reroll_hit_ones +
    # att_reroll_wound_ones in Unit.attack when mode != "melee". The escalating
    # half (+1 to Hit and +1 to Wound when attacking an enemy that killed a friendly
    # Adepta Sororitas unit) is a follow-up code build. Cited as
    # `simulator.storm_of_retribution`.
    storm_of_retribution: bool = False
    # Leagues of Votann native re-roll-Hit-roll-of-1 on ranged attacks
    # (override-only flag; not a mapper output). Models the per-datasheet
    # printed abilities Panspectral Scanning (Hearthkyn Warriors),
    # Panspectral Scanner (Hekaton Land Fortress) and Decisive Destruction
    # (Einhyr Hearthguard). Set via overrides.json; read at the ranged hit
    # step in code/units.py Unit.attack behind SWEG_VOTANN_NATIVE_REROLL.
    # Cited as `simulator.votann_native_reroll_ranged`.
    votann_native_reroll_ranged: bool = False
    rapid_fire: int = 0
    melta: int = 0
    ignores_cover: bool = False
    anti_keywords: Optional[Dict[str, int]] = None
    heavy: bool = False
    assault: bool = False
    torrent: bool = False
    hazardous: bool = False
    blast: bool = False
    # Phase F — niche 10e keywords
    lance: bool = False
    precision: bool = False
    pistol: bool = False
    # MAP-MULTIFIRE-VALIDATE — primary ranged weapon name (mapper's
    # `primary.name`). Surfaced on UnitProfile so the multi-profile picker
    # can group mode-alternates by stripped root name. Default "" =
    # legacy entries that predate the field.
    weapon: str = ""
    # MAP-MULTIFIRE-VALIDATE — pistol flag on the SECONDARY ranged weapon
    # profile (the primary's flag lives in `pistol` above). 10e Pistol
    # exclusivity is enforced in the picker; this flag tells the picker
    # whether the secondary belongs to the pistol group or the non-pistol
    # group of this chassis.
    secondary_pistol: bool = False
    indirect_fire: bool = False
    one_shot: bool = False
    # Phase H — Stealth (-1 to be hit)
    stealth: bool = False
    # Lone Operative (10e core ability) — can only be targeted by ranged
    # attacks from within 12". Parsed from BSData "Lone Operative" infoLinks.
    lone_operative: bool = False
    # FIGHTS FIRST datasheet keyword — unit fights in the Fights First step
    # of the Fight phase. Parsed from BSData "Fights First" infoLinks /
    # inline profiles. Cited as `simulator.fights_first_keyword`.
    fights_first: bool = False
    # WAVE-260 — World Eaters "Blessings of Khorne" army-rule ability carrier.
    # True iff the datasheet carries the Blessings of Khorne infoLink. Khorne
    # Daemon allies (Bloodletters, Flesh Hounds, Bloodcrushers) read False and
    # are excluded by the gated read in Unit.attack. Default True so non-World-
    # Eaters / pre-regen profiles stay permissive (the read is faction-gated).
    # Cited as `simulator.blessings_of_khorne`.
    has_blessings_of_khorne: bool = True
    # Phase I — deployment abilities
    deep_strike: bool = False
    scout_distance: int = 0
    infiltrator: bool = False
    # Deadly Demise X — when destroyed, roll 1D6; on 6, each unit within 6"
    # suffers X mortal wounds. Integer expected-value of the codex text.
    deadly_demise: int = 0
    # Firing Deck X (10e core, TRANSPORT keyword) — up to X embarked passenger
    # models may shoot using the transport's BS in its Shooting phase. 0 = none.
    firing_deck: int = 0
    fnp: int = 7
    # 10e Sticky Objectives — control persists after the unit leaves until
    # an opposing unit takes the objective back.
    sticky_objective: bool = False
    # 10e datasheet ability — Resolute Will (Custodian Wardens). Defender-
    # side -1 to Wound roll while led by a CHARACTER AND attacker S >
    # defender T. Set per-unit via overrides.json (BSData v10.6.0 mapper
    # does not yet parse this rule out of the cache; the override is the
    # authoritative source). Cited as `simulator.resolute_will`.
    resolute_will: bool = False
    # CHAOS DAEMONS — Murderer's Cowl (Khorne army rule). BSData verbatim:
    # "This unit is eligible to shoot and declare a charge in a turn in
    # which it Advanced." Set per-unit via overrides.json. Enables the
    # charge-after-Advance exemption in simulator._do_charge.
    # Cited as `simulator.murderers_cowl`.
    murderers_cowl: bool = False
    # CHAOS DAEMONS — Gloam Rot (Nurgle army rule). BSData verbatim:
    # "Each time an attack targets this unit, if the Strength characteristic
    # of that attack is greater than this unit's Toughness characteristic,
    # subtract 1 from the Wound roll." Set per-unit via overrides.json.
    # Cited as `simulator.gloam_rot`.
    gloam_rot: bool = False
    # ADEPTA SORORITAS — Righteous Paragons (Paragon Warsuits datasheet
    # ability). Wahapedia verbatim: "Each time a model in this unit makes
    # an attack that targets a MONSTER or VEHICLE unit, add 1 to the Hit
    # roll and add 1 to the Wound roll." Set per-unit via overrides.json.
    # Cited as `simulator.righteous_paragons`.
    righteous_paragons: bool = False
    # T'AU EMPIRE — Sunforge (Crisis Sunforge Battlesuits datasheet ability).
    # Cited as `simulator.tau_sunforge`.
    tau_sunforge: bool = False
    # T'AU EMPIRE — Armour Hunter (Hammerhead Gunship datasheet ability).
    # Cited as `simulator.tau_armour_hunter`.
    tau_armour_hunter: bool = False
    # T'AU EMPIRE — Targeting Array (Hammerhead Gunship datasheet ability).
    # Cited as `simulator.tau_targeting_array`.
    tau_targeting_array: bool = False
    # T'au Riptide Nova Charge (once-per-battle [DEVASTATING WOUNDS]). Set via
    # overrides.json; gated SWEG_TAU_NOVA_CHARGE. Cited `simulator.tau_nova_charge`.
    tau_nova_charge: bool = False
    # NECRONS-CTAN — Necrodermis (C'tan datasheet ability). Halves the
    # Damage characteristic of each allocated attack (rounding up); D1
    # attacks deal 0 damage. Set per-unit via overrides.json (the BSData
    # mapper does not currently extract this datasheet ability). Cited as
    # `UnitProfile.necrodermis`.
    necrodermis: bool = False
    # MAP-4 — per-unit Reanimation Protocols eligibility flag. True iff the
    # BSData datasheet carries the "Reanimation Protocols" infoLink AND lacks
    # CHARACTER / MONSTER / VEHICLE keywords (those keywords gate the ability
    # off per the 10e codex rule). Populated by the mapper from
    # `extract_reanimates_with_army`. Necron-specific; non-Necron units stay
    # False. Cited as `simulator.reanimation_protocols`.
    reanimates_with_army: bool = False
    unit_keywords: Optional[List[str]] = None
    melee_attacks: int = 0
    melee_damage_per_shot: float = 0.0
    melee_hit_probability: float = 0.0
    melee_strength: int = 4
    melee_ap: int = 0
    melee_weapon: str = ""
    range_inches: int = 24
    # Phase 2 / iter33 — secondary RANGED weapon profile. See
    # MappedUnit.secondary_attacks for the rationale (Stormsurge Pulse Driver
    # vs Pulse Blastcannon, etc.). 0 in secondary_attacks = "no secondary".
    secondary_attacks: int = 0
    secondary_weapon_damage_per_shot: float = 0.0
    secondary_hit_probability: float = 0.0
    secondary_ap: int = 0
    secondary_strength: int = 4
    secondary_range_inches: int = 0
    secondary_weapon: str = ""
    secondary_anti_keywords: Optional[Dict[str, int]] = None
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
    # secondary profile chain. Mirrors the fix applied to extra_ranged_profiles
    # in dc4f63c. Defaults False (safe legacy behaviour for pre-regen entries).
    secondary_one_shot: bool = False
    secondary_hazardous: bool = False
    secondary_indirect_fire: bool = False
    secondary_precision: bool = False
    # MAP-1: TERTIARY and beyond ranged profiles. List of dicts, each carrying
    # the same fields as the secondary block (weapon, attacks, damage,
    # hit_probability, ap, strength, range_inches, anti_keywords, plus the
    # ranged keyword flags). Empty = no extras. See MappedUnit comment.
    extra_ranged_profiles: Optional[List[Dict[str, Any]]] = None
    # KNIGHTS-MULTIPROFILE-2: TERTIARY+ melee weapon profiles (Knight Abominant
    # Balemace, Knight Rampager Reaper chainsword, etc.). List of dicts, each
    # carrying the melee weapon-attack contract (weapon, attacks,
    # weapon_damage_per_shot, hit_probability, ap, strength, plus per-weapon
    # keyword flags: sustained_hits, lethal_hits, devastating_wounds,
    # lance, precision, twin_linked, anti_keywords). Empty / missing = no
    # extras. ADDITIVE in simulator resolution (every entry fires alongside
    # the primary melee in the same Fight phase), as distinct from the MUTEX
    # extra_ranged_profiles picker. Cited as `simulator.extra_melee_profiles`.
    extra_melee_profiles: Optional[List[Dict[str, Any]]] = None
    # PER-MODEL-LOADOUTS (Stage 1 mapper / Stage 2 plumbing) — the actual
    # per-model-type weapon loadout for this unit. List of dicts, one per
    # distinct model type in the squad, each shaped
    #   {"name": str, "count": float, "ranged": [wdict, ...], "melee": [wdict, ...]}
    # where each `wdict` carries the same scalar weapon fields as the
    # extra_ranged_profiles dicts (weapon, attacks, weapon_damage_per_shot,
    # hit_probability, ap, strength, range_inches, anti_keywords, the ranged /
    # melee keyword flags) PLUS the raw dice strings `attacks_dice` and
    # `damage_dice`. Distinct from the aggregate synthetic primary/secondary/
    # extra_* weapon blocks above (which collapse the whole squad into one
    # averaged weapon): this field preserves who-carries-what so a later stage
    # can fire each model's real loadout. GATE-INERT in Stage 2 — nothing reads
    # it for behaviour yet; it is purely carried from parsed.json → UnitProfile.
    # Empty / missing = no per-model loadout recorded (legacy entries).
    model_loadouts: Optional[List[Dict[str, Any]]] = None
    # OVERRIDE-PRECEDENCE (env-gated SWEG_OVERRIDE_MELEE_PRECEDENCE) — the
    # names of fields that data/overrides.json explicitly set for this unit
    # (the hand-tuning layer only; the codex-corrections and calibrated-points
    # layers do not count as "hand override" for this marker). Populated in
    # `load_catalog` from the raw overrides.json entry, before the three
    # layers (corrections, overrides, calibrated) are merged together, so it
    # names exactly what a human typed into overrides.json.
    #
    # This exists because the per-model-loadout builder
    # (`code.army._add_squad_per_model`) rebuilds every model-Unit's weapon
    # fields — INCLUDING `extra_melee_profiles` / `extra_ranged_profiles` —
    # straight from the mapper's `model_loadouts` data, unconditionally
    # overwriting whatever the merged CatalogEntry carried for those two
    # fields. When a hand override in overrides.json sets one of those two
    # fields to correct a mapper mis-parse (a multi-profile weapon, a
    # datasheet's second melee weapon), the per-model rebuild silently
    # discards the correction — the override still merges into the
    # UNIT_CATALOG-level UnitProfile, but every per-model Unit the army
    # actually fires with reverts to the mapper's version. Gated by
    # SWEG_OVERRIDE_MELEE_PRECEDENCE (default-off, byte-identical off): when
    # on, `_add_squad_per_model` consults this tuple and leaves any listed
    # field alone rather than overwriting it. Cited as
    # `simulator.override_melee_precedence`.
    override_field_names: Tuple[str, ...] = ()
    # DAMAGED-BRACKET (task #77) — the 10e "Damaged: 1-X Wounds Remaining"
    # datasheet bracket, carried from parsed.json. `damaged_threshold == 0` means
    # no bracket. GATE-INERT until the simulator reads it (Stage 3, gated
    # SWEG_DMGBRACKET). Penalties are the per-stat reduction while the model is at
    # 1..threshold wounds remaining.
    damaged_threshold: int = 0
    damaged_oc_penalty: int = 0
    damaged_hit_penalty: int = 0
    damaged_attacks_penalty: int = 0
    # MAP-3-FIX — basket-fraction gating for partial-coverage weapon keywords.
    # Defaults to 1.0 preserve legacy single-weapon behaviour. Heterogeneous
    # squads (Rubric Marines, Skyweavers, Beast Snagga Boyz) carry values
    # < 1.0 so Unit.attack can Bernoulli-gate keyword consumption per shot.
    devastating_wounds_basket_fraction: float = 1.0
    lance_basket_fraction: float = 1.0
    anti_keyword_basket_fractions: Optional[Dict[str, float]] = None
    # 10e Movement characteristic (inches). 0 = use UnitProfile default (6.0).
    # Most BSData datasheets don't expose M numerically to the mapper, so this
    # is typically set via overrides.json (e.g. Vertus Praetors M=14"). Cited
    # per-unit in overrides.json notes.
    move: float = 0.0
    points_override: float = 0.0
    # Renderer-only model base footprint (see UnitProfile.base_shape).
    base_shape: str = "circle"
    base_diameter_mm: int = 32
    base_width_mm: int = 32
    base_length_mm: int = 32
    loadout: Optional[List[str]] = None
    notes: str = ""
    enabled: bool = True
    skip_reason: str = ""

    @classmethod
    def from_dict(cls, d: Dict) -> "CatalogEntry":
        return cls(
            key=d["key"],
            name=d.get("name", d["key"]),
            health=float(d.get("health", 0)),
            damage=float(d.get("damage", 0)),
            hit_probability=float(d.get("hit_probability", 0)),
            ap=int(d.get("ap", 0)),
            save=int(d.get("save", 7)),
            codex=d.get("codex", ""),
            points_listed=float(d.get("points_listed", 0)),
            min_models=int(d.get("min_models", 1)),
            max_models=int(d.get("max_models", 1)),
            strength=int(d.get("strength", 4)),
            toughness=int(d.get("toughness", 4)),
            leadership=int(d.get("leadership", 7)),
            oc=int(d.get("oc", 1)),
            attacks=int(d.get("attacks", 1)),
            weapon_damage_per_shot=float(d.get("weapon_damage_per_shot", 0)),
            lethal_hits=bool(d.get("lethal_hits", False)),
            sustained_hits=int(d.get("sustained_hits", 0)),
            melee_sustained_hits=int(d.get("melee_sustained_hits", 0)),
            # Wave-244 — melee keyword mode-routing fields. Explicit inert
            # defaults (False / {} / 1.0) so any parsed.json or overrides.json
            # entry that predates the mapper regen loads cleanly with NO melee
            # keyword applied (the safe, contamination-free state). melee_lethal_hits
            # was missing entirely pre-wave-244 (aggregate path always False);
            # added here alongside the five new fields.
            melee_lethal_hits=bool(d.get("melee_lethal_hits", False)),
            melee_anti_keywords=dict(d.get("melee_anti_keywords") or {}),
            melee_devastating_wounds=bool(d.get("melee_devastating_wounds", False)),
            melee_twin_linked=bool(d.get("melee_twin_linked", False)),
            melee_devastating_wounds_basket_fraction=float(
                d.get("melee_devastating_wounds_basket_fraction", 1.0)
            ),
            melee_anti_keyword_basket_fractions=dict(
                d.get("melee_anti_keyword_basket_fractions") or {}
            ),
            twin_linked=bool(d.get("twin_linked", False)),
            devastating_wounds=bool(d.get("devastating_wounds", False)),
            invuln_save=int(d.get("invuln_save", 7)),
            invuln_ranged_only=bool(d.get("invuln_ranged_only", False)),
            # Task #92: default the per-attack invuln to the single value for old
            # parsed.json / overrides that predate these keys.
            invuln_save_melee=int(d.get("invuln_save_melee", d.get("invuln_save", 7))),
            invuln_save_ranged=int(d.get("invuln_save_ranged", d.get("invuln_save", 7))),
            veterans_of_the_long_war=bool(d.get("veterans_of_the_long_war", False)),
            csm_despoilers=bool(d.get("csm_despoilers", False)),
            csm_unholy_bloodshed=bool(d.get("csm_unholy_bloodshed", False)),
            storm_of_retribution=bool(d.get("storm_of_retribution", False)),
            votann_native_reroll_ranged=bool(d.get("votann_native_reroll_ranged", False)),
            rapid_fire=int(d.get("rapid_fire", 0)),
            melta=int(d.get("melta", 0)),
            ignores_cover=bool(d.get("ignores_cover", False)),
            anti_keywords=dict(d.get("anti_keywords") or {}),
            heavy=bool(d.get("heavy", False)),
            assault=bool(d.get("assault", False)),
            torrent=bool(d.get("torrent", False)),
            hazardous=bool(d.get("hazardous", False)),
            blast=bool(d.get("blast", False)),
            lance=bool(d.get("lance", False)),
            precision=bool(d.get("precision", False)),
            pistol=bool(d.get("pistol", False)),
            weapon=str(d.get("weapon", "")),
            secondary_pistol=bool(d.get("secondary_pistol", False)),
            indirect_fire=bool(d.get("indirect_fire", False)),
            one_shot=bool(d.get("one_shot", False)),
            stealth=bool(d.get("stealth", False)),
            lone_operative=bool(d.get("lone_operative", False)),
            fights_first=bool(d.get("fights_first", False)),
            has_blessings_of_khorne=bool(d.get("has_blessings_of_khorne", True)),
            deep_strike=bool(d.get("deep_strike", False)),
            scout_distance=int(d.get("scout_distance", 0)),
            infiltrator=bool(d.get("infiltrator", False)),
            deadly_demise=int(d.get("deadly_demise", 0)),
            firing_deck=int(d.get("firing_deck", 0)),
            fnp=int(d.get("fnp", 7)),
            sticky_objective=bool(d.get("sticky_objective", False)),
            resolute_will=bool(d.get("resolute_will", False)),
            murderers_cowl=bool(d.get("murderers_cowl", False)),
            gloam_rot=bool(d.get("gloam_rot", False)),
            righteous_paragons=bool(d.get("righteous_paragons", False)),
            tau_sunforge=bool(d.get("tau_sunforge", False)),
            tau_armour_hunter=bool(d.get("tau_armour_hunter", False)),
            tau_targeting_array=bool(d.get("tau_targeting_array", False)),
            tau_nova_charge=bool(d.get("tau_nova_charge", False)),
            necrodermis=bool(d.get("necrodermis", False)),
            reanimates_with_army=bool(d.get("reanimates_with_army", False)),
            unit_keywords=list(d.get("unit_keywords") or []),
            melee_attacks=int(d.get("melee_attacks", 0)),
            melee_damage_per_shot=float(d.get("melee_damage_per_shot", 0)),
            melee_hit_probability=float(d.get("melee_hit_probability", 0)),
            melee_strength=int(d.get("melee_strength", 4)),
            melee_ap=int(d.get("melee_ap", 0)),
            melee_weapon=d.get("melee_weapon", ""),
            range_inches=int(d.get("range_inches", 24)),
            secondary_attacks=int(d.get("secondary_attacks", 0)),
            secondary_weapon_damage_per_shot=float(d.get("secondary_weapon_damage_per_shot", 0)),
            secondary_hit_probability=float(d.get("secondary_hit_probability", 0)),
            secondary_ap=int(d.get("secondary_ap", 0)),
            secondary_strength=int(d.get("secondary_strength", 4)),
            secondary_range_inches=int(d.get("secondary_range_inches", 0)),
            secondary_weapon=d.get("secondary_weapon", ""),
            secondary_anti_keywords=dict(d.get("secondary_anti_keywords") or {}),
            secondary_lethal_hits=bool(d.get("secondary_lethal_hits", False)),
            secondary_sustained_hits=int(d.get("secondary_sustained_hits", 0)),
            secondary_twin_linked=bool(d.get("secondary_twin_linked", False)),
            secondary_devastating_wounds=bool(d.get("secondary_devastating_wounds", False)),
            secondary_rapid_fire=int(d.get("secondary_rapid_fire", 0)),
            secondary_melta=int(d.get("secondary_melta", 0)),
            secondary_ignores_cover=bool(d.get("secondary_ignores_cover", False)),
            secondary_heavy=bool(d.get("secondary_heavy", False)),
            secondary_assault=bool(d.get("secondary_assault", False)),
            secondary_torrent=bool(d.get("secondary_torrent", False)),
            secondary_blast=bool(d.get("secondary_blast", False)),
            # SEC-KEYWORD-PARITY — new fields; default False for pre-regen
            # parsed.json entries that pre-date this fix.
            secondary_one_shot=bool(d.get("secondary_one_shot", False)),
            secondary_hazardous=bool(d.get("secondary_hazardous", False)),
            secondary_indirect_fire=bool(d.get("secondary_indirect_fire", False)),
            secondary_precision=bool(d.get("secondary_precision", False)),
            # MAP-1: list of tertiary+ ranged profiles. Each is a dict mirroring
            # the secondary_* fields. Missing key = no extras (most units).
            extra_ranged_profiles=list(d.get("extra_ranged_profiles") or []),
            # KNIGHTS-MULTIPROFILE-2: list of tertiary+ MELEE profiles. Each is
            # a dict mirroring the melee weapon-attack contract. Missing key =
            # no extras (most units). See CatalogEntry.extra_melee_profiles
            # for the field-level contract.
            extra_melee_profiles=list(d.get("extra_melee_profiles") or []),
            # PER-MODEL-LOADOUTS: list of per-model-type loadout dicts. Missing
            # key = no per-model loadout recorded. Mirrors the
            # extra_ranged_profiles read convention (carried verbatim; the
            # nested ranged/melee weapon dicts are not flattened until the
            # UnitProfile build in code.units._build_catalog).
            model_loadouts=list(d.get("model_loadouts") or []),
            # OVERRIDE-PRECEDENCE — see the field comment above. Missing key =
            # empty tuple (no fields marked as hand-override-explicit; the
            # common case for parsed.json base entries, which never carry
            # this key).
            override_field_names=tuple(d.get("override_field_names") or ()),
            # DAMAGED-BRACKET (task #77) — carried verbatim from parsed.json.
            # Missing key = 0 (no bracket / legacy entries predating extraction).
            damaged_threshold=int(d.get("damaged_threshold", 0) or 0),
            damaged_oc_penalty=int(d.get("damaged_oc_penalty", 0) or 0),
            damaged_hit_penalty=int(d.get("damaged_hit_penalty", 0) or 0),
            damaged_attacks_penalty=int(d.get("damaged_attacks_penalty", 0) or 0),
            # MAP-3-FIX — parse basket fractions. Missing key = 1.0 (legacy:
            # any unit predating this change keeps full-keyword behaviour).
            devastating_wounds_basket_fraction=float(
                d.get("devastating_wounds_basket_fraction", 1.0)
            ),
            lance_basket_fraction=float(d.get("lance_basket_fraction", 1.0)),
            anti_keyword_basket_fractions=dict(
                d.get("anti_keyword_basket_fractions") or {}
            ),
            move=float(d.get("move", 0)),
            points_override=float(d.get("points_override", 0)),
            base_shape=str(d.get("base_shape", "circle")),
            base_diameter_mm=int(d.get("base_diameter_mm", 32)),
            base_width_mm=int(d.get("base_width_mm", 32)),
            base_length_mm=int(d.get("base_length_mm", 32)),
            loadout=d.get("loadout") or [],
            notes=d.get("notes", ""),
            enabled=bool(d.get("enabled", True)),
            skip_reason=d.get("skip_reason", ""),
        )


def _load_parsed() -> Dict[str, CatalogEntry]:
    if not PARSED_PATH.exists():
        return {}
    payload = json.loads(PARSED_PATH.read_text(encoding="utf-8"))
    out: Dict[str, CatalogEntry] = {}
    for u in payload.get("units", []):
        entry = CatalogEntry.from_dict(u)
        out[entry.key] = entry
    return out


def _load_overrides() -> Dict[str, Dict]:
    if not OVERRIDES_PATH.exists():
        return {}
    payload = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return payload.get("units", {})


def _load_codex_corrections(codex_version: str) -> Dict[str, Dict]:
    """Load the per-codex-edition BSData-lag corrections file.

    Layered into load_catalog BETWEEN the BSData base and the hand-tuning
    overrides.json. Two reasons for keeping it separate from
    overrides.json:

      1. Auditability — when BSData updates and the lag closes, the
         corrections entry can be retired by checking that BSData now
         carries the field at the corrected value. Mixed with
         hand-tuning entries in overrides.json this would be lost.
      2. Codex version selection — when 11e (or any subsequent edition)
         releases, a parallel codex_corrections_11e.json file pins the
         simulator to the chosen edition without rewriting overrides.json.
         Pass codex_version="11e" to load_catalog (or the eval CLI) to
         flip baselines.

    Each entry has the shape:
      "unit_key": {
        "fields": {"<field>": <value>, ...},  # applied as override
        "source": "<wahapedia URL>",
        "errata": "<change description>",
        "bsdata_was": {"<field>": <stale value>}  # audit aid
      }

    Returns a flat {unit_key: fields_dict} suitable for the same
    `_apply_override` merge path used by overrides / calibrated.
    Metadata keys (source, errata, bsdata_was, notes) are stripped.
    Silent no-op if the corrections file doesn't exist.
    """
    path = _codex_corrections_path(codex_version)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, Dict] = {}
    for key, record in payload.get("corrections", {}).items():
        fields = record.get("fields") or {}
        if not fields:
            continue
        out[key] = dict(fields)
    return out


def _load_calibrated_overrides() -> Dict[str, Dict]:
    """
    Read data/calibrated_points.json (written by code/balancer.py) and shape
    its `balanced_points` values into the same {unit_key: {points_override: N}}
    layout used by overrides.json. Skips entries whose calibration didn't
    converge so unreliable values don't pollute the live catalogue.
    """
    if not CALIBRATED_PATH.exists():
        return {}
    payload = json.loads(CALIBRATED_PATH.read_text(encoding="utf-8"))
    out: Dict[str, Dict] = {}
    for key, record in payload.get("units", {}).items():
        if not record.get("converged"):
            continue
        balanced = float(record.get("balanced_points") or 0)
        if balanced <= 0:
            continue
        out[key] = {"points_override": balanced}
    return out


def _apply_override(
    base: Optional[CatalogEntry],
    override: Dict,
    key: str,
    hand_override_field_names: Tuple[str, ...] = (),
) -> CatalogEntry:
    """Apply an override dict to a base entry, or create a new entry from scratch.

    `hand_override_field_names` names the fields data/overrides.json (the
    hand-tuning layer specifically, not codex-corrections or calibrated-points)
    explicitly set for `key`. It is stamped onto the resulting CatalogEntry's
    `override_field_names` unchanged — see that field's comment for why it
    exists (OVERRIDE-PRECEDENCE, SWEG_OVERRIDE_MELEE_PRECEDENCE).
    """
    if base is None:
        # An override with no BSData base is only legitimate when it carries
        # the core stat fields needed to describe a unit from scratch. A
        # partial override (e.g. anti_keywords-only) on a key that doesn't
        # match any BSData entry is a typo'd key — silently fabricating a
        # zero-stat ghost entry caused a 14 GB pytest leak via build_random_army
        # (the zero-cost ghost was eternally affordable). Fail loud per
        # CLAUDE.md rule 13.
        required = ("name", "health", "damage")
        missing = [f for f in required if f not in override]
        if missing:
            raise KeyError(
                f"data/overrides.json key {key!r} has no matching entry in "
                f"data/bsdata/parsed.json and the override is partial "
                f"(missing required fields: {missing}; got: {sorted(override)}). "
                f"Either fix the typo so it matches a BSData key, or fill in "
                f"the missing fields to create a fresh unit from scratch."
            )
        return CatalogEntry.from_dict({
            "key": key,
            **override,
            "override_field_names": hand_override_field_names,
        })

    merged = {
        "key": base.key,
        "name": override.get("name", base.name),
        "health": override.get("health", base.health),
        "damage": override.get("damage", base.damage),
        "hit_probability": override.get("hit_probability", base.hit_probability),
        "ap": override.get("ap", base.ap),
        "save": override.get("save", base.save),
        "codex": override.get("codex", base.codex),
        "points_listed": override.get("points_listed", base.points_listed),
        # SWEG_IK_CANIS_SINGLE (default-on, `=0` byte-identical kill-switch) —
        # data-correctness fix. BSData folds "Sir Hekhtur" into the Canis Rex
        # datasheet as a second model_loadouts slot (the mapper then emits
        # min_models=max_models=2), but Sir Hekhtur is the EJECTED-PILOT
        # replacement — BSData verbatim: "Your Canis Rex unit is not
        # considered to be destroyed until Sir Hekhtur is also destroyed" —
        # a 3-wound INFANTRY character who only exists AFTER the Knight is
        # destroyed. The per-model squad builder (code/army.py
        # _add_squad_per_model) spawned one Unit per slot, and since
        # dataclasses.replace only swaps weapon fields BOTH inherited the
        # shared health=26 — the sim fielded TWO permanent 26-wound TITANIC
        # combatants from turn 1 in every Imperial Knights game (the
        # archetype seed guarantees Canis Rex). The faithful minimal model
        # is ONE Knight; the post-destruction Hekhtur bail-out is an
        # unmodelled mechanic (documented honest omission — far smaller than
        # the phantom double Knight). Cited `simulator.ik_canis_single`.
        "min_models": (
            1
            if (base.key == "imperial_knights_library_canis_rex"
                and os.environ.get("SWEG_IK_CANIS_SINGLE", "1") != "0")
            else override.get("min_models", base.min_models)
        ),
        "max_models": (
            1
            if (base.key == "imperial_knights_library_canis_rex"
                and os.environ.get("SWEG_IK_CANIS_SINGLE", "1") != "0")
            else override.get("max_models", base.max_models)
        ),
        "strength": override.get("strength", base.strength),
        "toughness": override.get("toughness", base.toughness),
        "leadership": override.get("leadership", base.leadership),
        "oc": override.get("oc", base.oc),
        "attacks": override.get("attacks", base.attacks),
        "weapon_damage_per_shot": override.get("weapon_damage_per_shot", base.weapon_damage_per_shot),
        "lethal_hits": override.get("lethal_hits", base.lethal_hits),
        "sustained_hits": override.get("sustained_hits", base.sustained_hits),
        "melee_sustained_hits": override.get("melee_sustained_hits", base.melee_sustained_hits),
        # Wave-244 melee mode-routing — pass the melee keyword fields through the
        # override merge. Pre-wave-244 melee_lethal_hits was ABSENT from this
        # merged dict (every unit re-built here lost it to the False default,
        # which is why the aggregate path always produced False); the five new
        # ANTI-X / DEVASTATING WOUNDS / TWIN-LINKED fields are added alongside it.
        # Override fully replaces when present; base (mapper) value is the fallback.
        "melee_lethal_hits": override.get("melee_lethal_hits", base.melee_lethal_hits),
        "melee_anti_keywords": override.get("melee_anti_keywords", base.melee_anti_keywords),
        "melee_devastating_wounds": override.get(
            "melee_devastating_wounds", base.melee_devastating_wounds
        ),
        "melee_twin_linked": override.get("melee_twin_linked", base.melee_twin_linked),
        "melee_devastating_wounds_basket_fraction": override.get(
            "melee_devastating_wounds_basket_fraction",
            base.melee_devastating_wounds_basket_fraction,
        ),
        "melee_anti_keyword_basket_fractions": override.get(
            "melee_anti_keyword_basket_fractions",
            base.melee_anti_keyword_basket_fractions,
        ),
        "twin_linked": override.get("twin_linked", base.twin_linked),
        # SWEG_WE_DW_RANGED_FAB (default-on) — the overrides add a unit-level
        # devastating_wounds=True to world_eaters_heldrake (its Baleflamer is a
        # Torrent weapon) and world_eaters_master_of_executions (its Bolt pistol);
        # neither ranged weapon carries [DEVASTATING WOUNDS] on its datasheet. The
        # melee claws / axe of dismemberment do, and are represented separately via
        # melee_devastating_wounds (mapper). =0 restores the fabricated ranged flag.
        "devastating_wounds": (
            False
            if (key in ("world_eaters_heldrake",
                        "world_eaters_master_of_executions")
                and os.environ.get("SWEG_WE_DW_RANGED_FAB", "1") != "0")
            else override.get("devastating_wounds", base.devastating_wounds)
        ),
        # SWEG_NECRON_LYCHGUARD_INVULN (default-on) — necrons_lychguard is modelled
        # with the Warscythe loadout (parsed weapon "Warscythe", S8 AP-3 D2 with
        # Devastating Wounds), but the override adds a 4+ invulnerable save that only
        # exists on the mutually-exclusive Hyperphase-sword-and-dispersion-shield
        # loadout. A Warscythe Lychguard has no invulnerable save; the combination is
        # impossible. Gate forces the base (no invulnerable) across all three invuln
        # fields; =0 restores the fabricated 4+.
        "invuln_save": (
            base.invuln_save
            if (key == "necrons_lychguard"
                and os.environ.get("SWEG_NECRON_LYCHGUARD_INVULN", "1") != "0")
            else override.get("invuln_save", base.invuln_save)
        ),
        "invuln_ranged_only": override.get("invuln_ranged_only", base.invuln_ranged_only),
        # Task #92: an override may set the per-attack invuln directly; else fall
        # back to any override of the single value, else the base per-attack value.
        # Lychguard invuln fabrication (SWEG_NECRON_LYCHGUARD_INVULN, see above) must
        # also zero the per-attack invuln fields — they otherwise fall back to the
        # override's single invuln_save value.
        "invuln_save_melee": (
            base.invuln_save_melee
            if (key == "necrons_lychguard"
                and os.environ.get("SWEG_NECRON_LYCHGUARD_INVULN", "1") != "0")
            else override.get("invuln_save_melee", override.get("invuln_save", base.invuln_save_melee))
        ),
        "invuln_save_ranged": (
            base.invuln_save_ranged
            if (key == "necrons_lychguard"
                and os.environ.get("SWEG_NECRON_LYCHGUARD_INVULN", "1") != "0")
            else override.get("invuln_save_ranged", override.get("invuln_save", base.invuln_save_ranged))
        ),
        "veterans_of_the_long_war": override.get("veterans_of_the_long_war", base.veterans_of_the_long_war),
        "csm_despoilers": override.get("csm_despoilers", base.csm_despoilers),
        "csm_unholy_bloodshed": override.get("csm_unholy_bloodshed", base.csm_unholy_bloodshed),
        "storm_of_retribution": override.get("storm_of_retribution", base.storm_of_retribution),
        "votann_native_reroll_ranged": override.get("votann_native_reroll_ranged", base.votann_native_reroll_ranged),
        "rapid_fire": override.get("rapid_fire", base.rapid_fire),
        "melta": override.get("melta", base.melta),
        "ignores_cover": override.get("ignores_cover", base.ignores_cover),
        "anti_keywords": override.get("anti_keywords", base.anti_keywords),
        "heavy": override.get("heavy", base.heavy),
        "assault": override.get("assault", base.assault),
        "torrent": override.get("torrent", base.torrent),
        "hazardous": override.get("hazardous", base.hazardous),
        "blast": override.get("blast", base.blast),
        "lance": override.get("lance", base.lance),
        "precision": override.get("precision", base.precision),
        "pistol": override.get("pistol", base.pistol),
        "weapon": override.get("weapon", base.weapon),
        "secondary_pistol": override.get("secondary_pistol", base.secondary_pistol),
        "indirect_fire": override.get("indirect_fire", base.indirect_fire),
        "one_shot": override.get("one_shot", base.one_shot),
        "stealth": override.get("stealth", base.stealth),
        "lone_operative": override.get("lone_operative", base.lone_operative),
        "fights_first": override.get("fights_first", base.fights_first),
        "has_blessings_of_khorne": override.get("has_blessings_of_khorne", base.has_blessings_of_khorne),
        # SWEG_DEEP_STRIKE_TRIAGE (default-on) — clears deep_strike=True for
        # VEHICLE/MOUNTED units whose Deep Strike ability is printed as an
        # OPTIONAL play (Webway Portal, Webway Assault, Webway Gate) rather
        # than the unit's actual default deployment method. BSData attaches the
        # "Deep Strike" infoLink directly to these unit entries because the
        # ability IS printed on the datasheet, but competitive play NEVER uses
        # it — deploying these transports and skimmers on-board from T1 is
        # strictly better. The SWEG_DEPLOY_AI reserve logic sends any
        # deep_strike=True unit to reserves, which breaks the entire faction
        # doctrine for Drukhari (and similar Aeldari builds).
        # Units affected: see _DEEP_STRIKE_TRIAGE_CLEAR_KEYS above.
        # =0 restores the BSData-verbatim flag (byte-identical to pre-triage).
        # Citation: data/rule_citations.d/deep_strike_triage.json
        "deep_strike": (
            False
            if (key in _DEEP_STRIKE_TRIAGE_CLEAR_KEYS
                and os.environ.get("SWEG_DEEP_STRIKE_TRIAGE", "1") != "0")
            else override.get("deep_strike", base.deep_strike)
        ),
        "scout_distance": override.get("scout_distance", base.scout_distance),
        "infiltrator": override.get("infiltrator", base.infiltrator),
        "deadly_demise": override.get("deadly_demise", base.deadly_demise),
        "firing_deck": override.get("firing_deck", base.firing_deck),
        # SWEG_EC_LUCIUS_FNP_FIX (wave-260, default-off) — fabrication removal.
        # parsed.json carries fnp=5 for emperor_s_children_lucius_the_eternal
        # as a mapper prose-walk artifact; no Feel No Pain ability of any
        # threshold appears on the real Lucius the Eternal datasheet (his only
        # defensive special rule is the 4++ Armour of Shrieking Souls, already
        # wired via overrides.json:1097). No citation exists in
        # data/rule_citations.json or data/rule_citations.d/ for any Lucius
        # Feel No Pain. The fix resets fnp to 7 (no effective save) when the
        # gate is active, matching the sibling mapper-sweep pattern used for
        # Lion El'Jonson, Azrael, and Saint Celestine. Gate OFF leaves
        # parsed.json's fnp=5 untouched so the byte-identical anchor is
        # reproducible. See docs/OVERPOLE_UNIT_AUDIT.md rank 6;
        # ADOPTED default-on (wave 260, fidelity-first); =0 kill-switch.
        # SWEG_DG_PLAGUE_FNP_FAITHFUL (default-off) — fabrication removal. The 10e
        # Plague Marines and Blightlord Terminators datasheets carry NO Feel No
        # Pain / Disgustingly Resilient (verified against the BSData Death Guard
        # cat — zero "Feel No Pain" in either datasheet window). The overrides.json
        # fnp=5 on them is the army-wide-Disgustingly-Resilient-as-FNP fabrication
        # the project already deleted at iter-15 (see data/rule_citations.d/
        # death_guard.json _comment: "there is NO codex-level Feel No Pain in the
        # 10e Death Guard codex... Disgustingly Resilient is ONLY the 2 CP Virulent
        # Vectorium stratagem (-1 damage)"), which leaked onto the per-datasheet
        # overrides. The real -1-damage stratagem is modelled separately at
        # simulator.py:4070 (_try_disgustingly_resilient). Plaguebearers / Typhus /
        # Mortarion / Poxwalkers / Deathshroud KEEP their fnp — BSData confirms
        # those datasheets DO carry Feel No Pain. ADOPTED default-on (fidelity-first;
        # scoped Death-Guard + Chaos-Space-Marines N=80 paired vs sc20a: gated mean
        # absolute error 3.26 -> 3.06, Death Guard -3.37 decisive toward its real
        # 47.6, only collateral Grey Knights -0.46). Set =0 as a kill-switch to
        # restore the fabricated fnp=5 and reproduce the sc20a anchor byte-identically.
        # SWEG_EC_LUCIUS_FNP_FIX — RETIRED to default-OFF (2026-07-01). The wave-260
        # removal was WRONG: the 2025 Emperor's Children codex gives Lucius the
        # Eternal a real Feel No Pain 5+ (BSData infoLink 01a8-58fe-9d82-ae3c,
        # unconditional; Wahapedia confirms). The mapper captured it correctly; the
        # wave-260 gate deleted a faithful stat (EVAL_PROTOCOL section 9 forbidden-
        # zone violation). Default-off now KEEPS his faithful fnp=5; set =1 to
        # re-enable the old removal (reproduces the sc21a anchor byte-identically).
        # SWEG_AUDIT2_FNP_FABS (default-ON) — audit-wave-2 fabrication removals. The
        # mapper prose-walk stamped an aura's GRANTED Feel No Pain onto the granter's
        # own profile: genestealer_cults_acolyte_iconward (Nexus of Devotion -> led
        # unit), necrons_technomancer (Rites of Reanimation -> led unit),
        # chaos_daemons_library_contorted_epitome (Swallow Energy -> Daemonettes).
        # death_guard_typhus's override fnp instead cited the non-existent army-wide
        # Disgustingly Resilient (his only relevant ability, The Destroyer Hive, is a
        # -1-to-hit melee aura). BSData confirms none of the four carries a self Feel
        # No Pain infoLink. (Locus / Cryptothralls were flagged but are already fnp=7
        # -- no action.) =0 kill-switch restores the fabricated fnp / reproduces sc21a.
        "fnp": (
            7
            if (
                (key == "emperor_s_children_lucius_the_eternal"
                 and os.environ.get("SWEG_EC_LUCIUS_FNP_FIX", "0") == "1")
                or (key in ("death_guard_plague_marines",
                            "chaos_space_marines_plague_marines",
                            "death_guard_blightlord_terminators")
                    and os.environ.get("SWEG_DG_PLAGUE_FNP_FAITHFUL", "1") != "0")
                or (key in ("genestealer_cults_acolyte_iconward",
                            "necrons_technomancer",
                            "chaos_daemons_library_contorted_epitome",
                            "death_guard_typhus")
                    and os.environ.get("SWEG_AUDIT2_FNP_FABS", "1") != "0")
            )
            else override.get("fnp", base.fnp)
        ),
        # SWEG_AM_STICKY_CADIAN (rank-8 lever) — ADOPTED default-on (wave 255).
        # Cadian Shock Troops carry the 'Shock Troops' sticky-objective ability
        # (Wahapedia: Cadian-Shock-Troops). The override sets sticky_objective
        # True for astra_militarum_cadian_shock_troops; honoured by default,
        # with SWEG_AM_STICKY_CADIAN=0 the byte-identical kill-switch (restores
        # base.sticky_objective=False for this unit). Paired N=80 (AM-scoped):
        # Astra Militarum +1.87 (25.9 -> 27.8), gated mean absolute error
        # 3.96 -> 3.86. Every other unit takes the unchanged merge regardless.
        # SWEG_GSC_STICKY_FAB (default-on) — genestealer_cults_acolyte_hybrids_with_
        # hand_flamers / _with_autopistols carry a fabricated sticky_objective citing
        # Cult Ambush, which has no sticky-objective clause (Cult Ambush is purely a
        # marker-redeploy / set-back-up ability; the real sticky rule is the Outlander
        # Claw detachment passive for Atalan Jackals). Gate zeroes them; =0 restores.
        "sticky_objective": (
            base.sticky_objective
            if (
                (key == "astra_militarum_cadian_shock_troops"
                 and os.environ.get("SWEG_AM_STICKY_CADIAN", "1") == "0")
                or (key in ("genestealer_cults_acolyte_hybrids_with_hand_flamers",
                            "genestealer_cults_acolyte_hybrids_with_autopistols")
                    and os.environ.get("SWEG_GSC_STICKY_FAB", "1") != "0")
            )
            else override.get("sticky_objective", base.sticky_objective)
        ),
        "resolute_will": override.get("resolute_will", base.resolute_will),
        "murderers_cowl": override.get("murderers_cowl", base.murderers_cowl),
        "gloam_rot": override.get("gloam_rot", base.gloam_rot),
        "righteous_paragons": override.get("righteous_paragons", base.righteous_paragons),
        "tau_sunforge": override.get("tau_sunforge", base.tau_sunforge),
        "tau_armour_hunter": override.get("tau_armour_hunter", base.tau_armour_hunter),
        "tau_targeting_array": override.get("tau_targeting_array", base.tau_targeting_array),
        "tau_nova_charge": override.get("tau_nova_charge", base.tau_nova_charge),
        "necrodermis": override.get("necrodermis", base.necrodermis),
        "reanimates_with_army": override.get("reanimates_with_army", base.reanimates_with_army),
        "unit_keywords": override.get("unit_keywords", base.unit_keywords),
        "melee_attacks": override.get("melee_attacks", base.melee_attacks),
        "melee_damage_per_shot": override.get("melee_damage_per_shot", base.melee_damage_per_shot),
        "melee_hit_probability": override.get("melee_hit_probability", base.melee_hit_probability),
        "melee_strength": override.get("melee_strength", base.melee_strength),
        "melee_ap": override.get("melee_ap", base.melee_ap),
        "melee_weapon": override.get("melee_weapon", base.melee_weapon),
        "range_inches": override.get("range_inches", base.range_inches),
        "secondary_attacks": override.get("secondary_attacks", base.secondary_attacks),
        "secondary_weapon_damage_per_shot": override.get("secondary_weapon_damage_per_shot", base.secondary_weapon_damage_per_shot),
        "secondary_hit_probability": override.get("secondary_hit_probability", base.secondary_hit_probability),
        "secondary_ap": override.get("secondary_ap", base.secondary_ap),
        "secondary_strength": override.get("secondary_strength", base.secondary_strength),
        "secondary_range_inches": override.get("secondary_range_inches", base.secondary_range_inches),
        "secondary_weapon": override.get("secondary_weapon", base.secondary_weapon),
        "secondary_anti_keywords": override.get("secondary_anti_keywords", base.secondary_anti_keywords),
        "secondary_lethal_hits": override.get("secondary_lethal_hits", base.secondary_lethal_hits),
        "secondary_sustained_hits": override.get("secondary_sustained_hits", base.secondary_sustained_hits),
        "secondary_twin_linked": override.get("secondary_twin_linked", base.secondary_twin_linked),
        "secondary_devastating_wounds": override.get("secondary_devastating_wounds", base.secondary_devastating_wounds),
        "secondary_rapid_fire": override.get("secondary_rapid_fire", base.secondary_rapid_fire),
        "secondary_melta": override.get("secondary_melta", base.secondary_melta),
        "secondary_ignores_cover": override.get("secondary_ignores_cover", base.secondary_ignores_cover),
        "secondary_heavy": override.get("secondary_heavy", base.secondary_heavy),
        "secondary_assault": override.get("secondary_assault", base.secondary_assault),
        "secondary_torrent": override.get("secondary_torrent", base.secondary_torrent),
        "secondary_blast": override.get("secondary_blast", base.secondary_blast),
        # SEC-KEYWORD-PARITY — new override-passthrough entries for the four
        # new secondary keyword fields. Same convention as the other secondary_*
        # fields above: override fully replaces when present, base value is the
        # fallback.
        "secondary_one_shot": override.get("secondary_one_shot", base.secondary_one_shot),
        "secondary_hazardous": override.get("secondary_hazardous", base.secondary_hazardous),
        "secondary_indirect_fire": override.get("secondary_indirect_fire", base.secondary_indirect_fire),
        "secondary_precision": override.get("secondary_precision", base.secondary_precision),
        # MAP-1: tertiary+ ranged profiles — override fully replaces (rare; the
        # mapper populates these from BSData and overrides almost never touch
        # multi-profile lists). base value defaults to [] when None.
        "extra_ranged_profiles": override.get(
            "extra_ranged_profiles", base.extra_ranged_profiles or []
        ),
        # KNIGHTS-MULTIPROFILE-2: tertiary+ MELEE profiles. Same convention
        # as extra_ranged_profiles — override fully replaces the list; base
        # value defaults to [] when None. Cited as
        # `simulator.extra_melee_profiles`.
        "extra_melee_profiles": override.get(
            "extra_melee_profiles", base.extra_melee_profiles or []
        ),
        # PER-MODEL-LOADOUTS: per-model-type loadout list. Same full-replacement
        # convention as extra_ranged_profiles / extra_melee_profiles — an
        # override key replaces the whole list (overrides almost never touch it;
        # the mapper populates it from BSData). base value defaults to [] when
        # None.
        "model_loadouts": (
            # SWEG_IK_CANIS_SINGLE (see min_models above): drop the Sir
            # Hekhtur loadout slot so the per-model builder fields exactly
            # one Knight. `=0` restores the verbatim two-slot list.
            [
                e for e in override.get(
                    "model_loadouts", base.model_loadouts or []
                )
                if not (isinstance(e, dict)
                        and e.get("name") == "Sir Hekhtur")
            ]
            if (base.key == "imperial_knights_library_canis_rex"
                and os.environ.get("SWEG_IK_CANIS_SINGLE", "1") != "0")
            else override.get(
                "model_loadouts", base.model_loadouts or []
            )
        ),
        # OVERRIDE-PRECEDENCE — see CatalogEntry.override_field_names. Carried
        # straight through from the caller; not derived from `override` here
        # because `override` is the corrections+overrides+calibrated merge,
        # and this marker must name ONLY the hand-tuning (overrides.json)
        # layer.
        "override_field_names": hand_override_field_names,
        # DAMAGED-BRACKET (task #77) — per-stat Damaged-bracket reduction. The
        # mapper extracts these from BSData; overrides may correct a mis-parse.
        # Default to the base (mapper) value, falling back to 0 (no bracket).
        "damaged_threshold": override.get(
            "damaged_threshold", base.damaged_threshold
        ),
        "damaged_oc_penalty": override.get(
            "damaged_oc_penalty", base.damaged_oc_penalty
        ),
        "damaged_hit_penalty": override.get(
            "damaged_hit_penalty", base.damaged_hit_penalty
        ),
        "damaged_attacks_penalty": override.get(
            "damaged_attacks_penalty", base.damaged_attacks_penalty
        ),
        # MAP-3-FIX — basket fractions. Override path almost never sets these
        # (the mapper computes them from BSData) but allow overrides for
        # corner cases / hand-tuning. Default 1.0 preserves legacy behaviour.
        "devastating_wounds_basket_fraction": override.get(
            "devastating_wounds_basket_fraction",
            base.devastating_wounds_basket_fraction,
        ),
        "lance_basket_fraction": override.get(
            "lance_basket_fraction", base.lance_basket_fraction,
        ),
        "anti_keyword_basket_fractions": override.get(
            "anti_keyword_basket_fractions",
            base.anti_keyword_basket_fractions,
        ),
        "move": override.get("move", base.move),
        "points_override": override.get("points_override", base.points_override),
        "base_shape": override.get("base_shape", base.base_shape),
        "base_diameter_mm": override.get("base_diameter_mm", base.base_diameter_mm),
        "base_width_mm": override.get("base_width_mm", base.base_width_mm),
        "base_length_mm": override.get("base_length_mm", base.base_length_mm),
        "loadout": override.get("loadout", base.loadout),
        "notes": override.get("notes", base.notes),
        "enabled": override.get("enabled", base.enabled),
        "skip_reason": override.get("skip_reason", base.skip_reason),
    }
    return CatalogEntry.from_dict(merged)


def load_catalog(
    include_disabled: bool = False,
    use_calibrated: bool = False,
    codex_version: str = DEFAULT_CODEX_VERSION,
) -> Dict[str, CatalogEntry]:
    """
    Build the merged catalogue. Layers, in precedence order (later wins):

      1. data/bsdata/parsed.json                 — BSData-derived base stats
      2. data/codex_corrections_<version>.json   — BSData-lag corrections
                                                   (canonical codex values
                                                   for the chosen edition)
      3. data/overrides.json                     — SwegHammer hand-tuning
      4. data/calibrated_points.json             — balancer-derived points
                                                   (only if use_calibrated=True
                                                   AND calibration converged)

    `codex_version` selects which corrections file to layer in. Default is
    "10e". When 11e releases, copy codex_corrections_10e.json to
    codex_corrections_11e.json, edit the 11e entries, and pass
    codex_version="11e" to lock the simulator to the 11e codex without
    touching overrides.json.
    """
    base = _load_parsed()
    corrections = _load_codex_corrections(codex_version)
    overrides = _load_overrides()
    calibrated = _load_calibrated_overrides() if use_calibrated else {}

    out: Dict[str, CatalogEntry] = {}
    keys = set(base) | set(corrections) | set(overrides) | set(calibrated)
    for key in keys:
        # Merge order: corrections first (canonical codex), then overrides
        # (SwegHammer hand-tuning), then calibrated (balancer output).
        # Each later layer wins on overlapping fields.
        merged_override = dict(corrections.get(key, {}))
        merged_override.update(overrides.get(key, {}))
        merged_override.update(calibrated.get(key, {}))
        # OVERRIDE-PRECEDENCE — names of the fields the HAND-TUNING layer
        # (overrides.json) explicitly set for this unit, sourced before the
        # corrections/calibrated merge above so it names only what a human
        # actually typed. See CatalogEntry.override_field_names.
        hand_override_field_names = tuple(sorted(overrides.get(key, {}).keys()))
        entry = _apply_override(
            base.get(key), merged_override, key,
            hand_override_field_names=hand_override_field_names,
        )
        if not include_disabled and not entry.enabled:
            continue
        out[entry.key] = entry
    return out


def summary(codex_version: str = DEFAULT_CODEX_VERSION) -> str:
    catalog = load_catalog(codex_version=codex_version)
    return (
        f"{len(catalog)} units in catalogue "
        f"({len(_load_parsed())} from BSData, "
        f"{len(_load_codex_corrections(codex_version))} codex_{codex_version} corrections, "
        f"{len(_load_overrides())} override entries)"
    )


if __name__ == "__main__":
    print(summary())
    catalog = load_catalog()
    for key, entry in sorted(catalog.items())[:10]:
        print(
            f"  {key:50} {entry.name[:30]:30} "
            f"H={entry.health:>4.1f} D={entry.damage:>4.1f} "
            f"Hit={entry.hit_probability:>5.2f} AP={entry.ap:>2} Sv={entry.save}"
        )
