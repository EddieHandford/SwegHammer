"""The Astra Militarum mechanics that are BUILT, CITED, and switched OFF.

`scripts/_gate_sweep.py` found 18 default-off gates whose citations read as rules
claims rather than piloting heuristics — and SEVEN of them are Astra Militarum,
far more than any other faction. That is a completely different angle on the
under-pole from anything tried: not "the artificial intelligence plays it badly"
but "the army is missing rules it owns".

This prints each one's citation so a human can separate the genuine
missing-mechanic cases from list CHOICES (a detachment swap is not a missing
mechanic) and from piloting heuristics that the keyword scan mis-filed.

Read-only. Run: python -m scripts._am_offgates
"""
from __future__ import annotations
import glob
import json

WANT = [
    ("SWEG_AM_CADIA_STANDS", "simulator.cadia_stands"),
    ("SWEG_AM_DUTY_AND_HONOUR", "Order.Duty and Honour!"),
    ("SWEG_AM_RECON", "simulator.masters_of_camouflage"),
    ("SWEG_CREED_TWO_ORDERS", "SWEG_CREED_TWO_ORDERS.lord_castellan_two_orders"),
    ("SWEG_REINFORCEMENTS", "Stratagem.Reinforcements!"),
    ("SWEG_AM_GRIZZLED", "GRIZZLED_COMPANY.grizzled_ruthless_discipline"),
    ("SWEG_AM_CHASE_VP", "simulator.vp_chase_targeting"),
]


def load():
    out = {}
    for f in glob.glob("data/rule_citations.d/*.json") + glob.glob("data/rule_citations.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for k, v in d.items():
            if isinstance(v, dict):
                out[k] = v
    return out


def main() -> None:
    cit = load()
    for gate, key in WANT:
        v = cit.get(key)
        print("=" * 78)
        print(f"{gate}   (cited {key})")
        if not v:
            print("   NO CITATION FOUND")
            continue
        print(f"   rule : {v.get('rule_name', '')[:100]}")
        print(f"   text : {v.get('quoted_text', '')[:260]}")
        print(f"   scope: {v.get('scope', '')}")
        eff = v.get("effect", "")
        low = eff.lower()
        kind = ("PILOTING HEURISTIC" if "heuristic" in low or "not a rules claim" in low
                else "RULES MECHANIC")
        print(f"   -> {kind}")


if __name__ == "__main__":
    main()
