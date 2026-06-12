# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 244 (2026-06-12, CLOSED) — first batch-screen wave under the new user-set methodology: three levers screened against one shared anchor, all three ADOPTED, defaults flipped together, one N=80 re-anchor — gated 5.90, the best honest frame yet (−0.80 versus the wave-243 anchor).

**1. Methodology (user-set this wave, now standing).** Re-anchors are the expensive runs, so the
wave shape changed: every lever built gated default-off, independent forty-battle paired screens
all reusing ONE off-arm anchor log, one combined forty-battle run of the keeper set before any
flip (levers do not compose additively), then all adopted defaults flipped together and a single
eighty-battle re-anchor on the flipped frame. Encoded as `AUTO_LOOP_PROCEDURE.md` §I together
with the confirmed operating shape (three to five file-disjoint levers per wave, next-wave build
agents pipelined inside the current wave's evaluation windows). Separately user-directed this
wave: vibe-code cleanup is now a standing housekeeping element (procedure "Vibe-code
housekeeping" subsection; research report at `docs/research/vibe_code_cleanup_research.md` — the
repo inventory found eighty-three `SWEG_` gates with only fourteen explicit defaults, roughly
fifty stale one-shot diagnostic scripts, and roughly one hundred pre-convention log files; one
checklist item executes per branch checkpoint, starting at the `sim-calibration-11` roll).

**2. Lever 1 — leader-stack seed priority (`SWEG_SEED_LEADERS`).** The archetype seed walk now
seeds the template's documented real-meta leader stack before spending the budget on the spine
(the wave-243 finding: the `(-count, -cost)` walk dropped two of Astra Militarum's three
officers). Fourteen-faction seed-fraction overrides re-derived as a strict superset of the
gate-off realization; menu factions scoped out (their builds stay byte-identical). Screened ALONE
it crashed Astra Militarum to gated 30.44 — three officers in the list with no piloting are dead
points — exactly the non-additivity case the combined-run rule exists for: an independent-sum
read would have wrongly rejected the lever.

**3. Lever 3 — officer attachment and stay-near piloting (`SWEG_OFFICER_FOLLOW`).** Astra
Militarum officer entries added to `code/leaders.py` (registry append at import, ~1388) plus a
stay-near-squads movement hook in `code/strategy.py` (~3006), so seeded officers hold aura range
instead of drifting eight to fourteen inches off the line by round 3. Combined 1+3 screen versus
the wave anchor: gated 7.22 → 7.20 (wash), with the lever-1 Astra Militarum crash recovered by
−5.27. Adopted on fidelity: the built list now matches the template's documented composition and
the officers actually play their role.

**4. Lever 2 — melee weapon-keyword mode routing (data-driven, no gate).** Ranged-only weapon
keywords (anti-keywords, devastating wounds, twin-linked) contaminated melee profiles on 242
units, granting fabricated melee output. Mode routing now keys each keyword to the profile that
actually carries it. Screen on the combined frame: gated 7.20 → 6.77 (−0.43); toward target —
Adeptus Custodes −4.03, Adeptus Mechanicus −3.40, Death Guard −3.16, Necrons −2.23, Orks −2.04,
Genestealer Cults −2.03, Leagues of Votann −1.49; away — Emperor's Children +2.93, Drukhari
+2.66, Imperial Knights +2.21, World Eaters +2.16 (melee factions losing fabricated keyword
output, the faithful direction). Thousand Sons raw narrowed 5.4 → 3.8, consistent with the
Mutalith devastating-wounds contamination hypothesis.

**5. Flip, fold, re-anchor.** Defaults flipped together (`2c5a7c4` — both gates default "1",
`=0` is the kill-switch, off-arm tests pinned explicitly since unset now means on); pull request
74 merged upstream and folded back as `fa44c15` with zero content difference (anchors stayed
valid); full test suite 1632 passed; demonstration battle clean. Eighty-battle re-anchor on the
flipped frame: **gated 5.90, raw 9.19, 3/22 in band — `data/_anchor_sc10a_n80_log.json` promoted
as the standing anchor.** Versus the sc9c anchor (6.70): −0.80, the best honest-frame headline
yet. Decisive movers at eighty battles: Adeptus Custodes 20.05 → 8.97, Necrons 9.72 → 4.04,
Genestealer Cults 4.71 → 0.30, Chaos Knights 6.53 → 1.30, Grey Knights 7.38 → 4.91, Leagues of
Votann 3.80 → 1.81 all toward target; Astra Militarum 19.01 → 22.97 away (the accepted fidelity
cost of the officer frame — remaining-gap diagnostic in flight), Imperial Knights 5.80 → 9.21
and Emperor's Children 12.05 → 14.44 away. In-band count 5 → 3 (Chaos Space Marines at 1.10 and
Adepta Sororitas at 0.35 slipped marginally out; Adeptus Astartes, T'au, Thousand Sons in).

**6. Wave 245 pipelined inside the eval windows (per §I).** (a) Fight-alternation variant (b) —
round-scoped once-per-round melee alternation — BUILT and held (`a5754c9` on its worktree
branch; cherry-pick onto `sim-calibration-11`; the commit bundles four pre-existing Astra
Militarum citation-debt fixes to review at pick time). The old "genuinely refuted" tag covered
only variant (a) full-doubling, and that refutation frame had melee structurally disabled.
Adoption, if the screen supports it, needs the explicit argument that bounding fight frequency
below the real rule compensates for the sim round model lacking Fall Back disengagement. (b) A
second planned lever — conditional per-attack-type invulnerable saves — was CANCELLED at
briefing validation: it already landed at wave 217 and was repaired at wave 236; a stale memory
file said otherwise and the validated-briefing prep step caught it before a build was wasted.
(c) The Astra Militarum remaining-gap diagnostic was re-dispatched (the original agent died
silently; its worktree held no work in progress) and RETURNED during this close. Confirmed, both
grounded in code and the BSData cache: Lord Solar's stay-near host set (`code/leaders.py` ~1444)
is infantry-only, so he drifts mid-table while the SQUADRON artillery he could order three times
a round sits at deployment outside his six-inch aura; and the Cadian Heavy Weapons Squad — nine
of ten built armies — loses its mortar's verbatim "Blast, Heavy, Indirect Fire" keyword to the
mapper's majority-vote flag aggregation across a four-weapon loadout (an overrides-only fix).
Refuted: Basilisk and Manticore indirect fire work correctly; defensive-order timing is minor;
the remembered Wyvern misidentification is real in code but the Wyvern is not in the archetype
template. Both confirmed levers are file-disjoint from the fight-alternation build — wave 245
fields all three.

**7. Wave close and checkpoint.** Branch past the hard size cap (seven commits, ~1,730
reviewable lines before this close): checkpoint pull request opens for `claude/sim-calibration-10`
after this close; `claude/sim-calibration-11` rolls off its head per the
merge-wait-must-not-bottleneck directive, and the first standing vibe-cleanup item (the scripts
archive pass) executes at the roll.
