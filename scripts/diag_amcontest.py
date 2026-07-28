"""Localize WHY Astra Militarum loses the objective-control contest (it delivers
normal OC onto markers but converts to primary VP worst-in-class).

Two hypotheses, both testable from the ObjectiveScored stream (a_oc/b_oc = each
army's summed OC on the marker at scoring; army_name = who won the VP):
  H1 OUT-MASSED: AM is present on markers but the opponent has MORE OC there
     (positioning / not massing onto the decisive marker).
  H2 DYING: AM's objective-holders are destroyed before the scoring step, so its
     marker-OC collapses in the late rounds.

Per faction:
  * present/game        scoring events where it had OC > 0 on the marker
  * won%                share of present where it took the VP
  * outmassed%          share of present where the opponent had MORE OC (H1)
  * OC R1-2% / R4-5%    OC-on-markers front vs back half (H2: late collapse)

Run:  PYTHONHASHSEED=0 python -m scripts.diag_amcontest
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_amcontest"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + ["Astra Militarum", "Imperial Knights", "Adeptus Custodes",
                     "Adeptus Astartes", "T'au Empire"]
SEEDS = [0, 1, 2]

STATS: dict = defaultdict(lambda: {
    "games": 0, "present": 0, "won": 0, "outmassed": 0,
    "oc_early": 0.0, "oc_late": 0.0,
})
_PAIR: dict = {"A": None, "B": None}


class _Contest:
    def __init__(self) -> None:
        self.round = 1

    def on_event(self, e) -> None:
        n = type(e).__name__
        if n == "RoundStarted":
            self.round = e.round_num
            return
        if n != "ObjectiveScored":
            return
        for letter, own, opp in (("A", e.a_oc, e.b_oc), ("B", e.b_oc, e.a_oc)):
            fac = _PAIR[letter]
            st = STATS[fac]
            if own > 0:
                st["present"] += 1
                if e.army_name == letter:
                    st["won"] += 1
                if opp > own:
                    st["outmassed"] += 1
                if self.round <= 2:
                    st["oc_early"] += own
                elif self.round >= 4:
                    st["oc_late"] += own


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    _PAIR["A"], _PAIR["B"] = a_fac, b_fac
    STATS[a_fac]["games"] += 1
    STATS[b_fac]["games"] += 1
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary, subscribers=[_Contest()]).run()


def main() -> None:
    n = 0
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
                n += 1

    print(f"\nObjective-contest localization — {n} battles\n")
    hdr = (f"{'faction':<20}{'present/g':>10}{'won%':>7}{'outmassed%':>11}"
           f"{'ocEarly':>9}{'ocLate':>9}{'late/early':>11}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        pres = st["present"] or 1
        le = (st["oc_late"] / st["oc_early"]) if st["oc_early"] else 0.0
        tag = "  <-- UNDER" if fac == "Astra Militarum" else ("  OVER" if fac in OVER_POLE else "")
        print(f"{fac:<20}{st['present'] / g:>10.1f}{100.0 * st['won'] / pres:>7.1f}"
              f"{100.0 * st['outmassed'] / pres:>11.1f}{st['oc_early'] / g:>9.1f}"
              f"{st['oc_late'] / g:>9.1f}{le:>11.2f}{tag}")
    print("\nwon% = of markers it's present on, share it took the VP; outmassed% = share "
          "where the opponent had MORE OC (H1 positioning); late/early = round 4-5 vs "
          "1-2 marker-OC ratio (H2: <1 means its holders die off late).")


if __name__ == "__main__":
    main()
