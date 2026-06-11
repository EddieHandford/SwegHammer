"""One-shot diagnostic: does a successful base-edge charge ever produce a melee
swing for 32mm-base units under the wave-240 default (SWEG_CHARGE_BASEEDGE=1)?

Hypothesis under test: the fight-eligibility gates (`pre_engaged` and
`in_range` in the fight routine) measure CENTRE distance <= 1.0", while the
base-edge placement parks a 32mm charger at centre distance ~2.26" and the
collision-aware pile-in stops at base contact (~1.26") — so the charge lands
but the fight never resolves. If true, melee is structurally crippled under
the adopted default and the wave-240 screen's melee-faction drops were a BUG,
not a faithful cost.

Run: PYTHONHASHSEED=0 python -m scripts.diag_fightgate_check
"""
from __future__ import annotations

import os
import random


def run(gate: str) -> dict:
    os.environ["SWEG_CHARGE_BASEEDGE"] = gate
    # Fresh import state per arm is unnecessary — the gate is read per call.
    from code.army import Army
    from code.events import EventLog, UnitCharged, UnitFought
    from code.map import Map, Objective
    from code.simulator import Battle
    from code.units import UnitProfile

    def melee_profile(name: str) -> UnitProfile:
        return UnitProfile(
            name=name, health=8, damage=1, hit_probability=0.5,
            ap=0, save=3, strength=4, toughness=4,
            attacks=1, weapon_damage_per_shot=1.0, range_inches=12,
            leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
            melee_attacks=6, melee_damage_per_shot=1.0,
            melee_hit_probability=0.66, melee_strength=5, melee_ap=1,
            move=6.0, base_diameter_mm=32,
        )

    random.seed(7)
    a = Army("A")
    b = Army("B")
    for i in range(4):
        a.add_unit(melee_profile("Bruiser"))
        b.add_unit(melee_profile("Brawler"))
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    m = Map(name="open", width=60.0, height=60.0, objectives=(obj,))
    log = EventLog()
    battle = Battle(a, b, map_=m, subscribers=[log])
    battle.run()

    charges = [e for e in log.events
               if isinstance(e, UnitCharged) and e.succeeded]
    fights = [e for e in log.events if isinstance(e, UnitFought)]
    return {
        "gate": gate,
        "successful_charges": len(charges),
        "melee_swings": len(fights),
        "total_melee_damage": sum(e.damage for e in fights),
    }


if __name__ == "__main__":
    on = run("1")
    off = run("0")
    for r in (on, off):
        print(f"SWEG_CHARGE_BASEEDGE={r['gate']}: "
              f"charges={r['successful_charges']} "
              f"swings={r['melee_swings']} "
              f"melee_damage={r['total_melee_damage']}")
    if on["successful_charges"] > 0 and on["melee_swings"] == 0 \
            and off["melee_swings"] > 0:
        print("CONFIRMED: base-edge placement strands chargers outside the "
              "centre-based fight gate — melee never resolves under the "
              "adopted default.")
    elif on["melee_swings"] > 0:
        print("NOT confirmed: melee resolves under the gate; "
              "investigate further.")
