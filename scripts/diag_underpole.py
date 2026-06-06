"""Under-pole loss decomposition (avenue-3, fork-agnostic).

The watchdog's question: the deck-frame under-pole (Astra Militarum ~14.9 / Adeptus
Mechanicus ~12.0 gated — half the residual, independent of the physics scale-fork)
loses. WHY? Is it DEAD-BY-COMBAT (tabled / decimated — a combat-output or durability
gap) or OUT-POSITIONED (lost on victory points while a healthy fraction of the army
is still ALIVE — a positional gap that folds into the contest/physics question)?

For Astra Militarum and Adeptus Mechanicus vs a cross-section of the field, at game
end measure the under-pole army's surviving-model fraction and classify each LOSS:
  tabled / dead-by-combat  = lost AND < 30% of its models still alive
  out-positioned           = lost AND >= 30% still alive (alive but not scoring)
Also report mean under-pole survival vs the opponent's (does it die FASTER than the
field?) and the mean round the under-pole is reduced below 50%.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_underpole
"""
from __future__ import annotations

import random

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

UNDER = ["Astra Militarum", "Adeptus Mechanicus"]
FIELD = ["Imperial Knights", "Tyranids", "Orks", "Adeptus Astartes",
         "Drukhari", "Thousand Sons", "World Eaters", "Necrons"]
SEEDS = list(range(1, 6))


def _alive_frac(army, start_n: int) -> float:
    return sum(1 for u in army.units if u.is_alive) / max(1, start_n)


def main() -> None:
    print("=== UNDER-POLE loss decomposition (dead-by-combat vs out-positioned) ===")
    for uf in UNDER:
        games = wins = tabled = positional = 0
        surv = opp_surv = 0.0
        for opp in FIELD:
            for seed in SEEDS:
                for side in ("A", "B"):
                    af = uf if side == "A" else opp
                    bf = opp if side == "A" else uf
                    a = build_faction_random_army("A", af, 2000, rng=random.Random(seed), use_archetype=True)
                    b = build_faction_random_army("B", bf, 2000, rng=random.Random(seed + 99), use_archetype=True)
                    if not a.units or not b.units:
                        continue
                    ua = a if side == "A" else b
                    oa = b if side == "A" else a
                    ua_start = sum(1 for _ in ua.units)
                    oa_start = sum(1 for _ in oa.units)
                    r = Battle(a, b, map_=_pick_rotation_map(seed)).run()
                    games += 1
                    uf_alive = _alive_frac(ua, ua_start)
                    surv += uf_alive
                    opp_surv += _alive_frac(oa, oa_start)
                    won = r.winner == ("A" if side == "A" else "B")
                    if won:
                        wins += 1
                    elif uf_alive < 0.30:
                        tabled += 1
                    else:
                        positional += 1
        losses = tabled + positional
        print(f"\n{uf}:  games {games}, win rate {100*wins/max(1,games):.0f}%")
        print(f"  mean end survival — under-pole {100*surv/max(1,games):.0f}%  vs opponent {100*opp_surv/max(1,games):.0f}%")
        print(f"  LOSSES decomposed ({losses}):")
        if losses:
            print(f"    DEAD-by-combat (tabled, <30% alive): {tabled}  ({100*tabled/losses:.0f}%)")
            print(f"    OUT-POSITIONED (>=30% alive, lost):  {positional}  ({100*positional/losses:.0f}%)")
    print("\nReading: high DEAD-by-combat% + under-pole survival << opponent = a COMBAT")
    print("gap (durability/output) — fork-independent, fix with cited unmodelled abilities.")
    print("High OUT-POSITIONED% + survival ~ opponent = a POSITIONAL gap that folds into")
    print("the contest/physics scale-fork (don't grind abilities).")


if __name__ == "__main__":
    main()
