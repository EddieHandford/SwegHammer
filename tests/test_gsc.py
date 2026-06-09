"""Tests for the Genestealer Cults army rule Cult Ambush (#120).

Cult Ambush (10e GSC army rule, Wahapedia):
    "At the start of the first battle round, after both sides have deployed,
     you can redeploy any number of units from your army. When doing so,
     each of those units can be set up anywhere on the battlefield that is
     more than 9\" horizontally away from all enemy models."

SwegHammer model:
    * Every GSC unit is routed into the simulator's `_reserves` bucket at
      deployment time (regardless of `deep_strike`) and tagged
      `cult_ambush_pending=True`.
    * `Battle._arrive_from_reserves` is now called on Round 1 too; ambush
      units land deterministically that round via the same threat/objective
      scoring landing-point picker the Deep Strike path uses.
    * Each arrival emits a UnitDeepStrike event (we reuse the existing event
      type rather than minting a UnitCultAmbushed parallel — the renderer
      already understands it).
    * Non-GSC armies are unaffected: their units still deploy at the line,
      and any deep-strikers in those armies still wait until Round 2.

Cited as `simulator.cult_ambush`.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.events import EventLog, UnitDeepStrike
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile builders
# ---------------------------------------------------------------------------

def _gsc_profile(name: str = "Neophyte Hybrid", **overrides) -> UnitProfile:
    """A minimal GSC unit. Health 1 / S4 / T3 / 4+ save so it can credibly
    represent an Acolyte or Neophyte stand-in for behaviour tests."""
    base = dict(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7,
        faction="Genestealer Cults",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )
    base.update(overrides)
    return UnitProfile(**base)


def _guard_profile(name: str = "Guardsman", **overrides) -> UnitProfile:
    """A non-GSC stand-in (Astra Militarum). Used as the opposing force and
    as the control group for "non-GSC armies deploy normally"."""
    base = dict(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Astra Militarum",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
    )
    base.update(overrides)
    return UnitProfile(**base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class CultAmbushDeploymentTests(unittest.TestCase):
    """Verify GSC units are pulled out of the deployment-line path and held
    in reserves, flagged ambush_pending, before Round 1 begins.

    These tests pin SWEG_DEPLOY_AI=0 (gate OFF) so the Reserves cap is not
    enforced. The purpose is to isolate the Cult Ambush mechanic itself
    (every GSC unit goes to reserves with cult_ambush_pending=True) from the
    AI piloting choice of which units to reserve. The cap behaviour is tested
    separately in tests/test_deploy_ai.py.
    """

    def setUp(self):
        self._prev_deploy_ai = os.environ.get("SWEG_DEPLOY_AI")
        os.environ["SWEG_DEPLOY_AI"] = "0"

    def tearDown(self):
        if self._prev_deploy_ai is None:
            os.environ.pop("SWEG_DEPLOY_AI", None)
        else:
            os.environ["SWEG_DEPLOY_AI"] = self._prev_deploy_ai

    def test_gsc_units_start_off_table(self):
        """Every GSC unit should be in reserves with cult_ambush_pending=True
        after deployment, NOT on the deployment line."""
        random.seed(0)
        cult = Army("Cult")
        cult.add_unit(_gsc_profile(name="Magus"))
        cult.add_unit(_gsc_profile(name="Acolyte Hybrid"))
        cult.add_unit(_gsc_profile(name="Neophyte Hybrid"))
        guard = Army("Guard")
        guard.add_unit(_guard_profile(name="Sgt"))

        battle = Battle(cult, guard)
        battle._assign_uids()
        battle._deploy_armies()

        # Cult side has nothing on-board — everything is in reserves.
        self.assertEqual(len(cult.units), 0,
            f"GSC army should deploy nothing at the line; got "
            f"{[u.profile.name for u in cult.units]}")
        reserves = battle._reserves[cult.name]
        self.assertEqual(len(reserves), 3)
        for u in reserves:
            self.assertTrue(u.cult_ambush_pending,
                f"{u.profile.name} should be flagged cult_ambush_pending=True "
                f"in reserves but isn't")

    def test_non_gsc_units_unaffected(self):
        """An Astra Militarum army should deploy at the line, NOT via the
        ambush path. cult_ambush_pending should remain False."""
        random.seed(0)
        guard = Army("Guard")
        guard.add_unit(_guard_profile(name="Trooper A"))
        guard.add_unit(_guard_profile(name="Trooper B"))
        enemy = Army("Enemy")
        enemy.add_unit(_guard_profile(name="EnemyA"))

        battle = Battle(guard, enemy)
        battle._assign_uids()
        battle._deploy_armies()

        # All Guard units on-board, none in reserves, ambush flag untouched.
        self.assertEqual(len(guard.units), 2)
        self.assertEqual(len(battle._reserves[guard.name]), 0)
        for u in guard.units:
            self.assertFalse(u.cult_ambush_pending)

    def test_gsc_units_arrive_round_1(self):
        """After one round of play, every GSC unit must be on the table and
        positioned > 9\" from every enemy model."""
        random.seed(0)
        cult = Army("Cult")
        # Enough variety that arrival has multiple candidates to score.
        cult.add_unit(_gsc_profile(name="Magus"))
        cult.add_unit(_gsc_profile(name="Acolyte Hybrid"))
        cult.add_unit(_gsc_profile(name="Neophyte Hybrid"))
        cult.add_unit(_gsc_profile(name="Aberrant"))
        guard = Army("Guard")
        guard.add_unit(_guard_profile(name="Sgt"))
        guard.add_unit(_guard_profile(name="Trooper"))

        battle = Battle(cult, guard)
        battle._assign_uids()
        battle._deploy_armies()
        # Drive just the ambush arrival, not a full round (avoids attrition
        # and stratagem side effects polluting the assertion).
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=1)

        # All four GSC units are now on the board.
        gsc_names = {u.profile.name for u in cult.units}
        self.assertEqual(
            gsc_names,
            {"Magus", "Acolyte Hybrid", "Neophyte Hybrid", "Aberrant"},
        )
        self.assertEqual(len(battle._reserves[cult.name]), 0)

        # Each landing site is > 9" from every Guard model.
        for u in cult.units:
            for enemy in guard.units:
                dx = u.position[0] - enemy.position[0]
                dy = u.position[1] - enemy.position[1]
                d = (dx * dx + dy * dy) ** 0.5
                self.assertGreater(d, 9.0,
                    f"{u.profile.name} ambushed at {u.position} but is only "
                    f"{d:.2f}\" from {enemy.profile.name} at {enemy.position}")

        # The ambush flag must be cleared once the unit lands.
        for u in cult.units:
            self.assertFalse(u.cult_ambush_pending)

    def test_cult_ambush_event_emitted(self):
        """Each GSC unit emits a UnitDeepStrike event during its Round 1
        ambush placement (we reuse the existing event type)."""
        random.seed(0)
        cult = Army("Cult")
        cult.add_unit(_gsc_profile(name="Magus"))
        cult.add_unit(_gsc_profile(name="Acolyte Hybrid"))
        guard = Army("Guard")
        guard.add_unit(_guard_profile(name="Sgt"))

        log = EventLog()
        battle = Battle(cult, guard, subscribers=[log])
        battle._assign_uids()
        battle._deploy_armies()
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=1)

        ds_events = [e for e in log.events if isinstance(e, UnitDeepStrike)]
        self.assertEqual(len(ds_events), 2)
        uids = {e.unit_uid for e in ds_events}
        self.assertEqual(uids, {u.uid for u in cult.units})

    def test_deep_striker_in_non_gsc_army_still_waits_for_round_2(self):
        """Regression: the Round 1 arrival path must NOT scoop up regular
        Deep Strike units in a non-GSC army. They wait for Round 2."""
        random.seed(0)
        a = Army("Alpha")
        a.add_unit(_guard_profile(name="DropTrooper", deep_strike=True))
        a.add_unit(_guard_profile(name="GroundPounder"))
        b = Army("Bravo")
        b.add_unit(_guard_profile(name="Defender"))

        battle = Battle(a, b)
        battle._assign_uids()
        battle._deploy_armies()

        # DropTrooper is in reserves but NOT ambush-flagged.
        self.assertEqual(
            {u.profile.name for u in battle._reserves[a.name]},
            {"DropTrooper"},
        )
        self.assertFalse(battle._reserves[a.name][0].cult_ambush_pending)

        # Round 1 arrival must leave the deep-striker in reserves.
        battle._fresh_arrivals = set()
        battle._arrive_from_reserves(round_num=1)
        self.assertEqual(len(battle._reserves[a.name]), 1)
        self.assertEqual(
            battle._reserves[a.name][0].profile.name, "DropTrooper",
        )

    def test_battle_runs_endtoend_with_gsc(self):
        """Full simulation with a GSC army doesn't crash and produces a
        winner. Smoke-tests the round-loop integration."""
        random.seed(0)
        cult = Army("Cult")
        for nm in ("Magus", "Acolyte A", "Acolyte B", "Neophyte A",
                   "Neophyte B"):
            cult.add_unit(_gsc_profile(name=nm))
        guard = Army("Guard")
        for nm in ("Sgt", "Tpr A", "Tpr B"):
            guard.add_unit(_guard_profile(name=nm))

        battle = Battle(cult, guard)
        result = battle.run()
        # Must produce one of the three legal winner values — no crash.
        self.assertIn(result.winner, {cult.name, guard.name, None})


if __name__ == "__main__":
    unittest.main()
