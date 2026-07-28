"""Per-unit contribution audit for one faction: who fires, who kills, who dies.

Distrust-everything instrument. For every unit datasheet in the built army it
records, across whole games: how many shooting activations it got, how many of
those actually resolved an attack, wounds dealt, wounds taken, and how long it
survived. A datasheet that costs two hundred points and resolves almost no
attacks is a misrepresentation, not a tuning question — that is how the Rogal
Dorn firing 3.1 times its legal loadout and the artillery-hold defect were both
found.

Run: PYTHONHASHSEED=0 AUD_FACTION="Astra Militarum" python -m scripts._am_unit_audit
"""
from __future__ import annotations
import os
import random
from collections import defaultdict

import code.simulator as SIM
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("AUD_FACTION", "Astra Militarum")
OPPS = os.environ.get("AUD_OPPS", "Genestealer Cults,Adepta Sororitas,Necrons,Death Guard").split(",")
N = int(os.environ.get("AUD_N", "5"))
_idx = {f: i for i, f in enumerate(FACTIONS)}

S = defaultdict(lambda: {
    "activations": 0, "resolved": 0, "no_target": 0, "dealt": 0.0,
    "taken": 0.0, "points": 0.0, "instances": 0, "alive_end": 0,
})

_real_do_shoot = SIM.Battle._do_shoot


def _probe_shoot(self, attacker, attacker_army, defender_army):
    if (attacker.profile.faction or "") != FAC:
        return _real_do_shoot(self, attacker, attacker_army, defender_army)
    name = attacker.profile.name or "?"
    d = S[name]
    d["activations"] += 1
    before = sum(u.current_health for u in defender_army.alive_units)
    _real_do_shoot(self, attacker, attacker_army, defender_army)
    after = sum(u.current_health for u in defender_army.alive_units)
    lost = before - after
    if lost > 0:
        d["resolved"] += 1
        d["dealt"] += lost
    else:
        d["no_target"] += 1


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    SIM.Battle._do_shoot = _probe_shoot
    games = 0
    for opp in OPPS:
        opp = opp.strip()
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            batt = SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                              primary_mission=_pick_primary_mission(ps))
            # Snapshot AFTER Battle construction: the constructor is what wires
            # army_ref / squad identity, and the Reinforcements! stratagem can
            # add unit instances mid-game, so a pre-construction uid map goes
            # stale. `full_health` is the datasheet value, so a unit that
            # appears mid-game is still accounted for correctly.
            start = {u.uid: float(u.current_health) for u in batt.a.units}
            for u in batt.a.units:
                d = S[u.profile.name or "?"]
                d["instances"] += 1
                d["points"] += float(u.profile.points_cost or 0)
            batt.run()
            for u in batt.a.units:
                d = S[u.profile.name or "?"]
                d["taken"] += max(
                    0.0,
                    start.get(u.uid, float(u.profile.health or 0)) - float(u.current_health),
                )
                if u.is_alive:
                    d["alive_end"] += 1
            games += 1

    print(f"=== {FAC} per-unit audit, {games} games vs {', '.join(o.strip() for o in OPPS)} ===")
    hdr = (f"{'datasheet':28s} {'pts/gm':>7s} {'activ':>6s} {'silent':>7s} "
           f"{'dealt':>8s} {'taken':>8s} {'survive':>8s} {'wounds/100pts':>14s}")
    print(hdr)
    rows = sorted(S.items(), key=lambda kv: -kv[1]["points"])
    for name, d in rows:
        if not d["instances"]:
            continue
        ppg = d["points"] / games
        act = d["activations"] / games
        silent = 100 * d["no_target"] / max(1, d["activations"])
        eff = d["dealt"] / max(1e-9, d["points"] / 100.0)
        print(f"{name[:28]:28s} {ppg:7.1f} {act:6.2f} {silent:6.0f}% "
              f"{d['dealt']/games:8.1f} {d['taken']/games:8.1f} "
              f"{100*d['alive_end']/max(1,d['instances']):7.0f}% {eff:14.2f}")
    tot_pts = sum(d["points"] for d in S.values()) / games
    tot_dealt = sum(d["dealt"] for d in S.values()) / games
    print(f"\narmy total: {tot_pts:.0f} points/game, {tot_dealt:.1f} wounds dealt/game")
