"""AM screen: OFF vs attach+count vs FULL (hosted+attach+count). N=30."""
import os, random
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission
def winner(over, seed):
    random.seed(seed)
    a=build_faction_random_army("A","Astra Militarum",2000,rng=random.Random(seed),use_archetype=True)
    b=build_faction_random_army("B",over,2000,rng=random.Random(seed+10000),use_archetype=True)
    return Battle(a,b,map_=_pick_rotation_map(seed),primary_mission=_pick_primary_mission(seed)).run().winner
def setg(hosted,attach,count):
    for k,v in [("SWEG_LEADER_HOSTED",hosted),("SWEG_LEADER_ATTACH",attach),("SWEG_SECONDARY_PER_UNIT",count)]:
        os.environ[k]="1" if v else "0"
N=20; seeds=list(range(N))
def rate(over,h,a,c):
    setg(h,a,c); return 100*sum(1 for s in seeds if winner(over,s)=="A")/N
OPPS=["Adeptus Astartes","Chaos Knights","Adepta Sororitas","Imperial Knights",
      "Death Guard","World Eaters"]
print(f"# AM full-stack screen  N={N}")
print(f"{'matchup':18} {'OFF':>5} {'atk+cnt':>8} {'FULL':>6}  {'FULLd':>6}")
to=ta=tf=0
for over in OPPS:
    o=rate(over,0,0,0); ac=rate(over,0,1,1); f=rate(over,1,1,1)
    to+=o; ta+=ac; tf+=f
    print(f"{over:18} {o:5.1f} {ac:8.1f} {f:6.1f}  {f-o:+6.1f}")
n=len(OPPS)
print(f"{'MEAN':18} {to/n:5.1f} {ta/n:8.1f} {tf/n:6.1f}  {(tf-to)/n:+6.1f}")
setg(0,0,0)
