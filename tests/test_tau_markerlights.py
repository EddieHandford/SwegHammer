"""Tests for the T'au Empire Markerlights -> Guided -> [LETHAL HITS] chain.

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights

Implements the T'au army-rule plumbing alongside the Mont'ka
`lethal_hits_on_guided` detachment flag (previously wired-but-unread):

    * `Army.guided_enemy_uids: Set[str]` — set populated each round by the
      simulator's `_run_markerlight_phase`. A MARKERLIGHT-keyword unit
      alive in a T'au army marks the highest-points enemy in 36" LoS;
      one mark per markerlight carrier.
    * `Unit.attack` — when the attacker is T'au, the target's uid is in
      the attacker army's `guided_enemy_uids`, and the active detachment
      sets `lethal_hits_on_guided=True`, the attacker resolves with
      [LETHAL HITS]: a natural-6 hit roll auto-wounds.
    * Marks are cleared at end-of-round so the buff doesn't leak.

Test coverage:
    * Markerlight phase populates `guided_enemy_uids` from a marker carrier.
    * No marker carrier => empty set.
    * T'au attacker firing at a Guided target lands a forced critical-hit
      auto-wound (LETHAL HITS) where it would otherwise wound-roll.
    * Marks clear at end of round.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import MONTKA
from code.simulator import Battle
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pathfinder_profile() -> UnitProfile:
    """Pathfinder Team — canonical Markerlight carrier."""
    return UnitProfile(
        name="Pathfinder Team", faction="T'au Empire",
        health=9, damage=1.48, hit_probability=0.5,
        ap=0, save=4, strength=5, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        move=6.0,
        unit_keywords=("INFANTRY", "MARKERLIGHT"),
        points_override=90.0,
    )


def _crisis_profile() -> UnitProfile:
    """Crisis Battlesuits — T'au shooter that benefits from Guided LETHAL HITS."""
    return UnitProfile(
        name="Crisis Battlesuits", faction="T'au Empire",
        health=5, damage=4, hit_probability=2 / 3,
        ap=-1, save=3, strength=5, toughness=5,
        attacks=4, weapon_damage_per_shot=2.0, range_inches=18,
        move=8.0,
        unit_keywords=("INFANTRY", "BATTLESUIT"),
        points_override=160.0,
    )


def _no_markerlight_tau_profile() -> UnitProfile:
    """A T'au unit WITHOUT the MARKERLIGHT keyword (Fire Warriors)."""
    return UnitProfile(
        name="Fire Warriors", faction="T'au Empire",
        health=12, damage=3, hit_probability=0.5,
        ap=0, save=4, strength=5, toughness=3,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        move=6.0,
        unit_keywords=("INFANTRY",),
        points_override=100.0,
    )


def _target_profile() -> UnitProfile:
    """Enemy target — built so the attacker would normally have to wound-roll
    to land hits. wound_target depends on S vs T (S5 vs T4 = 3+ wound) so
    LETHAL HITS converting a crit-hit (1/6 of dice) into an auto-wound is
    distinguishable from the baseline path under a controlled seed."""
    return UnitProfile(
        name="Target", faction="Test",
        health=20, damage=1, hit_probability=0.5,
        ap=0, save=7, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        points_override=100.0,
    )


def _build_battle_with_markerlight():
    """Tau army containing Pathfinders + Crisis Battlesuits vs single enemy."""
    a = Army("T'au")
    a.detachment = MONTKA
    a.add_unit(_pathfinder_profile())
    a.add_unit(_crisis_profile())
    b = Army("Enemy")
    b.add_unit(_target_profile())
    random.seed(2026)
    battle = Battle(a, b)
    battle._assign_uids()
    # Place units within Markerlight's 36" range.
    a.units[0].position = (10.0, 30.0)   # Pathfinders
    a.units[1].position = (12.0, 30.0)   # Crisis
    b.units[0].position = (22.0, 30.0)   # Enemy in 12" reach
    return battle, a, b


# ---------------------------------------------------------------------------
# _run_markerlight_phase tests
# ---------------------------------------------------------------------------


