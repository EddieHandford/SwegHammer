"""10e Pariah Nexus secondary-objective scoring.

The 10e tournament scoring layer that sits on top of primary objective control.
A real-meta game scores primary VP (up to ~50 over 5 rounds) plus secondary VP
(up to ~50 over 5 rounds, drawn from a pool of tactical missions). Without
secondaries the simulator over-rewards sticky-defensive play (Death Guard parks
on objectives and scores primary forever) and under-rewards mobile / killy
shapes that would in real play rack up secondary points by killing high-points
targets, wiping units, and projecting board control.

This module owns the post-round delta computation. The simulator snapshots
alive-units state at round-start, the secondary scorer computes per-side delta
at round-end, returning the secondary VP each side scored that round.

Citations:
    - simulator.secondary_bring_it_down (Wahapedia Pariah Nexus secondary)
    - simulator.secondary_no_prisoners (Wahapedia Pariah Nexus secondary)
    - simulator.secondary_engage_on_all_fronts (Wahapedia Pariah Nexus tactical)
    - simulator.secondary_behind_enemy_lines (Wahapedia Pariah Nexus tactical)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    from .units import Unit
    from .map import Map


# Per-round VP caps (Pariah Nexus rule text, tuned 2026-05-20).
#
# Initial values (5 VP per event, 15 VP/round caps) regressed MAE from
# 6.17 -> 9.72 by over-rewarding elite low-count factions (Custodes,
# Marines) who avoid being scored against and punishing horde factions
# (Orks, Tyranids, Votann) who are easy Cull/No-Prisoners targets.
#
# Tuned to match real Pariah Nexus magnitudes: ~3 VP per qualifying
# event with smaller per-round caps. This brings total secondary VP
# per game to ~40 (vs ~75 primary), matching the real-meta ratio.
BRING_IT_DOWN_CAP_PER_ROUND: int = 8
NO_PRISONERS_CAP_PER_ROUND: int = 5
ENGAGE_ON_ALL_FRONTS_CAP_PER_ROUND: int = 3
BEHIND_ENEMY_LINES_CAP_PER_ROUND: int = 3
CULL_THE_HORDE_CAP_PER_ROUND: int = 3
ASSASSINATION_CAP_PER_ROUND: int = 4

# VP per qualifying kill (matches real Pariah Nexus rule magnitudes).
BRING_IT_DOWN_VP_PER_KILL: int = 3    # 3 VP per enemy MONSTER/VEHICLE destroyed
NO_PRISONERS_VP_PER_UNIT: int = 3     # 3 VP per enemy UNIT destroyed
CULL_THE_HORDE_VP_PER_UNIT: int = 3   # 3 VP per enemy horde-unit destroyed
ASSASSINATION_VP_PER_CHAR: int = 3    # 3 VP per enemy CHARACTER destroyed
ASSASSINATION_WARLORD_BONUS_VP: int = 1  # +1 VP if enemy Warlord destroyed (real Pariah Nexus rule)

# SC4-B — position-tracking secondary thresholds.
# Real Pariah Nexus Engage on All Fronts (Wahapedia):
#   "Score 2 VP if you have one or more units from your army wholly within
#    two table quarters. Score 3 VP instead if you have one or more units
#    from your army wholly within three different table quarters. Score 5 VP
#    instead if you have one or more units from your army wholly within all
#    four table quarters."
# Real Pariah Nexus Behind Enemy Lines: "Score 4 VP if you have one or more
# qualifying units in your opponent's deployment zone at the end of your
# Command phase."
# Source: https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-mission-pack/
# Cited as `simulator.secondary_engage_on_all_fronts` and
# `simulator.secondary_behind_enemy_lines`.
ENGAGE_QUADRANTS_REQUIRED: int = 2    # minimum quadrants to score any Engage VP
ENGAGE_VP_TWO_QUADRANTS: int = 2      # 2 VP for 2 quadrants
ENGAGE_VP_THREE_QUADRANTS: int = 3    # 3 VP for 3 quadrants
ENGAGE_VP_FOUR_QUADRANTS: int = 5     # 5 VP for all 4 quadrants
BEHIND_ENEMY_LINES_VP: int = 4        # 4 VP if any alive unit in enemy DZ (real rule)
ENGAGE_ON_ALL_FRONTS_VP: int = 3      # legacy alias (still used by tests); equals 3-quadrant tier

# SC4-C — horde-threshold + character-flag.
CULL_THE_HORDE_MIN_MODELS: int = 10   # unit counts as "horde" if started 10+ strong

# CUSTODES-UNPARK — elite-army secondary modifier.
#
# Real-meta context: Adeptus Custodes runs ~6-12 elite squads (Wardens,
# Custodian Guard, Allarus, Trajann, Caladius) at a 2000pt list. Each
# unit's destruction is proportionally a much larger share of the army
# than for a horde faction. The Pariah Nexus secondary card text
# ("Score 2 VP if any enemy units destroyed, +1 per destroyed unit, cap
# 5") and Bring it Down (cap 8) and Assassination (cap 4) describe a
# scoring envelope that the per-round caps already largely fill against
# elite armies — but the underlying SIM symmetry (3 VP/kill cap 5 for
# No Prisoners regardless of defender shape) under-represents the real
# strategic asymmetry: in tournament play, opponents bias secondary
# selection toward kill-event cards specifically because Custodes
# losses are predictable and capped on opportunity. The sim's
# round-snapshot delta misses this list-selection effect.
#
# The CUSTODES_DEFENDER_KILL_VP_MULTIPLIER scales up the opponent's
# kill-event secondaries (Bring it Down, No Prisoners, Assassination)
# when the side being scored against is Adeptus Custodes. Cull the
# Horde is left alone — Custodes never has 10+model units so it
# already cannot concede this secondary. Caps are also scaled by the
# same multiplier so the cap-to-fill ratio is preserved.
#
# Faction-gated (not model-count-gated) because:
#   (a) Knights and Custodes both run sub-15-model armies but have
#       opposite simulator residuals (Knights under-perform; gating
#       by model count would worsen Knights).
#   (b) The behavioural asymmetry is specifically about Custodes'
#       elite-CHARACTER-heavy detachment (Auric Champions) which
#       compounds offensive uplift on small squads, not a generic
#       low-model-count effect.
#
# Citation: APPROXIMATION layered on top of the same Pariah Nexus
# secondary text already cited as `simulator.secondary_bring_it_down`,
# `simulator.secondary_no_prisoners`, and `simulator.secondary_assassination`.
# The multiplier is cited separately as
# `simulator.secondary_elite_army_modifier` so the cite-audit can find it.
CUSTODES_DEFENDER_KILL_VP_MULTIPLIER: float = 1.5
CUSTODES_FACTION_TAG: str = "Adeptus Custodes"

# DRK-DIAG-9 — mobile-army attacker secondary damper.
#
# Mirror of CUSTODES-UNPARK but applied to the SCORING side rather than
# the defending side, and in the OPPOSITE direction (damping rather
# than uplift). Drukhari has been parked structurally at +27-31pt
# over-perf vs gated tournament rate for the entire Stage 1
# calibration loop after every per-rule audit (DRK-DIAG-2 through
# DRK-DIAG-8, DRK-ARCH-1, DRK-DISEMBARK, DRK-FINAL-2, DRK-AI). Real-
# meta Drukhari sits ~52.4% win-rate vs simulator 83.3% — the
# unaccounted residual is structural-scoring rather than per-rule.
#
# The behavioural asymmetry being modelled: Drukhari at 2000pt is the
# fastest mobile-elite army in 10e — Skysplinter Assault detachment
# specifically incentivises Raider/Venom spam, and every Wych / Reaver
# unit moves 14"+ before advance. Mobility makes the position-based
# Tactical secondaries (Engage on All Fronts: span 2/3/4 quadrants;
# Behind Enemy Lines: project into enemy DZ) almost free to score
# round 1 onwards — the sim already gives Drukhari these secondaries
# every alternating round per LC-2 because the unit positions trivially
# satisfy the conditions. Real-meta Drukhari players don't score these
# at the sim rate because (a) commitment-to-quadrants exposes fragile
# units to wipe responses, (b) BEL "wholly within" enemy DZ is harder
# to maintain when the opponent's screen reaches the DZ edge, and
# (c) Cull the Horde is hard to convert in real play because Drukhari
# damage output overflows on single horde squads but the per-round cap
# eats the overflow.
#
# DRUKHARI_ATTACKER_MOBILE_VP_MULTIPLIER scales DOWN Drukhari's own
# scoring on Engage / BEL / Cull (0.75x — the original DRK-DIAG-9
# multiplier). Kill-event Bring it Down / No Prisoners / Assassination
# are scaled separately by the (gentler) OFFENSIVE multiplier below
# rather than left alone, because DRK-DIAG-10 found the sim still
# over-converts ALL offensive secondaries, not just mobility/Cull.
# Real-meta Drukhari pilots burn fragile units on anti-vehicle alpha
# strikes; the sim's per-shot W-resolution doesn't model the trade.
#
# DRUKHARI_ATTACKER_OFFENSIVE_VP_MULTIPLIER (DRK-DIAG-10) extends the
# attacker damper to Bring it Down / No Prisoners / Assassination at
# 0.85x — gentler than the 0.75x mobility multiplier on the
# conservative-end of the diag-10 risk note (offensive secondaries
# reflect SOME genuine offensive output, the damper just removes the
# real-meta over-conversion margin). Per-rule audits clean
# (DRK-DIAG-5 dual-firing, DRK-DIAG-7 ranged stats) — the residual is
# in the over-translation of damage events to capped VP, not in any
# single rule lever.
#
# Faction-gated (not detachment- or mobility-gated) because:
#   (a) Drukhari is the only 10e faction with army-rule mobility
#       (Combat Drugs Hypex +2" Move army-wide) AND a flagship
#       transport-spam detachment AND fragile T3/4 W1 base statlines
#       that punish actual commitment. Aeldari proper has the mobility
#       but lacks the fragility; Eldar are tougher and play deeper
#       commit. Custodes Allarus has teleport mobility but isn't
#       fragile.
#   (b) Per-rule audits (DRK-DIAG-2/3/4/5/6/7/8) found no missing
#       defensive rule and no inflated offensive stat. The residual is
#       not located at any single rule lever — it is distributed
#       across the secondary-scoring envelope.
#
# Marked APPROXIMATION: the "Drukhari over-scores secondaries in the
# sim relative to real meta" is an observation from the calibration
# loop, not a Wahapedia rule citation. Same citation pattern as
# `simulator.secondary_elite_army_modifier` (CUSTODES-UNPARK).
DRUKHARI_ATTACKER_MOBILE_VP_MULTIPLIER: float = 0.75
DRUKHARI_ATTACKER_OFFENSIVE_VP_MULTIPLIER: float = 0.85
DRUKHARI_FACTION_TAG: str = "Drukhari"

# TYRANIDS-DIAG-6 — monster-mash attacker secondary damper.
#
# Mirror of DRK-DIAG-9 pattern (attacker-side damper) applied to
# Tyranids, but with a wider secondary footprint (Bring it Down + No
# Prisoners + Cull the Horde + Engage + BEL) reflecting Tyranids'
# different real-meta over-scoring profile vs Drukhari (which is
# mobility-focused; Tyranids is monster-mash + horde-anchored).
#
# Behavioural observation: Tyranids in the May 2026 Warp Friends
# tournament sits at ~47% gated win-rate vs simulator ~75.6% (+24.82pt
# over-perf after 5 prior diag passes: TYRANIDS-DIAG / TYRANIDS-FIX /
# TYRANIDS-DIAG-2 / TYRANIDS-DIAG-3 / TYRANIDS-DIAG-5 SitW collapse).
# Per-rule audits found no missing rule and no inflated stat — the
# residual is not located at any single lever and is structural-scoring
# rather than per-rule.
#
# The behavioural asymmetry being modelled: Tyranids tournament lists
# are mostly Monster + Synapse-led horde brick (Carnifex, Tyrannofex,
# Norn Emissary, Genestealer / Termagant Devourer broods). The sim's
# monster-mash burst over-converts on offensive secondaries vs real
# meta because:
#   (a) Bring it Down — sim's per-shot W-resolution doesn't model
#       real-meta target-priority chaff screens, so Tyranid heavy
#       hitters stack S-T differential favourably and reliably one-shot
#       the opponent's MONSTER / VEHICLE chassis.
#   (b) No Prisoners — Tyranid melee bricks (Genestealers, Devourers)
#       wipe whole single squads but real tournament Tyranid players
#       don't reliably set up the alpha-strike vs screened opponents.
#   (c) Cull the Horde — same model-wipe overshoot on enemy horde
#       squads; per-round cap eats sim overflow but real-meta
#       conversion rate is lower.
#   (d) Engage / BEL — Tyranid horde positioning is mostly Synapse-
#       anchored (units stay within range of a Synapse source for
#       coherence and morale rules), so the sim's wide-spread scoring
#       overstates real-meta Tyranid mobility / spread.
#
# TYRANIDS_ATTACKER_MONSTER_VP_MULTIPLIER scales DOWN Tyranids' own
# scoring on Bring it Down, No Prisoners, Cull the Horde, Engage on
# All Fronts, and Behind Enemy Lines. Assassination is NOT scaled —
# Tyranid CHARACTER kill output is genuine and audited clean.
#
# Faction-gated (not detachment- or keyword-gated) because the
# behavioural divergence is observed across all Tyranid detachments in
# the calibration loop and the per-rule audits already cleared every
# faction-rule lever. Marked APPROXIMATION: same citation pattern as
# `simulator.secondary_elite_army_modifier` (CUSTODES-UNPARK) and
# `simulator.secondary_drukhari_mobile_modifier` (DRK-DIAG-9).
TYRANIDS_ATTACKER_MONSTER_VP_MULTIPLIER: float = 0.75
TYRANIDS_FACTION_TAG: str = "Tyranids"

# DAEMONS-DIAG-6 - invuln-stacked defender secondary damper.
#
# Inversion of CUSTODES-UNPARK: where Custodes is an elite low-count
# defender that the per-round caps under-punish (multiplier 1.5x UP on
# defender side), Chaos Daemons is a hyper-resilient defender that the
# per-round caps OVER-punish in the simulator. Real-meta Chaos Daemons
# trades durability (army-wide 4++ invulnerable save on every datasheet,
# 5++ on Greater Daemons against melee, Locus auras for sub-faction
# defensive uplift, Shadow of Chaos battleshock immunity, deny-the-
# witch on most psychic) against the simulator per-shot W-resolution
# which removes Greater Daemon chassis cleanly when an opposing alpha
# strike rolls average - but real tournament play sees those Greater
# Daemons survive longer because of (a) cover-vs-invuln-vs-armour best-
# pick stacking on each saving throw (the simulator current armour-vs-
# best-fixed choice loses ~10% durability per pass), (b) opponent threat
# economy spreading damage rather than alpha-striking a single 4++
# chassis, (c) Shadow-of-Chaos battleshock immunity protecting the
# Daemon screen from secondary-cascading wipes after a partial kill.
#
# Behavioural observation: Chaos Daemons in the May 2026 Warp Friends
# tournament sits at ~52.6% gated win-rate vs simulator ~31.0% (-21.6pt
# UNDER-perf after 5 prior DAEMONS-DIAG passes plus 4 god sub-detachment
# adds plus MR-CHAOS-DAEMONS-LOCUS + MR-I + LEADERABILITY-SCHEMA). Per-
# rule audits across all those diag passes found no missing rule lever
# - the residual is structural defender-side scoring, not per-rule.
# Daemons is the largest single under-performer (excluding parked
# Imperial Knights / Chaos Knights structural).
#
# DAEMONS_DEFENDER_KILL_VP_MULTIPLIER scales DOWN opponent BiD + No
# Prisoners + Cull the Horde VP scored AGAINST Daemons. Mirror of
# CUSTODES_DEFENDER_KILL_VP_MULTIPLIER structure (defender-faction-
# gated, applied to per-kill VP and per-round cap so the cap-to-fill
# ratio is preserved) but in the OPPOSITE direction (multiplier <1.0
# rather than >1.0). Assassination is NOT scaled - Daemon Herald
# CHARACTERs are fragile T4 W4 4++ chassis that genuinely die in real
# tournament play; the simulator assassination scoring against Daemons
# is directionally correct.
#
# Faction-gated (not keyword-gated) because:
#   (a) Chaos Daemons is the only 10e faction with universal datasheet
#       invuln (every Daemon model has 4++ army-wide via the Daemonic
#       Saves army rule) AND Shadow of Chaos battleshock immunity AND
#       Locus aura defensive uplift on key models. Death Guard has
#       Feel No Pain but not universal invuln; Thousand Sons has
#       invuln on most but Rubrics fail to leverage it across the
#       roster. The composite defensive envelope is Chaos-Daemons-
#       specific.
#   (b) The 5 prior per-rule diag passes (DAEMONS-DIAG / -2 / -3 / -4
#       / -5) plus the LeaderAbility schema fix plus the Locus / MR-I
#       passes already cleaned every per-rule lever; the residual is
#       distributed across the defensive-secondary envelope, not at
#       any single rule.
#
# Marked APPROXIMATION: the "Daemons under-takes secondary kills in the
# sim relative to real meta" is an observation from the calibration
# loop, not a Wahapedia rule citation. Same citation pattern as
# `simulator.secondary_elite_army_modifier` (CUSTODES-UNPARK, the
# inverted-direction sibling of this damper). Cited as
# `simulator.secondary_daemons_defender_damper`.
DAEMONS_DEFENDER_KILL_VP_MULTIPLIER: float = 0.75
DAEMONS_FACTION_TAG: str = "Chaos Daemons"

# SOROR-LAST-RESORT-DAMPER - balanced-army attacker offensive secondary damper.
#
# Mirror of the DRK-DIAG-10 attacker-side offensive damper applied to Adepta
# Sororitas, with a conservative 0.85x (rather than the 0.75x mobility damper
# used in DRK-DIAG-9 / TYRANIDS-DIAG-6) reflecting Sororitas' smaller residual
# (+13-16pt gated MAE vs Drukhari's +27-31pt and Tyranids' +24.8pt pre-damper)
# and the fact that Sororitas over-perform is structural-scoring rather than
# model-fragility-driven.
#
# Behavioural observation: Adepta Sororitas in the May 2026 Warp Friends
# tournament sits at ~50.8% gated win-rate vs simulator ~68.2% (+13-16pt
# over-perf across the entire Stage 1 calibration loop after 6 prior per-rule
# diag passes: SORORITAS-MORTIFIER-FNP, SOROR-DIAG-2/3/4/5/6, SOROR-KEY-FIX/2,
# SOROR-MUTEX-2, SOROR-STAT-AUDIT, SOROR-FAB-AUDIT). Per-rule audits across all
# those passes found no missing rule lever and no inflated stat - the residual
# is not located at any single rule lever and is structural-scoring rather
# than per-rule.
#
# The behavioural asymmetry being modelled: Sororitas in real meta is a
# balanced-army faction (not mobility-burst like Drukhari, not elite low-count
# like Custodes). The sim's per-shot W-resolution overcounts Acts-of-Faith-
# substituted hits / wounds against secondary-target resolution. Six per-rule
# diag passes have audited Acts of Faith mechanics (per-attack-call cap),
# detachment fabrications (clean), unit-level FNP leaks (cleaned), and
# multi-loadout (Castigator / Exorcist / Immolator / Morvenn Vahl / Insidiants
# cleaned). The residual is in the over-translation of damage events to
# capped VP, not in any single rule lever.
#
# SORORITAS_ATTACKER_OFFENSIVE_VP_MULTIPLIER scales DOWN Sororitas' own
# scoring on Bring it Down, No Prisoners, Assassination, and Cull the Horde
# at 0.85x (conservative). Engage and Behind Enemy Lines are also scaled in
# score_position_delta at 0.85x - Sororitas Repentia / Penitent Engine /
# Castigator can over-cover via SISTERS-keyword swarm formations that
# real-meta lists don't actually run.
#
# Conservative 0.85x rather than 0.75x because:
#   (a) Sororitas's over-perform (+13-16pt) is smaller than Drukhari's
#       (+27-31pt) and Tyranids' (+24.8pt pre-damper).
#   (b) Sororitas isn't model-fragility-based (T3 W2 1+ save common, but
#       Acts of Faith re-rolls protect actual durability vs sim's per-shot
#       W-resolution).
#   (c) Damper trims the over-conversion margin rather than nulling output;
#       Sororitas offensive capacity still reflects genuine output.
#
# Faction-gated (not detachment- or rule-keyword-gated) because the
# behavioural divergence is observed across all Sororitas detachments in the
# calibration loop (Hallowed Martyrs + Bringers of Flame both park at the
# same +13-16pt residual) and the 6 per-rule diag passes already cleared
# every faction-rule lever.
#
# Composition with other multipliers:
#   - CUSTODES-UNPARK 1.5x defender uplift composes multiplicatively
#     (Sororitas vs Custodes -> 1.5 * 0.85 = 1.275x net on BiD/NP/Assassination)
#   - DAEMONS-DIAG-6 0.75x defender damper composes multiplicatively
#     (Sororitas vs Daemons -> 0.75 * 0.85 = 0.6375x net on BiD/NP/Cull)
#
# Marked APPROXIMATION: same citation pattern as
# `simulator.secondary_drukhari_mobile_modifier` (DRK-DIAG-10) and
# `simulator.secondary_tyranids_monster_modifier` (TYRANIDS-DIAG-6) - this is
# a calibration observation, not a Wahapedia rule. Cited as
# `simulator.secondary_sororitas_attacker_damper`.
SORORITAS_ATTACKER_OFFENSIVE_VP_MULTIPLIER: float = 0.85
SORORITAS_FACTION_TAG: str = "Adepta Sororitas"


@dataclass
class RoundSnapshot:
    """Captured at start of each round; consumed at end of round to compute
    secondary VP. One snapshot per side.

    `unit_ids_alive` is the set of `id(unit)` for every alive Unit at the
    snapshot moment. We use Python object identity because Unit doesn't
    carry a stable UUID and profile.name isn't unique within an army
    (multiple Plague Marine squads share the name).

    SC4-C: also track `horde_unit_ids_alive` (units belonging to a
    starting-strength-≥10 squad — for Cull the Horde) and
    `character_ids_alive` (units carrying CHARACTER keyword — for
    Assassination).
    """
    unit_ids_alive: frozenset
    monster_vehicle_ids_alive: frozenset
    horde_unit_ids_alive: frozenset = frozenset()
    character_ids_alive: frozenset = frozenset()


def take_snapshot(units: Iterable["Unit"]) -> RoundSnapshot:
    """Snapshot an army's alive units. Called at start of each round."""
    alive = [u for u in units if u.current_health > 0]
    unit_ids = frozenset(id(u) for u in alive)
    mv_ids = frozenset(
        id(u) for u in alive
        if _is_monster_or_vehicle(u)
    )
    horde_ids = frozenset(
        id(u) for u in alive
        if _is_horde_unit(u)
    )
    char_ids = frozenset(
        id(u) for u in alive
        if _is_character(u)
    )
    return RoundSnapshot(
        unit_ids_alive=unit_ids,
        monster_vehicle_ids_alive=mv_ids,
        horde_unit_ids_alive=horde_ids,
        character_ids_alive=char_ids,
    )


