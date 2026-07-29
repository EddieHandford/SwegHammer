"""For gates that showed no effect, is their SUBJECT even on the table?

The behavioural sweep narrowed 148 gates to 26 with no observable change, and
its own control proved it cannot go further: SWEG_CULL_PICK_AWARE stays flat
even at 220 battles while being demonstrably real over 36,960 paired games. The
remaining question is structural, not statistical — does the unit the gate acts
on ever get built?

A gate whose subject is never fielded is STRUCTURALLY DEAD: every verdict ever
recorded for it measured nothing, and it will silently become live and untested
the moment that faction's list is re-sourced.

Builds the real fielded set for all 22 factions (session lesson #51 — never
infer it from the catalogue) and checks each named subject against it.

Run: PYTHONHASHSEED=0 python -m scripts._gate_subject_fielded
"""
from __future__ import annotations
import collections
import random

from code.archetypes import ARCHETYPES
from code.army_builder import build_faction_random_army

N = 10

# Gate -> (faction, substring that identifies its subject on a datasheet name).
# Only gates naming a concrete unit can be settled this way; the rest depend on
# a card, phase or board condition and are listed separately below.
#
# The needle must be a DATASHEET NAME. Where it is an ability name or a guess at
# what the gate scopes to, a "never fielded" result says nothing about the gate —
# it only says no unit carries that string in its name. Those rows are marked
# UNVERIFIED and must not be reported as structurally dead.
SUBJECTS = [
    # needle is a real datasheet name — result is decisive
    ("SWEG_ORKS_GHAZGHKULL",        "Orks",               "Ghazghkull", True),
    ("SWEG_IK_CANIS_SINGLE",        "Imperial Knights",   "Canis Rex", True),
    ("SWEG_IK_ACHERON_INVULN",      "Imperial Knights",   "Acheron", True),
    ("SWEG_DG_TYPHUS_MELEE_ONLY",   "Death Guard",        "Typhus", True),
    ("SWEG_CSM_SORCERER_PRESCIENCE", "Chaos Space Marines", "Sorcerer", True),
    ("SWEG_DRUKHARI_SUCCUBUS_SUSTAIN", "Drukhari",        "Succubus", True),
    ("SWEG_EC_DAEMONETTE_FF",       "Emperor's Children", "Daemonette", True),
    # needle is an ABILITY name or an assumption about scope — NOT decisive
    ("SWEG_IK_BONDSMAN_SCOPED",     "Imperial Knights",   "Bondsman", False),
    ("SWEG_WE_BLOOD_TITHE_SCOPED",  "World Eaters",       "Khorne Berzerker", False),
    ("SWEG_AELDARI_BLITZ_RANGE",    "Aeldari",            "Guardian", False),
]

# Gates that do NOT name a unit — they depend on a card, a phase, a cache or a
# board condition, so fieldedness cannot settle them. Recorded so the list is
# honest about what this instrument does not cover.
NOT_UNIT_SCOPED = {
    "SWEG_ACTION_ECONOMY": "action economy — needs an army that performs actions",
    "SWEG_AELDARI_BF_DISCARD": "Battle Focus carry-over — phase state",
    "SWEG_AELDARI_LFR_PHASE": "Lightning-Fast Reactions — stratagem trigger",
    "SWEG_AM_FIRE_SUPPORT_HOLD": "positional hold — board condition",
    "SWEG_DG_PLAGUE_FNP_FAITHFUL": "catalogue feel-no-pain fabrication removal",
    "SWEG_DRUKHARI_PFP_EMBARKED": "Power From Pain accrual while embarked",
    "SWEG_DURCACHE": "CACHE — inertness is CORRECT, a cache that changed results would be a bug",
    "SWEG_LOSCACHE": "CACHE — inertness is CORRECT, same reasoning",
    "SWEG_FIXBAYONETS": "needs a melee-statted Astra Militarum squad (ledger records none)",
    "SWEG_FIXED_POOL_FULL": "Fixed secondary pool — card draw",
    "SWEG_REINFORCEMENTS": "stratagem — needs a dead INFANTRY unit plus command points",
    "SWEG_SHADOW_ROUND2": "round-2 condition",
    "SWEG_THREAT_ALLOC": "threat allocation — piloting layer",
    "SWEG_THREAT_CHARGE_DIAG": "diagnostic instrument, not a rule",
    "SWEG_WE_DW_RANGED_FAB": "devastating-wounds fabrication removal on ranged",
    "SWEG_CULL_PICK_AWARE": "secondary card substitution — CONFIRMED rare-firing, live at N=80",
}


def main() -> None:
    fielded = collections.defaultdict(set)
    for faction in sorted(ARCHETYPES):
        for seed in range(N):
            try:
                army = build_faction_random_army("A", faction, 2000,
                                                 rng=random.Random(seed),
                                                 use_archetype=True)
            except Exception:
                continue
            for u in army.units:
                fielded[faction].add(u.profile.name)

    print(f"=== is each gate's subject ever fielded? ({N} armies/faction) ===\n")
    dead, alive, unsure = [], [], []
    for gate, faction, needle, decisive in SUBJECTS:
        names = fielded.get(faction, set())
        hits = sorted(n for n in names if needle.lower() in n.lower())
        if hits:
            alive.append((gate, faction, needle, hits))
        elif decisive:
            dead.append((gate, faction, needle))
        else:
            unsure.append((gate, faction, needle))

    print(f"--- STRUCTURALLY DEAD: {len(dead)} "
          f"(subject NEVER fielded — every recorded verdict measured nothing) ---")
    for gate, faction, needle in dead:
        print(f"    {gate:<34} {faction:<21} no '{needle}' on the table")

    print(f"\n--- SUBJECT IS FIELDED: {len(alive)} "
          f"(so the flat reading is rare-firing, not dead) ---")
    for gate, faction, needle, hits in alive:
        print(f"    {gate:<34} {faction:<21} {', '.join(hits)[:44]}")

    if unsure:
        print(f"\n--- UNVERIFIED SUBJECT: {len(unsure)} "
              f"(needle is an ability name or a guess at scope — the miss says")
        print("    nothing about the gate; identify the real datasheet first) ---")
        for gate, faction, needle in unsure:
            print(f"    {gate:<34} {faction:<21} '{needle}' matched nothing, "
                  f"but it is not a datasheet name")

    print(f"\n--- NOT UNIT-SCOPED: {len(NOT_UNIT_SCOPED)} "
          f"(fieldedness cannot settle these) ---")
    for gate, why in sorted(NOT_UNIT_SCOPED.items()):
        print(f"    {gate:<34} {why}")


if __name__ == "__main__":
    main()
