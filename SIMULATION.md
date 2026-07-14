# Simulation Engine Design

## Overview

The simulator is a stochastic 10th-edition Warhammer 40K combat engine
with movement, shooting, charge, fight, and morale phases over a 5-round
window on a 2D map. It models two armies fighting under SwegHammer's
unit-by-unit activation rules and emits a battle event stream that can
either be aggregated over thousands of battles for calibration sweeps or
rendered as a watchable replay for a single battle. The replay reconstructs
everything — positions, the running victory-point score, per-objective
holders, scoring flashes, and end-of-round secondary points — purely from
the event stream, so any simulator position change must emit a movement
event or the replay silently drifts from the live game. The dashboard
presents that stream as a per-round overview (`round_overview` in
`code/renderer.py`): the simulator models a codex squad as one unit per
model, so the raw stream is model-by-model, and the overview aggregates
it back up to squad granularity — each squad's net move, each
attacker-squad to target-squad shooting / charge / melee pairing with
total damage and models destroyed, arrivals, losses, the end-of-round
objective scoring, and each side's points remaining on the table —
beside one board snapshot per round. Under vanilla I-go-U-go (the
default — see "Activation Sequence" below), the overview also groups a
round's actions by *which player's turn* they happened in (the
`PlayerTurnStarted` event marks the boundary), not only by action type —
aggregating every move in a round ahead of every shot, with no turn
boundary, made a correct full-turn I-go-U-go simulation read as a
phase-by-phase alternating ruleset in the replay even though the
simulator itself was never wrong. Event logs with no `PlayerTurnStarted`
event (recorded under the SwegHammer alternating model, which has no
discrete per-player turn to mark, or older logs) fall back to one
unlabelled block per round.

Under the default vanilla battle-round structure, each player's turn emits
its own `TurnStarted` event (round number and army name; presentation-only,
no random-number draws, no effect on game state) at the moment that player's
Movement phase begins, and `round_overview` uses it to split each battle
round's recap into two sub-chapters — one per player's turn, in true
resolution order — instead of merging both players' moves, shots, charges,
and fights into a single per-round chapter bucketed by event type. A round's
losses, objective-scoring lines, and points-remaining trend line are round-
level tallies, not turn-level ones, so they appear once, on the round's
final sub-chapter, alongside the running score. Event logs recorded before
this change, or recorded under the alternating-activation ruleset (which has
no player-turn concept and so never emits `TurnStarted`), still render as
one chapter per round.

## Role in the two-stage pipeline

This document describes the **Stage 1** apparatus: the simulator whose
rules are being tuned until per-faction win rates match the May 2026
Warp Friends tournament aggregate (Goal A in `ROADMAP.md`). Stage 2's
points-equation fit (Goals C and D) runs on top of this engine once
Stage 1 has converged; the loop fits one master equation that prices
every unit from its stats plus small residuals, with the simulator
supplying the per-unit win rates that gate convergence. The
equation-fitting solvers live in `code/balancer.py` and
`code/equilibrium.py`; see `BASELINE.md` for the layer / track
breakdown. See `CLAUDE.md` "Project plan" for the full pipeline
framing.

## Architecture

```
code/
  units.py        — UnitProfile (frozen stats), Unit (mutable battle instance)
  army.py         — Army (collection of units + command points)
  simulator.py    — Battle (runs one engagement), BattleResult (output data)
  army_builder.py — Random army generation within a points budget
  calibration.py  — Batch simulation runner and win-rate analyser
  main.py         — Demo entry point
```

## Combat Model

### Stochastic Damage

Each attack is resolved against the full 10e hit / wound / save / Feel No
Pain chain with real dice rolls. The simulator is seedable so a single
matchup is reproducible; calibration sweeps re-seed per battle for an
honest distribution.

Deterministic average-case damage was used in the foundational 2025
prototype; the current engine has been stochastic since the Phase 1.5
foundation work (see `ROADMAP.md` "Foundation work").

