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


def weighted_basket_average(basket: "List[tuple[float, WeaponStats]]") -> Optional["WeaponStats"]:
    """
    Collapse a `[(weight, WeaponStats)] ` basket into a single synthetic
    WeaponStats by taking the WEIGHTED average of (attacks, damage, ap,
    hit_prob, strength) and the UNION / MAX of keyword effects.

    Rationale (matches the task brief):
      - Per-model stats (attacks/damage/AP/hit_prob/strength) are averaged so
        a 10-model Devastator Squad with 4 multi-meltas and 5 boltguns + 1
        sergeant ends up between bolter-only and multi-melta-only damage.
      - Keyword effects (rapid_fire, melta, anti_*, lethal_hits, etc.) take
        the maximum / union, on the assumption that in real combat the squad
        allocates the right weapon to the right target. We scale BACK the
        attack count via the weighting, so the union of keywords does NOT
        recover the cheese we removed.

    Returns None for an empty basket.
    """
    if not basket:
        return None
    total = sum(w for w, _ in basket if w > 0)
    if total <= 0:
        return None
    # Weighted scalar averages
    avg_attacks = sum(w * x.attacks for w, x in basket) / total
    avg_damage = sum(w * x.damage for w, x in basket) / total
    avg_hit = sum(w * x.hit_prob for w, x in basket) / total
    avg_ap = sum(w * x.ap for w, x in basket) / total
    avg_strength = sum(w * x.strength for w, x in basket) / total
    # Pick a representative name + range. Name = highest-weighted weapon.
    representative = max(basket, key=lambda b: b[0])[1]
    # Union/MAX keyword effects across the basket. The "max" idea lets a
    # squad with 1 melta inherit the Melta keyword at scaled-down attacks.
    union: Dict[str, object] = {
        "lethal_hits": any(x.lethal_hits for _, x in basket),
        "sustained_hits": max((x.sustained_hits for _, x in basket), default=0),
        "twin_linked": any(x.twin_linked for _, x in basket),
        "devastating_wounds": any(x.devastating_wounds for _, x in basket),
        "rapid_fire": max((x.rapid_fire for _, x in basket), default=0),
        "melta": max((x.melta for _, x in basket), default=0),
        "ignores_cover": any(x.ignores_cover for _, x in basket),
        "heavy": any(x.heavy for _, x in basket),
        "assault": any(x.assault for _, x in basket),
        # Torrent requires ALL variants to be Torrent — otherwise a mixed
        # basket (e.g. Aggressor Auto Boltstorm Gauntlets + Flamestorm Gauntlets)
        # would falsely inherit auto-hit from the Torrent variant while keeping
        # the numeric BS averaged in. See Wahapedia Aggressor Squad:
        # https://wahapedia.ru/wh40k10ed/factions/space-marines/#Aggressor-Squad
        "torrent": bool(basket) and all(x.torrent for _, x in basket),
        "hazardous": any(x.hazardous for _, x in basket),
        "blast": any(x.blast for _, x in basket),
        "lance": any(x.lance for _, x in basket),
        "precision": any(x.precision for _, x in basket),
        "pistol": any(x.pistol for _, x in basket),
        "indirect_fire": any(x.indirect_fire for _, x in basket),
        "one_shot": any(x.one_shot for _, x in basket),
        "stealth": any(x.stealth for _, x in basket),
    }
    # Anti-X — take the best (lowest threshold) across the basket per keyword
    anti: Dict[str, int] = {}
    for _, x in basket:
        for kw, n in (x.anti_keywords or {}).items():
            if kw not in anti or n < anti[kw]:
                anti[kw] = n
    return WeaponStats(
        name=representative.name,
        attacks=avg_attacks,
        hit_prob=avg_hit,
        damage=avg_damage,
        ap=int(round(avg_ap)),
        strength=int(round(avg_strength)) if avg_strength > 0 else representative.strength,
        range=representative.range,
        keywords=representative.keywords,
        anti_keywords=anti,
        **union,  # type: ignore[arg-type]
    )


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
    depth: int = 0, max_depth: int = 5, primary_name: str = "",
) -> None:
    """Collect the unit profile + every ranged weapon reachable within depth.

    ``max_depth`` was historically 3, which sufficed for Marine-shape squads
    (unit → group → model → weapon entryLink). Astra Militarum (and any
    codex that wraps its squad's models inside an intermediate
    ``selectionEntry type="upgrade"`` "Unit Composition" choice — Cadian
    Shock Troops, Catachan Jungle Fighters, Death Korps of Krieg) nests
    weapons two extra layers deeper:

        unit
        └─ selectionEntryGroup "Unit Composition"
            └─ selectionEntry type="upgrade"  (e.g. "1 Sergeant + 9 Troopers")
                └─ selectionEntryGroup "9 Troopers"  (Krieg) — OR direct
                    └─ selectionEntry type="model"
                        └─ entryLink → weapon

    Depth 5 covers both AM shapes (Cadian-style direct entryLinks at depth 4
    and Krieg-style nested group at depth 5) while the ``seen`` set still
    prevents weapon-tree cycles. Bumping the depth does NOT pull in extra
    "wrong" weapons: each unique element id is visited at most once.
    """
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


def _squad_group_size(grp: ET.Element) -> Optional[tuple[int, int]]:
    """Return (min, max) selections for a selectionEntryGroup, or None.

    BSData 10e expresses squad size in three different shapes:
      (a) Direct ``field="selections"`` min/max constraints on the group
          (Marine-style: Tactical Squad, Intercessor Squad).
      (b) Constraints only on the group's max, with min implicit at 1
          (Aeldari-style: Guardian Defenders).
      (c) No constraints on the group at all — the squad size lives on
          each model's own ``selections`` min/max constraints (Necron
          Tomb Blades, Drukhari Reaver Jetbikes). Sum the per-model
          mins and maxes.

    ``value="-1"`` is the BSData "unlimited" sentinel; ignore it so a
    real finite cap can win the min().

    When called on the outer unit ``selectionEntry`` (implicit-group
    shape, no wrapping ``selectionEntryGroup``), the entry's OWN
    constraints are army-list limits — ``scope="force"`` / ``"roster"``
    cap units per army, and ``scope="parent"`` on a unit entry refers
    to the unit's parent (the codex/category), not the squad. None of
    them encode squad model count. Pre-2026-05-16, reading those as
    squad size made Pink Horrors / Plaguebearers / Bloodletters /
    Sagittarum Custodians / Chaos Spawn / etc. report min_models=1, so
    per-model points cost collapsed to the full squad cost (Pink
    Horrors: 140 pts/model instead of 14). For unit entries we skip
    shape (a/b) entirely and use shape (c), where the inner model's
    own ``scope="parent"`` constraints encode the real squad size.
    """
    is_unit_entry = grp.tag == "selectionEntry" and grp.get("type") == "unit"
    mn: Optional[int] = None
    mx: Optional[int] = None
    if not is_unit_entry:
        for cons in grp.findall("./constraints/constraint"):
            if cons.get("field") != "selections":
                continue
            if cons.get("scope") in ("force", "roster"):
                continue
            try:
                value = int(cons.get("value") or 0)
            except ValueError:
                continue
            if cons.get("type") == "min":
                mn = value
            elif cons.get("type") == "max":
                if value < 0:
                    continue
                mx = value if mx is None else min(mx, value)
    if mn is None and mx is not None and mx >= 1:
        mn = 1
    if mn is not None and mx is not None and mx >= mn >= 1:
        return mn, mx
    # Shape (c): sum per-model selection constraints.
    model_mn = 0
    model_mx = 0
    found_any = False
    for me in grp.findall("./selectionEntries/selectionEntry"):
        if me.get("type") != "model":
            continue
        m_mn: Optional[int] = None
        m_mx: Optional[int] = None
        for cons in me.findall("./constraints/constraint"):
            if cons.get("field") != "selections":
                continue
            try:
                value = int(cons.get("value") or 0)
            except ValueError:
                continue
            if cons.get("type") == "min":
                m_mn = value
            elif cons.get("type") == "max":
                if value < 0:
                    continue
                m_mx = value if m_mx is None else min(m_mx, value)
        if m_mx is not None and m_mx >= 1:
            found_any = True
            model_mn += m_mn or 0
            model_mx += m_mx
    if found_any and model_mx >= max(1, model_mn):
        return max(1, model_mn), model_mx
    return None


