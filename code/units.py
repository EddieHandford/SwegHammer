"""Unit profiles and battle-instance unit class."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict

# ---------------------------------------------------------------------------
# Baseline calibration constants — Space Marine is the reference unit
# ---------------------------------------------------------------------------

BASELINE_HEALTH: float = 1.0
BASELINE_DAMAGE: float = 1.0
BASELINE_HIT_PROB: float = 2 / 3       # 3+ to hit on a d6
BASELINE_AP: int = 0
BASELINE_SAVE: int = 3                  # 3+ armour save
BASELINE_STRENGTH: int = 4              # bolter S4
BASELINE_TOUGHNESS: int = 4             # Marine T4
BASELINE_POINTS: float = 15.0


def wound_probability(strength: int, toughness: int) -> float:
    """
    Standard 40K wound table:

      S >= 2T : wound on 2+ (5/6)
      S > T   : wound on 3+ (4/6)
      S == T  : wound on 4+ (3/6)
      S < T   : wound on 5+ (2/6)
      2S <= T : wound on 6+ (1/6)
    """
    if strength >= 2 * toughness:
        return 5 / 6
    if 2 * strength <= toughness:
        return 1 / 6
    if strength > toughness:
        return 4 / 6
    if strength == toughness:
        return 3 / 6
    return 2 / 6   # strength < toughness but not 2S <= T


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
    strength: int = BASELINE_STRENGTH,
    toughness: int = BASELINE_TOUGHNESS,
) -> float:
    """
    Points cost relative to the baseline Space Marine.

    Offensive ratio: expected unsaved damage this unit does to a baseline Marine
    (hit × wound vs T4 × unsaved vs 3+) divided by what a Marine does.

    Defensive ratio: expected hits-to-kill this unit by a baseline Marine, vs
    the baseline against itself.

    The two ratios are averaged (not multiplied) to prevent runaway costs for
    units that are dominant on both axes.
    """
    attacker_wound = wound_probability(strength, BASELINE_TOUGHNESS)
    offensive = damage * hit_prob * attacker_wound * (1.0 - save_probability(BASELINE_SAVE, ap))

    baseline_wound = wound_probability(BASELINE_STRENGTH, BASELINE_TOUGHNESS)
    baseline_offensive = BASELINE_DAMAGE * BASELINE_HIT_PROB * baseline_wound * _baseline_survival()
    off_ratio = offensive / baseline_offensive

    incoming_wound = wound_probability(BASELINE_STRENGTH, toughness)
    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    if incoming_wound <= 0:
        incoming_wound = 1e-6
    durability = health / (incoming_wound * survive_chance)

    baseline_incoming_wound = wound_probability(BASELINE_STRENGTH, BASELINE_TOUGHNESS)
    baseline_survive = 1.0 - save_probability(BASELINE_SAVE)
    baseline_durability = BASELINE_HEALTH / (baseline_incoming_wound * baseline_survive)
    dur_ratio = durability / baseline_durability

    effectiveness = (off_ratio + dur_ratio) / 2.0
    return round(BASELINE_POINTS * effectiveness, 1)


def lanchester_score(
    health: float,
    damage: float,
    hit_prob: float,
    ap: int = 0,
    save: int = 7,
    strength: int = BASELINE_STRENGTH,
    toughness: int = BASELINE_TOUGHNESS,
) -> float:
    """Lanchester priority score: dps × durability (used for activation order)."""
    attacker_wound = wound_probability(strength, BASELINE_TOUGHNESS)
    dps = damage * hit_prob * attacker_wound * (1.0 - save_probability(BASELINE_SAVE, ap))

    incoming_wound = wound_probability(BASELINE_STRENGTH, toughness)
    survive_chance = 1.0 - save_probability(save)
    if survive_chance <= 0:
        survive_chance = 1e-6
    if incoming_wound <= 0:
        incoming_wound = 1e-6
    durability = health / (incoming_wound * survive_chance)
    return dps * durability


# ---------------------------------------------------------------------------
# UnitProfile — immutable stat block
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnitProfile:
    """Immutable stat block for a unit type."""

    name: str
    health: float
    damage: float                              # damage per unsaved hit
    hit_probability: float                     # probability of landing a hit (e.g. 2/3 for 3+)
    ap: int = 0                                # armour penetration modifier (0, -1, -2, -3 …)
    save: int = 7                              # armour save characteristic (7 = no save)
    strength: int = BASELINE_STRENGTH          # weapon strength used in the wound roll
    toughness: int = BASELINE_TOUGHNESS        # unit toughness defended in the wound roll

    @property
    def avg_damage_per_action(self) -> float:
        """Expected damage dealt per activation against a baseline Marine."""
        wound_p = wound_probability(self.strength, BASELINE_TOUGHNESS)
        unsaved = 1.0 - save_probability(BASELINE_SAVE, self.ap)
        return self.damage * self.hit_probability * wound_p * unsaved

    @property
    def points_cost(self) -> float:
        return points_for(
            self.health, self.damage, self.hit_probability,
            self.ap, self.save, self.strength, self.toughness,
        )

    @property
    def score(self) -> float:
        return lanchester_score(
            self.health, self.damage, self.hit_probability,
            self.ap, self.save, self.strength, self.toughness,
        )

    def __str__(self) -> str:
        save_str = f"{self.save}+" if self.save <= 6 else "none"
        ap_str = str(self.ap) if self.ap != 0 else "0"
        return (
            f"{self.name} "
            f"[H:{self.health} D:{self.damage} Hit:{self.hit_probability:.0%} "
            f"S:{self.strength} T:{self.toughness} AP:{ap_str} Sv:{save_str} "
            f"Pts:{self.points_cost}]"
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
        Full stochastic attack sequence:
          1. Roll to hit (hit_probability).
          2. Roll to wound (S vs T table).
          3. Target rolls armour save (modified by attacker AP and cover).
          4. Apply damage on failed save.

        Returns total damage dealt (0 on miss / no-wound / saved).
        """
        if random.random() >= self.profile.hit_probability:
            return 0.0  # missed

        wound_p = wound_probability(self.profile.strength, target.profile.toughness)
        if random.random() >= wound_p:
            return 0.0  # failed to wound

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
#   ap:    0 = no AP,  -1 = AP1,  -2 = AP2,  -3 = AP3
#   save:  3 = 3+, 4 = 4+, 5 = 5+, 6 = 6+, 7 = no save
#   S / T: roughly aligned with 10th-edition datasheets, rounded for sanity
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
