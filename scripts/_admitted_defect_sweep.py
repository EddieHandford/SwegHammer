"""Fourth sweep: citations that ADMIT a known defect left in place.

The approximation sweep turned up something sharper than a generic
approximation. `simulator.strands_of_fate` says of its own default path:

    "this is a KNOWN OVER-COUNT versus the codex (up to ~36-40 spends/round for
     a 9-10-squad army) ... being left in place as the default pending screening"

The real rule gives Aeldari SIX Fate dice for the whole battle. That is a
documented, self-confessed, roughly thirty-fold over-count sitting on the number
two over-pole (+13.7), with a faithful gate already built and switched off.

Where there is one such confession there are usually others. This greps every
citation for language that admits a live defect rather than a mere
simplification: over-count, too generous, known defect, pending screening, left
in place, wrong, should be.

Read-only. Run: python -m scripts._admitted_defect_sweep
"""
from __future__ import annotations
import glob
import json
import re

CONFESSIONS = (
    "over-count", "overcount", "over-counts", "over count",
    "too generous", "too many", "known defect", "known bug",
    "pending screening", "left in place", "predates this fix",
    "is wrong", "incorrect", "unfaithful", "over-credit", "over-reward",
    "double-count", "double counts", "not capped", "uncapped",
)


GATE_RE = re.compile(r"""environ\.get\(\s*["'](SWEG_[A-Z0-9_]+)["']\s*,\s*["']([01])["']\s*\)""")


def gate_defaults():
    """Current default of every gate, read from the CODE not the citation.

    CRITICAL. Citations keep their pre-fix narrative after a gate is adopted —
    the "ADOPTED default-on" note lives in a code comment, not in the citation
    text. Without this cross-check the sweep reports HISTORICAL confessions as
    live defects. It did exactly that on first run: `simulator.strands_of_fate`
    and `simulator.battle_focus` still read as self-confessed Aeldari over-counts,
    but SWEG_AELDARI_FATE_FAITHFUL and SWEG_AELDARI_BF_DISCARD were both adopted
    default-on back on 2026-07-08. Same for World Eaters' Blood Tithe. A
    confession is only actionable if its fix gate is still OFF.
    """
    import glob as _glob
    out = {}
    for p in _glob.glob("code/**/*.py", recursive=True):
        try:
            src = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for m in GATE_RE.finditer(src):
            out.setdefault(m.group(1), set()).add(m.group(2) == "1")
    return out


def load():
    out = {}
    for f in glob.glob("data/rule_citations.d/*.json") + glob.glob("data/rule_citations.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for k, v in d.items():
            if isinstance(v, dict):
                out[k] = (v, f.replace("\\", "/").split("/")[-1])
    return out


def main() -> None:
    cits = load()
    defaults = gate_defaults()
    live, fixed = [], []
    for key, (v, src) in cits.items():
        text = (v.get("effect", "") or "") + " " + (v.get("trigger", "") or "")
        low = text.lower()
        found = sorted({c for c in CONFESSIONS if c in low})
        if not found:
            continue
        sent = ""
        for s in re.split(r"(?<=[.;])\s+", text):
            if any(c in s.lower() for c in found):
                sent = s.strip()
                break
        # Which fix gates does this citation name, and are any still OFF?
        named = sorted(set(GATE_RE.findall(text.replace("environ.get", "environ.get"))) |
                       {g for g in defaults if g in text})
        off = [g for g in named if defaults.get(g) == {False}]
        on = [g for g in named if defaults.get(g) == {True}]
        row = (key, src, found, sent, off, on)
        (live if (off or not named) else fixed).append(row)

    print(f"citations scanned: {len(cits)}")
    print(f"ACTIONABLE (fix gate still OFF, or no gate named): {len(live)}")
    print(f"ALREADY FIXED (every named gate is default-ON): {len(fixed)}\n")

    for key, src, found, sent, off, on in sorted(live):
        print(f"== {key}   ({src})")
        print(f"   admits: {', '.join(found)}")
        if off:
            print(f"   FIX GATE STILL OFF: {', '.join(off)}")
        elif not off and not on:
            print("   no fix gate named — needs a build, not a flip")
        if sent:
            print(f"   text  : {sent[:280]}")
        print()

    if fixed:
        print("-" * 70)
        print("ALREADY FIXED — citation text is historical, gate is on:")
        for key, _src, _f, _s, _off, on in sorted(fixed):
            print(f"   {key}   ({', '.join(on)})")


if __name__ == "__main__":
    main()
