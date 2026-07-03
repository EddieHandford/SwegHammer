"""Read-only diagnostic: replay ONE specific Astra Militarum vs Emperor's
Children game from the standing anchor's exact eval-path construction (see
scripts._ec_crater_replay for the seed reconstruction) and print a detailed
round-by-round narrative, plus optional per-round renders, so the crater
mechanism can be told as a concrete story rather than just aggregate numbers.

Mirrors scripts/diag_pilot_am_vs_ik.py's move-log presentation, applied to the
anchor's OWN recorded seeds (not a fresh pilot seed) so the narrative is
faithful to the actual eval cell being diagnosed.

Run: PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts._ec_crater_narrative <a_fac> <b_fac> <seed> [--render]
Example:
  python -m scripts._ec_crater_narrative "Emperor's Children" "Astra Militarum" 4 --render
"""
from __future__ import annotations

import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "scripts._ec_crater_narrative"] + sys.argv[1:], env=os.environ).returncode)

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, UnitMoved, UnitShot, UnitFought,
    UnitCharged, UnitKilled, UnitAdvanced, ObjectiveScored, EventLog,
)
from code.simulator import Battle
from code.renderer import aggregate_activations, render_frame
from scripts.evaluate_vs_meta import FACTIONS, _pick_rotation_map, _pick_primary_mission

A_FAC = sys.argv[1]
B_FAC = sys.argv[2]
S = int(sys.argv[3])
RENDER = "--render" in sys.argv
TAG = "crater_" + (A_FAC.split()[0] + "_v_" + B_FAC.split()[0]).lower() + f"_s{S}"

FAC_IDX = {f: i for i, f in enumerate(FACTIONS)}


def _near_obj(pos, objs):
    best, bd = None, 1e9
    for i, o in enumerate(objs):
        d = ((pos[0] - o.x) ** 2 + (pos[1] - o.y) ** 2) ** 0.5
        if d < bd:
            best, bd = i, d
    return (best, bd) if bd <= 6.0 else (None, bd)


def main() -> None:
    ai, bi = FAC_IDX[A_FAC], FAC_IDX[B_FAC]
    pair_seed = (ai * 1000 + bi) * 100 + S
    random.seed(pair_seed)
    a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(S), use_archetype=True)
    b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(S + 10000), use_archetype=True)
    log = EventLog()
    battle_map = _pick_rotation_map(S)
    primary = _pick_primary_mission(pair_seed)
    battle = Battle(a, b, map_=battle_map, rules=None, primary_mission=primary, subscribers=[log])
    result = battle.run()
    ev = log.events
    objs = battle_map.objectives

    info = {}
    for e in ev:
        if isinstance(e, BattleStarted):
            for u in e.units:
                info[u.uid] = {"name": u.name, "army": u.army}
    last = {uid: i["name"] for uid, i in info.items()}

    if RENDER:
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
            render_frame(battle_map, ev, frame=fi, frames=frames).save(f"data/_pilot_{TAG}_r{rnd}.png")

    print(f"### {A_FAC} (A) vs {B_FAC} (B)  seed={S}  pair_seed={pair_seed}  "
          f"map={getattr(battle_map, 'name', '?')}  primary={primary}")
    print(f"A models={len([u for u in info.values() if u['army']=='A'])}  "
          f"B models={len([u for u in info.values() if u['army']=='B'])}  "
          f"objectives={[(round(o.x), round(o.y)) for o in objs]}")
    print(f"RESULT: winner={result.winner}  rounds={result.rounds}  "
          f"a_survivors={result.a_survivors}/{result.a_start}  b_survivors={result.b_survivors}/{result.b_start}")
    a_primary = battle._a_vp - battle._a_secondary_vp - battle._a_challenger_vp
    b_primary = battle._b_vp - battle._b_secondary_vp - battle._b_challenger_vp
    a_capped, b_capped = battle._capped_vp_pair()
    print(f"FINAL VP: A capped={a_capped} (primary={a_primary} secondary={battle._a_secondary_vp} "
          f"challenger={battle._a_challenger_vp})  "
          f"B capped={b_capped} (primary={b_primary} secondary={battle._b_secondary_vp} "
          f"challenger={battle._b_challenger_vp})")
    cur, acts = 0, {}

    def flush(rnd):
        if not rnd:
            return
        rends = [e for e in ev if isinstance(e, RoundEnded) and e.round_num == rnd]
        if rends:
            cap = (rends[-1].a_vp_capped, rends[-1].b_vp_capped)
            raw = (rends[-1].a_vp_total, rends[-1].b_vp_total)
        else:
            cap = ("?", "?")
            raw = ("?", "?")
        print(f"\n========== ROUND {rnd}   VP (capped): A {cap[0]} - {cap[1]} B"
              f"   [uncapped {raw[0]}-{raw[1]}] ==========")
        os_ = list(acts.get(rnd, {}).get("_obj", []))
        for e in os_:
            who = e.army_name or "CONTESTED"
            print(f"  OBJ {e.objective_name}: {who}  OC A{e.a_oc}/B{e.b_oc}  (+{e.vp_awarded}VP)")
        for army, label in (("A", A_FAC), ("B", B_FAC)):
            print(f"  -- {label} ({army}) --")
            n_shown = 0
            for uid, d in acts.get(rnd, {}).items():
                if uid == "_obj" or info.get(uid, {}).get("army") != army:
                    continue
                if not (d.get("shot") or d.get("charged") or d.get("died")):
                    continue  # only show units that DID something combat-relevant
                n_shown += 1
                nm = info[uid]["name"][:26]
                nobj, nd = _near_obj(d["pos"], objs) if d.get("pos") else (None, 99)
                where = f"obj{nobj}" if nobj is not None else f"{nd:.0f}in-off"
                bits = []
                if d.get("moved"):
                    bits.append(f"move {d['moved']:.0f}in->{where}")
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
            if n_shown == 0:
                print("     (no combat activity logged)")

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
    if RENDER:
        print(f"\n(renders: data/_pilot_{TAG}_r1..r5.png)")


if __name__ == "__main__":
    main()
