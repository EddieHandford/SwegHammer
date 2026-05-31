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
