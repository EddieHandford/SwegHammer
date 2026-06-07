"""Tests for the Adeptus Astartes army rules implemented in #115 + #116.

Covered:
  - Oath of Moment (#115): every Command phase the Marine army picks one
    enemy unit; Marine attacks against that unit re-roll BOTH the hit roll
    AND the wound roll. Cited as `simulator.oath_of_moment`.
  - Combat Doctrines (#116, Gladius Task Force detachment), as corrected in
    iter-9 audit (May 2026): round-rotating MOVEMENT UTILITY (no damage
    buff). R1 Devastator: shoot after Advance. R2 Tactical: shoot AND
    charge after Fall Back. R3+ Assault: charge after Advance. Faction-gated
    to Marines AND detachment-gated to Gladius. Cited as
    `simulator.combat_doctrines`.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.detachments import GLADIUS_TASK_FORCE, IRONSTORM_SPEARHEAD
from code.events import EventLog, OathTargetChosen
from code.factions import is_marine_faction, MARINE_FACTIONS
from code.simulator import Battle
from code.units import UnitProfile


def _marine_profile(
    name: str = "Tactical Marine",
    faction: str = "Adeptus Astartes",
    points: float = 100.0,
) -> UnitProfile:
    """A Marine stand-in. Ranged S4 AP0 + melee S4 AP0 so a baseline
    wound roll vs T4 lands on 4+ — leaving plenty of headroom for the
    Doctrines +1-to-wound test to bite. We pin per-model points via the
    Sweg-balancer override (`points_override > 0` shortcircuits the
    derived `points_cost` property)."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=6,
        faction=faction,
        points_override=float(points),
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _enemy_profile(name: str = "Cultist", points: float = 50.0) -> UnitProfile:
    """Non-Marine target. T4 keeps wound math on the 4+ knife-edge so the
    Doctrines +1 buff visibly shifts kill rate."""
    return UnitProfile(
        name=name,
        health=1, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7,
        faction="Chaos Space Marines",
        points_override=float(points),
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
    )


def _two_unit_battle(
    a_faction: str = "Adeptus Astartes",
    a_detachment=GLADIUS_TASK_FORCE,
    enemy_points: int = 200,
) -> Battle:
    a = Army("Marines", detachment=a_detachment)
    a.add_unit(_marine_profile(faction=a_faction))
    b = Army("Enemy")
    b.add_unit(_enemy_profile(points=enemy_points))
    battle = Battle(a, b)
    battle._assign_uids()
    return battle


# ---------------------------------------------------------------------------
# Marine umbrella — is_marine_faction
# ---------------------------------------------------------------------------


class MarineUmbrellaTests(unittest.TestCase):
    """Every chapter codex resolves as a Marine for army-rule purposes."""

    def test_marine_umbrella_factions_all_eligible(self):
        # Spot-check the headline chapters listed in CLAUDE.md / brief.
        for f in (
            "Adeptus Astartes", "Ultramarines", "Blood Angels", "Dark Angels",
            "Black Templars", "Space Wolves", "Imperial Fists", "Iron Hands",
            "Raven Guard", "Salamanders", "White Scars", "Deathwatch",
        ):
            with self.subTest(faction=f):
                self.assertTrue(is_marine_faction(f), f"{f} should be Marine")

    def test_non_marine_factions_not_eligible(self):
        # Grey Knights have their own army rule and are deliberately
        # excluded; Sisters / Custodes / Chaos / Xenos are obvious nopes.
        for f in (
            "Grey Knights", "Adepta Sororitas", "Adeptus Custodes",
            "Chaos Space Marines", "Necrons", "Orks", "Tyranids",
            "Adeptus Mechanicus", "Death Guard", "Aeldari",
        ):
            with self.subTest(faction=f):
                self.assertFalse(is_marine_faction(f), f"{f} must not be Marine")

    def test_marine_factions_constant_matches_helper(self):
        # The frozenset and the helper agree.
        for f in MARINE_FACTIONS:
            self.assertTrue(is_marine_faction(f))


