"""List-realism audit: for each faction, does the archetype builder REALIZE the
seeded (cited real) list, or does the seed_fraction/random_fill DROP the expensive
core + over-fill cheap units (the AdMech Onager distortion)? Read-only."""
import random
from collections import defaultdict
from code.archetypes import ARCHETYPES, SEED_FRACTION, SEED_FRACTION_BY_FACTION
from code.units import UNIT_CATALOG
import code.army_builder as ab

def pts(p):
    for a in ("cost","points","points_cost"):
        v = getattr(p, a, None)
        if isinstance(v,(int,float)): return v
    return 0.0
def mc(u):  # model count of a built unit
    return getattr(u,"start_count",None) or getattr(u,"models",None) or 1

N = 12
print(f"{'Faction':22} {'sf':>4} {'pts':>5} {'mdl':>4} {'unit':>4}  dropped-expensive-seeded(>=150pt, realized<0.6x seed)")
print("-"*120)
for fac, dets in ARCHETYPES.items():
    seed = defaultdict(int)
    for det in dets.values():
        for k,c in det.items(): seed[k]=max(seed[k],c)
    sf = SEED_FRACTION_BY_FACTION.get(fac, SEED_FRACTION)
    tot_pts=tot_mdl=tot_units=0
    name_counts = defaultdict(list)  # profile name -> per-build count
    for s in range(N):
        try:
            army = ab.build_faction_random_army("A",fac,2000,rng=random.Random(1000+s),use_archetype=True)
        except Exception as e:
            print(f"{fac:22} BUILD-ERR {e}"); break
        per = defaultdict(int)
        for u in army.units:
            per[u.profile.name]+=1; tot_mdl+=mc(u)
        for nm,c in per.items(): name_counts[nm].append(c)
        tot_pts += sum(pts(u.profile) for u in army.units)
        tot_units += len(army.units)
    drops=[]
    for k,sc in seed.items():
        cat = UNIT_CATALOG.get(k)
        if not cat: continue
        p = pts(cat)
        if p < 150: continue
        rc = name_counts.get(cat.name, [])
        avg = sum(rc)/N if rc else 0.0
        if avg < 0.6*sc:
            drops.append(f"{cat.name}({int(p)}pt {avg:.1f}/{sc})")
    print(f"{fac:22} {sf:>4} {tot_pts/N:5.0f} {tot_mdl/N:4.0f} {tot_units/N:4.1f}  {'; '.join(drops) if drops else 'OK'}")
