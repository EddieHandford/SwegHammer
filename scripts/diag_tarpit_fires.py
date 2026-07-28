"""Wave 130 diagnostic (watchdog request): does the Tarpit pin FIRE end-to-end?

The wave-129 A/B showed SWEG_TARPIT does not move the Imperial Knights win rate.
That can mean either (a) the pin fires but the game is decided on board control,
not combat (the convergence finding), or (b) the pin mechanic does not engage
(a bug) so the component is inert despite the valuation.

This distinguishes them with a proxy the sim already exposes: if a tarpit blunts
the Knight's shooting (Big Guns Never Tire: an engaged Knight shoots only its
tarpit at -1, or Falls Back and loses its shooting), the OPPONENT should lose
fewer models -> survive MORE when SWEG_TARPIT is on. We run Imperial Knights vs
melee/chaff-bearing armies (which actually have expendable bodies to throw) with
the gate off then on, and compare opponent survival % and opponent primary VP.

A rise in opponent survival with the gate on = the pin fires (the inertness is
board-control, finding (a)). No change = the pin does not engage (finding (b)).
Throwaway; not part of the suite.
"""
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import scripts.evaluate_vs_meta as ev

IK = "Imperial Knights"
# Melee / chaff-bearing opponents — the armies that CAN tarpit (cheap bodies).
OPPONENTS = ["Orks", "World Eaters", "Chaos Daemons", "Tyranids"]
N = 25


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def run(tarpit_on: bool):
    if tarpit_on:
        os.environ["SWEG_TARPIT"] = "1"
    else:
        os.environ.pop("SWEG_TARPIT", None)
    rows = {}
    for opp in OPPONENTS:
        op_surv, op_pri, ik_win = [], [], 0
        used = 0
        for i in range(N):
            s = 1000 + i * 7
            a = build_faction_random_army("A", IK, 2000, rng=random.Random(s),
                                          use_archetype=True)
            b = build_faction_random_army("B", opp, 2000,
                                          rng=random.Random(s + 10000),
                                          use_archetype=True)
            if not a.units or not b.units:
                continue
            used += 1
            battle = Battle(a, b, map_=ev._pick_rotation_map(s))
            r = battle.run()
            op_surv.append(100.0 * r.b_survivors / max(1, r.b_start))
            op_pri.append(battle._b_vp - battle._b_secondary_vp)
            if r.winner == "A":
                ik_win += 1
        rows[opp] = (ik_win, used, mean(op_surv), mean(op_pri))
    return rows


print(f"Tarpit pin-fires diagnostic — IK vs melee armies, {N} battles each\n")
off = run(False)
on = run(True)
hdr = f"{'opponent':14} {'IKwin off/on':>13} {'OPsurv% off->on':>18} {'OPprimary off->on':>20}"
print(hdr)
print("-" * len(hdr))
for opp in OPPONENTS:
    wo, uo, so, po = off[opp]
    wn, un, sn, pn = on[opp]
    print(f"{opp:14} {wo:>5}/{wn:<7} {so:>8.0f}% ->{sn:>5.0f}%      "
          f"{po:>8.1f} ->{pn:>7.1f}")
print("\nIf OPsurv% / OPprimary RISE with tarpit on, the pin fires end-to-end "
      "(inertness is board-control, not a bug).")
