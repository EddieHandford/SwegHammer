"""Does the Pathfinder Team carry the MARKERLIGHT keyword? It does not.

The T'au Guided chain (task #42) ends here. Uptime is 3.5 percent because the
army gets only 1.73 Markerlight attempts per shooting phase, and the gates are
not the constraint - 81 percent of attempts reach a hit roll. The remaining
question was how many Markerlight weapons a squad should fire.

That question turns out to be the wrong one. This lists every catalogue unit
carrying the MARKERLIGHT keyword alongside what the T'au archetype actually
fields, so the carriers can be compared against the roster rather than assumed.

WHY IT MATTERS: in tenth edition the Pathfinder Team is the faction's Markerlight
platform - it is the reason the army rule exists. If the keyword sits on other
datasheets instead, the simulator is generating its marks from the wrong units,
and no amount of tuning the per-squad attempt count will fix that.

BSData carries NO Markerlight data at all - the string does not appear once in
data/bsdata/parsed.json - so every MARKERLIGHT keyword in the catalogue comes
from hand-written entries in data/overrides.json. That makes this a data
question, not a mapper question.

Run: PYTHONHASHSEED=0 python -m scripts._tau_markerlight_carriers
"""
from __future__ import annotations
import collections
import random

from code.army_builder import build_faction_random_army
from code.units import UNIT_CATALOG

FAC = "T'au Empire"


def main() -> None:
    print("=== catalogue units carrying MARKERLIGHT ===")
    carriers = {}
    for key, p in UNIT_CATALOG.items():
        if "MARKERLIGHT" in (p.unit_keywords or ()):
            carriers[p.name] = max(1, p.min_models)
    for name, mm in sorted(carriers.items()):
        print(f"    {name[:44]:<46} min_models {mm}")

    print()
    print("=== what the T'au archetype actually fields ===")
    fielded = collections.Counter()
    for seed in range(8):
        army = build_faction_random_army("A", FAC, 2000,
                                         rng=random.Random(seed),
                                         use_archetype=True)
        for u in army.units:
            fielded[u.profile.name] += 1
    n = 8
    print(f"{'unit':<44}{'models/army':>12}{'MARKERLIGHT':>13}{'attempts':>10}")
    total_attempts = 0.0
    for name, c in fielded.most_common():
        per = c / n
        has = name in carriers
        att = (per / carriers[name]) if has else 0.0
        total_attempts += att
        print(f"{name[:43]:<44}{per:>12.1f}{('yes' if has else '-'):>13}"
              f"{att:>10.2f}")
    print()
    print(f"  expected Markerlight attempts per phase: {total_attempts:.2f}")
    print("  (measured 1.73 by scripts/_tau_marker_gates_probe)")

    print()
    pf = [nm for nm in fielded if "Pathfinder" in nm]
    for nm in pf:
        print(f"  {nm}: MARKERLIGHT = {nm in carriers}")
    if pf and not any(nm in carriers for nm in pf):
        print()
        print("  THE PATHFINDER TEAM CARRIES NO MARKERLIGHT KEYWORD.")
        print("  In tenth edition it is the faction's Markerlight platform and")
        print("  the reason the Guided rule exists. Every mark the simulator")
        print("  generates comes from other datasheets instead, which is why")
        print("  the attempt count is set by Strike and Breacher Teams at")
        print("  min_models 10 rather than by the unit built to do this.")
        print()
        print("  This is a DATA defect in data/overrides.json, not a defect in")
        print("  _run_markerlight_phase, and it needs the real datasheet")
        print("  confirmed before any entry is added - BSData carries no")
        print("  Markerlight data to check against.")


if __name__ == "__main__":
    main()
