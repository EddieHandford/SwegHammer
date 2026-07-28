"""Third defect class: rules the simulator implements as a KNOWN APPROXIMATION.

Two classes have already been swept and closed:
  1. "what rule does the codebase STATE but not apply everywhere?"
     -> the measurement-defect class (docs/MEASUREMENT_DEFECT_AUDIT.md)
  2. "what rule does the codebase IMPLEMENT but leave switched off?"
     -> scripts/_gate_sweep.py; eleven mechanics enabled, seven correctly excluded

The third question is "what rule does the codebase implement WRONGLY, and say so?"
The citations are unusually honest — many declare themselves approximations,
proxies, partial mappings or simplifications in their own `effect` text. Every
one of those is a fidelity gap with a paper trail, already localised to a cited
mechanic, and nobody has to guess whether it is real.

Ranks by how load-bearing the mechanic looks: an approximation in something that
fires every phase matters far more than one in a once-per-battle ability. That is
the frequency-of-consequence rule the measurement sweep established.

Read-only. Run: python -m scripts._approximation_sweep
"""
from __future__ import annotations
import glob
import json
import re

MARKERS = (
    "approximation", "approximate", "proxy", "simplif", "partial mapping",
    "not modelled", "not wired", "does not model", "stand-in", "crude",
    "rough", "placeholder", "best-effort",
)

# Words suggesting the mechanic fires constantly rather than rarely.
HOT = ("each time", "every time", "each phase", "every phase", "each round",
       "every round", "army-wide", "aura", "each model", "every model")
COLD = ("once per battle", "once per game", "one use", "first time")


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
    hits = []
    for key, (v, src) in cits.items():
        eff = v.get("effect", "") or ""
        low = eff.lower()
        found = [m for m in MARKERS if m in low]
        if not found:
            continue
        blob = (eff + " " + (v.get("quoted_text", "") or "")).lower()
        heat = sum(blob.count(h) for h in HOT) - 2 * sum(blob.count(c) for c in COLD)
        # pull the sentence that admits the approximation
        sent = ""
        for s in re.split(r"(?<=[.;])\s+", eff):
            if any(m in s.lower() for m in found):
                sent = s.strip()
                break
        hits.append((heat, key, src, found, sent))

    hits.sort(key=lambda r: -r[0])
    print(f"citations scanned: {len(cits)}")
    print(f"SELF-DECLARED APPROXIMATIONS: {len(hits)}\n")
    print("ranked by how often the mechanic plausibly fires (frequency of consequence)\n")
    for heat, key, src, found, sent in hits:
        print(f"[heat {heat:+d}] {key}   ({src})")
        print(f"          markers: {', '.join(sorted(set(found)))}")
        if sent:
            print(f"          admits : {sent[:240]}")
        print()


if __name__ == "__main__":
    main()
