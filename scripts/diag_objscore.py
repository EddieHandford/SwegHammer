"""Per-faction objective-scoring efficiency — Death Guard (over) vs Astra
Militarum (under) mirror probe.

Death Guard's stats are faithful (wave 249), yet it over-rates; its signature is
durable grind (highest survivors, low melee, plays to round 5). Hypothesis: the
sim over-converts durable bodies into HELD-OBJECTIVE primary Victory Points.
Mirror: Astra Militarum (-19.9, durable tanks/blobs) should UNDER-convert — if so,
one faithful objective-scoring fix moves both toward target (closed matrix).

Per faction, from the ObjectiveScored event stream (a_oc/b_oc = each army's summed
Objective Control credited on the marker when it scores; vp_awarded = primary VP):
  * primary VP / game and / 1000 pts   (scoring OUTPUT)
  * OC delivered onto markers / game and / 1000 pts   (the MECHANISM: presence)
  * army OC carried (sum of unit OC) and the delivered/carried conversion %
    (does durability convert carried OC into ON-marker OC?)

Run:  PYTHONHASHSEED=0 python -m scripts.diag_objscore
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_objscore"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
UNDER_POLE = ["Astra Militarum", "Drukhari", "Chaos Knights", "Leagues of Votann"]
PANEL = OVER_POLE + ["Astra Militarum", "Imperial Knights", "Adeptus Custodes",
                     "Adeptus Astartes", "T'au Empire"]
SEEDS = [0, 1, 2]

STATS: dict = defaultdict(lambda: {
    "games": 0, "prim_vp": 0, "oc_deliv": 0, "oc_carried": 0.0, "points_sum": 0.0,
})
_PAIR: dict = {"A": None, "B": None}


class _Obj:
    def on_event(self, e) -> None:
        if type(e).__name__ != "ObjectiveScored":
            return
        if _PAIR["A"]:
            STATS[_PAIR["A"]]["oc_deliv"] += e.a_oc
        if _PAIR["B"]:
            STATS[_PAIR["B"]]["oc_deliv"] += e.b_oc
        if e.army_name in ("A", "B") and e.vp_awarded:
            STATS[_PAIR[e.army_name]]["prim_vp"] += e.vp_awarded


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    _PAIR["A"], _PAIR["B"] = a_fac, b_fac
    for army, fac in ((a, a_fac), (b, b_fac)):
        st = STATS[fac]
        st["games"] += 1
        st["points_sum"] += sum(u.profile.points_cost for u in army.units)
        st["oc_carried"] += sum((u.profile.oc or 0) for u in army.units)
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary, subscribers=[_Obj()]).run()


def main() -> None:
    n = 0
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
                n += 1

    print(f"\nObjective-scoring efficiency — {n} battles\n")
    hdr = (f"{'faction':<20}{'prim/g':>8}{'prim/1k':>9}{'ocDel/g':>9}{'ocDel/1k':>10}"
           f"{'ocCarry':>9}{'conv%':>7}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        k = (st["points_sum"] / g / 1000.0) or 1.0
        prim = st["prim_vp"] / g
        ocd = st["oc_deliv"] / g
        carry = st["oc_carried"] / g
        conv = 100.0 * st["oc_deliv"] / st["oc_carried"] if st["oc_carried"] else 0.0
        tag = "  OVER" if fac in OVER_POLE else ("  UNDER" if fac in UNDER_POLE else "")
        print(f"{fac:<20}{prim:>8.1f}{prim / k:>9.1f}{ocd:>9.1f}{ocd / k:>10.1f}"
              f"{carry:>9.1f}{conv:>7.1f}{tag}")
    print("\nprim = primary VP/game; ocDel = own Objective Control summed onto markers "
          "across all scoring events/game; ocCarry = army's total carried OC; conv% = "
          "delivered/carried. Mirror confirmed if Death Guard OVER-converts (high "
          "prim/1k + ocDel/1k) and Astra Militarum UNDER-converts.")


if __name__ == "__main__":
    main()
