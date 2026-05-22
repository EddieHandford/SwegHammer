"""
Merge parsed BSData stats with hand-tuned overrides, producing the SwegHammer
unit catalogue.

Lookup order for each unit:
  1. data/bsdata/parsed.json — base stats derived from BSData
  2. data/overrides.json     — per-unit modifications (any subset of fields)

Overrides are keyed by the canonical slug (`key`) emitted by the mapper, e.g.
`ultramarines_tactical_squad`. They can:
  - override any stat (health, damage, hit_probability, ap, save, name)
  - flip `enabled` to gate units in or out of the catalogue
  - add `notes` for documentation

Overrides can also define units that DON'T exist in parsed.json (entirely
hand-rolled). Those entries must include all required fields.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PARSED_PATH = REPO_ROOT / "data" / "bsdata" / "parsed.json"
OVERRIDES_PATH = REPO_ROOT / "data" / "overrides.json"
CALIBRATED_PATH = REPO_ROOT / "data" / "calibrated_points.json"


@dataclass
class CatalogEntry:
    key: str
    name: str
    health: float
    damage: float
    hit_probability: float
    ap: int
    save: int
    codex: str = ""
    points_listed: float = 0.0
    min_models: int = 1
    max_models: int = 1
    strength: int = 4
    toughness: int = 4
    leadership: int = 7
    oc: int = 1
    attacks: int = 1
    weapon_damage_per_shot: float = 0.0
    lethal_hits: bool = False
    sustained_hits: int = 0
    # Melee-side SUSTAINED HITS — sourced from the best-legal MELEE weapon by
    # the mapper. Routed separately from `sustained_hits` (ranged-side) so
    # the simulator can pick the correct value per attack mode. See
    # MappedUnit.melee_sustained_hits for the iter28-MS1 rationale.
    melee_sustained_hits: int = 0
    twin_linked: bool = False
    devastating_wounds: bool = False
    invuln_save: int = 7
    rapid_fire: int = 0
    melta: int = 0
    ignores_cover: bool = False
    anti_keywords: Optional[Dict[str, int]] = None
    heavy: bool = False
    assault: bool = False
    torrent: bool = False
    hazardous: bool = False
    blast: bool = False
    # Phase F — niche 10e keywords
    lance: bool = False
    precision: bool = False
    pistol: bool = False
    # MAP-MULTIFIRE-VALIDATE — primary ranged weapon name (mapper's
    # `primary.name`). Surfaced on UnitProfile so the multi-profile picker
    # can group mode-alternates by stripped root name. Default "" =
    # legacy entries that predate the field.
    weapon: str = ""
    # MAP-MULTIFIRE-VALIDATE — pistol flag on the SECONDARY ranged weapon
    # profile (the primary's flag lives in `pistol` above). 10e Pistol
    # exclusivity is enforced in the picker; this flag tells the picker
    # whether the secondary belongs to the pistol group or the non-pistol
    # group of this chassis.
    secondary_pistol: bool = False
    indirect_fire: bool = False
    one_shot: bool = False
    # Phase H — Stealth (-1 to be hit)
    stealth: bool = False
    # Lone Operative (10e core ability) — can only be targeted by ranged
    # attacks from within 12". Parsed from BSData "Lone Operative" infoLinks.
    lone_operative: bool = False
    # FIGHTS FIRST datasheet keyword — unit fights in the Fights First step
    # of the Fight phase. Parsed from BSData "Fights First" infoLinks /
    # inline profiles. Cited as `simulator.fights_first_keyword`.
    fights_first: bool = False
    # Phase I — deployment abilities
    deep_strike: bool = False
    scout_distance: int = 0
    infiltrator: bool = False
    # Deadly Demise X — when destroyed, roll 1D6; on 6, each unit within 6"
    # suffers X mortal wounds. Integer expected-value of the codex text.
    deadly_demise: int = 0
    # Firing Deck X (10e core, TRANSPORT keyword) — up to X embarked passenger
    # models may shoot using the transport's BS in its Shooting phase. 0 = none.
    firing_deck: int = 0
    fnp: int = 7
    # 10e Sticky Objectives — control persists after the unit leaves until
    # an opposing unit takes the objective back.
    sticky_objective: bool = False
    # 10e datasheet ability — Resolute Will (Custodian Wardens). Defender-
    # side -1 to Wound roll while led by a CHARACTER AND attacker S >
    # defender T. Set per-unit via overrides.json (BSData v10.6.0 mapper
    # does not yet parse this rule out of the cache; the override is the
    # authoritative source). Cited as `simulator.resolute_will`.
    resolute_will: bool = False
    # MAP-4 — per-unit Reanimation Protocols eligibility flag. True iff the
    # BSData datasheet carries the "Reanimation Protocols" infoLink AND lacks
    # CHARACTER / MONSTER / VEHICLE keywords (those keywords gate the ability
    # off per the 10e codex rule). Populated by the mapper from
    # `extract_reanimates_with_army`. Necron-specific; non-Necron units stay
    # False. Cited as `simulator.reanimation_protocols`.
    reanimates_with_army: bool = False
    unit_keywords: Optional[List[str]] = None
    melee_attacks: int = 0
    melee_damage_per_shot: float = 0.0
    melee_hit_probability: float = 0.0
    melee_strength: int = 4
    melee_ap: int = 0
    melee_weapon: str = ""
    range_inches: int = 24
    # Phase 2 / iter33 — secondary RANGED weapon profile. See
    # MappedUnit.secondary_attacks for the rationale (Stormsurge Pulse Driver
    # vs Pulse Blastcannon, etc.). 0 in secondary_attacks = "no secondary".
    secondary_attacks: int = 0
    secondary_weapon_damage_per_shot: float = 0.0
    secondary_hit_probability: float = 0.0
    secondary_ap: int = 0
    secondary_strength: int = 4
    secondary_range_inches: int = 0
    secondary_weapon: str = ""
    secondary_anti_keywords: Optional[Dict[str, int]] = None
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
    # MAP-1: TERTIARY and beyond ranged profiles. List of dicts, each carrying
    # the same fields as the secondary block (weapon, attacks, damage,
    # hit_probability, ap, strength, range_inches, anti_keywords, plus the
    # ranged keyword flags). Empty = no extras. See MappedUnit comment.
    extra_ranged_profiles: Optional[List[Dict[str, Any]]] = None
    # MAP-3-FIX — basket-fraction gating for partial-coverage weapon keywords.
    # Defaults to 1.0 preserve legacy single-weapon behaviour. Heterogeneous
    # squads (Rubric Marines, Skyweavers, Beast Snagga Boyz) carry values
    # < 1.0 so Unit.attack can Bernoulli-gate keyword consumption per shot.
    devastating_wounds_basket_fraction: float = 1.0
    lance_basket_fraction: float = 1.0
    anti_keyword_basket_fractions: Optional[Dict[str, float]] = None
    # 10e Movement characteristic (inches). 0 = use UnitProfile default (6.0).
    # Most BSData datasheets don't expose M numerically to the mapper, so this
    # is typically set via overrides.json (e.g. Vertus Praetors M=14"). Cited
    # per-unit in overrides.json notes.
    move: float = 0.0
    points_override: float = 0.0
    # Renderer-only model base footprint (see UnitProfile.base_shape).
    base_shape: str = "circle"
    base_diameter_mm: int = 32
    base_width_mm: int = 32
    base_length_mm: int = 32
    loadout: Optional[List[str]] = None
    notes: str = ""
    enabled: bool = True
    skip_reason: str = ""

    @classmethod
    def from_dict(cls, d: Dict) -> "CatalogEntry":
        return cls(
            key=d["key"],
            name=d.get("name", d["key"]),
            health=float(d.get("health", 0)),
            damage=float(d.get("damage", 0)),
            hit_probability=float(d.get("hit_probability", 0)),
            ap=int(d.get("ap", 0)),
            save=int(d.get("save", 7)),
            codex=d.get("codex", ""),
            points_listed=float(d.get("points_listed", 0)),
            min_models=int(d.get("min_models", 1)),
            max_models=int(d.get("max_models", 1)),
            strength=int(d.get("strength", 4)),
            toughness=int(d.get("toughness", 4)),
            leadership=int(d.get("leadership", 7)),
            oc=int(d.get("oc", 1)),
            attacks=int(d.get("attacks", 1)),
            weapon_damage_per_shot=float(d.get("weapon_damage_per_shot", 0)),
            lethal_hits=bool(d.get("lethal_hits", False)),
            sustained_hits=int(d.get("sustained_hits", 0)),
            melee_sustained_hits=int(d.get("melee_sustained_hits", 0)),
            twin_linked=bool(d.get("twin_linked", False)),
            devastating_wounds=bool(d.get("devastating_wounds", False)),
            invuln_save=int(d.get("invuln_save", 7)),
            rapid_fire=int(d.get("rapid_fire", 0)),
            melta=int(d.get("melta", 0)),
            ignores_cover=bool(d.get("ignores_cover", False)),
            anti_keywords=dict(d.get("anti_keywords") or {}),
            heavy=bool(d.get("heavy", False)),
            assault=bool(d.get("assault", False)),
            torrent=bool(d.get("torrent", False)),
            hazardous=bool(d.get("hazardous", False)),
            blast=bool(d.get("blast", False)),
            lance=bool(d.get("lance", False)),
            precision=bool(d.get("precision", False)),
            pistol=bool(d.get("pistol", False)),
            weapon=str(d.get("weapon", "")),
            secondary_pistol=bool(d.get("secondary_pistol", False)),
            indirect_fire=bool(d.get("indirect_fire", False)),
            one_shot=bool(d.get("one_shot", False)),
            stealth=bool(d.get("stealth", False)),
            lone_operative=bool(d.get("lone_operative", False)),
            fights_first=bool(d.get("fights_first", False)),
            deep_strike=bool(d.get("deep_strike", False)),
            scout_distance=int(d.get("scout_distance", 0)),
            infiltrator=bool(d.get("infiltrator", False)),
            deadly_demise=int(d.get("deadly_demise", 0)),
            firing_deck=int(d.get("firing_deck", 0)),
            fnp=int(d.get("fnp", 7)),
            sticky_objective=bool(d.get("sticky_objective", False)),
            resolute_will=bool(d.get("resolute_will", False)),
            reanimates_with_army=bool(d.get("reanimates_with_army", False)),
            unit_keywords=list(d.get("unit_keywords") or []),
            melee_attacks=int(d.get("melee_attacks", 0)),
            melee_damage_per_shot=float(d.get("melee_damage_per_shot", 0)),
            melee_hit_probability=float(d.get("melee_hit_probability", 0)),
            melee_strength=int(d.get("melee_strength", 4)),
            melee_ap=int(d.get("melee_ap", 0)),
            melee_weapon=d.get("melee_weapon", ""),
            range_inches=int(d.get("range_inches", 24)),
            secondary_attacks=int(d.get("secondary_attacks", 0)),
            secondary_weapon_damage_per_shot=float(d.get("secondary_weapon_damage_per_shot", 0)),
            secondary_hit_probability=float(d.get("secondary_hit_probability", 0)),
            secondary_ap=int(d.get("secondary_ap", 0)),
            secondary_strength=int(d.get("secondary_strength", 4)),
            secondary_range_inches=int(d.get("secondary_range_inches", 0)),
            secondary_weapon=d.get("secondary_weapon", ""),
            secondary_anti_keywords=dict(d.get("secondary_anti_keywords") or {}),
            secondary_lethal_hits=bool(d.get("secondary_lethal_hits", False)),
            secondary_sustained_hits=int(d.get("secondary_sustained_hits", 0)),
            secondary_twin_linked=bool(d.get("secondary_twin_linked", False)),
            secondary_devastating_wounds=bool(d.get("secondary_devastating_wounds", False)),
            secondary_rapid_fire=int(d.get("secondary_rapid_fire", 0)),
            secondary_melta=int(d.get("secondary_melta", 0)),
            secondary_ignores_cover=bool(d.get("secondary_ignores_cover", False)),
            secondary_heavy=bool(d.get("secondary_heavy", False)),
            secondary_assault=bool(d.get("secondary_assault", False)),
            secondary_torrent=bool(d.get("secondary_torrent", False)),
            secondary_blast=bool(d.get("secondary_blast", False)),
            # MAP-1: list of tertiary+ ranged profiles. Each is a dict mirroring
            # the secondary_* fields. Missing key = no extras (most units).
            extra_ranged_profiles=list(d.get("extra_ranged_profiles") or []),
            # MAP-3-FIX — parse basket fractions. Missing key = 1.0 (legacy:
            # any unit predating this change keeps full-keyword behaviour).
            devastating_wounds_basket_fraction=float(
                d.get("devastating_wounds_basket_fraction", 1.0)
            ),
            lance_basket_fraction=float(d.get("lance_basket_fraction", 1.0)),
            anti_keyword_basket_fractions=dict(
                d.get("anti_keyword_basket_fractions") or {}
            ),
            move=float(d.get("move", 0)),
            points_override=float(d.get("points_override", 0)),
            base_shape=str(d.get("base_shape", "circle")),
            base_diameter_mm=int(d.get("base_diameter_mm", 32)),
            base_width_mm=int(d.get("base_width_mm", 32)),
            base_length_mm=int(d.get("base_length_mm", 32)),
            loadout=d.get("loadout") or [],
            notes=d.get("notes", ""),
            enabled=bool(d.get("enabled", True)),
            skip_reason=d.get("skip_reason", ""),
        )


def _load_parsed() -> Dict[str, CatalogEntry]:
    if not PARSED_PATH.exists():
        return {}
    payload = json.loads(PARSED_PATH.read_text(encoding="utf-8"))
    out: Dict[str, CatalogEntry] = {}
    for u in payload.get("units", []):
        entry = CatalogEntry.from_dict(u)
        out[entry.key] = entry
    return out


def _load_overrides() -> Dict[str, Dict]:
    if not OVERRIDES_PATH.exists():
        return {}
    payload = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return payload.get("units", {})


def _load_calibrated_overrides() -> Dict[str, Dict]:
    """
    Read data/calibrated_points.json (written by code/balancer.py) and shape
    its `balanced_points` values into the same {unit_key: {points_override: N}}
    layout used by overrides.json. Skips entries whose calibration didn't
    converge so unreliable values don't pollute the live catalogue.
    """
    if not CALIBRATED_PATH.exists():
        return {}
    payload = json.loads(CALIBRATED_PATH.read_text(encoding="utf-8"))
    out: Dict[str, Dict] = {}
    for key, record in payload.get("units", {}).items():
        if not record.get("converged"):
            continue
        balanced = float(record.get("balanced_points") or 0)
        if balanced <= 0:
            continue
        out[key] = {"points_override": balanced}
    return out


def _apply_override(base: Optional[CatalogEntry], override: Dict, key: str) -> CatalogEntry:
    """Apply an override dict to a base entry, or create a new entry from scratch."""
    if base is None:
        # Fresh entry from overrides only — fields must be present
        return CatalogEntry.from_dict({"key": key, **override})

    merged = {
        "key": base.key,
        "name": override.get("name", base.name),
        "health": override.get("health", base.health),
        "damage": override.get("damage", base.damage),
        "hit_probability": override.get("hit_probability", base.hit_probability),
        "ap": override.get("ap", base.ap),
        "save": override.get("save", base.save),
        "codex": override.get("codex", base.codex),
        "points_listed": override.get("points_listed", base.points_listed),
        "min_models": override.get("min_models", base.min_models),
        "max_models": override.get("max_models", base.max_models),
        "strength": override.get("strength", base.strength),
        "toughness": override.get("toughness", base.toughness),
        "leadership": override.get("leadership", base.leadership),
        "oc": override.get("oc", base.oc),
        "attacks": override.get("attacks", base.attacks),
        "weapon_damage_per_shot": override.get("weapon_damage_per_shot", base.weapon_damage_per_shot),
        "lethal_hits": override.get("lethal_hits", base.lethal_hits),
        "sustained_hits": override.get("sustained_hits", base.sustained_hits),
        "melee_sustained_hits": override.get("melee_sustained_hits", base.melee_sustained_hits),
        "twin_linked": override.get("twin_linked", base.twin_linked),
        "devastating_wounds": override.get("devastating_wounds", base.devastating_wounds),
        "invuln_save": override.get("invuln_save", base.invuln_save),
        "rapid_fire": override.get("rapid_fire", base.rapid_fire),
        "melta": override.get("melta", base.melta),
        "ignores_cover": override.get("ignores_cover", base.ignores_cover),
        "anti_keywords": override.get("anti_keywords", base.anti_keywords),
        "heavy": override.get("heavy", base.heavy),
        "assault": override.get("assault", base.assault),
        "torrent": override.get("torrent", base.torrent),
        "hazardous": override.get("hazardous", base.hazardous),
        "blast": override.get("blast", base.blast),
        "lance": override.get("lance", base.lance),
        "precision": override.get("precision", base.precision),
        "pistol": override.get("pistol", base.pistol),
        "weapon": override.get("weapon", base.weapon),
        "secondary_pistol": override.get("secondary_pistol", base.secondary_pistol),
        "indirect_fire": override.get("indirect_fire", base.indirect_fire),
        "one_shot": override.get("one_shot", base.one_shot),
        "stealth": override.get("stealth", base.stealth),
        "lone_operative": override.get("lone_operative", base.lone_operative),
        "fights_first": override.get("fights_first", base.fights_first),
        "deep_strike": override.get("deep_strike", base.deep_strike),
        "scout_distance": override.get("scout_distance", base.scout_distance),
        "infiltrator": override.get("infiltrator", base.infiltrator),
        "deadly_demise": override.get("deadly_demise", base.deadly_demise),
        "firing_deck": override.get("firing_deck", base.firing_deck),
        "fnp": override.get("fnp", base.fnp),
        "sticky_objective": override.get("sticky_objective", base.sticky_objective),
        "resolute_will": override.get("resolute_will", base.resolute_will),
        "reanimates_with_army": override.get("reanimates_with_army", base.reanimates_with_army),
        "unit_keywords": override.get("unit_keywords", base.unit_keywords),
        "melee_attacks": override.get("melee_attacks", base.melee_attacks),
        "melee_damage_per_shot": override.get("melee_damage_per_shot", base.melee_damage_per_shot),
        "melee_hit_probability": override.get("melee_hit_probability", base.melee_hit_probability),
        "melee_strength": override.get("melee_strength", base.melee_strength),
        "melee_ap": override.get("melee_ap", base.melee_ap),
        "melee_weapon": override.get("melee_weapon", base.melee_weapon),
        "range_inches": override.get("range_inches", base.range_inches),
        "secondary_attacks": override.get("secondary_attacks", base.secondary_attacks),
        "secondary_weapon_damage_per_shot": override.get("secondary_weapon_damage_per_shot", base.secondary_weapon_damage_per_shot),
        "secondary_hit_probability": override.get("secondary_hit_probability", base.secondary_hit_probability),
        "secondary_ap": override.get("secondary_ap", base.secondary_ap),
        "secondary_strength": override.get("secondary_strength", base.secondary_strength),
        "secondary_range_inches": override.get("secondary_range_inches", base.secondary_range_inches),
        "secondary_weapon": override.get("secondary_weapon", base.secondary_weapon),
        "secondary_anti_keywords": override.get("secondary_anti_keywords", base.secondary_anti_keywords),
        "secondary_lethal_hits": override.get("secondary_lethal_hits", base.secondary_lethal_hits),
        "secondary_sustained_hits": override.get("secondary_sustained_hits", base.secondary_sustained_hits),
        "secondary_twin_linked": override.get("secondary_twin_linked", base.secondary_twin_linked),
        "secondary_devastating_wounds": override.get("secondary_devastating_wounds", base.secondary_devastating_wounds),
        "secondary_rapid_fire": override.get("secondary_rapid_fire", base.secondary_rapid_fire),
        "secondary_melta": override.get("secondary_melta", base.secondary_melta),
        "secondary_ignores_cover": override.get("secondary_ignores_cover", base.secondary_ignores_cover),
        "secondary_heavy": override.get("secondary_heavy", base.secondary_heavy),
        "secondary_assault": override.get("secondary_assault", base.secondary_assault),
        "secondary_torrent": override.get("secondary_torrent", base.secondary_torrent),
        "secondary_blast": override.get("secondary_blast", base.secondary_blast),
        # MAP-1: tertiary+ ranged profiles — override fully replaces (rare; the
        # mapper populates these from BSData and overrides almost never touch
        # multi-profile lists). base value defaults to [] when None.
        "extra_ranged_profiles": override.get(
            "extra_ranged_profiles", base.extra_ranged_profiles or []
        ),
        # MAP-3-FIX — basket fractions. Override path almost never sets these
        # (the mapper computes them from BSData) but allow overrides for
        # corner cases / hand-tuning. Default 1.0 preserves legacy behaviour.
        "devastating_wounds_basket_fraction": override.get(
            "devastating_wounds_basket_fraction",
            base.devastating_wounds_basket_fraction,
        ),
        "lance_basket_fraction": override.get(
            "lance_basket_fraction", base.lance_basket_fraction,
        ),
        "anti_keyword_basket_fractions": override.get(
            "anti_keyword_basket_fractions",
            base.anti_keyword_basket_fractions,
        ),
        "move": override.get("move", base.move),
        "points_override": override.get("points_override", base.points_override),
        "base_shape": override.get("base_shape", base.base_shape),
        "base_diameter_mm": override.get("base_diameter_mm", base.base_diameter_mm),
        "base_width_mm": override.get("base_width_mm", base.base_width_mm),
        "base_length_mm": override.get("base_length_mm", base.base_length_mm),
        "loadout": override.get("loadout", base.loadout),
        "notes": override.get("notes", base.notes),
        "enabled": override.get("enabled", base.enabled),
        "skip_reason": override.get("skip_reason", base.skip_reason),
    }
    return CatalogEntry.from_dict(merged)


def load_catalog(
    include_disabled: bool = False,
    use_calibrated: bool = False,
) -> Dict[str, CatalogEntry]:
    """
    Build the merged catalogue. Layers, in precedence order (later wins):

      1. data/bsdata/parsed.json     — BSData-derived base stats
      2. data/overrides.json         — hand-tuned modifications
      3. data/calibrated_points.json — balancer-derived points_override
                                       (only applied if use_calibrated=True
                                       AND the calibration converged)
    """
    base = _load_parsed()
    overrides = _load_overrides()
    calibrated = _load_calibrated_overrides() if use_calibrated else {}

    out: Dict[str, CatalogEntry] = {}
    keys = set(base) | set(overrides) | set(calibrated)
    for key in keys:
        # Merge overrides FIRST, then calibrated on top so balancer output
        # wins over manual overrides for points only.
        merged_override = dict(overrides.get(key, {}))
        merged_override.update(calibrated.get(key, {}))
        entry = _apply_override(base.get(key), merged_override, key)
        if not include_disabled and not entry.enabled:
            continue
        out[entry.key] = entry
    return out


def summary() -> str:
    catalog = load_catalog()
    return (
        f"{len(catalog)} units in catalogue "
        f"({len(_load_parsed())} from BSData, {len(_load_overrides())} override entries)"
    )


if __name__ == "__main__":
    print(summary())
    catalog = load_catalog()
    for key, entry in sorted(catalog.items())[:10]:
        print(
            f"  {key:50} {entry.name[:30]:30} "
            f"H={entry.health:>4.1f} D={entry.damage:>4.1f} "
            f"Hit={entry.hit_probability:>5.2f} AP={entry.ap:>2} Sv={entry.save}"
        )
