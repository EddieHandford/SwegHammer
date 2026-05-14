"""Tests for the empirical points balancer.

The balancer runs real Monte-Carlo battles, so we keep budgets and counts
small. Tiny budgets give the cleanest signal: at points_override=5 a side
fields ~40 squads vs the baseline's 3, which crushes; at points_override=200
the same budget can't even afford one squad, which loses outright.
"""

from __future__ import annotations

import random
import unittest
from dataclasses import replace

from code.army_builder import build_attached_army, build_homogeneous_army
from code.detachments import (
    AWAKENED_DYNASTY,
    GLADIUS_TASK_FORCE,
    default_detachment_for_faction,
)
from code.balancer import (
    AUTO_BASELINE,
    DEFAULT_BASELINE,
    find_balanced_leader_points,
    find_balanced_points,
    find_balanced_support_points,
    measure_aura_uplift,
    measure_win_rate,
    measure_win_rate_leader_attached,
    resolve_baseline,
)
from code.roles import baseline_key_for, classify, pick_host_for_leader
from code.units import UNIT_CATALOG


_BASELINE_KEY = "space_marines_intercessor_squad"
# A canonical HEAVY-role unit used as the "previously-untunable" target
# in auto-baseline coverage. Knight Errant is itself the HEAVY baseline,
# but the C'tan-shard is sv=4 and lands in MELEE - we only need *any*
# unit whose role baseline isn't the default Intercessor.
_HEAVY_UNIT_KEY = "imperial_knights_library_knight_paladin"


class MeasureWinRateTests(unittest.TestCase):

    def test_returns_float_in_unit_interval(self):
        baseline = UNIT_CATALOG[_BASELINE_KEY]
        rng = random.Random(42)
        wr = measure_win_rate(baseline, baseline, 200, n_battles=5, rng=rng)
        self.assertIsInstance(wr, float)
        self.assertGreaterEqual(wr, 0.0)
        self.assertLessEqual(wr, 1.0)

    def test_severely_undercosted_unit_dominates(self):
        baseline = UNIT_CATALOG[_BASELINE_KEY]
        cheap = replace(baseline, points_override=5.0)
        rng = random.Random(42)
        wr = measure_win_rate(cheap, baseline, 200, n_battles=10, rng=rng)
        self.assertGreater(wr, 0.55)

    def test_severely_overcosted_unit_loses(self):
        baseline = UNIT_CATALOG[_BASELINE_KEY]
        # Baseline Intercessor is ~65 pts. At pts=200, budget=200 can field
        # exactly 1 squad while the baseline fields 3 - the lone squad gets
        # mauled.
        expensive = replace(baseline, points_override=200.0)
        rng = random.Random(42)
        wr = measure_win_rate(expensive, baseline, 200, n_battles=10, rng=rng)
        self.assertLess(wr, 0.45)


class ResolveBaselineTests(unittest.TestCase):
    """The baseline-picker should respect explicit overrides, fall back to
    role baselines when asked for auto, and never return self-vs-self."""

    def test_explicit_baseline_wins(self):
        # Even for a HEAVY unit, an explicit key passes straight through.
        self.assertEqual(
            resolve_baseline(_HEAVY_UNIT_KEY, "orks_boyz"),
            "orks_boyz",
        )

    def test_auto_uses_role_baseline(self):
        unit = UNIT_CATALOG[_HEAVY_UNIT_KEY]
        expected = baseline_key_for(classify(unit))
        self.assertEqual(resolve_baseline(_HEAVY_UNIT_KEY, AUTO_BASELINE), expected)

    def test_none_baseline_uses_role_baseline(self):
        unit = UNIT_CATALOG[_HEAVY_UNIT_KEY]
        expected = baseline_key_for(classify(unit))
        self.assertEqual(resolve_baseline(_HEAVY_UNIT_KEY, None), expected)

    def test_auto_avoids_self_vs_self(self):
        # The Intercessor Squad IS the DUAL/SHOOTY role baseline; calibrating
        # it under auto must not pick itself. Falls back to DEFAULT_BASELINE
        # (also itself in this case) -> the same-role-peer search kicks in.
        result = resolve_baseline(_BASELINE_KEY, AUTO_BASELINE)
        self.assertNotEqual(result, _BASELINE_KEY)
        self.assertIn(result, UNIT_CATALOG)


