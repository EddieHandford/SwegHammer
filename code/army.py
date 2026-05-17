"""Army — a collection of units with command point tracking."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from .detachments import Detachment, default_detachment_for_faction
from .stratagems import STARTING_CP
from .units import Unit, UnitProfile


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

    Returns False when either gate blocks the shot, True otherwise. The check
    is order-insensitive — both gates compose so a Lone Operative CHARACTER
    huddled next to an INFANTRY unit just gets the same 12" cap.
    """
    distance = _xy_distance(attacker.position, target.position)
    tp = target.profile
    target_kw = set(tp.unit_keywords or ())

    # Lone Operative — keyword-gated, hard 12" cap.
    if getattr(tp, "lone_operative", False) and distance > _LOS_RANGE_INCHES:
        return False

    # Look Out Sir — only fires on CHARACTERS that aren't MONSTER/VEHICLE.
    is_los_eligible_character = (
        "CHARACTER" in target_kw
        and "MONSTER" not in target_kw
        and "VEHICLE" not in target_kw
    )
    if is_los_eligible_character and distance > _LOS_RANGE_INCHES:
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
        # 10e Strike Force standard: each side starts with 3 CP. Battle then
        # drips +1/round via stratagems.award_command_phase_cp (capped at 6).
        self.command_points: int = STARTING_CP
        self.in_cover: bool = in_cover
        # Army-wide passive rules. Auto-resolves from the army's primary
        # faction (first unit's faction tag) when not explicitly set.
        self.detachment: Optional[Detachment] = detachment
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
        # Starting points snapshot — captured once at battle start by the
        # simulator so the WAAAGH! AI can compare current points to the
        # initial roster (the trigger fires early if Orks are taking heavy
        # losses). 0 until the simulator sets it.
        self.starting_points: float = 0.0
        # Adeptus Mechanicus army rule — Doctrina Imperatives. At the start
        # of each Command phase, the AdMech player picks ONE of two
        # imperatives, active until the start of their next Command phase:
        #   * "protector": +1 to hit ranged, -1 to hit melee
        #   * "conqueror": +1 to hit melee, -1 to hit ranged
        # Reset to None each round; re-picked by the simulator's AI based on
        # the army's role mix and engagement count. None on a non-AdMech
        # army (the gate is faction-checked at attack-resolution time too).
        # Cited as `simulator.doctrina_imperatives`.
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

    def pop_fate_die_meeting(self, threshold: int) -> Optional[int]:
        """Greedy spend: remove and return the LOWEST die in the pool
        that is >= `threshold` (so we don't waste a 6 to pass a 3+ save
        when a 3 in the pool would do). Returns None if no die qualifies.

        The heuristic intentionally avoids ever spending a die that
        would fail the roll — substitution is only worth doing when it
        flips fail -> success.
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
        unit = Unit(profile, in_cover=self.in_cover)
        unit.army_ref = self
        self.units.append(unit)

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
        return [u for u in self.units if u.is_alive]

    @property
    def unit_count(self) -> int:
        return len(self.alive_units)

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
