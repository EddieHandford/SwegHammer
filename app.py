"""SwegHammer — Streamlit battle simulator dashboard."""

from __future__ import annotations

import random
from typing import Callable, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import streamlit as st

from code.army import Army
from code.army_builder import build_homogeneous_army
from code.events import EventLog
from code.map import Map
from code.maps import STOCK_MAPS, DEFAULT_MAP
from code.renderer import event_description, render_frame
from code.simulator import Battle, BattleResult
from code.units import UNIT_CATALOG, UnitProfile, save_probability

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SwegHammer Simulator",
    page_icon="⚔️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COL_A = "#4e9af1"
COL_B = "#e05c5c"
COL_DRAW = "#aaaaaa"

# ---------------------------------------------------------------------------
# Preset battle definitions
# ---------------------------------------------------------------------------

PRESETS = {
    "⚔️  Classic: Space Marines vs Ork Boys": {
        "description": (
            "The quintessential matchup — disciplined, high-accuracy Marines "
            "against a swarm of brutal Ork Boys. Elite armour and AP vs sheer numbers."
        ),
        "a_name": "Space Marines",
        "a_key": "space_marine",
        "b_name": "Ork Boys",
        "b_key": "ork_boy",
        "points": 300,
    },
    "💀  Elite Clash: Terminators vs Tyranid Warriors": {
        "description": (
            "Heavy-armoured Terminators (2+ save, AP-2) face Tyranid Warriors "
            "(4+ save, AP-1). Two elite units with real staying power."
        ),
        "a_name": "Terminators",
        "a_key": "terminator",
        "b_name": "Tyranid Warriors",
        "b_key": "warrior",
        "points": 300,
    },
    "🦾  Tank vs Horde: Predator vs Gretchin": {
        "description": (
            "A Predator Tank (AP-3, 11 health) tries to grind through a tide of "
            "Gretchin (6+ save, 1 health each). Firepower vs volume of bodies."
        ),
        "a_name": "Predator Tank",
        "a_key": "predator_tank",
        "b_name": "Gretchin",
        "b_key": "gretchin",
        "points": 300,
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
):
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

    mode = st.radio("Mode", ["Preset Battle", "Custom Battle"], horizontal=True)
    st.divider()

    if mode == "Preset Battle":
        preset_key = st.selectbox("Choose a preset", list(PRESETS.keys()))
        preset = PRESETS[preset_key]
        st.info(preset["description"])

        a_name = preset["a_name"]
        b_name = preset["b_name"]
        profile_a = UNIT_CATALOG[preset["a_key"]]
        profile_b = UNIT_CATALOG[preset["b_key"]]
        points = st.slider("Points per army", 100, 600, preset["points"], step=50)

    else:
        st.subheader("Army A")
        a_name = st.text_input("Army A name", value="Army Alpha")
        a_unit_key = st.selectbox(
            "Army A unit", list(UNIT_CATALOG.keys()),
            format_func=lambda k: UNIT_CATALOG[k].name,
        )
        profile_a = UNIT_CATALOG[a_unit_key]

        st.subheader("Army B")
        b_name = st.text_input("Army B name", value="Army Bravo")
        b_unit_key = st.selectbox(
            "Army B unit", list(UNIT_CATALOG.keys()), index=10,
            format_func=lambda k: UNIT_CATALOG[k].name,
        )
        profile_b = UNIT_CATALOG[b_unit_key]

        points = st.slider("Points per army", 100, 600, 300, step=50)

    st.divider()
    st.subheader("Battlefield")
    map_key = st.selectbox(
        "Map",
        list(STOCK_MAPS.keys()),
        format_func=lambda k: STOCK_MAPS[k].name,
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
# Army preview
# ---------------------------------------------------------------------------

army_a_preview = build_homogeneous_army(a_name, profile_a, points, in_cover=a_cover)
army_b_preview = build_homogeneous_army(b_name, profile_b, points, in_cover=b_cover)

st.title("⚔️ SwegHammer Battle Simulator")

col1, col_vs, col2 = st.columns([5, 1, 5])

with col1:
    unit_card(profile_a, f"🔵 {a_name}", COL_A, a_cover)
    st.caption(
        f"{'🏠 In cover  ' if a_cover else ''}"
        f"{len(army_a_preview.units)} units @ {points} pts"
    )

with col_vs:
    st.markdown(
        "<div style='text-align:center;font-size:2rem;padding-top:2.5rem'>⚡</div>",
        unsafe_allow_html=True,
    )

with col2:
    unit_card(profile_b, f"🔴 {b_name}", COL_B, b_cover)
    st.caption(
        f"{'🏠 In cover  ' if b_cover else ''}"
        f"{len(army_b_preview.units)} units @ {points} pts"
    )

st.divider()

# ---------------------------------------------------------------------------
# Run and display results
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Run handler — populates st.session_state with stats results and one replay
# ---------------------------------------------------------------------------

if run:
    factory_a = lambda: build_homogeneous_army(a_name, profile_a, points, in_cover=a_cover)
    factory_b = lambda: build_homogeneous_army(b_name, profile_b, points, in_cover=b_cover)

    with st.spinner(f"Running {n_battles:,} battles + capturing one replay..."):
        results = run_simulations(factory_a, factory_b, n_battles, map_=selected_map)
        log = EventLog()
        Battle(factory_a(), factory_b(), subscribers=[log], map_=selected_map).run()

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
        "replay_map": selected_map,
    })

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

        st.divider()

        c_pie, c_attr = st.columns([2, 3])
        with c_pie:
            st.pyplot(chart_win_rates(a_wins, b_wins, draws, a_lbl, b_lbl, n))
        with c_attr:
            st.pyplot(chart_attrition(results, a_lbl, b_lbl))

        st.divider()
        st.pyplot(chart_survivor_histogram(results, a_lbl, b_lbl))

        if st.session_state.get("show_points_curve"):
            st.divider()
            with st.spinner("Sweeping point budgets for probability curve..."):
                st.pyplot(
                    chart_win_rate_vs_points(
                        st.session_state["profile_a"], st.session_state["profile_b"],
                        a_lbl, b_lbl,
                        st.session_state["a_cover"], st.session_state["b_cover"],
                        n_battles=200,
                        map_=st.session_state["replay_map"],
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
            tick = st.slider(
                "Tick (drag to scrub through the battle)",
                min_value=0,
                max_value=total - 1,
                value=0,
                key="replay_tick",
            )

            col_map, col_log = st.columns([3, 2])

            with col_map:
                fig = render_frame(map_, events, tick)
                st.pyplot(fig)
                plt.close(fig)

            with col_log:
                st.markdown("**Current event**")
                st.code(event_description(events[tick]), language=None)

                st.markdown("**Recent events**")
                start = max(0, tick - 12)
                recent = "\n".join(event_description(events[i]) for i in range(start, tick + 1))
                st.text(recent)

                st.caption(f"{total} events total")
