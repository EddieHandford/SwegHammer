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

from dataclasses import dataclass, field
from typing import Dict, Optional


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

    # Morale
    ld_bonus: int = 0                    # +N to friendly Ld (lower target)
    enemy_ld_penalty: int = 0            # -N to enemy Ld (higher target)


# ---------------------------------------------------------------------------
# Canonical detachments — start small, one per major faction
# ---------------------------------------------------------------------------

GLADIUS_TASK_FORCE = Detachment(
    name="Gladius Task Force",
    faction="Adeptus Astartes",
    notes=(
        "Combat Doctrines: lossy approximation as army-wide re-roll wound 1s. "
        "Real rule rotates through Devastator/Tactical/Assault doctrines."
    ),
    reroll_wound_ones=True,
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
        "lone Warrior squads get nothing."
    ),
    reanimate_per_round=1,
    bonus_to_hit_when_led=True,
)

INVASION_FLEET = Detachment(
    name="Invasion Fleet",
    faction="Tyranids",
    notes=(
        "Shadow in the Warp: enemies have -1 Ld for Battleshock. Real rule "
        "is range-gated; we apply army-wide."
    ),
    enemy_ld_penalty=1,
)

WAAAGH_DETACHMENT = Detachment(
    name="WAAAGH! Tribe",
    faction="Orks",
    notes=(
        "Always-on +1 Attack on every weapon: approximates the once-per-game "
        "WAAAGH! plus the Orks-be-Orks aggression baseline."
    ),
    plus_one_attack=1,
)

NOBLE_LANCE = Detachment(
    name="Noble Lance",
    faction="Imperial Knights",
    notes=(
        "Code Chivalric: lossy as army-wide +1 to wound. Real rule has "
        "conditional triggers (charged turn, lance keyword)."
    ),
    plus_one_to_wound=True,
)

HALLOWED_MARTYRS = Detachment(
    name="Hallowed Martyrs",
    faction="Adepta Sororitas",
    notes=(
        "Sacrifice-themed: +1 to wound army-wide. Real rule triggers off "
        "destroyed Sororitas units; we apply it always-on for the MVP."
    ),
    plus_one_to_wound=True,
)

SHIELD_HOST = Detachment(
    name="Shield Host",
    faction="Adeptus Custodes",
    notes=(
        "Custodes durability: +1 to armour saves army-wide (cap at 2+). "
        "Approximates the multiple bespoke save-stacking rules in 10e."
    ),
    plus_one_save=True,
)

SKITARII_HUNTER_COHORT = Detachment(
    name="Skitarii Hunter Cohort",
    faction="Adeptus Mechanicus",
    notes=(
        "Conqueror Doctrina Imperatives: lossy as army-wide re-roll hit 1s. "
        "Real rule rotates between offensive / defensive imperatives."
    ),
    reroll_hit_ones=True,
)

INQUISITION_TASK_FORCE = Detachment(
    name="Inquisition Task Force",
    faction="Agents of the Imperium",
    notes=(
        "Inquisitorial Authority: re-roll hit 1s army-wide for the assembled "
        "Imperial agents. Real rule is bespoke per Inquisitor archetype."
    ),
    reroll_hit_ones=True,
)

COMBINED_REGIMENT = Detachment(
    name="Combined Regiment",
    faction="Astra Militarum",
    notes=(
        "Fire Orders: lossy as army-wide +1 to hit. Real rule is officer-gated "
        "single-target buffs (FRFSRF, Take Aim, etc.)."
    ),
    plus_one_to_hit=True,
)

TELEPORT_STRIKE_FORCE = Detachment(
    name="Teleport Strike Force",
    faction="Grey Knights",
    notes=(
        "Teleportarium precision: army-wide re-roll wound 1s. Real rule "
        "includes deep strike and bespoke psychic mechanics."
    ),
    reroll_wound_ones=True,
)

BATTLE_HOST = Detachment(
    name="Battle Host",
    faction="Aeldari",
    notes=(
        "Aspect of the Path: lossy as army-wide re-roll hit 1s. Real rule "
        "rotates +1 to hit / +1 to wound per Aspect Path."
    ),
    reroll_hit_ones=True,
)

