"""Which gun-carrying units can never Fall Back out of melee?

`strategy.pick_move_intent` gates the Fall Back branch on
`role in ("SHOOTY", "HEAVY")` (plus DUAL for Leagues of Votann). `role` comes
from `roles.classify`, whose HORDE test runs FIRST and keys on
`health == 1 and save >= 4 and total < 1.5`. So every single-wound gunline
infantry unit is labelled HORDE, is therefore not SHOOTY, and can NEVER Fall
Back — once charged it is pinned in melee for the rest of the game, unable to
shoot and unable to leave.

This is the counterplay half of the same classification collision that
`roles.combat_profile` was built to fix on the melee side.

Run: PYTHONHASHSEED=0 python -m scripts._fallback_eligibility_audit
"""
from __future__ import annotations
import collections

from code.roles import classify, combat_profile, expected_ranged_dpa, expected_melee_dpa
from code.units import UNIT_CATALOG

# Mirrors strategy.py's `_is_melee_class` test at the Fall Back branch.
def _is_melee_class(p) -> bool:
    return expected_melee_dpa(p) >= expected_ranged_dpa(p)


def main() -> None:
    stranded = []
    eligible = 0
    for key, p in UNIT_CATALOG.items():
        prof = combat_profile(p)
        if prof not in ("RANGED_ONLY", "DUAL"):
            continue  # no gun to free — Fall Back buys it nothing
        if _is_melee_class(p):
            continue  # melee-primary: staying to fight is correct (task #7)
        role = classify(p)
        if role in ("SHOOTY", "HEAVY"):
            eligible += 1
        else:
            stranded.append((p.faction or "?", p.name or key, role, prof,
                             p.health, p.save, round(expected_ranged_dpa(p), 2)))

    print("=== Fall Back eligibility: ranged-primary units ===")
    print(f"    eligible (SHOOTY/HEAVY):        {eligible}")
    print(f"    STRANDED (cannot ever leave):   {len(stranded)}")
    print()
    byrole = collections.Counter(s[2] for s in stranded)
    print("    stranded by role label:", dict(byrole))
    byfac = collections.Counter(s[0] for s in stranded)
    print()
    print("    worst-hit factions:")
    for f, c in byfac.most_common(12):
        print(f"      {f:<24} {c}")
    print()
    print("    sample stranded gunline units (faction, name, role, W, Sv, ranged damage per activation):")
    for s in sorted(stranded, key=lambda s: -s[6])[:18]:
        print(f"      {s[0]:<22} {s[1]:<30} {s[2]:<8} W{s[4]} Sv{s[5]}+ {s[6]}")


if __name__ == "__main__":
    main()
