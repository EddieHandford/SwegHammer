"""WE melee-output over-credit probe (#86, wave 199) — last cheap over-side probe.

The watchdog wants the evidence completed before escalating the displacement-
re-model fork: is World Eaters' MELEE output over-credited per point vs the field's
other melee armies? Gated SWEG_MODE_INSTR splits each faction's damage dealt into
melee vs ranged. We compare WE's melee/game to the comparable melee armies
(Khorne-ish Daemons, Custodes, Drukhari, Tyranids) — if WE is a clear outlier
above them, a per-point melee over-credit lever may exist; if in line, it's
faithful (the known once-per-round-melee small residual) and the over-side combat
axis is exhausted.

Run: PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.diag_melee_output
"""
from __future__ import annotations

import os
import random

os.environ["SWEG_MODE_INSTR"] = "1"

from code.army_builder import build_faction_random_army
from code import units as units_mod
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map

FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
MELEE_FACTIONS = {"World Eaters", "Adeptus Custodes", "Chaos Daemons", "Tyranids",
                  "Orks", "Drukhari", "Emperor's Children", "Genestealer Cults"}
SEEDS = [1, 2, 3]
OPP_OFFSETS = [5, 11, 17]


def main():
    units_mod.MODE_STATS.clear()
    games = {}
    n = len(FACTIONS)
    for i, fa in enumerate(FACTIONS):
        for off in OPP_OFFSETS:
            fb = FACTIONS[(i + off) % n]
            for seed in SEEDS:
                a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
                b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 5000), use_archetype=True)
                if not a.units or not b.units:
                    continue
                games[fa] = games.get(fa, 0) + 1
                games[fb] = games.get(fb, 0) + 1
                Battle(a, b, map_=_pick_rotation_map(seed)).run()

    rows = []
    for fac, d in units_mod.MODE_STATS.items():
        g = max(1, games.get(fac, 1))
        rows.append((d["melee"] / g, d["ranged"] / g, fac))
    print("=== per-faction damage dealt by mode (per game) ===")
    print(f"{'faction':24} {'melee/g':>8} {'ranged/g':>9} {'total':>7}  melee-army?")
    for mel, rng, fac in sorted(rows, key=lambda r: -r[0]):
        tag = "MELEE" if fac in MELEE_FACTIONS else ""
        print(f"{fac:24} {mel:>8.0f} {rng:>9.0f} {mel+rng:>7.0f}  {tag}")
    print()
    we = next((r for r in rows if r[2] == "World Eaters"), None)
    mel_peers = [r for r in rows if r[2] in MELEE_FACTIONS and r[2] != "World Eaters"]
    if we and mel_peers:
        peer_avg = sum(r[0] for r in mel_peers) / len(mel_peers)
        print(f"World Eaters melee/g = {we[0]:.0f}; other melee armies avg = {peer_avg:.0f}")
        print("Reading: WE >> peers -> possible per-point melee over-credit (a cheap lever).")
        print("WE ~= peers -> faithful (known once-per-round small residual); over-side")
        print("combat axis exhausted -> the residual is the displacement representation.")


if __name__ == "__main__":
    main()
