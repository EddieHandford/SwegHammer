"""Tests for the 10e Leviathan Tournament Companion Primary VP cap.

Rule: each army may score a maximum of 15 Primary VP per battle round
(i.e. at most 3 controlled objectives counted at 5 VP each), regardless
of how many objectives they hold. Applied inside
`Battle._score_objectives` after per-objective awards are tallied.

Source:
https://wahapedia.ru/wh40k10ed/the-rules/leviathan-tournament-companion/
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _profile(name: str = "Trooper", **overrides) -> UnitProfile:
    base = dict(
        name=name, health=1, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        faction="Adeptus Astartes",
    )
    base.update(overrides)
    return UnitProfile(**base)


class PrimaryVpCapTests(unittest.TestCase):
    """Cap is applied per-army per-round in `_score_objectives`."""

    def _setup_battle(self, num_alpha_holders: int):
        """Build a battle whose default map has 5 quincunx objectives and
        park `num_alpha_holders` Alpha units, one on each of the first
        N objectives. Bravo is parked far away so Alpha controls cleanly.
        """
        random.seed(0)
        a = Army("Alpha")
        for i in range(num_alpha_holders):
            a.add_unit(_profile(f"AlphaHolder{i}", oc=2))
        b = Army("Bravo")
        b.add_unit(_profile("BravoTrooper", oc=1))

        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()

        # Park Alpha holders on the first N objectives, one each.
        objectives = battle.map.objectives
        self.assertGreaterEqual(
            len(objectives), num_alpha_holders,
            "default map must have enough objectives for this test",
        )
        for i, holder in enumerate(a.units):
            obj = objectives[i]
            holder.position = (obj.x, obj.y)

        # Park Bravo far from every objective.
        b.units[0].position = (-100.0, -100.0)

        return battle, a, b

    def test_five_held_caps_at_15_not_25(self):
        """Alpha sits on all 5 quincunx objectives; raw award is 25 VP
        but the cap clamps it to 15."""
        battle, a, b = self._setup_battle(num_alpha_holders=5)
        # Sanity: map really has 5 objectives.
        self.assertEqual(len(battle.map.objectives), 5)

        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()

        self.assertEqual(
            battle._a_vp, 15,
            "Alpha controls 5 objectives (raw 25 VP); cap must clamp to 15.",
        )
        self.assertEqual(
            battle._b_vp, 0,
            "Bravo holds nothing; should score 0.",
        )

    def test_three_held_scores_exactly_15(self):
        """Alpha sits on 3 objectives; 3 x 5 = 15 VP, equal to the cap,
        so the cap is a no-op and the army receives the full amount."""
        battle, a, b = self._setup_battle(num_alpha_holders=3)
        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()

        self.assertEqual(
            battle._a_vp, 15,
            "3 controlled objectives at 5 VP each = 15 VP (at the cap).",
        )

    def test_two_held_scores_10_uncapped(self):
        """Alpha sits on 2 objectives; 2 x 5 = 10 VP, well under the cap,
        so the cap is a no-op."""
        battle, a, b = self._setup_battle(num_alpha_holders=2)
        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()

        self.assertEqual(
            battle._a_vp, 10,
            "2 controlled objectives at 5 VP each = 10 VP (below cap).",
        )

    def test_cap_applies_per_round_not_per_battle(self):
        """The cap is per-round: an army holding 5 objectives in three
        consecutive rounds should accumulate 45 VP (3 * 15), not 75 or 15."""
        battle, a, b = self._setup_battle(num_alpha_holders=5)
        battle._a_vp = 0
        battle._b_vp = 0
        for _ in range(3):
            battle._score_objectives()
        self.assertEqual(
            battle._a_vp, 45,
            "Cap is per-round: 3 rounds * 15 = 45 VP.",
        )


if __name__ == "__main__":
    unittest.main()
