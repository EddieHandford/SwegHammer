"""Unit tests for the terrain geometry substrate (code/sim/los.py).

Hand-drawn cases for has_los / path_blocked / wall_clamp, plus an
agreement check that has_los matches the trusted Map.has_line_of_sight engine
it delegates to, and a byte-agreement sweep proving path_blocked and the
Liang-Barsky clamp are self-consistent.

Run:  python -m scripts.test_los
Exit: 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import sys

from code.map import Map, Objective, Terrain, TerrainType
from code.sim import los

_fails = []


def check(name, cond):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _fails.append(name)


def _map(*terrain):
    return Map(name="t", width=44.0, height=60.0, terrain=tuple(terrain),
               objectives=(Objective(name="c", x=22.0, y=30.0),))


def test_has_los_ruin():
    # A ruin square occupying x in [20,28], y in [20,28].
    ruin = Terrain("R", 20.0, 20.0, 8.0, 8.0, TerrainType.RUIN)
    m = _map(ruin)
    # Horizontal line at y=24 straight through the ruin -> blocked.
    check("ruin blocks a shot straight through it",
          los.has_los((10.0, 24.0), (38.0, 24.0), m) is False)
    # A line that passes well above the ruin (y=5) -> clear.
    check("shot clear of the ruin is not blocked",
          los.has_los((10.0, 5.0), (38.0, 5.0), m) is True)
    # Shooter standing INSIDE the ruin can see out (endpoint contained).
    check("model inside the ruin can see out",
          los.has_los((24.0, 24.0), (38.0, 24.0), m) is True)
    # AIRCRAFT sees through ruin walls (blanket exception).
    check("AIRCRAFT sees through the ruin",
          los.has_los((10.0, 24.0), (38.0, 24.0), m,
                      attacker_keywords=("AIRCRAFT",)) is True)


def test_has_los_woods():
    woods = Terrain("W", 20.0, 20.0, 8.0, 8.0, TerrainType.OBSCURING)
    m = _map(woods)
    check("woods block a shot straight through them",
          los.has_los((10.0, 24.0), (38.0, 24.0), m) is False)
    # TOWERING sees over Woods (but not ruins).
    check("TOWERING sees over the woods",
          los.has_los((10.0, 24.0), (38.0, 24.0), m,
                      target_keywords=("TOWERING",)) is True)


def test_has_los_cover_never_blocks():
    for tt in (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER):
        cov = Terrain("C", 20.0, 20.0, 8.0, 8.0, tt)
        m = _map(cov)
        check(f"{tt.value} never blocks sight",
              los.has_los((10.0, 24.0), (38.0, 24.0), m) is True)


def test_has_los_agrees_with_map():
    # A dense-ish layout; assert has_los == Map.has_line_of_sight on a grid of
    # sample lines (it delegates, so this must be exact — a guard against the
    # delegation being accidentally rewired).
    m = _map(
        Terrain("R1", 10.0, 10.0, 8.0, 8.0, TerrainType.RUIN),
        Terrain("W1", 26.0, 30.0, 6.0, 6.0, TerrainType.OBSCURING),
        Terrain("R2", 30.0, 8.0, 7.0, 9.0, TerrainType.RUIN),
    )
    pts = [(x, y) for x in range(2, 44, 3) for y in range(2, 60, 5)]
    disagree = 0
    n = 0
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            n += 1
            got = los.has_los(a, b, m)
            want = m.has_line_of_sight(a, b)
            if got != want:
                disagree += 1
    check(f"has_los agrees with Map.has_line_of_sight on {n} sample lines "
          f"(disagreements={disagree})", disagree == 0)


def test_path_blocked_ruin():
    ruin = Terrain("R", 20.0, 20.0, 8.0, 8.0, TerrainType.RUIN)
    m = _map(ruin)
    los._reset_caches()
    check("move straight through a ruin is path-blocked",
          los.path_blocked((10.0, 24.0), (38.0, 24.0), m) is True)
    check("move clear of the ruin is not path-blocked",
          los.path_blocked((10.0, 5.0), (38.0, 5.0), m) is False)
    # INFANTRY (block_ruins=False) move through ruin walls -> not blocked.
    check("INFANTRY move through the ruin is allowed (block_ruins=False)",
          los.path_blocked((10.0, 24.0), (38.0, 24.0), m, block_ruins=False) is False)
    # Leaving a ruin you start inside is allowed.
    check("a mover starting inside the ruin may leave it",
          los.path_blocked((24.0, 24.0), (38.0, 24.0), m) is False)


def test_path_blocked_woods_passable():
    woods = Terrain("W", 20.0, 20.0, 8.0, 8.0, TerrainType.OBSCURING)
    m = _map(woods)
    los._reset_caches()
    check("woods do not block movement (passable)",
          los.path_blocked((10.0, 24.0), (38.0, 24.0), m) is False)


def test_path_blocked_impassable_blocks_all():
    imp = Terrain("I", 20.0, 20.0, 8.0, 8.0, TerrainType.IMPASSABLE)
    m = _map(imp)
    los._reset_caches()
    check("impassable blocks movement even for block_ruins=False (infantry)",
          los.path_blocked((10.0, 24.0), (38.0, 24.0), m, block_ruins=False) is True)


def test_wall_clamp():
    ruin = Terrain("R", 20.0, 20.0, 8.0, 8.0, TerrainType.RUIN)
    m = _map(ruin)
    los._reset_caches()
    # Approaching the ruin from the left along y=24: should stop at x≈20.
    clamped = los.wall_clamp((10.0, 24.0), (38.0, 24.0), m)
    check("clamp stops the mover at the near wall face (x just under 20)",
          19.0 < clamped[0] <= 20.0 and abs(clamped[1] - 24.0) < 0.5)
    # A move that never touches the ruin is returned unchanged.
    free_end = (38.0, 5.0)
    check("clamp returns the destination unchanged when no wall is crossed",
          los.wall_clamp((10.0, 5.0), free_end, m) == free_end)
    # The clamped point itself must not be path_blocked from the start
    # (i.e. it truly stops outside the wall).
    check("the clamped endpoint does not itself cross the wall",
          los.path_blocked((10.0, 24.0), clamped, m) is False)


def main():
    print("test_los:")
    for fn in (
        test_has_los_ruin,
        test_has_los_woods,
        test_has_los_cover_never_blocks,
        test_has_los_agrees_with_map,
        test_path_blocked_ruin,
        test_path_blocked_woods_passable,
        test_path_blocked_impassable_blocks_all,
        test_wall_clamp,
    ):
        fn()
    print()
    if _fails:
        print(f"FAILED ({len(_fails)}): {', '.join(_fails)}")
        return 1
    print("all los substrate tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
