"""Roster-filter audit for the proposed Adeptus Astartes ranged-hold lever.

Replicates the shared advance-suppression filter used by the ranged-hold family
(_ad_tsons / _ad_soror): rDPA = attacks * hit_probability * weapon_damage_per_shot,
held iff rDPA >= 2.0 AND range_inches >= 18.0 AND NOT assault. Prints, for every
distinct Adeptus Astartes catalogue unit, whether the filter HOLDS it (Advance
suppressed) or leaves it FREE to Advance, so we can confirm the filter catches the
fire platforms and frees the assault/bolter infantry.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_astartes_filter
"""
from __future__ import annotations

from code.units import UNIT_CATALOG
from code.factions import is_marine_faction


def rdpa(p) -> float:
    return (p.attacks or 0.0) * (p.hit_probability or 0.0) * (p.weapon_damage_per_shot or 0.0)


def main() -> None:
    held, free = [], []
    seen = set()
    for key, u in sorted(UNIT_CATALOG.items()):
        p = getattr(u, "profile", u)
        fac = getattr(p, "faction", "") or ""
        if fac != "Adeptus Astartes":
            continue
        name = getattr(p, "name", key)
        if name in seen:
            continue
        seen.add(name)
        r = rdpa(p)
        rng = p.range_inches or 0.0
        assault = bool(getattr(p, "assault", False))
        passes = (r >= 2.0 and rng >= 18.0 and not assault)
        row = (name, r, rng, assault, p.attacks, p.hit_probability, p.weapon_damage_per_shot)
        (held if passes else free).append(row)

    def show(rows):
        for name, r, rng, assault, a, h, d in sorted(rows, key=lambda x: -x[1]):
            print(f"  {name[:34]:34s} rDPA={r:5.2f} range={rng:4.0f} "
                  f"assault={str(assault):5s} (A={a} hit={h:.2f} D={d})")

    print(f"=== HELD (Advance suppressed): {len(held)} units ===")
    show(held)
    print(f"\n=== FREE to Advance: {len(free)} units ===")
    show(free)


if __name__ == "__main__":
    main()
