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
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    from .units import Unit
    from .map import Map


# Per-round VP caps (Pariah Nexus rule text, tuned 2026-05-20).
#
# Initial values (5 VP per event, 15 VP/round caps) regressed MAE from
# 6.17 -> 9.72 by over-rewarding elite low-count factions (Custodes,
# Marines) who avoid being scored against and punishing horde factions
# (Orks, Tyranids, Votann) who are easy Cull/No-Prisoners targets.
#
# Tuned to match real Pariah Nexus magnitudes: ~3 VP per qualifying
# event with smaller per-round caps. This brings total secondary VP
# per game to ~40 (vs ~75 primary), matching the real-meta ratio.
BRING_IT_DOWN_CAP_PER_ROUND: int = 8
NO_PRISONERS_CAP_PER_ROUND: int = 5
ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND: int = 3
BEHIND_ENEMY_LINES_CAP_PER_ROUND: int = 3
CULL_THE_HORDE_CAP_PER_ROUND: int = 3
ASSASSINATION_CAP_PER_ROUND: int = 4

# VP per qualifying kill (matches real Pariah Nexus rule magnitudes).
BRING_IT_DOWN_VP_PER_KILL: int = 3    # 3 VP per enemy MONSTER/VEHICLE destroyed
NO_PRISONERS_VP_PER_UNIT: int = 3     # 3 VP per enemy UNIT destroyed
CULL_THE_HORDE_VP_PER_UNIT: int = 3   # 3 VP per enemy horde-unit destroyed
ASSASSINATION_VP_PER_CHAR: int = 3    # 3 VP per enemy CHARACTER destroyed
ASSASSINATION_WARLORD_BONUS_VP: int = 1  # +1 VP if enemy Warlord destroyed (real Pariah Nexus rule)

# SC4-B — position-tracking secondary thresholds.
# Real Pariah Nexus Engage on All Fronts (Wahapedia):
#   "Score 2 VP if you have one or more units from your army wholly within
#    two table quarters. Score 3 VP instead if you have one or more units
#    from your army wholly within three different table quarters. Score 5 VP
#    instead if you have one or more units from your army wholly within all
#    four table quarters."
# Real Pariah Nexus Behind Enemy Lines: "Score 4 VP if you have one or more
# qualifying units in your opponent's deployment zone at the end of your
# Command phase."
# Source: https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-mission-pack/
# Cited as `simulator.secondary_engage_on_all_fronts` and
# `simulator.secondary_behind_enemy_lines`.
ENGAGE_QUADRANTS_REQUIRED: int = 2    # minimum quadrants to score any Engage VP
ENGAGE_VP_TWO_QUADRANTS: int = 2      # 2 VP for 2 quadrants
ENGAGE_VP_THREE_QUADRANTS: int = 3    # 3 VP for 3 quadrants
ENGAGE_VP_FOUR_QUADRANTS: int = 5     # 5 VP for all 4 quadrants
BEHIND_ENEMY_LINES_VP: int = 4        # 4 VP if any alive unit in enemy DZ (real rule)
ENGAGE_ON_ALL_FRONTS_VP: int = 3      # legacy alias (still used by tests); equals 3-quadrant tier

# SC4-C — horde-threshold + character-flag.
CULL_THE_HORDE_MIN_MODELS: int = 10   # unit counts as "horde" if started 10+ strong

