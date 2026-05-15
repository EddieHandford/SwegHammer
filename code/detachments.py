"""
Detachment rules — army-wide passive buffs.

10e armies pick a Detachment at list-build time. Each detachment carries:
  - a passive "Detachment Rule" that applies to every model in the army
  - a Stratagem list (deferred — see Phase E)
  - an Enhancement list (deferred)

This module models JUST the always-on passive piece, captured as flags on a
`Detachment` dataclass. The simulator reads `Army.detachment` (if set) and
applies the matching modifiers during the relevant phase.

This is intentionally a thin MVP. Real 10e detachments have many bespoke
mechanics that can't be reduced to a flag (e.g. Oath of Moment picks a target
each turn; Reanimation Protocols restore W with specific roll mechanics).
We capture the headline effect of the canonical "first detachment" per
faction and document the simplification.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple

from .enhancements import Enhancement, enhancements_for_detachment
from .stratagems import (
    Stratagem,
    BATTLE_HOST_STRATAGEMS,
    DISGUSTINGLY_RESILIENT,
)


@dataclass(frozen=True)
class Detachment:
    """
    Army-wide passive modifiers. Most slots default to 'off'; setting a flag
    or value applies it to every friendly unit during the matching phase.

    The fields here are 10e-flavoured but lossy — see notes per detachment
    in DETACHMENTS for the rule each one approximates.
    """
    name: str
    faction: str
    notes: str = ""

    # Shooting / melee modifiers
    reroll_hit_ones: bool = False        # Re-roll natural 1s to hit (army-wide)
    reroll_wound_ones: bool = False      # Re-roll natural 1s to wound
    plus_one_to_hit: bool = False        # +1 to hit rolls (capped at 2+ canon)
    plus_one_to_wound: bool = False      # +1 to wound rolls
    plus_one_attack: int = 0             # Extra attacks per weapon (rare)

    # Defensive
    plus_one_save: bool = False          # +1 to armour save (cap 2+)
    extra_invuln: int = 7                # Cheap army-wide invuln (rare)
    fnp: int = 7                         # Army-wide Feel No Pain (7 = none)

    # Healing / recovery
    reanimate_per_round: int = 0         # W restored per unit per round end

    # Conditional attack buffs — apply only when the unit has an attached
    # friendly CHARACTER in aura range. Awakened Dynasty's Command
    # Protocols rule (Necrons 10e): "While a NECRONS CHARACTER model is
    # leading this unit, each time a model in this unit makes an attack,
    # add 1 to the Hit roll." The whole detachment's identity is "stack
    # characters into squads", so this is the right trigger to model.
    bonus_to_hit_when_led: bool = False

    # Psychic mortal-wound payload at end of each round. Models the
    # Thousand Sons Cabal-Points → Doombolt spell loop: the army's
    # collective psyker output cracks off N mortal wounds against the
    # highest-threat enemy, ignoring armour and toughness rolls. Median
    # of D3 = 2 maps cleanly to the typical Cult-of-Magic Doombolt yield.
    psychic_mortal_wounds_per_round: int = 0

    # Keyword-gated attack buffs introduced in #126 (second-detachment pass).
    # Each fires only when the ATTACKER unit matches the detachment's gate:
    #   * vehicles_reroll_hit_ones — Adeptus Astartes Ironstorm Spearhead.
    #     Friendly VEHICLE units re-roll Hit rolls of 1. Gate: attacker has
    #     the VEHICLE keyword.
    #   * canoptek_plus_one_to_wound — Necrons Canoptek Court. Friendly
    #     CANOPTEK units get +1 to wound rolls. Gate: attacker profile name
    #     starts with "Canoptek".
    #   * aspect_warrior_or_bike_plus_one_move — Aeldari Saim-Hann Wild Host.
    #     Aspect Warriors and Bike-mounted units gain +1" Movement. Gate:
    #     attacker profile name matches an Aspect Warrior datasheet (Howling
    #     Banshees, Striking Scorpions, Fire Dragons, Dark Reapers, Swooping
    #     Hawks, Warp Spiders, Shining Spears) or a bike chassis (Windriders,
    #     Shining Spears, Shroud Runners). Applied via `effective_move`.
    #   * plague_marines_plus_one_to_wound — Death Guard Plague Marines
    #     Onslaught. Plague Marines get +1 to wound rolls. Gate: attacker
    #     profile name == "Plague Marines".
    vehicles_reroll_hit_ones: bool = False
    canoptek_plus_one_to_wound: bool = False
    aspect_warrior_or_bike_plus_one_move: bool = False
    plague_marines_plus_one_to_wound: bool = False

    # Morale
    ld_bonus: int = 0                    # +N to friendly Ld (lower target)
    enemy_ld_penalty: int = 0            # -N to enemy Ld (higher target)

    # Detachment-specific Stratagems. Empty for now — the four UNIVERSAL
    # Core Stratagems are always available regardless of detachment (see
    # code/stratagems.py). Detachment-specific entries land in #104.
    stratagems: Tuple[Stratagem, ...] = ()

    # Detachment-specific Enhancements (10e core: each Detachment offers a
    # short list of Warlord upgrades available to one CHARACTER each). A
    # `Detachment` instance carries the tuple statically; `army_builder`
    # picks one Enhancement at construction time and assigns it to a
    # CHARACTER. See `code.enhancements` for the dataclass + registry.
    enhancements: Tuple[Enhancement, ...] = ()

    # Composition affinity — used by the army builder to pick a detachment
    # that suits the actual unit mix. Not a rule, just a selection tag.
    # One of: "vehicle", "infantry", "monster", "character", "balanced", or
    # "" (no preference, treated as balanced for scoring purposes).
    preferred_composition: str = ""


# ---------------------------------------------------------------------------
# Canonical detachments — start small, one per major faction
# ---------------------------------------------------------------------------

GLADIUS_TASK_FORCE = Detachment(
    name="Gladius Task Force",
    faction="Adeptus Astartes",
    notes=(
        "Combat Doctrines: round-rotating +1 to wound active for ADEPTUS "
        "ASTARTES units (Devastator R1 ranged-only / Tactical R2 both / "
        "Assault R3+ melee-only). The doctrine rotation lives in Unit.attack, "
        "gated on this detachment's name + faction. Cited as "
        "`simulator.combat_doctrines`. The detachment dataclass intentionally "
        "carries no offensive flags — Doctrines is round-and-mode-gated, "
        "not a static buff, so it can't be reduced to a single boolean field."
    ),
    preferred_composition="balanced",
)

AWAKENED_DYNASTY = Detachment(
    name="Awakened Dynasty",
    faction="Necrons",
    notes=(
        "Reanimation Protocols: dead models flip back to alive at end of "
        "round (simulator handles this directly via reanimate_per_round + "
        "_apply_reanimation). PLUS Command Protocols (Wahapedia): '\"While "
        "a NECRONS CHARACTER model is leading this unit, each time a model "
        "in this unit makes an attack, add 1 to the Hit roll.\"' The whole "
        "detachment's offensive teeth are gated on being character-led; "
        "lone Warrior squads get nothing. Detachment stratagems were "
        "previously fabricated (Implacable Onslaught, Methodical Destruction) "
        "and have been removed per the 2026-05-15 fabrication audit "
        "(commit fa9a957). Real Awakened Dynasty stratagems are the six "
        "'Protocol of the …' entries; replacement lands in a follow-up."
    ),
    reanimate_per_round=1,
    bonus_to_hit_when_led=True,
    preferred_composition="balanced",
)

INVASION_FLEET = Detachment(
    name="Invasion Fleet",
    faction="Tyranids",
    notes=(
        "Shadow in the Warp: enemies have -1 Ld for Battleshock. Real rule "
        "is range-gated; we apply army-wide."
    ),
    # APPROXIMATION: always-on -1 Ld passive substitutes for a once-per-battle Battleshock test.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tyranids/#Invasion-Fleet
    # Real rule: Shadow in the Warp — once-per-battle army-wide Battleshock test, not a passive Ld debuff.
    enemy_ld_penalty=1,
    preferred_composition="balanced",
)

# WAAAGH_DETACHMENT (the "WAAAGH! Tribe" placeholder) was deleted per the
# 2026-05-15 fabrication audit (commit fa9a957). The detachment name was not
# in the 10e Orks codex — real Ork detachments are War Horde, Da Big Hunt,
# Kult of Speed, Dread Mob, Green Tide, Bully Boyz, Taktikal Brigade, More
# Dakka!, Freebooter Krew, Speedwaaagh!, Blitz Brigade. The army rule
# (WAAAGH! once-per-game declaration) is unaffected and stays in
# `simulator.waaagh`; a real detachment replacement lands in a follow-up.

NOBLE_LANCE = Detachment(
    name="Noble Lance",
    faction="Imperial Knights",
    notes=(
        "Code Chivalric: lossy as army-wide +1 to wound. Real rule has "
        "conditional triggers (charged turn, lance keyword)."
    ),
    plus_one_to_wound=True,
    preferred_composition="vehicle",
)

HALLOWED_MARTYRS = Detachment(
    name="Hallowed Martyrs",
    faction="Adepta Sororitas",
    notes=(
        "Sacrifice-themed: +1 to wound army-wide. Real rule triggers off "
        "destroyed Sororitas units; we apply it always-on for the MVP."
    ),
    plus_one_to_wound=True,
    preferred_composition="infantry",
)

SHIELD_HOST = Detachment(
    name="Shield Host",
    faction="Adeptus Custodes",
    notes=(
        "Custodes durability: +1 to armour saves army-wide (cap at 2+). "
        "Approximates the multiple bespoke save-stacking rules in 10e."
    ),
    # APPROXIMATION: +1 save (defensive) substitutes for an offensive Crit Hit / AP buff.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
    # Real rule: Martial Mastery — Critical Hit / AP buff (offensive), not +1 save (defensive).
    plus_one_save=True,
    preferred_composition="infantry",
)

SKITARII_HUNTER_COHORT = Detachment(
    name="Skitarii Hunter Cohort",
    faction="Adeptus Mechanicus",
    notes=(
        "Conqueror Doctrina Imperatives: lossy as army-wide re-roll hit 1s. "
        "Real rule rotates between offensive / defensive imperatives."
    ),
    reroll_hit_ones=True,
    preferred_composition="infantry",
)

INQUISITION_TASK_FORCE = Detachment(
    name="Inquisition Task Force",
    faction="Agents of the Imperium",
    notes=(
        "Inquisitorial Authority: re-roll hit 1s army-wide for the assembled "
        "Imperial agents. Real rule is bespoke per Inquisitor archetype."
    ),
    reroll_hit_ones=True,
    preferred_composition="balanced",
)

COMBINED_REGIMENT = Detachment(
    name="Combined Regiment",
    faction="Astra Militarum",
    notes=(
        "Fire Orders: lossy as army-wide +1 to hit. Real rule is officer-gated "
        "single-target buffs (FRFSRF, Take Aim, etc.)."
    ),
    plus_one_to_hit=True,
    preferred_composition="balanced",
)

TELEPORT_STRIKE_FORCE = Detachment(
    name="Teleport Strike Force",
    faction="Grey Knights",
    notes=(
        "Teleportarium precision: army-wide re-roll wound 1s. Real rule "
        "includes deep strike and bespoke psychic mechanics."
    ),
    reroll_wound_ones=True,
    preferred_composition="infantry",
)

BATTLE_HOST = Detachment(
    # APPROXIMATION: detachment name "Battle Host" is the launch-day index name; codex name is "Warhost".
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost
    # Real rule: same detachment, renamed in the codex — effects roughly match but the key/name should be Warhost.
    name="Battle Host",
    faction="Aeldari",
    notes=(
        "Aspect of the Path: lossy as army-wide re-roll hit 1s. Real rule "
        "rotates +1 to hit / +1 to wound per Aspect Path. Detachment "
        "stratagems implemented: Lightning-Fast Reactions (+1 save), "
        "and Fire and Fade (re-roll hits on a friendly Aeldari unit's shoot). "
        "Matchless Agility and Spirit Stones were previously included here "
        "but have been removed per the 2026-05-15 fabrication audit "
        "(commit fa9a957) — neither was in the Aeldari codex."
    ),
    # APPROXIMATION: army-wide hit-1s reroll stands in for the Martial Grace / Battle Focus buff.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost
    # Real rule: Martial Grace — Battle Focus / Agile Manoeuvre token mechanic, not a hit-roll reroll.
    reroll_hit_ones=True,
    stratagems=BATTLE_HOST_STRATAGEMS,
    preferred_composition="infantry",
)

SKYSPLINTER_ASSAULT = Detachment(
    name="Skysplinter Assault",
    faction="Drukhari",
    notes=(
        "Hit-and-run raiders: approximated as army-wide re-roll wound 1s. "
        "Real rule grants +1 to wound on the turn a unit charged."
    ),
    reroll_wound_ones=True,
    preferred_composition="vehicle",
)

MONTKA = Detachment(
    name="Mont'ka",
    faction="T'au Empire",
    notes=(
        "APPROXIMATION: flat +1 to hit is a stand-in for the codex rule. "
        "Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tau-empire/#Montka. "
        "Real rule (Killing Blow): grants [ASSAULT] army-wide rounds 1-3 "
        "plus [LETHAL HITS] on Guided units — keyword grants, not a hit-roll "
        "bonus. Composes incorrectly with Strike Swiftly's transient_assault. "
        "Strike Swiftly stratagem previously attached here was an Enhancement "
        "(25 pts), not a stratagem — removed per 2026-05-15 fabrication audit."
    ),
    # APPROXIMATION: real Mont'ka grants [ASSAULT] army-wide rounds 1-3 + [LETHAL HITS] on Guided units, not +1 to hit.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tau-empire/#Montka
    # Real rule: Killing Blow — keyword grants, not a flat hit-roll bonus.
    plus_one_to_hit=True,
    preferred_composition="balanced",
)

PACTBOUND_ZEALOTS = Detachment(
    name="Pactbound Zealots",
    faction="Chaos Space Marines",
    notes=(
        "Dark Pacts: lossy as army-wide re-roll wound 1s. Real rule grants "
        "Lethal Hits or Sustained Hits at the cost of Battleshock checks."
    ),
    reroll_wound_ones=True,
    preferred_composition="balanced",
)

# PLAGUE_COMPANY (Death Guard) and CULT_OF_MAGIC (Thousand Sons) were deleted
# per the 2026-05-15 fabrication audit (commit fa9a957). Neither detachment
# exists in the 10e codex. Real DG detachments: Virulent Vectorium,
# Mortarion's Hammer, Champions of Contagion, Tallyband Summoners,
# Shamblerot Vectorium, Death Lord's Chosen, Flyblown Host. Real TSons
# detachments: Grand Coven, Changehost of Deceit, Warpmeld Pact, Rubricae
# Phalanx, Warpforged Cabal, Hexwarp Thrallband. Disgustingly Resilient
# (the real DG stratagem) has been re-anchored to Virulent Vectorium at
# 2CP in code/stratagems.py; real detachment replacements land per-faction.


BERZERKER_WARBAND = Detachment(
    name="Berzerker Warband",
    faction="World Eaters",
    notes=(
        "Blood Tithe frenzy: lossy as army-wide +1 to hit. Real rule spends "
        "Blood Tithe points on a roster of escalating effects."
    ),
    plus_one_to_hit=True,
    preferred_composition="infantry",
)

DAEMONIC_INCURSION = Detachment(
    name="Daemonic Incursion",
    faction="Chaos Daemons",
    notes=(
        "Shadow of Chaos: lossy as army-wide +1 to hit. Real rule grants "
        "Battle-shock immunity and bespoke god-specific buffs in friendly zones."
    ),
    plus_one_to_hit=True,
    preferred_composition="balanced",
)

FINAL_DAY = Detachment(
    name="Final Day",
    faction="Genestealer Cults",
    notes=(
        "Day of Reckoning: lossy as army-wide re-roll hit 1s. Real rule "
        "rotates between Ambush / Onslaught / Annihilation stages."
    ),
    reroll_hit_ones=True,
    preferred_composition="infantry",
)

# APPROXIMATION: "Oathband" is a generic stub; closest codex match is Hearthband.
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
# Real rule: codex Votann detachments are Needgaard Oathband, Persecution Prospect,
# Delve Assault Shift, Brandfast Oathband, Hearthfyre Arsenal, Hearthband, Mercenary Oathband.
OATHBAND = Detachment(
    name="Oathband",
    faction="Leagues of Votann",
    notes=(
        "Voidsmen Oaths: previously approximated as army-wide re-roll hit 1s "
        "because the real Eye of the Ancestors / Judgement Tokens rule was "
        "not modelled. Removed once `simulator.judgement_tokens` (Battle's "
        "per-army token store + Unit.attack re-roll buffs at 1+ / 3+ "
        "thresholds) landed — keeping the blanket re-roll on top of the real "
        "mechanic would double-stack the buff. Real Oathband detachment "
        "stratagems are deferred to #104."
    ),
    preferred_composition="balanced",
)


# ---------------------------------------------------------------------------
# Second detachments per major faction (#126). Each is keyword-gated so the
# buff only fires on the units the codex actually empowers — not army-wide.
# ---------------------------------------------------------------------------

IRONSTORM_SPEARHEAD = Detachment(
    name="Ironstorm Spearhead",
    faction="Adeptus Astartes",
    notes=(
        "Armoured Superiority: friendly VEHICLE units re-roll Hit rolls of 1. "
        "Lossy approximation of the canonical 'Armour of Contempt'-style "
        "vehicle-themed buffs in the launch-day Ironstorm Spearhead index; "
        "the codex replacement carries a similar VEHICLE-keyword reroll "
        "spine. Gate: attacker has the VEHICLE keyword."
    ),
    # APPROXIMATION: offensive vehicle hit-reroll stands in for a defensive AP debuff.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Ironstorm-Spearhead
    # Real rule: Armour of Contempt — -1 AP on Marine models (defensive), not vehicle hit rerolls (offensive).
    vehicles_reroll_hit_ones=True,
    preferred_composition="vehicle",
)

CANOPTEK_COURT = Detachment(
    name="Canoptek Court",
    faction="Necrons",
    notes=(
        "Canoptek-led command: friendly CANOPTEK units gain +1 to Wound "
        "rolls. Lossy approximation of the Canoptek Court detachment's "
        "Cryptek-led repair / acceleration buffs; we collapse the bundle "
        "into a flat +1 to wound on the Canoptek chassis. Gate: attacker "
        "profile name starts with 'Canoptek'."
    ),
    # APPROXIMATION: always-on +1 to wound stands in for a once-per-battle full wound reroll.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Canoptek-Court
    # Real rule: Hyper-Logical Strategy — once-per-battle full reroll, not always-on +1 to wound.
    canoptek_plus_one_to_wound=True,
    preferred_composition="balanced",
)

# SAIM_HANN_WILD_HOST (Aeldari) and PLAGUE_MARINES_ONSLAUGHT (Death Guard)
# were deleted per the 2026-05-15 fabrication audit (commit fa9a957).
# Neither detachment exists in the 10e codices. Real Aeldari detachments
# include Warhost, Windrider Host, Spirit Conclave, Guardian Battlehost,
# Ghosts of the Webway, Devoted of Ynnead, Seer Council, Aspect Host,
# Armoured Warhost, Serpent's Brood, Eldritch Raiders, Corsair Coterie.
# Real DG detachments are listed at PLAGUE_COMPANY's removal note above.
# Real detachment replacements land per-faction.


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DETACHMENTS: Dict[str, Detachment] = {
    "gladius_task_force":      GLADIUS_TASK_FORCE,
    "awakened_dynasty":        AWAKENED_DYNASTY,
    "invasion_fleet":          INVASION_FLEET,
    "noble_lance":             NOBLE_LANCE,
    "hallowed_martyrs":        HALLOWED_MARTYRS,
    "shield_host":             SHIELD_HOST,
    "skitarii_hunter_cohort":  SKITARII_HUNTER_COHORT,
    "inquisition_task_force":  INQUISITION_TASK_FORCE,
    "combined_regiment":       COMBINED_REGIMENT,
    "teleport_strike_force":   TELEPORT_STRIKE_FORCE,
    "battle_host":             BATTLE_HOST,
    "skysplinter_assault":     SKYSPLINTER_ASSAULT,
    "montka":                  MONTKA,
    "pactbound_zealots":       PACTBOUND_ZEALOTS,
    "berzerker_warband":       BERZERKER_WARBAND,
    "daemonic_incursion":      DAEMONIC_INCURSION,
    "final_day":               FINAL_DAY,
    "oathband":                OATHBAND,
    # Second detachments per major faction (#126).
    "ironstorm_spearhead":     IRONSTORM_SPEARHEAD,
    "canoptek_court":          CANOPTEK_COURT,
    # Deleted per fabrication audit fa9a957: waaagh_tribe, plague_company,
    # cult_of_magic, saim_hann_wild_host, plague_marines_onslaught. Real
    # codex detachment replacements land in per-faction follow-up commits.
}


# Bind enhancement tuples onto each Detachment whose key has a wired entry
# in `enhancements_for_detachment`. Uses dataclasses.replace because
# `Detachment` is frozen — this produces a new Detachment instance and
# replaces the registry entry in-place. Detachments with no wired
# enhancements keep the default empty tuple.
import dataclasses as _dc
for _key, _det in list(DETACHMENTS.items()):
    _enh = enhancements_for_detachment(_key)
    if _enh:
        DETACHMENTS[_key] = _dc.replace(_det, enhancements=_enh)
# Clean up the loop variables so `dir(detachments)` doesn't expose a stray
# `_det` Detachment instance that the rule auditor would otherwise scan for
# citations. The trailing underscore-prefixed names from the for-loop survive
# scope otherwise (CPython doesn't garbage-collect loop locals in module
# bodies), and the audit picked up the last-iteration Detachment as a
# spurious `_det.<field>` citation requirement.
del _key, _det, _enh, _dc
# Re-bind the module-level constants so downstream `from .detachments import
# GLADIUS_TASK_FORCE` callers see the patched-with-enhancements instance.
GLADIUS_TASK_FORCE = DETACHMENTS["gladius_task_force"]
AWAKENED_DYNASTY   = DETACHMENTS["awakened_dynasty"]
MONTKA             = DETACHMENTS["montka"]
# CULT_OF_MAGIC and PLAGUE_COMPANY re-bindings removed per fabrication
# audit (commit fa9a957); the detachments themselves are gone.

# Default detachment per faction (used when Army.detachment is None and a
# faction is known). Picks a sensible competitive default; user can override.
DEFAULT_BY_FACTION: Dict[str, str] = {
    "Adeptus Astartes":         "gladius_task_force",
    "Ultramarines":             "gladius_task_force",
    "Blood Angels":             "gladius_task_force",
    "Dark Angels":              "gladius_task_force",
    "Black Templars":           "gladius_task_force",
    "Space Wolves":             "gladius_task_force",
    "Salamanders":              "gladius_task_force",
    "Imperial Fists":           "gladius_task_force",
    "Iron Hands":               "gladius_task_force",
    "Raven Guard":              "gladius_task_force",
    "White Scars":              "gladius_task_force",
    "Deathwatch":               "gladius_task_force",
    "Necrons":                  "awakened_dynasty",
    "Tyranids":                 "invasion_fleet",
    # Orks: no detachment mapped after fa9a957 (waaagh_tribe was a
    # fabricated placeholder). Real Ork detachments land in follow-up.
    "Orks":                     "",
    "Imperial Knights":         "noble_lance",
    "Chaos Knights":            "noble_lance",
    "Adepta Sororitas":         "hallowed_martyrs",
    "Adeptus Custodes":         "shield_host",
    "Adeptus Mechanicus":       "skitarii_hunter_cohort",
    "Agents of the Imperium":   "inquisition_task_force",
    "Imperial Agents":          "inquisition_task_force",
    "Astra Militarum":          "combined_regiment",
    "Grey Knights":             "teleport_strike_force",
    "Aeldari":                  "battle_host",
    "Aeldari (Craftworlds)":    "battle_host",
    "Ynnari":                   "battle_host",
    "Drukhari":                 "skysplinter_assault",
    "T'au Empire":              "montka",
    "Tau Empire":               "montka",
    "Chaos Space Marines":      "pactbound_zealots",
    "Heretic Astartes":         "pactbound_zealots",
    # Death Guard + Thousand Sons: no detachment after fa9a957 (plague_company
    # and cult_of_magic were fabricated). Real detachment replacements land
    # in follow-up per-faction commits.
    "Death Guard":              "",
    "Thousand Sons":            "",
    "World Eaters":             "berzerker_warband",
    "Chaos Daemons":            "daemonic_incursion",
    "Genestealer Cults":        "final_day",
    "Leagues of Votann":        "oathband",
}


def default_detachment_for_faction(faction: str) -> Optional[Detachment]:
    """Return the canonical detachment for a faction, or None if unmapped."""
    key = DEFAULT_BY_FACTION.get(faction)
    return DETACHMENTS.get(key) if key else None


# ---------------------------------------------------------------------------
# Composition-driven detachment selection (Phase: army-builder picker)
# ---------------------------------------------------------------------------

# All detachments registered for a faction. For now most factions only have
# one entry — the catalogue expands in #104. Tuples preserve insertion order
# so the picker is deterministic given a seeded RNG.
FACTION_DETACHMENTS: Dict[str, Tuple[str, ...]] = {
    # Marines chapters now carry BOTH Gladius Task Force (balanced) and
    # Ironstorm Spearhead (vehicle-heavy) per #126. Picker selects by army
    # composition: vehicle-dominant rosters favour Ironstorm.
    "Adeptus Astartes":         ("gladius_task_force", "ironstorm_spearhead"),
    "Ultramarines":             ("gladius_task_force", "ironstorm_spearhead"),
    "Blood Angels":             ("gladius_task_force", "ironstorm_spearhead"),
    "Dark Angels":              ("gladius_task_force", "ironstorm_spearhead"),
    "Black Templars":           ("gladius_task_force", "ironstorm_spearhead"),
    "Space Wolves":             ("gladius_task_force", "ironstorm_spearhead"),
    "Salamanders":              ("gladius_task_force", "ironstorm_spearhead"),
    "Imperial Fists":           ("gladius_task_force", "ironstorm_spearhead"),
    "Iron Hands":               ("gladius_task_force", "ironstorm_spearhead"),
    "Raven Guard":              ("gladius_task_force", "ironstorm_spearhead"),
    "White Scars":              ("gladius_task_force", "ironstorm_spearhead"),
    "Deathwatch":               ("gladius_task_force", "ironstorm_spearhead"),
    # Necrons: Awakened Dynasty (balanced character-led) vs Canoptek Court
    # (boosts Canoptek chassis). Picker tilts toward Canoptek when the
    # army leans on its Canoptek units.
    "Necrons":                  ("awakened_dynasty", "canoptek_court"),
    "Tyranids":                 ("invasion_fleet",),
    "Orks":                     (),
    "Imperial Knights":         ("noble_lance",),
    "Chaos Knights":            ("noble_lance",),
    "Adepta Sororitas":         ("hallowed_martyrs",),
    "Adeptus Custodes":         ("shield_host",),
    "Adeptus Mechanicus":       ("skitarii_hunter_cohort",),
    "Agents of the Imperium":   ("inquisition_task_force",),
    "Imperial Agents":          ("inquisition_task_force",),
    "Astra Militarum":          ("combined_regiment",),
    "Grey Knights":             ("teleport_strike_force",),
    # Aeldari: Battle Host only. saim_hann_wild_host was deleted per
    # fabrication audit fa9a957 (closest real: Windrider Host).
    "Aeldari":                  ("battle_host",),
    "Aeldari (Craftworlds)":    ("battle_host",),
    "Ynnari":                   ("battle_host",),
    "Drukhari":                 ("skysplinter_assault",),
    "T'au Empire":              ("montka",),
    "Tau Empire":               ("montka",),
    "Chaos Space Marines":      ("pactbound_zealots",),
    "Heretic Astartes":         ("pactbound_zealots",),
    # Death Guard + Thousand Sons: no detachments mapped after fa9a957
    # (plague_company, plague_marines_onslaught, cult_of_magic all fabricated).
    "Death Guard":              (),
    "Thousand Sons":            (),
    "World Eaters":             ("berzerker_warband",),
    "Chaos Daemons":            ("daemonic_incursion",),
    "Genestealer Cults":        ("final_day",),
    "Leagues of Votann":        ("oathband",),
}


def _army_composition_signature(units) -> Dict[str, float]:
    """
    Compute the fraction of total army points spent on each composition tag.

    Returns a dict with keys:
      - vehicle_fraction: VEHICLE units
      - infantry_fraction: INFANTRY units that aren't also VEHICLE
      - monster_fraction: MONSTER units
      - character_fraction: CHARACTER units

    Buckets are not mutually exclusive (a CHARACTER may also be INFANTRY) —
    each fraction is computed independently against total spent points. An
    empty army returns all zeros.

    `units` may be a list of `Unit` instances (with `.profile`) or a list of
    `UnitProfile` instances directly — both are supported so the picker can
    be called during army construction.
    """
    def _profile(u):
        return u.profile if hasattr(u, "profile") else u

    def _kw(u) -> set:
        return set(_profile(u).unit_keywords or ())

    def _pts(u) -> float:
        return float(_profile(u).points_cost)

    total = sum(_pts(u) for u in units)
    if total <= 0:
        return {
            "vehicle_fraction": 0.0,
            "infantry_fraction": 0.0,
            "monster_fraction": 0.0,
            "character_fraction": 0.0,
        }

    vehicle_pts = sum(_pts(u) for u in units if "VEHICLE" in _kw(u))
    infantry_pts = sum(
        _pts(u) for u in units
        if "INFANTRY" in _kw(u) and "VEHICLE" not in _kw(u)
    )
    monster_pts = sum(_pts(u) for u in units if "MONSTER" in _kw(u))
    character_pts = sum(_pts(u) for u in units if "CHARACTER" in _kw(u))

    return {
        "vehicle_fraction": vehicle_pts / total,
        "infantry_fraction": infantry_pts / total,
        "monster_fraction": monster_pts / total,
        "character_fraction": character_pts / total,
    }


def _dominant_composition(composition: Dict[str, float]) -> str:
    """
    Return the composition tag with the largest fraction, or "balanced" if
    no single bucket dominates (max fraction < 0.4). CHARACTER is excluded
    from the dominance check — characters ride alongside other unit types
    and shouldn't outweigh the army's actual chassis mix.
    """
    chassis = {
        "vehicle":  composition.get("vehicle_fraction", 0.0),
        "infantry": composition.get("infantry_fraction", 0.0),
        "monster":  composition.get("monster_fraction", 0.0),
    }
    best = max(chassis, key=chassis.get)
    if chassis[best] < 0.4:
        return "balanced"
    return best


# Aspect Warrior / Bike datasheet names — used by the Saim-Hann picker
# affinity (and by `effective_move` to gate the +1" Movement buff). Matched
# against `UnitProfile.name` exactly.
ASPECT_WARRIOR_OR_BIKE_NAMES: Tuple[str, ...] = (
    "Howling Banshees",
    "Striking Scorpions",
    "Fire Dragons",
    "Dark Reapers",
    "Swooping Hawks",
    "Warp Spiders",
    "Shining Spears",
    "Windriders",
    "Shroud Runners",
)


def _keyword_affinity_score(det: Detachment, units) -> float:
    """Bonus score for detachments whose gate matches a sizable chunk of the
    army's points. Returns 0 when the detachment has no keyword gate; up to
    +20 when >=30% of points fit the gate (i.e. the detachment's buff would
    fire on a meaningful slice of the army).

    Each gate is checked against the actual unit list via the same predicates
    `effective_buffs` / `effective_move` use at runtime, so the picker and
    the simulator agree on what counts as a "Canoptek" / "Plague Marines"
    / Aspect-or-Bike unit.
    """
    def _profile(u):
        return u.profile if hasattr(u, "profile") else u
    def _pts(u) -> float:
        return float(_profile(u).points_cost)
    def _kw(u) -> set:
        return set(_profile(u).unit_keywords or ())
    def _name(u) -> str:
        return _profile(u).name or ""

    total = sum(_pts(u) for u in units)
    if total <= 0:
        return 0.0

    if det.canoptek_plus_one_to_wound:
        matched = sum(_pts(u) for u in units if _name(u).startswith("Canoptek"))
    elif det.plague_marines_plus_one_to_wound:
        matched = sum(_pts(u) for u in units if _name(u) == "Plague Marines")
    elif det.aspect_warrior_or_bike_plus_one_move:
        matched = sum(
            _pts(u) for u in units if _name(u) in ASPECT_WARRIOR_OR_BIKE_NAMES
        )
    elif det.vehicles_reroll_hit_ones:
        # VEHICLE already drives `preferred_composition="vehicle"`, but the
        # keyword affinity adds an extra nudge so Ironstorm dominates when
        # the army is genuinely tank-heavy rather than relying on the
        # chassis-dominant heuristic alone.
        matched = sum(_pts(u) for u in units if "VEHICLE" in _kw(u))
    else:
        return 0.0

    fraction = matched / total
    if fraction >= 0.3:
        return 20.0
    if fraction >= 0.15:
        return 10.0
    return 0.0


def _score_detachment_for_army(
    det: Detachment,
    composition: Dict[str, float],
    units=None,
) -> float:
    """
    Score a detachment against an army composition. +10 if the detachment's
    `preferred_composition` matches the dominant chassis tag; 0 otherwise.
    An untagged ("") detachment is treated as "balanced".

    If `units` is provided, ADD a keyword-affinity bonus for the four #126
    second detachments whose buff fires only on specific datasheet keywords
    (Canoptek / Plague Marines / Aspect-or-Bike / VEHICLE) — see
    `_keyword_affinity_score`. The two-stage score lets the chassis tag
    drive coarse picks (which composition is dominant) while the keyword
    affinity layers in finer disambiguation (a Necron army that is 40%
    Canoptek points tilts firmly to Canoptek Court, not Awakened Dynasty).
    """
    dominant = _dominant_composition(composition)
    pref = det.preferred_composition or "balanced"
    score = 10.0 if pref == dominant else 0.0
    if units is not None:
        score += _keyword_affinity_score(det, units)
    return score


def effective_move(unit) -> float:
    """Movement allowance for `unit` after detachment passives.

    Reads `unit.profile.move` and adds any detachment-side movement bonus
    that gates on the attacker. Currently only Saim-Hann Wild Host
    (`aspect_warrior_or_bike_plus_one_move`) — Aspect Warriors and Bike
    chassis units gain +1" Movement.

    Falls back cleanly when the unit has no army_ref / no detachment, so
    catalogue and unit-test code paths that construct bare Units still
    work. Cited as `SAIM_HANN_WILD_HOST.aspect_warrior_or_bike_plus_one_move`.
    """
    base = float(getattr(unit.profile, "move", 6.0) or 6.0)
    army = getattr(unit, "army_ref", None)
    if army is None:
        return base
    try:
        det = army.resolve_detachment()
    except Exception:
        det = None
    if det is None:
        return base
    if getattr(det, "aspect_warrior_or_bike_plus_one_move", False):
        name = getattr(unit.profile, "name", "") or ""
        if name in ASPECT_WARRIOR_OR_BIKE_NAMES:
            return base + 1.0
    return base


def pick_detachment_for_army(
    faction: str,
    units,
    rng: Optional[random.Random] = None,
) -> Optional[Detachment]:
    """
    Pick a detachment that fits the army's composition.

    - If the faction has zero registered detachments, falls back to the
      `DEFAULT_BY_FACTION` resolver and returns whatever that gives (may be
      None for unmapped factions).
    - If exactly one detachment is registered, returns it deterministically.
    - Otherwise scores each candidate against the composition and picks
      weighted-randomly so the top-scoring detachment dominates (~60%) but
      lower-scoring variants still appear occasionally for variety.

    `units` accepts the same forms as `_army_composition_signature`.
    """
    if rng is None:
        rng = random.Random()

    keys = FACTION_DETACHMENTS.get(faction, ())
    if not keys:
        return default_detachment_for_faction(faction)

    if len(keys) == 1:
        return DETACHMENTS[keys[0]]

    candidates = [DETACHMENTS[k] for k in keys if k in DETACHMENTS]
    if not candidates:
        return default_detachment_for_faction(faction)
    if len(candidates) == 1:
        return candidates[0]

    composition = _army_composition_signature(units)
    scores = [
        _score_detachment_for_army(d, composition, units=units)
        for d in candidates
    ]

    # Weight: best-scoring detachment gets a soft majority, not a landslide.
    # With +10 for a match and 0 otherwise, exp(s / 25) yields a ~60/40 split
    # between matching vs non-matching in the N=2 case
    # (exp(0.4) / (exp(0.4) + 1) ≈ 0.598). Variants still surface so the
    # picker doesn't collapse to a deterministic best.
    import math
    weights = [math.exp(s / 25.0) for s in scores]
    return rng.choices(candidates, weights=weights, k=1)[0]
