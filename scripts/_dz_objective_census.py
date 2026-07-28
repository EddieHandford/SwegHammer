"""How many objectives EXIST in each deployment zone, before anyone contests them?

scripts/_home_objective_probe measured armies controlling an objective in their
own deployment zone only 23.2 percent of the time, and concluded the artificial
intelligence abandons its home objective. That conclusion is only valid if there
IS a home objective to hold. If the rotation maps place most or all objectives
in No Man's Land, then a low control rate is structural and the conclusion is
wrong.

This counts, per map, how many objectives fall in army A's deployment zone,
army B's, and No Man's Land, using the simulator's own classifiers
(`_obj_in_own_dz`, `_obj_in_nml`) so the census matches exactly what the
scorer sees. No battles are run - the map geometry alone answers it.

Run: PYTHONHASHSEED=0 python -m scripts._dz_objective_census
"""
from __future__ import annotations
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map


def main() -> None:
    print("=== deployment zone objective census, by rotation map ===")
    print("Counts use the simulator's own _obj_in_own_dz / _obj_in_nml, so they")
    print("match what _score_board_secondaries classifies.\n")
    print(f"{'seed':>5}{'objectives':>12}{'A home':>9}{'B home':>9}"
          f"{'no mans land':>14}{'unclassified':>14}")

    tot_a = tot_b = tot_nml = tot_other = tot_obj = 0
    n_maps = 0
    for seed in range(12):
        random.seed(seed)
        a = build_faction_random_army("A", "Adeptus Astartes", 2000,
                                      rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", "Necrons", 2000,
                                      rng=random.Random(seed + 1),
                                      use_archetype=True)
        bt = Battle(a, b, map_=_pick_rotation_map(seed))
        a_home = b_home = nml = other = 0
        for obj in bt.map.objectives:
            in_a = bt._obj_in_own_dz(obj, True)
            in_b = bt._obj_in_own_dz(obj, False)
            if in_a:
                a_home += 1
            elif in_b:
                b_home += 1
            elif bt._obj_in_nml(obj):
                nml += 1
            else:
                other += 1
        n = len(bt.map.objectives)
        print(f"{seed:>5}{n:>12}{a_home:>9}{b_home:>9}{nml:>14}{other:>14}")
        tot_a += a_home
        tot_b += b_home
        tot_nml += nml
        tot_other += other
        tot_obj += n
        n_maps += 1

    print()
    print(f"  mean per map: {tot_obj / n_maps:.1f} objectives — "
          f"A home {tot_a / n_maps:.2f}, B home {tot_b / n_maps:.2f}, "
          f"No Man's Land {tot_nml / n_maps:.2f}, "
          f"unclassified {tot_other / n_maps:.2f}")
    print()
    if tot_a / n_maps < 0.5:
        print("  THERE IS USUALLY NO HOME OBJECTIVE. A 23 percent control rate is")
        print("  then structural, not a behaviour defect, and the earlier")
        print("  conclusion must be withdrawn: Extend Battle Lines and Defend")
        print("  Stronghold are near-unscoreable because the map geometry gives")
        print("  them nothing to hold, which is a MAP fidelity question.")
    else:
        print("  A home objective normally EXISTS, so a 23 percent control rate")
        print("  is a genuine behaviour defect: the artificial intelligence is")
        print("  not garrisoning ground it already owns at deployment.")


if __name__ == "__main__":
    main()
