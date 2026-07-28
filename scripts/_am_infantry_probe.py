"""Why does Astra Militarum infantry never deal damage?

The per-unit audit (`scripts/_am_unit_audit.py`) found Cadian Shock Troops
resolving 46 shooting activations a game for 0.4 wounds, and Death Korps of
Krieg 100 percent silent. Expected output for a single lasgun model inside half
range is roughly 0.33 wounds per activation, so the shortfall is nearly two
orders of magnitude and cannot be dice.

This decomposes each shooting activation of the named datasheets into the reason
it produced nothing: dead before activating, locked in melee, no target inside
weapon range at all, target in range but no line of sight, or it genuinely shot
and rolled poorly. It also records the distance to the nearest enemy so we can
see whether the infantry is simply never in lasgun range.

Run: PYTHONHASHSEED=0 python -m scripts._am_infantry_probe
"""
from __future__ import annotations
import os
import random
from collections import Counter, defaultdict

import code.simulator as SIM
from code.sim.geometry import _bc_model_radius_in
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

WATCH = {"Cadian Shock Troops", "Death Korps of Krieg", "Kasrkin", "Tempestus Scions"}
FAC = "Astra Militarum"
OPPS = ["Genestealer Cults", "Adepta Sororitas", "Necrons", "Death Guard"]
N = int(os.environ.get("IP_N", "4"))
_idx = {f: i for i, f in enumerate(FACTIONS)}

REASON = defaultdict(Counter)
NEAREST = defaultdict(list)
RANGES = Counter()

_real_do_shoot = SIM.Battle._do_shoot


def _probe(self, attacker, attacker_army, defender_army):
    name = attacker.profile.name or "?"
    if name not in WATCH or (attacker.profile.faction or "") != FAC:
        return _real_do_shoot(self, attacker, attacker_army, defender_army)

    R = REASON[name]
    if not attacker.is_alive:
        R["dead"] += 1
        return _real_do_shoot(self, attacker, attacker_army, defender_army)

    rng = float(attacker.profile.range_inches or 0.0)
    RANGES[f"{name} range={rng:.0f}"] += 1
    targetable = [u for u in defender_army.alive_units
                  if getattr(u, "embarked_in", None) is None]
    if not targetable:
        R["no enemy"] += 1
        return _real_do_shoot(self, attacker, attacker_army, defender_army)

    dists = [SIM._distance(attacker.position, u.position) for u in targetable]
    nearest = min(dists)
    NEAREST[name].append(nearest)

    in_range = [u for u, d in zip(targetable, dists) if d <= rng]
    if not in_range:
        R["no target in weapon range"] += 1
    else:
        seen = [
            u for u in in_range
            if self.map.has_line_of_sight(
                attacker.position, u.position,
                attacker_keywords=attacker.profile.unit_keywords or (),
                target_keywords=u.profile.unit_keywords or (),
            )
        ]
        if not seen:
            R["in range, no line of sight"] += 1
        else:
            R["SHOT"] += 1

    before = sum(u.current_health for u in defender_army.alive_units)
    out = _real_do_shoot(self, attacker, attacker_army, defender_army)
    after = sum(u.current_health for u in defender_army.alive_units)
    if before - after > 0:
        R["...dealt damage"] += 1
    return out


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._do_shoot = _probe
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()

    for name in sorted(REASON):
        R = REASON[name]
        tot = sum(v for k, v in R.items() if k != "...dealt damage")
        print(f"\n=== {name}  ({tot} shooting activations) ===")
        for reason, c in R.most_common():
            print(f"   {100*c/max(1,tot):5.1f}%  {reason}")
        ns = NEAREST[name]
        if ns:
            ns_sorted = sorted(ns)
            print(f"   distance to NEAREST enemy: median {ns_sorted[len(ns)//2]:.1f}\"  "
                  f"p10 {ns_sorted[len(ns)//10]:.1f}\"  min {ns_sorted[0]:.1f}\"")
    print("\nweapon ranges seen:")
    for k, c in RANGES.most_common():
        print(f"   {c:6d}  {k}")
