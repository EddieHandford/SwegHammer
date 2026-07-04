"""Module-level constants and instrument statistics for the battle simulator.

Extracted verbatim from ``code/simulator.py`` by pure code motion (Stage A of
``docs/SIM_MODULARIZATION_PLAN.md``). Nothing here depends on any other part of
the simulator, so this module is a package leaf. ``code/simulator.py`` re-imports
every name below so its public surface is unchanged; in particular the
instrument dictionaries are re-imported (not copied), so the diagnostic scripts
that reset and read ``simulator.OCFLIP_STATS`` and friends, and the geometry
helpers that mutate ``PATHFIND_STAGE0_STATS`` / ``REACH_STATS``, all operate on
the same single objects defined here.
"""

from __future__ import annotations

# A SwegHammer round is "every unit on both sides has activated once". A full
# game is 5 rounds (matches 10e). Round limit is also a backstop against
# pathological infinite loops if attrition somehow stalls.
MAX_ROUNDS = 5
CP_BONUS_DIVISOR = 2    # opponent must have this many more units per 1 CP awarded
CP_BONUS_CAP = 2        # max CP awarded per round
# 10e Unit Coherency band: every model must be within 2" of at least one other
# model in its unit (cited as `simulator.coherency_enforcement`). Used by the
# squad-rebuild Stage B post-move coherency pass.
COHERENCY_INCHES = 2.0

# OC-FLIP over-hold INSTRUMENT (#79, wave 192) — read-only accumulator, populated
# only when the env gate SWEG_OCFLIP_INSTR is set. Quantifies objective-rounds
# where a damaged big durable holder (a Knight / Titanic or big VEHICLE/MONSTER
# now in its damaged bracket, so effective OC < base OC) controls a marker the
# opponent COULD flip by committing nearby bodies (reachable OC > holder's
# effective on-marker OC). No behaviour change — purely measured. A diag runner
# resets and reads this. Keys: held = obj-rounds a damaged big-holder controls a
# marker; flippable = of those, how many the opponent could flip with nearby
# bodies; surplus = summed (opponent reachable OC − holder OC) over flippable.
OCFLIP_STATS = {"held": 0, "flippable": 0, "surplus": 0.0,
                "held_any": 0, "flippable_any": 0,
                # Reason-decomposition of the opponent's reachable OC on the
                # flippable-but-uncontested markers (#80 follow-up): how much is
                # melee (would abandon a fight to contest), shooty that could
                # shoot FROM the marker (the FREE-CONTEST opportunity the lever
                # should add), and shooty that would LOSE its shots from there
                # (correctly not pulled — a gunline-pull).
                "fc_melee_oc": 0.0, "fc_free_oc": 0.0, "fc_noshoot_oc": 0.0,
                # BURN-reachability (#87 avenue-1): of the obj-rounds a damaged big
                # holder controls a marker, how many have an OPPONENT unit that
                # could REACH the marker (within ~one move) and is NOT engaged — so
                # it could perform the Scorched Earth Burn Action (remove the
                # marker for VP, no OC win needed). Pre-check before the Burn build.
                "burn_reachable": 0}

# OVER-SCORE instrument (#83) — per-faction split of scored markers into
# (iii) contested-but-won vs (i) uncontested. Populated only when
# SWEG_OVERSCORE_INSTR is set; a diag runner resets and reads it. Read-only.
OVERSCORE_STATS: dict = {}

# OC-DELIVERY instrument (#84) — per-faction on-board OC vs OC delivered onto
# markers. Populated only when SWEG_DELIVERY_INSTR is set. Read-only.
DELIVERY_STATS: dict = {}

# SCREENING / shoot-loss instrument (#86) — per-faction shooting output split by
# free / pistol / big-gun-penalty / engagement-blocked. SWEG_SHOOTLOSS_INSTR. Read-only.
SHOOTLOSS_STATS: dict = {}

