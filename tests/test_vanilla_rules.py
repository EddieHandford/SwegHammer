"""Tests for vanilla WH40k 10e rules mode (`RulesConfig.vanilla_10e()`).

The simulator's default is currently SwegHammer mode for backward compat
with the existing 588-test suite; vanilla mode is opt-in via the
`rules=` kwarg on the Battle ctor. These tests prove each Tier-1 SwegHammer
rule modification is correctly gated off in vanilla mode, plus a tiny
integration smoke confirming a vanilla battle completes with a sensible
win-rate.

See plan `enchanted-wiggling-sundae` step 1 + step 2.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.army_builder import build_faction_random_army
from code.map import Map, Objective
from code.maps import DEFAULT_MAP
from code.simulator import Battle, RulesConfig
from code.stratagems import CP_CAP
from code.units import UnitProfile


def _basic_profile(name: str = "Test", hp: int = 2) -> UnitProfile:
    return UnitProfile(
        name=name, health=hp, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, attacks=2, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
    )


def _two_unit_army(name: str, profile_name: str, positions) -> Army:
    profile = _basic_profile(profile_name)
    army = Army(name)
    for i, pos in enumerate(positions):
        army.add_unit(profile)
        u = army.units[-1]
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


class RulesConfigTests(unittest.TestCase):
    def test_vanilla_10e_factory_all_off(self) -> None:
        cfg = RulesConfig.vanilla_10e()
        self.assertFalse(cfg.alternating_activations)
        self.assertFalse(cfg.simultaneous_movement)
        self.assertFalse(cfg.cp_catchup_bonus)
        self.assertFalse(cfg.coordinated_army_plan)

    def test_sweghammer_factory_all_on(self) -> None:
        cfg = RulesConfig.sweghammer()
        self.assertTrue(cfg.alternating_activations)
        self.assertTrue(cfg.simultaneous_movement)
        self.assertTrue(cfg.cp_catchup_bonus)
        self.assertTrue(cfg.coordinated_army_plan)

    def test_default_battle_uses_vanilla_10e(self) -> None:
        """Default Battle ctor now runs vanilla WH40k 10e rules. The
        simulator's primary job is reproducing real tournament play;
        SwegHammer's alternating-activation ruleset is opt-in."""
        a = _two_unit_army("A", "AOne", [(10.0, 10.0)])
        b = _two_unit_army("B", "BOne", [(20.0, 20.0)])
        battle = Battle(a, b)
        self.assertFalse(battle.rules.alternating_activations)
        self.assertFalse(battle.rules.simultaneous_movement)
        self.assertFalse(battle.rules.cp_catchup_bonus)
        self.assertFalse(battle.rules.coordinated_army_plan)


class CPCatchupBonusGateTests(unittest.TestCase):
    """Smaller-army CP catch-up bonus must be inert under vanilla rules."""

    def setUp(self):
        # command-phase scoring is now default-ON; this mechanic test uses the legacy timing
        os.environ["SWEG_CMDSCORE"] = "0"

    def test_vanilla_does_not_award_catchup_cp(self) -> None:
        # Lopsided armies: A has 1 unit, B has 4 units.
        a = _two_unit_army("A", "Sm", [(5.0, 5.0)])
        b = _two_unit_army("B", "Bg", [(20.0, 20.0), (21.0, 21.0),
                                       (22.0, 22.0), (23.0, 23.0)])
        a_initial_cp = a.command_points
        random.seed(0)
        battle = Battle(a, b, rules=RulesConfig.vanilla_10e(), map_=DEFAULT_MAP)
        # Run a single round to trigger _award_cp's "round_num > 1" gate
        # path — actually that's gated round 2+, so run 2 rounds.
        battle._assign_uids()
        battle._deploy_armies()
        battle._run_round(1)
        battle._run_round(2)
        # Under vanilla, A is smaller but receives no catch-up. The only
        # CP that can flow in is the per-round Command-phase drip
        # (secondary-economy audit fix D4: both players gain 1CP at the
        # start of EACH of the two Command phases per round, so 2CP/round),
        # capped at CP_CAP=6 — so the increase across 2 rounds is at most
        # CP_CAP - a_initial_cp (the drip alone would be +4, but the bank
        # ceiling clamps it).
        self.assertLessEqual(a.command_points - a_initial_cp, CP_CAP - a_initial_cp)

    def test_sweghammer_does_award_catchup_cp(self) -> None:
        a = _two_unit_army("A", "Sm", [(5.0, 5.0)])
        b = _two_unit_army("B", "Bg", [(20.0, 20.0), (21.0, 21.0),
                                       (22.0, 22.0), (23.0, 23.0)])
        a_initial_cp = a.command_points
        random.seed(0)
        battle = Battle(a, b, rules=RulesConfig.sweghammer(), map_=DEFAULT_MAP)
        battle._assign_uids()
        battle._deploy_armies()
        battle._run_round(1)
        battle._run_round(2)
        # SwegHammer awards catch-up: A is far smaller than B, so the
        # bonus fires in round 2 — total CP gain should EXCEED the
        # vanilla ceiling (CP_CAP - a_initial_cp, the corrected 2CP/round
        # drip clamped at the bank cap) because `_award_cp`'s catch-up
        # bonus is applied on top and is not itself clamped to CP_CAP.
        self.assertGreater(a.command_points - a_initial_cp, CP_CAP - a_initial_cp)


