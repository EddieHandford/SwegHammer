"""How much does a faction's fielded army vary from game to game?

This is the confound check on scripts/_dispersion_by_templates. Chaos Daemons
has the lowest matchup dispersion of all 22 factions and is the only faction
with more than one archetype list, which fits the hypothesis that averaging
over a POPULATION of lists is what pulls matchups toward the middle. But Chaos
Daemons might simply have homogeneous units, which would produce the same
ranking for an unrelated reason.

The hypothesis makes a sharper, checkable claim: single-list factions should
field a near-IDENTICAL army in every one of their games, so the only variation
across a pairing's battles is dice and map. If that is true, a simulated
matchup rate converges on "what does this exact list do against that exact
list", which is naturally far more decisive than a tournament aggregate over
hundreds of different lists piloted by players of varying skill.

This builds each faction's army across many seeds and measures how much the
datasheet composition actually moves:

  distinct       number of different armies produced across the seeds
  turnover       mean fraction of models that differ between two random seeds
                 (0.00 means every game fields exactly the same army)

Run: PYTHONHASHSEED=0 python -m scripts._army_variability_probe
     AV_SEEDS=12
"""
from __future__ import annotations
import collections
import os
import random

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import FACTIONS

N_SEEDS = int(os.environ.get("AV_SEEDS", "12"))


def _compose(fac: str, seed: int) -> collections.Counter:
    army = build_faction_random_army("A", fac, 2000,
                                     rng=random.Random(seed),
                                     use_archetype=True)
    c = collections.Counter()
    for u in army.units:
        c[u.profile.name or "?"] += 1
    return c


def _turnover(a: collections.Counter, b: collections.Counter) -> float:
    """Fraction of models that differ between two armies (0 = identical)."""
    total = (sum(a.values()) + sum(b.values())) / 2.0
    if total <= 0:
        return 0.0
    diff = sum((a - b).values()) + sum((b - a).values())
    return diff / (2.0 * total)


def main() -> None:
    seeds = list(range(N_SEEDS))
    rows = []
    for fac in FACTIONS:
        comps = [_compose(fac, s) for s in seeds]
        distinct = len({tuple(sorted(c.items())) for c in comps})
        pairs = [(i, j) for i in range(len(comps)) for j in range(i + 1, len(comps))]
        turn = sum(_turnover(comps[i], comps[j]) for i, j in pairs) / max(len(pairs), 1)
        rows.append((turn, fac, len(ARCHETYPES.get(fac, {})), distinct,
                     sum(comps[0].values())))

    rows.sort(reverse=True)
    print(f"=== army variability across {N_SEEDS} seeds ===")
    print(f"{'faction':<24}{'lists':>6}{'distinct':>10}{'turnover':>10}{'models':>8}")
    for turn, fac, ntmpl, distinct, models in rows:
        mark = ""
        if turn < 0.005:
            mark = "   <-- identical army every game"
        elif ntmpl > 1:
            mark = "   <-- multiple lists"
        print(f"{fac:<24}{ntmpl:>6}{distinct:>10}{turn:>10.3f}{models:>8}{mark}")

    frozen = [r for r in rows if r[0] < 0.005]
    print()
    print(f"  factions fielding an identical army every game: "
          f"{len(frozen)} of {len(rows)}")
    print()
    print("  A faction whose turnover is 0.000 contributes no list variance at all.")
    print("  Every one of its battles is the same two lists meeting again, so the")
    print("  pairing's win rate measures one list-versus-list result, while the")
    print("  Warp Friends figure it is scored against averages over hundreds of")
    print("  lists and pilots. That difference is a property of the harness, not")
    print("  of any faction's rules, and no per-faction mechanic can remove it.")


if __name__ == "__main__":
    main()
