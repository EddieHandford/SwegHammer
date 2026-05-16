"""
Necrons vanilla-10e regression diagnostic.

Context: simulator default flipped from SwegHammer alternating activations to
vanilla WH40k 10e I-go-you-go player turns. Almost every faction's eval-vs-meta
diff improved (Aeldari -8.3 -> -1.6, Custodes +5.3 -> -1.9, DG +4.2 -> +0.3),
but Necrons REGRESSED: +6.2 -> +9.0. Real-meta WR is 53.2; sim now ~62.2.

This script tests three hypotheses about why vanilla mode rewards Necrons more
than SwegHammer mode did:

  H_RP        Reanimation Protocols revives per battle.
              `_apply_reanimation` is called once per round in `_run_round`
              regardless of mode, so per-round rate should match. If the
              vanilla-mode count is materially higher, RP is over-firing.

  H_ObjBuff   Awakened Dynasty objective-control state.
              `u.on_objective` is precomputed each round in `_run_round`.
              The flag is not currently READ by any buff dispatcher (no
              `objective_holder_bonus_to_wound` consumer), but if Necrons
              hold objectives more under vanilla turn structure they will
              ALSO score more primary VP (which directly drives WR).

  H_AlphaStrike   Necron damage output round 1 vs round 5.
                  Vanilla mode lets the active player complete a full
                  shoot-pass before the opponent moves; sit-back-and-shoot
                  armies (Necron Warriors + Doomstalkers + Doomsday Arks)
                  benefit disproportionately. Compare R1 damage dealt by
                  Necrons under both modes.

Read-only. Pure diagnostic. Does NOT modify catalogue, simulator, or overrides.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.necrons_vanilla_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

# Lock hash randomisation off so set/dict iteration order is reproducible
# across runs (same convention as evaluate_vs_meta.py).
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.necrons_vanilla_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleEnded,
    RoundEnded,
    RoundStarted,
    UnitReanimated,
    UnitShot,
    UnitFought,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle, RulesConfig

NECRONS = "Necrons"
OPPONENTS: List[str] = ["Adeptus Astartes", "Aeldari", "T'au Empire"]
N_BATTLES = 30
POINTS = 1000


class NecronDiagSub:
    """Per-battle capture of:
      - reanimation revive count (per round)
      - on_objective Necron-unit count, sampled at start of each round AFTER
        _run_round computes the flag
      - damage dealt BY Necrons (sum of UnitShot + UnitFought damage where
        attacker uid is in the Necron army), per round
    """

    def __init__(self, necron_army, opponent_army) -> None:
        self.necron_army = necron_army
        self.opponent_army = opponent_army
        self.necron_uids = {u.uid for u in necron_army.units}
        # populated after _assign_uids; fill in on first activation
        self._uids_populated = False
        self.round_num = 0
        self.revives_by_round: Counter = Counter()
        self.dmg_by_round: Counter = Counter()  # round -> total dmg by necrons
        self.obj_holders_by_round: Dict[int, int] = {}
        self.winner: Optional[str] = None
        self.total_rounds = 0

    def _ensure_uids(self) -> None:
        if not self._uids_populated:
            self.necron_uids = {u.uid for u in self.necron_army.units}
            self._uids_populated = True

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.round_num = e.round_num
            self._ensure_uids()
            # Sample on_objective for the Necron army for this round AFTER
            # _run_round set the flag — by the time a RoundStarted event fires,
            # the simulator has already computed on_objective. (Verified by
            # reading `_run_round` ordering.)
            holders = sum(
                1 for u in self.necron_army.units
                if u.is_alive and getattr(u, "on_objective", False)
            )
            self.obj_holders_by_round[e.round_num] = holders
        elif isinstance(e, UnitReanimated):
            self._ensure_uids()
            # The reanimated uid is a Necron uid by construction (only the
            # Necron army carries the Reanimation flag in this matchup).
            if e.unit_uid in self.necron_uids:
                self.revives_by_round[self.round_num] += 1
        elif isinstance(e, UnitShot):
            self._ensure_uids()
            if e.attacker_uid in self.necron_uids:
                self.dmg_by_round[self.round_num] += float(e.damage)
        elif isinstance(e, UnitFought):
            self._ensure_uids()
            if e.attacker_uid in self.necron_uids:
                self.dmg_by_round[self.round_num] += float(e.damage)
        elif isinstance(e, RoundEnded):
            self.total_rounds = max(self.total_rounds, e.round_num)
        elif isinstance(e, BattleEnded):
            self.winner = e.winner
            self.total_rounds = e.rounds


def run_matchup(opponent: str, rules: Optional[RulesConfig]) -> Dict:
    """Run N_BATTLES Necrons vs opponent under the given rules config."""
    wins = 0
    losses = 0
    draws = 0
    revives_per_battle: List[int] = []
    revives_per_round_collected: List[int] = []
    r1_dmg: List[float] = []
    r5_dmg: List[float] = []
    all_round_dmg: Dict[int, List[float]] = defaultdict(list)
    obj_holders_per_round: Dict[int, List[int]] = defaultdict(list)

    for s in range(N_BATTLES):
        seed = s + 70001
        random.seed(seed)
        necrons = build_faction_random_army(
            "A", NECRONS, POINTS, rng=random.Random(seed),
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS, rng=random.Random(seed + 30000),
        )
        if not necrons.units or not opp.units:
            continue

        sub = NecronDiagSub(necrons, opp)
        battle = Battle(
            necrons, opp,
            map_=DEFAULT_MAP,
            subscribers=[sub],
            rules=rules,
        )
        result = battle.run()

        if result.winner == "A":
            wins += 1
        elif result.winner == "B":
            losses += 1
        else:
            draws += 1

        total_revives = sum(sub.revives_by_round.values())
        revives_per_battle.append(total_revives)
        for rd, n in sub.revives_by_round.items():
            revives_per_round_collected.append(n)
        # round-specific damage
        for rd in (1, 2, 3, 4, 5):
            dmg = sub.dmg_by_round.get(rd, 0.0)
            all_round_dmg[rd].append(dmg)
        r1_dmg.append(sub.dmg_by_round.get(1, 0.0))
        r5_dmg.append(sub.dmg_by_round.get(5, 0.0))
        for rd, h in sub.obj_holders_by_round.items():
            obj_holders_per_round[rd].append(h)

    n_total = wins + losses + draws
    wr = (wins / n_total * 100.0) if n_total else 0.0
    return {
        "opponent": opponent,
        "n": n_total,
        "wins": wins, "losses": losses, "draws": draws,
        "wr": wr,
        "revives_per_battle_mean": (
            statistics.mean(revives_per_battle) if revives_per_battle else 0.0
        ),
        "revives_per_round_mean": (
            statistics.mean(revives_per_round_collected)
            if revives_per_round_collected else 0.0
        ),
        "r1_dmg_mean": statistics.mean(r1_dmg) if r1_dmg else 0.0,
        "r5_dmg_mean": statistics.mean(r5_dmg) if r5_dmg else 0.0,
        "round_dmg_means": {
            rd: (statistics.mean(v) if v else 0.0)
            for rd, v in all_round_dmg.items()
        },
        "obj_holders_mean": {
            rd: (statistics.mean(v) if v else 0.0)
            for rd, v in obj_holders_per_round.items()
        },
    }


def report_matchup(r: Dict, mode_label: str) -> None:
    print(f"\n--- {mode_label}: Necrons vs {r['opponent']} "
          f"(N={r['n']}) ---")
    print(f"  WR (Necron-side A): {r['wr']:5.1f}%   "
          f"W/L/D = {r['wins']}/{r['losses']}/{r['draws']}")
    print(f"  H_RP   revives/battle mean:        {r['revives_per_battle_mean']:5.2f}")
    print(f"  H_RP   revives/round (non-zero) :  {r['revives_per_round_mean']:5.2f}")
    print(f"  H_AS   R1 Necron dmg mean :        {r['r1_dmg_mean']:6.1f}")
    print(f"  H_AS   R5 Necron dmg mean :        {r['r5_dmg_mean']:6.1f}")
    print("  H_AS   per-round dmg:")
    for rd in (1, 2, 3, 4, 5):
        d = r["round_dmg_means"].get(rd, 0.0)
        print(f"           R{rd}: {d:6.1f}")
    print("  H_OB   on-objective Necron-unit count by round:")
    for rd in (1, 2, 3, 4, 5):
        h = r["obj_holders_mean"].get(rd, 0.0)
        print(f"           R{rd}: {h:5.2f}")


def main() -> None:
    print(
        f"Necrons vanilla-10e regression diagnostic "
        f"(N={N_BATTLES} per matchup, {POINTS}pt)"
    )
    print("Comparing vanilla 10e (default) vs SwegHammer mode for the same seeds.")

    vanilla_results: List[Dict] = []
    sweg_results: List[Dict] = []

    for opp in OPPONENTS:
        v = run_matchup(opp, rules=None)   # vanilla = default
        s = run_matchup(opp, rules=RulesConfig.sweghammer())
        vanilla_results.append(v)
        sweg_results.append(s)
        report_matchup(v, "VANILLA 10e")
        report_matchup(s, "SwegHammer")

    print("\n=== AGGREGATE (across all three matchups) ===")
    print(f"{'Metric':40s}  {'Vanilla':>10s}  {'Sweg':>10s}  {'Delta':>10s}")
    print("-" * 78)

    def agg(results: List[Dict], key: str) -> float:
        return statistics.mean(r[key] for r in results)

    def agg_round(results: List[Dict], rd: int, kind: str) -> float:
        return statistics.mean(r[kind].get(rd, 0.0) for r in results)

    v_wr = agg(vanilla_results, "wr")
    s_wr = agg(sweg_results, "wr")
    print(f"{'WR (Necron side)':40s}  {v_wr:>9.2f}%  {s_wr:>9.2f}%  {v_wr - s_wr:>+9.2f}")
    v_rpb = agg(vanilla_results, "revives_per_battle_mean")
    s_rpb = agg(sweg_results, "revives_per_battle_mean")
    print(f"{'H_RP revives/battle':40s}  {v_rpb:>10.2f}  {s_rpb:>10.2f}  {v_rpb - s_rpb:>+10.2f}")
    v_rpr = agg(vanilla_results, "revives_per_round_mean")
    s_rpr = agg(sweg_results, "revives_per_round_mean")
    print(f"{'H_RP revives/round (nonzero)':40s}  {v_rpr:>10.2f}  {s_rpr:>10.2f}  {v_rpr - s_rpr:>+10.2f}")
    v_r1 = agg(vanilla_results, "r1_dmg_mean")
    s_r1 = agg(sweg_results, "r1_dmg_mean")
    print(f"{'H_AS R1 Necron dmg':40s}  {v_r1:>10.2f}  {s_r1:>10.2f}  {v_r1 - s_r1:>+10.2f}")
    v_r5 = agg(vanilla_results, "r5_dmg_mean")
    s_r5 = agg(sweg_results, "r5_dmg_mean")
    print(f"{'H_AS R5 Necron dmg':40s}  {v_r5:>10.2f}  {s_r5:>10.2f}  {v_r5 - s_r5:>+10.2f}")
    print(f"{'H_AS R1/R5 ratio':40s}  "
          f"{(v_r1/v_r5 if v_r5 else 0):>10.2f}  "
          f"{(s_r1/s_r5 if s_r5 else 0):>10.2f}")
    for rd in (1, 2, 3, 4, 5):
        v_h = agg_round(vanilla_results, rd, "obj_holders_mean")
        s_h = agg_round(sweg_results, rd, "obj_holders_mean")
        print(f"{'H_OB on-obj count R' + str(rd):40s}  {v_h:>10.2f}  {s_h:>10.2f}  {v_h - s_h:>+10.2f}")
    for rd in (1, 2, 3, 4, 5):
        v_d = agg_round(vanilla_results, rd, "round_dmg_means")
        s_d = agg_round(sweg_results, rd, "round_dmg_means")
        print(f"{'H_AS Necron dmg R' + str(rd):40s}  {v_d:>10.2f}  {s_d:>10.2f}  {v_d - s_d:>+10.2f}")

    print("\nInterpretation guide:")
    print("  - H_RP positive delta > +1.0 -> RP over-fires in vanilla mode.")
    print("  - H_OB positive delta of holders -> Necrons sit on objectives longer in vanilla.")
    print("  - H_AS positive R1 delta (vanilla > sweg) -> alpha-strike confirmed.")


if __name__ == "__main__":
    main()
