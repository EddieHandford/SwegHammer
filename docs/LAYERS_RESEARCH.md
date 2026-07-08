# Decision-substrate layers — design research (2026-07-08)

Owner's question, in spirit: what other **layers** can we add that tie together
existing systems and unlock emergent play? A layer here is a **substrate** — one
shared representation or evaluation surface that many decisions consult — not
another single-behaviour heuristic nudge. The two approved layers are the
reference shape:

- **Threat field** (`docs/THREAT_LAYER_PROPOSAL.md`) — "what arrives at this
  position": a summed incoming-damage field every move and charge prices against.
- **Terrain realism** (`docs/TERRAIN_REALISM_PROPOSAL.md`) — "what the board
  physically permits": real line of sight and wall collision.

This document extends that series. It evaluates the owner's six candidate seeds,
consolidates two of them, ranks the survivors, and states each one's evidence
base, real-play grounding, buildability, and — mandatorily — its family-table
risk and a **falsifiable behavioural instrument**, because the dominant lesson of
this campaign is that on-table play improvements bank to the durable side and the
headline mean absolute error does not move (see below).

---

## 0. The one architectural gap these layers exist to close

The decision-surface inventory names a single class-level weakness: **every
decision is LOCAL and SINGLE-TURN.** No unit reasons about the game two rounds
out. Concretely, in the code:

- `pick_army_plan` (`code/strategy.py:2833`) is the entire army-level horizon and
  it is a five-value string — `LEFT` / `RIGHT` / `MID` / `HOME_HOLD` / `COUNTER`
  — chosen from enemy centre-of-mass and the current victory-point differential.
  It has no per-position valuation and no memory across rounds.
- Charge scoring (`code/strategy.py`, `score = value / (1 + threat_against_target)`)
  reads only the target's own melee threat — no reasoning about what dies on both
  sides next turn, no army-level trade.
- The two approved layers are both still single-turn surfaces: the threat field
  answers "what hits me *this* turn"; terrain answers "what can I see/reach *now*".

This matters because the two remaining poles are themselves multi-round
phenomena. The honest residual (`docs/CURRENT_STATE.md` head) is **Astra Militarum
under by ~17 and Death Guard over by ~14** — ~72 percent of all remaining error.
Both are the same thing viewed from opposite ends: durable units win because the
scoring rewards *being alive in the scoring rounds*, and fragile bodies die before
those rounds. The ledger's own diagnosis (`diag_attrition`): the three biggest
over-poles kill the *least* (34–35 percent of the enemy by round 5) yet post the
highest primary because they still hold markers; the deepest under-pole is on an
objective only ~10 percent of unit-rounds. **The wall is a horizon artifact — and
nothing in the architecture currently has a horizon.** That is the class these
layers address.

### The escape condition every layer here must satisfy

