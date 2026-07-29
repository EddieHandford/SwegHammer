"""Authoritative inventory of every SWEG_* gate, read from the CODE.

Written 2026-07-28 after documentation drift caused a wrong finding to be
reported. `SWEG_AELDARI_BF_DISCARD` is default-ON, but the comment directly
above its read called it "the default-off gate"; a probe trusted the comment,
labelled its two arms backwards, and reported a Battle Focus carry-over defect
that production does not have. `SWEG_AELDARI_FATE_FAITHFUL` had the same
contradiction INSIDE ONE FUNCTION - a docstring saying "(default off)" six lines
above a line whose own inline comment said "ADOPTED default-on".

The mechanism is consistent: adopting a gate flips the read from
`get(X, "0") == "1"` to `get(X, "1") != "0"` and adds an inline note, but the
surrounding prose and the state documents are not swept.

This reads the code and reports the truth, so no future session has to trust
prose. It is deliberately NOT a linter over comments - comments are free text
and a heuristic over them would produce noise. It reports what the code does and
flags the specific contradiction that is machine-checkable: a nearby comment
asserting a default that the read disagrees with.

KNOWN BLIND SPOT, stated because it is the very case that motivated the script.
Claims are judged per block: if ANY line in the window names the gate and states
the correct default, the block is treated as resolved. That kills a lot of false
positives, because these comments narrate history and "built default-off ...
later ADOPTED default-on" is a correct account rather than a lie. But it also
means a block containing BOTH a stale claim and a correct one is not flagged -
and that is exactly the shape of SWEG_AELDARI_FATE_FAITHFUL, whose docstring said
"(default off)" twenty-seven lines above a read whose own inline comment said
"ADOPTED default-on". This tool would NOT have caught it.

So it catches the clear cases and misses mixed ones. Tightening it to flag any
stale sentence would restore that catch at the cost of roughly a dozen false
positives, which is the trade that turns a checker into noise nobody runs. The
mixed case is left to human review; run with GI_WINDOW to widen or narrow.

Exit code 1 if any contradiction is found, so it can gate a commit.

Run: PYTHONHASHSEED=0 python -m scripts.gate_inventory
     GI_VERBOSE=1   list every gate, not just the flagged ones
"""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
VERBOSE = os.environ.get("GI_VERBOSE") == "1"

# The three shapes a gate read takes in this codebase.
#   get("X", "1") != "0"   default ON, "0" is the kill-switch
#   get("X", "0") == "1"   default OFF, "1" enables
#   get("X") == "1"        default OFF (no default supplied)
# Also seen: get("X", "1") == "0" — an INVERTED read that tests for the
# kill-switch directly. That is still default-ON behaviour for the feature.
READ = re.compile(
    r'os\.environ\.get\(\s*"(SWEG_[A-Z0-9_]+)"\s*(?:,\s*"([01])"\s*)?\)'
    r'\s*(==|!=)\s*"([01])"'
)

# A comment or docstring line asserting a default, near a read.
CLAIM = re.compile(r'default[- ]?(on|off)\b', re.I)
# Lines above a read to search for a claim about its default. Set from the
# real distance seen in this codebase, not guessed: the stale
# SWEG_AELDARI_FATE_FAITHFUL docstring sat 27 lines above the read it described,
# so a 12-line window would have missed the very drift that motivated this
# script. The `name in line` requirement below is what keeps a window this wide
# from producing noise — a line 30 above that names the gate explicitly is
# almost certainly about it.
WINDOW = int(os.environ.get("GI_WINDOW", "40"))

# Gates DELIBERATELY read with two different defaults, where the second read is
# a legacy path preserved so a kill-switch reverts byte-identically. These are
# correct code, not drift, and each is documented at the read site.
#
#   SWEG_TAC_DECK — code/secondaries.py:1111-1113. When
#   SWEG_TAC_DECK_CONSUMER_FIX is on (the default) this module reads the gate
#   default-ON so it MATCHES the simulator's read; when the fix is switched off
#   the older mismatched `== "1"` read is kept so the revert is byte-identical.
#   Flagging that pair would train the reader to ignore this section.
INTENTIONAL_DUAL_READ = {"SWEG_TAC_DECK"}


