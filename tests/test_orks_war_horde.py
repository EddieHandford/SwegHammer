"""Tests for the real War Horde (Orks) detachment + stratagems (iter-1 B1).

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde
BSData v10.6.0 verbatim detachment rule "Get Stuck In": "Melee weapons
equipped by ORKS models from your army have the [SUSTAINED HITS 1] ability."

Coverage:
    * Registry: WAR_HORDE wired into DETACHMENTS, DEFAULT_BY_FACTION["Orks"],
      FACTION_DETACHMENTS["Orks"].
    * Six real War Horde stratagems exposed via WAR_HORDE.stratagems with
      the codex CP costs.
    * Each stratagem constant carries the canonical name (matched verbatim
      by the simulator's dispatcher block).
    * Get Stuck In flag wired into Unit.attack — an ORKS melee attacker
      in a War Horde army has effective_sustained_hits incremented by 1.
    * Smoke test: an Orks army with the War Horde detachment runs a full
      Battle.run() without raising.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.detachments import (
    DEFAULT_BY_FACTION, DETACHMENTS, FACTION_DETACHMENTS, WAR_HORDE,
)
from code.simulator import Battle
from code.stratagems import (
    BIG_KRUMPIN, DA_BIGGEST_BOSS, INSANE_BRAVERY, MOB_UP,
    POWER_OF_THE_WAAAGH, TELLYPORTA, WAR_HORDE_STRATAGEMS,
)
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _boyz_profile() -> UnitProfile:
    """A 100+ point Orks melee brick — passes the AI gate for the 1-CP
    War Horde melee stratagems. Health 6 (single-unit multi-wound chassis
    so the Mob Up max_hp >= 4.0 gate clears in tests)."""
    return UnitProfile(
        name="Boyz", faction="Orks",
        health=6, damage=1, hit_probability=0.5,
        ap=0, save=6, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        move=6.0, leadership=7, oc=2,
        unit_keywords=("INFANTRY", "ORKS"),
        melee_attacks=20, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=120.0,
    )


def _boyz_profile_single_attack() -> UnitProfile:
    """Single-melee-attack variant used by the Get Stuck In integration
    test (deterministic randint sequence requires exactly one to-hit roll)."""
    return UnitProfile(
        name="Boyz", faction="Orks",
        health=6, damage=1, hit_probability=0.5,
        ap=0, save=6, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        move=6.0, leadership=7, oc=2,
        unit_keywords=("INFANTRY", "ORKS"),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=0.5, melee_strength=4, melee_ap=0,
        points_override=120.0,
    )


def _warboss_profile() -> UnitProfile:
    """An Orks CHARACTER for Da Biggest Boss targeting."""
    return UnitProfile(
        name="Warboss", faction="Orks",
        health=6, damage=2, hit_probability=2 / 3,
        ap=-1, save=4, strength=6, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        move=6.0, leadership=6, oc=2,
        unit_keywords=("INFANTRY", "ORKS", "CHARACTER"),
        melee_attacks=6, melee_damage_per_shot=2.0,
        melee_hit_probability=2 / 3, melee_strength=8, melee_ap=-2,
        points_override=80.0,
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


class WarHordeRegistryTests(unittest.TestCase):

    def test_war_horde_in_detachments(self):
        self.assertIn("war_horde", DETACHMENTS)
        self.assertIs(DETACHMENTS["war_horde"], WAR_HORDE)

    def test_default_by_faction_orks(self):
        self.assertEqual(DEFAULT_BY_FACTION["Orks"], "war_horde")

    def test_faction_detachments_orks(self):
        self.assertEqual(FACTION_DETACHMENTS["Orks"], ("war_horde",))

    def test_get_stuck_in_flag_set(self):
        """The detachment rule (Get Stuck In) is wired as the boolean flag
        `melee_sustained_hits_army_wide` per BSData v10.6.0 verbatim text."""
        self.assertTrue(WAR_HORDE.melee_sustained_hits_army_wide)
        # War Horde shouldn't carry any of the legacy +1-to-X passives.
        self.assertFalse(WAR_HORDE.plus_one_to_hit)
        self.assertFalse(WAR_HORDE.plus_one_to_wound)
        self.assertFalse(WAR_HORDE.reroll_hit_ones)


# ---------------------------------------------------------------------------
# Stratagem CP costs + names
# ---------------------------------------------------------------------------


class WarHordeStratagemsTests(unittest.TestCase):
    """The six real War Horde stratagems must be attached to the detachment
    by canonical name + CP cost, and exposed via WAR_HORDE.stratagems."""

    EXPECTED = (
        ("Insane Bravery (War Horde)", 1),
        ("Power Of The WAAAGH!", 1),
        ("Mob Up", 1),
        ("Big Krumpin'", 2),
        ("Tellyporta", 1),
        ("Da Biggest Boss", 1),
    )

    def test_six_stratagems_attached_to_detachment(self):
        attached = {s.name: s.cp_cost for s in WAR_HORDE.stratagems}
        for name, cp in self.EXPECTED:
            self.assertIn(name, attached, f"{name} missing from WAR_HORDE.stratagems")
            self.assertEqual(
                attached[name], cp,
                f"{name} expected {cp} CP, got {attached[name]}",
            )

    def test_war_horde_stratagems_tuple_matches_attached(self):
        # WAR_HORDE_STRATAGEMS exported by code.stratagems is the same tuple
        # the detachment is built with.
        self.assertEqual(WAR_HORDE.stratagems, WAR_HORDE_STRATAGEMS)

    def test_constants_exist_and_named_correctly(self):
        # Each constant carries the canonical name (matches what the
        # dispatcher in _apply_detachment_stratagems looks for).
        self.assertEqual(INSANE_BRAVERY.name, "Insane Bravery (War Horde)")
        self.assertEqual(POWER_OF_THE_WAAAGH.name, "Power Of The WAAAGH!")
        self.assertEqual(MOB_UP.name, "Mob Up")
        self.assertEqual(BIG_KRUMPIN.name, "Big Krumpin'")
        self.assertEqual(TELLYPORTA.name, "Tellyporta")
        self.assertEqual(DA_BIGGEST_BOSS.name, "Da Biggest Boss")


# ---------------------------------------------------------------------------
# Dispatcher wiring — five wired stratagems set their transient flag
# ---------------------------------------------------------------------------


class WarHordeDispatcherTests(unittest.TestCase):
    """The simulator's `_try_*` dispatchers must each consume CP and set
    the right transient flag on a green-lit AI gate. Insane Bravery is
    intentionally no-op (APPROXIMATION)."""

    def _build_battle(self, cp: int = 6):
        a = Army("Orks")
        a.add_unit(_boyz_profile())
        a.add_unit(_warboss_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        battle._assign_uids()
        a.command_points = cp
        # Wound the Boyz (max 6 HP → 2.0 = 67% loss) so vulnerability +
        # reanimation gates clear (Mob Up requires hp_frac >= 0.3 AND
        # max_hp >= 4.0; Tellyporta requires hp_frac > 0.3 AND cost >= 80).
        a.units[0].current_health = 2.0
        battle._current_round = 2
        return battle, a, b

    def test_power_of_the_waaagh_sets_lethal_hits(self):
        # ST-1 corrected Power of the WAAAGH! from the +1-to-wound proxy to
        # transient_lethal_hits, which matches the codex "LETHAL HITS" text
        # (auto-wound on natural 6s only, ~17% yield vs ~25% for +1-to-wound).
        battle, a, _b = self._build_battle()
        battle._try_power_of_the_waaagh(a, _b)
        # The Boyz are the highest-DPA Orks melee unit.
        self.assertTrue(a.units[0].transient_lethal_hits)
        self.assertEqual(a.command_points, 5)

    def test_mob_up_sets_undying_legions_pulse(self):
        battle, a, _b = self._build_battle()
        battle._try_mob_up(a, _b)
        # The wounded Boyz is the most vulnerable Orks unit.
        self.assertEqual(a.units[0].transient_undying_legions_pulse, 2)
        self.assertEqual(a.command_points, 5)

    def test_big_krumpin_sets_reroll_wounds_ones(self):
        # ST-1 corrected Big Krumpin' from the +1-to-wound proxy to
        # transient_reroll_wounds_ones (1s-only re-roll, ~14% yield vs ~25%
        # for +1-to-wound, closer to the codex re-roll-wound-1s wording).
        battle, a, _b = self._build_battle()
        battle._try_big_krumpin(a, _b)
        self.assertTrue(a.units[0].transient_reroll_wounds_ones)
        self.assertEqual(a.command_points, 4)   # 2 command points

    def test_tellyporta_sets_plus_one_save(self):
        battle, a, _b = self._build_battle()
        battle._try_tellyporta(a, _b)
        self.assertTrue(a.units[0].transient_plus_one_save)
        self.assertEqual(a.command_points, 5)

    def test_da_biggest_boss_sets_assault_this_round(self):
        battle, a, _b = self._build_battle()
        battle._try_da_biggest_boss(a, _b)
        # The Warboss is the highest-DPA Orks CHARACTER.
        warboss = next(u for u in a.units if u.profile.name == "Warboss")
        self.assertTrue(warboss.transient_assault_this_round)
        self.assertEqual(a.command_points, 5)


# ---------------------------------------------------------------------------
# Get Stuck In: melee SUSTAINED HITS 1 in Unit.attack
# ---------------------------------------------------------------------------


class GetStuckInIntegrationTests(unittest.TestCase):
    """`Unit.attack` must read `WAR_HORDE.melee_sustained_hits_army_wide`
    on an Orks melee attacker and increment the effective sustained-hits
    multiplier by 1."""

    def test_get_stuck_in_drives_extra_hit_on_crit(self):
        """Force a deterministic crit-to-hit and confirm the +1 sustained
        hit lands. We monkeypatch `random.randint` to force a 6 on the
        first to-hit roll and otherwise force wound rolls to succeed,
        save rolls to fail. The expected hits-into-the-target should be
        2 (1 base + 1 sustained from Get Stuck In), not 1.
        """
        import random as _r

        a = Army("Orks")
        a.add_unit(_boyz_profile_single_attack())   # melee_attacks=1
        b = Army("Enemy")
        b.add_unit(_target_profile())
        battle = Battle(a, b)
        battle._assign_uids()
        attacker = a.units[0]
        defender = b.units[0]

        # Sequence the randint stream: hit (6 → crit), then for each
        # of the 2 expected hits: wound (6 → success), save (1 → fail).
        rolls = iter([6, 6, 1, 6, 1])
        original = _r.randint

        def fake_randint(lo, hi):
            try:
                return next(rolls)
            except StopIteration:
                return original(lo, hi)

        _r.randint = fake_randint
        try:
            damage = attacker.attack(defender, distance=0.5, mode="melee")
        finally:
            _r.randint = original
        # 2 hits × melee_damage_per_shot 1 = 2 raw damage. If Get Stuck
        # In didn't fire, we'd only see 1 damage.
        self.assertEqual(damage, 2.0)


# ---------------------------------------------------------------------------
# End-to-end smoke test — a full Battle runs without error
# ---------------------------------------------------------------------------


class WarHordeSmokeTest(unittest.TestCase):
    """An Orks army with the War Horde detachment selected should run a
    full Battle.run() to completion. Catches integration bugs in the
    dispatcher / strategy / Unit.attack wiring that wouldn't show in
    unit tests but would break a real battle."""

    def test_battle_runs_without_error(self):
        a = Army("Orks")
        a.add_unit(_boyz_profile())
        a.add_unit(_warboss_profile())
        b = Army("Enemy")
        b.add_unit(_target_profile())
        random.seed(2026)
        battle = Battle(a, b)
        result = battle.run()
        # Battle completes and returns a BattleResult with a winner
        # (could be either side, or a draw — we don't assert which).
        self.assertIsNotNone(result)
        # Confirm the detachment resolved to War Horde for the Orks army.
        self.assertIs(a.resolve_detachment(), WAR_HORDE)


if __name__ == "__main__":
    unittest.main()
