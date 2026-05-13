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
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PARSED_PATH = REPO_ROOT / "data" / "bsdata" / "parsed.json"
OVERRIDES_PATH = REPO_ROOT / "data" / "overrides.json"


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
        "loadout": override.get("loadout", base.loadout),
        "notes": override.get("notes", base.notes),
        "enabled": override.get("enabled", base.enabled),
        "skip_reason": override.get("skip_reason", base.skip_reason),
    }
    return CatalogEntry.from_dict(merged)


def load_catalog(include_disabled: bool = False) -> Dict[str, CatalogEntry]:
    """Build the merged catalogue from parsed.json + overrides.json."""
    base = _load_parsed()
    overrides = _load_overrides()

    out: Dict[str, CatalogEntry] = {}
    keys = set(base) | set(overrides)
    for key in keys:
        entry = _apply_override(base.get(key), overrides.get(key, {}), key)
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
