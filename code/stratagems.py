"""
Stratagems and the Command Point (CP) economy.

10e armies pick a Detachment that grants 6 detachment-specific Stratagems on
top of the universal Core Stratagems every army can use. Stratagems cost CP
and fire on specific triggers during specific phases — they're the lever real
tournament play uses to swing close fights.

Sources for every stratagem entry are cited in
`data/rule_citations.d/stratagems.json` per CLAUDE.md §10.

Audit history (2026-05-15, commit fa9a957): 11 fabricated stratagems were
removed from this file — they had no Wahapedia equivalent. (2026-05-16,
#197): the Warhost (Aeldari) detachment stratagem set was completed —
Lightning-Fast Reactions + Fire and Fade survived the audit; the remaining
four real codex stratagems (Skyborne Sanctuary, Feigned Retreat, Blitzing
Firepower, Webway Tunnel) have been added. The current entries are: the
four universal Core Stratagems (verbatim 10e), the six real Warhost
(Aeldari) stratagems, and Disgustingly Resilient (DG) which was
re-anchored to Virulent Vectorium at 2CP. Per-detachment real stratagem
sets for other factions are wired in follow-up per-faction PRs.

Dispatch model:
  * `name` — display label.
  * `cp_cost` — integer CP price.
  * `phase` — when the stratagem may legally fire ("command", "movement",
    "shooting", "charge", "fight", or "any").
  * `trigger` — a short string identifier the simulator branches on at the
    relevant event (e.g. "failed_wound_roll", "vehicle_charges",
    "enemy_landed_fight_kill", "friendly_character_near_charge_target").
  * `effect` — a short string identifier the simulator branches on when
    applying the stratagem's effect (e.g. "reroll_one_failed_roll",
    "out_of_sequence_fight", "d3_mortal_wounds", "3_inch_move_into_engagement").
  * `once_per_battle` — for non-Core stratagems with a per-game cap. None of
    the four universals are once-per-battle; the flag is here for #104.

The Stratagem is intentionally a string-identifier dispatcher rather than
holding a callable so it stays hashable / frozen-dataclass friendly and
serialises cleanly to event-log / Streamlit replays.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Stratagem:
    """A single Stratagem entry. Frozen + hashable so it can live in a
    Detachment's stratagems tuple and round-trip through the event log."""
    name: str
    cp_cost: int
    phase: str                           # "command" / "movement" / "shooting" / "charge" / "fight" / "any"
    trigger: str                         # identifier dispatched on by the simulator
    effect: str                          # identifier dispatched on by the simulator
    once_per_battle: bool = False


# ---------------------------------------------------------------------------
# Universal Core Stratagems
# ---------------------------------------------------------------------------
# Every army may spend these regardless of detachment. Cited in
# data/rule_citations.d/stratagems.json — keys are Stratagem.<name>.

COMMAND_RE_ROLL = Stratagem(
    name="Command Re-Roll",
    cp_cost=1,
    phase="any",
    trigger="failed_roll",
    effect="reroll_one_failed_roll",
)

COUNTER_OFFENSIVE = Stratagem(
    name="Counter-Offensive",
    cp_cost=2,
    phase="fight",
    trigger="enemy_unit_just_fought",
    effect="out_of_sequence_fight",
)

TANK_SHOCK = Stratagem(
    name="Tank Shock",
    cp_cost=1,
    phase="charge",
    trigger="vehicle_charges",
    effect="d3_mortal_wounds_to_charge_target",
)

HEROIC_INTERVENTION = Stratagem(
    name="Heroic Intervention",
    cp_cost=1,
    phase="charge",
    trigger="enemy_charges_near_friendly_character",
    effect="3_inch_move_into_engagement",
)


UNIVERSAL_STRATAGEMS: Tuple[Stratagem, ...] = (
    COMMAND_RE_ROLL,
    COUNTER_OFFENSIVE,
    TANK_SHOCK,
    HEROIC_INTERVENTION,
)


# ---------------------------------------------------------------------------
# Warhost (Aeldari) — six real detachment stratagems
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost
# The fabrication audit (commit fa9a957) confirmed Lightning-Fast Reactions
# and Fire and Fade as real entries; the remaining four (Skyborne Sanctuary,
# Feigned Retreat, Blitzing Firepower, Webway Tunnel) were added in #197
# from the Wahapedia stratagem list. The codex detachment name is "Warhost"
# (the launch-index name "Battle Host" was renamed).

LIGHTNING_FAST_REACTIONS = Stratagem(
    name="Lightning-Fast Reactions",
    cp_cost=1,
    phase="any",
    trigger="vulnerable_friendly_aeldari_unit",
    effect="plus_one_save_for_round",
)

FIRE_AND_FADE = Stratagem(
    name="Fire and Fade",
    cp_cost=1,
    phase="shooting",
    trigger="friendly_aeldari_unit_about_to_shoot",
    effect="reroll_hits_shooting_for_round",
)

# Skyborne Sanctuary: end of Fight phase, an AELDARI INFANTRY unit not in
# engagement range and wholly within 6" of a friendly AELDARI TRANSPORT can
# embark within it. Defensive re-embark; we approximate the offensive
# value via the same transient_plus_one_save flag (the canonical use case
# is saving a shot-up unit from a follow-up activation).
SKYBORNE_SANCTUARY = Stratagem(
    name="Skyborne Sanctuary",
    cp_cost=1,
    phase="fight",
    trigger="end_of_fight_aeldari_infantry_near_transport",
    effect="plus_one_save_for_round",
)

