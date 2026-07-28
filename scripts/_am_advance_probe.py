"""Check the user's game-watching observations: (1) are AM units Advancing every
turn (forfeiting shooting)? (2) does a transport sit at the back holding a point?
(3) do AM units move into cover? Instruments real Battles. Read-only. Not committed."""
from __future__ import annotations
import random, sys
from collections import defaultdict
from code.army_builder import build_faction_random_army
from code.events import BattleStarted, RoundStarted, UnitMoved, UnitAdvanced, EventLog
from code.simulator import Battle
from code.roles import classify
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC = "Astra Militarum"
OPPS = ["Necrons", "Adeptus Astartes", "Orks"]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
_idx = {f: i for i, f in enumerate(FACTIONS)}

# advance rate by role, transport behaviour, cover usage
adv = defaultdict(int); mov = defaultdict(int)   # role -> counts of advance / any-move
tr_games = 0; tr_backfield_hold = 0; tr_total = 0
cover_end = [0, 0]  # [in_cover, total] AM units at game end

for opp in OPPS:
    for seed in range(N):
        ps = (_idx[A_FAC] * 1000 + _idx[opp]) * 100 + seed
        random.seed(ps)
        a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
        lg = EventLog(); map_ = _pick_rotation_map(seed); pr = _pick_primary_mission(ps)
        Battle(a, b, subscribers=[lg], map_=map_, primary_mission=pr).run()
        ev = lg.events
        info = {}
        for e in ev:
            if isinstance(e, BattleStarted):
                for u in e.units:
                    if u.army == "A":
                        info[u.uid] = u.name
        # role + keywords per AM unit (from the army objects)
        role_of = {}; kw_of = {}
        for u in a.units:
            role_of[u.uid] = classify(u.profile)
            kw_of[u.uid] = set(u.profile.unit_keywords or ())
        advanced_uids_by_round = defaultdict(set)
        moved_uids_by_round = defaultdict(set)
        cur = 0
        for e in ev:
            if isinstance(e, RoundStarted):
                cur = e.round_num
            elif isinstance(e, UnitAdvanced) and e.unit_uid in info:
                advanced_uids_by_round[cur].add(e.unit_uid)
            elif isinstance(e, UnitMoved) and e.unit_uid in info:
                moved_uids_by_round[cur].add(e.unit_uid)
        for rnd in range(1, 6):
            for uid in moved_uids_by_round.get(rnd, set()):
                r = role_of.get(uid, "?")
                mov[r] += 1
                if uid in advanced_uids_by_round.get(rnd, set()):
                    adv[r] += 1
        # transports: TRANSPORT keyword, final position vs deployment half + on-marker
        objs = map_.objectives
        for u in a.units:
            if "TRANSPORT" in kw_of.get(u.uid, set()):
                tr_total += 1
                # backfield = in AM's deploy half (y small on these maps) AND on/near a home objective
                on_marker = any(((u.position[0]-o.x)**2+(u.position[1]-o.y)**2)**0.5 <= o.control_radius for o in objs)
                if u.position[1] < 18 and on_marker:  # AM deploys low-y; home-ish marker
                    tr_backfield_hold += 1
        # cover at end for AM shooting units
        for u in a.units:
            if u.current_health > 0 and classify(u.profile) in ("SHOOTY", "HEAVY", "HORDE"):
                cover_end[1] += 1
                if getattr(u, "in_cover", False):
                    cover_end[0] += 1

print(f"# AM advance/cover/transport probe — {len(OPPS)} opponents x {N} seeds")
print(f"\n## ADVANCE RATE by role (advanced / any-move; a SHOOTY/HEAVY gunline advancing = forfeits its shooting)")
for r in ("HORDE", "SHOOTY", "HEAVY", "DUAL", "MELEE", "SUPPORT"):
    if mov[r]:
        print(f"  {r:8} {adv[r]:4}/{mov[r]:<4} moves were Advances = {100*adv[r]/mov[r]:5.1f}%")
tot_a = sum(adv.values()); tot_m = sum(mov.values())
print(f"  ALL AM   {tot_a}/{tot_m} = {100*tot_a/max(tot_m,1):.1f}% of AM moves are Advances")
print(f"\n## TRANSPORTS holding a home/backfield marker: {tr_backfield_hold}/{tr_total} transport-instances")
print(f"\n## COVER at game end (AM shooting bodies in cover): {cover_end[0]}/{cover_end[1]} = {100*cover_end[0]/max(cover_end[1],1):.0f}%")
