"""
Round-robin tournament runner.

Simulates every 1v1 matchup within a faction (or all factions) and stores
results in data/tournament_results.json as a persistent lookup table.

Usage
-----
# Run one faction:
    python -m scripts.run_tournament --faction Necrons

# Run all factions (long — hours for large ones like Adeptus Astartes):
    python -m scripts.run_tournament --all

# Re-run only missing pairs (safe to interrupt and resume):
    python -m scripts.run_tournament --faction Necrons --skip-done

Options
-------
--faction FACTION   Faction name to run (exact match, case-sensitive)
--all               Run every faction sequentially
--sims N            Simulations per matchup (default 100)
--skip-done         Skip pairs already in the results file
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running as `python -m scripts.run_tournament` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from code.army_builder import build_army_from_list
from code.maps import DEFAULT_MAP
from code.simulator import Battle
from code.tournament import (
    load_results,
    missing_pairs,
    record_matchup,
    save_results,
)
from code.units import UNIT_CATALOG


def _faction_keys(faction: str):
    return sorted(k for k, v in UNIT_CATALOG.items() if v.faction == faction)


def run_matchup(key_a: str, key_b: str, n_sims: int):
    name_a = UNIT_CATALOG[key_a].name
    name_b = UNIT_CATALOG[key_b].name
    wins_a = wins_b = draws = 0
    for _ in range(n_sims):
        army_a = build_army_from_list(name_a, [key_a])
        army_b = build_army_from_list(name_b, [key_b])
        result = Battle(army_a, army_b, map_=DEFAULT_MAP).run()
        if result.winner == name_a:
            wins_a += 1
        elif result.winner == name_b:
            wins_b += 1
        else:
            draws += 1
    return wins_a, wins_b, draws


def run_faction(faction: str, n_sims: int, skip_done: bool, results: dict) -> int:
    keys = _faction_keys(faction)
    if not keys:
        print(f"  No units found for faction '{faction}'. Check spelling.")
        return 0

    if skip_done:
        pairs = missing_pairs(results, keys)
    else:
        import itertools
        pairs = list(itertools.combinations(sorted(keys), 2))

    total = len(pairs)
    if total == 0:
        print(f"  {faction}: all {len(keys)} units already fully covered — nothing to do.")
        return 0

    print(f"\n{'='*60}")
    print(f"  {faction}: {len(keys)} units, {total} matchups × {n_sims} sims")
    print(f"{'='*60}")

    t0 = time.time()
    for i, (key_a, key_b) in enumerate(pairs, 1):
        name_a = UNIT_CATALOG[key_a].name
        name_b = UNIT_CATALOG[key_b].name
        wins_a, wins_b, draws = run_matchup(key_a, key_b, n_sims)
        record_matchup(results, key_a, key_b, wins_a, wins_b, draws, n_sims)

        elapsed = time.time() - t0
        rate = i / elapsed
        eta = (total - i) / rate if rate > 0 else 0
        pct = wins_a / n_sims * 100
        print(
            f"  [{i:>4}/{total}] {name_a[:22]:<22} vs {name_b[:22]:<22} "
            f"→ {wins_a}W/{wins_b}L/{draws}D ({pct:.0f}%)  "
            f"ETA {eta/60:.1f}min"
        )

        # Save every 50 matchups so a crash loses at most 50 results
        if i % 50 == 0:
            save_results(results)
            print(f"  [checkpoint saved]")

    save_results(results)
    elapsed_total = time.time() - t0
    print(f"\n  {faction} done in {elapsed_total/60:.1f} min. Results saved.")
    return total


def main():
    parser = argparse.ArgumentParser(description="SwegHammer round-robin tournament runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--faction", metavar="FACTION", help="Run one faction")
    group.add_argument("--all", action="store_true", help="Run all factions")
    parser.add_argument("--sims", type=int, default=100, metavar="N",
                        help="Simulations per matchup (default 100)")
    parser.add_argument("--skip-done", action="store_true",
                        help="Skip matchups already in the results file")
    args = parser.parse_args()

    results = load_results()
    existing = len(results)
    print(f"Loaded {existing} existing matchup(s) from lookup table.")

    if args.all:
        factions = sorted({v.faction for v in UNIT_CATALOG.values() if v.faction})
        total_run = 0
        for faction in factions:
            total_run += run_faction(faction, args.sims, args.skip_done, results)
        print(f"\nAll done. {total_run} matchup(s) computed across {len(factions)} factions.")
    else:
        run_faction(args.faction, args.sims, args.skip_done, results)


if __name__ == "__main__":
    main()
