"""
Equilibrium-points solver — Phase 1.

The premise (see PROJECT.tex / CLAUDE.md): unit value is not a sum of
independent stat utilities. The wound table, AP-vs-save, and FNP combine
non-linearly, so a unit's combat value is a *function over the space of
enemies it faces*. The honest answer to "what should this unit cost?" is
the solution of a symmetric zero-sum game over the catalogue.

This module implements that solver as a Bradley-Terry / log-LSQ fit on the
pairwise time-to-kill matrix:

    T[i,j]  = wounds(j) / D[i,j]              # turns for one i to kill one j
    R[i,j]  = (1/2) * log(T[j,i] / T[i,j])    # log advantage of i over j
    log(p_i) - log(p_j)  ~=  R[i,j]           # fair-trade condition

The 1/2 factor and the T[j,i]/T[i,j] (NOT T[i,j]/T[j,i]) come from the
mutual-destruction derivation: fielding p_j worth of i vs p_j worth of j,
the side that kills first should be the cheaper-per-model unit. Solving
(p_i/p_j)^2 = T[j,i]/T[i,j] gives the formula above.

The exact LSQ solution of a fully-populated skew-symmetric R is the
row-mean closed form:

    log(p_i) = (1/n) * sum_j R[i,j] + scale_const

For partially populated R (some pairs have D = 0), the row-mean over valid
entries is used; this is the LSQ optimum under a missing-at-random
assumption. A "graph-Laplacian" full solve is left as a Phase 2 follow-up
when sparsity bites.

Anchor: one unit is pinned to a known per-model cost (default: Intercessor
Squad at 16 pts/model) to fix the overall scale.

Phase 1 scope
-------------
* Shooting only. Per-attacker-model expected wounds per turn against one
  defender model, accounting for:
    - hit / wound (S vs T table) / save (AP) / invuln / FNP
    - lethal hits, sustained hits, twin-linked, devastating wounds, anti-X
  Distance-conditional keywords (rapid fire, melta, heavy, indirect fire,
  lance, cover, leader auras, detachment buffs) are deferred to later
  phases — see TODO stubs below.
* Pure-melee units (attacks <= 0 or range_inches <= 0) get D[i, *] = 0
  and are dropped from the fit. They'll come back in Phase 2.

Later phases (TODO stubs at bottom of file)
-------------------------------------------
* Phase 2 — Melee damage matrix; combined shooting+melee with role mix.
* Phase 3 — Defensive integration (already captured via wounds in T denominator;
            audit edge cases: high-FNP low-wound, MW-vulnerability).
* Phase 4 — Tactical-utility term: move (non-linear), OC, deep strike,
            scout, infiltrator, sticky-objective. These don't show up in
            D[i,j] but are real points value.
* Phase 5 — Meta-weighting of matchups (weight residuals by P(facing j)
            from tournament data).
* Phase 6 — Solve the actual two-player zero-sum game (mixed strategies)
            to handle rock-paper-scissors mispricing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .units import UNIT_CATALOG, UnitProfile, wound_probability

REPO_ROOT = Path(__file__).resolve().parents[1]
EQUILIBRIUM_PATH = REPO_ROOT / "data" / "equilibrium_points.json"
EQUILIBRIUM_PLOT = REPO_ROOT / "data" / "equilibrium_points.png"

DEFAULT_ANCHOR_KEY = "space_marines_intercessor_squad"
DEFAULT_ANCHOR_PER_MODEL = 16.0   # GW listed: 80 pts / 5 models

# Numerical hygiene: clamp T[i,j] to avoid log-blow-ups when damage is tiny
# but non-zero. Below this fraction-of-a-wound per turn we treat the matchup
# as a no-op and exclude it from the fit.
_MIN_DAMAGE_PER_TURN = 1e-4


# ---------------------------------------------------------------------------
# Analytic shooting damage (one attacker model -> one defender model, per turn)
# ---------------------------------------------------------------------------

def expected_shooting_damage(attacker: UnitProfile, defender: UnitProfile) -> float:
    """
    Expected unsaved damage one attacker model inflicts on one defender model
    in a single shooting phase. Stateless: ignores distance, cover, charging,
    detachment buffs, and leader auras (those are later-phase concerns).

    Returns 0.0 for pure-melee units (attacks <= 0 or range == 0).
    """
    if attacker.attacks <= 0 or attacker.range_inches <= 0:
        return 0.0

    n_attacks = float(attacker.attacks)
    p_hit = float(attacker.hit_probability)
    if p_hit <= 0:
        return 0.0

    # ---- Hit phase: split into normal hits and crit hits (always 6+) ----
    p_crit_hit = 1.0 / 6.0
    p_normal_hit = max(0.0, p_hit - p_crit_hit)
    sustained = int(attacker.sustained_hits)

    # ---- Wound roll per surviving roll-to-wound input ----
    p_wound_base = wound_probability(attacker.strength, defender.toughness)
    if attacker.twin_linked:
        # Re-roll failed wounds = 1 - (1-p)^2 = 2p - p^2
        p_wound = p_wound_base + (1.0 - p_wound_base) * p_wound_base
    else:
        p_wound = p_wound_base

    # ---- Anti-X: lower the crit-wound threshold against matching keywords ----
    anti_crit_threshold = 6
    if attacker.anti_keywords and defender.unit_keywords:
        defender_kw = set(defender.unit_keywords)
        for kw, thresh in attacker.anti_keywords:
            if kw in defender_kw and thresh < anti_crit_threshold:
                anti_crit_threshold = thresh
    p_crit_wound = max(0.0, (7 - anti_crit_threshold) / 6.0)

    # ---- Compose wound rolls per shot ----
    # Lethal Hits: crit-to-hit auto-wounds (skips wound roll). Sustained extras
    # from the crit STILL roll to wound — they are "normal hits", not crits.
    if attacker.lethal_hits:
        auto_wounds_per_shot = p_crit_hit
        wound_rolls_per_shot = p_normal_hit + p_crit_hit * sustained
    else:
        auto_wounds_per_shot = 0.0
        wound_rolls_per_shot = p_normal_hit + p_crit_hit * (1 + sustained)

    # ---- Devastating Wounds: a fraction of wound rolls become mortals ----
    # Crit-wound rate is fixed at p_crit_wound regardless of TL (TL doesn't
    # re-roll a successful roll, so the natural-6 rate is unchanged).
    if attacker.devastating_wounds:
        mortals_per_roll = min(p_crit_wound, p_wound)
        save_wounds_per_roll = max(0.0, p_wound - mortals_per_roll)
    else:
        mortals_per_roll = 0.0
        save_wounds_per_roll = p_wound

    mortals_per_shot = wound_rolls_per_shot * mortals_per_roll
    save_wounds_per_shot = (
        wound_rolls_per_shot * save_wounds_per_roll + auto_wounds_per_shot
    )

    # ---- Save phase (mortals bypass saves) ----
    save_after_ap = defender.save - attacker.ap
    invuln = defender.invuln_save
    effective_save = (
        min(save_after_ap, invuln) if invuln <= 6 else save_after_ap
    )
    if effective_save > 6:
        p_save_succeeds = 0.0
    elif effective_save <= 2:
        p_save_succeeds = 5.0 / 6.0   # 2+ is the floor in 10e
    else:
        p_save_succeeds = (7 - effective_save) / 6.0
    p_save_fails = 1.0 - p_save_succeeds

    unsaved_wounds_per_shot = (
        mortals_per_shot + save_wounds_per_shot * p_save_fails
    )

    # ---- Per-shot damage ----
    if attacker.weapon_damage_per_shot > 0:
        dmg_per_shot = attacker.weapon_damage_per_shot
    else:
        dmg_per_shot = attacker.damage / max(1, attacker.attacks)

    # ---- FNP: applied per point of damage post-save ----
    if defender.fnp <= 6:
        fnp_multiplier = 1.0 - (7 - defender.fnp) / 6.0
    else:
        fnp_multiplier = 1.0

    return n_attacks * unsaved_wounds_per_shot * dmg_per_shot * fnp_multiplier


# ---------------------------------------------------------------------------
# Matrix builders
# ---------------------------------------------------------------------------

def pairwise_damage_matrix(units: List[UnitProfile]) -> np.ndarray:
    """D[i, j] = expected_shooting_damage(units[i], units[j]) (per attacker model, per turn)."""
    n = len(units)
    D = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            D[i, j] = expected_shooting_damage(units[i], units[j])
    return D


def time_to_kill_matrix(D: np.ndarray, units: List[UnitProfile]) -> np.ndarray:
    """T[i, j] = wounds(units[j]) / D[i, j]. Inf where D == 0."""
    n = len(units)
    wounds = np.array([max(1e-6, u.health) for u in units], dtype=float)
    T = np.full_like(D, np.inf)
    with np.errstate(divide="ignore", invalid="ignore"):
        mask = D > _MIN_DAMAGE_PER_TURN
        T[mask] = wounds[np.newaxis, :].repeat(n, axis=0)[mask] / D[mask]
    return T


# ---------------------------------------------------------------------------
# Equilibrium solve (closed-form log-LSQ via row-mean)
# ---------------------------------------------------------------------------

def solve_log_points(
    T: np.ndarray, anchor_idx: int, anchor_log_p: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Closed-form log-LSQ on T:

        x_i = mean over valid j of [log(T[i,j]) - log(T[j,i])]

    A pair (i, j) is *valid* iff both T[i,j] and T[j,i] are finite — i.e.
    both directions of the matchup do non-trivial damage. Units with no
    valid partners get x = anchor_log_p (no information; fall back to anchor).

    Returns (x, valid_counts):
        x[i]            — log equilibrium points per model
        valid_counts[i] — number of matchups that fed into x[i]
    """
    n = T.shape[0]
    finite_T = np.isfinite(T)
    log_T = np.zeros_like(T)
    log_T[finite_T] = np.log(T[finite_T])
    finite_mask = finite_T & finite_T.T
    np.fill_diagonal(finite_mask, False)

    # R[i, j] = (1/2) * log(T[j, i] / T[i, j]). Skew-symmetric on the valid set.
    # Positive R[i, j] means i is better than j (kills j faster than j kills i),
    # so i should cost MORE than j. The 1/2 factor comes from the
    # (p_i/p_j)^2 = T[j,i]/T[i,j] equilibrium condition derived in the docstring.
    R = np.where(finite_mask, 0.5 * (log_T.T - log_T), 0.0)
    counts = finite_mask.sum(axis=1)
    safe_counts = np.where(counts == 0, 1, counts)
    x_raw = R.sum(axis=1) / safe_counts

    # Shift so x[anchor] == anchor_log_p
    shift = anchor_log_p - x_raw[anchor_idx]
    x = x_raw + shift
    # Units with no valid partners: pin to anchor (no information).
    x[counts == 0] = anchor_log_p
    return x, counts


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------

