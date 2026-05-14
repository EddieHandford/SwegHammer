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
    Parse a "N+" target characteristic to the d6 target value. Some BSData
    authors omit the '+' (e.g. SV="5" for a 5+ save) — accept those too.

        "3+"   -> 3
        "5"    -> 5  (Jackal Alphus etc.)
        ""     -> None
    """
    if not text:
        return None
    t = text.strip()
    m = _PLUS_RE.search(t)
    if m:
        return int(m.group(1))
    # Fallback: bare single-digit integer in range [1, 7]
    bare = _INT_RE.search(t)
    if bare:
        v = int(bare.group(0))
        if 1 <= v <= 7:
            return v
    return None


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
    # Phase F — niche 10e keywords
    lance: bool = False          # +1 to wound if attacking unit charged this turn (melee)
    precision: bool = False      # bypass cover bonus when target has CHARACTER keyword
    pistol: bool = False         # may shoot while in engagement range
    indirect_fire: bool = False  # ignores LoS but -1 to hit vs non-visible targets
    one_shot: bool = False       # once per battle
    # Phase H — Stealth (parsed but stored on UnitProfile, not weapon)
    stealth: bool = False

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
# BSData seldom tags flamer-style weapons with a literal "Torrent" keyword
# token — the rule is implied by the weapon's name. We fall back to a
# substring sweep of the weapon name (case-insensitive) for the canonical
# flamer-family weapon nouns.
_TORRENT_NAME_TOKENS = (
    "flamer",
    "burna",
    "incinerator",
    "flamestorm",
    "inferno cannon",
    "heavy flamer",
)


def _torrent_from_name(name: str) -> bool:
    """True if the weapon's display name implies the Torrent keyword.

    Used as a fallback after the regex sweep of the Keywords characteristic,
    because BSData does not tag flamer-family weapons with "Torrent"
    explicitly — the rule is implied by the weapon noun (Flamer, Burna,
    Heavy Flamer, Inferno Cannon, etc.).
    """
    if not name:
        return False
    lowered = name.lower()
    return any(tok in lowered for tok in _TORRENT_NAME_TOKENS)
_HAZARDOUS_RE = re.compile(r"\bHazardous\b", re.IGNORECASE)
_BLAST_RE = re.compile(r"\bBlast\b", re.IGNORECASE)
# Phase F — five niche keywords. All five appear as standalone tokens in the
# Keywords characteristic (comma-separated). "Indirect Fire" and "One Shot"
# are multi-word; the latter is sometimes hyphenated (One-Shot).
_LANCE_RE = re.compile(r"\bLance\b", re.IGNORECASE)
_PRECISION_RE = re.compile(r"\bPrecision\b", re.IGNORECASE)
_PISTOL_RE = re.compile(r"\bPistol\b", re.IGNORECASE)
_INDIRECT_FIRE_RE = re.compile(r"\bIndirect\s+Fire\b", re.IGNORECASE)
_ONE_SHOT_RE = re.compile(r"\bOne[\s-]Shot\b", re.IGNORECASE)
# Phase H — Stealth keyword (-1 to be hit). Lives at unit level not weapon
# but we sweep the same blob for completeness.
_STEALTH_RE = re.compile(r"\bStealth\b", re.IGNORECASE)


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
    if _LANCE_RE.search(s):
        out["lance"] = True
    if _PRECISION_RE.search(s):
        out["precision"] = True
    if _PISTOL_RE.search(s):
        out["pistol"] = True
    if _INDIRECT_FIRE_RE.search(s):
        out["indirect_fire"] = True
    if _ONE_SHOT_RE.search(s):
        out["one_shot"] = True
    if _STEALTH_RE.search(s):
        out["stealth"] = True
    return out


def extract_melee_weapon(profile: ET.Element) -> Optional[WeaponStats]:
    """Same shape as extract_ranged_weapon but for typeName='Melee Weapons'.

    Uses WS instead of BS. Sets range_inches=1 (engagement)."""
    type_name = profile.get("typeName") or ""
    if "Melee" not in type_name:
        return None
    chars = profile_characteristics(profile)
    a = parse_dice_expr(chars.get("A", ""))
    d = parse_dice_expr(chars.get("D", ""))
    ws = parse_plus_target(chars.get("WS", ""))
    if a is None or d is None or ws is None:
        return None
    keywords = chars.get("Keywords", "")
    abilities = parse_weapon_keywords(keywords)
    s_text = chars.get("S", "")
    s_int = _to_int(s_text) if s_text else None
    return WeaponStats(
        name=profile.get("name") or "?",
        attacks=a,
        hit_prob=target_to_hit_probability(ws),
        damage=d,
        ap=parse_ap(chars.get("AP", "")),
        strength=s_int if s_int is not None else 4,
        range="melee",
        keywords=keywords,
        **abilities,
    )


def extract_ranged_weapon(profile: ET.Element) -> Optional[WeaponStats]:
    type_name = profile.get("typeName") or ""
    if "Ranged" not in type_name:
        return None
    chars = profile_characteristics(profile)
    a = parse_dice_expr(chars.get("A", ""))
    d = parse_dice_expr(chars.get("D", ""))
    bs = parse_plus_target(chars.get("BS", ""))
    if a is None or d is None:
        return None
    keywords = chars.get("Keywords", "")
    abilities = parse_weapon_keywords(keywords)
    # Strength can be a number or "User" (melee) — fall back to 4 if non-numeric.
    s_text = chars.get("S", "")
    s_int = _to_int(s_text) if s_text else None
    weapon_name = profile.get("name") or "?"
    # BSData usually omits the Torrent keyword on flamer-family weapons —
    # detect it from the weapon name as a fallback.
    if not abilities.get("torrent") and _torrent_from_name(weapon_name):
        abilities["torrent"] = True
    # Torrent weapons auto-hit and so list BS="N/A" in BSData. Treat that as
    # hit_prob=1.0 instead of dropping the weapon (the historical behaviour,
    # which excluded most flamer-family weapons from the mapping altogether).
    if bs is None:
        if abilities.get("torrent"):
            hit_prob = 1.0
        else:
            return None
    else:
        hit_prob = target_to_hit_probability(bs)
    return WeaponStats(
        name=weapon_name,
        attacks=a,
        hit_prob=hit_prob,
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
    melee_weapons: List[WeaponStats] = field(default_factory=list)


def _walk(
    elem: ET.Element, reg: Registry, seen: set, out: UnitWargear,
    depth: int = 0, max_depth: int = 3, primary_name: str = "",
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
        _consume_profile(prof, out, primary_name)

    # infoLinks → profiles
    for il in elem.findall("./infoLinks/infoLink"):
        if il.get("type") != "profile":
            continue
        target = reg.resolve(il.get("targetId") or "")
        if target is not None and target.tag == "profile":
            _consume_profile(target, out, primary_name)

    # entryLinks — carry their own infoLinks, then recurse into the target
    for el in elem.findall("./entryLinks/entryLink"):
        for il in el.findall("./infoLinks/infoLink"):
            if il.get("type") != "profile":
                continue
            tgt = reg.resolve(il.get("targetId") or "")
            if tgt is not None and tgt.tag == "profile":
                _consume_profile(tgt, out, primary_name)
        target = reg.resolve(el.get("targetId") or "")
        if target is not None:
            _walk(target, reg, seen, out, depth + 1, max_depth, primary_name)

    # Nested selectionEntries / groups
    for child in elem.findall("./selectionEntries/selectionEntry"):
        _walk(child, reg, seen, out, depth + 1, max_depth, primary_name)
    for grp in elem.findall("./selectionEntryGroups/selectionEntryGroup"):
        _walk(grp, reg, seen, out, depth + 1, max_depth, primary_name)


def _consume_profile(prof: ET.Element, out: UnitWargear, primary_name: str = "") -> None:
    """Collect a profile into the wargear bag.

    Multi-profile units (Saint Celestine + Geminae Superia, Chaplain Grimaldus
    + Cenobyte Servitors) put more than one Unit profile in the tree. We pick
    the one whose name MATCHES the unit's display name when available, so the
    "lead" character wins over their retinue.
    """
    type_name = prof.get("typeName") or ""
    if is_unit_profile(prof):
        prof_name = prof.get("name") or ""
        if out.unit_profile is None:
            out.unit_profile = prof
        elif primary_name and prof_name == primary_name:
            # Name match — prefer over previously-stored profile
            out.unit_profile = prof
        return
    if "Ranged" in type_name:
        w = extract_ranged_weapon(prof)
        if w is not None:
            out.ranged_weapons.append(w)
    elif "Melee" in type_name:
        w = extract_melee_weapon(prof)
        if w is not None:
            out.melee_weapons.append(w)


def gather_wargear(entry: ET.Element, reg: Registry) -> UnitWargear:
    out = UnitWargear()
    primary_name = entry.get("name") or ""
    _walk(entry, reg, set(), out, primary_name=primary_name)
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
    # Phase F — niche 10e keywords on the chosen primary weapon
    lance: bool = False
    precision: bool = False
    pistol: bool = False
    indirect_fire: bool = False
    one_shot: bool = False
    # Phase H — Stealth (-1 to be hit when this unit is shot at)
    stealth: bool = False
    # Unit-level
    fnp: int = 7                                  # 7 = no Feel No Pain
    unit_keywords: List[str] = field(default_factory=list)
    # Phase B — melee profile (best-legal melee weapon picked the same way)
    melee_attacks: int = 0
    melee_damage_per_shot: float = 0.0
    melee_hit_probability: float = 0.0
    melee_strength: int = 4
    melee_ap: int = 0
    melee_weapon: str = ""
    range_inches: int = 24       # primary-weapon range; melee-only => 1
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

    # Melee fallback — a unit with no ranged weapon is still useful if it
    # has a melee profile. Such units become engagement-only (range_inches=1).
    has_ranged = bool(gear.ranged_weapons)
    has_melee = bool(gear.melee_weapons)
    if not has_ranged and not has_melee:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=float(stats.wounds), damage=0, hit_probability=0,
            ap=0, save=stats.save,
            points_listed=points, enabled=False,
            skip_reason="no ranged OR melee weapons resolvable in tree",
        )

    # Best ranged weapon (may be None for melee-only units)
    best = (
        max(gear.ranged_weapons, key=lambda w: w.expected_damage_through_baseline())
        if has_ranged else None
    )
    best_melee = (
        max(gear.melee_weapons, key=lambda w: w.expected_damage_through_baseline())
        if has_melee else None
    )
    min_m, max_m = extract_squad_size(entry)
    invuln = extract_invuln(entry, reg)
    unit_kw = extract_unit_keywords(entry)
    fnp = extract_fnp(entry, reg)
    stealth = extract_stealth(entry, reg)

    # If melee-only (no ranged), use the melee weapon as the primary stat line
    primary = best if best is not None else best_melee
    # Derive range_inches: melee-only units get 1" engagement; else parse the
    # ranged weapon's Range characteristic ("24"" -> 24), default 24 on failure.
    if not has_ranged:
        primary_range = 1
    else:
        m = re.search(r"(\d+)", best.range or "")
        primary_range = int(m.group(1)) if m else 24
    return MappedUnit(
        key=key,
        name=name,
        codex=codex,
        health=float(stats.wounds),
        damage=round(primary.attacks * primary.damage, 2),
        hit_probability=round(primary.hit_prob, 3),
        ap=primary.ap,
        save=stats.save,
        points_listed=points,
        min_models=min_m,
        max_models=max_m,
        strength=primary.strength,
        toughness=stats.toughness or 4,
        leadership=stats.leadership or 7,
        oc=stats.oc or 1,
        attacks=max(1, int(round(primary.attacks))),
        weapon_damage_per_shot=round(primary.damage, 2),
        lethal_hits=primary.lethal_hits,
        sustained_hits=primary.sustained_hits,
        twin_linked=primary.twin_linked,
        devastating_wounds=primary.devastating_wounds,
        invuln_save=invuln,
        rapid_fire=primary.rapid_fire,
        melta=primary.melta,
        ignores_cover=primary.ignores_cover,
        anti_keywords=dict(primary.anti_keywords),
        heavy=primary.heavy,
        assault=primary.assault,
        torrent=primary.torrent,
        hazardous=primary.hazardous,
        blast=primary.blast,
        # Lance is a melee-only keyword (Wahapedia 10e core). Source from the
        # best melee weapon if there is one; otherwise fall back to primary
        # (covers melee-only units where primary == best_melee).
        lance=(best_melee.lance if best_melee is not None else primary.lance),
        # Precision can appear on either melee or ranged. Take it if EITHER
        # the primary (ranged) or the chosen melee weapon has it.
        precision=primary.precision or (best_melee.precision if best_melee else False),
        pistol=primary.pistol,
        indirect_fire=primary.indirect_fire,
        one_shot=primary.one_shot,
        stealth=stealth or primary.stealth,
        fnp=fnp,
        unit_keywords=list(unit_kw),
        melee_attacks=max(0, int(round(best_melee.attacks))) if best_melee else 0,
        melee_damage_per_shot=round(best_melee.damage, 2) if best_melee else 0.0,
        melee_hit_probability=round(best_melee.hit_prob, 3) if best_melee else 0.0,
        melee_strength=best_melee.strength if best_melee else 4,
        melee_ap=best_melee.ap if best_melee else 0,
        melee_weapon=best_melee.name if best_melee else "",
        range_inches=primary_range,
        loadout=[primary.name]
        + [w.name for w in (gear.ranged_weapons + gear.melee_weapons) if w.name != primary.name][:4],
        notes=f"LD={stats.leadership} OC={stats.oc} melee={'yes' if has_melee else 'no'} ranged={'yes' if has_ranged else 'no'}",
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
# Unit-level "Stealth" ability: matches Stealth as a bare word (not "Stealthy"
# adjectives). Used by extract_stealth to detect the defensive ability that
# imposes -1 to hit when this unit is shot at.
_STEALTH_ABILITY_RE = re.compile(r"(?:^|[\s,;.])Stealth(?:$|[\s,;.\)])")


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


def extract_stealth(entry: ET.Element, reg: Registry) -> bool:
    """True iff the unit has the Stealth datasheet ability (-1 to be hit
    by ranged attacks).

    In BSData 10e Stealth is published as a shared rule (`type="rule"`
    infoLink) attached to the unit entry, with `name="Stealth"`. A handful
    of units also inline a profile named exactly "Stealth". We only match
    those two shapes — never free-form prose that merely mentions the word
    (descriptions like "models in that unit have the Stealth ability").
    """
    # Direct infoLinks on this entry — the common case (Eliminators,
    # Infiltrators, Incursors, Reivers, Phobos characters, etc.).
    for il in entry.findall(".//infoLink"):
        if (il.get("name") or "").strip().lower() == "stealth":
            return True
    # Inline profile named "Stealth" — rare but seen in some xenos units.
    for prof in entry.findall(".//profile"):
        if (prof.get("name") or "").strip().lower() == "stealth":
            return True
    return False


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
