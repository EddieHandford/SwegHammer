"""Displacement Stage-0 FIGHT-OUTCOME instrument (gate SWEG_DISPLACE_INSTR).

The instrument (code/displace_instr.py) measures, per faction-matchup and per game,
how many primary victory points the simulator's raw-summed-Objective-Control marker
model awards in board states real play would resolve differently — the displacement
gap — BEFORE any behavioural build. It is OBSERVATION-ONLY: it changes no decision and
consumes no randomness, so the gate-OFF path is byte-identical (including the random
stream) and gate-ON produces the same winner + score for the same seed.

These tests pin:
  (a) OBSERVATION-ONLY: the instrument code is not invoked with the gate off, and a
      fixed-seed battle produces the IDENTICAL winner + victory points whether the gate
      is off or on (run the same seed under each gate, compare outcome).
  (b) WELL-FORMED ON: the per-game summary is well-formed, every total is non-negative,
      and a marker-tick files into AT MOST ONE classification bucket (mutually exclusive).
  (c) FAIL-LOUD (project rule 13): a controller name matching neither army raises, with
      no silent .get default.
"""

from __future__ import annotations

import os
import random
import unittest

from code import displace_instr
from code.army import Army
from code.army_builder import build_faction_random_army
from code.map import Map, Objective
from code.simulator import Battle
from code.units import UnitProfile


# --------------------------------------------------------------------------- helpers

def _holder(name: str = "Holder", oc: int = 4) -> UnitProfile:
    return UnitProfile(
        name=name, health=4.0, damage=1.0, hit_probability=0.5, ap=0, save=4,
        strength=4, toughness=4, attacks=1, weapon_damage_per_shot=1.0,
        range_inches=12, unit_keywords=("INFANTRY",), oc=oc,
        melee_attacks=1, melee_hit_probability=0.5, melee_strength=4,
        melee_damage_per_shot=1.0,
    )


