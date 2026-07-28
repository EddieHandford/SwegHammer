"""Localise the under-performance gap for Chaos Daemons (~33% sim vs ~52% real)
and Genestealer Cults (~25% sim vs ~47% real).

The mechanic check shows reserves / Deep Strike / Cult Ambush / battle-shock
are all present.  This script tests four behavioural hypotheses:

  h1 — Arrival timing: do reserves land late (round 4-5)?
  h2 — Arrival position: do they land near objectives or in the backfield?
       (>9" from any objective = backfield; <=9" = near; <=3" = on-marker)
  h3 — Post-arrival contest: do landed units hold a marker the SAME round?
  h4 — Primary VP curve: does the under-pole score primary VP early or only
       after round 3 when bodies are already dead?

Matchups: each faction vs 3 opponents (Imperial Knights = elite over-pole,
Adeptus Astartes = midfield, Aeldari = fast/positional).  3 seeds per pair,
both sides, = 18 battles per faction.

Run:
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_daemons_gsc_underpole
"""
from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import List, Tuple

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from code.events import UnitDeepStrike, RoundEnded
import scripts.evaluate_vs_meta as ev


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UNDER_FACTIONS = ["Chaos Daemons", "Genestealer Cults"]
OPPONENTS = ["Imperial Knights", "Adeptus Astartes", "Aeldari"]
SEEDS = [1, 2, 3]
POINTS = 2000


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _min_obj_dist(pos: Tuple[float, float], objectives) -> float:
    if not objectives:
        return 999.0
    return min(_dist(pos, (o.x, o.y)) for o in objectives)


# ---------------------------------------------------------------------------
# Per-battle instrumentation subscriber
# ---------------------------------------------------------------------------

@dataclass
class BattleInstrument:
    """Subscribes to a Battle's event stream and records the signals we need."""

    battle: object          # Battle instance (duck-typed)
    under_name: str         # name of the army under test ("A" or "B")

    # Deep-strike arrivals: (round, dist_to_nearest_objective)
    arrivals: List[Tuple[int, float]] = field(default_factory=list)
    # Round -> primary VP for the under-pole army at the END of that round
    primary_by_round: dict = field(default_factory=dict)
    # Set of unit uids that arrived this round (reset each RoundEnded)
    _arrived_this_round: set = field(default_factory=set)

    # Current round tracked from RoundEnded
    _current_round: int = 0

    def on_event(self, event) -> None:
        if isinstance(event, UnitDeepStrike):
            # Find which army owns this unit to tag arrivals for the under-pole only.
            b = self.battle
            under_army = b.a if self.under_name == "A" else b.b
            uid = event.unit_uid
            owner_is_under = any(u.uid == uid for u in under_army.units)
            if not owner_is_under:
                # Also check reserves (unit just arrived so it's in army.units
                # after _arrive_from_reserves, but belt-and-braces).
                owner_is_under = any(
                    u.uid == uid
                    for u in list(b._reserves.get(under_army.name, []))
                )
            if owner_is_under:
                d = _min_obj_dist(event.position, b.map.objectives)
                self._arrived_this_round.add(uid)
                self.arrivals.append((self._current_round + 1, d))

        elif isinstance(event, RoundEnded):
            rnd = getattr(event, "round_num", self._current_round + 1)
            self._current_round = rnd
            b = self.battle
            if self.under_name == "A":
                pri = b._a_vp - b._a_secondary_vp
            else:
                pri = b._b_vp - b._b_secondary_vp
            self.primary_by_round[rnd] = pri
            self._arrived_this_round.clear()


# ---------------------------------------------------------------------------
# Helper: count units on an objective at game-end for the under-pole side
# ---------------------------------------------------------------------------

def _count_on_objective(army, objectives) -> int:
    n = 0
    for u in army.units:
        if not u.is_alive:
            continue
        for o in objectives:
            if _dist(u.position, (o.x, o.y)) <= o.control_radius:
                n += 1
                break
    return n


# ---------------------------------------------------------------------------
# Run one battle, return stats
# ---------------------------------------------------------------------------

