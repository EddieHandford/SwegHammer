"""Pilot-comparison harness: one Astra Militarum (under-pole) vs Imperial Knights
(over-pole) game, rendered per round, with a per-round move log of every unit's
decisions, so a human can pilot the under-pole move-by-move against the AI and
localise whether the under-pole is a faithful floor or an AI-piloting gap.

Renders: data/_pilot_amik_r{round}.png. Read-only.
Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_pilot_am_vs_ik [seed]
"""
from __future__ import annotations

import random
import sys

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, UnitMoved, UnitShot, UnitFought,
    UnitCharged, UnitKilled, UnitAdvanced, ObjectiveScored, EventLog,
)
from code.simulator import Battle
from code.renderer import aggregate_activations, render_frame
from scripts.evaluate_vs_meta import (
    _pick_rotation_map, _pick_primary_mission, FACTIONS,
)

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
A_FAC = sys.argv[2] if len(sys.argv) > 2 else "Astra Militarum"
B_FAC = sys.argv[3] if len(sys.argv) > 3 else "Imperial Knights"
TAG = (A_FAC.split()[0] + "_v_" + B_FAC.split()[0]).lower()

# Reproduce the EXACT eval game for (A_FAC vs B_FAC, seed SEED) rather than a
# random one: match evaluate_vs_meta's pair_seed packing so the global RNG (dice)
# and primary mission are identical to the eval. Without this the play dice are
# unseeded and every render of "seed N" is a different game — board-reads then
# disagree run-to-run, which the pilot protocol's round-by-round reading needs.
_fac_idx = {f: i for i, f in enumerate(FACTIONS)}
PAIR_SEED = (_fac_idx[A_FAC] * 1000 + _fac_idx[B_FAC]) * 100 + SEED


def _near_obj(pos, objs):
    best, bd = None, 1e9
    for i, o in enumerate(objs):
        d = ((pos[0] - o.x) ** 2 + (pos[1] - o.y) ** 2) ** 0.5
        if d < bd:
            best, bd = i, d
    return (best, bd) if bd <= 6.0 else (None, bd)


def main() -> None:
    random.seed(PAIR_SEED)
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(SEED), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(SEED + 10000), use_archetype=True)
    log = EventLog()
    map_ = _pick_rotation_map(SEED)
    primary = _pick_primary_mission(PAIR_SEED)
    Battle(a, b, subscribers=[log], map_=map_, primary_mission=primary).run()
    ev = log.events
    objs = map_.objectives

    info = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                info[u.uid] = {"name": u.name, "army": u.army}
    last = {uid: i["name"] for uid, i in info.items()}

    # render each round's end frame
    frames = aggregate_activations(ev)
    rbi, r = [0] * len(ev), 0
    for i, e in enumerate(ev):
        if isinstance(e, RoundStarted):
            r = e.round_num
        rbi[i] = r
    last_fi = {}
    for fi, (_s, e_idx) in enumerate(frames):
        if rbi[e_idx] >= 1:
            last_fi[rbi[e_idx]] = fi
    for rnd, fi in sorted(last_fi.items()):
        render_frame(map_, ev, frame=fi, frames=frames).save(f"data/_pilot_{TAG}_r{rnd}.png")

    # walk events round by round and summarise per unit
    print(f"### {A_FAC} (A) vs {B_FAC} (B)  seed={SEED}  map={getattr(map_,'name','?')}")
    print(f"A models={len([u for u in info.values() if u['army']=='A'])}  "
          f"B models={len([u for u in info.values() if u['army']=='B'])}  "
          f"objectives={[(round(o.x),round(o.y)) for o in objs]}")
    cur, acts = 0, {}

    def flush(rnd):
        if not rnd:
            return
        rends = [e for e in ev if isinstance(e, RoundEnded) and e.round_num == rnd]
        # Show the CAPPED standing (what decides the winner); the uncapped running
        # total is shown in parentheses so an over-cap dominator is visible.
        if rends:
            cap = (rends[-1].a_vp_capped, rends[-1].b_vp_capped)
            raw = (rends[-1].a_vp_total, rends[-1].b_vp_total)
        else:
            cap = ("?", "?")
            raw = ("?", "?")
        print(f"\n========== ROUND {rnd}   VP (capped): A(AM) {cap[0]} - {cap[1]} B(IK)"
              f"   [uncapped {raw[0]}-{raw[1]}] ==========")
        os = [e for e in acts.get(rnd, {}).get("_obj", [])]
        for e in os:
            who = e.army_name or "CONTESTED"
            print(f"  OBJ {e.objective_name}: {who}  OC A{e.a_oc}/B{e.b_oc}  (+{e.vp_awarded}VP)")
        for army, label in (("A", "AM (you pilot)"), ("B", "IK (opponent)")):
            print(f"  -- {label} --")
            for uid, d in acts.get(rnd, {}).items():
                if uid == "_obj" or info.get(uid, {}).get("army") != army:
                    continue
                nm = info[uid]["name"][:26]
                nobj, nd = _near_obj(d["pos"], objs) if d.get("pos") else (None, 99)
                where = f"obj{nobj}" if nobj is not None else f"{nd:.0f}in-off"
                bits = []
                if d.get("moved"):
                    bits.append(f"move {d['moved']:.0f}in->{where}")
                else:
                    bits.append(f"HELD @{where}")
                if d.get("adv"):
                    bits.append("ADVANCED")
                if d.get("shot"):
                    tg = ", ".join(f"{last.get(t,'?')[:18]}({dm:.0f}{'X' if k else ''})"
                                   for t, dm, k in d["shot"][:3])
                    bits.append(f"shot {tg}")
                if d.get("charged"):
                    tg = ", ".join(f"{last.get(t,'?')[:18]}{'!' if s else 'x'}" for t, s in d["charged"])
                    bits.append(f"charge {tg}")
                if d.get("died"):
                    bits.append("*** DIED ***")
                print(f"     {nm:26s} {'; '.join(bits)}")

    for i, e in enumerate(ev):
        if isinstance(e, RoundStarted):
            flush(cur)
            cur = e.round_num
            acts.setdefault(cur, {})
        elif isinstance(e, ObjectiveScored):
            acts.setdefault(cur, {}).setdefault("_obj", []).append(e)
        elif isinstance(e, UnitMoved):
            d = acts.setdefault(cur, {}).setdefault(e.unit_uid, {})
            dist = ((e.to_pos[0]-e.from_pos[0])**2 + (e.to_pos[1]-e.from_pos[1])**2) ** 0.5
            d["moved"] = d.get("moved", 0) + dist
            d["pos"] = e.to_pos
        elif isinstance(e, UnitAdvanced):
            acts.setdefault(cur, {}).setdefault(e.unit_uid, {})["adv"] = True
        elif isinstance(e, UnitShot):
            d = acts.setdefault(cur, {}).setdefault(e.attacker_uid, {})
            d.setdefault("shot", []).append((e.target_uid, e.damage, not e.target_alive_after))
        elif isinstance(e, UnitFought):
            d = acts.setdefault(cur, {}).setdefault(e.attacker_uid, {})
            d.setdefault("shot", []).append((e.target_uid, e.damage, not e.target_alive_after))
        elif isinstance(e, UnitCharged):
            d = acts.setdefault(cur, {}).setdefault(e.unit_uid, {})
            d.setdefault("charged", []).append((e.target_uid, e.succeeded))
        elif isinstance(e, UnitKilled):
            acts.setdefault(cur, {}).setdefault(e.unit_uid, {})["died"] = True
    flush(cur)
    print("\n(renders: data/_pilot_amik_r1..r5.png)")


if __name__ == "__main__":
    main()
