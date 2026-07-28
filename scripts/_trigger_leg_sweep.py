"""Sixth sweep: CORE rules whose trigger enumerates several conditions, where the
simulator may wire only some of the legs.

This is the generalisation of the session's largest structural find. Fire
Overwatch's cited trigger reads verbatim:

    "just after an enemy unit is set up or starts or ends a Normal, Advance,
     Fall Back or Charge move"

— four move types, two timings. The simulator fired it on CHARGE and Reserves
arrival only. Wiring the movement leg moved Death Guard 2.1 points toward
reality, the first movement of that residual in the project's history, and it is
inherently ASYMMETRIC: a slow durable blob offers the trigger every turn, a fast
army almost never. That is exactly the anti-durable counterplay the 2026-07-15
frontier entry said the simulator lacked.

Where one enumerated trigger was half-wired there may be others. Unlike the
failed prose-based fabrication sweep, this one is objectively checkable: the
enumeration lives in the QUOTED RULE TEXT, so each leg can be read off the quote
and then looked for in the code by eye.

Ranks by how many legs the quote enumerates and whether the effect text mentions
fewer of them than the quote does.

Read-only. Run: python -m scripts._trigger_leg_sweep
"""
from __future__ import annotations
import glob
import json
import re

# Trigger vocabulary that appears in enumerated 10e trigger clauses.
LEGS = [
    "normal move", "advance", "fall back", "charge move", "charge",
    "set up", "starts", "ends", "movement phase", "charge phase",
    "shooting phase", "fight phase", "command phase", "reserves",
    "deep strike", "disembark", "destroyed", "declares",
]

# A quote is "enumerated" if it joins trigger conditions with or/comma lists.
ENUM_HINT = re.compile(r"\bor\b", re.I)


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


def trigger_clause(quote: str) -> str:
    """The WHEN/trigger sentence, where the enumeration usually lives."""
    low = quote.lower()
    for key in ("when:", "each time", "just after", "at the start", "at the end",
                "in your", "in the"):
        i = low.find(key)
        if i >= 0:
            return quote[i:i + 320]
    return quote[:320]


def main() -> None:
    cits = load()
    rows = []
    for key, (v, src) in cits.items():
        quote = v.get("quoted_text", "") or ""
        eff = (v.get("effect", "") or "") + " " + (v.get("trigger", "") or "")
        if not quote or not eff:
            continue
        clause = trigger_clause(quote)
        low_c = clause.lower()
        if not ENUM_HINT.search(low_c):
            continue
        in_quote = {leg for leg in LEGS if leg in low_c}
        if len(in_quote) < 2:
            continue
        low_e = eff.lower()
        missing = sorted(leg for leg in in_quote if leg not in low_e)
        if not missing:
            continue
        rows.append((len(missing), len(in_quote), key, src, missing, clause))

    rows.sort(key=lambda r: (-r[0], -r[1]))
    print(f"citations scanned: {len(cits)}")
    print(f"ENUMERATED TRIGGERS with legs absent from the effect text: {len(rows)}\n")
    print("Each needs an eye check against the code — the effect may paraphrase.")
    print("Prioritise CORE rules (every army has them) and triggers whose legs")
    print("fire at different rates for different army archetypes.\n")
    for nmiss, ntot, key, src, missing, clause in rows[:20]:
        print(f"== {key}   ({src})")
        print(f"   quote enumerates {ntot} legs; effect omits {nmiss}: {', '.join(missing)}")
        print(f"   trigger: {clause[:220].strip()}")
        print()


if __name__ == "__main__":
    main()
