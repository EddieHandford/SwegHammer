"""Register the Fire Overwatch movement-trigger finding in the DECISION_LEDGER.

Written as a script because Bash heredocs and PowerShell here-strings are both
intercepted in this environment. Idempotent.
"""
from __future__ import annotations

LEDGER = "docs/DECISION_LEDGER.md"
MARKER = "## ⭐⭐ THE FAITHFUL-ADOPTION WAVE (2026-07-25)"

ENTRY = """## ⭐⭐ THE MISSING OVERWATCH LEG (2026-07-25) — a CORE stratagem trigger that was never implemented, and a candidate answer to the counterplay frontier

**MECHANISM CONFIRMED IN CODE; ATTRIBUTION PENDING A DEDICATED ARM.**

`SWEG_OVERWATCH_MOVE` (default-off until this session) fires Fire Overwatch just
after an enemy unit **ends a Normal or Advance move**. The base simulator fired
Overwatch only after a **charge** or a **Reserves arrival**. The cited core
stratagem trigger (`simulator.fire_overwatch`, `core_overwatch.json`) is verbatim:

> "WHEN: Your opponent's Movement phase or Charge phase, just after an enemy unit
> is **set up or starts or ends a Normal, Advance, Fall Back or Charge move**."

So a leg of a **core stratagem every army in the game has** was simply not
implemented, and the missing leg is the one that fires in the MOVEMENT phase.

**WHY THIS MATTERS BEYOND ONE GATE.** The 2026-07-15 COUNTERPLAY FRONTIER entry
concluded that the number one residual (Death Guard) is not a durability floor but
a missing-counterplay gap — "the sim's WORLD lacks the COUNTERPLAY every real
opponent used to beat a durable army" — and that every internal lever failed
(canary loop nine times, target economics, staging, contest-routing, caging,
kiting) because each "improved play SYMMETRICALLY, banking to the durable side".
It named adding counterplay as the frontier.

Fire Overwatch on movement is **inherently asymmetric against durable slow
armies**: a Move 5" blob walking up the board offers a trigger every single turn,
while a fast or ranged army rarely does. It is not artificial-intelligence
quality, it is not a heuristic, and it cannot "bank to the durable side" — it is a
rule the durable army eats and the mobile army mostly avoids. That is precisely
the shape the frontier entry said was missing, and it was missing because a
trigger was unwired, not because the artificial intelligence was unsophisticated.

**THE EVIDENCE SO FAR** (both-sides raw error, `scripts/_config_compare2.py`).
Death Guard error by configuration: sc67a 14.2, four-gate 14.7, candidate
(seventeen gates minus five globals including this one) 14.5, weapon-range-off
12.6, sc68a (all gates) 12.2. Death Guard's 2.3-point gain therefore lives in the
five gates the candidate dropped; weapon range accounts for only 0.4 of it; and of
the remaining four, three are faction-local (Leagues of Votann, Emperor's
Children, Chaos Daemons) leaving `SWEG_OVERWATCH_MOVE` as the only global
candidate. CANDIDATE 2 (`data/_scr_cand2_log.json`) restores it to test this
directly.

**IF CONFIRMED**, the standing recommendation changes shape: the Death Guard
residual is attacked not by building counterplay artificial intelligence but by
finishing the implementation of a core rule — and the frontier entry's "do NOT
re-attempt symmetric play-quality levers" advice gains a positive counterpart:
**look for unimplemented legs of core rules whose trigger conditions are
asymmetric between army archetypes.**

**IF NOT CONFIRMED**, the gain belongs to one of the three faction-local gates and
each needs its own scoped arm; do not let this entry stand unqualified.

"""


def main() -> None:
    src = open(LEDGER, encoding="utf-8").read()
    if "THE MISSING OVERWATCH LEG" in src:
        print("entry already present — no change")
        return
    if MARKER not in src:
        print("MARKER NOT FOUND — refusing to guess an insertion point")
        return
    open(LEDGER, "w", encoding="utf-8").write(src.replace(MARKER, ENTRY + MARKER, 1))
    print("Fire Overwatch finding registered at ledger head")


if __name__ == "__main__":
    main()
