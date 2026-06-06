"""SwegHammer — Streamlit battle simulator dashboard."""

from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import time
from io import BytesIO
from typing import Callable, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from code.army import Army
from code.army_builder import (
    build_army_from_list,
    build_faction_random_army,
    build_homogeneous_army,
)
from code.events import EventLog
from code.factions import FACTION_COLOURS, colour_for
from code.map import Map
from code.maps import (
    DEFAULT_MAP,
    MAP_POINTS_RANGE,
    STOCK_MAPS,
    auto_select_map_key,
    maps_fitting,
)
from code.renderer import (
    aggregate_activations, event_description, frame_description, render_frame,
)
from code.simulator import Battle, BattleResult
from code.units import UNIT_CATALOG as _RAW_CATALOG, UnitProfile, balanced_catalog, save_probability
from code.equilibrium import (
    compute_phase1 as compute_equilibrium_phase1,
    DEFAULT_ANCHOR_KEY as EQ_DEFAULT_ANCHOR,
    DEFAULT_ANCHOR_PER_MODEL as EQ_DEFAULT_ANCHOR_PTS,
)
from code.equilibrium_simdriven import (
    SIMDRIVEN_PATH as EQ_SIMDRIVEN_PATH,
    load_snapshot as load_eq_simdriven_snapshot,
)
from code.compare_view import render_compare_tab
from code.equation_data_fit import (
    FeatureSpec as EqFitFeatureSpec,
    default_feature_specs as eqfit_default_specs,
    extract_features as eqfit_extract_features,
    faction_multipliers as eqfit_faction_multipliers,
    fit as eqfit_fit,
    transform_names as eqfit_transform_names,
)
from code.tournament_validation import (
    aggregate_by_faction as tv_aggregate_by_faction,
    fit_winrate_model as tv_fit_winrate_model,
    load_tournament_lists as tv_load_tournament_lists,
    match_units as tv_match_units,
    score_list as tv_score_list,
)

import json as _json
import pathlib as _pathlib
import csv as _csv

# ---------------------------------------------------------------------------
# v1.0 release identity (the "fanfare" — a cool title and a quiet version)
# ---------------------------------------------------------------------------

from code import __version__   # single source of truth: code/__init__.py
_APP_TITLE = "SwegHammer — Recalibrated"
_APP_TAGLINE = "Fair points, fitted to the meta"

# One palette for the whole app. Existing references to these hex codes
# stay as literals where they're already in use; this dict is the
# authoritative source for any new chart / widget.
SWEG_PALETTE = {
    "accent_gold":  "#c9a84c",   # primary headline / wordmark accent
    "line_blue":    "#9bd6ff",   # regression / reference lines
    "delta_up":     "#7eb87e",   # positive Δ (Sweg priced unit UP)
    "delta_down":   "#d65f5f",   # negative Δ (Sweg priced unit DOWN)
    "neutral_grey": "#888888",
    "bg_panel":     "#1a1d23",
    "bg_page":      "#0e1117",
    "grid":         "#3a3d45",
}

_SWEG_POINTS_PATH = _pathlib.Path(__file__).parent / "data" / "sweg_points_v1.json"

_META_SNAPSHOT_PATH        = _pathlib.Path(__file__).parent / "data" / "meta_comparison_snapshot.json"
_MAE_PROGRESS_PATH         = _pathlib.Path(__file__).parent / "docs" / "mae_progress.csv"
_EQUATION_SNAPSHOT_PATH    = _pathlib.Path(__file__).parent / "data" / "equation_vs_meta_snapshot.json"
_EQUATION_CALIBRATED_PATH  = _pathlib.Path(__file__).parent / "data" / "equation_calibrated_points.json"
_FIT_EQ_LOG_PATH           = _pathlib.Path(__file__).parent / "logs" / "fit_eq_gui.log"
_EVAL_EQ_LOG_PATH          = _pathlib.Path(__file__).parent / "logs" / "eval_eq_gui.log"

# Factions with no authoritative tournament data — excluded from the headline
# MAE. Must stay in sync with FX_ALL_FACTIONS in scripts/evaluate_vs_meta.py.
_FX_ALL_FACTIONS = frozenset({
    "Chaos Space Marines", "World Eaters", "Emperor's Children",
    "Chaos Daemons", "Astra Militarum", "Adeptus Mechanicus",
    "Adepta Sororitas", "Grey Knights", "Drukhari",
    "Genestealer Cults", "Imperial Knights", "Chaos Knights",
})


