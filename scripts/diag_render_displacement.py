"""Visual board-state diagnostic for the displacement-substrate review.

Renders THREE frames (early ~30%, mid ~60%, late ~85%) of one battle per
displacement-relevant matchup, at current production defaults (no gate
changes), so the eye can check the behaviours the displacement plan targets:

- Does a durable holder (Imperial Knight) park on a marker unopposed?
- Do body armies mass onto / contest enemy-held markers (tarpit) or hang back?
- Where do the under-pole armies (Astra Militarum, Chaos Space Marines) sit
  relative to markers while they shoot?

Also prints the last objective-scoring events per battle so the visual pairs
with the victory-point arithmetic.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_render_displacement
"""
from __future__ import annotations

import random
import sys

from code.army_builder import build_faction_random_army
from code.events import EventLog
from code.simulator import Battle
from code.renderer import render_frame, aggregate_activations
from scripts.evaluate_vs_meta import _pick_rotation_map

# (A faction, B faction, seed) — displacement-relevant matchups.
MATCHUPS = [
    ("Imperial Knights", "Astra Militarum", 3),
    ("Imperial Knights", "Tyranids", 3),
    ("Chaos Space Marines", "Adeptus Astartes", 5),
    ("Adeptus Mechanicus", "Orks", 7),
]

FRAME_POINTS = (0.30, 0.60, 0.85)


def _capture(a_fac: str, b_fac: str, seed: int) -> None:
    tag = (a_fac.split()[0] + "_v_" + b_fac.split()[0]).lower()
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    Battle(a, b, subscribers=[log], map_=map_).run()
    frames = aggregate_activations(log.events)
    if not frames:
        print(f"{tag}: no frames")
        return
    for pt in FRAME_POINTS:
        fi = max(0, int(len(frames) * pt) - 1)
        img = render_frame(map_, log.events, frame=fi, frames=frames)
        out = f"data/_displace_{tag}_f{int(pt * 100)}.png"
        img.save(out)
        print(f"{tag}: frame {fi}/{len(frames)} ({int(pt * 100)}%) -> {out}")
    # Tail of the objective-scoring story: last 8 scoring/contest summaries.
    score_lines = [
        e for e in log.events
        if type(e).__name__ in ("ObjectiveScored", "ObjectiveContested")
    ]
    print(f"{tag}: last objective events:")
    for e in score_lines[-8:]:
        name = getattr(e, "objective_name", "?")
        a_oc = getattr(e, "a_oc", "?")
        b_oc = getattr(e, "b_oc", "?")
        vp = getattr(e, "vp_awarded", None)
        who = getattr(e, "army_name", None)
        if vp is None:
            print(f"  {name}: contested OC {a_oc}/{b_oc}")
        else:
            print(f"  {name}: {who} +{vp} VP (OC {a_oc}/{b_oc})")


def main() -> None:
    for a_fac, b_fac, seed in MATCHUPS:
        _capture(a_fac, b_fac, seed)


if __name__ == "__main__":
    main()
