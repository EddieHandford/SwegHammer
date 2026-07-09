"""
Verify-and-run harness for a distributed screening job ticket.

A "screen job" pins one screen to an exact frame -- a git commit plus a
standing anchor log -- so a paired evaluation run on a collaborator's machine
is provably comparable to one run on the owner's box. See
`docs/DISTRIBUTED_SCREENING.md` for the concept and the two-command
collaborator workflow this harness exists to support.

Usage:
    python -m scripts.screen_job data/screen_jobs/<job_id>.json [--workers N]
                                  [--dry-run] [--allow-dirty-base]

Ticket JSON schema (one file per job, conventionally
`data/screen_jobs/<job_id>.json`, produced by `scripts/make_screen_job.py`):

    {
      "job_id": str,            # ticket name; matches the file stem by convention
      "base_commit": str,       # full 40-character git SHA this ticket is pinned to
      "anchor_path": str,       # path (repo-root-relative) to the OFF-arm anchor
                                 # log, e.g. "data/_anchor_sc61a_n80_log.json"
      "anchor_sha256": str,     # hex sha256 of anchor_path's exact bytes
      "env": {str: str, ...},   # ON-arm gate env vars, e.g. {"SWEG_X": "1"}
      "battles": int,           # --battles passed to evaluate_vs_meta
      "factions": str | null,   # comma-separated --factions scope, or null for
                                 # the full frame (all 22 factions)
      "seed_start": int,        # --seed-start (default 0)
      "log_path": str,          # where evaluate_vs_meta writes the ON-arm
                                 # per-game log, e.g.
                                 # "data/screen_results/<job_id>_log.json"
      "notes": str              # free text: what this screens, expected result
    }

The harness, in order:

  1. Refuses to run unless `git rev-parse HEAD` equals `base_commit` (hard
     refusal by default; `--allow-dirty-base` downgrades this single check to
     a printed warning -- everything else stays strict).
  2. Refuses to run unless sha256(anchor_path) equals `anchor_sha256`. This
     check is ALWAYS a hard refusal -- there is no override, because a wrong
     anchor silently invalidates the OFF arm of the whole paired comparison
     (docs/EVAL_PROTOCOL.md rule 1: the anchor IS the OFF arm).
  3. Runs `evaluate_vs_meta` as a subprocess in MODULE form
     (`python -m scripts.evaluate_vs_meta`) with `PYTHONHASHSEED=0`,
     `PYTHONIOENCODING=utf-8`, the ticket's `env` vars layered over the
     current environment, `SWEG_WORKERS` from `--workers` (default 8),
     `--use-archetype`, `--battles`, `--seed-start`, `--factions` (only if
     the ticket sets one), and `--log-games log_path`.
  4. On a clean exit, joins `log_path` (the ON arm) against `anchor_path`
     (the OFF arm) with `scripts.paired_delta` -- `--scoped` when `factions`
     is set, the plain full-frame join otherwise -- and captures its stdout.
  5. Writes `data/screen_results/<job_id>.json`:
     `{job_id, ran_at_commit, anchor_sha256, machine, env, battles,
       seed_start, paired_output, exit: "ok"|"failed", error: str|null}`.
     `ran_at_commit` is the ACTUAL `git rev-parse HEAD` this run executed
     under (equal to `base_commit` unless `--allow-dirty-base` was used).

`--dry-run` performs steps 1-2 only (the two refusal checks) and exits
without spawning any subprocess -- no evaluation, no battle-running compute,
no lock contention, no RNG. Use it to sanity-check a ticket before committing
a machine to a full run, or to exercise the refusal paths against a doctored
ticket.

Eval-lock discipline (docs/LEVER_PROTOCOL.md section 5): the harness does not
implement its own lock -- `evaluate_vs_meta` already owns `data/_eval.lock`
and the subprocess inherits that discipline. If the lock is held elsewhere,
the subprocess exits non-zero with a lock message on stderr; this harness
surfaces that verbatim as `error` and does NOT retry or loop -- it is a
single-shot runner, one ticket per invocation.

This harness never introduces new randomness: every number in the paired
report traces back to evaluate_vs_meta's `pair_seed` schedule, which is
already a pure function of (a_faction, b_faction, seed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TICKET_FIELDS = (
    "job_id", "base_commit", "anchor_path", "anchor_sha256", "env",
    "battles", "factions", "seed_start", "log_path", "notes",
)


def load_ticket(ticket_path: Path) -> Dict[str, Any]:
    """Load and shape-check a ticket JSON. Fails loud on any missing field
    (CLAUDE.md rule 13) -- a ticket that is missing a key never falls back to
    a default, it names the missing key and the file it came from."""
    if not ticket_path.exists():
        raise SystemExit(f"screen_job: ticket not found: {ticket_path}")
    with open(ticket_path, encoding="utf-8") as fh:
        ticket = json.load(fh)
    missing = [f for f in REQUIRED_TICKET_FIELDS if f not in ticket]
    if missing:
        raise SystemExit(
            f"screen_job: ticket {ticket_path} is missing required field(s) "
            f"{missing} -- see the schema in scripts/screen_job.py's module "
            f"docstring."
        )
    return ticket


def _git_head(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root,
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"screen_job: `git rev-parse HEAD` failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def verify_base_commit(ticket: Dict[str, Any], repo_root: Path,
                        allow_dirty_base: bool) -> str:
    """Check 1: the checked-out commit must equal the ticket's base_commit.

    Returns the ACTUAL current HEAD sha. Hard-refuses (SystemExit) on
    mismatch unless allow_dirty_base downgrades it to a printed warning.
    """
    head = _git_head(repo_root)
    expected = ticket["base_commit"]
    if head != expected:
        message = (
            f"base commit mismatch: ticket {ticket['job_id']!r} is pinned to "
            f"{expected}, but this worktree's HEAD is {head}. A screen run "
            f"under a different commit is not comparable to the frame the "
            f"ticket describes -- pull/checkout {expected} first."
        )
        if allow_dirty_base:
            print(f"WARNING (--allow-dirty-base): {message}")
        else:
            raise SystemExit(
                f"REFUSED: {message}\n"
                f"Pass --allow-dirty-base to downgrade this to a warning and "
                f"run anyway (not recommended -- the result will not be a "
                f"clean cross-machine comparison)."
            )
    return head


def verify_anchor(ticket: Dict[str, Any], repo_root: Path) -> Path:
    """Check 2: the anchor file's bytes must hash to the ticket's
    anchor_sha256. ALWAYS a hard refusal -- there is no override flag, because
    a silently-wrong anchor invalidates the OFF arm of the whole comparison.
    """
    anchor_path = repo_root / ticket["anchor_path"]
    if not anchor_path.exists():
        raise SystemExit(
            f"REFUSED: anchor file not found: {anchor_path} "
            f"(ticket {ticket['job_id']!r} expects it at {ticket['anchor_path']})."
        )
    actual = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
    expected = ticket["anchor_sha256"]
    if actual != expected:
        raise SystemExit(
            f"REFUSED: anchor sha256 mismatch for {anchor_path}.\n"
            f"  ticket expects: {expected}\n"
            f"  file hashes to: {actual}\n"
            f"The anchor on disk is not the exact bytes this ticket was cut "
            f"against -- do not run (docs/EVAL_PROTOCOL.md rule 1: the anchor "
            f"IS the OFF arm; a mismatched anchor is a silently wrong OFF arm)."
        )
    return anchor_path


def run_eval(ticket: Dict[str, Any], repo_root: Path, workers: int) -> subprocess.CompletedProcess:
    """Step 3: run evaluate_vs_meta as a subprocess, module form, ticket env
    layered on top of the current environment. Single-shot -- no retry."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update({str(k): str(v) for k, v in ticket["env"].items()})
    env["SWEG_WORKERS"] = str(workers)

    log_path = repo_root / ticket["log_path"]
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "scripts.evaluate_vs_meta",
        "--battles", str(ticket["battles"]),
        "--seed-start", str(ticket["seed_start"]),
        "--use-archetype",
        "--log-games", str(log_path),
    ]
    if ticket["factions"]:
        cmd += ["--factions", ticket["factions"]]

    print(f"Running: {' '.join(cmd)}")
    print(f"  env overrides: {ticket['env']}  SWEG_WORKERS={workers}")
    return subprocess.run(cmd, cwd=repo_root, env=env, capture_output=True, text=True)