# ---------------------------------------------------------------------------
# Oath of Moment — Command-phase target picker
# ---------------------------------------------------------------------------


class OathTargetPickerTests(unittest.TestCase):
    """Battle._pick_oath_target writes army.oath_target_uid and emits
    OathTargetChosen at the start of every Command phase."""

    def setUp(self):
        # command-phase scoring is now default-ON; this mechanic test uses the legacy timing
        os.environ["SWEG_CMDSCORE"] = "0"
        # collision is now default-ON; test_oath_picks_highest_points_enemy
        # tests target-picking geometry, not collision movement
        os.environ["SWEG_COLLISION"] = "0"

    def tearDown(self):
        os.environ.pop("SWEG_CMDSCORE", None)
        os.environ.pop("SWEG_COLLISION", None)

    def test_oath_target_chosen_in_command_phase(self):
        random.seed(0)
        battle = _two_unit_battle()
        log = EventLog()
        battle.subscribers.append(log)
        # Drive _run_round directly so we don't need a full Battle.run.
        battle._run_round(1)
        # Marines side should have an oath target stored.
        self.assertIsNotNone(battle.a.oath_target_uid)
        # The enemy side has no Marine units, so its oath_target_uid stays None.
        self.assertIsNone(battle.b.oath_target_uid)
        # Exactly one OathTargetChosen event for the Marine side.
        events = [e for e in log.events if isinstance(e, OathTargetChosen)]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].army_name, "Marines")
        self.assertEqual(events[0].round_num, 1)

    def test_oath_picks_highest_points_enemy(self):
        random.seed(0)
        a = Army("Marines", detachment=GLADIUS_TASK_FORCE)
        a.add_unit(_marine_profile())
        b = Army("Enemy")
        b.add_unit(_enemy_profile(name="Cheap", points=50))
        b.add_unit(_enemy_profile(name="Expensive", points=300))
        battle = Battle(a, b)
        battle._assign_uids()
        battle._run_round(1)
        # The expensive enemy is uid #1 in army b; either way the picked
        # uid must match the highest-points alive enemy.
        expensive = max(b.alive_units, key=lambda u: u.profile.points_cost)
        self.assertEqual(battle.a.oath_target_uid, expensive.uid)

    def test_oath_target_repicked_each_round(self):
        """The oath_target_uid resets at the start of every Command phase —
        a stale uid never leaks across rounds. Enemy is a Custodes-grade
        bricks (health=20) so it survives round 1 and remains the natural
        re-pick in round 2 — without the survivability buffer the now-real
        Devastator Doctrine lets the Marine actually shoot after Advancing
        and one-shot the test target."""
        random.seed(0)
        a = Army("Marines", detachment=GLADIUS_TASK_FORCE)
        a.add_unit(_marine_profile())
        b = Army("Enemy")
        # Beefy enemy that absorbs R1 fire so oath target persists into R2.
        enemy = _enemy_profile(points=200)
        ed = enemy.__dict__.copy()
        ed["health"] = 20
        b.add_unit(UnitProfile(**ed))
        battle = Battle(a, b)
        battle._assign_uids()
        battle._run_round(1)
        first = battle.a.oath_target_uid
        # Inject a sentinel value to simulate a stale uid, then run round 2.
        battle.a.oath_target_uid = "STALE"
        battle._run_round(2)
        # _run_round resets to None before re-picking, so the sentinel is gone.
        self.assertNotEqual(battle.a.oath_target_uid, "STALE")
        self.assertEqual(battle.a.oath_target_uid, first)


# ---------------------------------------------------------------------------
# Oath of Moment — re-roll application in Unit.attack
# ---------------------------------------------------------------------------


