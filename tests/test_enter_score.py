"""Entering-round primary scoring — wave 111, option (ii), env-gated SWEG_ENTERSCORE.

10e scores Primary VP at each player's Command phase: a unit holds an objective
from when it takes it until an enemy takes it away, and it scores even if the
objective is contested away later that battle round. The alternating-activation
round model collapses both turns into one interleaved sequence and the baseline
scores Primary only ONCE, at end of round AFTER all combat — crediting only the
post-combat survivor (the durable holder) and erasing the transient board control
a fragile broad army floods then loses (wave-110: 52% of the broad army's
entering-round marker control was stripped before the end-of-round score).

ENTER-SCORE, gated ON, instead scores Primary on the control state ENTERING each
of battle rounds 2-5 (before that round's combat). This test pins the timing: OFF
scores AFTER each round's activations (baseline), ON scores BEFORE them (rounds
2-5). Gate unset reproduces the end-of-round baseline.

Cited as `simulator.primary_vp_entering_round`
(data/rule_citations.d/core_primary_vp_cap.json).
"""

from __future__ import annotations

import os
import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import UnitProfile


def _unit(name: str = "U") -> UnitProfile:
    return UnitProfile(
        name=name, health=4.0, damage=1.0, hit_probability=0.5, ap=0, save=4,
        strength=4, toughness=4, attacks=2, weapon_damage_per_shot=1.0,
        range_inches=24, unit_keywords=("INFANTRY",), melee_attacks=2,
        melee_hit_probability=0.5, melee_strength=4, melee_damage_per_shot=1.0,
    )


def _call_order(enter_score: bool):
    """Run a minimal battle, recording the interleaving of _run_round and
    _score_objectives calls. Returns the recorded sequence."""
    if enter_score:
        os.environ["SWEG_ENTERSCORE"] = "1"
    else:
        os.environ.pop("SWEG_ENTERSCORE", None)
    try:
        a = Army("A"); a.add_unit(_unit())
        b = Army("B"); b.add_unit(_unit())
        battle = Battle(a, b, map_=Map("T", 60.0, 44.0))
        battle._assign_uids()
        seq = []
        run_orig = battle._run_round
        score_orig = battle._score_objectives

        def run_spy(rnd, o=run_orig):
            seq.append(("run", rnd))
            return o(rnd)

        def score_spy(o=score_orig):
            seq.append(("score",))
            return o()

        battle._run_round = run_spy
        battle._score_objectives = score_spy
        battle.run()
        return seq
    finally:
        os.environ.pop("SWEG_ENTERSCORE", None)


class EnterScoreTimingTests(unittest.TestCase):
    def test_off_scores_after_each_round(self):
        """Baseline: each round's _run_round precedes its _score_objectives."""
        seq = _call_order(enter_score=False)
        # The first score must come AFTER round 2's run.
        first_score_idx = seq.index(("score",))
        run2_idx = seq.index(("run", 2))
        self.assertLess(run2_idx, first_score_idx,
                        f"OFF should score after the round runs: {seq}")
        # Round 1 never scores (no ('score',) before ('run', 2)).
        self.assertNotIn(("score",), seq[:run2_idx + 1])

    def test_on_scores_before_each_round_from_round_2(self):
        """ENTER-SCORE: rounds 2-5 score BEFORE that round's _run_round."""
        seq = _call_order(enter_score=True)
        first_score_idx = seq.index(("score",))
        run2_idx = seq.index(("run", 2))
        self.assertLess(first_score_idx, run2_idx,
                        f"ON should score before the round runs: {seq}")
        # Round 1 still never scores (the entering-control score starts round 2).
        self.assertEqual(seq[0], ("run", 1))
        self.assertNotIn(("score",), seq[:1])

    def test_same_number_of_scoring_opportunities(self):
        """Both paths score four times (rounds 2-5)."""
        off = _call_order(enter_score=False)
        on = _call_order(enter_score=True)
        self.assertEqual(off.count(("score",)), on.count(("score",)))
        self.assertEqual(off.count(("score",)), 4)


if __name__ == "__main__":
    unittest.main()