def _implicit_squad_size_from_cost_tier(entry: ET.Element) -> Optional[int]:
    """Recover squad size from a points-tier modifier on the unit entry.

    Some 10e squads (Neurogaunts, Jakhals, and others where the unit can only
    be fielded at a fixed model count) carry NO `selectionEntryGroup` with a
    `selections` constraint AND no `selectionEntry type='model'` children. The
    squad size is implicit; BSData expresses it indirectly through a cost-tier
    modifier of the shape:

        <modifier type="set" field="<pts-typeId>" value="<higher cost>">
          <conditions>
            <condition type="greaterThan" field="selections"
                       childId="model" value="N"/>
          </conditions>
        </modifier>

    "When the unit has more than N models, the cost jumps." The threshold N is
    therefore the upper bound of the base cost tier — i.e. the squad size at
    base cost. For Neurogaunts that's 11 (so 45 pts / 11 models = 4.09 / model
    rather than the 45 / model the (1, 1) fallback produced). For Jakhals
    N=10 (65 / 10 = 6.5 / model).

    Returns the threshold N, or None when no qualifying modifier is present.
    """
    candidates: List[int] = []
    for mod in entry.findall("./modifiers/modifier"):
        if mod.get("type") != "set":
            continue
        # The modifier's `field` is the points typeId; we don't pin a literal
        # value because BSData has occasionally renumbered typeIds. Instead we
        # cross-check that this entry actually has a <cost name="pts"> with
        # the same typeId.
        mod_field = mod.get("field")
        if not mod_field:
            continue
        if not any(
            c.get("typeId") == mod_field and (c.get("name") or "").lower() == "pts"
            for c in entry.findall("./costs/cost")
        ):
            continue
        for cond in mod.findall("./conditions/condition"):
            if cond.get("type") != "greaterThan":
                continue
            if cond.get("field") != "selections":
                continue
            if cond.get("childId") != "model":
                continue
            try:
                n = int(cond.get("value") or 0)
            except ValueError:
                continue
            if n >= 1:
                candidates.append(n)
    if not candidates:
        return None
    # Pick the smallest threshold — for multi-tier costs (rare but possible),
    # the lowest tier-up threshold is the base squad's upper bound.
    return min(candidates)


def extract_squad_size(entry: ET.Element) -> tuple[int, int]:
    """
    Return (min_models, max_models) for a unit selectionEntry.

    10e squads encode size in four shapes that the mapper now reads in a
    single pass and combines:

      (a) inner ``selectionEntryGroup``s with `selections` constraints,
          one group per kind-of-model. Devastator Squad has two: the main
          "Devastators" group (4, 9) and the "Devastator Sergeant" group
          (1, 1); the squad size is the SUM of those (5, 10). The previous
          implementation returned the first non-None group, silently
          truncating leader-plus-body squads by one model — Devastators
          read as 30 pts/model instead of 24, etc. The fix is to sum.
      (b) direct ``selectionEntry type='model'`` children on the entry
          itself when no outer groups carry the size (Aeldari-shape).
      (c) the inner per-model constraints summed (Tomb Blades etc.),
          handled inside `_squad_group_size`.
      (d) implicit-only: no constraint encodes the squad count, but a
          points-tier modifier of the shape "when selections > N, set
          cost = higher" reveals N as the upper bound of the base cost
          tier. Jakhals (N=10) and Neurogaunts (N=11) are the canonical
          cases. See `_implicit_squad_size_from_cost_tier`. When the
          static signal sums to less than N (Jakhals: two loadout-choice
          groups summing to (2, 2)), the cost-tier value wins.

    Single-model units (characters, vehicles, monsters) have none of those
    shapes and default to (1, 1).
    """
    sum_min, sum_max, found = 0, 0, False
    for grp in entry.findall("./selectionEntryGroups/selectionEntryGroup"):
        size = _squad_group_size(grp)
        if size is not None:
            sum_min += size[0]
            sum_max += size[1]
            found = True
    # Shape (b): direct ``selectionEntry type='model'`` children on the unit
    # entry itself. Two patterns hit this branch:
    #   - Aeldari Guardian Defenders / Plaguebearers shape: no outer groups,
    #     all models are direct children.
    #   - Mixed shape (T'au Breacher Team, Servitor Battleclade): one or
    #     more outer groups carry the sergeant / officer with (1, 1), AND
    #     direct model entries carry the body of the squad. The previous
    #     ``if not found`` gate skipped this whole branch the moment any
    #     outer group fired, dropping the body count and collapsing the
    #     unit to its 1-model leader. Summing both branches together
    #     captures the full squad.
    if entry.find("./selectionEntries/selectionEntry[@type='model']") is not None:
        size = _squad_group_size(entry)
        if size is not None:
            sum_min += size[0]
            sum_max += size[1]
            found = True
    # Shape (d): cost-tier modifier reveals the implicit squad size. When
    # the static signal under-reports (loadout-choice groups misread as
    # model counts), the tier value supplies the floor for both min and
    # max — `max(sum, n)` prefers the larger of the two on each side, so
    # squads where the static signal is correct (Devastators: (5, 10))
    # are unaffected.
    n = _implicit_squad_size_from_cost_tier(entry)
    if n is not None:
        sum_min = max(sum_min, n)
        sum_max = max(sum_max, n)
        found = True
    if found and sum_max >= max(1, sum_min):
        return max(1, sum_min), sum_max
    return 1, 1


def _find_main_squad_group(entry: ET.Element) -> Optional[ET.Element]:
    """Return the element that wraps the squad's per-model selectionEntries.

    Two schema shapes appear in BSData 10e:
      (1) An inner ``selectionEntryGroup`` holds the squad's models and
          carries the min/max constraint (Space Marines, most Tac-ish
          squads).
      (2) The squad entry itself directly contains
          ``selectionEntry type='model'`` children, with the size
          constraint on the *entry* (Guardian Defenders, Kabalite Warriors,
          and other Aeldari-derived squads).

    Without the second branch those squads silently bypass the
    heterogeneous path and rerun the legacy "best single weapon for all
    models" code — exactly the cheese this work was meant to remove.
    """
    for grp in entry.findall("./selectionEntryGroups/selectionEntryGroup"):
        if _squad_group_size(grp) is not None:
            return grp
    # Shape (2): the entry itself is the implicit group.
    if entry.find("./selectionEntries/selectionEntry[@type='model']") is not None:
        if _squad_group_size(entry) is not None:
            return entry
    return None


