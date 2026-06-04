"""Durable-shooty-vehicle over-fragility / cover diagnostic (#1 lever, instrument-first).

The de-flattered baseline localized the #1 lever to the sim under-valuing durable
shooty vehicles (Astra Militarum / AdMech / CSM crater on real lists). Watchdog
hypothesis (user probe): the sim UNDER-grants cover — `Map.cover_at(point)` grants
Benefit of Cover only when a model's POSITION POINT is INSIDE a terrain footprint,
with NO behind-cover check. Real 10e grants cover for being within OR BEHIND a
cover feature; big vehicles can't sit inside terrain, so in real play they go
hull-down BEHIND it and get cover — but the sim gives them none → over-exposed →
over-die.

This read-only probe wraps `Battle._do_shoot` and, for every shot whose TARGET is
a durable VEHICLE (VEHICLE keyword + >=8 wounds), records whether the map grants
that target cover at its position, plus the damage it takes. Reports per faction:
durable-vehicle shots received, % in cover, and avg damage taken per such shot. If
durable vehicles are in cover ~never, the no-behind-cover gap is a real driver of
the #1 lever. Run with PYTHONHASHSEED=0.
"""
import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from code.map import TerrainType
from scripts.evaluate_vs_meta import _pick_rotation_map

# Durable-vehicle under-shooters + a spread of opponents.
DURABLE_VEH = ["Astra Militarum", "Adeptus Mechanicus", "Chaos Space Marines"]
OPPONENTS = ["Imperial Knights", "World Eaters", "Tyranids", "Aeldari",
             "Adeptus Astartes", "Necrons"]
SEEDS = [1, 2, 3]
COVER = (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.RUIN)


def _is_durable_vehicle(u):
    kw = u.profile.unit_keywords or ()
    return "VEHICLE" in kw and (u.profile.health or 0) >= 8


def run_pair(a_fac, b_fac, seed, agg):
    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed), use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000), use_archetype=True)
    if not a.units or not b.units:
        return
    battle = Battle(a, b, map_=_pick_rotation_map(seed))
    real = battle._do_shoot

    def wrapped(attacker, attacker_army, defender_army):
        # Snapshot the durable-vehicle defenders' HP before the shot so we can
        # attribute damage taken; record cover at their positions.
        before = {u.uid: u.current_health for u in defender_army.units if _is_durable_vehicle(u)}
        result = real(attacker, attacker_army, defender_army)
        for u in defender_army.units:
            if u.uid not in before:
                continue
            lost = before[u.uid] - u.current_health
            if lost <= 0:
                continue  # this shot didn't hit this vehicle
            fac = u.profile.faction or "?"
            in_cov = battle.map.cover_at(u.position) in COVER
            d = agg[fac]
            d["veh_shots"] += 1
            d["veh_in_cover"] += 1 if in_cov else 0
            d["veh_dmg_taken"] += lost
        return result

    battle._do_shoot = wrapped
    battle.run()


if __name__ == "__main__":
    agg = defaultdict(lambda: defaultdict(float))
    for f in DURABLE_VEH:
        for opp in OPPONENTS:
            for s in SEEDS:
                run_pair(f, opp, s, agg)
                run_pair(opp, f, s + 50, agg)

    print(f"{'Faction':<22} {'vehShots':>9} {'%inCover':>9} {'dmg/shot':>9}")
    print("-" * 52)
    for f in DURABLE_VEH:
        d = agg[f]
        n = d["veh_shots"] or 1
        print(f"{f:<22} {int(d['veh_shots']):>9} "
              f"{100*d['veh_in_cover']/n:>8.0f}% {d['veh_dmg_taken']/n:>9.2f}")
    print()
    print("vehShots = shots that damaged a durable VEHICLE (VEHICLE + >=8W) of this faction.")
    print("%inCover = fraction of those where the sim granted the vehicle cover at its position.")
    print("If %inCover is ~0, the no-behind-cover gap leaves durable vehicles over-exposed (the")
    print("watchdog's over-fragility hypothesis for the #1 lever).")
