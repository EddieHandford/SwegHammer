"""Matchup-scoping speed lever (evaluate_vs_meta --factions + paired_delta --scoped).

A localized single-faction change only moves that faction's row+column (42 of 462
cells); the rest is byte-identical to a saved full anchor. Scoping runs only the
touched cells and merges the unchanged ones from the anchor — a ~10x-fewer-battles
eval. These hermetic tests cover the scope predicate (identity at full scope, 42
cells per faction) and the anchor merge (unchanged cells must show 0 flips).
"""
from __future__ import annotations

import unittest

from scripts.evaluate_vs_meta import FACTIONS, _job_in_scope
from scripts.paired_delta import compute_paired


def _all_pairs(scope):
    return [(a, b) for a in FACTIONS for b in FACTIONS
            if a != b and _job_in_scope(a, b, scope)]


class JobInScopeTests(unittest.TestCase):
    def test_no_scope_runs_full_matrix(self):
        self.assertEqual(len(_all_pairs(None)), len(FACTIONS) * (len(FACTIONS) - 1))

    def test_full_scope_is_identity(self):
        # Scoping to every faction reproduces the full matrix (identity).
        self.assertEqual(_all_pairs(set(FACTIONS)), _all_pairs(None))

    def test_single_faction_is_row_plus_column(self):
        # One faction = its full row (21 as A) + full column (21 as B) = 42.
        pairs = _all_pairs({FACTIONS[2]})  # Aeldari
        self.assertEqual(len(pairs), 2 * (len(FACTIONS) - 1))
        # every pair touches the scoped faction
        self.assertTrue(all(FACTIONS[2] in (a, b) for a, b in pairs))

    def test_two_factions_share_their_crossing_cells(self):
        scope = {FACTIONS[2], FACTIONS[1]}
        pairs = set(_all_pairs(scope))
        # 2 * 42 minus the 2 shared crossing cells (A-vs-B and B-vs-A counted once each)
        self.assertEqual(len(pairs), 2 * 2 * (len(FACTIONS) - 1) - 2)


class ScopedMergeTests(unittest.TestCase):
    def _full(self, fac_awins):
        """Synthetic full log over 3 real factions, every ordered pair, n=10."""
        facs = FACTIONS[:3]
        g = {}
        for a in facs:
            for b in facs:
                if a == b:
                    continue
                aw = fac_awins.get((a, b), 5)
                for s in range(10):
                    g[(a, b, s)] = "A" if s < aw else "B"
        return g

    def test_merge_unchanged_cells_show_zero_flips(self):
        # Anchor (OFF) + a scoped ON that only changed the (f0, f1) cell.
        f0, f1 = FACTIONS[0], FACTIONS[1]
        anchor = self._full({})
        scoped_on = {k: v for k, v in self._full({(f0, f1): 9}).items()
                     if k[0] == f0 or k[1] == f0}  # only f0's row+column
        merged = {**anchor, **scoped_on}            # the --scoped merge
        self.assertEqual(len(merged), len(anchor))  # same coverage as the anchor
        w = {f: 1 for f in FACTIONS}
        tgt = {f: 50.0 for f in FACTIONS}
        nz = {f: 0.0 for f in FACTIONS}
        r = compute_paired(anchor, merged, w, tgt, nz)
        # f0 (the scoped faction) moved; f2 (untouched) is a literal anchor copy -> 0 flips.
        self.assertGreater(r["factions"][f0]["disc"], 0)
        self.assertEqual(r["factions"][FACTIONS[2]]["disc"], 0)


if __name__ == "__main__":
    unittest.main()
