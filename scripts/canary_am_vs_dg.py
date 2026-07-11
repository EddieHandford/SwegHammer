"""
Paired Astra Militarum vs Death Guard canary runner (docs/DECISION_LEDGER.md
"THE DENIAL PROGRAM + CANARY LOOP").

Runs ONLY the two ordered pairings of the owner-designated canary matchup —
("Astra Militarum", "Death Guard") and ("Death Guard", "Astra Militarum") — under
the SAME deterministic pair_seed schedule scripts/evaluate_vs_meta.py uses, so its
per-game log joins the standing full-matrix anchor game-for-game with
scripts/paired_delta.py (no --scoped needed). Seeds 0..79 reproduce the anchor's
160 canary-cell games exactly, giving a zero-cost OFF arm for the paired delta:
run this on the ON arm (the gates set in the environment), point --log-games at a
scratch path, and paired_delta.py --anchor joins it against the saved anchor log.

Vanilla WH40k 10e rules, use_archetype=True (the tournament-realistic curated
lists), exactly matching the anchor frame. It reuses evaluate_vs_meta's own worker
(`_run_battle_job`, side roll-off and all) and its game-log format verbatim, and
acquires the SAME global serial-eval lock evaluate_vs_meta.main does before running
any battle.

Usage:
    python -m scripts.canary_am_vs_dg --battles 80 --log-games data/_canary_on.json
    python -m scripts.canary_am_vs_dg --battles 20            # quick smoke
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

# Lock Python's hash randomisation off BEFORE importing anything from code.* so
# the simulator's set / dict-of-string iteration order is reproducible and this
# run's seeds land on exactly the anchor's games. Mirrors evaluate_vs_meta's
# guard (and re-exec via subprocess, robust on this Windows / Git-Bash box).
# Because we pin PYTHONHASHSEED=0 here first, importing evaluate_vs_meta below
# does NOT trigger its own re-exec (its guard sees the seed already set).
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import subprocess
    sys.exit(
        subprocess.run(
            [sys.executable, "-m", "scripts.canary_am_vs_dg"] + sys.argv[1:],
            env=os.environ,
        ).returncode
    )

from scripts.evaluate_vs_meta import (  # noqa: E402  (after the hash-seed guard)
    FACTIONS,
    _run_battle_job,
    _write_game_log,
)

CANARY_A = "Astra Militarum"
CANARY_B = "Death Guard"


def _build_canary_jobs(
    n: int, seed_start: int,
) -> List[Tuple[str, str, int, int, Optional[object], bool, Optional[Dict[str, float]]]]:
    """The exact pair_seed schedule scripts/evaluate_vs_meta.run_matrix builds,
    restricted to the two ordered canary pairings. Vanilla rules (None),
    use_archetype=True, no price overrides — the anchor frame."""
    fac_idx = {f: i for i, f in enumerate(FACTIONS)}
    ai, bi = fac_idx[CANARY_A], fac_idx[CANARY_B]
    # The registered FACTIONS indices (docs/DECISION_LEDGER.md): AM=14, DG=6.
    assert ai == 14 and bi == 6, (
        f"FACTIONS indices drifted: Astra Militarum={ai} (want 14), "
        f"Death Guard={bi} (want 6) — the pair_seed schedule would no longer "
        f"reproduce the anchor's canary games."
    )
    jobs = []
    for a_fac, b_fac in ((CANARY_A, CANARY_B), (CANARY_B, CANARY_A)):
        i, j = fac_idx[a_fac], fac_idx[b_fac]
        for s in range(seed_start, seed_start + n):
            pair_seed = (i * 1000 + j) * 100 + s
            jobs.append((a_fac, b_fac, s, pair_seed, None, True, None))
    return jobs


def _acquire_eval_lock():
    """Acquire the GLOBAL serial-eval lock exactly as evaluate_vs_meta.main does
    (git-common-dir/sweg_eval.lock), so the canary honours the same serial-only
    discipline and never collides with a running full-matrix eval. Returns
    nothing; registers an atexit unlink. Raises SystemExit if the lane is held."""
    import atexit
    import pathlib
    import subprocess as _lsp
    import time
    try:
        _common = _lsp.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        _lock = (pathlib.Path(_common) / "sweg_eval.lock"
                 if _common else pathlib.Path("data/_eval.lock"))
    except Exception:
        _lock = pathlib.Path("data/_eval.lock")
    if _lock.exists() and os.environ.get("SWEG_EVAL_FORCE") != "1":
        _other_alive = False
        _other_pid = None
        try:
            _other_pid = int(_lock.read_text().split()[0])
            if time.time() - _lock.stat().st_mtime < 7200:
                if os.name == "nt":
                    import subprocess as _sp
                    _tl = _sp.run(
                        ["tasklist", "/FI", f"PID eq {_other_pid}"],
                        capture_output=True, text=True, timeout=30,
                    ).stdout.lower()
                    _other_alive = "python" in _tl
                else:
                    os.kill(_other_pid, 0)
                    _other_alive = True
        except Exception:
            _other_alive = False
        if _other_alive:
            raise SystemExit(
                f"another eval run (pid {_other_pid}) holds the serial-eval "
                f"lock — serial evals only (docs/EVAL_PROTOCOL.md). Wait for it, "
                f"or set SWEG_EVAL_FORCE=1 if the lock is wrongly held."
            )
    if _lock.exists() and os.environ.get("SWEG_EVAL_FORCE") != "1":
        try:
            _lock.unlink()
        except OSError:
            pass
    try:
        _fd = os.open(str(_lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(_fd, str(os.getpid()).encode())
        os.close(_fd)
    except FileExistsError:
        raise SystemExit(
            "another eval run grabbed the serial-eval lock in the same window "
            "(atomic acquisition) — serial evals only; retry shortly."
        )
    atexit.register(lambda: _lock.unlink(missing_ok=True))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--battles", type=int, default=20,
                   help="Seeds per ordered pairing (default 20). 80 reproduces "
                        "the anchor's 160-game canary cell (80 per slot order).")
    p.add_argument("--seed-start", type=int, default=0,
                   help="First per-pairing seed index (default 0). Keep "
                        "seed-start + battles <= 100 (pair_seed packs two digits).")
    p.add_argument("--log-games", type=str, default=None,
                   help="Write every per-game winner to this JSON path (the "
                        "evaluate_vs_meta format) for a paired join against the "
                        "anchor via scripts/paired_delta.py.")
    p.add_argument("--workers", type=int, default=None,
                   help="Worker processes. Default ~70 percent of cores; pass 1 "
                        "for the serial code path.")
    args = p.parse_args()
    if args.seed_start + args.battles > 100:
        raise SystemExit("--seed-start + --battles must be <= 100 (pair_seed packing).")

    _acquire_eval_lock()

    jobs = _build_canary_jobs(args.battles, args.seed_start)

    max_workers = args.workers
    if max_workers is None:
        max_workers = max(1, int((os.cpu_count() or 2) * 0.7))

    if max_workers <= 1:
        results_iter = map(_run_battle_job, jobs)
    else:
        executor = ProcessPoolExecutor(max_workers=max_workers)
        results_iter = executor.map(_run_battle_job, jobs, chunksize=64)

    pair_winners: Dict[Tuple[str, str], Counter] = {}
    game_log: List[Tuple[str, str, int, Optional[str]]] = []
    try:
        for a_fac, b_fac, s, winner in results_iter:
            pair_winners.setdefault((a_fac, b_fac), Counter())
            if winner is not None:
                pair_winners[(a_fac, b_fac)][winner] += 1
            game_log.append((a_fac, b_fac, s, winner))
    finally:
        if max_workers > 1:
            executor.shutdown(wait=True)

    if args.log_games:
        _write_game_log(args.log_games, args.battles, game_log)

    n = args.battles
    ad = pair_winners.get((CANARY_A, CANARY_B), Counter())
    da = pair_winners.get((CANARY_B, CANARY_A), Counter())
    # A-frame win rate of each ordered cell (winner already re-oriented to a_fac
    # by the worker's side roll-off), and the both-slots Astra Militarum rate.
    am_as_a = ad.get("A", 0) / n * 100.0 if n else 0.0
    am_as_b = da.get("B", 0) / n * 100.0 if n else 0.0
    am_combined = (ad.get("A", 0) + da.get("B", 0)) / (2 * n) * 100.0 if n else 0.0

    print(f"Canary Astra Militarum vs Death Guard  (N={n} per slot order, "
          f"seeds {args.seed_start}..{args.seed_start + n - 1}, vanilla, archetype)")
    print("-" * 68)
    print(f"  ({CANARY_A} slot A vs {CANARY_B}):  Astra Militarum wins "
          f"{ad.get('A', 0):3d}/{n}  = {am_as_a:5.1f}%")
    print(f"  ({CANARY_B} slot A vs {CANARY_A}):  Astra Militarum wins "
          f"{da.get('B', 0):3d}/{n}  = {am_as_b:5.1f}%")
    print(f"  Astra Militarum combined win rate:            {am_combined:5.1f}%  "
          f"(anchor baseline 36.2%)")
    if args.log_games:
        print(f"  Per-game log written to {args.log_games} "
              f"(join with scripts/paired_delta.py).")


if __name__ == "__main__":
    main()
