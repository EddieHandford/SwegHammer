"""SWEG_TAC_DECK held-card ACHIEVE-RATE diagnostic (#1 lever A/B crux).

The watchdog's crux for the SWEG_TAC_DECK A/B: if the 2-card Tactical hand STALLS
(the AI holds cards it rarely achieves — wave 119 saw defend_stronghold 11% /
extend_battle_lines 9%), then turning the deck ON under-scores EVERYONE, including
the under-shooters, so it won't land — and the real fix is the AI-pursuit, not the
deck. This probe runs the deck ON (SWEG_TAC_DECK=1) and records, per faction:
  - the secondary TRACK chosen (TACTICAL vs FIXED, from _choose_secondary_track),
  - for TACTICAL armies, the per-card ACHIEVE-RATE of held cards (a card scoring
    1+ VP in a round it was held = achieved).
A healthy deck should show held cards achieving at a decent rate (a real player
achieves ~1-2 cards/turn). Low achieve-rates = the AI-pursuit stall the watchdog
warned about. Read-only, single process. Run with PYTHONHASHSEED=0.
"""
import os
os.environ["SWEG_TAC_DECK"] = "1"   # force the deck ON for this diagnostic

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

FACTIONS = ["Astra Militarum", "Adeptus Mechanicus", "Chaos Space Marines",
            "Imperial Knights", "World Eaters", "Tyranids", "Adeptus Astartes",
            "Necrons", "Aeldari", "T'au Empire"]
# Under-shooters + over-side get the focused read; the rest are opponents.
FOCUS = ["Astra Militarum", "Adeptus Mechanicus", "Chaos Space Marines",
         "Imperial Knights", "World Eaters"]
SEEDS = [1, 2, 3]

agg = defaultdict(lambda: defaultdict(float))   # faction -> counters
card = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # faction -> card -> [held, achieved]

_real_one = Battle._score_one_card
_real_hand = Battle._score_tactical_hand


def _fac(army):
    return army.units[0].profile.faction if army.units else "?"


def _patched_hand(self, army, other_army, own_is_army_a, round_num):
    fac = _fac(army)
    # Record per-card held + achieved BEFORE the discard/redraw mutates the hand.
    for c in list(army.tactical_hand):
        vp = _real_one(self, c, army, other_army, own_is_army_a, round_num)
        card[fac][c][0] += 1
        if vp > 0:
            card[fac][c][1] += 1
    return _real_hand(self, army, other_army, own_is_army_a, round_num)


def run_pair(a_fac, b_fac, seed):
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    battle.run()
    for army in (a, b):
        fac = _fac(army)
        track = getattr(army, "secondary_track", None)
        agg[fac]["battles"] += 1
        agg[fac]["tac"] += 1 if track == "TACTICAL" else 0


if __name__ == "__main__":
    Battle._score_tactical_hand = _patched_hand
    for i, f in enumerate(FOCUS):
        for opp in FACTIONS:
            if opp == f:
                continue
            for s in SEEDS:
                run_pair(f, opp, s)
                run_pair(opp, f, s + 50)

    print(f"{'Faction':<20} {'battles':>7} {'TACTICAL%':>9} {'heldCards':>9} {'achieve%':>9}")
    print("-" * 58)
    for f in FOCUS:
        d = agg[f]; n = d["battles"] or 1
        held = sum(h for h, a in card[f].values())
        ach = sum(a for h, a in card[f].values())
        print(f"{f:<20} {int(d['battles']):>7} {100*d['tac']/n:>8.0f}% "
              f"{held:>9} {100*ach/(held or 1):>8.0f}%")
    print()
    print("Per-card achieve-rate (TACTICAL held cards), focus factions:")
    print(f"{'Faction':<20} {'card':<22} {'held':>6} {'achieve%':>9}")
    print("-" * 60)
    for f in FOCUS:
        for c in sorted(card[f]):
            held, ach = card[f][c]
            if held == 0:
                continue
            print(f"{f:<20} {c:<22} {held:>6} {100*ach/held:>8.0f}%")
    print()
    print("TACTICAL% = how often this faction's list chose the Tactical track (low-model")
    print("durable armies should pick FIXED). achieve% = held cards that scored 1+ VP —")
    print("the AI-pursuit health. Low achieve% = the stall: deck ON under-scores them.")
