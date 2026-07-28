"""Find catalogue keys and prices for the units in the real Maastricht 2026 list.

Sourced list (Ron Eliyahoo, GW Open Maastricht 2026, Subterranean Assault) as
reported by SpikeyBits and Bell of Lost Souls — both already cited in
code/archetypes.py's Tyranid block:

    Trygon (with the Trygon Prime enhancement) - the detachment's engine
    3x Tyranid Prime with Lash Whip @ 65
    Old One Eye @ 150
    Maleceptor @ 170
    2x 10-model Hormagaunts
    Raveners: a Prime unit plus two five-model units
    Tyrannofex with Rupture cannon
    Zoanthropes with Neurothrope
    Carnifex
    Lictor, Neurolictor
    2x Biovore

Run: PYTHONHASHSEED=0 python -m scripts._real_list_key_lookup
"""
from __future__ import annotations

from code.units import UNIT_CATALOG

WANT = ["trygon", "prime", "old one eye", "maleceptor", "hormagaunt", "ravener",
        "tyrannofex", "zoanthrope", "neurothrope", "carnifex", "lictor",
        "biovore", "termagant", "ripper", "exocrine", "hive tyrant",
        "neurotyrant"]


def main() -> None:
    print(f"{'catalogue key':<44}{'name':<38}{'pts':>5}{'min':>5}{'squad':>7}")
    seen = set()
    for key, p in sorted(UNIT_CATALOG.items()):
        if (p.faction or "") != "Tyranids":
            continue
        nm = (p.name or "").lower()
        if not any(w in nm for w in WANT):
            continue
        if key in seen:
            continue
        seen.add(key)
        n = getattr(p, "min_models", 1) or 1
        print(f"{key:<44}{(p.name or '')[:38]:<38}{p.points_cost:>5.0f}{n:>5}"
              f"{p.points_cost*n:>7.0f}")


if __name__ == "__main__":
    main()
