"""Read-only cover-usage probe (diagnostic task, 2026-07).

Q4 of the AM-cover diagnostic: of AM shooting bodies (roles SHOOTY / HEAVY /
HORDE) alive at game end, what fraction are standing in a cover-granting
terrain feature?

IMPORTANT — why this does NOT use `unit.in_cover`:
`Unit.in_cover` (code/units.py) is a TRANSIENT flag. It is set True only while
`Battle._do_shoot` / `Battle._do_overwatch` are resolving ONE specific ranged
attack against the unit, and is restored to its pre-attack value (almost
always False) immediately after that attack finishes resolving (see
simulator.py, the `saved_cover = shoot_target.in_cover ... shoot_target.in_cover
= saved_cover` bracketing around each `_do_shoot` call, e.g. lines ~15915 and
~15999). By the time a game has ended nothing is mid-resolution, so
`unit.in_cover` reads back to its default False for essentially every unit —
sampling it post-game (as scripts/_am_advance_probe.py's "COVER at game end"
section does) measures nothing real.

This probe instead re-derives cover the way the sim's own save-math does it:
querying `Battle.map.cover_at(unit.position)` (code/map.py `Map.cover_at`),
the position-only terrain lookup that both `_do_shoot`'s SWEG_COVER_ANGLE=0
fallback and the movement AI's `_best_nearby_cover_point` consult. It reports
whether the unit is standing inside any LIGHT_COVER / HEAVY_COVER / RUIN /
OBSCURING (Woods) terrain footprint at the final board state.

Run:  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts._cover_probe [N]
Default N=4 seeds x 3 opponents = 12 games (single process, small probe).
"""
from __future__ import annotations
import os
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    import sys as _sys
    os.execvpe(_sys.executable, [_sys.executable, "-m", "scripts._cover_probe"] + _sys.argv[1:], os.environ)

import random
import sys
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from code.roles import classify
from code.map import TerrainType
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC = "Astra Militarum"
OPPS = ["Necrons", "Adeptus Astartes", "Orks"]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
_idx = {f: i for i, f in enumerate(FACTIONS)}

_COVER_TYPES = (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER,
                TerrainType.RUIN, TerrainType.OBSCURING)

ROLES = ("SHOOTY", "HEAVY", "HORDE")

# Overall + per-role + per-game tallies.
cover_total = [0, 0]                      # [in_cover, total] all qualifying AM bodies
cover_by_role = defaultdict(lambda: [0, 0])
per_game_frac = []                        # one fraction per game (for spread)
games_played = 0
games_with_zero_terrain = 0

for opp in OPPS:
    for seed in range(N):
        ps = (_idx[A_FAC] * 1000 + _idx[opp]) * 100 + seed
        random.seed(ps)
        a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(seed), use_archetype=True)
        b = build_faction_random_army("B", opp, 2000, rng=random.Random(seed + 10000), use_archetype=True)
        if not a.units or not b.units:
            continue
        map_ = _pick_rotation_map(seed)
        pr = _pick_primary_mission(ps)
        battle = Battle(a, b, map_=map_, primary_mission=pr)
        battle.run()
        games_played += 1

        if not any(t.type in _COVER_TYPES for t in map_.terrain):
            games_with_zero_terrain += 1

        g_in = 0
        g_total = 0
        for u in a.units:
            if u.current_health <= 0:
                continue
            role = classify(u.profile)
            if role not in ROLES:
                continue
            in_cov = battle.map.cover_at(u.position) in _COVER_TYPES
            cover_total[1] += 1
            cover_by_role[role][1] += 1
            g_total += 1
            if in_cov:
                cover_total[0] += 1
                cover_by_role[role][0] += 1
                g_in += 1
        if g_total:
            per_game_frac.append(g_in / g_total)

print(f"# AM cover-at-game-end probe -- {games_played} games "
      f"({len(OPPS)} opponents x up to {N} seeds)")
print(f"# Maps with zero cover-granting terrain: {games_with_zero_terrain}/{games_played}")
print()
print("## Cover terrain occupancy at game end, AM bodies alive, by role "
      "(map_.cover_at(position) in {LIGHT_COVER, HEAVY_COVER, RUIN, OBSCURING})")
for r in ROLES:
    n_in, n_tot = cover_by_role[r]
    if n_tot:
        print(f"  {r:8} {n_in:4}/{n_tot:<4} = {100*n_in/n_tot:5.1f}%")
n_in, n_tot = cover_total
print(f"  {'ALL':8} {n_in:4}/{n_tot:<4} = {100*n_in/max(n_tot,1):5.1f}%")
if per_game_frac:
    print(f"\n## Per-game fraction spread: min={min(per_game_frac):.2f} "
          f"max={max(per_game_frac):.2f} "
          f"mean={sum(per_game_frac)/len(per_game_frac):.2f} "
          f"(n_games_with_qualifying_units={len(per_game_frac)})")