# ---------------------------------------------------------------------------
# Squad-level loadout heterogeneity (issue #76)
# ---------------------------------------------------------------------------
#
# Real WH40k 10e squads are NOT 10 copies of the best weapon. A Devastator
# Squad is 1 sergeant + N base models + a small handful of heavy weapons;
# a Tactical Squad is 1 sergeant + 8 boltguns + 1 special weapon. The old
# `map_unit` picked the single best weapon in the unit's wargear tree and
# pretended every model carried it — turning Devastators into a 10-multi-
# melta blender.
#
# The mapper now walks the *inner* squad selectionEntryGroup and reads each
# `<selectionEntry type="model">` block individually. Each model carries:
#   - Its own min/max count constraints (how many of this model are taken).
#   - A list of fixed weapon entryLinks (Boltgun, Bolt Pistol, Close Combat).
#   - 0+ inner Weapon Option selectionEntryGroups whose entryLinks list the
#     *alternatives* one model picks from (e.g. Multi-melta XOR Heavy Bolter
#     XOR Lascannon …). We pick the best by expected-damage and treat that
#     as the canonical choice for that model.
#
# The output is a per-model count × per-model weapons list, which the
# weighted-basket averager collapses into a single synthetic WeaponStats.


@dataclass
class ModelLoadout:
    """A single model type within a squad: how many of them and what they carry."""
    name: str
    count: float                              # typical headcount in the squad
    ranged: List[WeaponStats] = field(default_factory=list)
    melee: List[WeaponStats] = field(default_factory=list)


def _resolve_weapon_target(target_id: str, reg: Registry) -> tuple[Optional[WeaponStats], Optional[WeaponStats]]:
    """
    Resolve a weapon-shaped selectionEntry to (ranged, melee) WeaponStats.
    A weapon entry typically holds two profiles — the Ranged profile and the
    Melee profile (pistols + chainswords) — or just one. We return both
    independently so the caller can categorise them. Returns (None, None) if
    the target isn't a weapon-shaped selectionEntry.
    """
    target = reg.resolve(target_id)
    if target is None:
        return None, None
    ranged: Optional[WeaponStats] = None
    melee: Optional[WeaponStats] = None
    # Inline profiles
    for prof in target.findall(".//profile"):
        tn = prof.get("typeName") or ""
        if "Ranged" in tn and ranged is None:
            ranged = extract_ranged_weapon(prof)
        elif "Melee" in tn and melee is None:
            melee = extract_melee_weapon(prof)
    # Some weapons are themselves infoLink-referenced; follow one level.
    if ranged is None and melee is None:
        for il in target.findall(".//infoLinks/infoLink"):
            tgt = reg.resolve(il.get("targetId") or "")
            if tgt is None or tgt.tag != "profile":
                continue
            tn = tgt.get("typeName") or ""
            if "Ranged" in tn and ranged is None:
                ranged = extract_ranged_weapon(tgt)
            elif "Melee" in tn and melee is None:
                melee = extract_melee_weapon(tgt)
    return ranged, melee


def _model_count_estimate(model_entry: ET.Element, squad_min: int, squad_max: int) -> float:
    """
    How many of this model type are typically in a squad?

    Heuristic: take the midpoint of the model's own (min, max) constraint,
    clamped to the squad's max. Models with min=max take that fixed value
    (e.g. sergeant = 1, "w/ Heavy Weapon" usually max=4). If no min/max is
    present, fall back to "the rest of the squad" = squad_max - already-
    accounted models; the caller does this post-hoc.
    """
    mn: Optional[int] = None
    mx: Optional[int] = None
    for cons in model_entry.findall("./constraints/constraint"):
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
    if mn is None and mx is None:
        return -1.0   # caller treats this as "fill the rest"
    if mn is None:
        mn = 0
    if mx is None:
        mx = squad_max
    mx = min(mx, squad_max)
    # Use the max value as the typical count — players bring the maximum
    # number of heavy/special weapons allowed (that's the "best legal" intent).
    # For the basic model group with max == squad_max, the post-hoc fill
    # below clamps the leftover to the actual squad fill.
    typical = max(mn, mx)
    return float(typical)


def _collect_weapons_for_model(
    model_entry: ET.Element,
    reg: Registry,
) -> tuple[List[WeaponStats], List[WeaponStats]]:
    """
    Collect this single model's ranged + melee weapons.

    Fixed weapons are entryLinks directly under the model with min>=1.
    Weapon options live in inner selectionEntryGroups; for each such group,
    we pick the BEST single weapon by expected-damage and treat it as this
    model's pick.
    """
    ranged_picks: List[WeaponStats] = []
    melee_picks: List[WeaponStats] = []

    # Fixed weapons attached to the model entry. A bare entryLink with no
    # selection constraint at all is treated as a CARRIED weapon — the 10e
    # BSData convention is that optional weapons live inside
    # selectionEntryGroup choice points, so a constraint-less entryLink
    # represents a model's default kit (Shuriken Catapult on a Guardian
    # Defender, Close Combat Weapon on basically every infantry profile).
    for el in model_entry.findall("./entryLinks/entryLink"):
        if el.get("type") != "selectionEntry":
            continue
        has_selection_constraint = False
        min_val = 0
        max_val = 1
        for cons in el.findall("./constraints/constraint"):
            if cons.get("field") != "selections":
                continue
            has_selection_constraint = True
            try:
                value = int(cons.get("value") or 0)
            except ValueError:
                continue
            if cons.get("type") == "min":
                min_val = value
            elif cons.get("type") == "max":
                max_val = value
        if not has_selection_constraint:
            min_val = 1   # absence == carried (see docstring above)
        if min_val < 1:
            # Optional weapon — skip; it's an upgrade, not a default carry.
            continue
        target_id = el.get("targetId") or ""
        r, m = _resolve_weapon_target(target_id, reg)
        if r is not None:
            ranged_picks.append(r)
        if m is not None:
            melee_picks.append(m)

    # Inline child selectionEntries — Hellblasters etc. embed the Plasma
    # Incinerator profile DIRECTLY here (not via an entryLink). Treat them
    # like fixed weapons: if min>=1 or no constraint, count as carried.
    for child in model_entry.findall("./selectionEntries/selectionEntry"):
        min_val = 0
        for cons in child.findall("./constraints/constraint"):
            if cons.get("field") != "selections":
                continue
            if cons.get("type") == "min":
                try:
                    min_val = int(cons.get("value") or 0)
                except ValueError:
                    pass
        if min_val < 1:
            # Optional embed — skip (it's not carried by default).
            continue
        # An inline selectionEntry can carry MULTIPLE Ranged Weapon profiles
        # representing modes (Plasma Incinerator Standard / Supercharge).
        # Pick the best mode rather than averaging — that's the player's
        # in-game choice point.
        ranged_modes: List[WeaponStats] = []
        melee_modes: List[WeaponStats] = []
        for prof in child.findall(".//profile"):
            tn = prof.get("typeName") or ""
            if "Ranged" in tn:
                w = extract_ranged_weapon(prof)
                if w is not None:
                    ranged_modes.append(w)
            elif "Melee" in tn:
                w = extract_melee_weapon(prof)
                if w is not None:
                    melee_modes.append(w)
        if ranged_modes:
            ranged_picks.append(
                max(ranged_modes, key=lambda w: w.expected_damage_through_baseline())
            )
        if melee_modes:
            melee_picks.append(
                max(melee_modes, key=lambda w: w.expected_damage_through_baseline())
            )

    # Weapon-option groups — pick the BEST single alternative within each.
    # A group's choices can live in any of three places:
    #   1. entryLink children (cross-reference into shared weapon catalogue)
    #   2. inline selectionEntry children (the weapon profile is right here)
    #   3. nested selectionEntryGroup children (sub-choice tree)
    # The pre-fix walker only saw (1), which silently dropped any unit whose
    # weapon options live inline (Immortals, Ophydian Destroyers, etc.) or
    # are nested inside a sub-group.
    for grp in model_entry.findall("./selectionEntryGroups/selectionEntryGroup"):
        candidates_ranged, candidates_melee = _gather_group_candidates(grp, reg)
        if candidates_ranged:
            best_r = max(candidates_ranged, key=lambda w: w.expected_damage_through_baseline())
            ranged_picks.append(best_r)
        if candidates_melee:
            best_m = max(candidates_melee, key=lambda w: w.expected_damage_through_baseline())
            melee_picks.append(best_m)

    return ranged_picks, melee_picks


