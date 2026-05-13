"""
Map BSData WH40k 2nd-Edition stats into the SwegHammer abstraction.

The mapping is intentionally lossy: 2nd-ed has M/WS/BS/S/T/W/I/A/LD; SwegHammer
collapses that into (health, damage, hit_probability, ap, save). The translation
rules are:

    health         <- W
    hit_probability<- BS  (target = 7 - BS on d6, hit prob = (7 - target) / 6)
    damage         <- best weapon's average Damage characteristic
    ap             <- best weapon's Save Modifier
    save           <- armour profile's Saving Throw (if any in the loadout tree)

"Best weapon" = the single legal weapon in the unit's wargear tree that maximises
the SwegHammer offensive metric  d * p * (1 - baseline_save_after_AP),  i.e. the
weapon that pushes the most damage through a baseline Space Marine's armour. This
respects the user's instruction to assume the best legal loadout rather than the
cheapest default.

Profiles that cannot be cleanly mapped (vehicles, characters with no weapon, etc.)
are emitted with enabled=False and a `skip_reason` so they can be repaired via
overrides without losing visibility.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .fetch import CACHE_DIR
from .parser import (
    Registry,
    iter_unit_entries,
    load_registry,
    profile_characteristics,
    selection_cost,
)

PARSED_PATH = CACHE_DIR.parent / "parsed.json"

# Baseline Marine for the offensive metric — kept in sync with code/units.py
BASELINE_SAVE = 3
BASELINE_AP = 0


# ---------------------------------------------------------------------------
# Numeric parsers
# ---------------------------------------------------------------------------

_DICE_RE = re.compile(r"(\d*)[dD](\d+)")
_INT_RE = re.compile(r"-?\d+")


def parse_damage(text: str) -> Optional[float]:
    """
    Convert a 2nd-ed Damage string to its expected value.

        "1"        -> 1
        "2"        -> 2
        "D3"       -> 2.0
        "D6"       -> 3.5
        "2D6"      -> 7.0
        "D6+2"     -> 5.5
        "D6+D3+5"  -> 10.5
        "-"        -> None  (no damage / not applicable)
    """
    if not text:
        return None
    s = text.strip()
    if not s or s in {"-", "—", "None", "N/A"}:
        return None

    total = 0.0
    # Sum dice terms
    for count_str, sides_str in _DICE_RE.findall(s):
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        total += count * (sides + 1) / 2.0

    # Strip dice terms, then sum any leftover integer offsets
    stripped = _DICE_RE.sub("", s)
    for n in _INT_RE.findall(stripped):
        total += int(n)

    return total if total > 0 else None


def parse_save(text: str) -> Optional[int]:
    """
    Parse a Saving Throw characteristic into a 2-6 d6 target, or None if no save.

        "3+"           -> 3
        "4+ Save"      -> 4
        "2+ (on 2D6)"  -> 2   (we don't model 2d6 saves yet)
        ""             -> None
    """
    if not text:
        return None
    m = re.search(r"(\d)\s*\+", text)
    if not m:
        return None
    return int(m.group(1))


def bs_to_hit_probability(bs: int) -> float:
    """
    2nd-ed BS → d6 hit probability.

    Target to-hit on d6 = 7 - BS, clamped to [1, 7].
    BS 4 → 3+ → 4/6.   BS 6 → 1+ → 6/6.   BS 0 → 7+ → 0 (cannot shoot).
    """
    target = 7 - bs
    if target <= 1:
        return 1.0
    if target >= 7:
        return 0.0
    return (7 - target) / 6.0


def _baseline_save_after_ap(ap: int) -> float:
    """How likely a baseline Marine is to save against a weapon with this AP."""
    effective = BASELINE_SAVE - ap  # ap is negative
    if effective > 6:
        return 0.0
    return max(0.0, (7 - effective) / 6.0)


# ---------------------------------------------------------------------------
# Stat extraction helpers
# ---------------------------------------------------------------------------

def _to_int(text: str) -> Optional[int]:
    if text is None:
        return None
    m = _INT_RE.search(text.strip())
    return int(m.group(0)) if m else None


def extract_unit_stat_line(profile: ET.Element) -> Dict[str, Optional[int]]:
    """Pull M/WS/BS/S/T/W/I/A/LD as ints from a Unit profile."""
    chars = profile_characteristics(profile)
    return {
        "M": _to_int(chars.get("M", "")),
        "WS": _to_int(chars.get("WS", "")),
        "BS": _to_int(chars.get("BS", "")),
        "S": _to_int(chars.get("S", "")),
        "T": _to_int(chars.get("T", "")),
        "W": _to_int(chars.get("W", "")),
        "I": _to_int(chars.get("I", "")),
        "A": _to_int(chars.get("A", "")),
        "LD": _to_int(chars.get("LD", "")),
    }


@dataclass
class WeaponStats:
    name: str
    damage: float
    save_modifier: int   # already negative-or-zero
    strength: Optional[int] = None
    raw_damage: str = ""
    raw_save_mod: str = ""

    def offensive_score(self, hit_prob: float) -> float:
        return self.damage * hit_prob * (1.0 - _baseline_save_after_ap(self.save_modifier))


def extract_weapon(profile: ET.Element) -> Optional[WeaponStats]:
    """Convert a Weapon profile element into WeaponStats, or None if unparseable."""
    chars = profile_characteristics(profile)
    raw_dmg = chars.get("Damage", "")
    raw_mod = chars.get("Save Modifier", "")
    dmg = parse_damage(raw_dmg)
    if dmg is None:
        return None
    save_mod = 0
    if raw_mod:
        m = re.search(r"-?\d+", raw_mod)
        if m:
            save_mod = int(m.group(0))
    return WeaponStats(
        name=profile.get("name") or "?",
        damage=dmg,
        save_modifier=save_mod,
        strength=_to_int(chars.get("Strength", "")),
        raw_damage=raw_dmg,
        raw_save_mod=raw_mod,
    )


# ---------------------------------------------------------------------------
# Tree walker
# ---------------------------------------------------------------------------

@dataclass
class UnitWargear:
    unit_profile: Optional[ET.Element] = None
    weapons: List[WeaponStats] = field(default_factory=list)
    armour_save: Optional[int] = None
    armour_name: str = ""


def _resolve_profiles_in_subtree(
    elem: ET.Element, reg: Registry, seen: set, out: UnitWargear, depth: int = 0,
    max_depth: int = 3,
) -> None:
    """
    Recursively walk a selectionEntry, collecting profiles. We stop at depth 3 to
    avoid bleeding into faction-wide shared wargear pools — depth 0 is the unit
    itself, depth 1 is its direct wargear slots, depth 2 is the options inside
    each slot, and depth 3 lets us follow one cross-reference (e.g. a slot that
    points to a shared "Special Weapons" group).

    Loops are broken by tracking visited element ids.
    """
    if depth > max_depth:
        return
    eid = elem.get("id")
    if eid:
        if eid in seen:
            return
        seen.add(eid)

    # 1. Inline profiles inside this entry
    for prof in elem.findall("./profiles/profile"):
        _consume_profile(prof, out, depth)

    # 2. infoLinks directly on this element → resolve to a profile
    for il in elem.findall("./infoLinks/infoLink"):
        if il.get("type") != "profile":
            continue
        target = reg.resolve(il.get("targetId") or "")
        if target is not None and target.tag == "profile":
            _consume_profile(target, out, depth)

    # 3. entryLinks → recurse into target selectionEntry / selectionEntryGroup
    for el in elem.findall("./entryLinks/entryLink"):
        # An entryLink can carry its own infoLinks (e.g. Power Armour's bundled bolter)
        for il in el.findall("./infoLinks/infoLink"):
            if il.get("type") != "profile":
                continue
            tgt = reg.resolve(il.get("targetId") or "")
            if tgt is not None and tgt.tag == "profile":
                _consume_profile(tgt, out, depth)
        target = reg.resolve(el.get("targetId") or "")
        if target is not None:
            _resolve_profiles_in_subtree(target, reg, seen, out, depth + 1, max_depth)

    # 4. Nested selectionEntries and groups
    for child in elem.findall("./selectionEntries/selectionEntry"):
        _resolve_profiles_in_subtree(child, reg, seen, out, depth + 1, max_depth)
    for grp in elem.findall("./selectionEntryGroups/selectionEntryGroup"):
        _resolve_profiles_in_subtree(grp, reg, seen, out, depth + 1, max_depth)


def _consume_profile(prof: ET.Element, out: UnitWargear, depth: int = 0) -> None:
    """
    Record a profile into the wargear bag.

    Armour is recorded only from the closest match (lowest depth) so that we
    don't accidentally pick up Terminator armour from a sibling option group when
    the actual unit wears Power Armour.
    """
    type_name = prof.get("typeName") or ""
    if type_name == "Unit" and out.unit_profile is None:
        out.unit_profile = prof
    elif type_name in ("Weapon", "Weapon - Missile / Grenade"):
        w = extract_weapon(prof)
        if w is not None:
            out.weapons.append(w)
    elif type_name == "Armour":
        chars = profile_characteristics(prof)
        sv = parse_save(chars.get("Saving Throw", ""))
        if sv is None:
            return
        # Closest-armour rule: only overwrite if this match is strictly closer
        # than the previous one. _armour_depth tracks the depth of the chosen
        # armour profile (None = not yet set).
        prev_depth = getattr(out, "_armour_depth", None)
        if prev_depth is None or depth < prev_depth:
            out.armour_save = sv
            out.armour_name = prof.get("name") or ""
            out._armour_depth = depth  # type: ignore[attr-defined]


def gather_wargear(entry: ET.Element, reg: Registry) -> UnitWargear:
    out = UnitWargear()
    _resolve_profiles_in_subtree(entry, reg, set(), out)
    return out


# ---------------------------------------------------------------------------
# Mapping to SwegHammer
# ---------------------------------------------------------------------------

@dataclass
class MappedUnit:
    """SwegHammer-shaped unit derived from BSData."""

    key: str                 # canonical slug for catalogue lookup
    name: str
    codex: str
    health: float
    damage: float
    hit_probability: float
    ap: int
    save: int                # 2-6, or 7 = no save
    points_listed: float     # BSData's listed cost (informational)
    loadout: List[str] = field(default_factory=list)
    notes: str = ""
    enabled: bool = True
    skip_reason: str = ""


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(codex: str, name: str) -> str:
    short_codex = codex.replace("Codex - ", "").replace("Codex ", "").replace(".cat", "")
    short_codex = short_codex.split(" (")[0].strip()
    base = f"{short_codex}-{name}".lower()
    return _SLUG_RE.sub("_", base).strip("_")


def map_unit(codex: str, entry: ET.Element, reg: Registry) -> MappedUnit:
    name = entry.get("name") or "?"
    key = _slugify(codex, name)
    gear = gather_wargear(entry, reg)
    points = selection_cost(entry)

    if gear.unit_profile is None:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=0, damage=0, hit_probability=0, ap=0, save=7,
            points_listed=points, enabled=False, skip_reason="no unit profile in loadout tree",
        )

    stats = extract_unit_stat_line(gear.unit_profile)
    if stats["BS"] is None or stats["W"] is None:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=float(stats["W"] or 0), damage=0,
            hit_probability=0, ap=0, save=7,
            points_listed=points, enabled=False, skip_reason="missing BS or W on unit profile",
        )

    hit_prob = bs_to_hit_probability(stats["BS"])

    if not gear.weapons:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=float(stats["W"]), damage=0,
            hit_probability=hit_prob, ap=0, save=gear.armour_save or 7,
            points_listed=points, enabled=False, skip_reason="no weapons resolvable from tree",
        )

    # Best legal loadout = weapon maximising offensive damage through baseline Marine armour
    best_weapon = max(gear.weapons, key=lambda w: w.offensive_score(hit_prob))

    return MappedUnit(
        key=key,
        name=name,
        codex=codex,
        health=float(stats["W"]),
        damage=round(best_weapon.damage, 2),
        hit_probability=round(hit_prob, 3),
        ap=best_weapon.save_modifier,
        save=gear.armour_save if gear.armour_save is not None else 7,
        points_listed=points,
        loadout=[best_weapon.name]
        + [w.name for w in gear.weapons if w.name != best_weapon.name][:4],
        notes=f"unit_type={stats}",
    )


def map_all(reg: Optional[Registry] = None) -> List[MappedUnit]:
    if reg is None:
        reg = load_registry()
    return [map_unit(codex, entry, reg) for codex, entry in iter_unit_entries(reg)]


def write_parsed_json(units: Iterable[MappedUnit], path: Path = PARSED_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"units": [asdict(u) for u in units]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    reg = load_registry()
    units = map_all(reg)
    enabled = [u for u in units if u.enabled]
    skipped = [u for u in units if not u.enabled]
    write_parsed_json(units)
    print(f"[mapper] mapped {len(enabled)} units, skipped {len(skipped)}")
    print(f"[mapper] wrote {PARSED_PATH}")

    # Show a few examples for spot-check
    for u in enabled[:8]:
        print(
            f"  {u.codex.replace('Codex - ', '')[:18]:18}  "
            f"{u.name[:24]:24}  H={u.health:>4.1f} D={u.damage:>4.1f} "
            f"Hit={u.hit_probability:>5.2f} AP={u.ap:>2} Sv={u.save} "
            f"BS-pts={u.points_listed:>4.0f}  best={u.loadout[0] if u.loadout else '-'}"
        )
    if skipped:
        print(f"\n  skipped reasons:")
        from collections import Counter
        for reason, n in Counter(u.skip_reason for u in skipped).most_common():
            print(f"    {n:4}  {reason}")


if __name__ == "__main__":
    main()