One characteristic stayed deterministic after that work: a weapon's random
Damage characteristic (`D6`, `D3+3`, `2D6`, …) was applied at its
expected-value mean (a `D6` weapon always inflicted a flat 3.5). The
per-model weapon-loadout staging adds an opt-in gate, `SWEG_ROLLDMG`, that
rolls each weapon's real Damage dice once per shot instead (`code.units.roll_damage`).
Unset (the default) keeps the mean and draws no extra dice, so the engine's
output is byte-for-byte unchanged; set, it rolls the dice on the per-model
firing path (the profiles that carry a raw `damage_dice` string). Rolling
follows the 10e ordering — roll the Damage, then apply per-allocation
modifiers (Necrodermis halving, Rend and Tear, Melta) to the rolled value.
The rolled distribution's mean equals the legacy expected-value field, so the
change is a faithful variance model rather than a re-pricing: it tests whether
expected-value overkill on big single-shot guns (a `D6` "reliably" destroying
a 3-wound model where a real roll destroys it about two-thirds of the time)
inflates the elite / big-gun factions. Cited as `simulator.rolled_damage`.

### Damage Allocation (squad spillover)

The engine represents one `Unit` object per physical model, so a codex unit
of N models is N `Unit` instances that share a build-time `squad_id` (assigned
by `Army.add_squad`). When one attacker fires into such a unit, its whole
attack sequence is resolved against that unit, and damage is allocated per the
10e core rule: each unsaved wound is allocated to one model, which loses wounds
equal to the Damage characteristic; a wounded model must keep receiving further
attacks until it is destroyed before allocation moves on; and when a model is
destroyed, **the killing attack's excess damage is lost** — it does not carry
to another model. The allocation pointer in `Unit.attack` advances to the next
surviving same-`squad_id` model only after the current one dies, so the number
of models destroyed is bounded by the number of unsaved wounds, never by the
damage total (three unsaved wounds of Damage 6 destroy at most three one-wound
models). Devastating Wounds is treated as a save-bypassing normal hit under the
same rule (excess lost, no cross-model carry), not as a mortal wound. Cited as
`simulator.damage_allocation_spillover`. Before this rule landed, every shot in
a volley was dumped into a single model and the overkill was wasted, which
heavily under-rated high-volume anti-horde firepower (Knights) and over-rated
multi-model armies (Drukhari, Tyranids).

**Which model the wounds land on is the defender's choice** (gate
`SWEG_DEFENDER_ALLOC`, default-ON). The attacker's targeting heuristics pick
*which enemy unit* to fire at and measure range / line-of-sight / cover to the
nearest in-range model of it; the *defending* player then chooses *which model*
of that unit absorbs the wounds, exactly as in 10e. `Battle._defender_alloc_model`
ranks the unit's models so that (1) an already-wounded model is taken first —
10e's mandatory-continuation rule forces the defender to finish a model that has
lost wounds before any other, even one standing on an objective, and even if that
model is itself out of the firing unit's range (once one model makes the unit a
legal target, wounds may be allocated to any model in it); and (2) among
full-health models the defender sacrifices trailing bodies — off-objective and
furthest out — before models holding an objective. This lets a defender leave a
body on the marker and feed casualties from the back, the real reason wound
allocation is a player decision. The picker is passed into `Unit.attack` as
`alloc_next_fn` so it also governs the spillover pointer when a model dies
mid-sequence. Because the allocation target can differ from the in-range model
used for the to-hit math, the two are tracked separately (`math_target` vs
`shoot_target`) in `Battle._do_shoot`. Cited as `simulator.defender_allocation`.
Setting `SWEG_DEFENDER_ALLOC=0` reverts to the older behaviour where the attacker
piled fire onto the lowest-health model it could see.

