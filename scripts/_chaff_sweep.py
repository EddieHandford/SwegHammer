"""How much of each army is piloted as sacrificial chaff?

`code.strategy._sacrificial_chaff_target` (AI-9) sends any unit under
`_CHAFF_MAX_POINTS_PER_MODEL` (15.0 points per model) that is not standing on an
objective into the enemy deployment zone to score the position secondaries. Its
conservative gate (d) only declines when a friendly is ALREADY in the enemy
deployment zone — so while the first unit is still walking, every other chaff
unit in the army receives the same intent. For an army built out of sub-15-point
models that is most of the army, every round, and a unit that Advances to cross
the table forfeits its Shooting phase.

This measures the share of move decisions that come back SACRIFICIAL per faction
and lines it up against that faction's residual, to see whether the effect
explains the under-poles.

Run: PYTHONHASHSEED=0 python -m scripts._chaff_sweep
"""
from __future__ import annotations
import json
import os
import random
import statistics
from collections import Counter, defaultdict

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

N = int(os.environ.get("CS_N", "2"))
OPP = os.environ.get("CS_OPP", "Necrons")
_idx = {f: i for i, f in enumerate(FACTIONS)}
TALLY = defaultdict(Counter)
_real = SIM.pick_move_intent


def _probe(unit, *a, **kw):
    out = _real(unit, *a, **kw)
    fac = getattr(getattr(unit, "profile", None), "faction", None) or "?"
    try:
        TALLY[fac]["SACRIFICIAL" if out[1] == "SACRIFICIAL" else "other"] += 1
    except Exception:
        pass
    return out


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.pick_move_intent = _probe
    for fac in FACTIONS:
        opp = OPP if fac != OPP else "Adeptus Astartes"
        for seed in range(N):
            ps = (_idx[fac] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", fac, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()

    log = json.load(open("data/_anchor_sc67a_n80_log.json"))
    w, n = Counter(), Counter()
    for fa, fb, seed, win in log["games"]:
        n[fa] += 1; w[fa] += (win == "A")
        n[fb] += 1; w[fb] += (win == "B")
    real = json.load(open("data/warpfriends_rolling.json"))["factions"]

    rows = []
    for fac in FACTIONS:
        C = TALLY[fac]
        tot = C["SACRIFICIAL"] + C["other"]
        if not tot:
            continue
        share = 100 * C["SACRIFICIAL"] / tot
        resid = 100 * w[fac] / n[fac] - real[fac]["win_rate"]
        rows.append((fac, share, resid))
    rows.sort(key=lambda r: -r[1])
    print(f"{'faction':24s} {'SACRIFICIAL share':>18s} {'residual':>10s}")
    for fac, share, resid in rows:
        print(f"{fac:24s} {share:17.1f}% {resid:+10.1f}")
    xs = [r[1] for r in rows]; ys = [r[2] for r in rows]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) ** .5) * (sum((y - my) ** 2 for y in ys) ** .5)
    print(f"\nPearson correlation(SACRIFICIAL share, residual) = {cov/den:+.3f}")
