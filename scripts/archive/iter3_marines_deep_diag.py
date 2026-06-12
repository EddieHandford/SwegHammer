"""
Iter-3 Marines deep diagnostic — post-#179 / post-iter-2.

After iter 2 (#179 random_fill cap, C2/C4 picker fixes) Marines still over-
performed by +13.1pt vs real-meta. This script probes the dimensions that
prior diagnostics didn't isolate:

  1. Oath of Moment usage rate. Real-meta uses Oath strategically (~30% of
     Marine output). The AI's "highest-points alive enemy unit" picker is
     simplistic — if it always lands Oath onto the same anchor that Marines
     are already shooting at anyway, the effective Oath impact may be far
     higher than real-meta because the simulator never "wastes" the pick.
  2. Combat Doctrines firing rate per round (R1 ranged-only, R2 both, R3+
     melee-only).
  3. Re-roll stacking — when Oath + Doctrines both apply, count the number of
     wound rolls re-rolled and compare to expected (Oath should grant the only
     wound re-roll; the +1-to-wound from Doctrines lowers the wound TN but
     does NOT add a separate re-roll). If the simulator is stacking re-rolls
     we'll see anomalously high damage per attack on the Oath target in R2.
  4. OC dominance post-#179: per-objective Marine OC vs opponent OC averages.
  5. Repulsor damage contribution: the 198-pt Repulsor is 20% of a 1000-pt
     archetype — track its share of Marine damage output.
  6. Matchup-specific dynamics: DG soak (T10+ Plagueburst, FNP), Necrons RP
     (does Oath ignore RP?), Tyranid swarms (gargoyles / termagants OC
     contest).

Read-only — no catalogue / simulator / strategy mutations. Faction name in
catalogue is the literal "Adeptus Astartes".

Usage:
    PYTHONIOENCODING=utf-8 python -m scripts.iter3_marines_deep_diag
"""
from __future__ import annotations

import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "-m", "scripts.iter3_marines_deep_diag"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army
from code.events import (
    ObjectiveScored,
    OathTargetChosen,
    RoundStarted,
    UnitFought,
    UnitKilled,
    UnitShot,
)
from code.factions import is_marine_faction
from code.maps import DEFAULT_MAP
from code.simulator import Battle

OPPONENTS = [
    "Death Guard", "Necrons", "Tyranids",
    "Aeldari", "T'au Empire", "Orks",
    "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
]
MARINES = "Adeptus Astartes"
N_BATTLES = 30
POINTS = 1000


