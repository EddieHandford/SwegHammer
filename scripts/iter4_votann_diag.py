"""
Iter 4 — Leagues of Votann diagnostic.

Votann WR drifted +4.0 (iter 0) -> +5.7 (iter 3) across the auto-loop and has
never been investigated directly. Real-meta WR 46.0%, sim ~51.7%.

This is a diagnostic-only script — does NOT mutate catalogue / simulator /
overrides. Runs 30 vanilla battles per opponent (Marines, Death Guard,
Necrons) and captures:

  H1  Per-round Votann damage output (shooting + melee).
  H2  Stratagem firing — which strats fire and how much CP the Oathband
      placeholder uses vs Marines / DG / Necrons. The OATHBAND detachment
      has zero detachment stratagems, so we expect Votann to spend CP only
      on the four UNIVERSAL_STRATAGEMS (Command Re-Roll, Counter-Offensive,
      Tank Shock, Heroic Intervention).
  H3  Survival — first-death round + total dead per battle. Votann are
      tanky (T5-T6 infantry with 4+/2+ saves, FNP on Beserks); if they
      cling on too long that is a contributor to the +5.7 inflation.
  H4  Judgement Tokens — count tokens awarded per battle. The simulator
      models the legacy Eye of the Ancestors mechanic which grants Votann
      escalating re-rolls vs the killer's unit (1+ tokens = re-roll Hit
      1s; 3+ tokens = re-roll all hits + Wound 1s). The current Wahapedia
      rule is Prioritised Efficiency (Yield Points / Hostile Acquisition),
      a totally different mechanic — tagged APPROXIMATION in
      `data/rule_citations.d/judgement_tokens.json`. Over-firing of EotA
      directly inflates Votann WR.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter4_votann_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional

# Lock hash randomisation off so set/dict iteration is reproducible.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter4_votann_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleEnded,
    JudgementTokenAwarded,
    RoundEnded,
    RoundStarted,
    StratagemFired,
    UnitFought,
    UnitKilled,
    UnitShot,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle

VOTANN = "Leagues of Votann"
OPPONENTS: List[str] = ["Adeptus Astartes", "Death Guard", "Necrons"]
N_BATTLES = 30
POINTS = 1000


class VotannDiagSub:
    """Per-battle capture for Votann diagnostic hypotheses."""

    def __init__(self, votann_army, opp_army) -> None:
        self.votann_army = votann_army
        self.opp_army = opp_army
        self.votann_uids = {u.uid for u in votann_army.units}
        self.opp_uids = {u.uid for u in opp_army.units}
        self.votann_total_models = len(votann_army.units)
        self.round_num = 0
        # H1: damage by Votann attacker per round.
        self.dmg_by_round: Counter = Counter()
        # H2: stratagems fired per army.
        self.strats_votann: Counter = Counter()
        self.strats_opp: Counter = Counter()
        self.cp_spent_votann = 0
        self.cp_spent_opp = 0
        # H3: deaths.
        self.first_death_round_votann: Optional[int] = None
        self.deaths_votann = 0
        self.deaths_opp = 0
        # H4: judgement tokens.
        self.tokens_awarded = 0
        self.max_tokens_on_any_target = 0
        # Win.
        self.winner: Optional[str] = None
        self.total_rounds = 0

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.round_num = e.round_num
        elif isinstance(e, UnitShot):
            if e.attacker_uid in self.votann_uids:
                self.dmg_by_round[self.round_num] += float(e.damage)
        elif isinstance(e, UnitFought):
            if e.attacker_uid in self.votann_uids:
                self.dmg_by_round[self.round_num] += float(e.damage)
        elif isinstance(e, StratagemFired):
            if e.army_name == self.votann_army.name:
                self.strats_votann[e.stratagem_name] += 1
                self.cp_spent_votann += e.cp_cost
            else:
                self.strats_opp[e.stratagem_name] += 1
                self.cp_spent_opp += e.cp_cost
        elif isinstance(e, UnitKilled):
            if e.unit_uid in self.votann_uids:
                self.deaths_votann += 1
                if self.first_death_round_votann is None:
                    self.first_death_round_votann = self.round_num
            elif e.unit_uid in self.opp_uids:
                self.deaths_opp += 1
        elif isinstance(e, JudgementTokenAwarded):
            self.tokens_awarded += 1
            if e.total_tokens > self.max_tokens_on_any_target:
                self.max_tokens_on_any_target = e.total_tokens
        elif isinstance(e, RoundEnded):
            self.total_rounds = max(self.total_rounds, e.round_num)
        elif isinstance(e, BattleEnded):
            self.winner = e.winner
            self.total_rounds = e.rounds


def run_matchup(opponent: str) -> Dict:
    wins = 0
    losses = 0
    draws = 0
    dmg_by_round_collected: Dict[int, List[float]] = defaultdict(list)
    cp_spent_votann_list: List[int] = []
    cp_spent_opp_list: List[int] = []
    strats_votann_total: Counter = Counter()
    strats_opp_total: Counter = Counter()
    first_death_list: List[int] = []
    deaths_votann_list: List[int] = []
    deaths_opp_list: List[int] = []
    survival_pct_list: List[float] = []
    tokens_per_battle: List[int] = []
    max_tokens_list: List[int] = []
    total_rounds_list: List[int] = []
    detachment_names: Counter = Counter()

    for s in range(N_BATTLES):
        seed = s + 80001
        random.seed(seed)
        votann = build_faction_random_army(
            "A", VOTANN, POINTS, rng=random.Random(seed),
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS, rng=random.Random(seed + 40000),
        )
        if not votann.units or not opp.units:
            continue

        sub = VotannDiagSub(votann, opp)
        battle = Battle(
            votann, opp,
            map_=DEFAULT_MAP,
            subscribers=[sub],
        )
        result = battle.run()

        if result.winner == "A":
            wins += 1
        elif result.winner == "B":
            losses += 1
        else:
            draws += 1

        det_name = votann.detachment.name if votann.detachment else "(none)"
        detachment_names[det_name] += 1

        for rd in (1, 2, 3, 4, 5):
            dmg_by_round_collected[rd].append(sub.dmg_by_round.get(rd, 0.0))
        cp_spent_votann_list.append(sub.cp_spent_votann)
        cp_spent_opp_list.append(sub.cp_spent_opp)
        for k, v in sub.strats_votann.items():
            strats_votann_total[k] += v
        for k, v in sub.strats_opp.items():
            strats_opp_total[k] += v
        first_death_list.append(
            sub.first_death_round_votann if sub.first_death_round_votann else 99
        )
        deaths_votann_list.append(sub.deaths_votann)
        deaths_opp_list.append(sub.deaths_opp)
        survival = (
            (sub.votann_total_models - sub.deaths_votann)
            / max(1, sub.votann_total_models)
            * 100.0
        )
        survival_pct_list.append(survival)
        tokens_per_battle.append(sub.tokens_awarded)
        max_tokens_list.append(sub.max_tokens_on_any_target)
        total_rounds_list.append(sub.total_rounds)

    n_total = wins + losses + draws
    wr = (wins / n_total * 100.0) if n_total else 0.0

    return {
        "opponent": opponent,
        "n": n_total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "wr": wr,
        "detachments": detachment_names,
        "dmg_by_round_mean": {
            rd: (statistics.mean(v) if v else 0.0)
            for rd, v in dmg_by_round_collected.items()
        },
        "cp_spent_votann_mean":
            statistics.mean(cp_spent_votann_list) if cp_spent_votann_list else 0.0,
        "cp_spent_opp_mean":
            statistics.mean(cp_spent_opp_list) if cp_spent_opp_list else 0.0,
        "strats_votann": strats_votann_total,
        "strats_opp": strats_opp_total,
        "first_death_mean":
            statistics.mean(first_death_list) if first_death_list else 0.0,
        "deaths_votann_mean":
            statistics.mean(deaths_votann_list) if deaths_votann_list else 0.0,
        "deaths_opp_mean":
            statistics.mean(deaths_opp_list) if deaths_opp_list else 0.0,
        "survival_pct_mean":
            statistics.mean(survival_pct_list) if survival_pct_list else 0.0,
        "tokens_per_battle_mean":
            statistics.mean(tokens_per_battle) if tokens_per_battle else 0.0,
        "max_tokens_mean":
            statistics.mean(max_tokens_list) if max_tokens_list else 0.0,
        "total_rounds_mean":
            statistics.mean(total_rounds_list) if total_rounds_list else 0.0,
    }


def report(r: Dict) -> None:
    print(f"\n=== Votann vs {r['opponent']}  (N={r['n']}) ===")
    print(f"  WR (Votann side A): {r['wr']:5.1f}%  W/L/D = "
          f"{r['wins']}/{r['losses']}/{r['draws']}")
    print(f"  Detachments seen: {dict(r['detachments'])}")
    print(f"  Total rounds mean: {r['total_rounds_mean']:.2f}")
    print("  H1 damage by round (mean):")
    for rd in (1, 2, 3, 4, 5):
        d = r["dmg_by_round_mean"].get(rd, 0.0)
        print(f"      R{rd}: {d:6.1f}")
    print("  H2 CP spent (mean):")
    print(f"      Votann: {r['cp_spent_votann_mean']:5.2f}")
    print(f"      Opp:    {r['cp_spent_opp_mean']:5.2f}")
    print("  H2 Votann stratagems fired (total across N battles):")
    if not r["strats_votann"]:
        print("      (none)")
    for k, v in r["strats_votann"].most_common():
        print(f"      {k:35s} x{v}")
    print("  H2 Opp stratagems fired (total across N battles):")
    for k, v in r["strats_opp"].most_common(8):
        print(f"      {k:35s} x{v}")
    print("  H3 survival:")
    print(f"      first Votann death round (mean):      "
          f"{r['first_death_mean']:5.2f}")
    print(f"      Votann deaths per battle (mean):       "
          f"{r['deaths_votann_mean']:5.2f}")
    print(f"      Opp    deaths per battle (mean):       "
          f"{r['deaths_opp_mean']:5.2f}")
    print(f"      Votann survival %% mean:                "
          f"{r['survival_pct_mean']:5.1f}")
    print("  H4 judgement tokens:")
    print(f"      tokens awarded per battle (mean):      "
          f"{r['tokens_per_battle_mean']:5.2f}")
    print(f"      max tokens on any single target (mean):"
          f" {r['max_tokens_mean']:5.2f}")


def main() -> None:
    print(
        f"Iter 4 Votann diagnostic (N={N_BATTLES} per matchup, "
        f"{POINTS}pt, vanilla 10e mode)"
    )

    all_results: List[Dict] = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        all_results.append(r)
        report(r)

    print("\n=== AGGREGATE (mean across 3 matchups) ===")
    def agg(key: str) -> float:
        return statistics.mean(r[key] for r in all_results)

    print(f"  WR mean:                          {agg('wr'):5.2f}%")
    print(f"  CP spent Votann mean:             "
          f"{agg('cp_spent_votann_mean'):5.2f}")
    print(f"  CP spent Opp mean:                "
          f"{agg('cp_spent_opp_mean'):5.2f}")
    print(f"  Tokens awarded / battle mean:     "
          f"{agg('tokens_per_battle_mean'):5.2f}")
    print(f"  Max tokens on any target mean:    "
          f"{agg('max_tokens_mean'):5.2f}")
    print(f"  Votann survival %% mean:           "
          f"{agg('survival_pct_mean'):5.1f}")
    print(f"  First Votann death round mean:    "
          f"{agg('first_death_mean'):5.2f}")
    print(f"  Total rounds mean:                "
          f"{agg('total_rounds_mean'):5.2f}")
    print("\n  R1-R5 mean Votann damage:")
    for rd in (1, 2, 3, 4, 5):
        d = statistics.mean(r["dmg_by_round_mean"].get(rd, 0.0)
                            for r in all_results)
        print(f"      R{rd}: {d:6.1f}")

    # Aggregate strats across all opponents.
    strats_v: Counter = Counter()
    strats_o: Counter = Counter()
    for r in all_results:
        strats_v.update(r["strats_votann"])
        strats_o.update(r["strats_opp"])
    print("\n  Votann stratagems (aggregate, all 3 matchups):")
    if not strats_v:
        print("      (none)")
    for k, v in strats_v.most_common():
        print(f"      {k:35s} x{v}")
    print("\n  Opp stratagems top 8 (aggregate, all 3 matchups):")
    for k, v in strats_o.most_common(8):
        print(f"      {k:35s} x{v}")

    print("\nInterpretation guide:")
    print("  - H2: if Votann CP-spent is materially lower than opponents,")
    print("        the OATHBAND placeholder has no detachment stratagems and")
    print("        is bleeding CP advantage to the opponent.")
    print("  - H4: tokens_per_battle very high (>5) means the legacy Eye-of-")
    print("        Ancestors approximation is firing a lot; max_tokens >=3 on")
    print("        any single target means the tier-3 reroll-all-hits buff")
    print("        activated, which is the biggest WR-inflator.")
    print("  - H1: high damage in early rounds R1-R2 means alpha-strike")
    print("        shooting profile is over-tuned (high-AP weapons + tokens).")


if __name__ == "__main__":
    main()
