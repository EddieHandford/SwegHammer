"""
Wave 248 — Fix Bayonets! engagement-range routing guard tests.

Tests three requirements:
  (a) Gate OFF (explicit SWEG_FIXBAYONETS=0): an unengaged melee-statted
      squad still receives Fix Bayonets! — behaviour is byte-identical to
      the pre-248 path.
  (b) Gate ON (SWEG_FIXBAYONETS=1): an unengaged melee-statted squad does
      NOT receive Fix Bayonets!; it falls through to the next-best Order
      instead (Take Aim! in the default fixture, which has no ranged weapon
      and no rapid-fire profile on the melee unit).
  (c) Gate ON (SWEG_FIXBAYONETS=1): an engaged melee-statted squad DOES
      receive Fix Bayonets!.

All tests use synthetic Unit-like objects and minimal fake Army objects so
that no real army-builder plumbing is needed. dispatch_orders is called
directly with an explicit enemy_army argument.
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Minimal stubs — mirroring the structure in test_orders_wave248_creed.py
# ---------------------------------------------------------------------------

class _FakeProfile:
    def __init__(
        self,
        name: str,
        faction: str = "Astra Militarum",
        unit_keywords: Optional[List[str]] = None,
        points_cost: float = 100.0,
        base_size_mm: float = 25.0,
    ) -> None:
        self.name = name
        self.faction = faction
        self.unit_keywords = unit_keywords or []
        self.points_cost = points_cost
        self.health = 1.0
        self.key = None
        # base_size_mm used by _bc_model_radius_in in sim.geometry
        self.base_size_mm = base_size_mm
        # Ranged attack stats — set to zero for pure-melee units
        self.attacks = 0
        self.hit_probability = 0.5
        self.per_shot_damage = 1.0
        self.rapid_fire = 0
        self.secondary_rapid_fire = 0
        self.extra_ranged_profiles = ()
        # Melee stats — set to give melee_dpa > 0.5
        self.melee_attacks = 4
        self.melee_hit_probability = 0.67
        self.melee_damage_per_shot = 2.0


class _FakeRangedProfile(_FakeProfile):
    """A ranged profile (e.g. Lasgun-style) for fallthrough order tests."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        # Give it real ranged stats so FRFSRF / Take Aim! can fire
        self.attacks = 2
        self.hit_probability = 0.67
        self.per_shot_damage = 1.0
        self.rapid_fire = 0  # no rapid fire → falls to Take Aim!
        # Zero out melee so the Fix Bayonets! branch does NOT fire
        self.melee_attacks = 0
        self.melee_hit_probability = 0.0
        self.melee_damage_per_shot = 0.0


class _FakeUnit:
    _uid_counter = 0

    def __init__(
        self,
        name: str,
        faction: str = "Astra Militarum",
        keywords: Optional[List[str]] = None,
        position: Any = (3.0, 3.0),
        squad_id: int = -1,
        points_cost: float = 100.0,
        current_health: float = 1.0,
        base_size_mm: float = 25.0,
        profile_cls=None,
    ) -> None:
        _FakeUnit._uid_counter += 1
        self.uid = _FakeUnit._uid_counter
        cls = profile_cls if profile_cls is not None else _FakeProfile
        self.profile = cls(
            name=name,
            faction=faction,
            unit_keywords=keywords or [],
            points_cost=points_cost,
            base_size_mm=base_size_mm,
        )
        self.position = position
        self.squad_id = squad_id
        self.is_alive = True
        self.current_health = current_health

    # Transient Order flags (set by _apply_order)
    transient_plus_one_to_hit_shooting: bool = False
    transient_plus_one_to_wound_melee: bool = False
    transient_plus_one_attack_rapid_fire: bool = False
    transient_plus_one_save: bool = False


class _FakeArmy:
    def __init__(self, units: List[_FakeUnit], name: str = "AM") -> None:
        self.name = name
        self.units = units
        self.alive_units = units
        self.orders_eligible_squadron_this_round = False


# ---------------------------------------------------------------------------
# Reload orders.py with specific gate values
# ---------------------------------------------------------------------------

def _reload_orders(fixbayonets_value: str) -> types.ModuleType:
    """Force-reload code.orders with the given SWEG_FIXBAYONETS env value.

    Necessary because _FIXBAYONETS_GUARD is a module-level constant read
    once at import time. Each test that needs a specific gate state calls
    this helper.
    """
    os.environ["SWEG_FIXBAYONETS"] = fixbayonets_value
    # Ensure the Creed gate is off so it doesn't interact with these tests.
    os.environ["SWEG_CREED_TWO_ORDERS"] = "0"

    mod_name = "code.orders"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    if "code" in sys.modules and hasattr(sys.modules["code"], "orders"):
        delattr(sys.modules["code"], "orders")

    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _build_melee_army(
    officer_position: Any = (3.0, 3.0),
    squad_position: Any = (3.0, 3.0),
    squad_sid: int = 1,
) -> _FakeArmy:
    """Return a minimal AM army with one Officer and one melee-statted squad.

    The squad is Bullgryn-style (melee_attacks=4, no ranged attacks) so
    the scorer would normally issue Fix Bayonets!. Placing the squad at
    squad_position lets tests control engagement distance from enemy units.
    """
    officer = _FakeUnit(
        "Cadian Castellan",
        keywords=["CHARACTER", "OFFICER", "REGIMENT"],
        position=officer_position,
        squad_id=-1,
        points_cost=50.0,
    )
    squad_member = _FakeUnit(
        "Bullgryns",
        keywords=["INFANTRY", "REGIMENT"],
        position=squad_position,
        squad_id=squad_sid,
        points_cost=90.0,
    )
    return _FakeArmy([officer, squad_member])


