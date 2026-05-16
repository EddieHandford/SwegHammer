"""Tests for the Phase 4 tactical-utility overlay on the equilibrium solver.

Phase 4 sits on top of Phase 2: the combat matrix is unchanged, but each unit's
log-points are bumped by `log(1 + tactical_value(u)) - log(1 + tactical_value(anchor))`.
The anchor stays pinned, every other unit moves multiplicatively.

What we check:
  * `tactical_value` is a pure function of profile fields with the documented
    shape — log-clamped on Move/range, linear on OC/scout, flat on booleans.
  * The anchor's tactical baseline is what gets subtracted out, so the anchor
    sees no movement vs Phase 2.
  * Move and deep_strike are positive utility (verified with non-default
    weights — the calibrated defaults zero them out because the held-out
    anchor set can't identify those weights, but the function shape itself
    should be monotonic when the weight is positive).
  * End-to-end Phase 4 runs over the full catalogue in <10s and produces a
    phase=4 result.
  * Among shooty units with no special abilities (deep strike, scout, etc.),
    the Phase 4 ranking should track the Phase 2 ranking — the utility term
    shouldn't reshape the ordering when there's no utility to apply.
"""

from __future__ import annotations

import math
import time
import unittest
from dataclasses import replace

from code.equilibrium import (
    DEFAULT_ANCHOR_KEY,
    TacticalWeights,
    compute_phase2,
    compute_phase4,
    tactical_value,
)
from code.units import UNIT_CATALOG, UnitProfile


# Module-level Phase 2 / Phase 4 solves shared across tests — the live catalogue
# is ~1300 units, single solve is ~3-5s, doing it once keeps test time tight.
_PHASE2 = None
_PHASE4 = None


def _get_phase2():
    global _PHASE2
    if _PHASE2 is None:
        _PHASE2 = compute_phase2()
    return _PHASE2


def _get_phase4():
    global _PHASE4
    if _PHASE4 is None:
        _PHASE4 = compute_phase4()
    return _PHASE4


def _simple_shooty(**overrides) -> UnitProfile:
    """Minimal shooty profile for tactical_value shape tests."""
    defaults = dict(
        name="Shooty",
        health=1.0,
        damage=1.0,
        hit_probability=2 / 3,
        attacks=1,
        range_inches=12,
        save=4,
        strength=4,
        toughness=4,
        move=6.0,
        oc=1,
    )
    defaults.update(overrides)
    return UnitProfile(**defaults)


