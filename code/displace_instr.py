"""Displacement substrate Stage 0 — FIGHT-OUTCOME instrument (gate SWEG_DISPLACE_INSTR).

READ-ONLY. This module measures, per faction-matchup and per game, how many primary
victory points the simulator's objective-control model awards in board states that
REAL competitive play would resolve differently — the displacement gap. It changes no
decision and consumes no randomness, so the OFF path is byte-identical (including the
random stream) and the ON path produces the same winner + score for the same seed.

WHY THIS EXISTS
---------------
The sim resolves objective-marker control by raw summed Objective Control within the
control radius (see `Battle._score_objectives`). Two failure modes follow, and Stage 0
sizes the victory points each is worth BEFORE any behavioural build:

  * UNDER-POLE (loser-held). A durable winner that has been out-fought locally still
    sits on a marker and keeps scoring it, because nobody physically removes or
    displaces it. Real play: the side winning the local fight pushes the beaten unit
    off and takes the tick. Astra Militarum / Adepta Sororitas durable winners that
    cannot convert a won fight into a taken marker live here.

  * OVER-POLE (uncontested durable hold). A single concentrated durable holder
    (Imperial Knight) parks OC-10 on a marker and is never swarmed, even when the
    opponent has bodies nearby whose summed Objective Control could flip or contest
    it if they committed. Real play: those bodies pile in and contest. The Knight's
    uncontested tick is swarm-addressable.

  * FAITHFUL TARPIT (NOT addressable — counted separately for information). An
    out-fought side that does NOT control but stays in engagement range of the
    holder's units at the marker, denying or flipping the tick by dying on the
    marker — this is CORRECT competitive play and must not be "fixed". Its denied
    victory points are tallied only so the two addressable buckets are not inflated
    by board states that are already faithful.

HOW IT TAPS
-----------
1. DAMAGE: at every damage-resolution site (shooting, fight, counter-offensive,
   overwatch) the simulator calls `record_damage(...)`. The cheap tap is the
   DEFENDER's position: if the defender model is within 6" of a marker, the damage
   it just took is credited to that marker as "dealt by the attacker's side" for the
   current battle round. This accumulates LOCAL fight dominance per marker per round.

2. CLASSIFY: at each primary scoring check (`_score_objectives`, rounds 2+), for each
   live marker, `classify_tick(...)` reads the already-computed summed Objective
   Control, the controller, the per-marker VP, and this round's accumulated local
   damage, then files the tick into exactly one bucket (see below). After the whole
   scoring pass the per-round damage accumulator is reset by `end_round()`.

CLASSIFICATION DEFINITIONS (as implemented; refinements documented inline)
--------------------------------------------------------------------------
For one marker-tick, let CONTROLLER be the side credited with the marker (strictly
greater summed Objective Control, or the sticky owner when neither side has OC), LOSER
be the other side, `ctrl_dealt`/`ctrl_recv` be the damage the controller dealt / received
AT THIS MARKER THIS ROUND (within 6"), `loser_oc` the loser's summed on-marker OC, and
VP the victory points awarded to the controller this tick. The buckets are mutually
exclusive — each tick files into AT MOST ONE — evaluated in this fixed priority order:

  c. FAITHFUL TARPIT (checked FIRST, not addressable). The LOSER has one or more models
     within engagement range (1") of any of the CONTROLLER's units that are within 6"
     of the marker. The loser is dying on the marker to deny/contest — faithful play.
     VP credited to `tarpit_vp_denied` for the LOSER's faction (the side doing the
     faithful denial). REFINEMENT vs the brief: the brief phrases tarpit as "does not
     control but has models in engagement range of the controller's units at the
     marker". We require the controller unit to itself be within 6" of the marker (not
     merely anywhere on the board) so the engagement is genuinely AT this marker; this
     is the same 6" locality the damage tap uses and prevents a melee elsewhere from
     being mis-filed as a marker tarpit.

  a. LOSER-HELD / under-pole (checked second). The CONTROLLER was clearly out-fought
     locally: it received local damage and dealt strictly LESS THAN HALF of what it
     received (`ctrl_dealt < 0.5 * ctrl_recv` and `ctrl_recv > 0`). Yet it controls.
     VP credited to `vp_addressable_underpole` for the CONTROLLER's faction.

  b. UNCONTESTED DURABLE HOLD / over-pole (checked last). The marker is controlled with
     the LOSER having ZERO summed Objective Control on it (`loser_oc == 0`, truly
     uncontested), the controller holds it with a SINGLE squad in marker range, and the
     loser has one or more units with models within 12" of the marker whose summed
     Objective Control is greater than zero (it could move in and flip/contest). VP
     credited to `vp_addressable_overpole` for the CONTROLLER's faction. REFINEMENT vs
     the brief: the brief says the nearby OC "could flip or contest". We require the
     nearby OC merely to be > 0 (any body that could contest), NOT strictly greater than
     the holder's OC, because a Knight's OC-10 is rarely beaten by a single nearby body
     yet a swarm that piles MULTIPLE bodies in would still contest the tick away; the
     summed-within-12" figure is also recorded so a stricter "could flip" (> holder OC)
     reading can be re-derived from the raw stats without re-running.

  CONTESTED-WON (no bucket, but counted). A tick where both sides had OC on the marker
  (`loser_oc > 0`) and the controller was NOT out-fought is a contested win — neither
  addressable nor a tarpit. Counted in `contested_ticks` for the per-game summary.

Every bucket is a SUM of victory points credited per faction (the side named above),
plus a count of contributing ticks. Totals are non-negative by construction.

Output object: `DisplaceInstr` accumulates into per-side `DisplaceSideTotals` and is
attached to the `BattleResult` as `.displace` when the gate is on; a per-game summary
is printed at battle end by `Battle.run`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional


GATE_ENV = "SWEG_DISPLACE_INSTR"

# Engagement range and the marker-locality radius (inches). 1" is the 10e core
# Engagement Range; 6" is the brief's locality window for "fighting AT this marker".
_ENGAGE_RANGE = 1.0
_MARKER_LOCAL = 6.0
_REACH_12 = 12.0


def gate_on() -> bool:
    """True when the instrument gate is set. Read once per Battle construction by the
    simulator; the OFF path never constructs a DisplaceInstr, so it stays byte-identical."""
    return bool(os.environ.get(GATE_ENV))


@dataclass
class DisplaceSideTotals:
    """Per-side (A or B) running displacement tallies for one game."""
    faction: str = "?"
    vp_addressable_underpole: float = 0.0   # (a) this side controls but was out-fought
    vp_addressable_overpole: float = 0.0    # (b) this side holds uncontested but swarm-able
    tarpit_vp_denied: float = 0.0           # (c) this side faithfully tarpits the holder
    underpole_ticks: int = 0
    overpole_ticks: int = 0
    tarpit_ticks: int = 0
    contested_ticks: int = 0                # both-sided contest this side won (info)
    # Raw nearby-OC sum recorded on over-pole ticks (lets a stricter "could flip"
    # reading be re-derived offline without re-running the sim).
    overpole_nearby_oc_sum: float = 0.0

    def as_dict(self) -> dict:
        return {
            "faction": self.faction,
            "vp_addressable_underpole": self.vp_addressable_underpole,
            "vp_addressable_overpole": self.vp_addressable_overpole,
            "tarpit_vp_denied": self.tarpit_vp_denied,
            "underpole_ticks": self.underpole_ticks,
            "overpole_ticks": self.overpole_ticks,
            "tarpit_ticks": self.tarpit_ticks,
            "contested_ticks": self.contested_ticks,
            "overpole_nearby_oc_sum": self.overpole_nearby_oc_sum,
        }


class DisplaceInstr:
    """Per-game fight-outcome instrument. One instance is created by `Battle` only when
    the gate is on. Observation-only: it reads board state and accumulates totals, never
    mutating a unit, an army, a roll, or a decision.

    Accumulators:
      * `_round_dmg[obj_idx]` -> [a_dealt, b_dealt] : local damage at the marker THIS
        round, reset by `end_round()` after the scoring pass.
      * `a` / `b` : DisplaceSideTotals for the two armies (A = army_a, B = army_b).
    """

    __slots__ = ("a", "b", "_round_dmg", "contested_marker_ticks")

    def __init__(self, faction_a: str, faction_b: str):
        self.a = DisplaceSideTotals(faction=faction_a or "?")
        self.b = DisplaceSideTotals(faction=faction_b or "?")
        self._round_dmg: Dict[int, list] = {}
        self.contested_marker_ticks = 0

    # -- damage tap ----------------------------------------------------------------
    def record_damage(self, attacker_is_a: bool, defender, objectives, dmg: float) -> None:
        """Credit `dmg` (dealt by side A if `attacker_is_a` else side B) to every marker
        the DEFENDER model is currently within 6" of. The defender-position tap is the
        cheap signal the brief specifies. No-op for non-positive damage or a defender
        with no position (e.g. an embarked / off-board unit)."""
        if dmg <= 0:
            return
        pos = getattr(defender, "position", None)
        if pos is None:
            return
        dx0, dy0 = pos[0], pos[1]
        local2 = _MARKER_LOCAL * _MARKER_LOCAL
        for obj_idx, obj in enumerate(objectives):
            dx = dx0 - obj.x
            dy = dy0 - obj.y
            if dx * dx + dy * dy <= local2:
                slot = self._round_dmg.get(obj_idx)
                if slot is None:
                    slot = [0.0, 0.0]
                    self._round_dmg[obj_idx] = slot
                slot[0 if attacker_is_a else 1] += dmg

    # -- per-marker classification at a scoring tick -------------------------------
    def classify_tick(
        self,
        obj_idx: int,
        obj,
        controller: Optional[str],
        a_name: str,
        b_name: str,
        a_oc: int,
        b_oc: int,
        vp: float,
        army_a,
        army_b,
        battleshocked: set,
        effective_oc,
        squad_in_range_count,
    ) -> None:
        """File one marker-tick into exactly one bucket. Arguments are all already
        computed by the caller (`_score_objectives`) so this does no rule geometry of
        its own beyond the cheap engagement / 12"-reach scans.

        `effective_oc(unit) -> int` and `squad_in_range_count(army, obj) -> int` are
        passed in from the Battle so the instrument reuses the simulator's existing OC
        and coherency-range helpers rather than re-implementing rule geometry."""
        if controller is None:
            # Nobody scores this tick — nothing addressable. (Also no VP awarded.)
            return

        if controller == a_name:
            ctrl_side, loser_side = self.a, self.b
            ctrl_army, loser_army = army_a, army_b
            ctrl_is_a = True
            loser_oc = b_oc
        elif controller == b_name:
            ctrl_side, loser_side = self.b, self.a
            ctrl_army, loser_army = army_b, army_a
            ctrl_is_a = False
            loser_oc = a_oc
        else:
            # Fail loud (rule 13): a controller name that matches neither army is a bug,
            # not a state to swallow.
            raise ValueError(
                f"displace_instr.classify_tick: controller {controller!r} matches neither "
                f"army ({a_name!r} / {b_name!r}) at objective {obj_idx}"
            )

        slot = self._round_dmg.get(obj_idx)
        if slot is None:
            ctrl_dealt = ctrl_recv = 0.0
        else:
            a_dealt, b_dealt = slot
            if ctrl_is_a:
                ctrl_dealt, ctrl_recv = a_dealt, b_dealt
            else:
                ctrl_dealt, ctrl_recv = b_dealt, a_dealt

        # Controller's units that are within 6" of the marker (the local presence the
        # loser must reach to tarpit). Computed once for the tarpit scan.
        ox, oy = obj.x, obj.y
        local2 = _MARKER_LOCAL * _MARKER_LOCAL
        ctrl_local = [
            u for u in ctrl_army.alive_units
            if u.uid not in battleshocked
            and (u.position[0] - ox) ** 2 + (u.position[1] - oy) ** 2 <= local2
        ]

        # ---- (c) FAITHFUL TARPIT (checked first) ---------------------------------
        # The loser does not control but keeps a model within Engagement Range (1") of a
        # controller unit that is itself local to the marker — dying on the marker to
        # deny/contest, the correct competitive play. Counted, NOT addressable.
        er2 = _ENGAGE_RANGE * _ENGAGE_RANGE
        if ctrl_local:
            for lu in loser_army.alive_units:
                lpx, lpy = lu.position[0], lu.position[1]
                tarpit = False
                for cu in ctrl_local:
                    ddx = lpx - cu.position[0]
                    ddy = lpy - cu.position[1]
                    if ddx * ddx + ddy * ddy <= er2:
                        tarpit = True
                        break
                if tarpit:
                    loser_side.tarpit_vp_denied += vp
                    loser_side.tarpit_ticks += 1
                    return

        # ---- (a) LOSER-HELD / under-pole (checked second) ------------------------
        # The controller received local damage and dealt strictly less than half of it.
        if ctrl_recv > 0.0 and ctrl_dealt < 0.5 * ctrl_recv:
            ctrl_side.vp_addressable_underpole += vp
            ctrl_side.underpole_ticks += 1
            return

        # ---- (b) UNCONTESTED DURABLE HOLD / over-pole (checked last) --------------
        # Uncontested (loser has no OC on the marker), a single controlling squad in
        # range, and the loser has reachable Objective Control within 12" that could
        # move in and contest.
        if loser_oc == 0:
            ctrl_squads = squad_in_range_count(ctrl_army, obj)
            if ctrl_squads == 1:
                reach2 = _REACH_12 * _REACH_12
                nearby_oc = 0.0
                for lu in loser_army.alive_units:
                    if lu.uid in battleshocked:
                        continue
                    ddx = lu.position[0] - ox
                    ddy = lu.position[1] - oy
                    if ddx * ddx + ddy * ddy <= reach2:
                        nearby_oc += effective_oc(lu)
                if nearby_oc > 0:
                    ctrl_side.vp_addressable_overpole += vp
                    ctrl_side.overpole_ticks += 1
                    ctrl_side.overpole_nearby_oc_sum += nearby_oc
                    return

        # ---- CONTESTED-WON (no bucket; informational count) ----------------------
        # Both sides had OC and the controller was not out-fought — a faithful contested
        # win. Count it for the per-game summary so addressable buckets are read in
        # context.
        if loser_oc > 0:
            ctrl_side.contested_ticks += 1
            self.contested_marker_ticks += 1

    def end_round(self) -> None:
        """Reset the per-round local-damage accumulator. Called by `_score_objectives`
        after the whole marker loop so the next round starts clean."""
        self._round_dmg.clear()

    # -- per-game summary ----------------------------------------------------------
    def summary(self) -> dict:
        """Well-formed per-game summary dict (both sides + contested tick count)."""
        return {
            "a": self.a.as_dict(),
            "b": self.b.as_dict(),
            "contested_marker_ticks": self.contested_marker_ticks,
        }

    def format_summary(self, a_name: str, b_name: str) -> str:
        """Human-readable one-block summary printed at battle end."""
        s = self.summary()
        lines = ["[displace-instr] fight-outcome displacement (victory points, this game):"]
        for side_key, army_name, side in (("a", a_name, s["a"]), ("b", b_name, s["b"])):
            lines.append(
                f"  {army_name} ({side['faction']}): "
                f"under-pole(loser-held)={side['vp_addressable_underpole']:.1f}vp "
                f"over-pole(uncontested-hold)={side['vp_addressable_overpole']:.1f}vp "
                f"tarpit-denied={side['tarpit_vp_denied']:.1f}vp "
                f"[ticks u/o/t/c="
                f"{side['underpole_ticks']}/{side['overpole_ticks']}/"
                f"{side['tarpit_ticks']}/{side['contested_ticks']}]"
            )
        lines.append(f"  contested marker-ticks (both): {s['contested_marker_ticks']}")
        return "\n".join(lines)