class DeepDiag:
    """Captures every attack event from Marine attackers and classifies it
    along (round, mode, target=oath?, attacker=repulsor?). Also captures
    end-of-round OC, kill timing, and tracks how often Oath re-rolls actually
    fire (proxy: damage delta on first-pass vs final via simulator hooks
    isn't available, so we approximate by counting attacks on oath_target
    that occur in Doctrine-active rounds — these are the "compound" cases).
    """

    def __init__(self, marine_army_name: str, marine_uids: Dict[str, "Unit"]) -> None:
        self.marine_army = marine_army_name
        self.marine_uids = marine_uids
        self.current_round = 0
        self.oath_target_uid: Optional[str] = None

        # Attack rollups
        self.total_marine_attacks = 0
        self.attacks_on_oath = 0
        self.damage_total = 0.0
        self.damage_on_oath = 0.0
        # Compound buff cases: Oath active AND Doctrine active for this
        # (round, mode). These attacks get re-roll-both AND +1-to-wound.
        self.compound_attacks = 0
        self.compound_damage = 0.0

        # Round/mode buckets for Doctrine firing rate.
        self.ranged_by_round: Dict[int, int] = defaultdict(int)
        self.melee_by_round: Dict[int, int] = defaultdict(int)
        self.dmg_ranged_by_round: Dict[int, float] = defaultdict(float)
        self.dmg_melee_by_round: Dict[int, float] = defaultdict(float)

        # Repulsor-attributed damage
        self.repulsor_damage = 0.0
        self.repulsor_attacks = 0

        # OC samples (end-of-round per objective)
        self.marine_oc_samples: List[int] = []
        self.opp_oc_samples: List[int] = []
        self.objectives_scored_to_marines = 0
        self.objectives_scored_to_opp = 0
        self.objectives_contested = 0

        # Kill timing — which round opponents lose first units; proxy for
        # Marines' burst window relative to opponent recovery (DG FNP,
        # Necron RP).
        self.opp_kills_by_round: Dict[int, int] = defaultdict(int)
        self.marine_kills_by_round: Dict[int, int] = defaultdict(int)

        # Oath target hit-by-others: does the AI pick targets that Marines
        # would shoot anyway? Count attacks-on-oath as fraction of total.
        # (Already captured above.)

    def _is_repulsor(self, attacker_uid: str) -> bool:
        u = self.marine_uids.get(attacker_uid)
        if u is None:
            return False
        return "repulsor" in u.profile.name.lower()

    def _is_marine(self, attacker_uid: str) -> bool:
        u = self.marine_uids.get(attacker_uid)
        return u is not None and is_marine_faction(u.profile.faction)

    def _doctrine_active(self, mode: str) -> bool:
        # SwegHammer AI rotation: R1 Devastator (ranged only),
        # R2 Tactical (both), R3+ Assault (melee only).
        r = self.current_round
        if r == 1:
            return mode == "ranged"
        if r == 2:
            return True
        if r >= 3:
            return mode == "melee"
        return False

    def on_event(self, e: object) -> None:
        if isinstance(e, RoundStarted):
            self.current_round = e.round_num
            self.oath_target_uid = None
        elif isinstance(e, OathTargetChosen):
            if e.army_name == self.marine_army:
                self.oath_target_uid = e.target_uid
        elif isinstance(e, UnitShot):
            self._record_attack(e, "ranged")
        elif isinstance(e, UnitFought):
            self._record_attack(e, "melee")
        elif isinstance(e, UnitKilled):
            # Whose unit died? Look up by uid in marine_uids; if absent
            # it's an opponent kill caused by Marines (most likely).
            if e.unit_uid in self.marine_uids:
                self.marine_kills_by_round[self.current_round] += 1
            else:
                self.opp_kills_by_round[self.current_round] += 1
        elif isinstance(e, ObjectiveScored):
            self.marine_oc_samples.append(e.a_oc)
            self.opp_oc_samples.append(e.b_oc)
            if e.army_name is None:
                self.objectives_contested += 1
            elif e.army_name == self.marine_army:
                self.objectives_scored_to_marines += 1
            else:
                self.objectives_scored_to_opp += 1

    def _record_attack(self, e, mode: str) -> None:
        if not self._is_marine(e.attacker_uid):
            return
        self.total_marine_attacks += 1
        self.damage_total += e.damage
        if mode == "ranged":
            self.ranged_by_round[self.current_round] += 1
            self.dmg_ranged_by_round[self.current_round] += e.damage
        else:
            self.melee_by_round[self.current_round] += 1
            self.dmg_melee_by_round[self.current_round] += e.damage
        on_oath = (
            self.oath_target_uid is not None
            and e.target_uid == self.oath_target_uid
        )
        if on_oath:
            self.attacks_on_oath += 1
            self.damage_on_oath += e.damage
        if self._is_repulsor(e.attacker_uid):
            self.repulsor_damage += e.damage
            self.repulsor_attacks += 1
        # Compound: Oath + Doctrine both fire on this attack.
        if on_oath and self._doctrine_active(mode):
            self.compound_attacks += 1
            self.compound_damage += e.damage


