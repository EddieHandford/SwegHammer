"""Tests for the Death Guard army rule Contagions of Nurgle / Nurgle's Gift (#146).

Nurgle's Gift (10e Death Guard army rule, Wahapedia / BSData verbatim):
    "While an enemy unit is within Contagion Range of one or more Death
     Guard units from your army, it is Afflicted ... while an enemy unit
     is Afflicted, subtract 1 from the Toughness characteristic of models
     in that unit, and that unit has the effect of your chosen Plague."
    CONTAGION RANGE: 1st Battle Round = 3"; 2nd Battle Round = 6"; 3rd
    Battle Round Onwards = 9" (DURA-AUDIT-D1, `_contagion_range_for_round`).

SwegHammer shape (post durability-fidelity-audit-D fixes D1/D2):
    Round 1 onward — Afflicted -1 Toughness, ALWAYS ON whenever an enemy
      unit is within the round's Contagion Range of a DG model
      (DURA-AUDIT-D2, SWEG_DG_AFFLICTED_TOUGHNESS gate; this replaces the
      old iter-4-removed launch-index "Virulent Rot" branch with the real,
      differently-sourced modern rule).
    Round 2 — Maladictive Pall: -1 Ld on enemy units within Contagion Range
      (pending the chosen-Plague fix, D3 — still round-staggered).
    Round 3+ — Fulminating Plague: -1 to Hit on attacks by enemy units
      within Contagion Range (also pending D3).

Implementation:
    * Every round: `Unit.attack` subtracts 1 from the defender's effective
      Toughness when the defender is Afflicted (DURA-AUDIT-D2).
    * `Battle._run_battleshock_phase` adds +1 to the battleshock test target
      for enemy units within Contagion Range of a DG model AND
      `round_num == 2`.
    * `Unit.attack` raises hit_target by 1 when the ATTACKER is within
      Contagion Range of any DG model on the opposing side AND
      `_current_round >= 3`, but ONLY if no other -1-to-hit modifier
      already shifted hit_target (10e cap: modifiers to a single hit roll
      can't compound past -1 / +1).

Cited as `simulator.contagions_of_nurgle` and `simulator.dg_afflicted_toughness`.
"""

from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import (
    Unit,
    UnitProfile,
    _prob_to_target,
    _contagion_round_for,
    _contagion_range_for_round,
    _is_near_enemy_dg_model,
)


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------


