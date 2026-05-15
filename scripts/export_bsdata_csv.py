"""Export the UNIT_CATALOG to a CSV for spot-checking / spreadsheet work.

CLI:
    python -m scripts.export_bsdata_csv [--out data/units.csv]

The CSV holds one row per unit in `code.units.UNIT_CATALOG`, with the columns
documented in COLUMNS below. Useful for eyeballing per-unit stats, finding
outliers, or pasting into a spreadsheet to chart points vs. health / damage.

This is an admin tool — it doesn't mutate any state and is not exercised by
the simulator. The point is to surface what BSData + overrides produced.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, List

from code.units import UNIT_CATALOG, UnitProfile


# Column order is the export contract — tests assert against it. Group by
# concern: identity, defence, mobility/objective, ranged offence, melee
# offence, weapon keywords, unit abilities, and finally points + keyword lists.
COLUMNS: List[str] = [
    # identity
    "key", "name", "faction",
    # defence
    "health", "toughness", "save", "invuln_save", "fnp",
    # mobility / objective
    "move", "oc", "leadership",
    # ranged offence
    "attacks", "hit_probability", "strength", "ap",
    "weapon_damage_per_shot", "range_inches",
    # melee offence
    "melee_attacks", "melee_hit_probability", "melee_strength",
    "melee_ap", "melee_damage_per_shot",
    # weapon keywords
    "assault", "heavy", "pistol", "rapid_fire", "twin_linked",
    "ignores_cover", "torrent", "lethal_hits", "lance", "melta",
    "sustained_hits", "devastating_wounds", "precision", "blast",
    "indirect_fire", "hazardous", "one_shot",
    # unit abilities
    "stealth", "deep_strike", "scout_distance", "infiltrators",
    "sticky_objective", "lone_operative", "fly",
    # points + keyword lists
    "deadly_demise", "points_cost",
    "anti_keywords", "unit_keywords",
]


def _format_anti(profile: UnitProfile) -> str:
    """Render anti_keywords tuple-of-tuples as `KW:N|KW:N` (empty -> "")."""
    if not profile.anti_keywords:
        return ""
    return "|".join(f"{kw}:{thresh}" for kw, thresh in profile.anti_keywords)


def _format_unit_keywords(profile: UnitProfile) -> str:
    """Render unit_keywords tuple as pipe-joined keywords (empty -> "")."""
    if not profile.unit_keywords:
        return ""
    return "|".join(profile.unit_keywords)


def row_for(key: str, profile: UnitProfile) -> List[object]:
    """Materialise the row for `profile` in the order declared by COLUMNS."""
    return [
        key,
        profile.name,
        profile.faction,
        profile.health,
        profile.toughness,
        profile.save,
        profile.invuln_save,
        profile.fnp,
        profile.move,
        profile.oc,
        profile.leadership,
        profile.attacks,
        profile.hit_probability,
        profile.strength,
        profile.ap,
        profile.weapon_damage_per_shot,
        profile.range_inches,
        profile.melee_attacks,
        profile.melee_hit_probability,
        profile.melee_strength,
        profile.melee_ap,
        profile.melee_damage_per_shot,
        profile.assault,
        profile.heavy,
        profile.pistol,
        profile.rapid_fire,
        profile.twin_linked,
        profile.ignores_cover,
        profile.torrent,
        profile.lethal_hits,
        profile.lance,
        profile.melta,
        profile.sustained_hits,
        profile.devastating_wounds,
        profile.precision,
        profile.blast,
        profile.indirect_fire,
        profile.hazardous,
        profile.one_shot,
        profile.stealth,
        profile.deep_strike,
        profile.scout_distance,
        # `infiltrators` (plural) is the column name spec; UnitProfile field
        # is singular (`infiltrator`). Mapped here so the CSV header matches
        # the task spec without renaming the dataclass field.
        profile.infiltrator,
        profile.sticky_objective,
        profile.lone_operative,
        profile.fly,
        profile.deadly_demise,
        profile.points_cost,
        _format_anti(profile),
        _format_unit_keywords(profile),
    ]


def export_csv(out_path: Path, catalog: Iterable[tuple] | None = None) -> int:
    """Write the catalogue to `out_path`. Returns the number of data rows."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    items = (
        sorted(catalog) if catalog is not None
        else sorted(UNIT_CATALOG.items())
    )
    n_rows = 0
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for key, profile in items:
            writer.writerow(row_for(key, profile))
            n_rows += 1
    return n_rows


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        default="data/units.csv",
        help="Output CSV path (default: data/units.csv)",
    )
    args = parser.parse_args(argv)
    n = export_csv(Path(args.out))
    print(f"Wrote {n} rows to {args.out} ({len(COLUMNS)} columns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