# Feigned Retreat: your Movement phase, just after an AELDARI INFANTRY unit
# Falls Back — until end of turn the unit can still shoot and declare a
# charge despite having Fallen Back. We approximate the offensive value
# via transient_assault_this_round (lets it shoot the same round it
# repositioned, the closest single-flag stand-in).
FEIGNED_RETREAT = Stratagem(
    name="Feigned Retreat",
    cp_cost=1,
    phase="movement",
    trigger="friendly_aeldari_infantry_just_fell_back",
    effect="transient_assault_for_round",
)

# Blitzing Firepower: your Shooting phase, when an AELDARI unit is selected
# to shoot — until end of phase its ranged weapons gain [SUSTAINED HITS 1]
# vs targets within 12" (or improve to 5+ Critical Hit if already having
# the ability). Approximated as +1 to hit shooting for the round, the
# nearest one-flag stand-in for the Sustained-Hits uplift.
BLITZING_FIREPOWER = Stratagem(
    name="Blitzing Firepower",
    cp_cost=1,
    phase="shooting",
    trigger="aeldari_unit_about_to_shoot_short_range",
    effect="plus_one_to_hit_shooting_for_round",
)

# Webway Tunnel: end of opponent's Fight phase, an AELDARI INFANTRY unit
# wholly within 9" of a battlefield edge and not in engagement range may
# enter Strategic Reserves. SwegHammer's reserve model is a single
# arrival queue with no mid-battle re-entry hook, so this stratagem is
# wired in but resolves as a defensive save buff (+1 save) — the
# strongest single-flag stand-in for "pull the unit off the table to
# avoid the next attack" while the reserves hook is not implemented.
WEBWAY_TUNNEL = Stratagem(
    name="Webway Tunnel",
    cp_cost=1,
    phase="fight",
    trigger="aeldari_infantry_near_board_edge_end_of_enemy_fight",
    effect="plus_one_save_for_round",
)

WARHOST_STRATAGEMS: Tuple[Stratagem, ...] = (
    LIGHTNING_FAST_REACTIONS,
    FIRE_AND_FADE,
    SKYBORNE_SANCTUARY,
    FEIGNED_RETREAT,
    BLITZING_FIREPOWER,
    WEBWAY_TUNNEL,
)


# ---------------------------------------------------------------------------
# Virulent Vectorium (Death Guard) — Disgustingly Resilient
# ---------------------------------------------------------------------------
# Wahapedia: https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium
# Disgustingly Resilient is the real DG stratagem — 2CP, found in the
# Virulent Vectorium detachment. Previously this constant was attached to
# the fabricated "Plague Company" detachment at 1CP; the fabrication audit
# (commit fa9a957) corrected the attachment and CP cost. The actual effect
# in the codex is more nuanced (-1 to wound vs the DG unit) than our current
# "-1 damage taken" simplification; treat the effect identifier as an
# APPROXIMATION pending a proper Virulent Vectorium detachment rebuild.

DISGUSTINGLY_RESILIENT = Stratagem(
    name="Disgustingly Resilient",
    cp_cost=2,
    phase="any",
    trigger="wounded_friendly_dg_unit",
    effect="minus_one_damage_taken_for_round",
)


# ---------------------------------------------------------------------------
# CP economy
# ---------------------------------------------------------------------------

STARTING_CP: int = 3                     # Strike Force standard (10e core rules)
CP_PER_COMMAND_PHASE: int = 1
CP_CAP: int = 6                          # 10e core: armies can't bank more than 6 CP


def award_command_phase_cp(army) -> None:
    """Grant the start-of-Command-phase CP, capped at CP_CAP.

    Called by Battle._run_round at the top of every round. The Strike Force
    starting allotment (STARTING_CP) is set on Army.__init__ — this function
    handles the per-round drip only.
    """
    army.command_points = min(CP_CAP, army.command_points + CP_PER_COMMAND_PHASE)


def stratagems_for_army(army) -> Tuple[Stratagem, ...]:
    """Every Stratagem this army can fire — the four universals plus any
    detachment-specific stratagems exposed on
    `Army.resolve_detachment().stratagems`.
    """
    extra: Tuple[Stratagem, ...] = ()
    det = army.resolve_detachment() if hasattr(army, "resolve_detachment") else None
    if det is not None:
        extra = tuple(getattr(det, "stratagems", ()) or ())
    return UNIVERSAL_STRATAGEMS + extra


__all__ = [
    "Stratagem",
    "COMMAND_RE_ROLL",
    "COUNTER_OFFENSIVE",
    "TANK_SHOCK",
    "HEROIC_INTERVENTION",
    "UNIVERSAL_STRATAGEMS",
    # Warhost (Aeldari) — six real stratagems
    "LIGHTNING_FAST_REACTIONS",
    "FIRE_AND_FADE",
    "SKYBORNE_SANCTUARY",
    "FEIGNED_RETREAT",
    "BLITZING_FIREPOWER",
    "WEBWAY_TUNNEL",
    "WARHOST_STRATAGEMS",
    # Virulent Vectorium (Death Guard) — Disgustingly Resilient (re-anchored)
    "DISGUSTINGLY_RESILIENT",
    # CP economy
    "STARTING_CP",
    "CP_PER_COMMAND_PHASE",
    "CP_CAP",
    "award_command_phase_cp",
    "stratagems_for_army",
]
