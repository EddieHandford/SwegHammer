"""Deep decomposition of the Astra Militarum / Adeptus Mechanicus under-valuation.

Three candidate mechanisms:
  (1) DURABILITY — units die before they can shoot (over-killed; missing
      damage-reduction / Feel No Pain / durability rule).
  (2) OUTPUT    — units survive but deal too little damage while alive
      (missing offensive buff — e.g. Astra Militarum Orders, or Adeptus
      Mechanicus Doctrina Imperatives).
  (3) POSITIONING / VICTORY POINTS — units are alive and shooting
      adequately but get out-scored on objectives (the representation
      floor — durable low-model armies under-hold objectives).

Method
------
For each under-shooter faction (Astra Militarum, Adeptus Mechanicus) vs
a spread of opponents, run battles using the Subscriber event stream to
snapshot per-army health at round start and round end.  From those
snapshots compute:

  * per-round damage DEALT and TAKEN by the under-shooter
  * per-round units ALIVE (survival curve)
  * end-of-game primary and secondary VP for each side
  * per-alive-unit-round output: total damage dealt / total unit-rounds
    alive (isolates mechanism 2 from 1)

The diagnostic is READ-ONLY: it does not modify the simulator.

Run with PYTHONHASHSEED=0:
    PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_undervaluation_deep
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Dict, List, Optional

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, RoundStarted, RoundEnded, Subscriber,
)
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UNDER = ["Astra Militarum", "Adeptus Mechanicus"]
OPPONENTS = [
    "Imperial Knights", "World Eaters", "Necrons", "T'au Empire",
    "Tyranids", "Adeptus Astartes", "Aeldari",
]
SEEDS = [1, 2, 3, 4, 5]
MAX_ROUNDS = 5


# ---------------------------------------------------------------------------
# Per-round subscriber
# ---------------------------------------------------------------------------

class RoundProbe(Subscriber):
    """Captures per-round damage dealt / taken and unit survival for the
    designated 'focal' army.

    The subscriber attaches to a Battle before run() is called.  It hooks
    RoundStarted to snapshot the health of every unit (in both armies)
    and RoundEnded to compute the delta.

    Attributes
    ----------
    focal_army_name : str
        The army whose numbers we track as "under-shooter".
    round_data : list[dict]
        One entry per battle round with keys:
          round, dealt, taken, me_alive, opp_alive, me_start, opp_start
    final_a_vp, final_b_vp : int
        Cumulative VP totals from the last RoundEnded event.
    focal_is_a : bool | None
        True if the focal army is army A in this battle.
    """

    def __init__(self, focal_army_name: str, army_a, army_b) -> None:
        self.focal_army_name = focal_army_name
        self._army_a = army_a
        self._army_b = army_b
        self.focal_is_a: Optional[bool] = None

        self.round_data: List[dict] = []

        # Health snapshots keyed by Python object id (stable for battle lifetime)
        self._snap_a: Dict[int, float] = {}
        self._snap_b: Dict[int, float] = {}

        self.final_a_vp: int = 0
        self.final_b_vp: int = 0

        self._battle: Optional[Battle] = None

    def attach(self, battle: Battle) -> None:
        """Link the battle reference before battle.run() is called."""
        self._battle = battle
        self.focal_is_a = (battle.a.name == self.focal_army_name)

    @staticmethod
    def _snapshot_health(army) -> Dict[int, float]:
        return {id(u): u.current_health for u in army.units}

    @staticmethod
    def _damage_delta(army, snap_before: Dict[int, float]) -> float:
        """Total HP lost by all units in army since snap_before was taken."""
        total = 0.0
        for u in army.units:
            hp_before = snap_before.get(id(u), 0.0)
            total += max(0.0, hp_before - u.current_health)
        return total

    def on_event(self, event: object) -> None:  # noqa: C901 (simple dispatch)
        if isinstance(event, BattleStarted):
            if self._battle is not None:
                self.focal_is_a = (self._battle.a.name == self.focal_army_name)

        elif isinstance(event, RoundStarted):
            # Snapshot health at the START of the round, before any combat.
            self._snap_a = self._snapshot_health(self._army_a)
            self._snap_b = self._snapshot_health(self._army_b)

        elif isinstance(event, RoundEnded):
            # Identify which snapshot belongs to whom.
            if self.focal_is_a:
                my_snap = self._snap_a
                opp_snap = self._snap_b
                me_army = self._army_a
                opp_army = self._army_b
            else:
                my_snap = self._snap_b
                opp_snap = self._snap_a
                me_army = self._army_b
                opp_army = self._army_a

            me_taken = self._damage_delta(me_army, my_snap)
            opp_taken = self._damage_delta(opp_army, opp_snap)
            me_dealt = opp_taken   # damage I dealt = HP opponent lost

            # Units alive at end of round
            me_alive_end = sum(1 for u in me_army.units if u.is_alive)
            opp_alive_end = sum(1 for u in opp_army.units if u.is_alive)

            # Units alive at START of round (how many entered the round)
            me_start = sum(1 for v in my_snap.values() if v > 1e-9)
            opp_start = sum(1 for v in opp_snap.values() if v > 1e-9)

            self.round_data.append({
                "round": event.round_num,
                "dealt": me_dealt,
                "taken": me_taken,
                "me_alive": me_alive_end,
                "opp_alive": opp_alive_end,
                "me_start": me_start,
                "opp_start": opp_start,
            })

            self.final_a_vp = event.a_vp_total
            self.final_b_vp = event.b_vp_total


# ---------------------------------------------------------------------------
# Per-game runner
# ---------------------------------------------------------------------------

def run_pair(
    me_fac: str,
    me_side: str,
    opp_fac: str,
    seed: int,
    agg: dict,
) -> None:
    a_fac = me_fac if me_side == "A" else opp_fac
    b_fac = opp_fac if me_side == "A" else me_fac

    random.seed(seed)
    a = build_faction_random_army(
        "A", a_fac, 2000, rng=random.Random(seed), use_archetype=True,
    )
    b = build_faction_random_army(
        "B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True,
    )
    if not a.units or not b.units:
        return

    probe = RoundProbe(me_fac, a, b)
    battle = Battle(a, b, map_=_pick_rotation_map(seed), subscribers=[probe])
    probe.attach(battle)
    battle.run()

    # Secondary VP from the battle state (not in RoundEnded events)
    a_sec = battle._a_secondary_vp
    b_sec = battle._b_secondary_vp
    focal_sec = a_sec if me_side == "A" else b_sec
    opp_sec   = b_sec if me_side == "A" else a_sec
    focal_total_vp = probe.final_a_vp if me_side == "A" else probe.final_b_vp
    opp_total_vp   = probe.final_b_vp if me_side == "A" else probe.final_a_vp
    focal_prim = focal_total_vp - focal_sec
    opp_prim   = opp_total_vp   - opp_sec

    d = agg[me_fac]
    d["n"] += 1
    d["focal_prim"] += focal_prim
    d["opp_prim"]   += opp_prim
    d["focal_sec"]  += focal_sec
    d["opp_sec"]    += opp_sec
    d["total_dealt"] += sum(r["dealt"] for r in probe.round_data)
    d["total_taken"] += sum(r["taken"] for r in probe.round_data)
    # Total unit-rounds alive: how many units entered each round alive (summed)
    d["total_me_unit_rounds"]  += sum(r["me_start"]  for r in probe.round_data)
    d["total_opp_unit_rounds"] += sum(r["opp_start"] for r in probe.round_data)

    for rnd_info in probe.round_data:
        rnd = rnd_info["round"]
        d[f"dealt_r{rnd}"]      += rnd_info["dealt"]
        d[f"taken_r{rnd}"]      += rnd_info["taken"]
        d[f"me_alive_r{rnd}"]   += rnd_info["me_alive"]
        d[f"opp_alive_r{rnd}"]  += rnd_info["opp_alive"]
        d[f"me_start_r{rnd}"]   += rnd_info["me_start"]
        d[f"opp_start_r{rnd}"]  += rnd_info["opp_start"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agg: dict = defaultdict(lambda: defaultdict(float))

    for me in UNDER:
        for opp in OPPONENTS:
            if opp == me:
                continue
            for s in SEEDS:
                run_pair(me, "A", opp, s, agg)
                run_pair(me, "B", opp, s + 100, agg)

    print()
    print("=" * 100)
    print("DEEP UNDER-VALUATION DECOMPOSITION")
    print("Astra Militarum and Adeptus Mechanicus vs 7-opponent pool")
    print("=" * 100)

    # ------------------------------------------------------------------
    # Table 1 — per-round damage dealt / taken + survival curve
    # ------------------------------------------------------------------
    print()
    print("TABLE 1 — Per-round damage dealt and taken by under-shooter (avg per game)")
    print(
        f"{'Faction':<22}"
        f"{'Rnd':>4}"
        f"{'Dealt':>8}"
        f"{'Taken':>8}"
        f"{'D/T':>6}"
        f"{'MeAlive':>9}"
        f"{'OppAlive':>9}"
        f"{'Me%alive':>10}"
        f"{'Opp%alive':>10}"
    )
    print("-" * 97)

    for me in UNDER:
        d = agg[me]
        n = d["n"] or 1
        for rnd in range(1, MAX_ROUNDS + 1):
            dealt     = d[f"dealt_r{rnd}"] / n
            taken     = d[f"taken_r{rnd}"] / n
            me_alive  = d[f"me_alive_r{rnd}"] / n
            opp_alive = d[f"opp_alive_r{rnd}"] / n
            me_start  = d[f"me_start_r{rnd}"] / n
            opp_start = d[f"opp_start_r{rnd}"] / n
            dt_ratio  = dealt / max(0.01, taken)
            me_pct    = 100.0 * me_alive  / max(0.01, me_start)
            opp_pct   = 100.0 * opp_alive / max(0.01, opp_start)
            label = me if rnd == 1 else ""
            print(
                f"{label:<22}"
                f"{rnd:>4}"
                f"{dealt:>8.1f}"
                f"{taken:>8.1f}"
                f"{dt_ratio:>6.2f}"
                f"{me_alive:>9.1f}"
                f"{opp_alive:>9.1f}"
                f"{me_pct:>9.0f}%"
                f"{opp_pct:>9.0f}%"
            )
        tot_dealt = d["total_dealt"] / n
        tot_taken = d["total_taken"] / n
        tot_dt    = tot_dealt / max(0.01, tot_taken)
        print(
            f"{'  TOTAL':<22}"
            f"{'':>4}"
            f"{tot_dealt:>8.1f}"
            f"{tot_taken:>8.1f}"
            f"{tot_dt:>6.2f}"
        )
        print()

    # ------------------------------------------------------------------
    # Table 2 — VP split
    # ------------------------------------------------------------------
    print()
    print("TABLE 2 — End-of-game Victory Point split (avg per game)")
    print(
        f"{'Faction':<22}"
        f"{'ME-Primary':>12}"
        f"{'OPP-Primary':>12}"
        f"{'dPrimary':>10}"
        f"{'ME-Secondary':>13}"
        f"{'OPP-Secondary':>14}"
        f"{'dSecondary':>11}"
        f"{'ME-Total':>10}"
        f"{'OPP-Total':>10}"
    )
    print("-" * 107)
    for me in UNDER:
        d = agg[me]
        n = d["n"] or 1
        mp  = d["focal_prim"] / n
        op  = d["opp_prim"]   / n
        ms  = d["focal_sec"]  / n
        os_ = d["opp_sec"]    / n
        print(
            f"{me:<22}"
            f"{mp:>12.1f}"
            f"{op:>12.1f}"
            f"{mp - op:>10.1f}"
            f"{ms:>13.1f}"
            f"{os_:>14.1f}"
            f"{ms - os_:>11.1f}"
            f"{mp + ms:>10.1f}"
            f"{op + os_:>10.1f}"
        )

    # ------------------------------------------------------------------
    # Table 3 — per-alive-unit output (isolates mechanism 1 vs 2)
    # ------------------------------------------------------------------
    print()
    print("TABLE 3 — Per-alive-unit-round output")
    print("  Wounds dealt per surviving unit per round entering the round.")
    print("  Isolates durability (1) from output-buff gap (2):")
    print("    Output ratio ~1.0 but ME unit-rounds << OPP unit-rounds => (1) DURABILITY")
    print("    Output ratio << 1.0 regardless of unit-round count => (2) OUTPUT/BUFF GAP")
    print()
    print(
        f"{'Faction':<22}"
        f"{'ME unit-rnds':>14}"
        f"{'OPP unit-rnds':>14}"
        f"{'ME dealt':>10}"
        f"{'OPP dealt*':>11}"
        f"{'ME dmg/u-rnd':>13}"
        f"{'OPP dmg/u-rnd':>14}"
        f"{'Output ratio':>13}"
    )
    print("  * OPP dealt = under-shooter taken (wounds removed from focal army by opponent)")
    print("-" * 105)
    for me in UNDER:
        d = agg[me]
        n = d["n"] or 1
        me_unit_rounds  = d["total_me_unit_rounds"]  / n
        opp_unit_rounds = d["total_opp_unit_rounds"] / n
        me_total_dealt  = d["total_dealt"]           / n
        opp_total_dealt = d["total_taken"]           / n   # opp dealt = my taken
        me_output   = me_total_dealt  / max(0.01, me_unit_rounds)
        opp_output  = opp_total_dealt / max(0.01, opp_unit_rounds)
        output_ratio = me_output / max(0.01, opp_output)
        print(
            f"{me:<22}"
            f"{me_unit_rounds:>14.1f}"
            f"{opp_unit_rounds:>14.1f}"
            f"{me_total_dealt:>10.1f}"
            f"{opp_total_dealt:>11.1f}"
            f"{me_output:>13.3f}"
            f"{opp_output:>14.3f}"
            f"{output_ratio:>13.2f}"
        )

    # ------------------------------------------------------------------
    # Interpretation key
    # ------------------------------------------------------------------
    print()
    print("=" * 100)
    print("INTERPRETATION KEY")
    print("=" * 100)
    print()
    print("TABLE 1 — D/T < 1.0 = faction takes more damage than it deals.")
    print("  Survival curve: if Me%alive collapses in rounds 1-2 => (1) DURABILITY.")
    print("  If Me%alive stays high but D/T remains low => (2) OUTPUT gap.")
    print()
    print("TABLE 2 — dPrimary large negative => (3) POSITIONING/VP gap.")
    print("  dSecondary near zero => secondary scoring is not the root cause.")
    print()
    print("TABLE 3 — Output ratio < 1.0 = under-shooter deals less per surviving unit.")
    print("  ratio ~1.0 + ME unit-rounds << OPP => (1) DURABILITY dominates.")
    print("  ratio << 1.0 + ME unit-rounds comparable => (2) OUTPUT/BUFF GAP dominates.")
    print()
    print("Candidate unmodelled output buffs:")
    print("  Astra Militarum Orders: +1 to hit or re-roll 1s to hit, once per Officer")
    print("    per Command phase. (Wahapedia: 'Voice of Command'.)")
    print("  Adeptus Mechanicus Doctrina Imperatives: +1 to hit (Protector) or")
    print("    +1 to wound (Conqueror), chosen at start of each battle round.")
    print("    (Wahapedia: 'Doctrina Imperatives'.)")
