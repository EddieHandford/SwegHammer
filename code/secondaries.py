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
    from .army import Army
    from .units import Unit
    from .map import Map


# Pool of recognised Pariah Nexus secondary keys. Used by `pick_secondaries`
# (assigns 2 Fixed + 2 Tactical to each army at battle start) and the
# `chosen` gate in `score_round_delta` / `score_position_delta`.
#
# Fixed Secondaries pool (10e Pariah Nexus, pick 2):
#   bring_it_down       — MONSTER/VEHICLE kill credit
#   no_prisoners        — generic unit-kill credit
#   cull_the_horde      — kill credit for 10+model squads
#   assassination       — CHARACTER kill credit (+1 if Warlord)
# Tactical Secondaries (pool of 9, draw 2 per round in real play):
#   engage_on_all_fronts — board-spread VP
#   behind_enemy_lines   — opponent DZ VP
# Source: https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-mission-pack/
# Cited as `simulator.secondary_selection`.
FIXED_SECONDARY_KEYS: Tuple[str, ...] = (
    "bring_it_down", "no_prisoners", "cull_the_horde", "assassination",
)
TACTICAL_SECONDARY_KEYS: Tuple[str, ...] = (
    "engage_on_all_fronts", "behind_enemy_lines",
)
ALL_SECONDARY_KEYS: Tuple[str, ...] = (
    FIXED_SECONDARY_KEYS + TACTICAL_SECONDARY_KEYS
)


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

    Per-unit secondary fix (No Prisoners / Cull the Horde):
    `alive_squad_ids` is the set of squad_id values (int >= 0) that had at
    least one alive model at snapshot time. A codex unit is considered
    destroyed this round only when ALL models sharing that squad_id have
    died — i.e. the squad_id is absent from the current alive set. Lone
    models (squad_id < 0) are already single-model units; their kills are
    tracked via `lone_unit_ids_alive` (id-based, unchanged semantics).
    `horde_squad_ids` is the subset of `alive_squad_ids` whose starting
    model count was >= CULL_THE_HORDE_MIN_MODELS (checked on any member).
    """
    unit_ids_alive: frozenset
    monster_vehicle_ids_alive: frozenset
    horde_unit_ids_alive: frozenset = frozenset()
    character_ids_alive: frozenset = frozenset()
    # Per-unit secondary fix fields:
    alive_squad_ids: frozenset = frozenset()    # squad_id values >= 0 alive at snapshot
    horde_squad_ids: frozenset = frozenset()    # subset of alive_squad_ids that are horde
    lone_unit_ids_alive: frozenset = frozenset()  # id(u) for lone models (squad_id < 0)
    horde_lone_ids_alive: frozenset = frozenset()  # lone ids that also qualify as horde


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
    # Per-unit secondary fix: track squad-level alive state for No Prisoners
    # and Cull the Horde. A codex unit is only destroyed when its LAST model
    # dies (all models sharing the same squad_id must be gone). Lone models
    # (squad_id < 0) are single-model units, tracked by object id separately.
    squad_alive: set = set()
    horde_squads: set = set()
    lone_ids: set = set()
    horde_lone_ids: set = set()
    for u in alive:
        sid = getattr(u, "squad_id", -1)
        if sid >= 0:
            squad_alive.add(sid)
            if _is_horde_unit(u):
                horde_squads.add(sid)
        else:
            lone_ids.add(id(u))
            # Lone models are single-model units and essentially never qualify
            # as horde (starting_strength=1 in the real catalogue). Track
            # anyway so synthetic / edge-case callers are handled correctly.
            if _is_horde_unit(u):
                horde_lone_ids.add(id(u))
    return RoundSnapshot(
        unit_ids_alive=unit_ids,
        monster_vehicle_ids_alive=mv_ids,
        horde_unit_ids_alive=horde_ids,
        character_ids_alive=char_ids,
        alive_squad_ids=frozenset(squad_alive),
        horde_squad_ids=frozenset(horde_squads),
        lone_unit_ids_alive=frozenset(lone_ids),
        horde_lone_ids_alive=frozenset(horde_lone_ids),
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
    attacker_faction: Optional[str] = None,
    chosen: Optional[Iterable[str]] = None,
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

    SECONDARY-SELECTION-V1: `chosen` is the iterable of Fixed Secondary
    keys this side has selected (per real 10e Pariah Nexus, each player
    picks exactly TWO from the Fixed pool or uses the Tactical deck).
    Any of the four components NOT in `chosen` is zeroed in the return
    tuple. Passing `chosen=None` means "score all four" — preserves
    backward compatibility for callers / tests that don't yet thread the
    selection through (simulator was updated to always pass the army's
    `chosen_secondaries`). Cited as `simulator.secondary_selection`.

    NOTE: `defender_faction` and `attacker_faction` parameters are accepted
    for API stability (callers in code/simulator.py pass these) but are
    currently unused. The faction-gated VP multipliers that previously used
    these parameters were removed as metric-tuning approximations rather than
    rules-correct calibration (CLAUDE.md §10 — Cite every rule. Don't invent).
    Secondary VP scoring is restored to the 10e core rules: fixed VP per kill,
    no per-faction scaling.
    """
    if chosen is None:
        chosen_set = frozenset(FIXED_SECONDARY_KEYS)
    else:
        chosen_set = frozenset(chosen)
    alive_now_ids = frozenset(
        id(u) for u in enemy_units_now if u.current_health > 0
    )
    mv_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_monster_or_vehicle(u)
    )
    char_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_character(u)
    )

    # Killed-this-round for model-based secondaries (Bring it Down,
    # Assassination): still id-based — these score per model kill.
    mv_killed = snapshot.monster_vehicle_ids_alive - mv_alive_now_ids
    chars_killed = snapshot.character_ids_alive - char_alive_now_ids

    # Per-unit secondary fix (No Prisoners, Cull the Horde): a codex unit
    # is destroyed only when ALL its models are gone. Count distinct destroyed
    # squad_ids (not individual model ids). Lone models (squad_id < 0) are
    # already single-model units and are tracked separately by object id.
    #
    # Build current alive squad_ids and lone ids from end-of-round state.
    alive_squad_ids_now: set = set()
    alive_lone_ids_now: set = set()
    for u in enemy_units_now:
        if u.current_health <= 0:
            continue
        sid = getattr(u, "squad_id", -1)
        if sid >= 0:
            alive_squad_ids_now.add(sid)
        else:
            alive_lone_ids_now.add(id(u))

    # Squad units destroyed = squad_id was alive at snapshot, no surviving
    # model carries that squad_id now.
    destroyed_squads = snapshot.alive_squad_ids - alive_squad_ids_now
    destroyed_horde_squads = snapshot.horde_squad_ids - alive_squad_ids_now
    # Lone units destroyed (single-model units — still id-based, unchanged).
    destroyed_lones = snapshot.lone_unit_ids_alive - alive_lone_ids_now
    destroyed_horde_lones = snapshot.horde_lone_ids_alive - alive_lone_ids_now

    # Total destroyed codex units for No Prisoners = squad kills + lone kills.
    units_killed_count = len(destroyed_squads) + len(destroyed_lones)
    # Cull the Horde counts horde squads + any lone-model units that somehow
    # qualify as horde (rare in the real catalogue, but handled for correctness).
    horde_killed_count = len(destroyed_horde_squads) + len(destroyed_horde_lones)

    bring_it_down_vp = min(
        BRING_IT_DOWN_CAP_PER_ROUND,
        len(mv_killed) * BRING_IT_DOWN_VP_PER_KILL,
    ) if "bring_it_down" in chosen_set else 0
    no_prisoners_vp = min(
        NO_PRISONERS_CAP_PER_ROUND,
        units_killed_count * NO_PRISONERS_VP_PER_UNIT,
    ) if "no_prisoners" in chosen_set else 0
    cull_the_horde_vp = min(
        CULL_THE_HORDE_CAP_PER_ROUND,
        horde_killed_count * CULL_THE_HORDE_VP_PER_UNIT,
    ) if "cull_the_horde" in chosen_set else 0
    assassination_vp = min(
        ASSASSINATION_CAP_PER_ROUND,
        len(chars_killed) * ASSASSINATION_VP_PER_CHAR,
    ) if "assassination" in chosen_set else 0
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
    if (
        "assassination" in chosen_set
        and enemy_warlord_uid is not None
        and enemy_warlord_uid in chars_killed
    ):
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
    attacker_faction: Optional[str] = None,
    chosen: Optional[Iterable[str]] = None,
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

    SECONDARY-SELECTION-V1: `chosen` is the iterable of Tactical
    secondary keys this side has selected
    ({"engage_on_all_fronts", "behind_enemy_lines"}). Engage / BEL VP is
    zeroed when the corresponding key is absent from `chosen`. Passing
    `chosen=None` defaults to "both Tactical secondaries active" — kept
    for backward compatibility with tests that don't yet thread the
    selection through. The simulator's `_score_secondaries` was updated
    to always pass the army's `chosen_secondaries`. Cited as
    `simulator.secondary_selection`.

    NOTE: `attacker_faction` parameter is accepted for API stability
    (callers in code/simulator.py pass this) but is currently unused.
    The faction-gated VP dampers that previously used this parameter
    were removed as metric-tuning approximations rather than
    rules-correct calibration (CLAUDE.md §10 — Cite every rule. Don't
    invent). Position secondary scoring uses fixed VP values with no
    per-faction scaling.
    """
    if chosen is None:
        chosen_set = frozenset(TACTICAL_SECONDARY_KEYS)
    else:
        chosen_set = frozenset(chosen)
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
    # SECONDARY-SELECTION-V1: gate further on `chosen_set` — even if the
    # LC-2 deck-draw slot is "active" this turn, the army only scores the
    # secondary when it has actually picked that Tactical card.
    engage_picked = "engage_on_all_fronts" in chosen_set
    bel_picked = "behind_enemy_lines" in chosen_set
    # Engage tiered (2/3/5 VP for 2/3/4 quadrants) per real Pariah Nexus.
    engage_vp = 0
    if engage_active and engage_picked:
        n = len(quadrants_occupied)
        if n >= 4:
            engage_vp = ENGAGE_VP_FOUR_QUADRANTS
        elif n == 3:
            engage_vp = ENGAGE_VP_THREE_QUADRANTS
        elif n == 2:
            engage_vp = ENGAGE_VP_TWO_QUADRANTS
    bel_vp = (
        BEHIND_ENEMY_LINES_VP
        if bel_active and bel_picked and in_enemy_dz
        else 0
    )
    return engage_vp, bel_vp


# ---------------------------------------------------------------------------
# SECONDARY-SELECTION-V1 — secondary picker
# ---------------------------------------------------------------------------

# Mobile-unit count threshold: an army with this many FLY-or-MOUNT units is
# considered fast enough to bring Behind Enemy Lines as its Tactical pick.
_BEL_MOBILE_THRESHOLD: int = 3
# MONSTER/VEHICLE count threshold: enemy with this many qualifying targets
# justifies bringing Bring it Down as a Fixed pick.
_BID_TARGET_THRESHOLD: int = 3


def _enemy_monster_vehicle_count(enemy_army: "Army") -> int:
    """Count MONSTER/VEHICLE units in the enemy's full roster (board +
    reserves). The picker fires at battle start, so we should look at the
    whole list, including deep-strikers / reserves the army has but hasn't
    deployed yet."""
    n = 0
    for u in enemy_army.units:
        if _is_monster_or_vehicle(u):
            n += 1
    return n


def _own_mobile_unit_count(own_army: "Army") -> int:
    """Count units in the army with FLY or MOUNT keyword — proxy for "fast
    enough to project into the enemy DZ for Behind Enemy Lines"."""
    n = 0
    for u in own_army.units:
        kw = u.profile.unit_keywords or ()
        if "FLY" in kw or "MOUNT" in kw:
            n += 1
    return n