class OathRerollTests(unittest.TestCase):
    """Oath of Moment grants full re-roll on hits AND wounds against the
    chosen target. We exercise the gate by comparing attack damage with /
    without the oath uid pointing at the defender."""

    def _setup(self, faction: str = "Adeptus Astartes"):
        a = Army("Marines", detachment=GLADIUS_TASK_FORCE)
        # Use a low-hit profile so re-rolls bite hard. Override hit_probability
        # to 0.5 (4+ to hit) for visible variance vs baseline.
        prof = _marine_profile(faction=faction)
        prof_dict = prof.__dict__.copy()
        prof_dict["hit_probability"] = 0.5
        a.add_unit(UnitProfile(**prof_dict))
        b = Army("Enemy")
        b.add_unit(_enemy_profile())
        battle = Battle(a, b)
        battle._assign_uids()
        battle._current_round = 5   # Round 5: Assault melee-only, so ranged
                                    # mode in this test gets no Doctrine
                                    # interference — Oath is the only buff.
        return battle, a, b

    def test_oath_grants_full_hit_reroll(self):
        """With oath active the Marine's expected ranged damage is strictly
        higher than without. We accumulate over many independent rolls."""
        battle, a, b = self._setup()
        attacker = a.units[0]
        defender = b.units[0]

        # Baseline (no oath): empty target uid.
        a.oath_target_uid = None
        random.seed(0)
        n_trials = 4000
        baseline_dmg = 0.0
        for _ in range(n_trials):
            defender.current_health = defender.profile.health
            baseline_dmg += attacker.attack(defender, distance=12.0, mode="ranged")

        # With oath: uid matches defender.
        a.oath_target_uid = defender.uid
        random.seed(0)
        oath_dmg = 0.0
        for _ in range(n_trials):
            defender.current_health = defender.profile.health
            oath_dmg += attacker.attack(defender, distance=12.0, mode="ranged")

        self.assertGreater(
            oath_dmg, baseline_dmg,
            f"Oath should boost damage; baseline={baseline_dmg:.1f}, "
            f"oath={oath_dmg:.1f}",
        )
        # Expected lift: hit chance 0.5 -> 0.75 (full re-roll), wound chance
        # 0.5 -> 0.75 (full re-roll). Combined hit*wound: 0.25 -> 0.5625, a
        # ~2.25x lift. Even with stochastic noise the ratio should clearly
        # exceed 1.5x.
        self.assertGreater(oath_dmg / max(baseline_dmg, 1.0), 1.5)

    def test_oath_grants_hit_reroll(self):
        """Oath of Moment grants re-roll of failed Hit rolls only (codex
        verbatim: 'you can re-roll the Hit roll'). Updated in the SC5-9 audit
        after the prior implementation that set att_reroll_all_wounds was
        corrected — the wound re-roll was a fabrication.

        This test uses hit_probability=0.5 (3+ equivalent miss rate) so the
        hit-reroll is meaningful: baseline hit chance 0.5, oath hit chance
        0.75 (full re-roll of failures). With wound at 0.5 (S4 vs T4 = 4+),
        baseline damage-per-attack is 0.25, oath is 0.375 — a 1.5x lift.
        The test checks ratio > 1.2 (ample margin for 4 000-trial noise)."""
        a = Army("Marines", detachment=GLADIUS_TASK_FORCE)
        prof = _marine_profile()
        d = prof.__dict__.copy()
        d["hit_probability"] = 0.5    # 3+ equivalent — miss half the time
        d["strength"] = 4             # S4 vs T4 = 4+ to wound (50% success)
        a.add_unit(UnitProfile(**d))
        b = Army("Enemy")
        b.add_unit(_enemy_profile())
        battle = Battle(a, b)
        battle._assign_uids()
        battle._current_round = 5     # Assault melee-only, ranged unaffected

        attacker = a.units[0]
        defender = b.units[0]

        n_trials = 4000
        a.oath_target_uid = None
        random.seed(0)
        base = 0.0
        for _ in range(n_trials):
            defender.current_health = defender.profile.health
            base += attacker.attack(defender, distance=12.0, mode="ranged")

        a.oath_target_uid = defender.uid
        random.seed(0)
        oath = 0.0
        for _ in range(n_trials):
            defender.current_health = defender.profile.health
            oath += attacker.attack(defender, distance=12.0, mode="ranged")

        # Hit chance 0.5 -> 0.75 under full re-roll = 1.5x hit lift.
        # With 50% wound chance: 0.25 -> 0.375 damage-per-attack, ratio 1.5.
        # Threshold 1.2 gives ample headroom for 4 000-trial stochastic noise.
        self.assertGreater(oath / max(base, 1.0), 1.2)

    def test_oath_does_not_fire_on_non_oath_target(self):
        """Oath uid is for a different defender — no re-roll, no damage lift."""
        a = Army("Marines", detachment=GLADIUS_TASK_FORCE)
        prof = _marine_profile()
        d = prof.__dict__.copy()
        d["hit_probability"] = 0.5
        a.add_unit(UnitProfile(**d))
        b = Army("Enemy")
        b.add_unit(_enemy_profile(name="Oath Target"))
        b.add_unit(_enemy_profile(name="Other"))
        battle = Battle(a, b)
        battle._assign_uids()
        battle._current_round = 5
        attacker = a.units[0]
        oath_tgt = b.units[0]
        other = b.units[1]

        # Point oath at oath_tgt but ATTACK other — no re-roll should fire.
        a.oath_target_uid = oath_tgt.uid

        n_trials = 4000
        random.seed(0)
        oath_off = 0.0
        a.oath_target_uid = None
        for _ in range(n_trials):
            other.current_health = other.profile.health
            oath_off += attacker.attack(other, distance=12.0, mode="ranged")

        a.oath_target_uid = oath_tgt.uid
        random.seed(0)
        oath_on_but_wrong_tgt = 0.0
        for _ in range(n_trials):
            other.current_health = other.profile.health
            oath_on_but_wrong_tgt += attacker.attack(
                other, distance=12.0, mode="ranged",
            )

        # Identical RNG seed + identical re-roll gates ⇒ identical damage.
        self.assertEqual(oath_off, oath_on_but_wrong_tgt)


