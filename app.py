"""SwegHammer — Streamlit battle simulator dashboard."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Callable, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import streamlit as st

from code.army import Army
from code.army_builder import build_homogeneous_army
from code.simulator import Battle, BattleResult
from code.units import UNIT_CATALOG, UnitProfile

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

COL_A = "#4e9af1"   # army A — blue
COL_B = "#e05c5c"   # army B — red
COL_DRAW = "#aaaaaa"

# ---------------------------------------------------------------------------
# Preset battle definitions
# ---------------------------------------------------------------------------

PRESETS = {
    "⚔️  Classic: Space Marines vs Ork Boys": {
        "description": (
            "The quintessential matchup — disciplined, high-accuracy Marines "
            "against a swarm of brutal Ork Boys. Elite skill vs sheer numbers."
        ),
        "a_name": "Space Marines",
        "a_key": "space_marine",
        "b_name": "Ork Boys",
        "b_key": "ork_boy",
        "points": 300,
    },
    "💀  Elite Clash: Terminators vs Tyranid Warriors": {
        "description": (
            "Heavy-armoured Terminators face off against Tyranid Warriors — "
            "two elite units with high health and solid damage output."
        ),
        "a_name": "Terminators",
        "a_key": "terminator",
        "b_name": "Tyranid Warriors",
        "b_key": "warrior",
        "points": 300,
    },
    "🦾  Tank vs Horde: Predator vs Gretchin": {
        "description": (
            "A lone Predator Tank tries to grind through a tide of Gretchin. "
            "Can raw firepower beat overwhelming numbers?"
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
) -> List[BattleResult]:
    results = []
    for _ in range(n):
        result = Battle(factory_a(), factory_b()).run()
        results.append(result)
    return results


def aggregate(results: List[BattleResult], a_name: str, b_name: str):
    a_wins = sum(1 for r in results if r.winner == a_name)
    b_wins = sum(1 for r in results if r.winner == b_name)
    draws = len(results) - a_wins - b_wins
    return a_wins, b_wins, draws


def avg_attrition(results: List[BattleResult]) -> Tuple[List[float], List[float]]:
    """Return (avg_a_per_round, avg_b_per_round) aligned to the longest battle."""
    max_len = max(len(r.round_history) for r in results)
    a_sums = [0.0] * max_len
    b_sums = [0.0] * max_len
    counts = [0] * max_len

    for r in results:
        for i, (a, b) in enumerate(r.round_history):
            a_sums[i] += a
            b_sums[i] += b
            counts[i] += 1

    a_avg = [a_sums[i] / counts[i] for i in range(max_len)]
    b_avg = [b_sums[i] / counts[i] for i in range(max_len)]
    return a_avg, b_avg

# ---------------------------------------------------------------------------
# Chart functions
# ---------------------------------------------------------------------------

def chart_win_rates(a_wins, b_wins, draws, a_name, b_name, n):
    fig, ax = plt.subplots(figsize=(4, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    labels = [a_name, b_name, "Draw"]
    sizes = [a_wins, b_wins, draws]
    colors = [COL_A, COL_B, COL_DRAW]
    explode = (0.04, 0.04, 0.02)

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        colors=colors,
        explode=explode,
        autopct=lambda p: f"{p:.1f}%" if p > 1 else "",
        startangle=90,
        wedgeprops=dict(linewidth=1.5, edgecolor="#0e1117"),
        textprops=dict(color="white"),
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_color("white")
        at.set_fontweight("bold")

    ax.legend(
        handles=[
            mpatches.Patch(color=COL_A, label=f"{a_name}  {a_wins/n:.1%}"),
            mpatches.Patch(color=COL_B, label=f"{b_name}  {b_wins/n:.1%}"),
            mpatches.Patch(color=COL_DRAW, label=f"Draw  {draws/n:.1%}"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.18),
        frameon=False,
        labelcolor="white",
        fontsize=10,
    )
    ax.set_title("Win Rate", color="white", fontsize=13, pad=12)
    fig.tight_layout()
    return fig


def chart_survivor_histogram(results: List[BattleResult], a_name: str, b_name: str):
    a_surv = [r.a_survivors for r in results]
    b_surv = [r.b_survivors for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(8, 3.5), sharey=False)
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
    n_battles: int = 200,
):
    point_values = list(range(100, 601, 50))
    a_rates, b_rates, draw_rates = [], [], []

    for pts in point_values:
        results = run_simulations(
            lambda p=pts: build_homogeneous_army(a_name, profile_a, p),
            lambda p=pts: build_homogeneous_army(b_name, profile_b, p),
            n_battles,
        )
        aw, bw, d = aggregate(results, a_name, b_name)
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
            "Army A unit",
            list(UNIT_CATALOG.keys()),
            format_func=lambda k: UNIT_CATALOG[k].name,
        )
        profile_a = UNIT_CATALOG[a_unit_key]

        st.subheader("Army B")
        b_name = st.text_input("Army B name", value="Army Bravo")
        b_unit_key = st.selectbox(
            "Army B unit",
            list(UNIT_CATALOG.keys()),
            index=10,
            format_func=lambda k: UNIT_CATALOG[k].name,
        )
        profile_b = UNIT_CATALOG[b_unit_key]

        points = st.slider("Points per army", 100, 600, 300, step=50)

    st.divider()
    n_battles = st.slider("Simulations", 100, 2000, 500, step=100)
    show_points_curve = st.checkbox("Show win% vs points curve", value=True)

    st.divider()
    run = st.button("▶  Run Simulation", use_container_width=True, type="primary")

# ---------------------------------------------------------------------------
# Army stat preview
# ---------------------------------------------------------------------------

army_a_preview = build_homogeneous_army(a_name, profile_a, points)
army_b_preview = build_homogeneous_army(b_name, profile_b, points)

st.title("⚔️ SwegHammer Battle Simulator")

col1, col_vs, col2 = st.columns([5, 1, 5])

with col1:
    st.markdown(f"### 🔵 {a_name}")
    st.markdown(
        f"**Unit:** {profile_a.name}  \n"
        f"**Health:** {profile_a.health}  &nbsp;|&nbsp;  "
        f"**Damage:** {profile_a.damage}  &nbsp;|&nbsp;  "
        f"**Hit%:** {profile_a.hit_probability:.0%}  \n"
        f"**Points/unit:** {profile_a.points_cost:.0f}  &nbsp;|&nbsp;  "
        f"**Unit count:** {len(army_a_preview.units)}"
    )

with col_vs:
    st.markdown("<div style='text-align:center;font-size:2rem;padding-top:1.2rem'>⚡</div>", unsafe_allow_html=True)

with col2:
    st.markdown(f"### 🔴 {b_name}")
    st.markdown(
        f"**Unit:** {profile_b.name}  \n"
        f"**Health:** {profile_b.health}  &nbsp;|&nbsp;  "
        f"**Damage:** {profile_b.damage}  &nbsp;|&nbsp;  "
        f"**Hit%:** {profile_b.hit_probability:.0%}  \n"
        f"**Points/unit:** {profile_b.points_cost:.0f}  &nbsp;|&nbsp;  "
        f"**Unit count:** {len(army_b_preview.units)}"
    )

st.divider()

# ---------------------------------------------------------------------------
# Run and display results
# ---------------------------------------------------------------------------

if run:
    with st.spinner(f"Running {n_battles:,} battles..."):
        results = run_simulations(
            lambda: build_homogeneous_army(a_name, profile_a, points),
            lambda: build_homogeneous_army(b_name, profile_b, points),
            n_battles,
        )

    a_wins, b_wins, draws = aggregate(results, a_name, b_name)

    # --- headline metrics ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"🔵 {a_name} wins", f"{a_wins/n_battles:.1%}", f"{a_wins} battles")
    m2.metric(f"🔴 {b_name} wins", f"{b_wins/n_battles:.1%}", f"{b_wins} battles")
    m3.metric("Draws", f"{draws/n_battles:.1%}", f"{draws} battles")
    avg_rounds = sum(r.rounds for r in results) / n_battles
    m4.metric("Avg rounds", f"{avg_rounds:.1f}")

    st.divider()

    # --- win rate pie + attrition side by side ---
    c_pie, c_attr = st.columns([2, 3])

    with c_pie:
        st.pyplot(chart_win_rates(a_wins, b_wins, draws, a_name, b_name, n_battles))

    with c_attr:
        st.pyplot(chart_attrition(results, a_name, b_name))

    st.divider()

    # --- survivor histograms ---
    st.pyplot(chart_survivor_histogram(results, a_name, b_name))

    # --- win rate vs points curve ---
    if show_points_curve:
        st.divider()
        with st.spinner("Sweeping point budgets for probability curve..."):
            st.pyplot(chart_win_rate_vs_points(profile_a, profile_b, a_name, b_name, n_battles=200))

else:
    st.info("Configure your armies in the sidebar and hit **▶ Run Simulation** to begin.")
    st.markdown(
        """
        **Charts you'll see:**
        - 🥧 **Win rate pie** — overall win/draw/loss breakdown
        - 📉 **Attrition curve** — average units alive per round
        - 📊 **Survivor histogram** — distribution of surviving units
        - 📈 **Win% vs points** — how the matchup shifts as budgets scale
        """
    )
