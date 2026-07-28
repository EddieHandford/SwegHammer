"""Add the citation for simulator.melee_only_engage."""
from __future__ import annotations
import collections
import json

PATH = "data/rule_citations.d/keywords_and_mechanics.json"
KEY = "simulator.melee_only_engage"


def main() -> None:
    d = json.load(open(PATH, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    if KEY in d:
        print("already cited — no change")
        return
    d[KEY] = collections.OrderedDict([
        ("source", "https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#FIGHT-PHASE"),
        ("rule_name", "Fight phase / datasheet weapons - a unit fights with the melee weapons it is equipped with"),
        ("quoted_text", "Each time a unit is selected to fight, you can make attacks with the melee weapons its models are equipped with."),
        ("trigger", "SWEG_MELEE_ONLY_ENGAGE=1 (unset or '0' is the byte-identical kill-switch); the moving unit's roles.classify label is not MELEE, but roles.combat_profile reports MELEE_ONLY - every weapon it carries has a reach of 1 inch or less."),
        ("effect", "ARTIFICIAL-INTELLIGENCE PILOTING HEURISTIC - not a 10e rules claim; the rule quoted above is why it exists, since a unit equipped only with melee weapons has exactly one way to damage an enemy. Such a unit is admitted to the engage branch of strategy.pick_move_intent, which is otherwise gated on the classify label being MELEE alone. roles.classify collapses capability (MELEE / SHOOTY / DUAL) and body class (HORDE / HEAVY / SUPPORT) into a single label and resolves the collision with an ordered chain whose HORDE test runs FIRST and keys on health == 1; every single-wound melee-only unit is therefore labelled HORDE and never engages. Measured on Tyranids: Hormagaunts take 0 percent ENGAGE intents, connect 11 percent of charges, sit a median 16 inches from the nearest enemy and return 1.7 melee wounds a game for 227 points, while Tyrant Guard - also melee-only but health 4, so it reaches the r == 0 line - takes 82.8 percent. classify is deliberately NOT modified: it is read at roughly seventy branch sites spanning both pipeline stages, and changing it would move the Stage-2 points baselines as a side effect, which the stage discipline in CLAUDE.md forbids. Blast radius measured with scripts/_role_flip_report.py: 12 catalogue units of 1385 across eight factions, every one a genuine melee-only assault unit."),
        ("scope", "keyword-gated"),
    ])
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(PATH, "a", encoding="utf-8").write("\n")
    print("cited simulator.melee_only_engage")


if __name__ == "__main__":
    main()
