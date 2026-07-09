"""AI Lab pilot-hook tests.

Two jobs:

1. THE critical regression guard: attaching NEUTRAL_GENOME pilots to both
   sides of a seeded Battle must reproduce the unhooked battle exactly —
   every BattleResult field and every event in the stream, not just the
   final score. This is the byte-identity contract the whole sandbox rests
   on (the genetic algorithm's baseline strain IS production behaviour).

2. Per-gene behaviour: pushing each of the five v1 genes away from neutral
   in its documented direction flips the specific decision it claims to
   control, on hand-built synthetic units.

The AI Lab is an exploratory sandbox outside the Stage 1 / Stage 2
calibration pipeline; these tests exercise no tournament data and no
points files.
"""

from __future__ import annotations

import os
import random
import unittest
from types import SimpleNamespace

from code.army import Army
from code.army_builder import build_homogeneous_army
from code.events import EventLog
from code.map import Map
from code.simulator import Battle
from code.strategy import _dual_engage_target, _melee_target_score, pick_move_intent
from code.units import UNIT_CATALOG, UnitProfile
from code.ai_lab.genome import DuelGenome, GENE_SPECS, NEUTRAL_GENOME
from code.ai_lab.ga import evaluate_fitness
from code.ai_lab import pilot

INTERCESSOR = "space_marines_intercessor_squad"
BOYZ = "orks_boyz"


def _duel_armies(key_a: str, key_b: str, squad_size: int = 5):
    pa = UNIT_CATALOG[key_a]
    pb = UNIT_CATALOG[key_b]
    army_a = build_homogeneous_army(
        "A", pa, pa.points_cost * squad_size, squad_size=squad_size)
    army_b = build_homogeneous_army(
        "B", pb, pb.points_cost * squad_size, squad_size=squad_size)
    return army_a, army_b


def _run_seeded(seed: int, key_a: str, key_b: str, attach_neutral: bool):
    random.seed(seed)
    army_a, army_b = _duel_armies(key_a, key_b)
    log = EventLog()
    battle = Battle(army_a, army_b, subscribers=[log])
    if attach_neutral:
        # squad_move_as_unit=False: this is the hook-INERTNESS proof — the
        # contract that the hooks themselves change nothing at neutral. The
        # AI Lab duel regime (squad_move_as_unit=True, run_duel's default)
        # deliberately diverges from raw production behaviour, identically
        # for both sides; its own guarantees are covered by
        # SquadMoveAsUnitTests below.
        pilot.attach(battle, NEUTRAL_GENOME, NEUTRAL_GENOME,
                     squad_move_as_unit=False)
    result = battle.run()
    return result, log.events


class NeutralGenomeByteIdentityTests(unittest.TestCase):
    """Neutral pilots on both sides == no pilots at all, event for event."""

    RESULT_FIELDS = (
        "winner", "rounds", "a_survivors", "b_survivors",
        "a_vp", "b_vp", "a_points_remaining", "b_points_remaining",
        "round_history",
    )

    def _assert_identical(self, seed: int, key_a: str, key_b: str):
        res_plain, ev_plain = _run_seeded(seed, key_a, key_b, False)
        res_pilot, ev_pilot = _run_seeded(seed, key_a, key_b, True)
        for f in self.RESULT_FIELDS:
            self.assertEqual(
                getattr(res_plain, f), getattr(res_pilot, f),
                f"seed {seed}: BattleResult.{f} diverged under neutral pilot",
            )
        self.assertEqual(
            len(ev_plain), len(ev_pilot),
            f"seed {seed}: event count diverged under neutral pilot",
        )
        for i, (a, b) in enumerate(zip(ev_plain, ev_pilot)):
            self.assertEqual(
                repr(a), repr(b),
                f"seed {seed}: event #{i} diverged under neutral pilot",
            )

    def test_intercessor_mirror_byte_identical(self):
        for seed in range(9100, 9110):
            self._assert_identical(seed, INTERCESSOR, INTERCESSOR)

    def test_cross_faction_byte_identical(self):
        # Boyz exercise the charge/melee paths the mirror may not reach.
        for seed in range(9200, 9203):
            self._assert_identical(seed, INTERCESSOR, BOYZ)


