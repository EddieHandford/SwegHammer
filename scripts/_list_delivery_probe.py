"""How much of a sourced list actually reaches the table, weighted by points?

The Aeldari sourced-list screen (task #38) came back FLAT at +1.06 with a
confidence interval of 3.96, and in the wrong direction. Two readings compete:

  (a) the list hypothesis is wrong for Aeldari - its residual is a mechanics
      defect, as with T'au Empire
  (b) the screen measured almost nothing, because the builder cannot field the
      list: the seed slice is 600 points of 2,000 (SEED_FRACTION 0.3) and every
      template overruns it (task #40)

These are distinguishable. Two other sourced lists moved their factions hard -
Tyranids +9.49 (adopted) and Leagues of Votann +15.89 - so the harness clearly
CAN deliver a list sometimes. What differs?

The candidate mechanism: a seed walk with a fixed points slice systematically
favours CHEAP entries. A list whose identity lives in expensive centrepieces
cannot be represented, because the slice affords two or three of them and
`_random_fill` then spends the remaining seventy percent on whatever is cheap.
The Aeldari list carries an Avatar of Khaine at 280 points, three Wraithlords
and three Fire Prisms; the Tyranid list is mostly cheap bodies.

This measures DELIVERY: for each declared entry, how many squads are fielded
against how many the real list runs, weighted by what those squads cost. A list
delivered faithfully scores near 1.0. One whose expensive anchors get dropped
while its cheap chaff is multiplied scores low, and its screen measured a
different army than the one intended.

Run: PYTHONHASHSEED=0 python -m scripts._list_delivery_probe
     LD_SEEDS=16
"""
from __future__ import annotations
import collections
import os
import random

from code.archetypes import ARCHETYPES, _effective_template, _squad_cost
from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG

N_SEEDS = int(os.environ.get("LD_SEEDS", "16"))

# (faction, environment gate, value to set, label). Each sourced list is
# measured with its own gate on, since most are default-off.
CASES = [
    ("Tyranids", "SWEG_TYRANID_LIST_SOURCED", "1", "adopted, screened +9.49"),
    ("Leagues of Votann", "SWEG_VOTANN_LIST_SOURCED", "1", "held, screened +15.89"),
    ("Aeldari", "SWEG_AELDARI_LIST_SOURCED", "1", "held, screened +1.06 FLAT"),
]


def _measure(fac: str):
    tmpl = ARCHETYPES.get(fac)
    if not tmpl:
        return None
    entries = _effective_template(fac, next(iter(tmpl.values())))
    name_of = {}
    cost_of = {}
    for k in entries:
        p = UNIT_CATALOG.get(k)
        if p is None:
            continue
        name_of[k] = p.name
        cost_of[k] = _squad_cost(k)

    fielded = collections.Counter()
    for seed in range(N_SEEDS):
        army = build_faction_random_army("A", fac, 2000, rng=random.Random(seed),
                                         use_archetype=True)
        per = collections.Counter()
        for u in army.units:
            per[u.profile.name] += 1
        for k, nm in name_of.items():
            p = UNIT_CATALOG[k]
            mm = max(1, getattr(p, "min_models", 1) or 1)
            per_squads = per.get(nm, 0) / mm
            fielded[k] += per_squads
    for k in fielded:
        fielded[k] /= N_SEEDS

    rows = []
    declared_pts = delivered_pts = surplus_pts = 0.0
    for k, want in entries.items():
        if k not in cost_of:
            continue
        got = fielded[k]
        c = cost_of[k]
        declared_pts += c * want
        delivered_pts += c * min(got, want)
        surplus_pts += c * max(0.0, got - want)
        rows.append((name_of[k], want, got, c))
    return rows, declared_pts, delivered_pts, surplus_pts


def main() -> None:
    print(f"=== sourced-list delivery, {N_SEEDS} seeds ===")
    print("delivery = points of the declared list actually fielded, over the")
    print("           points the list declares. 1.00 is faithful.")
    print("surplus  = points of OVER-fielded entries, over the same total.")
    print("           High surplus with low delivery is the seed slice buying")
    print("           cheap copies instead of the list's anchors.\n")

    summary = []
    for fac, gate, val, label in CASES:
        prev = os.environ.get(gate)
        os.environ[gate] = val
        try:
            import importlib
            import code.archetypes as _a
            importlib.reload(_a)
            globals()["ARCHETYPES"] = _a.ARCHETYPES
            res = _measure(fac)
        finally:
            if prev is None:
                os.environ.pop(gate, None)
            else:
                os.environ[gate] = prev
        if res is None:
            print(f"{fac}: no template")
            continue
        rows, decl, deliv, surp = res
        d = deliv / decl if decl else 0.0
        s = surp / decl if decl else 0.0
        summary.append((fac, label, d, s))
        print(f"--- {fac}  ({label}) ---")
        print(f"{'entry':<38}{'want':>6}{'fielded':>9}{'squad pts':>11}")
        for nm, want, got, c in sorted(rows, key=lambda r: -r[3]):
            flag = ""
            if got < want * 0.75:
                flag = "   <-- UNDER-delivered"
            elif got > want * 1.5:
                flag = "   <-- over-fielded"
            print(f"{nm[:37]:<38}{want:>6}{got:>9.2f}{c:>11.0f}{flag}")
        print(f"  declared {decl:.0f} pts | delivered {deliv:.0f} "
              f"({d:.2f}) | surplus {surp:.0f} ({s:.2f})\n")

    if summary:
        print("=== summary ===")
        print(f"{'faction':<20}{'delivery':>10}{'surplus':>9}   screen outcome")
        for fac, label, d, s in summary:
            print(f"{fac:<20}{d:>10.2f}{s:>9.2f}   {label}")
        print()
        print("  If the lists that MOVED their faction are the ones delivered,")
        print("  and the flat one is the one that was not, then the Aeldari")
        print("  screen measured the seed slice rather than the list, and the")
        print("  list hypothesis for Aeldari is untested rather than refuted.")


if __name__ == "__main__":
    main()
