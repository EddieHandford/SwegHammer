"""Tests for the real Oathband (Leagues of Votann) detachment stratagems
(iter-9 fix).

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/

Replaces the iter-0 zero-stratagem state where Votann burned every strat
fire on Command Re-Roll (universal Core). iter-8 anti-DG audit
(docs/AUTO_LOOP_ITER8_ANTI_DG_AUDIT.md fix #2) flagged Oathband as one of
the top fixes for the +18.1pt DG residual — Votann-vs-DG sits in the
unsampled-but-positive 7 matchups (~+8pt over real per iter-5).

Coverage:
    * Registry: OATHBAND still wired into DETACHMENTS, DEFAULT_BY_FACTION,
      FACTION_DETACHMENTS for Leagues of Votann.
    * Six real Oathband stratagems exposed via OATHBAND.stratagems with
      the codex CP costs.
    * Each `_try_*` dispatcher consumes CP and sets the right transient
      flag (or directly increments judgement_tokens for Ancestral Sentence)
      on a green-lit AI gate. No catalogued-but-no-op entries — all six
      wire to a real mechanical effect.
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
    ANCESTRAL_SENTENCE, GLORY_OF_THE_HEARTH, IRONKIN_SEQUENCE,
    OATHBAND_STRATAGEMS, VOID_ARMOURED_RESILIENCE, WARRIOR_PRIDE,
    WRATH_OF_THE_ANCESTORS,
)
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _hearthkyn_profile() -> UnitProfile:
    """A Hearthkyn Warriors brick — Votann INFANTRY + IRONKIN, the typical
    Oathband chassis. Cost above the AI gate threshold for the 1-CP
    Oathband stratagems."""
    return UnitProfile(
        name="Hearthkyn Warriors", faction="Leagues of Votann",
        health=20, damage=1, hit_probability=2 / 3,
        ap=-1, save=4, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        move=5.0, leadership=7, oc=2,
        unit_keywords=("INFANTRY", "LEAGUES OF VOTANN", "IRONKIN", "BATTLELINE"),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        points_override=100.0,
    )


def _hekaton_profile() -> UnitProfile:
    """A Hekaton Land Fortress — Votann VEHICLE for Glory of the Hearth
    targeting."""
    return UnitProfile(
        name="Hekaton Land Fortress", faction="Leagues of Votann",
        health=18, damage=3, hit_probability=2 / 3,
        ap=-2, save=2, strength=10, toughness=11,
        attacks=6, weapon_damage_per_shot=3.0, range_inches=36,
        move=8.0, leadership=6, oc=4,
        unit_keywords=("VEHICLE", "LEAGUES OF VOTANN", "IRONKIN"),
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
    """The six real Oathband stratagems must be attached to the detachment
    by canonical name + CP cost, and exposed via OATHBAND.stratagems."""

    EXPECTED = (
        ("Warrior Pride", 1),
        ("Wrath of the Ancestors", 1),
        ("Glory of the Hearth", 1),
        ("Ironkin Sequence", 1),
        ("Ancestral Sentence", 2),
        ("Void-Armoured Resilience", 1),
    )

    def test_six_stratagems_attached_to_detachment(self):
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
        self.assertEqual(WARRIOR_PRIDE.name, "Warrior Pride")
        self.assertEqual(WRATH_OF_THE_ANCESTORS.name, "Wrath of the Ancestors")
        self.assertEqual(GLORY_OF_THE_HEARTH.name, "Glory of the Hearth")
        self.assertEqual(IRONKIN_SEQUENCE.name, "Ironkin Sequence")
        self.assertEqual(ANCESTRAL_SENTENCE.name, "Ancestral Sentence")
        self.assertEqual(VOID_ARMOURED_RESILIENCE.name, "Void-Armoured Resilience")


# ---------------------------------------------------------------------------
# Dispatcher wiring — each stratagem sets its mechanical effect on a fire
# ---------------------------------------------------------------------------


class OathbandDispatcherTests(unittest.TestCase):
    """The simulator's `_try_*` dispatchers each consume CP and set the
    right transient flag (or increment the judgement_tokens dict for
    Ancestral Sentence) on a green-lit AI gate. All six wire to a real
    mechanical effect — no catalogued-but-no-op entries in this set."""

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
        # Wound the Hearthkyn so vulnerability gates clear (FNP / save
        # buffs require HP loss > 0.2).
        a.units[0].current_health = 10.0   # 50% HP loss on 20 max
        battle._current_round = 2
        return battle, a, b

    def test_warrior_pride_sets_plus_one_to_wound_both_modes(self):
        """Warrior Pride routes the wound-reroll value through +1 to wound
        on both melee and shooting on the highest-DPA Votann unit. The
        Hekaton clears the cost+DPA gates first, so it should pick up the
        buff before the Hearthkyn (which has lower per-attack DPA)."""
        battle, a, _b = self._build_battle()
        battle._try_warrior_pride(a, _b)
        # Find which unit got the buff — should be the highest-DPA Votann
        # (Hekaton: 6 attacks * 2/3 * 3 dmg = 12 DPA vs Hearthkyn's much
        # lower per-unit DPA).
        buffed = [u for u in a.units if u.transient_plus_one_to_wound_melee]
        self.assertEqual(len(buffed), 1, "Exactly one Votann unit should be buffed.")
        self.assertTrue(buffed[0].transient_plus_one_to_wound_shooting)
        self.assertEqual(a.command_points, 5)

    def test_wrath_of_the_ancestors_sets_plus_one_to_hit_shooting(self):
        """Wrath of the Ancestors (LETHAL HITS APPROXIMATION) maps to
        +1-to-hit-shooting on the highest-DPA Votann shooter."""
        battle, a, _b = self._build_battle()
        battle._try_wrath_of_the_ancestors(a, _b)
        buffed = [u for u in a.units if u.transient_plus_one_to_hit_shooting]
        self.assertEqual(len(buffed), 1)
        self.assertEqual(a.command_points, 5)

    def test_glory_of_the_hearth_sets_reroll_hits_on_vehicle(self):
        """Glory of the Hearth (Votann VEHICLE wound+hit reroll) maps to
        reroll-hits-shooting on the VEHICLE specifically."""
        battle, a, _b = self._build_battle()
        battle._try_glory_of_the_hearth(a, _b)
        hekaton = next(u for u in a.units if u.profile.name == "Hekaton Land Fortress")
        self.assertTrue(hekaton.transient_reroll_hits_shooting)
        # Hearthkyn (non-VEHICLE) must NOT be buffed.
        hearthkyn = next(u for u in a.units if u.profile.name == "Hearthkyn Warriors")
        self.assertFalse(hearthkyn.transient_reroll_hits_shooting)
        self.assertEqual(a.command_points, 5)

    def test_glory_of_the_hearth_skips_when_no_vehicle(self):
        """Glory of the Hearth has no legal target in a Hearthkyn-mono list;
        the dispatcher must skip the spend entirely."""
        battle, a, _b = self._build_battle(with_vehicle=False)
        cp_before = a.command_points
        battle._try_glory_of_the_hearth(a, _b)
        # No VEHICLE → no CP spent, no buff applied.
        self.assertEqual(a.command_points, cp_before)
        self.assertFalse(a.units[0].transient_reroll_hits_shooting)

    def test_ironkin_sequence_sets_plus_one_to_hit_shooting(self):
        """Ironkin Sequence maps directly to +1-to-hit-shooting on the
        highest-DPA IRONKIN unit."""
        battle, a, _b = self._build_battle()
        battle._try_ironkin_sequence(a, _b)
        buffed = [u for u in a.units if u.transient_plus_one_to_hit_shooting]
        self.assertEqual(len(buffed), 1)
        self.assertEqual(a.command_points, 5)

    def test_ancestral_sentence_issues_judgement_token(self):
        """Ancestral Sentence increments the Votann army's judgement_tokens
        dict for the highest-threat enemy uid. Spends 2 CP."""
        battle, a, b = self._build_battle()
        target = b.units[0]
        # Pre-fire: no tokens on the target.
        self.assertEqual(a.judgement_tokens.get(target.uid, 0), 0)
        battle._try_ancestral_sentence(a, b)
        # Post-fire: target has 1 token from the Votann army's pool.
        self.assertEqual(a.judgement_tokens.get(target.uid, 0), 1)
        self.assertEqual(a.command_points, 4)   # 2 CP cost

    def test_ancestral_sentence_skips_non_votann_army(self):
        """Ancestral Sentence is gated on `is_votann_army` — a non-Votann
        list carrying Oathband by accident must not increment tokens."""
        a = Army("Adeptus Astartes")
        a.add_unit(UnitProfile(
            name="Tactical Squad", faction="Adeptus Astartes",
            health=10, damage=1, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
            unit_keywords=("INFANTRY", "ADEPTUS ASTARTES"),
            points_override=100.0,
        ))
        b = Army("Enemy")
        b.add_unit(_target_profile())
        battle = Battle(a, b)
        battle._assign_uids()
        a.command_points = 6
        battle._current_round = 2
        cp_before = a.command_points
        battle._try_ancestral_sentence(a, b)
        # Not a Votann army → no token issued, no CP spent.
        self.assertEqual(a.command_points, cp_before)
        self.assertEqual(a.judgement_tokens.get(b.units[0].uid, 0), 0)

    def test_void_armoured_resilience_sets_fnp_5(self):
        """Void-Armoured Resilience maps directly to transient_fnp_5 on the
        most vulnerable Votann unit (the wounded Hearthkyn)."""
        battle, a, _b = self._build_battle()
        battle._try_void_armoured_resilience(a, _b)
        # The Hearthkyn is at 50% HP, more vulnerable than the full-HP
        # Hekaton.
        hearthkyn = next(u for u in a.units if u.profile.name == "Hearthkyn Warriors")
        self.assertTrue(hearthkyn.transient_fnp_5)
        self.assertEqual(a.command_points, 5)


# ---------------------------------------------------------------------------
# Stratagems-for-army integration
# ---------------------------------------------------------------------------


class OathbandStratagemsForArmyTests(unittest.TestCase):
    """A Votann army wired with Oathband must expose all four Core universals
    plus the six Oathband stratagems via `stratagems_for_army`."""

    def test_votann_army_exposes_oathband_stratagems(self):
        from code.stratagems import stratagems_for_army

        a = Army("Leagues of Votann")
        a.add_unit(_hearthkyn_profile())
        names = {s.name for s in stratagems_for_army(a)}
        # All six Oathband stratagems plus the four universal Core stratagems.
        for n in (
            "Warrior Pride", "Wrath of the Ancestors", "Glory of the Hearth",
            "Ironkin Sequence", "Ancestral Sentence", "Void-Armoured Resilience",
        ):
            self.assertIn(n, names, f"{n} missing from stratagems_for_army")
        # And the four Core universals.
        for n in (
            "Command Re-Roll", "Counter-Offensive", "Tank Shock",
            "Heroic Intervention",
        ):
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
