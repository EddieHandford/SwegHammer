"""
Thousand Sons vanilla-10e diagnostic — why does TSON sit at WR 49.4% (real-meta
54.6%) under the new vanilla simulator default?

Runs 30 seeded vanilla-10e battles per matchup (TSON vs Marines, Necrons,
Aeldari). Captures three hypotheses:

  H_CabalEcon       — track CP-equivalent "cabal" spend. The four Cult of
                       Magic stratagems (Doombolt, Cabbalistic Empowerment,
                       Twist of Fate, Glamour of Tzeentch) share the army's
                       global CP pool. Count fires per round and CP balance
                       at end-of-round, to confirm whether TSON runs the pool
                       dry by R2 — which would starve Doombolt for R3-5.

  H_DoombboltFires  — Doombolt fires from `_apply_detachment_stratagems` at
                       round start. Should fire every round (R1-5) if CP and
                       a psyker are alive. Count fires per battle and compute
                       fire-rate per round.

  H_RubricsSurvival — Rubric Marines are TSON's primary anchor unit. With
                       T4 W2 + 5++ invuln they should be tanky into the
                       late game. Track Rubric survival rate at end-of-battle.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.tson_vanilla_diag

Read-only — does not modify catalogue, simulator, or strategy code.
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
        [sys.executable, "-m", "scripts.tson_vanilla_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    RoundStarted,
    RoundEnded,
    StratagemFired,
    UnitKilled,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle, RulesConfig

OPPONENTS: List[str] = [
    "Adeptus Astartes",
    "Necrons",
    "Aeldari",
]
TSON = "Thousand Sons"
N_BATTLES = 30
POINTS = 1000

CULT_STRATS = {
    "Doombolt",
    "Cabbalistic Empowerment",
    "Twist of Fate",
    "Glamour of Tzeentch",
}

TRACK_PROFILES = {
    "Rubric Marines",
    "Scarab Occult Terminators",
    "Tzaangors",
    "Exalted Sorcerer",
    "Infernal Master",
}


class DiagSubscriber:
    """Captures per-battle events of interest."""

    def __init__(self) -> None:
        self.current_round = 0
        # Stratagem fires (TSON side) per round
        self.fires_per_round: Dict[int, Counter] = defaultdict(Counter)
        self.doombolt_fires_per_round: Counter = Counter()
        # UnitKilled events — uid → round it died in (TSON unit fates)
        self.unit_death_round: Dict[str, int] = {}
        self.tson_army_name: str = "A"

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, StratagemFired):
            if e.army_name == self.tson_army_name and e.stratagem_name in CULT_STRATS:
                self.fires_per_round[self.current_round][e.stratagem_name] += 1
                if e.stratagem_name == "Doombolt":
                    self.doombolt_fires_per_round[self.current_round] += 1
        elif isinstance(e, UnitKilled):
            if e.unit_uid not in self.unit_death_round:
                self.unit_death_round[e.unit_uid] = self.current_round


def run_matchup(opponent: str) -> Dict:
    wins = Counter()
    rounds_played: List[int] = []

    # H_DoombboltFires accumulators: doombolt fires count per battle, and
    # per-round fire-rate (battles where doombolt fired in round R).
    doombolts_total: List[int] = []
    fired_in_round: Counter = Counter()    # round_num -> count of battles
    battle_count = 0

    # H_CabalEcon accumulators: total cult stratagem CP spent per battle,
    # plus end-of-battle CP remaining on TSON.
    cult_cp_spent: List[int] = []
    cp_remaining_end: List[int] = []
    cp_spent_r1_r2: List[int] = []    # CP used in rounds 1-2 (early spend)
    cp_spent_r3_r5: List[int] = []    # CP used in rounds 3-5 (late spend)

    # H_RubricsSurvival: per-profile survival snapshot
    start_by_prof: Dict[str, int] = defaultdict(int)
    survive_by_prof: Dict[str, int] = defaultdict(int)

    for s in range(N_BATTLES):
        seed = s + 9001
        random.seed(seed)
        tson = build_faction_random_army(
            "A", TSON, POINTS,
            rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not tson.units or not opp.units:
            continue

        sub = DiagSubscriber()
        sub.tson_army_name = "A"
        # Explicit vanilla 10e mode (this is the simulator default after
        # #ddb44db, but pass it through for clarity).
        battle = Battle(
            tson, opp,
            map_=DEFAULT_MAP,
            subscribers=[sub],
            rules=RulesConfig.vanilla_10e(),
        )
        r = battle.run()

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        battle_count += 1

        # Doombolt fire counting
        db_total = sum(sub.doombolt_fires_per_round.values())
        doombolts_total.append(db_total)
        for rd in sorted(sub.doombolt_fires_per_round):
            if sub.doombolt_fires_per_round[rd] > 0:
                fired_in_round[rd] += 1

        # CP-economy accounting (cabal-equivalent on the global CP pool).
        # Each cult stratagem costs 1 CP (Glamour costs 2, the rest cost 1).
        # We sum per-round CP-equivalent spend so we can show the round-1/2
        # spike vs round-3/4/5 starve.
        early = 0
        late = 0
        for rd, fires in sub.fires_per_round.items():
            for name, n in fires.items():
                cost = 2 if name == "Glamour of Tzeentch" else 1
                if rd <= 2:
                    early += cost * n
                else:
                    late += cost * n
        cult_cp_spent.append(early + late)
        cp_spent_r1_r2.append(early)
        cp_spent_r3_r5.append(late)
        cp_remaining_end.append(tson.command_points)

        # Per-profile survival
        for u in tson.units:
            start_by_prof[u.profile.name] += 1
            if u.is_alive:
                survive_by_prof[u.profile.name] += 1

    a_wr = wins.get("A", 0) / max(1, N_BATTLES) * 100

    # Per-round Doombolt fire rate as fraction of battles that reached that round
    doombolt_fire_rate = {
        rd: fired_in_round[rd] / max(1, battle_count) * 100
        for rd in range(1, 6)
    }

    out = {
        "opponent": opponent,
        "a_wr": a_wr,
        "rounds_mean": statistics.mean(rounds_played) if rounds_played else 0.0,
        # H_DoombboltFires
        "doombolt_fires_per_battle": (
            statistics.mean(doombolts_total) if doombolts_total else 0.0
        ),
        "doombolt_fire_rate_by_round": doombolt_fire_rate,
        # H_CabalEcon
        "cult_cp_spent_per_battle": (
            statistics.mean(cult_cp_spent) if cult_cp_spent else 0.0
        ),
        "cult_cp_spent_r1_r2": (
            statistics.mean(cp_spent_r1_r2) if cp_spent_r1_r2 else 0.0
        ),
        "cult_cp_spent_r3_r5": (
            statistics.mean(cp_spent_r3_r5) if cp_spent_r3_r5 else 0.0
        ),
        "cp_remaining_end": (
            statistics.mean(cp_remaining_end) if cp_remaining_end else 0.0
        ),
        # H_RubricsSurvival
        "tracked_survival": {
            pname: (
                survive_by_prof.get(pname, 0)
                / max(1, start_by_prof.get(pname, 1))
                * 100
            )
            for pname in TRACK_PROFILES
            if start_by_prof.get(pname, 0) > 0
        },
        "tracked_start_counts": {
            pname: start_by_prof.get(pname, 0) / max(1, N_BATTLES)
            for pname in TRACK_PROFILES
            if start_by_prof.get(pname, 0) > 0
        },
    }
    return out


def main() -> None:
    print(
        f"=== TSON vanilla-10e diagnostic — {N_BATTLES} battles "
        f"per matchup, archetype=True ==="
    )
    print(
        f"{'Opponent':22s}  {'WR%':>5s}  {'R':>4s}  "
        f"{'DB/btl':>6s}  {'CP-cult':>7s}  {'CP-end':>6s}"
    )
    print("-" * 70)

    results: List[Dict] = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        results.append(r)
        print(
            f"{r['opponent']:22s}  {r['a_wr']:5.1f}  {r['rounds_mean']:4.1f}  "
            f"{r['doombolt_fires_per_battle']:6.2f}  "
            f"{r['cult_cp_spent_per_battle']:7.2f}  "
            f"{r['cp_remaining_end']:6.2f}"
        )

    mean_wr = statistics.mean(r["a_wr"] for r in results)
    print("-" * 70)
    print(f"Mean TSON win-rate (vs 3 opponents): {mean_wr:.1f}%")
    print()

    # Per-matchup detail
    for r in results:
        print(f"\nvs {r['opponent']}  (WR {r['a_wr']:.1f}%)")
        print(f"  rounds avg: {r['rounds_mean']:.1f}")
        print(
            f"  H_CabalEcon: cult-CP spent/battle = "
            f"{r['cult_cp_spent_per_battle']:.2f} "
            f"(R1-2 {r['cult_cp_spent_r1_r2']:.2f} / "
            f"R3-5 {r['cult_cp_spent_r3_r5']:.2f}); "
            f"CP-end {r['cp_remaining_end']:.2f}"
        )
        print(
            f"  H_DoombboltFires: total/battle "
            f"{r['doombolt_fires_per_battle']:.2f}; "
            f"per-round fire-rate (R1-5) = "
            + ", ".join(
                f"R{rd}={r['doombolt_fire_rate_by_round'].get(rd, 0):.0f}%"
                for rd in range(1, 6)
            )
        )
        print(f"  H_RubricsSurvival (and other anchors):")
        for pname in sorted(r["tracked_survival"]):
            sv = r["tracked_survival"][pname]
            stcnt = r["tracked_start_counts"].get(pname, 0.0)
            print(
                f"    {pname:35s} {sv:5.1f}%  (start {stcnt:.1f} models/battle)"
            )

    # Aggregate hypothesis numbers
    print("\n=== Aggregate hypothesis numbers ===")
    agg_db = statistics.mean(r["doombolt_fires_per_battle"] for r in results)
    agg_cult_cp = statistics.mean(r["cult_cp_spent_per_battle"] for r in results)
    agg_cp_end = statistics.mean(r["cp_remaining_end"] for r in results)
    print(f"H_DoombboltFires  : Doombolt fires/battle (mean across matchups) = {agg_db:.2f}")
    print(f"H_CabalEcon       : Cult-stratagem CP spent/battle             = {agg_cult_cp:.2f}")
    print(f"H_CabalEcon       : CP remaining at end of battle (TSON)        = {agg_cp_end:.2f}")
    # Aggregate Rubrics survival across matchups
    rubrics_sv: List[float] = []
    for r in results:
        if "Rubric Marines" in r["tracked_survival"]:
            rubrics_sv.append(r["tracked_survival"]["Rubric Marines"])
    if rubrics_sv:
        print(
            f"H_RubricsSurvival : Rubric Marines survival rate (mean)        "
            f"= {statistics.mean(rubrics_sv):.1f}%"
        )


if __name__ == "__main__":
    main()
