"""Deeper wide digest: the same ring pairing, but N seeds per pairing.

`scripts/_detcheck_wide.py` runs 2 seeds per pairing — 44 battles — and its
digest is quoted across the documentation, so it is deliberately NOT changed.

That sample is fine for proving a change is byte-identical-OFF, which is what it
exists for. It is NOT fine for the opposite claim. The gate inertness sweep
(scripts/_gate_inertness_sweep.py) found 33 of 148 gates producing no change at
44 battles, and at least one of those — SWEG_CULL_PICK_AWARE — is demonstrably
real, having scored the best ordering gain of its session over 36,960 paired
games. Absence of evidence at 44 battles is not evidence of absence.

This harness raises the sample so a rare-firing gate has a chance to show. A
gate still flat at 10 seeds (220 battles) is a much stronger candidate for
STRUCTURALLY DEAD than one flat at 2.

Digests from this script are NOT comparable to the canonical ones — different
sample, different value. Compare deep-to-deep only.

Run: PYTHONHASHSEED=0 DETCHECK_SEEDS=10 python -m scripts._detcheck_deep
"""
from __future__ import annotations
import hashlib
import os
import random

from code.army_builder import build_faction_random_army
from code.events import EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import (FACTIONS, _pick_rotation_map,
                                      _pick_primary_mission)

SEEDS = int(os.environ.get("DETCHECK_SEEDS", "10"))


def main() -> None:
    h = hashlib.sha256()
    n = len(FACTIONS)
    for i, A in enumerate(FACTIONS):
        B = FACTIONS[(i + 1) % n]
        for seed in range(SEEDS):
            random.seed(seed)
            a = build_faction_random_army("A", A, 2000, rng=random.Random(seed),
                                          use_archetype=True)
            b = build_faction_random_army("B", B, 2000,
                                          rng=random.Random(seed + 9),
                                          use_archetype=True)
            lg = EventLog()
            Battle(a, b, subscribers=[lg], map_=_pick_rotation_map(seed),
                   primary_mission=_pick_primary_mission(seed)).run()
            h.update(repr([(type(e).__name__, getattr(e, "army_name", None),
                            getattr(e, "vp_awarded", None))
                           for e in lg.events]).encode())
    print(f"deep event-log digest ({n} factions, {SEEDS * n} battles):",
          h.hexdigest()[:24])


if __name__ == "__main__":
    main()
