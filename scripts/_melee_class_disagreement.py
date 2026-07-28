"""How often does strategy._is_melee_class disagree with roles' damage model?

`strategy._is_melee_class` decides whether a unit pinned in melee should STAY and
fight (melee-primary) or Fall Back to free its guns. It estimates damage as

    attacks * hit_probability * damage_per_shot

omitting the wound roll, Strength versus Toughness, armour penetration and the
armour save — all four of which `roles.expected_ranged_dpa` /
`expected_melee_dpa` do model. It also carries ASYMMETRIC fallbacks:
`melee_damage_per_shot or 1.0` against `weapon_damage_per_shot or 0.0`, so a
missing melee damage value scores 1 while a missing ranged value scores 0.

The live probe (scripts/_pinned_gunline_probe.py) found the two functions
disagree on 40.8 percent of pinned ranged-primary activations. This attributes
the disagreement per unit and separates the two causes.

Run: PYTHONHASHSEED=0 python -m scripts._melee_class_disagreement
"""
from __future__ import annotations
import collections

from code.roles import expected_melee_dpa, expected_ranged_dpa
from code.strategy import _is_melee_class
from code.units import UNIT_CATALOG


def main() -> None:
    disagree_stay = []   # strategy says melee (STAY), roles says ranged-primary
    disagree_go = []     # strategy says ranged (GO), roles says melee-primary
    agree = 0
    missing_ranged_dmg = 0
    for key, p in UNIT_CATALOG.items():
        r, m = expected_ranged_dpa(p), expected_melee_dpa(p)
        roles_melee_primary = m >= r
        strat_melee_primary = _is_melee_class(p)
        if roles_melee_primary == strat_melee_primary:
            agree += 1
            continue
        # Does the asymmetric fallback explain this one?
        fallback = (not (p.weapon_damage_per_shot or 0.0)) and (p.attacks or 0) > 0
        if fallback:
            missing_ranged_dmg += 1
        row = (p.faction or "?", p.name or key, round(r, 2), round(m, 2), fallback)
        (disagree_stay if strat_melee_primary else disagree_go).append(row)

    tot = len(UNIT_CATALOG)
    n_dis = len(disagree_stay) + len(disagree_go)
    print("=== strategy._is_melee_class versus the roles damage model ===")
    print(f"    catalogue units:                              {tot}")
    print(f"    agree:                                        {agree}")
    print(f"    DISAGREE:                                     {n_dis} "
          f"({100*n_dis/tot:.1f}%)")
    print()
    print(f"    strategy says STAY, roles says ranged-primary: {len(disagree_stay)}"
          "   <- gunline told to stay in melee")
    print(f"    strategy says GO,   roles says melee-primary:  {len(disagree_go)}"
          "   <- melee unit told to walk away")
    print(f"    explained by the `or 0.0` / `or 1.0` asymmetry: {missing_ranged_dmg}")
    print()
    byfac = collections.Counter(r[0] for r in disagree_stay)
    print("    STAY-disagreement by faction (top 12):")
    for f, c in byfac.most_common(12):
        print(f"      {f:<24} {c}")
    print()
    print("    worst STAY disagreements (ranged damage per activation it forfeits):")
    for row in sorted(disagree_stay, key=lambda x: -(x[2] - x[3]))[:15]:
        flag = "  [missing ranged damage value]" if row[4] else ""
        print(f"      {row[0]:<22} {row[1]:<32} ranged {row[2]:>6} vs melee "
              f"{row[3]:>5}{flag}")


if __name__ == "__main__":
    main()
