"""Is AM's OWN secondary-VP output anomalously low vs the field, or sim-wide?
For each faction as army A, mean secondary VP banked per game across a fixed
small opponent set + seeds. Ranks factions; AM's rank is the signal. Read-only.
Not committed."""
from __future__ import annotations
import random
from code.army_builder import build_faction_random_army
from code.events import RoundEnded, EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

_fac_idx = {f: i for i, f in enumerate(FACTIONS)}
OPPS = ["Necrons", "Adeptus Astartes"]   # fixed durable opponents for comparability
SEEDS = [0, 1]

rows = []
for fac in FACTIONS:
    sec_tot = pri_tot = n = 0
    for opp in OPPS:
        if opp == fac:
            continue
        for seed in SEEDS:
            ps = (_fac_idx[fac] * 1000 + _fac_idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", fac, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            lg = EventLog(); map_ = _pick_rotation_map(seed); pr = _pick_primary_mission(ps)
            batt = Battle(a, b, subscribers=[lg], map_=map_, primary_mission=pr)
            batt.run()
            res = [e for e in lg.events if isinstance(e, RoundEnded)]
            if not res:
                continue
            asec = getattr(batt, "_a_secondary_vp", 0)
            last = res[-1]
            apri = last.a_vp_capped - min(asec, 40) - getattr(batt, "_a_challenger_vp", 0)
            sec_tot += asec; pri_tot += apri; n += 1
    if n:
        rows.append((fac, sec_tot / n, pri_tot / n))

rows.sort(key=lambda r: r[1])
print(f"# mean SECONDARY VP banked as army A (vs {OPPS}, seeds {SEEDS})")
print(f"{'faction':24} {'sec_VP':>7} {'pri_VP':>7}")
for fac, sec, pri in rows:
    mark = "  <== AM" if fac == "Astra Militarum" else ""
    print(f"{fac:24} {sec:>7.1f} {pri:>7.1f}{mark}")
field = sum(r[1] for r in rows) / len(rows)
am = next(r[1] for r in rows if r[0] == "Astra Militarum")
print(f"\n# field mean secondary = {field:.1f}   AM secondary = {am:.1f}   AM rank = {[r[0] for r in rows].index('Astra Militarum')+1}/{len(rows)} (1=lowest)")
