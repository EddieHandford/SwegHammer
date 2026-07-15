"""Deterministic byte-identical harness: seeded battles -> event-log digest.
Run: PYTHONHASHSEED=0 python -m scripts._detcheck"""
import os, random, hashlib
from code.army_builder import build_faction_random_army
from code.events import EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

h = hashlib.sha256()
pairs = [("Death Guard", "Astra Militarum"), ("Aeldari", "Adeptus Astartes"),
         ("Orks", "T'au Empire")]
for A, B in pairs:
    for seed in range(4):
        random.seed(seed)
        a = build_faction_random_army("A", A, 2000, rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", B, 2000, rng=random.Random(seed + 9), use_archetype=True)
        lg = EventLog()
        Battle(a, b, subscribers=[lg], map_=_pick_rotation_map(seed),
               primary_mission=_pick_primary_mission(seed)).run()
        h.update(repr([(type(e).__name__, getattr(e, "army_name", None),
                        getattr(e, "vp_awarded", None)) for e in lg.events]).encode())
print("event-log digest:", h.hexdigest()[:24])