# ---------------------------------------------------------------------------
# Synthetic stubs for exercising the pilot callables directly
# ---------------------------------------------------------------------------

def _stub_profile(**over):
    base = dict(
        melee_attacks=3, melee_hit_probability=2 / 3, melee_damage_per_shot=1.0,
        attacks=4, hit_probability=2 / 3, per_shot_damage=1.0,
        range_inches=24, move=6.0,
    )
    base.update(over)
    return SimpleNamespace(**base)


_STUB_UID = [0]


def _stub_unit(profile, position=(0.0, 0.0), squad_id=0):
    # squad_id=0 by default: most tests exercise squad-level behaviour, and
    # the pilot deliberately keys lone models (squad_id < 0) by their own
    # uid so they never share a decision cache slot.
    _STUB_UID[0] += 1
    return SimpleNamespace(profile=profile, position=position,
                           squad_id=squad_id, uid=f"stub{_STUB_UID[0]}")


def _attached_callables(genome, enemy_units, squad_move_as_unit=False):
    """Build pilot callables wired to a fake two-army battle.

    squad_move_as_unit defaults False here (unlike attach/run_duel) because
    most gene tests probe the narrow, gene-gated overrides in isolation.
    """
    army = SimpleNamespace(name="mine", alive_units=[])
    enemy_army = SimpleNamespace(name="theirs", alive_units=list(enemy_units))
    pairs = ((army, genome), (enemy_army, NEUTRAL_GENOME))
    return (
        pilot._make_pilot_charge(pairs),
        pilot._make_pilot_move(pairs, squad_move_as_unit=squad_move_as_unit),
        army,
        enemy_army,
    )


class ChargeAggressionGeneTests(unittest.TestCase):
    """charge_aggression scales melee output in the charge-desire check."""

    def test_neutral_returns_none(self):
        pc, _, army, _ = _attached_callables(NEUTRAL_GENOME, [])
        unit = _stub_unit(_stub_profile())
        self.assertIsNone(pc(None, unit, army))

    def test_high_gene_flips_shooter_to_charger(self):
        # melee_dpa = 3 * 2/3 * 1.0 = 2.0; ranged_dpa = 4 * 2/3 * 1.0 ~ 2.67.
        # Baseline: 2.0 < 2.67 -> no charge. At 2.0x: 4.0 >= 2.67 -> charge.
        profile = _stub_profile()
        unit = _stub_unit(profile)
        self.assertFalse(pilot._scaled_wants_to_charge(profile, 1.0))
        genome = DuelGenome(charge_aggression=2.0)
        pc, _, army, _ = _attached_callables(genome, [])
        self.assertIs(pc(None, unit, army), True)

    def test_low_gene_flips_charger_to_holder(self):
        # melee_dpa = 6 * 2/3 * 1.0 = 4.0 >= ranged 2.67 -> baseline charges.
        # At 0.4x: 1.6 < max(2.67, 1.0) -> holds.
        profile = _stub_profile(melee_attacks=6)
        unit = _stub_unit(profile)
        self.assertTrue(pilot._scaled_wants_to_charge(profile, 1.0))
        genome = DuelGenome(charge_aggression=0.4)
        pc, _, army, _ = _attached_callables(genome, [])
        self.assertIs(pc(None, unit, army), False)

    def test_unbriefed_army_fails_loud(self):
        pc, _, _, _ = _attached_callables(NEUTRAL_GENOME, [])
        stranger = SimpleNamespace(name="stranger", alive_units=[])
        with self.assertRaises(KeyError):
            pc(None, _stub_unit(_stub_profile()), stranger)


