"""One-shot roster audit: which Tyranids units would the shared ranged-hold
filter (rDPA >= 2.0 AND range >= 18") hold, and which stay free to Advance.

Read-only. Run:
  PYTHONIOENCODING=utf-8 python -m scripts.diag_tyranids_filter
"""
from __future__ import annotations

from code.units import UNIT_CATALOG


def main() -> None:
    rows = []
    for key, p in UNIT_CATALOG.items():
        if (p.faction or "") != "Tyranids":
            continue
        rdpa = p.attacks * p.hit_probability * (p.weapon_damage_per_shot or 0.0)
        rng = float(p.range_inches or 0.0)
        assault = bool(getattr(p, "assault", False))
        # The filter can only suppress a non-ASSAULT unit whose rDPA>=2 & range>=18.
        held = (rdpa >= 2.0) and (rng >= 18.0) and not assault
        rows.append((held, key, p.name, rdpa, rng, assault, p.attacks,
                     p.hit_probability, p.weapon_damage_per_shot, p.range_inches))
    rows.sort(key=lambda r: (-r[0], -r[3]))
    print(f"{'HELD':5s} {'name':32s} {'rDPA':>6s} {'rng':>5s} {'asslt':>5s} "
          f"{'atk':>5s} {'hit':>5s} {'dmg/shot':>8s}")
    print("-" * 90)
    for (held, key, name, rdpa, rng, assault, atk, hit, dps, rngi) in rows:
        mark = "HOLD" if held else "  -"
        print(f"{mark:5s} {name[:32]:32s} {rdpa:6.2f} {rng:5.0f} "
              f"{str(assault):>5s} {atk:5.1f} {hit:5.2f} {dps:8.2f}")
    n_hold = sum(1 for r in rows if r[0])
    print("-" * 90)
    print(f"Total Tyranids units: {len(rows)}   HELD by filter: {n_hold}")


if __name__ == "__main__":
    main()
