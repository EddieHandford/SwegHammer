"""Army — a collection of units with command point tracking."""

from __future__ import annotations

from typing import Dict, List, Optional

from .detachments import Detachment, default_detachment_for_faction
from .stratagems import STARTING_CP
from .units import Unit, UnitProfile


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
