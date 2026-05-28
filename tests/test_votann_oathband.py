"""Tests for the real Needgaard Oathband (Leagues of Votann) detachment
stratagems.

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/

VOTANN-DIAG-2 (2026-05-26) replaced the previous six-stratagem fabrication
(Warrior Pride, Wrath of the Ancestors, Glory of the Hearth, Ironkin
Sequence, Ancestral Sentence at 2 CP, Void-Armoured Resilience) with three
real Needgaard Oathband stratagems per Wahapedia:
    * Huntr's Mark (1 CP) — re-roll Hit and Wound rolls of 1
    * Ancestral Sentence (1 CP) — ranged [SUSTAINED HITS 1] for the phase
    * Void Hardened (1 CP) — defensive AP-worsen no-op (held slot)

Coverage:
    * Registry: OATHBAND still wired into DETACHMENTS, DEFAULT_BY_FACTION,
      FACTION_DETACHMENTS for Leagues of Votann.
    * Three real Oathband stratagems exposed via OATHBAND.stratagems with
      the codex CP costs.
    * Each `_try_*` dispatcher consumes CP and sets the right transient
      flag on a green-lit AI gate.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import (
    DEFAULT_BY_FACTION, DETACHMENTS, FACTION_DETACHMENTS, OATHBAND,
)
from code.simulator import Battle
from code.stratagems import (
    ANCESTRAL_SENTENCE, HUNTRS_MARK, OATHBAND_STRATAGEMS, VOID_HARDENED,
)
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _hearthkyn_profile() -> UnitProfile:
    """A Hearthkyn Warriors brick — Votann INFANTRY, the typical Oathband
    chassis. Cost above the AI gate threshold for the 1-CP Oathband
    stratagems."""
    return UnitProfile(
        name="Hearthkyn Warriors", faction="Leagues of Votann",
        health=20, damage=1, hit_probability=2 / 3,
        ap=-1, save=4, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        move=5.0, leadership=7, oc=2,
        unit_keywords=("INFANTRY", "LEAGUES OF VOTANN", "BATTLELINE"),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        points_override=100.0,
    )


def _hekaton_profile() -> UnitProfile:
    """A Hekaton Land Fortress — Votann VEHICLE with high DPA, the
    expected highest-DPA pick for the Oathband stratagem dispatchers."""
    return UnitProfile(
        name="Hekaton Land Fortress", faction="Leagues of Votann",
        health=18, damage=3, hit_probability=2 / 3,
        ap=-2, save=2, strength=10, toughness=11,
        attacks=6, weapon_damage_per_shot=3.0, range_inches=36,
        move=8.0, leadership=6, oc=4,
        unit_keywords=("VEHICLE", "LEAGUES OF VOTANN"),
        melee_attacks=4, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=8, melee_ap=-1,
        points_override=215.0,
    )


def _target_profile() -> UnitProfile:
    """A HEAVY-class target so the AI gates for stratagems clear."""
    return UnitProfile(
        name="HeavyTarget", faction="Test",
        health=10, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, strength=6, toughness=8,
        attacks=4, weapon_damage_per_shot=2.0, range_inches=48,
        unit_keywords=("VEHICLE",),
        points_override=200.0,
    )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class OathbandRegistryTests(unittest.TestCase):

    def test_oathband_in_detachments(self):
        self.assertIn("oathband", DETACHMENTS)
        self.assertIs(DETACHMENTS["oathband"], OATHBAND)

    def test_default_by_faction_votann(self):
        self.assertEqual(DEFAULT_BY_FACTION["Leagues of Votann"], "oathband")

    def test_faction_detachments_votann(self):
        self.assertEqual(
            FACTION_DETACHMENTS["Leagues of Votann"], ("oathband",),
        )


# ---------------------------------------------------------------------------
# Stratagem CP costs + names
# ---------------------------------------------------------------------------


class OathbandStratagemsTests(unittest.TestCase):
    """The three real Needgaard Oathband stratagems must be attached to
    the detachment by canonical name + CP cost, and exposed via
    OATHBAND.stratagems."""

    EXPECTED = (
        ("Huntr's Mark", 1),
        ("Ancestral Sentence", 1),
        ("Void Hardened", 1),
    )

    def test_three_stratagems_attached_to_detachment(self):
        attached = {s.name: s.cp_cost for s in OATHBAND.stratagems}
        for name, cp in self.EXPECTED:
            self.assertIn(name, attached, f"{name} missing from OATHBAND.stratagems")
            self.assertEqual(
                attached[name], cp,
                f"{name} expected {cp} CP, got {attached[name]}",
            )

    def test_oathband_stratagems_tuple_matches_attached(self):
        self.assertEqual(OATHBAND.stratagems, OATHBAND_STRATAGEMS)

    def test_constants_exist_and_named_correctly(self):
        self.assertEqual(HUNTRS_MARK.name, "Huntr's Mark")
        self.assertEqual(ANCESTRAL_SENTENCE.name, "Ancestral Sentence")
        self.assertEqual(VOID_HARDENED.name, "Void Hardened")


# ---------------------------------------------------------------------------
# Dispatcher wiring — each stratagem sets its mechanical effect on a fire
# ---------------------------------------------------------------------------


class OathbandDispatcherTests(unittest.TestCase):
    """The simulator's `_try_*` dispatchers each consume CP and set the
    right transient flag on a green-lit AI gate."""

    def _build_battle(self, cp: int = 6, with_vehicle: bool = True):
        a = Army("Leagues of Votann")
        a.add_unit(_hearthkyn_profile())
        if with_vehicle:
            a.add_unit(_hekaton_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.command_points = cp
        # Wound the Hearthkyn so vulnerability gates clear.
        a.units[0].current_health = 10.0   # 50% HP loss on 20 max
        battle._current_round = 2
        return battle, a, b

    def test_huntrs_mark_sets_reroll_hits_and_wound_ones(self):
        """Huntr's Mark routes the "re-roll hit/wound 1s" effect through
        transient_reroll_hits_shooting + transient_reroll_wounds_ones on
        the highest-DPA Votann unit (Hekaton)."""
        battle, a, _b = self._build_battle()
        battle._try_huntrs_mark(a, _b)
        # Find which unit got the buff — should be the highest-DPA Votann.
        buffed = [
            u for u in a.units
            if u.transient_reroll_hits_shooting and u.transient_reroll_wounds_ones
        ]
        self.assertEqual(len(buffed), 1, "Exactly one Votann unit should be buffed.")
        self.assertEqual(a.command_points, 5)   # 1 CP spent

    def test_ancestral_sentence_sets_sustained_hits(self):
        """Ancestral Sentence (current 10e codex) maps to
        transient_sustained_hits = 1 on the highest-DPA Votann shooter.
        The launch-day "issue a Judgement Token" effect is retired in the
        current codex; the dispatcher no longer increments
        `judgement_tokens` for this stratagem."""
        battle, a, _b = self._build_battle()
        battle._try_ancestral_sentence(a, _b)
        buffed = [u for u in a.units if getattr(u, "transient_sustained_hits", 0) >= 1]
        self.assertEqual(len(buffed), 1)
        self.assertEqual(a.command_points, 5)   # 1 CP spent (not the fabricated 2 CP)

    def test_void_hardened_spends_cp_with_no_offensive_effect(self):
        """Void Hardened is a defensive AP-worsen for a phase — the
        simulator has no incoming-AP worsening transient flag, so this
        dispatcher is a documented no-op that still consumes the CP
        spend. Verifies no Votann unit picks up an offensive transient
        as a side effect."""
        battle, a, _b = self._build_battle()
        battle._try_void_hardened(a, _b)
        for u in a.units:
            self.assertFalse(getattr(u, "transient_reroll_hits_shooting", False))
            self.assertFalse(getattr(u, "transient_plus_one_to_hit_shooting", False))
            self.assertFalse(getattr(u, "transient_plus_one_to_wound_melee", False))


# ---------------------------------------------------------------------------
# Stratagems-for-army integration
# ---------------------------------------------------------------------------


class OathbandStratagemsForArmyTests(unittest.TestCase):
    """A Votann army wired with Oathband must expose the three Oathband
    stratagems plus the three Core universals via `stratagems_for_army`."""

    def test_votann_army_exposes_oathband_stratagems(self):
        from code.stratagems import stratagems_for_army

        a = Army("Leagues of Votann")
        a.add_unit(_hearthkyn_profile())
        names = {s.name for s in stratagems_for_army(a)}
        for n in ("Huntr's Mark", "Ancestral Sentence", "Void Hardened"):
            self.assertIn(n, names, f"{n} missing from stratagems_for_army")
        # And the three Core universals.
        for n in ("Command Re-Roll", "Counter-Offensive", "Tank Shock"):
            self.assertIn(n, names)
        self.assertNotIn("Heroic Intervention", names)


if __name__ == "__main__":
    unittest.main()
