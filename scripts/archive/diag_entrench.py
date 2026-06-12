"""Entrenchment render (avenue-2 Stage 1+2 keep/reject input).

The watchdog's render question: with board-wide collision + sidestep ON, does an
opponent's bodies still CONTEST around a Knight that holds a marker (the faithful
10e picture — several models fit in the 3" ring beside a 170mm base), or does the
Knight's footprint push them all OUT (an ENTRENCHMENT artifact)? And do units
reach objectives at all, or end stranded mid-board?

For Imperial Knights vs body armies, at game end, for every marker an IK big model
(TITANIC / VEHICLE / MONSTER) controls, count the OPPONENT models within 3" of that
marker token. Compare collision OFF vs ON. A big drop ON = entrenchment.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_entrench
"""
from __future__ import annotations

import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

OPPONENTS = ["Astra Militarum", "Adeptus Mechanicus", "Tyranids", "Orks"]
SEEDS = list(range(1, 6))


def _within(u, obj) -> bool:
    return (u.position[0] - obj.x) ** 2 + (u.position[1] - obj.y) ** 2 <= obj.control_radius ** 2


def _is_big(u) -> bool:
    kw = u.profile.unit_keywords or ()
    return ("TITANIC" in kw or "VEHICLE" in kw or "MONSTER" in kw) and "FLY" not in kw


def measure(collision: bool):
    if collision:
        os.environ["SWEG_COLLISION"] = "1"
        os.environ["SWEG_MOVEPLAN"] = "1"
    else:
        os.environ.pop("SWEG_COLLISION", None)
        os.environ.pop("SWEG_MOVEPLAN", None)
    held = 0           # IK-controlled marker-snapshots (a big IK model within 3")
    contested = 0      # of those, how many ALSO have >=1 opponent body within 3"
    opp_bodies = 0     # total opponent models within 3" of an IK-held marker
    ik_onmarker = 0    # IK big models that end within 3" of ANY marker (reach check)
    ik_total = 0       # IK big models alive at end (denominator)
    for opp in OPPONENTS:
        for seed in SEEDS:
            for side in ("A", "B"):
                af = "Imperial Knights" if side == "A" else opp
                bf = opp if side == "A" else "Imperial Knights"
                a = build_faction_random_army("A", af, 2000, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", bf, 2000, rng=random.Random(seed + 99), use_archetype=True)
                if not a.units or not b.units:
                    continue
                bt = Battle(a, b, map_=_pick_rotation_map(seed))
                bt.run()
                ik_army = a if side == "A" else b
                opp_army = b if side == "A" else a
                for u in ik_army.alive_units:
                    if not _is_big(u):
                        continue
                    ik_total += 1
                    if any(_within(u, o) for o in bt.map.objectives):
                        ik_onmarker += 1
                for obj in bt.map.objectives:
                    if not any(_within(u, obj) for u in ik_army.alive_units if _is_big(u)):
                        continue
                    held += 1
                    n_opp = sum(1 for u in opp_army.alive_units if _within(u, obj))
                    opp_bodies += n_opp
                    if n_opp > 0:
                        contested += 1
    return held, contested, opp_bodies, ik_onmarker, ik_total


def main() -> None:
    print("=== ENTRENCHMENT render (Imperial Knights vs body armies, game-end) ===")
    for label, coll in (("collision OFF (free-stack baseline)", False),
                        ("collision ON  (sidestep + make-way)", True)):
        held, cont, ob, onm, tot = measure(coll)
        print(f"\n{label}:")
        print(f"  IK-held marker snapshots:                 {held}")
        if held:
            print(f"  of those, OPPONENT also contesting (>=1): {cont}  ({100*cont/held:.0f}%)")
            print(f"  mean opponent bodies in the 3\" ring:      {ob/held:.2f}")
        if tot:
            print(f"  IK big models reaching ANY marker:        {onm}/{tot}  ({100*onm/tot:.0f}%)  <-- reach check")
    print("\nReading: if collision-ON opponent-bodies/ring and contested% hold up near OFF,")
    print("bodies still contest around the Knight (faithful, NOT entrenched). If they")
    print("collapse toward 0, the 170mm base is pushing contesters out (entrenchment).")
    print("IK-reaching-a-marker% near OFF = units still reach objectives (not stranded).")


if __name__ == "__main__":
    main()
