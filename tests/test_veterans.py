"""Wave 217 — Chaos Space Marines Legionaries "Veterans of the Long War"
(gated SWEG_VETERANS). Verifies the melee wound step actually USES the ability:
in melee the unit re-rolls Wound rolls of 1, and when the target is within range
of an objective marker (`Unit.on_objective`) it re-rolls the full failed Wound
roll instead. Ranged attacks are unaffected, and the gate-off path reproduces the
no-ability behaviour.

Construction: the attacker always hits (so only the Wound roll varies), wounds on
5+ (Strength 3 vs Toughness 5) so re-rolls have measurable headroom, and the
defender has a large health pool so damage accumulates. The defender's save is
held constant across arms, so the damage DELTA between arms isolates the Wound
re-roll.
"""
from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _legionary(name: str = "Legionaries", veterans: bool = True) -> UnitProfile:
    # Identical melee + ranged weapons: always hits, S3 vs T5 wounds on 5+, AP0.
    return UnitProfile(
        name=name, health=4, damage=1, hit_probability=1.0,
        ap=0, save=3, strength=3, toughness=4,
        attacks=6, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=6, faction="Chaos Space Marines", points_override=100.0,
        unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=1.0, melee_strength=3, melee_ap=0,
        veterans_of_the_long_war=veterans,
    )


def _dummy(name: str = "Dummy") -> UnitProfile:
    return UnitProfile(
        name=name, health=600, damage=1, hit_probability=0.5,
        ap=0, save=6, strength=4, toughness=5,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Astra Militarum", points_override=100.0,
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )


def _setup(veterans: bool = True):
    a = Army("Atk"); a.add_unit(_legionary(veterans=veterans))
    b = Army("Def"); b.add_unit(_dummy())
    battle = Battle(a, b); battle._assign_uids()
    return a.units[0], b.units[0]


def _accum(attacker, defender, mode: str, on_objective: bool = False, n: int = 8000) -> float:
    random.seed(0)
    defender.on_objective = on_objective
    total = 0.0
    dist = 0.5 if mode == "melee" else 12.0
    for _ in range(n):
        defender.current_health = defender.profile.health
        total += attacker.attack(defender, distance=dist, mode=mode)
    return total


class VeteransOfTheLongWarTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SWEG_VETERANS", None)

    def test_melee_rerolls_wound_ones(self):
        # Default ON: a Legionary re-rolls melee Wound rolls of 1, so it deals
        # clearly more melee damage than an otherwise-identical non-veteran unit.
        os.environ.pop("SWEG_VETERANS", None)
        vet_atk, vet_def = _setup(veterans=True)
        plain_atk, plain_def = _setup(veterans=False)
        vet = _accum(vet_atk, vet_def, "melee")
        plain = _accum(plain_atk, plain_def, "melee")
        self.assertGreater(
            vet, plain * 1.06,
            f"veteran melee must re-roll wound 1s: vet={vet:.0f} plain={plain:.0f}",
        )

    def test_objective_upgrades_to_full_reroll(self):
        # Target within range of an objective marker → re-roll the full failed
        # Wound roll, dealing clearly more than the wound-1s-only (no-objective) arm.
        os.environ.pop("SWEG_VETERANS", None)
        atk, dfn = _setup(veterans=True)
        no_obj = _accum(atk, dfn, "melee", on_objective=False)
        on_obj = _accum(atk, dfn, "melee", on_objective=True)
        self.assertGreater(
            on_obj, no_obj * 1.12,
            f"objective upgrades to full wound re-roll: on_obj={on_obj:.0f} no_obj={no_obj:.0f}",
        )

    def test_ranged_unaffected(self):
        # The ability is melee-only: ranged damage is identical with or without it,
        # even when the target is on an objective.
        os.environ.pop("SWEG_VETERANS", None)
        vet_atk, vet_def = _setup(veterans=True)
        plain_atk, plain_def = _setup(veterans=False)
        vet = _accum(vet_atk, vet_def, "ranged", on_objective=True)
        plain = _accum(plain_atk, plain_def, "ranged", on_objective=True)
        self.assertAlmostEqual(
            vet, plain, delta=max(plain * 0.03, 1.0),
            msg=f"ranged must be unaffected by Veterans: vet={vet:.0f} plain={plain:.0f}",
        )

    def test_gate_off_equals_no_ability(self):
        # SWEG_VETERANS=0: the veteran unit's melee damage falls back to the
        # no-ability baseline (no wound re-roll), even on an objective.
        os.environ["SWEG_VETERANS"] = "0"
        vet_atk, vet_def = _setup(veterans=True)
        plain_atk, plain_def = _setup(veterans=False)
        vet = _accum(vet_atk, vet_def, "melee", on_objective=True)
        plain = _accum(plain_atk, plain_def, "melee", on_objective=True)
        self.assertAlmostEqual(
            vet, plain, delta=max(plain * 0.04, 1.0),
            msg=f"gate off: veteran melee should ~= non-veteran: vet={vet:.0f} plain={plain:.0f}",
        )


if __name__ == "__main__":
    unittest.main()
