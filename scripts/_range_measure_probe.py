"""How much shooting does the centre-to-centre range measurement cost?

10e core, already cited in this repository at
`data/rule_citations.d/keywords_and_mechanics.json`: "When measuring the distance
between models, measure between the closest points of the bases of the models
you're measuring to and from." The simulator applies that to Engagement Range
(`code.sim.geometry._er_gap`) and to objective control, but weapon range
eligibility (`Battle._do_shoot`, `_distance(attacker.position, u.position) <=
rng`) and every range-dependent weapon keyword (Rapid Fire X and Melta X, which
trigger at half range in `Unit.attack`) are measured centre to centre — so both
are STRICTER than the rule, by the two models' base radii.

This probe is read-only. It wraps the two measurements and counts:
  * shots denied by the centre-only range gate that base-edge would have allowed
  * shots that missed the half-range Rapid Fire / Melta bonus for the same reason

Run: PYTHONHASHSEED=0 python -m scripts._range_measure_probe
"""
from __future__ import annotations
import os
import random
from collections import Counter

import code.simulator as SIM
from code.sim.geometry import _bc_model_radius_in
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

N = int(os.environ.get("RP_N", "4"))
PAIRS = [
    ("Astra Militarum", "Death Guard"),
    ("Astra Militarum", "Adeptus Astartes"),
    ("Astra Militarum", "Imperial Knights"),
    ("Death Guard", "Adeptus Astartes"),
    ("Chaos Knights", "Aeldari"),
    ("Adeptus Astartes", "Aeldari"),
]
_idx = {f: i for i, f in enumerate(FACTIONS)}

# keyed by the SHOOTER's faction
denied = Counter()      # in range base-edge, denied centre-only
allowed = Counter()     # allowed by the centre-only gate (the shots that happen)
half_miss = Counter()   # Rapid Fire / Melta carrier outside half range centre-only, inside base-edge
half_hit = Counter()    # already inside half range centre-only
rf_shots = Counter()    # shots by a Rapid Fire / Melta carrier

_real_do_shoot = SIM.Battle._do_shoot


def _probe(self, attacker, attacker_army, defender_army):
    fac = attacker.profile.faction or "?"
    rng = attacker.profile.range_inches or 0.0
    r_a = _bc_model_radius_in(attacker.profile)
    if rng > 0:
        for u in defender_army.alive_units:
            if getattr(u, "embarked_in", None) is not None:
                continue
            d = SIM._distance(attacker.position, u.position)
            gap = d - r_a - _bc_model_radius_in(u.profile)
            if d <= rng:
                allowed[fac] += 1
            elif gap <= rng:
                denied[fac] += 1
        carrier = int(attacker.profile.rapid_fire or 0) > 0 or float(attacker.profile.melta or 0) > 0
        if carrier:
            half = rng / 2.0
            nearest = min(
                (u for u in defender_army.alive_units
                 if getattr(u, "embarked_in", None) is None),
                key=lambda u: SIM._distance(attacker.position, u.position),
                default=None,
            )
            if nearest is not None:
                rf_shots[fac] += 1
                d = SIM._distance(attacker.position, nearest.position)
                gap = d - r_a - _bc_model_radius_in(nearest.profile)
                if d <= half:
                    half_hit[fac] += 1
                elif gap <= half:
                    half_miss[fac] += 1
    return _real_do_shoot(self, attacker, attacker_army, defender_army)


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._do_shoot = _probe
    for fa, fb in PAIRS:
        for seed in range(N):
            ps = (_idx[fa] * 1000 + _idx[fb]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()

    print("=== TARGET ELIGIBILITY: attacker-target pairs inside weapon range ===")
    print(f"{'shooter faction':24s} {'centre-legal':>12s} {'base-edge-only':>15s} {'lost':>7s}")
    for fac in sorted(set(allowed) | set(denied), key=lambda f: -denied[f]):
        tot = allowed[fac] + denied[fac]
        print(f"{fac[:24]:24s} {allowed[fac]:12d} {denied[fac]:15d} "
              f"{100*denied[fac]/max(1,tot):6.1f}%")

    print("\n=== HALF RANGE (Rapid Fire X / Melta X trigger) vs nearest enemy ===")
    print(f"{'shooter faction':24s} {'activations':>12s} {'in half':>9s} {'lost to centre-only':>20s}")
    for fac in sorted(set(rf_shots), key=lambda f: -half_miss[f]):
        tot = rf_shots[fac]
        print(f"{fac[:24]:24s} {tot:12d} {half_hit[fac]:9d} "
              f"{half_miss[fac]:10d} ({100*half_miss[fac]/max(1,tot):.1f}% of activations)")
