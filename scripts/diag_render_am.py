"""Visual board-state diagnostic for the Astra Militarum under-pole: render the
end-of-each-round board for several Astra Militarum games (with the rebuilt body
count + Recon Element cover ON = the real competitive army) so the eye can find
what aggregate metrics miss — bodies clumping, getting charged off markers, dying
in the open, sitting away from objectives, etc.

Gates SWEG_AM_REALISM + SWEG_AM_RECON are forced ON (set in the hash-seed re-exec).

Run:  PYTHONHASHSEED=0 python -m scripts.diag_render_am
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["SWEG_AM_REALISM"] = "1"
    os.environ["SWEG_AM_RECON"] = "1"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_render_am"], os.environ)

import random

from code.army_builder import build_faction_random_army
from code.events import EventLog, RoundStarted, ObjectiveScored
from code.simulator import Battle
from code.renderer import aggregate_activations, render_frame
from scripts.evaluate_vs_meta import _pick_rotation_map

# Astra Militarum (army A) vs the matchups that expose the under-pole: a melee
# over-pole (World Eaters), a durable grind (Death Guard), and the horde mirror
# (Orks). Seed 0 each.
MATCHUPS = [
    ("Astra Militarum", "World Eaters", 0),
    ("Astra Militarum", "Death Guard", 0),
    ("Astra Militarum", "Orks", 0),
]


def _rounds_by_index(events):
    out = [0] * len(events)
    r = 0
    for i, ev in enumerate(events):
        if isinstance(ev, RoundStarted):
            r = ev.round_num
        out[i] = r
    return out


def _capture(a_fac: str, b_fac: str, seed: int) -> None:
    tag = (a_fac.split()[0] + "_v_" + b_fac.split()[1]).lower()
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    a_models, b_models = len(a.units), len(b.units)
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    Battle(a, b, subscribers=[log], map_=map_).run()
    events = log.events
    frames = aggregate_activations(events)
    rbi = _rounds_by_index(events)
    last_frame_by_round: dict = {}
    for fi, (_s, e) in enumerate(frames):
        rnd = rbi[e]
        if rnd >= 1:
            last_frame_by_round[rnd] = fi
    print(f"\n### {tag}  (A={a_fac} {a_models} models  vs  B={b_fac} {b_models} models)")
    for rnd in sorted(last_frame_by_round):
        fi = last_frame_by_round[rnd]
        img = render_frame(map_, events, frame=fi, frames=frames)
        out = f"data/_amr_{tag}_r{rnd}.png"
        img.save(out)
        # end-of-round objective story for this round
        end_idx = frames[fi][1]
        objs = [e for e in events[:end_idx + 1] if isinstance(e, ObjectiveScored)]
        recent = objs[-4:]
        ostr = "; ".join(
            f"{getattr(e, 'objective_name', '?')}:{e.army_name or 'contest'} OC{e.a_oc}/{e.b_oc}"
            for e in recent
        )
        print(f"  round {rnd} -> {out}   [{ostr}]")


def main() -> None:
    for a_fac, b_fac, seed in MATCHUPS:
        _capture(a_fac, b_fac, seed)


if __name__ == "__main__":
    main()
