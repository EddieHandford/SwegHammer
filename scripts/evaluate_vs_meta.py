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
import json
import os
import random
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
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

# Real tournament target: loaded from data/warpfriends_rolling.json — a
# game-weighted 4-week rolling aggregate scraped from warpfriends.wordpress.com
# (which hand-scrapes Best Coast Pairings). Replaces the prior mix of 10 hard
# Warp Friends numbers + 12 hand-curated midpoint approximations. Regenerate
# with `python -m scripts.scrape_warpfriends`.
#
# Each faction also carries a `noise_floor` — the larger of (week-to-week
# population stdev, binomial 95% CI half-width on the aggregate sample). It's
# the lower bound on MAE per faction: a sim landing inside its noise floor is
# inside sampling variance and shouldn't be chased further.
_WARPFRIENDS_PATH = Path(__file__).resolve().parent.parent / "data" / "warpfriends_rolling.json"
with open(_WARPFRIENDS_PATH, "r", encoding="utf-8") as _wf_f:
    _WF_DATA = json.load(_wf_f)

# Fail loud per CLAUDE.md §13: every faction in FACTIONS must appear in the
# rolling-aggregate JSON. A missing faction here means the scraper or the
# rollup map fell out of sync with the simulator's faction list, and we want
# the import to crash rather than silently substitute a default win rate.
_MISSING = [f for f in FACTIONS if f not in _WF_DATA["factions"]]
if _MISSING:
    raise KeyError(
        f"warpfriends_rolling.json is missing factions: {_MISSING}. "
        f"Re-run `python -m scripts.scrape_warpfriends` or update the rollup map."
    )

TOURNAMENT_TARGET: Dict[str, float] = {
    fac: _WF_DATA["factions"][fac]["win_rate"] for fac in FACTIONS
}
NOISE_FLOOR: Dict[str, float] = {
    fac: _WF_DATA["factions"][fac]["noise_floor"] for fac in FACTIONS
}
TOURNAMENT_GAMES: Dict[str, int] = {
    fac: _WF_DATA["factions"][fac]["total_games"] for fac in FACTIONS
}
# Retained as empty sets for backwards compat with downstream consumers
# (app.py Calibration tab, scripts/fit_equation_calibrated.py). Under the
# Warp Friends rolling aggregate every faction has real data, so the
# "approximate" and "no-data" categories are now empty.
APPROX_FACTIONS: set = set()
FX_ALL_FACTIONS: frozenset = frozenset()


