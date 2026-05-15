"""Tests for Phase 5 — meta-weighted equilibrium solve.

Phase 5 reweights the row-mean LSQ residuals by the *defender's* faction meta
share. The intuition: a unit's fair points should reflect how often it actually
faces each opponent on the table. A Custodes unit that crushes Tyranid hordes
(8% of the meta) and gets crushed by T'au gunlines (7%) should be priced for
*that* matchup distribution, not for a synthetic uniform meta.

What we check:
  * Phase 5 runs end-to-end on the live catalogue in <15s and returns a
    Phase5Result whose inner result carries phase=5.
  * Two synthetic units with identical D rows price *higher* when one is in a
    high-meta-share faction — the weighted row-mean shifts price toward the
    common matchups.
  * The Phase 4 -> Phase 5 movement is bounded: at least 80% of units stay
    within [0.5x, 2.0x] of their Phase 4 price (no catastrophic redistribution
    from a single reweighting pass).
  * The meta-share table is the one consumed by `scripts.evaluate_vs_meta` —
    same FACTIONS list, same May 2026 warpfriends source — so the test fails
    loudly if anyone ever decouples the two without thinking it through.
"""

from __future__ import annotations

import ast
import pathlib
import time
import unittest

from code.equilibrium import (
    DEFAULT_ANCHOR_KEY,
    META_FACTION_SHARE,
    compute_phase4,
    compute_phase5,
)
from code.units import UnitProfile


def _load_evaluate_vs_meta_factions():
    """Read the FACTIONS list out of `scripts/evaluate_vs_meta.py` via the AST.

    We can't `import scripts.evaluate_vs_meta` directly because its module-level
    `os.execvpe` re-exec (it pins PYTHONHASHSEED=0 for reproducibility) trips
    when run inside the unittest harness — it tries to re-launch the test as
    `evaluate_vs_meta.py` and fails. Reading the AST gives us the same data
    without executing the module. Same source file, same FACTIONS list — the
    point of this loader is exactly to prove that linkage.
    """
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    src = (repo_root / "scripts" / "evaluate_vs_meta.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        # Handle both `FACTIONS = [...]` (Assign) and `FACTIONS: List[str] = [...]`
        # (AnnAssign) — the latter is the actual form in the file today.
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "FACTIONS":
                    return [
                        elt.value for elt in node.value.elts
                        if isinstance(elt, ast.Constant)
                    ]
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "FACTIONS"
                and node.value is not None
                and isinstance(node.value, ast.List)
            ):
                return [
                    elt.value for elt in node.value.elts
                    if isinstance(elt, ast.Constant)
                ]
    raise AssertionError(
        "FACTIONS not found in scripts/evaluate_vs_meta.py — meta source has "
        "moved; update test_equilibrium_phase5._load_evaluate_vs_meta_factions"
    )


META_FACTIONS = _load_evaluate_vs_meta_factions()


# Single live-catalogue Phase 5 run shared across tests — full pipeline is
# ~5-10s; running it once keeps the suite quick.
_PHASE5_LIVE = None


def _get_phase5_live():
    global _PHASE5_LIVE
    if _PHASE5_LIVE is None:
        _PHASE5_LIVE = compute_phase5()
    return _PHASE5_LIVE


def _simple_shooty(**overrides) -> UnitProfile:
    """Minimal shooty UnitProfile for synthetic-catalogue tests."""
    defaults = dict(
        name="Synth",
        health=1.0,
        damage=1.0,
        hit_probability=2 / 3,
        attacks=2,
        range_inches=24,
        save=4,
        strength=4,
        toughness=4,
        move=6.0,
        oc=1,
        points_per_squad=10.0,
        min_models=1,
    )
    defaults.update(overrides)
    return UnitProfile(**defaults)


