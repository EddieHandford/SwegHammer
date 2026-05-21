"""Tests for the Drukhari army rule Power From Pain (#118).

Power From Pain (10e Drukhari army rule, Wahapedia):
    "At the start of each Command phase, each Drukhari unit from your
     army that is below its Starting Strength gains 1 Pain Token. Each
     unit can hold a maximum of 1 Pain Token. While a Drukhari unit
     from your army has a Pain Token, models in that unit have the
     [LETHAL HITS] keyword and a Feel No Pain 6+ ability."

Implementation:
    * `Unit.pain_tokens` — per-instance state on the live Unit (NOT the
      immutable UnitProfile). Default 0.
    * Token award: Battle._run_round, after the WAAAGH! block. Faction
      gate on profile.faction == "Drukhari"; below-starting-strength
      maps to current_health < profile.health; cap at 1.
    * Lethal Hits buff: `Unit.attack` uses `effective_lethal_hits =
      p.lethal_hits or (pain_tokens > 0 and faction == 'Drukhari')`.
    * FNP 6+ buff: `Unit.receive_damage` lowers `effective_fnp` to
      min(effective_fnp, 6) when the defender holds a Pain Token.

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
# Token effects: Lethal Hits + FNP 6+ buffs fire while pain_tokens > 0
# ---------------------------------------------------------------------------

class PainTokenEffectsTests(unittest.TestCase):
    """Run head-to-head attack volleys with and without a Pain Token and
    verify the buffed side does more damage (LETHAL HITS) and takes less
    damage (FNP 6+). Uses deterministic random seeds so the difference is
    measurable, not statistical luck."""

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

    def test_pain_token_grants_lethal_hits(self):
        """A Drukhari attacker with pain_tokens=1 auto-wounds on a crit-hit;
        without the token, the same crit still has to roll to wound. Across
        many attacks against a T8 / 3+ target (where wound rolls would
        usually fail), Lethal Hits must produce strictly more damage."""
        def _trial(with_token: bool, seed: int) -> float:
            random.seed(seed)
            kabal = Army("Kabal")
            kabal.add_unit(_drukhari_warrior())
            # Make the wound roll hard: T8 vs S4 = wound on 6+. Crit-to-hit
            # without Lethal Hits still has to roll a 6 to wound; with
            # Lethal Hits, crit-to-hit auto-wounds. Big delta.
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
        # Crit-to-hit rate is ~1/6 of attacks. With S4 vs T8 the regular
        # wound-on-6 success is 1/6; Lethal Hits converts every crit-hit
        # to an auto-wound (success goes 1 → 1 vs 1/6, ~6x). Even after
        # the save it must be strictly higher.
        self.assertGreater(
            with_token, without_token,
            f"Pain Token (Lethal Hits) should out-damage no-token: "
            f"with={with_token} without={without_token}",
        )

    def test_pain_token_grants_fnp_6(self):
        """A Drukhari defender with pain_tokens=1 absorbs ~1/6 of incoming
        damage via FNP 6+. We track the defender's `current_health` rather
        than `attack`'s returned `total_damage` — FNP saves fire inside
        `receive_damage` and reduce the defender's HP loss, but the return
        value is the pre-FNP damage tally. Across many shots the
        FNP-token defender should have strictly more HP remaining."""
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
            # Return HP lost — lower = better FNP performance.
            return defender.profile.health - defender.current_health

        with_token = _trial(defender_has_token=True, seed=99)
        without_token = _trial(defender_has_token=False, seed=99)
        # FNP 6+ ignores ~1/6 of damage. With 2000 shots, the HP-loss gap is
        # large enough that any reasonable seed shows the FNP benefit.
        self.assertLess(
            with_token, without_token,
            f"Pain Token (FNP 6+) should reduce HP lost: "
            f"with={with_token} without={without_token}",
        )


if __name__ == "__main__":
    unittest.main()
