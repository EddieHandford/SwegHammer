"""Stage-2 tests for the collision occupant spatial grid (docs/PATHFINDING_PLAN.md).

The grid must be a PURE SPEEDUP: every legality query returns the same boolean as
iterating the full occupant list, and a whole collision-ON battle must come out
byte-identical with the grid OFF vs ON. That identity is what lets the grid contain the
dense-horde O(models^2) collision cost without touching behaviour or determinism.
"""
import os
import random

from code.simulator import _collision_pos_legal, _OccupantGrid, Battle
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map


def test_grid_legality_matches_full_list():
    rng = random.Random(7)
    radii = [0.63, 1.0, 2.0, 3.35]
    occ = [
        (rng.uniform(0, 60), rng.uniform(0, 44), rng.choice(radii), rng.choice([True, False]))
        for _ in range(250)
    ]
    grid = _OccupantGrid(occ)
    for _ in range(2000):
        pos = (rng.uniform(-6, 66), rng.uniform(-6, 50))
        mr = rng.choice(radii)
        fly = rng.choice([True, False])
        assert _collision_pos_legal(pos, mr, occ, fly) == _collision_pos_legal(pos, mr, grid, fly)


def test_grid_preserves_iteration_order():
    occ = [(float(i), float(i), 0.63, bool(i % 2)) for i in range(50)]
    grid = _OccupantGrid(occ)
    assert list(grid) == occ          # order-dependent consumers see the unchanged list
    assert len(grid) == len(occ)
    assert bool(grid) is True
    assert bool(_OccupantGrid([])) is False


def _survivors(battle_armies):
    return tuple(sum(1 for u in army.units if u.is_alive) for army in battle_armies)


def test_collision_battle_identical_grid_off_vs_on():
    def run(grid_on):
        os.environ["SWEG_COLLISION"] = "1"
        os.environ["SWEG_MOVEPLAN"] = "1"
        if grid_on:
            os.environ["SWEG_OCCGRID"] = "1"
        else:
            os.environ.pop("SWEG_OCCGRID", None)
        random.seed(123)
        a = build_faction_random_army("A", "Imperial Knights", 2000, rng=random.Random(3), use_archetype=True)
        b = build_faction_random_army("B", "Orks", 2000, rng=random.Random(102), use_archetype=True)
        random.seed(123)   # combat RNG stream identical between the two runs
        res = Battle(a, b, map_=_pick_rotation_map(3)).run()
        return res.winner, _survivors((a, b))

    off = run(False)
    on = run(True)
    assert off == on, f"grid changed the battle outcome: OFF={off} ON={on}"
    # cleanup
    os.environ.pop("SWEG_OCCGRID", None)
    os.environ.pop("SWEG_COLLISION", None)
    os.environ.pop("SWEG_MOVEPLAN", None)
