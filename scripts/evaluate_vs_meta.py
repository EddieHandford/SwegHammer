"""
Run a faction-vs-faction matchup matrix and report the simulator's per-faction
win rate next to known tournament win rates. The mean absolute error (MAE)
between sim and tournament is the headline number we drive down each
iteration of the calibration loop (#91).

Usage:
    python -m scripts.evaluate_vs_meta              # N=20 per pairing (~2 min)
    python -m scripts.evaluate_vs_meta --battles 40  # tighter signal
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

# Lock Python's hash randomisation off so set() / dict-of-string iteration
# order is reproducible across runs — without this the sim's internal sets
# (advance/battleshock/fresh-arrival trackers) shuffle and the MAE drifts
# by ~3 pts between back-to-back invocations.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.evaluate_vs_meta"] + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army
from code.maps import DEFAULT_MAP, PARIAH_NEXUS_2K_ROTATION, STOCK_MAPS
from code.simulator import Battle, RulesConfig

FACTIONS: List[str] = [
    "Adeptus Astartes",
    "Necrons",
    "Aeldari",
    "Tyranids",
    "Orks",
    "T'au Empire",
    "Death Guard",
    "Adeptus Custodes",
    "Thousand Sons",
    "Leagues of Votann",
    # FX-ALL — extended coverage to all major-codex factions so the matchup
    # matrix can surface outliers that the 10-faction subset was missing.
    # Templates live in `code/archetypes.py` per FX-ALL commit.
    "Chaos Space Marines",
    "World Eaters",
    "Emperor's Children",
    "Chaos Daemons",
    "Astra Militarum",
    "Adeptus Mechanicus",
    "Adepta Sororitas",
    "Grey Knights",
    "Drukhari",
    "Genestealer Cults",
    "Imperial Knights",
    "Chaos Knights",
]

# Warp Friends cumulative dataslate aggregate, May 11 2026, sourced from
# Bestcoastpairings. All 22 entries are real measured win rates.
# "Adeptus Astartes" maps to the Warp Friends "Space Marines" codex row.
# "Adepta Sororitas" maps to the Warp Friends "Sisters of Battle" row.
TOURNAMENT_TARGET: Dict[str, float] = {
    "Adeptus Astartes": 47.6,
    "Necrons":          53.2,
    "Aeldari":          44.4,
    "Tyranids":         47.4,
    "Orks":             44.9,
    "T'au Empire":      54.5,
    "Death Guard":      46.1,
    "Adeptus Custodes": 52.1,
    "Thousand Sons":    54.6,
    "Leagues of Votann": 49.3,
    "Chaos Space Marines": 52.8,
    "World Eaters":        47.0,
    "Emperor's Children":  47.9,
    "Chaos Daemons":       50.8,
    "Astra Militarum":     45.1,
    "Adeptus Mechanicus":  43.8,
    "Adepta Sororitas":    50.4,
    "Grey Knights":        47.9,
    "Drukhari":            49.3,
    "Genestealer Cults":   47.4,
    "Imperial Knights":    48.5,
    "Chaos Knights":       47.5,
}
APPROX_FACTIONS: set = set()  # all factions now have real Warp Friends May 2026 data

# FX_ALL_FACTIONS — the 12 extended-coverage factions added after the initial
# 10-faction subset. All now have real Warp Friends May 2026 win-rate data.
# Still excluded from the headline MAE (10-faction anchor) for historical
# continuity; included in the all-22 MAE reference figure instead.
FX_ALL_FACTIONS: frozenset = frozenset(FACTIONS[10:])


# FX-MS — multi-source tournament-target comparison. Calibrating against a
# single source (Warp Friends weekly aggregate) bakes in that tournament
# pool's meta snapshot. Real-meta data from independent aggregators agrees
# within roughly 2-3pts per faction; high cross-source variance signals
# a meta-volatile faction (recent codex/dataslate, contentious balance
# state) where our sim doesn't need to land exactly on one source — just
# inside the cross-source band.
#
# Sources (May 2026 snapshot):
#   * warp_friends_may_2026 — Bestcoastpairings cumulative aggregate,
#     May 11 2026 dataslate; real measured win rates for all 22 factions
#   * goonhammer_q2_2026, stat_check_may_2026, meta_monday_may_2026 — real
#     data for the original 5 non-approx factions; set equal to warp_friends
#     for all others until independent source data is obtained (zero stdev
#     signals "single confirmed source", not "multi-source agreement")
TOURNAMENT_SOURCES: Dict[str, Dict[str, float]] = {
    "Adeptus Astartes":   {"warp_friends_may_2026": 47.6, "goonhammer_q2_2026": 47.6,
                           "stat_check_may_2026":   47.6, "meta_monday_may_2026": 47.6},
    "Necrons":            {"warp_friends_may_2026": 53.2, "goonhammer_q2_2026": 52.8,
                           "stat_check_may_2026":   53.5, "meta_monday_may_2026": 53.0},
    "Aeldari":            {"warp_friends_may_2026": 44.4, "goonhammer_q2_2026": 45.5,
                           "stat_check_may_2026":   44.0, "meta_monday_may_2026": 44.8},
    "Tyranids":           {"warp_friends_may_2026": 47.4, "goonhammer_q2_2026": 47.4,
                           "stat_check_may_2026":   47.4, "meta_monday_may_2026": 47.4},
    "Orks":               {"warp_friends_may_2026": 44.9, "goonhammer_q2_2026": 45.8,
                           "stat_check_may_2026":   44.5, "meta_monday_may_2026": 45.0},
    "T'au Empire":        {"warp_friends_may_2026": 54.5, "goonhammer_q2_2026": 53.0,
                           "stat_check_may_2026":   54.0, "meta_monday_may_2026": 54.0},
    "Death Guard":        {"warp_friends_may_2026": 46.1, "goonhammer_q2_2026": 46.1,
                           "stat_check_may_2026":   46.1, "meta_monday_may_2026": 46.1},
    "Adeptus Custodes":   {"warp_friends_may_2026": 52.1, "goonhammer_q2_2026": 52.1,
                           "stat_check_may_2026":   52.1, "meta_monday_may_2026": 52.1},
    "Thousand Sons":      {"warp_friends_may_2026": 54.6, "goonhammer_q2_2026": 53.5,
                           "stat_check_may_2026":   54.0, "meta_monday_may_2026": 54.2},
    "Leagues of Votann":  {"warp_friends_may_2026": 49.3, "goonhammer_q2_2026": 49.3,
                           "stat_check_may_2026":   49.3, "meta_monday_may_2026": 49.3},
    "Chaos Space Marines": {"warp_friends_may_2026": 52.8, "goonhammer_q2_2026": 52.8,
                            "stat_check_may_2026":   52.8, "meta_monday_may_2026": 52.8},
    "World Eaters":        {"warp_friends_may_2026": 47.0, "goonhammer_q2_2026": 47.0,
                            "stat_check_may_2026":   47.0, "meta_monday_may_2026": 47.0},
    "Emperor's Children":  {"warp_friends_may_2026": 47.9, "goonhammer_q2_2026": 47.9,
                            "stat_check_may_2026":   47.9, "meta_monday_may_2026": 47.9},
    "Chaos Daemons":       {"warp_friends_may_2026": 50.8, "goonhammer_q2_2026": 50.8,
                            "stat_check_may_2026":   50.8, "meta_monday_may_2026": 50.8},
    "Astra Militarum":     {"warp_friends_may_2026": 45.1, "goonhammer_q2_2026": 45.1,
                            "stat_check_may_2026":   45.1, "meta_monday_may_2026": 45.1},
    "Adeptus Mechanicus":  {"warp_friends_may_2026": 43.8, "goonhammer_q2_2026": 43.8,
                            "stat_check_may_2026":   43.8, "meta_monday_may_2026": 43.8},
    "Adepta Sororitas":    {"warp_friends_may_2026": 50.4, "goonhammer_q2_2026": 50.4,
                            "stat_check_may_2026":   50.4, "meta_monday_may_2026": 50.4},
    "Grey Knights":        {"warp_friends_may_2026": 47.9, "goonhammer_q2_2026": 47.9,
                            "stat_check_may_2026":   47.9, "meta_monday_may_2026": 47.9},
    "Drukhari":            {"warp_friends_may_2026": 49.3, "goonhammer_q2_2026": 49.3,
                            "stat_check_may_2026":   49.3, "meta_monday_may_2026": 49.3},
    "Genestealer Cults":   {"warp_friends_may_2026": 47.4, "goonhammer_q2_2026": 47.4,
                            "stat_check_may_2026":   47.4, "meta_monday_may_2026": 47.4},
    "Imperial Knights":    {"warp_friends_may_2026": 48.5, "goonhammer_q2_2026": 48.5,
                            "stat_check_may_2026":   48.5, "meta_monday_may_2026": 48.5},
    "Chaos Knights":       {"warp_friends_may_2026": 47.5, "goonhammer_q2_2026": 47.5,
                            "stat_check_may_2026":   47.5, "meta_monday_may_2026": 47.5},
}


def _source_stats(faction: str) -> Tuple[float, float, float]:
    """Return (mean, median, stdev) of tournament-source values for faction.

    Used by the FX-MS multi-source report. Stdev signals how meta-volatile
    a faction is across the source pool: high stdev = real-meta is itself
    unsettled for that faction, so our sim doesn't need to land exactly on
    one source — anywhere inside the band is acceptable.
    """
    values = list(TOURNAMENT_SOURCES[faction].values())
    return (
        statistics.mean(values),
        statistics.median(values),
        statistics.pstdev(values) if len(values) > 1 else 0.0,
    )


def _pick_rotation_map(seed: int):
    """Deterministic map rotation for the per-pair seed schedule.

    SC4-D: real tournament play rotates through the Pariah Nexus mission
    pack (Crucible of Battle, Take and Hold, Hammer and Anvil, Tipping
    Point, Search and Destroy). The previous calibration used a single
    fixed map (DEFAULT_MAP = COMBAT_PATROL_BASIC), which systematically
    biased the win-rate matrix toward the one deployment shape that
    happened to fit that map's geometry. Rotating across the 5 Pariah
    Nexus shapes averages out the per-map bias.

    Deterministic by seed so PYTHONHASHSEED=0 invocations reproduce
    identical matrices across runs.
    """
    rotation = PARIAH_NEXUS_2K_ROTATION
    key = rotation[seed % len(rotation)]
    return STOCK_MAPS[key]


def _run_battle_job(
    args: Tuple[str, str, int, int, Optional[RulesConfig], bool, Optional[Dict[str, float]]],
) -> Tuple[str, str, int, Optional[str]]:
    """Worker: build armies + run one battle for (a_fac, b_fac, seed).

    Performs the entire build-and-run inside the worker process. We pass
    only primitive args (faction names, seed, rules config) so the job is
    trivially picklable; Battle / Army / Unit themselves contain back-
    references that pickle poorly, so they're never sent across the
    process boundary — built inside the worker and discarded.

    The `random.seed(pair_seed)` call must be made INSIDE the worker
    process so the global random module is seeded in each worker before
    army building (random.seed is process-local).

    Returns (a_fac, b_fac, seed, winner) where winner is "A"/"B"/None.
    None indicates the pairing was skipped (empty army on either side).
    """
    a_fac, b_fac, s, pair_seed, rules, use_archetype, price_overrides = args
    random.seed(pair_seed)
    a = build_faction_random_army(
        "A", a_fac, 2000, rng=random.Random(s), use_archetype=use_archetype,
        price_overrides=price_overrides,
    )
    b = build_faction_random_army(
        "B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=use_archetype,
        price_overrides=price_overrides,
    )
    if not a.units or not b.units:
        return (a_fac, b_fac, s, None)
    battle_map = _pick_rotation_map(s)
    r = Battle(a, b, map_=battle_map, rules=rules).run()
    return (a_fac, b_fac, s, r.winner)


def run_matrix(n: int, rules: RulesConfig = None, use_archetype: bool = False,
               max_workers: Optional[int] = None,
               price_overrides: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Average win-rate per faction across all opponents in the FACTIONS list.

    Seeds the global random module per battle so the same code base produces
    the same matrix across re-runs — otherwise the simulator's dice noise
    swamps small calibration changes. The seed schedule is deterministic
    (faction-name hash + battle index) and stable across runs.

    If `use_archetype=True`, lists are built via the curated tournament-
    realistic archetype templates (Marines Gladius, Necrons Awakened
    Dynasty, etc.) instead of the random_fill pool. Useful for measuring
    how tournament-shaped lists fare under the current rule set.

    Parallelism: distributes (a_fac, b_fac, seed) battle jobs across a
    ProcessPoolExecutor. Each job is deterministic in its `pair_seed`,
    so winners are identical to the serial implementation regardless of
    job-completion order. Defaults to `os.cpu_count() - 1` workers
    (leaves one core for the OS / parent). With 22 factions × 21
    opponents × N seeds = 462·N jobs, parallelism gives ~4-8x speedup on
    multi-core hardware. PYTHONHASHSEED=0 is set at module import time
    above; workers inherit the env via the os.execvpe re-exec, so set
    iteration order is reproducible inside workers too.
    """
    fac_idx = {f: i for i, f in enumerate(FACTIONS)}

    # Build the full job list upfront so the executor can stream them.
    jobs: List[Tuple[str, str, int, int, Optional[RulesConfig], bool]] = []
    for a_fac in FACTIONS:
        for b_fac in FACTIONS:
            if a_fac == b_fac:
                continue
            for s in range(n):
                ai, bi = fac_idx[a_fac], fac_idx[b_fac]
                pair_seed = (ai * 1000 + bi) * 100 + s
                jobs.append((a_fac, b_fac, s, pair_seed, rules, use_archetype, price_overrides))

    # Aggregate winners per (a_fac, b_fac) pair. Job-completion order does
    # not affect the per-pair Counter because each pair_seed is unique.
    pair_winners: Dict[Tuple[str, str], Counter] = {}
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 2) - 1)

    if max_workers <= 1:
        # Serial fallback — useful for debugging / reproducibility checks
        # without the multiprocessing layer in the way.
        results_iter = map(_run_battle_job, jobs)
    else:
        executor = ProcessPoolExecutor(max_workers=max_workers)
        # chunksize tuned to keep IPC overhead small relative to per-battle
        # cost (~0.5-3s each). For ~9000 jobs / 8 workers, ~50 keeps
        # workers busy without front-loading the queue.
        results_iter = executor.map(_run_battle_job, jobs, chunksize=8)

    try:
        for a_fac, b_fac, _s, winner in results_iter:
            key = (a_fac, b_fac)
            if key not in pair_winners:
                pair_winners[key] = Counter()
            if winner is not None:
                pair_winners[key][winner] += 1
    finally:
        if max_workers > 1:
            executor.shutdown(wait=True)

    sim_wr: Dict[Tuple[str, str], float] = {}
    for a_fac in FACTIONS:
        for b_fac in FACTIONS:
            if a_fac == b_fac:
                continue
            winners = pair_winners.get((a_fac, b_fac), Counter())
            sim_wr[(a_fac, b_fac)] = winners.get("A", 0) / n * 100

    out: Dict[str, float] = {}
    for fac in FACTIONS:
        rates = [v for (a, _), v in sim_wr.items() if a == fac]
        out[fac] = sum(rates) / len(rates)
    return out


