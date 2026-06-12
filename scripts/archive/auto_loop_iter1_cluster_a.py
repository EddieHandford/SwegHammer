"""Auto-loop iter 1 — Cluster A over-performer mechanism trace.

Run 30 archetype battles per (over_perform_faction, opponent) triple for the
four over-performers (Death Guard, Marines, Tyranids, Necrons). Per battle,
capture damage in/out, kills by phase, VP, and stratagems fired.

Read-only — no catalogue / strategy / simulator mutation. Output is a
markdown table to stdout, parsed by the human into the analysis doc.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.auto_loop_iter1_cluster_a

Hard-cap: N=30, three opponents per faction. Never runs the eval suite.
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.auto_loop_iter1_cluster_a"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleEnded,
    ObjectiveScored,
    RoundEnded,
    RoundStarted,
    StratagemFired,
    UnitFought,
    UnitKilled,
    UnitReanimated,
    UnitShot,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle

# Per task: 4 over-performers vs 3 informative opponents each.
TARGETS: Dict[str, List[str]] = {
    "Death Guard": ["Adeptus Astartes", "Tyranids", "T'au Empire"],
    "Adeptus Astartes": ["Necrons", "Tyranids", "T'au Empire"],
    "Tyranids": ["Adeptus Astartes", "T'au Empire", "Aeldari"],
    "Necrons": ["Adeptus Astartes", "Aeldari", "T'au Empire"],
}
N_BATTLES = 30
POINTS = 1000


class TraceSub:
    """Collect per-side aggregates for one battle."""

    def __init__(self, fac_army: str, opp_army: str) -> None:
        self.fac_army = fac_army
        self.opp_army = opp_army
        self.current_round = 0
        # damage emitted: damage TO the listed defender army each round
        self.dmg_dealt_fac: List[float] = [0.0] * 6   # by round 0..5
        self.dmg_dealt_opp: List[float] = [0.0] * 6
        # kills inflicted by side, per round
        self.kills_by_fac_round: List[int] = [0] * 6
        self.kills_by_opp_round: List[int] = [0] * 6
        # uid -> army name (filled at battle build time)
        self.uid_army: Dict[str, str] = {}
        # stratagems fired by each side (name -> count)
        self.fac_strats: Counter = Counter()
        self.opp_strats: Counter = Counter()
        # VP after each RoundEnded
        self.last_a_vp = 0
        self.last_b_vp = 0
        self.fac_is_a: bool = True
        # reanimations (for necron read-out)
        self.reanims = 0
        # most recent attacker per UnitShot/Fought event (since UnitKilled
        # has no attacker info, we attribute the kill to the side whose
        # attack just landed)
        self._last_attacker_army: str | None = None
        self._last_attacker_round: int = 0

    def set_armies(self, a_uids: List[str], b_uids: List[str],
                   fac_is_a: bool, a_name: str, b_name: str) -> None:
        self.fac_is_a = fac_is_a
        for u in a_uids:
            self.uid_army[u] = a_name
        for u in b_uids:
            self.uid_army[u] = b_name

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, UnitShot):
            self._record_attack(e.attacker_uid, e.target_uid, e.damage,
                                e.target_alive_after)
        elif isinstance(e, UnitFought):
            self._record_attack(e.attacker_uid, e.target_uid, e.damage,
                                e.target_alive_after)
        elif isinstance(e, UnitKilled):
            # attribute to last attacker if same round
            atk = self._last_attacker_army
            rnd = max(0, min(5, self.current_round))
            if atk == self.fac_army:
                self.kills_by_fac_round[rnd] += 1
            elif atk == self.opp_army:
                self.kills_by_opp_round[rnd] += 1
        elif isinstance(e, StratagemFired):
            if e.army_name == self.fac_army:
                self.fac_strats[(self.current_round, e.stratagem_name)] += 1
            elif e.army_name == self.opp_army:
                self.opp_strats[(self.current_round, e.stratagem_name)] += 1
        elif isinstance(e, RoundEnded):
            self.last_a_vp = e.a_vp_total
            self.last_b_vp = e.b_vp_total
        elif isinstance(e, UnitReanimated):
            # only fires for the side that has Reanimation Protocols
            self.reanims += 1

    def _record_attack(self, attacker_uid: str, target_uid: str,
                       damage: float, target_alive_after: bool) -> None:
        a_army = self.uid_army.get(attacker_uid)
        t_army = self.uid_army.get(target_uid)
        rnd = max(0, min(5, self.current_round))
        if a_army == self.fac_army and t_army == self.opp_army:
            self.dmg_dealt_fac[rnd] += damage
        elif a_army == self.opp_army and t_army == self.fac_army:
            self.dmg_dealt_opp[rnd] += damage
        self._last_attacker_army = a_army
        self._last_attacker_round = rnd


def run_one_matchup(fac: str, opp: str) -> Dict:
    fac_wins = 0
    opp_wins = 0
    draws = 0
    fac_vp: List[int] = []
    opp_vp: List[int] = []
    fac_dmg_total: List[float] = []
    opp_dmg_total: List[float] = []
    fac_kills_total: List[int] = []
    opp_kills_total: List[int] = []
    rounds_played: List[int] = []
    strat_counts: Counter = Counter()
    opp_strat_counts: Counter = Counter()
    reanims: List[int] = []
    # round-distributed damage
    fac_dmg_by_round = [0.0] * 6
    opp_dmg_by_round = [0.0] * 6
    fac_kills_by_round = [0] * 6
    opp_kills_by_round = [0] * 6

    for s in range(N_BATTLES):
        seed = s + 12345
        random.seed(seed)
        fac_army = build_faction_random_army(
            "A", fac, POINTS, rng=random.Random(seed), use_archetype=True,
        )
        opp_army = build_faction_random_army(
            "B", opp, POINTS, rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not fac_army.units or not opp_army.units:
            continue

        sub = TraceSub(fac_army.name, opp_army.name)
        battle = Battle(fac_army, opp_army, map_=DEFAULT_MAP, subscribers=[sub])
        battle._assign_uids()
        sub.set_armies(
            [u.uid for u in fac_army.units],
            [u.uid for u in opp_army.units],
            fac_is_a=True, a_name=fac_army.name, b_name=opp_army.name,
        )
        r = battle.run()
        if r.winner == fac_army.name:
            fac_wins += 1
        elif r.winner == opp_army.name:
            opp_wins += 1
        else:
            draws += 1
        rounds_played.append(r.rounds)
        fac_vp.append(sub.last_a_vp)
        opp_vp.append(sub.last_b_vp)
        fac_dmg_total.append(sum(sub.dmg_dealt_fac))
        opp_dmg_total.append(sum(sub.dmg_dealt_opp))
        fac_kills_total.append(sum(sub.kills_by_fac_round))
        opp_kills_total.append(sum(sub.kills_by_opp_round))
        for i in range(6):
            fac_dmg_by_round[i] += sub.dmg_dealt_fac[i]
            opp_dmg_by_round[i] += sub.dmg_dealt_opp[i]
            fac_kills_by_round[i] += sub.kills_by_fac_round[i]
            opp_kills_by_round[i] += sub.kills_by_opp_round[i]
        for (_rnd, name), n in sub.fac_strats.items():
            strat_counts[name] += n
        for (_rnd, name), n in sub.opp_strats.items():
            opp_strat_counts[name] += n
        reanims.append(sub.reanims)

    n_total = fac_wins + opp_wins + draws
    wr = 100.0 * fac_wins / n_total if n_total else 0.0
    norm = float(n_total) if n_total else 1.0
    return {
        "fac": fac, "opp": opp, "wr": wr, "n": n_total,
        "fac_vp_mean": statistics.mean(fac_vp) if fac_vp else 0.0,
        "opp_vp_mean": statistics.mean(opp_vp) if opp_vp else 0.0,
        "fac_dmg_mean": statistics.mean(fac_dmg_total) if fac_dmg_total else 0.0,
        "opp_dmg_mean": statistics.mean(opp_dmg_total) if opp_dmg_total else 0.0,
        "fac_kills_mean": statistics.mean(fac_kills_total) if fac_kills_total else 0.0,
        "opp_kills_mean": statistics.mean(opp_kills_total) if opp_kills_total else 0.0,
        "rounds_mean": statistics.mean(rounds_played) if rounds_played else 0.0,
        "fac_strats": strat_counts.most_common(5),
        "opp_strats": opp_strat_counts.most_common(5),
        "reanims_mean": statistics.mean(reanims) if reanims else 0.0,
        "fac_dmg_per_round": [x / norm for x in fac_dmg_by_round],
        "opp_dmg_per_round": [x / norm for x in opp_dmg_by_round],
        "fac_kills_per_round": [x / norm for x in fac_kills_by_round],
        "opp_kills_per_round": [x / norm for x in opp_kills_by_round],
    }


def main() -> None:
    print(f"Cluster A over-performer trace — N={N_BATTLES}/matchup, {POINTS} pts each.")
    print("=" * 90)
    for fac, opps in TARGETS.items():
        print(f"\n## {fac}")
        agg_wr: List[float] = []
        agg_fac_vp: List[float] = []
        agg_opp_vp: List[float] = []
        for opp in opps:
            r = run_one_matchup(fac, opp)
            agg_wr.append(r["wr"])
            agg_fac_vp.append(r["fac_vp_mean"])
            agg_opp_vp.append(r["opp_vp_mean"])
            print(
                f"  vs {opp:22s} | WR {r['wr']:5.1f}% | rnd {r['rounds_mean']:.2f} |"
                f" {fac[:3]} VP {r['fac_vp_mean']:5.1f} | OPP VP {r['opp_vp_mean']:5.1f} |"
                f" dmg {r['fac_dmg_mean']:6.1f}/{r['opp_dmg_mean']:6.1f} |"
                f" kills {r['fac_kills_mean']:5.1f}/{r['opp_kills_mean']:5.1f} |"
                f" reanim {r['reanims_mean']:4.1f}"
            )
            print(
                f"    dmg/rnd ({fac[:3]}): " +
                " ".join(f"R{i}:{r['fac_dmg_per_round'][i]:.1f}" for i in range(1, 6))
            )
            print(
                f"    dmg/rnd (opp): " +
                " ".join(f"R{i}:{r['opp_dmg_per_round'][i]:.1f}" for i in range(1, 6))
            )
            print(f"    {fac[:3]} top strats: {r['fac_strats']}")
            print(f"    opp top strats: {r['opp_strats']}")
        avg_wr = statistics.mean(agg_wr) if agg_wr else 0.0
        avg_fac_vp = statistics.mean(agg_fac_vp) if agg_fac_vp else 0.0
        avg_opp_vp = statistics.mean(agg_opp_vp) if agg_opp_vp else 0.0
        vp_gap = avg_fac_vp - avg_opp_vp
        print(
            f"  >> 3-opp avg WR {avg_wr:.1f}% | VP {avg_fac_vp:.1f} vs {avg_opp_vp:.1f}"
            f" (gap +{vp_gap:.1f})"
        )


if __name__ == "__main__":
    main()
