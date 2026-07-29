"""Which SWEG_* gates actually DO anything on the evaluation frame?

`scripts.gate_inventory` reads the code and reports each gate's true default.
That is necessary but not sufficient: a gate can be correctly wired, correctly
documented, and still change NOTHING, because the thing it modifies never
appears on the table.

That is not hypothetical. Confirmed in one session:
  * SWEG_CSM_ABILITIES     — a scoped N=80 screen returned ZERO flips in 36,960
    games. It was already default-on; the screen measured nothing.
  * SWEG_CSM_SORCERER_PRESCIENCE — faithful rebuild, byte-inert: the Chaos Space
    Marines archetype never fields a Sorcerer (#59).
  * SWEG_DG_TYPHUS_MELEE_ONLY — ADOPTED default-on in wave 260 on fidelity
    grounds, and its kill-switch changes nothing: Typhus is never fielded (#31).

An inert gate is not a bug. But a screen run against a frame that cannot express
the gate reads "no change", which is indistinguishable from "no effect" — so
every verdict recorded for an inert gate measured nothing, and any future
re-sourcing of a list can silently make it live and unmeasured.

METHOD, deliberately behavioural rather than textual. Two previous attempts at
this problem parsed prose and produced noise. This flips each gate to the
OPPOSITE of its true default, recomputes the wide determinism digest, and
compares against production. Digest differs -> the gate is LIVE. Digest matches
-> NO OBSERVABLE EFFECT on this frame.

READ THE NEGATIVE RESULT CORRECTLY — THIS IS A LOW-SENSITIVITY SCREEN. The frame
is 44 battles. "No change in 44 battles" is NOT the same as "does nothing", and
this codebase contains a proven counter-example: SWEG_CULL_PICK_AWARE shows no
change here, yet a paired N=80 screen over 36,960 games recorded it as the best
ordering gain of that session with its mechanism resolved at r=-0.83. A gate
that fires rarely — one that needs a particular faction, card, or board state —
will hide at this sample size.

So a gate landing in the NO-EFFECT list means one of two very different things,
and they must be told apart before any verdict is written:
  (a) STRUCTURALLY DEAD — the thing it modifies never exists on this frame.
      Confirmed for SWEG_DG_TYPHUS_MELEE_ONLY (Typhus is never fielded) and
      SWEG_CSM_SORCERER_PRESCIENCE (no Sorcerer is fielded). For these, every
      recorded verdict genuinely measured nothing.
  (b) RARE-FIRING — real but below this frame's resolution. Needs a full N=80
      screen, not a conclusion.
Distinguish by checking whether the gate's subject is fielded at all
(scripts/_declared_vs_fielded.py), NOT by assuming.

Cost is one wide digest (22 factions, 44 battles) per gate, run in parallel.

Run: PYTHONHASHSEED=0 python -m scripts._gate_inertness_sweep
     GIS_WORKERS=12   parallel subprocesses (leave headroom on a 16-core box)
     GIS_ONLY=SWEG_A,SWEG_B   restrict to named gates
"""
from __future__ import annotations
import concurrent.futures as cf
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKERS = int(os.environ.get("GIS_WORKERS", "12"))
ONLY = [g for g in os.environ.get("GIS_ONLY", "").split(",") if g]
# Which digest harness to probe with. Default is the 44-battle wide check;
# point at scripts._detcheck_deep (with DETCHECK_SEEDS) to re-test the gates
# that showed nothing, at a sample where a rare-firing one can surface.
HARNESS = os.environ.get("GIS_HARNESS", "scripts._detcheck_wide")

DIGEST = re.compile(r":\s*([0-9a-f]{16,})\s*$")


def _digest(env_extra: dict) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    for k in list(env):
        if k.startswith("SWEG_"):
            del env[k]
    env.update(env_extra)
    out = subprocess.run(
        [sys.executable, "-m", HARNESS],
        cwd=str(ROOT), capture_output=True, text=True, env=env,
    ).stdout
    for line in out.splitlines():
        m = DIGEST.search(line.strip())
        if m:
            return m.group(1)
    return "ERROR"


def main() -> None:
    # Reuse gate_inventory's parser primitives rather than re-deriving the
    # defaults here — two sources of truth for "what is this gate's default"
    # is exactly the drift this whole thread exists to kill.
    from scripts.gate_inventory import READ, _default_of, CODE

    gates: dict = {}
    for path in sorted(CODE.rglob("*.py")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            m = READ.search(line)
            if not m:
                continue
            name, dflt, op, rhs = m.groups()
            state = _default_of(dflt or "", op, rhs)
            gates.setdefault(name, []).append(
                (path.relative_to(ROOT).as_posix(), i + 1, state))
    if ONLY:
        gates = {g: v for g, v in gates.items() if g in ONLY}

    baseline = _digest({})
    print(f"production baseline via {HARNESS}: {baseline}")
    if HARNESS != "scripts._detcheck_wide":
        print("  (NOT the canonical wide digest — different sample, different")
        print("   value. Comparable only to other runs of the same harness.)")
    print()
    if baseline == "ERROR":
        print("could not compute the baseline digest — aborting")
        return

    # Flip each gate to the opposite of its real default.
    jobs = {}
    for name, reads in sorted(gates.items()):
        default_on = reads[0][2] == "ON"
        jobs[name] = "0" if default_on else "1"

    live, inert, errors = [], [], []
    print(f"probing {len(jobs)} gates with {WORKERS} workers "
          f"(one wide digest each)...\n")
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(_digest, {n: v}): (n, v) for n, v in jobs.items()}
        for fut in cf.as_completed(futs):
            name, val = futs[fut]
            try:
                d = fut.result()
            except Exception as exc:
                errors.append((name, str(exc)))
                continue
            if d == "ERROR":
                errors.append((name, "no digest emitted"))
            elif d == baseline:
                inert.append((name, val))
            else:
                live.append((name, val, d))

    print(f"=== NO OBSERVABLE EFFECT on the 44-battle frame: "
          f"{len(inert)} of {len(jobs)} ===")
    print("    NOT a proof of inertness — this frame is 44 battles and a")
    print("    rare-firing gate hides at that sample size. SWEG_CULL_PICK_AWARE")
    print("    appears below yet scored the best ordering gain of its session")
    print("    over 36,960 paired games. Before writing any verdict, separate")
    print("    STRUCTURALLY DEAD (subject never fielded — check with")
    print("    scripts/_declared_vs_fielded.py) from RARE-FIRING (needs N=80).\n")
    for name, val in sorted(inert):
        print(f"    {name:<46} forced ={val}")

    print(f"\n=== LIVE: {len(live)} ===\n")
    for name, val, d in sorted(live):
        print(f"    {name:<46} ={val} -> {d}")

    if errors:
        print(f"\n=== ERRORS: {len(errors)} ===")
        for name, why in sorted(errors):
            print(f"    {name:<46} {why}")


if __name__ == "__main__":
    main()