def report(sim: Dict[str, float]) -> Tuple[float, float]:
    """Print the sim-vs-real table and return (mae_real, mae_sweg).

    Returns a dual headline:
      * `mae_real` — MAE between simulator and the real-meta tournament
        target. This is the calibration-against-GW signal that adding
        more faction rules can move.
      * `mae_sweg` — MAE between simulator and 50% across all factions.
        This is the Sweg-balanced target: a perfectly balanced rule set
        produces 50/50 cross-faction win rates. SwegHammer's "minimal
        rule changes" (alternating activation, CP-for-fewer-units) drift
        from real 10e by design, so `mae_real` has a structural floor that
        `mae_sweg` does not. Once the Sweg-balancer settles, `mae_sweg`
        should converge to ~0 while `mae_real` plateaus at the design
        floor.
    """
    print(f"{'Faction':22s}  {'Sim%':>6s}  {'Real%':>6s}  {'Diff':>6s}  {'vs50':>6s}")
    print("-" * 55)
    diffs_real = []       # anchored: 10 data factions only
    diffs_sweg = []       # anchored: 10 data factions only
    diffs_real_all = []   # all 22 factions
    diffs_sweg_all = []   # all 22 factions
    for fac in FACTIONS:
        target = TOURNAMENT_TARGET[fac]
        diff_real = sim[fac] - target
        diff_sweg = sim[fac] - 50.0
        marker = "" if fac not in APPROX_FACTIONS else " (~)"
        print(f"{fac:22s}  {sim[fac]:6.1f}  {target:6.1f}  "
              f"{diff_real:+6.1f}  {diff_sweg:+6.1f}{marker}")
        diffs_real_all.append(abs(diff_real))
        diffs_sweg_all.append(abs(diff_sweg))
        if fac not in FX_ALL_FACTIONS:
            diffs_real.append(abs(diff_real))
            diffs_sweg.append(abs(diff_sweg))
    mae_real = statistics.mean(diffs_real)
    mae_sweg = statistics.mean(diffs_sweg)
    mae_real_all = statistics.mean(diffs_real_all)
    mae_sweg_all = statistics.mean(diffs_sweg_all)
    print("-" * 55)
    print(f"MAE vs real meta (10 data factions): {mae_real:6.2f} pts  "
          f"(target ≤ 2.0; calibration anchor)")
    print(f"MAE vs real meta (all 22 factions):  {mae_real_all:6.2f} pts  "
          f"(reference only — 12 targets are estimates)")
    print(f"MAE vs Sweg-balanced (10 factions):  {mae_sweg:6.2f} pts  "
          f"(target ≤ 2.0; rule-internal-balance signal — 50/50 across factions)")

    # FX-MS — multi-source diagnostics. Show MAE against each source +
    # cross-source variance per faction. Identifies meta-volatile factions
    # (high stdev) vs meta-stable factions (low stdev).
    print()
    print("FX-MS multi-source diagnostic")
    print("-" * 75)
    print(f"{'Faction':22s}  {'Sim%':>6s}  {'Mean':>6s}  {'Med':>6s}  "
          f"{'σ':>5s}  {'Δmean':>6s}  {'Δmed':>6s}")
    print("-" * 75)
    diffs_mean: List[float] = []
    diffs_median: List[float] = []
    sources_seen = set()
    per_source_diffs: Dict[str, List[float]] = {}
    for fac in FACTIONS:
        sources_seen.update(TOURNAMENT_SOURCES[fac].keys())
    for src in sorted(sources_seen):
        per_source_diffs[src] = []
    for fac in FACTIONS:
        mean_t, median_t, stdev_t = _source_stats(fac)
        d_mean = sim[fac] - mean_t
        d_median = sim[fac] - median_t
        diffs_mean.append(abs(d_mean))
        diffs_median.append(abs(d_median))
        print(f"{fac:22s}  {sim[fac]:6.1f}  {mean_t:6.1f}  {median_t:6.1f}  "
              f"{stdev_t:5.2f}  {d_mean:+6.1f}  {d_median:+6.1f}")
        for src, val in TOURNAMENT_SOURCES[fac].items():
            per_source_diffs[src].append(abs(sim[fac] - val))
    print("-" * 75)
    mae_mean = statistics.mean(diffs_mean)
    mae_median = statistics.mean(diffs_median)
    print(f"MAE vs source mean:   {mae_mean:6.2f} pts")
    print(f"MAE vs source median: {mae_median:6.2f} pts")
    print()
    print(f"Per-source MAE (which source the sim aligns best to):")
    for src in sorted(per_source_diffs.keys()):
        per_mae = statistics.mean(per_source_diffs[src])
        print(f"  {src:30s}  {per_mae:6.2f} pts")
    return mae_real, mae_sweg, mae_real_all, mae_sweg_all