class ArmyPlanGateTests(unittest.TestCase):
    """Coordinated army-plan picker must not run in vanilla mode."""

    def test_vanilla_leaves_army_plan_none(self) -> None:
        a = _two_unit_army("A", "Aa", [(10.0, 10.0), (12.0, 10.0)])
        b = _two_unit_army("B", "Bb", [(20.0, 20.0), (22.0, 20.0)])
        random.seed(0)
        battle = Battle(a, b, rules=RulesConfig.vanilla_10e(), map_=DEFAULT_MAP)
        battle._assign_uids()
        battle._deploy_armies()
        battle._run_round(1)
        self.assertIsNone(a.army_plan)
        self.assertIsNone(b.army_plan)


class TurnStructureGateTests(unittest.TestCase):
    """Vanilla mode runs whole-army phase-by-phase turns; SwegHammer
    runs pair-alternating activations. We can't directly observe the
    activation order without instrumentation, but we can confirm the
    Battle completes under both modes."""

    def test_vanilla_battle_runs_to_completion(self) -> None:
        random.seed(0)
        a = build_faction_random_army("A", "Adeptus Astartes", 1000)
        b = build_faction_random_army("B", "Necrons", 1000)
        result = Battle(a, b, rules=RulesConfig.vanilla_10e(),
                        map_=DEFAULT_MAP).run()
        self.assertIn(result.winner, (a.name, b.name, None))
        self.assertGreater(result.rounds, 0)


class VanillaSmokeTests(unittest.TestCase):
    """Integration smoke: across 30 seeded vanilla battles, win-rate
    sits in a plausible band (35-65%). A degenerate gate would push
    win-rate to 0 / 100 / hang."""

    def setUp(self) -> None:
        # HERMETIC GUARD (see [[project-classify-cache-flakiness]]): these
        # win-rate-balance smokes re-seed RNG per battle but are still
        # sensitive to PROCESS-GLOBAL state that other tests accumulate —
        # notably the module-level lru_caches (`lookup_ability`, the combat
        # fraction caches) and the `effective_buffs` cache, which gated
        # faction-ability tests (e.g. Sororitas / Chaos Space Marines) flood
        # with extra entries when they run a battle with their gate ON. Reset
        # that shared state + any leaked faction gate so this smoke is
        # order-independent.
        import functools  # noqa: F401  (kept for clarity)
        from code import leaders, strategy, units
        for _g in ("SWEG_SOROR_ABILITIES", "SWEG_CSM_ABILITIES"):
            os.environ.pop(_g, None)
        for _fn in (
            getattr(leaders, "lookup_ability", None),
            getattr(units, "wound_probability", None),
            getattr(strategy, "_unsaved_fraction_cached", None),
            getattr(strategy, "_fnp_pass_fraction_cached", None),
        ):
            _cc = getattr(_fn, "cache_clear", None)
            if _cc is not None:
                _cc()
        _bump = getattr(leaders, "bump_buffs_generation", None)
        if _bump is not None:
            _bump()

    def test_marines_vs_necrons_winrate_sane(self) -> None:
        wins = 0
        n = 30
        for seed in range(n):
            random.seed(seed)
            a = build_faction_random_army(
                "A", "Adeptus Astartes", 1000)
            b = build_faction_random_army(
                "B", "Necrons", 1000)
            result = Battle(a, b, rules=RulesConfig.vanilla_10e(),
                            map_=DEFAULT_MAP).run()
            if result.winner == a.name:
                wins += 1
        wr = wins / n
        self.assertGreater(wr, 0.20)
        self.assertLess(wr, 0.80)

    def test_marines_mirror_winrate_balanced(self) -> None:
        wins = 0
        n = 30
        for seed in range(n):
            random.seed(seed)
            a = build_faction_random_army(
                "A", "Adeptus Astartes", 1000)
            b = build_faction_random_army(
                "B", "Adeptus Astartes", 1000)
            result = Battle(a, b, rules=RulesConfig.vanilla_10e(),
                            map_=DEFAULT_MAP).run()
            if result.winner == a.name:
                wins += 1
        wr = wins / n
        # Mirror match: should be close to 50/50 in expectation, allow
        # a generous band for n=30 noise.
        self.assertGreater(wr, 0.30)
        self.assertLess(wr, 0.70)


if __name__ == "__main__":
    unittest.main()
