"""Tests for task #168 — Synapse anti-swarm depth + Battleshock punishment.

Two themes:
  Part A — Battleshock stratagem-lockout. 10e core rule: while a unit is
    Battle-shocked, OC drops to 0 AND it cannot be the subject of any
    stratagem. The simulator's `_run_battleshock_phase` populates
    `_battleshocked_this_round` BEFORE `_apply_detachment_stratagems`
    runs, and the friendly/enemy target pickers
    (`_highest_dpa_unit`, `_most_vulnerable_unit`,
    `_highest_threat_enemy`) skip battleshocked uids.
  Part B — Synapse-source target priority. Non-Tyranid attackers bias
    toward SYNAPSE units (Hive Tyrant, Tervigon) so killing them revokes
    the swarm's Battle-shock auto-pass shelter. Symmetric Tyranid
    attackers do NOT get the bonus.
"""

from __future__ import annotations

import unittest

from code.army import Army
from code.simulator import Battle
from code.strategy import (
    _is_synapse_source,
    _melee_target_score,
    _synapse_target_bonus,
)
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile builders
# ---------------------------------------------------------------------------


def _marine_shooter() -> UnitProfile:
    return UnitProfile(
        name="Intercessor Squad", faction="Adeptus Astartes",
        health=2, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, attacks=2, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24, toughness=4,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        unit_keywords=("INFANTRY",),
        oc=2,
    )


def _hive_tyrant() -> UnitProfile:
    """SYNAPSE source — Tyranid Hive Tyrant. T9 W12 + SYNAPSE keyword."""
    return UnitProfile(
        name="Hive Tyrant", faction="Tyranids",
        health=12, damage=4, hit_probability=2 / 3,
        ap=-2, save=2, attacks=4, weapon_damage_per_shot=2.0,
        strength=7, range_inches=24, toughness=9,
        melee_attacks=6, melee_damage_per_shot=3.0,
        melee_hit_probability=2 / 3, melee_strength=8, melee_ap=-3,
        unit_keywords=("MONSTER", "CHARACTER", "PSYKER", "SYNAPSE"),
        oc=3,
        leadership=6,
    )


def _carnifex() -> UnitProfile:
    """Non-SYNAPSE Tyranid brick — same toughness shape as a Hive Tyrant
    but without the SYNAPSE keyword. Used as the control."""
    return UnitProfile(
        name="Carnifex", faction="Tyranids",
        health=8, damage=0, hit_probability=2 / 3,
        ap=-1, save=2, attacks=4, weapon_damage_per_shot=3.0,
        strength=8, range_inches=24, toughness=9,
        melee_attacks=6, melee_damage_per_shot=3.0,
        melee_hit_probability=2 / 3, melee_strength=9, melee_ap=-2,
        unit_keywords=("MONSTER",),
        oc=0,
    )


def _tyranid_warrior_attacker() -> UnitProfile:
    """A Tyranid attacker probing the intra-faction gate — no bonus."""
    return UnitProfile(
        name="Tyranid Warriors", faction="Tyranids",
        health=3, damage=1, hit_probability=2 / 3,
        ap=-1, save=4, attacks=2, weapon_damage_per_shot=1.0,
        strength=5, range_inches=18, toughness=5,
        melee_attacks=3, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5, melee_ap=-1,
        unit_keywords=("INFANTRY",),
        oc=2,
    )


def _make_army(name: str, profiles, positions) -> Army:
    """Build an Army with one unit per profile/position, assigning fixed uids."""
    army = Army(name)
    for p in profiles:
        army.add_unit(p)
    for i, (u, pos) in enumerate(zip(army.units, positions)):
        u.uid = f"{name[0]}{i}"
        u.position = pos
    return army


# ---------------------------------------------------------------------------
# Part B — Synapse-source target priority
# ---------------------------------------------------------------------------


