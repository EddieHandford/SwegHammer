"""Increment-2 (b)-first gating check: how many scout / infiltrate units do the
eval's archetype lists ACTUALLY field per faction?

Builds armies through the SAME entry point the eval uses
(build_faction_random_army(faction, 2000, use_archetype=True)) over many seeds
and reports, per faction: mean scout units / mean infiltrate units fielded, the
mean models carried by those units, and the share of armies that field >=1.

Decides the increment-2 fork: meaningful counts => scout-DESTINATION AI bites;
thin/absent => the lever is list-realism (field the real-meta scout units).
"""
from __future__ import annotations

import random
import statistics

from code.army_builder import build_faction_random_army

FACTIONS = [
    "Astra Militarum", "Adepta Sororitas", "Adeptus Mechanicus",
    "Aeldari", "T'au Empire", "Adeptus Astartes",  # comparison (scout-rich)
]
N = 30


def main() -> None:
    print(f"scout/infiltrate presence in --use-archetype lists (2000 pts, N={N} seeds/faction)")
    print(f"{'faction':24s} {'scoutU':>7s} {'scoutMdl':>9s} {'infilU':>7s} {'infilMdl':>9s} {'has>=1scout':>11s}")
    for fac in FACTIONS:
        s_units, s_models, i_units, i_models, has_scout = [], [], [], [], []
        for s in range(N):
            army = build_faction_random_army(
                "A", fac, 2000, rng=random.Random(s), use_archetype=True,
            )
            su = [u for u in army.units if getattr(u.profile, "scout_distance", 0) > 0]
            iu = [u for u in army.units if getattr(u.profile, "infiltrator", False)]
            # squad-expanded: each Unit is one model in this representation
            s_units.append(len({getattr(u, "squad_id", id(u)) for u in su}))
            s_models.append(len(su))
            i_units.append(len({getattr(u, "squad_id", id(u)) for u in iu}))
            i_models.append(len(iu))
            has_scout.append(1 if su else 0)
        print(f"{fac:24s} {statistics.mean(s_units):7.2f} {statistics.mean(s_models):9.2f} "
              f"{statistics.mean(i_units):7.2f} {statistics.mean(i_models):9.2f} "
              f"{statistics.mean(has_scout)*100:10.0f}%")


if __name__ == "__main__":
    main()
