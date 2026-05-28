"""Auto-loop housekeeping — keep per-iter token / disk / shell cost down.

Run manually at the end of an iter or whenever the workspace feels heavy:

    python scripts/loop_cleanup.py [--dry-run] [--archive-threshold 150]

What it does:

1. List git worktrees and remove the ones whose branch is fully merged
   into the current WIP branch (claude/sim-calibration-*) or origin/main.
   Worktrees with uncommitted changes are NEVER touched.

2. List git stashes; flag any older than 14 days that don't start with
   "WIP-keep" for removal. Removal requires --rm-stashes (separate flag —
   stashes are a recovery vehicle, kill them deliberately).

3. Archive docs/AUTO_LOOP_LOG.md when the live log exceeds the line
   threshold (default 150). Iter blocks older than the most recent two
   are moved into docs/AUTO_LOOP_LOG_archive.md with a one-line index
   appended to the live log.

4. Report disk + git stats so you can see the effect.

Intentionally NOT a hook: cleanup that silently mutates state breaks the
agent-crash recovery flow (an agent dies mid-iter, you fish its work out
of its worktree, then the cleanup nukes the worktree). You run this when
you've confirmed there's nothing to salvage.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "docs" / "AUTO_LOOP_LOG.md"
ARCHIVE = REPO / "docs" / "AUTO_LOOP_LOG_archive.md"


def _run(args: List[str], check: bool = True) -> str:
    out = subprocess.run(args, cwd=REPO, capture_output=True, text=True, check=False)
    if check and out.returncode != 0:
        sys.stderr.write(out.stderr)
        raise SystemExit(out.returncode)
    return out.stdout


@dataclass
class Worktree:
    path: str
    branch: Optional[str]
    head: str

    @property
    def is_main(self) -> bool:
        return self.path.endswith("SwegHammer") and "worktrees" not in self.path

    @property
    def is_dirty(self) -> bool:
        out = _run(["git", "-C", self.path, "status", "--porcelain"], check=False)
        return bool(out.strip())


def list_worktrees() -> List[Worktree]:
    raw = _run(["git", "worktree", "list", "--porcelain"]).splitlines()
    out: List[Worktree] = []
    cur: dict = {}
    for line in raw + [""]:
        if line.startswith("worktree "):
            if cur:
                out.append(Worktree(path=cur["worktree"], branch=cur.get("branch"),
                                    head=cur.get("HEAD", "")))
            cur = {"worktree": line[len("worktree "):].strip()}
        elif line.startswith("HEAD "):
            cur["HEAD"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):].strip().removeprefix("refs/heads/")
        elif not line.strip() and cur:
            out.append(Worktree(path=cur["worktree"], branch=cur.get("branch"),
                                head=cur.get("HEAD", "")))
            cur = {}
    return out


def current_wip_branch() -> str:
    return _run(["git", "branch", "--show-current"]).strip()


def merged_into(target: str) -> set:
    raw = _run(["git", "branch", "--merged", target, "-a"]).splitlines()
    return {b.strip().lstrip("* ").removeprefix("remotes/origin/") for b in raw if b.strip()}


def clean_worktrees(dry_run: bool, wip: str) -> int:
    merged = merged_into(wip) | merged_into("origin/main")
    removed = 0
    for wt in list_worktrees():
        if wt.is_main:
            continue
        if wt.branch and wt.branch.startswith("worktree-agent-"):
            # Only remove if (a) clean and (b) branch is merged
            if wt.is_dirty:
                print(f"  KEEP dirty {wt.path}")
                continue
            if wt.branch not in merged:
                # Allow removal of agent worktrees even if not merged — they're
                # ephemeral by design and we've already cherry-picked what we
                # want. Skip only if dirty.
                pass
            if dry_run:
                print(f"  WOULD REMOVE {wt.path}")
            else:
                # Double -f overrides Claude-agent worktree locks left behind
                # when a parent claude.exe exited without releasing them. Single
                # -f errors with "cannot remove a locked working tree"; the
                # script previously printed REMOVED while git silently failed.
                _run(["git", "worktree", "remove", "-f", "-f", wt.path], check=False)
                _run(["git", "branch", "-D", wt.branch], check=False)
                print(f"  REMOVED {wt.path}")
            removed += 1
    _run(["git", "worktree", "prune"], check=False)
    return removed


_AGE_RE = re.compile(r"^stash@\{(\d+)\}: (?:On|WIP on) ([^:]+): (.+)$")


def list_stashes(max_age_days: int) -> List[tuple]:
    raw = _run(["git", "stash", "list", "--date=iso", "--format=%gd|%ci|%s"]).splitlines()
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=max_age_days)
    out = []
    for line in raw:
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        ref, when, subj = parts
        try:
            ts = _dt.datetime.fromisoformat(when.strip().replace(" ", "T", 1).replace(" ", ""))
        except Exception:
            continue
        if ts < cutoff and not subj.strip().startswith("WIP-keep"):
            out.append((ref, when.strip(), subj.strip()))
    return out


def clean_stashes(dry_run: bool, do_remove: bool, max_age_days: int) -> int:
    stale = list_stashes(max_age_days)
    for ref, when, subj in stale:
        if do_remove and not dry_run:
            _run(["git", "stash", "drop", ref], check=False)
            print(f"  DROPPED {ref}  ({when})  {subj}")
        else:
            print(f"  STALE   {ref}  ({when})  {subj}")
    return len(stale)


_ITER_HEADER_RE = re.compile(r"^### Iter (\d+)\b", re.MULTILINE)


def archive_log(threshold: int, dry_run: bool) -> int:
    if not LOG.exists():
        return 0
    text = LOG.read_text(encoding="utf-8")
    if text.count("\n") < threshold:
        print(f"  log under threshold ({text.count(chr(10))} < {threshold}); nothing to archive")
        return 0
    iters = list(_ITER_HEADER_RE.finditer(text))
    if len(iters) < 3:
        print(f"  log has < 3 iter headers; nothing to archive")
        return 0
    # Keep the most recent two iter blocks live; archive the rest.
    keep_start = iters[-2].start()
    archive_chunk = text[:keep_start]
    live_remainder = text[keep_start:]
    if dry_run:
        print(f"  WOULD ARCHIVE {archive_chunk.count(chr(10))} lines from {LOG.name}")
        return archive_chunk.count("\n")
    if ARCHIVE.exists():
        ARCHIVE.write_text(ARCHIVE.read_text(encoding="utf-8") + "\n" + archive_chunk,
                           encoding="utf-8")
    else:
        ARCHIVE.write_text("# Auto-loop log archive\n\n"
                           "Archived iter blocks from `AUTO_LOOP_LOG.md`. The live log "
                           "keeps only the most recent two iter closes.\n\n"
                           + archive_chunk, encoding="utf-8")
    # Live log gets a brief index pointer at the top
    LOG.write_text("# Auto-loop log (recent)\n\n"
                   "Older iter blocks live in `AUTO_LOOP_LOG_archive.md`.\n\n"
                   + live_remainder, encoding="utf-8")
    print(f"  ARCHIVED {archive_chunk.count(chr(10))} lines")
    return archive_chunk.count("\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="print actions without doing them")
    p.add_argument("--archive-threshold", type=int, default=150,
                   help="line count above which the live log gets trimmed")
    p.add_argument("--rm-stashes", action="store_true",
                   help="actually drop stale stashes (default: list only)")
    p.add_argument("--stash-age-days", type=int, default=14)
    args = p.parse_args()

    wip = current_wip_branch()
    print(f"WIP branch: {wip}")

    print("\nWorktrees:")
    n_wt = clean_worktrees(args.dry_run, wip)
    print(f"  {n_wt} removed\n" if not args.dry_run else f"  {n_wt} flagged\n")

    print("Stashes:")
    n_st = clean_stashes(args.dry_run, args.rm_stashes, args.stash_age_days)
    print(f"  {n_st} stale {'dropped' if args.rm_stashes and not args.dry_run else 'flagged'}\n")

    print(f"Log archive ({LOG.name}):")
    archive_log(args.archive_threshold, args.dry_run)
    print()

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
