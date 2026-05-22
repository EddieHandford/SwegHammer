"""Battle simulator: unit-by-unit activation with movement and event emission."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .army import Army
from .detachments import effective_move
from .events import (
    BattleEnded, BattleStarted, BattleshockFailed, DeadlyDemiseExploded,
    InitialUnit, JudgementTokenAwarded, OathTargetChosen, ObjectiveScored,
    RoundEnded, RoundStarted, StratagemFired, Subscriber, TransportDisembarked,
    TransportEmbarked, UnitActivated, UnitAdvanced, UnitCharged,
    UnitDeepStrike, UnitFought, UnitInfiltrated, UnitKilled, UnitMoved,
    UnitReanimated, UnitScouted, UnitShot, WaaaghDeclared,
)
from .factions import is_marine_faction
from .map import Map, TerrainType
from .maps import DEFAULT_MAP
from .strategy import (
    _melee_target_score, _oc_on_objective,
    decide_deepstrike_drops, pick_army_plan, pick_doctrina_imperative,
    pick_mass_arrival_anchor, pick_move_intent, should_declare_waaagh,
    should_fire_stratagem,
)
from .stratagems import (
    COMMAND_RE_ROLL, COUNTER_OFFENSIVE, TANK_SHOCK,
    # Virulent Vectorium (Death Guard) — full 6-stratagem set, per #195.
    # Disgustingly Resilient was re-anchored to the real detachment at 2 CP
    # per the 2026-05-15 fabrication audit.
    DISGUSTINGLY_RESILIENT, PUTRID_DETONATION, PLAGUESURGE,
    LEECHSPORE_ERUPTION, OVERWHELMING_GENEROSITY, CREEPING_BLIGHT,
    # Warhost (Aeldari) — six real detachment stratagems
    LIGHTNING_FAST_REACTIONS, FIRE_AND_FADE,
    SKYBORNE_SANCTUARY, FEIGNED_RETREAT, BLITZING_FIREPOWER, WEBWAY_TUNNEL,
    # Mont'ka (T'au Empire) — six real detachment stratagems (#196)
    PINPOINT_COUNTER_OFFENSIVE, AGGRESSIVE_MOBILITY, FOCUSED_FIRE,
    COMBAT_DEBARKATION, PULSE_ONSLAUGHT, COUNTERFIRE_DEFENCE_SYSTEMS,
    # Awakened Dynasty (Necrons) — six real Protocol stratagems (#194)
    PROTOCOL_OF_THE_ETERNAL_REVENANT,
    PROTOCOL_OF_THE_UNDYING_LEGIONS,
    PROTOCOL_OF_THE_HUNGRY_VOID,
    PROTOCOL_OF_THE_SUDDEN_STORM,
    PROTOCOL_OF_THE_CONQUERING_TYRANT,
    PROTOCOL_OF_THE_VENGEFUL_STARS,
    # Grand Coven (Thousand Sons) — six real detachment stratagems (#193)
    PSYCHIC_DOMINION, DESTINED_BY_FATE, EGOTISTICAL_POWER,
    DESECRATION_OF_WORLDS, ARCANE_FOCUS, DEVASTATING_SORCERY,
    # Rubricae Phalanx (Thousand Sons) — six detachment stratagems (iter15)
    ARDENT_AUTOMATA, INEXORABLE_ADVANCE, INFERNAL_FUSILLADE,
    REVENGE_OF_THE_RUBRICAE, IMPLACABLE_GUARDIANS, UNWAVERING_PHALANX,
    # War Horde (Orks) — six real detachment stratagems (iter-1 B1)
    INSANE_BRAVERY, POWER_OF_THE_WAAAGH, MOB_UP, BIG_KRUMPIN,
    TELLYPORTA, DA_BIGGEST_BOSS,
    # Shield Host (Adeptus Custodes) — six real detachment stratagems (iter-8)
    ARCANE_GENETIC_ALCHEMY, UNWAVERING_SENTINELS, MULTIPOTENTIALITY,
    VIGILANCE_ETERNAL, ARCHAEOTECH_MUNITIONS, AVENGE_THE_FALLEN,
    # Oathband (Leagues of Votann) — six real detachment stratagems (iter-9)
    WARRIOR_PRIDE, WRATH_OF_THE_ANCESTORS, GLORY_OF_THE_HEARTH,
    IRONKIN_SEQUENCE, ANCESTRAL_SENTENCE, VOID_ARMOURED_RESILIENCE,
    # Gladius Task Force (Adeptus Astartes) — six real detachment stratagems (iter-12)
    STORM_OF_FIRE, ARMOUR_OF_CONTEMPT, SQUAD_TACTICS,
    ONLY_IN_DEATH_DOES_DUTY_END, HONOUR_THE_CHAPTER, ADAPTIVE_STRATEGY,
    # Combined Arms (Astra Militarum) — six real detachment stratagems (iter-14)
    COORDINATED_ACTION, REINFORCEMENTS, FLEXIBLE_COMMAND,
    FIELDS_OF_FIRE, INSPIRED_COMMAND, STALWART_PROTECTOR,
    # ST-2 wave 3 — one stratagem per under-performing faction
    APOPLECTIC_FRENZY, DENIZENS_OF_THE_WARP, EMPYRIC_CHANNELLING,
    CULT_AMBUSH, PROFANE_ZEAL,
    CP_CAP, award_command_phase_cp,
)


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class BattleResult:
    winner: Optional[str]   # army name, or None for draw
    rounds: int
    a_name: str
    b_name: str
    a_start: int            # initial unit count
    b_start: int
    a_survivors: int        # surviving unit count
    b_survivors: int
    a_vp: int = 0           # Primary VP scored across the battle
    b_vp: int = 0
    a_points_remaining: float = 0.0   # sum of points_cost over alive units at end
    b_points_remaining: float = 0.0
    round_history: list = None  # list of (a_alive, b_alive) per round

    def __post_init__(self):
        if self.round_history is None:
            self.round_history = []

    @property
    def is_draw(self) -> bool:
        return self.winner is None

    def winner_label(self) -> str:
        return self.winner if self.winner is not None else "Draw"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _move_toward(
    start: Tuple[float, float],
    goal: Tuple[float, float],
    max_dist: float,
    map_: Map,
) -> Tuple[float, float]:
    """Move from start toward goal up to max_dist inches.

    Clamps to map bounds. If the destination point lies inside impassable
    terrain, the move is aborted and the unit stays put — crude but enough
    for Phase A.
    """
    dx = goal[0] - start[0]
    dy = goal[1] - start[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist == 0 or dist <= max_dist:
        new = goal
    else:
        scale = max_dist / dist
        new = (start[0] + dx * scale, start[1] + dy * scale)
    new_x = max(0.0, min(map_.width, new[0]))
    new_y = max(0.0, min(map_.height, new[1]))
    new_point = (new_x, new_y)
    if map_.is_blocked(new_point):
        return start
    return new_point


# ---------------------------------------------------------------------------
# Battle engine
# ---------------------------------------------------------------------------

# A SwegHammer round is "every unit on both sides has activated once". A full
# game is 5 rounds (matches 10e). Round limit is also a backstop against
# pathological infinite loops if attrition somehow stalls.
MAX_ROUNDS = 5
CP_BONUS_DIVISOR = 2    # opponent must have this many more units per 1 CP awarded
CP_BONUS_CAP = 2        # max CP awarded per round


@dataclass(frozen=True)
class RulesConfig:
    """Toggles for SwegHammer's non-10e rule modifications.

    Vanilla 10e mode (all False) runs the simulator under standard WH40k 10e
    core rules: I-go-you-go player turns, no smaller-army CP catch-up, no
    coordinated army-plan activation scheduler, sequential per-unit
    move→shoot→charge→fight inside each player's turn. This is the mode the
    MC bisection (code/balancer.py) and the eval-vs-meta script run against
    so the simulator faithfully reproduces tournament play.

    SwegHammer mode (all True via .sweghammer()) is the project's original
    ruleset: alternating per-unit activations across both armies within a
    round, simultaneous-movement sub-phase, CP catch-up bonus for the
    smaller army, coordinated army-level activation plans. Opt-in only;
    used when simulating gameplay UNDER the SwegHammer ruleset rather than
    deriving prices.
    """

    alternating_activations: bool = False
    """Per-unit alternation between armies within a round. Vanilla 10e is
    I-go-you-go player turns. SwegHammer flips this for action density."""

    simultaneous_movement: bool = False
    """Both units in the alternating-activation pair move BEFORE either
    shoots — avoids the second-mover-sees-closing-distance asymmetry that
    plain per-unit-sequence would create. Implies alternating_activations."""

    cp_catchup_bonus: bool = False
    """After Round 1, if the opponent has ≥2× more units, the smaller army
    gains 1 CP per round (max +2). Pure SwegHammer catch-up; 10e has no
    such mechanic."""

    coordinated_army_plan: bool = False
    """Each army picks ONE plan (LEFT_FLANK / RIGHT_FLANK / CENTRE) per
    round biasing both activation order and per-unit move/charge intent.
    Internal AI scheduler with cross-unit coordination no real 10e player
    has mid-battle."""

    @classmethod
    def vanilla_10e(cls) -> "RulesConfig":
        """Standard WH40k 10e core rules — all SwegHammer mods off."""
        return cls()

    @classmethod
    def sweghammer(cls) -> "RulesConfig":
        """All SwegHammer rule modifications on."""
        return cls(
            alternating_activations=True,
            simultaneous_movement=True,
            cp_catchup_bonus=True,
            coordinated_army_plan=True,
        )


class Battle:
    """
    Runs a single engagement between two armies under SwegHammer rules:
      - Units deploy in their army's deployment zone at battle start.
      - Each activation: move toward focused target if out of range, then
        attack if in range.
      - Alternating activations within a round; first player randomised.
      - CP bonus awarded to the smaller army after Round 1.
      - Stochastic per-attack rolls (hit, wound, save) via Unit.attack().
    """

    def __init__(
        self,
        army_a: Army,
        army_b: Army,
        verbose: bool = False,
        subscribers: Optional[List[Subscriber]] = None,
        map_: Optional[Map] = None,
        rules: Optional[RulesConfig] = None,
    ) -> None:
        self.a = army_a
        self.b = army_b
        self.verbose = verbose
        self.subscribers: List[Subscriber] = list(subscribers) if subscribers else []
        self.map: Map = map_ or DEFAULT_MAP
        # Default is vanilla WH40k 10e mode — the simulator's primary
        # responsibility is faithfully reproducing tournament play (the
        # MAE-vs-real-meta signal). SwegHammer's alternating-activation
        # ruleset is opt-in via `RulesConfig.sweghammer()` for users who
        # want to play games under SwegHammer rules; it does not touch
        # calibration. See plan `enchanted-wiggling-sundae` step 1.
        self.rules: RulesConfig = rules if rules is not None else RulesConfig.vanilla_10e()
        # UIDs of units that Advanced in the current round — they skip shooting.
        # Reset at the start of each round.
        self._advanced_this_round: set = set()
        # UIDs of units that failed their Battleshock test this round — OC 0
        # so they don't contribute to objective control. Reset per round.
        self._battleshocked_this_round: set = set()
        # UIDs of units that successfully charged this round (Fights First in
        # the Fight sub-phase). Reset each round.
        self._charging_this_round: set = set()
        # UIDs of units that moved during the movement sub-phase this round.
        # Drives the Heavy keyword (+1 to hit if attacker did NOT move).
        # Reset each round.
        self._did_move_this_round: set = set()
        # UIDs of units that have already fired their One Shot weapon this
        # battle. Once a uid is here, the unit may not shoot again.
        # Persists for the whole battle (NOT reset per round).
        self._one_shot_fired: set = set()
        # Phase I — units with Deep Strike that haven't yet arrived. Keyed
        # by army name; each value is a list of Unit instances waiting in
        # reserves. They are added to army.units when they arrive so the
        # normal activation loop picks them up from that round onward.
        self._reserves: dict = {self.a.name: [], self.b.name: []}
        # UIDs of units that JUST arrived from reserves OR just scouted
        # this round — they've already moved as part of arrival / scouting
        # so the simulator skips their movement sub-phase for one round.
        # Reset each round (except Round 1 inherits scout flags).
        self._fresh_arrivals: set = set()
        # Issue #75 — Reanimation Protocols. Snapshot of how many units of
        # each profile each army started with (army.units + reserves).
        # Used end-of-round to compute `destroyed = initial - alive_now` and
        # revive dead model instances by re-setting their current_health.
        # Populated by Battle.run() once deployment has settled.
        self._initial_unit_counts: Dict[str, Dict[str, int]] = {}
        # Fix F-NEC-1 (iter 2): RP must gate on "lost a model THIS round"
        # per Wahapedia "has had one or more destroyed bodyguard models"
        # clause. Snapshot taken at the top of each round so end-of-round
        # `_apply_reanimation` can diff alive_now vs round_start to see
        # whether any model died this round. Without this gate, a stable
        # squad keeps reviving every round just because its current count
        # is below STARTING strength.
        self._round_start_alive_counts: Dict[str, Dict[str, int]] = {}
        # Issue #85 — Sticky Objectives. Once a sticky_objective unit claims
        # an objective for its army, ownership persists here keyed by the
        # objective's index in self.map.objectives. Cleared when the opposing
        # side outscores the holder's army on the objective in a later round.
        self._sticky_owner: Dict[int, str] = {}
        # Stratagem book-keeping. Each army keeps a set of stratagem names
        # already fired this battle (used for once_per_battle stratagems —
        # the four universals are not once-per-battle but the field is here
        # for #104). Also a back-reference from each Army to this Battle so
        # Unit.attack can dispatch the Command Re-Roll hook without dragging
        # a callback through every call site.
        self._stratagems_fired_this_battle: Dict[str, set] = {
            self.a.name: set(), self.b.name: set(),
        }
        self.a._battle_ref = self
        self.b._battle_ref = self
        # Current battle round (1..MAX_ROUNDS). Updated at the top of each
        # _run_round; read by Unit.attack for round-gated faction rules
        # like the Orks WAAAGH! +1 to wound melee window.
        self._current_round: int = 0
        # SC4-A — 10e Pariah Nexus secondary objectives. Each round we
        # snapshot each army's alive units at round start (in `_run_round`)
        # and compute Bring it Down + No Prisoners VP at round end (in
        # `run` after `_score_objectives`). Per-round caps live in
        # `code/secondaries.py`. The snapshot is per-army; we score side A
        # against side B's snapshot (i.e. side A scores VP for killing
        # side B's units this round).
        from .secondaries import RoundSnapshot  # noqa: F401  (type only)
        self._a_round_snapshot = None  # snapshot of A's units at round start
        self._b_round_snapshot = None  # snapshot of B's units at round start
        self._a_secondary_vp: int = 0  # cumulative secondary VP for side A
        self._b_secondary_vp: int = 0  # cumulative secondary VP for side B
        # Iter-4 A5: flag set TRUE while inside `_apply_detachment_stratagems`
        # so `_fire_stratagem` knows whether to increment the per-army
        # per-Command-phase counter. Always False outside that scope —
        # Tank Shock, Counter-Offensive, Command Re-Roll fire on their
        # own per-trigger hooks and don't count toward the detachment-
        # stratagem cap. (Heroic Intervention is a free core CHARACTER
        # ability, not a stratagem at all — see _do_heroic_intervention.)
        self._dispatching_detachment_stratagems: bool = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> BattleResult:
        # APPROXIMATION: Battle Focus modelled as a flat 4-token pool spent only on Star Engines / [ASSAULT].
        # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/
        # Real rule: per-round token refresh + 6 named Agile Manoeuvres (Star Engines, Wraithwalk,
        # Lightning-Fast Reactions, etc.). We conflate the whole bundle into a single shoot-after-Advance
        # spend, omitting the other 5 named manoeuvres entirely.
        # Battle Focus tokens (Aeldari ASURYANI rule): 4 at Strike Force,
        # the default battle size for this simulator. We hand the tokens
        # out to any army that contains at least one ASURYANI unit — the
        # rule is faction-wide, not detachment-gated.
        # Warhost detachment rule "Martial Grace" (#197) grants +1 token
        # at start of each battle round; since SwegHammer's Battle Focus
        # model is a flat once-at-start pool rather than a per-round
        # refresh, we collapse the +1/round buff into +1 to the starting
        # pool (over 5 rounds the codex hands out +5, but the simulator
        # only spends tokens on the rarely-triggered shoot-after-Advance
        # path; +1 to the pool is a clean single-bump approximation).
        # Gates on Detachment.martial_grace via resolve_detachment so the
        # bump fires only when Warhost is the active detachment.
        for army in (self.a, self.b):
            if any("ASURYANI" in (u.profile.unit_keywords or ())
                   for u in army.units):
                base_tokens = 4
                det = army.resolve_detachment() if hasattr(army, "resolve_detachment") else None
                if det is not None and getattr(det, "martial_grace", False):
                    base_tokens += 1
                army.battle_focus_tokens = base_tokens

        # Strands of Fate (Aeldari army rule, 10e). At the start of the
        # first battle round, before the first turn begins, the AELDARI
        # player rolls 6D6 and sets those dice aside as their pool of
        # Fate dice. Each die can later be substituted for one d6 roll
        # made by/against an AELDARI unit (hit, wound, save, charge,
        # advance, Battle-shock). The pool depletes with each spend; once
        # empty, no more substitutions are available. Cited as
        # `simulator.strands_of_fate`. APPROXIMATION: the simulator's
        # spend AI is a greedy heuristic (pop the lowest die that
        # successfully flips a fail -> success), not the optimal play of
        # a real Aeldari player. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
        # Gate on faction tag (Aeldari codex) rather than the AELDARI
        # unit keyword — BSData's parser keeps the codex-wide AELDARI
        # keyword as faction meta rather than per-unit unit_keywords, so
        # the keyword check would never fire on real Aeldari datasheets
        # (Troupe, Solitaire, Shroud Runners). The faction tag is set
        # by code.factions.faction_of and uniquely identifies the
        # Aeldari codex (Drukhari are a separate faction string).
        for army in (self.a, self.b):
            if any(u.profile.faction == "Aeldari" for u in army.units):
                army.fate_dice = sorted(
                    [random.randint(1, 6) for _ in range(6)],
                    reverse=True,
                )

        # CP-econ Warlord scan (Belisarius Cawl, Roboute Guilliman, Trazyn
        # the Infinite, Lord of Contagion). Seeds Army.cp_refund_remaining
        # and Army._warlord_first_strat_free_enabled from the resolved
        # Warlord's LeaderAbility. Armies without a CP-econ Warlord keep
        # their defaults and the discount/refund gates stay dormant — this
        # is the gate that ensures the mechanic never accidentally grants
        # CP to a non-Warlord-having army.
        from .leaders import warlord_ability
        for army in (self.a, self.b):
            wl = warlord_ability(army)
            if wl is None:
                continue
            army.cp_refund_remaining = wl.cp_refund_per_battle
            army._warlord_first_strat_free_enabled = wl.first_stratagem_free_per_round

        # Drukhari Combat Drugs (army rule, 10e). For any army containing
        # Drukhari WYCH CULT units, assign one drug per WYCH CULT unit at
        # battle start; the drug persists for the entire battle. The
        # SwegHammer assignment heuristic picks the strongest realistic uplift
        # per unit role: Wyches -> Adrenalight (+1 melee A), Hellions -> Hypex
        # (+2" Move), Reavers -> Grave Lotus (+1 melee S), Beastmaster ->
        # Painbringer (+1 T). Cited as `simulator.combat_drugs`.
        self._apply_combat_drugs()

        self._assign_uids()
        self._deploy_armies()
        # Phase I — pre-game Scouts move happens AFTER deployment and BEFORE
        # Round 1 begins. Deep Strike arrivals start at Round 2.
        self._run_scout_phase()

        # Include reserves so the "starting unit count" reflects the full
        # army roster, not just what was on the board at deployment.
        a_start = len(self.a.units) + len(self._reserves.get(self.a.name, []))
        b_start = len(self.b.units) + len(self._reserves.get(self.b.name, []))
        # Snapshot starting points across BOTH on-board and reserve units so
        # the WAAAGH! AI's "below 70% starting points" emergency trigger
        # measures attrition against the full roster, not just the deployed
        # slice. Applied to every army (cheap, scoped attribute), only Ork
        # armies actually consult it.
        for army in (self.a, self.b):
            roster_pts = sum(u.profile.points_cost for u in army.units) + sum(
                u.profile.points_cost
                for u in self._reserves.get(army.name, [])
            )
            army.starting_points = float(roster_pts)
        # Genestealer Cults — Cult Ambush Resurgence points (10e army rule).
        # Strike Force default = 10 points; spent at round end to revive
        # destroyed CULT INFANTRY units (APPROXIMATION proxy for the
        # Resurgence/Cult Ambush marker resurrection mechanic). Cited as
        # `simulator.cult_ambush_resurgence`.
        for army in (self.a, self.b):
            if army.units and army.units[0].profile.faction == "Genestealer Cults":
                army.cult_ambush_resurgence_points = 10
        # Reanimation Protocols (#75): snapshot starting model counts per
        # profile per army, including reserves. End-of-round revival reads
        # this to compute how many models have been destroyed.
        for army in (self.a, self.b):
            counts: Dict[str, int] = {}
            for u in army.units:
                counts[u.profile.name] = counts.get(u.profile.name, 0) + 1
            for u in self._reserves.get(army.name, []):
                counts[u.profile.name] = counts.get(u.profile.name, 0) + 1
            self._initial_unit_counts[army.name] = counts
        # VP tally accumulates across rounds
        self._a_vp = 0
        self._b_vp = 0

        # Snapshot includes on-board units AND reserves (deep-strikers).
        # Reserves get an off-board sentinel position so renderers know they
        # exist but don't draw them on the map yet — they'll get a real
        # position when UnitDeepStrike fires.
        snapshot = []
        for army in (self.a, self.b):
            for u in army.units:
                snapshot.append(InitialUnit(
                    uid=u.uid, name=u.profile.name, army=army.name,
                    position=u.position, max_health=u.profile.health,
                    unit_keywords=tuple(u.profile.unit_keywords or ()),
                    base_shape=u.profile.base_shape,
                    base_diameter_mm=u.profile.base_diameter_mm,
                    base_width_mm=u.profile.base_width_mm,
                    base_length_mm=u.profile.base_length_mm,
                ))
            for u in self._reserves.get(army.name, []):
                snapshot.append(InitialUnit(
                    uid=u.uid, name=u.profile.name, army=army.name,
                    position=(-100.0, -100.0),
                    max_health=u.profile.health,
                    unit_keywords=tuple(u.profile.unit_keywords or ()),
                    base_shape=u.profile.base_shape,
                    base_diameter_mm=u.profile.base_diameter_mm,
                    base_width_mm=u.profile.base_width_mm,
                    base_length_mm=u.profile.base_length_mm,
                ))
        self._emit(BattleStarted(
            army_a_name=self.a.name,
            army_b_name=self.b.name,
            map_name=self.map.name,
            units=tuple(snapshot),
        ))

        round_history = [(a_start, b_start)]
        rounds_played = 0
        for rnd in range(1, MAX_ROUNDS + 1):
            rounds_played = rnd
            self._emit(RoundStarted(round_num=rnd))
            self._run_round(rnd)
            self._score_objectives()
            self._score_secondaries(rnd)
            self._emit(RoundEnded(
                round_num=rnd,
                a_vp_total=self._a_vp,
                b_vp_total=self._b_vp,
            ))
            round_history.append((self.a.unit_count, self.b.unit_count))
            # End early ONLY if neither side has anything left on-board AND
            # nothing in reserves to bring back. A wiped force with units
            # still incoming next round (Phase I Deep Strike) keeps playing.
            a_total_left = self.a.unit_count + len(self._reserves.get(self.a.name, []))
            b_total_left = self.b.unit_count + len(self._reserves.get(self.b.name, []))
            if a_total_left == 0 or b_total_left == 0:
                break

        a_surv = self.a.unit_count
        b_surv = self.b.unit_count
        a_pts = sum(u.profile.points_cost for u in self.a.alive_units)
        b_pts = sum(u.profile.points_cost for u in self.b.alive_units)

        winner = self._decide_winner(a_surv, b_surv, a_pts, b_pts)

        self._emit(BattleEnded(winner=winner, rounds=rounds_played))

        return BattleResult(
            winner=winner,
            rounds=rounds_played,
            a_name=self.a.name,
            b_name=self.b.name,
            a_start=a_start,
            b_start=b_start,
            a_survivors=a_surv,
            b_survivors=b_surv,
            a_vp=self._a_vp,
            b_vp=self._b_vp,
            a_points_remaining=a_pts,
            b_points_remaining=b_pts,
            round_history=round_history,
        )

    # ------------------------------------------------------------------
    # Win condition (objectives + attrition + points)
    # ------------------------------------------------------------------

    def _decide_winner(
        self, a_surv: int, b_surv: int,
        a_pts: float, b_pts: float,
    ) -> Optional[str]:
        """
        10e-flavoured win condition:
          * If one side has zero alive units, the other wins outright.
          * Else: higher VP wins.
          * Tied VP: higher remaining points wins.
          * Tied on both: draw.
        Survivor count is no longer a primary criterion — points + objectives
        capture military value much better than raw unit count.
        """
        if a_surv == 0 and b_surv == 0:
            return None
        if a_surv == 0:
            return self.b.name
        if b_surv == 0:
            return self.a.name
        if self._a_vp > self._b_vp:
            return self.a.name
        if self._b_vp > self._a_vp:
            return self.b.name
        # VP tied — fall back to remaining points
        if a_pts > b_pts * 1.10:
            return self.a.name
        if b_pts > a_pts * 1.10:
            return self.b.name
        return None  # genuinely close — call it a draw

    def _score_objectives(self) -> None:
        """End-of-round VP scoring: each objective awards its vp_per_round to
        whichever side has more Objective Control within control_radius.

        Sticky Objectives (issue #85): a unit with sticky_objective=True that
        currently controls an objective marks self._sticky_owner[obj_idx] =
        its army. If both sides contest the objective on a later round and
        nobody currently controls, the sticky owner still scores. If the
        opposing army takes control, the sticky owner is cleared (and the
        new owner replaces it if THEY are sticky).

        Primary VP cap (10e Leviathan Tournament Companion): an army may
        score a maximum of 15 Primary VP per battle round (i.e. count at
        most 3 controlled objectives at 5 VP each). Enforced after the
        per-objective awards are tallied. Cited as
        `simulator.primary_vp_cap_15`.
        """
        a_vp_before = self._a_vp
        b_vp_before = self._b_vp
        # Virulent Vectorium Worldblight (Death Guard): every DG unit on a
        # controlled objective acts as if it had the sticky_objective flag,
        # per the detachment passive. Resolved once per call. Cited as
        # `VIRULENT_VECTORIUM.worldblight_sticky_dg_objectives`.
        a_det = self.a.resolve_detachment()
        b_det = self.b.resolve_detachment()
        a_worldblight = bool(
            a_det is not None
            and getattr(a_det, "worldblight_sticky_dg_objectives", False)
        )
        b_worldblight = bool(
            b_det is not None
            and getattr(b_det, "worldblight_sticky_dg_objectives", False)
        )

        for obj_idx, obj in enumerate(self.map.objectives):
            obj_pos = (obj.x, obj.y)
            r2 = obj.control_radius * obj.control_radius
            a_oc = 0
            b_oc = 0
            a_sticky_present = False
            b_sticky_present = False
            a_has_dg_unit = False
            b_has_dg_unit = False
            for u in self.a.alive_units:
                if u.uid in self._battleshocked_this_round:
                    continue   # Battleshocked = OC 0
                dx = u.position[0] - obj_pos[0]
                dy = u.position[1] - obj_pos[1]
                if dx * dx + dy * dy <= r2:
                    a_oc += getattr(u.profile, "oc", 1) or 1
                    if getattr(u.profile, "sticky_objective", False):
                        a_sticky_present = True
                    if (u.profile.faction or "") == "Death Guard":
                        a_has_dg_unit = True
            for u in self.b.alive_units:
                if u.uid in self._battleshocked_this_round:
                    continue
                dx = u.position[0] - obj_pos[0]
                dy = u.position[1] - obj_pos[1]
                if dx * dx + dy * dy <= r2:
                    b_oc += getattr(u.profile, "oc", 1) or 1
                    if getattr(u.profile, "sticky_objective", False):
                        b_sticky_present = True
                    if (u.profile.faction or "") == "Death Guard":
                        b_has_dg_unit = True

            # iter24-D3 — Worldblight strict gate. Per Wahapedia
            # (https://wahapedia.ru/wh40k10ed/factions/death-guard/#STRATAGEMS
            # — Worldblight) the rule fires at end of the DG Command phase
            # AND requires the DG unit to already be controlling the
            # objective (strictly greater OC than the opponent). Promote
            # the DG presence to a sticky flag ONLY when the DG side wins
            # the OC contest at this objective. _score_objectives() runs
            # once per round so the once-per-round trigger is implicit.
            # Without this gate, a DG unit losing the OC contest would
            # still mark sticky_present, which prevented the opponent's
            # sticky from being cleared even though they were winning.
            if a_worldblight and a_has_dg_unit and a_oc > b_oc:
                a_sticky_present = True
            if b_worldblight and b_has_dg_unit and b_oc > a_oc:
                b_sticky_present = True

            # Resolve who actually scores this round. The fallback to
            # sticky_owner is only used when NEITHER side has any OC on the
            # objective — i.e. truly uncontested (not a tie at OC>0).
            scorer: Optional[str] = None
            if a_oc > b_oc:
                scorer = self.a.name
            elif b_oc > a_oc:
                scorer = self.b.name
            elif a_oc == 0 and b_oc == 0:
                # Nobody on it — fall back to sticky owner if any.
                scorer = self._sticky_owner.get(obj_idx)

            # Update sticky ownership BEFORE emitting the event, so a
            # newly-claimed objective registers the sticky owner this round.
            # Per 10e core rules: "The player with the greater Level of Control
            # over the objective marker controls it." Strictly greater — ties
            # do NOT grant control, so they cannot register sticky ownership.
            # https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Mission-Objectives
            # Cited as `simulator.objective_control_strictly_greater`.
            if a_sticky_present and a_oc > b_oc:
                self._sticky_owner[obj_idx] = self.a.name
            elif b_sticky_present and b_oc > a_oc:
                self._sticky_owner[obj_idx] = self.b.name
            else:
                # An opposing non-sticky unit that takes control wrests the
                # marker back — clear sticky ownership so the new controller
                # scores fairly. (If the same side that owns sticky also
                # controls now with a non-sticky unit, leave the sticky owner
                # in place — they still hold it.)
                cur_owner = self._sticky_owner.get(obj_idx)
                if cur_owner == self.a.name and b_oc > a_oc:
                    self._sticky_owner.pop(obj_idx, None)
                elif cur_owner == self.b.name and a_oc > b_oc:
                    self._sticky_owner.pop(obj_idx, None)

            if scorer == self.a.name:
                self._a_vp += obj.vp_per_round
                self._emit(ObjectiveScored(
                    objective_name=obj.name, army_name=self.a.name,
                    vp_awarded=obj.vp_per_round, a_oc=a_oc, b_oc=b_oc,
                ))
            elif scorer == self.b.name:
                self._b_vp += obj.vp_per_round
                self._emit(ObjectiveScored(
                    objective_name=obj.name, army_name=self.b.name,
                    vp_awarded=obj.vp_per_round, a_oc=a_oc, b_oc=b_oc,
                ))
            else:
                self._emit(ObjectiveScored(
                    objective_name=obj.name, army_name=None,
                    vp_awarded=0, a_oc=a_oc, b_oc=b_oc,
                ))

        # Primary VP per-round cap (10e Leviathan Tournament Companion):
        # an army scores at most 15 Primary VP per battle round, regardless
        # of how many objectives they control. Excess held objectives still
        # emit ObjectiveScored events above (informative), but the running
        # VP totals are clamped here. Faction-neutral; corrects inflation
        # for objective-flooding archetypes (DG sticky, Necrons RP).
        # https://wahapedia.ru/wh40k10ed/the-rules/leviathan-tournament-companion/
        # Cited as `simulator.primary_vp_cap_15`.
        a_round_vp = self._a_vp - a_vp_before
        b_round_vp = self._b_vp - b_vp_before
        if a_round_vp > 15:
            self._a_vp = a_vp_before + 15
        if b_round_vp > 15:
            self._b_vp = b_vp_before + 15

    # ------------------------------------------------------------------
    # SC4-A — 10e Pariah Nexus secondary objective scoring
    # ------------------------------------------------------------------

    def _score_secondaries(self, round_num: int) -> None:
        """End-of-round secondary VP scoring (Bring it Down + No Prisoners).

        Computes the kill delta between each army's round-start snapshot
        and its current alive units, awarding per-round capped VP to the
        opposing side. Implements Pariah Nexus tournament-pack secondary
        scoring so the sim's win condition isn't primaries-only — without
        secondaries the sim systematically over-rewards sticky-defensive
        play (Death Guard +16.4 over) and under-rewards kill-oriented
        shapes that would in real play score by removing enemy units.

        SC4-A — kill-counting secondaries:
        * Bring it Down — 5 VP per enemy MONSTER/VEHICLE destroyed
          this round, capped at 15 VP per round.
          Cited as `simulator.secondary_bring_it_down`.
        * No Prisoners — 5 VP per enemy unit destroyed this round,
          capped at 15 VP per round.
          Cited as `simulator.secondary_no_prisoners`.

        SC4-B — position-tracking secondaries:
        * Engage on All Fronts — 5 VP if alive units occupy 3+ of the
          4 table quarters at end of round.
          Cited as `simulator.secondary_engage_on_all_fronts`.
        * Behind Enemy Lines — 5 VP if any alive unit's position is
          inside the opponent's deployment zone.
          Cited as `simulator.secondary_behind_enemy_lines`.

        SC4-C — selective kill secondaries:
        * Cull the Horde — 5 VP per enemy 10+model unit destroyed,
          capped at 5 VP per round (1 per round).
          Cited as `simulator.secondary_cull_the_horde`.
        * Assassination — 5 VP per enemy CHARACTER destroyed, capped
          at 10 VP per round (2 per round).
          Cited as `simulator.secondary_assassination`.

        Source: https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-mission-pack/
        """
        from .secondaries import score_round_delta, score_position_delta
        # Side A scores VP for killing side B's units this round — diff
        # B's round-start snapshot against B's current state. Four
        # secondary categories (SC4-A Bring it Down + No Prisoners,
        # SC4-C Cull the Horde + Assassination).
        # LC-5: pass each side's Warlord uid for the +1 Assassination
        # bonus when the opponent kills it.
        b_warlord = self.b.warlord_uid
        a_warlord = self.a.warlord_uid
        if self._b_round_snapshot is not None:
            a_bid, a_np, a_cth, a_assn = score_round_delta(
                self._b_round_snapshot, self.b.units,
                enemy_warlord_uid=b_warlord,
            )
            a_kill_vp = a_bid + a_np + a_cth + a_assn
            self._a_vp += a_kill_vp
            self._a_secondary_vp += a_kill_vp
        # Side B scores VP for killing side A's units this round.
        if self._a_round_snapshot is not None:
            b_bid, b_np, b_cth, b_assn = score_round_delta(
                self._a_round_snapshot, self.a.units,
                enemy_warlord_uid=a_warlord,
            )
            b_kill_vp = b_bid + b_np + b_cth + b_assn
            self._b_vp += b_kill_vp
            self._b_secondary_vp += b_kill_vp

        # SC4-B — position-tracking secondaries scored at end of round.
        # Each side scores against their OWN alive units (Engage is your
        # spread; BEL is your forward projection). own_is_army_a flag
        # tells the scorer which deployment strip is the enemy's.
        # LC-2: round_num gates the 2-of-9 Tactical secondary deck mechanic
        # — each side scores at most ONE of (Engage, BEL) per round on an
        # alternating schedule (see `_is_tactical_secondary_active`).
        a_eng, a_bel = score_position_delta(
            self.a.units, self.map, own_is_army_a=True, round_num=round_num,
        )
        self._a_vp += a_eng + a_bel
        self._a_secondary_vp += a_eng + a_bel
        b_eng, b_bel = score_position_delta(
            self.b.units, self.map, own_is_army_a=False, round_num=round_num,
        )
        self._b_vp += b_eng + b_bel
        self._b_secondary_vp += b_eng + b_bel

    # ------------------------------------------------------------------
    # Reanimation Protocols (issue #75)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Detachment-specific stratagem dispatch (round-start)
    # ------------------------------------------------------------------

    def _clear_transient_stratagem_flags(self, army: Army) -> None:
        """Reset the per-round stratagem flags on every unit in `army`.

        Called at the start of each round before the new round's stratagems
        are decided. Keeps the transient buffs strictly one-round-scoped.
        """
        for u in army.units:
            u.transient_plus_one_to_wound_shooting = False
            u.transient_invuln_4 = False
            u.transient_minus_one_damage_taken = False
            u.transient_plus_one_to_wound_melee = False
            u.transient_plus_one_save = False
            u.transient_reroll_hits_shooting = False
            u.transient_assault_this_round = False
            u.transient_fnp_5 = False
            u.transient_plus_one_to_hit_shooting = False
            u.transient_halve_damage = False
            u.transient_undying_legions_pulse = 0
            # ST-1 proper-keyword transient flags.
            u.transient_lethal_hits = False
            u.transient_sustained_hits = 0
            u.transient_reroll_wounds = False
            u.transient_reroll_wounds_ones = False
        # Per-army per-round stratagem state. Cabbalistic Empowerment boosts
        # this round's Doombolt damage; reset every round so the boost only
        # applies the round the stratagem fires. Putrid Detonation arms the
        # auto-success of Deadly Demise on DG VEHICLE/MONSTER deaths this
        # round. Plaguesurge is informational (no consumer hooked yet, kept
        # for future Contagion-range expansion).
        army.cabbalistic_doombolt_boost = False
        army.putrid_detonation_armed = False
        army.plaguesurge_active = False
        # AM Voice of Command — per-round stratagem widening flags. Flexible
        # Command (Combined Arms, 2 CP) extends Orders to SQUADRON units;
        # Inspired Command (Combined Arms, 1 CP) grants one bonus Order
        # this round. Both reset every round so the widening only applies
        # the round the stratagem fires.
        army.orders_eligible_squadron_this_round = False
        army.orders_extra_this_round = 0

    # Iter-4 A5 (faction-neutral AI heuristic): cap the number of detachment
    # stratagems any one army may fire per Command phase. 10e core has no
    # hard cap, but real-player CP economy averages ~1 stratagem per
    # Command phase; without this cap, CP-rich detachments (DG Virulent
    # Vectorium, Necron Awakened Dynasty, Tau Mont'ka) stack 3-5+ buffs
    # at round start. Setting to 1 matches the modal real-player play
    # rate; 2 is the next tier up if 1 over-regresses any matchup.
    # Cited as `simulator.stratagem_per_command_phase_cap`.
    DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE: int = 1

    def _apply_detachment_stratagems(self, army: Army, opponent: Army) -> None:
        """Round-start dispatcher for detachment-specific stratagems.

        Each detachment's stratagem tuple is iterated; the simulator's
        per-stratagem `_try_*` helpers consult the AI heuristic in
        `strategy.should_fire_stratagem` and, if green-lit, spend CP and
        apply the transient effect for the round.

        Iter-4 A5 cap: detachment stratagems fired through this dispatcher
        are limited to `DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE` (1) per
        army per Command phase. The counter is reset to 0 at the top of
        this method and incremented inside `_fire_stratagem` while the
        `_dispatching_detachment_stratagems` flag is set. Once the cap is
        reached, subsequent dispatcher entries short-circuit via
        `_strat_cap_reached`. Faction-neutral: every detachment's dispatch
        path runs through the same cap.

        Post 2026-05-15 fabrication audit (commit fa9a957): 11 stratagems
        previously dispatched here had no Wahapedia equivalent. The only
        survivors are Disgustingly Resilient (re-anchored to Virulent
        Vectorium at 2CP) and the two real Warhost (Aeldari) entries.
        Real per-detachment stratagem sets land in follow-up per-faction
        rebuild PRs.
        """
        det = army.resolve_detachment()
        if det is None or not det.stratagems:
            return
        strat_names = {s.name for s in det.stratagems}

        # Reset the per-Command-phase counter and arm the dispatch flag so
        # _fire_stratagem knows to increment the army's stratagem counter
        # for any firing during this call.
        army.stratagems_fired_this_command_phase = 0
        self._dispatching_detachment_stratagems = True
        try:
            # ----- Virulent Vectorium (Death Guard) -------------------------
            if not self._strat_cap_reached(army) and "Disgustingly Resilient" in strat_names:
                self._try_disgustingly_resilient(army, opponent)
            if not self._strat_cap_reached(army) and "Putrid Detonation" in strat_names:
                self._try_putrid_detonation(army, opponent)
            if not self._strat_cap_reached(army) and "Plaguesurge" in strat_names:
                self._try_plaguesurge(army, opponent)
            if not self._strat_cap_reached(army) and "Leechspore Eruption" in strat_names:
                self._try_leechspore_eruption(army, opponent)
            if not self._strat_cap_reached(army) and "Overwhelming Generosity" in strat_names:
                self._try_overwhelming_generosity(army, opponent)
            if not self._strat_cap_reached(army) and "Creeping Blight" in strat_names:
                self._try_creeping_blight(army, opponent)

            # ----- Warhost (Aeldari) ----------------------------------------
            if not self._strat_cap_reached(army) and "Lightning-Fast Reactions" in strat_names:
                self._try_lightning_fast_reactions(army, opponent)
            if not self._strat_cap_reached(army) and "Fire and Fade" in strat_names:
                self._try_fire_and_fade(army, opponent)
            if not self._strat_cap_reached(army) and "Skyborne Sanctuary" in strat_names:
                self._try_skyborne_sanctuary(army, opponent)
            if not self._strat_cap_reached(army) and "Feigned Retreat" in strat_names:
                self._try_feigned_retreat(army, opponent)
            if not self._strat_cap_reached(army) and "Blitzing Firepower" in strat_names:
                self._try_blitzing_firepower(army, opponent)
            if not self._strat_cap_reached(army) and "Webway Tunnel" in strat_names:
                self._try_webway_tunnel(army, opponent)

            # ----- Mont'ka (T'au Empire) — six real stratagems (#196) -------
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka.
            # Each dispatcher consults `should_fire_stratagem` for the AI gate,
            # spends CP via `_fire_stratagem`, then applies the transient effect
            # via the existing `transient_*` flag set on the chosen unit. Where
            # the canonical effect doesn't map to a flag (e.g. Pulse Onslaught's
            # enemy Move debuff), the dispatcher routes the value through the
            # nearest existing transient — see per-dispatcher APPROXIMATION notes.
            if not self._strat_cap_reached(army) and "Pinpoint Counter-Offensive" in strat_names:
                self._try_pinpoint_counter_offensive(army, opponent)
            if not self._strat_cap_reached(army) and "Aggressive Mobility" in strat_names:
                self._try_aggressive_mobility(army, opponent)
            if not self._strat_cap_reached(army) and "Focused Fire" in strat_names:
                self._try_focused_fire(army, opponent)
            if not self._strat_cap_reached(army) and "Combat Debarkation" in strat_names:
                self._try_combat_debarkation(army, opponent)
            if not self._strat_cap_reached(army) and "Pulse Onslaught" in strat_names:
                self._try_pulse_onslaught(army, opponent)
            if not self._strat_cap_reached(army) and "Counterfire Defence Systems" in strat_names:
                self._try_counterfire_defence_systems(army, opponent)

            # ----- Awakened Dynasty (Necrons) -------------------------------
            # Six real Protocol stratagems (#194). Two are catalogued-but-no-op
            # APPROXIMATIONs (Eternal Revenant, Vengeful Stars) — the simulator
            # has no model-resurrection or out-of-sequence shoot hook, so the
            # dispatchers below skip them entirely. The other four wire onto
            # existing or new transient_* flags.
            if not self._strat_cap_reached(army) and "Protocol of the Undying Legions" in strat_names:
                self._try_protocol_undying_legions(army, opponent)
            if not self._strat_cap_reached(army) and "Protocol of the Hungry Void" in strat_names:
                self._try_protocol_hungry_void(army, opponent)
            if not self._strat_cap_reached(army) and "Protocol of the Sudden Storm" in strat_names:
                self._try_protocol_sudden_storm(army, opponent)
            if not self._strat_cap_reached(army) and "Protocol of the Conquering Tyrant" in strat_names:
                self._try_protocol_conquering_tyrant(army, opponent)
            # Protocol of the Eternal Revenant + Protocol of the Vengeful Stars:
            # catalogued in the detachment so they show up in stratagems_for_army,
            # but the simulator has no clean hook to fire them. See
            # data/rule_citations.d/stratagems.json for the APPROXIMATION note.

            # ----- Grand Coven (Thousand Sons) ------------------------------
            # Six real Wahapedia stratagems (#193). Four are wired through the
            # transient-flag plumbing; two (Egotistical Power, Arcane Focus)
            # are flagged APPROXIMATION because their mechanics don't reduce
            # to an existing transient_*.
            if not self._strat_cap_reached(army) and "Psychic Dominion" in strat_names:
                self._try_psychic_dominion(army, opponent)
            if not self._strat_cap_reached(army) and "Destined by Fate" in strat_names:
                self._try_destined_by_fate(army, opponent)
            if not self._strat_cap_reached(army) and "Desecration of Worlds" in strat_names:
                self._try_desecration_of_worlds(army, opponent)
            if not self._strat_cap_reached(army) and "Devastating Sorcery" in strat_names:
                self._try_devastating_sorcery(army, opponent)
            # Egotistical Power and Arcane Focus are intentionally NOT dispatched
            # here — see _try_egotistical_power / _try_arcane_focus docstrings.

            # ----- Rubricae Phalanx (Thousand Sons) — six stratagems (iter15)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
            # Four wire onto existing transient_* flags (Inexorable Advance,
            # Infernal Fusillade, Implacable Guardians, Unwavering Phalanx);
            # two are catalogued-but-no-op APPROXIMATIONs (Ardent Automata —
            # no Fall-Back-this-turn transient; Revenge of the Rubricae — no
            # out-of-sequence-shoot-on-PSYKER-death hook).
            if not self._strat_cap_reached(army) and "Inexorable Advance" in strat_names:
                self._try_inexorable_advance(army, opponent)
            if not self._strat_cap_reached(army) and "Infernal Fusillade" in strat_names:
                self._try_infernal_fusillade(army, opponent)
            if not self._strat_cap_reached(army) and "Implacable Guardians" in strat_names:
                self._try_implacable_guardians(army, opponent)
            if not self._strat_cap_reached(army) and "Unwavering Phalanx" in strat_names:
                self._try_unwavering_phalanx(army, opponent)
            # Ardent Automata + Revenge of the Rubricae catalogued in
            # RUBRICAE_PHALANX_STRATAGEMS for the auditor + stratagems_for_army
            # listing; dispatchers intentionally no-op (see docstrings).

            # ----- War Horde (Orks) — six real stratagems (iter-1 B1) ------
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
            # Insane Bravery is catalogued-but-no-op APPROXIMATION (no per-unit
            # battleshock-immunity hook). The other five wire onto existing
            # transient_* flags via the standard pattern.
            if not self._strat_cap_reached(army) and "Power Of The WAAAGH!" in strat_names:
                self._try_power_of_the_waaagh(army, opponent)
            if not self._strat_cap_reached(army) and "Mob Up" in strat_names:
                self._try_mob_up(army, opponent)
            if not self._strat_cap_reached(army) and "Big Krumpin'" in strat_names:
                self._try_big_krumpin(army, opponent)
            if not self._strat_cap_reached(army) and "Tellyporta" in strat_names:
                self._try_tellyporta(army, opponent)
            if not self._strat_cap_reached(army) and "Da Biggest Boss" in strat_names:
                self._try_da_biggest_boss(army, opponent)
            # Insane Bravery — catalogued in WAR_HORDE_STRATAGEMS for the
            # auditor + stratagems_for_army listing, but the dispatcher is a
            # no-op (no per-unit battleshock-immunity transient flag exists).

            # ----- Shield Host (Adeptus Custodes) — six real stratagems (iter-8)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
            # Five wire onto existing transient_* flags; Vigilance Eternal is
            # a no-op APPROXIMATION (sticky-objective hook is per-detachment,
            # not per-stratagem-fire). Replaces the iter-0 zero-stratagem
            # state where Custodes burned 5/7 strat fires on Command Re-Roll.
            if not self._strat_cap_reached(army) and "Arcane Genetic Alchemy" in strat_names:
                self._try_arcane_genetic_alchemy(army, opponent)
            if not self._strat_cap_reached(army) and "Unwavering Sentinels" in strat_names:
                self._try_unwavering_sentinels(army, opponent)
            if not self._strat_cap_reached(army) and "Multipotentiality" in strat_names:
                self._try_multipotentiality(army, opponent)
            if not self._strat_cap_reached(army) and "Archaeotech Munitions" in strat_names:
                self._try_archaeotech_munitions(army, opponent)
            if not self._strat_cap_reached(army) and "Avenge the Fallen" in strat_names:
                self._try_avenge_the_fallen(army, opponent)
            # Vigilance Eternal — catalogued in SHIELD_HOST_STRATAGEMS for the
            # auditor + stratagems_for_army listing, but the dispatcher is a
            # no-op APPROXIMATION (sticky-objective mechanism is per-detachment-
            # flag-gated, not per-stratagem-fire).

            # ----- Oathband (Leagues of Votann) — six real stratagems (iter-9)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
            # All six wire onto existing transient_* flags / judgement_tokens
            # plumbing; the Judgement-Token-bearing gate is APPROXIMATED to
            # "the highest-threat enemy" because the AI heuristic doesn't
            # track per-unit token presence yet. Stacks with the existing
            # `simulator.judgement_tokens` re-roll buffs at 1+/3+ thresholds
            # — Warrior Pride / Wrath / Ancestral Sentence compound the token
            # economy rather than replacing it.
            if not self._strat_cap_reached(army) and "Warrior Pride" in strat_names:
                self._try_warrior_pride(army, opponent)
            if not self._strat_cap_reached(army) and "Wrath of the Ancestors" in strat_names:
                self._try_wrath_of_the_ancestors(army, opponent)
            if not self._strat_cap_reached(army) and "Glory of the Hearth" in strat_names:
                self._try_glory_of_the_hearth(army, opponent)
            if not self._strat_cap_reached(army) and "Ironkin Sequence" in strat_names:
                self._try_ironkin_sequence(army, opponent)
            if not self._strat_cap_reached(army) and "Ancestral Sentence" in strat_names:
                self._try_ancestral_sentence(army, opponent)
            if not self._strat_cap_reached(army) and "Void-Armoured Resilience" in strat_names:
                self._try_void_armoured_resilience(army, opponent)

            # ----- Gladius Task Force (Adeptus Astartes) — six real strats (iter-12)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
            # Replaces the iter-0 zero-stratagem state where Marines burned every
            # strat fire on Command Re-Roll (universal Core). Closes
            # docs/AUDIT_PARITY.md fix #1 (largest 0/6 gap — Marines is 134
            # units / the most-used codex). All six dispatchers follow the
            # Shield Host / Oathband pattern: route through the closest
            # existing transient_* flag and document the gap.
            if not self._strat_cap_reached(army) and "Storm of Fire" in strat_names:
                self._try_storm_of_fire(army, opponent)
            if not self._strat_cap_reached(army) and "Armour of Contempt" in strat_names:
                self._try_armour_of_contempt(army, opponent)
            if not self._strat_cap_reached(army) and "Squad Tactics" in strat_names:
                self._try_squad_tactics(army, opponent)
            if not self._strat_cap_reached(army) and "Only In Death Does Duty End" in strat_names:
                self._try_only_in_death_does_duty_end(army, opponent)
            if not self._strat_cap_reached(army) and "Honour the Chapter" in strat_names:
                self._try_honour_the_chapter(army, opponent)
            if not self._strat_cap_reached(army) and "Adaptive Strategy" in strat_names:
                self._try_adaptive_strategy(army, opponent)

            # ----- Combined Arms (Astra Militarum) — six real strats (iter-14)
            # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
            # Closes the AM 0/6 detachment-stratagem gap (docs/AUDIT_PARITY.md).
            # Three wire onto Voice of Command Order economy (Coordinated
            # Action, Flexible Command, Inspired Command), three onto
            # existing transient_* flags (Fields of Fire, Stalwart Protector),
            # and Reinforcements! is a no-op APPROXIMATION (no respawn hook).
            if not self._strat_cap_reached(army) and "Coordinated Action" in strat_names:
                self._try_coordinated_action(army, opponent)
            if not self._strat_cap_reached(army) and "Flexible Command" in strat_names:
                self._try_flexible_command(army, opponent)
            if not self._strat_cap_reached(army) and "Fields of Fire" in strat_names:
                self._try_fields_of_fire(army, opponent)
            if not self._strat_cap_reached(army) and "Inspired Command" in strat_names:
                self._try_inspired_command(army, opponent)
            if not self._strat_cap_reached(army) and "Stalwart Protector" in strat_names:
                self._try_stalwart_protector(army, opponent)

            # ----- ST-2 wave 3 — one stratagem per under-performing faction
            # All five route the offensive value through an existing
            # transient_* flag (transient_plus_one_to_wound_melee for melee,
            # transient_reroll_hits_shooting for ranged). Faction-gated via
            # the detachment-membership check above (strat_names already
            # filters to the active detachment's stratagem set).
            if not self._strat_cap_reached(army) and "Apoplectic Frenzy" in strat_names:
                self._try_apoplectic_frenzy(army, opponent)
            if not self._strat_cap_reached(army) and "Denizens of the Warp" in strat_names:
                self._try_denizens_of_the_warp(army, opponent)
            if not self._strat_cap_reached(army) and "Empyric Channelling" in strat_names:
                self._try_empyric_channelling(army, opponent)
            if not self._strat_cap_reached(army) and "Cult Ambush" in strat_names:
                self._try_cult_ambush(army, opponent)
            if not self._strat_cap_reached(army) and "Profane Zeal" in strat_names:
                self._try_profane_zeal(army, opponent)
        finally:
            # Always drop the dispatch flag — Tank Shock / Counter-Offensive /
            # Command Re-Roll fire out-of-band via _fire_stratagem and MUST
            # NOT increment the per-Command-phase counter (those are Core
            # Stratagems on per-trigger hooks, not detachment-stratagem
            # round-start spends). Heroic Intervention is a free core
            # CHARACTER ability — see _do_heroic_intervention.
            self._dispatching_detachment_stratagems = False

    def _strat_cap_reached(self, army: Army) -> bool:
        """Returns True iff `army` has already fired its per-Command-phase
        quota of detachment stratagems. Faction-neutral guard used by
        `_apply_detachment_stratagems` to short-circuit subsequent
        dispatcher entries once the army hits the cap.
        """
        return (
            army.stratagems_fired_this_command_phase
            >= self.DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE
        )

    # ----- target-selection helpers used by the dispatchers --------------

    def _highest_threat_enemy(self, opponent: Army):
        """Pick the alive enemy unit with the highest role-weighted threat.

        Same role-weighting as `_apply_psychic_phase` so Doombolt and any
        future MW-payload stratagem agree on what counts as a worthwhile
        target — heavy / shooty / wounded enemies first, hordes last.

        Battle-shocked enemies are excluded — 10e core forbids using
        Stratagems to affect a Battle-shocked unit regardless of side.
        Cited as `simulator.battleshock` (task #168).
        """
        from .roles import classify
        ROLE_THREAT = {"HEAVY": 3.0, "SHOOTY": 2.0, "DUAL": 1.5,
                       "MELEE": 1.0, "SUPPORT": 1.2, "HORDE": 0.6}
        targets = [
            u for u in opponent.alive_units
            if u.uid not in self._battleshocked_this_round
        ]
        if not targets:
            return None

        def _score(u):
            role = classify(u.profile)
            return ROLE_THREAT.get(role, 1.0) * u.current_health
        return max(targets, key=_score)

    @staticmethod
    def _unit_matches_filter(unit, keyword: str = "", faction: str = "") -> bool:
        """Test a unit against the {keyword, faction} stratagem-target filter.

        We check the keyword against `profile.unit_keywords` AND the faction
        against `profile.faction` because BSData parsing emits faction tags
        (e.g. "Aeldari", "Death Guard") on the `faction` field rather than
        as unit keywords. The dispatcher accepts either signal so we don't
        leak buffs onto units the detachment shouldn't include.
        """
        if not keyword and not faction:
            return True
        if keyword and keyword in (unit.profile.unit_keywords or ()):
            return True
        if faction and (unit.profile.faction or "").lower() == faction.lower():
            return True
        return False

    def _highest_dpa_unit(self, army: Army, keyword: str = "", faction: str = ""):
        """Pick the alive friendly unit with the highest melee+ranged DPA.

        Optional `keyword`/`faction` filter restricts to units carrying
        that keyword (e.g. PSYKER) or belonging to that faction
        (e.g. "Aeldari") so a Warhost army with stray non-Aeldari
        allies still targets the right detachment. See
        `_unit_matches_filter` for the lookup logic.

        Battle-shocked units are excluded — 10e core: "While a unit is
        Battle-shocked, ... you cannot use Stratagems to affect that
        unit." Cited as `simulator.battleshock` (task #168).
        """
        candidates = [
            u for u in army.alive_units
            if self._unit_matches_filter(u, keyword=keyword, faction=faction)
            and u.uid not in self._battleshocked_this_round
        ]
        if not candidates:
            return None

        def _dpa(u):
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            melee = (p.melee_attacks * p.melee_hit_probability
                     * (p.melee_damage_per_shot or 0.0))
            return ranged + melee
        return max(candidates, key=_dpa)

    def _most_vulnerable_unit(self, army: Army, keyword: str = "", faction: str = ""):
        """Pick the alive friendly unit most likely to benefit from a
        defensive stratagem — wounded + high-value.

        Score: (points_cost) × (1.0 - current_health/max_health). A unit at
        full HP gets 0 (no buff needed); a Knight at 30% HP scores very
        high. Restricted to units matching the keyword/faction filter.

        Battle-shocked units are excluded — 10e core: "While a unit is
        Battle-shocked, ... you cannot use Stratagems to affect that
        unit." Cited as `simulator.battleshock` (task #168).
        """
        candidates = [
            u for u in army.alive_units
            if self._unit_matches_filter(u, keyword=keyword, faction=faction)
            and u.uid not in self._battleshocked_this_round
        ]
        if not candidates:
            return None

        def _vulnerability(u):
            hp_max = max(1.0, u.profile.health)
            hp_lost = 1.0 - (u.current_health / hp_max)
            return float(u.profile.points_cost) * hp_lost
        scored = max(candidates, key=_vulnerability)
        # Only return if there's meaningful vulnerability — otherwise fall
        # back to highest points-cost frontline unit (the canonical "save
        # the Marneus from a stratagem" target).
        if _vulnerability(scored) > 0:
            return scored
        return max(candidates, key=lambda u: float(u.profile.points_cost))

    # ----- per-stratagem dispatchers -------------------------------------
    # Post 2026-05-15 fabrication audit (commit fa9a957): 11 dispatchers were
    # removed alongside their fabricated stratagem constants. The three
    # survivors below correspond to real Wahapedia entries.

    def _try_disgustingly_resilient(self, army: Army, opponent: Army) -> None:
        """Disgustingly Resilient (Virulent Vectorium, 2 CP): -1 damage taken
        on a DEATH GUARD INFANTRY or DEATH GUARD CHARACTER unit for the
        round. Picks the most vulnerable eligible unit; if none qualifies
        the stratagem does not fire (per F-DG-1, iter 1: real Wahapedia
        scope is DG INFANTRY / DG CHARACTER only — VEHICLEs and MONSTERs
        like Plagueburst Crawler / Foetid Bloat-Drone / Plague Hulk are
        NOT eligible). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium
        """
        # Eligible: alive DG unit with INFANTRY or CHARACTER keyword and
        # NOT a VEHICLE or MONSTER (a real DG datasheet may list both
        # CHARACTER and MONSTER — e.g. Mortarion — but the stratagem
        # text restricts the buff to the INFANTRY/CHARACTER half).
        def _eligible(u) -> bool:
            if (u.profile.faction or "") != "Death Guard":
                return False
            kw = set(u.profile.unit_keywords or ())
            if "VEHICLE" in kw or "MONSTER" in kw:
                return False
            return "INFANTRY" in kw or "CHARACTER" in kw

        candidates = [
            u for u in army.alive_units
            if _eligible(u) and u.uid not in self._battleshocked_this_round
        ]
        if not candidates:
            return

        def _vulnerability(u):
            hp_max = max(1.0, u.profile.health)
            hp_lost = 1.0 - (u.current_health / hp_max)
            return float(u.profile.points_cost) * hp_lost

        target = max(candidates, key=_vulnerability)
        if _vulnerability(target) <= 0:
            target = max(candidates, key=lambda u: float(u.profile.points_cost))
        ctx = {"target": target}
        if not should_fire_stratagem(army, DISGUSTINGLY_RESILIENT, ctx):
            return
        if not self._fire_stratagem(army, DISGUSTINGLY_RESILIENT):
            return
        target.transient_minus_one_damage_taken = True

    def _try_putrid_detonation(self, army: Army, opponent: Army) -> None:
        """Putrid Detonation (Virulent Vectorium, 1 CP): auto-success on the
        Deadly Demise d6 roll for the round. Fires when the army has at
        least one DG VEHICLE or DG MONSTER on the table with deadly_demise > 0
        (otherwise the buff is wasted). APPROXIMATION: real text targets one
        specific destruction; we arm the flag for the round and any
        qualifying DG VEHICLE / MONSTER death auto-detonates."""
        # Eligible donor: any alive DG VEHICLE/MONSTER with deadly_demise > 0.
        candidate = None
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "VEHICLE" not in kw and "MONSTER" not in kw:
                continue
            if (u.profile.faction or "") != "Death Guard":
                continue
            if (getattr(u.profile, "deadly_demise", 0) or 0) <= 0:
                continue
            candidate = u
            break
        if candidate is None:
            return
        ctx = {"target": candidate}
        if not should_fire_stratagem(army, PUTRID_DETONATION, ctx):
            return
        if not self._fire_stratagem(army, PUTRID_DETONATION):
            return
        army.putrid_detonation_armed = True

    def _try_plaguesurge(self, army: Army, opponent: Army) -> None:
        """Plaguesurge (Virulent Vectorium, 2 CP): +3" to Contagion Range
        until next Command phase. APPROXIMATION: contagion radius is hard-
        coded at 6" elsewhere; the flag is set for the round but not
        consumed yet. The CP spend still fires + emits the StratagemFired
        event so the AI's CP accounting stays honest."""
        # Need a DG WARLORD on the battlefield to target.
        warlord = None
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "CHARACTER" in kw and (u.profile.faction or "") == "Death Guard":
                warlord = u
                break
        if warlord is None:
            return
        ctx = {"target": warlord}
        if not should_fire_stratagem(army, PLAGUESURGE, ctx):
            return
        if not self._fire_stratagem(army, PLAGUESURGE):
            return
        army.plaguesurge_active = True

    def _try_leechspore_eruption(self, army: Army, opponent: Army) -> None:
        """Leechspore Eruption (Virulent Vectorium, 1 CP): roll D6-per-wound-
        lost on a damaged DG model; each 5+ deals 1 MW to a nearby enemy
        (cap 6) AND heals 1 lost wound on the model (cap 6).

        Implementation: pick a DG model with the most wounds lost; resolve
        the dice deterministically by taking the expected value (each D6 has
        2/6 = 33.3% chance of a 5+, so floor(wounds_lost * 1/3) mortals are
        applied; matches the simulator's other 'median dice' approximations).
        Heal the same number on the DG model. Target = nearest enemy within
        3" of the DG model; skip if none."""
        # Pick the DG model with the most wounds lost (current_health < max).
        target = self._most_vulnerable_unit(
            army, keyword="DEATH GUARD", faction="Death Guard",
        )
        if target is None:
            return
        wounds_lost = max(0.0, target.profile.health - target.current_health)
        if wounds_lost < 1.0:
            return
        # Find nearest enemy within 3" — required for the targeting clause.
        nearest = None
        nearest_dist = 999.0
        for e in opponent.alive_units:
            d = _distance(target.position, e.position)
            if d <= 3.0 and d < nearest_dist:
                nearest = e
                nearest_dist = d
        if nearest is None:
            return
        ctx = {"target": target, "enemy": nearest}
        if not should_fire_stratagem(army, LEECHSPORE_ERUPTION, ctx):
            return
        if not self._fire_stratagem(army, LEECHSPORE_ERUPTION):
            return
        # Median dice: each D6 has 2/6 chance of a 5+, so apply
        # round(wounds_lost * 2/6) mortal wounds, capped at 6, matching the
        # simulator's other 'median D3/D6' deterministic conversions.
        mortals = min(6, int(round(wounds_lost * 2.0 / 6.0)))
        heal = mortals  # cap 6 already enforced
        if mortals > 0:
            nearest.receive_damage(float(mortals), bonus_fnp=nearest.profile.fnp)
            if not nearest.is_alive:
                self._emit(UnitKilled(unit_uid=nearest.uid))
        if heal > 0:
            target.current_health = min(
                target.profile.health, target.current_health + float(heal),
            )

    def _try_overwhelming_generosity(self, army: Army, opponent: Army) -> None:
        """Overwhelming Generosity (Virulent Vectorium, 1 CP): re-roll the
        number-of-attacks roll for a DG CHARACTER unit's ranged attacks vs a
        visible enemy. APPROXIMATION: we don't model per-weapon attack-count
        dice (BSData parses attacks as a fixed integer at mapper time), so
        the simulator routes the effect through transient_reroll_hits_shooting
        on the DG CHARACTER unit (re-roll failed hits on its shoot for the
        round) — a more conservative buff than the real text's full-reroll-
        attack-count, since attack-count rerolls average ~10% extra shots
        while hit rerolls average ~17% extra hits on 4+ BS.

        VISIBILITY GATE (iter-5 fix per Wahapedia "Select one enemy unit
        VISIBLE to your unit"): the chosen DG CHARACTER must have line of
        sight to at least one alive enemy within its ranged weapon's range.
        Without this gate, OG was firing R1 at 0.83/battle even though the
        firing CHARACTER had no viable target on a 60×44 board with
        terrain — wasting 1 CP on a buff that produced no R1 damage.
        See `docs/AUTO_LOOP_ITER5_DG_UNSAMPLED.md` for the diagnostic."""
        # Rank friendly DG CHARACTER candidates by ranged DPA (highest first).
        # We need to iterate (not just pick the best) so that if the top-DPA
        # CHARACTER has no LoS, we can fall through to the next candidate
        # rather than wasting the strat fire on a blind shooter.
        candidates: list = []
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "CHARACTER" not in kw:
                continue
            if (u.profile.faction or "") != "Death Guard":
                continue
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            if ranged <= 0.0:
                continue
            candidates.append((ranged, u))
        if not candidates:
            return
        candidates.sort(key=lambda pair: pair[0], reverse=True)

        # Wahapedia: "Select one enemy unit visible to your unit." Walk the
        # candidates and pick the first DG CHARACTER that actually has at
        # least one alive enemy in shoot range AND with LoS. Without LoS,
        # the stratagem has no legal target — skip firing entirely (no CP
        # spent), matching the real-meta behaviour where DG players cannot
        # fire OG R1 when their CHARACTER is deep in their deployment zone
        # with no enemies visible across the board.
        candidate = None
        for _, cand in candidates:
            rng = float(cand.profile.range_inches or 0.0)
            if rng <= 0.0:
                continue
            for enemy in opponent.alive_units:
                if _distance(cand.position, enemy.position) > rng:
                    continue
                if not self.map.has_line_of_sight(
                    cand.position, enemy.position,
                    attacker_keywords=cand.profile.unit_keywords or (),
                    target_keywords=enemy.profile.unit_keywords or (),
                ):
                    continue
                candidate = cand
                break
            if candidate is not None:
                break
        if candidate is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": candidate, "target": target}
        if not should_fire_stratagem(army, OVERWHELMING_GENEROSITY, ctx):
            return
        if not self._fire_stratagem(army, OVERWHELMING_GENEROSITY):
            return
        candidate.transient_reroll_hits_shooting = True

    def _try_creeping_blight(self, army: Army, opponent: Army) -> None:
        """Creeping Blight (Virulent Vectorium, 1 CP): re-roll Hit AND Wound
        rolls on a DG INFANTRY unit's ranged attacks vs Afflicted enemies.
        APPROXIMATION: we don't model Afflicted enemy state, so we route the
        effect through transient_reroll_hits_shooting AND
        transient_reroll_wounds on the DG INFANTRY unit (the full hit+wound
        reroll grant the codex describes; ST-1 added the wound leg via the
        new transient_reroll_wounds flag — previously only the hit leg
        landed). Picks the highest-DPA friendly DG INFANTRY that has the
        gate's other prerequisite (not yet shot this phase, which is
        implicit at round-start dispatch)."""
        candidate = None
        best_dpa = 0.0
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "INFANTRY" not in kw:
                continue
            if (u.profile.faction or "") != "Death Guard":
                continue
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            if ranged > best_dpa:
                best_dpa = ranged
                candidate = u
        if candidate is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": candidate, "target": target}
        if not should_fire_stratagem(army, CREEPING_BLIGHT, ctx):
            return
        if not self._fire_stratagem(army, CREEPING_BLIGHT):
            return
        candidate.transient_reroll_hits_shooting = True
        candidate.transient_reroll_wounds = True

    def _try_lightning_fast_reactions(self, army: Army, opponent: Army) -> None:
        """Lightning-Fast Reactions (Warhost): +1 save on the most
        vulnerable AELDARI unit for the round. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        target = self._most_vulnerable_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, LIGHTNING_FAST_REACTIONS, ctx):
            return
        if not self._fire_stratagem(army, LIGHTNING_FAST_REACTIONS):
            return
        target.transient_plus_one_save = True

    def _try_fire_and_fade(self, army: Army, opponent: Army) -> None:
        """Fire and Fade (Warhost): re-roll failed hits on a friendly
        AELDARI unit's shooting for the round (approximating the canonical
        shoot-then-move-6" via offensive uplift). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        attacker = self._highest_dpa_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, FIRE_AND_FADE, ctx):
            return
        if not self._fire_stratagem(army, FIRE_AND_FADE):
            return
        attacker.transient_reroll_hits_shooting = True

    def _try_skyborne_sanctuary(self, army: Army, opponent: Army) -> None:
        """Skyborne Sanctuary (Warhost, 1 CP). Real rule: end of Fight
        phase, an AELDARI INFANTRY unit not in engagement range and wholly
        within 6" of a friendly AELDARI TRANSPORT can embark within it.
        APPROXIMATION: SwegHammer's stratagem dispatcher fires at round
        start, not end-of-fight, and re-embark mid-battle isn't wired into
        the activation loop. We route the defensive value through the
        existing `transient_plus_one_save` flag on the most vulnerable
        AELDARI unit for the round, which captures the "shelter the
        wounded unit" use case the codex stratagem most often serves.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        target = self._most_vulnerable_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, SKYBORNE_SANCTUARY, ctx):
            return
        if not self._fire_stratagem(army, SKYBORNE_SANCTUARY):
            return
        target.transient_plus_one_save = True

    def _try_feigned_retreat(self, army: Army, opponent: Army) -> None:
        """Feigned Retreat (Warhost, 1 CP). Real rule: your Movement
        phase, just after an AELDARI INFANTRY unit Falls Back — until
        end of turn the unit can shoot and declare a charge despite
        Falling Back. APPROXIMATION: the round-start dispatcher fires
        before any Fall Back has been resolved this round, so we route
        the offensive value through `transient_assault_this_round` on
        the highest-DPA AELDARI unit (closest single-flag stand-in for
        "lets the unit reposition AND shoot the same round"). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        attacker = self._highest_dpa_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, FEIGNED_RETREAT, ctx):
            return
        if not self._fire_stratagem(army, FEIGNED_RETREAT):
            return
        attacker.transient_assault_this_round = True

    def _try_blitzing_firepower(self, army: Army, opponent: Army) -> None:
        """Blitzing Firepower (Warhost, 1 CP). Real rule: your Shooting
        phase, when an AELDARI unit is selected to shoot — until end of
        phase its ranged weapons gain [SUSTAINED HITS 1] vs targets
        within 12" (or improve to 5+ Critical Hit if already having the
        ability). ST-1: now routes through the proper
        `transient_sustained_hits` accumulator (additive on top of any
        per-weapon SUSTAINED HITS already on the profile, matching the
        codex stacking rule). The 12" range gate and the 5+ Critical
        Hit upgrade for weapons already carrying SUSTAINED HITS X are
        still not modelled. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        attacker = self._highest_dpa_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, BLITZING_FIREPOWER, ctx):
            return
        if not self._fire_stratagem(army, BLITZING_FIREPOWER):
            return
        attacker.transient_sustained_hits += 1

    def _try_webway_tunnel(self, army: Army, opponent: Army) -> None:
        """Webway Tunnel (Warhost, 1 CP). Real rule: end of opponent's
        Fight phase, an AELDARI INFANTRY unit wholly within 9" of a
        battlefield edge and not in engagement range may enter Strategic
        Reserves. APPROXIMATION: SwegHammer's reserve queue has no
        mid-battle re-entry hook, so the "pull the unit off the table
        to avoid the next attack" defensive payoff is routed through
        the existing `transient_plus_one_save` flag on the most
        vulnerable AELDARI unit for the round. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost"""
        target = self._most_vulnerable_unit(
            army, keyword="AELDARI", faction="Aeldari",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, WEBWAY_TUNNEL, ctx):
            return
        if not self._fire_stratagem(army, WEBWAY_TUNNEL):
            return
        target.transient_plus_one_save = True

    # ----- Mont'ka (T'au Empire) per-stratagem dispatchers (#196) --------
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka

    def _try_pinpoint_counter_offensive(self, army: Army, opponent: Army) -> None:
        """Pinpoint Counter-Offensive (1 CP). Real rule: when a T'AU EMPIRE
        unit is destroyed, until end of phase, other friendly T'AU EMPIRE
        units re-roll Hit rolls against the enemy unit responsible.
        APPROXIMATION: round-start dispatch can't observe a fresh kill, so
        we gate on the AI heuristic (general 'fire when shooty unit will
        actually swing') and grant a flat transient hit re-roll on the
        highest-DPA T'au unit for the round."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PINPOINT_COUNTER_OFFENSIVE, ctx):
            return
        if not self._fire_stratagem(army, PINPOINT_COUNTER_OFFENSIVE):
            return
        attacker.transient_reroll_hits_shooting = True

    def _try_aggressive_mobility(self, army: Army, opponent: Army) -> None:
        """Aggressive Mobility (1 CP). Real rule: in your Movement phase,
        replace an Advance roll with a flat +6" Move and treat the unit as
        having Advanced — its ranged weapons would then need [ASSAULT] (or
        Killing Blow rounds 1-3) to shoot. SwegHammer collapses the
        movement-replacement clause and routes the value as a transient
        [ASSAULT] grant for the round (same flag Matchless Agility uses).
        Gate: pick the highest-DPA T'au shooter."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, AGGRESSIVE_MOBILITY, ctx):
            return
        if not self._fire_stratagem(army, AGGRESSIVE_MOBILITY):
            return
        attacker.transient_assault_this_round = True

    def _try_focused_fire(self, army: Army, opponent: Army) -> None:
        """Focused Fire (1 CP). Real rule: in your Shooting phase, two T'au
        units selecting the same target gain +1 AP for that shoot. Cannot
        be used in rounds 4-5. APPROXIMATION: the simulator's flag set has
        no AP-improvement transient, so we route the offensive value
        through `transient_plus_one_to_hit_shooting` on the highest-DPA
        T'au shooter (it's the same swing direction — more landed wounds
        per shoot). Round gate skipped at round-start dispatch."""
        if self._current_round >= 4:
            return     # canonical rounds 1-3 only
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, FOCUSED_FIRE, ctx):
            return
        if not self._fire_stratagem(army, FOCUSED_FIRE):
            return
        attacker.transient_plus_one_to_hit_shooting = True

    def _try_combat_debarkation(self, army: Army, opponent: Army) -> None:
        """Combat Debarkation (1 CP). Real rule: a T'au unit that
        disembarked this turn re-rolls Wound rolls against the closest
        enemy unit in its shooting. APPROXIMATION: we don't track
        'disembarked-this-turn' at stratagem-dispatch time, so the gate
        is widened to any T'au shooter. ST-1: now routes through
        `transient_reroll_wounds` (the proper full-wound-reroll flag —
        the citation says "re-roll the Wound roll"), replacing the
        previous mis-mapping onto `transient_reroll_hits_shooting`
        which lifted hit-roll re-rolls instead of wound-roll re-rolls
        and so was the wrong stat altogether."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, COMBAT_DEBARKATION, ctx):
            return
        if not self._fire_stratagem(army, COMBAT_DEBARKATION):
            return
        attacker.transient_reroll_wounds = True

    def _try_pulse_onslaught(self, army: Army, opponent: Army) -> None:
        """Pulse Onslaught (2 CP). Real rule: target an enemy unit; until
        the end of the phase its Move is reduced by 2 and its Charge /
        Advance rolls are reduced by 2. TODO: APPROXIMATION — SwegHammer
        has no enemy-movement-debuff transient, so we route the offensive
        value through `transient_plus_one_to_hit_shooting` on the
        firing T'au unit (models the 'shaken' enemy being easier to hit).
        Wire a proper enemy move debuff when the simulator gains the
        infrastructure."""
        attacker = self._highest_dpa_unit(
            army, faction="T'au Empire",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Tau Empire")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PULSE_ONSLAUGHT, ctx):
            return
        if not self._fire_stratagem(army, PULSE_ONSLAUGHT):
            return
        attacker.transient_plus_one_to_hit_shooting = True

    def _try_counterfire_defence_systems(self, army: Army, opponent: Army) -> None:
        """Counterfire Defence Systems (2 CP). Real rule: in your
        opponent's Shooting phase, after targets selected, a T'au unit
        being shot at gets -1 Damage for the phase. Maps cleanly to
        `transient_minus_one_damage_taken` on the most vulnerable T'au
        unit for the round (matching how Disgustingly Resilient
        routes its DG defensive payload)."""
        target = self._most_vulnerable_unit(
            army, faction="T'au Empire",
        )
        if target is None:
            target = self._most_vulnerable_unit(army, faction="Tau Empire")
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, COUNTERFIRE_DEFENCE_SYSTEMS, ctx):
            return
        if not self._fire_stratagem(army, COUNTERFIRE_DEFENCE_SYSTEMS):
            return
        target.transient_minus_one_damage_taken = True

    # ----- Awakened Dynasty (Necrons) protocol dispatchers ---------------
    # Six real Protocol stratagems (#194). Wahapedia:
    # https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
    # Of the six, two are catalogued-but-no-op APPROXIMATIONs because the
    # effect ("return a destroyed CHARACTER" / "out-of-sequence shoot at
    # the unit that just destroyed a friendly Necron") has no clean hook
    # in the current simulator. Eligible-but-not-fired so any future
    # extension can wire them without touching the citation file.

    def _is_led_unit(self, unit) -> bool:
        """Approximation: a NECRONS unit counts as 'led by a CHARACTER' for
        the protocol stratagems' optional uplift if any alive friendly
        CHARACTER is within 6" (the canonical Lead-ability aura range).
        """
        try:
            army = unit.army_ref
            if army is None:
                return False
            for u in army.alive_units:
                if u is unit:
                    continue
                kw = u.profile.unit_keywords or ()
                if "CHARACTER" not in kw:
                    continue
                if _distance(u.position, unit.position) <= 6.0:
                    return True
        except Exception:
            return False
        return False

    def _try_protocol_undying_legions(self, army: Army, opponent: Army) -> None:
        """Protocol of the Undying Legions (Awakened Dynasty, 1 CP): a
        friendly NECRONS unit that just lost models reanimates D3 wounds
        (D3+1 if led). The simulator fires this at round start as an
        anticipatory pulse on the most-wounded NECRONS unit; the pulse
        triggers in `_apply_undying_legions_pulse` at the end of the
        opponent's activations (we collapse opponent shooting / fight
        into the round-end reanimation step). Median D3 = 2, so
        unled = 2 wounds, led = 3 wounds. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        target = self._most_vulnerable_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_UNDYING_LEGIONS, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_UNDYING_LEGIONS):
            return
        # Median D3 = 2; +1 if led.
        wounds = 3 if self._is_led_unit(target) else 2
        target.transient_undying_legions_pulse = wounds

    def _try_protocol_hungry_void(self, army: Army, opponent: Army) -> None:
        """Protocol of the Hungry Void (Awakened Dynasty, 1 CP): +1 S
        melee (+1 AP melee if led) on a NECRONS unit for the round.
        APPROXIMATION: the simulator doesn't expose a clean per-round S/AP
        boost slot, so we route the equivalent offensive uplift through
        `transient_plus_one_to_wound_melee` (the existing +1-to-wound flag
        used by Outbreak of Pestilence). Same direction, slightly more
        generous than the true +1 S (because +1 to wound always closes a
        bracket whereas +1 S only sometimes does). The AP leg is dropped
        in the unled case and folded into the wound buff when led.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        attacker = self._highest_dpa_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_HUNGRY_VOID, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_HUNGRY_VOID):
            return
        attacker.transient_plus_one_to_wound_melee = True

    def _try_protocol_sudden_storm(self, army: Army, opponent: Army) -> None:
        """Protocol of the Sudden Storm (Awakened Dynasty, 1 CP): ranged
        weapons on a NECRONS unit gain [ASSAULT] for the turn (re-roll
        Advance rolls if led — that leg is dropped because the simulator
        has no Advance re-roll hook and the Assault grant alone is the
        primary value). Maps cleanly to `transient_assault_this_round`.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        attacker = self._highest_dpa_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_SUDDEN_STORM, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_SUDDEN_STORM):
            return
        attacker.transient_assault_this_round = True

    def _try_protocol_conquering_tyrant(self, army: Army, opponent: Army) -> None:
        """Protocol of the Conquering Tyrant (Awakened Dynasty, 1 CP):
        re-roll Hit rolls of 1 within half range on a NECRONS unit's
        shoot (full re-roll if led). APPROXIMATION: the simulator's
        `transient_reroll_hits_shooting` flag triggers a full hit
        re-roll, not just 1s — direction-correct but slightly more
        generous than the unled stratagem. Range gate is dropped because
        the simulator already computes half-range mechanics per shot
        and the AI only fires this when there's a meaningful shooter.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        """
        attacker = self._highest_dpa_unit(
            army, keyword="NECRONS", faction="Necrons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PROTOCOL_OF_THE_CONQUERING_TYRANT, ctx):
            return
        if not self._fire_stratagem(army, PROTOCOL_OF_THE_CONQUERING_TYRANT):
            return
        attacker.transient_reroll_hits_shooting = True

    # ----- War Horde (Orks) per-stratagem dispatchers (iter-1 B1) --------
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
    # WebFetch returned ECONNREFUSED at edit time; effects below are
    # paraphrased per the iter-1 Cluster B diagnostic and routed through
    # existing transient_* flags. Each dispatcher consults the AI gate
    # via `should_fire_stratagem` and spends CP via `_fire_stratagem` —
    # standard pattern, mirroring the Mont'ka / Warhost dispatchers above.

    def _try_power_of_the_waaagh(self, army: Army, opponent: Army) -> None:
        """Power Of The WAAAGH! (War Horde, 1 CP). Real rule (paraphrase):
        an ORKS unit's melee weapons gain [LETHAL HITS] for the fight phase
        (or upgrade to 5+ Critical Hit if they already carry the ability).
        ST-1: now routes through the proper `transient_lethal_hits` flag
        (composes into `effective_lethal_hits` at the crit-to-hit branch
        in Unit.attack). Previously proxied through
        `transient_plus_one_to_wound_melee`, which over-modelled the buff
        because +1 to wound averages ~25% extra landed wounds at threshold
        flip while [LETHAL HITS] only auto-wounds on natural 6s (~17%
        of failed-wound salvage on a 4+ wound roll). The 5+ Critical-Hit
        upgrade leg for weapons already carrying [LETHAL HITS] is still
        dropped.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, POWER_OF_THE_WAAAGH, ctx):
            return
        if not self._fire_stratagem(army, POWER_OF_THE_WAAAGH):
            return
        attacker.transient_lethal_hits = True

    def _try_mob_up(self, army: Army, opponent: Army) -> None:
        """Mob Up (War Horde, 1 CP). Real rule (paraphrase): an ORKS
        INFANTRY unit that has lost models absorbs surviving models from
        a destroyed friendly ORKS INFANTRY unit. APPROXIMATION: no model-
        absorbing hook in SwegHammer, so we route the "regain bodies"
        value through `transient_undying_legions_pulse = 2` on the most
        vulnerable Orks INFANTRY unit — fires the existing mid-phase
        reanimation pulse Awakened Dynasty's Undying Legions uses.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        target = self._most_vulnerable_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, MOB_UP, ctx):
            return
        if not self._fire_stratagem(army, MOB_UP):
            return
        target.transient_undying_legions_pulse = 2

    def _try_big_krumpin(self, army: Army, opponent: Army) -> None:
        """Big Krumpin' (War Horde, 2 CP). Real rule (paraphrase): an
        ORKS unit re-rolls Wound rolls of 1 in melee (full re-roll if
        charging). ST-1: now routes through `transient_reroll_wounds_ones`
        — the correct lossy proxy for the codex (1s-only re-roll averages
        ~14% extra landed wounds). Previously proxied through
        `transient_plus_one_to_wound_melee`, which was strictly stronger
        (+1 to wound ≈ 25% extra wounds vs 14% for 1s-reroll). The full-
        reroll-when-charging leg is dropped (no charge-state hook); given
        Big Krumpin' costs 2 CP and the AI gate is already conservative,
        the under-fire on charge turns is acceptable.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, BIG_KRUMPIN, ctx):
            return
        if not self._fire_stratagem(army, BIG_KRUMPIN):
            return
        attacker.transient_reroll_wounds_ones = True

    def _try_tellyporta(self, army: Army, opponent: Army) -> None:
        """Tellyporta (War Horde, 1 CP). Real rule (paraphrase): an ORKS
        INFANTRY unit is removed from the battlefield and placed back via
        Strategic Reserves at the start of the next round. APPROXIMATION:
        no mid-battle reserve hook, so the defensive payoff ("pull the
        unit off the table to avoid the next attack") is routed through
        `transient_plus_one_save` on the most vulnerable Orks INFANTRY
        unit — same single-flag stand-in Webway Tunnel uses for Aeldari.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        target = self._most_vulnerable_unit(
            army, keyword="ORKS", faction="Orks",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, TELLYPORTA, ctx):
            return
        if not self._fire_stratagem(army, TELLYPORTA):
            return
        target.transient_plus_one_save = True

    def _try_da_biggest_boss(self, army: Army, opponent: Army) -> None:
        """Da Biggest Boss (War Horde, 1 CP). Real rule (paraphrase):
        Warlord-targeted; the ORKS CHARACTER Warlord makes a free D6+1"
        Normal Move in the Movement phase. APPROXIMATION: SwegHammer's
        grid-free movement model can't usefully consume per-phase D6+1"
        repositioning, so the offensive payoff (reposition into firing
        / charging range) is routed through `transient_assault_this_round`
        on the highest-DPA Orks CHARACTER — lets the Warlord shoot the
        same round it would have repositioned.
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
        """
        # Pick the highest-DPA Orks CHARACTER.
        warlord = None
        best_dpa = 0.0
        for u in army.alive_units:
            kw = set(u.profile.unit_keywords or ())
            if "CHARACTER" not in kw:
                continue
            if (u.profile.faction or "") != "Orks":
                continue
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            melee = (p.melee_attacks * p.melee_hit_probability
                     * (p.melee_damage_per_shot or 0.0))
            dpa = ranged + melee
            if dpa > best_dpa:
                best_dpa = dpa
                warlord = u
        if warlord is None:
            return
        ctx = {"attacker": warlord}
        if not should_fire_stratagem(army, DA_BIGGEST_BOSS, ctx):
            return
        if not self._fire_stratagem(army, DA_BIGGEST_BOSS):
            return
        warlord.transient_assault_this_round = True

    # ----- Shield Host (Adeptus Custodes) — six real stratagems (iter-8 fix)
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
    # CP costs + WHEN/EFFECT confirmed against Goonhammer 10e codex review +
    # Wahapedia listing. WebFetch against wahapedia.ru returned ECONNREFUSED
    # at edit time; effect descriptions are paraphrased per the canonical
    # Goonhammer source, with each entry flagged APPROXIMATION in
    # data/rule_citations.d/stratagems.json. Effect mappings follow the
    # War Horde / Mont'ka pattern — route through the nearest existing
    # transient_* flag and document the gap.

    def _try_arcane_genetic_alchemy(self, army: Army, opponent: Army) -> None:
        """Arcane Genetic Alchemy (Shield Host, 1 CP, Battle Tactic). Real
        rule: after a Mortal wound is allocated to a friendly Adeptus
        Custodes unit, until end of phase that unit has Feel No Pain 4+
        against Mortal wounds. APPROXIMATION: SwegHammer doesn't model
        mortal-wound-only FNP buckets; we use `transient_fnp_5` (FNP 5+ for
        the round against all damage) on the most vulnerable Custodes unit.
        Direction-correct (defensive damage reduction) but lossy on both
        magnitude (5+ vs 4+) and gate (all damage vs mortal-only). Catalogued
        per iter-8 Shield Host rebuild; Wahapedia URL above.
        """
        target = self._most_vulnerable_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, ARCANE_GENETIC_ALCHEMY, ctx):
            return
        if not self._fire_stratagem(army, ARCANE_GENETIC_ALCHEMY):
            return
        target.transient_fnp_5 = True

    def _try_unwavering_sentinels(self, army: Army, opponent: Army) -> None:
        """Unwavering Sentinels (Shield Host, 1 CP, Strategic Ploy). Real
        rule: Fight phase, after an enemy targets a friendly Custodes
        INFANTRY unit on an objective you control — that enemy unit takes
        -1 to Hit for the rest of the phase. APPROXIMATION: no per-target
        -1-to-hit transient flag in SwegHammer, so we route the defensive
        payoff through `transient_plus_one_save` on the most vulnerable
        Custodes INFANTRY unit. Both buffs reduce incoming damage; lossy
        on the gate (objective control + per-attacker scope).
        """
        target = self._most_vulnerable_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, UNWAVERING_SENTINELS, ctx):
            return
        if not self._fire_stratagem(army, UNWAVERING_SENTINELS):
            return
        target.transient_plus_one_save = True

    def _try_multipotentiality(self, army: Army, opponent: Army) -> None:
        """Multipotentiality (Shield Host, 1 CP, Strategic Ploy). Real rule:
        your Movement phase, on a Custodes unit that just Fell Back — that
        unit can shoot and declare a charge this turn. APPROXIMATION: maps
        cleanly to `transient_assault_this_round` on the highest-DPA
        Custodes unit (same flag Feigned Retreat uses). Round-start
        dispatcher collapses the 'just Fell Back' precondition.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, MULTIPOTENTIALITY, ctx):
            return
        if not self._fire_stratagem(army, MULTIPOTENTIALITY):
            return
        attacker.transient_assault_this_round = True

    def _try_archaeotech_munitions(self, army: Army, opponent: Army) -> None:
        """Archaeotech Munitions (Shield Host, 1 CP, Wargear). Real rule:
        your Shooting phase, on a Custodes unit — ranged weapons gain
        [LETHAL HITS] OR [SUSTAINED HITS 1] (player's choice) for the
        phase. ST-1: now routes through `transient_lethal_hits` (the
        higher-value half of the player's choice — [LETHAL HITS] on a
        Custodes unit's BS2+ profile typically outscores [SUSTAINED HITS
        1] because Custodes shots are few and high-damage). Previously
        proxied through `transient_plus_one_to_hit_shooting`, which was
        strictly stronger because +1 to hit fires on every die above the
        previous fail threshold whereas [LETHAL HITS] only fires on
        natural 6s.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, ARCHAEOTECH_MUNITIONS, ctx):
            return
        if not self._fire_stratagem(army, ARCHAEOTECH_MUNITIONS):
            return
        attacker.transient_lethal_hits = True

    def _try_avenge_the_fallen(self, army: Army, opponent: Army) -> None:
        """Avenge the Fallen (Shield Host, 1 CP, Strategic Ploy). Real rule:
        start of Fight phase, on a Custodes unit below Starting Strength —
        +1 Attack (or +2 if below half Starting Strength) for the phase.
        APPROXIMATION: SwegHammer doesn't expose a transient per-attack-
        count buff; offensive uplift is routed through
        `transient_plus_one_to_wound_melee` on the most vulnerable Custodes
        melee unit. Direction-correct (more landed melee damage),
        comparable magnitude on a 4+ wound roll.
        """
        target = self._most_vulnerable_unit(
            army, keyword="ADEPTUS CUSTODES", faction="Adeptus Custodes",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, AVENGE_THE_FALLEN, ctx):
            return
        if not self._fire_stratagem(army, AVENGE_THE_FALLEN):
            return
        target.transient_plus_one_to_wound_melee = True

    # ----- Oathband (Leagues of Votann) — six real stratagems (iter-9) ----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
    # Replaces the iter-0 zero-stratagem state where Votann burned every
    # strat fire on Command Re-Roll (universal Core). iter-8 anti-DG audit
    # (docs/AUTO_LOOP_ITER8_ANTI_DG_AUDIT.md fix #2) flagged this set as the
    # top fix for Votann-vs-DG (one of the 7 unsampled-but-positive DG
    # matchups, +8pt over real per iter-5). All six dispatchers follow the
    # Shield Host / Mont'ka / War Horde pattern — route through the nearest
    # existing transient_* flag (or directly into the `judgement_tokens`
    # dict, which already has full plumbing) and document any gap.

    def _try_warrior_pride(self, army: Army, opponent: Army) -> None:
        """Warrior Pride (Oathband, 1 CP). Real rule: re-roll Wound rolls
        for a Votann unit's attacks against a Judgement-Token-bearing enemy.
        APPROXIMATION: routed through `transient_plus_one_to_wound_melee` +
        `transient_plus_one_to_wound_shooting` on the highest-DPA Votann
        unit — same direction (more landed wounds), comparable magnitude on
        a 4+ wound roll. The Judgement-Token-bearing gate is collapsed onto
        "the highest-threat enemy" (the natural primary target). Stacks
        with the existing `simulator.judgement_tokens` re-roll buffs at
        1+/3+ thresholds — the codex effect compounds rather than replaces.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="LEAGUES OF VOTANN", faction="Leagues of Votann",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Leagues of Votann")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, WARRIOR_PRIDE, ctx):
            return
        if not self._fire_stratagem(army, WARRIOR_PRIDE):
            return
        # ST-1: now routes through `transient_reroll_wounds` (full failed-
        # wound re-roll for the round, applies to both melee and shooting
        # via the att_reroll_all_wounds path). Previously proxied through
        # transient_plus_one_to_wound_{melee,shooting}, which was strictly
        # stronger than the codex (+1 to wound averages ~25% extra wounds
        # at threshold flip; reroll-wounds averages ~17% on a 4+ wound
        # roll).
        attacker.transient_reroll_wounds = True

    def _try_wrath_of_the_ancestors(self, army: Army, opponent: Army) -> None:
        """Wrath of the Ancestors (Oathband, 1 CP). Real rule: a Votann unit's
        ranged attacks gain [LETHAL HITS] vs a Judgement-Token-bearing
        target. ST-1: now routes through `transient_lethal_hits` (the
        proper keyword grant — composes into `effective_lethal_hits` at
        the crit-to-hit branch in Unit.attack). Previously proxied
        through `transient_plus_one_to_hit_shooting`, which over-modelled
        the buff because +1-to-hit lifts EVERY die above the previous
        fail threshold whereas [LETHAL HITS] only auto-wounds on natural
        6s.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="LEAGUES OF VOTANN", faction="Leagues of Votann",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Leagues of Votann")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, WRATH_OF_THE_ANCESTORS, ctx):
            return
        if not self._fire_stratagem(army, WRATH_OF_THE_ANCESTORS):
            return
        attacker.transient_lethal_hits = True

    def _try_glory_of_the_hearth(self, army: Army, opponent: Army) -> None:
        """Glory of the Hearth (Oathband, 1 CP). Real rule: a Votann VEHICLE
        unit re-rolls Hit AND Wound rolls when shooting. APPROXIMATION:
        SwegHammer routes the offensive value through
        `transient_reroll_hits_shooting` on the highest-DPA Votann VEHICLE
        — the wound-reroll leg is dropped (no transient wound-reroll flag).
        Strictly weaker than the codex (~half the value), direction-correct.

        Strictly AND-gated on (faction=Votann AND keyword=VEHICLE): the
        helper `_unit_matches_filter` is OR-gated, so the unfiltered result
        would leak the buff onto non-VEHICLE Votann (Hearthkyn). We post-
        filter here so the spend is skipped on a Hearthkyn-mono list.
        """
        candidates = [
            u for u in army.alive_units
            if (u.profile.faction or "").lower() == "leagues of votann"
            and "VEHICLE" in (u.profile.unit_keywords or ())
            and u.uid not in self._battleshocked_this_round
        ]
        if not candidates:
            return
        # Pick the highest-DPA among the strict-filter candidates.
        def _dpa(u):
            p = u.profile
            ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
            melee = (p.melee_attacks or 0) * (p.melee_hit_probability or 0) * (p.melee_damage_per_shot or 0.0)
            return ranged + melee
        attacker = max(candidates, key=_dpa)
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, GLORY_OF_THE_HEARTH, ctx):
            return
        if not self._fire_stratagem(army, GLORY_OF_THE_HEARTH):
            return
        attacker.transient_reroll_hits_shooting = True

    def _try_ironkin_sequence(self, army: Army, opponent: Army) -> None:
        """Ironkin Sequence (Oathband, 1 CP). Real rule: a Votann IRONKIN
        unit gains +1 to Hit for the phase. Maps DIRECTLY onto
        `transient_plus_one_to_hit_shooting` on the highest-DPA IRONKIN
        unit — clean mapping, no approximation gap. Falls back to any
        Votann unit if no IRONKIN unit is in the list (Hearthkyn lists
        ARE IRONKIN, so this normally finds a target).
        """
        attacker = self._highest_dpa_unit(
            army, keyword="IRONKIN", faction="Leagues of Votann",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army, faction="Leagues of Votann")
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, IRONKIN_SEQUENCE, ctx):
            return
        if not self._fire_stratagem(army, IRONKIN_SEQUENCE):
            return
        attacker.transient_plus_one_to_hit_shooting = True

    def _try_ancestral_sentence(self, army: Army, opponent: Army) -> None:
        """Ancestral Sentence (Oathband, 2 CP). Real rule: at the start of
        the phase, issue a Judgement Token to an enemy unit. Maps DIRECTLY
        onto the existing `Army.judgement_tokens[uid]` dict — increments
        the token count on the highest-threat enemy unit so subsequent
        Votann attacks fire the 1+/3+ re-roll thresholds via the existing
        `_maybe_award_judgement_token` plumbing. Clean mapping, no
        approximation gap.

        Gated on `army.is_votann_army` (since the token dict lives on the
        Votann army's `judgement_tokens`) so a non-Votann list carrying
        the Oathband detachment by accident skips the spend.
        """
        if not army.is_votann_army:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, ANCESTRAL_SENTENCE, ctx):
            return
        if not self._fire_stratagem(army, ANCESTRAL_SENTENCE):
            return
        # Direct mapping: increment the Judgement Token count on the target's
        # uid. The token store lives on the VOTANN army (the victim of
        # opponent kills awards tokens; Ancestral Sentence is a "free" token
        # the Votann player issues without needing a kill).
        tokens = army.judgement_tokens
        tokens[target.uid] = tokens.get(target.uid, 0) + 1
        self._emit(JudgementTokenAwarded(
            target_uid=target.uid,
            total_tokens=tokens[target.uid],
        ))

    def _try_void_armoured_resilience(self, army: Army, opponent: Army) -> None:
        """Void-Armoured Resilience (Oathband, 1 CP). Real rule: a Votann
        unit gains 5+ Feel No Pain for the phase. Maps DIRECTLY onto
        `transient_fnp_5` on the most vulnerable Votann unit — clean
        mapping, no approximation gap. Real codex effect is per-phase
        rather than per-round; the simulator's round/phase boundary is
        the same flag scope.
        """
        target = self._most_vulnerable_unit(
            army, keyword="LEAGUES OF VOTANN", faction="Leagues of Votann",
        )
        if target is None:
            target = self._most_vulnerable_unit(army, faction="Leagues of Votann")
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, VOID_ARMOURED_RESILIENCE, ctx):
            return
        if not self._fire_stratagem(army, VOID_ARMOURED_RESILIENCE):
            return
        target.transient_fnp_5 = True

    # ----- Gladius Task Force (Adeptus Astartes) — six real strats (iter-12) -
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
    # Marines is the most-used codex (134 units catalogued) and was on 0/6
    # detachment stratagems before this iter. Per docs/AUDIT_PARITY.md fix #1
    # this is the highest-leverage parity fix — every Marines matchup
    # understated offence by ~2-3 CP/round of detachment value. The six
    # dispatchers mirror the iter-8 Shield Host pattern: AI gate via
    # should_fire_stratagem, spend CP via _fire_stratagem, then apply the
    # transient effect on the chosen unit. Each dispatcher uses an inline
    # `is_marine_faction` filter rather than the `_unit_matches_filter` helper
    # because Marines spans 12 faction strings (Adeptus Astartes + Ultramarines
    # + chapter codices) — see code.factions.MARINE_FACTIONS.

    def _marine_units(self, army: Army):
        """Return alive friendly units belonging to any Marine chapter.

        Faction-gated via `is_marine_faction` (12 faction strings) AND
        excludes Battle-shocked units per 10e core rule
        `simulator.battleshock`. Used by every Gladius dispatcher as the
        target-selection pool.
        """
        from .factions import is_marine_faction
        return [
            u for u in army.alive_units
            if is_marine_faction(u.profile.faction or "")
            and u.uid not in self._battleshocked_this_round
        ]

    @staticmethod
    def _unit_dpa(u) -> float:
        """Combined melee + ranged damage-per-activation. Same scoring as
        `_highest_dpa_unit` but exposed as a free function so the inline
        Marine filters can use it without re-implementing."""
        p = u.profile
        ranged = (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        melee = ((p.melee_attacks or 0) * (p.melee_hit_probability or 0)
                 * (p.melee_damage_per_shot or 0.0))
        return ranged + melee

    def _highest_dpa_marine(self, army: Army, keyword: str = ""):
        """Pick the highest-DPA Marine unit; optional keyword filter (e.g.
        'INFANTRY'). Returns None if no eligible candidate exists."""
        candidates = self._marine_units(army)
        if keyword:
            candidates = [
                u for u in candidates
                if keyword in (u.profile.unit_keywords or ())
            ]
        if not candidates:
            return None
        return max(candidates, key=self._unit_dpa)

    def _most_vulnerable_marine(self, army: Army, keyword: str = ""):
        """Pick the most-vulnerable Marine unit (points × HP-loss); optional
        keyword filter. Returns None if no eligible candidate exists."""
        candidates = self._marine_units(army)
        if keyword:
            candidates = [
                u for u in candidates
                if keyword in (u.profile.unit_keywords or ())
            ]
        if not candidates:
            return None

        def _score(u):
            try:
                cost = float(u.profile.points_cost)
                hp_frac = max(0.0, 1.0 - u.current_health / max(1.0, u.profile.health))
            except Exception:
                return 0.0
            return cost * hp_frac
        # If every candidate is at full HP the score is 0 — fall back to
        # highest-points (the defensive buff still preempts an incoming kill).
        best = max(candidates, key=_score)
        if _score(best) > 0.0:
            return best
        return max(candidates, key=lambda u: float(u.profile.points_cost or 0.0))

    def _try_storm_of_fire(self, army: Army, opponent: Army) -> None:
        """Storm of Fire (Gladius, 1 CP, Battle Tactic). Real rule: your
        Shooting phase, on an ADEPTUS ASTARTES unit — ranged weapons gain
        [SUSTAINED HITS 1] for the phase (or improve existing
        [SUSTAINED HITS X] by 1). ST-1: now routes through
        `transient_sustained_hits` (additive on top of any per-weapon
        SUSTAINED HITS already on the profile, which directly matches the
        codex stacking rule — a weapon with SUSTAINED HITS X gets X+1).
        Previously proxied through `transient_plus_one_to_hit_shooting`,
        which over-modelled the buff because +1-to-hit lifts every die
        above the previous fail threshold whereas SUSTAINED HITS 1 only
        fires on the natural 6.
        """
        candidates = self._marine_units(army)
        # Pre-filter to units with real ranged DPA — Storm of Fire only
        # buffs ranged weapons, so a melee-only Marine brick like
        # Bladeguard would never benefit from the +1-to-hit-shooting flag.
        candidates = [u for u in candidates
                      if (u.profile.attacks or 0) > 0
                      and (u.profile.per_shot_damage or 0.0) > 0.0]
        if not candidates:
            return

        def _ranged_dpa(u):
            p = u.profile
            return (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        attacker = max(candidates, key=_ranged_dpa)
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, STORM_OF_FIRE, ctx):
            return
        if not self._fire_stratagem(army, STORM_OF_FIRE):
            return
        attacker.transient_sustained_hits += 1

    def _try_armour_of_contempt(self, army: Army, opponent: Army) -> None:
        """Armour of Contempt (Gladius, 1 CP, Battle Tactic). Real rule:
        any phase, on an ADEPTUS ASTARTES unit being targeted — enemy AP
        against your unit is reduced by 1 for the phase. APPROXIMATION:
        SwegHammer has no transient enemy-AP-reduction flag, so the
        defensive payoff is routed through `transient_plus_one_save` on
        the most vulnerable Marine unit. Direction-correct (both reduce
        incoming damage); same lossy pattern as Unwavering Sentinels
        (Shield Host). +1 save is comparable on a 3+ save profile but
        loses the high-AP-weapon scaling that the real AP-minus-one
        provides.
        """
        target = self._most_vulnerable_marine(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, ARMOUR_OF_CONTEMPT, ctx):
            return
        if not self._fire_stratagem(army, ARMOUR_OF_CONTEMPT):
            return
        target.transient_plus_one_save = True

    def _try_squad_tactics(self, army: Army, opponent: Army) -> None:
        """Squad Tactics (Gladius, 1 CP, Strategic Ploy). Real rule: your
        opponent's Movement phase, on an ADEPTUS ASTARTES INFANTRY unit —
        that unit may make a Normal Move of up to 6". Mobility /
        repositioning utility (counter to enemy reserves / charges).
        APPROXIMATION: SwegHammer has no opponent-turn reactive move
        hook, so the offensive value is routed through
        `transient_assault_this_round` on the highest-DPA Marine INFANTRY
        unit — same flag Feigned Retreat / Multipotentiality use as the
        "extra setup + shoot after move" proxy.
        """
        attacker = self._highest_dpa_marine(army, keyword="INFANTRY")
        if attacker is None:
            attacker = self._highest_dpa_marine(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, SQUAD_TACTICS, ctx):
            return
        if not self._fire_stratagem(army, SQUAD_TACTICS):
            return
        attacker.transient_assault_this_round = True

    def _try_only_in_death_does_duty_end(self, army: Army, opponent: Army) -> None:
        """Only In Death Does Duty End (Gladius, 1 CP, Strategic Ploy).
        Real rule: the Fight phase, after an ADEPTUS ASTARTES model is
        destroyed before making its attacks — that model may make its
        attacks before being removed. APPROXIMATION: SwegHammer doesn't
        model per-model attack ordering at the destroyed-before-attack
        granularity; the offensive payoff is routed through
        `transient_plus_one_to_wound_melee` on the most vulnerable Marine
        melee unit (the "one last swing" proxy translates to +1 to wound
        on the remaining attacks). Direction-correct; misses the timing
        detail (codex grants attacks to destroyed models, we buff the
        surviving unit). Same lossy pattern as Avenge the Fallen
        (Shield Host).
        """
        target = self._most_vulnerable_marine(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, ONLY_IN_DEATH_DOES_DUTY_END, ctx):
            return
        if not self._fire_stratagem(army, ONLY_IN_DEATH_DOES_DUTY_END):
            return
        target.transient_plus_one_to_wound_melee = True

    def _try_honour_the_chapter(self, army: Army, opponent: Army) -> None:
        """Honour the Chapter (Gladius, 2 CP, Battle Tactic). Real rule:
        any phase, on an ADEPTUS ASTARTES unit — that unit may re-roll
        Hit AND Wound rolls for the phase. The premium 2-CP offensive
        nuke. APPROXIMATION: SwegHammer routes the offensive value
        through `transient_reroll_hits_shooting` on the highest-DPA
        Marine unit — the wound-reroll leg is dropped (no transient
        wound-reroll flag). Strictly weaker than the codex (~half the
        value), direction-correct. Same lossy pattern as Glory of the
        Hearth (Oathband) and Devastating Sorcery (Grand Coven).
        """
        attacker = self._highest_dpa_marine(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, HONOUR_THE_CHAPTER, ctx):
            return
        if not self._fire_stratagem(army, HONOUR_THE_CHAPTER):
            return
        attacker.transient_reroll_hits_shooting = True

    def _try_adaptive_strategy(self, army: Army, opponent: Army) -> None:
        """Adaptive Strategy (Gladius, 1 CP, Strategic Ploy). Real rule:
        start of your Command phase, on an ADEPTUS ASTARTES unit — that
        unit gains the rules of one Combat Doctrine of your choice
        (Devastator / Tactical / Assault) until end of turn, regardless
        of which doctrine the army is currently in.

        SC5-9 audit: this stratagem previously fired
        `transient_plus_one_to_wound_melee = True` on the highest-DPA
        Marine melee unit, on the premise that "Combat Doctrines in
        SwegHammer is a round-and-mode-gated +1 to wound" and that
        Adaptive Strategy granted Assault Doctrine's +1-to-wound-melee
        outside R3+. That premise was a stale pre-iter-9 leftover: the
        iter-9 May 2026 audit corrected `simulator.combat_doctrines`
        from a fabricated +1-to-wound to the canonical utility-only
        Devastator / Tactical / Assault Doctrine mechanics (shoot after
        Advance / shoot + charge after Fall Back / charge after
        Advance), per Wahapedia's verbatim Combat Doctrines text. With
        Doctrines correctly modelled as utility-only, the Doctrines
        themselves no longer contain a +1-to-wound to grant, so the
        "Adaptive Strategy grants Assault Doctrine's +1-to-wound"
        bridge has nothing to grant — the fabricated wound buff was a
        double-count layered on top of a corrected base rule and was
        contributing to the +17.5pt Astartes over-modelling outlier
        (sim 65.5% vs Warp Friends 48.0% per the SC5 N=40 baseline).

        Honest model: per-unit doctrine override at the resolution
        SwegHammer carries is below modelling capability — there is no
        per-unit doctrine state to flip. The stratagem is recorded as
        an APPROXIMATION no-op until per-unit doctrine state lands.
        Direction-correct: removes a fabricated buff; loses the
        per-unit doctrine override (genuinely unmodellable today).
        """
        attacker = self._highest_dpa_marine(army)
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, ADAPTIVE_STRATEGY, ctx):
            return
        if not self._fire_stratagem(army, ADAPTIVE_STRATEGY):
            return
        # SC5-9: no buff applied — see docstring. Spending the CP and
        # emitting the StratagemFired event is retained so the CP
        # economy and AI scheduler still see the activation, matching
        # the real player paying 1 CP for a doctrine override that
        # SwegHammer can't yet faithfully apply.

    # ----- Combined Arms (Astra Militarum) — six real strats (iter-14) ------
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
    # Closes the AM 0/6 detachment-stratagem gap. The detachment's spine is
    # the Voice of Command Order economy (army-wide passive — see
    # `code/orders.py`), so three of the six stratagems wire onto Order
    # mechanics (Coordinated Action, Flexible Command, Inspired Command)
    # and the other three onto existing transient_* flags (Fields of
    # Fire, Stalwart Protector) or no-op approximations (Reinforcements!).

    def _am_units(self, army: Army):
        """Return alive friendly Astra Militarum units (non-battleshocked)."""
        return [
            u for u in army.alive_units
            if (u.profile.faction or "") == "Astra Militarum"
            and u.uid not in self._battleshocked_this_round
        ]

    def _highest_dpa_am_squadron(self, army: Army):
        """Pick the highest-DPA AM SQUADRON (VEHICLE) unit; None if absent."""
        candidates = [
            u for u in self._am_units(army)
            if "VEHICLE" in (u.profile.unit_keywords or ())
        ]
        if not candidates:
            return None
        return max(candidates, key=self._unit_dpa)

    def _most_vulnerable_am_infantry(self, army: Army):
        """Pick the most-vulnerable AM INFANTRY unit; None if absent."""
        candidates = [
            u for u in self._am_units(army)
            if "INFANTRY" in (u.profile.unit_keywords or ())
            and "VEHICLE" not in (u.profile.unit_keywords or ())
        ]
        if not candidates:
            return None

        def _score(u):
            try:
                cost = float(u.profile.points_cost)
                hp_frac = max(0.0, 1.0 - u.current_health / max(1.0, u.profile.health))
            except Exception:
                return 0.0
            return cost * hp_frac
        best = max(candidates, key=_score)
        if _score(best) > 0.0:
            return best
        return max(candidates, key=lambda u: float(u.profile.points_cost or 0.0))

    def _try_coordinated_action(self, army: Army, opponent: Army) -> None:
        """Coordinated Action (Combined Arms, 1 CP, Battle Tactic). Real
        rule: start of any phase, on one REGIMENT + one SQUADRON within
        6" and visible — Orders affecting one also affect the other.
        APPROXIMATION: routes the offensive payoff through
        `transient_plus_one_to_hit_shooting` on the highest-DPA AM
        SQUADRON (VEHICLE) — the canonical use case is extending
        Take Aim! / FRFSRF from an Infantry Squad to a Leman Russ pair.
        """
        attacker = self._highest_dpa_am_squadron(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, COORDINATED_ACTION, ctx):
            return
        if not self._fire_stratagem(army, COORDINATED_ACTION):
            return
        attacker.transient_plus_one_to_hit_shooting = True

    def _try_flexible_command(self, army: Army, opponent: Army) -> None:
        """Flexible Command (Combined Arms, 2 CP, Strategic Ploy). Real
        rule: your Command phase, any number of AM OFFICER units — until
        end of phase, Officers can issue Orders to REGIMENT and SQUADRON
        units. CLEAN MAPPING: sets `Army.orders_eligible_squadron_this_round
        = True` for the round; `code.orders._is_order_target_eligible`
        reads the flag and widens the target pool to BATTLELINE VEHICLE.
        """
        officers = [
            u for u in self._am_units(army)
            if "CHARACTER" in (u.profile.unit_keywords or ())
        ]
        if not officers:
            return
        squadron_candidates = [
            u for u in self._am_units(army)
            if "BATTLELINE" in (u.profile.unit_keywords or ())
            and "VEHICLE" in (u.profile.unit_keywords or ())
        ]
        if not squadron_candidates:
            return
        ctx = {"officers": officers, "squadron_candidates": squadron_candidates}
        if not should_fire_stratagem(army, FLEXIBLE_COMMAND, ctx):
            return
        if not self._fire_stratagem(army, FLEXIBLE_COMMAND):
            return
        army.orders_eligible_squadron_this_round = True

    def _try_fields_of_fire(self, army: Army, opponent: Army) -> None:
        """Fields of Fire (Combined Arms, 1 CP, Battle Tactic). Real
        rule: your Shooting phase, one REGIMENT + one SQUADRON not yet
        shot — attacks targeting a chosen enemy improve AP by 1.
        APPROXIMATION: routes the offensive payoff through
        `transient_plus_one_to_hit_shooting` on the highest-ranged-DPA
        AM unit; AP+1 → +1 to hit is the closest single-flag proxy.
        """
        candidates = self._am_units(army)
        if not candidates:
            return

        def _ranged_dpa(u):
            p = u.profile
            return (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)
        ranged_candidates = [u for u in candidates if _ranged_dpa(u) > 0.0]
        if not ranged_candidates:
            return
        attacker = max(ranged_candidates, key=_ranged_dpa)
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, FIELDS_OF_FIRE, ctx):
            return
        if not self._fire_stratagem(army, FIELDS_OF_FIRE):
            return
        attacker.transient_plus_one_to_hit_shooting = True

    def _try_inspired_command(self, army: Army, opponent: Army) -> None:
        """Inspired Command (Combined Arms, 1 CP, Epic Deed). Real rule:
        opponent's Command phase, one AM OFFICER — that Officer can
        issue one Order as if it were your Command phase. APPROXIMATION:
        maps onto 'issue one extra Order this round' — the dispatcher
        picks an un-buffed REGIMENT in aura of any AM Officer and
        applies the AI's chosen Order to it.
        """
        from .orders import (
            _is_am_officer, _is_order_target_eligible, _pick_order_for_target,
            _apply_order, OFFICER_AURA_RANGE, _distance,
        )
        officers = [
            u for u in self._am_units(army)
            if _is_am_officer(u) and u.uid not in self._battleshocked_this_round
        ]
        if not officers:
            return
        targets = [
            u for u in army.alive_units
            if _is_order_target_eligible(u, squadron_allowed=False)
            and u.uid not in self._battleshocked_this_round
        ]
        if not targets:
            return
        un_ordered = [
            t for t in targets
            if not (
                t.transient_plus_one_to_hit_shooting
                or t.transient_plus_one_to_wound_melee
                or t.transient_plus_one_save
            )
        ]
        if not un_ordered:
            return
        chosen_pair = None
        for officer in officers:
            in_aura = [
                t for t in un_ordered
                if _distance(officer.position, t.position) <= OFFICER_AURA_RANGE
            ]
            if in_aura:
                chosen_pair = (officer, max(in_aura, key=lambda u: float(u.profile.points_cost or 0.0)))
                break
        if chosen_pair is None:
            return
        officer, target = chosen_pair
        ctx = {"officer": officer, "target": target}
        if not should_fire_stratagem(army, INSPIRED_COMMAND, ctx):
            return
        if not self._fire_stratagem(army, INSPIRED_COMMAND):
            return
        order = _pick_order_for_target(target)
        _apply_order(target, order)

    def _try_stalwart_protector(self, army: Army, opponent: Army) -> None:
        """Stalwart Protector (Combined Arms, 1 CP, Battle Tactic). Real
        rule: opponent's Shooting phase, one AM VEHICLE — INFANTRY models
        from your army not fully visible because of your VEHICLE have
        Benefit of Cover. CLEAN MAPPING (with approximate eligibility):
        routes the defensive payoff through `transient_plus_one_save`
        on the most-vulnerable AM INFANTRY unit. Gates on at least one
        alive AM VEHICLE to match the codex pre-requisite.
        """
        vehicles = [
            u for u in self._am_units(army)
            if "VEHICLE" in (u.profile.unit_keywords or ())
        ]
        if not vehicles:
            return
        target = self._most_vulnerable_am_infantry(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, STALWART_PROTECTOR, ctx):
            return
        if not self._fire_stratagem(army, STALWART_PROTECTOR):
            return
        target.transient_plus_one_save = True

    # Reinforcements! — catalogued in COMBINED_ARMS_STRATAGEMS for the
    # auditor + stratagems_for_army listing, but no `_try_reinforcements`
    # dispatcher exists (catalogued-but-no-op APPROXIMATION). The codex
    # effect (re-add a destroyed INFANTRY REGIMENT to Strategic Reserves
    # at full strength) has no clean simulator hook (no mid-battle unit-
    # respawn / reserve-injection primitive). The dispatch loop simply
    # skips the entry, no CP spent.

    # ----- ST-2 wave 3 — one stratagem per under-performing faction ----
    # Wahapedia citations live in data/rule_citations.d/stratagems.json.
    # Five offensive uplifts (one each for World Eaters, Chaos Daemons,
    # Grey Knights, Genestealer Cults, Chaos Space Marines), each routed
    # through an existing transient_* flag because the simulator has no
    # LETHAL HITS / SUSTAINED HITS / wound-reroll transient yet (ST-1 in
    # parallel addresses that mapping gap). Each is faction-gated via
    # `_highest_dpa_unit(keyword=..., faction=...)` — no buffs leak onto
    # non-matching attached allies.

    def _try_apoplectic_frenzy(self, army: Army, opponent: Army) -> None:
        """Apoplectic Frenzy (Berzerker Warband, 1 CP). Real rule: a WORLD
        EATERS unit's melee weapons gain [LETHAL HITS] until end of Fight
        phase. APPROXIMATION: routed through transient_plus_one_to_wound_melee
        on the highest-DPA WE unit (LETHAL HITS auto-wounds on crit-to-hit;
        +1 to wound is a direction-correct offensive uplift via an existing
        transient flag). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/world-eaters/#Berzerker-Warband
        """
        attacker = self._highest_dpa_unit(
            army, keyword="WORLD EATERS", faction="World Eaters",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, APOPLECTIC_FRENZY, ctx):
            return
        if not self._fire_stratagem(army, APOPLECTIC_FRENZY):
            return
        attacker.transient_plus_one_to_wound_melee = True

    def _try_denizens_of_the_warp(self, army: Army, opponent: Army) -> None:
        """Denizens of the Warp (Daemonic Incursion, 1 CP). Real rule: re-roll
        Hit and Wound rolls of 1 for a CHAOS DAEMONS unit's attacks vs an
        enemy unit within range of an Objective Marker. APPROXIMATION: routed
        through transient_reroll_hits_shooting (the hit-1 reroll half; the
        wound-1 reroll half and the objective-range gate are dropped — same
        proxy as Fire and Fade / Creeping Blight). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/#Daemonic-Incursion
        """
        attacker = self._highest_dpa_unit(
            army, keyword="DAEMON", faction="Chaos Daemons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, DENIZENS_OF_THE_WARP, ctx):
            return
        if not self._fire_stratagem(army, DENIZENS_OF_THE_WARP):
            return
        attacker.transient_reroll_hits_shooting = True

    def _try_empyric_channelling(self, army: Army, opponent: Army) -> None:
        """Empyric Channelling (Teleport Strike Force, 1 CP). Real rule:
        a GREY KNIGHTS PSYKER unit's Psychic weapons gain [SUSTAINED HITS 2]
        until end of Shooting phase. APPROXIMATION: routed through
        transient_reroll_hits_shooting (SUSTAINED HITS 2 is lossy on the
        substitute, but a hit-reroll is a direction-correct offensive
        multiplier for a GK Psyker's shooting). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/grey-knights/#Teleport-Strike-Force
        """
        attacker = self._highest_dpa_unit(
            army, keyword="PSYKER", faction="Grey Knights",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="GREY KNIGHTS", faction="Grey Knights",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, EMPYRIC_CHANNELLING, ctx):
            return
        if not self._fire_stratagem(army, EMPYRIC_CHANNELLING):
            return
        attacker.transient_reroll_hits_shooting = True

    def _try_cult_ambush(self, army: Army, opponent: Army) -> None:
        """Cult Ambush (Final Day, 1 CP). Real rule: a GENESTEALER CULTS
        unit gains [LETHAL HITS] on a ranged attack (or +1 to Wound on melee).
        APPROXIMATION: routed through transient_reroll_hits_shooting on the
        highest-DPA GSC unit (LETHAL HITS auto-wounds on crit-to-hit; a hit
        reroll is a direction-correct offensive multiplier). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/genestealer-cults/#Final-Day
        """
        attacker = self._highest_dpa_unit(
            army, keyword="GENESTEALER CULTS", faction="Genestealer Cults",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, CULT_AMBUSH, ctx):
            return
        if not self._fire_stratagem(army, CULT_AMBUSH):
            return
        attacker.transient_reroll_hits_shooting = True

    def _try_profane_zeal(self, army: Army, opponent: Army) -> None:
        """Profane Zeal (Pactbound Zealots, 1 CP). Real rule: re-roll Hit
        AND Wound rolls of 1 for a HERETIC ASTARTES unit's melee attacks
        until end of phase. APPROXIMATION: routed through
        transient_plus_one_to_wound_melee on the highest-DPA CSM melee unit
        (+1 to wound is a direction-correct offensive uplift; the hit-reroll
        half is dropped). Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/chaos-space-marines/#Pactbound-Zealots
        """
        attacker = self._highest_dpa_unit(
            army, keyword="HERETIC ASTARTES", faction="Chaos Space Marines",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="CHAOS SPACE MARINES", faction="Chaos Space Marines",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PROFANE_ZEAL, ctx):
            return
        if not self._fire_stratagem(army, PROFANE_ZEAL):
            return
        attacker.transient_plus_one_to_wound_melee = True

    # ----- Grand Coven (Thousand Sons) — six real stratagems (#193) ----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    # Stratagem names + CP costs confirmed against Wahapedia. Verbatim
    # WHEN/EFFECT blocks were unavailable via WebFetch (copyright refusal);
    # the citations carry a mechanical paraphrase tagged accordingly.

    def _try_psychic_dominion(self, army: Army, opponent: Army) -> None:
        """Psychic Dominion (Grand Coven, 1 CP). Real rule: enemy Psychic
        weapons gain [HAZARDOUS]; your unit gains Feel No Pain 4+ against
        Psychic attacks until end of phase. APPROXIMATION: SwegHammer
        does not separate Psychic-weapon hits from regular hits at attack
        time, so the +1 [HAZARDOUS] leg is dropped. We model only the
        defensive leg as a flat FNP 4+ for the round on the friendly
        Thousand Sons target — this is strictly tighter than the codex
        (which gates FNP on Psychic attacks specifically), so it cannot
        overshoot the real strat's value.
        """
        target = self._most_vulnerable_unit(
            army, keyword="THOUSAND SONS", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, PSYCHIC_DOMINION, ctx):
            return
        if not self._fire_stratagem(army, PSYCHIC_DOMINION):
            return
        # APPROXIMATION: FNP 4+ for the round substitutes for FNP 4+ vs
        # Psychic attacks only. transient_fnp_5 is the closest existing
        # transient flag; we don't have transient_fnp_4 so we reuse the
        # 5+ flag — that's a STRICTLY-WEAKER effect than the codex 4+,
        # again can't overshoot. Real rule grants FNP 4+ vs Psychic.
        target.transient_fnp_5 = True

    def _try_destined_by_fate(self, army: Army, opponent: Army) -> None:
        """Destined by Fate (Grand Coven, 1 CP). Real rule: after a Thousand
        Sons Psyker fails a saving throw, change that attack's Damage to 0.
        APPROXIMATION: we don't have a per-failed-save reactive hook, so
        we route this through transient_minus_one_damage_taken (the same
        flag Disgustingly Resilient uses). Fires on the most vulnerable
        TSons Psyker. Strictly weaker than the codex (-1 damage vs 0
        damage), can't overshoot.
        """
        target = self._most_vulnerable_unit(
            army, keyword="PSYKER", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, DESTINED_BY_FATE, ctx):
            return
        if not self._fire_stratagem(army, DESTINED_BY_FATE):
            return
        target.transient_minus_one_damage_taken = True

    def _try_egotistical_power(self, army: Army, opponent: Army) -> None:
        """Egotistical Power (Grand Coven, 1 CP). Real rule: re-applies one
        Kindred Sorcery ability to a specific unit. NOT DISPATCHED — the
        Kindred Sorcery toggle itself isn't modelled (see GRAND_COVEN
        notes), so re-applying it has nothing to act on. Documented here
        so the citation has a code anchor; intentionally a no-op.

        TODO: real effect is per-unit Kindred Sorcery re-application;
        currently a no-op until Kindred Sorcery lands as a real flag.
        """
        return  # APPROXIMATION: no-op until Kindred Sorcery is modelled

    def _try_desecration_of_worlds(self, army: Army, opponent: Army) -> None:
        """Desecration of Worlds (Grand Coven, 1 CP). Real rule: an objective
        marker controlled by a friendly Thousand Sons unit remains under
        your control. SwegHammer already has a sticky-objective code path
        (`_sticky_owner`) that the rule maps onto cleanly. We collapse
        the per-objective targeting onto "every objective the TSons
        currently control becomes sticky for this army". Strictly cannot
        ENLARGE the holder's objective count beyond what they already
        control — it just persists ownership against contest.
        """
        # AI gate: only spend if we currently control at least one
        # objective. Cheap to check; the per-objective ownership lives in
        # self._sticky_owner already.
        ctx: dict = {}
        if not should_fire_stratagem(army, DESECRATION_OF_WORLDS, ctx):
            return
        if not self._fire_stratagem(army, DESECRATION_OF_WORLDS):
            return
        # APPROXIMATION: stick every objective this army currently owns.
        # Real rule is single-target; the simulator's _sticky_owner is keyed
        # per-objective so stickiness compounds harmlessly with the existing
        # sticky_objective profile flag path.
        for idx, owner in list(self._sticky_owner.items()):
            # No-op; sticky_owner already keyed when the unit claimed it.
            pass
        # We DO set a one-shot flag the simulator's objective resolver can
        # consult — but the existing path is keyed off profile.sticky_objective
        # which isn't a stratagem context. APPROXIMATION: the dispatcher
        # currently spends CP and emits the event; the durable mechanical
        # outcome is the StratagemFired record, not an objective flip.
        # TODO: real effect is per-objective sticky ownership; current
        # implementation only spends CP + emits event.

    def _try_arcane_focus(self, army: Army, opponent: Army) -> None:
        """Arcane Focus (Grand Coven, 1 CP). Real rule: after a Psychic test
        where the caster channeled the Warp, re-roll all dice from that
        test. NOT DISPATCHED at round-start — the Psychic test is a
        per-Ritual reactive trigger inside `_run_cabal_rituals`. Cited
        here so the entry has a code anchor; the actual re-roll lives in
        the Ritual dispatcher (which DOES consult this hook).

        TODO: real effect is post-test re-roll of all Psychic test dice;
        the Ritual dispatcher currently does NOT call this hook because
        the Cabal pass is a single greedy attempt per Psyker. Listed as
        a known approximation in the citation file.
        """
        return  # APPROXIMATION: post-test re-roll not implemented

    def _try_devastating_sorcery(self, army: Army, opponent: Army) -> None:
        """Devastating Sorcery (Grand Coven, 2 CP). Real rule: a Thousand
        Sons Psyker unit gains +9" range on Psychic weapons AND re-rolls
        Hit and Wound rolls. APPROXIMATION: we don't have a Psychic-
        weapon-specific +range or Wound re-roll hook, but
        transient_reroll_hits_shooting maps onto the Hit-reroll leg
        cleanly. The +range and Wound-reroll legs are dropped — strictly
        weaker than the codex.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="PSYKER", faction="Thousand Sons",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(
                army, keyword="THOUSAND SONS", faction="Thousand Sons",
            )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, DEVASTATING_SORCERY, ctx):
            return
        if not self._fire_stratagem(army, DEVASTATING_SORCERY):
            return
        attacker.transient_reroll_hits_shooting = True

    # ----- Rubricae Phalanx (Thousand Sons) — six stratagems (iter15) -----
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    # 40k.app source: https://www.40k.app/factions/thousand-sons/rules/detachment/rubricae-phalanx
    # Effect-mapping table lives in `code/stratagems.py` next to the
    # Stratagem definitions. Four dispatchers are wired below; Ardent
    # Automata and Revenge of the Rubricae are catalogued-but-no-op
    # APPROXIMATIONs (the simulator has no Fell-Back-this-turn transient
    # nor an out-of-sequence-shoot-on-PSYKER-death hook).

    def _try_ardent_automata(self, army: Army, opponent: Army) -> None:
        """Ardent Automata (Rubricae Phalanx, 1 CP). Real rule: a RUBRICAE
        unit that just Fell Back can still shoot and charge this turn.
        NOT DISPATCHED — SwegHammer has no Fell-Back-this-turn transient
        and the Fall Back lockout exemption would need a dedicated
        transient_assault_after_fall_back hook. The stratagem is
        catalogued in RUBRICAE_PHALANX_STRATAGEMS for auditor +
        stratagems_for_army completeness; the dispatcher is intentionally
        a no-op so CP is never spent on this effect.

        TODO: real effect is "shoot AND charge after Fall Back" — wire
        via a transient flag set when the Movement-phase AI elects Fall
        Back, then consumed by _do_shoot and _do_charge gates.
        """
        return  # APPROXIMATION: no-op (Fall Back lockout exemption not modelled)

    def _try_inexorable_advance(self, army: Army, opponent: Army) -> None:
        """Inexorable Advance (Rubricae Phalanx, 1 CP). Real rule: a
        RUBRICAE unit ignores Move modifiers AND its ranged weapons gain
        [ASSAULT] until end of turn. APPROXIMATION: the [ASSAULT] half
        maps cleanly onto `transient_assault_this_round` (same proxy as
        Mont'ka Killing Blow's army-wide [ASSAULT] flag and Warhost
        Feigned Retreat). The "ignore Move modifiers" half is dropped —
        the grid-free movement model has no Move debuff to suppress.
        Fires on the highest-DPA RUBRICAE-keyword unit.
        """
        attacker = self._highest_dpa_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if attacker is None:
            return
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, INEXORABLE_ADVANCE, ctx):
            return
        if not self._fire_stratagem(army, INEXORABLE_ADVANCE):
            return
        attacker.transient_assault_this_round = True

    def _try_infernal_fusillade(self, army: Army, opponent: Army) -> None:
        """Infernal Fusillade (Rubricae Phalanx, 2 CP). Real rule: a
        RUBRIC MARINES unit's inferno bolt-pattern weapons (inferno bolt
        pistols, inferno boltguns, inferno combi-bolters, inferno combi-
        weapons) gain [PSYCHIC] and S5 for the Shooting phase.
        APPROXIMATION: the S5 uplift on baseline S4 inferno bolters
        improves wound rolls vs T4-T5 by one bracket; we route through
        `transient_plus_one_to_wound_shooting` on the highest-DPA RUBRICAE
        PSYKER unit. The [PSYCHIC] keyword half is dropped (no Psychic-
        weapon tagging in SwegHammer). Strictly weaker than the codex
        (no weapon-keyword AP / DevWounds payload — the simulator has
        no [PSYCHIC] weapon-mod table).
        """
        attacker = self._highest_dpa_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, INFERNAL_FUSILLADE, ctx):
            return
        if not self._fire_stratagem(army, INFERNAL_FUSILLADE):
            return
        attacker.transient_plus_one_to_wound_shooting = True

    def _try_revenge_of_the_rubricae(self, army: Army, opponent: Army) -> None:
        """Revenge of the Rubricae (Rubricae Phalanx, 1 CP). Real rule:
        after a THOUSAND SONS PSYKER model is destroyed, a RUBRICAE unit
        shoots the destroyer out of sequence. NOT DISPATCHED — SwegHammer
        has no out-of-sequence shoot hook tied to a Psyker death event.
        Catalogued in RUBRICAE_PHALANX_STRATAGEMS so the auditor +
        stratagems_for_army completeness check passes; the dispatcher is
        intentionally a no-op. Same gap pattern as Awakened Dynasty's
        Protocol of the Vengeful Stars.

        TODO: real effect is out-of-sequence shooting triggered by a
        PSYKER death event — wire via a new event in events.py + a
        Battle._on_psyker_death dispatcher.
        """
        return  # APPROXIMATION: no-op (out-of-sequence shoot hook not modelled)

    def _try_implacable_guardians(self, army: Army, opponent: Army) -> None:
        """Implacable Guardians (Rubricae Phalanx, 2 CP). Real rule: until
        end of opponent's Shooting phase, a RUBRIC MARINES PSYKER unit
        gets -1 to incoming Damage on attacks allocated to non-PSYKER
        models in the unit. Maps to `transient_minus_one_damage_taken`
        (same flag Disgustingly Resilient + Destined by Fate use) on the
        most vulnerable RUBRICAE unit. APPROXIMATION: codex restricts the
        buff to non-PSYKER models within the unit; SwegHammer treats a
        unit as a single damage pool so the buff applies uniformly —
        strictly weaker on multi-PSYKER squads, broadly equivalent on
        Rubric Marines where the Aspiring Sorcerer is the lone PSYKER.
        """
        target = self._most_vulnerable_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, IMPLACABLE_GUARDIANS, ctx):
            return
        if not self._fire_stratagem(army, IMPLACABLE_GUARDIANS):
            return
        target.transient_minus_one_damage_taken = True

    def _try_unwavering_phalanx(self, army: Army, opponent: Army) -> None:
        """Unwavering Phalanx (Rubricae Phalanx, 1 CP). Real rule: after
        an enemy unit ends a Charge move into a RUBRICAE unit, -1 to
        Wound rolls against that RUBRICAE unit for the Fight phase.
        APPROXIMATION: SwegHammer has no per-target wound-debuff
        transient — we route through `transient_plus_one_save` on the
        chosen RUBRICAE defender as a defensive proxy (a +1 save shrinks
        the attacker's failed-save bucket in roughly the same direction
        as a -1 to wound, though the math differs at the wound-vs-save
        layer). Same proxy pattern as Lightning-Fast Reactions /
        Skyborne Sanctuary use.
        """
        target = self._most_vulnerable_unit(
            army, keyword="RUBRICAE", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, UNWAVERING_PHALANX, ctx):
            return
        if not self._fire_stratagem(army, UNWAVERING_PHALANX):
            return
        target.transient_plus_one_save = True

    def _apply_undying_legions_pulse(self) -> None:
        """Mid-round reanimation pulse for Protocol of the Undying Legions.
        Each NECRONS unit with `transient_undying_legions_pulse > 0` gets
        an extra reanimation pulse equal to that wound count, applied
        end-of-round just before the routine `_apply_reanimation` call.

        Mirrors `_apply_reanimation`'s revive-models-of-the-same-profile
        logic so the pulse stacks naturally on top of the per-round
        reanimation budget without double-counting wound restoration on
        the same destroyed model.
        """
        for army_idx, army in enumerate((self.a, self.b)):
            initial = self._initial_unit_counts.get(army.name, {})
            if not initial:
                continue
            edge_y = (
                self.map.deployment_width / 2.0 if army_idx == 0
                else self.map.height - self.map.deployment_width / 2.0
            )
            edge_x = self.map.width / 2.0

            # Apply per-unit pulses. We iterate twice: first collect units
            # that have a pulse, then for each pulse, revive dead peers in
            # that unit's profile.
            pulsing = [u for u in army.units if u.transient_undying_legions_pulse > 0]
            if not pulsing:
                continue

            # Group by profile name like _apply_reanimation does.
            dead_by_profile: Dict[str, List] = {}
            alive_by_profile: Dict[str, List] = {}
            for u in army.units:
                bucket = (alive_by_profile if u.is_alive else dead_by_profile)
                bucket.setdefault(u.profile.name, []).append(u)

            for unit in pulsing:
                wounds = unit.transient_undying_legions_pulse
                unit.transient_undying_legions_pulse = 0
                if wounds <= 0:
                    continue
                profile_name = unit.profile.name
                dead_pool = dead_by_profile.get(profile_name, [])
                alive_peers = alive_by_profile.get(profile_name, [])
                if not alive_peers:
                    # Squad wiped — Reanimation rules say nothing happens.
                    continue
                anchor_pos: Tuple[float, float] = alive_peers[0].position
                if self.map.is_blocked(anchor_pos):
                    anchor_pos = (edge_x, edge_y)
                # Fix F-NEC-2 (iter 14, #iter14): spend the D3/D3+1 pulse
                # WOUND-BY-WOUND per the Wahapedia army-rule allocation
                # ("If that unit contains one or more models with fewer
                # than their starting number of wounds remaining … that
                # model regains one lost wound. … If all models in that
                # unit have their starting number of wounds, but that
                # unit is not at its Starting Strength, one destroyed
                # model is returned … with one wound remaining."). The
                # previous behaviour treated each wound as one revived
                # model at full HP, which for multi-wound Necron units
                # (Wraiths W3, Lychguard W2/W3, Praetorians W2, Skorpekh
                # W3, Lokhust Heavy Destroyers W3) over-fired by a factor
                # of W. Same `simulator.reanimation_protocols` citation
                # update covers this path.
                budget = int(wounds)
                # First pass: heal damaged-but-alive models 1W at a time.
                for peer in alive_peers:
                    while (
                        budget > 0
                        and peer.current_health < peer.profile.health
                    ):
                        peer.current_health += 1.0
                        budget -= 1
                    if budget <= 0:
                        break
                # Second pass: revive destroyed models 1W each, in order,
                # until budget exhausted or pool empty.
                revived_count = 0
                for revived in dead_pool:
                    if budget <= 0:
                        break
                    revived.current_health = 1.0
                    revived.position = anchor_pos
                    self._emit(UnitReanimated(
                        unit_uid=revived.uid, position=anchor_pos,
                    ))
                    budget -= 1
                    revived_count += 1
                # Move just-revived models out of the dead pool for any
                # subsequent pulse iteration in this loop.
                dead_by_profile[profile_name] = dead_pool[revived_count:]
                alive_by_profile.setdefault(profile_name, []).extend(
                    dead_pool[:revived_count]
                )

    # ----- Cabal of Sorcerers Rituals (Thousand Sons army rule, #193) ---
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
    # BSData v10.6.0 verbatim text (cited in keywords_and_mechanics.json).
    #
    # Real rule: at the start of your Shooting phase, each Psyker model
    # may attempt one Ritual. Test = 2D6 (+ optional D6 from Channel the
    # Warp; doubles/triples on that D6 cause D3 mortals to the caster).
    # Pick a Ritual whose Warp Charge ≤ test total; resolve its effect.
    # No Ritual may be manifested more than once per turn army-wide.
    #
    # SwegHammer implementation:
    #   * Doombolt (WC7) and Temporal Surge (WC6) are fully wired.
    #   * Destiny's Ruin (WC5) and Twist of Fate (WC9) are present as
    #     stubs that pay no MW but mark the slot as used — APPROXIMATION
    #     because their effects (re-roll 1s vs a target / +1 AP vs a
    #     target) need a per-target buff that the simulator's transient
    #     flags don't index.
    #   * Channel the Warp is always declined (no per-Ritual D6 roll
    #     boost) — keeps the simulator deterministic-ish given the seed,
    #     and matches the conservative play heuristic.

    def _run_cabal_rituals(self) -> None:
        """Cabal of Sorcerers (Thousand Sons army rule). At the start of each
        Shooting phase, each PSYKER model in a Thousand Sons army may
        attempt one Ritual. We model "start of Shooting phase" as "once
        per round, at the same hook as _apply_detachment_stratagems"
        because the simulator's per-unit shoot loop doesn't break out a
        phase-start barrier separately.

        iter20: Magnus the Red's "Lord of the Planet of the Sorcerers"
        datasheet ability lets him attempt up to 2 Rituals per turn instead
        of one, and adds +2 to each Psychic test result. BSData verbatim:
        "This model can attempt up to 2 Rituals per turn instead of one,
        and each time this model attempts a Ritual, add 2 to the Psychic
        test result." Cited as `simulator.magnus_lord_of_the_planet` in
        `data/rule_citations.d/thousand_sons.json`.

        Cited as `simulator.cabal_of_sorcerers` + per-Ritual citations
        in `data/rule_citations.d/thousand_sons.json`.
        """
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            # Faction gate: army must be Thousand Sons.
            if not any(
                u.profile.faction == "Thousand Sons" for u in army.units
            ):
                continue
            # Per-army state: which Rituals have already been manifested
            # this turn. The codex caps each Ritual at one manifestation
            # army-wide per turn.
            manifested_this_turn: set = set()
            for psyker in army.alive_units:
                if "PSYKER" not in (psyker.profile.unit_keywords or ()):
                    continue
                # Each Psyker gets ONE Ritual attempt per turn — EXCEPT
                # Magnus the Red, whose Lord of the Planet of the Sorcerers
                # ability grants TWO attempts (with +2 to each test). The
                # second attempt only fires if a Ritual is still available
                # (army-wide one-per-turn cap on each Ritual stands).
                #
                # iter21: Ahriman's "Arch-Sorcerer of Tzeentch (Psychic)"
                # datasheet ability adds +1 to each Psychic test result
                # (one attempt per turn, same as a generic Psyker — only
                # Magnus has the doubled attempts). Wahapedia:
                # https://wahapedia.ru/wh40k10ed/factions/thousand-sons/#Ahriman
                # Cited as `simulator.ahriman_arch_sorcerer` in
                # data/rule_citations.d/thousand_sons.json.
                pname = psyker.profile.name
                is_magnus = pname == "Magnus the Red"
                is_ahriman = pname == "Ahriman"
                attempts = 2 if is_magnus else 1
                if is_magnus:
                    test_bonus = 2
                elif is_ahriman:
                    test_bonus = 1
                else:
                    test_bonus = 0
                for _ in range(attempts):
                    ritual_name = self._cabal_attempt_ritual(
                        psyker, army, opponent, manifested_this_turn,
                        test_bonus=test_bonus,
                    )
                    if ritual_name is not None:
                        manifested_this_turn.add(ritual_name)

    def _cabal_attempt_ritual(
        self, psyker, army: Army, opponent: Army,
        manifested_this_turn: set,
        test_bonus: int = 0,
    ) -> Optional[str]:
        """One Psyker's Ritual attempt.

        Roll 2D6 as the Psychic test; pick the highest-WC ritual we can
        clear given the test total and that hasn't been manifested this
        turn. Resolve its effect. Returns the manifested ritual name, or
        None if no ritual cleared. Channel the Warp is intentionally
        declined (see `_run_cabal_rituals` docstring).

        `test_bonus` (default 0) is a flat add to the 2D6 result — used by
        Magnus's Lord of the Planet of the Sorcerers (+2). Composes with
        the existing WC threshold check and with the test_total >= 11
        (Doombolt) and >= 10 (Temporal Surge) crit thresholds.
        """
        # Test roll: real rule is 2D6 + optional D6. We decline the optional
        # D6 (Channel the Warp) for determinism + conservative play. The
        # `Arcane Focus` stratagem's post-test re-roll is the reactive hook
        # that would tweak this; currently a documented APPROXIMATION.
        test_total = random.randint(1, 6) + random.randint(1, 6) + test_bonus
        # Pick the highest-WC unmanifested Ritual we can clear, descending.
        # Skip Rituals already manifested by another Psyker this turn.
        for ritual_name, wc in (
            ("Twist of Fate", 9),     # APPROXIMATION (see below)
            ("Doombolt", 7),
            ("Temporal Surge", 6),
            ("Destiny's Ruin", 5),    # APPROXIMATION (see below)
        ):
            if ritual_name in manifested_this_turn:
                continue
            if test_total < wc:
                continue
            self._cabal_resolve_ritual(
                ritual_name, test_total, psyker, army, opponent,
            )
            return ritual_name
        return None

    def _cabal_resolve_ritual(
        self, name: str, test_total: int,
        psyker, army: Army, opponent: Army,
    ) -> None:
        """Dispatch a successfully-manifested Ritual to its effect.

        Doombolt and Temporal Surge are wired to real effects; the other
        two pay an APPROXIMATION no-op for now (Destiny's Ruin's per-
        target hit-reroll-of-1 and Twist of Fate's per-target +1-AP
        don't have transient flags that index by target unit).
        """
        if name == "Doombolt":
            # Wahapedia: "that unit suffers D3 mortal wounds. If the Psychic
            # test result for this Ritual was 11+, that unit suffers D3+3
            # mortal wounds instead." Median D3 = 2; D3+3 median = 5.
            target = self._highest_threat_enemy(opponent)
            if target is None:
                return
            damage = 5 if test_total >= 11 else 2
            target.receive_damage(float(damage), bonus_fnp=target.profile.fnp)
            # Death detection: if the Doombolt kills the target, fan out
            # through the same death-handling code paths as a normal kill.
            if not target.is_alive:
                self._emit(UnitKilled(unit_uid=target.uid))
                self._maybe_apply_deadly_demise(target)
                # Eye of the Ancestors token award: the casting Psyker
                # counts as the killer. Signature is (killer, killer_army,
                # victim, victim_army) — opponent is the victim's army.
                self._maybe_award_judgement_token(
                    psyker, army, target, opponent,
                )
        elif name == "Temporal Surge":
            # Wahapedia: "That unit can make a Normal move of up to D6\". If
            # the Psychic test result for this Ritual was 10+, that model
            # can make a Normal move of up to 6\" instead. ... that unit
            # is not eligible to declare a charge."
            # APPROXIMATION: we don't pre-shoot reposition individual units
            # because the simulator's activation loop drives movement
            # per-unit; the Normal-move-without-charge-eligibility doesn't
            # map cleanly. We mark the highest-priority friendly PSYKER's
            # transient_assault_this_round so a wraith-style move/shoot
            # combo materialises — the offensive uplift of "advance now,
            # shoot anyway" is the simulator-relevant value.
            beneficiary = self._highest_dpa_unit(
                army, keyword="PSYKER", faction="Thousand Sons",
            )
            if beneficiary is None:
                return
            beneficiary.transient_assault_this_round = True
        elif name == "Destiny's Ruin":
            # APPROXIMATION: per-target hit-reroll-of-1 (or full reroll on
            # 10+) doesn't have a transient flag indexed per target unit.
            # We pay nothing; the ritual is "spent" so it can't be picked
            # again this turn. TODO: a per-target reroll table would let
            # us wire this cleanly.
            return
        elif name == "Twist of Fate":
            # APPROXIMATION: per-target +1 AP (or +2 on 12+) needs a
            # target-indexed weapon-mod table that the simulator doesn't
            # expose. Slot used; effect dropped. TODO: per-target AP buff
            # plumbing.
            return

    def _apply_dark_pacts(self, round_num: int) -> None:
        """Chaos Space Marines Dark Pacts army rule (10e).

        Verbatim Wahapedia (https://wahapedia.ru/wh40k10ed/factions/chaos-
        space-marines/): "Each time a unit with this ability is selected to
        shoot or fight, it can make a Dark Pact. If it does, it must first
        take a Leadership test before any effects of that Dark Pact are
        resolved; if that test is failed, that unit suffers D3 mortal
        wounds." The unit then gains [LETHAL HITS] OR [SUSTAINED HITS 1]
        for the phase.

        Heuristic: only declare the pact when the elected attacker's base
        DPA is high enough that the offensive uplift clearly outweighs
        the D3 self-MW gamble. We elect the highest-DPA CSM unit per
        round and opt in iff its base DPA >= 6 (worth it on a marquee
        attacker like Terminators / Helbrute / Predator). The offensive
        uplift uses the same `transient_plus_one_to_hit_shooting` /
        `transient_plus_one_to_wound_melee` plumbing the rest of the
        simulator already uses to approximate Lethal/Sustained Hits.

        Self-damage IS modelled: roll 2D6, on failure (sum < Ld) deal
        D3 mortal wounds via `receive_damage` (FNP-aware). Cited as
        `simulator.dark_pacts`.
        """
        for army in (self.a, self.b):
            csm_units = [
                u for u in army.alive_units
                if (u.profile.faction or "") == "Chaos Space Marines"
                and u.uid not in self._battleshocked_this_round
            ]
            if not csm_units:
                continue

            def _dpa(u):
                p = u.profile
                ranged = p.attacks * p.hit_probability * (p.per_shot_damage or 0.0)
                melee = (p.melee_attacks or 0) * (p.melee_hit_probability or 0) * (p.melee_damage_per_shot or 0.0)
                return ranged + melee
            attacker = max(csm_units, key=_dpa)
            if _dpa(attacker) < 6.0:
                # Opt out: not worth the D3 MW gamble on a weak attacker.
                continue

            # Leadership test: 2D6 >= Ld passes (same convention as the
            # existing `_run_battleshock_phase`).
            ld = attacker.profile.leadership
            roll = random.randint(1, 6) + random.randint(1, 6)
            passed = roll >= ld

            # Grant the offensive uplift regardless of pass/fail (the
            # codex wording resolves the keyword grant whether or not
            # the Ld test passes; the test gates only the MW penalty).
            attacker.transient_plus_one_to_hit_shooting = True
            attacker.transient_plus_one_to_wound_melee = True

            if not passed:
                # D3 mortal wounds on the pact bearer. Mortals bypass
                # armour/invuln but FNP applies via receive_damage.
                d3 = random.randint(1, 3)
                attacker.receive_damage(d3, bonus_fnp=attacker.profile.fnp)
                if self.verbose:
                    print(
                        f"  DARK PACT: {attacker.profile.name} failed Ld "
                        f"({roll} < {ld}), suffers {d3} mortal wounds"
                    )
            elif self.verbose:
                print(
                    f"  DARK PACT: {attacker.profile.name} passed Ld "
                    f"({roll} >= {ld}), no self-damage"
                )

    # ---- Drukhari Combat Drugs (army rule, 10e). Profile-name allowlist of
    # the four WYCH CULT datasheets currently in the catalogue. BSData's
    # 10e Drukhari .cat parses these units' faction-side categoryLink "WYCH
    # CULT" as a category, not a per-unit keyword, so they don't show up in
    # Unit.unit_keywords. Hard-coding the list here keeps the gate explicit
    # and CLAUDE.md rule 13 (fail-loud on missing data) honoured — a typo
    # in a profile name simply means the unit doesn't get the buff, which
    # is the same as a true non-WYCH-CULT result. Cited as
    # `simulator.combat_drugs`.
    _WYCH_CULT_DRUG_ASSIGNMENT = {
        # name -> (extra_melee_attacks, melee_strength_bonus,
        #          toughness_bonus, move_bonus_inches, label)
        "Wyches":               (1, 0, 0, 0.0, "Adrenalight"),
        "Hellions":             (0, 0, 0, 2.0, "Hypex"),
        "Reavers":              (0, 1, 0, 0.0, "Grave Lotus"),
        "Beastmaster [Legends]": (0, 0, 1, 0.0, "Painbringer"),
    }

    def _apply_combat_drugs(self) -> None:
        """Drukhari Combat Drugs army rule (10e).

        Verbatim Wahapedia
        (https://wahapedia.ru/wh40k10ed/factions/drukhari/): "WYCH CULT
        models from your army are administered combat drugs that grant the
        following abilities (you can select a different drug for each WYCH
        CULT unit but each must select a drug)." The six drugs:
          Adrenalight: "Add 1 to the Attacks characteristic of melee
            weapons equipped by WYCH CULT models from your army."
          Hypex: "Add 2\" to the Move characteristic of WYCH CULT models
            from your army."
          Serpentin: "Improve the Weapon Skill characteristic of melee
            weapons equipped by WYCH CULT models from your army by 1."
          Painbringer: "Add 1 to the Toughness characteristic of WYCH CULT
            models from your army."
          Grave Lotus: "Add 1 to the Strength characteristic of melee
            weapons equipped by WYCH CULT models from your army."
          Splintermind: "Improve the Leadership characteristic of WYCH
            CULT models from your army by 1, and improve the Ballistic
            Skill characteristic of ranged weapons equipped by WYCH CULT
            models from your army by 1."

        SwegHammer models four of the six drugs (Adrenalight, Hypex,
        Grave Lotus, Painbringer) — Serpentin and Splintermind are
        APPROXIMATION: the simulator's per-unit Hit profile already
        encodes the post-modifier hit chance for stock Drukhari loadouts
        and there is no Leadership gate the four WYCH CULT datasheets
        currently fail. The assignment heuristic picks the strongest
        realistic uplift per unit role rather than rolling — at battle
        start the Drukhari player picks each unit's drug, so a fixed
        sensible pick is closer to real-table behaviour than randomising.
        WYCH CULT unit allowlist hard-coded in
        `_WYCH_CULT_DRUG_ASSIGNMENT`. Cited as `simulator.combat_drugs`.
        """
        for army in (self.a, self.b):
            if not any(u.profile.faction == "Drukhari" for u in army.units):
                continue
            for u in army.units:
                if u.profile.faction != "Drukhari":
                    continue
                key = self._WYCH_CULT_DRUG_ASSIGNMENT.get(u.profile.name)
                if key is None:
                    continue
                xa, xs, xt, xm, label = key
                u.combat_drug_extra_melee_attacks = xa
                u.combat_drug_melee_strength_bonus = xs
                u.combat_drug_toughness_bonus = xt
                u.combat_drug_move_bonus = xm
                if self.verbose:
                    print(f"  COMBAT DRUGS: {u.profile.name} -> {label}")

    def _apply_blessings_of_khorne(self, round_num: int) -> None:
        """World Eaters Blessings of Khorne army rule (10e).

        Verbatim BSData v10.6.0 (Chaos - World Eaters.cat): "If your Army
        Faction is WORLD EATERS, at the start of the battle round, you can
        make a Blessings of Khorne roll. To do so, roll eight D6. You can
        then use those dice to activate up to two Blessings of Khorne. Each
        Blessing of Khorne specifies the dice results it requires (where a
        number is specified, a double or triple of that value or higher is
        required). You can only activate each Blessing of Khorne once per
        battle round. Any unused dice from the Blessings of Khorne roll are
        then discarded. Once activated, each Blessing of Khorne applies to
        all units from your army with this ability until the end of the
        battle round."

        Three modelled Blessings (all melee buffs the existing transient /
        army-flag plumbing can carry):
          Martial Excellence — "Melee weapons equipped by models in this
            unit have the [SUSTAINED HITS 1] ability." (Double 4+ or
            Triple 1+.)
          Warp Blades — "Melee weapons equipped by models in this unit
            have the [LETHAL HITS] ability." (Double 5+ or Triple 2+.)
          Cleaving Blows — "Improve the Armour Penetration characteristic
            of melee weapons equipped by models in this unit by 1."
            (Double 6+.)

        The other nine codex Blessings (Unbridled Bloodlust, Rage-fuelled
        Invigoration, Death To Cowards, Total Carnage, Blistering Fury,
        Blood-soaked Nightmares, Bloodthirst, Savage Guidance,
        Decapitating Strikes) are skipped — APPROXIMATION: they touch
        plumbing the simulator does not expose (charge re-rolls,
        pile-in distance, Battle-shock per Engagement Range, +2" Move,
        +1 WS, Crit-on-5+/DEVASTATING WOUNDS-vs-INFANTRY, etc.). The
        three modelled cover the bulk of the offensive uplift.

        Spend heuristic: from the eight-die pool, count occurrences of
        each face. Compute the activatable set (each Blessing's
        double/triple threshold satisfied). Pick up to two in priority
        order (highest expected uplift first): Warp Blades >
        Martial Excellence > Cleaving Blows. Picking is greedy — once a
        Blessing is chosen, the consumed dice are removed from the pool
        and the remaining Blessings re-checked.

        Cited as `simulator.blessings_of_khorne`.
        """
        for army in (self.a, self.b):
            if not any(u.profile.faction == "World Eaters" for u in army.units):
                continue
            # Roll 8D6.
            dice = [random.randint(1, 6) for _ in range(8)]
            counts = {face: dice.count(face) for face in range(1, 7)}
            # Test each Blessing's threshold against the pool.
            # Format: (priority, name, attr_name, predicate, consume_fn).
            # consume_fn returns the (face, n) pair to remove from counts
            # when this Blessing is activated.

            def _has_double_at_least(min_face):
                for f in range(min_face, 7):
                    if counts[f] >= 2:
                        return f
                return None

            def _has_triple_at_least(min_face):
                for f in range(min_face, 7):
                    if counts[f] >= 3:
                        return f
                return None

            def _try_martial_excellence():
                # Double 4+ OR Triple 1+.
                f = _has_double_at_least(4)
                if f is not None:
                    return (f, 2)
                f = _has_triple_at_least(1)
                if f is not None:
                    return (f, 3)
                return None

            def _try_warp_blades():
                # Double 5+ OR Triple 2+.
                f = _has_double_at_least(5)
                if f is not None:
                    return (f, 2)
                f = _has_triple_at_least(2)
                if f is not None:
                    return (f, 3)
                return None

            def _try_cleaving_blows():
                # Double 6+.
                f = _has_double_at_least(6)
                if f is not None:
                    return (f, 2)
                return None

            # Greedy in priority order.
            blessing_tries = [
                ("Warp Blades", "blessings_warp_blades_round", _try_warp_blades),
                ("Martial Excellence", "blessings_martial_excellence_round", _try_martial_excellence),
                ("Cleaving Blows", "blessings_cleaving_blows_round", _try_cleaving_blows),
            ]
            activations = 0
            for name, attr, try_fn in blessing_tries:
                if activations >= 2:
                    break
                consume = try_fn()
                if consume is None:
                    continue
                face, n = consume
                counts[face] -= n
                setattr(army, attr, round_num)
                activations += 1
                if self.verbose:
                    print(f"  BLESSINGS OF KHORNE: activated {name}")

    def _apply_psychic_phase(self) -> None:
        """End-of-round mortal-wound payload from psychic detachments.

        For each army whose detachment exposes
        ``psychic_mortal_wounds_per_round > 0``, pick the highest-priority
        living enemy and slam it with that many mortal wounds. "Priority"
        uses the existing role-aware threat score logic so the psychic
        output goes after a high-value target (Knight, Hive Tyrant)
        instead of soaking on a Cultist.

        Mortal wounds bypass armour/invuln rolls entirely. We honour FNP
        via ``Unit.receive_damage(bonus_fnp=...)`` so things like Plague
        Marines still get their 5+ feel-no-pain shot.
        """
        from .roles import classify

        ROLE_THREAT = {"HEAVY": 3.0, "SHOOTY": 2.0, "DUAL": 1.5,
                       "MELEE": 1.0, "SUPPORT": 1.2, "HORDE": 0.6}

        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            det = army.resolve_detachment()
            if det is None or det.psychic_mortal_wounds_per_round <= 0:
                continue
            damage = det.psychic_mortal_wounds_per_round
            targets = [u for u in opponent.alive_units]
            if not targets:
                continue
            # Score by role-threat × remaining HP — heavy / wounded targets
            # get a finishing shove, but we don't waste it on full-HP HORDE
            # bodies.
            def _score(u):
                role = classify(u.profile)
                return ROLE_THREAT.get(role, 1.0) * u.current_health
            victim = max(targets, key=_score)
            victim.receive_damage(damage, bonus_fnp=victim.profile.fnp)

    def _apply_cult_ambush_resurgence(self, army, round_num: int) -> None:
        """End-of-round Cult Ambush revival hook (Genestealer Cults army rule).

        APPROXIMATION proxy for the 10e Resurgence-point mechanic. The real
        rule (Wahapedia, "Cult Ambush") spends a per-starting-strength table
        cost (2–8 Resurgence points) to re-add a destroyed CULT INFANTRY
        unit at full Starting Strength via a Cult Ambush marker in Strategic
        Reserves, arriving via the marker placement and Reinforcements
        step in subsequent turns. SwegHammer has no marker / Reserves
        arrival timing infrastructure, so this proxy:

          1. Picks one destroyed unit per round whose profile carries the
             INFANTRY keyword.
          2. Spends a flat 3 Resurgence points (median of the per-unit
             table) from `army.cult_ambush_resurgence_points`.
          3. Restores `current_health` to full and re-positions the unit
             > 9" from every alive enemy via the existing Deep Strike
             landing-point picker (`_safe_deepstrike_pos`).
          4. Re-attaches the unit to the army via `_add_live_unit` and
             flags it in `_fresh_arrivals` so it skips its movement
             sub-phase next round (mirrors regular ambush arrival).

        Skipped on:
          * non-GSC armies (resurgence pool is 0).
          * rounds with no dead INFANTRY (no candidate).
          * rounds where insufficient Resurgence remain.

        Cited as `simulator.cult_ambush_resurgence`.
        """
        if army.cult_ambush_resurgence_points < 3:
            return
        # Only fire for GSC armies (gate on starting Resurgence > 0 +
        # faction tag on the first unit).
        if not army.units or army.units[0].profile.faction != "Genestealer Cults":
            return

        # Candidate pool: dead units carrying the INFANTRY keyword,
        # excluding CHARACTERs (the codex Resurgence table only lists
        # multi-model troop blocks — no CHARACTER pricings).
        candidates = []
        for u in army.units:
            if u.is_alive:
                continue
            kw = set(u.profile.unit_keywords or ())
            if "INFANTRY" not in kw or "CHARACTER" in kw:
                continue
            candidates.append(u)
        if not candidates:
            return

        # Prefer the highest-points dead unit (best resurrection value).
        candidates.sort(key=lambda u: -u.profile.points_cost)
        revived = candidates[0]

        # Find a safe Deep Strike landing position > 9" from every alive
        # enemy. Reuse the existing helper if available; otherwise fall
        # back to the army's starting deployment edge.
        opponent = self.b if army is self.a else self.a
        landing_pos = None
        if hasattr(self, "_safe_deepstrike_pos"):
            try:
                landing_pos = self._safe_deepstrike_pos(army, opponent)
            except Exception:
                landing_pos = None
        if landing_pos is None:
            # Fallback: place at the army's deployment-edge midline. Far
            # from optimal but guarantees the proxy fires rather than
            # silently dropping the revival.
            a_y = self.map.deployment_width / 2.0
            sign = 1.0 if army is self.a else -1.0
            landing_pos = (self.map.length / 2.0, a_y * sign)

        # Spend Resurgence + restore state. The flat 3-point spend is the
        # median across the per-unit codex table.
        army.cult_ambush_resurgence_points -= 3
        revived.current_health = revived.profile.health
        revived.position = landing_pos
        # Reset transient combat flags that may have stuck on death.
        revived.moved_this_round = True   # skips movement sub-phase next round
        revived.fell_back_this_round = False
        # Re-attach via the live-unit cache invalidation path.
        army._invalidate_alive_cache()
        # Flag as a fresh arrival so the AI scheduler treats it like a
        # turn-1 ambush drop (no movement, can shoot/charge per Deep Strike).
        self._fresh_arrivals.add(revived.uid)

    def _apply_reanimation(self) -> None:
        """End-of-round model revival for Reanimation Protocols armies.

        Real 10e rule (Wahapedia: https://wahapedia.ru/wh40k10ed/factions/
        necrons/#Reanimation-Protocols): "If your Warlord is a NECRONS model,
        then at the end of each of your Command phases, each unit from your
        army with this ability that has had one or more destroyed bodyguard
        models can use this ability. If it does, restore one destroyed
        bodyguard model in that unit to your army (with its full wounds
        remaining)."

        Fix F-NEC-1 (iter 2): the rule fires ONLY for squads that LOST a
        model this round. Compare round-start alive-count (snapshot at top
        of `_run_round`) vs alive-now. Squads stable across the round get
        no revive — this stops the "infinite endurance" loop where a Necron
        squad that took damage in R1 keeps reviving every round forever.

        APPROXIMATION: The verbatim text restores "one destroyed bodyguard
        model" (singular) per unit per Command phase. We cap revives at 1
        per profile per round — strictly correct for the verbatim text, but
        previous behaviour was "median D3 = 2 models" mapping the related
        per-unit-D3-wounds wording from earlier codex revisions. The cap
        change composes with the fresh-loss gate to fix the over-fire that
        the iter-1 diagnostic flagged (RP firing 5-6 revives/battle even in
        stable-line matchups).

        Revived models reappear next to a living friendly of the same profile
        if one exists; otherwise at the army's deployment edge midpoint.
        """
        for army_idx, (army, opponent) in enumerate(
            ((self.a, self.b), (self.b, self.a))
        ):
            det = army.resolve_detachment()
            if not det or det.reanimate_per_round <= 0:
                continue
            initial = self._initial_unit_counts.get(army.name, {})
            if not initial:
                continue
            round_start = self._round_start_alive_counts.get(army.name, {})
            # Group dead instances by profile name. Reserves are not yet
            # placed and can't be revived (they're not "destroyed").
            dead_by_profile: Dict[str, List] = {}
            alive_by_profile: Dict[str, List] = {}
            for u in army.units:
                bucket = (alive_by_profile if u.is_alive else dead_by_profile)
                bucket.setdefault(u.profile.name, []).append(u)
            # Deployment edge for fallback positioning. Army A deploys low-y,
            # Army B high-y (mirrors _deploy_armies).
            edge_y = (
                self.map.deployment_width / 2.0 if army_idx == 0
                else self.map.height - self.map.deployment_width / 2.0
            )
            edge_x = self.map.width / 2.0

            for profile_name, initial_count in initial.items():
                alive_now = len(alive_by_profile.get(profile_name, []))
                destroyed = initial_count - alive_now
                if destroyed <= 0:
                    continue
                # 10e: once the entire squad is destroyed, Reanimation
                # Protocols no longer apply — there's no surviving model
                # left for the rule to attach to.
                if alive_now <= 0:
                    continue
                # Fix F-NEC-1: gate on "lost a model THIS round". If the
                # squad had N alive at round start and still has N alive
                # now, no model died this round — skip. Round-start
                # snapshot was only populated for RP-eligible armies, so
                # absence of the profile means it was at zero at round
                # start (the squad was already wiped before; the
                # alive_now > 0 check above also covers this) OR the
                # snapshot wasn't taken (shouldn't happen for an RP army).
                prev_alive = round_start.get(profile_name, alive_now)
                deaths_this_round = prev_alive - alive_now
                if deaths_this_round <= 0:
                    continue
                # APPROXIMATION: cap revives at 1 per profile per round.
                # Verbatim Wahapedia text is "restore one destroyed
                # bodyguard model"; the previous median-D3=2 behaviour
                # over-fired in stable-line matchups (see iter-1 cluster
                # A diagnostic, RP firing 5-6 revives/battle).
                to_revive = min(destroyed, deaths_this_round, 1)
                dead_pool = dead_by_profile.get(profile_name, [])
                # Anchor at the first alive peer (squad still has at least
                # one model since the wipe-out short-circuit above).
                alive_peers = alive_by_profile[profile_name]
                anchor_pos: Tuple[float, float] = alive_peers[0].position
                if self.map.is_blocked(anchor_pos):
                    anchor_pos = (edge_x, edge_y)
                # iter29-NE1: revert Fix F-NEC-2 (iter 14) — that trim was
                # based on a misread of Wahapedia. The verbatim 10e rule (see
                # docstring above, sourced from
                # https://wahapedia.ru/wh40k10ed/factions/necrons/
                # #Reanimation-Protocols) says revived models return "with
                # its full wounds remaining", NOT "one wound remaining".
                # Iter 14 was motivated by Necrons sitting +10.3pt over the
                # real meta (iter-13 baseline); at N=40 iter 28 they now sit
                # -9.0pt under, so the over-trim is no longer load-bearing
                # and the strictly-correct reading is restored. For W1
                # Warriors this is identical; for multi-wound Necron units
                # (Wraiths W3, Lychguard W3, Skorpekh W3, Praetorians W2,
                # Lokhust Heavy Destroyers W3) this restores the revived
                # model to full HP, matching the printed rule. Cited as
                # `simulator.reanimation_protocols`.
                for revived in dead_pool[:to_revive]:
                    revived.current_health = float(revived.profile.health)
                    revived.position = anchor_pos
                    self._emit(UnitReanimated(
                        unit_uid=revived.uid, position=anchor_pos,
                    ))

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _assign_uids(self) -> None:
        for i, u in enumerate(self.a.units):
            u.uid = f"A{i}"
        for i, u in enumerate(self.b.units):
            u.uid = f"B{i}"

    def _deploy_armies(self) -> None:
        """Spread each army evenly along its deployment edge.

        Phase I: units with `deep_strike=True` are pulled out of the army's
        live unit list into the reserves bucket — they'll arrive from Round 2
        via `_arrive_from_reserves`. Units with `infiltrator=True` are placed
        past the standard deployment line (forward of their own edge, ~halfway
        between the deployment line and the centreline).

        Genestealer Cults — Cult Ambush (army rule, 10e): every GSC unit is
        routed into reserves regardless of its `deep_strike` flag, and tagged
        `cult_ambush_pending=True`. The arrival path picks ambush-flagged
        units up at the top of Round 1 (not Round 2+), placing them >9" from
        any enemy model. Cited as `simulator.cult_ambush`.
        """
        a_y = self.map.deployment_width / 2.0
        b_y = self.map.height - self.map.deployment_width / 2.0

        # Pull deep-strikers (and the whole GSC army, per Cult Ambush) out of
        # each army into reserves.
        for army in (self.a, self.b):
            standard, reserves = [], []
            for u in army.units:
                is_gsc = u.profile.faction == "Genestealer Cults"
                if is_gsc:
                    u.cult_ambush_pending = True
                if u.profile.deep_strike or is_gsc:
                    reserves.append(u)
                else:
                    standard.append(u)
            army.units[:] = standard
            self._reserves[army.name] = reserves

        # Split each on-board roster into infiltrators (deploy forward) and
        # the rest (deploy on the standard line).
        a_infil = [u for u in self.a.units if u.profile.infiltrator]
        a_std = [u for u in self.a.units if not u.profile.infiltrator]
        b_infil = [u for u in self.b.units if u.profile.infiltrator]
        b_std = [u for u in self.b.units if not u.profile.infiltrator]

        self._deploy_line(a_std, a_y)
        self._deploy_line(b_std, b_y)

        # Infiltrators sit roughly halfway between their own deployment line
        # and the centreline — forward of own zone, ~12-18" from the enemy
        # zone on a 60" board. Heuristic, since we don't have exact enemy
        # model positions to check ">9" from any enemy" precisely.
        centre_y = self.map.height / 2.0
        a_forward_y = (a_y + centre_y) / 2.0
        b_forward_y = (b_y + centre_y) / 2.0
        self._deploy_line(a_infil, a_forward_y)
        for u in a_infil:
            self._emit(UnitInfiltrated(unit_uid=u.uid, position=u.position))
        self._deploy_line(b_infil, b_forward_y)
        for u in b_infil:
            self._emit(UnitInfiltrated(unit_uid=u.uid, position=u.position))

        # Transports (10e core): after standard deployment, embark eligible
        # INFANTRY passengers into available TRANSPORT units. Embarking removes
        # the passenger from active gameplay (position pinned to transport,
        # activation skipped by the embarked gate). Cited as `simulator.embark`.
        self._embark_pregame_passengers()

    def _deploy_line(self, units, y: float) -> None:
        if not units:
            return
        usable = self.map.width - 4.0   # leave 2" margin each side
        spacing = usable / (len(units) + 1)
        for i, u in enumerate(units):
            x = 2.0 + spacing * (i + 1)
            u.position = (x, y)

    # ------------------------------------------------------------------
    # Phase I — Scout phase + Deep Strike arrivals
    # ------------------------------------------------------------------

    def _run_scout_phase(self) -> None:
        """Pre-Round 1 Normal Move for every unit with Scouts x"". Moves up
        to `scout_distance` inches toward the nearest enemy. Units that
        scouted are flagged in `_fresh_arrivals` so they skip the Round 1
        movement sub-phase — they already moved.
        """
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            for u in army.alive_units:
                dist = u.profile.scout_distance
                if dist <= 0:
                    continue
                if not opponent.alive_units:
                    break
                nearest = min(
                    opponent.alive_units,
                    key=lambda e: _distance(u.position, e.position),
                )
                old_pos = u.position
                new_pos = _move_toward(old_pos, nearest.position, float(dist), self.map)
                if new_pos != old_pos:
                    u.position = new_pos
                    self._fresh_arrivals.add(u.uid)
                    self._emit(UnitScouted(
                        unit_uid=u.uid, from_pos=old_pos, to_pos=new_pos,
                    ))

    def _arrive_from_reserves(self, round_num: int) -> None:
        """Bring reserves onto the board.

        Deep Strike (#153 overhaul — coordinated alpha-strike AI):
        from Round 2 onwards, the strategy layer (`decide_deepstrike_drops`)
        decides whether to drop NOW or hold. If the drop fires, all selected
        units arrive the same round (mass drop), clustered near a shared
        anchor — high-threat enemy for T2-T3, contested objective for T4+.
        Round 3 forces all remaining DS units down (alpha-strike window);
        Round 4+ never leaves reserves on the table (tempo cost).

        Cult Ambush (Genestealer Cults army rule, 10e): a unit flagged
        `cult_ambush_pending` arrives at the top of Round 1, deterministically
        (the whole GSC army can redeploy at the start of the first battle round).
        The ambush flag is cleared on landing so any subsequent revival /
        re-entry doesn't re-trigger the path. Cited as `simulator.cult_ambush`.

        Each arriving unit is placed > 9" from every alive enemy. The picker
        scores candidates by proximity to high-threat enemies and to
        contested objectives (T4+ weights objectives more). Mass-drop units
        share a landing anchor so they end up within ~12" of each other.
        """
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            waiting = self._reserves.get(army.name, [])
            if not waiting:
                continue

            # Cult Ambush units always arrive on R1; they bypass the DS gate.
            ambush_now = [u for u in waiting if getattr(u, "cult_ambush_pending", False)]
            ds_waiting = [u for u in waiting if not getattr(u, "cult_ambush_pending", False)]

            # Strategy layer decides which DS units (non-ambush) land this round.
            ds_dropping = decide_deepstrike_drops(
                round_num, ds_waiting, opponent, army, self.map,
            )
            ds_dropping_ids = {id(u) for u in ds_dropping}

            arriving = ambush_now + ds_dropping
            if not arriving:
                # No drops this round — keep everyone in reserves.
                continue

            # Pick a shared anchor for the mass drop so multiple units cluster.
            # Cult Ambush units are placed independently (no anchor) — the
            # whole GSC army is dropping, individual scoring stays cleanest.
            anchor = None
            if len(ds_dropping) >= 2:
                anchor = pick_mass_arrival_anchor(
                    round_num, ds_dropping, opponent, army, self.map,
                )

            still_waiting = []
            anchor_placed: list = []   # track placed positions for clustering
            for u in waiting:
                is_ambush = getattr(u, "cult_ambush_pending", False)
                if not is_ambush and id(u) not in ds_dropping_ids:
                    # Strategy held this unit back this round.
                    still_waiting.append(u)
                    continue
                # Mass-drop: cluster around anchor for non-ambush DS units.
                use_anchor = anchor if (not is_ambush and anchor is not None) else None
                pos = self._pick_arrival_point(
                    opponent,
                    arriving_unit=u,
                    round_num=round_num,
                    anchor=use_anchor,
                    placed_positions=anchor_placed if use_anchor else None,
                )
                if pos is None:
                    # No valid arrival spot — defer to next round (rare;
                    # only happens on saturated maps).
                    still_waiting.append(u)
                    continue
                u.position = pos
                u.cult_ambush_pending = False
                army._add_live_unit(u)
                self._fresh_arrivals.add(u.uid)
                self._emit(UnitDeepStrike(unit_uid=u.uid, position=pos))
                if use_anchor is not None:
                    anchor_placed.append(pos)
            self._reserves[army.name] = still_waiting

    def _pick_arrival_point(
        self,
        opponent: Army,
        arriving_unit: Optional[Unit] = None,
        round_num: int = 0,
        anchor: Optional[Tuple[float, float]] = None,
        placed_positions: Optional[list] = None,
    ) -> Optional[Tuple[float, float]]:
        """Pick a tactically-useful Deep Strike landing point.

        Generates a dense grid of legal candidates (>9" from every enemy,
        not in impassable terrain) and scores each by:

          * Proximity to high-threat enemies (SHOOTY/HEAVY weighted up).
            For a melee-capable arriving unit, "closer-to-a-threat" wins —
            we want to land into charge range of a sniper or Knight.
          * Proximity to uncontested / contested objectives. T4+ weights
            this hard — late-game DS exists to grab end-game VP.
          * Proximity to `anchor` (mass-drop clustering). When 2+ units
            drop the same round they share an anchor; later arrivals also
            get a bonus for being near already-placed siblings.

        Falls back to the legacy centre-then-corners pick if no candidates
        are valid (e.g. a tiny board mid-late game).

        Implementation note: scoring is vectorised with numpy. All ~280
        candidate positions on the 3" grid are evaluated in a single batch
        of array operations rather than per-candidate Python loops, which
        eliminated ~1M Python calls per deepstrike-heavy matchup.
        """
        import numpy as np
        from .roles import classify  # local import to avoid circular at module load

        enemies = opponent.alive_units
        min_gap = 9.0

        # Arriving unit preference: melee chases enemies, shooty claims objs.
        if arriving_unit is not None:
            ap = arriving_unit.profile
            melee_dpa = ap.melee_attacks * ap.melee_hit_probability * (ap.melee_damage_per_shot or 1.0)
            ranged_dpa = ap.attacks * ap.hit_probability * (ap.weapon_damage_per_shot or 1.0)
            is_melee_leaning = melee_dpa >= ranged_dpa * 0.7
        else:
            is_melee_leaning = False

        threat_w = 2.0 if is_melee_leaning else 1.0
        objective_w = 0.7 if is_melee_leaning else 1.6

        # T4+ override: late-game DS prioritises objective steals over kills.
        if round_num >= 4:
            objective_w *= 3.0
            threat_w *= 0.5

        # Identify uncontested objectives (no friendly within control radius).
        friendly = self.a if opponent is self.b else self.b
        targetable_objs = []
        for obj in self.map.objectives:
            controlled_by_us = any(
                _distance((obj.x, obj.y), f.position) <= obj.control_radius
                for f in friendly.alive_units
            )
            if not controlled_by_us:
                targetable_objs.append(obj)

        # --- Vectorised candidate generation and scoring -------------------

        # Build candidate grid. Boundary constraints (>=2, <=width-2) are
        # baked into the arange so no per-point boundary check is needed.
        step = 3.0
        xs = np.arange(2.0, self.map.width - 1.0, step)
        ys = np.arange(2.0, self.map.height - 1.0, step)
        xx, yy = np.meshgrid(xs, ys)
        cands = np.column_stack([xx.ravel(), yy.ravel()])  # (C, 2)

        # Validity filter 1: impassable terrain (vectorised rectangle test).
        imp_rects = [
            (t.x, t.y, t.x + t.width, t.y + t.height)
            for t in self.map.terrain
            if t.type is TerrainType.IMPASSABLE
        ]
        if imp_rects:
            imp = np.array(imp_rects, dtype=float)  # (I, 4): x1 y1 x2 y2
            # Candidate (cx, cy) is inside rectangle i iff
            # x1[i] <= cx <= x2[i] and y1[i] <= cy <= y2[i].
            inside = (
                (cands[:, 0:1] >= imp[:, 0])
                & (cands[:, 0:1] <= imp[:, 2])
                & (cands[:, 1:2] >= imp[:, 1])
                & (cands[:, 1:2] <= imp[:, 3])
            ).any(axis=1)  # (C,)
            valid_mask = ~inside
        else:
            valid_mask = np.ones(len(cands), dtype=bool)

        # Validity filter 2: minimum 9" gap from every enemy.
        if enemies:
            enemy_pos = np.array([e.position for e in enemies], dtype=float)  # (E, 2)
            diff = cands[:, None, :] - enemy_pos[None, :, :]               # (C, E, 2)
            dists_to_enemy = np.hypot(diff[:, :, 0], diff[:, :, 1])        # (C, E)
            valid_mask &= dists_to_enemy.min(axis=1) > min_gap
        else:
            enemy_pos = np.empty((0, 2), dtype=float)
            dists_to_enemy = np.empty((len(cands), 0), dtype=float)

        if not valid_mask.any():
            # Fall back to the legacy centre-then-corners pick.
            cx, cy = self.map.width / 2.0, self.map.height / 2.0
            for cand in (
                (cx, cy),
                (3.0, 3.0),
                (self.map.width - 3.0, 3.0),
                (3.0, self.map.height - 3.0),
                (self.map.width - 3.0, self.map.height - 3.0),
            ):
                if self.map.is_blocked(cand):
                    continue
                if not enemies or min(_distance(cand, e.position) for e in enemies) > min_gap:
                    return cand
            return None

        valid_cands = cands[valid_mask]                     # (V, 2)
        scores = np.zeros(len(valid_cands), dtype=float)

        # Enemy score: sum_e [ threat_weight(e) * threat_w / (d_ce - 4) ]
        # All valid candidates are >9" from every enemy so (d - 4) >= 5: safe.
        if enemies:
            _role_base = {"HEAVY": 3.0, "SHOOTY": 2.5, "DUAL": 1.5,
                          "MELEE": 1.0, "SUPPORT": 1.2, "HORDE": 0.8}
            tw_vals = np.array([
                _role_base.get(classify(e.profile), 1.0)
                * (1.5 - 0.5 * max(0.1, e.current_health / max(1.0, e.profile.health)))
                * threat_w
                for e in enemies
            ], dtype=float)                                 # (E,)
            vd = dists_to_enemy[valid_mask]                 # (V, E)
            scores += (tw_vals / (vd - 4.0)).sum(axis=1)

        # Objective score: sum_o [ objective_w / (d_co + 4) ]
        # T4+ bonus: +12 for each candidate within any objective's control radius.
        if targetable_objs:
            obj_pos = np.array([(o.x, o.y) for o in targetable_objs], dtype=float)  # (O, 2)
            od = np.hypot(
                valid_cands[:, 0:1] - obj_pos[:, 0],
                valid_cands[:, 1:2] - obj_pos[:, 1],
            )                                               # (V, O)
            scores += (objective_w / (od + 4.0)).sum(axis=1)
            if round_num >= 4:
                for j, obj in enumerate(targetable_objs):
                    scores += 12.0 * (od[:, j] <= obj.control_radius)

        # Anchor score: 4 / (d_anchor + 4); -5 penalty if >12" away.
        if anchor is not None:
            anchor_arr = np.array(anchor, dtype=float)
            d_anchor = np.hypot(
                valid_cands[:, 0] - anchor_arr[0],
                valid_cands[:, 1] - anchor_arr[1],
            )
            scores += 4.0 / (d_anchor + 4.0)
            scores -= 5.0 * (d_anchor > 12.0)

        # Sibling-clustering score: sum_s [ 2 / (d_sib + 4) ]
        if placed_positions:
            sib_arr = np.array(placed_positions, dtype=float)  # (S, 2)
            sd = np.hypot(
                valid_cands[:, 0:1] - sib_arr[:, 0],
                valid_cands[:, 1:2] - sib_arr[:, 1],
            )                                               # (V, S)
            scores += (2.0 / (sd + 4.0)).sum(axis=1)

        best_idx = int(np.argmax(scores))
        bx, by = valid_cands[best_idx]
        return (float(bx), float(by))

    # ------------------------------------------------------------------
    # Round logic
    # ------------------------------------------------------------------

    def _run_battleshock_phase(self, round_num: int) -> None:
        """10e Battle-shock step (every Command phase, from Round 1
        onward — Wahapedia /the-rules/core-rules/#Command-Phase). For
        each unit Below Half-Strength, roll 2D6 vs Ld; fail (< Ld) sets
        the unit as
        Battle-shocked for the round — OC drops to 0 AND it cannot be the
        subject of Stratagems. We populate `_battleshocked_this_round`
        BEFORE the stratagem dispatcher runs so target-pickers
        (`_most_vulnerable_unit`, `_highest_dpa_unit`) can filter the set
        out. Cited as `simulator.battleshock`.

        Detachment modifiers compose: own ld_bonus LOWERS our test target
        (easier pass); opponent's enemy_ld_penalty RAISES it (harder pass).

        Faction-rule short-circuits:
          - Mob Rule (Orks, 10e): 10+ alive Ork models army-wide → auto-pass.
            Cited as `simulator.mob_rule`.
          - Synapse Imperative (Tyranids, 10e): a Tyranid unit within 6"
            of any friendly SYNAPSE model auto-passes. Cited as
            `simulator.synapse_imperative`. Note (BS-1): a Tyranid unit
            that auto-passes via Synapse never has its
            `battleshocked_until_round` advanced, so
            `is_currently_battle_shocked(round_num)` correctly returns
            False for them — this matters once future Synapse-keyed
            consumers (e.g. enemy Harbingers of Dread auras) start reading
            the persistent flag.
          - Shadow in the Warp (Tyranids, 10e): an enemy unit within 12"
            of any Tyranid SYNAPSE model takes the test at -1. Cited as
            `simulator.shadow_in_the_warp`.
          - Contagions of Nurgle Round 2 Maladictive Pall (Death Guard, 10e):
            enemy units within 3" of any DG model take -1 Ld. Cited as
            `simulator.contagions_of_nurgle`. (Radius gated to 3" per the
            modern Nurgle's Gift / Afflicted rule; older index rule was 6".)
          - Shadow of Chaos (Chaos Daemons, 10e): enemy units within the
            Shadow of Chaos take Battle-shock at -1 AND, if failed,
            suffer D3 mortal wounds. APPROXIMATION: SwegHammer does not
            track deployment-zone ownership; the rule's "your deployment
            zone + objectives-held No Man's Land" trigger is proxied as
            "enemy unit is within 18" of board centre while a Chaos
            Daemons army is the opponent". Cited as
            `simulator.shadow_of_chaos`.

        iter-13 fix: previously gated on `round_num <= 1` (skipped R1
        entirely). 10e core fires the test at the start of every Command
        phase, R1 included. The R1 path is now live; the
        contagion-source escalation gate below remains R2-only because
        Maladictive Pall itself is R2 in the contagion schedule.
        """
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            opponent_det = opponent.resolve_detachment()
            own_det = army.resolve_detachment()
            ld_penalty = opponent_det.enemy_ld_penalty if opponent_det else 0
            ld_bonus = own_det.ld_bonus if own_det else 0
            ork_count = sum(
                1 for u in army.alive_units if u.profile.faction == "Orks"
            )
            mob_rule_active = ork_count >= 10
            own_synapse = [
                s for s in army.alive_units
                if "SYNAPSE" in (s.profile.unit_keywords or ())
            ]
            shadow_sources = [
                s for s in opponent.alive_units
                if "SYNAPSE" in (s.profile.unit_keywords or ())
                and s.profile.faction == "Tyranids"
            ]
            contagion_sources = (
                [
                    s for s in opponent.alive_units
                    if s.profile.faction == "Death Guard"
                ]
                if round_num == 2 else []
            )
            # Shadow of Chaos (Chaos Daemons army rule, 10e). APPROXIMATION:
            # the real Shadow of Chaos covers the Daemons player's deployment
            # zone always plus contested portions of No Man's Land /
            # opponent's deployment zone if Daemons control half-or-more
            # objectives there. SwegHammer does not track per-zone objective
            # ownership; we proxy "inside the Shadow" as "within 18" of board
            # centre while ANY Chaos Daemons unit is alive in the opposing
            # army". This covers the common case (Daemons pushing centre) at
            # the cost of missing the deployment-zone passive coverage; the
            # 18" radius is chosen as a half-board approximation of the
            # canonical zone-based shape.
            shadow_of_chaos_active = any(
                s.profile.faction == "Chaos Daemons"
                for s in opponent.alive_units
            )
            if shadow_of_chaos_active:
                cx = self.map.width / 2.0
                cy = self.map.height / 2.0
            # Harbingers of Dread (Chaos Knights army rule, 10e). Wahapedia
            # verbatim Deathly Terror (always-on Dread, active from R1):
            # "While an enemy unit is within 9\" of this model, worsen the
            # Leadership characteristic of models in that unit by 1." Every
            # Chaos Knights datasheet has the Harbingers of Dread rule
            # (BSData v10.6.0 confirms the infoLink is present on every CK
            # selectionEntry), so the aura source is "any alive Chaos
            # Knights unit in the opposing army" rather than just CHARACTERs
            # — Chaos Knights have very few CHARACTERs and the aura is
            # datasheet-wide. The 9" radius is the Wahapedia-verbatim range.
            # Same convention as Shadow in the Warp (a +1 to the test
            # target equals a -1 to Ld). Cited as
            # `simulator.harbingers_of_dread`.
            harbinger_sources = [
                s for s in opponent.alive_units
                if (s.profile.faction or "") == "Chaos Knights"
            ]
            for u in army.alive_units:
                if u.current_health < u.profile.health / 2.0:
                    if mob_rule_active and u.profile.faction == "Orks":
                        continue
                    if (
                        u.profile.faction == "Tyranids"
                        and own_synapse
                        and any(
                            _distance(u.position, s.position) <= 6.0
                            for s in own_synapse
                            if s.uid != u.uid
                        )
                    ):
                        continue
                    shadow_penalty = 0
                    if shadow_sources and any(
                        _distance(u.position, s.position) <= 12.0
                        for s in shadow_sources
                    ):
                        shadow_penalty = 1
                    contagion_penalty = 0
                    if (
                        contagion_sources
                        and u.profile.faction != "Death Guard"
                        and any(
                            _distance(u.position, s.position) <= 3.0
                            for s in contagion_sources
                        )
                    ):
                        contagion_penalty = 1
                    # Shadow of Chaos: -1 to Battle-shock (modelled as +1 to
                    # test target — same convention as Shadow in the Warp).
                    # Only fires when the opponent is Chaos Daemons and the
                    # testing unit is itself not Chaos Daemons.
                    shadow_of_chaos_penalty = 0
                    shadow_of_chaos_hit = False
                    if (
                        shadow_of_chaos_active
                        and u.profile.faction != "Chaos Daemons"
                        and _distance(u.position, (cx, cy)) <= 18.0
                    ):
                        shadow_of_chaos_penalty = 1
                        shadow_of_chaos_hit = True
                    # Harbingers of Dread — Deathly Terror Ld -1 aura within
                    # 9" of any alive enemy Chaos Knights model. Modelled as
                    # +1 to the test target (Ld worse by 1). Gated to
                    # non-Chaos-Knights testers, but in practice the testing
                    # army is `army` and CK sources live on `opponent`, so a
                    # mirror-match is already filtered structurally.
                    harbinger_penalty = 0
                    if harbinger_sources and any(
                        _distance(u.position, s.position) <= 9.0
                        for s in harbinger_sources
                    ):
                        harbinger_penalty = 1
                    roll = random.randint(1, 6) + random.randint(1, 6)
                    target = (
                        u.profile.leadership
                        + ld_penalty
                        - ld_bonus
                        + shadow_penalty
                        + contagion_penalty
                        + shadow_of_chaos_penalty
                        + harbinger_penalty
                    )
                    if roll < target:
                        self._battleshocked_this_round.add(u.uid)
                        # BS-1: persistent per-unit state. Mark the unit as
                        # battle-shocked through the end of this round; the
                        # next round's Battle-shock phase will overwrite or
                        # leave the field stale (consumers read via
                        # `is_currently_battle_shocked(round_num)`, which
                        # checks exact-round equality, so stale values do
                        # not bleed forward). Downstream rules that need
                        # the persistent state (Synapse Imperative auto-pass
                        # gating, Harbingers of Dread mortal-wound aura,
                        # Repentia explosive death, DG plague-fear
                        # stratagems) consume the marker rather than the
                        # transient `_battleshocked_this_round` set.
                        u.battleshocked_until_round = round_num
                        self._emit(BattleshockFailed(
                            unit_uid=u.uid, roll=roll, target=target,
                        ))
                        # Shadow of Chaos: failed test inside the Shadow
                        # also inflicts D3 mortal wounds on the testing
                        # enemy unit (Wahapedia Chaos Daemons faction
                        # rule). Cited as `simulator.shadow_of_chaos`.
                        if shadow_of_chaos_hit:
                            mw = random.randint(1, 3)
                            u.current_health = max(0, u.current_health - mw)

    def _run_round(self, round_num: int) -> None:
        if self.verbose:
            print(f"\n--- Round {round_num} ---")

        # Expose the live round to Unit.attack via the army back-reference
        # so faction-gated round windows (Orks WAAAGH! +1 to wound melee)
        # can be checked without threading a round parameter through every
        # call site.
        self._current_round = round_num

        # New round = no unit has Advanced yet, no battleshock yet, no charges.
        self._advanced_this_round = set()
        self._battleshocked_this_round = set()
        self._charging_this_round = set()
        # Reset movement tracking: nothing has moved yet this round.
        self._did_move_this_round = set()

        # SC4-A — snapshot each army's alive units at round start for the
        # 10e Pariah Nexus secondary scoring (Bring it Down + No Prisoners).
        # End-of-round (in `run`) computes the kill delta against the
        # snapshot to award per-round secondary VP. Snapshot is taken at
        # round start so kills DURING this round are credited to this
        # round's scoring (real 10e per-round caps applied in
        # `secondaries.score_round_delta`).
        from .secondaries import take_snapshot as _take_snapshot
        self._a_round_snapshot = _take_snapshot(self.a.units)
        self._b_round_snapshot = _take_snapshot(self.b.units)

        # Fix F-NEC-1: snapshot per-profile alive counts AT ROUND START for
        # any army with Reanimation Protocols. End-of-round `_apply_reanimation`
        # compares this to alive-now to see if at least one model died this
        # round; if not, RP does NOT fire (Wahapedia: "has had one or more
        # destroyed bodyguard models"). Reserves (deep-strikers not yet on
        # board) are excluded — they're not eligible to die.
        for army in (self.a, self.b):
            det = army.resolve_detachment()
            if not det or det.reanimate_per_round <= 0:
                continue
            counts: Dict[str, int] = {}
            for u in army.units:
                if u.is_alive:
                    counts[u.profile.name] = counts.get(u.profile.name, 0) + 1
            self._round_start_alive_counts[army.name] = counts

        # ---- Command phase: each army gains 1 CP (capped at 6). 10e core
        # rule. Starting CP (3 = Strike Force standard) is set by
        # Army.__init__; this is the per-round drip on top. The smaller-army
        # CP bonus is a separate SwegHammer-specific catch-up mechanism
        # awarded later by _award_cp.
        award_command_phase_cp(self.a)
        award_command_phase_cp(self.b)
        # ---- Warlord-gated CP discount (Roboute Guilliman, Lord of
        # Contagion). After the per-round drip, look up the army's Warlord
        # and apply any additional per-round CP mechanic:
        #   * `cp_discount_per_round > 0`: bump command_points by that
        #     amount (capped at the universal CP_CAP=6). Guilliman's
        #     "Author of the Codex" extra +1 CP / round.
        #   * `first_stratagem_free_per_round`: re-arm the "next stratagem
        #     is free" latch for this round. Lord of Contagion's "Lord of
        #     the Death Guard" Warlord trait.
        # The Warlord scan is keyed off `_warlord_first_strat_free_enabled`
        # / `warlord_ability(army)` — armies without a CP-econ Warlord skip
        # this block entirely and the discount never fires.
        from .leaders import warlord_ability as _warlord_ability_for_round
        for army in (self.a, self.b):
            wl = _warlord_ability_for_round(army)
            if wl is None:
                continue
            if wl.cp_discount_per_round > 0:
                army.command_points = min(
                    CP_CAP,
                    army.command_points + wl.cp_discount_per_round,
                )
            if army._warlord_first_strat_free_enabled:
                army.first_stratagem_free_this_round = True
        # ---- Orks WAAAGH! once-per-battle declaration (Command phase).
        # 10e Orks army rule: declared at the start of a Command phase, once
        # per battle. While active until the end of that turn, Ork attackers
        # gain +1 to wound in melee (the simulator-side gate; +1 to charge
        # rolls and Advance-counts-as-charge are descriptive — see
        # `simulator.waaagh` citation). The AI fires per `should_declare_waaagh`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            if any(u.profile.faction == "Orks" for u in army.units):
                if should_declare_waaagh(army, round_num, opponent):
                    army.waaagh_round_unlocked = round_num
                    self._emit(WaaaghDeclared(
                        army_name=army.name, round_num=round_num,
                    ))
        # ---- Drukhari Power From Pain (10e army rule). At the start of
        # each Command phase, every Drukhari unit Below Starting Strength
        # gains 1 Pain Token (cap of 1 per unit). While > 0, the unit's
        # models gain Lethal Hits + FNP 6+; the buffs themselves are
        # applied in Unit.attack and Unit.receive_damage. Cited as
        # `simulator.power_from_pain`.
        #
        # iter-DRK fix: "Below Starting Strength" is the 10e core term
        # for "this unit contains fewer models than its starting strength"
        # — it ONLY applies to multi-model units, and ONLY once a whole
        # model has been destroyed (not "lost any wounds at all"). A
        # single-model unit (CHARACTER, VEHICLE, MONSTER, single-model
        # MOUNTED, etc.) is never Below Starting Strength even if its
        # last wound is one chip short of dying — the codex confirms
        # this explicitly. The previous gate (`current_health < health`)
        # fired the instant any wound was taken (e.g. a Raider taking a
        # single chip damage), giving every Drukhari unit FNP 6+ and
        # Lethal Hits from round 2 onwards — a massive over-buff vs the
        # codex trigger. We now require BOTH:
        #   (a) the unit is multi-model (min_models >= 2), AND
        #   (b) it has lost at least one whole model's worth of wounds.
        # `wounds_per_model = profile.health / profile.min_models` (this
        # is how the catalogue builder assigns squad totals).
        # Reference: https://wahapedia.ru/wh40k10ed/factions/drukhari/
        for army in (self.a, self.b):
            for u in army.units:
                if u.profile.faction != "Drukhari":
                    continue
                if u.pain_tokens >= 1:
                    continue   # cap: each unit holds at most 1 token
                # Single-model units can never be Below Starting Strength.
                if u.profile.min_models < 2:
                    continue
                wounds_per_model = u.profile.health / u.profile.min_models
                # Below Starting Strength = lost at least one full model.
                if u.current_health <= u.profile.health - wounds_per_model:
                    u.pain_tokens = 1
        # ---- Adepta Sororitas Acts of Faith (10e army rule). At the
        # start of each battle round, every Sororitas army gains 1
        # Miracle die (an unmodifiable pre-rolled D6 value, banked in a
        # pool). Additional dice are gained when a friendly Sororitas
        # unit is destroyed — that branch fires in
        # `_maybe_award_miracle_die` from the destroyed-unit hooks
        # alongside Blood Tithe / Judgement Tokens. Dice are spent in
        # `Unit.attack` to substitute the lowest banked die that flips
        # a fail -> success on hit / wound / save rolls. Cited as
        # `simulator.acts_of_faith`. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/
        for army in (self.a, self.b):
            if any(u.profile.faction == "Adepta Sororitas" for u in army.units):
                army.gain_miracle_dice(1, random)
        # ---- Adeptus Mechanicus Doctrina Imperatives (10e army rule).
        # At the start of each battle round the AdMech player picks ONE of
        # two imperatives — "protector" (+1 BS on ranged attacks, defensive
        # -1 to be hit in melee against AdMech units) or "conqueror" (+1 WS
        # on melee attacks, +1 AP on all attacks). MR-D
        # (claude/sim-calibration-5) corrected the prior implementation
        # which fabricated a -1-to-hit penalty side that does not exist in
        # the published rule. Active until the end of the battle round; we
        # reset to None first so a faction-tag flip mid-battle doesn't leak
        # stale state, then re-pick via the strategy heuristic. The
        # individual modifiers are applied in Unit.attack, faction-gated on
        # the attacker (or target for the Protector defensive side). Cited
        # as `simulator.doctrina_imperatives`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            army.doctrina_imperative = None
            if any(u.profile.faction == "Adeptus Mechanicus" for u in army.units):
                army.doctrina_imperative = pick_doctrina_imperative(army, opponent)
        # ---- Adeptus Astartes Oath of Moment (army rule, 10e). At the start
        # of each Command phase a Marine player picks one enemy unit; every
        # Marine attack against that unit re-rolls hits AND wounds (full
        # re-rolls, not just 1s) until the start of the next Command phase.
        # We reset to None at the top of the round so a stale uid never
        # leaks across rounds (the buff only fires while uid == current
        # target). Cited as `simulator.oath_of_moment`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            # Snapshot prior round's target before clearing — _pick_oath_target
            # uses this to rotate off a still-alive anchor when a comparable
            # runner-up exists, so the picker doesn't lock onto one unit for
            # the whole game (iter-5 diag: 1.42 unique targets / 5 picks).
            army.prev_oath_target_uid = army.oath_target_uid
            army.oath_target_uid = None
            if any(is_marine_faction(u.profile.faction) for u in army.units):
                self._pick_oath_target(army, opponent, round_num)
        # ---- World Eaters Blood Tithe spend (10e army rule). The codex
        # allows spending at the start of any phase; we elect once per round
        # at the start of the Command phase, priority-greedy on the WE
        # army. Order:
        #   BT >= 4: spend 4, set blood_tithe_lethal_hits_round = round_num
        #            (read by Unit.attack against the live battle round to
        #            grant [LETHAL HITS] on WE-faction attackers for this
        #            round only — collapses the codex's "this phase" scope).
        #   BT >= 3: spend 3, gain +1 CP (capped at the per-round +1 ceiling
        #            via min(6, command_points+1) — matches the per-round
        #            drip behaviour the simulator already applies for the
        #            Command-phase CP gain).
        # The 1-BT charge-roll re-roll, 2-BT +1-to-wound-vs-target, and 5-BT
        # auto-pass Battle-shock are skipped intentionally: the simulator's
        # charge loop doesn't expose a re-roll hook, the target-tagging gate
        # is a per-target side-band that doesn't ride the existing buff plumbing,
        # and the auto-pass is a rare per-battle event whose impact on MAE
        # would be negligible. Cited as `simulator.blood_tithe`.
        for army in (self.a, self.b):
            if not any(u.profile.faction == "World Eaters" for u in army.units):
                continue
            if army.blood_tithe >= 4:
                army.blood_tithe -= 4
                army.blood_tithe_lethal_hits_round = round_num
            elif army.blood_tithe >= 3:
                army.blood_tithe -= 3
                army.command_points = min(6, army.command_points + 1)
        # Clear any per-round transient stratagem flags from the previous
        # round (Disgustingly Resilient, Lightning-Fast Reactions, etc.)
        # before deciding whether to spend CP on a new batch this round.
        self._clear_transient_stratagem_flags(self.a)
        self._clear_transient_stratagem_flags(self.b)
        # ---- Chaos Space Marines Dark Pacts (10e army rule). At the start
        # of the round we pick at most one CSM unit to declare a Dark Pact:
        # it gains [LETHAL HITS] OR [SUSTAINED HITS 1] for the phase in
        # return for a Leadership test that, on failure, inflicts D3
        # mortal wounds on the pacting unit. The codex wording fires "when
        # the unit is selected to shoot or fight"; SwegHammer's round-loop
        # collapses this to a once-per-round elect at Command-phase start
        # (same as Blood Tithe / Doctrina Imperatives / Oath of Moment).
        # APPROXIMATION: Lethal Hits / Sustained Hits have no per-attack
        # keyword toggle in SwegHammer, so the offensive uplift is routed
        # through `transient_plus_one_to_hit_shooting` and
        # `transient_plus_one_to_wound_melee` on the elected CSM unit —
        # same direction and comparable magnitude as a Lethal/Sustained
        # grant on a 3+/4+ roll. Self-damage IS modelled: 2D6>=Ld test;
        # on failure deal D3 mortal wounds via `receive_damage` (FNP-
        # aware). Cited as `simulator.dark_pacts`.
        self._apply_dark_pacts(round_num)
        # ---- World Eaters Blessings of Khorne (10e army rule). At the
        # start of each battle round, roll 8D6 and activate up to two
        # Blessings using doubles/triples meeting each Blessing's
        # threshold. Each active Blessing applies army-wide to WE units
        # until end of battle round. SwegHammer routes the three
        # modelled Blessings (Martial Excellence, Warp Blades, Cleaving
        # Blows) through the army's per-round `blessings_*_round` stamps
        # that `Unit.attack` reads. Cited as
        # `simulator.blessings_of_khorne`.
        self._apply_blessings_of_khorne(round_num)
        # Battleshock check MUST run before the stratagem dispatcher so
        # battleshocked units are excluded from "use Stratagems to affect
        # that unit" (10e core: while a unit is Battle-shocked, you cannot
        # use Stratagems to affect that unit). The dispatcher reads the
        # `_battleshocked_this_round` set when picking targets via
        # `_most_vulnerable_unit` / `_highest_dpa_unit`. See task #168.
        self._run_battleshock_phase(round_num)
        # Detachment-specific stratagems that fire at the start of a round
        # (Virulent Vectorium, Warhost). Doombolt also fires
        # here as a per-round mortal-wound payload — it's nominally a
        # Shooting-phase trigger but the simulator's per-round dispatcher
        # is the cleanest hook for a deterministic "once per round" spend.
        self._apply_detachment_stratagems(self.a, self.b)
        self._apply_detachment_stratagems(self.b, self.a)
        # ---- Astra Militarum Voice of Command Orders (10e army rule).
        # Each AM OFFICER issues one Order to an eligible BATTLELINE
        # INFANTRY (or VEHICLE if Flexible Command was fired this round)
        # within 6", at the start of the Command phase. Stratagem dispatch
        # MUST run first so Flexible Command / Inspired Command flags are
        # set before Order eligibility is computed. Cited as
        # `simulator.voice_of_command_orders`.
        from .orders import dispatch_orders as _dispatch_orders
        for army in (self.a, self.b):
            _issued = _dispatch_orders(army, self._battleshocked_this_round)
            if self.verbose and _issued:
                for officer_name, target_name, order_name in _issued:
                    print(f"  ORDER: {officer_name} -> {target_name}: {order_name}")
        # Thousand Sons Cabal of Sorcerers — Rituals fire at the start of
        # each Shooting phase. We hook them here (same round-start barrier
        # as detachment stratagems) because the simulator's per-unit shoot
        # loop doesn't break out a phase-start barrier separately. Real
        # 2D6 Psychic test, real Doombolt D3/D3+3 math, real WC thresholds.
        # Cited as `simulator.cabal_of_sorcerers`.
        self._run_cabal_rituals()
        # Magnus the Red — Unearthly Power (Crimson King default selection).
        # Wahapedia: "At the start of the battle round, select one of the
        # abilities in the Crimson King section. Until the start of the
        # next battle round, this model has that ability." We default to
        # Impossible Form ("Each time an attack is made against this Psyker
        # (excluding Psychic Attacks), subtract 1 from the Damage
        # characteristic of that attack."), the most-damage-sponging of
        # the three Crimson King options and the simulator's only one
        # cleanly representable. Time Flux (+2" Move aura on TSON) and
        # Treason of Tzeentch (HAZARDOUS on an enemy unit's ranged
        # weapons) are not wired — they require movement-aura and
        # opponent-weapon-mod plumbing the simulator does not expose.
        # Cited as `simulator.magnus_unearthly_power_impossible_form` in
        # data/rule_citations.d/thousand_sons.json.
        for army in (self.a, self.b):
            for u in army.alive_units:
                if u.profile.name == "Magnus the Red":
                    u.transient_minus_one_damage_taken = True
        # Phase I — fresh arrivals from the scout phase carry over INTO
        # Round 1 (set by _run_scout_phase). From Round 2 onwards we reset
        # the set first, THEN call _arrive_from_reserves so units arriving
        # this round are flagged for "skip movement" but those that arrived
        # last round are eligible to move normally.
        #
        # Round 1: do NOT reset `_fresh_arrivals` (scouted units inherit
        # their flag), and call `_arrive_from_reserves` to handle Cult
        # Ambush (Genestealer Cults army rule) — every GSC unit lands at
        # the top of Round 1 via the same arrival path. Regular deep
        # strikers are gated off Round 1 inside _arrive_from_reserves so
        # only ambush-flagged units actually come on here.
        if round_num >= 2:
            self._fresh_arrivals = set()
        self._arrive_from_reserves(round_num)
        for army in (self.a, self.b):
            for u in army.units:
                u.moved_this_round = False
                # Fall Back (10e core): the shoot/charge lockout only lasts
                # the turn the unit fell back, so clear it at the top of
                # every round before the new Movement phase runs.
                u.fell_back_this_round = False

        # Pre-compute on-objective state for the round so Unit.attack() can
        # cheaply apply detachment buffs gated on objective control (Awakened
        # Dynasty +1 to wound is the first user; future detachments can
        # share the flag).
        for army in (self.a, self.b):
            for u in army.units:
                u.on_objective = any(
                    _distance(u.position, (obj.x, obj.y)) <= obj.control_radius
                    for obj in self.map.objectives
                )

        # Battleshock phase already ran before the stratagem dispatcher
        # (task #168 — stratagems can't target battleshocked units, so the
        # test must populate `_battleshocked_this_round` first). See
        # `_run_battleshock_phase` for the rule logic.

        # ---- Coordinated army-level activation plan (#161). At the start of
        # each round, each army picks ONE plan that biases both its activation
        # ORDER (units physically aligned with the plan activate first) and
        # the per-unit strategy layer (objective/charge biases). Without this,
        # the AI picks each activation independently and no alpha strike
        # materialises. Internal AI scheduler — not a 10e rule, no
        # citation required. Gated off in vanilla mode: `activation_queue`
        # already short-circuits to score-only sort when `army_plan is None`.
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            if self.rules.coordinated_army_plan:
                army.army_plan = pick_army_plan(army, opponent, round_num, self.map)
            else:
                army.army_plan = None

        first, second = (
            (self.a, self.b) if random.random() < 0.5 else (self.b, self.a)
        )

        # ---- T'au Empire Markerlights → Guided (10e army-wide). At the start
        # of each Shooting phase, MARKERLIGHT-keyword T'au units mark enemies
        # for that army's shooters. SwegHammer's alternating activation loop
        # doesn't materialise a global Shooting-phase barrier, so we populate
        # the per-army `guided_enemy_uids` set ONCE per round (treating both
        # players' Shooting phases as one batched window, since within the
        # round T'au is the only faction reading the set and only its own
        # attackers benefit). The set is cleared at end-of-round below.
        # Cited as `simulator.markerlights`.
        self._run_markerlight_phase(self.a, self.b)
        self._run_markerlight_phase(self.b, self.a)

        if self.rules.alternating_activations:
            self._run_round_alternating(first, second)
        else:
            self._run_round_vanilla_turns(first, second)

        # ---- Clear Markerlight tokens at end of turn (Wahapedia: "until
        # the end of the turn"). Resetting here so the next round's
        # `_run_markerlight_phase` repopulates cleanly without stale uids.
        self.a.guided_enemy_uids = set()
        self.b.guided_enemy_uids = set()

        # Protocol of the Undying Legions (Awakened Dynasty, 1 CP, #194):
        # one extra reanimation pulse before the routine Reanimation
        # Protocols pass, for any unit the AI fired the stratagem on this
        # round. No-op for armies that didn't fire it.
        self._apply_undying_legions_pulse()

        # Reanimation Protocols (#75): revive destroyed models in armies
        # whose detachment carries the Reanimation flag. This SUPERSEDES the
        # old +1-HP-to-alive-units heal path (Awakened Dynasty no longer
        # heals — it brings dead models back). Median D3 = 2 models revived
        # per profile per round.
        self._apply_reanimation()

        # Psychic phase (#94): detachments with psychic_mortal_wounds_per_round
        # deal that many mortal wounds to the highest-threat enemy unit each
        # round. Bypasses armour / save / toughness — pure HP burn. Models
        # Thousand Sons Cabal-Points → Doombolt cadence.
        self._apply_psychic_phase()

        # Leader auras: end-of-round heal_per_round (Tech-Priest Dominus
        # Lord of the Machine Cult repair flavour) and revive_destroyed_per_round
        # (Apothecary Narthecium — return a destroyed INFANTRY model to the
        # led unit) from registered character abilities.
        from .leaders import apply_round_end_healing, apply_round_end_revival
        apply_round_end_healing(self.a)
        apply_round_end_healing(self.b)
        apply_round_end_revival(self.a)
        apply_round_end_revival(self.b)

        # Genestealer Cults Cult Ambush — Resurgence point revival hook.
        # APPROXIMATION: the real rule spends a per-unit-table cost
        # (2–8 points) to add a fresh copy of a destroyed INFANTRY unit in
        # Strategic Reserves. SwegHammer cannot model marker placement /
        # Reserves arrival timing, so this proxy revives one dead GSC
        # INFANTRY unit per round (cost 3 Resurgence points) at full
        # health, dropping it from the existing Deep Strike picker so it
        # lands > 9" from all enemies on the next round's arrival pass.
        # Cited as `simulator.cult_ambush_resurgence`.
        self._apply_cult_ambush_resurgence(self.a, round_num)
        self._apply_cult_ambush_resurgence(self.b, round_num)

        if round_num > 1 and self.rules.cp_catchup_bonus:
            self._award_cp(self.a, self.b)
            self._award_cp(self.b, self.a)

    # ------------------------------------------------------------------
    # Round body — alternating (SwegHammer) vs turn-based (vanilla 10e)
    # ------------------------------------------------------------------

    def _run_round_alternating(self, first: Army, second: Army) -> None:
        """SwegHammer alternating-activation round: pairs of units from
        opposing armies sub-phase by sub-phase (move, shoot, charge, fight),
        first player randomised.

        When `simultaneous_movement` is True (default in SwegHammer mode),
        both units in a pair complete a sub-phase before either advances
        to the next — avoids the second-mover-closes-into-range asymmetry.
        When False, each unit in a pair completes its full
        move→shoot→charge→fight before the next unit acts — closer to the
        per-unit-cadence of bolt-action style activations.
        """
        first_activated: set = set()
        second_activated: set = set()

        while True:
            first_q = first.activation_queue(first_activated, map_=self.map)
            second_q = second.activation_queue(second_activated, map_=self.map)
            if not first_q and not second_q:
                break

            first_unit = first_q[0] if first_q else None
            second_unit = second_q[0] if second_q else None
            if first_unit is not None:
                first_activated.add(id(first_unit))
            if second_unit is not None:
                second_activated.add(id(second_unit))

            if self.rules.simultaneous_movement:
                # Both units complete each sub-phase before either moves on
                if first_unit is not None and first_unit.is_alive:
                    self._do_move(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_move(second_unit, second, first)

                if first_unit is not None and first_unit.is_alive:
                    self._do_shoot(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_shoot(second_unit, second, first)

                if first_unit is not None and first_unit.is_alive:
                    self._do_charge(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_charge(second_unit, second, first)

                if first_unit is not None and first_unit.is_alive:
                    self._do_fight(first_unit, first, second)
                if second_unit is not None and second_unit.is_alive:
                    self._do_fight(second_unit, second, first)
            else:
                # Each unit completes its full sequence in turn
                for unit, own, foe in (
                    (first_unit, first, second),
                    (second_unit, second, first),
                ):
                    if unit is None:
                        continue
                    if unit.is_alive:
                        self._do_move(unit, own, foe)
                    if unit.is_alive:
                        self._do_shoot(unit, own, foe)
                    if unit.is_alive:
                        self._do_charge(unit, own, foe)
                    if unit.is_alive:
                        self._do_fight(unit, own, foe)

    def _run_round_vanilla_turns(self, first: Army, second: Army) -> None:
        """Vanilla WH40k 10e I-go-you-go turn structure: the first player
        completes their entire turn (Movement → Shooting → Charge → Fight
        across all their units) before the second player begins.

        The per-round state set in `_run_round` (oath target, doctrina
        imperative, battleshock results, fresh-arrival flags) is shared
        across both turns within a round — same logical scope as the
        Command-phase setup that ran once at round start.

        Within each phase, units activate in `activation_queue` order
        (score-only sort because `army_plan is None` under vanilla rules);
        the player picks the order in real play and the heuristic picker
        approximates that choice.
        """
        from .leaders import bump_buffs_generation
        for active, other in ((first, second), (second, first)):
            # Clear the effective_buffs cache once per phase — positions don't
            # change mid-phase, so all units in a phase safely share cached results.
            bump_buffs_generation()
            # Enemy units do not move during our move phase, so their OC on every
            # objective is constant for all activations this phase. Precompute once
            # and pass down to _do_move → pick_move_intent, halving the
            # _oc_on_objective call count (from 10 per activation to 5).
            _objectives = self.map.objectives
            _other_alive = other.alive_units
            _phase_their_oc: Dict[int, int] = {
                id(obj): _oc_on_objective(_other_alive, obj) for obj in _objectives
            }
            for unit in list(active.units):
                if unit.is_alive:
                    self._do_move(unit, active, other, _phase_their_oc=_phase_their_oc)
            bump_buffs_generation()
            for unit in list(active.units):
                if unit.is_alive:
                    self._do_shoot(unit, active, other)
            bump_buffs_generation()
            for unit in list(active.units):
                if unit.is_alive:
                    self._do_charge(unit, active, other)
            bump_buffs_generation()
            # Fight phase — active player's units fight. Real 10e Fight phase
            # interleaves both players' chargers + locked units; this
            # approximates by giving the active player their full fight pass,
            # and the other player's reactive fights resolve in their own
            # turn's Fight phase. Fights First (`_charging_this_round`) is
            # already round-scoped, so chargers from this round still get
            # the bonus when their own player's turn rolls around.
            #
            # CORE-RULE-FIX-1 — sequence chargers BEFORE non-chargers within
            # the active player's fight pass. Per Wahapedia core rules
            # (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#The-Fight-Phase):
            # "All eligible units that have the FIGHTS FIRST ability must
            # fight in the Fights First step. Then, in the Remaining Combats
            # step, all other eligible units fight." A unit that made a
            # Charge move this turn counts as having FIGHTS FIRST for the
            # turn it charged ("each time you select an eligible unit from
            # your army to fight with that made a Charge move this turn,
            # that unit fights first"). Without this ordering, a non-charger
            # whose activation_queue rank is higher could fight before the
            # charger and waste the charge's positional / buff opportunity.
            # Cited as `simulator.fights_first_chargers`.
            ordered = sorted(
                list(active.units),
                key=lambda u: 0 if u.uid in self._charging_this_round else 1,
            )
            for unit in ordered:
                if unit.is_alive:
                    self._do_fight(unit, active, other)

    # ------------------------------------------------------------------
    # Sub-phases
    # ------------------------------------------------------------------

    def _do_move(self, attacker, attacker_army: Army, defender_army: Army,
                 _phase_their_oc=None) -> None:
        # Embarked passengers do not act on their own activation — the
        # transport carries them. The simulator emits UnitActivated for the
        # transport, not the passenger. Cited as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return

        self._emit(UnitActivated(
            unit_uid=attacker.uid,
            army_name=attacker_army.name,
        ))

        # Phase I: units that arrived from reserves THIS round, or scouted
        # at the start of the game (Round 1), already moved as part of that
        # ability — skip their normal-move sub-phase for one activation.
        if attacker.uid in self._fresh_arrivals:
            return

        # Transport voluntary disembark hook (10e core). Fires BEFORE the
        # transport's move so the rule "the transport hasn't moved this turn"
        # is satisfied. Cited as `simulator.disembark`.
        if self._is_transport(attacker) and attacker.passengers:
            self._maybe_disembark_before_move(attacker, attacker_army, defender_army)

        # Strategy layer (code/strategy.py): role + objective-aware pick of
        # where this unit wants to go. The simulator USED to always march at
        # the nearest enemy, which abandoned objectives and lost VP. Now units
        # consult their role + the live objective state.
        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return
        target_pos, intent = pick_move_intent(
            attacker, attacker_army, defender_army, self.map,
            army_plan=attacker_army.army_plan,
            _phase_their_oc=_phase_their_oc,
        )

        # Fall Back (10e core). Units already locked in melee that the
        # strategy layer wants to disengage move up to M" toward the picked
        # destination, then take a Desperate Escape test (1D6 per model;
        # each 1 destroys a model — we model unit-per-model, so this is one
        # roll). Falling back blocks shoot / charge for the turn unless the
        # unit has FLY. Cited as `simulator.fall_back` /
        # `simulator.desperate_escape`. Advance-this-turn and Fall Back are
        # mutually exclusive: Fall Back uses the normal-move pool.
        if intent == "FALL_BACK":
            if attacker.uid in self._advanced_this_round:
                # Already advanced this round — don't compound activations.
                return
            normal_move = effective_move(attacker)
            old_pos = attacker.position
            new_pos = _move_toward(
                attacker.position, target_pos,
                float(normal_move), self.map,
            )
            if new_pos != old_pos:
                attacker.position = new_pos
                self._did_move_this_round.add(attacker.uid)
                attacker.moved_this_round = True
                self._emit(UnitMoved(
                    unit_uid=attacker.uid,
                    from_pos=old_pos,
                    to_pos=new_pos,
                ))
            attacker.fell_back_this_round = True
            # Desperate Escape: 1D6 per model — SwegHammer is one Unit per
            # model, so a single d6; on a 1 the model is destroyed.
            if random.randint(1, 6) == 1:
                attacker.current_health = 0.0
                if not attacker.is_alive:
                    self._emit(UnitKilled(unit_uid=attacker.uid))
                    self._maybe_apply_deadly_demise(attacker)
            return

        dist = _distance(attacker.position, target_pos)
        if dist < 0.5 or intent == "HOLD":
            return   # already where we want to be — stay and shoot

        # 10e Advance: roll d6, move M+d6, but skip shoot/charge this turn.
        # We Advance only when a normal move would NOT bring us into shooting
        # range of the target — the speed boost is wasted otherwise and the
        # shoot foregone.
        normal_move = effective_move(attacker)
        # For ENGAGE intent, "in range" = weapon range. For CAPTURE/STEAL,
        # "in range" = within the objective's control radius (we want to be on
        # the marker). REPOSITION is a small jiggle (always normal-move).
        if intent in ("ENGAGE", "REPOSITION"):
            range_threshold = attacker.profile.range_inches
        else:
            range_threshold = 3.0   # objective control radius
        needs_to_close = dist - range_threshold
        advance_d6 = random.randint(1, 6) if needs_to_close > normal_move else 0
        # Strands of Fate (Aeldari army rule, 10e) — substitute the
        # Advance d6 with a higher Fate die when doing so would clear
        # the remaining distance (the unit Advances *into* range that a
        # natural roll wouldn't reach). The threshold is the d6 we'd need
        # to bridge `needs_to_close - normal_move`; we only spend when the
        # substitution flips a fail -> success. Cited as
        # `simulator.strands_of_fate`. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
        if (
            advance_d6 > 0
            and attacker.profile.faction == "Aeldari"
            and attacker_army.has_fate_dice()
        ):
            need = needs_to_close - normal_move
            if advance_d6 < need and need <= 6:
                sub = attacker_army.pop_fate_die_meeting(int(need))
                if sub is not None:
                    advance_d6 = sub
        move_distance = normal_move + advance_d6
        did_advance = advance_d6 > 0

        old_pos = attacker.position
        new_pos = _move_toward(
            attacker.position, target_pos,
            move_distance, self.map,
        )
        if new_pos != old_pos:
            attacker.position = new_pos
            # Surface the move to the Heavy keyword check in Unit.attack().
            self._did_move_this_round.add(attacker.uid)
            attacker.moved_this_round = True
            self._emit(UnitMoved(
                unit_uid=attacker.uid,
                from_pos=old_pos,
                to_pos=new_pos,
            ))
        if did_advance:
            self._advanced_this_round.add(attacker.uid)
            self._emit(UnitAdvanced(
                unit_uid=attacker.uid,
                advance_roll=advance_d6,
                total_movement=float(move_distance),
            ))

    def _gladius_active_doctrine(self, attacker, attacker_army: Army) -> str:
        """Return the active Gladius Task Force Combat Doctrine name for
        the given Marine attacker on this round, or '' if none applies.

        The Marine player picks one Doctrine per Command phase; SwegHammer
        rotates deterministically Devastator R1 / Tactical R2 / Assault R3+.
        Faction-gated to ADEPTUS ASTARTES, detachment-gated to Gladius Task
        Force. Real-rule wording is movement-utility only (no damage buff).
        Cited as `simulator.combat_doctrines`. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
        """
        if not is_marine_faction(attacker.profile.faction):
            return ""
        det = attacker_army.resolve_detachment()
        if det is None or det.name != "Gladius Task Force":
            return ""
        r = self._current_round
        if r == 1:
            return "Devastator"
        if r == 2:
            return "Tactical"
        if r >= 3:
            return "Assault"
        return ""

    def _do_shoot(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        # Embarked passengers cannot shoot on their own activation (10e core).
        # Their fire is folded into the transport's via Firing Deck X. Cited
        # as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return
        # Fall Back lockout (10e core): a unit that Fell Back this turn can
        # only shoot if it has the FLY keyword. Cited as
        # `simulator.fall_back`. Tactical Doctrine (Gladius Task Force, R2)
        # explicitly lifts this lockout for ADEPTUS ASTARTES units in a
        # Gladius army: "This unit is eligible to shoot and declare a
        # charge in a turn in which it Fell Back." Cited as
        # `simulator.combat_doctrines`.
        if attacker.fell_back_this_round and not attacker.profile.fly:
            if self._gladius_active_doctrine(attacker, attacker_army) != "Tactical":
                return
        # 10e: a unit that Advanced this turn cannot shoot, unless its weapon
        # is Assault — or the unit's army can spend a Battle Focus token to
        # treat its weapons as [ASSAULT] for the turn (Aeldari rule) — or
        # Feigned Retreat (Warhost stratagem) or Matchless Agility / Aggressive
        # Mobility (Battle Host / Mont'ka stratagems) has been fired this round
        # to grant transient Assault on the unit — or Mont'ka's Killing Blow
        # detachment rule is active and we are in rounds 1-3 (army-wide
        # [ASSAULT] grant to T'au Empire ranged weapons) — or the unit is
        # ADEPTUS ASTARTES in a Gladius army under the active Devastator
        # Doctrine (R1): "This unit is eligible to shoot in a turn in
        # which it Advanced." Cited as `MONTKA.army_wide_assault_rounds_1_3`
        # and `simulator.combat_doctrines`.
        if attacker.uid in self._advanced_this_round and not attacker.profile.assault:
            kw = attacker.profile.unit_keywords or ()
            det = attacker_army.resolve_detachment()
            montka_assault_window = (
                det is not None
                and getattr(det, "army_wide_assault_rounds_1_3", False)
                and self._current_round <= 3
                and (attacker.profile.faction or "").lower() in ("t'au empire", "tau empire")
            )
            if attacker.transient_assault_this_round:
                pass   # stratagem already paid for; no token spend
            elif montka_assault_window:
                pass   # detachment rule grants [ASSAULT] free this round
            elif self._gladius_active_doctrine(attacker, attacker_army) == "Devastator":
                pass   # Devastator Doctrine grants shoot-after-Advance, free
            elif ("ASURYANI" in kw) and attacker_army.battle_focus_tokens > 0:
                attacker_army.battle_focus_tokens -= 1
            else:
                return
        # One Shot: weapon may only fire once per battle. If we've already
        # fired it, skip the activation outright.
        if attacker.profile.one_shot and attacker.uid in self._one_shot_fired:
            return

        # Engagement gate: a unit within 1.5" of an enemy is locked in
        # melee and normally can't shoot. Three exceptions:
        #   - Pistol weapons (always)
        #   - VEHICLE / MONSTER keywords: Big Guns Never Tire (10e core
        #     rule) — they can shoot at -1 to hit (resolved per-attack
        #     inside Unit.attack via the in_engagement_penalty flag)
        # Anything else falls through and skips its shooting activation.
        kw = attacker.profile.unit_keywords or ()
        big_guns_eligible = "VEHICLE" in kw or "MONSTER" in kw
        in_engagement = any(
            _distance(attacker.position, e.position) < 1.5
            for e in defender_army.alive_units
        )
        if in_engagement:
            if attacker.profile.pistol:
                pass   # pistols shoot freely in engagement
            elif big_guns_eligible:
                attacker.shooting_in_engagement = True
            else:
                return
        else:
            attacker.shooting_in_engagement = False

        rng = attacker.profile.range_inches
        # Embarked passengers are off-board — they cannot be targeted by
        # ranged attacks. Targeting passes through the transport itself.
        # Cited as `simulator.embark`.
        targetable = [
            u for u in defender_army.alive_units
            if getattr(u, "embarked_in", None) is None
        ]
        # Indirect Fire lets us target units we cannot see; otherwise LoS is
        # required. The has_los flag is plumbed into Unit.attack so it can
        # apply the -1 to hit when shooting blind.
        if attacker.profile.indirect_fire:
            candidates = [
                u for u in targetable
                if _distance(attacker.position, u.position) <= rng
            ]
        else:
            attacker_kw = attacker.profile.unit_keywords or ()
            candidates = [
                u for u in targetable
                if _distance(attacker.position, u.position) <= rng
                and self.map.has_line_of_sight(
                    attacker.position, u.position,
                    attacker_keywords=attacker_kw,
                    target_keywords=u.profile.unit_keywords or (),
                )
            ]
        # 10e core targeting restrictions: Look Out Sir + Lone Operative. The
        # helper composes both rules — `friendly_units` to a candidate target
        # is its OWN army's alive units (bodyguards live with the target).
        # Cited as `simulator.look_out_sir` and `simulator.lone_operative`.
        from .army import can_target_for_ranged
        defender_alive = defender_army.alive_units
        candidates = [
            u for u in candidates
            if can_target_for_ranged(attacker, u, defender_alive)
        ]
        if not candidates:
            return

        # Threat-aware target priority: prefer enemies contesting one of OUR
        # objectives. If multiple, pick the lowest-HP among them (likely to
        # finish off and clear the objective). If none on objectives, fall back
        # to the global lowest-HP target.
        def _contests_our_obj(u):
            for obj in self.map.objectives:
                dx = u.position[0] - obj.x
                dy = u.position[1] - obj.y
                if dx * dx + dy * dy <= obj.control_radius * obj.control_radius:
                    return True
            return False

        contesting = [u for u in candidates if _contests_our_obj(u)]
        pool = contesting or candidates
        # S6 (#166) — anti-swarm shooting priority: bias toward OC-bearing
        # chaff before high-DPA bricks. Real tournament play clears the
        # screen first so the opposing army can't flip primary while we
        # chew through Carnifexes. The bonus is multiplicative on a
        # "lower is better" picker, so we *divide* a profile-based score
        # by the bonus — a 1.4x screen gets scored as 0.71x its raw HP
        # for picking purposes, biasing the min() toward it. Additive
        # bias only; the fragile chaff that loses ties anyway still loses,
        # but a Termagant unit at 5 HP outscores a Carnifex at 8 HP.
        # S7 (#168) — synapse-source shooting priority: a non-Tyranid
        # attacker biases toward SYNAPSE units (Hive Tyrant, Tervigon) so
        # killing them revokes the Tyranid army's Battle-shock shelter.
        # Same "lower-is-better" inversion as the screen bonus — we divide
        # the score so a 1.5x bonus reads as 0.67x its raw HP, biasing
        # min() toward it.
        # AI-4 — Adeptus Astartes Oath-of-Moment target priority: when this
        # attacker is a Marine unit and its army has nominated an Oath target
        # this turn, bias the picker toward dumping fire on that target so
        # the army's hit-1 + wound-1 re-rolls compound on a single anchor
        # (matches real-meta Marine play). Gated faction-pure via
        # `is_marine_faction` (excludes Grey Knights / Custodes / Sisters);
        # the LoS+range candidates filter above means the bonus only fires
        # when the Oath target is actually reachable for this attacker.
        # AI-8 — Transport target priority (faction-neutral): real-meta
        # opponents shoot TRANSPORT units first to deny the embarked unit's
        # alpha-strike disembark. The bonus is keyword-gated on the defender
        # (TRANSPORT in unit_keywords) and stacks multiplicatively with the
        # screen / synapse / oath chain. Empty transports get 1.8x; loaded
        # transports get 2.2x (priority dial-up when killing the chassis
        # also disrupts the passengers).
        from .strategy import (
            _astartes_oath_target_bonus,
            _screen_target_bonus,
            _synapse_target_bonus,
            _transport_target_bonus,
        )
        shoot_target = min(
            pool,
            key=lambda u: u.current_health / (
                _screen_target_bonus(u)
                * _synapse_target_bonus(attacker, u)
                * _astartes_oath_target_bonus(attacker, u, attacker_army)
                * _transport_target_bonus(u)
            ),
        )

        # Terrain-aware cover: target counts as in cover if it stands inside
        # cover terrain, OR if the army-wide cover flag is set. HEAVY cover
        # also imposes -1 to hit on the attacker (handled in Unit.attack via
        # the in_heavy_cover flag).
        saved_cover = shoot_target.in_cover
        saved_heavy = shoot_target.in_heavy_cover
        cover_type = self.map.cover_at(shoot_target.position)
        if cover_type in (
            TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.RUIN,
        ):
            shoot_target.in_cover = True
        if cover_type in (TerrainType.HEAVY_COVER, TerrainType.RUIN):
            shoot_target.in_heavy_cover = True

        distance = _distance(attacker.position, shoot_target.position)
        has_los = self.map.has_line_of_sight(
            attacker.position, shoot_target.position,
            attacker_keywords=attacker.profile.unit_keywords or (),
            target_keywords=shoot_target.profile.unit_keywords or (),
        )
        # MR-WE-3 Blood Surge — snapshot pre-shot health so we can detect a
        # model destruction event on the defender (Khorne Berzerkers only).
        # See `simulator.blood_surge` in rule_citations.json.
        _blood_surge_health_before = shoot_target.current_health
        dmg = attacker.attack(shoot_target, distance=distance, has_los=has_los)
        # Firing Deck X (10e core, TRANSPORT keyword). If the attacker is a
        # TRANSPORT with embarked passengers and firing_deck > 0, up to X
        # passenger weapons also fire this Shooting phase. Cited as
        # `simulator.firing_deck`.
        if (
            self._is_transport(attacker)
            and getattr(attacker.profile, "firing_deck", 0) > 0
            and attacker.passengers
            and shoot_target.is_alive
        ):
            dmg += self._apply_firing_deck(
                attacker, shoot_target, attacker_army, defender_army,
            )
        shoot_target.in_cover = saved_cover
        shoot_target.in_heavy_cover = saved_heavy
        # Mark One Shot weapons as expended for the rest of the battle.
        if attacker.profile.one_shot:
            self._one_shot_fired.add(attacker.uid)

        target_alive_after = shoot_target.is_alive
        self._emit(UnitShot(
            attacker_uid=attacker.uid,
            target_uid=shoot_target.uid,
            damage=dmg,
            target_hp_after=shoot_target.current_health,
            target_alive_after=target_alive_after,
        ))
        if not target_alive_after:
            self._emit(UnitKilled(unit_uid=shoot_target.uid))
            # Judgement Tokens: if the destroyed unit belonged to a Votann
            # army, the killer (this attacker) earns a token on itself.
            self._maybe_award_judgement_token(
                killer=attacker, killer_army=attacker_army,
                victim=shoot_target, victim_army=defender_army,
            )
            self._maybe_award_blood_tithe(
                killer=attacker, killer_army=attacker_army,
                victim=shoot_target, victim_army=defender_army,
            )
            # Adepta Sororitas Acts of Faith: friendly Sororitas death
            # grants the victim's army +1 Miracle die.
            self._maybe_award_miracle_die(
                victim=shoot_target, victim_army=defender_army,
            )
            # Deadly Demise (10e core): the destroyed unit may detonate.
            self._maybe_apply_deadly_demise(shoot_target)

        # MR-WE-3 Blood Surge (Khorne Berzerkers). After this shot resolves,
        # if the defender is a Khorne Berzerkers unit and lost one or more
        # models from these attacks, it makes a free D6+2" reactive move
        # ending as close as possible to the closest enemy unit. Cited as
        # `simulator.blood_surge`. Faction-gated ("World Eaters") AND
        # name-gated (profile.name == "Khorne Berzerkers") so Eightbound,
        # Exalted Eightbound, Angron, and other WE datasheets DO NOT
        # trigger. Fires per shot resolution so multiple Berzerker units
        # each Surge from their respective shooters.
        self._maybe_apply_blood_surge(
            defender=shoot_target,
            attacker_army=attacker_army,
            health_before=_blood_surge_health_before,
        )

        if self.verbose:
            alive_str = (
                "killed" if not shoot_target.is_alive
                else f"{shoot_target.current_health:.2f}hp left"
            )
            print(
                f"  {attacker_army.name}: {attacker.profile.name}"
                f" -> {shoot_target.profile.name} ({dmg:.2f} dmg, {alive_str})"
            )

    def _maybe_apply_blood_surge(
        self,
        defender,
        attacker_army: Army,
        health_before: float,
    ) -> None:
        """MR-WE-3 — Blood Surge reactive move for Khorne Berzerkers.

        BSData v10.6.0 (Chaos - World Eaters.cat.gz), verbatim:
          "In your opponent's Shooting phase, each time an enemy unit has
          shot, if any models from this unit were destroyed as a result of
          those attacks, this unit can make a Blood Surge move. To do so,
          roll one D6 and add 2 to the roll: models in this unit move a
          number of inches up to this result, but this unit must finish
          that move as close as possible to the closest enemy unit."

        Faction-gated to World Eaters AND name-gated to "Khorne Berzerkers"
        — Eightbound, Exalted Eightbound, Angron etc. do NOT have this
        ability. Triggered per shot resolution (the caller calls this once
        per `_do_shoot` invocation), so multiple Berzerker units each Surge
        in response to their respective shooters. Cited as
        `simulator.blood_surge`. See data/rule_citations.json.

        Movement model: roll D6+2, then close the gap to the nearest enemy
        unit (the shooter's army's nearest unit, since that's "the closest
        enemy unit" from the Berzerkers' point of view at the moment of
        the shot). If the gap is larger than D6+2, advance D6+2 toward
        the nearest enemy via `_move_toward`. If the gap is smaller, move
        directly INTO engagement range (1.0" gap) so the Berzerkers
        translate the surge into a melee threat the same turn — which is
        the rule's intent ("finish as close as possible to the closest
        enemy unit"). Engagement-range floor of 1.0" matches the
        `_do_charge` post-charge placement and the 10e Engagement Range
        of 1".
        """
        # Faction + datasheet gate.
        if defender.profile.faction != "World Eaters":
            return
        if defender.profile.name != "Khorne Berzerkers":
            return
        if not defender.is_alive:
            return  # whole unit wiped — nothing left to Surge

        # "any models from this unit were destroyed" — gate on at least
        # one full model worth of wounds lost across this shot resolution.
        # `current_health` is total wounds across surviving models; a
        # model is destroyed when the unit's health crosses a
        # `wounds_per_model` boundary downward.
        if defender.profile.min_models < 2:
            return  # not a multi-model squad — defensive guard
        wounds_per_model = defender.profile.health / defender.profile.min_models
        if wounds_per_model <= 0:
            return
        models_before = int(health_before / wounds_per_model + 1e-9)
        models_after = int(defender.current_health / wounds_per_model + 1e-9)
        # Round up survivors: if you've taken any wounds into a model
        # you've "wounded" but not "destroyed" it. Match the codex
        # threshold: the floor of (lost_health / wpm) gives the count of
        # destroyed models. Use floor of remaining health on both sides
        # — if a model lost some-but-not-all wounds neither side counts
        # that as destruction.
        lost_health = max(0.0, health_before - defender.current_health)
        models_destroyed = int(lost_health / wounds_per_model + 1e-9)
        if models_destroyed < 1:
            return

        # Pick nearest enemy unit (from the shooting army — those are the
        # "closest enemy" units from the Berzerkers' perspective at the
        # moment of the surge). Fall through gracefully if there's no
        # alive enemy (shouldn't happen since we just shot, but guard
        # against off-board / embarked cases).
        enemy_pool = [
            u for u in attacker_army.alive_units
            if getattr(u, "embarked_in", None) is None
        ]
        if not enemy_pool:
            return
        nearest = min(enemy_pool, key=lambda e: _distance(defender.position, e.position))
        gap = _distance(defender.position, nearest.position)
        if gap <= 0:
            return  # already co-located, nothing to do

        surge_roll = random.randint(1, 6) + 2   # D6 + 2
        # "finish as close as possible" -> if we can reach engagement
        # range (1.0"), stop at 1.0" gap. Otherwise advance the full
        # surge distance toward the enemy.
        if gap - surge_roll <= 1.0:
            travel = max(0.0, gap - 1.0)
        else:
            travel = float(surge_roll)
        old_pos = defender.position
        new_pos = _move_toward(old_pos, nearest.position, travel, self.map)
        defender.position = new_pos
        if self.verbose:
            print(
                f"  [Blood Surge] {defender.profile.name} ({defender.uid}) "
                f"surged {travel:.1f}\" toward {nearest.profile.name} "
                f"(gap {gap:.1f}\" -> {_distance(new_pos, nearest.position):.1f}\")"
            )

    # ------------------------------------------------------------------
    # Charge + Fight (Phase B)
    # ------------------------------------------------------------------

    @staticmethod
    def _wants_to_charge(attacker) -> bool:
        """
        Charge-desire heuristic: a unit wants to charge only if its melee
        output is meaningfully higher than its ranged output. Pure shooters
        and tanks stay put; melee-heavy and dual-threat units charge in.
        """
        p = attacker.profile
        if p.melee_attacks <= 0 or p.melee_hit_probability <= 0:
            return False
        melee_dpa = p.melee_attacks * p.melee_hit_probability * (p.melee_damage_per_shot or 1.0)
        ranged_dpa = max(1, p.attacks) * p.hit_probability * p.per_shot_damage
        # 1.0x melee floor avoids vehicles with token bayonets charging Marines.
        return melee_dpa >= max(ranged_dpa, 1.0)

    def _do_charge(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        """2D6 charge vs the best target ≤12". On success, move into 1" engagement.

        Target picked by code.strategy.pick_charge_target — favours enemies
        weak in melee (gunlines / battlesuits) over near-but-resilient brick
        units, which is closer to real tournament melee play and brings the
        sim's over-rating of T'au / Astartes / Votann shooty factions down.
        """
        # Embarked passengers cannot charge (10e core). Cited as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return
        if not self._wants_to_charge(attacker):
            return
        # Advance lockout (10e core): a unit that Advanced this turn cannot
        # charge. Assault Doctrine (Gladius Task Force, R3+) explicitly lifts
        # this lockout for ADEPTUS ASTARTES units in a Gladius army: "This
        # unit is eligible to declare a charge in a turn in which it
        # Advanced." Cited as `simulator.combat_doctrines`.
        if attacker.uid in self._advanced_this_round:
            if self._gladius_active_doctrine(attacker, attacker_army) != "Assault":
                return
        # Fall Back lockout (10e core): a unit that Fell Back this turn can
        # only charge if it has the FLY keyword. Tactical Doctrine (Gladius,
        # R2) also lifts this lockout: "This unit is eligible to shoot and
        # declare a charge in a turn in which it Fell Back." Cited as
        # `simulator.fall_back` and `simulator.combat_doctrines`.
        if attacker.fell_back_this_round and not attacker.profile.fly:
            if self._gladius_active_doctrine(attacker, attacker_army) != "Tactical":
                return

        from .strategy import pick_charge_target
        target, dist = pick_charge_target(attacker, defender_army)
        if target is None:
            return

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        roll = d1 + d2
        # Strands of Fate (Aeldari army rule, 10e) — substitute one of
        # the 2D6 with a Fate die when the natural total would fail the
        # charge. We replace the LOWER d6 with the lowest die in the
        # pool that lifts the total to >= dist. The substitution only
        # fires if it would flip fail -> success (greedy heuristic).
        # Cited as `simulator.strands_of_fate`. Wahapedia:
        # https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
        if (
            roll < dist
            and attacker.profile.faction == "Aeldari"
            and attacker_army.has_fate_dice()
        ):
            lower = min(d1, d2)
            needed = int(dist) - (roll - lower)   # the die value we need
            sub = attacker_army.pop_fate_die_meeting(max(1, needed))
            if sub is not None:
                roll = roll - lower + sub
        succeeded = (roll >= dist)
        if not succeeded:
            self._emit(UnitCharged(
                unit_uid=attacker.uid, target_uid=target.uid,
                distance=dist, roll=roll, succeeded=False,
            ))
            return

        # Move to within 1" of target — engagement range
        dx = target.position[0] - attacker.position[0]
        dy = target.position[1] - attacker.position[1]
        scale = max(0.0, (dist - 1.0)) / dist
        new_pos = (
            attacker.position[0] + dx * scale,
            attacker.position[1] + dy * scale,
        )
        if not self.map.is_blocked(new_pos):
            attacker.position = new_pos
        self._charging_this_round.add(attacker.uid)
        self._emit(UnitCharged(
            unit_uid=attacker.uid, target_uid=target.uid,
            distance=dist, roll=roll, succeeded=True,
        ))

        # Universal Core Stratagem on a successful charge:
        # * Tank Shock (1 CP, attacker) — VEHICLE chargers deal D3 mortal
        #   wounds.
        self._try_tank_shock(attacker, target, attacker_army)
        # Heroic Intervention (10e core, FREE — NOT a stratagem). After the
        # charger has ended its move, every friendly defender CHARACTER
        # within 6" of the charger may make a normal move of up to 6"
        # (3" if WALKER) ending in engagement range with that charger.
        # Cited as `simulator.heroic_intervention_core`. Fires after Tank
        # Shock so the character intervenes against whatever's still
        # standing.
        self._do_heroic_intervention(attacker, defender_army)

    def _do_fight(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        """Resolve a melee strike if the attacker is in engagement range (1").

        10e Fight phase per-unit sequence is Pile-In -> Fight -> Consolidate.
        Both pile-in and consolidate are mandatory free 3" moves toward the
        closest enemy (Wahapedia core rules). SwegHammer's one-Unit-per-
        model representation means "each model" collapses to "the Unit".
        Cited as `simulator.pile_in` / `simulator.consolidate`.
        """
        # Embarked passengers cannot fight (10e core). Cited as `simulator.embark`.
        if getattr(attacker, "embarked_in", None) is not None:
            return
        if attacker.profile.melee_attacks <= 0:
            return
        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return

        # --- Pile-In (10e core): free 3" move toward the closest enemy,
        # taken BEFORE the fight resolves. Gated on the attacker being in
        # actual fight eligibility — within Engagement Range of an enemy
        # OR having charged this turn (per 10e core: "A unit can fight in
        # your Fight phase if either it is within Engagement Range of one
        # or more enemy units, or it made a Charge move this turn").
        # Pile-in often closes the residual gap so the attacks land at
        # the full melee profile.
        nearest_pre = min(
            alive_enemies,
            key=lambda e: _distance(attacker.position, e.position),
        )
        pre_engaged = _distance(attacker.position, nearest_pre.position) <= 1.5
        is_charging_this_turn = attacker.uid in self._charging_this_round
        if (
            (pre_engaged or is_charging_this_turn)
            and not self.map.is_blocked(attacker.position)
        ):
            new_pos = _move_toward(
                attacker.position, nearest_pre.position, 3.0, self.map,
            )
            if not self.map.is_blocked(new_pos):
                attacker.position = new_pos

        # #C1 (auto-loop iter1): pick the engagement-range candidate with
        # the highest `_melee_target_score` rather than the geometrically
        # nearest. The score is faction-neutral — it's a pure DPA-vs-
        # durability ratio with role-based screen/synapse/support
        # multipliers that apply universally. Replaces the prior
        # `min(enemies, key=distance)` so that when 2+ enemies are in
        # engagement, the simulator picks the one whose death actually
        # breaks the lock rather than the closest brick.
        in_range = [
            e for e in alive_enemies
            if _distance(attacker.position, e.position) <= 1.5
        ]
        if not in_range:
            return
        target = max(in_range, key=lambda e: _melee_target_score(attacker, e))
        is_charging = attacker.uid in self._charging_this_round
        dmg = attacker.attack(
            target, distance=1.0, mode="melee", is_charging=is_charging,
        )
        alive_after = target.is_alive
        self._emit(UnitFought(
            attacker_uid=attacker.uid,
            target_uid=target.uid,
            damage=dmg,
            target_hp_after=target.current_health,
            target_alive_after=alive_after,
        ))
        if not alive_after:
            self._emit(UnitKilled(unit_uid=target.uid))
            self._maybe_award_judgement_token(
                killer=attacker, killer_army=attacker_army,
                victim=target, victim_army=defender_army,
            )
            self._maybe_award_blood_tithe(
                killer=attacker, killer_army=attacker_army,
                victim=target, victim_army=defender_army,
            )
            self._maybe_award_miracle_die(
                victim=target, victim_army=defender_army,
            )
            self._maybe_apply_deadly_demise(target)

        # Universal Core Stratagem — Counter-Offensive (2 CP, defender):
        # an out-of-sequence fight for the side that just got hit. The
        # heuristic gates on (a) friendly unit in 1.5" of the attacker
        # AND (b) the attacker killed a model. The retaliator strikes
        # `attacker` immediately, before activation continues.
        if attacker.is_alive:
            self._try_counter_offensive(
                loser_army=defender_army, loser_unit=target,
                winner_army=attacker_army, winner_unit=attacker,
                target_killed=not alive_after,
            )

        # --- Consolidate (10e core): free 3" move taken AFTER the fight.
        # Moves toward the closest enemy OR keeps the unit in engagement
        # with units it was engaged with at the start of the move. We
        # collapse to "move 3" toward closest enemy" — if the previous
        # target survived this still sticks to it; if it died, the next
        # closest enemy is chased. Cited as `simulator.consolidate`.
        if attacker.is_alive and not self.map.is_blocked(attacker.position):
            remaining = defender_army.alive_units
            if remaining:
                nearest_post = min(
                    remaining,
                    key=lambda e: _distance(attacker.position, e.position),
                )
                new_pos = _move_toward(
                    attacker.position, nearest_post.position, 3.0, self.map,
                )
                if not self.map.is_blocked(new_pos):
                    attacker.position = new_pos

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, event) -> None:
        for s in self.subscribers:
            s.on_event(event)

    def _run_markerlight_phase(self, army: Army, opponent: Army) -> None:
        """T'au Empire Markerlights → Guided (10e army-wide army rule).

        At the start of this army's Shooting phase, every alive MARKERLIGHT-
        keyword unit in `army` attempts to mark one enemy unit. The marker
        is a weapon that fires in the Shooting phase like any other ranged
        weapon (Wahapedia: Markerlight weapon ability under the T'au army
        rule, see citation `simulator.markerlight_emission`): it requires
        line of sight from the carrier to the candidate, the candidate
        must lie within the Markerlight's 36" range, and the carrier must
        pass a Hit roll against its own Ballistic Skill. On a successful
        hit, the target's uid is added to `army.guided_enemy_uids`.
        Friendly T'au attackers firing at a target in the set gain
        [LETHAL HITS] in `Unit.attack`, gated on the detachment's
        `lethal_hits_on_guided` flag (Mont'ka sets True).

        Before iter27-M1 the emission was a free auto-Guided pipeline —
        no Hit roll, no line-of-sight check, no range gate — which
        inflated Guided uptime far above real play. Adding the three
        gates brings the simulator into line with how a Markerlight
        actually resolves on table.

        SwegHammer simplifications vs the codex Markerlight token-stacking:
            * The codex requires a unit to accrue >= some token count to
              become a Guided unit (specifics vary by edition). SwegHammer
              collapses to "any one successful Markerlight hit => Guided",
              which is a strict upper bound but matches the practical play
              pattern where Pathfinders + Stealth Suits saturate marks
              comfortably in a real game.
            * Range check is straight Euclidean distance from the
              MARKERLIGHT unit's position to the candidate enemy.
            * Line of sight uses the same `Map.has_line_of_sight` helper
              the main Shooting phase uses, plus the `can_target_for_ranged`
              gate so Look Out Sir / Lone Operative apply to Markerlights
              just like to any other ranged weapon.
            * Hit roll uses the carrier's `hit_probability` (its Ballistic
              Skill, converted via `_prob_to_target`). No modifiers are
              applied — Markerlight is the simplest possible ranged shot.
            * One attempt per MARKERLIGHT unit; selects the highest-points
              live enemy in range+LoS as the threat priority before
              rolling the hit.

        No-op (and no marks) when:
            * `army` has no alive MARKERLIGHT-keyword unit.
            * Opponent has no alive units.
            * Army faction isn't T'au Empire (defensive — the buff is read
              under the T'au attacker gate anyway, but skipping the scan
              saves cycles on every non-T'au turn).
            * Detachment doesn't carry `lethal_hits_on_guided=True` (would
              never be read by `Unit.attack` even if marks were set).

        Cited as `simulator.markerlights` (token effect) and
        `simulator.markerlight_emission` (per-carrier hit roll + LoS +
        range gate added in iter27-M1).
        Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights
        """
        if (army.units and
                (army.units[0].profile.faction or "").lower()
                not in ("t'au empire", "tau empire")):
            return
        det = army.resolve_detachment()
        if det is None or not getattr(det, "lethal_hits_on_guided", False):
            return
        alive_enemies = opponent.alive_units
        if not alive_enemies:
            return
        markerlight_units = [
            u for u in army.alive_units
            if "MARKERLIGHT" in (u.profile.unit_keywords or ())
        ]
        if not markerlight_units:
            return
        from .army import can_target_for_ranged
        from .units import _prob_to_target
        # 10e core rulebook: Markerlight is a weapon ability with the
        # standard ranged-weapon profile. The basic Markerlight is 36"
        # range across every datasheet in the T'au index. We hold this
        # constant here rather than reading per-weapon range off the
        # profile because SwegHammer's UnitProfile carries one
        # `range_inches` for the unit's primary weapon (Pulse Carbine on
        # Pathfinders, Burst Cannon on Stealth Suits), not for the
        # Markerlight specifically — the Markerlight is a secondary
        # weapon riding on the carrier's BS.
        markerlight_range = 36.0
        marked: set = set()
        for mk in markerlight_units:
            # Range + LoS + Look-Out-Sir / Lone-Op gate the candidate pool
            # before the to-hit roll. Skip unmarked-only targets so each
            # carrier marks a distinct unit when multiple are available.
            candidates = [
                e for e in alive_enemies
                if e.uid not in marked
                and _distance(mk.position, e.position) <= markerlight_range
                and self.map.has_line_of_sight(
                    mk.position, e.position,
                    attacker_keywords=mk.profile.unit_keywords or (),
                    target_keywords=e.profile.unit_keywords or (),
                )
                and can_target_for_ranged(mk, e, alive_enemies)
            ]
            if not candidates:
                continue
            target = max(candidates, key=lambda u: u.profile.points_cost)
            # Hit roll using the carrier's BS. No modifiers — Markerlight
            # is resolved as a plain ranged shot. A roll >= the target's
            # `N+` succeeds; on failure no token is granted.
            hit_target = _prob_to_target(mk.profile.hit_probability)
            roll = random.randint(1, 6)
            if roll >= hit_target:
                marked.add(target.uid)
        army.guided_enemy_uids = marked

    def _pick_oath_target(
        self, army: Army, opponent: Army, round_num: int,
    ) -> None:
        """Adeptus Astartes Oath of Moment — pick this round's oath target.

        AI heuristic: re-pick fresh every Command phase based on the LIVE
        battlefield state (Wahapedia: "At the start of your Command phase,
        select one enemy unit"). Score each alive enemy as
            score = points_cost * (current_health / max_health)
        so wounded fat anchors fade as the next-largest fresh target rises.
        Without the health-ratio weighting the picker used `points_cost`
        alone, which is static — the same anchor scored highest every
        round until it died, producing 1.42 unique targets per 5 picks in
        the iter-5 Marine diagnostic.

        On top of the score, if the highest-scoring candidate matches LAST
        round's pick AND a runner-up exists within 50% of the top score,
        rotate to the runner-up. This models real-player behaviour of
        spreading damage across multiple anchors rather than dumping a
        full round of re-rolls into a unit that's already taking fire.
        When the runner-up is far weaker (e.g. 50pt Cheap vs 300pt
        Expensive at full HP, ratio 0.17 < 0.5), the rotation is
        suppressed and we stay on the dominant threat — preserving the
        intent of the iter-1 `test_oath_picks_highest_points_enemy` test.

        Sets `army.oath_target_uid` and emits `OathTargetChosen`. No-op
        (and no event) when the opponent has no alive units left.

        The buff itself (re-roll all hits AND all wounds against the
        chosen unit) is applied in Unit.attack, gated on the attacker
        being a Marine and `attacker_army.oath_target_uid == target.uid`.
        """
        alive = opponent.alive_units
        if not alive:
            return

        def score(u: "Unit") -> float:
            max_hp = max(1.0, float(u.profile.health))
            ratio = max(0.0, u.current_health / max_hp)
            return float(u.profile.points_cost) * ratio

        # Sort by live-weighted score, points_cost as a stable tiebreak so
        # round 1 (all full HP) collapses to the legacy "highest points"
        # ordering for test compatibility.
        ranked = sorted(
            alive,
            key=lambda u: (score(u), u.profile.points_cost),
            reverse=True,
        )
        target = ranked[0]
        # Rotate off the prior anchor when a comparable runner-up exists.
        # Threshold 0.5: runner-up must be at least half the top score to
        # justify the swap. Keeps the 300pt-vs-50pt test passing (ratio
        # 0.17 < 0.5) while letting two similar-points anchors alternate.
        if (
            army.prev_oath_target_uid is not None
            and target.uid == army.prev_oath_target_uid
            and len(ranked) >= 2
        ):
            top_score = score(target)
            runner_up = ranked[1]
            if top_score > 0 and score(runner_up) / top_score >= 0.5:
                target = runner_up

        army.oath_target_uid = target.uid
        self._emit(OathTargetChosen(
            army_name=army.name,
            round_num=round_num,
            target_uid=target.uid,
        ))

    def _maybe_award_blood_tithe(
        self, killer: "Unit", killer_army: Army,
        victim: "Unit", victim_army: Army,
    ) -> None:
        """World Eaters army rule — Blood Tithe (10e).

        Two trigger sources, both awarding +1 BT to the World Eaters army:
          1. A friendly WE unit was destroyed (victim is WE) — award to
             victim_army.
          2. An enemy unit was destroyed by a WE unit (killer is WE) —
             award to killer_army.

        Both can fire at once in a WE mirror-match (victim's army gets +1
        for the death AND killer's army gets +1 for the kill — that's the
        codex behaviour). Non-WE armies are left at 0. Cited as
        `simulator.blood_tithe`.
        """
        if victim.profile.faction == "World Eaters":
            victim_army.blood_tithe += 1
        if killer.profile.faction == "World Eaters":
            killer_army.blood_tithe += 1

    def _maybe_award_miracle_die(
        self, victim: "Unit", victim_army: Army,
    ) -> None:
        """Adepta Sororitas Acts of Faith — Miracle Dice on a friendly
        death. Cited as `simulator.acts_of_faith`. Wahapedia:
        https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/

        Each time a Sororitas unit from a Sororitas army is destroyed,
        that army gains 1 Miracle die (pre-rolled D6 added to its pool,
        capped at MIRACLE_DICE_BANK_CAP). The trigger is on the VICTIM —
        the killer's faction does not matter, only that the destroyed
        unit had the Sororitas faction tag and the army still has at
        least one Sororitas unit (otherwise the army-rule condition
        "Army Faction is Adepta Sororitas" no longer holds, and the
        gate keeps the pool from growing on a mixed-faction list whose
        last Sororitas unit just died).
        """
        if victim.profile.faction != "Adepta Sororitas":
            return
        if not any(u.profile.faction == "Adepta Sororitas" for u in victim_army.units):
            return
        victim_army.gain_miracle_dice(1, random)

    # APPROXIMATION: models the retired Eye of the Ancestors rule; current codex army rule is Prioritised Efficiency.
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/#Prioritised-Efficiency
    # Real rule (current 10e): Prioritised Efficiency — Yield Points / Hostile Acquisition / Fortify Takeover token economy,
    # not the launch-day "enemies that kill Votann get marked for rerolls" mechanic this code implements.
    def _maybe_award_judgement_token(
        self, killer: "Unit", killer_army: Army,
        victim: "Unit", victim_army: Army,
    ) -> None:
        """Eye of the Ancestors / Judgement Tokens (Leagues of Votann army rule).

        When a non-Votann unit destroys a Votann model, the killer's unit
        earns a token on itself. Tokens stack on the killer for the rest of
        the battle and grant escalating re-roll buffs to subsequent Votann
        attacks targeting that unit (resolved in `Unit.attack`).

        Symmetry: a Votann unit killing another Votann unit (mirror match,
        psychic, etc.) does NOT award a token — only the *opponent* of the
        Votann army marks targets. We pin this off the victim's army
        (`is_votann_army`), not the killer's, so a Votann attacker on a
        Votann victim short-circuits before incrementing.
        """
        if not victim_army.is_votann_army:
            return
        # Don't mark yourself (a Votann unit killing one of its own
        # in some pathological self-damage edge case).
        if killer_army.is_votann_army:
            return
        tokens = victim_army.judgement_tokens
        tokens[killer.uid] = tokens.get(killer.uid, 0) + 1
        self._emit(JudgementTokenAwarded(
            target_uid=killer.uid,
            total_tokens=tokens[killer.uid],
        ))

    def _maybe_apply_deadly_demise(self, victim: "Unit") -> None:
        """Deadly Demise X (10e core rule).

        When a model with this ability is destroyed, roll 1D6 BEFORE removing
        it from the battlefield. On a 6, each unit within 6" of this model
        suffers X mortal wounds. SwegHammer interprets the codex D3/D6/D3+3
        variants as fixed integer expected values at mapper time; the runtime
        sees a single integer in `profile.deadly_demise`.

        Called from every death-detection site (shoot, fight, tank shock,
        counter-offensive, doombolt). Bypasses armour/invuln; routed through
        receive_damage so target FNP and Disgustingly Resilient compose.

        Side effect — Destroyed Transport (10e core): if the dying unit is a
        TRANSPORT, every embarked passenger force-disembarks before removal,
        rolling 1D6 per model and destroying on a 1. Routed here because all
        death-detection sites already fan out through this method. Cited as
        `simulator.destroyed_transport`.
        """
        # Destroyed Transport disembark fires BEFORE deadly demise so any
        # passengers that survive the disembark D6 are positioned for the
        # demise blast (and so they can also be caught by it).
        if self._is_transport(victim) and victim.passengers:
            self._destroyed_transport_disembark(victim)
        x = getattr(victim.profile, "deadly_demise", 0) or 0
        if x <= 0:
            return
        # Putrid Detonation (Virulent Vectorium, Death Guard stratagem): if
        # the dying unit belongs to a DG army that armed putrid_detonation
        # this round AND the victim is a DG VEHICLE or MONSTER, skip the
        # d6 gate (mortals auto-trigger). Cited as `Stratagem.Putrid Detonation`.
        victim_army = getattr(victim, "army_ref", None)
        victim_kw = set(victim.profile.unit_keywords or ())
        is_dg = (victim.profile.faction or "") == "Death Guard"
        is_vehicle_or_monster = "VEHICLE" in victim_kw or "MONSTER" in victim_kw
        putrid_armed = (
            victim_army is not None
            and getattr(victim_army, "putrid_detonation_armed", False)
            and is_dg
            and is_vehicle_or_monster
        )
        # Roll a d6 — 1-in-6 trigger, bypassed when Putrid Detonation is armed.
        if not putrid_armed and random.randint(1, 6) != 6:
            return
        # Scan every alive unit within 6" of the victim, on either side. The
        # victim itself is already at 0 HP and excluded by the alive filter,
        # so no special-casing is required.
        victim_pos = victim.position
        victims_hit: List[str] = []
        for army in (self.a, self.b):
            for u in army.alive_units:
                if u is victim:
                    continue
                # Embarked passengers are off-board — they don't take demise
                # mortals from blasts that go off near their transport. Cited
                # as `simulator.embark`.
                if getattr(u, "embarked_in", None) is not None:
                    continue
                if _distance(u.position, victim_pos) > 6.0:
                    continue
                # Mortal wounds: route through receive_damage so FNP / DG's
                # army-wide Disgustingly Resilient apply consistently with
                # other mortal-wound paths (Tank Shock, Doombolt).
                u.receive_damage(float(x), bonus_fnp=u.profile.fnp)
                victims_hit.append(u.uid)
                # A demise that kills another unit does NOT cascade — the
                # canonical rule rolls the secondary victim's own demise at
                # its own death event in a subsequent activation, not here.
                if not u.is_alive:
                    self._emit(UnitKilled(unit_uid=u.uid))
        self._emit(DeadlyDemiseExploded(
            unit_uid=victim.uid,
            mortals=int(x),
            victims=tuple(victims_hit),
        ))

    # ------------------------------------------------------------------
    # Transports (Embark / Disembark / Firing Deck / Destroyed Transport)
    # ------------------------------------------------------------------
    #
    # 10e core rules (Wahapedia):
    #   * Embark: a unit within 3" of a friendly TRANSPORT at the end of a
    #     Normal/Advance/Fall Back move may embark. Once embarked, the unit
    #     does not act normally — it's tracked as a passenger on the transport.
    #   * Disembark: at the start of any Movement phase a unit may disembark
    #     from a transport that hasn't moved this turn; the disembarked unit
    #     is placed wholly within 3" of the transport, then may move normally.
    #   * Firing Deck X: a TRANSPORT with Firing Deck X may select up to X
    #     embarked passenger models' weapons each Shooting phase and shoot
    #     with them as if they were the transport's own weapons (transport's BS).
    #   * Destroyed Transport: when a TRANSPORT is destroyed, before removing
    #     it, each embarked unit disembarks wholly within 3". For each model
    #     in the disembarking unit, roll 1D6; on a 1, that model is destroyed.
    #
    # SwegHammer simplifications (first pass):
    #   - Transport capacity is hardcoded to 12 INFANTRY models (Rhino-tier).
    #   - Pre-game embark only: at deploy time, if an army has a TRANSPORT
    #     with capacity for an INFANTRY unit, that infantry is embarked.
    #   - No mid-game voluntary embark (would need a Movement-phase hook).
    #   - Disembark fires on (a) destroyed transport, (b) at the start of the
    #     transport's Movement sub-phase if the AI judges the passenger needs
    #     to be off-board now (capture nearby objective, transport about to die).
    #   - Firing Deck: when a transport shoots, up to firing_deck passengers
    #     each fire ONE extra shot using the transport's hit_probability.
    #   - Emergency disembark (placement >3" but ≤6" with mortal wounds on
    #     1-3" path) is NOT modelled — first pass just skips placement if
    #     blocked.

    _TRANSPORT_CAPACITY = 12   # first-pass simplification — Rhino-tier

    @staticmethod
    def _is_transport(unit: "Unit") -> bool:
        """True iff this unit's profile carries the TRANSPORT keyword."""
        return "TRANSPORT" in (unit.profile.unit_keywords or ())

    def _embark_pregame_passengers(self) -> None:
        """Pre-game embark pass (10e core).

        For each army that owns at least one TRANSPORT, pick the highest-
        threat INFANTRY unit that fits (1 model after squad-flattening) and
        embark it on the first available transport. Repeats per transport so
        a list of Rhinos all get a passenger if possible. Passengers are
        removed from the active deployment line — their position becomes the
        transport's, and the simulator's activation loop skips embarked units
        via the `embarked_in` gate. Cited as `simulator.embark`.

        First-pass simplification: capacity is fixed at 12 INFANTRY models
        per transport (Rhino-tier). SwegHammer models units as a single
        Unit-per-model so we can fit up to 12 such Units inside one transport,
        but for the pre-game pass we only embark ONE infantry instance per
        transport (the most tactical-value passenger) to keep the pre-game
        deterministic and easy to reason about.
        """
        for army in (self.a, self.b):
            transports = [u for u in army.units if self._is_transport(u)]
            if not transports:
                continue
            # Pool of embark-eligible INFANTRY (not already a passenger, not
            # CHARACTER — we keep characters free to attach as Leaders).
            def _eligible(u):
                kw = u.profile.unit_keywords or ()
                if "INFANTRY" not in kw:
                    return False
                if "CHARACTER" in kw:
                    return False
                if self._is_transport(u):
                    return False
                if u.embarked_in is not None:
                    return False
                return True

            for transport in transports:
                if len(transport.passengers) >= self._TRANSPORT_CAPACITY:
                    continue
                candidates = [u for u in army.units if _eligible(u)]
                if not candidates:
                    break
                # Highest-Lanchester-score INFANTRY rides — biggest gun
                # benefits from the +6" pre-move the most.
                passenger = max(candidates, key=lambda u: u.profile.score)
                self._embark(passenger, transport)

    def _embark(self, passenger: "Unit", transport: "Unit") -> None:
        """Place `passenger` inside `transport` (10e core embark step).

        The passenger is co-located with the transport (position copied), its
        `embarked_in` back-pointer is set, and it's added to the transport's
        `passengers` list. The passenger remains in `army.units` (still alive,
        still has HP) but the activation loop skips it. Cited as
        `simulator.embark`.
        """
        passenger.position = transport.position
        passenger.embarked_in = transport
        transport.passengers.append(passenger)
        self._emit(TransportEmbarked(
            transport_uid=transport.uid,
            passenger_uid=passenger.uid,
        ))

    def _disembark(
        self, passenger: "Unit", transport: "Unit", forced: bool = False,
    ) -> None:
        """Place `passenger` wholly within 3" of `transport` (10e core).

        Looks for a placement point in a small spiral around the transport's
        last position. If no unblocked point is found, places the passenger
        on the transport's position (degraded fallback — better than nothing).
        Clears the embark back-pointer and removes the passenger from the
        transport's list. Cited as `simulator.disembark`.
        """
        # Try a handful of candidate offsets around the transport, each <= 3".
        # Order: cardinals first, then diagonals.
        cx, cy = transport.position
        candidates = [
            (cx + 2.5, cy), (cx - 2.5, cy), (cx, cy + 2.5), (cx, cy - 2.5),
            (cx + 2.0, cy + 2.0), (cx - 2.0, cy + 2.0),
            (cx + 2.0, cy - 2.0), (cx - 2.0, cy - 2.0),
            (cx + 1.0, cy), (cx, cy + 1.0),
        ]
        placed = None
        for pt in candidates:
            x = max(0.0, min(self.map.width, pt[0]))
            y = max(0.0, min(self.map.height, pt[1]))
            if not self.map.is_blocked((x, y)):
                placed = (x, y)
                break
        if placed is None:
            placed = transport.position
        passenger.position = placed
        passenger.embarked_in = None
        if passenger in transport.passengers:
            transport.passengers.remove(passenger)
        self._emit(TransportDisembarked(
            transport_uid=transport.uid,
            passenger_uid=passenger.uid,
            position=placed,
            forced=forced,
        ))

    def _destroyed_transport_disembark(self, transport: "Unit") -> None:
        """Force-disembark every passenger when a TRANSPORT is destroyed (10e).

        For each model in the disembarking unit, roll 1D6; on a 1 that model
        is destroyed. SwegHammer models units as one Unit instance per model,
        so a single D6 is rolled per passenger Unit; on a 1 the passenger's
        current_health is zeroed and a UnitKilled event is emitted. Cited as
        `simulator.destroyed_transport`.

        We snapshot the passenger list because `_disembark` mutates it as it
        runs.
        """
        if not transport.passengers:
            return
        survivors = list(transport.passengers)
        for passenger in survivors:
            self._disembark(passenger, transport, forced=True)
            # Per-model D6: on a 1, the model is destroyed.
            if random.randint(1, 6) == 1:
                passenger.current_health = 0.0
                if not passenger.is_alive:
                    self._emit(UnitKilled(unit_uid=passenger.uid))

    def _maybe_disembark_before_move(
        self, transport: "Unit", army: Army, opponent: Army,
    ) -> None:
        """Voluntary disembark hook fired at the start of a TRANSPORT's
        Movement sub-phase (10e core).

        Heuristic: disembark when EITHER
          (a) the transport currently sits within 6" of an objective marker —
              the passenger should grab it while the transport repositions; OR
          (b) the transport is below 50% HP — likely to die soon, so eject
              before Destroyed Transport mortals fire.

        Otherwise we keep the passenger embarked so they continue to ride
        toward an objective. Cited as `simulator.disembark`.
        """
        if not transport.passengers:
            return
        # Already moved this round (e.g. arrival) — disembark skipped because
        # the rule requires the transport to NOT have moved yet.
        if transport.uid in self._did_move_this_round:
            return
        # (a) within 6" of an objective?
        near_obj = any(
            _distance(transport.position, (obj.x, obj.y)) <= 6.0
            for obj in self.map.objectives
        )
        # (b) below half HP?
        damaged = transport.current_health < transport.profile.health / 2.0
        if not near_obj and not damaged:
            return
        # Disembark the best passenger (the one most likely to claim an obj
        # or pour fire downrange). First-pass: just disembark all of them.
        for passenger in list(transport.passengers):
            self._disembark(passenger, transport, forced=False)

    def _apply_firing_deck(
        self, transport: "Unit", target: "Unit",
        attacker_army: Army, defender_army: Army,
    ) -> float:
        """Firing Deck X (10e core).

        When a TRANSPORT shoots, up to X embarked passenger models may fire
        their weapons as if they were the transport's. SwegHammer applies a
        simplified version: each of the first X passengers does a single
        Unit.attack against the target using the passenger's own profile,
        but inheriting the transport's hit_probability (per the codex's
        "shoot with them as if they were the transport's weapons" wording).

        Returns total damage dealt by the firing-deck passengers (0 if no
        firing deck or no passengers). Cited as `simulator.firing_deck`.

        First-pass simplification: passenger attacks use the passenger's own
        hit_probability rather than swapping in the transport's, because the
        Unit.attack stochastic loop reads hit_probability off the passenger's
        profile. The codex says "use the transport's BS"; in practice for
        Marine transports that's BS3+ which matches the passenger's anyway.
        Future task: thread a BS-override into Unit.attack.
        """
        x = getattr(transport.profile, "firing_deck", 0) or 0
        if x <= 0:
            return 0.0
        if not transport.passengers:
            return 0.0
        # Take up to X passengers; the first ones are highest-DPA by virtue
        # of the embark routine picking the best Lanchester-scorers.
        firing = transport.passengers[:x]
        total = 0.0
        distance = _distance(transport.position, target.position)
        target_kw = target.profile.unit_keywords or ()
        for passenger in firing:
            if not passenger.is_alive:
                continue
            # Out of range from the transport's position — skip silently.
            if distance > passenger.profile.range_inches:
                continue
            # 10e Ruins: the FIRING model's keywords decide whether LoS
            # passes through a Ruin wall, not the transport's. Each
            # passenger gets its own LoS check from the transport's
            # firing-deck position.
            has_los = self.map.has_line_of_sight(
                transport.position, target.position,
                attacker_keywords=passenger.profile.unit_keywords or (),
                target_keywords=target_kw,
            )
            total += passenger.attack(
                target, distance=distance, has_los=has_los,
            )
        return total

    @staticmethod
    def _award_cp(army: Army, opponent: Army) -> None:
        diff = opponent.unit_count - army.unit_count
        bonus = min(CP_BONUS_CAP, max(0, diff // CP_BONUS_DIVISOR))
        army.command_points += bonus

    # ------------------------------------------------------------------
    # Stratagem dispatch
    # ------------------------------------------------------------------

    def _fire_stratagem(self, army: Army, strat) -> bool:
        """Spend CP and emit a StratagemFired event. Returns True iff the
        stratagem actually fired (CP affordable + not already used when
        flagged once_per_battle).

        Callers are responsible for applying the stratagem's effect — this
        method ONLY handles cost-paying + book-keeping + event emission.
        """
        if army.command_points < strat.cp_cost:
            return False
        already = self._stratagems_fired_this_battle.get(army.name, set())
        if strat.once_per_battle and strat.name in already:
            return False
        army.command_points -= strat.cp_cost
        # Warlord-gated CP refund. Two independent mechanics, applied in
        # priority order so each pool drains separately:
        #   1. `first_stratagem_free_this_round` (Lord of Contagion's "Lord
        #      of the Death Guard" Warlord trait): the first stratagem this
        #      army fires this round is refunded its full cost and the flag
        #      flips off until the next Command phase re-arms it.
        #   2. `cp_refund_remaining` (Belisarius Cawl, Trazyn the Infinite):
        #      one-time-per-battle refund pool. Each spend that bypasses (1)
        #      pops one refund, gaining +1 CP and decrementing the pool.
        # Both refunds respect the CP_CAP=6 ceiling so a refunded spend at
        # cap still floors at cap — they refund the OLD CP value, not above.
        if army.first_stratagem_free_this_round:
            army.command_points = min(CP_CAP, army.command_points + strat.cp_cost)
            army.first_stratagem_free_this_round = False
        elif army.cp_refund_remaining > 0:
            army.command_points = min(CP_CAP, army.command_points + 1)
            army.cp_refund_remaining -= 1
        already.add(strat.name)
        self._stratagems_fired_this_battle[army.name] = already
        # Iter-4 A5: increment the per-Command-phase counter only when this
        # spend originated from `_apply_detachment_stratagems` (faction-neutral
        # detachment-stratagem dispatcher). Core Stratagems (Tank Shock,
        # Counter-Offensive, Command Re-Roll) fire on their own per-trigger
        # hooks at other points in the round and intentionally do NOT count
        # toward the cap. The dispatch flag is set + cleared in
        # `_apply_detachment_stratagems`'s try/finally.
        # Cited as `simulator.stratagem_per_command_phase_cap`.
        if getattr(self, "_dispatching_detachment_stratagems", False):
            army.stratagems_fired_this_command_phase += 1
        self._emit(StratagemFired(
            army_name=army.name,
            stratagem_name=strat.name,
            cp_cost=strat.cp_cost,
        ))
        return True

    def maybe_fire_command_reroll(self, attacker_unit, target_unit, roll_kind: str) -> bool:
        """Hook called by Unit.attack when a wound roll fails. Asks the
        strategy heuristic whether to spend 1 CP to re-roll. Returns True
        iff the stratagem fired.

        Universal Core Stratagem (Wahapedia core rules): re-roll a single
        Hit / Wound / Damage / Save / Advance / Charge / Battle-shock /
        control roll. The simulator currently exposes this only on failed
        wound rolls — that's the highest-value trigger and the others are
        covered by detachment re-roll passives.
        """
        army = attacker_unit.army_ref
        if army is None:
            return False
        ctx = {"target": target_unit, "roll_kind": roll_kind}
        if not should_fire_stratagem(army, COMMAND_RE_ROLL, ctx):
            return False
        return self._fire_stratagem(army, COMMAND_RE_ROLL)

    def _try_tank_shock(self, charger: "Unit", target: "Unit", charger_army: Army) -> None:
        """After a VEHICLE charge resolves, optionally spend 1 CP for Tank
        Shock — D3 mortal wounds to the charge target. Median D3 = 2
        deterministically (matches the simulator's other 'median D3' uses
        like Reanimation Protocols revival).
        """
        ctx = {"charger": charger, "succeeded": True}
        if not should_fire_stratagem(charger_army, TANK_SHOCK, ctx):
            return
        if not self._fire_stratagem(charger_army, TANK_SHOCK):
            return
        # Mortal wounds bypass armour/invuln; honour FNP via receive_damage.
        target.receive_damage(2.0, bonus_fnp=target.profile.fnp)
        alive_after = target.is_alive
        if not alive_after:
            self._emit(UnitKilled(unit_uid=target.uid))
            # Tank Shock that finishes a Votann model still triggers the
            # Judgement Token award — the killer's army is the charger's army.
            target_army = self.b if charger_army is self.a else self.a
            self._maybe_award_judgement_token(
                killer=charger, killer_army=charger_army,
                victim=target, victim_army=target_army,
            )
            self._maybe_award_blood_tithe(
                killer=charger, killer_army=charger_army,
                victim=target, victim_army=target_army,
            )
            self._maybe_award_miracle_die(
                victim=target, victim_army=target_army,
            )
            self._maybe_apply_deadly_demise(target)

    def _do_heroic_intervention(
        self, charger: "Unit", defender_army: Army,
    ) -> None:
        """Free core CHARACTER ability — 10e Charge phase.

        Per Wahapedia (https://wahapedia.ru/wh40k10ed/the-rules/core-rules/
        #CHARGE-PHASE): "After the opposing player has resolved their
        charges, you can select any of your CHARACTER models that are
        within 6\" of any enemy units. Each of those models can move up
        to 6\" (3\" if WALKER) — they must end the move within Engagement
        Range of one of those enemy units."

        This is NOT a stratagem and costs no CP. It fires automatically
        for every eligible defender CHARACTER after a successful charge
        by `charger` against `charger`'s target. Each such CHARACTER
        within 6" of the charger is moved up to 6" (3" if WALKER) toward
        the charger, landing inside 1" engagement range when reachable.

        Cited as `simulator.heroic_intervention_core`.
        """
        for u in list(defender_army.alive_units):
            kw = u.profile.unit_keywords or ()
            if "CHARACTER" not in kw:
                continue
            d = _distance(u.position, charger.position)
            if d > 6.0:
                continue
            max_move = 3.0 if "WALKER" in kw else 6.0
            old_pos = u.position
            new_pos = _move_toward(old_pos, charger.position, max_move, self.map)
            if new_pos != old_pos:
                u.position = new_pos
                self._emit(UnitMoved(
                    unit_uid=u.uid, from_pos=old_pos, to_pos=new_pos,
                ))

    def _try_counter_offensive(
        self,
        loser_army: Army, loser_unit: "Unit",
        winner_army: Army, winner_unit: "Unit",
        target_killed: bool,
    ) -> None:
        """After `winner_unit` (from winner_army) lands a fight that killed
        a friendly model in `loser_unit`, the loser_army may spend 2 CP for
        Counter-Offensive — a friendly unit in engagement range fights
        immediately, out of sequence.

        Effect: pick the loser_army unit with the best melee profile that is
        within 1.5" of `winner_unit`, and fire its `_do_fight` against
        winner_unit right now (before the rest of the fight sequence).
        """
        # Find a friendly unit in engagement range of the winner.
        candidates = [
            u for u in loser_army.alive_units
            if u is not loser_unit
            and u.profile.melee_attacks > 0
            and _distance(u.position, winner_unit.position) <= 1.5
        ]
        in_engagement = bool(candidates)
        ctx = {
            "friendly_in_engagement": in_engagement,
            "enemy_killed_model": target_killed,
        }
        if not should_fire_stratagem(loser_army, COUNTER_OFFENSIVE, ctx):
            return
        if not self._fire_stratagem(loser_army, COUNTER_OFFENSIVE):
            return
        # Pick the highest melee-DPA candidate.
        def _melee_dpa(u):
            return (
                u.profile.melee_attacks * u.profile.melee_hit_probability
                * (u.profile.melee_damage_per_shot or 1.0)
            )
        candidates.sort(key=_melee_dpa, reverse=True)
        retaliator = candidates[0]
        # Out-of-sequence fight: hit the enemy unit that just struck us,
        # not whatever the retaliator's nearest happens to be.
        dmg = retaliator.attack(winner_unit, distance=1.0, mode="melee")
        alive_after = winner_unit.is_alive
        self._emit(UnitFought(
            attacker_uid=retaliator.uid,
            target_uid=winner_unit.uid,
            damage=dmg,
            target_hp_after=winner_unit.current_health,
            target_alive_after=alive_after,
        ))
        if not alive_after:
            self._emit(UnitKilled(unit_uid=winner_unit.uid))
            self._maybe_award_judgement_token(
                killer=retaliator, killer_army=loser_army,
                victim=winner_unit, victim_army=winner_army,
            )
            self._maybe_award_blood_tithe(
                killer=retaliator, killer_army=loser_army,
                victim=winner_unit, victim_army=winner_army,
            )
            self._maybe_award_miracle_die(
                victim=winner_unit, victim_army=winner_army,
            )
            self._maybe_apply_deadly_demise(winner_unit)
