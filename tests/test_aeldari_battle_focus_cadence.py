"""Tests for the Aeldari Battle Focus per-round token grant cadence.

AELDARI-BATTLE-FOCUS-V2 (wave 235): the token grant was moved from a
once-at-battle-start flat pool to a per-round additive grant scaled by
battle size, matching the verbatim Wahapedia rule:

  "At the start of the battle round, you receive a number of Battle Focus
   tokens based on the battle size, as shown in the table below."
   Table: Incursion 2 | Strike Force 4 | Onslaught 6.

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Battle-Focus

Warhost Martial Grace adds +1 per round:
  "At the start of the battle round, you receive 1 additional Battle Focus
   token."

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Warhost

These tests exercise Battle._grant_battle_focus_tokens directly — the
function is the boundary between the per-round cadence and the token spend
gate in Unit.attack. Running full battles is unnecessary: the spend gate
is covered by the strategy tests in test_aeldari_battle_focus.py.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.detachments import Detachment, WARHOST
from code.map import Map
from code.simulator import Battle
from code.units import Unit, UnitProfile


# --------------------------------------------------------------------------- #
# A minimal Aeldari detachment with martial_grace=False so we can test the    #
# base grant in isolation without the Warhost +1-per-round bump.               #
# The Aeldari default detachment (Warhost) has martial_grace=True; any test   #
# that wants the plain base grant must supply this fixture explicitly.         #
# --------------------------------------------------------------------------- #
_NO_GRACE_DET = Detachment(name="TestAeldariDet", faction="Aeldari", martial_grace=False)


# --------------------------------------------------------------------------- #
# Profile helpers                                                              #
# --------------------------------------------------------------------------- #


def _asuryani_profile() -> UnitProfile:
    """A minimal ASURYANI unit profile — just enough to pass the faction gate."""
    return UnitProfile(
        name="Guardian",
        faction="Aeldari",
        health=4,
        damage=2,
        hit_probability=2 / 3,
        ap=-1,
        save=4,
        strength=4,
        toughness=3,
        attacks=2,
        weapon_damage_per_shot=1.0,
        range_inches=18,
        leadership=7,
        unit_keywords=("INFANTRY", "ASURYANI"),
        move=6.0,
        melee_attacks=1,
        melee_hit_probability=0.5,
        melee_strength=3,
        melee_damage_per_shot=1.0,
        melee_ap=0,
    )


def _non_asuryani_profile() -> UnitProfile:
    """A non-ASURYANI profile — must never receive Battle Focus tokens."""
    return UnitProfile(
        name="Marine",
        faction="Space Marines",
        health=4,
        damage=2,
        hit_probability=2 / 3,
        ap=-1,
        save=3,
        strength=4,
        toughness=4,
        attacks=2,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        leadership=8,
        unit_keywords=("INFANTRY", "ADEPTUS ASTARTES"),
        move=6.0,
        melee_attacks=2,
        melee_hit_probability=2 / 3,
        melee_strength=4,
        melee_damage_per_shot=1.0,
        melee_ap=-1,
    )


def _make_battle(army_a: Army, army_b: Army) -> Battle:
    """Build a minimal Battle with no objectives or terrain."""
    return Battle(army_a, army_b, map_=Map("Test", 60.0, 44.0))


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #


class BattleFocusGrantPerRoundTests(unittest.TestCase):
    """_grant_battle_focus_tokens must add tokens each call, not set them once.

    These tests use _NO_GRACE_DET (martial_grace=False) to isolate the base
    battle-size grant from the Warhost +1 per round. The Aeldari default
    detachment is Warhost (martial_grace=True); without an explicit non-Warhost
    detachment the counts would be 5/15/9 instead of 4/12/7.
    """

    def _asuryani_army(self, pts: float) -> Army:
        # Explicit non-Warhost detachment so the base grant is tested alone.
        army = Army("Aeldari", detachment=_NO_GRACE_DET)
        army.add_unit(_asuryani_profile())
        army.starting_points = pts
        return army

    def test_tokens_start_at_zero(self):
        """Army.battle_focus_tokens begins at 0 before any grant."""
        army = self._asuryani_army(2000.0)
        self.assertEqual(army.battle_focus_tokens, 0)

    def test_grant_once_adds_strike_force_tokens(self):
        """A single call at 2000 pts grants 4 tokens (Strike Force table entry)."""
        army = self._asuryani_army(2000.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 4)

    def test_grant_three_rounds_is_additive(self):
        """Tokens accumulate across rounds — three rounds of 4 = 12 tokens."""
        army = self._asuryani_army(2000.0)
        battle = _make_battle(army, Army("Opponent"))
        for _ in range(3):
            battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 12)

    def test_spend_and_grant_carryover(self):
        """Unspent tokens carry over: grant 4, spend 1, grant 4 again = 7."""
        army = self._asuryani_army(2000.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)   # +4 → 4
        army.battle_focus_tokens -= 1             # spend 1 → 3
        battle._grant_battle_focus_tokens(army)   # +4 → 7
        self.assertEqual(army.battle_focus_tokens, 7)


class BattleFocusBattleSizeTests(unittest.TestCase):
    """Battle size thresholds from the Wahapedia table:
    Incursion (≤1000 pts) → 2 tokens/round
    Strike Force (≤2000 pts) → 4 tokens/round
    Onslaught (>2000 pts) → 6 tokens/round

    These tests use _NO_GRACE_DET (martial_grace=False) to isolate the
    battle-size grant from the Warhost +1 per round.
    """

    def _army(self, pts: float) -> Army:
        # Explicit non-Warhost detachment so the base grant is tested alone.
        army = Army("Aeldari", detachment=_NO_GRACE_DET)
        army.add_unit(_asuryani_profile())
        army.starting_points = pts
        return army

    def test_incursion_500pts_grants_2_per_round(self):
        """500 pts = Incursion → 2 tokens per round."""
        army = self._army(500.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 2)

    def test_incursion_1000pts_boundary_grants_2_per_round(self):
        """1000 pts is the Incursion upper boundary → 2 tokens per round."""
        army = self._army(1000.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 2)

    def test_strike_force_1001pts_grants_4_per_round(self):
        """1001 pts is above the Incursion ceiling → 4 tokens per round."""
        army = self._army(1001.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 4)

    def test_strike_force_2000pts_grants_4_per_round(self):
        """2000 pts = Strike Force (the evaluation default) → 4 tokens per round."""
        army = self._army(2000.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 4)

    def test_onslaught_2001pts_grants_6_per_round(self):
        """2001 pts is above Strike Force ceiling → 6 tokens per round."""
        army = self._army(2001.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 6)

    def test_onslaught_3000pts_grants_6_per_round(self):
        """3000 pts = Onslaught → 6 tokens per round."""
        army = self._army(3000.0)
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 6)


class BattleFocusWarhostMartialGraceTests(unittest.TestCase):
    """Warhost Martial Grace adds +1 Battle Focus token per round on top of the
    battle-size base grant — not +1 once to the starting pool."""

    def test_warhost_adds_one_per_round_at_strike_force(self):
        """Strike Force (2000 pts) Warhost: 4 + 1 = 5 tokens per round."""
        army = Army("Aeldari", detachment=WARHOST)
        army.add_unit(_asuryani_profile())
        army.starting_points = 2000.0
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 5)

    def test_warhost_adds_one_each_round_not_just_first(self):
        """Three rounds of Warhost grants 5 tokens each = 15 total."""
        army = Army("Aeldari", detachment=WARHOST)
        army.add_unit(_asuryani_profile())
        army.starting_points = 2000.0
        battle = _make_battle(army, Army("Opponent"))
        for _ in range(3):
            battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 15)

    def test_non_warhost_does_not_get_extra_token(self):
        """An Aeldari army with a non-Warhost detachment gets exactly the base grant."""
        army = Army("Aeldari", detachment=_NO_GRACE_DET)
        army.add_unit(_asuryani_profile())
        army.starting_points = 2000.0
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 4)

    def test_warhost_grants_one_extra_vs_non_warhost(self):
        """Warhost grant must exceed non-Warhost grant by exactly 1 per round."""
        no_grace_det = _NO_GRACE_DET
        warhost_army = Army("Aeldari", detachment=WARHOST)
        warhost_army.add_unit(_asuryani_profile())
        warhost_army.starting_points = 2000.0

        plain_army = Army("Aeldari", detachment=no_grace_det)
        plain_army.add_unit(_asuryani_profile())
        plain_army.starting_points = 2000.0

        battle_w = _make_battle(warhost_army, Army("Opponent"))
        battle_p = _make_battle(plain_army, Army("Opponent"))

        battle_w._grant_battle_focus_tokens(warhost_army)
        battle_p._grant_battle_focus_tokens(plain_army)

        self.assertEqual(
            warhost_army.battle_focus_tokens - plain_army.battle_focus_tokens, 1
        )


class BattleFocusNonAsuryaniTests(unittest.TestCase):
    """Non-ASURYANI armies must never receive Battle Focus tokens."""

    def test_non_asuryani_army_gets_no_tokens(self):
        """A Space Marines army gets zero tokens regardless of points."""
        army = Army("Space Marines")
        army.add_unit(_non_asuryani_profile())
        army.starting_points = 2000.0
        battle = _make_battle(army, Army("Opponent"))
        battle._grant_battle_focus_tokens(army)
        self.assertEqual(army.battle_focus_tokens, 0)


class BattleFocusStartingPointsErrorTests(unittest.TestCase):
    """Battle._grant_battle_focus_tokens must fail loud when starting_points
    is 0 (unset), not silently default to any battle size."""

    def test_raises_if_starting_points_not_set(self):
        """starting_points=0 means the army was not initialised before the
        round loop. This must raise RuntimeError, not silently grant tokens."""
        army = Army("Aeldari")
        army.add_unit(_asuryani_profile())
        # starting_points defaults to 0.0 in Army.__init__ — do not set it.
        self.assertEqual(army.starting_points, 0.0)
        battle = _make_battle(army, Army("Opponent"))
        with self.assertRaises(RuntimeError):
            battle._grant_battle_focus_tokens(army)


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