def _build_enemy_army(position: Any = (30.0, 3.0)) -> _FakeArmy:
    """Return a minimal enemy army with one unit at `position`."""
    enemy_unit = _FakeUnit(
        "Space Marine",
        faction="Space Marines",
        keywords=["INFANTRY"],
        position=position,
        squad_id=99,
        points_cost=80.0,
    )
    return _FakeArmy([enemy_unit], name="SM")


# ---------------------------------------------------------------------------
# Test (a): gate OFF — unengaged melee squad still receives Fix Bayonets!
# ---------------------------------------------------------------------------

def test_gate_off_unengaged_squad_gets_fix_bayonets() -> None:
    """When SWEG_FIXBAYONETS=0 (legacy path), an unengaged melee squad
    receives Fix Bayonets! — byte-identical to the pre-248 behaviour."""
    orders_mod = _reload_orders("0")
    assert not orders_mod._FIXBAYONETS_GUARD, "Gate must be off"

    # Squad is far from any enemy — not engaged.
    army = _build_melee_army(
        officer_position=(3.0, 3.0),
        squad_position=(3.0, 3.0),
    )
    # Enemy is 30" away — clearly not within Engagement Range.
    enemy = _build_enemy_army(position=(33.0, 3.0))

    issued = orders_mod.dispatch_orders(
        army, battleshocked_uids=set(), enemy_army=enemy
    )

    squad_unit = army.units[1]
    assert squad_unit.transient_plus_one_to_wound_melee, (
        "Gate off: unengaged melee squad must still receive Fix Bayonets! "
        "(transient_plus_one_to_wound_melee should be True)"
    )


# ---------------------------------------------------------------------------
# Test (b): gate ON — unengaged melee squad does NOT get Fix Bayonets!
# ---------------------------------------------------------------------------

def test_gate_on_unengaged_squad_does_not_get_fix_bayonets() -> None:
    """When SWEG_FIXBAYONETS=1, an unengaged melee squad must NOT receive
    Fix Bayonets! — it falls through to a different Order instead."""
    orders_mod = _reload_orders("1")
    assert orders_mod._FIXBAYONETS_GUARD, "Gate must be on"

    # Squad is far from any enemy — not engaged.
    army = _build_melee_army(
        officer_position=(3.0, 3.0),
        squad_position=(3.0, 3.0),
    )
    # Enemy is 30" away — clearly not within Engagement Range.
    enemy = _build_enemy_army(position=(33.0, 3.0))

    issued = orders_mod.dispatch_orders(
        army, battleshocked_uids=set(), enemy_army=enemy
    )

    squad_unit = army.units[1]
    assert not squad_unit.transient_plus_one_to_wound_melee, (
        "Gate on: unengaged melee squad must NOT receive Fix Bayonets! "
        "(transient_plus_one_to_wound_melee should be False)"
    )

    # The squad should still have received some other Order — the dispatcher
    # must not silently drop the Order slot.
    order_flags = [
        squad_unit.transient_plus_one_to_hit_shooting,
        squad_unit.transient_plus_one_to_wound_melee,
        squad_unit.transient_plus_one_attack_rapid_fire,
        squad_unit.transient_plus_one_save,
    ]
    true_count = sum(1 for f in order_flags if f)
    assert true_count == 1, (
        f"Gate on: unengaged melee squad must still receive exactly one Order "
        f"(got {true_count} flags set)"
    )


# ---------------------------------------------------------------------------
# Test (c): gate ON — engaged melee squad DOES get Fix Bayonets!
# ---------------------------------------------------------------------------

def test_gate_on_engaged_squad_gets_fix_bayonets() -> None:
    """When SWEG_FIXBAYONETS=1, a melee squad that is within Engagement
    Range of an enemy DOES receive Fix Bayonets!."""
    orders_mod = _reload_orders("1")
    assert orders_mod._FIXBAYONETS_GUARD, "Gate must be on"

    # Place the squad at (3.0, 3.0); enemy at (3.5, 3.0) — 0.5" centre
    # distance, which is less than 1.0" base-edge gap (25mm base ~ 0.5"
    # radius each, so base-edge gap ≈ 0.5 − 0.5 − 0.5 = −0.5" < 1.0",
    # definitely engaged). Use a very small base size on the enemy so the
    # gap arithmetic stays clearly inside the engagement threshold.
    army = _build_melee_army(
        officer_position=(0.0, 0.0),
        squad_position=(0.5, 0.0),
    )
    # Enemy placed at (1.0, 0.0): centre distance = 0.5", both bases tiny
    # → base-edge gap negative → unambiguously within Engagement Range.
    enemy_unit = _FakeUnit(
        "Space Marine",
        faction="Space Marines",
        keywords=["INFANTRY"],
        position=(1.0, 0.0),
        squad_id=99,
        points_cost=80.0,
        base_size_mm=1.0,  # near-zero radius so gap ≈ centre distance
    )
    enemy = _FakeArmy([enemy_unit], name="SM")

    issued = orders_mod.dispatch_orders(
        army, battleshocked_uids=set(), enemy_army=enemy
    )

    squad_unit = army.units[1]
    assert squad_unit.transient_plus_one_to_wound_melee, (
        "Gate on: engaged melee squad MUST receive Fix Bayonets! "
        "(transient_plus_one_to_wound_melee should be True)"
    )