class DualScaleGeneTests(unittest.TestCase):
    """charge_range_buffer / melee_engage_score_min via _dual_engage_target
    and the army-planted _ai_lab_dual_scales attribute."""

    def _mover_and_enemy(self, gap: float):
        army_a = Army("A")
        army_a.add_unit(UNIT_CATALOG[INTERCESSOR])
        mover = army_a.units[0]
        mover.position = (0.0, 30.0)
        army_b = Army("B")
        army_b.add_unit(UNIT_CATALOG[INTERCESSOR])
        enemy = army_b.units[0]
        enemy.position = (gap, 30.0)
        return mover, enemy, army_a, army_b

    def test_buffer_scale_widens_threat_range(self):
        # Intercessor move 6 + 12 = 18" baseline threat. Enemy at 20" is out
        # of it; at buffer scale 2.0 (6 + 24 = 30") it is in.
        mover, enemy, _, _ = self._mover_and_enemy(20.0)
        bare_map = Map(name="bare", width=44.0, height=60.0)
        self.assertIsNone(
            _dual_engage_target(mover, [enemy], bare_map))
        picked = _dual_engage_target(
            mover, [enemy], bare_map, threat_buffer=24.0)
        self.assertIs(picked, enemy)

    def test_score_min_scale_vetoes_marginal_target(self):
        mover, enemy, _, _ = self._mover_and_enemy(10.0)
        bare_map = Map(name="bare", width=44.0, height=60.0)
        raw = _melee_target_score(mover, enemy)
        self.assertGreater(raw, 0.0)
        # Threshold just below the raw score accepts; just above vetoes.
        self.assertIs(
            _dual_engage_target(mover, [enemy], bare_map,
                                score_min=raw * 0.9),
            enemy)
        self.assertIsNone(
            _dual_engage_target(mover, [enemy], bare_map,
                                score_min=raw * 1.1))

    def test_army_scales_attribute_reaches_pick_move_intent(self):
        # Two enemies: a near brick and a farther, higher-scoring squishy
        # gunner. Baseline threat range (18") only sees the brick; a 2.0
        # buffer scale (30") brings the gunner in, and it outscores.
        army_a = Army("A")
        army_a.add_unit(UNIT_CATALOG[INTERCESSOR])
        mover = army_a.units[0]
        mover.position = (0.0, 30.0)

        brick = UnitProfile(
            name="Brick", health=8, damage=2, hit_probability=2 / 3,
            ap=-2, save=2, strength=8, toughness=10,
            attacks=2, weapon_damage_per_shot=2.0, range_inches=12,
            leadership=8, faction="Generic", unit_keywords=("MONSTER",),
            melee_attacks=4, melee_damage_per_shot=2.0,
            melee_hit_probability=2 / 3, melee_strength=8, melee_ap=2,
        )
        gunner = UnitProfile(
            name="Gunner", health=1, damage=1, hit_probability=2 / 3,
            ap=-1, save=5, strength=3, toughness=3,
            attacks=4, weapon_damage_per_shot=1.0, range_inches=24,
            leadership=7, faction="Generic", unit_keywords=("INFANTRY",),
            melee_attacks=1, melee_damage_per_shot=1.0,
            melee_hit_probability=0.5, melee_strength=3, melee_ap=0,
        )
        army_b = Army("B")
        army_b.add_unit(brick)
        army_b.add_unit(gunner)
        brick_u, gunner_u = army_b.units
        brick_u.position = (10.0, 30.0)
        gunner_u.position = (25.0, 30.0)

        bare_map = Map(name="bare", width=44.0, height=60.0)

        pos_base, intent_base = pick_move_intent(
            mover, army_a, army_b, bare_map)
        self.assertEqual(intent_base, "ENGAGE")
        self.assertEqual(pos_base, brick_u.position)

        army_a._ai_lab_dual_scales = (2.0, 1.0)
        try:
            pos_wide, intent_wide = pick_move_intent(
                mover, army_a, army_b, bare_map)
        finally:
            del army_a._ai_lab_dual_scales
        self.assertEqual(intent_wide, "ENGAGE")
        self.assertEqual(pos_wide, gunner_u.position)


