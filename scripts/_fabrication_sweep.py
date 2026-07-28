"""Fifth defect class: effects the simulator grants that the rule text never mentions.

The four sweeps so far asked what the codebase states-but-misapplies, what it
implements-but-disables, what it approximates, and what it confesses. The
remaining question is the most dangerous one: **what does it GRANT that no rule
authorises?** A fabricated buff is a pure over-credit with no fidelity defence at
all, and the decision ledger records that exactly this class has bitten before —
"the accidental `_screen_target_bonus` mislabelling of Khorne Berzerkers",
Awakened Dynasty run wrong for weeks, and several `LeaderAbility` proxies since
removed as "fabrications".

Heuristic: for each citation, look for 10e mechanic keywords named in the EFFECT
that do not appear anywhere in the QUOTED RULE TEXT. That is not proof — an
effect legitimately paraphrases, and a datasheet quote may be truncated — but it
is a strong shortlist, and every hit is cheap to adjudicate by eye against the
quote printed beside it.

Read-only. Run: python -m scripts._fabrication_sweep
"""
from __future__ import annotations
import glob
import json
import re

# Mechanics that are always named explicitly in real 10e rule text when granted.
MECHANICS = [
    "lethal hits", "sustained hits", "devastating wounds", "feel no pain",
    "invulnerable save", "benefit of cover", "ignores cover", "precision",
    "blast", "torrent", "melta", "rapid fire", "assault", "heavy",
    "twin-linked", "extra attacks", "hazardous", "anti-", "fights first",
    "deep strike", "infiltrators", "scouts", "stealth", "lone operative",
    "re-roll", "reroll",
]

# Citation keys whose effect text legitimately describes simulator plumbing
# rather than a granted rule; skip to cut noise.
SKIP_SUBSTR = ("instrument", "diag", "harness", "_frame", "eval")


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
    rows = []
    for key, (v, src) in cits.items():
        if any(s in key.lower() for s in SKIP_SUBSTR):
            continue
        quote = (v.get("quoted_text", "") or "").lower()
        eff = (v.get("effect", "") or "")
        low = eff.lower()
        if not quote or not eff:
            continue
        missing = []
        for m in MECHANICS:
            if m in low and m not in quote:
                # "removed", "fabrication", "prior" => the effect is describing a
                # PAST wrong implementation, not a current grant.
                idx = low.find(m)
                window = low[max(0, idx - 120): idx + 120]
                if any(w in window for w in ("removed", "fabricat", "prior ",
                                             "previously", "no longer", "not modelled",
                                             "does not", "never")):
                    continue
                missing.append(m)
        if missing:
            rows.append((len(missing), key, src, sorted(set(missing)), quote, eff))

    rows.sort(key=lambda r: -r[0])
    print(f"citations scanned: {len(cits)}")
    print(f"SHORTLIST — effect names a mechanic the quote does not: {len(rows)}\n")
    print("each needs eye adjudication: paraphrase and truncated quotes are legitimate\n")
    for _n, key, src, missing, quote, eff in rows[:25]:
        print(f"== {key}   ({src})")
        print(f"   effect grants : {', '.join(missing)}")
        print(f"   quote (start) : {quote[:150]}")
        print(f"   effect (start): {eff[:170]}")
        print()


if __name__ == "__main__":
    main()
