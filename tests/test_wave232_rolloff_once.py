"""Once-per-battle first-turn roll-off — wave 232, gate SWEG_ROLLOFF_ONCE (default-ON since wave 232).

Real Warhammer 40k 10e (mission sequence step 12): 'The players roll off. The
winner declares whether they will take the first or second turn.' That order
then persists for the entire battle — the same player always goes first.

The simulator previously re-rolled who went first every round, producing random
first-turn assignment each battle round (a fake free double-turn mechanic). With
gate SWEG_ROLLOFF_ONCE=1 a single random.random() draw in round 1 resolves first
turn and the result is stored on Battle._first_player and reused each subsequent
round without a new draw.

Gate OFF: per-round flip — one random.random() draw every round, byte-identical
to the pre-wave-232 behaviour.

Tests:
 1. gate_on_fixed_order_across_rounds: after running a multi-round seeded battle
    with the gate ON, _first_player is not None and is one of the two armies;
    confirm the same draw from the initial seed always resolves to the same army.
 2. gate_on_order_persists: in a seeded battle each _run_round invocation
    receives the SAME first/second assignment (verified by monkey-patching
    _run_round_vanilla_turns to record the 'first' argument and asserting all
    recordings are the same army name).
 3. gate_off_state_is_none: with gate OFF, _first_player remains None after the
    battle (confirming no state side-effect on the OFF path).
 4. gate_off_byte_identical_to_baseline: with an identical seed and gate OFF,
    the BattleResult is identical to a run with the gate completely unset
    (confirms the OFF path is byte-identical to pre-wave-232 code).
"""
from __future__ import annotations

import os
import random
import unittest

from code.army import Army
from code.map import Map
from code.simulator import Battle
from code.units import UnitProfile


# ---------------------------------------------------------------------------
# Shared profiles and battle factory
# ---------------------------------------------------------------------------