**Mortal wounds** follow the opposite spill rule and are handled separately by
`Battle._apply_mortal_wounds`: excess mortal-wound damage is **not** lost on a
model's death — it keeps allocating to the next model of the same unit until all
mortal wounds are spent or the unit is destroyed (Feel No Pain rolled per mortal
wound). Every "a unit suffers X mortal wounds" effect routes through it (Doombolt,
the psychic-detachment payload, Bloodthirster, Tank Shock, Dark Pact, Leechspore).
Cited as `simulator.mortal_wound_spillover`. Devastating Wounds is *not* a mortal
wound in the current edition — it is a save-bypassing normal hit and follows the
normal (excess-lost) allocation above. **Deadly Demise** hits each *unit* within
6″ once (not each model): nearby models are grouped by `squad_id` and the unit
takes its X mortal wounds a single time. **Blast** likewise counts the models in
the *targeted unit* (by `squad_id`), not every same-name model in the army.

### Shooting into engagements — the reciprocal Big Guns Never Tire rule

Two directions of the same core rule are modelled. The *attacker's own*
engagement was already handled: a unit within Engagement Range of an enemy
normally cannot shoot, except Pistols (fire freely) and MONSTER/VEHICLE units
(Big Guns Never Tire — they shoot at −1 to Hit and may only target enemies they
are themselves engaged with). The *reciprocal* direction (gate
`SWEG_BGNT_RECIPROCAL`, default-ON; `=0` restores the prior pipeline
byte-for-byte) closes the other half in `Battle._do_shoot`: an enemy unit within
Engagement Range of a friendly unit *other than the attacker* cannot be selected
as a ranged target **unless it is a MONSTER or VEHICLE**, in which case the shot
is permitted but each non-Pistol attack takes −1 to Hit (set on the firing model
as `shooting_at_engaged_brick`, read in `Unit.attack`). That −1 composes with
the attacker's own in-engagement −1 under the ±1 hit-modifier cap, so the two
never stack past −1. **Blast** weapons get no carve-out at all — they can never
target a unit within Engagement Range of *any* friendly unit, including the
attacker's own. The candidate list is filtered before every target scorer, so
the focus-fire and target-economics pickers only ever score legal targets; the
split-fire planner (`_plan_squad_fire`) and the T'au Markerlight emission apply
the same gate. One deliberate consequence, faithful to the printed rule: a melee
army that pins an enemy now *protects* that enemy from its own guns. Cited as
`simulator.big_guns_reciprocal` and `simulator.blast_engagement_restriction`.