# Retained for backwards compat with any external script importing the
# dict, but no longer the primary signal. The hand-curated multi-source
# data here is a stale May 2026 snapshot where the 12 approximate factions
# had identical values across all four sources. The real cross-sample
# variance signal now lives in NOISE_FLOOR (week-to-week rolling stdev
# of independent weekly tournament samples from the Warp Friends scrape).
TOURNAMENT_SOURCES: Dict[str, Dict[str, float]] = {
    "Adeptus Astartes":   {"warp_friends_may_2026": 48.0, "goonhammer_q2_2026": 48.5,
                           "stat_check_may_2026":   48.0, "meta_monday_may_2026": 48.2},
    "Necrons":            {"warp_friends_may_2026": 53.2, "goonhammer_q2_2026": 52.8,
                           "stat_check_may_2026":   53.5, "meta_monday_may_2026": 53.0},
    "Aeldari":            {"warp_friends_may_2026": 44.4, "goonhammer_q2_2026": 45.5,
                           "stat_check_may_2026":   44.0, "meta_monday_may_2026": 44.8},
    "Tyranids":           {"warp_friends_may_2026": 48.0, "goonhammer_q2_2026": 49.0,
                           "stat_check_may_2026":   48.5, "meta_monday_may_2026": 48.2},
    "Orks":               {"warp_friends_may_2026": 44.9, "goonhammer_q2_2026": 45.8,
                           "stat_check_may_2026":   44.5, "meta_monday_may_2026": 45.0},
    "T'au Empire":        {"warp_friends_may_2026": 54.5, "goonhammer_q2_2026": 53.0,
                           "stat_check_may_2026":   54.0, "meta_monday_may_2026": 54.0},
    "Death Guard":        {"warp_friends_may_2026": 48.0, "goonhammer_q2_2026": 49.0,
                           "stat_check_may_2026":   48.0, "meta_monday_may_2026": 48.5},
    "Adeptus Custodes":   {"warp_friends_may_2026": 48.0, "goonhammer_q2_2026": 49.5,
                           "stat_check_may_2026":   48.0, "meta_monday_may_2026": 49.0},
    "Thousand Sons":      {"warp_friends_may_2026": 54.6, "goonhammer_q2_2026": 53.5,
                           "stat_check_may_2026":   54.0, "meta_monday_may_2026": 54.2},
    "Leagues of Votann":  {"warp_friends_may_2026": 46.0, "goonhammer_q2_2026": 46.5,
                           "stat_check_may_2026":   46.0, "meta_monday_may_2026": 46.2},
    # FX-ALL approximations — no cross-source signal (same value across
    # all sources). Hand-curated meta-midpoint guesses; replace with
    # real per-source data when scraping is wired.
    "Chaos Space Marines": {"warp_friends_may_2026": 46.0, "goonhammer_q2_2026": 46.0,
                            "stat_check_may_2026":   46.0, "meta_monday_may_2026": 46.0},
    "World Eaters":        {"warp_friends_may_2026": 50.0, "goonhammer_q2_2026": 50.0,
                            "stat_check_may_2026":   50.0, "meta_monday_may_2026": 50.0},
    "Emperor's Children":  {"warp_friends_may_2026": 48.0, "goonhammer_q2_2026": 48.0,
                            "stat_check_may_2026":   48.0, "meta_monday_may_2026": 48.0},
    "Chaos Daemons":       {"warp_friends_may_2026": 47.0, "goonhammer_q2_2026": 47.0,
                            "stat_check_may_2026":   47.0, "meta_monday_may_2026": 47.0},
    "Astra Militarum":     {"warp_friends_may_2026": 47.0, "goonhammer_q2_2026": 47.0,
                            "stat_check_may_2026":   47.0, "meta_monday_may_2026": 47.0},
    "Adeptus Mechanicus":  {"warp_friends_may_2026": 45.0, "goonhammer_q2_2026": 45.0,
                            "stat_check_may_2026":   45.0, "meta_monday_may_2026": 45.0},
    "Adepta Sororitas":    {"warp_friends_may_2026": 49.0, "goonhammer_q2_2026": 49.0,
                            "stat_check_may_2026":   49.0, "meta_monday_may_2026": 49.0},
    "Grey Knights":        {"warp_friends_may_2026": 47.0, "goonhammer_q2_2026": 47.0,
                            "stat_check_may_2026":   47.0, "meta_monday_may_2026": 47.0},
    "Drukhari":            {"warp_friends_may_2026": 51.0, "goonhammer_q2_2026": 51.0,
                            "stat_check_may_2026":   51.0, "meta_monday_may_2026": 51.0},
    "Genestealer Cults":   {"warp_friends_may_2026": 46.0, "goonhammer_q2_2026": 46.0,
                            "stat_check_may_2026":   46.0, "meta_monday_may_2026": 46.0},
    "Imperial Knights":    {"warp_friends_may_2026": 46.0, "goonhammer_q2_2026": 46.0,
                            "stat_check_may_2026":   46.0, "meta_monday_may_2026": 46.0},
    "Chaos Knights":       {"warp_friends_may_2026": 45.0, "goonhammer_q2_2026": 45.0,
                            "stat_check_may_2026":   45.0, "meta_monday_may_2026": 45.0},
}


def _noise_gated_error(sim_wr: float, target: float, noise: float) -> float:
    """Return the portion of |sim - target| that exceeds the noise floor.

    Inside the noise band the gated error is zero — the simulator is within
    sampling variance of the real-meta tournament aggregate, and chasing it
    further is chasing noise rather than rule fidelity. Outside the band, the
    gated error is the overshoot (always non-negative).

    The headline calibration metric becomes "mean(gated_error) across
    factions" — directly answering "by how many points is the sim outside
    its measurable signal envelope?" rather than the raw "by how many points
    does the sim differ from a point estimate?".
    """
    return max(0.0, abs(sim_wr - target) - noise)


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