def _weapons_from_inline_entry(
    sel_entry: ET.Element,
) -> tuple[List[WeaponStats], List[WeaponStats]]:
    """Extract ranged + melee weapon stats directly attached as profiles to
    a single inline selectionEntry. Mirrors the inline-weapon path used at
    the model level for fixed weapons like Hellblaster Plasma Incinerators —
    same logic, just factored out so the group walker can call it too.
    """
    ranged: List[WeaponStats] = []
    melee: List[WeaponStats] = []
    for prof in sel_entry.findall(".//profile"):
        tn = prof.get("typeName") or ""
        if "Ranged" in tn:
            w = extract_ranged_weapon(prof)
            if w is not None:
                ranged.append(w)
        elif "Melee" in tn:
            w = extract_melee_weapon(prof)
            if w is not None:
                melee.append(w)
    return ranged, melee


def _gather_group_candidates(
    grp: ET.Element,
    reg: Registry,
) -> tuple[List[WeaponStats], List[WeaponStats]]:
    """Recursively collect every weapon candidate inside a selectionEntryGroup.

    Walks three branches: cross-referenced entryLinks, inline child
    selectionEntries (with their own profile blocks), and nested
    selectionEntryGroups. Each leaf is a possible weapon choice — the
    caller picks one best candidate from the union per group.
    """
    candidates_ranged: List[WeaponStats] = []
    candidates_melee: List[WeaponStats] = []

    # 1. entryLink children — cross-reference into the shared weapon catalogue
    for el in grp.findall("./entryLinks/entryLink"):
        if el.get("type") != "selectionEntry":
            continue
        target_id = el.get("targetId") or ""
        r, m = _resolve_weapon_target(target_id, reg)
        if r is not None:
            candidates_ranged.append(r)
        if m is not None:
            candidates_melee.append(m)

    # 2. inline selectionEntry children — the weapon profile is right here
    for child in grp.findall("./selectionEntries/selectionEntry"):
        r_list, m_list = _weapons_from_inline_entry(child)
        # One inline entry can carry multiple profile modes (Plasma standard /
        # supercharge); the player picks the best, so we treat that as the
        # single candidate this entry contributes.
        if r_list:
            candidates_ranged.append(
                max(r_list, key=lambda w: w.expected_damage_through_baseline())
            )
        if m_list:
            candidates_melee.append(
                max(m_list, key=lambda w: w.expected_damage_through_baseline())
            )

    # 3. nested selectionEntryGroup children — flatten their candidates up
    for sub in grp.findall("./selectionEntryGroups/selectionEntryGroup"):
        r_sub, m_sub = _gather_group_candidates(sub, reg)
        candidates_ranged.extend(r_sub)
        candidates_melee.extend(m_sub)

    return candidates_ranged, candidates_melee


def gather_squad_loadout(entry: ET.Element, reg: Registry) -> Optional[List[ModelLoadout]]:
    """
    Build a per-model loadout list for a multi-model squad.

    Returns None if:
      - the unit has no inner squad SEG (single-model unit), OR
      - no model entries are found, OR
      - no weapons resolve on any model (the caller should fall back).

    The returned list's `count` fields SUM to the squad's max headcount.
    """
    grp = _find_main_squad_group(entry)
    if grp is None:
        return None
    size = _squad_group_size(grp)
    if size is None:
        return None
    _, squad_max = size

    # Crisis Battlesuit-style entries split their models across two
    # locations: a Shas'ui directly under the unit entry and a Shas'vre
    # leader inside a nested ``selectionEntryGroup``. If the picker chose
    # one of those locations we still need to collect the model from the
    # OTHER one — otherwise the basket misses ~half the squad and the
    # legacy single-best-weapon path kicks in, picking the highest-A
    # weapon in the tree (which for many battlesuits is a leader profile
    # with +1 A, leading to the Crisis +1 / Riptide +2 over-counts).
    model_entries = list(grp.findall("./selectionEntries/selectionEntry"))
    seen_names = set()
    for me in model_entries:
        if me.get("type") == "model" and me.get("name"):
            seen_names.add(me.get("name"))
    # Pull additional models from the entry's other location.
    if grp is entry:
        # We're walking the entry-direct slot; pick up nested-group models.
        for sub in entry.findall("./selectionEntryGroups/selectionEntryGroup"):
            for me in sub.findall("./selectionEntries/selectionEntry"):
                if me.get("type") == "model" and me.get("name") not in seen_names:
                    model_entries.append(me)
                    seen_names.add(me.get("name"))
    else:
        # We picked a nested group; pick up the entry-direct models too.
        for me in entry.findall("./selectionEntries/selectionEntry"):
            if me.get("type") == "model" and me.get("name") not in seen_names:
                model_entries.append(me)
                seen_names.add(me.get("name"))
    # Whichever shape: if the entry itself declares a wider size constraint
    # (e.g. 1-3 Shas'ui + 1 Shas'vre = squad max 4), prefer that as the
    # effective squad max — it captures both halves.
    entry_size = _squad_group_size(entry)
    if entry_size is not None and entry_size[1] >= squad_max:
        size = entry_size
        _, squad_max = size
    if squad_max <= 1:
        return None
    models: List[ModelLoadout] = []
    fill_placeholders: List[ModelLoadout] = []
    accounted = 0.0
    for model_entry in model_entries:
        if model_entry.get("type") != "model":
            continue
        name = model_entry.get("name") or "?"
        cnt = _model_count_estimate(model_entry, *size)
        ranged_picks, melee_picks = _collect_weapons_for_model(model_entry, reg)
        ml = ModelLoadout(name=name, count=cnt, ranged=ranged_picks, melee=melee_picks)
        if cnt < 0:
            fill_placeholders.append(ml)
        else:
            models.append(ml)
            accounted += cnt
    # If any model lacked min/max, assign it the leftover ("base" boltgun model).
    if fill_placeholders:
        leftover = max(0.0, squad_max - accounted)
        # Split leftover equally across fillers (almost always one).
        share = leftover / len(fill_placeholders) if fill_placeholders else 0.0
        for ml in fill_placeholders:
            ml.count = share
            models.append(ml)
    # Clamp the SUM of counts to squad_max — if our heuristic over-allocates
    # (e.g. basic-marine "max=9" + heavy "max=4" + sergeant "max=1" = 14 > 10),
    # scale the basic-marine model down. The basic model is the one with the
    # largest max constraint (typically the boltgun grunt).
    total_cnt = sum(m.count for m in models)
    if total_cnt > squad_max:
        # Find the largest single contributor and shrink it by the overflow.
        biggest = max(models, key=lambda m: m.count)
        biggest.count = max(0.0, biggest.count - (total_cnt - squad_max))
    # Drop empty rows
    models = [m for m in models if m.count > 0 and (m.ranged or m.melee)]
    if not models:
        return None
    # Verify the combined squad actually has SOME weapon
    if not any(m.ranged or m.melee for m in models):
        return None
    return models


