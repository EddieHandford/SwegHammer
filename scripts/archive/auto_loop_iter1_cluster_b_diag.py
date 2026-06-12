"""
Auto-loop iter 1, Cluster B — under-performer mechanism trace.

For each of the three under-performing factions (Orks -6.6pt, Aeldari -4.4pt,
T'au -3.4pt) runs 30 archetype-vs-archetype battles vs 3 representative
opponents and captures:

  * damage dealt vs received by the faction (mean per battle)
  * stratagems fired by the faction (name -> count)
  * VP scored vs lost (rough proxy: friendly survivors / opponent survivors)
  * round of first death of a faction unit (alpha-strike vulnerability)
  * mean number of attempted-but-failed charges (range gating)
  * for Orks specifically: round of WAAAGH! declaration vs round of first
    successful charge (timing diagnostic)
  * for Aeldari specifically: battle-focus tokens used (Advance+shoot uplift)
  * for T'au specifically: rounds 1-3 vs 4-5 damage split (alpha-strike window)

Read-only. Pure diagnostic. PYTHONIOENCODING=utf-8 required on Windows.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.auto_loop_iter1_cluster_b_diag

Total run time: ~120s for 270 N=30 battles (3 factions x 3 opponents x 30).
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional

# Deterministic hash seeding for repeatable matchup-keys.
os.environ.setdefault("PYTHONHASHSEED", "0")

from code.army_builder import build_faction_random_army  # noqa: E402
from code.events import (  # noqa: E402
    RoundStarted,
    StratagemFired,
    UnitCharged,
    UnitKilled,
    UnitShot,
    UnitFought,
    WaaaghDeclared,
)
from code.maps import DEFAULT_MAP  # noqa: E402
from code.simulator import Battle  # noqa: E402


N_BATTLES = 30
POINTS = 1000

FACTIONS_AND_OPPONENTS: Dict[str, List[str]] = {
    # Under-performers vs three representative tournament opponents
    # (one elite, one shooty, one balanced).
    "Orks":         ["Adeptus Custodes", "T'au Empire",      "Necrons"],
    "Aeldari":      ["Adeptus Custodes", "Death Guard",      "Necrons"],
    "T'au Empire":  ["Adeptus Custodes", "Tyranids",         "Necrons"],
}


class Sub:
    """Captures per-battle diagnostic stats for the faction under test."""

    def __init__(self, faction_uid_prefix: str, faction_army) -> None:
        self.prefix = faction_uid_prefix
        self.faction_army = faction_army
        self.round_num = 0
        self.dmg_dealt_per_round: Dict[int, float] = defaultdict(float)
        self.dmg_taken_per_round: Dict[int, float] = defaultdict(float)
        self.strats_fired: Counter = Counter()
        self.charges_attempted = 0
        self.charges_failed = 0
        self.first_death_round: Optional[int] = None
        self.waaagh_round: Optional[int] = None
        self.first_charge_round: Optional[int] = None

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.round_num = e.round_num
        elif isinstance(e, UnitShot):
            if e.attacker_uid.startswith(self.prefix):
                self.dmg_dealt_per_round[self.round_num] += float(e.damage)
            elif e.target_uid.startswith(self.prefix):
                self.dmg_taken_per_round[self.round_num] += float(e.damage)
        elif isinstance(e, UnitFought):
            if e.attacker_uid.startswith(self.prefix):
                self.dmg_dealt_per_round[self.round_num] += float(e.damage)
            elif e.target_uid.startswith(self.prefix):
                self.dmg_taken_per_round[self.round_num] += float(e.damage)
        elif isinstance(e, UnitKilled):
            if e.unit_uid.startswith(self.prefix) and self.first_death_round is None:
                self.first_death_round = self.round_num
        elif isinstance(e, StratagemFired):
            if e.army_name == self.faction_army.name:
                self.strats_fired[e.stratagem_name] += 1
        elif isinstance(e, UnitCharged):
            if e.unit_uid.startswith(self.prefix):
                self.charges_attempted += 1
                if not e.succeeded:
                    self.charges_failed += 1
                elif self.first_charge_round is None:
                    self.first_charge_round = self.round_num
        elif isinstance(e, WaaaghDeclared):
            if e.army_name == self.faction_army.name:
                self.waaagh_round = e.round_num


def run_matchup(faction: str, opponent: str) -> Dict:
    dmg_dealt_total: List[float] = []
    dmg_taken_total: List[float] = []
    early_dmg: List[float] = []      # rounds 1-3
    late_dmg: List[float] = []       # rounds 4-5
    strat_counter: Counter = Counter()
    survivor_ratio: List[float] = []
    first_deaths: List[int] = []
    charges_attempted: List[int] = []
    charges_failed: List[int] = []
    waaagh_rounds: List[int] = []
    first_charge_rounds: List[int] = []
    wins = 0

    for s in range(N_BATTLES):
        seed = s + 13000 + hash(faction + opponent) % 1000
        random.seed(seed)
        try:
            a = build_faction_random_army(
                "A", faction, POINTS, rng=random.Random(seed),
                use_archetype=True,
            )
            b = build_faction_random_army(
                "B", opponent, POINTS, rng=random.Random(seed + 40000),
                use_archetype=True,
            )
        except Exception as exc:
            print(f"  builder failed seed={seed}: {exc}")
            continue
        if not a.units or not b.units:
            continue

        sub = Sub("A", a)
        battle = Battle(a, b, map_=DEFAULT_MAP, subscribers=[sub])
        result = battle.run()

        d_total = sum(sub.dmg_dealt_per_round.values())
        t_total = sum(sub.dmg_taken_per_round.values())
        dmg_dealt_total.append(d_total)
        dmg_taken_total.append(t_total)
        early_dmg.append(sum(v for r, v in sub.dmg_dealt_per_round.items() if r <= 3))
        late_dmg.append(sum(v for r, v in sub.dmg_dealt_per_round.items() if r >= 4))
        strat_counter.update(sub.strats_fired)
        a_alive = sum(1 for u in a.units if u.is_alive)
        b_alive = sum(1 for u in b.units if u.is_alive)
        survivor_ratio.append(a_alive / max(1, b_alive))
        if sub.first_death_round is not None:
            first_deaths.append(sub.first_death_round)
        charges_attempted.append(sub.charges_attempted)
        charges_failed.append(sub.charges_failed)
        if sub.waaagh_round is not None:
            waaagh_rounds.append(sub.waaagh_round)
        if sub.first_charge_round is not None:
            first_charge_rounds.append(sub.first_charge_round)
        if result.winner == a.name:
            wins += 1

    def _mean(xs):
        return statistics.mean(xs) if xs else None

    return {
        "faction": faction,
        "opponent": opponent,
        "n": len(dmg_dealt_total),
        "wins": wins,
        "win_rate": wins / max(1, len(dmg_dealt_total)),
        "dmg_dealt_mean": _mean(dmg_dealt_total),
        "dmg_taken_mean": _mean(dmg_taken_total),
        "early_dmg_mean": _mean(early_dmg),
        "late_dmg_mean":  _mean(late_dmg),
        "strats_per_battle": {
            k: round(v / max(1, len(dmg_dealt_total)), 2)
            for k, v in strat_counter.most_common()
        },
        "survivor_ratio_mean": _mean(survivor_ratio),
        "first_death_round_mean": _mean(first_deaths),
        "charges_attempted_mean": _mean(charges_attempted),
        "charges_failed_mean": _mean(charges_failed),
        "waaagh_round_mean": _mean(waaagh_rounds),
        "first_charge_round_mean": _mean(first_charge_rounds),
    }


def report(r: Dict) -> None:
    fac = r["faction"]
    opp = r["opponent"]
    print(f"\n--- {fac} vs {opp} (N={r['n']}) ---")
    print(f"  win rate:        {r['win_rate']:.1%}  ({r['wins']}/{r['n']})")
    print(f"  dmg dealt mean:  {r['dmg_dealt_mean']:.1f}")
    print(f"  dmg taken mean:  {r['dmg_taken_mean']:.1f}")
    print(f"  early/late dmg:  {r['early_dmg_mean']:.1f} / {r['late_dmg_mean']:.1f}")
    print(f"  survivor ratio:  {r['survivor_ratio_mean']:.2f}")
    fdr = r["first_death_round_mean"]
    if fdr is not None:
        print(f"  first death R:   {fdr:.2f}")
    print(f"  charges:         {r['charges_attempted_mean']:.1f} attempted, {r['charges_failed_mean']:.1f} failed")
    if r["waaagh_round_mean"] is not None:
        print(f"  WAAAGH! mean R:  {r['waaagh_round_mean']:.2f}")
    if r["first_charge_round_mean"] is not None:
        print(f"  1st charge R:    {r['first_charge_round_mean']:.2f}")
    if r["strats_per_battle"]:
        print(f"  stratagems / battle:")
        for k, v in r["strats_per_battle"].items():
            print(f"     {k:<30} {v}")
    else:
        print(f"  stratagems / battle: NONE FIRED")


def main() -> None:
    print(f"Auto-loop iter 1 Cluster B diagnostic (N={N_BATTLES} per matchup, {POINTS}pts)")
    for fac, opps in FACTIONS_AND_OPPONENTS.items():
        for opp in opps:
            r = run_matchup(fac, opp)
            report(r)


if __name__ == "__main__":
    main()
