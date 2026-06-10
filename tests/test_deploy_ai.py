"""Tests for the holding-force deployment heuristic (SWEG_DEPLOY_AI gate).

The bug being fixed: with the gate OFF (default), every deep_strike unit and
every Genestealer Cults unit is sent to reserves — so Chaos Daemons and GSC
deploy 0 units at game start and lose the primary-VP race in Rounds 1-2.

The fix (SWEG_DEPLOY_AI=1): an AI piloting heuristic keeps a board-holding
force on the table.  The algorithm:
  * Compute total army OC and already-on-board OC.
  * Sort reservable candidates (deep_strike or GSC) by OC desc, then by
    points_cost desc.
  * Promote candidates to on-board until cumulative on-board OC >= 0.5 * total.
  * Remaining lower-OC / alpha-strike units stay in reserves.
  * Armies with <2 reservable units are left unchanged.

Gate OFF: byte-identical to the legacy all-in-reserves path.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile builders
# ---------------------------------------------------------------------------

def _daemon_profile(name: str = "Bloodletter", *, oc: int = 1,
                    deep_strike: bool = True,
                    points_per_squad: float = 100.0,
                    **overrides) -> UnitProfile:
    """A Chaos Daemons unit — deep_strike=True (most Daemons have this)."""
    base = dict(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=-1, save=5, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=1,
        leadership=7, oc=oc,
        faction="Chaos Daemons",
        unit_keywords=("INFANTRY", "DAEMON"),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=-1,
        deep_strike=deep_strike,
        points_per_squad=points_per_squad,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _gsc_profile(name: str = "Neophyte Hybrid", *, oc: int = 2,
                 points_per_squad: float = 80.0,
                 **overrides) -> UnitProfile:
    """A Genestealer Cults unit — GSC faction routes the whole army to reserves."""
    base = dict(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7, oc=oc,
        faction="Genestealer Cults",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        deep_strike=False,
        points_per_squad=points_per_squad,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _ground_profile(name: str = "Guardsman") -> UnitProfile:
    """Non-reservable filler unit — stays on board regardless of gate."""
    return UnitProfile(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, oc=1,
        faction="Astra Militarum",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
    )


def _deploy(army_a: Army, army_b: Army, *, gate_on: bool) -> Battle:
    """Deploy both armies with SWEG_DEPLOY_AI set/unset; return the Battle."""
    prev = os.environ.get("SWEG_DEPLOY_AI")
    os.environ["SWEG_DEPLOY_AI"] = "1" if gate_on else "0"
    try:
        battle = Battle(army_a, army_b)
        battle._assign_uids()
        battle._deploy_armies()
        return battle
    finally:
        if prev is None:
            os.environ.pop("SWEG_DEPLOY_AI", None)
        else:
            os.environ["SWEG_DEPLOY_AI"] = prev


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _total_oc(units) -> int:
    return sum(u.profile.oc or 0 for u in units)


# ---------------------------------------------------------------------------
# Gate OFF — behaviour must be byte-identical to old path
# ---------------------------------------------------------------------------

class GateOffLegacyTests(unittest.TestCase):
    """With SWEG_DEPLOY_AI=0 (default) the old all-reserves path is unchanged."""

    def test_daemons_all_reserved_gate_off(self):
        """Gate OFF: all deep_strike Daemons go to reserves (old behaviour)."""
        random.seed(42)
        cult = Army("Daemons")
        for i in range(5):
            cult.add_unit(_daemon_profile(f"Bloodletter {i}", oc=1))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        battle = _deploy(cult, enemy, gate_on=False)

        self.assertEqual(len(cult.units), 0,
            "Gate OFF: all deep_strike Daemons should be in reserves")
        self.assertEqual(len(battle._reserves[cult.name]), 5)

    def test_gsc_all_reserved_gate_off(self):
        """Gate OFF: all GSC units go to reserves (old Cult Ambush behaviour)."""
        random.seed(42)
        gsc = Army("Cult")
        for i in range(4):
            gsc.add_unit(_gsc_profile(f"Neophyte {i}", oc=2))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        battle = _deploy(gsc, enemy, gate_on=False)

        self.assertEqual(len(gsc.units), 0,
            "Gate OFF: all GSC units should be in reserves")
        self.assertEqual(len(battle._reserves[gsc.name]), 4)


# ---------------------------------------------------------------------------
# Gate ON — holding-force heuristic
# ---------------------------------------------------------------------------

class GateOnHoldingForceTests(unittest.TestCase):
    """With SWEG_DEPLOY_AI=1 the heuristic keeps high-OC units on the board."""

    def test_daemons_non_zero_on_board(self):
        """Gate ON: at least one Daemons unit must be on the board (not all reserved)."""
        random.seed(7)
        daemons = Army("Daemons")
        # Mix: some high-OC Bloodthirster-ish (oc=5) and low-OC strikers (oc=1).
        daemons.add_unit(_daemon_profile("Bloodthirster", oc=5, points_per_squad=350.0))
        for i in range(4):
            daemons.add_unit(_daemon_profile(f"Bloodletter {i}", oc=1, points_per_squad=80.0))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        battle = _deploy(daemons, enemy, gate_on=True)

        on_board_count = len(daemons.units)
        self.assertGreater(on_board_count, 0,
            "Gate ON: Daemons must have at least 1 unit on the board at deployment")

    def test_on_board_oc_at_least_half_total(self):
        """Gate ON: on-board OC must be >= 50% of total army OC."""
        random.seed(7)
        daemons = Army("Daemons")
        daemons.add_unit(_daemon_profile("Bloodthirster", oc=5, points_per_squad=350.0))
        for i in range(4):
            daemons.add_unit(_daemon_profile(f"Bloodletter {i}", oc=1, points_per_squad=80.0))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        all_units = list(daemons.units)  # snapshot before deploy mutates
        battle = _deploy(daemons, enemy, gate_on=True)

        total_oc = _total_oc(all_units)
        on_board_oc = _total_oc(daemons.units)
        self.assertGreaterEqual(
            on_board_oc, 0.5 * total_oc - 1e-6,
            f"Gate ON: on-board OC {on_board_oc} < 50% of total {total_oc}",
        )

    def test_high_oc_units_preferred_on_board(self):
        """Gate ON: the highest-OC reservable unit should be on the board."""
        random.seed(7)
        daemons = Army("Daemons")
        # Bloodthirster has OC 5 — should be the one promoted to on-board.
        daemons.add_unit(_daemon_profile("Bloodthirster", oc=5, points_per_squad=350.0))
        for i in range(3):
            daemons.add_unit(_daemon_profile(f"Bloodletter {i}", oc=1, points_per_squad=80.0))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        battle = _deploy(daemons, enemy, gate_on=True)

        on_board_names = {u.profile.name for u in daemons.units}
        self.assertIn("Bloodthirster", on_board_names,
            "Gate ON: highest-OC unit (Bloodthirster, OC 5) must be promoted to on-board")

    def test_gsc_non_zero_on_board(self):
        """Gate ON: GSC army must have at least 1 unit on the board."""
        random.seed(7)
        gsc = Army("Cult")
        # High-OC blob (OC 2 each) as the holding force.
        for i in range(5):
            gsc.add_unit(_gsc_profile(f"Neophyte {i}", oc=2, points_per_squad=80.0))
        # Magus with OC 1 — less valuable as a holder, should stay in reserves.
        gsc.add_unit(_gsc_profile("Magus", oc=1, points_per_squad=60.0))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        # GSC cult_ambush_pending flags are set in _deploy_armies; the heuristic
        # must still promote units to on-board despite the GSC path.
        battle = _deploy(gsc, enemy, gate_on=True)

        on_board_count = len(gsc.units)
        self.assertGreater(on_board_count, 0,
            "Gate ON: GSC must have at least 1 unit on the board at deployment")

    def test_gsc_on_board_oc_at_least_half_total(self):
        """Gate ON: GSC on-board OC >= 50% of total army OC."""
        random.seed(7)
        gsc = Army("Cult")
        for i in range(5):
            gsc.add_unit(_gsc_profile(f"Neophyte {i}", oc=2, points_per_squad=80.0))
        gsc.add_unit(_gsc_profile("Magus", oc=1, points_per_squad=60.0))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        all_units = list(gsc.units)
        battle = _deploy(gsc, enemy, gate_on=True)

        total_oc = _total_oc(all_units)
        on_board_oc = _total_oc(gsc.units)
        self.assertGreaterEqual(
            on_board_oc, 0.5 * total_oc - 1e-6,
            f"Gate ON GSC: on-board OC {on_board_oc} < 50% of total {total_oc}",
        )

    def test_some_units_still_reserved(self):
        """Gate ON: the lower-OC alpha-strikers must remain in reserves."""
        random.seed(7)
        daemons = Army("Daemons")
        # If OC is uniform, the algorithm will stop as soon as it hits 50%.
        # With 6 units of OC 1 each, total OC = 6, so 3 go on board, 3 stay.
        for i in range(6):
            daemons.add_unit(_daemon_profile(f"Bloodletter {i}", oc=1))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        battle = _deploy(daemons, enemy, gate_on=True)

        reserved_count = len(battle._reserves[daemons.name])
        on_board_count = len(daemons.units)
        self.assertGreater(reserved_count, 0,
            "Gate ON: some units should remain in reserves (alpha-strikers)")
        self.assertGreater(on_board_count, 0,
            "Gate ON: some units should be on the board (holders)")

    def test_single_reservable_unit_unchanged(self):
        """Gate ON: an army with only 1 reservable unit is left as-is (<2 threshold)."""
        random.seed(7)
        mixed = Army("Mixed")
        mixed.add_unit(_daemon_profile("Lone DS Unit", oc=3))
        # Non-reservable unit already on board.
        mixed.add_unit(_ground_profile("GroundUnit"))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("Guard"))

        battle = _deploy(mixed, enemy, gate_on=True)

        # With only 1 reservable unit, the heuristic does not split — it stays
        # in reserves unchanged (the GroundUnit is already on board, so the
        # army is not completely empty anyway).
        reserved_names = {u.profile.name for u in battle._reserves[mixed.name]}
        self.assertIn("Lone DS Unit", reserved_names,
            "Gate ON: single-reservable-unit army must leave it in reserves (no split)")
        on_board_names = {u.profile.name for u in mixed.units}
        self.assertIn("GroundUnit", on_board_names)


# ---------------------------------------------------------------------------
# Non-reservable armies are unaffected
# ---------------------------------------------------------------------------

class NonReservableArmyTests(unittest.TestCase):
    """Armies with no deep_strike / GSC units are untouched by the gate."""

    def test_ground_army_unaffected(self):
        """A standard ground army deploys all units on the board regardless of gate."""
        random.seed(0)
        guard = Army("Guard")
        for i in range(4):
            guard.add_unit(_ground_profile(f"Trooper {i}"))
        enemy = Army("Enemy")
        enemy.add_unit(_ground_profile("EnemyA"))

        battle = _deploy(guard, enemy, gate_on=True)

        self.assertEqual(len(guard.units), 4)
        self.assertEqual(len(battle._reserves[guard.name]), 0)


if __name__ == "__main__":
    unittest.main()
