"""Wave 236 regression tests: Dark Pacts proxy replaced with verbatim
[LETHAL HITS] grant (election model unchanged).

Verbatim rule (BSData Chaos - Chaos Space Marines.cat.gz, rule id
fd69-68cc-5d63-c84d):
"If your Army Faction is Heretic Astartes, each time a unit with this
ability is selected to shoot or fight, it can make a Dark Pact. If it
does, it must first take a Leadership test before any effects of the Dark
Pact are resolved; if that test is failed, that unit suffers D3 mortal
wounds. Then, select one of the following abilities for that unit's
weapons to gain until the end of the phase:
  [LETHAL HITS]
  [SUSTAINED HITS 1]"

Wave 236 correction: the old proxy (transient_plus_one_to_hit_shooting +
transient_plus_one_to_wound_melee) is replaced by transient_lethal_hits.
The election model is unchanged: exactly one Chaos Space Marines unit
(the highest damage-per-activation pick, only when damage-per-activation
>= 6) declares the pact per round — the wave-209 coverage-expansion
experiment was abandoned and must not be re-attempted.

CHOICE COLLAPSE approximation: the rule offers [LETHAL HITS] or
[SUSTAINED HITS 1] at the player's choice. We always grant [LETHAL HITS]
(the competitively dominant pick); no target-context plumbing is built.

Assertions:
a) After _apply_dark_pacts fires, the elected unit has transient_lethal_hits
   True, and does NOT have transient_plus_one_to_hit_shooting or
   transient_plus_one_to_wound_melee set.
b) The grant does not leak to other units (neither the enemy nor a
   second Chaos Space Marines unit that lost the election).
c) The Leadership-test mortal-wound path: _apply_mortal_wounds is called
   when the Leadership test fails. Verified by patching random.randint to
   always return 1 (roll = 2, fails any Leadership >= 3) and asserting the
   elected unit loses hit points.
d) Election stays one-unit-per-round: the highest-damage-per-activation
   unit is elected; a lower-damage-per-activation unit in the same army
   does NOT receive the grant.
"""

from __future__ import annotations

import random
import unittest
import unittest.mock

from code.army import Army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csm_unit(
    name: str = "CSM Terminator",
    points: float = 150.0,
    dpa: float = 8.0,
    health: int = 3,
    leadership: int = 7,
) -> UnitProfile:
    """A high-damage-per-activation Chaos Space Marines unit that exceeds
    the Dark Pacts opt-in threshold (damage-per-activation >= 6).

    damage-per-activation = ranged + melee = dpa parameter (split evenly).
    By default: ranged 4.0 + melee 4.0 = 8.0 (well above the 6.0 gate).
    """
    half = dpa / 2.0
    # attacks * hit_probability * damage_per_shot = half
    # Use 4 attacks, hit_probability=0.5, damage_per_shot=half/2
    return UnitProfile(
        name=name,
        health=health,
        damage=2,
        hit_probability=0.5,
        ap=-2,
        save=3,
        strength=6,
        toughness=5,
        attacks=4,
        weapon_damage_per_shot=half / 2.0,
        range_inches=24,
        leadership=leadership,
        faction="Chaos Space Marines",
        unit_keywords=("INFANTRY",),
        melee_attacks=4,
        melee_damage_per_shot=half / 2.0,
        melee_hit_probability=0.5,
        melee_strength=6,
        melee_ap=-2,
        points_override=points,
    )


def _weak_csm_unit(name: str = "CSM Cultist") -> UnitProfile:
    """A weak Chaos Space Marines unit whose damage-per-activation (< 6) is
    below the Dark Pacts opt-in threshold — should never receive the grant."""
    return UnitProfile(
        name=name,
        health=1,
        damage=1,
        hit_probability=0.5,
        ap=0,
        save=5,
        strength=3,
        toughness=3,
        attacks=1,
        weapon_damage_per_shot=0.5,
        range_inches=24,
        leadership=6,
        faction="Chaos Space Marines",
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_damage_per_shot=0.3,
        melee_hit_probability=0.5,
        melee_strength=3,
        melee_ap=0,
        points_override=50.0,
    )


