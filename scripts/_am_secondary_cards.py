"""Which secondary cards does Astra Militarum fail to score?

The corrected victory-point split says the remaining Astra Militarum gap is equal
halves primary and secondary (5.6 and 5.3). This decomposes the secondary half by
CARD, for Astra Militarum against every opponent, so a structural failure on one
card is visible rather than buried in an aggregate.

Wraps `Battle._score_one_card` (the per-card dispatcher used by the deck-aware
scorer) and tallies victory points by faction and card. Applies the
SWEG_SIDE_ROLLOFF re-orientation the evaluation uses.

Run: PYTHONHASHSEED=0 python -m scripts._am_secondary_cards
"""
from __future__ import annotations
import os
import random
from collections import defaultdict

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("SC_FACTION", "Astra Militarum")
N = int(os.environ.get("SC_N", "2"))
OPPS = [f for f in FACTIONS if f != FAC]
_idx = {f: i for i, f in enumerate(FACTIONS)}

CARD = defaultdict(lambda: defaultdict(float))   # faction -> card -> vp
CALLS = defaultdict(lambda: defaultdict(int))
_real = SIM.Battle._score_one_card


def _probe(self, card, army, other, own_is_a, round_num):
    vp = _real(self, card, army, other, own_is_a, round_num)
    fac = "?"
    for u in army.units:
        if u.profile.faction:
            fac = u.profile.faction
            break
    CARD[fac][card] += float(vp or 0)
    CALLS[fac][card] += 1
    return vp


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._score_one_card = _probe
    games = 0
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
            games += 1

    am = CARD[FAC]
    others = defaultdict(float)
    other_games = 0
    for f, d in CARD.items():
        if f == FAC:
            continue
        other_games += 1
        for c, v in d.items():
            others[c] += v
    print(f"=== secondary victory points by card, {games} games ===")
    print(f"{'card':34s} {FAC+'/gm':>19s} {'opponents/gm':>14s} {'gap':>8s}")
    keys = sorted(set(am) | set(others), key=lambda c: -(others[c] / max(1, games) - am.get(c, 0) / max(1, games)))
    for c in keys:
        a_v = am.get(c, 0.0) / max(1, games)
        o_v = others[c] / max(1, games)
        print(f"{str(c)[:34]:34s} {a_v:19.2f} {o_v:14.2f} {o_v - a_v:+8.2f}")
    print(f"\ntotal: {FAC} {sum(am.values())/max(1,games):.1f}/game  "
          f"opponents {sum(others.values())/max(1,games):.1f}/game")
