"""Tests for the Drukhari army rule Power From Pain (#118).

Power From Pain (10e Drukhari codex, current Wahapedia text):
    Pain abilities only apply to a unit while it is Empowered. The
    Drukhari player gains Pain tokens (1 at start of own Command phase;
    1 per enemy unit destroyed; 1 per enemy unit failing a Battle-shock
    test) into an army-wide pool, and SPENDS them at the per-datasheet
    Pain-ability trigger to Empower a unit until the end of the phase.
    The rule does NOT grant a passive Lethal Hits or Feel No Pain from
    holding a token — that was an older index version. Per-datasheet
    Pain abilities are not catalogued in SwegHammer, so the spend half
    of the rule has no in-sim effect yet.

Implementation (post DRK-PAIN-TOKENS):
    * `Unit.pain_tokens` — per-instance state on the live Unit (NOT the
      immutable UnitProfile). Default 0. The accrual machinery is
      preserved as inert state so future per-datasheet Pain abilities
      have a hook; no Unit.attack or Unit.receive_damage branch reads
      it for any combat effect.
    * Token award: Battle._run_round, after the WAAAGH! block. Faction
      gate on profile.faction == "Drukhari"; below-starting-strength
      gate (multi-model unit AND has lost at least one whole model's
      worth of wounds); cap at 1. (Narrower than the full codex accrual
      list, kept because no downstream consumer reads the count yet
      and additional accruals would be dead state.)

Cited as `simulator.power_from_pain`.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _drukhari_warrior(name: str = "Kabalite Warrior") -> UnitProfile:
    """A minimal Drukhari profile tagged with the canonical faction string.
    Two-model squad (min_models=2) at 1W per model — total health=2 — so
    "Below Starting Strength" (lost one model = current_health <= 1) is
    well-defined under the iter-DRK fix to the Power From Pain trigger.
    T3 / S4 so a Marine hits us on 3+/wounds on 3+ (no AP), and we hit
    Marines on 3+/wound them on 4+."""
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
    """A non-Drukhari stand-in used as the opposing force / control group."""
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


# ---------------------------------------------------------------------------
# Token award: simulator-side gate fires at start of each Command phase
# ---------------------------------------------------------------------------

class PainTokenAwardTests(unittest.TestCase):
    """Drive Battle._run_round and verify the token-award block fires for
    Drukhari units below Starting Strength, caps at 1, and never fires for
    non-Drukhari factions or for full-HP units."""

    def _make_battle(self, drukhari_n: int = 2, marine_n: int = 1) -> Battle:
        kabal = Army("Kabal")
        for _ in range(drukhari_n):
            kabal.add_unit(_drukhari_warrior())
        marines = Army("Marines")
        for _ in range(marine_n):
            marines.add_unit(_marine_profile())
        battle = Battle(kabal, marines)
        battle._assign_uids()
        return battle

    def test_pain_token_awarded_when_wounded(self):
        random.seed(0)
        battle = self._make_battle()
        # Drop the first Drukhari unit below Starting Strength (HP=2 → 1.0).
        battle.a.units[0].current_health = 1.0
        # All other units are at full HP — only the wounded one should gain
        # a token on the Command phase tick.
        battle._run_round(1)
        self.assertEqual(battle.a.units[0].pain_tokens, 1,
                         "Wounded Drukhari unit must gain a Pain Token")
        self.assertEqual(battle.a.units[1].pain_tokens, 0,
                         "Full-HP Drukhari unit must NOT gain a Pain Token")

    def test_pain_token_caps_at_1(self):
        """A unit that already holds a Pain Token must not gain another
        — the cap is enforced before the Command-phase tick increments."""
        random.seed(0)
        battle = self._make_battle()
        # Pre-seed the unit with 1 token and keep it below Starting Strength.
        battle.a.units[0].pain_tokens = 1
        battle.a.units[0].current_health = 1.0
        battle._run_round(1)
        self.assertEqual(battle.a.units[0].pain_tokens, 1,
                         "Pain Token must cap at 1 per unit")

    def test_pain_token_not_awarded_when_full_health(self):
        random.seed(0)
        battle = self._make_battle()
        # Every Drukhari unit is at full HP — no tokens should be awarded.
        battle._run_round(1)
        for u in battle.a.units:
            self.assertEqual(u.pain_tokens, 0,
                             f"{u.profile.name} at full HP must not gain a token")

    def test_pain_token_not_awarded_to_single_model_unit(self):
        """iter-DRK: a single-model Drukhari unit (CHARACTER / VEHICLE /
        MOUNTED) is NEVER Below Starting Strength even when chipped — the
        10e definition of Below Starting Strength requires losing a whole
        model. Previously a Raider taking a single point of damage would
        light up Pain Token effects army-wide; that was the over-modelling
        root cause for Drukhari's +39 pt sim-vs-meta gap."""
        random.seed(0)
        kabal = Army("Kabal")
        # Force a single-model Drukhari unit at chipped health.
        solo = _drukhari_warrior("Drukhari Solo")
        solo = UnitProfile(
            **{f: getattr(solo, f) for f in solo.__dataclass_fields__
               if f not in ("min_models", "max_models")},
            min_models=1, max_models=1,
        )
        kabal.add_unit(solo)
        marines = Army("Marines")
        marines.add_unit(_marine_profile())
        battle = Battle(kabal, marines)
        battle._assign_uids()
        # Chip the solo unit (1.5 / 2.0 HP) — current_health < health but
        # still at "1 model alive", i.e. not Below Starting Strength.
        battle.a.units[0].current_health = 1.5
        battle._run_round(1)
        self.assertEqual(
            battle.a.units[0].pain_tokens, 0,
            "Single-model Drukhari unit must NEVER gain a Pain Token "
            "from chip damage — Below Starting Strength is undefined "
            "for 1-model units.",
        )

    def test_non_drukhari_does_not_get_tokens(self):
        """A Marines unit at half HP must NOT gain a Pain Token — the gate
        is faction-Drukhari only."""
        random.seed(0)
        marines_atk = Army("Marines Attackers")
        marines_atk.add_unit(_marine_profile())
        marines_def = Army("Marines Defenders")
        marines_def.add_unit(_marine_profile())
        battle = Battle(marines_atk, marines_def)
        battle._assign_uids()
        # Drop the attacker below Starting Strength.
        marines_atk.units[0].current_health = 1.0
        battle._run_round(1)
        self.assertEqual(marines_atk.units[0].pain_tokens, 0,
                         "Non-Drukhari unit must NEVER gain a Pain Token")


