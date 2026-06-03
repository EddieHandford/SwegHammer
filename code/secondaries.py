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
    # Wave 74: Cleanse is an action-based tactical secondary. Its scoring +
    # action assignment live in code/simulator.py (Battle._score_cleanse /
    # _assign_cleanse_actions, env-gated SWEG_ACTIONS); registering the key here
    # lets `pick_secondaries` add it to an army's chosen tuple.
    "cleanse",
    # Wave 75: Sabotage — action in No Man's Land (3 VP) or the enemy DZ (6 VP).
    # Scoring + assignment in code/simulator.py (Battle._score_sabotage /
    # _assign_sabotage_actions, env-gated SWEG_S2).
    "sabotage",
)
# Wave 83 Tier A: the objective-holding / board-control secondaries. Scoring +
# zone classification live in code/simulator.py (Battle._score_board_secondaries,
# env-gated SWEG_TIER_A); registering the keys here lets `pick_secondaries` add
# them to an army's chosen tuple. The real Pariah Nexus take-and-hold cards — the
# scoring paths a body army uses to out-score a durable camper. Source:
# https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-battles/
BOARD_SECONDARY_KEYS: Tuple[str, ...] = (
    "secure_no_mans_land",
    "defend_stronghold",
    "extend_battle_lines",
    "storm_hostile_objective",
    "area_denial",
)
ALL_SECONDARY_KEYS: Tuple[str, ...] = (
    FIXED_SECONDARY_KEYS + TACTICAL_SECONDARY_KEYS + BOARD_SECONDARY_KEYS
)

# M2 (wave 119) — the real 2-card Tactical Mission deck (env-gated SWEG_TAC_DECK).
#
# CA-2025-26 v1.5: at game start each player secretly chooses Fixed OR Tactical
# Missions. A TACTICAL army builds a deck of Secondary Mission cards, draws two
# into a held hand at the start of its first Command phase, and from each
# subsequent Command phase redraws back up to two; any card it scored 1+ VP from
# is discarded ("achieved") and replaced. So a Tactical army scores at most its
# TWO HELD cards per round — not the whole pile.
#
# The deck pool below is the Tactical / action / take-and-hold set the simulator
# already scores (the 4 Fixed KILL cards are the FIXED track's pool and are NOT
# in this deck). Each card here is routed to its existing scorer by
# `Battle._score_one_card`. This is the union of:
#   * the two position Tactical cards (Engage on All Fronts, Behind Enemy Lines),
#   * the two action cards (Cleanse, Sabotage), and
#   * the five Tier-A take-and-hold board cards.
# Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
# (deck mechanic) + the per-card sources already cited in
# data/rule_citations.d/secondaries_pariah_nexus.json. Cited as
# `simulator.tactical_secondary_deck`.
TACTICAL_DECK_POOL: Tuple[str, ...] = (
    "engage_on_all_fronts",
    "behind_enemy_lines",
    "cleanse",
    "sabotage",
    "secure_no_mans_land",
    "defend_stronghold",
    "extend_battle_lines",
    "storm_hostile_objective",
    "area_denial",
)
# TODO M2 Stage C: the CA-2025-26 Tactical deck also contains several action
# cards the simulator does not yet model — Establish Locus, Recover Assets, and
# A Tempting Target. Adding them requires verbatim card text (not yet captured in
# the repo — the planned data/reference/wahapedia_ca2025-26.txt does not exist)
# plus a new scoring check + citation per card. Left as a TODO rather than
# invented; the deck runs on the nine already-faithful cards above.


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
BRING_IT_DOWN_CAP_PER_ROUND: int = 18  # CA-2025-26 has NO per-round cap; 18 = effectively unbounded (under the 40-VP secondary total cap)
NO_PRISONERS_CAP_PER_ROUND: int = 5    # CA-2025-26: 2 VP/unit "up to 5 VP" — matches
ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND: int = 3
BEHIND_ENEMY_LINES_CAP_PER_ROUND: int = 4   # CA-2025-26 BEL tops out at 4 VP (2+ units)
CULL_THE_HORDE_CAP_PER_ROUND: int = 15  # CA-2025-26 Cull has NO per-round cap; 15 = effectively unbounded in practice, still under the 40-VP secondary total cap
ASSASSINATION_CAP_PER_ROUND: int = 12  # CA-2025-26 has NO per-round cap; 12 = effectively unbounded (under the 40-VP secondary total cap)

