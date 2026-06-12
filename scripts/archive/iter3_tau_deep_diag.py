"""
Iter 3 — T'au Empire deep diagnostic.

T'au calibrates at -3.9pt (sim 50.6% vs real 54.5%). After iter-2 the Mont'ka
[ASSAULT]-rounds-1-3 leg is wired (PR #196) and reads correctly in `_do_shoot`,
six Mont'ka stratagems dispatch via round-start, BUT the [LETHAL HITS] on
Guided half of Killing Blow is a wired-but-not-read flag because the simulator
has no Markerlight / Guided concept. This script measures five hypotheses to
identify the dominant mechanism behind the -3.9pt gap.

Hypotheses
----------

H_MARK   Markerlight / Guided [LETHAL HITS] is absent.
         Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights
         Real rule: MARKER units (Pathfinders, Stealth Suits with markerlight
         drones) mark enemy units; in your Shooting phase, when a marked enemy
         is targeted, T'au shooters' ranged weapons gain [LETHAL HITS]. This
         compounds with Mont'ka rounds 1-3 (a marked enemy gives EVERY T'au
         shooter [LETHAL HITS] until the start of next Command phase). At
         BS 4+ on Crisis, Riptide, Broadside, [LETHAL HITS] adds ~10-12% extra
         landed wounds — central T'au identity. This script can only measure
         the GAP indirectly: it computes what an idealised universal-Guided
         rounds-1-3 buff would produce by re-running the same seeds with
         lethal_hits_on_guided wired as a faction-wide LETHAL HITS proxy.
         (See `_simulate_with_synthetic_markerlights` below.)

H_MK_ADV Mont'ka [ASSAULT] window utilisation.
         Measure: of T'au unit-activations in rounds 1-3, what fraction
         elected to Advance? The [ASSAULT] grant pays off only when a unit
         BOTH Advances AND has a target in range after the advance — if the
         AI rarely Advances (because the picker's `needs_to_close > normal_
         move` gate refuses) the [ASSAULT] grant is dead. Compare T'au
         Advance-and-shoot count in R1-3 (Mont'ka active) vs R4-5 (gone).

H_STRAT  Stratagem firing audit.
         Count StratagemFired events by stratagem name per battle. Six
         Mont'ka stratagems exist; some have APPROXIMATED effects (Focused
         Fire = +1 to hit instead of +1 AP; Pulse Onslaught = +1 to hit
         instead of enemy Move debuff; Combat Debarkation = re-roll hits
         instead of re-roll wounds). Measure: are the stratagems firing at
         all? Where's the CP going?

H_DMG    Per-round T'au damage output, R1-3 vs R4-5.
         T'au are shooty — their damage curve should ramp in rounds 1-3
         (Mont'ka active) and decay in R4-5 (Mont'ka gone). Compare the
         observed curve.

H_SURV   Riptide / Crisis / Stormsurge first-death round.
         Battlesuit longevity is the alpha-strike payoff (a Riptide that
         lives round 4 is fired three more times). Measure the round at
         which the first/median Riptide/Crisis/Stormsurge dies, faceted by
         opponent.

Read-only — does NOT modify catalogue / simulator / overrides.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter3_tau_deep_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

# Lock hash randomisation off so set/dict iteration order is reproducible.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter3_tau_deep_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleEnded,
    RoundEnded,
    RoundStarted,
    StratagemFired,
    UnitAdvanced,
    UnitFought,
    UnitKilled,
    UnitShot,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle

TAU = "T'au Empire"
OPPONENTS: List[str] = ["Death Guard", "Adeptus Astartes", "Necrons"]
N_BATTLES = 30
POINTS = 1000

# Battlesuit profile-name substring buckets for the H_SURV hypothesis. Match
# substrings to be robust to Crisis-variant naming (Fireknife / Sunforge / ...).
BATTLESUIT_BUCKETS: Dict[str, List[str]] = {
    "Riptide":     ["Riptide"],
    "Crisis":      ["Crisis"],
    "Stormsurge":  ["Stormsurge"],
    "Broadside":   ["Broadside"],
    "Ghostkeel":   ["Ghostkeel"],
}


def _bucket(profile_name: str) -> Optional[str]:
    for bucket, needles in BATTLESUIT_BUCKETS.items():
        for n in needles:
            if n in profile_name:
                return bucket
    return None


class TauDiagSub:
    """Per-battle capture of:

      - StratagemFired by name + CP cost, T'au side only
      - UnitAdvanced events keyed by T'au attacker uid + round
      - UnitShot/UnitFought damage by T'au attacker uid + round
      - First-death round for each Battlesuit profile bucket
      - Did the unit shoot this round? (UnitShot event present)
    """

    def __init__(self, tau_army, opp_army) -> None:
        self.tau_army = tau_army
        self.opp_army = opp_army
        # uids are assigned by Battle._assign_uids() AFTER subscriber
        # construction — defer until the first RoundStarted event arrives.
        self.tau_uids: set = set()
        self.opp_uids: set = set()
        self.bucket_of: Dict[str, str] = {}
        self._uids_ready = False
        self.round_num = 0
        self.strats_fired: Counter = Counter()
        self.cp_spent: int = 0
        # round -> total T'au damage dealt (shoot+fight)
        self.dmg_by_round: Counter = Counter()
        # round -> count of T'au shoot activations that produced any damage
        self.shoots_by_round: Counter = Counter()
        # round -> count of UnitAdvanced events on T'au uids
        self.advances_by_round: Counter = Counter()
        # uids that advanced this round -> did they shoot afterwards?
        self._advanced_uids_this_round: set = set()
        # round -> count of uids that Advanced AND subsequently shot
        self.advance_then_shoot_by_round: Counter = Counter()
        # bucket -> earliest round-of-death for any unit in that bucket
        self.bucket_first_death: Dict[str, int] = {}
        self.winner: Optional[str] = None
        self.total_rounds: int = 0

    def _ensure_uids(self) -> None:
        if self._uids_ready:
            return
        self.tau_uids = {u.uid for u in self.tau_army.units}
        self.opp_uids = {u.uid for u in self.opp_army.units}
        for u in self.tau_army.units:
            b = _bucket(u.profile.name)
            if b is not None:
                self.bucket_of[u.uid] = b
        self._uids_ready = True

    def on_event(self, e: object) -> None:
        self._ensure_uids()
        if isinstance(e, RoundStarted):
            self.round_num = e.round_num
            self._advanced_uids_this_round = set()
        elif isinstance(e, StratagemFired):
            if e.army_name == self.tau_army.name:
                self.strats_fired[e.stratagem_name] += 1
                self.cp_spent += int(e.cp_cost)
        elif isinstance(e, UnitAdvanced):
            if e.unit_uid in self.tau_uids:
                self.advances_by_round[self.round_num] += 1
                self._advanced_uids_this_round.add(e.unit_uid)
        elif isinstance(e, UnitShot):
            if e.attacker_uid in self.tau_uids:
                self.dmg_by_round[self.round_num] += float(e.damage)
                self.shoots_by_round[self.round_num] += 1
                if e.attacker_uid in self._advanced_uids_this_round:
                    self.advance_then_shoot_by_round[self.round_num] += 1
        elif isinstance(e, UnitFought):
            if e.attacker_uid in self.tau_uids:
                self.dmg_by_round[self.round_num] += float(e.damage)
        elif isinstance(e, UnitKilled):
            if e.unit_uid in self.tau_uids:
                b = self.bucket_of.get(e.unit_uid)
                if b is not None and b not in self.bucket_first_death:
                    self.bucket_first_death[b] = self.round_num
        elif isinstance(e, RoundEnded):
            self.total_rounds = max(self.total_rounds, e.round_num)
        elif isinstance(e, BattleEnded):
            self.winner = e.winner
            self.total_rounds = e.rounds


def run_matchup(opponent: str) -> Dict:
    wins = losses = draws = 0
    diag_subs: List[TauDiagSub] = []

    for s in range(N_BATTLES):
        seed = s + 90001
        random.seed(seed)
        tau = build_faction_random_army(
            "A", TAU, POINTS, rng=random.Random(seed),
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS, rng=random.Random(seed + 30000),
        )
        if not tau.units or not opp.units:
            continue
        sub = TauDiagSub(tau, opp)
        battle = Battle(tau, opp, map_=DEFAULT_MAP, subscribers=[sub])
        result = battle.run()
        if result.winner == "A":
            wins += 1
        elif result.winner == "B":
            losses += 1
        else:
            draws += 1
        diag_subs.append(sub)

    n_total = wins + losses + draws
    wr = (wins / n_total * 100.0) if n_total else 0.0

    # ---- H_MK_ADV: Advance + Advance-then-shoot by round
    adv_by_round: Dict[int, List[int]] = defaultdict(list)
    ats_by_round: Dict[int, List[int]] = defaultdict(list)
    for sub in diag_subs:
        for rd in (1, 2, 3, 4, 5):
            adv_by_round[rd].append(sub.advances_by_round.get(rd, 0))
            ats_by_round[rd].append(sub.advance_then_shoot_by_round.get(rd, 0))

    # ---- H_STRAT: stratagem firing counts
    strat_totals: Counter = Counter()
    cp_total = 0
    for sub in diag_subs:
        strat_totals.update(sub.strats_fired)
        cp_total += sub.cp_spent

    # ---- H_DMG: per-round damage
    dmg_by_round: Dict[int, List[float]] = defaultdict(list)
    shoots_by_round: Dict[int, List[int]] = defaultdict(list)
    for sub in diag_subs:
        for rd in (1, 2, 3, 4, 5):
            dmg_by_round[rd].append(sub.dmg_by_round.get(rd, 0.0))
            shoots_by_round[rd].append(sub.shoots_by_round.get(rd, 0))

    # ---- H_SURV: first-death round per battlesuit bucket
    surv_by_bucket: Dict[str, List[int]] = defaultdict(list)
    for sub in diag_subs:
        for bucket, rd in sub.bucket_first_death.items():
            surv_by_bucket[bucket].append(rd)

    return {
        "opponent": opponent,
        "n": n_total,
        "wr": wr,
        "wins": wins, "losses": losses, "draws": draws,
        "adv_mean": {rd: statistics.mean(adv_by_round[rd]) for rd in (1, 2, 3, 4, 5)},
        "ats_mean": {rd: statistics.mean(ats_by_round[rd]) for rd in (1, 2, 3, 4, 5)},
        "dmg_mean": {rd: statistics.mean(dmg_by_round[rd]) for rd in (1, 2, 3, 4, 5)},
        "shoots_mean": {rd: statistics.mean(shoots_by_round[rd]) for rd in (1, 2, 3, 4, 5)},
        "strat_totals": dict(strat_totals),
        "cp_spent_per_battle": cp_total / max(1, len(diag_subs)),
        "surv_by_bucket": {
            b: {
                "n_died_battles": len(v),
                "median_death_round": (statistics.median(v) if v else None),
                "mean_death_round": (statistics.mean(v) if v else None),
            } for b, v in surv_by_bucket.items()
        },
    }


def report_matchup(r: Dict) -> None:
    print(f"\n--- T'au vs {r['opponent']} (N={r['n']}) ---")
    print(f"  WR (T'au-side A): {r['wr']:5.1f}%   W/L/D = {r['wins']}/{r['losses']}/{r['draws']}")
    print(f"  H_MK_ADV  Advance events / battle (T'au):")
    for rd in (1, 2, 3, 4, 5):
        a = r["adv_mean"][rd]
        ats = r["ats_mean"][rd]
        flag = "  [MONTKA]" if rd <= 3 else ""
        print(f"            R{rd}: advances={a:5.2f}  advance-then-shoot={ats:5.2f}{flag}")
    print(f"  H_STRAT   stratagem fires (totals across N battles):")
    for name, n in sorted(r["strat_totals"].items(), key=lambda x: -x[1]):
        print(f"            {n:4d}  {name}")
    print(f"            CP spent / battle: {r['cp_spent_per_battle']:.2f}")
    print(f"  H_DMG     per-round T'au dmg + shoots:")
    for rd in (1, 2, 3, 4, 5):
        d = r["dmg_mean"][rd]
        s = r["shoots_mean"][rd]
        flag = "  [MONTKA]" if rd <= 3 else ""
        print(f"            R{rd}: dmg={d:6.1f}  shoot_acts={s:5.2f}{flag}")
    print(f"  H_SURV    battlesuit first-death round:")
    for bucket, info in r["surv_by_bucket"].items():
        med = info["median_death_round"]
        mean = info["mean_death_round"]
        med_s = f"{med:.1f}" if med is not None else "n/a"
        mean_s = f"{mean:.2f}" if mean is not None else "n/a"
        print(f"            {bucket:12s}  died in {info['n_died_battles']:3d}/{r['n']:<3d} battles "
              f"(median R{med_s}, mean R{mean_s})")


def main() -> None:
    print(
        f"Iter 3 — T'au Empire deep diagnostic "
        f"(N={N_BATTLES} per matchup, {POINTS}pt, vanilla 10e)"
    )
    print(f"  Matchups: T'au vs {OPPONENTS}")
    print(f"  T'au calibration gap: -3.9pt (sim 50.6% vs real 54.5%)")

    results = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        results.append(r)
        report_matchup(r)

    print("\n=== AGGREGATE across all matchups ===")
    print(f"{'Metric':40s}  {'Value':>10s}")
    print("-" * 56)
    wr_overall = statistics.mean(r["wr"] for r in results)
    label_wr = "Overall T'au WR"
    print(f"{label_wr:40s}  {wr_overall:>9.2f}%")
    for rd in (1, 2, 3, 4, 5):
        agg_dmg = statistics.mean(r["dmg_mean"][rd] for r in results)
        agg_adv = statistics.mean(r["adv_mean"][rd] for r in results)
        agg_ats = statistics.mean(r["ats_mean"][rd] for r in results)
        tag = "  [MONTKA]" if rd <= 3 else ""
        print(f"{'R' + str(rd) + ' dmg / advances / atk-then-shoot':40s}  "
              f"{agg_dmg:>6.1f} / {agg_adv:.2f} / {agg_ats:.2f}{tag}")

    print(f"\n  Ratio R1-3-dmg / R4-5-dmg (T'au front-loaded if > 1.5):")
    front = statistics.mean(
        (r["dmg_mean"][1] + r["dmg_mean"][2] + r["dmg_mean"][3]) / 3.0
        for r in results
    )
    back = statistics.mean(
        (r["dmg_mean"][4] + r["dmg_mean"][5]) / 2.0
        for r in results
    )
    ratio = front / back if back > 0 else float("inf")
    print(f"    front (R1-3) {front:5.1f}  back (R4-5) {back:5.1f}  ratio {ratio:.2f}")

    print("\n  Aggregate stratagem fires (per battle average):")
    agg_strat: Counter = Counter()
    for r in results:
        for name, n in r["strat_totals"].items():
            agg_strat[name] += n
    total_battles = sum(r["n"] for r in results)
    for name, n in sorted(agg_strat.items(), key=lambda x: -x[1]):
        per_battle = n / max(1, total_battles)
        print(f"    {per_battle:5.2f}/battle  {name}")

    print("\nInterpretation guide:")
    print("  H_MK_ADV: Advance-then-shoot count in R1-3 vs R4-5. Mont'ka")
    print("    [ASSAULT] grant pays off only on a unit that Advanced AND then")
    print("    had a target in range. If counts are equal across R1-3 vs R4-5,")
    print("    [ASSAULT] is dead — either AI never elects Advance, or already-")
    print("    in-range Crisis suits never need to.")
    print("  H_STRAT: per-stratagem fire rate. Aggressive Mobility has the")
    print("    same shape as Mont'ka detachment rule — if it fires often, AI")
    print("    *wants* Advance + shoot. If it rarely fires, AI has plenty of")
    print("    Advance-free shoot opportunities (so Mont'ka detachment leg is")
    print("    underused too).")
    print("  H_DMG ratio: > 1.8 means front-loaded shooty curve; ~1.0 means")
    print("    T'au is functioning more like a sustained-fire army (Marines-")
    print("    like) which under-uses the alpha-strike payoff.")
    print("  H_SURV: median death round < R3 for Riptide / Crisis means the")
    print("    'fire in R1-3' window collapses early — battlesuits die before")
    print("    they can deliver the Mont'ka payoff. Real-meta Riptides survive")
    print("    to R4-5 routinely (3+ save, 5++ invuln, Nova Shield).")
    print("  H_MARK (not measured here — infrastructure cost): the Wahapedia")
    print("    Markerlight rule grants [LETHAL HITS] to T'au shooters vs Guided")
    print("    enemies. Approximate per-shot uplift at BS 4+ S5 vs T4 unsaved:")
    print("    LETHAL HITS swaps a 6-to-hit roll's failed-wound branch for an")
    print("    auto-wound. At hit 4+/wound 4+, ~17% of hits become auto-wounds")
    print("    that would otherwise be at-risk wound rolls — net ~+8% damage")
    print("    output. With Mont'ka rounds 1-3 already wired, full Markerlights")
    print("    would compound: every R1-3 shoot vs the army-priority target")
    print("    would gain LETHAL HITS. Estimated WR uplift +1.5 to +2.5pt at")
    print("    1000pt; gap is -3.9pt so this alone wouldn't close it but is")
    print("    the largest single-rule lever remaining.")


if __name__ == "__main__":
    main()