def run_paired_delta(ticket: Dict[str, Any], anchor_path: Path, repo_root: Path) -> subprocess.CompletedProcess:
    """Step 4: join the ON-arm log against the anchor (OFF arm)."""
    log_path = repo_root / ticket["log_path"]
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "-m", "scripts.paired_delta", str(anchor_path), str(log_path)]
    if ticket["factions"]:
        cmd.append("--scoped")
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=repo_root, env=env, capture_output=True, text=True)


def write_result(ticket: Dict[str, Any], repo_root: Path, ran_at_commit: str,
                  battles: int, seed_start: int, paired_output: Optional[str],
                  exit_status: str, error: Optional[str]) -> Path:
    """Step 5: write data/screen_results/<job_id>.json."""
    result = {
        "job_id": ticket["job_id"],
        "ran_at_commit": ran_at_commit,
        "anchor_sha256": ticket["anchor_sha256"],
        "machine": platform.node(),
        "env": ticket["env"],
        "battles": battles,
        "seed_start": seed_start,
        "paired_output": paired_output,
        "exit": exit_status,
        "error": error,
    }
    out_path = repo_root / "data" / "screen_results" / f"{ticket['job_id']}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("ticket", type=str, help="path to a screen job ticket JSON")
    p.add_argument("--workers", type=int, default=8,
                    help="SWEG_WORKERS for the evaluate_vs_meta subprocess "
                         "(default 8 -- the standing CPU-budget rule, "
                         "docs/LEVER_PROTOCOL.md section 5).")
    p.add_argument("--dry-run", action="store_true",
                    help="Verify the ticket's base_commit and anchor_sha256 "
                         "only; do not run any evaluation.")
    p.add_argument("--allow-dirty-base", action="store_true",
                    help="Downgrade a base_commit mismatch from a hard "
                         "refusal to a printed warning. The anchor sha256 "
                         "check has no such override.")
    args = p.parse_args()

    ticket_path = Path(args.ticket)
    ticket = load_ticket(ticket_path)

    print(f"Ticket: {ticket['job_id']}  ({ticket_path})")
    head = verify_base_commit(ticket, REPO_ROOT, args.allow_dirty_base)
    anchor_path = verify_anchor(ticket, REPO_ROOT)
    print(f"OK: base_commit and anchor_sha256 both verified.")

    if args.dry_run:
        print("DRY RUN: verification only, no evaluation run.")
        sys.exit(0)

    eval_proc = run_eval(ticket, REPO_ROOT, args.workers)
    sys.stdout.write(eval_proc.stdout)
    sys.stderr.write(eval_proc.stderr)
    if eval_proc.returncode != 0:
        error = eval_proc.stderr.strip() or eval_proc.stdout.strip() or \
            f"evaluate_vs_meta exited {eval_proc.returncode}"
        out_path = write_result(ticket, REPO_ROOT, head, ticket["battles"],
                                 ticket["seed_start"], None, "failed", error)
        print(f"FAILED -- result written to {out_path}")
        sys.exit(1)

    paired_proc = run_paired_delta(ticket, anchor_path, REPO_ROOT)
    sys.stdout.write(paired_proc.stdout)
    sys.stderr.write(paired_proc.stderr)
    if paired_proc.returncode != 0:
        error = paired_proc.stderr.strip() or f"paired_delta exited {paired_proc.returncode}"
        out_path = write_result(ticket, REPO_ROOT, head, ticket["battles"],
                                 ticket["seed_start"], paired_proc.stdout, "failed", error)
        print(f"FAILED -- result written to {out_path}")
        sys.exit(1)

    out_path = write_result(ticket, REPO_ROOT, head, ticket["battles"],
                             ticket["seed_start"], paired_proc.stdout, "ok", None)
    print(f"OK -- result written to {out_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
