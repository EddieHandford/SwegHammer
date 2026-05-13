"""
Calibration suite — runs batches of battles and reports win rates.

Usage:
    python -m code.calibration [--battles N] [--points P] [--seed S]
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .army import Army
from .army_builder import build_homogeneous_army, build_random_army
from .simulator import Battle, BattleResult
from .units import UNIT_CATALOG, UnitProfile


# ---------------------------------------------------------------------------
# Aggregated result
# ---------------------------------------------------------------------------

@dataclass
class MatchupReport:
    a_name: str
    b_name: str
    battles: int
    a_wins: int = 0
    b_wins: int = 0
    draws: int = 0
    total_rounds: int = 0
    a_total_survivors: int = 0
    b_total_survivors: int = 0

    @property
    def a_win_rate(self) -> float:
        return self.a_wins / self.battles if self.battles else 0.0

    @property
    def b_win_rate(self) -> float:
        return self.b_wins / self.battles if self.battles else 0.0

    @property
    def draw_rate(self) -> float:
        return self.draws / self.battles if self.battles else 0.0

    @property
    def avg_rounds(self) -> float:
        return self.total_rounds / self.battles if self.battles else 0.0

    @property
    def avg_a_survivors(self) -> float:
        return self.a_total_survivors / self.battles if self.battles else 0.0

    @property
    def avg_b_survivors(self) -> float:
        return self.b_total_survivors / self.battles if self.battles else 0.0

    def record(self, result: BattleResult) -> None:
        if result.winner == self.a_name:
            self.a_wins += 1
        elif result.winner == self.b_name:
            self.b_wins += 1
        else:
            self.draws += 1
        self.total_rounds += result.rounds
        self.a_total_survivors += result.a_survivors
        self.b_total_survivors += result.b_survivors

    def __str__(self) -> str:
        balance_flag = ""
        if abs(self.a_win_rate - 0.5) > 0.05:
            balance_flag = "  ⚠ IMBALANCED"
        return (
            f"  {self.a_name:<26} vs {self.b_name:<26}\n"
            f"    {self.a_name} wins:  {self.a_wins:>5} ({self.a_win_rate:>5.1%})\n"
            f"    {self.b_name} wins:  {self.b_wins:>5} ({self.b_win_rate:>5.1%})\n"
            f"    Draws:              {self.draws:>5} ({self.draw_rate:>5.1%})\n"
            f"    Avg rounds:         {self.avg_rounds:>7.1f}\n"
            f"    Avg survivors:      {self.avg_a_survivors:.1f} / {self.avg_b_survivors:.1f}"
            f"{balance_flag}"
        )


# ---------------------------------------------------------------------------
# Batch runner helpers
# ---------------------------------------------------------------------------

ArmyFactory = Callable[[str], Army]


def run_matchup(
    factory_a: ArmyFactory,
    factory_b: ArmyFactory,
    n_battles: int,
    rng: random.Random,
) -> MatchupReport:
    """Run n_battles between two armies produced by factory functions."""
    # Build one army for naming purposes
    sample_a = factory_a("A")
    sample_b = factory_b("B")
    report = MatchupReport(
        a_name=sample_a.name,
        b_name=sample_b.name,
        battles=n_battles,
    )
    for _ in range(n_battles):
        army_a = factory_a(sample_a.name)
        army_b = factory_b(sample_b.name)
        result = Battle(army_a, army_b).run()
        report.record(result)
    return report


# ---------------------------------------------------------------------------
# Calibration suites
# ---------------------------------------------------------------------------

def suite_homogeneous(
    points: float,
    n_battles: int,
    rng: random.Random,
) -> List[MatchupReport]:
    """
    Pit each unit type against the baseline Space Marine in homogeneous armies
    (all units of a single type) at equal points.
    """
    baseline_profile = UNIT_CATALOG["space_marine"]
    reports: List[MatchupReport] = []

    for key, profile in sorted(UNIT_CATALOG.items()):
        if key == "space_marine":
            continue

        def make_marines(name: str, p: UnitProfile = baseline_profile) -> Army:
            return build_homogeneous_army(name, p, points)

        def make_challenger(name: str, p: UnitProfile = profile) -> Army:
            return build_homogeneous_army(name, p, points)

        report = run_matchup(
            lambda name: make_marines(f"Marines ({points:.0f}pts)"),
            lambda name, p=profile: make_challenger(f"{p.name}s ({points:.0f}pts)"),
            n_battles,
            rng,
        )
        reports.append(report)

    return reports


def suite_mixed(
    points: float,
    n_battles: int,
    rng: random.Random,
) -> MatchupReport:
    """
    Run n_battles between two random mixed armies at equal points.
    Both armies draw from the full unit catalogue.
    """
    report = MatchupReport(
        a_name=f"Random Army A ({points:.0f}pts)",
        b_name=f"Random Army B ({points:.0f}pts)",
        battles=n_battles,
    )
    for _ in range(n_battles):
        army_a = build_random_army(
            f"Random Army A ({points:.0f}pts)", points, rng=rng
        )
        army_b = build_random_army(
            f"Random Army B ({points:.0f}pts)", points, rng=rng
        )
        result = Battle(army_a, army_b).run()
        report.record(result)
    return report


def suite_mirror(
    profile_key: str,
    points: float,
    n_battles: int,
    rng: random.Random,
) -> MatchupReport:
    """Mirror match: two homogeneous armies of the same unit type. Should be ~50%."""
    profile = UNIT_CATALOG[profile_key]
    report = MatchupReport(
        a_name=f"{profile.name} A",
        b_name=f"{profile.name} B",
        battles=n_battles,
    )
    for _ in range(n_battles):
        army_a = build_homogeneous_army(f"{profile.name} A", profile, points)
        army_b = build_homogeneous_army(f"{profile.name} B", profile, points)
        result = Battle(army_a, army_b).run()
        report.record(result)
    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Swaghammer calibration suite")
    parser.add_argument("--battles", type=int, default=1000,
                        help="Battles per matchup (default: 1000)")
    parser.add_argument("--points", type=float, default=1000.0,
                        help="Points per army (default: 1000)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--homogeneous", action="store_true",
                        help="Run homogeneous unit-vs-Marine matchups")
    parser.add_argument("--mixed", action="store_true",
                        help="Run random mixed-army matchup")
    parser.add_argument("--mirror", type=str, default=None,
                        help="Run mirror match for a catalogue key (e.g. space_marine)")
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)

    if not any([args.homogeneous, args.mixed, args.mirror]):
        # Default: run all suites
        args.homogeneous = True
        args.mixed = True
        args.mirror = "space_marine"

    print(
        f"\nSwaghammer Calibration Suite"
        f"\n{'='*60}"
        f"\nBattles per matchup: {args.battles}"
        f"\nPoints per army:     {args.points:.0f}"
        f"\nRandom seed:         {args.seed}"
        f"\n{'='*60}"
    )

    if args.mirror:
        print(f"\n## Mirror Match — {args.mirror}\n")
        report = suite_mirror(args.mirror, args.points, args.battles, rng)
        print(report)

    if args.homogeneous:
        print(f"\n## Homogeneous Matchups vs Space Marines\n")
        reports = suite_homogeneous(args.points, args.battles, rng)
        for r in reports:
            print(r)
            print()

    if args.mixed:
        print(f"\n## Mixed Random Armies\n")
        report = suite_mixed(args.points, args.battles, rng)
        print(report)

    print(f"\n{'='*60}\nDone.\n")


if __name__ == "__main__":
    main(sys.argv[1:])
