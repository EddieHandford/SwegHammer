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

PARTICIPATION DECOMPOSITION (second report section — the residual the
substrate calibration isolated: the allocated field still over-predicts
because it grants every living enemy its full output every turn while most
realized roster-turns spend nothing). Every ZERO-DAMAGE roster-turn slot —
one slot per unit on an army's roster per army turn — is classified into
exclusive causes:

  DEAD-BEFORE-ACTING  — destroyed before its activation that turn (killed in
                        the opponent's preceding turn or earlier in the
                        current one; it never emitted UnitActivated).
  MELEE-LOCKED        — alive and activated but inside engagement range at
                        activation (shooting suppressed or restricted to Big
                        Guns Never Tire), and it did not attack.
  OUT-OF-REACH        — alive, free, activated, did not attack, and had ZERO
                        eligible targets at its end-of-activation position
                        (no enemy within weapon range, none in engagement —
                        the sim has no line-of-sight occlusion, so range is
                        the surface; a melee unit whose charge failed lands
                        here, since realized engagement is its eligibility).
  ENGAGED-BUT-WHIFFED — attacked (shot or fought) but realized zero damage
                        (misses/saves). Separated because expected-wounds
                        math ALREADY prices dice variance — this class is
                        NOT a participation gap and must not be
                        double-counted by any realization-rate term.
  CHOSE-NOT-TO        — alive, free, had eligible targets at its final
                        position, and spent the activation on something else
                        (an objective move / action without attacking).

Plus a no-activation residual (alive but never activated — embarked
passengers and reserves in transit), reported separately so the five classes
stay exclusive and the universe exhaustive. Attribution notes: attacks are
credited to the unit whose activation is open (overwatch and counter-strike
damage during the OPPONENT'S activation is bonus participation outside the
per-turn slot model, and is not attributed); the roster accumulates live
from each army's unit list at every turn boundary, so reserves join the
universe when they arrive.

Also reported: the SURVIVAL-WEIGHTING CURVE — the mean fraction of an army's
roster dead at the start of its own turn, per round 1-5 — the curve a
structural participation term (survival x reachability x not-locked) would
need for its survival factor.

