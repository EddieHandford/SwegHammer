"""What move INTENT does Astra Militarum infantry carry?

The advance-suppression family in `Battle._do_move` only applies when
`intent in ("CAPTURE", "STEAL")`. If the infantry is carrying some other intent
the suppression never runs, which would explain why admitting Astra Militarum
REGIMENT infantry to the family (SWEG_AM_INFANTRY_FIRE) moved Cadian Shock
Troops only 82.2 -> 74.4 percent Advanced and Death Korps of Krieg not at all.

Run: PYTHONHASHSEED=0 python -m scripts._am_intent_probe
"""
from __future__ import annotations
import os
import random
from collections import Counter, defaultdict

import code.simulator as SIM
import code.strategy as ST
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

WATCH = set(os.environ.get("MI_WATCH", "Cadian Shock Troops,Death Korps of Krieg,Kasrkin,Tempestus Scions").split(","))
FAC = os.environ.get("MI_FACTION", "Astra Militarum")
OPPS = ["Genestealer Cults", "Adepta Sororitas", "Necrons", "Death Guard"]
N = int(os.environ.get("MI_N", "3"))
_idx = {f: i for i, f in enumerate(FACTIONS)}
INTENT = defaultdict(Counter)

_real = SIM.pick_move_intent


def _probe(unit, *a, **kw):
    out = _real(unit, *a, **kw)
    name = getattr(getattr(unit, "profile", None), "name", "?")
    if name in WATCH and (getattr(unit.profile, "faction", "") or "") == FAC:
        try:
            INTENT[name][out[1]] += 1
        except Exception:
            pass
    return out


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.pick_move_intent = _probe
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()
    for name in sorted(INTENT):
        C = INTENT[name]
        tot = sum(C.values())
        print(f"\n=== {name} — {tot} move decisions ===")
        for k, c in C.most_common():
            mark = "  <- suppression family applies" if k in ("CAPTURE", "STEAL") else ""
            print(f"   {100*c/max(1,tot):5.1f}%  {k}{mark}")
