"""Does the simulator over-value the units the real Votann winning list is built on?

The sourced Leagues of Votann list (task #34) was screened and moved the faction
from 61.4 to 77.3 in the A-frame against a real 48.0 - a residual of +29.3. A
KNOWN-GOOD 6-0 tournament list, faithfully fielded, wins 77 percent in the
simulator and about 48 percent in reality. That isolates the defect: it is not
the list, it is how these units are modelled.

This prints the catalogue profile of every unit in that list so each stat can be
checked against Wahapedia by hand. Prime suspect is the Hekaton Land Fortress -
the template's own comment calls it "T12 sv2+ 16HP, S18 AP-4 7.5 dam/shot,
devastating wounds - single biggest anti-tank pillar of the list", and the
sourced list runs THREE of them.

Run: PYTHONHASHSEED=0 python -m scripts._votann_profile_check
"""
from __future__ import annotations

from code.units import UNIT_CATALOG

KEYS = [
    "leagues_of_votann_hekaton_land_fortress",
    "leagues_of_votann_br_khyr_thunderkyn",
    "leagues_of_votann_thar_the_destined",
    "leagues_of_votann_hernkyn_yaegirs",
    "leagues_of_votann_cthonian_beserks",
    "leagues_of_votann_hernkyn_pioneers",
    "leagues_of_votann_br_khyr_iron_master",
]

FIELDS = ("invulnerable_save", "fnp", "devastating_wounds", "lethal_hits",
          "sustained_hits", "twin_linked", "blast", "heavy", "melta",
          "weapon_keywords", "keywords")


def main() -> None:
    for k in KEYS:
        p = UNIT_CATALOG.get(k)
        if p is None:
            print(f"{k}: NOT IN CATALOGUE")
            continue
        mm = max(1, getattr(p, "min_models", 1) or 1)
        print(f"=== {p.name}  ({p.points_cost:.0f} points/model, min {mm} "
              f"-> {p.points_cost*mm:.0f}/unit) ===")
        print(f"    Toughness {p.toughness}  Wounds {p.health}  Save {p.save}+")
        print(f"    RANGED  attacks {p.attacks}  range {p.range_inches}\"  "
              f"Strength {p.strength}  armour penetration {p.ap}  "
              f"damage {p.weapon_damage_per_shot}  hit probability "
              f"{p.hit_probability:.2f}")
        print(f"    MELEE   attacks {p.melee_attacks}  Strength "
              f"{p.melee_strength}  armour penetration {p.melee_ap}  "
              f"damage {p.melee_damage_per_shot}  hit probability "
              f"{p.melee_hit_probability:.2f}")
        extra = []
        for f in FIELDS:
            v = getattr(p, f, None)
            if v not in (None, 0, False, "", (), []):
                extra.append(f"{f}={v}")
        if extra:
            print("    " + "  ".join(str(e)[:90] for e in extra))
        print()


if __name__ == "__main__":
    main()
