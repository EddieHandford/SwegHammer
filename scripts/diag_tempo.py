"""Tempo + reserve-reliance diagnostic: does each over-pole faction win by an
early ALPHA (deep-strike / fast burst) or a sustained GRIND? Separates the
remaining ambiguous signatures (Death Guard's durable contest, Daemons' unknown
mechanism) from World Eaters' aggressive trade.

Per faction, over a fixed seeded matrix:
  * dmg dealt per round R1..R5 as a SHARE of the faction's total damage (the
    tempo SHAPE — alpha factions front-load, grinders are flat / back-loaded).
    Robust attribution with no uid map: a subscriber holds both army refs and
    reads each army's total health at every RoundEnded; the opponent's health
    drop that round is the damage this faction dealt (melee + shooting + mortals).
  * deep-strike reliance: share of the army's models and points that start in
    Reserves (profile.deep_strike) — the alpha-from-nowhere axis.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_tempo
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_tempo"], os.environ)

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

OVER_POLE = ["Death Guard", "World Eaters", "Emperor's Children", "Chaos Daemons"]
PANEL = OVER_POLE + [
    "Astra Militarum", "Imperial Knights", "Adeptus Custodes",
    "Adeptus Astartes", "T'au Empire",
]
SEEDS = [0, 1]

STATS: dict = defaultdict(lambda: {
    "games": 0, "dmg_r": defaultdict(float), "dmg_total": 0.0,
    "ds_models": 0, "models": 0, "ds_points": 0.0, "points": 0.0,
})


class _Tempo:
    """Holds both army refs; per-round opponent health-drop = damage this faction dealt."""

    def __init__(self, a, b, a_fac, b_fac) -> None:
        self.a, self.b, self.af, self.bf = a, b, a_fac, b_fac
        self.last_a = self._hp(a)
        self.last_b = self._hp(b)

    @staticmethod
    def _hp(army) -> float:
        return sum(max(0.0, u.current_health) for u in army.units)

    def on_event(self, e) -> None:
        if type(e).__name__ != "RoundEnded":
            return
        ha, hb = self._hp(self.a), self._hp(self.b)
        r = min(e.round_num, 5)
        dealt_by_a = max(0.0, self.last_b - hb)   # b lost this much -> a dealt it
        dealt_by_b = max(0.0, self.last_a - ha)
        STATS[self.af]["dmg_r"][r] += dealt_by_a
        STATS[self.af]["dmg_total"] += dealt_by_a
        STATS[self.bf]["dmg_r"][r] += dealt_by_b
        STATS[self.bf]["dmg_total"] += dealt_by_b
        self.last_a, self.last_b = ha, hb


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    for army, fac in ((a, a_fac), (b, b_fac)):
        st = STATS[fac]
        st["games"] += 1
        st["models"] += len(army.units)
        st["ds_models"] += sum(1 for u in army.units if u.profile.deep_strike)
        st["points"] += sum(u.profile.points_cost for u in army.units)
        st["ds_points"] += sum(u.profile.points_cost for u in army.units if u.profile.deep_strike)
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary,
           subscribers=[_Tempo(a, b, a_fac, b_fac)]).run()


def main() -> None:
    n = 0
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
                n += 1

    print(f"\nTempo + reserve-reliance diagnostic — {n} battles\n")
    hdr = (f"{'faction':<20}{'R1%':>6}{'R2%':>6}{'R3%':>6}{'R4%':>6}{'R5%':>6}"
           f"{'early%':>8}{'DSmdl%':>8}{'DSpts%':>8}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        tot = st["dmg_total"] or 1.0
        rs = [100.0 * st["dmg_r"].get(r, 0.0) / tot for r in range(1, 6)]
        early = rs[0] + rs[1]
        dsm = 100.0 * st["ds_models"] / (st["models"] or 1)
        dsp = 100.0 * st["ds_points"] / (st["points"] or 1)
        tag = "  <-- OVER-POLE" if fac in OVER_POLE else ""
        print(f"{fac:<20}{rs[0]:>6.1f}{rs[1]:>6.1f}{rs[2]:>6.1f}{rs[3]:>6.1f}"
              f"{rs[4]:>6.1f}{early:>8.1f}{dsm:>8.1f}{dsp:>8.1f}{tag}")
    print("\nRn% = share of the faction's total damage dealt in round n; early% = "
          "R1+R2 share (alpha front-load); DSmdl%/DSpts% = share of models/points that "
          "start in Reserves (deep-strike). Alpha factions front-load + deep-strike; "
          "grinders are flat/back-loaded.")


if __name__ == "__main__":
    main()
