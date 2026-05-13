"""Random army generation within a points budget."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from .army import Army
from .units import UnitProfile, UNIT_CATALOG


def build_random_army(
    name: str,
    points_budget: float,
    unit_pool: Optional[Dict[str, UnitProfile]] = None,
    max_unit_fraction: float = 0.5,
    rng: Optional[random.Random] = None,
    in_cover: bool = False,
) -> Army:
    """
    Build an army by randomly selecting units from `unit_pool` until the
    points budget is exhausted.

    Args:
        name: Army display name.
        points_budget: Maximum total points.
        unit_pool: Profile catalogue to draw from. Defaults to UNIT_CATALOG.
        max_unit_fraction: A single unit type may not exceed this fraction of
            the total budget (prevents degenerate all-Carnifex armies).
        rng: Optional seeded Random instance for reproducibility.

    Returns:
        A populated Army instance.
    """
    if unit_pool is None:
        unit_pool = UNIT_CATALOG
    if rng is None:
        rng = random.Random()

    profiles: List[UnitProfile] = list(unit_pool.values())
    army = Army(name, in_cover=in_cover)
    remaining = points_budget
    unit_type_spend: Dict[str, float] = {p.name: 0.0 for p in profiles}

    while True:
        affordable = [
            p for p in profiles
            if p.points_cost <= remaining
            and unit_type_spend[p.name] + p.points_cost
               <= points_budget * max_unit_fraction
        ]
        if not affordable:
            break
        chosen = rng.choice(affordable)
        army.add_unit(chosen)
        remaining -= chosen.points_cost
        unit_type_spend[chosen.name] += chosen.points_cost

    return army


def build_homogeneous_army(
    name: str,
    profile: UnitProfile,
    points_budget: float,
    in_cover: bool = False,
) -> Army:
    """
    Fill an army with as many copies of a single unit type as the budget allows.
    Used for clean unit-vs-unit comparison.
    """
    army = Army(name, in_cover=in_cover)
    remaining = points_budget
    while remaining >= profile.points_cost:
        army.add_unit(profile)
        remaining -= profile.points_cost
    return army


def build_army_from_list(name: str, unit_keys: Sequence[str], in_cover: bool = False) -> Army:
    """
    Build an army from an explicit list of unit catalogue keys.
    Useful for testing specific compositions.
    """
    army = Army(name, in_cover=in_cover)
    for key in unit_keys:
        profile = UNIT_CATALOG[key]
        army.add_unit(profile)
    return army
