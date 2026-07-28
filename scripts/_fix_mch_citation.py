"""Correct the blast radius and record the screen verdict in the melee_charge_hold citation."""
from __future__ import annotations
import collections
import json

PATH = "data/rule_citations.d/keywords_and_mechanics.json"
KEY = "simulator.melee_charge_hold"

ADD = (
    " BLAST RADIUS CORRECTION: this gate touches **132 catalogue units of 1385**, "
    "every melee-only unit in the game (Chaos Daemons 25, Tyranids 20, Chaos Space "
    "Marines 11, Death Guard 9, Necrons 9, World Eaters 7 and so on) - NOT the 12 "
    "units first recorded, which is the HORDE-and-melee-only subset that "
    "SWEG_MELEE_ONLY_ENGAGE touches. The figure was carried across in error; the "
    "N=80 screen exposed it, because fifteen factions moved decisively and no "
    "12-unit change could do that. "
    "SCREENED (data/_scr_mch_full_log.json, N=80 paired against sc68a): gated mean "
    "absolute error 3.21 -> 3.63, +0.42 WORSE. A redistribution rather than a "
    "uniform regression - Adeptus Astartes -4.36, Aeldari -3.65, Chaos Space Marines "
    "-5.09 and Emperor's Children +5.02 move TOWARD real, while Genestealer Cults "
    "+12.66, World Eaters +9.59, Drukhari +8.25, Death Guard +4.31 and Astra "
    "Militarum -4.10 move away. TYRANIDS, the faction this was built for, moved "
    "+0.34 and NOT decisively: doubling charge eligibility (25.1 to 52.5 percent), "
    "charge connection (11 to 25 percent) and engagement (8.7 to 20.4 percent), and "
    "tripling Hormagaunt melee damage (1.7 to 5.1 a game), produced no measurable "
    "win-rate gain. HELD default-off pending an owner ruling: it is faithful and it "
    "costs the frame."
)


def main() -> None:
    d = json.load(open(PATH, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    if KEY not in d:
        print("citation missing — nothing to correct")
        return
    if "BLAST RADIUS CORRECTION" in d[KEY].get("effect", ""):
        print("already corrected — no change")
        return
    d[KEY]["effect"] = d[KEY]["effect"] + ADD
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(PATH, "a", encoding="utf-8").write("\n")
    print("blast radius corrected and verdict recorded")


if __name__ == "__main__":
    main()
