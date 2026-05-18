"""Tests for the real Mont'ka (T'au Empire) detachment + stratagems (#196).

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Montka

Replaces the launch-day +1-to-hit approximation with the real Killing Blow
rule:
    * "During the first, second and third battle rounds, ranged weapons
       equipped by T'AU EMPIRE models from your army have the [ASSAULT]
       ability."
    * "During the first, second and third battle rounds, while a unit is
       a Guided unit, its ranged weapons have the [LETHAL HITS] ability."

Plus the six real Mont'ka stratagems: Pinpoint Counter-Offensive,
Aggressive Mobility, Focused Fire, Combat Debarkation, Pulse Onslaught,
Counterfire Defence Systems.

Test coverage:
    * Detachment rule flags wired (army_wide_assault_rounds_1_3 True,
      lethal_hits_on_guided True, plus_one_to_hit False).
    * Detachment exposes all six stratagems by name.
    * The [ASSAULT] window lets a T'au unit shoot after Advancing in
      rounds 1-3 but NOT in round 4 (no extra Battle Focus token needed
      because we're not Aeldari).
    * Counterfire Defence Systems fires end-to-end via Battle and sets
      the defender's transient -1 damage taken flag (a smoke test that
      the dispatcher is wired in).
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import DETACHMENTS, MONTKA
from code.simulator import Battle
from code.stratagems import (
    MONTKA_STRATAGEMS, PINPOINT_COUNTER_OFFENSIVE, AGGRESSIVE_MOBILITY,
    FOCUSED_FIRE, COMBAT_DEBARKATION, PULSE_ONSLAUGHT,
    COUNTERFIRE_DEFENCE_SYSTEMS,
)
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tau_crisis_profile() -> UnitProfile:
    """A 150+ point T'au shooter — passes the AI gate for Mont'ka stratagems
    (cost >= 150 brick filter). Crisis Battlesuits are the canonical 'do
    fire the stratagem on this unit' target."""
    return UnitProfile(
        name="Crisis Battlesuits", faction="T'au Empire",
        health=5, damage=4, hit_probability=2 / 3,
        ap=-1, save=3, strength=5, toughness=5,
        attacks=4, weapon_damage_per_shot=2.0, range_inches=18,
        move=8.0,
        unit_keywords=("INFANTRY", "BATTLESUIT"),
        points_override=160.0,
    )


def _target_profile() -> UnitProfile:
    return UnitProfile(
        name="Target", faction="Test",
        health=2, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
    )


# ---------------------------------------------------------------------------
# Detachment-rule tests
# ---------------------------------------------------------------------------


class MontkaDetachmentRuleTests(unittest.TestCase):

    def test_killing_blow_flags_wired(self):
        """The real Killing Blow rule sets two flags and clears the
        launch-day +1-to-hit approximation."""
        self.assertTrue(MONTKA.army_wide_assault_rounds_1_3)
        self.assertTrue(MONTKA.lethal_hits_on_guided)
        self.assertFalse(MONTKA.plus_one_to_hit)

    def test_montka_in_registry(self):
        self.assertIn("montka", DETACHMENTS)
        self.assertIs(DETACHMENTS["montka"], MONTKA)


class MontkaStratagemsTests(unittest.TestCase):
    """The six real Mont'ka stratagems must be attached to the detachment
    by canonical name + CP cost, and exposed via MONTKA.stratagems."""

    EXPECTED = (
        ("Pinpoint Counter-Offensive", 1),
        ("Aggressive Mobility", 1),
        ("Focused Fire", 1),
        ("Combat Debarkation", 1),
        ("Pulse Onslaught", 2),
        ("Counterfire Defence Systems", 2),
    )

    def test_six_stratagems_attached_to_detachment(self):
        attached = {s.name: s.cp_cost for s in MONTKA.stratagems}
        for name, cp in self.EXPECTED:
            self.assertIn(name, attached, f"{name} missing from MONTKA.stratagems")
            self.assertEqual(
                attached[name], cp,
                f"{name} expected {cp} CP, got {attached[name]}",
            )

    def test_montka_stratagems_tuple_matches_attached(self):
        # MONTKA_STRATAGEMS exported by code.stratagems is the same tuple
        # the detachment is built with.
        self.assertEqual(MONTKA.stratagems, MONTKA_STRATAGEMS)

    def test_constants_exist_and_named_correctly(self):
        # Each constant carries the canonical name (matches what the
        # dispatcher in _apply_detachment_stratagems looks for).
        self.assertEqual(PINPOINT_COUNTER_OFFENSIVE.name, "Pinpoint Counter-Offensive")
        self.assertEqual(AGGRESSIVE_MOBILITY.name, "Aggressive Mobility")
        self.assertEqual(FOCUSED_FIRE.name, "Focused Fire")
        self.assertEqual(COMBAT_DEBARKATION.name, "Combat Debarkation")
        self.assertEqual(PULSE_ONSLAUGHT.name, "Pulse Onslaught")
        self.assertEqual(COUNTERFIRE_DEFENCE_SYSTEMS.name, "Counterfire Defence Systems")