def _astartes_unit(name: str = "Space Marine") -> UnitProfile:
    """A generic enemy unit — not Chaos Space Marines."""
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
        range_inches=24,
        faction="Space Marines",
        unit_keywords=("INFANTRY",),
        melee_attacks=2,
        melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3,
        melee_strength=4,
        melee_ap=0,
        points_override=80.0,
    )


def _open_map() -> Map:
    """60x60 board with one objective so strategy lookups have data."""
    obj = Objective(name="Centre", x=30.0, y=30.0, control_radius=3.0)
    return Map(name="open", width=60.0, height=60.0, objectives=(obj,))


def _build_battle_one_csm() -> tuple:
    """One high-damage-per-activation Chaos Space Marines unit vs one Astartes
    unit. The elected unit is the single Chaos Space Marines model."""
    csm_army = Army("Chaos Space Marines")
    csm_army.add_unit(_csm_unit())
    enemy = Army("Space Marines")
    enemy.add_unit(_astartes_unit())
    battle = Battle(csm_army, enemy, map_=_open_map(), verbose=False)
    battle._assign_uids()
    return battle, csm_army, enemy


def _build_battle_two_csm() -> tuple:
    """Two Chaos Space Marines units (one strong, one weak) vs one Astartes
    unit. Used to verify the election selects only the strong unit."""
    csm_army = Army("Chaos Space Marines")
    csm_army.add_unit(_csm_unit(name="CSM Terminator", dpa=8.0))
    csm_army.add_unit(_weak_csm_unit(name="CSM Cultist"))
    enemy = Army("Space Marines")
    enemy.add_unit(_astartes_unit())
    battle = Battle(csm_army, enemy, map_=_open_map(), verbose=False)
    battle._assign_uids()
    return battle, csm_army, enemy


# ---------------------------------------------------------------------------
# (a) Verbatim grant: transient_lethal_hits set; old proxies not set
# ---------------------------------------------------------------------------


class TestDarkPactsVerbatimGrant(unittest.TestCase):
    """After _apply_dark_pacts fires, the elected unit must have
    transient_lethal_hits True and the old proxy flags must be False."""

    def _fire_pacts(self):
        battle, csm_army, enemy = _build_battle_one_csm()
        elected = csm_army.units[0]
        enemy_unit = enemy.units[0]
        # Guarantee the Leadership test passes so no mortal wounds obscure
        # the flag state (roll=12 always passes any Leadership).
        with unittest.mock.patch("random.randint", return_value=6):
            battle._apply_dark_pacts(round_num=1)
        return elected, enemy_unit

    def test_transient_lethal_hits_set(self):
        elected, _ = self._fire_pacts()
        self.assertTrue(
            elected.transient_lethal_hits,
            "transient_lethal_hits must be True after Dark Pacts fires "
            "(wave 236 verbatim [LETHAL HITS] grant)",
        )

    def test_old_hit_proxy_not_set(self):
        elected, _ = self._fire_pacts()
        self.assertFalse(
            elected.transient_plus_one_to_hit_shooting,
            "transient_plus_one_to_hit_shooting must NOT be set — the old "
            "+1-to-hit proxy was removed in wave 236",
        )

    def test_old_wound_proxy_not_set(self):
        elected, _ = self._fire_pacts()
        self.assertFalse(
            elected.transient_plus_one_to_wound_melee,
            "transient_plus_one_to_wound_melee must NOT be set — the old "
            "+1-to-wound proxy was removed in wave 236",
        )


# ---------------------------------------------------------------------------
# (b) Grant does not leak to other units
# ---------------------------------------------------------------------------


