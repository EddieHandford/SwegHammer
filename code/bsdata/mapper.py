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
import os
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
# Weapon-CHOICE target basket (SWEG_CHOICE_TARGET_BASKET)
# ---------------------------------------------------------------------------
#
# The legacy weapon-choice score `expected_damage_through_baseline` scores a
# weapon as  attacks * hit_prob * damage * (1 - marine_save_after_ap)  — it has
# NO strength-versus-toughness wound roll at all, so a weapon's Strength is
# ignored entirely when a choice group is resolved. Consequence: every anti-tank
# option (high Strength, low volume) loses to the higher-volume anti-infantry
# option in its group, because the only thing the score rewards is raw shot
# volume times flat damage. The canonical live case is the Drukhari Ravager,
# which the mapper equips with Disintegrator Cannons (Strength 6) instead of
# Dark Lances (Strength 12); the whole field ends up under-armed against
# vehicles and monsters.
#
# The fix, gated behind SWEG_CHOICE_TARGET_BASKET, scores every weapon-choice
# option against a REPRESENTATIVE TARGET BASKET — a weighted set of the three
# target classes a real 2000-point field presents — WITH the wound roll the
# baseline metric omitted. An option's basket score is the weighted sum of its
# expected damage against each class, so an anti-tank option wins wherever its
# Strength earns it against the monster/vehicle share of the field.
#
# The class weights are the census of the tournament ARCHETYPES templates
# (code/archetypes.py): every unit the archetypes field was classified into one
# of the three classes (monster/vehicle if it carries the VEHICLE, MONSTER or
# TITANIC keyword; heavy infantry if it has a 3+-or-better save, Toughness 5+ or
# 2+ wounds; light infantry otherwise), and the classes were counted weighted by
# the archetypes' own template counts. That census is:
#     light infantry     15.2 %   (Gaunts / Guardsmen / Cultists — Toughness 3, save 5+)
#     heavy infantry      51.4 %   (Marines / Terminators / Custodes — Toughness 4, save 3+)
#     monster / vehicle   33.4 %   (Toughness 10, save 3+)
# rounded to the weights below (which sum to exactly 1.0). The representative
# Toughness / Save per class are the medians of the units the archetypes field
# in that class. Damage is NOT capped at the target's wounds — this keeps the
# metric's damage treatment identical to the legacy baseline metric, so the only
# structural change is the newly-added wound roll and the multi-class basket.
#
# Each entry: (weight, toughness, save, keywords, melta_applies). `keywords` is
# the target-class keyword set an Anti-X weapon keyword improves the wound roll
# against; `melta_applies` adds the weapon's Melta bonus to its damage (half-range
# assumption) only against the monster/vehicle class.
_CHOICE_TARGET_BASKET = (
    (0.15, 3, 5, frozenset({"INFANTRY"}), False),               # light infantry
    (0.51, 4, 3, frozenset({"INFANTRY"}), False),               # heavy infantry
    (0.34, 10, 3, frozenset({"VEHICLE", "MONSTER"}), True),     # monster / vehicle
)

# Whether the choice scorers use the target basket. Read once at mapper import /
# regeneration time (rule 13 — an explicit, documented default, not a silent
# fallback). Default OFF reproduces parsed.json byte-for-byte; the fix ships by
# regenerating parsed.json with this ON and committing the new data, exactly as
# the choice-group fix did.
_USE_CHOICE_BASKET = os.environ.get(
    "SWEG_CHOICE_TARGET_BASKET", "0"
).strip().lower() not in ("", "0", "false", "off", "no")


def _wound_probability(strength: int, toughness: int) -> float:
    """10e Strength-versus-Toughness wound chart. Mirrors
    code/units.wound_probability verbatim; kept local so the mapper does not
    import the catalogue module (avoids an import cycle)."""
    if strength >= 2 * toughness:
        return 5 / 6
    if 2 * strength <= toughness:
        return 1 / 6
    if strength > toughness:
        return 4 / 6
    if strength == toughness:
        return 3 / 6
    return 2 / 6   # strength < toughness but not 2S <= T


def _save_prob_after_ap(save: int, ap: int) -> float:
    """Probability a model with this armour save passes against a weapon with
    this AP. Generalises `_baseline_save_after_ap` to any save characteristic.
    A save can never be better than 2+ (a natural 1 always fails)."""
    effective = save - ap  # ap is negative
    if effective > 6:
        return 0.0
    if effective < 2:
        effective = 2
    return max(0.0, (7 - effective) / 6.0)


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
    # PER-MODEL-LOADOUTS STAGE 1 — raw BSData dice strings for the Attacks and
    # Damage characteristics (e.g. "2D6", "D6+1"). `attacks` / `damage` above
    # keep the expected-value MEAN as today (via parse_dice_expr); these two
    # fields preserve the unrolled dice expression so a later stage can roll
    # real damage dice per shot. They default to "" and are NOT read by
    # `weighted_basket_average` (which constructs the synthetic aggregate
    # weapon from numeric means + flags only), so the aggregate stays
    # byte-identical and the dice strings never leak into it.
    attacks_dice: str = ""
    damage_dice: str = ""
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
    # DAEMONS-EXTRA-MELEE-MAPPER-V1 — Extra Attacks keyword. When True, this
    # melee weapon fires IN ADDITION to the model's other melee weapons in the
    # Fight phase (10e core rule). The mapper collects weapons with this flag
    # into UnitProfile.extra_melee_profiles. Cited as
    # `simulator.extra_melee_profiles`.
    extra_attacks: bool = False
    # MAP-3-FIX — basket-fraction gating for partial-coverage weapon keywords.
    # The MAP-3 boolean flags (lance, devastating_wounds, anti_keywords) take
    # the UNION across the basket so heterogeneous squads (Rubric Marines,
    # Skyweavers, Beast Snagga Boyz, Knight Castellan, AdMech Skitarii) keep
    # the keyword visible to the picker. To prevent every shot in such a squad
    # from firing the keyword (single-weapon model contaminating the whole
    # unit), the simulator gates each attack with a Bernoulli draw against
    # these fractions. Default 1.0 preserves legacy behaviour for any path
    # that does not set them (single-weapon units, multi-profile picker swap
    # producing a synthetic profile that already isolates the keyword).
    devastating_wounds_basket_fraction: float = 1.0
    lance_basket_fraction: float = 1.0
    anti_keyword_basket_fractions: Dict[str, float] = field(default_factory=dict)

    def _apply_keyword_bumps(self, base: float) -> float:
        """Approximate ability boosts so the loadout optimiser doesn't
        undervalue high-ability weapons. Small multiplicative bumps based on
        common math. Shared by the baseline-Marine and target-basket scorers so
        both rank abilities on the same footing."""
        if self.lethal_hits:
            base *= 1.15
        if self.sustained_hits:
            base *= (1.0 + 0.17 * self.sustained_hits)   # 1/6 crit rate × N
        if self.twin_linked:
            base *= 1.30
        if self.devastating_wounds:
            base *= 1.10
        return base

    def expected_damage_through_baseline(self) -> float:
        """Expected damage per activation against a baseline Marine."""
        base = (
            self.attacks
            * self.hit_prob
            * self.damage
            * (1.0 - _baseline_save_after_ap(self.ap))
        )
        return self._apply_keyword_bumps(base)

    def expected_damage_vs_basket(self) -> float:
        """Expected damage per activation against the representative target
        basket (`_CHOICE_TARGET_BASKET`).

        Unlike `expected_damage_through_baseline`, this INCLUDES the
        Strength-versus-Toughness wound roll — the term the baseline metric
        omits, which made every anti-tank option lose to a higher-volume
        anti-infantry option in its choice group. The score is the weighted sum
        over the three target classes of

            attacks * hit_prob * wound_prob(S, T) * unsaved(save, AP) * damage

        with the same multiplicative ability bumps applied on top. An Anti-X
        weapon keyword improves the wound roll against a class carrying keyword
        X, and Melta adds its bonus to damage against the monster/vehicle class
        (half-range assumption). Damage is NOT capped at the target's wounds,
        matching the baseline metric's damage treatment.

        A [ONE SHOT] weapon is discounted to one fifth of its per-activation
        score: it fires once in a roughly five-round battle, whereas a normal
        weapon fires every round, so a one-shot bonus weapon (a hunter-killer
        missile) must never out-rank a unit's every-round gun as its primary.
        The baseline metric could not surface this because, lacking the wound
        roll, it already under-rated the high-Strength one-shot missiles; adding
        the wound roll makes the discount necessary."""
        base = 0.0
        anti = self.anti_keywords or {}
        for weight, toughness, save, class_keywords, melta_applies in _CHOICE_TARGET_BASKET:
            wound = _wound_probability(self.strength, toughness)
            for keyword, threshold in anti.items():
                if keyword in class_keywords:
                    try:
                        wound = max(wound, (7 - int(threshold)) / 6.0)
                    except (TypeError, ValueError):
                        continue
            damage = self.damage + (self.melta if melta_applies else 0)
            unsaved = 1.0 - _save_prob_after_ap(save, self.ap)
            base += weight * self.attacks * self.hit_prob * wound * unsaved * damage
        score = self._apply_keyword_bumps(base)
        if self.one_shot:
            score *= 0.2   # fires once per ~5-round battle, not every round
        return score


def _choice_score(weapon: "WeaponStats") -> float:
    """Score a weapon for a CHOICE decision (which option a choice group takes,
    which weapon is a chassis's primary, the ranking of secondary profiles).

    Behind `SWEG_CHOICE_TARGET_BASKET` (read once at mapper-run / regeneration
    time) this is the Toughness-aware target-basket score, so anti-tank options
    win where their Strength earns it. With the gate OFF (the default) it is
    byte-for-byte the legacy baseline-Marine score, so a gate-off regeneration
    reproduces `parsed.json` exactly. Every weapon-choice scorer in the mapper
    routes through this one function so the catalogue is scored consistently."""
    if _USE_CHOICE_BASKET:
        return weapon.expected_damage_vs_basket()
    return weapon.expected_damage_through_baseline()


