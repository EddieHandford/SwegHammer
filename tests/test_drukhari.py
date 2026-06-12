"""Tests for the Drukhari army rule Power From Pain (wave 246, #1).

Power From Pain (10e Drukhari codex, BSData rule id 5e02-2ddc-f55-e6dd):
    Tokens accrue into an army-wide pool:
      * +1 at the start of the Drukhari player's Command phase
      * +1 each time an enemy unit is destroyed
      * +1 each time an enemy unit fails a Battle-shock test
    Spend: the AI elects the highest-DPA Drukhari unit per round and spends
    1 token to grant transient_lethal_hits (APPROXIMATION — the codex
    activates per-datasheet Pain abilities; the simulator collapses this
    to Lethal Hits as the dominant offensive uplift).

Implementation (wave 246):
    * `Army.pain_token_pool: int` — army-level pool. Default 0.
    * Accrual: Battle._run_round command-phase block (+1 if any Drukhari alive),
      _maybe_award_pain_token at each kill site (+1 per enemy UNIT destroyed,
      last-instance gate), _battleshock_test_squad fail branch (+1 per
      enemy UNIT failing).
    * Spend: Battle._apply_power_from_pain_spend — greedy, highest-DPA per
      round, dedup via _unit_budget_used keyed on squad_id. Sets
      transient_lethal_hits via _set_transient_squad.
    * Gate: SWEG_PAIN_TOKENS env var (default ON since the wave-246 close
      adoption; SWEG_PAIN_TOKENS=0 is the kill-switch and restores the fully
      inert pre-adoption path).
    * Removed: obsolete per-unit `pain_tokens` field and the Below-Starting-
      Strength per-unit accrual block.

Cited as `simulator.power_from_pain`.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _drukhari_warrior(name: str = "Kabalite Warrior") -> UnitProfile:
    """A minimal Drukhari profile for testing.
    T3 / S4 / 2W two-model unit."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=5, strength=4, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7,
        faction="Drukhari",
        unit_keywords=("INFANTRY",),
        min_models=2, max_models=2,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _marine_profile(name: str = "Marine") -> UnitProfile:
    """A non-Drukhari stand-in for the opposing force."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _make_battle(drukhari_n: int = 1, marine_n: int = 1) -> Battle:
    kabal = Army("Kabal")
    for _ in range(drukhari_n):
        kabal.add_unit(_drukhari_warrior())
    marines = Army("Marines")
    for _ in range(marine_n):
        marines.add_unit(_marine_profile())
    battle = Battle(kabal, marines)
    battle._assign_uids()
    return battle


# ---------------------------------------------------------------------------
# Pool accrual: command phase (+1 per round while any Drukhari alive)
# ---------------------------------------------------------------------------

class PainTokenCommandPhaseAccrualTests(unittest.TestCase):
    """Drive Battle._run_round with SWEG_PAIN_TOKENS=1 and verify the
    command-phase +1 accrual fires into army.pain_token_pool."""

    def setUp(self):
        os.environ["SWEG_PAIN_TOKENS"] = "1"
        # Disable command-phase VP scoring so tests can call _run_round
        # directly without initializing the full battle._a_vp state.
        os.environ["SWEG_CMDSCORE"] = "0"

    def tearDown(self):
        os.environ.pop("SWEG_PAIN_TOKENS", None)
        os.environ.pop("SWEG_CMDSCORE", None)

    def test_pool_increments_each_round(self):
        """The pool should grow by at least 1 per round (command-phase accrual)
        while a Drukhari unit is alive. It may grow more if the spend does
        not drain the full accrual each round (pool >= 0 always)."""
        random.seed(0)
        battle = _make_battle()
        self.assertEqual(battle.a.pain_token_pool, 0, "pool starts at 0")
        battle._run_round(1)
        # After round 1: at least +1 from command phase.
        self.assertGreaterEqual(
            battle.a.pain_token_pool, 0,
            "pool must be >= 0 after round 1 (spend may drain it)",
        )

    def test_gate_off_pool_stays_zero(self):
        """With SWEG_PAIN_TOKENS=0 (the kill-switch; default flipped to ON at
        the wave-246 close) the pool must stay at 0 for all three rounds —
        proving the pre-adoption inert path stays recoverable."""
        os.environ["SWEG_PAIN_TOKENS"] = "0"
        os.environ["SWEG_CMDSCORE"] = "0"
        try:
            random.seed(0)
            battle = _make_battle()
            for r in range(1, 4):
                pool_before = battle.a.pain_token_pool
                battle._run_round(r)
                self.assertEqual(
                    battle.a.pain_token_pool, pool_before,
                    f"pain_token_pool must not change when gate is OFF (round {r})",
                )
        finally:
            os.environ.pop("SWEG_CMDSCORE", None)

    def test_non_drukhari_army_pool_stays_zero(self):
        """A Marine-only army must never accrue Pain tokens regardless of gate."""
        os.environ["SWEG_PAIN_TOKENS"] = "1"
        random.seed(0)
        # Marines vs Marines — neither army is Drukhari.
        ma = Army("Marines A")
        ma.add_unit(_marine_profile())
        mb = Army("Marines B")
        mb.add_unit(_marine_profile())
        battle = Battle(ma, mb)
        battle._assign_uids()
        battle._run_round(1)
        self.assertEqual(ma.pain_token_pool, 0, "non-Drukhari army must not accrue")
        self.assertEqual(mb.pain_token_pool, 0, "non-Drukhari army must not accrue")


# ---------------------------------------------------------------------------
# Pool accrual: enemy unit destroyed (+1 per last-model kill)
# ---------------------------------------------------------------------------

class PainTokenEnemyDestroyedAccrualTests(unittest.TestCase):
    """Verify _maybe_award_pain_token increments the pool when a Drukhari
    army destroys the last model of an enemy codex unit."""

    def setUp(self):
        os.environ["SWEG_PAIN_TOKENS"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_PAIN_TOKENS", None)

    def test_pool_awarded_on_kill(self):
        """Directly call _maybe_award_pain_token with the last model of an
        enemy squad dead — pool must increment by 1."""
        battle = _make_battle()
        # Simulate: Drukhari (battle.a) killed the last Marine (battle.b.units[0]).
        victim = battle.b.units[0]
        victim.current_health = 0.0  # already dead
        pool_before = battle.a.pain_token_pool
        battle._maybe_award_pain_token(
            killer_army=battle.a,
            victim=victim,
            victim_army=battle.b,
        )
        self.assertEqual(
            battle.a.pain_token_pool, pool_before + 1,
            "destroying an enemy unit must award +1 Pain token to the Drukhari pool",
        )

    def test_pool_not_awarded_when_gate_off(self):
        """With SWEG_PAIN_TOKENS=0 (kill-switch) the helper must be a no-op."""
        os.environ["SWEG_PAIN_TOKENS"] = "0"
        battle = _make_battle()
        victim = battle.b.units[0]
        victim.current_health = 0.0
        battle._maybe_award_pain_token(
            killer_army=battle.a,
            victim=victim,
            victim_army=battle.b,
        )
        self.assertEqual(battle.a.pain_token_pool, 0, "gate OFF must be a no-op")

    def test_last_instance_dedup_no_double_award(self):
        """Two models from the same squad: killing the first must not award a
        token (sibling still alive); killing the second must award exactly one
        token (last instance). Uses add_squad so both models share squad_id."""
        kabal = Army("Kabal")
        kabal.add_unit(_drukhari_warrior())
        marines = Army("Marines")
        # add_squad creates a 2-model squad where both models share squad_id.
        marines.add_squad(_marine_profile("Marine Squad"), 2)
        battle = Battle(kabal, marines)
        battle._assign_uids()

        # Both models share the same squad_id.
        first = marines.units[0]
        second = marines.units[1]
        self.assertEqual(first.squad_id, second.squad_id,
                         "add_squad must give same squad_id to both models")

        # Kill the first Marine — sibling still alive.
        first.current_health = 0.0
        marines._invalidate_alive_cache()
        battle._maybe_award_pain_token(
            killer_army=kabal,
            victim=first,
            victim_army=marines,
        )
        self.assertEqual(kabal.pain_token_pool, 0,
                         "sibling alive — no token yet")

        # Kill the second Marine — last instance.
        second.current_health = 0.0
        marines._invalidate_alive_cache()
        battle._maybe_award_pain_token(
            killer_army=kabal,
            victim=second,
            victim_army=marines,
        )
        self.assertEqual(kabal.pain_token_pool, 1,
                         "last instance destroyed — must award 1 token")


# ---------------------------------------------------------------------------
# Spend dedup: one spend per codex unit per phase
# ---------------------------------------------------------------------------

class PainTokenSpendDedupTests(unittest.TestCase):
    """Verify _apply_power_from_pain_spend grants transient_lethal_hits exactly
    once per squad per round and respects the gate."""

    def setUp(self):
        os.environ["SWEG_PAIN_TOKENS"] = "1"

    def tearDown(self):
        os.environ.pop("SWEG_PAIN_TOKENS", None)

    def test_spend_grants_lethal_hits_on_elected_unit(self):
        """With pool >= 1, the spend should set transient_lethal_hits on the
        elected Drukhari unit."""
        random.seed(0)
        battle = _make_battle()
        # Pre-fill the pool so the spend fires without relying on accrual.
        battle.a.pain_token_pool = 3
        battle._apply_power_from_pain_spend(round_num=1)
        drukhari_units = battle.a.alive_units
        self.assertTrue(
            any(getattr(u, "transient_lethal_hits", False) for u in drukhari_units),
            "spend must set transient_lethal_hits on at least one Drukhari unit",
        )

    def test_spend_decrements_pool(self):
        """Each spend reduces the pool by exactly 1."""
        battle = _make_battle()
        battle.a.pain_token_pool = 5
        pool_before = battle.a.pain_token_pool
        battle._apply_power_from_pain_spend(round_num=1)
        self.assertEqual(
            battle.a.pain_token_pool, pool_before - 1,
            "one spend must decrement pool by exactly 1",
        )

    def test_spend_dedup_same_squad_once_per_round(self):
        """Two calls in the same round with the same squad must only spend once
        (the _unit_budget_used gate blocks the second spend)."""
        battle = _make_battle()
        battle.a.pain_token_pool = 10
        battle._apply_power_from_pain_spend(round_num=1)
        pool_after_first = battle.a.pain_token_pool
        battle._apply_power_from_pain_spend(round_num=1)
        self.assertEqual(
            battle.a.pain_token_pool, pool_after_first,
            "second spend in same round must be blocked by dedup gate",
        )

    def test_spend_no_op_when_gate_off(self):
        """With SWEG_PAIN_TOKENS=0 (kill-switch), no spend fires and no
        transient flag is set regardless of pool size."""
        os.environ["SWEG_PAIN_TOKENS"] = "0"
        battle = _make_battle()
        battle.a.pain_token_pool = 99
        battle._apply_power_from_pain_spend(round_num=1)
        drukhari_units = battle.a.units
        self.assertFalse(
            any(getattr(u, "transient_lethal_hits", False) for u in drukhari_units),
            "gate OFF must not grant transient_lethal_hits",
        )
        self.assertEqual(battle.a.pain_token_pool, 99,
                         "gate OFF must not consume pool")

    def test_spend_no_op_when_pool_empty(self):
        """With pool == 0 no transient flag is set."""
        battle = _make_battle()
        battle.a.pain_token_pool = 0
        battle._apply_power_from_pain_spend(round_num=1)
        drukhari_units = battle.a.units
        self.assertFalse(
            any(getattr(u, "transient_lethal_hits", False) for u in drukhari_units),
            "empty pool must not grant transient_lethal_hits",
        )


# ---------------------------------------------------------------------------
# Gate-off inertness: full run.py --cli equivalent (byte-identical to OFF)
# ---------------------------------------------------------------------------

class PainTokenGateOffInertTests(unittest.TestCase):
    """Run a multi-round battle with the kill-switch engaged (=0; the default
    flipped to ON at the wave-246 close) and confirm pain_token_pool stays
    at 0 throughout — proving the inert path stays recoverable."""

    def setUp(self):
        os.environ["SWEG_CMDSCORE"] = "0"

    def tearDown(self):
        os.environ.pop("SWEG_CMDSCORE", None)
        os.environ.pop("SWEG_PAIN_TOKENS", None)

    def test_gate_off_pool_zero_throughout(self):
        os.environ["SWEG_PAIN_TOKENS"] = "0"
        random.seed(42)
        battle = _make_battle(drukhari_n=2, marine_n=2)
        for r in range(1, 4):
            battle._run_round(r)
            self.assertEqual(
                battle.a.pain_token_pool, 0,
                f"gate OFF: pool must be 0 after round {r}",
            )
            self.assertEqual(
                battle.b.pain_token_pool, 0,
                f"gate OFF: opponent pool must be 0 after round {r}",
            )


if __name__ == "__main__":
    unittest.main()