def _flatten_to_basket(
    models: List[ModelLoadout],
    select: str,   # "ranged" or "melee"
) -> List[tuple[float, WeaponStats]]:
    """
    Spread each ModelLoadout's weapons across its `count` budget.

    A model with 2 weapons of the named kind splits its count evenly
    between them — that's the "this model carries both" interpretation,
    closest to per-model expected damage. (For most squads the result is
    a single ranged + a single melee per model, so the split is trivial.)
    """
    basket: List[tuple[float, WeaponStats]] = []
    for m in models:
        weapons = m.ranged if select == "ranged" else m.melee
        if not weapons:
            continue
        share = m.count / len(weapons)
        for w in weapons:
            basket.append((share, w))
    return basket


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
    # Lone Operative (10e core ability) — ranged attackers must be within 12"
    # to target this unit. Parsed via `extract_lone_operative` from BSData.
    lone_operative: bool = False
    # Phase I — deployment abilities (parsed from unit-level infoLinks)
    deep_strike: bool = False                     # starts in Reserves; arrives turn 2+
    scout_distance: int = 0                       # pre-game Normal Move up to N"
    infiltrator: bool = False                     # deploy past the deployment line
    # Deadly Demise X — when destroyed, roll 1D6; on 6, each unit within 6"
    # suffers X mortal wounds. Integer X is the expected-value of the codex
    # text (D3→2, D6→3, D3+3→5, plain integer N→N). 0 = no Deadly Demise.
    # Cited as `simulator.deadly_demise`.
    deadly_demise: int = 0
    # Firing Deck X (10e core, TRANSPORT keyword). When this unit shoots,
    # up to X embarked passenger models may also shoot using the transport's
    # BS. Integer X parsed from the BSData "Firing Deck" infoLink modifier.
    # 0 = no Firing Deck. Cited as `simulator.firing_deck`.
    firing_deck: int = 0
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
    # Renderer-only base footprint. BSData doesn't encode base sizes, so we
    # derive a sensible default from the unit's keywords at map time; the
    # hand-curated override path in data/overrides.json wins for precision
    # cases (Repulsor 102x178mm, Riptide 80mm, etc.). See UnitProfile.base_shape
    # for the shape vocabulary.
    base_shape: str = "circle"
    base_diameter_mm: int = 32
    base_width_mm: int = 32
    base_length_mm: int = 32
    loadout: List[str] = field(default_factory=list)
    notes: str = ""
    enabled: bool = True
    skip_reason: str = ""


def _derive_base_footprint(unit_keywords: List[str]) -> tuple:
    """Best-effort base footprint from 10e keywords. BSData doesn't encode
    real GW base sizes, so we pick a sensible default per silhouette family
    and let `data/overrides.json` overwrite per-unit precision values
    (Repulsor 102x178mm, Riptide 80mm, etc.).

    Returns (shape, diameter_mm, width_mm, length_mm). For "circle" only
    diameter is meaningful; for "rect"/"oval" only width and length matter.

    Defaults chosen to match common GW kits:
      TITANIC / TOWERING     -> 170x105mm oval (typical Knight footprint)
      VEHICLE / WALKER       -> 152x89mm rect (Rhino chassis footprint)
      MONSTER (no FLY)       -> 80mm circle  (typical mid-monster base)
      MONSTER + FLY          -> 105x70mm oval (typical flying monster)
      BIKE / MOUNTED         -> 75x42mm oval (GW small oval)
      SWARM                  -> 40mm circle  (cluster base)
      CHARACTER (no others)  -> 32mm circle  (named hero default)
      INFANTRY / fallback    -> 32mm circle  (Marine default)
    """
    kw = set(k.upper() for k in (unit_keywords or ()))
    if "TITANIC" in kw or "TOWERING" in kw:
        return ("oval", 32, 105, 170)
    if "VEHICLE" in kw or "WALKER" in kw:
        return ("rect", 32, 89, 152)
    if "MONSTER" in kw:
        if "FLY" in kw:
            return ("oval", 32, 70, 105)
        return ("circle", 80, 80, 80)
    if "BIKE" in kw or "MOUNTED" in kw:
        return ("oval", 32, 42, 75)
    if "SWARM" in kw:
        return ("circle", 40, 40, 40)
    # CHARACTER / INFANTRY / nothing -> standard 32mm Marine round
    return ("circle", 32, 32, 32)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(codex: str, name: str) -> str:
    short = codex.replace(".cat.gz", "").replace(".gst.gz", "").replace(".cat", "")
    # Drop common prefixes for cleaner keys
    for prefix in ("Imperium - Adeptus Astartes - ", "Imperium - ", "Chaos - "):
        if short.startswith(prefix):
            short = short[len(prefix):]
            break
    base = f"{short}-{name}".lower()
    return _SLUG_RE.sub("_", base).strip("_")


