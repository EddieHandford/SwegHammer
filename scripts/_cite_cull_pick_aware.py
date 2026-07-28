"""Add the citation for simulator.secondary_cull_pick_aware."""
from __future__ import annotations
import collections
import json

PATH = "data/rule_citations.d/secondaries_pariah_nexus.json"
KEY = "simulator.secondary_cull_pick_aware"


def main() -> None:
    d = json.load(open(PATH, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    if KEY in d:
        print("already cited - no change")
        return
    d[KEY] = collections.OrderedDict([
        ("source", "https://wahapedia.ru/wh40k10ed/the-rules/pariah-nexus-tournament-companion/#Secondary-Missions"),
        ("rule_name", "Fixed Secondary Missions - note down which two you will use"),
        ("quoted_text", "If you are using Fixed Secondary Missions, then before the battle begins, note down which two Secondary Missions from those available you will be using for the battle. Those two Secondary Missions will be active for you for the duration of the battle."),
        ("trigger", "SWEG_CULL_PICK_AWARE=1 (unset or '0' is the byte-identical kill-switch); secondaries._pick_fixed_pair_full is choosing the two Fixed cards and the enemy roster contains ZERO units whose Starting Strength is CULL_THE_HORDE_MIN_MODELS (13) or more, counted per squad_id group rather than per model instance by _enemy_qualifying_horde_units."),
        ("effect", "SELECTION FIDELITY, not a scoring change - the Cull the Horde scorer itself is untouched and remains cited under simulator.secondary_cull_the_horde. Cull the Horde is replaced in whichever slot took it, falling through the printed Fixed pool in the order this function already documents for its duplicate case: No Prisoners first, being broad generic kill achievable against any roster, then Cleanse. The rule quoted above has both players note their two Fixed Missions down before the battle with army lists known, so a pick made against the opponent's actual composition is what the rule describes and an unscoreable note-down is the artefact. The picker was ALREADY composition-aware for the other two kill cards - Bring It Down requires the enemy to field at least _BID_TARGET_THRESHOLD MONSTER/VEHICLE units and Assassination requires two or more enemy CHARACTERs - but Cull the Horde was the FALLBACK for both slots, taken whenever those tests failed, with no check that the enemy could concede it. MEASURED with scripts/_cull_pick_waste_probe.py over all 1386 ordered faction pairs at three seeds each: 294 picks took Cull the Horde and 231 of them, 78.6 percent, faced an enemy with zero qualifying squads. With the gate on, wasted picks fall to zero and Cull is taken 63 times, only where it can score. The waste was near-uniform across factions at about 17.5 percent of each faction's pairs, because it is determined by which OPPONENTS field thirteen-plus-model squads and every faction faces the same field; only about three factions in twenty-two field such squads at all, which is why a gaunt-brood army concedes this card far more often than it can score it."),
        ("scope", "keyword-gated"),
    ])
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(PATH, "a", encoding="utf-8").write("\n")
    print("cited simulator.secondary_cull_pick_aware")


if __name__ == "__main__":
    main()
