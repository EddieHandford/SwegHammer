"""Paired screen: the two faithful fixes (attachment + per-unit assassination
counting) vs the current behaviour, AM as army A across its spread. N=40."""
import os, random
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission
def winner(over, seed):
    random.seed(seed)
    a=build_faction_random_army("A","Astra Militarum",2000,rng=random.Random(seed),use_archetype=True)
    b=build_faction_random_army("B",over,2000,rng=random.Random(seed+10000),use_archetype=True)
    return Battle(a,b,map_=_pick_rotation_map(seed),primary_mission=_pick_primary_mission(seed)).run().winner
N=40; seeds=list(range(N))
OPPS=["Adeptus Astartes","Imperial Knights","Genestealer Cults","Adepta Sororitas",
      "Chaos Knights","Death Guard","World Eaters","Adeptus Custodes","T'au Empire","Necrons"]
print(f"# AM attachment+per-unit-counting screen  N={N}  (paired off vs on)")
print(f"{'matchup':20} {'OFF%':>6} {'ON%':>6} {'dpp':>6} {'L>W':>4} {'W>L':>4}")
tot_off=tot_on=0
for over in OPPS:
    os.environ["SWEG_LEADER_ATTACH"]="0"; os.environ["SWEG_SECONDARY_PER_UNIT"]="0"
    off={s:winner(over,s) for s in seeds}
    os.environ["SWEG_LEADER_ATTACH"]="1"; os.environ["SWEG_SECONDARY_PER_UNIT"]="1"
    on ={s:winner(over,s) for s in seeds}
    ow=sum(1 for s in seeds if off[s]=="A"); nw=sum(1 for s in seeds if on[s]=="A")
    lw=sum(1 for s in seeds if off[s]!="A" and on[s]=="A"); wl=sum(1 for s in seeds if off[s]=="A" and on[s]!="A")
    tot_off+=ow; tot_on+=nw
    print(f"{over:20} {100*ow/N:6.1f} {100*nw/N:6.1f} {100*(nw-ow)/N:+6.1f} {lw:4d} {wl:4d}")
n=len(OPPS)*N
print(f"{'AM MEAN':20} {100*tot_off/n:6.1f} {100*tot_on/n:6.1f} {100*(tot_on-tot_off)/n:+6.1f}")
os.environ["SWEG_LEADER_ATTACH"]="0"; os.environ["SWEG_SECONDARY_PER_UNIT"]="0"
