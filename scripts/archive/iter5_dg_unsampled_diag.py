"""Auto-loop iter 5 — Death Guard diagnostic for the 7 UNSAMPLED matchups.

Iter-4 finding: the 3-opponent slice (DG vs Marines / Necrons / Tyranids) is
calibrated to 47.8% WR (real meta 48%) — so the +15.3pt DG residual on the
full eval lives in the OTHER 7 matchups (Aeldari, T'au, Orks, TSON, Custodes,
Votann, mirror).

This script samples N=30 vanilla battles for each of those 7 matchups and
captures:
  1. DG WR per matchup
  2. Damage in / out per round
  3. DG stratagem fires per battle (count, per-round, by name)
  4. Plague Marine survival vs opp BATTLELINE survival
  5. Sticky-attributed VP (DG VP scored at 0 OC — Worldblight fallback)
  6. Contagion-related signals (battleshock fails attributable to R2 -1Ld;
     R3+ dmg-suppression proxy via opp-dmg-late-rounds vs opp-dmg-early)
  7. Matchup-specific notes (low-model Custodes; chaff Aeldari T3; etc.)

Read-only. No catalogue / strategy / simulator mutation. Hard cap N=30 per
matchup, 7 opponents. Vanilla 10e rules, 1000 pts, archetype builder OFF
(use_archetype=False) — the curated archetypes regressed eval-vs-meta MAE
per the May-2026 calibration note in army_builder.py.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter5_dg_unsampled_diag

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
        [sys.executable, "-m", "scripts.iter5_dg_unsampled_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    BattleshockFailed,
    DeadlyDemiseExploded,
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


# The 7 unsampled matchups per iter-4 DG diagnostic.
UNSAMPLED_OPPS: List[str] = [
    "Aeldari",
    "T'au Empire",
    "Orks",
    "Thousand Sons",
    "Adeptus Custodes",
    "Leagues of Votann",
    "Death Guard",   # mirror
]
N_BATTLES = 30
POINTS = 1000


class DGTrace5:
    """Iter-5 subscriber. Same signal set as iter-4 plus battleshock-fail
    tracking (proxy for R2 Maladictive Pall / Contagion -1 Ld pressure)."""

    def __init__(self, dg_army: str, opp_army: str) -> None:
        self.dg_army = dg_army
        self.opp_army = opp_army
        self.current_round = 0
        self.dg_vp_round: List[int] = [0] * 6
        self.opp_vp_round: List[int] = [0] * 6
        self.dg_obj_vp_round: List[int] = [0] * 6
        self.opp_obj_vp_round: List[int] = [0] * 6
        self.dg_sticky_vp_round: List[int] = [0] * 6
        self._last_dg_vp = 0
        self._last_opp_vp = 0
        self.dmg_dg_to_opp: List[float] = [0.0] * 6
        self.dmg_opp_to_dg: List[float] = [0.0] * 6
        self.kills_dg: List[int] = [0] * 6
        self.kills_opp: List[int] = [0] * 6
        self.cp_dg_round: List[int] = [0] * 6
        self.cp_opp_round: List[int] = [0] * 6
        self.dg_strat_rounds: Dict[str, List[int]] = {}
        self.opp_strat_rounds: Dict[str, List[int]] = {}
        self.dg_strat_count: List[int] = [0] * 6
        self.opp_strat_count: List[int] = [0] * 6
        # Battleshock fails by army-of-failing-unit, per round.
        self.bs_fail_dg_round: List[int] = [0] * 6
        self.bs_fail_opp_round: List[int] = [0] * 6
        # uid bookkeeping.
        self.uid_army: Dict[str, str] = {}
        self.uid_profile_key: Dict[str, str] = {}
        self.uid_keywords: Dict[str, frozenset] = {}
        self.uid_min_models: Dict[str, int] = {}
        self.uid_faction: Dict[str, str] = {}
        # Tracked uid groups.
        self.plague_marine_uids: set = set()
        self.opp_battleline_uids: set = set()
        self.dg_vehicle_uids: set = set()
        self.dg_battleline_uids: set = set()
        self.pm_dead_round: List[int] = [0] * 6
        self.opp_bl_dead_round: List[int] = [0] * 6
        self.dg_veh_dead_round: List[int] = [0] * 6
        self.demise_mortals: int = 0
        self.demise_events: int = 0
        self._last_attacker_army: Optional[str] = None
        self.dg_sticky_vp_total: int = 0
        # Total model counts on each side at battle start (for chaff-density
        # signal — high-model opps stress DG less per-model than low-model).
        self.dg_total_models: int = 0
        self.opp_total_models: int = 0

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
            if "BATTLELINE" in kw:
                self.dg_battleline_uids.add(u.uid)
        for u in opp_units:
            self.uid_army[u.uid] = opp_name
            self.uid_profile_key[u.uid] = u.profile.name
            kw = frozenset(u.profile.unit_keywords or ())
            self.uid_keywords[u.uid] = kw
            self.uid_min_models[u.uid] = max(1, u.profile.min_models)
            self.uid_faction[u.uid] = u.profile.faction or ""
            self.opp_total_models += max(1, u.profile.min_models)
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
            atk = self._last_attacker_army
            rnd = max(0, min(5, self.current_round))
            if atk == self.dg_army:
                self.kills_dg[rnd] += 1
            elif atk == self.opp_army:
                self.kills_opp[rnd] += 1
            if e.unit_uid in self.plague_marine_uids:
                self.pm_dead_round[rnd] += 1
            if e.unit_uid in self.opp_battleline_uids:
                self.opp_bl_dead_round[rnd] += 1
            if e.unit_uid in self.dg_vehicle_uids:
                self.dg_veh_dead_round[rnd] += 1
        elif isinstance(e, StratagemFired):
            rnd = max(0, min(5, self.current_round))
            cost = int(e.cp_cost)
            if e.army_name == self.dg_army:
                self.cp_dg_round[rnd] += cost
                self.dg_strat_count[rnd] += 1
                self.dg_strat_rounds.setdefault(e.stratagem_name, [0] * 6)[rnd] += 1
            elif e.army_name == self.opp_army:
                self.cp_opp_round[rnd] += cost
                self.opp_strat_count[rnd] += 1
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
                self.dg_obj_vp_round[rnd] += e.vp_awarded
                if e.a_oc == 0 and e.vp_awarded > 0:
                    self.dg_sticky_vp_round[rnd] += e.vp_awarded
                    self.dg_sticky_vp_total += e.vp_awarded
            elif e.army_name == self.opp_army:
                self.opp_obj_vp_round[rnd] += e.vp_awarded
        elif isinstance(e, DeadlyDemiseExploded):
            if e.unit_uid in self.dg_vehicle_uids:
                self.demise_mortals += e.mortals
                self.demise_events += 1
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
        elif a_army == self.opp_army and t_army == self.dg_army:
            self.dmg_opp_to_dg[rnd] += damage
        self._last_attacker_army = a_army


def run_one_matchup(dg: str, opp: str) -> Dict:
    wins = 0
    losses = 0
    draws = 0
    dg_vp_list: List[int] = []
    opp_vp_list: List[int] = []
    rounds_played: List[int] = []
    vp_dg_by_round = [0.0] * 6
    vp_opp_by_round = [0.0] * 6
    obj_vp_dg_by_round = [0.0] * 6
    obj_vp_opp_by_round = [0.0] * 6
    sticky_vp_dg_by_round = [0.0] * 6
    dmg_dg_by_round = [0.0] * 6
    dmg_opp_by_round = [0.0] * 6
    kills_dg_by_round = [0.0] * 6
    kills_opp_by_round = [0.0] * 6
    cp_dg_by_round = [0.0] * 6
    cp_opp_by_round = [0.0] * 6
    pm_dead_by_round = [0.0] * 6
    opp_bl_dead_by_round = [0.0] * 6
    dg_veh_dead_by_round = [0.0] * 6
    bs_fail_dg_by_round = [0.0] * 6
    bs_fail_opp_by_round = [0.0] * 6
    dg_strat_fires_by_round: Dict[str, List[float]] = defaultdict(lambda: [0.0] * 6)
    opp_strat_fires_by_round: Dict[str, List[float]] = defaultdict(lambda: [0.0] * 6)
    demise_mortals_total = 0
    demise_events_total = 0
    sticky_vp_total: List[int] = []
    pm_squad_size: List[int] = []
    pm_dead_total: List[int] = []
    opp_bl_squad_size: List[int] = []
    opp_bl_dead_total: List[int] = []
    dg_total_models_list: List[int] = []
    opp_total_models_list: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 54321  # distinct seed offset from iter-4
        random.seed(seed)
        a_rng = random.Random(seed)
        b_rng = random.Random(seed + 70000)
        # For mirror: ensure unique army names so subscriber army-attribution
        # via name string still resolves both sides.
        a_name = "A_DG"
        b_name = "B_" + opp.replace(" ", "_").replace("'", "")
        a = build_faction_random_army(
            a_name, dg, POINTS, rng=a_rng, use_archetype=False,
        )
        b = build_faction_random_army(
            b_name, opp, POINTS, rng=b_rng, use_archetype=False,
        )
        if not a.units or not b.units:
            continue

        sub = DGTrace5(a.name, b.name)
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
            vp_dg_by_round[i] += sub.dg_vp_round[i]
            vp_opp_by_round[i] += sub.opp_vp_round[i]
            obj_vp_dg_by_round[i] += sub.dg_obj_vp_round[i]
            obj_vp_opp_by_round[i] += sub.opp_obj_vp_round[i]
            sticky_vp_dg_by_round[i] += sub.dg_sticky_vp_round[i]
            dmg_dg_by_round[i] += sub.dmg_dg_to_opp[i]
            dmg_opp_by_round[i] += sub.dmg_opp_to_dg[i]
            kills_dg_by_round[i] += sub.kills_dg[i]
            kills_opp_by_round[i] += sub.kills_opp[i]
            cp_dg_by_round[i] += sub.cp_dg_round[i]
            cp_opp_by_round[i] += sub.cp_opp_round[i]
            pm_dead_by_round[i] += sub.pm_dead_round[i]
            opp_bl_dead_by_round[i] += sub.opp_bl_dead_round[i]
            dg_veh_dead_by_round[i] += sub.dg_veh_dead_round[i]
            bs_fail_dg_by_round[i] += sub.bs_fail_dg_round[i]
            bs_fail_opp_by_round[i] += sub.bs_fail_opp_round[i]
        for name, rounds in sub.dg_strat_rounds.items():
            for i in range(6):
                dg_strat_fires_by_round[name][i] += rounds[i]
        for name, rounds in sub.opp_strat_rounds.items():
            for i in range(6):
                opp_strat_fires_by_round[name][i] += rounds[i]
        demise_mortals_total += sub.demise_mortals
        demise_events_total += sub.demise_events
        sticky_vp_total.append(sub.dg_sticky_vp_total)
        pm_total = sum(sub.uid_min_models[uid] for uid in sub.plague_marine_uids) \
            if sub.plague_marine_uids else 0
        pm_squad_size.append(pm_total)
        pm_dead_total.append(sum(sub.pm_dead_round))
        bl_total = sum(sub.uid_min_models[uid] for uid in sub.opp_battleline_uids) \
            if sub.opp_battleline_uids else 0
        opp_bl_squad_size.append(bl_total)
        opp_bl_dead_total.append(sum(sub.opp_bl_dead_round))
        dg_total_models_list.append(sub.dg_total_models)
        opp_total_models_list.append(sub.opp_total_models)

    n_total = wins + losses + draws
    wr = 100.0 * wins / n_total if n_total else 0.0
    norm = float(n_total) if n_total else 1.0

    def _per(lst):
        return [x / norm for x in lst]

    dg_strat_avg = {k: [x / norm for x in v] for k, v in dg_strat_fires_by_round.items()}
    opp_strat_avg = {k: [x / norm for x in v] for k, v in opp_strat_fires_by_round.items()}

    pm_total_models = sum(pm_squad_size)
    pm_total_dead = sum(pm_dead_total)
    pm_survival = (
        100.0 * (pm_total_models - pm_total_dead) / pm_total_models
        if pm_total_models > 0 else 0.0
    )
    bl_total_models = sum(opp_bl_squad_size)
    bl_total_dead = sum(opp_bl_dead_total)
    bl_survival = (
        100.0 * (bl_total_models - bl_total_dead) / bl_total_models
        if bl_total_models > 0 else 0.0
    )

    # DG total stratagem fires/battle.
    dg_strat_total = sum(sum(v) for v in dg_strat_avg.values())
    opp_strat_total = sum(sum(v) for v in opp_strat_avg.values())

    return {
        "dg": dg, "opp": opp, "wr": wr, "n": n_total,
        "dg_vp_mean": statistics.mean(dg_vp_list),
        "opp_vp_mean": statistics.mean(opp_vp_list),
        "rounds_mean": statistics.mean(rounds_played),
        "vp_dg_per_round": _per(vp_dg_by_round),
        "vp_opp_per_round": _per(vp_opp_by_round),
        "obj_vp_dg_per_round": _per(obj_vp_dg_by_round),
        "obj_vp_opp_per_round": _per(obj_vp_opp_by_round),
        "sticky_vp_dg_per_round": _per(sticky_vp_dg_by_round),
        "dmg_dg_per_round": _per(dmg_dg_by_round),
        "dmg_opp_per_round": _per(dmg_opp_by_round),
        "kills_dg_per_round": _per(kills_dg_by_round),
        "kills_opp_per_round": _per(kills_opp_by_round),
        "cp_dg_per_round": _per(cp_dg_by_round),
        "cp_opp_per_round": _per(cp_opp_by_round),
        "cp_dg_total": sum(cp_dg_by_round) / norm,
        "cp_opp_total": sum(cp_opp_by_round) / norm,
        "bs_fail_dg_per_round": _per(bs_fail_dg_by_round),
        "bs_fail_opp_per_round": _per(bs_fail_opp_by_round),
        "pm_dead_per_round": _per(pm_dead_by_round),
        "opp_bl_dead_per_round": _per(opp_bl_dead_by_round),
        "dg_veh_dead_per_round": _per(dg_veh_dead_by_round),
        "dg_strat_avg": dg_strat_avg,
        "opp_strat_avg": opp_strat_avg,
        "dg_strat_total": dg_strat_total,
        "opp_strat_total": opp_strat_total,
        "demise_mortals_per_battle": demise_mortals_total / norm,
        "demise_events_per_battle": demise_events_total / norm,
        "sticky_vp_mean": statistics.mean(sticky_vp_total) if sticky_vp_total else 0.0,
        "pm_survival_pct": pm_survival,
        "pm_total_dead": pm_total_dead,
        "pm_total_models": pm_total_models,
        "bl_survival_pct": bl_survival,
        "bl_total_dead": bl_total_dead,
        "bl_total_models": bl_total_models,
        "dg_models_mean": statistics.mean(dg_total_models_list) if dg_total_models_list else 0.0,
        "opp_models_mean": statistics.mean(opp_total_models_list) if opp_total_models_list else 0.0,
    }


def fmt_row5(vals, fmt="6.2f"):
    return " ".join(f"R{i}:{vals[i]:{fmt}}" for i in range(1, 6))


def main() -> None:
    print(f"Iter 5 — Death Guard UNSAMPLED-matchup diagnostic. N={N_BATTLES}/matchup, {POINTS} pts.")
    print("=" * 100)
    all_results: List[Dict] = []
    for opp in UNSAMPLED_OPPS:
        r = run_one_matchup("Death Guard", opp)
        all_results.append(r)
        print(
            f"\n## DG vs {opp}"
            f"   WR {r['wr']:5.1f}% | rnd {r['rounds_mean']:.2f}"
            f" | DG VP {r['dg_vp_mean']:5.1f} | OPP VP {r['opp_vp_mean']:5.1f}"
            f" | gap +{r['dg_vp_mean']-r['opp_vp_mean']:.1f}"
            f" | models: DG {r['dg_models_mean']:.0f} vs OPP {r['opp_models_mean']:.0f}"
        )
        print(
            "  [VP/rnd DG]   " + fmt_row5(r["vp_dg_per_round"]) +
            f"  | total {sum(r['vp_dg_per_round']):.1f}"
        )
        print(
            "  [VP/rnd opp]  " + fmt_row5(r["vp_opp_per_round"]) +
            f"  | total {sum(r['vp_opp_per_round']):.1f}"
        )
        print(
            "  [sticky-attrib DG (0 OC)]  " + fmt_row5(r["sticky_vp_dg_per_round"]) +
            f"  | total {sum(r['sticky_vp_dg_per_round']):.1f}"
        )
        print(
            "  [dmg DG->opp] " + fmt_row5(r["dmg_dg_per_round"]) +
            f"  | total {sum(r['dmg_dg_per_round']):.1f}"
        )
        print(
            "  [dmg opp->DG] " + fmt_row5(r["dmg_opp_per_round"]) +
            f"  | total {sum(r['dmg_opp_per_round']):.1f}"
        )
        print(
            "  [kills DG]    " + fmt_row5(r["kills_dg_per_round"], "5.2f") +
            f"  | total {sum(r['kills_dg_per_round']):.1f}"
        )
        print(
            "  [kills opp]   " + fmt_row5(r["kills_opp_per_round"], "5.2f") +
            f"  | total {sum(r['kills_opp_per_round']):.1f}"
        )
        print(
            "  [BS fail opp] " + fmt_row5(r["bs_fail_opp_per_round"], "5.2f") +
            f"  | total {sum(r['bs_fail_opp_per_round']):.2f}"
        )
        print(
            "  [BS fail DG]  " + fmt_row5(r["bs_fail_dg_per_round"], "5.2f") +
            f"  | total {sum(r['bs_fail_dg_per_round']):.2f}"
        )
        print(
            f"  CP: DG {r['cp_dg_total']:.1f} vs OPP {r['cp_opp_total']:.1f}"
            f" | DG strat fires/battle {r['dg_strat_total']:.1f}"
            f" vs OPP {r['opp_strat_total']:.1f}"
        )
        print(
            f"  PM survival {r['pm_survival_pct']:.1f}%"
            f" ({r['pm_total_dead']}/{r['pm_total_models']})"
            f"  vs OPP BL {r['bl_survival_pct']:.1f}%"
            f" ({r['bl_total_dead']}/{r['bl_total_models']})"
        )
        print("  DG stratagems (top 6 by total fires):")
        for name, rounds in sorted(
            r["dg_strat_avg"].items(),
            key=lambda kv: -sum(kv[1]),
        )[:6]:
            total = sum(rounds)
            if total < 0.05:
                continue
            print(f"    {name:30s} {fmt_row5(rounds, '5.2f')}  total={total:.2f}")

    # Cross-matchup summary table.
    print("\n## Per-matchup summary (N=30 each)")
    print(
        f"{'Opponent':22s} | {'WR%':>5s} | {'DG VP':>5s} | {'OPP VP':>6s} |"
        f" {'sticky':>6s} | {'PM srv':>6s} | {'OPP BL':>6s} | {'DG dmg':>6s} |"
        f" {'OPP dmg':>7s} | {'DG strat':>8s} | {'OPP strat':>9s}"
    )
    for r in all_results:
        print(
            f"{r['opp']:22s} | {r['wr']:5.1f} | {r['dg_vp_mean']:5.1f}"
            f" | {r['opp_vp_mean']:6.1f} | {r['sticky_vp_mean']:6.1f}"
            f" | {r['pm_survival_pct']:5.1f}% | {r['bl_survival_pct']:5.1f}%"
            f" | {sum(r['dmg_dg_per_round']):6.1f}"
            f" | {sum(r['dmg_opp_per_round']):7.1f}"
            f" | {r['dg_strat_total']:8.2f} | {r['opp_strat_total']:9.2f}"
        )
    mean_wr = statistics.mean(r["wr"] for r in all_results)
    mean_dg_vp = statistics.mean(r["dg_vp_mean"] for r in all_results)
    mean_opp_vp = statistics.mean(r["opp_vp_mean"] for r in all_results)
    mean_sticky = statistics.mean(r["sticky_vp_mean"] for r in all_results)
    print(
        f"{'7-opp MEAN':22s} | {mean_wr:5.1f} | {mean_dg_vp:5.1f}"
        f" | {mean_opp_vp:6.1f} | {mean_sticky:6.1f}"
    )


if __name__ == "__main__":
    main()