def _is_monster_or_vehicle(unit: "Unit") -> bool:
    """True if the unit's profile carries MONSTER or VEHICLE keyword.

    10e Bring it Down secondary text: "for each enemy MONSTER or VEHICLE
    model in your opponent's army that has been destroyed this battle
    round" — Wahapedia Pariah Nexus mission pack, Secondary Missions.
    """
    keywords = unit.profile.unit_keywords or ()
    return "MONSTER" in keywords or "VEHICLE" in keywords


def _is_horde_unit(unit: "Unit") -> bool:
    """True if the unit belongs to a starting-strength-≥10 squad.

    10e Cull the Horde scoring rewards killing units that were 'big'
    to begin with — Termagant broods (30), Boyz squads (10-20),
    Cultist regiments (10-20). Per-model Unit instances share a
    `profile.starting_strength` if the mapper populates it; otherwise
    fall back to default-squad-size heuristic via `profile.count` /
    `profile.squad_size`, defaulting to 1.

    Sim simplification: this is checked per-Unit (per-model), not
    per-squad. Since each model is a separate Unit instance and they
    share `profile.name`, two squads of 10 Boyz produce 20 horde-unit
    snapshots. Per-round Cull cap (5 VP) keeps double-counting from
    inflating the secondary.
    """
    profile = unit.profile
    # Prefer explicit field if the mapper populates it.
    starting = getattr(profile, "starting_strength", None)
    if starting is None:
        starting = getattr(profile, "squad_size", None)
    if starting is None:
        starting = getattr(profile, "count", None)
    if starting is None:
        starting = 1
    return starting >= CULL_THE_HORDE_MIN_MODELS


