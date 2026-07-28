"""Wave 158 structural proof for squad-rebuild Stage A (gate SWEG_SQUADACT).

A byte-identical A/B cannot tell a working no-op scaffold apart from a gate that
was never toggled. This script proves the gate does something STRUCTURAL:
it runs the SAME seeded battle twice (gate OFF, gate ON), wrapping Battle._emit
to (a) count UnitActivated events and (b) snapshot the high-water size of the
_squad_move_intent cache. Gate ON must populate the cache and emit extra
UnitActivated events; gate OFF must leave the cache empty and emit none from the
scaffold path. Run with PYTHONHASHSEED=0.
"""
import os
import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from code.events import UnitActivated
from scripts.evaluate_vs_meta import _pick_rotation_map


def run_once(a_fac, b_fac, seed, gate_on):
    if gate_on:
        os.environ["SWEG_SQUADACT"] = "1"
    else:
        os.environ.pop("SWEG_SQUADACT", None)

    random.seed(seed)
    a = build_faction_random_army("A", a_fac, 2000, rng=random.Random(seed),
                                  use_archetype=True)
    b = build_faction_random_army("B", b_fac, 2000, rng=random.Random(seed + 10000),
                                  use_archetype=True)
    battle_map = _pick_rotation_map(seed)
    battle = Battle(a, b, map_=battle_map)

    stats = {"unit_activated": 0, "max_cache": 0}
    real_emit = battle._emit

    def counting_emit(event):
        if isinstance(event, UnitActivated):
            stats["unit_activated"] += 1
        cache = getattr(battle, "_squad_move_intent", {})
        if len(cache) > stats["max_cache"]:
            stats["max_cache"] = len(cache)
        return real_emit(event)

    battle._emit = counting_emit
    battle.run()
    return stats


if __name__ == "__main__":
    A, B, SEED = "Tyranids", "Space Marines", 7
    off = run_once(A, B, SEED, gate_on=False)
    on = run_once(A, B, SEED, gate_on=True)
    print(f"pairing: {A} vs {B}  seed={SEED}")
    print(f"  gate OFF: UnitActivated={off['unit_activated']:4d}  "
          f"max _squad_move_intent cache size={off['max_cache']}")
    print(f"  gate ON : UnitActivated={on['unit_activated']:4d}  "
          f"max _squad_move_intent cache size={on['max_cache']}")
    extra = on["unit_activated"] - off["unit_activated"]
    print(f"  delta UnitActivated (ON-OFF) = {extra}")
    ok_cache = off["max_cache"] == 0 and on["max_cache"] > 0
    ok_emit = extra > 0
    print(f"  STRUCTURAL PROOF: cache populated only when ON = {ok_cache}; "
          f"scaffold emitted extra activations when ON = {ok_emit}")
    print("  VERDICT:", "PASS — gate is live and cache is readable"
          if (ok_cache and ok_emit) else "FAIL — gate did nothing structural")
