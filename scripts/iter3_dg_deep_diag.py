"""Auto-loop iter 3 — Death Guard deep diagnostic (+17.0pt residual).

Vanilla 1000 pt archetype battles, N=30 per matchup, DG vs each top-MAE-impact
opponent (Adeptus Astartes, Necrons, Tyranids). Per battle, capture:

  1. Damage in/out per round (DG -> opp, opp -> DG).
  2. Virulent Vectorium stratagem fire counts (which fire, on whom, what round).
  3. Objective VP vs kill-driven VP — does Worldblight sticky tilt scoring?
  4. Putrid Detonation arming + Deadly Demise spillover damage from DG VEHICLEs.
  5. Leechspore Eruption heal counts + mortal-wound payloads.
  6. Plague Marine squad survival (vs other faction BATTLELINE survival).

Read-only — no catalogue / strategy / simulator mutation. Output is markdown
to stdout. Parsed by the human into the analysis doc.

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter3_dg_deep_diag

Hard-cap: N=30, three opponents. Never runs the eval suite.
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
        [sys.executable, "-m", "scripts.iter3_dg_deep_diag"] + sys.argv[1:],
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


# Virulent Vectorium stratagem names (per code/stratagems.py).
VV_STRATS = {
    "Disgustingly Resilient",
    "Putrid Detonation",
    "Plaguesurge",
    "Leechspore Eruption",
    "Overwhelming Generosity",
    "Creeping Blight",
}


class DGTraceSub:
    """Collect per-battle aggregates for one DG-vs-opp match."""

    def __init__(self, dg_army: str, opp_army: str) -> None:
        self.dg_army = dg_army
        self.opp_army = opp_army
        self.current_round = 0
        # Damage emitted by DG to opp and vice-versa, per round 0..5.
        self.dmg_dg_to_opp: List[float] = [0.0] * 6
        self.dmg_opp_to_dg: List[float] = [0.0] * 6
        # Kills per round.
        self.kills_dg: List[int] = [0] * 6
        self.kills_opp: List[int] = [0] * 6
        # uid -> army name + uid -> profile key.
        self.uid_army: Dict[str, str] = {}
        self.uid_profile_key: Dict[str, str] = {}
        self.uid_keywords: Dict[str, frozenset] = {}
        self.uid_max_health: Dict[str, float] = {}
        self.uid_min_models: Dict[str, int] = {}
        # Stratagem fires (DG-side only matters here).
        self.dg_strats: Counter = Counter()
        self.opp_strats: Counter = Counter()
        # VP after each RoundEnded.
        self.last_a_vp = 0
        self.last_b_vp = 0
        # Objective VP awards (DG side / opp side), per round.
        self.dg_obj_vp: List[int] = [0] * 6
        self.opp_obj_vp: List[int] = [0] * 6
        # Putrid detonation events (mortal wounds dealt by DG VEHICLE/MONSTER
        # deaths via Deadly Demise — we count the events, since spillover damage
        # is the `mortals` field on the event).
        self.demise_events: List[Tuple[int, str, int, int]] = []  # (round, victim_uid, mortals, n_victims)
        # Plague Marines tracking: list of (uid, starting_hp, ending_hp) after battle.
        # Stats per Plague Marine squad survival.
        self._last_attacker_army: Optional[str] = None
        # Track Plague Marines casualty count = models lost
        # (each model is a Unit instance; UnitKilled fires once per dead model)
        self.plague_marine_uids: set = set()
        self.plague_marines_killed: int = 0
        # Comparable: track opp BATTLELINE deaths.
        self.opp_battleline_uids: set = set()
        self.opp_battleline_killed: int = 0
        # Track DG VEHICLE deaths (so we can divide demise events by deaths).
        self.dg_vehicle_uids: set = set()
        self.dg_vehicles_killed: int = 0
        # Track DG sticky-objective inferred VP — heuristic:
        # if dg_oc == 0 and dg gets a VP for that obj, attribute to sticky.
        self.dg_sticky_vp: int = 0
        # Leechspore is event-only via StratagemFired (we count fires; the
        # actual heal/mortal payload happens inside _try_leechspore_eruption
        # which doesn't emit a custom event).
        self.leechspore_fires: int = 0
        # Putrid Detonation fires (the arming event — not all arms result in
        # an explosion if the VEHICLE doesn't die that round).
        self.putrid_armed: int = 0
        # Overwhelming Generosity + Creeping Blight fires (the two reroll-hit
        # buffs that compose on shooting).
        self.over_gen_fires: int = 0
        self.creeping_blight_fires: int = 0
        self.disgustingly_resilient_fires: int = 0
        self.plaguesurge_fires: int = 0

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
            if "Plague Marine" in u.profile.name:
                self.plague_marine_uids.add(u.uid)
            if "VEHICLE" in kw:
                self.dg_vehicle_uids.add(u.uid)
        for u in opp_units:
            self.uid_army[u.uid] = opp_name
            self.uid_profile_key[u.uid] = u.profile.name
            kw = frozenset(u.profile.unit_keywords or ())
            self.uid_keywords[u.uid] = kw
            self.uid_max_health[u.uid] = u.profile.health
            self.uid_min_models[u.uid] = max(1, u.profile.min_models)
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
                self.plague_marines_killed += 1
            if e.unit_uid in self.opp_battleline_uids:
                self.opp_battleline_killed += 1
            if e.unit_uid in self.dg_vehicle_uids:
                self.dg_vehicles_killed += 1
        elif isinstance(e, StratagemFired):
            rnd = max(0, min(5, self.current_round))
            if e.army_name == self.dg_army:
                self.dg_strats[(rnd, e.stratagem_name)] += 1
                if e.stratagem_name == "Disgustingly Resilient":
                    self.disgustingly_resilient_fires += 1
                elif e.stratagem_name == "Putrid Detonation":
                    self.putrid_armed += 1
                elif e.stratagem_name == "Plaguesurge":
                    self.plaguesurge_fires += 1
                elif e.stratagem_name == "Leechspore Eruption":
                    self.leechspore_fires += 1
                elif e.stratagem_name == "Overwhelming Generosity":
                    self.over_gen_fires += 1
                elif e.stratagem_name == "Creeping Blight":
                    self.creeping_blight_fires += 1
            elif e.army_name == self.opp_army:
                self.opp_strats[(rnd, e.stratagem_name)] += 1
        elif isinstance(e, ObjectiveScored):
            rnd = max(0, min(5, self.current_round))
            if e.army_name == self.dg_army:
                self.dg_obj_vp[rnd] += e.vp_awarded
                # If DG has 0 OC but still scored, attribute to sticky/worldblight.
                if e.a_oc == 0 and e.vp_awarded > 0:
                    self.dg_sticky_vp += e.vp_awarded
            elif e.army_name == self.opp_army:
                self.opp_obj_vp[rnd] += e.vp_awarded
                # (Same for opp — won't usually fire vs DG.)
        elif isinstance(e, DeadlyDemiseExploded):
            rnd = max(0, min(5, self.current_round))
            self.demise_events.append((rnd, e.unit_uid, e.mortals, len(e.victims)))
        elif isinstance(e, RoundEnded):
            self.last_a_vp = e.a_vp_total
            self.last_b_vp = e.b_vp_total

    def _record_attack(
        self, attacker_uid: str, target_uid: str, damage: float
    ) -> None:
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
    dg_dmg_total: List[float] = []
    opp_dmg_total: List[float] = []
    rounds_played: List[int] = []
    dmg_dg_by_round = [0.0] * 6
    dmg_opp_by_round = [0.0] * 6
    kills_dg_by_round = [0] * 6
    kills_opp_by_round = [0] * 6
    obj_vp_dg_by_round = [0] * 6
    obj_vp_opp_by_round = [0] * 6

    strat_dg_total: Counter = Counter()
    strat_opp_total: Counter = Counter()

    putrid_fires_total = 0
    putrid_explosions: List[int] = []           # mortals per battle from DG demises
    putrid_victims: List[int] = []              # n_victims per battle from DG demises
    dg_vehicle_deaths_total = 0
    leechspore_fires_total = 0
    over_gen_fires_total = 0
    creeping_blight_fires_total = 0
    dr_fires_total = 0
    plaguesurge_fires_total = 0

    sticky_vp_total: List[int] = []
    plague_marine_deaths: List[int] = []
    plague_marine_squad_size: List[int] = []
    opp_battleline_deaths: List[int] = []
    opp_battleline_squad_size: List[int] = []

    for s in range(N_BATTLES):
        seed = s + 12345
        random.seed(seed)
        a = build_faction_random_army(
            "A", dg, POINTS, rng=random.Random(seed), use_archetype=True,
        )
        b = build_faction_random_army(
            "B", opp, POINTS, rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not a.units or not b.units:
            continue

        sub = DGTraceSub(a.name, b.name)
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
        dg_vp_list.append(sub.last_a_vp)
        opp_vp_list.append(sub.last_b_vp)
        dg_dmg_total.append(sum(sub.dmg_dg_to_opp))
        opp_dmg_total.append(sum(sub.dmg_opp_to_dg))
        for i in range(6):
            dmg_dg_by_round[i] += sub.dmg_dg_to_opp[i]
            dmg_opp_by_round[i] += sub.dmg_opp_to_dg[i]
            kills_dg_by_round[i] += sub.kills_dg[i]
            kills_opp_by_round[i] += sub.kills_opp[i]
            obj_vp_dg_by_round[i] += sub.dg_obj_vp[i]
            obj_vp_opp_by_round[i] += sub.opp_obj_vp[i]
        for (_rnd, name), n in sub.dg_strats.items():
            strat_dg_total[name] += n
        for (_rnd, name), n in sub.opp_strats.items():
            strat_opp_total[name] += n

        putrid_fires_total += sub.putrid_armed
        leechspore_fires_total += sub.leechspore_fires
        over_gen_fires_total += sub.over_gen_fires
        creeping_blight_fires_total += sub.creeping_blight_fires
        dr_fires_total += sub.disgustingly_resilient_fires
        plaguesurge_fires_total += sub.plaguesurge_fires
        dg_vehicle_deaths_total += sub.dg_vehicles_killed

        # Demise events: each tuple is (round, victim_uid, mortals, n_victims).
        battle_demise_mortals = sum(d[2] for d in sub.demise_events)
        battle_demise_victims = sum(d[3] for d in sub.demise_events)
        putrid_explosions.append(battle_demise_mortals)
        putrid_victims.append(battle_demise_victims)

        sticky_vp_total.append(sub.dg_sticky_vp)
        plague_marine_deaths.append(sub.plague_marines_killed)
        plague_marine_squad_size.append(
            sum(sub.uid_min_models[uid] for uid in sub.plague_marine_uids)
            if sub.plague_marine_uids else 0
        )
        opp_battleline_deaths.append(sub.opp_battleline_killed)
        opp_battleline_squad_size.append(
            sum(sub.uid_min_models[uid] for uid in sub.opp_battleline_uids)
            if sub.opp_battleline_uids else 0
        )

    n_total = wins + losses + draws
    wr = 100.0 * wins / n_total if n_total else 0.0
    norm = float(n_total) if n_total else 1.0

    pm_total_models = sum(plague_marine_squad_size)
    pm_total_dead = sum(plague_marine_deaths)
    pm_survival = (
        100.0 * (pm_total_models - pm_total_dead) / pm_total_models
        if pm_total_models > 0 else 0.0
    )
    bl_total_models = sum(opp_battleline_squad_size)
    bl_total_dead = sum(opp_battleline_deaths)
    bl_survival = (
        100.0 * (bl_total_models - bl_total_dead) / bl_total_models
        if bl_total_models > 0 else 0.0
    )

    return {
        "dg": dg, "opp": opp, "wr": wr, "n": n_total,
        "dg_vp_mean": statistics.mean(dg_vp_list),
        "opp_vp_mean": statistics.mean(opp_vp_list),
        "dg_dmg_mean": statistics.mean(dg_dmg_total),
        "opp_dmg_mean": statistics.mean(opp_dmg_total),
        "rounds_mean": statistics.mean(rounds_played),
        "dmg_dg_per_round": [x / norm for x in dmg_dg_by_round],
        "dmg_opp_per_round": [x / norm for x in dmg_opp_by_round],
        "obj_vp_dg_per_round": [x / norm for x in obj_vp_dg_by_round],
        "obj_vp_opp_per_round": [x / norm for x in obj_vp_opp_by_round],
        "obj_vp_dg_total": sum(obj_vp_dg_by_round) / norm,
        "obj_vp_opp_total": sum(obj_vp_opp_by_round) / norm,
        "sticky_vp_mean": statistics.mean(sticky_vp_total),
        "strat_dg_top": strat_dg_total.most_common(8),
        "strat_opp_top": strat_opp_total.most_common(5),
        "putrid_fires_per_battle": putrid_fires_total / norm,
        "putrid_explosions_mean": statistics.mean(putrid_explosions),
        "putrid_victims_mean": statistics.mean(putrid_victims),
        "dg_vehicle_deaths_per_battle": dg_vehicle_deaths_total / norm,
        "leechspore_fires_per_battle": leechspore_fires_total / norm,
        "over_gen_fires_per_battle": over_gen_fires_total / norm,
        "creeping_blight_fires_per_battle": creeping_blight_fires_total / norm,
        "dr_fires_per_battle": dr_fires_total / norm,
        "plaguesurge_fires_per_battle": plaguesurge_fires_total / norm,
        "pm_survival_pct": pm_survival,
        "pm_total_models": pm_total_models,
        "pm_total_dead": pm_total_dead,
        "bl_survival_pct": bl_survival,
        "bl_total_models": bl_total_models,
        "bl_total_dead": bl_total_dead,
    }


def main() -> None:
    print(f"Iter 3 — Death Guard deep diagnostic. N={N_BATTLES}/matchup, {POINTS} pts.")
    print("=" * 96)
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
                f" | dmg DG→opp {r['dg_dmg_mean']:6.1f} / opp→DG {r['opp_dmg_mean']:6.1f}"
            )
            print(
                f"    dmg/rnd DG→opp: " +
                " ".join(f"R{i}:{r['dmg_dg_per_round'][i]:.1f}" for i in range(1, 6))
            )
            print(
                f"    dmg/rnd opp→DG: " +
                " ".join(f"R{i}:{r['dmg_opp_per_round'][i]:.1f}" for i in range(1, 6))
            )
            print(
                f"    obj VP/rnd DG:  " +
                " ".join(f"R{i}:{r['obj_vp_dg_per_round'][i]:.1f}" for i in range(1, 6))
                + f" | total {r['obj_vp_dg_total']:.1f}"
            )
            print(
                f"    obj VP/rnd opp: " +
                " ".join(f"R{i}:{r['obj_vp_opp_per_round'][i]:.1f}" for i in range(1, 6))
                + f" | total {r['obj_vp_opp_total']:.1f}"
            )
            print(
                f"    sticky-attrib VP/battle: {r['sticky_vp_mean']:.2f}"
                f"  (DG scored objective with 0 OC)"
            )
            print(
                f"    VV strat fires/battle: DR={r['dr_fires_per_battle']:.2f}"
                f"  Putrid={r['putrid_fires_per_battle']:.2f}"
                f"  Plaguesurge={r['plaguesurge_fires_per_battle']:.2f}"
                f"  Leechspore={r['leechspore_fires_per_battle']:.2f}"
                f"  OverGen={r['over_gen_fires_per_battle']:.2f}"
                f"  CreepingBlight={r['creeping_blight_fires_per_battle']:.2f}"
            )
            print(
                f"    DG VEHICLE deaths/battle: {r['dg_vehicle_deaths_per_battle']:.2f}"
                f"  | Putrid Detonation explosion mortals/battle: {r['putrid_explosions_mean']:.2f}"
                f"  (victims hit/battle: {r['putrid_victims_mean']:.2f})"
            )
            print(
                f"    Plague Marine survival: {r['pm_survival_pct']:.1f}%"
                f"  ({r['pm_total_dead']}/{r['pm_total_models']} dead)"
                f"  vs opp BATTLELINE survival: {r['bl_survival_pct']:.1f}%"
                f"  ({r['bl_total_dead']}/{r['bl_total_models']} dead)"
            )
            print(f"    DG top strats: {r['strat_dg_top']}")
        avg_wr = statistics.mean(agg_wr) if agg_wr else 0.0
        avg_dg_vp = statistics.mean(agg_dg_vp) if agg_dg_vp else 0.0
        avg_opp_vp = statistics.mean(agg_opp_vp) if agg_opp_vp else 0.0
        vp_gap = avg_dg_vp - avg_opp_vp
        print(
            f"\n  >> 3-opp avg WR {avg_wr:.1f}% | VP {avg_dg_vp:.1f} vs {avg_opp_vp:.1f}"
            f" (gap +{vp_gap:.1f})"
        )

    # Cross-matchup aggregates.
    print("\n## Aggregated across 3 matchups (DG only)")
    total_obj_vp_dg = sum(r["obj_vp_dg_total"] for r in all_results) / max(1, len(all_results))
    total_obj_vp_opp = sum(r["obj_vp_opp_total"] for r in all_results) / max(1, len(all_results))
    total_sticky = sum(r["sticky_vp_mean"] for r in all_results) / max(1, len(all_results))
    pm_surv = statistics.mean(r["pm_survival_pct"] for r in all_results)
    bl_surv = statistics.mean(r["bl_survival_pct"] for r in all_results)
    print(f"  Mean obj VP (DG): {total_obj_vp_dg:.2f}  vs opp obj VP: {total_obj_vp_opp:.2f}")
    print(f"  Mean sticky-attribution VP (DG, 0 OC): {total_sticky:.2f}")
    print(f"  Mean Plague Marine survival: {pm_surv:.1f}%  vs opp BATTLELINE: {bl_surv:.1f}%")
    print(
        f"  Putrid fires (armed)/battle: "
        + ", ".join(f"{r['opp']}:{r['putrid_fires_per_battle']:.2f}" for r in all_results)
    )
    print(
        f"  Putrid explosion mortals/battle (DG VEHICLEs that died + armed): "
        + ", ".join(f"{r['opp']}:{r['putrid_explosions_mean']:.2f}" for r in all_results)
    )
    print(
        f"  Leechspore fires/battle: "
        + ", ".join(f"{r['opp']}:{r['leechspore_fires_per_battle']:.2f}" for r in all_results)
    )


if __name__ == "__main__":
    main()