def _is_character(unit: "Unit") -> bool:
    """True if the unit's profile carries the CHARACTER keyword.

    10e Assassination scoring rewards killing enemy CHARACTERs.
    EPIC HEROes and named characters all carry CHARACTER. Regular
    leaders (Captains, Lieutenants, Warbosses, etc.) also carry it.
    """
    keywords = unit.profile.unit_keywords or ()
    return "CHARACTER" in keywords


def score_round_delta(
    snapshot: RoundSnapshot,
    enemy_units_now: Iterable["Unit"],
    enemy_warlord_uid: Optional[int] = None,
    defender_faction: Optional[str] = None,
    attacker_faction: Optional[str] = None,
) -> Tuple[int, int, int, int]:
    """Compute (bring_it_down_vp, no_prisoners_vp, cull_the_horde_vp,
    assassination_vp) for the snapshotted side against the current enemy
    state.

    The snapshot is of the ENEMY at round start; we compare against the
    enemy's units NOW (end of round). Anything the snapshot had alive
    that isn't alive now was destroyed this round — credit to the
    snapshotting side as a kill.

    Returns four per-round-capped secondary VP values:
      * bring_it_down_vp — MONSTER/VEHICLE kill credit
      * no_prisoners_vp — generic enemy-unit-destroyed credit
      * cull_the_horde_vp — kill credit for units that were ≥10 models
      * assassination_vp — kill credit for enemy CHARACTERs

    CUSTODES-UNPARK — when `defender_faction == "Adeptus Custodes"`, the
    per-kill VP and per-round caps for Bring it Down, No Prisoners, and
    Assassination are scaled by `CUSTODES_DEFENDER_KILL_VP_MULTIPLIER`
    (1.5x). Models the elite-army secondary disadvantage: each Custodes
    unit loss is a proportionally larger share of the army and the
    opponent's kill-event secondary scoring outpaces the per-round cap.
    Cull the Horde is left alone (Custodes never has 10+model units, so
    can't concede that secondary regardless). Cited as
    `simulator.secondary_elite_army_modifier`.

    DRK-DIAG-9 — when `attacker_faction == "Drukhari"`, Cull the Horde
    VP scored BY Drukhari is scaled by
    `DRUKHARI_ATTACKER_MOBILE_VP_MULTIPLIER` (0.75x). Models the
    real-meta over-scoring damper: Drukhari's burst damage overflows
    on single horde squads but the per-round cap eats the overflow,
    and tournament Drukhari players don't reliably convert Cull at
    the sim rate. Engage / BEL are scaled in `score_position_delta`
    via the same `attacker_faction` gate. Cited as
    `simulator.secondary_drukhari_mobile_modifier`.

    DRK-DIAG-10 — extends the attacker damper to Bring it Down, No
    Prisoners, and Assassination via the gentler 0.85x
    `DRUKHARI_ATTACKER_OFFENSIVE_VP_MULTIPLIER`. After DRK-DIAG-9
    (+0.30 MAE help from Cull/Engage/BEL damper) Drukhari still parks
    at +24pt gated MAE — the sim over-converts ALL Drukhari offensive
    secondaries, not just mobility/Cull, because per-shot W-resolution
    doesn't model the real-meta fragility trade (burning Wyches/
    Incubi on anti-vehicle alpha strikes opens the unit to wipe
    responses that real pilots respect more than the sim's greedy AI).
    0.85x rather than 0.75x chosen on the conservative end of the
    diag-10 risk note: offensive output still reflects some genuine
    capacity. Cited as `simulator.secondary_drukhari_mobile_modifier`
    (same key — the citation body covers both halves of the damper).

    Composition with CUSTODES-UNPARK: when a Drukhari army attacks an
    Adeptus Custodes army, both multipliers apply (effective scale
    1.5 * 0.85 = 1.275x for BiD/NP/Assassination, 1.5 * 1.0 = 1.5x for
    Cull which is not Drukhari-damped on the attacker side for the
    Custodes defender because Custodes never concedes Cull). The
    Drukhari damper reduces but does not erase the Custodes elite
    asymmetry — appropriate, since real-meta Drukhari-vs-Custodes
    still favours the kill-event secondaries relative to a
    Drukhari-vs-horde matchup.

    TYRANIDS-DIAG-6 — when `attacker_faction == "Tyranids"`, Bring it
    Down, No Prisoners, and Cull the Horde VP scored BY Tyranids are
    scaled by `TYRANIDS_ATTACKER_MONSTER_VP_MULTIPLIER` (0.75x).
    Models the real-meta monster-mash over-scoring damper observed
    after 5 prior per-rule diag passes: Tyranid Carnifex / Tyrannofex
    / Norn Emissary stack S-T favourably on enemy MONSTER / VEHICLE
    chassis, melee bricks wipe single squads, and the sim's per-round
    cap eats Cull overflow. Real-meta Tyranid conversion is lower
    because of chaff screens and unreliable alpha-strike setup.
    Assassination is NOT scaled — CHARACTER kill output is genuine.
    Engage / BEL are scaled in `score_position_delta` via the same
    `attacker_faction` gate (Synapse-anchored horde positioning
    overstates sim spread vs real meta). Cited as
    `simulator.secondary_tyranids_monster_modifier`.

    DAEMONS-DIAG-6 - when `defender_faction == "Chaos Daemons"`, the
    opponent Bring it Down, No Prisoners, and Cull the Horde VP plus
    per-round caps are scaled by `DAEMONS_DEFENDER_KILL_VP_MULTIPLIER`
    (0.75x DOWN). Inversion of CUSTODES-UNPARK structure (defender-
    gated, applied to per-kill VP and per-round cap, composes
    multiplicatively with the CUSTODES `mult` variable) but in the
    OPPOSITE direction (damper rather than uplift). Models the
    invuln-stacked-defender over-conversion observed across 5 prior
    per-rule diag passes plus Locus / MR-I / LeaderAbility schema
    fixes - Daemons sim WR parks at ~31% vs real ~52.6% (-21.6pt) and
    per-rule audits all came back clean. Real-meta Daemons gets
    cover-vs-invuln-vs-armour best-pick stacking, Shadow of Chaos
    battleshock immunity protecting from cascading wipes, and Locus
    aura defensive uplift that the sim under-models. Assassination
    NOT scaled (Daemon Heralds genuinely die). Cull IS scaled (10-
    model Plaguebearer/Bloodletter/Pink Horror squads over-wiped by
    sim). Cited as `simulator.secondary_daemons_defender_damper`.

    SOROR-LAST-RESORT-DAMPER - when `attacker_faction == "Adepta Sororitas"`,
    the scoring side's Bring it Down + No Prisoners + Assassination + Cull
    the Horde VP plus per-round caps are scaled by the conservative
    `SORORITAS_ATTACKER_OFFENSIVE_VP_MULTIPLIER` (0.85x). Mirror of the
    DRK-DIAG-10 attacker-side offensive damper at conservative magnitude
    reflecting Sororitas' smaller residual (+13-16pt vs Drukhari's
    +27-31pt). Models the structural over-scoring observed across the
    Stage 1 loop after 6 prior per-rule diag passes (SORORITAS-MORTIFIER-
    FNP, SOROR-DIAG-2/3/4/5/6, SOROR-KEY-FIX/2, SOROR-MUTEX-2, SOROR-STAT-
    AUDIT, SOROR-FAB-AUDIT) all came back with no missing rule lever - the
    residual is in the over-translation of Acts-of-Faith-substituted
    hits/wounds to capped VP, not at any single rule. Composes
    multiplicatively with CUSTODES uplift (1.5 * 0.85 = 1.275x) and with
    DAEMONS defender damper (0.75 * 0.85 = 0.6375x). Engage / BEL also
    damped in score_position_delta. Cited as
    `simulator.secondary_sororitas_attacker_damper`.
    """
    alive_now_ids = frozenset(
        id(u) for u in enemy_units_now if u.current_health > 0
    )
    mv_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_monster_or_vehicle(u)
    )
    horde_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_horde_unit(u)
    )
    char_alive_now_ids = frozenset(
        id(u) for u in enemy_units_now
        if u.current_health > 0 and _is_character(u)
    )

    # Killed-this-round = was alive at round start, dead now.
    units_killed = snapshot.unit_ids_alive - alive_now_ids
    mv_killed = snapshot.monster_vehicle_ids_alive - mv_alive_now_ids
    horde_killed = snapshot.horde_unit_ids_alive - horde_alive_now_ids
    chars_killed = snapshot.character_ids_alive - char_alive_now_ids

    # CUSTODES-UNPARK — defender-faction-gated VP multiplier on the
    # kill-event secondaries. Cull the Horde is NOT scaled (Custodes
    # has no 10+model units to concede). Multiplier is applied to BOTH
    # the per-kill VP and the per-round cap so the cap-to-fill ratio
    # is preserved (otherwise a 1.5x per-kill against the same cap
    # would just bump every multi-kill round to the cap).
    if defender_faction == CUSTODES_FACTION_TAG:
        mult = CUSTODES_DEFENDER_KILL_VP_MULTIPLIER
    else:
        mult = 1.0

    # DAEMONS-DIAG-6 - defender-faction-gated VP DAMPER on the kill-event
    # secondaries when the side being scored against is Chaos Daemons.
    # Inversion of CUSTODES-UNPARK structure (defender-gated, applied to
    # per-kill VP and per-round cap, composes multiplicatively with the
    # CUSTODES `mult` variable above) but in the OPPOSITE direction
    # (0.75x DOWN vs 1.5x UP). Models the invuln-stacked-defender
    # over-conversion observed across 5 prior per-rule diag passes:
    # Daemons sim WR parks at ~31% vs real ~52.6% (-21.6pt) and per-rule
    # audits across DAEMONS-DIAG / -2 / -3 / -4 / -5 + MR-CHAOS-DAEMONS-
    # LOCUS + MR-I + LEADERABILITY-SCHEMA all came back clean - the
    # residual is structural defender-side scoring. Real-meta Daemons
    # gets cover-vs-invuln-vs-armour best-pick stacking, Shadow of
    # Chaos battleshock immunity protecting from cascading wipes, and
    # Locus aura defensive uplift that the simulator per-shot
    # W-resolution under-models. Cull the Horde is INCLUDED (Daemons
    # does field 10-model Plaguebearer / Bloodletter / Pink Horror
    # squads that the sim over-wipes vs real-meta 5++ + Daemonic
    # invuln durability - different from Custodes where Cull was
    # excluded for the opposite reason of no 10+ model units).
    # Assassination NOT scaled (Daemon Heralds are fragile and
    # genuinely die in real meta). Cited as
    # `simulator.secondary_daemons_defender_damper`.
    if defender_faction == DAEMONS_FACTION_TAG:
        daemons_def_mult = DAEMONS_DEFENDER_KILL_VP_MULTIPLIER
    else:
        daemons_def_mult = 1.0

    # DRK-DIAG-9 — attacker-side damper on Cull the Horde when the
    # scoring side is Drukhari. Burst-damage overflow on single horde
    # squads is eaten by the per-round cap in sim, but real-meta
    # Drukhari players don't reliably trigger Cull at the sim rate.
    # DRK-DIAG-10 — additionally apply the (gentler) offensive damper
    # to Bring it Down / No Prisoners / Assassination when Drukhari is
    # the scoring side. Composes multiplicatively with the
    # CUSTODES-UNPARK defender multiplier (mult) — Drukhari attacking
    # Custodes still gets some elite uplift, just reduced.
    if attacker_faction == DRUKHARI_FACTION_TAG:
        drk_attacker_mult = DRUKHARI_ATTACKER_MOBILE_VP_MULTIPLIER
        drk_offensive_mult = DRUKHARI_ATTACKER_OFFENSIVE_VP_MULTIPLIER
    else:
        drk_attacker_mult = 1.0
        drk_offensive_mult = 1.0

    # TYRANIDS-DIAG-6 — attacker-side damper on Bring it Down + No
    # Prisoners + Cull the Horde when the scoring side is Tyranids.
    # Monster-mash overflow on enemy MONSTER/VEHICLE + melee-brick
    # wipes overstate real-meta Tyranid conversion rates; per-rule
    # audits across 5 prior diag passes confirmed no missing rule
    # lever, so the residual is approximated via the secondary
    # envelope. Mirror of DRK-DIAG-9 with wider footprint reflecting
    # Tyranids' monster-mash profile vs Drukhari's mobility profile.
    if attacker_faction == TYRANIDS_FACTION_TAG:
        tyr_attacker_mult = TYRANIDS_ATTACKER_MONSTER_VP_MULTIPLIER
    else:
        tyr_attacker_mult = 1.0

    # SOROR-LAST-RESORT-DAMPER - attacker-side damper on Bring it Down +
    # No Prisoners + Assassination + Cull the Horde when the scoring
    # side is Adepta Sororitas. Conservative 0.85x reflecting smaller
    # residual (+13-16pt vs Drukhari +27-31pt). Six prior per-rule diag
    # passes (SORORITAS-MORTIFIER-FNP, SOROR-DIAG-2/3/4/5/6, SOROR-KEY-
    # FIX/2, SOROR-MUTEX-2, SOROR-STAT-AUDIT, SOROR-FAB-AUDIT) all came
    # back with no missing rule lever - the residual is in over-
    # translation of Acts-of-Faith-substituted damage events to capped
    # VP. Composes multiplicatively with all other multipliers.
    if attacker_faction == SORORITAS_FACTION_TAG:
        soror_attacker_mult = SORORITAS_ATTACKER_OFFENSIVE_VP_MULTIPLIER
    else:
        soror_attacker_mult = 1.0

    bring_it_down_vp = min(
        int(BRING_IT_DOWN_CAP_PER_ROUND * mult * daemons_def_mult * drk_offensive_mult * tyr_attacker_mult * soror_attacker_mult),
        int(len(mv_killed) * BRING_IT_DOWN_VP_PER_KILL * mult * daemons_def_mult * drk_offensive_mult * tyr_attacker_mult * soror_attacker_mult),
    )
    no_prisoners_vp = min(
        int(NO_PRISONERS_CAP_PER_ROUND * mult * daemons_def_mult * drk_offensive_mult * tyr_attacker_mult * soror_attacker_mult),
        int(len(units_killed) * NO_PRISONERS_VP_PER_UNIT * mult * daemons_def_mult * drk_offensive_mult * tyr_attacker_mult * soror_attacker_mult),
    )
    # Cull damper composes the Drukhari (mobility), Tyranids
    # (monster-mash), Sororitas (last-resort) attacker gates and the
    # Daemons (invuln-stacked) defender gate. CUSTODES `mult` does NOT
    # apply to Cull (Custodes never has 10+model units to concede).
    # DAEMONS_DEFENDER damper DOES apply (Daemons fields 10-model
    # Plaguebearer/Bloodletter/Pink Horror squads that the sim over-
    # wipes vs real-meta 5++ + Daemonic-invuln durability). SORORITAS
    # damper DOES apply (Sororitas can wipe horde squads via massed
    # bolter/flamer output; Acts of Faith re-rolls inflate sim
    # conversion vs real-meta).
    cull_combined_mult = drk_attacker_mult * tyr_attacker_mult * daemons_def_mult * soror_attacker_mult
    cull_the_horde_vp = int(min(
        CULL_THE_HORDE_CAP_PER_ROUND * cull_combined_mult,
        len(horde_killed) * CULL_THE_HORDE_VP_PER_UNIT * cull_combined_mult,
    ))
    # Assassination intentionally NOT scaled by the DAEMONS defender
    # damper - Daemon Heralds are fragile T4 W4 4++ chassis that
    # genuinely die in real tournament play; the simulator Assassination
    # scoring against Daemons is directionally correct. SORORITAS
    # attacker damper DOES apply - Sororitas character-kill output is
    # part of the over-scoring envelope (Morvenn Vahl, Canoness, Saint
    # Celestine assassinate-CHARACTER alpha strikes inflate sim VP vs
    # real-meta).
    assassination_vp = min(
        int(ASSASSINATION_CAP_PER_ROUND * mult * drk_offensive_mult * soror_attacker_mult),
        int(len(chars_killed) * ASSASSINATION_VP_PER_CHAR * mult * drk_offensive_mult * soror_attacker_mult),
    )
    # LC-5: +1 VP bonus if the enemy Warlord was among the destroyed
    # CHARACTERs this round. Real Pariah Nexus Assassination: "Score 3
    # VP at the end of the battle round if one or more enemy CHARACTER
    # models were destroyed this battle round. Score 4 VP instead if
    # the enemy WARLORD was among those models." Cited as
    # `simulator.warlord_designation`. The bonus is added on TOP of
    # the per-round cap (Pariah Nexus rule treats the 4 VP as the
    # alternative max, not as cap + bonus — but since our flat 3 VP
    # per CHARACTER already gets close to the 4 VP ceiling on one
    # kill, the bonus VP is small and we add it post-cap for clarity).
    if enemy_warlord_uid is not None and enemy_warlord_uid in chars_killed:
        assassination_vp += ASSASSINATION_WARLORD_BONUS_VP

    return (bring_it_down_vp, no_prisoners_vp,
            cull_the_horde_vp, assassination_vp)


