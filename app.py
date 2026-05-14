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
) -> List[BattleResult]:
    return [Battle(factory_a(), factory_b(), map_=map_).run() for _ in range(n)]


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
    n_battles = st.slider("Simulations", 100, 2000, 500, step=100)
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

    with st.spinner(f"Running {n_battles:,} battles + capturing one replay..."):
        results = run_simulations(factory_a, factory_b, n_battles, map_=selected_map)

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
        with st.spinner(f"Pre-rendering {len(replay_frames)} replay frames..."):
            st.session_state["replay_pngs"] = [
                _render_frame_png(replay_id, i)
                for i in range(len(replay_frames))
            ]
    else:
        st.session_state["replay_pngs"] = []

    # Pre-compute the points-curve data here too if the toggle is on.
    # Otherwise the Statistics tab re-runs ~2200 simulations on every
    # script re-execution (incl. tab switches) — the actual cause of
    # the multi-second "Watch a battle" tab-click delay.
    if show_points_curve and profile_a and profile_b:
        with st.spinner("Sweeping point budgets for probability curve..."):
            point_values = list(range(100, 601, 50))
            a_rates_p, b_rates_p, draw_rates_p = [], [], []
            for pts in point_values:
                res = run_simulations(
                    lambda p=pts: build_homogeneous_army(a_name, profile_a, p, in_cover=a_cover),
                    lambda p=pts: build_homogeneous_army(b_name, profile_b, p, in_cover=b_cover),
                    200, map_=selected_map,
                )
                aw, bw, d = aggregate(res, a_name, b_name)
                a_rates_p.append(aw / 200)
                b_rates_p.append(bw / 200)
                draw_rates_p.append(d / 200)
            st.session_state["points_curve_data"] = (
                point_values, a_rates_p, b_rates_p, draw_rates_p,
            )
    else:
        st.session_state["points_curve_data"] = None

# ---------------------------------------------------------------------------
# Tabs: Statistics + Watch a battle
# ---------------------------------------------------------------------------

tab_stats, tab_replay = st.tabs(["Statistics", "Watch a battle"])

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