def _run_seeded_battle(seed: int):
    """Build two small faction armies deterministically and run one battle. Returns the
    BattleResult. The global `random` module is seeded so `Battle.run`'s rolls reproduce.
    """
    random.seed(seed)
    a = build_faction_random_army(
        "A", "Astra Militarum", 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army(
        "B", "Tyranids", 2000, rng=random.Random(seed + 10000), use_archetype=True)
    random.seed(seed)   # re-seed AFTER army construction so the battle stream is fixed
    return Battle(a, b).run()


# --------------------------------------------------------------------------- (a)

class ObservationOnlyTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop(displace_instr.GATE_ENV, None)

    def tearDown(self):
        os.environ.pop(displace_instr.GATE_ENV, None)

    def test_gate_off_does_not_construct_instrument(self):
        os.environ.pop(displace_instr.GATE_ENV, None)
        a = Army("A"); a.add_unit(_holder())
        b = Army("B"); b.add_unit(_holder())
        battle = Battle(a, b, map_=Map("T", 60.0, 44.0))
        self.assertIsNone(
            battle._displace, "gate OFF must not construct the instrument")
        # The damage tap must be a no-op when the instrument is None.
        battle._displace_tap(a, b.units[0], 5.0)   # must not raise
        res = battle.run()
        self.assertIsNone(res.displace, "gate OFF result.displace must be None")

    def test_gate_on_constructs_instrument(self):
        os.environ[displace_instr.GATE_ENV] = "1"
        a = Army("A"); a.add_unit(_holder())
        b = Army("B"); b.add_unit(_holder())
        battle = Battle(a, b, map_=Map("T", 60.0, 44.0))
        self.assertIsNotNone(
            battle._displace, "gate ON must construct the instrument")

    def test_same_seed_off_vs_on_identical_outcome(self):
        """OBSERVATION-ONLY: the same seed produces the identical winner + victory points
        whether the instrument is off or on (it consumes no randomness, changes nothing)."""
        seed = 4
        os.environ.pop(displace_instr.GATE_ENV, None)
        off = _run_seeded_battle(seed)
        os.environ[displace_instr.GATE_ENV] = "1"
        try:
            on = _run_seeded_battle(seed)
        finally:
            os.environ.pop(displace_instr.GATE_ENV, None)
        self.assertEqual(off.winner, on.winner, "winner must be identical OFF vs ON")
        self.assertEqual((off.a_vp, off.b_vp), (on.a_vp, on.b_vp),
                         "victory points must be identical OFF vs ON")
        self.assertEqual(off.rounds, on.rounds, "round count must be identical OFF vs ON")
        # The OFF result carries no summary; the ON result must carry a well-formed one.
        self.assertIsNone(off.displace)
        self.assertIsNotNone(on.displace)


# --------------------------------------------------------------------------- (b)

def _two_obj_battle(gate: bool = True):
    """A two-objective battle wired so we can drive `record_damage` + `_score_objectives`
    by hand. Returns (battle, objectives)."""
    if gate:
        os.environ[displace_instr.GATE_ENV] = "1"
    objs = (
        Objective("Left", 20.0, 22.0, control_radius=3.0, vp_per_round=5),
        Objective("Right", 40.0, 22.0, control_radius=3.0, vp_per_round=5),
    )
    a = Army("A"); a.add_unit(_holder()); a.add_unit(_holder())
    b = Army("B"); b.add_unit(_holder()); b.add_unit(_holder())
    battle = Battle(a, b, map_=Map("T", 60.0, 44.0, objectives=objs))
    battle._assign_uids()
    battle._current_round = 2
    battle._a_vp = 0
    battle._b_vp = 0
    battle._sticky_owner = {}
    return battle, objs


class WellFormedSummaryTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop(displace_instr.GATE_ENV, None)

    def test_summary_well_formed_and_non_negative(self):
        battle, objs = _two_obj_battle()
        # Left: A holds it uncontested, B has a body within 12" → over-pole candidate.
        battle.a.units[0].position = (20.0, 22.0)
        battle.b.units[0].position = (29.0, 22.0)   # 9" away from Left, OC nearby
        # Right: A holds it but was out-fought there (B dealt heavy damage to A's unit).
        battle.a.units[1].position = (40.0, 22.0)
        battle.b.units[1].position = (5.0, 40.0)    # B far from Right (no OC there)
        # Record local damage at Right: B dealt 10 to A, A dealt 1 to B → A out-fought.
        battle._displace.record_damage(
            attacker_is_a=False, defender=battle.a.units[1], objectives=objs, dmg=10.0)
        battle._displace.record_damage(
            attacker_is_a=True, defender=battle.b.units[1], objectives=objs, dmg=1.0)
        battle._score_objectives()

        summary = battle._displace.summary()
        # Well-formed: both sides present + the contested-tick count.
        self.assertIn("a", summary)
        self.assertIn("b", summary)
        self.assertIn("contested_marker_ticks", summary)
        for side in ("a", "b"):
            s = summary[side]
            for key in (
                "vp_addressable_underpole", "vp_addressable_overpole",
                "tarpit_vp_denied",
            ):
                self.assertGreaterEqual(s[key], 0.0, f"{side}.{key} must be non-negative")
            for key in (
                "underpole_ticks", "overpole_ticks", "tarpit_ticks", "contested_ticks",
            ):
                self.assertGreaterEqual(s[key], 0, f"{side}.{key} must be non-negative")
        self.assertGreaterEqual(summary["contested_marker_ticks"], 0)

    def test_classifications_mutually_exclusive_per_tick(self):
        """A single marker-tick files into AT MOST ONE bucket. Drive one isolated marker
        with an out-fought controller and assert exactly one bucket incremented."""
        battle, objs = _two_obj_battle()
        # Only one objective contested: put everything at Left, nothing at Right.
        battle.a.units[0].position = (20.0, 22.0)   # A controls Left
        battle.b.units[0].position = (5.0, 40.0)    # B nowhere near Left
        # Park the spare models far off both markers so only Left ticks.
        battle.a.units[1].position = (5.0, 5.0)
        battle.b.units[1].position = (55.0, 40.0)
        # A out-fought at Left (received 8, dealt 0).
        battle._displace.record_damage(
            attacker_is_a=False, defender=battle.a.units[0], objectives=objs, dmg=8.0)
        battle._score_objectives()

        sa = battle._displace.a
        sb = battle._displace.b
        # Exactly one bucket fired across BOTH sides for this single Left tick: the
        # under-pole bucket on A (controller out-fought). Right had no controller.
        total_addressable_ticks = (
            sa.underpole_ticks + sa.overpole_ticks + sa.tarpit_ticks
            + sb.underpole_ticks + sb.overpole_ticks + sb.tarpit_ticks
            + sa.contested_ticks + sb.contested_ticks
        )
        self.assertEqual(total_addressable_ticks, 1,
                         "exactly one bucket may fire for one marker-tick")
        self.assertEqual(sa.underpole_ticks, 1, "A should be the out-fought (under-pole) holder")
        self.assertEqual(sa.vp_addressable_underpole, 5.0)

    def test_tarpit_classified_separately(self):
        """A loser in engagement range of the local holder = faithful tarpit, NOT under/
        over-pole. Counted in tarpit_vp_denied for the tarpitting side.

        A must still CONTROL Left (strictly greater OC), so both A models sit on Left
        (OC 8) while B's single model in engagement range only contributes OC 4 — A wins
        the contest yet B is dying on the marker in engagement range (the faithful tarpit).
        """
        battle, objs = _two_obj_battle()
        battle.a.units[0].position = (20.0, 22.0)   # A on Left
        battle.a.units[1].position = (20.3, 22.0)   # second A on Left → A OC 8
        battle.b.units[0].position = (20.7, 22.0)   # B in ER of A's holders, OC 4 (loses)
        battle.b.units[1].position = (55.0, 40.0)   # B spare far away
        # A out-fought at Left too (received damage) — tarpit must still pre-empt.
        battle._displace.record_damage(
            attacker_is_a=False, defender=battle.a.units[0], objectives=objs, dmg=8.0)
        battle._score_objectives()
        # B is in ER of A's controlling holders → tarpit on B; A's under-pole must NOT fire.
        self.assertEqual(battle._displace.b.tarpit_ticks, 1)
        self.assertEqual(battle._displace.a.underpole_ticks, 0,
                         "tarpit must pre-empt the under-pole bucket")

    def test_overpole_uncontested_hold(self):
        """A single durable holder on an uncontested marker with a nearby enemy body =
        over-pole addressable."""
        battle, objs = _two_obj_battle()
        battle.a.units[0].position = (20.0, 22.0)   # A holds Left, uncontested
        battle.b.units[0].position = (29.0, 22.0)   # B body 9" from Left (within 12")
        battle.a.units[1].position = (5.0, 5.0)
        battle.b.units[1].position = (55.0, 40.0)
        # No fighting at Left → not under-pole, not tarpit → over-pole.
        battle._score_objectives()
        self.assertEqual(battle._displace.a.overpole_ticks, 1)
        self.assertEqual(battle._displace.a.vp_addressable_overpole, 5.0)
        self.assertEqual(battle._displace.a.underpole_ticks, 0)


# --------------------------------------------------------------------------- (c)

class FailLoudTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop(displace_instr.GATE_ENV, None)

    def test_unknown_controller_raises(self):
        """Rule 13: a controller name matching neither army must raise, not silently
        default. This guards the classify_tick lookup."""
        instr = displace_instr.DisplaceInstr("Astra Militarum", "Tyranids")
        obj = Objective("X", 20.0, 22.0, control_radius=3.0, vp_per_round=5)
        with self.assertRaises(ValueError):
            instr.classify_tick(
                obj_idx=0, obj=obj, controller="Orks",   # neither A nor B
                a_name="A", b_name="B", a_oc=3, b_oc=0, vp=5,
                army_a=None, army_b=None, battleshocked=set(),
                effective_oc=lambda u: 1,
                squad_in_range_count=lambda army, o: 1,
            )

    def test_none_controller_is_no_op(self):
        """A None controller (nobody scores) files nothing and does not raise."""
        instr = displace_instr.DisplaceInstr("Astra Militarum", "Tyranids")
        obj = Objective("X", 20.0, 22.0, control_radius=3.0, vp_per_round=5)
        instr.classify_tick(
            obj_idx=0, obj=obj, controller=None,
            a_name="A", b_name="B", a_oc=0, b_oc=0, vp=0,
            army_a=None, army_b=None, battleshocked=set(),
            effective_oc=lambda u: 1,
            squad_in_range_count=lambda army, o: 0,
        )
        s = instr.summary()
        self.assertEqual(s["a"]["underpole_ticks"], 0)
        self.assertEqual(s["b"]["underpole_ticks"], 0)


if __name__ == "__main__":
    unittest.main()
