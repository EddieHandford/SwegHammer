"""Does fixing the host-squad under-fielding unlock the attachment protection?
A/B the SAME list off vs on (so 'more army' cancels in the delta), on the
default under-hosted list vs a properly-hosted list (host squads added so
leaders pair 1-2 per squad, respecting _MAX_LEADERS_PER_SQUAD=2)."""
import os, random
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission

HOSTS = {"Cadian Shock Troops","Kasrkin","Death Korps of Krieg",
         "Tempestus Scions","Catachan Jungle Fighters"}
_ST = UNIT_CATALOG["astra_militarum_cadian_shock_troops"]

def host_am(a):
    cunits=set(); hsq=set()
    for u in a.units:
        kw=set(u.profile.unit_keywords or ())
        if "CHARACTER" in kw and not ({"VEHICLE","MONSTER"} & kw):
            sid=getattr(u,"squad_id",-1); cunits.add(sid if sid>=0 else ("l",id(u)))
        if u.profile.name in HOSTS:
            sid=getattr(u,"squad_id",-1)
            if sid>=0: hsq.add(sid)
    need=(len(cunits)+1)//2          # ceil(leaders/2), cap 2 per squad
    for _ in range(max(0, need-len(hsq))):
        a.add_squad(_ST, size=10)

def winner(over, seed, hosted):
    random.seed(seed)
    a=build_faction_random_army("A","Astra Militarum",2000,rng=random.Random(seed),use_archetype=True)
    if hosted: host_am(a)
    b=build_faction_random_army("B",over,2000,rng=random.Random(seed+10000),use_archetype=True)
    return Battle(a,b,map_=_pick_rotation_map(seed),primary_mission=_pick_primary_mission(seed)).run().winner

def main():
    N=30; seeds=list(range(N))
    def rate(over, hosted, on):
        os.environ["SWEG_LEADER_ATTACH"]="1" if on else "0"
        os.environ["SWEG_SECONDARY_PER_UNIT"]="1" if on else "0"
        return 100*sum(1 for s in seeds if winner(over,s,hosted)=="A")/N
    print(f"# hosted-list attachment test  N={N}")
    print(f"{'matchup':18} | {'DEFAULT off':>11} {'on':>5} {'d':>5} | {'HOSTED off':>10} {'on':>5} {'d':>5}")
    for over in ["Adeptus Astartes","Chaos Knights","World Eaters"]:
        doff=rate(over,False,False); don=rate(over,False,True)
        hoff=rate(over,True,False);  hon=rate(over,True,True)
        print(f"{over:18} | {doff:11.1f} {don:5.1f} {don-doff:+5.1f} | {hoff:10.1f} {hon:5.1f} {hon-hoff:+5.1f}")
    os.environ["SWEG_LEADER_ATTACH"]="0"; os.environ["SWEG_SECONDARY_PER_UNIT"]="0"

if __name__ == "__main__":
    main()
