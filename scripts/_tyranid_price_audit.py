"""What does the catalogue charge for Tyranid monsters, and per how many models?

The Tyranid archetype declares a Carnifex slot but annotates it "461pt min squad
in SwegHammer pricing - too expensive to seed". A real 10th-edition Carnifex is
priced per model, around 115-125 points. If the catalogue charges 461 for the
minimum squad, the builder cannot afford one inside a 2000-point army and fills
the space with gaunts instead — which would explain a gaunt-swarm Tyranid list
with almost no way to hurt a Toughness-10 target.

Prints, for every Tyranid datasheet: points_cost, the minimum squad size the
builder will field, and the resulting minimum squad price.

Run: PYTHONHASHSEED=0 python -m scripts._tyranid_price_audit
"""
from __future__ import annotations
import os

from code.units import UNIT_CATALOG

FAC = os.environ.get("PA_FACTION", "Tyranids")

# Field names that could carry a minimum/default squad size, checked in order.
SIZE_FIELDS = ("min_models", "default_models", "squad_size", "models_per_unit",
               "unit_size", "models")


def _squad_size(p):
    for f in SIZE_FIELDS:
        v = getattr(p, f, None)
        if isinstance(v, (int, float)) and v >= 1:
            return int(v), f
    return 1, "(none found - assumed 1)"


def main() -> None:
    rows = []
    for key, p in UNIT_CATALOG.items():
        if (p.faction or "") != FAC:
            continue
        n, src = _squad_size(p)
        rows.append((p.name or key, p.points_cost, n, p.points_cost * n, src,
                     p.toughness, p.health))
    rows.sort(key=lambda r: -r[3])
    print(f"=== {FAC} catalogue pricing ({len(rows)} datasheets) ===")
    print(f"{'unit':<36}{'pts/model':>10}{'min models':>11}{'min squad':>11}"
          f"{'T':>4}{'W':>6}   size field")
    for name, ppm, n, tot, src, t, w in rows:
        print(f"{name[:36]:<36}{ppm:>10.0f}{n:>11}{tot:>11.0f}{t:>4}{w:>6.0f}   {src}")


if __name__ == "__main__":
    main()