A read-only instrument (`SWEG_RECIP_INSTR`, default-off, byte-identical when
unset) sizes how much of a faction under-pole this reciprocal filter can own via
blocked shooting. When set, `Battle._record_reciprocal_block` tallies per faction
how often the filter empties a shooting activation's legal-target pool (a fully
lost activation) versus merely drops the gun's single best target for a
lower-expected-wounds shot (a focus-fire downgrade), plus the summed expected
wounds surrendered. `scripts/diag_recip_block.py` resets and reads it.
Measured footprint on Astra Militarum (the frame's biggest under-pole): fully
lost activations are near zero (≤0.2 per game), downgrades ≤1.5 per game, ≤1.4
expected wounds surrendered per game, and *exactly zero* against a gunline
opponent that never engages the screens — a negligible mechanical cost. The
matching win-rate counterfactual needs no code: running the evaluation with
`SWEG_BGNT_RECIPROCAL=0` and pairing against the standing anchor moves Astra
Militarum's aggregate win rate by only +0.24 points, so the reciprocal rule owns
essentially none of that faction's −14 under-pole.

### Charge-Path Legality (screening)

A charging unit may not pass within Engagement Range of any enemy unit it did
not declare as a charge target (10e core Charge Move rule — gate
`SWEG_CHARGE_PATH`, default-ON since wave 242). The charge-target picker
(`pick_charge_target` in `code/strategy.py`) enforces two geometry checks: for
non-flying chargers, the straight-line path from the charger to the approximate
charge-end spot must not pass within Engagement Range of a non-target enemy
(`_charge_path_screen_gap` in `code/sim/geometry.py`); and for all chargers —
including those with the FLY keyword, which may cross over screens but not end
among them — the end spot itself must not sit within Engagement Range of a
non-target enemy. Candidates that fail either check drop out of the scorer, so
a screening body becomes the charge target naturally through the existing
kill-value ranking — screens work because the rules make them work, not via
any new scoring term. Cited as `simulator.charge_path_non_target`. Setting
`SWEG_CHARGE_PATH=0` restores the legacy behaviour where chargers passed
through screening units to reach the unit behind.

### Threat-Projection Field — Charge Scoring (default-off)

The charge-target picker's default score prices each candidate against only that
target's own melee output back at the charger (the denominator
`1 + threat_against_target`), so it is blind to the rest of the board — most
sharply to a second enemy melee squad sitting beside the target that will
counter-charge whoever commits (the two-adjacent-Khorne-Berzerkers case). The
threat-projection field, gate `SWEG_THREAT_CHARGE` (default-OFF), replaces that
denominator with the post-fight incoming threat field at the charge destination:
`1 + T_post / effective_wounds(charger)`, where `T_post` sums the projected
expected wounds every living enemy can deliver onto the charger standing at the
destination — its guns within Move + weapon range (attenuated by the positional
Benefit of Cover at the cell) plus its melee weighted by the real Move + 2D6
charge-reach probability — minus the target's own contribution weighted by the
probability the fight kills it this turn (killing an isolated target removes it
from the field; a supported target leaves its neighbour's reach in the
denominator). Every existing bonus multiplier is preserved and the OFF path is
byte-identical (the denominator is the exact legacy value when the gate is
unset). The field REUSES the audited expected-wounds helpers
(`strategy._kill_potential_wounds`, `simulator._ranged_expected_wounds`) and the
audited cover save math, and draws no new random number. Cited as
`simulator.threat_projection_charge`; owner-originated design in
`docs/THREAT_LAYER_PROPOSAL.md`. The falsifier is the "walked-into-it" rate —
how often a unit ends an activation in a cell whose realized next-turn incoming
damage is lethal — measured by `scripts/diag_walked_into_it.py`. Honest caveat:
the ranged half is attenuated only by the angle-independent positional cover the
shooting resolution actually enforces, not by line-of-sight occlusion (a
separate rules-fidelity question). Only charge scoring (consumer 1) is built;
move-intent destinations and reserve placement (consumers 2-3) are not.

### Activation Sequence

`code.simulator.RulesConfig` selects one of two activation models at
`Battle` construction — it is an explicit choice, not an environment gate,
and the two are not interchangeable in how they read as a replay (see
"Output Format" below).

**Vanilla 10e I-go-U-go — `RulesConfig.vanilla_10e()`, the default.**
`Battle(a, b)` with no `rules=` argument uses this. Matches the real
mission sequence: one player completes their *entire* turn — every one of
their units' Movement, then Shooting, then Charge, then Fight — before the
other player's turn begins. This is the mode `code/balancer.py`'s Monte
Carlo bisection and `scripts/evaluate_vs_meta.py` run against, so Stage 1's
tournament comparison reflects the real turn structure.

1. **First-player determination**: Randomised once at the start of the battle (50/50) and
   the same player goes first every round thereafter, matching the real mission sequence
   ("The players roll off. The winner declares whether they will take the first or second
   turn."). Default since wave 232; setting `SWEG_ROLLOFF_ONCE=0` restores the legacy
   per-round re-roll. Shared with the alternating model below — it is not mode-specific.
2. **Per-turn, per-phase activation**: within the active player's turn, each phase
   (Movement, Shooting, Charge, Fight) activates that player's alive units in
   `activation_queue` order (Lanchester score, highest first) before the round moves on
   to the other player's turn. `cp_catchup_bonus` (the smaller army's bonus-CP rule
   below) is off by default under this mode — 10e has no such mechanic.

**SwegHammer alternating activations — `RulesConfig.sweghammer()`, opt-in
only.** The project's original, non-10e ruleset, used only when a script
explicitly asks to simulate SwegHammer-house-rule play rather than derive
prices or calibrate against tournament data — never constructed by the CLI
demo, the Streamlit dashboard, or the calibration sweep. Both armies'
units alternate one at a time within a round instead of each player
taking a full turn:

