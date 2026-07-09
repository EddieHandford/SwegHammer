"""
Ticket generator for `scripts.screen_job`.

Writes a screen job ticket that pins one screen to an exact frame -- the
current git commit and a chosen standing anchor log -- so a collaborator on
another machine can reproduce the exact comparison
(`python -m scripts.screen_job data/screen_jobs/<job_id>.json`). See
`docs/DISTRIBUTED_SCREENING.md` for the concept and workflow, and the schema
docstring in `scripts/screen_job.py` for the ticket's exact fields.

Usage:
    python -m scripts.make_screen_job --id <job_id> --battles 20 \
        [--gate SWEG_X=1 [--gate SWEG_Y=0 ...]] \
        [--factions "Orks,Aeldari"] [--seed-start 0] \
        [--anchor data/_anchor_sc61a_n80_log.json] [--notes "..."] [--force]

Computes:
  - base_commit   = `git rev-parse HEAD`
  - anchor_path   = --anchor, or (default) the `data/_anchor_*_n80_log.json`
                     file with the newest mtime -- i.e. the most recently
                     promoted standing anchor.
  - anchor_sha256 = sha256 of anchor_path's exact bytes.

Refuses to run when the working tree is dirty (`git status --porcelain` is
non-empty): a ticket pins a commit collaborators can `git pull` to, so it must
describe a state that is actually committed (and, in practice, pushed) --
--force overrides this with a printed warning, for local dry-runs only.

Writes `data/screen_jobs/<job_id>.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git_head(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root,
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"make_screen_job: `git rev-parse HEAD` failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _git_is_dirty(repo_root: Path) -> bool:
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo_root,
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"make_screen_job: `git status` failed: {proc.stderr.strip()}")
    return bool(proc.stdout.strip())


def _default_anchor(repo_root: Path) -> Path:
    """The most recently promoted standing anchor: the
    data/_anchor_*_n80_log.json file with the newest mtime."""
    candidates = sorted(
        repo_root.glob("data/_anchor_*_n80_log.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise SystemExit(
            "make_screen_job: no data/_anchor_*_n80_log.json found -- pass "
            "--anchor explicitly."
        )
    return candidates[-1]


def _parse_gates(gate_args: List[str]) -> Dict[str, str]:
    """Parse repeated --gate VAR=val into a dict. Fails loud on a malformed
    entry rather than silently dropping it (CLAUDE.md rule 13)."""
    out: Dict[str, str] = {}
    for entry in gate_args:
        if "=" not in entry:
            raise SystemExit(f"make_screen_job: bad --gate entry (need VAR=val): {entry!r}")
        k, v = entry.split("=", 1)
        k = k.strip()
        if not k:
            raise SystemExit(f"make_screen_job: bad --gate entry (empty VAR): {entry!r}")
        out[k] = v.strip()
    return out


def make_ticket(job_id: str, battles: int, gates: Dict[str, str],
                 factions: Optional[str], seed_start: int,
                 anchor_path: Path, notes: str, repo_root: Path,
                 force: bool) -> Dict:
    if _git_is_dirty(repo_root) and not force:
        raise SystemExit(
            "REFUSED: working tree is dirty. A screen job ticket pins a "
            "commit collaborators can `git pull` and reproduce -- commit "
            "(and push) first, or pass --force for a local-only dry-run "
            "ticket (its base_commit will not be fetchable by anyone else)."
        )
    if _git_is_dirty(repo_root) and force:
        print("WARNING (--force): working tree is dirty; base_commit will "
              "describe the last commit, NOT the files currently on disk.")

    head = _git_head(repo_root)
    anchor_sha256 = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
    anchor_rel = anchor_path.resolve().relative_to(repo_root.resolve()).as_posix()

    return {
        "job_id": job_id,
        "base_commit": head,
        "anchor_path": anchor_rel,
        "anchor_sha256": anchor_sha256,
        "env": gates,
        "battles": battles,
        "factions": factions,
        "seed_start": seed_start,
        "log_path": f"data/screen_results/{job_id}_log.json",
        "notes": notes,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--id", type=str, required=True, dest="job_id",
                    help="job_id -- also the output filename stem "
                         "(data/screen_jobs/<id>.json).")
    p.add_argument("--battles", type=int, required=True,
                    help="--battles the ticket will run.")
    p.add_argument("--gate", action="append", default=[],
                    help='One ON-arm env gate "VAR=val". Repeat for '
                         'multiple gates. Omit entirely for a no-gate '
                         '(identity-check style) ticket.')
    p.add_argument("--factions", type=str, default=None,
                    help="Comma-separated faction scope for --factions. "
                         "Omit for the full 22-faction frame.")
    p.add_argument("--seed-start", type=int, default=0, dest="seed_start")
    p.add_argument("--anchor", type=str, default=None,
                    help="Anchor log path. Default: the newest "
                         "data/_anchor_*_n80_log.json by mtime.")
    p.add_argument("--notes", type=str, default="",
                    help="Free-text notes stored in the ticket (what this "
                         "screens, expected result).")
    p.add_argument("--force", action="store_true",
                    help="Write the ticket even with a dirty working tree "
                         "(prints a warning; the ticket will not be "
                         "reproducible by a collaborator).")
    args = p.parse_args()

    anchor_path = Path(args.anchor) if args.anchor else _default_anchor(REPO_ROOT)
    if not anchor_path.is_absolute():
        anchor_path = REPO_ROOT / anchor_path
    if not anchor_path.exists():
        raise SystemExit(f"make_screen_job: anchor not found: {anchor_path}")

    gates = _parse_gates(args.gate)
    ticket = make_ticket(
        job_id=args.job_id, battles=args.battles, gates=gates,
        factions=args.factions, seed_start=args.seed_start,
        anchor_path=anchor_path, notes=args.notes, repo_root=REPO_ROOT,
        force=args.force,
    )

    out_path = REPO_ROOT / "data" / "screen_jobs" / f"{args.job_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existed = out_path.exists()
    out_path.write_text(json.dumps(ticket, indent=2), encoding="utf-8")

    print(f"{'Overwrote' if existed else 'Wrote'} {out_path}")
    print(f"  base_commit   = {ticket['base_commit']}")
    print(f"  anchor_path   = {ticket['anchor_path']}")
    print(f"  anchor_sha256 = {ticket['anchor_sha256']}")
    print(f"  env           = {ticket['env']}")
    print(f"  battles       = {ticket['battles']}  seed_start = {ticket['seed_start']}  "
          f"factions = {ticket['factions']}")


if __name__ == "__main__":
    main()
