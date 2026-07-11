"""Astra Militarum vs Death Guard canary instrument.

READ-ONLY diagnostic. This matchup is the designated canary for the next
build cycle: the anchor baseline has Astra Militarum winning 36.2 percent of
its 160-game cell against Death Guard, while both factions' real win rates
imply near-parity. A board-read of one indicative game (seed 0, faithful
defaults) found five concrete failure modes:
  (1) Astra Militarum vacates its own deployment zone turn 1, so Death Guard
      deep-strikes unopposed into its backfield;
  (2) the artillery (Manticore + Basilisks) burns activations shooting the
      toughest target on the board (the Foetid Bloat-drone) for near-zero
      damage while softer targets sit on markers;
  (3) the Shock Troops battleline marches into double charges;
  (4) foot officers/Command Squads charge Daemon Princes/Plague Marines for
      no realistic chance of cracking them and die for nothing;
  (5) a lost home-half objective marker is never recontested.

This script quantifies all five, plus the headline win rate and a cheap
Death Guard mirror, over N games (both slot orders, fixed seeds) with an
EventLog-style subscriber plus live-object reads — the same pattern as
`scripts/diag_walked_into_it.py`. It requires NO simulator changes and NO
gate of its own: every SWEG_* environment gate is read from the ambient
process environment exactly as the caller set it, so the loop can re-run
this unchanged with any new layer turned on to see the canary move.

Army building follows `scripts/diag_walked_into_it.py`'s convention exactly:
`build_faction_random_army(..., use_archetype=True)` with a per-slot seeded
`random.Random`, PLUS a `random.seed(seed)` call on the global module before
each game (the simulator's own dice rolls read the global `random` module,
not a passed-in generator, so full-game determinism needs both).

Metrics (see the printed table):
  1. Astra Militarum win rate.
  2. Deep-strike exposure: Death Guard reserve arrivals landing in Astra
     Militarum's own board half / own deployment zone (from UnitDeepStrike
     events vs the map's deployment geometry), and the mean count of Astra
     Militarum units still standing inside their own deployment zone at the
     end of round 1 (the screen-presence gauge).
  3. Shooting misallocation: for every Astra Militarum ranged activation,
     realized damage vs the maximum expected damage available among
     eligible targets at that moment. "Eligible" is approximated as alive,
     unembarked, in range, and with line of sight (core geometry only, no
     dependence on any SWEG_* gated targeting refinement) so the instrument
     stays valid regardless of which levers are on. Expected wounds are
     recomputed live via `Battle._ranged_expected_wounds` against every
     eligible target — the same function the focus-fire AI itself uses.
  4. Home-marker timeline: Astra Militarum's home-half objective markers
     (the objectives that fall on its own side of the board's long-axis
     midline), round-by-round held/enemy-held/contested from
     ObjectiveScored's a_oc/b_oc, flip counts, and whether a marker lost to
     Death Guard was ever re-entered afterward.
  5. Suicide charges: Astra Militarum charges whose expected melee wounds
     (`strategy._kill_potential_wounds`) against the target were below 20
     percent of the target's remaining health at the moment of the charge —
     literally the simulator's own "won't-crack" threshold
     (`strategy._WONT_CRACK_HP_FRAC`) — and how many of those chargers were
     dead by game end.
  6. Death Guard mirror: its own deep-strike arrival total and charges made.

Usage:
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_canary_am_dg
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_canary_am_dg --games 40 --seed-base 100
  SWEG_SOME_NEW_GATE=1 PYTHONHASHSEED=0 python -m scripts.diag_canary_am_dg
"""
from __future__ import annotations

import os
import sys

# PYTHONHASHSEED must be pinned before the interpreter starts hashing strings
# (dict/set iteration order for the sim's internal trackers depends on it) —
# matches the re-exec convention used across scripts/_*_check.py.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(subprocess.run(
        [sys.executable, "-m", "scripts.diag_canary_am_dg"] + sys.argv[1:],
        env=os.environ,
    ).returncode)

import argparse
import random
import statistics
from collections import Counter, defaultdict

from code.army_builder import build_faction_random_army
from code.maps import (
    PARIAH_NEXUS_2K_ROTATION,
    PARIAH_NEXUS_2K_ROTATION_FULL,
    STOCK_MAPS,
)
from code.simulator import Battle, _distance
from code.strategy import _kill_potential_wounds, _WONT_CRACK_HP_FRAC

