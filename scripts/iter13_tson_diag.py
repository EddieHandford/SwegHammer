"""
iter13 TSON diagnostic — verify the _fit_squad_size cap-aware fix lets
high-min-cost battleline squads (Rubric Marines, Scarab Occult Terminators)
actually appear in random_fill TSON lists, and check whether Magnus the Red
is being picked organically now that the random pool can produce supporting
Rubrics around him.

Measures across 30 random_fill TSON armies at 1000pt:
  * Rubric Marines: squad count per army (a "squad" is min_models..max_models
    copies of the profile added by a single pick — we count by unique pick
    not by individual model)
  * Scarab Occult Terminators: same
  * Magnus the Red appearance rate
  * Ahriman appearance rate (sanity check the auto-include is still there)

Then runs the same 30-battle TSON-vs-meta matchups iter12 ran (Marines,
DG, Necrons) and reports WR%.

Read-only — does NOT modify catalogue / simulator / strategy.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter13_tson_diag
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
        [sys.executable, "-m", "scripts.iter13_tson_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS: List[str] = [
    "Adeptus Astartes",
    "Death Guard",
    "Necrons",
]
TSON = "Thousand Sons"
N = 30
POINTS = 1000

TRACK = (
    "Magnus the Red",
    "Ahriman",
    "Rubric Marines",
    "Scarab Occult Terminators",
    "Exalted Sorcerer",
    "Infernal Master",
)


def _profile_squad_counts(army) -> Dict[str, int]:
    """Count consecutive same-profile runs as 'squads' — random_fill adds
    `size` copies of one profile in a single iteration, so consecutive
    identical profiles in `army.units` represent one squad. This isn't
    perfect (two separate picks of the same profile back-to-back collapse)
    but it's a close-enough proxy for diag purposes."""
    counts: Dict[str, int] = defaultdict(int)
    prev = None
    for u in army.units:
        if u.profile.name != prev:
            counts[u.profile.name] += 1
            prev = u.profile.name
    return counts


def _model_counts(army) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for u in army.units:
        out[u.profile.name] += 1
    return out


def composition_audit() -> None:
    print(f"=== iter13 TSON composition audit — {N} random_fill armies @ {POINTS}pt ===")
    squad_totals: Dict[str, int] = defaultdict(int)
    model_totals: Dict[str, int] = defaultdict(int)
    appearance_armies: Dict[str, int] = defaultdict(int)
    pts_sum = 0.0

    for s in range(N):
        a = build_faction_random_army(
            "A", TSON, POINTS,
            rng=random.Random(s),
            use_archetype=False,
        )
        pts_sum += sum(u.profile.points_cost for u in a.units)
        sq = _profile_squad_counts(a)
        md = _model_counts(a)
        for n, c in sq.items():
            squad_totals[n] += c
        for n, c in md.items():
            model_totals[n] += c
            appearance_armies[n] += 1  # at least one model -> appears

    print(f"\nMean TSON points spent per army: {pts_sum/N:.1f}")
    print(f"\n{'Profile':30s} {'sq/army':>8s} {'models/army':>12s} {'appear%':>9s}")
    print("-" * 65)
    for n in TRACK:
        sq = squad_totals.get(n, 0) / N
        md = model_totals.get(n, 0) / N
        ap = appearance_armies.get(n, 0) / N * 100
        print(f"{n:30s} {sq:8.2f} {md:12.2f} {ap:9.1f}")

    # Sample compositions
    print(f"\nSample compositions (first 3 armies):")
    for s in range(3):
        a = build_faction_random_army(
            "A", TSON, POINTS,
            rng=random.Random(s),
            use_archetype=False,
        )
        cts = Counter(u.profile.name for u in a.units)
        print(f"  s={s}: " + ", ".join(f"{c}x {n}" for n, c in cts.most_common()))


def matchup_audit() -> None:
    print(f"\n=== iter13 TSON WR vs meta — {N} battles each, random_fill ===")
    print(f"{'Opponent':22s} {'TSON WR%':>9s}")
    print("-" * 35)
    wrs: List[float] = []
    for opp in OPPONENTS:
        wins = 0
        for s in range(N):
            tson = build_faction_random_army(
                "A", TSON, POINTS,
                rng=random.Random(s),
                use_archetype=False,
            )
            other = build_faction_random_army(
                "B", opp, POINTS,
                rng=random.Random(s + 10000),
                use_archetype=False,
            )
            if not tson.units or not other.units:
                continue
            battle = Battle(tson, other, map_=DEFAULT_MAP)
            r = battle.run()
            if r.winner == "A":
                wins += 1
        wr = wins / N * 100
        wrs.append(wr)
        print(f"{opp:22s} {wr:9.1f}")
    print(f"\nMean TSON WR vs {len(OPPONENTS)} factions: {statistics.mean(wrs):.1f}%")


def main() -> None:
    composition_audit()
    matchup_audit()


if __name__ == "__main__":
    main()
