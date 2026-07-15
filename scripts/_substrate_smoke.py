"""Functional smoke for the imported planner substrate: build a battle, deploy,
and call each estimator on a live unit to prove every name resolves at runtime
(the deepest, value_top_marker_index, chains through value_projection + the threat
field). Run: PYTHONHASHSEED=0 python -m scripts._substrate_smoke"""
import os, random
from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission
import code.strategy as S

random.seed(0)
a = build_faction_random_army("A", "Aeldari", 2000, rng=random.Random(0), use_archetype=True)
b = build_faction_random_army("B", "Death Guard", 2000, rng=random.Random(9), use_archetype=True)
batt = Battle(a, b, map_=_pick_rotation_map(0), primary_mission=_pick_primary_mission(0))
# run a few activations so units are on the board with positions
batt.run()

unit = next(u for u in a.units if u.current_health > 0)
projectors = S._threat_projectors(b)
srr = 4

r1 = S._trade_vp_per_wound(unit.profile, srr)
r2 = S._trade_our_return(unit, unit.position, [u for u in b.units if u.current_health > 0], srr)
r3 = S._threat_field_at(unit, projectors, unit.position, batt.map)
r4 = S.value_top_marker_index(unit, a, b, batt.map)
obj = batt.map.objectives[0]
r5 = S.value_projection(unit, obj, 2, 1, projectors, batt.map, srr, True, set())

print(f"_trade_vp_per_wound   -> {r1:.4f}")
print(f"_trade_our_return     -> {r2:.4f}")
print(f"_threat_field_at      -> {r3:.4f}")
print(f"value_top_marker_index-> {r4}")
print(f"value_projection      -> {r5}")
print("ALL ESTIMATORS CALLABLE ✓")
