# Standing rules for Claude instances on SwegHammer

These rules apply to any Claude session working on this project. Read them before
touching code.

> **For project vision, math, terrain plan, and the human-facing to-do list with
> ownership tags, see [`PROJECT.tex`](PROJECT.tex)** (rendered as `PROJECT.pdf`).
> This file is the Claude-specific operating layer on top.

> **For the autonomous calibration loop's operating procedure (fix-first
> protocol, bundle-of-one agent dispatch, trimmed prompt template,
> AUTO_LOOP_LOG archival, task-tracker discipline, periodic cleanup), see
> [`docs/AUTO_LOOP_PROCEDURE.md`](docs/AUTO_LOOP_PROCEDURE.md).** Procedural
> rules there apply on top of the standing rules in this file when working
> the loop.

## Project plan: a two-stage pipeline

SwegHammer runs as two sequenced feedback loops, not one. Future sessions:
read this before reasoning about what the project is doing, because the two
stages are easy to conflate and the user has caught this mistake before. The
authoritative non-technical picture lives in
[`OVERVIEW.tex`](OVERVIEW.tex) (rendered as `OVERVIEW.pdf`).

**Stage 1 — Make the simulator play like reality.** Run the sim, compare
per-faction win rates to the May 2026 Warp Friends ~10k-game tournament
aggregate (`scripts/evaluate_vs_meta.py`), tweak the simulator's *rules and
mechanics* until per-faction mean absolute error closes. Headline metric:
mean absolute error vs the Warp Friends per-faction win rates, target
≤ 2.0 pts. This is Goal A in `PROJECT.tex` §3.

**Stage 2 — Fit the points equation.** Once Stage 1 has converged, *freeze
the sim's rules* and fit one master equation that prices every unit from
its stats (plus small per-unit residuals for the rough edges). Run the
now-faithful sim with equation-priced units, check the spread of per-unit
win rates across the catalogue (every unit should hover near 50% in
equal-points fights), re-weight the equation's stat coefficients and
adjust the residuals, repeat until the distribution flattens. The loop
tunes the equation, not individual prices; per-unit costs fall out
deterministically from the fitted formula. Two solvers contribute:
`code/balancer.py` (Monte Carlo bisection, supplies per-unit anchor
prices) and `code/equilibrium.py` (closed-form log-least-squares on the
pairwise time-to-kill matrix, supplies the coefficient structure). This
is Goal C in `PROJECT.tex` §3.

**The feedback signals are different and must not be confused.** Stage 1
is gated by the tournament mean absolute error. Stage 2 is gated by the
win-rate spread across all units. A diagram that has pricing output
feeding back into the simulator gated by tournament data is wrong — that
conflates the two loops.

**Stage discipline.** When you pick up a task, work out which stage it
belongs to and say so in the pull request description. Rule of thumb: if
the change tunes simulator behaviour (a new ability, a fixed movement
bug, a faction rule), it is Stage 1. If the change tunes the points
equation, its stat coefficients, a per-unit residual, or the solver that
produces those coefficients, it is Stage 2. Mixing both in the same pull
request is allowed only when the mix is unavoidable, and in that case
the description must say which parts are which.

**Current state (2026-05-17).** Stage 1 mean absolute error is 7.01 pts
at N = 200 vs a 2.0 pt target — Stage 1 is not converged. Stage 2 work is
running in parallel anyway, which means current
`data/calibrated_points.json` and `data/equilibrium_points*.json` outputs
are calibrated against a sim that does not yet match reality, and will
need redoing once Stage 1 lands. Treat Stage 2 outputs as provisional
until the user signals Stage 1 convergence.

## 1. Test before pushing

Before `git push`, run `python run.py --cli` and confirm it exits cleanly. If the
demo battle crashes or the calibration suite errors out, the branch is not ready to
upload — fix it first.