3. **Activation queue**: Both armies sort their alive units by Lanchester score (highest first),
   creating an ordered activation queue for the round.
4. **Alternating activations**: The first player activates their highest-priority unactivated
   unit; the second player responds with theirs. This repeats until one or both queues are
   exhausted.
5. **Surplus activations**: If one army has more units, its remaining units activate unopposed
   after the other army's queue is empty.
6. **Command point awards**: After each round (except Round 1), the player with fewer surviving
   units receives bonus CP: `bonus_CP = max(0, floor((opponent_count - own_count) / 2))`
   (`cp_catchup_bonus`, on by default under this mode only — pure SwegHammer catch-up, not
   a 10e rule).

### Target Selection

Attackers target the enemy unit with the **lowest current health** (focus-fire heuristic). This
approximates optimal play and ensures units are eliminated rather than spread-damaged, producing
cleaner attrition dynamics.

### Charge trade assessment and kiting

Two environment-gated piloting heuristics model how a real player weighs
melee commitment:

- **`SWEG_CHARGE_TRADE`** (adopted **default-on** by owner ruling on
  2026-07-07; `=0` is the byte-identical kill-switch,
  `scripts/sim_motion_proof.py` fingerprint match) — before declaring a
  charge, estimate the fight-phase points trade
  (`Battle._melee_trade_estimate`): the charger's first-strike damage into
  the target versus the counter-swing from the target and its squad-mates
  within pile-in reach. A charge into a melee-superior target that clearly
  loses the trade is not declared — the "Intercessors charge Boyz" misplay.
  Charges into shooters (tying up guns), coordinated cage charges, and cheap
  tarpit chaff are exempt.
- **`SWEG_KITING`** (built + **held default-off** pending a proper
  eighty-battle screen; `SWEG_KITING=1` opts in, useful when watching
  replays) — a shooting unit with a melee-superior enemy squad inside likely
  charge reach (their Move plus the two-dice median), where the trade
  estimate says the enemy wins the fight, steps back just far enough to
  restore the stand-off gap and keeps shooting. It never kites off an
  objective marker, never fires for chaff or screens, never fires when
  behind on victory points (a player behind must contest, not retreat), and
  only fires when its own shooting can meaningfully damage the pursuer. The
  older sibling `SWEG_KITE_MOVE` screened +1.12 worse mean absolute error at
  eighty battles per matchup; this lever's rails target exactly that failure
  mode, and the screen recorded in the decision ledger's open levers decides
  its default. Do not enable both kite levers together.

Units that made a charge move fight in the **Fights First** step of the fight
phase (cited `simulator.fights_first_chargers`, alongside the datasheet-level
Fights First keyword, `simulator.fights_first_keyword`); the replay overview
annotates melee lines with "(charged — fights first)" so the strike order is
visible in a recap.

### Pilot hooks — external decision overrides

Three attachment points let an external harness override the engine's
decision heuristics without touching production behaviour. All follow the
same pattern: an attribute production code never sets, consulted through
`getattr(..., None)`, byte-identical when absent.

- **`Battle._pilot_focus`** (the original, predating the AI Lab) —
  consulted in `_do_shoot`; a callable that may force the attacker's
  shoot-target choice. Built for the manual anti-Knight piloting
  experiments recorded in `docs/PILOT_FINDINGS.md`.
- **`Battle._pilot_charge`** — consulted in `_do_charge` just before
  `_wants_to_charge`; returns True/False to override *whether* the unit
  wants to charge, or None to defer to the baseline heuristic. Whom to
  charge stays with `pick_charge_target` either way.
- **`Battle._pilot_move`** — consulted in `_do_move` immediately after
  `pick_move_intent`; sees the baseline `(target_pos, intent)` and may
  return a replacement. Downstream move processing (make-way spread,
  staging, the production kiting gates) applies to the override exactly as
  it would to the baseline decision.

