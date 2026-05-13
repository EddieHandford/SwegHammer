"""Unit profiles and battle-instance unit class."""

from dataclasses import dataclass
from typing import Dict

# ---------------------------------------------------------------------------
# Baseline calibration constants
# ---------------------------------------------------------------------------

BASELINE_HEALTH: float = 1.0
BASELINE_DAMAGE: float = 1.0
BASELINE_HIT_PROB: float = 2.0 / 3.0
BASELINE_POINTS: float = 15.0

_BASELINE_EFFECTIVENESS: float = BASELINE_HEALTH * BASELINE_DAMAGE * BASELINE_HIT_PROB


def points_for(health: float, damage: float, hit_prob: float) -> float:
    """Return Phase-One cost: linear in raw effectiveness relative to baseline Marine."""
    effectiveness = health * damage * hit_prob
    return round(BASELINE_POINTS * effectiveness / _BASELINE_EFFECTIVENESS, 1)


def lanchester_score(health: float, damage: float, hit_prob: float) -> float:
    """Return the unit's Lanchester effectiveness score: (H × D × P)²."""
    return (health * damage * hit_prob) ** 2


# ---------------------------------------------------------------------------
# UnitProfile — immutable stat block
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnitProfile:
    """Immutable stat block for a unit type."""

    name: str
    health: float
    damage: float       # damage per attack action (before hit roll)
    hit_probability: float

    @property
    def effectiveness(self) -> float:
        return self.health * self.damage * self.hit_probability

    @property
    def score(self) -> float:
        return lanchester_score(self.health, self.damage, self.hit_probability)

    @property
    def points_cost(self) -> float:
        return points_for(self.health, self.damage, self.hit_probability)

    @property
    def avg_damage_per_action(self) -> float:
        """Deterministic (average-case) damage dealt per activation."""
        return self.damage * self.hit_probability

    def __str__(self) -> str:
        return (
            f"{self.name} "
            f"[H:{self.health} D:{self.damage} P:{self.hit_probability:.2f} "
            f"Score:{self.score:.2f} Pts:{self.points_cost}]"
        )


# ---------------------------------------------------------------------------
# Unit — mutable battle instance
# ---------------------------------------------------------------------------

class Unit:
    """A live unit on the battlefield, tracking current health."""

    __slots__ = ("profile", "current_health")

    def __init__(self, profile: UnitProfile) -> None:
        self.profile = profile
        self.current_health: float = profile.health

    @property
    def is_alive(self) -> bool:
        return self.current_health > 1e-9

    def receive_damage(self, amount: float) -> None:
        self.current_health = max(0.0, self.current_health - amount)

    def attack(self, target: "Unit") -> float:
        """Deal deterministic average damage to target. Returns damage dealt."""
        dmg = self.profile.avg_damage_per_action
        target.receive_damage(dmg)
        return dmg

    def __repr__(self) -> str:
        return f"{self.profile.name}({self.current_health:.2f}/{self.profile.health}hp)"


# ---------------------------------------------------------------------------
# Unit catalogue
# ---------------------------------------------------------------------------

UNIT_CATALOG: Dict[str, UnitProfile] = {
    # --- Space Marines ---
    "scout_marine": UnitProfile(
        name="Scout Marine", health=1, damage=1, hit_probability=0.500
    ),
    "space_marine": UnitProfile(
        name="Space Marine", health=1, damage=1, hit_probability=2 / 3
    ),
    "veteran_marine": UnitProfile(
        name="Veteran Marine", health=2, damage=1, hit_probability=2 / 3
    ),
    "terminator": UnitProfile(
        name="Terminator", health=3, damage=2, hit_probability=2 / 3
    ),
    "dreadnought": UnitProfile(
        name="Dreadnought", health=8, damage=3, hit_probability=2 / 3
    ),
    "predator_tank": UnitProfile(
        name="Predator Tank", health=11, damage=4, hit_probability=2 / 3
    ),
    # --- Chaos ---
    "cultist": UnitProfile(
        name="Cultist", health=1, damage=1, hit_probability=0.500
    ),
    "chaos_space_marine": UnitProfile(
        name="Chaos Space Marine", health=2, damage=1, hit_probability=2 / 3
    ),
    "chaos_terminator": UnitProfile(
        name="Chaos Terminator", health=3, damage=2, hit_probability=2 / 3
    ),
    "chaos_dreadnought": UnitProfile(
        name="Chaos Dreadnought", health=8, damage=3, hit_probability=2 / 3
    ),
    # --- Orks ---
    "gretchin": UnitProfile(
        name="Gretchin", health=1, damage=1, hit_probability=1 / 3
    ),
    "ork_boy": UnitProfile(
        name="Ork Boy", health=2, damage=1, hit_probability=0.500
    ),
    "ork_nob": UnitProfile(
        name="Ork Nob", health=3, damage=2, hit_probability=0.500
    ),
    "mek_gun": UnitProfile(
        name="Mek Gun", health=5, damage=3, hit_probability=0.500
    ),
    # --- Tyranids ---
    "termagant": UnitProfile(
        name="Termagant", health=1, damage=1, hit_probability=0.500
    ),
    "hormagaunt": UnitProfile(
        name="Hormagaunt", health=1, damage=2, hit_probability=0.500
    ),
    "warrior": UnitProfile(
        name="Warrior", health=3, damage=2, hit_probability=2 / 3
    ),
    "carnifex": UnitProfile(
        name="Carnifex", health=10, damage=4, hit_probability=2 / 3
    ),
}