SKYSPLINTER_ASSAULT = Detachment(
    name="Skysplinter Assault",
    faction="Drukhari",
    notes=(
        "Hit-and-run raiders: approximated as army-wide re-roll wound 1s. "
        "Real rule grants +1 to wound on the turn a unit charged."
    ),
    reroll_wound_ones=True,
)

MONTKA = Detachment(
    name="Mont'ka",
    faction="T'au Empire",
    notes=(
        "Killing Blow doctrine: lossy as army-wide +1 to hit. Real rule "
        "alternates between Mont'ka (offensive) and Kauyon (defensive)."
    ),
    plus_one_to_hit=True,
)

PACTBOUND_ZEALOTS = Detachment(
    name="Pactbound Zealots",
    faction="Chaos Space Marines",
    notes=(
        "Dark Pacts: lossy as army-wide re-roll wound 1s. Real rule grants "
        "Lethal Hits or Sustained Hits at the cost of Battleshock checks."
    ),
    reroll_wound_ones=True,
)

PLAGUE_COMPANY = Detachment(
    name="Plague Company",
    faction="Death Guard",
    notes=(
        "Disgustingly Resilient: army-wide Feel No Pain 5+ approximation. "
        "Real rule has Contagions and bespoke aura mechanics layered in."
    ),
    fnp=5,
)

CULT_OF_MAGIC = Detachment(
    name="Cult of Magic",
    faction="Thousand Sons",
    notes=(
        "Psychic mastery: army-wide +1 to wound PLUS end-of-round Cabal "
        "Points → Doombolt mortal-wound payload (median D3 = 2 MWs to "
        "the highest-threat enemy). The mortal-wound stream is what "
        "calibrates Thousand Sons up from a base ~40% sim WR closer "
        "to the real 54% tournament number."
    ),
    plus_one_to_wound=True,
    psychic_mortal_wounds_per_round=2,
)

BERZERKER_WARBAND = Detachment(
    name="Berzerker Warband",
    faction="World Eaters",
    notes=(
        "Blood Tithe frenzy: lossy as army-wide +1 to hit. Real rule spends "
        "Blood Tithe points on a roster of escalating effects."
    ),
    plus_one_to_hit=True,
)

DAEMONIC_INCURSION = Detachment(
    name="Daemonic Incursion",
    faction="Chaos Daemons",
    notes=(
        "Shadow of Chaos: lossy as army-wide +1 to hit. Real rule grants "
        "Battle-shock immunity and bespoke god-specific buffs in friendly zones."
    ),
    plus_one_to_hit=True,
)

FINAL_DAY = Detachment(
    name="Final Day",
    faction="Genestealer Cults",
    notes=(
        "Day of Reckoning: lossy as army-wide re-roll hit 1s. Real rule "
        "rotates between Ambush / Onslaught / Annihilation stages."
    ),
    reroll_hit_ones=True,
)

OATHBAND = Detachment(
    name="Oathband",
    faction="Leagues of Votann",
    notes=(
        "Voidsmen Oaths: lossy as army-wide re-roll hit 1s. Real rule grants "
        "Judgement Tokens that escalate effects vs marked enemy units."
    ),
    reroll_hit_ones=True,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DETACHMENTS: Dict[str, Detachment] = {
    "gladius_task_force":      GLADIUS_TASK_FORCE,
    "awakened_dynasty":        AWAKENED_DYNASTY,
    "invasion_fleet":          INVASION_FLEET,
    "waaagh_tribe":            WAAAGH_DETACHMENT,
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
    "plague_company":          PLAGUE_COMPANY,
    "cult_of_magic":           CULT_OF_MAGIC,
    "berzerker_warband":       BERZERKER_WARBAND,
    "daemonic_incursion":      DAEMONIC_INCURSION,
    "final_day":               FINAL_DAY,
    "oathband":                OATHBAND,
}

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
    "Orks":                     "waaagh_tribe",
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
    "Death Guard":              "plague_company",
    "Thousand Sons":            "cult_of_magic",
    "World Eaters":             "berzerker_warband",
    "Chaos Daemons":            "daemonic_incursion",
    "Genestealer Cults":        "final_day",
    "Leagues of Votann":        "oathband",
}


def default_detachment_for_faction(faction: str) -> Optional[Detachment]:
    """Return the canonical detachment for a faction, or None if unmapped."""
    key = DEFAULT_BY_FACTION.get(faction)
    return DETACHMENTS.get(key) if key else None
