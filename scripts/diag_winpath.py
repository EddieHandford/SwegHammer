"""Win-path diagnostic: HOW does each over-pole faction bank its Victory Points
and win? Splits the false "melee over-pole cluster" into per-faction signatures.

Per faction, over a fixed seeded matrix (attribution from the event stream's
army name "A"/"B" mapped to the battle's factions, and final survivor counts):

  * win%                      sanity
  * primary VP / game         objective-hold scoring (ObjectiveScored)
  * secondary VP / game       total (RoundEnded) minus primary
  * VP margin / game          own total VP minus opponent's
  * rounds                    game length (5 unless ended early)
  * own survivors %           board presence at the end (alive / starting models)
  * tables-opp % / tabled %   wipes the enemy / gets wiped

Read against Adeptus Astartes (in-band). A faction that over-scores on PRIMARY
with high survivors and long games wins by durable objective-holding; one that
over-scores via TABLING / low opponent survivors wins by killing; one that
out-margins without tabling and dies itself points at deep-strike alpha / burst.

Run:  PYTHONHASHSEED=0 python -m scripts.diag_winpath
"""
from __future__ import annotations

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable, "-m", "scripts.diag_winpath"], os.environ)

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
    "games": 0, "wins": 0, "prim_for": 0, "total_for": 0, "total_against": 0,
    "rounds_sum": 0, "models_start": 0, "models_end": 0,
    "tabled_opp": 0, "got_tabled": 0, "points_sum": 0.0,
})


class _WinPath:
    """Per-battle accumulator over the event stream (army names 'A'/'B')."""

    def __init__(self) -> None:
        self.prim = {"A": 0, "B": 0}
        self.total = {"A": 0, "B": 0}
        self.rounds = 0
        self.winner = None

    def on_event(self, e) -> None:
        n = type(e).__name__
        if n == "ObjectiveScored" and e.army_name in ("A", "B") and e.vp_awarded:
            self.prim[e.army_name] += e.vp_awarded
        elif n == "RoundEnded":
            self.total["A"] = e.a_vp_total
            self.total["B"] = e.b_vp_total
            self.rounds = e.round_num
        elif n == "BattleEnded":
            self.winner = e.winner
            self.rounds = e.rounds


def _run_one(a_fac: str, b_fac: str, s: int) -> None:
    pair_seed = (hash(a_fac) % 997 * 1000 + hash(b_fac) % 997) * 100 + s
    random.seed(pair_seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(s), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(s + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    wp = _WinPath()
    battle_map = _pick_rotation_map(s)
    primary = _pick_primary_mission(pair_seed)
    Battle(a, b, map_=battle_map, primary_mission=primary, subscribers=[wp]).run()

    for letter, fac, army, opp in (("A", a_fac, a, b), ("B", b_fac, b, a)):
        st = STATS[fac]
        st["games"] += 1
        st["points_sum"] += sum(u.profile.points_cost for u in army.units)
        st["models_start"] += len(army.units)
        alive = sum(1 for u in army.units if u.is_alive)
        st["models_end"] += alive
        st["prim_for"] += wp.prim[letter]
        st["total_for"] += wp.total[letter]
        st["total_against"] += wp.total["B" if letter == "A" else "A"]
        st["rounds_sum"] += wp.rounds
        if wp.winner == letter:
            st["wins"] += 1
        if sum(1 for u in opp.units if u.is_alive) == 0:
            st["tabled_opp"] += 1
        if alive == 0:
            st["got_tabled"] += 1


def main() -> None:
    n = 0
    for a_fac in PANEL:
        for b_fac in PANEL:
            if a_fac == b_fac:
                continue
            for s in SEEDS:
                _run_one(a_fac, b_fac, s)
                n += 1

    print(f"\nWin-path diagnostic — {n} battles\n")
    hdr = (f"{'faction':<20}{'win%':>6}{'prim/g':>8}{'sec/g':>7}{'margin/g':>9}"
           f"{'rounds':>7}{'surv%':>7}{'tblOpp%':>8}{'tabled%':>8}")
    print(hdr)
    print("-" * len(hdr))
    for fac in PANEL:
        st = STATS[fac]
        g = st["games"] or 1
        prim = st["prim_for"] / g
        total = st["total_for"] / g
        margin = (st["total_for"] - st["total_against"]) / g
        surv = 100.0 * st["models_end"] / (st["models_start"] or 1)
        tag = "  <-- OVER-POLE" if fac in OVER_POLE else ""
        print(f"{fac:<20}{100.0 * st['wins'] / g:>6.1f}{prim:>8.1f}"
              f"{total - prim:>7.1f}{margin:>9.1f}{st['rounds_sum'] / g:>7.2f}"
              f"{surv:>7.1f}{100.0 * st['tabled_opp'] / g:>8.1f}"
              f"{100.0 * st['got_tabled'] / g:>8.1f}{tag}")
    print("\nprim = primary objective VP/game; sec = secondary VP/game; margin = own "
          "minus opponent total VP; surv% = alive/starting models at game end; "
          "tblOpp% = wiped the enemy; tabled% = got wiped. Compare OVER-POLE rows to "
          "Adeptus Astartes (in-band).")


if __name__ == "__main__":
    main()