def run_matchup(opponent: str) -> Dict:
    wins = Counter()
    oath_pct: List[float] = []
    doctrine_pct: List[float] = []
    compound_pct: List[float] = []
    repulsor_share: List[float] = []
    repulsor_dmg_means: List[float] = []
    marine_oc_means: List[float] = []
    opp_oc_means: List[float] = []
    dmg_per_attack_oath: List[float] = []
    dmg_per_attack_other: List[float] = []
    dmg_per_attack_compound: List[float] = []
    opp_kills_r1: List[int] = []
    opp_kills_r2: List[int] = []
    rounds_played: List[int] = []
    marine_attack_totals: List[int] = []
    obj_marines_total = 0
    obj_opp_total = 0
    obj_contested_total = 0

    for s in range(N_BATTLES):
        seed = s + 12000
        random.seed(seed)
        marines = build_faction_random_army(
            "A", MARINES, POINTS,
            rng=random.Random(seed),
            use_archetype=True,
        )
        opp = build_faction_random_army(
            "B", opponent, POINTS,
            rng=random.Random(seed + 50000),
            use_archetype=True,
        )
        if not marines.units or not opp.units:
            continue

        # Pre-fill uid lookup before run() (same trick as marines_diag).
        battle = Battle(marines, opp, map_=DEFAULT_MAP)
        battle._assign_uids()
        marine_uids = {u.uid: u for u in marines.units}
        diag = DeepDiag(marines.name, marine_uids)
        battle.subscribers.append(diag)
        r = battle.run()

        wins[r.winner] += 1
        rounds_played.append(r.rounds)
        marine_attack_totals.append(diag.total_marine_attacks)

        if diag.total_marine_attacks > 0:
            oath_pct.append(100.0 * diag.attacks_on_oath / diag.total_marine_attacks)
            # Doctrine firing rate
            doc_fires = 0
            for rnd, n in diag.ranged_by_round.items():
                if rnd == 1 or rnd == 2:
                    doc_fires += n
            for rnd, n in diag.melee_by_round.items():
                if rnd >= 2:
                    doc_fires += n
            doctrine_pct.append(100.0 * doc_fires / diag.total_marine_attacks)
            compound_pct.append(
                100.0 * diag.compound_attacks / diag.total_marine_attacks
            )
            if diag.attacks_on_oath > 0:
                dmg_per_attack_oath.append(
                    diag.damage_on_oath / diag.attacks_on_oath
                )
            other_attacks = diag.total_marine_attacks - diag.attacks_on_oath
            other_dmg = diag.damage_total - diag.damage_on_oath
            if other_attacks > 0:
                dmg_per_attack_other.append(other_dmg / other_attacks)
            if diag.compound_attacks > 0:
                dmg_per_attack_compound.append(
                    diag.compound_damage / diag.compound_attacks
                )

        if diag.damage_total > 0:
            repulsor_share.append(
                100.0 * diag.repulsor_damage / diag.damage_total
            )
            repulsor_dmg_means.append(diag.repulsor_damage)

        if diag.marine_oc_samples:
            marine_oc_means.append(statistics.mean(diag.marine_oc_samples))
            opp_oc_means.append(statistics.mean(diag.opp_oc_samples))

        opp_kills_r1.append(diag.opp_kills_by_round.get(1, 0))
        opp_kills_r2.append(diag.opp_kills_by_round.get(2, 0))
        obj_marines_total += diag.objectives_scored_to_marines
        obj_opp_total += diag.objectives_scored_to_opp
        obj_contested_total += diag.objectives_contested

    a_wins = wins.get("A", 0)
    b_wins = wins.get("B", 0)
    draws = wins.get(None, 0)
    total = a_wins + b_wins + draws
    wr = (a_wins / total * 100.0) if total else 0.0

    return {
        "opp": opponent,
        "wr": wr,
        "n": total,
        "rounds": statistics.mean(rounds_played) if rounds_played else 0.0,
        "marine_attacks": (
            statistics.mean(marine_attack_totals) if marine_attack_totals else 0.0
        ),
        "oath_pct": statistics.mean(oath_pct) if oath_pct else 0.0,
        "doctrine_pct": statistics.mean(doctrine_pct) if doctrine_pct else 0.0,
        "compound_pct": statistics.mean(compound_pct) if compound_pct else 0.0,
        "repulsor_share": (
            statistics.mean(repulsor_share) if repulsor_share else 0.0
        ),
        "repulsor_dmg": (
            statistics.mean(repulsor_dmg_means) if repulsor_dmg_means else 0.0
        ),
        "marine_oc": statistics.mean(marine_oc_means) if marine_oc_means else 0.0,
        "opp_oc": statistics.mean(opp_oc_means) if opp_oc_means else 0.0,
        "dpa_oath": (
            statistics.mean(dmg_per_attack_oath) if dmg_per_attack_oath else 0.0
        ),
        "dpa_other": (
            statistics.mean(dmg_per_attack_other) if dmg_per_attack_other else 0.0
        ),
        "dpa_compound": (
            statistics.mean(dmg_per_attack_compound)
            if dmg_per_attack_compound
            else 0.0
        ),
        "opp_kills_r1": (
            statistics.mean(opp_kills_r1) if opp_kills_r1 else 0.0
        ),
        "opp_kills_r2": (
            statistics.mean(opp_kills_r2) if opp_kills_r2 else 0.0
        ),
        "obj_m": obj_marines_total,
        "obj_o": obj_opp_total,
        "obj_c": obj_contested_total,
    }


