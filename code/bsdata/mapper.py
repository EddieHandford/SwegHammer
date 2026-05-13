"""
Map BSData WH40k 10th-Edition stats into the SwegHammer abstraction.

10e has a cleaner schema than 2nd ed for our purposes:
  - Save (SV) lives directly on the Unit profile — no separate Armour profile.
  - Vehicles use the same T/W/SV stats as everyone else (no armour facings).
  - Weapons split into typeName="Ranged Weapons" / "Melee Weapons" with explicit
    A (attacks), BS/WS, S, AP, D characteristics.

SwegHammer mapping:

    health         <- W
    save           <- SV  ("3+" -> 3)
    hit_probability<- BS  ("3+" -> (7-3)/6 = 4/6)
    damage         <- A * D  (best ranged weapon's expected damage per activation)
    ap             <- best ranged weapon's AP

"Best weapon" = the legal weapon in the unit's wargear tree that maximises
the SwegHammer offensive metric  attacks * hit_prob * damage *
(1 - baseline_save_after_AP).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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
_PLUS_RE = re.compile(r"(\d+)\s*\+")


def parse_dice_expr(text: str) -> Optional[float]:
    """
    Convert a 10e dice/damage characteristic to its expected value.

        "1"       -> 1
        "3"       -> 3
        "D3"      -> 2.0
        "D6"      -> 3.5
        "2D6"     -> 7.0
        "D6+2"    -> 5.5
        "-"       -> None
        "N/A"     -> None
    """
    if not text:
        return None
    s = text.strip()
    if not s or s in {"-", "—", "N/A", "None"}:
        return None

    total = 0.0
    for count_str, sides_str in _DICE_RE.findall(s):
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        total += count * (sides + 1) / 2.0

    stripped = _DICE_RE.sub("", s)
    for n in _INT_RE.findall(stripped):
        total += int(n)

    return total if total > 0 else None


def parse_plus_target(text: str) -> Optional[int]:
    """
    Parse a "N+" target characteristic to the d6 target value.

        "3+"   -> 3
        "2+"   -> 2
        ""     -> None
    """
    if not text:
        return None
    m = _PLUS_RE.search(text.strip())
    return int(m.group(1)) if m else None


def target_to_hit_probability(target: Optional[int]) -> float:
    """d6 hit probability for a target like 3+ → (7-3)/6 = 4/6."""
    if target is None:
        return 0.0
    if target <= 1:
        return 1.0
    if target >= 7:
        return 0.0
    return (7 - target) / 6.0


def _to_int(text: str) -> Optional[int]:
    """First integer in a string, or None. Accepts "4", "S+1", "User" → None, etc."""
    if not text:
        return None
    m = _INT_RE.search(text.strip())
    return int(m.group(0)) if m else None


def parse_ap(text: str) -> int:
    """AP is already given negative in 10e, e.g. "-2". Returns 0 if missing."""
    if not text:
        return 0
    m = _INT_RE.search(text.strip())
    return int(m.group(0)) if m else 0


def _baseline_save_after_ap(ap: int) -> float:
    """Probability a baseline Marine saves against a weapon with this AP."""
    effective = BASELINE_SAVE - ap  # ap is negative
    if effective > 6:
        return 0.0
    return max(0.0, (7 - effective) / 6.0)


# ---------------------------------------------------------------------------
# 10e stat extraction
# ---------------------------------------------------------------------------

@dataclass
class UnitStatLine:
    movement: str = ""
    toughness: Optional[int] = None
    save: Optional[int] = None       # parsed "3+" -> 3
    wounds: Optional[int] = None
    leadership: Optional[int] = None
    oc: Optional[int] = None


def extract_unit_stat_line(profile: ET.Element) -> UnitStatLine:
    chars = profile_characteristics(profile)

    def _int(field: str) -> Optional[int]:
        m = _INT_RE.search(chars.get(field, ""))
        return int(m.group(0)) if m else None

    return UnitStatLine(
        movement=chars.get("M", ""),
        toughness=_int("T"),
        save=parse_plus_target(chars.get("SV", "")),
        wounds=_int("W"),
        leadership=parse_plus_target(chars.get("LD", "")),
        oc=_int("OC"),
    )


def is_unit_profile(profile: ET.Element) -> bool:
    """A 10e unit profile is one whose characteristics include both W and SV."""
    if profile.tag != "profile":
        return False
    chars = profile_characteristics(profile)
    return "W" in chars and "SV" in chars


@dataclass
class WeaponStats:
    name: str
    attacks: float
    hit_prob: float
    damage: float
    ap: int
    strength: int = 4
    range: str = ""
    keywords: str = ""
    # Parsed keyword effects (populated by extract_ranged_weapon)
    lethal_hits: bool = False
    sustained_hits: int = 0
    twin_linked: bool = False
    devastating_wounds: bool = False
    rapid_fire: int = 0
    melta: int = 0
    ignores_cover: bool = False
    anti_keywords: dict = field(default_factory=dict)
    heavy: bool = False
    assault: bool = False
    torrent: bool = False
    hazardous: bool = False
    blast: bool = False

    def expected_damage_through_baseline(self) -> float:
        """Expected damage per activation against a baseline Marine."""
        base = (
            self.attacks
            * self.hit_prob
            * self.damage
            * (1.0 - _baseline_save_after_ap(self.ap))
        )
        # Approximate ability boosts so the loadout optimiser doesn't undervalue
        # high-ability weapons. Small multiplicative bumps based on common math.
        if self.lethal_hits:
            base *= 1.15
        if self.sustained_hits:
            base *= (1.0 + 0.17 * self.sustained_hits)   # 1/6 crit rate × N
        if self.twin_linked:
            base *= 1.30
        if self.devastating_wounds:
            base *= 1.10
        return base


_KEYWORD_SUSTAINED = re.compile(r"Sustained\s+Hits\s+(\d+|D3|D6)", re.IGNORECASE)
_RAPID_FIRE_RE = re.compile(r"Rapid\s+Fire\s*(\d+)", re.IGNORECASE)
_MELTA_RE = re.compile(r"\bMelta\s*(\d+)", re.IGNORECASE)
_IGNORES_COVER_RE = re.compile(r"Ignores\s+Cover", re.IGNORECASE)
_ANTI_RE = re.compile(r"Anti-([A-Z][A-Z_-]+)\s*(\d)\s*\+", re.IGNORECASE)
_HEAVY_RE = re.compile(r"(?:^|[\s,;.])Heavy(?:$|[\s,;.])")
_ASSAULT_RE = re.compile(r"(?:^|[\s,;.])Assault(?:$|[\s,;.])")
_TORRENT_RE = re.compile(r"\bTorrent\b", re.IGNORECASE)
_HAZARDOUS_RE = re.compile(r"\bHazardous\b", re.IGNORECASE)
_BLAST_RE = re.compile(r"\bBlast\b", re.IGNORECASE)


def parse_weapon_keywords(text: str) -> Dict[str, object]:
    """
    Scan a weapon's `Keywords` characteristic for the abilities we model.
    Returns a dict suitable for splat into WeaponStats kwargs.
    """
    if not text:
        return {}
    s = text
    out: Dict[str, object] = {}
    if re.search(r"\blethal\s+hits\b", s, re.IGNORECASE):
        out["lethal_hits"] = True
    if re.search(r"\btwin[\s-]?linked\b", s, re.IGNORECASE):
        out["twin_linked"] = True
    if re.search(r"\bdevastating\s+wounds\b", s, re.IGNORECASE):
        out["devastating_wounds"] = True
    m = _KEYWORD_SUSTAINED.search(s)
    if m:
        tok = m.group(1).upper()
        out["sustained_hits"] = {"D3": 2, "D6": 3}.get(tok, int(tok) if tok.isdigit() else 1)
    m = _RAPID_FIRE_RE.search(s)
    if m:
        out["rapid_fire"] = int(m.group(1))
    m = _MELTA_RE.search(s)
    if m:
        out["melta"] = int(m.group(1))
    if _IGNORES_COVER_RE.search(s):
        out["ignores_cover"] = True
    anti: Dict[str, int] = {}
    for kw, thresh in _ANTI_RE.findall(s):
        target = kw.upper().strip("_-")
        try:
            n = int(thresh)
        except ValueError:
            continue
        if target not in anti or n < anti[target]:
            anti[target] = n
    if anti:
        out["anti_keywords"] = anti
    if _HEAVY_RE.search(s):
        out["heavy"] = True
    if _ASSAULT_RE.search(s):
        out["assault"] = True
    if _TORRENT_RE.search(s):
        out["torrent"] = True
    if _HAZARDOUS_RE.search(s):
        out["hazardous"] = True
    if _BLAST_RE.search(s):
        out["blast"] = True
    return out


def extract_ranged_weapon(profile: ET.Element) -> Optional[WeaponStats]:
    type_name = profile.get("typeName") or ""
    if "Ranged" not in type_name:
        return None
    chars = profile_characteristics(profile)
    a = parse_dice_expr(chars.get("A", ""))
    d = parse_dice_expr(chars.get("D", ""))
    bs = parse_plus_target(chars.get("BS", ""))
    if a is None or d is None or bs is None:
        return None
    keywords = chars.get("Keywords", "")
    abilities = parse_weapon_keywords(keywords)
    # Strength can be a number or "User" (melee) — fall back to 4 if non-numeric.
    s_text = chars.get("S", "")
    s_int = _to_int(s_text) if s_text else None
    return WeaponStats(
        name=profile.get("name") or "?",
        attacks=a,
        hit_prob=target_to_hit_probability(bs),
        damage=d,
        ap=parse_ap(chars.get("AP", "")),
        strength=s_int if s_int is not None else 4,
        range=chars.get("Range", ""),
        keywords=keywords,
        **abilities,
    )


# ---------------------------------------------------------------------------
# Tree walker
# ---------------------------------------------------------------------------

@dataclass
class UnitWargear:
    unit_profile: Optional[ET.Element] = None
    ranged_weapons: List[WeaponStats] = field(default_factory=list)


def _walk(
    elem: ET.Element, reg: Registry, seen: set, out: UnitWargear,
    depth: int = 0, max_depth: int = 3,
) -> None:
    """Collect the unit profile + every ranged weapon reachable within depth."""
    if depth > max_depth:
        return
    eid = elem.get("id")
    if eid:
        if eid in seen:
            return
        seen.add(eid)

    # Inline profiles
    for prof in elem.findall("./profiles/profile"):
        _consume_profile(prof, out)

    # infoLinks → profiles
    for il in elem.findall("./infoLinks/infoLink"):
        if il.get("type") != "profile":
            continue
        target = reg.resolve(il.get("targetId") or "")
        if target is not None and target.tag == "profile":
            _consume_profile(target, out)

    # entryLinks — carry their own infoLinks, then recurse into the target
    for el in elem.findall("./entryLinks/entryLink"):
        for il in el.findall("./infoLinks/infoLink"):
            if il.get("type") != "profile":
                continue
            tgt = reg.resolve(il.get("targetId") or "")
            if tgt is not None and tgt.tag == "profile":
                _consume_profile(tgt, out)
        target = reg.resolve(el.get("targetId") or "")
        if target is not None:
            _walk(target, reg, seen, out, depth + 1, max_depth)

    # Nested selectionEntries / groups
    for child in elem.findall("./selectionEntries/selectionEntry"):
        _walk(child, reg, seen, out, depth + 1, max_depth)
    for grp in elem.findall("./selectionEntryGroups/selectionEntryGroup"):
        _walk(grp, reg, seen, out, depth + 1, max_depth)


def _consume_profile(prof: ET.Element, out: UnitWargear) -> None:
    type_name = prof.get("typeName") or ""
    if is_unit_profile(prof) and out.unit_profile is None:
        out.unit_profile = prof
        return
    if "Ranged" in type_name:
        w = extract_ranged_weapon(prof)
        if w is not None:
            out.ranged_weapons.append(w)


def gather_wargear(entry: ET.Element, reg: Registry) -> UnitWargear:
    out = UnitWargear()
    _walk(entry, reg, set(), out)
    return out


def extract_squad_size(entry: ET.Element) -> tuple[int, int]:
    """
    Return (min_models, max_models) for a unit selectionEntry.

    10e squads have an inner selectionEntryGroup whose name often follows
    "N-M <unit-noun>" and which carries `field="selections"` constraints with
    the squad size bounds. Single-model units (characters, vehicles, monsters)
    have no such group; we default to (1, 1).
    """
    for grp in entry.findall("./selectionEntryGroups/selectionEntryGroup"):
        mn: Optional[int] = None
        mx: Optional[int] = None
        for cons in grp.findall("./constraints/constraint"):
            if cons.get("field") != "selections":
                continue
            try:
                value = int(cons.get("value") or 0)
            except ValueError:
                continue
            if cons.get("type") == "min":
                mn = value
            elif cons.get("type") == "max":
                mx = value
        if mn is not None and mx is not None and mx >= mn >= 1:
            return mn, mx
    return 1, 1


# ---------------------------------------------------------------------------
# Mapping to SwegHammer
# ---------------------------------------------------------------------------

@dataclass
class MappedUnit:
    key: str
    name: str
    codex: str
    health: float
    damage: float
    hit_probability: float
    ap: int
    save: int                # 2-6, or 7 for no save
    points_listed: float     # BSData cost (for the minimum-size squad if it scales)
    min_models: int = 1
    max_models: int = 1
    # Stat-line attacker / defender numbers for the wound roll
    strength: int = 4        # weapon S used in the wound roll
    toughness: int = 4       # unit T defended in the wound roll
    leadership: int = 7      # Ld target for Battleshock (2D6 >= Ld passes)
    oc: int = 1              # Objective Control
    # Per-shot decomposition + weapon abilities
    attacks: int = 1
    weapon_damage_per_shot: float = 0.0
    lethal_hits: bool = False
    sustained_hits: int = 0
    twin_linked: bool = False
    devastating_wounds: bool = False
    invuln_save: int = 7    # parsed from "Invulnerable Save (X+*)" infoLinks in the tree
    # Phase A2/A3 keywords carried forward from the chosen ranged weapon
    rapid_fire: int = 0
    melta: int = 0
    ignores_cover: bool = False
    anti_keywords: dict = field(default_factory=dict)
    heavy: bool = False
    assault: bool = False
    torrent: bool = False
    hazardous: bool = False
    blast: bool = False
    # Unit-level
    fnp: int = 7                                  # 7 = no Feel No Pain
    unit_keywords: List[str] = field(default_factory=list)
    loadout: List[str] = field(default_factory=list)
    notes: str = ""
    enabled: bool = True
    skip_reason: str = ""


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(codex: str, name: str) -> str:
    short = codex.replace(".cat", "")
    # Drop common prefixes for cleaner keys
    for prefix in ("Imperium - Adeptus Astartes - ", "Imperium - ", "Chaos - "):
        if short.startswith(prefix):
            short = short[len(prefix):]
            break
    base = f"{short}-{name}".lower()
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
            points_listed=points, enabled=False,
            skip_reason="no unit profile (no W/SV characteristic) in tree",
        )

    stats = extract_unit_stat_line(gear.unit_profile)
    if stats.wounds is None or stats.save is None:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=float(stats.wounds or 0), damage=0,
            hit_probability=0, ap=0,
            save=stats.save if stats.save is not None else 7,
            points_listed=points, enabled=False,
            skip_reason="unit profile missing W or SV",
        )

    if not gear.ranged_weapons:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=float(stats.wounds), damage=0, hit_probability=0,
            ap=0, save=stats.save,
            points_listed=points, enabled=False,
            skip_reason="no ranged weapons resolvable in tree",
        )

    best = max(gear.ranged_weapons, key=lambda w: w.expected_damage_through_baseline())
    min_m, max_m = extract_squad_size(entry)
    invuln = extract_invuln(entry, reg)
    unit_kw = extract_unit_keywords(entry)
    fnp = extract_fnp(entry, reg)

    return MappedUnit(
        key=key,
        name=name,
        codex=codex,
        health=float(stats.wounds),
        damage=round(best.attacks * best.damage, 2),
        hit_probability=round(best.hit_prob, 3),
        ap=best.ap,
        save=stats.save,
        points_listed=points,
        min_models=min_m,
        max_models=max_m,
        strength=best.strength,
        toughness=stats.toughness or 4,
        leadership=stats.leadership or 7,
        oc=stats.oc or 1,
        attacks=max(1, int(round(best.attacks))),
        weapon_damage_per_shot=round(best.damage, 2),
        lethal_hits=best.lethal_hits,
        sustained_hits=best.sustained_hits,
        twin_linked=best.twin_linked,
        devastating_wounds=best.devastating_wounds,
        invuln_save=invuln,
        rapid_fire=best.rapid_fire,
        melta=best.melta,
        ignores_cover=best.ignores_cover,
        anti_keywords=dict(best.anti_keywords),
        heavy=best.heavy,
        assault=best.assault,
        torrent=best.torrent,
        hazardous=best.hazardous,
        blast=best.blast,
        fnp=fnp,
        unit_keywords=list(unit_kw),
        loadout=[best.name]
        + [w.name for w in gear.ranged_weapons if w.name != best.name][:4],
        notes=f"LD={stats.leadership} OC={stats.oc}",
    )


# ---------------------------------------------------------------------------
# Unit keywords + FNP extractors
# ---------------------------------------------------------------------------

# Standard 10e unit keywords we care about for Anti-X targeting and rules.
_TRACKED_UNIT_KEYWORDS = {
    "INFANTRY", "VEHICLE", "MONSTER", "CHARACTER", "FLY",
    "TITANIC", "TOWERING", "WALKER", "BATTLELINE", "SWARM",
    "BIKE", "MOUNTED", "BEAST", "DAEMON", "PSYKER",
}


def extract_unit_keywords(entry: ET.Element) -> List[str]:
    """Scan the unit's categoryLinks for known 10e keyword tags."""
    found: List[str] = []
    for cl in entry.findall(".//categoryLink"):
        name = (cl.get("name") or "").upper().strip()
        # Strip BSData prefixes like "Faction: " or "Allegiance: "
        if ":" in name:
            name = name.split(":", 1)[1].strip()
        if name in _TRACKED_UNIT_KEYWORDS:
            if name not in found:
                found.append(name)
    return found