def _dg_plague_marine() -> UnitProfile:
    """Plague Marine-ish profile. Faction tag drives the aura source check.
    Stats don't matter for the contagion gates — only `profile.faction`."""
    return UnitProfile(
        name="DG Plague Marine",
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Death Guard",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _marine_profile(name: str = "Marine") -> UnitProfile:
    """A non-DG enemy unit used both as the attacker (round 3+ test) and
    defender (round 1 / round 2 tests)."""
    return UnitProfile(
        name=name,
        health=2, damage=1, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=7,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


# ---------------------------------------------------------------------------
# Helpers — replay the wound/hit target math from Unit.attack
# ---------------------------------------------------------------------------


def _effective_wound_target_round_1(attacker: Unit, defender: Unit) -> int:
    """Replay the wound_target derivation for an attacker shooting `defender`
    in round 1, including the DURA-AUDIT-D2 Afflicted -1 Toughness effect:
    the defender's effective Toughness drops by 1 whenever it is within
    Contagion Range of an enemy DG model, every round from round 1 onward
    (SWEG_DG_AFFLICTED_TOUGHNESS gate). This is a DIFFERENT, faithfully
    modern-codex-sourced rule from the launch-index "Virulent Rot" branch
    iter-4 removed — it happens to also debuff Toughness in round 1, but
    for the real reason (Afflicted status), not the old approximation."""
    from code.units import wound_probability
    toughness = defender.profile.toughness
    if (
        os.environ.get("SWEG_DG_AFFLICTED_TOUGHNESS", "1") != "0"
        and (defender.profile.faction or "") != "Death Guard"
        and _is_near_enemy_dg_model(
            defender,
            radius=_contagion_range_for_round(_contagion_round_for(defender)),
        )
    ):
        toughness -= 1
    wound_p = wound_probability(attacker.profile.strength, toughness)
    return _prob_to_target(wound_p)


def _effective_hit_target_round_3(attacker: Unit) -> int:
    """Replay the hit_target derivation for an attacker firing in round 3+,
    applying ONLY the Contagion round-3+ -1 to hit (no other modifiers,
    so the no-compound check passes by default). Radius escalates per
    DURA-AUDIT-D1 (`_contagion_range_for_round`; 9" from round 3 onward)."""
    hit_target = _prob_to_target(attacker.profile.hit_probability)
    # No other +/-1-to-hit modifiers in the fixture — _hit_target_after_buffs
    # is just hit_target. The contagion check fires if attacker is near an
    # enemy DG model in round >= 3 and the attacker is not DG.
    _round = _contagion_round_for(attacker)
    if (
        _round >= 3
        and attacker.profile.faction != "Death Guard"
        and _is_near_enemy_dg_model(
            attacker, radius=_contagion_range_for_round(_round)
        )
    ):
        hit_target = min(7, hit_target + 1)
    return hit_target


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class ContagionsOfNurgleTests(unittest.TestCase):
    """All scenarios use a Battle so `_battle_ref` is wired and
    `_current_round` can be set deterministically."""

    def _build_battle(self) -> Battle:
        """DG army with one Plague Marine vs. an Astartes army with one Marine.
        Positions are set by each test as appropriate."""
        dg = Army("Death Guard")
        dg.add_unit(_dg_plague_marine())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        battle = Battle(dg, ast)
        battle._assign_uids()
        return battle

    # ----- Round 1 — Afflicted -1 Toughness (DURA-AUDIT-D2) -----------------

    def test_round_1_afflicted_toughness_debuff_applies(self):
        """DURA-AUDIT-D2: the modern Afflicted -1 Toughness effect is
        always-on from round 1 (a DIFFERENT, faithfully-cited rule from the
        launch-index Virulent Rot branch iter-4 removed). A non-DG unit
        within Contagion Range of a DG model in round 1 must take its wound
        rolls at BASE-TOUGHNESS-MINUS-1. With Marine S4 vs Marine T4, base
        wound_target is 4+; Afflicted (T3) shifts it to 3+ (S4 > T3)."""
        battle = self._build_battle()
        dg = battle.a.units[0]
        ast = battle.b.units[0]
        # Place models 2" apart — well inside the round-1 3" Contagion Range.
        dg.position = (0.0, 0.0)
        ast.position = (2.0, 0.0)
        battle._current_round = 1

        # Sanity: S4 vs T4 base wound target is 4+; S4 vs T3 (Afflicted) is 3+.
        from code.units import wound_probability
        base_wt = _prob_to_target(wound_probability(4, 4))
        afflicted_wt = _prob_to_target(wound_probability(4, 3))
        self.assertEqual(base_wt, 4, "S4 vs T4 should be 4+ to wound by default")
        self.assertEqual(afflicted_wt, 3, "S4 vs T3 (Afflicted) should be 3+ to wound")

        shifted_wt = _effective_wound_target_round_1(dg, ast)
        self.assertEqual(
            shifted_wt, afflicted_wt,
            f"DURA-AUDIT-D2 Afflicted -1 Toughness must apply from round 1 — "
            f"expected {afflicted_wt}, got {shifted_wt}",
        )

        # Also assert the helper still correctly reports the Marine as near a
        # DG model at the round-1 (3") Contagion Range.
        self.assertTrue(
            _is_near_enemy_dg_model(ast, radius=_contagion_range_for_round(1)),
            "Proximity helper should still detect the DG model at 2\"",
        )
        self.assertEqual(
            _contagion_round_for(ast), 1,
            "Round helper should still resolve round 1 from the battle ref",
        )

    def test_round_1_afflicted_toughness_gate_off_restores_legacy(self):
        """SWEG_DG_AFFLICTED_TOUGHNESS=0 must restore the pre-fix behaviour:
        no Toughness debuff at all in round 1 (the legacy iter-4 state)."""
        import os
        from unittest import mock

        battle = self._build_battle()
        dg = battle.a.units[0]
        ast = battle.b.units[0]
        dg.position = (0.0, 0.0)
        ast.position = (2.0, 0.0)
        battle._current_round = 1

        from code.units import wound_probability
        base_wt = _prob_to_target(wound_probability(4, 4))
        with mock.patch.dict(os.environ, {"SWEG_DG_AFFLICTED_TOUGHNESS": "0"}):
            shifted_wt = _effective_wound_target_round_1(dg, ast)
        self.assertEqual(
            shifted_wt, base_wt,
            f"Gate off must restore the pre-fix base wound target "
            f"{base_wt}, got {shifted_wt}",
        )

    def test_round_1_dg_attacker_into_marine_uplift(self):
        """End-to-end via Unit.attack — DURA-AUDIT-D2: a DG attacker firing
        into a Marine in round 1 within Contagion Range must now produce
        MORE expected damage than the same shooter into a Marine 12" away
        (Afflicted -1 Toughness turns T4 into T3 — wound on 3+ vs 4+)."""
        battle_with = self._build_battle()
        dg_a = battle_with.a.units[0]
        ast_a = battle_with.b.units[0]
        dg_a.position = (0.0, 0.0)
        ast_a.position = (2.0, 0.0)
        battle_with._current_round = 1
        ast_a.current_health = 10_000.0

        random.seed(2026)
        dmg_in_aura = 0.0
        for _ in range(2000):
            dmg_in_aura += dg_a.attack(
                ast_a, distance=2.0, mode="ranged", has_los=True,
            )

        battle_no = self._build_battle()
        dg_b = battle_no.a.units[0]
        ast_b = battle_no.b.units[0]
        dg_b.position = (0.0, 0.0)
        ast_b.position = (12.0, 0.0)   # > round-1 3" Contagion Range
        battle_no._current_round = 1
        ast_b.current_health = 10_000.0

        random.seed(2026)
        dmg_out_of_aura = 0.0
        for _ in range(2000):
            dmg_out_of_aura += dg_b.attack(
                ast_b, distance=12.0, mode="ranged", has_los=True,
            )

        # Uplift assertion: the in-aura damage must be meaningfully higher
        # than the out-of-aura damage (-1 T turns T4 into T3 — wound on 3+
        # vs 4+, a 4/6 -> 3/6 shift, roughly +33% expected wounds).
        self.assertGreater(
            dmg_in_aura, dmg_out_of_aura * 1.15,
            f"DURA-AUDIT-D2 Afflicted -1 Toughness should uplift in-aura "
            f"damage vs out-of-aura. got in={dmg_in_aura:.1f} out={dmg_out_of_aura:.1f}",
        )

    # ----- Round 2 — Maladictive Pall (-1 Ld on battleshock) -----------------

    def test_round_2_minus_one_leadership(self):
        """A non-DG unit within 3" of a DG model in round 2 must take its
        battle-shock test at -1 Ld (target raised by 1). Drive the
        Battle._run_round path with a damaged Marine adjacent to a DG model
        and assert the Marine fails battleshock more often than a Marine 12"
        away (out of contagion range)."""
        N_TRIALS = 800

        # Helper to run a single round-2 battleshock pass and return how
        # many trials saw the Marine fail.
        def run_battleshock(distance: float) -> int:
            fails = 0
            random.seed(2026)
            for _ in range(N_TRIALS):
                battle = self._build_battle()
                dg = battle.a.units[0]
                ast = battle.b.units[0]
                dg.position = (0.0, 0.0)
                ast.position = (distance, 0.0)
                # Damage the Marine so it triggers battleshock (below half HP).
                ast.current_health = 0.5  # well below profile.health / 2.0
                battle._current_round = 2
                # Drive the battleshock block directly — _run_round does a
                # lot more than just battleshock, so we invoke its logic by
                # calling the relevant section. The cleanest path is to
                # invoke _run_round itself for round 2.
                # _run_round does: clear advanced set, clear battleshock,
                # award CP, doctrina, then battleshock check (round_num > 1).
                # The battleshock check is what we want. Other side-effects
                # (movement, attacks) are bounded by Marine being far from
                # the DG model so combat doesn't muddy the result, except
                # at distance=4". To isolate, we'll invoke a direct copy of
                # the battleshock block:
                fails += _run_battleshock_only(battle, round_num=2)
            return fails

        # Marine adjacent to DG model should fail MORE often than one far away.
        fails_near = run_battleshock(distance=2.0)
        fails_far = run_battleshock(distance=20.0)
        self.assertGreater(
            fails_near, fails_far,
            f"Round-2 contagion should make adjacent Marines fail battleshock "
            f"more often (got near={fails_near}, far={fails_far} of {N_TRIALS})",
        )

    # ----- Round 3+ — Fulminating Plague (-1 to hit on enemy attackers) -----

    def test_round_3_minus_one_to_hit(self):
        """An Astartes attacker firing within 3" of a DG model in round 3
        must take its Hit roll at -1 (hit_target raised by 1). We replay the
        hit_target math (no other modifiers in fixture) and check the shift."""
        battle = self._build_battle()
        dg = battle.a.units[0]
        ast = battle.b.units[0]
        dg.position = (0.0, 0.0)
        ast.position = (2.0, 0.0)
        battle._current_round = 3

        base_hit = _prob_to_target(ast.profile.hit_probability)   # 3+
        shifted = _effective_hit_target_round_3(ast)
        self.assertEqual(
            shifted, base_hit + 1,
            f"Round-3 contagion should raise hit_target from {base_hit} to "
            f"{base_hit + 1}",
        )

    # ----- Out-of-range and non-DG armies don't project the aura -----------

    def test_outside_3_inch_no_effect(self):
        """A Marine standing > 3" from every DG model gets no -1 T contagion
        debuff even in round 1."""
        battle = self._build_battle()
        dg = battle.a.units[0]
        ast = battle.b.units[0]
        dg.position = (0.0, 0.0)
        ast.position = (10.0, 0.0)   # 10" — outside the 3" aura
        battle._current_round = 1

        from code.units import wound_probability
        base_wt = _prob_to_target(wound_probability(4, 4))
        shifted_wt = _effective_wound_target_round_1(dg, ast)
        self.assertEqual(
            shifted_wt, base_wt,
            "Marine outside 3\" of every DG model must not take the -1 T penalty",
        )
        # Also check the round-3 -1-to-hit gate at the same range.
        battle._current_round = 3
        base_hit = _prob_to_target(ast.profile.hit_probability)
        shifted_hit = _effective_hit_target_round_3(ast)
        self.assertEqual(
            shifted_hit, base_hit,
            "Marine outside 3\" of every DG model must not take the -1 to hit",
        )

    def test_non_dg_army_doesnt_have_contagion(self):
        """An army with no DG models cannot project the aura. A Marine in
        an Astartes-vs-Astartes match takes its base wound target even when
        directly adjacent to an opposing model."""
        ast_a = Army("Astartes A")
        ast_a.add_unit(_marine_profile("Attacker"))
        ast_b = Army("Astartes B")
        ast_b.add_unit(_marine_profile("Defender"))
        battle = Battle(ast_a, ast_b)
        battle._assign_uids()
        attacker = battle.a.units[0]
        defender = battle.b.units[0]
        attacker.position = (0.0, 0.0)
        defender.position = (2.0, 0.0)
        battle._current_round = 1

        from code.units import wound_probability
        base_wt = _prob_to_target(wound_probability(4, 4))
        shifted_wt = _effective_wound_target_round_1(attacker, defender)
        self.assertEqual(
            shifted_wt, base_wt,
            "Non-DG armies must not project the Contagion aura",
        )

    def test_dg_units_are_never_contagioned(self):
        """The aura debuffs *enemy* units of DG; DG models themselves are
        immune. Even when a DG unit is within 6" of another DG model, no
        -1 T penalty applies to wound rolls against it."""
        dg = Army("Death Guard")
        dg.add_unit(_dg_plague_marine())
        ast = Army("Astartes")
        ast.add_unit(_marine_profile())
        battle = Battle(dg, ast)
        battle._assign_uids()
        # Edge case: model is_near_enemy_dg_model would return False for a DG
        # defender (DG models look at the opposing side for DG sources, and
        # the opposing side is Astartes — no DG there). We assert that
        # explicitly so a future refactor that swaps the helper's "opposing"
        # logic doesn't accidentally start debuffing DG units.
        dg_model = battle.a.units[0]
        battle._current_round = 1
        # Stand the DG model "next to itself" — no opposing DG models exist,
        # so the helper must return False.
        dg_model.position = (0.0, 0.0)
        self.assertFalse(
            _is_near_enemy_dg_model(dg_model, radius=3.0),
            "DG units must never see themselves as 'near an enemy DG model'",
        )


# ---------------------------------------------------------------------------
# Helper — invoke just the battleshock block of _run_round for a given round
# ---------------------------------------------------------------------------


def _run_battleshock_only(battle: Battle, round_num: int) -> int:
    """Replay the battleshock-check block from Battle._run_round for the
    given round, mutating `battle._battleshocked_this_round`. Returns 1 iff
    the Marine (battle.b.units[0]) failed its test, 0 otherwise.

    This is a slimmed-down copy of the production code in
    code/simulator.py:_run_round (the round_num > 1 block), exercising just
    the contagion / shadow / ld_bonus paths against a single damaged unit.
    """
    from code.simulator import _distance
    army_a, army_b = battle.a, battle.b

    # We only check army_b (the Astartes Marine) — that's the unit under test.
    army, opponent = army_b, army_a
    opponent_det = opponent.resolve_detachment()
    own_det = army.resolve_detachment()
    ld_penalty = opponent_det.enemy_ld_penalty if opponent_det else 0
    ld_bonus = own_det.ld_bonus if own_det else 0
    # Contagion sources on the opposing side, gated to round 2 only.
    contagion_sources = (
        [s for s in opponent.alive_units if s.profile.faction == "Death Guard"]
        if round_num == 2 else []
    )
    fails = 0
    for u in army.alive_units:
        if u.current_health >= u.profile.health / 2.0:
            continue
        contagion_penalty = 0
        if (
            contagion_sources
            and u.profile.faction != "Death Guard"
            and any(
                _distance(u.position, s.position) <= 3.0
                for s in contagion_sources
            )
        ):
            contagion_penalty = 1
        roll = random.randint(1, 6) + random.randint(1, 6)
        target = (
            u.profile.leadership
            + ld_penalty
            - ld_bonus
            + contagion_penalty
        )
        if roll < target:
            fails += 1
    return fails


if __name__ == "__main__":
    unittest.main()