class SynapseTargetBonusHelperTests(unittest.TestCase):
    """The `_is_synapse_source` and `_synapse_target_bonus` helpers directly."""

    def test_hive_tyrant_is_synapse_source(self):
        self.assertTrue(_is_synapse_source(_hive_tyrant()))

    def test_carnifex_is_not_synapse_source(self):
        self.assertFalse(_is_synapse_source(_carnifex()))

    def test_marine_attacker_gets_bonus_vs_tyrant(self):
        marine_army = _make_army("A", [_marine_shooter()], [(0.0, 0.0)])
        tyrant_army = _make_army("E", [_hive_tyrant()], [(10.0, 0.0)])
        self.assertAlmostEqual(
            _synapse_target_bonus(marine_army.units[0], tyrant_army.units[0]),
            1.5,
        )

    def test_marine_attacker_no_bonus_vs_carnifex(self):
        marine_army = _make_army("A", [_marine_shooter()], [(0.0, 0.0)])
        fex_army = _make_army("E", [_carnifex()], [(10.0, 0.0)])
        self.assertAlmostEqual(
            _synapse_target_bonus(marine_army.units[0], fex_army.units[0]),
            1.0,
        )

    def test_tyranid_attacker_no_synapse_bonus(self):
        """Intra-faction: Tyranid attacker against a SYNAPSE source gets 1.0,
        not 1.5 — the bonus is hard-gated on non-Tyranid attackers."""
        ty_army = _make_army(
            "A", [_tyranid_warrior_attacker()], [(0.0, 0.0)],
        )
        tyrant_army = _make_army("E", [_hive_tyrant()], [(10.0, 0.0)])
        self.assertAlmostEqual(
            _synapse_target_bonus(ty_army.units[0], tyrant_army.units[0]),
            1.0,
        )


class SynapseSourceTargetedFirstTests(unittest.TestCase):
    """Marine attacker picking between Hive Tyrant (SYNAPSE) and Carnifex
    (no SYNAPSE) — Hive Tyrant should win the melee target score."""

    def test_synapse_source_targeted_first(self):
        marine_army = _make_army("A", [_marine_shooter()], [(0.0, 0.0)])
        enemy_army = _make_army(
            "E",
            [_hive_tyrant(), _carnifex()],
            [(10.0, 0.0), (10.0, 5.0)],
        )
        attacker = marine_army.units[0]
        tyrant = enemy_army.units[0]
        fex = enemy_army.units[1]
        s_tyrant = _melee_target_score(attacker, tyrant)
        s_fex = _melee_target_score(attacker, fex)
        # Hive Tyrant scores strictly higher than Carnifex for the Marine
        # attacker thanks to the 1.5x synapse bonus.
        self.assertGreater(
            s_tyrant, s_fex,
            f"Hive Tyrant (SYNAPSE) should outscore Carnifex for Marine "
            f"attackers: got tyrant={s_tyrant:.3f} vs fex={s_fex:.3f}",
        )


# ---------------------------------------------------------------------------
# Part A — Battleshock stratagem-lockout
# ---------------------------------------------------------------------------


def _dg_unit_low_hp() -> UnitProfile:
    """A Death Guard unit profile suitable for Disgustingly Resilient.
    We'll wound the instance below half-strength so battleshock fires."""
    return UnitProfile(
        name="Plague Marines", faction="Death Guard",
        health=4, damage=2, hit_probability=2 / 3,
        ap=-1, save=3, attacks=2, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24, toughness=5,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        unit_keywords=("INFANTRY", "DEATH GUARD"),
        leadership=7,
        points_override=90.0,
        oc=2,
    )


def _ts_psyker() -> UnitProfile:
    """A Thousand Sons PSYKER unit, used as a Cabbalistic Empowerment /
    Doombolt target probe."""
    return UnitProfile(
        name="Rubric Marines", faction="Thousand Sons",
        health=2, damage=1, hit_probability=2 / 3,
        ap=-1, save=3, attacks=2, weapon_damage_per_shot=1.0,
        strength=4, range_inches=24, toughness=4,
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4,
        unit_keywords=("INFANTRY", "PSYKER", "THOUSAND SONS"),
        leadership=7,
        points_override=120.0,
        oc=2,
    )


