"""
Demo entry point — runs a short battle and prints the blow-by-blow.

Usage:
    python -m code.main
"""

from __future__ import annotations

import random

from .army_builder import build_homogeneous_army, build_random_army
from .simulator import Battle
from .units import UNIT_CATALOG, UnitProfile


def print_unit_catalogue() -> None:
    print("\n=== Unit Catalogue ===")
    header = f"{'Name':<26} {'Health':>6} {'Damage':>6} {'Hit%':>6} {'Score':>8} {'Points':>7}"
    print(header)
    print("-" * len(header))
    for key, p in sorted(UNIT_CATALOG.items(), key=lambda kv: kv[1].points_cost):
        print(
            f"{p.name:<26} {p.health:>6.0f} {p.damage:>6.0f} "
            f"{p.hit_probability:>6.2f} {p.score:>8.2f} {p.points_cost:>7.1f}"
        )


DEMO_MARINE_KEY = "space_marines_intercessor_squad"
DEMO_ORK_KEY = "orks_boyz"
DEMO_TERMINATOR_KEY = "space_marines_terminator_squad"


def demo_verbose_battle() -> None:
    print("\n=== Verbose Demo Battle ===")
    rng = random.Random(1)
    marines = build_homogeneous_army("Marines", UNIT_CATALOG[DEMO_MARINE_KEY], 300)
    orks = build_homogeneous_army("Orks", UNIT_CATALOG[DEMO_ORK_KEY], 300)

    print(f"\n{marines.name}: {marines.total_points:.0f} pts, {len(marines.units)} units")
    for u in marines.units:
        print(f"  {u.profile.name} — {u.profile.points_cost:.0f} pts")

    print(f"\n{orks.name}: {orks.total_points:.0f} pts, {len(orks.units)} units")
    for u in orks.units:
        print(f"  {u.profile.name} — {u.profile.points_cost:.0f} pts")

    print()
    battle = Battle(marines, orks, verbose=True)
    result = battle.run()

    print(f"\n--- Result ---")
    print(f"  Winner:    {result.winner_label()}")
    print(f"  Rounds:    {result.rounds}")
    print(f"  Survivors: {result.a_name}: {result.a_survivors}  |  {result.b_name}: {result.b_survivors}")


def demo_quick_calibration() -> None:
    print("\n=== Quick Calibration (100 battles per matchup) ===")
    from .calibration import suite_homogeneous, suite_mirror

    rng = random.Random(42)
    print(f"\n-- Mirror match ({UNIT_CATALOG[DEMO_MARINE_KEY].name} vs itself) --")
    report = suite_mirror(DEMO_MARINE_KEY, 300.0, 100, rng)
    print(report)

    print(f"\n-- {UNIT_CATALOG[DEMO_MARINE_KEY].name} vs {UNIT_CATALOG[DEMO_ORK_KEY].name} --")
    from .calibration import run_matchup
    from .army_builder import build_homogeneous_army

    sm = UNIT_CATALOG[DEMO_MARINE_KEY]
    ob = UNIT_CATALOG[DEMO_ORK_KEY]

    report = run_matchup(
        lambda name: build_homogeneous_army("Marines", sm, 300.0),
        lambda name: build_homogeneous_army("Orks", ob, 300.0),
        100,
        rng,
    )
    print(report)

    print(f"\n-- {UNIT_CATALOG[DEMO_MARINE_KEY].name} vs {UNIT_CATALOG[DEMO_TERMINATOR_KEY].name} --")
    tm = UNIT_CATALOG[DEMO_TERMINATOR_KEY]
    report = run_matchup(
        lambda name: build_homogeneous_army("Marines", sm, 300.0),
        lambda name: build_homogeneous_army("Terminators", tm, 300.0),
        100,
        rng,
    )
    print(report)


def main() -> None:
    print_unit_catalogue()
    demo_verbose_battle()
    demo_quick_calibration()


if __name__ == "__main__":
    main()
