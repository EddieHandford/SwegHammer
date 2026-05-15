"""
Quantify the OC-on-objective imbalance for Tyranids vs each opponent at
R1 end. We expect Tyranid OC on objectives to be ~2-3x opponent OC
because of the Termagant + Gargoyle + Hormagaunt screen.
"""

from __future__ import annotations

import random
from collections import Counter

from code.archetypes import build_archetype_army, has_archetype
from code.army_builder import build_faction_random_army
from code.events import EventLog, ObjectiveScored, RoundEnded
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
]


def _build(faction: str, name: str, budget: float, seed: int):
    rng = random.Random(seed)
    if has_archetype(faction):
        return build_archetype_army(name, faction, budget, rng=rng)
    return build_faction_random_army(name, faction, budget, rng=rng)


def per_round_obj_oc(opp: str, n: int = 10):
    a_oc_per_round = [[] for _ in range(6)]
    b_oc_per_round = [[] for _ in range(6)]
    for s in range(n):
        random.seed(2000 + s)
        tyr = _build("Tyranids", "TYR", 1000, seed=s)
        op = _build(opp, "OPP", 1000, seed=s + 50000)
        log = EventLog()
        battle = Battle(tyr, op, map_=DEFAULT_MAP, subscribers=[log])
        battle.run()
        current_round = 0
        a_oc_round = Counter()
        b_oc_round = Counter()
        for e in log.events:
            if isinstance(e, ObjectiveScored):
                # Combined OC each side had on this objective.
                a_oc_round[current_round] += e.a_oc
                b_oc_round[current_round] += e.b_oc
            elif isinstance(e, RoundEnded):
                if current_round < 6:
                    a_oc_per_round[current_round].append(a_oc_round[current_round])
                    b_oc_per_round[current_round].append(b_oc_round[current_round])
                current_round += 1
            elif e.__class__.__name__ == "RoundStarted":
                # Battle is reset each round
                pass
    return a_oc_per_round, b_oc_per_round


def main():
    print(f"{'OPP':22s}  R1_TYR/OPP  R2_TYR/OPP  R3_TYR/OPP  R4_TYR/OPP  R5_TYR/OPP")
    for opp in OPPONENTS:
        a, b = per_round_obj_oc(opp, n=10)
        parts = []
        for r in range(1, 6):
            av = sum(a[r]) / max(1, len(a[r]))
            bv = sum(b[r]) / max(1, len(b[r]))
            parts.append(f"{av:4.1f}/{bv:4.1f}")
        print(f"{opp:22s}  " + "  ".join(parts))


if __name__ == "__main__":
    main()