Use the `--cli` flag, not bare `python run.py`. Bare `python run.py` launches the
Tkinter GUI menu (`launch_gui` → `root.mainloop()`), which blocks until the window
is closed and so never returns in a headless or automated run — it will hang the
autonomous loop. `--cli` runs the demo battle and exits. (`run.py` also falls back
to the CLI automatically when it is not attached to an interactive terminal, but
pass `--cli` explicitly so the intent is unambiguous.)

The Streamlit app (`streamlit run app.py`) can't be tested headlessly, so smoke
test by importing the catalogue (`python -c "from code.units import UNIT_CATALOG; print(len(UNIT_CATALOG))"`)
and spot-checking that every key referenced by `app.py` resolves. If you've
changed the catalogue, every preset's `a_key` and `b_key` must exist.

Windows console note: `PYTHONIOENCODING=utf-8 python run.py --cli` — without this,
the `→` arrow in `simulator.py` crashes cp1252.

## 2. Update docs in the same PR as the code that invalidates them

The right moment to update documentation is **the final step before you commit**.
The code's shape is settled, the diff is in front of you, and the doc edit lands
in the same PR as the change it describes. "I'll update docs after merge" never
happens.

Before touching any subject covered by an existing doc (`THEORY.md`,
`BASELINE.md`, `SIMULATION.md`, `ROADMAP.md`, `README.md`), read that doc first
so you don't build something that contradicts stated intent.

When you finish a change, sweep:

- `BASELINE.md` — points formula, baseline unit definition, the unit catalogue
- `ROADMAP.md` — phase status, what's done vs planned
- `README.md` — quickstart commands, project structure table
- `THEORY.md` — only if the cost model changed
- `SIMULATION.md` — only if the combat or activation model changed

## 3. Never commit, push, or open PRs without explicit user "go"

Build the change. Show the diff. Wait for the user to read it and say "go" or
"push". Only then run `git commit` / `git push` / `gh pr create`. A user
saying "build X" is not authorisation to ship X.

## 4. Branch naming: `claude/<short-description>`

Match the existing convention (`claude/bsdata-stats-import`,
`claude/warhammer-unit-costing-5WaMf`, `claude/review-todo-list-irtiP`).
Lowercase, dash-separated, descriptive.

## 5. Git identity: one-shot override, not config edit

The collaborator on this repo is `Allknight96 <jknight96@live.co.uk>`. If git
refuses to commit because no identity is configured, use:

```
git -c user.email=jknight96@live.co.uk -c user.name=Allknight96 commit ...
```

Do **not** run `git config --global user.email ...` or its `--local` variant —
that mutates persistent config. The `-c` flag is a one-shot scoped to that
single command.

## 6. Looking up WH40k rules: BSData first, Wahapedia as fallback

