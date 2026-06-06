"""Over-shooter cluster decomposition (#82, wave 194).

The over-pole (Imperial Knights) plateaued on the contest family at gated ~21.
The next axis is the OVER-SHOOTER CLUSTER — Thousand Sons / Emperor's Children /
World Eaters / Custodes / Sororitas / Votann / Drukhari are all systematically
over their tournament target. The watchdog's fork to resolve BEFORE building:

  (a) COMBAT-OUTPUT over-rating — the sim over-credits their elite weapons per
      point (they DEAL too much damage). A faithful per-weapon fidelity fix.
  (b) DURABILITY over-rating — they over-survive (they TAKE too little). Also a
      combat-fidelity axis.
  (c) per-model REPRESENTATION over-rating — they win WITHOUT proportional
      damage (concentration / objective / activation effects). Structural; keep
      hunting representation fidelity, do NOT re-fit stats.

Method (mirrors diag_attrition_split): every faction plays a fixed round-robin of
opponents; snapshot wounds at start/end; per faction accumulate damage DEALT (wounds
removed from opponents) and damage TAKEN (own wounds lost) and the win rate. All
armies are 2000 pts so the numbers are directly comparable. We then rank the field:
  * over-shooters HIGH on dealt/game  -> (a) output over-rating
  * over-shooters LOW on taken/game   -> (b) durability over-rating
  * over-shooters win (high net) but dealt/taken are NORMAL -> (c) representation
    (they out-score without out-fighting).

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_overshooter
"""
from __future__ import annotations

import random
from collections import defaultdict

from code.army_builder import build_faction_random_army
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
OVERSHOOTERS = {
    "Thousand Sons", "Emperor's Children", "World Eaters", "Adeptus Custodes",
    "Adepta Sororitas", "Leagues of Votann", "Drukhari",
}
SEEDS = [1, 2, 3]
OPP_OFFSETS = [5, 11, 17]  # each faction faces a fixed varied spread


def _snap(army):
    return {id(u): u.current_health for u in army.units}


def _taken(army, before):
    return sum(max(0.0, before.get(id(u), 0.0) - u.current_health) for u in army.units)


def main():
    stats = defaultdict(lambda: {"dealt": 0.0, "taken": 0.0, "wins": 0.0, "vp": 0.0, "games": 0})
    n = len(FACTIONS)
    for i, fa in enumerate(FACTIONS):
        for off in OPP_OFFSETS:
            fb = FACTIONS[(i + off) % n]
            for seed in SEEDS:
                a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 5000), use_archetype=True)
                if not a.units or not b.units:
                    continue
                sa, sb = _snap(a), _snap(b)
                battle = Battle(a, b, map_=_pick_rotation_map(seed))
                result = battle.run()
                ta, tb = _taken(a, sa), _taken(b, sb)
                stats[fa]["dealt"] += tb        # a dealt = wounds taken by b
                stats[fa]["taken"] += ta
                stats[fa]["vp"] += result.a_vp  # faction a's primary VP this game
                stats[fa]["games"] += 1
                if result.winner == a.name:
                    stats[fa]["wins"] += 1
                elif result.winner is None:
                    stats[fa]["wins"] += 0.5

    rows = []
    for fac, d in stats.items():
        g = max(1, d["games"])
        rows.append((d["dealt"] / g, d["taken"] / g, 100 * d["wins"] / g, d["vp"] / g, fac))
    print("=== field damage + primary-VP decomposition (2000pt, fixed round-robin) ===")
    print(f"{'faction':24} {'dealt/g':>8} {'taken/g':>8} {'net/g':>7} {'WR%':>6} {'primVP/g':>9}  over?")
    for dealt, taken, wr, vp, fac in sorted(rows, key=lambda r: -r[2]):
        tag = "OVER" if fac in OVERSHOOTERS else ""
        print(f"{fac:24} {dealt:>8.0f} {taken:>8.0f} {dealt-taken:>7.0f} {wr:>6.0f} {vp:>9.1f}  {tag}")
    print()
    over = [r for r in rows if r[4] in OVERSHOOTERS]
    rest = [r for r in rows if r[4] not in OVERSHOOTERS]
    def avg(rs, k): return sum(r[k] for r in rs) / max(1, len(rs))
    print(f"OVER-SHOOTERS  dealt={avg(over,0):.0f} taken={avg(over,1):.0f} net={avg(over,0)-avg(over,1):.0f} WR={avg(over,2):.0f}% primVP={avg(over,3):.1f}")
    print(f"REST           dealt={avg(rest,0):.0f} taken={avg(rest,1):.0f} net={avg(rest,0)-avg(rest,1):.0f} WR={avg(rest,2):.0f}% primVP={avg(rest,3):.1f}")
    print()
    print("Reading: over-shooter WINS via HIGH net damage -> (a) OUTPUT/(b) DURABILITY")
    print("combat fidelity; via HIGH primVP with NORMAL/negative net -> (c) REPRESENTATION")
    print("(out-scores without out-fighting — the structural objective-game over-side).")


if __name__ == "__main__":
    main()
