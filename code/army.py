"""Army — a collection of units with command point tracking."""

from __future__ import annotations

from typing import List, Optional

from .detachments import Detachment, default_detachment_for_faction
from .units import Unit, UnitProfile


class Army:
    """A named collection of unit instances participating in a battle."""

    def __init__(
        self, name: str, in_cover: bool = False,
        detachment: Optional[Detachment] = None,
    ) -> None:
        self.name = name
        self.units: List[Unit] = []
        self.command_points: int = 3
        self.in_cover: bool = in_cover
        # Army-wide passive rules. Auto-resolves from the army's primary
        # faction (first unit's faction tag) when not explicitly set.
        self.detachment: Optional[Detachment] = detachment

    # ------------------------------------------------------------------
    # Army construction
    # ------------------------------------------------------------------

    def add_unit(self, profile: UnitProfile) -> None:
        self.units.append(Unit(profile, in_cover=self.in_cover))

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
