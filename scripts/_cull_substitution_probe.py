"""Who substitutes, who is substituted against, and does it explain the deltas?

The SWEG_CULL_PICK_AWARE screen moved Aeldari -6.38 and Chaos Knights +4.80 by
swapping one passive kill card for another. A Cleanse-cascade explanation was
proposed and then REFUTED - the corrected fall-through changed one game in 36,960
(task #54). This instruments the picker directly instead of theorising, which is
what should have happened before any code was written.

Two roles matter and they pull in opposite directions:

  AS PICKER    the army holds a Cull the Horde it cannot score, swaps it for No
               Prisoners, and gains victory points. Should push the faction UP.
  AS ENEMY     the faction fields no thirteen-plus-model squad, so every
               opponent substitutes against it and gains. Should push it DOWN.

A faction's net delta should track (times substituted against) minus (times it
substituted), if the substitution is the whole story. This measures both counts
per faction and correlates them against the screen's measured deltas.

If neither correlates, the substitution is not what moves the win rates and the
gate is doing something else entirely - which is worth knowing before it is
adopted or discarded.

Run: PYTHONHASHSEED=0 python -m scripts._cull_substitution_probe
"""
from __future__ import annotations
import collections
import math
import os
import random

import code.secondaries as secmod
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map

SEEDS = [int(s) for s in os.environ.get("CS_SEEDS", "0").split(",")]

# Measured per-faction deltas from the full-matrix screen (army-A frame,
# paired against sc69a). Inputs, not outputs - quoted here so the correlation
# is against real screen results rather than a re-derivation.
DELTA = {
    "Aeldari": -6.38, "Adeptus Custodes": -4.05, "T'au Empire": -2.49,
    "Chaos Daemons": -2.07, "Leagues of Votann": -0.81,
    "Genestealer Cults": -0.40, "Adeptus Astartes": +0.92,
    "Emperor's Children": +3.00, "Grey Knights": +3.87,
    "Imperial Knights": +2.95, "Chaos Knights": +4.80,
}

picked_by = collections.Counter()      # faction -> times IT substituted
picked_against = collections.Counter() # faction -> times it was the hordeless enemy
calls_by = collections.Counter()
hordeless = {}

_real = secmod._pick_fixed_pair_full


def _fac(army):
    return army.units[0].profile.faction if army.units else "?"


def _patched(own_army, enemy_army):
    before_h = secmod._enemy_qualifying_horde_units(enemy_army)
    out = _real(own_army, enemy_army)
    o, e = _fac(own_army), _fac(enemy_army)
    calls_by[o] += 1
    hordeless[e] = before_h
    if before_h == 0 and "cull_the_horde" not in out:
        # The gate fired: an unscoreable Cull was replaced.
        picked_by[o] += 1
        picked_against[e] += 1
    return out


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def main() -> None:
    os.environ["SWEG_CULL_PICK_AWARE"] = "1"
    secmod._pick_fixed_pair_full = _patched
    pairs = [(a, b) for i, a in enumerate(FACTIONS) for b in FACTIONS[i + 1:]]
    try:
        for s in SEEDS:
            for fa, fb in pairs:
                seed = 9000 + s * 10000 + hash((fa, fb)) % 9999
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
    finally:
        secmod._pick_fixed_pair_full = _real
        os.environ.pop("SWEG_CULL_PICK_AWARE", None)

    print("=== Cull substitution, by role ===")
    print("  'substituted' = this army swapped an unscoreable Cull for a")
    print("  scoreable card. 'targeted' = opponents swapped against IT because")
    print("  it fields no 13-plus-model squad.\n")
    print(f"{'faction':<24}{'13+ squads':>11}{'substituted':>13}"
          f"{'targeted':>10}{'net':>7}{'screen delta':>14}")
    rows = []
    for fac in FACTIONS:
        h = hordeless.get(fac)
        sub = picked_by[fac]
        tgt = picked_against[fac]
        net = tgt - sub
        d = DELTA.get(fac)
        rows.append((fac, h, sub, tgt, net, d))
    rows.sort(key=lambda r: (r[5] is None, -(r[5] or 0)))
    for fac, h, sub, tgt, net, d in rows:
        ds = f"{d:+.2f}" if d is not None else "flat"
        hs = "?" if h is None else str(h)
        print(f"{fac:<24}{hs:>11}{sub:>13}{tgt:>10}{net:>+7}{ds:>14}")

    scored = [r for r in rows if r[5] is not None]
    if len(scored) >= 3:
        print()
        print(f"  Pearson, screen delta against:")
        print(f"    times substituted   "
              f"{_pearson([r[2] for r in scored], [r[5] for r in scored]):+.3f}")
        print(f"    times targeted      "
              f"{_pearson([r[3] for r in scored], [r[5] for r in scored]):+.3f}")
        print(f"    net (targeted-sub)  "
              f"{_pearson([r[4] for r in scored], [r[5] for r in scored]):+.3f}")
    print()
    print("  If none of these correlate, the substitution is not what moves the")
    print("  win rates, and the gate's measured effect comes from somewhere the")
    print("  card swap only triggers indirectly.")


if __name__ == "__main__":
    main()