AM = "Astra Militarum"
DG = "Death Guard"
POINTS = 2000.0


def _pick_map(seed: int):
    """Deterministic map rotation, duplicated (not imported) from
    `scripts.evaluate_vs_meta._pick_rotation_map` to avoid pulling in that
    module's ProcessPoolExecutor / re-exec machinery for a single-process
    diagnostic. Honours SWEG_FULL_DEPLOY_ROTATION so this script's map
    selection never drifts from the real eval frame's."""
    if os.environ.get("SWEG_FULL_DEPLOY_ROTATION", "0") == "1":
        rotation = PARIAH_NEXUS_2K_ROTATION_FULL
    else:
        rotation = PARIAH_NEXUS_2K_ROTATION
    return STOCK_MAPS[rotation[seed % len(rotation)]]


# ---------------------------------------------------------------------------
# Shooting-misallocation instrumentation.
#
# Battle._do_shoot(self, attacker, attacker_army, defender_army) is the exact
# ranged-activation entry point (one call = one UnitShot event, or none if the
# activation bails out on an engagement/advance/etc. lockout). We wrap it at
# the class level, single-process, sequential-games-only (mirrors
# scripts/diag_firepower_audit.py's Unit.attack monkeypatch): before calling
# the original, if the attacker belongs to the game's Astra Militarum army we
# snapshot the best expected-wounds target available; after it returns we
# scan the newly appended events for the UnitShot it produced (if any) and
# pair the two. No gate is touched; PYTHONHASHSEED/SWEG_* all pass through.
# ---------------------------------------------------------------------------
_active_recorder = [None]   # holds the current game's CanaryObserver, or None
_orig_do_shoot = Battle._do_shoot


def _patched_do_shoot(self, attacker, attacker_army, defender_army):
    rec = _active_recorder[0]
    pre = None
    before_n = 0
    if rec is not None and attacker_army.name == rec.am_name and attacker.is_alive:
        before_n = len(rec.events)
        pre = rec.pre_shot_snapshot(self, attacker, defender_army)
    _orig_do_shoot(self, attacker, attacker_army, defender_army)
    if pre is not None:
        rec.finalize_shot(pre, before_n)


