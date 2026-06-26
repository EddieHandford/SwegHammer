# Next-session handover — 2026-06-26

A start-here pointer for the session that picks up after the "all the fixes"
under-pole campaign. The authoritative running log is `docs/CURRENT_STATE.md`
(head block) and `docs/DECISION_LEDGER.md`; this file is the short version plus
the recommended next moves.

## Where things stand

- **Standing anchor: `data/_anchor_sc16a_n80_log.json` — gated mean absolute
  error 3.48** (raw 6.27, nine of twenty-two factions inside the per-faction
  noise band). This is the live production frame: all adopted gates default-on.
- The "all the fixes" campaign (waves 254–259) is **done and pushed**. It built
  and screened all thirteen verified survivors of the Wahapedia-primary
  under-pole audit (`underpole-unit-audit`, run `w6adydjru`): **7 adopted,
  2 held, 3 refuted (Chaos Knights), 0 phantoms shipped.** Headline moved
  4.20 (wave 253) → 3.48; T'au Empire and Leagues of Votann brought into band.

## Branch / pull-request state (read before committing anything)

- Working branch: `claude/sim-calibration-15` (tip wave 259).
- **Pull request #82** = this campaign (waves 254–259), **stacked on
  `claude/sim-calibration-14`** (which is pull request #81, the wave-253
  tie-draw, still open).
- Merge order: **#81 first, then #82.** When both merge, fold `origin/main`
  per procedure §H and start a fresh `claude/sim-calibration-16` — do NOT keep
  stacking new waves on -15 (CLAUDE.md §14; -15 is at ~755 lines vs main, still
  under the ~1500-line / 15-commit checkpoint, but the campaign is closed).
- Do not adopt anything new to `main` until #81 (and ideally #82) merge.

## Held levers (built, faithful, cited, default-off — re-confirm, don't re-propose as fresh)

- `SWEG_AM_DUTY_AND_HONOUR` (Astra Militarum Duty and Honour order, +1 Objective
  Control): +0.55 non-decisive, 126-flip churn. Re-screen against a future
  full re-anchor before rejecting outright.
- `SWEG_VOTANN_KAHL_LETHAL` (Kahl Kindred Hero lethal-hits): −0.12 wash. The
  re-roll-1s proxy is a better-calibrated compensating error; the faithful
  lethal-hits does not beat it. Keep the proxy default.

## Refuted / stashed (do NOT re-attempt without new grounding)

- **Chaos Knights cluster** (Infernal Lance / Malefic Surge, Knight Abominant,
  War Dogs) — all three refuted. Infernal Lance is **decisively worse than the
  default Iconoclast Fiefdom (−8.66)**; Abominant and War Dogs wash. Code is in
  git stash `ck-cluster-refuted-wave259` (recoverable); full specs in
  `data/_lever_specs.json` keys 2/6/10. The Chaos Knights under-pole is
  **structural** (archetype composition or representation), not a
  detachment/ability gap. Do not re-propose Infernal-Lance-as-default without
  BOTH a fuller Malefic Surge model (it currently models only the Diabolic
  Power leg plus the mandatory self-mortal-wounds downside) AND the
  competitive-list citation the audit verifier flagged as unverifiable.

## The residuals, ranked (where the remaining gated error lives)

1. **Astra Militarum — 26.8 vs real 45.3, gated 15.27 (dominant).** The Cadian
   sticky-objective lifted it +0.9 (the first faithful lever to move it on its
   real win condition), but the durability-in-contest wall persists: cheap T3
   bodies lose contested markers while alive. The objective-control channel is
   now partly addressed; the open question is durability/scoring of mass
   infantry. This likely needs a list/representation decision (a user call), not
   autonomous lever-hunting — see the long history in
   `data/_melee_shooting_am_crack.md` and `data/_secondary_vp_diagnosis.md`.
2. **The over-pole half** — World Eaters +13.9, Emperor's Children +12.0, Chaos
   Daemons +10.5, Necrons +9.4, Death Guard +9.5, Adeptus Custodes +8.3. This
   is now the largest *addressable* chunk. The tie-draw (wave 253) showed the
   winning direction is "remove an unfaithful durable-survivor OVER-credit."
   Look for unfaithful over-credits on these specific factions (fabricated
   buffs, mis-modelled army rules, over-generous scoring) the same way the
   audit found under-credits — an "over-pole audit" is the natural next workflow.
3. **Drukhari — 44.8, gated 4.21.** The Power-from-Pain levers (wave 258)
   helped (+1.87) but it is still under; the deferred Ravager Agonising
   Suppression (needs cross-round target-side plumbing) and a fuller per-unit
   model are open.
4. **Chaos Knights — 37.5, gated 3.90 (structural, see above).**

## Recommended next move

Run an **over-pole audit** (mirror the `underpole-unit-audit` workflow but for
the +9 to +14 over-poles: World Eaters, Emperor's Children, Chaos Daemons,
Necrons, Death Guard, Adeptus Custodes) hunting unfaithful OVER-credits to
remove. That is the largest addressable lever family left and has a proven
direction (the tie-draw). Treat the Astra Militarum under-pole and the Chaos
Knights structural gap as user-decision items rather than autonomous targets.

## Screening recipe (what worked this campaign)

- Build each lever gated default-off, byte-identical when off (gate is the first
  check; all new random draws inside the gate). Prove it with a both-off
  validation arm reading **0 flips** vs the anchor.
- Screen faction-scoped: `python -m scripts.evaluate_vs_meta --use-archetype
  --battles 80 --factions "<Faction>" --log-games X.json`, then
  `python -m scripts.paired_delta data/_anchor_sc16a_n80_log.json X.json
  --scoped`. Set `PYTHONHASHSEED=0`.
- When screening a faction after earlier adoptions, **neutralise the already-
  adopted gates** (`SWEG_...=0`) so the base matches the anchor; adopt only on a
  decisive faithful win or a clear data/rules-correctness fix; re-confirm
  marginal-but-positive levers at the full re-anchor (the wave-245 lesson).
- Adopt by flipping the gate to `os.environ.get("SWEG_X","1") != "0"` (default-on,
  `=0` kill-switch), update the citation + comment prose, re-anchor.