def _load_meta_snapshot():
    """Return parsed JSON from data/meta_comparison_snapshot.json, or None."""
    if not _META_SNAPSHOT_PATH.exists():
        return None
    try:
        return _json.loads(_META_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _load_equation_snapshot():
    """Return parsed JSON from data/equation_vs_meta_snapshot.json, or None."""
    if not _EQUATION_SNAPSHOT_PATH.exists():
        return None
    try:
        return _json.loads(_EQUATION_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _load_mae_progress():
    """Return list of dicts from docs/mae_progress.csv, skipping parked rows."""
    if not _MAE_PROGRESS_PATH.exists():
        return []
    rows = []
    with _MAE_PROGRESS_PATH.open(newline="", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            if row.get("parked", "False").strip().lower() == "true":
                continue
            try:
                rows.append({
                    "when":  row["when"],
                    "label": row["label"],
                    "mae":   float(row["mae"]),
                    "mode":  row.get("mode", ""),
                })
            except (KeyError, ValueError):
                continue
    return rows

# `UNIT_CATALOG` in this module starts as the raw catalogue but gets re-bound
# below once the sidebar's "Use SwegHammer balanced points" toggle is read.
# Module-level helper functions resolve `UNIT_CATALOG` from app.py's globals
# at call time, so rebinding propagates without further plumbing.
UNIT_CATALOG = _RAW_CATALOG

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SwegHammer Simulator",
    page_icon="⚔️",
    layout="wide",
)

st.markdown("""
<style>
/* ── Sidebar title accent ────────────────────────────────── */
[data-testid="stSidebar"] .stMarkdown h1 {
    color: #c9a84c;
    letter-spacing: 0.05em;
}

/* ── Primary button (Run Simulation) ────────────────────── */
[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #b8860b 0%, #c9a84c 100%);
    border: none;
    color: #0e1117;
    font-weight: 700;
    letter-spacing: 0.04em;
    border-radius: 6px;
}
[data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg, #c9a84c 0%, #e0c070 100%);
    color: #0e1117;
}

/* ── Metric cards — subtle border only, no bg override ───── */
[data-testid="stMetric"] {
    border: 1px solid #3a3d45;
    border-radius: 8px;
    padding: 0.5rem 0.8rem;
}

/* ── Active tab accent ───────────────────────────────────── */
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #c9a84c;
    border-bottom-color: #c9a84c;
}

/* ── Progress bar fill ───────────────────────────────────── */
[data-testid="stProgressBar"] > div {
    background-color: #c9a84c;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached per-frame PNG renderer
# ---------------------------------------------------------------------------
# The Replay slider triggers a full Streamlit rerun on every tick. Rendering
# a matplotlib figure from scratch each time (~100-300ms for a busy frame)
# makes scrubbing feel sluggish. We cache the rendered PNG keyed by
# (replay_id, frame_idx): scrubbing back through a previously-rendered frame
# is then instant. `replay_id` increments per run so old caches dropped.

@st.cache_data(show_spinner=False, max_entries=400)
def _render_frame_png(replay_id: int, frame_idx: int) -> bytes:
    events = st.session_state["replay_events"]
    map_ = st.session_state["replay_map"]
    frames = st.session_state.get("replay_frames")
    col_a = st.session_state.get("replay_colour_a", "#4e9af1")
    col_b = st.session_state.get("replay_colour_b", "#e05c5c")
    img = render_frame(
        map_, events, frame_idx, frames=frames,
        colour_a=col_a, colour_b=col_b,
    )
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

DEFAULT_COL_A = "#4e9af1"
DEFAULT_COL_B = "#e05c5c"
COL_DRAW = "#aaaaaa"

# Sorted faction list (drops empty/unknown) — drives the faction-filter dropdown
FACTIONS_AVAILABLE = sorted({
    UNIT_CATALOG[k].faction for k in UNIT_CATALOG if UNIT_CATALOG[k].faction
})


def _units_in_faction(faction: str) -> List[str]:
    """Catalogue keys belonging to a faction, sorted by display name."""
    return sorted(
        (k for k in UNIT_CATALOG if UNIT_CATALOG[k].faction == faction),
        key=lambda k: UNIT_CATALOG[k].name,
    )


# Composition rows are (unit_key, num_squads) — legacy, presets/random — OR
# (unit_key, num_squads, models_per_squad) from the army-list builder. The
# `*rest` unpack tolerates both; a missing size defaults to 1 (the legacy
# one-model-per-instance behaviour), while the builder passes an explicit
# squad size in [min_models, max_models].
def _composition_total_points(comp) -> float:
    total = 0.0
    for k, n, *rest in comp:
        if n <= 0:
            continue
        size = int(rest[0]) if rest else 1
        total += UNIT_CATALOG[k].points_cost * max(1, size) * n
    return total


def _composition_faction(comp) -> str:
    """The faction of the first non-zero entry — used to pick the army's colour."""
    for k, n, *rest in comp:
        if n > 0:
            return UNIT_CATALOG[k].faction
    return ""


def _build_army_from_composition(name: str, comp, in_cover: bool = False) -> Army:
    army = Army(name, in_cover=in_cover)
    for unit_key, count, *rest in comp:
        count = max(0, int(count))
        if count == 0:
            continue
        profile = UNIT_CATALOG[unit_key]
        size = max(1, int(rest[0]) if rest else 1)
        for _ in range(count):
            army.add_squad(profile, size)
    return army


def _army_spec_from_composition(
    name: str, comp: List[Tuple[str, int]], in_cover: bool = False,
) -> dict:
    keys: List[str] = []
    for unit_key, count in comp:
        keys.extend([unit_key] * max(0, int(count)))
    return {"name": name, "keys": keys, "in_cover": in_cover}


def _composition_from_random(
    faction: str, budget: float, size_policy: str, seed: int,
) -> List[Tuple[str, int]]:
    """Generate a single sample random army and return its model breakdown."""
    rng = random.Random(seed)
    army = build_faction_random_army(faction, faction, budget, rng=rng, size_policy=size_policy)
    # Group adjacent same-profile units into (key, count) pairs
    from collections import Counter
    name_to_key = {UNIT_CATALOG[k].name: k for k in UNIT_CATALOG if UNIT_CATALOG[k].faction == faction}
    counts = Counter(u.profile.name for u in army.units)
    return [(name_to_key[n], c) for n, c in counts.most_common() if n in name_to_key]

# ---------------------------------------------------------------------------
# Preset battle definitions
# ---------------------------------------------------------------------------

PRESETS = {
    "⚔️  Classic: Intercessors vs Ork Boyz": {
        "description": (
            "The quintessential matchup — disciplined, high-accuracy Marines "
            "against a brutal Boyz mob. Elite armour and AP vs sheer numbers."
        ),
        "a_name": "Intercessor Squad",
        "a_key": "space_marines_intercessor_squad",
        "b_name": "Boyz",
        "b_key": "orks_boyz",
        "points": 500,
    },
    "💀  Elite Clash: Terminators vs Necron Warriors": {
        "description": (
            "Heavy-armoured Marine Terminators against the resilient Necron line. "
            "Elite firepower vs reanimating bodies."
        ),
        "a_name": "Terminator Squad",
        "a_key": "space_marines_terminator_squad",
        "b_name": "Necron Warriors",
        "b_key": "necrons_necron_warriors",
        "points": 500,
    },
    "🤺  God-engine: Knight Errant vs Necrons": {
        "description": (
            "A 22-wound Imperial Knight Errant with melta cannon stomps through "
            "a Necron Warrior line. Single super-heavy vs horde."
        ),
        "a_name": "Knight Errant",
        "a_key": "imperial_knights_library_knight_errant",
        "b_name": "Necron Warriors",
        "b_key": "necrons_necron_warriors",
        "points": 500,
    },
}

# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def run_simulations(
    factory_a: Callable[[], Army],
    factory_b: Callable[[], Army],
    n: int,
    map_: Map = DEFAULT_MAP,
    on_progress: Optional[Callable[[int, int], None]] = None,
    spec_a: Optional[dict] = None,
    spec_b: Optional[dict] = None,
) -> List[BattleResult]:
    if spec_a is not None and spec_b is not None:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from code.sim_worker import run_one_battle
        results: List[Optional[BattleResult]] = [None] * n
        with ProcessPoolExecutor() as executor:
            fs = {executor.submit(run_one_battle, spec_a, spec_b, map_): i
                  for i in range(n)}
            done = 0
            for future in as_completed(fs):
                results[fs[future]] = future.result()
                done += 1
                if on_progress:
                    on_progress(done, n)
        return results  # type: ignore[return-value]
    results = []
    for i in range(n):
        results.append(Battle(factory_a(), factory_b(), map_=map_).run())
        if on_progress:
            on_progress(i + 1, n)
    return results


def aggregate(results: List[BattleResult], a_name: str, b_name: str):
    a_wins = sum(1 for r in results if r.winner == a_name)
    b_wins = sum(1 for r in results if r.winner == b_name)
    draws = len(results) - a_wins - b_wins
    return a_wins, b_wins, draws


def avg_attrition(results: List[BattleResult]) -> Tuple[List[float], List[float]]:
    max_len = max(len(r.round_history) for r in results)
    a_sums = [0.0] * max_len
    b_sums = [0.0] * max_len
    counts = [0] * max_len
    for r in results:
        for i, (a, b) in enumerate(r.round_history):
            a_sums[i] += a
            b_sums[i] += b
            counts[i] += 1
    return [a_sums[i] / counts[i] for i in range(max_len)], \
           [b_sums[i] / counts[i] for i in range(max_len)]

# ---------------------------------------------------------------------------
# Chart functions
# ---------------------------------------------------------------------------

def chart_win_rates(a_wins, b_wins, draws, a_name, b_name, n):
    fig, ax = plt.subplots(figsize=(4, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    sizes = [a_wins, b_wins, draws]
    colors = [COL_A, COL_B, COL_DRAW]
    wedges, _, autotexts = ax.pie(
        sizes, colors=colors, explode=(0.04, 0.04, 0.02),
        autopct=lambda p: f"{p:.1f}%" if p > 1 else "",
        startangle=90,
        wedgeprops=dict(linewidth=1.5, edgecolor="#0e1117"),
        textprops=dict(color="white"),
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")

    ax.legend(
        handles=[
            mpatches.Patch(color=COL_A, label=f"{a_name}  {a_wins/n:.1%}"),
            mpatches.Patch(color=COL_B, label=f"{b_name}  {b_wins/n:.1%}"),
            mpatches.Patch(color=COL_DRAW, label=f"Draw  {draws/n:.1%}"),
        ],
        loc="lower center", bbox_to_anchor=(0.5, -0.18),
        frameon=False, labelcolor="white", fontsize=10,
    )
    ax.set_title("Win Rate", color="white", fontsize=13, pad=12)
    fig.tight_layout()
    return fig


def chart_survivor_histogram(results: List[BattleResult], a_name: str, b_name: str):
    a_surv = [r.a_survivors for r in results]
    b_surv = [r.b_survivors for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(8, 3.5))
    fig.patch.set_facecolor("#0e1117")

    for ax, data, name, color in [
        (axes[0], a_surv, a_name, COL_A),
        (axes[1], b_surv, b_name, COL_B),
    ]:
        ax.set_facecolor("#1a1d23")
        max_val = max(data) if data else 1
        bins = range(0, max_val + 2)
        ax.hist(data, bins=bins, color=color, alpha=0.85, edgecolor="#0e1117", rwidth=0.85)
        ax.axvline(np.mean(data), color="white", linestyle="--", linewidth=1.2, alpha=0.7)
        ax.set_title(f"{name}\nSurvivors", color="white", fontsize=11)
        ax.set_xlabel("Units remaining", color="#aaaaaa", fontsize=9)
        ax.set_ylabel("Battles", color="#aaaaaa", fontsize=9)
        ax.tick_params(colors="#aaaaaa")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333333")

    fig.suptitle("Survivor Distribution", color="white", fontsize=13, y=1.02)
    fig.tight_layout()
    return fig


def chart_attrition(results: List[BattleResult], a_name: str, b_name: str):
    a_avg, b_avg = avg_attrition(results)
    rounds = list(range(len(a_avg)))

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#1a1d23")

    ax.plot(rounds, a_avg, color=COL_A, linewidth=2.5, label=a_name, marker="o", markersize=4)
    ax.plot(rounds, b_avg, color=COL_B, linewidth=2.5, label=b_name, marker="o", markersize=4)
    ax.fill_between(rounds, a_avg, alpha=0.15, color=COL_A)
    ax.fill_between(rounds, b_avg, alpha=0.15, color=COL_B)

    ax.set_xlabel("Round", color="#aaaaaa", fontsize=10)
    ax.set_ylabel("Avg units alive", color="#aaaaaa", fontsize=10)
    ax.set_title("Attrition Curve (avg across all battles)", color="white", fontsize=13)
    ax.legend(frameon=False, labelcolor="white", fontsize=10)
    ax.tick_params(colors="#aaaaaa")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")

    fig.tight_layout()
    return fig


def chart_win_rate_vs_points(
    profile_a: UnitProfile,
    profile_b: UnitProfile,
    a_name: str,
    b_name: str,
    a_cover: bool,
    b_cover: bool,
    n_battles: int = 200,
    map_: Map = DEFAULT_MAP,
    precomputed: Optional[tuple] = None,
):
    if precomputed is not None:
        point_values, a_rates, b_rates, draw_rates = precomputed
    else:
        point_values = list(range(100, 601, 50))
        a_rates, b_rates, draw_rates = [], [], []

        for pts in point_values:
            res = run_simulations(
                lambda p=pts: build_homogeneous_army(a_name, profile_a, p, in_cover=a_cover),
                lambda p=pts: build_homogeneous_army(b_name, profile_b, p, in_cover=b_cover),
                n_battles,
                map_=map_,
            )
            aw, bw, d = aggregate(res, a_name, b_name)
            a_rates.append(aw / n_battles)
            b_rates.append(bw / n_battles)
            draw_rates.append(d / n_battles)

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#1a1d23")

    ax.plot(point_values, a_rates, color=COL_A, linewidth=2.5, label=f"{a_name} win%", marker="o", markersize=4)
    ax.plot(point_values, b_rates, color=COL_B, linewidth=2.5, label=f"{b_name} win%", marker="o", markersize=4)
    ax.plot(point_values, draw_rates, color=COL_DRAW, linewidth=1.5, linestyle="--", label="Draw%", marker=".", markersize=3)
    ax.axhline(0.5, color="white", linestyle=":", linewidth=1, alpha=0.4)

    ax.set_ylim(0, 1)
    ax.set_xlabel("Points per army (equal)", color="#aaaaaa", fontsize=10)
    ax.set_ylabel("Win probability", color="#aaaaaa", fontsize=10)
    ax.set_title("Win Rate vs Points Budget", color="white", fontsize=13)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.legend(frameon=False, labelcolor="white", fontsize=10)
    ax.tick_params(colors="#aaaaaa")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")

    fig.tight_layout()
    return fig

# ---------------------------------------------------------------------------
# Equilibrium figure — cached so clicks / filter toggles don't rebuild it
# ---------------------------------------------------------------------------
# Without this cache, every click on the scatter triggers a full Streamlit
# rerun that rebuilds the whole Plotly figure (1,400+ points across ~30
# faction traces with customdata blobs). That made the chart feel sluggish
# under any interaction. The figure depends only on (anchor, filters), so
# we cache on those and replays are instant.


def _build_equilibrium_figure(entries, y_axis_title: str) -> go.Figure:
    """Render the equilibrium scatter from a flat list of entry objects.

    Used by both the cached closed-form path (`_equilibrium_plotly_figure`)
    and the sim-driven snapshot path. Entries must expose
    `faction`, `gw_points_per_model`, `equilibrium_points_per_model`,
    `key`, `name`, `role`, `mispricing_pct`, `valid_matchups` — both the
    `EquilibriumEntry` dataclass and the SimpleNamespace-wrapped snapshot
    rows satisfy this.
    """
    fig = go.Figure()
    by_faction: dict[str, list] = {}
    for e in entries:
        by_faction.setdefault(e.faction or "Unknown", []).append(e)

    for faction, faction_entries in sorted(by_faction.items()):
        fig.add_trace(go.Scatter(
            x=[e.gw_points_per_model for e in faction_entries],
            y=[e.equilibrium_points_per_model for e in faction_entries],
            mode="markers",
            name=faction,
            marker=dict(
                size=9,
                color=colour_for(faction),
                line=dict(width=0.5, color="white"),
                opacity=0.85,
            ),
            customdata=[
                [e.key, e.name, e.role, e.mispricing_pct, e.valid_matchups]
                for e in faction_entries
            ],
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                f"Faction: {faction}<br>"
                "Role: %{customdata[2]}<br>"
                "GW pts/model: %{x:.1f}<br>"
                "Equilibrium pts/model: %{y:.1f}<br>"
                "Mispricing: %{customdata[3]:+.1f}%<br>"
                "Valid matchups: %{customdata[4]}<br>"
                "<i>click to drill into this unit</i>"
                "<extra></extra>"
            ),
        ))

    if entries:
        xs_all = [e.gw_points_per_model for e in entries]
        ys_all = [e.equilibrium_points_per_model for e in entries]
        lo = max(0.5, min(min(xs_all), min(ys_all)) * 0.8)
        hi = max(max(xs_all), max(ys_all)) * 1.2
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[lo, hi],
            mode="lines",
            name="y = x (fair)",
            line=dict(color="#FFD700", dash="dash", width=1.2),
            hoverinfo="skip",
            showlegend=True,
        ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#1a1d23",
        xaxis=dict(
            title="GW points per model (log)",
            type="log",
            gridcolor="#3a3d45",
            zerolinecolor="#3a3d45",
        ),
        yaxis=dict(
            title=y_axis_title,
            type="log",
            gridcolor="#3a3d45",
            zerolinecolor="#3a3d45",
        ),
        title=dict(
            text=(
                "Above diagonal → GW undercosted  ·  "
                "Below diagonal → GW overcosted"
            ),
            font=dict(color="#c9a84c", size=13),
        ),
        legend=dict(
            bgcolor="rgba(26, 29, 35, 0.85)",
            bordercolor="#3a3d45",
            borderwidth=1,
            font=dict(size=10),
        ),
        height=560,
        margin=dict(l=60, r=20, t=60, b=50),
        hovermode="closest",
        uirevision="eq_scatter_static",
    )
    return fig


@st.cache_data(show_spinner="Building equilibrium chart…", max_entries=8)
def _equilibrium_plotly_figure(
    anchor_key: str,
    anchor_pts: float,
    factions_tuple: Tuple[str, ...],
    roles_tuple: Tuple[str, ...],
    balanced: bool,
) -> go.Figure:
    catalog = balanced_catalog() if balanced else _RAW_CATALOG
    result = compute_equilibrium_phase1(
        catalog=catalog, anchor_key=anchor_key, anchor_per_model=anchor_pts,
    )
    faction_set = set(factions_tuple) if factions_tuple else None
    role_set = set(roles_tuple)
    entries = [
        e for e in result.entries
        if (faction_set is None or e.faction in faction_set)
        and e.role in role_set
        and e.gw_points_per_model > 0
        and e.equilibrium_points_per_model > 0
    ]
    return _build_equilibrium_figure(
        entries,
        y_axis_title="Equilibrium points per model (log)",
    )


@st.cache_data(show_spinner="Building equilibrium chart…", max_entries=4)
def _equilibrium_plotly_figure_simdriven(
    factions_tuple: Tuple[str, ...],
    roles_tuple: Tuple[str, ...],
    only_measured: bool,
) -> go.Figure:
    snapshot = load_eq_simdriven_snapshot()
    if snapshot is None:
        return go.Figure()
    from types import SimpleNamespace
    rows = [SimpleNamespace(**row) for row in snapshot.get("units", {}).values()]
    faction_set = set(factions_tuple) if factions_tuple else None
    role_set = set(roles_tuple)
    entries = [
        e for e in rows
        if (faction_set is None or e.faction in faction_set)
        and e.role in role_set
        and e.gw_points_per_model > 0
        and e.equilibrium_points_per_model > 0
        and (not only_measured or getattr(e, "source", "") == "sim")
    ]
    return _build_equilibrium_figure(
        entries,
        y_axis_title="Sim-driven equilibrium points per model (log)",
    )


def _load_equation_calibrated_entries():
    """Load `data/equation_calibrated_points.json` and join with UNIT_CATALOG.

    The fit script writes per-unit `price_per_model` only; we attach name /
    faction / role / GW price by looking each unit up in the live catalogue.
    A unit is tagged `source="sim"` when its faction is in the snapshot's
    `trusted_factions`, else `phase1_fallback` (approximation — exact when
    the fit was run without `--max-per-faction`).
    """
    from types import SimpleNamespace
    from code.equilibrium import _classify_role
    if not _EQUATION_CALIBRATED_PATH.exists():
        return [], {}
    data = _json.loads(_EQUATION_CALIBRATED_PATH.read_text(encoding="utf-8"))
    prices = data.get("prices", {})
    trusted = set(data.get("trusted_factions", []))
    entries = []
    for key, price_per_model in prices.items():
        unit = _RAW_CATALOG.get(key)
        if unit is None or price_per_model <= 0:
            continue
        gw_per_model = (
            unit.points_per_squad / max(1, unit.min_models)
            if unit.points_per_squad > 0 else 0.0
        )
        if gw_per_model <= 0:
            continue
        misp = (price_per_model - gw_per_model) / gw_per_model * 100.0
        entries.append(SimpleNamespace(
            key=key,
            name=unit.name,
            faction=unit.faction or "Unknown",
            role=_classify_role(unit),
            min_models=unit.min_models,
            gw_points_per_squad=unit.points_per_squad,
            gw_points_per_model=gw_per_model,
            equilibrium_points_per_model=float(price_per_model),
            equilibrium_points_per_squad=float(price_per_model) * unit.min_models,
            mispricing_pct=misp,
            valid_matchups=0,  # not tracked by the equation fit
            source="sim" if unit.faction in trusted else "phase1_fallback",
        ))
    meta = {k: v for k, v in data.items() if k != "prices"}
    return entries, meta


@st.cache_data(show_spinner="Building equation chart…", max_entries=4)
def _equilibrium_plotly_figure_equation(
    factions_tuple: Tuple[str, ...],
    roles_tuple: Tuple[str, ...],
    only_measured: bool,
) -> go.Figure:
    entries, _meta = _load_equation_calibrated_entries()
    if not entries:
        return go.Figure()
    faction_set = set(factions_tuple) if factions_tuple else None
    role_set = set(roles_tuple)
    filtered = [
        e for e in entries
        if (faction_set is None or e.faction in faction_set)
        and e.role in role_set
        and e.gw_points_per_model > 0
        and e.equilibrium_points_per_model > 0
        and (not only_measured or e.source == "sim")
    ]
    return _build_equilibrium_figure(
        filtered,
        y_axis_title="Equation-calibrated points per model (log)",
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def save_str(save: int) -> str:
    return f"{save}+" if save <= 6 else "none"

def ap_str(ap: int) -> str:
    return str(ap) if ap != 0 else "0"

def unit_card(profile: UnitProfile, name: str, colour: str, cover: bool):
    sv_prob = save_probability(profile.save, in_cover=cover)
    st.markdown(
        f"### <span style='color:{colour}'>{name}</span>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    cols[0].metric("Health", profile.health)
    cols[1].metric("Damage", profile.damage)
    cols[2].metric("Hit", f"{profile.hit_probability:.0%}")
    cols[3].metric("AP", ap_str(profile.ap))
    cols2 = st.columns(3)
    cols2[0].metric("Save", save_str(profile.save))
    cols2[1].metric("Save% (base)", f"{sv_prob:.0%}")
    cols2[2].metric("Pts/unit", f"{profile.points_cost:.0f}")

# ---------------------------------------------------------------------------
# v1.0 release: view-mode toggle + SwegHammer-points switch
# ---------------------------------------------------------------------------
#
# Rendered before the existing sidebar so the wordmark and view toggle sit
# at the top of the sidebar. Player view diverts to a separate render path
# and `st.stop()`s before the existing Calibration code below has a chance
# to execute, so the legacy ~3,500 lines of dashboard logic stay untouched
# whenever a hobbyist user picks the Player view.

st.set_page_config(
    page_title=_APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.markdown(f"## {_APP_TITLE}")
st.sidebar.caption(f"v{__version__}  ·  {_APP_TAGLINE}")
st.sidebar.divider()

_view_mode = st.sidebar.radio(
    "View",
    ["Player", "Calibration"],
    horizontal=True,
    key="sweg_view_mode",
    help=(
        "**Player** shows the curated SwegHammer prices view "
        "(unit browser, faction overview, the equation explained). "
        "**Calibration** is the full technical dashboard with the "
        "simulator, calibration sweeps and the equation-fit internals."
    ),
)

_use_sweg_points = st.sidebar.checkbox(
    "Use SwegHammer points (v1.0)",
    value=(_view_mode == "Player"),
    key="sweg_use_v1_points",
    help=(
        "Swap in the v1 SwegHammer prices for every unit in the "
        "catalogue. Default ON in Player view, OFF in Calibration view. "
        "Toggling off restores the printed GW costs."
    ),
)

# Apply / reset the v1 prices on every rerun so the catalogue state is
# deterministic per script execution. The catalogue dict object is shared
# across reruns inside one Python process — without this reset, stale
# overrides would leak between mode flips.
from code.sweg_points import (  # noqa: E402  (intentional late import)
    apply_to_catalog as _sweg_apply_to_catalog,
    load_sweg_overrides as _sweg_load_overrides,
    reset_catalog_overrides as _sweg_reset_catalog_overrides,
)

_sweg_reset_catalog_overrides(_RAW_CATALOG)
if _use_sweg_points and _SWEG_POINTS_PATH.exists():
    try:
        _sweg_apply_to_catalog(
            _RAW_CATALOG,
            _sweg_load_overrides(_SWEG_POINTS_PATH),
            strict=False,   # tolerate catalogue drift between bakes
        )
    except (FileNotFoundError, ValueError, KeyError) as _e:
        st.sidebar.warning(f"Could not load SwegHammer points: {_e}")

st.sidebar.divider()

# ---------------------------------------------------------------------------
# Player-view tab renderers
# ---------------------------------------------------------------------------
#
# Each renderer is a small function so the tab dispatch reads cleanly.
# Steps 5–6 of the v1 execution plan populate the actual content; for now
# they render placeholders so the structure can be smoke-tested first.

def _load_sweg_dataset():
    """Read the v1 prices file once per rerun (st.cache_data-friendly)."""
    if not _SWEG_POINTS_PATH.exists():
        return None
    return _json.loads(_SWEG_POINTS_PATH.read_text(encoding="utf-8"))


def _render_player_home(sweg_data):
    """Player-mode landing page: wordmark + tagline + intro + jump cards."""
    st.markdown(f"# {_APP_TITLE}")
    st.caption(_APP_TAGLINE + f"  ·  v{__version__}")
    if sweg_data is None:
        st.warning(
            "The v1 SwegHammer prices dataset is missing. Generate it with "
            "`python3 scripts/bake_swegpoints_v1.py` then refresh the page."
        )
        return
    counts = sweg_data.get("counts", {})
    n_units = counts.get("total_units", "?")
    n_mults = len(sweg_data.get("faction_multipliers_active", {}))
    r2 = sweg_data.get("fit_metrics", {}).get("r_squared", "?")
    st.markdown(
        f"**SwegHammer v1.0** prices **{n_units} units** across "
        f"**{n_mults} factions** with active tournament meta multipliers. "
        f"The regression equation fits stat-line features against printed "
        f"GW prices at R² = **{r2}**, then corrects per-faction using the "
        f"Warp Friends May 2026 win-rate snapshot."
    )
    st.divider()
    st.markdown(
        "Use the tabs above to:\n\n"
        "- **Unit Browser** — see every unit's GW price vs SwegHammer "
        "price, sorted by where they disagree most.\n"
        "- **Army Compare** — line two armies up side by side and see "
        "the matchup at a glance.\n"
        "- **Faction Overview** — pick a faction, see its biggest "
        "winners and losers under the SwegHammer rebalance.\n"
        "- **The Equation** — a friendly walk-through of how prices "
        "are derived from stats."
    )
    st.caption("Switch to **Calibration view** in the sidebar for the "
               "full technical dashboard with the simulator and "
               "calibration sweeps.")


def _render_unit_browser(sweg_data):
    st.markdown("## Unit Browser")
    if sweg_data is None:
        st.warning("v1 prices dataset is missing; cannot render the browser.")
        return
    st.caption(
        "Every catalogue unit with its printed GW price and SwegHammer v1 "
        "price side by side. Sort by **|Δ %|** to surface the units the "
        "equation re-priced most. Click a row's expander for the feature "
        "contributions that drove the re-price."
    )

    prices = sweg_data.get("prices", {})
    if not prices:
        st.info("Prices block is empty.")
        return

    # Flatten to a list of dicts for the dataframe.
    rows = []
    for key, rec in prices.items():
        rows.append({
            "key": key,
            "Unit": rec.get("name", key),
            "Faction": rec.get("faction", "—"),
            "GW pts/model": rec.get("gw_pts_per_model"),
            "Sweg pts/model": rec.get("sweg_pts_per_model"),
            "Δ %": rec.get("delta_pct"),
            "Faction mult": rec.get("faction_multiplier"),
            "Method": rec.get("method", ""),
        })
    df = pd.DataFrame(rows)

    # Sidebar-local filters (rendered inside this tab to keep the main
    # sidebar reserved for view-mode controls).
    f_col, s_col, sort_col = st.columns([2.0, 2.0, 1.0])
    with f_col:
        all_factions = sorted(df["Faction"].dropna().unique())
        picked = st.multiselect(
            "Factions", all_factions, default=[],
            placeholder="(all factions)",
            key="sweg_browser_factions",
        )
    with s_col:
        query = st.text_input(
            "Search by unit name", value="",
            placeholder="e.g. Intercessor, Magnus, Hellblade",
            key="sweg_browser_query",
        )
    with sort_col:
        sort_choice = st.selectbox(
            "Sort by",
            ["|Δ %| desc", "Δ % desc", "Δ % asc", "Sweg pts desc",
             "Sweg pts asc", "Unit name"],
            key="sweg_browser_sort",
        )

    view = df
    if picked:
        view = view[view["Faction"].isin(picked)]
    if query.strip():
        view = view[view["Unit"].str.contains(query.strip(), case=False, na=False)]

    if sort_choice == "|Δ %| desc":
        view = view.assign(_abs=view["Δ %"].abs()).sort_values(
            "_abs", ascending=False, na_position="last").drop(columns="_abs")
    elif sort_choice == "Δ % desc":
        view = view.sort_values("Δ %", ascending=False, na_position="last")
    elif sort_choice == "Δ % asc":
        view = view.sort_values("Δ %", ascending=True, na_position="last")
    elif sort_choice == "Sweg pts desc":
        view = view.sort_values("Sweg pts/model", ascending=False)
    elif sort_choice == "Sweg pts asc":
        view = view.sort_values("Sweg pts/model", ascending=True)
    else:
        view = view.sort_values("Unit")

    st.caption(f"Showing **{len(view)} / {len(df)}** units.")
    st.dataframe(
        view.drop(columns=["key", "Method"]),
        hide_index=True,
        use_container_width=True,
        height=520,
        column_config={
            "GW pts/model":   st.column_config.NumberColumn(format="%.1f"),
            "Sweg pts/model": st.column_config.NumberColumn(format="%d"),
            "Δ %":            st.column_config.NumberColumn(format="%+.1f%%"),
            "Faction mult":   st.column_config.NumberColumn(format="%.2fx"),
        },
    )

    # Inspector — pick a unit, see its full feature contribution breakdown.
    st.divider()
    st.markdown("### Inspect a unit")
    if view.empty:
        st.info("No units match the current filters.")
        return
    visible_keys = view["key"].tolist()
    visible_names = view["Unit"].tolist()
    label_to_key = {f"{n}  ({k})": k for n, k in zip(visible_names, visible_keys)}
    pick_label = st.selectbox(
        "Pick a unit from the filtered list",
        list(label_to_key.keys()),
        key="sweg_browser_inspect",
    )
    pick_key = label_to_key[pick_label]
    rec = prices[pick_key]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GW pts/model", f"{rec['gw_pts_per_model']:.1f}")
    c2.metric("Sweg pts/model", f"{rec['sweg_pts_per_model']}")
    delta = rec.get("delta_pct")
    c3.metric("Δ %", f"{delta:+.1f}%" if delta is not None else "—")
    c4.metric("Faction mult", f"{rec.get('faction_multiplier', 1.0):.2f}×")
    st.caption(f"**Method:** {rec.get('method', '?')}")
    st.markdown("**Top feature contributions** (to log(price)):")
    top = rec.get("top_features") or []
    if not top:
        st.info("No top-features recorded for this unit.")
    else:
        contrib_df = pd.DataFrame(top, columns=["Feature", "Contribution"])
        st.dataframe(
            contrib_df, hide_index=True, use_container_width=True,
            column_config={
                "Contribution": st.column_config.NumberColumn(format="%+.4f"),
            },
        )
        st.caption(
            "Each row is `coefficient × transform(feature_value)` — the "
            "additive piece in the equation's log-price prediction. Positive "
            "values push the unit's price up, negative push it down. The "
            "intercept and the remaining feature contributions are also part "
            "of the equation; only the three with largest absolute effect "
            "are listed here."
        )


def _render_army_compare_player():
    st.markdown("## Army Compare")
    st.caption(
        "Pit two armies against one another with the current points "
        "in effect (SwegHammer v1 if the sidebar toggle is on, GW otherwise). "
        "Pick presets or build custom lists, then watch the matchup at a "
        "glance."
    )
    render_compare_tab(st)


def _render_faction_overview(sweg_data):
    st.markdown("## Faction Overview")
    if sweg_data is None:
        st.warning("v1 prices dataset is missing.")
        return
    prices = sweg_data.get("prices", {})
    mults = sweg_data.get("faction_multipliers_active", {})
    if not prices:
        st.info("Prices block is empty.")
        return

    all_factions = sorted({rec["faction"] for rec in prices.values()
                           if rec.get("faction")})
    pick = st.selectbox("Faction", all_factions, key="sweg_faction_pick")

    fac_rows = [rec for rec in prices.values() if rec.get("faction") == pick]
    # Drop super-heavy fallbacks from the over/under-priced lists (their
    # delta is zero by construction).
    re_priced = [r for r in fac_rows
                 if r.get("method") != "gw_fallback_super_heavy"
                 and r.get("delta_pct") is not None]
    n_units = len(fac_rows)
    n_repriced = len(re_priced)

    mult = mults.get(pick)
    # Look up the per-faction tournament win rate from the snapshot if present.
    wf_pct = None
    if _EQUATION_SNAPSHOT_PATH.exists():
        snap = _json.loads(_EQUATION_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        for row in snap.get("factions", []):
            if row.get("faction") == pick and not row.get("is_approx"):
                wf_pct = row.get("tournament_pct")
                break

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Units in catalogue", n_units)
    m2.metric("Re-priced", n_repriced)
    m3.metric("Faction multiplier",
              f"{mult:.2f}×" if mult is not None else "1.00× (default)")
    m4.metric("Warp Friends WR",
              f"{wf_pct:.1f}%" if wf_pct is not None else "—")

    if not re_priced:
        st.info("No re-priced units to break down (every unit is in the "
                "super-heavy GW-fallback bucket).")
        return

    by_delta = sorted(re_priced, key=lambda r: r["delta_pct"])
    top_down = by_delta[:5]
    top_up = list(reversed(by_delta[-5:]))

    st.divider()
    cu, cd = st.columns(2)
    with cu:
        st.markdown("### Equation priced **UP** vs GW")
        st.caption("Units the equation thinks GW under-costs — these are "
                   "the 'fair' prices argue should be higher.")
        df_up = pd.DataFrame(top_up)[["name", "gw_pts_per_model",
                                       "sweg_pts_per_model", "delta_pct"]]
        df_up.columns = ["Unit", "GW", "Sweg", "Δ %"]
        st.dataframe(df_up, hide_index=True, use_container_width=True,
                     column_config={
                         "GW":   st.column_config.NumberColumn(format="%.1f"),
                         "Sweg": st.column_config.NumberColumn(format="%d"),
                         "Δ %":  st.column_config.NumberColumn(format="%+.1f%%"),
                     })
    with cd:
        st.markdown("### Equation priced **DOWN** vs GW")
        st.caption("Units the equation thinks GW over-costs — these come "
                   "down in SwegHammer v1.")
        df_dn = pd.DataFrame(top_down)[["name", "gw_pts_per_model",
                                         "sweg_pts_per_model", "delta_pct"]]
        df_dn.columns = ["Unit", "GW", "Sweg", "Δ %"]
        st.dataframe(df_dn, hide_index=True, use_container_width=True,
                     column_config={
                         "GW":   st.column_config.NumberColumn(format="%.1f"),
                         "Sweg": st.column_config.NumberColumn(format="%d"),
                         "Δ %":  st.column_config.NumberColumn(format="%+.1f%%"),
                     })

    st.divider()
    st.markdown(f"### Δ % across the {pick} catalogue")
    bar_df = pd.DataFrame(re_priced)[["name", "delta_pct"]].sort_values(
        "delta_pct", ascending=False)
    bar_fig = go.Figure(go.Bar(
        x=bar_df["name"], y=bar_df["delta_pct"],
        marker_color=[SWEG_PALETTE["delta_up"] if v >= 0
                      else SWEG_PALETTE["delta_down"]
                      for v in bar_df["delta_pct"]],
        hovertemplate="<b>%{x}</b><br>Δ = %{y:+.1f}%<extra></extra>",
    ))
    bar_fig.add_hline(y=0, line=dict(color=SWEG_PALETTE["neutral_grey"],
                                     width=1))
    bar_fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=SWEG_PALETTE["bg_page"],
        plot_bgcolor=SWEG_PALETTE["bg_panel"],
        xaxis=dict(title="Unit", tickangle=-40,
                   gridcolor=SWEG_PALETTE["grid"], showticklabels=False),
        yaxis=dict(title="Sweg − GW (%)", gridcolor=SWEG_PALETTE["grid"]),
        height=360, margin=dict(l=40, r=20, t=10, b=40),
    )
    st.plotly_chart(bar_fig, use_container_width=True,
                    key="sweg_faction_bar")

    mean_delta = float(np.mean([r["delta_pct"] for r in re_priced]))
    st.caption(f"Mean Δ for {pick}: **{mean_delta:+.1f}%** across "
               f"{n_repriced} re-priced units.")


def _render_equation_lite(sweg_data):
    st.markdown("## The Equation")
    if sweg_data is None:
        st.warning("v1 prices dataset is missing.")
        return

    fit = sweg_data.get("fit_metrics", {})
    r2 = fit.get("r_squared", "?")
    mae_log = fit.get("mae_log", "?")
    mae_price = fit.get("mae_price", None)
    mae_price_str = f"{mae_price:.1f}" if mae_price is not None else "?"
    feat_n = sweg_data.get("feature_count", "?")

    # Headline metrics up top — these are the numbers a viewer should leave with.
    cols = st.columns(4)
    cols[0].metric("Units priced", f"{sweg_data.get('counts', {}).get('total_units', '?')}")
    cols[1].metric("Stat features", f"{feat_n}")
    cols[2].metric("R² vs GW", f"{r2}")
    cols[3].metric("Mean error", f"{mae_price_str} pts/model")

    st.markdown(
        "Every unit is priced by one regression equation over the stat line — "
        "wounds, toughness, save, AP, attacks, damage, hit probability, "
        "secondary weapon profile, special weapon keywords (precision, lance, "
        "assault, indirect fire, anti-X), leader aura buffs, even Necron "
        "reanimation. The equation predicts `log(price per model)`, which is "
        "exponentiated back to a points value and then multiplied by a "
        "**per-faction tournament-meta correction**.\n\n"
        f"The fit lands at **R² = {r2}** against GW's printed prices "
        f"(mean absolute error **{mae_price_str} pts/model**, log-space MAE "
        f"**{mae_log}**)."
    )

    # Family rollups — group correlated features (wounds, wounds², toughness×wounds, …)
    # into one bar per family so the signs are interpretable. Same shape the
    # playtester HTML shows.
    family_rollups = sweg_data.get("family_contributions_avg", {})
    if family_rollups:
        st.divider()
        st.markdown("### What drives a unit's cost?")
        st.caption(
            "Four big buckets the equation cares about — Durability, Offense, "
            "Mobility, Special abilities. Signed mean is the family's average "
            "contribution to log(price) per unit; magnitude shows how much each "
            "family moves prices around. Family rollups instead of raw "
            "coefficients because dozens of correlated features (wounds, wounds², "
            "toughness × wounds, …) cancel out in opposing directions individually "
            "— sums across a whole family are stable and interpretable."
        )
        family_items = [
            (family, float(stats.get("signed_mean", 0)), float(stats.get("abs_mean", 0)))
            for family, stats in family_rollups.items()
        ]
        family_items.sort(key=lambda x: -x[2])
        family_df = pd.DataFrame(
            family_items,
            columns=["Family", "Signed mean", "Magnitude (abs mean)"],
        )
        st.dataframe(
            family_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Signed mean": st.column_config.NumberColumn(
                    format="%+.3f",
                    help="Average signed contribution per unit (gold = adds to price, red = subtracts).",
                ),
                "Magnitude (abs mean)": st.column_config.ProgressColumn(
                    format="%.3f",
                    min_value=0.0,
                    max_value=max((m for _, _, m in family_items), default=1.0),
                    help="Average absolute contribution per unit — how much each family moves prices around.",
                ),
            },
        )

    st.divider()
    st.markdown("### Worked example")
    # Find a canonical infantry workhorse for the worked example. Intercessor
    # Squad is the project's documented baseline.
    target = None
    for key, rec in sweg_data.get("prices", {}).items():
        if "intercessor_squad" in key and "assault" not in key:
            target = (key, rec)
            break
    if target is None:
        # Fallback: any Marine infantry workhorse.
        for key, rec in sweg_data.get("prices", {}).items():
            if rec.get("faction") == "Adeptus Astartes" and rec.get("delta_pct") is not None:
                target = (key, rec)
                break
    if target is None:
        st.info("Could not find a worked-example unit in the dataset.")
        return

    ex_rec = target[1]
    st.markdown(f"**Unit:** {ex_rec['name']}  ·  *{ex_rec['faction']}*")

    cols = st.columns(4)
    cols[0].metric("GW pts/model", f"{ex_rec['gw_pts_per_model']:.1f}")
    cols[1].metric("Equation only",
                   f"{ex_rec['sweg_pts_per_model'] / max(0.001, ex_rec.get('faction_multiplier', 1.0)):.1f}")
    cols[2].metric("Faction mult",
                   f"{ex_rec.get('faction_multiplier', 1.0):.2f}×")
    cols[3].metric("Sweg pts/model", f"{ex_rec['sweg_pts_per_model']}")

    st.markdown("**Top three feature contributions** to this unit's log(price):")
    top = ex_rec.get("top_features") or []
    if top:
        contrib_df = pd.DataFrame(top, columns=["Feature", "Contribution to log(price)"])
        st.dataframe(contrib_df, hide_index=True, use_container_width=True,
                     column_config={
                         "Contribution to log(price)":
                            st.column_config.NumberColumn(format="%+.4f"),
                     })
    st.caption(
        "Each contribution = coefficient × transform(feature value). The "
        "equation sums these (plus contributions from every other feature, "
        "plus an intercept) and exponentiates the result to land on the "
        "per-model price. The faction multiplier then scales that price up "
        "(faction over-performs in real tournaments) or down (under-performs)."
    )

    st.divider()
    st.markdown("### Want the full equation?")
    st.caption(
        "Switch to **Calibration view** in the sidebar and open the "
        "**Equation Fit** tab — it has the full feature panel, the fitted "
        "coefficients, a 3D surface explorer, and the outlier diagnostics."
    )


def _render_player_view():
    """Top-level Player-view dispatcher: builds the five tabs and renders each."""
    sweg_data = _load_sweg_dataset()
    p_home, p_browser, p_compare, p_faction, p_equation = st.tabs(
        ["Home", "Unit Browser", "Army Compare",
         "Faction Overview", "The Equation"]
    )
    with p_home:
        _render_player_home(sweg_data)
    with p_browser:
        _render_unit_browser(sweg_data)
    with p_compare:
        _render_army_compare_player()
    with p_faction:
        _render_faction_overview(sweg_data)
    with p_equation:
        _render_equation_lite(sweg_data)
    st.caption(f"SwegHammer v{__version__}  ·  Player view")


# Player view is a self-contained branch: render the five tabs, then halt
# script execution so none of the Calibration-view code below runs.
if _view_mode == "Player":
    _render_player_view()
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar — controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚔️ SwegHammer")
    st.caption("Battle Simulator")
    st.divider()

    # Points-source toggle. When ON, calibrated_points.json overrides the
    # derived points_for() values for any unit whose calibration converged.
    use_balanced = st.toggle(
        "Use SwegHammer balanced points",
        value=False,
        help=(
            "Off: use the analytic points formula derived from each unit's "
            "stats. On: substitute the empirical points produced by "
            "code/balancer.py for units that converged in calibration. "
            "Useful for A/B-comparing GW-style points vs SwegHammer-balanced."
        ),
    )
    st.divider()

    mode = st.radio(
        "Mode",
        ["Preset Battle", "Custom Battle", "Faction vs Faction (random)"],
        horizontal=False,
    )
    st.divider()

    # Rebind module-level UNIT_CATALOG based on the toggle so downstream
    # widgets (composition picker, preset lookup) and helpers see the right
    # catalogue. Python resolves `UNIT_CATALOG` from app.py's module globals
    # at call time, so this rebind propagates without further plumbing.
    UNIT_CATALOG = balanced_catalog() if use_balanced else _RAW_CATALOG

    if mode == "Preset Battle":
        preset_key = st.selectbox("Choose a preset", list(PRESETS.keys()))
        preset = PRESETS[preset_key]
        st.info(preset["description"])

        a_name = preset["a_name"]
        b_name = preset["b_name"]
        profile_a = UNIT_CATALOG[preset["a_key"]]
        profile_b = UNIT_CATALOG[preset["b_key"]]
        points = st.slider("Points per army", 100, 2000, preset["points"], step=50)
        # Preset uses a homogeneous army filled to the points budget.
        a_count = max(1, int(points // profile_a.points_cost))
        b_count = max(1, int(points // profile_b.points_cost))
        a_comp: List[Tuple[str, int]] = [(preset["a_key"], a_count)]
        b_comp: List[Tuple[str, int]] = [(preset["b_key"], b_count)]
        a_faction = profile_a.faction
        b_faction = profile_b.faction

    elif mode == "Faction vs Faction (random)":
        # --- Faction-vs-faction calibration mode ---------------------------
        st.caption(
            "Each battle rebuilds both armies from a random draw within each "
            "faction's unit pool, respecting BSData squad min/max. Use this to "
            "stress-test the ruleset balance."
        )
        a_faction = st.selectbox(
            "Army A faction", FACTIONS_AVAILABLE,
            index=FACTIONS_AVAILABLE.index("Necrons")
            if "Necrons" in FACTIONS_AVAILABLE else 0,
            key="fvf_a_faction",
        )
        b_faction = st.selectbox(
            "Army B faction", FACTIONS_AVAILABLE,
            index=FACTIONS_AVAILABLE.index("Tyranids")
            if "Tyranids" in FACTIONS_AVAILABLE else 1,
            key="fvf_b_faction",
        )
        a_name = a_faction
        b_name = b_faction
        budget = st.slider(
            "Points per army", 200, 3000, 1000, step=100, key="fvf_budget",
        )
        size_policy = st.radio(
            "Squad size policy",
            ["max", "half_or_max", "random"],
            horizontal=True,
            key="fvf_size_policy",
            help=(
                "max: always take maximum-size squads (competitive default). "
                "half_or_max: 50/50 between half-rounded-up and max. "
                "random: uniform integer between min and max."
            ),
        )

        # Sample preview army per side. Stable across reruns so editing other
        # controls doesn't flicker the preview, but bump on user request via
        # the re-roll button. Actual Run battles use fresh randomness per call.
        if "fvf_reroll_n" not in st.session_state:
            st.session_state["fvf_reroll_n"] = 0
        if st.button("🎲 Re-roll preview armies", key="fvf_reroll_btn"):
            st.session_state["fvf_reroll_n"] += 1
            st.rerun()
        sample_seed = abs(hash((
            a_faction, b_faction, budget, size_policy,
            st.session_state["fvf_reroll_n"],
        ))) & 0xFFFF
        a_comp = _composition_from_random(a_faction, budget, size_policy, sample_seed)
        b_comp = _composition_from_random(b_faction, budget, size_policy, sample_seed + 1)

        # The widgets already publish budget + size_policy under their `key`s,
        # so session_state has them without explicit assignment. The run handler
        # discriminates by `mode` directly.
        points = budget
        # Headline unit for the preview cards = first non-zero
        profile_a = UNIT_CATALOG[next((k for k, n, *_ in a_comp if n > 0), a_comp[0][0])] if a_comp else None
        profile_b = UNIT_CATALOG[next((k for k, n, *_ in b_comp if n > 0), b_comp[0][0])] if b_comp else None

    else:
        # --- Custom: per-army faction filter + multi-unit composition -----
        def _composition_picker(side: str, default_faction: str, default_name: str
                                ) -> Tuple[str, str, List[Tuple[str, int]]]:
            st.subheader(f"Army {side}")
            army_name = st.text_input(
                f"{side} name", value=default_name, key=f"{side}_name",
            )
            faction = st.selectbox(
                f"{side} faction", FACTIONS_AVAILABLE,
                index=FACTIONS_AVAILABLE.index(default_faction)
                if default_faction in FACTIONS_AVAILABLE else 0,
                key=f"{side}_faction",
            )
            available = _units_in_faction(faction)
            if not available:
                st.warning(f"No units in {faction}.")
                return army_name, faction, []

            def _default_size(uk: str) -> int:
                return max(1, UNIT_CATALOG[uk].min_models)

            def _seed():
                # Rows are (unit_key, num_squads, models_per_squad).
                return [(available[0], 1, _default_size(available[0]))]

            state_key = f"{side}_comp"
            if state_key not in st.session_state:
                st.session_state[state_key] = _seed()
            # Reset if any row's unit no longer belongs to the chosen faction.
            if not all(row[0] in available for row in st.session_state[state_key]):
                st.session_state[state_key] = _seed()

            new_comp: List[Tuple[str, int, int]] = []
            for i, row in enumerate(st.session_state[state_key]):
                uk = row[0]
                cnt = int(row[1]) if len(row) > 1 else 1
                cur_size = int(row[2]) if len(row) > 2 else _default_size(uk)
                c1, c2, c3 = st.columns([5, 2, 3])
                chosen = c1.selectbox(
                    f"Unit type {i + 1}", available,
                    index=available.index(uk),
                    format_func=lambda k: UNIT_CATALOG[k].name,
                    key=f"{side}_u_{i}",
                )
                count = c2.number_input(
                    "Squads", min_value=0, max_value=99, value=cnt, step=1,
                    key=f"{side}_c_{i}",
                )
                lo = max(1, UNIT_CATALOG[chosen].min_models)
                hi = max(lo, UNIT_CATALOG[chosen].max_models)
                # Clamp the carried size into the chosen unit's legal range
                # (reset to min if the unit just changed).
                base = cur_size if chosen == uk else lo
                size_val = min(hi, max(lo, base))
                if hi > lo:
                    size = c3.number_input(
                        f"Models/squad ({lo}–{hi})",
                        min_value=lo, max_value=hi, value=size_val, step=1,
                        key=f"{side}_s_{i}",
                    )
                else:
                    c3.caption(f"{lo}-model unit")
                    size = lo
                new_comp.append((chosen, int(count), int(size)))
            st.session_state[state_key] = new_comp

            cc1, cc2 = st.columns(2)
            if cc1.button(f"+ Add unit type", key=f"{side}_add"):
                st.session_state[state_key].append(
                    (available[0], 1, _default_size(available[0]))
                )
                st.rerun()
            if len(new_comp) > 1 and cc2.button("− Remove last", key=f"{side}_rm"):
                st.session_state[state_key].pop()
                st.rerun()

            total_pts = _composition_total_points(new_comp)
            total_squads = sum(n for _, n, _ in new_comp if n > 0)
            total_models = sum(n * sz for _, n, sz in new_comp if n > 0)
            st.caption(f"**{total_pts:.0f} pts** across {total_models} models")
            return army_name, faction, new_comp

        a_name, a_faction, a_comp = _composition_picker(
            "A", default_faction="Necrons", default_name="Necrons",
        )
        b_name, b_faction, b_comp = _composition_picker(
            "B", default_faction="Tyranids", default_name="Tyranids",
        )

        # Make the "points slider" stop driving the simulation in custom mode —
        # composition is count-based — but keep a points slider for the
        # win-rate-vs-points sweep that reuses profile_a/profile_b.
        points = max(
            _composition_total_points(a_comp),
            _composition_total_points(b_comp),
        )
        # profile_a/b are used by the unit card and the points-curve sweep;
        # in mixed mode we surface the *headline* unit (first non-zero).
        profile_a = UNIT_CATALOG[next((k for k, n, *_ in a_comp if n > 0), a_comp[0][0])] if a_comp else None
        profile_b = UNIT_CATALOG[next((k for k, n, *_ in b_comp if n > 0), b_comp[0][0])] if b_comp else None

    st.divider()
    st.subheader("Battlefield")
    # Points to drive map sizing: prefer the points slider in preset/FvF modes,
    # fall back to the composition total in custom.
    points_for_map = float(points) if points else 1000.0

    if mode == "Custom Battle":
        # Custom mode: filter the dropdown to maps that suit the army size,
        # but let the user override.
        fitting = maps_fitting(points_for_map)
        all_keys = list(STOCK_MAPS.keys())
        # Order: fitting ones first, then the rest
        ordered = fitting + [k for k in all_keys if k not in fitting]
        default_key = auto_select_map_key(points_for_map)
        map_key = st.selectbox(
            "Map (default tuned to your army size)",
            ordered,
            index=ordered.index(default_key) if default_key in ordered else 0,
            format_func=lambda k: (
                f"{STOCK_MAPS[k].name}  "
                f"({MAP_POINTS_RANGE[k][0]}–{MAP_POINTS_RANGE[k][1]} pts)"
            ),
        )
    else:
        # Preset / FvF: auto-select based on the points budget. No dropdown.
        map_key = auto_select_map_key(points_for_map)
        lo, hi = MAP_POINTS_RANGE[map_key]
        st.caption(
            f"Auto-selected for {points_for_map:.0f} pts: "
            f"**{STOCK_MAPS[map_key].name}** ({lo}–{hi} pts band)"
        )

    selected_map = STOCK_MAPS[map_key]
    st.caption(
        f"{selected_map.width:.0f}\" x {selected_map.height:.0f}\" "
        f"with {len(selected_map.terrain)} terrain pieces"
    )

    st.divider()
    st.subheader("Terrain (army-wide cover flag)")
    a_cover = st.checkbox(f"🔵 {a_name} in cover", value=False)
    b_cover = st.checkbox(f"🔴 {b_name} in cover", value=False)

    st.divider()
    n_battles = st.slider("Simulations", 1, 1000, 100, step=1)
    show_points_curve = st.checkbox("Show win% vs points curve", value=True)

    st.divider()
    run = st.button("▶  Run Simulation", use_container_width=True, type="primary")

# ---------------------------------------------------------------------------
# Faction colours — re-bound each Streamlit run; chart funcs read globally
# ---------------------------------------------------------------------------

COL_A = colour_for(a_faction) if a_faction else DEFAULT_COL_A
COL_B = colour_for(b_faction) if b_faction else DEFAULT_COL_B
# If both armies share a faction (mirror match), shift B toward a contrasting tone
if a_faction and b_faction and a_faction == b_faction:
    COL_B = DEFAULT_COL_B

# ---------------------------------------------------------------------------
# Army preview
# ---------------------------------------------------------------------------

army_a_preview = _build_army_from_composition(a_name, a_comp, in_cover=a_cover)
army_b_preview = _build_army_from_composition(b_name, b_comp, in_cover=b_cover)

st.title("⚔️ SwegHammer Battle Simulator")


def _ability_glyphs(p: UnitProfile) -> str:
    bits = []
    if p.lethal_hits: bits.append("LH")
    if p.sustained_hits: bits.append(f"SH{p.sustained_hits}")
    if p.twin_linked: bits.append("TL")
    if p.devastating_wounds: bits.append("DW")
    if p.invuln_save <= 6: bits.append(f"inv {p.invuln_save}+")
    return " · ".join(bits) if bits else "—"


def _render_army_overview(
    label: str, faction: str, comp: List[Tuple[str, int]],
    in_cover: bool, colour: str,
) -> None:
    """Table-style army summary: unit rows + totals."""
    st.markdown(
        f"### <span style='color:{colour}'>⬤ {label}</span>"
        f"<span style='color:#aaa;font-weight:normal;font-size:0.85em'>"
        f"  &middot; {faction}{' &middot; 🏠 in cover' if in_cover else ''}"
        f"</span>",
        unsafe_allow_html=True,
    )

    rows = []
    total_models = 0
    total_wounds = 0.0
    total_pts = 0.0
    for unit_key, count, *rest in comp:
        if count <= 0:
            continue
        size = max(1, int(rest[0]) if rest else 1)
        models = count * size
        p = UNIT_CATALOG[unit_key]
        unit_pts = p.points_cost * models
        unit_hp = p.health * models
        sv_str = f"{p.save}+" if p.save <= 6 else "—"
        rows.append({
            "Unit":   p.name,
            "Squads": count,
            "Size":   size,
            "Models": models,
            "W":      f"{p.health:g}",
            "T":      p.toughness,
            "Sv":     sv_str,
            "A×D":    f"{p.attacks}×{p.weapon_damage_per_shot:g}",
            "AP":     p.ap if p.ap else 0,
            "Pts ea": f"{p.points_cost:.0f}",
            "Total":  f"{unit_pts:.0f}",
            "Abil":   _ability_glyphs(p),
        })
        total_models += models
        total_wounds += unit_hp
        total_pts += unit_pts

    if not rows:
        st.caption("_(no units selected)_")
        return

    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(
        f"**{total_models}** models  ·  "
        f"**{total_wounds:g}** total wounds  ·  "
        f"**{total_pts:.0f}** pts"
    )


col1, col_vs, col2 = st.columns([5, 1, 5])

with col1:
    _render_army_overview(a_name, a_faction, a_comp, a_cover, COL_A)

with col_vs:
    st.markdown(
        "<div style='text-align:center;font-size:2rem;padding-top:5rem'>⚡</div>",
        unsafe_allow_html=True,
    )

with col2:
    _render_army_overview(b_name, b_faction, b_comp, b_cover, COL_B)

st.divider()

# ---------------------------------------------------------------------------
# Run and display results
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Run handler — populates st.session_state with stats results and one replay
# ---------------------------------------------------------------------------

if run:
    _spec_a = None
    _spec_b = None
    if mode == "Faction vs Faction (random)":
        budget = st.session_state.get("fvf_budget", 1000)
        size_policy = st.session_state.get("fvf_size_policy", "max")
        factory_a = lambda: build_faction_random_army(
            a_name, a_faction, budget, in_cover=a_cover, size_policy=size_policy,
        )
        factory_b = lambda: build_faction_random_army(
            b_name, b_faction, budget, in_cover=b_cover, size_policy=size_policy,
        )
    else:
        factory_a = lambda: _build_army_from_composition(a_name, a_comp, in_cover=a_cover)
        factory_b = lambda: _build_army_from_composition(b_name, b_comp, in_cover=b_cover)
        _spec_a = _army_spec_from_composition(a_name, a_comp, in_cover=a_cover)
        _spec_b = _army_spec_from_composition(b_name, b_comp, in_cover=b_cover)

    _battle_bar = st.progress(0, text=f"Running battles… 0 / {n_battles:,}")
    def _battle_progress(done: int, total: int) -> None:
        _battle_bar.progress(done / total, text=f"Running battles… {done:,} / {total:,}")

    results = run_simulations(
        factory_a, factory_b, n_battles,
        map_=selected_map, on_progress=_battle_progress,
        spec_a=_spec_a, spec_b=_spec_b,
    )
    _battle_bar.empty()

    # Pick a replay that's REPRESENTATIVE of the stats: same winner as
    # the modal outcome, with survivor counts close to the mean. We
    # roll fresh replays until we find a match, capped to avoid
    # pathological cases (e.g. very stochastic mirror matches where
    # no single roll is "average").
    a_wins_n, b_wins_n, draws_n = aggregate(results, a_name, b_name)
    if a_wins_n >= b_wins_n and a_wins_n >= draws_n:
        target_winner = a_name
    elif b_wins_n >= draws_n:
        target_winner = b_name
    else:
        target_winner = None  # Modal outcome is a draw
    winning_results = [
        r for r in results
        if (r.winner == target_winner if target_winner else r.winner is None)
    ]
    if winning_results:
        mean_a_surv = sum(r.a_survivors for r in winning_results) / len(winning_results)
        mean_b_surv = sum(r.b_survivors for r in winning_results) / len(winning_results)
    else:
        mean_a_surv = mean_b_surv = 0.0

    def _score(res) -> float:
        # Lower = more representative. Mismatched winner is a hard
        # penalty so it never beats a correct-winner battle.
        winner_match = (
            (res.winner == target_winner) if target_winner
            else (res.winner is None)
        )
        penalty = 0.0 if winner_match else 1e6
        surv_dist = abs(res.a_survivors - mean_a_surv) + abs(res.b_survivors - mean_b_surv)
        return penalty + surv_dist

    best_log = None
    best_result = None
    best_score = float("inf")
    with st.spinner("Capturing representative replay…"):
        for _ in range(5):
            log = EventLog()
            res = Battle(
                factory_a(), factory_b(), subscribers=[log], map_=selected_map,
            ).run()
            score = _score(res)
            if score < best_score:
                best_score, best_log, best_result = score, log, res
            if score < 1e6 and (res.a_survivors - mean_a_surv) ** 2 + (res.b_survivors - mean_b_surv) ** 2 <= 1.0:
                break   # Close-enough match — stop rolling.

    log = best_log if best_log is not None else EventLog()
    # Pre-compute the activation-frame index once per run so the Replay
    # tab's slider doesn't recompute it on every tick.
    replay_frames = aggregate_activations(log.events)

    replay_id = st.session_state.get("replay_id", 0) + 1
    st.session_state.update({
        "results": results,
        "a_name": a_name,
        "b_name": b_name,
        "n_battles": n_battles,
        "show_points_curve": show_points_curve,
        "profile_a": profile_a,
        "profile_b": profile_b,
        "a_cover": a_cover,
        "b_cover": b_cover,
        "replay_events": log.events,
        "replay_frames": replay_frames,
        # Monotonic id so the per-PNG cache below knows when to discard old
        # entries (new run = bump the id, old cached frames become unreachable).
        "replay_id": replay_id,
        "replay_map": selected_map,
        # Faction colours flow to the Replay renderer.
        "replay_colour_a": COL_A,
        "replay_colour_b": COL_B,
    })
    # Pre-render EVERY replay frame inside the existing spinner. The slider
    # then just indexes a list of PNG bytes — zero matplotlib / Streamlit
    # rerun cost per scrub tick. ~22 KB × N frames stays well under the
    # session_state size budget.
    if replay_frames:
        _replay_bar = st.progress(0, text="Rendering replay frames…")
        st.session_state["replay_pngs"] = []
        for _fi in range(len(replay_frames)):
            st.session_state["replay_pngs"].append(_render_frame_png(replay_id, _fi))
            _replay_bar.progress((_fi + 1) / len(replay_frames),
                                 text=f"Rendering replay frames… {_fi + 1} / {len(replay_frames)}")
        _replay_bar.empty()
    else:
        st.session_state["replay_pngs"] = []

    # Pre-compute the points-curve data here too if the toggle is on.
    # Otherwise the Statistics tab re-runs ~2200 simulations on every
    # script re-execution (incl. tab switches) — the actual cause of
    # the multi-second "Watch a battle" tab-click delay.
    if show_points_curve and profile_a and profile_b:
        point_values = list(range(100, 601, 50))
        a_rates_p, b_rates_p, draw_rates_p = [], [], []
        _curve_bar = st.progress(0, text="Sweeping point budgets…")
        for _ci, pts in enumerate(point_values):
            _curve_bar.progress(
                (_ci + 1) / len(point_values),
                text=f"Sweeping point budgets… {pts} pts  ({_ci + 1}/{len(point_values)})",
            )
            res = run_simulations(
                lambda p=pts: build_homogeneous_army(a_name, profile_a, p, in_cover=a_cover),
                lambda p=pts: build_homogeneous_army(b_name, profile_b, p, in_cover=b_cover),
                200, map_=selected_map,
            )
            aw, bw, d = aggregate(res, a_name, b_name)
            a_rates_p.append(aw / 200)
            b_rates_p.append(bw / 200)
            draw_rates_p.append(d / 200)
        _curve_bar.empty()
        st.session_state["points_curve_data"] = (
            point_values, a_rates_p, b_rates_p, draw_rates_p,
        )
    else:
        st.session_state["points_curve_data"] = None

# ---------------------------------------------------------------------------
# Tabs: Home + Statistics + Watch a battle + …
# ---------------------------------------------------------------------------
#
# v1.0 added a Home tab at the front of the Calibration view as the default
# landing — it shows the headline calibration metrics and a small
# MAE-history line chart, so the dashboard opens to "where are we" rather
# than the empty Statistics tab.

(tab_home, tab_stats, tab_replay, tab_efficiency, tab_equilibrium,
 tab_compare, tab_convergence, tab_calibration, tab_equation_fit) = st.tabs(
    ["Home", "Statistics", "Watch a battle", "Efficiency", "Equilibrium",
     "Compare", "Convergence", "Calibration", "Equation Fit"]
)

# --- Calibration Home tab ---
with tab_home:
    st.markdown(f"# {_APP_TITLE}")
    st.caption(f"v{__version__}  ·  Calibration view  ·  {_APP_TAGLINE}")
    st.divider()
    st.markdown("### Headline metrics")

    # Pull the freshest numbers we can find on disk.
    _ch_mae = None
    if _EQUATION_SNAPSHOT_PATH.exists():
        try:
            _ch_snap = _json.loads(_EQUATION_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            _ch_mae = _ch_snap.get("mae_real_all")
        except (ValueError, OSError):
            _ch_mae = None
    _ch_sweg_meta = None
    if _SWEG_POINTS_PATH.exists():
        try:
            _ch_sweg_meta = _json.loads(_SWEG_POINTS_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            _ch_sweg_meta = None

    _hc1, _hc2, _hc3, _hc4 = st.columns(4)
    _hc1.metric(
        "Sim MAE vs Warp Friends",
        f"{_ch_mae:.2f} pts" if _ch_mae is not None else "—",
        help="Headline calibration metric. Target ≤ 2.0. Loaded from "
             "data/equation_vs_meta_snapshot.json.",
    )
    if _ch_sweg_meta:
        _hc2.metric(
            "Equation R²",
            f"{_ch_sweg_meta['fit_metrics']['r_squared']}",
            help="Regression fit quality vs printed GW prices.",
        )
        _hc3.metric(
            "Units priced",
            _ch_sweg_meta["counts"]["total_units"],
            help="Total catalogue size covered by the v1 dataset.",
        )
        _hc4.metric(
            "Active faction multipliers",
            len(_ch_sweg_meta.get("faction_multipliers_active", {})),
            help="Factions with real Warp Friends tournament data feeding "
                 "the multiplier; the rest default to 1.0×.",
        )
    else:
        _hc2.metric("Equation R²", "—")
        _hc3.metric("Units priced", "—")
        _hc4.metric("Active faction multipliers", "—")

    # MAE history mini-chart from docs/mae_progress.csv.
    if _MAE_PROGRESS_PATH.exists():
        _mae_rows = []
        try:
            with _MAE_PROGRESS_PATH.open(encoding="utf-8") as _fh:
                for _row in _csv.DictReader(_fh):
                    if _row.get("parked", "False").strip().lower() == "true":
                        continue
                    try:
                        _mae_rows.append({
                            "when":  _row["when"],
                            "label": _row["label"],
                            "mae":   float(_row["mae"]),
                        })
                    except (KeyError, ValueError):
                        continue
        except OSError:
            _mae_rows = []

        if _mae_rows:
            _mae_df = pd.DataFrame(_mae_rows)
            _mae_fig = go.Figure(go.Scatter(
                x=_mae_df["when"], y=_mae_df["mae"],
                mode="lines+markers",
                line=dict(color=SWEG_PALETTE["line_blue"], width=1.6),
                marker=dict(size=5, color=SWEG_PALETTE["accent_gold"]),
                hovertemplate="%{x}<br>MAE = %{y:.2f}<br>%{text}<extra></extra>",
                text=_mae_df["label"],
            ))
            _mae_fig.add_hline(y=2.0, line=dict(color=SWEG_PALETTE["delta_up"],
                                                dash="dash", width=1),
                               annotation_text="target 2.0",
                               annotation_position="bottom right")
            _mae_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor=SWEG_PALETTE["bg_page"],
                plot_bgcolor=SWEG_PALETTE["bg_panel"],
                xaxis=dict(title="When",
                           gridcolor=SWEG_PALETTE["grid"],
                           showticklabels=False),
                yaxis=dict(title="MAE (pts)",
                           gridcolor=SWEG_PALETTE["grid"]),
                height=240, margin=dict(l=40, r=20, t=10, b=30),
            )
            st.markdown("### MAE history")
            st.plotly_chart(_mae_fig, use_container_width=True,
                            key="cal_home_mae_history")

    st.divider()
    st.markdown("### Quick jump")
    st.markdown(
        "- **Equation Fit** — feature panel, fitted coefficients, 3D "
        "surface, outliers, tournament-list validation.\n"
        "- **Convergence** — live calibration sweep with streaming updates.\n"
        "- **Calibration** — run an evaluate-vs-meta sweep from the GUI.\n"
        "- **Compare** — pit two armies head to head.\n"
        "- **Statistics / Watch a battle / Efficiency / Equilibrium** — "
        "the original sim-driven tabs."
    )
    st.caption("Switch to **Player view** in the sidebar for the curated "
               "SwegHammer prices view (unit browser, faction overview, "
               "equation explainer).")

# --- Statistics tab ---
with tab_stats:
    if "results" not in st.session_state:
        st.info("Configure your armies in the sidebar and hit **Run Simulation** to begin.")
        st.markdown(
            """
            **Charts you'll see here:**
            - **Win rate pie** — overall win/draw/loss breakdown
            - **Attrition curve** — average units alive per round
            - **Survivor histogram** — distribution of surviving units
            - **Win% vs points** — how the matchup shifts as budgets scale
            """
        )
    else:
        results = st.session_state["results"]
        a_lbl = st.session_state["a_name"]
        b_lbl = st.session_state["b_name"]
        n = st.session_state["n_battles"]

        a_wins, b_wins, draws = aggregate(results, a_lbl, b_lbl)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"🔵 {a_lbl} wins", f"{a_wins/n:.1%}", f"{a_wins} battles")
        m2.metric(f"🔴 {b_lbl} wins", f"{b_wins/n:.1%}", f"{b_wins} battles")
        m3.metric("Draws", f"{draws/n:.1%}", f"{draws} battles")
        m4.metric("Avg rounds", f"{sum(r.rounds for r in results)/n:.1f}")

        # New VP + points-remaining metrics — primary score under the new
        # win condition (objectives + remaining points + attrition wipe).
        avg_a_vp = sum(r.a_vp for r in results) / n
        avg_b_vp = sum(r.b_vp for r in results) / n
        avg_a_pts_rem = sum(r.a_points_remaining for r in results) / n
        avg_b_pts_rem = sum(r.b_points_remaining for r in results) / n
        v1, v2, v3, v4 = st.columns(4)
        v1.metric(f"🔵 avg VP", f"{avg_a_vp:.1f}", f"primary scoring")
        v2.metric(f"🔴 avg VP", f"{avg_b_vp:.1f}", f"primary scoring")
        v3.metric(f"🔵 pts left", f"{avg_a_pts_rem:.0f}", f"end-of-game")
        v4.metric(f"🔴 pts left", f"{avg_b_pts_rem:.0f}", f"end-of-game")

        st.divider()

        c_pie, c_attr = st.columns([2, 3])
        with c_pie:
            st.pyplot(chart_win_rates(a_wins, b_wins, draws, a_lbl, b_lbl, n))
        with c_attr:
            st.pyplot(chart_attrition(results, a_lbl, b_lbl))

        st.divider()
        st.pyplot(chart_survivor_histogram(results, a_lbl, b_lbl))

        # VP margin distribution — how decisive were the wins?
        st.divider()
        vp_margins = [r.a_vp - r.b_vp for r in results]
        fig_vp, ax_vp = plt.subplots(figsize=(8, 3.0))
        fig_vp.patch.set_facecolor("#0e1117")
        ax_vp.set_facecolor("#1a1d23")
        ax_vp.hist(vp_margins, bins=21, color="#7a9ec7", edgecolor="#0e1117")
        ax_vp.axvline(0, color="white", linestyle="--", linewidth=1, alpha=0.6)
        ax_vp.set_xlabel(f"VP margin  ({a_lbl} − {b_lbl})", color="#aaa", fontsize=9)
        ax_vp.set_ylabel("Battles", color="#aaa", fontsize=9)
        ax_vp.set_title("VP margin distribution — how close were the games?",
                        color="white", fontsize=11)
        ax_vp.tick_params(colors="#aaa")
        for s in ax_vp.spines.values():
            s.set_edgecolor("#333")
        fig_vp.tight_layout()
        st.pyplot(fig_vp)

        if st.session_state.get("show_points_curve"):
            curve = st.session_state.get("points_curve_data")
            if curve is not None:
                st.divider()
                st.pyplot(
                    chart_win_rate_vs_points(
                        st.session_state["profile_a"], st.session_state["profile_b"],
                        a_lbl, b_lbl,
                        st.session_state["a_cover"], st.session_state["b_cover"],
                        n_battles=200,
                        map_=st.session_state["replay_map"],
                        precomputed=curve,
                    )
                )

# --- Replay tab ---
with tab_replay:
    if "replay_events" not in st.session_state:
        st.info(
            "Configure your armies and hit **Run Simulation** to load a replay. "
            "One full battle is recorded each time you run."
        )
    else:
        events = st.session_state["replay_events"]
        map_ = st.session_state["replay_map"]
        total = len(events)

        if total == 0:
            st.warning("No events recorded.")
        else:
            # Frames are pre-computed once at run time (see the run handler
            # above) and stored in session state — avoids the O(N) aggregate
            # walk on every slider tick.
            frames = st.session_state.get("replay_frames") or aggregate_activations(events)
            total_frames = len(frames)

            frame_idx = st.slider(
                "Frame (drag to scrub through the battle)",
                min_value=0,
                max_value=max(0, total_frames - 1),
                value=0,
                key="replay_tick",
            )

            col_map, col_log = st.columns([3, 2])

            with col_map:
                # Replay PNGs are pre-rendered at run time into a list —
                # scrubbing is a Python list index, no rendering work.
                pngs = st.session_state.get("replay_pngs") or []
                if pngs:
                    st.image(pngs[frame_idx], use_container_width=True)
                else:
                    png = _render_frame_png(
                        st.session_state["replay_id"], frame_idx,
                    )
                    st.image(png, use_container_width=True)

            with col_log:
                st.markdown("**Current activation**")
                st.code(
                    frame_description(events, frames[frame_idx]),
                    language=None,
                )

                st.markdown("**Recent activations**")
                start_frame = max(0, frame_idx - 6)
                recent_blocks = [
                    frame_description(events, frames[i])
                    for i in range(start_frame, frame_idx + 1)
                ]
                st.text("\n".join(recent_blocks))

                st.caption(
                    f"{total_frames} frames  ·  {total} raw events total"
                )

# ---------------------------------------------------------------------------
# Efficiency tab — Lanchester score vs points cost scatter
# ---------------------------------------------------------------------------

with tab_efficiency:
    st.markdown("## Lanchester Score vs Points Cost")
    st.caption(
        "Each dot is one unit. "
        "X = points cost (derived or override). "
        "Y = Lanchester score (DPS × durability vs baseline Marine). "
        "Dots above the trend line are good value; below are expensive for their combat power."
    )

    # Collect data from the full catalogue
    _eff_names: list[str] = []
    _eff_pts: list[float] = []
    _eff_scores: list[float] = []
    _eff_factions: list[str] = []
    _eff_colours: list[str] = []

    for _key, _u in UNIT_CATALOG.items():
        _pts = _u.points_cost
        _sc = _u.score
        if _pts <= 0 or _sc <= 0:
            continue
        _eff_names.append(_u.name)
        _eff_pts.append(_pts)
        _eff_scores.append(_sc)
        _eff_factions.append(_u.faction)
        _eff_colours.append(colour_for(_u.faction))

    if not _eff_pts:
        st.warning("No units found in catalogue.")
    else:
        # --- faction filter ---
        _all_factions = sorted(set(_eff_factions))
        _selected_factions = st.multiselect(
            "Filter factions",
            options=_all_factions,
            default=_all_factions,
            key="eff_faction_filter",
        )

        # Apply filter
        _mask = [f in _selected_factions for f in _eff_factions]
        _f_names   = [v for v, m in zip(_eff_names,   _mask) if m]
        _f_pts     = [v for v, m in zip(_eff_pts,     _mask) if m]
        _f_scores  = [v for v, m in zip(_eff_scores,  _mask) if m]
        _f_colours = [v for v, m in zip(_eff_colours, _mask) if m]
        _f_factions= [v for v, m in zip(_eff_factions,_mask) if m]

        # --- scatter plot ---
        _fig_eff, _ax_eff = plt.subplots(figsize=(12, 7))
        _fig_eff.patch.set_facecolor("#0e1117")
        _ax_eff.set_facecolor("#1a1d23")

        _ax_eff.scatter(
            _f_pts, _f_scores,
            c=_f_colours,
            s=40, alpha=0.8, linewidths=0.4, edgecolors="white",
        )

        # Trend line — linear fit in log-log space (power-law relationship)
        _pts_arr = np.array(_f_pts, dtype=float)
        _sc_arr  = np.array(_f_scores, dtype=float)
        if len(_pts_arr) >= 2:
            _m, _b = np.polyfit(np.log10(_pts_arr), np.log10(_sc_arr), 1)
            _x_line = np.logspace(np.log10(_pts_arr.min()), np.log10(_pts_arr.max()), 300)
            _y_line = 10 ** (_b + _m * np.log10(_x_line))
            _ax_eff.plot(_x_line, _y_line, color="#FFD700", linewidth=1.2,
                         linestyle="--", label=f"trend  (slope {_m:.2f})", zorder=3)

        # Label the 10 most efficient outliers (score / pts)
        _eff_ratio = _sc_arr / _pts_arr
        _top_idx   = np.argsort(_eff_ratio)[-10:]
        for _i in _top_idx:
            _ax_eff.annotate(
                _f_names[_i],
                (_f_pts[_i], _f_scores[_i]),
                fontsize=6, color="white", alpha=0.9,
                xytext=(4, 3), textcoords="offset points",
            )

        # Legend: one entry per faction that's visible
        _seen: set[str] = set()
        for _fn, _fc in zip(_f_factions, _f_colours):
            if _fn not in _seen:
                _seen.add(_fn)
                _ax_eff.scatter([], [], color=_fc, s=30, label=_fn)

        _ax_eff.legend(
            loc="upper left", fontsize=7,
            facecolor="#1a1d23", edgecolor="#444", labelcolor="white",
            ncol=max(1, len(_seen) // 20),
        )

        _ax_eff.set_xscale("log")
        _ax_eff.set_yscale("log")
        _ax_eff.set_xlabel("Points cost  (log scale)", color="white", fontsize=11)
        _ax_eff.set_ylabel("Lanchester score  (log scale)", color="white", fontsize=11)
        _ax_eff.set_title("Lanchester score vs Points cost", color="white", fontsize=13, pad=10)
        _ax_eff.tick_params(colors="white", which="both")
        for _spine in _ax_eff.spines.values():
            _spine.set_edgecolor("#444")

        _fig_eff.tight_layout()
        st.pyplot(_fig_eff)

        # --- efficiency ranking table ---
        st.divider()
        st.markdown("### Efficiency ranking  (Lanchester score ÷ points)")
        _eff_rows = sorted(
            [
                {
                    "Unit": _f_names[i],
                    "Faction": _f_factions[i],
                    "Points": round(_f_pts[i], 1),
                    "Lanchester score": round(_f_scores[i], 4),
                    "Score / pt": round(_eff_ratio[i], 5),
                }
                for i in range(len(_f_names))
            ],
            key=lambda r: r["Score / pt"],
            reverse=True,
        )
        st.dataframe(_eff_rows, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Equilibrium tab — Phase 1 fair-points solver
# ---------------------------------------------------------------------------
with tab_equilibrium:
    st.markdown("## Equilibrium points  —  Phase 1 (shooting only)")
    st.caption(
        "What SHOULD a unit cost if balance were perfect? "
        "We treat the catalogue as a symmetric zero-sum game, compute every "
        "pairwise time-to-kill, and solve for points that make every duel "
        "mutually destructive in equal time."
    )

    # ---- Math explainer ----
    with st.expander("How the math works", expanded=False):
        st.markdown(
            "**Step 1 — Pairwise damage.**  For every ordered pair of units "
            "$(i, j)$ we compute the expected unsaved damage one model of $i$ "
            "deals to one model of $j$ in a single shooting phase, accounting "
            "for hit, wound (S vs T table), AP-vs-save, invuln, FNP, and the "
            "stateless weapon keywords (Lethal Hits, Sustained Hits, "
            "Twin-Linked, Devastating Wounds, Anti-X)."
        )
        st.latex(
            r"D[i,j] = n_i \cdot p_{\text{hit}} \cdot p_{\text{wound}}(S_i, T_j) "
            r"\cdot p_{\text{fail save}}(\text{save}_j, AP_i, \text{inv}_j) "
            r"\cdot d_i \cdot \left(1 - p_{\text{FNP}_j}\right)"
        )
        st.markdown("**Step 2 — Time-to-kill.**")
        st.latex(r"T[i,j] = \frac{W_j}{D[i,j]}")
        st.markdown(
            "**Step 3 — Fair-trade condition.**  Field $p_j$ points of $i$ "
            "vs $p_j$ points of $j$ (equal budget). The side that wipes "
            "first is the cheaper-per-model unit. Solving for "
            "mutual destruction at the same instant:"
        )
        st.latex(r"\left(\frac{p_i}{p_j}\right)^2 = \frac{T[j,i]}{T[i,j]}")
        st.markdown(
            "Take logs and you get a linear equation in $\\log p$:"
        )
        st.latex(
            r"\log p_i - \log p_j \;=\; \tfrac{1}{2} \log\!\frac{T[j,i]}{T[i,j]} "
            r"\;\equiv\; R[i,j]"
        )
        st.markdown(
            "**Step 4 — Closed-form solve.**  $R$ is skew-symmetric; the LSQ "
            "optimum for $\\log p$ is the row mean (Bradley-Terry / PageRank "
            "structure):"
        )
        st.latex(
            r"\log p_i \;=\; \tfrac{1}{n}\sum_{j \neq i} R[i,j] \;+\; \text{anchor shift}"
        )
        st.markdown(
            "The **anchor** pins one unit's per-model cost (default: "
            "Intercessor @ 16 pts) to fix the overall scale. Everything else "
            "is relative.\n\n"
            "**Phase 1 limitations** (deferred to later phases — see "
            "`code/equilibrium.py`):\n"
            "- Shooting only (no melee, no charge value)\n"
            "- No leader auras / detachment buffs\n"
            "- No tactical utility: move, OC, deep strike, sticky objectives\n"
            "- No meta-weighting of matchups (all pairs equal weight)\n"
            "- No proper Nash mixed-strategy solve (would handle "
            "rock-paper-scissors mispricing)\n\n"
            "So aura-heavy characters and chaff swarms will look mispriced — "
            "the model can't see what they're actually good at yet."
        )

    # ---- Source toggle: closed-form vs sim-driven snapshot ----
    # Closed-form Phase 1 is fast and recomputes on every interaction — it
    # only sees the datasheet. Sim-driven loads a pre-built JSON of pairwise
    # win-rates measured by the actual simulator, so faction army rules /
    # detachment passives / leader auras / movement / charges all feed
    # through to the points. The snapshot is built by
    # `python -m code.equilibrium_simdriven` and lives at
    # `data/equilibrium_points_simdriven.json`.
    _simdriven_snapshot = load_eq_simdriven_snapshot()
    _has_simdriven = _simdriven_snapshot is not None
    _has_equation = _EQUATION_CALIBRATED_PATH.exists()
    _source_options = ["Closed-form Phase 1 (live)"]
    if _has_simdriven:
        _source_options.append("Sim-driven (snapshot)")
    if _has_equation:
        _source_options.append("Equation-calibrated (snapshot)")
    _eq_source = st.radio(
        "Solver source",
        _source_options,
        horizontal=True,
        key="eq_source",
        help=(
            "Closed-form Phase 1 derives points from datasheet stats only — "
            "fast, but blind to faction rules and tactics. "
            "Sim-driven measures win rates from real Battle() runs at equal "
            "points; the snapshot is built offline by "
            "`python -m code.equilibrium_simdriven`. "
            "Equation-calibrated loads `data/equation_calibrated_points.json` "
            "from `scripts/fit_equation_calibrated.py` — fit only on factions "
            "whose simulator MAE is within threshold of real tournament data."
        ),
    )
    _use_simdriven = (_eq_source == "Sim-driven (snapshot)")
    _use_equation  = (_eq_source == "Equation-calibrated (snapshot)")
    if not _has_simdriven:
        st.caption(
            "No sim-driven snapshot found. Build one with "
            "`python -m code.equilibrium_simdriven` to enable the "
            "sim-driven view (the diagnostic subset takes ~5–10 minutes; "
            "`--full` is overnight)."
        )
    if not _has_equation:
        st.caption(
            "No equation-calibrated snapshot found. Build one from the "
            "Calibration tab (Step 1) or with "
            "`python -m scripts.fit_equation_calibrated`."
        )

    # ---- Controls ----
    st.divider()
    _col_anchor, _col_anchor_pts, _col_role = st.columns([3, 1, 2])

    _shooty_keys = sorted([k for k, u in UNIT_CATALOG.items()
                           if u.attacks > 0 and u.range_inches > 0])
    _default_anchor = (
        EQ_DEFAULT_ANCHOR if EQ_DEFAULT_ANCHOR in _shooty_keys else _shooty_keys[0]
    )
    _anchor_locked = _use_simdriven or _use_equation
    with _col_anchor:
        _anchor_key = st.selectbox(
            "Anchor unit  (its cost is held fixed; everything else floats)",
            _shooty_keys,
            index=_shooty_keys.index(_default_anchor),
            format_func=lambda k: f"{UNIT_CATALOG[k].name}  —  {UNIT_CATALOG[k].faction}",
            key="eq_anchor_key",
            disabled=_anchor_locked,
            help=(
                "Anchor is fixed by the snapshot when using a pre-built source; "
                "rebuild the snapshot with a different `--anchor` to change it."
                if _anchor_locked else None
            ),
        )
    with _col_anchor_pts:
        _default_anchor_pts = float(
            UNIT_CATALOG[_anchor_key].points_per_squad /
            max(1, UNIT_CATALOG[_anchor_key].min_models)
        )
        if _default_anchor_pts <= 0:
            _default_anchor_pts = EQ_DEFAULT_ANCHOR_PTS
        _anchor_pts = st.number_input(
            "Anchor pts / model",
            min_value=1.0, max_value=2000.0,
            value=_default_anchor_pts,
            step=1.0,
            key="eq_anchor_pts",
            disabled=_anchor_locked,
        )
    with _col_role:
        _role_filter = st.multiselect(
            "Role filter",
            options=["shooty", "dual"],
            default=["shooty", "dual"],
            key="eq_role_filter",
            help="`shooty` = no melee profile, `dual` = also has melee. Pure-melee units are excluded from Phase 1.",
        )

    # ---- Cached compute (closed-form) ----
    @st.cache_data(show_spinner="Solving equilibrium points…")
    def _equilibrium_result(anchor_key: str, anchor_pts: float):
        # Catalog identity matters (raw vs balanced) but it's not hashable, so
        # we just key on the user-controlled args. Cache invalidates when the
        # process restarts, which is acceptable for an exploratory view.
        return compute_equilibrium_phase1(
            catalog=UNIT_CATALOG,
            anchor_key=anchor_key,
            anchor_per_model=anchor_pts,
        )

    # ---- Snapshot loader (sim-driven) ----
    # The snapshot is a dict of entry-dicts; the chart and table code path
    # below uses attribute access on entries (e.g. `e.gw_points_per_model`),
    # so we wrap each row in SimpleNamespace to keep that code unchanged.
    # The drill-down section needs a full `EquilibriumResult` with D/T/R
    # matrices and is skipped when sim-driven is active (the snapshot does
    # not carry the matrices — we'd have to re-measure to populate them).
    @st.cache_data(show_spinner="Loading sim-driven snapshot…")
    def _equilibrium_simdriven_entries():
        from types import SimpleNamespace
        if _simdriven_snapshot is None:
            return [], {}
        units = _simdriven_snapshot.get("units", {})
        entries = [SimpleNamespace(**row) for row in units.values()]
        meta = {k: v for k, v in _simdriven_snapshot.items() if k != "units"}
        return entries, meta

    if _use_simdriven:
        _simdriven_entries, _simdriven_meta = _equilibrium_simdriven_entries()
        _anchor_key = _simdriven_meta.get("anchor_key", _anchor_key)
        _anchor_pts = float(_simdriven_meta.get("anchor_per_model", _anchor_pts))
        # Surface snapshot provenance so the user sees what they're looking at.
        _measured = _simdriven_meta.get("measured_keys", [])
        st.caption(
            f"Snapshot: **{_simdriven_meta.get('battles_run', 0):,} battles** "
            f"({_simdriven_meta.get('n_battles_per_pair', 0)}× per pair) "
            f"at {_simdriven_meta.get('points_budget', 0):.0f}-pt budget, "
            f"{len(_measured)} units measured, "
            f"wall-clock {_simdriven_meta.get('wall_clock_sec', 0):.0f}s. "
            f"Units outside the measured set inherit their closed-form "
            f"Phase 1 value (marked `phase1_fallback`)."
        )
        _result = None  # No D/T/R matrices in sim-driven; drill-down disabled.
        _result_entries = _simdriven_entries
    elif _use_equation:
        _equation_entries, _equation_meta = _load_equation_calibrated_entries()
        _anchor_key = _equation_meta.get("anchor_key", _anchor_key)
        _anchor_pts = float(_equation_meta.get("anchor_per_model", _anchor_pts))
        _trusted = _equation_meta.get("trusted_factions", [])
        _n_sim = _equation_meta.get("units_sim_fitted", 0)
        _n_fb  = _equation_meta.get("units_phase1_fallback", 0)
        st.caption(
            f"Equation fit: **{_n_sim} units sim-measured** across "
            f"{len(_trusted)} trusted factions "
            f"({', '.join(_trusted) if _trusted else '—'}), "
            f"{_equation_meta.get('n_battles_per_pair', 0)} battles/pair "
            f"at {_equation_meta.get('budget_per_side', 0):.0f}-pt budget. "
            f"{_n_fb} catalogue units inherit Phase 1 closed-form prices "
            f"(marked `phase1_fallback`). "
            f"Built {_equation_meta.get('built_at', '')[:19].replace('T', ' ')}."
        )
        _result = None  # No D/T/R matrices in equation-calibrated; drill-down disabled.
        _result_entries = _equation_entries
    else:
        try:
            _result = _equilibrium_result(_anchor_key, float(_anchor_pts))
        except ValueError as _exc:
            st.error(f"Couldn't compute equilibrium: {_exc}")
            st.stop()
        _result_entries = _result.entries

    # ---- Faction filter (operates on cached entries — re-renders only) ----
    _all_factions = sorted({e.faction for e in _result_entries if e.faction})
    _selected_factions = st.multiselect(
        "Show factions",
        options=_all_factions,
        default=_all_factions,
        key="eq_faction_filter",
    )

    _filtered = [
        e for e in _result_entries
        if (e.faction in _selected_factions if _selected_factions else True)
        and e.role in _role_filter
    ]

    if not _filtered:
        st.warning("No units match the current filters.")
    else:
        # ---- Summary metrics ----
        _under = [e for e in _filtered if e.mispricing_pct < -10]
        _over  = [e for e in _filtered if e.mispricing_pct > 10]
        _m1, _m2, _m3, _m4 = st.columns(4)
        _m1.metric("Units fitted", len(_filtered))
        _m2.metric("GW undercosted (>10%)", len(_under),
                   help="Equilibrium says these should cost more than GW prices them.")
        _m3.metric("GW overcosted (>10%)", len(_over),
                   help="Equilibrium says these should cost less than GW prices them.")
        _m4.metric("Anchor", f"{UNIT_CATALOG[_anchor_key].name[:18]}",
                   f"{_anchor_pts:.0f} pts/model")

        # ---- Interactive Plotly scatter ----
        # The heavy lifting (computing equilibrium + assembling 30 faction
        # traces with customdata blobs) is cached on the filter inputs, so
        # clicks and faction-filter toggles only pay the rerun cost. The
        # cached builder differs by source: Phase 1 recomputes from the
        # catalogue, sim-driven loads the JSON snapshot.
        if _use_simdriven:
            # Sim-driven defaults to showing ONLY the measured units —
            # otherwise the bulk of dots in the chart are Phase 1 fallbacks
            # that look identical to the Phase 1 view, hiding the
            # sim-driven signal. A small expander offers the full overlay
            # for callers who want to compare both at once.
            with st.expander("Sim-driven view options", expanded=False):
                _only_measured = st.checkbox(
                    "Only show measured units (hide Phase 1 fallback)",
                    value=True,
                    key="eq_simdriven_only_measured",
                )
            _fig = _equilibrium_plotly_figure_simdriven(
                factions_tuple=tuple(sorted(_selected_factions)),
                roles_tuple=tuple(sorted(_role_filter)),
                only_measured=bool(_only_measured),
            )
        elif _use_equation:
            # Same default as sim-driven: hide Phase 1 fallback so the
            # actual fit signal isn't buried under 1k+ inherited dots.
            with st.expander("Equation view options", expanded=False):
                _only_measured = st.checkbox(
                    "Only show sim-fitted units (hide Phase 1 fallback)",
                    value=True,
                    key="eq_equation_only_measured",
                )
            _fig = _equilibrium_plotly_figure_equation(
                factions_tuple=tuple(sorted(_selected_factions)),
                roles_tuple=tuple(sorted(_role_filter)),
                only_measured=bool(_only_measured),
            )
        else:
            _fig = _equilibrium_plotly_figure(
                anchor_key=_anchor_key,
                anchor_pts=float(_anchor_pts),
                factions_tuple=tuple(sorted(_selected_factions)),
                roles_tuple=tuple(sorted(_role_filter)),
                balanced=bool(use_balanced),
            )

        _event = st.plotly_chart(
            _fig,
            use_container_width=True,
            key="eq_scatter",
            on_select="rerun",
            selection_mode="points",
        )

        # If the user clicked a point, write its key into the drill-down
        # selectbox's session state BEFORE the selectbox renders below.
        _selected_points = []
        if _event and getattr(_event, "selection", None):
            _selected_points = _event.selection.get("points", []) or []
        if _selected_points:
            _pt = _selected_points[0]
            _cd = _pt.get("customdata")
            if _cd and len(_cd) >= 1:
                st.session_state["eq_drill_key"] = _cd[0]

        st.caption(
            "Hover to inspect a unit. Click any point to drill into its "
            "matchups below. Click a faction in the legend to toggle it; "
            "double-click to isolate it. Drag to zoom, double-click to reset."
        )

        # ---- Sortable explorer table ----
        st.divider()
        st.markdown("### Explore the data")
        _rows = [
            {
                "Unit": e.name,
                "Faction": e.faction,
                "Role": e.role,
                "GW pts/model": e.gw_points_per_model,
                "Eq pts/model": e.equilibrium_points_per_model,
                "Mispricing %": e.mispricing_pct,
                "GW pts/squad": e.gw_points_per_squad,
                "Eq pts/squad": e.equilibrium_points_per_squad,
                "Min models": e.min_models,
                "Matchups": e.valid_matchups,
                "key": e.key,
            }
            for e in _filtered
        ]
        st.dataframe(
            _rows,
            hide_index=True,
            use_container_width=True,
            column_config={
                "key": None,   # hide the catalogue key column
                "Mispricing %": st.column_config.NumberColumn(
                    help="Positive = GW prices it ABOVE equilibrium (overcosted). "
                         "Negative = GW prices BELOW equilibrium (undercosted).",
                    format="%+.1f%%",
                ),
            },
        )
        st.caption(
            "Click any column header to sort. "
            "**Mispricing %** = `(GW − equilibrium) / equilibrium`."
        )

        # ---- Per-unit matchup drilldown ----
        # The drill-down reads from the Phase 1 D/T/R matrices. The
        # sim-driven snapshot only stores aggregate log-p values per unit,
        # not the underlying pairwise win rates, so the drill-down is
        # hidden in that mode. Add it to the snapshot if/when the
        # per-pair detail is wanted in the UI.
        if _use_simdriven or _use_equation:
            st.divider()
            st.info(
                "Per-unit matchup drill-down is not yet available for the "
                "snapshot views. Switch the **Solver source** above to "
                "*Closed-form Phase 1* to inspect pairwise time-to-kill "
                "and log-advantage matrices."
            )
            st.stop()

        st.divider()
        st.markdown("### Drill into a unit's matchups")
        # Defensive: filter out keys no longer in UNIT_CATALOG (the
        # equilibrium JSONs are snapshotted with the catalogue at solve
        # time; renames in the BSData mapper can leave stale keys).
        _drill_options = sorted(
            [e.key for e in _filtered if e.key in UNIT_CATALOG],
            key=lambda k: UNIT_CATALOG[k].name,
        )
        if not _drill_options:
            st.info("No comparable units — regenerate `data/equilibrium_points_*.json` to match the current catalogue.")
            st.stop()
        _drill_key = st.selectbox(
            "Pick a unit",
            _drill_options,
            format_func=lambda k: f"{UNIT_CATALOG[k].name}  —  {UNIT_CATALOG[k].faction}",
            key="eq_drill_key",
        )

        _drill_entry = next(e for e in _result.entries if e.key == _drill_key)
        _d1, _d2, _d3 = st.columns(3)
        _d1.metric("GW points / model", f"{_drill_entry.gw_points_per_model:.1f}")
        _d2.metric("Equilibrium / model",
                   f"{_drill_entry.equilibrium_points_per_model:.1f}",
                   f"{_drill_entry.mispricing_pct:+.1f}% vs GW")
        _d3.metric("Valid matchups", _drill_entry.valid_matchups)

        _best, _worst = _result.matchups_for(_drill_key, top_n=10)

        def _matchup_rows(matchups):
            out = []
            for m in matchups:
                _opp = UNIT_CATALOG.get(m["opponent_key"])
                if _opp is None:
                    continue
                out.append({
                    "Opponent": _opp.name,
                    "Faction": _opp.faction,
                    "Turns I kill them": m["T_self_kills_opp"],
                    "Turns they kill me": m["T_opp_kills_self"],
                    "Log advantage R": m["R_log_advantage"],
                    "Fair pts ratio (me/them)": m["fair_points_ratio"],
                })
            return out

        _col_best, _col_worst = st.columns(2)
        with _col_best:
            st.markdown(
                f"**Strongest matchups for {UNIT_CATALOG[_drill_key].name}**  "
                "<br><span style='color:#aaa;font-size:0.85em'>(highest log "
                "advantage = should cost most relative to opponent)</span>",
                unsafe_allow_html=True,
            )
            st.dataframe(_matchup_rows(_best), hide_index=True,
                         use_container_width=True)
        with _col_worst:
            st.markdown(
                f"**Weakest matchups for {UNIT_CATALOG[_drill_key].name}**  "
                "<br><span style='color:#aaa;font-size:0.85em'>(lowest log "
                "advantage = should cost least relative to opponent)</span>",
                unsafe_allow_html=True,
            )
            st.dataframe(_matchup_rows(_worst), hide_index=True,
                         use_container_width=True)

        st.caption(
            "**Log advantage R** is the value the solver averages to derive "
            "equilibrium points. **Fair pts ratio** = $\\exp(R)$ = what "
            "fraction of the opponent's points-per-model the equilibrium says "
            "this unit should cost in an isolated 1-vs-1."
        )


# --- Compare tab ---
with tab_compare:
    render_compare_tab(st)


# ---------------------------------------------------------------------------
# Convergence tab — live 1-v-1 simulation with shrinking confidence band
# ---------------------------------------------------------------------------
# The premise: most users want to know "has this Monte-Carlo settled?" rather
# than "what does the underlying win rate look like in the limit". This tab
# answers both. We pick two squads, run battles in small batches, and after
# every batch we update a Plotly figure with:
#   * the running win-rate trajectory for A / B / draws, and
#   * the Wilson 95% confidence half-width — the "convergence" signal that
#     drops toward zero as 1 / sqrt(N).
# A green indicator fires when the half-width falls under the user-set
# tolerance. The loop drives itself via st.rerun() between batches so the
# Stop button stays responsive (Streamlit cannot interrupt a running loop;
# each rerun gives it a chance to read the button).

A_OUTCOME, B_OUTCOME, DRAW_OUTCOME = "A", "B", "D"


def _wilson_half_width(p: float, n: int, z: float = 1.96) -> float:
    """Half-width of the Wilson score 95% interval for a binomial proportion.

    Returns 1.0 when n is zero so the convergence trace starts at the top of
    the axis rather than being undefined.
    """
    if n <= 0:
        return 1.0
    return (z / (1.0 + z * z / n)) * math.sqrt(
        max(0.0, p * (1.0 - p) / n + z * z / (4 * n * n))
    )


def _running_rates(outcomes: List[str]) -> Tuple[List[float], List[float], List[float]]:
    """Running win-rate trajectories for A, B, draws after each battle."""
    a_rate, b_rate, d_rate = [], [], []
    a = b = d = 0
    for i, outcome in enumerate(outcomes, start=1):
        if outcome == A_OUTCOME:
            a += 1
        elif outcome == B_OUTCOME:
            b += 1
        else:
            d += 1
        a_rate.append(a / i)
        b_rate.append(b / i)
        d_rate.append(d / i)
    return a_rate, b_rate, d_rate


def _outcomes_to_dataframes(
    outcomes_iter: List[str], state: dict,
    a_label: str, b_label: str, tolerance_pct: float,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Turn a batch (or full history) of outcomes into (rate_df, hw_df).

    `state` is a dict {a, b, d, n} that is mutated to maintain running
    counts across batches — so calling this on a batch produces only the
    DataFrame rows for those new battles, indexed by their absolute
    battle number. Both DataFrames carry percent-scale values (0-100).
    """
    if a_label == b_label:
        raise ValueError(
            f"a_label and b_label must be distinct (got {a_label!r} for both); "
            "side-prefixed labels at the call site are how that is enforced."
        )
    rate_rows, hw_rows, indices = [], [], []
    for outcome in outcomes_iter:
        if outcome == A_OUTCOME:
            state["a"] += 1
        elif outcome == B_OUTCOME:
            state["b"] += 1
        else:
            state["d"] += 1
        state["n"] += 1
        n = state["n"]
        ar, br, dr = state["a"] / n, state["b"] / n, state["d"] / n
        rate_rows.append({
            a_label: ar * 100,
            b_label: br * 100,
            "Draws": dr * 100,
            "50/50": 50.0,
        })
        hw_rows.append({
            f"{a_label} half-width": _wilson_half_width(ar, n) * 100,
            f"{b_label} half-width": _wilson_half_width(br, n) * 100,
            "Tolerance": tolerance_pct,
        })
        indices.append(n)

    if not rate_rows:
        rate_df = pd.DataFrame(
            columns=[a_label, b_label, "Draws", "50/50"], dtype="float64",
        )
        hw_df = pd.DataFrame(
            columns=[f"{a_label} half-width", f"{b_label} half-width", "Tolerance"],
            dtype="float64",
        )
        return rate_df, hw_df

    rate_df = pd.DataFrame(rate_rows, index=indices)
    hw_df = pd.DataFrame(hw_rows, index=indices)
    return rate_df, hw_df


def _render_convergence_metrics(
    slot, state: dict, a_label: str, b_label: str,
    max_battles: int, tolerance_pct: float,
) -> None:
    """Refresh the four-metric header row from running state."""
    n = state["n"]
    if n == 0:
        with slot.container():
            st.info(
                "Configure both sides and press **Run** to begin. "
                "Charts populate live as battles run."
            )
        return
    ar = state["a"] / n
    br = state["b"] / n
    hwa = _wilson_half_width(ar, n) * 100
    hwb = _wilson_half_width(br, n) * 100
    converged = (hwa <= tolerance_pct) and (hwb <= tolerance_pct)
    with slot.container():
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(a_label, f"{ar:.1%}", f"±{hwa:.2f}% (95%)")
        m2.metric(b_label, f"{br:.1%}", f"±{hwb:.2f}% (95%)")
        m3.metric("Draws", f"{state['d'] / n:.1%}", f"{state['d']} / {n}")
        if converged:
            m4.metric("Status", "✓ Converged", f"after {n} battles")
        elif st.session_state["conv_running"]:
            m4.metric("Status", "Running…", f"{n} / {max_battles}")
        else:
            m4.metric("Status", "Stopped",
                      f"{n} / {max_battles} not yet converged")


@st.fragment
def _convergence_fragment(
    a_key: str, b_key: str, a_squads: int, b_squads: int,
    a_label: str, b_label: str, a_colour: str, b_colour: str,
    a_side_name: str, b_side_name: str,
    batch_size: int, max_battles: int, tolerance_pct: float,
) -> None:
    """Live chart + batch driver for the Convergence tab.

    Uses `st.line_chart` + `add_rows()` — Streamlit's native streaming
    pipeline. Unlike `st.plotly_chart`, `add_rows` ships only the new
    points over the websocket and the existing chart updates in place
    rather than re-rendering, so there is no flicker between batches.

    Streamlit cancels this fragment cleanly when any widget outside it
    (Run, Stop, Reset, the unit pickers) is interacted with — the new
    script run pre-empts this one — so the Stop button stays responsive
    without us polling for it.
    """
    metrics_slot = st.empty()
    st.markdown("**Running win rate (percent)**")
    rate_chart_slot = st.empty()
    st.markdown("**95% confidence half-width — the convergence signal**")
    hw_chart_slot = st.empty()

    state = {"a": 0, "b": 0, "d": 0, "n": 0}
    outcomes: List[str] = st.session_state["conv_outcomes"]

    rate_chart = None
    hw_chart = None
    rate_colors = [a_colour, b_colour, "#aaaaaa", "#FFD700"]
    hw_colors = [a_colour, b_colour, "#27c97d"]

    # Seed chart from any existing history. `st.line_chart` needs at
    # least one row to draw — if outcomes is empty we just wait for the
    # first batch to populate the slot.
    if outcomes:
        initial_rate_df, initial_hw_df = _outcomes_to_dataframes(
            outcomes, state, a_label, b_label, tolerance_pct,
        )
        rate_chart = rate_chart_slot.line_chart(
            initial_rate_df, height=320, use_container_width=True,
            color=rate_colors,
        )
        hw_chart = hw_chart_slot.line_chart(
            initial_hw_df, height=220, use_container_width=True,
            color=hw_colors,
        )

    _render_convergence_metrics(
        metrics_slot, state, a_label, b_label, max_battles, tolerance_pct,
    )

    if not st.session_state["conv_running"]:
        return

    a_keys = [a_key] * a_squads
    b_keys = [b_key] * b_squads

    while st.session_state["conv_running"] and state["n"] < max_battles:
        n_to_run = min(batch_size, max_battles - state["n"])
        batch: List[str] = []
        for _ in range(n_to_run):
            army_a = build_army_from_list(a_side_name, a_keys)
            army_b = build_army_from_list(b_side_name, b_keys)
            result = Battle(army_a, army_b, map_=DEFAULT_MAP).run()
            if result.winner == a_side_name:
                outcome = A_OUTCOME
            elif result.winner == b_side_name:
                outcome = B_OUTCOME
            else:
                outcome = DRAW_OUTCOME
            outcomes.append(outcome)
            batch.append(outcome)

        batch_rate_df, batch_hw_df = _outcomes_to_dataframes(
            batch, state, a_label, b_label, tolerance_pct,
        )

        if rate_chart is None:
            # First batch — create the charts now that we have data.
            rate_chart = rate_chart_slot.line_chart(
                batch_rate_df, height=320, use_container_width=True,
                color=rate_colors,
            )
            hw_chart = hw_chart_slot.line_chart(
                batch_hw_df, height=220, use_container_width=True,
                color=hw_colors,
            )
        else:
            rate_chart.add_rows(batch_rate_df)
            hw_chart.add_rows(batch_hw_df)

        n = state["n"]
        ar = state["a"] / n
        br = state["b"] / n
        if (_wilson_half_width(ar, n) * 100 <= tolerance_pct
                and _wilson_half_width(br, n) * 100 <= tolerance_pct):
            st.session_state["conv_running"] = False

        _render_convergence_metrics(
            metrics_slot, state, a_label, b_label, max_battles, tolerance_pct,
        )

        time.sleep(0.01)

    if state["n"] >= max_battles:
        st.session_state["conv_running"] = False
        _render_convergence_metrics(
            metrics_slot, state, a_label, b_label, max_battles, tolerance_pct,
        )


with tab_convergence:
    st.markdown("## Convergence  —  basic 1-v-1 simulation")
    st.caption(
        "Pick two squads. Battles run in small batches and the chart "
        "updates after every batch. The bottom panel is the convergence "
        "signal: the 95% confidence half-width drops toward zero as more "
        "battles run. Stop when the band is tight enough for the question "
        "you are asking."
    )

    # ----- Squad pickers -----
    _conv_factions = FACTIONS_AVAILABLE
    _c_left, _c_right = st.columns(2)
    with _c_left:
        st.markdown("**Side A**")
        _a_default_faction = (
            "Space Marines" if "Space Marines" in _conv_factions else _conv_factions[0]
        )
        _conv_a_faction = st.selectbox(
            "Faction A", _conv_factions,
            index=_conv_factions.index(_a_default_faction),
            key="conv_a_faction",
        )
        _conv_a_units = _units_in_faction(_conv_a_faction)
        _a_default_unit = next(
            (k for k in _conv_a_units if "intercessor" in k.lower()),
            _conv_a_units[0] if _conv_a_units else None,
        )
        _conv_a_key = st.selectbox(
            "Unit A", _conv_a_units,
            index=_conv_a_units.index(_a_default_unit) if _a_default_unit else 0,
            format_func=lambda k: UNIT_CATALOG[k].name,
            key="conv_a_key",
        )
        _conv_a_squads = st.number_input(
            "Squads of A", min_value=1, max_value=20, value=1, step=1,
            key="conv_a_squads",
        )
    with _c_right:
        st.markdown("**Side B**")
        _b_default_faction = (
            "Space Marines" if "Space Marines" in _conv_factions else _conv_factions[0]
        )
        _conv_b_faction = st.selectbox(
            "Faction B", _conv_factions,
            index=_conv_factions.index(_b_default_faction),
            key="conv_b_faction",
        )
        _conv_b_units = _units_in_faction(_conv_b_faction)
        _b_default_unit = next(
            (k for k in _conv_b_units if "tactical" in k.lower()
             or "intercessor" in k.lower()),
            _conv_b_units[0] if _conv_b_units else None,
        )
        _conv_b_key = st.selectbox(
            "Unit B", _conv_b_units,
            index=_conv_b_units.index(_b_default_unit) if _b_default_unit else 0,
            format_func=lambda k: UNIT_CATALOG[k].name,
            key="conv_b_key",
        )
        _conv_b_squads = st.number_input(
            "Squads of B", min_value=1, max_value=20, value=1, step=1,
            key="conv_b_squads",
        )

    # ----- Run parameters -----
    _ctl1, _ctl2, _ctl3 = st.columns(3)
    _conv_batch = _ctl1.number_input(
        "Batch size", min_value=1, max_value=200, value=10, step=1,
        key="conv_batch_size",
        help="Battles per chart refresh. Smaller batches = smoother live update, bigger batches = faster total run.",
    )
    _conv_max = _ctl2.number_input(
        "Max battles", min_value=20, max_value=20000, value=1000, step=20,
        key="conv_max_battles",
        help="Hard cap so an un-converging matchup does not run forever.",
    )
    _conv_tol = _ctl3.number_input(
        "Convergence tolerance (± %)",
        min_value=0.5, max_value=10.0, value=2.0, step=0.5,
        key="conv_tolerance",
        help="Stop when both A's and B's Wilson 95% half-width drop below this.",
    )

    # ----- Session state -----
    if "conv_outcomes" not in st.session_state:
        st.session_state["conv_outcomes"] = []
    if "conv_running" not in st.session_state:
        st.session_state["conv_running"] = False

    # Detect a config change — if the user re-picks units while a run is
    # in flight or completed, the prior history is meaningless against the
    # new matchup. Reset the history (but only if there is one) so the
    # chart does not mix outcomes from two different fights.
    _conv_signature = (
        _conv_a_key, int(_conv_a_squads), _conv_b_key, int(_conv_b_squads),
    )
    if st.session_state.get("conv_signature") != _conv_signature:
        if st.session_state["conv_outcomes"]:
            st.session_state["conv_outcomes"] = []
        st.session_state["conv_running"] = False
        st.session_state["conv_signature"] = _conv_signature

    _btn_run, _btn_stop, _btn_reset, _ = st.columns([1, 1, 1, 4])
    if _btn_run.button("▶ Run", type="primary", key="conv_run_btn",
                       disabled=st.session_state["conv_running"]):
        st.session_state["conv_outcomes"] = []
        st.session_state["conv_running"] = True
        st.rerun()
    if _btn_stop.button("■ Stop", key="conv_stop_btn",
                        disabled=not st.session_state["conv_running"]):
        st.session_state["conv_running"] = False
        st.rerun()
    if _btn_reset.button("Reset", key="conv_reset_btn",
                         disabled=st.session_state["conv_running"]):
        st.session_state["conv_outcomes"] = []
        st.rerun()

    # ----- Display + live loop (inside a fragment so reruns don't flash) -----
    _a_profile = UNIT_CATALOG[_conv_a_key]
    _b_profile = UNIT_CATALOG[_conv_b_key]
    # Always prefix with the side so mirror matches (same unit + count on
    # both sides) cannot collide into a single DataFrame column.
    _a_label = f"A — {_a_profile.name} x{int(_conv_a_squads)}"
    _b_label = f"B — {_b_profile.name} x{int(_conv_b_squads)}"
    _a_colour = colour_for(_a_profile.faction) if _a_profile.faction else DEFAULT_COL_A
    _b_colour = colour_for(_b_profile.faction) if _b_profile.faction else DEFAULT_COL_B
    # If the two sides share a faction colour (e.g. Space Marines mirror match),
    # fall back to the default blue/red palette so the two traces are readable.
    if _a_colour == _b_colour:
        _a_colour, _b_colour = DEFAULT_COL_A, DEFAULT_COL_B

    _convergence_fragment(
        a_key=_conv_a_key, b_key=_conv_b_key,
        a_squads=int(_conv_a_squads), b_squads=int(_conv_b_squads),
        a_label=_a_label, b_label=_b_label,
        a_colour=_a_colour, b_colour=_b_colour,
        a_side_name="Side A", b_side_name="Side B",
        batch_size=int(_conv_batch),
        max_battles=int(_conv_max),
        tolerance_pct=float(_conv_tol),
    )


# ---------------------------------------------------------------------------
# Calibration tab — Stage 1 sim vs tournament win rates
# ---------------------------------------------------------------------------
with tab_calibration:
    st.markdown("## Calibration — Stage 1: sim win rates vs tournament")
    st.caption(
        "Compares per-faction average win rate from the simulator against the "
        "Warp Friends May 2026 ~10k-game tournament aggregate. The headline "
        "metric is mean absolute error (MAE) vs real meta — Stage 1 target is "
        "≤ 2.0 pts. Snapshot built offline by: "
        "`python -m scripts.evaluate_vs_meta --battles 100 --out data/meta_comparison_snapshot.json`"
    )

    _cal_snap = _load_meta_snapshot()
    _mae_progress = _load_mae_progress()

    # ---- MAE progress chart (always shown if CSV exists) ----
    if _mae_progress:
        st.markdown("### MAE progress over calibration iterations")
        _modes_seen = sorted({r["mode"] for r in _mae_progress})
        _mode_colours = {
            "random_fill 1000pt":    "#4C9BE8",
            "archetype 1000pt":      "#E88C4C",
            "archetype 2000pt":      "#9B4CE8",
            "archetype 2000pt N=20": "#C89BE8",
        }
        _mode_dash = {
            "archetype 2000pt N=20": "dot",
        }
        _prog_fig = go.Figure()
        for _m in _modes_seen:
            _rows = [r for r in _mae_progress if r["mode"] == _m]
            _colour = _mode_colours.get(_m, "#888888")
            _dash   = _mode_dash.get(_m, "solid")
            _prog_fig.add_trace(go.Scatter(
                x=[r["when"][:10] for r in _rows],
                y=[r["mae"] for r in _rows],
                mode="lines+markers",
                name=_m,
                line=dict(color=_colour, width=2, dash=_dash),
                marker=dict(size=7, opacity=0.7 if _dash != "solid" else 1.0),
                hovertemplate=(
                    "<b>%{customdata}</b><br>MAE: %{y:.2f} pts<extra></extra>"
                ),
                customdata=[r["label"] for r in _rows],
            ))
        _prog_fig.add_hline(
            y=2.0, line_dash="dash", line_color="green",
            annotation_text="Target ≤ 2.0 pts",
            annotation_position="bottom right",
        )
        _prog_fig.update_layout(
            xaxis_title="Date",
            yaxis_title="MAE (pts)",
            legend_title="Evaluation mode",
            height=300,
            margin=dict(t=20, b=40),
        )
        st.plotly_chart(_prog_fig, use_container_width=True)

    # ---- Snapshot-dependent content ----
    if _cal_snap is None:
        st.info(
            "No calibration snapshot found. Build one with:\n\n"
            "```\npython -m scripts.evaluate_vs_meta --battles 100 "
            "--out data/meta_comparison_snapshot.json\n```"
        )
    else:
        # ---- Headline metrics ----
        _c1, _c2, _c3, _c4 = st.columns(4)
        _c1.metric(
            "MAE (10 data factions)",
            f"{_cal_snap['mae_real']:.2f} pts",
            help="Mean absolute error vs Warp Friends data for the 10 factions with real tournament numbers. Target ≤ 2.0 pts. The 12 factions with no real data are excluded.",
        )
        _c2.metric(
            "MAE vs 50 %",
            f"{_cal_snap['mae_sweg']:.2f} pts",
            help="Mean absolute error between sim and 50 % for the 10 data factions. Target ≤ 2.0 pts for rule-internal balance.",
        )
        _c3.metric("Battles per pairing", f"{_cal_snap['n_battles']:,}")
        _c4.metric("Factions measured", str(len(_cal_snap["factions"])))
        _mae_all = _cal_snap.get("mae_real_all")
        st.caption(
            f"Snapshot: {_cal_snap['built_at'][:10]}  |  "
            f"mode: {_cal_snap['mode']}  |  lists: {_cal_snap['list_mode']}"
            + (f"  |  MAE all 22 factions: {_mae_all:.2f} pts (reference, 12 targets are estimates)" if _mae_all else "")
        )

        st.divider()

        # ---- Per-faction deviation chart (data factions only) ----
        st.markdown("### Per-faction sim win rate vs tournament target")

        _factions_data = sorted(
            [r for r in _cal_snap["factions"]
             if not r.get("is_no_data", r["faction"] in _FX_ALL_FACTIONS)],
            key=lambda r: abs(r["diff"]),
            reverse=True,
        )

        def _bar_colour(row: dict) -> str:
            if abs(row["diff"]) <= 2.0:
                return "#2ecc71"   # green — within target
            if abs(row["diff"]) <= 5.0:
                return "#f39c12"   # amber
            return "#e74c3c"       # red — significant outlier

        _bar_colours = [_bar_colour(r) for r in _factions_data]
        _faction_labels = [
            f"{r['faction']} (~)" if r["is_approx"] else r["faction"]
            for r in _factions_data
        ]

        _dev_fig = go.Figure()
        _dev_fig.add_trace(go.Bar(
            y=_faction_labels,
            x=[r["diff"] for r in _factions_data],
            orientation="h",
            marker_color=_bar_colours,
            customdata=[
                [r["sim_pct"], r["tournament_pct"], r["diff"]]
                for r in _factions_data
            ],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Sim: %{customdata[0]:.1f}%<br>"
                "Tournament: %{customdata[1]:.1f}%<br>"
                "Difference: %{customdata[2]:+.1f} pts<extra></extra>"
            ),
        ))
        _dev_fig.add_vline(x=0, line_color="white", line_width=1)
        _dev_fig.add_vrect(x0=-2, x1=2, fillcolor="green", opacity=0.08, line_width=0)
        _dev_fig.update_layout(
            xaxis_title="Sim % − Tournament % (positive = sim overestimates faction strength)",
            height=max(400, len(_factions_data) * 28),
            margin=dict(t=20, l=200, r=20, b=40),
        )
        st.plotly_chart(_dev_fig, use_container_width=True)
        st.caption(
            "Green band = ±2 pt target zone. "
            "(~) = approximate target (some real-world basis but flagged as less authoritative). "
            "12 factions with no real tournament data are excluded from this chart and the headline MAE."
        )

        st.divider()

        # ---- Full table ----
        st.markdown("### Full faction breakdown")
        def _data_quality(r: dict) -> str:
            if r.get("is_no_data", r["faction"] in _FX_ALL_FACTIONS):
                return "no data"
            if r["is_approx"]:
                return "approx"
            return "real"

        _table_rows = [
            {
                "Faction": r["faction"],
                "Data": _data_quality(r),
                "Sim %": r["sim_pct"],
                "Tournament %": r["tournament_pct"],
                "Diff": r["diff"],
                "vs 50 %": r["diff_vs_50"],
            }
            for r in sorted(_cal_snap["factions"], key=lambda r: r["faction"])
        ]
        st.dataframe(
            pd.DataFrame(_table_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Diff": st.column_config.NumberColumn(format="%+.1f"),
                "vs 50 %": st.column_config.NumberColumn(format="%+.1f"),
            },
        )

    st.divider()

    # ---- Hypothetical win rates with equation-derived prices ----
    st.markdown("## Hypothetical win rates — equation-derived prices")
    st.caption(
        "Win rates simulated using prices output by the calibrated equation rather than "
        "GW published costs. Calibrated factions (those within the MAE threshold when the "
        "equation was fit) are shown with solid bars; uncalibrated factions are dashed — "
        "their win rates are predictions from the equation extrapolating beyond its training data."
    )

    _eq_snap = _load_equation_snapshot()
    if _eq_snap is None:
        st.info(
            "No hypothetical snapshot found. Build one with:\n\n"
            "```\n"
            "# Step 1: fit the equation (once per calibration session)\n"
            "python -m scripts.fit_equation_calibrated --threshold 10.0\n\n"
            "# Step 2: run the faction matrix with equation prices\n"
            "python -m scripts.evaluate_vs_meta --battles 40 "
            "--equation-prices data/equation_calibrated_points.json "
            "--out data/equation_vs_meta_snapshot.json\n"
            "```"
        )
    else:
        _eq_trusted = set(_eq_snap.get("trusted_factions", []))

        _eq_col1, _eq_col2, _eq_col3 = st.columns(3)
        _eq_col1.metric(
            "MAE vs 50 % (all factions)",
            f"{_eq_snap['mae_sweg']:.2f} pts",
            help="Mean absolute error between equation-priced sim and 50 % across all factions. "
                 "Target ≤ 2.0 pts for internal balance.",
        )
        _eq_col2.metric(
            "MAE vs 50 % (calibrated factions only)",
            f"{_eq_snap['mae_real']:.2f} pts",
            help="MAE for the factions used to fit the equation.",
        )
        _eq_col3.metric("Battles per pairing", f"{_eq_snap['n_battles']:,}")
        st.caption(
            f"Snapshot: {_eq_snap['built_at'][:10]}  |  "
            f"mode: {_eq_snap['mode']}  |  lists: {_eq_snap['list_mode']}"
        )

        _eq_factions = sorted(
            _eq_snap["factions"],
            key=lambda r: abs(r["diff_vs_50"]),
            reverse=True,
        )

        _eq_colours = []
        _eq_labels = []
        for r in _eq_factions:
            is_trusted = r["faction"] in _eq_trusted
            diff = abs(r["diff_vs_50"])
            if diff <= 2.0:
                colour = "#2ecc71"
            elif diff <= 5.0:
                colour = "#f39c12"
            else:
                colour = "#e74c3c"
            _eq_colours.append(colour)
            label = r["faction"] if is_trusted else f"{r['faction']} *"
            _eq_labels.append(label)

        _eq_fig = go.Figure()
        _eq_fig.add_trace(go.Bar(
            y=_eq_labels,
            x=[r["diff_vs_50"] for r in _eq_factions],
            orientation="h",
            marker_color=_eq_colours,
            customdata=[[r["sim_pct"], r["diff_vs_50"]] for r in _eq_factions],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Sim win rate: %{customdata[0]:.1f}%<br>"
                "vs 50%%: %{customdata[1]:+.1f} pts<extra></extra>"
            ),
        ))
        _eq_fig.add_vline(x=0, line_color="white", line_width=1)
        _eq_fig.add_vrect(x0=-2, x1=2, fillcolor="green", opacity=0.08, line_width=0)
        _eq_fig.update_layout(
            xaxis_title="Sim % − 50 % (positive = equation overprices this faction's opponents)",
            height=max(400, len(_eq_factions) * 28),
            margin=dict(t=20, l=220, r=20, b=40),
        )
        st.plotly_chart(_eq_fig, use_container_width=True)
        st.caption(
            "Green band = ±2 pt target zone. "
            "* = uncalibrated faction (equation extrapolation, not a training anchor)."
        )

    # -------------------------------------------------------------------------
    # Tools — launch long-running calibration jobs from the user interface
    # -------------------------------------------------------------------------
    st.divider()
    st.markdown("## Tools — run calibration jobs from the user interface")
    st.caption(
        "These launch the fitting and evaluation scripts as background processes. "
        "Progress streams into the log box below. The page stays responsive while "
        "the job runs — you can switch tabs and come back."
    )

    def _subprocess_env() -> dict:
        """Build an env dict that suppresses the PYTHONHASHSEED re-exec guard."""
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _launch_subprocess(args: list, log_path: _pathlib.Path) -> subprocess.Popen:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "w", encoding="utf-8")
        return subprocess.Popen(
            args,
            env=_subprocess_env(),
            stdout=log_file,
            stderr=log_file,
            cwd=str(_pathlib.Path(__file__).parent),
        )

    def _read_log_tail(log_path: _pathlib.Path, max_chars: int = 4000) -> str:
        if not log_path.exists():
            return ""
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[-max_chars:] if len(text) > max_chars else text

    # ---- Step 1: Fit equation ------------------------------------------------
    with st.expander("Step 1 — Fit equation from trusted factions", expanded=True):
        st.caption(
            "Measures pairwise win rates for units from factions within the MAE "
            "threshold, then fits the Bradley-Terry equation. Writes "
            "`data/equation_calibrated_points.json`."
        )
        _fc1, _fc2, _fc3, _fc4 = st.columns(4)
        _fit_threshold  = _fc1.number_input(
            "MAE threshold (pts)", min_value=1.0, max_value=20.0, value=10.0, step=0.5,
            key="fit_threshold",
            help="Factions with |sim − tournament| within this value are used to fit the equation.",
        )
        _fit_battles    = _fc2.number_input(
            "Battles per pair", min_value=1, max_value=200, value=5, step=1,
            key="fit_battles",
            help="More battles = more accurate prices but longer run time.",
        )
        _fit_max_per    = _fc3.number_input(
            "Max units per faction", min_value=5, max_value=100, value=15, step=5,
            key="fit_max_per",
            help="Cap units per faction (evenly-spaced cost sample). 15 → ~60 units, ~80 s on 11 cores.",
        )
        _fit_workers    = _fc4.number_input(
            "Worker processes", min_value=1, max_value=max(1, (os.cpu_count() or 2)),
            value=max(1, (os.cpu_count() or 2) - 1), step=1,
            key="fit_workers",
        )

        if "fit_proc" not in st.session_state:
            st.session_state["fit_proc"] = None
            st.session_state["fit_running"] = False

        _fb_run, _fb_stop, _fb_status = st.columns([1, 1, 6])
        _fit_run_clicked = _fb_run.button(
            "▶ Fit equation", type="primary", key="fit_run_btn",
            disabled=bool(st.session_state.get("fit_running")),
        )
        _fit_stop_clicked = _fb_stop.button(
            "■ Stop", key="fit_stop_btn",
            disabled=not bool(st.session_state.get("fit_running")),
        )

        if _fit_run_clicked:
            proc = _launch_subprocess(
                [
                    sys.executable, "-m", "scripts.fit_equation_calibrated",
                    "--threshold", str(_fit_threshold),
                    "--battles",   str(_fit_battles),
                    "--max-per-faction", str(int(_fit_max_per)),
                    "--workers",   str(int(_fit_workers)),
                ],
                _FIT_EQ_LOG_PATH,
            )
            st.session_state["fit_proc"]    = proc
            st.session_state["fit_running"] = True
            st.rerun()

        if _fit_stop_clicked:
            proc = st.session_state.get("fit_proc")
            if proc and proc.poll() is None:
                proc.terminate()
            st.session_state["fit_running"] = False
            st.rerun()

        # Check if process finished naturally
        proc = st.session_state.get("fit_proc")
        if proc is not None and st.session_state.get("fit_running"):
            if proc.poll() is not None:
                st.session_state["fit_running"] = False

        _fit_log_text = _read_log_tail(_FIT_EQ_LOG_PATH)
        if _fit_log_text:
            if st.session_state.get("fit_running"):
                _fb_status.info("Running… refresh to update progress.")
                st.button("🔄 Refresh progress", key="fit_refresh_btn")
            elif st.session_state.get("fit_proc") is not None:
                ret = st.session_state["fit_proc"].poll()
                if ret == 0:
                    st.success("Equation fitting complete — `data/equation_calibrated_points.json` updated.")
                elif ret is not None:
                    st.error(f"Process exited with code {ret}. See log below.")
            st.code(_fit_log_text, language=None)
        elif _EQUATION_CALIBRATED_PATH.exists():
            st.success(
                f"`data/equation_calibrated_points.json` exists from a previous run. "
                f"Press **Fit equation** to rebuild it."
            )

    # ---- Step 2: Run evaluation with equation prices ------------------------
    with st.expander("Step 2 — Evaluate equation prices vs tournament", expanded=True):
        st.caption(
            "Runs the faction-vs-faction matrix using equation-derived prices instead "
            "of GW costs and records the win rates. Writes "
            "`data/equation_vs_meta_snapshot.json` (shown above as 'Hypothetical win rates')."
        )
        _ec1, _ec2 = st.columns(2)
        _eval_battles = _ec1.number_input(
            "Battles per faction pairing", min_value=5, max_value=500, value=40, step=5,
            key="eval_battles",
        )
        _eval_workers = _ec2.number_input(
            "Worker processes", min_value=1, max_value=max(1, (os.cpu_count() or 2)),
            value=max(1, (os.cpu_count() or 2) - 1), step=1,
            key="eval_workers",
        )

        if not _EQUATION_CALIBRATED_PATH.exists():
            st.warning(
                "Run **Step 1 — Fit equation** first. "
                "`data/equation_calibrated_points.json` does not exist yet."
            )

        if "eval_proc" not in st.session_state:
            st.session_state["eval_proc"] = None
            st.session_state["eval_running"] = False

        _eb_run, _eb_stop, _eb_status = st.columns([1, 1, 6])
        _eval_run_clicked = _eb_run.button(
            "▶ Run evaluation", type="primary", key="eval_run_btn",
            disabled=(
                bool(st.session_state.get("eval_running"))
                or not _EQUATION_CALIBRATED_PATH.exists()
            ),
        )
        _eval_stop_clicked = _eb_stop.button(
            "■ Stop", key="eval_stop_btn",
            disabled=not bool(st.session_state.get("eval_running")),
        )

        if _eval_run_clicked:
            proc = _launch_subprocess(
                [
                    sys.executable, "-m", "scripts.evaluate_vs_meta",
                    "--battles", str(int(_eval_battles)),
                    "--workers", str(int(_eval_workers)),
                    "--equation-prices", str(_EQUATION_CALIBRATED_PATH),
                    "--out", "data/equation_vs_meta_snapshot.json",
                ],
                _EVAL_EQ_LOG_PATH,
            )
            st.session_state["eval_proc"]    = proc
            st.session_state["eval_running"] = True
            st.rerun()

        if _eval_stop_clicked:
            proc = st.session_state.get("eval_proc")
            if proc and proc.poll() is None:
                proc.terminate()
            st.session_state["eval_running"] = False
            st.rerun()

        proc = st.session_state.get("eval_proc")
        if proc is not None and st.session_state.get("eval_running"):
            if proc.poll() is not None:
                st.session_state["eval_running"] = False

        _eval_log_text = _read_log_tail(_EVAL_EQ_LOG_PATH)
        if _eval_log_text:
            if st.session_state.get("eval_running"):
                _eb_status.info("Running… refresh to update progress.")
                st.button("🔄 Refresh progress", key="eval_refresh_btn")
            elif st.session_state.get("eval_proc") is not None:
                ret = st.session_state["eval_proc"].poll()
                if ret == 0:
                    st.success(
                        "Evaluation complete — reload the page to see updated "
                        "hypothetical win rates above."
                    )
                elif ret is not None:
                    st.error(f"Process exited with code {ret}. See log below.")
            st.code(_eval_log_text, language=None)


# ===========================================================================
# Tab: Equation Fit (Goal C Track 4 — data-driven regression visualiser)
# ===========================================================================
#
# Lets the user iterate on the regression feature set: include / exclude
# features, swap functional forms, refit, see the headline R² / MAE,
# compare predicted-vs-GW prices, drill into outliers. The 3D surface
# plot (pick two features for the X/Y axes, see the fitted manifold with
# real units overlaid) is the follow-up; this tab ships with the
# essentials so you can already drive the equation interactively.

with tab_equation_fit:
    st.markdown("## Equation Fit  —  data-driven regression on stats")
    st.caption(
        "Fit a Generalized Additive Model that predicts log(GW points per "
        "model) from unit stats. Each feature gets a configurable functional "
        "form (linear / log / sqrt / quadratic / cubic). Faction-level "
        "tournament-meta multipliers are layered on top of the equation's "
        "stats-only prediction so factions that over- or under-perform at "
        "GW pricing get scaled accordingly."
    )

    # Cache the feature DataFrame so we don't re-extract on every refit.
    @st.cache_data(show_spinner="Extracting features…", max_entries=2)
    def _eqfit_features_df() -> "pd.DataFrame":
        return eqfit_extract_features()

    _eqfit_df = _eqfit_features_df()

    _all_specs = eqfit_default_specs()
    _spec_by_name = {s.name: s for s in _all_specs}
    _transform_options = eqfit_transform_names()

    st.divider()
    st.markdown("### Feature panel")
    st.caption(
        "Tick a feature to include it, pick its transform. Hit **Refit** "
        "below to recompute. Defaults reflect a reasonable starting model "
        "with all stat lines on and utility derivatives off."
    )

    # Group features by topic for the panel layout.
    _GROUPS = [
        ("Defensive",   ["wounds_per_model", "toughness", "save_quality", "invuln_quality", "fnp_quality"]),
        ("Ranged",      ["ranged_attacks", "ranged_strength", "ranged_ap_abs", "ranged_damage_per_shot", "ranged_range"]),
        ("Melee",       ["melee_attacks", "melee_strength", "melee_ap_abs", "melee_damage_per_shot"]),
        ("Mobility / objective", ["move", "oc", "min_models"]),
        ("Weapon keywords", ["lethal_hits", "sustained_hits", "twin_linked", "devastating_wounds",
                             "blast", "torrent", "melta", "rapid_fire", "ignores_cover"]),
        ("Deployment",  ["deep_strike", "scout_distance", "infiltrator", "lone_operative", "stealth"]),
        ("Interactions",    ["toughness_x_wounds", "total_wounds"]),
        ("Utility derived", ["expected_ranged_dmg_vs_meq", "expected_melee_dmg_vs_meq", "effective_wounds"]),
        ("Unit class",  ["is_monster", "is_vehicle", "is_character", "is_fly"]),
    ]

    # Each (feature, transform, include) triple is persisted in session
    # state so the user's choices survive reruns.
    if "eqfit_state" not in st.session_state:
        st.session_state["eqfit_state"] = {
            s.name: {"include": s.include, "transform": s.transform}
            for s in _all_specs
        }
    _state = st.session_state["eqfit_state"]

    for group_label, feature_names in _GROUPS:
        with st.expander(group_label, expanded=(group_label == "Defensive")):
            for name in feature_names:
                spec = _spec_by_name.get(name)
                if spec is None:
                    continue
                cur = _state.setdefault(
                    name, {"include": spec.include, "transform": spec.transform},
                )
                c1, c2, c3 = st.columns([0.6, 1.0, 3.0])
                with c1:
                    cur["include"] = st.checkbox(
                        " ", value=cur["include"], key=f"eqfit_inc_{name}",
                        label_visibility="collapsed",
                    )
                with c2:
                    cur["transform"] = st.selectbox(
                        " ", _transform_options,
                        index=_transform_options.index(cur["transform"]),
                        key=f"eqfit_t_{name}",
                        label_visibility="collapsed",
                        disabled=not cur["include"],
                    )
                with c3:
                    st.markdown(f"**{name}** — {spec.description}")

    st.divider()

    # Faction-multiplier alpha control.
    _alpha = st.slider(
        "Faction-multiplier α  (sensitivity to tournament-meta deviation)",
        min_value=0.0, max_value=4.0, value=2.0, step=0.25,
        help=(
            "multiplier = 1 + α · (real_winrate − 0.5). Higher α means a "
            "faction's over- or under-performance translates into a bigger "
            "per-unit price adjustment. α = 0 disables the meta correction."
        ),
        key="eqfit_alpha",
    )

    _refit_clicked = st.button("▶ Refit", type="primary", key="eqfit_refit_btn")

    # Cache the fit on the (feature set, transform set, alpha) signature.
    @st.cache_data(show_spinner="Fitting equation…", max_entries=8)
    def _run_eqfit(spec_signature: Tuple[Tuple[str, str], ...], alpha: float):
        specs = []
        for name, transform in spec_signature:
            base = _spec_by_name.get(name)
            description = base.description if base is not None else ""
            specs.append(
                EqFitFeatureSpec(name=name, transform=transform, include=True,
                                 description=description)
            )
        result = eqfit_fit(_eqfit_df, specs)

        # Faction multipliers.
        mults: Dict[str, float] = {}
        if _META_SNAPSHOT_PATH.exists():
            snap = _json.loads(_META_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            mults = eqfit_faction_multipliers(snap, alpha=alpha)

        # Per-unit multiplied predictions for the full DataFrame.
        adjusted = result.predicted_price.copy()
        factions = _eqfit_df["faction"].to_numpy()
        for i, f in enumerate(factions):
            adjusted[i] = adjusted[i] * mults.get(f, 1.0)
        return result, mults, adjusted

    _spec_signature = tuple(
        (name, _state[name]["transform"])
        for name in _state
        if _state[name]["include"]
    )

    if not _spec_signature:
        st.warning("Toggle at least one feature on to run a fit.")
        st.stop()

    _result, _mults, _adjusted = _run_eqfit(_spec_signature, float(_alpha))

    st.divider()
    st.markdown("### Headline metrics")
    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("R²", f"{_result.r_squared:.3f}",
               help="Proportion of variance in log(GW points/model) explained by the regression. 1.0 is perfect.")
    _m2.metric("MAE (log space)", f"{_result.mae_log:.3f}",
               help="Mean absolute error on log(price). 0.10 ≈ ±10% typical price error; 0.20 ≈ ±22%.")
    _m3.metric("MAE (price space)", f"{_result.mae_price:.1f} pts/model",
               help="Mean absolute error on raw price. Skewed by premium units.")
    _m4.metric("Features fitted", len(_result.feature_names),
               help="Number of features included in the regression.")

    if _mults:
        st.caption(
            "Faction multipliers (from data/meta_comparison_snapshot.json): "
            + ", ".join(f"{f} {m:.2f}×" for f, m in sorted(_mults.items()))
        )
    else:
        st.caption(
            "No faction multipliers available (data/meta_comparison_snapshot.json "
            "missing or empty). Equation predictions shown without meta correction."
        )

    # ---------------- predicted-vs-GW scatter ----------------
    st.divider()
    st.markdown("### Predicted vs GW points (log–log)")
    st.caption(
        "Each point is a unit. Above the y=x line → equation thinks GW "
        "undercosts it; below → overcosts. Hover to inspect."
    )

    _eligible = _eqfit_df["gw_points_per_model"] > 0
    _xs = _eqfit_df.loc[_eligible, "gw_points_per_model"].to_numpy()
    _ys = _adjusted[_eligible.to_numpy()]
    _names = _eqfit_df.loc[_eligible, "name"].to_numpy()
    _factions = _eqfit_df.loc[_eligible, "faction"].to_numpy()

    _fig = go.Figure()
    for fac in sorted(set(_factions)):
        mask = _factions == fac
        _fig.add_trace(go.Scatter(
            x=_xs[mask], y=_ys[mask],
            mode="markers",
            name=fac,
            marker=dict(size=7, color=colour_for(fac), opacity=0.8,
                        line=dict(width=0.5, color="white")),
            customdata=np.stack([_names[mask]], axis=-1),
            hovertemplate=("<b>%{customdata[0]}</b><br>"
                           f"Faction: {fac}<br>"
                           "GW pts/model: %{x:.1f}<br>"
                           "Predicted: %{y:.1f}<extra></extra>"),
        ))
    _lo = max(0.5, float(np.nanmin(_xs)) * 0.8)
    _hi = float(np.nanmax(_xs)) * 1.2
    _fig.add_trace(go.Scatter(
        x=[_lo, _hi], y=[_lo, _hi], mode="lines",
        line=dict(color="#FFD700", dash="dash", width=1.2),
        name="y = x", hoverinfo="skip",
    ))
    _fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#1a1d23",
        xaxis=dict(title="GW points / model (log)", type="log", gridcolor="#3a3d45"),
        yaxis=dict(title="Predicted points / model (log)", type="log", gridcolor="#3a3d45"),
        height=520, margin=dict(l=50, r=20, t=30, b=40),
        legend=dict(font=dict(size=10), bgcolor="rgba(26,29,35,0.85)"),
    )
    st.plotly_chart(_fig, use_container_width=True, key="eqfit_scatter")

    # ---------------- coefficient table ----------------
    st.divider()
    st.markdown("### Fitted coefficients")
    st.caption(
        "Each row is a feature's contribution to log(price). Positive = the "
        "feature pushes price up; negative = down. Interpretable on the "
        "log scale: β = 0.10 ≈ +10% price per unit increase (after transform)."
    )
    _coef_rows = [
        {
            "Feature": n,
            "Transform": t,
            "Coefficient (β)": round(float(c), 4),
            "exp(β) per unit": round(float(np.exp(c)), 3),
        }
        for n, t, c in sorted(
            zip(_result.feature_names, _result.transforms, _result.coefficients),
            key=lambda r: -abs(r[2]),
        )
    ]
    st.dataframe(_coef_rows, hide_index=True, use_container_width=True)

    # ---------------- outliers ----------------
    st.divider()
    st.markdown("### Outliers (top 20 each way)")
    st.caption(
        "Top of the iteration loop: units the equation strongly disagrees "
        "with GW on. Investigate; if real meta agrees with GW, the equation "
        "is missing a feature. If real meta agrees with the equation, "
        "this is a candidate mispricing in GW."
    )
    _resid_df = _eqfit_df.loc[_eligible].copy()
    _resid_df["predicted"] = _ys
    _resid_df["ratio"] = _ys / _resid_df["gw_points_per_model"]
    _resid_df["log_resid"] = np.log(_ys) - np.log(_resid_df["gw_points_per_model"])
    _resid_df = _resid_df.sort_values("log_resid")
    _col_lo, _col_hi = st.columns(2)
    with _col_lo:
        st.markdown("**Equation says CHEAPER than GW**")
        st.dataframe(
            _resid_df.head(20)[["name", "faction", "gw_points_per_model", "predicted", "ratio"]].rename(columns={
                "name": "Unit", "faction": "Faction",
                "gw_points_per_model": "GW", "predicted": "Pred", "ratio": "Ratio",
            }).round({"GW": 1, "Pred": 1, "Ratio": 2}),
            hide_index=True, use_container_width=True,
        )
    with _col_hi:
        st.markdown("**Equation says MORE EXPENSIVE than GW**")
        st.dataframe(
            _resid_df.tail(20).iloc[::-1][["name", "faction", "gw_points_per_model", "predicted", "ratio"]].rename(columns={
                "name": "Unit", "faction": "Faction",
                "gw_points_per_model": "GW", "predicted": "Pred", "ratio": "Ratio",
            }).round({"GW": 1, "Pred": 1, "Ratio": 2}),
            hide_index=True, use_container_width=True,
        )

    # ---------------- 3D surface explorer ----------------
    st.divider()
    st.markdown("### 3D surface explorer")
    st.caption(
        "Pick two features for the axes. The surface is the equation's "
        "predicted price across that 2D slice with all OTHER features held "
        "at their catalogue median. Real units are overlaid as points at "
        "their actual feature values + predicted price, coloured by faction."
    )

    # Only continuous features make sense as surface axes — boolean keywords
    # would just give a 4-corner surface that's not informative.
    _CONTINUOUS_FEATURES = [
        "wounds_per_model", "toughness", "save_quality", "invuln_quality",
        "fnp_quality", "ranged_attacks", "ranged_strength", "ranged_ap_abs",
        "ranged_damage_per_shot", "ranged_range", "melee_attacks",
        "melee_strength", "melee_ap_abs", "melee_damage_per_shot",
        "move", "oc", "min_models", "scout_distance",
        "expected_ranged_dmg_vs_meq", "expected_melee_dmg_vs_meq",
        "effective_wounds",
        "toughness_x_wounds", "total_wounds",
    ]
    # Keep only features that are actually in the current fit.
    _surface_options = [
        n for n in _CONTINUOUS_FEATURES
        if n in _result.feature_names
    ]
    if len(_surface_options) < 2:
        st.info(
            "Need at least two continuous features in the fit to draw the "
            "surface. Toggle on more numeric features above."
        )
    else:
        _sx_col, _sy_col, _scolor_col = st.columns(3)
        with _sx_col:
            _surf_x = st.selectbox(
                "X axis feature", _surface_options,
                index=_surface_options.index(
                    "wounds_per_model" if "wounds_per_model" in _surface_options
                    else _surface_options[0]
                ),
                key="eqfit_surf_x",
            )
        with _sy_col:
            _y_default = "toughness" if "toughness" in _surface_options else _surface_options[1]
            _surf_y = st.selectbox(
                "Y axis feature", [s for s in _surface_options if s != _surf_x],
                index=max(0, [s for s in _surface_options if s != _surf_x].index(_y_default))
                    if _y_default in _surface_options and _y_default != _surf_x else 0,
                key="eqfit_surf_y",
            )
        with _scolor_col:
            _surf_logz = st.checkbox(
                "Log Z axis (price)", value=True,
                key="eqfit_surf_logz",
                help="Compresses the price axis so cheap and premium units "
                     "share the same view; off shows linear scale.",
            )

        @st.cache_data(show_spinner="Building 3D surface…", max_entries=8)
        def _build_surface(
            spec_signature: Tuple[Tuple[str, str], ...],
            alpha: float,
            x_feature: str,
            y_feature: str,
            n_grid: int = 30,
        ):
            """
            Returns (XX, YY, ZZ, sample_units) for the 3D plot. ZZ is the
            predicted price (after faction multiplier averaging) across the
            (x_feature, y_feature) grid, with all other features held at
            their catalogue median.
            """
            specs = []
            for name, transform in spec_signature:
                base = _spec_by_name.get(name)
                description = base.description if base is not None else ""
                specs.append(
                    EqFitFeatureSpec(name=name, transform=transform,
                                     include=True, description=description)
                )
            result = eqfit_fit(_eqfit_df, specs)

            # Per-feature median across the live catalogue.
            medians = _eqfit_df[result.feature_names].median(numeric_only=True)

            x_min = float(_eqfit_df[x_feature].min())
            x_max = float(_eqfit_df[x_feature].max())
            y_min = float(_eqfit_df[y_feature].min())
            y_max = float(_eqfit_df[y_feature].max())
            # Guard against degenerate ranges
            if x_max <= x_min:
                x_max = x_min + 1.0
            if y_max <= y_min:
                y_max = y_min + 1.0

            xs = np.linspace(x_min, x_max, n_grid)
            ys = np.linspace(y_min, y_max, n_grid)
            XX, YY = np.meshgrid(xs, ys)

            # Build a synthetic DataFrame for the grid. Every feature
            # except X/Y is at its catalogue median.
            grid_data = {}
            for f in result.feature_names:
                if f == x_feature:
                    grid_data[f] = XX.flatten()
                elif f == y_feature:
                    grid_data[f] = YY.flatten()
                else:
                    grid_data[f] = np.full(XX.size, float(medians.get(f, 0.0)))
            synth_df = pd.DataFrame(grid_data)

            # Apply transforms + predict.
            from code.equation_data_fit import predict as eqfit_predict_fn
            preds = eqfit_predict_fn(synth_df, result, specs)
            ZZ = preds.reshape(n_grid, n_grid)
            return XX, YY, ZZ, x_min, x_max, y_min, y_max

        _XX, _YY, _ZZ, _xmin, _xmax, _ymin, _ymax = _build_surface(
            _spec_signature, float(_alpha), _surf_x, _surf_y,
        )

        # If log Z requested, take log of the surface (clamped to a small
        # positive minimum so we don't log zero).
        _Z_plot = np.log10(np.maximum(_ZZ, 0.5)) if _surf_logz else _ZZ

        _surface_fig = go.Figure()
        _surface_fig.add_trace(go.Surface(
            x=_XX, y=_YY, z=_Z_plot,
            opacity=0.5,
            colorscale="Viridis",
            showscale=False,
            name="fitted surface",
            hovertemplate=(
                f"{_surf_x}: %{{x:.2f}}<br>"
                f"{_surf_y}: %{{y:.2f}}<br>"
                + ("log10(price): %{z:.2f}<extra></extra>" if _surf_logz
                   else "price: %{z:.1f}<extra></extra>")
            ),
        ))

        # Real units overlaid as scatter, coloured by faction. Only points
        # whose X/Y land inside the surface's range (so the camera framing
        # stays sane).
        _eqfit_eligible = _eqfit_df["gw_points_per_model"] > 0
        _real_x = _eqfit_df.loc[_eqfit_eligible, _surf_x].to_numpy()
        _real_y = _eqfit_df.loc[_eqfit_eligible, _surf_y].to_numpy()
        _real_pred = _adjusted[_eqfit_eligible.to_numpy()]
        _real_z = np.log10(np.maximum(_real_pred, 0.5)) if _surf_logz else _real_pred
        _real_factions = _eqfit_df.loc[_eqfit_eligible, "faction"].to_numpy()
        _real_names = _eqfit_df.loc[_eqfit_eligible, "name"].to_numpy()
        _real_gw = _eqfit_df.loc[_eqfit_eligible, "gw_points_per_model"].to_numpy()

        _in_range = (
            (_real_x >= _xmin) & (_real_x <= _xmax)
            & (_real_y >= _ymin) & (_real_y <= _ymax)
        )

        # Group by faction so each gets its own legend entry.
        for fac in sorted(set(_real_factions[_in_range])):
            m = (_real_factions == fac) & _in_range
            if not m.any():
                continue
            _surface_fig.add_trace(go.Scatter3d(
                x=_real_x[m], y=_real_y[m], z=_real_z[m],
                mode="markers",
                name=fac,
                marker=dict(size=4, color=colour_for(fac), opacity=0.9,
                            line=dict(width=0.2, color="white")),
                customdata=np.stack([_real_names[m], _real_gw[m], _real_pred[m]], axis=-1),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    f"Faction: {fac}<br>"
                    f"{_surf_x}: %{{x:.2f}}<br>"
                    f"{_surf_y}: %{{y:.2f}}<br>"
                    "GW pts/model: %{customdata[1]:.1f}<br>"
                    "Predicted pts/model: %{customdata[2]:.1f}"
                    "<extra></extra>"
                ),
            ))

        _surface_fig.update_layout(
            template="plotly_dark", paper_bgcolor="#0e1117",
            scene=dict(
                xaxis_title=_surf_x,
                yaxis_title=_surf_y,
                zaxis_title=("log10(predicted price)" if _surf_logz
                             else "predicted price"),
                xaxis=dict(backgroundcolor="#1a1d23", gridcolor="#3a3d45"),
                yaxis=dict(backgroundcolor="#1a1d23", gridcolor="#3a3d45"),
                zaxis=dict(backgroundcolor="#1a1d23", gridcolor="#3a3d45"),
            ),
            height=640, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(font=dict(size=10), bgcolor="rgba(26,29,35,0.85)"),
        )
        st.plotly_chart(_surface_fig, use_container_width=True, key="eqfit_surface")

        st.caption(
            "Surface: equation's predicted price across the 2D slice "
            f"({_surf_x} × {_surf_y}), with every other feature held at its "
            "catalogue median. Points: real catalogue units. Distance from "
            "a point to the surface = how much that unit's other features "
            "differ from median. Faction colours match the scatter above."
        )

    # ---------------- tournament list validation ----------------
    # Independent real-world check on the equation: load Goonhammer-scraped
    # tournament lists, fuzzy-match every unit to UNIT_CATALOG, sum the
    # equation's prediction for each list, and compare to the player's
    # actual placement / win record. See code/tournament_validation.py
    # for the loader, matcher and scorer.
    st.divider()
    st.markdown("### Tournament list validation  —  real lists vs equation")
    st.caption(
        "Loads scraped tournament lists from `data/tournament_lists/`, "
        "fuzzy-matches each unit against `UNIT_CATALOG`, sums the equation's "
        "predicted price per list and compares the resulting **equation cost "
        "overrun** to how the list actually performed."
    )
    st.warning(
        "⚠ **Selection bias in the current dataset.** The scraped Goonhammer "
        "\"Competitive Innovations\" write-ups only publish podium finishers "
        "and a handful of notable lists per event — they do not publish the "
        "bottom of the table. That means every list in this dataset already "
        "won most of its games, the win-rate variance is heavily compressed, "
        "and a low R² on the win-rate scatter is mostly a feature of the "
        "censored sample rather than a fault of the equation. The "
        "placement-percentile scatter has more data (every list has a "
        "placement, only podium finishers have win/loss records) but the "
        "same bias applies — we're ranking winners against winners. The "
        "faction roll-up further down is the chart most robust to this "
        "bias because it averages across the meta."
    )

    with st.expander("Tournament list validation", expanded=False):
        @st.cache_data(show_spinner="Scoring tournament lists…", max_entries=8)
        def _tv_score_lists(spec_signature: Tuple[Tuple[str, str], ...],
                            alpha: float):
            specs = []
            for name, transform in spec_signature:
                base = _spec_by_name.get(name)
                description = base.description if base is not None else ""
                specs.append(EqFitFeatureSpec(
                    name=name, transform=transform, include=True,
                    description=description,
                ))
            fit_result = eqfit_fit(_eqfit_df, specs)

            mults: Dict[str, float] = {}
            if _META_SNAPSHOT_PATH.exists():
                snap = _json.loads(_META_SNAPSHOT_PATH.read_text(encoding="utf-8"))
                mults = eqfit_faction_multipliers(snap, alpha=alpha)

            try:
                raw_lists = tv_load_tournament_lists()
            except FileNotFoundError:
                return None, [], pd.DataFrame(), {}

            scored = []
            unmatched_counter: Dict[str, int] = {}
            for lr in raw_lists:
                match = tv_match_units(lr)
                for nm, _pts in match.unmatched:
                    unmatched_counter[nm] = unmatched_counter.get(nm, 0) + 1
                s = tv_score_list(match, fit_result, _eqfit_df, mults, specs=specs)
                if s is not None:
                    scored.append(s)
            faction_agg = tv_aggregate_by_faction(scored)
            return raw_lists, scored, faction_agg, unmatched_counter

        (_tv_raw_lists, _tv_scores, _tv_faction_agg,
         _tv_unmatched) = _tv_score_lists(
            _spec_signature, float(_alpha),
        )

        if _tv_raw_lists is None:
            st.info("No `data/tournament_lists/` directory found; add scraped "
                    "tournament JSON dumps to enable this view.")
        elif not _tv_scores:
            st.info("Loaded tournament lists but failed to score any of them. "
                    "The matcher rejected every unit — check that "
                    "`UNIT_CATALOG` was loaded.")
        else:
            # ---- coverage report ----
            _tv_n_loaded = len(_tv_raw_lists)
            _tv_n_scored = len(_tv_scores)
            _tv_n_with_record = sum(1 for s in _tv_scores if s.actual_winrate is not None)
            _tv_n_with_placement = sum(1 for s in _tv_scores if s.placement_percentile is not None)
            _tv_total_unmatched = sum(_tv_unmatched.values())

            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("Lists loaded", _tv_n_loaded,
                       help="Non-partial lists across all JSON files in data/tournament_lists/.")
            _c2.metric("Lists scored", _tv_n_scored,
                       help="Lists where at least one unit matched UNIT_CATALOG.")
            _c3.metric("With win/loss record", _tv_n_with_record,
                       help="Lists where the source article published a wins/losses record (usually podium finishers only).")
            _c4.metric("With placement", _tv_n_with_placement,
                       help="Lists where placement and event size are both known.")

            if _tv_total_unmatched:
                _top_unmatched = sorted(_tv_unmatched.items(),
                                        key=lambda kv: -kv[1])[:30]
                with st.expander(f"Unmatched unit names ({len(_tv_unmatched)} unique, "
                                 f"{_tv_total_unmatched} total appearances)"):
                    st.dataframe(
                        pd.DataFrame(_top_unmatched, columns=["unit_name", "appearances"]),
                        hide_index=True, use_container_width=True,
                    )
                    st.caption(
                        "These names didn't fuzzy-match any UNIT_CATALOG entry "
                        "in the list's faction scope above the 0.78 similarity "
                        "cutoff. Most are new releases, named characters or "
                        "Legends datasheets missing from BSData. They count "
                        "toward each list's total points but not toward the "
                        "equation prediction."
                    )

            def _render_scatter(target: str, y_label: str, y_unit: str,
                                chart_key: str):
                """Draw one overrun-vs-performance scatter with an OLS best fit."""
                dots = [s for s in _tv_scores
                        if (s.actual_winrate if target == "winrate"
                            else s.placement_percentile) is not None]
                if not dots:
                    st.info(f"No lists with {y_label.lower()} data available.")
                    return
                fit = tv_fit_winrate_model(_tv_scores, target=target)
                xs = np.array([s.overrun_ratio for s in dots])
                ys = np.array([(s.actual_winrate if target == "winrate"
                                else s.placement_percentile) for s in dots])
                facs_dots = [s.match.list_record.faction for s in dots]
                names = [f"{s.match.list_record.player} — {s.match.list_record.event_name}"
                         for s in dots]

                fig = go.Figure()
                for fac in sorted(set(facs_dots)):
                    mask = np.array([f == fac for f in facs_dots])
                    fig.add_trace(go.Scatter(
                        x=xs[mask], y=ys[mask] * 100.0,
                        mode="markers", name=fac,
                        marker=dict(size=10, color=colour_for(fac),
                                    line=dict(width=0.6, color="white"),
                                    opacity=0.85),
                        text=[names[i] for i, m in enumerate(mask) if m],
                        hovertemplate=("<b>%{text}</b><br>"
                                       f"Faction: {fac}<br>"
                                       "Overrun ratio: %{x:.2f}<br>"
                                       f"{y_label}: %{{y:.1f}}{y_unit}<extra></extra>"),
                    ))
                if fit is not None and fit.n >= 3:
                    line_xs = np.linspace(xs.min(), xs.max(), 50)
                    line_ys = (fit.intercept + fit.slope * line_xs) * 100.0
                    fig.add_trace(go.Scatter(
                        x=line_xs, y=line_ys, mode="lines",
                        line=dict(color="#9bd6ff", dash="solid", width=1.8),
                        name=(f"OLS fit  slope={fit.slope:+.2f}, "
                              f"R²={fit.r_squared:+.2f}, N={fit.n}"),
                    ))
                fig.add_vline(x=1.0, line=dict(color="#888", dash="dot", width=1),
                              annotation_text="equation = GW",
                              annotation_position="top right")
                fig.update_layout(
                    template="plotly_dark", paper_bgcolor="#0e1117",
                    plot_bgcolor="#1a1d23",
                    xaxis=dict(title="Equation overrun ratio  (predicted ÷ paid)",
                               gridcolor="#3a3d45"),
                    yaxis=dict(title=f"{y_label} ({y_unit.strip()})",
                               gridcolor="#3a3d45"),
                    height=460, margin=dict(l=50, r=20, t=30, b=40),
                    legend=dict(font=dict(size=10),
                                bgcolor="rgba(26,29,35,0.85)"),
                )
                st.plotly_chart(fig, use_container_width=True, key=chart_key)

            # ---- scatter 1: overrun vs actual win rate ----
            st.divider()
            st.markdown("#### Scatter 1  —  overrun vs actual win rate")
            st.caption(
                "Y = wins ÷ (wins + losses). Only podium finishers have full "
                f"records, so N is small ({_tv_n_with_record} lists). "
                "A positive slope means the equation correctly identifies "
                "stronger lists; expect a flat line on this view given the "
                "selection-bias caveat above."
            )
            _render_scatter("winrate", "Actual win rate", "%",
                            "eqfit_tv_scatter_winrate")

            # ---- scatter 2: overrun vs placement percentile ----
            st.divider()
            st.markdown("#### Scatter 2  —  overrun vs placement percentile")
            st.caption(
                "Y = 100% for 1st place at the event, 0% for last. Every list "
                f"with a placement is shown (N = {_tv_n_with_placement}), so "
                "this is our larger-sample view. Within-podium ranking: does "
                "the equation predict who finished higher among the winners?"
            )
            _render_scatter("placement", "Placement percentile", "%",
                            "eqfit_tv_scatter_placement")

            # ---- per-faction roll-up ----
            st.divider()
            st.markdown("#### Per-faction roll-up")
            st.caption(
                "Cross-check the equation against the Warp Friends per-faction "
                "tournament rates. If the equation is healthy, factions with "
                "high mean overrun should also have high Warp Friends win rates."
            )

            # Layer the Warp Friends rate from the meta snapshot.
            _wf_rates: Dict[str, float] = {}
            if _META_SNAPSHOT_PATH.exists():
                _wf_snap = _json.loads(_META_SNAPSHOT_PATH.read_text(encoding="utf-8"))
                for row in _wf_snap.get("factions", []):
                    if row.get("is_approx"):
                        continue
                    pct = row.get("tournament_pct")
                    if pct is None:
                        continue
                    _wf_rates[row["faction"]] = float(pct) / 100.0

            _fac_disp = _tv_faction_agg.copy()
            _fac_disp["warp_friends_winrate"] = _fac_disp["faction"].map(_wf_rates)

            _fac_table = _fac_disp.copy()
            _fac_table["mean_overrun_ratio"] = _fac_table["mean_overrun_ratio"].map(
                lambda v: f"{v:.2f}×" if v == v else "—")
            _fac_table["mean_actual_winrate"] = _fac_table["mean_actual_winrate"].map(
                lambda v: f"{v*100:.1f}%" if v is not None and v == v else "—")
            _fac_table["mean_placement_percentile"] = _fac_table["mean_placement_percentile"].map(
                lambda v: f"{v*100:.1f}%" if v is not None and v == v else "—")
            _fac_table["warp_friends_winrate"] = _fac_table["warp_friends_winrate"].map(
                lambda v: f"{v*100:.1f}%" if v == v else "—")
            st.dataframe(_fac_table, hide_index=True, use_container_width=True)

            # Bar chart pairs the equation-implied advantage with Warp Friends.
            _bar_rows = []
            for _, r in _fac_disp.iterrows():
                if r["warp_friends_winrate"] != r["warp_friends_winrate"]:  # NaN
                    continue
                _bar_rows.append({
                    "faction": r["faction"],
                    "Equation overrun (% above GW)": (r["mean_overrun_ratio"] - 1.0) * 100.0,
                    "Warp Friends winrate − 50 (%)":
                        (r["warp_friends_winrate"] - 0.5) * 100.0,
                })
            if _bar_rows:
                _bar_df = pd.DataFrame(_bar_rows).sort_values(
                    "Equation overrun (% above GW)", ascending=False,
                )
                _bar_fig = go.Figure()
                _bar_fig.add_trace(go.Bar(
                    x=_bar_df["faction"],
                    y=_bar_df["Equation overrun (% above GW)"],
                    name="Equation overrun (% above GW)",
                    marker_color="#9bd6ff",
                ))
                _bar_fig.add_trace(go.Bar(
                    x=_bar_df["faction"],
                    y=_bar_df["Warp Friends winrate − 50 (%)"],
                    name="Warp Friends winrate − 50 %",
                    marker_color="#c9a84c",
                ))
                _bar_fig.update_layout(
                    template="plotly_dark", paper_bgcolor="#0e1117",
                    plot_bgcolor="#1a1d23", barmode="group", height=400,
                    margin=dict(l=50, r=20, t=20, b=80),
                    xaxis=dict(tickangle=-30, gridcolor="#3a3d45"),
                    yaxis=dict(title="Percent", gridcolor="#3a3d45"),
                    legend=dict(font=dict(size=10),
                                bgcolor="rgba(26,29,35,0.85)"),
                )
                st.plotly_chart(_bar_fig, use_container_width=True,
                                key="eqfit_tv_faction_bars")

            # ---- per-list explorer ----
            st.divider()
            st.markdown("#### Per-list explorer")
            _list_rows = []
            for s in _tv_scores:
                lr = s.match.list_record
                rec = (f"{lr.wins}-{lr.losses}-{lr.draws}"
                       if lr.wins is not None else "—")
                _list_rows.append({
                    "event": lr.event_name,
                    "player": lr.player,
                    "faction": lr.faction,
                    "detachment": lr.detachment or "—",
                    "placement": lr.placement if lr.placement is not None else "—",
                    "record": rec,
                    "predicted_total": round(s.predicted_total, 1),
                    "gw_total (matched)": s.gw_total,
                    "overrun_ratio": round(s.overrun_ratio, 3),
                    "coverage": f"{s.match.coverage_ratio*100:.0f}%",
                })
            st.dataframe(pd.DataFrame(_list_rows), hide_index=True,
                         use_container_width=True)

            st.caption(
                "**Scope.** Three scraped Goonhammer events, "
                f"{_tv_n_scored} scored lists, {_tv_n_with_record} with full "
                "win/loss records — wide confidence intervals on the "
                "regression. Win rate is per-list (army-level), not per-unit. "
                "Fuzzy name matching uses a 0.78 similarity cutoff scoped "
                "to the list's faction; unmatched units are reported above."
            )

    # ---------------- archetype-proxy validation ----------------
    # Faction-level fallback for factions without good per-list data in the
    # tournament dump above. Sums the equation across each faction's
    # canonical archetype list and compares against per-faction tournament
    # win rates.
    st.divider()
    st.markdown("### Validation: archetype list value vs real meta")
    st.warning(
        "⚠ **Faction-level proxy.** Sums the equation's stats-only "
        "prediction across each faction's canonical archetype list (no "
        "faction multiplier) and compares to that faction's real "
        "tournament win rate. Per-list validation against scraped "
        "tournament rosters lives in the **Tournament list validation** "
        "section above; this archetype proxy is the wider-coverage "
        "fallback for factions with few or no real lists in the scraped "
        "dataset."
    )

    st.caption(
        "**Hypothesis:** if the equation captures real unit value better "
        "than GW does, then a strong faction's archetype should sum to "
        "MORE than 2000 equation-pts (their list is built from units the "
        "equation thinks GW underprices). A weak faction's archetype "
        "should sum to less or near 2000. Look for a positive correlation "
        "between equation sum and real-meta win rate."
    )

    _proxy_budget = st.slider(
        "Budget per archetype (pts)", min_value=1000, max_value=2500,
        value=2000, step=100, key="eqfit_proxy_budget",
        help="Standard tournament budget is 2000. Lowering shrinks the lists.",
    )
    _proxy_n_builds = st.slider(
        "Builds per faction (averaged to smooth random fill)",
        min_value=1, max_value=20, value=5, step=1,
        key="eqfit_proxy_n_builds",
        help="The archetype builder tops up with same-faction random picks. "
             "Averaging multiple builds smooths that noise.",
    )

    @st.cache_data(show_spinner="Building archetype proxies…", max_entries=4)
    def _archetype_proxy_table(
        spec_signature: Tuple[Tuple[str, str], ...],
        budget: float,
        n_builds: int,
    ):
        """For each faction with an archetype, compute the average
        equation-sum (stats-only) across n_builds random instantiations."""
        from code.archetypes import ARCHETYPES, build_archetype_army, has_archetype
        from code.units import UNIT_CATALOG
        import random as _random

        # Recompute the fit so we have the up-to-date stats-only predictions.
        specs = []
        for name, transform in spec_signature:
            base = _spec_by_name.get(name)
            description = base.description if base is not None else ""
            specs.append(
                EqFitFeatureSpec(name=name, transform=transform,
                                 include=True, description=description)
            )
        result = eqfit_fit(_eqfit_df, specs)
        key_to_pred = {
            key: float(p)
            for key, p in zip(_eqfit_df["key"].to_numpy(), result.predicted_price)
        }
        # Reverse map: profile id → unit key.
        id_to_key = {id(v): k for k, v in UNIT_CATALOG.items()}

        # Meta snapshot for real win rates.
        meta_winrates: Dict[str, float] = {}
        if _META_SNAPSHOT_PATH.exists():
            snap = _json.loads(_META_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            for row in snap.get("factions", []):
                if row.get("is_approx"):
                    continue
                meta_winrates[row["faction"]] = float(row.get("tournament_pct", 0)) / 100.0

        rows = []
        for faction, archetypes_dict in ARCHETYPES.items():
            if not has_archetype(faction):
                continue
            arch_name = list(archetypes_dict.keys())[0]  # first archetype as canonical

            sums_eq = []
            sums_gw = []
            n_models_list = []
            for seed in range(n_builds):
                rng = _random.Random(seed)
                army = build_archetype_army(
                    "P", faction, budget, rng=rng, archetype_name=arch_name,
                )
                if not army.units:
                    continue
                eq_total = 0.0
                gw_total = 0.0
                for u in army.units:
                    profile = u.profile if hasattr(u, "profile") else None
                    if profile is None:
                        continue
                    k = id_to_key.get(id(profile))
                    if k is None or k not in key_to_pred:
                        continue
                    eq_total += key_to_pred[k]
                    # Use profile.points_cost (the property that falls back
                    # to the Lanchester-derived score when points_per_squad
                    # is 0 — Carnifexes / Ironstrider Ballistarii / 38 such
                    # units across the catalogue) so the GW sum tracks the
                    # actual budget the army builder spent.
                    gw_total += float(profile.points_cost)
                sums_eq.append(eq_total)
                sums_gw.append(gw_total)
                n_models_list.append(len(army.units))
            if not sums_eq:
                continue
            rows.append({
                "Faction": faction,
                "Archetype": arch_name,
                "Models (avg)": round(float(np.mean(n_models_list)), 1),
                "GW sum (avg)": round(float(np.mean(sums_gw)), 1),
                "Equation sum (avg)": round(float(np.mean(sums_eq)), 1),
                "Equation - GW (avg)": round(float(np.mean(sums_eq) - np.mean(sums_gw)), 1),
                "Real win rate": meta_winrates.get(faction, None),
                "Has real data": faction in meta_winrates,
            })
        return rows

    _proxy_rows = _archetype_proxy_table(
        _spec_signature, float(_proxy_budget), int(_proxy_n_builds),
    )

    if not _proxy_rows:
        st.info("No archetypes available — check code/archetypes.py.")
    else:
        # Scatter for the factions that DO have real data.
        with_real = [r for r in _proxy_rows if r["Has real data"]]
        if with_real:
            _scatter_xs = [r["Real win rate"] * 100 for r in with_real]
            _scatter_ys = [r["Equation sum (avg)"] for r in with_real]
            _scatter_labels = [r["Faction"] for r in with_real]
            _scatter_models = [r["Models (avg)"] for r in with_real]

            _proxy_fig = go.Figure()
            for r in with_real:
                _proxy_fig.add_trace(go.Scatter(
                    x=[r["Real win rate"] * 100],
                    y=[r["Equation sum (avg)"]],
                    mode="markers+text",
                    text=[r["Faction"][:18]],
                    textposition="top center",
                    marker=dict(size=11, color=colour_for(r["Faction"]),
                                line=dict(width=0.6, color="white")),
                    name=r["Faction"],
                    hovertemplate=(
                        f"<b>{r['Faction']}</b><br>"
                        f"Archetype: {r['Archetype']}<br>"
                        f"Real WR: {r['Real win rate']*100:.1f}%<br>"
                        f"Equation sum: {r['Equation sum (avg)']:.0f} pts<br>"
                        f"GW sum: {r['GW sum (avg)']:.0f} pts<br>"
                        f"Models avg: {r['Models (avg)']:.0f}"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                ))
            # Reference: budget line (where equation sum equals GW budget).
            _proxy_fig.add_hline(
                y=_proxy_budget, line=dict(color="#FFD700", dash="dash", width=1.2),
                annotation_text=f"y = {_proxy_budget} pts (GW budget)",
                annotation_position="bottom right",
            )
            _proxy_fig.add_vline(
                x=50.0, line=dict(color="#888", dash="dot", width=1),
                annotation_text="50% WR",
                annotation_position="top right",
            )
            # Best-fit line if we have ≥3 points.
            if len(with_real) >= 3:
                xs = np.array(_scatter_xs)
                ys = np.array(_scatter_ys)
                slope, intercept = np.polyfit(xs, ys, 1)
                line_xs = np.linspace(xs.min() - 2, xs.max() + 2, 50)
                line_ys = slope * line_xs + intercept
                # Pearson correlation.
                corr = float(np.corrcoef(xs, ys)[0, 1])
                _proxy_fig.add_trace(go.Scatter(
                    x=line_xs, y=line_ys, mode="lines",
                    line=dict(color="#9bd6ff", dash="solid", width=1.5),
                    name=f"linear fit (r={corr:+.3f})",
                ))
            _proxy_fig.update_layout(
                template="plotly_dark", paper_bgcolor="#0e1117",
                plot_bgcolor="#1a1d23",
                xaxis=dict(title="Real-meta win rate (%)", gridcolor="#3a3d45"),
                yaxis=dict(title="Equation sum across archetype (pts)",
                           gridcolor="#3a3d45"),
                title=dict(text="Equation sum vs real meta win rate, per faction archetype",
                           font=dict(color="#c9a84c", size=13)),
                height=520, margin=dict(l=50, r=20, t=40, b=40),
                legend=dict(font=dict(size=10), bgcolor="rgba(26,29,35,0.85)"),
            )
            st.plotly_chart(_proxy_fig, use_container_width=True,
                            key="eqfit_proxy_scatter")

            if len(with_real) >= 3:
                xs = np.array(_scatter_xs)
                ys = np.array(_scatter_ys)
                corr = float(np.corrcoef(xs, ys)[0, 1])
                if corr > 0.3:
                    interp = ("**Positive correlation** — winning factions' archetypes "
                              "sum to more equation-pts. Directional support for the "
                              "equation capturing real value GW underprices.")
                elif corr < -0.3:
                    interp = ("**Negative correlation** — winning factions' archetypes "
                              "sum to LESS equation-pts. Unexpected; might mean the "
                              "equation is over-weighting features that don't actually "
                              "drive tournament wins.")
                else:
                    interp = ("**No clear correlation** — the equation's residuals "
                              "(deviations from GW pricing) don't predict real-meta "
                              "win rate at the archetype level. Could mean the faction "
                              "multipliers are doing most of the calibration work, or "
                              "the per-faction signal is too small to detect with 10 data points.")
                st.markdown(f"Pearson r = `{corr:+.3f}` across {len(with_real)} factions. " + interp)
        else:
            st.info(
                "No factions in the meta snapshot have real tournament data. "
                "All 22 factions are FX_ALL placeholders — the validation can't run."
            )

        # Show the full table, including FX_ALL factions for reference.
        st.markdown("**Per-archetype values** (factions without real meta data shown for reference):")
        _proxy_df_display = pd.DataFrame(_proxy_rows)
        if "Real win rate" in _proxy_df_display.columns:
            _proxy_df_display["Real win rate"] = _proxy_df_display["Real win rate"].apply(
                lambda v: f"{v*100:.1f}%" if v is not None else "—"
            )
        st.dataframe(_proxy_df_display.drop(columns=["Has real data"]),
                     hide_index=True, use_container_width=True)
