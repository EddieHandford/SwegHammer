"""Army — a collection of units with command point tracking."""

from __future__ import annotations

import dataclasses
import os
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .detachments import Detachment, default_detachment_for_faction
from .stratagems import STARTING_CP
from .units import (
    Unit,
    UnitProfile,
    _distribute_squad_slots,
    _loadout_entry_to_weapon_fields,
    _unflatten_model_loadouts,
)


# Engagement distance (in inches) inside which Look Out Sir / Lone Operative
# stop blocking the shot. Wahapedia 10e core: "...unless the attacking unit
# is within 12\" of the target."
_LOS_RANGE_INCHES: float = 12.0
# Bodyguard radius (in inches) used by Look Out Sir — a friendly non-CHARACTER
# within this distance of the target shields it. Wahapedia 10e core wording.
_BODYGUARD_RADIUS_INCHES: float = 3.0


def _xy_distance(a, b) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def can_target_for_ranged(
    attacker: Unit,
    target: Unit,
    friendly_units: Iterable[Unit],
) -> bool:
    """Return True iff `attacker` is permitted to make a ranged attack against
    `target` under the 10e core targeting rules (Look Out Sir + Lone Operative).

    Args:
        attacker: the firing unit. Its `.position` is read for the 12" check.
        target: the prospective target unit. Its profile keywords and
            `.lone_operative` flag drive the gates. `target.position` is read
            for the bodyguard / 12" checks.
        friendly_units: alive units allied to the TARGET (i.e. the defender's
            army), used to find non-CHARACTER bodyguards within 3" of the
            target for Look Out Sir.

    Rules implemented (Wahapedia 10e core):
      * Look Out Sir (`simulator.look_out_sir`): if the target is a CHARACTER
        unit and is NOT also MONSTER or VEHICLE, and a friendly non-CHARACTER
        unit (other than the target itself) is within 3" of the target, then
        the attack cannot be made unless the attacker is within 12" of the
        target.
      * Lone Operative (`simulator.lone_operative`): if the target has the
        Lone Operative ability, the attack can only be made from within 12".
      * PRECISION (`simulator.precision_keyword`): if the attacker carries
        a PRECISION ranged weapon (collapsed onto the unit-level `precision`
        flag by the mapper), the Look Out Sir bodyguard gate is bypassed.
        Real 10e text: "...attack can be allocated to that CHARACTER model
        instead of following the normal attack-allocation rules." The
        simulator collapses Look Out Sir into a TARGETING gate (since
        characters are modelled as standalone units and there is no
        attached-unit wound-allocation step), so a precision attacker's
        equivalent is being permitted to shoot the otherwise-shielded
        character. Lone Operative is NOT bypassed — that is a separate
        ability with its own keyword text. Cited as
        `simulator.precision_keyword`.

    Returns False when either gate blocks the shot, True otherwise. The check
    is order-insensitive — both gates compose so a Lone Operative CHARACTER
    huddled next to an INFANTRY unit just gets the same 12" cap.
    """
    distance = _xy_distance(attacker.position, target.position)
    tp = target.profile
    target_kw = set(tp.unit_keywords or ())

    # Lone Operative — keyword-gated, hard 12" cap. NOT bypassed by PRECISION.
    if getattr(tp, "lone_operative", False) and distance > _LOS_RANGE_INCHES:
        return False

    # Look Out Sir — only fires on CHARACTERS that aren't MONSTER/VEHICLE.
    is_los_eligible_character = (
        "CHARACTER" in target_kw
        and "MONSTER" not in target_kw
        and "VEHICLE" not in target_kw
    )
    if is_los_eligible_character and distance > _LOS_RANGE_INCHES:
        # PRECISION bypass: a PRECISION-bearing attacker is permitted to
        # pick the CHARACTER directly even when a bodyguard is in range.
        # Real-rule equivalent of "allocate the wound to the CHARACTER".
        if getattr(attacker.profile, "precision", False):
            return True
        # Bodyguard scan: any friendly non-CHARACTER unit within 3" of the
        # target (excluding the target itself).
        for f in friendly_units:
            if f is target or not f.is_alive:
                continue
            fkw = set(f.profile.unit_keywords or ())
            if "CHARACTER" in fkw:
                continue
            if _xy_distance(f.position, target.position) <= _BODYGUARD_RADIUS_INCHES:
                return False

    return True


# Faction tag for the Leagues of Votann army-rule (Eye of the Ancestors /
# Judgement Tokens). Centralised so the detection in army.py + simulator.py
# can't drift from each other. The string matches code.factions.faction_of
# for the Leagues of Votann codex.
VOTANN_FACTION_TAG = "Leagues of Votann"


