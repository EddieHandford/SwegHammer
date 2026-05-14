"""
Leader abilities — proximity-gated aura buffs from attached CHARACTER units.

10e attached leaders sit inside a friendly squad and project an aura: nearby
friendlies get to-hit / to-wound buffs, re-rolls, an invuln, Feel No Pain, or
mid-battle healing. This module is the MVP version of that: a small registry
of well-known characters keyed by substring match on the profile name, plus a
single helper `effective_buffs(attacker)` that merges:

    detachment passives (Army.resolve_detachment())
        +
    every alive friendly leader whose aura covers the attacker

into one buff dict the simulator can consume.

Wiring:
  - `Unit.attack` calls `effective_buffs(attacker)` to compose flags from the
    detachment and any in-range leader auras (re-roll 1s, +1 to hit / wound,
    extra invuln, FNP).
  - `Battle._run_round` runs `apply_round_end_healing(army)` so leaders with
    `heal_per_round > 0` patch up a nearby wounded friendly each round end.

The registry is intentionally small. Substring matching against `profile.name`
catches the obvious variants ("Captain in Terminator Armour" matches "Captain"),
which is enough to demonstrate the mechanic. Bespoke per-character abilities
(Lethal Hits aura, Oath of Moment, mortal-wound bombs etc.) are deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .army import Army
    from .units import Unit


# ---------------------------------------------------------------------------
# LeaderAbility — same modifier shape as Detachment, plus aura range + heal
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LeaderAbility:
    """
    Aura buff granted by an attached CHARACTER to nearby friendlies.

    Modifier flags use the same convention as `Detachment`:
      * boolean fields: True = active
      * `extra_invuln`, `fnp`: 7 = none, lower number = better (10e d6 target)

    `aura_range` is in inches. `0` means army-wide (no proximity gating).
    """
    name: str
    aura_range: float                       # inches; 0 = army-wide
    # Offensive modifiers (apply to ATTACKER when it's in range of this leader)
    reroll_hit_ones: bool = False
    reroll_wound_ones: bool = False
    plus_one_to_hit: bool = False
    plus_one_to_wound: bool = False
    # Defensive modifiers (apply to DEFENDER when it's in range of this leader)
    extra_invuln: int = 7                   # 7 = none
    fnp: int = 7                            # 7 = none
    # End-of-round healing: restore N HP to the nearest wounded friendly in
    # aura range (or to the leader itself if none are wounded).
    heal_per_round: int = 0


# ---------------------------------------------------------------------------
# Registry — substring-keyed lookup by profile name
# ---------------------------------------------------------------------------
# Order matters: longer / more specific keys come FIRST so that
# "Captain in Terminator Armour" matches "Captain" cleanly but doesn't
# accidentally collide with a hypothetical future "Captain-General".

_REGISTRY: Tuple[Tuple[str, LeaderAbility], ...] = (
    # Space Marine HQ
    ("Captain",            LeaderAbility(name="Rites of Battle",            aura_range=6.0, reroll_hit_ones=True)),
    ("Chaplain",           LeaderAbility(name="Spiritual Leader",           aura_range=6.0, reroll_wound_ones=True)),
    ("Apothecary",         LeaderAbility(name="Combat Restoratives",        aura_range=3.0, heal_per_round=1)),
    ("Librarian",          LeaderAbility(name="Psychic Empowerment",        aura_range=6.0, plus_one_to_wound=True)),
    # Adepta Sororitas
    ("Canoness",           LeaderAbility(name="Beacon of Faith",            aura_range=6.0, reroll_hit_ones=True)),
    # Necrons
    ("Overlord",           LeaderAbility(name="My Will Be Done",            aura_range=6.0, plus_one_to_hit=True)),
    ("Chronomancer",       LeaderAbility(name="Chronometron",               aura_range=6.0, fnp=5)),
    ("Plasmancer",         LeaderAbility(name="Harbinger of Destruction",   aura_range=6.0, fnp=5)),
    ("Technomancer",       LeaderAbility(name="Canoptek Cloak",             aura_range=6.0, fnp=5)),
    # Orks
    ("Warboss",            LeaderAbility(name="Waaagh! Boss",               aura_range=6.0, plus_one_to_wound=True)),
    # Tyranids
    ("Hive Tyrant",        LeaderAbility(name="Synaptic Imperative",        aura_range=6.0, reroll_wound_ones=True)),
    # Aeldari
    ("Farseer",            LeaderAbility(name="Runes of Fate",              aura_range=6.0, reroll_wound_ones=True)),
    ("Autarch",            LeaderAbility(name="Path of Command",            aura_range=6.0, plus_one_to_hit=True)),
    ("Avatar of Khaine",   LeaderAbility(name="Avatar's Fury",              aura_range=6.0, reroll_hit_ones=True)),
    # T'au Empire
    ("Ethereal",           LeaderAbility(name="Guiding Hand of the Greater Good", aura_range=6.0, reroll_wound_ones=True)),
    ("Commander in",       LeaderAbility(name="Coordinated Fire Plan",      aura_range=6.0, plus_one_to_hit=True)),
    ("Cadre Fireblade",    LeaderAbility(name="Volley Fire",                aura_range=6.0, reroll_hit_ones=True)),
    # Chaos Space Marines
    ("Sorcerer",           LeaderAbility(name="Death Hex",                  aura_range=6.0, plus_one_to_wound=True)),
    ("Dark Apostle",       LeaderAbility(name="Profane Litanies",           aura_range=6.0, reroll_hit_ones=True)),
    ("Chaos Lord",         LeaderAbility(name="Lord of Hosts",              aura_range=6.0, plus_one_to_wound=True)),
    # Adeptus Custodes
    ("Shield-Captain",     LeaderAbility(name="Stoic Vigil",                aura_range=6.0, reroll_hit_ones=True)),
    ("Trajann Valoris",    LeaderAbility(name="Auric Sage",                 aura_range=6.0, plus_one_to_hit=True)),
    # Adeptus Mechanicus
    ("Tech-Priest Dominus", LeaderAbility(name="Master of the Machine",    aura_range=6.0, reroll_hit_ones=True, heal_per_round=1)),
    # Death Guard
    ("Lord of Contagion",  LeaderAbility(name="Plague-Ridden Champion",     aura_range=6.0, plus_one_to_wound=True)),
    ("Typhus",             LeaderAbility(name="Host of the Destroyer Hive", aura_range=6.0, reroll_wound_ones=True)),
    # Grey Knights
    ("Brother-Captain",    LeaderAbility(name="First to the Fray",          aura_range=6.0, reroll_hit_ones=True)),
    ("Grand Master",       LeaderAbility(name="Tactical Acumen",            aura_range=6.0, plus_one_to_wound=True)),
    # Drukhari
    ("Archon",             LeaderAbility(name="Overlord of Commorragh",     aura_range=6.0, plus_one_to_hit=True)),
    ("Succubus",           LeaderAbility(name="Precision Blows",            aura_range=6.0, reroll_hit_ones=True)),
    # Genestealer Cults
    ("Primus",             LeaderAbility(name="Meticulous Uprising",       aura_range=6.0, reroll_hit_ones=True)),
    # Leagues of Votann
    ("Kâhl",               LeaderAbility(name="Warrior-Forged Leadership",  aura_range=6.0, plus_one_to_hit=True)),
)


def lookup_ability(profile_name: str) -> Optional[LeaderAbility]:
    """
    Find a LeaderAbility by substring match against the unit's profile name.

    "Captain in Terminator Armour" -> matches "Captain" -> Rites of Battle.
    Returns None if no entry matches.
    """
    if not profile_name:
        return None
    for key, ability in _REGISTRY:
        if key in profile_name:
            return ability
    return None


# ---------------------------------------------------------------------------
# Aura application — merge detachment + in-range leader flags
# ---------------------------------------------------------------------------

# Default buff dict: all flags off / neutral. Same shape Unit.attack consumes.
_NEUTRAL_BUFFS: Dict[str, object] = {
    "reroll_hit_ones": False,
    "reroll_wound_ones": False,
    "plus_one_to_hit": False,
    "plus_one_to_wound": False,
    "plus_one_attack": 0,
    "plus_one_save": False,
    "extra_invuln": 7,
    "fnp": 7,
}


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def _merge_bool(target: Dict[str, object], source: object, key: str) -> None:
    """OR-merge a boolean flag: any source granting it wins."""
    if getattr(source, key, False):
        target[key] = True


def _merge_min(target: Dict[str, object], source: object, key: str, default_off: int = 7) -> None:
    """Take the better (lower) of the two values, treating `default_off` as off."""
    s_val = getattr(source, key, default_off)
    if s_val < target[key]:
        target[key] = s_val


def _merge_add(target: Dict[str, object], source: object, key: str) -> None:
    """Additive int merge — used for plus_one_attack stacking."""
    s_val = getattr(source, key, 0)
    if s_val:
        target[key] = target[key] + s_val


def in_range_leaders(attacker: "Unit") -> List["Unit"]:
    """
    Return alive friendly CHARACTER units whose aura covers `attacker`.

    A leader covers the attacker if:
      * its aura_range is 0 (army-wide), OR
      * the distance from leader to attacker is <= aura_range.

    Leaders without a registered ability are skipped.
    """
    army = getattr(attacker, "army_ref", None)
    if army is None:
        return []
    covered: List["Unit"] = []
    for u in army.alive_units:
        if u is attacker:
            continue
        ability = lookup_ability(u.profile.name)
        if ability is None:
            continue
        if ability.aura_range <= 0:
            covered.append(u)
        else:
            if _distance(u.position, attacker.position) <= ability.aura_range:
                covered.append(u)
    return covered


def effective_buffs(attacker: "Unit") -> Dict[str, object]:
    """
    Merge the attacker's detachment passives with every in-range friendly
    leader's aura flags. Returns a buff dict with the same field names as
    `Detachment`. Booleans OR together; `extra_invuln` / `fnp` take the min.

    Detachment carries all the boolean attack flags + plus_one_attack +
    plus_one_save + extra_invuln. Leader auras add the offensive booleans,
    extra_invuln, and FNP (which detachments don't currently expose).
    """
    buffs = dict(_NEUTRAL_BUFFS)

    army = getattr(attacker, "army_ref", None)
    if army is not None:
        try:
            det = army.resolve_detachment()
        except Exception:
            det = None
        if det is not None:
            _merge_bool(buffs, det, "reroll_hit_ones")
            _merge_bool(buffs, det, "reroll_wound_ones")
            _merge_bool(buffs, det, "plus_one_to_hit")
            _merge_bool(buffs, det, "plus_one_to_wound")
            _merge_bool(buffs, det, "plus_one_save")
            _merge_add(buffs, det, "plus_one_attack")
            _merge_min(buffs, det, "extra_invuln")
            _merge_min(buffs, det, "fnp")

    for leader in in_range_leaders(attacker):
        ability = lookup_ability(leader.profile.name)
        if ability is None:
            continue
        _merge_bool(buffs, ability, "reroll_hit_ones")
        _merge_bool(buffs, ability, "reroll_wound_ones")
        _merge_bool(buffs, ability, "plus_one_to_hit")
        _merge_bool(buffs, ability, "plus_one_to_wound")
        _merge_min(buffs, ability, "extra_invuln")
        _merge_min(buffs, ability, "fnp")

    return buffs


# ---------------------------------------------------------------------------
# Round-end healing
# ---------------------------------------------------------------------------

def apply_round_end_healing(army: "Army") -> None:
    """
    End-of-round leader heal: every alive leader with heal_per_round > 0
    restores HP. Priority:
      1. nearest WOUNDED friendly within aura_range (lowest current_health
         first, ties broken by distance);
      2. else the leader itself if it's wounded;
      3. else no-op.

    Cap at the recipient's max health.
    """
    for leader in army.alive_units:
        ability = lookup_ability(leader.profile.name)
        if ability is None or ability.heal_per_round <= 0:
            continue

        # Build candidate list: wounded friendlies in aura
        candidates: List["Unit"] = []
        for u in army.alive_units:
            if u is leader:
                continue
            if u.current_health >= u.profile.health:
                continue   # already at full HP
            if ability.aura_range > 0:
                if _distance(leader.position, u.position) > ability.aura_range:
                    continue
            candidates.append(u)

        recipient: Optional["Unit"] = None
        if candidates:
            # Pick the most-wounded; tie-break by proximity to the leader
            candidates.sort(
                key=lambda u: (
                    u.current_health,
                    _distance(leader.position, u.position),
                )
            )
            recipient = candidates[0]
        elif leader.current_health < leader.profile.health:
            recipient = leader

        if recipient is None:
            continue
        recipient.current_health = min(
            recipient.profile.health,
            recipient.current_health + ability.heal_per_round,
        )