class CanaryObserver:
    """Per-game event subscriber + live-object reader. Holds the live Battle
    so it can read current army state (health, position) at the moment an
    event fires — the diag_walked_into_it live-object pattern — instead of
    only replaying the immutable event stream."""

    def __init__(self, battle: Battle, am_name: str, dg_name: str) -> None:
        self.battle = battle
        self.am_name = am_name
        self.dg_name = dg_name
        self.events: list = []
        self.cur_round = 0
        self.winner = None

        # Deep-strike exposure.
        self.dg_deepstrike_total = 0
        self.dg_ds_in_am_half = 0
        self.dg_ds_in_am_dz = 0
        self.am_units_in_dz_r1 = 0

        # Shooting misallocation.
        self.am_shot_activations = 0
        self.am_shot_forfeit_sum = 0.0
        self.am_shot_target_counts: Counter = Counter()

        # Home-marker timeline.
        self.home_marker_names: list = []
        self.marker_status: dict = {}   # (round, obj_name) -> (a_oc, b_oc)
        self.home_marker_flips = 0
        self.home_marker_am_loss_flips = 0
        self.home_marker_am_loss_reentries = 0

        # Suicide charges.
        self.am_suicide_charges = 0
        self.am_suicide_charger_uids: set = set()
        self.killed_uids: set = set()

        # Death Guard mirror.
        self.dg_charges_made = 0

        # Victory-point ledger (iteration 7 of the canary loop): the
        # last-written objective-control reading per (round, marker) for ALL
        # markers (the home-marker dict above filters to the home half), and
        # the final scores read off the Battle after the run. THE QUESTION
        # THE LEDGER ANSWERS: when Astra Militarum castles correctly (holds
        # two markers and shoots), does it lose a DETERMINISTIC two-versus-
        # three primary race that its shooting cannot change?
        self.all_marker_status: dict = {}   # (round, obj_name) -> (a_oc, b_oc)
        self.vp_ledger: dict = {}           # filled by finalize_vp_ledger()

    # -- setup ---------------------------------------------------------- #

    def _am_is_a(self) -> bool:
        return self.am_name == "A"

    def _am_army(self):
        return self.battle.a if self._am_is_a() else self.battle.b

    def setup_home_markers(self) -> None:
        """Astra Militarum's home-half markers = the objectives on its own
        side of the board's long-axis midline (deployment is always along y:
        Army A low-y, Army B high-y — see Battle._deploy_armies). A marker
        sitting exactly on the midline is neutral and excluded."""
        half = self.battle.map.height / 2.0
        names = []
        for obj in self.battle.map.objectives:
            if self._am_is_a() and obj.y < half - 1e-6:
                names.append(obj.name)
            elif not self._am_is_a() and obj.y > half + 1e-6:
                names.append(obj.name)
        self.home_marker_names = names

    # -- live lookups ----------------------------------------------------- #

    def _find_unit(self, uid: str):
        for u in self.battle.a.units:
            if u.uid == uid:
                return u
        for u in self.battle.b.units:
            if u.uid == uid:
                return u
        return None

    def _in_am_half(self, pos) -> bool:
        half = self.battle.map.height / 2.0
        return pos[1] < half if self._am_is_a() else pos[1] > half

    def _in_am_dz(self, pos) -> bool:
        dz = self.battle.map.deployment_width
        if self._am_is_a():
            return pos[1] <= dz
        return pos[1] >= (self.battle.map.height - dz)

    # -- event dispatch ----------------------------------------------------#

    def on_event(self, ev) -> None:
        self.events.append(ev)
        t = type(ev).__name__
        if t == "RoundStarted":
            self.cur_round = ev.round_num
        elif t == "RoundEnded":
            if ev.round_num == 1:
                self._snapshot_round1_dz()
        elif t == "UnitDeepStrike":
            self._on_deepstrike(ev)
        elif t == "UnitCharged":
            if ev.succeeded:
                self._on_charge(ev)
        elif t == "UnitKilled":
            self.killed_uids.add(ev.unit_uid)
        elif t == "ObjectiveScored":
            self._on_obj_scored(ev)
        elif t == "BattleEnded":
            self.winner = ev.winner

    def _snapshot_round1_dz(self) -> None:
        army = self._am_army()
        self.am_units_in_dz_r1 = sum(
            1 for u in army.alive_units if self._in_am_dz(u.position)
        )

    def _on_deepstrike(self, ev) -> None:
        u = self._find_unit(ev.unit_uid)
        if u is None or u.profile.faction != DG:
            return
        self.dg_deepstrike_total += 1
        if self._in_am_half(ev.position):
            self.dg_ds_in_am_half += 1
        if self._in_am_dz(ev.position):
            self.dg_ds_in_am_dz += 1

    def _on_charge(self, ev) -> None:
        attacker = self._find_unit(ev.unit_uid)
        if attacker is None:
            return
        if attacker.profile.faction == DG:
            self.dg_charges_made += 1
            return
        if attacker.profile.faction != AM:
            return
        target = self._find_unit(ev.target_uid)
        if target is None or target.current_health <= 0:
            return
        expected = _kill_potential_wounds(attacker.profile, target.profile)
        if expected < _WONT_CRACK_HP_FRAC * target.current_health:
            self.am_suicide_charges += 1
            self.am_suicide_charger_uids.add(attacker.uid)

    def _on_obj_scored(self, ev) -> None:
        # Victory-point ledger: record EVERY marker's last in-round reading
        # (same last-write-wins convention as the home-marker dict below).
        self.all_marker_status[(self.cur_round, ev.objective_name)] = (
            ev.a_oc, ev.b_oc)
        if ev.objective_name not in self.home_marker_names:
            return
        # Last write per (round, marker) wins — under the default per-player
        # command-phase scoring (SWEG_CMDSCORE, ON by default) a marker is
        # visited twice a round, once from each side's own scoring pass; the
        # a_oc/b_oc fields are the true current OC on BOTH passes (the
        # only_for filter only masks army_name/vp_awarded), so keeping the
        # later pass is simply the more up-to-date in-round reading.
        self.marker_status[(self.cur_round, ev.objective_name)] = (ev.a_oc, ev.b_oc)

    def finalize_home_markers(self) -> None:
        by_marker: dict = defaultdict(dict)
        for (rnd, name), oc in self.marker_status.items():
            by_marker[name][rnd] = oc
        for name, rounds in by_marker.items():
            sorted_rounds = sorted(rounds.keys())
            last_decisive = None
            for i, r in enumerate(sorted_rounds):
                a_oc, b_oc = rounds[r]
                am_oc = a_oc if self._am_is_a() else b_oc
                dg_oc = b_oc if self._am_is_a() else a_oc
                if am_oc > dg_oc:
                    decisive = "AM"
                elif dg_oc > am_oc:
                    decisive = "DG"
                else:
                    decisive = None
                if decisive is not None and last_decisive is not None and decisive != last_decisive:
                    self.home_marker_flips += 1
                    if last_decisive == "AM" and decisive == "DG":
                        self.home_marker_am_loss_flips += 1
                        reentered = False
                        for r2 in sorted_rounds[i + 1:]:
                            a_oc2, b_oc2 = rounds[r2]
                            am_oc2 = a_oc2 if self._am_is_a() else b_oc2
                            if am_oc2 > 0:
                                reentered = True
                                break
                        if reentered:
                            self.home_marker_am_loss_reentries += 1
                if decisive is not None:
                    last_decisive = decisive

    def finalize_vp_ledger(self) -> None:
        """Read the final scores off the finished Battle and reduce the
        all-marker objective-control timeline to markers-held-per-scoring-
        round. Direct attribute access on the Battle internals on purpose
        (fail loud if the scoring fields are ever renamed): the running
        `_a_vp`/`_b_vp` totals are UNCAPPED, the secondary and challenger
        components live in `_a_secondary_vp`/`_a_challenger_vp`, and the
        capped standing (the winner-deciding view) comes from
        `_capped_vp_pair`. Primary = total minus secondary minus challenger,
        exactly as `_capped_vp_pair` derives it."""
        b = self.battle
        a_total = b._a_vp
        b_total = b._b_vp
        a_sec = b._a_secondary_vp
        b_sec = b._b_secondary_vp
        a_chal = b._a_challenger_vp
        b_chal = b._b_challenger_vp
        a_primary = a_total - a_sec - a_chal
        b_primary = b_total - b_sec - b_chal
        a_capped, b_capped = b._capped_vp_pair()
        am_is_a = self._am_is_a()

        def _pick(a_val, b_val):
            return (a_val, b_val) if am_is_a else (b_val, a_val)

        am_primary, dg_primary = _pick(a_primary, b_primary)
        am_sec, dg_sec = _pick(a_sec, b_sec)
        am_chal, dg_chal = _pick(a_chal, b_chal)
        am_capped, dg_capped = _pick(a_capped, b_capped)

        # Markers held per scoring round, from the last recorded
        # objective-control reading of each (round, marker).
        rounds_seen = sorted({rnd for (rnd, _n) in self.all_marker_status})
        am_held_by_round = []
        dg_held_by_round = []
        for rnd in rounds_seen:
            am_held = dg_held = 0
            for (r2, _name), (a_oc, b_oc) in self.all_marker_status.items():
                if r2 != rnd:
                    continue
                am_oc, dg_oc = _pick(a_oc, b_oc)
                if am_oc > dg_oc:
                    am_held += 1
                elif dg_oc > am_oc:
                    dg_held += 1
            am_held_by_round.append(am_held)
            dg_held_by_round.append(dg_held)

        self.vp_ledger = {
            "am_capped": am_capped, "dg_capped": dg_capped,
            "am_primary": am_primary, "dg_primary": dg_primary,
            "am_secondary": am_sec, "dg_secondary": dg_sec,
            "am_challenger": am_chal, "dg_challenger": dg_chal,
            "am_markers_mean": (sum(am_held_by_round) / len(am_held_by_round)
                                if am_held_by_round else 0.0),
            "dg_markers_mean": (sum(dg_held_by_round) / len(dg_held_by_round)
                                if dg_held_by_round else 0.0),
        }

    # -- shooting misallocation -------------------------------------------#

    def pre_shot_snapshot(self, battle: Battle, attacker, defender_army):
        rng = attacker.profile.range_inches or 0.0
        if rng <= 0:
            return None
        # Indirect Fire (the Manticore / Basilisk artillery central to failure
        # mode #2) may target anything in range with no line-of-sight
        # requirement — mirrors the exact branch in Battle._do_shoot. Treating
        # every indirect-fire attacker as LOS-gated here would silently drop
        # legal soft targets sitting behind terrain from the "eligible" pool
        # and understate what the gun could actually have hit.
        indirect = bool(attacker.profile.indirect_fire)
        attacker_kw = attacker.profile.unit_keywords or ()
        best = 0.0
        for u in defender_army.alive_units:
            if getattr(u, "embarked_in", None) is not None:
                continue
            if _distance(attacker.position, u.position) > rng:
                continue
            if not indirect and not battle.map.has_line_of_sight(
                attacker.position, u.position,
                attacker_keywords=attacker_kw,
                target_keywords=u.profile.unit_keywords or (),
            ):
                continue
            ew = Battle._ranged_expected_wounds(attacker.profile, u)
            if ew > best:
                best = ew
        if best <= 0.0:
            return None
        return (attacker.uid, best)

    def finalize_shot(self, pre, before_n: int) -> None:
        attacker_uid, best_exp = pre
        for e in self.events[before_n:]:
            if type(e).__name__ == "UnitShot" and e.attacker_uid == attacker_uid:
                self.am_shot_activations += 1
                self.am_shot_forfeit_sum += 1.0 - (e.damage / best_exp)
                tgt = self._find_unit(e.target_uid)
                tgt_name = tgt.profile.name if tgt is not None else "?"
                self.am_shot_target_counts[tgt_name] += 1
                break


