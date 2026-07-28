"""Correct the HEAVY eligibility shape in simulator.fallback_capability and
record the first screen's verdict (which measured a bug, not the mechanism)."""
from __future__ import annotations
import collections
import json

PATH = "data/rule_citations.d/keywords_and_mechanics.json"
KEY = "simulator.fallback_capability"

OLD_TRIGGER_FRAGMENT = "roles.classify is HEAVY (unchanged legacy path), OR"
NEW_TRIGGER_FRAGMENT = (
    "roles.classify is HEAVY OR"
)

APPEND = (
    " CORRECTION AND FIRST SCREEN. As first written this gate made HEAVY eligible "
    "UNCONDITIONALLY, on the reasoning that it kept the legacy behaviour for "
    "gunline vehicles. That was wrong: the legacy condition is role in "
    "('SHOOTY','HEAVY') AND NOT _is_melee_class(...), so the melee-primary guard "
    "has always applied to HEAVY as well, and dropping it stripped the task #7 "
    "ruling that a competent player never Falls Back a melee Knight (Gallant or "
    "Rampager), Carnifex, Hive Tyrant or Daemon Prince. The N=80 full-matrix screen "
    "(data/_scr_fbcap_full_log.json, paired against sc68a) landed exactly where "
    "that bug predicts: Imperial Knights -9.03 (51.6 to 42.5 against a real 47.7) "
    "and Chaos Knights -6.33 (48.0 to 41.6 against a real 44.7), the two "
    "almost-entirely-HEAVY-melee factions, were the largest movers in the table, "
    "and the arm came out gated 3.21 to 4.13 (+0.92) and both-sides raw 6.31 to "
    "7.12 (+0.81) - both WORSE. That screen therefore measured the defect and not "
    "the mechanism. The guard is now universal: eligible if (HEAVY or carries a gun "
    "worth freeing) AND ranged-primary on effective damage. A fair re-screen is "
    "outstanding. The mechanism still looks right where it should: even under the "
    "bug, Astra Militarum moved +4.30 (36.6 to 40.9 against a real 45.3) and Death "
    "Guard -4.97 (59.0 to 54.0 against a real 47.6), both decisively TOWARD real."
)


def main() -> None:
    d = json.load(open(PATH, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    if KEY not in d:
        print("citation missing - nothing to correct")
        return
    if "CORRECTION AND FIRST SCREEN" in d[KEY].get("effect", ""):
        print("already corrected - no change")
        return
    trig = d[KEY].get("trigger", "")
    if OLD_TRIGGER_FRAGMENT in trig:
        d[KEY]["trigger"] = trig.replace(OLD_TRIGGER_FRAGMENT, NEW_TRIGGER_FRAGMENT)
        d[KEY]["trigger"] += (
            " The melee-primary test applies in BOTH branches - a HEAVY unit that is "
            "melee-primary stays and fights."
        )
        print("trigger corrected")
    else:
        print("WARNING: trigger fragment not found; appending verdict only")
    d[KEY]["effect"] = d[KEY]["effect"] + APPEND
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(PATH, "a", encoding="utf-8").write("\n")
    print("fallback_capability citation corrected and screen verdict recorded")


if __name__ == "__main__":
    main()
