"""Do armies hold an objective in their OWN deployment zone?

Task #46 found Extend Battle Lines scoring zero on 84 percent of calls while the
real source calls it "the most free objective in the game" with above ninety
percent completion. Reading the scorer (Battle._score_board_secondaries) shows it
is a CONJUNCTION:

    if "extend_battle_lines" in chosen and own_dz_controlled >= 1
                                       and nml_controlled >= 1:

and its two siblings each test one half. Their measured rates multiply out
almost exactly:

    Defend Stronghold      own deployment zone only   20% non-zero
    Secure No Man's Land   No Man's Land only         82% non-zero
    0.20 x 0.82 = 16.4%, against Extend Battle Lines' measured 16%

So Extend Battle Lines is not independently broken. It inherits the real defect:
armies appear to control a home objective only about a fifth of the time. In
real Warhammer holding the objective inside your own deployment zone is close to
automatic - a single cheap unit sits on it all game - which is precisely why the
card is described as free.

This measures it directly rather than inferring it from card rates, because the
card rates are conditioned on the card having been chosen and could be a
selection artefact. It recomputes the same two counters the scorer uses, with
the same helpers (`_oc_within`, `_obj_in_own_dz`, `_obj_in_nml`), at every
scoring call.

If home control really is near 20 percent, the defect is in MOVEMENT or
DEPLOYMENT - the artificial intelligence does not garrison its home objective -
and it is not a scoring bug at all. That would also feed the primary
over-scoring found in task #45 from the other direction, since the same
objectives drive primary.

Run: PYTHONHASHSEED=0 python -m scripts._home_objective_probe
     HO_SEEDS=1
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map

SEEDS = int(os.environ.get("HO_SEEDS", "1"))

samples: list = []          # (own_dz_controlled, nml_controlled, total_objs)
by_round: dict = collections.defaultdict(list)

_real = Battle._score_board_secondaries


def _patched(self, army, opponent, own_is_army_a: bool, chosen_override=None):
    # Recompute the scorer's own two counters using its own helpers, so this
    # measures exactly what the card condition sees - not an approximation.
    own_dz = nml = 0
    for obj in self.map.objectives:
        if self._oc_within(army, obj) <= self._oc_within(opponent, obj):
            continue
        if self._obj_in_own_dz(obj, own_is_army_a):
            own_dz += 1
        elif self._obj_in_nml(obj):
            nml += 1
    samples.append((own_dz, nml, len(self.map.objectives)))
    rnd = getattr(self, "_round_num", None) or getattr(self, "round_num", 0)
    by_round[rnd].append(own_dz)
    return _real(self, army, opponent, own_is_army_a, chosen_override)


def main() -> None:
    pairs = [(a, b) for i, a in enumerate(FACTIONS) for b in FACTIONS[i + 1:]]
    Battle._score_board_secondaries = _patched
    n_battles = 0
    try:
        for s in range(SEEDS):
            for fa, fb in pairs:
                seed = 8000 + s * 10000 + hash((fa, fb)) % 9999
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
                n_battles += 1
    finally:
        Battle._score_board_secondaries = _real

    if not samples:
        print("no scoring calls observed — is the Tier-A gate off?")
        return

    n = len(samples)
    home_any = sum(1 for o, _, _ in samples if o >= 1)
    nml_any = sum(1 for _, m, _ in samples if m >= 1)
    both = sum(1 for o, m, _ in samples if o >= 1 and m >= 1)
    mean_home = sum(o for o, _, _ in samples) / n
    mean_nml = sum(m for _, m, _ in samples) / n
    mean_objs = sum(t for _, _, t in samples) / n

    print(f"=== home objective control, {n_battles} battles, "
          f"{n} scoring evaluations ===")
    print(f"  objectives on the map (mean)          {mean_objs:.1f}")
    print()
    print(f"  controls 1+ in OWN deployment zone    {100.0 * home_any / n:5.1f}%"
          f"   (mean {mean_home:.2f})")
    print(f"  controls 1+ in No Man's Land          {100.0 * nml_any / n:5.1f}%"
          f"   (mean {mean_nml:.2f})")
    print(f"  controls BOTH (Extend Battle Lines)   {100.0 * both / n:5.1f}%")
    print()
    print(f"  product of the two independently      "
          f"{100.0 * (home_any / n) * (nml_any / n):5.1f}%")
    print("  If that product is close to the measured BOTH figure, the two")
    print("  conditions are near-independent and Extend Battle Lines is simply")
    print("  their conjunction — not separately broken.")
    print()
    print("  own-deployment-zone control by round:")
    for rnd in sorted(by_round):
        vals = by_round[rnd]
        pct = 100.0 * sum(1 for v in vals if v >= 1) / len(vals)
        print(f"    round {rnd}   {pct:5.1f}%  over {len(vals)} evaluations")
    print()
    print("  In real Warhammer, holding the objective inside your own deployment")
    print("  zone is close to automatic — a single cheap unit sits on it all")
    print("  game. A low figure here is a MOVEMENT or DEPLOYMENT defect, not a")
    print("  scoring one, and it would also inflate the opponent's primary.")


if __name__ == "__main__":
    main()
