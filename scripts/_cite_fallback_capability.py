"""Add the citation for simulator.fallback_capability."""
from __future__ import annotations
import collections
import json

PATH = "data/rule_citations.d/keywords_and_mechanics.json"
KEY = "simulator.fallback_capability"


def main() -> None:
    d = json.load(open(PATH, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    if KEY in d:
        print("already cited - no change")
        return
    d[KEY] = collections.OrderedDict([
        ("source", "https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Fall-Back"),
        ("rule_name", "Fall Back"),
        ("quoted_text", "If a unit starts its Movement phase within Engagement Range of one or more enemy units, it can either Remain Stationary or Fall Back. ... A unit that Falls Back cannot shoot or declare a charge later that turn."),
        ("trigger", "SWEG_FALLBACK_CAPABILITY=1 (unset or '0' is the byte-identical kill-switch); the unit is inside enemy Engagement Range and is deciding its move intent. Eligibility becomes: roles.classify is HEAVY (unchanged legacy path), OR roles.combat_profile reports RANGED_ONLY or DUAL and strategy._is_melee_class_effective reports the unit is ranged-primary on effective damage."),
        ("effect", "ARTIFICIAL-INTELLIGENCE PILOTING HEURISTIC - not a 10e rules claim. The Fall Back move itself, its shoot-and-charge lockout and the Desperate Escape test are implemented and cited separately (simulator.fall_back, simulator.desperate_escape); this gate changes only WHICH units the piloting layer will consider Falling Back, never what the rule does. The legacy eligibility test is a role LABEL test - role in ('SHOOTY','HEAVY') - which asks a capability question of a body-class answer. roles.classify collapses capability (SHOOTY / MELEE / DUAL) and body class (HORDE / HEAVY / SUPPORT) into one string through an ordered chain, so a gun-carrying unit is labelled SUPPORT whenever its total damage per activation is below 0.4 and HORDE whenever it has one wound and a save of 4+, and either label leaves it permanently unable to break off and free its guns. The AI-3 Leagues of Votann DUAL extension in the same block is a symptom of that under-inclusion: the general rule was too narrow, so one faction was special-cased. MEASURED with scripts/_pinned_gunline_probe.py over ranged-primary units standing inside enemy Engagement Range: the role label excludes 55.0 percent of pinned activations (SUPPORT 30.8, HORDE 15.2, DUAL 9.0) while the melee-primary test excludes 0.0 percent, and of the activations that do reach the branch most Fall Back - so the branch works and eligibility was the defect. With the gate on, pinned gunlines that break off rise from 35.1 to 87.2 percent and units pinned for three or more consecutive activations fall from 2.9 to 0.5 percent; SWEG_DISPLACE_FALLBACK (default-ON) still applies its three-condition only-when-genuinely-wasted narrowing, so those figures are post-narrowing. Melee-primary units still STAY and fight, preserving the task #7 ruling that a competent player never Falls Back a melee Knight, Carnifex or Hive Tyrant - the ruling is unchanged, only measured with the wound roll, Strength versus Toughness, armour penetration and save included. This is the counterplay half of the classification collision that roles.combat_profile addresses on the melee side."),
        ("scope", "keyword-gated"),
    ])
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(PATH, "a", encoding="utf-8").write("\n")
    print("cited simulator.fallback_capability")


if __name__ == "__main__":
    main()
