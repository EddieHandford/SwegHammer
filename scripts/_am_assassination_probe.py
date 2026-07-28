"""Sizing probe (NOT a faithful fix): how much of AM's under-pole is the
Assassination bleed? The sim does not model 10e Leader attachment, so AM's ~10
standalone CHARACTERs each feed 3-5 VP Assassination when killed. This probe
zeroes Assassination VP scored *against Astra Militarum* (an upper bound on
"perfect Leader protection") and measures AM's paired win-rate swing.

Run: PYTHONHASHSEED=0 python -m scripts._am_assassination_probe <N>
"""
from __future__ import annotations
import sys, random
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

_ORIG = Battle._score_one_card
SUPPRESS = {"v": False}


def _faction(army):
    return army.units[0].profile.faction if army.units else None


def _patched(self, card_key, scoring_army, other_army, own_is_army_a, round_num):
    vp = _ORIG(self, card_key, scoring_army, other_army, own_is_army_a, round_num)
    # other_army is the VICTIM whose dead CHARACTERs feed `scoring_army`'s
    # Assassination. Suppress only Assassination scored off Astra Militarum.
    if (SUPPRESS["v"] and "assassination" in str(card_key)
            and _faction(other_army) == "Astra Militarum"):
        return 0
    return vp


Battle._score_one_card = _patched


def winner(over, seed):
    random.seed(seed)
    a = build_faction_random_army("A", "Astra Militarum", 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", over, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    return Battle(a, b, map_=_pick_rotation_map(seed),
                  primary_mission=_pick_primary_mission(seed)).run().winner


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    seeds = list(range(n))
    print(f"# AM Assassination-bleed sizing probe  N={n}  (paired)")
    print(f"{'matchup':20} {'base%':>6} {'protected%':>10} {'Δpp':>6} {'L>W':>4} {'W>L':>4}")
    for over in ["Adeptus Astartes", "Imperial Knights", "Adepta Sororitas",
                 "Genestealer Cults", "T'au Empire"]:
        SUPPRESS["v"] = False
        base = {s: winner(over, s) for s in seeds}
        SUPPRESS["v"] = True
        prot = {s: winner(over, s) for s in seeds}
        bw = sum(1 for s in seeds if base[s] == "A")
        pw = sum(1 for s in seeds if prot[s] == "A")
        lw = sum(1 for s in seeds if base[s] != "A" and prot[s] == "A")
        wl = sum(1 for s in seeds if base[s] == "A" and prot[s] != "A")
        print(f"{over:20} {100*bw/n:6.1f} {100*pw/n:10.1f} {100*(pw-bw)/n:+6.1f} {lw:4d} {wl:4d}")
    SUPPRESS["v"] = False


if __name__ == "__main__":
    main()