class BattleshockedFriendlyExcludedFromStratagemPickersTests(unittest.TestCase):
    """A battleshocked friendly unit must NOT be returned by the
    target-picker helpers used by the detachment stratagem dispatcher."""

    def test_battleshocked_unit_skipped_by_most_vulnerable(self):
        """Two DG plague-marine units; one is battleshocked. The defensive
        stratagem target picker must NOT pick the battleshocked one."""
        army = Army("Death Guard")
        army.add_unit(_dg_unit_low_hp())
        army.add_unit(_dg_unit_low_hp())
        opp = Army("Marines")
        opp.add_unit(_marine_shooter())
        battle = Battle(army, opp)
        battle._assign_uids()
        # Wound BOTH below half so both are otherwise eligible.
        for u in army.units:
            u.current_health = 1.0
        # Mark the FIRST unit as battleshocked.
        battle._battleshocked_this_round.add(army.units[0].uid)
        picked = battle._most_vulnerable_unit(
            army, keyword="DEATH GUARD", faction="Death Guard",
        )
        self.assertIsNotNone(picked)
        self.assertNotEqual(
            picked.uid, army.units[0].uid,
            "Battle-shocked DG unit must be excluded from stratagem target pool",
        )
        self.assertEqual(picked.uid, army.units[1].uid)

    def test_battleshocked_unit_skipped_by_highest_dpa(self):
        """Same shape for the offensive stratagem picker (Plague Weapons / etc.)."""
        army = Army("Death Guard")
        army.add_unit(_dg_unit_low_hp())
        army.add_unit(_dg_unit_low_hp())
        opp = Army("Marines")
        opp.add_unit(_marine_shooter())
        battle = Battle(army, opp)
        battle._assign_uids()
        battle._battleshocked_this_round.add(army.units[0].uid)
        picked = battle._highest_dpa_unit(
            army, keyword="DEATH GUARD", faction="Death Guard",
        )
        self.assertIsNotNone(picked)
        self.assertNotEqual(picked.uid, army.units[0].uid)

    def test_battleshocked_enemy_skipped_by_highest_threat(self):
        """Doombolt / Cabbalistic Empowerment look up the enemy via
        `_highest_threat_enemy`; battleshocked enemies must be excluded too
        (10e: 'you cannot use Stratagems to affect that unit' is sided on
        the subject unit, not the controller)."""
        army = Army("Thousand Sons")
        army.add_unit(_ts_psyker())
        opp = Army("Death Guard")
        opp.add_unit(_dg_unit_low_hp())
        opp.add_unit(_dg_unit_low_hp())
        battle = Battle(army, opp)
        battle._assign_uids()
        # Mark first DG as battleshocked (the highest-threat target by raw HP)
        battle._battleshocked_this_round.add(opp.units[0].uid)
        picked = battle._highest_threat_enemy(opp)
        self.assertIsNotNone(picked)
        self.assertNotEqual(picked.uid, opp.units[0].uid)
        self.assertEqual(picked.uid, opp.units[1].uid)

    def test_battleshocked_unit_cannot_be_strat_target(self):
        """End-to-end: with only ONE eligible DG unit (and it's battleshocked),
        `_most_vulnerable_unit` returns None when restricted to DG — and the
        unrestricted fallback also returns None because the battleshocked
        unit is excluded from the global pool too."""
        army = Army("Death Guard")
        army.add_unit(_dg_unit_low_hp())
        opp = Army("Marines")
        opp.add_unit(_marine_shooter())
        battle = Battle(army, opp)
        battle._assign_uids()
        army.units[0].current_health = 1.0
        battle._battleshocked_this_round.add(army.units[0].uid)
        picked_filtered = battle._most_vulnerable_unit(
            army, keyword="DEATH GUARD", faction="Death Guard",
        )
        picked_fallback = battle._most_vulnerable_unit(army)
        self.assertIsNone(
            picked_filtered,
            "DG-filtered pick must be None when the only DG unit is "
            "battle-shocked",
        )
        self.assertIsNone(
            picked_fallback,
            "Unrestricted fallback also returns None — the battleshocked "
            "unit is excluded from the global pool",
        )


class BattleshockRunsBeforeStratagemsTests(unittest.TestCase):
    """Architectural: `_run_battleshock_phase` populates the set early
    enough for the stratagem dispatcher to see it."""

    def test_run_battleshock_phase_is_a_separate_method(self):
        """The phase must be extractable so the round-start dispatcher
        order is explicit. Regression-guards against silently inlining
        battleshock back into _run_round below the stratagem dispatcher
        (where it was before task #168)."""
        self.assertTrue(
            hasattr(Battle, "_run_battleshock_phase"),
            "_run_battleshock_phase must exist as a Battle method",
        )

    def test_round_one_skips_battleshock(self):
        """Round 1 has no battleshock step — the method returns without
        touching the set."""
        army = Army("Death Guard")
        army.add_unit(_dg_unit_low_hp())
        opp = Army("Marines")
        opp.add_unit(_marine_shooter())
        battle = Battle(army, opp)
        battle._assign_uids()
        army.units[0].current_health = 1.0   # below half
        battle._run_battleshock_phase(1)
        self.assertEqual(
            battle._battleshocked_this_round, set(),
            "Round 1 must skip the battleshock step",
        )


if __name__ == "__main__":
    unittest.main()
