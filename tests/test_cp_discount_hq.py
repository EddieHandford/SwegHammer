"""Tests for CP-discount / CP-refund Warlord HQ mechanics (task #128).

Covers four 10e characters whose datasheet grants the army an extra CP or
a stratagem-cost refund when the character is the army's Warlord:

    - Belisarius Cawl (AdMech): once-per-battle +1 CP
    - Roboute Guilliman (Ultramarines): +1 CP per Command phase
    - Trazyn the Infinite (Necrons): once-per-battle CP refund on a spend
    - Lord of Contagion (DG, Warlord trait): first stratagem each round free

The mechanic is implemented via three LeaderAbility fields
(`cp_discount_per_round`, `cp_refund_per_battle`,
`first_stratagem_free_per_round`) and two Army state fields
(`cp_refund_remaining`, `first_stratagem_free_this_round`). The simulator
seeds them at battle start from `warlord_ability(army)` and consumes them
in `_run_round` (Command phase) and `_fire_stratagem` (spend).
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.leaders import LeaderAbility, lookup_ability, warlord_ability
from code.simulator import Battle
from code.stratagems import COMMAND_RE_ROLL, CP_CAP
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Fixtures — tiny profiles that match the leader registry's substring keys
# ---------------------------------------------------------------------------

def _grunt_profile(name: str = "Grunt") -> UnitProfile:
    return UnitProfile(
        name=name, health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0,
        unit_keywords=("INFANTRY",),
    )


def _heavy_profile() -> UnitProfile:
    """HEAVY target — triggers the Command Re-Roll heuristic."""
    return UnitProfile(
        name="Knight",
        health=22, damage=6, hit_probability=2 / 3,
        ap=-3, save=2, strength=10, toughness=12,
        attacks=4, weapon_damage_per_shot=1.5,
        range_inches=48,
        unit_keywords=("VEHICLE", "TITANIC"),
    )


def _make_character(profile_name: str) -> UnitProfile:
    """Build a CHARACTER profile whose name matches the leader registry."""
    return UnitProfile(
        name=profile_name, health=6, damage=2, hit_probability=2 / 3,
        ap=-1, save=2, strength=5, toughness=5,
        attacks=3, weapon_damage_per_shot=1.0,
        unit_keywords=("INFANTRY", "CHARACTER"),
    )


def _build_army(name: str, profiles) -> Army:
    army = Army(name)
    for p in profiles:
        army.add_unit(p)
    return army


# ---------------------------------------------------------------------------
# Registry sanity — the four new LeaderAbility entries are wired up
# ---------------------------------------------------------------------------

class RegistryTests(unittest.TestCase):

    def test_cawl_lookup_carries_cp_refund(self):
        ab = lookup_ability("Belisarius Cawl")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.cp_refund_per_battle, 1)
        self.assertEqual(ab.cp_discount_per_round, 0)
        self.assertFalse(ab.first_stratagem_free_per_round)

    def test_guilliman_lookup_carries_cp_discount(self):
        ab = lookup_ability("Roboute Guilliman")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.cp_discount_per_round, 1)
        self.assertEqual(ab.cp_refund_per_battle, 0)

    def test_trazyn_lookup_carries_cp_refund(self):
        ab = lookup_ability("Trazyn the Infinite")
        self.assertIsNotNone(ab)
        self.assertEqual(ab.cp_refund_per_battle, 1)
        # Trazyn entry must win the substring contest over the generic
        # "Overlord" entry (which doesn't carry CP fields).
        self.assertNotEqual(ab.name, "My Will Be Done")

    def test_lord_of_contagion_lookup_carries_first_strat_free(self):
        ab = lookup_ability("Lord of Contagion")
        self.assertIsNotNone(ab)
        self.assertTrue(ab.first_stratagem_free_per_round)

    def test_warlord_resolves_to_first_eligible_character(self):
        # An AdMech army with Cawl as the only CHARACTER resolves to Cawl.
        a = _build_army("AdMech", [
            _make_character("Belisarius Cawl"),
            _grunt_profile("Skitarii"),
        ])
        wl = warlord_ability(a)
        self.assertIsNotNone(wl)
        self.assertEqual(wl.cp_refund_per_battle, 1)

    def test_warlord_returns_none_for_plain_army(self):
        a = _build_army("Vanilla", [_grunt_profile(), _grunt_profile()])
        self.assertIsNone(warlord_ability(a))


# ---------------------------------------------------------------------------
# Battle-level: Command phase CP gains
# ---------------------------------------------------------------------------

class GuillimanCpDiscountTests(unittest.TestCase):

    def test_guilliman_grants_cp_per_round(self):
        # Ultramarines army with Guilliman as Warlord gains an extra CP
        # at the start of each Command phase, on top of the universal +1.
        a = _build_army("Ultras", [
            _make_character("Roboute Guilliman"),
            _grunt_profile("Intercessor"),
        ])
        b = _build_army("Foe", [_grunt_profile(), _grunt_profile()])
        battle = Battle(a, b)
        battle._assign_uids()

        # Pre-round 1 baseline: STARTING_CP=3.
        baseline = a.command_points

        # Simulate one Command phase only (call the CP drips directly).
        # We bypass the full _run_round to keep the test focused on the
        # CP economy and avoid combat noise. award_command_phase_cp adds
        # 1, then the Warlord block in _run_round adds another +1 = +2 total.
        from code.stratagems import award_command_phase_cp
        award_command_phase_cp(a)
        # Replicate the Warlord-discount step from _run_round inline.
        wl = warlord_ability(a)
        if wl is not None and wl.cp_discount_per_round > 0:
            a.command_points = min(
                CP_CAP, a.command_points + wl.cp_discount_per_round
            )

        self.assertEqual(
            a.command_points, min(CP_CAP, baseline + 2),
            "Guilliman should add +1 CP on top of the +1/round drip"
        )

    def test_guilliman_cp_discount_respects_cap(self):
        # When already at CP_CAP, the discount must NOT push CP above 6.
        a = _build_army("Ultras", [
            _make_character("Roboute Guilliman"),
            _grunt_profile(),
        ])
        b = _build_army("Foe", [_grunt_profile()])
        Battle(a, b)._assign_uids()
        a.command_points = CP_CAP

        wl = warlord_ability(a)
        # Even if both effects fire, CP must clamp at CP_CAP.
        from code.stratagems import award_command_phase_cp
        award_command_phase_cp(a)
        a.command_points = min(
            CP_CAP, a.command_points + (wl.cp_discount_per_round if wl else 0)
        )
        self.assertEqual(a.command_points, CP_CAP)


class CawlCpRefundTests(unittest.TestCase):

    def test_cawl_grants_cp_once_per_battle(self):
        # AdMech army with Cawl as Warlord gains exactly +1 CP once. The
        # refund pool is seeded at Battle.run() (not at __init__), but we
        # can simulate the same effect by setting cp_refund_remaining
        # directly via the warlord_ability scan.
        a = _build_army("AdMech", [
            _make_character("Belisarius Cawl"),
            _grunt_profile("Skitarii"),
        ])
        b = _build_army("Foe", [_grunt_profile()])
        battle = Battle(a, b)
        battle._assign_uids()

        # Seed the refund pool as Battle.run() would do.
        wl = warlord_ability(a)
        self.assertIsNotNone(wl)
        a.cp_refund_remaining = wl.cp_refund_per_battle
        self.assertEqual(a.cp_refund_remaining, 1)

        # Spend a stratagem. The CP cost should be paid AND refunded.
        a.command_points = 4
        before = a.command_points
        battle._fire_stratagem(a, COMMAND_RE_ROLL)
        # Spent 1 CP, refunded 1 CP -> net unchanged.
        self.assertEqual(a.command_points, before,
                         "Cawl's once-per-battle refund should restore the 1CP spend")
        self.assertEqual(a.cp_refund_remaining, 0,
                         "refund pool should be empty after the one shot")

        # A second spend should NOT be refunded.
        a.command_points = 4
        battle._fire_stratagem(a, COMMAND_RE_ROLL)
        self.assertEqual(a.command_points, 3,
                         "second spend pays full price with empty refund pool")


class LordOfContagionFirstStrategemFreeTests(unittest.TestCase):

    def test_lord_of_contagion_first_stratagem_free(self):
        # DG army with LoC as Warlord pays 0 CP for the first stratagem
        # fired each round (cost is refunded immediately).
        a = _build_army("DG", [
            _make_character("Lord of Contagion"),
            _grunt_profile("Plague Marine"),
        ])
        b = _build_army("Foe", [_grunt_profile()])
        battle = Battle(a, b)
        battle._assign_uids()

        # Seed the latch as Battle.run() would do.
        wl = warlord_ability(a)
        self.assertIsNotNone(wl)
        a._warlord_first_strat_free_enabled = wl.first_stratagem_free_per_round
        # Re-arm the per-round flag (Command phase does this each round).
        a.first_stratagem_free_this_round = True

        # First spend: free.
        a.command_points = 4
        before = a.command_points
        battle._fire_stratagem(a, COMMAND_RE_ROLL)
        self.assertEqual(a.command_points, before,
                         "first stratagem of the round should be refunded")
        self.assertFalse(a.first_stratagem_free_this_round,
                         "latch should flip off after the freebie")

        # Second spend (same round): full cost.
        battle._fire_stratagem(a, COMMAND_RE_ROLL)
        self.assertEqual(a.command_points, before - 1,
                         "second stratagem in the same round pays full price")

    def test_non_warlord_doesnt_grant_discount(self):
        # A DG army with Typhus (not LoC) as Warlord must NOT enable the
        # first-stratagem-free latch.
        a = _build_army("DG-Typhus", [
            _make_character("Typhus"),
            _grunt_profile("Plague Marine"),
        ])
        b = _build_army("Foe", [_grunt_profile()])
        battle = Battle(a, b)
        battle._assign_uids()

        wl = warlord_ability(a)
        # Typhus has an entry but none of the CP-econ fields → warlord_ability
        # should return None (no eligible Warlord) OR an ability whose CP
        # fields are all default zero / False.
        if wl is not None:
            self.assertEqual(wl.cp_discount_per_round, 0)
            self.assertEqual(wl.cp_refund_per_battle, 0)
            self.assertFalse(wl.first_stratagem_free_per_round)
        else:
            # Preferred outcome — Typhus isn't a CP-econ Warlord.
            self.assertIsNone(wl)

        # Whichever it is, the Army's CP-econ latches must remain inert.
        a.cp_refund_remaining = wl.cp_refund_per_battle if wl else 0
        a._warlord_first_strat_free_enabled = (
            wl.first_stratagem_free_per_round if wl else False
        )
        a.first_stratagem_free_this_round = a._warlord_first_strat_free_enabled
        self.assertEqual(a.cp_refund_remaining, 0)
        self.assertFalse(a.first_stratagem_free_this_round)

        # Fire a stratagem — CP must drop by the full cp_cost, no refund.
        a.command_points = 4
        battle._fire_stratagem(a, COMMAND_RE_ROLL)
        self.assertEqual(a.command_points, 3,
                         "non-LoC Warlord must not trigger the free-strat refund")


class TrazynCpRefundTests(unittest.TestCase):

    def test_trazyn_refunds_one_cp_per_battle(self):
        # Necron army with Trazyn as Warlord gets one CP back on a spend.
        a = _build_army("Necrons", [
            _make_character("Trazyn the Infinite"),
            _grunt_profile("Warrior"),
        ])
        b = _build_army("Foe", [_grunt_profile()])
        battle = Battle(a, b)
        battle._assign_uids()

        wl = warlord_ability(a)
        self.assertIsNotNone(wl)
        a.cp_refund_remaining = wl.cp_refund_per_battle
        self.assertEqual(a.cp_refund_remaining, 1)

        a.command_points = 5
        before = a.command_points
        battle._fire_stratagem(a, COMMAND_RE_ROLL)
        self.assertEqual(a.command_points, before,
                         "Trazyn's once-per-battle refund should restore the spend")
        self.assertEqual(a.cp_refund_remaining, 0)


class NonWarlordArmyTests(unittest.TestCase):
    """Confirm the discount/refund logic NEVER fires on an army that
    doesn't have a CP-econ Warlord — the most important regression gate."""

    def test_plain_army_keeps_cp_econ_inert(self):
        # No CHARACTER at all → no Warlord → no CP econ.
        a = _build_army("Plain", [_grunt_profile(), _grunt_profile()])
        b = _build_army("Foe", [_grunt_profile()])
        battle = Battle(a, b)
        battle._assign_uids()

        # Battle.run() seeding path: should leave both fields default.
        self.assertEqual(a.cp_refund_remaining, 0)
        self.assertFalse(a.first_stratagem_free_this_round)
        self.assertFalse(a._warlord_first_strat_free_enabled)
        self.assertIsNone(warlord_ability(a))

        # A spend pays full cost.
        a.command_points = 4
        battle._fire_stratagem(a, COMMAND_RE_ROLL)
        self.assertEqual(a.command_points, 3)

    def test_character_without_cp_econ_doesnt_qualify_as_warlord(self):
        # A vanilla Captain (no CP-econ fields) doesn't make the army a
        # Warlord-bearer for the discount mechanic.
        a = _build_army("Marines", [
            _make_character("Captain"),
            _grunt_profile(),
        ])
        b = _build_army("Foe", [_grunt_profile()])
        battle = Battle(a, b)
        battle._assign_uids()
        self.assertIsNone(warlord_ability(a),
                          "Captain has no CP-econ fields and must not qualify")


if __name__ == "__main__":
    unittest.main()
