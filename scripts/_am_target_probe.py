"""What does Astra Militarum infantry actually shoot at?

`scripts/_am_infantry_probe.py` established that Cadian Shock Troops and Death
Korps of Krieg DO have a legal target in weapon range with line of sight on
roughly seventy percent of their activations, and still deal damage on one
percent and zero percent of them respectively — while Tempestus Scions, firing
the same way, land damage on 15.7 percent, which is exactly what a single
Strength 3 shot should do. The engine is fine; the difference has to be the
TARGET.

This records, for each watched datasheet, the target it chose and the expected
unsaved wounds that choice yields, against the expected unsaved wounds of the
BEST target that was legally available at that moment. A large gap means the
target scorer is sending lasguns at things lasguns cannot hurt.

Run: PYTHONHASHSEED=0 python -m scripts._am_target_probe
"""
from __future__ import annotations
import os
import random
from collections import Counter, defaultdict

import code.simulator as SIM
import code.units as U
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

WATCH = {"Cadian Shock Troops", "Death Korps of Krieg", "Kasrkin", "Tempestus Scions"}
FAC = "Astra Militarum"
OPPS = ["Genestealer Cults", "Adepta Sororitas", "Necrons", "Death Guard"]
N = int(os.environ.get("TP_N", "3"))
_idx = {f: i for i, f in enumerate(FACTIONS)}

CHOSEN = defaultdict(Counter)
EFF = defaultdict(lambda: {"got": 0.0, "best": 0.0, "n": 0})


def _p_wound(s, t):
    if s >= 2 * t:
        return 5 / 6
    if s > t:
        return 4 / 6
    if s == t:
        return 3 / 6
    if s * 2 <= t:
        return 1 / 6
    return 2 / 6


def _expected(attacker_profile, target) -> float:
    """Expected unsaved wounds for one activation into `target` — the same
    arithmetic the shooting resolution does, at the level of detail needed to
    RANK targets (hit 4+, wound by the Strength/Toughness table, armour save
    modified by armour penetration, damage per unsaved wound)."""
    p = attacker_profile
    shots = max(1, int(p.attacks or 1))
    pw = _p_wound(int(p.strength or 1), int(target.profile.toughness or 1))
    sv = int(target.profile.save or 7) - int(p.ap or 0)
    inv = int(getattr(target.profile, "invulnerable_save", 0) or 0)
    if inv:
        sv = min(sv, inv)
    p_fail = max(0.0, min(1.0, (sv - 1) / 6.0)) if sv <= 6 else 1.0
    return shots * 0.5 * pw * p_fail * float(p.damage or 1)


_real_attack = U.Unit.attack


def _probe_attack(self, target, *a, **kw):
    name = self.profile.name or "?"
    if name in WATCH and (self.profile.faction or "") == FAC and kw.get("mode") != "melee":
        CHOSEN[name][target.profile.name or "?"] += 1
        got = _expected(self.profile, target)
        army = getattr(target, "army_ref", None)
        best = got
        if army is not None:
            rng = float(self.profile.range_inches or 0.0)
            for u in army.alive_units:
                if getattr(u, "embarked_in", None) is not None:
                    continue
                if SIM._distance(self.position, u.position) > rng:
                    continue
                best = max(best, _expected(self.profile, u))
        d = EFF[name]
        d["got"] += got
        d["best"] += best
        d["n"] += 1
    return _real_attack(self, target, *a, **kw)


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    U.Unit.attack = _probe_attack
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", FAC, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                       primary_mission=_pick_primary_mission(ps)).run()

    for name in sorted(EFF):
        d = EFF[name]
        if not d["n"]:
            continue
        print(f"\n=== {name} — {d['n']} resolved ranged attacks ===")
        print(f"   expected unsaved wounds, target CHOSEN : {d['got']/d['n']:.4f} per activation")
        print(f"   expected unsaved wounds, BEST in range : {d['best']/d['n']:.4f} per activation")
        print(f"   efficiency of the choice               : "
              f"{100*d['got']/max(1e-9,d['best']):.1f}%")
        print("   most-chosen targets:")
        for tname, c in CHOSEN[name].most_common(6):
            print(f"      {100*c/d['n']:5.1f}%  {tname}")
