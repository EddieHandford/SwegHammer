"""Paired A/B for SWEG_THREATPRIO: does letting low-output bodies mass onto
objectives in-range raise Astra Militarum (presence + win rate) and, via the
closed matrix, pull the over-pole down?

Per pairing + seed, two arms with identical CRN army builds: OFF (production) vs
ON (SWEG_THREATPRIO=1). Measures each faction's win rate and its objective
marker presence (ObjectiveScored events where it had OC > 0) in both arms.

CONFIRMED if Astra Militarum's presence AND win rate rise, and the over-pole
four drift down (closed matrix). WASH if Astra Militarum doesn't move — then the
in-range body-massing axis is exhausted (like the original SWEG_MASS Stage-E).

Run:  PYTHONHASHSEED=0 python -m scripts.diag_massbodies_ab
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_massbodies_ab"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + ["Astra Militarum", "Imperial Knights", "Adeptus Custodes",
                     "Adeptus Astartes", "T'au Empire"]
SEEDS = [0, 1, 2, 3]

STATS: dict = defaultdict(lambda: {
    "games": 0, "win_off": 0, "win_on": 0, "pres_off": 0, "pres_on": 0,
})
_PAIR: dict = {"A": None, "B": None}
_PRES: dict = {"A": 0, "B": 0}


class _Pres:
    def on_event(self, e) -> None:
        if type(e).__name__ == "ObjectiveScored":
            if e.a_oc > 0:
                _PRES["A"] += 1
            if e.b_oc > 0:
                _PRES["B"] += 1


def _play(a_fac: str, b_fac: str, s: int, on: bool):
    os.environ["SWEG_THREATPRIO"] = "1" if on else "0"
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return None, 0, 0
    _PRES["A"] = _PRES["B"] = 0
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    w = Battle(a, b, map_=battle_map, primary_mission=primary, subscribers=[_Pres()]).run().winner
    return w, _PRES["A"], _PRES["B"]


def _run_pair(a_fac: str, b_fac: str, s: int) -> None:
    w0, pa0, pb0 = _play(a_fac, b_fac, s, False)
    w1, pa1, pb1 = _play(a_fac, b_fac, s, True)
    if w0 is None or w1 is None:
        return
    for letter, fac, p0, p1 in (("A", a_fac, pa0, pa1), ("B", b_fac, pb0, pb1)):
        st = STATS[fac]
        st["games"] += 1
        st["win_off"] += (w0 == letter)
        st["win_on"] += (w1 == letter)
        st["pres_off"] += p0
        st["pres_on"] += p1


def main() -> None:
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_pair(a_fac, b_fac, s)
    os.environ["SWEG_THREATPRIO"] = "0"

    print("\nSWEG_THREATPRIO paired A/B (win% + marker presence)\n")
    hdr = (f"{'faction':<20}{'win%off':>8}{'win%on':>8}{'dWin':>7}"
           f"{'pres/g off':>11}{'pres/g on':>11}{'dPres':>7}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        wo, wn = 100.0 * st["win_off"] / g, 100.0 * st["win_on"] / g
        po, pn = st["pres_off"] / g, st["pres_on"] / g
        tag = "  UNDER" if fac == "Astra Militarum" else ("  OVER" if fac in OVER_POLE else "")
        print(f"{fac:<20}{wo:>8.1f}{wn:>8.1f}{wn - wo:>+7.1f}{po:>11.1f}{pn:>11.1f}"
              f"{pn - po:>+7.1f}{tag}")
    print("\ndWin/dPres = ON minus OFF. CONFIRMED if Astra Militarum dWin and dPres are "
          "clearly positive and the OVER rows drift negative.")


if __name__ == "__main__":
    main()
