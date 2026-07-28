"""Which decision sites ask a CAPABILITY question of roles.classify's label?

`roles.classify` returns ONE string that mixes two independent axes:

    capability : SHOOTY / MELEE / DUAL      - what the unit can do
    body class : HORDE / HEAVY / SUPPORT    - what the unit is made of

and resolves the collision with an ordered chain whose HORDE test runs first
(health == 1 and save >= 4 and total < 1.5) and whose SUPPORT test runs second
(total <= 0.4). So a unit's capability is SILENTLY DROPPED whenever its body
class matches first. Two defects found this way already:

  * melee-only single-wound units never take ENGAGE intents (label HORDE, never
    MELEE)                                        -> roles.combat_profile
  * gun-carrying units can never Fall Back out of melee (label SUPPORT or HORDE,
    never SHOOTY)                                 -> SWEG_FALLBACK_CAPABILITY

This sweeps every site that branches on a classify label and reports which ones
test a CAPABILITY value (SHOOTY / MELEE / DUAL) — those are the sites where a
body-class label silently wins — versus which test only body class.

For each capability-testing site it also counts how many catalogue units are
MISCLASSIFIED for that question: units whose `combat_profile` says they have the
capability the site is looking for, but whose label says otherwise.

Run: PYTHONHASHSEED=0 python -m scripts._role_label_misuse_audit
"""
from __future__ import annotations
import collections
import re

from code.roles import classify, combat_profile
from code.units import UNIT_CATALOG

FILES = ["code/strategy.py", "code/simulator.py", "code/balancer.py",
         "code/equilibrium.py", "code/orders.py", "code/army_builder.py"]

CAPABILITY = {"SHOOTY", "MELEE", "DUAL"}
BODY = {"HORDE", "HEAVY", "SUPPORT"}

# A label test looks like: role == "MELEE", role in ("SHOOTY","HEAVY"),
# _role != 'DUAL', classify(p) == "HORDE" ...
PAT = re.compile(
    r"""(?P<lhs>[A-Za-z_][\w.\[\]()'"]*)\s*(?P<op>==|!=|\sin\s|\snot\s+in\s)\s*"""
    r"""(?P<rhs>\(?[^:\n]*?["'](?:SHOOTY|MELEE|DUAL|HORDE|HEAVY|SUPPORT)["'][^:\n]*?\)?)""")


def _labels(text: str) -> set:
    return set(re.findall(r"""["'](SHOOTY|MELEE|DUAL|HORDE|HEAVY|SUPPORT)["']""", text))


def main() -> None:
    sites = []
    for path in FILES:
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except FileNotFoundError:
            continue
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith("#") or s.startswith('"') or s.startswith("'"):
                continue
            for m in PAT.finditer(line):
                lhs = m.group("lhs")
                # only count tests against a role-ish variable
                if not re.search(r"role|_rl|klass|clazz|label|classify", lhs, re.I):
                    continue
                labs = _labels(m.group("rhs"))
                if not labs:
                    continue
                sites.append((path, i, s[:104], labs))
                break

    cap_sites = [s for s in sites if s[3] & CAPABILITY]
    body_sites = [s for s in sites if not (s[3] & CAPABILITY)]

    print("=== sites branching on a roles.classify label ===")
    print(f"    total label tests found:                  {len(sites)}")
    print(f"    test a CAPABILITY value (at risk):        {len(cap_sites)}")
    print(f"    test only body class (correct by design): {len(body_sites)}")
    print()

    # How many catalogue units does each capability question misread?
    miss = collections.Counter()
    for key, p in UNIT_CATALOG.items():
        lab = classify(p)
        prof = combat_profile(p)
        if lab in BODY:
            if prof in ("MELEE_ONLY", "DUAL"):
                miss["melee capability hidden by a body-class label"] += 1
            if prof in ("RANGED_ONLY", "DUAL"):
                miss["ranged capability hidden by a body-class label"] += 1
    print("    catalogue units whose capability its label hides:")
    for k, v in miss.most_common():
        print(f"      {v:5d}  {k}")
    print()
    print("    CAPABILITY-testing sites — each is a candidate defect:")
    for path, ln, src, labs in cap_sites:
        print(f"      {path}:{ln}")
        print(f"          {sorted(labs)}  {src}")


if __name__ == "__main__":
    main()