class KiteHoldRangeGeneTests(unittest.TestCase):
    def _callables(self, genome, enemy_pos, enemy_profile=None):
        enemy = _stub_unit(enemy_profile or _stub_profile(),
                           position=enemy_pos)
        pc, pm, army, enemy_army = _attached_callables(genome, [enemy])
        return pm, army, enemy_army

    def test_zero_gene_is_structural_noop(self):
        pm, army, enemy_army = self._callables(NEUTRAL_GENOME, (10.0, 0.0))
        unit = _stub_unit(_stub_profile())
        self.assertIsNone(
            pm(None, unit, army, enemy_army, (10.0, 0.0), "ENGAGE"))

    def test_in_range_shooter_holds(self):
        # Enemy 10" out, gun range 24", clearance 9" >= gene 3" -> HOLD here.
        genome = DuelGenome(kite_hold_range=3.0)
        pm, army, enemy_army = self._callables(genome, (10.0, 0.0))
        unit = _stub_unit(_stub_profile())
        result = pm(None, unit, army, enemy_army, (10.0, 0.0), "ENGAGE")
        self.assertEqual(result, ((0.0, 0.0), "HOLD"))

    def test_gap_too_small_defers_to_baseline(self):
        # Enemy 3" out: clearance 2" < gene 3" -> no override.
        genome = DuelGenome(kite_hold_range=3.0)
        pm, army, enemy_army = self._callables(genome, (3.0, 0.0))
        unit = _stub_unit(_stub_profile())
        self.assertIsNone(
            pm(None, unit, army, enemy_army, (3.0, 0.0), "ENGAGE"))

    def test_melee_dominant_unit_never_kites(self):
        # A unit that wants to charge (under its own charge_aggression)
        # keeps closing even with the kite gene set.
        genome = DuelGenome(kite_hold_range=3.0)
        pm, army, enemy_army = self._callables(genome, (10.0, 0.0))
        brawler = _stub_unit(_stub_profile(melee_attacks=6))
        self.assertIsNone(
            pm(None, brawler, army, enemy_army, (10.0, 0.0), "ENGAGE"))


class AdvanceVsHoldBiasGeneTests(unittest.TestCase):
    def test_zero_gene_is_structural_noop(self):
        enemy = _stub_unit(_stub_profile(), position=(10.0, 0.0))
        _, pm, army, enemy_army = _attached_callables(NEUTRAL_GENOME, [enemy])
        unit = _stub_unit(_stub_profile())
        self.assertIsNone(
            pm(None, unit, army, enemy_army, (0.0, 0.0), "HOLD"))

    def test_positive_bias_nudges_toward_enemy(self):
        genome = DuelGenome(advance_vs_hold_bias=2.0)
        enemy = _stub_unit(_stub_profile(), position=(10.0, 0.0))
        _, pm, army, enemy_army = _attached_callables(genome, [enemy])
        unit = _stub_unit(_stub_profile())
        result = pm(None, unit, army, enemy_army, (0.0, 0.0), "HOLD")
        self.assertIsNotNone(result)
        (nx, ny), intent = result
        self.assertEqual(intent, "REPOSITION")
        self.assertAlmostEqual(nx, 2.0)
        self.assertAlmostEqual(ny, 0.0)

    def test_negative_bias_nudges_away(self):
        genome = DuelGenome(advance_vs_hold_bias=-2.0)
        enemy = _stub_unit(_stub_profile(), position=(10.0, 0.0))
        _, pm, army, enemy_army = _attached_callables(genome, [enemy])
        unit = _stub_unit(_stub_profile())
        (nx, ny), intent = pm(None, unit, army, enemy_army,
                              (0.0, 0.0), "HOLD")
        self.assertEqual(intent, "REPOSITION")
        self.assertAlmostEqual(nx, -2.0)
        self.assertAlmostEqual(ny, 0.0)

    def test_nudge_capped_at_unit_move(self):
        # Bias 4" but the documented cap is effective_move (6" Intercessor
        # stub); use an oversized bias via range clamp bypass: the gene range
        # caps at 4.0, so cap-vs-move only binds for slow units. Use a slow
        # profile (move 1.5) to prove the min().
        genome = DuelGenome(advance_vs_hold_bias=4.0)
        enemy = _stub_unit(_stub_profile(), position=(10.0, 0.0))
        _, pm, army, enemy_army = _attached_callables(genome, [enemy])
        slow = _stub_unit(_stub_profile(move=1.5))
        (nx, ny), _ = pm(None, slow, army, enemy_army, (0.0, 0.0), "HOLD")
        self.assertAlmostEqual(nx, 1.5)


