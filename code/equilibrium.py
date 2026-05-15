"""
Equilibrium-points solver — Phase 1 (shooting) and Phase 2 (shoot+melee).

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

Phase 2 scope
-------------
* Shooting + melee. `expected_melee_damage` mirrors the shooting routine on
  the melee stat block (S/AP/attacks/hit_prob from `melee_*` fields), and
  `pairwise_combat_matrix` blends the two matrices per-attacker via a
  shoot_weight that defaults to a coarse role lookup
  (SHOOTY=0.90, HEAVY=0.80, DUAL=0.55, HORDE=0.50, MELEE=0.20, SUPPORT=0.50).
  Pure-melee units rejoin the fit; only noncombat profiles are still excluded.

Later phases (TODO stubs at bottom of file)
-------------------------------------------
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
EQUILIBRIUM_PHASE2_PATH = REPO_ROOT / "data" / "equilibrium_points_phase2.json"
EQUILIBRIUM_PHASE2_PLOT = REPO_ROOT / "data" / "equilibrium_points_phase2.png"
EQUILIBRIUM_PHASE4_PATH = REPO_ROOT / "data" / "equilibrium_points_phase4.json"
EQUILIBRIUM_PHASE4_PLOT = REPO_ROOT / "data" / "equilibrium_points_phase4.png"
EQUILIBRIUM_PHASE5_PATH = REPO_ROOT / "data" / "equilibrium_points_phase5.json"
EQUILIBRIUM_PHASE5_PLOT = REPO_ROOT / "data" / "equilibrium_points_phase5.png"
EQUILIBRIUM_PHASE6_PATH = REPO_ROOT / "data" / "equilibrium_points_phase6.json"
EQUILIBRIUM_PHASE6_PLOT = REPO_ROOT / "data" / "equilibrium_points_phase6.png"

DEFAULT_ANCHOR_KEY = "space_marines_intercessor_squad"
DEFAULT_ANCHOR_PER_MODEL = 16.0   # GW listed: 80 pts / 5 models

# Phase 2 — default shoot/melee mixing weights per coarse role from code.roles.
# Per-attacker fraction of pairwise damage that comes from the shooting matrix;
# the complement (1 - w) is melee. Tuned by hand for Phase 2; later phases may
# learn this from sim data. Keys are the labels returned by code.roles.classify.
DEFAULT_SHOOT_WEIGHT_BY_ROLE: Dict[str, float] = {
    "SHOOTY":  0.90,
    "HEAVY":   0.80,
    "DUAL":    0.55,
    "HORDE":   0.50,
    "MELEE":   0.20,
    "SUPPORT": 0.50,
}

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
# Analytic melee damage (one attacker model -> one defender model, per turn)
# ---------------------------------------------------------------------------

def expected_melee_damage(attacker: UnitProfile, defender: UnitProfile) -> float:
    """
    Expected unsaved damage one attacker model inflicts on one defender model
    in a single fight-phase melee swing. Mirrors `expected_shooting_damage`
    structurally but routes through the melee stat block:

      melee_attacks x melee_hit_probability x wound(melee_strength, T)
        x (1 - max(save_after_melee_AP, invuln)) x melee_damage_per_shot
        x fnp_multiplier

    Lethal Hits / Sustained Hits / Twin-Linked / Devastating Wounds /
    Anti-X are honoured symmetrically — they're carried at the unit level
    in our model, so the melee branch enjoys (or suffers) the same.

    Cover is ignored (melee always ignores cover). Charging Lance,
    leader auras, fight-first, and stratagems are deferred to later phases.

    Returns 0.0 for units with no usable melee profile.
    """
    if attacker.melee_attacks <= 0 or attacker.melee_hit_probability <= 0:
        return 0.0

    n_attacks = float(attacker.melee_attacks)
    p_hit = float(attacker.melee_hit_probability)
    if p_hit <= 0:
        return 0.0

    # ---- Hit phase: split into normal hits and crit hits (always 6+) ----
    p_crit_hit = 1.0 / 6.0
    p_normal_hit = max(0.0, p_hit - p_crit_hit)
    sustained = int(attacker.sustained_hits)

    # ---- Wound roll per surviving roll-to-wound input ----
    p_wound_base = wound_probability(attacker.melee_strength, defender.toughness)
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

    # ---- Compose wound rolls per swing ----
    if attacker.lethal_hits:
        auto_wounds_per_shot = p_crit_hit
        wound_rolls_per_shot = p_normal_hit + p_crit_hit * sustained
    else:
        auto_wounds_per_shot = 0.0
        wound_rolls_per_shot = p_normal_hit + p_crit_hit * (1 + sustained)

    # ---- Devastating Wounds: a fraction of wound rolls become mortals ----
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
    # Melee uses melee_ap; no cover bonus (melee ignores cover).
    save_after_ap = defender.save - attacker.melee_ap
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

    # ---- Per-swing damage ----
    dmg_per_shot = attacker.melee_damage_per_shot or 1.0

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


def pairwise_melee_matrix(units: List[UnitProfile]) -> np.ndarray:
    """D[i, j] = expected_melee_damage(units[i], units[j]) (per attacker model, per turn)."""
    n = len(units)
    D = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            D[i, j] = expected_melee_damage(units[i], units[j])
    return D


def _default_shoot_weight(unit: UnitProfile) -> float:
    """Per-attacker shoot weight from coarse role classification."""
    from .roles import classify
    role = classify(unit)
    return DEFAULT_SHOOT_WEIGHT_BY_ROLE.get(role, 0.5)


def pairwise_combat_matrix(
    units: List[UnitProfile],
    shoot_weight=None,
) -> np.ndarray:
    """
    Combined shooting + melee damage matrix:

        D[i, j] = w(i) * D_shoot[i, j] + (1 - w(i)) * D_melee[i, j]

    The shoot/melee mix is per-attacker — a melee specialist doesn't suddenly
    contribute shooting just because the matrix asks. `shoot_weight` may be:

      * None        -> default per-role mix via `_default_shoot_weight`
      * float       -> the same constant for every attacker
      * callable    -> called as shoot_weight(unit_profile), must return [0, 1]
      * sequence    -> indexed by row position; entry i applies to attacker i

    Returns an (n, n) array of expected damage per attacker model per turn.
    """
    n = len(units)
    D_shoot = pairwise_damage_matrix(units)
    D_melee = pairwise_melee_matrix(units)

    if shoot_weight is None:
        weights = np.array([_default_shoot_weight(u) for u in units], dtype=float)
    elif callable(shoot_weight):
        weights = np.array([float(shoot_weight(u)) for u in units], dtype=float)
    elif isinstance(shoot_weight, (int, float)):
        weights = np.full(n, float(shoot_weight), dtype=float)
    else:
        weights = np.asarray(shoot_weight, dtype=float)
        if weights.shape != (n,):
            raise ValueError(
                f"shoot_weight sequence must be length {n}, got {weights.shape}"
            )
    weights = np.clip(weights, 0.0, 1.0)

    # Broadcast weights across columns: attacker (row) decides the mix.
    w = weights[:, np.newaxis]
    return w * D_shoot + (1.0 - w) * D_melee


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
    """Phase 1 / Phase 2 output bundle. Includes both per-unit entries AND
    the raw matrices that produced them, so the Streamlit UI can drill into
    the pairwise structure (best/worst matchups for a chosen unit).

    The `phase` field marks which solver produced this result: 1 = shooting
    only, 2 = combined shoot+melee with per-attacker role-weighted mix.
    """
    entries: List[EquilibriumEntry]
    keys: List[str]                  # row/col ordering for the matrices
    D: np.ndarray                    # shape (n, n) — damage per turn per model
    T: np.ndarray                    # shape (n, n) — time-to-kill, inf where D too small
    R: np.ndarray                    # shape (n, n) — log advantage of i over j
    log_p: np.ndarray                # shape (n,)   — log equilibrium pts/model
    anchor_key: str
    anchor_per_model: float
    phase: int = 1

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
        phase=1,
    )


def compute_phase2(
    catalog: Optional[Dict[str, UnitProfile]] = None,
    anchor_key: str = DEFAULT_ANCHOR_KEY,
    anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL,
    faction: Optional[str] = None,
    limit: Optional[int] = None,
    shoot_weight=None,
) -> EquilibriumResult:
    """
    Phase 2 — combined shoot+melee equilibrium solve.

    Same shape as `compute_phase1`, but the pairwise damage matrix is
    `pairwise_combat_matrix` (a per-attacker-role weighted blend of the
    shooting and melee matrices). Pure-melee units now contribute non-zero
    damage and re-enter the fit. `shoot_weight=None` uses the
    `DEFAULT_SHOOT_WEIGHT_BY_ROLE` table; pass a float / callable / sequence
    to override (see `pairwise_combat_matrix`).

    Noncombat units (no ranged AND no melee profile) are still excluded —
    they get costed in the Phase 4 tactical-utility pass.
    """
    if catalog is None:
        catalog = UNIT_CATALOG

    items: List[Tuple[str, UnitProfile]] = sorted(catalog.items())
    if faction:
        items = [(k, u) for k, u in items if u.faction == faction]
    if limit:
        items = items[:limit]

    # Phase 2: include shooty / dual / melee_only. Noncombat still excluded.
    fittable = [
        (k, u) for k, u in items
        if _classify_role(u) in ("shooty", "dual", "melee_only")
    ]
    if anchor_key not in {k for k, _ in fittable}:
        raise ValueError(
            f"Anchor unit {anchor_key!r} is not in the fittable subset "
            f"(faction={faction!r}, limit={limit!r}). Pick an anchor with a "
            f"shooting or melee profile."
        )

    keys = [k for k, _ in fittable]
    units = [u for _, u in fittable]
    anchor_idx = keys.index(anchor_key)
    anchor_log_p = math.log(anchor_per_model)

    D = pairwise_combat_matrix(units, shoot_weight=shoot_weight)
    T = time_to_kill_matrix(D, units)
    x, counts = solve_log_points(T, anchor_idx, anchor_log_p)
    eq_per_model = np.exp(x)

    # Rebuild R for UI introspection. Same formula as Phase 1.
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
        phase=2,
    )


# ---------------------------------------------------------------------------
# Phase 3 — Defensive audit (pure analysis; no rule changes)
# ---------------------------------------------------------------------------
#
# The defensive math (save_after_ap, invuln, fnp_multiplier) already enters the
# pricing via `expected_*_damage` -> D[i,j] -> T[i,j] = wounds(j) / D[i,j].
# Phase 3 is an audit pass: surface the edge-case unit classes where defence
# does the heaviest lifting, sanity-check that they're being captured, and
# detect units the anchor simply can't damage (so future phases know which
# matchups need a fallback).
#
# This module is read-only over an EquilibriumResult; it generates no new
# SIMULATOR_RULE_KEYS / detachment / leader entries.

# Edge-case thresholds for the four audit classes. Tuned to match the
# wording in the task brief and the in-code comments — adjust if the
# definition of "elite" / "cliff" shifts.
_PHASE3_FNP_THRESHOLD = 5      # FNP <= 5+ (i.e. fnp in {2..5}) counts as "high"
_PHASE3_LOW_WOUND_MAX = 2      # health <= 2 is "low wound" for the FNP class
_PHASE3_DURABILITY_UPLIFT_FLOOR = 1.5 - 1e-9   # flag when FNP makes you >=50%
                                                # more durable. The 1e-9 epsilon
                                                # admits FNP 5+ at its exact
                                                # 1.5x boundary (the float
                                                # 1/(4/6) = 1.4999...e0).
_PHASE3_INVULN_CEIL = 4        # invuln <= 4+ is "good"
_PHASE3_INVULN_GAP_MIN = 2     # |save - invuln| >= 2 is a real "cliff" —
                               # captures both directions: a Ministorum
                               # Priest (Sv 6+ / Inv 4+, gap +2) AND a
                               # Custodian Guard (Sv 2+ / Inv 4+, gap -2,
                               # |gap|=2). The Custodes "cliff" only shows
                               # up vs high AP that strips the armour past
                               # the invuln, but at the unit-classification
                               # layer we flag both directions and let the
                               # damage routine's min(save, invuln) handle
                               # the AP-conditional pricing.
_PHASE3_ELITE_WOUND_MIN = 3    # health >= 3 is "multi-wound"
_PHASE3_ELITE_SAVE_MAX = 3     # save <= 3+ is "elite armour"
_PHASE3_NEAR_ZERO_DAMAGE = 0.05  # D < this/turn = anchor can't price this unit


@dataclass
class Phase3Audit:
    """Defensive-audit findings over an EquilibriumResult.

    All collections are sorted for deterministic output; spot_checks preserves
    insertion order so the brief's named pairings stay readable.

    Fields:
      high_fnp_units      — (unit_key, durability_uplift_vs_save_only) for
                            units with FNP <= 5+ AND health <= 2 whose FNP
                            multiplies effective survivability by >1.5x.
      invuln_cliff_units  — (unit_key, save, invuln) where invuln <= 4+ AND
                            |save - invuln| >= 2 — defensive math is doing
                            real work in either direction (a strong invuln
                            that dominates a poor save, or an invuln floor
                            that backstops a great save when armour is stripped).
      multiwound_elite_units — keys with health >= 3 AND save <= 3+ (heavy
                            infantry: linear T scaling with wound count).
      spot_checks         — list of dicts: {attacker_key, defender_key, T_value,
                            expected_vs_naive_ratio, ...} for the brief's
                            named anchor-vs-X comparisons.
      unpriceable_vs_anchor — keys where anchor cannot deal meaningful
                            (<0.05/turn) damage; these can't be priced via
                            the anchor's row alone and need fallback treatment.
      anchor_key          — the EquilibriumResult anchor reused for spot checks.
    """
    high_fnp_units: List[Tuple[str, float]]
    invuln_cliff_units: List[Tuple[str, int, int]]
    multiwound_elite_units: List[str]
    spot_checks: List[dict]
    unpriceable_vs_anchor: List[str]
    anchor_key: str


def _fnp_multiplier(fnp: int) -> float:
    """Same FNP curve `expected_*_damage` uses. 7 = no FNP -> 1.0 (full damage)."""
    if fnp <= 6:
        return 1.0 - (7 - fnp) / 6.0
    return 1.0


def _save_fail_prob(save: int, ap: int = 0, invuln: int = 7) -> float:
    """Probability a save FAILS — mirrors the in-damage save block.

    Uses min(save_after_ap, invuln) when invuln <= 6, else just save_after_ap.
    2+ is the floor in 10e (a natural 1 always fails -> 5/6 succeed).
    """
    save_after_ap = save - ap
    effective = min(save_after_ap, invuln) if invuln <= 6 else save_after_ap
    if effective > 6:
        return 1.0
    if effective <= 2:
        return 1.0 - 5.0 / 6.0
    return 1.0 - (7 - effective) / 6.0


def _spot_check(
    result: EquilibriumResult,
    attacker_key: str,
    defender_key: str,
    catalog: Optional[Dict[str, UnitProfile]] = None,
) -> Optional[dict]:
    """Return T[i,j] and a defence-amplification ratio for a labelled matchup.

    `expected_vs_naive_ratio` is T_with_defence / T_naive, where T_naive is
    what the time-to-kill would be against a stripped defender (save=7, no
    invuln, no FNP). Ratio > 1 means defensive stats are extending survival;
    ratio == 1 means the defender's stats don't matter for this matchup.
    """
    if attacker_key not in result.keys or defender_key not in result.keys:
        return None
    i = result.index_of(attacker_key)
    j = result.index_of(defender_key)
    if not np.isfinite(result.T[i, j]):
        # Anchor can't damage defender at all — record the matchup as
        # unpriceable rather than fabricating a finite ratio.
        return {
            "attacker_key": attacker_key,
            "defender_key": defender_key,
            "T_value": float("inf"),
            "expected_vs_naive_ratio": float("inf"),
            "note": "anchor cannot damage defender (T = inf)",
        }
    # Naive baseline: rebuild D with a stripped defender clone.
    from dataclasses import replace
    units_by_key = {
        k: u for k, u in zip(result.keys, _units_from_result(result, catalog=catalog))
    }
    naive_defender = replace(
        units_by_key[defender_key], save=7, invuln_save=7, fnp=7,
    )
    naive_attacker = units_by_key[attacker_key]
    # Use the same combined / shooting damage routine the result phase used.
    if result.phase == 2:
        from .roles import classify
        w = DEFAULT_SHOOT_WEIGHT_BY_ROLE.get(classify(naive_attacker), 0.5)
        D_naive = (
            w * expected_shooting_damage(naive_attacker, naive_defender)
            + (1.0 - w) * expected_melee_damage(naive_attacker, naive_defender)
        )
    else:
        D_naive = expected_shooting_damage(naive_attacker, naive_defender)
    if D_naive <= _MIN_DAMAGE_PER_TURN:
        ratio = float("inf")
    else:
        T_naive = naive_defender.health / D_naive
        ratio = float(result.T[i, j]) / T_naive
    return {
        "attacker_key": attacker_key,
        "defender_key": defender_key,
        "T_value": round(float(result.T[i, j]), 3),
        "expected_vs_naive_ratio": round(float(ratio), 3),
    }


def _units_from_result(
    result: EquilibriumResult,
    catalog: Optional[Dict[str, UnitProfile]] = None,
) -> List[UnitProfile]:
    """Look up UnitProfile objects in the same order as result.keys.

    `catalog` lets tests inject a synthetic dict; defaults to UNIT_CATALOG.
    """
    src = catalog if catalog is not None else UNIT_CATALOG
    return [src[k] for k in result.keys]


def _closest_key_by_substring(keys: List[str], substring: str) -> Optional[str]:
    """Find the first key in `keys` that contains `substring` (case-insensitive).

    Used by the spot-check pipeline when the brief's canonical key isn't in
    the current catalogue build — we fall back to the closest match by name
    and the caller logs the substitution.
    """
    needle = substring.lower()
    matches = [k for k in keys if needle in k.lower()]
    return matches[0] if matches else None


def compute_phase3_audit(
    result: EquilibriumResult,
    catalog: Optional[Dict[str, UnitProfile]] = None,
) -> Phase3Audit:
    """Phase 3 — defensive-audit pass over an EquilibriumResult.

    Identifies the unit classes where defensive math does the heaviest lifting
    (high FNP + low wounds, invuln cliffs, multi-wound elites) and verifies
    the pricing captures them. Also lists units the anchor can't meaningfully
    damage. No mutation of the result; returns a Phase3Audit report.

    `catalog` lets callers inject a synthetic profile map (used by tests to
    sanity-check the logic when the live catalogue's invuln data is sparse).
    Defaults to `UNIT_CATALOG`.

    See module-level Phase 3 block for class definitions and thresholds.
    """
    keys = list(result.keys)
    units = _units_from_result(result, catalog=catalog)

    high_fnp_units: List[Tuple[str, float]] = []
    invuln_cliff_units: List[Tuple[str, int, int]] = []
    multiwound_elite_units: List[str] = []

    for key, u in zip(keys, units):
        # ---- Class 1: high FNP + low wounds. ----
        # Uplift = T_with_fnp / T_save_only = (1/fnp_mult). FNP 5+ -> 1.5x,
        # FNP 4+ -> 2.0x, FNP 3+ -> 3.0x. Threshold is uplift > 1.5x, which
        # captures FNP 4+ AND FNP 5+ at the boundary.
        if u.fnp <= _PHASE3_FNP_THRESHOLD and u.health <= _PHASE3_LOW_WOUND_MAX:
            mult = _fnp_multiplier(u.fnp)
            if mult > 0:
                uplift = 1.0 / mult
                if uplift >= _PHASE3_DURABILITY_UPLIFT_FLOOR:
                    high_fnp_units.append((key, round(uplift, 3)))

        # ---- Class 2: invuln cliff. ----
        # The damage routine uses `min(save_after_ap, invuln)`. We flag a
        # cliff when |save - invuln| >= 2 with invuln <= 4+. Two regimes:
        #   (a) save WORSE than invuln (Sv 6+/Inv 4+ Priest, gap +2):
        #       invuln dominates from the start.
        #   (b) save BETTER than invuln (Sv 2+/Inv 4+ Custodes, gap -2):
        #       invuln only kicks in vs AP-2-or-better, but it provides
        #       a hard 4+ floor that armour-stripping shots cannot break.
        # Both regimes show up as "defensive math is doing real work" —
        # the bare save number alone undersells durability.
        if (
            u.invuln_save <= _PHASE3_INVULN_CEIL
            and abs(u.save - u.invuln_save) >= _PHASE3_INVULN_GAP_MIN
        ):
            invuln_cliff_units.append((key, int(u.save), int(u.invuln_save)))

        # ---- Class 3: multi-wound elite. ----
        # T scales linearly with wounds (T = wounds / D), so health=3 -> 50%
        # longer to kill than health=2 at the same D. List these for the
        # sanity check at the end.
        if u.health >= _PHASE3_ELITE_WOUND_MIN and u.save <= _PHASE3_ELITE_SAVE_MAX:
            multiwound_elite_units.append(key)

    high_fnp_units.sort(key=lambda x: x[1], reverse=True)
    invuln_cliff_units.sort()
    multiwound_elite_units.sort()

    # ---- Class 4: spot-checks against the anchor. ----
    anchor_key = result.anchor_key
    spot_checks: List[dict] = []
    targets = [
        ("death_guard_plague_marines", "plague_marines"),
        ("adeptus_custodes_custodian_guard", "custodian_guard"),
        ("aeldari_aeldari_library_wraithguard", "wraithguard"),
    ]
    for canonical, substring in targets:
        defender_key = canonical if canonical in keys else _closest_key_by_substring(
            keys, substring,
        )
        if defender_key is None:
            spot_checks.append({
                "attacker_key": anchor_key,
                "defender_key": None,
                "T_value": None,
                "expected_vs_naive_ratio": None,
                "note": f"no catalogue match for {substring!r}",
            })
            continue
        entry = _spot_check(result, anchor_key, defender_key, catalog=catalog)
        if entry is None:
            continue
        if defender_key != canonical:
            entry["note"] = f"substituted for missing {canonical!r}"
        spot_checks.append(entry)

    # ---- Class 5: unpriceable vs anchor. ----
    # Units the anchor's shooting matrix can't put a meaningful dent in
    # (D < 0.05/turn). The full-row solver still computes log_p from valid
    # off-axis matchups, but these matchups specifically need a fallback.
    if anchor_key in keys:
        i = result.index_of(anchor_key)
        anchor_row = result.D[i]
        unpriceable_vs_anchor = sorted(
            keys[j] for j in range(len(keys))
            if j != i and anchor_row[j] < _PHASE3_NEAR_ZERO_DAMAGE
        )
    else:
        unpriceable_vs_anchor = []

    return Phase3Audit(
        high_fnp_units=high_fnp_units,
        invuln_cliff_units=invuln_cliff_units,
        multiwound_elite_units=multiwound_elite_units,
        spot_checks=spot_checks,
        unpriceable_vs_anchor=unpriceable_vs_anchor,
        anchor_key=anchor_key,
    )


# ---------------------------------------------------------------------------
# Phase 4 — Tactical-utility term (move / OC / range / deploy abilities)
# ---------------------------------------------------------------------------
#
# The Phase 2 solver prices units by their pairwise damage matrix. Defensive
# math enters via T = wounds / D. But two non-damaging dimensions of tournament
# value are *invisible* to DPA-based matrices:
#
#   * positional advantage — Move, range, scout, infiltrator, deep strike all
#     let a unit pick the engagement it wants. A 12" Move unit can refuse a
#     bad matchup and force a good one; that's pricing-relevant.
#   * objective economy — OC and sticky-objective directly convert to VP under
#     10e mission scoring; a 2-OC Termagant is worth more on a Take-and-Hold
#     primary than a 1-OC equivalent.
#
# Phase 4 adds an analytic `tactical_value(u, weights)` term that contributes a
# phantom DPS-like number to the row-sum. Each component clamps at the baseline
# value (M=6, OC=1, range=12) so vanilla profiles get 0 contribution and only
# above-average traits add value. Composition is additive — each component has
# its own weight, summed.
#
# Calibration: the default `TacticalWeights` below were chosen by grid search
# over a held-out set of 9 GW-priced "known fair" units (Intercessor Squad,
# Custodian Guard, Hellblasters, Ork Boyz, Necron Warriors, Termagants,
# Kasrkin, Battle Sisters, Skitarii Rangers — Crisis Battlesuits and
# Wraithguard excluded because their min_models=1 in the catalogue distorts
# per-model pricing). The objective minimised was the sum-of-squared Phase 2
# mispricing percentage. See `_calibrate_weights` and the `--calibrate` CLI
# flag for the procedure; the docstring on `TacticalWeights` records the
# chosen values.

@dataclass(frozen=True)
class TacticalWeights:
    """Per-component weights for `tactical_value`.

    These defaults were chosen by a 5-level grid search (`_calibrate_weights`)
    over the 9-unit held-out anchor set in `_CALIBRATION_ANCHORS`, minimising
    sum-of-squared Phase 2 mispricing-pct.

    The 2026-05 calibration result on the live BSData v10.6.0 catalogue:

        w_move              = 0.000   (anchors are uniform on move=6; no signal)
        w_oc                = 0.000   (Battle Sisters & Termagants both OC2 but
                                       mispriced opposite directions; no signal)
        w_range             = 0.250   (Kasrkin r24, Skitarii r30 -> uplifts
                                       Phase-2-undercosted shooters)
        w_deep_strike       = 0.000   (Custodes are *already* OVERCOSTED by
                                       Phase 2 — adding DS uplift hurts)
        w_scout             = 0.050   (Kasrkin & Skitarii both scout 6")
        w_infiltrator       = 0.000   (no anchor has it; calibration can't sign)
        w_sticky_objective  = 0.150   (Necron Warriors only; pulls them toward
                                       fair price)

        RSS reduction: 38932 -> 33654 on 9 anchors (-13.6%).

    Findings worth recording for future calibration passes:

      * `w_move=0` and `w_infiltrator=0` aren't statements about the rule —
        they're statements about the anchor set being underpowered to identify
        those weights. A wider anchor set (Eldar Spectres, Ork Stormboyz,
        Genestealer Cults Acolytes) would constrain them properly.
      * `w_deep_strike=0` reflects that Custodian Guard, the only DS anchor,
        is already overcosted by Phase 2 — Phase 4 correctly declines to make
        that worse. Once Phase 3's invuln-cliff fix lands in the damage matrix
        Custodes should re-price up and the calibration can re-enable DS.
      * `w_range=0.25` is at the upper end of the sensible grid; if you widen
        further it keeps climbing because Kasrkin's +70% Phase 2 underpricing
        is bigger than Skitarii's overshoot. Capped at 0.25 to keep the term
        physically interpretable (24" weapons get +17% from this component).

    Field semantics — each is a log/linear contribution that clamps at the
    baseline (M=6, OC=1, range=12) so vanilla profiles add 0:
      w_move              per unit of log(move/6), only above 6
      w_oc                per OC point above 1 (linear)
      w_range             per unit of log(range/12), only above 12
      w_deep_strike       flat bonus if deep_strike=True
      w_scout             per inch of scout_distance (linear)
      w_infiltrator       flat bonus if infiltrator=True
      w_sticky_objective  flat bonus if sticky_objective=True
    """

    w_move: float = 0.00
    w_oc: float = 0.00
    w_range: float = 0.25
    w_deep_strike: float = 0.00
    w_scout: float = 0.05
    w_infiltrator: float = 0.00
    w_sticky_objective: float = 0.15


def tactical_value(profile: UnitProfile,
                   weights: TacticalWeights = TacticalWeights()) -> float:
    """Phantom DPS-like additive contribution from tactical traits.

    Returns a non-negative float that is shifted into the log-points domain
    multiplicatively as `1 + tactical_value(u)` (see `compute_phase4`).

    Component shape rationale:
      * Move uses max(0, log(m / 6)) so a 12" unit gets log(2) ~= 0.693, a 6"
        unit gets 0, a 4" unit also gets 0 (no penalty for being slow — the
        damage matrix already prices the engagement they LOSE).
      * Range uses max(0, log(r / 12)) on the same shape — a 24" weapon gets
        log(2), a 48" weapon gets log(4), 12" gets 0.
      * OC and scout are linear above their baselines.
      * Boolean traits contribute their flat weight.
    """
    m = max(0.0, math.log(max(profile.move, 1e-9) / 6.0))
    r = max(0.0, math.log(max(profile.range_inches, 1e-9) / 12.0))
    oc_excess = max(0, profile.oc - 1)
    scout_inches = max(0, profile.scout_distance)
    return (
        weights.w_move * m
        + weights.w_oc * oc_excess
        + weights.w_range * r
        + weights.w_deep_strike * (1.0 if profile.deep_strike else 0.0)
        + weights.w_scout * scout_inches
        + weights.w_infiltrator * (1.0 if profile.infiltrator else 0.0)
        + weights.w_sticky_objective * (1.0 if profile.sticky_objective else 0.0)
    )


def compute_phase4(
    catalog: Optional[Dict[str, UnitProfile]] = None,
    anchor_key: str = DEFAULT_ANCHOR_KEY,
    anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL,
    faction: Optional[str] = None,
    limit: Optional[int] = None,
    shoot_weight=None,
    weights: TacticalWeights = TacticalWeights(),
) -> EquilibriumResult:
    """Phase 4 — Phase 2 combat solve plus a tactical-utility term.

    Mechanism: run `compute_phase2` first, then bump each unit's log-points by
    `log(1 + tactical_value(u))` minus the anchor's tactical baseline. This
    leaves the anchor's price pinned (Intercessor pays its own tactical_value
    out, so the scale doesn't drift) and adds a multiplicative `1 + t(u)/(1+t_a)`
    correction on every other unit.

    The damage matrix `D`, time-to-kill `T`, and log-advantage `R` are inherited
    from the Phase 2 result unchanged — the tactical term is a pure analytic
    overlay on top of the combat math, not a re-solve.
    """
    base = compute_phase2(
        catalog=catalog,
        anchor_key=anchor_key,
        anchor_per_model=anchor_per_model,
        faction=faction,
        limit=limit,
        shoot_weight=shoot_weight,
    )

    src = catalog if catalog is not None else UNIT_CATALOG
    units = [src[k] for k in base.keys]
    anchor_idx = base.keys.index(anchor_key)

    tv = np.array([tactical_value(u, weights) for u in units], dtype=float)
    log_factor = np.log1p(tv)
    # Subtract the anchor's tactical baseline so the anchor stays pinned at
    # its target price after the additive shift.
    log_factor = log_factor - log_factor[anchor_idx]
    x_phase4 = base.log_p + log_factor
    eq_per_model = np.exp(x_phase4)

    entries: List[EquilibriumEntry] = []
    for key, u, eq_pm, vc_entry in zip(base.keys, units, eq_per_model, base.entries):
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
                valid_matchups=vc_entry.valid_matchups,
                role=_classify_role(u),
            )
        )
    return EquilibriumResult(
        entries=entries,
        keys=base.keys,
        D=base.D,
        T=base.T,
        R=base.R,
        log_p=x_phase4,
        anchor_key=anchor_key,
        anchor_per_model=anchor_per_model,
        phase=4,
    )


# ---------------------------------------------------------------------------
# Phase 4 — Weight calibration (offline)
# ---------------------------------------------------------------------------
#
# The "known fair" anchor set is GW-priced units that the meta consensus and
# tournament data treat as roughly fair-priced. We exclude units whose
# `min_models=1` in the catalogue doesn't match their GW squad size (e.g.
# Crisis Battlesuits at 130/1, Wraithguard at 170/1) because their per-model
# mispricing is dominated by data shape, not tactical utility.

_CALIBRATION_ANCHORS: Tuple[str, ...] = (
    "space_marines_intercessor_squad",
    "adeptus_custodes_custodian_guard",
    "space_marines_hellblaster_squad",
    "orks_boyz",
    "necrons_necron_warriors",
    "tyranids_termagants",
    "astra_militarum_library_kasrkin",
    "adepta_sororitas_battle_sisters_squad",
    "adeptus_mechanicus_skitarii_rangers",
)


def _mispricing_rss(entries: List[EquilibriumEntry],
                    anchor_keys: Tuple[str, ...]) -> float:
    """Sum of squared mispricing-pct over the held-out anchors."""
    by_key = {e.key: e for e in entries}
    total = 0.0
    n = 0
    for k in anchor_keys:
        if k not in by_key:
            continue
        e = by_key[k]
        if e.gw_points_per_model <= 0:
            continue
        total += (e.mispricing_pct) ** 2
        n += 1
    return total


def _calibrate_weights(
    anchor_keys: Tuple[str, ...] = _CALIBRATION_ANCHORS,
    catalog: Optional[Dict[str, UnitProfile]] = None,
    levels: int = 5,
) -> Tuple[TacticalWeights, float, float]:
    """Coarse grid search over `TacticalWeights` minimising mispricing RSS.

    Returns `(best_weights, rss_before, rss_after)`. `rss_before` is the
    Phase 2 RSS over `anchor_keys`; `rss_after` is the best Phase 4 RSS found.

    The grid is 5 levels per weight on a sensible range; this is enough to
    pick a robust point without overfitting the noisy anchor labels. The full
    search costs `levels**7` * one cheap log_p shift per evaluation — ~78k
    points at default settings, runs in under 5s after the (single) Phase 2
    solve completes.
    """
    base = compute_phase2(catalog=catalog)
    src = catalog if catalog is not None else UNIT_CATALOG
    units = [src[k] for k in base.keys]
    anchor_idx = base.keys.index(DEFAULT_ANCHOR_KEY)

    # Baseline RSS at Phase 2 (no tactical correction).
    rss_before = _mispricing_rss(base.entries, anchor_keys)

    # 5-level grids per weight on a "sensible" range around the docstring default.
    # Ranges chosen wide enough that the optimum isn't pinned to a corner; if
    # it is, widen the range for that weight and re-run. The upper bounds
    # below were calibrated by hand: each weight's max is roughly 2x what
    # produces a "matters but doesn't dominate" multiplicative shift on a
    # representative unit (e.g. w_sticky 0.6 -> 60% per-model uplift on a
    # sticky-objective unit; w_range 0.15 -> 15% * log(24/12) ~= 10% on a
    # 24" weapon).
    move_grid = np.linspace(0.0, 0.15, levels)
    oc_grid = np.linspace(0.0, 0.20, levels)
    range_grid = np.linspace(0.0, 0.25, levels)
    ds_grid = np.linspace(0.0, 0.40, levels)
    scout_grid = np.linspace(0.0, 0.10, levels)
    inf_grid = np.linspace(0.0, 0.30, levels)
    sticky_grid = np.linspace(0.0, 0.60, levels)

    # Cache: which keys are in the held-out set and what's the per-key GW.
    keep_idx = [base.keys.index(k) for k in anchor_keys if k in base.keys]
    gw_per_model = np.array([
        units[i].points_per_squad / max(1, units[i].min_models) for i in keep_idx
    ])

    # Precompute the per-component values for every keep_idx — the loop only
    # multiplies these by candidate weights.
    def _comp(u: UnitProfile):
        m = max(0.0, math.log(max(u.move, 1e-9) / 6.0))
        r = max(0.0, math.log(max(u.range_inches, 1e-9) / 12.0))
        return np.array([
            m, max(0, u.oc - 1), r,
            1.0 if u.deep_strike else 0.0,
            max(0, u.scout_distance),
            1.0 if u.infiltrator else 0.0,
            1.0 if u.sticky_objective else 0.0,
        ], dtype=float)

    comp_keep = np.array([_comp(units[i]) for i in keep_idx])  # (n_keep, 7)
    comp_anchor = _comp(units[anchor_idx])                     # (7,)
    base_log_p_keep = base.log_p[keep_idx]
    base_log_p_anchor = base.log_p[anchor_idx]

    best_rss = float("inf")
    best_w: Optional[TacticalWeights] = None
    for wm in move_grid:
        for wo in oc_grid:
            for wr in range_grid:
                for wd in ds_grid:
                    for ws in scout_grid:
                        for wi in inf_grid:
                            for wsk in sticky_grid:
                                w_vec = np.array([wm, wo, wr, wd, ws, wi, wsk])
                                # tactical_value for keep_idx and anchor
                                tv_keep = comp_keep @ w_vec
                                tv_anchor = float(comp_anchor @ w_vec)
                                log_shift = np.log1p(tv_keep) - math.log1p(tv_anchor)
                                # Anchor itself stays pinned by construction.
                                # (When the keep_idx contains the anchor, that
                                # row's shift is exactly 0 — confirmed analytically.)
                                eq_pm = np.exp(base_log_p_keep + log_shift)
                                # Mispricing-pct = (GW - eq) / eq * 100
                                mp = (gw_per_model - eq_pm) / eq_pm * 100.0
                                # Filter out any GW=0 entries (shouldn't happen on
                                # the held-out set, but guard anyway).
                                ok = gw_per_model > 0
                                rss = float(np.sum(mp[ok] ** 2))
                                if rss < best_rss:
                                    best_rss = rss
                                    best_w = TacticalWeights(
                                        w_move=float(wm),
                                        w_oc=float(wo),
                                        w_range=float(wr),
                                        w_deep_strike=float(wd),
                                        w_scout=float(ws),
                                        w_infiltrator=float(wi),
                                        w_sticky_objective=float(wsk),
                                    )

    assert best_w is not None
    return best_w, rss_before, best_rss


# ---------------------------------------------------------------------------
# Phase 5 — Meta-weighted matchup solve
# ---------------------------------------------------------------------------
#
# Phase 1-4 treat every matchup (i, j) as equally important when forming the
# row-mean of R[i, j] = (1/2) log(T[j,i]/T[i,j]). That implicitly assumes a
# uniform meta — that you're equally likely to face any unit on the table.
# Real tournament play is heavily skewed: in May 2026 ~55% of top-table games
# involve a Necron / T'au / Thousand Sons opponent, while Leagues of Votann and
# Adepta Sororitas combined are <10% of fields. A unit whose value comes from
# crushing the common archetypes deserves to cost more than one whose value
# comes from crushing what nobody plays.
#
# Phase 5 reweights the LSQ residuals by the *defender's* faction meta share.
# The closed-form weighted row-mean is:
#
#     x_i = sum_j (w_j * R[i,j]) / sum_j (w_j)        # over valid j
#
# where w_j is the meta share of defender j's faction. This is the LSQ optimum
# under independent column weights — equivalent to running np.linalg.lstsq on
# the same R with the j-axis weighted by sqrt(w_j).
#
# Attacker-meta uplift
# --------------------
# Column weighting alone doesn't shift the price of two identical-stat units
# in different factions: their R[i, :] rows are identical, so their weighted
# row-means are identical. But the brief's intuition — "a unit in a 15% meta
# share faction has weight ~0.15" — is per-unit, not per-pair. We honour that
# with a small additive log-shift `META_ATTACKER_UPLIFT * (w_i - w_anchor)`
# on top of the column-weighted solve. This is a calibrated, capped shift
# (default 0.5 in log-space, i.e. up to ~+5% / -5% per ±10% share gap)
# chosen small enough that high-meta-share factions price up modestly
# without overwhelming the matchup-driven signal.
#
# Meta source
# -----------
# Faction representation comes from the May 2026 warpfriends weekly aggregate
# (~10k games) — the same source `scripts/evaluate_vs_meta.py` uses for its
# win-rate target. Win-rate is what `TOURNAMENT_TARGET` records there;
# representation share is what we need *here* (we want to know how often a
# faction shows up, not how well it does when it shows up). The figures below
# are the faction-representation column from the same aggregate, cited per
# entry. Factions outside the top-10 share table get the residual mass split
# evenly — a conservative "we don't know, assume average representation" prior.

# Faction-representation share from the May 2026 warpfriends weekly. Top-10
# factions only — these are the slices the aggregate reports separately. The
# numbers reflect *play share*, not win rate (Necrons can be 11% of fields
# without dominating; T'au at 7% can punch above their share at high WR).
#
# Source: warpfriends weekly meta snapshot (May 2026, ~10k games). Aligned
# 1:1 with `scripts.evaluate_vs_meta.FACTIONS` so the same source defines
# both the win-rate target and the play-rate weight.
META_FACTION_SHARE: Dict[str, float] = {
    "Adeptus Astartes":   0.13,   # broad chapter family — largest single bloc
    "Necrons":            0.11,
    "Aeldari":            0.09,
    "Tyranids":           0.08,
    "Orks":               0.08,
    "T'au Empire":        0.07,
    "Death Guard":        0.05,
    "Adeptus Custodes":   0.04,
    "Thousand Sons":      0.05,
    "Leagues of Votann":  0.03,
}
# Residual mass (1 - sum) is split evenly across factions absent from the
# table. The catalogue has ~25 factions outside the top-10, so the default
# share is small but non-zero — a unit whose only same-faction opponents are
# Genestealer Cults still gets *some* signal, just less than a Necron unit
# would.
_META_TOP_TOTAL = sum(META_FACTION_SHARE.values())
_META_RESIDUAL_PER_FACTION_HINT = max(0.0, 1.0 - _META_TOP_TOTAL)

# Strength of the per-unit attacker-meta uplift in log-space. Applied as
#     log_shift = META_ATTACKER_UPLIFT * (w_i - w_anchor)
# so the anchor stays pinned and a +10% share gap produces a ~+5% price
# uplift (since exp(0.05) ~= 1.05). Capped small enough that the column-
# weighted matchup signal still dominates pricing.
META_ATTACKER_UPLIFT = 0.5


def _meta_weight_for_unit(unit: UnitProfile,
                           share_table: Dict[str, float],
                           default: float) -> float:
    """Look up a unit's faction meta-share weight. Falls back to `default` if
    the unit's faction isn't in the share table (e.g. Heresy Legends, Chaos
    Daemons, Adepta Sororitas — present in the catalogue but outside the
    reported top-10)."""
    return float(share_table.get(unit.faction, default))


def _build_meta_weights(
    units: List[UnitProfile],
    share_table: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """Per-unit meta weight vector. Length n_units; entry j is used as the
    column weight for defender j when reweighting R[i, j]."""
    if share_table is None:
        share_table = META_FACTION_SHARE
    # Compute a faction-uniform default for unseen factions: the residual mass
    # (1 - sum of known shares) divided over the count of "unseen" factions
    # actually present in `units`. This keeps the per-unit weight comparable
    # in scale to the known-faction weights instead of jumping to a tiny prior.
    seen_unseen = {u.faction for u in units if u.faction not in share_table}
    if seen_unseen:
        default = max(1e-6, _META_RESIDUAL_PER_FACTION_HINT) / len(seen_unseen)
    else:
        default = 1e-6
    return np.array(
        [_meta_weight_for_unit(u, share_table, default) for u in units],
        dtype=float,
    )


def solve_log_points_weighted(
    T: np.ndarray,
    column_weights: np.ndarray,
    anchor_idx: int,
    anchor_log_p: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Weighted closed-form log-LSQ.

    Identical to `solve_log_points` except each column j contributes
    `column_weights[j]` to the row-mean. The optimum of

        min_x sum_{i,j} w_j * (x_i - x_j - R[i,j])^2     (LSQ on R with col weights)

    when only row-mean degrees of freedom are used is

        x_i = sum_j (w_j * R[i,j]) / sum_j (w_j over valid pairs)

    Returns (x, weighted_sum_of_weights) — the second array carries the total
    column-weight that fed into each row, useful for diagnostics.
    """
    n = T.shape[0]
    finite_T = np.isfinite(T)
    log_T = np.zeros_like(T)
    log_T[finite_T] = np.log(T[finite_T])
    finite_mask = finite_T & finite_T.T
    np.fill_diagonal(finite_mask, False)

    R = np.where(finite_mask, 0.5 * (log_T.T - log_T), 0.0)
    # Broadcast column weights across rows, mask out invalid pairs.
    w_row = np.broadcast_to(column_weights[np.newaxis, :], R.shape)
    w_valid = np.where(finite_mask, w_row, 0.0)
    weighted_R = R * w_valid
    weight_totals = w_valid.sum(axis=1)
    safe_totals = np.where(weight_totals <= 0, 1.0, weight_totals)
    x_raw = weighted_R.sum(axis=1) / safe_totals

    shift = anchor_log_p - x_raw[anchor_idx]
    x = x_raw + shift
    # Units with zero total weight (no valid partners OR all partners zero-weight):
    # fall back to the anchor price.
    x[weight_totals <= 0] = anchor_log_p
    return x, weight_totals


@dataclass
class Phase5Comparison:
    """Per-unit Phase 4 -> Phase 5 movement record."""
    key: str
    name: str
    faction: str
    phase4_per_model: float
    phase5_per_model: float
    ratio_phase5_over_phase4: float
    meta_weight: float


@dataclass
class Phase5Result:
    """Phase 5 output bundle. Carries the same EquilibriumResult-shaped fields
    as Phase 4 plus the per-unit comparison vs Phase 4 and the meta weight
    vector that produced them.

    `result` is a standard `EquilibriumResult` (phase=5) so downstream UI /
    persistence code can consume it unchanged. `comparison` lets callers see
    what moved without re-running Phase 4.
    """
    result: EquilibriumResult
    comparison: List[Phase5Comparison]
    meta_weights: np.ndarray
    share_table: Dict[str, float]
    phase4_result: EquilibriumResult


def compute_phase5(
    catalog: Optional[Dict[str, UnitProfile]] = None,
    anchor_key: str = DEFAULT_ANCHOR_KEY,
    anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL,
    faction: Optional[str] = None,
    limit: Optional[int] = None,
    shoot_weight=None,
    weights: TacticalWeights = TacticalWeights(),
    share_table: Optional[Dict[str, float]] = None,
) -> Phase5Result:
    """Phase 5 — meta-weighted equilibrium solve on top of Phase 4.

    Pipeline:
      1. Run Phase 4 to get the tactical-utility-adjusted baseline (its
         damage matrix D, T, R are reused — only the residual weighting
         changes).
      2. Build a per-defender column-weight vector from `share_table`
         (defaults to `META_FACTION_SHARE` — the May 2026 warpfriends
         aggregate).
      3. Re-run the closed-form log-LSQ with `solve_log_points_weighted`,
         using T from step 1 and the column weights from step 2.
      4. Re-apply the tactical-utility log-shift on top of the weighted solve
         (the tactical term is independent of the meta — a unit's positional
         advantage doesn't depend on who it faces).
      5. Build a Phase5Comparison list against the Phase 4 prices.

    The anchor remains pinned to `anchor_per_model` — the weighted shift
    preserves the anchor by construction (we subtract `x_raw[anchor_idx]`
    before adding `anchor_log_p`).
    """
    phase4 = compute_phase4(
        catalog=catalog,
        anchor_key=anchor_key,
        anchor_per_model=anchor_per_model,
        faction=faction,
        limit=limit,
        shoot_weight=shoot_weight,
        weights=weights,
    )

    src = catalog if catalog is not None else UNIT_CATALOG
    units = [src[k] for k in phase4.keys]
    anchor_idx = phase4.keys.index(anchor_key)
    anchor_log_p = math.log(anchor_per_model)

    column_weights = _build_meta_weights(units, share_table=share_table)

    # Run the WEIGHTED solve on the same T matrix Phase 4 used. We re-derive
    # T here rather than relying on phase4.T directly because the weighted
    # solver wants the raw time-to-kill matrix — phase4.T already carries
    # any infinities from D=0 matchups, which is the right input.
    x_weighted, weight_totals = solve_log_points_weighted(
        phase4.T, column_weights, anchor_idx, anchor_log_p,
    )

    # Re-apply the tactical-utility overlay on top of the weighted log-points.
    # Mathematically: x_phase5 = x_weighted + (log_factor - log_factor[anchor])
    # where log_factor[i] = log(1 + tactical_value(u_i)). This mirrors how
    # Phase 4 applies the overlay on top of Phase 2.
    tv = np.array([tactical_value(u, weights) for u in units], dtype=float)
    log_factor = np.log1p(tv)
    log_factor = log_factor - log_factor[anchor_idx]

    # Attacker-meta uplift: small additive log-shift proportional to the gap
    # between a unit's own faction share and the anchor's. Anchor's shift is
    # exactly 0 by construction (so it stays pinned), high-share units get a
    # positive shift, low-share units get a negative one. See module-level
    # "Attacker-meta uplift" docstring for the calibration rationale.
    anchor_weight = column_weights[anchor_idx]
    attacker_uplift = META_ATTACKER_UPLIFT * (column_weights - anchor_weight)

    x_phase5 = x_weighted + log_factor + attacker_uplift
    eq_per_model = np.exp(x_phase5)

    entries: List[EquilibriumEntry] = []
    for key, u, eq_pm, vc_entry in zip(phase4.keys, units, eq_per_model, phase4.entries):
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
                valid_matchups=vc_entry.valid_matchups,
                role=_classify_role(u),
            )
        )

    result = EquilibriumResult(
        entries=entries,
        keys=phase4.keys,
        D=phase4.D,
        T=phase4.T,
        R=phase4.R,
        log_p=x_phase5,
        anchor_key=anchor_key,
        anchor_per_model=anchor_per_model,
        phase=5,
    )

    # Per-unit Phase 4 -> Phase 5 comparison records, sorted by absolute
    # log-ratio movement (largest mover first).
    phase4_by_key = {e.key: e for e in phase4.entries}
    comparison: List[Phase5Comparison] = []
    for key, e5, w_j in zip(phase4.keys, entries, column_weights):
        e4 = phase4_by_key[key]
        ratio = (
            e5.equilibrium_points_per_model / e4.equilibrium_points_per_model
            if e4.equilibrium_points_per_model > 0 else 0.0
        )
        comparison.append(Phase5Comparison(
            key=key,
            name=e5.name,
            faction=e5.faction,
            phase4_per_model=e4.equilibrium_points_per_model,
            phase5_per_model=e5.equilibrium_points_per_model,
            ratio_phase5_over_phase4=round(float(ratio), 4),
            meta_weight=round(float(w_j), 4),
        ))

    return Phase5Result(
        result=result,
        comparison=comparison,
        meta_weights=column_weights,
        share_table=share_table if share_table is not None else dict(META_FACTION_SHARE),
        phase4_result=phase4,
    )


# ---------------------------------------------------------------------------
# Phase 6 — Nash equilibrium for mixed strategies
# ---------------------------------------------------------------------------
#
# Phase 5 reweights the row-mean LSQ residuals by a *fixed exogenous* meta
# distribution (May 2026 warpfriends play-share). Phase 6 asks the deeper
# question: what defender distribution would the WORST-CASE opponent play
# against you? That distribution is the Nash equilibrium of the symmetric
# two-player zero-sum game over the catalogue.
#
# Payoff matrix
# -------------
# Per the brief, the symmetric payoff is the trade ratio:
#
#     M[i, j] = (T[j, i] - T[i, j]) / (T[i, j] + T[j, i])    in [-1, 1]
#
# Antisymmetric (M[i, j] == -M[j, i]) by construction. Positive M[i, j] means
# row-player's unit i kills column-player's unit j faster than the reverse —
# i.e. i is better than j. For pairs where either T is infinite (no damage in
# at least one direction) we set M[i, j] = 0: no usable game signal.
#
# LP formulation
# --------------
# Row player's max-min problem:
#
#     max v
#     s.t. sigma^T @ M[:, j] >= v   for all j
#          sum(sigma) = 1
#          sigma >= 0
#
# Standard linprog form (minimise c^T x, A_ub x <= b_ub, A_eq x = b_eq, bounds):
#   variables x = [sigma_1, ..., sigma_n, v]
#   minimise:   c = [0, ..., 0, -1]                 (maximise v)
#   A_ub row j: [-M[1,j], -M[2,j], ..., -M[n,j], 1] <= 0
#               (rewrite v - sigma^T M[:,j] <= 0)
#   A_eq:       [1, 1, ..., 1, 0] = 1               (simplex)
#   bounds:     sigma_i in [0, None], v in (-inf, inf)
#
# Because M is antisymmetric the game value v is zero (by the symmetric-game
# lemma) — we don't use v, we use sigma. sigma is the Nash mixed strategy:
# the defender distribution against which every unit's expected payoff is at
# least v=0, with equality on the support.
#
# Fair points from the Nash strategy
# ----------------------------------
# Two reasonable readings of "fair value from dual variables":
#   (a) sigma itself — the relative weight a unit gets in the Nash mix is its
#       strategic importance, and prices should reflect that.
#   (b) the dual of the inequality constraints (the column player's strategy
#       tau, equal to sigma in a symmetric game) — same numbers, same prices.
#
# We use sigma as a per-defender column weight in `solve_log_points_weighted`,
# operating on the SAME T matrix Phase 5 used. This treats the Nash mixed
# strategy as "the meta you should price against" — replacing Phase 5's
# exogenous warpfriends meta with an endogenous, game-theoretic one.
#
# We anchor on the same Intercessor baseline as Phase 1-5 by pinning the
# anchor's post-shift log-price to log(anchor_per_model). The tactical-utility
# overlay (Phase 4) and attacker-meta uplift (Phase 5) are NOT re-applied at
# Phase 6 — they remain part of the prior_result's log-prices and would
# double-count if added a second time. We start from phase5.T, not from
# phase5.log_p, and rebuild log_p with the Nash-weighted solve.

# Numerical regulariser: when sigma's support is very sparse the column-
# weighted LSQ can become near-degenerate for low-support attackers. We mix a
# tiny epsilon of the uniform distribution into the weight vector so every
# defender contributes some signal — Tikhonov-style stabilisation.
_PHASE6_SIGMA_REGULARISATION = 1e-3


def _build_nash_payoff_matrix(T: np.ndarray) -> np.ndarray:
    """Antisymmetric trade-ratio matrix M[i, j] = (T[j,i] - T[i,j]) / (T[i,j] + T[j,i]).

    Where either T is non-finite or the denominator vanishes, M = 0 (no game
    signal). Diagonal is forced to 0. Entries are guaranteed in [-1, 1] and
    M == -M.T to numerical precision (subject to inf-handling).
    """
    n = T.shape[0]
    M = np.zeros((n, n), dtype=float)
    finite = np.isfinite(T) & np.isfinite(T.T)
    np.fill_diagonal(finite, False)
    with np.errstate(invalid="ignore", divide="ignore"):
        num = T.T - T
        den = T + T.T
        ratio = np.where((den > 0) & finite, num / den, 0.0)
    M[finite] = ratio[finite]
    # Force exact antisymmetry — numerical noise can leak in via the inf-mask
    # asymmetry. (1/2)(M - M^T) projects onto the antisymmetric subspace.
    M = 0.5 * (M - M.T)
    np.fill_diagonal(M, 0.0)
    # Pre-normalise to [-1, 1] (defensive; the formula guarantees it).
    max_abs = float(np.max(np.abs(M))) if M.size else 0.0
    if max_abs > 1.0:
        M = M / max_abs
    return M


def solve_nash_mixed_strategy(M: np.ndarray) -> Tuple[np.ndarray, float, bool]:
    """Solve the symmetric zero-sum LP and return the row player's Nash sigma.

    Maximise v s.t. M^T sigma >= v 1, sum(sigma) = 1, sigma >= 0.
    Encoded into scipy.optimize.linprog standard form (minimise -v with
    -M^T sigma + v <= 0 inequality rows). Returns `(sigma, v, ok)` where
    `ok=False` signals the LP failed (infeasible/unbounded) and `sigma` falls
    back to the uniform distribution.
    """
    from scipy.optimize import linprog

    n = M.shape[0]
    # Variables: x = [sigma_0, ..., sigma_{n-1}, v].
    # Objective: minimise -v  <=> maximise v.
    c = np.zeros(n + 1, dtype=float)
    c[-1] = -1.0
    # Inequalities: for each j, v - sum_i sigma_i * M[i, j] <= 0
    #   row j: [-M[0,j], -M[1,j], ..., -M[n-1,j], 1] <= 0
    A_ub = np.zeros((n, n + 1), dtype=float)
    A_ub[:, :n] = -M.T
    A_ub[:, -1] = 1.0
    b_ub = np.zeros(n, dtype=float)
    # Equality: sum(sigma) = 1
    A_eq = np.zeros((1, n + 1), dtype=float)
    A_eq[0, :n] = 1.0
    b_eq = np.array([1.0], dtype=float)
    # Bounds: sigma >= 0, v unbounded
    bounds = [(0.0, None)] * n + [(None, None)]

    res = linprog(
        c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds,
        method="highs",
    )
    if not res.success or res.x is None:
        # Fall back to uniform; caller will log the warning.
        return np.full(n, 1.0 / max(n, 1), dtype=float), 0.0, False
    sigma = np.asarray(res.x[:n], dtype=float)
    v = float(res.x[-1])
    # Clip tiny negatives from interior-point slack and re-normalise to the
    # simplex — Nash sigma is defined exactly on it.
    sigma = np.clip(sigma, 0.0, None)
    s = sigma.sum()
    if s > 0:
        sigma = sigma / s
    else:
        sigma = np.full(n, 1.0 / max(n, 1), dtype=float)
    return sigma, v, True


@dataclass
class Phase6NashResult:
    """Phase 6 output bundle. Carries an EquilibriumResult-shaped result plus
    the Nash mixed strategy and the game value v.

    `result` is a standard `EquilibriumResult` (phase=6) so downstream UI /
    persistence consume it unchanged. `nash_strategy` is the row player's
    optimal sigma on the simplex — by symmetry it's also the column player's
    optimal tau. `game_value` is the LP's v; in a symmetric antisymmetric game
    this is identically zero to numerical precision, and we report it for the
    audit trail.
    """
    result: EquilibriumResult
    nash_strategy: np.ndarray
    game_value: float
    lp_ok: bool
    prior_result: EquilibriumResult


def compute_phase6_nash(
    catalog: Optional[Dict[str, UnitProfile]] = None,
    anchor_key: str = DEFAULT_ANCHOR_KEY,
    anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL,
    faction: Optional[str] = None,
    limit: Optional[int] = None,
    shoot_weight=None,
    weights: TacticalWeights = TacticalWeights(),
    prior_result: Optional[EquilibriumResult] = None,
) -> Phase6NashResult:
    """Phase 6 — Nash equilibrium-weighted pricing.

    Pipeline:
      1. Get the prior (Phase 5) result. If `prior_result=None`, run Phase 5
         on the same catalogue / anchor / faction filter to produce it.
      2. Build the antisymmetric trade-ratio matrix M from prior_result.T.
      3. Solve the zero-sum LP for the row player's Nash sigma.
      4. Use sigma (plus a tiny uniform regulariser) as the column weight in
         `solve_log_points_weighted` on the SAME T matrix the prior used.
      5. Anchor-pin: the weighted solver subtracts x_raw[anchor_idx] and adds
         log(anchor_per_model), so the anchor stays at its configured price.

    If the LP fails (infeasible / unbounded — shouldn't happen on real data,
    but defensive), sigma falls back to uniform and `Phase6NashResult.lp_ok`
    is `False`. The result is then effectively a uniform-meta solve (which is
    Phase 4's solve, anchored).

    The tactical-utility log-shift and Phase-5 attacker-meta uplift are NOT
    re-applied at Phase 6 — they're already baked into the prior_result's
    `log_p`, but we don't use that vector here; we re-solve from prior_result.T
    with the Nash weights. To keep the tactical overlay, we add it on top
    AFTER the Nash-weighted solve (mirroring Phase 4/5 composition).
    """
    if prior_result is None:
        phase5_bundle = compute_phase5(
            catalog=catalog,
            anchor_key=anchor_key,
            anchor_per_model=anchor_per_model,
            faction=faction,
            limit=limit,
            shoot_weight=shoot_weight,
            weights=weights,
        )
        prior_result = phase5_bundle.result

    src = catalog if catalog is not None else UNIT_CATALOG
    units = [src[k] for k in prior_result.keys]
    if anchor_key not in prior_result.keys:
        raise ValueError(
            f"Anchor unit {anchor_key!r} is not in the prior result; cannot "
            f"anchor Phase 6."
        )
    anchor_idx = prior_result.keys.index(anchor_key)
    anchor_log_p = math.log(anchor_per_model)

    # 1. Antisymmetric trade-ratio matrix.
    M = _build_nash_payoff_matrix(prior_result.T)

    # 2. Solve LP for Nash sigma.
    sigma, v, lp_ok = solve_nash_mixed_strategy(M)
    if not lp_ok:
        import warnings
        warnings.warn(
            "Phase 6 LP failed; falling back to uniform column weights. "
            "Result is effectively a uniform-meta solve.",
            RuntimeWarning,
        )

    # 3. Tikhonov-style regularisation: tiny mix of uniform so very-low-sigma
    # defenders still contribute (otherwise the weighted row-mean for some
    # attackers can collapse onto a single defender).
    n = len(units)
    uniform = np.full(n, 1.0 / max(n, 1), dtype=float)
    column_weights = (
        (1.0 - _PHASE6_SIGMA_REGULARISATION) * sigma
        + _PHASE6_SIGMA_REGULARISATION * uniform
    )

    # 4. Weighted closed-form LSQ on the prior's T matrix.
    x_weighted, weight_totals = solve_log_points_weighted(
        prior_result.T, column_weights, anchor_idx, anchor_log_p,
    )

    # 5. Re-apply the tactical-utility overlay so Phase 6 stays comparable to
    # Phase 4/5 — same multiplicative shift, anchor-relative. The attacker-
    # meta uplift from Phase 5 is *not* re-applied at Phase 6: it was a fix
    # for the column-weight scheme being unable to discriminate same-stat
    # different-faction units, but Phase 6's Nash weights already differ
    # per-unit (not per-faction), so the symptom doesn't recur.
    tv = np.array([tactical_value(u, weights) for u in units], dtype=float)
    log_factor = np.log1p(tv)
    log_factor = log_factor - log_factor[anchor_idx]
    x_phase6 = x_weighted + log_factor

    # Fallback: any unit whose weighted-solve totals collapsed to zero falls
    # back to the prior result's price (so we don't ship NaNs / anchor pins
    # for things the LP simply couldn't price).
    zero_mask = weight_totals <= 0
    if zero_mask.any():
        x_phase6[zero_mask] = prior_result.log_p[zero_mask]

    eq_per_model = np.exp(x_phase6)

    entries: List[EquilibriumEntry] = []
    prior_by_key = {e.key: e for e in prior_result.entries}
    for key, u, eq_pm in zip(prior_result.keys, units, eq_per_model):
        gw_per_squad = float(u.points_per_squad)
        gw_per_model = (
            gw_per_squad / max(1, u.min_models) if gw_per_squad > 0 else 0.0
        )
        eq_per_squad = eq_pm * max(1, u.min_models)
        if gw_per_model > 0:
            mispricing = (gw_per_model - eq_pm) / eq_pm * 100.0
        else:
            mispricing = 0.0
        # Carry the prior's valid_matchups count (it was computed on the same
        # T matrix and is unchanged by the reweighting).
        vc = prior_by_key[key].valid_matchups if key in prior_by_key else 0
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

    result = EquilibriumResult(
        entries=entries,
        keys=prior_result.keys,
        D=prior_result.D,
        T=prior_result.T,
        R=prior_result.R,
        log_p=x_phase6,
        anchor_key=anchor_key,
        anchor_per_model=anchor_per_model,
        phase=6,
    )

    return Phase6NashResult(
        result=result,
        nash_strategy=sigma,
        game_value=v,
        lp_ok=lp_ok,
        prior_result=prior_result,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_PHASE_METADATA: Dict[int, Tuple[str, str]] = {
    1: (
        "Phase 1 equilibrium-points solver output. log-LSQ on pairwise "
        "shooting-only time-to-kill. Pure-melee units excluded. See "
        "code/equilibrium.py for full method and TODO list of later phases.",
        "log-LSQ on pairwise shooting time-to-kill (row-mean closed form)",
    ),
    2: (
        "Phase 2 equilibrium-points solver output. log-LSQ on pairwise "
        "combined shoot+melee time-to-kill, with a per-attacker-role mix "
        "of shooting and melee damage. Pure-melee units re-enter the fit. "
        "See code/equilibrium.py for the role weights and TODO list.",
        "log-LSQ on pairwise combined shoot+melee time-to-kill "
        "(per-role attacker mix; row-mean closed form)",
    ),
    4: (
        "Phase 4 equilibrium-points solver output. Phase 2 combat solve "
        "with a tactical-utility overlay: per-unit log-points shifted by "
        "log(1 + tactical_value(u)) - log(1 + tactical_value(anchor)). The "
        "tactical term combines move, OC, range, deep-strike, scout, "
        "infiltrator, sticky-objective — calibrated by grid search on a "
        "held-out 'known fair' anchor set. See `TacticalWeights` docstring.",
        "Phase 2 combat solve + multiplicative tactical-utility overlay "
        "(anchor-relative log-shift)",
    ),
    5: (
        "Phase 5 equilibrium-points solver output. Phase 4 pipeline with the "
        "log-LSQ row-mean reweighted by per-defender meta-share — a unit's "
        "fair price now reflects how often each opponent actually shows up "
        "on the tournament table. Meta source: May 2026 warpfriends weekly "
        "aggregate (top-10 factions explicitly; residual mass split evenly "
        "across remaining catalogue factions). See `META_FACTION_SHARE` and "
        "`solve_log_points_weighted` in code/equilibrium.py.",
        "Phase 4 solve + meta-share-weighted log-LSQ (defender-column "
        "reweighting on R[i, j])",
    ),
    6: (
        "Phase 6 equilibrium-points solver output. Phase 5 T-matrix re-solved "
        "with column weights from the Nash mixed strategy of the symmetric "
        "zero-sum game M[i, j] = (T[j,i] - T[i,j]) / (T[i,j] + T[j,i]). The "
        "Nash sigma is the worst-case defender distribution — a unit's fair "
        "price is what it costs against that adversarial mix, plus the same "
        "tactical-utility overlay Phase 4 applies. LP solved via "
        "`scipy.optimize.linprog` (HiGHS). See `compute_phase6_nash` in "
        "code/equilibrium.py for the LP formulation.",
        "Phase 5 T matrix + Nash-mixed-strategy column-weighted log-LSQ "
        "(scipy.optimize.linprog) + tactical-utility overlay",
    ),
}


def write_json(entries: List[EquilibriumEntry], path: Path = EQUILIBRIUM_PATH,
               anchor_key: str = DEFAULT_ANCHOR_KEY,
               anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL,
               phase: int = 1) -> None:
    comment, method = _PHASE_METADATA.get(phase, _PHASE_METADATA[1])
    payload = {
        "_comment": comment,
        "phase": phase,
        "method": method,
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
# Phase 2 — DONE: combined shoot+melee matrix via `compute_phase2` /
#   `pairwise_combat_matrix`. Per-attacker `shoot_weight` defaults to a
#   coarse-role lookup (`DEFAULT_SHOOT_WEIGHT_BY_ROLE`); a sim-data fit is
#   left as a follow-up tuning task.
#
# Phase 3 — DONE: defensive audit. `compute_phase3_audit` (above) flags four
#   classes — high-FNP-low-wound, invuln-cliff, multiwound-elite, anchor-can't-
#   touch — plus spot-checks of the anchor against Plague Marines / Custodian
#   Guard / Wraithguard. Pure analysis: no rule changes, no MAE impact. Run
#   via `python -m code.equilibrium --phase 3`.
#
# Phase 4 — DONE: tactical-utility term. `compute_phase4` runs Phase 2 then
#   multiplicatively shifts every unit's log-points by `log(1 + tactical_value(u))`
#   relative to the anchor's baseline. `TacticalWeights` carries the
#   grid-search-calibrated defaults; see its docstring and `_calibrate_weights`
#   for the calibration procedure. Pure analysis — no simulator or rule-citation
#   impact.
#
# Phase 5 — DONE: meta-weighted matchup solve. `compute_phase5` runs Phase 4
#   then re-solves the closed-form log-LSQ with column weights from
#   `META_FACTION_SHARE` (May 2026 warpfriends weekly aggregate, top-10 share
#   table aligned with `scripts.evaluate_vs_meta`). Same tactical overlay
#   applied on top. Pure analysis — no simulator or rule-citation impact.
#
# Phase 6 — DONE: Nash equilibrium of the symmetric zero-sum game over the
#   trade-ratio payoff matrix M[i, j] = (T[j,i] - T[i,j]) / (T[i,j] + T[j,i]).
#   `compute_phase6_nash` runs Phase 5 first, builds M, solves the LP for the
#   row player's mixed strategy sigma via `scipy.optimize.linprog` (HiGHS),
#   then uses sigma as the column weight in the same closed-form weighted
#   LSQ Phase 5 uses (with a small uniform regulariser for stability). The
#   tactical-utility overlay is re-applied on top so Phase 6 prices stay
#   comparable to Phase 4/5. Game value v is reported but should be ~0 by
#   the symmetric-antisymmetric-game lemma.


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Equilibrium-points solver. --phase 1 = shooting only; "
                    "--phase 2 = combined shoot+melee; --phase 3 = Phase 2 "
                    "solve + defensive-audit report (no extra plotting); "
                    "--phase 4 = Phase 2 + tactical-utility overlay; "
                    "--phase 5 = Phase 4 + meta-share-weighted LSQ; "
                    "--phase 6 = Phase 5 T-matrix + Nash mixed-strategy "
                    "column weights (zero-sum LP)."
    )
    parser.add_argument("--phase", type=int, default=1, choices=(1, 2, 3, 4, 5, 6),
                        help="Which solver to run (default 1)")
    parser.add_argument("--calibrate", action="store_true",
                        help="(--phase 4 only) re-run weight grid search "
                             "instead of using the docstring defaults; "
                             "prints chosen weights and before/after RSS.")
    parser.add_argument("--faction", type=str, default=None,
                        help="Restrict to a single faction (e.g. 'Necrons')")
    parser.add_argument("--limit", type=int, default=None,
                        help="Truncate the catalogue (debugging only)")
    parser.add_argument("--anchor", type=str, default=DEFAULT_ANCHOR_KEY)
    parser.add_argument("--anchor-points", type=float, default=DEFAULT_ANCHOR_PER_MODEL)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output JSON path (defaults: phase 1 -> "
                             "equilibrium_points.json, phase 2 -> "
                             "equilibrium_points_phase2.json)")
    parser.add_argument("--plot-out", type=Path, default=None,
                        help="Output PNG path (phase-specific default)")
    args = parser.parse_args()

    if args.phase == 3:
        # Phase 3 is an audit pass that consumes a Phase 2 result; it produces
        # no JSON/plot of its own and writes nothing — pure stdout report.
        result = compute_phase2(
            anchor_key=args.anchor,
            anchor_per_model=args.anchor_points,
            faction=args.faction,
            limit=args.limit,
        )
        audit = compute_phase3_audit(result)
        print(f"\nPhase 3 defensive audit — anchor {audit.anchor_key} "
              f"(Phase 2 result over {len(result.keys)} units).")

        print(f"\nHigh-FNP low-wound class ({len(audit.high_fnp_units)} units, "
              f"top 20 by uplift):")
        for key, uplift in audit.high_fnp_units[:20]:
            print(f"  {uplift:>5.2f}x  {key}")

        print(f"\nInvuln-cliff class ({len(audit.invuln_cliff_units)} units, "
              f"top 20 by save):")
        for key, sv, inv in audit.invuln_cliff_units[:20]:
            print(f"  Sv {sv}+ / Inv {inv}+ (cliff = {sv - inv})  {key}")

        print(f"\nMulti-wound elite class ({len(audit.multiwound_elite_units)} "
              f"units, top 20 alphabetical):")
        for key in audit.multiwound_elite_units[:20]:
            u = UNIT_CATALOG[key]
            print(f"  T{u.toughness} W{u.health:.0f} Sv{u.save}+  {key}")

        print(f"\nSpot-checks vs anchor:")
        for sc in audit.spot_checks:
            if sc.get("defender_key") is None:
                print(f"  [skip] {sc.get('note', 'no defender')}")
                continue
            note = f"  ({sc['note']})" if "note" in sc else ""
            print(f"  {sc['attacker_key']} -> {sc['defender_key']}: "
                  f"T = {sc['T_value']}  defence-amp = "
                  f"{sc['expected_vs_naive_ratio']}x{note}")

        print(f"\nUnpriceable vs anchor (D < {_PHASE3_NEAR_ZERO_DAMAGE}/turn): "
              f"{len(audit.unpriceable_vs_anchor)} units")
        for key in audit.unpriceable_vs_anchor[:20]:
            print(f"  {key}")
        if len(audit.unpriceable_vs_anchor) > 20:
            print(f"  ... and {len(audit.unpriceable_vs_anchor) - 20} more")
        print()
    else:
        phase5_bundle: Optional[Phase5Result] = None
        phase6_bundle: Optional[Phase6NashResult] = None
        if args.phase == 6:
            out_path = args.out or EQUILIBRIUM_PHASE6_PATH
            plot_path = args.plot_out or EQUILIBRIUM_PHASE6_PLOT
            print("\nPhase 6: running Phase 4/5 first, then Nash mixed-strategy "
                  "re-solve on top.")
            phase5_bundle = compute_phase5(
                anchor_key=args.anchor,
                anchor_per_model=args.anchor_points,
                faction=args.faction,
                limit=args.limit,
            )
            phase6_bundle = compute_phase6_nash(
                anchor_key=args.anchor,
                anchor_per_model=args.anchor_points,
                faction=args.faction,
                limit=args.limit,
                prior_result=phase5_bundle.result,
            )
            result = phase6_bundle.result
        elif args.phase == 5:
            out_path = args.out or EQUILIBRIUM_PHASE5_PATH
            plot_path = args.plot_out or EQUILIBRIUM_PHASE5_PLOT
            print("\nPhase 5: running Phase 4 first (utility) then meta-weighted "
                  "re-solve on top.")
            phase5_bundle = compute_phase5(
                anchor_key=args.anchor,
                anchor_per_model=args.anchor_points,
                faction=args.faction,
                limit=args.limit,
            )
            result = phase5_bundle.result
        elif args.phase == 4:
            out_path = args.out or EQUILIBRIUM_PHASE4_PATH
            plot_path = args.plot_out or EQUILIBRIUM_PHASE4_PLOT
            weights = TacticalWeights()
            if args.calibrate:
                weights, rss_before, rss_after = _calibrate_weights()
                print(f"\nCalibrated weights (5-level grid search):")
                for f in (
                    "w_move", "w_oc", "w_range", "w_deep_strike",
                    "w_scout", "w_infiltrator", "w_sticky_objective",
                ):
                    print(f"  {f:20s} = {getattr(weights, f):.4f}")
                print(f"  RSS over {len(_CALIBRATION_ANCHORS)} anchors: "
                      f"{rss_before:.1f} -> {rss_after:.1f}")
            result = compute_phase4(
                anchor_key=args.anchor,
                anchor_per_model=args.anchor_points,
                faction=args.faction,
                limit=args.limit,
                weights=weights,
            )
        elif args.phase == 2:
            out_path = args.out or EQUILIBRIUM_PHASE2_PATH
            plot_path = args.plot_out or EQUILIBRIUM_PHASE2_PLOT
            result = compute_phase2(
                anchor_key=args.anchor,
                anchor_per_model=args.anchor_points,
                faction=args.faction,
                limit=args.limit,
            )
        else:
            out_path = args.out or EQUILIBRIUM_PATH
            plot_path = args.plot_out or EQUILIBRIUM_PLOT
            result = compute_phase1(
                anchor_key=args.anchor,
                anchor_per_model=args.anchor_points,
                faction=args.faction,
                limit=args.limit,
            )
        entries = result.entries
        write_json(entries, out_path, anchor_key=args.anchor,
                   anchor_per_model=args.anchor_points, phase=args.phase)
        if not args.no_plot:
            plot_scatter(entries, plot_path)

        # Print top mispricings
        sorted_entries = sorted(entries, key=lambda e: e.mispricing_pct)
        print(f"\nPhase {args.phase}: {len(entries)} units fitted. "
              f"Anchor: {args.anchor} @ {args.anchor_points} pts/model.")
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
        print(f"\nWrote {out_path}")
        if not args.no_plot:
            print(f"Wrote {plot_path}")

        if phase5_bundle is not None:
            # Show the biggest Phase 4 -> Phase 5 movers (by abs log-ratio).
            movers = sorted(
                phase5_bundle.comparison,
                key=lambda c: abs(math.log(c.ratio_phase5_over_phase4))
                if c.ratio_phase5_over_phase4 > 0 else 0.0,
                reverse=True,
            )
            print("\nTop 10 Phase 4 -> Phase 5 movers (per-model price ratio):")
            for c in movers[:10]:
                print(f"  ratio {c.ratio_phase5_over_phase4:>6.3f}  "
                      f"P4 {c.phase4_per_model:>5.1f} -> P5 {c.phase5_per_model:>5.1f}  "
                      f"w={c.meta_weight:.3f}  "
                      f"{c.name[:42]} ({c.faction[:18]})")
            # Faction-level price uplift summary: did high-meta-share factions
            # price up vs low-meta-share factions?
            from collections import defaultdict
            fac_ratios: Dict[str, List[float]] = defaultdict(list)
            for c in phase5_bundle.comparison:
                if c.ratio_phase5_over_phase4 > 0:
                    fac_ratios[c.faction].append(c.ratio_phase5_over_phase4)
            print("\nFaction-level mean Phase 5 / Phase 4 price ratio "
                  "(sorted by meta share, descending):")
            # Sort by explicit share when present (highest first), then by
            # faction name for the "default" tail. Using -1 as the sort key
            # for unmapped factions keeps them after every listed share, even
            # if the residual mass per faction is larger than the smallest
            # listed share (the residual gets split across many factions, so
            # the per-faction default weight is tiny).
            sorted_factions = sorted(
                fac_ratios.keys(),
                key=lambda f: (
                    phase5_bundle.share_table.get(f, -1.0), f,
                ),
                reverse=True,
            )
            for fac in sorted_factions[:15]:
                ratios = fac_ratios[fac]
                mean_r = sum(ratios) / len(ratios)
                share = phase5_bundle.share_table.get(fac, None)
                share_s = f"{share:.3f}" if share is not None else "(default)"
                print(f"  share={share_s:>9s}  ratio={mean_r:.3f}  "
                      f"({len(ratios)} units)  {fac}")

        if phase6_bundle is not None:
            sigma = phase6_bundle.nash_strategy
            print(f"\nPhase 6 Nash LP: lp_ok={phase6_bundle.lp_ok}, "
                  f"v={phase6_bundle.game_value:+.4f}, "
                  f"sigma support (>= 1e-4) = {int((sigma >= 1e-4).sum())}/{len(sigma)}.")
            # Top sigma weights — units the Nash strategy actually wants to play.
            keys = phase6_bundle.result.keys
            top_sigma = sorted(
                zip(keys, sigma), key=lambda kv: kv[1], reverse=True,
            )[:15]
            print("\nTop 15 units by Nash strategy weight (sigma):")
            for k, s in top_sigma:
                u = UNIT_CATALOG.get(k)
                name = u.name if u else k
                print(f"  sigma={s:.4f}  {name[:45]} ({u.faction[:18] if u else ''})")
            # Phase 5 -> Phase 6 movers.
            p5_by_key = {
                e.key: e.equilibrium_points_per_model
                for e in phase6_bundle.prior_result.entries
            }
            movers6: List[Tuple[str, float, float, float, str, str]] = []
            for e in phase6_bundle.result.entries:
                p5 = p5_by_key.get(e.key)
                if p5 is None or p5 <= 0 or e.equilibrium_points_per_model <= 0:
                    continue
                ratio = e.equilibrium_points_per_model / p5
                movers6.append(
                    (e.key, p5, e.equilibrium_points_per_model, ratio, e.name, e.faction)
                )
            movers6.sort(key=lambda r: abs(math.log(r[3])), reverse=True)
            print("\nTop 10 Phase 5 -> Phase 6 movers (per-model price ratio):")
            for _, p5, p6, r, name, fac in movers6[:10]:
                print(f"  ratio {r:>6.3f}  P5 {p5:>5.1f} -> P6 {p6:>5.1f}  "
                      f"{name[:42]} ({fac[:18]})")
