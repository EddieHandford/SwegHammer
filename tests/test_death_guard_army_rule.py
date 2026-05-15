"""Tests for the Death Guard army rule Disgustingly Resilient (#144).

Disgustingly Resilient (10e Death Guard army rule, Wahapedia):
    "Each time a model in this unit would lose a wound, this ability has
     Feel No Pain 5+ against that lost wound."

Faction-wide, always-on, for every DEATH GUARD model. Implemented as a
faction-gated runtime check in `Unit.receive_damage`: when the defender's
profile.faction == "Death Guard", `effective_fnp` is lowered to
min(effective_fnp, 5). Composes with the existing transient Plague Company
stratagem (`transient_minus_one_damage_taken`) and with profile.fnp from
the overrides (Plague Marines already carry fnp=5 — the min keeps them at
5+, not 4+).

Cited as `simulator.disgustingly_resilient`.
"""

from __future__ import annotations

import random
import unittest

from code.units import Unit, UnitProfile


def _dg_terminator_profile() -> UnitProfile:
    """Death Guard Terminator-ish profile (T6 / W3 / Sv2+ / fnp default 7).
    The army rule should floor effective FNP at 5 on every receive_damage
    call. Faction tag is the gate."""
    return UnitProfile(
        name="DG Terminator",
        health=3, damage=1, hit_probability=2 / 3,
        ap=0, save=2, strength=4, toughness=6,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=8,
        faction="Death Guard",
        unit_keywords=("INFANTRY", "TERMINATOR"),
    )


def _astartes_terminator_profile() -> UnitProfile:
    """Identical stats but faction='Adeptus Astartes' — no army-rule FNP.
    Used as the control."""
    return UnitProfile(
        name="Astartes Terminator",
        health=3, damage=1, hit_probability=2 / 3,
        ap=0, save=2, strength=4, toughness=6,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=8,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY", "TERMINATOR"),
    )


def _plague_marine_profile(fnp: int = 5) -> UnitProfile:
    """Plague Marines already carry profile.fnp=5 via overrides (#142).
    The army rule should NOT double-up to 4+."""
    return UnitProfile(
        name="Plague Marine",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Death Guard",
        fnp=fnp,
        unit_keywords=("INFANTRY",),
    )


class DisgustinglyResilientArmyRuleTests(unittest.TestCase):
    """Run thousands of receive_damage trials to compare DG vs non-DG.
    Difference must be ~16.6% (one in six wounds prevented by FNP 5+)."""

    def test_dg_terminator_has_effective_fnp_5(self):
        """A DG Terminator (profile.fnp=7) takes ~16.6% less damage than
        an otherwise identical Astartes Terminator. We apply N wounds via
        receive_damage and compare totals."""
        N_TRIALS = 5000

        random.seed(2026)
        dg = Unit(_dg_terminator_profile())
        dg.current_health = N_TRIALS + 100.0   # avoid running out of HP
        for _ in range(N_TRIALS):
            dg.receive_damage(1.0)
        dg_taken = (N_TRIALS + 100.0) - dg.current_health

        random.seed(2026)
        ast = Unit(_astartes_terminator_profile())
        ast.current_health = N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            ast.receive_damage(1.0)
        ast_taken = (N_TRIALS + 100.0) - ast.current_health

        # Control absorbs all N. DG absorbs ~4/6 N (FNP 5+ ignores 2/6 of
        # wounds — succeed on 5+, two faces out of six). Reduction ~33%.
        self.assertEqual(int(ast_taken), N_TRIALS,
                         "Non-DG control should have no FNP — takes every wound.")
        reduction = (ast_taken - dg_taken) / ast_taken
        self.assertAlmostEqual(
            reduction, 2 / 6, delta=0.03,
            msg=f"DG should ignore ~2/6 of wounds via FNP 5+; got {reduction:.3f}",
        )

    def test_plague_marine_already_fnp_5_doesnt_double_up(self):
        """Plague Marines have profile.fnp=5 from overrides. The army rule
        must compose by min(5, 5) = 5, not stack to 4+. Verify the average
        absorbed fraction matches FNP 5+, not FNP 4+."""
        N_TRIALS = 5000

        random.seed(2026)
        pm = Unit(_plague_marine_profile(fnp=5))
        pm.current_health = N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            pm.receive_damage(1.0)
        pm_taken = (N_TRIALS + 100.0) - pm.current_health

        reduction = (N_TRIALS - pm_taken) / N_TRIALS
        # FNP 5+: 2/6 = 33.3% absorbed. FNP 4+ would be 3/6 = 50%. Tight
        # delta so we'd catch a stacked-to-4+ bug.
        self.assertAlmostEqual(
            reduction, 2 / 6, delta=0.03,
            msg=f"PM FNP 5+ should absorb ~33%, not stack to FNP 4+/50%; got {reduction:.3f}",
        )

    def test_dg_stratagem_4plus_still_works(self):
        """The Plague Company stratagem `Disgustingly Resilient` (separate
        from the army rule) sets transient_minus_one_damage_taken for a
        round → per-shot damage reduced by 1 (floor 1). Verify that path
        still fires on top of the army rule.

        Note: the existing stratagem is NOT FNP 4+; the codex 10e stratagem
        is `-1 damage taken` (see code/detachments.py:282). We assert the
        damage-floor path still runs and stacks atop the army-rule FNP 5+.
        """
        N_TRIALS = 3000

        # Baseline: DG Terminator under just the army rule, taking 2 dmg shots.
        random.seed(2026)
        dg = Unit(_dg_terminator_profile())
        dg.current_health = 10 * N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            dg.receive_damage(2.0)
        dg_only_taken = (10 * N_TRIALS + 100.0) - dg.current_health

        # Stratagem on top: 2-dmg shots become 1-dmg before the FNP roll.
        random.seed(2026)
        dg_stratted = Unit(_dg_terminator_profile())
        dg_stratted.transient_minus_one_damage_taken = True
        dg_stratted.current_health = 10 * N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            dg_stratted.receive_damage(2.0)
        stratted_taken = (10 * N_TRIALS + 100.0) - dg_stratted.current_health

        # Stratagem path must produce STRICTLY less damage taken.
        self.assertLess(
            stratted_taken, dg_only_taken,
            f"Stratagem should reduce damage taken further (got "
            f"stratted={stratted_taken:.1f}, baseline={dg_only_taken:.1f})",
        )
        # Ballpark: baseline ~5/6 * 2 * N = ~1.67N. Stratagem path ~5/6 * 1 * N
        # = ~0.83N. The ratio should be ~0.5 (give or take rng).
        ratio = stratted_taken / dg_only_taken
        self.assertAlmostEqual(
            ratio, 0.5, delta=0.05,
            msg=f"Stratagem should roughly halve damage on 2-dmg shots; ratio={ratio:.3f}",
        )

    def test_non_dg_unaffected(self):
        """A vanilla Astartes Marine (no DG faction, profile.fnp default 7)
        takes every wound — no FNP roll fires."""
        N_TRIALS = 2000
        random.seed(2026)
        ast = Unit(_astartes_terminator_profile())
        ast.current_health = N_TRIALS + 100.0
        for _ in range(N_TRIALS):
            ast.receive_damage(1.0)
        ast_taken = (N_TRIALS + 100.0) - ast.current_health
        self.assertEqual(
            int(ast_taken), N_TRIALS,
            f"Non-DG unit must take every wound — got {ast_taken} of {N_TRIALS}",
        )


if __name__ == "__main__":
    unittest.main()
