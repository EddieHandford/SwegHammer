"""Concrete AM firepower-gap instrument: how much of AM's shooting actually
happens in the sim. Per game (averaged over seeds), measures:
  - AM Orders issued per round (Order COVERAGE: buffed squads vs total squads)
  - indirect-fire shots fired (is the artillery used?)
  - total AM ranged attacks, damage dealt, enemy models killed
so we can compare the sim's output to what a real Order-stacked AM gunline does.

  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._diag_am_firepower 10 "World Eaters"
"""
from __future__ import annotations

import random
import sys
from collections import defaultdict

from code import orders
from code.army_builder import build_faction_random_army
from code.events import EventLog, UnitShot, UnitKilled, RoundStarted, RoundEnded
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

_orig_dispatch = orders.dispatch_orders


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    opp = sys.argv[2] if len(sys.argv) > 2 else "World Eaters"

    tot = defaultdict(float)
    for seed in range(n):
        am = build_faction_random_army("A", "Astra Militarum", 2000,
                                       rng=random.Random(seed), use_archetype=True)
        ob = build_faction_random_army("B", opp, 2000,
                                       rng=random.Random(seed + 10_000), use_archetype=True)
        battle = Battle(am, ob, subscribers=[EventLog()], map_=_pick_rotation_map(seed))
        # uid -> (army, profile) needs uids assigned; Battle assigns them in run().
        am_orders = [0]

        def _wrap(army, *a, **k):
            res = _orig_dispatch(army, *a, **k)
            if army is am:
                am_orders[0] += len(res)
            return res
        orders.dispatch_orders = _wrap
        try:
            battle.run()
        finally:
            orders.dispatch_orders = _orig_dispatch

        log = battle._subscribers[0] if hasattr(battle, "_subscribers") else None
        # fall back: find the EventLog
        if log is None or not hasattr(log, "events"):
            for s in getattr(battle, "subscribers", []) or []:
                if hasattr(s, "events"):
                    log = s
        ev = log.events
        uid2prof = {u.uid: u.profile for u in list(am.units) + list(ob.units)}
        am_uids = {u.uid for u in am.units}
        ob_uids = {u.uid for u in ob.units}
        am_shots = am_dmg = indirect_shots = enemy_killed = 0.0
        for e in ev:
            if isinstance(e, UnitShot) and e.attacker_uid in am_uids:
                am_shots += 1
                am_dmg += e.damage
                p = uid2prof.get(e.attacker_uid)
                if p is not None and getattr(p, "indirect_fire", False):
                    indirect_shots += 1
            elif isinstance(e, UnitKilled) and e.unit_uid in ob_uids:
                enemy_killed += 1
        # AM squad count (distinct squad_id among AM units)
        sids = {getattr(u, "squad_id", -1) for u in am.units}
        sids.discard(-1)
        tot["am_units"] += len(am.units)
        tot["am_squads"] += len(sids) if sids else 0
        tot["orders"] += am_orders[0]
        tot["am_shots"] += am_shots
        tot["am_dmg"] += am_dmg
        tot["indirect_shots"] += indirect_shots
        tot["enemy_killed"] += enemy_killed
        tot["enemy_total"] += len(ob.units)

    g = n
    print(f"AM firepower instrument — AM vs {opp}, averaged over {n} games")
    print(f"  AM army:                {tot['am_units']/g:.0f} models in {tot['am_squads']/g:.0f} squads")
    print(f"  AM Orders issued/GAME:  {tot['orders']/g:.1f}   (~{tot['orders']/g/5:.1f}/round; vs ~{tot['am_squads']/g:.0f} AM squads)")
    print(f"  AM ranged attacks/game: {tot['am_shots']/g:.0f}")
    print(f"  indirect-fire shots/game:{tot['indirect_shots']/g:.1f}")
    print(f"  AM damage dealt/game:   {tot['am_dmg']/g:.0f}")
    print(f"  enemy models killed/game:{tot['enemy_killed']/g:.1f}  of {tot['enemy_total']/g:.0f}")
    print("  [done]")


if __name__ == "__main__":
    main()