_FNP_RE = re.compile(r"Feel\s+No\s+Pain\s*\(?\s*(\d)\s*\+", re.IGNORECASE)


def extract_fnp(entry: ET.Element, reg: Registry) -> int:
    """
    Walk the unit's profiles + linked rules for prose "Feel No Pain N+" mentions.
    Returns the lowest N (best for the unit), or 7 if none.
    """
    best = 7
    seen: set = set()
    def walk(elem: ET.Element, depth: int):
        nonlocal best
        if depth > 3:
            return
        eid = elem.get("id")
        if eid:
            if eid in seen:
                return
            seen.add(eid)
        # Scan all characteristic text values for the phrase
        for c in elem.iter("characteristic"):
            txt = (c.text or "")
            m = _FNP_RE.search(txt)
            if m:
                v = int(m.group(1))
                if v < best:
                    best = v
        for il in elem.findall(".//infoLink"):
            tgt = reg.resolve(il.get("targetId") or "")
            if tgt is not None:
                walk(tgt, depth + 1)
        for el in elem.findall("./entryLinks/entryLink"):
            tgt = reg.resolve(el.get("targetId") or "")
            if tgt is not None:
                walk(tgt, depth + 1)
    walk(entry, 0)
    return best


_INVULN_RE = re.compile(r"Invulnerable\s+Save\s*\(?\s*(\d)\s*\+", re.IGNORECASE)


