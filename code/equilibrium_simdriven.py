"""
Sim-driven equilibrium points — full-battle measurement instead of closed-form.

The closed-form `compute_phase1` derives points from a pairwise damage matrix
computed purely from datasheet stats (S/T/AP/save/FNP and the stateless
shooting keywords). Every effect the simulator adds on top of that — army
rules, detachment passives, leader auras, charge math, OC contests on
objectives, terrain effects, fire-order heuristics — is invisible to it.

The sim-driven phase replaces the closed-form damage matrix with one MEASURED
from full simulator battles, so faction-rule work that ships in the simulator
(Awakened Dynasty, Death Guard Contagions, Marines Oath of Moment, leader
auras …) flows through to the equilibrium graph.

Mechanics
---------
Per ordered pair (i, j) of measured units, run `n_battles` full ``Battle()``
runs of all-i army vs all-j army at equal points budget (mirroring
``code/balancer.py::measure_win_rate``). The observed win rate r[i, j] feeds
the same log-LSQ solver Phase 1 uses, via Bradley-Terry:

    R[i, j] = logit(r[i, j]) = log(r / (1 - r))
    log p_i - log p_j  ~=  R[i, j]

This is structurally the same row-mean closed form as
``equilibrium.solve_log_points`` — only the way R is generated changes (sim,
not closed-form damage), and we skip the intermediate T = wounds/D step
because the sim's win rate already integrates over the full kill exchange.

Scope
-----
Wall-clock budget matters. At roughly 140 ms / battle on a desktop CPU, the
full N² ~ 600² shooting-fittable matrix at n_battles = 5 is multi-day. So
the default ``measured_keys`` is a diagnostic subset of ~30 anchors spanning
the role × faction grid (see ``DEFAULT_DIAGNOSTIC_KEYS``); units outside the
subset inherit their closed-form Phase 1 log-p value verbatim. ``--full``
measures every shooting-fittable unit (overnight cron territory). The CLI is
the only place the snapshot is written; the Streamlit equilibrium tab reads
the snapshot and falls back to closed-form when absent.

Snapshot
--------
``data/equilibrium_points_simdriven.json`` — same per-unit entry shape as the
other phase snapshots, plus a header recording anchor, points budget,
n_battles, the measured_keys list, and wall-clock cost. Regenerate via

    python -m code.equilibrium_simdriven                   # diagnostic subset
    python -m code.equilibrium_simdriven --full            # all fittable (slow)
    python -m code.equilibrium_simdriven --keys k1,k2,...  # custom subset
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .army_builder import build_homogeneous_army
from .equilibrium import (
    DEFAULT_ANCHOR_KEY,
    DEFAULT_ANCHOR_PER_MODEL,
    REPO_ROOT,
    _classify_role,
    compute_phase1,
)
from .maps import DEFAULT_MAP
from .simulator import Battle
from .units import UNIT_CATALOG, UnitProfile

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SIMDRIVEN_PATH = REPO_ROOT / "data" / "equilibrium_points_simdriven.json"

# Smaller than the balancer's 1000-pt budget. The sim cost scales roughly
# linearly with model count; 500 keeps a single battle in the ~100-200 ms
# range while still letting both sides field meaningful unit counts.
SIMDRIVEN_BUDGET_PTS: float = 500.0

# n_battles per ordered pair. Sample-size tradeoff:
#   k = 3  -> ~95% CI of about ±0.28 on a Wilson-corrected proportion, so
#             logit(r) is very noisy near r = 0.5. Fine for the diagonal of
#             a non-fitness-mattering-much pair, terrible for the borderline
#             ones we actually want to resolve.
#   k = 5  -> ±0.21. Default.
#   k = 10 -> ±0.15. Doubles wall-clock for a modest noise win.
SIMDRIVEN_DEFAULT_BATTLES: int = 5

# Logit clamp: a perfect 0-or-N sweep gives r = 0 or 1, whose logit is
# infinite. Pull r into [eps, 1-eps] before taking the log. eps = 1/(2k)
# (Bayesian-style additive smoothing for an unobserved trial each side) is
# the standard fix and produces a finite, conservative R when one direction
# of a matchup is a wipe.
LOGIT_EPSILON: float = 0.05   # finite floor — corresponds to k ~ 10


# Curated diagnostic anchors: one shooting-capable representative per faction
# per role tier, kept short enough that 30² × k=5 ~ 4 500 battles ≈ 10–15 min
# at the measured ~140 ms / battle. These are the keys most relevant to
# Goal A calibration (BATTLELINE backbones + a flagship elite shooter), so
# their sim-vs-closed-form delta is the highest-signal correction available
# without paying for the full catalogue. Sorted by faction for readability;
# order does not affect the solve.
DEFAULT_DIAGNOSTIC_KEYS: Tuple[str, ...] = (
    "space_marines_intercessor_squad",
    "space_marines_hellblaster_squad",
    "space_marines_devastator_squad",
    "necrons_necron_warriors",
    "necrons_immortals",
    "orks_boyz",
    "orks_lootas",
    "tyranids_termagants",
    "tyranids_hive_guard",
    "t_au_empire_strike_team",
    "t_au_empire_breacher_team",
    "t_au_empire_crisis_fireknife_battlesuits",
    "aeldari_craftworlds_guardian_defenders",
    "aeldari_craftworlds_dark_reapers",
    "death_guard_plague_marines",
    "death_guard_blightlord_terminators",
    "thousand_sons_rubric_marines",
    "thousand_sons_scarab_occult_terminators",
    "chaos_space_marines_legionaries",
    "chaos_space_marines_chaos_terminator_squad",
    "astra_militarum_cadian_shock_troops",
    "adeptus_custodes_custodian_guard",
    "adepta_sororitas_battle_sisters_squad",
    "leagues_of_votann_hearthkyn_warriors",
    "world_eaters_khorne_berzerkers",
    "adeptus_mechanicus_skitarii_vanguard",
    "genestealer_cults_neophyte_hybrids",
    "grey_knights_strike_squad",
)


# ---------------------------------------------------------------------------
# Per-unit row + bundle
# ---------------------------------------------------------------------------

@dataclass
class SimDrivenEntry:
    """One row in the sim-driven snapshot.

    Mirrors ``equilibrium.EquilibriumEntry`` plus a ``source`` flag so the UI
    can distinguish units whose log-p came out of the sim measurement from
    units that inherited their Phase 1 closed-form value.
    """
    key: str
    name: str
    faction: str
    gw_points_per_squad: float
    gw_points_per_model: float
    min_models: int
    equilibrium_points_per_model: float
    equilibrium_points_per_squad: float
    mispricing_pct: float
    valid_matchups: int
    role: str
    source: str   # "sim" — measured against the diagnostic set, or
                  # "phase1_fallback" — inherited from compute_phase1


@dataclass
class SimDrivenResult:
    entries: List[SimDrivenEntry]
    measured_keys: List[str]            # subset that got pairwise sim measurement
    n_battles_per_pair: int
    points_budget: float
    anchor_key: str
    anchor_per_model: float
    battles_run: int
    wall_clock_sec: float
    phase: str = "simdriven"


# ---------------------------------------------------------------------------
# Pair measurement
# ---------------------------------------------------------------------------

def _measure_pair_winrate(
    profile_i: UnitProfile,
    profile_j: UnitProfile,
    n_battles: int,
    points_budget: float,
    rng: random.Random,
) -> Tuple[float, int]:
    """Return ``(win_rate_of_i, settled_battle_count)``.

    ``settled_battle_count`` excludes degenerate matchups where neither side
    could field a model at the budget — those are skipped, not counted as
    draws. A return of ``(0.5, 0)`` means "no information; treat as
    balanced". This mirrors ``code/balancer.py::measure_win_rate`` so the
    sim semantics are identical (full detachment + stratagem + leader-aura
    machinery active in every measured battle).
    """
    a_wins = 0
    b_wins = 0
    settled = 0
    for _ in range(n_battles):
        a = build_homogeneous_army("A", profile_i, points_budget)
        b = build_homogeneous_army("B", profile_j, points_budget)
        if not a.units or not b.units:
            continue
        result = Battle(a, b, map_=DEFAULT_MAP).run()
        settled += 1
        if result.winner == "A":
            a_wins += 1
        elif result.winner == "B":
            b_wins += 1
    if settled == 0:
        return 0.5, 0
    decided = a_wins + b_wins
    if decided == 0:
        return 0.5, settled
    return a_wins / decided, settled


def _pair_job(
    args: Tuple[int, int, "UnitProfile", "UnitProfile", int, float, int],
) -> Tuple[int, int, float, int]:
    """Process-pool worker: measure win-rate for one unit pair.

    Must be a module-level function (not a closure) so ProcessPoolExecutor
    can pickle it across process boundaries on Windows. Args are all
    primitives or frozen dataclasses (picklable).

    Returns (i, j, r_ij, settled_battles).
    """
    i, j, profile_i, profile_j, n_battles, budget, seed = args
    rng = random.Random(seed)
    r_ij, settled = _measure_pair_winrate(profile_i, profile_j, n_battles, budget, rng)
    return i, j, r_ij, settled


def _logit_clamped(p: float, eps: float = LOGIT_EPSILON) -> float:
    """Logit with the input pulled into ``[eps, 1-eps]``.

    A sweep (r = 0 or 1) gives ±∞ otherwise, which would dominate the row
    mean. Clamping caps the per-pair contribution at ``±log((1-eps)/eps)`` —
    finite, conservative, and stable.
    """
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))


# ---------------------------------------------------------------------------
# Top-level solve
# ---------------------------------------------------------------------------

def compute_phase_simdriven(
    catalog: Optional[Dict[str, UnitProfile]] = None,
    anchor_key: str = DEFAULT_ANCHOR_KEY,
    anchor_per_model: float = DEFAULT_ANCHOR_PER_MODEL,
    measured_keys: Optional[List[str]] = None,
    n_battles: int = SIMDRIVEN_DEFAULT_BATTLES,
    points_budget: float = SIMDRIVEN_BUDGET_PTS,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    rng: Optional[random.Random] = None,
    max_workers: Optional[int] = None,
) -> SimDrivenResult:
    """Run the sim-driven equilibrium solve over ``measured_keys``.

    Units outside ``measured_keys`` inherit their Phase 1 closed-form log-p
    value verbatim and are tagged ``source="phase1_fallback"`` in the
    result, so the snapshot is always complete for the full fittable
    catalogue — the sim-driven phase only PERTURBS the subset it measured.

    ``progress_cb(done, total, message)`` is invoked once per outer-loop
    attacker so a CLI / Streamlit caller can render a progress bar without
    coupling to this module's loop shape.
    """
    if catalog is None:
        catalog = UNIT_CATALOG
    if rng is None:
        rng = random.Random()

    # Always anchor against the closed-form Phase 1 solve. Phase 1 fills in
    # log-p for the full fittable catalogue; the sim measurement perturbs
    # the subset it touches.
    phase1 = compute_phase1(
        catalog=catalog,
        anchor_key=anchor_key,
        anchor_per_model=anchor_per_model,
    )
    phase1_log_p_by_key: Dict[str, float] = {
        k: float(phase1.log_p[i]) for i, k in enumerate(phase1.keys)
    }

    if measured_keys is None:
        measured_keys = list(DEFAULT_DIAGNOSTIC_KEYS)

    # Filter to keys that actually exist in the catalogue, are shooting-
    # fittable, and have non-zero per-model GW pts. Anything else can't
    # be fielded by build_homogeneous_army at a fixed budget.
    valid_measured: List[str] = []
    for k in measured_keys:
        u = catalog.get(k)
        if u is None:
            continue
        if _classify_role(u) not in ("shooty", "dual"):
            continue
        if u.points_per_squad <= 0 or u.min_models <= 0:
            continue
        valid_measured.append(k)
    if anchor_key not in valid_measured:
        raise ValueError(
            f"Anchor unit {anchor_key!r} is not in the measured_keys set or is "
            f"not shooting-fittable. The anchor must be measured so its "
            f"log-p can pin the solve."
        )

    n = len(valid_measured)
    # R[i, j] holds logit(r_ij). Skew-symmetric on the valid mask.
    R = np.full((n, n), np.nan, dtype=float)
    valid_pair_count = np.zeros(n, dtype=int)

    t_start = time.time()
    battles_run = 0

    # Symmetric loop: measure (i, j) for i < j, infer R[j, i] = -R[i, j].
    if max_workers is not None and max_workers > 1:
        # Parallel path — distribute pair jobs across worker processes.
        # Each job is a tuple of picklable args; UnitProfile is a frozen
        # dataclass and is picklable on the Windows spawn start method.
        jobs = []
        for i in range(n):
            for j in range(i + 1, n):
                seed = i * 100_000 + j  # deterministic per pair
                jobs.append((
                    i, j,
                    catalog[valid_measured[i]],
                    catalog[valid_measured[j]],
                    n_battles, points_budget, seed,
                ))
        total_pairs = len(jobs)
        done = 0
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for res_i, res_j, r_ij, settled in executor.map(
                _pair_job, jobs, chunksize=8
            ):
                done += 1
                if settled == 0:
                    continue
                battles_run += settled
                r_logit = _logit_clamped(r_ij)
                R[res_i, res_j] = r_logit
                R[res_j, res_i] = -r_logit
                valid_pair_count[res_i] += 1
                valid_pair_count[res_j] += 1
                if progress_cb is not None:
                    progress_cb(done, total_pairs, valid_measured[res_i])
    else:
        # Serial path (original).
        for i, key_i in enumerate(valid_measured):
            u_i = catalog[key_i]
            for j in range(i + 1, n):
                key_j = valid_measured[j]
                u_j = catalog[key_j]
                r_ij, settled = _measure_pair_winrate(
                    u_i, u_j, n_battles, points_budget, rng,
                )
                battles_run += settled
                if settled == 0:
                    continue
                r_logit = _logit_clamped(r_ij)
                R[i, j] = r_logit
                R[j, i] = -r_logit
                valid_pair_count[i] += 1
                valid_pair_count[j] += 1
            if progress_cb is not None:
                progress_cb(i + 1, n, key_i)

    # Row-mean of R gives raw log-p (skew-symmetric → mean over valid
    # columns is the LSQ optimum, same closed form as solve_log_points).
    finite_mask = np.isfinite(R)
    counts = finite_mask.sum(axis=1)
    safe_counts = np.where(counts == 0, 1, counts)
    log_p_raw = np.where(finite_mask, R, 0.0).sum(axis=1) / safe_counts

    anchor_idx = valid_measured.index(anchor_key)
    anchor_log_p_target = math.log(anchor_per_model)
    shift = anchor_log_p_target - log_p_raw[anchor_idx]
    log_p_sim = log_p_raw + shift
    # Units with zero valid partners (shouldn't happen at n ≥ 2 but guard
    # anyway) fall back to the anchor's log-p so the entry is still
    # serialisable rather than producing nan / inf downstream.
    log_p_sim[counts == 0] = anchor_log_p_target

    sim_log_p_by_key: Dict[str, float] = {
        valid_measured[i]: float(log_p_sim[i]) for i in range(n)
    }
    sim_valid_matchups: Dict[str, int] = {
        valid_measured[i]: int(counts[i]) for i in range(n)
    }

    # Build entries for every fittable unit. Measured units get the sim
    # log-p; the rest inherit their Phase 1 value.
    entries: List[SimDrivenEntry] = []
    for i, key in enumerate(phase1.keys):
        u = catalog[key]
        if key in sim_log_p_by_key:
            log_p = sim_log_p_by_key[key]
            source = "sim"
            valid = sim_valid_matchups[key]
        else:
            log_p = phase1_log_p_by_key[key]
            source = "phase1_fallback"
            # Carry the Phase 1 valid-matchup count over verbatim so the
            # entry is comparable in the UI.
            valid = int(np.isfinite(phase1.T[i]).sum())

        eq_per_model = float(math.exp(log_p))
        eq_per_squad = eq_per_model * max(1, u.min_models)
        gw_per_squad = float(u.points_per_squad)
        gw_per_model = (
            gw_per_squad / max(1, u.min_models) if gw_per_squad > 0 else 0.0
        )
        mispricing = (
            (gw_per_model - eq_per_model) / eq_per_model * 100.0
            if gw_per_model > 0 else 0.0
        )
        entries.append(
            SimDrivenEntry(
                key=key,
                name=u.name,
                faction=u.faction,
                gw_points_per_squad=round(gw_per_squad, 2),
                gw_points_per_model=round(gw_per_model, 2),
                min_models=int(u.min_models),
                equilibrium_points_per_model=round(eq_per_model, 2),
                equilibrium_points_per_squad=round(eq_per_squad, 2),
                mispricing_pct=round(float(mispricing), 1),
                valid_matchups=valid,
                role=_classify_role(u),
                source=source,
            )
        )

    return SimDrivenResult(
        entries=entries,
        measured_keys=valid_measured,
        n_battles_per_pair=n_battles,
        points_budget=points_budget,
        anchor_key=anchor_key,
        anchor_per_model=anchor_per_model,
        battles_run=battles_run,
        wall_clock_sec=time.time() - t_start,
    )


# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------

def save_snapshot(result: SimDrivenResult, path: Path = SIMDRIVEN_PATH) -> None:
    """Write the result to ``path`` as JSON.

    Schema matches the other ``data/equilibrium_points_phase*.json`` files
    so the existing ``code/compare_view.py`` loader could pick it up with
    only a one-line registration if we later decide to surface sim-driven
    in the Compare tab alongside the closed-form phases.
    """
    payload = {
        "phase": "simdriven",
        "anchor_key": result.anchor_key,
        "anchor_per_model": result.anchor_per_model,
        "n_battles_per_pair": result.n_battles_per_pair,
        "points_budget": result.points_budget,
        "measured_keys": result.measured_keys,
        "battles_run": result.battles_run,
        "wall_clock_sec": round(result.wall_clock_sec, 1),
        "units": {e.key: asdict(e) for e in result.entries},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_snapshot(path: Path = SIMDRIVEN_PATH) -> Optional[Dict]:
    """Return the parsed JSON payload, or ``None`` if the snapshot is
    missing or unreadable. Used by the Streamlit equilibrium tab to decide
    whether to offer the sim-driven view at all."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_progress(done: int, total: int, key: str) -> None:
    pct = done * 100 // max(1, total)
    print(f"  [{done:>3}/{total}]  ({pct:>3}%)  done attacker {key}", flush=True)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the sim-driven equilibrium points snapshot.",
    )
    parser.add_argument(
        "--keys",
        type=str,
        default=None,
        help="Comma-separated list of catalogue keys to measure. "
             "Default: the curated diagnostic set (see DEFAULT_DIAGNOSTIC_KEYS).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Measure every shooting-fittable unit. Multi-hour, intended "
             "as an overnight cron build.",
    )
    parser.add_argument(
        "--battles",
        type=int,
        default=SIMDRIVEN_DEFAULT_BATTLES,
        help=f"Battles per ordered pair (default {SIMDRIVEN_DEFAULT_BATTLES}).",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=SIMDRIVEN_BUDGET_PTS,
        help=f"Points budget per army (default {SIMDRIVEN_BUDGET_PTS}).",
    )
    parser.add_argument(
        "--anchor",
        type=str,
        default=DEFAULT_ANCHOR_KEY,
        help=f"Anchor unit key (default {DEFAULT_ANCHOR_KEY}).",
    )
    parser.add_argument(
        "--anchor-pts",
        type=float,
        default=DEFAULT_ANCHOR_PER_MODEL,
        help=f"Anchor pts/model (default {DEFAULT_ANCHOR_PER_MODEL}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducibility (default: nondeterministic).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(SIMDRIVEN_PATH),
        help=f"Output snapshot path (default {SIMDRIVEN_PATH}).",
    )
    args = parser.parse_args(argv)

    if args.keys and args.full:
        parser.error("--keys and --full are mutually exclusive.")

    if args.full:
        measured_keys = sorted(
            k for k, u in UNIT_CATALOG.items()
            if _classify_role(u) in ("shooty", "dual")
            and u.points_per_squad > 0
            and u.min_models > 0
        )
    elif args.keys:
        measured_keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    else:
        measured_keys = list(DEFAULT_DIAGNOSTIC_KEYS)

    # Anchor must be in the measured set.
    if args.anchor not in measured_keys:
        measured_keys = [args.anchor] + measured_keys
        print(
            f"  (note) anchor {args.anchor} prepended to measured set",
            flush=True,
        )

    n_pairs = len(measured_keys) * (len(measured_keys) - 1) // 2
    estimated_battles = n_pairs * args.battles
    print(
        f"Sim-driven equilibrium: {len(measured_keys)} units, "
        f"{n_pairs} ordered pairs, ~{estimated_battles} battles "
        f"(approx {estimated_battles * 0.14:.0f} s at 140 ms/battle).",
        flush=True,
    )

    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    result = compute_phase_simdriven(
        catalog=UNIT_CATALOG,
        anchor_key=args.anchor,
        anchor_per_model=args.anchor_pts,
        measured_keys=measured_keys,
        n_battles=args.battles,
        points_budget=args.budget,
        progress_cb=_print_progress,
        rng=rng,
    )
    out_path = Path(args.out)
    save_snapshot(result, out_path)
    print(
        f"Wrote {out_path} — {result.battles_run} battles in "
        f"{result.wall_clock_sec:.1f} s "
        f"({result.wall_clock_sec * 1000 / max(1, result.battles_run):.1f} ms/battle).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
