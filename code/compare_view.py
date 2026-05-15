"""Compare GW points against equilibrium prices across all solver phases.

This module surfaces a tidy DataFrame joining the per-phase
``data/equilibrium_points*.json`` outputs with the SwegHammer override
registry, so the Streamlit UI can render a one-stop "which units does GW
mis-price" table.

Why a dedicated module rather than inlining in ``app.py``: keeping the data
shaping out of the UI lets unit tests pin the schema, and the helper can be
reused by audit scripts later.

The phase files are loaded lazily and tolerantly — if a phase JSON is missing
or malformed the corresponding columns are filled with NaN rather than the
whole comparison failing. This matters because the equilibrium solvers are
periodically re-run and one phase may be temporarily absent on a feature
branch.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

# Repository root is two levels up from this file (code/compare_view.py).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _REPO_ROOT / "data"

# Ordered: oldest -> newest. Order is the column order in the output.
PHASE_FILES: "OrderedDict[str, str]" = OrderedDict(
    [
        ("phase1", "equilibrium_points.json"),
        ("phase2", "equilibrium_points_phase2.json"),
        ("phase4", "equilibrium_points_phase4.json"),
        ("phase5", "equilibrium_points_phase5.json"),
        ("phase6", "equilibrium_points_phase6.json"),
    ]
)

_OVERRIDES_FILE = "overrides.json"


def _load_phase_units(filename: str) -> Dict[str, Dict[str, Any]]:
    """Return the ``units`` dict from a phase JSON, or {} if unreadable."""
    path = _DATA_DIR / filename
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    units = payload.get("units", {})
    if not isinstance(units, dict):
        return {}
    return units


def _load_override_keys() -> set:
    """Return the set of unit keys that have a SwegHammer override."""
    path = _DATA_DIR / _OVERRIDES_FILE
    if not path.exists():
        return set()
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return set()
    units = payload.get("units", {})
    if not isinstance(units, dict):
        return set()
    return set(units.keys())


def _identity_for(key: str, phase_data: Iterable[Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
    """Pick a canonical name / faction / role / GW points for a unit.

    We scan phase outputs in order and take the first non-empty value for
    each field. Equilibrium JSONs all share the same identity fields, but
    a unit may only appear in later phases (or vice versa) so we union.
    """
    fields = ("name", "faction", "role", "gw_points_per_model")
    out: Dict[str, Any] = {f: None for f in fields}
    for units in phase_data:
        entry = units.get(key)
        if not entry:
            continue
        for f in fields:
            if out[f] is None and entry.get(f) is not None:
                out[f] = entry[f]
        if all(out[f] is not None for f in fields):
            break
    return out


def build_comparison_df(
    phase_files: Optional["OrderedDict[str, str]"] = None,
    data_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """Build a tidy DataFrame comparing GW points to equilibrium prices.

    Columns:
        unit_key, name, faction, role, gw_points_per_model,
        eq_<phase>, mispricing_pct_<phase> for each configured phase,
        sweghammer_override (bool)
    """
    # Allow tests to inject a sandbox data dir.
    global _DATA_DIR  # noqa: PLW0603 — intentional, scoped to test injection
    original_data_dir = _DATA_DIR
    if data_dir is not None:
        _DATA_DIR = Path(data_dir)

    try:
        phases = phase_files if phase_files is not None else PHASE_FILES

        phase_units: "OrderedDict[str, Dict[str, Dict[str, Any]]]" = OrderedDict(
            (label, _load_phase_units(fname)) for label, fname in phases.items()
        )
        override_keys = _load_override_keys()

        # Union of unit keys across every phase.
        all_keys: set = set()
        for units in phase_units.values():
            all_keys.update(units.keys())

        rows: List[Dict[str, Any]] = []
        for key in sorted(all_keys):
            identity = _identity_for(key, phase_units.values())
            row: Dict[str, Any] = {
                "unit_key": key,
                "name": identity["name"],
                "faction": identity["faction"],
                "role": identity["role"],
                "gw_points_per_model": identity["gw_points_per_model"],
            }
            for label, units in phase_units.items():
                entry = units.get(key)
                if entry is None:
                    row[f"eq_{label}"] = None
                    row[f"mispricing_pct_{label}"] = None
                else:
                    row[f"eq_{label}"] = entry.get("equilibrium_points_per_model")
                    row[f"mispricing_pct_{label}"] = entry.get("mispricing_pct")
            row["sweghammer_override"] = key in override_keys
            rows.append(row)

        columns = (
            ["unit_key", "name", "faction", "role", "gw_points_per_model"]
            + [f"eq_{label}" for label in phases]
            + [f"mispricing_pct_{label}" for label in phases]
            + ["sweghammer_override"]
        )
        df = pd.DataFrame(rows, columns=columns)
        return df
    finally:
        _DATA_DIR = original_data_dir


def render_compare_tab(st) -> None:  # pragma: no cover — Streamlit UI
    """Render the Compare tab inside an existing Streamlit ``st.tabs`` block.

    Caller is expected to have already created the tab and entered the
    ``with`` context. We just paint into the current container.
    """
    st.markdown("## Compare  —  GW points vs SwegHammer equilibrium")
    st.caption(
        "Each row is one unit. GW's listed cost sits next to the equilibrium "
        "price our solver believes the unit should command, one column per "
        "solver phase. ``sweghammer_override`` marks units whose base stats "
        "we have hand-tuned in ``data/overrides.json``."
    )

    df = build_comparison_df()

    if df.empty:
        st.warning(
            "No equilibrium data found. Run the Phase 1+ solvers first "
            "(`python -m code.equilibrium`)."
        )
        return

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------
    col_f, col_r, col_o = st.columns([2, 2, 1])
    with col_f:
        factions = sorted({f for f in df["faction"].dropna().unique()})
        picked_factions = st.multiselect(
            "Faction", factions, default=[], key="compare_factions"
        )
    with col_r:
        roles = sorted({r for r in df["role"].dropna().unique()})
        picked_roles = st.multiselect(
            "Role", roles, default=[], key="compare_roles"
        )
    with col_o:
        only_overrides = st.checkbox(
            "Override only", value=False, key="compare_overrides_only"
        )

    filtered = df
    if picked_factions:
        filtered = filtered[filtered["faction"].isin(picked_factions)]
    if picked_roles:
        filtered = filtered[filtered["role"].isin(picked_roles)]
    if only_overrides:
        filtered = filtered[filtered["sweghammer_override"]]

    st.markdown(f"**{len(filtered)}** units shown (of {len(df)} total).")

    # The default Streamlit dataframe is sortable on every column, which is
    # exactly the interaction we want here — sort by mispricing_pct_phase6
    # descending to see the most over-costed units, etc.
    st.dataframe(filtered, use_container_width=True, hide_index=True)