class TestDarkPactsNoLeak(unittest.TestCase):
    """The [LETHAL HITS] grant must not reach the enemy or the losing
    Chaos Space Marines candidate."""

    def test_grant_does_not_reach_enemy(self):
        battle, csm_army, enemy = _build_battle_one_csm()
        with unittest.mock.patch("random.randint", return_value=6):
            battle._apply_dark_pacts(round_num=1)
        enemy_unit = enemy.units[0]
        self.assertFalse(
            enemy_unit.transient_lethal_hits,
            "transient_lethal_hits must NOT leak to the enemy unit",
        )

    def test_grant_does_not_reach_losing_candidate(self):
        """When two Chaos Space Marines units are present, only the highest-
        damage-per-activation unit is elected; the weak cultist must not
        receive the grant."""
        battle, csm_army, enemy = _build_battle_two_csm()
        terminator = csm_army.units[0]  # dpa=8.0, elected
        cultist = csm_army.units[1]     # dpa<6, not elected

        with unittest.mock.patch("random.randint", return_value=6):
            battle._apply_dark_pacts(round_num=1)

        self.assertTrue(
            terminator.transient_lethal_hits,
            "the high-damage-per-activation Terminator must receive the grant",
        )
        self.assertFalse(
            cultist.transient_lethal_hits,
            "the low-damage-per-activation Cultist must NOT receive the grant "
            "(only one unit is elected per round)",
        )


# ---------------------------------------------------------------------------
# (c) Leadership-test mortal-wound path fires on failure
# ---------------------------------------------------------------------------


class TestDarkPactsMortalWoundPath(unittest.TestCase):
    """When the Leadership test fails (roll < Leadership), the elected unit
    suffers D3 mortal wounds.

    Strategy: patch random.randint to always return 1 so the 2D6 roll = 2,
    which fails any Leadership >= 3. Then assert the unit's hit points have
    decreased from their initial value.
    """

    def test_mortal_wounds_applied_on_ld_failure(self):
        battle, csm_army, enemy = _build_battle_one_csm()
        elected = csm_army.units[0]
        # Record health before
        health_before = elected.current_health

        # roll=1 each time -> 2D6=2, Leadership=7 -> fails
        with unittest.mock.patch("random.randint", return_value=1):
            battle._apply_dark_pacts(round_num=1)

        health_after = elected.current_health
        self.assertLess(
            health_after,
            health_before,
            "elected unit must have lost hit points after a failed "
            "Leadership test (D3 mortal wounds)",
        )


# ---------------------------------------------------------------------------
# (d) Election stays one unit per round
# ---------------------------------------------------------------------------


class TestDarkPactsElectionModel(unittest.TestCase):
    """Exactly one unit is elected per army per round: the highest-
    damage-per-activation Chaos Space Marines unit above the opt-in
    threshold. The wave-209 coverage expansion is not re-attempted."""

    def test_only_strongest_unit_elected(self):
        battle, csm_army, enemy = _build_battle_two_csm()
        with unittest.mock.patch("random.randint", return_value=6):
            battle._apply_dark_pacts(round_num=1)

        elected_count = sum(
            1 for u in csm_army.units if u.transient_lethal_hits
        )
        self.assertEqual(
            elected_count,
            1,
            "exactly one Chaos Space Marines unit must be elected per round "
            "(wave-209 coverage expansion is permanently reverted)",
        )

    def test_weak_unit_below_threshold_is_skipped(self):
        """An army with only a low-damage-per-activation Chaos Space Marines
        unit must opt out entirely — no grant fires."""
        csm_army = Army("Chaos Space Marines")
        csm_army.add_unit(_weak_csm_unit())
        enemy = Army("Space Marines")
        enemy.add_unit(_astartes_unit())
        battle = Battle(csm_army, enemy, map_=_open_map(), verbose=False)
        battle._assign_uids()

        with unittest.mock.patch("random.randint", return_value=6):
            battle._apply_dark_pacts(round_num=1)

        weak_unit = csm_army.units[0]
        self.assertFalse(
            weak_unit.transient_lethal_hits,
            "a unit below the damage-per-activation threshold must not "
            "receive the Dark Pacts grant (opt-out: not worth the D3 mortal "
            "wound gamble)",
        )


if __name__ == "__main__":
    unittest.main()
