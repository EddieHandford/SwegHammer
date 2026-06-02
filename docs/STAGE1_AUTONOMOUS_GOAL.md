# Stage 1 autonomous goal — close the calibration loop

This file is the standing mission for a hands-off autonomous run of the SwegHammer
Stage 1 calibration loop. Hand it to a self-paced loop (see "Launch" at the bottom)
and it will pursue convergence across context windows, re-reading
`docs/CURRENT_STATE.md` each wave. It deliberately leans on the canonical procedure
(`docs/AUTO_LOOP_PROCEDURE.md`, the `sweg-wave` skill, `CLAUDE.md`, and auto-memory)
for mechanics rather than restating them, so it stays correct as those evolve.

---

## Mission

Close SwegHammer Stage 1. Drive the headline **noise-gated mean absolute error**
(versus the Warp Friends May-2026 tournament aggregate) below the per-faction noise
floor — every faction inside its band, gated mean absolute error toward zero — and
confirm it holds across a clean re-evaluation. The current headline is 5.98 gated
(4 of 22 factions in band). Done is "below the floor, all factions in band,"
verified twice. When you reach it, **stop and report**; do not keep tweaking a
converged simulator.

## Prime directive — the line you must never cross

Every change must make the simulator a more faithful model of real 10th-edition
rules and real May-2026 tournament play. You may **never** move the metric by
fabricating a multiplier, ability, statistic, proxy flag, or list edit whose only
justification is "it pushes a faction toward its target." The test for every
change: *would this still be correct if it moved the metric the wrong way?* If the
only argument for a change is its win-rate effect, reject it. The noise-gated mean
absolute error is a thermometer, not a steering wheel — you lower it by curing the
simulator's fevers (wrong rules, wrong stats, wrong artificial-intelligence
piloting), never by holding a match to the bulb.

## Current phase — UPDATED 2026-06-02 (USER RULING): the win-rate gap is SIM-FIDELITY, NOT a stats re-fit

**The "re-calibration / re-fit stats" conclusion is KILLED (user, 2026-06-02).** The tournaments use the SAME
GW stats and the SAME points as us. So the per-faction win-rate gap (Imperial Knights ~76% sim vs ~48% real,
the +27) CANNOT be the stats — they are identical inputs on both sides. It is therefore a SIMULATION-FIDELITY
gap: the sim is missing or mis-weighting something about how the game is actually PLAYED and WON. Re-fitting
per-faction stats / overrides / lists to force the win rate would be (a) the metric-tuning the prime directive
forbids — fudging GW's real values — and (b) poison for Stage 2, which prices units FROM those real stats.
**DO NOT re-fit stats/data to chase win rates. This is the Stage-1 premise: fix the SIMULATOR, not the stats.**

**Reframe the 7 frozen-under levers:** six were combat/firepower, which help the stronger combat army
(Knights) → frozen-under. The PATTERN is the diagnosis — the sim decides games too much on COMBAT, too little
on the MISSION. In reality 40k is won on VICTORY POINTS, and a Knight army (few models, no cheap action-doers,
no screens, low total Objective Control) LOSES the VP/mission game despite great combat stats. The sim
under-models that. The missing fidelity is in **HOW THE GAME IS WON — the mission / primary-VP / secondary /
board-control layer, and possibly the one-Unit-per-model representation that over-weights elite combat power
and under-weights model-count board control** — NOT combat, NOT stats.

**The path (Stage-1-faithful): DIAGNOSE then FIX the missing simulation mechanic, no stat-fudge.** Diagnostic
questions: why don't Knights LOSE the VP game in the sim like they do in reality? — Are they out-scored on
PRIMARY (a broad army holds more of the markers)? Do they hold objectives a broad army should be CONTESTING
BACK (a Knight parks on a marker uncontested — is the summed-OC contest / model-count board-control faithful)?
Do they dodge the SECONDARY game (no action-doers — does the sim model that they can't score actions / cards a
broad army can)? Is the one-Unit-per-model representation over-rating the Knight's combat and under-rating the
board control of model count? Find the SPECIFIC missing mechanic, build it faithful + cited + even-handed,
measure. (This resolves the old re-calibration-vs-scoring fork toward the SCORING/MISSION/POSITIONAL fidelity —
a faithful simulator fix — and away from the stat re-fit.) The earlier "re-calibration is the next step"
note below is SUPERSEDED by this.

---

## Earlier — UPDATED 2026-06-01 (Q11 ruling): the positional re-model + Chapter Approved 2025-26 deck

The faithful scoring/secondary track drove gated MAE 5.98 → **4.08** (Tier A board secondaries +
the real Knights damaged-OC bracket) and then hit a STRUCTURAL FLOOR (waves 86-90). The residual is
now ONE axis: **primary victory points / objective control** — Imperial Knights +27 over-hold the
markers, Chaos Daemons −22 under-hold them; the same one-Unit-per-model positioning/representation gap
at opposite ends. The faithful AI levers for it are exhausted (washed 5+ times); the secondary layer is
a cap-wash; the over-shooter detachments are clean. The user ruled the strategic checkpoint:

**1. Mission deck = CHAPTER APPROVED 2025-26 (Q10).** The May-2026 calibration target was played under
the CA-2025-26 deck, not Pariah Nexus 2024. Do the unified secondary deck re-alignment to CA-2025-26
values (Cull 13+ models / 5 VP; Engage 1/2/4 at 2/3/4 quarters; Assassination 4 VP for 4+-wound /
3 VP otherwise; plus the deck-independent corrections Bring It Down bracketed 2+2+2, No Prisoners 2,
Behind Enemy Lines 3/4) AND re-check the landed Tier A cards against CA-2025-26. Source/cite from ≥2
CA-2025-26 sources (BSData / Goonhammer CA review — NEVER 40k.app, which is index data). Likely a small
headline move (the cap-wash), but it is the faithful match to the target data.

