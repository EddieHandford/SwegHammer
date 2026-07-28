"""Confirm the Astra Militarum under-contest mechanism: do its low-value BODY
units fail to seek objectives because SWEG_MASS only fires when a unit is OUT of
its firing range (so an in-range gunline never masses)?

Wraps strategy.pick_move_intent and tallies the returned intent per faction,
split by whether the unit is a BODY (low ranged damage-per-activation, < 1.5) or
a GUN (>= 1.5). Objective-seeking = CAPTURE + STEAL. If Astra Militarum's BODY
units have a much lower objective-seeking share than the field's bodies, the
in-range gate is the cause and a low-value-in-range massing branch is the fix.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_intent
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_intent"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import code.simulator as sim
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + ["Astra Militarum", "Imperial Knights", "Adeptus Custodes",
                     "Adeptus Astartes", "T'au Empire"]
SEEDS = [0, 1, 2]
OBJSEEK = {"CAPTURE", "STEAL"}

# per (faction, bucket): intent -> count
STATS: dict = defaultdict(lambda: defaultdict(int))
_orig_pmi = sim.pick_move_intent


def _ranged_dpa(p) -> float:
    return (getattr(p, "attacks", 0) or 0) * (getattr(p, "hit_probability", 0) or 0) \
        * (getattr(p, "per_shot_damage", 0.0) or 0.0)


def _wrap_pmi(unit, friendly, enemy, *a, **k):
    res = _orig_pmi(unit, friendly, enemy, *a, **k)
    fac = (unit.profile.faction or "?") or "?"
    bucket = "body" if _ranged_dpa(unit.profile) < 1.5 else "gun"
    STATS[(fac, bucket)][res[1]] += 1
    return res


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary).run()


def main() -> None:
    sim.pick_move_intent = _wrap_pmi
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
    sim.pick_move_intent = _orig_pmi

    print("\nMove-intent objective-seeking share (CAPTURE+STEAL) by faction\n")
    hdr = f"{'faction':<20}{'BODY obj%':>10}{'BODY n':>8}{'GUN obj%':>10}{'GUN n':>8}"
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        row = []
        for bucket in ("body", "gun"):
            d = STATS[(fac, bucket)]
            tot = sum(d.values()) or 1
            seek = sum(v for k, v in d.items() if k in OBJSEEK)
            row.append((100.0 * seek / tot, sum(d.values())))
        tag = "  <-- UNDER" if fac == "Astra Militarum" else ("  OVER" if fac in OVER_POLE else "")
        print(f"{fac:<20}{row[0][0]:>10.1f}{row[0][1]:>8}{row[1][0]:>10.1f}{row[1][1]:>8}{tag}")
    print("\nBODY = ranged DPA < 1.5 (cheap objective-holders); GUN = >= 1.5. obj% = "
          "share of activations choosing CAPTURE/STEAL. If Astra Militarum BODY obj% "
          "is far below the field, its bodies stay in-range shooting instead of "
          "massing onto markers — the in-range SWEG_MASS gate is the cause.")


if __name__ == "__main__":
    main()
