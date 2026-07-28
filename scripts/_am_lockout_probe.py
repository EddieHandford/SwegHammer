"""Which lockout eats Astra Militarum infantry's shooting?

`scripts/_am_target_probe.py` showed Cadian Shock Troops reaching `Unit.attack`
on 34 activations when roughly 358 had a legal target in weapon range with line
of sight — about ninety percent of legal shooting disappears between the two.
`Battle._do_shoot` has several early returns before the range gate (action
lockout, embarked, Fall Back, Advance, One Shot, Engagement Range). This
attributes every activation to the first gate that would stop it.

Run: PYTHONHASHSEED=0 python -m scripts._am_lockout_probe
"""
from __future__ import annotations
import os
import random
from collections import Counter, defaultdict

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

WATCH = {"Cadian Shock Troops", "Death Korps of Krieg", "Kasrkin", "Tempestus Scions"}
FAC = os.environ.get("LP_FACTION", "Astra Militarum")
OPPS = ["Genestealer Cults", "Adepta Sororitas", "Necrons", "Death Guard"]
N = int(os.environ.get("LP_N", "3"))
_idx = {f: i for i, f in enumerate(FACTIONS)}
GATE = defaultdict(Counter)

_real = SIM.Battle._do_shoot


def _probe(self, attacker, attacker_army, defender_army):
    name = attacker.profile.name or "?"
    if name in WATCH and (attacker.profile.faction or "") == FAC:
        G = GATE[name]
        if not attacker.is_alive:
            G["dead"] += 1
        elif attacker.action_this_round is not None:
            G["performing an action"] += 1
        elif getattr(attacker, "embarked_in", None) is not None:
            G["embarked"] += 1
        elif getattr(attacker, "fell_back_this_round", False):
            G["fell back"] += 1
        elif attacker.uid in self._advanced_this_round:
            G["ADVANCED"] += 1
        else:
            eng = SIM._er_engaged_by(
                attacker, [u for u in defender_army.alive_units], base_edge=self._charge_baseedge
            )
            G["locked in Engagement Range" if eng else "free to shoot"] += 1
    return _real(self, attacker, attacker_army, defender_army)


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._do_shoot = _probe
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()
    for name in sorted(GATE):
        G = GATE[name]
        tot = sum(G.values())
        print(f"\n=== {name} — {tot} shooting activations ===")
        for k, c in G.most_common():
            print(f"   {100*c/max(1,tot):5.1f}%  {k}")
