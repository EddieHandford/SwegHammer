"""Rewrite the stale default claims that `scripts.gate_inventory` flags.

gate_inventory reports gates whose prose asserts a default the code contradicts.
Every current instance is the same shape: the comment says the gate is
default-OFF because that was true when it was WRITTEN, the gate was later
adopted default-on, and the prose was never swept.

That drift is not cosmetic. It has already produced three wrong conclusions in
one session: a retracted Aeldari Battle Focus finding (task #43), a hunt for a
Chaos Lord "fabrication" that had already been removed, and a wasted N=80 screen
of SWEG_CSM_ABILITIES that returned zero flips because the gate was already on.

This edits ONLY the specific comment lines gate_inventory flags, and only the
default-claim phrase on those lines. It does not touch code, does not reflow
prose, and prints every change for review. Dry-run by default.

Deliberately NOT automatic beyond that: the blind-spot cases (a block that
states BOTH a stale and a correct default, which is exactly
SWEG_AELDARI_FATE_FAITHFUL and SWEG_CSM_ABILITIES) are not detected by
gate_inventory and are not touched here. They need human review.

Run: PYTHONHASHSEED=0 python -m scripts._fix_gate_comments          # dry run
     PYTHONHASHSEED=0 python -m scripts._fix_gate_comments --apply
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Ordered rules. The TEMPORAL forms must match first: "default-off while
# screening" corrected to merely "default-ON while screening" would still assert
# the gate is under trial, which is a NEW falsehood rather than a fix. Those
# clauses are removed outright.
#
# Everything here says the same thing — the gate is on unless explicitly killed —
# so the reader never has to reconcile the prose with the read expression again.
PHRASES = [
    (r"default[- ]off while screening", "ADOPTED default-on"),
    (r"default[- ]off during screen", "ADOPTED default-on"),
    (r"default[- ]off while [a-z ]+", "ADOPTED default-on"),
    (r"default[- ]?(?:off|OFF)\b", "ADOPTED default-on"),
    (r"defaults off\b", "defaults ON"),
]

# Comments whose sentence describes the ENABLING CONDITION rather than just the
# default cannot be repaired by swapping a word — rewriting the default inside
# "True when X == '1' (default-OFF)" yields a self-contradiction. Left for hand
# editing and reported explicitly.
MANUAL_ONLY = {
    # Docstring states the enabling condition: "True when X == '1' (default-OFF)".
    "SWEG_WARGEAR_MUTEX",
    # The stale clause runs onto the NEXT line ("...default-off while / screening"),
    # so a single-line rewrite leaves a dangling "while".
    "SWEG_TAC_DECK_CONSUMER_FIX",
}

FLAG = re.compile(
    r"^\s{4}(SWEG_[A-Z0-9_]+)\s*$"
)
COMMENT_AT = re.compile(
    r"^\s{6}comment\s+(\S+):(\d+)\s+says\s+default-(ON|OFF)\s*$"
)


def collect() -> list:
    """Re-run gate_inventory and parse its contradiction block."""
    out = subprocess.run(
        [sys.executable, "-m", "scripts.gate_inventory"],
        cwd=str(ROOT), capture_output=True, text=True,
    ).stdout.splitlines()
    hits, gate = [], None
    for line in out:
        m = FLAG.match(line)
        if m:
            gate = m.group(1)
            continue
        m = COMMENT_AT.match(line)
        if m and gate:
            hits.append((gate, m.group(1), int(m.group(2))))
    return hits


def main() -> None:
    apply = "--apply" in sys.argv
    hits = collect()
    if not hits:
        print("no contradictions reported by gate_inventory")
        return

    print(f"=== {len(hits)} flagged comment line(s) ===\n")
    edits = {}
    unchanged = []
    for gate, relpath, lineno in hits:
        path = ROOT / relpath
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        idx = lineno - 1
        if idx < 0 or idx >= len(lines):
            unchanged.append((gate, relpath, lineno, "line out of range"))
            continue
        original = lines[idx]
        if gate in MANUAL_ONLY:
            unchanged.append((gate, relpath, lineno,
                              "sentence states the enabling CONDITION, not just "
                              "the default — a word swap would contradict itself"))
            continue
        new = original
        for stale, truthful in PHRASES:
            new2 = re.sub(stale, truthful, new)
            if new2 != new:
                new = new2
                break
        if new == original:
            unchanged.append((gate, relpath, lineno, "no default phrase on line"))
            continue
        print(f"{gate}\n  {relpath}:{lineno}")
        print(f"  -  {original.rstrip()}")
        print(f"  +  {new.rstrip()}\n")
        edits.setdefault(path, {})[idx] = new

    if unchanged:
        print("=== NOT rewritten (need human review) ===")
        for gate, relpath, lineno, why in unchanged:
            print(f"  {gate:<42} {relpath}:{lineno}  — {why}")
        print()

    if not apply:
        print("DRY RUN. Re-run with --apply to write.")
        return

    for path, changes in edits.items():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        for idx, new in changes.items():
            lines[idx] = new
        path.write_text("".join(lines), encoding="utf-8", newline="")
    n = sum(len(c) for c in edits.values())
    print(f"APPLIED {n} line rewrite(s) across {len(edits)} file(s).")
    print("Re-run scripts.gate_inventory to confirm, then verify the")
    print("determinism digests are UNCHANGED — this must not alter behaviour.")


if __name__ == "__main__":
    main()
