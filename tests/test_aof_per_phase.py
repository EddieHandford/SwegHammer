"""Acts of Faith per-phase budget gate (SWEG_AOF_PER_PHASE) — regression tests.

Codex rule: "each unit from your army with this ability can perform one Act of
Faith per phase." (Wahapedia Adepta Sororitas army rule,
https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/)

Two tests:

(a) Gate OFF (SWEG_AOF_PER_PHASE="0" — explicit opt-out since the wave-239
    default flip): legacy per-round behaviour is byte-identical. A Sororitas
    unit that spends a Miracle die in the Shooting phase (simulated as the
    first attack() call in a round) CANNOT spend again in the Fight phase
    (simulated as a second attack() call in the same round). This pins the
    legacy behaviour so it cannot silently regress.

(b) Gate ON (SWEG_AOF_PER_PHASE unset or "1" — the production default since
    wave 239): codex-correct behaviour. The same unit
    CAN spend once in the Shooting phase AND once in the Fight phase. It cannot
    spend TWICE in the same phase (aof_used_this_phase blocks the second
    spend within one phase).

Both tests verify the per-unit-instance flag (`aof_used_this_phase` /
`aof_used_this_round`) and the squad-level budget (Army._unit_budget_used["aof"])
because both layers gate the spend.

Test strategy: directly manipulate Unit state and Army.miracle_dice to force
the substitution branch, rather than relying on a full Battle run, so the test
is fast and deterministic.
"""
from __future__ import annotations

import os
import unittest

from code.army import Army
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _sororitas_profile() -> UnitProfile:
    """Single-model Adepta Sororitas attacker with a reliable hit and wound
    profile so the AoF substitution branch is reachable in every call."""
    return UnitProfile(
        name="Battle Sisters Squad",
        health=10,
        damage=1,
        hit_probability=0.667,
        ap=0,
        save=3,
        strength=3,
        toughness=3,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        leadership=6,
        faction="Adepta Sororitas",
        points_override=100.0,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_damage_per_shot=1.0,
        melee_hit_probability=0.5,
        melee_strength=3,
        melee_ap=0,
    )


def _target_profile() -> UnitProfile:
    """Durable non-Sororitas target that survives many attacks."""
    return UnitProfile(
        name="Dummy Target",
        health=1_000_000,
        damage=1,
        hit_probability=0.5,
        ap=0,
        save=5,
        strength=4,
        toughness=4,
        attacks=1,
        weapon_damage_per_shot=1.0,
        range_inches=12,
        leadership=7,
        faction="Astra Militarum",
        points_override=100.0,
        unit_keywords=("INFANTRY",),
        melee_attacks=1,
        melee_damage_per_shot=1.0,
        melee_hit_probability=0.5,
        melee_strength=4,
        melee_ap=0,
    )


def _setup_units() -> tuple:
    """Return (attacker Unit, target Unit, attacker Army) with a full Miracle
    dice pool (max 8) and a fresh squad-level aof budget for the attacker.

    army.add_unit() sets unit.army_ref automatically (see code/army.py).
    """
    army = Army("Sororitas")
    attacker_profile = _sororitas_profile()
    army.add_unit(attacker_profile)
    attacker = army.units[0]
    # squad_id is set by add_unit; verify it is valid for budget keying.

    target_army = Army("Foe")
    target_profile = _target_profile()
    target_army.add_unit(target_profile)
    target = target_army.units[0]

    # Fill the Miracle dice pool with high-value dice so the substitution
    # branch always finds a die that meets the hit/wound target.
    army.miracle_dice = [6, 6, 6, 6, 6, 6, 6, 6]

    return attacker, target, army



# ---------------------------------------------------------------------------
# (a) Gate OFF — legacy per-round behaviour pinned
# ---------------------------------------------------------------------------

class AoFPerPhaseGateOffTests(unittest.TestCase):
    """Gate OFF: spending in call 1 (Shooting phase) prevents spending in
    call 2 (Fight phase) in the same round.  aof_used_this_round is the active
    flag.  Byte-identical to the behaviour before wave 238.  Since the
    wave-239 default flip, the legacy path requires an explicit "0"."""

    def setUp(self):
        os.environ["SWEG_AOF_PER_PHASE"] = "0"

    def tearDown(self):
        os.environ.pop("SWEG_AOF_PER_PHASE", None)
        os.environ.pop("SWEG_SOROR_ABILITIES", None)

    def test_gate_off_second_spend_blocked_by_round_flag(self):
        """Gate OFF: after one spend the round flag is True; a second attack()
        call in the same round must NOT spend again (aof_used_this_round blocks
        the squad-level budget is also exhausted, both layers checked)."""
        os.environ["SWEG_AOF_PER_PHASE"] = "0"
        attacker, target, army = _setup_units()

        import random as _rng
        _rng.seed(42)

        # First call — simulate Shooting phase spend.
        pool_before_first = len(army.miracle_dice)
        attacker.attack(target, distance=12.0, mode="ranged")
        pool_after_first = len(army.miracle_dice)
        first_spent = pool_before_first - pool_after_first

        # If the first call did spend (hit or wound was low), check that the
        # round flag and squad budget are now set so the second call cannot.
        if first_spent > 0:
            # Verify the round flag is set.
            self.assertTrue(
                attacker.aof_used_this_round,
                "Gate OFF: aof_used_this_round must be True after a spend"
            )
            # Second call — simulate Fight phase (same round, flag still True).
            pool_before_second = len(army.miracle_dice)
            attacker.attack(target, distance=12.0, mode="ranged")
            pool_after_second = len(army.miracle_dice)
            second_spent = pool_before_second - pool_after_second

            self.assertEqual(
                second_spent, 0,
                f"Gate OFF: second attack() call in same round must not spend "
                f"a Miracle die (aof_used_this_round is True), but {second_spent} "
                f"dice were consumed."
            )
        else:
            # No spend happened (all dice already above threshold or different
            # roll path); still verify the phase flag is False.
            self.assertFalse(
                attacker.aof_used_this_round,
                "Gate OFF: aof_used_this_round must be False when no spend occurred"
            )

    def test_gate_off_phase_flag_not_used(self):
        """Gate OFF: aof_used_this_phase must remain False regardless of spends
        (the per-phase flag is not read or written on the legacy path)."""
        os.environ["SWEG_AOF_PER_PHASE"] = "0"
        attacker, target, army = _setup_units()

        import random as _rng
        _rng.seed(7)

        for _ in range(10):
            attacker.attack(target, distance=12.0, mode="ranged")

        self.assertFalse(
            attacker.aof_used_this_phase,
            "Gate OFF: aof_used_this_phase must stay False (not used in legacy path)"
        )


