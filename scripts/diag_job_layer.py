"""Mechanism instruments for SWEG_JOB_LAYER — the job/commitment layer (v1).

READ-ONLY. Runs a fixed bundle of fixed-seed battles and reports the two
mechanism instruments the build brief pre-registers:

  1. PER-FACTION JOB DISTRIBUTION (gate ON): the fraction of each faction's move
     decisions that resolved to HOLD / KILL / SURVIVE. Read from the read-only
     strategy._JOB_DIAG counter (populated when SWEG_JOB_LAYER_DIAG=1 — pure
     measurement, no events, no random draws, so it never perturbs the digest).
     EXPECTATION: Astra Militarum SPLITS (cheap infantry hold, tanks/artillery
     kill) while Imperial Knights skew heavily KILL.

  2. PILE-ON RATE, gate OFF vs ON: the fraction of controlled objective markers
     that carry a REDUNDANT holder — a marker the army still controls after
     removing its smallest on-marker holder. The army-level assignment pass
     (strategy.assign_jobs) stops committing holders once a marker's objective
     control suffices, so this rate must FALL from OFF to ON. Measured on the
     live board at every turn boundary (the just-finished army), effective-OC
     aware to match the scorer.

The walked-into-it instrument is the existing scripts/diag_walked_into_it.py —
run that OFF vs ON separately (it is a build-time report number, not a gate).

Determinism: PYTHONHASHSEED must be 0 (re-exec below, mirroring
scripts/sim_motion_proof.py). Env gates are set on os.environ before each arm's
battles run and read at call time by the strategy layer, so OFF and ON share one
process on identical seeds (a paired comparison).

USAGE
    PYTHONHASHSEED=0 python scripts/diag_job_layer.py
"""
from __future__ import annotations

import os
import random
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(
        sys.executable,
        [sys.executable, "scripts/diag_job_layer.py"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army           # noqa: E402
from code.maps import PARIAH_NEXUS_2K_ROTATION, STOCK_MAPS         # noqa: E402
from code.simulator import Battle                                  # noqa: E402
import code.strategy as strategy                                   # noqa: E402
from code.strategy import (                                        # noqa: E402
    _JOB_HOLD, _JOB_KILL, _JOB_SURVIVE,
    _effective_oc_on_objective, _effective_oc_value,
)

# Six fixed pairings. Astra Militarum appears twice (must split) and Imperial
# Knights twice (must skew KILL); the rest exercise a horde, a psyker line, a
# kill-tempo brawler and a shooty elite so the distribution table is broad.
BATTLES = (
    ("Astra Militarum", "Orks", 1),
    ("Imperial Knights", "Necrons", 2),
    ("Astra Militarum", "Adeptus Astartes", 3),
    ("Imperial Knights", "Tyranids", 4),
    ("World Eaters", "T'au Empire", 5),
    ("Chaos Daemons", "Drukhari", 6),
)
POINTS = 2000


def _build(a_fac, b_fac, seed):
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, POINTS, rng=random.Random(seed),
                                  use_archetype=True)
    b = build_faction_random_army("B", b_fac, POINTS, rng=random.Random(seed + 10000),
                                  use_archetype=True)
    map_ = STOCK_MAPS[PARIAH_NEXUS_2K_ROTATION[seed % len(PARIAH_NEXUS_2K_ROTATION)]]
    return a, b, map_


class PileOnObserver:
    """Counts, at each turn boundary, redundant-holder markers for the army that
    just finished its turn. A marker is 'piled on' when the army controls it with
    at least two on-marker holders and still controls it after dropping the
    smallest — an over-commitment the assignment pass exists to remove."""

    def __init__(self, battle):
        self.battle = battle
        self.current_army = None
        self.piled = 0
        self.controlled = 0

    def on_event(self, ev):
        if type(ev).__name__ != "UnitActivated":
            return
        army = ev.army_name
        if self.current_army is not None and army != self.current_army:
            self._measure(self.current_army)
        self.current_army = army

    def _measure(self, prev_name):
        active = self.battle.a if self.battle.a.name == prev_name else self.battle.b
        enemy = self.battle.b if active is self.battle.a else self.battle.a
        e_alive = enemy.alive_units
        for obj in self.battle.map.objectives:
            r2 = obj.control_radius * obj.control_radius
            holders = [
                _effective_oc_value(u) for u in active.alive_units
                if (u.position[0] - obj.x) ** 2 + (u.position[1] - obj.y) ** 2 <= r2
                and _effective_oc_value(u) > 0
            ]
            our = sum(holders)
            their = _effective_oc_on_objective(e_alive, obj)
            if our <= their:
                continue                       # not controlled — not our marker
            self.controlled += 1
            if len(holders) >= 2 and our - min(holders) > their:
                self.piled += 1


def run_distribution():
    os.environ["SWEG_JOB_LAYER"] = "1"
    os.environ["SWEG_JOB_LAYER_DIAG"] = "1"
    strategy.reset_job_diag()
    for a_fac, b_fac, seed in BATTLES:
        a, b, map_ = _build(a_fac, b_fac, seed)
        Battle(a, b, map_=map_).run()
    snapshot = {f: dict(c) for f, c in strategy._JOB_DIAG.items()}
    del os.environ["SWEG_JOB_LAYER_DIAG"]
    del os.environ["SWEG_JOB_LAYER"]
    return snapshot


def run_pileon(gate_on):
    if gate_on:
        os.environ["SWEG_JOB_LAYER"] = "1"
    else:
        os.environ.pop("SWEG_JOB_LAYER", None)
    piled = controlled = 0
    for a_fac, b_fac, seed in BATTLES:
        a, b, map_ = _build(a_fac, b_fac, seed)
        battle = Battle(a, b, map_=map_)
        obs = PileOnObserver(battle)
        battle.subscribers.append(obs)
        battle.run()
        piled += obs.piled
        controlled += obs.controlled
    os.environ.pop("SWEG_JOB_LAYER", None)
    return piled, controlled


def main():
    print(f"job-layer mechanism instruments — {len(BATTLES)} fixed-seed battles, "
          f"{POINTS} points, use_archetype=True\n")

    dist = run_distribution()
    print("1) PER-FACTION JOB DISTRIBUTION (gate ON, fractions of move decisions)")
    hdr = f"  {'faction':18s} {'decisions':>9s} {'HOLD':>7s} {'KILL':>7s} {'SURVIVE':>8s}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for fac in sorted(dist):
        c = dist[fac]
        n = c[_JOB_HOLD] + c[_JOB_KILL] + c[_JOB_SURVIVE]
        if n == 0:
            continue
        print(f"  {fac:18s} {n:9d} {c[_JOB_HOLD]/n:7.3f} "
              f"{c[_JOB_KILL]/n:7.3f} {c[_JOB_SURVIVE]/n:8.3f}")

    print("\n2) PILE-ON RATE (redundant-holder markers / controlled markers)")
    off_p, off_c = run_pileon(gate_on=False)
    on_p, on_c = run_pileon(gate_on=True)
    off_r = off_p / max(1, off_c)
    on_r = on_p / max(1, on_c)
    print(f"  gate OFF : {off_p:5d} / {off_c:5d}  = {off_r:.4f}")
    print(f"  gate ON  : {on_p:5d} / {on_c:5d}  = {on_r:.4f}")
    print(f"  delta    : {on_r - off_r:+.4f}   (must be negative — pile-on falls)")


if __name__ == "__main__":
    main()