# VP per qualifying kill. Re-aligned to the CHAPTER APPROVED 2025-26 deck (wave 91,
# the deck the May-2026 calibration target was played under). No Prisoners 2 VP/unit
# (was 3) and Cull the Horde 5 VP/unit (was 3) are CA-2025-26 values, ≥2-source-verified
# (wahapedia chapter-approved-2025-26 + Goonhammer CA-2025 review + GW Tournament Companion).
# CA-2025-26 Bring It Down (Fixed): 2 VP base, +2 if the destroyed unit's total
# Wounds characteristic is 15+, +2 if 20+, to a maximum of 6 VP per unit.
BRING_IT_DOWN_VP_PER_KILL: int = 2    # base 2 VP per destroyed MONSTER/VEHICLE
BRING_IT_DOWN_VP_BONUS: int = 2       # +2 at 15+ total wounds, +2 again at 20+
BRING_IT_DOWN_VP_MAX_PER_UNIT: int = 6
NO_PRISONERS_VP_PER_UNIT: int = 2     # CA-2025-26: 2 VP per enemy UNIT destroyed (up to 5/turn)
CULL_THE_HORDE_VP_PER_UNIT: int = 5   # CA-2025-26: 5 VP per qualifying INFANTRY unit destroyed
# CA-2025-26 Assassination (Fixed): 4 VP for a destroyed CHARACTER with 4+ Wounds,
# 3 VP for one with fewer than 4 Wounds. NO Warlord bonus (removed in CA-2025-26).
ASSASSINATION_VP_PER_CHAR: int = 3    # 3 VP for a <4-wound CHARACTER
ASSASSINATION_VP_4PLUS_WOUNDS: int = 4  # 4 VP for a 4+-wound CHARACTER
ASSASSINATION_WARLORD_BONUS_VP: int = 0  # CA-2025-26: no Warlord bonus

# SC4-B — position-tracking secondary thresholds. Re-aligned to CHAPTER APPROVED
# 2025-26 (wave 91; ≥2-source-verified: wahapedia chapter-approved-2025-26 +
# Goonhammer CA-2025 review + Bell of Lost Souls).
# CA-2025-26 Engage on All Fronts: "1 VP for units wholly within two table
#   quarters, 2 VP for three quarters, 4 VP for all four quarters." (Was Pariah
#   Nexus 2/3/5 at 2/3/4 — CA-2025-26 adds a 1-VP floor at 2 quarters and lowers
#   the 3/4-quarter tiers.)
# CA-2025-26 Behind Enemy Lines (UNCHANGED from Pariah Nexus): "3 VP if one
#   non-AIRCRAFT unit is wholly within the opponent's deployment zone, 4 VP if
#   two or more are." (Was modelled as a flat 4 — now tiered 3 / 4.)
# Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
# Cited as `simulator.secondary_engage_on_all_fronts` and
# `simulator.secondary_behind_enemy_lines`.
ENGAGE_QUADRANTS_REQUIRED: int = 2    # minimum quadrants to score any Engage VP
ENGAGE_VP_TWO_QUADRANTS: int = 1      # CA-2025-26: 1 VP for 2 quadrants
ENGAGE_VP_THREE_QUADRANTS: int = 2    # CA-2025-26: 2 VP for 3 quadrants
ENGAGE_VP_FOUR_QUADRANTS: int = 4     # CA-2025-26: 4 VP for all 4 quadrants
BEHIND_ENEMY_LINES_VP: int = 4        # CA-2025-26: 4 VP if TWO+ units in enemy DZ
BEHIND_ENEMY_LINES_VP_SINGLE: int = 3  # CA-2025-26: 3 VP if ONE unit in enemy DZ
ENGAGE_ON_ALL_FRONTS_VP: int = 2      # legacy alias (still used by tests); equals the 3-quadrant tier

