"""Prepend the list-fidelity wave entry to docs/DECISION_LEDGER.md."""
from __future__ import annotations

PATH = "docs/DECISION_LEDGER.md"
MARK = "## THE SIMULATOR WAS NOT PLAYING THE TYRANID LIST"

ENTRY = """## THE SIMULATOR WAS NOT PLAYING THE TYRANID LIST (2026-07-26)

**The finding.** The Tyranid `Subterranean Assault` archetype cites the GW Open
Maastricht 2026 winning list in its own comment block. It does not field it. The
sourced army — Trygon carrying the Trygon Prime enhancement, three Tyranid Primes
with Lash Whips, Old One Eye, a Maleceptor, two ten-model Hormagaunt squads, a
Ravener Prime unit plus two five-model Ravener units, a Tyrannofex, Zoanthropes,
a Carnifex, a Lictor, a Neurolictor and two Biovores — shares exactly three
entries with what the builder produces. The simulator instead fields about 47
Termagants, 9 Ripper Swarms, an Exocrine and a Hive Tyrant, none of which appear
in the sourced list, and omits the Trygon, all three Primes, Old One Eye, the
Maleceptor, every Ravener, the Carnifex and both Lictors.

Every measured symptom of the number-one under-pole follows from the
substitution. `bring_it_down` 0.38 against opponents' 1.81, because with no
Carnifex, Old One Eye or Maleceptor the list's entire anti-armour capability is
two Tyrannofexes. `assassination` 0.36 against 1.19, because nothing in the
fielded list is built to reach a CHARACTER. And `cull_the_horde` 0.12 against
2.26 — the sharpest of the three — because the sourced list's chaff is two TEN-
model Hormagaunt squads, which can never reach the thirteen-model Starting
Strength that concedes the card, while the substituted Termagant squads average
about sixteen models and concede it every game. The simulator's Tyranids were
paying a tax the real army does not pay.

It also resolves the session's most confusing result. `SWEG_MELEE_CHARGE_HOLD`
doubled Tyranid charge eligibility (25.1 to 52.5 percent), more than doubled
charge connection (11 to 25 percent) and tripled Hormagaunt melee damage (1.7 to
5.1 a game), and moved the Tyranid win rate +0.34, not decisively. Getting a
gaunt swarm into combat more reliably does not fix an army whose problem is that
it is the wrong army.

**Why the engine was removed.** The template's comment justifies it: "Trygon
dropped to 0: post-CHARACTER-keyword-strip it no longer tags as a leader-host and
is redundant with Carnifex/Tyrannofex as a deep-strike wrecker." That is an
internal modelling convenience, not a real-meta observation. The Trygon is the
unit the detachment is named for and the mechanism the sourced list is built
around. Separately, the same block calls a Carnifex a "461 point minimum squad,
too expensive to seed" — a stale Stage-2 calibrated price. The vanilla catalogue
the archetype actually runs in charges 90 for one model.

**Built.** `SWEG_TYRANID_LIST_SOURCED`, default-off, byte-identical
(`4aab205fbb99635db7c607db`). Model count falls from about 113 to about 57. Two
knowing departures: Biovores have no catalogue entry and are omitted, and the
builder's random fill does not reproduce the list exactly (Maleceptor in three
seeds of six, Trygon in five of six). Full write-up in
`docs/TYRANID_LIST_FIDELITY.md`. **Not yet screened** — until it is, the size of
the effect is unknown, and every Tyranid mechanics conclusion in this session,
including this session's own, rests on a wrong input.

**Two retractions, recorded because the reasoning was wrong, not just the
number.**

1. *The melee-charge-hold blast radius.* It was recorded as 12 catalogue units.
   That is the HORDE-and-melee-only subset touched by `SWEG_MELEE_ONLY_ENGAGE`;
   the charge-hold gate keys on `MELEE_ONLY` alone and touches **132 units of
   1385**. The N=80 screen exposed the error — fifteen factions moved decisively,
   which no 12-unit change could produce. Verdict: gated mean absolute error 3.21
   to 3.63, **+0.42 worse**, a redistribution rather than a regression (Adeptus
   Astartes −4.36, Aeldari −3.65 and Chaos Space Marines −5.09 toward real;
   Genestealer Cults +12.66, World Eaters +9.59, Drukhari +8.25 away). Held
   default-off: faithful, and it costs the frame.

2. *The archetype sweep's "31 declared but never built".* Reported first as a
   systemic builder defect across 21 factions, with Emperor's Children named as
   the strongest next candidate for declaring Fulgrim and its elite core and
   fielding none of it. **Withdrawn.** Seven templates declare more than a
   2000-point army and are therefore MENUS the builder samples, not lists it must
   field — Imperial Knights 3380 points, World Eaters 2820, Aeldari 2780, Chaos
   Knights 2725, T'au 2675, Emperor's Children 2625, Grey Knights 2405. Absence
   there is by design, and it accounts for 22 of the 31 hits including every
   Emperor's Children and Imperial Knights entry. The genuine residue is nine
   entries in templates that do fit: Killa Kans, Celestian Insidiants, Allarus
   Custodians, Typhus, Pteraxii Skystalkers, Foul Blightspawn, Acolyte Hybrids
   with Hand Flamers and Serberys Sulphurhounds. The price hypothesis was tested
   and only partly supported (never-built median 125 against built 95, a ratio of
   1.32, with cheap entries skipped and dearer ones fielded), so the mechanism is
   still unknown.

**The standing lesson.** Two of tonight's three biggest errors were the same
mistake: a number measured for one thing, reused for another. The blast radius of
one gate quoted for a different gate; the absence of a menu entry read as the
absence of a list entry. Before quoting a measurement, check that the thing it
measured is the thing being claimed.

**Also built, both default-off, byte-identical, cited, awaiting screen.**
`SWEG_FALLBACK_CAPABILITY` — Fall Back eligibility tested a `roles.classify`
LABEL, `("SHOOTY","HEAVY")`, which is a body-class answer to a capability
question, so a gun-carrying unit labelled SUPPORT or HORDE could never break off
and shoot. Measured over pinned ranged-primary activations: the label excludes
55.0 percent (SUPPORT 30.8, HORDE 15.2, DUAL 9.0) and the melee-primary test
excludes 0.0 percent. Gate on, pinned gunlines that break off rise 35.1 to 87.2
percent. `SWEG_CULL_PICK_AWARE` — the Fixed-pair picker is composition-aware for
Bring It Down and Assassination but takes Cull the Horde as the FALLBACK for both
slots with no check that the enemy can concede it; across all 1386 ordered
faction pairs, 231 of 294 Cull picks (78.6 percent) face a roster with zero
qualifying squads.

**A third retraction, smaller.** An earlier reading of the pinned-gunline probe
attributed 40.8 percent of exclusions to `strategy._is_melee_class`. The branch
is `role in _fall_back_eligible_roles and not _is_melee_class(...)` and Python
short-circuits, so the role test runs first; the probe had bucketed on
`_is_melee_class` before it. The true figure is 0.0 percent. A gate that only
swapped that estimator was built, measured inert, and replaced.

"""


def main() -> None:
    s = open(PATH, encoding="utf-8").read()
    if MARK in s:
        print("already recorded - no change")
        return
    open(PATH, "w", encoding="utf-8").write(ENTRY + s)
    print("decision ledger updated")


if __name__ == "__main__":
    main()