class SquadCohesionTests(unittest.TestCase):
    """Two related findings from manual testing, both real, pulling in
    opposite directions — this class pins both so neither regresses.

    1. ENGAGE-target divergence (a genuine bug, now fixed). A genome that
       suppresses charging forces Intercessors into a multi-round WALK
       instead of a single-round charge; while walking, the DUAL branch's
       per-model choice of WHICH ENEMY MODEL to engage is computed
       independently per model, and squad members a few inches apart can
       walk toward different models — verified to already be true of an
       UNMODIFIED baseline battle with a naturally non-charging DUAL unit
       (Drukhari Wracks), so this is a pre-existing simulator
       characteristic. code/ai_lab/pilot.py's `walk_targets` cache fixes
       it for ENGAGE only: cache the first squad member's own baseline
       ENGAGE target each round and share it with the rest.

    2. CAPTURE/STEAL-target divergence must NOT be "fixed" the same way —
       a second, more severe bug found and reverted in manual testing.
       Individual squad members legitimately picking DIFFERENT objective
       markers is not a defect: it is how a squad spreads across the
       board to hold multiple objectives and score Victory Points, and
       the FROZEN BASELINE OPPONENT relies on exactly this to win. Coor-
       dinating CAPTURE/STEAL the same way as ENGAGE was tried, measured,
       and reverted: it glued every model in a squad onto one shared
       objective marker, forfeiting three or four objectives' worth of
       Victory Points every game. Because melee_engage_score_min's range
       (0.2-20.0) essentially never lands exactly on its neutral 1.0 for
       any mutated genome, that bug fired on almost every genome the
       search ever produced — measured win rate against baseline
       collapsed to roughly 6-10% even for a genome differing from
       neutral by less than 1% in a single gene, regardless of direction
       or magnitude. This is why every evolution run reported "epoch
       exhausted without a promotion" no matter how the parameters were
       tuned. `test_tiny_perturbation_does_not_collapse_win_rate` below
       is the direct regression guard for this.
    """

    def test_engage_target_is_shared_across_squad(self):
        # Two squadmates a few inches apart, and two enemy models whose
        # _melee_target_score the DUAL branch would rank differently
        # depending on which attacker position it's measured from (the
        # exact mechanism that let a squad split in production). With the
        # charge-axis gene active, both squadmates must return the SAME
        # target — proving the coordination cache, not each attacker's own
        # nearest-target computation, decides where the squad walks.
        genome = DuelGenome(melee_engage_score_min=2.0)
        _, pm, army, enemy_army = _attached_callables(genome, [])
        mover_a = _stub_unit(_stub_profile(), position=(0.0, 0.0))
        mover_b = _stub_unit(_stub_profile(), position=(3.0, 0.0))
        target_for_a = (20.0, 5.0)
        target_for_b = (20.0, -5.0)   # a plausible DIFFERENT pick for mover_b

        first = pm(None, mover_a, army, enemy_army, target_for_a, "ENGAGE")
        self.assertIsNone(first)   # first evaluator keeps its own target

        second = pm(None, mover_b, army, enemy_army, target_for_b, "ENGAGE")
        self.assertEqual(
            second, (target_for_a, "ENGAGE"),
            "second squad member must be redirected to the FIRST member's "
            "target, not walk toward its own independently-picked one",
        )

    def test_capture_target_is_not_coordinated(self):
        # The deliberate asymmetry: CAPTURE must NOT be shared, even with
        # the same charge-axis gene active, or objective-spreading breaks.
        genome = DuelGenome(melee_engage_score_min=2.0)
        _, pm, army, enemy_army = _attached_callables(genome, [])
        mover_a = _stub_unit(_stub_profile(), position=(0.0, 0.0))
        mover_b = _stub_unit(_stub_profile(), position=(3.0, 0.0))
        pm(None, mover_a, army, enemy_army, (20.0, 5.0), "CAPTURE")
        second = pm(None, mover_b, army, enemy_army, (20.0, -5.0), "CAPTURE")
        self.assertIsNone(
            second,
            "CAPTURE targets must be left to each model's own baseline "
            "pick — coordinating them glues the squad onto one objective "
            "and forfeits the rest to the opponent (see class docstring)",
        )

    def test_tiny_perturbation_does_not_collapse_win_rate(self):
        # Regression guard for the CAPTURE-coordination bug: a genome only
        # 1% off neutral in a single charge-axis gene must NOT crater to a
        # tiny fraction of the neutral baseline's win rate. This is a real
        # battle measurement (not mocked) because the bug lived in how
        # pick_move_intent's CAPTURE branch interacts with real objective
        # scoring across a real 5-round game — nothing about it is visible
        # from a synthetic single-call unit test.
        near_neutral = DuelGenome(charge_aggression=0.99)
        fr = evaluate_fitness(near_neutral, NEUTRAL_GENOME, epoch=900,
                              generation=0, n_duels=40, margin_weight=0.0)
        self.assertGreater(
            fr.win_rate, 0.30,
            f"a genome 1% off neutral scored only {fr.win_rate:.2f} win "
            f"rate against the neutral baseline over {fr.n} duels — "
            f"squad-coordination is glueing the squad onto one objective "
            f"again (see class docstring, finding 2)",
        )