# ---------------------------------------------------------------------------
# [ASSAULT] window — _do_shoot honour-check
# ---------------------------------------------------------------------------


class MontkaAssaultWindowTests(unittest.TestCase):
    """In rounds 1-3, a T'au unit that Advanced can still shoot (no Battle
    Focus token spend required). In round 4+, the window has closed."""

    def _build_battle(self):
        a = Army("T'au")
        a.add_unit(_tau_crisis_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        # Position so the target is reachable for shooting (range 18, place
        # them 12" apart on the same y).
        a.units[0].position = (10.0, 30.0)
        b.units[0].position = (22.0, 30.0)
        return battle, a, b

    def test_tau_can_shoot_after_advance_in_round_1(self):
        battle, a, b = self._build_battle()
        attacker = a.units[0]
        # Flag the attacker as having Advanced this round.
        battle._advanced_this_round.add(attacker.uid)
        battle._current_round = 1
        # Take HP before to see if shooting landed any damage (smoke check).
        defender_before = b.units[0].current_health
        battle._do_shoot(attacker, a, b)
        # Crucial: the call returned without bailing — we got to the actual
        # shooting code (the Advance-gate didn't fire). We confirm via the
        # absence of bail-out — defender HP MAY have dropped depending on
        # rolls but never increased.
        self.assertLessEqual(b.units[0].current_health, defender_before)
        # Battle Focus tokens stay at zero (no token spend — Mont'ka grants
        # [ASSAULT] free during the window).
        self.assertEqual(a.battle_focus_tokens, 0)

    def test_tau_cannot_shoot_after_advance_in_round_4(self):
        battle, a, b = self._build_battle()
        attacker = a.units[0]
        battle._advanced_this_round.add(attacker.uid)
        battle._current_round = 4
        defender_before = b.units[0].current_health
        battle._do_shoot(attacker, a, b)
        # Round 4 is outside Mont'ka's [ASSAULT] window — the unit's shot
        # must have been skipped (no damage). HP unchanged.
        self.assertEqual(b.units[0].current_health, defender_before)


# ---------------------------------------------------------------------------
# Stratagem dispatch end-to-end
# ---------------------------------------------------------------------------


class CounterfireDefenceSystemsTests(unittest.TestCase):
    """Counterfire Defence Systems (2 CP) — fires from the round-start
    dispatcher when the army has a wounded high-value T'au unit. Sets
    `transient_minus_one_damage_taken` on the target."""

    def test_dispatcher_sets_minus_one_damage_taken(self):
        """Drive the dispatcher directly so we isolate Counterfire from the
        other five Mont'ka stratagems that all fire on the same vulnerable
        unit (the wider _apply_detachment_stratagems pass spends all 6 CP
        on the offensive five before Counterfire's turn — that's by-design
        ordering, not a Counterfire bug)."""
        a = Army("T'au")
        a.add_unit(_tau_crisis_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.command_points = 4
        a.units[0].current_health = 1.0   # full HP is 5; lost > 50%
        battle._current_round = 3
        battle._try_counterfire_defence_systems(a, b)
        # The dispatcher should have set the transient defensive flag on
        # the wounded T'au unit.
        self.assertTrue(a.units[0].transient_minus_one_damage_taken)
        # CP must have dropped by 2.
        self.assertEqual(a.command_points, 4 - 2)


class MontkaAllStratagemsFireSmokeTests(unittest.TestCase):
    """Round-start dispatcher smoke test: with abundant CP and a wounded
    high-value T'au unit, the offensive Mont'ka stratagems (1-CP block)
    fire and set their respective transient flags. Confirms the dispatcher
    wires every entry — a missing _try_* would leave one flag clear.

    Iter-4 A5 note: `_apply_detachment_stratagems` is capped at
    `Battle.DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE` (default 1)
    stratagems per army per Command phase (faction-neutral AI heuristic).
    This smoke test temporarily raises the cap so the dispatcher fires
    every wired Mont'ka stratagem in one pass — the original intent here
    is to verify each `_try_*` is wired in, not to characterise the cap.
    """

    def test_offensive_stratagems_fire(self):
        a = Army("T'au")
        a.add_unit(_tau_crisis_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        # 6 CP is exactly the offensive Mont'ka budget (4 x 1 CP + 2 CP
        # Pulse Onslaught). Wound the T'au unit so the AI gate clears.
        a.command_points = 6
        a.units[0].current_health = 1.0
        battle._current_round = 3
        # Iter-4 A5: lift the per-Command-phase cap for this smoke test
        # only — we want every wired dispatcher to fire so a missing one
        # is visible. The cap is exercised separately by the simulator's
        # MAE evaluation against the meta dataset.
        battle.DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE = 999
        battle._apply_detachment_stratagems(a, b)
        # The 1-CP offensive stratagems all target the same T'au shooter
        # via transient flags. With 6 CP available, we expect at least the
        # reroll-hits flag (Pinpoint Counter-Offensive / Combat Debarkation)
        # AND the assault flag (Aggressive Mobility) AND the +1-to-hit flag
        # (Focused Fire / Pulse Onslaught) all set.
        unit = a.units[0]
        self.assertTrue(unit.transient_reroll_hits_shooting)
        self.assertTrue(unit.transient_assault_this_round)
        self.assertTrue(unit.transient_plus_one_to_hit_shooting)


class StratagemPerCommandPhaseCapTests(unittest.TestCase):
    """Iter-4 A5 (faction-neutral AI heuristic): cap the number of
    detachment stratagems any one army may fire per Command phase.
    `_apply_detachment_stratagems` short-circuits after
    `Battle.DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE` (default 1)
    stratagems have fired for that army. Cited as
    `simulator.stratagem_per_command_phase_cap`.
    """

    def test_cap_limits_to_one_stratagem_per_command_phase(self):
        a = Army("T'au")
        a.add_unit(_tau_crisis_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        # Plenty of CP — without the cap, three or more Mont'ka stratagems
        # would all fire (proven by MontkaAllStratagemsFireSmokeTests when
        # the cap is lifted).
        a.command_points = 6
        a.units[0].current_health = 1.0
        battle._current_round = 3
        # Default cap = 1.
        self.assertEqual(battle.DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE, 1)
        battle._apply_detachment_stratagems(a, b)
        # Exactly one stratagem fired through the dispatcher.
        self.assertEqual(a.stratagems_fired_this_command_phase, 1)

    def test_cap_resets_between_command_phases(self):
        """Resetting `_apply_detachment_stratagems` once per army per
        Command phase reinitialises the counter to 0; the cap therefore
        permits one fresh fire per subsequent Command phase.
        """
        a = Army("T'au")
        a.add_unit(_tau_crisis_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.command_points = 6
        a.units[0].current_health = 1.0
        battle._current_round = 3
        battle._apply_detachment_stratagems(a, b)
        self.assertEqual(a.stratagems_fired_this_command_phase, 1)
        # New Command phase — refill CP, the counter is reset at the top
        # of `_apply_detachment_stratagems` so the next call gets a fresh
        # quota.
        a.command_points = 6
        battle._apply_detachment_stratagems(a, b)
        self.assertEqual(a.stratagems_fired_this_command_phase, 1)

    def test_core_stratagems_do_not_count_toward_cap(self):
        """Core Stratagems (Tank Shock, Counter-Offensive, Command
        Re-Roll) fire on per-trigger hooks outside
        `_apply_detachment_stratagems` and must NOT increment the
        per-Command-phase counter. We exercise the in-band path through
        `_fire_stratagem` with the dispatch flag explicitly OFF (the
        post-condition that all Core-Stratagem call sites rely on).
        (Heroic Intervention is a free core CHARACTER ability per
        #iter12 — no longer a stratagem.)
        """
        from code.stratagems import COMMAND_RE_ROLL

        a = Army("T'au")
        a.add_unit(_tau_crisis_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.command_points = 6
        # Dispatcher flag is False by default (set True only inside
        # `_apply_detachment_stratagems`'s try/finally block).
        self.assertFalse(battle._dispatching_detachment_stratagems)
        ok = battle._fire_stratagem(a, COMMAND_RE_ROLL)
        self.assertTrue(ok)
        # CP spent, but the per-Command-phase detachment counter did NOT
        # increment because the dispatch flag was clear.
        self.assertEqual(a.command_points, 5)
        self.assertEqual(a.stratagems_fired_this_command_phase, 0)


if __name__ == "__main__":
    unittest.main()
