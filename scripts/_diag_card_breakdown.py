"""Read-only scratch probe (lens investigation): per-card secondary VP at
CURRENT PRODUCTION DEFAULTS, patching Battle._score_one_card (the single
dispatch point both the FIXED and TACTICAL scoring paths route through, per
code/simulator.py:4903-4913 `_score_secondaries_deck`). Also records each
army's secondary_track (FIXED/TACTICAL) and chosen_secondaries / tactical_hand
size, to separate "card type never drawn/held" from "card drawn but scores 0".

Small-N, single process. Run with PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8.
"""
import os
import random
from collections import defaultdict

import code.simulator as simmod
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

FACTIONS = ["Death Guard", "Astra Militarum", "Adeptus Astartes", "Necrons"]
SEEDS = [1, 2, 3]

_real_score_one_card = Battle._score_one_card
card_vp = defaultdict(float)      # card_key -> total VP scored (all armies)
card_calls = defaultdict(int)     # card_key -> number of times _score_one_card invoked (i.e. held/chosen this round)
card_vp_by_fac = defaultdict(lambda: defaultdict(float))   # faction -> card_key -> VP
track_counts = defaultdict(lambda: defaultdict(int))       # faction -> track -> count
hand_sizes = []
fixed_pair_sizes = []


def _fac_of(army):
    return army.units[0].profile.faction if army.units else "?"


def _patched_score_one_card(self, card_key, scoring_army, other_army, own_is_army_a, round_num, *a, **k):
    vp = _real_score_one_card(self, card_key, scoring_army, other_army, own_is_army_a, round_num, *a, **k)
    card_vp[card_key] += vp
    card_calls[card_key] += 1
    fac = _fac_of(scoring_army)
    card_vp_by_fac[fac][card_key] += vp
    return vp


def run_one(fac, opp, seed):
    random.seed(seed)
    a = build_faction_random_army("A", fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    battle.run()
    for army in (a, b):
        fac_name = _fac_of(army)
        track = getattr(army, "secondary_track", None)
        track_counts[fac_name][track] += 1
        hand = getattr(army, "tactical_hand", None)
        if track == "TACTICAL" and hand is not None:
            hand_sizes.append(len(hand))
        if track == "FIXED":
            fixed_pair_sizes.append(len(army.chosen_secondaries or ()))


if __name__ == "__main__":
    print("Env gate state (production defaults unless overridden):")
    for var in ("SWEG_TAC_DECK", "SWEG_TAC_DECK_CONSUMER_FIX", "SWEG_TACDECK_BIG_GAME",
                "SWEG_TACDECK_FULL", "SWEG_FIXED_POOL_FULL", "SWEG_TAC_SHEDDING",
                "SWEG_ACTIONS_HAND_GATED", "SWEG_CP_PER_COMMAND_PHASE", "SWEG_TIER_A",
                "SWEG_SECONDARY_PER_UNIT", "SWEG_SECONDARY", "SWEG_ACTION_ECONOMY",
                "SWEG_SECONDARY_HANDCAP", "SWEG_TERRAIN_DENSE"):
        print(f"  {var} = {os.environ.get(var, '<unset>')}")
    print()

    Battle._score_one_card = _patched_score_one_card
    n = 0
    OPPS = ["Chaos Space Marines", "Tyranids", "Imperial Knights"]
    for fac in FACTIONS:
        for opp in OPPS:
            if opp == fac:
                continue
            for s in SEEDS:
                run_one(fac, opp, s)
                n += 1
    Battle._score_one_card = _real_score_one_card

    print(f"Ran {n} games.\n")
    print("=== Per-card totals (all armies, all games) ===")
    print(f"{'card':<24} {'calls':>7} {'total VP':>10} {'VP/call':>8}")
    for k in sorted(card_vp, key=lambda x: -card_vp[x]):
        c = card_calls[k]
        v = card_vp[k]
        print(f"{k:<24} {c:>7} {v:>10.1f} {(v/c if c else 0):>8.2f}")

    print("\n=== Track routing (faction -> track -> #armies) ===")
    for fac, d in track_counts.items():
        print(f"  {fac:<20} {dict(d)}")

    if hand_sizes:
        print(f"\nTactical hand size: mean={sum(hand_sizes)/len(hand_sizes):.2f} n={len(hand_sizes)}")
    if fixed_pair_sizes:
        print(f"Fixed chosen_secondaries size: mean={sum(fixed_pair_sizes)/len(fixed_pair_sizes):.2f} n={len(fixed_pair_sizes)}")

    print("\n=== Per-faction per-card VP (only Death Guard / Astra Militarum) ===")
    for fac in ("Death Guard", "Astra Militarum"):
        print(f"-- {fac} --")
        d = card_vp_by_fac.get(fac, {})
        for k in sorted(d, key=lambda x: -d[x]):
            print(f"   {k:<24} {d[k]:>8.1f}  (calls {card_calls.get(k, 0)})")