# ---------------------------------------------------------------------------
# Token effects: post-DRK-PAIN-TOKENS, holding a token grants NO passive
# combat buff. Per current Wahapedia (the codex update), the buff side of
# Power From Pain is per-datasheet Pain abilities activated by SPENDING
# tokens to Empower a unit. SwegHammer has not catalogued any per-datasheet
# Pain abilities, so token state is inert in combat. These tests pin the
# inertness so a future regression that resurrects the passive-buff branch
# (and re-introduces the +33pt Drukhari overshoot from wave 42) is caught.
# ---------------------------------------------------------------------------

class PainTokenEffectsTests(unittest.TestCase):
    """Hold a Pain Token on a Drukhari attacker / defender and verify
    Unit.attack and Unit.receive_damage produce IDENTICAL distributions
    with and without the token — i.e. the legacy passive Lethal Hits and
    FNP 6+ buffs have been removed and tokens have no combat effect."""

    def _wire_battle_round(self, attacker, defender, round_num: int = 1):
        """Minimal Battle shim — Unit.attack hits army_ref._battle_ref on
        the Command-Re-Roll path. We never spend CP in these tests."""
        class _FakeBattle:
            _current_round = 0
            def maybe_fire_command_reroll(self, *args, **kwargs):
                return False
        fb = _FakeBattle()
        fb._current_round = round_num
        attacker.army_ref._battle_ref = fb
        defender.army_ref._battle_ref = fb
        return fb

    def test_pain_token_does_not_grant_lethal_hits(self):
        """A Drukhari attacker with pain_tokens=1 must produce IDENTICAL
        damage output to the same attacker with pain_tokens=0 against a
        T8 target where Lethal Hits would otherwise show a large delta.
        Pinned to catch any regression that resurrects the old passive-
        buff branch (DRK-PAIN-TOKENS, wave 43)."""
        def _trial(with_token: bool, seed: int) -> float:
            random.seed(seed)
            kabal = Army("Kabal")
            kabal.add_unit(_drukhari_warrior())
            # T8 vs S4 = wound on 6+. If passive Lethal Hits were still
            # firing, crit-to-hit (~1/6) would auto-wound instead of having
            # to roll a 6, producing a large gap. We assert NO gap.
            tough_profile = UnitProfile(
                name="Tough Target",
                health=200, damage=1, hit_probability=2 / 3,
                ap=0, save=3, strength=4, toughness=8,
                attacks=1, weapon_damage_per_shot=1.0,
                faction="Adeptus Astartes",
                unit_keywords=("VEHICLE",),
            )
            defenders = Army("Defenders")
            defenders.add_unit(tough_profile)
            attacker = kabal.units[0]
            attacker.uid = "kabal0"
            target = defenders.units[0]
            target.uid = "tgt0"
            if with_token:
                attacker.pain_tokens = 1
            self._wire_battle_round(attacker, target)
            total = 0.0
            for _ in range(2000):
                total += attacker.attack(target, distance=6.0, mode="ranged")
            return total

        with_token = _trial(with_token=True, seed=42)
        without_token = _trial(with_token=False, seed=42)
        self.assertEqual(
            with_token, without_token,
            f"Pain Token must NOT alter Unit.attack output (current "
            f"Wahapedia text grants no passive Lethal Hits from holding "
            f"a token): with={with_token} without={without_token}",
        )

    def test_pain_token_does_not_grant_fnp_6(self):
        """A Drukhari defender with pain_tokens=1 must take IDENTICAL HP
        loss to the same defender with pain_tokens=0. Pinned to catch any
        regression that resurrects the old passive FNP 6+ branch
        (DRK-PAIN-TOKENS, wave 43)."""
        def _trial(defender_has_token: bool, seed: int) -> float:
            random.seed(seed)
            marines = Army("Marines")
            marines.add_unit(_marine_profile())
            kabal = Army("Kabal")
            # Bulky target so a single trial doesn't deplete it.
            durable = UnitProfile(
                **{**_drukhari_warrior().__dict__, "health": 100000.0},
            )
            kabal.add_unit(durable)
            attacker = marines.units[0]
            attacker.uid = "ma0"
            defender = kabal.units[0]
            defender.uid = "kabal0"
            if defender_has_token:
                defender.pain_tokens = 1
            self._wire_battle_round(attacker, defender)
            for _ in range(2000):
                attacker.attack(defender, distance=6.0, mode="ranged")
            return defender.profile.health - defender.current_health

        with_token = _trial(defender_has_token=True, seed=99)
        without_token = _trial(defender_has_token=False, seed=99)
        self.assertEqual(
            with_token, without_token,
            f"Pain Token must NOT alter Unit.receive_damage output "
            f"(current Wahapedia text grants no passive FNP 6+ from "
            f"holding a token): with={with_token} without={without_token}",
        )


if __name__ == "__main__":
    unittest.main()