`docs/LEVER_PROTOCOL.md` §2 and the whole REVERTED/REJECTED graveyard say the same
thing five different ways: a **faction-neutral single-sided piloting nudge washes
or feeds the durable side** by closed-matrix symmetry (raising one army's play
lowers its opponents'). The list is long and consistent — `SWEG_SCREEN_AI`,
`SWEG_TANK_SCREEN`, `SWEG_MASS_BODIES`, `SWEG_FOCUS_MELEE`, `SWEG_SHOOT_HOLDERS`,
`SWEG_GUNLINE_HOLD`, `SWEG_STAGING`, `SWEG_FOCUS_FIRE`,
`SWEG_PERSISTENT_NOMINATION`, the entire going-second family — every one of them
was built, fired correctly, and either washed or banked to the durable pole.

The threat proposal states the only known escape precisely: a **substrate operates
on both sides at once** (fragile units decline exposure they cannot pay for AND
durable/killy units commit correctly), so it is not a one-directional nudge that
the closed matrix cancels. That is **necessary but not sufficient** — even a
symmetric substrate can bank to the durable side if the durable side profits more
from better play. So each layer below must additionally either (a) give the
*fragile* side a capability it structurally lacks, or (b) add the *multi-round*
dimension the wall lives in, and each is judged on a **behavioural falsifier, not
the headline** — exactly the honest posture the threat and terrain proposals
adopt. Two of the six seeds fail the substrate test outright and are consolidated
or rejected; three survive; one survives only in a narrow sliver.

---

## Layer A — THE VALUE FIELD (the multi-round dual of the threat field)

**The keystone.** The threat field prices *what arrives* at a position. The value
field prices *what a position is worth over the rounds that remain*: expected
victory-point yield from marker control, secondary opportunity, and denial. It is
the missing horizon, and it is the substrate Layers B, C, and the consolidated
resource term all read from.

### (a) Evidence it is missing

- The single named architectural gap in §0: no per-position, multi-round
  valuation exists anywhere. `pick_army_plan` is a five-string proxy.
- `SWEG_AM_CHASE_VP` (ledger, held 2026-07-07) — the owner's play-to-score idea —
  raised Astra Militarum victory points almost everywhere in the battery yet did
  **not convert to wins**: it "padded the margin in the far-behind matchups where
  Astra Militarum loses anyway." A single-turn target multiplier cannot tell that
  a game is already lost; a multi-round value field can (a lost-value position
  stops attracting commitment).
- `SWEG_AM_CADIA_STANDS` (held, inert) — a survive-on-the-objective buff with
  almost nothing to protect because Astra Militarum bodies are on an objective
  only ~10 percent of unit-rounds. The upstream problem is **getting bodies to
  the positions worth holding**, which is a valuation-and-movement problem, not a
  survival buff.
- `diag_signatures`: flat round-2-to-5 primary trajectory, no late-game attrition
  decay — the sim plays every round as if it were the same round. Real games have
  a scoring arc the AI does not represent.
- The refuted claim-and-bank / sticky-race / mass-bodies family all failed
  because fragile bodies die *this* turn; none of them could reason "this body
  will be dead by the scoring round, so spend it now for maximum denial instead."

### (b) Real-play grounding

Competitive play is explicitly multi-round value management. The Grimhammer
game-plan primer: in the pre-game "you should have identified what units you want
alive in the late stages of the game… in the early stages you're protecting these
units so they have an impact to shift the Primary to you in the later game"
([Grimhammer, Build a Gameplan](https://grimhammertactics.com/40k-tactics-how-to-build-a-gameplan-for-competitive-40k-missions/)).
Goonhammer's scoring maths sets the stakes the field prices: up to 45 primary
victory points, capped 15 per round, and secondaries that "reward playing armies
which are versatile… the ability to keep drawing them if you don't score means
you can stack them for later turns"
([Goonhammer, 10th Edition Primary Scoring Statistics](https://www.goonhammer.com/hammer-of-math-10th-edition-primary-scoring-statistics);
[Goonhammer, Examining Objective Scoring](https://www.goonhammer.com/hammer-of-math-examining-40k-objective-scoring-in-2021/)).
The core skill named in the Start Competing guide is playing the mission over the
whole game, not the local firefight
([Goonhammer, Start Competing](https://www.goonhammer.com/start-competing-your-guide-to-getting-better-at-warhammer-40000/)).

### (c) Composition — what it reads, what consumes it

The value field is knob-free and composes entirely from priced quantities that
already exist:

- **Reads:** objective marker positions and the primary award rule
  (`Battle._score_objectives`, `code/simulator.py:1109`; the round-start
  controller cache `_obj_controller_at_round_start`); the army's *own picked*
  secondary cards (`pick_secondaries`, `code/secondaries.py:1101`, returns the
  Fixed + Tactical keys this army brought) so the field knows whether Behind
  Enemy Lines, Bring It Down, Engage on All Fronts etc. are even scorable for
  this army; the victory-point differential and round number the army plan
  already fetches (`army._battle_ref._a_vp` / `_b_vp`).
- **The multi-round term (the new part):** for each candidate position, sum the
  expected victory points it yields over *rounds remaining* — marker control
  weighted by **contestability** (can I still control it at the scoring step,
  given the threat field's incoming damage against a unit standing there?) plus
  the secondary opportunity the position unlocks. Contestability is where the
  value field *multiplies into the threat field*: a position's value is discounted
  by the probability the unit holding it is dead before it scores. This is the dual
  the owner named — threat says "you take this much damage here"; value says "this
  is what surviving here is worth, over this many rounds."
- **Per-unit dual (this absorbs seed 5, the resource/attrition budget):** the same
  arithmetic applied to a *unit* rather than a *position* is that unit's future
  value — its expected remaining victory-point contribution. That single scalar is
  the "preserve me / spend me" signal seed 5 asked for; it does not need a
  separate substrate (see the consolidation note under Layer E).
- **Consumers, in adoption order:** (1) movement destination choice — a mover is
  pulled toward high-net-value cells (value minus threat-cost), which is what
  finally gives Cadia-Stands-class buffs something to protect; (2) `pick_army_plan`
  itself — replace the five-string heuristic with the highest-value posture; (3)
  target choice — kill the enemy unit whose death opens the most *value* (denies
  the most future scoring), the honest form of the chase-victory-points idea.

Complexity: O(candidates × markers × rounds-remaining) per activation, with the
per-enemy threat parameters already cached once per round — the same budget class
as the threat field. Rough size: a Tier-3 build, but smaller than the threat
field because it reuses the threat field's cached projections and the existing
scoring functions rather than introducing new geometry.

### (d) Family-table risk and mechanism-difference

Family row: "Chase VP / play-to-score weights" — standing verdict **built, held,
does not convert under the durability wall**. Mechanism-difference: `SWEG_AM_CHASE_VP`
was a *single-turn, single-sided, faction-scoped target multiplier*. The value
field is a *two-sided multi-round substrate that drives movement and preservation*,
not just target selection, and both armies consult it. That is a genuine
mechanism change on all three axes (horizon, sidedness, consumer set).

**Honest risk, stated in advance:** the value field is the one layer that could
actually move the wall, *because the wall is a horizon artifact* — but it is also
the one whose sign is most genuinely uncertain, for the symmetric reason. It
equally tells the *durable* side "hold the marker you will survive on," which
reinforces exactly the survivor-uptime over-reward. It escapes the closed-matrix
wash (both sides consult it) but may still bank to the durable side if durable
units realise more of their projected value than fragile ones do. This is the
same posture the threat and terrain proposals take: the justification is fidelity
of play plus being the substrate Stage-2 pricing will need, and the falsifier is
behavioural, not the headline.

### (e) Emergent behaviours (named concretely)

- **Late-game objective flip** — a unit preserved (low current value on a
  contested flank, high future value elsewhere) repositions in round 3–4 to
  contest the round-5 scoring step rather than dying early for nothing.
- **Claim-and-bank-then-leave** — a sticky-objective unit banks its marker and
  the field then values it *off* that marker (future value is elsewhere), so it
  redeploys instead of dying in place; the claim-and-bank lever failed precisely
  because it had no horizon to tell the body to leave after banking.
- **Refuse a dead flank** — once a flank's realised value is provably lower than
  its threat cost over the remaining rounds, the field stops attracting
  commitment there (the multi-round form of not throwing good units after bad).
- **Fragile-side denial play** — Astra Militarum reasoning "I will be dead by
  round 4, so I contest the durable unit's marker *now* to deny its round-5 hold"
  rather than trying to survive on it — a multi-round play none of the refuted
  single-round levers could express.

### (f) Falsifiable instrument

Per faction, the **realised-versus-projected value ratio** and the
**committed-to-dead-value rate**: how often a unit ends its activation moving
toward a position whose realised victory-point yield over the remaining rounds was
below its threat cost. The layer must reduce that rate. Sharper pole-specific
falsifier: Astra Militarum's **round-5 objective-contest rate** and the
Astra-Militarum-versus-Death-Guard cell win rate — if the horizon lets the fragile
side trade for denial, that cell moves toward real; if the wall banks it, the cell
does not, and the layer is fidelity-only (still worth shipping, per the threat
proposal's standard, but not a headline lever). Judge on these, not on the gated
mean absolute error alone.

### (g) Build order and dependencies

**Composes on the threat field** (needs its cached incoming-damage projection for
the contestability discount) and on nothing else new — objectives and secondaries
already exist. So: **build after threat, before Layers B and C**, which both read
the value field. It is the first thing to build once threat lands because it is the
horizon the other two need.

---

## Layer B — THE TRADE / EXCHANGE EVALUATOR (one-ply, symmetric threat)

The most-cited concept in competitive play, and the one that fixes a named,
verified misplay class. When a unit commits (charge or exposed move), price **what
dies on both sides** by running the opponent's best reply through the *same*
expected-wounds math — the threat field used symmetrically.

### (a) Evidence it is missing

- Charge scoring reads *only the target's own* melee threat (`score =
  value / (1 + threat_against_target)`, verified in `code/strategy.py`) — no
  army-level accounting of the return blow, no notion of trade efficiency.
- The Chaos Daemons pilot (PILOT_PROTOCOL §"why this exists"; ledger REFUTED
  entry for `SWEG_MELEE_HOLD_OBJECTIVE`) — Khorne melee **futile-charging a
  Toughness-12 brick it cannot crack, throwing a tied game**. A trade evaluator
  that priced "this charge kills nothing and my unit dies to the reply" would
  re-target to a crackable enemy.
- Uncoordinated pile-ons and futile charges are on the threat proposal's own
  board-read failure list; the two-Berzerker case (charging one of two adjacent
  squads with no awareness of the second) is a trade-blindness case.

### (b) Real-play grounding

Trading is named "one of the cornerstones of a game where one of the goals is to
remove your opponents assets." Trading up is charging a cheaper unit into a dearer
one and destroying it; a good trade "kills enough to cover its cost or can trade
up and kill more than what you paid for"
([Bell of Lost Souls, Understanding Trades, Baits & Bricks](https://www.belloflostsouls.net/2025/12/warhammer-40k-tactics-understanding-trades-baits-bricks.html);
[Frontline Gaming, 40k Lingo](https://frontlinegaming.org/2022/03/14/all-the-warhammer-40k-lingo-you-need-to-know/)).
The attrition-role framing is the same idea at the army scale: "every unit is
considered expendable, so the army trades pieces efficiently — if sacrificing a
unit denies the opponent scoring or gains an objective, it's a win"
([Goonhammer, Unit Roles: Attrition](https://www.goonhammer.com/unit-roles-in-9th-edition-attrition/)).

### (c) Composition

- **Reads** the threat field *symmetrically*: my expected damage out (existing
  `_ranged_expected_wounds`, `code/simulator.py:14299`; `_kill_potential_wounds`,
  `code/strategy.py:1812`; the melee arithmetic in `score_charge_target` around
  `code/strategy.py:1960`), then the opponent's best reply computed with the same
  helpers against the position I would end in. The two-dice charge gradient
  already exists as the coarse success table at `code/strategy.py:1975`.
- **Prices the exchange in value, not just wounds:** a trade's worth is
  (value I remove) minus (value the reply removes from me), read from the **value
  field's per-unit dual** (Layer A). This is why Trade composes *on* the value
  field: "kills more than what you paid for" is a value comparison.
- **Consumers:** charge target *re-selection* (pick the crackable target, not the
  brick) and exposed-commit pricing. Deliberately **not** a charge suppressor —
  see the risk note.

### (d) Family-table risk and mechanism-difference

Two graveyard hazards, both avoidable if scoped correctly:

1. **Blanket charge-blocking is REJECTED** — `SWEG_AM_CHARGE_DISCIPLINE`
   (−2.41, reverted): "a no-damage charge still ties a melee threat in
   Engagement Range, eats its activation, and contests ground." So the trade
   evaluator must **re-target, never freeze**: it moves the charge to a better
   trade, it does not cancel commitment. A do-not-re-attempt comment already
   guards the generic block in `_do_charge`.
2. This is the **highest-risk layer for the durability wall**, because
   trade-efficiency *is* what the wall rewards — the durable side has better
   trades by construction (its bricks do not die). Mechanism-difference that
   makes it worth building anyway: the value is in the *fragile-side* behaviours
   it unlocks — **refusing the uncrackable trade** (the exact Chaos Daemons
   misplay) and **baiting** (offer a cheap unit to draw the durable unit out of
   position), neither of which the durable side benefits from. The trade
   evaluator is two-sided arithmetic whose *useful asymmetry* falls on the
   fragile side; the durable side already trades well.

### (e) Emergent behaviours

- **Refused flank** — decline the bad trade on the durable flank; commit where
  the trade is positive.
- **Bait / refused charge into a brick** — a cheap unit offered forward to draw
  the durable unit off its objective; the fragile army does not charge the brick
  it cannot crack (the Daemons game stops being thrown).
- **Trade-up target-swaps** — the two-Berzerker case priced: charge the squad
  whose death is worth more and whose reply is survivable.

### (f) Falsifiable instrument

**Futile-charge rate** (charges whose expected enemy wounds are ≈ 0) and
**adverse-trade rate** (commits where priced value-lost exceeds value-gained),
per faction. The layer must cut both. The pole falsifier is the Chaos Daemons
under-pole specifically: the ledger already has the deterministic
board-read harness (`scripts/diag_pilot_am_vs_ik.py`, seed-exact) — re-read the
thrown Daemons seeds and confirm the futile charges become crackable-target
charges. If the behaviour changes but the cell does not move, it is fidelity-only.

### (g) Build order and dependencies

**Composes on the threat field (symmetric reply) and the value field (trade
priced in value).** Build **after Layer A**. It is second because it is the
highest real-play grounding and fixes a named misplay, but it needs the value
field to price a trade correctly.

---

## Layer C — THE JOB / COMMITMENT LAYER (army-level assignment, cross-round)

The integrator. Explicit army-level task allocation — hold X, screen Y, hunt Z,
deny W, run this action — as an assignment problem over units × jobs, priced by
the threat field (job cost) and the value field (job reward), and **persisted
across rounds**. This is the principled replacement for the five-string
`pick_army_plan`.

### (a) Evidence it is missing

- `pick_army_plan` is the whole army-level layer and it is crude (§0). It biases
  activation *order* and applies `_plan_objective_bias` / `_plan_engage_bias`
  multipliers, but it assigns no unit to any job.
- **The persistent-nomination lesson** (`SWEG_PERSISTENT_NOMINATION`, held):
  cross-round *commitment mattered* — the one-phase focus-fire gate "never
  fired" (demanded ~22 wounds in a single phase, a bar bricks never clear),
  while the persistent version fired in 98.8 percent of shooting phases. But it
  persisted **one** job (kill this brick) and still banked to the durable side.
  The finding to carry forward: persistence is the right shape, a *single* kill
  job is the wrong scope.
- Scattered activations and uncoordinated pile-ons (threat proposal board-read).

### (b) Real-play grounding

Real armies allocate roles pre-game and hold them: "identify what units you want
alive in the late stages… protect these units" and build a gameplan around fixed
roles ([Grimhammer, Build a Gameplan](https://grimhammertactics.com/40k-tactics-how-to-build-a-gameplan-for-competitive-40k-missions/)).
Force-disposition thinking assigns priority assets to jobs (hold, screen,
hunt, action-monkey) and the attrition doctrine spends expendable pieces on
denial jobs deliberately ([Goonhammer, Unit Roles: Attrition](https://www.goonhammer.com/unit-roles-in-9th-edition-attrition/)).

### (c) Composition

- A **units × jobs assignment**: jobs are drawn from the value field (each
  high-value marker spawns a hold/contest job; each secondary spawns an action
  or denial job) and from the threat field (each dangerous enemy spawns a
  hunt/screen job). Each (unit, job) pair is priced = job reward (value field) −
  exposure cost (threat field) − mismatch penalty (unit role vs job, read from
  `code/roles.py`). Solve greedily (the existing activation loop already sorts
  units; this replaces the sort key with an assignment).
- **Persistence:** jobs carry a unit nomination on army state across rounds
  (the `SWEG_PERSISTENT_NOMINATION` `Army._persistent_nom_uid` pattern
  generalised to a jobs table), re-solved only when a job completes or its price
  inverts.
- **Consumers:** `pick_army_plan` becomes "solve the jobs board"; per-unit intent
  reads its assigned job; activation order (Layer F) sequences jobs.

### (d) Family-table risk and mechanism-difference

Family row: scoped/neutral piloting + the persistent-nomination held verdict.
Mechanism-difference: nomination was *one* job (kill the brick) and it banked
because the durable side out-killed the field's grind. The jobs board's escape is
that it lets the AI **choose not to fight the brick at all** — assign fragile
units to **denial and scoring jobs elsewhere** and simply *leave the durable brick
alone*, starving it of victory points. The whole refuted on-table family attacked
the durable brick from the *fight* side (kill it, hold against it, screen it,
out-position it) and the wall banked every one. The jobs board is the first
mechanism to attack it from the *avoid* side: don't trade into the thing the
scoring over-rewards; go score where it isn't. Whether that converts is honestly
uncertain (the durable side runs the same solver and defends its markers), but it
is a genuinely unexplored direction, not a re-run of a settled verdict.

### (e) Emergent behaviours

- **Refused flank / castle-then-break** — early rounds assign hold jobs
  (castle); late rounds the value field re-prices and the solver reassigns to
  hunt/contest jobs (break). The posture change is emergent from re-pricing, not
  a scripted phase.
- **Coordinated alpha** — the assignment concentrates the round's activations on
  one flank's jobs (the alpha strike `pick_army_plan` was written to produce but
  cannot guarantee).
- **Deliberate denial trades** — a fragile unit assigned a deny job spends itself
  to strip the durable side's marker, priced as worth more than the body.

### (f) Falsifiable instrument

**Job-coherence rate** — fraction of activations that advance their assigned job
versus scatter — and **cross-round job persistence** (how many rounds a job's
nominee holds before completion or re-pricing). A working jobs board raises both
over the `pick_army_plan` baseline. Pole falsifier: does the fragile side's
*avoid-the-brick* assignment raise its scoring in the durable matchups without
raising its casualties — i.e. does it score where the brick isn't? Instrument the
victory-points-scored-away-from-the-durable-unit metric.

### (g) Build order and dependencies

**Depends on both Layer A (job reward) and Layer B (trade pricing for hunt/deny
jobs).** Build **third**, as the capstone integrator. It has the highest emergent
ceiling but the most dependencies, so it must come last of the three.

---

## Layer D — SPACE-CONTROL / SCREENING (rejected as a general layer; one sliver kept)

**Evaluated and mostly rejected.** Seed 4 proposed zone denial priced as area,
"emerging from threat+value composition rather than the rejected screen-nudges."

### Why it is rejected as a substrate

The screen/space family is the **most thoroughly refuted region of the entire
graveyard** — five independent levers, all deleted: `SWEG_SCREEN_AI` (decisively
wrong-direction, every gunline worse, every melee over-pole better),
`SWEG_TANK_SCREEN` (+0.49 wrong-direction, craters the target under-pole),
`SWEG_GUNLINE_HOLD`, `SWEG_MASS_BODIES`, `SWEG_FOCUS_MELEE`. The ledger's verdict
is explicit and load-bearing: "you cannot out-position, out-hold, out-shoot, or
out-screen a melee army the scoring over-rewards for winning contested markers…
the sim cannot separate dedicated screen-chaff from objective-bodies (no surplus
chaff in the representation), so even screening loses the objective game."

The seed's mechanism-difference claim — "priced as area from the fields rather
than a nudge" — does **not** clear the family verdict. Re-pricing the *same*
interpose-a-body-on-the-charge-lane action off two fields instead of one does not
change the outcome the ledger measured: the body pulled back to screen is the
body that was holding the objective, and the melee takes the abandoned marker
anyway. "It's priced better" is the "it's a bit narrower" that LEVER_PROTOCOL §2
forbids. **Do not re-enter this graveyard.**

### The one sliver worth keeping — reserve/deep-strike denial

There is a genuinely different mechanism inside seed 4 that the refuted family
never touched: **denying the opponent's reserve/deep-strike arrival by controlling
area**, the real 9-inch-bubble screen. Every refuted lever was a *charge-lane*
screen (interpose against a melee threat already on the board). Reserve denial is
a different thing — it denies the opponent's *alpha* by making arrival zones
illegal, and its cost is not "abandon an objective," it is "spread out."

- **Evidence:** the deploy-AI reserve split is faction-blind and over-reserves
  (ledger, "NOTED TO FIX LATER", `simulator.py` ~7404) — the arrival side is
  known-crude; the *denial* side (blocking arrival by proximity) is likely
  unmodelled. Worth a read-only instrument before any build.
- **Real-play:** "each of your models has a 9-inch bubble that protects from deep
  striking… two units of 5 infantry can screen off the entire width of the board";
  and the counter, the "wrap and trap" where the screen itself becomes the target
  ([Goonhammer, Screening Tactics](https://www.goonhammer.com/start-competing-how-to-screen-everything)).
- **Composition + dependency:** this reads **terrain geometry** (arrival must be
  in a legal, visible zone) far more than the threat field, so it is a **terrain
  T2/T3 rider, not a threat rider** — gate it behind wall collision and line of
  sight, and instrument-before-build (does reserve denial even occur at a
  frequency that matters, given the archetype lists' reserve usage? The
  `SWEG_REEMBARK` and `SWEG_PROBE_RESERVE` history says reserve mechanics fire
  rarely on this frame — check first).

**Disposition:** reject space-control as a general layer; keep reserve-denial as a
narrow, instrument-first candidate downstream of terrain. Rank low.

---

## Layer E — RESOURCE / ATTRITION BUDGET (consolidated into the value field)

**Consolidated, not built separately.** Seed 5 proposed units as spendable
resources with a victory-points-per-point-lost efficiency and a
preservation-versus-expenditure posture by game phase.

This is real and well-grounded — "the expensive unit can impact the game by merely
existing… threatening areas of the board and allowing you to control the tempo,"
and "every unit is considered expendable, so the army trades pieces efficiently"
([Goonhammer, Unit Roles: Attrition](https://www.goonhammer.com/unit-roles-in-9th-edition-attrition/)).
It names the late-game body-starvation the boards show (Astra Militarum ground out
before the scoring rounds).

But it is **not a separate substrate.** A unit's spend/preserve value is exactly
the **per-unit dual of the value field** (Layer A(c)): its expected remaining
victory-point contribution, discounted by its survival probability from the threat
field. Building a second surface for it would duplicate the value field and the
threat-tolerance the threat proposal already derives. The right move is to expose
the value field's per-unit scalar as the resource budget and let Layer B (trade)
and Layer C (jobs) consume it — "is this unit worth spending on this trade / this
job?" is answered by that one number. **Fold it in; do not build a fifth layer.**
This is flagged so a future session does not re-propose it as novel.

---

## Layer F — TEMPO / ACTIVATION-ORDER (mostly subsumed; thin capstone only)

Seed 6 proposed commit-order economics across the round: who activates first,
activation-order optimisation against the plan.

### What is already covered

Two of the three pieces are already claimed by other layers:

- **Inter-turn tempo (going first/second) is a settled graveyard.** The entire
  going-second family — `SWEG_OVERWATCH_MOVE`, `SWEG_KITE_MOVE`,
  `SWEG_PROBE_RESERVE` — is REJECTED, and the "frame-confounded" reopen was
  re-screened on the clean sc59a frame and **closed for good (2026-07-08)**: the
  durable side banks reactive fire. Do not touch going-second.
- **Mid-turn sequencing falls out of the threat field already.** The threat
  proposal's owner-refinement #1 ("kills edit the field mid-turn — sequencing
  falls out"; the planned-kill discount; the shoot-before-move "unlocks space"
  term) puts intra-turn kill-then-move sequencing on the threat field. The jobs
  board (Layer C) supplies the activation *ordering* against the plan.

### The thin residual worth a capstone

What is left is an explicit **activation-order optimiser**: given the jobs board,
choose the order of activations that maximises the round's realised value — shoot
the screen before charging through the gap it was blocking; issue the buff before
the buffed unit acts. This is a small optimisation on top of Layers A+C, not a
substrate of its own.

- **Evidence:** `pick_army_plan` biases order crudely (score-only sort under
  vanilla; plan-biased sort otherwise, `simulator.py:12037`); the ordering is a
  heuristic, not an optimisation.
- **Real-play:** controlling tempo is "trades on your terms" and forcing the
  opponent to react ([Grimhammer, Controlling Tempo](https://grimhammertactics.com/40k-tactics-controlling-tempo-in-competitive-40k/)).
- **Family risk:** low, *provided* it stays intra-turn ordering and never
  re-opens going-second. Mechanism-difference from the rejected family: those
  changed *which turn* an army acts reactively; this changes *the order of an
  army's own activations within its turn* — a different mechanism entirely.
- **Falsifiable instrument:** per-round realised-value uplift from re-ordering
  versus the plan-sorted baseline; the "acted-out-of-order-and-wasted" rate
  (a unit that moved before the shot that would have cleared its path).

**Disposition:** build last and thin, as an ordering pass over the jobs board;
most of seed 6 is already delivered by the threat field and Layer C.

---

## Ranked roadmap

Everything below assumes the two approved layers land first: the **threat field**
(the shared incoming-damage substrate the rest read) and **terrain realism**
(line of sight + wall collision). The value field needs the threat field's cached
projection; the reserve-denial sliver needs terrain. Build order:

| # | Layer | Depends on | Why here | Honest metric expectation |
|---|---|---|---|---|
| 1 | **Value field** (A) | Threat field | The keystone: the missing multi-round horizon, the dual of the threat field, and the substrate Layers B and C both read. The one layer that could move the wall *because the wall is a horizon artifact*. | Sign genuinely uncertain (may bank to durable via survivor-uptime). Ship on fidelity + Stage-2-substrate grounds; judge on the value-realisation and round-5-contest instruments. |
| 2 | **Trade / exchange evaluator** (B) | Threat field (symmetric reply) + value field (trade priced in value) | Highest real-play grounding; fixes the named futile-charge misplay class (the thrown Chaos Daemons game). Its useful asymmetry falls on the fragile side (refuse/bait). | Highest wall risk (trade-efficiency is what the wall rewards) — but the fragile-side behaviours are genuine. Judge on futile-charge and adverse-trade rates. |
| 3 | **Job / commitment layer** (C) | Value field + trade evaluator | The army-level integrator that replaces the five-string `pick_army_plan`; highest emergent ceiling (refused flank, castle-then-break, deliberate denial). First mechanism to attack the durable brick from the *avoid* side. | Uncertain but unexplored (not a settled re-run). Judge on job-coherence and score-away-from-the-brick metrics. |

**Lower tier, deliberately deferred:**

- **Reserve/deep-strike denial** (the one kept sliver of seed 4) — a **terrain
  T2/T3 rider**, instrument-first (confirm reserve denial fires at a frequency
  that matters on this frame before building). Reject general space-control /
  screening outright: it is the most-refuted graveyard region and the seed's
  re-pricing does not clear the family verdict.
- **Activation-order optimiser** (the thin residual of seed 6) — build last as an
  ordering pass over the jobs board; most of the tempo seed is already delivered
  by the threat field's mid-turn recompute and Layer C's ordering. Never re-open
  going-second.
- **Resource/attrition budget** (seed 5) — **do not build**; it is the per-unit
  dual of the value field and is delivered by Layer A(c).

### Why this order, in one line each

- **Value first** because it is the horizon the whole architecture lacks and the
  substrate the other two consume — nothing downstream can be built without it,
  and it is the only layer whose mechanism directly targets the wall's root
  (no unit reasons about the scoring rounds).
- **Trade second** because it has the strongest real-play mandate and the
  clearest named-misplay fix, but it must price trades in *value*, so it waits on
  Layer A.
- **Jobs third** because it is the integrator that turns the two fields into
  coherent army behaviour and has the highest emergent payoff, but it depends on
  both and so must be the capstone.

### The standing honesty caveat (carried from the threat and terrain proposals)

None of these three is expected to be a guaranteed headline mean-absolute-error
lever. The durability-over-reward wall has banked every on-table play improvement
of the campaign, and it may bank these too — they operate on both sides, which
escapes the closed-matrix *wash*, but two-sided is necessary, not sufficient. The
justification is threefold and explicit: (1) **fidelity of play** — real armies
reason over the mission across rounds, trade, and allocate jobs, and the sim does
none of it; (2) these are the **substrates Stage-2 pricing will consult** — a
points equation fitted over a sim that plays with a horizon is a better equation;
(3) the value field is the one honest shot at the wall's *root*, because the wall
is a horizon artifact and this is the horizon. Each layer is judged on a
**behavioural falsifier** — the value-realisation rate, the futile-charge rate,
the job-coherence rate — **not on the headline alone**, exactly as the two
approved layers require. Instrument before building each one (LEVER_PROTOCOL §1),
gate default-off and byte-identical-off, and screen the consumers individually.

---

## Sources

- Bell of Lost Souls — *Understanding Trades, Baits, & Bricks* — https://www.belloflostsouls.net/2025/12/warhammer-40k-tactics-understanding-trades-baits-bricks.html
- Goonhammer — *Start Competing: Screening Tactics* — https://www.goonhammer.com/start-competing-how-to-screen-everything
- Goonhammer — *Start Competing! Your Guide to Warhammer 40,000 Tactics and Strategy* — https://www.goonhammer.com/start-competing-your-guide-to-getting-better-at-warhammer-40000/
- Goonhammer — *Unit Roles in 9th Edition: Attrition* — https://www.goonhammer.com/unit-roles-in-9th-edition-attrition/
- Goonhammer — *Hammer of Math: 10th Edition Primary Scoring Statistics* — https://www.goonhammer.com/hammer-of-math-10th-edition-primary-scoring-statistics
- Goonhammer — *Hammer of Math: Examining 40k Objective Scoring* — https://www.goonhammer.com/hammer-of-math-examining-40k-objective-scoring-in-2021/
- Grimhammer Tactics — *How to Build a Gameplan for Competitive 40K Missions* — https://grimhammertactics.com/40k-tactics-how-to-build-a-gameplan-for-competitive-40k-missions/
- Grimhammer Tactics — *Controlling Tempo in Competitive 40K* — https://grimhammertactics.com/40k-tactics-controlling-tempo-in-competitive-40k/
- Frontline Gaming — *All The Warhammer 40k Lingo You NEED To Know* — https://frontlinegaming.org/2022/03/14/all-the-warhammer-40k-lingo-you-need-to-know/
</content>
</invoke>