class TacticalValueShapeTests(unittest.TestCase):
    """`tactical_value` is a function of profile fields with documented shape."""

    def test_tactical_value_zero_at_anchor_baseline(self):
        # An Intercessor-shaped profile (M=6, OC=2, range=12, no abilities)
        # gets tactical_value() = w_oc * 1 (OC excess of 1 over baseline 1).
        # With the calibrated default w_oc=0, that's exactly zero. With a
        # non-zero w_oc, it's the OC weight itself.
        anchor_like = _simple_shooty(move=6.0, oc=2, range_inches=12)
        # Default weights -> tactical_value is just w_oc * (oc-1) under the
        # log-clamped Move/range shape.
        defaults = TacticalWeights()
        self.assertAlmostEqual(
            tactical_value(anchor_like, defaults),
            defaults.w_oc * 1.0,
            places=6,
        )
        # With everything zeroed, it's exactly zero.
        zero = TacticalWeights(
            w_move=0, w_oc=0, w_range=0, w_deep_strike=0,
            w_scout=0, w_infiltrator=0, w_sticky_objective=0,
        )
        self.assertEqual(tactical_value(anchor_like, zero), 0.0)

    def test_phase4_anchor_pinned_to_phase2(self):
        # The phase4 transform shifts every unit's log_p by
        # log(1+t(u)) - log(1+t(anchor)); the anchor row is exactly 0 by
        # construction, so the anchor's equilibrium per-model price must
        # equal Phase 2 (which itself equals the configured anchor price).
        r4 = _get_phase4()
        anchor = next(e for e in r4.entries if e.key == DEFAULT_ANCHOR_KEY)
        self.assertAlmostEqual(
            anchor.equilibrium_points_per_model, r4.anchor_per_model,
            places=2,
        )

    def test_tactical_value_monotonic_in_move(self):
        # Function shape: with a positive w_move, a 12" Move profile must
        # have higher tactical_value than a 6" profile holding everything
        # else equal. (Default w_move is 0 by calibration; pass a non-zero
        # weight to test the shape itself.)
        weights = TacticalWeights(
            w_move=0.05, w_oc=0, w_range=0, w_deep_strike=0,
            w_scout=0, w_infiltrator=0, w_sticky_objective=0,
        )
        slow = _simple_shooty(move=6.0)
        fast = _simple_shooty(move=12.0)
        very_fast = _simple_shooty(move=14.0)
        self.assertGreater(
            tactical_value(fast, weights), tactical_value(slow, weights),
        )
        self.assertGreater(
            tactical_value(very_fast, weights), tactical_value(fast, weights),
        )
        # Below-baseline move clamps to 0 — a 4" unit doesn't get a penalty.
        slow_too = _simple_shooty(move=4.0)
        self.assertEqual(tactical_value(slow_too, weights), 0.0)
        # And the exact value at M=12: log(12/6) = log(2) ~= 0.693.
        self.assertAlmostEqual(
            tactical_value(fast, weights),
            0.05 * math.log(2.0),
            places=6,
        )

    def test_deep_strike_bonus_present(self):
        # Holding everything else equal, a deep-strike profile must price
        # higher than a non-deep-strike profile under a positive w_deep_strike.
        # Use a non-zero w_deep_strike — the calibrated default is 0 because
        # Custodes (the only DS anchor) is already overcosted by Phase 2.
        weights = TacticalWeights(
            w_move=0, w_oc=0, w_range=0, w_deep_strike=0.15,
            w_scout=0, w_infiltrator=0, w_sticky_objective=0,
        )
        regular = _simple_shooty(deep_strike=False)
        deepstrike = _simple_shooty(deep_strike=True)
        self.assertGreater(
            tactical_value(deepstrike, weights),
            tactical_value(regular, weights),
        )
        # And the exact bonus is exactly the weight.
        self.assertAlmostEqual(
            tactical_value(deepstrike, weights) - tactical_value(regular, weights),
            0.15,
            places=6,
        )

    def test_range_log_clamped_at_baseline(self):
        # range <= 12 -> 0; range = 24 -> log(2).
        weights = TacticalWeights(
            w_move=0, w_oc=0, w_range=0.10, w_deep_strike=0,
            w_scout=0, w_infiltrator=0, w_sticky_objective=0,
        )
        short = _simple_shooty(range_inches=12)
        long_ = _simple_shooty(range_inches=24)
        self.assertEqual(tactical_value(short, weights), 0.0)
        self.assertAlmostEqual(
            tactical_value(long_, weights),
            0.10 * math.log(2.0),
            places=6,
        )

    def test_oc_excess_is_linear(self):
        weights = TacticalWeights(
            w_move=0, w_oc=0.05, w_range=0, w_deep_strike=0,
            w_scout=0, w_infiltrator=0, w_sticky_objective=0,
        )
        oc1 = _simple_shooty(oc=1)
        oc3 = _simple_shooty(oc=3)
        self.assertEqual(tactical_value(oc1, weights), 0.0)
        self.assertAlmostEqual(
            tactical_value(oc3, weights), 0.10, places=6,
        )

    def test_synthetic_unit_with_deep_strike_prices_higher(self):
        # Brief's requirement at the equilibrium-solve level: two identical
        # profiles, one with deep_strike=True, the DS one must end up with a
        # higher Phase 4 per-model equilibrium price.
        weights = TacticalWeights(
            w_move=0, w_oc=0, w_range=0, w_deep_strike=0.15,
            w_scout=0, w_infiltrator=0, w_sticky_objective=0,
        )
        # Synthetic catalogue: an anchor (Intercessor-like) plus two clones,
        # one with deep_strike. Both clones must be solvable by Phase 2 -> need
        # a damage-dealing profile.
        anchor = _simple_shooty(name="Anchor", oc=2, range_inches=12,
                                points_per_squad=16.0, min_models=1)
        regular = _simple_shooty(name="Regular", deep_strike=False,
                                 points_per_squad=10.0, min_models=1)
        deepstrike = _simple_shooty(name="DSed", deep_strike=True,
                                    points_per_squad=10.0, min_models=1)
        synthetic = {
            "anchor_unit": anchor,
            "regular_unit": regular,
            "deepstrike_unit": deepstrike,
        }
        result = compute_phase4(
            catalog=synthetic,
            anchor_key="anchor_unit",
            anchor_per_model=16.0,
            weights=weights,
        )
        by_k = {e.key: e for e in result.entries}
        self.assertGreater(
            by_k["deepstrike_unit"].equilibrium_points_per_model,
            by_k["regular_unit"].equilibrium_points_per_model,
            "deep_strike=True must price higher under positive w_deep_strike",
        )


