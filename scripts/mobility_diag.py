"""
F3 Mobility-faction archetype diagnostic — Marines / Aeldari / Votann.

Eval-vs-meta (archetype=True) puts:
  * Adeptus Astartes (Gladius Strike Force)  +22 pts above real WR
  * Aeldari (Battle Host)                    -11 pts under real WR
  * Leagues of Votann (Oathband)             -12 pts under real WR

Three different problems. This script runs N=30 seeded battles per matchup
(focus-faction vs each of the 9 other archetype-enabled factions) and captures:
  * A-WR
  * Stratagem firing counts (per faction-specific list)
  * Oath of Moment target choices (Marines)
  * Battle Focus token spend (Aeldari)
  * Judgement Tokens awarded (Votann opponents)
  * Per-profile start counts + survival rates

Read-only — does NOT modify catalogue, simulator, strategy, or archetypes.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.mobility_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.mobility_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleshockFailed,
    JudgementTokenAwarded,
    OathTargetChosen,
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
N_BATTLES = 30
POINTS = 1000

FOCUS_FACTIONS = ["Adeptus Astartes", "Aeldari", "Leagues of Votann"]

# Tracked profile names per faction (loose match — substring is ok)
TRACK = {
    "Adeptus Astartes": {
        "Intercessor Squad", "Hellblaster Squad", "Eradicator Squad",
        "Aggressor Squad", "Captain in Terminator Armour", "Apothecary",
        "Repulsor",
    },
    "Aeldari": {
        "Dire Avengers", "Guardian Defenders", "Rangers", "Fire Dragons",
        "Wraithguard", "Farseer", "Autarch", "Wave Serpent", "Falcon",
    },
    "Leagues of Votann": {
        "Hearthkyn Warriors", "Einhyr Hearthguard", "Hernkyn Pioneers",
        "Cthonian Beserks", "Brôkhyr Iron-master", "Sagitaur",
        "Hekaton Land Fortress",
    },
}


class DiagSub:
    """Per-battle event capture for one focus faction."""

    def __init__(self, focus_army_name: str) -> None:
        self.focus_army = focus_army_name
        self.stratagem_fires: Counter = Counter()
        self.oath_targets: List[str] = []
        self.judgement_awards: List[int] = []   # total_tokens at each award
        self.killed_uids: set = set()
        self.round_num = 0
        # Heuristic for "battle focus spent": ASURYANI advance counted
        # is hard to wire here, so we instead snapshot army.battle_focus_tokens
        # after each round in a separate hook — see run_matchup.

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.round_num = e.round_num
        elif isinstance(e, StratagemFired):
            if e.army_name == self.focus_army:
                self.stratagem_fires[e.stratagem_name] += 1
        elif isinstance(e, OathTargetChosen):
            if e.army_name == self.focus_army:
                self.oath_targets.append(e.target_uid)
        elif isinstance(e, JudgementTokenAwarded):
            self.judgement_awards.append(e.total_tokens)
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
    oath_counts: List[int] = []
    bf_spent_per_battle: List[int] = []
    judgement_total_per_battle: List[int] = []
    judgement_max_per_battle: List[int] = []
    start_by_prof: Dict[str, int] = defaultdict(int)
    survive_by_prof: Dict[str, int] = defaultdict(int)

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

        # Aeldari Battle Focus is pre-set per round inside _on_command_phase
        # to 4 tokens; capture the running spend by snapshotting at battle start
        # and after each round end. We don't have a hook for round-end here,
        # so we read tokens_remaining at end of battle and infer "tokens spent
        # across all rounds" as (4 * rounds_played - tokens_remaining_at_end).
        # NB: tokens reset to 4 each command phase, so a more honest metric is
        # to add a per-round capture. For lightweight diag we instead estimate
        # via the simulator counter — see post-battle snapshot.

        sub = DiagSub("A")
        battle = Battle(focus, opp, map_=DEFAULT_MAP, subscribers=[sub])
        r = battle.run()

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        strat_per_battle.append(sub.stratagem_fires)
        oath_counts.append(len(sub.oath_targets))
        judgement_total_per_battle.append(len(sub.judgement_awards))
        judgement_max_per_battle.append(
            max(sub.judgement_awards) if sub.judgement_awards else 0
        )

        # Battle Focus spend reconstruction (Aeldari only). The simulator
        # resets tokens to 4 at the start of every command phase (line 213).
        # So per-round spend = 4 - tokens_at_end_of_round. Without a per-round
        # snapshot we report (focus.battle_focus_tokens at end) as a single
        # snapshot — 4 means "didn't spend this round", <4 means "spent some".
        bf_spent_per_battle.append(4 - getattr(focus, "battle_focus_tokens", 4))

        for pname, n in _count_by_profile(focus, alive_only=False).items():
            start_by_prof[pname] += n
        for pname, n in _count_by_profile(focus, alive_only=True).items():
            survive_by_prof[pname] += n

    a_wr = wins.get("A", 0) / max(1, N_BATTLES) * 100
    # Aggregate stratagem fires across battles
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
        "oath_targets_mean": statistics.mean(oath_counts) if oath_counts else 0.0,
        "bf_spent_last_round_mean": statistics.mean(bf_spent_per_battle) if bf_spent_per_battle else 0.0,
        "judgement_events_mean": statistics.mean(judgement_total_per_battle) if judgement_total_per_battle else 0.0,
        "judgement_max_mean": statistics.mean(judgement_max_per_battle) if judgement_max_per_battle else 0.0,
        "tracked_survival": survival,
        "tracked_start_counts": start_counts,
        "tracked_missing": missing,
    }


def run_focus(focus_faction: str) -> List[Dict]:
    print(f"\n=== Focus: {focus_faction} ===")
    print(f"{'Opponent':22s}  {'WR%':>5s}  {'R':>4s}")
    print("-" * 50)
    results: List[Dict] = []
    for opp in OPPONENTS_ALL:
        if opp == focus_faction:
            continue
        r = run_matchup(focus_faction, opp)
        results.append(r)
        print(f"{opp:22s}  {r['a_wr']:5.1f}  {r['rounds_mean']:4.1f}")
    mean_wr = statistics.mean(r["a_wr"] for r in results)
    print("-" * 50)
    print(f"Mean WR: {mean_wr:.1f}%")
    return results


def report_one(results: List[Dict]) -> None:
    focus = results[0]["focus"]
    results_sorted = sorted(results, key=lambda r: r["a_wr"])
    print(f"\n=== {focus} — bottom 3 matchups detail ===")
    for r in results_sorted[:3]:
        print(f"\n  vs {r['opponent']}  WR={r['a_wr']:.1f}%  rounds={r['rounds_mean']:.1f}")
        if r["strats_per_battle"]:
            print(f"    stratagems/battle:")
            for k, v in sorted(r["strats_per_battle"].items(), key=lambda x: -x[1])[:8]:
                print(f"      {k:35s} {v:5.2f}")
        else:
            print(f"    stratagems/battle: (none)")
        if focus == "Adeptus Astartes":
            print(f"    Oath targets chosen/battle: {r['oath_targets_mean']:.2f}")
        if focus == "Aeldari":
            print(f"    Battle Focus tokens spent last round (mean): {r['bf_spent_last_round_mean']:.2f}/4")
        if focus == "Leagues of Votann":
            print(f"    Judgement Token award events/battle: {r['judgement_events_mean']:.2f}")
            print(f"    Max Judgement stack on any enemy unit (mean): {r['judgement_max_mean']:.2f}")
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
