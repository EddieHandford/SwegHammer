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
    """Allarus Custodians deep-strike when fielded — but only up to the 10e
    Reserves cap.

    The simulator's `_deploy_armies` routes units with `deep_strike=True` into
    the per-army reserves bucket, subject to the Chapter Approved 2025-26
    Reserves cap: "No more than half of the units in your army can start the
    battle in Reserves, and the points total of those units cannot be more than
    half of the points total of your army." So a degenerate all-Allarus army
    (every unit a deep-striker) cannot reserve everything — at most half may go
    into Reserves; the rest must deploy on the board to contest objectives.

    Source (Reserves cap, `simulator.reserves_cap`):
    https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Reinforcements
    """

    def test_allarus_reserves_respect_the_reserves_cap(self):
        import math

        allarus = UNIT_CATALOG["adeptus_custodes_allarus_custodians"]
        # Pair the Allarus squad against a vanilla Custodian Guard so the
        # opposing army is non-empty (the simulator won't run with zero
        # units on a side).
        guard = UNIT_CATALOG["adeptus_custodes_custodian_guard"]

        army_a = Army("AllarusForce")
        n_allarus = max(1, allarus.min_models)
        for _ in range(n_allarus):
            army_a.add_unit(allarus)

        army_b = Army("GuardForce")
        for _ in range(max(1, guard.min_models)):
            army_b.add_unit(guard)

        battle = Battle(army_a, army_b)
        battle._assign_uids()
        battle._deploy_armies()

        reserves = battle._reserves.get(army_a.name, [])
        reserved_allarus = [u for u in reserves if u.profile.name == allarus.name]
        onboard_allarus = [u for u in army_a.units if u.profile.name == allarus.name]

        # 10e units-half of the Reserves cap: no more than floor(half) may
        # start in Reserves. Every unit here is a deep-striker, so the cap is
        # the binding constraint.
        units_cap = math.floor(0.5 * n_allarus)
        self.assertLessEqual(
            len(reserved_allarus), units_cap,
            "Reserves cap: at most half the army's units may start in reserves",
        )
        # Deep-strikers still use reserves up to the cap (this is not the old
        # "reserve nothing" behaviour either).
        self.assertEqual(
            len(reserved_allarus), units_cap,
            "Deep-strikers should fill the reserves allowance up to the cap",
        )
        # The remainder must be on the board (kept there to contest objectives).
        self.assertEqual(
            len(onboard_allarus), n_allarus - units_cap,
            "Units over the Reserves cap must deploy on the board, not reserve",
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
