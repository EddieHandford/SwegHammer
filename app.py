"""SwegHammer — Streamlit battle simulator dashboard."""

from __future__ import annotations

import random
from io import BytesIO
from typing import Callable, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
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
from code.compare_view import render_compare_tab

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
    fig = render_frame(
        map_, events, frame_idx, frames=frames,
        colour_a=col_a, colour_b=col_b,
    )
    buf = BytesIO()
    # DPI 90 (was 110): ~30% faster encode with no visible loss in the
    # Streamlit column width (which is typically ~500-700px wide).
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), dpi=90)
    plt.close(fig)
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


def _composition_total_points(comp: List[Tuple[str, int]]) -> float:
    return sum(UNIT_CATALOG[k].points_cost * n for k, n in comp if n > 0)


def _composition_faction(comp: List[Tuple[str, int]]) -> str:
    """The faction of the first non-zero entry — used to pick the army's colour."""
    for k, n in comp:
        if n > 0:
            return UNIT_CATALOG[k].faction
    return ""


def _build_army_from_composition(
    name: str, comp: List[Tuple[str, int]], in_cover: bool = False,
) -> Army:
    keys: List[str] = []
    for unit_key, count in comp:
        keys.extend([unit_key] * max(0, int(count)))
    if not keys:
        # No units selected — return an empty army (battle will just walk over)
        return Army(name, in_cover=in_cover)
    return build_army_from_list(name, keys, in_cover=in_cover)


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
) -> List[BattleResult]:
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
        points = st.slider("Points per army", 100, 1500, preset["points"], step=50)
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
        profile_a = UNIT_CATALOG[next((k for k, n in a_comp if n > 0), a_comp[0][0])] if a_comp else None
        profile_b = UNIT_CATALOG[next((k for k, n in b_comp if n > 0), b_comp[0][0])] if b_comp else None

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

            state_key = f"{side}_comp"
            if state_key not in st.session_state:
                st.session_state[state_key] = [(available[0], 5)]

            # Reset rows that no longer belong to the chosen faction
            if not all(uk in available for uk, _ in st.session_state[state_key]):
                st.session_state[state_key] = [(available[0], 5)]

            new_comp: List[Tuple[str, int]] = []
            for i, (uk, cnt) in enumerate(st.session_state[state_key]):
                c1, c2 = st.columns([5, 2])
                chosen = c1.selectbox(
                    f"Unit type {i + 1}", available,
                    index=available.index(uk),
                    format_func=lambda k: UNIT_CATALOG[k].name,
                    key=f"{side}_u_{i}",
                )
                count = c2.number_input(
                    "Count", min_value=0, max_value=99, value=int(cnt), step=1,
                    key=f"{side}_c_{i}",
                )
                new_comp.append((chosen, int(count)))
            st.session_state[state_key] = new_comp

            cc1, cc2 = st.columns(2)
            if cc1.button(f"+ Add unit type", key=f"{side}_add"):
                st.session_state[state_key].append((available[0], 1))
                st.rerun()
            if len(new_comp) > 1 and cc2.button("− Remove last", key=f"{side}_rm"):
                st.session_state[state_key].pop()
                st.rerun()

            total_pts = _composition_total_points(new_comp)
            total_models = sum(n for _, n in new_comp if n > 0)
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
        profile_a = UNIT_CATALOG[next((k for k, n in a_comp if n > 0), a_comp[0][0])] if a_comp else None
        profile_b = UNIT_CATALOG[next((k for k, n in b_comp if n > 0), b_comp[0][0])] if b_comp else None

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
    for unit_key, count in comp:
        if count <= 0:
            continue
        p = UNIT_CATALOG[unit_key]
        unit_pts = p.points_cost * count
        unit_hp = p.health * count
        sv_str = f"{p.save}+" if p.save <= 6 else "—"
        rows.append({
            "Unit":   p.name,
            "Count":  count,
            "W":      f"{p.health:g}",
            "T":      p.toughness,
            "Sv":     sv_str,
            "A×D":    f"{p.attacks}×{p.weapon_damage_per_shot:g}",
            "AP":     p.ap if p.ap else 0,
            "Pts ea": f"{p.points_cost:.0f}",
            "Total":  f"{unit_pts:.0f}",
            "Abil":   _ability_glyphs(p),
        })
        total_models += count
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

    _battle_bar = st.progress(0, text=f"Running battles… 0 / {n_battles:,}")
    def _battle_progress(done: int, total: int) -> None:
        _battle_bar.progress(done / total, text=f"Running battles… {done:,} / {total:,}")

    results = run_simulations(
        factory_a, factory_b, n_battles,
        map_=selected_map, on_progress=_battle_progress,
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
        for _ in range(30):
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
# Tabs: Statistics + Watch a battle
# ---------------------------------------------------------------------------

tab_stats, tab_replay, tab_efficiency, tab_equilibrium, tab_compare = st.tabs(
    ["Statistics", "Watch a battle", "Efficiency", "Equilibrium", "Compare"]
)

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

    # ---- Controls ----
    st.divider()
    _col_anchor, _col_anchor_pts, _col_role = st.columns([3, 1, 2])

    _shooty_keys = sorted([k for k, u in UNIT_CATALOG.items()
                           if u.attacks > 0 and u.range_inches > 0])
    _default_anchor = (
        EQ_DEFAULT_ANCHOR if EQ_DEFAULT_ANCHOR in _shooty_keys else _shooty_keys[0]
    )
    with _col_anchor:
        _anchor_key = st.selectbox(
            "Anchor unit  (its cost is held fixed; everything else floats)",
            _shooty_keys,
            index=_shooty_keys.index(_default_anchor),
            format_func=lambda k: f"{UNIT_CATALOG[k].name}  —  {UNIT_CATALOG[k].faction}",
            key="eq_anchor_key",
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
        )
    with _col_role:
        _role_filter = st.multiselect(
            "Role filter",
            options=["shooty", "dual"],
            default=["shooty", "dual"],
            key="eq_role_filter",
            help="`shooty` = no melee profile, `dual` = also has melee. Pure-melee units are excluded from Phase 1.",
        )

    # ---- Cached compute ----
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

    try:
        _result = _equilibrium_result(_anchor_key, float(_anchor_pts))
    except ValueError as _exc:
        st.error(f"Couldn't compute equilibrium: {_exc}")
        st.stop()

    # ---- Faction filter (operates on cached entries — re-renders only) ----
    _all_factions = sorted({e.faction for e in _result.entries if e.faction})
    _selected_factions = st.multiselect(
        "Show factions",
        options=_all_factions,
        default=_all_factions,
        key="eq_faction_filter",
    )

    _filtered = [
        e for e in _result.entries
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

        # ---- Scatter plot ----
        _xs = np.array([e.gw_points_per_model for e in _filtered])
        _ys = np.array([e.equilibrium_points_per_model for e in _filtered])
        _factions = [e.faction for e in _filtered]
        _names = [e.name for e in _filtered]
        _cols = [colour_for(f) for f in _factions]

        # Filter out degenerate points (GW = 0 means no listed points)
        _valid = (_xs > 0) & (_ys > 0)
        _xs_p, _ys_p = _xs[_valid], _ys[_valid]
        _cols_p = [c for c, v in zip(_cols, _valid) if v]
        _names_p = [n for n, v in zip(_names, _valid) if v]

        _fig, _ax = plt.subplots(figsize=(12, 7))
        _fig.patch.set_facecolor("#0e1117")
        _ax.set_facecolor("#1a1d23")

        _ax.scatter(_xs_p, _ys_p, c=_cols_p, s=28, alpha=0.78,
                    linewidths=0.3, edgecolors="white")

        _lo = float(min(_xs_p.min(), _ys_p.min())) if len(_xs_p) else 1.0
        _hi = float(max(_xs_p.max(), _ys_p.max())) if len(_xs_p) else 1000.0
        _ax.plot([_lo, _hi], [_lo, _hi], color="#FFD700", linestyle="--",
                 linewidth=1.0, label="y = x (fair)")

        # Label most-mispriced outliers
        if len(_xs_p) >= 4:
            _log_ratio = np.log(_ys_p / _xs_p)
            _n_labels = min(6, len(_xs_p) // 5)
            _worst_under = np.argsort(_log_ratio)[-_n_labels:]
            _worst_over = np.argsort(_log_ratio)[:_n_labels]
            for _i in list(_worst_under) + list(_worst_over):
                _ax.annotate(
                    _names_p[_i],
                    (_xs_p[_i], _ys_p[_i]),
                    fontsize=6.5, color="white", alpha=0.9,
                    xytext=(4, 3), textcoords="offset points",
                )

        # Faction legend (sample of visible factions only)
        _seen = set()
        for _f, _c in zip(_factions, _cols):
            if _f not in _seen and len(_seen) < 22:
                _seen.add(_f)
                _ax.scatter([], [], color=_c, s=30, label=_f)
        _ax.legend(loc="upper left", fontsize=6.5,
                   facecolor="#1a1d23", edgecolor="#444", labelcolor="white",
                   ncol=max(1, len(_seen) // 18))

        _ax.set_xscale("log")
        _ax.set_yscale("log")
        _ax.set_xlabel("GW points per model  (log)", color="white", fontsize=11)
        _ax.set_ylabel("Equilibrium points per model  (log)", color="white", fontsize=11)
        _ax.set_title(
            "Above diagonal → GW undercosted  ·  Below diagonal → GW overcosted",
            color="white", fontsize=11, pad=8,
        )
        _ax.tick_params(colors="white", which="both")
        for _s in _ax.spines.values():
            _s.set_edgecolor("#444")
        _ax.grid(True, alpha=0.15, color="#888", linestyle=":")

        _fig.tight_layout()
        st.pyplot(_fig)

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
