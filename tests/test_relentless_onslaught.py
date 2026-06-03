"""Tests for the Necrons Cursed Legion "Relentless Onslaught" detachment rule.

BSData v10.6.0 (Necrons.cat.gz, rule id 1dfc-5377-99ac-a700), verbatim:
  "Each time a NECRONS model from your army makes an attack that targets a
   unit within range of one or more objective markers, add 1 to the Hit roll.
   In addition, ranged weapons equipped by NECRONS VEHICLE and NECRONS MOUNTED
   models (excluding TITANIC models) from your army have the [ASSAULT] ability."

Two simulator gates read Detachment.relentless_onslaught:
  * the +1-to-Hit gate in code.units.Unit.attack — fires when the attacker is
    a NECRONS model AND the target unit is within range of an objective marker
    (`target.on_objective`). Applies to BOTH ranged and melee attacks, with no
    round restriction, and composes with other +1-to-hit sources through the
    10e ±1 Hit-modifier cap.
  * the [ASSAULT] Advance-lockout exemption in code.simulator.Battle._do_shoot
    — lets a NECRONS VEHICLE / MOUNTED (excluding TITANIC) unit that Advanced
    still shoot, mirroring the [ASSAULT] grant on its ranged weapons.

These tests verify both clauses fire only under the detachment gate + the
rule's own keyword gates, and stay off for a non-Necrons army or a Necrons
army on a detachment that lacks the flag (Awakened Dynasty). The rule is
even-handed: gated on the DETACHMENT flag + target.on_objective + the NECRONS
keyword the rule itself names — no hardcoded faction-only branch.

Abilities #1 (claude/sim-calibration-6).
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import (
    AWAKENED_DYNASTY,
    CURSED_LEGION,
    DETACHMENTS,
    FACTION_DETACHMENTS,
    default_detachment_for_faction,
)
from code.simulator import Battle
from code.units import Unit, UnitProfile


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def _necron_infantry() -> UnitProfile:
    """A NECRONS INFANTRY shooter. hit_probability 0.5 (hit_target 4+) so the
    +1-to-Hit visibly closes a bracket (4+ -> 3+). High attack count so the
    Monte-Carlo damage mean is tight."""
    return UnitProfile(
        name="Necron Warriors", faction="Necrons",
        health=10, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=20, weapon_damage_per_shot=1.0,
        melee_attacks=20, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4,
        range_inches=24,
        unit_keywords=("NECRONS", "INFANTRY"),
        points_override=90.0,
    )


def _non_necron_infantry() -> UnitProfile:
    """An identical-statline non-NECRONS attacker (faction gate control)."""
    return UnitProfile(
        name="Guardsman Squad", faction="Astra Militarum",
        health=10, damage=1, hit_probability=0.5,
        ap=0, save=4, strength=4, toughness=4,
        attacks=20, weapon_damage_per_shot=1.0,
        melee_attacks=20, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4,
        range_inches=24,
        unit_keywords=("ASTRA MILITARUM", "INFANTRY"),
        points_override=90.0,
    )


def _soft_target() -> UnitProfile:
    """A high-wound soft target so a single attack() call never wipes it —
    keeps the damage mean an unbiased estimate of the hit-rate change."""
    return UnitProfile(
        name="Cultist Mob", faction="Chaos Space Marines",
        health=200, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        points_override=60.0,
    )


def _necron_vehicle(keywords=("NECRONS", "VEHICLE"),
                    faction="Necrons") -> UnitProfile:
    return UnitProfile(
        name="Annihilation Barge", faction=faction,
        health=10, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=6, toughness=9,
        attacks=6, weapon_damage_per_shot=2.0,
        range_inches=24,
        unit_keywords=keywords,
        points_override=120.0,
    )


def _enemy_blob() -> UnitProfile:
    return UnitProfile(
        name="Guardsman Squad", faction="Astra Militarum",
        health=80, damage=1, hit_probability=0.5,
        ap=0, save=5, strength=3, toughness=3,
        attacks=1, weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        points_override=60.0,
    )


def _mean_attack_damage(attacker_profile, detachment, on_objective, mode="ranged",
                        n=4000, seed=20260603):
    """Monte-Carlo mean of a single attack() call against a fresh soft target.

    Returns the average expected damage so the test can compare the +1-to-Hit
    on/off cases. The target is reset to full health each trial so a stray
    wipe never truncates the shot count."""
    a = Army("Attacker")
    a.add_unit(attacker_profile)
    a.detachment = detachment
    b = Army("Defender")
    b.add_unit(_soft_target())
    atk = a.units[0]
    tgt = b.units[0]
    tgt.on_objective = on_objective
    random.seed(seed)
    total = 0.0
    for _ in range(n):
        total += atk.attack(tgt, mode=mode)
        tgt.current_health = tgt.profile.health
    return total / n


def _vehicle_shoots_after_advance(detachment, vehicle_profile):
    """Return True if a unit with `vehicle_profile`, having Advanced this round,
    is allowed to fire (i.e. it deals damage) under `detachment`."""
    random.seed(0)
    a = Army("Attacker")
    a.add_unit(vehicle_profile)
    a.detachment = detachment
    b = Army("Defender")
    b.add_unit(_enemy_blob())
    battle = Battle(a, b)
    battle._assign_uids()
    battle._deploy_armies()
    atk = a.units[0]
    tgt = b.units[0]
    # Place adjacent so the target is in range and visible.
    atk.position = (10.0, 10.0)
    tgt.position = (12.0, 10.0)
    tgt.current_health = tgt.profile.health
    # Mark the attacker as having Advanced this round (the lockout trigger).
    battle._advanced_this_round = {atk.uid}
    before = tgt.current_health
    battle._do_shoot(atk, a, b)
    return tgt.current_health < before


# ---------------------------------------------------------------------------
# Registry / wiring
# ---------------------------------------------------------------------------

class RelentlessOnslaughtRegistryTests(unittest.TestCase):

    def test_flag_set_on_cursed_legion_only(self):
        self.assertTrue(CURSED_LEGION.relentless_onslaught)
        # The other Necrons detachments must NOT carry the flag.
        self.assertFalse(AWAKENED_DYNASTY.relentless_onslaught)
        self.assertFalse(DETACHMENTS["canoptek_court"].relentless_onslaught)
        self.assertFalse(DETACHMENTS["annihilation_legion"].relentless_onslaught)

    def test_cursed_legion_registered_and_necron(self):
        self.assertIn("cursed_legion", DETACHMENTS)
        self.assertIs(DETACHMENTS["cursed_legion"], CURSED_LEGION)
        self.assertEqual(CURSED_LEGION.faction, "Necrons")

    def test_cursed_legion_is_primary_necron_detachment(self):
        # Default + first in the picker tuple so the calibration A/B measures it.
        self.assertEqual(default_detachment_for_faction("Necrons"), CURSED_LEGION)
        self.assertEqual(FACTION_DETACHMENTS["Necrons"][0], "cursed_legion")
        # Variety picks retained.
        for key in ("awakened_dynasty", "canoptek_court", "annihilation_legion"):
            self.assertIn(key, FACTION_DETACHMENTS["Necrons"])


# ---------------------------------------------------------------------------
# Clause 1 — +1 to Hit vs targets near objectives
# ---------------------------------------------------------------------------

class RelentlessOnslaughtHitBonusTests(unittest.TestCase):

    def test_necron_gets_plus_one_hit_vs_on_objective_target(self):
        on = _mean_attack_damage(_necron_infantry(), CURSED_LEGION, on_objective=True)
        off = _mean_attack_damage(_necron_infantry(), CURSED_LEGION, on_objective=False)
        # +1 to hit raises 4+ to 3+ (0.5 -> ~0.667 hit rate), a clear ~33% lift.
        self.assertGreater(on, off * 1.2)

    def test_no_bonus_when_target_not_on_objective(self):
        # Same Necron + Cursed Legion, off-objective target == baseline 0.5 hit.
        off = _mean_attack_damage(_necron_infantry(), CURSED_LEGION, on_objective=False)
        baseline = _mean_attack_damage(
            _necron_infantry(), AWAKENED_DYNASTY, on_objective=True,
        )
        # Off-objective Cursed Legion and on-objective Awakened Dynasty must
        # both land at the un-buffed hit rate (within Monte-Carlo noise).
        self.assertAlmostEqual(off, baseline, delta=0.25)

    def test_non_necron_army_gets_no_bonus(self):
        # A non-NECRONS attacker, even vs an on-objective target with the same
        # Cursed Legion detachment object, gets nothing (faction gate).
        on = _mean_attack_damage(_non_necron_infantry(), CURSED_LEGION, on_objective=True)
        off = _mean_attack_damage(_non_necron_infantry(), CURSED_LEGION, on_objective=False)
        self.assertAlmostEqual(on, off, delta=0.25)

    def test_necron_on_non_relentless_detachment_gets_no_bonus(self):
        # NECRONS attacker, on-objective target, but Awakened Dynasty (no flag).
        on = _mean_attack_damage(_necron_infantry(), AWAKENED_DYNASTY, on_objective=True)
        off = _mean_attack_damage(_necron_infantry(), AWAKENED_DYNASTY, on_objective=False)
        self.assertAlmostEqual(on, off, delta=0.25)

    def test_bonus_applies_in_melee_too(self):
        # The rule says "makes an attack" — melee benefits as well as ranged.
        on = _mean_attack_damage(
            _necron_infantry(), CURSED_LEGION, on_objective=True, mode="melee",
        )
        off = _mean_attack_damage(
            _necron_infantry(), CURSED_LEGION, on_objective=False, mode="melee",
        )
        self.assertGreater(on, off * 1.2)


# ---------------------------------------------------------------------------
# Clause 2 — [ASSAULT] on NECRONS VEHICLE / MOUNTED (non-TITANIC)
# ---------------------------------------------------------------------------

class RelentlessOnslaughtAssaultClauseTests(unittest.TestCase):

    def test_necron_vehicle_shoots_after_advance(self):
        self.assertTrue(_vehicle_shoots_after_advance(
            CURSED_LEGION, _necron_vehicle(("NECRONS", "VEHICLE")),
        ))

    def test_necron_mounted_shoots_after_advance(self):
        self.assertTrue(_vehicle_shoots_after_advance(
            CURSED_LEGION, _necron_vehicle(("NECRONS", "MOUNTED")),
        ))

    def test_titanic_excluded(self):
        # TITANIC NECRONS VEHICLE is explicitly excluded by the rule.
        self.assertFalse(_vehicle_shoots_after_advance(
            CURSED_LEGION, _necron_vehicle(("NECRONS", "VEHICLE", "TITANIC")),
        ))

    def test_no_assault_without_relentless_detachment(self):
        # Awakened Dynasty lacks the flag — the vehicle stays Advance-locked.
        self.assertFalse(_vehicle_shoots_after_advance(
            AWAKENED_DYNASTY, _necron_vehicle(("NECRONS", "VEHICLE")),
        ))

    def test_non_necron_vehicle_excluded(self):
        # Faction gate: a non-NECRONS VEHICLE gets no [ASSAULT] from this rule.
        non_necron = _necron_vehicle(("VEHICLE",), faction="Astra Militarum")
        self.assertFalse(_vehicle_shoots_after_advance(CURSED_LEGION, non_necron))

    def test_necron_infantry_not_covered_by_assault_clause(self):
        # The [ASSAULT] clause is VEHICLE / MOUNTED only — plain INFANTRY stays
        # Advance-locked (its weapons do not gain [ASSAULT]).
        self.assertFalse(_vehicle_shoots_after_advance(
            CURSED_LEGION, _necron_infantry(),
        ))


if __name__ == "__main__":
    unittest.main()