**2. Authorise the hard POSITIONAL-REPRESENTATION RE-MODEL (Q11 = c) — diagnose, do not nerf.** Re-model
the real mechanic of how a body army's surviving Objective Control gets onto and massed on markers (the
one-Unit-per-model gap: body armies have huge total Objective Control but get almost none within range of
markers). This is the ONLY faithful path to the IK-over / Daemons-under axis, and it is HIGH-RISK — the
AI-positioning class has washed/regressed every prior attempt. **Hard rails (this is the sharpest
metric-tuning surface in the project):**
- It MUST be a faithful representation / positioning fix — e.g. the AI actually moving body-army models
  onto and massing on objectives (a real tactic), or a real coherency / range / geometry correction to
  how models contribute Objective Control on a marker. Cited if it implements a rule; EVEN-HANDED across
  all factions.
- It must NOT be a per-faction or per-model-count Objective-Control→primary-VP conversion knob, a
  body-army primary boost, or a Knight primary penalty. The test is unchanged: would it be correct if it
  moved the metric the wrong way? A conversion factor tuned to lift Daemons / lower Knights = metric-tuning.
- Plan-FIRST (the proven wave-73→74 / wave-82 plan→build pattern), env-gated A/B, per-matchup before/after
  on the IK and Daemons objective-holding cells. Expect a possible regression/wash; if it washes, REPORT
  it honestly — do NOT force it or reach for a knob.

Sequence: the CA-2025-26 deck re-alignment first (bounded, faithful), then plan + build the positional
re-model. Clean non-regressing under-shooter fixes remain available alongside.

---

## Earlier phase — UPDATED 2026-06-01 (user ruling on Q6): the scoring / victory-point model overhaul (Tier A landed; floor reached — see above)

**The faithful AI track below is CONCLUDED — structurally blocked for the durable
over-shooters.** All four levers (value-targeting w72, focus fire w79, the sourced Armiger
list re-fit w80, contest/deny w81) regressed and were reverted with no nerf — confirming 3×
the frozen-under law: a faithful artificial-intelligence improvement helps whoever has the
better army, and the over-shooters HAVE the better armies, so sharper play widens the
headline. The leftover Imperial Knights over-rate (and the durable over-shooters generally)
is a structural VP-vs-durability SCORING residual: a durable camper converts objective-holding
into held primary victory points, and the simulator under-models how real tournaments deny
that primary through the full secondary economy and board tempo.

**The user chose to BUILD THE SCORING / VICTORY-POINT MODEL OVERHAUL (Q6 option a) — diagnose,
do not nerf.** This is the genuine root-cause lever. Scope:

- **Goal:** make a durable camper's objective-holding stop OVER-converting into primary
  victory points, by modelling the real 10th-edition Pariah Nexus scoring economy MORE
  COMPLETELY — never by reducing scoring for armies "because they over-shoot."
- **Faithful candidates** (pick what the matchup diagnosis supports; verify each against the
  real Pariah Nexus mission pack / Leviathan Tournament Companion; cite per rule 10):
  complete the tactical-secondary pool (the sim models ~2 of 9 action/board tacticals) so
  board-control opponents have the real scoring paths they use to out-score a camper; model
  the real primary-scoring mechanic more faithfully (per-round cap, hold-versus-contest
  dynamics, mission/primary variety) so monopolising a few objectives does not run away; any
  other real scoring-economy element the diagnosis shows is missing.
- **THIS IS THE SHARPEST METRIC-TUNING SURFACE IN THE PROJECT — guard hardest.** A scoring
  change is the easiest place to fudge (re-weight to move win rates). Every scoring change
  MUST be a faithful model of a REAL 10th-edition rule, CITED, applied even-handedly across
  ALL factions. The test is unchanged: would it be correct even if it moved the metric the
  wrong way? A scoring tweak whose only justification is the residual direction is
  metric-tuning — reject it. NO per-faction scoring weights, NO durability/camper penalties.
- **Method:** scope/plan FIRST (a dedicated plan wave, mirroring the successful wave-73→74
  plan→build), then build environment-gated, with PER-MATCHUP win% before/after on the
  durable-camper matchups specifically. Accept a temporary regression that the completed
  faithful model recovers.
- The approved interim — small clean NON-regressing under-shooter correctness / datasheet
  fixes — stays available alongside.

### Watchdog correction REVERSED (2026-06-01) — the damaged-Objective-Control bracket IS REAL; KEEP it

An earlier watchdog directive wrongly called `Battle._effective_oc` /
`simulator.damaged_objective_control_bracket` a fabrication and ordered its removal. **That was the
WATCHDOG'S error — the rule is REAL and the worker was right.** Multiple independent sources (the
worker's 40k.app, plus Goonhammer's codex review and the 1d6chan tactics page, confirmed by web
search 2026-06-01) agree that a 10e Knight loses Objective Control on its damage bracket: a
Questoris-class Knight (Objective Control 10) subtracts Objective Control while it has 1-9 wounds
remaining, and an Armiger (Objective Control 6) has its Objective Control halved to 3 while it has
1-5 wounds remaining. BOTH the worker's AND the watchdog's BSData-cache reads that suggested
otherwise were flawed greps that hit the wrong "Damaged" ability lines / a neighbouring unit's
profile, NOT the Knight's damage-table rows — neither of us actually read the bracket. The project's
BSData IS the current codex (Knight T11/W26), and the codex review states a Knight "loses 4 Objective
Control instead of 5" when bracketed, so the reduction is real and almost certainly present in
BSData; extract the damage-table rows properly to confirm. So `_effective_oc` is FAITHFUL —
**RE-ADD it** (the worker removed it on that bad read; its "Objective Control does not bracket" memory
is WRONG and should be corrected).

It is NOT metric-tuning: it is a real per-datasheet rule that only Knights have, so gating it to
Imperial / Chaos Knights is the correct faithful implementation, not a per-faction fudge. And the
fact that it also helps the Imperial Knights over-control residual is a happy case where the real
rule and the metric agree — keep it because it is real, regardless.