# Telemetry: how many units used the squad-aware (heterogeneous) path vs.
# fell back to the legacy single-best-weapon path. Reset by `map_all`.
_LOADOUT_TELEMETRY: Dict[str, int] = {"heterogeneous": 0, "fallback": 0}


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

    # --- Heterogeneous squad-loadout path (issue #76) -----------------------
    # For multi-model squads, walk the inner model entries and build a
    # per-weapon basket weighted by typical headcount. The resulting synthetic
    # WeaponStats sit BETWEEN the base bolter and the all-best-loadout cheese.
    #
    # If parsing fails (single-model unit, no constraint info, no resolvable
    # weapons in the squad SEG) we fall back to the legacy gather_wargear path
    # below — that's the safety floor required by the task brief.
    squad_models = gather_squad_loadout(entry, reg)
    loadout_basket_ranged: List[tuple[float, WeaponStats]] = []
    loadout_basket_melee: List[tuple[float, WeaponStats]] = []
    if squad_models is not None:
        loadout_basket_ranged = _flatten_to_basket(squad_models, "ranged")
        loadout_basket_melee = _flatten_to_basket(squad_models, "melee")
    used_heterogeneous = bool(squad_models) and (
        bool(loadout_basket_ranged) or bool(loadout_basket_melee)
    )

    # Melee fallback — a unit with no ranged weapon is still useful if it
    # has a melee profile. Such units become engagement-only (range_inches=1).
    has_ranged = bool(gear.ranged_weapons) or bool(loadout_basket_ranged)
    has_melee = bool(gear.melee_weapons) or bool(loadout_basket_melee)
    if not has_ranged and not has_melee:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=float(stats.wounds), damage=0, hit_probability=0,
            ap=0, save=stats.save,
            points_listed=points, enabled=False,
            skip_reason="no ranged OR melee weapons resolvable in tree",
        )

    # Best ranged / melee weapon — for single-model units (or units where the
    # heterogeneous path failed) we fall back to the legacy "single best
    # weapon in tree" behaviour. For multi-model squads with a parseable
    # loadout, we synthesise a weighted-average weapon instead.
    if used_heterogeneous and loadout_basket_ranged:
        best = weighted_basket_average(loadout_basket_ranged)
    elif gear.ranged_weapons:
        best = max(gear.ranged_weapons, key=lambda w: w.expected_damage_through_baseline())
    else:
        best = None
    if used_heterogeneous and loadout_basket_melee:
        best_melee = weighted_basket_average(loadout_basket_melee)
    elif gear.melee_weapons:
        best_melee = max(gear.melee_weapons, key=lambda w: w.expected_damage_through_baseline())
    else:
        best_melee = None
    # Recompute has_ranged/has_melee in case the basket-average returned None.
    has_ranged = best is not None
    has_melee = best_melee is not None
    if not has_ranged and not has_melee:
        return MappedUnit(
            key=key, name=name, codex=codex,
            health=float(stats.wounds), damage=0, hit_probability=0,
            ap=0, save=stats.save,
            points_listed=points, enabled=False,
            skip_reason="no ranged OR melee weapons resolvable in tree",
        )
    if used_heterogeneous:
        _LOADOUT_TELEMETRY["heterogeneous"] += 1
    elif squad_models is None:
        # Single-model unit — fallback isn't actually "fallback", it's the
        # correct path. Don't count it.
        pass
    else:
        _LOADOUT_TELEMETRY["fallback"] += 1
    min_m, max_m = extract_squad_size(entry)
    invuln = extract_invuln(entry, reg)
    unit_kw = extract_unit_keywords(entry)
    fnp = extract_fnp(entry, reg)
    stealth = extract_stealth(entry, reg)
    lone_operative = extract_lone_operative(entry, reg)
    deployment = extract_deployment_abilities(entry)
    deadly_demise = extract_deadly_demise(entry)
    firing_deck = extract_firing_deck(entry)

    # If melee-only (no ranged), use the melee weapon as the primary stat line
    primary = best if best is not None else best_melee
    # Derive range_inches: melee-only units get 1" engagement; else parse the
    # ranged weapon's Range characteristic ("24"" -> 24), default 24 on failure.
    if not has_ranged:
        primary_range = 1
    else:
        m = re.search(r"(\d+)", best.range or "")
        primary_range = int(m.group(1)) if m else 24
    base_shape, base_diameter, base_width, base_length = _derive_base_footprint(list(unit_kw))
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
        lone_operative=lone_operative,
        deep_strike=bool(deployment["deep_strike"]),
        scout_distance=int(deployment["scout_distance"]),
        infiltrator=bool(deployment["infiltrator"]),
        deadly_demise=deadly_demise,
        firing_deck=firing_deck,
        fnp=fnp,
        unit_keywords=list(unit_kw),
        melee_attacks=max(0, int(round(best_melee.attacks))) if best_melee else 0,
        melee_damage_per_shot=round(best_melee.damage, 2) if best_melee else 0.0,
        melee_hit_probability=round(best_melee.hit_prob, 3) if best_melee else 0.0,
        melee_strength=best_melee.strength if best_melee else 4,
        melee_ap=best_melee.ap if best_melee else 0,
        melee_weapon=best_melee.name if best_melee else "",
        range_inches=primary_range,
        base_shape=base_shape,
        base_diameter_mm=base_diameter,
        base_width_mm=base_width,
        base_length_mm=base_length,
        loadout=_build_loadout_strings(
            primary, gear, squad_models, used_heterogeneous,
        ),
        notes=(
            f"LD={stats.leadership} OC={stats.oc} "
            f"melee={'yes' if has_melee else 'no'} "
            f"ranged={'yes' if has_ranged else 'no'} "
            f"loadout={'heterogeneous' if used_heterogeneous else 'all-best'}"
        ),
    )


def _build_loadout_strings(
    primary: WeaponStats,
    gear: UnitWargear,
    squad_models: Optional[List[ModelLoadout]],
    used_heterogeneous: bool,
) -> List[str]:
    """
    Human-readable loadout list for the MappedUnit.

    Heterogeneous path: show each model's contribution as "Weapon x<n>"
    (rounded count) so the BSData mix is visible. Falls back to the legacy
    "primary first, then other weapons in the tree" formatting.
    """
    if used_heterogeneous and squad_models is not None:
        rows: List[str] = []
        for ml in squad_models:
            n = max(1, int(round(ml.count)))
            for w in ml.ranged + ml.melee:
                rows.append(f"{w.name} x{n}")
        # Deduplicate while preserving first occurrence
        seen: set = set()
        out: List[str] = []
        for r in rows:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out[:8]
    return [primary.name] + [
        w.name
        for w in (gear.ranged_weapons + gear.melee_weapons)
        if w.name != primary.name
    ][:4]


# ---------------------------------------------------------------------------
# Unit keywords + FNP extractors
# ---------------------------------------------------------------------------

# Standard 10e unit keywords we care about for Anti-X targeting and rules.
#
# ASURYANI is a faction sub-keyword: every Eldar Craftworlds unit carries it
# (Guardians, Aspect Warriors, Wraith constructs, etc.), and the simulator's
# Aeldari Battle Focus mechanic gates on it. In BSData the keyword appears
# as a <categoryLink name="Faction: Asuryani"/> on the unit's selectionEntry;
# Drukhari, Harlequins, and Ynnari units do not carry that link (per the
# 10e Aeldari codex), so we get correct discrimination for free from the
# categoryLink → keyword mapping below.
_TRACKED_UNIT_KEYWORDS = {
    "INFANTRY", "VEHICLE", "MONSTER", "CHARACTER", "FLY",
    "TITANIC", "TOWERING", "WALKER", "BATTLELINE", "SWARM",
    "BIKE", "MOUNTED", "BEAST", "DAEMON", "PSYKER",
    "ASURYANI",
    # TRANSPORT (10e core). Any model that can carry passengers carries this
    # keyword (Rhino, Repulsor, Impulsor, Wave Serpent, Devilfish, Chimera,
    # Trukk, Caladius Grav-Tank, etc.) plus a "Transport" Ability profile on
    # its datasheet. Read by simulator.embark / simulator.disembark /
    # simulator.firing_deck / simulator.destroyed_transport gates.
    "TRANSPORT",
    # SYNAPSE: Tyranids army-rule keyword. Used by simulator.synapse_imperative
    # (friendly Tyranids within 6" auto-pass Battle-shock) and
    # simulator.shadow_in_the_warp (enemy units within 12" take Battle-shock
    # at -1 to the test). Carried by Hive Tyrants, Tervigons, Maleceptors,
    # Tyranid Primes, Old One Eye, Norn Emissary, Broodlords, etc.
    "SYNAPSE",
    # EPIC HERO: 10e core rule — "EPIC HERO units can only be taken once per
    # army." Universal across every codex. Read by army-composition gates
    # (build_faction_random_army, _random_fill, archetype seed) to refuse
    # duplicate inclusion. Source:
    # https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Datasheets
    "EPIC HERO",
}


def extract_unit_keywords(entry: ET.Element) -> List[str]:
    """Scan the unit's categoryLinks for known 10e keyword tags.

    Each categoryLink name is uppercased and any BSData prefix (e.g.
    "Faction: ", "Allegiance: ") is stripped before matching against
    ``_TRACKED_UNIT_KEYWORDS``. This means "Faction: Asuryani" becomes
    "ASURYANI", "Infantry" becomes "INFANTRY", etc. — the cleaned name
    is matched as-is, so the tracked set is the single source of truth
    for which keywords are exposed to the simulator.
    """
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
# Matches the value attribute on a <modifier type="append" field="name" value="5+"/>
# child of an FNP infoLink (BSData's canonical encoding for the threshold).
_FNP_MOD_VALUE_RE = re.compile(r"(\d)\s*\+?")
# Unit-level "Stealth" ability: matches Stealth as a bare word (not "Stealthy"
# adjectives). Used by extract_stealth to detect the defensive ability that
# imposes -1 to hit when this unit is shot at.
_STEALTH_ABILITY_RE = re.compile(r"(?:^|[\s,;.])Stealth(?:$|[\s,;.\)])")


