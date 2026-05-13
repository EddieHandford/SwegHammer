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

MAX_ROUNDS = 30
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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> BattleResult:
        self._assign_uids()
        self._deploy_armies()

        a_start = len(self.a.units)
        b_start = len(self.b.units)

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
            self._emit(RoundEnded(round_num=rnd))
            round_history.append((self.a.unit_count, self.b.unit_count))
            if not self.a.alive_units or not self.b.alive_units:
                break

        a_surv = self.a.unit_count
        b_surv = self.b.unit_count

        if a_surv > b_surv:
            winner = self.a.name
        elif b_surv > a_surv:
            winner = self.b.name
        else:
            winner = None  # mutual destruction or round-limit tie

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
            round_history=round_history,
        )

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
        if dist > attacker.profile.range_inches:
            old_pos = attacker.position
            new_pos = _move_toward(
                attacker.position, move_target.position,
                attacker.profile.move, self.map,
            )
            if new_pos != old_pos:
                attacker.position = new_pos
                self._emit(UnitMoved(
                    unit_uid=attacker.uid,
                    from_pos=old_pos,
                    to_pos=new_pos,
                ))

    def _do_shoot(self, attacker, attacker_army: Army, defender_army: Army) -> None:
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

        dmg = attacker.attack(shoot_target)
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