REMAINING WORK (faithful refinement, NOT removal):
- VALUE — RESOLVED (2026-06-01) from the canonical BSData cache, extracted VERBATIM (the
  authoritative read; this supersedes the watchdog's earlier "−4" guess): Armiger / War Dog **−3**
  (Objective Control 6 → 3) at 1-5 wounds; Questoris **−5** (Objective Control 10 → 5) at 1-9 wounds;
  Dominus **−5** at 1-10 wounds. The worker implemented exactly this and cited it verbatim — CORRECT.
  The watchdog's "codex is −4" came from an unreliable web summary; rule 6 (BSData first) governs, so
  the cache −5 is authoritative (and the ±1 vs the web summary is metric-negligible). 40k.app is INDEX
  data and is never a live-value source. Floored at 0. (Worker's Q10 discrepancy flag is resolved: use
  the cache −5.)
- Add the `data/rule_citations.d/` entry with verbatim datasheet text (the audit requires it).
- Keep the floor at 0 (the current `max(0, …)` is correct); never a negative Objective Control.
- Land it on the normal environment-gated A/B + per-matchup evidence like any change.

The separate summed-Objective-Control contest (Q8 — does a body blob correctly out-control a Knight)
remains a valid faithful question to check alongside this.

**Watchdog lesson:** do NOT declare a worker's CITED rule a fabrication on the strength of one local
read — check the actual cited source (or several) first. Verify-first applies to accusations too.

---

## Earlier phase (2026-05-31): the faithful AI track + matchup-fidelity diagnosis (now concluded — see above)

The clean rule-level structural levers are largely exhausted (gated MAE ~4.9; trajectory
5.98 → 4.9 this session, all faithful). The user chose the next direction:

**1. Push the faithful target/positioning AI — diagnose, do not nerf.** The remaining big
residuals (Imperial Knights, Drukhari over; Chaos Daemons, Chaos Space Marines, Chaos
Knights under) are artificial-intelligence-quality problems: opponents do not focus fire
durable / key threats, do not contest and deny objectives, and mis-allocate units to
actions. Redesign the artificial intelligence to play like a real tournament player —
focus the highest-value reachable threat, contest and deny objectives, screen, commit only
genuinely spare units to actions — all real 10th-edition tactics. This regressed before
(wave 72) because the unit statistics are co-adapted to the weak artificial intelligence
(the frozen-under-headline problem, memory `project-ai-frozen-under-mae-first`). When the
better artificial intelligence exposes an over-shoot, **treat it as a DIAGNOSIS problem —
find the faithful simulator cause (a mis-modelled rule, a statistic wrong versus BSData, an
unrealistic list) and fix THAT — never a metric-driven nerf.** Use an environment-gated A/B
so the change is measured cleanly, and accept a temporary headline regression that a
faithful re-calibration then recovers.

**2. Matchup-fidelity diagnosis — compare the simulator to real tournament play.** Do not
work only from aggregate per-faction win rates. For each big residual, drill into the
specific matchups driving it (which factions does the simulator have LOSING to Imperial
Knights or Drukhari; which factions is Chaos Daemons losing to). Then compare against how
those factions actually play that matchup in real May-2026 tournaments — their real lists
and real strategy (anti-tank focus fire, objective play, screening, the specific stratagems
and counters competitive players use). Sources: Goonhammer faction / matchup guides and
detachment focuses, Bell of Lost Souls / Stat Check tournament reports (Wahapedia domain
name resolution may be down — fall back to BSData and cached competitive write-ups; do not
invent). The gap between simulator and real play is the fix, and it sorts into exactly
three faithful buckets:
   - the faction uses a real tactic the simulator's artificial intelligence cannot execute
     → an artificial-intelligence fix;
   - the real competitive list runs a counter the simulator's archetype lacks → a
     list-realism fix, toward the real tournament list (see the relaxed re-fit rule below);
   - the simulator mis-models a rule or statistic in that matchup → a simulator/stat fix.
   Never a win-rate nerf in any bucket — the matchup data tells you WHAT is unfaithful; you
   fix the unfaithful thing.

**Re-fit is now permitted, but only as a FAITHFUL re-calibration.** The earlier blanket
"archetype lists are lowest priority, do not touch" is relaxed for this phase: a list MAY
be edited toward a real May-2026 tournament list when the matchup diagnosis shows the
simulator's list is unrealistic (missing a counter the real list runs, wrong unit ratios, a
unit that did not exist when the archetype was written). It may NEVER be edited to hit a
win-rate target. The test is unchanged — would this edit be correct even if it moved the
metric the wrong way? If the only argument is the residual direction, it is a nerf; reject it.

## Each iteration (one wave; mechanics per `docs/AUTO_LOOP_PROCEDURE.md` + the `sweg-wave` skill)

1. Read `docs/CURRENT_STATE.md` for live residuals and ranked levers.
2. Pick the highest-leverage target: usually the largest-magnitude residual
   faction, but a **systemic** fix (one artificial-intelligence or representation
   change that moves many factions) beats a per-unit patch — see memory
   `project-ai-piloting-top-lever`.
3. Diagnose the residual as a **simulator** cause — a wrong or missing rule, a
   wrong statistic, an artificial-intelligence mis-pilot, or a representation
   artifact. Fix-first if you can name file, line, and Wahapedia uniform resource
   locator; otherwise dispatch a verify-first diagnostic agent.
4. **Verify before acting.** Research agents over-claim on this project (phantom
   invulnerable saves, fabricated cross-faction keys, "missing" units that already
   exist, and "unrealistic" lists that are already citation-calibrated). Check
   every claim against `code/`, `data/bsdata/cache/`, `data/overrides.json`, and
   Wahapedia first.
5. Implement faithfully. Real rules get a `data/rule_citations.json` entry (standing
   rule 10; `scripts/audit_rules.py` is enforcing — no citation, no rule). Statistic
   fixes go in `data/overrides.json`, never `parsed.json`. New units get full
   override entries, never hand-rolled code. Use tiered bundle-of-one agents (Haiku
   for data, Sonnet for audits and small code, Opus for novel mechanics); brief the
   standing-rule-8 worktree base-reset in every worktree agent.
6. Evaluate: `PYTHONHASHSEED=0 python -m scripts.evaluate_vs_meta --battles 40
   --use-archetype` (the seed prefix is mandatory on this machine; the evaluation
   segfaults without it). Run the pytest sweep too. Hand the before/after logs to
   the `eval-interpreter` sub-agent for per-faction deltas.
