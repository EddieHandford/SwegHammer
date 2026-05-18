"""Tests that pin the absence of any fabricated army-wide Death Guard FNP 5+.

The previous test file in this slot asserted a codex-level "every DEATH
GUARD model has FNP 5+" rule. That rule does NOT exist in the 10e codex.
Per Wahapedia (https://wahapedia.ru/wh40k10ed/factions/death-guard/) the
DG army rule is Nurgle's Gift / Contagions of Nurgle (a -1 T / -1 Ld /
-1 to hit aura). Disgustingly Resilient in 10e is ONLY the 2 CP Virulent
Vectorium stratagem (-1 damage per allocated attack, INFANTRY/CHARACTER
scope), wired via `transient_minus_one_damage_taken` on Unit.receive_damage.

Sources:
- Goonhammer "Hammer of Math: New Disgustingly Resilient":
  https://www.goonhammer.com/hammer-of-math-new-disgustingly-resilient/
  ("Disgustingly Resilient is gone as an army ability in 10th edition.
   ... No omnipresent -1D, no FNP.")
- Goonhammer 10e Death Guard codex review:
  https://www.goonhammer.com/goonhammer-reviews-codex-death-guard-10th-edition/

Per-datasheet innate FNP (Plague Marines fnp=5, Mortarion fnp=5,
Deathshroud fnp=4, etc.) still lives on profile.fnp via overrides.json /
parsed.json and is honoured by the existing `min(self.profile.fnp, ...)`
line in Unit.receive_damage. These tests pin that:

  1. A DG datasheet with profile.fnp default (7) takes EVERY wound — no
     phantom army-wide FNP 5+ kicks in.
  2. A Plague Marine (profile.fnp=5 from overrides) still gets its FNP 5+
     via the datasheet path.
  3. The Virulent Vectorium 2 CP stratagem path
     (transient_minus_one_damage_taken) still bites.
"""

from __future__ import annotations

import random
import unittest

from code.units import Unit, UnitProfile


def _dg_vehicle_profile() -> UnitProfile:
    """Death Guard VEHICLE-ish profile (no datasheet FNP). Used to be granted
    a fictional army-wide FNP 5+ pre-iter-15. Post-iter-15 it must take
    every wound it's dealt."""
    return UnitProfile(
        name="DG Plagueburst Crawler",
        health=12, damage=1, hit_probability=2 / 3,
        ap=0, save=2, strength=4, toughness=11,
        attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Death Guard",
        unit_keywords=("VEHICLE",),
    )


def _astartes_marine_profile() -> UnitProfile:
    """Control: identical stats but faction='Adeptus Astartes'."""
    return UnitProfile(
        name="Astartes Marine",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
    )


def _plague_marine_profile() -> UnitProfile:
    """Plague Marines carry profile.fnp=5 via overrides.json. That datasheet
    FNP still fires through the existing `min(self.profile.fnp, ...)` path —
    nothing to do with the deleted phantom army-wide rule."""
    return UnitProfile(
        name="Plague Marine",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=5, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Death Guard",
        fnp=5,
        unit_keywords=("INFANTRY",),
    )


