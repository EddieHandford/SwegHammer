"""Battle simulator: unit-by-unit activation with movement and event emission."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .army import Army
from .events import (
    BattleEnded, BattleStarted, BattleshockFailed, InitialUnit,
    JudgementTokenAwarded, ObjectiveScored, RoundEnded, RoundStarted,
    StratagemFired, Subscriber, UnitActivated, UnitAdvanced, UnitCharged,
    UnitDeepStrike, UnitFought, UnitInfiltrated, UnitKilled, UnitMoved,
    UnitReanimated, UnitScouted, UnitShot, WaaaghDeclared,
)
from .map import Map, TerrainType
from .maps import DEFAULT_MAP
from .strategy import pick_move_intent, should_declare_waaagh, should_fire_stratagem
from .stratagems import (
    COMMAND_RE_ROLL, COUNTER_OFFENSIVE, HEROIC_INTERVENTION, TANK_SHOCK,
    # Cult of Magic (Thousand Sons)
    DOOMBOLT, TWIST_OF_FATE, GLAMOUR_OF_TZEENTCH,
    # Plague Company (Death Guard)
    DISGUSTINGLY_RESILIENT, PLAGUE_WEAPONS, OUTBREAK_OF_PESTILENCE,
    # Battle Host (Aeldari)
    LIGHTNING_FAST_REACTIONS, FIRE_AND_FADE, MATCHLESS_AGILITY,
    award_command_phase_cp,
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
    ) -> None:
        self.a = army_a
        self.b = army_b
        self.verbose = verbose
        self.subscribers: List[Subscriber] = list(subscribers) if subscribers else []
        self.map: Map = map_ or DEFAULT_MAP
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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> BattleResult:
        # Battle Focus tokens (Aeldari ASURYANI rule): 4 at Strike Force,
        # the default battle size for this simulator. We hand the tokens
        # out to any army that contains at least one ASURYANI unit — the
        # rule is faction-wide, not detachment-gated.
        for army in (self.a, self.b):
            if any("ASURYANI" in (u.profile.unit_keywords or ())
                   for u in army.units):
                army.battle_focus_tokens = 4

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
                ))
            for u in self._reserves.get(army.name, []):
                snapshot.append(InitialUnit(
                    uid=u.uid, name=u.profile.name, army=army.name,
                    position=(-100.0, -100.0),
                    max_health=u.profile.health,
                    unit_keywords=tuple(u.profile.unit_keywords or ()),
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
        """
        for obj_idx, obj in enumerate(self.map.objectives):
            obj_pos = (obj.x, obj.y)
            r2 = obj.control_radius * obj.control_radius
            a_oc = 0
            b_oc = 0
            a_sticky_present = False
            b_sticky_present = False
            for u in self.a.alive_units:
                if u.uid in self._battleshocked_this_round:
                    continue   # Battleshocked = OC 0
                dx = u.position[0] - obj_pos[0]
                dy = u.position[1] - obj_pos[1]
                if dx * dx + dy * dy <= r2:
                    a_oc += getattr(u.profile, "oc", 1) or 1
                    if getattr(u.profile, "sticky_objective", False):
                        a_sticky_present = True
            for u in self.b.alive_units:
                if u.uid in self._battleshocked_this_round:
                    continue
                dx = u.position[0] - obj_pos[0]
                dy = u.position[1] - obj_pos[1]
                if dx * dx + dy * dy <= r2:
                    b_oc += getattr(u.profile, "oc", 1) or 1
                    if getattr(u.profile, "sticky_objective", False):
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
            if a_sticky_present and a_oc >= b_oc and a_oc > 0:
                self._sticky_owner[obj_idx] = self.a.name
            elif b_sticky_present and b_oc >= a_oc and b_oc > 0:
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

    def _apply_detachment_stratagems(self, army: Army, opponent: Army) -> None:
        """Round-start dispatcher for detachment-specific stratagems.

        Each detachment's stratagem tuple is iterated; the simulator's
        per-stratagem `_try_*` helpers consult the AI heuristic in
        `strategy.should_fire_stratagem` and, if green-lit, spend CP and
        apply the transient effect for the round.

        We bundle the dispatch here rather than scattering it across the
        sub-phase methods because all three detachments' high-impact
        stratagems are best modelled as "decide once per round, apply for
        the round" — round-scoped buffs match the calibration target
        (close the under-rating without inflating turn-by-turn variance).
        """
        det = army.resolve_detachment()
        if det is None or not det.stratagems:
            return
        strat_names = {s.name for s in det.stratagems}

        # ----- Cult of Magic (Thousand Sons) -----------------------------
        if "Doombolt" in strat_names:
            self._try_doombolt(army, opponent)
        if "Twist of Fate" in strat_names:
            self._try_twist_of_fate(army, opponent)
        if "Glamour of Tzeentch" in strat_names:
            self._try_glamour_of_tzeentch(army, opponent)

        # ----- Plague Company (Death Guard) ------------------------------
        if "Disgustingly Resilient" in strat_names:
            self._try_disgustingly_resilient(army, opponent)
        if "Plague Weapons" in strat_names:
            self._try_plague_weapons(army, opponent)
        if "Outbreak of Pestilence" in strat_names:
            self._try_outbreak_of_pestilence(army, opponent)

        # ----- Battle Host (Aeldari) ------------------------------------
        if "Lightning-Fast Reactions" in strat_names:
            self._try_lightning_fast_reactions(army, opponent)
        if "Fire and Fade" in strat_names:
            self._try_fire_and_fade(army, opponent)
        if "Matchless Agility" in strat_names:
            self._try_matchless_agility(army, opponent)

    # ----- target-selection helpers used by the dispatchers --------------

    @staticmethod
    def _highest_threat_enemy(opponent: Army):
        """Pick the alive enemy unit with the highest role-weighted threat.

        Same role-weighting as `_apply_psychic_phase` so Doombolt and any
        future MW-payload stratagem agree on what counts as a worthwhile
        target — heavy / shooty / wounded enemies first, hordes last.
        """
        from .roles import classify
        ROLE_THREAT = {"HEAVY": 3.0, "SHOOTY": 2.0, "DUAL": 1.5,
                       "MELEE": 1.0, "SUPPORT": 1.2, "HORDE": 0.6}
        targets = list(opponent.alive_units)
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

    @classmethod
    def _highest_dpa_unit(cls, army: Army, keyword: str = "", faction: str = ""):
        """Pick the alive friendly unit with the highest melee+ranged DPA.

        Optional `keyword`/`faction` filter restricts to units carrying
        that keyword (e.g. PSYKER) or belonging to that faction
        (e.g. "Aeldari") so a Battle Host army with stray non-Aeldari
        allies still targets the right detachment. See
        `_unit_matches_filter` for the lookup logic.
        """
        candidates = [
            u for u in army.alive_units
            if cls._unit_matches_filter(u, keyword=keyword, faction=faction)
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

    @classmethod
    def _most_vulnerable_unit(cls, army: Army, keyword: str = "", faction: str = ""):
        """Pick the alive friendly unit most likely to benefit from a
        defensive stratagem — wounded + high-value.

        Score: (points_cost) × (1.0 - current_health/max_health). A unit at
        full HP gets 0 (no buff needed); a Knight at 30% HP scores very
        high. Restricted to units matching the keyword/faction filter.
        """
        candidates = [
            u for u in army.alive_units
            if cls._unit_matches_filter(u, keyword=keyword, faction=faction)
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

    def _try_doombolt(self, army: Army, opponent: Army) -> None:
        """Doombolt (Cult of Magic): D3 mortal wounds (median 2) to the
        highest-threat enemy unit. Fires once per round if the army has at
        least one alive PSYKER unit and a viable target exists."""
        has_psyker = any(
            "PSYKER" in (u.profile.unit_keywords or ())
            for u in army.alive_units
        )
        if not has_psyker:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"target": target, "has_psyker": True}
        if not should_fire_stratagem(army, DOOMBOLT, ctx):
            return
        if not self._fire_stratagem(army, DOOMBOLT):
            return
        target.receive_damage(2.0, bonus_fnp=target.profile.fnp)
        if not target.is_alive:
            self._emit(UnitKilled(unit_uid=target.uid))

    def _try_twist_of_fate(self, army: Army, opponent: Army) -> None:
        """Twist of Fate (Cult of Magic): +1 to wound on a friendly TSons
        unit's shooting for the round. Picks the highest-DPA THOUSAND SONS
        attacker so the buff lands on the biggest gun in the army."""
        attacker = self._highest_dpa_unit(
            army, keyword="THOUSAND SONS", faction="Thousand Sons",
        )
        if attacker is None:
            # Fall back to highest-DPA in the whole army (faction tag may
            # be missing on some datasheets after BSData parsing).
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, TWIST_OF_FATE, ctx):
            return
        if not self._fire_stratagem(army, TWIST_OF_FATE):
            return
        attacker.transient_plus_one_to_wound_shooting = True

    def _try_glamour_of_tzeentch(self, army: Army, opponent: Army) -> None:
        """Glamour of Tzeentch (Cult of Magic, 2 CP): transient 4++ invuln
        on the most vulnerable friendly TSons unit for the round."""
        target = self._most_vulnerable_unit(
            army, keyword="THOUSAND SONS", faction="Thousand Sons",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, GLAMOUR_OF_TZEENTCH, ctx):
            return
        if not self._fire_stratagem(army, GLAMOUR_OF_TZEENTCH):
            return
        target.transient_invuln_4 = True

    def _try_disgustingly_resilient(self, army: Army, opponent: Army) -> None:
        """Disgustingly Resilient (Plague Company): -1 damage taken on a
        DEATH GUARD unit for the round. Picks the most vulnerable DG unit."""
        target = self._most_vulnerable_unit(
            army, keyword="DEATH GUARD", faction="Death Guard",
        )
        if target is None:
            target = self._most_vulnerable_unit(army)
        if target is None:
            return
        ctx = {"target": target}
        if not should_fire_stratagem(army, DISGUSTINGLY_RESILIENT, ctx):
            return
        if not self._fire_stratagem(army, DISGUSTINGLY_RESILIENT):
            return
        target.transient_minus_one_damage_taken = True

    def _try_plague_weapons(self, army: Army, opponent: Army) -> None:
        """Plague Weapons (Plague Company): +1 to wound on a friendly DG
        unit's shooting for the round."""
        attacker = self._highest_dpa_unit(
            army, keyword="DEATH GUARD", faction="Death Guard",
        )
        if attacker is None:
            attacker = self._highest_dpa_unit(army)
        if attacker is None:
            return
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, PLAGUE_WEAPONS, ctx):
            return
        if not self._fire_stratagem(army, PLAGUE_WEAPONS):
            return
        attacker.transient_plus_one_to_wound_shooting = True

    def _try_outbreak_of_pestilence(self, army: Army, opponent: Army) -> None:
        """Outbreak of Pestilence (Plague Company): +1 to wound on a
        friendly DG unit's melee attacks for the round."""
        # Pick the friendly DG melee threat — highest melee-DPA unit so the
        # +1 to wound lands where it does the most work.
        candidates = [
            u for u in army.alive_units
            if self._unit_matches_filter(u, keyword="DEATH GUARD", faction="Death Guard")
            and u.profile.melee_attacks > 0
        ]
        if not candidates:
            candidates = [
                u for u in army.alive_units
                if u.profile.melee_attacks > 0
            ]
        if not candidates:
            return

        def _melee_dpa(u):
            p = u.profile
            return (p.melee_attacks * p.melee_hit_probability
                    * (p.melee_damage_per_shot or 0.0))
        attacker = max(candidates, key=_melee_dpa)
        target = self._highest_threat_enemy(opponent)
        if target is None:
            return
        ctx = {"attacker": attacker, "target": target}
        if not should_fire_stratagem(army, OUTBREAK_OF_PESTILENCE, ctx):
            return
        if not self._fire_stratagem(army, OUTBREAK_OF_PESTILENCE):
            return
        attacker.transient_plus_one_to_wound_melee = True

    def _try_lightning_fast_reactions(self, army: Army, opponent: Army) -> None:
        """Lightning-Fast Reactions (Battle Host): +1 save on the most
        vulnerable AELDARI unit for the round."""
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
        """Fire and Fade (Battle Host): re-roll failed hits on a friendly
        AELDARI unit's shooting for the round (approximating the canonical
        shoot-then-move-6" via offensive uplift)."""
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

    def _try_matchless_agility(self, army: Army, opponent: Army) -> None:
        """Matchless Agility (Battle Host): transient Assault keyword on
        a friendly AELDARI unit for the round (advance + shoot)."""
        # Only worth firing on a unit that might want to Advance — i.e. one
        # currently OUT of weapon range of the nearest enemy. Otherwise the
        # transient Assault is wasted and we leak CP.
        candidates = [
            u for u in army.alive_units
            if self._unit_matches_filter(u, keyword="AELDARI", faction="Aeldari")
            and u.profile.range_inches >= 12   # actual shooter, not melee-only
            and not u.profile.assault          # already-Assault gains nothing
        ]
        if not candidates:
            return
        # Pick one whose nearest enemy is out of weapon range — Matchless
        # Agility is a "close the gap and still shoot" stratagem.
        def _wants_advance(u):
            if not opponent.alive_units:
                return False
            nearest = min(
                opponent.alive_units,
                key=lambda e: _distance(u.position, e.position),
            )
            return _distance(u.position, nearest.position) > u.profile.range_inches
        viable = [u for u in candidates if _wants_advance(u)]
        if not viable:
            return
        attacker = max(viable, key=lambda u: float(u.profile.points_cost))
        ctx = {"attacker": attacker}
        if not should_fire_stratagem(army, MATCHLESS_AGILITY, ctx):
            return
        if not self._fire_stratagem(army, MATCHLESS_AGILITY):
            return
        attacker.transient_assault_this_round = True

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

    def _apply_reanimation(self) -> None:
        """End-of-round model revival for Reanimation Protocols armies.

        Real 10e rule: at the start of each Command Phase, REANIMATION-keyword
        units restore D3 destroyed wounds. We model squads as N separate
        single-model `Unit` instances, so "restore D3 wounds" maps to "revive
        D3 destroyed models per profile". We use median D3 = 2 deterministically
        to keep round-to-round outcomes reproducible under a fixed seed.

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
                # Median D3 roll = 2. Cap by however many are actually dead.
                to_revive = min(destroyed, 2)
                dead_pool = dead_by_profile.get(profile_name, [])
                # Anchor at the first alive peer (squad still has at least
                # one model since the wipe-out short-circuit above).
                alive_peers = alive_by_profile[profile_name]
                anchor_pos: Tuple[float, float] = alive_peers[0].position
                if self.map.is_blocked(anchor_pos):
                    anchor_pos = (edge_x, edge_y)
                for revived in dead_pool[:to_revive]:
                    revived.current_health = revived.profile.health
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
        """
        a_y = self.map.deployment_width / 2.0
        b_y = self.map.height - self.map.deployment_width / 2.0

        # Pull deep-strikers out of each army into reserves.
        for army in (self.a, self.b):
            standard, reserves = [], []
            for u in army.units:
                if u.profile.deep_strike:
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
        """Bring Deep Strike reserves onto the board starting Round 2. Each
        unit is placed > 9" from every alive enemy. Picks the centre of the
        board first; if it's too close to an enemy, tries each board corner
        and falls back to a coarse grid sweep. Units that just arrived are
        flagged in `_fresh_arrivals` so they skip movement this round.
        """
        if round_num < 2:
            return
        for army, opponent in ((self.a, self.b), (self.b, self.a)):
            waiting = self._reserves.get(army.name, [])
            if not waiting:
                continue
            still_waiting = []
            for u in waiting:
                # 66% chance to arrive each round from Round 2; forced
                # arrival from Round 4 onwards (10e: reserves must come on
                # by end of Round 3 or are destroyed — we soft-enforce by
                # auto-arriving). Avoids dumping the whole army turn 2.
                if round_num >= 4 or random.random() < 0.66:
                    pos = self._pick_arrival_point(opponent, arriving_unit=u)
                    if pos is None:
                        # No valid arrival spot — defer to next round.
                        still_waiting.append(u)
                        continue
                    u.position = pos
                    army.units.append(u)
                    self._fresh_arrivals.add(u.uid)
                    self._emit(UnitDeepStrike(unit_uid=u.uid, position=pos))
                else:
                    still_waiting.append(u)
            self._reserves[army.name] = still_waiting

    def _pick_arrival_point(
        self, opponent: Army, arriving_unit: Optional[Unit] = None,
    ) -> Optional[Tuple[float, float]]:
        """Pick a tactically-useful Deep Strike landing point.

        Generates a dense grid of legal candidates (>9" from every enemy,
        not in impassable terrain) and scores each by:

          * Proximity to high-threat enemies (SHOOTY/HEAVY weighted up).
            For a melee-capable arriving unit, "closer-to-a-threat" wins —
            we want to land into charge range of a sniper or Knight.
          * Proximity to uncontested objectives.
            For a shooty arriving unit, this dominates — drop and claim.

        Falls back to the legacy centre-then-corners pick if no candidates
        are valid (e.g. a tiny board mid-late game).
        """
        from .roles import classify  # local import to avoid circular at module load

        enemies = opponent.alive_units
        min_gap = 9.0

        def _valid(p: Tuple[float, float]) -> bool:
            if p[0] < 1.0 or p[0] > self.map.width - 1.0:
                return False
            if p[1] < 1.0 or p[1] > self.map.height - 1.0:
                return False
            if self.map.is_blocked(p):
                return False
            for e in enemies:
                if _distance(p, e.position) <= min_gap:
                    return False
            return True

        # Threat weight per enemy: SHOOTY/HEAVY are the prime ambush targets
        # (sniping our backline / kiting), MELEE less so (already coming to
        # us), SUPPORT a useful kill but lower priority.
        def _threat_weight(enemy: Unit) -> float:
            role = classify(enemy.profile)
            base = {
                "HEAVY":   3.0,
                "SHOOTY":  2.5,
                "DUAL":    1.5,
                "MELEE":   1.0,
                "SUPPORT": 1.2,
                "HORDE":   0.8,
            }.get(role, 1.0)
            # Wounded enemies are more attractive — easier finishers.
            hp_frac = max(0.1, enemy.current_health / max(1.0, enemy.profile.health))
            return base * (1.5 - 0.5 * hp_frac)   # full HP -> 1.0×, near-dead -> 1.45×

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

        def _score(p: Tuple[float, float]) -> float:
            s = 0.0
            for e in enemies:
                d = _distance(p, e.position)
                # Add 5" softener so the score doesn't blow up at the 9" boundary.
                s += _threat_weight(e) * threat_w / (d - 4.0)
            for obj in targetable_objs:
                d = _distance(p, (obj.x, obj.y))
                s += objective_w / (d + 4.0)
            return s

        # Dense candidate grid (~3" spacing). Cheap; runs at most ~5 times
        # per battle when reserves arrive.
        best: Optional[Tuple[float, float]] = None
        best_score = -1e9
        step = 3.0
        x = 2.0
        while x < self.map.width - 1.0:
            y = 2.0
            while y < self.map.height - 1.0:
                p = (x, y)
                if _valid(p):
                    sc = _score(p)
                    if sc > best_score:
                        best_score = sc
                        best = p
                y += step
            x += step

        if best is not None:
            return best

        # Fall back to the legacy "any legal spot" pick when no candidates
        # found (very small board or saturated with enemies).
        cx, cy = self.map.width / 2.0, self.map.height / 2.0
        for cand in (
            (cx, cy),
            (3.0, 3.0),
            (self.map.width - 3.0, 3.0),
            (3.0, self.map.height - 3.0),
            (self.map.width - 3.0, self.map.height - 3.0),
        ):
            if _valid(cand):
                return cand
        return None

    # ------------------------------------------------------------------
    # Round logic
    # ------------------------------------------------------------------

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

        # ---- Command phase: each army gains 1 CP (capped at 6). 10e core
        # rule. Starting CP (3 = Strike Force standard) is set by
        # Army.__init__; this is the per-round drip on top. The smaller-army
        # CP bonus is a separate SwegHammer-specific catch-up mechanism
        # awarded later by _award_cp.
        award_command_phase_cp(self.a)
        award_command_phase_cp(self.b)
        # ---- Orks WAAAGH! once-per-battle declaration (Command phase).
        # 10e Orks army rule: declared at the start of a Command phase, once
        # per battle. While active until the end of that turn, Ork attackers
        # gain +1 to wound in melee (the simulator-side gate; +1 to charge
        # rolls and Advance-counts-as-charge are descriptive — see
        # `simulator.waaagh` citation). The AI fires per `should_declare_waaagh`.
        for army in (self.a, self.b):
            if any(u.profile.faction == "Orks" for u in army.units):
                if should_declare_waaagh(army, round_num):
                    army.waaagh_round_unlocked = round_num
                    self._emit(WaaaghDeclared(
                        army_name=army.name, round_num=round_num,
                    ))
        # Clear any per-round transient stratagem flags from the previous
        # round (Disgustingly Resilient, Lightning-Fast Reactions, etc.)
        # before deciding whether to spend CP on a new batch this round.
        self._clear_transient_stratagem_flags(self.a)
        self._clear_transient_stratagem_flags(self.b)
        # Detachment-specific stratagems that fire at the start of a round
        # (Cult of Magic, Plague Company, Battle Host). Doombolt also fires
        # here as a per-round mortal-wound payload — it's nominally a
        # Shooting-phase trigger but the simulator's per-round dispatcher
        # is the cleanest hook for a deterministic "once per round" spend.
        self._apply_detachment_stratagems(self.a, self.b)
        self._apply_detachment_stratagems(self.b, self.a)
        # Phase I — fresh arrivals from the scout phase carry over INTO
        # Round 1 (set by _run_scout_phase). From Round 2 onwards we reset
        # the set first, THEN call _arrive_from_reserves so units arriving
        # this round are flagged for "skip movement" but those that arrived
        # last round are eligible to move normally.
        if round_num >= 2:
            self._fresh_arrivals = set()
            self._arrive_from_reserves(round_num)
        for army in (self.a, self.b):
            for u in army.units:
                u.moved_this_round = False

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

        # Battleshock phase (after Round 1). 10e core rule: any unit Below
        # Half-Strength tests; pass on 2d6 >= Ld. We treat each Unit
        # instance as a stand-in for a single squad member; "below half
        # strength" maps to "current HP < starting HP / 2".
        # Detachment modifiers compose: own ld_bonus LOWERS our test target
        # (easier pass); opponent's enemy_ld_penalty RAISES it (harder pass).
        #
        # Mob Rule (Orks army rule, 10e): an Ork unit with 10+ models on the
        # battlefield auto-passes its Battle-shock test — no roll, no chance
        # of failure. SwegHammer models each squad member as a separate Unit
        # instance, so "10+ models" maps to "10+ alive Ork units in the same
        # army". When that threshold is met, every Ork unit in the army skips
        # the roll regardless of its own current_health. Cited as
        # `simulator.mob_rule`.
        #
        # Synapse Imperative (Tyranids army rule, 10e): a Tyranid unit within
        # 6" of any friendly SYNAPSE model cannot be Battle-shocked — it
        # auto-passes. Cited as `simulator.synapse_imperative`.
        #
        # Shadow in the Warp (Tyranids army rule, 10e): an enemy unit within
        # 12" of any SYNAPSE model from the Tyranid army takes its Battle-shock
        # test at -1 (i.e. the test target is raised by 1, making the pass
        # harder). Cited as `simulator.shadow_in_the_warp`.
        if round_num > 1:
            for army, opponent in ((self.a, self.b), (self.b, self.a)):
                opponent_det = opponent.resolve_detachment()
                own_det = army.resolve_detachment()
                ld_penalty = opponent_det.enemy_ld_penalty if opponent_det else 0
                ld_bonus = own_det.ld_bonus if own_det else 0
                # Mob Rule check: count alive Ork models army-wide.
                ork_count = sum(
                    1 for u in army.alive_units if u.profile.faction == "Orks"
                )
                mob_rule_active = ork_count >= 10
                # SYNAPSE pools — own-side (Synapse Imperative shelter) and
                # opposing-side (Shadow in the Warp penalty). We snapshot
                # the alive SYNAPSE units once per army before iterating so
                # the inner loop only re-evaluates the per-target distance.
                own_synapse = [
                    s for s in army.alive_units
                    if "SYNAPSE" in (s.profile.unit_keywords or ())
                ]
                shadow_sources = [
                    s for s in opponent.alive_units
                    if "SYNAPSE" in (s.profile.unit_keywords or ())
                    and s.profile.faction == "Tyranids"
                ]
                for u in army.alive_units:
                    if u.current_health < u.profile.health / 2.0:
                        # Mob Rule short-circuit: Ork units auto-pass when the
                        # army has 10+ Ork models on the battlefield.
                        if mob_rule_active and u.profile.faction == "Orks":
                            continue
                        # Synapse Imperative: a Tyranid unit within 6" of any
                        # friendly SYNAPSE model auto-passes. Faction-gated
                        # so a non-Tyranid drifting near a stray SYNAPSE
                        # unit doesn't inherit the shelter.
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
                        # Shadow in the Warp: enemy units within 12" of any
                        # SYNAPSE model from the Tyranid army take the test
                        # at -1 (raises the test target by 1).
                        shadow_penalty = 0
                        if shadow_sources and any(
                            _distance(u.position, s.position) <= 12.0
                            for s in shadow_sources
                        ):
                            shadow_penalty = 1
                        roll = random.randint(1, 6) + random.randint(1, 6)
                        target = (
                            u.profile.leadership
                            + ld_penalty
                            - ld_bonus
                            + shadow_penalty
                        )
                        if roll < target:
                            self._battleshocked_this_round.add(u.uid)
                            self._emit(BattleshockFailed(
                                unit_uid=u.uid, roll=roll, target=target,
                            ))

        first, second = (
            (self.a, self.b) if random.random() < 0.5 else (self.b, self.a)
        )

        first_activated: set = set()
        second_activated: set = set()

        while True:
            first_q = first.activation_queue(first_activated)
            second_q = second.activation_queue(second_activated)
            if not first_q and not second_q:
                break

            # Pick the next attacker on each side for this pair
            first_unit = first_q[0] if first_q else None
            second_unit = second_q[0] if second_q else None
            if first_unit is not None:
                first_activated.add(id(first_unit))
            if second_unit is not None:
                second_activated.add(id(second_unit))

            # ---- MOVEMENT sub-phase: both move before either shoots ----
            # This avoids the "second mover sees an updated target position"
            # asymmetry that would otherwise let the second player close into
            # range while the first player can't.
            if first_unit is not None and first_unit.is_alive:
                self._do_move(first_unit, first, second)
            if second_unit is not None and second_unit.is_alive:
                self._do_move(second_unit, second, first)

            # ---- SHOOTING sub-phase: both shoot from their new positions ----
            if first_unit is not None and first_unit.is_alive:
                self._do_shoot(first_unit, first, second)
            if second_unit is not None and second_unit.is_alive:
                self._do_shoot(second_unit, second, first)

            # ---- CHARGE sub-phase: both attempt charges if they want melee ----
            if first_unit is not None and first_unit.is_alive:
                self._do_charge(first_unit, first, second)
            if second_unit is not None and second_unit.is_alive:
                self._do_charge(second_unit, second, first)

            # ---- FIGHT sub-phase: chargers fight first, then others ----
            if first_unit is not None and first_unit.is_alive:
                self._do_fight(first_unit, first, second)
            if second_unit is not None and second_unit.is_alive:
                self._do_fight(second_unit, second, first)

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

        if round_num > 1:
            self._award_cp(self.a, self.b)
            self._award_cp(self.b, self.a)

    # ------------------------------------------------------------------
    # Sub-phases
    # ------------------------------------------------------------------

    def _do_move(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        self._emit(UnitActivated(
            unit_uid=attacker.uid,
            army_name=attacker_army.name,
        ))

        # Phase I: units that arrived from reserves THIS round, or scouted
        # at the start of the game (Round 1), already moved as part of that
        # ability — skip their normal-move sub-phase for one activation.
        if attacker.uid in self._fresh_arrivals:
            return

        # Strategy layer (code/strategy.py): role + objective-aware pick of
        # where this unit wants to go. The simulator USED to always march at
        # the nearest enemy, which abandoned objectives and lost VP. Now units
        # consult their role + the live objective state.
        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return
        target_pos, intent = pick_move_intent(
            attacker, attacker_army, defender_army, self.map,
        )

        dist = _distance(attacker.position, target_pos)
        if dist < 0.5 or intent == "HOLD":
            return   # already where we want to be — stay and shoot

        # 10e Advance: roll d6, move M+d6, but skip shoot/charge this turn.
        # We Advance only when a normal move would NOT bring us into shooting
        # range of the target — the speed boost is wasted otherwise and the
        # shoot foregone.
        normal_move = attacker.profile.move
        # For ENGAGE intent, "in range" = weapon range. For CAPTURE/STEAL,
        # "in range" = within the objective's control radius (we want to be on
        # the marker). REPOSITION is a small jiggle (always normal-move).
        if intent in ("ENGAGE", "REPOSITION"):
            range_threshold = attacker.profile.range_inches
        else:
            range_threshold = 3.0   # objective control radius
        needs_to_close = dist - range_threshold
        advance_d6 = random.randint(1, 6) if needs_to_close > normal_move else 0
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

    def _do_shoot(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        # 10e: a unit that Advanced this turn cannot shoot, unless its weapon
        # is Assault — or the unit's army can spend a Battle Focus token to
        # treat its weapons as [ASSAULT] for the turn (Aeldari rule) — or
        # Matchless Agility (Battle Host stratagem) has been fired this
        # round to grant transient Assault.
        if attacker.uid in self._advanced_this_round and not attacker.profile.assault:
            kw = attacker.profile.unit_keywords or ()
            if attacker.transient_assault_this_round:
                pass   # stratagem already paid for; no token spend
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
        # Indirect Fire lets us target units we cannot see; otherwise LoS is
        # required. The has_los flag is plumbed into Unit.attack so it can
        # apply the -1 to hit when shooting blind.
        if attacker.profile.indirect_fire:
            candidates = [
                u for u in defender_army.alive_units
                if _distance(attacker.position, u.position) <= rng
            ]
        else:
            candidates = [
                u for u in defender_army.alive_units
                if _distance(attacker.position, u.position) <= rng
                and self.map.has_line_of_sight(attacker.position, u.position)
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
        shoot_target = min(contesting or candidates, key=lambda u: u.current_health)

        # Terrain-aware cover: target counts as in cover if it stands inside
        # cover terrain, OR if the army-wide cover flag is set. HEAVY cover
        # also imposes -1 to hit on the attacker (handled in Unit.attack via
        # the in_heavy_cover flag).
        saved_cover = shoot_target.in_cover
        saved_heavy = shoot_target.in_heavy_cover
        cover_type = self.map.cover_at(shoot_target.position)
        if cover_type in (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER):
            shoot_target.in_cover = True
        if cover_type is TerrainType.HEAVY_COVER:
            shoot_target.in_heavy_cover = True

        distance = _distance(attacker.position, shoot_target.position)
        has_los = self.map.has_line_of_sight(attacker.position, shoot_target.position)
        dmg = attacker.attack(shoot_target, distance=distance, has_los=has_los)
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

        if self.verbose:
            alive_str = (
                "killed" if not shoot_target.is_alive
                else f"{shoot_target.current_health:.2f}hp left"
            )
            print(
                f"  {attacker_army.name}: {attacker.profile.name}"
                f" -> {shoot_target.profile.name} ({dmg:.2f} dmg, {alive_str})"
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
        if not self._wants_to_charge(attacker):
            return
        if attacker.uid in self._advanced_this_round:
            return   # advanced units cannot charge

        from .strategy import pick_charge_target
        target, dist = pick_charge_target(attacker, defender_army)
        if target is None:
            return

        roll = random.randint(1, 6) + random.randint(1, 6)
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

        # Universal Core Stratagems on a successful charge:
        # * Tank Shock (1 CP, attacker) — VEHICLE chargers deal D3 mortal
        #   wounds.
        # * Heroic Intervention (1 CP, defender) — friendly CHARACTER
        #   within 6" of the charge target moves 3" into engagement range
        #   with the charger. Fire AFTER Tank Shock so the character
        #   intervenes against whatever's still standing.
        self._try_tank_shock(attacker, target, attacker_army)
        if target.is_alive:
            self._try_heroic_intervention(attacker, target, defender_army)

    def _do_fight(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        """Resolve a melee strike if the attacker is in engagement range (1")."""
        if attacker.profile.melee_attacks <= 0:
            return
        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return
        # Find an enemy in engagement range
        nearest = min(
            alive_enemies,
            key=lambda e: _distance(attacker.position, e.position),
        )
        if _distance(attacker.position, nearest.position) > 1.5:
            return
        is_charging = attacker.uid in self._charging_this_round
        dmg = attacker.attack(
            nearest, distance=1.0, mode="melee", is_charging=is_charging,
        )
        alive_after = nearest.is_alive
        self._emit(UnitFought(
            attacker_uid=attacker.uid,
            target_uid=nearest.uid,
            damage=dmg,
            target_hp_after=nearest.current_health,
            target_alive_after=alive_after,
        ))
        if not alive_after:
            self._emit(UnitKilled(unit_uid=nearest.uid))
            self._maybe_award_judgement_token(
                killer=attacker, killer_army=attacker_army,
                victim=nearest, victim_army=defender_army,
            )

        # Universal Core Stratagem — Counter-Offensive (2 CP, defender):
        # an out-of-sequence fight for the side that just got hit. The
        # heuristic gates on (a) friendly unit in 1.5" of the attacker
        # AND (b) the attacker killed a model. The retaliator strikes
        # `attacker` immediately, before activation continues.
        if attacker.is_alive:
            self._try_counter_offensive(
                loser_army=defender_army, loser_unit=nearest,
                winner_army=attacker_army, winner_unit=attacker,
                target_killed=not alive_after,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, event) -> None:
        for s in self.subscribers:
            s.on_event(event)

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
        already.add(strat.name)
        self._stratagems_fired_this_battle[army.name] = already
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

    def _try_heroic_intervention(
        self, charger: "Unit", charge_target: "Unit",
        defender_army: Army,
    ) -> None:
        """When an enemy charges a unit, look for a friendly CHARACTER
        within 6" of the charge target — and if present, optionally spend
        1 CP to pull them into engagement range with the charger.

        Modelled as a free 3" move that places the CHARACTER 1" from the
        charger (inside engagement range), so the next fight sub-phase
        resolves their melee profile.
        """
        # Find the closest friendly CHARACTER to the charge target.
        best = None
        best_d = 999.0
        for u in defender_army.alive_units:
            if "CHARACTER" not in (u.profile.unit_keywords or ()):
                continue
            d = _distance(u.position, charge_target.position)
            if d < best_d:
                best_d = d
                best = u
        if best is None:
            return
        ctx = {
            "character": best,
            "charge_target": charge_target,
            "distance": best_d,
        }
        if not should_fire_stratagem(defender_army, HEROIC_INTERVENTION, ctx):
            return
        if not self._fire_stratagem(defender_army, HEROIC_INTERVENTION):
            return
        # Move the character toward the charger up to 3", landing inside
        # 1.0" engagement range if reachable.
        old_pos = best.position
        # Aim 1" short of the charger so we land in engagement, not on top.
        new_pos = _move_toward(old_pos, charger.position, 3.0, self.map)
        if new_pos != old_pos:
            best.position = new_pos
            self._emit(UnitMoved(
                unit_uid=best.uid, from_pos=old_pos, to_pos=new_pos,
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
