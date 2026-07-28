"""Scratch: per-card secondary-VP breakdown for AM vs Astartes over the loss
seeds, by wrapping Battle._score_one_card. Answers: WHICH secondary cards is
each side scoring? Localises AM's secondary bleed to a specific card. Read-only.
Not committed."""
from __future__ import annotations
import random
import sys
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.events import RoundEnded, EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC = "Astra Militarum"
B_FAC = "Adeptus Astartes"
_fac_idx = {f: i for i, f in enumerate(FACTIONS)}
seeds = [int(x) for x in sys.argv[1:]] or [5, 10, 7, 13, 9, 15]

_orig = Battle._score_one_card
tally = defaultdict(lambda: [0, 0])  # card -> [A_vp, B_vp]

def _wrapped(self, card_key, scoring_army, other_army, own_is_a, round_num):
    vp = _orig(self, card_key, scoring_army, other_army, own_is_a, round_num)
    tally[card_key][0 if own_is_a else 1] += vp
    return vp

Battle._score_one_card = _wrapped

n = 0
for seed in seeds:
    pair_seed = (_fac_idx[A_FAC] * 1000 + _fac_idx[B_FAC]) * 100 + seed
    random.seed(pair_seed)
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, subscribers=[log], map_=map_, primary_mission=primary).run()
    n += 1

print(f"# per-card secondary VP, AM(A) vs Astartes(B), summed over {n} loss games")
print(f"{'card':32} {'AM_vp':>7} {'Astartes_vp':>12} {'B-A':>6}")
rows = sorted(tally.items(), key=lambda kv: kv[1][1] - kv[1][0], reverse=True)
tA = tB = 0
for card, (av, bv) in rows:
    tA += av; tB += bv
    print(f"{card:32} {av:>7} {bv:>12} {bv-av:>+6}")
print(f"{'TOTAL':32} {tA:>7} {tB:>12} {tB-tA:>+6}   (per game: AM {tA/n:.1f}  Astartes {tB/n:.1f})")
