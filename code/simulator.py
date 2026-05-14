"""Battle simulator: unit-by-unit activation with movement and event emission."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .army import Army
from .events import (
    BattleEnded, BattleStarted, BattleshockFailed, InitialUnit, ObjectiveScored,
    RoundEnded, RoundStarted, Subscriber, UnitActivated, UnitAdvanced,
    UnitCharged, UnitDeepStrike, UnitFought, UnitInfiltrated, UnitKilled,
    UnitMoved, UnitReanimated, UnitScouted, UnitShot,
)
from .map import Map, TerrainType
from .maps import DEFAULT_MAP
from .strategy import pick_move_intent


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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> BattleResult:
        self._assign_uids()
        self._deploy_armies()
        # Phase I — pre-game Scouts move happens AFTER deployment and BEFORE
        # Round 1 begins. Deep Strike arrivals start at Round 2.
        self._run_scout_phase()

        # Include reserves so the "starting unit count" reflects the full
        # army roster, not just what was on the board at deployment.
        a_start = len(self.a.units) + len(self._reserves.get(self.a.name, []))
        b_start = len(self.b.units) + len(self._reserves.get(self.b.name, []))
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
                # Median D3 roll = 2. Cap by however many are actually dead.
                to_revive = min(destroyed, 2)
                dead_pool = dead_by_profile.get(profile_name, [])
                # Anchor position: nearest alive friendly of the same profile,
                # or the army's deployment edge midpoint if the squad is wiped.
                alive_peers = alive_by_profile.get(profile_name, [])
                anchor_pos: Tuple[float, float]
                if alive_peers:
                    # Place at the first alive peer (caller-stable choice).
                    anchor_pos = alive_peers[0].position
                else:
                    anchor_pos = (edge_x, edge_y)
                # Make sure the anchor isn't on impassable terrain; nudge
                # off to the deployment edge if it is.
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
                    pos = self._pick_arrival_point(opponent)
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

    def _pick_arrival_point(self, opponent: Army) -> Optional[Tuple[float, float]]:
        """Find a point > 9" from every alive enemy and not in impassable
        terrain. Tries the centre first, then the four corners of the
        > 9" exclusion zone, then a coarse 4" grid sweep.
        """
        enemies = opponent.alive_units
        min_gap = 9.0
        cx, cy = self.map.width / 2.0, self.map.height / 2.0

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

        candidates = [
            (cx, cy),                                       # centre
            (3.0, 3.0),                                     # SW corner
            (self.map.width - 3.0, 3.0),                    # SE corner
            (3.0, self.map.height - 3.0),                   # NW corner
            (self.map.width - 3.0, self.map.height - 3.0),  # NE corner
        ]
        for p in candidates:
            if _valid(p):
                return p

        # Coarse 4" grid sweep across the board as a last resort.
        x = 4.0
        while x < self.map.width - 1.0:
            y = 4.0
            while y < self.map.height - 1.0:
                if _valid((x, y)):
                    return (x, y)
                y += 4.0
            x += 4.0
        return None

    # ------------------------------------------------------------------
    # Round logic
    # ------------------------------------------------------------------

    def _run_round(self, round_num: int) -> None:
        if self.verbose:
            print(f"\n--- Round {round_num} ---")

        # New round = no unit has Advanced yet, no battleshock yet, no charges.
        self._advanced_this_round = set()
        self._battleshocked_this_round = set()
        self._charging_this_round = set()
        # Reset movement tracking: nothing has moved yet this round.
        self._did_move_this_round = set()
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

        # Battleshock phase (after Round 1). 10e core rule: any unit Below
        # Half-Strength tests; pass on 2d6 >= Ld. We treat each Unit
        # instance as a stand-in for a single squad member; "below half
        # strength" maps to "current HP < starting HP / 2".
        # Detachment modifiers compose: own ld_bonus LOWERS our test target
        # (easier pass); opponent's enemy_ld_penalty RAISES it (harder pass).
        if round_num > 1:
            for army, opponent in ((self.a, self.b), (self.b, self.a)):
                opponent_det = opponent.resolve_detachment()
                own_det = army.resolve_detachment()
                ld_penalty = opponent_det.enemy_ld_penalty if opponent_det else 0
                ld_bonus = own_det.ld_bonus if own_det else 0
                for u in army.alive_units:
                    if u.current_health < u.profile.health / 2.0:
                        roll = random.randint(1, 6) + random.randint(1, 6)
                        target = u.profile.leadership + ld_penalty - ld_bonus
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

        # Leader auras: end-of-round heal_per_round from Apothecaries etc.
        from .leaders import apply_round_end_healing
        apply_round_end_healing(self.a)
        apply_round_end_healing(self.b)

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
        # 10e: a unit that Advanced this turn cannot shoot, unless its weapon is Assault.
        if attacker.uid in self._advanced_this_round and not attacker.profile.assault:
            return
        # One Shot: weapon may only fire once per battle. If we've already
        # fired it, skip the activation outright.
        if attacker.profile.one_shot and attacker.uid in self._one_shot_fired:
            return

        # Pistol gate: a unit within 1.5" of an enemy is in engagement range
        # and may ONLY shoot if its weapon has the Pistol keyword.
        in_engagement = any(
            _distance(attacker.position, e.position) < 1.5
            for e in defender_army.alive_units
        )
        if in_engagement and not attacker.profile.pistol:
            return

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
        """2D6 charge vs nearest enemy ≤12". On success, move into engagement (1")."""
        if not self._wants_to_charge(attacker):
            return
        if attacker.uid in self._advanced_this_round:
            return   # advanced units cannot charge

        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return
        # Pick nearest enemy within charge range
        candidates = [
            (e, _distance(attacker.position, e.position))
            for e in alive_enemies
        ]
        candidates = [(e, d) for e, d in candidates if d <= 12.0 and d > 1.0]
        if not candidates:
            return
        candidates.sort(key=lambda kv: kv[1])
        target, dist = candidates[0]

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, event) -> None:
        for s in self.subscribers:
            s.on_event(event)

    @staticmethod
    def _award_cp(army: Army, opponent: Army) -> None:
        diff = opponent.unit_count - army.unit_count
        bonus = min(CP_BONUS_CAP, max(0, diff // CP_BONUS_DIVISOR))
        army.command_points += bonus
