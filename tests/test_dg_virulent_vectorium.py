"""Tests for the Death Guard Virulent Vectorium detachment (task #195).

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium

Coverage:
  * VIRULENT_VECTORIUM is registered and bound as the default for Death Guard.
  * The detachment exposes all six real codex stratagems.
  * The detachment passive (Worldblight) lights up `_sticky_owner` on DG
    objectives without requiring the `sticky_objective` profile flag.
  * The Putrid Detonation stratagem dispatcher arms
    `Army.putrid_detonation_armed` and the `_maybe_apply_deadly_demise` gate
    auto-triggers on DG VEHICLE deaths.
  * The Leechspore Eruption stratagem dispatcher heals a damaged DG model and
    inflicts mortal wounds on a nearby enemy.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import (
    DEFAULT_BY_FACTION, DETACHMENTS, FACTION_DETACHMENTS, VIRULENT_VECTORIUM,
)
from code.simulator import Battle
from code.stratagems import (
    CREEPING_BLIGHT, DISGUSTINGLY_RESILIENT, LEECHSPORE_ERUPTION,
    OVERWHELMING_GENEROSITY, PLAGUESURGE, PUTRID_DETONATION,
    VIRULENT_VECTORIUM_STRATAGEMS,
)
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _plague_marine_profile() -> UnitProfile:
    return UnitProfile(
        name="Plague Marines",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, oc=2,
        faction="Death Guard",
        fnp=5,
        unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        points_override=100,
    )


def _plagueburst_crawler_profile() -> UnitProfile:
    """A DG VEHICLE with Deadly Demise > 0, so Putrid Detonation has a donor."""
    return UnitProfile(
        name="Plagueburst Crawler",
        health=12, damage=2, hit_probability=2 / 3,
        ap=-2, save=3, strength=8, toughness=11,
        attacks=4, weapon_damage_per_shot=2.0, range_inches=48,
        leadership=7,
        faction="Death Guard",
        unit_keywords=("VEHICLE", "MONSTER"),
        deadly_demise=3,
        points_override=170,
    )


def _typhus_profile() -> UnitProfile:
    """A DG CHARACTER for Plaguesurge / Overwhelming Generosity targeting."""
    return UnitProfile(
        name="Typhus",
        health=6, damage=2, hit_probability=2 / 3,
        ap=-2, save=2, strength=5, toughness=5,
        attacks=4, weapon_damage_per_shot=2.0, range_inches=24,
        leadership=6,
        faction="Death Guard",
        fnp=5,
        unit_keywords=("CHARACTER", "INFANTRY"),
        melee_attacks=6, melee_damage_per_shot=2.0,
        melee_hit_probability=5 / 6, melee_strength=6, melee_ap=-2,
        points_override=150,
    )


def _marine_profile(name: str = "Marine") -> UnitProfile:
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, oc=2,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        points_override=80,
    )


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


class DetachmentRegistryTests(unittest.TestCase):

    def test_virulent_vectorium_registered(self):
        self.assertIn("virulent_vectorium", DETACHMENTS)
        self.assertIs(DETACHMENTS["virulent_vectorium"], VIRULENT_VECTORIUM)

    def test_virulent_vectorium_is_default_for_death_guard(self):
        self.assertEqual(DEFAULT_BY_FACTION["Death Guard"], "virulent_vectorium")
        self.assertIn("virulent_vectorium", FACTION_DETACHMENTS["Death Guard"])

    def test_worldblight_flag_set(self):
        self.assertTrue(
            VIRULENT_VECTORIUM.worldblight_sticky_dg_objectives,
            "Virulent Vectorium must carry the Worldblight flag.",
        )

    def test_six_stratagems_attached(self):
        # The codex Virulent Vectorium detachment carries exactly 6 stratagems.
        self.assertEqual(len(VIRULENT_VECTORIUM_STRATAGEMS), 6)
        # Each constant is wired onto the detachment.
        wired = {s.name for s in VIRULENT_VECTORIUM.stratagems}
        for strat in (
            PUTRID_DETONATION, DISGUSTINGLY_RESILIENT, PLAGUESURGE,
            LEECHSPORE_ERUPTION, OVERWHELMING_GENEROSITY, CREEPING_BLIGHT,
        ):
            self.assertIn(strat.name, wired, f"{strat.name} missing")

    def test_cp_costs_match_wahapedia(self):
        # Wahapedia CP costs verbatim.
        self.assertEqual(PUTRID_DETONATION.cp_cost, 1)
        self.assertEqual(DISGUSTINGLY_RESILIENT.cp_cost, 2)
        self.assertEqual(PLAGUESURGE.cp_cost, 2)
        self.assertEqual(LEECHSPORE_ERUPTION.cp_cost, 1)
        self.assertEqual(OVERWHELMING_GENEROSITY.cp_cost, 1)
        self.assertEqual(CREEPING_BLIGHT.cp_cost, 1)


# ---------------------------------------------------------------------------
# Worldblight — sticky-control for DG objectives
# ---------------------------------------------------------------------------


class WorldblightTests(unittest.TestCase):

    def _build_battle(self) -> Battle:
        dg = Army("Death Guard")
        dg.add_unit(_plague_marine_profile())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        battle = Battle(dg, ast)
        battle._assign_uids()
        # _score_objectives reads / writes self._a_vp / self._b_vp; these
        # are normally initialised by Battle.run() before _score_objectives
        # is ever called, but we're driving _score_objectives directly here.
        battle._a_vp = 0
        battle._b_vp = 0
        return battle

    def test_dg_unit_on_objective_marks_sticky_owner(self):
        """A DG unit (no `sticky_objective` profile flag) sitting on an
        objective under Worldblight should still mark `_sticky_owner` for
        its army at end-of-round scoring."""
        battle = self._build_battle()
        if not battle.map.objectives:
            self.skipTest("Map has no objectives — nothing to score")
        obj = battle.map.objectives[0]
        battle.a.units[0].position = (obj.x, obj.y)
        # No B-side unit on the objective.
        battle.b.units[0].position = (obj.x + 50.0, obj.y + 50.0)
        battle._score_objectives()
        self.assertEqual(
            battle._sticky_owner.get(0), battle.a.name,
            "DG army should hold sticky ownership of objective 0 via Worldblight",
        )

    def test_no_worldblight_no_sticky(self):
        """An Astartes army (no Worldblight) must NOT mark the sticky owner
        when its non-sticky unit sits on the objective."""
        battle = self._build_battle()
        if not battle.map.objectives:
            self.skipTest("Map has no objectives")
        obj = battle.map.objectives[0]
        # Astartes sits on objective; DG is far away.
        battle.b.units[0].position = (obj.x, obj.y)
        battle.a.units[0].position = (obj.x + 50.0, obj.y + 50.0)
        battle._score_objectives()
        self.assertIsNone(
            battle._sticky_owner.get(0),
            "Astartes army has no Worldblight — sticky owner must stay unset.",
        )


# ---------------------------------------------------------------------------
# Putrid Detonation — auto-success Deadly Demise gate
# ---------------------------------------------------------------------------


class PutridDetonationTests(unittest.TestCase):

    def test_armed_flag_skips_d6_roll(self):
        """With putrid_detonation_armed=True, a dying DG VEHICLE auto-deals
        its Deadly Demise mortals (no d6 needed)."""
        random.seed(0)
        dg = Army("Death Guard")
        dg.add_unit(_plagueburst_crawler_profile())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        battle = Battle(dg, ast)
        battle._assign_uids()
        # Place the marine within 6" of the crawler so the demise blast lands.
        battle.a.units[0].position = (10.0, 10.0)
        battle.b.units[0].position = (12.0, 10.0)
        # Arm the stratagem and kill the crawler.
        dg.putrid_detonation_armed = True
        crawler = battle.a.units[0]
        crawler.current_health = 0.0
        hp_before = battle.b.units[0].current_health
        battle._maybe_apply_deadly_demise(crawler)
        # The Marine should have taken 3 mortal wounds (no FNP profile = 0).
        # FNP is honoured but the Marine has no fnp set → mortal lands raw.
        hp_after = battle.b.units[0].current_health
        self.assertLess(
            hp_after, hp_before,
            f"Putrid Detonation should have auto-dealt Deadly Demise: "
            f"hp_before={hp_before}, hp_after={hp_after}",
        )

    def test_unarmed_d6_roll_still_gated(self):
        """Without putrid_detonation_armed, the d6 gate still fires (1-in-6
        trigger). Across many trials, the mean damage dealt is far below
        the auto-success damage (~0.5 vs 3 per trial)."""
        random.seed(42)
        N = 600
        # Multi-wound chassis so the demise damage doesn't cap-clip. Build a
        # one-off profile with health=100 instead of mutating a frozen one.
        big_profile = UnitProfile(
            name="Big",
            health=100, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
            leadership=7, oc=2,
            faction="Adeptus Astartes",
            unit_keywords=("INFANTRY",),
            points_override=80,
        )
        total_damage = 0.0
        for _ in range(N):
            dg = Army("Death Guard")
            dg.add_unit(_plagueburst_crawler_profile())
            ast = Army("Astartes")
            ast.add_unit(big_profile)
            battle = Battle(dg, ast)
            battle._assign_uids()
            battle.a.units[0].position = (10.0, 10.0)
            battle.b.units[0].position = (12.0, 10.0)
            battle.b.units[0].current_health = 100.0
            # DON'T arm — leave gate to the d6 roll.
            dg.putrid_detonation_armed = False
            crawler = battle.a.units[0]
            crawler.current_health = 0.0
            before = battle.b.units[0].current_health
            battle._maybe_apply_deadly_demise(crawler)
            total_damage += before - battle.b.units[0].current_health
        # Expected: 3 dmg × 1/6 trigger rate × N = N/2. Allow wide bounds.
        mean = total_damage / N
        self.assertLess(mean, 1.5, "Unarmed demise should average ~0.5 dmg/trial")
        self.assertGreater(mean, 0.1, "But the d6 gate should sometimes fire")


# ---------------------------------------------------------------------------
# Leechspore Eruption — heal-self + mortal-wound payload
# ---------------------------------------------------------------------------


class LeechsporeEruptionTests(unittest.TestCase):

    def test_dispatcher_heals_and_chips(self):
        """With a wounded DG model adjacent to an enemy, the dispatcher
        spends 1 CP, heals the DG model, and damages the enemy."""
        random.seed(0)
        dg = Army("Death Guard")
        # A wounded Plagueburst Crawler with HP loss high enough to clear
        # the strategy heuristic gate (hp_frac >= 0.5).
        dg.add_unit(_plagueburst_crawler_profile())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        battle = Battle(dg, ast)
        battle._assign_uids()
        # Position the crawler with the Marine 2" away (within the 3" gate).
        crawler = battle.a.units[0]
        marine = battle.b.units[0]
        crawler.position = (10.0, 10.0)
        marine.position = (12.0, 10.0)
        # Burn the crawler down to ~25% HP (9 wounds lost out of 12).
        crawler.current_health = 3.0
        # Marine starts with health=2; bump current_health well above max so
        # the mortal-wound damage shows up without instantly killing the
        # model (receive_damage doesn't cap at max — it just subtracts).
        marine.current_health = 100.0
        # Give DG enough CP to fire.
        dg.command_points = 5
        dg._battle_ref = battle
        ast._battle_ref = battle
        # Set round so the pivotal-turn deferral doesn't block T2.
        battle._current_round = 3
        crawler_hp_before = crawler.current_health
        marine_hp_before = marine.current_health
        battle._try_leechspore_eruption(dg, ast)
        # The crawler should have healed at least 1 wound, and the marine
        # should have taken at least 1 mortal wound.
        self.assertGreater(
            crawler.current_health, crawler_hp_before,
            "Crawler should heal at least 1 wound from Leechspore Eruption",
        )
        self.assertLess(
            marine.current_health, marine_hp_before,
            "Marine should take mortal wounds from Leechspore Eruption",
        )

    def test_no_enemy_in_range_no_fire(self):
        """With no enemy within 3" of the wounded DG model, the stratagem
        must NOT fire (no CP spent)."""
        random.seed(0)
        dg = Army("Death Guard")
        dg.add_unit(_plagueburst_crawler_profile())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        battle = Battle(dg, ast)
        battle._assign_uids()
        crawler = battle.a.units[0]
        marine = battle.b.units[0]
        crawler.position = (10.0, 10.0)
        marine.position = (50.0, 50.0)   # well > 3"
        crawler.current_health = 3.0
        dg.command_points = 5
        dg._battle_ref = battle
        battle._current_round = 3
        cp_before = dg.command_points
        battle._try_leechspore_eruption(dg, ast)
        self.assertEqual(
            dg.command_points, cp_before,
            "No enemy within 3\" — CP must not be spent",
        )


# ---------------------------------------------------------------------------
# Overall smoke: a full battle with Virulent Vectorium runs cleanly
# ---------------------------------------------------------------------------


class VirulentVectoriumSmokeBattleTest(unittest.TestCase):
    """The detachment + 6 stratagems should run through a full battle without
    raising. We don't assert exact VP — just no exceptions and CP doesn't
    go negative."""

    def test_full_battle_no_exceptions(self):
        random.seed(2026)
        dg = Army("Death Guard")
        dg.add_unit(_plague_marine_profile())
        dg.add_unit(_plague_marine_profile())
        dg.add_unit(_plagueburst_crawler_profile())
        dg.add_unit(_typhus_profile())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        ast.add_unit(_marine_profile())
        ast.add_unit(_marine_profile())
        battle = Battle(dg, ast)
        battle.run()  # should not raise
        # CP must not go negative under any dispatch path.
        self.assertGreaterEqual(dg.command_points, 0)
        self.assertGreaterEqual(ast.command_points, 0)


if __name__ == "__main__":
    unittest.main()