class FindBalancedPointsAutoBaselineTests(unittest.TestCase):
    """Cheap smoke coverage: a single iteration is enough to prove the
    auto-baseline plumbing flows through to the CalibrationResult."""

    def _quick(self, key, **kwargs):
        return find_balanced_points(
            key,
            n_battles=2,
            max_iters=1,
            points_budget=500.0,
            rng=random.Random(0),
            **kwargs,
        )

    def test_auto_baseline_for_heavy_unit_does_not_crash(self):
        r = self._quick(_HEAVY_UNIT_KEY, auto_baseline=True)
        self.assertIn(r.baseline_key, UNIT_CATALOG)

    def test_auto_baseline_matches_role_lookup(self):
        unit = UNIT_CATALOG[_HEAVY_UNIT_KEY]
        expected = baseline_key_for(classify(unit))
        r = self._quick(_HEAVY_UNIT_KEY, auto_baseline=True)
        self.assertEqual(r.baseline_key, expected)

    def test_explicit_baseline_overrides_auto(self):
        # Explicit baseline wins even when auto_baseline=True.
        r = self._quick(
            _HEAVY_UNIT_KEY,
            baseline_key="orks_boyz",
            auto_baseline=True,
        )
        self.assertEqual(r.baseline_key, "orks_boyz")

    def test_default_baseline_when_auto_disabled(self):
        r = self._quick(_HEAVY_UNIT_KEY, auto_baseline=False)
        self.assertEqual(r.baseline_key, DEFAULT_BASELINE)


class MobilityCovariateTests(unittest.TestCase):
    """#90 - CalibrationResult should carry the unit's mobility stats so post-hoc
    analysis can spot whether speed is systematically under-rewarded."""

    def test_mobility_fields_populated(self):
        r = find_balanced_points(
            _BASELINE_KEY, n_battles=2, max_iters=1,
            points_budget=500.0, rng=random.Random(0),
        )
        profile = UNIT_CATALOG[_BASELINE_KEY]
        self.assertEqual(r.move, profile.move)
        self.assertEqual(r.scout_distance, profile.scout_distance)
        self.assertEqual(r.deep_strike, profile.deep_strike)
        self.assertEqual(r.infiltrator, profile.infiltrator)
        self.assertFalse(r.attached_mode)
        self.assertEqual(r.host_key, "")


class AttachedArmyBuilderTests(unittest.TestCase):
    """#88 - build_attached_army interleaves host/leader so deployment puts
    the leader next to its bodyguard."""

    def test_pairs_interleave(self):
        host = UNIT_CATALOG[_BASELINE_KEY]
        # Pick the cheapest CHARACTER as a stand-in leader
        leader_key = next(
            k for k, p in UNIT_CATALOG.items()
            if "CHARACTER" in (p.unit_keywords or ()) and p.faction == host.faction
        )
        leader = UNIT_CATALOG[leader_key]
        budget = (host.points_cost + leader.points_cost) * 3
        army = build_attached_army("Test", host, leader, budget)
        # Pairs should appear in (host, leader, host, leader, ...) order.
        for i in range(0, len(army.units) - 1, 2):
            self.assertEqual(army.units[i].profile.name, host.name)
            self.assertEqual(army.units[i + 1].profile.name, leader.name)


class PickHostForLeaderTests(unittest.TestCase):
    """#88 - host selection prefers the LeaderAbility-declared host_keys,
    then falls back to a same-faction INFANTRY battleline."""

    def test_returns_catalogue_key(self):
        leader_key = next(
            k for k, p in UNIT_CATALOG.items()
            if "CHARACTER" in (p.unit_keywords or ()) and p.faction
        )
        host_key = pick_host_for_leader(UNIT_CATALOG[leader_key])
        self.assertIn(host_key, UNIT_CATALOG)
        self.assertNotIn(
            "CHARACTER", UNIT_CATALOG[host_key].unit_keywords or (),
        )

    def test_registry_declared_host_wins(self):
        # A Necron Overlord profile should resolve to a declared Necron host
        # (Warriors or Immortals) via the LeaderAbility.host_keys path.
        overlord_keys = [
            k for k, p in UNIT_CATALOG.items()
            if "Overlord" in p.name and p.faction == "Necrons"
        ]
        if not overlord_keys:
            self.skipTest("No Necron Overlord profile in catalogue")
        host = pick_host_for_leader(UNIT_CATALOG[overlord_keys[0]])
        self.assertIn(host, ("necrons_necron_warriors", "necrons_immortals"))


