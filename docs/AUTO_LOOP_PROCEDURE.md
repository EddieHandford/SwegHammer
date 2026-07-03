# Auto-loop operating procedure

Procedural rules for the autonomous calibration loop that drives MAE toward 2.0.
Applies on top of `CLAUDE.md` (which contains standing project rules). Goal:
keep per-iter token cost low without sacrificing correctness or auditability.

## A. Fix-first when the lever is clear

Skip the diagnostic-agent dispatch when the outlier's root cause is already
named in `docs/AUTO_LOOP_LOG.md`, or when the outlier has a public Wahapedia
datasheet gap that can be confirmed by reading the datasheet + the relevant
sim code without running anything.

Run a fix agent directly with a one-line root-cause statement in the prompt.
Reserve diagnostic dispatch for factions where the cause is genuinely
unclear after a quick code/Wahapedia check.

Rule of thumb: if you can name the file + line + Wahapedia URL of the
suspected bug before dispatching, you don't need a diag agent — go straight
to a fix.

## B. Bundle-of-one fix agents

One fix per agent, max 30 tool uses each. Parallel up to four to six per
iter. Reasons:

* Each commit lands atomically before any rate-limit cliff, so a dying
  agent never costs the iter the entire bundle.
* Smaller scope means a smaller prompt, lower context, faster turnaround.
* Cherry-picking is one commit per logical change — easier review.

Bundle larger only when fixes are tightly coupled (shared file, shared
test). Worldblight gate + Lord of Contagion host_keys live in different
files and can split cleanly; a Custodes Resolute Will + simulator wiring
+ override + citation has to go together.

## C. Trimmed agent prompt template

Target 400 tokens per agent prompt. Don't repeat what `CLAUDE.md` already
says — the agent reads it on entry. Required content only:

```
SwegHammer iter <N> — <faction> <fix-key> (Stage 1 calibration).

Branch: claude/sim-calibration-<n>, top commit <SHA>. Worktree align per
CLAUDE.md §8 (reset to origin/<branch> before starting).

ROOT CAUSE: <one sentence + Wahapedia URL>.

FIX: <file:line — what to change>.

VERIFY: <test command + eval command>.

COMMIT: one commit with message "iter<N>-<key>: <one-line fix>" — body
explains why per Wahapedia. Stay on worktree branch; do NOT push.
```

Anything longer is repetition.

## D. Direct main-worktree work for trivial overrides

For changes that touch only `data/overrides.json` (FNP / invuln / deep_strike
flag corrections) and have no test churn, edit and commit in the main
worktree directly. No worktree isolation.

Reasons: worktrees default to main not the WIP branch (CLAUDE.md §8 base
verification dance), and `data/overrides.json` is the most-polluted file in
the repo — keeping its edits in one shell removes the "did the agent write
to its own worktree or to mine" problem.

Use worktree isolation when: the change touches `code/`, adds a new test,
or could plausibly conflict with other parallel agent work.

## E. Archive AUTO_LOOP_LOG.md

Keep only the most recent iter close + the open `Iter N+1 priorities` block
loaded in the main `docs/AUTO_LOOP_LOG.md`. Move iter 1-N-2 content into
`docs/AUTO_LOOP_LOG_archive.md` with a short index header so referents can
still find prior iters.

Run the archive pass whenever the live log exceeds ~150 lines.

## F. Task tracker discipline

Delete completed tasks once the work has shipped to main, except the
current iter and the iter just-closed. Do NOT carry "completed iter 1" or
"in_progress iter 8" tasks across the loop — they bloat every system-
reminder turn.

Mark in_progress only while you are actively working that iter; flip back
to pending if you pause or pivot.

## G. Toolbox sweep — analysis tools are part of the research process

User directive (2026-06-10). The canonical inventory of every analysis tool the
loop has built or discovered — visual renders, game-shape signatures, gated
mechanic instruments, the paired-evaluation measurement stack, the one-question
diagnostic scripts, ground-truth sources, and the event stream — lives in
[`ANALYSIS_TOOLBOX.md`](ANALYSIS_TOOLBOX.md). Sweeping that list is a standing
step of every research and diagnostic pass, not an optional extra:

