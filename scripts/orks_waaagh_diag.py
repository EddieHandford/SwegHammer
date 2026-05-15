"""
#175 G9 — Orks WAAAGH! AI timing diagnostic.

Orks sit -5.3pt in archetype eval-vs-meta. Suspected cause: WAAAGH! declared at
the wrong round (turn 1 too early, before Boyz are in charge range; or turn 5
too late, when Boyz are already dead).

This script runs N=30 seeded archetype battles per Ork matchup vs T'au /
Astartes / Necrons (1000 pts, archetype=True both sides). For each battle it
captures:

  * Round in which the Ork player declared WAAAGH! (1..5).
  * Round in which the first Ork unit successfully charged (1..5 or None).
  * Count of Boyz models alive at WAAAGH! declaration vs at first-charge-round.

Read-only. Pure diagnostic.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.orks_waaagh_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter
from typing import Dict, List, Optional

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.orks_waaagh_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    RoundStarted,
    UnitCharged,
    WaaaghDeclared,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS: List[str] = ["T'au Empire", "Adeptus Astartes", "Necrons"]
N_BATTLES = 30
POINTS = 1000


def _alive_boyz(army) -> int:
    return sum(1 for u in army.units if u.is_alive and "Boyz" in u.profile.name)


class WaaaghSub:
    """Per-battle capture of WAAAGH! timing and first Ork charge."""

    def __init__(self, ork_army_uid_prefix: str, ork_army) -> None:
        self.prefix = ork_army_uid_prefix
        self.ork_army = ork_army
        self.round_num = 0
        self.waaagh_round: Optional[int] = None
        self.first_charge_round: Optional[int] = None
        self.boyz_at_waaagh: Optional[int] = None
        self.boyz_at_first_charge: Optional[int] = None

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.round_num = e.round_num
        elif isinstance(e, WaaaghDeclared):
            if e.army_name == self.ork_army.name:
                self.waaagh_round = e.round_num
                self.boyz_at_waaagh = _alive_boyz(self.ork_army)
        elif isinstance(e, UnitCharged):
            if e.succeeded and e.unit_uid.startswith(self.prefix):
                if self.first_charge_round is None:
                    self.first_charge_round = self.round_num
                    self.boyz_at_first_charge = _alive_boyz(self.ork_army)


def run_matchup(opponent: str) -> Dict:
    waaagh_dist: Counter = Counter()
    waaagh_none = 0
    first_charge_rounds: List[int] = []
    no_charge = 0
    boyz_at_w: List[int] = []
    boyz_at_c: List[int] = []
    waaagh_before_charge = 0
    waaagh_same_round = 0
    waaagh_after_charge = 0
    no_boyz = 0

    for s in range(N_BATTLES):
        seed = s + 9001
        random.seed(seed)
        orks = build_faction_random_army(
            "A", "Orks", POINTS,
            rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(seed + 40000),
            use_archetype=True,
        )
        if not orks.units or not opp.units:
            continue
        starting_boyz = sum(1 for u in orks.units if "Boyz" in u.profile.name)
        if starting_boyz == 0:
            no_boyz += 1

        sub = WaaaghSub("A", orks)
        battle = Battle(orks, opp, map_=DEFAULT_MAP, subscribers=[sub])
        battle.run()

        if sub.waaagh_round is not None:
            waaagh_dist[sub.waaagh_round] += 1
        else:
            waaagh_none += 1
        if sub.first_charge_round is not None:
            first_charge_rounds.append(sub.first_charge_round)
        else:
            no_charge += 1
        if sub.boyz_at_waaagh is not None:
            boyz_at_w.append(sub.boyz_at_waaagh)
        if sub.boyz_at_first_charge is not None:
            boyz_at_c.append(sub.boyz_at_first_charge)

        if sub.waaagh_round is not None and sub.first_charge_round is not None:
            if sub.waaagh_round < sub.first_charge_round:
                waaagh_before_charge += 1
            elif sub.waaagh_round == sub.first_charge_round:
                waaagh_same_round += 1
            else:
                waaagh_after_charge += 1

    return {
        "opponent": opponent,
        "waaagh_dist": waaagh_dist,
        "waaagh_none": waaagh_none,
        "first_charge_mean": (
            statistics.mean(first_charge_rounds) if first_charge_rounds else None
        ),
        "no_charge": no_charge,
        "boyz_at_w_mean": statistics.mean(boyz_at_w) if boyz_at_w else None,
        "boyz_at_c_mean": statistics.mean(boyz_at_c) if boyz_at_c else None,
        "w_before_c": waaagh_before_charge,
        "w_same_c": waaagh_same_round,
        "w_after_c": waaagh_after_charge,
        "no_boyz_seeds": no_boyz,
    }


def report(r: Dict) -> None:
    opp = r["opponent"]
    print(f"\n--- Orks vs {opp} (N={N_BATTLES}) ---")
    print(f"WAAAGH! round distribution:")
    for rd in (1, 2, 3, 4, 5):
        n = r["waaagh_dist"].get(rd, 0)
        print(f"  R{rd}: {n}/{N_BATTLES}")
    if r["waaagh_none"]:
        print(f"  NEVER FIRED: {r['waaagh_none']}/{N_BATTLES}")
    fc = r["first_charge_mean"]
    if fc is not None:
        print(f"Mean round of first Ork charge: {fc:.2f}")
    else:
        print("Mean round of first Ork charge: n/a")
    if r["no_charge"]:
        print(f"  battles with no successful Ork charge: {r['no_charge']}/{N_BATTLES}")
    bw, bc = r["boyz_at_w_mean"], r["boyz_at_c_mean"]
    bw_s = f"{bw:.1f}" if bw is not None else "n/a"
    bc_s = f"{bc:.1f}" if bc is not None else "n/a"
    print(f"Boyz models alive at WAAAGH declare: mean={bw_s}, vs at first-charge-round: mean={bc_s}")
    print(
        f"WAAAGH vs first-charge ordering: "
        f"before={r['w_before_c']}  same={r['w_same_c']}  after={r['w_after_c']}"
    )
    if r["no_boyz_seeds"]:
        print(f"  seeds with NO Boyz in roster: {r['no_boyz_seeds']}/{N_BATTLES}")


def main() -> None:
    print(f"#175 G9 — Orks WAAAGH! AI timing diagnostic (N={N_BATTLES} per matchup)")
    for opp in OPPONENTS:
        r = run_matchup(opp)
        report(r)


if __name__ == "__main__":
    main()
