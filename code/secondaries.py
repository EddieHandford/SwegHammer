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
    - simulator.secondary_bring_it_down (Chapter Approved 2025-26 Fixed secondary)
    - simulator.secondary_no_prisoners (Chapter Approved 2025-26 Tactical-only secondary — banned as a Fixed pick)
    - simulator.secondary_engage_on_all_fronts (Chapter Approved 2025-26 tactical)
    - simulator.secondary_behind_enemy_lines (Chapter Approved 2025-26 tactical)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple


def _action_economy_enabled() -> bool:
    """Action-economy build gate (Chapter Approved 2025-26 Tactical action cards:
    Establish Locus, Recover Assets, A Tempting Target). DEFAULT-OFF: the three
    cards are inert unless `SWEG_ACTION_ECONOMY` is explicitly "1".

    This is the faithful anti-durability mechanism the durability over-reward
    investigation identified (docs/DURABILITY_OVERREWARD_INVESTIGATION.md): real
    10th-edition Tactical action cards tax a unit by making it stop and perform
    an action for victory points instead of shooting or charging — a tax a
    low-model durable army (Imperial Knights) cannot pay but a unit-rich horde
    can. The asymmetry is EMERGENT (more units means more spare bodies that can
    perform actions); it NEVER branches on faction or model count.

    The gate is read at the point the deck pool is built so that, while it is
    off, the three card keys are ABSENT from `TACTICAL_DECK_POOL` entirely — the
    deck never draws them, the shuffle order is unchanged, and every downstream
    scoring / assignment path is unreachable. This is the byte-identical OFF
    contract."""
    return os.environ.get("SWEG_ACTION_ECONOMY", "1") != "0"

if TYPE_CHECKING:
    from .army import Army
    from .units import Unit
    from .map import Map