def _fnp_from_infolink_modifier(il: ET.Element) -> int:
    """
    Read the FNP threshold from a Feel No Pain infoLink's modifier-append child.

    BSData encodes the FNP value as:
        <infoLink name="Feel No Pain" type="rule" targetId="...">
          <modifiers>
            <modifier type="append" field="name" value="5+"/>
          </modifiers>
        </infoLink>

    The linked "Feel No Pain" rule body itself just says "Feel No Pain x+"
    (no number), so the only place to recover the per-unit threshold is
    this modifier. Returns 7 if the infoLink isn't actually an FNP link or
    no readable threshold is present.
    """
    name = (il.get("name") or "").strip()
    if name.lower() != "feel no pain":
        return 7
    best = 7
    for mod in il.iter():
        tag = mod.tag.split("}")[-1] if "}" in mod.tag else mod.tag
        if tag != "modifier":
            continue
        if (mod.get("type") or "").lower() != "append":
            continue
        if (mod.get("field") or "").lower() != "name":
            continue
        value = (mod.get("value") or "").strip()
        m = _FNP_MOD_VALUE_RE.search(value)
        if not m:
            continue
        try:
            v = int(m.group(1))
        except ValueError:
            continue
        if 2 <= v <= 6 and v < best:
            best = v
    return best


def extract_fnp(entry: ET.Element, reg: Registry) -> int:
    """
    Resolve the unit's Feel No Pain threshold.

    Strategy (canonical first, prose as fallback):
      1. Scan the unit's direct infoLinks for ``name="Feel No Pain"`` carrying
         a ``<modifier type="append" field="name" value="N+"/>`` — this is the
         BSData-canonical encoding. ~107 units across 27 catalogues use this
         shape (Poxwalkers, Wracks, Wulfen, Repentia, Death Company, etc.),
         and they were previously dropped to FNP 7 because the linked rule
         body says "Feel No Pain x+" with no number.
      2. Fall back to the legacy depth-limited walk that hunts for prose
         "Feel No Pain N+" in characteristic text on linked profiles / rules.
    Returns the lowest N (best for the unit), or 7 if none.
    """
    best = 7
    # (1) Canonical modifier-append at unit-direct infoLinks. We also look
    # one level deep into entryLinks (some units expose FNP via an upgrade
    # selectionEntry's infoLinks, e.g. wargear-granted FNP), but never
    # follow rule targetIds — the rule body never carries the threshold.
    canonical_found = False
    for il in entry.findall("./infoLinks/infoLink"):
        v = _fnp_from_infolink_modifier(il)
        if v < best:
            best = v
        if (il.get("name") or "").strip().lower() == "feel no pain":
            canonical_found = True
    for il in entry.findall("./entryLinks/entryLink/infoLinks/infoLink"):
        v = _fnp_from_infolink_modifier(il)
        if v < best:
            best = v
        if (il.get("name") or "").strip().lower() == "feel no pain":
            canonical_found = True
    # When a canonical Feel No Pain infoLink is present on the unit (or one
    # of its direct upgrade selectionEntries), trust its modifier-append
    # value as authoritative. The legacy prose walk traverses shared rules
    # / library entries that frequently mention OTHER units' FNP thresholds
    # in passing (e.g. "X works against Feel No Pain 5+ abilities"), which
    # would otherwise pull a stronger but incorrect threshold here.
    if canonical_found:
        return best
    # (2) Legacy prose walk — catches the older shape where the threshold is
    # baked into an ability description ("This unit has the Feel No Pain 5+
    # ability."). Kept as a fallback for units that don't use the canonical
    # infoLink+modifier idiom.
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


# ---------------------------------------------------------------------------
# Phase I — Deep Strike / Scout / Infiltrators extraction
# ---------------------------------------------------------------------------
#
# Wahapedia 10e shape in BSData:
#   - "Deep Strike" appears as an infoLink (type="rule") with name="Deep Strike".
#   - "Infiltrators" appears as an infoLink (type="rule") with name="Infiltrators".
#   - "Scouts" appears as an infoLink (type="rule") with name="Scouts" — the
#     actual distance ("6"", "7"", "8"", "9"") is published as a child
#     <modifier type="append" field="name" value='6"' /> on the infoLink so
#     the displayed name in BS becomes "Scouts 6"". A handful of units
#     publish "Scouts x"" directly as the infoLink name; we accept either
#     shape so we don't miss those.
#
# We only honour the unit-level infoLinks on the unit's selectionEntry — never
# free-form prose that merely mentions the words.

_SCOUTS_DISTANCE_RE = re.compile(r"(\d+)\s*\"?")


def _extract_scout_distance_from_infolink(il: ET.Element) -> int:
    """Pull the scout distance from an infoLink whose name is 'Scouts' or
    'Scouts N"'. Returns 0 if no number can be recovered."""
    name = (il.get("name") or "").strip()
    # Shape 1: name already carries the distance ("Scouts 6"" / "Scouts 8")
    if name.lower().startswith("scouts"):
        m = _SCOUTS_DISTANCE_RE.search(name[len("Scouts"):])
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
    # Shape 2: a child <modifier field="name" type="append" value='6"' />
    # Tag uses the catalogueSchema namespace, so iterate any descendant
    # named 'modifier' regardless of prefix.
    for mod in il.iter():
        tag = mod.tag.split("}")[-1] if "}" in mod.tag else mod.tag
        if tag != "modifier":
            continue
        if mod.get("field") != "name" or mod.get("type") != "append":
            continue
        val = (mod.get("value") or "").strip()
        m = _SCOUTS_DISTANCE_RE.search(val)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return 0


def extract_deployment_abilities(entry: ET.Element) -> Dict[str, object]:
    """
    Scan the unit's directly-attached infoLinks for the three Phase I
    deployment abilities. Returns a dict with three keys:

        deep_strike:     bool
        scout_distance:  int  (0 if no Scouts, else inches; commonly 6/7/8/9)
        infiltrator:     bool

    Mirrors `extract_stealth` in only honouring infoLink names, never prose.
    """
    deep_strike = False
    scout_distance = 0
    infiltrator = False
    for il in entry.findall(".//infoLink"):
        name = (il.get("name") or "").strip()
        if name == "Deep Strike":
            deep_strike = True
        elif name == "Infiltrators":
            infiltrator = True
        elif name == "Scouts" or name.lower().startswith("scouts "):
            d = _extract_scout_distance_from_infolink(il)
            # Default to 6" if we can't recover the distance — that's the
            # most common value across the catalogue and a safe fallback.
            if d <= 0:
                d = 6
            if d > scout_distance:
                scout_distance = d
    return {
        "deep_strike": deep_strike,
        "scout_distance": scout_distance,
        "infiltrator": infiltrator,
    }


_DEADLY_DEMISE_INT_RE = re.compile(r"^\s*(\d+)\s*$")


def _parse_demise_value(s: str) -> int:
    """Map a 'Deadly Demise N' suffix string to its expected-value integer.

    Canonical forms seen in BSData 10e infoLink modifiers:
       "1", "2", "3", "D3", "D6", "D3+3"
    Returns 0 if unrecognised. Mapping:
       integer N -> N
       "D3"      -> 2   (expected value)
       "D6"      -> 3   (expected value, rounded down from 3.5)
       "D3+3"    -> 5   (E[D3] + 3 = 2 + 3)
    """
    s = (s or "").strip()
    if not s:
        return 0
    su = s.upper().replace(" ", "")
    if su == "D3":
        return 2
    if su == "D6":
        return 3
    if su == "D3+3":
        return 5
    if su == "D6+3":
        return 6
    m = _DEADLY_DEMISE_INT_RE.match(s)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0
    return 0


