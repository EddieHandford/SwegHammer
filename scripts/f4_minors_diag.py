"""
F4 Minor-outlier diagnostic — 5 factions with archetype-eval residuals <10pt.

Eval-vs-meta (archetype=True) puts:
  * Necrons        +8.7
  * Death Guard    +8.9
  * Orks           -5.3
  * Adeptus Custodes  -3.9
  * T'au Empire    -4.9

Brief secondary-outlier diagnostic. N=20 seeded battles per matchup
(focus faction vs each of the 9 other archetype-enabled factions, 1000 pts,
archetype=True on both sides, seeds 9001-9020). Per matchup capture:

  * A-WR
  * Stratagem firing counts (focus army only)
  * Per-profile start counts + survival rates

Read-only. Pure diagnostic.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.f4_minors_diag
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
        [sys.executable, "-m", "scripts.f4_minors_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleshockFailed,
    RoundStarted,
    StratagemFired,
    UnitKilled,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS_ALL: List[str] = [
    "Adeptus Astartes",
    "Necrons",
    "Aeldari",
    "Tyranids",
    "Orks",
    "T'au Empire",
    "Death Guard",
    "Adeptus Custodes",
    "Thousand Sons",
    "Leagues of Votann",
]
N_BATTLES = 20
POINTS = 1000

FOCUS_FACTIONS = [
    "Necrons",
    "Death Guard",
    "Orks",
    "Adeptus Custodes",
    "T'au Empire",
]

# Tracked profile names per faction (substring match is OK)
TRACK = {
    "Necrons": {
        "Necron Warriors", "Immortals", "Lychguard", "Triarch Praetorians",
        "Catacomb Command Barge", "Overlord", "Cryptek", "Doomstalker",
    },
    "Death Guard": {
        "Plague Marines", "Poxwalkers", "Death Guard Terminator",
        "Foul Blightspawn", "Lord of Virulence", "Plague Surgeon",
        "Plagueburst Crawler", "Myphitic Blight-hauler", "Biologus Putrifier",
    },
    "Orks": {
        "Boyz", "Nobz", "Gretchin", "Meganobz", "Warboss",
        "Killa Kans", "Deff Dread", "Boomdakka Snazzwagon", "Painboy",
    },
    "Adeptus Custodes": {
        "Custodian Guard", "Custodian Wardens", "Allarus Custodians",
        "Sagittarum Custodians", "Vexilus Praetor", "Shield-Captain",
        "Witchseeker Squad", "Prosecutor", "Dawneagle Jetbike",
    },
    "T'au Empire": {
        "Strike Team", "Breacher Team", "Pathfinder Team",
        "Crisis Battlesuit", "Stealth Battlesuits",
        "Hammerhead Gunship", "Devilfish", "Riptide", "Ethereal",
        "Commander", "Broadside",
    },
}


class DiagSub:
    """Per-battle event capture for one focus faction."""

    def __init__(self, focus_army_name: str) -> None:
        self.focus_army = focus_army_name
        self.stratagem_fires: Counter = Counter()
        self.killed_uids: set = set()
        self.bs_failures: Counter = Counter()  # by army name
        self.round_num = 0

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.round_num = e.round_num
        elif isinstance(e, StratagemFired):
            if e.army_name == self.focus_army:
                self.stratagem_fires[e.stratagem_name] += 1
        elif isinstance(e, BattleshockFailed):
            # uid prefix: A0,A1... = focus army A; B0,B1... = opponent
            side = "A" if e.unit_uid.startswith("A") else "B"
            self.bs_failures[side] += 1
        elif isinstance(e, UnitKilled):
            self.killed_uids.add(e.unit_uid)


def _count_by_profile(army, alive_only: bool) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for u in army.units:
        if alive_only and not u.is_alive:
            continue
        out[u.profile.name] += 1
    return out


def run_matchup(focus_faction: str, opponent: str) -> Dict:
    wins: Counter = Counter()
    rounds_played: List[int] = []
    strat_per_battle: List[Counter] = []
    bs_focus_per_battle: List[int] = []
    bs_opp_per_battle: List[int] = []
    start_by_prof: Dict[str, int] = defaultdict(int)
    survive_by_prof: Dict[str, int] = defaultdict(int)
    focus_final_vp: List[int] = []
    opp_final_vp: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 9001
        random.seed(seed)
        focus = build_faction_random_army(
            "A", focus_faction, POINTS,
            rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(seed + 40000),
            use_archetype=True,
        )
        if not focus.units or not opp.units:
            continue

        sub = DiagSub("A")
        battle = Battle(focus, opp, map_=DEFAULT_MAP, subscribers=[sub])
        r = battle.run()

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        strat_per_battle.append(sub.stratagem_fires)
        bs_focus_per_battle.append(sub.bs_failures.get("A", 0))
        bs_opp_per_battle.append(sub.bs_failures.get("B", 0))
        focus_final_vp.append(getattr(focus, "victory_points", 0))
        opp_final_vp.append(getattr(opp, "victory_points", 0))

        for pname, n in _count_by_profile(focus, alive_only=False).items():
            start_by_prof[pname] += n
        for pname, n in _count_by_profile(focus, alive_only=True).items():
            survive_by_prof[pname] += n

    a_wr = wins.get("A", 0) / max(1, N_BATTLES) * 100
    total_strats: Counter = Counter()
    for c in strat_per_battle:
        total_strats.update(c)
    mean_strats: Dict[str, float] = {
        k: v / max(1, N_BATTLES) for k, v in total_strats.items()
    }
    tracked = TRACK.get(focus_faction, set())
    survival = {
        pname: (
            survive_by_prof.get(pname, 0)
            / max(1, start_by_prof.get(pname, 1))
            * 100
        )
        for pname in tracked
        if start_by_prof.get(pname, 0) > 0
    }
    start_counts = {
        pname: start_by_prof.get(pname, 0) / max(1, N_BATTLES)
        for pname in tracked
        if start_by_prof.get(pname, 0) > 0
    }
    missing = [pname for pname in tracked if start_by_prof.get(pname, 0) == 0]

    return {
        "focus": focus_faction,
        "opponent": opponent,
        "a_wr": a_wr,
        "rounds_mean": statistics.mean(rounds_played) if rounds_played else 0.0,
        "strats_per_battle": mean_strats,
        "bs_focus_mean": statistics.mean(bs_focus_per_battle) if bs_focus_per_battle else 0.0,
        "bs_opp_mean": statistics.mean(bs_opp_per_battle) if bs_opp_per_battle else 0.0,
        "focus_vp_mean": statistics.mean(focus_final_vp) if focus_final_vp else 0.0,
        "opp_vp_mean": statistics.mean(opp_final_vp) if opp_final_vp else 0.0,
        "tracked_survival": survival,
        "tracked_start_counts": start_counts,
        "tracked_missing": missing,
    }


def run_focus(focus_faction: str) -> List[Dict]:
    print(f"\n=== Focus: {focus_faction} ===")
    print(f"{'Opponent':22s}  {'WR%':>5s}  {'R':>4s}  {'VP A':>6s}  {'VP B':>6s}")
    print("-" * 60)
    results: List[Dict] = []
    for opp in OPPONENTS_ALL:
        if opp == focus_faction:
            continue
        r = run_matchup(focus_faction, opp)
        results.append(r)
        print(f"{opp:22s}  {r['a_wr']:5.1f}  {r['rounds_mean']:4.1f}  "
              f"{r['focus_vp_mean']:6.1f}  {r['opp_vp_mean']:6.1f}")
    mean_wr = statistics.mean(r["a_wr"] for r in results)
    print("-" * 60)
    print(f"Mean WR: {mean_wr:.1f}%")
    return results


def report_one(results: List[Dict]) -> None:
    focus = results[0]["focus"]
    results_sorted = sorted(results, key=lambda r: r["a_wr"])
    print(f"\n=== {focus} — worst 2 matchups detail ===")
    for r in results_sorted[:2]:
        print(f"\n  vs {r['opponent']}  WR={r['a_wr']:.1f}%  rounds={r['rounds_mean']:.1f}  "
              f"VP {r['focus_vp_mean']:.1f}/{r['opp_vp_mean']:.1f}")
        print(f"    BS-fails: focus={r['bs_focus_mean']:.2f}  opp={r['bs_opp_mean']:.2f}")
        if r["strats_per_battle"]:
            print(f"    stratagems/battle:")
            for k, v in sorted(r["strats_per_battle"].items(), key=lambda x: -x[1])[:6]:
                print(f"      {k:35s} {v:5.2f}")
        else:
            print(f"    stratagems/battle: (none)")
        if r["tracked_survival"]:
            print(f"    tracked profile survival:")
            for pname in sorted(r["tracked_survival"]):
                sv = r["tracked_survival"][pname]
                st = r["tracked_start_counts"].get(pname, 0.0)
                print(f"      {pname:35s} {sv:5.1f}%  (start {st:.1f}/battle)")
        if r["tracked_missing"]:
            print(f"    NEVER SEEDED: {', '.join(r['tracked_missing'])}")


def main() -> None:
    all_results: Dict[str, List[Dict]] = {}
    for f in FOCUS_FACTIONS:
        all_results[f] = run_focus(f)
    for f in FOCUS_FACTIONS:
        report_one(all_results[f])


if __name__ == "__main__":
    main()
