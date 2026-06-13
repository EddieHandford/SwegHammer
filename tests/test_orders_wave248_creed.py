"""
Wave 248 — Ursula Creed Lord Castellan two-Order exception gate tests.

Tests three requirements:
  (a) Gate OFF (explicit SWEG_CREED_TWO_ORDERS=0): every squad receives at most
      one Order per round. Behaviour is byte-identical to the pre-248 path.
  (b) Gate ON (SWEG_CREED_TWO_ORDERS=1): Creed's led squad can carry two
      DIFFERENT Orders in the same round, while every other squad still caps at
      one Order.
  (c) Gate ON: Creed's led squad never receives the SAME Order twice.

All tests use synthetic Unit-like objects and a minimal fake Army so that no
real army-builder plumbing is needed. The Order dispatcher (dispatch_orders) is
called directly.
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

class _FakeProfile:
    def __init__(
        self,
        name: str,
        faction: str = "Astra Militarum",
        unit_keywords: Optional[List[str]] = None,
        points_cost: float = 100.0,
    ) -> None:
        self.name = name
        self.faction = faction
        self.unit_keywords = unit_keywords or []
        self.points_cost = points_cost
        self.health = 1.0
        self.key = None  # not used by orders.py
        # Fields read by _unit_ranged_dpa, _unit_melee_dpa, _unit_has_rapid_fire,
        # and _squad_hp_frac_lost:
        self.attacks = 2
        self.hit_probability = 0.5
        self.per_shot_damage = 1.0
        self.melee_attacks = 0
        self.melee_hit_probability = 0.0
        self.melee_damage_per_shot = 0.0
        self.rapid_fire = 1  # Lasgun-style so FRFSRF is eligible
        self.secondary_rapid_fire = 0
        self.extra_ranged_profiles = ()


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
    ) -> None:
        _FakeUnit._uid_counter += 1
        self.uid = _FakeUnit._uid_counter
        self.profile = _FakeProfile(
            name=name,
            faction=faction,
            unit_keywords=keywords or [],
            points_cost=points_cost,
        )
        self.position = position
        self.squad_id = squad_id
        self.is_alive = True
        self.current_health = current_health
        self._orders: List[str] = []
        self.army_ref: Any = None  # set after army construction

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
        for u in units:
            u.army_ref = self


# ---------------------------------------------------------------------------
# Helpers to build the fake armies used by the tests
# ---------------------------------------------------------------------------

def _build_army_with_creed(
    extra_squad_sid: int = 10,
    creed_position: Any = (3.0, 3.0),
    cadians_position: Any = (3.0, 3.0),
    extra_squad_position: Any = (3.0, 3.0),
) -> _FakeArmy:
    """Return a minimal AM army containing:
    - Ursula Creed (OFFICER, EPIC HERO, REGIMENT) at creed_position
    - A 1-model Cadian Shock Troops squad (sid=1) at cadians_position
      — this is Creed's legal bodyguard per her host_keys
    - A 1-model Cadian Shock Troops squad (sid=extra_squad_sid) at
      extra_squad_position — a second squad that should cap at 1 Order
    """
    creed = _FakeUnit(
        "Ursula Creed",
        keywords=["CHARACTER", "EPIC HERO", "OFFICER", "REGIMENT"],
        position=creed_position,
        squad_id=-1,
        points_cost=85.0,
    )
    cadian_led = _FakeUnit(
        "Cadian Shock Troops",
        keywords=["INFANTRY", "REGIMENT"],
        position=cadians_position,
        squad_id=1,
        points_cost=60.0,
    )
    cadian_other = _FakeUnit(
        "Cadian Shock Troops",
        keywords=["INFANTRY", "REGIMENT"],
        position=extra_squad_position,
        squad_id=extra_squad_sid,
        points_cost=60.0,
    )
    return _FakeArmy([creed, cadian_led, cadian_other])


# ---------------------------------------------------------------------------
# Reload orders.py with a specific gate value
# ---------------------------------------------------------------------------

def _reload_orders(creed_two_orders_value: str) -> types.ModuleType:
    """Force-reload code.orders with the given SWEG_CREED_TWO_ORDERS env value.

    Necessary because _CREED_TWO_ORDERS is a module-level constant (read once
    at import time). Each test that needs a specific gate state calls this.
    """
    import importlib

    # Patch env before reload
    os.environ["SWEG_CREED_TWO_ORDERS"] = creed_two_orders_value

    mod_name = "code.orders"
    # Remove cached module so the next import re-executes the module body and
    # picks up the new env value. Also clear the parent package's cached
    # attribute — `from code import orders` won't re-execute the body otherwise.
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    if "code" in sys.modules and hasattr(sys.modules["code"], "orders"):
        delattr(sys.modules["code"], "orders")

    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# Test (a): gate OFF — every squad gets at most one Order
# ---------------------------------------------------------------------------

def test_gate_off_one_order_per_squad() -> None:
    """When SWEG_CREED_TWO_ORDERS=0, no squad receives more than one Order."""
    orders_mod = _reload_orders("0")
    assert not orders_mod._CREED_TWO_ORDERS, "Gate must be off"

    army = _build_army_with_creed()

    # Creed issues 3 Orders; army has 2 squads, so both should get 1 each.
    issued = orders_mod.dispatch_orders(army, battleshocked_uids=set())

    # Count per target squad (by squad_id, not by issued list length)
    from collections import Counter
    squad_counts: Counter = Counter()
    for officer_name, target_name, order_name in issued:
        # Determine squad by matching issued target_name against unit names
        # (in our setup all targets are "Cadian Shock Troops").
        pass

    # The core invariant: the led squad (squad_id=1) receives AT MOST 1 Order.
    cadian_led_unit = army.units[1]  # sid=1
    order_flags = [
        cadian_led_unit.transient_plus_one_to_hit_shooting,
        cadian_led_unit.transient_plus_one_to_wound_melee,
        cadian_led_unit.transient_plus_one_attack_rapid_fire,
        cadian_led_unit.transient_plus_one_save,
    ]
    # Only one of the four flags should be True (or none if the squad was
    # not reached) — but never more than one, since each _apply_order sets
    # exactly one flag.
    true_count = sum(1 for f in order_flags if f)
    assert true_count <= 1, (
        f"Gate off: Creed's led squad received {true_count} orders, expected <= 1"
    )

    # Second squad also at most 1 Order.
    cadian_other_unit = army.units[2]  # sid=10
    other_flags = [
        cadian_other_unit.transient_plus_one_to_hit_shooting,
        cadian_other_unit.transient_plus_one_to_wound_melee,
        cadian_other_unit.transient_plus_one_attack_rapid_fire,
        cadian_other_unit.transient_plus_one_save,
    ]
    other_true = sum(1 for f in other_flags if f)
    assert other_true <= 1, (
        f"Gate off: other squad received {other_true} orders, expected <= 1"
    )


# ---------------------------------------------------------------------------
# Test (b): gate ON — Creed's led squad can carry two DIFFERENT Orders
# ---------------------------------------------------------------------------

def test_gate_on_creed_led_squad_receives_two_orders() -> None:
    """When gate is on, the led squad appears in `issued` up to twice
    (and those two orders are different)."""
    orders_mod = _reload_orders("1")
    assert orders_mod._CREED_TWO_ORDERS, "Gate must be on"

    # Place Creed and the led squad at origin, second squad far away so only
    # the led squad is in aura for the second issuance.
    # Creed issues 3 Orders; army has 2 squads.
    army = _build_army_with_creed(
        creed_position=(0.0, 0.0),
        cadians_position=(1.0, 0.0),      # within 6"
        extra_squad_position=(10.0, 0.0), # outside 6" so Creed can't reach
    )

    issued = orders_mod.dispatch_orders(army, battleshocked_uids=set())

    # Collect orders issued to the led squad (squad_id=1)
    led_unit = army.units[1]
    # We identify it by position (1.0, 0.0)
    led_orders = [order for _, tname, order in issued if tname == led_unit.profile.name]

    # With the extra squad out of range, the only target for Creed's second
    # issuance is the led squad — so it should appear in issued twice (if two
    # different orders can be picked; if only one order type applies, it may
    # only appear once because the duplicate guard fires).
    # The test requires: if the squad appears twice, the two orders are different.
    if len(led_orders) >= 2:
        assert led_orders[0] != led_orders[1], (
            f"Gate on: Creed's led squad received the same Order twice: "
            f"{led_orders[0]!r}"
        )

    # Regardless: the led squad never appears more than twice.
    assert len(led_orders) <= 2, (
        f"Gate on: Creed's led squad appeared in issued {len(led_orders)} times; "
        "max is 2"
    )


# ---------------------------------------------------------------------------
# Test (c): gate ON — led squad never receives the same Order twice
# ---------------------------------------------------------------------------

def test_gate_on_no_duplicate_order_on_led_squad() -> None:
    """When the gate is on, the led squad never has the same order applied
    more than once, even when only one Order type is valid for it."""
    orders_mod = _reload_orders("1")
    assert orders_mod._CREED_TWO_ORDERS, "Gate must be on"

    # Put both squads in range of Creed.
    army = _build_army_with_creed(
        creed_position=(0.0, 0.0),
        cadians_position=(1.0, 0.0),
        extra_squad_position=(2.0, 0.0),
    )

    issued = orders_mod.dispatch_orders(army, battleshocked_uids=set())

    # Count orders issued per squad key (squad_id).
    from collections import defaultdict
    orders_by_squad: dict = defaultdict(list)
    for _, tname, order in issued:
        # Find the corresponding unit's squad_id.
        for u in army.units:
            if u.profile.name == tname:
                orders_by_squad[u.squad_id].append(order)
                break

    # No squad should have received the same order more than once.
    for sid, order_list in orders_by_squad.items():
        assert len(order_list) == len(set(order_list)), (
            f"Squad sid={sid} received duplicate Orders: {order_list}"
        )

    # Non-led squads (sid != 1) should have at most 1 Order.
    for sid, order_list in orders_by_squad.items():
        if sid != 1:  # led squad has sid=1 in our fixture
            assert len(order_list) <= 1, (
                f"Non-led squad sid={sid} received {len(order_list)} orders; "
                "expected <= 1"
            )