A fourth, army-level hook — **`Army._ai_lab_dual_scales`** — is read inside
`pick_move_intent`'s DUAL engage branch and rescales that branch's
charge-threat buffer and acceptance threshold; scaling inside the branch is
what lets a narrowed pick fall through to the objective logic naturally.

The consumer of the charge/move/dual hooks is the **AI Lab** — the
genetic-algorithm duel sandbox in `code/ai_lab/` (see
[`docs/AI_LAB_PLAN.md`](docs/AI_LAB_PLAN.md)), which evolves interpretable
piloting knobs against a frozen baseline strain. With the hooks in their
inert regime (`pilot.attach(..., squad_move_as_unit=False)`) the neutral
genome is proven byte-identical to an unhooked battle, event-for-event, by
`tests/test_ai_lab_pilot_hooks.py`. AI Lab duels themselves run with
`squad_move_as_unit=True`: every squad's walk intents are decided once per
squad per round and shared across its models, on both sides symmetrically —
a deliberate, fair divergence from the calibration simulator's per-model
walks, closer to real 10e Unit Coherency, applied only inside the sandbox
and never to calibration battles.

### Victory Conditions

A battle ends when:
- One army has no surviving units → the other army wins.
- Both armies reach zero simultaneously → draw (mutual destruction).
- The round limit (30) is reached → the army with more surviving units wins; if equal, draw.

## Data Flow

```
BattleConfig
    │
    ▼
ArmyBuilder.build(points_budget, unit_pool)  →  Army A, Army B
    │
    ▼
Battle(army_a, army_b).run()  →  BattleResult
    │
    ▼
CalibrationSuite.run(n_battles)  →  WinRateReport
```

## Output Format

### BattleResult

```python
@dataclass
class BattleResult:
    winner: Optional[str]   # army name, or None for draw
    rounds: int             # number of rounds played
    a_survivors: int        # units surviving in army A
    b_survivors: int        # units surviving in army B
    a_start: int            # initial unit count for army A
    b_start: int            # initial unit count for army B
```

### CalibrationReport

```
Matchup: Marines vs Orks (1000 pts each, 1000 battles)
  Marine wins:  512 (51.2%)
  Ork wins:     471 (47.1%)
  Draws:         17  (1.7%)
  Avg rounds:   8.3
  Avg Marine survivors: 2.1
  Avg Ork survivors:    1.9
```

## Engine status (shipped)

The phase-based naming below ("Phase One / Two / Three") was retired in
the 2026-05 docs sweep — both because the original "planned" phases have
all shipped, and because reusing the word "Phase" inside this document
collided with the equilibrium solver's own Phase 1–6 ladder
(`code/equilibrium.py`). The current state of the engine:

- **Stochastic damage** — full 10e hit / wound / Armour Penetration / Feel
  No Pain chain with real dice rolls.
- **All five combat phases** — Command, Movement, Shooting, Charge, Fight,
  with Battleshock at round end.
