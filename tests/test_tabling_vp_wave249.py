"""Tests for wave 249 lever 1: tabling decides on Victory Points, not automatic win.

Gate: SWEG_TABLING_VP (default OFF).

When OFF (default): a one-sided tabling (one army has zero survivors) is an
automatic win for the surviving army, regardless of Victory Points totals.
When ON: the result is decided by the accumulated Victory Points totals only,
exactly as the 10th edition core rule states ("the player with the most Victory
Points is the winner"). The run loop already plays out all five battle rounds
on a one-sided tabling, so the Victory Points totals are complete at decision time.

Source: https://wahapedia.ru/wh40k10ed/the-rules/matched-play/ — Determine Victor.
Cited as simulator.win_on_vp_not_tabling in data/rule_citations.d/core_win_condition.json.
"""

from __future__ import annotations

import os
import random
import types
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _profile(name: str = "Trooper", **overrides) -> UnitProfile:
    """Build a minimal UnitProfile sufficient for a Battle construct."""
    base = dict(
        name=name, health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        faction="Adeptus Astartes",
    )
    base.update(overrides)
    return UnitProfile(**base)


def _make_battle() -> Battle:
    """Construct a minimal Battle and return it before running."""
    random.seed(0)
    a = Army("Alpha")
    a.add_unit(_profile("AlphaTrooper"))
    b = Army("Bravo")
    b.add_unit(_profile("BravoTrooper"))
    battle = Battle(a, b)
    battle._assign_uids()
    battle._deploy_armies()
    return battle


def _call_decide(battle: Battle, a_surv: int, b_surv: int,
                  a_vp: int, b_vp: int,
                  a_secondary: int, b_secondary: int,
                  a_pts: float = 100.0, b_pts: float = 100.0) -> object:
    """Set VP state on the Battle, then call _decide_winner and return the result."""
    battle._a_vp = a_vp
    battle._b_vp = b_vp
    battle._a_secondary_vp = a_secondary
    battle._b_secondary_vp = b_secondary
    return battle._decide_winner(a_surv, b_surv, a_pts, b_pts)


class TablingVpGateOffTests(unittest.TestCase):
    """With SWEG_TABLING_VP unset (default), tabling is an automatic win."""

    def setUp(self):
        os.environ.pop("SWEG_TABLING_VP", None)
        self.battle = _make_battle()

    def tearDown(self):
        os.environ.pop("SWEG_TABLING_VP", None)

    def test_b_tabled_a_wins_even_when_a_has_lower_vp(self):
        """Side B is tabled (b_surv == 0) but side A has LOWER Victory Points.
        OFF arm: auto-win for the surviving army (Alpha) regardless of Victory Points."""
        # Alpha has 20 Victory Points, Bravo has 35 Victory Points — Bravo led on points.
        # But Bravo is tabled (b_surv == 0). Default path returns Alpha outright.
        result = _call_decide(
            self.battle,
            a_surv=3, b_surv=0,
            a_vp=20, b_vp=35,
            a_secondary=5, b_secondary=10,
        )
        self.assertEqual(
            result, "Alpha",
            "OFF arm: tabling must give automatic win to the surviving army (Alpha), "
            "ignoring that Bravo had more Victory Points.",
        )

    def test_a_tabled_b_wins_even_when_b_has_lower_vp(self):
        """Side A is tabled (a_surv == 0) but side B has LOWER Victory Points.
        OFF arm: auto-win for the surviving army (Bravo)."""
        result = _call_decide(
            self.battle,
            a_surv=0, b_surv=5,
            a_vp=40, b_vp=15,
            a_secondary=10, b_secondary=5,
        )
        self.assertEqual(result, "Bravo", "OFF arm: tabling gives Bravo the win.")

    def test_mutual_wipe_returns_draw(self):
        """Mutual wipe (both sides zero survivors) is a draw in the OFF arm."""
        result = _call_decide(
            self.battle,
            a_surv=0, b_surv=0,
            a_vp=30, b_vp=30,
            a_secondary=10, b_secondary=10,
        )
        self.assertIsNone(result, "OFF arm: mutual wipe must be a draw (None).")


