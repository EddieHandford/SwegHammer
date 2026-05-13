"""Unit profiles and battle-instance unit class."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict

# ---------------------------------------------------------------------------
# Baseline calibration constants — Space Marine is the reference unit
# ---------------------------------------------------------------------------

BASELINE_HEALTH: float = 1.0
BASELINE_DAMAGE: float = 1.0
BASELINE_HIT_PROB: float = 2 / 3       # 3+ to hit on a d6
BASELINE_AP: int = 0
BASELINE_SAVE: int = 3                  # 3+ armour save
BASELINE_POINTS: float = 15.0


def save_probability(save: int, ap: int = 0, in_cover: bool = False) -> float:
    """
    Probability of passing an armour save roll on a d6.

    save:      the unit's base save characteristic (e.g. 3 means 3+)
    ap:        weapon AP modifier (negative integer, e.g. -1 degrades save by 1)
    in_cover:  cover improves save by 1 pip (e.g. 4+ → 3+), capped at 2+
    """
    effective = save - ap                       # AP-1 on a 3+ → 4+
    if in_cover:
        effective = max(2, effective - 1)       # cover: improve by 1, cap at 2+
    if effective > 6:
        return 0.0                              # save negated entirely
    return max(0.0, (7 - effective) / 6)


def _baseline_survival() -> float:
    """Fraction of hits that get through against a baseline Marine (no AP, no cover)."""
    return 1.0 - save_probability(BASELINE_SAVE, BASELINE_AP)


def points_for(
    health: float,
    damage: float,
    hit_prob: float,
    ap: int = 0,
    save: int = 7,
) -> float:
    """
    Points cost relative to the baseline Space Marine.

    Offensive ratio: how much damage this unit pumps through a baseline Marine's
    armour vs how much a Marine does.

    Defensive ratio: expected hits to kill this unit vs a baseline Marine.

    We use the average (additive) of the two ratios rather than multiplying them,
    which prevents runaway costs for units that are dominant on both axes.
    """
    offensive = damage * hit_prob * (1.0 - save_probability(BASELINE_SAVE, ap))
    baseline_offensive = BASELINE_DAMAGE * BASELINE_HIT_PROB * _baseline_survival()
    off_ratio = offensive / baseline_offensive

    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    durability = health / survive_chance

    baseline_survive = 1.0 - save_probability(BASELINE_SAVE)
    baseline_durability = BASELINE_HEALTH / baseline_survive
    dur_ratio = durability / baseline_durability

    effectiveness = (off_ratio + dur_ratio) / 2.0
    return round(BASELINE_POINTS * effectiveness, 1)


def lanchester_score(
    health: float,
    damage: float,
    hit_prob: float,
    ap: int = 0,
    save: int = 7,
) -> float:
    """Lanchester priority score: dps × durability (used for activation order only)."""
    dps = damage * hit_prob * (1.0 - save_probability(BASELINE_SAVE, ap))
    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    durability = health / survive_chance
    return dps * durability


# ---------------------------------------------------------------------------
# UnitProfile — immutable stat block
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnitProfile:
    """Immutable stat block for a unit type."""

    name: str
    health: float
    damage: float           # damage per unsaved hit
    hit_probability: float  # probability of landing a hit (e.g. 2/3 for 3+)
    ap: int = 0             # armour penetration modifier (0, -1, -2, -3 …)
    save: int = 7           # armour save characteristic (7 = no save)

    @property
    def avg_damage_per_action(self) -> float:
        """Expected damage dealt per activation assuming no target save."""
        return self.damage * self.hit_probability

    @property
    def points_cost(self) -> float:
        return points_for(self.health, self.damage, self.hit_probability, self.ap, self.save)

    @property
    def score(self) -> float:
        return lanchester_score(self.health, self.damage, self.hit_probability, self.ap, self.save)

    def __str__(self) -> str:
        save_str = f"{self.save}+" if self.save <= 6 else "none"
        ap_str = str(self.ap) if self.ap != 0 else "0"
        return (
            f"{self.name} "
            f"[H:{self.health} D:{self.damage} Hit:{self.hit_probability:.0%} "
            f"AP:{ap_str} Sv:{save_str} Pts:{self.points_cost}]"
        )


# ---------------------------------------------------------------------------
# Unit — mutable battle instance
# ---------------------------------------------------------------------------

class Unit:
    """A live unit on the battlefield, tracking current health."""

    __slots__ = ("profile", "current_health", "in_cover")

    def __init__(self, profile: UnitProfile, in_cover: bool = False) -> None:
        self.profile = profile
        self.current_health: float = profile.health
        self.in_cover: bool = in_cover

    @property
    def is_alive(self) -> bool:
        return self.current_health > 1e-9

    def receive_damage(self, amount: float) -> None:
        self.current_health = max(0.0, self.current_health - amount)

    def attack(self, target: "Unit") -> float:
        """
        Stochastic attack sequence:
          1. Roll to hit (hit_probability)
          2. Roll armour save for target (target save modified by attacker AP and cover)
          3. Apply damage on failed save.

        Returns total damage dealt.
        """
        if random.random() >= self.profile.hit_probability:
            return 0.0  # missed

        sv_prob = save_probability(target.profile.save, self.profile.ap, target.in_cover)
        if random.random() < sv_prob:
            return 0.0  # saved

        target.receive_damage(self.profile.damage)
        return self.profile.damage

    def __repr__(self) -> str:
        return f"{self.profile.name}({self.current_health:.1f}/{self.profile.health}hp)"


# ---------------------------------------------------------------------------
# Unit catalogue
# ---------------------------------------------------------------------------
#
# Stats follow the SwegHammer abstraction (not 1:1 with any edition):
#   hit_probability: 1/2 = 4+, 2/3 = 3+, 5/6 = 2+ (on a d6)
#   ap:  0 = no AP,  -1 = AP1,  -2 = AP2,  -3 = AP3
#   save: 3 = 3+, 4 = 4+, 5 = 5+, 6 = 6+, 7 = no save
#
# UNIT_CATALOG is built at import time by merging:
#   data/bsdata/parsed.json — base stats derived from BSData WH40k 2nd Edition
#   data/overrides.json     — per-unit hand tuning, plus legacy hand-rolled units
#
# To refresh the BSData base, run:
#     python -m code.bsdata.fetch --tag <release>
#     python -m code.bsdata.mapper
#
def _build_catalog() -> Dict[str, UnitProfile]:
    from .bsdata.loader import load_catalog

    catalog: Dict[str, UnitProfile] = {}
    for key, entry in load_catalog().items():
        catalog[key] = UnitProfile(
            name=entry.name,
            health=entry.health,
            damage=entry.damage,
            hit_probability=entry.hit_probability,
            ap=entry.ap,
            save=entry.save,
        )
    return catalog


UNIT_CATALOG: Dict[str, UnitProfile] = _build_catalog()
