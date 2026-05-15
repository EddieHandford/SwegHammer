"""
One-battle event trace: Tyranids vs T'au (worst matchup, +48.7pt).

Captures OC composition per round, kill-target patterns, and synapse coverage
to test H2 (synapse shelters swarm) and H3 (opponent AI ignores screens).
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict

from code.archetypes import build_archetype_army, has_archetype
from code.army_builder import build_faction_random_army
from code.events import (
    BattleshockFailed, EventLog, ObjectiveScored, RoundEnded,
    RoundStarted, UnitCharged, UnitKilled, UnitShot, UnitFought,
    UnitMoved,
)
from code.maps import DEFAULT_MAP
from code.simulator import Battle


def _build(faction: str, name: str, budget: float, seed: int):
    rng = random.Random(seed)
    if has_archetype(faction):
        return build_archetype_army(name, faction, budget, rng=rng)
    return build_faction_random_army(name, faction, budget, rng=rng)


def trace_battle(opp: str, seed: int = 0) -> None:
    random.seed(1000 + seed)
    tyr = _build("Tyranids", "TYR", 1000, seed=seed)
    op = _build(opp, "OPP", 1000, seed=seed + 50000)

    # Map uid -> (army_name, unit profile_name, points, oc)
    uid_info = {}
    for army in (tyr, op):
        for u in army.units:
            # uids assigned by sim at start; capture from id() temporarily.
            pass

    log = EventLog()
    battle = Battle(tyr, op, map_=DEFAULT_MAP, subscribers=[log])
    r = battle.run()

    # Build uid_info from BattleStarted snapshot.
    from code.events import BattleStarted, InitialUnit
    info = {}
    for e in log.events:
        if isinstance(e, BattleStarted):
            for iu in e.units:
                info[iu.uid] = (iu.army, iu.name)
            break

    # Map uid -> profile lookup for OC and SYNAPSE.
    name_to_profile = {}
    for army in (tyr, op):
        for u in army.units:
            name_to_profile[(army.name, u.profile.name)] = u.profile

    # Per-round breakdowns.
    current_round = 0
    kills_per_round = defaultdict(lambda: Counter())  # round -> killer_army -> Counter(victim_profile)
    shots_per_round = defaultdict(lambda: defaultdict(int))  # round -> (attacker_army, target_army) -> count
    target_choice = defaultdict(Counter)  # attacker_army -> Counter(victim_profile) over the battle

    for e in log.events:
        if isinstance(e, RoundStarted):
            current_round = e.round_num
        elif isinstance(e, UnitKilled):
            victim_army, victim_name = info.get(e.unit_uid, ("?", "?"))
            kills_per_round[current_round][victim_army] += 1
            kills_per_round[current_round][(victim_army, victim_name)] += 1
        elif isinstance(e, UnitShot):
            atk_army, _ = info.get(e.attacker_uid, ("?", "?"))
            tgt_army, tgt_name = info.get(e.target_uid, ("?", "?"))
            shots_per_round[current_round][(atk_army, tgt_army)] += 1
            target_choice[atk_army][tgt_name] += 1
        elif isinstance(e, UnitFought):
            atk_army, _ = info.get(e.attacker_uid, ("?", "?"))
            tgt_army, tgt_name = info.get(e.target_uid, ("?", "?"))
            shots_per_round[current_round][(atk_army, tgt_army)] += 1
            target_choice[atk_army][tgt_name] += 1
        elif isinstance(e, RoundEnded):
            pass

    print(f"=== Tyranids (TYR) vs {opp} (OPP), seed={seed} ===")
    print(f"Result: {r.winner}, final VP {r.a_vp}/{r.b_vp}, rounds {r.rounds}")
    print()
    print("Per-round kills (victim army):")
    for rd in sorted(kills_per_round):
        d = kills_per_round[rd]
        tyr_k = d.get("TYR", 0)
        opp_k = d.get("OPP", 0)
        print(f"  R{rd}: TYR-units-killed={tyr_k}, OPP-units-killed={opp_k}")
    print()
    print("Per-round shots-or-melee (attacker -> target army):")
    for rd in sorted(shots_per_round):
        d = shots_per_round[rd]
        tt = d.get(("TYR", "TYR"), 0); to = d.get(("TYR", "OPP"), 0)
        ot = d.get(("OPP", "TYR"), 0); oo = d.get(("OPP", "OPP"), 0)
        print(f"  R{rd}: TYR->OPP={to}, OPP->TYR={ot}  (self/other: TYR->TYR={tt}, OPP->OPP={oo})")
    print()
    print(f"OPP target-choice over the battle (top 8 targets):")
    for n, c in target_choice["OPP"].most_common(8):
        # Pull OC and SYNAPSE for context
        prof = name_to_profile.get(("TYR", n))
        oc_str = f"OC={prof.oc}" if prof else "OC=?"
        kw = ("SYNAPSE" if prof and "SYNAPSE" in (prof.unit_keywords or ()) else "")
        print(f"  {n:35s} attacks={c:4d}  {oc_str}  {kw}")
    print()
    print(f"TYR target-choice (top 8):")
    for n, c in target_choice["TYR"].most_common(8):
        print(f"  {n:35s} attacks={c:4d}")


if __name__ == "__main__":
    import sys
    opp = sys.argv[1] if len(sys.argv) > 1 else "T'au Empire"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    trace_battle(opp, seed)
