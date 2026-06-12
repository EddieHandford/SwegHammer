"""Auto-loop iter 4 — Death Guard post-sticky-tighten diagnostic (+15.3pt residual).

Iter-3 fix tightened `_sticky_owner` claim from `>=` to `>` (Wahapedia
"greater than" wording). The DG slice moved from +17.0 to +15.3 — only
-1.7pt of the predicted -4 to -7. Something ELSE is driving the residual.

Hypotheses to discriminate (set out in the iter-4 brief):
  H1. Sticky-claim path is partially closed but the sticky-OWNER scoring
      fallback (`a_oc==0 AND b_oc==0`) is still cheap because DG's army-wide
      Disgustingly Resilient + T6 keeps DG bodies on top of objectives so
      the opp simply can't break the lock for a round. -> per-round VP
      breakdown should show DG VP arriving as `obj VP` mostly in R2-R5.
  H2. Disgustingly Resilient FNP 5+ is applied army-wide (units.py:574)
      to every DG unit including VEHICLE/MONSTER (Plagueburst Crawler,
      Foetid Bloat-Drone). On Wahapedia the DR army rule wording is
      "Each time a model in this unit would lose a wound, this ability
      has Feel No Pain 5+ against that lost wound." — applies to every
      DG model, so the FNP 5+ scope is correct. But the Plague Marine
      override (fnp=5 in overrides.json) compounds when other DG units
      ALSO get the same FNP via min() — net no effect, but for non-PM DG
      units (T6 PCBs, Drones, Pox Walkers) it doubles their effective HP
      and prevents the opp from breaking sticky.
  H3. Contagions of Nurgle Round 1 -1T (effectively +1-to-wound) hits
      every enemy unit within 3" of any DG model. Plague Marines have
      M5 so they can plant on objectives in R1 and instantly debuff
      anyone trying to contest them. Measure fire-rate per round.
  H4. Stratagem stack: OverGen + Creeping Blight (both reroll-hit
      shooting) compose every round. The real DG codex lists OverGen
      as Battle Tactic - 1 CP - one DG CHARACTER unit, and Creeping
      Blight as Battle Tactic - 1 CP - one DG INFANTRY unit; the
      "1 Stratagem per phase per unit" 10e core rule may not be
      enforced — measure if BOTH fire on the SAME unit in the SAME
      phase.

Output: dense markdown to stdout. Read-only — no catalogue / strategy /
simulator mutation. Hard cap N=30 per matchup, 3 opponents.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter4_dg_post_sticky_diag

Never runs the eval suite. Never edits anything.
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter4_dg_post_sticky_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
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


TARGETS: Dict[str, List[str]] = {
    "Death Guard": ["Adeptus Astartes", "Necrons", "Tyranids"],
}
N_BATTLES = 30
POINTS = 1000


VV_STRATS = {
    "Disgustingly Resilient",
    "Putrid Detonation",
    "Plaguesurge",
    "Leechspore Eruption",
    "Overwhelming Generosity",
    "Creeping Blight",
}


class DGTrace4:
    """Iter-4 sub. Captures per-round VP, CP spend, kill-trade per round,
    survival of DG BATTLELINE (PM) vs opp BATTLELINE, contagion-eligible
    enemy unit counts, and stratagem fires per round.
    """

    def __init__(self, dg_army: str, opp_army: str) -> None:
        self.dg_army = dg_army
        self.opp_army = opp_army
        self.current_round = 0
        # VP per round (delta), not cumulative. Captured at RoundEnded.
        self.dg_vp_round: List[int] = [0] * 6
        self.opp_vp_round: List[int] = [0] * 6
        self.dg_obj_vp_round: List[int] = [0] * 6
        self.opp_obj_vp_round: List[int] = [0] * 6
        self.dg_sticky_vp_round: List[int] = [0] * 6   # DG scored with 0 OC
        self._last_dg_vp = 0
        self._last_opp_vp = 0
        # Damage in/out by round.
        self.dmg_dg_to_opp: List[float] = [0.0] * 6
        self.dmg_opp_to_dg: List[float] = [0.0] * 6
        # Kills (model count) per round, per side.
        self.kills_dg: List[int] = [0] * 6
        self.kills_opp: List[int] = [0] * 6
        # CP spend per round, by army (event includes cp_cost).
        self.cp_dg_round: List[int] = [0] * 6
        self.cp_opp_round: List[int] = [0] * 6
        # Stratagem fires per round, by name.
        self.dg_strat_rounds: Dict[str, List[int]] = {}
        self.opp_strat_rounds: Dict[str, List[int]] = {}
        # Per-round stratagem counts (any name) per side.
        self.dg_strat_count: List[int] = [0] * 6
        self.opp_strat_count: List[int] = [0] * 6
        # uid bookkeeping.
        self.uid_army: Dict[str, str] = {}
        self.uid_profile_key: Dict[str, str] = {}
        self.uid_keywords: Dict[str, frozenset] = {}
        self.uid_max_health: Dict[str, float] = {}
        self.uid_min_models: Dict[str, int] = {}
        self.uid_faction: Dict[str, str] = {}
        # PM survival.
        self.plague_marine_uids: set = set()
        self.opp_battleline_uids: set = set()
        self.dg_vehicle_uids: set = set()
        self.dg_battleline_uids: set = set()
        # Per-round dead counts in these tracked uid groups.
        self.pm_dead_round: List[int] = [0] * 6
        self.opp_bl_dead_round: List[int] = [0] * 6
        self.dg_veh_dead_round: List[int] = [0] * 6
        # Total demise mortals from DG VEHICLEs.
        self.demise_mortals: int = 0
        self.demise_events: int = 0
        # Track last attacker army for kill attribution.
        self._last_attacker_army: Optional[str] = None
        # Track sticky-attributed VP overall.
        self.dg_sticky_vp_total: int = 0

    def set_armies(
        self,
        dg_units: list,
        opp_units: list,
        dg_name: str,
        opp_name: str,
    ) -> None:
        for u in dg_units:
            self.uid_army[u.uid] = dg_name
            self.uid_profile_key[u.uid] = u.profile.name
            kw = frozenset(u.profile.unit_keywords or ())
            self.uid_keywords[u.uid] = kw
            self.uid_max_health[u.uid] = u.profile.health
            self.uid_min_models[u.uid] = max(1, u.profile.min_models)
            self.uid_faction[u.uid] = u.profile.faction or ""
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
            self.uid_max_health[u.uid] = u.profile.health
            self.uid_min_models[u.uid] = max(1, u.profile.min_models)
            self.uid_faction[u.uid] = u.profile.faction or ""
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
    # Cross-battle aggregations.
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
    dg_strat_fires_by_round: Dict[str, List[float]] = defaultdict(lambda: [0.0] * 6)
    opp_strat_fires_by_round: Dict[str, List[float]] = defaultdict(lambda: [0.0] * 6)
    demise_mortals_total = 0
    demise_events_total = 0
    sticky_vp_total: List[int] = []
    pm_squad_size: List[int] = []
    pm_dead_total: List[int] = []
    opp_bl_squad_size: List[int] = []
    opp_bl_dead_total: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 12345
        random.seed(seed)
        a = build_faction_random_army(
            "A", dg, POINTS, rng=random.Random(seed), use_archetype=True,
        )
        b = build_faction_random_army(
            "B", opp, POINTS, rng=random.Random(seed + 50000), use_archetype=True,
        )
        if not a.units or not b.units:
            continue

        sub = DGTrace4(a.name, b.name)
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
        "pm_dead_per_round": _per(pm_dead_by_round),
        "opp_bl_dead_per_round": _per(opp_bl_dead_by_round),
        "dg_veh_dead_per_round": _per(dg_veh_dead_by_round),
        "dg_strat_avg": dg_strat_avg,
        "opp_strat_avg": opp_strat_avg,
        "demise_mortals_per_battle": demise_mortals_total / norm,
        "demise_events_per_battle": demise_events_total / norm,
        "sticky_vp_mean": statistics.mean(sticky_vp_total) if sticky_vp_total else 0.0,
        "pm_survival_pct": pm_survival,
        "pm_total_dead": pm_total_dead,
        "pm_total_models": pm_total_models,
        "bl_survival_pct": bl_survival,
        "bl_total_dead": bl_total_dead,
        "bl_total_models": bl_total_models,
    }


def fmt_row5(vals, fmt="6.2f"):
    return " ".join(f"R{i}:{vals[i]:{fmt}}" for i in range(1, 6))


def main() -> None:
    print(f"Iter 4 — Death Guard post-sticky-tighten diagnostic. N={N_BATTLES}/matchup, {POINTS} pts.")
    print("=" * 100)
    all_results = []
    for dg, opps in TARGETS.items():
        print(f"\n## {dg}")
        agg_wr: List[float] = []
        agg_dg_vp: List[float] = []
        agg_opp_vp: List[float] = []
        for opp in opps:
            r = run_one_matchup(dg, opp)
            all_results.append(r)
            agg_wr.append(r["wr"])
            agg_dg_vp.append(r["dg_vp_mean"])
            agg_opp_vp.append(r["opp_vp_mean"])
            print(
                f"\n  vs {opp:22s} | WR {r['wr']:5.1f}% | rnd {r['rounds_mean']:.2f}"
                f" | DG VP {r['dg_vp_mean']:5.1f} | OPP VP {r['opp_vp_mean']:5.1f}"
                f" | gap +{r['dg_vp_mean']-r['opp_vp_mean']:.1f}"
            )
            print(
                "    [VP/rnd DG]   " + fmt_row5(r["vp_dg_per_round"]) +
                f"  | total {sum(r['vp_dg_per_round']):.1f}"
            )
            print(
                "    [VP/rnd opp]  " + fmt_row5(r["vp_opp_per_round"]) +
                f"  | total {sum(r['vp_opp_per_round']):.1f}"
            )
            print(
                "    [obj VP DG]   " + fmt_row5(r["obj_vp_dg_per_round"]) +
                f"  | total {sum(r['obj_vp_dg_per_round']):.1f}"
            )
            print(
                "    [obj VP opp]  " + fmt_row5(r["obj_vp_opp_per_round"]) +
                f"  | total {sum(r['obj_vp_opp_per_round']):.1f}"
            )
            print(
                "    [sticky-attrib DG (0 OC win)]  " + fmt_row5(r["sticky_vp_dg_per_round"]) +
                f"  | total {sum(r['sticky_vp_dg_per_round']):.1f}"
            )
            print(
                "    [dmg DG->opp] " + fmt_row5(r["dmg_dg_per_round"]) +
                f"  | total {sum(r['dmg_dg_per_round']):.1f}"
            )
            print(
                "    [dmg opp->DG] " + fmt_row5(r["dmg_opp_per_round"]) +
                f"  | total {sum(r['dmg_opp_per_round']):.1f}"
            )
            print(
                "    [kills DG]    " + fmt_row5(r["kills_dg_per_round"]) +
                f"  | total {sum(r['kills_dg_per_round']):.1f}"
            )
            print(
                "    [kills opp]   " + fmt_row5(r["kills_opp_per_round"]) +
                f"  | total {sum(r['kills_opp_per_round']):.1f}"
            )
            print(
                "    [CP spent DG] " + fmt_row5(r["cp_dg_per_round"]) +
                f"  | total {r['cp_dg_total']:.1f}"
            )
            print(
                "    [CP spent opp]" + fmt_row5(r["cp_opp_per_round"]) +
                f"  | total {r['cp_opp_total']:.1f}"
            )
            print(
                f"    PM survival: {r['pm_survival_pct']:.1f}%"
                f" ({r['pm_total_dead']}/{r['pm_total_models']} dead)"
                f"  vs opp BL: {r['bl_survival_pct']:.1f}%"
                f" ({r['bl_total_dead']}/{r['bl_total_models']} dead)"
            )
            print(
                "    [PM dead/rnd]    " + fmt_row5(r["pm_dead_per_round"], "5.2f")
            )
            print(
                "    [opp BL dead/rnd]" + fmt_row5(r["opp_bl_dead_per_round"], "5.2f")
            )
            print(
                "    [DG VEH dead/rnd]" + fmt_row5(r["dg_veh_dead_per_round"], "5.2f")
            )
            print(
                f"    Putrid demise events: {r['demise_events_per_battle']:.2f}"
                f"  mortals/battle: {r['demise_mortals_per_battle']:.2f}"
            )
            print("    DG stratagems (fires/battle by round R1..R5):")
            for name, rounds in sorted(
                r["dg_strat_avg"].items(),
                key=lambda kv: -sum(kv[1]),
            )[:10]:
                total = sum(rounds)
                if total < 0.05:
                    continue
                print(f"      {name:30s} {fmt_row5(rounds, '5.2f')}  total={total:.2f}")
            print("    OPP stratagems (top 5):")
            for name, rounds in sorted(
                r["opp_strat_avg"].items(),
                key=lambda kv: -sum(kv[1]),
            )[:5]:
                total = sum(rounds)
                if total < 0.05:
                    continue
                print(f"      {name:30s} {fmt_row5(rounds, '5.2f')}  total={total:.2f}")
        avg_wr = statistics.mean(agg_wr) if agg_wr else 0.0
        avg_dg_vp = statistics.mean(agg_dg_vp) if agg_dg_vp else 0.0
        avg_opp_vp = statistics.mean(agg_opp_vp) if agg_opp_vp else 0.0
        print(
            f"\n  >> 3-opp avg WR {avg_wr:.1f}% | DG VP {avg_dg_vp:.1f}"
            f" vs OPP VP {avg_opp_vp:.1f} (gap +{avg_dg_vp - avg_opp_vp:.1f})"
        )

    print("\n## Cross-matchup means (DG slice)")
    for key, label in [
        ("vp_dg_per_round", "DG VP/rnd"),
        ("vp_opp_per_round", "OPP VP/rnd"),
        ("obj_vp_dg_per_round", "DG obj VP/rnd"),
        ("sticky_vp_dg_per_round", "DG sticky-attrib VP/rnd"),
        ("dmg_dg_per_round", "DG dmg/rnd"),
        ("dmg_opp_per_round", "OPP dmg/rnd"),
        ("cp_dg_per_round", "DG CP/rnd"),
        ("cp_opp_per_round", "OPP CP/rnd"),
        ("pm_dead_per_round", "PM dead/rnd"),
        ("opp_bl_dead_per_round", "OPP BL dead/rnd"),
    ]:
        means = [
            statistics.mean(rs[key][i] for rs in all_results)
            for i in range(6)
        ]
        print(f"  {label:30s} " + fmt_row5(means))


if __name__ == "__main__":
    main()
