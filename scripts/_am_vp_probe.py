"""Does capping the sacrificial-chaff commitment cost secondary victory points?

SWEG_CHAFF_COMMIT_CAP stops the army sending roughly half its bodies into the
enemy deployment zone. The intended trade is "the infantry shoots instead", but
the position secondaries (Behind Enemy Lines, Engage on All Fronts) are exactly
what the discarded behaviour was chasing. If those collapse, the package has
bought shooting with victory points and the win-rate number would be masking it.

Reports primary, secondary and total victory points for both sides.

Run: PYTHONHASHSEED=0 python -m scripts._am_vp_probe
"""
from __future__ import annotations
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("VP_FACTION", "Astra Militarum")
# Default is the four hardest cells (the set this probe was first written
# against, while hunting the damage defect). Set VP_OPPS="ALL" for a FAIR
# spread across every opponent � the deficit measured on the worst four is not
# the deficit in an average matchup, and the two must not be conflated.
_opps_env = os.environ.get("VP_OPPS", "")
if _opps_env.strip().upper() == "ALL":
    OPPS = [f for f in FACTIONS if f != FAC]
elif _opps_env.strip():
    OPPS = [f.strip() for f in _opps_env.split(",") if f.strip()]
else:
    OPPS = ["Genestealer Cults", "Adepta Sororitas", "Necrons", "Death Guard"]
N = int(os.environ.get("VP_N", "3"))
_idx = {f: i for i, f in enumerate(FACTIONS)}

if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    a_sec = a_vp = b_vp = b_sec = 0.0
    wins = games = 0
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            _fa, _fb = (opp, FAC) if swap else (FAC, opp)
            a = build_faction_random_army("A", _fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", _fb, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            batt = Battle(a, b, map_=_pick_rotation_map(seed), primary_mission=_pick_primary_mission(ps))
            r = batt.run()
            games += 1
            # Re-orient to the FAC perspective. SWEG_SIDE_ROLLOFF is
            # DEFAULT-ON in scripts/evaluate_vs_meta.py: it flips which faction
            # occupies slot A on a per-game coin flip keyed on the pair seed and
            # re-orients the winner, so every evaluated cell is a both-sides
            # average. A probe that always builds its subject as slot A measures
            # a one-sided frame instead, which is why this script's package-off
            # baseline read 42.9 percent against the anchor's 33.8.
            _me, _them = ("A", "B") if not swap else ("B", "A")
            wins += (r.winner == _me)
            a_sec += batt._a_secondary_vp if _me == "A" else batt._b_secondary_vp
            b_sec += batt._b_secondary_vp if _me == "A" else batt._a_secondary_vp
            a_vp += r.a_vp if _me == "A" else r.b_vp
            b_vp += r.b_vp if _me == "A" else r.a_vp
    print(f"{FAC} over {games} games:")
    print(f"  win rate            {100*wins/games:.1f}%")
    print(f"  total victory points {a_vp/games:.1f}   (opponent {b_vp/games:.1f})")
    print(f"  secondary            {a_sec/games:.1f}")
    print(f"  primary (implied)    {(a_vp-a_sec)/games:.1f}")
    print(f"  OPPONENT secondary   {b_sec/games:.1f}")
    print(f"  OPPONENT primary     {(b_vp-b_sec)/games:.1f}")