# ---------------------------------------------------------------------------
# Combat Doctrines — round + mode gating
# ---------------------------------------------------------------------------


class CombatDoctrinesTests(unittest.TestCase):
    """R1 Devastator (shoot after Advance), R2 Tactical (shoot + charge
    after Fall Back), R3+ Assault (charge after Advance). The real rules
    are MOVEMENT-UTILITY EXEMPTIONS to the 10e core lockouts — there is no
    damage buff. We exercise the helper Battle._gladius_active_doctrine
    directly and check the matching lockout bypass in _do_shoot / _do_charge.
    """

    def _make(self, detachment=GLADIUS_TASK_FORCE, faction="Adeptus Astartes"):
        a = Army("Marines", detachment=detachment)
        a.add_unit(_marine_profile(faction=faction))
        b = Army("Enemy")
        b.add_unit(_enemy_profile(points=200))
        battle = Battle(a, b)
        battle._assign_uids()
        a.oath_target_uid = None
        return battle, a, b

    def test_doctrine_rotation_by_round(self):
        """Devastator R1, Tactical R2, Assault R3+ for Gladius Marines."""
        battle, a, _b = self._make()
        attacker = a.units[0]
        for rnd, expected in ((1, "Devastator"), (2, "Tactical"),
                              (3, "Assault"), (4, "Assault"), (5, "Assault")):
            battle._current_round = rnd
            with self.subTest(round=rnd):
                self.assertEqual(
                    battle._gladius_active_doctrine(attacker, a), expected,
                )

    def test_doctrine_off_for_non_marine_faction(self):
        """Doctrine helper returns '' for non-Marine factions even in a
        Gladius detachment army."""
        battle, a, _b = self._make(faction="Chaos Space Marines")
        attacker = a.units[0]
        battle._current_round = 1
        self.assertEqual(battle._gladius_active_doctrine(attacker, a), "")

    def test_doctrine_off_for_non_gladius_detachment(self):
        """Ironstorm Spearhead Marines get no Doctrines."""
        battle, a, _b = self._make(detachment=IRONSTORM_SPEARHEAD)
        attacker = a.units[0]
        for rnd in (1, 2, 3, 4):
            battle._current_round = rnd
            with self.subTest(round=rnd):
                self.assertEqual(
                    battle._gladius_active_doctrine(attacker, a), "",
                )

    def test_devastator_r1_shoot_after_advance(self):
        """R1 Devastator: Marine unit that Advanced may still shoot.
        Without the doctrine, the Advance lockout in _do_shoot would
        prevent the activation. We assert the shoot path NOT-returns
        by checking that UnitShot fires."""
        from code.events import UnitShot
        battle, a, b = self._make()
        battle._current_round = 1
        attacker = a.units[0]
        defender = b.units[0]
        # Place units in range; mark Marine as Advanced.
        attacker.position = (0.0, 0.0)
        defender.position = (10.0, 0.0)
        battle._advanced_this_round.add(attacker.uid)
        log = EventLog()
        battle.subscribers.append(log)
        battle._do_shoot(attacker, a, b)
        shots = [e for e in log.events if isinstance(e, UnitShot)]
        self.assertGreater(len(shots), 0, "Devastator should permit shoot-after-Advance")

    def test_no_devastator_no_shoot_after_advance(self):
        """Without Gladius (Ironstorm), Advance lockout still blocks shooting."""
        from code.events import UnitShot
        battle, a, b = self._make(detachment=IRONSTORM_SPEARHEAD)
        battle._current_round = 1
        attacker = a.units[0]
        defender = b.units[0]
        attacker.position = (0.0, 0.0)
        defender.position = (10.0, 0.0)
        battle._advanced_this_round.add(attacker.uid)
        log = EventLog()
        battle.subscribers.append(log)
        battle._do_shoot(attacker, a, b)
        shots = [e for e in log.events if isinstance(e, UnitShot)]
        self.assertEqual(len(shots), 0, "Ironstorm Marines must not shoot after Advance")

    def test_tactical_r2_shoot_after_fall_back(self):
        """R2 Tactical: Marine unit that Fell Back may still shoot."""
        from code.events import UnitShot
        battle, a, b = self._make()
        battle._current_round = 2
        attacker = a.units[0]
        defender = b.units[0]
        attacker.position = (0.0, 0.0)
        defender.position = (10.0, 0.0)
        attacker.fell_back_this_round = True
        log = EventLog()
        battle.subscribers.append(log)
        battle._do_shoot(attacker, a, b)
        shots = [e for e in log.events if isinstance(e, UnitShot)]
        self.assertGreater(len(shots), 0, "Tactical should permit shoot-after-Fall-Back")


class MarineUmbrellaIntegrationTests(unittest.TestCase):
    """Blood Angels and Dark Angels (and any Marine chapter) must benefit
    from Oath of Moment and Combat Doctrines just like vanilla Astartes."""

    def test_blood_angels_inherit_oath(self):
        random.seed(0)
        battle = _two_unit_battle(a_faction="Blood Angels")
        battle._run_round(1)
        self.assertIsNotNone(battle.a.oath_target_uid)

    def test_dark_angels_inherit_oath(self):
        random.seed(0)
        battle = _two_unit_battle(a_faction="Dark Angels")
        battle._run_round(1)
        self.assertIsNotNone(battle.a.oath_target_uid)


if __name__ == "__main__":
    unittest.main()
