"""Fire-allocation concentration instrument — instrument-before-build for the
allocation-aware threat field (docs/DECISION_LEDGER.md "ALLOCATION-AWARE THREAT
FIELD" registration).

READ-ONLY. The summed threat field counts every enemy's full output against
every cell; the owner's design rule is that an enemy with ONE eligible target
sends everything at it while an enemy with several splits the RISK across
them. The registered v1 weights are attractiveness-proportional (expected-
wounds-proportional). This instrument measures how the sim's REALIZED fire
actually distributes, so the weight form is validated (or refuted) against
measurement instead of assumption:

  * For each shooting activation (grouped by attacker across consecutive
    UnitShot events — split fire emits several events for one shooter), count
    how many enemy targets were ELIGIBLE at the moment of the first shot —
    recomputed live from positions: within the shooter's weapon range (the
    larger of the model's own profile range and the squad-aggregate scoring
    range, since per-model loadouts can narrow the aggregate), UNIONED with
    the targets the activation actually shot (a shot target was eligible by
    the resolution's own reckoning — overwatch-class shots resolve at the
    target's end-of-move cell, which a static range recompute can misjudge).
    The sim's shooting has no true line-of-sight occlusion (see the
    threat-field header in code/strategy.py), so range IS the surface.
  * Targets are aggregated by SQUAD (the sim models a codex squad as one
    Unit per model sharing a squad_id; targeting chooses between squads, so
    the squad is the real allocation grain — model-grain eligibility would
    read a 20-model squad as 20 arbitrary "targets" and dilute the signal).
  * Record how the shooter's realized damage distributed across target
    squads, and take the top-1 share. NOTE the sim's activation grain is one
    MODEL, and a model fires its whole activation at one pick almost always
    — so the per-activation top-1 share is expected to read at or near 1.0
    and the army-level risk split across defenders is carried by WHICH
    target each activation picks. The pick-frequency columns are therefore
    the discriminating measurement:
  * Per activation, the share the attractiveness-proportional weight form
    would PREDICT for the top-1 target (each eligible target's ranged
    expected wounds, same audited per-pair math the threat field uses,
    cover-attenuated at the target's own cell, normalized); whether the
    realized pick WAS the ew-argmax target ("picked ew-top rate"); and the
    ew-share of the actually-chosen target. If picks land on the ew-top
    target at roughly its ew share, ew-proportional allocation is validated;
    if picks are near-always the ew-top target, realized concentration is
    sharper than ew-proportional (winner-take-all by attractiveness).

Buckets: eligible-target count n = 1, 2, 3, 4+ — means per bucket.

Determinism: PYTHONHASHSEED re-exec mirrors scripts/sim_motion_proof.py.
Zero-damage activations (all shots saved) carry no allocation information and
are counted separately. Events are read via the ordinary subscriber stream
(the diag_walked_into_it live-object pattern); no simulator changes.

USAGE
    PYTHONHASHSEED=0 python scripts/diag_fire_allocation.py
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
        [sys.executable, "scripts/diag_fire_allocation.py"] + sys.argv[1:],
        os.environ,
    )

from code.army_builder import build_faction_random_army           # noqa: E402
from code.maps import PARIAH_NEXUS_2K_ROTATION, STOCK_MAPS         # noqa: E402
from code.simulator import Battle                                  # noqa: E402
from code.strategy import _cover_attenuation, _dist, _score_profile  # noqa: E402

# Eight fixed-seed mixed pairs — the five sim_motion_proof pairings plus three
# more so sixteen distinct factions appear. Shared verbatim with
# scripts/diag_threat_calibration.py so the two instruments read one bundle.
BATTLES = (
    ("Adeptus Astartes", "Orks", 1),
    ("Necrons", "Tyranids", 2),
    ("Imperial Knights", "Astra Militarum", 3),
    ("Thousand Sons", "Drukhari", 4),
    ("Adeptus Custodes", "World Eaters", 5),
    ("T'au Empire", "Chaos Daemons", 6),
    ("Death Guard", "Aeldari", 7),
    ("Chaos Knights", "Genestealer Cults", 8),
)
POINTS_BUDGET = 2000


def _bucket(n: int) -> str:
    return str(n) if n <= 3 else "4+"


class FireAllocationObserver:
    """Groups consecutive UnitShot events by attacker and, at each group's
    first shot, snapshots the shooter's live eligibility set (per-enemy
    ew values kept so the pick-frequency columns can be scored when the
    group closes)."""

    def __init__(self, battle: Battle) -> None:
        self.battle = battle
        self._cur_attacker = None
        self._cur_ews = None             # target_uid -> ew (eligibility set)
        self._cur_damage = None          # target_uid -> realized damage
        # bucket -> [count, sum measured top1 share, sum ew-predicted top1
        #            share, sum picked-ew-top indicator, sum ew share of the
        #            chosen target, pick-scored sample count]
        self.buckets = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0, 0])
        self.zero_damage_activations = 0

    # -- live lookups -----------------------------------------------------
    def _unit(self, uid):
        for u in list(self.battle.a.units) + list(self.battle.b.units):
            if u.uid == uid:
                return u
        return None

    def _enemies_of(self, unit):
        army = self.battle.a if unit.uid.startswith("A") else self.battle.b
        other = self.battle.b if army is self.battle.a else self.battle.a
        return other.alive_units

    def _ew(self, sp, target):
        ew = Battle._ranged_expected_wounds(sp, target)
        if ew > 0.0:
            ew *= _cover_attenuation(target, getattr(sp, "ap", 0) or 0,
                                     self.battle.map, target.position)
        return ew

    @staticmethod
    def _squad_key(unit):
        """Aggregation key: the sim models a codex squad as one Unit per
        MODEL sharing a squad_id; targeting chooses between squads, so the
        allocation measurement aggregates members (-1 = lone model)."""
        sid = getattr(unit, "squad_id", -1)
        if sid is None:
            sid = -1
        return (unit.uid[0], sid) if sid >= 0 else ("u", unit.uid)

    def _eligibility(self, shooter):
        """squad_key -> summed ew over the live range-eligible enemy squads.
        Range = max(model profile range, squad-aggregate scoring range):
        per-model loadouts can narrow the aggregate below a model's real
        weapon."""
        sp = _score_profile(shooter)
        rng = max(float(getattr(sp, "range_inches", 0.0) or 0.0),
                  float(getattr(shooter.profile, "range_inches", 0.0) or 0.0))
        ews = defaultdict(float)
        if rng <= 0.0:
            return ews
        for e in self._enemies_of(shooter):
            if _dist(shooter.position, e.position) <= rng:
                ews[self._squad_key(e)] += self._ew(sp, e)
        return ews

    # -- event stream ------------------------------------------------------
    def on_event(self, ev) -> None:
        name = type(ev).__name__
        if name == "UnitShot":
            if ev.attacker_uid != self._cur_attacker:
                self._close_group()
                self._cur_attacker = ev.attacker_uid
                shooter = self._unit(ev.attacker_uid)
                self._cur_shooter = shooter
                self._cur_ews = (self._eligibility(shooter)
                                 if shooter is not None else {})
                self._cur_damage = defaultdict(float)
            # A shot target was eligible by the resolution's own reckoning —
            # union its squad in (overwatch resolves at the target's
            # end-of-move cell, which a static recompute can misjudge).
            t = self._unit(ev.target_uid)
            key = (self._squad_key(t) if t is not None
                   else ("u", ev.target_uid))
            if key not in self._cur_ews:
                if t is not None and self._cur_shooter is not None:
                    self._cur_ews[key] = self._ew(
                        _score_profile(self._cur_shooter), t)
                else:
                    self._cur_ews[key] = 0.0
            self._cur_damage[key] += max(0.0, ev.damage)
        elif name in ("UnitActivated", "BattleEnded"):
            self._close_group()

    def _close_group(self) -> None:
        if self._cur_attacker is None or self._cur_damage is None:
            self._cur_attacker = None
            return
        total = sum(self._cur_damage.values())
        if total <= 0.0:
            self.zero_damage_activations += 1
        elif self._cur_ews:
            n = len(self._cur_ews)
            top1 = max(self._cur_damage.values()) / total
            b = self.buckets[_bucket(n)]
            b[0] += 1
            b[1] += top1
            ew_total = sum(self._cur_ews.values())
            if ew_total > 0.0:
                b[2] += max(self._cur_ews.values()) / ew_total
                chosen = max(self._cur_damage, key=self._cur_damage.get)
                ew_top_uid = max(self._cur_ews, key=self._cur_ews.get)
                b[3] += 1.0 if chosen == ew_top_uid else 0.0
                b[4] += self._cur_ews.get(chosen, 0.0) / ew_total
                b[5] += 1
        self._cur_attacker = None
        self._cur_damage = None


def main() -> int:
    agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0, 0])
    zero = 0
    for (fa, fb, seed) in BATTLES:
        random.seed(seed)
        a = build_faction_random_army("A", fa, POINTS_BUDGET,
                                      rng=random.Random(seed),
                                      use_archetype=True)
        b = build_faction_random_army("B", fb, POINTS_BUDGET,
                                      rng=random.Random(seed + 10000),
                                      use_archetype=True)
        map_key = PARIAH_NEXUS_2K_ROTATION[seed % len(PARIAH_NEXUS_2K_ROTATION)]
        battle = Battle(a, b, map_=STOCK_MAPS[map_key])
        obs = FireAllocationObserver(battle)
        battle.subscribers.append(obs)
        battle.run()
        for k, v in obs.buckets.items():
            for i in range(6):
                agg[k][i] += v[i]
        zero += obs.zero_damage_activations

    print("fire-allocation concentration curve — %d fixed-seed battles, "
          "%d points, use_archetype=True" % (len(BATTLES), POINTS_BUDGET))
    print("(per shooting activation: n = live range-eligible enemy SQUADS at")
    print(" the first shot, unioned with squads actually shot; 'measured")
    print(" top-1' = realized damage share on the activation's top squad —")
    print(" the sim activates per MODEL, so this reads ~1.0 and army-level")
    print(" splitting is carried by WHICH squad each activation picks;")
    print(" 'ew-prop pred' = the attractiveness-proportional top-1 share;")
    print(" 'picked ew-top' = how often the realized pick was the ew-argmax")
    print(" squad; 'ew share of pick' = the chosen squad's own ew weight)\n")
    hdr = (f"  {'n eligible':>10s} {'activations':>12s} "
           f"{'measured top-1':>15s} {'ew-prop pred':>13s} "
           f"{'picked ew-top':>14s} {'ew share of pick':>17s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for k in ("1", "2", "3", "4+"):
        cnt, s_meas, s_pred, s_hit, s_chosen, n_pred = agg.get(
            k, [0, 0.0, 0.0, 0.0, 0.0, 0])
        meas = s_meas / cnt if cnt else float("nan")
        pred = s_pred / n_pred if n_pred else float("nan")
        hit = s_hit / n_pred if n_pred else float("nan")
        chosen = s_chosen / n_pred if n_pred else float("nan")
        print(f"  {k:>10s} {cnt:12d} {meas:15.3f} {pred:13.3f} "
              f"{hit:14.3f} {chosen:17.3f}")
    print(f"\n  zero-damage activations (no allocation info): {zero}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
