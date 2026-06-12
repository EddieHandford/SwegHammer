"""
iter12 TSON diagnostic — investigate why TSON random_fill mode under-performs
by -6.5pt despite the iter 11 template-walk fix.

The iter 11 fix corrected the archetype builder, but `evaluate_vs_meta` uses
`build_faction_random_army` with `use_archetype=False`. Random fill at 1000pt
appears to never produce Rubric Marines (squad-max 540pt > 50% cap=500pt) or
Scarab Occult Terminators (891pt > cap), and Magnus the Red (435pt < cap) is
selected uniformly so rarely appears as the centerpiece.

This script runs 30 vanilla random_fill battles TSON vs Marines, DG, Necrons
and reports:
  * TSON composition profile (what units are picked)
  * Magnus/Ahriman start counts per battle
  * Rubric / Scarab Occult start counts per battle
  * Cabal Ritual stratagem firings (Doombolt, Cabbalistic Empowerment,
    Twist of Fate, Glamour of Tzeentch)
  * TSON unit deaths per round
  * VP / kill / damage exchanges

Read-only — does NOT modify catalogue, simulator, or strategy code.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter12_tson_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter12_tson_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import StratagemFired, UnitKilled, RoundStarted
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS: List[str] = [
    "Adeptus Astartes",
    "Death Guard",
    "Necrons",
]
TSON = "Thousand Sons"
N_BATTLES = 30
POINTS = 1000

TRACK_PROFILES = {
    "Magnus the Red",
    "Ahriman",
    "Rubric Marines",
    "Scarab Occult Terminators",
    "Exalted Sorcerer",
    "Infernal Master",
    "Kairos Fateweaver",
    "Lord of Change",
    "Daemon Prince of Tzeentch",
    "Daemon Prince of Tzeentch with wings",
    "Tzaangors",
    "Helbrute",
}


class DiagSub:
    def __init__(self) -> None:
        self.doombolt = 0
        self.cabbalistic = 0
        self.twist = 0
        self.glamour = 0
        self.destiny = 0
        self.temporal = 0
        self.tson_deaths_by_round: Dict[int, int] = defaultdict(int)
        self.opp_deaths_by_round: Dict[int, int] = defaultdict(int)
        self.current_round = 0
        self.tson_uids: set = set()

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, StratagemFired):
            n = e.stratagem_name
            if n == "Doombolt":
                self.doombolt += 1
            elif n == "Cabbalistic Empowerment":
                self.cabbalistic += 1
            elif n == "Twist of Fate":
                self.twist += 1
            elif n == "Glamour of Tzeentch":
                self.glamour += 1
            elif n == "Destiny's Ruin":
                self.destiny += 1
            elif n == "Temporal Surge":
                self.temporal += 1
        elif isinstance(e, UnitKilled):
            if e.unit_uid in self.tson_uids:
                self.tson_deaths_by_round[self.current_round] += 1
            else:
                self.opp_deaths_by_round[self.current_round] += 1


def _count_total_by_profile(army) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for u in army.units:
        out[u.profile.name] += 1
    return out


def _count_alive_by_profile(army) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for u in army.units:
        if u.is_alive:
            out[u.profile.name] += 1
    return out


def run_matchup(opponent: str) -> Dict:
    wins = Counter()
    rounds_played: List[int] = []
    doombolts: List[int] = []
    cabbalistics: List[int] = []
    twists: List[int] = []
    glamours: List[int] = []
    destinys: List[int] = []
    temporals: List[int] = []
    tson_total_strat: List[int] = []
    a_pts: List[float] = []
    b_pts: List[float] = []

    start_by_prof: Dict[str, int] = defaultdict(int)
    survive_by_prof: Dict[str, int] = defaultdict(int)

    composition_examples: List[str] = []

    deaths_by_round_acc: Dict[int, List[int]] = defaultdict(list)
    opp_deaths_by_round_acc: Dict[int, List[int]] = defaultdict(list)

    for s in range(N_BATTLES):
        # Mirror evaluate_vs_meta's seeding so we observe the same armies.
        rng = random.Random(s)
        tson = build_faction_random_army(
            "A", TSON, POINTS,
            rng=rng,
            use_archetype=False,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(s + 10000),
            use_archetype=False,
        )
        if not tson.units or not opp.units:
            continue

        sub = DiagSub()
        sub.tson_uids = {u.uid for u in tson.units}
        battle = Battle(tson, opp, map_=DEFAULT_MAP, subscribers=[sub])
        r = battle.run()

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        doombolts.append(sub.doombolt)
        cabbalistics.append(sub.cabbalistic)
        twists.append(sub.twist)
        glamours.append(sub.glamour)
        destinys.append(sub.destiny)
        temporals.append(sub.temporal)
        tson_total_strat.append(
            sub.doombolt + sub.cabbalistic + sub.twist
            + sub.glamour + sub.destiny + sub.temporal
        )
        a_pts.append(sum(u.profile.points_cost for u in tson.units))
        b_pts.append(sum(u.profile.points_cost for u in opp.units))

        # Composition snapshot for first 3 battles
        if s < 3:
            cts = Counter(u.profile.name for u in tson.units)
            composition_examples.append(
                f"battle {s}: " + ", ".join(f"{c}x {n}" for n, c in cts.most_common())
            )

        for r_num, d in sub.tson_deaths_by_round.items():
            deaths_by_round_acc[r_num].append(d)
        for r_num, d in sub.opp_deaths_by_round.items():
            opp_deaths_by_round_acc[r_num].append(d)

        starts = _count_total_by_profile(tson)
        survives = _count_alive_by_profile(tson)
        for pn, n in starts.items():
            start_by_prof[pn] += n
        for pn, n in survives.items():
            survive_by_prof[pn] += n

    a_wr = wins.get("A", 0) / max(1, N_BATTLES) * 100
    return {
        "opponent": opponent,
        "a_wr": a_wr,
        "rounds_mean": statistics.mean(rounds_played) if rounds_played else 0.0,
        "doombolt_mean": statistics.mean(doombolts) if doombolts else 0.0,
        "cabbalistic_mean": statistics.mean(cabbalistics) if cabbalistics else 0.0,
        "twist_mean": statistics.mean(twists) if twists else 0.0,
        "glamour_mean": statistics.mean(glamours) if glamours else 0.0,
        "destiny_mean": statistics.mean(destinys) if destinys else 0.0,
        "temporal_mean": statistics.mean(temporals) if temporals else 0.0,
        "tson_strat_total_mean": statistics.mean(tson_total_strat) if tson_total_strat else 0.0,
        "a_pts_mean": statistics.mean(a_pts) if a_pts else 0.0,
        "b_pts_mean": statistics.mean(b_pts) if b_pts else 0.0,
        "comp_examples": composition_examples,
        "tracked_start": {
            pn: start_by_prof.get(pn, 0) / max(1, N_BATTLES)
            for pn in TRACK_PROFILES
        },
        "tracked_survival": {
            pn: (survive_by_prof.get(pn, 0) / max(1, start_by_prof.get(pn, 1)) * 100)
                if start_by_prof.get(pn, 0) > 0 else None
            for pn in TRACK_PROFILES
        },
        "deaths_by_round": {
            r: statistics.mean(v) if v else 0.0
            for r, v in deaths_by_round_acc.items()
        },
        "opp_deaths_by_round": {
            r: statistics.mean(v) if v else 0.0
            for r, v in opp_deaths_by_round_acc.items()
        },
    }


def main() -> None:
    print(f"=== iter12 TSON diagnostic — random_fill (use_archetype=False), N={N_BATTLES} ===")
    print(f"{'Opponent':22s} {'WR%':>5s} {'R':>4s} {'DB':>5s} {'CE':>5s} {'TF':>5s} {'GT':>5s} {'TSON pts':>9s} {'opp pts':>9s}")
    print("-" * 90)

    results: List[Dict] = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        results.append(r)
        print(f"{opp:22s} {r['a_wr']:5.1f} {r['rounds_mean']:4.1f} "
              f"{r['doombolt_mean']:5.2f} {r['cabbalistic_mean']:5.2f} "
              f"{r['twist_mean']:5.2f} {r['glamour_mean']:5.2f} "
              f"{r['a_pts_mean']:9.0f} {r['b_pts_mean']:9.0f}")

    print()
    print(f"Mean TSON WR vs {len(OPPONENTS)} opponents: {statistics.mean(r['a_wr'] for r in results):.1f}%")
    print()

    print("=== Per-matchup detail ===")
    for r in results:
        print(f"\nvs {r['opponent']}  WR={r['a_wr']:.1f}%, rounds={r['rounds_mean']:.1f}")
        print(f"  Cabal Rituals fired/battle: DB={r['doombolt_mean']:.2f} CE={r['cabbalistic_mean']:.2f} "
              f"TF={r['twist_mean']:.2f} GT={r['glamour_mean']:.2f} "
              f"DR={r['destiny_mean']:.2f} TS={r['temporal_mean']:.2f}")
        print(f"  TSON total strats/battle: {r['tson_strat_total_mean']:.2f}")
        print(f"  Tracked profile start counts (per battle) & survival:")
        for pn in sorted(TRACK_PROFILES):
            sc = r["tracked_start"].get(pn, 0.0)
            sv = r["tracked_survival"].get(pn)
            if sc > 0:
                print(f"    {pn:38s} start={sc:4.2f}/battle  survive={sv:5.1f}%")
            else:
                print(f"    {pn:38s} start=0 (never seeded)")
        print(f"  Compositions (first 3 battles):")
        for c in r["comp_examples"]:
            print(f"    {c}")
        print(f"  TSON deaths by round: " + ", ".join(
            f"R{k}={v:.1f}" for k, v in sorted(r["deaths_by_round"].items())))
        print(f"  Opp deaths by round:  " + ", ".join(
            f"R{k}={v:.1f}" for k, v in sorted(r["opp_deaths_by_round"].items())))


if __name__ == "__main__":
    main()