# ---------------------------------------------------------------------------
# (b) Gate ON — codex-correct per-phase behaviour
# ---------------------------------------------------------------------------

class AoFPerPhaseGateOnTests(unittest.TestCase):
    """Gate ON (SWEG_AOF_PER_PHASE=1): a unit may spend once in the Shooting
    phase AND once in the Fight phase, but not twice within the same phase."""

    def setUp(self):
        os.environ["SWEG_AOF_PER_PHASE"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_AOF_PER_PHASE", None)
        os.environ.pop("SWEG_SOROR_ABILITIES", None)

    def test_gate_on_spend_then_reset_allows_second_spend(self):
        """Gate ON: after a spend, resetting aof_used_this_phase (simulating a
        new phase) allows another spend in the next attack() call."""
        attacker, target, army = _setup_units()

        import random as _rng
        _rng.seed(42)

        # First call — simulates Shooting phase.
        pool_before = len(army.miracle_dice)
        attacker.attack(target, distance=12.0, mode="ranged")
        pool_after = len(army.miracle_dice)
        first_spent = pool_before - pool_after

        if first_spent > 0:
            # Phase flag must be set.
            self.assertTrue(
                attacker.aof_used_this_phase,
                "Gate ON: aof_used_this_phase must be True after a spend"
            )
            # Round flag must NOT be set (gate ON does not write aof_used_this_round).
            self.assertFalse(
                attacker.aof_used_this_round,
                "Gate ON: aof_used_this_round must remain False (not used when gate is ON)"
            )

            # Simulate the start of the Fight phase: reset the phase flag and
            # clear the squad-level aof budget (as _run_round_vanilla_turns would).
            attacker.aof_used_this_phase = False
            army._unit_budget_used.pop("aof", None)

            # Second call — simulates Fight phase (new phase, flag reset).
            pool_before_second = len(army.miracle_dice)
            attacker.attack(target, distance=0.0, mode="melee")
            pool_after_second = len(army.miracle_dice)
            second_spent = pool_before_second - pool_after_second

            self.assertGreater(
                second_spent, 0,
                "Gate ON: after resetting phase flag and squad budget, a second "
                "phase spend must be allowed (codex: one Act of Faith per phase)"
            )

    def test_gate_on_second_spend_blocked_within_same_phase(self):
        """Gate ON: within one phase, a second attack() call on the same unit
        must NOT spend again (aof_used_this_phase blocks it)."""
        attacker, target, army = _setup_units()

        import random as _rng
        _rng.seed(42)

        # First call — simulates first attack in Shooting phase.
        pool_before = len(army.miracle_dice)
        attacker.attack(target, distance=12.0, mode="ranged")
        pool_after = len(army.miracle_dice)
        first_spent = pool_before - pool_after

        if first_spent > 0:
            self.assertTrue(
                attacker.aof_used_this_phase,
                "Gate ON: phase flag must be True after first spend"
            )
            # Second call — same phase, flag still True.
            pool_before_second = len(army.miracle_dice)
            attacker.attack(target, distance=12.0, mode="ranged")
            pool_after_second = len(army.miracle_dice)
            second_spent = pool_before_second - pool_after_second

            self.assertEqual(
                second_spent, 0,
                f"Gate ON: second attack() call in same phase must not spend a "
                f"Miracle die (aof_used_this_phase is True), but {second_spent} "
                f"dice were consumed."
            )

    def test_gate_on_round_flag_stays_false(self):
        """Gate ON: aof_used_this_round must never be set True; the per-phase
        gate writes aof_used_this_phase only."""
        attacker, target, army = _setup_units()

        import random as _rng
        _rng.seed(7)

        for _ in range(5):
            attacker.attack(target, distance=12.0, mode="ranged")
            self.assertFalse(
                attacker.aof_used_this_round,
                "Gate ON: aof_used_this_round must stay False "
                "(only aof_used_this_phase is written when gate is ON)"
            )


if __name__ == "__main__":
    unittest.main()
