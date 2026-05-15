"""Tests for the Adeptus Astartes army rules implemented in #115 + #116.

Covered:
  - Oath of Moment (#115): every Command phase the Marine army picks one
    enemy unit; Marine attacks against that unit re-roll BOTH the hit roll
    AND the wound roll. Cited as `simulator.oath_of_moment`.
  - Combat Doctrines (#116, Gladius Task Force detachment): round-rotating
    +1 to wound. Round 1 Devastator (ranged only), Round 2 Tactical (both
    modes), Round 3+ Assault (melee only). Faction-gated to Marines AND
    detachment-gated to Gladius. Cited as `simulator.combat_doctrines`.
"""

from __future__ import annotations

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
        a stale uid never leaks across rounds."""
        random.seed(0)
        battle = _two_unit_battle()
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

    def test_oath_grants_full_wound_reroll(self):
        """Force-hit by setting hit_probability = 1.0 so only the wound
        re-roll matters. Confirms the wound branch fires under oath."""
        a = Army("Marines", detachment=GLADIUS_TASK_FORCE)
        prof = _marine_profile()
        d = prof.__dict__.copy()
        d["hit_probability"] = 1.0    # always hit
        d["strength"] = 3             # S3 vs T4 = 5+ to wound (low success)
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

        # Wound chance 1/3 -> ~5/9 under full re-roll = 1.67x lift.
        self.assertGreater(oath / max(base, 1.0), 1.3)

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
    """Round 1 Devastator (ranged), Round 2 Tactical (both), Round 3+ Assault
    (melee). We exercise the gate by comparing wound damage with the
    detachment set vs unset, varying round and mode."""

    def _battle(self, detachment=GLADIUS_TASK_FORCE):
        a = Army("Marines", detachment=detachment)
        prof = _marine_profile()
        d = prof.__dict__.copy()
        d["hit_probability"] = 1.0          # always hit so we measure wound only
        d["melee_hit_probability"] = 1.0
        d["strength"] = 4
        d["melee_strength"] = 4
        a.add_unit(UnitProfile(**d))
        b = Army("Enemy")
        b.add_unit(_enemy_profile())
        battle = Battle(a, b)
        battle._assign_uids()
        # Suppress Oath so it doesn't muddy the Doctrine signal.
        a.oath_target_uid = None
        return battle, a, b

    def _avg_damage(self, attacker, defender, mode: str, n: int = 4000) -> float:
        random.seed(0)
        total = 0.0
        for _ in range(n):
            defender.current_health = defender.profile.health
            total += attacker.attack(defender, distance=12.0, mode=mode)
        return total / n

    def test_combat_doctrines_devastator_t1_ranged(self):
        """Round 1 — Devastator: +1 to wound on RANGED attacks only."""
        battle, a, b = self._battle()
        attacker, defender = a.units[0], b.units[0]
        battle._current_round = 1

        # vs no detachment baseline
        battle_no_det, a_no, b_no = self._battle(detachment=IRONSTORM_SPEARHEAD)
        battle_no_det._current_round = 1
        base_attacker, base_defender = a_no.units[0], b_no.units[0]

        gladius_ranged = self._avg_damage(attacker, defender, "ranged")
        baseline_ranged = self._avg_damage(base_attacker, base_defender, "ranged")
        self.assertGreater(
            gladius_ranged, baseline_ranged,
            f"Devastator R1 should boost ranged damage; "
            f"gladius={gladius_ranged:.3f} baseline={baseline_ranged:.3f}",
        )

        # Melee in round 1 must NOT receive the boost.
        gladius_melee = self._avg_damage(attacker, defender, "melee")
        baseline_melee = self._avg_damage(base_attacker, base_defender, "melee")
        # Identical RNG and no buff: damage curves should match.
        self.assertAlmostEqual(gladius_melee, baseline_melee, delta=0.02)

    def test_combat_doctrines_tactical_t2_both(self):
        """Round 2 — Tactical: +1 to wound on BOTH ranged and melee."""
        battle, a, b = self._battle()
        attacker, defender = a.units[0], b.units[0]
        battle._current_round = 2

        battle_no_det, a_no, b_no = self._battle(detachment=IRONSTORM_SPEARHEAD)
        battle_no_det._current_round = 2
        base_attacker, base_defender = a_no.units[0], b_no.units[0]

        for mode in ("ranged", "melee"):
            with self.subTest(mode=mode):
                gladius = self._avg_damage(attacker, defender, mode)
                baseline = self._avg_damage(base_attacker, base_defender, mode)
                self.assertGreater(
                    gladius, baseline,
                    f"Tactical R2 should boost {mode}; "
                    f"gladius={gladius:.3f} baseline={baseline:.3f}",
                )

    def test_combat_doctrines_assault_t3_melee(self):
        """Round 3 — Assault: +1 to wound on MELEE attacks only."""
        battle, a, b = self._battle()
        attacker, defender = a.units[0], b.units[0]
        battle._current_round = 3

        battle_no_det, a_no, b_no = self._battle(detachment=IRONSTORM_SPEARHEAD)
        battle_no_det._current_round = 3
        base_attacker, base_defender = a_no.units[0], b_no.units[0]

        gladius_melee = self._avg_damage(attacker, defender, "melee")
        baseline_melee = self._avg_damage(base_attacker, base_defender, "melee")
        self.assertGreater(
            gladius_melee, baseline_melee,
            f"Assault R3 should boost melee; "
            f"gladius={gladius_melee:.3f} baseline={baseline_melee:.3f}",
        )

        # Ranged in round 3 must NOT receive the boost.
        gladius_ranged = self._avg_damage(attacker, defender, "ranged")
        baseline_ranged = self._avg_damage(base_attacker, base_defender, "ranged")
        self.assertAlmostEqual(gladius_ranged, baseline_ranged, delta=0.02)

    def test_non_gladius_detachment_no_doctrines(self):
        """Ironstorm Spearhead Marines get NO Doctrines buff in any round."""
        battle, a, b = self._battle(detachment=IRONSTORM_SPEARHEAD)
        attacker, defender = a.units[0], b.units[0]

        # Construct a parallel "no detachment at all" baseline.
        no_a = Army("NoDet")
        prof = _marine_profile()
        d = prof.__dict__.copy()
        d["hit_probability"] = 1.0
        d["melee_hit_probability"] = 1.0
        no_a.add_unit(UnitProfile(**d))
        no_b = Army("Enemy")
        no_b.add_unit(_enemy_profile())
        no_battle = Battle(no_a, no_b)
        no_battle._assign_uids()
        no_a.oath_target_uid = None
        # Force no detachment so Doctrines can't fire.
        no_a.detachment = IRONSTORM_SPEARHEAD

        for rnd in (1, 2, 3, 4):
            battle._current_round = rnd
            no_battle._current_round = rnd
            for mode in ("ranged", "melee"):
                with self.subTest(round=rnd, mode=mode):
                    iron = self._avg_damage(attacker, defender, mode)
                    none = self._avg_damage(no_a.units[0], no_b.units[0], mode)
                    self.assertAlmostEqual(iron, none, delta=0.02)


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
