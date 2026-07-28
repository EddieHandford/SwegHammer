"""Scratch render: reproduce the FAITHFUL anchor pairing (matches
scripts.pilot_manual._winner / evaluate_vs_meta._play_pairing) for chosen
(under, over, seed) games and dump the end-of-round board image per round, so
the board can be read on ACTUAL loss seeds under the DEFAULT production config
(no forced SWEG_AM_* gates — unlike diag_render_am which forces REALISM+RECON).

Run: PYTHONHASHSEED=0 python -m scripts._pilot_am_render "Astra Militarum" "Adeptus Astartes" 24,60
"""
from __future__ import annotations
import os, sys, random

from code.army_builder import build_faction_random_army
from code.events import EventLog, RoundStarted, RoundEnded, ObjectiveScored
from code.simulator import Battle
from code.renderer import aggregate_activations, render_frame
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission


def _rounds_by_index(events):
    out = [0] * len(events); r = 0
    for i, ev in enumerate(events):
        if isinstance(ev, RoundStarted):
            r = ev.round_num
        out[i] = r
    return out


def render_game(under, over, seed):
    random.seed(seed)  # faithful to _winner: global RNG seeded per game
    a = build_faction_random_army("A", under, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", over, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    tag = (under.split()[0] + "_v_" + over.split()[0] + f"_s{seed}").lower()
    log = EventLog()
    map_ = _pick_rotation_map(seed)
    res = Battle(a, b, subscribers=[log], map_=map_,
                 primary_mission=_pick_primary_mission(seed)).run()
    events = log.events
    frames = aggregate_activations(events)
    rbi = _rounds_by_index(events)
    last_by_round = {}
    for fi, (_s, e) in enumerate(frames):
        rnd = rbi[e]
        if rnd >= 1:
            last_by_round[rnd] = fi
    rends = [e for e in events if isinstance(e, RoundEnded)]
    avp, bvp = (rends[-1].a_vp_capped, rends[-1].b_vp_capped) if rends else (0, 0)
    print(f"\n### {tag}  A={under} ({len(a.units)}u) vs B={over} ({len(b.units)}u)")
    print(f"    WINNER={res.winner}  capped VP  A(AM)={avp}  B={bvp}   map={getattr(map_,'name','?')}")
    for rnd in sorted(last_by_round):
        fi = last_by_round[rnd]
        img = render_frame(map_, events, frame=fi, frames=frames)
        out = f"data/_amr2_{tag}_r{rnd}.png"
        img.save(out)
        end_idx = frames[fi][1]
        objs = [e for e in events[:end_idx + 1] if isinstance(e, ObjectiveScored)]
        recent = objs[-5:]
        ostr = "; ".join(
            f"{getattr(e,'objective_name','?')}:{e.army_name or 'contest'}(OC {e.a_oc}/{e.b_oc})"
            for e in recent)
        print(f"    round {rnd} -> {out}   [{ostr}]")


def main():
    under = sys.argv[1] if len(sys.argv) > 1 else "Astra Militarum"
    over = sys.argv[2] if len(sys.argv) > 2 else "Adeptus Astartes"
    seeds = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "24").split(",")]
    for s in seeds:
        render_game(under, over, s)


if __name__ == "__main__":
    main()
