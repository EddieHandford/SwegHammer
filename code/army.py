"""Army — a collection of units with command point tracking."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

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

    # ------------------------------------------------------------------
    # Faction detection
    # ------------------------------------------------------------------

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

    def activation_queue(self, excluded_ids: set) -> List[Unit]:
        """Return alive units not yet activated, sorted by score descending."""
        available = [u for u in self.alive_units if id(u) not in excluded_ids]
        return sorted(available, key=lambda u: u.profile.score, reverse=True)

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