class SquadMoveAsUnitTests(unittest.TestCase):
    """The AI Lab duel regime (attach/run_duel default): every squad's walk
    intents (CAPTURE / STEAL / ENGAGE) are decided once per squad per round
    and shared across its models, on BOTH sides symmetrically — the
    harness-level answer to squads visibly scattering model-by-model across
    objectives, which real 10e Unit Coherency forbids but the simulator's
    one-Unit-per-model representation allows. Symmetry is the load-bearing
    property: coordinating only one side (an earlier, gene-gated version)
    forfeited the Victory Point race and collapsed measured win rates to
    6-10% — see AI_LAB_PLAN.md "Squad cohesion under _pilot_move".
    """

    def test_capture_is_coordinated_even_at_neutral(self):
        # Unlike the gene-gated regime, the flag applies to a NEUTRAL
        # genome too — the baseline side plays under the same movement
        # discipline as every challenger.
        _, pm, army, enemy_army = _attached_callables(
            NEUTRAL_GENOME, [], squad_move_as_unit=True)
        mover_a = _stub_unit(_stub_profile(), position=(0.0, 0.0))
        mover_b = _stub_unit(_stub_profile(), position=(3.0, 0.0))
        first = pm(None, mover_a, army, enemy_army, (20.0, 5.0), "CAPTURE")
        self.assertIsNone(first)   # first evaluator keeps its own pick
        second = pm(None, mover_b, army, enemy_army, (20.0, -5.0), "CAPTURE")
        self.assertEqual(second, ((20.0, 5.0), "CAPTURE"))

    def test_hold_is_never_coordinated(self):
        # Position-relative intents stay per-model in both regimes.
        _, pm, army, enemy_army = _attached_callables(
            NEUTRAL_GENOME, [], squad_move_as_unit=True)
        mover_a = _stub_unit(_stub_profile(), position=(0.0, 0.0))
        mover_b = _stub_unit(_stub_profile(), position=(3.0, 0.0))
        pm(None, mover_a, army, enemy_army, (0.0, 0.0), "HOLD")
        self.assertIsNone(
            pm(None, mover_b, army, enemy_army, (3.0, 0.0), "HOLD"))

    def test_lone_models_are_not_coordinated_with_each_other(self):
        # Two lone models (squad_id < 0) are separate one-model units and
        # must never share a walk target — the cache keys them by uid.
        _, pm, army, enemy_army = _attached_callables(
            NEUTRAL_GENOME, [], squad_move_as_unit=True)
        solo_a = _stub_unit(_stub_profile(), position=(0.0, 0.0),
                            squad_id=-1)
        solo_b = _stub_unit(_stub_profile(), position=(3.0, 0.0),
                            squad_id=-1)
        pm(None, solo_a, army, enemy_army, (20.0, 5.0), "CAPTURE")
        self.assertIsNone(
            pm(None, solo_b, army, enemy_army, (20.0, -5.0), "CAPTURE"))

    def test_real_battles_keep_squads_together(self):
        # The user-facing guarantee, measured the way the scatter was first
        # noticed: final squad spread in real seeded duels, with an ACTIVE
        # genome (worst case: suppressed charging forces multi-round walks).
        genome = DuelGenome(kite_hold_range=4.0, advance_vs_hold_bias=3.0,
                            charge_aggression=0.4)
        for seed in (7001, 7002, 7010):
            random.seed(seed)
            army_a, army_b = _duel_armies(INTERCESSOR, INTERCESSOR)
            battle = Battle(army_a, army_b)
            pilot.attach(battle, genome, genome)   # flag defaults True
            battle.run()
            for army in (battle.a, battle.b):
                alive = [u for u in army.units if u.is_alive]
                if len(alive) < 2:
                    continue
                cx = sum(u.position[0] for u in alive) / len(alive)
                cy = sum(u.position[1] for u in alive) / len(alive)
                mean_spread = sum(
                    ((u.position[0] - cx) ** 2 + (u.position[1] - cy) ** 2)
                    ** 0.5 for u in alive) / len(alive)
                self.assertLess(
                    mean_spread, 4.0,
                    f"seed {seed} {army.name}: mean spread "
                    f"{mean_spread:.2f}\" — squads are scattering again "
                    f"under squad_move_as_unit",
                )


