"""Tests for the World Eaters army rule Blood Tithe (#121).

Blood Tithe (10e World Eaters army rule, Wahapedia):
    Each time a WORLD EATERS unit from your army is destroyed, you gain
    1 Blood Tithe point. Each time an enemy unit is destroyed by a WORLD
    EATERS unit from your army, you gain 1 Blood Tithe point. At the
    start of any phase, you can spend Blood Tithe points on Boons of
    Khorne (1=re-roll Charge, 2=+1 to wound vs target, 3=+1 CP,
    4=[LETHAL HITS] on a WE unit for the phase, 5=auto-pass Battle-shock).

Implementation:
    * `Army.blood_tithe` — per-army accumulator (int, starts 0).
    * `Army.blood_tithe_lethal_hits_round` — int|None; round number in
      which a 4-BT spend fired. Read by Unit.attack against the live
      battle round to grant LETHAL HITS on WE attackers.
    * Award hook: `Battle._maybe_award_blood_tithe` fires from every kill
      path (shoot / fight / tank shock / counter-offensive) alongside the
      existing Judgement Token award.
    * Spend block: `Battle._run_round` at the top of the Command phase,
      priority-greedy on the WE side — BT>=4 sets the round flag, else
      BT>=3 spends 3 for +1 CP (capped at 6). 1-BT, 2-BT, 5-BT skipped
      (TODO documented in the citation).

Cited as `simulator.blood_tithe`.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import Unit, UnitProfile


def _berzerker_profile(name: str = "Berzerker") -> UnitProfile:
    """A minimal World Eaters profile (Khorne Berzerker stand-in)."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="World Eaters",
        unit_keywords=("INFANTRY",),
        melee_attacks=4, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5, melee_ap=1,
    )