class Army:
    """A named collection of unit instances participating in a battle."""

    def __init__(
        self, name: str, in_cover: bool = False,
        detachment: Optional[Detachment] = None,
    ) -> None:
        self.name = name
        self.units: List[Unit] = []
        # Cached result of [u for u in self.units if u.is_alive]. Invalidated
        # by Unit.current_health.setter on life-state transitions and by
        # _add_live_unit(). Rebuilt lazily on next alive_units access.
        self._alive_cache: Optional[List[Unit]] = None
        self._squad_count_cache: Optional[Dict[str, int]] = None
        # SQUAD-ACTIVATION (Lever 1, P1): monotonic counter handing out a unique
        # squad_id to each instantiated codex squad via add_squad(). Starts at 0.
        self._next_squad_id: int = 0
        # 10e Strike Force standard: each side starts with 3 CP. Battle then
        # drips +1/round via stratagems.award_command_phase_cp (capped at 6).
        self.command_points: int = STARTING_CP
        self.in_cover: bool = in_cover
        # Army-wide passive rules. Auto-resolves from the army's primary
        # faction (first unit's faction tag) when not explicitly set.
        self.detachment: Optional[Detachment] = detachment
        # LC-5: Warlord designation. 10e Strike Force requires every army
        # to designate one CHARACTER as the Warlord. Set lazily on first
        # access via `warlord_uid` property — picks the first alive
        # CHARACTER in deterministic seed order, mirroring the
        # tournament list rule "first CHARACTER on the list page is
        # typically the Warlord by convention". Read by the secondary
        # scorer's Assassination calculation to award +1 bonus VP when
        # the Warlord is among the destroyed CHARACTERs this round (real
        # Pariah Nexus Assassination rule). None means "no CHARACTER in
        # army" (rare edge case for synthetic / Combat Patrol lists).
        # Cited as `simulator.warlord_designation`.
        self._warlord_uid: Optional[int] = None
        # Battle Focus tokens (Aeldari ASURYANI rule, 10e). Allocated at
        # battle start by the simulator based on faction + battle size
        # (4 at the default Strike Force ~1000pt budget). Spent during
        # an ASURYANI unit's activation to grant [ASSAULT] for that turn
        # (i.e. shoot after Advance).
        self.battle_focus_tokens: int = 0
        # Strands of Fate (Aeldari army rule, 10e) — 6D6 Fate dice pool
        # rolled at start of battle and spent thereafter as substitute
        # rolls (hit/wound/save/charge/advance). Stored sorted descending
        # so the spend heuristic can `pop_high(threshold)` / `pop_low()`
        # in O(1) on a tiny list. Populated by Battle.run for AELDARI
        # armies; empty on non-Aeldari armies and once exhausted.
        # Cited as `simulator.strands_of_fate`.
        self.fate_dice: List[int] = []
        # Adepta Sororitas army rule — Acts of Faith / Miracle Dice (10e).
        # Bank of pre-rolled D6 values. Gain 1 at the start of each battle
        # round AND 1 each time a Sororitas unit from this army is
        # destroyed. Spent by substituting a banked value for one D6 in any
        # of: Advance, Battle-shock, Charge, Damage, Hit, Saving throw,
        # Wound. The simulator's spend AI is a greedy heuristic (pop the
        # lowest die that flips fail -> success on hit/wound/save, same
        # shape as fate_dice). A soft cap of 8 is enforced to keep the
        # pool from growing without bound in a stalled simulation —
        # tournament games rarely exceed 6-7 banked dice and the codex
        # has no in-text cap, so 8 is a generous safety bound rather than
        # a rule. Stored sorted descending. Empty on non-Sororitas armies.
        # Cited as `simulator.acts_of_faith`.
        self.miracle_dice: List[int] = []
        # Squad rebuild Stage C — ONE generalized per-round "once per codex
        # unit per round" budget, replacing four separate sets that previously
        # tracked the same shape of state (Acts of Faith, and the three Strands
        # of Fate gates: advance / hit / save). The simulator instantiates each
        # model in a squad as a separate Unit instance, so a 10-model squad
        # becomes 10 Unit objects; without a unit-level budget each instance
        # could independently spend its faction's once-per-codex-unit-per-round
        # resource, giving a 10x over-count. `_unit_budget_used` maps an effect
        # name ("aof" / "fate_advance" / "fate_hit" / "fate_save") to the set of
        # keys (squad_id int when >= 0, else profile.name str — the task #28
        # squad_id re-key; the mixed int/str type is intentional and cannot
        # collide) that have already spent that effect this round. Reset wholesale
        # at the start of each battle round by Battle._run_round. ALWAYS present
        # (not faction-gated) so standalone tests with no Battle still read an
        # empty-but-present budget via the unit_budget_available / mark_unit_budget
        # methods below. Effect citations unchanged: `simulator.acts_of_faith`
        # (aof) and `simulator.strands_of_fate` (fate_advance / fate_hit /
        # fate_save). Wahapedia Strands of Fate:
        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
        self._unit_budget_used: dict = {}
        # Back-reference to the Battle currently running this army. Set
        # by Battle.__init__ so Unit.attack can dispatch the Command
        # Re-Roll stratagem without threading callbacks through every
        # call site. None when no Battle is active (catalogue tests, etc.).
        self._battle_ref = None
        # Leagues of Votann army rule — Eye of the Ancestors / Judgement
        # Tokens. When an enemy unit destroys a Votann model, that enemy
        # unit gains a token. Tokens stack on the enemy unit and grant
        # escalating re-roll buffs to Votann attackers shooting/fighting
        # that token-marked target. Keyed by enemy unit uid; value is the
        # accumulated token count for that target. Only populated on a
        # Votann army (see `is_votann_army`); other armies keep this dict
        # empty for the whole battle.
        self.judgement_tokens: Dict[str, int] = {}
        # Orks WAAAGH! army rule — declared once per battle at the start of
        # an Ork player's Command phase. Stores the round in which WAAAGH!
        # was unlocked; `Unit.attack` reads this against the live battle
        # round to apply the +1 to wound melee buff. None = not yet declared.
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#WAAAGH!
        # Cited as `simulator.waaagh`.
        self.waaagh_round_unlocked: Optional[int] = None
        # Tyranids Shadow in the Warp — declared once per battle in either
        # player's Command phase. Stores the round in which Shadow was
        # unleashed; the Battle-shock phase reads this against the live battle
        # round to apply the -1 to enemy Battle-shock tests (only on that
        # round, within 6"). None = not yet declared.
        # TYRANIDS-DIAG-5 (2026-05-24) — collapsed from the prior always-on
        # 12" aura to the codex-correct once-per-battle 6" trigger. The
        # previous always-on implementation over-applied the debuff every
        # round, contributing to Tyranids +24pt sim over-perf. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/tyranids/ "Shadow in the
        # Warp". Cited as `simulator.shadow_in_the_warp`.
        self.shadow_in_the_warp_used_round: Optional[int] = None
        # Genestealer Cults Cult Ambush — Resurgence points pool used to
        # revive destroyed CULT INFANTRY units at round end. Populated at
        # battle start by the simulator for GSC armies (Strike Force default
        # = 10 points). 0 / unused on non-GSC armies. Each revival in the
        # round-end hook spends a fixed cost (proxy for the per-unit table
        # in the codex). Tracked per battle, never resets between rounds.
        # Cited as `simulator.cult_ambush_resurgence`.
        self.cult_ambush_resurgence_points: int = 0
        # Starting points snapshot — captured once at battle start by the
        # simulator so the WAAAGH! AI can compare current points to the
        # initial roster (the trigger fires early if Orks are taking heavy
        # losses). 0 until the simulator sets it.
        self.starting_points: float = 0.0
        # Adeptus Mechanicus army rule — Doctrina Imperatives. At the start
        # of each battle round, the AdMech player picks ONE of two buff-only
        # imperatives (no penalty side — Wahapedia 10e):
        #   * "protector": +1 BS on ranged attacks (army-wide); defensive
        #     -1 to hit for incoming melee attacks against BATTLELINE-adjacent
        #     AdMech units.
        #   * "conqueror": +1 WS on melee attacks (army-wide); +1 AP on all
        #     attacks for BATTLELINE-adjacent AdMech units.
        # Reset to None each round; re-picked by the simulator's AI based on
        # the army's role mix and engagement count. None on a non-AdMech
        # army (alive_units gate at round-start, faction-checked at attack-
        # resolution time too). Cited as `simulator.doctrina_imperatives`.
        self.doctrina_imperative: Optional[str] = None
        # World Eaters army rule — Blood Tithe (10e). Codex-wide accumulator
        # incremented by 1 each time a friendly WORLD EATERS unit dies OR an
        # enemy unit is destroyed by a WORLD EATERS unit. Spent at the start
        # of any phase on Boons of Khorne benefits — the simulator's AI
        # spends priority-greedy in `_run_round` (BT>=4 grants Lethal Hits
        # on a WE unit for the phase; BT>=3 grants +1 CP). Stays 0 on a
        # non-WE army (the spend gate checks faction tag before running).
        # Cited as `simulator.blood_tithe`.
        self.blood_tithe: int = 0
        # Round number in which a 4-BT Lethal Hits spend fired. Read by
        # Unit.attack against the live battle round (via _battle_ref) to
        # gate effective_lethal_hits for World Eaters attackers; the buff
        # is scoped to "this phase" in the codex, which we collapse to
        # "this round" because the simulator activation loop doesn't break
        # round-internal phases out separately. None = not active.
        self.blood_tithe_lethal_hits_round: Optional[int] = None
        # World Eaters army rule — Blessings of Khorne (10e). At the start of
        # each battle round a World Eaters army rolls 8D6 and activates up to
        # 2 Blessings of Khorne; each Blessing requires a double (or triple)
        # of at least a stated value. Each Blessing applies to every unit in
        # the army with the ability until end of battle round. SwegHammer
        # tracks the round in which each Blessing fired plus a single
        # "blessings_active_round" stamp; `Unit.attack` checks the stamp
        # against the live battle round and applies the buff only on the
        # matching round (auto-lapses next round even if the simulator skips
        # the clear). Three Blessings are modelled:
        #   blessings_martial_excellence_round  — melee SUSTAINED HITS 1
        #   blessings_warp_blades_round         — melee LETHAL HITS
        #   blessings_cleaving_blows_round      — melee AP+1
        # All start as None (inactive). The remaining nine Blessings are
        # skipped per the same APPROXIMATION discipline used for Doctrina /
        # Dark Pacts — they touch plumbing the simulator doesn't expose
        # (per-target Battle-shock, pile-in distance, Engagement Range
        # mortals, etc.) and the three modelled here cover the high-value
        # offensive uplift. Cited as `simulator.blessings_of_khorne`.
        self.blessings_martial_excellence_round: Optional[int] = None
        self.blessings_warp_blades_round: Optional[int] = None
        self.blessings_cleaving_blows_round: Optional[int] = None
        # Cult of Magic Cabbalistic Empowerment (Thousand Sons stratagem,
        # 1 CP). When set True for the round, the simulator's _try_doombolt
        # dispatcher pays 3 MW instead of the base 2 MW (median D3) to its
        # target. Reset to False each round by Battle._clear_transient_stratagem_flags.
        # Cited as `Stratagem.Cabbalistic Empowerment`.
        self.cabbalistic_doombolt_boost: bool = False
        # Virulent Vectorium Putrid Detonation (Death Guard stratagem, 1 CP).
        # When True for the round, any DG VEHICLE / DG MONSTER that dies on
        # this army's side and has the Deadly Demise ability auto-succeeds
        # the d6 roll (mortals always trigger). APPROXIMATION: real text
        # targets one specific destruction; the simulator arms the flag at
        # round start and any qualifying death this round auto-detonates.
        # Reset by Battle._clear_transient_stratagem_flags. Cited as
        # `Stratagem.Putrid Detonation`.
        self.putrid_detonation_armed: bool = False
        # Virulent Vectorium Plaguesurge (Death Guard stratagem, 2 CP).
        # When True for the round, the army's Contagion Range is conceptually
        # +3" — the simulator currently hard-codes contagion radius at 6"
        # so this flag is APPROXIMATED as informational only (the buff isn't
        # consumed by any active code path yet). Reset by
        # Battle._clear_transient_stratagem_flags. Cited as
        # `Stratagem.Plaguesurge`.
        self.plaguesurge_active: bool = False
        # CP discount / refund mechanics tied to specific Warlord characters
        # (Belisarius Cawl, Roboute Guilliman, Trazyn the Infinite, Lord of
        # Contagion). The Battle initialiser scans this army's CHARACTER
        # units at start-of-battle and seeds the fields below from the
        # bearer's LeaderAbility, IFF that character is the army's Warlord.
        self.cp_refund_remaining: int = 0
        self.first_stratagem_free_this_round: bool = False
        self._warlord_first_strat_free_enabled: bool = False
        # Universal per-Command-phase detachment-stratagem cap (faction-neutral
        # AI heuristic). 10e core rules don't impose a hard cap on stratagems
        # fired per Command phase, but real-player CP economy averages ~1
        # stratagem per Command phase per army; the simulator's round-start
        # dispatcher in Battle._apply_detachment_stratagems used to fire every
        # green-lit detachment stratagem on offer, stacking 3-5+ in a single
        # Command phase on CP-rich detachments (DG Virulent Vectorium, Necron
        # Awakened Dynasty). This counter is reset to 0 at the top of each
        # army's _apply_detachment_stratagems call and incremented inside
        # _fire_stratagem when called from a detachment dispatcher; the
        # dispatcher early-exits once the counter hits STRATAGEM_CAP (1).
        # Faction-neutral: every detachment's dispatch path runs through the
        # same cap. Core Stratagems (Tank Shock, Counter-Offensive,
        # Command Re-Roll) are triggered out-of-band and don't increment
        # this counter — they fire on their own per-phase triggers.
        # Cited as `simulator.stratagem_per_command_phase_cap` (APPROXIMATION).
        self.stratagems_fired_this_command_phase: int = 0
        # Astra Militarum Voice of Command — Flexible Command stratagem
        # (Combined Arms, 2 CP) widens the Order-eligible target set from
        # BATTLELINE INFANTRY only to ALSO include BATTLELINE VEHICLE
        # (SQUADRON) for the round it fires. The simulator's
        # `_try_flexible_command` dispatcher sets this True at round start;
        # the round-start `_clear_transient_stratagem_flags` flips it back
        # to False before the next round's Order dispatch runs.
        # Cited as `Stratagem.Flexible Command`.
        self.orders_eligible_squadron_this_round: bool = False
        # Astra Militarum Voice of Command — Inspired Command stratagem
        # (Combined Arms, 1 CP) grants ONE additional Order this round
        # (codex text: "Your OFFICER can issue one Order as if it were
        # your Command phase"). Decrements as the Order dispatch consumes
        # the extra cap. Cleared each round.
        # Cited as `Stratagem.Inspired Command`.
        self.orders_extra_this_round: int = 0
        # Adeptus Astartes Oath of Moment (army rule, 10e). At the start of
        # each Command phase the Marine player picks one enemy unit; until
        # the start of their next Command phase, every Marine attack against
        # that unit re-rolls BOTH the hit roll and the wound roll (any
        # failure, not just 1s). The simulator picks this in _run_round per
        # round, stores the chosen enemy unit's uid here, and Unit.attack
        # reads it via the army back-reference to gate the re-rolls. None
        # means "no oath this round" (e.g. round 0, or no Marine units alive).
        # Cited as `simulator.oath_of_moment`.
        self.oath_target_uid: Optional[str] = None
        # Previous round's Oath target uid, snapshotted at the top of the
        # Command phase before `oath_target_uid` is reset. _pick_oath_target
        # reads this to bias picks AWAY from a still-alive prior target when
        # a comparably-valuable runner-up exists — modelling the real-player
        # behaviour of spreading damage across multiple anchors rather than
        # spamming the same anchor 5 rounds in a row. Cited as part of
        # `simulator.oath_of_moment` (heuristic, not a codex constraint).
        self.prev_oath_target_uid: Optional[str] = None
        # Adeptus Mechanicus — Belisarius Cawl's "Invocation of Machine
        # Vengeance" Canticle (10e). At the start of each Command phase, while
        # a Belisarius Cawl model is alive, the AdMech player designates one
        # enemy unit as the Machine Vengeance target; until the start of the
        # next Command phase, every friendly ADEPTUS MECHANICUS attack against
        # that unit may re-roll the Hit roll. This mirrors the Adeptus Astartes
        # Oath of Moment substrate exactly: the simulator picks the target in
        # _run_round per round (_pick_machine_vengeance_target), stores the
        # chosen enemy unit's uid here, and Unit.attack reads it via the army
        # back-reference to gate the re-roll. None means "no Machine Vengeance
        # this round" (e.g. round 0, or no Belisarius Cawl alive). FAITHFUL
        # APPROXIMATION: Cawl picks one of three Canticles per Command phase
        # (Machine Vengeance / Mantra of Discipline / Shroudpsalm); we model
        # him always choosing the offensive Machine Vengeance, the common
        # competitive pick. Cited as `simulator.machine_vengeance`.
        self.machine_vengeance_target_uid: Optional[str] = None
        # T'au Empire Markerlights → Guided mechanic (10e army-wide). At the
        # start of this army's Shooting phase, every alive MARKERLIGHT-keyword
        # unit in this army "spots" one enemy unit in LoS within 36"; that
        # enemy's uid is added to this set, and any friendly T'au attacker
        # firing at a target in the set gains [LETHAL HITS] (crit hits
        # auto-wound) when the detachment carries `lethal_hits_on_guided=True`
        # (Mont'ka, all rounds — codex Markerlight base rule, not gated to
        # rounds 1-3 even though the Mont'ka detachment text repeats the
        # window for `army_wide_assault_rounds_1_3`; the Guided LETHAL HITS
        # is the army-wide Markerlight rule). Tokens persist for the
        # marker-spotting army's Shooting phase only — cleared at the end
        # of that army's turn so the buff doesn't leak across rounds.
        # Cited as `simulator.markerlights`.
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights
        self.guided_enemy_uids: Set[str] = set()
        # SECONDARY-SELECTION-V1 — Pariah Nexus Fixed + Tactical secondary
        # choice. Real 10e CA-2025-26 tournament play picks exactly TWO Fixed
        # Secondaries from the pool {bring_it_down, cull_the_horde,
        # assassination} (no_prisoners is Tactical-only in tournament play)
        # OR uses the Tactical deck
        # (drawing per round). The simulator previously scored ALL four
        # Fixed + both Tactical (engage_on_all_fronts, behind_enemy_lines)
        # every round for every army, systematically over-rewarding
        # balanced kill-heavy / mobile armies (Drukhari, Aeldari,
        # Tyranids). This tuple, populated by `secondaries.pick_secondaries`
        # at battle start, restricts the secondary scorer to the picked
        # subset. Defaults to () meaning "no secondaries chosen" —
        # `Battle.__init__` should always call the picker before scoring
        # runs. Cited as `simulator.secondary_selection` (10e Pariah Nexus
        # mission pack: each player selects 2 Fixed or draws Tactical).
        self.chosen_secondaries: Tuple[str, ...] = ()
        # M2 (wave 119) — real 2-card Tactical secondary deck (env-gated
        # SWEG_TAC_DECK). Each army uses one of two tracks, decided by
        # `secondaries.pick_secondaries` from unit count (even-handed, no
        # faction awareness): "FIXED" (2 kill cards scored every round) or
        # "TACTICAL" (a 2-card rotating hand). These three fields are only
        # populated/used when the deck gate is ON; OFF leaves them at their
        # defaults and the legacy union-of-sources scoring runs unchanged.
        #   secondary_track: "FIXED" | "TACTICAL" | None (None == gate off /
        #     not yet picked — the scorer falls back to the legacy path).
        #   tactical_hand: the <=2 Tactical cards currently held (active until
        #     achieved). Scored each round; an achieved card is discarded and a
        #     replacement is drawn from `tactical_deck`.
        #   tactical_deck: the shuffled remaining pool the hand redraws from.
        # The hand + deck are seeded deterministically at battle start (see
        # `Battle._init_tactical_deck`) so PYTHONHASHSEED=0 reproduces.
        # Cited as `simulator.tactical_secondary_deck`.
        self.secondary_track: Optional[str] = None
        self.tactical_hand: List[str] = []
        self.tactical_deck: List[str] = []
        # Coordinated army-level activation plan (#161 / S3). Picked once per
        # round by the simulator's `_pick_army_plan` and consulted by both
        # `activation_queue` (to order units that align with the plan first)
        # and `pick_move_intent` (to bias objective / charge scoring toward
        # the chosen flank). One of:
        #   "LEFT_FLANK"  — push the left half of the map
        #   "RIGHT_FLANK" — push the right half
        #   "MID_PUSH"    — converge on map centre
        #   "HOME_HOLD"   — protect own backline + nearest home objective
        #   "COUNTER"     — react to opponent's biggest threat
        # None outside a battle (catalogue tests, etc.) — the strategy
        # bias is short-circuited when the field is None, preserving the
        # backward-compatible per-unit picks.
        self.army_plan: Optional[str] = None

    # ------------------------------------------------------------------
    # Faction detection
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Strands of Fate helpers (Aeldari army rule, 10e). See Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
    # Real rule: 6D6 rolled at battle start; each die can later be
    # substituted for ONE roll of any d6 the army would make (hit, wound,
    # save, charge, advance, Battle-shock) or that an opponent makes
    # against an AELDARI unit. The simulator uses a greedy heuristic:
    # for "needs N+ to succeed" rolls, pop the lowest die in the pool
    # that still meets N+. Cited as `simulator.strands_of_fate`.
    # ------------------------------------------------------------------

    def has_fate_dice(self) -> bool:
        """True iff at least one Fate die remains in the pool."""
        return bool(self.fate_dice)

    def pop_fate_die_meeting(
        self,
        threshold: int,
        *,
        high_value: bool = True,
    ) -> Optional[int]:
        """Greedy spend: remove and return the LOWEST die in the pool
        that is >= `threshold` (so we don't waste a 6 to pass a 3+ save
        when a 3 in the pool would do). Returns None if no die qualifies.

        The heuristic intentionally avoids ever spending a die that
        would fail the roll — substitution is only worth doing when it
        flips fail -> success.

        AI-5 (claude/sim-calibration-6): added `high_value` tier to model
        real Aeldari players' habit of hoarding the bank for decisive
        moments. When `high_value=False` (low-stakes roll — a single-shot
        damage-1 hit or wound, a defensive save vs a damage-1 attack), the
        spend is gated on the qualifying die actually being a LOW die in
        the bank (value <= 2). In other words: a 1 or 2 in the pool that
        already happens to meet the threshold is fine to burn on a small
        upside, but never spend a 3+ die on a low-stakes flip. This stops
        small Aeldari units from draining the pool on shuriken-catapult
        misses before the decisive charge / save vs lascannon arrives.
        `high_value=True` (charges, advances, saves vs >=2-damage attacks,
        hits/wounds with >=2-damage weapons) keeps the original
        always-spend-if-it-flips behaviour.
        """
        if not self.fate_dice:
            return None
        # fate_dice is kept sorted descending. Scan from the back (lowest)
        # for the first die that meets the threshold.
        best_idx = None
        best_val = None
        for i in range(len(self.fate_dice) - 1, -1, -1):
            v = self.fate_dice[i]
            if v >= threshold:
                if best_val is None or v < best_val:
                    best_idx = i
                    best_val = v
                    # Since the list is sorted descending, the FIRST hit
                    # from the right (lowest) is already the optimum.
                    break
        if best_idx is None:
            return None
        # AI-5 low-stakes gate: only burn the die if it's a 1 or 2. A 3+
        # die is held back for a high-value roll later in the game.
        if not high_value and best_val is not None and best_val >= 3:
            return None
        return self.fate_dice.pop(best_idx)

    def pop_fate_die_for_opponent(self, max_value: int = 1) -> Optional[int]:
        """Defensive substitution: when an OPPONENT is rolling against an
        AELDARI unit (their hit / wound roll), we can substitute one of
        OUR Fate dice for the opponent's roll. We want the substitution
        to FAIL — so pop a die with value <= `max_value` (default 1).
        Returns None if no qualifying die remains.

        This implements the rule's text: "...or a unit from your army is
        the target of an attack...". The simulator currently only uses
        this in the most clear-cut cases (forcing an enemy hit roll to a
        natural 1 to whiff the attack outright) to keep the heuristic
        conservative.
        """
        if not self.fate_dice:
            return None
        # Scan from the back (lowest) for the first die <= max_value.
        # Sorted-descending invariant means the smallest are at the end.
        for i in range(len(self.fate_dice) - 1, -1, -1):
            v = self.fate_dice[i]
            if v <= max_value:
                return self.fate_dice.pop(i)
            else:
                # Once we cross above max_value, no further candidates
                # exist (list is sorted descending).
                break
        return None

    # ------------------------------------------------------------------
    # Acts of Faith helpers (Adepta Sororitas army rule, 10e). See
    # Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/
    # Real rule: gain 1 Miracle die at the start of each battle round, and
    # +1 each time a Sororitas unit is destroyed. A unit with the Acts of
    # Faith ability may perform one Act per phase: before any d6 roll
    # (Advance / Battle-shock / Charge / Damage / Hit / Save / Wound),
    # substitute one banked Miracle die for ONE of the dice in that
    # roll (multi-die rolls like Charge only allow one substitution).
    # The simulator's greedy heuristic: substitute only when a banked
    # die would flip a fail -> success. Cited as `simulator.acts_of_faith`.
    # ------------------------------------------------------------------

    # Soft cap on the Sororitas Miracle Dice bank. The codex imposes no
    # hard limit; in practice tournament games end at 6-7 dice. The cap
    # keeps the pool from growing without bound in a stalled simulation.
    MIRACLE_DICE_BANK_CAP = 8

    def has_miracle_dice(self) -> bool:
        """True iff at least one Miracle die remains in the pool."""
        return bool(self.miracle_dice)

    def gain_miracle_dice(self, n: int, rng) -> None:
        """Roll `n` D6 and add them to the pool, then re-sort descending
        and trim down to MIRACLE_DICE_BANK_CAP. `rng` is the random
        module / instance the simulator is already using (passed in so
        seeded runs stay deterministic).
        """
        for _ in range(n):
            self.miracle_dice.append(rng.randint(1, 6))
        # Keep sorted descending so the pop helpers can scan from the
        # back for the lowest qualifying die.
        self.miracle_dice.sort(reverse=True)
        if len(self.miracle_dice) > self.MIRACLE_DICE_BANK_CAP:
            # Trim from the tail — discard the LOWEST dice when over
            # cap, since they're the least valuable to keep.
            self.miracle_dice = self.miracle_dice[: self.MIRACLE_DICE_BANK_CAP]

    def aof_squad_available(self, profile_name: str, squad_id: int = -1) -> bool:
        """True iff the squad has NOT yet used its Acts of Faith budget this
        round. SOROR-ACTS-OF-FAITH-V1 / task #28 squad_id re-key: key on
        squad_id when the unit has a valid squad_id (>= 0), otherwise fall
        back to profile_name. This prevents two different squads that share
        the same datasheet name (e.g. two separate Battle Sisters Squad units
        on the table) from being throttled by each other's AoF spend.
        One AoF spend per codex unit per phase — codex wording enforced at
        the correct granularity. Cited as `simulator.acts_of_faith`.
        """
        key = squad_id if squad_id >= 0 else profile_name
        return self.unit_budget_available("aof", key)

    def aof_squad_mark_used(self, profile_name: str, squad_id: int = -1) -> None:
        """Record that the squad has used its Acts of Faith budget this round.
        SOROR-ACTS-OF-FAITH-V1 / task #28 squad_id re-key. Cited as
        `simulator.acts_of_faith`.
        """
        key = squad_id if squad_id >= 0 else profile_name
        self.mark_unit_budget("aof", key)

    def unit_budget_available(self, effect: str, key) -> bool:
        """True if `key` (squad_id int or profile.name str) has NOT yet used the
        once-per-unit-per-round `effect`. Squad-rebuild Stage C: generalizes the
        former per-effect _<x>_names_used_this_round sets into one keyed budget."""
        return key not in self._unit_budget_used.get(effect, ())

    def mark_unit_budget(self, effect: str, key) -> None:
        """Record that `key` has used `effect` this round."""
        self._unit_budget_used.setdefault(effect, set()).add(key)

    def pop_miracle_die_meeting(self, threshold: int) -> Optional[int]:
        """Greedy spend: remove and return the LOWEST die in the pool
        that is >= `threshold`. Mirrors `pop_fate_die_meeting` — the
        heuristic only substitutes when the swap converts fail ->
        success, never when it would still fail.
        """
        if not self.miracle_dice:
            return None
        # miracle_dice is kept sorted descending. Scan from the back
        # (lowest) for the first die that meets the threshold.
        for i in range(len(self.miracle_dice) - 1, -1, -1):
            v = self.miracle_dice[i]
            if v >= threshold:
                return self.miracle_dice.pop(i)
        return None

    @property
    def is_votann_army(self) -> bool:
        """True iff at least one unit in this army carries the Votann faction
        tag. Used to gate the Eye of the Ancestors / Judgement Tokens
        bookkeeping — non-Votann armies never gain or read tokens.

        The detection scans all units (not just `units[0]`) so an army that
        leads with a Codex Agents allied character still resolves correctly
        as long as the bulk of the roster is Votann.
        """
        return any(u.profile.faction == VOTANN_FACTION_TAG for u in self.units)

    # ------------------------------------------------------------------
    # Army construction
    # ------------------------------------------------------------------

    def add_unit(self, profile: UnitProfile) -> None:
        # Back-compat: a lone unit is a one-model squad with its own squad_id.
        self.add_squad(profile, 1)

    def add_squad(self, profile: UnitProfile, size: int = 1) -> None:
        """SQUAD-ACTIVATION (Lever 1, P1): instantiate `size` model-Units that
        all share one freshly-allocated squad_id, so the squad-level activation
        loop (P3) can treat them as a single unit. Two squads of the same
        datasheet receive distinct ids (fixing the profile.name-merge issue).

        PER-MODEL-LOADOUTS (Stage 3-5, now DEFAULT-ON): when the profile carries
        a per-model loadout, each model-Unit is built from its OWN weapons (a Knight
        fires only its equipped guns; a squad's special-weapon model carries its
        special weapon, lost when that model dies). The faithful 10e Weapons model,
        flipped default-ON wave 210 (fidelity-first; the AI scores the SQUAD aggregate
        via strategy._score_profile so it isn't confounded by one model's gun). The
        legacy shared-profile path is retained behind `SWEG_PERMODEL=0` (reversible,
        byte-identical to the pre-Stage-3 baseline). Cited as `simulator.per_model_loadouts`.
        """
        sid = self._next_squad_id
        self._next_squad_id += 1
        if os.environ.get("SWEG_PERMODEL", "1") != "0" and profile.model_loadouts:
            self._add_squad_per_model(profile, size, sid)
        else:
            # Legacy path — byte-identical to the pre-Stage-3 loop (no extra
            # RNG, no profile rebuild), so SWEG_PERMODEL unset reproduces the
            # baseline exactly.
            for _ in range(max(1, int(size))):
                unit = Unit(profile, in_cover=self.in_cover)
                unit.army_ref = self
                unit.squad_id = sid
                self.units.append(unit)
        self._invalidate_alive_cache()

    def _add_squad_per_model(
        self, profile: UnitProfile, size: int, sid: int
    ) -> None:
        """PER-MODEL-LOADOUTS (Stage 3) — instantiate one Unit per model, each
        re-pointed at that model's real weapons.

        The loadout entries carry counts for the MAX squad; map them onto the
        actual `size` model slots via the largest-remainder (Hamilton) method
        (`_distribute_squad_slots`), then for each slot build a per-model
        `UnitProfile` (replace only the weapon fields via
        `_loadout_entry_to_weapon_fields`) and a `Unit`. Each Unit keeps a
        reference to the original aggregate profile (`squad_profile_ref`) so
        unit-level consumers (which read squad-wide stats) still see the
        aggregate; the firing path reads the per-model `Unit.profile`.
        """
        loadouts = _unflatten_model_loadouts(profile.model_loadouts)
        slots = _distribute_squad_slots(loadouts, size)
        for entry in slots:
            weapon_fields = _loadout_entry_to_weapon_fields(entry)
            model_profile = dataclasses.replace(profile, **weapon_fields)
            unit = Unit(model_profile, in_cover=self.in_cover)
            unit.army_ref = self
            unit.squad_id = sid
            # The original aggregate profile — unit-level consumers (squad-wide
            # stats, AI scoring in a later stage) read this rather than the
            # narrowed per-model weapon block.
            unit.squad_profile_ref = profile
            self.units.append(unit)

    def squads(self):
        """SQUAD-ACTIVATION (Lever 1): alive units grouped by squad_id in
        first-seen order. Units with squad_id < 0 (lone / never-assigned, e.g.
        a legacy direct construction) each form their own singleton group so
        they never merge. Returns OrderedDict[key, List[Unit]]. (Not consumed
        until P3; provided here as P1 infrastructure.)
        """
        from collections import OrderedDict
        groups = OrderedDict()
        for u in self.alive_units:
            key = u.squad_id if u.squad_id >= 0 else ("lone", id(u))
            groups.setdefault(key, []).append(u)
        return groups

    def _add_live_unit(self, unit: "Unit") -> None:
        """Attach a pre-existing live Unit to this army (used for deepstrike arrivals).

        Sets army_ref and invalidates the alive cache so the unit is immediately
        visible via alive_units.
        """
        unit.army_ref = self
        self.units.append(unit)
        self._invalidate_alive_cache()

    def _invalidate_alive_cache(self) -> None:
        self._alive_cache = None
        self._squad_count_cache = None

    def resolve_detachment(self) -> Optional[Detachment]:
        """Return the detachment in effect — explicit if set, else faction default."""
        if self.detachment is not None:
            return self.detachment
        if self.units:
            faction = self.units[0].profile.faction
            return default_detachment_for_faction(faction)
        return None

    # ------------------------------------------------------------------
    # Derived state
    # ------------------------------------------------------------------

    @property
    def alive_units(self) -> List[Unit]:
        if self._alive_cache is None:
            self._alive_cache = [u for u in self.units if u.is_alive]
        return self._alive_cache

    def squad_sibling_count(self, unit_name: str) -> int:
        """Return the number of alive units sharing `unit_name`, including self.

        Result is cached alongside `_alive_cache` — rebuilds only when a unit
        dies or arrives, not on every caller invocation. Used by
        `strategy._squad_size_factor` to avoid iterating alive_units repeatedly.
        """
        if self._squad_count_cache is None:
            counts: Dict[str, int] = {}
            for u in self.alive_units:
                name = getattr(u.profile, "name", None)
                if name:
                    counts[name] = counts.get(name, 0) + 1
            self._squad_count_cache = counts
        return self._squad_count_cache.get(unit_name, 0)

    @property
    def unit_count(self) -> int:
        return len(self.alive_units)

    @property
    def warlord_uid(self) -> Optional[int]:
        """LC-5: id() of the army's Warlord (first CHARACTER by deploy order).

        Computed lazily and cached. Picks the first unit in `self.units`
        whose profile carries the CHARACTER keyword. Returns None if no
        CHARACTER is present (synthetic test armies / Combat Patrol).

        Used by `code/secondaries.py` Assassination scoring: when the
        killed CHARACTER set includes the enemy's `warlord_uid`, an
        additional +1 VP is awarded per real Pariah Nexus rule text
        ("Score 3 VP at the end of the battle round if one or more
        enemy CHARACTER models were destroyed this battle round. Score
        4 VP instead if the enemy WARLORD was among those models").

        Caching uses id() not name because multiple CHARACTERs can share
        a profile name across leader-attachment patterns. Cache is
        invalidated by `_invalidate_alive_cache` if the original
        Warlord unit dies — the position is NOT transferred to another
        CHARACTER (real 10e rule: Warlord is set pre-game and stays
        the original model regardless of survival).
        """
        if self._warlord_uid is None:
            for u in self.units:
                keywords = u.profile.unit_keywords or ()
                if "CHARACTER" in keywords:
                    self._warlord_uid = id(u)
                    break
        return self._warlord_uid

    @property
    def total_points(self) -> float:
        return sum(u.profile.points_cost for u in self.units)

    @property
    def total_score(self) -> float:
        """Aggregate Lanchester score across all units (alive + dead, for reference)."""
        return sum(u.profile.score for u in self.units)

    # ------------------------------------------------------------------
    # Tactical helpers
    # ------------------------------------------------------------------

    def pick_target(self, enemy: "Army") -> Optional[Unit]:
        """Focus-fire heuristic: target the enemy unit with lowest current health."""
        alive = enemy.alive_units
        if not alive:
            return None
        return min(alive, key=lambda u: u.current_health)

    def activation_queue(
        self, excluded_ids: set, map_=None,
    ) -> List[Unit]:
        """Return alive units not yet activated, sorted for activation order.

        Default (no `army_plan` set, or `map_` is None): sort by Lanchester
        score descending so the highest-impact unit activates first.

        With an `army_plan` set on this Army (see `pick_army_plan` in the
        simulator), units whose physical position aligns with the plan's
        target flank activate before units that don't, *then* score breaks
        ties within each group. This makes coordinated alpha-strikes
        materialise: every unit in the left-flank push activates before
        right-side units start their turn, so right-side enemies see a fully
        committed left flank in one round rather than a trickle. Internal
        AI heuristic (no GW rule citation — it's an activation-order
        scheduler, not a 10e mechanic).

        Within each (plan_priority, score) group, CHARACTER units that are
        currently leading a friendly squad get a priority bump so they
        resolve BEFORE that squad's activation. Aura buffs applied at
        activation time (+1 to hit, +1 to wound, re-rolls, etc.) need the
        leader's slot to fire first; without this bump 37.4% of leader
        activations land AFTER their led teammate, wasting the buff. The
        rule is faction-neutral: it fires on any CHARACTER with a
        registered `LeaderAbility` whose aura currently covers (army-wide,
        or within `aura_range` of) at least one friendly non-CHARACTER
        unit. Internal AI heuristic — no 10e citation required (the rule
        is an activation-order scheduler, not a game mechanic).

        `map_` is required to compute the flank assignment (left half vs
        right half of the board); when omitted the spatial sort short-
        circuits and the queue collapses to the legacy score-only order
        (still with the leader-before-led priority bump applied).
        """
        available = [u for u in self.alive_units if id(u) not in excluded_ids]

        def _is_leading_unit(u: Unit) -> bool:
            """True iff `u` is a CHARACTER with a registered LeaderAbility
            whose aura currently reaches at least one friendly non-CHARACTER
            alive unit. Pragmatic stand-in for "currently leading a squad"
            in lieu of an explicit led-pair registry on `Army`.
            """
            kw = u.profile.unit_keywords or ()
            if "CHARACTER" not in kw:
                return False
            # Local import to avoid the army <-> leaders circular import at
            # module load time.
            from .leaders import lookup_ability
            ability = lookup_ability(u.profile.name)
            if ability is None:
                return False
            aura = ability.aura_range
            for ally in self.alive_units:
                if ally is u:
                    continue
                if "CHARACTER" in (ally.profile.unit_keywords or ()):
                    continue
                if aura <= 0:
                    return True  # army-wide aura
                dx = ally.position[0] - u.position[0]
                dy = ally.position[1] - u.position[1]
                if (dx * dx + dy * dy) ** 0.5 <= aura:
                    return True
            return False

        plan = self.army_plan
        if plan is None or map_ is None:
            # Score-only path: 0 = leader-bumped, 1 = everyone else; ties
            # break by Lanchester score descending.
            return sorted(
                available,
                key=lambda u: (
                    0 if _is_leading_unit(u) else 1,
                    -u.profile.score,
                ),
            )

        half_x = map_.width / 2.0
        half_y = map_.height / 2.0

        def _plan_priority(u: Unit) -> int:
            """Lower value = earlier in the queue.

            Match (priority 0) = unit aligns with the plan's target zone.
            No-match (priority 1) = unit is elsewhere on the board.
            """
            px, py = u.position
            if plan == "LEFT_FLANK":
                return 0 if px < half_x else 1
            if plan == "RIGHT_FLANK":
                return 0 if px >= half_x else 1
            if plan == "MID_PUSH":
                # Centre-aligned: within a quarter-width band around midline.
                quarter = map_.width / 4.0
                return 0 if abs(px - half_x) <= quarter else 1
            if plan == "HOME_HOLD":
                # Friendly back-half (the half closer to our deployment side).
                # We assume the army that's HOME_HOLD-ing wants units already
                # on its own side to activate first. The Y half is the cleaner
                # proxy because deployment zones split the board along Y in
                # the default map.
                return 0 if py < half_y else 1
            # COUNTER: no per-unit prioritisation here — the strategy biases
            # handle target selection. Fall through to score-only ordering.
            return 0

        return sorted(
            available,
            key=lambda u: (
                _plan_priority(u),
                0 if _is_leading_unit(u) else 1,
                -u.profile.score,
            ),
        )

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Army({self.name!r}, units={len(self.units)}, "
            f"pts={self.total_points:.0f}, cp={self.command_points})"
        )

    def summary(self) -> str:
        lines = [f"  {self.name} [{self.total_points:.0f} pts]"]
        for u in self.units:
            status = "alive" if u.is_alive else f"dead ({u.profile.name})"
            lines.append(f"    {u}")
        return "\n".join(lines)
