"""Pilot layer: wires a DuelGenome onto a Battle via the pilot hooks.

Three attachment points, all following the pre-existing Battle._pilot_focus
precedent (an attribute production code never sets, consulted via
getattr(..., None)):

  * Battle._pilot_charge — overrides WHETHER a unit wants to charge
    (gene: charge_aggression). Whom to charge stays with the baseline
    pick_charge_target.
  * Battle._pilot_move  — sees the baseline (target_pos, intent) from
    pick_move_intent and may replace it (genes: advance_vs_hold_bias,
    kite_hold_range).
  * Army._ai_lab_dual_scales — (threat_buffer_scale, score_min_scale) read
    INSIDE pick_move_intent's DUAL branch (genes: charge_range_buffer,
    melee_engage_score_min). Scaling inside the branch — rather than post-hoc
    here — is what lets a narrowed pick fall through to the objective logic,
    exactly as an out-of-range target would.

Byte-identity guarantee: every gene's override is STRUCTURALLY skipped at its
neutral value (explicit early-returns / attribute not planted), and no code
in this module ever touches the random module — so attaching NEUTRAL_GENOME
to both sides of a seeded Battle reproduces the unhooked battle exactly
(tests/test_ai_lab_pilot_hooks.py proves this event-for-event).
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from ..detachments import effective_move
from .genome import DuelGenome

# Engagement range in inches (10e core); mirrors _ENGAGEMENT_RANGE in
# code/strategy.py.
_ENGAGEMENT_RANGE = 1.0


def _guard_squadact() -> None:
    """Fail loud if the squad-activation rebuild gate is on.

    pick_move_intent is ALSO called at code/simulator.py's squad-level
    move-decision cache (the SWEG_SQUADACT Stage A precompute). That call is
    inert today — the cache is populated but never applied — but if a future
    stage starts applying it, the pilot's move override would be silently
    bypassed. Refusing to run under the gate turns that silent bypass into a
    loud error (CLAUDE.md rule 13). Graduating the squad-activation cache
    requires wrapping that call site with the same pilot consultation.
    """
    if os.environ.get("SWEG_SQUADACT") == "1":
        raise RuntimeError(
            "code/ai_lab/pilot: SWEG_SQUADACT=1 is set. The squad-level "
            "move-intent cache in code/simulator.py bypasses the AI-Lab "
            "pilot's move override (Army._ai_lab_dual_scales is consulted, "
            "but Battle._pilot_move is not, on that path once the cache is "
            "applied). Unset SWEG_SQUADACT to run AI-Lab duels."
        )


def _dpa_pair(profile) -> Tuple[float, float]:
    """(melee_dpa, ranged_dpa) exactly as Battle._wants_to_charge computes them."""
    melee_dpa = (
        profile.melee_attacks
        * profile.melee_hit_probability
        * (profile.melee_damage_per_shot or 1.0)
    )
    ranged_dpa = (
        max(1, profile.attacks)
        * profile.hit_probability
        * profile.per_shot_damage
    )
    return melee_dpa, ranged_dpa


def _scaled_wants_to_charge(profile, charge_aggression: float) -> bool:
    """Battle._wants_to_charge with melee output scaled by the gene.

    At charge_aggression == 1.0 this reproduces the baseline exactly (same
    early-exit, same floor) — but callers must not rely on that: the pilot
    returns None at neutral instead, keeping the no-op structural.
    """
    if profile.melee_attacks <= 0 or profile.melee_hit_probability <= 0:
        return False
    melee_dpa, ranged_dpa = _dpa_pair(profile)
    # 1.0x melee floor avoids vehicles with token bayonets charging Marines
    # (same floor as the baseline heuristic).
    return melee_dpa * charge_aggression >= max(ranged_dpa, 1.0)


def _nearest_enemy_from(point, defender_army):
    """Nearest alive enemy to `point` by centre-to-centre distance, with that
    distance.

    Centre-to-centre (not base-edge) is deliberate: this is a piloting
    heuristic, not a rules measurement, and the simpler metric keeps the
    gene interpretable. Returns (None, inf) when nothing is alive — callers
    treat that as "no override".
    """
    best = None
    best_d2 = float("inf")
    px, py = point
    for e in defender_army.alive_units:
        ex, ey = e.position
        d2 = (px - ex) ** 2 + (py - ey) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = e
    return best, best_d2 ** 0.5


def _nearest_enemy(attacker, defender_army):
    return _nearest_enemy_from(attacker.position, defender_army)


def _squad_members(attacker, attacker_army):
    """Alive squadmates sharing `attacker`'s squad_id, including `attacker`
    itself. A lone model (squad_id < 0) is its own one-member "squad".

    Falls back to [attacker] if the army lookup comes back empty — in a real
    Battle the attacker is by definition alive and present in its own army,
    so the fallback only fires for synthetic test stubs, but an empty squad
    would crash the centroid computation, so never return one.
    """
    squad_id = getattr(attacker, "squad_id", -1)
    if squad_id < 0:
        return [attacker]
    members = [u for u in attacker_army.alive_units
               if getattr(u, "squad_id", -1) == squad_id]
    return members or [attacker]


def _squad_centroid(members):
    n = len(members)
    cx = sum(m.position[0] for m in members) / n
    cy = sum(m.position[1] for m in members) / n
    return (cx, cy)


def _genome_for(army_genome_pairs, army, hook_name: str) -> DuelGenome:
    """Identity lookup over [(army, genome), ...].

    Deliberately NOT an id()-keyed dict: the closure holding strong
    references and comparing with `is` means a garbage-collected army's
    reused memory address can never alias a briefed one, and an army the
    pilot was never briefed on fails loud rather than silently piloting
    one side only (CLAUDE.md rule 13).
    """
    for known_army, genome in army_genome_pairs:
        if known_army is army:
            return genome
    raise KeyError(
        f"ai_lab {hook_name}: no genome attached for army "
        f"{getattr(army, 'name', army)!r}"
    )


def _make_pilot_charge(army_genome_pairs):
    def pilot_charge(battle, attacker, attacker_army) -> Optional[bool]:
        genome = _genome_for(army_genome_pairs, attacker_army, "pilot_charge")
        if genome.charge_aggression == 1.0:
            return None   # structural no-op at neutral
        return _scaled_wants_to_charge(attacker.profile, genome.charge_aggression)
    return pilot_charge


def _make_pilot_move(army_genome_pairs, squad_move_as_unit: bool = False):
    # Per-duel decision caches, keyed by (id(attacker_army), squad_key,
    # current_round). A fresh closure (and so a fresh, empty cache) is built
    # on every pilot.attach() call, which happens once per duel — so this
    # never leaks state between duels and needs no manual reset.
    #
    # WHY THESE CACHES EXIST: kite_hold_range and advance_vs_hold_bias were
    # originally evaluated independently per model. Squad members standing
    # a few inches apart can straddle a hard distance threshold, so some
    # models would hold at range while their squadmates closed to melee —
    # the squad visibly split apart, well beyond what the simulator's
    # post-move coherency pass (code/simulator.py::_enforce_squad_coherency)
    # can repair, since a model that already spent its full move charging in
    # has no remaining move budget left to be pulled back. Deciding ONCE per
    # squad per round — from the squad's centroid, not any one model's
    # position — keeps every model in a squad making the same categorical
    # choice, exactly like a real player deciding "the squad holds" or "the
    # squad advances" as one call, not five independent coin-flips.
    kite_decisions = {}
    advance_directions = {}
    walk_targets = {}

    def _squad_cache_key(attacker, attacker_army, current_round):
        # Lone models (squad_id < 0) must NOT share one cache slot — keying
        # them all under -1 would make the first lone model's decision leak
        # onto every other lone model in the army that round. Key them by
        # their own identity instead (each is its own one-model "squad").
        squad_id = getattr(attacker, "squad_id", -1)
        if squad_id < 0:
            squad_id = ("solo", getattr(attacker, "uid", id(attacker)))
        return (id(attacker_army), squad_id, current_round)

    def pilot_move(battle, attacker, attacker_army, defender_army,
                   target_pos, intent):
        genome = _genome_for(army_genome_pairs, attacker_army, "pilot_move")
        current_round = getattr(battle, "_current_round", 0)
        cache_key = _squad_cache_key(attacker, attacker_army, current_round)

        # --- kite_hold_range: ranged-dominant unit already in gun range holds
        # its ENGAGE walk while it can keep a stand-off gap. Structural no-op
        # at <= 0.0 (explicit early gate, like the SWEG_KITING opt-in).
        if intent == "ENGAGE" and genome.kite_hold_range > 0.0:
            profile = attacker.profile
            weapon_range = float(profile.range_inches or 0.0)
            if weapon_range > 0.0 and not _scaled_wants_to_charge(
                profile, genome.charge_aggression
            ):
                if cache_key in kite_decisions:
                    should_kite = kite_decisions[cache_key]
                else:
                    members = _squad_members(attacker, attacker_army)
                    centroid = _squad_centroid(members)
                    _, dist = _nearest_enemy_from(centroid, defender_army)
                    clearance = dist - _ENGAGEMENT_RANGE
                    should_kite = (dist <= weapon_range
                                  and clearance >= genome.kite_hold_range)
                    kite_decisions[cache_key] = should_kite
                if should_kite:
                    return attacker.position, "HOLD"

        # --- squad-coordinated walk target. Two regimes:
        #
        # 1. squad_move_as_unit=True (the AI Lab duel default, applied to
        #    BOTH sides regardless of genome): every walk intent (CAPTURE /
        #    STEAL / ENGAGE) is decided once per squad per round — the first
        #    squad member's own baseline pick is shared with the rest, so
        #    the squad moves as one body. This is the harness-level answer
        #    to the user-visible "models wander off on their own" problem:
        #    the calibration simulator's one-Unit-per-model representation
        #    lets a codex squad scatter its models across objectives 20"
        #    apart, which real 10e Unit Coherency (every model within 2" of
        #    a squadmate) flatly forbids — a representation infidelity that
        #    the production post-move coherency nudge cannot fully repair
        #    once a model has spent its whole move walking elsewhere.
        #    CRITICALLY this must be symmetric: an earlier version
        #    coordinated only genomes with active charge-axis genes, which
        #    glued the CHALLENGER's squad onto one objective while the
        #    NEUTRAL baseline stayed free to spread over three or four —
        #    the challenger forfeited the Victory Point race every game and
        #    measured win rates collapsed to roughly 6-10% for genomes less
        #    than 1% away from neutral. Applying the rule to both sides
        #    always makes the duel fair by construction, and the frozen
        #    baseline plays under exactly the same movement discipline as
        #    every challenger.
        #
        # 2. squad_move_as_unit=False (hook-inertness proofs, unit tests):
        #    only ENGAGE is coordinated, and only when a charge-axis gene is
        #    non-neutral — the original, narrower fix for the DUAL branch's
        #    per-model enemy-model pick (verified pre-existing in unmodified
        #    baseline battles with naturally non-charging DUAL units such as
        #    Drukhari Wracks). CAPTURE/STEAL stay per-model in this regime
        #    for the asymmetry reason above. Position-RELATIVE intents
        #    (HOLD / REPOSITION / FALL_BACK) are never coordinated in either
        #    regime — they already return something close to each model's
        #    own position, and forcing one shared absolute point would clump
        #    the squad rather than keep it coherent.
        _charge_axis_active = (
            genome.charge_aggression != 1.0
            or genome.charge_range_buffer != 1.0
            or genome.melee_engage_score_min != 1.0
        )
        if squad_move_as_unit:
            _coordinate_walk = intent in ("CAPTURE", "STEAL", "ENGAGE")
        else:
            _coordinate_walk = intent == "ENGAGE" and _charge_axis_active
        if _coordinate_walk:
            if cache_key in walk_targets:
                shared_target, shared_intent = walk_targets[cache_key]
                if (shared_target, shared_intent) != (target_pos, intent):
                    return shared_target, shared_intent
            else:
                walk_targets[cache_key] = (target_pos, intent)

        # --- advance_vs_hold_bias: nudge a HOLD toward (+) or away from (-)
        # the nearest enemy. Structural no-op at 0.0. Returned as REPOSITION
        # because the move executor short-circuits intent == "HOLD" without
        # moving; the nudge magnitude is capped at THIS model's remaining
        # move so the executor's normal-move path (never Advance) carries it
        # out, and the executor's _move_toward clamp keeps the destination
        # legal — but the DIRECTION is shared across the whole squad (from
        # the squad centroid) so a nudged squad moves as one body.
        if intent == "HOLD" and genome.advance_vs_hold_bias != 0.0:
            if cache_key in advance_directions:
                direction = advance_directions[cache_key]
            else:
                members = _squad_members(attacker, attacker_army)
                centroid = _squad_centroid(members)
                enemy, dist = _nearest_enemy_from(centroid, defender_army)
                direction = None
                if enemy is not None and dist > 1e-9:
                    ex, ey = enemy.position
                    direction = ((ex - centroid[0]) / dist,
                                (ey - centroid[1]) / dist)
                advance_directions[cache_key] = direction
            if direction is not None:
                bias = genome.advance_vs_hold_bias
                step = min(abs(bias), effective_move(attacker))
                if step > 0.0:
                    ax, ay = attacker.position
                    ux, uy = direction
                    sign = 1.0 if bias > 0.0 else -1.0
                    return (ax + ux * step * sign, ay + uy * step * sign), \
                        "REPOSITION"

        return None
    return pilot_move


def attach(battle, genome_a: DuelGenome, genome_b: DuelGenome,
           squad_move_as_unit: bool = True) -> None:
    """Wire genomes onto both sides of a Battle. Call right after Battle(...).

    Both sides ALWAYS get a pilot — there is no special-cased "baseline side
    has no hook" branch to get wrong. The baseline strain is simply whichever
    genome happens to be neutral (epoch 1) or the previously promoted
    champion (later epochs).

    squad_move_as_unit (default True — the AI Lab duel regime): every squad's
    walk intents (CAPTURE / STEAL / ENGAGE) are decided once per squad per
    round and shared across its models, on BOTH sides symmetrically, so
    squads move as one body — closer to real 10e Unit Coherency than the
    calibration simulator's per-model walks. Pass False to run the hooks in
    their strictly-inert-at-neutral regime: with squad_move_as_unit=False
    and NEUTRAL_GENOME on both sides, the battle is proven byte-identical to
    an unhooked one (the hook-inertness contract the sandbox rests on).
    With the flag True the duel deliberately diverges from raw production
    behaviour — identically for both sides.
    """
    _guard_squadact()
    army_genome_pairs = ((battle.a, genome_a), (battle.b, genome_b))
    battle._pilot_charge = _make_pilot_charge(army_genome_pairs)
    battle._pilot_move = _make_pilot_move(
        army_genome_pairs, squad_move_as_unit=squad_move_as_unit)
    for army, genome in ((battle.a, genome_a), (battle.b, genome_b)):
        scales = (genome.charge_range_buffer, genome.melee_engage_score_min)
        if scales != (1.0, 1.0):
            army._ai_lab_dual_scales = scales
        elif hasattr(army, "_ai_lab_dual_scales"):
            # Defensive: never leave a stale scale on a reused Army object.
            del army._ai_lab_dual_scales