* **Every residual diagnosis, research briefing, and adjudication states which
  toolbox sections were consulted and why each was used or skipped.** One line
  per section is enough; the point is that the consideration happened, because
  aggregate win rates hide what the visual and instrument tools catch (the
  unit-stacking bug and the empty-marker gap were both found by renders, not
  metrics).
* **Before dispatching a build, corroborate the diagnosis with at least one
  evidence source that is not a win rate** — a render, a signature, an
  instrument readout, or an event-stream analysis. This is the practical
  enforcement of the "ground claims in code, measure don't rule-read" rules.
* **Research-agent briefings name the relevant tools** so the agent knows what
  evidence already exists and does not re-derive or re-run it.
* **A new diagnostic tool is registered in `ANALYSIS_TOOLBOX.md` in the same
  pull request that creates it.** An unlisted tool is a tool the next wave
  forgets.

## H. Upstream pickup + pull-request size discipline

User directive (2026-06-11). Work the reviewer merges to `main` must flow back
into the loop automatically, and the loop's own output must stay reviewable
(standing rule 14 in `CLAUDE.md`).

**Upstream pickup.** The session hooks watch `origin/main` for the loop: the
session-start hook fetches and reports any upstream commits this branch lacks,
and the every-prompt hook re-checks on a fifteen-minute throttle, so a merge
landing mid-session surfaces without anyone asking. When a `PICKUP NEEDED`
notice appears:

