"""
Loader and applier for the v1 SwegHammer prices dataset.

The dataset itself is produced by `scripts/bake_swegpoints_v1.py` and lives
at `data/sweg_points_v1.json`. This module gives the rest of the codebase
two thin entry points:

- `load_sweg_overrides(path)` returns the per-unit prices as a flat
  ``key -> points_per_model`` dict, ready to hand to
  ``code.army_builder.build_*`` via the existing ``price_overrides``
  parameter.
- `apply_to_catalog(catalog, overrides)` mutates ``UnitProfile.points_override``
  in place for every matching key. Used by the Streamlit app when the
  "Use SwegHammer points (v1.0)" checkbox is on, since the in-process
  catalogue dict is shared across the app.

Per CLAUDE.md rule 13, any key in the overrides file that doesn't resolve
in ``UNIT_CATALOG`` raises loudly rather than silently dropping.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Dict

from .units import UNIT_CATALOG, UnitProfile

SWEG_POINTS_V1_PATH = Path(__file__).parent.parent / "data" / "sweg_points_v1.json"


def load_sweg_overrides(path: Path = SWEG_POINTS_V1_PATH) -> Dict[str, float]:
    """Read a sweg_points_v*.json file and return ``{catalog_key: price}``.

    The dataset's ``prices`` block has the form
    ``{key: {"sweg_pts_per_model": int, ...}}``; this collapses it to
    ``{key: float}`` so it slots into the existing ``price_overrides``
    parameter on ``code.army_builder.build_*``.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"SwegHammer prices dataset not found at {path}. "
            "Run: python3 scripts/bake_swegpoints_v1.py"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if "prices" not in data:
        raise ValueError(
            f"{path} is missing the required 'prices' block "
            "(expected a dict of catalog_key -> price record)."
        )
    out: Dict[str, float] = {}
    for key, record in data["prices"].items():
        if not isinstance(record, dict) or "sweg_pts_per_model" not in record:
            raise ValueError(
                f"{path}: price record for {key!r} is missing "
                "'sweg_pts_per_model'."
            )
        out[key] = float(record["sweg_pts_per_model"])
    return out


def apply_to_catalog(
    catalog: Dict[str, UnitProfile],
    overrides: Dict[str, float],
    strict: bool = True,
) -> int:
    """Set ``points_override`` on every catalogue entry named in ``overrides``.

    Returns the number of profiles touched. If ``strict`` is True (default,
    per CLAUDE.md rule 13), any key in ``overrides`` that doesn't resolve in
    ``catalog`` raises loudly. Set ``strict=False`` only when applying an
    overrides file produced from a different catalogue revision and the
    drift is expected.
    """
    missing = [k for k in overrides if k not in catalog]
    if strict and missing:
        sample = ", ".join(missing[:5])
        raise KeyError(
            f"sweg_points overrides reference {len(missing)} keys not in "
            f"UNIT_CATALOG (e.g. {sample}). The dataset was likely baked "
            "against a different catalogue revision — re-run "
            "scripts/bake_swegpoints_v1.py."
        )

    touched = 0
    for key, price in overrides.items():
        profile = catalog.get(key)
        if profile is None:
            continue
        # UnitProfile is a frozen dataclass — swap the entry rather than
        # mutate. Callers holding references to the prior instance keep the
        # old prices, which is the safer default for Streamlit's per-rerun
        # lifecycle.
        catalog[key] = dataclasses.replace(profile, points_override=float(price))
        touched += 1
    return touched


def reset_catalog_overrides(catalog: Dict[str, UnitProfile]) -> int:
    """Clear every ``points_override`` set by a previous ``apply_to_catalog``.

    Used by the Streamlit app when the user toggles the SwegHammer-prices
    checkbox off — we restore GW prices by zeroing the override so the
    canonical ``points_per_squad / min_models`` formula takes back over.
    Returns the number of profiles cleared.
    """
    cleared = 0
    for key, profile in list(catalog.items()):
        if profile.points_override and profile.points_override > 0:
            catalog[key] = dataclasses.replace(profile, points_override=0.0)
            cleared += 1
    return cleared