def _default_of(has_default: str, op: str, rhs: str) -> str:
    """Resolve whether the FEATURE is on when the environment variable is unset.

    The distinction that matters, and which a first version of this script got
    wrong: report the state of the FEATURE, not the truth value of the
    expression. Both shapes below leave the feature ON by default —

        get(X, "1") != "0"    "is the feature enabled?"      True  by default
        get(X, "1") == "0"    "is the kill-switch thrown?"   False by default

    — and a classifier that reported the expression's truth would call the
    second one OFF, then flag every correct comment beside it as a
    contradiction. That is a plausible-looking wrong answer, which is the exact
    failure this tool exists to prevent, so it is worth stating.

    The supplied default literal is the whole answer: "1" means the gate is
    adopted and `=0` is its kill-switch; "0" or no default means it is opt-in.
    `op` and `rhs` describe how the call site phrases the question and do not
    affect the feature's default state.
    """
    return "ON" if has_default == "1" else "OFF"


def main() -> int:
    gates: dict = {}
    contradictions: list = []

    for path in sorted(CODE.rglob("*.py")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            for m in READ.finditer(line):
                name, dflt, op, rhs = m.groups()
                state = _default_of(dflt or "", op, rhs)
                rel = path.relative_to(ROOT).as_posix()
                gates.setdefault(name, []).append((rel, i + 1, state))

                # Collect EVERY prose claim about this gate in the window, then
                # judge them together. Flagging the first mismatching sentence
                # produces false positives all over this codebase, because these
                # comments narrate history: "built default-off ... ADOPTED
                # default-on" is a correct and useful account, not a lie. Only
                # when NO claim in the window matches the code is the reader
                # actually left with the wrong impression.
                claims = []
                for j in range(max(0, i - WINDOW), i + 1):
                    ctx = lines[j]
                    # Require the gate to be NAMED on the claiming line. Without
                    # this a wide window picks up any nearby "default off" prose
                    # about a different gate, which is how a checker like this
                    # turns into noise nobody reads.
                    #
                    # The name must match WHOLE. A plain substring test makes
                    # every gate a false match for its own longer siblings —
                    # SWEG_TAC_DECK matched prose about
                    # SWEG_TAC_DECK_CONSUMER_FIX and reported a contradiction
                    # that did not exist. Same defect that made
                    # scripts/_gate_verdict_triage.py unreliable.
                    if not re.search(name + r"(?![A-Z0-9_])", ctx):
                        continue
                    c = CLAIM.search(ctx)
                    if c:
                        claims.append((j + 1, c.group(1).upper(),
                                       ctx.strip()[:88]))
                # A gate with an INTENTIONAL dual read has a block that must
                # describe BOTH states ("with the fix ON ... with it OFF the
                # legacy read is preserved"), so a single-state check will
                # always fire on one of them. Suppressed for the same reason
                # the dual read itself is: it is correct code, and a checker
                # that cries wolf here is one nobody runs.
                if name in INTENTIONAL_DUAL_READ:
                    claims = []
                if claims and not any(cl == state for _, cl, _ in claims):
                    ln, claimed, text = claims[0]
                    contradictions.append(
                        (name, rel, ln, claimed, i + 1, state, text))

    # A gate read in several places with DIFFERENT defaults is its own hazard.
    inconsistent = {n: v for n, v in gates.items()
                    if len({s for _, _, s in v}) > 1
                    and n not in INTENTIONAL_DUAL_READ}

    on = sorted(n for n, v in gates.items() if v[0][2] == "ON")
    off = sorted(n for n, v in gates.items() if v[0][2] == "OFF")

    print(f"=== SWEG gate inventory, read from code/ ===")
    print(f"  {len(gates)} distinct gates — {len(on)} default-ON, "
          f"{len(off)} default-OFF\n")

    if VERBOSE:
        for label, names in (("DEFAULT-ON", on), ("DEFAULT-OFF", off)):
            print(f"  --- {label} ---")
            for n in names:
                where = gates[n][0]
                print(f"    {n:<40} {where[0]}:{where[1]}")
            print()

    if inconsistent:
        print("  !! GATES READ WITH DIFFERENT DEFAULTS IN DIFFERENT PLACES !!")
        for n, v in sorted(inconsistent.items()):
            print(f"    {n}")
            for rel, ln, st in v:
                print(f"      {st:<3} {rel}:{ln}")
        print()

    if contradictions:
        print("  !! PROSE CONTRADICTS THE CODE !!")
        for name, rel, cln, claimed, rln, state, text in contradictions:
            print(f"    {name}")
            print(f"      comment {rel}:{cln} says default-{claimed}")
            print(f"      code    {rel}:{rln} is  default-{state}")
            print(f"      > {text}")
        print()
    else:
        print("  No comment contradicts its own gate read.\n")

    bad = len(contradictions) + len(inconsistent)
    if bad:
        print(f"  {bad} problem(s). A gate whose prose lies about its default")
        print("  will mislead the next reader, and has already caused one wrong")
        print("  finding to be reported (see task #43).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
