"""Why is each default-off gate off? Triage them by recorded verdict.

Several gates in this repository were built, verified faithful, and held ONLY
because they did not improve the gated mean absolute error - a metric task #37
showed is beaten by a constant scoring 0.66 against the simulator's 2.85. That
is not a safe reason to leave faithful work switched off, because the metric
cannot distinguish fidelity from convergence toward the mean.

But it is not a reason to switch everything on either. SWEG_OBJ_HOME was the
pilot for exactly this question and the answer was HOLD: re-screened on the
ordering diagnostics it still failed, for a mechanism reason that remains live.
So the question per gate is what its verdict actually RESTS ON:

  REJECTED-EMPIRICAL  screened, moved the wrong way, mechanism identified.
                      Stays off. Re-opening needs a mechanism difference.
  BLOCKED             faithful, but depends on something not built yet.
                      Stays off until the dependency lands.
  HELD-FLAT           faithful, screened, metric did not move. THIS is the
                      class worth re-judging on ordering and spread.
  NEVER SCREENED      built and cited, no verdict recorded at all. Cheapest
                      possible win if any of these are faithful.
  NO RECORD           not mentioned in the documentation. Needs a read.

This reads the gate list from scripts/gate_inventory (rather than duplicating
its classifier, which would let the two drift apart) and searches the
documentation for each gate's recorded verdict.

THE VERDICT COLUMN IS A READING-ORDER HINT AND HAS BEEN WRONG THREE TIMES.
Stated bluntly because the temptation to quote it as a finding is exactly the
trap. In development it successively:

  1. matched gate names as SUBSTRINGS, so SWEG_SECONDARY_PURSUIT inherited the
     record of SWEG_AM_SECONDARY_PURSUIT and SWEG_SECONDARY collected 37 hits
     belonging to four longer names;
  2. accepted a verdict word ANYWHERE on a line mentioning the gate, so
     SWEG_EC_RANGED_HOLD and SWEG_REEMBARK were labelled ADOPTED when both read
     "BUILT + HELD default-off" - the ledger writes long lines listing several
     gates with different outcomes;
  3. still shifts gates between categories when the proximity window changes,
     which is the signature of a heuristic rather than a measurement.

What IS reliable here is the gate LIST and the default state, both read from
code, and the "NO RECORD" rows, which mean the documentation genuinely never
names the gate. Treat everything else as an ordering aid for human reading. A
gate discussed across several waves carries several verdicts and only the most
recent counts, which no keyword search can know.

Run: PYTHONHASHSEED=0 python -m scripts._gate_verdict_triage
     GT_VERBOSE=1  print the matching documentation lines
"""
from __future__ import annotations
import os
import re
from pathlib import Path

from scripts.gate_inventory import READ, _default_of

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
DOCS = ROOT / "docs"
VERBOSE = os.environ.get("GT_VERBOSE") == "1"
# Characters either side of a gate name within which a verdict word is treated
# as being ABOUT that gate. The decision ledger writes long lines listing
# several gates with different outcomes, so an unbounded line-level match
# attributes one gate's verdict to another.
PROXIMITY = int(os.environ.get("GT_PROXIMITY", "110"))

# Verdict signals, most decisive first — the first that matches wins, so
# REJECTED outranks HELD when a line says "held after rejection".
SIGNALS = [
    ("REJECTED", re.compile(
        r"REJECTED|rejected-empirical|wrong-sign|regress|backfired|reverted",
        re.I)),
    ("BLOCKED", re.compile(
        r"BLOCKED|blocked on|needs the |prerequisite|depends on|queue debt|"
        r"STILL-BLOCKED", re.I)),
    ("ADOPTED", re.compile(r"\bADOPTED\b", re.I)),
    ("HELD-FLAT", re.compile(
        r"\bHELD\b|held-fidelity|flat|neutral|inconclusive|no change|"
        r"within noise|near-flat|wash", re.I)),
    ("SCREENED", re.compile(r"screen|N=\d+|gated \d", re.I)),
]


