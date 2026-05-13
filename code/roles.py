"""
Unit role classification.

Derives a coarse "role" label from each UnitProfile's stat block so other
modules can reason about kind-of-unit rather than just raw stats:

  - SHOOTY      : ranged DPA >> melee DPA; tanks, gunlines, snipers
  - MELEE       : melee DPA >> ranged DPA; close-combat specialists
  - DUAL        : both meaningful; flexible threats (Intercessors, Boyz)
  - HORDE       : single-wound, low Sv, count-on-numbers infantry
  - HEAVY       : high-wound, low save-after-AP defenders (vehicles, monsters)
  - SUPPORT     : low offensive output overall (characters that buff others)

Used by:
  - simulator: charge-desire (only MELEE / DUAL want to charge)
  - balancer:  role-stratified calibration — compare a unit against a
    same-role baseline rather than always against Intercessor Squad
"""

from __future__ import annotations

from typing import Dict, Tuple

from .units import UnitProfile, wound_probability


def expected_ranged_dpa(p: UnitProfile, target_t: int = 4, target_sv: int = 3) -> float:
    """Expected ranged damage per activation against a generic Marine-ish target."""
    if p.attacks <= 0:
        return 0.0
    wound_p = wound_probability(p.strength, target_t)
    sv_after_ap = max(2, target_sv - p.ap)
    unsaved = max(0.0, 1.0 - (7 - sv_after_ap) / 6.0) if sv_after_ap <= 6 else 1.0
    return p.attacks * p.hit_probability * wound_p * unsaved * p.per_shot_damage


def expected_melee_dpa(p: UnitProfile, target_t: int = 4, target_sv: int = 3) -> float:
    """Expected melee damage per activation."""
    if p.melee_attacks <= 0 or p.melee_hit_probability <= 0:
        return 0.0
    wound_p = wound_probability(p.melee_strength, target_t)
    sv_after_ap = max(2, target_sv - p.melee_ap)
    unsaved = max(0.0, 1.0 - (7 - sv_after_ap) / 6.0) if sv_after_ap <= 6 else 1.0
    return p.melee_attacks * p.melee_hit_probability * wound_p * unsaved * (p.melee_damage_per_shot or 1.0)


def classify(p: UnitProfile) -> str:
    """Return the role label for this UnitProfile."""
    r = expected_ranged_dpa(p)
    m = expected_melee_dpa(p)
    total = r + m

    # HORDE check FIRST — H=1 Sv 5+/6+ infantry are HORDE even at very low DPA
    if p.health == 1 and p.save >= 5 and total < 1.5:
        return "HORDE"

    if total <= 0.4:
        return "SUPPORT"

    # HEAVY: substantial wounds AND tough armour
    if p.health >= 8 and p.save <= 3:
        return "HEAVY"

    # MELEE / SHOOTY / DUAL by ratio
    if m == 0:
        return "SHOOTY"
    if r == 0:
        return "MELEE"
    ratio = m / max(r, 1e-6)
    if ratio >= 1.5:
        return "MELEE"
    if ratio <= 0.4:
        return "SHOOTY"
    return "DUAL"


def classify_catalogue(catalog: Dict[str, UnitProfile]) -> Dict[str, str]:
    """Map every catalogue key to its role label."""
    return {k: classify(p) for k, p in catalog.items()}


# ---------------------------------------------------------------------------
# Role baselines — used by the balancer for like-vs-like calibration
# ---------------------------------------------------------------------------

ROLE_BASELINES: Dict[str, str] = {
    "SHOOTY":  "space_marines_intercessor_squad",
    "DUAL":    "space_marines_intercessor_squad",
    "MELEE":   "space_marines_assault_intercessor_squad",
    "HORDE":   "orks_boyz",
    "HEAVY":   "imperial_knights_library_knight_errant",
    "SUPPORT": "space_marines_captain_in_terminator_armour",
}


def baseline_key_for(role: str) -> str:
    """Pick a sensible same-role baseline key. Defaults to Intercessor."""
    return ROLE_BASELINES.get(role, "space_marines_intercessor_squad")
