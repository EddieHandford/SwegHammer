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


# ---------------------------------------------------------------------------
# Faction-scoped random army (calibration tool)
# ---------------------------------------------------------------------------

def _squad_size(profile: UnitProfile, policy: str, rng: random.Random) -> int:
    """
    Choose how many models to take of a given squad-type, respecting BSData
    min/max. Policy:

      "max"          -> always take the maximum-size squad
      "half_or_max"  -> 50/50 between half-rounded-up and max (matches Eddie's
                        observation that competitive lists tend to one extreme)
      "random"       -> uniform int in [min, max]
    """
    lo, hi = max(1, profile.min_models), max(1, profile.max_models)
    if hi < lo:
        hi = lo
    if policy == "max":
        return hi
    if policy == "half_or_max":
        half = (lo + hi + 1) // 2  # midpoint, rounded up
        return rng.choice((half, hi))
    return rng.randint(lo, hi)


def _squad_points(profile: UnitProfile, size: int) -> float:
    """
    SwegHammer points for a squad of `size` models — the formula in
    `units.py::points_for` is per-model, so squad cost is linear in size.
    Using SwegHammer pts (not BSData listed pts) means the UI's points slider
    and `army.total_points` agree.
    """
    return profile.points_cost * size


def build_faction_random_army(
    name: str,
    faction: str,
    points_budget: float,
    rng: Optional[random.Random] = None,
    in_cover: bool = False,
    size_policy: str = "max",
    max_unit_fraction: float = 0.5,
) -> Army:
    """
    Build a random army drawing only from a single faction's unit pool.

    Each pick rolls a squad size honouring BSData min/max, scales the cost
    linearly, and adds N copies of the UnitProfile to the army. Fills until
    no affordable picks remain. `max_unit_fraction` caps spend per unit type
    to avoid degenerate "20 Termagants and nothing else" outcomes.
    """
    if rng is None:
        rng = random.Random()

    pool = [UNIT_CATALOG[k] for k in UNIT_CATALOG if UNIT_CATALOG[k].faction == faction]
    if not pool:
        return Army(name, in_cover=in_cover)

    army = Army(name, in_cover=in_cover)
    remaining = float(points_budget)
    spent_by_name: Dict[str, float] = {p.name: 0.0 for p in pool}
    cap = points_budget * max_unit_fraction

    while True:
        affordable = []
        for p in pool:
            size = _squad_size(p, size_policy, rng)
            cost = _squad_points(p, size)
            if cost <= remaining and spent_by_name[p.name] + cost <= cap:
                affordable.append((p, size, cost))
        if not affordable:
            break
        chosen, size, cost = rng.choice(affordable)
        for _ in range(size):
            army.add_unit(chosen)
        spent_by_name[chosen.name] += cost
        remaining -= cost

    return army