7. Decide by fidelity, not by metric: **keep** a correct fix even if it is
   metric-neutral. If a correct fix **regresses** gated mean absolute error, another
   simulator error was compensating for it — hunt that error, do not revert the
   correct fix (memory `project-ai-frozen-under-mae-first`). **Reject** anything that
   only helped by fudging.
8. Close the wave: archive and write the `docs/AUTO_LOOP_LOG.md` block, update
   `docs/CURRENT_STATE.md` with the new headline and next three levers, run
   `python scripts/loop_cleanup.py`, and commit locally to
   `claude/sim-calibration-6`.

## Pacing between waves

This mission runs in self-paced loop mode: after each wave you end your turn and the
harness re-invokes you on the next scheduled wakeup (`ScheduleWakeup`). Because there
is always more work until the floor is reached, schedule that between-wave wakeup at
the **minimum delay (60 seconds)** so the next wave begins promptly. Do **not** use
the long idle-tick default (1200 seconds and up) — that cadence is for polling
external state, not for a work queue that is never empty; at 20-30 minutes per gap it
wastes most of the run.

Within a wave, a background evaluation or agent you dispatched with `run_in_background`
re-invokes you automatically when it finishes — so do not burn a short polling wakeup
on it; if you set a fallback in case it hangs, make it long (1200 seconds or more).
The 60-second minimum is specifically for the between-waves restart, where nothing is
pending and the only thing between you and wave N+1 is the wakeup itself.

## Asking questions — route to the watchdog, never interrupt the user

A supervising watchdog session reviews your output between waves and answers your
questions. When you reach a question you would otherwise put to the user:

- **Do not call `AskUserQuestion` or otherwise ping the user.** The user has asked that
  your questions route through the watchdog instead.
- **Append the question to `LOOP_QA.md`** (repository root; it is gitignored — a live
  scratch channel, do not commit it), using the block format documented at the top of
  that file: question, context, options, your most-faithful default, and whether it is
  blocking.
- **Then keep moving.** Default to non-blocking: pick the most faithful,
  prime-directive-compliant interpretation, proceed with it, and let the watchdog confirm
  or correct it later. Only park a lever (mark it blocking) if proceeding would risk
  fabricating or metric-tuning — then move to a different lever rather than stalling.
- **Read `LOOP_QA.md` at the start of every wave** and apply any answers the watchdog has
  written (`[ANSWERED]`); revisit a parked lever once its question is answered.

The watchdog answers what it can from the prime directive, `CLAUDE.md`, and the
established methodology, and escalates only genuine steering forks to the user — so a
question costs you no stall and the user no interruption.

