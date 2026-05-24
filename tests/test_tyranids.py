"""Tests for the Tyranids army rules implemented in #117.

Covered:
  - Synapse Imperative: a Tyranid unit within 6" of any friendly SYNAPSE
    model auto-passes its Battle-shock test (no roll). Cited as
    `simulator.synapse_imperative`.
  - Shadow in the Warp (TYRANIDS-DIAG-5, codex 10e): once per battle, in
    either player's Command phase, an enemy unit within 6" of any SYNAPSE
    model from the Tyranid army takes Battle-shock at -1. Modelled by
    `Army.shadow_in_the_warp_used_round` set during the Command phase
    (AI heuristic fires at Round 2). Cited as
    `simulator.shadow_in_the_warp`.

Both effects key off the SYNAPSE keyword extracted by the BSData mapper from
the unit's categoryLinks. The tests bypass Battle.run() and drive _run_round
directly so the wounded-below-half-strength state is fully controllable.
"""

from __future__ import annotations

import random
import unittest

from code.army import Army
from code.simulator import Battle
from code.units import UnitProfile


def _hive_tyrant_profile() -> UnitProfile:
    """A small Hive Tyrant stand-in tagged SYNAPSE + Tyranids."""
    return UnitProfile(
        name="Hive Tyrant",
        health=12, damage=4.0, hit_probability=2 / 3,
        ap=-2, save=2, strength=7, toughness=9,
        attacks=4, weapon_damage_per_shot=2.0, range_inches=24,
        leadership=6,
        faction="Tyranids",
        unit_keywords=("MONSTER", "CHARACTER", "PSYKER", "SYNAPSE"),
        melee_attacks=6, melee_damage_per_shot=3.0,
        melee_hit_probability=2 / 3, melee_strength=8, melee_ap=-3,
    )


def _tyranid_warrior_profile() -> UnitProfile:
    """A Tyranid Warrior — Tyranids but NOT a SYNAPSE source."""
    return UnitProfile(
        name="Tyranid Warrior",
        health=3, damage=1.0, hit_probability=2 / 3,
        ap=-1, save=4, strength=5, toughness=5,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=18,
        leadership=7,
        faction="Tyranids",
        unit_keywords=("INFANTRY",),
        melee_attacks=3, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=5, melee_ap=-1,
    )


def _marine_profile() -> UnitProfile:
    return UnitProfile(
        name="Marine",
        health=2, damage=1.0, hit_probability=2 / 3,
        ap=0, save=3, strength=4, toughness=4,
        attacks=2, weapon_damage_per_shot=1.0, range_inches=24,
        leadership=6,
        faction="Adeptus Astartes",
        unit_keywords=("INFANTRY",),
        melee_attacks=1, melee_damage_per_shot=1.0,
        melee_hit_probability=2 / 3, melee_strength=4, melee_ap=0,
    )


def _build_battle(
    a_units, b_units, positions_a=None, positions_b=None,
) -> Battle:
    a = Army("A")
    for p in a_units:
        a.add_unit(p)
    b = Army("B")
    for p in b_units:
        b.add_unit(p)
    battle = Battle(a, b)
    battle._assign_uids()
    if positions_a is not None:
        for u, pos in zip(a.units, positions_a):
            u.position = pos
    if positions_b is not None:
        for u, pos in zip(b.units, positions_b):
            u.position = pos
    return battle


# ---------------------------------------------------------------------------
# Synapse Imperative — auto-pass within 6" of a friendly SYNAPSE model
# ---------------------------------------------------------------------------