def run_one_game(seed: int, am_slot: str) -> CanaryObserver:
    random.seed(seed)
    map_ = _pick_map(seed)
    dg_slot = "B" if am_slot == "A" else "A"
    if am_slot == "A":
        am_army = build_faction_random_army(
            "A", AM, POINTS, rng=random.Random(seed), use_archetype=True)
        dg_army = build_faction_random_army(
            "B", DG, POINTS, rng=random.Random(seed + 10000), use_archetype=True)
        a, b = am_army, dg_army
    else:
        dg_army = build_faction_random_army(
            "A", DG, POINTS, rng=random.Random(seed + 10000), use_archetype=True)
        am_army = build_faction_random_army(
            "B", AM, POINTS, rng=random.Random(seed), use_archetype=True)
        a, b = dg_army, am_army

    battle = Battle(a, b, map_=map_)
    rec = CanaryObserver(battle, am_name=am_slot, dg_name=dg_slot)
    battle.subscribers.append(rec)
    rec.setup_home_markers()

    _active_recorder[0] = rec
    try:
        battle.run()
    finally:
        _active_recorder[0] = None
    rec.finalize_home_markers()
    rec.finalize_vp_ledger()
    return rec


def _mean_std(vals):
    if not vals:
        return 0.0, 0.0
    return statistics.mean(vals), statistics.pstdev(vals)


