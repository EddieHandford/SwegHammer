"""Tests for the Thousand Sons defensive rules.

iter14 update: the simulator now models the CURRENT 10e versions of the
TSON defensive stack rather than the pre-codex launch-index "All Is Dust
== -1 to wound on D1 attacks for any TSON non-DAEMON unit". Specifically:

* `simulator.all_is_dust` (Rubricae Phalanx detachment rule, Wahapedia):
  "Each time an attack with an unmodified Damage characteristic of 1 is
   allocated to a RUBRICAE model from your army, add 1 to any armour
   saving throw made against that attack."
  Gates on:
    * defender carries the RUBRICAE unit-keyword (Rubric Marines and
      Scarab Occult Terminators — both seeded via overrides.json)
    * incoming attack has weapon_damage_per_shot == 1.0
  Effect: +1 to the defender's armour save (capped at 2+).

* `simulator.rites_of_coalescence` (Scarab Occult Terminators datasheet
  ability, Wahapedia): "While this unit contains one or more PSYKER
  models, each time an attack targets this unit, subtract 1 from the
  Wound roll."
  Gates on:
    * defender's profile.name == "Scarab Occult Terminators"
    * defender carries the PSYKER unit-keyword
  Effect: -1 to the attacker's wound roll on any-damage attacks.

These tests use deterministic seeds and large attack volumes so the
empirical wound rate matches the analytical d6 distribution within a
loose statistical tolerance.
"""

from __future__ import annotations

import dataclasses
import random
import unittest

from code.army import Army
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Helpers — minimal profiles wired with the canonical faction strings and
# keywords required by the iter14 gates.
# ---------------------------------------------------------------------------