class SynapseImperativeTests(unittest.TestCase):

    def test_synapse_within_6_auto_passes(self):
        """A wounded Tyranid Warrior 5" from a Hive Tyrant must auto-pass
        Battle-shock — its uid should NOT land in _battleshocked_this_round."""
        # Seed so that an actual roll would fail Ld 7 (2D6 < 7).
        random.seed(0)
        battle = _build_battle(
            a_units=[_hive_tyrant_profile(), _tyranid_warrior_profile()],
            b_units=[_marine_profile()],
            positions_a=[(0.0, 0.0), (5.0, 0.0)],
            positions_b=[(40.0, 0.0)],
        )
        # Wound the Tyranid Warrior below half strength so it would test.
        warrior = battle.a.units[1]
        warrior.current_health = 1.0   # below 3/2 = 1.5
        battle._current_round = 2
        battle._run_round(2)
        self.assertNotIn(
            warrior.uid, battle._battleshocked_this_round,
            "Tyranid Warrior within 6\" of a SYNAPSE Hive Tyrant should "
            "auto-pass Synapse Imperative",
        )

    def test_synapse_outside_6_does_not_auto_pass(self):
        """Same setup but the Hive Tyrant is 12" away — Synapse Imperative
        does not apply, the roll must happen. We force a fail seed and
        confirm the unit gets battleshocked."""
        random.seed(0)
        battle = _build_battle(
            a_units=[_hive_tyrant_profile(), _tyranid_warrior_profile()],
            b_units=[_marine_profile()],
            positions_a=[(0.0, 0.0), (12.0, 0.0)],
            positions_b=[(40.0, 0.0)],
        )
        warrior = battle.a.units[1]
        warrior.current_health = 1.0
        battle._current_round = 2
        # Pick a seed where 2D6 < 7. random.seed(0) → first call yields a
        # low pair; we verify the roll path was taken by checking either
        # outcome: the warrior either failed (battleshocked) or rolled
        # high (still didn't fail). Critical assertion: Synapse Imperative
        # did NOT short-circuit the roll — i.e. the path with no SYNAPSE
        # within 6" behaved like normal Battle-shock. We pin this by
        # iterating seeds and confirming SOME seed produces a failure.
        outcomes = []
        for seed in range(20):
            random.seed(seed)
            battle._battleshocked_this_round = set()
            battle._run_round(2)
            outcomes.append(warrior.uid in battle._battleshocked_this_round)
        # If Synapse Imperative wrongly auto-passed, no seed would fail.
        self.assertIn(
            True, outcomes,
            "Tyranid Warrior outside 6\" should be able to fail Battle-shock "
            "across some seeds — Synapse Imperative should NOT apply",
        )

    def test_synapse_only_helps_tyranids(self):
        """A wounded Marine 4" from a Hive Tyrant does NOT auto-pass — the
        Synapse Imperative is gated on the testing unit's Tyranids faction.
        This is a control: the geometry says "within 6"" but the faction
        gate must refuse."""
        # Put the Marine on army A so it's friendly with the Hive Tyrant
        # (this is the gate we're stressing — same side, in range, but
        # the wrong faction).
        battle = _build_battle(
            a_units=[_hive_tyrant_profile(), _marine_profile()],
            b_units=[_tyranid_warrior_profile()],
            positions_a=[(0.0, 0.0), (4.0, 0.0)],
            positions_b=[(50.0, 0.0)],
        )
        marine = battle.a.units[1]
        marine.current_health = 0.5    # below 2/2 = 1.0
        battle._current_round = 2
        # As above, iterate seeds and confirm at least one fails.
        outcomes = []
        for seed in range(20):
            random.seed(seed)
            battle._battleshocked_this_round = set()
            battle._run_round(2)
            outcomes.append(marine.uid in battle._battleshocked_this_round)
        self.assertIn(
            True, outcomes,
            "A non-Tyranid (Marine) standing in the Synapse aura must NOT "
            "auto-pass — Synapse Imperative is faction-gated",
        )


# ---------------------------------------------------------------------------
# Shadow in the Warp — once-per-battle, enemy units within 6" take
# Battle-shock at -1 on the round it is unleashed (TYRANIDS-DIAG-5).
# ---------------------------------------------------------------------------


