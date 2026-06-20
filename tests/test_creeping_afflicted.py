"""Tests for SWEG_CREEPING_AFFLICTED gate on Creeping Blight (Virulent
Vectorium, Death Guard 10e).

Real rule (Goonhammer / Wargamer; Wahapedia unreachable at build time):
  WHEN: Your Shooting phase.
  TARGET: One DEATH GUARD INFANTRY unit from your army that has not been
          selected to shoot this phase.
  EFFECT: Until the end of the phase, each time a model in your unit makes a
          ranged attack that targets an AFFLICTED unit, you can re-roll the Hit
          roll and you can re-roll the Wound roll.

Afflicted in Death Guard 10e = an enemy unit within 3" of a DEATH GUARD model
(Nurgle's Gift; proxied by `_is_near_enemy_dg_model(unit, radius=3.0)` in
code/units.py line 163).

SWEG_CREEPING_AFFLICTED (default "0"):
  "0" (OFF / legacy): re-roll flags applied unconditionally — byte-identical to
      pre-gate behaviour.
  "1" (ON): re-roll flags applied ONLY when the target is Afflicted (within 3"
      of any DEATH GUARD model).  Command point is still spent either way.

These tests are fast (no sim games).  They drive `Battle._try_creeping_blight`
directly and inspect the transient flags on the candidate unit.
"""

from __future__ import annotations

import os
import random
import unittest
from unittest import mock

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _plague_marine() -> UnitProfile:
    """Death Guard INFANTRY — the Creeping Blight candidate."""
    return UnitProfile(
        name="Plague Marines",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, oc=2,
        faction="Death Guard",
        fnp=5,
        unit_keywords=("INFANTRY",),
        melee_attacks=2, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        points_override=100,
    )