# Pool of recognised Pariah Nexus secondary keys. Used by `pick_secondaries`
# (assigns 2 Fixed + 2 Tactical to each army at battle start) and the
# `chosen` gate in `score_round_delta` / `score_position_delta`.
#
# Fixed Secondaries — the printed CA-2025-26 Fixed pool is FIVE cards, pick 2
# (distinct): Assassination, No Prisoners, Cull the Horde, Bring It Down, Cleanse.
# The three kill cards below are the always-present core; No Prisoners and Cleanse
# are added as legal Fixed picks by D5 (`_pick_fixed_pair_full`, env-gated
# SWEG_FIXED_POOL_FULL, default ON) — see `simulator.fixed_pool_full` for the
# citation and the open caveat that whether the specific May-2026 Warp Friends
# tournament banned No Prisoners as a Fixed pick is unverified (the base rule
# includes it). This tuple stays the 3-card core because it feeds the
# backward-compatible `score_round_delta(chosen=None)` fallback; the picker
# returns the No Prisoners / Cleanse picks directly and the scorer handles them.
#   bring_it_down       — MONSTER/VEHICLE kill credit
#   cull_the_horde      — kill credit for 13+model squads
#   assassination       — CHARACTER kill credit (wound-bracket split)
# Tactical Secondaries (pool of 9+, draw 2 per round in real play):
#   engage_on_all_fronts — board-spread victory points
#   behind_enemy_lines   — opponent deployment zone victory points
#   no_prisoners         — generic unit-kill credit (Tactical only in tournament)
# Durability fidelity wave, audit C divergence 2 (2026-07-03): the printed
# CA-2025-26 Secondary Mission deck carries BOTH a Fixed box and a Tactical
# box on the same physical card for most cards, including bring_it_down and
# assassination — they are NOT Fixed-exclusive. See TACTICAL_DECK_POOL below
# and `simulator.tactical_deck_big_game` (env-gated SWEG_TACDECK_BIG_GAME,
# default ON) for the reachability fix that adds them to the drawable deck.
# Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
# Cited as `simulator.secondary_selection`.
FIXED_SECONDARY_KEYS: Tuple[str, ...] = (
    "bring_it_down", "cull_the_horde", "assassination",
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
    # No Prisoners is a Tactical-only card in CA-2025-26 tournament play (banned
    # as a Fixed pick). Registered here so the legacy pick_secondaries path can
    # include it in a Tactical army's chosen tuple and so ALL_SECONDARY_KEYS
    # keeps a complete union.
    "no_prisoners",
    # Action-economy build: the three CA-2025-26 Tactical action cards modelled
    # behind SWEG_ACTION_ECONOMY. Registering the keys here keeps the per-card
    # `chosen` gate and ALL_SECONDARY_KEYS union complete; they are inert in
    # score_position_delta (which only reads engage / behind_enemy_lines) and are
    # only ever drawn when the gate adds them to TACTICAL_DECK_POOL below.
    # Establish Locus  — cited simulator.secondary_establish_locus
    # Recover Assets   — cited simulator.secondary_recover_assets
    # A Tempting Target — cited secondaries.a_tempting_target
    "establish_locus",
    "recover_assets",
    "a_tempting_target",
    # Secondary-economy audit fix wave, D3 (SWEG_TACDECK_FULL): the three printed
    # Chapter Approved 2025-26 Tactical cards the sim did not implement at all.
    # Scored in code/simulator.py (Battle._score_marked_for_death /
    # _score_overwhelming_force / _score_display_of_might); registered here so
    # ALL_SECONDARY_KEYS stays complete and the per-card `chosen` gate recognises
    # them. Only ever drawn when SWEG_TACDECK_FULL adds them to TACTICAL_DECK_POOL.
    "marked_for_death",
    "overwhelming_force",
    "display_of_might",
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
# already scores. Two of the three Fixed KILL cards (bring_it_down and
# assassination) are ALSO drawable from this deck — see the
# `_BIG_GAME_DECK_CARDS` block further down and `simulator.tactical_deck_big_game`
# for the reachability fix and its printed-deck verification (durability
# fidelity wave, audit C divergence 2, 2026-07-03). Cull the Horde is left
# out of scope for that fix (a separate, un-audited reachability gap of the
# same shape — its Tactical text is already cited at
# `simulator.secondary_cull_the_horde_tactical` but likewise unreachable — is
# noted there for a future ticket, not fixed here). No Prisoners IS in this
# deck because it is a Tactical-only card in CA-2025-26 tournament play (it
# is never a valid Fixed pick, so there is no Fixed-track overlap to reason
# about). Each card here is routed to its existing scorer by
# `Battle._score_one_card`. This is the union of:
#   * No Prisoners (generic unit-kill credit, Tactical only in tournament),
#   * the two position Tactical cards (Engage on All Fronts, Behind Enemy Lines),
#   * the two action cards (Cleanse, Sabotage),
#   * the five Tier-A take-and-hold board cards, and
#   * (gated) Bring It Down / Assassination, the two Tactical-capable Fixed
#     kill cards.
# Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
# (deck mechanic) + the per-card sources already cited in
# data/rule_citations.d/secondaries_pariah_nexus.json. Cited as
# `simulator.tactical_secondary_deck`.
_TACTICAL_DECK_BASE_POOL: Tuple[str, ...] = (
    "no_prisoners",
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
# Action-economy build (Chapter Approved 2025-26): the deck also contains three
# Tactical action cards the simulator previously stubbed — Establish Locus,
# Recover Assets, and A Tempting Target. Their verbatim card text is now captured
# (the rule citations live in data/rule_citations.d/secondaries_pariah_nexus.json
# under simulator.secondary_establish_locus, simulator.secondary_recover_assets,
# and secondaries.a_tempting_target), and each has a scoring check + action
# assignment in code/simulator.py.
#
# BYTE-IDENTICAL OFF CONTRACT: the three keys are appended to TACTICAL_DECK_POOL
# ONLY when SWEG_ACTION_ECONOMY=1. While the gate is off the keys are absent, so
# the deck shuffle (_init_tactical_deck) and the challenger draw both see the
# same ten-card pool as before — no extra cards, no perturbed draw order, no
# extra random consumption. The downstream scorers/assigners are unreachable
# because the card is never drawn or chosen.
_ACTION_ECONOMY_DECK_CARDS: Tuple[str, ...] = (
    "establish_locus",
    "recover_assets",
    "a_tempting_target",
)
# Durability fidelity wave, audit C divergence 2 (2026-07-03, env-gated
# SWEG_TACDECK_BIG_GAME, DEFAULT-ON) — Bring It Down and Assassination are
# Tactical-capable Fixed kill cards in the real CA-2025-26 Secondary Mission
# deck, not Fixed-exclusive. Verified against Wahapedia
# (https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/ and
# https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-battles/): the printed
# deck prints a Tactical scoring box on both cards ("One or more enemy
# MONSTER or VEHICLE units were destroyed this turn. TACTICAL 4VP" / "One or
# more enemy CHARACTER models were destroyed this turn. TACTICAL 5VP"),
# corroborating the verbatim text a prior session already captured (wave 181)
# in the `simulator.secondary_bring_it_down_tactical` /
# `..._assassination_tactical` citations — text that has been fully wired
# into `Battle._score_one_card`'s `is_tactical` branch since wave 181
# (`code/simulator.py:3616-3633`) but was unreachable because no TACTICAL-track
# army could ever draw either card. This gate makes the deck include them so
# that already-implemented, already-cited scoring path actually runs.
# Cited as `simulator.tactical_deck_big_game`.
_BIG_GAME_DECK_CARDS: Tuple[str, ...] = (
    "bring_it_down",
    "assassination",
)


def _big_game_tactical_enabled() -> bool:
    """Bring It Down / Assassination Tactical-deck reachability gate. DEFAULT
    ON; `SWEG_TACDECK_BIG_GAME=0` is the byte-identical-off kill-switch that
    restores the pre-fix deck (`_TACTICAL_DECK_BASE_POOL` plus whatever the
    independent `SWEG_ACTION_ECONOMY` gate adds) exactly, with no perturbed
    shuffle order and no extra random consumption when both cards are
    absent — see `_BIG_GAME_DECK_CARDS` above for the rule verification."""
    return os.environ.get("SWEG_TACDECK_BIG_GAME", "1") != "0"


# Secondary-economy audit fix wave, D3 (env-gated SWEG_TACDECK_FULL, DEFAULT-ON):
# complete the printed Chapter Approved 2025-26 Secondary Mission deck (19 cards).
# The pre-fix production pool was 12 cards (base 10 + big-game 2); it lacked seven
# printed cards (docs/_SEC_ECONOMY_AUDIT.md D3), so its drawable pool was smaller
# and harder than the real one. These seven complete it:
#   * establish_locus / recover_assets / a_tempting_target — implemented action
#     cards previously reachable only under SWEG_ACTION_ECONOMY; their gating
#     folds into this fix (the shedding fix D1 and hand-gating fix D2 remove the
#     action-economy over-assignment that caused their prior metric-harm rejection).
#   * cull_the_horde — its Tactical scorer (CULL_THE_HORDE_TACTICAL_VP, routed in
#     Battle._score_one_card) already existed but the card was unreachable on the
#     Tactical track (the wave-181 exclusion the big-game citation flagged as a
#     separate follow-up); this restores it.
#   * marked_for_death / overwhelming_force / display_of_might — the three cards
#     not implemented at all; their scorers are added in code/simulator.py and
#     cited verbatim (simulator.secondary_marked_for_death /
#     simulator.secondary_overwhelming_force / simulator.secondary_display_of_might).
# The full drawable census (SWEG_TACDECK_BIG_GAME + SWEG_TACDECK_FULL both default
# ON) is exactly the printed 19-card list. Cited `simulator.tactical_deck_full`.
# Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
_TACDECK_FULL_EXTRA_CARDS: Tuple[str, ...] = (
    "establish_locus",
    "recover_assets",
    "a_tempting_target",
    "cull_the_horde",
    "marked_for_death",
    "overwhelming_force",
    "display_of_might",
)


def _tacdeck_full_enabled() -> bool:
    """D3 full printed 19-card deck gate. DEFAULT ON; `SWEG_TACDECK_FULL=0`
    restores the pre-fix pool byte-identically (base + action-economy-if-gated +
    big-game-if-gated, in exactly the pre-fix order)."""
    return os.environ.get("SWEG_TACDECK_FULL", "1") != "0"


def _build_tactical_deck_pool() -> Tuple[str, ...]:
    """Assemble the drawable Tactical deck pool at import time. With
    SWEG_TACDECK_FULL on, the printed 19-card deck (base + big-game + the seven
    D3 cards, de-duplicated, preserving first-seen order). With it off, the exact
    pre-fix expression (byte-identical shuffle input)."""
    if _tacdeck_full_enabled():
        pool: List[str] = list(_TACTICAL_DECK_BASE_POOL)
        if _big_game_tactical_enabled():
            pool += [c for c in _BIG_GAME_DECK_CARDS if c not in pool]
        for c in _TACDECK_FULL_EXTRA_CARDS:
            if c not in pool:
                pool.append(c)
        return tuple(pool)
    # Legacy pre-fix pool (byte-identical order).
    return (
        _TACTICAL_DECK_BASE_POOL
        + (_ACTION_ECONOMY_DECK_CARDS if _action_economy_enabled() else ())
        + (_BIG_GAME_DECK_CARDS if _big_game_tactical_enabled() else ())
    )


TACTICAL_DECK_POOL: Tuple[str, ...] = _build_tactical_deck_pool()


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

# CA-2025-26 Tactical-track kill card flat VP values (scored once per turn if
# ONE OR MORE qualifying enemy units died, else 0). These are the TACTICAL card
# values — distinct from the Fixed per-unit accumulation above.
# Source: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
# Cited as `simulator.secondary_assassination_tactical`,
#         `simulator.secondary_bring_it_down_tactical`,
#         `simulator.secondary_cull_the_horde_tactical`.
ASSASSINATION_TACTICAL_VP: int = 5   # flat 5 VP if one or more CHARACTERs died
BRING_IT_DOWN_TACTICAL_VP: int = 4   # flat 4 VP if one or more MONSTER/VEHICLE units died
CULL_THE_HORDE_TACTICAL_VP: int = 5  # flat 5 VP if one or more qualifying INFANTRY units died


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
    # Per-UNIT Assassination fix (SWEG_SECONDARY_PER_UNIT). A CHARACTER unit is
    # destroyed only when ALL its models die — like the No Prisoners / Cull
    # per-squad handling above. Without this a multi-model CHARACTER unit (e.g.
    # the 5-model Cadian Command Squad) scores Assassination once per MODEL.
    # char_squad_ids: squad_ids (>=0) that are CHARACTER units; char_lone_ids:
    # lone (squad_id<0) CHARACTER unit ids; *_4plus: the 4+-wound subsets.
    char_squad_ids: frozenset = frozenset()
    char_squad_ids_4plus: frozenset = frozenset()
    char_lone_ids: frozenset = frozenset()
    char_lone_ids_4plus: frozenset = frozenset()


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
    char_squads: set = set()
    char_squads_4p: set = set()
    char_lones: set = set()
    char_lones_4p: set = set()
    for u in alive:
        sid = getattr(u, "squad_id", -1)
        is_char = _is_character(u)
        is_4plus = (getattr(u.profile, "health", 0) or 0) >= 4
        if sid >= 0:
            squad_alive.add(sid)
            if _is_horde_unit(u):
                horde_squads.add(sid)
            if is_char:
                char_squads.add(sid)
                if is_4plus:
                    char_squads_4p.add(sid)
        else:
            lone_ids.add(id(u))
            # Lone models are single-model units and essentially never qualify
            # as horde (starting_strength=1 in the real catalogue). Track
            # anyway so synthetic / edge-case callers are handled correctly.
            if _is_horde_unit(u):
                horde_lone_ids.add(id(u))
            if is_char:
                char_lones.add(id(u))
                if is_4plus:
                    char_lones_4p.add(id(u))
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
        char_squad_ids=frozenset(char_squads),
        char_squad_ids_4plus=frozenset(char_squads_4p),
        char_lone_ids=frozenset(char_lones),
        char_lone_ids_4plus=frozenset(char_lones_4p),
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
    tactical: bool = False,
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
      * cull_the_horde_vp — kill credit for units whose Starting Strength was
        CULL_THE_HORDE_MIN_MODELS (13) or more. (This line previously said 10,
        which never matched the constant or the citation.)
      * assassination_vp — kill credit for enemy CHARACTERs

    SECONDARY-SELECTION-V1: `chosen` is the iterable of secondary keys this
    side has selected (per real CA-2025-26, each player picks exactly TWO
    Fixed Secondaries from the three-card Fixed pool OR uses the Tactical
    deck, where No Prisoners is available as a Tactical-only card).
    Any of the four components NOT in `chosen` is zeroed in the return
    tuple. Passing `chosen=None` means "score all four kill cards" — preserves
    backward compatibility for callers / tests that don't yet thread the
    selection through (simulator was updated to always pass the army's
    `chosen_secondaries`). The None fallback includes no_prisoners so
    existing scorer-only tests continue to pass (it remains a scoreable
    card, just not a valid Fixed pick). Cited as
    `simulator.secondary_selection`.

    Fixed-vs-Tactical track split (CA-2025-26):
      `tactical=False` (default) — FIXED per-unit scoring: each qualifying
        destroyed unit earns VP individually (current behaviour, unchanged).
      `tactical=True` — TACTICAL flat per-turn scoring: each of the three
        kill cards (bring_it_down, cull_the_horde, assassination) scores a
        flat VP value if ONE OR MORE qualifying enemy units died this turn,
        else 0. The flat values are:
          Assassination: 5 VP if one or more enemy CHARACTERs died
          Bring It Down: 4 VP if one or more enemy MONSTER/VEHICLE units died
          Cull the Horde: 5 VP if one or more qualifying INFANTRY units died
        No Prisoners is per-unit-capped (2 VP/unit, max 5/turn) in BOTH
        tracks — it does not change form when tactical=True. Cited as
        `simulator.secondary_assassination_tactical`,
        `simulator.secondary_bring_it_down_tactical`,
        `simulator.secondary_cull_the_horde_tactical`.

    NOTE: `defender_faction` and `attacker_faction` parameters are accepted
    for API stability (callers in code/simulator.py pass these) but are
    currently unused. The faction-gated VP multipliers that previously used
    these parameters were removed as metric-tuning approximations rather than
    rules-correct calibration (CLAUDE.md §10 — Cite every rule. Don't invent).
    Secondary VP scoring is restored to the 10e core rules: fixed VP per kill,
    no per-faction scaling.
    """
    if chosen is None:
        # Backward-compat: score all four kill cards (the three valid Fixed
        # picks + no_prisoners, which is Tactical-only in tournament play but
        # is still a real card the scorer knows how to score). Tests that call
        # score_round_delta without a `chosen` argument are unit-testing the
        # scorer itself, not the picker, so no_prisoners must still score here.
        chosen_set = frozenset(FIXED_SECONDARY_KEYS) | frozenset(("no_prisoners",))
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

    # Per-UNIT Assassination (SWEG_SECONDARY_PER_UNIT): a CHARACTER unit is
    # destroyed only when its LAST model dies — matching the No Prisoners / Cull
    # per-squad handling. Without it a 5-model Cadian Command Squad scores
    # Assassination 5x. Build the list of destroyed CHARACTER UNITS with a 4+-
    # wound flag each (character squads gone + character lone models gone). Gate
    # off -> None -> the legacy per-model path below scores (byte-identical).
    killed_char_unit_4plus: Optional[List[bool]] = None
    if os.environ.get("SWEG_SECONDARY_PER_UNIT", "1") != "0":  # DEFAULT-ON, adopted 2026-07-13
        _dead_char_squads = snapshot.char_squad_ids - alive_squad_ids_now
        _dead_char_lones = snapshot.char_lone_ids - alive_lone_ids_now
        killed_char_unit_4plus = (
            [sid in snapshot.char_squad_ids_4plus for sid in _dead_char_squads]
            + [lid in snapshot.char_lone_ids_4plus for lid in _dead_char_lones]
        )

    # Total destroyed codex units for No Prisoners = squad kills + lone kills.
    units_killed_count = len(destroyed_squads) + len(destroyed_lones)
    # Cull the Horde counts horde squads + any lone-model units that somehow
    # qualify as horde (rare in the real catalogue, but handled for correctness).
    horde_killed_count = len(destroyed_horde_squads) + len(destroyed_horde_lones)

    # CA-2025-26 Bring It Down scoring — split by track:
    #   FIXED (tactical=False): per destroyed MONSTER/VEHICLE, 2 VP + 2 (15+ total
    #     wounds) + 2 (20+), capped at 6 per unit; no per-round cap.
    #   TACTICAL (tactical=True): flat 4 VP if one or more MONSTER/VEHICLE units
    #     were destroyed this turn, else 0.
    # Cited as `simulator.secondary_bring_it_down` (Fixed) and
    # `simulator.secondary_bring_it_down_tactical` (Tactical).
    bring_it_down_vp = 0
    if "bring_it_down" in chosen_set:
        if tactical:
            bring_it_down_vp = BRING_IT_DOWN_TACTICAL_VP if mv_killed else 0
        else:
            for mid in mv_killed:
                vp = BRING_IT_DOWN_VP_PER_KILL
                if mid in snapshot.mv_ids_15plus:
                    vp += BRING_IT_DOWN_VP_BONUS
                if mid in snapshot.mv_ids_20plus:
                    vp += BRING_IT_DOWN_VP_BONUS
                bring_it_down_vp += min(vp, BRING_IT_DOWN_VP_MAX_PER_UNIT)
            bring_it_down_vp = min(bring_it_down_vp, BRING_IT_DOWN_CAP_PER_ROUND)
    # No Prisoners — per-unit-capped (2 VP/unit, max 5/turn) in BOTH tracks.
    # The Tactical track does not change its scoring form for No Prisoners.
    no_prisoners_vp = min(
        NO_PRISONERS_CAP_PER_ROUND,
        units_killed_count * NO_PRISONERS_VP_PER_UNIT,
    ) if "no_prisoners" in chosen_set else 0
    # CA-2025-26 Cull the Horde scoring — split by track:
    #   FIXED (tactical=False): 5 VP per qualifying INFANTRY unit destroyed.
    #   TACTICAL (tactical=True): flat 5 VP if one or more qualifying INFANTRY
    #     units were destroyed this turn, else 0.
    # Cited as `simulator.secondary_cull_the_horde` (Fixed) and
    # `simulator.secondary_cull_the_horde_tactical` (Tactical).
    cull_the_horde_vp = 0
    if "cull_the_horde" in chosen_set:
        if tactical:
            cull_the_horde_vp = CULL_THE_HORDE_TACTICAL_VP if horde_killed_count > 0 else 0
        else:
            cull_the_horde_vp = min(
                CULL_THE_HORDE_CAP_PER_ROUND,
                horde_killed_count * CULL_THE_HORDE_VP_PER_UNIT,
            )
    # CA-2025-26 Assassination scoring — split by track:
    #   FIXED (tactical=False): 4 VP per destroyed CHARACTER with 4+ Wounds, 3 VP
    #     for one with fewer than 4; no per-round cap.
    #   TACTICAL (tactical=True): flat 5 VP if one or more CHARACTERs were destroyed
    #     this turn, else 0. No wound-tier split on the Tactical card.
    # Cited as `simulator.secondary_assassination` (Fixed) and
    # `simulator.secondary_assassination_tactical` (Tactical).
    assassination_vp = 0
    if "assassination" in chosen_set:
        if killed_char_unit_4plus is not None:
            # Per-UNIT (SWEG_SECONDARY_PER_UNIT): one score per destroyed
            # CHARACTER unit, not per model.
            if tactical:
                assassination_vp = (
                    ASSASSINATION_TACTICAL_VP if killed_char_unit_4plus else 0
                )
            else:
                for is_4plus in killed_char_unit_4plus:
                    assassination_vp += (
                        ASSASSINATION_VP_4PLUS_WOUNDS
                        if is_4plus
                        else ASSASSINATION_VP_PER_CHAR
                    )
                assassination_vp = min(assassination_vp, ASSASSINATION_CAP_PER_ROUND)
        elif tactical:
            assassination_vp = ASSASSINATION_TACTICAL_VP if chars_killed else 0
        else:
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
    deck_path: bool = False,
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
    # SWEG_MAP_REAL_GEOMETRY: when the map carries a sourced deployment polygon,
    # test against the real SHAPE instead of the flat strip above. No real Pariah
    # Nexus zone is a flat strip — they are diagonal, stepped, quadrant, or 18
    # inches deep — so the strip test both admits points outside the real zone
    # and excludes points inside it. `_enemy_dz_poly` stays None when no polygon
    # is present, so every map without sourced geometry is byte-identical.
    _enemy_dz_poly = (map_.deployment_polygon_b if own_is_army_a
                      else map_.deployment_polygon_a) or None

    def _in_enemy_dz(pos) -> bool:
        if _enemy_dz_poly is not None:
            return map_.in_deployment_zone(pos, is_army_a=not own_is_army_a)
        return enemy_dz_lo <= pos[1] <= enemy_dz_hi

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
                if not _in_enemy_dz((ux, uy)):
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
            if _in_enemy_dz((ux, uy)):
                enemy_dz_count += 1

    # LC-2: gate Engage / BEL behind the per-round tactical-secondary
    # draw. Each side scores AT MOST ONE per round (the secondary that's
    # "active" this turn per the alternating schedule).
    side = "A" if own_is_army_a else "B"
    # SECONDARY-POSFIX (env-gated SWEG_SECONDARY_POSFIX, default OFF, byte-identical
    # off). On the Tactical-DECK path the hand-draw already gates cadence (a card in
    # hand scores every round, persistent-while-held per CA-2025-26); applying the
    # legacy LC-2 every-other-round schedule ON TOP of it double-gates Engage /
    # Behind Enemy Lines, halving them (data/_secondary_model_design.md — the sim
    # 11.4 vs real 22.7 secondary gap). When set + on the deck path, skip LC-2 so a
    # held positional card scores every round it is achieved. Asymmetric: only pays
    # a unit that ACHIEVES board-quarter spread / enemy-DZ presence (the mobility
    # secondaries) — a durable gunline clustered on 1-2 markers does not newly
    # qualify. Legacy union path (deck_path=False) is unchanged.
    if deck_path and __import__("os").environ.get("SWEG_SECONDARY_POSFIX") == "1":
        engage_active = True
        bel_active = True
    else:
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


def _enemy_qualifying_horde_units(enemy_army: "Army") -> int:
    """Count enemy units that could ever concede Cull the Horde.

    Cull the Horde scores on destroying an enemy INFANTRY unit whose Starting
    Strength was `CULL_THE_HORDE_MIN_MODELS` (13) or more. Like
    `_enemy_monster_vehicle_count` this reads the whole roster, board and
    reserves, because the picker fires at battle start.

    The simulator stores one `Unit` instance per physical model, so a codex unit
    is a GROUP of instances sharing a `squad_id` — this counts groups, never
    instances. Counting instances would report every 13-model army as having 13
    qualifying units and defeat the purpose. Single-model units (`squad_id < 0`)
    can never reach 13 and are skipped.

    Used only by `_pick_fixed_pair_full` under `SWEG_CULL_PICK_AWARE`.
    """
    sizes: Dict[int, int] = {}
    for u in enemy_army.units:
        sid = getattr(u, "squad_id", -1)
        if sid >= 0:
            sizes[sid] = sizes.get(sid, 0) + 1
    return sum(1 for n in sizes.values() if n >= CULL_THE_HORDE_MIN_MODELS)


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
    """M2 real 2-card Tactical secondary deck — CONSUMER gate-read.

    GATE-MISMATCH FIX (SWEG_TAC_DECK_CONSUMER_FIX, ADOPTED default-on; "0"
    is the kill-switch): the deck was ADOPTED default-on at wave 210, but only the
    simulator-side read (`Battle._tac_deck_enabled`, `!= "0"` = default-ON)
    was flipped — this module-side read stayed at `== "1"` (default-OFF), so
    at production defaults the two halves of the pipeline DISAGREED: the
    Battle initialised 2-card tactical decks while this module's
    `pick_secondaries` path stuffed the full legacy union of card sources,
    and the scorer's fallback branch scored all of them, every round,
    uncapped — the measured ~39 secondary victory points per player per game
    versus the real 22.7 (docs/REAL_META_SIGNATURES.md). Same defect class
    as the wave-254 markerlight consumer gate-read fix. With the fix gate ON
    this read matches the simulator's (`SWEG_TAC_DECK != "0"`, default-ON);
    with it OFF the legacy mismatched read is preserved byte-identically.
    Rides on the existing wave-210 deck citation; the fix changes no rule
    content, only makes the adopted rule actually run end-to-end."""
    import os
    # ADOPTED default-on 2026-07-02 (fidelity-first ruling): full-frame N=40
    # vs sc35a read gated 2.37 -> 5.09 — the quantified compensating error
    # (durables up to +17.9, hordes to -12.5) — and the going-first signature
    # fell from ~69% to 50.0% (real 49-52%). `=0` restores the mismatched
    # legacy read byte-identically.
    if os.environ.get("SWEG_TAC_DECK_CONSUMER_FIX", "1") != "0":
        return os.environ.get("SWEG_TAC_DECK", "1") != "0"
    return os.environ.get("SWEG_TAC_DECK") == "1"


def _fixed_pool_full_enabled() -> bool:
    """D5 — the printed 5-card Fixed Secondary pool (SWEG_FIXED_POOL_FULL,
    DEFAULT-ON). The printed Chapter Approved 2025-26 Fixed pool is Assassination,
    No Prisoners, Cull the Horde, Bring It Down and Cleanse; a Fixed player picks
    TWO (distinct) of them. The pre-fix picker excluded No Prisoners and Cleanse
    and could resolve BOTH slots to Cull the Horde (a degenerate duplicate). `=0`
    restores the pre-fix 3-card picker byte-identically. Cited
    `simulator.fixed_pool_full`."""
    return os.environ.get("SWEG_FIXED_POOL_FULL", "1") != "0"


def _pick_fixed_pair_full(own_army: "Army", enemy_army: "Army") -> List[str]:
    """D5 — pick TWO DISTINCT Fixed Secondary Missions from the printed 5-card
    Fixed pool. Slots 1 and 2 keep the pre-fix target-richness heuristic exactly
    (so bring_it_down + cull, bring_it_down + assassination and cull + assassination
    are unchanged); only the degenerate case where both slots would resolve to
    Cull the Horde is corrected, by falling through the rest of the printed Fixed
    pool for a DISTINCT second pick — No Prisoners first (broad generic-kill,
    achievable against any roster; the natural pick facing a chaff-heavy,
    character-light, vehicle-light enemy) then Cleanse. This removes the duplicate
    the printed 'note down which TWO Fixed Missions' rule forbids, and makes No
    Prisoners and Cleanse legal Fixed picks."""
    mv = _enemy_monster_vehicle_count(enemy_army)
    enemy_chars = sum(1 for u in enemy_army.units if _is_character(u))
    slot1 = "bring_it_down" if mv >= _BID_TARGET_THRESHOLD else "cull_the_horde"
    slot2 = "assassination" if enemy_chars >= 2 else "cull_the_horde"
    # SWEG_CULL_PICK_AWARE (default-off, byte-identical when unset): do not note
    # down Cull the Horde against a roster that cannot concede it.
    #
    # The two positive tests above are already composition-aware — Bring It Down
    # requires _BID_TARGET_THRESHOLD enemy MONSTER/VEHICLE units, Assassination
    # requires two or more enemy CHARACTERs — but Cull the Horde is the FALLBACK
    # for both slots and is taken whenever those tests fail, with no check that
    # the enemy fields a single qualifying unit. Cull scores only on destroying an
    # enemy INFANTRY unit whose Starting Strength was CULL_THE_HORDE_MIN_MODELS
    # (13) or more, so against an elite roster of five- and ten-model squads it is
    # unscoreable. MEASURED with scripts/_cull_pick_waste_probe.py over all 1386
    # ordered faction pairs: 294 picks take Cull and 231 of them — 78.6 percent —
    # face an enemy with ZERO qualifying squads. The waste is near-uniform across
    # factions (about 17.5 percent of every faction's pairs) because it is set by
    # which OPPONENTS field thirteen-plus-model squads, and every faction faces
    # the same field.
    #
    # 10e Pariah Nexus notes the two Fixed Missions down before the battle with
    # both army lists known, so a composition-aware pick is what the rule
    # describes; an unscoreable note-down is the artefact. The fall-through order
    # is the one this function already documents for the duplicate case — No
    # Prisoners first, being broad generic kill achievable against any roster,
    # then Cleanse.
    # SUBSTITUTE ONLY INTO PASSIVE CARDS (corrected 2026-07-28 after the first
    # screen). The original fall-through was ("no_prisoners", "cleanse"), which
    # looked harmless — the duplicate-slot path below uses the same order — but
    # CLEANSE IS AN ACTION CARD, and that made this gate do something it never
    # claimed to.
    #
    # When both positive tests fail, slot1 and slot2 are BOTH cull_the_horde, so
    # the old loop filled the first with No Prisoners and the second, that name
    # now being taken, with Cleanse. Performing Cleanse commits a unit and locks
    # it out of shooting and charging (`_unit_can_perform_action`, whose own
    # docstring notes "a Knight's units are all productive shooters / fighters,
    # so none pass ... a broad army has spare non-shooting bodies that do"). So a
    # card-selection fix silently became a unit-commitment change.
    #
    # That is what the full-matrix screen measured: Imperial Knights +2.95 and
    # Chaos Knights +4.80 — they are the hordeless ENEMY, so their opponents
    # substituted, committed chaff to Cleanse, and fought with less — while
    # Aeldari, which substitutes often because much of the field is elite, lost
    # 6.38. The scoring swap was never the dominant term.
    #
    # The corrected order is passive-only and composition-aware, in the same
    # style as the two tests above: No Prisoners is broad generic kill and is
    # achievable against any roster, so it is always a legal replacement;
    # Assassination needs an enemy CHARACTER and Bring It Down an enemy
    # MONSTER or VEHICLE, so each is offered only where it can actually score.
    # If nothing passive qualifies the slot KEEPS Cull the Horde — an
    # unscoreable note-down is a smaller error than silently buying an Action.
    if (os.environ.get("SWEG_CULL_PICK_AWARE", "0") == "1"
            and _enemy_qualifying_horde_units(enemy_army) == 0):
        _passive = ["no_prisoners"]
        if enemy_chars >= 1:
            _passive.append("assassination")
        if mv >= 1:
            _passive.append("bring_it_down")
        _slots = [slot1, slot2]
        for _i, _slot in enumerate(_slots):
            if _slot != "cull_the_horde":
                continue
            for _cand in _passive:
                if _cand not in _slots:
                    _slots[_i] = _cand
                    break
        slot1, slot2 = _slots
    if slot2 == slot1:
        for candidate in ("no_prisoners", "cleanse", "assassination",
                          "bring_it_down"):
            if candidate != slot1:
                slot2 = candidate
                break
    return [slot1, slot2]


def _pick_fixed_kill_pair(own_army: "Army", enemy_army: "Army") -> List[str]:
    """The 2 Fixed cards an army brings (CA-2025-26 Fixed pool). Factored out so
    both the legacy path and the M2 FIXED track use the identical heuristic.

    D5 (SWEG_FIXED_POOL_FULL, default ON): pick two DISTINCT cards from the printed
    5-card Fixed pool (Assassination, No Prisoners, Cull the Horde, Bring It Down,
    Cleanse) — see `_pick_fixed_pair_full`. `SWEG_FIXED_POOL_FULL=0` restores the
    pre-fix 3-card picker below byte-identically:

      Slot 1: enemy has >= 3 MONSTER/VEHICLE units → bring_it_down,
              else → cull_the_horde (the broadest remaining kill card; fires
              whenever an enemy INFANTRY unit with Starting Strength 13+ is
              destroyed, which is common against any body army).
      Slot 2: enemy has >= 2 CHARACTER units → assassination, else → cull_the_horde.

    In the degenerate case where both slots resolve to cull_the_horde the pre-fix
    picker runs two copies (the scorer gates on `"cull_the_horde" in chosen`, so
    two copies collapse to one scoring pass) — the duplicate D5 removes.
    """
    if _fixed_pool_full_enabled():
        return _pick_fixed_pair_full(own_army, enemy_army)
    fixed: List[str] = []
    if _enemy_monster_vehicle_count(enemy_army) >= _BID_TARGET_THRESHOLD:
        fixed.append("bring_it_down")
    else:
        fixed.append("cull_the_horde")
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
        * Otherwise → "cull_the_horde"
        (No Prisoners is a Tactical-only card in CA-2025-26 tournament
        play and is excluded from Fixed picks entirely.)
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

    # Fixed picks: no_prisoners is excluded (Tactical-only in CA-2025-26
    # tournament play). Use _pick_fixed_kill_pair for the canonical heuristic.
    fixed: List[str] = _pick_fixed_kill_pair(own_army, enemy_army)
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
        # Action-economy build: an army with spare cheap bodies also brings the
        # three CA-2025-26 Tactical action cards. They are inert unless
        # SWEG_ACTION_ECONOMY is set (the simulator gates both assignment and
        # scoring). Appending them only under the same gate keeps the OFF path's
        # chosen tuple byte-identical (the legacy union scorer never sees them).
        if _action_economy_enabled():
            tactical.append("establish_locus")
            tactical.append("recover_assets")
            tactical.append("a_tempting_target")
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
