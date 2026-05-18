"""Tests for the sim-driven equilibrium phase.

The module is a thin wrapper around the simulator: per ordered pair (i, j)
of measured units it runs ``Battle()`` n_battles times at equal points,
converts the observed win rate to a log-advantage via clamped logit, and
feeds that into the same row-mean closed form Phase 1 uses. The tests
here pin three properties so the wrapper does not regress:

  1. Anchor pinning — the chosen anchor's equilibrium points-per-model
     equals the requested anchor_per_model exactly. This is the load-
     bearing invariant of the solve (every other unit's price is relative
     to the anchor).
  2. Phase 1 fallback — units outside ``measured_keys`` carry their
     closed-form Phase 1 value verbatim with ``source="phase1_fallback"``.
     This keeps the snapshot a complete catalogue rather than a sparse
     overlay.
  3. Snapshot round-trip — ``save_snapshot`` + ``load_snapshot`` recover
     the same payload. Used by the Streamlit equilibrium tab to load the
     pre-built JSON without re-running the multi-hour sim.

Logit-clamp tested separately as a pure-math unit test so the snapshot
test doesn't have to rely on a degenerate-matchup fixture.
"""

from __future__ import annotations

import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from code.equilibrium_simdriven import (
    LOGIT_EPSILON,
    SimDrivenEntry,
    _logit_clamped,
    compute_phase_simdriven,
    load_snapshot,
    save_snapshot,
)
from code.units import UNIT_CATALOG


# A short, deterministic measured set: anchor + two same-role rivals.
# Three units = 3 ordered pairs at n_battles=2 = 6 battles; well under a
# second of wall-clock even on a slow box, so the test is safe in CI.
_TEST_MEASURED_KEYS = [
    "space_marines_intercessor_squad",
    "space_marines_hellblaster_squad",
    "necrons_necron_warriors",
]


def _all_present_in_catalog() -> bool:
    return all(k in UNIT_CATALOG for k in _TEST_MEASURED_KEYS)


class LogitClampTests(unittest.TestCase):
    """`_logit_clamped` must produce finite output across the full domain."""

    def test_logit_of_half_is_zero(self):
        self.assertAlmostEqual(_logit_clamped(0.5), 0.0)

    def test_logit_is_skew_symmetric(self):
        for p in (0.1, 0.25, 0.4, 0.7, 0.9):
            self.assertAlmostEqual(_logit_clamped(p), -_logit_clamped(1.0 - p))

    def test_extremes_are_clamped_not_infinite(self):
        finite_low = _logit_clamped(0.0)
        finite_hi = _logit_clamped(1.0)
        self.assertTrue(math.isfinite(finite_low))
        self.assertTrue(math.isfinite(finite_hi))
        # The clamp pulls both ends to ±log((1-eps)/eps); symmetric.
        self.assertAlmostEqual(finite_low, -finite_hi)
        # Bound: |logit_clamped(0)| = log((1-eps)/eps).
        bound = math.log((1.0 - LOGIT_EPSILON) / LOGIT_EPSILON)
        self.assertAlmostEqual(abs(finite_low), bound)


@unittest.skipUnless(
    _all_present_in_catalog(),
    "test fixture units missing from UNIT_CATALOG",
)
class SimDrivenIntegrationTests(unittest.TestCase):
    """End-to-end: compute_phase_simdriven + snapshot round-trip on 3 units."""

    @classmethod
    def setUpClass(cls):
        cls.rng = random.Random(11)
        cls.result = compute_phase_simdriven(
            catalog=UNIT_CATALOG,
            anchor_key=_TEST_MEASURED_KEYS[0],
            anchor_per_model=16.0,
            measured_keys=list(_TEST_MEASURED_KEYS),
            n_battles=2,
            points_budget=400.0,
            rng=cls.rng,
        )

    def test_anchor_pinned_to_requested_per_model_cost(self):
        anchor = next(
            e for e in self.result.entries
            if e.key == _TEST_MEASURED_KEYS[0]
        )
        self.assertEqual(anchor.source, "sim")
        self.assertAlmostEqual(
            anchor.equilibrium_points_per_model, 16.0, places=2,
            msg="anchor's per-model points must exactly equal anchor_per_model",
        )

    def test_measured_units_tagged_as_sim_source(self):
        measured_entries = [
            e for e in self.result.entries
            if e.key in _TEST_MEASURED_KEYS
        ]
        self.assertEqual(len(measured_entries), len(_TEST_MEASURED_KEYS))
        for e in measured_entries:
            self.assertEqual(e.source, "sim")
            self.assertGreater(
                e.valid_matchups, 0,
                msg=f"{e.key} got zero valid matchups — battles all degenerated?",
            )

    def test_unmeasured_units_inherit_phase1(self):
        """A catalogue unit NOT in measured_keys must appear in the result
        with source='phase1_fallback'."""
        fallbacks = [
            e for e in self.result.entries
            if e.source == "phase1_fallback"
        ]
        self.assertGreater(
            len(fallbacks), 50,
            msg="far fewer fallback entries than expected — Phase 1 inheritance broken?",
        )
        # Every fallback entry must still be a fittable unit, since Phase 1
        # itself excludes pure-melee + noncombat.
        for e in fallbacks[:20]:
            self.assertIn(e.role, ("shooty", "dual"))

    def test_snapshot_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            save_snapshot(self.result, path=path)
            payload = load_snapshot(path=path)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["phase"], "simdriven")
        self.assertEqual(payload["anchor_key"], _TEST_MEASURED_KEYS[0])
        self.assertEqual(payload["n_battles_per_pair"], 2)
        # Every entry in the result must survive the round trip with the
        # same key set.
        keys_before = {e.key for e in self.result.entries}
        keys_after = set(payload["units"].keys())
        self.assertEqual(keys_before, keys_after)
        # Anchor must keep its pinned cost across save/load.
        loaded_anchor = payload["units"][_TEST_MEASURED_KEYS[0]]
        self.assertAlmostEqual(
            loaded_anchor["equilibrium_points_per_model"], 16.0, places=2,
        )


class ConfigurationGuardTests(unittest.TestCase):
    """compute_phase_simdriven rejects degenerate inputs cleanly."""

    def test_anchor_not_in_measured_set_raises(self):
        # Picking a key that exists in the catalogue but is not in
        # measured_keys must raise — otherwise the anchor shift step would
        # silently anchor against a wrong-index entry.
        with self.assertRaises(ValueError) as cm:
            compute_phase_simdriven(
                anchor_key="space_marines_intercessor_squad",
                measured_keys=["necrons_necron_warriors"],
                n_battles=1,
                points_budget=300.0,
                rng=random.Random(0),
            )
        self.assertIn("anchor", str(cm.exception).lower())


if __name__ == "__main__":
    unittest.main()
