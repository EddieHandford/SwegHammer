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
class RoundEnded:
    round_num: int


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