class DGNoArmyWideFNPTests(unittest.TestCase):
    """Pin the absence of the deleted phantom army-wide FNP 5+."""

    def test_dg_datasheet_without_innate_fnp_has_no_phantom_fnp(self):
        """A DG datasheet with profile.fnp default (7) must take EVERY
        wound. Pre-iter-15 the simulator was granting it phantom FNP 5+ via
        a faction gate; iter 15 deleted that fabrication."""
        N_TRIALS = 5000
        random.seed(2026)
        dg = Unit(_dg_vehicle_profile())
        dg.current_health = N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            dg.receive_damage(1.0)
        dg_taken = (N_TRIALS + 100.0) - dg.current_health
        self.assertEqual(
            int(dg_taken), N_TRIALS,
            f"DG VEHICLE (profile.fnp=7) must take every wound. The "
            f"deleted phantom army-wide FNP 5+ would have absorbed "
            f"~33%. Got {dg_taken} of {N_TRIALS}.",
        )

    def test_dg_vehicle_matches_astartes_control(self):
        """A DG VEHICLE and an Astartes Marine taking identical hits should
        take statistically identical damage — there is no longer any
        faction-side FNP boost for DG."""
        N_TRIALS = 5000

        random.seed(2026)
        dg = Unit(_dg_vehicle_profile())
        dg.current_health = N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            dg.receive_damage(1.0)
        dg_taken = (N_TRIALS + 100.0) - dg.current_health

        random.seed(2026)
        ast = Unit(_astartes_marine_profile())
        ast.current_health = N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            ast.receive_damage(1.0)
        ast_taken = (N_TRIALS + 100.0) - ast.current_health

        self.assertEqual(
            int(dg_taken), int(ast_taken),
            f"Faction tag alone must not grant FNP. DG took {dg_taken}, "
            f"Astartes took {ast_taken}.",
        )


class DGDatasheetFNPStillBitesTests(unittest.TestCase):
    """Plague Marines / Deathshroud / Mortarion still have datasheet FNP
    via overrides.json — those values live on profile.fnp and fire through
    the unchanged `min(self.profile.fnp, bonus_fnp)` path."""

    def test_plague_marine_datasheet_fnp_5_still_fires(self):
        N_TRIALS = 5000
        random.seed(2026)
        pm = Unit(_plague_marine_profile())
        pm.current_health = N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            pm.receive_damage(1.0)
        pm_taken = (N_TRIALS + 100.0) - pm.current_health
        reduction = (N_TRIALS - pm_taken) / N_TRIALS
        # FNP 5+: 2/6 = 33.3% absorbed. Tolerance keeps the assert tight
        # enough to catch a regression that reverted to no-FNP or
        # double-applied to 4+ (50%).
        self.assertAlmostEqual(
            reduction, 2 / 6, delta=0.03,
            msg=f"Plague Marine profile.fnp=5 should absorb ~33%; "
                f"got {reduction:.3f}",
        )


class DGVirulentVectoriumStratagemStillBitesTests(unittest.TestCase):
    """The 2 CP Disgustingly Resilient stratagem (Virulent Vectorium) is
    NOT the same as the deleted army rule. It still wires through
    `transient_minus_one_damage_taken` per the existing dispatcher."""

    def test_strat_reduces_damage_by_one_floor_1(self):
        """When the flag is set, each per-call damage value drops by 1
        (floor 1). The flag is applied per round by
        Battle._try_disgustingly_resilient on an INFANTRY/CHARACTER DG unit."""
        N_TRIALS = 3000

        # Baseline: vehicle taking 2-dmg shots, no stratagem.
        random.seed(2026)
        dg = Unit(_dg_vehicle_profile())
        dg.current_health = 10 * N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            dg.receive_damage(2.0)
        baseline_taken = (10 * N_TRIALS + 100.0) - dg.current_health

        # Stratagem on: 2-dmg shots become 1-dmg pre-FNP.
        random.seed(2026)
        dg_stratted = Unit(_dg_vehicle_profile())
        dg_stratted.transient_minus_one_damage_taken = True
        dg_stratted.current_health = 10 * N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            dg_stratted.receive_damage(2.0)
        stratted_taken = (10 * N_TRIALS + 100.0) - dg_stratted.current_health

        self.assertLess(
            stratted_taken, baseline_taken,
            f"Stratagem should reduce damage taken. baseline={baseline_taken:.1f}, "
            f"stratted={stratted_taken:.1f}",
        )
        # 2 -> 1 dmg per shot is exactly halved (no FNP on this vehicle).
        ratio = stratted_taken / baseline_taken
        self.assertAlmostEqual(
            ratio, 0.5, delta=0.05,
            msg=f"Stratagem should halve damage on 2-dmg shots vs DG VEHICLE; "
                f"ratio={ratio:.3f}",
        )


if __name__ == "__main__":
    unittest.main()