CONDITIONAL-PROPENSITY EVIDENCE (sections 4 and 5 — the inputs to the
registered fallback decision, docs/DECISION_LEDGER.md "THREAT-FIELD
PARTICIPATION RATE"): per living activated slot, whether the unit ATTEMPTED
output (dealt damage or whiffed), reported (4) per faction and (5) bucketed
by the unit's OWN BEST expected-wounds opportunity at its activation — the
best single-target expected wounds over enemies inside its Move + weapon
range (cover-attenuated at the target's cell) or melee reach (the real 2D6
gradient), computed from its pre-move position with the same audited
per-pair helpers the threat field uses. If the attempt rate rises with the
unit's own opportunity, propensity conditioned on attractiveness-weighted
eligibility is the grounded curve the registered fallback would read.

Determinism: PYTHONHASHSEED re-exec mirrors scripts/sim_motion_proof.py.
Zero-damage activations (all shots saved) carry no allocation information and
are counted separately. Events are read via the ordinary subscriber stream
(the diag_walked_into_it live-object pattern); no simulator changes.
--seed-base N shifts every battle seed (the out-of-sample battery convention
shared with scripts/diag_threat_calibration.py).

USAGE
    PYTHONHASHSEED=0 python scripts/diag_fire_allocation.py
    PYTHONHASHSEED=0 python scripts/diag_fire_allocation.py --seed-base 100
"""
from __future__ import annotations

import argparse
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
from code.strategy import (                                        # noqa: E402
    _ENGAGEMENT_RANGE,
    _cover_attenuation,
    _dist,
    _er_gap,
    _kill_potential_wounds,
    _p_2d6_at_least,
    _score_profile,
    _THREAT_ENGAGE_RANGE,
    effective_move,
)

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


# Classification labels for the participation decomposition.
_DEAD = "DEAD-BEFORE-ACTING"
_LOCKED = "MELEE-LOCKED"
_UNREACH = "OUT-OF-REACH"
_WHIFF = "ENGAGED-BUT-WHIFFED"
_CHOSE = "CHOSE-NOT-TO"
_NOACT = "no-activation residual"
_DAMAGE = "dealt damage"


class ParticipationObserver:
    """Classifies every roster-turn slot (one per unit on an army's roster
    per army turn) — see the module docstring's PARTICIPATION DECOMPOSITION
    section for the class definitions and attribution notes.

    Turn structure note (verified against the live event stream): a player
    turn is PHASE-STRUCTURED — every unit emits UnitActivated in the
    Movement phase, then the UnitShot / UnitFought events arrive in the
    later Shooting / Fight phases with no second activation marker. So
    attacks cannot be nested inside an activation window; the classifier
    accumulates per-uid attack and damage tallies across the WHOLE turn
    (crediting only attackers on the acting side, which excludes defensive
    overwatch and counter-strikes) and classifies every roster slot at the
    turn boundary. Engagement is snapshotted per unit AT ITS ACTIVATION
    (pre-move — the lock that suppresses its shooting); target eligibility
    for the CHOSE-NOT-TO / OUT-OF-REACH split is read at turn close, when
    the turn's positions have settled."""

    def __init__(self, battle: Battle) -> None:
        self.battle = battle
        self.counts = defaultdict(int)          # class label -> slots
        # round -> [sum of dead-fractions at turn start, turn count]
        self.dead_curve = defaultdict(lambda: [0.0, 0])
        # Conditional-propensity evidence: per faction and per own-best-ew
        # bucket, [living activated slots, attempts (damage or whiff)].
        self.propensity_fac = defaultdict(lambda: [0, 0])
        self.propensity_ew = defaultdict(lambda: [0, 0])
        self._round = 0
        self._cur_army = None                   # army NAME whose turn is open
        self._cur_side = None                   # "A"/"B" uid prefix
        self._activated = {}                    # uid -> engaged at activation
        self._best_ew = {}                      # uid -> own best-ew opportunity
        self._attacked = set()                  # acting-side uids that attacked
        self._damage = defaultdict(float)       # acting-side uid -> damage
        self._roster = {"A": {}, "B": {}}       # side -> uid -> unit ref

    # -- live lookups ------------------------------------------------------
    def _side(self, army_name):
        return "A" if self.battle.a.name == army_name else "B"

    def _army_obj(self, army_name):
        return (self.battle.a if self.battle.a.name == army_name
                else self.battle.b)

    def _unit(self, uid):
        for u in list(self.battle.a.units) + list(self.battle.b.units):
            if u.uid == uid:
                return u
        return None

    def _enemies_of_unit(self, unit):
        other = (self.battle.b if unit.uid.startswith("A") else self.battle.a)
        return other.alive_units

    def _engaged(self, unit):
        return any(
            _er_gap(unit.position, unit.profile, e.position, e.profile)
            <= _ENGAGEMENT_RANGE
            for e in self._enemies_of_unit(unit))

    def _has_eligible(self, unit):
        """Any target at the unit's (settled) position: an enemy within its
        weapon range (max of model and squad-aggregate range), or an enemy
        inside engagement range (it could fight)."""
        sp = _score_profile(unit)
        rng = max(float(getattr(sp, "range_inches", 0.0) or 0.0),
                  float(getattr(unit.profile, "range_inches", 0.0) or 0.0))
        for e in self._enemies_of_unit(unit):
            if rng > 0.0 and _dist(unit.position, e.position) <= rng:
                return True
            if (_er_gap(unit.position, unit.profile, e.position, e.profile)
                    <= _ENGAGEMENT_RANGE):
                return True
        return False

    def _best_ew_opportunity(self, unit):
        """The unit's OWN best single-target expected-wounds opportunity at
        its activation: over living enemies, the better of its ranged
        expected wounds (if the enemy is inside Move + weapon range,
        cover-attenuated at the enemy's cell) and its melee kill-potential
        weighted by the real 2D6 reach gradient — the same audited per-pair
        helpers the threat field uses, from the unit's pre-move position."""
        sp = _score_profile(unit)
        move = float(effective_move(unit))
        rng = max(float(getattr(sp, "range_inches", 0.0) or 0.0),
                  float(getattr(unit.profile, "range_inches", 0.0) or 0.0))
        melee_capable = (getattr(sp, "melee_attacks", 0) or 0) > 0
        best = 0.0
        for e in self._enemies_of_unit(unit):
            d = _dist(unit.position, e.position)
            ew = 0.0
            if rng > 0.0 and d <= move + rng:
                rw = Battle._ranged_expected_wounds(sp, e)
                if rw > 0.0:
                    rw *= _cover_attenuation(e, getattr(sp, "ap", 0) or 0,
                                             self.battle.map, e.position)
                ew = rw
            if melee_capable:
                needed = d - move - _THREAT_ENGAGE_RANGE
                if needed <= 12.0:
                    mw = (_kill_potential_wounds(sp, _score_profile(e))
                          * _p_2d6_at_least(needed))
                    if mw > ew:
                        ew = mw
            if ew > best:
                best = ew
        return best

    @staticmethod
    def _ew_bucket(ew):
        if ew <= 0.0:
            return "0"
        if ew <= 0.5:
            return "(0, 0.5]"
        if ew <= 1.5:
            return "(0.5, 1.5]"
        if ew <= 3.0:
            return "(1.5, 3]"
        return "> 3"

    # -- event stream ------------------------------------------------------
    def on_event(self, ev) -> None:
        name = type(ev).__name__
        if name == "RoundStarted":
            self._round = ev.round_num
        elif name == "UnitActivated":
            if self._cur_army is not None and ev.army_name != self._cur_army:
                self._close_turn()
            if self._cur_army != ev.army_name:
                self._open_turn(ev.army_name)
            u = self._unit(ev.unit_uid)
            self._activated[ev.unit_uid] = (
                self._engaged(u) if u is not None else False)
            self._best_ew[ev.unit_uid] = (
                self._best_ew_opportunity(u) if u is not None else 0.0)
        elif name in ("UnitShot", "UnitFought"):
            # Credit only attackers on the ACTING side — a defender's
            # overwatch / counter-strike is participation outside its own
            # turn slot and is deliberately not attributed here.
            if (self._cur_side is not None
                    and ev.attacker_uid.startswith(self._cur_side)):
                self._attacked.add(ev.attacker_uid)
                self._damage[ev.attacker_uid] += max(0.0, ev.damage)
        elif name == "BattleEnded":
            self._close_turn()

    def _open_turn(self, army_name) -> None:
        self._cur_army = army_name
        self._cur_side = self._side(army_name)
        self._activated = {}
        self._attacked = set()
        self._damage = defaultdict(float)
        # Accumulate the roster live (reserves join when they arrive) and
        # record the survival curve point: fraction of the acting army's
        # accumulated roster dead at its turn start.
        roster = self._roster[self._cur_side]
        for u in self._army_obj(army_name).units:
            roster[u.uid] = u
        if roster:
            dead = sum(1 for u in roster.values() if u.current_health <= 0)
            row = self.dead_curve[max(1, min(self._round, 5))]
            row[0] += dead / len(roster)
            row[1] += 1

    def _close_turn(self) -> None:
        if self._cur_army is None:
            return
        for uid, u in self._roster[self._cur_side].items():
            attempted = False
            if self._damage.get(uid, 0.0) > 0.0:
                self.counts[_DAMAGE] += 1
                attempted = True
            elif uid in self._attacked:
                self.counts[_WHIFF] += 1
                attempted = True
            elif uid in self._activated:
                if self._activated[uid]:
                    self.counts[_LOCKED] += 1
                elif self._has_eligible(u):
                    self.counts[_CHOSE] += 1
                else:
                    self.counts[_UNREACH] += 1
            elif u.current_health <= 0:
                self.counts[_DEAD] += 1
                continue
            else:
                self.counts[_NOACT] += 1
                continue
            # Conditional-propensity evidence over LIVING ACTIVATED slots.
            if uid in self._activated:
                fac = self.propensity_fac[u.profile.faction]
                fac[0] += 1
                fac[1] += 1 if attempted else 0
                bucket = self.propensity_ew[
                    self._ew_bucket(self._best_ew.get(uid, 0.0))]
                bucket[0] += 1
                bucket[1] += 1 if attempted else 0
        self._cur_army = None
        self._cur_side = None
        self._activated = {}
        self._best_ew = {}
        self._attacked = set()
        self._damage = defaultdict(float)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed-base", type=int, default=0,
                    help="shift every battle seed by N (0 = the fit battery; "
                         "a non-zero base is the out-of-sample battery)")
    args = ap.parse_args()
    agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0, 0])
    zero = 0
    part_counts = defaultdict(int)
    dead_curve = defaultdict(lambda: [0.0, 0])
    prop_fac = defaultdict(lambda: [0, 0])
    prop_ew = defaultdict(lambda: [0, 0])
    for (fa, fb, base_seed) in BATTLES:
        seed = base_seed + args.seed_base
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
        part = ParticipationObserver(battle)
        battle.subscribers.append(obs)
        battle.subscribers.append(part)
        battle.run()
        for k, v in obs.buckets.items():
            for i in range(6):
                agg[k][i] += v[i]
        zero += obs.zero_damage_activations
        for k, v in part.counts.items():
            part_counts[k] += v
        for r, row in part.dead_curve.items():
            dead_curve[r][0] += row[0]
            dead_curve[r][1] += row[1]
        for k, v in part.propensity_fac.items():
            prop_fac[k][0] += v[0]
            prop_fac[k][1] += v[1]
        for k, v in part.propensity_ew.items():
            prop_ew[k][0] += v[0]
            prop_ew[k][1] += v[1]

    print("fire-allocation concentration curve — %d fixed-seed battles, "
          "%d points, use_archetype=True, seed base %d%s"
          % (len(BATTLES), POINTS_BUDGET, args.seed_base,
             "" if args.seed_base == 0 else " (OUT-OF-SAMPLE battery)"))
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

    total_slots = sum(part_counts.values())
    dealt = part_counts.get(_DAMAGE, 0)
    zero_slots = total_slots - dealt
    print("\n2) ZERO-DAMAGE PARTICIPATION DECOMPOSITION")
    print("   (one slot per roster unit per army turn; exclusive classes —")
    print("    see the module docstring for definitions)")
    print(f"  roster-turn slots: {total_slots}")
    print(f"  dealt damage:      {dealt}  "
          f"({100.0 * dealt / max(1, total_slots):.1f}% of slots)")
    print(f"  zero damage:       {zero_slots}, classified:")
    for label in (_DEAD, _LOCKED, _UNREACH, _WHIFF, _CHOSE, _NOACT):
        n = part_counts.get(label, 0)
        print(f"    {label:24s} {n:6d}  "
              f"({100.0 * n / max(1, zero_slots):5.1f}% of zero-damage)")

    print("\n3) SURVIVAL-WEIGHTING CURVE")
    print("   (mean fraction of the acting army's accumulated roster dead at")
    print("    its own turn start — the survival factor a structural")
    print("    participation term would need)")
    for r in range(1, 6):
        s, n = dead_curve.get(r, [0.0, 0])
        frac = s / n if n else float("nan")
        print(f"  round {r}: {frac:6.3f}   ({n} army-turns)")

    print("\n4) ATTEMPT PROPENSITY PER FACTION")
    print("   (living activated slots that attempted output — dealt damage")
    print("    or whiffed; the per-faction spread of the flat measured rate)")
    for fac in sorted(prop_fac):
        slots, attempts = prop_fac[fac]
        rate = attempts / slots if slots else float("nan")
        print(f"  {fac:22s} {slots:6d} slots   propensity {rate:6.3f}")

    print("\n5) ATTEMPT PROPENSITY vs OWN BEST EXPECTED WOUNDS")
    print("   (bucketed by the unit's own best single-target expected-wounds")
    print("    opportunity at its activation — the conditional-propensity")
    print("    curve the registered fallback would read)")
    for k in ("0", "(0, 0.5]", "(0.5, 1.5]", "(1.5, 3]", "> 3"):
        slots, attempts = prop_ew.get(k, [0, 0])
        rate = attempts / slots if slots else float("nan")
        print(f"  best-ew {k:11s} {slots:6d} slots   propensity {rate:6.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