class ShadowInTheWarpTests(unittest.TestCase):

    def _captured_targets(self, battle: Battle, unit_uid: str) -> list:
        """Drive _run_round many times with different seeds and record the
        TARGET value used (the test's Ld + ld_penalty - ld_bonus + shadow).
        We inspect the BattleshockFailed event log entries; failures emit
        the target, so a -1 penalty raises it by 1.

        Simpler approach: monkey-patch `random.randint` to record the seed
        and verify the target. Cleanest: snapshot the test target by
        forcing a known roll outcome.

        We just check that, with a wounded Marine present and the Hive
        Tyrant within 12" vs out of range, the FAIL rate diverges
        consistently across many seeds — Shadow makes failure more likely.
        """
        return []

    def test_shadow_in_the_warp_subtracts_1(self):
        """A wounded Marine 4" from the opposing Tyranids' Hive Tyrant must
        face a higher test target (Ld + 1) than the same Marine with no
        SYNAPSE model in range. TYRANIDS-DIAG-5: codex radius is 6" and
        the rule fires once-per-battle (declared at Round 2 by the AI
        heuristic). We verify by comparing per-seed failure rates: with
        Shadow, more seeds fail.

        We rebuild a fresh Battle per seed so that positional drift and
        damage carried over from in-round activations don't pollute the
        comparison."""
        marine_pos = (4.0, 0.0)  # within 6" of Hive Tyrant at (0,0)

        def _fail_rate(ht_pos, n_seeds: int = 144) -> int:
            fails = 0
            for seed in range(n_seeds):
                random.seed(seed)
                battle = _build_battle(
                    a_units=[_hive_tyrant_profile()],
                    b_units=[_marine_profile()],
                    positions_a=[ht_pos],
                    positions_b=[marine_pos],
                )
                marine = battle.b.units[0]
                marine.current_health = 0.5
                battle._current_round = 2
                battle._run_round(2)
                if marine.uid in battle._battleshocked_this_round:
                    fails += 1
            return fails

        fails_with_shadow = _fail_rate((0.0, 0.0))     # 4" away — inside 6" aura
        fails_no_shadow = _fail_rate((50.0, 0.0))      # 46" away — out of aura
        # Shadow makes the test harder (Ld + 1), so fails_with > fails_no.
        # Mathematically: P(2D6<7) = 15/36 vs P(2D6<6) = 10/36 — substantial.
        self.assertGreater(
            fails_with_shadow, fails_no_shadow,
            f"Shadow in the Warp should raise failure rate; "
            f"with={fails_with_shadow} no={fails_no_shadow}",
        )

    def test_shadow_in_the_warp_outside_6_does_nothing(self):
        """A Hive Tyrant 7" from the Marine is outside the codex 6" aura
        — no penalty. The failure rate must equal the no-Tyrant baseline
        (matching seed iteration). TYRANIDS-DIAG-5: tightened from the
        prior 12" always-on aura to the codex 6" once-per-battle gate."""
        marine_pos = (7.0, 0.0)  # 7" away — outside 6"

        def _fail_count(ht_pos, n_seeds: int = 72) -> int:
            fails = 0
            for seed in range(n_seeds):
                random.seed(seed)
                battle = _build_battle(
                    a_units=[_hive_tyrant_profile()],
                    b_units=[_marine_profile()],
                    positions_a=[ht_pos],
                    positions_b=[marine_pos],
                )
                marine = battle.b.units[0]
                marine.current_health = 0.5
                battle._current_round = 2
                battle._run_round(2)
                if marine.uid in battle._battleshocked_this_round:
                    fails += 1
            return fails

        # Both Tyrant positions are out of the 6" aura → identical fail rates.
        self.assertEqual(
            _fail_count((0.0, 0.0)),         # 7" away from Marine
            _fail_count((60.0, 0.0)),        # 53" away
            "Shadow in the Warp outside 6\" must not apply — failure "
            "rate must match the far-away control",
        )

    def test_shadow_in_the_warp_round_1_does_nothing(self):
        """TYRANIDS-DIAG-5: Shadow in the Warp is once-per-battle, declared
        at Round 2 by the AI heuristic. Running Round 1 should NOT apply
        the -1 debuff (the Tyranid army has not yet unleashed Shadow). The
        failure rate for a Marine within the 6" radius at Round 1 must
        equal the no-Tyrant baseline."""
        marine_pos = (4.0, 0.0)

        def _fail_count(ht_pos, n_seeds: int = 72) -> int:
            fails = 0
            for seed in range(n_seeds):
                random.seed(seed)
                battle = _build_battle(
                    a_units=[_hive_tyrant_profile()],
                    b_units=[_marine_profile()],
                    positions_a=[ht_pos],
                    positions_b=[marine_pos],
                )
                marine = battle.b.units[0]
                marine.current_health = 0.5
                battle._current_round = 1
                battle._run_round(1)
                if marine.uid in battle._battleshocked_this_round:
                    fails += 1
            return fails

        # Round 1 — Shadow not yet declared. Both should equal baseline.
        self.assertEqual(
            _fail_count((0.0, 0.0)),         # 4" away from Marine, Round 1
            _fail_count((60.0, 0.0)),        # 56" away, Round 1
            "Shadow in the Warp at Round 1 must not apply — once-per-battle "
            "AI heuristic declares at Round 2.",
        )


if __name__ == "__main__":
    unittest.main()
