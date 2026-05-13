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

    # Healing / recovery
    reanimate_per_round: int = 0         # W restored per unit per round end

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
        "Reanimation Protocols: each unit regains 1 W per round end. Real "
        "rule rolls per model; this captures the headline durability boost."
    ),
    reanimate_per_round=1,
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


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DETACHMENTS: Dict[str, Detachment] = {
    "gladius_task_force":  GLADIUS_TASK_FORCE,
    "awakened_dynasty":    AWAKENED_DYNASTY,
    "invasion_fleet":      INVASION_FLEET,
    "waaagh_tribe":        WAAAGH_DETACHMENT,
    "noble_lance":         NOBLE_LANCE,
}

# Default detachment per faction (used when Army.detachment is None and a
# faction is known). Picks a sensible competitive default; user can override.
DEFAULT_BY_FACTION: Dict[str, str] = {
    "Adeptus Astartes":   "gladius_task_force",
    "Ultramarines":       "gladius_task_force",
    "Blood Angels":       "gladius_task_force",
    "Dark Angels":        "gladius_task_force",
    "Black Templars":     "gladius_task_force",
    "Space Wolves":       "gladius_task_force",
    "Salamanders":        "gladius_task_force",
    "Imperial Fists":     "gladius_task_force",
    "Iron Hands":         "gladius_task_force",
    "Raven Guard":        "gladius_task_force",
    "White Scars":        "gladius_task_force",
    "Necrons":            "awakened_dynasty",
    "Tyranids":           "invasion_fleet",
    "Orks":               "waaagh_tribe",
    "Imperial Knights":   "noble_lance",
}


def default_detachment_for_faction(faction: str) -> Optional[Detachment]:
    """Return the canonical detachment for a faction, or None if unmapped."""
    key = DEFAULT_BY_FACTION.get(faction)
    return DETACHMENTS.get(key) if key else None