@dataclass
class EquilibriumEntry:
    key: str
    name: str
    faction: str
    gw_points_per_squad: float
    gw_points_per_model: float
    min_models: int
    equilibrium_points_per_model: float
    equilibrium_points_per_squad: float
    mispricing_pct: float            # +ve = GW overcosted, -ve = GW undercosted
    valid_matchups: int
    role: str                         # "shooty" / "melee_only" / "dual" — coarse


@dataclass
class EquilibriumResult:
    """Phase 1 output bundle. Includes both per-unit entries AND the raw
    matrices that produced them, so the Streamlit UI can drill into the
    pairwise structure (best/worst matchups for a chosen unit)."""
    entries: List[EquilibriumEntry]
    keys: List[str]                  # row/col ordering for the matrices
    D: np.ndarray                    # shape (n, n) — damage per turn per model
    T: np.ndarray                    # shape (n, n) — time-to-kill, inf where D too small
    R: np.ndarray                    # shape (n, n) — log advantage of i over j
    log_p: np.ndarray                # shape (n,)   — log equilibrium pts/model
    anchor_key: str
    anchor_per_model: float

    def index_of(self, key: str) -> int:
        return self.keys.index(key)

    def matchups_for(self, key: str, top_n: int = 10):
        """Best and worst matchups for `key`. Returns (best, worst) where each
        is a list of dicts with the opponent's stats and the matchup details,
        sorted by R[i, j] (descending for best, ascending for worst)."""
        i = self.index_of(key)
        finite = np.isfinite(self.T[i]) & np.isfinite(self.T[:, i])
        finite[i] = False
        idx = np.where(finite)[0]
        if len(idx) == 0:
            return [], []
        ranked = sorted(idx, key=lambda j: float(self.R[i, j]), reverse=True)
        def _pack(j: int):
            return {
                "opponent_key": self.keys[j],
                "T_self_kills_opp": round(float(self.T[i, j]), 3),
                "T_opp_kills_self": round(float(self.T[j, i]), 3),
                "R_log_advantage": round(float(self.R[i, j]), 3),
                "fair_points_ratio": round(float(np.exp(self.R[i, j])), 3),
            }
        best = [_pack(j) for j in ranked[:top_n]]
        worst = [_pack(j) for j in ranked[-top_n:][::-1]]
        return best, worst


