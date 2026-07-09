# Distributed screening across two collaborators' machines

This is the one-page guide to running screens split across more than one
machine without losing frame identity. It sits on top of
[`EVAL_PROTOCOL.md`](EVAL_PROTOCOL.md) (how to measure) and
[`LEVER_PROTOCOL.md`](LEVER_PROTOCOL.md) (what to build) -- read those first.
This page adds nothing about what a good lever is; it is purely about running
one screen's compute on two boxes and trusting the combined result.

## The frame-identity concept

A paired evaluation is only a valid comparison when both arms are byte-for-
byte the same frame: the same simulator code and the same off-arm anchor. On
one machine that is trivially true because both arms run back to back. Across
two machines it is not automatic -- a collaborator could be a commit behind,
or hold a stale copy of the anchor log, and the resulting screen would look
plausible while comparing against the wrong baseline.

The fix is to pin both halves of the frame explicitly in a **job ticket**:

- **`base_commit`** -- the full git commit SHA the screen must run under.
- **`anchor_sha256`** -- the sha256 of the exact anchor log bytes the screen's
  OFF arm reuses (per `EVAL_PROTOCOL.md` rule 1: the anchor IS the OFF arm).

`scripts/screen_job.py` refuses to run a ticket whose worktree HEAD does not
match `base_commit`, and always refuses (no override) when the anchor file's
hash does not match `anchor_sha256`. A ticket that passes both checks is
running the identical frame the ticket author measured against, regardless of
which machine executes it.

## Policy change: the standing anchor now ships in-repo

Previously the standing anchor log (`data/_anchor_<frame>_n80_log.json`,
roughly 1-2 megabytes) was a local, untracked file -- every anchor promotion
had to be manually copied between machines out of band, which is exactly the
staleness risk the frame-identity check above exists to catch. From this
change onward:

- **The current standing anchor is committed to the repository.** A
  collaborator who runs `git pull` has the exact anchor bytes any ticket's
  `anchor_sha256` was cut against -- no manual file copy, no staleness risk.
- **Superseded anchors are pruned from git** (not from disk) at the next
  re-anchor. Keep them locally for historical diagnosis if useful, but do not
  carry every retired anchor in the repository forever -- each is 1-2
  megabytes and only the current one is load-bearing for any live ticket.
- Adding the standing anchor requires `git add -f` the first time only if a
  future `.gitignore` rule excludes it; as of this change no such rule exists
  (checked with `git check-ignore`), so the anchor commits with a plain `git
  add`. Use `-f` anyway if a repository-hygiene pass later adds a broad
  `data/*.json` exclusion, so the anchor commit does not silently start being
  skipped.

## The two-command collaborator workflow

Once a ticket exists (see below), running it on any machine that has cloned
the repository is exactly two commands:

```
git pull
python -m scripts.screen_job data/screen_jobs/<job_id>.json
```

That is the entire interface. `screen_job.py` verifies the frame, runs the
evaluation, joins it against the anchor with `scripts/paired_delta`, and
writes `data/screen_results/<job_id>.json` with the paired output and a
`machine` field (`platform.node()`) identifying which box produced it.

Tickets are generated once, by whoever is proposing the screen, with:

```
python -m scripts.make_screen_job --id <job_id> --battles 20 \
    --gate SWEG_NEW_LEVER=1 --factions "Orks" --notes "what this screens"
```

`make_screen_job.py` refuses to write a ticket from a dirty working tree --
a ticket must pin a commit a collaborator can actually `git pull` to.

## Run the identity-check ticket first

Before any new machine's screens count toward a keep/reject decision, it must
reproduce `data/screen_jobs/identity_check.json` -- an Orks-scoped, N=20,
no-gate-overrides ticket -- with **zero flips** against the standing anchor.
Zero flips proves the machine's simulator run is byte-identical to the anchor
run for a faction cell it should trivially match (the same rule
`EVAL_PROTOCOL.md` rule 2 uses locally: a both-off run must reproduce the
anchor exactly). A machine that cannot pass the identity check -- a
mismatched Python version, a stale checkout, a hash-seed leak -- must not be
trusted for a real screen until the mismatch is found and fixed.

```
git pull
python -m scripts.screen_job data/screen_jobs/identity_check.json
```

Check the written `data/screen_results/identity_check.json`'s `paired_output`
for `flips` columns of 0 across the board before treating that machine's
future tickets as valid.

## Splitting one screen across two machines: the seed-window pattern

A single N=40 screen can be halved across two machines by giving each one a
disjoint `--seed-start` window over the same ticket parameters, then unioning
the two per-game logs before pairing:

- Machine A's ticket: `seed_start: 0`, `battles: 20` (seeds 0-19).
- Machine B's ticket: `seed_start: 20`, `battles: 20` (seeds 20-39).

Each machine writes its own `log_path`
(`data/screen_results/<job_id>_log.json` per ticket -- give the two tickets
distinct `job_id`s, e.g. `<job_id>_a` and `<job_id>_b`, so they do not clobber
each other's log file). Because `evaluate_vs_meta`'s `pair_seed` schedule is a
pure function of `(a_faction, b_faction, seed)`, the two logs cover disjoint,
non-overlapping games on the same schedule -- union them (the two JSON
`games` arrays concatenate cleanly) and run `scripts.paired_delta` once over
the combined log to get the full N=40 paired verdict. This is the same
disjoint-seed-window guarantee `scripts/paired_sequential.py` already relies
on for its own early-stop batching, applied across machines instead of across
time.

## Central processing unit etiquette

- `SWEG_WORKERS` defaults to 8 in `scripts/screen_job.py` (half of a 16-core
  box) per the standing central-processing-unit-budget rule
  (`LEVER_PROTOCOL.md` section 5, set after a 100 percent freeze of the
  owner's machine). Pass `--workers N` to override on a machine with a
  different core count, but do not default to using every core.
- **One compute lane per machine.** `evaluate_vs_meta` already refuses to
  start a second concurrent run on the SAME machine via `data/_eval.lock`;
  that lock is local to each machine's filesystem, so it does not by itself
  prevent two DIFFERENT machines from running screens at the same time --
  that is fine and is the whole point of distributing the work. What it does
  not permit is a second lane on the SAME box while one ticket is running;
  do not launch a second `screen_job.py` invocation (or any other
  battle-running compute) on a machine that already holds the lock.