def _report(results, n_requested: int) -> None:
    n = len(results)
    wins = [1.0 if r.winner == r.am_name else 0.0 for r in results]
    ds_half = [r.dg_ds_in_am_half for r in results]
    ds_dz = [r.dg_ds_in_am_dz for r in results]
    am_dz_r1 = [r.am_units_in_dz_r1 for r in results]
    shot_act = [r.am_shot_activations for r in results]
    forfeit_per_game = [
        (r.am_shot_forfeit_sum / r.am_shot_activations) if r.am_shot_activations else 0.0
        for r in results
    ]
    flips = [r.home_marker_flips for r in results]
    loss_flips = [r.home_marker_am_loss_flips for r in results]
    suicide_charges = [r.am_suicide_charges for r in results]
    dg_ds_total = [r.dg_deepstrike_total for r in results]
    dg_charges = [r.dg_charges_made for r in results]

    total_am_activations = sum(shot_act)
    total_loss_flips = sum(loss_flips)
    total_reentries = sum(r.home_marker_am_loss_reentries for r in results)
    total_suicide_chargers = sum(len(r.am_suicide_charger_uids) for r in results)
    total_suicide_died = sum(
        1 for r in results for uid in r.am_suicide_charger_uids if uid in r.killed_uids
    )

    top_targets: Counter = Counter()
    for r in results:
        top_targets.update(r.am_shot_target_counts)

    print(f"=== CANARY: {AM} vs {DG} (N={n} games, requested={n_requested}) ===")
    print(f"total Astra Militarum ranged activations counted: {total_am_activations}")
    print()

    rows = []

    def row(label, vals):
        m, s = _mean_std(vals)
        rows.append((label, m, s))

    row("AM win rate (0/1 per game)", wins)
    row("DG deep-strike arrivals in AM's board half /game", ds_half)
    row("DG deep-strike arrivals in AM's deployment zone /game", ds_dz)
    row("AM units still in own deployment zone at end of R1 /game", am_dz_r1)
    row("AM ranged activations /game", shot_act)
    row("AM shooting mean forfeited fraction (per-game mean)", forfeit_per_game)
    row("AM home-half marker flips (any direction) /game", flips)
    row("AM home-half marker LOSS flips (AM->DG) /game", loss_flips)
    row("AM suicide charges (<20% expected wounds) /game", suicide_charges)
    row("DG deep-strike arrivals TOTAL /game (mirror)", dg_ds_total)
    row("DG charges made /game (mirror)", dg_charges)

    label_w = max(len(lbl) for lbl, _, _ in rows)
    print(f"  {'metric':{label_w}s}   {'mean':>8s}   {'+/-spread':>9s}")
    print("  " + "-" * (label_w + 24))
    for lbl, m, s in rows:
        print(f"  {lbl:{label_w}s}   {m:8.3f}   {s:9.3f}")

    # -- Victory-point ledger (iteration 7) ------------------------------ #
    # The question this section answers: when Astra Militarum castles
    # correctly (holds two markers and shoots), does it lose a DETERMINISTIC
    # two-versus-three primary race that its shooting cannot change? A
    # structural marker split with a matching primary gap means movement
    # pricing is no longer the binding constraint — the residual is the
    # kill/scoring economy, escalated to the owner rather than iterated.
    led = [r.vp_ledger for r in results if r.vp_ledger]
    if led:
        def _lmean(key):
            return sum(l[key] for l in led) / len(led)
        print()
        print("  VICTORY-POINT LEDGER (per-game means)")
        print(f"    final standing (capped):   AM {_lmean('am_capped'):6.2f}"
              f"   vs   DG {_lmean('dg_capped'):6.2f}")
        print(f"    primary   (uncapped):      AM {_lmean('am_primary'):6.2f}"
              f"   vs   DG {_lmean('dg_primary'):6.2f}")
        print(f"    secondary (uncapped):      AM {_lmean('am_secondary'):6.2f}"
              f"   vs   DG {_lmean('dg_secondary'):6.2f}")
        print(f"    challenger:                AM {_lmean('am_challenger'):6.2f}"
              f"   vs   DG {_lmean('dg_challenger'):6.2f}")
        print(f"    markers held /scoring rnd: AM {_lmean('am_markers_mean'):6.2f}"
              f"   vs   DG {_lmean('dg_markers_mean'):6.2f}")

    print()
    if total_loss_flips:
        pct = 100.0 * total_reentries / total_loss_flips
        print(f"of {total_loss_flips} AM home-marker LOSS flips (pooled across all games), "
              f"{total_reentries} ({pct:.0f}%) later saw an AM unit re-enter the marker's "
              f"control radius; {total_loss_flips - total_reentries} were never recontested.")
    else:
        print("no AM home-marker LOSS flips observed (own home markers were never lost).")

    if total_suicide_chargers:
        pct = 100.0 * total_suicide_died / total_suicide_chargers
        print(f"of {total_suicide_chargers} AM suicide chargers (pooled, deduped per game), "
              f"{total_suicide_died} ({pct:.0f}%) were dead by game end.")
    else:
        print("no AM suicide charges observed.")

    print()
    print("top 3 most-shot targets by AM ranged-activation count (pooled across all games):")
    if top_targets:
        for name, cnt in top_targets.most_common(3):
            print(f"  {name[:40]:42s} {cnt} shots  ({cnt / n:.2f}/game)")
    else:
        print("  (no AM ranged activations recorded)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=20,
                    help="total games to run, split evenly across both slot orders (default 20)")
    ap.add_argument("--seed-base", type=int, default=0,
                    help="base seed; one seed per slot-order pair, incrementing (default 0)")
    args = ap.parse_args()

    n_pairs = max(1, (args.games + 1) // 2)
    specs = []
    for i in range(n_pairs):
        seed = args.seed_base + i
        specs.append((seed, "A"))
        specs.append((seed, "B"))
    specs = specs[:args.games]

    orig_do_shoot = Battle._do_shoot
    Battle._do_shoot = _patched_do_shoot
    results = []
    try:
        for seed, slot in specs:
            rec = run_one_game(seed, slot)
            if not rec.battle.a.units and not rec.battle.b.units:
                continue
            results.append(rec)
    finally:
        Battle._do_shoot = orig_do_shoot

    _report(results, args.games)


if __name__ == "__main__":
    main()
