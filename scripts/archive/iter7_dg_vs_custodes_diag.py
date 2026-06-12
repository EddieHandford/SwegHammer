"""Auto-loop iter 7 — DG vs Adeptus Custodes deep diagnostic.

Iter-5 finding: DG vs Custodes is the biggest DG over-perform in the
unsampled slice — simulator WR 76.7% vs real-meta ~48% (+28.7pt). The
shape is paradoxical: DG LOSES the damage race 36.3 vs 89.3 yet wins
76.7% of battles because Custodes only ships ~30 models and cannot
park enough OC tokens on enough markers to break the Worldblight
sticky fallback (sticky-VP 16.7/battle — the highest in the slice).

This iter-7 script samples N=40 vanilla DG-vs-Custodes battles and
captures the five required signals:

  1. Per-round VP source: sticky-attributed (DG scored at 0 OC,
     Worldblight fallback) vs killing-attributed proxy vs primary
     contest (DG scored with a_oc > b_oc).
  2. Custodes OC capacity vs DG sticky markers — how much OC does
     Custodes field on average per objective they reach vs how many
     markers are DG sticky-claimed per round.
  3. Custodes stratagem usage + CP spend per battle (Custodes has NO
     Shield Host detachment stratagems registered — only universal
     core stratagems, so this measures whether Custodes is spending
     CP at all).
  4. Plague Marines vs Custodian Guard damage exchange specifically
     (filter the dmg-in / dmg-out traces to just those two profiles).
  5. SHIELD_HOST.plus_one_save — currently APPROXIMATION (defensive
     save buff substituting for the real Martial Mastery offensive
     Critical Hit / AP buff). Measure how often the buff applies and
     how many opp wounds it actually saves on Custodes units.

Read-only. No catalogue / strategy / simulator mutation. N=40 battles,
1000 pts, archetype builder OFF (use_archetype=False), vanilla 10e.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter7_dg_vs_custodes_diag

Never runs the eval suite. Never edits anything.
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import defaultdict
from typing import Dict, List, Optional

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter7_dg_vs_custodes_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleshockFailed,
    ObjectiveScored,
    RoundEnded,
    RoundStarted,
    StratagemFired,
    UnitFought,
    UnitKilled,
    UnitShot,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle


N_BATTLES = 40
POINTS = 1000


class IT7Trace:
    """Iter-7 subscriber for DG vs Custodes deep diagnostic."""

    def __init__(self, dg_army: str, opp_army: str) -> None:
        self.dg_army = dg_army
        self.opp_army = opp_army
        self.current_round = 0
        # VP / objective accounting.
        self.dg_vp_round: List[int] = [0] * 6
        self.opp_vp_round: List[int] = [0] * 6
        self._last_dg_vp = 0
        self._last_opp_vp = 0
        # VP source breakdown for DG per round.
        self.dg_sticky_vp_round: List[int] = [0] * 6   # a_oc == 0 AND b_oc == 0
        self.dg_primary_vp_round: List[int] = [0] * 6  # a_oc > b_oc
        self.dg_sticky_vp_total: int = 0
        self.dg_primary_vp_total: int = 0
        # OC samples — for each ObjectiveScored event, log opp OC on that obj.
        # Custodes' realised OC presence on contested DG markers.
        self.opp_oc_samples_round: List[List[int]] = [[] for _ in range(6)]
        # Damage exchange per round.
        self.dmg_dg_to_opp: List[float] = [0.0] * 6
        self.dmg_opp_to_dg: List[float] = [0.0] * 6
        # PM <-> Custodian Guard specific damage.
        self.dmg_pm_to_cg: List[float] = [0.0] * 6
        self.dmg_cg_to_pm: List[float] = [0.0] * 6
        self.cg_models_killed_by_pm: int = 0
        self.pm_models_killed_by_cg: int = 0
        # Kill totals.
        self.kills_dg: List[int] = [0] * 6
        self.kills_opp: List[int] = [0] * 6
        # CP / stratagem economy.
        self.cp_dg_round: List[int] = [0] * 6
        self.cp_opp_round: List[int] = [0] * 6
        self.dg_strat_rounds: Dict[str, List[int]] = {}
        self.opp_strat_rounds: Dict[str, List[int]] = {}
        # Battleshock fails (proxy for Contagion -1Ld pressure).
        self.bs_fail_dg_round: List[int] = [0] * 6
        self.bs_fail_opp_round: List[int] = [0] * 6
        # SHIELD_HOST.plus_one_save firings — count opp shooting / fight events
        # that targeted a Custodes unit (the +1 save is always-on so every
        # incoming save vs Custodes models is "buffed"). We can't observe
        # the saved-wound count from outside the simulator without adding
        # an event; proxy = total dmg-into-Custodes is the upper bound on
        # what +1 save reduces.
        # uid bookkeeping.
        self.uid_army: Dict[str, str] = {}
        self.uid_profile_key: Dict[str, str] = {}
        self.uid_keywords: Dict[str, frozenset] = {}
        self.uid_min_models: Dict[str, int] = {}
        self.uid_faction: Dict[str, str] = {}
        # Tracked uid groups.
        self.plague_marine_uids: set = set()
        self.custodian_guard_uids: set = set()
        self.opp_battleline_uids: set = set()
        self.dg_vehicle_uids: set = set()
        self.pm_dead_round: List[int] = [0] * 6
        self.cg_dead_round: List[int] = [0] * 6
        self.opp_bl_dead_round: List[int] = [0] * 6
        # Track who's the last attacker for kill attribution.
        self._last_attacker_uid: Optional[str] = None
        self._last_attacker_army: Optional[str] = None
        # Total opp models (Custodes has very few).
        self.dg_total_models: int = 0
        self.opp_total_models: int = 0
        # Opp unit count (distinct units, not models).
        self.opp_unit_count: int = 0
        self.opp_move_speeds: List[int] = []

    def set_armies(self, dg_units, opp_units, dg_name, opp_name) -> None:
        for u in dg_units:
            self.uid_army[u.uid] = dg_name
            self.uid_profile_key[u.uid] = u.profile.name
            kw = frozenset(u.profile.unit_keywords or ())
            self.uid_keywords[u.uid] = kw
            self.uid_min_models[u.uid] = max(1, u.profile.min_models)
            self.uid_faction[u.uid] = u.profile.faction or ""
            self.dg_total_models += max(1, u.profile.min_models)
            if "Plague Marine" in u.profile.name:
                self.plague_marine_uids.add(u.uid)
            if "VEHICLE" in kw:
                self.dg_vehicle_uids.add(u.uid)
        for u in opp_units:
            self.uid_army[u.uid] = opp_name
            self.uid_profile_key[u.uid] = u.profile.name
            kw = frozenset(u.profile.unit_keywords or ())
            self.uid_keywords[u.uid] = kw
            self.uid_min_models[u.uid] = max(1, u.profile.min_models)
            self.uid_faction[u.uid] = u.profile.faction or ""
            self.opp_total_models += max(1, u.profile.min_models)
            self.opp_unit_count += 1
            self.opp_move_speeds.append(int(getattr(u.profile, "move", 0) or 0))
            if "Custodian Guard" in u.profile.name:
                self.custodian_guard_uids.add(u.uid)
            if "BATTLELINE" in kw:
                self.opp_battleline_uids.add(u.uid)

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
        elif isinstance(e, UnitShot):
            self._record_attack(e.attacker_uid, e.target_uid, e.damage)
        elif isinstance(e, UnitFought):
            self._record_attack(e.attacker_uid, e.target_uid, e.damage)
        elif isinstance(e, UnitKilled):
            atk_uid = self._last_attacker_uid
            atk_army = self._last_attacker_army
            rnd = max(0, min(5, self.current_round))
            if atk_army == self.dg_army:
                self.kills_dg[rnd] += 1
            elif atk_army == self.opp_army:
                self.kills_opp[rnd] += 1
            if e.unit_uid in self.plague_marine_uids:
                self.pm_dead_round[rnd] += 1
                if atk_uid in self.custodian_guard_uids:
                    self.pm_models_killed_by_cg += 1
            if e.unit_uid in self.custodian_guard_uids:
                self.cg_dead_round[rnd] += 1
                if atk_uid in self.plague_marine_uids:
                    self.cg_models_killed_by_pm += 1
            if e.unit_uid in self.opp_battleline_uids:
                self.opp_bl_dead_round[rnd] += 1
        elif isinstance(e, StratagemFired):
            rnd = max(0, min(5, self.current_round))
            cost = int(e.cp_cost)
            if e.army_name == self.dg_army:
                self.cp_dg_round[rnd] += cost
                self.dg_strat_rounds.setdefault(e.stratagem_name, [0] * 6)[rnd] += 1
            elif e.army_name == self.opp_army:
                self.cp_opp_round[rnd] += cost
                self.opp_strat_rounds.setdefault(e.stratagem_name, [0] * 6)[rnd] += 1
        elif isinstance(e, BattleshockFailed):
            rnd = max(0, min(5, self.current_round))
            fail_army = self.uid_army.get(e.unit_uid, "")
            if fail_army == self.dg_army:
                self.bs_fail_dg_round[rnd] += 1
            elif fail_army == self.opp_army:
                self.bs_fail_opp_round[rnd] += 1
        elif isinstance(e, ObjectiveScored):
            rnd = max(0, min(5, self.current_round))
            if e.army_name == self.dg_army:
                if e.a_oc == 0 and e.b_oc == 0 and e.vp_awarded > 0:
                    self.dg_sticky_vp_round[rnd] += e.vp_awarded
                    self.dg_sticky_vp_total += e.vp_awarded
                elif e.a_oc > e.b_oc and e.vp_awarded > 0:
                    self.dg_primary_vp_round[rnd] += e.vp_awarded
                    self.dg_primary_vp_total += e.vp_awarded
            # Sample opp OC on every scored objective regardless of scorer.
            # Question: is Custodes EVER on a marker DG sticky-claims?
            self.opp_oc_samples_round[rnd].append(e.b_oc)
        elif isinstance(e, RoundEnded):
            rnd = max(0, min(5, self.current_round))
            self.dg_vp_round[rnd] = e.a_vp_total - self._last_dg_vp
            self.opp_vp_round[rnd] = e.b_vp_total - self._last_opp_vp
            self._last_dg_vp = e.a_vp_total
            self._last_opp_vp = e.b_vp_total

    def _record_attack(self, attacker_uid: str, target_uid: str, damage: float) -> None:
        a_army = self.uid_army.get(attacker_uid)
        t_army = self.uid_army.get(target_uid)
        rnd = max(0, min(5, self.current_round))
        if a_army == self.dg_army and t_army == self.opp_army:
            self.dmg_dg_to_opp[rnd] += damage
            if (
                attacker_uid in self.plague_marine_uids
                and target_uid in self.custodian_guard_uids
            ):
                self.dmg_pm_to_cg[rnd] += damage
        elif a_army == self.opp_army and t_army == self.dg_army:
            self.dmg_opp_to_dg[rnd] += damage
            if (
                attacker_uid in self.custodian_guard_uids
                and target_uid in self.plague_marine_uids
            ):
                self.dmg_cg_to_pm[rnd] += damage
        self._last_attacker_uid = attacker_uid
        self._last_attacker_army = a_army


def fmt_row(vals, fmt="6.2f"):
    return " ".join(f"R{i}:{vals[i]:{fmt}}" for i in range(1, 6))


def main() -> None:
    dg = "Death Guard"
    opp = "Adeptus Custodes"
    print(f"Iter 7 — DG vs Custodes deep diag. N={N_BATTLES}, {POINTS} pts, vanilla.")
    print("=" * 100)

    wins = 0
    losses = 0
    draws = 0
    dg_vp_list: List[int] = []
    opp_vp_list: List[int] = []
    rounds_played: List[int] = []
    dg_vp_round_acc = [0.0] * 6
    opp_vp_round_acc = [0.0] * 6
    sticky_vp_round_acc = [0.0] * 6
    primary_vp_round_acc = [0.0] * 6
    dmg_dg_acc = [0.0] * 6
    dmg_opp_acc = [0.0] * 6
    dmg_pm_to_cg_acc = [0.0] * 6
    dmg_cg_to_pm_acc = [0.0] * 6
    kills_dg_acc = [0.0] * 6
    kills_opp_acc = [0.0] * 6
    cp_dg_acc = [0.0] * 6
    cp_opp_acc = [0.0] * 6
    pm_dead_acc = [0.0] * 6
    cg_dead_acc = [0.0] * 6
    opp_bl_dead_acc = [0.0] * 6
    bs_fail_dg_acc = [0.0] * 6
    bs_fail_opp_acc = [0.0] * 6
    dg_strat_acc: Dict[str, List[float]] = defaultdict(lambda: [0.0] * 6)
    opp_strat_acc: Dict[str, List[float]] = defaultdict(lambda: [0.0] * 6)
    sticky_total_list: List[int] = []
    primary_total_list: List[int] = []
    opp_oc_samples_all: List[List[int]] = [[] for _ in range(6)]
    pm_total_models_list: List[int] = []
    cg_total_models_list: List[int] = []
    cg_killed_by_pm_total = 0
    pm_killed_by_cg_total = 0
    dg_models_list: List[int] = []
    opp_models_list: List[int] = []
    opp_unit_count_list: List[int] = []
    opp_move_speed_means: List[float] = []
    dmg_pm_to_cg_total_list: List[float] = []
    dmg_cg_to_pm_total_list: List[float] = []
    # Track raw Custodes total dmg taken — proxy for SHIELD_HOST.plus_one_save
    # effective workload.
    dmg_taken_by_custodes_list: List[float] = []

    for s in range(N_BATTLES):
        seed = s + 70007
        random.seed(seed)
        a_rng = random.Random(seed)
        b_rng = random.Random(seed + 90000)
        a = build_faction_random_army(
            "A_DG", dg, POINTS, rng=a_rng, use_archetype=False,
        )
        b = build_faction_random_army(
            "B_AC", opp, POINTS, rng=b_rng, use_archetype=False,
        )
        if not a.units or not b.units:
            continue

        sub = IT7Trace(a.name, b.name)
        battle = Battle(a, b, map_=DEFAULT_MAP, subscribers=[sub])
        battle._assign_uids()
        sub.set_armies(list(a.units), list(b.units), a.name, b.name)
        r = battle.run()
        if r.winner == a.name:
            wins += 1
        elif r.winner == b.name:
            losses += 1
        else:
            draws += 1
        rounds_played.append(r.rounds)
        dg_vp_list.append(sub._last_dg_vp)
        opp_vp_list.append(sub._last_opp_vp)
        for i in range(6):
            dg_vp_round_acc[i] += sub.dg_vp_round[i]
            opp_vp_round_acc[i] += sub.opp_vp_round[i]
            sticky_vp_round_acc[i] += sub.dg_sticky_vp_round[i]
            primary_vp_round_acc[i] += sub.dg_primary_vp_round[i]
            dmg_dg_acc[i] += sub.dmg_dg_to_opp[i]
            dmg_opp_acc[i] += sub.dmg_opp_to_dg[i]
            dmg_pm_to_cg_acc[i] += sub.dmg_pm_to_cg[i]
            dmg_cg_to_pm_acc[i] += sub.dmg_cg_to_pm[i]
            kills_dg_acc[i] += sub.kills_dg[i]
            kills_opp_acc[i] += sub.kills_opp[i]
            cp_dg_acc[i] += sub.cp_dg_round[i]
            cp_opp_acc[i] += sub.cp_opp_round[i]
            pm_dead_acc[i] += sub.pm_dead_round[i]
            cg_dead_acc[i] += sub.cg_dead_round[i]
            opp_bl_dead_acc[i] += sub.opp_bl_dead_round[i]
            bs_fail_dg_acc[i] += sub.bs_fail_dg_round[i]
            bs_fail_opp_acc[i] += sub.bs_fail_opp_round[i]
            opp_oc_samples_all[i].extend(sub.opp_oc_samples_round[i])
        for name, rounds in sub.dg_strat_rounds.items():
            for i in range(6):
                dg_strat_acc[name][i] += rounds[i]
        for name, rounds in sub.opp_strat_rounds.items():
            for i in range(6):
                opp_strat_acc[name][i] += rounds[i]
        sticky_total_list.append(sub.dg_sticky_vp_total)
        primary_total_list.append(sub.dg_primary_vp_total)
        pm_total = sum(sub.uid_min_models[uid] for uid in sub.plague_marine_uids) \
            if sub.plague_marine_uids else 0
        cg_total = sum(sub.uid_min_models[uid] for uid in sub.custodian_guard_uids) \
            if sub.custodian_guard_uids else 0
        pm_total_models_list.append(pm_total)
        cg_total_models_list.append(cg_total)
        cg_killed_by_pm_total += sub.cg_models_killed_by_pm
        pm_killed_by_cg_total += sub.pm_models_killed_by_cg
        dg_models_list.append(sub.dg_total_models)
        opp_models_list.append(sub.opp_total_models)
        opp_unit_count_list.append(sub.opp_unit_count)
        if sub.opp_move_speeds:
            opp_move_speed_means.append(
                statistics.mean(sub.opp_move_speeds)
            )
        dmg_pm_to_cg_total_list.append(sum(sub.dmg_pm_to_cg))
        dmg_cg_to_pm_total_list.append(sum(sub.dmg_cg_to_pm))
        dmg_taken_by_custodes_list.append(sum(sub.dmg_dg_to_opp))

    n_total = wins + losses + draws
    wr = 100.0 * wins / n_total if n_total else 0.0
    norm = float(n_total) if n_total else 1.0
    def per(lst): return [x / norm for x in lst]

    # ----- Headline -----
    print(f"\n## Headline")
    print(
        f"WR DG = {wr:.1f}%  ({wins}-{losses}-{draws})  "
        f"rounds avg {statistics.mean(rounds_played):.2f}"
    )
    print(
        f"DG VP avg {statistics.mean(dg_vp_list):.1f}  "
        f"Custodes VP avg {statistics.mean(opp_vp_list):.1f}  "
        f"gap {statistics.mean(dg_vp_list) - statistics.mean(opp_vp_list):+.1f}"
    )
    print(
        f"Army size: DG models {statistics.mean(dg_models_list):.1f}  "
        f"Custodes models {statistics.mean(opp_models_list):.1f}  "
        f"Custodes units {statistics.mean(opp_unit_count_list):.1f}"
    )
    if opp_move_speed_means:
        print(
            f"Custodes avg move (across units): "
            f"{statistics.mean(opp_move_speed_means):.1f}\""
        )

    # ----- 1. VP source per round -----
    print(f"\n## 1. VP source breakdown (DG, averaged across {N_BATTLES} battles)")
    print(f"  [DG VP/rnd total]      {fmt_row(per(dg_vp_round_acc))}  | sum {sum(per(dg_vp_round_acc)):.2f}")
    print(f"  [DG sticky-VP (0/0)]   {fmt_row(per(sticky_vp_round_acc))}  | sum {sum(per(sticky_vp_round_acc)):.2f}")
    print(f"  [DG primary (a>b)]     {fmt_row(per(primary_vp_round_acc))}  | sum {sum(per(primary_vp_round_acc)):.2f}")
    print(f"  [Custodes VP/rnd]      {fmt_row(per(opp_vp_round_acc))}  | sum {sum(per(opp_vp_round_acc)):.2f}")
    sticky_share = (
        100.0 * statistics.mean(sticky_total_list)
        / max(1.0, statistics.mean(dg_vp_list))
    )
    primary_share = (
        100.0 * statistics.mean(primary_total_list)
        / max(1.0, statistics.mean(dg_vp_list))
    )
    print(
        f"  Sticky share of DG VP:  {sticky_share:.1f}%  "
        f"Primary-contest share:  {primary_share:.1f}%  "
        f"(remainder = secondaries / not-objective)"
    )
    print(
        f"  sticky-VP/battle mean = {statistics.mean(sticky_total_list):.2f}  "
        f"stdev = {statistics.stdev(sticky_total_list) if len(sticky_total_list)>1 else 0:.2f}"
    )

    # ----- 2. Custodes OC capacity -----
    print(f"\n## 2. Custodes OC presence on scored objectives, per round")
    for i in range(1, 6):
        samples = opp_oc_samples_all[i]
        if not samples:
            print(f"  R{i}: no samples")
            continue
        zero = sum(1 for x in samples if x == 0)
        low = sum(1 for x in samples if 1 <= x <= 3)
        mid = sum(1 for x in samples if 4 <= x <= 7)
        high = sum(1 for x in samples if x > 7)
        print(
            f"  R{i}: n={len(samples):4d}  "
            f"AC OC=0: {100*zero/len(samples):5.1f}%  "
            f"OC 1-3: {100*low/len(samples):5.1f}%  "
            f"OC 4-7: {100*mid/len(samples):5.1f}%  "
            f"OC >7: {100*high/len(samples):5.1f}%  "
            f"mean OC = {statistics.mean(samples):.2f}"
        )

    # ----- 3. Custodes stratagems + CP -----
    print(f"\n## 3. Stratagem economy")
    dg_strat_total = sum(sum(v) for v in dg_strat_acc.values())
    opp_strat_total = sum(sum(v) for v in opp_strat_acc.values())
    print(
        f"  DG strat fires/battle:       {dg_strat_total/norm:.2f}  "
        f"CP spent/battle: {sum(cp_dg_acc)/norm:.2f}"
    )
    print(
        f"  Custodes strat fires/battle: {opp_strat_total/norm:.2f}  "
        f"CP spent/battle: {sum(cp_opp_acc)/norm:.2f}"
    )
    print(f"  DG stratagems by name (per-battle avg):")
    for name, rounds in sorted(
        dg_strat_acc.items(), key=lambda kv: -sum(kv[1]),
    ):
        total = sum(rounds) / norm
        if total < 0.02:
            continue
        per_round = [x / norm for x in rounds]
        print(f"    {name:32s} {fmt_row(per_round, '5.2f')}  /battle={total:.2f}")
    print(f"  Custodes stratagems by name (per-battle avg):")
    for name, rounds in sorted(
        opp_strat_acc.items(), key=lambda kv: -sum(kv[1]),
    ):
        total = sum(rounds) / norm
        if total < 0.02:
            continue
        per_round = [x / norm for x in rounds]
        print(f"    {name:32s} {fmt_row(per_round, '5.2f')}  /battle={total:.2f}")

    # ----- 4. Plague Marines vs Custodian Guard -----
    print(f"\n## 4. Plague Marines vs Custodian Guard damage exchange")
    print(
        f"  PM total models avg = {statistics.mean(pm_total_models_list):.1f}  "
        f"CG total models avg = {statistics.mean(cg_total_models_list):.1f}"
    )
    print(
        f"  [dmg PM->CG /rnd]    {fmt_row(per(dmg_pm_to_cg_acc))}  "
        f"| total {sum(per(dmg_pm_to_cg_acc)):.2f}"
    )
    print(
        f"  [dmg CG->PM /rnd]    {fmt_row(per(dmg_cg_to_pm_acc))}  "
        f"| total {sum(per(dmg_cg_to_pm_acc)):.2f}"
    )
    print(
        f"  CG models killed BY PM total = {cg_killed_by_pm_total}  "
        f"({cg_killed_by_pm_total/norm:.2f}/battle)"
    )
    print(
        f"  PM models killed BY CG total = {pm_killed_by_cg_total}  "
        f"({pm_killed_by_cg_total/norm:.2f}/battle)"
    )
    pm_dmg_per_model = (
        sum(per(dmg_pm_to_cg_acc)) / max(1, statistics.mean(pm_total_models_list))
    )
    cg_dmg_per_model = (
        sum(per(dmg_cg_to_pm_acc)) / max(1, statistics.mean(cg_total_models_list))
    )
    print(
        f"  Efficiency: dmg PM->CG per PM model = {pm_dmg_per_model:.2f}  "
        f"vs dmg CG->PM per CG model = {cg_dmg_per_model:.2f}"
    )
    print(
        f"  [PM dead /rnd]       {fmt_row(per(pm_dead_acc), '5.2f')}  "
        f"total {sum(per(pm_dead_acc)):.2f}"
    )
    print(
        f"  [CG dead /rnd]       {fmt_row(per(cg_dead_acc), '5.2f')}  "
        f"total {sum(per(cg_dead_acc)):.2f}"
    )

    # ----- 5. SHIELD_HOST.plus_one_save approximation -----
    print(f"\n## 5. SHIELD_HOST.plus_one_save (APPROXIMATION) signal")
    print(
        f"  Total dmg DG -> Custodes per battle = "
        f"{statistics.mean(dmg_taken_by_custodes_list):.2f}"
    )
    print(
        f"  Custodes models lost per battle (battleline) = "
        f"{sum(opp_bl_dead_acc) / norm:.2f}  "
        f"(of {statistics.mean(cg_total_models_list):.1f} CG starting)"
    )
    print(
        "  Approximation note: real rule is Martial Mastery — OFFENSIVE "
        "Crit Hit (5+) / +1 AP buff on melee, NOT a +1 save defensive buff."
    )
    print(
        "  Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/#Shield-Host"
    )

    # ----- Full damage / kill traces (for reference) -----
    print(f"\n## All-unit traces")
    print(f"  [dmg DG->opp /rnd]   {fmt_row(per(dmg_dg_acc))}  total {sum(per(dmg_dg_acc)):.2f}")
    print(f"  [dmg opp->DG /rnd]   {fmt_row(per(dmg_opp_acc))}  total {sum(per(dmg_opp_acc)):.2f}")
    print(f"  [kills DG /rnd]      {fmt_row(per(kills_dg_acc), '5.2f')}  total {sum(per(kills_dg_acc)):.2f}")
    print(f"  [kills opp /rnd]     {fmt_row(per(kills_opp_acc), '5.2f')}  total {sum(per(kills_opp_acc)):.2f}")
    print(f"  [BS fail opp /rnd]   {fmt_row(per(bs_fail_opp_acc), '5.2f')}  total {sum(per(bs_fail_opp_acc)):.2f}")
    print(f"  [BS fail DG /rnd]    {fmt_row(per(bs_fail_dg_acc), '5.2f')}  total {sum(per(bs_fail_dg_acc)):.2f}")


if __name__ == "__main__":
    main()