class TablingVpGateOnTests(unittest.TestCase):
    """With SWEG_TABLING_VP=1, one-sided tabling is decided by Victory Points."""

    def setUp(self):
        os.environ["SWEG_TABLING_VP"] = "1"
        # Disable the primary cap so VP arithmetic is straightforward.
        os.environ["SWEG_PRIMARY_CAP_50"] = "0"
        self.battle = _make_battle()

    def tearDown(self):
        os.environ.pop("SWEG_TABLING_VP", None)
        os.environ.pop("SWEG_PRIMARY_CAP_50", None)

    def test_b_tabled_but_b_has_more_vp_b_wins(self):
        """Side B is tabled (b_surv == 0) but accumulated more Victory Points.
        ON arm: Bravo wins on Victory Points."""
        # All VP is primary (secondary = 0 for simplicity). Bravo scored 35, Alpha 20.
        result = _call_decide(
            self.battle,
            a_surv=3, b_surv=0,
            a_vp=20, b_vp=35,
            a_secondary=0, b_secondary=0,
        )
        self.assertEqual(
            result, "Bravo",
            "ON arm: tabled side Bravo had more Victory Points (35 vs 20) "
            "and must win.",
        )

    def test_b_tabled_and_a_has_more_vp_a_wins(self):
        """Side B is tabled and Alpha also leads on Victory Points.
        ON arm: Alpha wins (same result as OFF arm for this scenario)."""
        result = _call_decide(
            self.battle,
            a_surv=3, b_surv=0,
            a_vp=40, b_vp=20,
            a_secondary=0, b_secondary=0,
        )
        self.assertEqual(result, "Alpha", "ON arm: Alpha wins on Victory Points.")

    def test_mutual_wipe_equal_vp_returns_draw(self):
        """Mutual wipe with equal Victory Points is a draw in the ON arm."""
        result = _call_decide(
            self.battle,
            a_surv=0, b_surv=0,
            a_vp=30, b_vp=30,
            a_secondary=10, b_secondary=10,
        )
        self.assertIsNone(result, "ON arm: mutual wipe with equal VP must be a draw.")

    def test_mutual_wipe_unequal_vp_higher_vp_wins(self):
        """Mutual wipe where one side accumulated more Victory Points.
        ON arm: the side with more Victory Points wins."""
        result = _call_decide(
            self.battle,
            a_surv=0, b_surv=0,
            a_vp=45, b_vp=30,
            a_secondary=15, b_secondary=10,
        )
        self.assertEqual(
            result, "Alpha",
            "ON arm: mutual wipe where Alpha led on Victory Points — Alpha wins.",
        )


class BothSidesAliveIdenticalWinnerTests(unittest.TestCase):
    """When both sides have surviving units, gate value must not change the winner.

    This proves the gate only changes the tabling path; the standard
    Victory Points comparison path is unaffected.
    """

    def tearDown(self):
        os.environ.pop("SWEG_TABLING_VP", None)
        os.environ.pop("SWEG_PRIMARY_CAP_50", None)

    def _winner_with_gate(self, gate_on: bool) -> object:
        os.environ.pop("SWEG_TABLING_VP", None)
        os.environ.pop("SWEG_PRIMARY_CAP_50", None)
        if gate_on:
            os.environ["SWEG_TABLING_VP"] = "1"
            os.environ["SWEG_PRIMARY_CAP_50"] = "0"
        battle = _make_battle()
        # Both armies have survivors; Alpha is clearly ahead on Victory Points.
        return _call_decide(
            battle,
            a_surv=4, b_surv=2,
            a_vp=40, b_vp=20,
            a_secondary=10, b_secondary=5,
        )

    def test_gate_off_alpha_wins_on_vp(self):
        """Both sides alive, Alpha ahead on Victory Points: Alpha wins (gate OFF)."""
        self.assertEqual(self._winner_with_gate(False), "Alpha")

    def test_gate_on_alpha_wins_on_vp(self):
        """Both sides alive, Alpha ahead on Victory Points: Alpha wins (gate ON)."""
        self.assertEqual(self._winner_with_gate(True), "Alpha")

    def test_winner_identical_both_gate_states(self):
        """Result is byte-identical across gate states when both armies have survivors."""
        self.assertEqual(
            self._winner_with_gate(False),
            self._winner_with_gate(True),
            "Gate must not affect the winner when both armies still have survivors.",
        )


if __name__ == "__main__":
    unittest.main()