def save_snapshot(
    sim: Dict[str, float],
    mae_real: float,
    mae_sweg: float,
    mae_real_all: float,
    mae_sweg_all: float,
    n_battles: int,
    mode: str,
    list_mode: str,
    path: str,
    trusted_factions: Optional[List[str]] = None,
) -> None:
    """Write the faction win-rate matrix result to a JSON snapshot file.

    The snapshot is read by the Calibration tab in app.py to display the
    per-faction sim-vs-tournament comparison without re-running the matrix.
    """
    import datetime
    faction_rows = []
    for fac in FACTIONS:
        target = TOURNAMENT_TARGET[fac]
        sim_pct = sim[fac]
        sources = TOURNAMENT_SOURCES.get(fac, {})
        faction_rows.append({
            "faction": fac,
            "sim_pct": round(sim_pct, 2),
            "tournament_pct": target,
            "is_approx": fac in APPROX_FACTIONS,
            "is_no_data": fac in FX_ALL_FACTIONS,
            "diff": round(sim_pct - target, 2),
            "diff_vs_50": round(sim_pct - 50.0, 2),
            "tournament_sources": {k: round(v, 1) for k, v in sources.items()},
        })
    payload = {
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "n_battles": n_battles,
        "mode": mode,
        "list_mode": list_mode,
        "mae_real": round(mae_real, 2),          # anchored: 10 data factions
        "mae_sweg": round(mae_sweg, 2),          # anchored: 10 data factions
        "mae_real_all": round(mae_real_all, 2),  # reference: all 22 factions
        "mae_sweg_all": round(mae_sweg_all, 2),  # reference: all 22 factions
        "factions": faction_rows,
    }
    if trusted_factions is not None:
        payload["trusted_factions"] = trusted_factions
    import pathlib
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        __import__("json").dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Snapshot written → {out}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--battles", type=int, default=20)
    p.add_argument(
        "--sweghammer",
        action="store_true",
        help="Run under SwegHammer rules (alternating activations, "
             "simultaneous-movement sub-phase, CP catch-up bonus, "
             "coordinated army-plan). Default is vanilla WH40k 10e.",
    )
    p.add_argument(
        "--use-archetype",
        action="store_true",
        help="Build tournament-realistic curated lists (Gladius, Awakened "
             "Dynasty, etc.) instead of random_fill. Useful for measuring "
             "how tourney-shaped lists fare under the current rule set.",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes for the battle matrix. Default is "
             "os.cpu_count() - 1 (leaves one core for OS / parent). Pass 1 "
             "to force the serial code path (debugging / reproducibility).",
    )
    p.add_argument(
        "--out",
        type=str,
        default=None,
        help="If given, write a JSON snapshot of results to this path. "
             "The snapshot is consumed by the Calibration tab in app.py.",
    )
    p.add_argument(
        "--equation-prices",
        type=str,
        default=None,
        help="Path to equation_calibrated_points.json. When set, armies are "
             "built using equation-derived prices instead of GW prices. "
             "Use with --out to produce a hypothetical win-rate snapshot.",
    )
    p.add_argument(
        "--swegpoints",
        action="store_true",
        help="Build armies using the v1.0 SwegHammer points dataset at "
             "data/sweg_points_v1.json (regenerate with "
             "`python3 scripts/bake_swegpoints_v1.py`). Convenience "
             "wrapper over --equation-prices for the canonical v1 release.",
    )
    args = p.parse_args()
    rules = RulesConfig.sweghammer() if args.sweghammer else None
    mode = "sweghammer" if args.sweghammer else "vanilla"
    list_mode = "tourney-archetype" if args.use_archetype else "random_fill"
    workers = args.workers if args.workers is not None else max(1, (os.cpu_count() or 2) - 1)

    price_overrides: Optional[Dict[str, float]] = None
    if args.swegpoints and args.equation_prices:
        raise SystemExit("Pass either --swegpoints or --equation-prices, not both.")
    if args.swegpoints:
        from code.sweg_points import load_sweg_overrides, SWEG_POINTS_V1_PATH
        price_overrides = load_sweg_overrides()
        print(
            f"Using SwegHammer v1 points from {SWEG_POINTS_V1_PATH.name} "
            f"({len(price_overrides)} units priced).\n"
        )
    if args.equation_prices:
        import pathlib as _pl
        eq_path = _pl.Path(args.equation_prices)
        if not eq_path.exists():
            raise FileNotFoundError(
                f"Equation prices file not found: {eq_path}\n"
                "Run first: python -m scripts.fit_equation_calibrated"
            )
        eq_data = __import__("json").loads(eq_path.read_text(encoding="utf-8"))
        price_overrides = eq_data["prices"]
        print(
            f"Using equation prices from {eq_path} "
            f"(threshold {eq_data.get('threshold', '?')} pts, "
            f"trusted factions: {', '.join(eq_data.get('trusted_factions', []))})\n"
        )

    print(f"Mode: {'SwegHammer' if args.sweghammer else 'vanilla WH40k 10e'} | "
          f"Lists: {list_mode} | N={args.battles} | workers={workers}\n")
    sim = run_matrix(args.battles, rules=rules, use_archetype=args.use_archetype,
                     max_workers=workers, price_overrides=price_overrides)
    mae_real, mae_sweg, mae_real_all, mae_sweg_all = report(sim)
    if args.out:
        trusted = eq_data.get("trusted_factions") if args.equation_prices else None
        save_snapshot(sim, mae_real, mae_sweg, mae_real_all, mae_sweg_all,
                      args.battles, mode, list_mode, args.out,
                      trusted_factions=trusted)
    sys.exit(0)   # informational only — never error-exit


if __name__ == "__main__":
    main()
