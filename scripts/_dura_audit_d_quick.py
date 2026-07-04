import os, sys
os.environ.setdefault("PYTHONHASHSEED", "0")
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
import scripts._dura_audit_d_winshape as W

games = W.load_dg_games("data/_anchor_sc50a_n80_log.json")
# stratified: first 15 seeds per opponent
from collections import defaultdict
byopp = defaultdict(list)
for a,b,s,w in games:
    o = b if a=="Death Guard" else a
    if len(byopp[o]) < 15:
        byopp[o].append((a,b,s,w))
subset = [g for lst in byopp.values() for g in lst]
print("subset games:", len(subset))
sums=[]; matched=0
for a,b,s,w in subset:
    res,log,aa,bb,battle = W.replay_one(a,b,s)
    sm = W.summarise(a,b,s,w,res,log,battle)
    if sm is None: continue
    if sm["match"]: matched+=1
    sums.append(sm)
wins=[x for x in sums if x["dg_win"]]
losses=[x for x in sums if not x["dg_win"] and x["rep"] is not None]
def avg(l,k): return sum(x[k] for x in l)/len(l) if l else 0
print(f"repro {matched}/{len(sums)}")
print(f"DG {len(wins)}W/{len(losses)}L = {100*len(wins)/(len(wins)+len(losses)):.1f}%")
allp = wins+losses
print("ALL games (n=%d):" % len(allp))
print(f"  primary   DG {avg(allp,'dg_primary'):.1f} vs opp {avg(allp,'opp_primary'):.1f}  margin {avg(allp,'dg_primary')-avg(allp,'opp_primary'):+.2f}")
print(f"  secondary DG {avg(allp,'dg_sec'):.1f} vs opp {avg(allp,'opp_sec'):.1f}  margin {avg(allp,'dg_sec')-avg(allp,'opp_sec'):+.2f}")
print(f"  capped    DG {avg(allp,'dg_capped'):.1f} vs opp {avg(allp,'opp_capped'):.1f}  margin {avg(allp,'dg_capped')-avg(allp,'opp_capped'):+.2f}")
print(f"  DG survival {100*avg(allp,'dg_surv')/avg(allp,'dg_start'):.1f}%  opp survival {100*avg(allp,'opp_surv')/avg(allp,'opp_start'):.1f}%")
print("WINS (n=%d):" % len(wins))
print(f"  primary margin {avg(wins,'dg_primary')-avg(wins,'opp_primary'):+.2f}  secondary margin {avg(wins,'dg_sec')-avg(wins,'opp_sec'):+.2f}")
print(f"  DG survivors {avg(wins,'dg_surv'):.1f}/{avg(wins,'dg_start'):.1f} ({100*avg(wins,'dg_surv')/avg(wins,'dg_start'):.0f}%)  opp survivors {avg(wins,'opp_surv'):.1f}/{avg(wins,'opp_start'):.1f} ({100*avg(wins,'opp_surv')/avg(wins,'opp_start'):.0f}%)")
print("LOSSES (n=%d):" % len(losses))
print(f"  DG survivors {100*avg(losses,'dg_surv')/avg(losses,'dg_start'):.0f}%  opp survivors {100*avg(losses,'opp_surv')/avg(losses,'opp_start'):.0f}%")
# per-class detail
print("\nDETAIL by opponent class:")
for o in ["Aeldari","Orks","Astra Militarum","Adeptus Custodes","Imperial Knights","T'au Empire"]:
    gl = [x for x in sums if x["opp"]==o][:2]
    for sm in gl:
        print(f"  vs {o} s={sm['s']} r{sm['rounds']} {'WIN' if sm['dg_win'] else 'LOSS'}: cap DG{sm['dg_capped']}-{sm['opp_capped']} | prim {sm['dg_primary']:.0f}-{sm['opp_primary']:.0f} sec {sm['dg_sec']:.0f}-{sm['opp_sec']:.0f} | surv DG{sm['dg_surv']}/{sm['dg_start']} opp{sm['opp_surv']}/{sm['opp_start']}")
