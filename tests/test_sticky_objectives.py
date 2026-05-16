"""Tests for issue #85 — Sticky Objectives.

10e rule: once a sticky_objective unit takes control of an objective for its
army, the objective remains controlled by that army after the unit moves off
or dies, until the opposing side wrests it back by controlling the objective
themselves.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.events import ObjectiveScored
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


class StickyObjectivesTests(unittest.TestCase):

    def _setup_battle(self):
        """Build a 2-army battle with a sticky claimant in A and a normal
        body in B. Position units manually onto the centre objective."""
        random.seed(0)
        a = Army("Alpha")
        a.add_unit(_profile("StickyClaimant", sticky_objective=True, oc=2))
        a.add_unit(_profile("AlphaFiller"))
        b = Army("Bravo")
        b.add_unit(_profile("BravoTrooper", oc=1))

        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()
        return battle, a, b

    def _objective_pos(self, battle):
        """Return the (x,y) of the first objective on this battle's map."""
        obj = battle.map.objectives[0]
        return (obj.x, obj.y)

    def test_sticky_unit_holds_objective_after_dying(self):
        """Sticky unit claims an objective then dies. Next round, with no
        side present on the objective, the sticky owner still scores VP."""
        battle, a, b = self._setup_battle()
        ox, oy = self._objective_pos(battle)

        # Round 1: sticky claimant stands on the objective alone.
        sticky = next(u for u in a.units if u.profile.name == "StickyClaimant")
        sticky.position = (ox, oy)
        # Make sure Bravo isn't accidentally on this objective.
        b.units[0].position = (ox + 50.0, oy + 50.0)
        # The other Alpha filler also far away.
        a.units[1].position = (ox - 50.0, oy - 50.0)

        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()
        self.assertGreater(battle._a_vp, 0,
            "Alpha's sticky unit should score VP on the contested objective.")
        a_vp_round1 = battle._a_vp
        # Sticky ownership should be flagged for objective index 0.
        self.assertEqual(battle._sticky_owner.get(0), a.name)

        # Round 2: sticky unit dies (and nobody else is near the objective).
        sticky.current_health = 0
        battle._score_objectives()
        # Alpha should still score on the objective because of sticky.
        self.assertGreater(battle._a_vp, a_vp_round1,
            "Sticky owner should keep scoring after the claimant dies.")

    def test_opposing_unit_flips_sticky_ownership(self):
        """A sticky unit holds an objective, then dies, then an opposing
        non-sticky unit moves onto it — control should transfer to Bravo."""
        battle, a, b = self._setup_battle()
        ox, oy = self._objective_pos(battle)
        sticky = next(u for u in a.units if u.profile.name == "StickyClaimant")

        # Round 1: Alpha claims the objective via sticky unit.
        sticky.position = (ox, oy)
        b.units[0].position = (ox + 50.0, oy + 50.0)
        a.units[1].position = (ox - 50.0, oy - 50.0)
        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()
        self.assertEqual(battle._sticky_owner.get(0), a.name)
        a_vp_after_r1 = battle._a_vp
        b_vp_after_r1 = battle._b_vp

        # Round 2: Alpha's sticky dies, Bravo takes the objective.
        sticky.current_health = 0
        b.units[0].position = (ox, oy)
        battle._score_objectives()
        # Bravo should have scored at least once now.
        self.assertGreater(battle._b_vp, b_vp_after_r1,
            "Bravo should score after wresting the objective from Alpha.")
        # Sticky owner cleared because Bravo took it.
        self.assertNotEqual(battle._sticky_owner.get(0), a.name,
            "Alpha's sticky ownership should be cleared once Bravo controls the objective.")

        # Round 3: Bravo leaves. With no sticky_objective unit, control
        # should NOT persist for Bravo — score should be uncontested.
        b.units[0].position = (ox + 50.0, oy + 50.0)
        prev_a_vp = battle._a_vp
        prev_b_vp = battle._b_vp
        battle._score_objectives()
        self.assertEqual(battle._a_vp, prev_a_vp,
            "Alpha shouldn't score — nobody is on the objective and sticky was cleared.")
        self.assertEqual(battle._b_vp, prev_b_vp,
            "Bravo lacks sticky_objective so control should not persist after they leave.")

    def _setup_battle_with_oc(self, a_sticky_oc: int, b_oc: int):
        """Variant of _setup_battle that lets the caller pin both sides' OC
        on the sticky claimant and the Bravo trooper. UnitProfile is a frozen
        dataclass, so we set OC at construction time rather than mutating."""
        random.seed(0)
        a = Army("Alpha")
        a.add_unit(_profile("StickyClaimant", sticky_objective=True, oc=a_sticky_oc))
        a.add_unit(_profile("AlphaFiller"))
        b = Army("Bravo")
        b.add_unit(_profile("BravoTrooper", oc=b_oc))

        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()
        return battle, a, b

    def test_tied_oc_does_not_grant_sticky_ownership(self):
        """10e core rules: 'The player with the greater Level of Control over
        the objective marker controls it.' Strictly greater — tied OC yields
        no controller and therefore cannot promote sticky ownership.
        https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Mission-Objectives
        """
        battle, a, b = self._setup_battle_with_oc(a_sticky_oc=2, b_oc=2)
        ox, oy = self._objective_pos(battle)

        sticky = next(u for u in a.units if u.profile.name == "StickyClaimant")
        sticky.position = (ox, oy)
        b.units[0].position = (ox, oy)
        a.units[1].position = (ox - 50.0, oy - 50.0)

        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()
        self.assertEqual(battle._a_vp, 0,
            "Tied OC should not award VP to Alpha.")
        self.assertEqual(battle._b_vp, 0,
            "Tied OC should not award VP to Bravo.")
        self.assertIsNone(battle._sticky_owner.get(0),
            "Tied OC must NOT promote sticky ownership per 10e 'greater Level of Control' wording.")

    def test_strictly_greater_oc_grants_sticky_ownership(self):
        """Alpha with strictly more OC (3 vs 2) controls and promotes sticky."""
        battle, a, b = self._setup_battle_with_oc(a_sticky_oc=3, b_oc=2)
        ox, oy = self._objective_pos(battle)

        sticky = next(u for u in a.units if u.profile.name == "StickyClaimant")
        sticky.position = (ox, oy)
        b.units[0].position = (ox, oy)
        a.units[1].position = (ox - 50.0, oy - 50.0)

        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()
        self.assertGreater(battle._a_vp, 0,
            "Alpha (OC 3 vs 2) strictly out-controls and should score.")
        self.assertEqual(battle._sticky_owner.get(0), a.name,
            "Strictly greater OC must register sticky ownership.")

    def test_sticky_owner_with_zero_oc_loses_to_any_opposing_oc(self):
        """Sticky owner with 0 OC on the marker; opponent has 1 OC on it.
        Per strict-greater rule, opponent controls — sticky promotion does
        NOT preserve the absent owner this scoring tick."""
        battle, a, b = self._setup_battle()
        ox, oy = self._objective_pos(battle)
        sticky = next(u for u in a.units if u.profile.name == "StickyClaimant")

        # Round 1: Alpha claims via sticky.
        sticky.position = (ox, oy)
        b.units[0].position = (ox + 50.0, oy + 50.0)
        a.units[1].position = (ox - 50.0, oy - 50.0)
        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()
        self.assertEqual(battle._sticky_owner.get(0), a.name)

        # Round 2: Alpha's sticky leaves; Bravo arrives with 1 OC.
        sticky.position = (ox + 80.0, oy + 80.0)
        b.units[0].position = (ox, oy)
        a_vp_before = battle._a_vp
        b_vp_before = battle._b_vp
        battle._score_objectives()
        self.assertGreater(battle._b_vp, b_vp_before,
            "Bravo with strictly greater OC (1 vs 0) should score.")
        self.assertEqual(battle._a_vp, a_vp_before,
            "Alpha (0 OC, even with prior sticky) should NOT score against opposing OC>0.")
        self.assertNotEqual(battle._sticky_owner.get(0), a.name,
            "Alpha's sticky ownership must be cleared once Bravo strictly out-controls.")

    def test_non_sticky_unit_does_not_register_sticky_ownership(self):
        """A non-sticky unit standing on an objective scores normally but
        does NOT set the sticky_owner flag — leaving means losing it."""
        battle, a, b = self._setup_battle()
        ox, oy = self._objective_pos(battle)

        # Use Alpha's non-sticky filler unit instead of the sticky claimant.
        filler = next(u for u in a.units if u.profile.name == "AlphaFiller")
        filler.position = (ox, oy)
        # Sticky claimant is dead / removed from contention.
        sticky = next(u for u in a.units if u.profile.name == "StickyClaimant")
        sticky.current_health = 0
        b.units[0].position = (ox + 50.0, oy + 50.0)

        battle._a_vp = 0
        battle._b_vp = 0
        battle._score_objectives()
        self.assertGreater(battle._a_vp, 0,
            "Alpha's non-sticky filler should score VP from standing on the objective.")
        # Sticky owner should NOT be set because no sticky unit was present.
        self.assertIsNone(battle._sticky_owner.get(0),
            "Sticky ownership shouldn't be claimed by a non-sticky unit.")


if __name__ == "__main__":
    unittest.main()
