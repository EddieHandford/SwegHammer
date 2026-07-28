"""Scratch: consolidated AM-vs-<opponent> loss diagnostic. Per seed: winner,
capped VP, primary/secondary split; then the closest losses; then the aggregate
per-card secondary breakdown. Reflects current defaults (dedupe now ON). Uses the
diag_pilot game construction so a chosen seed renders the same game. Read-only.
Not committed.  Usage: python -m scripts._am_diag "Necrons" [N]"""
from __future__ import annotations
import random, sys
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.events import RoundEnded, EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC = "Astra Militarum"
B_FAC = sys.argv[1] if len(sys.argv) > 1 else "Necrons"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 16
_fac_idx = {f: i for i, f in enumerate(FACTIONS)}

tally = defaultdict(lambda: [0, 0])   # card -> [A_vp, B_vp]
_orig = Battle._score_one_card
def _wrapped(self, card_key, scoring_army, other_army, own_is_a, round_num):
    vp = _orig(self, card_key, scoring_army, other_army, own_is_a, round_num)
    tally[card_key][0 if own_is_a else 1] += vp
    return vp
Battle._score_one_card = _wrapped

print(f"# {A_FAC} (A) vs {B_FAC} (B)  N={N}   (defaults: dedupe ON)")
print(f"{'seed':>4} {'win':>3} {'Acap':>4} {'Bcap':>4} {'marg':>5} {'Apri':>4} {'Bpri':>4} {'Asec':>4} {'Bsec':>4}")
rows = []
for seed in range(N):
    pair_seed = (_fac_idx[A_FAC] * 1000 + _fac_idx[B_FAC]) * 100 + seed
    random.seed(pair_seed)
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    lg = EventLog()
    map_ = _pick_rotation_map(seed)
    primary = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, subscribers=[lg], map_=map_, primary_mission=primary)
    battle.run()
    res = [e for e in lg.events if isinstance(e, RoundEnded)]
    if not res:
        continue
    last = res[-1]
    ac, bc = last.a_vp_capped, last.b_vp_capped
    asec = getattr(battle, "_a_secondary_vp", 0); bsec = getattr(battle, "_b_secondary_vp", 0)
    achal = getattr(battle, "_a_challenger_vp", 0); bchal = getattr(battle, "_b_challenger_vp", 0)
    apri = ac - min(asec, 40) - achal; bpri = bc - min(bsec, 40) - bchal
    win = "A" if ac > bc else ("B" if bc > ac else "=")
    rows.append((seed, win, ac, bc, ac - bc, apri, bpri, asec, bsec))
    print(f"{seed:>4} {win:>3} {ac:>4} {bc:>4} {ac-bc:>+5} {apri:>4} {bpri:>4} {asec:>4} {bsec:>4}")

losses = sorted([r for r in rows if r[1] == "B"], key=lambda r: r[4], reverse=True)
wins = sum(1 for r in rows if r[1] == "A")
n = len(rows) or 1
pri_d = sum(r[5] - r[6] for r in rows) / n
sec_d = sum(r[7] - r[8] for r in rows) / n
print(f"\n# AM wins {wins}/{len(rows)}   mean primary_diff {pri_d:+.1f}   mean secondary_diff {sec_d:+.1f}")
print("# closest AM losses (seed, margin):", [(r[0], r[4]) for r in losses[:5]])
print(f"\n# per-card secondary VP (summed over all {n} games)")
print(f"{'card':30} {'AM':>5} {'OPP':>5} {'OPP-AM':>7}")
for card, (av, bv) in sorted(tally.items(), key=lambda kv: kv[1][1] - kv[1][0], reverse=True):
    if av or bv:
        print(f"{card:30} {av:>5} {bv:>5} {bv-av:>+7}")
