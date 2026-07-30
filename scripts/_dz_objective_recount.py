"""How many objectives actually sit inside a deployment zone, per rotation map?

Task #46 records "only 4 of 12 maps place any objective in a deployment zone" as
the root cause of the secondary-scoring shortfall — the simulator scores 11.8
secondary victory points against a real 22.7 while OVER-scoring primary 37.7
against 29.1, so the two errors cancel in the total and the distortion hides.

The denominator in that claim does not match the code: the evaluation rotation
is FIVE maps, not twelve (STOCK_MAPS holds ten, including combat_patrol,
open_plains and urban_sprawl, which the rotation never draws). This recomputes
the figure from the actual geometry.

Deployment zones are uniform across every map (code/secondaries.py: Army A's
enemy zone is y >= height - deployment_width, Army B's is y <= deployment_width),
so an objective is "in a deployment zone" exactly when its y falls in either
strip.

WHY IT MATTERS: Extend Battle Lines requires controlling an objective in YOUR
OWN deployment zone. On a map with no such objective the card cannot be scored
by either player, no matter how well the army is piloted.

Run: PYTHONHASHSEED=0 python -m scripts._dz_objective_recount
"""
from __future__ import annotations

from code.maps import (PARIAH_NEXUS_2K_ROTATION, PARIAH_NEXUS_2K_ROTATION_FULL,
                       STOCK_MAPS)


def audit(keys, label: str) -> None:
    print(f"=== {label}: {len(keys)} maps ===\n")
    with_dz = 0
    for key in keys:
        m = STOCK_MAPS[key]
        lo = m.deployment_width
        hi = m.height - m.deployment_width
        # Use the MAP'S OWN predicate, not a re-implemented flat-strip test.
        # With SWEG_MAP_REAL_GEOMETRY on, zones are polygons (diagonal, stepped,
        # quadrant), and a strip test both misses markers that are really inside
        # and admits ones that are not — an earlier version of this script
        # under-counted the sourced layouts for exactly that reason.
        def _zone(o):
            if m.in_deployment_zone((o.x, o.y), is_army_a=True):
                return "A"
            if m.in_deployment_zone((o.x, o.y), is_army_a=False):
                return "B"
            return ""
        inside = [o for o in m.objectives if _zone(o)]
        if inside:
            with_dz += 1
        shape = ("real polygons" if m.deployment_polygon_a
                 else f"flat strips y<={lo:.0f} and y>={hi:.0f}")
        print(f"  {m.name:<28} {len(m.objectives)} objectives, {shape}")
        for o in m.objectives:
            z = _zone(o)
            tag = f"  <-- IN army {z}'s deployment zone" if z else ""
            if z and not m.deployment_polygon_a:
                if abs(o.y - lo) < 1e-6 or abs(o.y - hi) < 1e-6:
                    tag += " (exactly ON the boundary)"
            print(f"      {o.name:<20} x={o.x:>5.1f} y={o.y:>5.1f}{tag}")
        print(f"      -> {len(inside)} of {len(m.objectives)} in a "
              f"deployment zone")
        print()
    print(f"  {with_dz} of {len(keys)} maps place ANY objective in a "
          f"deployment zone\n")


def main() -> None:
    audit(PARIAH_NEXUS_2K_ROTATION, "PRODUCTION ROTATION")
    audit(PARIAH_NEXUS_2K_ROTATION_FULL,
          "FULL ROTATION (SWEG_FULL_DEPLOY_ROTATION, default-off)")
    print("Extend Battle Lines needs an objective in the player's OWN")
    print("deployment zone. On a map with none, the card is unscoreable by")
    print("either side regardless of piloting — so the achievable secondary")
    print("ceiling is set by geometry before any AI decision is made.")


if __name__ == "__main__":
    main()