**NEVER HALT THE LOOP (re-primed 2026-06-02 — the user's standing instruction after two stalls).**
You stalled twice on the night of 2026-06-01/02: each time you committed a wave cleanly and then the
loop simply stopped, leaving queued work idle until the user relaunched. **Do not do this.** After every
wave, self-pace straight into the next one — pick the next lever from the WATCHDOG-MANAGED TASK QUEUE and
keep going until the mission goal (gated mean absolute error below the per-faction noise floor) is met.
- **Never stop to ask, never end the session, never wait.** If you reach a question, a fork, a wash, a
  thing you can't resolve, or anything that tempts you to halt: write it to `LOOP_QA.md` (Blocking: no),
  pick the most-faithful interpretation OR move to a different queued lever, and CONTINUE. The watchdog
  session is awake and reviewing between every wave — it will confirm, correct, or escalate; you lose
  nothing by proceeding.
- **The only legitimate stop** is the one in "When to stop and surface to the user" below (true floor /
  no faithful lever left for 2-3 waves) — and even then you REPORT (write the finding + log it) and keep
  the loop alive on the next-best lever; you do not silently end.
- If you ever find yourself about to output a "loop complete / awaiting input / I'll continue next time"
  message after a commit — that is the stall. Instead, immediately begin the next wave.

## Do not tunnel: take the structural lever when narrow fixes stall

Watch for this failure mode, because the loop has already fallen into it: you correctly
diagnose that the headline is structural (the over/under split is single-rooted), you
even name the root cause — and then you spend the wave on a safe, narrow, 0.05-point
faithful nerf instead of the structural fix you just identified. Three waves stuck near
gated 5.9, two of them on one faction's invulnerable-save mechanics, is the symptom.

Standing corrections:

- **When you have identified a structural root cause and not yet acted on it, do not
  spend a wave on a narrow fix that moves the headline less than ~0.1.** Take the
  structural lever instead, even though it is bigger and riskier. A 0.05-point wave that
  dodges the known root cause is the stall, not a step toward avoiding it.
- **Retire "audit the over-shooters for things to nerf."** Hunting only the armies that
  are over, looking only for mechanics to reduce, is metric-driven selection — motivated
  reasoning that reaches a nerf and then finds a citation for it. Fidelity audits must be
  applied **evenly across all factions**, and you keep a correction only because it is the
  faithful reading of the rule, never because of which direction it moves a residual.
- **"Faithful" does not mean "only small, individually-citeable nerfs."** The largest
  fidelity gaps are structural: whether the scoring, mission, representation, and
  artificial-intelligence machinery actually models how real games are won. Modelling that
  correctly IS the rules-accurate fix this mission asks for.
- **Verify that the existing machinery is actually wired up — do not assume it is broken,
  and do not assume it works; check.** Two cautionary examples from this loop, in opposite
  directions: (1) the watchdog briefly believed the Pariah Nexus secondary VP was a dead
  store — it is NOT. `Battle._score_secondaries` adds it straight into `_a_vp` / `_b_vp`
  (lines ~925/937/954/961), the very totals `_decide_winner` compares, so the win already
  counts primary plus secondary; the `_a_secondary_vp` accumulator is only a parallel
  reporting tally. Wave 73 verified this and correctly refused a "fix" that would have
  double-counted. (2) Cull the Horde, by contrast, IS a real dead mechanic:
  `secondaries._is_horde_unit` reads `starting_strength` / `squad_size` / `count`, all None,
  so it should read `max_models` — today it scores 0 for everyone. Read the code before
  building on either assumption.

### The named structural lever (verified — kill-secondary asymmetry → action secondaries)

The secondary layer is already wired into the win condition (verified above), so the win
counts primary plus secondary. The real structural driver is the **kill-secondary
asymmetry**: the implemented secondaries are kill-heavy (Bring It Down, No Prisoners, Cull,
Assassination) plus two position tacticals (Engage, Behind Enemy Lines) — only 2 of the 9
real Tactical secondaries — so durable killers bank secondary VP for killing while their
victims and board-control armies have little path back. The faithful counterbalance is the
missing **action-economy secondary family** (Cleanse, Sabotage, Recover Assets): a unit
performing a 10e action gives up shooting and charging that round, which a low-model durable
army cannot spare a body for and a horde / MSU army can — an even-handed tax that falls out
of unit count, not a per-faction knob. The scoped build is in
`docs/ACTION_SECONDARIES_PLAN.md` (Cleanse vertical slice first, env-gated A/B); land the
`_is_horde_unit` correctness fix in the same wave. Verify the card text first (Wahapedia DNS
is down — use the GW Pariah Nexus pack / Goonhammer) and cite each per rule 10.

### The wider structural rotation (when narrow levers stall, pick from here, not nerf-hunts)

- **Scoring/representation** — the action-secondary family above; then whether the
  artificial intelligence actually *plays toward* the scored secondaries (board spread for
  Engage on All Fronts, entering the enemy deployment zone for Behind Enemy Lines), and
  completing the rest of the tactical-secondary pool (only 2 of 9 are implemented).
- **Denial / repulsion positioning (#13)** — distinct from the *target* AI that regressed;
  this is movement that lets under-shooters contest and take objectives *from* durable
  holders, which the loop itself identified as the bottleneck.
- **Per-model activation tax** — low-model durable armies are not punished for low body
  count; **terrain density** — sparse boards over-rate gunlines.

## The toolbox — every mechanism used so far; keep them all in play

Pick what the residual calls for; do not marry one approach.

- **Artificial-intelligence piloting** (`code/strategy.py`) — the top lever.
  Mis-pilot fixes (Fall-Back), plan-level objective behaviour (the objective-hold
  change #12), consolidate-onto-objective, damage-allocation spillover. Open work:
  the #13 artificial-intelligence repulsion/denial positioning lever, and re-running
  the sixteen-tactic tournament-tactic capability audit (lost in a restart — memory
  `project-ai-tactical-gaps` holds the framework).
- **Faction army rules / detachments / leaders / stratagems**
  (`code/detachments.py`, `code/leaders.py`, `code/stratagems.py`) — implement a
  faction's real missing rules.
- **Core-rules fidelity** (`code/simulator.py`) — line of sight (Towering, Ruins),
  mortal wounds, Big Guns Never Tire, one-Unit-per-model representation plus
  `squad_id`, damage spillover.
- **Statistic / data corrections** (`data/overrides.json`) — fix BSData mapper
  artifacts (feel-no-pain prose-walk, multi-profile-weapon under-capture,
  static-versus-runtime double-count). The deep multi-profile-weapon mapper fix is
  **structural** — flag and queue it, do not bodge it.
- **Detachment de-fabrication** — replace always-on proxy flags that do not match
  the real rule with the real mechanic (memory
  `project-detachment-fabrication-pattern`).
- **Archetype lists** (`code/archetypes.py`) — **lowest priority, handle with
  care.** These are already calibrated to real May-2026 lists with citations. Touch
  a list only for a genuine, verifiable realism gap (a unit that did not exist when
  the list was written, or a composition demonstrably wrong versus real meta) —
  never as a win-rate knob, and never just because a different valid real list
  exists. "With some variation" means there is no single canonical list, so swapping
  one realistic list for another to move a win rate is metric-tuning.

## WATCHDOG-MANAGED TASK QUEUE (prioritized by estimated impact — user-authorized 2026-06-01)

The user authorized the watchdog to review, add, and **prioritize tasks by estimated impact**.
Work this queue top-down. Estimated impact is on the headline gated mean absolute error, weighted by
the dominant residual (the positional axis: Imperial Knights +27 over-hold / Chaos Daemons −22
under-hold ≈ half the gated MAE).

**HOW TO EXECUTE THE FIX BATCH — MULTIPLE PARALLEL AGENTS (user directive, 2026-06-01).** Work the
core-rules audit findings as a fan-out of CONCURRENT worktree-isolated fix agents (sweg-wave skill;
CLAUDE.md §8 base-reset dance in every worktree agent's prompt — push WIP, reset the worktree to it,
confirm HEAD), NOT one finding per serial wave. Group by the MERGE-SAFE streams in
`docs/CORE_RULES_AUDIT_FINDINGS_2026-06-01.md`: Streams **A** (`strategy.py`), **B** (`stratagems.py` +
`stratagems.json`), **C** (`maps.py` density) are file-disjoint → run in parallel. Stream **D+E**
(cover / line-of-sight / terrain RULES + Fall Back gates) shares `map.py`/`units.py`/`simulator.py`
hot functions → ONE coherent agent, and sequence it AFTER Candidate B lands (P0 also edits
`simulator.py` — do not run them concurrently or the diffs won't merge). Each agent: re-verify its
finding against `data/reference/wahapedia_core_rules_2026-06-01.txt`, fix, CITE (audit enforces), run
the pytest sweep + N=40 A/B; keep faithful fixes regardless of metric direction but measure + report.
This batch SUBSUMES the standalone P1 terrain task below (Stream C = its density build, Stream D = its
cover/line-of-sight rules).

**P0 — ✅ RESOLVED (wave 95; queue note was stale, corrected wave 124).** Candidate B (`SWEG_MASS`) LANDED
default-ON: gated 4.15 → 3.81 (Daemons −22.7 → −16.4, IK +27 → +25.5); already in the current N=80 3.69
baseline. It did NOT wash — the faithful movement half of M4. Nothing left to do here.

~~**P0 — IN FLIGHT (finish, then report; do not abandon mid-measurement).**
Candidate B (`SWEG_MASS`, the move AI massing units onto markers). Finish the env-gated A/B vs 4.15,
per-matchup on the IK + Daemons cells. **Even-handed** — a general objective-seeking move-AI
improvement for ALL factions; body armies benefiting more must be EMERGENT (more bodies), NOT a coded
body-army / under-shooter / per-archetype massing preference (that is the forbidden knob). Real movement
only — NO objective-control counting / coherency-buffer change (that is the reverted A2 by the back
door). Expect a likely wash (the frozen-under / w81 class); **if it washes, REPORT it** — do not force,
do not reach for A2 or any knob. (Watchdog estimate: low-to-moderate; likely wash, but cheap to finish
and the result is informative for the terrain hypothesis below.)~~

**P1 — ✅ RESOLVED (wave 97; queue note was stale, corrected wave 124). TERRAIN-REALISM REVIEW — DONE +
HYPOTHESIS REFUTED.** Both halves are complete: the terrain-RULES fixes (TOWERING-not-blanket-for-ruins,
cover, line-of-sight) landed in the wave-96 core-rules batch (Stream D+E), and the terrain-DENSITY rework
(`code/maps._competitive_terrain`, using the watchdog's supplied competitive Pariah Nexus reference, cited
`terrain.competitive_pariah_nexus_layout`) landed wave 97 default-ON. **Result REFUTED the sparse-terrain
hypothesis:** realistic dense terrain made the Imperial Knights WORSE (+25.9 → +27.3, gated 3.59 → 4.13) —
realistic terrain AMPLIFIES the durable over-holder rather than helping melee under-shooters reach markers.
KEPT as fidelity (the May-2026 target was played on it) despite the regression. Terrain is NOT the
root-cause of the positional axis. Nothing left to do here.

> _(Superseded original P1 note retained below for reference — the review is done and refuted, see above.)_

**P1 (ORIGINAL NOTE, superseded) — HIGHEST estimated impact (NEW, user-authorized): TERRAIN-REALISM REVIEW.**
Hypothesis (watchdog, data-backed): the positional residual is substantially driven by SPARSE terrain.
Our 10 calibration maps average ~8–10% terrain area / ~7–8% line-of-sight-blocking coverage with small
scattered pieces; real competitive Pariah Nexus layouts are far denser (~25–30% area with large central
line-of-sight-blocking ruins). Sparse, open boards systematically favour shooting + TOWERING (Imperial
Knights shoot across the table and over-hold) and starve melee / board armies of cover to advance (Chaos
Daemons get shot off the board before reaching markers → under-hold) — the exact residual shape. This
may root-cause the axis the AI-positioning levers cannot move (a perfect massing AI still can't get
Daemons onto markers if they're killed crossing open ground). Sub-tasks:
- **(a) Audit.** Quantify each map's terrain area %, line-of-sight-blocking %, piece sizes and placement
  (is there a central line-of-sight spine, or only scattered small pieces?) versus the ACTUAL May-2026
  Pariah Nexus competitive terrain layouts. Source the real layouts from a citable reference (Games
  Workshop Pariah Nexus tournament companion / World Team Championship layouts / Goonhammer terrain
  articles). **The worker's web access is unreliable (Wahapedia DNS fails in agents) — if you cannot
  source the real layouts, the WATCHDOG will provide the reference data via LOOP_QA before this task is
  picked up; flag it there rather than guessing.**
- **(b) Build.** Raise our maps' terrain density and add central line-of-sight-blocking ruins to MATCH
  the real competitive layouts. FAITHFUL BY CONSTRUCTION: reproduce real terrain, cite the layouts in
  `data/rule_citations.d/`. EVEN-HANDED — terrain is faction-neutral; do NOT gerrymander terrain or
  objective placement to favour or disfavour any faction. Prime-directive test: would this terrain be
  correct if it moved the metric the WRONG way? Yes, iff it matches the real layouts — so match them,
  do not tune them.
- **(c) Measure.** Before/after N=40 eval; report the IK + Daemons residual and the over/under-shooters.
  Because matching real terrain is faithful regardless of metric direction, KEEP the realism upgrade as
  fidelity even if metric-neutral — but never adjust terrain to chase the metric. If it moves the axis,
  that is the root-cause finding; if it washes, report that the axis survives realistic terrain too.
  (Watchdog estimate: HIGH — directly addresses the dominant residual via a faithful, even-handed lever
  the AI track structurally cannot reach.)
- **(d) Terrain-RULES-fidelity fixes — CONFIRMED against the PRIMARY current core rules (Wahapedia, Core
  Rules 1.8 Oct 2025 + Balance Dataslate 3.4 Mar 2026; full verbatim text captured 2026-06-01).** The
  terrain layer is framed on the deprecated 9th-edition "terrain traits" vocabulary; CURRENT 10e uses
  terrain CATEGORIES (Ruins, Woods, Hills, Craters & Rubble, Barricades, Battlefield Debris) — VERIFIED:
  "Dense/Light/Heavy Cover", "terrain trait", "Difficult Ground", "Scaleable" each appear ZERO times in
  the core rules. Do these fixes (suggest BEFORE the density rework so the line-of-sight measurement is
  clean), each cited to the captured verbatim text:
  - **(i) CONFIRMED BUG — TOWERING is NOT a blanket see-over for RUINS (it is for WOODS).** `code/map.py`
    `has_line_of_sight` sets `ruin_pass = towering OR …`, so a Knight (TOWERING) shoots through EVERY ruin
    from anywhere. The two area-terrain types differ:
    - RUINS (verbatim): *"Models cannot see over or through this terrain feature … AIRCRAFT models are
      exceptions to this — visibility to and from such models is determined normally, even if this terrain
      feature is wholly in between them and the observing model. Models can see into this terrain feature
      normally, and models that are wholly within this terrain feature can see out of it normally. Models
      that are within this terrain feature can be seen normally and TOWERING models that are within this
      terrain feature can also see out of it normally."* → ONLY AIRCRAFT is a blanket exception; TOWERING
      only sees OUT when WITHIN the ruin; a TOWERING model OUTSIDE a ruin is blocked like anyone else.
    - WOODS (verbatim): *"AIRCRAFT and TOWERING models are exceptions to this — visibility to and from such
      models is determined normally, even if this terrain feature is wholly in between them…"* → here
      TOWERING DOES get the blanket see-over.
    FIX (surgical): KEEP towering ignoring the woods/obscuring type (that is correct); STOP towering from
    forcing `ruin_pass`. For ruins: blanket pass for AIRCRAFT only; add the "endpoint within a ruin → can
    see out" allowance (covers wholly-within for all + within for TOWERING); otherwise ruins block. Re-cite
    `simulator.towering_los` to the two verbatim passages above (drop the 9e "Obscuring or Dense Cover
    trait" quote). **Metric hypothesis (measure, don't assume): plausibly reduces the Imperial Knights
    over-hold (+27) — the sim currently gives Knights table-wide sightlines real ruins would block — and
    compounds with the density rework.** Faithful regardless of metric direction.
  - **(ii) CONFIRMED stale — remove the INFANTRY/BEAST/SWARM "shoot through ruin walls" line-of-sight pass**
    (`_has_ruin_pass`). In current ruins the INFANTRY/BEAST exception is MOVEMENT ONLY (verbatim: *"INFANTRY,
    IMPERIUM, PRIMARCH, BELISARIUS CAWL, and BEAST models can move through this terrain feature (walls,
    floors, ceilings…) as if it were not there"*); "shoot through" / "through the wall" appear ZERO times.
    Ruins fully block line of sight. Remove the shoot-through-walls LoS exception (keep movement-through if
    modelled).
  - **(iii) CONFIRMED — collapse cover to a single Benefit of Cover (+1 save), drop `HEAVY_COVER = -1 to
    hit`.** 10e grants only the Benefit of Cover against ranged attacks (verbatim: *"that model has the
    Benefit of Cover against that attack"*) = +1 to the saving throw (with the standard "cannot improve a
    3+-or-better save vs AP0" caveat — verify). There is no -1-to-hit and no Light/Heavy split in the core
    rules. Re-cite accordingly.
  - Re-frame the `TerrainType` model on the 10e categories. (Watchdog now has live Wahapedia access via the
    user's VPN; the verbatim rule text is captured in the oversight log + LOOP_QA if access drops.)
    Cross-check the PRIMARY rule text — a web search SUMMARY described the outdated launch TOWERING and was
    wrong (the OC-bracket / primary-source-first lesson). Even-handed.

**P2 — BUILD-NEW MECHANICS from the coverage sweep (bigger than the quick-fix batch; see
`docs/CORE_RULES_AUDIT_FINDINGS_2026-06-01.md` coverage section).** Ranked by impact: (1) Fire Overwatch
core stratagem (out-of-phase reaction shooting — melee-vs-gunline balance); (2) Go To Ground / Smokescreen
defensive core stratagems (fragile-infantry over-kill); (3) Strategic Reserves board-edge arrival + Rapid
Ingress; (4) mid-game voluntary embark (Drukhari Skysplinter); (5) AIRCRAFT special rules (only if aircraft
units are in the archetype lists); (6) surge-move primitive. Each is faithful + cited; A/B each.

**P1.5 — ROLL DAMAGE (USER-APPROVED 2026-06-01; structural; high value).** Replace the expected-value
damage shortcut (`parse_dice_expr` collapsing D6/D3+N to mean at load) with a per-shot runtime damage
ROLL. Rationale (faithful + two payoffs): (a) restores damage variance + correct overkill/threshold
behaviour against multi-wound models — plausibly trims the big-gun / Imperial Knights over-rate; (b)
**ENABLES a whole class of abilities that are currently DEAD under expected-value** — "re-roll the Damage
roll", "re-roll Damage rolls of 1", minimum-damage floors (the user flagged Space Marines specifically,
which have built-in optional damage re-rolls that benefit enormously). So this task is TWO parts: (1) roll
variable damage per shot at runtime; (2) audit the catalogue/BSData for damage-reroll + damage-floor
abilities that were inert under expected-value and wire them (cited). Caveats: it touches the `units.py`
damage hot-path, so SEQUENCE it after the quick-fix batch's `units.py`/Stream-D work (do not edit
`units.py` concurrently); and rolled damage WIDENS variance, so re-check the per-faction noise floor and
whether N=40 still gives stable gated MAE (raise N or note the wider noise band if needed). A/B vs the
current baseline; keep regardless of metric direction (faithful), but measure + report the big-gun/Knight
delta.

**P3 — backlog (revisit after the positional axis; re-rank by residual each wave).**
- **Drukhari anti-tank reads 0 (watchdog-flagged 2026-06-02, user asked to queue).** A watchdog tally of
  per-archetype anti-tank (weapons with Strength ≥9 + multi-damage, ranged or melee) found the Drukhari
  archetype scoring ZERO anti-tank — which is wrong (real Drukhari run dark lances / disintegrators /
  haywire). Investigate whether (a) the Drukhari archetype LIST genuinely lacks its anti-tank units
  (Ravagers / Kabalite dark lances / Scourges — if so, add them, cited) or (b) the per-model loadout data
  / weapon read under-detects Drukhari weapons. Either way it under-states the Drukhari list's threat to
  vehicles/Knights. Low priority but a real data gap.
- **Threat-priority / focus-fire target AI (watchdog diagnostic 2026-06-02).** An instrumented N=16
  Adeptus Astartes vs Imperial Knights run (current live sim) showed Astartes win 6%, kill 0.00 big
  Knights/game (only ~1.8 Armigers), deal ~38% of the Knights' total wounds, and only 39% of that damage
  comes from anti-tank units. The list HAS adequate anti-tank (~880 equiv; ~4 Lancers should kill a
  Paladin) — the failure is the AI shooting the lowest-wound target (Armigers) and never FOCUSING anti-tank
  onto a single big Knight to cross its wound threshold. This is the DEFENCE half of the IK +27 (distinct
  from the per-model offence over-count): wants a threat-priority / focus-fire target AI (per
  `project-faction-residual-rootcause`). Also suspect: dense terrain blocks the non-TOWERING enemy
  anti-tank's line of sight to Knights (would also explain wave-97 terrain making IK worse).
  **ROOT CAUSE FOUND + ELEVATED (2026-06-02 — wave 99 REFUTED the per-model offence over-count at the metric,
  so this defence/AI lever is now the PRIME suspect for IK +27).** Watchdog reviewed the AI vs the real
  counter-Knight playbook (Goonhammer IK faction focus + Start Competing; 1d6chan): the `code/strategy.py`
  shooting/charge target score applies a "WON'T-CRACK PENALTY" — if a unit's expected wounds
  `< WONT_CRACK_HP_FRAC × target.current_health`, its score is slashed. Against a 22-26-wound Knight NO single
  unit can crack it, so EVERY unit individually avoids the big Knight and shoots a killable Armiger/chaff;
  nothing coordinates multiple units' fire onto one Knight. That is the exact inverse of the #1 real
  counter-Knight tactic (focus fire to bring one Knight low). Verified in-sim: Astartes kill 0 big
  Knights/game, win 6%. The AI does ~NONE of the damage-side counter-Knight tactics. FIX: an ARMY-LEVEL
  focus-fire layer that, when the army COLLECTIVELY can crack a Knight, overrides the per-unit won't-crack
  penalty and concentrates fire to finish it (and values removing a high-threat brick even if no single unit
  solos it). FAITHFUL (real tactic), EVEN-HANDED (army-level focus-fire for ALL factions, NOT a Knight nerf).
  Likely frozen-under-adjacent → measure vs IK +27 and pair with re-calibration.
- **Advanced-tactics AI review (watchdog, 2026-06-02; sources: Goonhammer faction focuses, 1d6chan 10e
  Tactics, Grimhammer deployment guide, Vanguard Tactics).** Audited the move/target AI vs the competitive
  10e playbook. The AI does objective play PARTIALLY (its one real competency) and ~NONE of the rest. Ranked
  gaps to build (all faithful real tactics, even-handed across factions; each frozen-under-adjacent so
  measure + pair with re-calibration):
  1. **Focus-fire / threat-priority targeting** — see the note above; the #1 lever (IK +27 defence half).
  2. **Intelligent deployment + SCREENING** — the sim line-deploys (`_deploy_line`) with no screen-first /
     hold-threats-back logic and no screening to deny the 9" deep-strike bubble or block charges. Real play
     deploys chaff first to control mid-board + deny reserves. Affects deep-strike / alpha-strike matchups
     and lets under-shooters get bled. (Medium-high; ties to the coverage-audit "deployment is PARTIAL".)
  3. **Reactive fire — Fire Overwatch** (already P2 coverage build): punishes chargers / arriving reserves;
     its absence over-rewards melee/aggression vs gunlines.
  4. **Trading-up / bait + efficient sacrifice** — no deliberate baiting or expendable-chaff trading; the
     won't-crack/DPA score is only a crude proxy. (Lower.)
  5. **Combined-arms concentration of force** — units act independently with no concentration onto a flank /
     a target priority shared army-wide (focus-fire above is the shooting half of this). (Lower.)
  6. **Pile-in / consolidate positioning** (the user's "combat shenanigans") — charge stops at 1", no
     overshoot, consolidate only drifts 3" toward nearest; under-rates mobile-melee threat range. (Lower;
     partly bounded by the one-Unit-per-model representation.)
  Build top-down; #1 (focus-fire) and #2 (deployment/screening) are the high-impact, residual-relevant ones.

## Known work queue (starting points; re-rank by residual each wave)

- **Imperial Knights, +27.8 over** — audit the wave-69 Bold Gallantry / Bondsman
  buffs for over-rating (do they match the real detachment text?), now triple-stacked
  with the gun-heavy archetype and the #12 objective-camp. This is a rule-fidelity
  check, **not** a list trim.
- **Chaos Daemons, −19.5** — per-god rules plus the missing Be'lakor datasheet (add
  via overrides). **Drukhari, +17.1 / Thousand Sons, +13.1** — per-model activation
  over-rating plus unconstrained rituals. **Astra Militarum, −15** — Orders not
  modelled. **Adeptus Mechanicus, −8.3 / Tyranids, −7.5** — board control / synapse.
- Recover and evaluate the Dark Pacts selective commit (`1d24e40`, intact in its
  worktree) when Chaos Space Marines need attention.
- Verify the Chaos Knights detachment (Iconoclast Fiefdom wired versus Infernal
  Lance competitive) — a rule-correctness fix.

## Guardrails

- **Stage 1 only.** Do not touch the points equation, its coefficients or
  residuals, `code/balancer.py`, or `code/equilibrium.py` (that is Stage 2, frozen
  until the user signals Stage 1 convergence).
- Local commits to the work-in-progress branch are fine. Do **not** `git push`,
  open a pull request, or run `git config` without an explicit user "go"
  (`CLAUDE.md` rules 3 and 5).
- Fail loud on missing data (rule 13). No acronyms in commit, pull-request, or
  documentation prose (rule 11). Update documentation in the same change (rules 2
  and 12).
- Keep `docs/AUTO_LOOP_LOG.md` and `docs/CURRENT_STATE.md` current — they are the
  loop's memory across context windows.

## When to stop and surface to the user (do not invent your way past these)

- A rule you need has no findable Wahapedia or canonical citation — skip that lever
  and log it; only halt the loop if it is the sole remaining path.
- A fix needs a structural mapper or parser change — flag and queue, do not bodge.
- Real-meta list data is genuinely ambiguous — leave the list alone.
- Gated mean absolute error stalls for roughly two to three waves with no faithful
  lever left that reduces it — report the residual factions and the suspected
  (uncitable or structural) causes rather than reaching for a fudge. That stall is
  itself the finding.
- You reach the floor — stop and report.

---

## Launch

From a terminal in `C:\Users\Jake\Claude\code\SwegHammer`:

```powershell
claude --dangerously-skip-permissions "/loop Read docs/STAGE1_AUTONOMOUS_GOAL.md in full, then pursue that mission autonomously — self-pace one calibration wave at a time until the headline noise-gated mean absolute error is below the per-faction noise floor, then stop and report. Honour every guardrail in that file: no fabricated multipliers or tweaks to force results, Stage 1 only, and no git push or pull request without an explicit go."
```

The `/loop` with no interval self-paces; `--dangerously-skip-permissions` is what
makes it genuinely hands-off (the loop runs many Bash, edit, and agent calls per
wave). Push protection then rests on this file's guardrail plus the git-guard hooks,
not on a permission prompt — so the no-push rule is load-bearing.
