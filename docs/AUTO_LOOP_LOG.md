# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 236 (2026-06-11) — displacement Stage 1 ADOPTED AS DEFAULT + catalogue-wide invulnerable-save repair (128 units) + nine-commit batch pushed + N=80 re-anchor gated 5.71. NEW STANDING FRAME (best yet on the honest scale).

**1. Displacement Stage 1 measured and adopted.** Built behind `SWEG_DISPLACE_FALLBACK` (fall back from
melee only when the unit's presence changes no marker outcome AND staying buys nothing AND the move has a
destination worth its Desperate Escape cost — the user-ruled stay-on-the-marker rails). The eighty-battle
paired comparison against the wave-236 anchor: **gated 6.03 → 5.96** (paired delta −0.07), decisive movers
(95% confidence intervals clear of zero) Aeldari −1.74 / Chaos Knights +1.66 / Leagues of Votann +1.42
toward target, versus Imperial Knights +1.36 / Chaos Daemons −1.94 wrong-direction. Net headline
improvement on a faithful piloting heuristic → **default flipped ON** (`5a80a4c`; legacy eager fall-back
kept byte-identical behind `SWEG_DISPLACE_FALLBACK=0`). On-arm record `data/wf_wave236_displace_on_n80.txt`.

**2. Mapper per-attack invulnerable-save repair — the wave's biggest fidelity catch.** A code-grounded
Adepta Sororitas residual audit (`docs/SORORITAS_UNDERPOLE_AUDIT.md`, 7 ranked findings) found
`_INVULN_PER_ATTACK_RE` only matched digit-first phrasing ("4+ invulnerable save"), missing the
"invulnerable save of 4+" form and the bare-digit linked-profile form — and since the conditional-invuln
path (default ON) reads ONLY `invuln_save_melee`/`invuln_save_ranged` with no legacy fallback, **128
catalogue units (120 effective) had NO invulnerable save at all**: every Terminator-armour unit across
five Space Marine codexes plus 29 of 33 Adepta Sororitas units. Fixed in `299aefc` (named-group regex +
bare-digit fallback); regen diff verified invuln-fields-only; gap count 128 → 0, orchestrator-verified
in the effective catalogue.

**3. The rest of the nine-commit batch** (all reviewed, full suite 1473 green, audit clean, demo exit 0,
pushed `1c7790c..4f9cce3` under the standing pull-request-66 authorization): officer order counts
(`33e1a67`), Forgefiend Daemonic Ordnance election corrected (`adc510e`+`d16cfba` — crits are unmodified
6s regardless of strength-versus-toughness; the old `* wound_prob` factor under-counted crits ~3× into
tough targets), Legionaries Astartes-chainsword melee basket (`9c54ed2`, A4 armour-penetration −1
verbatim), Chaos Space Marines leaders Master of Possession / Warpsmith / Dark Commune (`4f9cce3` —
Dark Commune's Faithful Flock is a real 5+ invulnerable grant; the other two are structural no-flag
entries, abilities documented as unmodelled rather than proxied).

