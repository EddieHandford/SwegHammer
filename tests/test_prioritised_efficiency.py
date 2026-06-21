"""Tests for the Leagues of Votann "Prioritised Efficiency" army rule
(current 10e codex), env-gated SWEG_VOTANN_PRIORITISED_EFFICIENCY (default OFF).

BSData v10.6.0 (Leagues of Votann.cat.gz, sharedRules rule id
351a-a702-9080-7f08), Hostile Acquisition clause, verbatim:
  "Each time a model in this unit makes an attack that targets an enemy unit
   within range of one or more objective markers, add 1 to the Hit roll."

One simulator gate reads this rule in code.units.Unit.attack: a Leagues of
Votann attacker (Army.is_votann_army) gets +1 to the Hit roll when the target
is within range of an objective marker (`target.on_objective`). It applies to
BOTH ranged and melee attacks, composes with other +1-to-hit sources through
the 10e +/-1 Hit-modifier cap, and only fires while the env gate is ON.

The rule is the real printed replacement for the retired Eye of the Ancestors
mechanic. It is deliberately conditional on the target being near an objective
marker (not a blanket army-wide +1), which is the discriminator that keeps it
moderate. APPROXIMATION (documented in data/rule_citations.d/votann.json): only
the Hostile Acquisition state is modelled — not the Yield-Point economy, the
Fortify Takeover switch, or the Advance-and-Charge re-roll.

These tests verify the +1-to-Hit fires only under the env gate + the Votann
faction gate + the rule's own near-objective condition, and that with the gate
OFF the behaviour is the un-buffed baseline.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def _votann_infantry() -> UnitProfile:
    """A LEAGUES OF VOTANN shooter. hit_probability 0.5 (hit_target 4+) so the
    +1-to-Hit visibly closes a bracket (4+ -> 3+). High attack count so the
    Monte-Carlo damage mean is tight."""
    return UnitProfile(
        name="Hearthkyn Warriors", faction="Leagues of Votann",
        health=10, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=20, weapon_damage_per_shot=1.0,
        melee_attacks=20, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4,
        range_inches=24,
        unit_keywords=("LEAGUES OF VOTANN", "INFANTRY"),
        points_override=90.0,
    )


def _non_votann_infantry() -> UnitProfile:
    """An identical-statline non-VOTANN attacker (faction gate control)."""
    return UnitProfile(
        name="Guardsman Squad", faction="Astra Militarum",
        health=10, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=20, weapon_damage_per_shot=1.0,
        melee_attacks=20, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4,
        range_inches=24,
        unit_keywords=("ASTRA MILITARUM", "INFANTRY"),
        points_override=90.0,
    )


def _soft_target() -> UnitProfile:
    """A high-wound soft target so a single attack() call never wipes it —
    keeps the damage mean an unbiased estimate of the hit-rate change."""
    return UnitProfile(
        name="Cultist Mob", faction="Chaos Space Marines",
        health=200, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        points_override=60.0,
    )


def _mean_attack_damage(attacker_profile, on_objective, mode="ranged",
                        n=4000, seed=20260620):
    """Monte-Carlo mean of a single attack() call against a fresh soft target.

    Returns the average expected damage so the test can compare the +1-to-Hit
    on/off cases. The target is reset to full health each trial so a stray
    wipe never truncates the shot count."""
    a = Army("Attacker")
    a.add_unit(attacker_profile)
    b = Army("Defender")
    b.add_unit(_soft_target())
    atk = a.units[0]
    tgt = b.units[0]
    tgt.on_objective = on_objective
    random.seed(seed)
    total = 0.0
    for _ in range(n):
        total += atk.attack(tgt, mode=mode)
        tgt.current_health = tgt.profile.health
    return total / n


# ---------------------------------------------------------------------------
# Gate ON — +1 to Hit vs targets near objectives (Hostile Acquisition)
# ---------------------------------------------------------------------------

class PrioritisedEfficiencyGateOnTests(unittest.TestCase):

    def setUp(self):
        os.environ["SWEG_VOTANN_PRIORITISED_EFFICIENCY"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_VOTANN_PRIORITISED_EFFICIENCY", None)

    def test_votann_gets_plus_one_hit_vs_on_objective_target(self):
        on = _mean_attack_damage(_votann_infantry(), on_objective=True)
        off = _mean_attack_damage(_votann_infantry(), on_objective=False)
        # +1 to hit raises 4+ to 3+ (0.5 -> ~0.667 hit rate), a clear ~33% lift.
        self.assertGreater(on, off * 1.2)

    def test_no_bonus_when_target_not_on_objective(self):
        # Votann attacker, gate ON, but the target is NOT near an objective:
        # the near-objective condition fails, so the hit rate stays un-buffed.
        off = _mean_attack_damage(_votann_infantry(), on_objective=False)
        baseline = _mean_attack_damage(_non_votann_infantry(), on_objective=True)
        # Off-objective Votann and on-objective non-Votann must both land at the
        # un-buffed hit rate (within Monte-Carlo noise).
        self.assertAlmostEqual(off, baseline, delta=0.25)

    def test_non_votann_army_gets_no_bonus(self):
        # A non-VOTANN attacker, even vs an on-objective target, gets nothing
        # (faction gate).
        on = _mean_attack_damage(_non_votann_infantry(), on_objective=True)
        off = _mean_attack_damage(_non_votann_infantry(), on_objective=False)
        self.assertAlmostEqual(on, off, delta=0.25)

    def test_bonus_applies_in_melee_too(self):
        # The rule says "makes an attack" — melee benefits as well as ranged.
        on = _mean_attack_damage(_votann_infantry(), on_objective=True, mode="melee")
        off = _mean_attack_damage(_votann_infantry(), on_objective=False, mode="melee")
        self.assertGreater(on, off * 1.2)


# ---------------------------------------------------------------------------
# Gate OFF — byte-identical to the pre-change baseline (no buff at all)
# ---------------------------------------------------------------------------

class PrioritisedEfficiencyGateOffTests(unittest.TestCase):

    def setUp(self):
        # Ensure the gate is unambiguously OFF (the default), regardless of any
        # leftover environment state.
        os.environ.pop("SWEG_VOTANN_PRIORITISED_EFFICIENCY", None)

    def test_no_bonus_when_gate_off_even_on_objective(self):
        # Gate OFF: a Votann attacker vs an on-objective target gets NO bonus —
        # identical hit rate to the off-objective case.
        on = _mean_attack_damage(_votann_infantry(), on_objective=True)
        off = _mean_attack_damage(_votann_infantry(), on_objective=False)
        self.assertAlmostEqual(on, off, delta=0.25)

    def test_gate_off_matches_on_objective_gate_on_off_target(self):
        # Cross-check: gate-OFF on-objective Votann == gate-ON off-objective
        # Votann (both are the un-buffed baseline; the condition / gate that
        # would grant +1 is not satisfied in either case).
        off_gate_on_obj = _mean_attack_damage(_votann_infantry(), on_objective=True)
        os.environ["SWEG_VOTANN_PRIORITISED_EFFICIENCY"] = "1"
        try:
            on_gate_off_obj = _mean_attack_damage(
                _votann_infantry(), on_objective=False,
            )
        finally:
            os.environ.pop("SWEG_VOTANN_PRIORITISED_EFFICIENCY", None)
        self.assertAlmostEqual(off_gate_on_obj, on_gate_off_obj, delta=0.25)


if __name__ == "__main__":
    unittest.main()
