"""End-to-end smoke for every supported faction (#81).

The catalogue now spans ~1300 units across 30+ factions. Marines and Necrons
get loving care; T'au, Drukhari, Death Guard, Genestealer Cults, Adepta
Sororitas et al. get tested ad-hoc at best. This module asserts that every
faction listed in `code.factions.FACTION_COLOURS` can:

  1. Build a random army via `build_faction_random_army` from its own pool.
  2. Run a `Battle` against a generic Adeptus Astartes "control" army.
  3. Finish within MAX_ROUNDS (==5).
  4. Emit a non-empty event stream.

Skipped (counts as pass) when the catalogue has zero units for the faction
— some codex subsets are empty after BSData regenerations (Ynnari, Adeptus
Titanicus, Chaos Titans at time of writing; Drukhari was empty before #150
re-wired the BSData mapper to credit cross-library imports to the importing
codex rather than the defining library file).

Speed: 500-pt budgets, seed=42 throughout. Whole suite adds <5s.
"""

from __future__ import annotations

import random
import unittest
from collections import Counter

from code.army_builder import build_faction_random_army
from code.events import EventLog
from code.factions import FACTION_COLOURS
from code.simulator import MAX_ROUNDS, Battle
from code.units import UNIT_CATALOG


# Budget kept small for speed. 500 pts is enough to deploy ~5-15 units per
# side, which exercises movement, shooting, melee, deployment, and end-of-
# battle scoring without dragging the test suite.
POINTS_BUDGET = 500.0
SEED = 42

# The "control" army every faction is tested against. Astartes are chosen
# because they have the deepest catalogue coverage and are the implicit
# baseline elsewhere in the codebase (Intercessor Squad is the default
# balancer baseline).
CONTROL_FACTION = "Adeptus Astartes"


def _faction_unit_count() -> Counter:
    """Count UnitProfiles per faction tag once, reused across tests."""
    return Counter(p.faction for p in UNIT_CATALOG.values())


# Module-level cache so each parametric test doesn't re-scan the catalogue.
_FACTION_COUNTS = _faction_unit_count()


class FactionSmokeTests(unittest.TestCase):
    """One method per faction would be unwieldy; we generate subtests instead.

    Using `subTest` keeps the failure output legible — a crash in T'au won't
    short-circuit the Necron / GSC / Sororitas legs of the sweep, so we get
    a full per-faction report from a single test run.
    """

    def _run_one(self, faction: str) -> None:
        # Skip empty factions (Drukhari etc. may have zero units post-BSData
        # regen). Skipping counts as a pass for the suite as a whole.
        if _FACTION_COUNTS.get(faction, 0) == 0:
            self.skipTest(f"No units catalogued for faction {faction!r}")

        # Two independent seeded RNGs so the two armies don't share state
        # but both runs are deterministic.
        rng_a = random.Random(SEED)
        rng_b = random.Random(SEED + 1)

        a = build_faction_random_army(
            name=faction,
            faction=faction,
            points_budget=POINTS_BUDGET,
            rng=rng_a,
        )
        b = build_faction_random_army(
            name=CONTROL_FACTION,
            faction=CONTROL_FACTION,
            points_budget=POINTS_BUDGET,
            rng=rng_b,
        )

        # Some faction pools may price-out at 500 pts (every unit too
        # expensive for the cap). Treat empty armies as a skip — the
        # builder isn't broken, the pool is just too sparse to fill.
        if a.unit_count == 0:
            self.skipTest(f"Faction {faction!r} pool can't fill {POINTS_BUDGET}-pt budget")
        self.assertGreater(
            b.unit_count, 0,
            f"Control {CONTROL_FACTION!r} army should always fill the budget",
        )

        # Seed module RNG too — the simulator pulls from `random` directly
        # for some sub-systems (deployment jitter, attack rolls).
        random.seed(SEED)

        log = EventLog()
        battle = Battle(a, b, subscribers=[log])
        result = battle.run()

        # 1) Winner is one of the two army names or a draw.
        self.assertIn(
            result.winner_label(),
            {a.name, b.name, "Draw"},
            f"{faction}: unexpected winner {result.winner_label()!r}",
        )

        # 2) Battle ran at least one round and never overshot the cap.
        self.assertGreater(
            result.rounds, 0,
            f"{faction}: battle reported zero rounds played",
        )
        self.assertLessEqual(
            result.rounds, MAX_ROUNDS,
            f"{faction}: rounds={result.rounds} exceeds MAX_ROUNDS={MAX_ROUNDS}",
        )

        # 3) Event stream is non-empty (BattleStarted + at least one
        # round-bracket pair would already exceed 3, but we only need >0).
        self.assertGreater(
            len(log), 0,
            f"{faction}: event log is empty",
        )

    def test_every_faction_finishes_a_battle(self):
        # Iterate in dict order so failures bisect predictably.
        for faction in FACTION_COLOURS:
            if not faction:
                continue  # the "" fallback entry is not a real faction
            with self.subTest(faction=faction):
                self._run_one(faction)


if __name__ == "__main__":
    unittest.main()