def weighted_basket_average(basket: "List[tuple[float, WeaponStats]]") -> Optional["WeaponStats"]:
    """
    Collapse a `[(weight, WeaponStats)] ` basket into a single synthetic
    WeaponStats by taking the WEIGHTED average of (attacks, damage, ap,
    hit_prob, strength) and proportion-thresholded keyword effects.

    Rationale:
      - Per-model stats (attacks/damage/AP/hit_prob/strength) are averaged so
        a 10-model Devastator Squad with 4 multi-meltas and 5 boltguns + 1
        sergeant ends up between bolter-only and multi-melta-only damage.

      - **Boolean weapon keywords** (lethal_hits, devastating_wounds,
        twin_linked, ignores_cover, heavy, assault, blast, hazardous, lance,
        precision, pistol, indirect_fire, one_shot, stealth) are gated by
        whether they fire on a MAJORITY of attacks in the basket. The
        previous `any(...)` union granted Plague Marines squad-wide Lethal
        Hits from a single heavy plague weapon on 1-of-5 models, inflating
        BATTLELINE damage across many factions (issue: #iter20).

        Threshold = 50% (strict majority). Chosen because the simulator's
        per-attack loop applies these flags as boolean predicates
        (`effective_lethal_hits OR ...`), so the closest single-bit
        approximation to "fraction f of attacks have the keyword" is True
        iff f > 0.5. The remaining model error vs. true per-attack
        stochastic application is bounded by the basket's weight skew.

      - **Integer-magnitude keywords** (sustained_hits, rapid_fire, melta)
        take the proportion-weighted ROUNDED value, NOT the max. A 5-bolter
        + 1-melta squad gets melta = round(1*1/6) = 0 — the dominant weapon
        wins. Previously `max(...)` granted the squad-wide melta keyword
        from a single model, double-counting at the simulator level.

      - **Anti-X** is still proportion-thresholded (a single model carrying
        Anti-Vehicle 2+ should not let a 10-model squad treat every attack
        as Anti-Vehicle). Threshold = 50% on the fraction of basket weight
        that carries the keyword.

      - **Torrent** keeps the ALL-variants rule (mixed Aggressor gauntlets
        must not inherit auto-hit from the Flamestorm leg while averaging
        BS in from the Boltstorm leg).

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

    def _frac_true(predicate) -> float:
        """Fraction of basket weight where `predicate(weapon)` is truthy."""
        num = sum(w for w, x in basket if predicate(x))
        return num / total

    # MAJORITY-THRESHOLD boolean keywords (>50%). See module docstring above
    # for rationale: the simulator applies each as a boolean predicate per
    # attack, so we lose less expected-damage error by setting True iff the
    # keyword fires on >50% of basket-weight, vs the legacy any(...) which
    # let a single elite weapon set the squad flag.
    #
    # MAP-3 exception — ``lance`` and ``devastating_wounds`` are taken as
    # the UNION across the basket. Reasoning: these are situational/keyword
    # bonuses that the simulator-side picker should be aware of as soon as
    # ANY weapon profile in the basket carries them. The model in the squad
    # actively chooses to use that weapon profile when it pays off (charging
    # for [LANCE], shooting at high-toughness for [DEVASTATING WOUNDS]); the
    # majority-of-basket gate previously dropped these keywords for
    # mixed-loadout units (Venatari Custodians, Ork Warbikers, Skyweavers,
    # Knight Castellan), forcing per-unit override patches in AK-1/AK-2.
    # The damage-inflation risk is bounded by the fact that the simulator
    # only fires the bonus on the profile that legitimately carries it
    # (via per-shot picker rules / anti_keywords / multi-profile picker).
    majority = 0.5
    bool_keywords = {
        "lethal_hits": _frac_true(lambda x: x.lethal_hits) > majority,
        "twin_linked": _frac_true(lambda x: x.twin_linked) > majority,
        # UNION (MAP-3) — see comment above
        "devastating_wounds": any(x.devastating_wounds for _, x in basket),
        "ignores_cover": _frac_true(lambda x: x.ignores_cover) > majority,
        "heavy": _frac_true(lambda x: x.heavy) > majority,
        "assault": _frac_true(lambda x: x.assault) > majority,
        "hazardous": _frac_true(lambda x: x.hazardous) > majority,
        "blast": _frac_true(lambda x: x.blast) > majority,
        # UNION (MAP-3) — see comment above
        "lance": any(x.lance for _, x in basket),
        "precision": _frac_true(lambda x: x.precision) > majority,
        "pistol": _frac_true(lambda x: x.pistol) > majority,
        "indirect_fire": _frac_true(lambda x: x.indirect_fire) > majority,
        "one_shot": _frac_true(lambda x: x.one_shot) > majority,
        "stealth": _frac_true(lambda x: x.stealth) > majority,
    }

    # PROPORTION-WEIGHTED integer keywords. A single melta in a 6-model squad
    # contributes weight 1/6 * melta_N to the rounded average; usually rounds
    # to 0, preventing the squad-wide melta cheese.
    def _weighted_int(attr: str) -> int:
        total_weighted = sum(w * int(getattr(x, attr) or 0) for w, x in basket)
        return int(round(total_weighted / total))

    int_keywords = {
        "sustained_hits": _weighted_int("sustained_hits"),
        "rapid_fire": _weighted_int("rapid_fire"),
        "melta": _weighted_int("melta"),
    }

    # Torrent — preserve the legacy ALL-variants rule. Mixed weapon profiles
    # (e.g. Aggressor Auto Boltstorm Gauntlets + Flamestorm Gauntlets) must
    # not inherit auto-hit from the Torrent leg while keeping numeric BS
    # averaged in. See Wahapedia Aggressor Squad:
    # https://wahapedia.ru/wh40k10ed/factions/space-marines/#Aggressor-Squad
    torrent = bool(basket) and all(x.torrent for _, x in basket)

    union: Dict[str, object] = {**bool_keywords, **int_keywords, "torrent": torrent}

    # Anti-X — UNION across the basket per MAP-3. If any weapon profile in
    # the basket carries [ANTI-VEHICLE N+], the squad's basket keeps that
    # tag with the best (lowest) threshold among carrying weapons. The
    # squad's per-attack damage stays honest because the simulator-side
    # picker only fires the anti bonus on the model that's actually
    # carrying that profile (Skyweaver Haywire Cannon, Beast Snagga Klaw,
    # Knight Styrix Graviton Crusher) — the threshold sits on the basket
    # so it can be SEEN, not so it gets multiplied across unrelated shots.
    # The pre-MAP-3 majority gate dropped the keyword for any squad that
    # mixed loadouts (Skyweavers, Scourges, Raveners, Beast Snagga Boyz,
    # Knight Styrix), forcing per-unit override patches in AK-2.
    anti: Dict[str, int] = {}
    all_anti_kws = set()
    for _, x in basket:
        all_anti_kws.update((x.anti_keywords or {}).keys())
    for kw in all_anti_kws:
        best_thresh = min(
            x.anti_keywords[kw] for _, x in basket
            if kw in (x.anti_keywords or {})
        )
        anti[kw] = best_thresh

    # MAP-3-FIX — emit basket fractions alongside the UNION booleans / dict so
    # the simulator can Bernoulli-gate each shot. Each fraction = (sum of basket
    # weights of weapons carrying the keyword) / total basket weight. A single
    # heavy plague weapon in a 5-bolter squad gives fraction = 1/6 = 0.167; the
    # simulator then only fires DEVASTATING WOUNDS on ~17% of shots, which
    # matches reality (only 1 model in 6 carries the weapon that has it).
    dw_fraction = _frac_true(lambda x: x.devastating_wounds)
    lance_fraction = _frac_true(lambda x: x.lance)
    anti_fractions: Dict[str, float] = {}
    for kw in all_anti_kws:
        anti_fractions[kw] = (
            sum(w for w, x in basket if kw in (x.anti_keywords or {})) / total
        )

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
        devastating_wounds_basket_fraction=dw_fraction,
        lance_basket_fraction=lance_fraction,
        anti_keyword_basket_fractions=anti_fractions,
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

# Plasma Incinerator and Macro Plasma Incinerator are NOT Torrent weapons —
# they require a normal Ballistic Skill hit roll. The word "incinerator" in
# their names would otherwise match the _TORRENT_NAME_TOKENS substring sweep,
# incorrectly granting auto-hit to every Hellblaster / Redemptor plasma shot.
# Wahapedia verbatim (Hellblaster Squad plasma incinerator):
#   https://wahapedia.ru/wh40k10ed/factions/space-marines/#Hellblasters
# Keywords field lists: "Heavy, Hazardous" — no Torrent.
_PLASMA_INCINERATOR_RE = re.compile(r"\bplasma\b", re.IGNORECASE)


def _torrent_from_name(name: str) -> bool:
    """True if the weapon's display name implies the Torrent keyword.

    Used as a fallback after the regex sweep of the Keywords characteristic,
    because BSData does not tag flamer-family weapons with "Torrent"
    explicitly — the rule is implied by the weapon noun (Flamer, Burna,
    Heavy Flamer, Inferno Cannon, etc.).

    Exception: "Plasma Incinerator" and "Macro Plasma Incinerator" are NOT
    Torrent — they share the "incinerator" token with flamer-family weapons
    but are plasma weapons that require a normal hit roll.  Guard against
    the false positive by returning False whenever the name also contains
    the word "plasma".
    """
    if not name:
        return False
    lowered = name.lower()
    if not any(tok in lowered for tok in _TORRENT_NAME_TOKENS):
        return False
    # Plasma Incinerator / Macro Plasma Incinerator matched "incinerator" but
    # are not Torrent.  Any weapon name that contains "plasma" alongside a
    # torrent token is a plasma weapon, not a flamer — exclude it.
    if _PLASMA_INCINERATOR_RE.search(name):
        return False
    return True
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
# DAEMONS-EXTRA-MELEE-MAPPER-V1 — Extra Attacks keyword. A melee weapon with
# this keyword fires IN ADDITION to the model's other melee attacks rather than
# replacing them (10e core rules, Fight phase: "[EXTRA ATTACKS] — Each time the
# bearer fights, it makes a number of attacks with this weapon equal to that
# weapon's Attacks characteristic in addition to the attacks it makes with its
# other melee weapons."). Parsed from BSData by extract_melee_weapon and
# carried on WeaponStats.extra_attacks so the mapper can collect these weapons
# into UnitProfile.extra_melee_profiles instead of silently discarding them.
# Cited as `simulator.extra_melee_profiles`.
_EXTRA_ATTACKS_RE = re.compile(r"\bExtra\s+Attacks\b", re.IGNORECASE)


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
    if _EXTRA_ATTACKS_RE.search(s):
        out["extra_attacks"] = True
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
        # PER-MODEL-LOADOUTS STAGE 1 — preserve the RAW dice expressions
        # alongside the parsed means. `a`/`d` above are already the
        # expected values; these strip-only copies keep the dice for a
        # later per-shot rolling stage. ranged-side mirror is in
        # extract_ranged_weapon.
        attacks_dice=(chars.get("A", "") or "").strip(),
        damage_dice=(chars.get("D", "") or "").strip(),
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
        # PER-MODEL-LOADOUTS STAGE 1 — preserve the RAW dice expressions
        # alongside the parsed means (see WeaponStats / extract_melee_weapon).
        attacks_dice=(chars.get("A", "") or "").strip(),
        damage_dice=(chars.get("D", "") or "").strip(),
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


def _is_crusade_only_entry(elem: ET.Element) -> bool:
    """Return True if this selectionEntry / selectionEntryGroup / entryLink
    is a narrative-campaign (Crusade) upgrade that should NOT appear in a
    matched-play loadout.

    Two signals identify Crusade-only content:

    1. **Cost shape.** A Crusade-only selectionEntry carries a positive
       ``Crusade Points`` cost while leaving the matched-play ``pts`` cost
       at 0 (or absent). A standard matched-play wargear entry has only a
       ``pts`` cost block. The diagnostic case is the Adeptus Mechanicus
       Archeotech Weapon group: Digital Cannon, Electro-fused Vambraces,
       Nanoshard Projector, Neural Jammer — each carries ``pts=0`` AND
       ``Crusade Points=1``, sits inside a ``selectionEntryGroup`` named
       "Archeotech Weapon" within the larger "Crusade" container.

    2. **Container name.** Every 10e faction file wraps its narrative
       content in a ``selectionEntryGroup name="Crusade"`` (or an entryLink
       of the same name pointing to one). Inside that container are
       sub-groups like "Legendary Archeotech" / "Battle Honours" /
       "Crusade Relics" whose individual leaf weapons do NOT carry Crusade
       Points cost blocks (the cost is implicit because the whole subtree
       is Crusade) and so would slip past the cost-shape filter alone.
       Skipping any selection at the "Crusade" name level catches those.

    Pre-fix the mapper had no Crusade discrimination at all and mapped
    Archeotech weapons onto the Archaeopter chassis as standard ranged
    profiles, fabricating ~+1 attack of free damage onto every Adeptus
    Mechanicus aircraft. The pre-fix mapper also wired Legendary Archeotech
    weapons (Syntaxik Charger, etc.) into every Mechanicus unit's wargear
    tree by reaching them through the Crusade selectionEntryGroup.

    Note: a pts cost of exactly 0 (the BSData convention for "default
    included") is fine on a normal wargear entry — it's the COMBINATION
    (pts<=0 with Crusade Points>=1) that signals Crusade-only via cost.
    """
    # Signal 2: name-based gate at the Crusade container.
    name = elem.get("name") or ""
    if name == "Crusade":
        return True
    # Signal 1: cost-shape filter on the entry itself.
    has_positive_crusade_points = False
    has_positive_pts = False
    for cost in elem.findall("./costs/cost"):
        cost_name = cost.get("name") or ""
        try:
            value = float(cost.get("value") or 0)
        except ValueError:
            continue
        if cost_name == "Crusade Points" and value > 0:
            has_positive_crusade_points = True
        elif (cost_name == "pts" or cost.get("typeId") == "points") and value > 0:
            has_positive_pts = True
    return has_positive_crusade_points and not has_positive_pts


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

    # entryLinks — carry their own infoLinks, then recurse into the target.
    # Filter out Crusade-only narrative options: their selectionEntries carry
    # a positive ``Crusade Points`` cost with ``pts<=0``, and they live in
    # max-1 selectionEntryGroups under names like "Archeotech Weapon". They
    # are matched-play-invisible upgrades and must not become default
    # wargear (see _is_crusade_only_entry docstring).
    for el in elem.findall("./entryLinks/entryLink"):
        # Skip the entryLink ITSELF if it stamps Crusade Points on the link.
        if _is_crusade_only_entry(el):
            continue
        for il in el.findall("./infoLinks/infoLink"):
            if il.get("type") != "profile":
                continue
            tgt = reg.resolve(il.get("targetId") or "")
            if tgt is not None and tgt.tag == "profile":
                _consume_profile(tgt, out, primary_name)
        target = reg.resolve(el.get("targetId") or "")
        if target is not None and not _is_crusade_only_entry(target):
            _walk(target, reg, seen, out, depth + 1, max_depth, primary_name)

    # Nested selectionEntries / groups
    for child in elem.findall("./selectionEntries/selectionEntry"):
        if _is_crusade_only_entry(child):
            continue
        _walk(child, reg, seen, out, depth + 1, max_depth, primary_name)
    for grp in elem.findall("./selectionEntryGroups/selectionEntryGroup"):
        if _is_crusade_only_entry(grp):
            continue
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
        # Skip Crusade-only narrative wargear — see _is_crusade_only_entry.
        if _is_crusade_only_entry(el):
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
        # Also reject if the entryLink resolves to a Crusade-only entry on
        # the far side (cost stamped on the target, not the link).
        resolved = reg.resolve(target_id)
        if resolved is not None and _is_crusade_only_entry(resolved):
            continue
        r, m = _resolve_weapon_target(target_id, reg)
        if r is not None:
            ranged_picks.append(r)
        if m is not None:
            melee_picks.append(m)

    # Inline child selectionEntries — Hellblasters etc. embed the Plasma
    # Incinerator profile DIRECTLY here (not via an entryLink). Treat them
    # like fixed weapons: if min>=1 or no constraint, count as carried.
    for child in model_entry.findall("./selectionEntries/selectionEntry"):
        if _is_crusade_only_entry(child):
            continue
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
                max(ranged_modes, key=lambda w: _choice_score(w))
            )
        if melee_modes:
            melee_picks.append(
                max(melee_modes, key=lambda w: _choice_score(w))
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
        if _is_crusade_only_entry(grp):
            continue
        candidates_ranged, candidates_melee = _gather_group_candidates(grp, reg)
        if candidates_ranged:
            best_r = max(candidates_ranged, key=lambda w: _choice_score(w))
            ranged_picks.append(best_r)
        if candidates_melee:
            best_m = max(candidates_melee, key=lambda w: _choice_score(w))
            melee_picks.append(best_m)

    # GSC-REGRESSION-V1 / HETERO-SQUAD-MAPPER-V2: keep only the BEST single
    # ranged weapon per model when the model carries multiple fixed ranged weapons.
    #
    # 10e core rule (Wahapedia "Shooting phase"): each model makes attacks with
    # ONE of its ranged weapons per activation. Models are never compelled to
    # split fire across multiple weapons in the same shooting phase. A model
    # carrying both a Mining laser (S10 AP-3 D=4.5) and an Autopistol (S3 AP0
    # D=1) will ALWAYS fire the mining laser in the Shooting phase; the
    # autopistol is only fired in PISTOL range during the Fight phase (10e core:
    # "[PISTOL] … can be shot while within Engagement Range of one or more
    # enemy units").
    #
    # The previous behaviour (_flatten_to_basket splits count / len(weapons))
    # gave equal basket weight to every fixed ranged weapon on the model —
    # treating the Autopistol as if it fired 50% of the time alongside the
    # Mining laser. This diluted Neophyte Hybrids' Mining laser contribution
    # from its correct ~4/20 basket share down to ~2/20 (half-weighted against
    # the Autopistol secondary), and similarly diluted Hellblasters' plasma
    # incinerators against their bolt pistols.
    #
    # Fix: if a model ends up with more than one fixed ranged weapon, keep
    # only the best by expected_damage_through_baseline. Option-group weapons
    # (from selectionEntryGroups above) are already deduplicated to one best
    # per group and are not affected.
    #
    # Pistol-only exception: if ALL ranged picks are [PISTOL] weapons
    # (i.e. the model has no primary ranged weapon and exclusively fires
    # pistols in Engagement Range), keep all of them rather than dropping
    # to a single pistol arbitrarily. This is rare but covers models like
    # the Genestealers who only carry a Rending Claws profile and no ranged.
    # Cited as `simulator.basket_best_ranged_per_model`.
    if len(ranged_picks) > 1:
        non_pistol = [w for w in ranged_picks if not w.pistol]
        if non_pistol:
            # Keep only the single best non-pistol (primary) ranged weapon.
            ranged_picks = [
                max(non_pistol, key=lambda w: _choice_score(w))
            ]
        # else: all weapons are [PISTOL]; keep all (pistol-only model).

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
    _seen: Optional[set] = None,
) -> tuple[List[WeaponStats], List[WeaponStats]]:
    """Recursively collect every weapon candidate inside a selectionEntryGroup.

    Walks: cross-referenced entryLinks (to a weapon selectionEntry OR to a
    shared choice selectionEntryGroup), inline child selectionEntries (with
    their own profile blocks), and inline nested selectionEntryGroups. Each
    leaf is a possible weapon choice — the caller picks the group's best.
    """
    if _seen is None:
        _seen = set()
    gid = id(grp)
    if gid in _seen:
        return [], []
    _seen.add(gid)

    candidates_ranged: List[WeaponStats] = []
    candidates_melee: List[WeaponStats] = []

    # 1. entryLink children — cross-reference into the shared weapon catalogue.
    for el in grp.findall("./entryLinks/entryLink"):
        if _is_crusade_only_entry(el):
            continue
        target_id = el.get("targetId") or ""
        resolved = reg.resolve(target_id)
        if resolved is not None and _is_crusade_only_entry(resolved):
            continue
        # An entryLink can resolve to a shared CHOICE GROUP (Library weapon
        # options — e.g. a Knight's "Carapace weapons" / "Main weapons" options
        # live in a linked group), not just a single weapon. Recurse so those
        # candidates are not lost (the historical bug left such slots empty,
        # stripping the main guns off Knight Tyrant / Forgefiend-class chassis).
        if el.get("type") == "selectionEntryGroup" or (
            resolved is not None and resolved.tag == "selectionEntryGroup"
        ):
            if resolved is not None:
                r_sub, m_sub = _gather_group_candidates(resolved, reg, _seen)
                candidates_ranged.extend(r_sub)
                candidates_melee.extend(m_sub)
            continue
        if el.get("type") != "selectionEntry":
            continue
        r, m = _resolve_weapon_target(target_id, reg)
        if r is not None:
            candidates_ranged.append(r)
        if m is not None:
            candidates_melee.append(m)

    # 2. inline selectionEntry children — the weapon profile is right here
    for child in grp.findall("./selectionEntries/selectionEntry"):
        if _is_crusade_only_entry(child):
            continue
        r_list, m_list = _weapons_from_inline_entry(child)
        # One inline entry can carry multiple profile modes (Plasma standard /
        # supercharge); the player picks the best, so we treat that as the
        # single candidate this entry contributes.
        if r_list:
            candidates_ranged.append(
                max(r_list, key=lambda w: _choice_score(w))
            )
        if m_list:
            candidates_melee.append(
                max(m_list, key=lambda w: _choice_score(w))
            )

    # 3. inline nested selectionEntryGroup children — flatten their candidates up
    for sub in grp.findall("./selectionEntryGroups/selectionEntryGroup"):
        if _is_crusade_only_entry(sub):
            continue
        r_sub, m_sub = _gather_group_candidates(sub, reg, _seen)
        candidates_ranged.extend(r_sub)
        candidates_melee.extend(m_sub)

    return candidates_ranged, candidates_melee


# A single choice-group OPTION: the (ranged, melee) profiles a player receives
# by taking ONE selection from the group. Either half may be None; a dual-profile
# weapon (a weapon selectionEntry that carries BOTH a Ranged and a Melee profile,
# or a combined-arm entry such as "Siege claw and rad cleanser") fills both.
WeaponOption = tuple[Optional[WeaponStats], Optional[WeaponStats]]


def _gather_group_options(
    grp: ET.Element,
    reg: Registry,
    _seen: Optional[set] = None,
) -> List[WeaponOption]:
    """Collect a selectionEntryGroup's candidate weapons AS OPTIONS, keeping
    each option's ranged and melee profiles PAIRED.

    This is the option-preserving sibling of `_gather_group_candidates` (which
    flattens every leaf into two independent ranged / melee lists). Pairing
    matters for the single-model choice-group resolver: taking ONE option from a
    `max=1` group must bring ALL of that option's profiles, never one profile
    from option A and another from option B. A dual-profile weapon — the Aeldari
    Singing Spear, the Necron Staff of light, a Knight's "siege claw and rad
    cleanser" combined arm — is one selection carrying both a ranged and a melee
    profile; it must count as ONE choice, not two competing candidates.

    Walks the same three shapes `_gather_group_candidates` does — cross-referenced
    entryLinks (to a weapon selectionEntry OR a shared choice group), inline
    child selectionEntries, and inline nested selectionEntryGroups — so the
    candidate SET is identical; only the pairing differs. Linked / nested
    sub-groups flatten their options up (each sub-option is an independent option
    of this group, mirroring the original union-of-choices behaviour)."""
    if _seen is None:
        _seen = set()
    gid = id(grp)
    if gid in _seen:
        return []
    _seen.add(gid)

    options: List[WeaponOption] = []

    # 1. entryLink children — cross-reference into the shared weapon catalogue.
    for el in grp.findall("./entryLinks/entryLink"):
        if _is_crusade_only_entry(el):
            continue
        target_id = el.get("targetId") or ""
        resolved = reg.resolve(target_id)
        if resolved is not None and _is_crusade_only_entry(resolved):
            continue
        if el.get("type") == "selectionEntryGroup" or (
            resolved is not None and resolved.tag == "selectionEntryGroup"
        ):
            if resolved is not None:
                options.extend(_gather_group_options(resolved, reg, _seen))
            continue
        if el.get("type") != "selectionEntry":
            continue
        r, m = _resolve_weapon_target(target_id, reg)
        if r is not None or m is not None:
            options.append((r, m))

    # 2. inline selectionEntry children — one entry is one option; its multiple
    #    firing modes (Plasma standard / supercharge) each collapse to the best
    #    mode of that type, and a dual-profile entry keeps both halves together.
    for child in grp.findall("./selectionEntries/selectionEntry"):
        if _is_crusade_only_entry(child):
            continue
        r_list, m_list = _weapons_from_inline_entry(child)
        best_r = (
            max(r_list, key=lambda w: _choice_score(w))
            if r_list else None
        )
        best_m = (
            max(m_list, key=lambda w: _choice_score(w))
            if m_list else None
        )
        if best_r is not None or best_m is not None:
            options.append((best_r, best_m))

    # 3. inline nested selectionEntryGroup children — flatten their options up.
    for sub in grp.findall("./selectionEntryGroups/selectionEntryGroup"):
        if _is_crusade_only_entry(sub):
            continue
        options.extend(_gather_group_options(sub, reg, _seen))

    return options


def gather_squad_loadout(entry: ET.Element, reg: Registry) -> Optional[List[ModelLoadout]]:
    """
    Build a per-model loadout list for a multi-model squad.

    Returns None if:
      - the unit has no inner squad SEG (single-model unit), OR
      - no model entries are found, OR
      - no weapons resolve on any model (the caller should fall back).

    The returned list's `count` fields SUM to the squad's max headcount.

    BSData 10e encodes squad composition across multiple selectionEntryGroup
    nodes under a single unit entry: typically one "body" group (e.g.
    "9-19 Boyz", "Tankbustas") plus one "leader" group ("Boss Nob",
    "Sybarite"). The old implementation called ``_find_main_squad_group``
    which returned the FIRST group with a size constraint — the leader group
    when it is listed first (Tankbustas, Breaka Boyz) — causing
    ``squad_max=1`` and an early bail-out to the legacy single-best-weapon
    path. The fix collects model-type selectionEntries from EVERY SEG under
    the unit entry (and from the entry itself for Guardian-Defender-style
    squads). The authoritative squad total comes from ``extract_squad_size``
    (already summing all SEGs).
    """
    # Use extract_squad_size for the total squad headcount — it already sums
    # across all selectionEntryGroups and direct model entries.
    min_m, max_m = extract_squad_size(entry)
    squad_max = max_m
    size = (min_m, max_m)

    # Collect model-type selectionEntries from every source:
    #   (a) every top-level selectionEntryGroup under the unit entry
    #   (b) direct selectionEntry type="model" children of the unit entry
    #       (Guardian Defender / Kabalite Warrior shape)
    # This replaces the previous _find_main_squad_group + single-group walk
    # that missed sibling groups (Boss Nob in Tankbustas, Sybarite in
    # Kabalite Warriors) when the leader group was listed first.
    model_entries: List[ET.Element] = []
    seen_names: set = set()

    # Shape (a): iterate ALL selectionEntryGroups, not just the first one.
    for seg in entry.findall("./selectionEntryGroups/selectionEntryGroup"):
        if _is_crusade_only_entry(seg):
            continue
        for me in seg.findall("./selectionEntries/selectionEntry"):
            name = me.get("name")
            if me.get("type") == "model" and name not in seen_names:
                model_entries.append(me)
                if name:
                    seen_names.add(name)

    # Shape (b): direct model children on the entry itself (Aeldari-derived
    # squads: Guardian Defenders, original Kabalite Warrior schema).
    for me in entry.findall("./selectionEntries/selectionEntry"):
        name = me.get("name")
        if me.get("type") == "model" and name not in seen_names:
            model_entries.append(me)
            if name:
                seen_names.add(name)

    # If no model-type entries found at all, fall back to legacy path.
    if not model_entries:
        return None

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
# PER-MODEL-LOADOUTS STAGE 1 — single-model loadout collection
# ---------------------------------------------------------------------------
#
# Single-model units (Knights, Wraithknights, most CHARACTERs and vehicles)
# encode their weapons differently from multi-model squads: instead of one
# flat "Weapon 1 / Weapon 2" choice group per model, a titanic/vehicle chassis
# wraps its weapons inside a "Wargear" CONTAINER group whose members are EITHER
#   - fixed weapons that fire simultaneously (a Knight Paladin's Rapid-fire
#     battle cannon AND Questoris heavy stubber), OR
#   - nested CHOICE groups (Left Arm / Right Arm / Carapace-mounted Weapon)
#     from which the player picks one.
#
# The signal that distinguishes the two: a CHOICE group carries a `max`
# selections constraint (pick at most N). A CONTAINER (the "Wargear" wrapper)
# carries no `max` selections constraint — its direct weapon leaves are
# simultaneous and its sub-groups are each independent choices. We walk the
# tree recursively, picking the single best option per choice group and
# collecting every fixed weapon, exactly mirroring the option-per-group logic
# `_collect_weapons_for_model` already applies to multi-model squads. This
# avoids the legacy flat weapon-walk that collected ALL of a chassis's
# mutually-exclusive arm-weapon options (Suncannon AND Heavy Wraithcannon).


def _seg_max_selections(grp: ET.Element) -> Optional[int]:
    """Return the `max` selections constraint on a group (or its linked
    target), or None when the group carries no such constraint. A real
    weapon-choice group ("Left Arm", "Carapace-mounted Weapon") always has a
    `max`; a wrapper container ("Wargear") does not. The `-1` BSData
    "unlimited" sentinel is treated as no cap (None)."""
    for cons in grp.findall("./constraints/constraint"):
        if cons.get("field") != "selections":
            continue
        if cons.get("type") != "max":
            continue
        try:
            value = int(cons.get("value") or 0)
        except ValueError:
            continue
        if value < 0:
            continue
        return value
    return None


def _best_candidate(
    candidates: List[WeaponStats],
) -> Optional[WeaponStats]:
    """Pick the single highest expected-damage weapon from a choice group's
    candidate list (the player's one pick from that group)."""
    if not candidates:
        return None
    return max(candidates, key=lambda w: _choice_score(w))


def _weapon_base_name(name: str) -> str:
    """Collapse a weapon's BSData firing-mode marker so two modes of one gun
    count as one weapon slot. BSData names the modes of a multi-mode weapon
    "➤ Ectoplasma decimator - standard" / "➤ Ectoplasma decimator - supercharge";
    both reduce to "Ectoplasma decimator". Plain weapon names pass through."""
    n = (name or "").lstrip("➤").strip()
    if " - " in n:
        n = n.split(" - ", 1)[0].strip()
    return n


def _option_expected_damage(option: WeaponOption) -> float:
    """Score a whole choice-group OPTION by the combined expected damage of its
    profiles, so ranged-only, melee-only and dual-profile options are ranked on
    one comparable expected-value basis. A dual-profile option (both a ranged and
    a melee profile) is worth the sum — that is the value of taking the one
    selection that grants both."""
    r, m = option
    total = 0.0
    if r is not None:
        total += _choice_score(r)
    if m is not None:
        total += _choice_score(m)
    return total


def _pick_group_options(
    options: List[WeaponOption], max_sel: int,
    exclude_ranged: Optional[set] = None,
    exclude_melee: Optional[set] = None,
) -> tuple[List[WeaponStats], List[WeaponStats]]:
    """Resolve ONE choice group by picking its `max_sel` best OPTIONS from the
    COMBINED (ranged + melee) candidate pool, then partitioning the winners'
    profiles back into ranged and melee.

    -- BUG CLASS FIXED: mixed-type choice-group double-equip -----------------
    The previous resolver picked a group's best RANGED candidate and its best
    MELEE candidate INDEPENDENTLY (two separate `_pick_group_weapons` calls).
    For a MIXED group — one whose options are of different weapon types, e.g. a
    Knight arm group that is "keep the Reaper chainsword (melee) OR replace it
    with a gatling / battle / thermal cannon (ranged)" — that equipped BOTH the
    melee default AND the best ranged alternative, when the `max=1` constraint
    means the player takes exactly ONE. No legal build carries both.

    Proven live cases (verified unit audit):
      * Knight Despoiler fired Daemonbreath thermal cannon + Ruinspear rocket
        pod + Daemonbreath meltagun AND fought with Warpstrike claw + Reaper
        chainsword + Titanic feet — a mix of mutually-exclusive arm options.
      * Chaos Defiler fired four ranged weapons including a baleflamer that
        REPLACES the battle-cannon slot, and carried a DUPLICATED electroscourge
        in melee.

    Scoring ranged and melee options on the same expected-damage basis and
    taking the top `max_sel` OPTIONS means a `max=1` mixed group contributes
    exactly one weapon — of whichever type won — and a ranged-only or
    melee-only group behaves exactly as before (its options are all one type,
    so the pick is unchanged). Because each option is taken whole, a
    dual-profile option contributes both its profiles as ONE selection.

    `exclude_ranged` / `exclude_melee` (base weapon names) skip profiles the
    model already carries as FIXED wargear, so a choice group that also lists a
    fixed weapon does not re-pick it (a Knight Tyrant's "Main weapons" group
    lists its fixed Warpshock harpoon, which out-ranks the volcano lance;
    without this the group re-picks the harpoon and the real main gun is lost).
    An option counts toward `max_sel` when it contributes at least one NEW
    profile of either type."""
    n = max(1, int(max_sel))
    seen_ranged: set = set(exclude_ranged) if exclude_ranged else set()
    seen_melee: set = set(exclude_melee) if exclude_melee else set()
    chosen_ranged: List[WeaponStats] = []
    chosen_melee: List[WeaponStats] = []
    picked = 0
    for r, m in sorted(options, key=_option_expected_damage, reverse=True):
        r_base = _weapon_base_name(r.name) if r is not None else None
        m_base = _weapon_base_name(m.name) if m is not None else None
        take_r = r is not None and r_base not in seen_ranged
        take_m = m is not None and m_base not in seen_melee
        # Skip an option whose every profile is already carried (a fixed-weapon
        # re-pick, or a duplicate of a weapon this group already selected).
        if not take_r and not take_m:
            continue
        if take_r:
            seen_ranged.add(r_base)
            chosen_ranged.append(r)
        if take_m:
            seen_melee.add(m_base)
            chosen_melee.append(m)
        picked += 1
        if picked >= n:
            break
    return chosen_ranged, chosen_melee


def _collect_single_model_weapons(
    node: ET.Element,
    reg: Registry,
    _seen: Optional[set] = None,
) -> tuple[List[WeaponStats], List[WeaponStats]]:
    """Recursively collect ONE single model's actual weapon loadout.

    Walks the weapon tree under `node` (a model entry or the unit entry of a
    single-model unit), reusing the same option-picking the multi-model path
    uses:

      - Fixed weapons (entryLinks / inline selectionEntries with min>=1, or
        no selection constraint at all) fire together — collect every one.
      - A CHOICE group (selectionEntryGroup, or an entryLink resolving to one,
        that carries a `max` selections constraint) contributes its `max`
        best OPTIONS, chosen by expected damage from the COMBINED ranged +
        melee pool so a mixed group's pick spans both types (see
        `_pick_group_options`).
      - A CONTAINER group ("Wargear" wrapper, no `max` constraint) is
        transparent: descend into it and classify each of its members the
        same way.

    Returns (ranged_picks, melee_picks). Unlike `_collect_weapons_for_model`,
    this does NOT collapse multiple fixed ranged weapons to a single best —
    a titanic chassis really does fire all of its weapons at once."""
    if _seen is None:
        _seen = set()
    node_id = id(node)
    if node_id in _seen:
        return [], []
    _seen.add(node_id)

    ranged_picks: List[WeaponStats] = []
    melee_picks: List[WeaponStats] = []
    # Choice-group option lists accumulate here and are resolved AFTER every
    # group at this node is seen. Each entry is (options, max_sel) for one
    # choice group, where `options` pairs each candidate's ranged / melee
    # profiles so a mixed group's `max_sel` pick spans BOTH types (see
    # `_pick_group_options` for the mixed-type double-equip bug this fixes).
    choice_groups: List[tuple[List[WeaponOption], int]] = []

    def _add_group(grp: ET.Element) -> None:
        """Classify a resolved selectionEntryGroup as choice vs container."""
        if _is_crusade_only_entry(grp):
            return
        max_sel = _seg_max_selections(grp)
        if max_sel is not None:
            # CHOICE group — record its candidate OPTIONS plus its slot count
            # (the group's `max` selections). Each group is an INDEPENDENT
            # weapon slot, resolved on its own below: a Knight's two arm groups
            # plus carapace each contribute their pick, instead of collapsing
            # to one gun. Options keep each candidate's ranged / melee profiles
            # PAIRED so a mixed group picks ONE weapon across both types.
            options = _gather_group_options(grp, reg)
            if options:
                choice_groups.append((options, max_sel))
        else:
            # CONTAINER — its direct weapon leaves are simultaneous fixed
            # weapons and its sub-groups are independent choices. Recurse.
            sub_r, sub_m = _collect_single_model_weapons(grp, reg, _seen)
            ranged_picks.extend(sub_r)
            melee_picks.extend(sub_m)

    # 1. entryLink children. Each can resolve to a weapon (selectionEntry) or
    #    to a choice/container group (selectionEntryGroup).
    for el in node.findall("./entryLinks/entryLink"):
        if _is_crusade_only_entry(el):
            continue
        link_type = el.get("type")
        target_id = el.get("targetId") or ""
        resolved = reg.resolve(target_id)
        if resolved is not None and _is_crusade_only_entry(resolved):
            continue
        if link_type == "selectionEntryGroup" or (
            resolved is not None and resolved.tag == "selectionEntryGroup"
        ):
            if resolved is not None:
                _add_group(resolved)
            continue
        if link_type != "selectionEntry":
            continue
        # selectionEntry link — a fixed weapon unless it is an OPTIONAL upgrade
        # (min < 1). Mirror _collect_weapons_for_model's fixed-weapon gate:
        # absence of a selection constraint means "carried by default".
        has_selection_constraint = False
        min_val = 0
        for cons in el.findall("./constraints/constraint"):
            if cons.get("field") != "selections":
                continue
            has_selection_constraint = True
            if cons.get("type") == "min":
                try:
                    min_val = int(cons.get("value") or 0)
                except ValueError:
                    pass
        if not has_selection_constraint:
            min_val = 1
        if min_val < 1:
            continue
        r, m = _resolve_weapon_target(target_id, reg)
        if r is not None:
            ranged_picks.append(r)
        if m is not None:
            melee_picks.append(m)

    # 2. inline selectionEntry children carrying their own weapon profiles
    #    (min>=1 == fixed). Multiple profile modes on one entry (Plasma
    #    standard / supercharge) collapse to the best mode.
    for child in node.findall("./selectionEntries/selectionEntry"):
        if _is_crusade_only_entry(child):
            continue
        if child.get("type") == "model":
            # A nested model entry — its weapons belong to that model, which
            # the caller handles separately. Skip to avoid double-counting.
            continue
        min_val = 0
        has_constraint = False
        for cons in child.findall("./constraints/constraint"):
            if cons.get("field") != "selections":
                continue
            has_constraint = True
            if cons.get("type") == "min":
                try:
                    min_val = int(cons.get("value") or 0)
                except ValueError:
                    pass
        if not has_constraint:
            min_val = 1
        if min_val < 1:
            continue
        r_modes: List[WeaponStats] = []
        m_modes: List[WeaponStats] = []
        for prof in child.findall(".//profile"):
            tn = prof.get("typeName") or ""
            if "Ranged" in tn:
                w = extract_ranged_weapon(prof)
                if w is not None:
                    r_modes.append(w)
            elif "Melee" in tn:
                w = extract_melee_weapon(prof)
                if w is not None:
                    m_modes.append(w)
        best_r = _best_candidate(r_modes)
        best_m = _best_candidate(m_modes)
        if best_r is not None:
            ranged_picks.append(best_r)
        if best_m is not None:
            melee_picks.append(best_m)

    # 3. direct selectionEntryGroup children — classify each.
    for grp in node.findall("./selectionEntryGroups/selectionEntryGroup"):
        _add_group(grp)

    # Resolve the accumulated choice groups. Each group is an INDEPENDENT
    # weapon slot and contributes its own `max`-selections best weapons. A
    # titanic chassis's two arm groups plus carapace therefore each fire, and a
    # "Secondary Weapons" group with max=2 yields its two best. Mutually-
    # exclusive options WITHIN one group still collapse to that group's best.
    #
    # Each group is resolved across its COMBINED ranged + melee option pool
    # (`_pick_group_options`), so a MIXED group — one whose `max=1` choice is
    # "keep the melee weapon OR replace it with a ranged gun" — contributes
    # exactly one weapon, of whichever type won, rather than double-equipping
    # the melee default AND the best ranged alternative (the Knight Despoiler /
    # Chaos Defiler illegal-loadout bug). A ranged-only or melee-only group is
    # unaffected: all its options are one type, so the pick is identical.
    #
    # The per-group INDEPENDENCE itself replaced an earlier union-by-shared-
    # weapon-name clustering that picked ONE weapon across every group sharing
    # any candidate name — it wrongly merged genuinely-independent slots (Left
    # Arm / Right Arm of a Wraithknight, Main / Carapace of a Knight Tyrant) and
    # stripped the main guns off ~250 multi-weapon chassis (Knights, Titans,
    # Dreadnoughts, super-heavy tanks). See tests/test_model_loadouts.py.
    fixed_bases_r = {_weapon_base_name(w.name) for w in ranged_picks}
    fixed_bases_m = {_weapon_base_name(w.name) for w in melee_picks}
    for options, max_sel in choice_groups:
        grp_r, grp_m = _pick_group_options(
            options, max_sel,
            exclude_ranged=fixed_bases_r, exclude_melee=fixed_bases_m,
        )
        ranged_picks.extend(grp_r)
        melee_picks.extend(grp_m)

    return ranged_picks, melee_picks


def _find_single_model_node(entry: ET.Element) -> ET.Element:
    """Locate the node that carries a single-model unit's weapons. When the
    unit has exactly one model-type child entry, that child is the model;
    otherwise the unit entry itself is the model (Knights / many vehicles are
    `type="model"` and hold their weapons directly on the unit entry)."""
    model_children: List[ET.Element] = []
    for seg in entry.findall("./selectionEntryGroups/selectionEntryGroup"):
        for me in seg.findall("./selectionEntries/selectionEntry"):
            if me.get("type") == "model":
                model_children.append(me)
    for me in entry.findall("./selectionEntries/selectionEntry"):
        if me.get("type") == "model":
            model_children.append(me)
    if len(model_children) == 1:
        return model_children[0]
    return entry


def _build_single_model_loadout(
    entry: ET.Element,
    reg: Registry,
    fallback_weapons: Optional[tuple[List[WeaponStats], List[WeaponStats]]] = None,
) -> Optional[List[ModelLoadout]]:
    """Build the one-model loadout for a single-model unit.

    Returns a list of exactly one ModelLoadout with `count == 1.0` carrying
    the model's ACTUAL equipped weapons, picked with the same
    option-per-choice-group logic the multi-model squad path uses (so a
    Knight's loadout has one weapon per choice group, not every alternative).

    If the option-picker resolves no weapon (rare datasheet shapes with no
    model entry / unusual wargear nesting), synthesize the loadout from the
    unit's already-resolved best weapons in `fallback_weapons` so every firing
    unit still ends with >=1 model entry holding >=1 weapon with a real
    `damage_dice`. Returns None only when there is genuinely nothing to fire."""
    node = _find_single_model_node(entry)
    ranged_picks, melee_picks = _collect_single_model_weapons(node, reg)
    name = node.get("name") or entry.get("name") or "?"
    if fallback_weapons is not None:
        # Synthesis fallback — when the option-picker resolves no weapon in a
        # given mode (a datasheet shape its group walk does not reach), use the
        # unit's flat-resolved weapons so the loadout is never empty for a unit
        # that can fire. Applied PER MODE: a Forgefiend resolves its melee but
        # not its (Hades autocannon / Ectoplasma cannon) ranged guns, and must
        # still get the ranged fallback rather than firing nothing.
        fb_r, fb_m = fallback_weapons
        if not ranged_picks and fb_r:
            ranged_picks = list(fb_r)
        if not melee_picks and fb_m:
            melee_picks = list(fb_m)
    if not ranged_picks and not melee_picks:
        return None
    return [ModelLoadout(name=name, count=1.0, ranged=ranged_picks, melee=melee_picks)]


def _build_model_loadouts(
    entry: ET.Element,
    reg: Registry,
    squad_models: Optional[List[ModelLoadout]],
    fallback_weapons: tuple[List[WeaponStats], List[WeaponStats]],
) -> List[ModelLoadout]:
    """Resolve the per-model loadouts for ANY unit, kept entirely separate
    from the aggregate-weapon path so it can never alter the synthetic
    averaged weapon (Stage 1 is additive-only).

      - Multi-model squads already have their per-model loadouts in
        `squad_models` (built by `gather_squad_loadout`) — reuse them.
      - Single-model units get a fresh one-model loadout from the
        option-per-choice-group picker, with a synthesis fallback from the
        unit's resolved best weapons.

    Returns [] only when nothing resolves (a unit with no firing weapons)."""
    if squad_models is not None:
        return squad_models
    single = _build_single_model_loadout(entry, reg, fallback_weapons=fallback_weapons)
    return single or []


def _weapon_to_dict(w: WeaponStats, include_dice: bool = False) -> Dict:
    """Serialize a WeaponStats to the flat dict shape used by
    `extra_ranged_profiles` (and, with `include_dice=True`, by the new
    per-model `model_loadouts`).

    With `include_dice=False` the output is byte-for-byte the historical
    `extra_ranged_profiles` entry — that path MUST stay identical so the
    regenerated parsed.json changes additively (only the new `model_loadouts`
    key appears). With `include_dice=True` two extra keys carry the raw BSData
    Attacks / Damage dice strings (`attacks_dice` / `damage_dice`) for a later
    per-shot rolling stage; `attacks` / `weapon_damage_per_shot` stay the
    rounded MEANS (the mean is the fallback when nothing rolls dice yet)."""
    d: Dict = {
        "weapon": w.name,
        "attacks": max(1, int(round(w.attacks))),
        "weapon_damage_per_shot": round(w.damage, 2),
        "hit_probability": round(w.hit_prob, 3),
        "ap": w.ap,
        "strength": w.strength,
        "range_inches": (
            int(re.search(r"(\d+)", w.range or "").group(1))
            if re.search(r"(\d+)", w.range or "") else 0
        ),
        "anti_keywords": dict(w.anti_keywords),
        "lethal_hits": w.lethal_hits,
        "sustained_hits": w.sustained_hits,
        "twin_linked": w.twin_linked,
        "devastating_wounds": w.devastating_wounds,
        "rapid_fire": w.rapid_fire,
        "melta": w.melta,
        "ignores_cover": w.ignores_cover,
        "heavy": w.heavy,
        "assault": w.assault,
        "torrent": w.torrent,
        "blast": w.blast,
        # MAP-MULTIFIRE-VALIDATE — Pistol exclusivity per profile (10e core
        # rule). The picker partitions extras into pistol/non-pistol groups.
        "pistol": w.pistol,
        # INDIRECT-PARITY-FIX — boolean weapon keywords that were previously
        # dropped when a weapon profile was serialized into extra_ranged_profiles.
        # When a multi-profile unit hot-swaps one of these extras in via
        # dataclasses.replace, fields absent from the swap dict are silently
        # inherited from the primary profile — so a Wyvern whose primary has
        # indirect_fire=False would fire its mortar stormshard profile without
        # the Indirect Fire keyword, causing the profile to be wall-blocked.
        # All five fields are consumed by units.py / code/simulator.py:
        #   indirect_fire  — LoS exemption + -1 to-hit vs non-visible targets
        #   one_shot       — once-per-battle gate in simulator
        #   hazardous      — d6 self-harm on activation in units.py
        #   precision      — bypasses cover vs CHARACTER targets (ranged)
        #   lance          — +1 to wound on melee if charged (melee path only,
        #                    but carried here so extras that ARE melee-mode-
        #                    swapped do not silently lose the keyword)
        "indirect_fire": w.indirect_fire,
        "one_shot": w.one_shot,
        "hazardous": w.hazardous,
        "precision": w.precision,
        "lance": w.lance,
    }
    if include_dice:
        d["attacks_dice"] = w.attacks_dice
        d["damage_dice"] = w.damage_dice
    return d


def _model_loadout_to_dict(ml: ModelLoadout) -> Dict:
    """Serialize one ModelLoadout to the dict stored in
    `MappedUnit.model_loadouts`. Each weapon carries the full
    `extra_ranged_profiles` stat shape PLUS the raw dice strings."""
    return {
        "name": ml.name,
        "count": ml.count,
        "ranged": [_weapon_to_dict(w, include_dice=True) for w in ml.ranged],
        "melee": [_weapon_to_dict(w, include_dice=True) for w in ml.melee],
    }


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
    # 10e Move characteristic in inches (parsed from BSData's "M" stat).
    # 0 = "missing" — should never reach the simulator because the
    # downstream loader / UnitProfile build is supposed to surface that as
    # a data-quality error rather than silently substituting M6.
    move: int = 0
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
    # Melee-side SUSTAINED HITS — sourced from the best-legal MELEE weapon's
    # keywords. Tracked separately from the ranged `sustained_hits` field so
    # the simulator can route by attack mode (`mode == "melee"` reads this;
    # `mode == "ranged"` reads `sustained_hits`). Without this split, a ranged
    # SUSTAINED HITS N would leak into melee resolution — the exact failure
    # mode that fabricated SUSTAINED HITS on Orks Choppa profiles in iter27.
    melee_sustained_hits: int = 0
    # Same shape as melee_sustained_hits for [LETHAL HITS] on melee weapons.
    # Wave-52 schema gap fix surfaced by DAEMONS-GREATER-COMBAT-V1: GUO's
    # Bilesword carries [LETHAL HITS] in BSData but the prior single
    # `lethal_hits` field read from the ranged primary only.
    melee_lethal_hits: bool = False
    # Wave-244 melee mode-routing — ANTI-X / DEVASTATING WOUNDS / TWIN-LINKED
    # sourced from the chosen MELEE weapon's keywords. Mirrors the melee /
    # ranged split already applied to sustained_hits and lethal_hits above.
    # Without these three fields the simulator read the ranged-primary
    # `anti_keywords` / `devastating_wounds` / `twin_linked` during the Fight
    # phase, contaminating melee resolution on ~242 units. Serialized as dicts
    # (not tuples) to match the JSON shape of the ranged-side anti_keywords /
    # anti_keyword_basket_fractions; the tuple-of-tuples hashable form is
    # produced in code.units._build_catalog. Basket fractions default 1.0 so
    # single-weapon / non-heterogeneous units keep full-keyword behaviour.
    melee_anti_keywords: dict = field(default_factory=dict)
    melee_devastating_wounds: bool = False
    melee_twin_linked: bool = False
    melee_devastating_wounds_basket_fraction: float = 1.0
    melee_anti_keyword_basket_fractions: Dict[str, float] = field(default_factory=dict)
    twin_linked: bool = False
    devastating_wounds: bool = False
    invuln_save: int = 7    # parsed from "Invulnerable Save (X+*)" infoLinks in the tree
    # Task #92: per-attack-type invuln (7 = none). Default = invuln_save so the
    # common case is unconditional; conditional datasheets (Wyches 4+ melee, Ion
    # Shield ranged-only) differ. Inert until the loader/builder + save step read them.
    invuln_save_melee: int = 7
    invuln_save_ranged: int = 7
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
    # MAP-MULTIFIRE-VALIDATE — primary ranged weapon name; surfaced for
    # the simulator's mode-group picker.
    weapon: str = ""
    # MAP-MULTIFIRE-VALIDATE — Pistol keyword on the SECONDARY profile
    # (independent of the primary's pistol flag).
    secondary_pistol: bool = False
    indirect_fire: bool = False
    one_shot: bool = False
    # Phase H — Stealth (-1 to be hit when this unit is shot at)
    stealth: bool = False
    # Lone Operative (10e core ability) — ranged attackers must be within 12"
    # to target this unit. Parsed via `extract_lone_operative` from BSData.
    lone_operative: bool = False
    # FIGHTS FIRST datasheet keyword — unit fights in the Fights First step
    # of the Fight phase (alongside chargers) rather than the Remaining
    # Combats step. Parsed via `extract_fights_first` from BSData. Cited as
    # `simulator.fights_first_keyword`. Real 10e datasheets with this
    # keyword: Wyches, Howling Banshees, Custodian Wardens, Mandrakes, etc.
    fights_first: bool = False
    # WAVE-260 — World Eaters "Blessings of Khorne" army-rule ability carrier
    # flag. True iff the datasheet carries the Blessings of Khorne ability
    # infoLink (parsed via `extract_blessings_of_khorne`). The army rule only
    # buffs "units from your army WITH THIS ABILITY", so Khorne Daemon allies
    # (Bloodletters, Flesh Hounds, Bloodcrushers) read False and are excluded
    # by the gated read in Unit.attack. Default True so non-World-Eaters units
    # (which never reach the faction-gated read) and any pre-regen profile
    # stay permissive. Cited as `simulator.blessings_of_khorne`.
    has_blessings_of_khorne: bool = True
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
    # MAP-4 — Reanimation Protocols eligibility. True iff the BSData
    # datasheet carries the "Reanimation Protocols" infoLink AND the unit's
    # keywords do not include CHARACTER, MONSTER, or VEHICLE (those keywords
    # gate the army-wide tier of the ability off per the 10e codex; the
    # bodyguard / led-by-CHARACTER override is a runtime concern handled by
    # the simulator, not the mapper). Set via `extract_reanimates_with_army`.
    # Non-Necron units stay False. Cited as `simulator.reanimation_protocols`.
    reanimates_with_army: bool = False
    unit_keywords: List[str] = field(default_factory=list)
    # Phase B — melee profile (best-legal melee weapon picked the same way)
    melee_attacks: int = 0
    melee_damage_per_shot: float = 0.0
    melee_hit_probability: float = 0.0
    melee_strength: int = 4
    melee_ap: int = 0
    melee_weapon: str = ""
    range_inches: int = 24       # primary-weapon range; melee-only => 1
    # ----- Phase 2 / iter33 — secondary RANGED weapon profile -----
    # Some datasheets carry two distinct ranged weapons whose stat lines and
    # ranges differ enough that real 10e play picks one over the other based
    # on target / range (Stormsurge Pulse Driver 72" vs Pulse Blastcannon
    # 24", Magnus Tempestus Sceptre vs Tzeentch's Firestorm, etc.). The
    # mapper picks the second-best ranged profile (by
    # expected-damage-through-baseline) and exposes it via these fields so
    # Unit.attack can compute expected damage under both and route per shot.
    # 0 in `secondary_attacks` means "no secondary profile available".
    # Cited as `simulator.multi_profile_weapon_selection`.
    secondary_attacks: int = 0
    secondary_weapon_damage_per_shot: float = 0.0
    secondary_hit_probability: float = 0.0
    secondary_ap: int = 0
    secondary_strength: int = 4
    secondary_range_inches: int = 0
    secondary_weapon: str = ""
    secondary_anti_keywords: dict = field(default_factory=dict)
    # Carry the most-impactful keywords for the secondary profile too, so the
    # picker's expected-damage estimate reflects them (Heavy, Rapid Fire,
    # Melta, Lethal/Sustained/Devastating, etc.). Booleans default False, ints
    # default 0 (same convention as primary).
    secondary_lethal_hits: bool = False
    secondary_sustained_hits: int = 0
    secondary_twin_linked: bool = False
    secondary_devastating_wounds: bool = False
    secondary_rapid_fire: int = 0
    secondary_melta: int = 0
    secondary_ignores_cover: bool = False
    secondary_heavy: bool = False
    secondary_assault: bool = False
    secondary_torrent: bool = False
    secondary_blast: bool = False
    # SEC-KEYWORD-PARITY — four boolean weapon keywords that were missing from
    # the secondary profile serialization, causing the secondary profile to
    # silently inherit the PRIMARY profile's value for each when the simulator
    # hot-swaps via dataclasses.replace. Mirrors the fix applied to
    # extra_ranged_profiles in dc4f63c (INDIRECT-PARITY-FIX). Defaults False.
    secondary_one_shot: bool = False
    secondary_hazardous: bool = False
    secondary_indirect_fire: bool = False
    secondary_precision: bool = False
    # ---- MAP-1: TERTIARY+ ranged weapon profiles ----------------------------
    # Generalises the multi-profile mapper from 2 to N. Knight Castellan fires
    # five ranged weapons in real 10e play (Volcano Lance, Plasma Decimator,
    # Twin Meltagun, Shieldbreaker Missiles, Twin Siegebreaker Cannon);
    # `weapon` + `secondary_weapon` cover the two strongest, this list carries
    # the rest (3rd, 4th, 5th, ...). Each entry is a dict with the same
    # secondary_* stat fields, plus the weapon name and an optional
    # anti_keywords mapping. The simulator's per-shot picker compares the
    # expected damage of every profile (primary + secondary + each extra)
    # against the current target / range and routes accordingly.
    # Cited as `simulator.multi_profile_weapon_selection`.
    extra_ranged_profiles: List[Dict] = field(default_factory=list)
    # ---- DAEMONS-EXTRA-MELEE-MAPPER-V1: ADDITIVE melee weapon profiles ------
    # Mirrors extra_ranged_profiles for the Fight phase. Populated by the
    # mapper for any non-heterogeneous unit whose gear.melee_weapons list
    # contains one or more weapons tagged [EXTRA ATTACKS] in BSData (i.e.
    # weapons that fire IN ADDITION to the primary melee weapon per the 10e
    # core rule). Deduplication by name prevents the same weapon appearing
    # twice when BSData lists it under multiple selection entries.
    # Heterogeneous (squad-average) units receive an empty list here; the
    # overrides layer (data/overrides.json) can fill them in if needed.
    # Cited as `simulator.extra_melee_profiles`.
    extra_melee_profiles: List[Dict] = field(default_factory=list)
    # MAP-3-FIX — basket-fraction gating for partial-coverage weapon keywords.
    # See WeaponStats for the rationale. Defaults to 1.0 preserve legacy
    # behaviour for any single-weapon unit (the keyword either fires for every
    # shot or doesn't fire at all). Heterogeneous squads (Rubric Marines, etc.)
    # land here with fractions < 1.0 so the simulator's Bernoulli gate fires
    # the keyword on a proportional subset of shots. Cited as
    # `simulator.basket_fraction_gating`.
    devastating_wounds_basket_fraction: float = 1.0
    lance_basket_fraction: float = 1.0
    anti_keyword_basket_fractions: Dict[str, float] = field(default_factory=dict)
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
    # DAMAGED-BRACKET (task #77) — the 10e "Damaged: 1-X Wounds Remaining"
    # datasheet ability, extracted per-unit from BSData so the simulator can apply
    # the REAL per-datasheet bracket to every model rather than the Knight-only
    # heuristic. `damaged_threshold == 0` means the unit has no bracket. Penalties
    # are how much each stat drops while the model is at 1..threshold wounds. v1
    # models OC + Hit (the only effects the sim applies today); attacks_penalty is
    # extracted for completeness but is 0 across all 10e brackets (verified). Move
    # degradation is deferred (not modelled). Additive data — nothing reads these
    # until the gated application stage. Cited `simulator.damaged_bracket`.
    damaged_threshold: int = 0
    damaged_oc_penalty: int = 0
    damaged_hit_penalty: int = 0
    damaged_attacks_penalty: int = 0
    # PER-MODEL-LOADOUTS STAGE 1 — per-model weapon loadouts (each model type's
    # actual equipped weapons, with raw dice strings preserved). This is the
    # ADDITIVE data the later per-model firing stage reads; nothing reads it
    # yet, so populating it does NOT change the simulator, the aggregate weapon,
    # or the eval. Serialized as a list of
    #   {"name": str, "count": float,
    #    "ranged": [weapon-dict...], "melee": [weapon-dict...]}
    # where each weapon-dict is the `extra_ranged_profiles` shape plus
    # `attacks_dice` / `damage_dice`. Declared LAST so `asdict` appends
    # `model_loadouts` after every pre-existing key (preserving key order so
    # the regenerated parsed.json differs only by this new key).
    model_loadouts: List[Dict] = field(default_factory=list)


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


# DAMAGED-BRACKET (task #77) — parse the 10e "Damaged: 1-X Wounds Remaining"
# datasheet ability. BSData encodes it as an inline Abilities profile named
# "Damaged: 1-X Wounds Remaining" whose Description reads e.g. "While this model
# has 1-5 wounds remaining, subtract 3 from this model's Objective Control
# characteristic, and each time this model makes an attack, subtract 1 from the
# Hit roll." The Hit regex anchors on "this model makes an attack" so it captures
# ONLY the offensive self-penalty and NOT the unrelated defensive "-1 to be hit"
# form ("each time an attack targets that unit ...") — the de-conflation the
# wave-190b audit proved necessary. Apostrophes vary (models / model's / model’s).
_DMG_THRESH_RE = re.compile(r"1-(\d+)\s*wounds remaining", re.IGNORECASE)
_DMG_OC_RE = re.compile(
    r"subtract\s+(\d+)\s+from this model[’'’]?s? Objective Control", re.IGNORECASE
)
_DMG_HIT_RE = re.compile(
    r"this model makes an attack,\s*subtract\s+1\s+from the Hit roll", re.IGNORECASE
)
_DMG_ATK_RE = re.compile(
    r"subtract\s+(\d+)\s+from this model[’'’]?s? Attacks", re.IGNORECASE
)


def _gather_damaged_profiles(elem: ET.Element, reg: Registry,
                             depth: int = 0, seen: Optional[set] = None) -> list:
    """Collect every "Damaged"-named Abilities profile reachable from `elem`:
    inline AND link-resolved. Many datasheets (all the mainline Imperial / Chaos
    Knights, etc.) do NOT carry the Damaged ability inline — they reference a
    SHARED "Damaged: 1-X Wounds Remaining" profile in a linked Library via an
    infoLink, so an inline-only walk misses it (the verification that caught this
    showed only 1/42 Knights extracted). We resolve infoLink / entryLink targetIds
    through the registry, mirroring the weapon-resolution walk. Bounded depth +
    seen-set guard against cycles."""
    if seen is None:
        seen = set()
    if depth > 3 or id(elem) in seen:
        return []
    seen.add(id(elem))
    out = []
    for prof in elem.findall(".//profile"):
        if (prof.get("typeName") or "") == "Abilities" and \
                (prof.get("name") or "").strip().lower().startswith("damaged"):
            out.append(prof)
    for il in elem.findall(".//infoLinks/infoLink"):
        tgt = reg.resolve(il.get("targetId") or "")
        if tgt is not None and tgt.tag == "profile" and \
                (tgt.get("typeName") or "") == "Abilities" and \
                (tgt.get("name") or "").strip().lower().startswith("damaged"):
            out.append(tgt)
    for el in elem.findall(".//entryLinks/entryLink"):
        tgt = reg.resolve(el.get("targetId") or "")
        if tgt is not None:
            out.extend(_gather_damaged_profiles(tgt, reg, depth + 1, seen))
    return out


def extract_damaged_bracket(entry: ET.Element, reg: Registry) -> tuple:
    """Return (threshold, oc_penalty, hit_penalty, attacks_penalty) for the unit's
    10e Damaged bracket. threshold == 0 means the unit has no bracket. Gathers the
    "Damaged"-named Abilities profiles reachable from `entry` (inline + link-
    resolved via `reg`) and returns the first that degrades a stat we model. A unit
    has at most one Damaged bracket on its own datasheet; the first match is its
    own."""
    for prof in _gather_damaged_profiles(entry, reg):
        desc = ""
        for ch in prof.iter("characteristic"):
            if ch.get("name") == "Description":
                desc = ch.text or ""
                break
        if not desc:
            continue
        mt = _DMG_THRESH_RE.search(desc) or _DMG_THRESH_RE.search(prof.get("name") or "")
        if not mt:
            continue
        threshold = int(mt.group(1))
        moc = _DMG_OC_RE.search(desc)
        matk = _DMG_ATK_RE.search(desc)
        oc_pen = int(moc.group(1)) if moc else 0
        hit_pen = 1 if _DMG_HIT_RE.search(desc) else 0
        atk_pen = int(matk.group(1)) if matk else 0
        if oc_pen or hit_pen or atk_pen:
            return (threshold, oc_pen, hit_pen, atk_pen)
    return (0, 0, 0, 0)


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
        best = max(gear.ranged_weapons, key=lambda w: _choice_score(w))
    else:
        best = None
    # ---- Phase 2 / iter33: pick a SECONDARY ranged weapon, distinct from
    # `best`, for the multi-profile picker in Unit.attack. We only do this on
    # the legacy single-best path — the heterogeneous squad path already
    # collapses every model's weapon into one synthetic average. Heuristic:
    # take the next-best ranged WeaponStats by expected-damage, excluding
    # anything that shares both name AND range with `best` (so we don't pick
    # the same profile twice). The "best" profile picked above is already
    # one weapon; the secondary is the runner-up of a different name.
    second_best: Optional[WeaponStats] = None
    # MAP-1: tertiary+ profiles. Cap total at 5 ranged weapons per chassis to
    # cover the worst real case (Knight Castellan = 5: Volcano Lance, Plasma
    # Decimator, Twin Meltagun, Shieldbreaker Missiles, Twin Siegebreaker
    # Cannon). Anything beyond the 5 strongest is dropped — heavier chassis
    # like the Lord of Skulls cap below this anyway.
    _MULTI_PROFILE_RANGED_CAP = 5
    extra_weapons: List[WeaponStats] = []
    if not used_heterogeneous and gear.ranged_weapons and best is not None:
        already_chosen = [best]
        # Build the ranked list of remaining distinct ranged profiles.
        remaining = [
            w for w in gear.ranged_weapons
            if w is not best
            and not (w.name == best.name and (w.range or "") == (best.range or ""))
        ]
        remaining_sorted = sorted(
            remaining,
            key=lambda w: _choice_score(w),
            reverse=True,
        )
        # De-duplicate by (name, range) so the same profile under different
        # selection-entry copies doesn't get picked twice.
        seen_keys = {(w.name, w.range or "") for w in already_chosen}
        ranked: List[WeaponStats] = []
        for w in remaining_sorted:
            k = (w.name, w.range or "")
            if k in seen_keys:
                continue
            seen_keys.add(k)
            ranked.append(w)
        if ranked:
            second_best = ranked[0]
            already_chosen.append(second_best)
            # Take up to (cap - 2) more — the 3rd, 4th, 5th profiles.
            for w in ranked[1 : _MULTI_PROFILE_RANGED_CAP - 1]:
                extra_weapons.append(w)
    if used_heterogeneous and loadout_basket_melee:
        best_melee = weighted_basket_average(loadout_basket_melee)
    elif gear.melee_weapons:
        best_melee = max(gear.melee_weapons, key=lambda w: _choice_score(w))
    else:
        best_melee = None
    # DAEMONS-EXTRA-MELEE-MAPPER-V1 — collect EXTRA ATTACKS melee weapons.
    # On the non-heterogeneous path (single-model units or fallback), any
    # melee weapon in gear.melee_weapons that carries the [EXTRA ATTACKS]
    # keyword fires IN ADDITION to the primary melee weapon in the Fight
    # phase (10e core rule). Collect them here so the mapper can populate
    # UnitProfile.extra_melee_profiles. Deduplication by name prevents the
    # same profile appearing twice when BSData lists a weapon under multiple
    # selection entries.
    # Scope: non-heterogeneous only — the heterogeneous basket-average path
    # already collapses all melee weapons into one synthetic profile and
    # the EXTRA ATTACKS semantics don't apply cleanly to averaged squads.
    # Cited as `simulator.extra_melee_profiles`.
    extra_melee_weapons: List[WeaponStats] = []
    if not used_heterogeneous and gear.melee_weapons and best_melee is not None:
        _seen_melee_names: set = {best_melee.name}
        for _w in gear.melee_weapons:
            if not _w.extra_attacks:
                continue
            if _w.name in _seen_melee_names:
                continue
            _seen_melee_names.add(_w.name)
            extra_melee_weapons.append(_w)
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
    invuln, invuln_melee, invuln_ranged = extract_invuln(entry, reg)
    unit_kw = extract_unit_keywords(entry)
    fnp = extract_fnp(entry, reg)
    stealth = extract_stealth(entry, reg)
    lone_operative = extract_lone_operative(entry, reg)
    fights_first = extract_fights_first(entry, reg)
    has_blessings_of_khorne = extract_blessings_of_khorne(entry, reg)
    deployment = extract_deployment_abilities(entry)
    deadly_demise = extract_deadly_demise(entry)
    firing_deck = extract_firing_deck(entry)
    dmg_threshold, dmg_oc_pen, dmg_hit_pen, dmg_atk_pen = extract_damaged_bracket(entry, reg)
    reanimates = extract_reanimates_with_army(entry, reg, list(unit_kw))

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
    # Parse Movement from the unit profile stat line. BSData stores "M" as a
    # string like '8"', '12"', '5'. We take the first integer. Empty / dash /
    # unparseable → 0, which is the "missing-data" signal for the loader.
    _move_match = _INT_RE.search(stats.movement or "")
    move_inches = int(_move_match.group(0)) if _move_match else 0
    # PER-MODEL-LOADOUTS STAGE 1 — resolve the per-model loadouts. Kept fully
    # separate from the aggregate path above (it never touches `best` /
    # `best_melee` / the synthetic averaged weapon), so populating it is
    # additive-only. Multi-model squads reuse `squad_models`; single-model
    # units get the option-per-choice-group loadout, with a synthesis fallback
    # from the unit's resolved best weapons so a firing unit is never empty.
    _fallback_loadout_weapons = (
        [best] if best is not None else [],
        [best_melee] if best_melee is not None else [],
    )
    model_loadout_objs = _build_model_loadouts(
        entry, reg, squad_models, _fallback_loadout_weapons
    )
    model_loadouts_dicts = [_model_loadout_to_dict(ml) for ml in model_loadout_objs]
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
        move=move_inches,
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
        # Source melee SUSTAINED HITS from the chosen melee weapon if one
        # exists. Melee-only units have primary == best_melee (the mapper
        # promotes best_melee to primary when no ranged weapon resolves, see
        # lines above), so the value lines up with primary.sustained_hits in
        # that case. For mixed units (ranged + melee) the two fields diverge
        # — exactly the bug iter28-MS1 fixes.
        melee_sustained_hits=(best_melee.sustained_hits if best_melee is not None else 0),
        # Same shape as melee_sustained_hits — source melee LETHAL HITS from
        # the chosen melee weapon when one exists. Wave-52 schema gap fix:
        # the prior single `lethal_hits` field read from the ranged primary
        # would leak ranged LETHAL HITS into melee resolution (and miss
        # melee-only LETHAL HITS like GUO's Bilesword). Mode-routed at the
        # attack-resolution site in code/units.py.
        melee_lethal_hits=(best_melee.lethal_hits if best_melee is not None else False),
        # Wave-244 melee mode-routing — source ANTI-X / DEVASTATING WOUNDS /
        # TWIN-LINKED + their basket fractions from the chosen MELEE weapon
        # (the synthetic basket-average for heterogeneous squads, the single
        # best melee weapon otherwise). best_melee is None for ranged-only
        # units; those keep the inert defaults ((), False, 1.0). These feed the
        # melee-mode guards in code/units.py so a ranged-only keyword no longer
        # leaks into the Fight phase (e.g. Wave Serpent Twin Bright Lance).
        melee_anti_keywords=(
            dict(best_melee.anti_keywords) if best_melee is not None else {}
        ),
        melee_devastating_wounds=(
            best_melee.devastating_wounds if best_melee is not None else False
        ),
        melee_twin_linked=(
            best_melee.twin_linked if best_melee is not None else False
        ),
        melee_devastating_wounds_basket_fraction=(
            best_melee.devastating_wounds_basket_fraction
            if best_melee is not None
            else 1.0
        ),
        melee_anti_keyword_basket_fractions=(
            dict(best_melee.anti_keyword_basket_fractions)
            if best_melee is not None
            else {}
        ),
        twin_linked=primary.twin_linked,
        devastating_wounds=primary.devastating_wounds,
        invuln_save=invuln,
        invuln_save_melee=invuln_melee,
        invuln_save_ranged=invuln_ranged,
        rapid_fire=primary.rapid_fire,
        melta=primary.melta,
        ignores_cover=primary.ignores_cover,
        anti_keywords=dict(primary.anti_keywords),
        # MAP-3-FIX — propagate basket fractions from the chosen primary
        # weapon. For single-weapon units / fallback (non-heterogeneous) path,
        # WeaponStats defaults to 1.0 so legacy behaviour is preserved. For
        # heterogeneous-squad units the synthetic average carries a fraction
        # < 1.0 reflecting how much of the basket weight legitimately has the
        # keyword.
        devastating_wounds_basket_fraction=primary.devastating_wounds_basket_fraction,
        # Lance is melee-only, so source from best_melee when one exists.
        lance_basket_fraction=(
            best_melee.lance_basket_fraction
            if best_melee is not None
            else primary.lance_basket_fraction
        ),
        anti_keyword_basket_fractions=dict(primary.anti_keyword_basket_fractions),
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
        # MAP-MULTIFIRE-VALIDATE — surface the primary ranged weapon name
        # so the simulator's multi-profile picker can group mode-alternates
        # (sibling weapon profiles whose names differ only by a trailing
        # mode suffix like " - focused" / " - dispersed").
        weapon=primary.name,
        # MAP-MULTIFIRE-VALIDATE — pistol flag on the SECONDARY ranged
        # profile, mirrored separately so the picker can enforce 10e
        # Pistol exclusivity per profile (not per chassis).
        secondary_pistol=(second_best.pistol if second_best is not None else False),
        indirect_fire=primary.indirect_fire,
        one_shot=primary.one_shot,
        stealth=stealth or primary.stealth,
        lone_operative=lone_operative,
        fights_first=fights_first,
        has_blessings_of_khorne=has_blessings_of_khorne,
        damaged_threshold=dmg_threshold,
        damaged_oc_penalty=dmg_oc_pen,
        damaged_hit_penalty=dmg_hit_pen,
        damaged_attacks_penalty=dmg_atk_pen,
        deep_strike=bool(deployment["deep_strike"]),
        scout_distance=int(deployment["scout_distance"]),
        infiltrator=bool(deployment["infiltrator"]),
        deadly_demise=deadly_demise,
        firing_deck=firing_deck,
        fnp=fnp,
        reanimates_with_army=reanimates,
        unit_keywords=list(unit_kw),
        melee_attacks=max(0, int(round(best_melee.attacks))) if best_melee else 0,
        melee_damage_per_shot=round(best_melee.damage, 2) if best_melee else 0.0,
        melee_hit_probability=round(best_melee.hit_prob, 3) if best_melee else 0.0,
        melee_strength=best_melee.strength if best_melee else 4,
        melee_ap=best_melee.ap if best_melee else 0,
        melee_weapon=best_melee.name if best_melee else "",
        range_inches=primary_range,
        # ---- Phase 2 / iter33 — secondary ranged profile (Stormsurge Pulse
        # Driver vs Pulse Blastcannon, etc.). `secondary_attacks > 0` is the
        # sentinel the simulator / picker checks. Unpacked from `second_best`
        # only if the legacy single-best ranged path saw a distinct runner-up.
        secondary_attacks=(
            max(1, int(round(second_best.attacks))) if second_best else 0
        ),
        secondary_weapon_damage_per_shot=(
            round(second_best.damage, 2) if second_best else 0.0
        ),
        secondary_hit_probability=(
            round(second_best.hit_prob, 3) if second_best else 0.0
        ),
        secondary_ap=second_best.ap if second_best else 0,
        secondary_strength=second_best.strength if second_best else 4,
        secondary_range_inches=(
            int(re.search(r"(\d+)", second_best.range or "").group(1))
            if second_best and re.search(r"(\d+)", second_best.range or "")
            else 0
        ),
        secondary_weapon=second_best.name if second_best else "",
        secondary_anti_keywords=(
            dict(second_best.anti_keywords) if second_best else {}
        ),
        secondary_lethal_hits=second_best.lethal_hits if second_best else False,
        secondary_sustained_hits=(
            second_best.sustained_hits if second_best else 0
        ),
        secondary_twin_linked=second_best.twin_linked if second_best else False,
        secondary_devastating_wounds=(
            second_best.devastating_wounds if second_best else False
        ),
        secondary_rapid_fire=second_best.rapid_fire if second_best else 0,
        secondary_melta=second_best.melta if second_best else 0,
        secondary_ignores_cover=(
            second_best.ignores_cover if second_best else False
        ),
        secondary_heavy=second_best.heavy if second_best else False,
        secondary_assault=second_best.assault if second_best else False,
        secondary_torrent=second_best.torrent if second_best else False,
        secondary_blast=second_best.blast if second_best else False,
        # SEC-KEYWORD-PARITY — carry the four boolean keyword fields added to
        # MappedUnit above; secondary profile silently inherited primary values
        # before this fix.
        secondary_one_shot=second_best.one_shot if second_best else False,
        secondary_hazardous=second_best.hazardous if second_best else False,
        secondary_indirect_fire=second_best.indirect_fire if second_best else False,
        secondary_precision=second_best.precision if second_best else False,
        # MAP-1: 3rd+ ranged profiles. Same fields as the secondary block,
        # one dict per profile, in expected-damage-descending order so the
        # picker sees them in priority order. Empty list = no extras.
        # Cited as `simulator.multi_profile_weapon_selection`.
        # PER-MODEL-LOADOUTS STAGE 1 — the per-weapon dict shape is now built
        # by `_weapon_to_dict` (shared with `model_loadouts`). With
        # include_dice=False the output is byte-identical to the prior inline
        # builder, keeping this field unchanged in the regenerated parsed.json.
        extra_ranged_profiles=[
            _weapon_to_dict(w, include_dice=False) for w in extra_weapons
        ],
        # DAEMONS-EXTRA-MELEE-MAPPER-V1 — ADDITIVE melee profiles for
        # weapons tagged [EXTRA ATTACKS] in BSData. Each entry fires
        # alongside the primary melee block in the same Fight phase.
        # The attack-resolution contract mirrors extra_ranged_profiles
        # minus the range_inches / ranged-only fields (pistol, assault,
        # rapid_fire, melta, torrent, blast, ignores_cover, heavy). The
        # field is NOT populated on the heterogeneous (squad-average) path;
        # units on that path receive an empty list here and the overrides
        # layer may fill it in via data/overrides.json if needed.
        # Cited as `simulator.extra_melee_profiles`.
        extra_melee_profiles=[
            {
                "weapon": w.name,
                "attacks": max(1, int(round(w.attacks))),
                "weapon_damage_per_shot": round(w.damage, 2),
                "hit_probability": round(w.hit_prob, 3),
                "ap": w.ap,
                "strength": w.strength,
                "anti_keywords": dict(w.anti_keywords),
                "lethal_hits": w.lethal_hits,
                "sustained_hits": w.sustained_hits,
                "twin_linked": w.twin_linked,
                "devastating_wounds": w.devastating_wounds,
                "lance": w.lance,
                "precision": w.precision,
                # EXTRA-MELEE-KEYWORD-PARITY — one_shot and hazardous were
                # absent from this inline dict, so they were never written into
                # extra_melee_profiles in parsed.json and the runtime swap block
                # silently inherited the primary melee profile's values. The
                # fix mirrors dc4f63c (INDIRECT-PARITY-FIX) for the melee path.
                # indirect_fire is ranged-only and intentionally omitted here.
                "one_shot": w.one_shot,
                "hazardous": w.hazardous,
            }
            for w in extra_melee_weapons
        ],
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
        model_loadouts=model_loadouts_dicts,
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
    # REGIMENT: Astra Militarum codex keyword carried by infantry and light
    # vehicle datasheets that are eligible to receive Voice of Command Orders
    # from REGIMENT-targeting Officers (e.g. Ursula Creed, Cadian Castellan,
    # Command Squads). In BSData v10.6.0 this appears as a categoryLink name
    # "Regiment" on each eligible selectionEntry. Read by
    # `code.orders._unit_satisfies_target_type` and the army-wide target pool
    # in `code.orders.dispatch_orders`. Must NOT be conflated with BATTLELINE
    # — REGIMENT/SQUADRON are codex eligibility keywords, BATTLELINE is an
    # army-construction keyword used by archetypes.py squad caps.
    # Source: BSData cache data/bsdata/cache/Imperium - Astra Militarum - Library.cat.gz
    "REGIMENT",
    # SQUADRON: Astra Militarum codex keyword carried by vehicle datasheets
    # (Leman Russ variants, Rogal Dorn, Sentinels, Chimera, etc.) that are
    # eligible to receive Voice of Command Orders from SQUADRON-targeting
    # Officers (e.g. Leman Russ Commander, Rogal Dorn Commander, Sentinel
    # Commander, Lord Solar Leontus). In BSData v10.6.0 this appears as a
    # categoryLink name "Squadron" on each eligible selectionEntry. Read by
    # `code.orders._unit_satisfies_target_type` and the army-wide target pool
    # in `code.orders.dispatch_orders`. The Flexible Command stratagem
    # (Combined Arms, 2 command points) widens the eligible set to include
    # SQUADRON targets for the round it fires.
    # Source: BSData cache data/bsdata/cache/Imperium - Astra Militarum - Library.cat.gz
    "SQUADRON",
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
         BSData-canonical encoding used by ~107 units across 27 catalogues
         (Poxwalkers, Repentia, Death Company, etc.).
      2. Scan inline ``<profile typeName="Abilities">`` directly on the unit
         whose Description characteristic contains "Feel No Pain N+". This is
         the shape used when BSData encodes the FNP threshold in the ability
         prose text rather than as a separate infoLink modifier. Only profiles
         whose name starts with "feel no pain" (case-insensitive) are matched
         to avoid pulling conditional FNP text from unrelated abilities (e.g.
         "This model has the Feel No Pain 5+ ability against mortal wounds
         only" in an enhancement or army rule that merely references the
         mechanic).
      3. Fall back to the legacy depth-limited walk that hunts for prose
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
    # (2) Inline Abilities profile on the unit whose name starts with
    # "Feel No Pain" and whose Description characteristic contains "N+".
    # Analogous to extract_invuln Shape 3. This covers BSData entries that
    # encode the FNP threshold in a named Abilities profile rather than as
    # a separate infoLink+modifier.
    for prof in entry.findall(".//profile"):
        if (prof.get("typeName") or "") != "Abilities":
            continue
        pname = (prof.get("name") or "").strip().lower()
        if not pname.startswith("feel no pain"):
            continue
        for ch in prof.iter("characteristic"):
            if ch.get("name") != "Description":
                continue
            m = _FNP_RE.search(ch.text or "")
            if m is not None:
                v = int(m.group(1))
                if 2 <= v <= 6 and v < best:
                    best = v
            break
    if best < 7:
        return best
    # (3) Legacy prose walk — catches the older shape where the threshold is
    # baked into an ability description ("This unit has the Feel No Pain 5+
    # ability."). Kept as a fallback for units that don't use the canonical
    # infoLink+modifier idiom.
    #
    # MAP-2 — prune `type="upgrade"` subtrees while walking. Enhancements
    # (e.g. Tyranid Adaptive Biology, Custodes Talons of the Emperor, Death
    # Guard Revolting Regeneration) live in BSData as ``selectionEntry
    # type="upgrade"`` blocks reachable from a unit's Enhancements
    # ``entryLink``. Their characteristic prose frequently says
    # ``"Feel No Pain N+"`` because the Enhancement grants that to the
    # bearer when taken — but it is NOT a base stat of the datasheet, and
    # was silently leaking into the base FNP for every unit that COULD
    # take the Enhancement (SC5-10 patched 12 Tyranid units via overrides
    # when this was first spotted). Skip the upgrade subtree entirely: do
    # not scan its characteristics and do not follow its links.
    #
    # Note we still recurse through ``selectionEntryGroup`` containers
    # (the Enhancements group itself is a group, not an upgrade), but
    # individual upgrade children inside it are pruned.
    seen: set = set()

    def _scan_characteristics(elem: ET.Element):
        """Scan characteristic text in `elem` and its descendants, pruning
        any subtree rooted at a ``type="upgrade"`` selectionEntry. We
        traverse manually rather than via ``.iter()`` so the prune at
        upgrade boundaries can fire."""
        nonlocal best
        for child in list(elem):
            tag = child.tag
            if tag == "selectionEntry" and (
                (child.get("type") or "").strip().lower() == "upgrade"
            ):
                # Enhancement / wargear upgrade — its prose ("Feel No
                # Pain N+") is conditional on the upgrade being taken,
                # so it must not propagate into the datasheet's BASE
                # stats. Skip this whole subtree.
                continue
            if tag == "characteristic":
                txt = (child.text or "")
                m = _FNP_RE.search(txt)
                if m:
                    v = int(m.group(1))
                    if v < best:
                        best = v
            # Descend into any other child element (profiles, groups,
            # nested model selectionEntries, characteristics container,
            # etc.) so the iter("characteristic") behaviour is preserved
            # everywhere except the upgrade prune.
            _scan_characteristics(child)

    def _collect_links(elem: ET.Element):
        """Yield (infoLinks, entryLinks) from `elem`'s subtree, pruning any
        ``type="upgrade"`` selectionEntry the same way ``_scan_characteristics``
        does. The legacy code used ``.//infoLink`` which recursed through
        upgrade subtrees and followed THEIR targetIds — that was the second
        leak path for Enhancement-granted FNP."""
        infolinks: list = []
        entrylinks: list = []
        def _recurse(node: ET.Element):
            for child in list(node):
                if (
                    child.tag == "selectionEntry"
                    and (child.get("type") or "").strip().lower() == "upgrade"
                ):
                    continue
                if child.tag == "infoLink":
                    infolinks.append(child)
                elif child.tag == "entryLink":
                    entrylinks.append(child)
                _recurse(child)
        _recurse(elem)
        return infolinks, entrylinks

    def walk(elem: ET.Element, depth: int):
        if depth > 3:
            return
        # Skip upgrade subtrees entirely. The root call passes the unit's
        # datasheet selectionEntry (type="unit" / "model") so the gate
        # only fires when we follow a link INTO an upgrade target.
        if (elem.get("type") or "").strip().lower() == "upgrade":
            return
        eid = elem.get("id")
        if eid:
            if eid in seen:
                return
            seen.add(eid)
        _scan_characteristics(elem)
        infolinks, entrylinks = _collect_links(elem)
        for il in infolinks:
            tgt = reg.resolve(il.get("targetId") or "")
            if tgt is not None:
                walk(tgt, depth + 1)
        for el in entrylinks:
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
       "1", "2", "3", "D3", "D6", "D3+3", "D6+2", "D6+3"
    Returns 0 if unrecognised. Mapping:
       integer N -> N
       "D3"      -> 2   (expected value)
       "D6"      -> 3   (expected value, rounded down from 3.5)
       "D3+3"    -> 5   (E[D3] + 3 = 2 + 3)
       "D6+2"    -> 5   (E[D6] + 2 = 3.5 + 2 = 5.5, rounded down to 5)
       "D6+3"    -> 6   (E[D6] + 3 = 3.5 + 3 = 6.5, rounded down to 6)

    Note: "D6+2" was previously unhandled and fell through to 0, then to the
    no-suffix fallback (returns 1). Affects Knight Castellan, Knight Valiant,
    all Cerastus Knights (IK/CK), Knight Tyrant, Baneblade-class super-heavies,
    Stormsurge, Khorne Lord of Skulls, and others. Fixed 2026-05-30.
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
    if su == "D6+2":
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


_EXCLUSION_PROSE_RE = re.compile(
    r"(cannot use|does not have|never gains?|loses)[^.]{0,80}Reanimation Protocols",
    re.IGNORECASE,
)


def extract_reanimates_with_army(
    entry: ET.Element, reg: Registry, unit_keywords: List[str]
) -> bool:
    """True iff the unit benefits from the army-wide Reanimation Protocols
    tier. Detection has three gates:

      1. The datasheet carries an `<infoLink name="Reanimation Protocols">`
         direct child of its `<infoLinks>` block. BSData uses this shape on
         every Necron datasheet that has the ability — including some that
         the printed codex excludes via keyword. The keyword gate (next)
         filters those out.
      2. No CHARACTER, MONSTER, or VEHICLE keyword on the unit. Per Wahapedia
         10e Necrons Reanimation Protocols:
         https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols
         the ability text excludes CHARACTER / MONSTER / VEHICLE models from
         regaining wounds. Bodyguarded characters joining a reanimating unit
         are a runtime concern (leader attachment), not a per-unit flag.
      3. No exclusion prose like "This unit cannot use its Reanimation
         Protocols ability" in any of the unit's own profile / characteristic
         text. Catches the (rare) data entries that disable the ability
         outright via a sub-profile.

    Returns False for any non-Necron unit (no RP infoLink → fails gate 1).
    Cited as `simulator.reanimation_protocols`.
    """
    has_rp_infolink = False
    for il_block in entry.findall("./infoLinks"):
        for il in il_block.findall("./infoLink"):
            if (il.get("name") or "").strip().lower() == "reanimation protocols":
                has_rp_infolink = True
                break
        if has_rp_infolink:
            break
    if not has_rp_infolink:
        return False
    # Keyword gate — uppercase normalise.
    kws_upper = {(k or "").upper() for k in (unit_keywords or [])}
    if kws_upper & {"CHARACTER", "MONSTER", "VEHICLE"}:
        return False
    # Exclusion-prose gate. Scan this unit's own profile/characteristic text.
    for ch in entry.findall(".//characteristic"):
        if ch.text and _EXCLUSION_PROSE_RE.search(ch.text):
            return False
    return True


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


def extract_fights_first(entry: ET.Element, reg: Registry) -> bool:
    """True iff the unit has the FIGHTS FIRST datasheet keyword.

    Per Wahapedia 10e core rules (Fight phase, "Fights First" step:
    https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#The-Fight-Phase):
    "All eligible units that have the FIGHTS FIRST ability must fight in
    the Fights First step. Then, in the Remaining Combats step, all other
    eligible units fight." Datasheets carrying this keyword (Wyches,
    Howling Banshees, Custodian Wardens, Mandrakes, etc.) gain the
    benefit every Fight phase — not just on the turn they charged.

    BSData publishes FIGHTS FIRST in two structural shapes — a shared-rule
    infoLink named "Fights First" attached to the datasheet, or an inline
    profile named "Fights First". A handful of datasheets only mention the
    phrase in the unit's "Abilities" characteristic prose ("This unit has
    the FIGHTS FIRST ability."); detect that as a fallback. Detection
    mirrors `extract_stealth` / `extract_lone_operative` for the
    structured shapes, then adds prose scanning for the third shape.
    Cited as `simulator.fights_first_keyword`.
    """
    for il in entry.findall(".//infoLink"):
        if (il.get("name") or "").strip().lower() == "fights first":
            return True
    for prof in entry.findall(".//profile"):
        if (prof.get("name") or "").strip().lower() == "fights first":
            return True
    # Prose fallback — some datasheets inline the keyword in their
    # Abilities characteristic text rather than via a structured
    # infoLink. Match the exact uppercase keyword to avoid false
    # positives from descriptive sentences.
    for ch in entry.findall(".//characteristic"):
        if ch.text and "FIGHTS FIRST" in ch.text:
            return True
    return False


def extract_blessings_of_khorne(entry: ET.Element, reg: Registry) -> bool:
    """True iff the datasheet carries the World Eaters "Blessings of Khorne"
    army-rule ability.

    WAVE-260 over-credit fix (docs/OVERPOLE_UNIT_AUDIT.md rank 2). The
    Blessings of Khorne army rule applies its activated Blessings only to
    "all units from your army WITH THIS ABILITY" — i.e. only to datasheets
    that actually carry the Blessings of Khorne ability. World Eaters lists
    can field Khorne Daemon allies (Bloodletters, Flesh Hounds,
    Bloodcrushers) which do NOT carry the ability and so do NOT benefit. The
    simulator's three Blessing legs (melee LETHAL HITS / SUSTAINED HITS /
    AP+1) previously gated on `p.faction == 'World Eaters'` alone, over-
    crediting those daemon allies.

    BSData publishes Blessings of Khorne as a shared-rule infoLink named
    "Blessings of Khorne" attached to each eligible datasheet (verified in
    data/bsdata/cache/Chaos - World Eaters.cat.gz — ~30 native World Eaters
    datasheets carry it; the three daemon-ally datasheets do not). Detection
    mirrors `extract_lone_operative` / `extract_fights_first`: scan the
    structured infoLink / profile shapes only, never free-form prose. Cited
    as `simulator.blessings_of_khorne`.
    """
    for il in entry.findall(".//infoLink"):
        if (il.get("name") or "").strip().lower() == "blessings of khorne":
            return True
    for prof in entry.findall(".//profile"):
        if (prof.get("name") or "").strip().lower() == "blessings of khorne":
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
#
# Task #92 does exactly that. `_parse_invuln_per_attack` (below) generalises the
# single-value parse into (melee, ranged) so 10e CONDITIONAL invulns model
# faithfully — Wyches "6+ Invulnerable save, 4+ against melee attacks" ->
# (melee 4, ranged 6); the Ion Shield "5+ against ranged attacks" ->
# (melee none=7, ranged 5). 58 such clauses span 14 faction files, so the
# single-value model wrongly grants ranged-only invulns in melee. The single
# `extract_invuln` value is kept unchanged for back-compat; the per-attack
# values are extracted in parallel from the same Shape-2/3 descriptions.
_INVULN_PER_ATTACK_RE = re.compile(
    # Two canonical BSData phrasings for a per-attack invulnerable save clause.
    # Group names:
    #   pre  — digit-first form:  "4+ invulnerable save"
    #   post — post-of form:      "invulnerable save of 4+"
    #   qual — optional qualifier: "against (melee|ranged) attacks"
    r"(?:(?P<pre>\d)\+\s*[Ii]nvulnerable\s+[Ss]ave"
    r"|[Ii]nvulnerable\s+[Ss]ave\s+of\s+(?P<post>\d)\+)"
    r"(?:\s+against\s+(?P<qual>melee|ranged)\s+attacks)?",
    re.IGNORECASE,
)


def _parse_invuln_per_attack(desc: str) -> Tuple[int, int]:
    """Parse ALL invulnerable-save clauses in a Description WITH their attack-type
    qualifiers. Returns (melee, ranged) as the best (lowest) value each; 7 = none.

    Unqualified clauses apply to both attack types; "against melee attacks" /
    "against ranged attacks" qualify. Each attack type takes the best (lowest) of
    the unconditional value and its own qualified values.
    """
    if not desc:
        return (7, 7)
    uncond: List[int] = []
    melee: List[int] = []
    ranged: List[int] = []
    for m in _INVULN_PER_ATTACK_RE.finditer(desc):
        v = int(m.group("pre") or m.group("post"))
        q = (m.group("qual") or "").lower()
        if q == "melee":
            melee.append(v)
        elif q == "ranged":
            ranged.append(v)
        else:
            uncond.append(v)
    # Bare-digit fallback: a linked profile whose Description is just "4+" (no
    # prose) is always an unconditional invulnerable save — the profile name
    # "Invulnerable Save" already supplies the context.  This covers the Shape-2
    # and Shape-3 groups (Black Templars Terminators, Adeptus Mechanicus vehicles,
    # Dark Angels characters, and ~90 other datasheets) where BSData stores only
    # the bare save value in the Description field.
    if not uncond and not melee and not ranged:
        mb = _INVULN_BARE_RE.match(desc.strip())
        if mb:
            v = int(mb.group(1))
            uncond.append(v)
    base = min(uncond) if uncond else None
    pool_m = ([base] if base is not None else []) + melee
    pool_r = ([base] if base is not None else []) + ranged
    return (min(pool_m) if pool_m else 7, min(pool_r) if pool_r else 7)


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


def extract_invuln(entry: ET.Element, reg: Registry) -> Tuple[int, int, int]:
    """
    Find the best invulnerable save on a unit by scanning for three shapes:

      1. An infoLink whose own name carries the digit ("Invulnerable Save (4+*)")
         — historical shape, e.g. Genestealer Cults Patriarch.
      2. An infoLink whose name is the bare "Invulnerable Save" and the digit
         lives in the LINKED profile's Description characteristic — the shape
         used by Adeptus Custodes (all 31 datasheets), Adeptus Mechanicus,
         Terminator squads, Sanguinary Guard, Marneus Calgar etc. Discovered
         missing in May 2026 Phase 3 defensive audit.
      3. An inline <profile typeName="Abilities"> directly on the selection
         entry whose name starts with "invulnerable save" (case-insensitive,
         covers bare and parenthesised forms like "Invulnerable Save (Yvraine)"),
         with the digit in its Description characteristic. Used by Chaos
         Daemons Library, Dark Angels, Library - Titans, Deathwatch, and
         several Aeldari characters — surfaced across the wave 47 stale-faction
         audit batches (5 catalogues, 20+ correction entries before this fix).

    The Shape 3 name filter is narrower than "any profile that mentions an
    invulnerable save in its text" because the wave-47 audits found enough
    abilities that conditionally reference invuln digits ("...gains a 5+
    invulnerable save when X...") that a description-only match would over-
    grant invulns to units that don't actually have one. Anchoring on
    "invulnerable save" as a prefix of the profile's own name keeps the
    match high-confidence while still covering character-named forms.

    Returns the best (lowest) value found, or 7 if none.
    """
    best = 7
    m_best = 7   # Task #92: per-attack best (melee), 7 = none
    r_best = 7   # Task #92: per-attack best (ranged)
    seen: set = set()
    def _consume(melee: int, ranged: int) -> None:
        nonlocal m_best, r_best
        if melee < m_best:
            m_best = melee
        if ranged < r_best:
            r_best = ranged
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
                _consume(v, v)  # name-digit invuln is unconditional
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
                _consume(*_parse_invuln_per_attack(ch.text or ""))
                break
        # Shape 3: inline <profile typeName="Abilities"> on this entry whose
        # name starts with "invulnerable save".
        for prof in elem.findall(".//profile"):
            if (prof.get("typeName") or "") != "Abilities":
                continue
            pname = (prof.get("name") or "").strip().lower()
            if not pname.startswith("invulnerable save"):
                continue
            for ch in prof.iter("characteristic"):
                if ch.get("name") != "Description":
                    continue
                v = _parse_invuln_from_description(ch.text or "")
                if v is not None and v < best:
                    best = v
                _consume(*_parse_invuln_per_attack(ch.text or ""))
                break
        for el in elem.findall("./entryLinks/entryLink"):
            target = reg.resolve(el.get("targetId") or "")
            if target is not None:
                walk(target, depth + 1)
    walk(entry, 0)
    return best, m_best, r_best


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