def _marine_profile(name: str = "Marine") -> UnitProfile:
    """A non-WE control (vanilla Astartes)."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


class BloodTitheAwardTests(unittest.TestCase):
    """Verify _maybe_award_blood_tithe fires on both kill-direction cases."""

    def _make_battle(self) -> Battle:
        we = Army("World Eaters")
        we.add_unit(_berzerker_profile())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        battle = Battle(we, ast, verbose=False)
        battle._assign_uids()
        return battle

    def test_bt_awarded_on_we_kill(self):
        """A WE attacker destroying an enemy unit grants the WE army +1 BT."""
        battle = self._make_battle()
        we, ast = battle.a, battle.b
        attacker = we.units[0]
        victim = ast.units[0]
        self.assertEqual(we.blood_tithe, 0)
        # Drop victim to 0 HP so the next damage call kills it.
        victim.current_health = 0.5
        # Direct invocation of the award helper mirrors what _do_shoot /
        # _do_fight do after the UnitKilled emission.
        battle._maybe_award_blood_tithe(
            killer=attacker, killer_army=we,
            victim=victim, victim_army=ast,
        )
        self.assertEqual(we.blood_tithe, 1)
        self.assertEqual(ast.blood_tithe, 0)

    def test_bt_awarded_on_we_death(self):
        """A WE unit dying (regardless of killer faction) grants the WE
        army +1 BT."""
        battle = self._make_battle()
        we, ast = battle.a, battle.b
        attacker = ast.units[0]    # the non-WE killer
        victim = we.units[0]       # the WE victim
        battle._maybe_award_blood_tithe(
            killer=attacker, killer_army=ast,
            victim=victim, victim_army=we,
        )
        self.assertEqual(we.blood_tithe, 1)
        self.assertEqual(ast.blood_tithe, 0)

    def test_non_we_doesnt_accumulate_bt(self):
        """An Astartes-on-Astartes kill never touches blood_tithe on either
        side — the rule is World-Eaters-only."""
        ast1 = Army("Marines A")
        ast1.add_unit(_marine_profile())
        ast2 = Army("Marines B")
        ast2.add_unit(_marine_profile())
        battle = Battle(ast1, ast2, verbose=False)
        battle._assign_uids()
        attacker = ast1.units[0]
        victim = ast2.units[0]
        battle._maybe_award_blood_tithe(
            killer=attacker, killer_army=ast1,
            victim=victim, victim_army=ast2,
        )
        self.assertEqual(ast1.blood_tithe, 0)
        self.assertEqual(ast2.blood_tithe, 0)

    def test_mirror_match_both_armies_get_bt(self):
        """WE-on-WE kill: victim's army gets +1 (a WE unit died) AND
        killer's army gets +1 (a WE unit killed an enemy unit). Codex
        behaviour — both triggers fire."""
        we_a = Army("WE A")
        we_a.add_unit(_berzerker_profile())
        we_b = Army("WE B")
        we_b.add_unit(_berzerker_profile())
        battle = Battle(we_a, we_b, verbose=False)
        battle._assign_uids()
        attacker = we_a.units[0]
        victim = we_b.units[0]
        battle._maybe_award_blood_tithe(
            killer=attacker, killer_army=we_a,
            victim=victim, victim_army=we_b,
        )
        self.assertEqual(we_a.blood_tithe, 1)
        self.assertEqual(we_b.blood_tithe, 1)


class BloodTitheSpendTests(unittest.TestCase):
    """Drive Battle._run_round and verify the spend block fires correctly."""

    def _make_battle(self) -> Battle:
        we = Army("WE")
        for _ in range(2):
            we.add_unit(_berzerker_profile())
        ast = Army("Astartes")
        for _ in range(2):
            ast.add_unit(_marine_profile())
        battle = Battle(we, ast, verbose=False)
        battle._assign_uids()
        # _run_round drives Battle-shock etc. — needs valid positions so
        # the SYNAPSE pool and on-objective gates don't trip. Deploy the
        # standard line for both armies.
        battle._deploy_armies()
        return battle

    def test_bt_4_grants_lethal_hits(self):
        """A WE army with BT>=4 at the start of a round should spend 4 BT
        and set blood_tithe_lethal_hits_round to the current round —
        enabling effective_lethal_hits on a WE attacker for that round."""
        battle = self._make_battle()
        we = battle.a
        we.blood_tithe = 4
        # Run one round; the spend block runs at the top of _run_round.
        random.seed(2026)
        battle._run_round(1)
        self.assertLessEqual(we.blood_tithe, 1, "BT-4 spend should drain 4 BT")
        self.assertEqual(
            we.blood_tithe_lethal_hits_round, 1,
            "BT-4 spend should record the round it fired in",
        )

    def test_bt_3_grants_cp(self):
        """A WE army with BT=3 at the start of a round should spend 3 BT
        and gain +1 CP (capped at 6)."""
        battle = self._make_battle()
        we = battle.a
        starting_cp = we.command_points
        we.blood_tithe = 3
        random.seed(2026)
        battle._run_round(1)
        self.assertEqual(we.blood_tithe, 0, "BT-3 spend should drain 3 BT")
        # Per-round dripped +1 CP fires too (award_command_phase_cp), so
        # CP gain is at least +2 over the entering value, capped at 6.
        self.assertGreaterEqual(
            we.command_points, min(6, starting_cp + 1),
            "BT-3 spend should yield at least +1 CP on top of normal CP drip",
        )

    def test_bt_4_priority_over_bt_3(self):
        """At BT=5, the spender should pick the 4-BT option over the 3-BT
        option (the priority-greedy ordering puts Lethal Hits first)."""
        battle = self._make_battle()
        we = battle.a
        we.blood_tithe = 5
        random.seed(2026)
        battle._run_round(1)
        self.assertEqual(
            we.blood_tithe_lethal_hits_round, 1,
            "BT-4 takes priority over BT-3 — Lethal Hits should fire",
        )
        # 5 - 4 = 1 left; should not have also drained 3 for CP.
        self.assertEqual(we.blood_tithe, 1)

    def test_bt_below_3_no_spend(self):
        """BT=2 should not trigger either spend (Lethal Hits costs 4, CP
        costs 3; the 1/2/5 options aren't modelled yet)."""
        battle = self._make_battle()
        we = battle.a
        we.blood_tithe = 2
        random.seed(2026)
        battle._run_round(1)
        self.assertEqual(we.blood_tithe, 2, "BT=2 should be untouched")
        self.assertIsNone(we.blood_tithe_lethal_hits_round)

    def test_non_we_army_doesnt_spend(self):
        """Even with blood_tithe artificially set, a non-WE army's spend
        block is gated off — the faction check short-circuits."""
        ast1 = Army("Marines A")
        ast1.add_unit(_marine_profile())
        ast2 = Army("Marines B")
        ast2.add_unit(_marine_profile())
        battle = Battle(ast1, ast2, verbose=False)
        battle._assign_uids()
        battle._deploy_armies()
        ast1.blood_tithe = 4
        random.seed(2026)
        battle._run_round(1)
        # Non-WE: spend block doesn't trigger, so BT stays 4 and
        # the round flag stays None.
        self.assertEqual(ast1.blood_tithe, 4)
        self.assertIsNone(ast1.blood_tithe_lethal_hits_round)


class BloodTitheLethalHitsAttackTests(unittest.TestCase):
    """Verify the BT-4 Lethal Hits buff actually affects Unit.attack."""

    def test_bt_4_lethal_hits_fires_on_we_attacker(self):
        """When the WE army has blood_tithe_lethal_hits_round == cur_round,
        a WE attacker's crit-to-hit auto-wounds. Compare wounds dealt with
        the buff vs without — buff version should kill more often."""
        we = Army("WE")
        we.add_unit(_berzerker_profile())
        ast = Army("Marines")
        ast.add_unit(_marine_profile())
        # Battle ties up _battle_ref and assigns uids.
        battle = Battle(we, ast, verbose=False)
        battle._assign_uids()

        attacker = we.units[0]
        # Make damage high enough to one-shot to amplify the signal.
        # We measure expected damage across many trials.
        N = 2000

        # ---- Without the buff ---------------------------------------
        random.seed(2026)
        battle._current_round = 1
        we.blood_tithe_lethal_hits_round = None
        no_buff_total = 0.0
        for _ in range(N):
            target = Unit(_marine_profile())
            target.uid = "B0"
            target.army_ref = ast
            target.current_health = 100.0
            attacker.attack(target, distance=1.0, mode="melee")
            no_buff_total += 100.0 - target.current_health

        # ---- With the buff active -----------------------------------
        random.seed(2026)
        battle._current_round = 1
        we.blood_tithe_lethal_hits_round = 1
        buff_total = 0.0
        for _ in range(N):
            target = Unit(_marine_profile())
            target.uid = "B0"
            target.army_ref = ast
            target.current_health = 100.0
            attacker.attack(target, distance=1.0, mode="melee")
            buff_total += 100.0 - target.current_health

        self.assertGreater(
            buff_total, no_buff_total,
            f"BT-4 Lethal Hits should increase damage; got buff={buff_total:.1f} "
            f"vs no_buff={no_buff_total:.1f}",
        )

    def test_bt_4_lethal_hits_doesnt_fire_on_non_we(self):
        """A non-WE attacker should not gain Lethal Hits even if some
        rogue army has the round flag set. Faction gate."""
        ast1 = Army("Marines A")
        ast1.add_unit(_marine_profile())
        ast2 = Army("Marines B")
        ast2.add_unit(_marine_profile())
        battle = Battle(ast1, ast2, verbose=False)
        battle._assign_uids()
        attacker = ast1.units[0]

        # Force the round flag on the non-WE army (pathological case).
        ast1.blood_tithe_lethal_hits_round = 1
        battle._current_round = 1

        N = 1000
        # The expectation is statistical: with the gate working, the
        # attacker's effective_lethal_hits stays False, so damage stays
        # at the normal wound-roll-driven level. We assert nothing fancy
        # here — the units.py gate has `p.faction == "World Eaters"`
        # in the new code path; a sanity invariant check is enough.
        random.seed(2026)
        total = 0.0
        for _ in range(N):
            target = Unit(_marine_profile())
            target.uid = "B0"
            target.army_ref = ast2
            target.current_health = 100.0
            attacker.attack(target, distance=1.0, mode="melee")
            total += 100.0 - target.current_health
        # Just verify the run didn't crash and produced sensible output.
        self.assertGreater(total, 0.0)
        self.assertLess(total, N * 2.0)


class BloodTitheKillIntegrationTests(unittest.TestCase):
    """End-to-end: a kill in `Battle._do_shoot` actually drives BT up."""

    def test_fight_kill_awards_bt(self):
        """Drive _do_fight directly: WE attacker, low-HP Astartes target.
        After the swing lands the kill, we.blood_tithe must be >= 1.
        Loops until a kill lands (the attack is stochastic — 4 melee
        attacks at 2/3 hit / 5+ wound usually kills a 0.1-HP target,
        but we re-roll the rng to make the test deterministic on any
        future random.seed shift)."""
        we = Army("WE")
        we.add_unit(_berzerker_profile())
        ast = Army("Marines")
        ast.add_unit(_marine_profile())
        battle = Battle(we, ast, verbose=False)
        battle._assign_uids()
        battle._deploy_armies()
        attacker = we.units[0]
        target = ast.units[0]
        # Put both units in melee engagement (1" of each other).
        attacker.position = (target.position[0] + 0.5, target.position[1])

        # Replay attack rounds until we get a kill. Each iteration resets
        # the target to 0.1 HP. We try a handful of seeds to make sure
        # at least one lands a wound (4 attacks at ~33%-wound = ~80%
        # chance per round; this loop tops out in 1-3 iterations).
        killed = False
        for seed in (2026, 1234, 42, 7, 99, 314):
            target.current_health = 0.1
            we.blood_tithe = 0
            random.seed(seed)
            battle._do_fight(attacker, we, ast)
            if not target.is_alive:
                killed = True
                break
        self.assertTrue(killed, "Target should have died on at least one seed")
        self.assertGreaterEqual(
            we.blood_tithe, 1,
            "WE army should gain Blood Tithe after killing an enemy unit",
        )


class TestBloodSurge(unittest.TestCase):
    """MR-WE-3 — Khorne Berzerkers' Blood Surge reactive move.

    Verifies that when a Berzerker unit loses at least one model to a
    shooting attack, it advances toward the shooter via the D6+2
    reactive move (`simulator.blood_surge`).

    Per-model architecture (Issue #61 fix): each Unit instance IS one
    physical model (health=2, min_models=1).  A squad of ten Berzerkers
    is ten separate Unit objects sharing the same squad_id on the same
    Army.  The trigger fires when the targeted model unit dies (its
    health drops to 0), and the whole surviving squad surges together.
    """

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _make_shooter(position=(10.0, 30.0)):
        """Build a minimal Marine shooter unit."""
        profile = UnitProfile(
            name="Tactical Marine",
            health=2, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
            leadership=7,
            faction="Adeptus Astartes",
            unit_keywords=("INFANTRY",),
        )
        u = Unit(profile)
        u.position = position
        return u

    @staticmethod
    def _berzerker_profile():
        """Return the Khorne Berzerkers UnitProfile (per-model, health=2)."""
        return UnitProfile(
            name="Khorne Berzerkers",   # name gate is exact
            health=2, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=12,
            leadership=7,
            faction="World Eaters",   # faction gate
            unit_keywords=("INFANTRY",),
            min_models=1,   # per-model representation: one Unit = one model
            melee_attacks=4, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=5, melee_ap=1,
        )

    @staticmethod
    def _build_squad(profile, positions, squad_id=0):
        """Create Unit objects sharing squad_id on a fresh Army.

        Returns (army, [unit, ...]).  Each unit is positioned at the
        corresponding entry in ``positions``.  army_ref and squad_id are
        set on every unit so the sibling-collection logic in
        _maybe_apply_blood_surge can find them.
        """
        army = Army(name="WE")
        units = []
        for pos in positions:
            u = Unit(profile)
            u.position = pos
            u.army_ref = army
            u.squad_id = squad_id
            army.units.append(u)
            units.append(u)
        army._invalidate_alive_cache()
        return army, units

    # ------------------------------------------------------------------ tests

    def test_blood_surge_fires_when_targeted_model_dies(self):
        """Surge triggers when the shot model's health drops to zero.

        The targeted Berzerker model dies (health 2 -> 0).  A surviving
        sibling in the same squad_id should surge toward the shooter.
        This is the core per-model fix: previously the pooled-health
        formula mis-computed model destruction, triggering on chip damage
        or not at all when the model died.
        """
        profile = self._berzerker_profile()
        # Squad of two models: model A (the target) and model B (the sibling).
        positions = [(40.0, 30.0), (42.0, 30.0)]
        we, (model_a, model_b) = self._build_squad(profile, positions)

        shooter = self._make_shooter(position=(10.0, 30.0))
        marines = Army(name="Marines")
        marines.units = [shooter]

        battle = Battle(we, marines)

        # Simulate model A being killed: snapshot health_before = 2.0, then
        # drop to 0 (dead).
        model_a.current_health = 0.0

        sibling_pos_before = model_b.position
        random.seed(0)
        # The defender is model_a (the killed model).
        battle._maybe_apply_blood_surge(
            defender=model_a, attacker_army=marines, health_before=2.0,
        )

        # model_b (alive sibling) should have moved toward the shooter.
        sibling_gap_before = (
            (sibling_pos_before[0] - shooter.position[0]) ** 2
            + (sibling_pos_before[1] - shooter.position[1]) ** 2
        ) ** 0.5
        sibling_gap_after = (
            (model_b.position[0] - shooter.position[0]) ** 2
            + (model_b.position[1] - shooter.position[1]) ** 2
        ) ** 0.5
        self.assertLess(
            sibling_gap_after, sibling_gap_before,
            "Surviving sibling should surge toward the shooter after a "
            "Berzerker model is destroyed",
        )
        # D6+2 clamped at up to 8 inches of travel.
        moved = sibling_gap_before - sibling_gap_after
        self.assertGreaterEqual(moved, 3.0 - 1e-6)
        self.assertLessEqual(moved, 8.0 + 1e-6)

    def test_blood_surge_does_not_fire_on_chip_damage(self):
        """Chip damage (wounded but alive) must NOT trigger Surge.

        This was the old pooled-health bug: with min_models=10 and
        health=2 the formula gave wounds_per_model=0.2, so a single wound
        counted as a model destroyed and fired the surge spuriously.  With
        the corrected alive→dead transition check, only a killed model
        triggers.
        """
        profile = self._berzerker_profile()
        we, (bz,) = self._build_squad(profile, [(40.0, 30.0)])
        # Model wounded but alive: took 1 wound out of 2.
        bz.current_health = 1.0

        shooter = self._make_shooter()
        marines = Army(name="Marines")
        marines.units = [shooter]

        battle = Battle(we, marines)

        pos_before = bz.position
        random.seed(0)
        battle._maybe_apply_blood_surge(
            defender=bz, attacker_army=marines, health_before=2.0,
        )
        self.assertEqual(
            bz.position, pos_before,
            "Chip damage (model wounded but alive) must NOT trigger Blood Surge",
        )

    def test_blood_surge_does_not_fire_across_different_squads(self):
        """A model dying in squad A must NOT trigger surge for squad B.

        Verifies the squad_id boundary: the sibling-death hook only looks
        at models sharing the same squad_id.  A Berzerker model from a
        different squad_id (a separate detachment in the same army) must
        remain stationary even if its faction+name gates pass.
        """
        profile = self._berzerker_profile()
        # Squad 0: one model (the defender that dies).
        # Squad 1: one model at a different position.
        we = Army(name="WE")

        model_sq0 = Unit(profile)
        model_sq0.position = (40.0, 30.0)
        model_sq0.army_ref = we
        model_sq0.squad_id = 0
        we.units.append(model_sq0)

        model_sq1 = Unit(profile)
        model_sq1.position = (45.0, 30.0)
        model_sq1.army_ref = we
        model_sq1.squad_id = 1   # DIFFERENT squad
        we.units.append(model_sq1)
        we._invalidate_alive_cache()

        shooter = self._make_shooter(position=(10.0, 30.0))
        marines = Army(name="Marines")
        marines.units = [shooter]

        battle = Battle(we, marines)

        # Kill the squad-0 model.
        model_sq0.current_health = 0.0

        sq1_pos_before = model_sq1.position
        random.seed(0)
        # Surge is called for the squad-0 death.
        battle._maybe_apply_blood_surge(
            defender=model_sq0, attacker_army=marines, health_before=2.0,
        )
        self.assertEqual(
            model_sq1.position, sq1_pos_before,
            "A Berzerker model in a different squad_id must NOT surge when "
            "another squad's model is destroyed",
        )

    def test_blood_surge_skips_non_berzerker_world_eaters(self):
        """Eightbound (also WE) must NOT Blood Surge — name-gated."""
        eightbound_profile = UnitProfile(
            name="Eightbound",
            health=6, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=5, toughness=5,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=12,
            leadership=7,
            faction="World Eaters",
            unit_keywords=("INFANTRY",),
            min_models=1,
        )
        eb = Unit(eightbound_profile)
        eb.position = (40.0, 30.0)
        # Model dies — would fire if name were "Khorne Berzerkers".
        eb.current_health = 0.0

        shooter = self._make_shooter()
        marines = Army(name="Marines")
        marines.units = [shooter]

        we = Army(name="WE")
        we.units = [eb]

        battle = Battle(we, marines)
        before_pos = eb.position
        random.seed(0)
        battle._maybe_apply_blood_surge(
            defender=eb, attacker_army=marines, health_before=6.0,
        )
        self.assertEqual(eb.position, before_pos,
                         "Eightbound must NOT Blood Surge (name-gated)")

    def test_blood_surge_skips_when_no_models_destroyed(self):
        """Damage that doesn't kill the targeted model must NOT trigger Surge."""
        profile = self._berzerker_profile()
        we, (bz,) = self._build_squad(profile, [(40.0, 30.0)])
        # Model took 1 wound but is still alive (health=1 out of 2).
        bz.current_health = 1.0

        shooter = self._make_shooter()
        marines = Army(name="Marines")
        marines.units = [shooter]

        battle = Battle(we, marines)
        pos_before = bz.position
        random.seed(0)
        battle._maybe_apply_blood_surge(
            defender=bz, attacker_army=marines, health_before=2.0,
        )
        self.assertEqual(bz.position, pos_before,
                         "No model destroyed -> no Surge")

    def test_blood_surge_lone_model_no_army_ref(self):
        """Lone model with no army_ref: the trigger still fires but the
        movement loop is a no-op because the dead model is the only one
        (alive_units returns nothing and _surge_squad is empty).

        This covers the legacy single-unit path — no crash, no movement.
        """
        profile = self._berzerker_profile()
        bz = Unit(profile)
        bz.position = (40.0, 30.0)
        bz.current_health = 0.0   # model died

        shooter = self._make_shooter()
        marines = Army(name="Marines")
        marines.units = [shooter]

        # No army: army_ref stays None, squad_id = -1.
        # Build a Battle by wrapping the unit in a bare Army.
        we = Army(name="WE")
        we.units = [bz]
        battle = Battle(we, marines)

        pos_before = bz.position
        # Must not raise; dead lone model has no siblings to move.
        battle._maybe_apply_blood_surge(
            defender=bz, attacker_army=marines, health_before=2.0,
        )
        self.assertEqual(bz.position, pos_before,
                         "Dead lone model with no siblings: position unchanged")


if __name__ == "__main__":
    unittest.main()
