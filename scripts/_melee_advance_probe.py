"""Does giving a melee-only unit ENGAGE intent make it ADVANCE and lose the charge?

`SWEG_MELEE_ONLY_ENGAGE` changes Hormagaunt intents from 0 percent ENGAGE to 73.2
percent, and they do close (median distance to nearest enemy 16.0 -> 12.2 inches)
— but they end up ENGAGED LESS often (8.7 -> 3.4 percent) and connect FEWER
charges (11 -> 3 percent). The suspected cause is the 10e core lockout this
codebase implements correctly: "A unit that Advances can't shoot or declare a
charge later this turn." Heading at the enemy makes them Advance to cover ground,
and Advancing forfeits the charge.

This counts, per activation, whether the unit Advanced — with the gate off and on.

Run: PYTHONHASHSEED=0 python -m scripts._melee_advance_probe
"""
from __future__ import annotations
import collections
import os
import random

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("MA_FACTION", "Tyranids")
WATCH = set(os.environ.get("MA_WATCH", "Hormagaunts").split(","))
N = int(os.environ.get("MA_N", "4"))
OPPS = ["Adeptus Astartes", "Necrons", "Adepta Sororitas", "Death Guard"]
_idx = {f: i for i, f in enumerate(FACTIONS)}

C = collections.Counter()
_real_charge = SIM.Battle._do_charge


def _charge(self, attacker, attacker_army, defender_army):
    name = attacker.profile.name or "?"
    if name in WATCH and (attacker.profile.faction or "") == FAC and attacker.is_alive:
        C["charge_step_reached"] += 1
        if attacker.uid in self._advanced_this_round:
            C["ADVANCED - charge forfeit"] += 1
        elif getattr(attacker, "fell_back_this_round", False):
            C["fell back"] += 1
        else:
            C["eligible to charge"] += 1
    return _real_charge(self, attacker, attacker_army, defender_army)


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._do_charge = _charge
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            fa, fb = (opp, FAC) if swap else (FAC, opp)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()

    tot = max(1, C["charge_step_reached"])
    gate = os.environ.get("SWEG_MELEE_ONLY_ENGAGE", "0")
    print(f"=== {', '.join(sorted(WATCH))} charge eligibility "
          f"(SWEG_MELEE_ONLY_ENGAGE={gate}) ===")
    print(f"   activations reaching the charge step: {tot}")
    for k in ("eligible to charge", "ADVANCED - charge forfeit", "fell back"):
        if C[k]:
            print(f"   {100*C[k]/tot:5.1f}%  {k}")