# CUSTODES-UNPARK — elite-army secondary modifier.
#
# Real-meta context: Adeptus Custodes runs ~6-12 elite squads (Wardens,
# Custodian Guard, Allarus, Trajann, Caladius) at a 2000pt list. Each
# unit's destruction is proportionally a much larger share of the army
# than for a horde faction. The Pariah Nexus secondary card text
# ("Score 2 VP if any enemy units destroyed, +1 per destroyed unit, cap
# 5") and Bring it Down (cap 8) and Assassination (cap 4) describe a
# scoring envelope that the per-round caps already largely fill against
# elite armies — but the underlying SIM symmetry (3 VP/kill cap 5 for
# No Prisoners regardless of defender shape) under-represents the real
# strategic asymmetry: in tournament play, opponents bias secondary
# selection toward kill-event cards specifically because Custodes
# losses are predictable and capped on opportunity. The sim's
# round-snapshot delta misses this list-selection effect.
#
# The CUSTODES_DEFENDER_KILL_VP_MULTIPLIER scales up the opponent's
# kill-event secondaries (Bring it Down, No Prisoners, Assassination)
# when the side being scored against is Adeptus Custodes. Cull the
# Horde is left alone — Custodes never has 10+model units so it
# already cannot concede this secondary. Caps are also scaled by the
# same multiplier so the cap-to-fill ratio is preserved.
#
# Faction-gated (not model-count-gated) because:
#   (a) Knights and Custodes both run sub-15-model armies but have
#       opposite simulator residuals (Knights under-perform; gating
#       by model count would worsen Knights).
#   (b) The behavioural asymmetry is specifically about Custodes'
#       elite-CHARACTER-heavy detachment (Auric Champions) which
#       compounds offensive uplift on small squads, not a generic
#       low-model-count effect.
#
# Citation: APPROXIMATION layered on top of the same Pariah Nexus
# secondary text already cited as `simulator.secondary_bring_it_down`,
# `simulator.secondary_no_prisoners`, and `simulator.secondary_assassination`.
# The multiplier is cited separately as
# `simulator.secondary_elite_army_modifier` so the cite-audit can find it.
CUSTODES_DEFENDER_KILL_VP_MULTIPLIER: float = 1.5
CUSTODES_FACTION_TAG: str = "Adeptus Custodes"


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
    enemy_warlord_uid: Optional[int] = None,
    defender_faction: Optional[str] = None,
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

    CUSTODES-UNPARK — when `defender_faction == "Adeptus Custodes"`, the
    per-kill VP and per-round caps for Bring it Down, No Prisoners, and
    Assassination are scaled by `CUSTODES_DEFENDER_KILL_VP_MULTIPLIER`
    (1.5x). Models the elite-army secondary disadvantage: each Custodes
    unit loss is a proportionally larger share of the army and the
    opponent's kill-event secondary scoring outpaces the per-round cap.
    Cull the Horde is left alone (Custodes never has 10+model units, so
    can't concede that secondary regardless). Cited as
    `simulator.secondary_elite_army_modifier`.
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

    # CUSTODES-UNPARK — defender-faction-gated VP multiplier on the
    # kill-event secondaries. Cull the Horde is NOT scaled (Custodes
    # has no 10+model units to concede). Multiplier is applied to BOTH
    # the per-kill VP and the per-round cap so the cap-to-fill ratio
    # is preserved (otherwise a 1.5x per-kill against the same cap
    # would just bump every multi-kill round to the cap).
    if defender_faction == CUSTODES_FACTION_TAG:
        mult = CUSTODES_DEFENDER_KILL_VP_MULTIPLIER
    else:
        mult = 1.0

    bring_it_down_vp = min(
        int(BRING_IT_DOWN_CAP_PER_ROUND * mult),
        int(len(mv_killed) * BRING_IT_DOWN_VP_PER_KILL * mult),
    )
    no_prisoners_vp = min(
        int(NO_PRISONERS_CAP_PER_ROUND * mult),
        int(len(units_killed) * NO_PRISONERS_VP_PER_UNIT * mult),
    )
    cull_the_horde_vp = min(
        CULL_THE_HORDE_CAP_PER_ROUND,
        len(horde_killed) * CULL_THE_HORDE_VP_PER_UNIT,
    )
    assassination_vp = min(
        int(ASSASSINATION_CAP_PER_ROUND * mult),
        int(len(chars_killed) * ASSASSINATION_VP_PER_CHAR * mult),
    )
    # LC-5: +1 VP bonus if the enemy Warlord was among the destroyed
    # CHARACTERs this round. Real Pariah Nexus Assassination: "Score 3
    # VP at the end of the battle round if one or more enemy CHARACTER
    # models were destroyed this battle round. Score 4 VP instead if
    # the enemy WARLORD was among those models." Cited as
    # `simulator.warlord_designation`. The bonus is added on TOP of
    # the per-round cap (Pariah Nexus rule treats the 4 VP as the
    # alternative max, not as cap + bonus — but since our flat 3 VP
    # per CHARACTER already gets close to the 4 VP ceiling on one
    # kill, the bonus VP is small and we add it post-cap for clarity).
    if enemy_warlord_uid is not None and enemy_warlord_uid in chars_killed:
        assassination_vp += ASSASSINATION_WARLORD_BONUS_VP

    return (bring_it_down_vp, no_prisoners_vp,
            cull_the_horde_vp, assassination_vp)


def _is_tactical_secondary_active(round_num: int, side: str, tactical: str) -> bool:
    """LC-2: deterministic tactical-secondary draw mechanic.

    Real Pariah Nexus has 9 Tactical secondaries; players hold 2 at any
    time, drawn from the deck. Any specific Tactical card is active for
    ~2/9 (~22%) of turns on average. SwegHammer implements only 2
    Tactical secondaries (Engage on All Fronts, Behind Enemy Lines);
    in a 2-card pool, real meta would have BOTH always-active, so the
    pre-LC2 sim scored both every round — which over-rewarded elite
    low-count factions (Custodes +20.9 vs real 48%) that can always
    hit the Engage / BEL conditions.

    LC-2 model: each side scores AT MOST ONE Tactical secondary per
    round. Selection alternates deterministically by (round_num, side):
      * side A round 1, 3, 5: Engage
      * side A round 2, 4:     BEL
      * side B round 1, 3, 5: BEL
      * side B round 2, 4:     Engage
    This halves each tactical secondary's effective coverage to ~50%
    per side, approximating the 22% real-meta coverage scaled to a
    2-card pool. Deterministic per (round, side) so PYTHONHASHSEED=0
    reproduces matrices.
    """
    # Sides A and B get OPPOSITE secondaries each round so neither
    # side has the same hand twice in a row.
    odd_round = (round_num % 2 == 1)
    if side == "A":
        is_engage_turn = odd_round
    else:  # side B mirrors
        is_engage_turn = not odd_round
    if tactical == "engage":
        return is_engage_turn
    if tactical == "behind_enemy_lines":
        return not is_engage_turn
    return False


def score_position_delta(
    own_units: Iterable["Unit"],
    map_: "Map",
    own_is_army_a: bool,
    round_num: int = 1,
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

    # LC-2: gate Engage / BEL behind the per-round tactical-secondary
    # draw. Each side scores AT MOST ONE per round (the secondary that's
    # "active" this turn per the alternating schedule).
    side = "A" if own_is_army_a else "B"
    engage_active = _is_tactical_secondary_active(round_num, side, "engage")
    bel_active = _is_tactical_secondary_active(round_num, side,
                                                "behind_enemy_lines")
    # Engage tiered (2/3/5 VP for 2/3/4 quadrants) per real Pariah Nexus.
    engage_vp = 0
    if engage_active:
        n = len(quadrants_occupied)
        if n >= 4:
            engage_vp = ENGAGE_VP_FOUR_QUADRANTS
        elif n == 3:
            engage_vp = ENGAGE_VP_THREE_QUADRANTS
        elif n == 2:
            engage_vp = ENGAGE_VP_TWO_QUADRANTS
    bel_vp = BEHIND_ENEMY_LINES_VP if bel_active and in_enemy_dz else 0
    return engage_vp, bel_vp
