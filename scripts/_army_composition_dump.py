"""Print the archetype army a faction actually fields, with anti-armour reach.

PILOT_PROTOCOL requires checking the archetype list against the real sourced
list before calling any pole structural. This dumps what the builder produces:
models per datasheet, points, and — because the Tyranid secondary breakdown
shows the deficit is entirely kill cards — how much of the list can actually
threaten a Toughness-10 or higher target.

Run: PYTHONHASHSEED=0 AC_FACTION=Tyranids python -m scripts._army_composition_dump
"""
from __future__ import annotations
import collections
import os
import random

from code.army_builder import build_faction_random_army
from code.roles import combat_profile
from code.units import wound_probability

FAC = os.environ.get("AC_FACTION", "Tyranids")
SEEDS = [int(s) for s in os.environ.get("AC_SEEDS", "0,1,2").split(",")]
HARD_T = int(os.environ.get("AC_HARD_T", "10"))   # a Toughness-10 vehicle
HARD_SV = int(os.environ.get("AC_HARD_SV", "3"))


def _eff(attacks, hit_p, s, ap, dmg, t, sv) -> float:
    if not attacks or not hit_p:
        return 0.0
    sv_after = max(2, sv - (ap or 0))
    unsaved = max(0.0, 1.0 - (7 - sv_after) / 6.0) if sv_after <= 6 else 1.0
    return attacks * hit_p * wound_probability(s, t) * unsaved * (dmg or 1.0)


def main() -> None:
    for seed in SEEDS:
        army = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed),
                                         use_archetype=True)
        models = collections.Counter()
        prof = {}
        for u in army.units:
            n = u.profile.name or "?"
            models[n] += 1
            prof[n] = u.profile
        pts = sum(prof[n].points_cost * c for n, c in models.items())
        print(f"=== {FAC} archetype army, seed {seed} "
              f"({sum(models.values())} models, ~{pts} points) ===")
        anti = 0.0
        total = 0.0
        for n, c in models.most_common():
            p = prof[n]
            m = _eff(p.melee_attacks, p.melee_hit_probability, p.melee_strength,
                     p.melee_ap, p.melee_damage_per_shot, HARD_T, HARD_SV)
            r = _eff(p.attacks, p.hit_probability, p.strength, p.ap,
                     p.weapon_damage_per_shot, HARD_T, HARD_SV)
            best = max(m, r) * c
            total += best
            if max(m, r) >= 0.5:      # can meaningfully hurt a hard target
                anti += best
            print(f"  {c:3d}x {n[:34]:<34} {combat_profile(p):<11} "
                  f"T{p.toughness} W{p.health}  "
                  f"vs T{HARD_T}/Sv{HARD_SV}+: melee {m:5.2f} ranged {r:5.2f}"
                  f"{'   <-- ANTI-ARMOUR' if max(m, r) >= 0.5 else ''}")
        print(f"  ---- damage per round into a Toughness-{HARD_T} Save-{HARD_SV}+ "
              f"target: {total:.1f} total, {anti:.1f} from units that individually "
              f"clear 0.5 ({100*anti/max(total,1e-9):.0f}%)")
        print()


if __name__ == "__main__":
    main()
