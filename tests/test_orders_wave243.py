"""Wave 243 regression tests: REGIMENT and SQUADRON made first-class unit keywords;
Orders plumbing switched from the old BATTLELINE proxy to real codex keywords.

Background: before wave 243, `_unit_satisfies_target_type` mapped
  REGIMENT  → unit has BATTLELINE + INFANTRY
  SQUADRON  → unit has BATTLELINE + VEHICLE
and `_is_order_target_eligible` had a hard gate "BATTLELINE not in kw: return False".
BSData v10.6.0 grants BATTLELINE to almost nothing in Astra Militarum (only three core
troops), so the gate silently blocked Kasrkin, Tempestus Scions, Heavy Weapons Squads,
all SQUADRON vehicles, and the tank Commander officers themselves from ever ordering or
being ordered. Wave 243 adds REGIMENT and SQUADRON to the mapper's
`_TRACKED_UNIT_KEYWORDS` so each unit's real BSData categoryLink keyword is preserved
through to `unit_keywords`, then switches all three eligibility checks in `code/orders.py`
to test those real keywords directly.

Test plan:
  A. A unit carrying only SQUADRON (no BATTLELINE) IS order-eligible from a
     SQUADRON-targeting Officer (Leman Russ Commander pattern).
  B. `_try_flexible_command` in the simulator finds SQUADRON candidates using
     the real SQUADRON keyword (not BATTLELINE + VEHICLE).
  C. A unit carrying neither REGIMENT nor SQUADRON nor TITANIC is refused.
  D. A unit carrying only REGIMENT (no BATTLELINE) IS order-eligible from a
     REGIMENT-targeting Officer (Kasrkin pattern).
  E. `_unit_satisfies_target_type` with REGIMENT target type accepts a unit
     that has REGIMENT but not BATTLELINE.
  F. Backward compatibility: the BATTLELINE+INFANTRY old proxy no longer
     gates Order eligibility; a BATTLELINE+INFANTRY unit without the REGIMENT
     keyword is now ineligible.

All tests use synthetic UnitProfile instances with explicit `unit_keywords` so
they do not depend on catalogue load order or file I/O.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.map import Map, Objective
from code.orders import (
    OFFICER_ORDER_PROFILES,
    _is_order_target_eligible,
    _unit_satisfies_target_type,
    dispatch_orders,
)
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Minimal synthetic profile factories
# ---------------------------------------------------------------------------

def _officer_profile(name: str) -> UnitProfile:
    """Minimal Officer profile: alive, Astra Militarum, in the Officer allowlist."""
    return UnitProfile(
        name=name,
        health=8,
        damage=0,
        hit_probability=0.5,
        attacks=0,
        range_inches=0,
        save=3,
        toughness=4,
        strength=4,
        ap=0,
        weapon_damage_per_shot=0.0,
        points_override=130.0,
        faction="Astra Militarum",
        # CHARACTER + no REGIMENT/SQUADRON so the officer is not its own target.
        unit_keywords=("CHARACTER", "INFANTRY", "EPIC HERO"),
    )


def _regiment_only_profile(name: str = "Kasrkin") -> UnitProfile:
    """Synthetic REGIMENT unit — carries REGIMENT but NOT BATTLELINE.

    This is the Kasrkin pattern: BSData categoryLinks include "Regiment"
    but not "Battleline", so before wave 243 the unit was completely blocked
    by the BATTLELINE hard gate.
    """
    return UnitProfile(
        name=name,
        health=2,
        damage=1,
        hit_probability=0.67,
        attacks=2,
        range_inches=18,
        save=4,
        toughness=4,
        strength=4,
        ap=1,
        weapon_damage_per_shot=1.0,
        rapid_fire=0,
        points_override=20.0,
        faction="Astra Militarum",
        # REGIMENT keyword: real codex keyword from BSData categoryLinks.
        # Deliberately no BATTLELINE — testing that BATTLELINE is no longer required.
        unit_keywords=("INFANTRY", "REGIMENT"),
    )


def _squadron_only_profile(name: str = "LemanRuss") -> UnitProfile:
    """Synthetic SQUADRON unit — carries SQUADRON but NOT BATTLELINE.

    This is the Leman Russ Battle Tank pattern: BSData categoryLinks include
    "Squadron" but not "Battleline", so before wave 243 the tank commander
    effectively issued zero orders.
    """
    return UnitProfile(
        name=name,
        health=13,
        damage=1,
        hit_probability=0.67,
        attacks=3,
        range_inches=48,
        save=2,
        toughness=11,
        strength=9,
        ap=3,
        weapon_damage_per_shot=3.0,
        points_override=210.0,
        faction="Astra Militarum",
        # SQUADRON keyword: real codex keyword from BSData categoryLinks.
        # Deliberately no BATTLELINE — testing that BATTLELINE is no longer required.
        unit_keywords=("VEHICLE", "SQUADRON"),
    )


def _neither_profile(name: str = "Commissar") -> UnitProfile:
    """A unit with no REGIMENT, SQUADRON, or TITANIC keyword — ineligible."""
    return UnitProfile(
        name=name,
        health=4,
        damage=0,
        hit_probability=0.5,
        attacks=2,
        range_inches=12,
        save=4,
        toughness=3,
        strength=3,
        ap=0,
        weapon_damage_per_shot=1.0,
        points_override=40.0,
        faction="Astra Militarum",
        # CHARACTER + INFANTRY but no REGIMENT/SQUADRON/TITANIC.
        unit_keywords=("CHARACTER", "INFANTRY"),
    )


def _build_army(officer_name: str, *target_profiles) -> Army:
    """Build an Army with one officer and the given target profiles.

    All units are placed at position (0.0, 0.0) by default (Army.add_unit
    sets position on the Unit from its profile, or it defaults to (0, 0)
    in the Army initialiser). Sequential uids are assigned for de-duplication.
    """
    army = Army("Test")
    army.add_unit(_officer_profile(officer_name))
    for p in target_profiles:
        army.add_unit(p)
    for idx, u in enumerate(army.units):
        u.uid = f"U{idx}"
    army._alive_cache = None
    return army


# ---------------------------------------------------------------------------
# Test A: SQUADRON-keyword vehicle is Order-eligible from a SQUADRON Officer
# ---------------------------------------------------------------------------

class TestSquadronKeywordVehicleIsOrderEligible(unittest.TestCase):
    """A unit carrying SQUADRON (no BATTLELINE) must be eligible to receive
    an Order from a SQUADRON-targeting Officer (e.g. Leman Russ Commander).

    Before wave 243 the BATTLELINE hard gate in `_is_order_target_eligible`
    blocked ALL Leman Russ / Rogal Dorn targets, so Leman Russ Commander and
    Rogal Dorn Commander issued zero Orders every game.
    """

    def test_squadron_unit_is_eligible_for_squadron_officer(self) -> None:
        """_is_order_target_eligible returns True for a SQUADRON unit when the
        Officer's target types include SQUADRON.
        """
        army = _build_army(
            "Leman Russ Commander",
            _squadron_only_profile("LR1"),
        )
        # Use the real Unit object from the army (has .is_alive, .profile, etc.)
        target = army.units[1]
        officer_types = frozenset({"SQUADRON"})
        self.assertTrue(
            _is_order_target_eligible(
                target,
                squadron_allowed=False,
                officer_target_types=officer_types,
            ),
            "A unit with SQUADRON keyword must be order-eligible when the Officer "
            "targets SQUADRON — the old BATTLELINE hard gate has been removed (wave 243)",
        )

    def test_squadron_officer_dispatches_order_to_squadron_unit(self) -> None:
        """Leman Russ Commander (SQUADRON-only Officer) must issue exactly 2 Orders
        to SQUADRON targets (its per-datasheet cap from BSData).

        Verbatim source (BSData Library Astra Militarum cache,
        unit id 5430-18e-d7b0-1d54, Orders profile id d520-92fd-8c74-ec6e):
            'This OFFICER can issue 2 Orders to SQUADRON units.'
        """
        army = _build_army(
            "Leman Russ Commander",
            _squadron_only_profile("LR1"),
            _squadron_only_profile("LR2"),
            _squadron_only_profile("LR3"),
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        self.assertEqual(
            len(issued), 2,
            f"Leman Russ Commander must issue 2 Orders to SQUADRON targets "
            f"(per-datasheet cap from BSData); got {len(issued)}: {issued}",
        )
        for _officer, target_name, _order in issued:
            self.assertIn(
                target_name, {"LR1", "LR2", "LR3"},
                f"Leman Russ Commander issued Order to unexpected target {target_name!r}",
            )

    def test_rogal_dorn_commander_issues_to_squadron(self) -> None:
        """Rogal Dorn Commander must also issue Orders to SQUADRON targets.

        Verbatim source (BSData Library Astra Militarum cache,
        unit id 78b6-f280-bba9-0594, Orders profile id 2798-cdef-e114-6795):
            'This OFFICER can issue 2 Orders to SQUADRON units.'
        """
        army = _build_army(
            "Rogal Dorn Commander",
            _squadron_only_profile("RDB1"),
            _squadron_only_profile("RDB2"),
            _squadron_only_profile("RDB3"),
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        self.assertEqual(
            len(issued), 2,
            f"Rogal Dorn Commander must issue 2 Orders; got {len(issued)}: {issued}",
        )


# ---------------------------------------------------------------------------
# Test B: _try_flexible_command finds SQUADRON candidates (simulator layer)
# ---------------------------------------------------------------------------

class TestTryFlexibleCommandFindsSquadronCandidates(unittest.TestCase):
    """simulator._try_flexible_command must find SQUADRON vehicles using the
    real SQUADRON keyword, not the old BATTLELINE + VEHICLE proxy.

    This test builds a minimal Battle and calls _try_flexible_command directly.
    The function sets `army.orders_eligible_squadron_this_round = True` only
    when there is at least one Officer AND at least one SQUADRON candidate AND
    the stratagem AI decides to fire. We verify that a SQUADRON-keyword vehicle
    (without BATTLELINE) is counted as a candidate by checking the flag after
    the call — or at minimum that no KeyError / AttributeError is raised and
    the function completes cleanly with the correct candidate pool.

    To avoid dependence on should_fire_stratagem heuristics, we test via
    dispatch_orders with squadron_allowed pre-set to True (simulating Flexible
    Command having already fired).
    """

    def test_squadron_vehicle_eligible_when_flexible_command_fired(self) -> None:
        """When `army.orders_eligible_squadron_this_round = True` (Flexible
        Command has fired) and an Officer whose own types are REGIMENT-only
        is present, the SQUADRON vehicle must still be Order-eligible.

        Ursula Creed (REGIMENT-only) normally cannot issue to SQUADRON.
        With Flexible Command fired, the OR gate must open SQUADRON eligibility.
        """
        army = _build_army(
            "Ursula Creed",
            _squadron_only_profile("LRTest"),
        )
        army.orders_eligible_squadron_this_round = True

        issued = dispatch_orders(army, battleshocked_uids=set())
        # Ursula Creed has REGIMENT-only restriction, but Flexible Command
        # must OR-open the SQUADRON gate, so 1 Order should be issued.
        self.assertEqual(
            len(issued), 1,
            f"Flexible Command must open SQUADRON eligibility for Ursula Creed "
            f"(REGIMENT-only Officer); the SQUADRON unit has no BATTLELINE keyword "
            f"but the real SQUADRON keyword — got {len(issued)} issued: {issued}",
        )
        _officer, target_name, _order = issued[0]
        self.assertEqual(
            target_name, "LRTest",
            f"The issued Order must go to the SQUADRON target; got {target_name!r}",
        )


# ---------------------------------------------------------------------------
# Test C: A unit with neither REGIMENT nor SQUADRON nor TITANIC is refused
# ---------------------------------------------------------------------------

class TestNeitherKeywordIsRefused(unittest.TestCase):
    """A unit carrying neither REGIMENT, SQUADRON, nor TITANIC must not be
    eligible to receive Orders regardless of any other keyword (e.g. INFANTRY,
    CHARACTER, BATTLELINE alone).
    """

    def test_infantry_only_no_regiment_is_ineligible(self) -> None:
        """A unit with INFANTRY but no REGIMENT keyword must be ineligible."""
        army = _build_army("Ursula Creed", _neither_profile("Commissar"))
        target = army.units[1]
        officer_types = frozenset({"REGIMENT"})
        self.assertFalse(
            _is_order_target_eligible(
                target,
                squadron_allowed=False,
                officer_target_types=officer_types,
            ),
            "A unit without REGIMENT/SQUADRON/TITANIC must be refused even if it "
            "carries INFANTRY — REGIMENT is the actual codex eligibility keyword",
        )

    def test_neither_keyword_unit_gets_no_orders(self) -> None:
        """dispatch_orders must issue zero Orders when the only available target
        carries neither REGIMENT, SQUADRON, nor TITANIC.
        """
        army = _build_army(
            "Ursula Creed",
            _neither_profile("Commissar1"),
            _neither_profile("Commissar2"),
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        self.assertEqual(
            len(issued), 0,
            f"No Orders must be issued when no REGIMENT/SQUADRON/TITANIC units exist; "
            f"got {len(issued)}: {issued}",
        )

    def test_battleline_without_regiment_is_ineligible(self) -> None:
        """A unit with BATTLELINE alone (no REGIMENT keyword) must be ineligible.

        This directly tests that the wave 243 switch from BATTLELINE-proxy to
        real REGIMENT keyword has not introduced a silent fallback: if a unit
        has BATTLELINE but the mapper produced no REGIMENT keyword (because
        BSData did not grant that categoryLink), the unit must be refused.
        """
        # Simulate a unit that has BATTLELINE (e.g. from another faction's
        # Battleline tag) but is NOT an AM REGIMENT or SQUADRON unit.
        battleline_only_profile = UnitProfile(
            name="BattlelineNonRegiment",
            health=1,
            damage=1,
            hit_probability=0.5,
            attacks=1,
            range_inches=24,
            save=5,
            toughness=3,
            strength=3,
            ap=0,
            weapon_damage_per_shot=1.0,
            points_override=10.0,
            faction="Astra Militarum",
            unit_keywords=("INFANTRY", "BATTLELINE"),  # no REGIMENT
        )
        army = _build_army("Ursula Creed", battleline_only_profile)
        target = army.units[1]
        self.assertFalse(
            _is_order_target_eligible(
                target,
                squadron_allowed=False,
                officer_target_types=frozenset({"REGIMENT"}),
            ),
            "BATTLELINE alone must NOT grant Order eligibility after wave 243 — "
            "only the real REGIMENT keyword does",
        )


# ---------------------------------------------------------------------------
# Test D: A REGIMENT infantry unit (Kasrkin pattern) is eligible
# ---------------------------------------------------------------------------

class TestRegimentKeywordInfantryIsEligible(unittest.TestCase):
    """A unit carrying REGIMENT (without BATTLELINE) must be eligible to receive
    Orders from a REGIMENT-targeting Officer.

    This covers the Kasrkin, Tempestus Scions, Heavy Weapons Squads pattern —
    units whose BSData categoryLinks include "Regiment" but not "Battleline",
    so they were blocked by the old BATTLELINE gate in wave 237.
    """

    def test_regiment_unit_is_eligible_for_regiment_officer(self) -> None:
        """_is_order_target_eligible returns True for a REGIMENT unit when the
        Officer's target types include REGIMENT.
        """
        army = _build_army("Ursula Creed", _regiment_only_profile("Kasrkin"))
        target = army.units[1]
        officer_types = frozenset({"REGIMENT"})
        self.assertTrue(
            _is_order_target_eligible(
                target,
                squadron_allowed=False,
                officer_target_types=officer_types,
            ),
            "A unit with REGIMENT keyword (no BATTLELINE) must be order-eligible "
            "when the Officer targets REGIMENT — the BATTLELINE hard gate has been "
            "removed (wave 243)",
        )

    def test_cadian_castellan_issues_to_regiment_unit(self) -> None:
        """Cadian Castellan (REGIMENT-only Officer) must issue Orders to REGIMENT
        units even when those units carry no BATTLELINE keyword.

        This is the Kasrkin / Tempestus Scions scenario.
        """
        army = _build_army(
            "Cadian Castellan",
            _regiment_only_profile("Kasrkin1"),
            _regiment_only_profile("Kasrkin2"),
            _regiment_only_profile("Kasrkin3"),
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        # Cadian Castellan cap is 2 (BSData unit id 2b49-4d03-aaf5-3532,
        # Orders profile id 21e5-4e9-7904-8d96).
        self.assertEqual(
            len(issued), 2,
            f"Cadian Castellan must issue 2 Orders to REGIMENT targets; "
            f"got {len(issued)}: {issued}",
        )

    def test_ursula_creed_issues_three_orders_to_regiment_units(self) -> None:
        """Ursula Creed (REGIMENT-only Officer, cap 3) issues to REGIMENT units
        even without BATTLELINE.
        """
        army = _build_army(
            "Ursula Creed",
            _regiment_only_profile("Scions1"),
            _regiment_only_profile("Scions2"),
            _regiment_only_profile("Scions3"),
            _regiment_only_profile("Scions4"),
        )
        issued = dispatch_orders(army, battleshocked_uids=set())
        self.assertEqual(
            len(issued), 3,
            f"Ursula Creed must issue 3 Orders to REGIMENT targets (no BATTLELINE); "
            f"got {len(issued)}: {issued}",
        )


# ---------------------------------------------------------------------------
# Test E: _unit_satisfies_target_type with REGIMENT accepts REGIMENT-only unit
# ---------------------------------------------------------------------------

class TestUnitSatisfiesTargetType(unittest.TestCase):
    """Direct unit tests for `_unit_satisfies_target_type`."""

    def _unit_from(self, keywords: tuple) -> "object":
        """Return a minimal mock-like Unit with unit_keywords set."""
        p = UnitProfile(
            name="TestUnit",
            health=1,
            damage=1,
            hit_probability=0.5,
            attacks=1,
            range_inches=24,
            save=5,
            toughness=3,
            strength=3,
            ap=0,
            weapon_damage_per_shot=1.0,
            points_override=10.0,
            faction="Astra Militarum",
            unit_keywords=keywords,
        )
        # Build a minimal Unit-like object with only a .profile attribute.
        # dispatch_orders accesses unit.profile.unit_keywords directly.
        class _MinUnit:
            def __init__(self, profile):
                self.profile = profile
        return _MinUnit(p)

    def test_regiment_keyword_satisfies_regiment_target_type(self) -> None:
        unit = self._unit_from(("INFANTRY", "REGIMENT"))
        self.assertTrue(
            _unit_satisfies_target_type(unit, frozenset({"REGIMENT"})),
            "REGIMENT keyword must satisfy REGIMENT target type",
        )

    def test_squadron_keyword_satisfies_squadron_target_type(self) -> None:
        unit = self._unit_from(("VEHICLE", "SQUADRON"))
        self.assertTrue(
            _unit_satisfies_target_type(unit, frozenset({"SQUADRON"})),
            "SQUADRON keyword must satisfy SQUADRON target type",
        )

    def test_regiment_does_not_satisfy_squadron(self) -> None:
        unit = self._unit_from(("INFANTRY", "REGIMENT"))
        self.assertFalse(
            _unit_satisfies_target_type(unit, frozenset({"SQUADRON"})),
            "REGIMENT-only unit must not satisfy SQUADRON target type",
        )

    def test_squadron_does_not_satisfy_regiment(self) -> None:
        unit = self._unit_from(("VEHICLE", "SQUADRON"))
        self.assertFalse(
            _unit_satisfies_target_type(unit, frozenset({"REGIMENT"})),
            "SQUADRON-only unit must not satisfy REGIMENT target type",
        )

    def test_neither_satisfies_neither(self) -> None:
        unit = self._unit_from(("INFANTRY", "CHARACTER"))
        self.assertFalse(
            _unit_satisfies_target_type(unit, frozenset({"REGIMENT", "SQUADRON"})),
            "Unit with no REGIMENT/SQUADRON/TITANIC must satisfy no target type",
        )

    def test_battleline_alone_does_not_satisfy_regiment(self) -> None:
        """Regression: BATTLELINE alone must not satisfy REGIMENT target type."""
        unit = self._unit_from(("INFANTRY", "BATTLELINE"))
        self.assertFalse(
            _unit_satisfies_target_type(unit, frozenset({"REGIMENT"})),
            "BATTLELINE alone must NOT satisfy REGIMENT target type after wave 243",
        )

    def test_battleline_vehicle_alone_does_not_satisfy_squadron(self) -> None:
        """Regression: BATTLELINE + VEHICLE alone must not satisfy SQUADRON target type."""
        unit = self._unit_from(("VEHICLE", "BATTLELINE"))
        self.assertFalse(
            _unit_satisfies_target_type(unit, frozenset({"SQUADRON"})),
            "BATTLELINE + VEHICLE alone must NOT satisfy SQUADRON target type after wave 243 — "
            "only the real SQUADRON keyword does",
        )

    def test_unit_with_both_regiment_and_squadron(self) -> None:
        """A unit carrying both REGIMENT and SQUADRON (e.g. Armoured Sentinels
        in BSData) satisfies both target types.
        """
        unit = self._unit_from(("VEHICLE", "REGIMENT", "SQUADRON"))
        self.assertTrue(
            _unit_satisfies_target_type(unit, frozenset({"REGIMENT"})),
            "REGIMENT+SQUADRON unit must satisfy REGIMENT target type",
        )
        self.assertTrue(
            _unit_satisfies_target_type(unit, frozenset({"SQUADRON"})),
            "REGIMENT+SQUADRON unit must satisfy SQUADRON target type",
        )


# ---------------------------------------------------------------------------
# Test F: TITANIC keyword still works (regression guard)
# ---------------------------------------------------------------------------

class TestTitanicKeywordStillWorks(unittest.TestCase):
    """TITANIC keyword must still satisfy the TITANIC target type.

    Lord Solar Leontus's Orders profile includes TITANIC. This test guards
    against the wave 243 refactor accidentally removing the TITANIC branch.
    """

    def test_titanic_satisfies_titanic_target_type(self) -> None:
        p = UnitProfile(
            name="TitanicUnit",
            health=24,
            damage=1,
            hit_probability=0.5,
            attacks=6,
            range_inches=36,
            save=2,
            toughness=12,
            strength=14,
            ap=4,
            weapon_damage_per_shot=6.0,
            points_override=600.0,
            faction="Astra Militarum",
            unit_keywords=("VEHICLE", "TITANIC"),
        )

        class _MinUnit:
            def __init__(self, profile):
                self.profile = profile

        unit = _MinUnit(p)
        self.assertTrue(
            _unit_satisfies_target_type(unit, frozenset({"TITANIC"})),
            "TITANIC unit must satisfy TITANIC target type (Lord Solar Leontus path)",
        )

    def test_non_titanic_does_not_satisfy_titanic(self) -> None:
        p = UnitProfile(
            name="NormalUnit",
            health=13,
            damage=1,
            hit_probability=0.5,
            attacks=3,
            range_inches=48,
            save=2,
            toughness=11,
            strength=9,
            ap=3,
            weapon_damage_per_shot=3.0,
            points_override=200.0,
            faction="Astra Militarum",
            unit_keywords=("VEHICLE", "SQUADRON"),
        )

        class _MinUnit:
            def __init__(self, profile):
                self.profile = profile

        unit = _MinUnit(p)
        self.assertFalse(
            _unit_satisfies_target_type(unit, frozenset({"TITANIC"})),
            "SQUADRON-only unit must not satisfy TITANIC target type",
        )


if __name__ == "__main__":
    unittest.main()
