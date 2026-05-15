"""Random army generation within a points budget."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from .army import Army
from .detachments import default_detachment_for_faction, pick_detachment_for_army
from .enhancements import Enhancement, pick_enhancement
from .units import UnitProfile, UNIT_CATALOG


def _assign_enhancement_to_warlord(army: Army, rng: random.Random) -> None:
    """Pick a single Enhancement from the army's Detachment list (if any)
    and attach it to one alive CHARACTER. No-op if:
      * the army has no detachment resolved yet,
      * the detachment has no wired enhancements,
      * the army has no CHARACTER units.

    Cost handling: the caller is responsible for honouring `points_cost`
    before this is called (the build loops below deduct upfront in the
    `points_budget` accounting). This function only mutates the unit.

    The picked CHARACTER is deterministic given a seeded RNG — we choose
    the highest-points CHARACTER first (the Warlord proxy), with the RNG
    only firing if multiple CHARACTERS tie. 10e: only one Enhancement per
    army, so we stop after assigning to a single bearer.
    """
    det = army.resolve_detachment()
    if det is None or not getattr(det, "enhancements", ()):
        return
    candidates = [
        u for u in army.units
        if "CHARACTER" in (u.profile.unit_keywords or ())
    ]
    if not candidates:
        return
    candidates.sort(key=lambda u: u.profile.points_cost, reverse=True)
    # Filter to the top points bracket so ties get RNG-broken.
    top_pts = candidates[0].profile.points_cost
    top_tier = [u for u in candidates if u.profile.points_cost == top_pts]
    warlord = rng.choice(top_tier)
    enh = pick_enhancement(_detachment_key_for(det), rng=rng)
    if enh is None:
        return
    warlord.enhancement = enh


def _detachment_key_for(det) -> str:
    """Inverse of `DETACHMENTS[key] == det`. Returns the registry key for
    the supplied Detachment instance, or empty string if not registered."""
    from .detachments import DETACHMENTS
    for key, val in DETACHMENTS.items():
        if val is det:
            return key
    # Fallback: match by name (covers replace()'d instances that don't
    # alias the original).
    for key, val in DETACHMENTS.items():
        if val.name == det.name:
            return key
    return ""


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

    # Detachment + Enhancement: assign once units are picked so we can
    # see which CHARACTERS the army actually contains. Detachment derives
    # from the first unit's faction (no composition picker for the generic
    # `build_random_army` path — used mostly by toy tests).
    if army.units and not army.detachment:
        first_faction = army.units[0].profile.faction
        if first_faction:
            army.detachment = default_detachment_for_faction(first_faction)
    _assign_enhancement_to_warlord(army, rng)

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

    Detachment: if `profile.faction` is non-empty, the army's detachment is
    set to that faction's canonical default via `default_detachment_for_faction`.
    This ensures calibration battles exercise army-wide passives (Awakened
    Dynasty's bonus-to-hit-when-led, Gladius's wound-1 reroll, etc.) and
    stratagems / CP economy on a representative footing rather than the
    no-detachment baseline that earlier versions accidentally compared.
    """
    army = Army(name, in_cover=in_cover)
    remaining = points_budget
    while remaining >= profile.points_cost:
        army.add_unit(profile)
        remaining -= profile.points_cost
    if profile.faction:
        army.detachment = default_detachment_for_faction(profile.faction)
    return army