**4. Fresh full N=80 re-anchor on `4f9cce3`: gated MAE 6.03 → 5.71** (raw 8.86, 5/22 in band). **NEW
STANDING ANCHOR: `data/_anchor_wave237_n80_log.json`.** Best frame yet on the post-list-realism honest
scale (previous best 5.74, wave 233). Movers: **Chaos Space Marines −20.9 → −18.0** (g15.52, the
leaders/Forgefiend/Legionaries/Terminator-invuln batch), **Adepta Sororitas −19.5 → −17.4** (g13.57, the
invuln repair), **Aeldari +16.5 → +14.3** (g11.15, the displacement adoption's predicted decisive mover
confirmed). Worsened: **Adeptus Custodes +17.7 (g15.03, NEW top residual)**, Necrons +15.2 (g11.96),
Imperial Knights +16.0 (g13.08 — matches the displacement on-arm's wrong-direction prediction; banked
structural, Stage 2 in build). Astra Militarum flat −17.6 (g14.42). In band (5): Thousand Sons, Votann,
Daemons, Grey Knights, Drukhari (World Eaters g0.53, Emperor's Children g0.38 just outside).

**5. Queue discovery:** the torrent-over-cannon override batch is ALREADY COMPLETE — all 15 citable
anti-tank weapon-election corrections landed as ATK-BIAS-1 entries in a prior wave (briefing-drafter
verified by direct file inspection). Queue item retired.

**Wave-238 diagnostic result (Chaos Space Marines mark-grants, read-only, landed early):** REDIRECT —
do NOT build Pactbound Zealots per-mark infrastructure as the next Chaos Space Marines lever. Grounding:
(a) no mark keywords exist anywhere in the data layer (all 21 archetype units unmarked; mapper does not
extract the BSData categoryLink mark keywords); (b) the per-mark grants fire ONLY during a successful
Dark Pact (BSData rule id `009d-9d09-08c7-82e5` verbatim — "Each time a unit with one of these keywords
gains a weapon ability as the result of a Dark Pact and does not fail the resulting Leadership test"),
and Khorne/Tzeentch grants are fully redundant with the Dark Pacts Lethal Hits the simulator already
applies — net uplift estimate 1–4 points against a −18.0 residual; (c) the loss-mode probe (24 games,
6 hardest opponents) shows Chaos Space Marines lose **69% by OUT-POSITIONING** (alive at game end,
lost on victory points; mean end survival 39%) and only 31% dead-by-combat — the same low-model-count
off-marker signature as Imperial Knights / Daemons. The Chaos Space Marines under-pole is therefore the
POSITIONAL class, not an output gap: the named levers are the displacement substrate's own-marker
direction (mass/re-task-to-empty-markers, ranked in `docs/DISPLACEMENT_SUBSTRATE_PLAN.md` future
candidates), not marks. Mark build anchors recorded in the diagnostic report should marks ever be wanted
for completeness (BSData profile ids f5e9/8ea6/5c9d/68fd/642a).

**BRANCH TRANSITION (2026-06-11 ~09:50):** Ed merged pull request 66 into `main` (merge `808f299`,
which also brought in pull request 67's five archetype unit replacements — the parked frame-changing
merge, now resolved). Old branch `claude/sim-calibration-6` deleted local + origin; clean branch
**`claude/sim-calibration-7`** created off `origin/main`. Three completed worktree builds harvested
onto it: Blood Surge squad-level sibling-death trigger (`a9cc9ee`, issue #61 — also fixed a
chip-damage false trigger and an alive-check early-return that suppressed the surge on real model
death), officer Order target-type eligibility (`9a5bd4e` — plus BSData-sourced corrections: Cadian
Castellan two Orders, Leman Russ / Rogal Dorn Commanders two Orders to SQUADRON), Adepta Sororitas
Acts of Faith per-phase (`620a586`, `SWEG_AOF_PER_PHASE` default-off pending paired A/B). Stale eval
logs (301 files) moved to gitignored `data/eval_archive/`; tracked stale logs deleted from the index.
**The pull-request-67 archetype change makes every existing anchor stale — a fresh N=80 re-anchor on
the new branch is mandatory before any keep/reject decision.** Displacement Stage 2 build still in
flight in its worktree; harvests onto the new branch when it reports.

**In-flight (wave 237):** three worktree builds dispatched — **displacement Stage 2**
(`SWEG_DISPLACE_SWARM`, charge-to-contest with the full-cluster stacked-Objective-Control rail,
default-off pending its own paired A/B vs the 5.71 anchor), **officer Order target-type eligibility**
(REGIMENT/SQUADRON/TITANIC enforcement in `code/orders.py`), **Blood Surge squad-level sibling-death
hook** (the remaining half of issue #61). After harvest: Sororitas findings 2–7 re-rank on the new frame
(finding 2 Acts of Faith one-per-phase is the leading candidate), Chaos Space Marines re-diagnosis at
−18.0 (Pactbound per-mark grants rank 4), SWEG_FIGHTALT paired re-test. Parked for a wave boundary:
merge `origin/main` (pull request 67) + the Warp Friends target refresh decision; Plasmancer Harbinger
of Destruction rebuild; mapper extract_fnp structural fix.