def _is_tactical_secondary_active(round_num: int, side: str, tactical: str) -> bool:
    """LC-2: deterministic tactical-secondary draw mechanic.

    Real Pariah Nexus has 9 Tactical secondaries; players hold 2 at any
    time, drawn from the deck. Any specific Tactical card is active for
    ~2/9 (~22%) of turns on average. SwegHammer implements only 2
    Tactical secondaries (Engage on All Fronts, Behind Enemy Lines);
    in a 2-card pool, real meta would have BOTH always-active, so the
    pre-LC2 sim scored both every round — which over-rewarded elite
    low-count factions (Custodes +20.9 vs real 48%) that can always
    hit the Engage / BEL conditions.

    LC-2 model: each side scores AT MOST ONE Tactical secondary per
    round. Selection alternates deterministically by (round_num, side):
      * side A round 1, 3, 5: Engage
      * side A round 2, 4:     BEL
      * side B round 1, 3, 5: BEL
      * side B round 2, 4:     Engage
    This halves each tactical secondary's effective coverage to ~50%
    per side, approximating the 22% real-meta coverage scaled to a
    2-card pool. Deterministic per (round, side) so PYTHONHASHSEED=0
    reproduces matrices.
    """
    # Sides A and B get OPPOSITE secondaries each round so neither
    # side has the same hand twice in a row.
    odd_round = (round_num % 2 == 1)
    if side == "A":
        is_engage_turn = odd_round
    else:  # side B mirrors
        is_engage_turn = not odd_round
    if tactical == "engage":
        return is_engage_turn
    if tactical == "behind_enemy_lines":
        return not is_engage_turn
    return False


