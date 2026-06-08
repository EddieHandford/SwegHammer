"""Visual board-state verification for the faithful-collision thrust.

Renders the SAME Imperial Knights vs Tyranids (hardest-walling horde) matchup
and seed at a late frame, once collision-OFF and once collision-ON
(SWEG_COLLISION + SWEG_PATHFIND + SWEG_OCCGRID, NO make-way), so the board
states can be compared side by side. The watchdog's directive: use the render
to classify the reach-degradation as faithful (Knight legitimately screened /
routing around; horde walls legally in coherency) vs buggy (units stuck
illegally, overlapping, oscillating).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_render_collision
"""
from __future__ import annotations

import os
import random
import sys

from code.army_builder import build_faction_random_army
from code.events import EventLog
from code.simulator import Battle
from code.renderer import render_frame, aggregate_activations
from scripts.evaluate_vs_meta import _pick_rotation_map

# Optional argv override: <A_FAC> <B_FAC> [SEED] — lets the same diagnostic render
# any matchup (e.g. the under-pole reach check: "Astra Militarum" "Aeldari").
A_FAC = sys.argv[1] if len(sys.argv) > 1 else "Imperial Knights"
B_FAC = sys.argv[2] if len(sys.argv) > 2 else "Tyranids"
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 3
_TAG = (A_FAC.split()[0] + "_v_" + B_FAC.split()[0]).lower()


def _capture(tag: str) -> None:
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(SEED), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(SEED + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(SEED)
    Battle(a, b, subscribers=[log], map_=map_).run()
    frames = aggregate_activations(log.events)
    if not frames:
        print(f"{tag}: no frames")
        return
    # Render a late frame (~80% through) where walling / contest has settled.
    fi = max(0, int(len(frames) * 0.8) - 1)
    img = render_frame(map_, log.events, frame=fi, frames=frames)
    out = f"data/_collision_{_TAG}_{tag}.png"
    img.save(out)
    print(f"{tag}: frames={len(frames)} rendered frame {fi} -> {out}")


def main() -> None:
    # OFF first (gates unset)
    for g in ("SWEG_COLLISION", "SWEG_PATHFIND", "SWEG_OCCGRID"):
        os.environ.pop(g, None)
    _capture("off")
    # ON (gates read live per move, so setting them now applies to this run)
    os.environ["SWEG_COLLISION"] = "1"
    os.environ["SWEG_PATHFIND"] = "1"
    os.environ["SWEG_OCCGRID"] = "1"
    _capture("on")


if __name__ == "__main__":
    main()
