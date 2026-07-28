"""Astra Militarum ORDER-COVERAGE fidelity diagnostic (the queued 2026-07-02 thread).

The ledger records "~1.4 Orders/round reach ~9% of squads" as an OLD finding and
registers the question "does the sim under-issue Orders vs the real officer
economy?" as queued-never-run. This measures it on the CURRENT frame.

For each Astra Militarum battle round it records:
  * officers alive and their per-datasheet Order caps (the rules-legal ceiling)
  * Orders actually issued
  * how many orderable squads existed, and how many were inside SOME officer's
    6" aura (the coverage denominator)
  * for each unissued Order, whether the officer had NO eligible squad in aura

Read-only: it monkeypatches the dispatcher to observe, changing nothing.

Run: PYTHONHASHSEED=0 python -m scripts._am_order_coverage
"""
from __future__ import annotations
import os
import random
from collections import Counter, defaultdict

import code.orders as O
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

AM = "Astra Militarum"
OPPS = ["Death Guard", "Adeptus Astartes", "Imperial Knights", "Aeldari", "T'au Empire"]
N = int(os.environ.get("OC_N", "6"))
_idx = {f: i for i, f in enumerate(FACTIONS)}

STATS = {
    "rounds": 0,
    "cap": 0,          # rules-legal Orders available (sum of live officers' caps)
    "issued": 0,       # Orders actually issued
    "officers": 0,     # live officer-units summed over rounds
    "squads": 0,       # orderable AM squads summed over rounds
    "covered": 0,      # of those, inside some officer's aura AND keyword-eligible
    "starved": 0,      # officer-Order slots that found no eligible squad in aura
}
ORDER_MIX = Counter()
TARGET_MIX = Counter()
OFFICER_ROSTER = Counter()
PER_ROUND = defaultdict(lambda: {"cap": 0, "issued": 0, "rounds": 0})
PER_OFFICER = defaultdict(lambda: {"cap": 0, "reach": 0, "short": 0, "n": 0})

_real_dispatch = O.dispatch_orders