def main() -> None:
    print(f"Iter-3 Marines deep diag — N={N_BATTLES} per matchup, {POINTS}pt.")
    print(
        f"{'opp':14s} {'WR%':>5s} {'rnd':>4s} {'atk':>5s} "
        f"{'oath%':>6s} {'doc%':>6s} {'cmp%':>5s} "
        f"{'repS%':>5s} {'repDmg':>7s} "
        f"{'MOC':>5s} {'OOC':>5s} {'dpaO':>5s} {'dpaX':>5s} {'dpaC':>5s} "
        f"{'k1':>4s} {'k2':>4s} {'obj_m/o/c':>11s}"
    )
    print("-" * 130)
    results = []
    for opp in OPPONENTS:
        r = run_matchup(opp)
        results.append(r)
        print(
            f"{r['opp']:14s} {r['wr']:>5.1f} {r['rounds']:>4.1f}"
            f" {r['marine_attacks']:>5.1f}"
            f" {r['oath_pct']:>6.2f} {r['doctrine_pct']:>6.2f}"
            f" {r['compound_pct']:>5.2f}"
            f" {r['repulsor_share']:>5.1f} {r['repulsor_dmg']:>7.1f}"
            f" {r['marine_oc']:>5.1f} {r['opp_oc']:>5.1f}"
            f" {r['dpa_oath']:>5.2f} {r['dpa_other']:>5.2f} {r['dpa_compound']:>5.2f}"
            f" {r['opp_kills_r1']:>4.1f} {r['opp_kills_r2']:>4.1f}"
            f" {r['obj_m']:>3d}/{r['obj_o']:>3d}/{r['obj_c']:>3d}"
        )
    print("-" * 130)
    if results:
        keys = [
            "wr", "oath_pct", "doctrine_pct", "compound_pct",
            "repulsor_share", "marine_oc", "opp_oc",
            "dpa_oath", "dpa_other", "dpa_compound",
        ]
        means = {k: statistics.mean(r[k] for r in results) for k in keys}
        print(
            f"{'MEAN':14s} {means['wr']:>5.1f}      "
            f"      {means['oath_pct']:>6.2f} {means['doctrine_pct']:>6.2f}"
            f" {means['compound_pct']:>5.2f}"
            f" {means['repulsor_share']:>5.1f}        "
            f" {means['marine_oc']:>5.1f} {means['opp_oc']:>5.1f}"
            f" {means['dpa_oath']:>5.2f} {means['dpa_other']:>5.2f}"
            f" {means['dpa_compound']:>5.2f}"
        )
    print()
    print("Legend:")
    print("  oath%   = % of Marine attacks landed on round's Oath target")
    print("  doc%    = % of Marine attacks in a (round,mode) where Doctrine grants +1-wound")
    print("  cmp%    = % of Marine attacks with BOTH Oath re-roll AND Doctrine +1-wound")
    print("  repS%   = Repulsor's share of total Marine damage")
    print("  dpaO    = avg damage per attack against Oath target")
    print("  dpaX    = avg damage per attack against non-Oath targets")
    print("  dpaC    = avg damage per attack with Oath+Doctrine compound")
    print("  k1/k2   = opp units killed by Marines in R1 / R2")
    print("  obj     = objectives scored Marines / opponent / contested (total across battles)")


if __name__ == "__main__":
    main()