class Phase5EndToEndTests(unittest.TestCase):
    """Phase 5 on the live catalogue: shape, runtime, plumbing."""

    def test_phase5_runs_endtoend(self):
        start = time.perf_counter()
        bundle = compute_phase5()
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 15.0,
            f"Phase 5 took {elapsed:.2f}s on {len(bundle.result.keys)} units, "
            f"budget 15s",
        )
        self.assertEqual(bundle.result.phase, 5)
        self.assertGreater(len(bundle.result.entries), 0)
        # Every unit must have a positive equilibrium price.
        for e in bundle.result.entries:
            self.assertGreater(
                e.equilibrium_points_per_model, 0.0,
                f"Phase 5 must produce positive cost for {e.key}",
            )
        # Comparison records must align with the result entries.
        self.assertEqual(len(bundle.comparison), len(bundle.result.entries))
        # Anchor must remain pinned to its configured price.
        anchor_entry = next(
            e for e in bundle.result.entries if e.key == DEFAULT_ANCHOR_KEY
        )
        self.assertAlmostEqual(
            anchor_entry.equilibrium_points_per_model,
            bundle.result.anchor_per_model,
            places=2,
        )

    def test_phase5_keeps_phase4_overall_scale(self):
        # The meta-weighting should reshape the price *distribution* but not
        # blow it up: at least 80% of units must stay within [0.5x, 2.0x] of
        # their Phase 4 price. This is a "no catastrophic redistribution"
        # guard — if a future change rebalances things so dramatically that
        # half the catalogue swings outside this band, the test fails and we
        # take a hard look at why.
        bundle = _get_phase5_live()
        in_band = 0
        total = 0
        for c in bundle.comparison:
            if c.phase4_per_model <= 0:
                continue
            total += 1
            ratio = c.phase5_per_model / c.phase4_per_model
            if 0.5 <= ratio <= 2.0:
                in_band += 1
        self.assertGreater(total, 100, "expected lots of priceable units")
        in_band_pct = in_band / total
        self.assertGreaterEqual(
            in_band_pct, 0.80,
            f"Phase 4 -> Phase 5 movement must stay within [0.5x, 2.0x] for "
            f"at least 80% of units; got {in_band_pct:.1%} ({in_band}/{total})",
        )

    def test_meta_weight_uses_real_data(self):
        # The meta-share table must reference the same faction list that
        # `scripts.evaluate_vs_meta` uses — both are sourced from the same
        # May 2026 warpfriends weekly aggregate. If anyone replaces one
        # without the other, this test fails loudly.
        # 1. The constant exists and is non-empty.
        self.assertGreater(len(META_FACTION_SHARE), 0,
                           "META_FACTION_SHARE must be populated")
        # 2. Every faction in the share table is also in the evaluate_vs_meta
        #    FACTIONS list (same source, same names).
        meta_set = set(META_FACTIONS)
        for fac in META_FACTION_SHARE:
            self.assertIn(
                fac, meta_set,
                f"META_FACTION_SHARE key {fac!r} not in "
                f"scripts.evaluate_vs_meta.FACTIONS — sources have drifted",
            )
        # 3. Shares are non-negative and the top-10 total stays under 1.0
        #    (the residual is distributed across catalogue-only factions).
        for fac, share in META_FACTION_SHARE.items():
            self.assertGreaterEqual(share, 0.0, f"negative share for {fac}")
        self.assertLess(
            sum(META_FACTION_SHARE.values()), 1.0 + 1e-9,
            "Top-10 meta shares must sum to <= 1.0",
        )
        # 4. The bundle reports the table it actually used, and it matches
        #    the module constant by default.
        bundle = _get_phase5_live()
        self.assertEqual(bundle.share_table, dict(META_FACTION_SHARE))


class Phase5MetaWeightingShapeTests(unittest.TestCase):
    """Synthetic-catalogue checks: high-meta-share factions price up."""

    def test_unit_in_common_faction_weighted_more(self):
        # Two synthetic units with identical stats — one in a high-meta-share
        # faction, one in a low-meta-share faction — must produce different
        # Phase 5 prices, with the high-share one pricing higher (its row in
        # R[i, j] is weighted more heavily when others' row-means look at it).
        #
        # Construction: pick two real factions with very different shares so
        # the test exercises the actual META_FACTION_SHARE table. We use the
        # anchor's faction (Adeptus Astartes, share 0.13) and a low-share
        # faction (Leagues of Votann, share 0.03).
        anchor = _simple_shooty(
            name="Anchor",
            faction="Adeptus Astartes",
            points_per_squad=16.0,
            min_models=1,
        )
        # Three damage-dealing peers so the matrix has finite entries:
        #   - one in the high-share faction (matches anchor faction)
        #   - one in the low-share faction
        #   - one in a third (unrelated) faction so neither test unit is
        #     identical to the anchor profile in faction membership.
        common = _simple_shooty(
            name="CommonFactionUnit",
            faction="Necrons",          # share 0.11 — high
            points_per_squad=10.0,
            min_models=1,
        )
        rare = _simple_shooty(
            name="RareFactionUnit",
            faction="Leagues of Votann",   # share 0.03 — low
            points_per_squad=10.0,
            min_models=1,
        )
        # A neutral foil unit so the row-means have content beyond the anchor
        # alone. Its faction is in the share table at moderate weight.
        foil = _simple_shooty(
            name="Foil",
            faction="Tyranids",     # share 0.08
            points_per_squad=10.0,
            min_models=1,
        )

        # Critical: in this synthetic catalogue, the anchor must be present
        # by key, and the test units must have identical D rows. They share
        # the exact same stat block, so their D[i, :] rows match — the only
        # difference is which faction they're in, which is what Phase 5's
        # column-weight reshapes.
        synthetic = {
            "anchor_unit": anchor,
            "common_unit": common,
            "rare_unit": rare,
            "foil_unit": foil,
        }
        bundle = compute_phase5(
            catalog=synthetic,
            anchor_key="anchor_unit",
            anchor_per_model=16.0,
        )
        by_key = {e.key: e for e in bundle.result.entries}
        # The high-meta-share unit must price strictly higher than the
        # low-meta-share unit, even though their stats are identical.
        self.assertGreater(
            by_key["common_unit"].equilibrium_points_per_model,
            by_key["rare_unit"].equilibrium_points_per_model,
            "high-meta-share faction must price higher than identical-stat "
            "low-meta-share faction under Phase 5",
        )


class Phase5VsPhase4Tests(unittest.TestCase):
    """Phase 5 is built on top of Phase 4; sanity-check the composition."""

    def test_phase5_anchor_matches_phase4_anchor(self):
        # Both phases must keep the anchor pinned at the same configured
        # per-model price (the weighted shift inside Phase 5 preserves the
        # anchor by construction).
        bundle5 = _get_phase5_live()
        result4 = compute_phase4()
        a4 = next(e for e in result4.entries if e.key == DEFAULT_ANCHOR_KEY)
        a5 = next(e for e in bundle5.result.entries if e.key == DEFAULT_ANCHOR_KEY)
        self.assertAlmostEqual(
            a4.equilibrium_points_per_model,
            a5.equilibrium_points_per_model,
            places=2,
        )


if __name__ == "__main__":
    unittest.main()
