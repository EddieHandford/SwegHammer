"""Scratch: byte-identical-off proof for SWEG_LEADER_SQUAD_DEDUPE. Replay a
sample of sc64a anchor games with the gate OFF (default) using the NEW code and
compare each winner to the logged winner. Prioritises games involving factions
whose archetype/random-fill can include the promotion-bug leader squads
(AM/CSM/Votann/Tyranids/Dark Angels). Any mismatch => the OFF path is NOT
byte-identical. Read-only. Not committed."""
from __future__ import annotations
import json, random, sys

from code.army_builder import build_faction_random_army
from code.events import RoundEnded, EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

_fac_idx = {f: i for i, f in enumerate(FACTIONS)}
PRIORITY = {"Astra Militarum", "Chaos Space Marines", "Leagues of Votann",
            "Tyranids", "Dark Angels"}

log = json.load(open("data/_anchor_sc64a_n40_log.json", encoding="utf-8"))
games = log["games"]
# sample: all priority-faction games first, capped, then a general spread
prio = [g for g in games if g[0] in PRIORITY or g[1] in PRIORITY]
sample_n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
# deterministic stride sample (no RNG — Math.random is unavailable anyway)
step = max(1, len(prio) // sample_n)
sample = prio[::step][:sample_n]

def replay_winner(fac_a, fac_b, seed):
    pair_seed = (_fac_idx[fac_a] * 1000 + _fac_idx[fac_b]) * 100 + seed
    random.seed(pair_seed)
    a = build_faction_random_army("A", fac_a, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", fac_b, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    lg = EventLog()
    map_ = _pick_rotation_map(seed)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, subscribers=[lg], map_=map_, primary_mission=primary).run()
    res = [e for e in lg.events if isinstance(e, RoundEnded)]
    if not res:
        return "?"
    last = res[-1]
    return "A" if last.a_vp_capped > last.b_vp_capped else ("B" if last.b_vp_capped > last.a_vp_capped else "draw")

match = mism = 0
mismatches = []
for g in sample:
    fac_a, fac_b, seed, logged = g[0], g[1], g[2], g[3]
    w = replay_winner(fac_a, fac_b, seed)
    if w == logged:
        match += 1
    else:
        mism += 1
        mismatches.append((fac_a, fac_b, seed, logged, w))

print(f"# byte-identical-off replay: {match}/{match+mism} winners match sc64a (gate default-off)")
if mismatches:
    print("# MISMATCHES (byte-identity BROKEN):")
    for fa, fb, s, lw, w in mismatches[:20]:
        print(f"  {fa} vs {fb} seed={s}: logged={lw} replay={w}")
else:
    print("# ZERO mismatches -> OFF path is byte-identical to sc64a.")
