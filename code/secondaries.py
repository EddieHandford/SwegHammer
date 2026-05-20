"""10e Pariah Nexus secondary-objective scoring.

The 10e tournament scoring layer that sits on top of primary objective control.
A real-meta game scores primary VP (up to ~50 over 5 rounds) plus secondary VP
(up to ~50 over 5 rounds, drawn from a pool of tactical missions). Without
secondaries the simulator over-rewards sticky-defensive play (Death Guard parks
on objectives and scores primary forever) and under-rewards mobile / killy
shapes that would in real play rack up secondary points by killing high-points
targets, wiping units, and projecting board control.

This module owns the post-round delta computation. The simulator snapshots
alive-units state at round-start, the secondary scorer computes per-side delta
at round-end, returning the secondary VP each side scored that round.

Citations:
    - simulator.secondary_bring_it_down (Wahapedia Pariah Nexus secondary)
    - simulator.secondary_no_prisoners (Wahapedia Pariah Nexus secondary)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Tuple

if TYPE_CHECKING:
    from .units import Unit


# Per-round VP caps (Pariah Nexus rule text).
BRING_IT_DOWN_CAP_PER_ROUND: int = 15
NO_PRISONERS_CAP_PER_ROUND: int = 15

# VP per qualifying kill.
BRING_IT_DOWN_VP_PER_KILL: int = 5    # 5 VP per enemy MONSTER/VEHICLE destroyed
NO_PRISONERS_VP_PER_UNIT: int = 5     # 5 VP per enemy UNIT destroyed


@dataclass
class RoundSnapshot:
    """Captured at start of each round; consumed at end of round to compute
    secondary VP. One snapshot per side.

    `unit_ids_alive` is the set of `id(unit)` for every alive Unit at the
    snapshot moment. We use Python object identity because Unit doesn't
    carry a stable UUID and profile.name isn't unique within an army
    (multiple Plague Marine squads share the name).
    """
    unit_ids_alive: frozenset
    monster_vehicle_ids_alive: frozenset


def take_snapshot(units: Iterable["Unit"]) -> RoundSnapshot:
    """Snapshot an army's alive units. Called at start of each round."""
    alive = [u for u in units if u.current_health > 0]
    unit_ids = frozenset(id(u) for u in alive)
    mv_ids = frozenset(
        id(u) for u in alive
        if _is_monster_or_vehicle(u)
    )
    return RoundSnapshot(
        unit_ids_alive=unit_ids,
        monster_vehicle_ids_alive=mv_ids,
    )


def _is_monster_or_vehicle(unit: "Unit") -> bool:
    """True if the unit's profile carries MONSTER or VEHICLE keyword.

    10e Bring it Down secondary text: "for each enemy MONSTER or VEHICLE
    model in your opponent's army that has been destroyed this battle
    round" — Wahapedia Pariah Nexus mission pack, Secondary Missions.
    """
    keywords = unit.profile.unit_keywords or ()
    return "MONSTER" in keywords or "VEHICLE" in keywords


def score_round_delta(
    snapshot: RoundSnapshot,
    enemy_units_now: Iterable["Unit"],
) -> Tuple[int, int]:
    """Compute (bring_it_down_vp, no_prisoners_vp) for the snapshotted side
    against the current enemy state.

    The snapshot is of the ENEMY at round start; we compare against the
    enemy's units NOW (end of round). Anything the snapshot had alive that
    isn't alive now was destroyed this round — credit to the snapshotting
    side as a kill.

    Returns (bring_it_down_vp, no_prisoners_vp), each capped per round.
    """
    alive_now_ids = frozenset(
        id(u) for u in enemy_units_now if u.current_health > 0
    )
    mv_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_monster_or_vehicle(u)
    )

    # Killed-this-round = was alive at round start, dead now.
    units_killed = snapshot.unit_ids_alive - alive_now_ids
    mv_killed = snapshot.monster_vehicle_ids_alive - mv_alive_now_ids

    bring_it_down_vp = min(
        BRING_IT_DOWN_CAP_PER_ROUND,
        len(mv_killed) * BRING_IT_DOWN_VP_PER_KILL,
    )
    no_prisoners_vp = min(
        NO_PRISONERS_CAP_PER_ROUND,
        len(units_killed) * NO_PRISONERS_VP_PER_UNIT,
    )
    return bring_it_down_vp, no_prisoners_vp