def _run_battle(under_fac: str, opp_fac: str, seed: int, under_is_A: bool) -> dict:
    af = under_fac if under_is_A else opp_fac
    bf = opp_fac if under_is_A else under_fac
    a = build_faction_random_army("A", af, POINTS,
                                  rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", bf, POINTS,
                                  rng=random.Random(seed + 9000), use_archetype=True)
    if not a.units or not b.units:
        return None

    under_name = "A" if under_is_A else "B"
    battle = Battle(a, b, map_=ev._pick_rotation_map(seed))
    instr = BattleInstrument(battle=battle, under_name=under_name)
    battle.subscribers.append(instr)
    result = battle.run()

    under_army = a if under_is_A else b
    opp_army = b if under_is_A else a
    under_start = result.a_start if under_is_A else result.b_start
    under_surv = result.a_survivors if under_is_A else result.b_survivors
    opp_start = result.b_start if under_is_A else result.a_start
    opp_surv = result.b_survivors if under_is_A else result.a_survivors

    under_pri = (battle._a_vp - battle._a_secondary_vp) if under_is_A else (battle._b_vp - battle._b_secondary_vp)
    under_sec = battle._a_secondary_vp if under_is_A else battle._b_secondary_vp
    opp_pri   = (battle._b_vp - battle._b_secondary_vp) if under_is_A else (battle._a_vp - battle._a_secondary_vp)

    won = result.winner == under_name

    # Deep-strike arrival stats
    arrivals = instr.arrivals  # [(round, dist_to_obj)]
    n_arr = len(arrivals)
    backfield = sum(1 for (_, d) in arrivals if d > 9.0)
    near_obj  = sum(1 for (_, d) in arrivals if d <= 9.0)
    on_marker = sum(1 for (_, d) in arrivals if d <= 3.0)
    avg_arr_round = (sum(r for (r, _) in arrivals) / n_arr) if n_arr else None
    avg_arr_dist  = (sum(d for (_, d) in arrivals) / n_arr) if n_arr else None

    # Primary VP curve (h4)
    primary_by_round = instr.primary_by_round

    # On-objective count at game end (h3 proxy)
    on_obj_end = _count_on_objective(under_army, battle.map.objectives)

    return dict(
        won=won,
        rounds=result.rounds,
        under_surv_pct=100.0 * under_surv / max(1, under_start),
        opp_surv_pct=100.0 * opp_surv / max(1, opp_start),
        under_pri=under_pri,
        under_sec=under_sec,
        opp_pri=opp_pri,
        n_arrivals=n_arr,
        backfield=backfield,
        near_obj=near_obj,
        on_marker=on_marker,
        avg_arr_round=avg_arr_round,
        avg_arr_dist=avg_arr_dist,
        primary_by_round=primary_by_round,
        on_obj_end=on_obj_end,
        kills_dealt=opp_start - opp_surv,
        kills_taken=under_start - under_surv,
    )


# ---------------------------------------------------------------------------
# Aggregate + print
# ---------------------------------------------------------------------------

def _mean(vals, default=0.0):
    return sum(vals) / len(vals) if vals else default


