"""Base-overlap audit: is the rendered unit stacking real sim state or a replay artifact?

Issue #52 verification pass. The user's replay screenshot (Adeptus Custodes vs
Astra Militarum, round 5) shows clustered, apparently overlapping bases. Two
distinct failure modes could produce that picture:

  (1) REAL stacking — a placement path bypasses the SWEG_COLLISION no-overlap
      predicate (`Battle._collision_kwargs` -> `_collision_pos_legal`), so the
      live sim positions genuinely interpenetrate.
  (2) REPLAY artifact — sim positions are legal, but the event stream the
      renderer replays misses some position changes (e.g. silent pile-in /
      consolidate), so the *reconstructed* positions drift and only the
      drawing overlaps.

This audit measures both, using the SAME radius the sim's collision predicate
enforces (`code.sim.geometry._bc_model_radius_in`):

  * GROUND TRUTH: a subscriber checks the LIVE army positions pairwise at
    BattleStarted and every RoundEnded — overlap incidents here are mode (1).
  * DRIFT: the same subscriber maintains renderer-style reconstructed
    positions from the event stream and reports units whose live position has
    drifted from the reconstruction — drift incidents are mode (2).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_overlap_audit
Optional argv: <A_FACTION> <B_FACTION> <SEED...>  (defaults: the screenshot
matchup, seeds 3 4 5).
"""
from __future__ import annotations

import math
import random
import sys
from collections import Counter

from code.army_builder import build_faction_random_army
from code.events import (
    BattleStarted, EventLog, RoundEnded, UnitDeepStrike, UnitInfiltrated,
    UnitMoved, UnitReanimated, UnitScouted,
)
from code.sim.geometry import _bc_model_radius_in
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

TOL_IN = 0.05          # measurement tolerance: penetration below this is "touching"
DRIFT_TOL_IN = 0.05    # live-vs-reconstructed position mismatch threshold


class OverlapAuditor:
    """Event subscriber that audits LIVE sim positions at round boundaries."""

    def __init__(self, army_a, army_b):
        self.armies = (army_a, army_b)
        self.incidents = []      # (round, name1, name2, depth_in, cross_army)
        self.drift = []          # (round, name, drift_in)
        self.recon = {}          # uid -> reconstructed (x, y), renderer-style
        self.round = 0

    # -- renderer-style position reconstruction (mirror of reconstruct_state) --
    def _apply(self, ev):
        if isinstance(ev, BattleStarted):
            for u in ev.units:
                self.recon[u.uid] = u.position
        elif isinstance(ev, (UnitMoved, UnitScouted)):
            self.recon[ev.unit_uid] = ev.to_pos
        elif isinstance(ev, (UnitDeepStrike, UnitInfiltrated, UnitReanimated)):
            self.recon[ev.unit_uid] = ev.position

    def _audit(self, label):
        alive = [u for army in self.armies for u in army.alive_units]
        for i, u in enumerate(alive):
            ru = _bc_model_radius_in(u.profile)
            ux, uy = u.position
            for v in alive[i + 1:]:
                rv = _bc_model_radius_in(v.profile)
                vx, vy = v.position
                pen = (ru + rv) - math.hypot(ux - vx, uy - vy)
                if pen > TOL_IN:
                    cross = u.army_ref is not v.army_ref
                    self.incidents.append(
                        (label, u.profile.name, v.profile.name, pen, cross))
        for army in self.armies:
            for u in army.alive_units:
                rp = self.recon.get(u.uid)
                if rp is None:
                    continue
                d = math.hypot(u.position[0] - rp[0], u.position[1] - rp[1])
                if d > DRIFT_TOL_IN:
                    self.drift.append((label, u.profile.name, d))

    def on_event(self, ev):
        self._apply(ev)
        if isinstance(ev, BattleStarted):
            self._audit("deploy")
        elif isinstance(ev, RoundEnded):
            self._audit(f"r{ev.round_num}")


def run_one(a_fac: str, b_fac: str, seed: int) -> None:
    a = build_faction_random_army("A", a_fac, 2000,
                                  rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000,
                                  rng=random.Random(seed + 10000), use_archetype=True)
    auditor = OverlapAuditor(a, b)
    log = EventLog()
    Battle(a, b, subscribers=[log, auditor], map_=_pick_rotation_map(seed)).run()

    by_round = Counter(lbl for lbl, *_ in auditor.incidents)
    cross = sum(1 for *_x, c in auditor.incidents if c)
    same = len(auditor.incidents) - cross
    print(f"\n=== seed {seed}: {a_fac} vs {b_fac} ===")
    print(f"LIVE overlap incidents: {len(auditor.incidents)} "
          f"(same-army {same} / cross-army {cross})  by tick: {dict(by_round)}")
    worst = sorted(auditor.incidents, key=lambda t: -t[3])[:10]
    for lbl, n1, n2, pen, c in worst:
        kind = "CROSS" if c else "same "
        print(f"  {lbl:>7} {kind} {pen:5.2f}\" deep: {n1} <> {n2}")
    drift_by = Counter(lbl for lbl, *_ in auditor.drift)
    print(f"RECON drift (live vs event-replayed position > {DRIFT_TOL_IN}\"): "
          f"{len(auditor.drift)} units  by tick: {dict(drift_by)}")
    for lbl, name, d in sorted(auditor.drift, key=lambda t: -t[2])[:5]:
        print(f"  {lbl:>7} {d:5.2f}\" drift: {name}")


def main() -> None:
    a_fac = sys.argv[1] if len(sys.argv) > 1 else "Adeptus Custodes"
    b_fac = sys.argv[2] if len(sys.argv) > 2 else "Astra Militarum"
    seeds = [int(s) for s in sys.argv[3:]] or [3, 4, 5]
    for seed in seeds:
        run_one(a_fac, b_fac, seed)


if __name__ == "__main__":
    main()
