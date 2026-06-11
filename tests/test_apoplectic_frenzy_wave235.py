"""Wave 235 regression tests: Apoplectic Frenzy corrected from a fabricated
melee-buff paraphrase to the verbatim advance-and-charge rule.

Verbatim rule (Wahapedia, Berzerker Warband, fetched 2026-06-11):
"WHEN: Your Movement phase, just after a KHORNE BERZERKERS unit from your
army is selected to Advance. TARGET: That KHORNE BERZERKERS unit. EFFECT:
Until the end of the turn, your unit is eligible to declare a charge in a
turn in which it Advanced."

Assertions:
1. After the stratagem fires, transient_charge_after_advance is True on the
   targeted World Eaters unit.
2. Neither transient_plus_one_to_wound_melee (the old fabricated proxy) nor
   transient_lethal_hits (the rejected rewire) is set.
3. The grant does not leak to the enemy unit.
4. _clear_transient_stratagem_flags resets the flag (one-round scope).
5. Charge-lockout integration: a unit in _advanced_this_round is blocked by
   _do_charge without the flag and charges successfully with it (asserted
   via _charging_this_round membership). Positions 2.5 inches apart (wave-241
   base-edge Engagement Range: gap 1.24 inches, a valid charge candidate
   whose required move is 0.24 inches) make the 2D6 charge roll (minimum 2)
   always sufficient, so no dice mocking needed.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _we_berzerker(name: str = "Berzerker", points: float = 80.0) -> UnitProfile:
    """A high-DPA World Eaters melee unit eligible for Apoplectic Frenzy.

    melee DPA = 4 * (2/3) * 1.0 = 2.67 — clears the strategy gate's 1.5
    threshold AND _wants_to_charge (melee 2.67 >= max(ranged 1.33, 1.0)).
    """
    return UnitProfile(
        name=name,
        health=2,
        damage=1,
        hit_probability=2 / 3,
        ap=-1,
        save=3,
        strength=5,
        toughness=4,
        attacks=2,
        weapon_damage_per_shot=1.0,
        range_inches=0,
        leadership=7,
        faction="World Eaters",
        unit_keywords=("INFANTRY",),
        melee_attacks=4,
        melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3,
        melee_strength=5,
        melee_ap=-1,
        points_override=points,
    )


def _heavy_target(name: str = "Knight") -> UnitProfile:
    """A HEAVY-class enemy target (VEHICLE TITANIC) that satisfies the
    _is_heavy_target gate in strategy.py."""
    return UnitProfile(
        name=name,
        health=22,
        damage=6,
        hit_probability=2 / 3,
        ap=-3,
        save=2,
        strength=10,
        toughness=12,
        attacks=4,
        weapon_damage_per_shot=1.5,
        range_inches=48,
        points_override=430.0,
        unit_keywords=("VEHICLE", "TITANIC"),
    )


def _harmless_defender(name: str = "Bystander") -> UnitProfile:
    """A zero-output defender for the charge-lockout tests so Fire Overwatch
    (if enabled in the environment) cannot perturb the charger."""
    return UnitProfile(
        name=name,
        health=2,
        damage=0,
        hit_probability=0,
        attacks=0,
        range_inches=1,
        melee_attacks=0,
        unit_keywords=("INFANTRY",),
    )


def _open_map() -> Map:
    """60x60 board with one objective in the centre so strategy has data."""
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _build_stratagem_battle() -> tuple:
    """Minimal World Eaters vs heavy-target battle with enough command points
    to fire Apoplectic Frenzy (1 CP cost)."""
    we = Army("World Eaters")
    we.add_unit(_we_berzerker())
    enemy = Army("Astartes")
    enemy.add_unit(_heavy_target())
    battle = Battle(we, enemy, verbose=False)
    battle._assign_uids()
    we.command_points = 5
    return battle, we, enemy


def _build_charge_battle() -> tuple:
    """Melee charger 2.5 inches (centre) from a harmless defender. Under the
    wave-241 base-edge Engagement Range measure (production default) that is
    a gap of 1.24 inches — a valid charge candidate, not already engaged —
    and the required charge move is 0.24 inches, so a 2D6 charge roll
    (minimum 2) always reaches and only the advance lockout can block."""
    a = Army("Chargers")
    a.add_unit(_we_berzerker())
    b = Army("Defenders")
    b.add_unit(_harmless_defender())
    battle = Battle(a, b, map_=_open_map(), verbose=False)
    battle._assign_uids()
    charger = a.units[0]
    defender = b.units[0]
    charger.position = (20.0, 30.0)
    defender.position = (22.5, 30.0)
    return battle, charger, defender


# ---------------------------------------------------------------------------
# Stratagem routing
# ---------------------------------------------------------------------------

class TestApoplecticFrenzyRouting(unittest.TestCase):
    """The stratagem sets transient_charge_after_advance and nothing else."""

    def _fire_stratagem(self):
        battle, we, enemy = _build_stratagem_battle()
        we_unit = we.units[0]
        enemy_unit = enemy.units[0]

        self.assertFalse(
            we_unit.transient_charge_after_advance,
            "transient_charge_after_advance must start False",
        )
        battle._try_apoplectic_frenzy(we, enemy)
        return battle, we_unit, enemy_unit

    def test_charge_after_advance_set(self):
        _, we_unit, _ = self._fire_stratagem()
        self.assertTrue(
            we_unit.transient_charge_after_advance,
            "transient_charge_after_advance must be True after Apoplectic "
            "Frenzy fires (wave 235 correction: advance-and-charge, not a "
            "melee buff)",
        )

    def test_old_wound_proxy_not_set(self):
        _, we_unit, _ = self._fire_stratagem()
        self.assertFalse(
            we_unit.transient_plus_one_to_wound_melee,
            "transient_plus_one_to_wound_melee must NOT be set — the "
            "fabricated +1-to-wound proxy was removed in wave 235",
        )

    def test_lethal_hits_not_set(self):
        _, we_unit, _ = self._fire_stratagem()
        self.assertFalse(
            we_unit.transient_lethal_hits,
            "transient_lethal_hits must NOT be set — the [LETHAL HITS] "
            "reading was a fabricated paraphrase, rejected in wave 235",
        )

    def test_grant_does_not_reach_enemy(self):
        _, _, enemy_unit = self._fire_stratagem()
        self.assertFalse(
            enemy_unit.transient_charge_after_advance,
            "the grant must NOT leak to the enemy unit",
        )


# ---------------------------------------------------------------------------
# Transient lifecycle
# ---------------------------------------------------------------------------

class TestApoplecticFrenzyTransientCleared(unittest.TestCase):
    """transient_charge_after_advance is one-round-scoped: the round-start
    reset (_clear_transient_stratagem_flags) returns it to False."""

    def test_cleared_by_round_reset(self):
        battle, we, enemy = _build_stratagem_battle()
        we_unit = we.units[0]

        battle._try_apoplectic_frenzy(we, enemy)
        self.assertTrue(
            we_unit.transient_charge_after_advance,
            "flag must be True after the stratagem fires",
        )
        battle._clear_transient_stratagem_flags(we)
        self.assertFalse(
            we_unit.transient_charge_after_advance,
            "flag must be False after the round-start transient reset",
        )


# ---------------------------------------------------------------------------
# Charge-lockout integration
# ---------------------------------------------------------------------------

class TestAdvanceChargeLockoutExemption(unittest.TestCase):
    """_do_charge: an Advanced unit is blocked without the flag and charges
    with it — the transient analogue of Murderer's Cowl."""

    def test_advanced_unit_blocked_without_flag(self):
        battle, charger, _ = _build_charge_battle()
        battle._advanced_this_round.add(charger.uid)
        battle._do_charge(charger, battle.a, battle.b)
        self.assertNotIn(
            charger.uid, battle._charging_this_round,
            "a unit that Advanced must NOT charge without the exemption "
            "(10e core advance lockout)",
        )

    def test_advanced_unit_charges_with_flag(self):
        battle, charger, _ = _build_charge_battle()
        battle._advanced_this_round.add(charger.uid)
        charger.transient_charge_after_advance = True
        battle._do_charge(charger, battle.a, battle.b)
        self.assertIn(
            charger.uid, battle._charging_this_round,
            "with transient_charge_after_advance the Advanced unit must be "
            "eligible to charge (Apoplectic Frenzy verbatim effect)",
        )

    def test_non_advanced_unit_charges_normally(self):
        # Baseline sanity: without Advancing, the charge goes through with
        # no flag at all (the lockout gate is the only thing under test).
        battle, charger, _ = _build_charge_battle()
        battle._do_charge(charger, battle.a, battle.b)
        self.assertIn(
            charger.uid, battle._charging_this_round,
            "a unit that did not Advance must charge normally at 2.5 inches",
        )


if __name__ == "__main__":
    unittest.main()