def run_faction(faction: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {faction}")
    print(f"{'='*70}")

    all_stats = []
    for opp in OPPONENTS:
        opp_stats = []
        for seed in SEEDS:
            for under_is_A in (True, False):
                s = _run_battle(faction, opp, seed, under_is_A)
                if s is None:
                    continue
                opp_stats.append(s)
        all_stats.extend(opp_stats)

        wins = sum(1 for s in opp_stats if s["won"])
        n = len(opp_stats)
        arr_rounds = [s["avg_arr_round"] for s in opp_stats if s["avg_arr_round"] is not None]
        arr_dists  = [s["avg_arr_dist"]  for s in opp_stats if s["avg_arr_dist"]  is not None]
        backfield_pct = 100.0 * sum(s["backfield"] for s in opp_stats) / max(1, sum(s["n_arrivals"] for s in opp_stats))
        near_pct      = 100.0 * sum(s["near_obj"]  for s in opp_stats) / max(1, sum(s["n_arrivals"] for s in opp_stats))
        on_pct        = 100.0 * sum(s["on_marker"] for s in opp_stats) / max(1, sum(s["n_arrivals"] for s in opp_stats))
        print(f"\n  vs {opp:20}  [{n} battles, {wins}/{n} wins = {100*wins//max(1,n)}%]")
        print(f"    Survival  : under {_mean([s['under_surv_pct'] for s in opp_stats]):.0f}%  "
              f"opp {_mean([s['opp_surv_pct'] for s in opp_stats]):.0f}%"
              f"   kills dealt {_mean([s['kills_dealt'] for s in opp_stats]):.1f}  "
              f"taken {_mean([s['kills_taken'] for s in opp_stats]):.1f}")
        print(f"    Primary VP: under {_mean([s['under_pri'] for s in opp_stats]):.1f}  "
              f"opp {_mean([s['opp_pri'] for s in opp_stats]):.1f}  "
              f"secondary {_mean([s['under_sec'] for s in opp_stats]):.1f}")
        print(f"    Arrivals  : n={sum(s['n_arrivals'] for s in opp_stats)}"
              f"  avg_round={_mean(arr_rounds):.2f}"
              f"  avg_dist_to_obj={_mean(arr_dists):.1f}\""
              f"  backfield(>9\")={backfield_pct:.0f}%"
              f"  near(<=9\")={near_pct:.0f}%"
              f"  on-marker(<=3\")={on_pct:.0f}%")
        print(f"    End-game  : on-obj at game-end {_mean([s['on_obj_end'] for s in opp_stats]):.1f} units")

        # Primary-VP-by-round curve
        by_round: dict = {}
        for s in opp_stats:
            for rnd, vp in s["primary_by_round"].items():
                by_round.setdefault(rnd, []).append(vp)
        curve = "  ".join(
            f"T{r}={_mean(by_round.get(r,[])):.0f}"
            for r in sorted(by_round.keys())
        )
        print(f"    PrimaryVP curve: {curve}")

    # Aggregate across all opponents
    n_tot = len(all_stats)
    if n_tot == 0:
        return
    wins_tot = sum(1 for s in all_stats if s["won"])
    total_arrivals = sum(s["n_arrivals"] for s in all_stats)
    backfield_all = sum(s["backfield"] for s in all_stats)
    near_all      = sum(s["near_obj"] for s in all_stats)
    on_all        = sum(s["on_marker"] for s in all_stats)
    arr_rounds_all = [s["avg_arr_round"] for s in all_stats if s["avg_arr_round"] is not None]
    arr_dists_all  = [s["avg_arr_dist"]  for s in all_stats if s["avg_arr_dist"]  is not None]

    print(f"\n  --- OVERALL {faction} ({n_tot} battles) ---")
    print(f"  Win rate  : {100*wins_tot//max(1,n_tot)}%  (real ~{'52' if 'Daemon' in faction else '47'}%)")
    print(f"  Survival  : under {_mean([s['under_surv_pct'] for s in all_stats]):.0f}%  "
          f"opp {_mean([s['opp_surv_pct'] for s in all_stats]):.0f}%")
    print(f"  Primary VP: under {_mean([s['under_pri'] for s in all_stats]):.1f}  "
          f"opp {_mean([s['opp_pri'] for s in all_stats]):.1f}  "
          f"secondary {_mean([s['under_sec'] for s in all_stats]):.1f}")
    print(f"  Arrivals  : total {total_arrivals}"
          f"  avg_round={_mean(arr_rounds_all):.2f}"
          f"  avg_dist={_mean(arr_dists_all):.1f}\""
          f"  backfield={100*backfield_all//max(1,total_arrivals)}%"
          f"  near={100*near_all//max(1,total_arrivals)}%"
          f"  on-marker={100*on_all//max(1,total_arrivals)}%")
    print(f"  On-obj at game-end: {_mean([s['on_obj_end'] for s in all_stats]):.1f} units")

    by_round_all: dict = {}
    for s in all_stats:
        for rnd, vp in s["primary_by_round"].items():
            by_round_all.setdefault(rnd, []).append(vp)
    curve_all = "  ".join(
        f"T{r}={_mean(by_round_all.get(r,[])):.0f}"
        for r in sorted(by_round_all.keys())
    )
    print(f"  Primary VP curve (all): {curve_all}")

    # Hypothesis verdicts
    print(f"\n  HYPOTHESIS VERDICTS:")
    avg_dist = _mean(arr_dists_all)
    backfield_frac = backfield_all / max(1, total_arrivals)
    avg_arr_r = _mean(arr_rounds_all)
    under_pri_mean = _mean([s["under_pri"] for s in all_stats])
    opp_pri_mean   = _mean([s["opp_pri"]  for s in all_stats])
    under_surv_mean = _mean([s["under_surv_pct"] for s in all_stats])
    opp_surv_mean   = _mean([s["opp_surv_pct"] for s in all_stats])

    h1_flag = avg_arr_r > 3.2
    h2_flag = backfield_frac > 0.50
    h3_flag = _mean([s["on_obj_end"] for s in all_stats]) < 1.0
    h4_flag = (
        _mean(by_round_all.get(1, [])) < 5.0
        and _mean(by_round_all.get(2, [])) < 12.0
    )
    print(f"  h1 (late arrival): avg_round={avg_arr_r:.2f}  TRIGGERED={h1_flag}")
    print(f"  h2 (backfield land): backfield%={100*backfield_frac:.0f}%  avg_dist={avg_dist:.1f}\"  TRIGGERED={h2_flag}")
    print(f"  h3 (post-land no-contest): on-obj-end={_mean([s['on_obj_end'] for s in all_stats]):.1f}  TRIGGERED={h3_flag}")
    print(f"  h4 (primary-VP starvation): T1={_mean(by_round_all.get(1,[])):.1f}  T2={_mean(by_round_all.get(2,[])):.1f}  TRIGGERED={h4_flag}")
    durability_gap = opp_surv_mean > under_surv_mean + 15.0
    print(f"  durability/combat-output gap: under_surv={under_surv_mean:.0f}%  opp_surv={opp_surv_mean:.0f}%  "
          f"TRIGGERED={durability_gap}  (under-priVP={under_pri_mean:.1f}  opp-priVP={opp_pri_mean:.1f})")


def main() -> None:
    print("=== Daemons + GSC under-pole localisation ===")
    print("Matchups: vs Imperial Knights, Adeptus Astartes, Aeldari")
    print("3 seeds x 2 sides = 6 battles per matchup, 18 per faction\n")
    for fac in UNDER_FACTIONS:
        run_faction(fac)
    print("\n=== END ===")


if __name__ == "__main__":
    main()