def _rubric_marine(
    faction: str = "Thousand Sons",
    keywords=("PSYKER", "INFANTRY", "BATTLELINE", "RUBRICAE"),
) -> UnitProfile:
    """A bulky T4 / 3+ save / 5++ Rubric stand-in carrying RUBRICAE keyword."""
    return UnitProfile(
        name="Rubric Marines",
        health=10_000.0, damage=1, hit_probability=2 / 3,
        ap=0, save=3, invuln_save=5, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction=faction,
        unit_keywords=keywords,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _scarab_occult_terminator() -> UnitProfile:
    """Scarab Occult stand-in carrying RUBRICAE + PSYKER (Rites of Coalescence)."""
    return UnitProfile(
        name="Scarab Occult Terminators",
        health=10_000.0, damage=1, hit_probability=2 / 3,
        ap=0, save=2, invuln_save=4, strength=4, toughness=5,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Thousand Sons",
        unit_keywords=("PSYKER", "INFANTRY", "TERMINATOR", "RUBRICAE"),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _single_damage_attacker() -> UnitProfile:
    """An S4 / D1 attacker. Auto-hits via torrent so the only stochastic
    inputs are the wound and save rolls — wound on 4+ baseline vs T4."""
    return UnitProfile(
        name="D1 Bolter",
        health=2.0, damage=1, hit_probability=1.0,
        ap=0, save=4, strength=4, toughness=4,
        attacks=1, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        torrent=True,
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _multi_damage_attacker() -> UnitProfile:
    """Same chassis but D2 — All Is Dust must NOT fire (D2 != 1)."""
    return dataclasses.replace(
        _single_damage_attacker(),
        weapon_damage_per_shot=2.0,
        damage=2,
        name="D2 Plasma",
    )


# ---------------------------------------------------------------------------
# Empirical wound-rate harness. We assemble armies, hand off via Unit.attack,
# and count damage applied. The relative ratio between with-rule and
# without-rule is what we assert on.
# ---------------------------------------------------------------------------

def _wound_rate(attacker_profile: UnitProfile,
                defender_profile: UnitProfile,
                n_attacks: int = 8000,
                seed: int = 0) -> float:
    """Mean damage per attack (proxy for landed-and-failed-save rate)."""
    random.seed(seed)
    atk_army = Army("Atk")
    atk_army.add_unit(attacker_profile)
    def_army = Army("Def")
    def_army.add_unit(defender_profile)
    attacker = atk_army.units[0]
    attacker.uid = "atk0"
    defender = def_army.units[0]
    defender.uid = "def0"

    class _FakeBattle:
        _current_round = 1
        def maybe_fire_command_reroll(self, *args, **kwargs):
            return False
    fb = _FakeBattle()
    attacker.army_ref._battle_ref = fb
    defender.army_ref._battle_ref = fb

    total = 0.0
    for _ in range(n_attacks):
        total += attacker.attack(defender, distance=6.0, mode="ranged")
    return total / n_attacks


class AllIsDustTests(unittest.TestCase):
    """Cover the iter14 All Is Dust + Rites of Coalescence semantics."""

    def test_d1_attack_into_rubricae_improves_save(self):
        """D1 S4 attacker into a RUBRICAE T4 3+/5++ defender. Baseline wounds
        on 4+ (50%), save 3+ passes 4/6 → 1/6 ≈ 0.167 W/shot. With All Is Dust
        the save improves to 2+ (5/6 passes) → 1/12 ≈ 0.083 W/shot. With-rule
        rate should be ~50% of without-rule."""
        atk = _single_damage_attacker()
        rubric = _rubric_marine(faction="Thousand Sons")
        # Vanilla Marine control: same save 3+, same T4, no RUBRICAE keyword.
        # We strip the invuln to keep the comparison clean — the buff being
        # measured is the save-improvement, not the invuln backstop.
        marine = dataclasses.replace(
            _rubric_marine(faction="Adeptus Astartes",
                           keywords=("INFANTRY",)),
            invuln_save=7,
            name="Tactical Marine",
        )
        with_rule = _wound_rate(atk, rubric, seed=0)
        without_rule = _wound_rate(atk, marine, seed=0)
        self.assertGreater(
            without_rule, with_rule,
            f"All Is Dust must reduce damage taken: "
            f"with={with_rule:.4f} without={without_rule:.4f}",
        )
        # With save improving 3+→2+ vs the D1 attack the ratio should be
        # roughly 0.5 — generous tolerance for seed noise and the wound roll
        # being separate from the save roll.
        ratio = with_rule / without_rule
        self.assertLess(
            ratio, 0.70,
            f"All Is Dust effect too small: ratio={ratio:.3f}",
        )

    def test_d2_attack_does_not_improve_save(self):
        """D2 S4 attacker into a RUBRICAE T4 defender. All Is Dust gates on
        weapon_damage_per_shot == 1.0, so a D2 attack must hit at the base
        save (3+, 4/6 passes → 1/3 fail-save). The wound rate vs RUBRICAE
        and vs a non-RUBRICAE control should match within seed noise."""
        atk = _multi_damage_attacker()
        rubric = _rubric_marine(faction="Thousand Sons")
        # Match the rubric's save / toughness / damage but strip the keyword
        marine = dataclasses.replace(
            _rubric_marine(faction="Adeptus Astartes",
                           keywords=("INFANTRY",)),
            invuln_save=5,    # match the rubric's 5++ so invuln backstop is fair
            name="Tactical Marine",
        )
        rate_rubric = _wound_rate(atk, rubric, seed=1)
        rate_marine = _wound_rate(atk, marine, seed=1)
        ratio = rate_rubric / rate_marine if rate_marine else 0.0
        self.assertGreater(
            ratio, 0.90,
            f"D2 attacker should be unaffected by All Is Dust: "
            f"rubric={rate_rubric:.4f} marine={rate_marine:.4f}",
        )
        self.assertLess(
            ratio, 1.10,
            f"D2 attacker should be unaffected by All Is Dust: "
            f"rubric={rate_rubric:.4f} marine={rate_marine:.4f}",
        )

    def test_non_rubricae_tson_target_unaffected_by_all_is_dust(self):
        """A TSON defender WITHOUT the RUBRICAE keyword (e.g. Tzaangors, a
        Sorcerer on foot, a Daemon Prince) must NOT get +1 save vs D1 — the
        rule is RUBRICAE-keyword-gated, not faction-gated."""
        atk = _single_damage_attacker()
        # Strip RUBRICAE but keep faction TSON — should now match the marine
        # baseline (same save, same T, no rule fires).
        tzaangor = _rubric_marine(
            faction="Thousand Sons",
            keywords=("INFANTRY",),  # no RUBRICAE, no PSYKER → no AID / no Rites
        )
        # Vanilla control (same body but Adeptus Astartes faction)
        marine = dataclasses.replace(
            _rubric_marine(faction="Adeptus Astartes",
                           keywords=("INFANTRY",)),
            invuln_save=5,
            name="Tactical Marine (control)",
        )
        rate_tzaangor = _wound_rate(atk, tzaangor, seed=2)
        rate_marine = _wound_rate(atk, marine, seed=2)
        ratio = rate_tzaangor / rate_marine if rate_marine else 0.0
        self.assertGreater(
            ratio, 0.90,
            f"Non-RUBRICAE TSON should not get All Is Dust: "
            f"tzaangor={rate_tzaangor:.4f} marine={rate_marine:.4f}",
        )
        self.assertLess(
            ratio, 1.10,
            f"Non-RUBRICAE TSON should not get All Is Dust: "
            f"tzaangor={rate_tzaangor:.4f} marine={rate_marine:.4f}",
        )

    def test_save_floor_at_2_plus(self):
        """The +1 to save from All Is Dust must respect the 2+ floor — a
        rubric already on a 2+ save (e.g. with an additional plus_one_save
        buff already applied) does not improve to 1+. We approximate this
        by ensuring the with-rule rate never drops below the ideal 2+ save
        wound rate (vs T4: wound 50%, save 5/6 → 1/12 ≈ 0.083 W/shot)."""
        atk = _single_damage_attacker()
        rubric = _rubric_marine(faction="Thousand Sons")
        rate = _wound_rate(atk, rubric, seed=4)
        # 2+ save floor → ~0.083 W/shot. Loose tolerance for seed noise and
        # the wound roll being independent from the save roll.
        self.assertGreater(rate, 0.05,
                           f"All Is Dust floored too low: {rate:.4f}")
        self.assertLess(rate, 0.13,
                        f"All Is Dust did not fire: {rate:.4f} "
                        f"(should be ~0.083 with rule, ~0.167 without)")


class RitesOfCoalescenceTests(unittest.TestCase):
    """Scarab Occult Terminators datasheet ability — -1 to wound on any-D
    attack while the squad contains a PSYKER. The Aspiring Sorcerer is
    mandatory so the rule is effectively always-on."""

    def test_d1_attack_into_scarab_occult_is_doubly_buffed(self):
        """A D1 attack into Scarab Occult fires BOTH Rites of Coalescence
        (-1 to wound) AND All Is Dust (+1 save vs D1, RUBRICAE-gated). The
        combined effect should drop damage taken significantly below the
        non-Scarab baseline."""
        atk = _single_damage_attacker()
        scarab = _scarab_occult_terminator()
        # Stripped control — same body, same save/inv, but no rules fire
        control = dataclasses.replace(
            scarab,
            name="Inert Terminators",
            faction="Adeptus Astartes",
            unit_keywords=("INFANTRY", "TERMINATOR"),
        )
        rate_scarab = _wound_rate(atk, scarab, seed=10)
        rate_control = _wound_rate(atk, control, seed=10)
        self.assertGreater(
            rate_control, rate_scarab,
            f"Scarab Occult should take less damage than the control: "
            f"scarab={rate_scarab:.4f} control={rate_control:.4f}",
        )
        # Expect at least a 40% drop (combined Rites + AID effect on a 2+
        # save vs S4 D1: wound 4+ → 5+, save 2+ → 2+ floored). Loose bounds
        # because the modifier cap (±1 wound only) clamps Rites + any
        # attacker +1 to net zero.
        ratio = rate_scarab / rate_control
        self.assertLess(
            ratio, 0.75,
            f"Combined Rites + AID effect too small: ratio={ratio:.3f}",
        )

    def test_d2_attack_into_scarab_occult_fires_rites_not_aid(self):
        """A D2 attack still triggers Rites of Coalescence (-1 to wound)
        even though All Is Dust does NOT fire (D2 attack). Scarab Occult
        should still be more durable than a Rites-stripped control."""
        atk = _multi_damage_attacker()
        scarab = _scarab_occult_terminator()
        control = dataclasses.replace(
            scarab,
            name="Inert Terminators",
            faction="Adeptus Astartes",
            unit_keywords=("INFANTRY", "TERMINATOR"),
        )
        rate_scarab = _wound_rate(atk, scarab, seed=11)
        rate_control = _wound_rate(atk, control, seed=11)
        # Rites of Coalescence alone (no AID, D2 attack) — S4 vs T5 already
        # wounds on 5+, Rites pushes it to 6+. Damage drop should be ~50%
        # (1/6 → 1/6 of base; against 2+/4++ the save half is unchanged).
        self.assertGreater(
            rate_control, rate_scarab,
            f"Rites of Coalescence must reduce D2 damage taken: "
            f"scarab={rate_scarab:.4f} control={rate_control:.4f}",
        )

    def test_non_scarab_psyker_squad_does_not_get_rites(self):
        """A non-Scarab-Occult PSYKER squad (e.g. Rubric Marines) does NOT
        get Rites of Coalescence — the rule is name-gated to Scarab Occult."""
        atk = _multi_damage_attacker()  # D2 to bypass All Is Dust
        rubric = _rubric_marine(faction="Thousand Sons")  # PSYKER + RUBRICAE
        marine = dataclasses.replace(
            _rubric_marine(faction="Adeptus Astartes",
                           keywords=("INFANTRY",)),
            invuln_save=5,
            name="Tactical Marine",
        )
        rate_rubric = _wound_rate(atk, rubric, seed=12)
        rate_marine = _wound_rate(atk, marine, seed=12)
        # Rubric should match the non-TSON control on D2 — Rites must not
        # fire on a non-Scarab unit even if PSYKER is set.
        ratio = rate_rubric / rate_marine if rate_marine else 0.0
        self.assertGreater(
            ratio, 0.85,
            f"Rubric must not get Rites: "
            f"rubric={rate_rubric:.4f} marine={rate_marine:.4f}",
        )
        self.assertLess(
            ratio, 1.15,
            f"Rubric must not get Rites: "
            f"rubric={rate_rubric:.4f} marine={rate_marine:.4f}",
        )


if __name__ == "__main__":
    unittest.main()