def _instrumented(army, battleshocked_uids, enemy_army=None):
    issued = _real_dispatch(army, battleshocked_uids, enemy_army=enemy_army)
    if not any((u.profile.faction or "") == AM for u in army.units):
        return issued
    rnd = getattr(getattr(army, "_battle_ref", None), "round_num", 0) or 0

    # Re-derive the ceiling exactly as the dispatcher does (same dedupe key).
    _issuer_by_squad = os.environ.get("SWEG_ORDER_ISSUER_BY_SQUAD", "1") != "0"
    seen = set()
    officers = []
    for u in army.alive_units:
        if not O._is_am_officer(u) or u.uid in battleshocked_uids:
            continue
        sid = getattr(u, "squad_id", -1)
        key = (("squad", sid) if sid >= 0 else ("solo", u.uid)) if _issuer_by_squad else (u.profile.name or "")
        if key in seen:
            continue
        seen.add(key)
        officers.append(u)
    cap = sum(O.OFFICER_ORDER_COUNTS[o.profile.name or ""] for o in officers)

    # Orderable squads and how many sit inside some officer's aura.
    targets = [
        u for u in army.alive_units
        if (u.profile.faction or "") == AM
        and u.uid not in battleshocked_uids
        and set(u.profile.unit_keywords or ()) & {"REGIMENT", "SQUADRON", "TITANIC"}
    ]
    squads = {}
    for t in targets:
        sid = getattr(t, "squad_id", -1)
        squads.setdefault(("squad", sid) if sid >= 0 else ("solo", t.uid), []).append(t)
    squadron_allowed = bool(getattr(army, "orders_eligible_squadron_this_round", False))
    covered = 0
    for _key, members in squads.items():
        for o in officers:
            if not O._is_order_target_eligible(
                members[0], squadron_allowed=squadron_allowed,
                officer_target_types=O._officer_target_types(o.profile.name or ""),
            ):
                continue
            if any(O._aura_gap(o, m) <= O.OFFICER_AURA_RANGE for m in members):
                covered += 1
                break

    # Per-officer starvation: how many eligible squads sit in THIS officer's
    # aura versus the Orders it is entitled to issue. `short` is the Orders it
    # could not place for want of a distinct eligible squad in range.
    for o in officers:
        cap_o = O.OFFICER_ORDER_COUNTS[o.profile.name or ""]
        reach = sum(
            1 for _k, members in squads.items()
            if O._is_order_target_eligible(
                members[0], squadron_allowed=squadron_allowed,
                officer_target_types=O._officer_target_types(o.profile.name or ""),
            )
            and any(O._aura_gap(o, m) <= O.OFFICER_AURA_RANGE for m in members)
        )
        d = PER_OFFICER[o.profile.name or ""]
        d["cap"] += cap_o
        d["reach"] += reach
        d["short"] += max(0, cap_o - reach)
        d["n"] += 1

    STATS["rounds"] += 1
    STATS["cap"] += cap
    STATS["issued"] += len(issued)
    STATS["officers"] += len(officers)
    STATS["squads"] += len(squads)
    STATS["covered"] += covered
    STATS["starved"] += max(0, cap - len(issued))
    PER_ROUND[rnd]["cap"] += cap
    PER_ROUND[rnd]["issued"] += len(issued)
    PER_ROUND[rnd]["rounds"] += 1
    for o in officers:
        OFFICER_ROSTER[o.profile.name or ""] += 1
    for _oname, tname, order in issued:
        ORDER_MIX[order] += 1
        TARGET_MIX[tname] += 1
    return issued


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    O.dispatch_orders = _instrumented
    import code.simulator as SIM
    SIM.dispatch_orders = _instrumented  # in case of a module-level rebind

    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[AM] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            a = build_faction_random_army("A", AM, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            Battle(a, b, map_=_pick_rotation_map(seed), primary_mission=_pick_primary_mission(ps)).run()

    r = STATS["rounds"]
    print(f"=== ORDER COVERAGE — Astra Militarum, {len(OPPS)*N} games, {r} command phases ===")
    print(f"live officer-units / round : {STATS['officers']/r:.2f}")
    print(f"rules-legal Order cap/round: {STATS['cap']/r:.2f}")
    print(f"Orders ISSUED / round      : {STATS['issued']/r:.2f}"
          f"   ({100*STATS['issued']/max(1,STATS['cap']):.0f}% of the legal ceiling)")
    print(f"unissued (starved) / round : {STATS['starved']/r:.2f}")
    print(f"orderable squads / round   : {STATS['squads']/r:.2f}")
    print(f"  of those, in some aura   : {STATS['covered']/r:.2f}"
          f"   ({100*STATS['covered']/max(1,STATS['squads']):.0f}% coverage)")
    print(f"squads RECEIVING an Order  : {100*STATS['issued']/max(1,STATS['squads']):.0f}% of squads/round")
    print("\nby round (cap -> issued):")
    for rnd in sorted(PER_ROUND):
        d = PER_ROUND[rnd]
        if not d["rounds"]:
            continue
        print(f"  R{rnd}: {d['cap']/d['rounds']:.2f} -> {d['issued']/d['rounds']:.2f}")
    print("\nofficer roster (unit-rounds alive):")
    for name, c in OFFICER_ROSTER.most_common():
        print(f"  {c/r:5.2f}/round  {name}  (cap {O.OFFICER_ORDER_COUNTS[name]})")
    print("\nper-officer starvation (Orders entitled vs distinct eligible squads in aura):")
    for name, d in sorted(PER_OFFICER.items(), key=lambda x: -x[1]["short"]):
        if not d["n"]:
            continue
        print(f"  {name:24s} cap {d['cap']/d['n']:.2f}  reach {d['reach']/d['n']:.2f}"
              f"  UNPLACEABLE {d['short']/d['n']:.2f}/round")
    print("\nOrder mix:")
    for name, c in ORDER_MIX.most_common():
        print(f"  {100*c/max(1,STATS['issued']):5.1f}%  {name}")
    print("\ntop Order recipients:")
    for name, c in TARGET_MIX.most_common(10):
        print(f"  {100*c/max(1,STATS['issued']):5.1f}%  {name}")
