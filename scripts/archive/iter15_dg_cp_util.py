"""Auto-loop iter 15 — DG CP utilisation diagnostic.

Runs N battles of Death Guard vs every other faction (round-robin) and tallies
stratagem firing frequency by round + total CP spent per battle, both globally
and split by stratagem name. Diagnoses whether DG's +6.7pt over-strength comes
from "every CP fires every round" CP-glut, or from a specific stratagem doing
too much per fire.

Read-only — no catalogue / strategy / simulator mutation. Default N=30 battles
per opponent matchup.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.iter15_dg_cp_util
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter15_dg_cp_util"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import RoundStarted, StratagemFired
from code.maps import DEFAULT_MAP
from code.simulator import Battle


# Opposing factions (DG plays one battle vs each, repeated N_BATTLES times).
OPPONENTS = [
    "Adeptus Astartes",
    "Necrons",
    "Aeldari",
    "Tyranids",
    "Orks",
    "T'au Empire",
    "Adeptus Custodes",
    "Thousand Sons",
    "Leagues of Votann",
]

N_BATTLES = 30   # per opponent
POINTS = 1000


class CPCounter:
    """Subscriber that tracks the active round + per-round stratagem firings
    for one army name. Plugged into Battle.subscribers per battle."""

    def __init__(self, army_name: str) -> None:
        self.army_name = army_name
        self.current_round = 0
        # round -> stratagem_name -> fire count
        self.fires_by_round: Dict[int, Counter] = defaultdict(Counter)
        self.total_cp_spent = 0
        # stratagem_name -> fire count across all rounds
        self.fires_total: Counter = Counter()

    def on_event(self, event: object) -> None:
        if isinstance(event, RoundStarted):
            self.current_round = event.round_num
        elif isinstance(event, StratagemFired):
            if event.army_name != self.army_name:
                return
            self.fires_by_round[self.current_round][event.stratagem_name] += 1
            self.fires_total[event.stratagem_name] += 1
            self.total_cp_spent += event.cp_cost


def main() -> None:
    print(f"Iter 15 — Death Guard CP utilisation diagnostic (N={N_BATTLES} per opponent)")
    print("=" * 78)

    # Aggregates across ALL opponents.
    all_cp_per_battle: List[int] = []
    all_fires_by_round: Dict[int, Counter] = defaultdict(Counter)
    all_fires_total: Counter = Counter()
    per_opp_cp_mean: Dict[str, float] = {}
    n_battles_played = 0

    for opp in OPPONENTS:
        cp_per_battle: List[int] = []
        for s in range(N_BATTLES):
            seed = 555000 + hash(opp) % 1000 + s
            rng_a = random.Random(seed)
            rng_b = random.Random(seed + 7919)
            army_a = build_faction_random_army("DG", "Death Guard", POINTS, rng=rng_a)
            army_b = build_faction_random_army("OPP", opp, POINTS, rng=rng_b)
            counter = CPCounter("DG")
            battle = Battle(army_a, army_b, subscribers=[counter], map_=DEFAULT_MAP)
            battle.run()
            cp_per_battle.append(counter.total_cp_spent)
            all_cp_per_battle.append(counter.total_cp_spent)
            for rnd, c in counter.fires_by_round.items():
                all_fires_by_round[rnd].update(c)
            all_fires_total.update(counter.fires_total)
            n_battles_played += 1
        mean_cp = statistics.mean(cp_per_battle) if cp_per_battle else 0.0
        per_opp_cp_mean[opp] = mean_cp
        print(f"  vs {opp:24s}: mean CP spent {mean_cp:5.2f}  "
              f"(min {min(cp_per_battle)}, max {max(cp_per_battle)})")

    print()
    print(f"Total DG battles sampled: {n_battles_played}")
    print(f"Global mean CP spent per battle: "
          f"{statistics.mean(all_cp_per_battle):.2f}  "
          f"(median {statistics.median(all_cp_per_battle):.1f}, "
          f"max {max(all_cp_per_battle)})")
    print()
    print("CP fired by ROUND (sum across all battles):")
    total_fires_across_rounds = sum(sum(c.values()) for c in all_fires_by_round.values())
    for rnd in sorted(all_fires_by_round.keys()):
        n = sum(all_fires_by_round[rnd].values())
        pct = 100.0 * n / max(1, total_fires_across_rounds)
        per_battle = n / max(1, n_battles_played)
        print(f"  Round {rnd}: {n:4d} fires  ({pct:4.1f}%)  "
              f"{per_battle:.2f} fires/battle")

    print()
    print("Total fires by stratagem (top 15):")
    for name, c in all_fires_total.most_common(15):
        per_battle = c / max(1, n_battles_played)
        print(f"  {name:40s}  {c:4d} fires  ({per_battle:.2f}/battle)")

    # Worldblight + DR are the iter-13 named suspects — call them out.
    print()
    print("Named suspects (per iter-13 DG diag):")
    for name in [
        "Disgustingly Resilient",
        "Putrid Detonation",
        "Plaguesurge",
        "Leechspore Eruption",
        "Overwhelming Generosity",
        "Creeping Blight",
    ]:
        c = all_fires_total.get(name, 0)
        per_battle = c / max(1, n_battles_played)
        print(f"  {name:40s}  {c:4d}  ({per_battle:.2f}/battle)")


if __name__ == "__main__":
    main()