def report(sim: Dict[str, float]) -> Tuple[float, float, float]:
    """Print the sim-vs-real table and return (mae_raw, mae_gated, mae_sweg).

    Three headline numbers:
      * `mae_raw` — mean |sim - target| across factions. The classic signal;
        useful for trend tracking but doesn't account for the fact that
        real-meta numbers carry their own sampling and week-to-week
        variance.
      * `mae_gated` — mean(max(0, |sim - target| - noise_floor)) across
        factions. Per-faction error is only counted to the extent it
        exceeds the noise floor (the larger of week-to-week stdev and
        binomial 95% CI half-width on the WF aggregate sample). This is
        the calibration metric that actually matters: a faction sitting
        inside its noise band contributes zero, because chasing it
        further is chasing sampling variance.
      * `mae_sweg` — mean |sim - 50.0|. The Sweg-balanced target: a
        perfectly internally-balanced rule set yields 50/50 cross-faction
        win rates. Independent of the real-meta target.

    Inside-noise-band factions are marked with a trailing dot in the table.
    """
    print(f"{'Faction':22s}  {'Sim%':>6s}  {'Real%':>6s}  {'Noise':>6s}  "
          f"{'Diff':>6s}  {'Gated':>6s}  {'vs50':>6s}")
    print("-" * 72)
    diffs_raw = []
    diffs_gated = []
    diffs_sweg = []
    inside_band = 0
    for fac in FACTIONS:
        target = TOURNAMENT_TARGET[fac]
        noise = NOISE_FLOOR[fac]
        diff_real = sim[fac] - target
        gated = _noise_gated_error(sim[fac], target, noise)
        diff_sweg = sim[fac] - 50.0
        in_band = gated == 0.0
        if in_band:
            inside_band += 1
        marker = " ." if in_band else "  "
        print(f"{fac:22s}  {sim[fac]:6.1f}  {target:6.1f}  {noise:6.2f}  "
              f"{diff_real:+6.1f}  {gated:6.2f}  {diff_sweg:+6.1f}{marker}")
        diffs_raw.append(abs(diff_real))
        diffs_gated.append(gated)
        diffs_sweg.append(abs(diff_sweg))
    mae_raw = statistics.mean(diffs_raw)
    mae_gated = statistics.mean(diffs_gated)
    mae_sweg = statistics.mean(diffs_sweg)
    print("-" * 72)
    print(f"MAE raw (sim - real_meta):       {mae_raw:6.2f} pts  "
          f"(legacy headline)")
    print(f"MAE gated (only beyond noise):   {mae_gated:6.2f} pts  "
          f"(target → 0; the real calibration signal)")
    print(f"MAE vs Sweg-balanced (50/50):    {mae_sweg:6.2f} pts  "
          f"(rule-internal-balance signal)")
    print(f"Factions inside noise band:      {inside_band}/{len(FACTIONS)}  "
          f"(target → all 22)")
    return mae_raw, mae_gated, mae_sweg


def save_snapshot(
    sim: Dict[str, float],
    mae_raw: float,
    mae_gated: float,
    mae_sweg: float,
    n_battles: int,
    mode: str,
    list_mode: str,
    path: str,
    trusted_factions: Optional[List[str]] = None,
) -> None:
    """Write the faction win-rate matrix result to a JSON snapshot file.

    The snapshot is read by the Calibration tab in app.py to display the
    per-faction sim-vs-tournament comparison without re-running the matrix.
    Snapshot fields surface the noise floor + gated error so the UI can
    show inside-band vs outside-band status without recomputing.

    Legacy `mae_real` / `mae_real_all` / `mae_sweg_all` fields are written
    equal to the corresponding raw/sweg values for backwards compat with
    consumers that haven't been updated to the noise-gated headline.
    """
    import datetime
    faction_rows = []
    for fac in FACTIONS:
        target = TOURNAMENT_TARGET[fac]
        sim_pct = sim[fac]
        noise = NOISE_FLOOR[fac]
        gated = _noise_gated_error(sim_pct, target, noise)
        faction_rows.append({
            "faction": fac,
            "sim_pct": round(sim_pct, 2),
            "tournament_pct": round(target, 2),
            "noise_floor": round(noise, 2),
            "diff": round(sim_pct - target, 2),
            "gated_error": round(gated, 2),
            "inside_noise_band": gated == 0.0,
            "tournament_games": TOURNAMENT_GAMES[fac],
            "is_approx": False,
            "is_no_data": False,
        })
    payload = {
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "n_battles": n_battles,
        "mode": mode,
        "list_mode": list_mode,
        "mae_raw": round(mae_raw, 2),
        "mae_gated": round(mae_gated, 2),
        "mae_sweg": round(mae_sweg, 2),
        # Legacy aliases retained for backwards compat with consumers that
        # still expect the old 4-MAE shape (e.g. app.py Calibration tab).
        "mae_real": round(mae_raw, 2),
        "mae_real_all": round(mae_raw, 2),
        "mae_sweg_all": round(mae_sweg, 2),
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
    args = p.parse_args()
    rules = RulesConfig.sweghammer() if args.sweghammer else None
    mode = "sweghammer" if args.sweghammer else "vanilla"
    list_mode = "tourney-archetype" if args.use_archetype else "random_fill"
    workers = args.workers if args.workers is not None else max(1, (os.cpu_count() or 2) - 1)

    price_overrides: Optional[Dict[str, float]] = None
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
    mae_raw, mae_gated, mae_sweg = report(sim)
    if args.out:
        trusted = eq_data.get("trusted_factions") if args.equation_prices else None
        save_snapshot(sim, mae_raw, mae_gated, mae_sweg,
                      args.battles, mode, list_mode, args.out,
                      trusted_factions=trusted)
    sys.exit(0)   # informational only — never error-exit


if __name__ == "__main__":
    main()
