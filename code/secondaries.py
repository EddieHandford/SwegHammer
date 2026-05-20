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
    - simulator.secondary_engage_on_all_fronts (Wahapedia Pariah Nexus tactical)
    - simulator.secondary_behind_enemy_lines (Wahapedia Pariah Nexus tactical)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Tuple

if TYPE_CHECKING:
    from .units import Unit
    from .map import Map


# Per-round VP caps (Pariah Nexus rule text).
BRING_IT_DOWN_CAP_PER_ROUND: int = 15
NO_PRISONERS_CAP_PER_ROUND: int = 15
ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND: int = 5
BEHIND_ENEMY_LINES_CAP_PER_ROUND: int = 5
CULL_THE_HORDE_CAP_PER_ROUND: int = 5
ASSASSINATION_CAP_PER_ROUND: int = 10

# VP per qualifying kill.
BRING_IT_DOWN_VP_PER_KILL: int = 5    # 5 VP per enemy MONSTER/VEHICLE destroyed
NO_PRISONERS_VP_PER_UNIT: int = 5     # 5 VP per enemy UNIT destroyed
CULL_THE_HORDE_VP_PER_UNIT: int = 5   # 5 VP per enemy horde-unit (10+ models) destroyed
ASSASSINATION_VP_PER_CHAR: int = 5    # 5 VP per enemy CHARACTER destroyed

# SC4-B — position-tracking secondary thresholds.
ENGAGE_QUADRANTS_REQUIRED: int = 3    # need units in 3+ of 4 quadrants to score
BEHIND_ENEMY_LINES_VP: int = 5        # flat 5 VP if any alive unit in enemy DZ

# SC4-C — horde-threshold + character-flag.
CULL_THE_HORDE_MIN_MODELS: int = 10   # unit counts as "horde" if started 10+ strong


@dataclass
class RoundSnapshot:
    """Captured at start of each round; consumed at end of round to compute
    secondary VP. One snapshot per side.

    `unit_ids_alive` is the set of `id(unit)` for every alive Unit at the
    snapshot moment. We use Python object identity because Unit doesn't
    carry a stable UUID and profile.name isn't unique within an army
    (multiple Plague Marine squads share the name).

    SC4-C: also track `horde_unit_ids_alive` (units belonging to a
    starting-strength-≥10 squad — for Cull the Horde) and
    `character_ids_alive` (units carrying CHARACTER keyword — for
    Assassination).
    """
    unit_ids_alive: frozenset
    monster_vehicle_ids_alive: frozenset
    horde_unit_ids_alive: frozenset = frozenset()
    character_ids_alive: frozenset = frozenset()


def take_snapshot(units: Iterable["Unit"]) -> RoundSnapshot:
    """Snapshot an army's alive units. Called at start of each round."""
    alive = [u for u in units if u.current_health > 0]
    unit_ids = frozenset(id(u) for u in alive)
    mv_ids = frozenset(
        id(u) for u in alive
        if _is_monster_or_vehicle(u)
    )
    horde_ids = frozenset(
        id(u) for u in alive
        if _is_horde_unit(u)
    )
    char_ids = frozenset(
        id(u) for u in alive
        if _is_character(u)
    )
    return RoundSnapshot(
        unit_ids_alive=unit_ids,
        monster_vehicle_ids_alive=mv_ids,
        horde_unit_ids_alive=horde_ids,
        character_ids_alive=char_ids,
    )


def _is_monster_or_vehicle(unit: "Unit") -> bool:
    """True if the unit's profile carries MONSTER or VEHICLE keyword.

    10e Bring it Down secondary text: "for each enemy MONSTER or VEHICLE
    model in your opponent's army that has been destroyed this battle
    round" — Wahapedia Pariah Nexus mission pack, Secondary Missions.
    """
    keywords = unit.profile.unit_keywords or ()
    return "MONSTER" in keywords or "VEHICLE" in keywords


def _is_horde_unit(unit: "Unit") -> bool:
    """True if the unit belongs to a starting-strength-≥10 squad.

    10e Cull the Horde scoring rewards killing units that were 'big'
    to begin with — Termagant broods (30), Boyz squads (10-20),
    Cultist regiments (10-20). Per-model Unit instances share a
    `profile.starting_strength` if the mapper populates it; otherwise
    fall back to default-squad-size heuristic via `profile.count` /
    `profile.squad_size`, defaulting to 1.

    Sim simplification: this is checked per-Unit (per-model), not
    per-squad. Since each model is a separate Unit instance and they
    share `profile.name`, two squads of 10 Boyz produce 20 horde-unit
    snapshots. Per-round Cull cap (5 VP) keeps double-counting from
    inflating the secondary.
    """
    profile = unit.profile
    # Prefer explicit field if the mapper populates it.
    starting = getattr(profile, "starting_strength", None)
    if starting is None:
        starting = getattr(profile, "squad_size", None)
    if starting is None:
        starting = getattr(profile, "count", None)
    if starting is None:
        starting = 1
    return starting >= CULL_THE_HORDE_MIN_MODELS


def _is_character(unit: "Unit") -> bool:
    """True if the unit's profile carries the CHARACTER keyword.

    10e Assassination scoring rewards killing enemy CHARACTERs.
    EPIC HEROes and named characters all carry CHARACTER. Regular
    leaders (Captains, Lieutenants, Warbosses, etc.) also carry it.
    """
    keywords = unit.profile.unit_keywords or ()
    return "CHARACTER" in keywords


