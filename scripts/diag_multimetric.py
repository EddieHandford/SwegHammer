"""Wave 138 — multi-metric fidelity instrumentation (the worker's contribution to
the user's multi-metric review; the watchdog leads the analysis + real-data
sourcing). Dumps the full per-faction stat profile so the underlying dynamics can
be compared to real tournament data, not just win rate:

  win% | avg rounds | opp-tabled% | self-tabled% | survivor% | kills inflicted |
  final PRIMARY VP | final SECONDARY VP | per-round PRIMARY-VP curve.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_multimetric
Throwaway diagnostic (not committed / not part of the suite). Honest caveat: only
win rates have a real reference (Warp Friends); the richer metrics are sim-vs-
competitive-EXPECTATION until the user sources VP-split / kill data.
"""
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
import scripts.evaluate_vs_meta as ev

# The calibration factions (real win-rate reference = data/warpfriends_rolling.json).
FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
N = 8    # battles per (faction, opponent) cell
OPP_CAP = 7   # opponents sampled per faction (a rotating window, keeps runtime sane)


class _VPCurve:
    """Subscriber: snapshot each side's PRIMARY / SECONDARY VP at every RoundEnded
    by reading the live battle, so we get the per-round accrual curve (the event
    itself only carries the combined total)."""
    def __init__(self, battle):
        self.battle = battle
        self.rows = []   # (round, a_primary, a_secondary, b_primary, b_secondary)

    def on_event(self, event):
        if type(event).__name__ == "RoundEnded":
            b = self.battle
            self.rows.append((
                getattr(event, "round_num", len(self.rows) + 1),
                b._a_vp - b._a_secondary_vp, b._a_secondary_vp,
                b._b_vp - b._b_secondary_vp, b._b_secondary_vp,
            ))


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def profile_faction(fac):
    _others = [f for f in FACTIONS if f != fac]
    _start = FACTIONS.index(fac)   # rotate the window so coverage varies by faction
    opponents = [_others[(_start + j) % len(_others)] for j in range(OPP_CAP)]
    win = rounds = opp_tab = self_tab = 0
    used = 0
    surv, kills, prim, sec = [], [], [], []
    curve_primary = {}   # round -> list of own primary VP totals
    for i, opp in enumerate(opponents):
        for k in range(N):
            s = 4000 + i * 101 + k * 7
            a = build_faction_random_army("A", fac, 2000,
                                          rng=random.Random(s), use_archetype=True)
            b = build_faction_random_army("B", opp, 2000,
                                          rng=random.Random(s + 50000), use_archetype=True)
            if not a.units or not b.units:
                continue
            used += 1
            battle = Battle(a, b, map_=ev._pick_rotation_map(s))
            curve = _VPCurve(battle)
            battle.subscribers.append(curve)
            r = battle.run()
            if r.winner == "A":
                win += 1
            rounds += r.rounds
            if r.b_survivors == 0:
                opp_tab += 1
            if r.a_survivors == 0:
                self_tab += 1
            surv.append(100.0 * r.a_survivors / max(1, r.a_start))
            kills.append(r.b_start - r.b_survivors)
            prim.append(battle._a_vp - battle._a_secondary_vp)
            sec.append(battle._a_secondary_vp)
            for (rnd, ap, _asec, _bp, _bsec) in curve.rows:
                curve_primary.setdefault(rnd, []).append(ap)
    pc = " ".join(f"{mean(curve_primary.get(r, [])):.0f}" for r in range(1, 6))
    return (fac, 100.0 * win / max(1, used), mean([rounds / max(1, used)]),
            100.0 * opp_tab / max(1, used), 100.0 * self_tab / max(1, used),
            mean(surv), mean(kills), mean(prim), mean(sec), pc, used)


hdr = (f"{'faction':20} {'win%':>5} {'rds':>4} {'oppTab%':>7} {'selfTab%':>8} "
       f"{'surv%':>6} {'kills':>6} {'priVP':>6} {'secVP':>6}  {'primary-by-round':>16}")
print("Multi-metric per-faction profile — " + str(N) + " battles per opponent\n")
print(hdr)
print("-" * len(hdr))
for fac in FACTIONS:
    (f, w, rds, ot, st, sv, kl, pr, sc, pc, used) = profile_faction(fac)
    print(f"{f:20} {w:>5.0f} {rds:>4.1f} {ot:>7.0f} {st:>8.0f} {sv:>6.0f} "
          f"{kl:>6.1f} {pr:>6.1f} {sc:>6.1f}  {pc:>16}")