def pick_secondaries(
    own_army: "Army", enemy_army: "Army",
) -> Tuple[str, ...]:
    """Return a tuple of 2 Fixed + up-to-2 Tactical secondary keys this
    army has picked for the battle. Real 10e Pariah Nexus rule: each
    player picks exactly TWO Fixed Secondaries from the four-card pool OR
    uses the Tactical deck (drawing per round). The Tactical layer in
    SwegHammer is simplified to a fixed 2-card pool (Engage on All
    Fronts + Behind Enemy Lines) — we treat the army's Tactical picks as
    a parallel choice of which of those two to "bring".

    Heuristic (deterministic given (own_army, enemy_army) so N=40 eval
    is reproducible) — picks 2 Fixed + 2 Tactical:
      Fixed slot 1:
        * If enemy has >= 3 MONSTER/VEHICLE units → "bring_it_down"
        * Otherwise → "no_prisoners"
      Fixed slot 2:
        * If enemy has >= 2 CHARACTER units → "assassination"
        * Otherwise → "cull_the_horde"
      Tactical slot 1:
        * If own mobile-unit (FLY or MOUNT) count >= 3 →
          "behind_enemy_lines" (army is fast enough to project into
          the enemy DZ each turn)
        * Otherwise → "engage_on_all_fronts" (default-aware pick,
          easier to satisfy for slower / objective-heavy lists)
      Tactical slot 2:
        * The other Tactical card (engage <-> BEL) — most real-meta
          armies bring two Tactical picks, and the simulator's
          2-card Tactical pool means this slot covers whichever
          card the slot-1 heuristic didn't pick.

    The heuristic is intentionally simple — under 30 lines. The
    structural fix is on the Fixed side: previously ALL FOUR Fixed
    Secondaries scored every game; now only the picked 2 do. The
    Tactical layer keeps the same 2-card pool but each army now picks
    its 2 (still both, given the small pool) so the
    `chosen_secondaries` gate is consistent across Fixed and Tactical.

    Cited as `simulator.secondary_selection`.
    """
    fixed: List[str] = []
    enemy_mv = _enemy_monster_vehicle_count(enemy_army)
    if enemy_mv >= _BID_TARGET_THRESHOLD:
        fixed.append("bring_it_down")
    else:
        fixed.append("no_prisoners")
    # Second Fixed pick: count enemy CHARACTERs to decide assassination
    # vs cull_the_horde.
    enemy_chars = sum(1 for u in enemy_army.units if _is_character(u))
    if enemy_chars >= 2:
        fixed.append("assassination")
    else:
        fixed.append("cull_the_horde")
    # Tactical picks: mobile armies prioritise BEL; everyone else
    # defaults to Engage. The OTHER tactical card is the second pick.
    own_mobile = _own_mobile_unit_count(own_army)
    if own_mobile >= _BEL_MOBILE_THRESHOLD:
        tactical = ["behind_enemy_lines", "engage_on_all_fronts"]
    else:
        tactical = ["engage_on_all_fronts", "behind_enemy_lines"]
    return tuple(fixed + tactical)