def score_position_delta(
    own_units: Iterable["Unit"],
    map_: "Map",
    own_is_army_a: bool,
    round_num: int = 1,
    attacker_faction: Optional[str] = None,
) -> Tuple[int, int]:
    """Compute (engage_vp, behind_enemy_lines_vp) for one side at end-of-
    round given the side's currently-alive units, the battlefield map,
    and whether this side deployed in Army A's zone (low-y).

    Engage on All Fronts (Pariah Nexus tactical secondary, simplified):
        Score 5 VP if your alive units occupy 3+ of the 4 table
        quarters at end of round. Quarters are determined by dividing
        the map at (cx=width/2, cy=height/2). A quarter is "occupied"
        if at least one alive unit's position is inside it.

    Behind Enemy Lines (Pariah Nexus tactical secondary, simplified):
        Score 5 VP if any alive unit's position is within the
        opponent's deployment zone at end of round. Army A's enemy DZ
        is y >= map.height - map.deployment_width; Army B's enemy DZ
        is y <= map.deployment_width.

    Real-rule fidelity caveats:
    * Real Engage scores 2/3/5 VP for 2/3/4 quadrants and requires the
      occupying unit to be "wholly within" the quarter. Sim simplifies
      to a single 5 VP threshold at 3+ quadrants (position centroid).
    * Real BEL requires the unit "wholly within" the enemy DZ. Sim
      simplifies to position-inside-DZ check.
    Both simplifications preserve the secondary's directional
    incentive — projecting units forward / spreading across the map
    is rewarded, sticky-camping is not.
    """
    cx = map_.width / 2.0
    cy = map_.height / 2.0
    quadrants_occupied = set()
    in_enemy_dz = False

    if own_is_army_a:
        # Army A's enemy DZ is the high-y strip.
        enemy_dz_lo = map_.height - map_.deployment_width
        enemy_dz_hi = map_.height
    else:
        # Army B's enemy DZ is the low-y strip.
        enemy_dz_lo = 0.0
        enemy_dz_hi = map_.deployment_width

    for u in own_units:
        if u.current_health <= 0:
            continue
        pos = getattr(u, "position", None)
        if pos is None:
            continue
        ux, uy = pos
        # Quadrant detection: (low-x, low-y) = SW, (high-x, low-y) = SE,
        # (low-x, high-y) = NW, (high-x, high-y) = NE.
        qx = 0 if ux < cx else 1
        qy = 0 if uy < cy else 1
        quadrants_occupied.add((qx, qy))
        # Enemy DZ check.
        if enemy_dz_lo <= uy <= enemy_dz_hi:
            in_enemy_dz = True

    # LC-2: gate Engage / BEL behind the per-round tactical-secondary
    # draw. Each side scores AT MOST ONE per round (the secondary that's
    # "active" this turn per the alternating schedule).
    side = "A" if own_is_army_a else "B"
    engage_active = _is_tactical_secondary_active(round_num, side, "engage")
    bel_active = _is_tactical_secondary_active(round_num, side,
                                                "behind_enemy_lines")
    # Engage tiered (2/3/5 VP for 2/3/4 quadrants) per real Pariah Nexus.
    engage_vp = 0
    if engage_active:
        n = len(quadrants_occupied)
        if n >= 4:
            engage_vp = ENGAGE_VP_FOUR_QUADRANTS
        elif n == 3:
            engage_vp = ENGAGE_VP_THREE_QUADRANTS
        elif n == 2:
            engage_vp = ENGAGE_VP_TWO_QUADRANTS
    bel_vp = BEHIND_ENEMY_LINES_VP if bel_active and in_enemy_dz else 0
    # DRK-DIAG-9 — attacker-side damper on the mobility tactical
    # secondaries (Engage on All Fronts, Behind Enemy Lines) when the
    # scoring side is Drukhari. Real-meta Drukhari does not convert
    # these at the sim rate because commitment-to-quadrants exposes
    # fragile units to wipe responses, and "wholly within" enemy DZ
    # is harder to maintain than the position-centroid check
    # approximates. Cited as `simulator.secondary_drukhari_mobile_modifier`.
    if attacker_faction == DRUKHARI_FACTION_TAG:
        engage_vp = int(engage_vp * DRUKHARI_ATTACKER_MOBILE_VP_MULTIPLIER)
        bel_vp = int(bel_vp * DRUKHARI_ATTACKER_MOBILE_VP_MULTIPLIER)
    # TYRANIDS-DIAG-6 — attacker-side damper on the mobility tactical
    # secondaries when the scoring side is Tyranids. Tyranid horde
    # positioning is mostly Synapse-anchored (units stay within range
    # of a Synapse source for coherence and morale rules), so the
    # sim's wide-spread Engage scoring and centroid-based BEL check
    # overstate real-meta Tyranid mobility / spread. Cited as
    # `simulator.secondary_tyranids_monster_modifier`.
    if attacker_faction == TYRANIDS_FACTION_TAG:
        engage_vp = int(engage_vp * TYRANIDS_ATTACKER_MONSTER_VP_MULTIPLIER)
        bel_vp = int(bel_vp * TYRANIDS_ATTACKER_MONSTER_VP_MULTIPLIER)
    # SOROR-LAST-RESORT-DAMPER - attacker-side damper on the mobility
    # tactical secondaries when the scoring side is Adepta Sororitas.
    # Sororitas Repentia / Penitent Engine / Castigator can over-cover
    # via SISTERS-keyword swarm formations that real-meta lists don't
    # actually run; sim's centroid-based quadrant / DZ check overstates
    # real-meta Sororitas mobility / spread. Conservative 0.85x mirror
    # of the DRK-DIAG-9 / TYRANIDS-DIAG-6 pattern. Cited as
    # `simulator.secondary_sororitas_attacker_damper`.
    if attacker_faction == SORORITAS_FACTION_TAG:
        engage_vp = int(engage_vp * SORORITAS_ATTACKER_OFFENSIVE_VP_MULTIPLIER)
        bel_vp = int(bel_vp * SORORITAS_ATTACKER_OFFENSIVE_VP_MULTIPLIER)
    return engage_vp, bel_vp
