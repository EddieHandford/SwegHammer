"""
Battle event types and the Subscriber protocol.

Events are immutable records of what happened during a Battle. The Battle
emits them; Subscribers consume them. Both the Streamlit replay renderer
and the Pygame live renderer read from this stream, and the calibration
sweep simply attaches no subscribers (zero overhead).

Adding a new event:
  1. Define a frozen dataclass below.
  2. Battle emits it via self._emit(...) at the appropriate point.
  3. Renderers handle (or ignore) it in their on_event() dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InitialUnit:
    """Snapshot of a unit at battle start, embedded in BattleStarted so a
    renderer can reconstruct the world without touching live Unit objects."""
    uid: str
    name: str
    army: str
    position: Tuple[float, float]
    max_health: float
    unit_keywords: Tuple[str, ...] = ()   # 10e keywords (INFANTRY, VEHICLE, MONSTER, ...) — used by the renderer for shape variety


@dataclass(frozen=True)
class BattleStarted:
    army_a_name: str
    army_b_name: str
    map_name: str
    units: Tuple[InitialUnit, ...]


@dataclass(frozen=True)
class RoundStarted:
    round_num: int


@dataclass(frozen=True)
class UnitActivated:
    unit_uid: str
    army_name: str


@dataclass(frozen=True)
class UnitMoved:
    unit_uid: str
    from_pos: Tuple[float, float]
    to_pos: Tuple[float, float]


@dataclass(frozen=True)
class UnitShot:
    attacker_uid: str
    target_uid: str
    damage: float
    target_hp_after: float
    target_alive_after: bool


@dataclass(frozen=True)
class UnitKilled:
    unit_uid: str


@dataclass(frozen=True)
class UnitAdvanced:
    """A unit elected to Advance (M + d6 movement, no shoot / charge)."""
    unit_uid: str
    advance_roll: int           # the d6 result
    total_movement: float       # M + d6 inches


@dataclass(frozen=True)
class UnitCharged:
    """A unit attempted a charge. `succeeded` is True iff 2d6 met the gap."""
    unit_uid: str
    target_uid: str
    distance: float
    roll: int                   # 2d6 total
    succeeded: bool


@dataclass(frozen=True)
class UnitFought:
    """A melee strike — shape mirrors UnitShot for renderer convenience."""
    attacker_uid: str
    target_uid: str
    damage: float
    target_hp_after: float
    target_alive_after: bool


@dataclass(frozen=True)
class ObjectiveScored:
    """End-of-round VP award for one objective."""
    objective_name: str
    army_name: Optional[str]    # None if contested / no scoring this round
    vp_awarded: int
    a_oc: int                   # combined OC each army had on the objective
    b_oc: int


@dataclass(frozen=True)
class UnitInfiltrated:
    """A unit with the Infiltrators ability deployed past its army's
    deployment line (Phase I)."""
    unit_uid: str
    position: Tuple[float, float]


@dataclass(frozen=True)
class UnitScouted:
    """A unit with the Scouts x" ability made its pre-Round 1 Normal Move
    (Phase I)."""
    unit_uid: str
    from_pos: Tuple[float, float]
    to_pos: Tuple[float, float]


@dataclass(frozen=True)
class UnitDeepStrike:
    """A unit with the Deep Strike ability arrived from Reserves at the
    start of a round from Round 2 onwards (Phase I)."""
    unit_uid: str
    position: Tuple[float, float]


@dataclass(frozen=True)
class UnitReanimated:
    """A previously-destroyed model in a REANIMATION-keyword unit was revived
    at the end of a Command Phase by Reanimation Protocols.

    We model squads as N single-model Unit instances; "revive a destroyed
    model" means re-marking a dead Unit's `current_health` back to its
    profile max. The renderer treats this like a Deep Strike arrival —
    a fresh body appears on the board at `position`.
    """
    unit_uid: str
    position: Tuple[float, float]


@dataclass(frozen=True)
class JudgementTokenAwarded:
    """A Votann opponent (i.e. an enemy unit fighting the Leagues of Votann)
    destroyed a Votann model and gained a Judgement Token.

    Tokens accumulate on the killer's unit for the rest of the battle and
    grant escalating re-roll buffs to subsequent Votann attacks against
    that target — modelling the canonical Eye of the Ancestors rule. The
    event is informational; the buff lookup is done live in `Unit.attack`
    via `Army.judgement_tokens[target_uid]` so renderers can safely ignore
    this event.
    """
    target_uid: str             # uid of the unit that just earned the token
    total_tokens: int           # cumulative tokens on that target after this kill


@dataclass(frozen=True)
class StratagemFired:
    """An army spent CP to activate a Stratagem.

    The simulator emits this whenever Battle resolves an effect dispatch
    (Command Re-Roll, Counter-Offensive, Tank Shock, Heroic Intervention,
    or any detachment-specific stratagem added in #104). Renderers can
    ignore it freely — it's primarily for the event-log replay and for
    test assertions ("did our CP get spent?").
    """
    army_name: str
    stratagem_name: str
    cp_cost: int


@dataclass(frozen=True)
class BattleshockFailed:
    """A unit failed its Battleshock check this round and counts as OC 0."""
    unit_uid: str
    roll: int                   # 2d6 total
    target: int                 # Ld value


@dataclass(frozen=True)
class RoundEnded:
    round_num: int
    a_vp_total: int = 0         # running VP totals after this round's scoring
    b_vp_total: int = 0


@dataclass(frozen=True)
class BattleEnded:
    winner: Optional[str]   # army name, or None for draw
    rounds: int


# ---------------------------------------------------------------------------
# Subscriber protocol
# ---------------------------------------------------------------------------

class Subscriber(Protocol):
    """Anything that wants to consume the battle event stream."""

    def on_event(self, event: object) -> None: ...


class EventLog:
    """Simple subscriber that records every event into a list for replay."""

    def __init__(self) -> None:
        self.events: List[object] = []

    def on_event(self, event: object) -> None:
        self.events.append(event)

    def __len__(self) -> int:
        return len(self.events)