class Phase4EndToEndTests(unittest.TestCase):
    """Phase 4 over the live catalogue: shape, runtime, plumbing."""

    def test_phase4_runs_endtoend(self):
        start = time.perf_counter()
        result = compute_phase4()
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 10.0,
            f"Phase 4 took {elapsed:.2f}s on {len(result.keys)} units, budget 10s",
        )
        self.assertEqual(result.phase, 4)
        self.assertGreater(len(result.entries), 0)
        for e in result.entries:
            self.assertGreater(
                e.equilibrium_points_per_model, 0.0,
                f"Phase 4 must produce positive cost for {e.key}",
            )

    def test_phase4_keeps_phase2_ranking_within_role(self):
        # Among shooty units that have NONE of the tactical-utility traits
        # (no DS, scout, infiltrator, sticky, OC<=1, M<=6, range<=12), the
        # Phase 4 multiplicative shift is exactly 1 / (1 + t(anchor)). All
        # those units shift together by the same factor, so the ranking
        # must be preserved.
        r2 = _get_phase2()
        r4 = _get_phase4()
        by_k2 = {e.key: e for e in r2.entries}
        by_k4 = {e.key: e for e in r4.entries}

        def _is_vanilla(u: UnitProfile) -> bool:
            return (
                not u.deep_strike and not u.infiltrator
                and not u.sticky_objective and u.scout_distance == 0
                and u.oc <= 1 and u.move <= 6.0 and u.range_inches <= 12
                and u.attacks > 0 and u.range_inches > 0
            )

        vanilla_keys = [k for k in by_k2
                        if k in by_k4 and _is_vanilla(UNIT_CATALOG[k])]
        # Need at least a handful to make the rank-correlation meaningful.
        self.assertGreater(
            len(vanilla_keys), 20,
            "expected a healthy number of vanilla shooty units in the catalogue",
        )

        # All vanilla units must shift by the same factor (1 / (1 + t(anchor))).
        # Specifically: ratio eq_phase4 / eq_phase2 should be identical
        # (within float tolerance) across the whole vanilla set.
        # NOTE: the EquilibriumEntry public surface rounds prices to 2 decimals,
        # which is too coarse for this invariant when the shared shift factor
        # is non-unity (e.g. when the anchor's tactical_value > 0 because its
        # range_inches > 12). Use the unrounded log_p arrays directly.
        log_p2 = {k: lp for k, lp in zip(r2.keys, r2.log_p)}
        log_p4 = {k: lp for k, lp in zip(r4.keys, r4.log_p)}
        diffs = [log_p4[k] - log_p2[k] for k in vanilla_keys]
        spread = max(diffs) - min(diffs)
        self.assertLess(
            spread, 1e-6,
            f"vanilla units should all shift by the same log-factor; "
            f"spread={spread:.6g}",
        )

        # And as a stronger sanity check: the rank order is exactly preserved.
        order_2 = sorted(vanilla_keys, key=lambda k: log_p2[k])
        order_4 = sorted(vanilla_keys, key=lambda k: log_p4[k])
        self.assertEqual(order_2, order_4)


if __name__ == "__main__":
    unittest.main()
