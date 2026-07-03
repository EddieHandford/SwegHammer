"""Going-first win rate broken down PER deployment map.

The aggregate going-first signature (`scripts/diag_signatures`, signature 2) rolls
the whole `PARIAH_NEXUS_2K_ROTATION` together, so a ~69% aggregate could be a
uniform tempo bias OR a few pathological deployment geometries (e.g. Search and
Destroy's opposing-corner land-grab) dragging up an otherwise-fine field. This
diagnostic forces each rotation map in turn and reports the going-first win rate
per map, so we can tell whether the over-reward is a global AI/tempo problem or a
per-deployment geometry artifact.

Reuses the exact first-player inference and aggregation from diag_signatures
(`_parse_event_log` + `_compute_signatures`), so the per-map numbers are
apples-to-apples with the aggregate signature.

    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_going_first_by_map --pairs 10 --seeds 6

Read-only diagnostic: no code changes, no gate, no eval-frame mutation.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_going_first_by_map"] + sys.argv[1:], os.environ)

from code.army_builder import build_faction_random_army  # noqa: E402
from code.events import EventLog  # noqa: E402
from code.maps import PARIAH_NEXUS_2K_ROTATION, STOCK_MAPS  # noqa: E402
from code.simulator import Battle  # noqa: E402
from scripts.diag_signatures import (  # noqa: E402
    MATCHUP_POOL,
    _compute_signatures,
    _parse_event_log,
)


def _run_for_map(map_key, matchups, seeds):
    records = []
    battle_map = STOCK_MAPS[map_key]
    for a_fac, b_fac in matchups:
        for seed in seeds:
            a = build_faction_random_army(
                "A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army(
                "B", b_fac, 2000, rng=random.Random(seed + 10_000), use_archetype=True)
            log = EventLog()
            result = Battle(a, b, subscribers=[log], map_=battle_map).run()
            records.append(_parse_event_log(log, result))
    return _compute_signatures(records)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Going-first win rate per Pariah Nexus deployment map.")
    p.add_argument("--pairs", type=int, default=10)
    p.add_argument("--seeds", type=int, default=6)
    args = p.parse_args()

    matchups = MATCHUP_POOL[: args.pairs]
    seeds = list(range(args.seeds))
    per_map = len(matchups) * len(seeds)
    print(f"Going-first by map — {per_map} games/map x {len(PARIAH_NEXUS_2K_ROTATION)} maps "
          f"({per_map * len(PARIAH_NEXUS_2K_ROTATION)} total). Real target 49-52%.")
    print(f"(PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED')})\n")

    all_records_gf = []
    rows = []
    for map_key in PARIAH_NEXUS_2K_ROTATION:
        sigs = _run_for_map(map_key, matchups, seeds)
        gf = sigs["going_first_win_rate"]
        n = sigs["going_first_sample_size"]
        rows.append((map_key, gf, n))
        gf_pct = f"{gf*100:5.1f}%" if gf is not None else "  n/a"
        print(f"  {map_key:22s}  going-first {gf_pct}  (n={n:3d} decisive)")

    print("\n" + "=" * 60)
    print("  SUMMARY (sorted by going-first win rate)")
    print("=" * 60)
    for map_key, gf, n in sorted(rows, key=lambda r: (r[1] is not None, r[1] or 0), reverse=True):
        gf_pct = f"{gf*100:5.1f}%" if gf is not None else "  n/a"
        print(f"  {gf_pct}  {map_key:22s} (n={n})")
    print("\n  Real going-first target: 49-52% (Chapter Approved 2025-26).")
    print("  A map far above ~55% is a per-deployment geometry contributor;")
    print("  a uniform ~69% across all maps points to a global tempo/AI cause.")


if __name__ == "__main__":
    main()
