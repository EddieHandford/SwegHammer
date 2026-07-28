"""WHERE does the secondary shortfall come from - selection, or scoring?

Task #45 established, against a cited source, that the simulator scores roughly
half the secondary it should while the total comes out right:

    real, Pariah Nexus ~7,600 games   primary 29.1  secondary 22.7  share 43.8%
    simulator, 231 battles            primary 37.7  secondary 11.8  share 23.8%

That says the total is missing about eleven victory points of secondary per
army per game. This locates them. There are three places they can be hiding and
they need very different fixes:

  NEVER OFFERED   a card is not in the deck or pool the simulator draws from,
                  so it can never contribute. A content gap.
  OFFERED, NOT SCORED  the card is held or chosen but scores zero or near-zero,
                  because the condition never fires or the scoring path is
                  broken. A mechanics bug.
  SCORED LOW      the card scores, but well under what real players get from
                  it. A tuning or opportunity problem.

The real per-card numbers from the same Goonhammer article give direct targets
for fixed selections: Bring It Down averages 12.7 VP when taken, Assassination
12.8, Engage on All Fronts 10.8. Extend Battle Lines, Secure No Man's Land and
No Prisoners all complete above 90 percent of the time.

Method mirrors scripts/_diag_card_breakdown.py: patch Battle._score_one_card,
the single dispatch point both the FIXED and TACTICAL paths route through, and
record every invocation with the victory points it returned. Patching is
restored in a finally block so an exception cannot leave the class mutated.

CAVEAT: the real per-card averages are for cards taken as FIXED, and the real
data reports fixed selection at only about 12 percent of games. The simulator's
mix of FIXED and TACTICAL is reported here so the comparison is not made across
different regimes without saying so.

Run: PYTHONHASHSEED=0 python -m scripts._secondary_gap_probe
     SG_SEEDS=2
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map

SEEDS = int(os.environ.get("SG_SEEDS", "2"))

# Real averages when the card is taken as a FIXED secondary, from Goonhammer
# "Hammer of Math: Stats from the First Month of Pariah Nexus, Part 2".
REAL_FIXED = {
    "bring_it_down": 12.7,
    "assassination": 12.8,
    "engage_on_all_fronts": 10.8,
}

card_vp: dict = collections.defaultdict(float)
card_calls: dict = collections.defaultdict(int)
card_zero: dict = collections.defaultdict(int)
track_counts: dict = collections.Counter()
games = 0

_real_score_one_card = Battle._score_one_card


def _patched(self, card_key, scoring_army, other_army, own_is_army_a,
             round_num, *a, **k):
    vp = _real_score_one_card(self, card_key, scoring_army, other_army,
                              own_is_army_a, round_num, *a, **k)
    card_vp[card_key] += float(vp or 0)
    card_calls[card_key] += 1
    if not vp:
        card_zero[card_key] += 1
    return vp


def main() -> None:
    global games
    pairs = [(a, b) for i, a in enumerate(FACTIONS) for b in FACTIONS[i + 1:]]
    Battle._score_one_card = _patched
    try:
        for s in range(SEEDS):
            for fa, fb in pairs:
                seed = 7000 + s * 10000 + hash((fa, fb)) % 9999
                random.seed(seed)
                a = build_faction_random_army("A", fa, 2000,
                                              rng=random.Random(seed),
                                              use_archetype=True)
                b = build_faction_random_army("B", fb, 2000,
                                              rng=random.Random(seed + 1),
                                              use_archetype=True)
                if not a.units or not b.units:
                    continue
                Battle(a, b, map_=_pick_rotation_map(seed)).run()
                games += 1
                for army in (a, b):
                    track_counts[getattr(army, "secondary_track", None)] += 1
    finally:
        Battle._score_one_card = _real_score_one_card

    armies = 2 * games
    print(f"=== secondary card scoring, {games} battles ({armies} armies) ===")
    print(f"  secondary track mix: " +
          "  ".join(f"{k}={v} ({100.0*v/max(armies,1):.0f}%)"
                    for k, v in track_counts.most_common()))
    print()
    print(f"{'card':<30}{'times scored':>13}{'total VP':>10}"
          f"{'VP per call':>13}{'zero-VP calls':>15}")
    total_vp = 0.0
    for k in sorted(card_vp, key=lambda x: -card_vp[x]):
        n = card_calls[k]
        total_vp += card_vp[k]
        per = card_vp[k] / n if n else 0.0
        print(f"{k[:29]:<30}{n:>13}{card_vp[k]:>10.0f}{per:>13.2f}"
              f"{card_zero[k]:>15}")
    print()
    print(f"  total secondary victory points across all armies: {total_vp:.0f}")
    print(f"  mean per army per game: {total_vp / max(armies, 1):.2f}"
          f"   (real benchmark 22.7)")

    print()
    print("  === cards NEVER invoked ===")
    print("  Any card absent from the table above was never held or chosen in")
    print("  any of these battles, so it cannot contribute victory points at")
    print("  all. That is a content gap rather than a scoring one.")

    print()
    print("  === against the real fixed-selection averages ===")
    print("  Real numbers are per-GAME averages for cards taken as FIXED; the")
    print("  simulator column here is victory points per SCORING CALL, which is")
    print("  per round, so the two are not directly comparable without knowing")
    print("  how many rounds a card is held. Reported to show ORDER OF")
    print("  MAGNITUDE and to spot cards scoring at or near zero.")
    for k, real in REAL_FIXED.items():
        hits = [c for c in card_vp if k in c]
        if not hits:
            print(f"    {k:<26} real {real:>5.1f}   SIMULATOR: never invoked")
            continue
        for c in hits:
            n = card_calls[c]
            per = card_vp[c] / n if n else 0.0
            print(f"    {c[:26]:<26} real {real:>5.1f}   sim {per:>5.2f} per call"
                  f"  over {n} calls")


if __name__ == "__main__":
    main()
