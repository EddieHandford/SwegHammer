"""Prepend the current-state entry for the list-fidelity wave."""
from __future__ import annotations

PATH = "docs/CURRENT_STATE.md"
MARK = "### 2026-07-26 — the input was wrong"

ENTRY = """### 2026-07-26 — the input was wrong, not just the mechanics

**Standing anchor unchanged: `sc68a`, gated mean absolute error 3.21, raw
both-sides 6.31, production digest `4aab205fbb99635db7c607db`. Nothing has been
committed. Four gates are built and default-off; three are unscreened.**

**The headline.** The Tyranid archetype does not field the list it cites. Its own
comment block names the GW Open Maastricht 2026 winning Subterranean Assault army;
the builder produces something sharing three entries with it, omitting the Trygon
that the detachment is named for along with all three Tyranid Primes, Old One Eye,
the Maleceptor, every Ravener, the Carnifex and both Lictors, and substituting
about 47 Termagants and 9 Ripper Swarms that the real list does not contain. All
three failing kill cards follow from this, and so does the otherwise-puzzling
result that doubling Tyranid charge connection moved their win rate +0.34. Built
as `SWEG_TYRANID_LIST_SOURCED`; see `docs/TYRANID_LIST_FIDELITY.md`. **Unscreened
— every Tyranid mechanics conclusion in this session rests on a wrong input,
including this session's own.**

**Screened and decided.** `SWEG_MELEE_CHARGE_HOLD`: gated 3.21 to 3.63, +0.42
worse, fifteen decisive movers. A redistribution, not a regression — Adeptus
Astartes −4.36, Aeldari −3.65 and Chaos Space Marines −5.09 move toward real while
Genestealer Cults +12.66, World Eaters +9.59 and Drukhari +8.25 move away. Held
default-off. Its blast radius had been recorded as 12 units; the true figure is
132 melee-only units of 1385, and the 12 belongs to `SWEG_MELEE_ONLY_ENGAGE`.
Fifteen decisive movers is what exposed it.

**Built, measured, awaiting a screen.**

- `SWEG_FALLBACK_CAPABILITY` — Fall Back eligibility asked a capability question
  of a `roles.classify` body-class label, so a gun-carrying unit labelled SUPPORT
  or HORDE could never break off and shoot. The label excludes 55.0 percent of
  pinned ranged-primary activations (SUPPORT 30.8, HORDE 15.2, DUAL 9.0); the
  melee-primary test excludes 0.0. Gate on: pinned gunlines that break off rise
  35.1 to 87.2 percent, and units pinned three or more activations fall 2.9 to
  0.5. The Leagues of Votann DUAL special-case at the same site was a symptom of
  the same under-inclusion. Full-matrix arm running.
- `SWEG_CULL_PICK_AWARE` — the Fixed-pair picker is composition-aware for Bring It
  Down and Assassination but takes Cull the Horde as the fallback for both slots
  without checking the enemy can concede it. Across all 1386 ordered faction
  pairs, 231 of 294 Cull picks (78.6 percent) face a roster with zero qualifying
  thirteen-model squads. Gate on drives that to zero.
- `SWEG_TYRANID_LIST_SOURCED` — above.

**Three retractions.** The charge-hold blast radius (12 → 132, above). The
pinned-gunline attribution: `strategy._is_melee_class` was reported as causing
40.8 percent of Fall Back exclusions; the branch short-circuits on the role test
first and the true figure is 0.0 percent — a gate that only swapped that estimator
was built, measured inert, and replaced. And the archetype sweep's "31 declared
but never built across 21 factions", which named Emperor's Children as the next
big candidate: **withdrawn**, because seven templates declare more than a
2000-point army and are menus the builder samples rather than lists it must field
(Imperial Knights 3380 points, Emperor's Children 2625, Grey Knights 2405 and four
others), accounting for 22 of the 31 hits. The genuine residue is nine entries in
templates that do fit — Killa Kans, Celestian Insidiants, Allarus Custodians,
Typhus, Pteraxii Skystalkers, Foul Blightspawn, Acolyte Hybrids with Hand Flamers,
Serberys Sulphurhounds — and the price hypothesis for those was tested and only
partly supported (never-built median 125 against built 95).

**The standing lesson from all three.** Each was a number measured for one thing
and reused for another: one gate's blast radius quoted for a different gate, an
exclusion counted before the test that actually excluded it, a menu's absence read
as a list's absence. Before quoting a measurement, check that what it measured is
what is being claimed.

**Next.** Screen the sourced Tyranid list scoped to Tyranids (42 of 462 cells,
about 12 minutes) as soon as the lock frees — it is the highest-value outstanding
question and it gates re-reading everything else about Tyranids. Then the Cull
pick arm. Then audit the remaining twenty templates against their cited sources,
which is where the Tyranid defect actually lived and which no mechanical sweep can
find.

"""


def main() -> None:
    s = open(PATH, encoding="utf-8").read()
    if MARK in s:
        print("already recorded - no change")
        return
    open(PATH, "w", encoding="utf-8").write(ENTRY + s)
    print("current state updated")


if __name__ == "__main__":
    main()