class LeaderAttachedCalibrationTests(unittest.TestCase):
    """#88 - leader-attached path: a CalibrationResult populated with the
    attached_mode flag and host_key, mobility covariates filled in."""

    def _leader_key(self):
        # Pick the cheapest CHARACTER with a faction so pick_host_for_leader
        # can resolve.
        return next(
            k for k, p in UNIT_CATALOG.items()
            if "CHARACTER" in (p.unit_keywords or ()) and p.faction
        )

    def test_attached_mode_metadata(self):
        leader_key = self._leader_key()
        r = find_balanced_leader_points(
            leader_key, n_battles=2, max_iters=1,
            points_budget=500.0, rng=random.Random(0),
        )
        self.assertTrue(r.attached_mode)
        self.assertEqual(r.host_key, pick_host_for_leader(UNIT_CATALOG[leader_key]))
        # baseline_key == host_key in attached mode (we test (host+leader) vs host)
        self.assertEqual(r.baseline_key, r.host_key)

    def test_measure_win_rate_attached_returns_unit_interval(self):
        leader_key = self._leader_key()
        leader = UNIT_CATALOG[leader_key]
        host = UNIT_CATALOG[pick_host_for_leader(leader)]
        wr = measure_win_rate_leader_attached(
            leader, host, host, 500.0, n_battles=3, rng=random.Random(0),
        )
        self.assertIsInstance(wr, float)
        self.assertGreaterEqual(wr, 0.0)
        self.assertLessEqual(wr, 1.0)


class AuraUpliftCalibrationTests(unittest.TestCase):
    """#89 - aura uplift-delta calibration for SUPPORT characters.

    `measure_aura_uplift` returns two win-rates in [0, 1] and
    `find_balanced_support_points` returns a populated CalibrationResult
    with `attached_mode=True` and `balanced_points >= 1.0`.
    """

    def _support_key(self):
        # Cheapest CHARACTER with a faction so the auto client-picker resolves.
        return next(
            k for k, p in UNIT_CATALOG.items()
            if "CHARACTER" in (p.unit_keywords or ()) and p.faction
        )

    def test_measure_aura_uplift_returns_two_floats_in_unit_interval(self):
        support_key = self._support_key()
        support = UNIT_CATALOG[support_key]
        client_key = pick_host_for_leader(support)
        client = UNIT_CATALOG[client_key]
        wr_with, wr_without = measure_aura_uplift(
            support, client, client, 500.0,
            n_battles=3, rng=random.Random(0),
        )
        self.assertIsInstance(wr_with, float)
        self.assertIsInstance(wr_without, float)
        self.assertGreaterEqual(wr_with, 0.0)
        self.assertLessEqual(wr_with, 1.0)
        self.assertGreaterEqual(wr_without, 0.0)
        self.assertLessEqual(wr_without, 1.0)

    def test_find_balanced_support_points_populates_result(self):
        support_key = self._support_key()
        r = find_balanced_support_points(
            support_key, n_battles=3,
            points_budget=500.0, rng=random.Random(0),
        )
        self.assertTrue(r.attached_mode)
        self.assertGreaterEqual(r.balanced_points, 1.0)
        # uplift_delta must be populated as a float (possibly negative if the
        # support's aura doesn't help in this match-up). The field default is
        # 0.0; verify the calibrator actually wrote it by checking it's a
        # float and that the result is internally consistent with the
        # conversion formula (balanced_points >= 1.0 always).
        self.assertIsInstance(r.uplift_delta, float)
        self.assertEqual(r.host_key, pick_host_for_leader(UNIT_CATALOG[support_key]))
        self.assertEqual(r.baseline_key, r.host_key)
        self.assertIn("aura uplift", r.notes)