def _marine(name: str = "Marine") -> UnitProfile:
    """Generic non-DG target unit."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7, oc=2,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
        points_override=80,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_battle(
    dg_position: tuple[float, float] = (10.0, 10.0),
    enemy_position: tuple[float, float] = (20.0, 10.0),
) -> tuple[Battle, Army, Army]:
    """Build a minimal DG-vs-Astartes battle with one Plague Marine squad and
    one Marine squad, positioned at the given coordinates.  Returns
    (battle, dg_army, enemy_army).
    """
    dg = Army("Death Guard")
    dg.add_unit(_plague_marine())
    ast = Army("Astartes")
    ast.add_unit(_marine())

    battle = Battle(dg, ast)
    battle._assign_uids()

    # Wire army back-references so _is_near_enemy_dg_model can traverse armies.
    dg._battle_ref = battle
    ast._battle_ref = battle

    # Position units.
    battle.a.units[0].position = dg_position
    battle.b.units[0].position = enemy_position

    # Give DG enough command points to fire Creeping Blight.
    dg.command_points = 5

    # Place the battle in round 3 so round-gating heuristics don't block.
    battle._current_round = 3

    return battle, dg, ast


# ---------------------------------------------------------------------------
# Gate ON (SWEG_CREEPING_AFFLICTED=1)
# ---------------------------------------------------------------------------


class CreepingBlightGateONTests(unittest.TestCase):
    """When SWEG_CREEPING_AFFLICTED=1, re-roll flags must ONLY be applied when
    the chosen target is Afflicted (within 3\" of any DEATH GUARD model).

    The DG Plague Marines serve as BOTH the Creeping Blight candidate AND the
    Affliction source.  Placing the enemy within 3\" of the Plague Marines
    makes the enemy Afflicted; placing the enemy far away makes it not
    Afflicted.
    """

    def test_afflicted_target_receives_reroll_buff(self):
        """Gate ON + target within 3\" of DG model (Afflicted) → both
        transient_reroll_hits_shooting and transient_reroll_wounds are set on
        the DG INFANTRY candidate."""
        random.seed(0)
        # Place Plague Marines at (10, 10); enemy 2\" away — within the 3\"
        # Afflicted radius.
        battle, dg, ast = _build_battle(
            dg_position=(10.0, 10.0),
            enemy_position=(12.0, 10.0),
        )
        candidate = battle.a.units[0]
        # Sanity: gate is OFF by default, so confirm no pre-existing flag.
        self.assertFalse(
            getattr(candidate, "transient_reroll_hits_shooting", False),
        )
        with mock.patch.dict(os.environ, {"SWEG_CREEPING_AFFLICTED": "1"}):
            battle._try_creeping_blight(dg, ast)

        self.assertTrue(
            getattr(candidate, "transient_reroll_hits_shooting", False),
            "Afflicted target (2\" from DG) — hit re-roll flag must be set",
        )
        self.assertTrue(
            getattr(candidate, "transient_reroll_wounds", False),
            "Afflicted target (2\" from DG) — wound re-roll flag must be set",
        )

    def test_non_afflicted_target_receives_no_reroll_buff(self):
        """Gate ON + target far from DG models (NOT Afflicted) → neither
        transient_reroll_hits_shooting nor transient_reroll_wounds is set on
        the DG INFANTRY candidate."""
        random.seed(0)
        # Place Plague Marines at (10, 10); enemy 20\" away — well outside 3\".
        battle, dg, ast = _build_battle(
            dg_position=(10.0, 10.0),
            enemy_position=(30.0, 10.0),
        )
        candidate = battle.a.units[0]

        with mock.patch.dict(os.environ, {"SWEG_CREEPING_AFFLICTED": "1"}):
            battle._try_creeping_blight(dg, ast)

        self.assertFalse(
            getattr(candidate, "transient_reroll_hits_shooting", False),
            "Non-Afflicted target (20\" from DG) — hit re-roll flag must NOT be set",
        )
        self.assertFalse(
            getattr(candidate, "transient_reroll_wounds", False),
            "Non-Afflicted target (20\" from DG) — wound re-roll flag must NOT be set",
        )

    def test_cp_spent_regardless_of_afflicted_status(self):
        """Gate ON: the command point is spent even when the target is NOT
        Afflicted.  Gating the CP spend would reallocate the saved point and
        cause back-fire (Conquering Tyrant lesson, commit 868f9a4)."""
        random.seed(0)
        # Non-Afflicted (far) target.
        battle, dg, ast = _build_battle(
            dg_position=(10.0, 10.0),
            enemy_position=(30.0, 10.0),
        )
        cp_before = dg.command_points

        with mock.patch.dict(os.environ, {"SWEG_CREEPING_AFFLICTED": "1"}):
            battle._try_creeping_blight(dg, ast)

        self.assertLess(
            dg.command_points, cp_before,
            "Command point must be spent even when target is not Afflicted "
            "(the firing is not gated — only the buff application is)",
        )

    def test_exactly_at_3_inch_boundary_is_afflicted(self):
        """A target at exactly 3\" from a DG model is within the Afflicted
        radius (the check uses <=, matching _is_near_enemy_dg_model behaviour).
        """
        random.seed(0)
        battle, dg, ast = _build_battle(
            dg_position=(10.0, 10.0),
            enemy_position=(13.0, 10.0),  # exactly 3.0" away
        )
        candidate = battle.a.units[0]

        with mock.patch.dict(os.environ, {"SWEG_CREEPING_AFFLICTED": "1"}):
            battle._try_creeping_blight(dg, ast)

        self.assertTrue(
            getattr(candidate, "transient_reroll_hits_shooting", False),
            "Target at exactly 3\" is Afflicted (<=3\" check) — buff must apply",
        )
        self.assertTrue(
            getattr(candidate, "transient_reroll_wounds", False),
            "Target at exactly 3\" is Afflicted (<=3\" check) — buff must apply",
        )


# ---------------------------------------------------------------------------
# Gate OFF (SWEG_CREEPING_AFFLICTED=0 — default / legacy)
# ---------------------------------------------------------------------------


class CreepingBlightGateOFFTests(unittest.TestCase):
    """When SWEG_CREEPING_AFFLICTED=0 (default), the re-roll flags are applied
    unconditionally regardless of the target's Afflicted status — byte-identical
    to pre-gate legacy behaviour."""

    def test_off_always_applies_buff_for_afflicted_target(self):
        """Gate OFF + Afflicted target → flags set (same as before gate)."""
        random.seed(0)
        battle, dg, ast = _build_battle(
            dg_position=(10.0, 10.0),
            enemy_position=(12.0, 10.0),  # Afflicted (2" away)
        )
        candidate = battle.a.units[0]

        with mock.patch.dict(os.environ, {"SWEG_CREEPING_AFFLICTED": "0"}):
            battle._try_creeping_blight(dg, ast)

        self.assertTrue(
            getattr(candidate, "transient_reroll_hits_shooting", False),
            "Gate OFF + Afflicted target — hit re-roll flag must be set (legacy)",
        )
        self.assertTrue(
            getattr(candidate, "transient_reroll_wounds", False),
            "Gate OFF + Afflicted target — wound re-roll flag must be set (legacy)",
        )

    def test_off_always_applies_buff_for_non_afflicted_target(self):
        """Gate OFF + non-Afflicted target (far away) → flags STILL set
        (legacy unconditional behaviour; no Afflicted check)."""
        random.seed(0)
        battle, dg, ast = _build_battle(
            dg_position=(10.0, 10.0),
            enemy_position=(30.0, 10.0),  # not Afflicted (20" away)
        )
        candidate = battle.a.units[0]

        with mock.patch.dict(os.environ, {"SWEG_CREEPING_AFFLICTED": "0"}):
            battle._try_creeping_blight(dg, ast)

        self.assertTrue(
            getattr(candidate, "transient_reroll_hits_shooting", False),
            "Gate OFF + non-Afflicted target — hit re-roll flag must STILL be set",
        )
        self.assertTrue(
            getattr(candidate, "transient_reroll_wounds", False),
            "Gate OFF + non-Afflicted target — wound re-roll flag must STILL be set",
        )

    def test_default_env_behaves_as_off(self):
        """With SWEG_CREEPING_AFFLICTED absent from the environment (the
        default), the legacy unconditional behaviour applies."""
        random.seed(0)
        # Non-Afflicted target — should still get the buff under the default.
        battle, dg, ast = _build_battle(
            dg_position=(10.0, 10.0),
            enemy_position=(30.0, 10.0),
        )
        candidate = battle.a.units[0]

        # Ensure the env var is absent.
        env_without_gate = {
            k: v for k, v in os.environ.items()
            if k != "SWEG_CREEPING_AFFLICTED"
        }
        with mock.patch.dict(os.environ, env_without_gate, clear=True):
            battle._try_creeping_blight(dg, ast)

        self.assertTrue(
            getattr(candidate, "transient_reroll_hits_shooting", False),
            "Default (env var absent) must behave as OFF — buff applies unconditionally",
        )
        self.assertTrue(
            getattr(candidate, "transient_reroll_wounds", False),
            "Default (env var absent) must behave as OFF — buff applies unconditionally",
        )


# ---------------------------------------------------------------------------
# Smoke: import and basic wiring
# ---------------------------------------------------------------------------


class ImportSmokeTests(unittest.TestCase):
    """Confirm that the _is_near_enemy_dg_model helper and the simulator
    _try_creeping_blight method are importable and callable without error."""

    def test_is_near_enemy_dg_model_importable(self):
        from code.units import _is_near_enemy_dg_model  # noqa: F401
        self.assertTrue(callable(_is_near_enemy_dg_model))

    def test_try_creeping_blight_importable(self):
        battle, dg, ast = _build_battle()
        self.assertTrue(hasattr(battle, "_try_creeping_blight"))
        self.assertTrue(callable(battle._try_creeping_blight))


if __name__ == "__main__":
    unittest.main()