def _off_gates():
    gates: dict = {}
    for path in sorted(CODE.rglob("*.py")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            for m in READ.finditer(line):
                name, dflt, op, rhs = m.groups()
                if _default_of(dflt or "", op, rhs) == "OFF":
                    gates.setdefault(name, path.relative_to(ROOT).as_posix())
    return gates


def main() -> None:
    gates = _off_gates()
    doc_text = {}
    for p in sorted(DOCS.rglob("*.md")):
        try:
            doc_text[p.name] = p.read_text(encoding="utf-8",
                                           errors="replace").splitlines()
        except OSError:
            continue

    rows = []
    for name, where in sorted(gates.items()):
        # Match the gate name as a WHOLE token. A plain substring test is wrong
        # here and produced visibly bad output in the first version:
        # SWEG_SECONDARY_PURSUIT matches inside SWEG_AM_SECONDARY_PURSUIT,
        # SWEG_SECONDARY inside four longer names, and SWEG_TAC_DECK inside
        # SWEG_TAC_DECK_CONSUMER_FIX - so a default-off gate inherited the
        # "ADOPTED" verdict belonging to its default-on sibling. Six gates were
        # mislabelled that way.
        token = re.compile(re.escape(name) + r"(?![A-Za-z0-9_])")
        hits = []
        for doc, lines in doc_text.items():
            for i, ln in enumerate(lines):
                if token.search(ln):
                    hits.append((doc, i + 1, ln.strip()))
        verdict = "NO RECORD"
        evidence = ""
        if hits:
            verdict = "SEE DOCS"
            # Require the verdict word to sit NEAR the gate name on the line.
            # Without this, a decision-ledger line listing several gates with
            # mixed verdicts hands its first keyword to whichever gate is
            # matched - which mislabelled SWEG_EC_RANGED_HOLD and SWEG_REEMBARK
            # as ADOPTED when both read "BUILT + HELD default-off". Proximity is
            # a crude proxy for association and still gets cases wrong; the
            # column is a HINT for reading order, never a verdict.
            for label, pat in SIGNALS:
                done = False
                for doc, ln, text in hits:
                    for tm in token.finditer(text):
                        lo = max(0, tm.start() - PROXIMITY)
                        hi = min(len(text), tm.end() + PROXIMITY)
                        if pat.search(text[lo:hi]):
                            verdict, evidence = label, f"{doc}:{ln}"
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
        rows.append((verdict, name, where, len(hits), evidence, hits))

    order = {"HELD-FLAT": 0, "SCREENED": 1, "MENTIONED": 2, "NO RECORD": 3,
             "BLOCKED": 4, "ADOPTED": 5, "REJECTED": 6}
    rows.sort(key=lambda r: (order.get(r[0], 9), r[1]))

    print(f"=== default-off gate triage — {len(gates)} gates ===")
    print("Ordered so the re-judgeable classes come first.\n")
    print(f"{'verdict':<12}{'gate':<42}{'doc hits':>9}  evidence")
    counts: dict = {}
    for verdict, name, where, n, ev, hits in rows:
        counts[verdict] = counts.get(verdict, 0) + 1
        print(f"{verdict:<12}{name:<42}{n:>9}  {ev}")
        if VERBOSE and hits:
            for doc, ln, text in hits[:2]:
                print(f"{'':<12}  > {doc}:{ln} {text[:96]}")

    print()
    for k in sorted(counts, key=lambda x: order.get(x, 9)):
        print(f"  {k:<12} {counts[k]}")
    print()
    print("  HELD-FLAT and NEVER-SCREENED are the classes where a gate may be")
    print("  faithful and switched off only because a metric that cannot")
    print("  distinguish fidelity from convergence disliked it. REJECTED and")
    print("  BLOCKED stay off - SWEG_OBJ_HOME was the pilot for re-judging and")
    print("  it stayed off for a live mechanism reason.")
    print()
    print("  Keyword matching over prose is crude and a gate may carry several")
    print("  verdicts across waves, with only the most recent counting. Read")
    print("  every row before acting on it.")


if __name__ == "__main__":
    main()
