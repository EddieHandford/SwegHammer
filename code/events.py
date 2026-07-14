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
    # Renderer-only model base footprint (see UnitProfile.base_shape).
    # Optional with defaults so legacy event logs without these fields keep
    # rendering as 32mm round bases.
    base_shape: str = "circle"
    base_diameter_mm: int = 32
    base_width_mm: int = 32
    base_length_mm: int = 32
    # The simulator models a codex squad as one Unit per model, all sharing a
    # squad_id (-1 = lone model). Carried in the snapshot so replay views can
    # aggregate per squad instead of per model. Defaulted for legacy logs.
    squad_id: int = -1
    # Per-model points cost, so the replay overview can report each side's
    # points remaining after every round. 0.0 on legacy logs suppresses the
    # points-remaining line rather than mis-reporting it.
    points_cost: float = 0.0


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
class TurnStarted:
    """A player's turn began within a vanilla (I-go-you-go) battle round.

    Emitted once per army per round from `_run_round_vanilla_turns`, before
    that army's Movement phase begins. Presentation-only: it carries no game
    state and gates no behaviour — it exists solely so a replay renderer
    (`round_overview` in `code/renderer.py`) can split a battle round's recap
    into one sub-chapter per player's turn, in true resolution order, instead
    of bucketing both players' events together by phase type. Not emitted
    from `_run_round_alternating`, which has no player-turn concept.
    """
    round_num: int
    army_name: str


@dataclass(frozen=True)
class UnitActivated:
    unit_uid: str
    army_name: str


@dataclass(frozen=True)
class PlayerTurnStarted:
    """One player's complete turn (Movement through Fight) is beginning.

    Emitted once per player-turn under vanilla I-go-U-go
    (`Battle._run_round_vanilla_turns`) so a renderer can group a round's
    events by which player's turn they happened in, instead of only by
    event type — without this boundary, a replay that aggregates "all
    moves this round" before "all shots this round" makes a correct
    full-turn I-go-U-go simulation look like a phase-by-phase alternating
    ruleset. NOT emitted by `_run_round_alternating` (that model has no
    discrete per-player turn to mark); renderers that don't see this event
    should fall back to their prior whole-round grouping.
    """
    army_name: str
    round_num: int


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
    (Command Re-Roll, Counter-Offensive, Tank Shock, or any detachment-
    specific stratagem added in #104). Renderers can
    ignore it freely — it's primarily for the event-log replay and for
    test assertions ("did our CP get spent?").
    """
    army_name: str
    stratagem_name: str
    cp_cost: int


@dataclass(frozen=True)
class DeadlyDemiseExploded:
    """A unit with the Deadly Demise X ability rolled a 6 on its demise d6
    and detonated, dealing X mortal wounds to every unit within 6".

    Wahapedia 10e core rule: when a model with Deadly Demise X is destroyed,
    roll one D6 BEFORE removing it from the battlefield (after resolving the
    attack that destroyed it). On a 6, each unit within 6" suffers X mortal
    wounds. The simulator interprets D3/D6/D3+3 codex variants as fixed
    integer expected values (D3→2, D6→3, D3+3→5). Cited as
    `simulator.deadly_demise`.

    Informational — the renderer can ignore freely; the mortal-wound dispatch
    has already mutated each victim's current_health by the time the event
    fires.
    """
    unit_uid: str                 # uid of the exploding unit
    mortals: int                  # X — mortal wounds applied to each victim
    victims: Tuple[str, ...]      # uids of the units that took the mortals


@dataclass(frozen=True)
class TransportEmbarked:
    """A passenger unit embarked inside a TRANSPORT (10e core).

    Emitted from `Battle._embark_pregame_passengers` at deploy time. The
    passenger is removed from the active battlefield (its position is set to
    the transport's position and the simulator skips its activations until
    it disembarks). Cited as `simulator.embark`.
    """
    transport_uid: str
    passenger_uid: str


@dataclass(frozen=True)
class TransportDisembarked:
    """A passenger unit disembarked from a TRANSPORT (10e core).

    Emitted by `Battle._maybe_disembark_before_move` (voluntary disembark at
    the start of the Movement phase) and by `Battle._destroyed_transport_disembark`
    (forced disembark when the transport is destroyed). `position` is the
    placed disembark location (within 3" of the transport's last position).
    `forced` is True iff this disembark was triggered by transport destruction.
    Cited as `simulator.disembark` / `simulator.destroyed_transport`.
    """
    transport_uid: str
    passenger_uid: str
    position: Tuple[float, float]
    forced: bool = False


@dataclass(frozen=True)
class WaaaghDeclared:
    """An Ork army declared WAAAGH! at the start of its Command phase.

    10e Orks army rule (once per battle). While active until end of the
    declaring turn: +1 to charge rolls for Ork units, Advance counts as a
    charge for the Fight sub-phase, and Ork attackers add +1 to melee
    wound rolls. SwegHammer currently models the +1-to-wound-melee leg as
    a `simulator.waaagh` gate read by `Unit.attack`; the charge/advance
    legs are descriptive (the AI picks WAAAGH! rounds to match a melee
    push but the gates aren't separately implemented yet).

    Renderers can ignore this event — the wound-roll math is applied via
    `Army.waaagh_round_unlocked` at attack time.
    """
    army_name: str
    round_num: int


@dataclass(frozen=True)
class OathTargetChosen:
    """An Adeptus Astartes army picked an enemy unit as its Oath of Moment
    target at the start of its Command phase.

    10e Adeptus Astartes army rule (every round). The Marine player picks
    one enemy unit; until the start of their next Command phase, every
    Marine attack against that unit re-rolls the hit roll (codex grants
    HIT re-rolls only, not wound re-rolls). The simulator's AI picks the
    highest-points enemy unit each round; Unit.attack reads
    `army.oath_target_uid` to gate the re-rolls. Cited as
    `simulator.oath_of_moment`.

    Informational — renderers can ignore this event; the re-roll math is
    applied at attack time via `Army.oath_target_uid`.
    """
    army_name: str
    round_num: int
    target_uid: str


@dataclass(frozen=True)
class BattleshockFailed:
    """A unit failed its Battleshock check this round and counts as OC 0."""
    unit_uid: str
    roll: int                   # 2d6 total
    target: int                 # Ld value


@dataclass(frozen=True)
class RoundEnded:
    round_num: int
    a_vp_total: int = 0         # running VP totals after this round's scoring (UNCAPPED)
    b_vp_total: int = 0
    # The real standing under the Pariah Nexus caps (primary <=50, secondary <=40,
    # challenger <= lifetime cap) — this is what decides the winner, so it is the
    # meaningful "who is ahead" figure for displays/audits. The uncapped totals
    # above can run past a ceiling and overstate a dominator's lead.
    a_vp_capped: int = 0
    b_vp_capped: int = 0


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