def extract_deadly_demise(entry: ET.Element) -> int:
    """Scan the unit's directly-attached infoLinks for the Deadly Demise ability.

    In BSData 10e, Deadly Demise is published as a shared-rule infoLink with
    name="Deadly Demise" and a child <modifier type="append" field="name"
    value="X"/> that carries the X value as a literal (e.g. "1", "D3", "D6",
    "D3+3"). Returns the parsed integer expected value, or 0 if not present.

    Cited as `simulator.deadly_demise`.
    """
    for il in entry.findall(".//infoLink"):
        name = (il.get("name") or "").strip()
        if name != "Deadly Demise":
            continue
        # Find the modifier carrying the X suffix
        for mod in il.iter():
            tag = mod.tag.split("}")[-1] if "}" in mod.tag else mod.tag
            if tag != "modifier":
                continue
            if mod.get("field") != "name" or mod.get("type") != "append":
                continue
            val = (mod.get("value") or "").strip()
            v = _parse_demise_value(val)
            if v > 0:
                return v
        # Fall back: an infoLink named "Deadly Demise" with no suffix is
        # rare but should still record the ability (treat as 1).
        return 1
    return 0


_FIRING_DECK_INT_RE = re.compile(r"^\s*(\d+)\s*$")


def extract_firing_deck(entry: ET.Element) -> int:
    """Scan the unit's directly-attached infoLinks for the Firing Deck ability.

    In BSData 10e, Firing Deck is published as a shared-rule infoLink with
    name="Firing Deck" and a child <modifier type="append" field="name"
    value="X"/> that carries the integer X (e.g. "2", "6", "10"). Returns
    the parsed integer, or 0 if not present.

    Cited as `simulator.firing_deck`.
    """
    for il in entry.findall(".//infoLink"):
        name = (il.get("name") or "").strip()
        if name != "Firing Deck":
            continue
        for mod in il.iter():
            tag = mod.tag.split("}")[-1] if "}" in mod.tag else mod.tag
            if tag != "modifier":
                continue
            if mod.get("field") != "name" or mod.get("type") != "append":
                continue
            val = (mod.get("value") or "").strip()
            m = _FIRING_DECK_INT_RE.match(val)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    return 0
        # Firing Deck with no parsed X — fall back to 1 so the keyword
        # still registers (rare; defensive).
        return 1
    return 0


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


def extract_lone_operative(entry: ET.Element, reg: Registry) -> bool:
    """True iff the unit has the Lone Operative core ability (ranged attackers
    must be within 12" to target it).

    Detection mirrors `extract_stealth`: BSData publishes Lone Operative as a
    shared rule infoLink with `name="Lone Operative"` attached to the unit
    entry, plus a small number of datasheets inline it as a profile named
    "Lone Operative". Only those two structured shapes count — never
    free-form prose that merely mentions the words.
    """
    for il in entry.findall(".//infoLink"):
        if (il.get("name") or "").strip().lower() == "lone operative":
            return True
    for prof in entry.findall(".//profile"):
        if (prof.get("name") or "").strip().lower() == "lone operative":
            return True
    return False


_INVULN_RE = re.compile(r"Invulnerable\s+Save\s*\(?\s*(\d)\s*\+", re.IGNORECASE)
# Match the digit inside an Invuln-Save profile's Description characteristic.
# Three canonical phrasings appear across BSData (surveyed across all codices):
#   "Models in this unit have a 4+ invulnerable save."
#   "This model has a 4+ invulnerable save."
#   "Invulnerable Save of 4+." (Drukhari Archon, etc.)
# A handful of profiles store ONLY the bare digit ("4+") in the Description,
# leaning on the profile's name="Invulnerable Save" for context — covered by
# `_INVULN_BARE_RE` as a fallback.
_INVULN_DESC_PRE_RE = re.compile(r"(\d)\+\s*[Ii]nvulnerable\s+[Ss]ave", re.IGNORECASE)
_INVULN_DESC_POST_RE = re.compile(r"[Ii]nvulnerable\s+[Ss]ave\s+of\s+(\d)\+", re.IGNORECASE)
_INVULN_BARE_RE = re.compile(r"^\s*(\d)\+\s*$")
# We deliberately do NOT exclude phrasings like "against ranged attacks only".
# The simulator doesn't model ranged-vs-melee invuln separately, and an invuln
# that only applies vs ranged attacks is still strictly better than no invuln
# (vs the simulator's symmetric shooting-then-melee phase, the effective uplift
# is approximate but on the correct side). If we later add ranged-only invuln
# modelling, that's the right place to slice this distinction.


def _parse_invuln_from_description(desc: str) -> Optional[int]:
    """Pull the digit from an Invuln-Save profile's Description characteristic.

    Returns None if no recognisable invuln value is present.
    """
    if not desc:
        return None
    m = _INVULN_DESC_PRE_RE.search(desc)
    if m:
        return int(m.group(1))
    m = _INVULN_DESC_POST_RE.search(desc)
    if m:
        return int(m.group(1))
    m = _INVULN_BARE_RE.match(desc.strip())
    if m:
        return int(m.group(1))
    return None


def _is_bare_invuln_name(name: str) -> bool:
    """True if an infoLink/profile name is exactly "Invulnerable Save" with no
    qualifying parenthetical (e.g. "Invulnerable Save (Yvraine)" — conditional
    on a leader — should NOT match: those infoLinks point at non-Invuln rules).
    """
    s = (name or "").strip()
    return s.lower() == "invulnerable save"


def extract_invuln(entry: ET.Element, reg: Registry) -> int:
    """
    Find the best invulnerable save on a unit by scanning infoLinks for two shapes:

      1. The infoLink's own name carries the digit ("Invulnerable Save (4+*)")
         — historical shape, e.g. Genestealer Cults Patriarch.
      2. The infoLink's name is the bare "Invulnerable Save" and the digit
         lives in the LINKED profile's Description characteristic — the shape
         used by Adeptus Custodes (all 31 datasheets), Adeptus Mechanicus,
         Terminator squads, Sanguinary Guard, Marneus Calgar etc. Discovered
         missing in May 2026 Phase 3 defensive audit.

    Returns the best (lowest) value found, or 7 if none.
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
            # Shape 1: digit embedded in the infoLink name.
            m = _INVULN_RE.search(name)
            if m:
                v = int(m.group(1))
                if v < best:
                    best = v
                continue
            # Shape 2: bare "Invulnerable Save" name → resolve target profile
            # and parse its Description characteristic for the digit.
            if not _is_bare_invuln_name(name):
                continue
            target = reg.resolve(il.get("targetId") or "")
            if target is None or target.tag != "profile":
                continue
            for ch in target.iter("characteristic"):
                if ch.get("name") != "Description":
                    continue
                v = _parse_invuln_from_description(ch.text or "")
                if v is not None and v < best:
                    best = v
                break
        for el in elem.findall("./entryLinks/entryLink"):
            target = reg.resolve(el.get("targetId") or "")
            if target is not None:
                walk(target, depth + 1)
    walk(entry, 0)
    return best


def map_all(reg: Optional[Registry] = None) -> List[MappedUnit]:
    if reg is None:
        reg = load_registry()
    # Reset telemetry so successive map_all() calls report this run only.
    _LOADOUT_TELEMETRY["heterogeneous"] = 0
    _LOADOUT_TELEMETRY["fallback"] = 0
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
    het = _LOADOUT_TELEMETRY["heterogeneous"]
    fb = _LOADOUT_TELEMETRY["fallback"]
    print(
        f"[mapper] loadout: {het} heterogeneous (squad-aware), "
        f"{fb} fallback (no parseable squad SEG)"
    )

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
