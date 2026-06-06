# AI-pursuit layer for held Tactical cards (plan, wave 121)

The watchdog's prescribed fix for the M2 AI-pursuit artifact (wave 120): a real
Tactical army under-scores in the sim (~10 secondary vs a faithful ~25-35) because
the combat-focused AI does not *pursue* the cards it holds. This plans the
even-handed layer that makes the AI play toward its held Tactical card — then the
key strategic caveat the wave-120 instrumentation surfaced.

## What the instrumentation showed (per-card achieve rate under M2-ON)

| held card | achieve % | pursuable by movement? |
|---|---|---|
| engage_on_all_fronts | 89% | already pursued (`_plan_engage_bias`) — fine |
| sabotage | 60% | partly (action on a forward body) |
| behind_enemy_lines | 37% | YES — move a spare fast unit into the enemy DZ |
| cleanse | 28% | YES — move a spare chaff unit onto a forward controlled objective |
| secure_no_mans_land | 50% | board-control (representation-gated) |
| storm_hostile_objective | 34% | board-control (representation-gated) |
| area_denial | 16% | board-control (representation-gated) |
| defend_stronghold | 11% | board-control (representation-gated) |
| extend_battle_lines | 9% | board-control (representation-gated) |

The existing pursuit only flags a unit that is ALREADY positioned (e.g.
`_assign_cleanse_actions` flags a chaff unit already sitting on a controlled
forward objective; it never MOVES one there). Engage is already pursued well (89%)
via `_plan_engage_bias`. The two clear, movement-pursuable gaps are **Behind Enemy
Lines (37%)** and **Cleanse (28%)**.

## The build (env-gated; even-handed; touches the move/action AI)

When an army holds a Tactical card it CAN pursue and has a SPARE unit to commit
(the asymmetry that falls out of unit count — a Knight has no spare bodies, a broad
army does), bias that unit's movement toward achieving the card:
1. **Behind Enemy Lines held** → pick a spare, fast, non-essential unit and bias its
   move-intent toward the opponent's deployment zone (a real player commits an
   expendable fast unit to project into the enemy DZ).
2. **Cleanse held** → pick a spare chaff unit and bias its move toward the nearest
   forward (outside-own-DZ) objective the army can control, so it is positioned to
   perform the Cleanse action that round (then the existing `_assign_cleanse_actions`
   flags it).
Only SPARE units (already-not-needed for the army's primary plan / combat) are
committed — no faction awareness; the benefit accrues to armies with spare bodies
(the broad under-shooters) emergently. Reuse `_is_chaff_unit` / the spare-unit
signals + `pick_move_intent` in `code/strategy.py`. Gate behind `SWEG_TAC_DECK`
(it only matters when the deck is on) or a sub-gate; A/B; keep-if-faithful.

## The strategic caveat (surfaced to the watchdog — read before building)

**The AI-pursuit layer's upside is BOUNDED to the 4 action/position cards. 5 of the
9 deck cards are board-control (secure / defend / extend / storm / area_denial),
which stall at 9-50% — and that stall is NOT an AI-pursuit gap, it is the
one-Unit-per-model REPRESENTATION gap (armies genuinely under-hold objectives in
zones — the same gap that drives the Imperial Knights primary over-hold).** So a
Tactical army's hand is OFTEN clogged with board-control cards no movement can
rescue; the pursuit layer lifts only Behind Enemy Lines + Cleanse (+ marginally
Sabotage). Expected effect: the Tactical armies recover PARTWAY (not fully to
~25-35), so M2(+pursuit) net-improves but is still bounded by the representation
gap.

**This means the representation gap (M4) is the single root of BOTH the primary
residual (IK over-hold) AND the secondary board-control stall — it gates ~5/9 of
the deck too.** Fork for the watchdog: (a) build the AI-pursuit layer now (bounded
upside, the prescribed step, a genuine one-sided secondary lever for broad armies),
then M4; or (b) go straight to the M4 representation work (the deeper root for both
primary and secondary), since the pursuit layer's ceiling is set by it. Default
(non-blocking): build the AI-pursuit layer (a) — it is faithful, even-handed, and
its partial recovery is real — then tackle M4.
