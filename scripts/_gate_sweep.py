"""Which simulator gates are default-OFF, and which of those implement a RULE?

Generalises the method that found the measurement-defect class. That class was
found by asking "what rule does this codebase state but not apply everywhere?".
The sibling question is "what rule does this codebase IMPLEMENT but leave switched
off?" — because the project's fidelity-first doctrine says a faithful mechanic
should not be gated off for metric reasons.

Cross-references every `SWEG_*` gate default against `data/rule_citations*` and
splits the default-off set by whether its citation reads as a RULES claim or as
an explicitly-labelled artificial-intelligence piloting heuristic (the citations
self-identify: heuristic entries say so in their `effect` text). A default-off
gate whose citation is a rules claim is a candidate faithful-mechanic-gated-off.

Read-only. Run: python -m scripts._gate_sweep
"""
from __future__ import annotations
import collections
import glob
import json
import os
import re

# Classify by the DEFAULT STRING only, never by the comparison direction.
#
# An earlier version of this sweep inferred the boolean from the comparison and
# got it backwards for guard-clause sites: `if environ.get("SWEG_OVERWATCH",
# "1") == "0": return` reads as default "1" compared against "0", which the
# naive rule scores as default-OFF — when in fact Fire Overwatch is default-ON
# and the line is an early-return kill-switch. That false positive would have
# reported a core 10e stratagem as switched off. The default STRING is
# unambiguous on its own: "0" means off-unless-set, "1" means on-unless-set,
# whatever the surrounding comparison does with it.
GATE_RE = re.compile(
    r"""environ\.get\(\s*["'](SWEG_[A-Z0-9_]+)["']\s*,\s*["']([01])["']\s*\)"""
)

HEURISTIC_MARKERS = (
    "piloting heuristic",
    "artificial-intelligence piloting",
    "not a 10e rules claim",
    "not a rules claim",
    "ai heuristic",
    "instrument",
    "read-only",
)


def gate_defaults():
    gates = collections.defaultdict(set)
    where = collections.defaultdict(set)
    for p in glob.glob("code/**/*.py", recursive=True):
        try:
            src = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for m in GATE_RE.finditer(src):
            g, dflt = m.group(1), m.group(2)
            gates[g].add(dflt == "1")
            where[g].add(os.path.basename(p))
    return gates, where


def citations():
    out = {}
    for p in glob.glob("data/rule_citations.d/*.json") + glob.glob("data/rule_citations.json"):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for k, v in d.items():
            if isinstance(v, dict):
                out[k] = v
    return out


def main() -> None:
    gates, where = gate_defaults()
    cits = citations()
    blob = {k: (v.get("effect", "") + " " + v.get("trigger", "")).lower()
            for k, v in cits.items()}

    off = sorted(g for g, v in gates.items() if v == {False})
    on = sorted(g for g, v in gates.items() if v == {True})
    mixed = sorted(g for g, v in gates.items() if len(v) > 1)

    print(f"gates found: {len(gates)}   default-ON: {len(on)}   "
          f"default-OFF: {len(off)}   INCONSISTENT: {len(mixed)}")

    if mixed:
        print("\n!! INCONSISTENT DEFAULTS — same gate, different default per site")
        print("   (a real defect class of its own: behaviour depends on which site runs)")
        for g in mixed:
            print(f"   {g}   in {', '.join(sorted(where[g]))}")

    rules, heur, uncited = [], [], []
    for g in off:
        hits = [k for k, t in blob.items() if g.lower() in t]
        if not hits:
            uncited.append(g)
            continue
        if any(any(mk in blob[k] for mk in HEURISTIC_MARKERS) for k in hits):
            heur.append((g, hits[0]))
        else:
            rules.append((g, hits[0]))

    print(f"\n=== DEFAULT-OFF gates whose citation reads as a RULES claim ({len(rules)}) ===")
    print("    candidates for 'faithful mechanic gated off' — check each against doctrine")
    for g, k in rules:
        print(f"   {g:38s} cited {k}")

    print(f"\n=== DEFAULT-OFF, self-declared heuristic or instrument ({len(heur)}) ===")
    for g, k in heur:
        print(f"   {g:38s} cited {k}")

    print(f"\n=== DEFAULT-OFF, no citation mentions the gate ({len(uncited)}) ===")
    print("    mostly screening/diagnostic switches; scan for anything rule-bearing")
    for g in uncited:
        print(f"   {g}")


if __name__ == "__main__":
    main()