# RECIPROCAL-BLOCK instrument — per-faction footprint of the reciprocal
# shooting-into-engagement filter (SWEG_BGNT_RECIPROCAL) on a shooting
# activation's legal-target pool: how often the filter empties the pool (a
# fully lost activation), how often it drops the gun's single best target and
# forces a lower-expected-wounds shot (a focus-fire downgrade), and the summed
# expected wounds surrendered to those downgrades. Sizes how much of a faction's
# under-pole the reciprocal rule can own via blocked shooting. Populated only
# when SWEG_RECIP_INSTR is set; scripts/diag_recip_block.py resets + reads it.
# Read-only. Keys per faction:
#   reaching_filter, had_target, lost_all, partial_retarget, targets_dropped,
#   downgraded_shot, downgrade_ew_lost.
RECIP_INSTR_STATS: dict = {}

# STRANDING instrument (structural re-model Step 2, wave-93 drill re-run) —
# per-faction summed Objective Control within the control radius (three inches)
# versus within twice the control radius (six inches) of every marker, at each
# scoring snapshot. A six-to-three ratio near 2 means half the near-marker control
# strands in the three-to-six-inch ring (the M4-alpha target); near 1 means the
# default-on movement changes already closed it. SWEG_STRAND_INSTR. Read-only.
STRAND_STATS: dict = {}

# BOARD-CONTROL instrument (avenue-2 Stage 0, docs/BOARD_CONTROL_PLAN.md) — sizes the
# physical-board-control levers (no-overlap collision / ruin-wall movement / make-way).
# Populated ONLY when SWEG_BOARDCTRL_INSTR is set; a diag runner resets + reads it.
# Read-only. Measures, at settled objective-scoring snapshots: how packed OC-counted
# models are within 3" of markers (a >100% base-area packing ratio = OC that no-overlap
# collision will physically cap), how many base footprints actually overlap, how
# concentrated OC is on CONTESTED markers, and — a settled-position proxy for the
# ruin-wall lever — how often a big VEHICLE/MONSTER/TITANIC (non-FLY) model sits inside a
# RUIN footprint it should have to route around. Plus a per-faction JAM baseline at game
# end (models stranded in own deployment zone + mean squad->nearest-objective distance),
# the anti-regression yardstick Stages 1-4 must not worsen.
BOARDCONTROL_STATS: dict = {
    "obj_rounds": 0, "overlap_pairs": 0,
    "packing_sum": 0.0, "packing_n": 0, "packing_over100": 0,
    "contested_rounds": 0, "contested_packing_sum": 0.0,
    "big_in_ruin": 0, "big_snaps": 0,
    "jam": {},  # faction -> {games, dz_models_sum, min_dist_sum, squads}
}

# PATHFINDING Stage-0 GO/NO-GO counter (read-only; docs/PATHFINDING_PLAN.md). Counts,
# under SWEG_COLLISION, how often a collision move's STRAIGHT end is blocked (the case
# a pathfinder would have to route around), split big-base vs small-base. Only mutated
# when occupants are passed (collision active) AND SWEG_PATHFIND_STAGE0 is set — the
# production default path returns before this block, so it stays byte-identical.
PATHFIND_STAGE0_STATS: dict = {
    "total_big": 0, "blocked_big": 0, "total_small": 0, "blocked_small": 0,
}
# Reach-degradation instrument (gated SWEG_REACH_INSTR, wave 211): per BIG-mover
# move under collision, classify the block — an ENEMY on the path (cap_t<1) is
# FAITHFUL screening (keep), while reaching short with NO enemy on the path
# (cap_t>=1 but the straight end is illegal → overlaps a friendly/terrain) is the
# open-space over-impediment ARTIFACT to fix. Read-only; the diag runner resets it.
REACH_STATS: dict = {
    "big_moves": 0, "big_reached": 0, "big_enemy_capped": 0, "big_open_blocked": 0,
}
# A mover is "big" for pathfinding purposes when its footprint radius exceeds this
# (~38mm base). A 170mm Knight is ~3.3", infantry ~0.63" — the threshold cleanly
# separates the big bases that crash their reach from the small bases that sidestep fine.
_PATHFIND_BIG_RADIUS_IN = 1.5