* **Fold `origin/main` into the working branch at the next wave boundary** —
  not mid-wave (a moving base invalidates in-flight paired comparisons and
  worktree agents' bases). Merge, resolve, run the full test suite.
* **If the merge changes simulator behaviour or the archetype lists, every
  standing anchor is stale** — a fresh full N=80 re-anchor is mandatory before
  any keep/reject decision. A documentation-only or tooling-only merge keeps
  the anchor.
* Worktree agents dispatched after the fold-in must base on the post-merge
  head (the `CLAUDE.md` rule 8 base-reset dance already enforces this).

**Size discipline.** The push guard prints a soft pull-request size advisory
(never blocks), and the every-prompt hook surfaces a `SIZE` warning when the
branch passes the standing-rule-14 caps: four hundred hand-written changed
lines (soft), one thousand (hard, agree with the reviewer first), and the
rolling-branch checkpoint at roughly fifteen wave commits or one thousand five
hundred reviewable lines — at the checkpoint, mark the pull request
merge-ready and roll a fresh branch after it merges, as was done for
`sim-calibration-6` to `sim-calibration-7`. Generated files
(`data/bsdata/parsed.json` regenerations, archived evaluation logs) do not
count toward the caps.

## I. Batch screens, single re-anchor — the standing wave shape

> The full pre-flight for running an evaluation — the deterministic-eval / reuse-the-
> anchor-as-the-OFF-arm rule, the byte-identical-off validation, anchor staleness,
> flip-count forensics, and the forbidden zone — lives in
> [`EVAL_PROTOCOL.md`](EVAL_PROTOCOL.md). Read it before any screen or re-anchor; the
> wave shape below is the part of it that governs how a whole wave is batched.

User-set (2026-06-12, wave 244). Re-anchors are the expensive runs, so a wave
batches its levers against one shared baseline and pays for exactly one
re-anchor at close:

1. **Build every lever gated, default-off.** Subset combinations stay
   screenable against one baseline without rebasing mid-wave.
2. **Independent N=40 paired screens, all reusing the wave's single off-arm
   anchor log** (the reuse-confirmed-frame and no-redundant-runs rules).
   Screens run serially — the win is fewer expensive runs, not parallel
   screening; fill the evaluation wall-clock with build and diagnostic agents
   instead.
3. **Always run one combined N=40 of the keeper set before flipping** —
   levers do not compose additively. Wave-244 proof: lever 1 alone crashed
   Astra Militarum to gated 30.44 (officer dead weight), levers 1+3 together
   recovered −5.27; an independent-sum read would have wrongly rejected
   lever 1.
4. **Flip all adopted defaults together at wave close** (each lever keeps its
   kill-switch), then run **one N=80 re-anchor on the flipped frame** and
   promote it as the standing anchor.

**Lever count and pipelining.** Three to five levers per wave, preferring
file-disjoint levers so build agents do not collide. Build agents for the
NEXT wave are dispatched inside the current wave's evaluation windows, so the
serial evaluation queue — the binding constraint — never idles. The
diagnosis-quality gate stays: do not manufacture shallow levers to fill build
capacity; a wash still costs a full screen slot.

## Cleanup routine

Run `python scripts/loop_cleanup.py` at the end of each iter (or whenever
the system feels heavy). The script:

* Lists worktrees and removes those whose branch is fully merged into
  `claude/sim-calibration-<n>` or `main` (safe — no uncommitted work
  loss).
* Prunes git stashes older than 14 days, except those whose subject
  starts with `WIP-keep` (manually marked).
* Archives `docs/AUTO_LOOP_LOG.md` per rule E above.
* Compacts `data/overrides.json` (re-orders by faction prefix; doesn't
  change content).

Cleanup is opt-in (you run it manually), not a hook. Cleanup that
silently mutates state breaks the recovery flow when an agent dies
mid-task.

### Vibe-code housekeeping (standing element, user-directed 2026-06-12)

Beyond the per-iteration script above, the loop carries a standing
code-hygiene obligation: the debt that accumulates from rapid
agent-generated work (stale environment gates, dead experiment helpers,
one-shot diagnostic scripts, unused dependencies) gets paid down on a
fixed cadence instead of waiting for a dedicated cleanup project.

**Source of truth:** the prioritised checklist in
`docs/research/vibe_code_cleanup_research.md`. Treat it as a living
document — when an item completes, annotate it with the date and the
commit; when new debt classes appear, append them.

**Cadence: one checklist item per branch checkpoint.** When a rolling
calibration branch hits the size cap and checkpoints (pull request
marked merge-ready, fresh branch rolled), pick the highest-priority
unfinished checklist item and execute it on the fresh branch before or
between the first calibration waves. Low-effort items (audit sweeps,
archive passes) may additionally run as filler inside evaluation
windows, the same slot build agents use.

**Rules for cleanup work:**

* Each checklist item is its own small pull request (standing rule 14)
  — never bundled with calibration levers, so a cleanup regression is
  trivially bisectable from a behaviour change.
* Gate retirement follows the lifecycle: force the gate always-on
  (explicit default at the read site) → let it survive at least one
  N=80 re-anchor → delete the gate check and the legacy code path
  together, with a fixed-seed game-log byte-comparison as the
  behaviour-identity proof. Batches of three to five gates per pull
  request.
* Dead-code deletion needs the same byte-identity proof when it touches
  `code/`; pure `scripts/` archive moves only need the demo battle to
  exit cleanly.

**Prevention (so the debt stops accumulating):**

* Every new `SWEG_` gate declares its default explicitly at the read
  site (`os.environ.get("SWEG_X", "0") == "1"`), never the implicit
  falsy-when-unset pattern — the adoption state must be readable from
  the code, not reconstructed from memory files.
* When a screened lever is REJECTED, delete its gate and code path in
  the same wave-close commit — do not leave it default-off "in case".
  A parked lever (re-test planned) keeps its gate but gets a comment
  naming the parking decision and date.
* Evaluation logs (`wf_wave*.log`, `wf_wave*.txt`, `wf_wave*.err`,
  `wf_wave*.json`) older than the last twenty waves live in
  `data/archive/`, not in `docs/` or the repository root. Move them
  with `git mv` so the rename is tracked; a one-line `data/archive/README.md`
  describes what lives there. Untracked artifacts that pre-date the
  `data/` convention are moved on discovery; those already untracked
  may be deleted rather than archived (they are not in git history).
