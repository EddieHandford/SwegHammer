"""Battle simulator: unit-by-unit activation with deterministic damage."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .army import Army


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
# Battle engine
# ---------------------------------------------------------------------------

MAX_ROUNDS = 30
CP_BONUS_DIVISOR = 2    # opponent must have this many more units per 1 CP awarded
CP_BONUS_CAP = 2        # max CP awarded per round


class Battle:
    """
    Runs a single engagement between two armies under Swaghammer rules:
      - Unit-by-unit alternating activations each round.
      - First player randomised per round.
      - CP bonus awarded to the smaller army after Round 1.
      - Deterministic (average-case) damage — no dice rolls.
    """

    def __init__(
        self,
        army_a: Army,
        army_b: Army,
        verbose: bool = False,
    ) -> None:
        self.a = army_a
        self.b = army_b
        self.verbose = verbose

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> BattleResult:
        a_start = len(self.a.units)
        b_start = len(self.b.units)

        round_history = [(a_start, b_start)]
        rounds_played = 0
        for rnd in range(1, MAX_ROUNDS + 1):
            rounds_played = rnd
            self._run_round(rnd)
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

        # Alternate activations until both queues are exhausted
        while True:
            first_q = first.activation_queue(first_activated)
            second_q = second.activation_queue(second_activated)

            if not first_q and not second_q:
                break

            if first_q:
                self._activate(first, second, first_activated)

            if second_q:
                self._activate(second, first, second_activated)

        # CP economy (skip Round 1 to discourage list-building exploits)
        if round_num > 1:
            self._award_cp(self.a, self.b)
            self._award_cp(self.b, self.a)

    def _activate(self, attacker_army: Army, defender_army: Army, activated: set) -> None:
        queue = attacker_army.activation_queue(activated)
        if not queue:
            return
        attacker = queue[0]
        activated.add(id(attacker))

        if not attacker.is_alive:
            return

        target = attacker_army.pick_target(defender_army)
        if target is None:
            return

        dmg = attacker.attack(target)

        if self.verbose:
            alive_str = "killed" if not target.is_alive else f"{target.current_health:.2f}hp left"
            print(
                f"  {attacker_army.name}: {attacker.profile.name}"
                f" → {target.profile.name} ({dmg:.2f} dmg, {alive_str})"
            )

    @staticmethod
    def _award_cp(army: Army, opponent: Army) -> None:
        diff = opponent.unit_count - army.unit_count
        bonus = min(CP_BONUS_CAP, max(0, diff // CP_BONUS_DIVISOR))
        army.command_points += bonus