def build_attached_army(
    name: str,
    host_profile: UnitProfile,
    leader_profile: UnitProfile,
    points_budget: float,
    in_cover: bool = False,
) -> Army:
    """
    Build an army of (host, leader) pairs, interleaved so the deployment line
    places leaders adjacent to their host within aura range.

    Used by the leader-attached calibration mode to measure the leader's
    actual battlefield value (aura uplift on a bodyguard squad) rather than
    fighting in isolation. Remaining budget after the last pair is spent on
    extra hosts.
    """
    army = Army(name, in_cover=in_cover)
    remaining = points_budget
    pair_cost = host_profile.points_cost + leader_profile.points_cost
    while remaining >= pair_cost:
        army.add_unit(host_profile)
        army.add_unit(leader_profile)
        remaining -= pair_cost
    while remaining >= host_profile.points_cost:
        army.add_unit(host_profile)
        remaining -= host_profile.points_cost
    # Detachment derives from the HOST's faction, not the leader's. A leader
    # may be conceptually allied (Inquisitor attached to a Marine squad);
    # the bodyguard squad's faction is what determines the army's detachment
    # rule. Falls through silently when host_profile.faction is empty.
    if host_profile.faction:
        army.detachment = default_detachment_for_faction(host_profile.faction)
    # Enhancement: assign once the army has a detachment. The leader (the
    # attached CHARACTER) is the natural bearer; the helper picks the
    # highest-points CHARACTER which is the leader profile here.
    _assign_enhancement_to_warlord(army, random.Random())
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
    use_archetype: bool = False,
) -> Army:
    """
    Build a random army drawing only from a single faction's unit pool.

    Each pick rolls a squad size honouring BSData min/max, scales the cost
    linearly, and adds N copies of the UnitProfile to the army. Fills until
    no affordable picks remain. `max_unit_fraction` caps spend per unit type
    to avoid degenerate "20 Termagants and nothing else" outcomes.

    If `use_archetype=True` and a curated tournament archetype exists for
    the faction in `code.archetypes`, the army is built from that template
    instead. Default is `False` — the curated archetypes regressed eval-vs-
    meta MAE in the May 2026 calibration (4.14 -> 16+), because the
    random-pool's accidental cost balance is more representative of real
    win-rates than the MSU-tournament templates allow given the catalogue's
    lopsided per-unit SwegHammer pricing. Archetypes remain available for
    opt-in experimentation and for callers who want flavoured lists.
    """
    # Curated-archetype shortcut (opt-in only). Local import to avoid
    # circular import (archetypes -> army -> nothing, but staying defensive).
    if use_archetype:
        from .archetypes import build_archetype_army, has_archetype
        if has_archetype(faction):
            return build_archetype_army(
                name, faction, points_budget,
                rng=rng, in_cover=in_cover,
            )

    if rng is None:
        rng = random.Random()

    pool = [UNIT_CATALOG[k] for k in UNIT_CATALOG if UNIT_CATALOG[k].faction == faction]
    if not pool:
        return Army(name, in_cover=in_cover)

    army = Army(name, in_cover=in_cover)
    remaining = float(points_budget)
    spent_by_name: Dict[str, float] = {p.name: 0.0 for p in pool}
    cap = points_budget * max_unit_fraction

    # CHARACTER-tagged profiles are eligible to be drafted as attached leaders.
    # 10e: a leader sits inside an infantry / battleline unit and grants auras.
    character_pool = [
        p for p in pool
        if "CHARACTER" in (p.unit_keywords or ())
    ]

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

        # 50% preference: when we just added a non-character squad, try to
        # attach a same-faction character leader. Skip if the chosen profile
        # was itself a character, or if no characters fit the remaining budget.
        is_character = "CHARACTER" in (chosen.unit_keywords or ())
        if not is_character and character_pool and rng.random() < 0.5:
            leaders_affordable = [
                c for c in character_pool
                if c.points_cost <= remaining
                and spent_by_name[c.name] + c.points_cost <= cap
            ]
            if leaders_affordable:
                leader = rng.choice(leaders_affordable)
                army.add_unit(leader)
                spent_by_name[leader.name] += leader.points_cost
                remaining -= leader.points_cost

    # Pick a detachment that suits the actual composition. Done AFTER unit
    # selection so the picker can read the real vehicle / infantry mix
    # rather than guessing from faction defaults. Falls back to None if
    # the faction is unmapped — `Army.resolve_detachment` then re-tries
    # the default lookup, preserving prior behaviour for edge cases.
    if army.units:
        army.detachment = pick_detachment_for_army(faction, army.units, rng)

    # 10e Enhancement: if the resolved detachment carries enhancements,
    # pick one and attach to a CHARACTER. The cost is recorded on the
    # army (subtracted from remaining budget for reporting); we don't
    # try to claw points back from already-picked units — instead the
    # army_points accounting reports `total_points - enhancement.cost`
    # for the "what the player paid" view used by tests.
    _assign_enhancement_to_warlord(army, rng)

    return army
