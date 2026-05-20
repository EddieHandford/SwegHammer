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