def _classify_role(u: UnitProfile) -> str:
    has_shoot = u.attacks > 0 and u.range_inches > 0
    has_melee = u.melee_attacks > 0
    if has_shoot and has_melee:
        return "dual"
    if has_shoot:
        return "shooty"
    if has_melee:
        return "melee_only"
    return "noncombat"


def compute_phase1(
    catalog: Optional[Dict[str, UnitProfile]] = None,
    anchor_key: str = DEFAULT_ANCHOR_KEY,
    anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL,
    faction: Optional[str] = None,
    limit: Optional[int] = None,
) -> EquilibriumResult:
    """
    Run the Phase 1 equilibrium solve. Returns an EquilibriumResult with one
    entry per fittable unit AND the underlying D/T/R matrices (so the UI can
    drill into pairwise matchups). Pure-melee and noncombat units are
    excluded — they show up in later phases.

    Filtering:
      * `faction=...` restricts the catalogue (useful for fast iteration).
      * `limit=N` truncates the catalogue (debugging only — affects the fit).
    """
    if catalog is None:
        catalog = UNIT_CATALOG

    items: List[Tuple[str, UnitProfile]] = sorted(catalog.items())
    if faction:
        items = [(k, u) for k, u in items if u.faction == faction]
    if limit:
        items = items[:limit]

    # Filter to units that have a shooting profile (Phase 1 limitation).
    fittable = [(k, u) for k, u in items if _classify_role(u) in ("shooty", "dual")]
    if anchor_key not in {k for k, _ in fittable}:
        raise ValueError(
            f"Anchor unit {anchor_key!r} is not in the fittable subset "
            f"(faction={faction!r}, limit={limit!r}). Pick an anchor with a shooting profile."
        )

    keys = [k for k, _ in fittable]
    units = [u for _, u in fittable]
    anchor_idx = keys.index(anchor_key)
    anchor_log_p = math.log(anchor_per_model)

    D = pairwise_damage_matrix(units)
    T = time_to_kill_matrix(D, units)
    x, counts = solve_log_points(T, anchor_idx, anchor_log_p)
    eq_per_model = np.exp(x)

    # Rebuild the R matrix that the solver computed internally, so the UI
    # can show pairwise advantage values. R[i, j] = (1/2) log(T[j,i]/T[i,j]).
    finite_T = np.isfinite(T)
    log_T = np.zeros_like(T)
    log_T[finite_T] = np.log(T[finite_T])
    finite_mask = finite_T & finite_T.T
    np.fill_diagonal(finite_mask, False)
    R = np.where(finite_mask, 0.5 * (log_T.T - log_T), np.nan)

    entries: List[EquilibriumEntry] = []
    for key, u, eq_pm, vc in zip(keys, units, eq_per_model, counts):
        gw_per_squad = float(u.points_per_squad)
        gw_per_model = (
            gw_per_squad / max(1, u.min_models) if gw_per_squad > 0 else 0.0
        )
        eq_per_squad = eq_pm * max(1, u.min_models)
        if gw_per_model > 0:
            mispricing = (gw_per_model - eq_pm) / eq_pm * 100.0
        else:
            mispricing = 0.0
        entries.append(
            EquilibriumEntry(
                key=key,
                name=u.name,
                faction=u.faction,
                gw_points_per_squad=round(gw_per_squad, 2),
                gw_points_per_model=round(gw_per_model, 2),
                min_models=int(u.min_models),
                equilibrium_points_per_model=round(float(eq_pm), 2),
                equilibrium_points_per_squad=round(float(eq_per_squad), 2),
                mispricing_pct=round(float(mispricing), 1),
                valid_matchups=int(vc),
                role=_classify_role(u),
            )
        )
    return EquilibriumResult(
        entries=entries, keys=keys, D=D, T=T, R=R, log_p=x,
        anchor_key=anchor_key, anchor_per_model=anchor_per_model,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def write_json(entries: List[EquilibriumEntry], path: Path = EQUILIBRIUM_PATH,
               anchor_key: str = DEFAULT_ANCHOR_KEY,
               anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL) -> None:
    payload = {
        "_comment": (
            "Phase 1 equilibrium-points solver output. log-LSQ on pairwise "
            "shooting-only time-to-kill. Pure-melee units excluded. See "
            "code/equilibrium.py for full method and TODO list of later phases."
        ),
        "phase": 1,
        "method": "log-LSQ on pairwise shooting time-to-kill (row-mean closed form)",
        "anchor": {
            "key": anchor_key,
            "per_model_points": anchor_per_model,
        },
        "units": {e.key: asdict(e) for e in entries},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def plot_scatter(entries: List[EquilibriumEntry], path: Path = EQUILIBRIUM_PLOT) -> None:
    """
    GW points-per-model (x) vs equilibrium points-per-model (y), log-log scatter.

    Diagonal y=x is fair. Points above diagonal = GW overcosted (equilibrium
    says it should cost less). Below diagonal = GW undercosted.
    """
    import matplotlib.pyplot as plt

    pts: List[Tuple[float, float, str, str]] = []
    for e in entries:
        if e.gw_points_per_model > 0 and e.equilibrium_points_per_model > 0:
            pts.append((e.gw_points_per_model, e.equilibrium_points_per_model,
                        e.faction, e.name))
    if not pts:
        return

    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    factions = [p[2] for p in pts]

    fig, ax = plt.subplots(figsize=(11, 8))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#1a1d23")

    # Faction colours: deterministic from a fixed palette
    unique_factions = sorted(set(factions))
    cmap = plt.get_cmap("tab20")
    colour = {f: cmap(i % 20) for i, f in enumerate(unique_factions)}
    cols = [colour[f] for f in factions]

    ax.scatter(xs, ys, c=cols, s=22, alpha=0.75, linewidths=0.3, edgecolors="white")

    lo = float(min(xs.min(), ys.min()))
    hi = float(max(xs.max(), ys.max()))
    ax.plot([lo, hi], [lo, hi], color="#FFD700", linestyle="--",
            linewidth=1.0, label="y = x (fair)")

    # Label the 8 most over- and 8 most undercosted units
    log_ratio = np.log(ys / xs)
    worst_over = np.argsort(log_ratio)[-8:]   # ys >> xs → equilibrium higher than GW → undercosted by GW
    worst_under = np.argsort(log_ratio)[:8]   # ys << xs → equilibrium lower than GW → overcosted by GW
    for idx in list(worst_over) + list(worst_under):
        ax.annotate(
            pts[idx][3],
            (xs[idx], ys[idx]),
            fontsize=6, color="white", alpha=0.9,
            xytext=(4, 3), textcoords="offset points",
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("GW points per model  (log)", color="white")
    ax.set_ylabel("Equilibrium points per model  (log)", color="white")
    ax.set_title(
        "Phase 1: GW vs equilibrium points (shooting-only)\n"
        "Above diagonal = GW undercosted   |   below = GW overcosted",
        color="white",
    )
    ax.tick_params(colors="white", which="both")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.grid(True, alpha=0.15, color="#888", linestyle=":")
    ax.legend(facecolor="#1a1d23", edgecolor="#444", labelcolor="white")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------------------
# TODO — later phases
# ---------------------------------------------------------------------------
#
# Phase 2: melee damage matrix
#   def expected_melee_damage(attacker, defender) -> float: ...
#   def pairwise_combat_matrix(units, shoot_weight: float) -> np.ndarray:
#       D_shoot = pairwise_damage_matrix(units)
#       D_melee = pairwise_melee_matrix(units)
#       return shoot_weight * D_shoot + (1 - shoot_weight) * D_melee
#   Open question: how to set `shoot_weight` per attacker — naive 0.5 for
#   dual, 1.0 for shooty, 0.0 for melee-only? Or learn it from sim data?
#
# Phase 3: defensive audit
#   Edge cases where T denominator overstates durability — e.g., a unit
#   with FNP 5+ and 1 wound should be ~50% more durable, but our T already
#   captures that via the multiplicative fnp_multiplier inside D. Verify
#   with a spot-check on Death Guard Plague Marines vs. baseline Marines.
#
# Phase 4: tactical-utility term
#   Add a per-unit `tactical_value(u)` that contributes a phantom DPS-like
#   number to the row-sum, parameterised by:
#     - move (non-linear: log(m / 6) clamped)
#     - oc (linear)
#     - deep_strike (fixed bonus, faction-conditional?)
#     - scout_distance (small linear)
#     - infiltrator (fixed bonus)
#     - sticky_objective (fixed bonus)
#     - range_inches (log; long range = positioning advantage)
#   Calibrate the weights by minimising residual mispricing on a held-out
#   set of "known fair" units (the ones tournament data says GW priced
#   correctly).
#
# Phase 5: meta-weighting
#   Weight pair (i, j) by P(facing j) from tournament data. Need a meta
#   distribution source — Goonhammer top-table data, BCP, or our own
#   tournament_results.json once it has enough samples.
#
# Phase 6: actual Nash equilibrium
#   Solve the symmetric zero-sum game:
#     - Payoff M[i, j] = (T[j,i] - T[i,j]) / (T[i,j] + T[j,i])   # trade ratio
#     - Find mixed strategies sigma, tau on simplex maximising min-payoff
#   Use the LP formulation (scipy.optimize.linprog) — needs scipy installed.
#   The "fair points" are then derived from the dual variables.


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 1 equilibrium-points solver (shooting only)."
    )
    parser.add_argument("--faction", type=str, default=None,
                        help="Restrict to a single faction (e.g. 'Necrons')")
    parser.add_argument("--limit", type=int, default=None,
                        help="Truncate the catalogue (debugging only)")
    parser.add_argument("--anchor", type=str, default=DEFAULT_ANCHOR_KEY)
    parser.add_argument("--anchor-points", type=float, default=DEFAULT_ANCHOR_PER_MODEL)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--out", type=Path, default=EQUILIBRIUM_PATH)
    parser.add_argument("--plot-out", type=Path, default=EQUILIBRIUM_PLOT)
    args = parser.parse_args()

    result = compute_phase1(
        anchor_key=args.anchor,
        anchor_per_model=args.anchor_points,
        faction=args.faction,
        limit=args.limit,
    )
    entries = result.entries
    write_json(entries, args.out, anchor_key=args.anchor, anchor_per_model=args.anchor_points)
    if not args.no_plot:
        plot_scatter(entries, args.plot_out)

    # Print top mispricings
    sorted_entries = sorted(entries, key=lambda e: e.mispricing_pct)
    print(f"\n{len(entries)} units fitted. Anchor: {args.anchor} @ {args.anchor_points} pts/model.")
    print("\nMost UNDERCOSTED by GW (equilibrium says should cost more):")
    for e in sorted_entries[:10]:
        print(f"  {e.mispricing_pct:+6.1f}%   "
              f"GW {e.gw_points_per_model:>5.1f} vs eq {e.equilibrium_points_per_model:>5.1f}   "
              f"{e.name[:50]} ({e.faction[:20]})")
    print("\nMost OVERCOSTED by GW (equilibrium says should cost less):")
    for e in sorted_entries[-10:][::-1]:
        print(f"  {e.mispricing_pct:+6.1f}%   "
              f"GW {e.gw_points_per_model:>5.1f} vs eq {e.equilibrium_points_per_model:>5.1f}   "
              f"{e.name[:50]} ({e.faction[:20]})")
    print(f"\nWrote {args.out}")
    if not args.no_plot:
        print(f"Wrote {args.plot_out}")
