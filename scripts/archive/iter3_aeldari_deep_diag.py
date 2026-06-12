"""
Auto-loop iter 3 — Aeldari deep diagnostic (-3.8pt under-perform).

Per CLAUDE.md §1 & §3: read-only diagnostic. No commit, no push.

Runs 30 vanilla battles per matchup of Aeldari vs three representative
opponents (Death Guard, Marines/Space Marines, Necrons) at 1000pts and
captures four mechanism cohorts:

  1. Battle Focus token economy — tokens issued, tokens spent per battle,
     mean Advance+shoot fires per battle. Wahapedia: Battle Focus grants
     ~8-12 Agile Manoeuvres / battle in real play; we model 4 tokens once.

  2. Stratagem firing — count fires of every Aeldari stratagem
     (Lightning-Fast Reactions, Fire and Fade, Skyborne Sanctuary,
     Feigned Retreat, Blitzing Firepower, Webway Tunnel,
     Matchless Agility, Spirit Stones). Real expected 4-6 / battle.

  3. Damage output — per-round dealt and taken; AP-rich burst proxy
     captured as mean damage in the first 2 rounds vs final 2 rounds.
     Aeldari is melta/Fusion heavy: alpha-window output is the lever.

  4. Survival — round of first death; mean alive units at battle end.
     Aeldari is fragile but mobile — short first-death rounds indicate
     "no Strands of Fate / no Fate-dice-save" gap (turn 1 alpha kills
     half the army).

Output: prints summary tables; written by hand into the iter3 doc.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter3_aeldari_deep_diag

Total run time: ~120s for 90 N=30 vanilla battles.
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional

os.environ.setdefault("PYTHONHASHSEED", "0")

from code.army_builder import build_faction_random_army  # noqa: E402
from code.events import (  # noqa: E402
    RoundStarted,
    StratagemFired,
    UnitAdvanced,
    UnitCharged,
    UnitFought,
    UnitKilled,
    UnitShot,
)
from code.maps import DEFAULT_MAP  # noqa: E402
from code.simulator import Battle  # noqa: E402


N_BATTLES = 30
POINTS = 1000

OPPONENTS = ["Death Guard", "Adeptus Astartes", "Necrons"]


class AeldariSub:
    """Captures per-battle Aeldari diagnostic stats."""

    def __init__(self, faction_uid_prefix: str, faction_army) -> None:
        self.prefix = faction_uid_prefix
        self.faction_army = faction_army
        self.starting_tokens: int = 0
        self.round_num = 0
        self.dmg_dealt_per_round: Dict[int, float] = defaultdict(float)
        self.dmg_taken_per_round: Dict[int, float] = defaultdict(float)
        self.strats_fired: Counter = Counter()
        self.advances: int = 0
        self.charges_attempted = 0
        self.charges_failed = 0
        self.first_death_round: Optional[int] = None
        self.kills_by_round: Dict[int, int] = defaultdict(int)

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
            if e.unit_uid.startswith(self.prefix):
                if self.first_death_round is None:
                    self.first_death_round = self.round_num
                self.kills_by_round[self.round_num] += 1
        elif isinstance(e, StratagemFired):
            if e.army_name == self.faction_army.name:
                self.strats_fired[e.stratagem_name] += 1
        elif isinstance(e, UnitAdvanced):
            if e.unit_uid.startswith(self.prefix):
                self.advances += 1
        elif isinstance(e, UnitCharged):
            if e.unit_uid.startswith(self.prefix):
                self.charges_attempted += 1
                if not e.succeeded:
                    self.charges_failed += 1


def run_matchup(faction: str, opponent: str) -> Dict:
    dmg_dealt_total: List[float] = []
    dmg_taken_total: List[float] = []
    burst_dmg: List[float] = []          # rounds 1-2
    late_dmg: List[float] = []           # rounds 4-5
    burst_dmg_taken: List[float] = []    # rounds 1-2 incoming (alpha pressure)
    strat_counter: Counter = Counter()
    first_deaths: List[int] = []
    advances_per_battle: List[int] = []
    charges_attempted: List[int] = []
    charges_failed: List[int] = []
    tokens_start: List[int] = []
    tokens_end: List[int] = []
    tokens_spent: List[int] = []
    units_alive_end: List[int] = []
    units_alive_start: List[int] = []
    wins = 0

    for s in range(N_BATTLES):
        seed = s + 31000 + hash(faction + opponent) % 1000
        random.seed(seed)
        try:
            a = build_faction_random_army(
                "A", faction, POINTS, rng=random.Random(seed),
                use_archetype=True,
            )
            b = build_faction_random_army(
                "B", opponent, POINTS, rng=random.Random(seed + 70000),
                use_archetype=True,
            )
        except Exception as exc:
            print(f"  builder failed seed={seed}: {exc}", file=sys.stderr)
            continue
        if not a.units or not b.units:
            continue

        sub = AeldariSub("A", a)
        battle = Battle(a, b, map_=DEFAULT_MAP, subscribers=[sub])
        # Capture tokens after setup_battle has run.
        result = battle.run()
        # Pull starting tokens by re-deriving via the same rule the simulator uses.
        # Approximated by reading post-battle a.battle_focus_tokens (= remaining).
        end_tokens = int(getattr(a, "battle_focus_tokens", 0) or 0)
        # Reconstruct starting tokens: 4 + (1 if Warhost martial_grace else 0).
        det = a.resolve_detachment() if hasattr(a, "resolve_detachment") else None
        base = 4
        if det is not None and getattr(det, "martial_grace", False):
            base += 1
        has_asuryani = any(
            "ASURYANI" in (u.profile.unit_keywords or ()) for u in a.units
        )
        start_tokens = base if has_asuryani else 0

        d_total = sum(sub.dmg_dealt_per_round.values())
        t_total = sum(sub.dmg_taken_per_round.values())
        dmg_dealt_total.append(d_total)
        dmg_taken_total.append(t_total)
        burst_dmg.append(
            sum(v for r, v in sub.dmg_dealt_per_round.items() if r <= 2)
        )
        late_dmg.append(
            sum(v for r, v in sub.dmg_dealt_per_round.items() if r >= 4)
        )
        burst_dmg_taken.append(
            sum(v for r, v in sub.dmg_taken_per_round.items() if r <= 2)
        )
        strat_counter.update(sub.strats_fired)
        if sub.first_death_round is not None:
            first_deaths.append(sub.first_death_round)
        advances_per_battle.append(sub.advances)
        charges_attempted.append(sub.charges_attempted)
        charges_failed.append(sub.charges_failed)
        tokens_start.append(start_tokens)
        tokens_end.append(end_tokens)
        tokens_spent.append(max(0, start_tokens - end_tokens))
        units_alive_start.append(len(a.units))
        units_alive_end.append(sum(1 for u in a.units if u.is_alive))
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
        "burst_dmg_mean": _mean(burst_dmg),
        "late_dmg_mean": _mean(late_dmg),
        "burst_dmg_taken_mean": _mean(burst_dmg_taken),
        "strats_per_battle": {
            k: round(v / max(1, len(dmg_dealt_total)), 2)
            for k, v in strat_counter.most_common()
        },
        "first_death_round_mean": _mean(first_deaths),
        "advances_mean": _mean(advances_per_battle),
        "charges_attempted_mean": _mean(charges_attempted),
        "charges_failed_mean": _mean(charges_failed),
        "tokens_start_mean": _mean(tokens_start),
        "tokens_end_mean": _mean(tokens_end),
        "tokens_spent_mean": _mean(tokens_spent),
        "units_alive_start_mean": _mean(units_alive_start),
        "units_alive_end_mean": _mean(units_alive_end),
    }


def report(r: Dict) -> None:
    fac, opp = r["faction"], r["opponent"]
    print(f"\n--- {fac} vs {opp} (N={r['n']}) ---")
    print(f"  win rate:          {r['win_rate']:.1%}  ({r['wins']}/{r['n']})")
    print(f"  dmg dealt / taken: {r['dmg_dealt_mean']:.1f} / {r['dmg_taken_mean']:.1f}")
    print(f"  burst (R1-2) / late (R4-5) dealt: "
          f"{r['burst_dmg_mean']:.1f} / {r['late_dmg_mean']:.1f}")
    print(f"  burst (R1-2) taken: {r['burst_dmg_taken_mean']:.1f}  "
          f"(alpha-pressure proxy)")
    fdr = r["first_death_round_mean"]
    if fdr is not None:
        print(f"  first death R:     {fdr:.2f}")
    print(f"  units start/end:   {r['units_alive_start_mean']:.1f} / "
          f"{r['units_alive_end_mean']:.1f}")
    print(f"  advances:          {r['advances_mean']:.1f} / battle")
    print(f"  charges:           {r['charges_attempted_mean']:.1f} attempted, "
          f"{r['charges_failed_mean']:.1f} failed")
    print(f"  battle_focus tokens: start {r['tokens_start_mean']:.1f} → "
          f"end {r['tokens_end_mean']:.1f}  (spent {r['tokens_spent_mean']:.1f})")
    if r["strats_per_battle"]:
        print(f"  stratagems / battle:")
        for k, v in r["strats_per_battle"].items():
            print(f"     {k:<32} {v}")
    else:
        print(f"  stratagems / battle: NONE FIRED")


def main() -> None:
    print(f"Iter 3 Aeldari deep diagnostic (N={N_BATTLES} per matchup, "
          f"{POINTS}pts, vanilla)")
    for opp in OPPONENTS:
        r = run_matchup("Aeldari", opp)
        report(r)


if __name__ == "__main__":
    main()
