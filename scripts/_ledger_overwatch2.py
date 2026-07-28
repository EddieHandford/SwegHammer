"""Resolve the Fire Overwatch ledger entry with the CONFIRMED attribution."""
from __future__ import annotations

LEDGER = "docs/DECISION_LEDGER.md"

OLD_START = "**IF CONFIRMED**, the standing recommendation changes shape:"
NEW = """**CONFIRMED (`data/_scr_cand2_log.json`).** Candidate 1 (this gate OFF) gives
Death Guard error 14.5; candidate 2 (identical but this gate ON) gives **12.4**.
Fire Overwatch on movement is the source of the Death Guard gain — **2.1 points
toward reality on the residual that survived the counterplay campaign, the
durability audits and nine canary iterations.** Nothing else in this project's
history has moved it.

**AND IT COSTS MORE THAN IT BUYS, on the current metric.** Raw both-sides mean
absolute error: four-gate **5.46**, sc67a 5.48, candidate 1 5.56, weapon-range-off
5.93, candidate 2 **6.00**, sc68a 6.31. The gate helps Death Guard (14.5 -> 12.4),
Emperor's Children, Orks and Imperial Knights; it hurts **Tyranids +1.9**, Leagues
of Votann +2.3, Adeptus Astartes +1.7, Necrons +1.7, Chaos Knights +1.5, Chaos
Space Marines +1.4, Aeldari +1.4, T'au +1.2. Net **+0.44 raw**.

**Tyranids worst is the honest tell, and it is not a bug**: a horde that advances
every turn offers an Overwatch trigger every turn. That is faithful — and it
deepens the game's deepest under-pole. This is the THIRD independent case this
session of a provably faithful mechanic worsening calibration by amplifying an
existing pole (with weapon range on Adeptus Astartes and Kindred Hero on Leagues
of Votann).

**THE GENERALISABLE DIRECTION STANDS REGARDLESS.** The frontier entry's advice
("do NOT re-attempt symmetric play-quality levers") now has a positive
counterpart: **look for unimplemented legs of CORE rules whose trigger conditions
are asymmetric between army archetypes.** That search found, in one night, the
only lever ever to move Death Guard. The Astra Militarum result came from the
same class — a comparison operator, not smarter piloting.

**RECOMMENDATION (owner's call).** By measured error the best configuration
remains the four-gate Astra Militarum package (raw 5.46, gated 2.51). The owner
ruled "implement it all" and the tree currently carries every faithful gate; that
ruling now has a price tag — **+0.85 raw versus the Astra Militarum package
alone** — and the composition is a redistribution that fixes the two biggest poles
and breaks six mid-table factions. Both halves are defensible; the choice is
doctrine, not evidence.
"""


def main() -> None:
    src = open(LEDGER, encoding="utf-8").read()
    if "**CONFIRMED (`data/_scr_cand2_log.json`)" in src:
        print("already resolved — no change")
        return
    i = src.find(OLD_START)
    if i < 0:
        print("pending clause not found — refusing to guess")
        return
    j = src.find("\n\n## ", i)
    if j < 0:
        print("could not find end of entry — refusing to guess")
        return
    open(LEDGER, "w", encoding="utf-8").write(src[:i] + NEW + src[j:])
    print("Fire Overwatch entry resolved with confirmed attribution")


if __name__ == "__main__":
    main()
