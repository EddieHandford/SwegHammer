# Design: the whole-game strategic planner

## Goal (plain language)

Today the simulator's decision engine picks each unit's move one unit at a time,
optimising the value of the current turn. It has no plan for the whole game. This
is the single unfixed cause of the durable-army over-reward: against a durable
objective-holder (Death Guard sits at +16 percentage points over its real win
rate), the correct real-play counter is *not* to fight it — it is to concede the
markers it holds, refuse the attrition, and win the game on secondary objectives
and the objectives it cannot reach. That is a whole-game strategy — deciding
*which fights to decline* and *what to race for* — and a one-unit-at-a-time value
picker cannot represent it.

This document designs a thin **strategic planner** that sits above the existing
per-unit decision engine and, once per army per turn, allocates the army across
competing uses of a unit's activation — contest a primary objective, score a
secondary objective, hold/defend, or concede — measured in one common currency of
victory points, over the remaining rounds of the game. The planner does not
replace the per-unit mover; it *directs* it.

**What will be different after this lands:** the fragile side of a durable matchup
will commit *real* units (not only spare cheap bodies) to scoring secondaries and
taking uncontested objectives, and will stop feeding units into unwinnable
attrition against a durable holder. The measurable consequence is the durable
over-poles deflating while the aggressive, secondary-reliant under-poles (Astra
Militarum, T'au) rise — a redistribution, not a uniform lift.

**Why this approach over the alternatives:** every per-turn lever tried this
session (devastating-wounds valuation, secondary position-fix, mobility denial,
gang-deny, coordinated contest) washed or backfired, because each improved play
*symmetrically* and symmetric improvement banks to the durable side. Three
independent experiments this session proved the bottleneck is faithful durability
expressed as Objective-Control persistence, not any single missing mechanic. The
only remaining path that is asymmetric *by nature* — because the fragile side's
correct whole-game plan genuinely differs from the durable side's — is a planner
that changes the objective function from "maximise this turn's value" to "maximise
whole-game victory-point margin, choosing which fights to decline."

This is Stage 1 work (it tunes simulator behaviour, not the points equation). See
[`COUNTERPLAY_BEHAVIOR_SPEC.md`](COUNTERPLAY_BEHAVIOR_SPEC.md) for the grounding
evidence and the behavioural-test method this design commits to.

The objective function in Section 2 is version 3. It was rebuilt after an
adversarial four-lens review (game-theoretic soundness, buildability, calibration
risk, real-play fidelity) found three fatal flaws and two over-swing holes in the
first draft. The review's findings and the open decisions it surfaced are recorded
in Section 9.

---

## 1. The core idea: one currency, two horizons

The parked layer program (branch `claude/layer-stack-research`, all my own commits)
already did the hard half of this: it prices individual unit-actions in **measured
victory points**. Its exchange rate `_trade_vp_per_wound` (0.0152 victory points
per enemy point destroyed, fitted from eighteen thousand games by
`scripts/fit_exchange_rate.py`) makes killing, holding, and scoring directly
comparable — all in victory points. That is the currency.

What the layer program never had is the **second horizon**. Its job/commitment
channels (kill, hold, survive, deny) are still chosen *per unit, per turn*: each
unit greedily picks the channel with the best value for its own activation. That
is exactly why turning the whole calibrated stack on made the durable factions
*dominate* (Imperial Knights ran to a 75.3% win rate): honest per-turn pricing
tells a brick "commit, you win this fight," and every brick does. Per-unit honesty
amplifies the durability over-reward.

The planner supplies the missing horizon: a **whole-game victory-point forecast**
and an **army-level allocation** built on top of the same currency. Neither half
works alone — the layer program alone banks to durability; a planner without a
measured currency has nothing to allocate. Together they can express "this unit is
worth more scoring Cleanse for the next three rounds than dying to a Death Guard
blob," which is the whole tape.

---

## 2. The objective function (version 3)

### 2.0 Two invariants that make the whole thing coherent

Two decisions from the review are load-bearing and stated once, up front:

- **The decision variable is a per-unit role assignment**, `role(unit)`, coupled
  only through a shared enemy-responder pool. There is **never** an enumerated
  "army positioning" to score or take a variance over — that would be a game-tree
  search and is forbidden (it is also what the first draft accidentally
  reintroduced).
- **The objective is denominated in victory-point MARGIN** — my victory points
  minus the opponent's — over a single horizon `H` (rounds remaining) with one
  discount `γ` applied to *every* term. Every estimator call is tagged **my-side**
  or **opponent-side**; an opponent-side quantity enters the sum with exactly one
  sign flip (the opponent's loss is my margin gain). Without this the objective
  would be adding victory points I gain to victory points the opponent forgoes as
  if they were the same number — the incoherence that sank the first draft.

### 2.1 Each unit contributes the ENVELOPE of its roles, never the sum

A unit gets one activation and does one job. So each unit's contribution is the
**maximum** over its feasible roles, not the sum of everything it could threaten.
This one rule fixes the biggest over-swing risk — otherwise a fast unit within
reach of three objectives banks the value of all three though it takes one — and
it makes the opportunity cost symmetric for free: a unit sent forward has
implicitly forgone its own best hold-or-score, because the assignment rejected
that alternative. It also models multi-role optionality correctly (the scarab
example): a single unit threatening a marker *and* a vehicle *and* a screen is one
bundle the opponent answers with one sufficient response to the source unit, not
three separate bills.

The four roles and their per-unit margin, all my-side, `H`-integrated, and
reach-gated:

- **`CONTEST(marker k)`** = `Pr_win(unit, k) · Σ_{h≤H} γ^h · value_projection(unit, k, …)`
  minus the threat-field attrition cost of going there. `Pr_win` is evaluated
  against the marker's **real** defender profile and Objective-Control state —
  **including the strict-out-Control sticky rule** for a Death Guard Worldblight
  marker. Against a durable holder this is near zero, so the term goes negative
  once attrition is subtracted, and **`CEDE` falls out with no special case**.
  This honest pricing is non-negotiable: if the contest estimator is even mildly
  optimistic about evicting a sticky durable holder, the planner regenerates the
  unwinnable contest and donates bodies — the exact failure this design abandons.
- **`HOLD(marker k)`** = the `H`-integral of `[` opponent `value_projection(k` if I
  do not defend `)` − opponent `value_projection(k` if I do defend `)]`. This is
  the **concede / defensive term, carried per unit** — the review's single most
  important addition. It is nearly free (same estimator, sides swapped) and it
  makes over-extension *visible*: pull every unit forward and none is assigned
  `HOLD`, so the opponent's projected scoring on my now-open markers stays in the
  margin as their gain. Without it the objective was one-sided and rewarded
  over-commitment — the same disease this project exists to cure, pointed the
  other way.
- **`SCORE(card)`** = `card_victory_points_per_round · scoring_rounds_remaining ·
  reachable(unit → goal)` minus attrition, using the **per-unit card geometry**
  already in `_assign_card_pursuit` / `_board_pursuit_goals`. It must subtract the
  offensive output the unit forgoes by acting, plus a survive-to-completion
  discount from the threat field (a mid-action unit is locked and fragile). Army-
  level `score_position_delta` is **not** used per unit (it is an O(units²)
  leave-one-out); it stays the army-level verifier for behavioural test T2.
- The **kill component** of any role is priced through the already-built mirror
  `_trade_our_return` × `_trade_vp_per_wound`, against the target's real profile so
  a non-credible threat (a Carnifex bouncing off a Redemptor) prices near zero.

### 2.2 The opponent's answer is a hard minimum under a capacity budget

The opponent answers to **minimise my margin**, under a **capacity budget** `k`. The
owner's guidance fixes what `k` is and where its weight sits. The **dominant** answer
channel is what the opponent does on its **own following turn** — the un-activated
units that can reach and answer a threat, each answering at most one (its single
activation). Its **reactive stratagems on my turn** (Fire Overwatch, Go to Ground,
Rotate Ion Shields, Smokescreen) are a **secondary, smaller** channel — most factions
have only a few and the command-point pool is small — but still modelled: `k` adds the
reactions the opponent can afford from its live `command_points` pool (already tracked
and genuinely spent by exactly those stratagems — initialised to `STARTING_CP`,
awarded each Command phase, capped at six). So

```
k = (opponent's next-turn reachable un-activated units)    # dominant
  + (reactive-stratagem answers affordable from command points)   # modest add-on
```

The opponent answers **greedily, highest-honest-value first, until `k` is
exhausted**; every threat past `k` **converts at its honest value**. Because the
dominant channel is the opponent's *next turn*, the response model is a one-ply
forecast of that turn — the same window the concede term and (later) the two-move
combo already reason over. The response option set **explicitly
includes "ignore"** — so a big-but-ignorable threat (a durable brick's "I just sit
here," a non-credible charge) earns nothing regardless of how large it looks,
which is what stops durable elites re-inflating through the "you had to answer my
brick" channel.

This is a single-semantics worst-case-under-budget operator — **not** the first
draft's incoherent "minimum, softened to probabilistic." The capacity cap, not a
probability, is what stops a competent opponent collapsing every plan's value to
zero: beyond `k` threats, the remainder score.

Each answer is priced as the **marginal** delta in that answerer's own output —
`OpportunityLoss(u)` = its best static alternative job on the current board minus
its value answering my threat. This is **opponent-own-production only** (no
"denies me" component — that keeps it disjoint from any future follow-up credit);
computed **once per responder** via `value_top_marker_index` run for the enemy
(never by re-invoking the planner, so no infinite regress), with the threat field's
allocation **pinned to the opponent's current allocation**. It is **allowed to be
negative and never floored** — a negative answered-branch is a genuine "I dangled
bait worth more than it pulled off," which the minimising opponent correctly
exploits. `value_projection` (a two-sided "whoever holds it" number) is **forbidden
inside `OpportunityLoss`**; use a one-sided opponent-production leaf, or the
double-count returns.

The **idle-responder guard** the owner insisted on is now automatic: a spare/idle
answerer has `OpportunityLoss ≈ 0`, so "chuck a Carnifex up the table" scores near
zero on *both* branches — near-zero value when ignored (low realisable
probability), near-zero forcing value when answered (an idle blocker gave up
nothing). Both guards are needed; either alone leaks.

### 2.3 Saturation is one army-level coupling term

"A distraction is worth something only when the opponent is capacity-constrained"
is a property that does **not** decompose per unit — it is the dual of the shared-
responder budget. In version 0 it is one army-level scalar:

```
SAT = my_answerable_forward_threats / enemy_reaction_capacity
# enemy_reaction_capacity = next-turn reachable un-activated units (dominant)
#                         + reactive-stratagem answers affordable from command points (add-on)
```

The distraction reward ramps from ~0 toward a threat's honest value only as `SAT`
crosses 1: below saturation a forced answer is credited only its (small)
`OpportunityLoss`; above it, the surplus threat scores its full value — threat
saturation, emergent rather than assumed. In later versions, replace the scalar
with the real greedy reachability-sparse cover and use its dual, *if* the scalar
washes the behavioural tests the way the coordinated-contest lever did.

### 2.4 Threat granularity: Objective-Control, sufficiency-capped

A marker contested by ten gaunts is **one** threat worth **one** marker — bodies
sum into a single contest and the greedy assignment decrements that marker's
remaining Objective-Control need. Kill-threats are capped by the unit's actual
shot/attack budget, so a gunline cannot project more killing than it can output.
This is what stops a horde swinging between wild under- and over-reward on an
unstated pricing granularity.

### 2.5 The objective, and how it is solved

```
Value(assignment) =
    Σ over my units u   marginal_margin(u, role(u))            # my-side: CONTEST / HOLD / SCORE, envelope, H-integrated
  + Σ over forward threats beyond opponent capacity   honest_value(t)   # saturation reward (my-side)
  + Σ over answered forward threats   OpportunityLoss(responder)        # forcing value (opponent-side, sign-flipped, may be negative)
```

Solved **greedily**: sort units by their envelope margin, assign top-down,
decrement each objective's remaining Objective-Control need as it is filled
(sufficiency — never pile past what wins the marker). One role per unit plus the
envelope caps a plan's value at what its units can *simultaneously realise*, which
is the root fix for both the mobile threat-count over-reward and the multi-role
double-count.

### 2.6 What is deferred, and why it stays disjoint when it lands

- **The two-move combo** (bait a response, exploit the opening next turn) is
  **off in version 0** — the review was unanimous. When added it is taken as an
  **expectation over the near-optimal response set** (a single hard argument-of-
  the-minimum flickers discontinuously as the opponent's assignment ties break),
  discounted by `γ` and by the **same** probability-the-opponent-answers used in
  the base minimum — never as a static forced response while ply one is imperfect.
  It credits **only my incremental production** in the vacated zone; the opponent's
  forgone production there is already booked in `OpportunityLoss`. Tagging every
  victory-point source by owner-side keeps the two credits genuinely disjoint. It
  ships behind its own realised-opening gauge (Section 5).
- The **ranged-threat-as-positioning channel** and the **deep-strike-opening threat
  class** are version-N (owner's call: defer the ranged channel, accepting that
  version 0's redistribution lands on mobile shapes first and the gunline under-poles
  T'au and Astra Militarum come with the ranged channel later). The **score-gap-and-
  rounds risk transform is IN version 0** (owner's call) — see 2.7.

### 2.7 The risk transform (in version 0)

`Value(assignment)` above is expected margin, and expected value is the wrong
objective in the tails of a race to a fixed threshold: when behind late, only a
high-variance line can still reach the win, and its expected value may be *lower*
than a safe line that reaches a losing score with certainty. So the final plan value
applies a transform keyed on the current score gap and rounds remaining — convex
(variance-seeking) when behind late, concave (variance-averse) when ahead. The
expected-margin terms are unchanged; the transform reshapes only how the assignment
trades certainty against swing near the end of the game. Its inputs (score gap,
rounds remaining) are already tracked; it adds one shape parameter to fit alongside
`k`.

---

## 3. Integration with the existing layers

The planner is an *assigner above executors*, so it reuses the layer program
wholesale. Mapping each existing component to its role:

| Existing component (location) | Role under the planner |
|---|---|
| `_trade_vp_per_wound` (strategy.py ~3028) | **The currency.** Every margin term is denominated through it. Measured, not asserted; safe to inherit as-is. |
| `value_projection` (strategy.py ~2860) | Primary-victory-point estimator for `CONTEST`; its contestability discount already encodes durability *emergently* (tiny for a Knight, large for a Termagant) — the planner must **not** add a separate durability term or it double-discounts the fragile side. |
| `_threat_field_at` — allocation-aware, line-of-sight-consuming (strategy.py ~2557) | The **attrition-cost estimator** for every role; its allocation is **pinned** to the opponent's current allocation inside opportunity-cost so it cannot reopen the recursion. Safe to inherit (its own falsifier passed). |
| Job/commitment channels — kill, hold, survive, deny (strategy.py ~3440+) | The **per-unit executors.** The planner is the "who does what" layer the job layer never had; the channels stay the "how." Not turned on globally — that is the thing that inflated the durable pole. |
| `_trade_our_return` (the mirror: me as projector) | The kill-threat estimator, priced through the currency against real defender profiles. |
| `value_top_marker_index` (strategy.py ~2921), run for the enemy | The opponent's **best-alternative-job** estimator inside opportunity-cost — computed once per responder, static, non-recursive. |
| `secondaries` card geometry — `_assign_card_pursuit` / `_board_pursuit_goals` (simulator.py ~3519 / ~3686) | The per-unit **`SCORE`** goal + estimator. `score_position_delta` stays the army-level T2 verifier only. |
| `pursue_target` + the `_assign_card_pursuit` lifecycle slot (simulator.py ~3519) | The **execution hook.** The planner writes `pursue_target` for real units chosen by margin math; `pick_move_intent` already consumes it at strategy.py ~3725. The planner supersedes the chaff-only `_assign_card_pursuit`, which was measured ineffective precisely because it only ever spent spare chaff. |

The consequence: **the planner does not re-open the composed-stack failure.** That
failure was per-unit greedy channel selection. The planner selects channels army-
wide under a whole-game margin objective, so the durable side's units are told
"hold, you already win" (unchanged) while the fragile side's units are told "cede
and go score" (new). The asymmetry is produced by the allocation, not a per-faction
flag.

---

## 4. Why this is asymmetric by nature — and self-damping against over-swing

Every failed lever this session was symmetric and banked to durability. The planner
is structurally asymmetric because the fragile side's margin-maximising plan and the
durable side's are *different plans*: the durable side is already near its optimum
(hold and grind), and honest pricing keeps telling it to hold; the fragile side is
far from its optimum (it currently trades into durability), and honest pricing tells
it to cede and score. Improving both toward their own optimal plans improves the
fragile side more.

Crucially, version 3 is also **self-damping against the *inverse* miscalibration**
(over-rewarding the fast, multi-threat side), which the first draft was not:

- **Honest, success-weighted value** makes non-credible threats and durable-marker
  contests price near zero, so "spam cheap threats" does not pay.
- **The envelope (one role per unit)** stops a mobile unit banking value for
  everything it can reach.
- **The concede term** charges over-extension.
- **The "ignore" option** denies durable bricks their forcing value.

These are damping forces, not a guarantee. The remaining free parameter — the
capacity budget `k` — is exactly where a residual over- or under-swing would enter,
which is why Section 5 adds gauges aimed specifically at it, and Section 9 flags it
as needing a fit against the tournament data, not a guess.

---

## 5. Behavioural tests and health gauges

The first draft's health signal and the existing behavioural tests are
**structurally blind to an over-swing**, so the review added gauges. All measured
by `scripts/_behavior_check.py` (extended) on eval-faithful Death-Guard-versus-
field games, planner off versus on.

Retained behavioural tests (from `COUNTERPLAY_BEHAVIOR_SPEC.md`):

- **T1 — commits real units:** count of non-chaff units assigned `SCORE` or ceding
  a durable marker to redeploy is greater than zero.
- **T2 — lifts secondary victory points** toward the real 22.7 (from ~11.4).
- **T3 — stops donating into durability:** rate of committing units to *unwinnable*
  Death Guard contests falls; Death Guard cap-hit falls toward the field's 13%.
- **T4 — the asymmetry falsifier:** Death Guard and the durable trio deflate AND
  the aggressive under-poles rise (redistribution, not uniform lift).

Changed and new gauges:

- **Health signal (changed).** *Not* the variance of value across candidate plans —
  against a genuinely durable opponent many plans legitimately tie, and the old
  detector would false-abort a working planner. New signal: (a) the sign and size
  of the best assignment's margin versus the null/greedy plan, and (b) whether the
  top assignment changes any unit's role. "Inert" = *never changes roles AND never
  shows a positive margin*.
- **G-signed (hard gate on the readout).** Track **signed** per-faction error (via
  `scripts/diag_frame.py`'s symmetrised column) in the standard eval readout — the
  mean-absolute-error headline can stay flat while a mobile over-reward and a
  durable deflate cancel on different factions.
- **G-mobile (hard gate before the first screen).** Signed error of the fast multi-
  threat cohort {Aeldari, Orks, Tyranids, Drukhari}: **fail** if any crosses from
  below its real rate to above real-plus-margin.
- **G-realise (hard gate, behavioural).** Realisability ratio = credited-threats /
  threats-actually-executed next turn, per game: **fail** if greater than ~1.3.
  Catches threat over-crediting as a behaviour, before any screen.
- **G-opening (version-N, when the two-move combo lands).** Measured rate at which
  a predicted vacated-zone opening is actually realised in the executed game;
  discount the two-ply term by it.

Only after T1–T4 and the applicable G-gauges pass does the change proceed to a
paired common-random-number screen against the standing anchor, per
[`EVAL_PROTOCOL.md`](EVAL_PROTOCOL.md) and [`LEVER_PROTOCOL.md`](LEVER_PROTOCOL.md):
byte-identical-off verified (zero flips), symmetrised, minimum N per the verdict
rules.

---

## 6. Build plan (phased, each phase small and independently testable)

Version 0 ships with the score-gap-and-rounds **risk transform on** (owner's call),
and with the two-move combo, the ranged-threat channel, and the deep-strike-opening
threat class all **off**. Its threat classes are `{reachable objectives,
killable/damageable enemies, held-secondary goals}`.

1. **Substrate import.** Bring `_trade_vp_per_wound`, `_threat_field_at`,
   `value_top_marker_index`, and the mirror `_trade_our_return` onto the working
   branch behind their existing gates, default-off. Proof: full test suite green,
   byte-identical-off digest match. No behaviour change.
2. **Estimators as pure functions.** Expose `value_projection` and the card
   geometry as victory-point estimators callable with the planner off. No behaviour
   change.
3. **`plan_turn` — allocation, `CEDE`/`CONTEST` with honest sticky-aware pricing.**
   The per-unit envelope assignment over primary objectives, with the concede term.
   Hooked at simulator.py ~3519 (the `_assign_card_pursuit` slot), gated
   `SWEG_PLANNER`, default-off, byte-identical-off, writing `pursue_target`.
   Build both projector lists once at entry and thread them (the global
   `_threat_proj_cache` is single-slot and thrashes across side-swaps).
   Behavioural gate: **T3**.
4. **`SCORE` with real units.** Value the current hand via the card geometry;
   assign real units; execute via `pursue_target`. Behavioural gate: **T1 + T2**.
5. **Whole-game multiplier + saturation coupling + risk transform + tuning.** Add
   the `H` discounting, the `SAT` coupling (capacity from command points + un-
   activated reachable units), and the score-gap-and-rounds risk transform; fit `k`
   and the risk shape parameter. Behavioural gate: **T4 + G-mobile + G-realise**,
   then the paired screen.

Cost target: **O(units · roles · enemies) per side** — the same envelope as the
existing whole-army value scan; profile before any default-on proposal. Each phase
is a separate pull request naming the one before and after it, updating the
standing-rule documentation, and spelling every term out in full.

Later versions, only if the behavioural tests show version 0 cannot bait-and-open
or the named gunline under-poles do not move: the real reachability-sparse cover and
its dual (replacing `SAT`); the two-move combo (behind G-opening); the ranged-
threat-as-positioning channel; the score-gap-and-rounds risk transform.

---

## 7. Risks and open questions carried into the build

- **The capacity budget `k` is the single load-bearing knob.** It prevents value
  collapse *and* sets the whole mobile-versus-durable balance. It must be fit
  against the tournament data, not guessed (Section 9, question 1).
- **Secondary-scoring faithfulness bounds what T2 can show.** If the simulator's
  secondary rewards are themselves too low, the planner correctly computes that
  scoring does not pay and reverts to fighting. Watch T1 versus T2: real-unit
  commitment rising (T1) while secondary victory points do not (T2) localises a
  residual gap to the *scoring*, a parallel dependency the planner cannot fix.
- **`CEDE` is only as good as the honest sticky-aware contest estimator.** If it is
  mildly optimistic about a Worldblight marker, the planner regenerates the
  unwinnable contest. That estimator is validated independently before the planner
  is trusted.
- **The depth-one truncation of opportunity cost is an unmeasured approximation** —
  answering a threat changes the board the responder's alternative job would be
  valued on. Accepted for version 0; revisited only if a behavioural test exposes
  it.
- **Cost.** `plan_turn` is army-level per turn; acceptable behind a default-off
  gate, profiled before any default-on proposal.

---

## 8. What this does not do

It does not touch the points equation (Stage 2). It does not re-price any unit. It
does not add or change a single 10th-edition rule — it is a decision-engine
heuristic, so it carries no rule citation (same class as the existing
`_assign_card_pursuit` and contest heuristics). It does not turn the job/commitment
channels on globally — the one thing proven to inflate the durable pole.

---

## 9. Decisions surfaced by the design review

The four-lens review left five genuine decisions. Three are resolved (owner,
2026-07-15); two remain, with the build's recommended default noted.

**Resolved:**

1. **Capacity budget `k` = next-turn activations (dominant) + affordable reactive
   command points (add-on).** The main way the opponent answers a threat is on its
   own following turn, by activating a reachable un-activated unit (one answer each);
   reactive stratagems on my turn are the minor add-on, bounded by the live
   `command_points` pool. Both read off existing faithful state, not a fitted free
   constant — though the weighting still has a shape parameter to fit in phase 5.
   (Section 2.2.)
3. **Ranged channel: deferred to version N.** Version 0 ships without the ranged-
   threat-as-positioning channel, accepting that its redistribution lands on mobile
   shapes (Aeldari, Orks, Tyranids) first and the gunline under-poles (T'au, Astra
   Militarum) arrive with the ranged channel later. (Section 2.6.)
4. **Risk transform: in version 0.** The score-gap-and-rounds variance transform
   ships in version 0 — variance-seeking when behind late, variance-averse when
   ahead. (Section 2.7.)

**Open (recommended default in italics):**

2. **Hard gates.** *Recommend confirming G-mobile and G-realise gate before the
   first screen* — a passing T4 alone can license an over-swing the same way per-
   unit honesty licensed the durability blow-up.
5. **Candidate generation.** *Recommend reusing the existing mover's top intents*
   as the feasible role set (rather than a new generator, which would silently
   reintroduce a search).
