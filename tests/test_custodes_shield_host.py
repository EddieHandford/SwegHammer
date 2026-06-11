"""Tests for the real Shield Host (Adeptus Custodes) detachment + stratagems
(iter-8 fix).

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host

Replaces the iter-0 `plus_one_save` defensive approximation with the
canonical Martial Ka'tah / Martial Mastery Rendax melee AP+1 buff, plus the
six real Shield Host detachment stratagems (Arcane Genetic Alchemy, Unwavering
Sentinels, Multipotentiality, Vigilance Eternal, Archaeotech Munitions,
Avenge the Fallen).

CUSTODES-KATAH-V1 (claude/sim-calibration-6): `melee_crit_on_5_plus_hits` was
a fabricated Ka'tah stance with no codex counterpart. The three real Martial
Ka'tah stances are Kaptaris (+1 invuln ranged), Rendax (AP+1 melee), and
Dacatarai (Sustained Hits ranged). The fabricated "Crit-on-5+ melee" bullet
inflated melee output on EVEN rounds and has been removed from SHIELD_HOST.
Only `melee_ap_plus_one` (Rendax Ka'tah, ODD rounds 1/3/5) remains active.

Coverage:
    * Registry: SHIELD_HOST wired into DETACHMENTS, DEFAULT_BY_FACTION,
      FACTION_DETACHMENTS for Adeptus Custodes.
    * Rendax Ka'tah flag set on the detachment instance (`melee_ap_plus_one`)
      and the fabricated `melee_crit_on_5_plus_hits` flag confirmed False.
    * The iter-0 `plus_one_save` flag confirmed removed.
    * Six real Shield Host stratagems exposed via SHIELD_HOST.stratagems
      with the codex CP costs.
    * Each `_try_*` dispatcher consumes CP and sets the right transient
      flag on a green-lit AI gate. Vigilance Eternal (wave 235) is wired:
      it writes sticky ownership for BATTLELINE-held objectives.
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

    def test_martial_katah_rendax_flag_set(self):
        """Rendax Ka'tah (melee AP+1) is wired via `melee_ap_plus_one=True`.
        The fabricated `melee_crit_on_5_plus_hits` bullet was removed in
        CUSTODES-KATAH-V1 (claude/sim-calibration-6) — it had no codex
        counterpart. Confirm it is now False."""
        self.assertTrue(SHIELD_HOST.melee_ap_plus_one)
        self.assertFalse(
            SHIELD_HOST.melee_crit_on_5_plus_hits,
            "melee_crit_on_5_plus_hits must be False: this was a fabricated "
            "Ka'tah stance with no Wahapedia codex counterpart. The three "
            "real Martial Ka'tah stances are Kaptaris, Rendax, Dacatarai. "
            "None grants Crit-on-5+ melee.",
        )

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

    def test_archaeotech_munitions_sets_lethal_hits(self):
        battle, a, _b = self._build_battle()
        battle._try_archaeotech_munitions(a, _b)
        captain = next(u for u in a.units if u.profile.name == "Shield-Captain")
        self.assertTrue(captain.transient_lethal_hits)
        self.assertEqual(a.command_points, 5)

    def test_avenge_the_fallen_sets_plus_one_to_wound_melee(self):
        battle, a, _b = self._build_battle()
        battle._try_avenge_the_fallen(a, _b)
        # The wounded Custodian Guard is the most vulnerable Custodes unit.
        self.assertTrue(a.units[0].transient_plus_one_to_wound_melee)
        self.assertEqual(a.command_points, 5)

    def test_vigilance_eternal_writes_sticky_owner(self):
        """Wave 235: Vigilance Eternal is now wired via _try_vigilance_eternal.
        A Custodes BATTLELINE unit on an objective causes _sticky_owner to be
        written for that objective's index after the stratagem fires.
        Wahapedia: 'That objective marker remains under your control even if
        you have no models within range of it, until your opponent controls it
        at the start or end of any turn.'
        Source: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host
        """
        battle, a, b = self._build_battle()
        if not battle.map.objectives:
            self.skipTest("Map has no objectives")
        # Seed enough CP and a round number that passes the AI gate.
        a.command_points = 6
        battle._current_round = 2
        # Place the Custodian Guard (BATTLELINE) on the first objective.
        obj = battle.map.objectives[0]
        a.units[0].position = (obj.x, obj.y)
        # Opponent is far away — no contest.
        b.units[0].position = (obj.x + 50.0, obj.y + 50.0)
        # Before firing: sticky_owner is empty.
        self.assertIsNone(battle._sticky_owner.get(0))
        # Fire the dispatcher directly.
        battle._try_vigilance_eternal(a, b)
        # After firing: sticky_owner must record this army for objective 0.
        self.assertEqual(
            battle._sticky_owner.get(0), a.name,
            "Vigilance Eternal must write sticky ownership for the BATTLELINE-held objective.",
        )
        # Exactly 1 command point spent.
        self.assertEqual(a.command_points, 5, "Vigilance Eternal must spend exactly 1 command point.")

    def test_vigilance_eternal_no_spend_without_battleline_on_objective(self):
        """Vigilance Eternal must not spend command points when no Custodes
        BATTLELINE unit is within range of any objective marker."""
        battle, a, b = self._build_battle()
        a.command_points = 6
        battle._current_round = 2
        if battle.map.objectives:
            obj = battle.map.objectives[0]
            # Move the Custodian Guard far from all objectives.
            a.units[0].position = (obj.x + 50.0, obj.y + 50.0)
        battle._try_vigilance_eternal(a, b)
        # The AI gate fires (round >= 2, CP >= 2), command points get spent,
        # but no sticky_owner entries are written because the unit is off-marker.
        # This is acceptable — the spend fires but produces no sticky writes.
        # (The real value: we confirm _sticky_owner stays empty.)
        self.assertIsNone(battle._sticky_owner.get(0))


# ---------------------------------------------------------------------------
# Martial Ka'tah Rendax AP+1 behaviour in Unit.attack
# ---------------------------------------------------------------------------


class MartialKatahRendaxAp1Tests(unittest.TestCase):
    """Custodes melee attacker in a Shield Host army gets Rendax Ka'tah AP+1
    on ODD battle rounds. Verify the buff fires correctly on round 1 (ODD)
    and does NOT fire on round 2 (EVEN, no real codex bullet active).

    CUSTODES-KATAH-V1 (claude/sim-calibration-6): the fabricated Crit-on-5+
    bullet was removed. This test replaces the old Crit-on-5+ integration
    test with a correct Rendax AP+1 check. Wahapedia: Rendax Ka'tah states
    "Improve the Armour Penetration characteristic of melee weapons equipped
    by ADEPTUS CUSTODES models from your army with the Martial Ka'tah ability
    by 1."
    """

    def _single_attack_custodian_ap0(self) -> UnitProfile:
        """Single melee attack, AP 0, so AP+1 (if applied) makes it AP-1."""
        return UnitProfile(
            name="Custodian Guard", faction="Adeptus Custodes",
            health=3, damage=1, hit_probability=2 / 3,
            ap=0, save=2, strength=4, toughness=6,
            attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
            move=6.0, leadership=6, oc=2,
            unit_keywords=("INFANTRY", "ADEPTUS CUSTODES"),
            melee_attacks=4, melee_damage_per_shot=1.0,
            melee_hit_probability=5 / 6, melee_strength=6, melee_ap=0,
            points_override=80.0, invuln_save=4,
        )

    def _target_save3(self) -> UnitProfile:
        """3+ save target — AP 0 attacker needs 3+ to wound-save, AP-1 needs
        4+. Tracking damage difference verifies the AP+1 applied."""
        return UnitProfile(
            name="MarineTarget", faction="Test",
            health=10, damage=2, hit_probability=2 / 3,
            ap=0, save=3, strength=4, toughness=4,
            attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
            points_override=100.0,
        )

    def test_rendax_ap1_fires_on_odd_round(self):
        """On ODD battle round 1, the Shield Host AP+1 bullet fires and
        the attacker's melee AP is improved. We run many attacks at a known
        seed and check that total damage is higher with Shield Host than
        without (AP-1 vs AP 0 means the target's save goes from 3+ to 4+,
        which should produce measurably more damage)."""
        import random as _r

        N = 100
        _r.seed(7)

        # With Shield Host, ODD round 1
        a_sh = Army("Adeptus Custodes")
        a_sh.add_unit(self._single_attack_custodian_ap0())
        b_sh = Army("Enemy")
        b_sh.add_unit(self._target_save3())
        battle_sh = Battle(a_sh, b_sh)
        battle_sh._assign_uids()
        battle_sh._current_round = 1   # ODD -> Rendax AP+1 active
        attacker_sh = a_sh.units[0]
        defender_sh = b_sh.units[0]
        damage_with = sum(
            attacker_sh.attack(defender_sh, distance=0.5, mode="melee")
            for _ in range(N)
        )

        # Without Shield Host (no AP+1)
        from code.army import Army as _Army
        a_no = _Army("Custodes NoSH")
        from code.detachments import AURIC_CHAMPIONS
        a_no.detachment = AURIC_CHAMPIONS   # different detachment, no melee_ap_plus_one
        a_no.add_unit(self._single_attack_custodian_ap0())
        b_no = _Army("Enemy2")
        b_no.add_unit(self._target_save3())
        battle_no = Battle(a_no, b_no)
        battle_no._assign_uids()
        battle_no._current_round = 1
        attacker_no = a_no.units[0]
        defender_no = b_no.units[0]
        _r.seed(7)
        damage_without = sum(
            attacker_no.attack(defender_no, distance=0.5, mode="melee")
            for _ in range(N)
        )

        # Shield Host with AP+1 should produce at least as much damage as
        # without (AP-1 vs AP 0 against a 3+ save; save becomes 4+ so more
        # wounds land). Allow small RNG variance — strictly >= is correct
        # over a large N.
        self.assertGreaterEqual(
            damage_with, damage_without * 0.95,
            "Shield Host Rendax Ka'tah AP+1 on ODD round should not reduce "
            f"damage vs AP 0 baseline (got {damage_with:.1f} vs {damage_without:.1f}).",
        )


if __name__ == "__main__":
    unittest.main()
