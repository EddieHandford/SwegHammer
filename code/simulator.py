"""Battle simulator: unit-by-unit activation with movement and event emission."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .army import Army
from .events import (
    BattleEnded, BattleStarted, InitialUnit, RoundEnded, RoundStarted,
    Subscriber, UnitActivated, UnitKilled, UnitMoved, UnitShot,
)
from .map import Map, TerrainType
from .maps import DEFAULT_MAP


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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> BattleResult:
        self._assign_uids()
        self._deploy_armies()

        a_start = len(self.a.units)
        b_start = len(self.b.units)
        # VP tally accumulates across rounds
        self._a_vp = 0
        self._b_vp = 0

        self._emit(BattleStarted(
            army_a_name=self.a.name,
            army_b_name=self.b.name,
            map_name=self.map.name,
            units=tuple(
                InitialUnit(
                    uid=u.uid,
                    name=u.profile.name,
                    army=army.name,
                    position=u.position,
                    max_health=u.profile.health,
                )
                for army in (self.a, self.b)
                for u in army.units
            ),
        ))

        round_history = [(a_start, b_start)]
        rounds_played = 0
        for rnd in range(1, MAX_ROUNDS + 1):
            rounds_played = rnd
            self._emit(RoundStarted(round_num=rnd))
            self._run_round(rnd)
            self._score_objectives()
            self._emit(RoundEnded(round_num=rnd))
            round_history.append((self.a.unit_count, self.b.unit_count))
            if not self.a.alive_units or not self.b.alive_units:
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
        whichever side has more Objective Control within control_radius."""
        for obj in self.map.objectives:
            obj_pos = (obj.x, obj.y)
            r2 = obj.control_radius * obj.control_radius
            a_oc = 0
            b_oc = 0
            for u in self.a.alive_units:
                if u.uid in self._battleshocked_this_round:
                    continue   # Battleshocked = OC 0
                dx = u.position[0] - obj_pos[0]
                dy = u.position[1] - obj_pos[1]
                if dx * dx + dy * dy <= r2:
                    a_oc += getattr(u.profile, "oc", 1) or 1
            for u in self.b.alive_units:
                if u.uid in self._battleshocked_this_round:
                    continue
                dx = u.position[0] - obj_pos[0]
                dy = u.position[1] - obj_pos[1]
                if dx * dx + dy * dy <= r2:
                    b_oc += getattr(u.profile, "oc", 1) or 1
            if a_oc > b_oc:
                self._a_vp += obj.vp_per_round
            elif b_oc > a_oc:
                self._b_vp += obj.vp_per_round

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _assign_uids(self) -> None:
        for i, u in enumerate(self.a.units):
            u.uid = f"A{i}"
        for i, u in enumerate(self.b.units):
            u.uid = f"B{i}"

    def _deploy_armies(self) -> None:
        """Spread each army evenly along its deployment edge."""
        a_y = self.map.deployment_width / 2.0
        b_y = self.map.height - self.map.deployment_width / 2.0
        self._deploy_line(self.a.units, a_y)
        self._deploy_line(self.b.units, b_y)

    def _deploy_line(self, units, y: float) -> None:
        if not units:
            return
        usable = self.map.width - 4.0   # leave 2" margin each side
        spacing = usable / (len(units) + 1)
        for i, u in enumerate(units):
            x = 2.0 + spacing * (i + 1)
            u.position = (x, y)

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

        # Battleshock phase (after Round 1). 10e core rule: any unit Below
        # Half-Strength tests; pass on 2d6 >= Ld. We treat each Unit
        # instance as a stand-in for a single squad member; "below half
        # strength" maps to "current HP < starting HP / 2".
        if round_num > 1:
            for army, opponent in ((self.a, self.b), (self.b, self.a)):
                opponent_det = opponent.resolve_detachment()
                ld_penalty = opponent_det.enemy_ld_penalty if opponent_det else 0
                for u in army.alive_units:
                    if u.current_health < u.profile.health / 2.0:
                        roll = random.randint(1, 6) + random.randint(1, 6)
                        target = u.profile.leadership + ld_penalty
                        if roll < target:
                            self._battleshocked_this_round.add(u.uid)

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

        # Detachment passives: end-of-round reanimation/healing if any
        for army in (self.a, self.b):
            det = army.resolve_detachment()
            if det and det.reanimate_per_round > 0:
                for u in army.alive_units:
                    u.current_health = min(
                        u.profile.health,
                        u.current_health + det.reanimate_per_round,
                    )

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

        # Move toward the NEAREST enemy (not the global lowest-HP focus).
        # Lowest-HP focus would make every unit converge on one corner,
        # producing an unstable, map-asymmetric clumping pattern.
        alive_enemies = defender_army.alive_units
        if not alive_enemies:
            return
        move_target = min(
            alive_enemies,
            key=lambda u: _distance(attacker.position, u.position),
        )

        dist = _distance(attacker.position, move_target.position)
        if dist <= attacker.profile.range_inches:
            return  # already in range — hold position and shoot

        # 10e Advance: roll d6, move M+d6, but skip shoot/charge this turn.
        # We Advance only when a normal move would NOT bring us into shooting
        # range — the speed boost is wasted otherwise and the shoot foregone.
        # (Assault-weapon exception is deferred until the Assault keyword
        # is parsed by the mapper.)
        normal_move = attacker.profile.move
        needs_to_close = dist - attacker.profile.range_inches
        advance_d6 = random.randint(1, 6) if needs_to_close > normal_move else 0
        move_distance = normal_move + advance_d6
        did_advance = advance_d6 > 0

        old_pos = attacker.position
        new_pos = _move_toward(
            attacker.position, move_target.position,
            move_distance, self.map,
        )
        if new_pos != old_pos:
            attacker.position = new_pos
            self._emit(UnitMoved(
                unit_uid=attacker.uid,
                from_pos=old_pos,
                to_pos=new_pos,
            ))
        if did_advance:
            self._advanced_this_round.add(attacker.uid)

    def _do_shoot(self, attacker, attacker_army: Army, defender_army: Army) -> None:
        # 10e: a unit that Advanced this turn cannot shoot, unless its weapon is Assault.
        if attacker.uid in self._advanced_this_round and not attacker.profile.assault:
            return

        rng = attacker.profile.range_inches
        candidates = [
            u for u in defender_army.alive_units
            if _distance(attacker.position, u.position) <= rng
            and self.map.has_line_of_sight(attacker.position, u.position)
        ]
        if not candidates:
            return

        shoot_target = min(candidates, key=lambda u: u.current_health)

        # Terrain-aware cover: target counts as in cover if it stands inside
        # cover terrain, OR if the army-wide cover flag is set.
        saved_cover = shoot_target.in_cover
        cover_type = self.map.cover_at(shoot_target.position)
        if cover_type in (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER):
            shoot_target.in_cover = True

        distance = _distance(attacker.position, shoot_target.position)
        dmg = attacker.attack(shoot_target, distance=distance)
        shoot_target.in_cover = saved_cover

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
        if roll < dist:
            return   # charge failed

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
        attacker.attack(nearest, distance=1.0, mode="melee")

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
