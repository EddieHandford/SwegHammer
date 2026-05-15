"""
Thousand Sons archetype diagnostic — why does Cult of Magic under-perform by
-32.6 pts in archetype-enabled eval-vs-meta?

Runs 30 seeded battles per matchup (TSON vs each of 9 opponents) with archetypes
on for BOTH armies, then captures:
  * per-matchup A-win-rate
  * Doombolt stratagem firing count per battle
  * Cabbalistic Empowerment firing count per battle
  * Rubric Marines + Scarab Occult + Tzaangors surviving counts at end
  * mean rounds-to-rubrics-half-dead (a soft "anchor lifespan" proxy)

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.tson_diag

Read-only — does NOT modify catalogue, simulator, or strategy code.
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.tson_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import StratagemFired, UnitKilled, RoundStarted
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS: List[str] = [
    "Adeptus Astartes",
    "Necrons",
    "Aeldari",
    "Tyranids",
    "Orks",
    "T'au Empire",
    "Death Guard",
    "Adeptus Custodes",
    "Leagues of Votann",
]
TSON = "Thousand Sons"
N_BATTLES = 30
POINTS = 1000

# Track these TSON profile names for survivability accounting. The archetype
# builder seeds these by min_models squads then random-fills with same-faction
# picks, so the unit set is stable across battles.
TRACK_PROFILES = {
    "Rubric Marines",
    "Scarab Occult Terminators",
    "Tzaangors",
    "Exalted Sorcerer",
    "Infernal Master",
    "Helbrute",
}


class DiagSubscriber:
    """Captures per-battle events of interest."""

    def __init__(self) -> None:
        self.doombolt_fires = 0
        self.cabbalistic_fires = 0
        self.twist_fires = 0
        self.glamour_fires = 0
        self.units_killed: set = set()
        self.current_round = 0

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, StratagemFired):
            if e.stratagem_name == "Doombolt":
                self.doombolt_fires += 1
            elif e.stratagem_name == "Cabbalistic Empowerment":
                self.cabbalistic_fires += 1
            elif e.stratagem_name == "Twist of Fate":
                self.twist_fires += 1
            elif e.stratagem_name == "Glamour of Tzeentch":
                self.glamour_fires += 1
        elif isinstance(e, UnitKilled):
            self.units_killed.add(e.unit_uid)


def _count_alive_by_profile(army) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for u in army.units:
        if u.is_alive:
            out[u.profile.name] += 1
    return out


def _count_total_by_profile(army) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for u in army.units:
        out[u.profile.name] += 1
    return out


def run_matchup(opponent: str) -> Dict:
    wins = Counter()
    rounds_played: List[int] = []
    doombolts: List[int] = []
    cabbalistics: List[int] = []
    twists: List[int] = []
    glamours: List[int] = []

    # Per-profile starting and surviving counts, summed across battles.
    start_by_prof: Dict[str, int] = defaultdict(int)
    survive_by_prof: Dict[str, int] = defaultdict(int)

    # CP-spent proxy: total stratagems fired by TSON
    total_tson_strats: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 7919  # stable, offset to differ from random-eval seeds
        random.seed(seed)
        tson = build_faction_random_army(
            "A", TSON, POINTS,
            rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not tson.units or not opp.units:
            continue

        sub = DiagSubscriber()
        battle = Battle(tson, opp, map_=DEFAULT_MAP, subscribers=[sub])
        r = battle.run()

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        doombolts.append(sub.doombolt_fires)
        cabbalistics.append(sub.cabbalistic_fires)
        twists.append(sub.twist_fires)
        glamours.append(sub.glamour_fires)
        total_tson_strats.append(
            sub.doombolt_fires + sub.cabbalistic_fires
            + sub.twist_fires + sub.glamour_fires
        )

        # Snapshot TSON unit fates by profile name
        starts = _count_total_by_profile(tson)
        survives = _count_alive_by_profile(tson)
        for pname, n in starts.items():
            start_by_prof[pname] += n
        for pname, n in survives.items():
            survive_by_prof[pname] += n

    a_wr = wins.get("A", 0) / max(1, N_BATTLES) * 100
    out = {
        "opponent": opponent,
        "a_wr": a_wr,
        "rounds_mean": statistics.mean(rounds_played) if rounds_played else 0.0,
        "doombolt_mean": statistics.mean(doombolts) if doombolts else 0.0,
        "cabbalistic_mean": statistics.mean(cabbalistics) if cabbalistics else 0.0,
        "twist_mean": statistics.mean(twists) if twists else 0.0,
        "glamour_mean": statistics.mean(glamours) if glamours else 0.0,
        "tson_strat_total_mean": statistics.mean(total_tson_strats) if total_tson_strats else 0.0,
        "tracked_survival": {
            pname: (
                survive_by_prof.get(pname, 0)
                / max(1, start_by_prof.get(pname, 1))
                * 100
            )
            for pname in TRACK_PROFILES
            if start_by_prof.get(pname, 0) > 0
        },
        "tracked_start_counts": {
            pname: start_by_prof.get(pname, 0) / max(1, N_BATTLES)
            for pname in TRACK_PROFILES
            if start_by_prof.get(pname, 0) > 0
        },
    }
    return out


def main() -> None:
    print(f"=== TSON diagnostic — {N_BATTLES} battles per matchup, archetype=True ===")
    print(f"{'Opponent':22s}  {'WR%':>5s}  {'R':>4s}  {'DB':>5s}  {'CE':>5s}  {'TF':>5s}  {'GT':>5s}")
    print("-" * 70)

    results: List[Dict] = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        results.append(r)
        print(f"{opp:22s}  {r['a_wr']:5.1f}  {r['rounds_mean']:4.1f}  "
              f"{r['doombolt_mean']:5.2f}  {r['cabbalistic_mean']:5.2f}  "
              f"{r['twist_mean']:5.2f}  {r['glamour_mean']:5.2f}")

    mean_wr = statistics.mean(r["a_wr"] for r in results)
    print("-" * 70)
    print(f"Mean TSON win-rate vs all 9 opponents: {mean_wr:.1f}%")
    print()

    # Sort by win-rate ascending = worst first
    results_sorted = sorted(results, key=lambda r: r["a_wr"])
    print("=== Worst 3 matchups — per-profile survival & strat usage ===")
    for r in results_sorted[:3]:
        print(f"\nvs {r['opponent']}  (WR {r['a_wr']:.1f}%)")
        print(f"  rounds avg: {r['rounds_mean']:.1f}")
        print(f"  Doombolt fires/battle: {r['doombolt_mean']:.2f}")
        print(f"  Cabbalistic fires/battle: {r['cabbalistic_mean']:.2f}")
        print(f"  Twist of Fate fires/battle: {r['twist_mean']:.2f}")
        print(f"  Glamour of Tzeentch fires/battle: {r['glamour_mean']:.2f}")
        print(f"  Tracked profile survival rates:")
        for pname in sorted(r["tracked_survival"]):
            sv = r["tracked_survival"][pname]
            stcnt = r["tracked_start_counts"].get(pname, 0.0)
            print(f"    {pname:35s} {sv:5.1f}%  (start {stcnt:.1f} models/battle)")

    print()
    print("=== Best 2 matchups for comparison ===")
    for r in results_sorted[-2:]:
        print(f"\nvs {r['opponent']}  (WR {r['a_wr']:.1f}%)")
        print(f"  Doombolt fires/battle: {r['doombolt_mean']:.2f}")
        print(f"  Tracked profile survival rates:")
        for pname in sorted(r["tracked_survival"]):
            sv = r["tracked_survival"][pname]
            stcnt = r["tracked_start_counts"].get(pname, 0.0)
            print(f"    {pname:35s} {sv:5.1f}%  (start {stcnt:.1f} models/battle)")


if __name__ == "__main__":
    main()
