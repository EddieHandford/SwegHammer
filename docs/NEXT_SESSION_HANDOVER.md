# Next-session handover — 2026-06-26 (after wave 260, the over-pole audit)

A start-here pointer for the session that picks up after the over-pole
over-credit audit and removal. The authoritative running picture is the
`docs/CURRENT_STATE.md` head block and `docs/DECISION_LEDGER.md`; this file is
the short version plus the recommended next moves.

## Where things stand

- **Standing anchor: `data/_anchor_sc17a_n80_log.json` — gated mean absolute
  error 3.45** (production default = all eight wave-260 gates default-on).
  sc16a (gated 3.48) is retired but kept on disk.
- **Wave 260 is closed.** The adversarial over-pole audit
  (`docs/OVERPOLE_UNIT_AUDIT.md`) verified 27 candidate over-credits, 9
  survived, and the user authorised building Waves A+B (8 levers). All eight
  adopted default-on (fidelity-first): six passive-buff / scope narrowings and
  two fabrication removals. **The combined screen was a WASH (gated 3.48 →
  3.45).** The over-credits are real but not load-bearing for the win rate.

## The headline finding (read this before proposing more over-pole levers)

The wave-260 wash is a clean A/B confirmation that **the elite/melee over-pole
cluster is STRUCTURAL — per-model representation / durability-in-contest
scoring — not an ability-over-credit gap.** We removed the last clean
fabrications and scope errors on World Eaters, Death Guard, Chaos Daemons and
Emperor's Children and the metric did not move. This extends the decision
ledger's long-standing melee-cluster conclusion to the elite over-poles, now
proven by direct experiment rather than inference.

**Both poles are now confirmed structural:**
- Astra Militarum under-pole (gated ~15, the durability-in-contest wall).
- The elite/melee over-pole (per-model representation).

The autonomous faithful-lever families that move either pole are largely
exhausted. The remaining addressable work is the **PARKED structural /
representation re-model — a user decision** (authorise the representation work,
or accept the current fidelity floor at gated 3.45). Do NOT spin up another
ability-over-credit hunt on these factions expecting metric movement; the
audit already swept them.

## Branch / pull-request state (read before committing anything)

- Working branch: `claude/sim-calibration-16` (fresh off -15's tip `2803388`).
  Wave 260 = 8 lever commits + the adoption commit + the wave-close commit.
- **Pull request #82** (waves 254-259, `claude/sim-calibration-15`) is still
  OPEN. **#81 (wave 253) is MERGED.** No §H fold was needed when -16 was rolled
  — `origin/main`'s only delta over -15 is the #81 merge commit whose content
  -15 already carries (`git diff` vs the merge-base is empty). sc17a is valid.
- Wave 260 is committed locally on -16, **NOT pushed** (no user "go" yet). When
  #82 merges, fold `origin/main` per procedure §H and re-confirm the anchor.

## Follow-ups carried from wave 260 (cited in the audit doc)

- **Daemonic Invulnerability** (`SWEG_DAEMONS_INVULN_FAITHFUL`) gate-on currently
  spends the command point for ZERO effect — adopted as net-more-faithful than
  the removed flat-4+-for-the-round over-credit, but the real rule is a reactive
  single-failed-invulnerable-save re-roll. Build that re-roll mechanism and make
  the stratagem fire reactively (so no command point is wasted).
- **Typhus Destroyer Hive** (`SWEG_DG_TYPHUS_MELEE_ONLY`) now applies a melee-only
  Feel No Pain proxy; the real rule is a melee-only −1-to-Hit on the attacker.
  Build the target-side hit-penalty when the leader-aura layer can express it.
- **Wave C — HELD, not built:** Adeptus Custodes Arcane Genetic Alchemy
  (`docs/OVERPOLE_UNIT_AUDIT.md` rank 9) — narrow the Feel No Pain to mortal
  wounds only; needs a scoped paired A/B before adopting (command-point
  reallocation risk).

## Recommended next move

The over-pole ability-fidelity avenue is exhausted (wave 260 swept it). The two
genuine remaining frontiers are both **user decisions**, not autonomous
lever-hunting:

1. **Authorise the structural / representation re-model** (the parked work that
   would move BOTH poles — the per-model representation limit and the
   durability-in-contest scoring). This is the only thing left that can close
   the gated 3.45 → 2.0 target. It is frame-level and was reserved for a user
   call. If the user greenlights it, scope a diagnostic-first plan.
2. **Accept the current fidelity floor at gated 3.45** and pivot to Stage 2
   (the points-equation fit), treating the sim as faithful-enough. Note Stage 2
   outputs are provisional until Stage 1 converges (decision ledger PARKED).

If neither is chosen, the thin autonomous options are: the two wave-260
follow-ups above (small fidelity builds, metric-neutral by construction); a
vibe-code housekeeping checklist item (procedure §Cleanup, due at this branch
checkpoint); or the held levers from prior waves (Astra Militarum
Duty-and-Honour, Votann Kahl lethal-hits — both washed, re-confirm only at a
future re-anchor).

## Prior structural residuals (unchanged, carried for reference)

- **Astra Militarum — gated ~15, the dominant residual.** Durability-in-contest
  wall; cheap T3 bodies lose contested markers while alive. Needs the
  representation decision, not lever-hunting (`data/_melee_shooting_am_crack.md`,
  `data/_secondary_vp_diagnosis.md`).
- **Chaos Knights — under-pole, structural** (composition / representation; the
  wave-259 detachment/ability cluster was fully refuted and stashed
  `ck-cluster-refuted-wave259`).
- **Drukhari — under, partially addressed** by the wave-258 Power-from-Pain work;
  the deferred Ravager Agonising Suppression needs cross-round target plumbing.