The canonical source for stat data in this project is BSData WH40k 10e
(`data/bsdata/cache/`). When you need a rule that isn't structured in BSData
— Feel No Pain, army rules, detachment effects, specific keyword wording, FAQ
clarifications — check **[wahapedia.ru](https://wahapedia.ru/)**, which has
free-to-read full datasheets and core rules text. Cite the URL in commit
messages or overrides when relevant so future readers can verify.

## 7. Unit catalogue lives in two layers

- `data/bsdata/parsed.json` — base stats from BSData, regenerated by the mapper
- `data/overrides.json` — hand tuning, the only place to edit unit values

Never edit `parsed.json` directly — the mapper will overwrite it. Tune via
overrides. Refresh the BSData base with:

```
python -m code.bsdata.fetch --tag <release>   # default v10.6.0
python -m code.bsdata.mapper
```

## 8. Briefing parallel sub-agents — base-branch verification

When spawning Agent calls with `isolation: "worktree"`, the worktree may be
created from a stale base (e.g. `main` rather than your current WIP HEAD).
Two agents launched mid-session both branched from main and produced
unmergeable diffs because their base was missing the WIP commits.

**Mandatory in every agent prompt that uses worktree isolation:**
- Worktrees default to being created off the default branch (usually `main`),
  NOT off your current WIP branch. The base will be wrong by default.
- Push your WIP branch to `origin` first so the agent can pull from it.
- In the prompt, tell the agent to RESET its worktree to your WIP branch
  before doing any work — the worktree is fresh, so the reset is safe.

Example briefing block:
> Run these first to align your base — the worktree is fresh, no
> uncommitted work to lose:
> ```
> git fetch origin
> git reset --hard origin/<your-wip-branch>
> git log --oneline -3
> ```
> Top commit must be `<SHA>`. If not, STOP and report "REBASE FAILED".

## 9. Don't hand-roll new units in code

If you need a unit that doesn't exist in BSData, add it as a fully-specified
entry in `data/overrides.json` (all required fields). Do not edit
`code/units.py` to add `UnitProfile(...)` entries — the catalogue is loader-built.

## 10. Cite every rule. Don't invent.

Any code that implements a 10e rule — a `Detachment` flag set True, a
`LeaderAbility` field, a simulator gate that fires per a faction ability,
a Stratagem effect — needs a matching entry in `data/rule_citations.json`.
Format:

```json
{
  "AWAKENED_DYNASTY.bonus_to_hit_when_led": {
    "source": "https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty",
    "rule_name": "Command Protocols",
    "quoted_text": "While a NECRONS CHARACTER model is leading this unit, each time a model in this unit makes an attack, add 1 to the Hit roll.",
    "trigger": "attacker's unit is led by a friendly CHARACTER in aura range",
    "effect": "+1 to the Hit roll",
    "scope": "unit-led"
  }
}
```

Required fields per entry: `source` (Wahapedia URL or, if not on Wahapedia,
the canonical free reference — Goonhammer datasheet readout, GW errata PDF),
`rule_name`, `quoted_text` (verbatim, including the "While …" trigger half),
`trigger`, `effect`, `scope` (one of `army-wide` / `unit-led` /
`character-only` / `phase-gated` / `keyword-gated` / `weapon-keyword`).

Key format: `<REGISTRY_NAME>.<field>` for detachment / leader / stratagem
flags, or a plain dotted path for simulator-side gates
(e.g. `simulator.big_guns_never_tire`).

`scripts/audit_rules.py` enforces this. Run it before committing any change
to `code/detachments.py`, `code/leaders.py`, `code/stratagems.py`, or the
rule-bearing parts of `code/simulator.py` / `code/units.py`. If you can't
find a Wahapedia / canonical citation for a rule, **stop and ask the user**.
Don't approximate or invent — that's the failure mode that got Awakened
Dynasty's rule wrong in the May 2026 calibration work.

## 11. No acronyms in pull requests or documentation — ever

Write every term out in full in pull request titles, pull request descriptions,
commit messages, and any documentation file (`*.md`, `*.tex`, in-repo guides).
This applies even to terms that feel universal in the hobby or in software.

Examples:
- "pull request", not "PR"
- "pull request description", not "PR description"
- "feel no pain", not "FNP"
- "ballistic skill", not "BS"
- "weapon skill", not "WS"
- "command point", not "CP"
- "user interface", not "UI"
- "application programming interface", not "API"
- "continuous integration", not "CI"

Code identifiers, file names, and quoted rule text are exempt — keep
`UNIT_CATALOG`, `app.py`, and verbatim Wahapedia citations as-is. The rule is
about prose written for humans, where an acronym costs the reader a lookup the
author could have spared them.

## 12. Every pull request must update the main documentation and state its goal clearly

Two things every pull request must do, no exceptions:

**Update the main documentation.** Before the pull request is opened, sweep the
documentation files listed in rule 2 (`BASELINE.md`, `ROADMAP.md`, `README.md`,
`THEORY.md`, `SIMULATION.md`) and `PROJECT.tex`, and update any section the
change touches. If the change genuinely touches no documented subject, say so
explicitly in the pull request description ("no documentation impact, swept
the following files and confirmed: …") so the reader knows it was checked, not
forgotten. Documentation updates land in the same pull request as the code,
never in a follow-up.

**Explain very clearly what the pull request is meant to achieve.** The
description must open with a plain-language statement of the goal — what
problem is being solved, what behaviour will be different after the merge, and
why this approach was chosen over alternatives. Assume the reader has not been
in the conversation that led to the change. A reviewer should be able to read
the first paragraph and know whether the pull request is worth their time,
without scrolling through the diff to reconstruct intent. Write out terms in
full per rule 11 — no acronyms in the goal statement.

## 13. Fail loud when data is missing — no silent defaults

When code cannot find a unit, override, rule citation, detachment, leader,
stratagem, or any other piece of structured data it expected to find, raise an
error that names the missing key and the file it was looked up in. Do not
substitute a default value, do not fall back to a sibling entry, and do not
return `None` and let the caller carry on as if nothing happened.

Silent fallbacks have already caused real harm on this project: a missing rule
citation that defaulted to "no effect" let the simulator run a wrong version
of Awakened Dynasty for weeks, and a typo in an override key once resolved to
the baseline unit profile without anyone noticing the catalogue load was
incomplete. Both failures would have been caught at the first run if the
lookup had thrown.

The rule applies to loaders (`code/bsdata/mapper.py`, the override merger, the
catalogue builder), to registries (`code/detachments.py`, `code/leaders.py`,
`code/stratagems.py`), and to anything else that reads from
`data/overrides.json`, `data/rule_citations.json`, or `data/bsdata/parsed.json`.
If a default genuinely is the right behaviour for a specific field — for
instance, an optional override flag that means "leave the base stat alone" —
that default must be set explicitly at the call site with a comment explaining
why silence is acceptable there, never buried in a generic `.get(key, None)`.

## 14. Keep pull requests small — one self-contained change, soft cap four hundred lines

Reviewers on this project have flagged our pull requests as too large to
review properly. The research agrees with them: the SmartBear study of code
review at Cisco found defect-detection effectiveness drops sharply once a
review exceeds roughly four hundred lines, and Google's engineering-practices
guide treats around one hundred lines as a reasonable change and around one
thousand as usually too large
(https://google.github.io/eng-practices/review/developer/small-cls.html). A
reviewer who cannot hold the whole diff in their head is approving on trust,
not reviewing.

The rule, for every pull request a Claude session opens:

- **One self-contained change per pull request.** One mechanic, one bug fix,
  one subsystem, one data batch. If the description needs the word "also",
  it is two pull requests.
- **Soft cap: four hundred changed lines** of hand-written diff (code, tests,
  and documentation together). Past that, split before opening.
- **Hard cap: one thousand changed lines.** Never open one this size without
  agreeing it with the reviewer first.
- **Generated files do not count** toward the caps —
  `data/bsdata/parsed.json` regenerations, evaluation logs, lock files. List
  them in the description as generated so the reviewer knows to skim them.
- **Pure code-motion refactors are the one exemption.** A
  move-code-without-changing-it pull request may exceed the caps, but it must
  contain zero logic changes, move one subsystem only, and state its
  behaviour-identity proof in the description (full test suite green plus a
  fixed-seed demonstration-battle game-log byte-comparison before and after).
- **The calibration loop's rolling branch must not grow unbounded.** When the
  running branch reaches roughly fifteen wave commits, or its reviewable diff
  against `main` passes roughly one thousand five hundred hand-written lines,
  stop stacking: mark the pull request merge-ready for review and start the
  next work on a fresh branch once it merges. This is the
  `sim-calibration-6` to `sim-calibration-7` checkpoint pattern, made
  standing.
- **When a change genuinely cannot be small, stack it.** Split it into a
  sequence of pull requests, each self-contained and reviewable alone, each
  description naming the one before and after it.