# SC4-C — horde-threshold + character-flag.
# CA-2025-26 Cull the Horde: qualifying = INFANTRY unit Starting Strength 13+
# (including attached Leaders). The sim uses the squad's starting model count as
# the proxy (attached-Leader inclusion not separately modelled). Was Pariah Nexus
# 20+ models / 25+ wounds; the sim previously used 10.
CULL_THE_HORDE_MIN_MODELS: int = 13   # CA-2025-26: started 13+ models


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
    # CA-2025-26 wound-bracket fields (wave 92): MONSTER/VEHICLE ids whose Wounds
    # characteristic is 15+/20+ (for Bring It Down's 2 +2 +2 brackets), and
    # CHARACTER ids with 4+ Wounds (for Assassination's 4-vs-3 split).
    mv_ids_15plus: frozenset = frozenset()
    mv_ids_20plus: frozenset = frozenset()
    char_ids_4plus: frozenset = frozenset()


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
    # CA-2025-26 wound brackets. Uses the model's Wounds CHARACTERISTIC
    # (profile.health = the datasheet max), not current wounds. Single-model
    # MONSTER/VEHICLE (most of them) -> per-model wounds == the unit's total;
    # multi-model vehicle squadrons under-count (rare, accepted approximation).
    mv_ids_15plus = frozenset(
        id(u) for u in alive
        if _is_monster_or_vehicle(u) and (getattr(u.profile, "health", 0) or 0) >= 15
    )
    mv_ids_20plus = frozenset(
        id(u) for u in alive
        if _is_monster_or_vehicle(u) and (getattr(u.profile, "health", 0) or 0) >= 20
    )
    char_ids_4plus = frozenset(
        id(u) for u in alive
        if _is_character(u) and (getattr(u.profile, "health", 0) or 0) >= 4
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
        mv_ids_15plus=mv_ids_15plus,
        mv_ids_20plus=mv_ids_20plus,
        char_ids_4plus=char_ids_4plus,
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
    # WAVE 74 FIX: the populated field on UnitProfile is `max_models` (the
    # datasheet's maximum squad size — Termagants 20, Boyz 20, Poxwalkers 20,
    # Cadians 10). The previous code read `starting_strength` / `squad_size` /
    # `count`, all of which are None in the live catalogue, so this returned
    # False for every unit and Cull the Horde scored 0 for everyone (a dead
    # mechanic). A unit whose datasheet allows >= 10 models is horde-capable;
    # tournament hordes field them at or near max. Fall back to the legacy
    # fields if a synthetic caller populates them instead.
    starting = getattr(profile, "max_models", None)
    if not starting:
        starting = getattr(profile, "starting_strength", None)
    if not starting:
        starting = getattr(profile, "squad_size", None)
    if not starting:
        starting = getattr(profile, "count", None)
    if not starting:
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

    # CA-2025-26 Bring It Down: per destroyed MONSTER/VEHICLE, 2 VP + 2 (15+ total
    # wounds) + 2 (20+), capped at 6 per unit; no per-round cap (the 18 ceiling is
    # effectively unbounded, under the 40-VP secondary total cap).
    bring_it_down_vp = 0
    if "bring_it_down" in chosen_set:
        for mid in mv_killed:
            vp = BRING_IT_DOWN_VP_PER_KILL
            if mid in snapshot.mv_ids_15plus:
                vp += BRING_IT_DOWN_VP_BONUS
            if mid in snapshot.mv_ids_20plus:
                vp += BRING_IT_DOWN_VP_BONUS
            bring_it_down_vp += min(vp, BRING_IT_DOWN_VP_MAX_PER_UNIT)
        bring_it_down_vp = min(bring_it_down_vp, BRING_IT_DOWN_CAP_PER_ROUND)
    no_prisoners_vp = min(
        NO_PRISONERS_CAP_PER_ROUND,
        units_killed_count * NO_PRISONERS_VP_PER_UNIT,
    ) if "no_prisoners" in chosen_set else 0
    cull_the_horde_vp = min(
        CULL_THE_HORDE_CAP_PER_ROUND,
        horde_killed_count * CULL_THE_HORDE_VP_PER_UNIT,
    ) if "cull_the_horde" in chosen_set else 0
    # CA-2025-26 Assassination: 4 VP per destroyed CHARACTER with 4+ Wounds, 3 VP
    # for one with fewer than 4; no per-round cap (12 ceiling, under the 40 total).
    assassination_vp = 0
    if "assassination" in chosen_set:
        for cid in chars_killed:
            assassination_vp += (
                ASSASSINATION_VP_4PLUS_WOUNDS
                if cid in snapshot.char_ids_4plus
                else ASSASSINATION_VP_PER_CHAR
            )
        assassination_vp = min(assassination_vp, ASSASSINATION_CAP_PER_ROUND)
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
    enemy_dz_count = 0   # CA-2025-26 BEL: 3 VP for one unit in the enemy DZ, 4 for two+

    if own_is_army_a:
        # Army A's enemy DZ is the high-y strip.
        enemy_dz_lo = map_.height - map_.deployment_width
        enemy_dz_hi = map_.height
    else:
        # Army B's enemy DZ is the low-y strip.
        enemy_dz_lo = 0.0
        enemy_dz_hi = map_.deployment_width

    import os as _os
    if _os.environ.get("SWEG_SECONDARY") == "1":
        # Wave 136 (user catch) — squad-granularity WHOLLY-WITHIN. Real Engage
        # scores a quarter only for a unit WHOLLY WITHIN it and >6" from board
        # centre; real Behind Enemy Lines only for a unit WHOLLY WITHIN the enemy
        # deployment zone. The one-Unit-per-model representation OVER-credits with
        # an "any model inside" check (a spread codex squad registers in several
        # quarters via different models, never paying the straddle penalty). Group
        # models by `squad_id` and require ALL of a squad's models to qualify; a
        # straddling squad counts for NO quarter. Even-handed (favours a compact
        # unit — emergent, no faction branch); cited `simulator.secondary_wholly_within`.
        from collections import defaultdict as _dd
        _squads = _dd(list)
        for u in own_units:
            if u.current_health <= 0:
                continue
            pos = getattr(u, "position", None)
            if pos is None:
                continue
            sid = getattr(u, "squad_id", -1)
            key = sid if (sid is not None and sid >= 0) else ("lone", id(u))
            _squads[key].append(pos)
        for _positions in _squads.values():
            _quarters = set()
            _all_beyond_centre = True   # all models >6" from centre (Engage)
            _all_in_enemy_dz = True     # all models wholly within the enemy DZ (BEL)
            for (ux, uy) in _positions:
                _quarters.add((0 if ux < cx else 1, 0 if uy < cy else 1))
                if (ux - cx) ** 2 + (uy - cy) ** 2 <= 36.0:   # within 6" of centre
                    _all_beyond_centre = False
                if not (enemy_dz_lo <= uy <= enemy_dz_hi):
                    _all_in_enemy_dz = False
            # Engage: the squad is wholly within ONE quarter and clear of centre.
            if len(_quarters) == 1 and _all_beyond_centre:
                quadrants_occupied.add(next(iter(_quarters)))
            # BEL: count one unit (not per-model) only if wholly within the DZ.
            if _all_in_enemy_dz:
                enemy_dz_count += 1
    else:
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
            # Enemy DZ check (count units for the CA-2025-26 BEL 1-vs-2+ tier).
            if enemy_dz_lo <= uy <= enemy_dz_hi:
                enemy_dz_count += 1

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
    bel_vp = 0
    if bel_active and bel_picked and enemy_dz_count >= 1:
        # CA-2025-26: 3 VP for one unit wholly in the enemy DZ, 4 VP for two or more.
        bel_vp = (
            BEHIND_ENEMY_LINES_VP if enemy_dz_count >= 2
            else BEHIND_ENEMY_LINES_VP_SINGLE
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


# M2 (wave 119) — the Fixed-vs-Tactical track threshold (env-gated SWEG_TAC_DECK).
#
# A real player choosing between Fixed (2 kill cards, scored every round) and
# Tactical (a 2-card rotating action/board hand) leans on what their army can
# DO each turn. A broad army with spare cheap bodies can keep a Tactical deck
# churning — it has the chaff to perform actions (Cleanse / Sabotage) and the
# model count to spread across quarters and hold scattered markers. A low-model
# durable army (the Knight, emergently) has no spare action-doers and cannot
# reliably achieve a fresh Tactical card every round, so it leans Fixed kill.
#
# This is exactly the real-world choice and it falls out of UNIT COUNT alone —
# NO faction awareness. A Knight (5-6 single-model units, ~0 chaff) lands below
# the threshold and picks FIXED; a horde / mechanised list lands above it and
# picks TACTICAL. Even-handed: the same count test runs for both sides.
_TACTICAL_TRACK_MIN_CHAFF: int = 2   # spare cheap action-doers needed to churn a deck
_TACTICAL_TRACK_MIN_UNITS: int = 8   # broad-enough roster to spread + redraw


def _tac_deck_enabled() -> bool:
    """M2 real 2-card Tactical secondary deck. Env-gated SWEG_TAC_DECK; unset →
    legacy `pick_secondaries` / `_score_secondaries` (union of all sources)
    runs byte-identical. Kept as a function so a future A/B can re-gate via a
    one-line edit and so OFF is unambiguous at every call site."""
    import os
    return os.environ.get("SWEG_TAC_DECK") == "1"


def _pick_fixed_kill_pair(own_army: "Army", enemy_army: "Army") -> List[str]:
    """The 2 Fixed KILL cards an army brings (CA-2025-26 Fixed pool). This is
    exactly today's Fixed-pick logic, factored out so both the legacy path and
    the M2 FIXED track use the identical heuristic.

      Slot 1: enemy has >= 3 MONSTER/VEHICLE units → bring_it_down, else no_prisoners.
      Slot 2: enemy has >= 2 CHARACTER units → assassination, else cull_the_horde.
    """
    fixed: List[str] = []
    if _enemy_monster_vehicle_count(enemy_army) >= _BID_TARGET_THRESHOLD:
        fixed.append("bring_it_down")
    else:
        fixed.append("no_prisoners")
    enemy_chars = sum(1 for u in enemy_army.units if _is_character(u))
    if enemy_chars >= 2:
        fixed.append("assassination")
    else:
        fixed.append("cull_the_horde")
    return fixed


def _choose_secondary_track(own_army: "Army") -> str:
    """M2: decide FIXED vs TACTICAL for one army from unit count only (no
    faction awareness). Returns "TACTICAL" if the army has enough spare chaff
    AND a broad-enough roster to keep a 2-card deck churning, else "FIXED".

    The asymmetry is purely emergent: a low-model durable list (no chaff, few
    units) lands on FIXED kill exactly as a real Knight player would; a broad
    body army lands on TACTICAL. Identical test for both sides — even-handed."""
    chaff = _own_chaff_count(own_army)
    units = sum(1 for _ in own_army.units)
    if chaff >= _TACTICAL_TRACK_MIN_CHAFF and units >= _TACTICAL_TRACK_MIN_UNITS:
        return "TACTICAL"
    return "FIXED"


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
    # M2 (wave 119, env-gated SWEG_TAC_DECK) — the real Fixed-OR-Tactical track
    # choice. When the deck gate is ON we set `own_army.secondary_track` and
    # return ONLY that track's scoring sources (the simulator's deck-aware
    # scorer reads the track + hand), instead of the legacy union of every
    # source. OFF leaves the track None and falls through to the byte-identical
    # legacy path below. Cited as `simulator.tactical_secondary_deck`.
    if _tac_deck_enabled():
        track = _choose_secondary_track(own_army)
        own_army.secondary_track = track
        if track == "FIXED":
            # FIXED: the 2 kill cards, scored every round.
            own_army.tactical_hand = []
            own_army.tactical_deck = []
            return tuple(_pick_fixed_kill_pair(own_army, enemy_army))
        # TACTICAL: the 2-card rotating hand. The hand + remaining deck are
        # filled deterministically at battle start by `Battle._init_tactical_deck`
        # (the army name + battle seed are not visible here). Return the full
        # deck pool as the army's `chosen_secondaries` so every per-card gate
        # (cleanse / sabotage / board) recognises the card while the hand is the
        # actual scored subset.
        return tuple(TACTICAL_DECK_POOL)

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
    # Wave 74: an army with spare cheap bodies can also bring the Cleanse action
    # secondary (it can afford to take a unit out of the firefight to perform the
    # action). Low-model elite armies have no chaff to spare and never satisfy it,
    # so the asymmetry is even-handed — it falls out of unit cost, not faction.
    # Inert unless SWEG_ACTIONS is set (the simulator gates the scoring).
    if _own_chaff_count(own_army) >= 2:
        tactical.append("cleanse")
        # Wave 75: an army with spare cheap bodies can also bring Sabotage
        # (push a body forward into No Man's Land / the enemy DZ for the action).
        # Inert unless SWEG_S2 is set (the simulator gates the scoring + the
        # 40-VP secondary cap that keeps total secondary VP faithful).
        tactical.append("sabotage")
    # Wave 83 Tier A: every army brings the full objective-holding / board-control
    # package. The asymmetry is purely in COMPLETION (a low-model durable army
    # controls few objectives across zones and scores ~0 on the spread cards),
    # not in the pick — identical for both sides, so even-handed. Inert unless
    # SWEG_TIER_A is set (the simulator gates the scoring), and bounded by the
    # 40-VP secondary total cap plus each card's natural ≤20-VP/game ceiling.
    board = list(BOARD_SECONDARY_KEYS)
    return tuple(fixed + tactical + board)


def _own_chaff_count(own_army: "Army") -> int:
    """Count cheap, spare-able units (per-model points under 15, no CHARACTER)
    — the same chaff definition as `strategy._is_chaff_unit`. Proxy for "has a
    body it can take out of the firefight to perform an action"."""
    n = 0
    for u in own_army.units:
        p = u.profile
        pts = float(getattr(p, "points_cost", 0.0) or 0.0)
        if pts <= 0.0 or pts >= 15.0:
            continue
        if "CHARACTER" in (p.unit_keywords or ()):
            continue
        n += 1
    return n