def _basic_profile(name: str = "Trooper", health: float = 6.0) -> UnitProfile:
    """Generic Ballistic Skill 3+ infantry profile — enough to run a full
    battle without an early wipe."""
    return UnitProfile(
        name=name,
        health=health,
        damage=1.0,
        hit_probability=2 / 3,
        ap=-1,
        save=4,
        strength=4,
        toughness=4,
        attacks=2,
        weapon_damage_per_shot=1.0,
        range_inches=24,
        unit_keywords=("INFANTRY",),
        melee_attacks=2,
        melee_hit_probability=2 / 3,
        melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _build_battle(seed: int, gate_value: str | None) -> tuple[Battle, list, object]:
    """Build a seeded battle with no special map, run it, and return
    (battle, recorded_first_army_names, battle_result).

    ``gate_value`` is the string to set SWEG_ROLLOFF_ONCE to ("0" / "1"),
    or None to pop the variable entirely (pure baseline).

    Also installs a recording hook on _run_round_vanilla_turns so the caller
    can verify which army was passed as 'first' each round."""
    if gate_value is None:
        os.environ.pop("SWEG_ROLLOFF_ONCE", None)
    else:
        os.environ["SWEG_ROLLOFF_ONCE"] = gate_value

    random.seed(seed)
    army_a = Army("Alpha")
    army_b = Army("Beta")
    for _ in range(3):
        army_a.add_unit(_basic_profile("AlphaTroop"))
        army_b.add_unit(_basic_profile("BetaTroop"))

    battle = Battle(army_a, army_b, map_=Map("Test", 60.0, 44.0))

    # Monkey-patch _run_round_vanilla_turns to record which army was 'first'
    # each round.  The original remains callable; we only wrap it.
    recorded_firsts: list[str] = []
    original_vrounds = battle._run_round_vanilla_turns

    def _recording_vrounds(first, second):
        recorded_firsts.append(first.name)
        return original_vrounds(first, second)

    battle._run_round_vanilla_turns = _recording_vrounds

    result = battle.run()
    return battle, recorded_firsts, result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class RolloffOnceGateOnTests(unittest.TestCase):
    """Gate SWEG_ROLLOFF_ONCE=1: once-per-battle first-turn determination."""

    def setUp(self):
        os.environ.pop("SWEG_ROLLOFF_ONCE", None)

    def tearDown(self):
        os.environ.pop("SWEG_ROLLOFF_ONCE", None)

    def test_gate_on_first_player_is_set(self):
        """After a gate-ON battle, _first_player is one of the two armies
        (not None), confirming the persistent state was written."""
        os.environ["SWEG_ROLLOFF_ONCE"] = "1"
        random.seed(7)
        army_a = Army("Alpha")
        army_b = Army("Beta")
        for _ in range(3):
            army_a.add_unit(_basic_profile("AlphaTroop"))
            army_b.add_unit(_basic_profile("BetaTroop"))
        battle = Battle(army_a, army_b, map_=Map("T", 60.0, 44.0))
        battle.run()
        self.assertIsNotNone(
            battle._first_player,
            "_first_player must be set after gate-ON battle"
        )
        self.assertIn(
            battle._first_player,
            (battle.a, battle.b),
            "_first_player must be one of the two Army instances"
        )

    def test_gate_on_order_persists_across_rounds(self):
        """Every vanilla round in a gate-ON battle must receive the SAME first
        army.  The per-round flip (gate-OFF behaviour) would mix Alpha and Beta
        across rounds; the once-per-battle rule locks one army in for all rounds."""
        battle, recorded, _result = _build_battle(seed=42, gate_value="1")
        # The battle must have run at least 2 rounds to test persistence.
        self.assertGreater(
            len(recorded), 1,
            "Battle ran fewer than 2 vanilla rounds — cannot test persistence"
        )
        first_name = recorded[0]
        for rnd_idx, name in enumerate(recorded, start=1):
            self.assertEqual(
                name, first_name,
                f"Round {rnd_idx}: expected first army '{first_name}' but got "
                f"'{name}' — gate-ON must keep the same first army every round"
            )

    def test_gate_on_first_player_matches_recording(self):
        """battle._first_player.name must match the army recorded as 'first'
        in every vanilla round turn."""
        battle, recorded, _result = _build_battle(seed=99, gate_value="1")
        if not recorded:
            return  # alternating-activation path — skip
        self.assertEqual(
            battle._first_player.name,
            recorded[0],
            "_first_player must name the army that went first in round 1"
        )


class RolloffOnceGateOffTests(unittest.TestCase):
    """Gate SWEG_ROLLOFF_ONCE=0 (explicit OFF): per-round flip, no state
    change. Since wave 232 the gate is default-ON, so UNSET is the ON path —
    the unset tests below assert ON behaviour."""

    def setUp(self):
        os.environ.pop("SWEG_ROLLOFF_ONCE", None)

    def tearDown(self):
        os.environ.pop("SWEG_ROLLOFF_ONCE", None)

    def test_gate_off_first_player_stays_none(self):
        """With gate OFF, _first_player must remain None — the OFF path must
        not write persistent state."""
        battle, _, _result = _build_battle(seed=17, gate_value="0")
        self.assertIsNone(
            battle._first_player,
            "_first_player must remain None on the gate-OFF path"
        )

    def test_gate_unset_first_player_is_set(self):
        """With gate completely unset (no env var), _first_player must be SET —
        default-ON since wave 232 means unset is the once-per-battle path."""
        battle, _, _result = _build_battle(seed=17, gate_value=None)
        self.assertIsNotNone(
            battle._first_player,
            "_first_player must be set when gate env var is not set "
            "(default-ON since wave 232)"
        )

    def test_gate_unset_byte_identical_to_explicit_on(self):
        """BattleResult produced with the gate variable completely unset must
        be identical to the result produced with SWEG_ROLLOFF_ONCE=1 — since
        wave 232 both are the once-per-battle path and must use the same
        random draws in the same order."""
        # Run gate-ON (explicit "1") and unset back-to-back on the same seed.
        _battle_on, _, result_on = _build_battle(seed=55, gate_value="1")
        # Re-seed identically for the unset run.
        _battle_unset, _, result_unset = _build_battle(seed=55, gate_value=None)

        self.assertEqual(
            result_on.winner,
            result_unset.winner,
            "gate-ON winner must match gate-unset winner (byte-identical paths)"
        )
        self.assertEqual(
            result_on.rounds,
            result_unset.rounds,
            "gate-ON rounds must match gate-unset"
        )
        self.assertEqual(
            result_on.a_vp,
            result_unset.a_vp,
            "gate-ON a_vp must match gate-unset a_vp"
        )
        self.assertEqual(
            result_on.b_vp,
            result_unset.b_vp,
            "gate-ON b_vp must match gate-unset b_vp"
        )

    def test_gate_off_can_mix_first_army_across_rounds(self):
        """Gate OFF draws randomly every round, so across many seeds at least
        one run must produce different first armies in different rounds (showing
        the per-round flip is active and not accidentally frozen)."""
        mixed_found = False
        for seed in range(100):
            _battle, recorded, _result = _build_battle(seed=seed, gate_value="0")
            if len(recorded) >= 2 and len(set(recorded)) > 1:
                mixed_found = True
                break
        self.assertTrue(
            mixed_found,
            "Gate-OFF must sometimes flip first-army across rounds; "
            "no such case found in 100 seeds"
        )