def extract_invuln(entry: ET.Element, reg: Registry) -> int:
    """
    Find the best invulnerable save on a unit by scanning infoLinks to profiles
    named "Invulnerable Save (X+*)". Returns 7 if none.
    """
    best = 7
    seen: set = set()
    def walk(elem: ET.Element, depth: int):
        nonlocal best
        if depth > 3:
            return
        eid = elem.get("id")
        if eid:
            if eid in seen:
                return
            seen.add(eid)
        for il in elem.findall(".//infoLink"):
            name = il.get("name") or ""
            m = _INVULN_RE.search(name)
            if m:
                v = int(m.group(1))
                if v < best:
                    best = v
        for el in elem.findall("./entryLinks/entryLink"):
            target = reg.resolve(el.get("targetId") or "")
            if target is not None:
                walk(target, depth + 1)
    walk(entry, 0)
    return best


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

    for u in enabled[:8]:
        print(
            f"  {u.codex[:24]:24}  {u.name[:30]:30}  "
            f"H={u.health:>4.0f} D={u.damage:>5.1f} Hit={u.hit_probability:>5.2f} "
            f"AP={u.ap:>2} Sv={u.save}+  pts={u.points_listed:>4.0f}  best={u.loadout[0] if u.loadout else '-'}"
        )
    if skipped:
        print(f"\n  skipped reasons:")
        from collections import Counter
        for reason, n in Counter(u.skip_reason for u in skipped).most_common():
            print(f"    {n:4}  {reason}")


if __name__ == "__main__":
    main()
