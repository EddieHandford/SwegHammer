"""Which secondary cards actually SCORE, and which are drawn and score nothing?

The simulator scores about 12.3 secondary victory points per player per game
against a real 22.7 — a ten-point gap that is the largest single measured
distortion left. Correcting the map geometry did NOT touch it (#64), so the cause
is behavioural: either the cards are drawn and never satisfied, or the piloting
layer never plays for them.

This separates those two. For every card in the Tactical pool and the Fixed pool
it records how often the card is HELD and how many victory points it yields, so a
card that is drawn constantly and scores nothing is visible as such. A card that
never scores is either unachievable on this frame (a geometry or representation
problem) or unpursued (a piloting problem) — and knowing WHICH cards are dead is
what tells the two apart.

Instruments the real scorers rather than reimplementing them, since a probe that
reimplements what it measures is how an earlier blind-spot probe produced a
confidently wrong answer.

Run: PYTHONHASHSEED=0 python -m scripts._secondary_card_yield
     SCY_BATTLES=24
"""
from __future__ import annotations
import collections
import os
import random

import code.secondaries as S
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import (FACTIONS, _pick_rotation_map,
                                      _pick_primary_mission)

N = int(os.environ.get("SCY_BATTLES", "24"))

held = collections.Counter()
scored_vp = collections.Counter()
scored_times = collections.Counter()

# Battle._score_one_card is the per-card dispatcher: it takes the card key and
# returns that card's victory points, routing to whichever scorer owns it. That
# makes it the ONE hook that sees every card, instead of wrapping a dozen
# scorers and inevitably missing some. An earlier version of this probe wrapped
# only the two module-level scorers and could see 6 of 19 cards; the 13 it could
# not see read as zero, which is exactly the kind of silent blind spot that
# turns a probe into a wrong answer.
_real_one_card = Battle._score_one_card


def _wrap_one_card(self, card_key, scoring_army, other_army, own_is_army_a,
                   round_num):
    vp = _real_one_card(self, card_key, scoring_army, other_army,
                        own_is_army_a, round_num)
    held[card_key] += 1
    try:
        v = float(vp)
    except (TypeError, ValueError):
        v = 0.0
    if v > 0:
        scored_vp[card_key] += v
        scored_times[card_key] += 1
    return vp


def main() -> None:
    Battle._score_one_card = _wrap_one_card
    opponents = [f for f in FACTIONS if f != FACTIONS[0]]
    try:
        for i in range(N):
            seed = 4000 + i
            A = FACTIONS[i % len(FACTIONS)]
            B = opponents[(i * 7) % len(opponents)]
            if B == A:
                B = opponents[(i * 7 + 1) % len(opponents)]
            random.seed(seed)
            a = build_faction_random_army("A", A, 2000, rng=random.Random(seed),
                                          use_archetype=True)
            b = build_faction_random_army("B", B, 2000,
                                          rng=random.Random(seed + 1),
                                          use_archetype=True)
            if not a.units or not b.units:
                continue
            Battle(a, b, map_=_pick_rotation_map(seed),
                   primary_mission=_pick_primary_mission(seed)).run()
    finally:
        Battle._score_one_card = _real_one_card

    pool = list(dict.fromkeys(
        list(getattr(S, "TACTICAL_DECK_POOL", ()))
        + list(getattr(S, "FIXED_SECONDARY_KEYS", ()))
        + list(getattr(S, "TACTICAL_SECONDARY_KEYS", ()))))

    print(f"=== secondary card yield, {N} battles ===\n")
    if not held:
        print("  NO card slots observed. The scorer's signature does not expose")
        print("  the held cards by keyword, so this attribution approach cannot")
        print("  see them — inspect score_round_delta's parameters and adapt")
        print("  before drawing any conclusion from silence.")
        print(f"\n  pool has {len(pool)} distinct cards:")
        for c in pool:
            print(f"    {c}")
        return

    print(f"{'card':<34}{'held':>7}{'scored':>8}{'total VP':>10}{'VP/held':>9}")
    dead = []
    for c in pool:
        h = held.get(c, 0)
        s = scored_times.get(c, 0)
        v = scored_vp.get(c, 0.0)
        if h and not s:
            dead.append(c)
        print(f"{c[:33]:<34}{h:>7}{s:>8}{v:>10.1f}"
              f"{(v / h if h else 0.0):>9.2f}")

    print()
    if dead:
        print(f"  DRAWN BUT NEVER SCORED: {len(dead)}")
        for c in dead:
            print(f"    {c}")
        print()
        print("  A card held repeatedly that yields nothing is either")
        print("  unachievable on this frame or never pursued. Check each against")
        print("  its scorer before assuming which.")
    else:
        print("  Every held card scored at least once.")


if __name__ == "__main__":
    main()
