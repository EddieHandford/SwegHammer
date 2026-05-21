"""
Enhancements (10e detachment-level character upgrades).

Each Detachment offers a list of Enhancements — one-off upgrades applied to a
single CHARACTER model at army-construction time. The rule (Wahapedia core
rules, "Enhancements"):

    "Each Enhancement is a one-off upgrade given to a CHARACTER model in your
     army, costing points... Each unique Enhancement can only be taken once
     per army. A CHARACTER can only have one Enhancement."

This module is the MVP version of that rule:

  1. `Enhancement` dataclass — frozen, hashable, with a small set of
     modifier fields that compose with the existing `LeaderAbility` aura.
  2. A starter registry of FIVE enhancements (one per high-touch Detachment
     we already wire end-to-end: Gladius, Awakened Dynasty, Cult of Magic,
     Plague Company, Mont'ka). Each carries a verbatim Wahapedia citation
     under `data/rule_citations.d/enhancements.json` (CLAUDE.md §10).
  3. A picker helper used by the army builder: given a Detachment, pick
     one Enhancement deterministically (via a seeded RNG) so calibration
     runs are reproducible.

Runtime composition:

  * `Unit.enhancement` (optional Enhancement) stores the assigned upgrade.
  * `leaders.effective_buffs(attacker)` reads the enhancement off any
     in-range friendly CHARACTER and merges its aura flags into the same
     buff dict it already builds for detachments + leader auras.
  * Defensive modifiers (`fnp_to_5`) compose with `Unit.receive_damage`
     via the same `bonus_fnp` path leaders already use — we tunnel the
     enhancement's FNP value through `effective_buffs(target)["fnp"]`.

The starter set leans on aura fields that already exist in
`leaders.effective_buffs`'s neutral buff dict (`plus_one_to_hit`,
`plus_one_to_wound`, `reroll_hit_ones`, `reroll_wound_ones`, `fnp`) so the
mechanic lands without simulator surgery. Bespoke once-per-battle effects
(Veil of Darkness teleport, Umbralefic Crystal redeploy) are deferred.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple


# ---------------------------------------------------------------------------
# Enhancement dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Enhancement:
    """A single Enhancement attached to one CHARACTER for the duration of a
    battle. Modifier fields compose with the unit's leader aura and the
    army's detachment passives via `leaders.effective_buffs`.

    Naming convention: aura fields mirror the corresponding LeaderAbility /
    Detachment flag name where possible so the merge in
    `leaders.effective_buffs` is one OR per field.
    """
    name: str
    detachment: str                   # registry key from code.detachments.DETACHMENTS
    points_cost: int                  # subtracted from the army budget at build time
    # ---- Offensive aura modifiers (apply when bearer's aura covers the
    # attacking unit). Same semantics as LeaderAbility fields. ----
    plus_one_to_hit_aura: bool = False
    plus_one_to_wound_aura: bool = False
    reroll_hit_ones_aura: bool = False
    reroll_wound_ones_aura: bool = False
    extra_attacks_melee: int = 0      # +N melee attacks for models in the bearer's unit
    # ---- Defensive aura modifier ----
    fnp_to_5: bool = False             # bearer's unit (and aura'd friendlies) gain FNP 5+


# ---------------------------------------------------------------------------
# Starter registry — ONE Enhancement per implemented Detachment
# ---------------------------------------------------------------------------

CHAMPION_OF_HUMANITY = Enhancement(
    name="Champion of Humanity",
    detachment="gladius_task_force",
    points_cost=20,
    # Real rule grants +1 to wound vs CHARACTER targets only. SwegHammer's
    # focus-fire heuristic targets the lowest-health enemy unit, which is
    # often (but not always) a CHARACTER. We apply +1 to wound aura-wide
    # to keep the buff mechanically observable; the citation flags this
    # as a (target-CHARACTER) simplification.
    plus_one_to_wound_aura=True,
)

HYPERPHASIC_FULCRUM = Enhancement(
    name="Hyperphasic Fulcrum",
    detachment="awakened_dynasty",
    points_cost=15,
    # LC-4 correction: BSData v10.6.0 verbatim rule is "CRYPTEK model only.
    # While the bearer is leading a unit, if that unit is wholly within
    # your army's Power Matrix, each time a model in that unit makes an
    # attack, re-roll a Wound roll of 1." Previous mapping (+1 to hit)
    # was a misread — the codex pattern is reroll-wound-1s, NOT +1 to hit.
    # The Power Matrix wholly-within gate is dropped (SwegHammer has no
    # Power Matrix model — it's a Necron deployment-zone token); we apply
    # the reroll-wound-1s aura unconditionally on the bearer's unit as an
    # approximation. CRYPTEK host_keyword gate not enforced at runtime —
    # the warlord picker still chooses the highest-points CHARACTER,
    # which is rarely a CRYPTEK in archetype builds (typically Overlord);
    # downstream calibration accepts the wider host as an MVP simplification.
    reroll_wound_ones_aura=True,
)

# LC-4 — Phasal Subjugator (Necrons Awakened Dynasty). BSData v10.6.0
# verbatim: "NECRONS model only. While a friendly NECRONS unit (excluding
# CHARACTER units) is within 6" of the bearer, each time a model in that
# unit makes an attack, add 1 to the hit roll." Maps directly onto the
# existing `plus_one_to_hit_aura` field — the enhancement aura is
# bodyguard-gated by the `in_range_leaders` 6" check that the host's
# LeaderAbility already enforces. Strictly +1 to hit on attacks made by
# the led unit, both ranged and melee.
PHASAL_SUBJUGATOR = Enhancement(
    name="Phasal Subjugator",
    detachment="awakened_dynasty",
    points_cost=25,
    plus_one_to_hit_aura=True,
)

# LC-4 — Veiled Blade (Custodes Shield Host). BSData v10.6.0 verbatim:
# "Add 2 to the Attacks characteristic of the bearer's melee weapons. Once
# per battle, at the start of any Command phase, triple the bearer's
# Objective Control characteristic until the end of the turn." Maps onto
# `extra_attacks_melee=2`. The OC-triple secondary clause is dropped —
# SwegHammer's objective control model doesn't gate buffs through the OC
# stat in a way that benefits from a single-character-once-per-battle
# triple. APPROXIMATION: the +2 attacks is applied unit-wide on the
# bearer's squad (via plus_one_attack stacking through effective_buffs)
# rather than bearer-only because SwegHammer's aura merge doesn't
# distinguish bearer-only buffs from bodyguard-unit buffs; this slightly
# overshoots the codex but the bearer in a Custodian Wardens / Guard
# squad is typically the single source of melee output anyway.
VEILED_BLADE = Enhancement(
    name="Veiled Blade",
    detachment="shield_host",
    points_cost=25,
    extra_attacks_melee=2,
)

# ARCANE_VORTEX (cult_of_magic) and LIVING_PLAGUE (plague_company) were
# removed per the 2026-05-15 fabrication audit (commit fa9a957). Both
# enhancements pointed at fabricated detachment keys that have been
# deleted from `code.detachments`. The enhancements themselves were
# wired against detachments that don't exist in the 10e codices;
# replacement enhancements land alongside real-codex detachment rebuilds.

PURETIDE_ENGRAM_NEUROCHIP = Enhancement(
    name="Puretide Engram Neurochip",
    detachment="montka",
    points_cost=15,
    # Real rule: "Once per battle, while the bearer is leading a unit, you
    # can re-roll a single Hit roll, a single Wound roll, and a single
    # Damage roll for that unit." SwegHammer collapses the
    # once-per-battle limit to a permanent re-roll hit 1s aura — across
    # a five-round game the gameplay impact is roughly equivalent in
    # expected hits.
    reroll_hit_ones_aura=True,
)


# Registry keyed by Enhancement.name (display name; matches citation key)
ENHANCEMENTS: Dict[str, Enhancement] = {
    e.name: e for e in (
        CHAMPION_OF_HUMANITY,
        HYPERPHASIC_FULCRUM,
        PHASAL_SUBJUGATOR,
        VEILED_BLADE,
        PURETIDE_ENGRAM_NEUROCHIP,
    )
}


# Detachment-keyed grouping. Empty tuple means the detachment has no
# enhancements wired yet (most do — see ROADMAP).
ENHANCEMENTS_BY_DETACHMENT: Dict[str, Tuple[Enhancement, ...]] = {}
for _e in ENHANCEMENTS.values():
    ENHANCEMENTS_BY_DETACHMENT.setdefault(_e.detachment, tuple())
    ENHANCEMENTS_BY_DETACHMENT[_e.detachment] = (
        ENHANCEMENTS_BY_DETACHMENT[_e.detachment] + (_e,)
    )


def enhancements_for_detachment(detachment_key: str) -> Tuple[Enhancement, ...]:
    """Return the tuple of Enhancements offered by the given detachment key.

    Returns an empty tuple when the detachment has no wired enhancements.
    Detachment key matches `code.detachments.DETACHMENTS` (lowercase,
    underscore-separated).
    """
    return ENHANCEMENTS_BY_DETACHMENT.get(detachment_key, tuple())


def pick_enhancement(
    detachment_key: str,
    rng: Optional[random.Random] = None,
) -> Optional[Enhancement]:
    """Pick one Enhancement for a detachment, or None if none are wired.

    Used by the army builder to assign a starter enhancement to a single
    CHARACTER at construction time. The choice is RNG-driven so calibration
    runs vary list configurations across seeds, but determinism is preserved
    when the caller passes a seeded `random.Random`.
    """
    pool = enhancements_for_detachment(detachment_key)
    if not pool:
        return None
    if rng is None:
        rng = random.Random()
    return rng.choice(pool)
