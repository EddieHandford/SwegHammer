"""Per-unit contribution audit covering BOTH shooting and melee.

`scripts/_am_unit_audit.py` hooks `Battle._do_shoot` only. That was fine for
Astra Militarum, a shooting army, where it found the real defect (Cadian Shock
Troops resolving 46 activations a game for 0.4 wounds). It is actively
MISLEADING for a melee army: run against Tyranids it reports Hormagaunts and
Tyrant Guard as "100 percent silent, 0.0 wounds dealt", which is the probe
measuring the wrong phase — those datasheets carry no ranged weapons at all.

This version hooks `_do_shoot` AND `_do_fight` and reports them separately, so a
melee army's contribution is visible and the silent-activation signal means what
it claims to mean.

Run: PYTHONHASHSEED=0 UA_FACTION=Tyranids python -m scripts._unit_audit_full
"""
from __future__ import annotations
import collections
import os
import random

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("UA_FACTION", "Tyranids")
N = int(os.environ.get("UA_N", "4"))
OPPS = os.environ.get(
    "UA_OPPS", "Adeptus Astartes,Necrons,Adepta Sororitas,Death Guard"
).split(",")
_idx = {f: i for i, f in enumerate(FACTIONS)}

S = collections.defaultdict(lambda: collections.Counter())
F = collections.defaultdict(float)

_real_shoot = SIM.Battle._do_shoot
_real_fight = SIM.Battle._do_fight


def _wrap(real, tag):
    def inner(self, attacker, attacker_army, defender_army):
        if (attacker.profile.faction or "") != FAC:
            return real(self, attacker, attacker_army, defender_army)
        name = attacker.profile.name or "?"
        S[name][tag + "_activations"] += 1
        before = sum(u.current_health for u in defender_army.alive_units)
        out = real(self, attacker, attacker_army, defender_army)
        after = sum(u.current_health for u in defender_army.alive_units)
        lost = before - after
        if lost > 0:
            F[(name, tag)] += lost
        else:
            S[name][tag + "_silent"] += 1
        return out
    return inner


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._do_shoot = _wrap(_real_shoot, "shoot")
    SIM.Battle._do_fight = _wrap(_real_fight, "fight")

    games = 0
    for opp in OPPS:
        opp = opp.strip()
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            fa, fb = (opp, FAC) if swap else (FAC, opp)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            batt = SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                              primary_mission=_pick_primary_mission(ps))
            me = batt.b if swap else batt.a
            for u in me.units:
                S[u.profile.name or "?"]["points"] += float(u.profile.points_cost or 0)
                S[u.profile.name or "?"]["instances"] += 1
            batt.run()
            for u in me.units:
                if u.is_alive:
                    S[u.profile.name or "?"]["alive_end"] += 1
            games += 1

    g = max(1, games)
    print(f"=== {FAC} per-unit audit (shooting AND melee), {g} games ===")
    print(f"{'datasheet':28s} {'pts/gm':>7s} {'shoot':>6s} {'shotDmg':>8s} "
          f"{'fight':>6s} {'melDmg':>7s} {'survive':>8s} {'dmg/100pt':>10s}")
    rows = sorted(S.items(), key=lambda kv: -kv[1]["points"])
    tot_dmg = tot_pts = 0.0
    for name, d in rows:
        if not d["instances"]:
            continue
        sd = F[(name, "shoot")] / g
        md = F[(name, "fight")] / g
        pts = d["points"] / g
        tot_dmg += sd + md
        tot_pts += pts
        eff = (F[(name, "shoot")] + F[(name, "fight")]) / max(1e-9, d["points"] / 100.0)
        print(f"{name[:28]:28s} {pts:7.1f} {d['shoot_activations']/g:6.1f} {sd:8.1f} "
              f"{d['fight_activations']/g:6.1f} {md:7.1f} "
              f"{100*d['alive_end']/max(1,d['instances']):7.0f}% {eff:10.2f}")
    print(f"\narmy total: {tot_pts:.0f} points/game, {tot_dmg:.1f} wounds dealt/game "
          f"(shooting + melee)")