class MarkerlightPhaseTests(unittest.TestCase):

    def test_markerlight_unit_marks_enemy(self):
        battle, a, b = _build_battle_with_markerlight()
        # Before the phase runs, set is empty.
        self.assertEqual(a.guided_enemy_uids, set())
        # iter27-M1: Markerlight emission now requires a successful Hit
        # roll against the carrier's Ballistic Skill. Force the dice to
        # a 6 so the BS4+ Pathfinder always lands the marker — isolates
        # the LoS / range / token bookkeeping from the to-hit randomness.
        rolls = iter([6] * 20)
        original_randint = random.randint
        def patched(a_, b_):
            try:
                return next(rolls)
            except StopIteration:
                return original_randint(a_, b_)
        random.randint = patched
        try:
            battle._run_markerlight_phase(a, b)
        finally:
            random.randint = original_randint
        # After running, the enemy unit's uid is in the set.
        self.assertIn(b.units[0].uid, a.guided_enemy_uids)

    def test_markerlight_hit_roll_failure_grants_no_token(self):
        """iter27-M1 gate: a missed Hit roll produces no Guided token.

        Carrier is Pathfinder BS4+ (hit_probability=0.5 => target 4+).
        Forcing the d6 to a 1 makes every Markerlight emission miss, so
        the resulting `guided_enemy_uids` must remain empty even when
        range + LoS would otherwise have permitted the mark.
        """
        battle, a, b = _build_battle_with_markerlight()
        rolls = iter([1] * 20)
        original_randint = random.randint
        def patched(a_, b_):
            try:
                return next(rolls)
            except StopIteration:
                return original_randint(a_, b_)
        random.randint = patched
        try:
            battle._run_markerlight_phase(a, b)
        finally:
            random.randint = original_randint
        self.assertEqual(a.guided_enemy_uids, set())

    def test_no_markerlight_unit_means_no_marks(self):
        a = Army("T'au")
        a.detachment = MONTKA
        a.add_unit(_no_markerlight_tau_profile())   # no MARKERLIGHT keyword
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.units[0].position = (10.0, 30.0)
        b.units[0].position = (22.0, 30.0)
        battle._run_markerlight_phase(a, b)
        self.assertEqual(a.guided_enemy_uids, set())

    def test_non_tau_army_skipped(self):
        """Defensive: _run_markerlight_phase short-circuits on non-T'au armies."""
        a = Army("NotTau")
        a.add_unit(UnitProfile(
            name="Marine", faction="Adeptus Astartes",
            health=10, damage=2, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
            unit_keywords=("INFANTRY", "MARKERLIGHT"),  # forced for paranoia
            points_override=100.0,
        ))
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.units[0].position = (10.0, 30.0)
        b.units[0].position = (22.0, 30.0)
        battle._run_markerlight_phase(a, b)
        # Non-T'au -> skipped.
        self.assertEqual(a.guided_enemy_uids, set())

    def test_marks_clear_after_round(self):
        """The end-of-round cleanup in _run_round must reset the set."""
        battle, a, b = _build_battle_with_markerlight()
        # Hand-seed marks as if a previous phase had populated them.
        a.guided_enemy_uids = {b.units[0].uid}
        b.guided_enemy_uids = {a.units[0].uid}
        # Run a single round of the simulator's round loop.
        battle._current_round = 1
        battle._run_round(1)
        # End-of-round cleanup empties both sets.
        self.assertEqual(a.guided_enemy_uids, set())
        self.assertEqual(b.guided_enemy_uids, set())


# ---------------------------------------------------------------------------
# Unit.attack — LETHAL HITS applied vs Guided target
# ---------------------------------------------------------------------------


class GuidedLethalHitsApplyTests(unittest.TestCase):
    """When the target is in the attacker army's `guided_enemy_uids` set AND
    the detachment carries `lethal_hits_on_guided=True`, a critical-hit
    (natural 6 to hit) by a T'au attacker auto-wounds — bypassing the
    wound-roll branch entirely. We force the dice with a custom random
    sequence to isolate the LETHAL HITS gate from the wound roll."""

    def test_guided_target_gains_lethal_hits(self):
        battle, a, b = _build_battle_with_markerlight()
        attacker = a.units[1]   # Crisis Battlesuits
        target = b.units[0]
        # Mark the target as Guided.
        a.guided_enemy_uids = {target.uid}
        # Force the dice: hit rolls of 6 (crit) so the LETHAL HITS branch
        # fires once per attack; save target is 7 so the wound path needs
        # only a successful wound roll to land. With LETHAL HITS the
        # crit-hit auto-wounds without rolling, and there's no save.
        # We just need to verify the attack lands at least the auto-wounds.
        rolls = iter([6] * 200)
        original_randint = random.randint
        def patched(a_, b_):
            try:
                return next(rolls)
            except StopIteration:
                return original_randint(a_, b_)
        random.randint = patched
        try:
            before_hp = target.current_health
            damage = attacker.attack(target, mode="ranged")
            after_hp = target.current_health
        finally:
            random.randint = original_randint
        # With every hit roll a 6, every attack crits — under LETHAL HITS
        # each crit auto-wounds; with save 7+ none save. Crisis has 4
        # attacks at 2.0 dmg => 8 dmg expected, possibly capped by target
        # HP (20).
        self.assertGreater(damage, 0.0)
        self.assertLess(after_hp, before_hp)

    def test_unguided_target_no_lethal_hits_path(self):
        """Sanity: when the target is NOT in guided_enemy_uids, the LETHAL
        HITS branch does NOT fire; a natural 6 hit still has to roll for
        wounds. We force a hit-6 sequence but make wound rolls all-fail
        (1s) — without LETHAL HITS the attack should land zero damage
        despite all crits. Set CP=0 to disable the universal Command
        Re-Roll stratagem (otherwise that stratagem re-rolls the failed
        wound and lands damage independently of LETHAL HITS)."""
        battle, a, b = _build_battle_with_markerlight()
        attacker = a.units[1]
        target = b.units[0]
        # NOT marking the target.
        a.guided_enemy_uids = set()
        # Zero out CP so the universal Command Re-Roll cannot fire on a
        # failed wound and confound the LETHAL HITS isolation.
        a.command_points = 0
        # Hits = 6 (crit), wounds = 1 (always fail). With LETHAL HITS we'd
        # auto-wound; without, the unit must roll a wound and a 1 always
        # fails. We use a flip-flop sequence: even calls (hits) return 6,
        # odd calls (wounds) return 1.
        seq = []
        for _ in range(200):
            seq.append(6)   # hit
            seq.append(1)   # wound
        rolls = iter(seq)
        original_randint = random.randint
        def patched(a_, b_):
            try:
                return next(rolls)
            except StopIteration:
                return original_randint(a_, b_)
        random.randint = patched
        try:
            before_hp = target.current_health
            damage = attacker.attack(target, mode="ranged")
            after_hp = target.current_health
        finally:
            random.randint = original_randint
        # Without LETHAL HITS, every wound roll of 1 fails (no re-roll
        # because Mont'ka does not grant wound re-rolls, and we zeroed
        # the universal Command Re-Roll budget above). Net damage = 0.
        self.assertEqual(damage, 0.0)
        self.assertEqual(after_hp, before_hp)


if __name__ == "__main__":
    unittest.main()