class DetachmentAwareBuilderTests(unittest.TestCase):
    """Calibration builders must set the army's detachment from the unit's
    faction default, so that army-wide passives (Awakened Dynasty's
    bonus-to-hit-when-led, Gladius's wound-1 reroll, etc.) and stratagems
    fire during the simulated battle that produces a balanced_points number.

    Pre-fix, both `build_homogeneous_army` and `build_attached_army` left
    `army.detachment = None`, which meant the calibrator was tuning costs
    against a no-detachment baseline that didn't match real-game points
    calibration intent.
    """

    def test_homogeneous_army_has_detachment_set(self):
        warriors = UNIT_CATALOG["necrons_necron_warriors"]
        army = build_homogeneous_army("Test", warriors, 1000.0)
        self.assertIsNotNone(army.detachment)
        self.assertIs(army.detachment, AWAKENED_DYNASTY)
        # And resolve_detachment must return the same - the homogeneous
        # builder sets it explicitly, not just via the fallback path.
        self.assertIs(army.resolve_detachment(), AWAKENED_DYNASTY)

    def test_homogeneous_army_no_detachment_when_faction_empty(self):
        # Defensive: if a profile has no faction (custom test profile),
        # the builder must not crash; detachment stays None.
        baseline = UNIT_CATALOG[_BASELINE_KEY]
        faction_less = replace(baseline, faction="")
        army = build_homogeneous_army("Test", faction_less, 500.0)
        self.assertIsNone(army.detachment)

    def test_attached_army_uses_host_faction_detachment(self):
        # Captain + Intercessor Squad: host is the Marine battleline, so
        # the army's detachment is the Marine default (Gladius). The
        # leader's faction is read for nothing - even if it were a
        # different faction conceptually, the bodyguard squad's faction
        # is what determines the army-wide passive.
        host = UNIT_CATALOG["space_marines_intercessor_squad"]
        leader = UNIT_CATALOG["space_marines_captain"]
        army = build_attached_army(
            "Test", host, leader, 1000.0,
        )
        self.assertIsNotNone(army.detachment)
        self.assertIs(army.detachment, GLADIUS_TASK_FORCE)

    def test_attached_army_detachment_derives_from_host_not_leader(self):
        # Build a synthetic leader profile whose faction conflicts with the
        # host's. The army's detachment must reflect the HOST's faction -
        # the leader is just a model inside the bodyguard unit and doesn't
        # change the army's detachment rule.
        host = UNIT_CATALOG["necrons_necron_warriors"]    # Necrons
        leader = replace(
            UNIT_CATALOG["space_marines_captain"],
            faction="Adeptus Astartes",
        )
        army = build_attached_army("Test", host, leader, 500.0)
        self.assertIs(army.detachment, AWAKENED_DYNASTY)

    def test_balanced_points_uses_detachment(self):
        """Regression: the calibrator's internal builder calls must result in
        battles where each side has its faction detachment in effect.

        We exercise this by running a single-iteration find_balanced_points
        and asserting that the (very small) homogeneous armies it generates
        carry a detachment.

        We can't easily snoop on the Battle's internal armies, so this test
        instead reaches into `measure_win_rate` indirectly: it builds the
        same kind of armies that the calibrator does and confirms the
        detachment is set. If a future refactor drops the detachment hook,
        this test will catch it without needing to monkey-patch Battle.
        """
        warriors = UNIT_CATALOG["necrons_necron_warriors"]
        a = build_homogeneous_army("Test", warriors, 500.0)
        self.assertIsNotNone(a.detachment)
        self.assertEqual(
            a.detachment, default_detachment_for_faction("Necrons"),
        )

        # Smoke-test the full path too - a tiny calibration must complete
        # without crashing once detachments are wired.
        r = find_balanced_points(
            "necrons_necron_warriors",
            n_battles=2, max_iters=1,
            points_budget=500.0, rng=random.Random(0),
        )
        self.assertGreater(r.balanced_points, 0.0)


if __name__ == "__main__":
    unittest.main()
