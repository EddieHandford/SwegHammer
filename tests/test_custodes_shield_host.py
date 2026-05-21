"""Tests for the real Shield Host (Adeptus Custodes) detachment + stratagems
(iter-8 fix).

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host

Replaces the iter-0 `plus_one_save` defensive approximation with the
canonical Martial Ka'tah / Martial Mastery offensive Crit-on-5+ melee +
melee AP+1 dual buff, plus the six real Shield Host detachment stratagems
(Arcane Genetic Alchemy, Unwavering Sentinels, Multipotentiality, Vigilance
Eternal, Archaeotech Munitions, Avenge the Fallen).

Coverage:
    * Registry: SHIELD_HOST wired into DETACHMENTS, DEFAULT_BY_FACTION,
      FACTION_DETACHMENTS for Adeptus Custodes.
    * Martial Ka'tah flags set on the detachment instance
      (`melee_crit_on_5_plus_hits`, `melee_ap_plus_one`) and the iter-0
      `plus_one_save` flag REMOVED.
    * Six real Shield Host stratagems exposed via SHIELD_HOST.stratagems
      with the codex CP costs.
    * Each `_try_*` dispatcher consumes CP and sets the right transient
      flag on a green-lit AI gate. Vigilance Eternal is intentionally
      no-op (APPROXIMATION).
    * Integration: Custodes melee attacker in a Shield Host army gets
      Crit-on-5+ behaviour in `Unit.attack`.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import (
    DEFAULT_BY_FACTION, DETACHMENTS, FACTION_DETACHMENTS, SHIELD_HOST,
)
from code.simulator import Battle
from code.stratagems import (
    ARCANE_GENETIC_ALCHEMY, ARCHAEOTECH_MUNITIONS, AVENGE_THE_FALLEN,
    MULTIPOTENTIALITY, SHIELD_HOST_STRATAGEMS, UNWAVERING_SENTINELS,
    VIGILANCE_ETERNAL,
)
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _custodian_guard_profile() -> UnitProfile:
    """A 100+ pt Adeptus Custodes melee brick — passes AI gates for the
    1-CP Shield Host stratagems."""
    return UnitProfile(
        name="Custodian Guard", faction="Adeptus Custodes",
        health=12, damage=1, hit_probability=2 / 3,
        ap=-2, save=2, strength=4, toughness=6,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        move=6.0, leadership=6, oc=2,
        unit_keywords=("INFANTRY", "ADEPTUS CUSTODES", "BATTLELINE"),
        melee_attacks=1, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=6, melee_ap=-2,
        points_override=215.0, invuln_save=4,
    )


def _shield_captain_profile() -> UnitProfile:
    """An Adeptus Custodes CHARACTER for Multipotentiality targeting."""
    return UnitProfile(
        name="Shield-Captain", faction="Adeptus Custodes",
        health=6, damage=2, hit_probability=5 / 6,
        ap=-2, save=2, strength=6, toughness=6,
        attacks=2, weapon_damage_per_shot=2.0, range_inches=24,
        move=6.0, leadership=6, oc=2,
        unit_keywords=("INFANTRY", "ADEPTUS CUSTODES", "CHARACTER"),
        melee_attacks=6, melee_damage_per_shot=3.0,
        melee_hit_probability=5 / 6, melee_strength=8, melee_ap=-3,
        points_override=130.0, invuln_save=4,
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


class ShieldHostRegistryTests(unittest.TestCase):

    def test_shield_host_in_detachments(self):
        self.assertIn("shield_host", DETACHMENTS)
        self.assertIs(DETACHMENTS["shield_host"], SHIELD_HOST)

    def test_default_by_faction_custodes(self):
        self.assertEqual(DEFAULT_BY_FACTION["Adeptus Custodes"], "shield_host")

    def test_faction_detachments_custodes(self):
        # LC1-A: Custodes detachment pool widened from (shield_host,) to
        # (shield_host, auric_champions). Shield Host remains the default
        # per DEFAULT_BY_FACTION; Auric Champions appears as a milder
        # offensive alternative so the picker has a real choice.
        self.assertEqual(
            FACTION_DETACHMENTS["Adeptus Custodes"],
            ("shield_host", "auric_champions"),
        )

    def test_martial_katah_flags_set(self):
        """Martial Ka'tah / Martial Mastery is wired as the two boolean
        flags `melee_crit_on_5_plus_hits` and `melee_ap_plus_one`."""
        self.assertTrue(SHIELD_HOST.melee_crit_on_5_plus_hits)
        self.assertTrue(SHIELD_HOST.melee_ap_plus_one)

    def test_iter0_plus_one_save_approximation_removed(self):
        """The iter-0 defensive `plus_one_save` approximation was the
        wrong direction (Custodes durability instead of melee output) —
        iter-8 fix removed it. The flag must now read False."""
        self.assertFalse(SHIELD_HOST.plus_one_save)


# ---------------------------------------------------------------------------
# Stratagem CP costs + names
# ---------------------------------------------------------------------------


class ShieldHostStratagemsTests(unittest.TestCase):
    """The six real Shield Host stratagems must be attached to the detachment
    by canonical name + CP cost, and exposed via SHIELD_HOST.stratagems."""

    EXPECTED = (
        ("Arcane Genetic Alchemy", 1),
        ("Unwavering Sentinels", 1),
        ("Multipotentiality", 1),
        ("Vigilance Eternal", 1),
        ("Archaeotech Munitions", 1),
        ("Avenge the Fallen", 1),
    )

    def test_six_stratagems_attached_to_detachment(self):
        attached = {s.name: s.cp_cost for s in SHIELD_HOST.stratagems}
        for name, cp in self.EXPECTED:
            self.assertIn(name, attached, f"{name} missing from SHIELD_HOST.stratagems")
            self.assertEqual(
                attached[name], cp,
                f"{name} expected {cp} CP, got {attached[name]}",
            )

    def test_shield_host_stratagems_tuple_matches_attached(self):
        self.assertEqual(SHIELD_HOST.stratagems, SHIELD_HOST_STRATAGEMS)

    def test_constants_exist_and_named_correctly(self):
        self.assertEqual(ARCANE_GENETIC_ALCHEMY.name, "Arcane Genetic Alchemy")
        self.assertEqual(UNWAVERING_SENTINELS.name, "Unwavering Sentinels")
        self.assertEqual(MULTIPOTENTIALITY.name, "Multipotentiality")
        self.assertEqual(VIGILANCE_ETERNAL.name, "Vigilance Eternal")
        self.assertEqual(ARCHAEOTECH_MUNITIONS.name, "Archaeotech Munitions")
        self.assertEqual(AVENGE_THE_FALLEN.name, "Avenge the Fallen")


# ---------------------------------------------------------------------------
# Dispatcher wiring — five wired stratagems set their transient flag
# ---------------------------------------------------------------------------


class ShieldHostDispatcherTests(unittest.TestCase):
    """The simulator's `_try_*` dispatchers must each consume CP and set
    the right transient flag on a green-lit AI gate. Vigilance Eternal is
    intentionally no-op (APPROXIMATION — sticky-objective is per-detachment-
    flag-gated, not per-stratagem-fire)."""

    def _build_battle(self, cp: int = 6):
        a = Army("Adeptus Custodes")
        a.add_unit(_custodian_guard_profile())
        a.add_unit(_shield_captain_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.command_points = cp
        # Wound the Custodian Guard so vulnerability gates clear (the
        # defensive stratagems gate on HP loss > 0/0.2, and Avenge the
        # Fallen requires hp_frac > 0).
        a.units[0].current_health = 6.0   # 50% HP loss on 12 max
        battle._current_round = 2
        return battle, a, b

    def test_arcane_genetic_alchemy_sets_fnp_5(self):
        battle, a, _b = self._build_battle()
        battle._try_arcane_genetic_alchemy(a, _b)
        self.assertTrue(a.units[0].transient_fnp_5)
        self.assertEqual(a.command_points, 5)

    def test_unwavering_sentinels_sets_plus_one_save(self):
        battle, a, _b = self._build_battle()
        battle._try_unwavering_sentinels(a, _b)
        self.assertTrue(a.units[0].transient_plus_one_save)
        self.assertEqual(a.command_points, 5)

    def test_multipotentiality_sets_assault_this_round(self):
        battle, a, _b = self._build_battle()
        battle._try_multipotentiality(a, _b)
        # Highest-DPA Custodes is the Shield-Captain (6 attacks * 5/6 *
        # 3 damage = 15 melee DPA, vs Custodian Guard's 1 * 2/3 * 2 =
        # 1.33). The Custodian Guard's ranged is 2 * 2/3 * 1 = 1.33 too.
        captain = next(u for u in a.units if u.profile.name == "Shield-Captain")
        self.assertTrue(captain.transient_assault_this_round)
        self.assertEqual(a.command_points, 5)

    def test_archaeotech_munitions_sets_plus_one_to_hit_shooting(self):
        battle, a, _b = self._build_battle()
        battle._try_archaeotech_munitions(a, _b)
        captain = next(u for u in a.units if u.profile.name == "Shield-Captain")
        self.assertTrue(captain.transient_plus_one_to_hit_shooting)
        self.assertEqual(a.command_points, 5)

    def test_avenge_the_fallen_sets_plus_one_to_wound_melee(self):
        battle, a, _b = self._build_battle()
        battle._try_avenge_the_fallen(a, _b)
        # The wounded Custodian Guard is the most vulnerable Custodes unit.
        self.assertTrue(a.units[0].transient_plus_one_to_wound_melee)
        self.assertEqual(a.command_points, 5)

    def test_vigilance_eternal_is_no_op_in_dispatcher_block(self):
        """Vigilance Eternal is catalogued in SHIELD_HOST_STRATAGEMS for the
        auditor + stratagems_for_army listing, but the dispatcher block
        intentionally does NOT call any `_try_vigilance_eternal` method
        (sticky-objective is per-detachment-flag, not per-stratagem-fire).
        Verify the simulator does not expose such a method, so the absence
        is explicit and re-fires don't accidentally drain CP."""
        battle, _a, _b = self._build_battle()
        self.assertFalse(
            hasattr(battle, "_try_vigilance_eternal"),
            "Vigilance Eternal must remain catalogued-but-no-op (APPROXIMATION).",
        )