class AttachWiringTests(unittest.TestCase):
    def test_neutral_attach_plants_no_dual_scales(self):
        army_a, army_b = _duel_armies(INTERCESSOR, INTERCESSOR)
        battle = Battle(army_a, army_b)
        pilot.attach(battle, NEUTRAL_GENOME, NEUTRAL_GENOME)
        self.assertFalse(hasattr(army_a, "_ai_lab_dual_scales"))
        self.assertFalse(hasattr(army_b, "_ai_lab_dual_scales"))
        self.assertIsNotNone(getattr(battle, "_pilot_move", None))
        self.assertIsNotNone(getattr(battle, "_pilot_charge", None))

    def test_nonneutral_attach_plants_dual_scales(self):
        army_a, army_b = _duel_armies(INTERCESSOR, INTERCESSOR)
        battle = Battle(army_a, army_b)
        genome = DuelGenome(charge_range_buffer=1.5,
                            melee_engage_score_min=2.0)
        pilot.attach(battle, genome, NEUTRAL_GENOME)
        self.assertEqual(army_a._ai_lab_dual_scales, (1.5, 2.0))
        self.assertFalse(hasattr(army_b, "_ai_lab_dual_scales"))

    def test_squadact_gate_fails_loud(self):
        army_a, army_b = _duel_armies(INTERCESSOR, INTERCESSOR)
        battle = Battle(army_a, army_b)
        old = os.environ.get("SWEG_SQUADACT")
        os.environ["SWEG_SQUADACT"] = "1"
        try:
            with self.assertRaises(RuntimeError):
                pilot.attach(battle, NEUTRAL_GENOME, NEUTRAL_GENOME)
        finally:
            if old is None:
                del os.environ["SWEG_SQUADACT"]
            else:
                os.environ["SWEG_SQUADACT"] = old


class GenomeSpecTests(unittest.TestCase):
    def test_neutral_genome_is_neutral(self):
        self.assertTrue(NEUTRAL_GENOME.is_neutral())
        self.assertFalse(DuelGenome(charge_aggression=1.2).is_neutral())

    def test_round_trip_dict(self):
        g = DuelGenome(charge_aggression=1.3, kite_hold_range=2.5)
        self.assertEqual(DuelGenome.from_dict(g.as_dict()), g)

    def test_from_dict_fails_loud_on_unknown_and_missing(self):
        with self.assertRaises(KeyError):
            DuelGenome.from_dict({"not_a_gene": 1.0})
        d = NEUTRAL_GENOME.as_dict()
        d.pop("charge_aggression")
        with self.assertRaises(KeyError):
            DuelGenome.from_dict(d)

    def test_specs_cover_every_field(self):
        self.assertEqual(
            {s.name for s in GENE_SPECS},
            set(NEUTRAL_GENOME.as_dict().keys()),
        )


if __name__ == "__main__":
    unittest.main()
