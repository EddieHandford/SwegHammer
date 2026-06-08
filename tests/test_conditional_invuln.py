"""Task #92 — per-attack-type invulnerable save, at the save step (gated
SWEG_COND_INVULN). Verifies the save step actually USES the conditional invuln:
a Wyches-like defender (4+ invulnerable save against melee, 6+ against ranged)
takes less damage from melee than from an otherwise-identical ranged attack.

Construction: the attacker's melee and ranged weapons are identical (same
Attacks / Strength / AP / Damage, always hits), and its AP is high enough to
bypass the defender's poor armour save, so the ONLY thing that differs between
the two modes is the defender's per-attack invulnerable save.
"""
from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _wyches_like(name: str = "Wyches") -> UnitProfile:
    # Poor 6+ armour so the invuln is the operative save; conditional invuln
    # 4+ vs melee / 6+ vs ranged; large health pool so damage accumulates.
    return UnitProfile(
        name=name, health=500, damage=1, hit_probability=0.5,
        ap=0, save=6, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=12,
        leadership=7, faction="Drukhari", points_override=100.0,
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        invuln_save=6, invuln_save_melee=4, invuln_save_ranged=6,
    )


def _piercer(name: str = "Piercer") -> UnitProfile:
    # Identical melee + ranged weapons: always hits, S8 vs T4 wounds on 2+, AP-3
    # bypasses the 6+ armour so the invuln is what matters.
    return UnitProfile(
        name=name, health=4, damage=1, hit_probability=1.0,
        ap=-3, save=3, strength=8, toughness=4,
        attacks=6, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, faction="Adeptus Astartes", points_override=100.0,
        unit_keywords=("INFANTRY",),
        melee_attacks=6, melee_damage_per_shot=1.0,
        melee_hit_probability=1.0, melee_strength=8, melee_ap=-3,
    )


def _setup():
    a = Army("Atk"); a.add_unit(_piercer())
    b = Army("Def"); b.add_unit(_wyches_like())
    battle = Battle(a, b); battle._assign_uids()
    return a.units[0], b.units[0]


def _accum(attacker, defender, mode: str, n: int = 4000) -> float:
    random.seed(0)
    total = 0.0
    dist = 0.5 if mode == "melee" else 12.0
    for _ in range(n):
        defender.current_health = defender.profile.health
        total += attacker.attack(defender, distance=dist, mode=mode)
    return total


class ConditionalInvulnSaveTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SWEG_COND_INVULN", None)

    def test_default_melee_invuln_blocks_more_than_ranged(self):
        # Per-attack ON (default): 4+ vs melee blocks ~50%, 6+ vs ranged ~17%,
        # so melee should deal clearly less damage.
        os.environ.pop("SWEG_COND_INVULN", None)
        atk, dfn = _setup()
        melee = _accum(atk, dfn, "melee")
        ranged = _accum(atk, dfn, "ranged")
        self.assertLess(
            melee, ranged * 0.85,
            f"melee invuln 4+ must block more than ranged 6+: melee={melee:.0f} ranged={ranged:.0f}",
        )

    def test_gate_off_melee_equals_ranged(self):
        # SWEG_COND_INVULN=0: both modes fall back to the single invuln_save (6+)
        # — Wyches are not invuln_ranged_only — so melee ≈ ranged.
        os.environ["SWEG_COND_INVULN"] = "0"
        atk, dfn = _setup()
        melee = _accum(atk, dfn, "melee")
        ranged = _accum(atk, dfn, "ranged")
        self.assertAlmostEqual(
            melee, ranged, delta=ranged * 0.1,
            msg=f"gate off: melee should ~= ranged (both 6+): melee={melee:.0f} ranged={ranged:.0f}",
        )


if __name__ == "__main__":
    unittest.main()