- **Counter-Offensive same-unit-twice fix** (2026-07-09) — the reactive
  Core Stratagem (`Battle._try_counter_offensive`) re-selected the single
  best-melee-DPA candidate on every trigger with no memory of earlier
  picks, so one unit could be picked to fight via Counter-Offensive more
  than once in the same Fight-phase pass — Counter-Offensive's own TARGET
  restriction ("a unit ... that has not already been selected to fight
  this phase") was assumed to hold implicitly rather than enforced. Now
  tracked explicitly via `Battle._fought_this_fight_phase` (reset once per
  Fight-phase pass; populated by both the normal Fight-phase sequence and
  this out-of-sequence strike). A second, legal Counter-Offensive fire in
  the same phase against a *different* not-yet-fought unit is still
  possible. Cited as `Stratagem.Counter-Offensive`.
- **2D map and terrain** — continuous-coordinate map with Light /
  Heavy / Obscuring / Impassable terrain; Liang-Barsky parametric clipping
  for line of sight; objective markers with primary victory point scoring.
  Ruins block line of sight except when both endpoints carry an INFANTRY,
  BEAST, or SWARM keyword (10e core Ruins rule). When either endpoint carries
  the TOWERING keyword (Knights, Wraithknight, Daemon Primarchs, Titans),
  both Obscuring terrain and Ruin walls are bypassed for line-of-sight
  purposes (10e core TOWERING keyword rule).
- **Angle-aware Benefit of Cover** (terrain-and-line-of-sight program Phase
  2a, `docs/TERRAIN_LOS_SPEC.md` section 4; env-gated `SWEG_COVER_ANGLE`,
  default off, byte-identical off). The default cover lookup (`Map.cover_at`)
  is position-only: it grants the Benefit of Cover purely from what terrain
  the *target* stands in, regardless of where the attacker is standing —
  which both over-grants (a shooter standing in the same Ruin as its target
  still "gets" the target's cover) and under-grants (a Ruin genuinely
  intervening on the shot line grants nothing if the target's own position
  is in the open) relative to the real 10e rule for area terrain. The gate
  swaps in `Map.cover_between(attacker_pos, target_pos)`, which grants cover
  only when the target is within a cover piece the attacker is not also
  within, or a cover piece (containing neither endpoint) crosses the shot
  segment. It also folds Woods (`OBSCURING`) into the cover-granting set,
  fixing an existing omission where a unit standing only in Woods received no
  cover at all. Wired at the two cover-consult points in `Battle._do_shoot`
  and Fire Overwatch; the position-only `Map.cover_at` is untouched for any
  other caller. Per the spec, this is meant to become the single shared
  cover-and-occlusion geometry for both resolution and the threat-projection
  field above once the positioning layer is ready to consume it (Phase 3,
  not yet built). Cited as `simulator.benefit_of_cover_angle` in
  `data/rule_citations.d/core_terrain_ruins.json`.
- **Strategy layer** — units pick a per-activation intent (HOLD, CAPTURE,
  STEAL, ENGAGE, REPOSITION, FALL_BACK) based on objective state and role.
- **Catalogue** — ~1478 units from BSData WH40k 10e (`v10.6.0`), refined
  by `data/overrides.json`.
- **Additive melee weapon profiles** (`UnitProfile.extra_melee_profiles`) —
  the Fight phase resolves one extra attack pass per entry in this tuple,
  using that entry's own attacks / strength / armour penetration / damage /
  keyword flags. Populated by the BSData mapper for every non-heterogeneous
  unit whose gear contains a melee weapon tagged with the 10e core
  `[EXTRA ATTACKS]` keyword (fires in addition to the model's other melee
  weapons; distinct from the ranged `extra_ranged_profiles` picker, which
  is mutex / pick-one per group). 135 units populated in BSData v10.6.0.
- **Override precedence for the per-model weapon-list rebuild** (env-gated
  `SWEG_OVERRIDE_MELEE_PRECEDENCE`, default off) — `Army._add_squad_per_model`
  (the per-model-loadouts firing path) rebuilds every per-model Unit's
  `extra_melee_profiles` / `extra_ranged_profiles` from the BSData mapper's
  `model_loadouts` data, which unconditionally overwrote a hand correction to
  either field in `data/overrides.json` even though that correction merged
  correctly into the aggregate catalogue profile — the fix was silently inert
  in every simulated battle. When the gate is on, the rebuild leaves a field
  alone whenever `data/overrides.json` explicitly set it for that unit
  (tracked via `UnitProfile.override_field_names`, populated in
  `code/bsdata/loader.py`). A blast-radius audit of `data/overrides.json`
  found 33 units carrying an `extra_melee_profiles` or `extra_ranged_profiles`
  hand override with a resolved per-model loadout, 26 of which were actively
  affected before this fix (the Chaos Knights Knight Despoiler and Knight
  Tyrant among them). Off (the default) reproduces the unconditional rebuild
  byte-identically. Cited as `simulator.override_melee_precedence`.
- **Sweep coverage** — `scripts/evaluate_vs_meta.py` runs the per-faction
  matchup matrix and reports mean absolute error vs the May 2026 Warp
  Friends tournament aggregate. This is the Stage 1 success metric.
- **Two-track points-equation fit** (`code/balancer.py`, `code/equilibrium.py`)
  — Stage 2 work, runs on top of this engine once Stage 1 converges. The
  two tracks supply the equation's coefficients and per-unit residuals.
  See `BASELINE.md`.

For per-feature status and ownership, see `PROJECT.tex`.

## Performance

The simulator's hot path is `Battle.run()` — movement intent selection,
shooting, charge, and fight phases repeated for up to five rounds. Three tiers
of caching were added to reduce per-battle wall time from roughly 117 ms to
roughly 32 ms (73% reduction, measured by `scripts/bench_simulator.py` on a
30-battle benchmark across three matchups):

- **Save and wound probability cache** (`functools.lru_cache` on
  `save_probability` and `wound_probability` in `code/simulator.py`). Both
  functions are pure; there are only a few dozen distinct input combinations
  per battle. Tier 1.
- **Alive-units cache** — `Battle.run()` rebuilds alive-unit lists once per
  round rather than on every phase call. Tier 2.
- **Line-of-sight cache** (`_los_cache` in `code/map.py`). Keyed by a
  terrain-epoch integer (assigned per unique terrain tuple to avoid garbage-
  collector identifier reuse), the 0.5-inch-grid-discretised endpoint pair,
  the ruin-pass boolean, and the towering boolean. ~46 000 distinct entries
  per 90 battles, ~40% hit rate, ~1.6× speedup vs uncached. Tier 3.
- **Cover-priority cache** (`_cover_prio_cache` in `code/strategy.py`). Keyed
  by terrain epoch and 0.5-inch-grid position; reused by both
  `_shimmy_target` and `_best_nearby_cover_point`. ~1 300 entries per 90
  battles — high hit rate because cover zones are large. Tier 3.
- **Unsaved-fraction cache** (`_unsaved_fraction` with `functools.lru_cache`
  in `code/strategy.py`). There are only ~200 distinct `(save, invuln_save,
  attacker_ap)` triples in the catalogue; near-100% hit rate after warm-up.
  Eliminates the save-probability calls that `_durability` was making on every
  one of ~56 000 invocations per benchmark run. Tier 3.
- **Cover-point search** (`_best_nearby_cover_point`). Precomputed
  trigonometric constants replace per-call `math.cos`/`math.sin`; a
  running-best comparison replaces the candidate list and `max()` call; the
  `is_blocked()` check is replaced by the cover-priority cache (impassable
  terrain is assigned priority −1). Tier 3.

The benchmark harness lives in `scripts/bench_simulator.py` and runs
`python -m scripts.bench_simulator` (pass `--battles N` or `--profile` for
cProfile output). Baseline numbers and per-tier deltas are in the commit
messages on branch `claude/add-visualization-graphs-Um9Eq`.

## Design Decisions and Trade-offs

### Why Stochastic Damage?

The 2025 prototype used deterministic average-case damage to surface
structural imbalances in ~100 battles per matchup. As soon as the
calibration target moved from "is this army composition balanced?" to
"do per-faction win rates match the real tournament aggregate?", real
dice rolls became necessary — tournament data is the sum of variance-
inclusive games, so the simulator has to match that distribution.
Calibration sample sizes are correspondingly larger (N=200 per pairing
for the honest reading).

### Why Focus-Fire Target Selection?

Focus-fire (targeting lowest-health enemy) eliminates units fastest, maximising the Lanchester
advantage of the attacking army. It approximates the play of an experienced player. Spread-damage
targeting would artificially suppress the score advantage of strong armies, masking imbalances.

### Why Randomise First-Player Each Round?

The goal is to measure structural balance, not first-player advantage. By randomising per round,
the first-player effect averages out over a large number of simulations. A separate experiment can
fix first player to measure the size of that advantage.