def score_round_delta(
    snapshot: RoundSnapshot,
    enemy_units_now: Iterable["Unit"],
) -> Tuple[int, int, int, int]:
    """Compute (bring_it_down_vp, no_prisoners_vp, cull_the_horde_vp,
    assassination_vp) for the snapshotted side against the current enemy
    state.

    The snapshot is of the ENEMY at round start; we compare against the
    enemy's units NOW (end of round). Anything the snapshot had alive
    that isn't alive now was destroyed this round — credit to the
    snapshotting side as a kill.

    Returns four per-round-capped secondary VP values:
      * bring_it_down_vp — MONSTER/VEHICLE kill credit
      * no_prisoners_vp — generic enemy-unit-destroyed credit
      * cull_the_horde_vp — kill credit for units that were ≥10 models
      * assassination_vp — kill credit for enemy CHARACTERs
    """
    alive_now_ids = frozenset(
        id(u) for u in enemy_units_now if u.current_health > 0
    )
    mv_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_monster_or_vehicle(u)
    )
    horde_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_horde_unit(u)
    )
    char_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_character(u)
    )

    # Killed-this-round = was alive at round start, dead now.
    units_killed = snapshot.unit_ids_alive - alive_now_ids
    mv_killed = snapshot.monster_vehicle_ids_alive - mv_alive_now_ids
    horde_killed = snapshot.horde_unit_ids_alive - horde_alive_now_ids
    chars_killed = snapshot.character_ids_alive - char_alive_now_ids

    bring_it_down_vp = min(
        BRING_IT_DOWN_CAP_PER_ROUND,
        len(mv_killed) * BRING_IT_DOWN_VP_PER_KILL,
    )
    no_prisoners_vp = min(
        NO_PRISONERS_CAP_PER_ROUND,
        len(units_killed) * NO_PRISONERS_VP_PER_UNIT,
    )
    cull_the_horde_vp = min(
        CULL_THE_HORDE_CAP_PER_ROUND,
        len(horde_killed) * CULL_THE_HORDE_VP_PER_UNIT,
    )
    assassination_vp = min(
        ASSASSINATION_CAP_PER_ROUND,
        len(chars_killed) * ASSASSINATION_VP_PER_CHAR,
    )
    return (bring_it_down_vp, no_prisoners_vp,
            cull_the_horde_vp, assassination_vp)


def score_position_delta(
    own_units: Iterable["Unit"],
    map_: "Map",
    own_is_army_a: bool,
) -> Tuple[int, int]:
    """Compute (engage_vp, behind_enemy_lines_vp) for one side at end-of-
    round given the side's currently-alive units, the battlefield map,
    and whether this side deployed in Army A's zone (low-y).

    Engage on All Fronts (Pariah Nexus tactical secondary, simplified):
        Score 5 VP if your alive units occupy 3+ of the 4 table
        quarters at end of round. Quarters are determined by dividing
        the map at (cx=width/2, cy=height/2). A quarter is "occupied"
        if at least one alive unit's position is inside it.

    Behind Enemy Lines (Pariah Nexus tactical secondary, simplified):
        Score 5 VP if any alive unit's position is within the
        opponent's deployment zone at end of round. Army A's enemy DZ
        is y >= map.height - map.deployment_width; Army B's enemy DZ
        is y <= map.deployment_width.

    Real-rule fidelity caveats:
    * Real Engage scores 2/3/5 VP for 2/3/4 quadrants and requires the
      occupying unit to be "wholly within" the quarter. Sim simplifies
      to a single 5 VP threshold at 3+ quadrants (position centroid).
    * Real BEL requires the unit "wholly within" the enemy DZ. Sim
      simplifies to position-inside-DZ check.
    Both simplifications preserve the secondary's directional
    incentive — projecting units forward / spreading across the map
    is rewarded, sticky-camping is not.
    """
    cx = map_.width / 2.0
    cy = map_.height / 2.0
    quadrants_occupied = set()
    in_enemy_dz = False

    if own_is_army_a:
        # Army A's enemy DZ is the high-y strip.
        enemy_dz_lo = map_.height - map_.deployment_width
        enemy_dz_hi = map_.height
    else:
        # Army B's enemy DZ is the low-y strip.
        enemy_dz_lo = 0.0
        enemy_dz_hi = map_.deployment_width

    for u in own_units:
        if u.current_health <= 0:
            continue
        pos = getattr(u, "position", None)
        if pos is None:
            continue
        ux, uy = pos
        # Quadrant detection: (low-x, low-y) = SW, (high-x, low-y) = SE,
        # (low-x, high-y) = NW, (high-x, high-y) = NE.
        qx = 0 if ux < cx else 1
        qy = 0 if uy < cy else 1
        quadrants_occupied.add((qx, qy))
        # Enemy DZ check.
        if enemy_dz_lo <= uy <= enemy_dz_hi:
            in_enemy_dz = True

    engage_vp = (
        ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND
        if len(quadrants_occupied) >= ENGAGE_QUADRANTS_REQUIRED
        else 0
    )
    bel_vp = BEHIND_ENEMY_LINES_VP if in_enemy_dz else 0
    return engage_vp, bel_vp
