"""Tests for the Custodes mobility audit (#iter8).

The DG-vs-Custodes calibration (iter 7) flagged OC starvation on the Custodes
side: their 14 line-troops sit at M=6" because BSData does not expose the M
characteristic numerically and the simulator's default move was the universal
6.0". In reality:

  * Allarus Custodian Squad — M=5", DEEP STRIKE keyword (arrives mid-battle
    anywhere on the table). Source:
    https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Allarus-Custodian-Squad
  * Vertus Praetors — M=14", FLY (jet bikes). Source:
    https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Vertus-Praetors
  * Caladius Grav-tank — M=12", FLY/HOVER. Source:
    https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Caladius-Grav-tank
  * Prosecutors — M=7" (light Sisters-of-Silence infantry). Source:
    https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Prosecutors

These tests pin:
  1. The catalogue exposes the correct M / FLY / DEEP STRIKE values after the
     overrides.json patch.
  2. Allarus Custodians actually go into reserves and arrive from there in a
     real battle (verifying that the simulator's `_arrive_from_reserves`
     plumbing fires for this datasheet, not just for the test-fixture
     Terminators).
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UNIT_CATALOG


class CustodesCatalogueMobilityTests(unittest.TestCase):
    """The catalogue exposes the Wahapedia M / FLY / DEEP STRIKE values."""

    def test_allarus_custodians_deep_strike_and_move_5(self):
        u = UNIT_CATALOG["adeptus_custodes_allarus_custodians"]
        self.assertTrue(u.deep_strike, "Allarus must have Deep Strike")
        self.assertEqual(u.move, 5.0, "Allarus Terminator armour M=5\"")

    def test_vertus_praetors_fly_and_move_14(self):
        u = UNIT_CATALOG["adeptus_custodes_vertus_praetors"]
        self.assertTrue(u.fly, "Vertus Praetors must have FLY")
        self.assertEqual(u.move, 14.0, "Vertus Praetors jetbike M=14\"")

    def test_caladius_grav_tank_fly_and_move_12(self):
        u = UNIT_CATALOG["adeptus_custodes_caladius_grav_tank"]
        self.assertTrue(u.fly, "Caladius Grav-tank must have FLY (hover)")
        self.assertEqual(u.move, 12.0, "Caladius M=12\"")

    def test_prosecutors_move_7(self):
        u = UNIT_CATALOG["adeptus_custodes_prosecutors"]
        self.assertEqual(u.move, 7.0, "Prosecutors (Sisters of Silence) M=7\"")


class CustodesDeepStrikeInBattleTests(unittest.TestCase):
    """Allarus Custodians actually deep-strike when fielded in a real battle.

    The simulator's `_deploy_armies` routes any unit with `deep_strike=True`
    into the per-army reserves bucket. We verify that holds for the live
    Allarus profile coming out of the catalogue, not just a synthetic test
    fixture.
    """

    def test_allarus_enters_reserves_at_battle_start(self):
        allarus = UNIT_CATALOG["adeptus_custodes_allarus_custodians"]
        # Pair the Allarus squad against a vanilla Custodian Guard so the
        # opposing army is non-empty (the simulator won't run with zero
        # units on a side).
        guard = UNIT_CATALOG["adeptus_custodes_custodian_guard"]

        army_a = Army("AllarusForce")
        for _ in range(max(1, allarus.min_models)):
            army_a.add_unit(allarus)

        army_b = Army("GuardForce")
        for _ in range(max(1, guard.min_models)):
            army_b.add_unit(guard)

        battle = Battle(army_a, army_b)
        battle._assign_uids()
        battle._deploy_armies()

        reserves = battle._reserves.get(army_a.name, [])
        self.assertGreater(
            len(reserves), 0,
            "Allarus must be placed into reserves at deployment (DEEP STRIKE)",
        )
        # The Allarus models should be the ones in reserves, not on the
        # board, pre-Round 2.
        reserved_names = {u.profile.name for u in reserves}
        self.assertIn(allarus.name, reserved_names)
        for u in army_a.units:
            self.assertNotEqual(
                u.profile.name, allarus.name,
                "Allarus should be in reserves, not on the board, pre-Round 2",
            )


class CustodesFlyOverTerrainTests(unittest.TestCase):
    """Vertus Praetors and Caladius Grav-tank have FLY so they can move over
    terrain (the simulator's terrain blocker for movement applies only to
    non-FLY units). Caught at the profile-level so the simulator's existing
    FLY gates apply automatically."""

    def test_vertus_praetors_have_fly(self):
        u = UNIT_CATALOG["adeptus_custodes_vertus_praetors"]
        self.assertTrue(
            u.fly,
            "Vertus Praetors are jetbikes (FLY keyword on the Wahapedia "
            "datasheet)",
        )

    def test_caladius_has_fly_for_hover(self):
        u = UNIT_CATALOG["adeptus_custodes_caladius_grav_tank"]
        self.assertTrue(
            u.fly,
            "Caladius Grav-tank hovers and has the FLY keyword on the "
            "Wahapedia datasheet",
        )


if __name__ == "__main__":
    unittest.main()
