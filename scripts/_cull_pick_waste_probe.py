"""How often is Cull the Horde picked against an enemy who cannot concede it?

`secondaries._pick_fixed_pair_full` chooses the two Fixed cards an army brings.
It is composition-aware for two of them — Bring It Down needs the enemy to hold
at least `_BID_TARGET_THRESHOLD` MONSTER/VEHICLE units, Assassination needs two
or more enemy CHARACTERs — but Cull the Horde is the FALLBACK for both slots,
taken whenever those tests fail, with no check that the enemy fields any
qualifying unit at all.

Cull the Horde scores only on destroying an enemy INFANTRY unit whose Starting
Strength was CULL_THE_HORDE_MIN_MODELS (13) or more. Against an elite roster of
five- and ten-model squads it is unscoreable, and the picker takes it regardless.
A real player choosing Fixed Missions sees the opponent's army first and would
never note down an unscoreable card.

This needs no battles — only army builds and the picker — so it is cheap and
exact. For every ordered faction pair it counts how often the chosen pair
contains a card the enemy roster cannot concede.

Run: PYTHONHASHSEED=0 python -m scripts._cull_pick_waste_probe
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from code.secondaries import (
    CULL_THE_HORDE_MIN_MODELS, _pick_fixed_kill_pair, _enemy_monster_vehicle_count,
    _is_character,
)
from scripts.evaluate_vs_meta import FACTIONS

N = int(os.environ.get("CP_N", "3"))


def _qualifying_horde_squads(army) -> int:
    """Count enemy INFANTRY units whose STARTING strength was 13 or more.

    The simulator stores one Unit per physical model, so a codex unit is a group
    of Unit instances sharing a squad_id — count groups, not instances.
    """
    sizes = collections.Counter()
    lone = 0
    for u in army.units:
        sid = getattr(u, "squad_id", -1)
        if sid >= 0:
            sizes[sid] += 1
        else:
            lone += 1
    return sum(1 for n in sizes.values() if n >= CULL_THE_HORDE_MIN_MODELS)


def main() -> None:
    waste = collections.Counter()
    picks = collections.Counter()
    byfac = collections.defaultdict(collections.Counter)
    for i, own in enumerate(FACTIONS):
        for j, foe in enumerate(FACTIONS):
            if own == foe:
                continue
            for seed in range(N):
                a = build_faction_random_army("A", own, 2000,
                                              rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", foe, 2000,
                                              rng=random.Random(seed + 10000),
                                              use_archetype=True)
                pair = _pick_fixed_kill_pair(a, b)
                nh = _qualifying_horde_squads(b)
                mv = _enemy_monster_vehicle_count(b)
                nc = sum(1 for u in b.units if _is_character(u))
                picks["pairs"] += 1
                byfac[own]["pairs"] += 1
                if "cull_the_horde" in pair:
                    picks["cull picked"] += 1
                    byfac[own]["cull picked"] += 1
                    if nh == 0:
                        picks["CULL PICKED, enemy has ZERO 13+ squads"] += 1
                        byfac[own]["wasted"] += 1
                if "bring_it_down" in pair and mv == 0:
                    picks["bring it down picked, enemy has no monster/vehicle"] += 1
                if "assassination" in pair and nc == 0:
                    picks["assassination picked, enemy has no character"] += 1

    tot = max(1, picks["pairs"])
    print("=== Fixed-pair picks that the enemy roster cannot concede ===")
    print(f"    faction pairs evaluated: {tot}  ({len(FACTIONS)} factions, {N} seeds)")
    for k, v in picks.most_common():
        if k == "pairs":
            continue
        print(f"    {100*v/tot:5.1f}%  ({v:5d})  {k}")
    print()
    print("    wasted Cull the Horde picks, by the army DOING the picking:")
    rows = sorted(byfac.items(), key=lambda kv: -kv[1]["wasted"])
    for fac, c in rows:
        if not c["pairs"]:
            continue
        print(f"      {fac:<24} wasted {c['wasted']:>3} / {c['pairs']:>3} pairs "
              f"({100*c['wasted']/c['pairs']:5.1f}%)   cull picked {c['cull picked']}")


if __name__ == "__main__":
    main()
