"""Does the Tyranid swarm ever REACH combat?

The full audit shows Hormagaunts — the army's dedicated melee swarm — logging 76
fight activations a game for 1.7 total wounds, and 5 percent surviving.
Termagants deal 0.0 melee damage across 105. But `_do_fight` is called once per
activation whether or not the unit is engaged, so those counts say nothing on
their own. The real question for a melee army is the same one that cracked Astra
Militarum's shooting: of the activations it gets, how many end in the thing the
unit exists to do?

Per activation this classifies: dead already, not in Engagement Range (so
`_do_fight` returns immediately), or genuinely fighting. It also tracks charges
declared versus charges that succeeded, and the distance to the nearest enemy,
so "never arrives" and "arrives and does nothing" are distinguishable.

Run: PYTHONHASHSEED=0 python -m scripts._melee_reach_probe
"""
from __future__ import annotations
import collections
import os
import random

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("MR_FACTION", "Tyranids")
WATCH = set(os.environ.get(
    "MR_WATCH", "Hormagaunts,Termagants,Ripper Swarms,Tyrant Guard,Hive Tyrant"
).split(","))
N = int(os.environ.get("MR_N", "4"))
OPPS = ["Adeptus Astartes", "Necrons", "Adepta Sororitas", "Death Guard"]
_idx = {f: i for i, f in enumerate(FACTIONS)}

R = collections.defaultdict(collections.Counter)
NEAR = collections.defaultdict(list)

_real_fight = SIM.Battle._do_fight
_real_charge = SIM.Battle._do_charge


def _fight(self, attacker, attacker_army, defender_army):
    name = attacker.profile.name or "?"
    if name in WATCH and (attacker.profile.faction or "") == FAC:
        c = R[name]
        if not attacker.is_alive:
            c["dead"] += 1
        else:
            engaged = SIM._er_engaged_by(
                attacker, list(defender_army.alive_units),
                base_edge=self._charge_baseedge,
            )
            c["ENGAGED - fights" if engaged else "not in engagement range"] += 1
            if not engaged:
                live = [u for u in defender_army.alive_units
                        if getattr(u, "embarked_in", None) is None]
                if live:
                    NEAR[name].append(
                        min(SIM._distance(attacker.position, u.position) for u in live)
                    )
    return _real_fight(self, attacker, attacker_army, defender_army)


def _charge(self, attacker, attacker_army, defender_army):
    name = attacker.profile.name or "?"
    watched = name in WATCH and (attacker.profile.faction or "") == FAC
    before = None
    if watched:
        R[name]["charge_calls"] += 1
        before = SIM._er_engaged_by(
            attacker, list(defender_army.alive_units), base_edge=self._charge_baseedge)
    out = _real_charge(self, attacker, attacker_army, defender_army)
    if watched and not before:
        after = SIM._er_engaged_by(
            attacker, list(defender_army.alive_units), base_edge=self._charge_baseedge)
        if after:
            R[name]["charge_CONNECTED"] += 1
    return out


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._do_fight = _fight
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

    for name in sorted(R):
        c = R[name]
        tot = c["dead"] + c["ENGAGED - fights"] + c["not in engagement range"]
        print(f"\n=== {name} — {tot} fight activations ===")
        for k in ("ENGAGED - fights", "not in engagement range", "dead"):
            if c[k]:
                print(f"   {100*c[k]/max(1,tot):5.1f}%  {k}")
        cc, cn = c["charge_calls"], c["charge_CONNECTED"]
        if cc:
            print(f"   charges: {cc} attempts, {cn} connected ({100*cn/cc:.0f}%)")
        ns = sorted(NEAR[name])
        if ns:
            print(f"   when NOT engaged, nearest enemy: median {ns[len(ns)//2]:.1f}\"  "
                  f"p10 {ns[len(ns)//10]:.1f}\"")
