"""Wave 109 diagnostic (user sim-fidelity ruling): WHY does the sim's Imperial
Knights win the +27? Separate the win mechanism — tabling (combat) vs out-scoring
PRIMARY victory points (positioning) vs the opponent failing the SECONDARY game.
Throwaway; not committed."""
import random
import statistics

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import scripts.evaluate_vs_meta as ev

IK = "Imperial Knights"
OPPONENTS = [
    "Tyranids", "Astra Militarum", "Necrons", "Orks",
    "Chaos Daemons", "Adeptus Mechanicus", "Genestealer Cults",
]
N = 25


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


print(f"IK vs broad armies — {N} battles each (archetype lists)\n")
hdr = (f"{'opponent':20} {'IKwin':>6} {'IKtab':>6} {'opptab':>7} "
       f"{'IKpri':>6} {'IKsec':>6} {'OPpri':>6} {'OPsec':>6} {'OPsurv%':>8} {'rds':>4}")
print(hdr)
print("-" * len(hdr))
for opp in OPPONENTS:
    ik_win = ik_tab = opp_tab = 0
    ik_pri, ik_sec, op_pri, op_sec, op_surv, rds = [], [], [], [], [], []
    used = 0
    for i in range(N):
        s = 1000 + i * 7
        a = build_faction_random_army("A", IK, 2000, rng=random.Random(s),
                                       use_archetype=True)
        b = build_faction_random_army("B", opp, 2000, rng=random.Random(s + 10000),
                                      use_archetype=True)
        if not a.units or not b.units:
            continue
        used += 1
        battle = Battle(a, b, map_=ev._pick_rotation_map(s))
        r = battle.run()
        ik_pri.append(battle._a_vp - battle._a_secondary_vp)
        ik_sec.append(battle._a_secondary_vp)
        op_pri.append(battle._b_vp - battle._b_secondary_vp)
        op_sec.append(battle._b_secondary_vp)
        if r.winner == "A":
            ik_win += 1
        if r.b_survivors == 0:
            ik_tab += 1
        if r.a_survivors == 0:
            opp_tab += 1
        op_surv.append(100.0 * r.b_survivors / max(1, r.b_start))
        rds.append(r.rounds)
    print(f"{opp:20} {ik_win:>5}/{used:<0} {ik_tab:>6} {opp_tab:>7} "
          f"{mean(ik_pri):>6.1f} {mean(ik_sec):>6.1f} {mean(op_pri):>6.1f} "
          f"{mean(op_sec):>6.1f} {mean(op_surv):>7.0f}% {mean(rds):>4.1f}")
