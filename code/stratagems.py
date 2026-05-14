"""
Stratagems and the Command Point (CP) economy.

10e armies pick a Detachment that grants 6 detachment-specific Stratagems on
top of the universal Core Stratagems every army can use. Stratagems cost CP
and fire on specific triggers during specific phases — they're the lever real
tournament play uses to swing close fights, and the reason "underrated"
factions (Necrons, Death Guard, Thousand Sons) hold their own against shooty
brick armies in our calibration.

This module models JUST the Stratagem dataclass and the four universal Core
Stratagems (Wahapedia core-rules page). Detachment-specific stratagems land
in a follow-up PR (issue #104) — they'll attach to `Detachment.stratagems`,
which already accepts a tuple.

Sources for the four universal entries are cited in
`data/rule_citations.d/stratagems.json` per CLAUDE.md §10.

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
    """Every Stratagem this army can fire. Today that's just the four
    universals; once #104 lands, this also folds in any detachment-specific
    stratagems exposed on `Army.resolve_detachment().stratagems`.
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
    "STARTING_CP",
    "CP_PER_COMMAND_PHASE",
    "CP_CAP",
    "award_command_phase_cp",
    "stratagems_for_army",
]
