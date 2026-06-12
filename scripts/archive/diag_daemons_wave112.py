"""Wave 112 diagnostic (watchdog steer): WHY do Chaos Daemons under-shoot
(-14.7 default)? Mirror the wave-109 IK probe — separate the loss mechanism:
tabling/combat vs PRIMARY victory points vs SECONDARY vs dying before arriving.
Daemons are side A (the faction under test). Throwaway; not committed."""
import random
import statistics

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import scripts.evaluate_vs_meta as ev

DAEMONS = "Chaos Daemons"
# A spread of opponents: shooty/durable armies that should be shooting Daemons
# off the board, plus the Knight (the over-shooter) for contrast.
OPPONENTS = [
    "Adeptus Astartes", "T'au Empire", "Astra Militarum", "Necrons",
    "Adeptus Custodes", "Imperial Knights", "Aeldari", "Tyranids",
]
N = 25


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


print(f"Chaos Daemons (side A) vs a spread — {N} battles each (archetype lists)\n")
hdr = (f"{'opponent':20} {'Dwin':>6} {'Dtab':>6} {'opptab':>7} "
       f"{'Dpri':>6} {'Dsec':>6} {'OPpri':>6} {'OPsec':>6} {'Dsurv%':>7} {'rds':>4}")
print(hdr)
print("-" * len(hdr))
agg = {"Dwin": 0, "tot": 0, "Dtab": 0, "opptab": 0}
for opp in OPPONENTS:
    d_win = d_tab = opp_tab = 0
    d_pri, d_sec, o_pri, o_sec, d_surv, rds = [], [], [], [], [], []
    used = 0
    for i in range(N):
        s = 4000 + i * 7
        a = build_faction_random_army("A", DAEMONS, 2000, rng=random.Random(s),
                                      use_archetype=True)
        b = build_faction_random_army("B", opp, 2000, rng=random.Random(s + 10000),
                                      use_archetype=True)
        if not a.units or not b.units:
            continue
        used += 1
        battle = Battle(a, b, map_=ev._pick_rotation_map(s))
        r = battle.run()
        d_pri.append(battle._a_vp - battle._a_secondary_vp)
        d_sec.append(battle._a_secondary_vp)
        o_pri.append(battle._b_vp - battle._b_secondary_vp)
        o_sec.append(battle._b_secondary_vp)
        if r.winner == "A":
            d_win += 1
        if r.a_survivors == 0:
            d_tab += 1       # Daemons tabled
        if r.b_survivors == 0:
            opp_tab += 1     # Daemons tabled the opponent
        d_surv.append(100.0 * r.a_survivors / max(1, r.a_start))
        rds.append(r.rounds)
    agg["Dwin"] += d_win; agg["tot"] += used
    agg["Dtab"] += d_tab; agg["opptab"] += opp_tab
    print(f"{opp:20} {d_win:>5}/{used:<0} {d_tab:>6} {opp_tab:>7} "
          f"{mean(d_pri):>6.1f} {mean(d_sec):>6.1f} {mean(o_pri):>6.1f} "
          f"{mean(o_sec):>6.1f} {mean(d_surv):>6.0f}% {mean(rds):>4.1f}")
print("-" * len(hdr))
print(f"TOTAL: Daemons win {agg['Dwin']}/{agg['tot']} "
      f"({100.0*agg['Dwin']/max(1,agg['tot']):.0f}%) | "
      f"Daemons tabled {agg['Dtab']}x | tabled the opponent {agg['opptab']}x")
print("(Dpri/Dsec = Daemons primary/secondary VP; OPpri/OPsec = opponent's; "
      "Dsurv% = Daemon units alive at end as % of start)")
