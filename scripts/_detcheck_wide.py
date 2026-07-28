"""Wide byte-identical harness: EVERY faction, seeded battles -> event-log digest.

`scripts/_detcheck.py` runs three pairings — Death Guard/Astra Militarum,
Aeldari/Adeptus Astartes, Orks/T'au Empire — so its digest covers SIX factions of
twenty-two. Any gate whose effect is confined to the other sixteen produces an
identical digest whether it is on or off, and "byte-identical verified" against
that digest is then vacuous.

That is not hypothetical: `SWEG_TYRANID_LIST_SOURCED` was recorded as
byte-identical-off on the strength of the canonical digest, which cannot see a
Tyranid-only change at all. This harness exists so a faction-scoped gate can be
verified against a digest that actually exercises it.

The canonical digest is deliberately NOT changed — it is referenced across the
documentation and every prior wave's verification. This is a SECOND, independent
digest covering all twenty-two factions, to be quoted alongside it.

Run: PYTHONHASHSEED=0 python -m scripts._detcheck_wide
"""
from __future__ import annotations
import hashlib
import random

from code.army_builder import build_faction_random_army
from code.events import EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import (FACTIONS, _pick_rotation_map,
                                      _pick_primary_mission)


def main() -> None:
    h = hashlib.sha256()
    # Ring pairing: every faction appears exactly twice, once per side, so a
    # change confined to any single faction moves the digest.
    n = len(FACTIONS)
    for i, A in enumerate(FACTIONS):
        B = FACTIONS[(i + 1) % n]
        for seed in range(2):
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
    print(f"wide event-log digest ({n} factions, {2*n} battles):",
          h.hexdigest()[:24])


if __name__ == "__main__":
    main()