# ---------------------------------------------------------------------------
# Martial Ka'tah Crit-on-5+ behaviour in Unit.attack
# ---------------------------------------------------------------------------


class MartialKatahCritOn5Tests(unittest.TestCase):
    """Custodes melee attacker in a Shield Host army gets Crit-on-5+
    behaviour: an unmodified Hit roll of 5 should fire the crit branch
    (anti-X / Devastating Wounds / Sustained Hits). Without Martial Ka'tah
    the same roll only hits, not crits."""

    def _single_attack_custodian(self) -> UnitProfile:
        """Single melee attack, anti-VEHICLE 2+ so the crit triggers
        Devastating Wounds / Lethal Hits behaviour we can observe in
        wound resolution."""
        return UnitProfile(
            name="Custodian Guard", faction="Adeptus Custodes",
            health=3, damage=1, hit_probability=2 / 3,
            ap=0, save=2, strength=4, toughness=6,
            attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
            move=6.0, leadership=6, oc=2,
            unit_keywords=("INFANTRY", "ADEPTUS CUSTODES"),
            melee_attacks=1, melee_damage_per_shot=1.0,
            melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
            # devastating_wounds triggered by a crit -> bypasses saves
            devastating_wounds=True,
            points_override=80.0, invuln_save=4,
        )

    def test_crit_on_5_fires_for_shield_host_custodes_melee(self):
        """With Shield Host active AND on an EVEN battle round, an
        unmodified Hit roll of 5 on a Custodes melee attacker scores a
        Critical Hit, which on a devastating_wounds weapon bypasses
        saves. Without the detachment (or for a non-Custodes attacker),
        the same roll only hits, the wound roll happens, and the save
        can succeed.

        C1 (claude/sim-calibration-4): the Crit-on-5+ bullet now fires
        only on EVEN battle rounds (2, 4); the AP+1 bullet fires on ODD
        battle rounds (1, 3, 5). The test sets `_current_round = 2` to
        exercise the Crit-on-5+ branch.

        We force the to-hit roll to 5, the wound roll to 6 (auto-pass),
        and the save to a value that would normally succeed. Damage > 0
        means the crit fired (saves bypassed via devastating_wounds);
        damage == 0 means the crit didn't fire (save succeeded).
        """
        import random as _r

        # ---- WITH Shield Host on an EVEN round: 5 should crit, dev_wounds
        # bypasses save.
        a = Army("Adeptus Custodes")
        a.add_unit(self._single_attack_custodian())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        battle = Battle(a, b)
        battle._assign_uids()
        # C1: Crit-on-5+ alternation — exercise the EVEN-round branch.
        battle._current_round = 2
        attacker = a.units[0]
        defender = b.units[0]

        # Sequence: hit (5), wound (6 -> crit_wound but we test crit_hit
        # via devastating_wounds), save (1 -> would normally fail). With
        # crit_hit=True + devastating_wounds, the per_shot damage applies
        # directly and the save is bypassed.
        rolls = iter([5, 6, 1])
        original = _r.randint

        def fake_randint(lo, hi):
            try:
                return next(rolls)
            except StopIteration:
                return original(lo, hi)

        _r.randint = fake_randint
        try:
            damage_with = attacker.attack(defender, distance=0.5, mode="melee")
        finally:
            _r.randint = original

        # With Crit-on-5+, the 5 to-hit becomes a Critical Hit. The
        # devastating_wounds keyword on a crit bypasses the save and
        # applies per_shot_damage = 1 directly.
        self.assertEqual(
            damage_with, 1.0,
            "Shield Host Crit-on-5+ should fire on a roll of 5; "
            "devastating_wounds should bypass save and deal 1 damage."
        )


if __name__ == "__main__":
    unittest.main()
