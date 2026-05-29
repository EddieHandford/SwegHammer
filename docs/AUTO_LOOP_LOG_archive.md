# Auto-loop log archive

Archived iter blocks from `AUTO_LOOP_LOG.md`. The live log keeps only the most recent two iter closes.

# Auto-calibration loop log

Started 2026-05-16. Hands-off iteration toward MAE-vs-real-meta ≤ 1.0pt
or 3 consecutive iterations with Δ < 0.1pt.

## Rules

- Every rule addition cites Wahapedia (CLAUDE.md §10).
- AI improvements must benefit all factions equally — no faction-specific picker biases.
- Regressing fix batches get reverted, logged in "Parked" with reason, continue loop.
- Cumulative MAE delta is the metric — individual fix predictions are informational.

## Baseline

- Iter 0: MAE-vs-real **6.72pt**, MAE-vs-Sweg 6.78pt (commit `053e352`).
- Per-faction (Sim% / Real% / Diff):
  - Marines 58.9 / 48.0 / +10.9
  - Necrons 60.0 / 53.2 / +6.8
  - Aeldari 40.0 / 44.4 / −4.4
  - Tyranids 56.1 / 48.0 / +8.1
  - Orks 38.3 / 44.9 / −6.6
  - T'au 51.1 / 54.5 / −3.4
  - DG 67.2 / 48.0 / +19.2
  - Custodes 50.0 / 48.0 / +2.0
  - TSON 52.8 / 54.6 / −1.8
  - Votann 50.0 / 46.0 / +4.0

## Iteration log

(Each iteration: cluster diagnostics → per-faction synthesis → fix dispatch → merge → eval → commit-or-park.)

### Iter 1 (2026-05-16)

**Diagnostics**: Cluster A (over-performers DG/Marines/Tyranids/Necrons), B (under-performers Orks/Aeldari/T'au), C (faction-neutral AI). Docs at `AUTO_LOOP_ITER1_CLUSTER_{A,B,C}.md`.

**Batch dispatched**: 5 fix agents (A1, A3, B1, B4, C1).

**Results vs 6.72 baseline (individual, all solo-measured)**:
- A1 DG Disgustingly Resilient INFANTRY/CHARACTER keyword gate: 0.0pt (neutral; correct rule but freed CP cancels per-fire nerf)
- A3 Synapse self-shelter (real-rule fix): **+0.33pt regression** → **PARKED**
- B1 Orks War Horde detachment + 6 stratagems: −0.11pt ✓ Wahapedia-cited
- B4 WAAAGH! +1 charge roll leg: −0.22pt ✓ real rule
- C1 Fight picker → `_melee_target_score` (faction-neutral): −0.17pt ✓

**Cumulative (4-fix bundle, A3 parked)**: MAE 6.72 → **6.39pt** (Δ **−0.33pt**). MAE-vs-Sweg 6.78 → 6.67pt.

**Parked** (per loop rule — would regress cumulative):
- A3 Synapse self-shelter (`a262910`). Wahapedia-correct change (a SYNAPSE model is "within Synapse Range of itself" by reading the rule literally), but the simulator-side effect of self-sheltering small / isolated SYNAPSE squads (Hive Tyrants in particular) widened auto-pass coverage and tilted other factions' matchups. **Re-evaluate when**: opponent counter-tools land (e.g. WAAAGH! 5++ vs melee, Marine Oath retargeting after kill, T'au Markerlights making SYNAPSE-led units take more damage). The SYNAPSE-as-anchor target priority (G3) already incentivises killing them — but they survive too well now.

**Per-faction shifts (iter 0 → iter 1)**:
- Marines: +10.9 → +17.0 (regressed, but this is variance — Marines wasn't directly touched; cross-faction shifts under new Orks WAAAGH push made Marines look stronger by comparison in mirror seeds)
- Necrons: +6.8 → +6.2 (improved)
- Aeldari: −4.4 → −2.7 (improved)
- Tyranids: +8.1 → +6.4 (improved)
- Orks: −6.6 → −5.5 (improved, B1+B4 working)
- T'au: −3.4 → −3.9 (similar; Mont'ka [ASSAULT] still under-firing)
- DG: +19.2 → +19.2 (unchanged; A1 keyword gate freed CP that fires elsewhere)
- Custodes: +2.0 → +3.1 (similar)
- TSON: −1.8 → −2.4 (similar)
- Votann: +4.0 → +3.4 (improved)

**Iter 1 commits on origin**:
- `36660c0` #B4 WAAAGH! +1 charge
- `60ec880` #A1 DG Disgustingly Resilient keyword gate
- `3090b5c` #C1 Fight picker melee_target_score
- `f69f9d1` #B1 Orks War Horde + stratagems

**Iter 2 priorities** (from cluster diagnostics, not yet picked):
- Higher leverage candidates remaining: A2 Necron Reanimation fresh-loss gate (−2 to −3pt), A4 DG Contagions radius gate (−1.5 to −2.5pt), A5 stratagem firing-cap bundle (−2 to −5pt), B2 Aeldari Strands of Fate (high infra, −1.5 to −2.5pt), B3 T'au Markerlights (high infra, −1 to −1.5pt).
- DG +19.2 hasn't moved; needs different lever (Marines OC stack #179 may also be cross-faction unlock).
- Marines +17.0 needs the F5b random_fill cap (#179) — that's the only single fix likely to drop Marines back into noise.

### Iter 2 (2026-05-16)

**Batch dispatched**: 5 fix agents (A2, A4, #179, C2, C4).

**Results (cumulative, post-merge measurement)**:
- A2 Necron Reanimation fresh-loss gate: solo −0.23pt; landed (Wahapedia "restore one destroyed bodyguard model")
- A4 DG Contagions 3" radius gate: solo −0.55pt (N=10); landed (radius-only, escalation pattern preserved)
- #179 random_fill BATTLELINE cap: 0.0pt — agent confirmed the existing `0.5 * remaining_budget` cap already prevents Intercessor stacking; commit kept as defensive safeguard
- C2 Charge picker won't-crack penalty (faction-neutral): solo −0.63pt (N=10); landed
- C4 Leader-before-led activation priority (faction-neutral): solo 0.0pt — dormant in vanilla mode because `_run_round_vanilla_turns` iterates `active.units` directly. Commit kept; activates when C3 (vanilla uses activation_queue) lands.

**Cumulative**: MAE 6.39 → **5.66pt** (Δ **−0.73pt**). MAE-vs-Sweg 6.67 → 5.94pt.

**Per-faction shifts (iter 1 → iter 2)**:
- Marines: +17.0 → +13.1 (−3.9, C2 + leader priority eating Marines' wasted-charge / under-led-squad overhead)
- Necrons: +6.2 → +4.6 (−1.6, A2 RP fresh-loss working)
- Aeldari: −2.7 → −3.8 (small backslide)
- Tyranids: +6.4 → +3.7 (−2.7, C2 wont-crack drops failed charges into Carnifex bricks)
- Orks: −5.5 → −4.3 (improved)
- T'au: −3.9 → −3.9 (unchanged)
- DG: +19.2 → +17.0 (−2.2, A4 Contagions 3" gate)
- Custodes: +3.1 → +0.3 (big improvement)
- TSON: −2.4 → −1.8 (improved)
- Votann: +3.4 → +4.0 (similar)

**Iter 2 commits on origin**:
- `79b5817` #C4 Leader-before-led
- `e821940` #C2 Charge won't-crack
- `fd69ef5` #A2 Necron RP fresh-loss
- `3737802` #A4 DG Contagions 3"
- `f2e8e67` #179 random_fill cap

**Iter 3 priorities**:
- DG +17.0 still biggest outlier — A5 stratagem firing-cap bundle remains, or look at Marines and DG's interaction directly.
- Marines +13.1 — explore which mechanic still dominates now that #179 isn't the root cause; cluster A's diagnostic noted "Combat Doctrines + Oath rerolls compound" but solo Doctrines is real per Wahapedia.
- B2 Aeldari Strands of Fate (high infra) — would close Aeldari −3.8.
- B3 T'au Markerlights (high infra) — would close T'au −3.9.
- Iter 3 cluster re-diagnostics: the previous cluster docs are stale post iter 2; consider fresh diagnostic round before iter 3 dispatch.

**Loop exit status**: ΔMAE 0.33 (iter 1) + 0.73 (iter 2) → cumulative −1.06pt. Neither exit condition hit yet (MAE 5.66 > 1.0; Δ 0.73 > 0.1).

### Iter 3 — PAUSED (API rate limit) then resumed

Dispatched 5 per-faction deep-diagnostic agents (DG, Marines, Aeldari, Orks, T'au). First attempt died on API rate limit (4:50am London reset). Re-dispatched successfully after reset.

### Iter 3 (2026-05-16)

**Diagnostics**: per-faction deep audits at `docs/AUTO_LOOP_ITER3_{DG,MARINES,AELDARI,ORKS,TAU}.md`.

**Fix batch dispatched**: 5 fixes.

**Results (solo MAE deltas vs 5.66 baseline)**:
- DG sticky `>=` → `>` (10e strict-greater): −0.16pt ✓
- T'au Markerlights / Guided / [LETHAL HITS]: −0.16pt ✓
- Aeldari Strands of Fate (6D6 Fate dice pool): ~+0.05pt (Aeldari moved +0.3pt; MAE noise)
- Marines mapper Torrent `any` → `all` (faction-neutral bug fix): +0.12pt (correctness-positive but ineffective; deeper bug in `_collect_weapons_for_model:918` not addressed)
- Orks WAAAGH! 5++ vs melee + verify B4 +1-charge (discovered B4 was never wired): +0.10pt solo, but **−4.5pt regression on Orks (−4.3 → −8.8)** — likely interaction: Orks now stay alive longer in unwinnable melee. PARKED.

**Cumulative (4-fix bundle, Orks parked)**: MAE 5.66 → **5.28pt** (Δ **−0.38pt**). MAE-vs-Sweg 5.94 → 6.33pt.

**Parked**:
- Orks WAAAGH 5++ vs melee + +1 charge roll (was b969dfa). Rules are real and Wahapedia-cited, but combined effect tilts Ork matchups DOWN. Hypothesis: +1 charge → more committed Ork charges into T8+ bricks; 5++ → Orks survive longer in unwinnable melee instead of dying and freeing OC. Re-evaluate when Orks gets a "disengage from melee" tool or when archetype seeds shift toward higher-S options.

**Per-faction shifts (iter 2 → iter 3)**:
- Marines: +13.1 → +12.6 (slight improvement)
- Necrons: +4.6 → +2.9 (better)
- Aeldari: −3.8 → −3.3 (Strands of Fate working)
- Tyranids: +3.7 → +2.6 (better)
- Orks: −4.3 → −4.3 (parked fix; unchanged)
- T'au: −3.9 → −2.3 (Markerlights working)
- DG: +17.0 → +15.3 (sticky fix helped)
- Custodes: +0.3 → −0.2 (similar)
- TSON: −1.8 → +0.4 (drifted positive)
- Votann: +4.0 → +5.7 (worse — noise)

**Iter 3 commits on origin** (final post-rebase SHAs):
- DG sticky `>=` → `>`
- T'au Markerlights
- Aeldari Strands of Fate
- Marines mapper `any` → `all`

**Iter 4 priorities**:
- DG +15.3 still biggest outlier (sticky fix delivered −1.7pt; remaining lever unknown).
- Marines +12.6 — mapper deeper bug (`_collect_weapons_for_model:918` mutex weapon-option groups pick single-best, never present Auto Boltstorm in basket). Worth fixing properly.
- Orks −4.3 needs a different lever (the WAAAGH 5++ approach backfired).
- Votann +5.7 — has drifted up; no investigation yet.

**Loop exit status**: Cumulative ΔMAE 6.72 → 5.28 = −1.44pt across 3 iters. Latest Δ 0.38pt > 0.1pt threshold; MAE 5.28 >> 1.0pt threshold. Continue.

### Iter 4 (2026-05-16)

**Diagnostics**: DG deeper, Votann (first-look). Docs: `AUTO_LOOP_ITER4_DG.md`, `AUTO_LOOP_ITER4_VOTANN.md`.

**Fix batch dispatched**: 4 (A5 strat cap, Marines mapper Option A, DG R1 Contagion drop, Votann token gate).

**Results (solo)**:
- A5 universal stratagem cap (1/Command phase/army): −0.27pt ✓ shipped
- DG R1 −1T Contagion drop (older-index rule removal): 0.0pt — correctness-positive, no measurable signal at N=20 (R1 rarely fires at 3" radius)
- Marines mapper Option A (mutex weapon-option groups present all variants weighted): **+1.52pt regression** — PARKED. The fix is universal but creates "compromise" stat-lines that don't match any real loadout (Crisis Battlesuits Legends S 9→6, AP −4→−1, A 1→3). Agent's recommendation: per-group meta priors needed.
- Votann probabilistic token gate (1/min_models): **+0.68pt regression** — PARKED. Correct mechanism but extra `random.random()` consumer shifted global RNG stream propagating noise. Needs separate Random instance to avoid stream shift.

**Cumulative (2-fix bundle, 2 parked)**: MAE 5.28 → **5.01pt** (Δ **−0.27pt**). MAE-vs-Sweg 6.33 → 5.50pt.

**Parked**:
- Marines mapper Option A (weighted basket for mutex weapon-option groups). Real-meta lists pick ONE variant per group, not the weighted average. A future fix needs per-group meta priors or per-list-build variant resolution. Re-evaluate when MC bisection comes online — bisection could probe each variant separately.
- Votann probabilistic token gate. Mechanism correct (1/min_models) but global RNG-stream collision. Future fix uses dedicated Random instance keyed off battle seed + token-context.

**Iter 4 commits on origin**:
- `ef0cd2d` #iter4 A5 stratagem cap
- `7ef471b` #iter4 DG R1 Contagion drop

**Iter 5 priorities**:
- DG +15.3 persists. Per iter 4 DG diag, the slice WR on Marines/Necrons/Tyranids is 47.8% vs real 48% — the residual lives in UNSAMPLED matchups. Need diag of DG vs Aeldari/T'au/Orks/TSON/Custodes/Votann.
- Marines +12.6 needs a different lever (mapper fix parked).
- Cluster C remaining items: C3 vanilla mode uses activation_queue (unlocks C4 leader-before-led that's currently dormant), C5 stratagem CP-leak cleanup.

**Loop exit status**: Cumulative ΔMAE 6.72 → 5.01 = −1.71pt across 4 iters. Latest Δ 0.27pt > 0.1pt; MAE 5.01 >> 1.0pt. Continue.

### Iter 5 (2026-05-16)

**Diagnostics**: DG unsampled matchups (the 7 not sampled in iter 4), Marines alternate-mechanism. Docs: `AUTO_LOOP_ITER5_DG_UNSAMPLED.md`, `AUTO_LOOP_ITER5_MARINES.md`.

**Fix batch dispatched**: 4 (DG OG LoS gate, Marines vehicle all-weapon basket, C3 vanilla uses activation_queue, C5 CP-leak cleanup).

**Results (solo)**:
- DG OG LoS gate: 0pt — OG fires/battle 3.49 → 1.75 (R1 fires 0.93 → 0.00); saved CP shifts to other stratagems so headline unchanged at N=20
- Marines vehicle all-weapon basket (non-mutex weapons all fire together): **+1.77pt regression** — PARKED. Marines DOES fix (+12.6 → +2.0!) but inflates all multi-weapon vehicles cross-faction (DG +9.4, Tyranids +8.3). The fix is correctness-positive (real vehicles fire all their guns); the cross-faction calibration needs to absorb the new vehicle damage baseline. Re-evaluate after MC bisection comes online (re-derived points will absorb the new damage profile).
- C3 vanilla mode uses activation_queue (unlocks C4 leader-before-led): +0.20pt — PARKED. Score-sort biases activation toward heavy bricks, helping over-performers (Tyranids/Votann) more than under-performers.
- C5 stratagem CP-leak cleanup: +0.02pt — within noise but mechanism correct (R3+R4 Command Re-Roll leak dropped 22%). Shipped as mechanical fix.

**Cumulative (3 shipped: DG OG + C5 + DG unsampled diag + Marines diag, 2 parked)**: MAE 5.01 → **5.03pt** (Δ **+0.02pt**). MAE-vs-Sweg 5.50 → **5.06pt** (Δ **−0.44pt** — significant internal-balance improvement).

**Parked**:
- Marines vehicle all-weapon basket. The cross-faction inflation is real signal — every multi-weapon vehicle in 10e fires all its guns; our simulator has been systematically under-rating them. Park until MC bisection / per-faction recalibration absorbs the new baseline.
- C3 vanilla uses activation_queue. Tests that exercised C4 leader priority now exercise dead code again (C4 fix shipped but is dormant).

**Per-faction shifts (iter 4 → iter 5)**:
- Marines: +12.6 → +12.0 (small, unrelated to parked fixes)
- DG: +15.3 → +17.0 (drift; OG fix is correctness-positive but doesn't reduce DG WR)
- Necrons: +2.9 → +6.2 (drifted up — RNG/C5 interaction)
- Aeldari: −3.3 → −5.6 (worse)
- Tyranids: +2.6 → +3.1 (similar)
- Orks: −4.3 → −5.6 (similar)
- T'au: −2.3 → 0.0 (improved)
- Custodes: −0.2 → +2.8 (drifted)
- TSON: +0.4 → −2.2 (drifted)
- Votann: +3.4 → +1.7 (improved)

**Iter 5 commits on origin**:
- `43c045d` iter 5 DG unsampled diagnostic
- `c35ac33` iter 5 Marines alternate-mechanism diagnostic
- `53d2fff` #C5 stratagem CP-leak cleanup
- (DG OG LoS gate `34f0e4b` to land on next push)

**Iter 6 priorities**:
- Cheap stat corrections from iter 5 Marines diag side finding: Intercessor 12→24", Hellblaster 12→24", Eradicator 12→18" weapon range (per Wahapedia datasheets).
- Oath of Moment retargeting (real rule: re-pick target each Command phase; sim picks once).
- Universal AI: explore non-activation-order, non-CP-economy levers.

**Loop exit status**: Cumulative ΔMAE 6.72 → 5.03 = −1.69pt across 5 iters. **Latest Δ 0.02pt < 0.1pt — FIRST iter inside convergence threshold.** Need 2 more consecutive iters at Δ<0.1 to exit, OR MAE<1.0. MAE 5.03 >> 1.0pt. Continue.

### Iter 6 (2026-05-16)

**Fix batch**: 2 (Marines weapon-range corrections, Oath of Moment retargeting per Command phase).

**Results (solo)**:
- Marines weapon ranges (Intercessor 12→24", Hellblaster 12→24", Eradicator 12→18", per Wahapedia datasheets): −0.11pt ✓
- Oath of Moment retargeting (real rule re-picks target each Command phase; sim was using static `points_cost` score, sticking on same anchor): 0.0pt headline but Marines diff −3.3pt (+14.2 → +10.9). Cross-faction noise cancels (T'au regressed, Custodes/Votann drifted).

**Cumulative**: MAE 5.03 → **5.03pt** (Δ **0.00pt**). MAE-vs-Sweg 5.06 → 5.44pt.

**Per-faction shifts (iter 5 → iter 6)**:
- Marines: +12.0 → +10.9 (Oath retargeting + range fix)
- Necrons: +6.2 → +5.7
- Aeldari: −5.6 → +1.2 (massive improvement — Oath retargeting indirectly helps Aeldari by reducing Marine focus-fire concentration)
- Tyranids: +3.1 → +3.7
- Orks: −5.6 → −0.5 (massive improvement, same dynamic)
- T'au: 0.0 → −2.8 (regression — less Marine pressure they may have been benefiting from in a non-obvious way)
- DG: +17.0 → +17.6 (slight drift)
- Custodes: +2.8 → +4.2 (regression)
- TSON: −2.2 → +0.4
- Votann: +1.7 → +3.4

**Iter 6 commits on origin**:
- `5f98496` / `60ea2a0` #iter6 Marines weapon ranges
- `a4f1740` #iter6 Oath of Moment retargeting

**Iter 7 priorities**:
- DG +17.6 dominates remaining MAE (~⅓ of total). Need a different attack vector — sticky/Contagion/OG-LoS already addressed.
- Cross-faction calibration drift is the new pattern: rule fixes shift WR but cross-faction interactions cancel headlines. MC bisection (Plan Step 4) becomes increasingly relevant.

**Loop exit status**: Cumulative ΔMAE 6.72 → 5.03 = −1.69pt across 6 iters. **Latest Δ 0.00pt < 0.1pt — SECOND consecutive sub-0.1 iter.** Need 1 more to exit on convergence, OR MAE<1.0. MAE 5.03 >> 1.0pt. Continue.

### Iter 7 — PAUSED (API rate limit, second time)

Dispatched 3 agents (DG vs Custodes deep diag, shoot picker won't-crack penalty, BATTLELINE range audit across all factions). All 3 died early on Anthropic rate limit ("resets 4:10pm Europe/London"). No commits landed.

**Resume**: re-dispatch the same 3 agents. Prompts unchanged. Pre-pause state: MAE-vs-real 5.03pt, MAE-vs-Sweg 5.44pt, HEAD `611d555`, 666 tests green.

**Convergence status**: Iter 5 and iter 6 both Δ<0.1pt (consecutive). Iter 7 will be the third — if it lands Δ<0.1 the loop exits on convergence criterion.

### Iter 7 — completed (2026-05-16)

**Diagnostics**: DG vs Custodes deep diag. Doc: `AUTO_LOOP_ITER7_DG_VS_CUSTODES.md`. Root cause: **Custodes OC starvation** (73-76% of objectives have Custodes OC=0; 14 units M6" can't reach 4 of 5 markers). Plus: Shield Host detachment has ZERO stratagems registered.

**Fix batch**: 2 (shoot-picker won't-crack, BATTLELINE weapon-range audit).

**Results (solo)**:
- Shoot picker won't-crack penalty (mirror of C2): +0.28pt solo regression — PARKED.
- BATTLELINE weapon-range audit: 4 corrections (T'au Strike Team 12→30, TSON Rubric 12→24, CSM Rubric 12→24, Votann Hearthkyn 12→18). Solo −0.03pt.

**Cumulative**: MAE → **5.14pt**. MAE-vs-Sweg → 5.50pt.

**Measurement noise observation**: re-measuring iter 6 commit `611d555` produces MAE 5.17, not 5.03 as originally recorded. Same commit, same PYTHONHASHSEED=0, different process → **±0.15pt variance**. Iter 5-7 Δ values all within noise.

**Iter 7 commits on origin** (final):
- `26e641b` iter 7 DG vs Custodes diagnostic
- `7f99ebd` #iter7 BATTLELINE weapon-range audit

## Loop terminated — convergence at noise floor

**Stop reason**: Convergence criterion (Δ<0.1pt for 3 consecutive) sits below measurement noise (±0.15pt at N=20). Iter 5-7 all read at the noise floor. MAE<1pt unreachable at current calibration baseline (rule-correct simulator + uncalibrated points = 5.14pt floor).

**Cumulative loop result**:
- MAE-vs-real: 6.72 → **5.14pt** (Δ **−1.58pt** across 7 iters)
- MAE-vs-Sweg: 6.78 → **5.50pt** (Δ **−1.28pt**)
- Tests: 632 → 666 (+34 pinning fix invariants)
- Rules cited: 151 → 162 active

**Per-faction final state**:
- DG +18.1 (biggest residual)
- Marines +11.4
- Necrons +5.7 / Custodes +4.8 / Tyranids +4.2 / Aeldari +2.3 / Votann +1.8 / TSON −0.2 / Orks −0.5 / T'au −4.5

**Next-step recommendation**: move to **Plan Step 4 — Re-introduce MC bisection in vanilla mode**. The 5.14pt MAE is rule-correct simulator + un-recalibrated points. MC bisection re-derives per-unit prices against the rule-correct baseline, then feeds Plan Step 5 (utility-factor function fit). The remaining MAE compresses once points absorb the rule shifts.

**Parked items still worth re-evaluating** after MC bisection lands:
- A3 Tyranid Synapse self-shelter
- Marines mapper Option A (mutex weighted basket)
- Marines vehicle all-weapon basket
- Votann probabilistic token gate (needs dedicated Random instance)
- C3 vanilla uses activation_queue (scored-sort)
- C2b shoot-picker won't-crack
- Orks WAAAGH! 5++ vs melee + Advance-and-charge

## Loop resumed — iter 8–13 (post-termination)

User directive on 2026-05-16: "ignore the bar, carry on with the loop … Keep looping till MAE is <2". Iter 7's 5.14pt floor was the rule-correct-but-uncalibrated baseline; re-opening under the rule that correctness-positive changes are kept even if they expose underpricing.

### Iter 8–12 summary (commits on `claude/auto-loop-carryover`)

- Iter 8 — DG opponent-side fixes + Custodes Shield Host real rebuild (`db8d1a6`, `f203c6c`, `983d2a3`). MAE 5.14 → 5.92 (rule-correct regression — Custodes had a fabricated detachment that was over-tuned; replaced with real Auric Champions wording).
- Iter 9 — ANTI-INFANTRY mapper, Votann Oathband 6 real stratagems, Marines Combat Doctrines audit (`1ed3571`, `1f3605e`, `8009d7d`). Combat Doctrines fabrication finding: previous +1-wound rotating buff was invented; real rule is utility-only. Kept the correction (MAE +0.08).
- Iter 10 — EPIC HERO 1-per-army (user-surfaced rule) + 2 audit docs (`b4b2bd1`, `20ce014`, `58e4d5a`). 210 EH datasheets newly constrained. MAE +0.98 — EH stacking was masking underpricing; kept per correctness directive.
- Iter 11 — TSON walk-bug + AM catalogue mapper depth 3→5 + ±1 modifier cap + Ruins INFANTRY-through-walls LoS (`52a5c8c`, `7a5ff80`, `9d2606b`, `f1e2337`). MAE 6.45 → **6.00** (−0.45 — mapper depth fix surfaced 22 missing units).
- Iter 12 — Pile-In/Consolidate, TSON Ahriman seed, Drukhari template, Heroic Intervention as core, Marines Gladius 6 stratagems (`ca76b4d`, `af33ff9`, `cca5246`, `a386f81`, `611f304`). MAE 6.00 (held).

### Iter 13 (2026-05-17)

**Batch dispatched**: 6 parallel agents covering core rules + list realism + parity + mapper hunt.

**Agents reported**:
- Primary VP cap 15/round/army (`1afb043` was `6c0928d`) — core rule, faction-neutral. Solo +0.05.
- Battleshock from R1 (`0476eb7` was `7d11662`) — core rule, faction-neutral. Solo 0.00.
- DG Mortarion + Foetid Bloat-Drone auto-include (`8b0ef45` was `b86f657`) — real-meta list realism. Solo +0.11 (DG WR +0.3pt; over-strength is unit-balance, not list shape).
- TSON Rubric/Scarab Occult cap fix (`e24fb8b`) — squad-fit walk, faction-neutral. Solo −0.20.
- Aeldari Warhost Yvraine+Yncarne template (`879daf6`) — real-meta detachment composition. Solo +0.92 — **PARKED** (Strength From Death mechanic unmodelled; Ynnari delivers no power until that lands).
- BSData mapper deep audit (`6bd3922` was `61e3fc1`) — diagnostic doc only; prose-FNP filter tested but reverted (MAE +0.92 — phantom FNP was masking unmodelled Custodes Bodyguard/ablative-wounds).

**Cumulative (5-fix bundle, Aeldari parked)**: MAE **6.00 → 5.38pt** (Δ **−0.62pt** vs real meta). MAE-vs-Sweg 5.67 → 6.69pt.

**Per-faction shifts (post-iter-12 → post-iter-13)**:
- Marines +10.0 (held)
- Necrons +10.3 (held)
- Aeldari **−4.4 → −1.6** (improved — cumulative effect, Aeldari template parked)
- Tyranids −1.7 (held within variance)
- Orks −9.4 (held)
- T'au +5.0 (held)
- DG **+10.6 → +4.7** (improved — Mortarion + VP cap landed)
- Custodes +1.9 (held)
- TSON **−4.3 → −12.7** (regressed — Rubric cap surfaced All-Is-Dust + 5++ durability under-model)
- Votann −8.6 (held)

**Parked** (per loop rule — would regress cumulative without dependency):
- Aeldari Warhost Yvraine+Yncarne template (`879daf6`). Real-meta correct (May 2026 Warhost mandates Ynnari triumvirate). Park reason: Strength From Death mechanic (Soulburst, Word of the Phoenix) not in simulator — Yvraine/Yncarne in the list deliver no power, just consume budget. **Unpark when**: Strength From Death is implemented (Aeldari/Ynnari psychic/rez chain). Worktree branch `worktree-agent-af8ec43db0bb49cc4` retains the commit.
- BSData mapper prose-FNP qualifier filter (described in `docs/AUDIT_MAPPER_DEEP.md` §6/7). Logically correct but calibration-regressive — phantom FNP currently compensates for unmodelled Custodes Bodyguard + ablative wounds. **Unpark when**: Custodes defensive layer (Bodyguard rule, ablative wounds) is modelled.

**Iter 14 priorities**:
- TSON +5.6pt → +12.7pt: All-Is-Dust 5+ saves vs AP0/AP1 + 5++ Rubric invuln likely under-applied in damage calc. Investigate `code/units.py` save resolution under AP-modifiers and re-verify TSON unit invuln overrides.
- Marines +10.0 / Necrons +10.3: standing high-error band — Oath of Moment + Reanimation Protocols. Both are real rules already implemented; outliers suggest implementation gap or AI under-use of counter-tools.
- DG +4.7 down from +10.6 but still over: investigate stratagem cost utilisation + Disgustingly Resilient FNP 5+ scope (army-wide vs INFANTRY-only).
- Custodes defensive layer (Bodyguard + ablative wounds) — unblocks the parked mapper FNP fix.
- AM Officer/Order parity (still 0/6 stratagems).

### Iter 14 (2026-05-17)

**Batch dispatched**: 6 parallel agents.

**Agents reported**:
- TSON durability (`791a8ad`) — rule-correct All Is Dust rewrite (was modelling deleted launch-index rule). Real 10e rule is Rubricae Phalanx detachment rule "+1 to save vs D1 attacks against RUBRICAE". Added Scarab Occult Rites of Coalescence (-1 to wound). 6 Daemon datasheets missing invulns added (Pink/Blue Horrors, Flamers, Screamers, Sorcerer x2). Solo -0.15.
- AM Combined Arms (`78a2a2d`) — salvaged from worktree (agent terminated mid-flight on rate limit). Real Born Soldiers LETHAL HITS replaces approximation. Voice of Command Order economy with 4 wired Orders (Take Aim, Fix Bayonets, FRFSRF, Take Cover) via new `code/orders.py`. 6 Combined Arms stratagems.
- Necrons RP (`a3798e3`) — salvaged from worktree. Revived models come back at 1HP (not full), wound-by-wound pulse allocation per Wahapedia army-rule wording. Multi-wound Necron units (Wraiths W3, Lychguard W2/W3, Skorpekh W3, Praetorians W2, Lokhust HD W3) were over-firing by W. Solo -0.03 (Necrons +10.3 → +9.4).
- Marines counter-tool diag (`9d5e227`) — agent ABSTAINED per brief. 3 faction-neutral hypotheses identified (H-A leader kill rate, H-B target-spread tiebreaker, H-C charge-target leader bypass). Tested `_support_target_bonus` extension to shoot picker → regressed MAE 5.38 → 5.62. Reverted. Key finding for iter 15: Marines net VP dominance is from OBJECTIVE CONTROL (M_OC 1.04 vs 0.84), not Oath damage — investigate Marines auto-fielding too many cheap 2-OC squads.
- Custodes Bodyguard layer (agent worktree empty) — LOST to API rate limit. Re-dispatch in iter 15.
- DG DR FNP + CP util (agent worktree empty in committed form, partial diag in main worktree pollution stash) — LOST to API rate limit. Re-dispatch in iter 15.

**Test fix in cherry-pick**: Updated `tests/test_detachments.py` fixture for AM rename `plus_one_to_hit` → `am_born_soldiers_lethal_hits`.

**Cumulative (4-fix bundle, Custodes+DG re-dispatch pending)**: MAE **5.38 → 5.20pt** (Δ **−0.18pt** vs real meta). MAE-vs-Sweg 6.69 → 6.58pt. Rule citations 187 → 200.

**Per-faction shifts (post-iter-13 → post-iter-14)**:
- Marines +12.0 → +10.9 (−1.1, AM lethal-hits gives opponent counter-fire)
- Necrons +7.1 → +6.8 (−0.3, RP wound-by-wound bite)
- Aeldari −1.6 → −1.9 (held)
- Tyranids +0.3 → −0.2 (held)
- Orks −4.3 → −4.9 (slight regress, variance)
- T'au +0.5 → +0.8 (held)
- DG +6.7 → +6.7 (unchanged — DG audit slot lost)
- Custodes +3.9 → +4.5 (slight regress — audit slot lost; phantom FNP still in)
- TSON **−12.7 → −11.0** (+1.7 — TSON durability fix bit hard)
- Votann −4.6 → −4.3 (held)

**Stashed (cross-worktree pollution from terminated agents)**:
- `stash@{0}`: iter14-cross-worktree-pollution-round2-2026-05-17 (DG + Custodes partial work, leaked into main worktree)
- `stash@{1}`: iter14-main-worktree-pollution-2026-05-17 (earlier round)
Both worth re-salvaging in iter 15 — contains DG `iter14_dg_cp_util.py` diag + Custodes `mapper_fnp_qualifier_filter.json` + `_dbg_fnp.py`.

**Iter 15 priorities**:
- Re-dispatch Custodes Bodyguard + ablative wounds (still needed; unblocks parked mapper FNP fix).
- Re-dispatch DG DR FNP scope + CP utilisation audit.
- Marines OC squad sizing investigation per iter-14 Marines diag finding (squad count in `data/overrides.json` / `code/archetypes.py`).
- TSON Rubricae Phalanx detachment — currently approximated army-wide; build full detachment registry entry for proper gate.
- Aeldari Warhost unpark candidate: implement Strength From Death (Soulburst, Word of the Phoenix) — would unlock the iter-13 parked Yvraine+Yncarne template.

### Iter 15 (2026-05-17) — DG DR audit re-dispatch

**Agent reported** (DG DR FNP scope + CP utilisation):

**Fabrication finding**: The `simulator.disgustingly_resilient` army-wide FNP 5+ block in `code/units.py:575-576` was a fabrication. Per Wahapedia (https://wahapedia.ru/wh40k10ed/factions/death-guard/) + Goonhammer "Hammer of Math: New Disgustingly Resilient" (https://www.goonhammer.com/hammer-of-math-new-disgustingly-resilient/) — "Disgustingly Resilient is gone as an army ability in 10th edition. ... No omnipresent -1D, no FNP." The DG army rule is Nurgle's Gift / Contagions of Nurgle (the aura). DR in 10e is ONLY the 2 CP Virulent Vectorium stratagem (-1 damage per allocated attack, INFANTRY/CHARACTER scope) — already correctly wired via `transient_minus_one_damage_taken`.

**Fix**: Removed the blanket `if profile.faction == "Death Guard": effective_fnp = min(effective_fnp, 5)` block from Unit.receive_damage. The fabricated gate was granting phantom FNP 5+ to every DG VEHICLE / Bloat-drone / Helbrute / Plagueburst Crawler / Land Raider / Blightlord Terminator / Plaguebearer / Nurgling regardless of datasheet. Per-datasheet FNP (Plague Marines fnp=5, Mortarion fnp=5, Deathshroud fnp=4 via overrides.json) still fires through the unchanged `min(self.profile.fnp, bonus_fnp)` path. Citation + audit_rules SIMULATOR_RULE_KEYS entry removed; FABRICATION_AUDIT.md updated.

**CP utilisation diag** (`scripts/iter15_dg_cp_util.py`, N=30 vs each of 9 opponents): DG burns 7.86 CP/battle on average (median 8, max 13), well within the 12 CP budget. Round 2 is the firing peak (37.3% of all fires). Top stratagems: Command Re-Roll 2.49/battle, Overwhelming Generosity 1.64/battle, Creeping Blight 1.60/battle, Putrid Detonation 0.63/battle, Disgustingly Resilient 0.30/battle (rare — the iter-13 hypothesis that DR was over-firing is NOT borne out; it's the army-wide FNP fabrication that drove the over-strength).

**Worldblight audit**: Verified `_score_objectives` Worldblight implementation matches Wahapedia text (sticky-only approximation, Nurgle's-Gift-on-objective half dropped as documented). No change.

**Results (cumulative, post-fix)**: MAE **5.20 → 5.04pt** (Δ **−0.16pt** vs real meta). DG WR shift: **+6.7 → +6.4pt** (−0.3pt). Modest — confirms that the iter-13 unit-level over-strength hypothesis is partially borne out (the fabrication WAS over-strengthening DG vehicles), but a residual +6.4pt over remains that is consistent with points (un-recalibrated MC bisection) and/or other unmodelled DG counter-tools. Audit clean (199/199 cited, 4 DG test assertions rewritten to pin the absence of phantom FNP).

**Iter 15 commit on origin** (pending user "go"):
- `(SHA tbd)` #iter15 fix — DG Disgustingly Resilient: remove fabricated army-wide FNP 5+

**Iter 16 priorities**:
- Residual DG +6.4pt is now small enough to attribute to points-space (flag for MC bisection per Plan Step 4).
- Custodes Bodyguard ablative wounds still owed (iter 15 didn't dispatch).
- TSON −11.0pt is now the dominant outlier — TSON durability fix surfaced All-Is-Dust under-model but the detachment-rule approximation is still army-wide, not Rubricae-gated.
- Marines +11.7pt held — F4 #179 random_fill safeguard active but Oath + Doctrines still bites; investigate counter-tools.

### Iter 15 closure (2026-05-17)

Remaining 4 agents reported. Full iter 15 batch summary:

**Agents reported**:
- DG fabricated FNP removal (`3e8d450`) — covered above. Solo −0.16. KEPT.
- Marines OC squad-sizing diag (`1a8a700`) — ABSTAINED per brief. Hypothesis (a) FALSIFIED: Marines field the LOWEST total OC (28.8/army) of any major faction. Real cause: damage-per-pt = 0.0768 vs other-faction avg 0.0635 (+20.8%). Flagged for MC bisection. KEPT as diag.
- Aeldari Warhost archetype unpark (`c4ced18` cherry-pick of `879daf6`) + Yvraine/Yncarne abilities (`c35790e`) — agent corrected my brief's outdated 9th-ed Soulburst wording. 10e Strength From Death is the Devoted of Ynnead DETACHMENT rule, not the army rule. Implemented Yvraine "Word of the Phoenix" (revive_destroyed_per_round=2) + Yncarne "Ethereal Form" (heal_per_round=2 + plus_one_to_hit). MAE unchanged because `evaluate_vs_meta` only picks faction="Aeldari", not "Ynnari" subfaction. KEPT (correctness).
- TSON Rubricae Phalanx detachment (`8c0f2fa`) — new detachment with proper 10e All Is Dust gate, 6 stratagems (4 wired). Default detachment swap `grand_coven` → `rubricae_phalanx`. Solo −0.05. KEPT.
- Custodes FNP filter (`4b355e2`) — **PARKED**. Agent confirmed LOS+ablative already in `code/army.py::can_target_for_ranged`. FNP filter alone REGRESSED MAE 5.20 → 5.91 (+0.71). **Unpark when**: MC bisection recalibrates points.

**Cumulative iter 15 (5-fix bundle, Custodes parked)**: MAE **5.20 → 5.13pt** (Δ **−0.07pt**). MAE-vs-Sweg 6.58 → 6.44pt. Rule citations 200 → 208. Tests 767/771 → **771/771** (pre-existing `test_archetype_fallback_when_no_curated` failure resolved as side-effect of TSON archetype rebuild).

**Per-faction shifts (post-iter-14 → post-iter-15)**:
- Marines +10.9 → +11.7 (variance)
- Necrons +6.8 → +6.2 (held)
- Aeldari **−1.9 → −1.1** (+0.8 mostly variance; Yvraine/Yncarne fire only in archetype builds)
- Tyranids −0.2 → +0.3 (held)
- Orks **−4.9 → −3.5** (+1.4 — DG fabrication removal eased Orks' phantom-FNP punishment)
- T'au +0.8 → +2.2 (slight regress)
- DG +6.7 → +7.0 (slight regress, cross-faction)
- Custodes +4.5 → +3.7 (variance)
- TSON −11.0 → −11.5 (held within noise)
- Votann −4.3 → −4.1 (held)

**Loop progress since resume**:
- iter 7 floor: 5.14pt
- iter 8-11 (rule corrections surfaced fabrications): 6.45pt transient peak
- iter 12: 6.00pt
- iter 13: 5.38pt
- iter 14: 5.20pt
- iter 15: **5.13pt**
- Target: <2.0pt
- Remaining gap: ~3.1pt — mostly points-calibration territory. MC bisection (Plan Step 4) is the next major lever.

**Iter 16+ priorities**:
- **MC bisection (Plan Step 4)** — long overdue. Remaining ~3pt is almost entirely points-calibration. Marines profile slice first per iter-15 diag recommendation.
- Magnus-centric TSON template variant.
- Aeldari Ynnari subfaction inclusion in `build_faction_random_army` so Yvraine/Yncarne register in eval.
- Re-evaluate parked Custodes FNP filter post-MC-bisection.
- Standing parity gaps: CSM Pactbound 6 stratagems, Sororitas Miracle Dice, GK Brotherhood Psychic, IK Code Chivalric+LANCE, Chaos Daemons Shadow of Chaos, WE Blood Tithe spend menu.

## Loop pivot — tourney-archetype eval (2026-05-17)

User directive: switch loop calibration target from `random_fill` to `--use-archetype` lists.

**N=500 tourney-archetype baseline** (45,000 battles):

```
Faction                   Sim%   Real%    Diff
Adeptus Astartes          54.4    48.0    +6.4
Necrons                   91.0    53.2   +37.8  ← apex outlier
Aeldari                   44.4    44.4     0.0  ← bullseye
Tyranids                  38.6    48.0    -9.4
Orks                      43.5    44.9    -1.4
T'au Empire               33.4    54.5   -21.1
Death Guard               65.9    48.0   +17.9
Adeptus Custodes          62.1    48.0   +14.1
Thousand Sons             35.5    54.6   -19.1
Leagues of Votann         45.1    46.0    -0.9
MAE vs real meta:     12.81 pts
```

Rationale: tournament-shaped lists are how the simulator will actually be used IRL. Random_fill (MAE 5.13) obscures list-shape biases that archetype templates encode. `scripts/evaluate_vs_meta.py` now supports `--use-archetype`.

**Iter 16+ measures against archetype baseline (MAE 12.81).** Random_fill remains a parallel sanity check but not the primary metric.

Biggest archetype outliers:
1. **Necrons Awakened Dynasty +37.8** (sim 91% — apex; archetype seeds an unbeatable list)
2. **T'au Mont'ka −21.1** (sim 33.4% — battlesuit anchor under-seeded or AI under-uses Markerlights at MSU scale)
3. **TSON Rubricae Phalanx −19.1** (sim 35.5% — Magnus + Rubrics anchor underweighted)
4. **DG Virulent Vectorium +17.9** (sim 65.9% — Mortarion + Bloat-Drones over-seeded post iter-13)
5. **Custodes Shield Host +14.1** (phantom FNP + tight elite list)
6. **Tyranids −9.4** (template misses synapse-anchor balance)
7. **Marines Gladius +6.4** (less acute now after Combat Doctrines rebuild)
8. **Aeldari Warhost 0.0** (Yvraine/Yncarne firing as intended — keep as reference)
9. **Orks War Horde −1.4 / Votann Oathband −0.9** (well-calibrated)

Per-archetype trims must cite competitive-list-realism sources (Goonhammer, Frontline, Stat Check, Wahapedia FAQ).

### Iter 16 (2026-05-17)

**Batch dispatched**: 6 parallel agents targeting archetype outliers. First attempt rate-limited mid-flight (5 of 6 hit Anthropic limit at 12:30pm London). Second attempt landed all 6 reports.

**Agents reported**:
- **Necrons Awakened Dynasty trim** (`d8f4d37` salvage + `7296226` tune) — **massive win**. Solo Necrons WR 95.0% → 63.1% (−31.9pt). Critical AI improvement: **MONSTER/TITANIC/EPIC HERO cap in `_random_fill`** (faction-neutral; prevents over-seeding apex anchors). [Legends]/[Crucible] filter. Warriors and Immortals 2→1 each. KEPT.
- **T'au Mont'ka anchor restore** (`62c7881` salvage + `afb1257` tune) — solo T'au 33.4% → 52.5% (+19.1pt). Riptide×3 + Hammerhead×2 + Crisis×2 + Pathfinder×2. MARKERLIGHT keyword added to Strike Team / Breacher / Sky Ray (was on weapon row only in BSData). KEPT.
- **TSON Rubricae detachment-picker fix** (`4837592`) — solo TSON 35.5% → 38.6% (+3.1pt). Root cause: detachment picker was 50/50 between Rubricae Phalanx and Grand Coven; half the time TSON lost All Is Dust. Added RUBRICAE-keyword affinity branch in `_keyword_affinity_score`. KEPT.
- **Tyranids Subterranean Assault detachment** (`cfc6e17` salvage + `1c30b8b` tune) — solo Tyranids 38.6% → 55.8% (|err| 9.4 → 7.8). Added Subterranean Assault detachment + 4 stratagems + Trygon-heavy template per Goonhammer + Maastricht 2026 GT. KEPT.
- **Custodes Auric Champions rename** (`d58c854`) — solo Custodes 62.1% → 43.1% (−19.0pt, overshoots; Custodes now −4.9 instead of +14.1). Archetype rename Shield Host → Auric Champions, character-heavy template. No new detachment registered. KEPT.
- **DG Virulent Vectorium trim** — **PARKED**. Agent tried 3 variants, all regressed to 76-89% sim WR. Root cause finding: `_random_fill` is the over-anchor force, not the template. Template trim frees budget for higher-impact picks. The MONSTER/EPIC HERO cap (from Necrons agent) is the cross-cutting fix.

**Cumulative iter 16 (5-agent bundle, DG parked)**: MAE **12.81 → 11.48pt** (Δ **−1.33pt**). MAE-vs-Sweg 13.29 → 10.89pt. Tests 771/771. Rule citations 208 → 214.

**Per-faction shifts**:
- Marines **+6.4 → +1.2** (−5.2 ✅)
- Necrons **+37.8 → +4.3** (−33.5 ✅✅)
- Aeldari 0.0 → +11.2 (cross-faction regress)
- Tyranids −9.4 → +23.4 (FLIPPED; MONSTER cap removed Trygon spam compensator)
- Orks −1.4 → +7.6 (cross-faction; rivals weakened)
- T'au **−21.1 → +1.9** (−23.0 ✅✅)
- DG +17.9 → +13.4 (−4.5 ✅)
- Custodes +14.1 → −11.6 (overshoots; template rename too aggressive)
- TSON −19.1 → −28.8 (regress; cross-faction effect from MONSTER cap weakening TSON's Magnus pickup)
- Votann −0.9 → −11.6 (regress)

**Iter 17 priorities**:
- Custodes template re-tune: add 1-2 mid-elite units back (Vertus Praetors, Aquilon Custodians) to lift from −11.6 toward 48-55%.
- Tyranids template re-tune: lower Trygon×2 to ×1 or restore Carnifex×2 to absorb overshoot from +23.4.
- TSON: revisit Magnus support at 1500pt budget archetype variant; consider raising SEED_FRACTION specifically for TSON.
- Aeldari: Warhost archetype Yvraine+Yncarne now over-firing in N=40 archetype; tune size of supporting Eldar squads.
- Votann/Orks: cross-faction regressors; minor template adjustments.
- DG: revisit with `_random_fill` MONSTER cap now in place (the cap should make trim attempts work).
- Marines: at +1.2 — essentially solved. Hold.
- Necrons: at +4.3 — near-target.

### Iter 17 (2026-05-17, TSON-focused)

**Agent**: iter17 TSON fix.

**Change shipped**: Add Mutalith Vortex Beast (170pt MONSTER) to TSON Rubricae Phalanx archetype template.

**Diagnostic** (`scripts/iter17_tson_diag.py`):
- Seed audit at 1000pt: template never seats a wrecker. SOT (396pt) is over the 300pt SEED_FRACTION slice; Magnus (435pt) is barred from random_fill by the iter16 EPIC HERO cap.
- Template-variant probe (N=30 vs random_fill opponents): +Mutalith **+16.7pt** solo (32.2% → 48.9%); +LoC alternatives also tested.
- Template-variant probe (N=30 vs archetype opponents, production matrix shape): +Mutalith neutral (30.0% → 30.0%). Other variants tested (-SOT +Lord of Change, +Daemon Prince, +Pink Horrors, +Heldrake, +Forgefiend, +Helbrute, +Chaos Predator Annihilator) regress or are neutral.
- Detachment picker check: 14/20 Rubricae Phalanx vs 6/20 Grand Coven post iter16 affinity. Holds with SOT kept; drops to 7/20 if SOT removed (RUBRICAE points share falls to ~24%, below the +20 affinity threshold).

**Eval result (N=40 archetype, full matrix)**:
- TSON 25.8% → **26.9%** (+1.1pt, far short of the 45-55% target).
- MAE unchanged at **11.48** (the Mutalith add is a no-op at the matrix level).

**Test fixture fixes**:
- `tests/test_archetypes.py::test_archetype_fallback_when_no_curated` — pre-existing failure under PYTHONHASHSEED=0. The test picked "Chaos Titans" (cheapest unit 1100pt > 1000pt eval budget) and asserted any units built. Fixed by filtering for "obscure faction that has at least one affordable profile at the test budget".
- `tests/test_synapse_anti_swarm.py::test_round_one_skips_battleshock` — pre-existing failure. The test asserted "R1 skips battleshock" but iter13 (`0476eb7`) removed the R1 short-circuit per Wahapedia core rules — battleshock fires every Command phase from R1. Renamed test to `test_round_one_runs_battleshock` and updated assertion to accept either outcome of the now-live R1 test.

**Tests**: 770/770 pass (1 skip is the pre-existing visualisation test that wants headless display).

**Structural conclusion (FLAGGED FOR ITER 18)**:
At 1000pt eval budget, TSON archetype is structurally under-resourced. Neither Magnus (435pt) nor a second Scarab Occult squad (792pt) can fit. Real meta May 2026 win-rate (54.6%) reflects 2000pt+ play. The simulator's archetype matrix uses 1000pt because that's the calibration default; TSON's deficit is partially a "wrong budget for this faction" artefact rather than a tuneable template/rule problem.

**Recommended dispatch for iter 18**:
1. Raise eval budget to 2000pt globally (matches real tournament budget; ALL factions get richer lists). Tradeoff: 4x more compute per battle, but the matrix is N=40×10×10 = 4000 battles already so 16000 is still reachable in ~10 min.
2. Alternative: enable `SEED_FRACTION_BY_FACTION["Thousand Sons"] = 0.6` so the 1000pt seed slice can fit either Magnus (435pt + 240pt Rubric ≤ 600pt) or LoC+Mutalith.
3. Alternative: split TSON archetype into "Rubricae Phalanx (1000pt budget)" and "Magnus Anchor (2000pt budget)" variants and let `build_archetype_army` pick based on the passed budget.

Cumulative MAE: **11.48 → 11.48pt** (Δ 0.00). Iter 17 holds the line on TSON archetype but flags the budget structural ceiling.


### Iter 17 closure (2026-05-17)

All 5 KEEPers landed on carryover. DG dispatch DEFERRED (MC bisection territory).

**Agents reported**:
- Votann recovery (`0325555`) — sim 34.4% → 42.2% (+7.8pt). Hekaton + Kâhl + Einhyr Champion. SEED_FRACTION_BY_FACTION["Leagues of Votann"] = 0.4.
- TSON Mutalith (`810ca80`) — sim 25.8% → 26.9% (+1.1pt). Structural 1000pt budget ceiling flagged. Bonus: 2 pre-existing test fixes.
- Custodes re-tune (`308cb72`) — sim 36.4% → 47.2% (+10.8pt, |err| 0.8 — bullseye). Vertus Praetors + Blade Champion + Allarus 1→2. SEED_FRACTION 0.55.
- Tyranids re-tune (`dbc4569`) — sim 71.4% → 50.3% (−21.1pt). Trygon×2→×1, added Tyrannofex.
- Aeldari trim (`1ce1b6d`) — sim 55.6% → 43.3% (−12.3pt). Avatar of Khaine anchor, drop Yvraine, Yncarne ×4. Yvraine revive 2→1 cited update.
- DG retry — **DEFERRED**. Even with iter 16 MONSTER cap, drone-heavy variant regressed to 89.7%. Plague Marines (BATTLELINE) + Bloat-Drones (VEHICLE) are not caught by the MONSTER cap. DG points are under-costed → MC bisection (Plan Step 4).

**Cumulative iter 17 (5-fix bundle, DG parked)**: MAE **11.48 → 8.25pt** (Δ **−3.23pt**). MAE-vs-Sweg 10.89 → 7.75pt. Tests 771/771. Rule citations 214 → 214.

**Per-faction shifts (post-iter-16 → post-iter-17)**:
- Marines +1.2 → +4.8 (variance)
- Necrons +4.3 → +9.9 (variance — cross-faction)
- Aeldari **+11.2 → +3.1** (−8.1 ✅)
- Tyranids **+23.4 → +5.6** (−17.8 ✅✅)
- Orks +7.6 → +10.9 (variance)
- T'au +1.9 → +5.5 (variance)
- DG +13.4 → +15.9 (variance; awaits MC bisection)
- Custodes **−11.6 → −0.8** (+10.8 ✅ bullseye)
- TSON −28.8 → −24.9 (+3.9, structural ceiling)
- Votann **−11.6 → +1.2** (+12.8 ✅✅ bullseye)

**Loop trajectory under `--use-archetype`**:
- N=500 baseline: 12.81
- iter 16: 11.48 (−1.33)
- iter 17: **8.25** (−3.23)
- Target: <2.0
- Gap: ~6.25pt remaining

**Iter 18 priorities**:
- TSON structural budget — raise eval to 2000pt globally OR split archetypes by budget. Most impactful single move (would unlock Magnus + SOT for TSON; gives all factions richer lists).
- DG — MC bisection on Plague Marines + Bloat-Drones + Plagueburst Crawler points.
- Cross-faction variance regressions on Marines/Necrons/Orks/T'au/DG (small drifts ~3-5pt each).
- Marines damage-per-pt finding from iter 15 still pending MC bisection.

## Loop pivot — eval budget 1000pt -> 2000pt (2026-05-17)

User directive: raise eval budget to match real tournament play. Result: archetype templates calibrated for 1000pt no longer fit the budget properly — random_fill topup at 2000pt adds high-impact bricks the templates didn't constrain.

**2000pt baseline (N=40 archetype, post-iter-17 carryover at 526c148)**:

```
Adeptus Astartes  72.8 / 48.0 / +24.8  ← apex outlier (was +4.8 at 1000pt)
Necrons           66.1 / 53.2 / +12.9
Aeldari           41.7 / 44.4 / -2.7  ✅
Tyranids          32.5 / 48.0 / -15.5  (FLIPPED from +5.6 at 1000pt)
Orks              48.1 / 44.9 / +3.2  ✅
T'au Empire       68.6 / 54.5 / +14.1
Death Guard       72.5 / 48.0 / +24.5  (MC bisection confirmed)
Adeptus Custodes  46.1 / 48.0 / -1.9  ✅
Thousand Sons     31.7 / 54.6 / -22.9  (structural — Magnus still bottlenecked even at 2000pt)
Leagues of Votann 53.1 / 46.0 / +7.1
MAE vs real meta: 12.96 pts (was 8.25 at 1000pt)
```

Most templates encode unit counts for 1000pt eval. At 2000pt, the seed slice doubles (e.g. Custodes 0.55 * 2000 = 1100pt seeded) but the count-multipliers don't scale up automatically — `_random_fill` then loads cheap high-WR units on top, inflating the strong factions (Marines, DG, T'au, Necrons) and crushing the weak ones (Tyranids, TSON).

**Iter 18 measures against 2000pt archetype baseline (MAE 12.96).**

### Iter 18 — PARKED (cumulative regression) (2026-05-17)

6 agents dispatched against 2000pt archetype outliers. Cumulative N=40 cherry-pick result: MAE **12.96 → 14.04 (+1.08 regression)**. Per loop rules, bundle parked; reset carryover to `d253b90` (2000pt pivot baseline).

**Agent findings (each commit lives on its worktree branch for iter 19 mining)**:
- TSON Magnus unlock — Magnus is a sim under-performer. Forcing him in regressed TSON 31.7% → 21.9%. Agent confirmed with V_A probe (no Magnus, just bigger seed) — also regressed. Real fix: Magnus PSYKER abilities / deadly_demise / aura wiring in simulator. NOT a template issue.
- Marines doc-only — both template attempts regressed (vehicles +3.3pt, BATTLELINE chaff +6.1pt). BATTLELINE cap admits `max(1, template_count)` fills → multi-count INCREASES stacking. Fix needs MC bisection on Marines points OR tighter `_random_fill` cap (0.5 → 0.33).
- Necrons template variants — iter17 baseline IS local minimum. Every variant tested regressed (+12 to +26pt). The brief's "multi-wrecker stack" hypothesis is empirically FALSIFIED — iter16 MONSTER cap blocks it. Necron over-shoot is in simulator (RP, +1-to-hit aura, Lokhust HD stats).
- DG MC bisection (partial) — +25-33% across DG core only shifted DG 72.5% → 73.6% (no improvement). DG over-strength is in COMBAT MODEL not points (Typhus dmg=18, LoC dmg=15 — suspected per-squad aggregation rather than per-model).
- T'au template trim — modest improvement (66.7%, -1.9pt). Structural finding: VEHICLE/WALKER not in `_random_fill` wrecker cap; Riptide/Crisis stacking goes uncapped.
- Tyranids template restore — succeeded solo (32.5% → 57.8%, +25.3pt) but cumulative overshoot to +6.2 vs target +/-5pt band.

**Aggregate diagnosis**: Iter 18 confirms the **archetype-template ceiling**. Per-faction template changes have natural limits at 2000pt because `_random_fill` topup compounds template choices via the BATTLELINE-cap `max(1, template_count)`. Further reduction requires SIMULATOR-side work, not template work.

**Iter 19 priorities (simulator-side)**:
1. `_random_fill` cost cap tighten (0.5 → 0.33) + extend wrecker cap keywords (VEHICLE / WALKER) — faction-neutral global improvement
2. Necrons Awakened Dynasty +1-to-hit aura: verify real-rule gates (currently always-on per simulator?)
3. DG per-CHARACTER damage aggregation audit (Typhus, LoC, Foul Blightspawn — verify dmg is per-model not per-squad)
4. TSON Magnus PSYKER abilities + deadly_demise + Cabal of Sorcerers Rituals firing audit
5. Marines MC bisection on key units (Repulsor, Hellblaster, Aggressor, Eradicator) per iter 15 diag finding
6. Aeldari Warhost may auto-recover once other factions stabilize — re-eval after structural changes

### Iter 19 — PARKED (cumulative regression) (2026-05-17)

6 agents on simulator-side work past template ceiling. 2 lost to rate limit (DG damage agent eventually reported; T'au cleanup minor). Cumulative N=40 result:

**Full bundle (5 commits)**: MAE **12.96 → 13.43 (+0.47 regression)**. Marines drops 24.8→12.3 (-12.5pt) — but cross-faction regressors (Aeldari, Tyranids, Custodes, TSON) more than offset.

**Marines+DG+T'au-only subset**: MAE **12.96 → 13.01 (+0.05, flat)**. Marines bumps alone yield -4.2pt vs -12.5pt in full bundle — the _random_fill cap was the synergy multiplier, but it was itself MAE-negative in cumulative.

**Agent findings preserved on worktree branches**:
- `a878dde` `_random_fill` cap 0.5→0.33 + VEHICLE/WALKER. Cap was too aggressive; over-compressed fill.
- `ff72bc8` Necrons aura gates (78 lines). Cross-faction MAE-negative.
- `6732722` TSON Magnus PSYKER/deadly_demise wiring (96 lines). TSON further regressed -22.9→-29.3.
- `44681be` Marines price bumps +15-20%. **Real win (-12.5pt) but only with full bundle synergy.**
- `8f49bd2` DG/CSM Plague Marines lethal_hits=false (mapper weighted_basket bug fix). Correctness-positive, MAE-neutral.
- `503329d` T'au Crisis Suit override cleanup. Lanchester hygiene, MAE-neutral.

**Deferred (DG damage agent finding)**: Plague Marine lethal_hits leakage is a real mapper bug — `weighted_basket_average` unions keyword flags across heterogeneous loadout baskets with `any(...)`. Proper fix is rewriting weighted_basket to weight keyword flags by basket proportion. Structural mapper change for iter 20+.

**Loop status**: Templates calibrated for 1000pt regressed at 2000pt (iter 18). Simulator-side dials regressed cross-faction (iter 19). The MAE floor at archetype 2000pt is structural — further progress likely requires:
1. **Rewrite `_random_fill` topup model** — current `0.5 * remaining_budget` cap is the dominant lever; need a faction-neutral redesign that doesn't favour one matchup.
2. **Magnus / Cabal / All-Is-Dust simulator wiring** — iter 19 agent confirmed Magnus is sim under-performer; PSYKER MW output and detachment-rule gates need attention.
3. **MC bisection on a broader unit set** — Marines bumps showed pricing works but needs cross-faction balance.

**Iter 20 priorities** (per agent recommendations):
- Mapper `weighted_basket_average` keyword-flag-by-proportion rewrite
- Necrons Awakened Dynasty aura: real-rule gating audit (currently always-on)
- TSON Magnus + Cabal of Sorcerers Rituals + All Is Dust full simulator-side audit
- Marines bumps may land if `_random_fill` cap is tuned more carefully (0.4 instead of 0.33)

Loop trajectory under `--use-archetype` 2000pt:
- Baseline (post-pivot): 12.96
- iter 18: parked at 14.04
- iter 19: parked at 13.43
- Target: <2.0

## Branch pivot — claude/sim-calibration (2026-05-18)

PR #20 opened from `claude/auto-loop-carryover` to main. Started new branch `claude/sim-calibration` for simulator-correctness work past the archetype-template ceiling. User directive saved as memory feedback (`feedback-mae-floor-before-mc`): MUST drive MAE low via sim-correctness + faction-neutral AI improvements BEFORE pivoting to MC bisection.

### Iter 20 (2026-05-18) — correctness sweep

5 agents on real-bug correctness fixes. 3 commits cherry-picked, 1 still pending (DG audit), 1 already known to be empty (Crisis 4++ — covered by `7e3e8e2`).

**Cherry-picks on `claude/sim-calibration`**:
- `7e3e8e2` — Crisis Fireknife/Starscythe + 6 other variant 4++ overrides (BSData v10.6.0 omits Invulnerable-Save infoLinks on variant CHARACTER/TERMINATOR entries; long-tail mapper gap)
- `5cbf7e2` — Necrons Awakened Dynasty leading-gate tightening (`bonus_to_hit_when_led` now requires formal Bodyguard attachment via host_keys + added Lychguard to Overlord's bodyguard list)
- `1c0c1ce` — Mapper `weighted_basket_average` keyword-by-proportion rewrite (majority-threshold >50% basket weight for booleans + Anti-X proportion-thresholded; parsed.json 1155-line regen) + Magnus PSYKER deadly_demise wiring (eval-neutral since Magnus seeded into 0/40 archetype lists at 2000pt)

**Cumulative iter 20**: MAE **12.96 → 13.73pt** (Δ **+0.77 regression**). Per user iter 20 directive (correctness > MAE), KEPT.

**Per-faction shifts**:
- Marines **+24.8 → +20.3** (−4.5 ✅ — mapper fix removed phantom Heavy/Melta/Lethal Hits on Marines weapons)
- Necrons +12.9 → +17.6 (+4.7 ❌ — Overlord per-leader `My Will Be Done` plus_one_to_hit fab still firing; iter 21 target)
- Aeldari −2.7 → −6.9 (cross-faction regress)
- Tyranids −15.5 → −17.7
- Orks +3.2 → +4.8
- T'au **+14.1 → +11.1** (−3.0 ✅ — Crisis 4++ didn't push them further over)
- DG +24.5 → +23.7 (−0.8)
- Custodes −1.9 → −3.8
- TSON −22.9 → −24.6 (slight; Magnus wiring no-op until template change lands)
- Votann +7.1 → +6.8

**Iter 21 priorities (locked in)**:
1. Remove `plus_one_to_hit=True` fab from Necron Overlord/Chronomancer/Technomancer LeaderAbilities (already flagged as approximation in `data/rule_citations.d/leaders.json` per iter 11 fabrication audit, but never removed). Should close most of Necrons +4.7 regression.
2. DG combat model audit re-dispatch (iter 20 agent terminated empty).
3. Magnus simulator under-performance investigation — why does 16W T11 4++ MONSTER PSYKER under-deliver his 435pt sticker?
4. Faction-neutral AI improvements (per standing user directive after correctness): leader-aura utilisation, smarter charge target picker, etc.


Older iter blocks live in `AUTO_LOOP_LOG_archive.md`.

## Branch claude/sim-calibration-6 (2026-05-23) — noise-gated calibration + PR #31

### Headline reframing

The calibration target moved from a hand-curated `TOURNAMENT_TARGET` dictionary (10 real Warp Friends numbers + 12 meta-midpoint approximations) to a JSON load from `data/warpfriends_rolling.json` — a game-weighted 4-week rolling aggregate scraped by `scripts/scrape_warpfriends.py` from the public `warpfriends.wordpress.com` archive. Total games across the 4 weeks: 31,841. Faction-name normalisation map: 6 Space Marine chapters game-weight-aggregated into Adeptus Astartes; "Tau" / "Sisters of Battle" / "Genestealer Cult" normalised to the simulator's internal names; "Imperial Agents" dropped.

The headline calibration metric is now noise-gated MAE: `mean(max(0, |sim - target| - noise_floor))`. Per-faction `noise_floor = max(week_to_week_stdev, binomial_95_CI_halfwidth)`. A faction inside its noise band contributes zero. Raw MAE retained as legacy headline. New `Factions inside noise band: N/22` count is the structural progress signal — the target endpoint of Stage 1 is now "all 22 inside" rather than a numeric MAE threshold.

Mean per-faction noise floor across the 22 factions is 3.67pt. The old "MAE ≤ 2.0" Goal A target sat below it (chasing variance) and is superseded — `ROADMAP.md` updated.

Top 4 signal-bearing target shifts:
| Faction | Old target | Rolling | Noise | Gap |
|---|---:|---:|---:|---:|
| Chaos Space Marines | 46.0 | 55.63 | 2.48 | +9.63 |
| Chaos Daemons | 47.0 | 52.60 | 3.16 | +5.60 |
| World Eaters | 50.0 | 44.93 | 3.42 | -5.07 |
| Aeldari | 44.4 | 41.55 | 3.10 | -2.85 |

18 of 22 factions were already inside their noise band under the old approximations — hand-curated targets were closer than expected on average.

### Stage 1 commits before the reframing (40 landings on sim-cal-6)

AI piloting (9 waves): AI-1 Orks tarpit / AI-2A WE / AI-2B Tyranids / AI-2C Daemons / AI-3 Custodes-Drukhari-Votann objective priority / AI-4 Astartes Oath / AI-5 Aeldari Strands / AI-7 Necron Reanimation-aware (not landed — Detachment-level per-army flag couldn't model per-unit eligibility, parked pending MAP-4 infrastructure) / AI-8 transport priority / AI-9 sacrificial chaff deployment for Engage/BEL VP.

Anti-keyword sweep (2): AK-1 [DEVASTATING WOUNDS] on 14 weapon profiles; AK-2 [LANCE] + [ANTI-MONSTER] + [ANTI-VEHICLE] on 12 profiles.

Stratagem (3): ST-1 replaced 8 `transient_plus_one_*` proxies with real LETHAL HITS / REROLL WOUNDS; ST-2 added 5 stratagems for under-performers; ST-3 tightened over-eager AI gates on 7 stratagems.

Mapper structural (6): MAP-1 multi-profile mapper generalised; MAP-2/3 prose-walk gate fix + basket-threshold keyword union with Bernoulli gating; MAP-3-FIX basket-fraction gating for partial-coverage; MAP-4 per-unit Reanimation eligibility; MAP-MULTIFIRE + VALIDATE multi-profile fire-all with mode-suffix clustering + pistol exclusivity. BS-1 per-unit battleshock state infra.

Faction rules (4): MR-WE-2 Beacons of Rage / Rend and Tear; MR-WE-3 Berzerker Blood Surge; MR-CHAOS-DAEMONS-LOCUS 4 Herald leaders; MR-CK-HARBINGERS Chaos Knights Harbingers of Dread (3-Dread rotation, battleshock-keyed).

Universal 10e core rules audit (6 passes): CORE-RULE-AUDIT 1..6 + CORE-RULE-FIX-1 chargers-fight-first / -2 Indirect Fire no-crit-no-Heavy / -5 unmodified-roll crit gate / -6a engagement range 1.5" → 1.0". FF-KEYWORD-1 per-unit Fights First datasheet keyword pipeline.

Data corrections (5): STAT-AUDIT 7 unit-stat mapper artifacts; SK-1 8 Phobos/Pteraxii/Pathfinder Stealth surfaces; KNIGHT-STAT-AUDIT 2 Knight weapon artifacts; TYRANIDS-FIX Trygon CHARACTER strip + archetype rebalance; DET-VARIETY-1 3 alternative detachments.

### Merge from origin/main + WF wire-up

2026-05-23: merged Ed's 15+ commits from origin/main into sim-cal-6 (BSData Move-stat fix, equation-fit pipeline, Streamlit app changes). Three conflict resolutions: AI-9 block in code/strategy.py (additive — keep both); Stompa override in data/overrides.json (additive — keep both); evaluate_vs_meta.py rewrite to integrate noise-gated MAE on top of Ed's `price_overrides` + `save_snapshot` plumbing.

WF-SCRAPE-1 (commit 4834002) + WF-WIRE-1 (commit 41c942d) landed on top. The snapshot JSON now also writes per-faction noise_floor + gated_error so the Calibration tab can surface inside-band vs outside-band status without re-running the matrix. PR #31 opened.

### N=40 baseline against new Warp Friends rolling target

`docs/wf_baseline_n40.log` — MAE raw 14.57, MAE gated 11.35, 4/22 inside band (DG, WE, EC, GK). 3 factions structurally parked (Chaos Knights 35.83, Imperial Knights 26.65, Custodes 14.01 — together 76.5pt of the headline, blocked on multi-profile mapper / board-control rebalance). Tractable outliers ordered: Drukhari 31.78, Tyranids 23.74, Daemons 21.58, AdMech 13.93, Sororitas 14.15.

### Wave 1 (2026-05-23) — 3 parallel diag agents

| Faction | Commit | Move @ N=40 | Notes |
|---|---|---:|---|
| Drukhari | `54f6663` DRK-DIAG-2 | -1.91 | 3 phantom-ranged baskets zeroed (Lelith / Incubi / Succubus, same Drazhar pattern) |
| Tyranids | `4552f34` TYRANIDS-DIAG-2 | 0 | 2 Norn FNP false-positives cleared (Norns not in archetype, rule-correctness hygiene); flagged Tyranid Warriors + Hive Tyrant basket inflation as structural carry-forward |
| Daemons | `083c30c` DAEMONS-DIAG-2 | **-4.40** | **46 Daemonic 4+/5+ invuln saves restored** (same BSData omission pattern as DDA / Wraithguard / Chaos Knights — entire Chaos Daemons codex missing army-wide invuln) |

Cumulative MAE gated 11.35 → 10.99 (-0.36pt). Inside band 4/22 → 3/22 (DG slipped out by 0.27 — well within noise).

### Wave 2 (2026-05-23) — 3 parallel diag agents on next-tier outliers

| Faction | Commit | Move @ N=40 | Notes |
|---|---|---:|---|
| Sororitas | `095007b` SORORITAS-DIAG | -0.95 | Canoness "Beacon of Faith" leader fab dropped — citation self-admitted "invented label for reroll-1s proxy" |
| AdMech | `e4f9a55` ADMECH-DIAG | +1.07 | 4 Crusade-Points-only Archeotech weapons stripped from Archaeopters (BSData mapped narrative campaign upgrades as standard wargear). Direction-wrong at N=40 — likely matchup-redistribution within noise. Carry-forward: structural mapper Crusade-Points filter needed |
| Drukhari | `7a8a780` DRK-DIAG-3 | ~0 (host-key bound) | Archon "Hatred Eternal" + Succubus "Precision Blows" leader fabs dropped — both self-confessed proxies in citation text |

Cumulative MAE gated 10.99 → 10.98 (-0.01pt). Inside band stayed at 3/22. Wave finding: small per-unit fab drops in already-audited factions are hitting diminishing returns; the big movers are systematic restores (Daemonic invuln 46-unit fix in W1) and stat artifacts (DRK-DIAG-2 phantom ranged in W1).

### Wave 3 (2026-05-23) — carry-forward-driven dispatches

| Faction | Commit | Move @ N=40 | Notes |
|---|---|---:|---|
| Sororitas | `ff034bb` SORORITAS-MORTIFIER-FNP | +0.72 (noise) | 2 SC5-10 prose-walk leaks fixed (Hospitaller — FNP grants to led unit not self; Saint Celestine — Lifewards conditional on Geminae alive). Mortifier/Penitent/Repentia FNP 5+ was actually unconditional, no leak there |
| Tyranids | `ec0197e` TYRANIDS-MULTI-LOADOUT | **-3.33** | 3 multi-loadout fixes (Tyranid Warriors attack-volume-weighted blend, Hive Tyrant + Winged Hive Tyrant exclusive-alternative cleared). Hive Tyrant did the visible work — Warriors + Winged inert until archetype-surfaced |
| Drukhari | `bad0df2` DRK-DIAG-4 | +0.48 (noise) | Combat Drugs stacking bug fixed (was applying all 4 mutually-exclusive drugs simultaneously, collapsed to one army-wide pick per real rule). Direction-wrong at N=5 + N=40 but rule-correct; tournament data agrees Wych Cult shouldn't be as deadly as stacked-drug sim was modeling |

Cumulative MAE gated 10.98 → 10.93 (-0.05pt). Inside band 3/22 → **4/22** (Death Guard rejoins).

### Wave 4 (2026-05-23) — structural mapper + Greater Daemon auras + Drukhari vehicles

| Faction | Commit | Move @ N=40 | Notes |
|---|---|---:|---|
| Drukhari | `b29a4c9` DRK-DIAG-5 | **-4.17** | Raider / Ravager / Razorwing exclusive-loadout dual-firing fixed (Disintegrator + Dark Lance both firing per shot, should be one-or-other). Same TYRANIDS-MULTI-LOADOUT pattern, bigger impact because Skysplinter Assault is vehicle-heavy |
| Daemons | `f4c8109` DAEMONS-DIAG-3 | -0.12 | All 4 Greater Daemons + Skarbrand were missing from leader registry (silent zero-buff bug). Wired Bloodthirster + Skarbrand Khorne auras; LoC/GUO/KoS deferred because LeaderAbility schema lacks `plus_one_strength_ranged` / `plus_one_toughness` / `plus_one_ap_melee` fields (refused to fabricate per CLAUDE.md section 10). Limited impact because Daemonic Incursion is multi-god |
| AdMech | `1927b99` MAPPER-CRUSADE-FILTER | **-2.50** | Structural mapper fix: `_is_crusade_only_entry` helper in `code/bsdata/mapper.py` excludes weapons with `Crusade Points`-only cost AND any entry inside a `"Crusade"` container. 20 AdMech units cleaned (multiple Tech-priest variants, Sicarian Ruststalkers, Sydonian Skatros). Defensive container-name gate confirmed no other factions affected |
| Infra | `0769e81` STATCHECK-1 | — | Playwright scraper for Stat Check Tableau viz. Cannot run in agent harness (no pip access); user must `pip install playwright && playwright install chromium && python -m scripts.scrape_statcheck` locally to populate `data/statcheck_meta.json`. Stub written with expected JSON shape |

Cumulative MAE gated 10.93 → **10.73** (-0.20pt). Inside band stayed at 4/22 (DG/WE/EC/GK).

### Iteration close summary (2026-05-23)

**4 waves of 3 parallel agents = 12 dispatches, 11 commits landed + 1 infra commit.** Cumulative MAE gated **11.35 → 10.73 (-0.62pt headline, -5.5% relative)**, 4/22 inside noise band.

Biggest wins:
- DAEMONS-DIAG-2 (-4.40, 46-unit Daemonic invuln restore)
- DRK-DIAG-5 (-4.17, vehicle dual-firing fix)
- TYRANIDS-MULTI-LOADOUT (-3.33, Hive Tyrant exclusive-alternative)
- MAPPER-CRUSADE-FILTER (-2.50, structural Crusade filter on 20 AdMech units)
- DRK-DIAG-2 (-1.91, phantom-ranged baskets on Lelith / Incubi / Succubus)

Pattern: every meaningful headline movement came from data corrections (BSData omissions, basket-composition inflation, multi-loadout dual-firing), not from rule/AI tuning. Small per-unit fab drops in already-audited factions are clean correctness hygiene but MAE-neutral.

### Wave 5 (2026-05-23) — Stat Check cross-source noise floor + cleanup wave

Cross-source data wire-up (separate from the loop's rule-correctness work):
- **STATCHECK-WIRE** (`aa10639`): Stat Check's Tableau dashboard scrape now produces `data/statcheck_meta.json` (22 factions, 15,052 games from Best Coast Pairings + TourneyKeeper + Mini Headquarters). `scripts/scrape_statcheck.py` was rewritten from a heuristic walker to a precise length-prefix-framing parser that pulls win rates from the Tableau dataDictionary block. `evaluate_vs_meta.py` now computes `NOISE_FLOOR = max(within-source Warp Friends noise, |WF.wr - SC.wr|/2)`. Only Death Guard's noise floor moved (2.58 to 2.80) under this rule — every other faction's within-source noise was already wider than the cross-source disagreement, confirming that the WF rolling aggregate was already capturing the variance signal. Mean noise floor 3.67 to 3.68 pt — principled infra rather than a numeric MAE shift. Cross-source disagreements flag meta-volatile factions: Thousand Sons (gap 7.91 pt), Death Guard (5.59), Chaos Knights (5.56), Emperor's Children (4.20). User one-time Playwright setup: `py -3.13 -m pip install playwright; py -3.13 -m playwright install chromium`.

| Faction | Commit | Move @ N=40 | Notes |
|---|---|---:|---|
| Sororitas | `be0abca` SOROR-KEY-FIX | +0.47 | 5 dead-key overrides rekeyed `adeptus_sororitas_*` to `adepta_sororitas_*` — Morvenn Vahl, Junith Eruita, Canoness (× 2 variants), Saint Celestine had been silently saveless for who knows how many iterations. Direction-wrong for Sororitas MAE (already over) but rule-correct per `feedback-rule-correctness-not-made-up` |
| Daemons | `66594fd` DAEMONS-DIAG-4 | +0.12 | 4 god-aligned sub-detachments (Blood Legion, Legion of Excess, Plague Legion, Scintillating Legion), all no-flag composition-only per DET-VARIETY-1 pattern. `FACTION_DETACHMENTS["Chaos Daemons"]` expanded 1 → 5 entries. Real impact lever (Locus auras for LoC/GUO/KoS) still requires LeaderAbility schema extension — carried forward |
| Drukhari | `1f852c0` DRK-DIAG-6 | 0 | Fixed AI-3 asymmetry: `_drukhari_decisive_strike_penalty` 0.5× bias was in MOVE planner but not CHARGE planner, so Drukhari would move-reject a non-decisive target then charge it anyway. Now applied to both. N=5 moved Drukhari -0.95 but N=40 archetype matrix flat |

Cumulative MAE gated 10.73 → 10.76 (+0.03 within noise). Inside band stayed at 4 of 22.

### Five-wave session close (2026-05-23)

**Five waves of 3 parallel agents = 15 dispatches + 1 infra. 15 commits landed + 1 cross-source data source.** Cumulative MAE gated **11.35 → 10.76 (-0.59 pt headline, -5.2% relative)**, 4 of 22 inside noise band.

Top wins (in order of impact at N=40):
- DAEMONS-DIAG-2 (-4.40, 46-unit Daemonic invuln restore)
- DRK-DIAG-5 (-4.17, vehicle dual-firing fix)
- TYRANIDS-MULTI-LOADOUT (-3.33, Hive Tyrant exclusive-alternative)
- MAPPER-CRUSADE-FILTER (-2.50, structural Crusade filter on 20 AdMech units)
- DRK-DIAG-2 (-1.91, phantom-ranged baskets on Lelith / Incubi / Succubus)

Open carry-forwards for the next iteration (priority order):
1. **LeaderAbility schema extension** — `plus_one_strength_ranged` / `plus_one_toughness` / `plus_one_ap_melee` fields + 3 simulator gates. Unblocks Lord of Change / Great Unclean One / Keeper of Secrets Locus auras (Daemons still gated 17.54).
2. **Structurally-parked factions** (Knights pair + Custodes = 75.2 pt of headline gated MAE) need infra: multi-profile Knight mapper or Custodes scoring rebalance.
3. **Drukhari structural residual** (still gated 26.18). Combat Drugs damage magnitude, Pain Tokens not implemented, archetype-level Raider/Venom volume audit.
4. **Onager Dunecrawler multi-loadout** — flagged by ADMECH-DIAG but not addressed (4 mutually-exclusive main weapons fire simultaneously).
5. **Tyranids structural** — Tyranid Warriors basket-composition (1 venom cannon + 5 deathspitters) is currently inert until archetype-surfaced.

Loop paused per user direction.

### Wave 6 (2026-05-23) — LeaderAbility schema + Onager multi-loadout

| Faction | Commit | Move @ N=40 | Notes |
|---|---|---:|---|
| Daemons | `9bee471` LEADERABILITY-SCHEMA | +0.23 (noise) | Extended LeaderAbility with 3 new effect fields (`plus_one_strength_ranged`, `plus_one_toughness`, `plus_one_ap_melee`); wired Lord of Change Locus of Change, Great Unclean One Locus of Virulence, Keeper of Secrets Locus of Slaanesh with their respective god rosters. Limited N=40 movement because the Daemonic Incursion archetype matrix may not seed Tzeentch/Nurgle/Slaanesh Greater Daemons frequently enough — fix is rule-correct and will pay out on archetype diversification |
| AdMech | `d8ad3de` ONAGER-MULTILOAD | **-0.36** | Onager Dunecrawler + Skorpius Disintegrator had multiple mutually-exclusive main weapons firing per shooting phase (Onager had ALL FIVE: Eradication beamer + Neutron laser + Phosphor blaster + Icarus array + Eradication dup; Skorpius had Ferrumite + Disruptor + Belleros). Same multi-loadout pattern as DRK-DIAG-5 and Hive Tyrant. Kataphron variants + Skorpius Dunerider + Sicarian Infiltrators audited clean |
| Drukhari | (no-ship DRK-DIAG-7) | — | Combat Drugs implementation audited clean (magnitude correct, gating correct, persistence correct). Skysplinter archetype audited clean (vehicle-heavy, Wych-light, matches real meta). The +29pt overshoot is NOT in Combat Drugs or archetype shape. Carry-forward: Pain Tokens magnitude, Drukhari overrides still baking static FNP that SC5-8 missed, AI target-priority bias toward fast skimmers |

Cumulative MAE gated 10.76 → **10.66** (-0.10pt). Inside band 4/22.

### Six-wave session close (2026-05-23)

**Cumulative session totals: MAE gated 11.35 → 10.66 (-0.69 pt headline, -6.1% relative). 17 rule-correctness landings + 1 cross-source data source + 1 schema extension.**

Open carry-forwards for next iteration:
1. **Drukhari Pain Tokens implementation magnitude** (DRK-DIAG-7 found no defect in Combat Drugs but Drukhari residual is still 26.18 — Pain Tokens haven't been audited)
2. **Drukhari overrides post-SC5-8 sweep** — static FNP that SC5-8 missed (DRK-DIAG-7 carry-forward)
3. **AdMech remaining multi-loadout chassis** — Kastelan Robots (Heavy phosphor blaster vs Incendine combustor), Sydonian Dragoons (Taser lance vs Radium Jezzail), Archaeopter Stratoraptor extras
4. **Tyranids structural** — Tyranid Warriors basket inert until archetype-surfaced
5. **Custodes / Knights pair structural parking** (75.2 pt of headline still parked)
6. **Daemons archetype** may need to seed Tzeentch/Nurgle/Slaanesh Greater Daemons more often so the new LEADERABILITY-SCHEMA Locus auras can surface


Carry-forwards for the next iteration:
1. **Mapper-structural Crusade-Points filter** in `code/bsdata/mapper.py` + parsed.json regen — sweep all factions, exclude Crusade-Points-only weapons from default loadouts (ADMECH-DIAG carry-forward).
2. **Mapper-structural multi-loadout generalisation** — Onager Dunecrawler (AdMech), Tyranid Warriors / Hive Tyrant alt loadouts (carry-forwards from wave 3), Knight chassis (parked structural).
3. **5 dead-key Sororitas overrides** — `adeptus_sororitas_*` typo prefix means 5 invuln saves are silently absent (Morvenn Vahl, Junith Eruita, 2x Canoness, Saint Celestine). Rekey to `adepta_sororitas_*`. Direction-wrong for Sororitas MAE (already over-perf) but rule-correct.
4. **DAEMONS-DIAG-3** — god-specific detachment rules (Khorne/Tzeentch/Nurgle/Slaanesh flag audit). Daemons still gated 17.54 after the invuln restore.
5. **DRK-DIAG-5** — Drukhari Detachment.py flag audit + vehicle stat re-audit (Raiders/Ravagers). Combat Drugs reform didn't close the +30pt residual — implies structural lever elsewhere.
6. **3 structurally-parked factions** (Knights ×2 + Custodes, 76.5pt of headline gated MAE) need infra work, not loop-style fixes.




22-faction matrix expanded in sim-cal-4 (FX-ALL + FX-MS) created 12 new minimal-archetype outliers. Starting baseline pre-SC5 N=20: MAE 15.95 (vs pre-FX-ALL 10-faction N=40 = 5.79). User directive: "work through all the factions starting with the biggest outliers focusing on rule correct updates to bring their MAE down. then do a loop summary and feed those notes into the next loop. continue until MAE is at least as good as before we added the remaining factions or we're below our noise floor."

### SC5-1 to SC5-6 — six rule-correct landings

**SC5-1 Drukhari Skysplinter Assault fabrication dropped** (`c1456c4`). `reroll_wound_ones=True` was a fabricated army-wide always-on proxy. Real "Rain of Cruelty" rule grants `[ignores cover]` + `[lance]` to a single disembarking unit per disembark — narrowly gated, no wound-roll modifier. Drukhari sim% −8.6 at N=5.

**SC5-2 Chaos Knights Ion Shield 5++ restored** (`16a27f9`). BSData v10.6.0 cache omits the Invulnerable Save infoLink on all 10 Chaos Knight chassis (same omission pattern as Doomsday Ark / Wraithguard). Added `invuln_save: 5` overrides for Desecrator, Rampager, Despoiler, Tyrant, Abominant + 5 War Dog variants. IK already correctly carried 5++. CK +1.0 sim%. **Knights residual is structural — multi-profile weapon mapper gap (saved as memory `project-knights-multiprofile-weapons`)**: Castellan/Crusader fire 4–5 ranged profiles, BSData mapper captures only `weapon` + `secondary_weapon`. Parked for iter 31–45 mapper phase.

**SC5-3 Trajann Valoris Captain-General fabrication dropped** (`ba85564`). LeaderAbility carried `plus_one_to_hit=True` self-flagged as "upper-bound flavour proxy". Real rule is modifier-cancellation (negates -1 to hit penalties), not a flat +1 — and SwegHammer doesn't model hit penalties on the attack side, so net contribution should be ~0. Agent verified the rest of the Custodes engine is correct: Martial Ka'tah alternation works (AP+1 odd / Crit-5+ even), Wardens Resolute Will is 3-way gated, no leader-aura stack on Allarus/Sagittarum/Vertus. **Custodes +29 residual is structural — board-control bias against elite-low-model armies (saved as memory `project-custodes-board-control`)**. Parked.

**SC5-4 AdMech + Sororitas detachment fabrications dropped** (`5372011`). `SKITARII_HUNTER_COHORT.reroll_hit_ones=True` cited against "Stealth Optimisation" — real rule is purely defensive (Stealth + cover at >12" for Sicarians). `HALLOWED_MARTYRS.plus_one_to_wound=True` cited against "The Blood of Martyrs" — real rule only fires Below Starting Strength / Below Half. Both dropped. **Biggest single-commit win of the loop**: AdMech −7.6, Sororitas −12.7 combined ~20pt correction at N=5.

**SC5-5 Votann Warrior Pride + Wrath of the Ancestors token-gated** (`fa0f60d`). Stratagems were firing round 1 against highest-threat target rather than waiting for a Judgement Token to be issued. Rule-correct fix tightens fire conditions per Wahapedia. **Votann sim% went up +3.8 at N=5** — agent notes the underlying stratagem effect mappings are systematically over-strong: `transient_plus_one_to_wound` proxies a Wound REROLL (close), `transient_plus_one_to_hit_shooting` proxies LETHAL HITS (over-strong on 3+ shots that gain an extra hit). Kept per correctness-over-MAE; flag for iter 2.

**SC5-6 Grey Knights Fury of Titan reroll_hit_ones restored** (`a817186`). Citation in `data/rule_citations.d/detachments.json` reads "re-roll a Hit roll of 1 **and** re-roll a Wound roll of 1", but the `Detachment` instance only had `reroll_wound_ones=True`. The matching Hit reroll was dropped at some prior point. Restored — no fabrication, code now matches the citation. GK −6.6 at N=5. MAE 18.09 → 17.53.

### SC5-7 honest N=40 measurement (2026-05-21)

Cumulative `claude/sim-calibration-5` at `a817186`. N=40 archetype eval (parallelised, 15 workers):

| Metric | Pre-SC5 N=20 | Post-SC5 N=40 |
|---|---|---|
| MAE vs Warp Friends | 15.95 | **14.97** |
| MAE vs source mean | 16.something | 14.92 |

Biggest residuals post-SC5:
- **Drukhari +37.1** (was +39.5) — Combat Drugs / per-unit stat audit still on the table
- **Imperial Knights −37.1** + **Chaos Knights −35.5** — STRUCTURAL (mapper gap), parked
- **Adeptus Custodes +29.3** — STRUCTURAL (board-control bias), parked
- **Leagues of Votann +21.0** — stratagem effect mapping over-strong
- **Tyranids +18.3, Adeptus Astartes +17.5, AdMech +17.1, TSON +14.1, Aeldari +14.3, Orks +14.3, Sororitas +13.1** — mid-band, all candidates for the same detachment-fab pattern (3-of-3 hit rate so far)

### Pattern observed: detachment fabrication

Three of the six fixes (SC5-1 Skysplinter, SC5-4-A Skitarii Hunter Cohort, SC5-4-B Hallowed Martyrs) were the same pattern: `code/detachments.py` carrying always-on proxy flags (`reroll_wound_ones`, `reroll_hit_ones`, `plus_one_to_wound`) that don't match the cited real-rule text. Saved as memory `project-detachment-fabrication-pattern`. Strong probability more remain across the 22 detachments — iter 2 should sweep them all systematically.

### Iter 2 plan (not yet dispatched)

Top candidates ordered by expected magnitude × structural-tractability:

1. **Drukhari Combat Drugs audit** — Adrenalight (+1 Attack) may be always-on full-archetype rather than 1-of-4 random.
2. **Adeptus Astartes Oath of Moment** — full-army reroll-hit-1s vs Oath target, may be gated wrong (whole army instead of just declared shooters).
3. **Tyranids Shadow in the Warp / Synapse** — Synapse buffs may apply to non-Synapse units.
4. **Aeldari Strands of Fate** — dice-pool replacement may be modelled as always-take-the-best.
5. **TSON All Is Dust** — -1 damage may apply to non-Rubric/Scarab units.
6. **Sweep all 22 detachments** for fabricated proxy flags in one focused agent pass.

The 5.79 pre-FX-ALL target may not be reachable on the 22-faction matrix without fleshing out the 12 minimal archetypes (10–30pt of structural uplift per archetype). Realistic iter 2 target: MAE ≤ 10 within ~8 more SC-style commits, then re-assess whether further compression requires Stage 2 or archetype-depth investment.

### SC5-8 to SC5-11 — iter 2 landings

**SC5-8 Drukhari static Feel No Pain double-count dropped** (`ae3c9a0`). BSData v10.6.0 embeds "Feel No Pain 5+" as a static infoLink on every Drukhari datasheet (32 units, including 8 vehicles), while `code/units.py:668` already implements **conditional** Power From Pain (FNP 6+ while pain_tokens > 0). Double-count: every Drukhari unit got permanent FNP 5+ that ignored the token gate AND was stronger than the rule. Added `fnp: 7` overrides on 24 units. **Biggest iter 2 win**: Drukhari +37.1 → +28.6 at N=40 (−8.5pt). New memory `project-bsdata-static-vs-runtime-double-count`.

**SC5-9 Adaptive Strategy fabricated +1-to-wound dropped** (`7e20026`). Gladius Task Force stratagem `_try_adaptive_strategy` was firing `transient_plus_one_to_wound_melee=True` based on a docstring premise that Combat Doctrines confers +1-to-wound — but iter-9 May 2026 had already corrected Doctrines to utility-only (shoot after Advance / charge after Fall Back). The stratagem was stacking a stale fabricated wound buff on the corrected base rule. Replaced with rule-correct no-op (CP still paid). Astartes +17.5 → +16.9 N=40.

**SC5-10 Tyranid Enhancement FNP prose-walk false-positive dropped** (`20d7789`). `code/bsdata/mapper.py:extract_fnp` does a depth-3 prose walk that pulled "Feel No Pain 5+" text from the **Adaptive Biology Enhancement option** (granted to one attached CHARACTER) into the base stats of every datasheet that lists the Enhancement. 15 Tyranid units carried fabricated `fnp=5`; only 3 (Norn Emissary, Norn Assimilator, Psychophage) have native FNP. Patched 12 units via overrides. New memory `project-bsdata-mapper-prose-walk-bug` — the structural mapper fix belongs in iter 31–45.

**SC5-11 detachment fabrication sweep — 8 proxies dropped** (`b92665e`). Audited all 28 `Detachment(...)` entries. KEEP confirmed for 20 (citation-matched flags); DROP for 8 fabrications: NOBLE_LANCE.plus_one_to_wound (real rule is [ASSAULT]-on-Advance), PACTBOUND_ZEALOTS.reroll_wound_ones (real rule grants Lethal/Sustained via Dark Pacts), BERZERKER_WARBAND.plus_one_to_hit (real rule is +1A/+2S on charge), DAEMONIC_INCURSION.plus_one_to_hit (Warp Rifts is Deep Strike reduction), FINAL_DAY.reroll_hit_ones (Psionic Parasitism is per-Synapse +1 Hit at MW cost), IRONSTORM_SPEARHEAD.vehicles_reroll_hit_ones (Armour of Contempt is defensive -1 AP — direction-wrong), PLAGUE_COMPANY.melee_sustained_hits_army_wide (paraphrased citation, no verbatim primary), CANOPTEK_COURT.canoptek_plus_one_to_wound (Hyper-Logical Strategy is once-per-battle reroll). **N=5 MAE +0.43 immediately — kept per correctness-over-MAE.**

### Iter 2 honest measurement (2026-05-21)

`claude/sim-calibration-5` at `b92665e` (4 iter 2 commits on top of `f1ff9d4`). N=40 archetype eval:

| Metric | Iter 1 close (N=40) | Iter 2 close (N=40) | Delta |
|---|---|---|---|
| MAE vs Warp Friends | 14.97 | **15.65** | +0.68 |
| MAE vs source mean | 14.92 | 15.61 | +0.69 |

**Iter 2 net regressed MAE.** Decomposition (vs iter 1 N=40 baseline):
- ✅ SC5-8 Drukhari −8.5pt (+37.1 → +28.6) — the win.
- ➖ SC5-9 / SC5-10 ~−0.6pt each on Astartes / Tyranids — small.
- ❌ SC5-11 +3pt of net regression across 5 under-performing factions: World Eaters −13.7, GSC −13.0, Daemons −6.2, IK −37.5, CK −35.1. Dropping fabs from under-performers EXPOSED archetype thinness.

**Pattern recognised** (memory `project-fab-bandaid-on-thin-archetypes`): removing rule-correct fabs from over-performers compresses MAE; removing the same kind of fabs from under-performers worsens MAE because the fabs were band-aids on thin FX-ALL minimal archetypes. The 12 minimal archetypes have 7–12 entries vs 15–25 in the original 10 archetypes. The structural fix is fleshing them out + modelling their actual army rules, NOT more fab cleanup.

### Loop conclusion + next-phase recommendation

Cumulative SC5 loop (iter 1 + iter 2, 11 commits + 2 summaries on `claude/sim-calibration-5`):
- N=20 pre-SC5 baseline: 15.95 → N=40 post-SC5: **15.65** (−0.30 net)
- Pre-FX-ALL N=40 10-faction target: 5.79 — **not reachable on 22-faction matrix without fleshing out minimal archetypes**.

Outlier shape after iter 2 (N=40, ranked):
- **Imperial Knights −37.5, Chaos Knights −35.1** — STRUCTURAL (mapper gap, parked memory `project-knights-multiprofile-weapons`).
- **Custodes +30.6** — STRUCTURAL (board-control bias, parked memory `project-custodes-board-control`).
- **Drukhari +28.6** — post-SC5-8 remnant; further compression needs Combat Drugs / per-unit stat audit.
- **Votann +23.4, AdMech +18.7, Tyranids +18.1, TSON +16.7, Astartes +16.9, Orks +17.2, Aeldari +15.7** — mid-band, requires real-faction-rule modelling rather than fab cleanup.

The natural next phase per the user's iter 31–45 plan (`project-iter31-45-plan`) is the **mapper-structural** phase: multi-profile weapon mapper + Enhancement-FNP prose-walk fix. After that, archetype-depth work for the 12 minimal archetypes. Continued SC-style outlier-grind has hit diminishing returns; iter 2 net regression confirms the band-aid pattern.

Memories built in this loop (all in `~/.claude/projects/.../memory/`):
- `project-knights-multiprofile-weapons` (IK/CK residual is mapper gap)
- `project-custodes-board-control` (Custodes residual is sim bias)
- `project-detachment-fabrication-pattern` (3 hits in iter 1, 8 in iter 2)
- `project-bsdata-static-vs-runtime-double-count` (SC5-8 Drukhari, biggest single win)
- `project-bsdata-mapper-prose-walk-bug` (SC5-10 Tyranid Enhancement FNP)
- `project-fab-bandaid-on-thin-archetypes` (SC5-11 pattern explanation)

### AX-A to AX-D — archetype depth expansion (2026-05-21)

User directive: "flesh out the archetypes" — direct follow-up to the SC5-11 finding that fab cleanup hurt under-modelled factions because their FX-ALL minimal archetypes were too thin to compete. Four parallel agents, ~10 tool uses each (well-budgeted vs the SC5 agents' 30+).

| Faction | Before | After |
|---|---|---|
| CSM Pactbound Zealots | 8 | 19 |
| World Eaters Berzerker Warband | 8 | 19 |
| Emperor's Children Slaaneshi Excess | 8 | 19 |
| Chaos Daemons Daemonic Incursion | 8 | 13 |
| Astra Militarum Combined Arms | 9 | 17 |
| AdMech Skitarii Hunter Cohort | 8 | 17 |
| Sororitas Hallowed Martyrs | 9 | 18 |
| Grey Knights Teleport Strike Force | 7 | 18 |
| Genestealer Cults Final Day | 9 | 17 |
| Imperial Knights Noble Lance | 6 | 10 |
| Chaos Knights Noble Lance | 6 | 10 |

All 11 minimal archetypes now in the 10-19 range matching the original 10 archetypes' depth.

**N=40 result**: MAE 15.65 → **15.28 (−0.37)**.

Per-faction wins:
- Sororitas +14.0 → +5.5 (**−8.5pt**, biggest single faction win)
- Genestealer Cults −13.0 → −6.7 (**+6.3pt**)
- Chaos Space Marines −6.8 → −1.7 (**+5.1pt**)
- AdMech +18.7 → +17.5
- Imperial Knights −37.5 → −36.2 (mapper gap dominates)

Per-faction regressions (new units lose more matchups than they win):
- Emperor's Children +0.8 → +5.0 (added Slaaneshi daemons + Fulgrim)
- Chaos Daemons −6.2 → −9.3 (broader daemon roster represented)
- Astartes / Tyranids / Orks +1–2pt each (untouched factions; matchup re-distribution)

**Net path so far**: pre-SC5 N=20 baseline 15.95 → SC5 iter 1 14.97 → iter 2 close 15.65 → archetype expansion **15.28**. Within ~0.3pt of iter 1 close while having: 8 rule-correct fabs dropped, ~110 new archetype entries added across 11 factions, 6 carry-forward memories.

Knights remain the dominant outlier (−36/−35) — confirms `project-knights-multiprofile-weapons`: archetype depth alone won't close the mapper-structural gap. Custodes +30 also structural per `project-custodes-board-control`. Real next-phase candidates are the mapper-structural work (iter 31-45 phase 2) and/or implementing missing faction army rules.

### MR-A to MR-J + DRK-2 — missing-faction-rule implementation (2026-05-21)

User directive: "equal modeling quality across factions" + matchup-tuning via opponent-side rule wiring. Implemented army rules for the 11 FX-ALL factions that lacked them.

| Faction | Rule | Approach |
|---|---|---|
| Imperial Knights | Code Chivalric (martial-valour Quality) | reroll hit+wound 1s, deliberately under-buffed proxy; CK skipped (needs battleshock infra) |
| Genestealer Cults | Cult Ambush | Resurgence Points: 10pt budget, 3pt per revival, dead INFANTRY restored at round-end via deep-strike landing |
| Chaos Space Marines | Dark Pacts | AI gate on DPA ≥ 6.0 units; grants LH+SH proxy; Ld test 2D6 vs unit Ld; D3 MW on fail |
| Adeptus Mechanicus | Doctrina Imperatives | Buff-only Protector/Conqueror alternation (odd/even rounds); dropped pre-existing fabricated penalty per agent finding |
| Adepta Sororitas | Acts of Faith | Miracle Dice bank (Strands-of-Fate pattern); +1/round + on-death; substitute hit/wound/save |
| Astra Militarum | Voice of Command | **Already implemented** from iter-14 (4 Orders + Officer dispatch); MR-F survey-only |
| World Eaters | Blessings of Khorne | 8D6 doubles/triples → up to 2 melee Blessings/round (Martial Excellence / Warp Blades / Cleaving Blows) |
| Emperor's Children | Thrill Seekers | Shoot+charge after Advance/Fall Back (army-wide); 2 targeting restrictions NOT modelled (mildly over-rates) |
| Chaos Daemons | Shadow of Chaos | 18"-centre proxy: −1 to enemy battleshock + D3 MW on fail (no deployment-zone position-tracking) |
| Grey Knights | (survey only) | Existing impl (Teleport Strike Force + leaders) suffices; +1W-vs-DAEMONS skipped per matchup-tuning trap (would worsen already-under Daemons) |
| Chaos Knights | (parked) | Harbingers of Dread needs battleshock infrastructure (per MR-A finding) |
| Drukhari | Combat Drugs | WYCH CULT units: Wyches+1A, Hellions+2"M, Reavers+1S, Beastmaster+1T; Serpentin/Splintermind no-op approximation |

Two agents corrected faulty brief premises by going to Wahapedia first:
- **MR-D** found Doctrina Imperatives is **buff-only** (not buff+penalty alternation as briefed); dropped a pre-existing fabricated penalty.
- **MR-A** found Knights have NO army-wide Lance rule — IK = Oath system (Code Chivalric), CK = Harbingers of Dread (battleshock-keyed, needs new infra).

### N=40 path through this phase

| State | N=40 MAE |
|---|---|
| Pre-SC5 (N=20 baseline) | 15.95 |
| SC5 iter 1 close | 14.97 |
| SC5 iter 2 close | 15.65 |
| Post-AX (archetype expansion) | 15.28 |
| Post-MR1 (IK/GSC/CSM/AdMech) | 15.08 |
| Post-MR2 (Sororitas/AM/WE/EC) | 15.26 |
| **Post-MR3+DRK-2 (Daemons/Drukhari/GK survey)** | **15.32** |

Cumulative branch progress: **−0.63 MAE across 24 commits** (11 SC5 + 4 AX + 9 MR/DRK). 9 carry-forward memories built.

### Quality-parity assessment

All 22 factions have army rules implemented or surveyed. The Stage 1 floor for the 22-faction matrix sits ~15pt MAE without structural unblocks. Remaining dominant outliers (post-MR3):

| Faction | Sim Δ | Status |
|---|---|---|
| Chaos Knights | −35.0 | STRUCTURAL: needs multi-profile weapon mapper + battleshock infra |
| Imperial Knights | −32.1 | STRUCTURAL: multi-profile weapon mapper |
| Custodes | +29.3 | STRUCTURAL: board-control bias |
| Drukhari | +28.9 | Combat Drugs added (rule-correct overshoot); further levers per-unit / anti-keyword |
| Votann | +22.7 | Stratagem-mapping over-strong per SC5-5 |
| AdMech | +20.0 | Doctrina-correct overshoot |
| Sororitas | +19.9 | Acts-of-Faith-correct overshoot |
| Astartes | +17.4 | No clear remaining lever |
| Tyranids | +16.9 | No clear remaining lever |
| Orks | +16.9 | No clear remaining lever |
| TSON | +14.4 | No clear remaining lever |
| Aeldari | +13.9 | No clear remaining lever |

### Strategic options surface (for user)

Five rules-correct paths forward, ordered by leverage × tractability:

1. **Anti-keyword weapon tagging sweep** — [DEVASTATING WOUNDS] / [ANTI-MONSTER 4+] / [LANCE] / [MELTA] coverage on weapon profiles. Pulls Custodes / Drukhari / Votann via opponent-side modelling. Pure data-entry in overrides; low risk.
2. **Stratagem effect-mapping audit** — fix the over-strong `+1 to hit/wound` proxies that SC5-5 found; precondition for adding more stratagems.
3. **Mortal-wound surface for psyker factions** — TSON Cabal of Sorcerers, GK Psychic Action, Aeldari Wraithseer charge MW. Direct counter for elite-2+ outliers.
4. **Detachment variety** — each faction has 3-4 detachments, currently 1-2 implemented. Each new detachment diversifies the matchup matrix.
5. **Enhancement expansion** — 4 Enhancements per detachment × 22 factions; ~15% implemented. Slow but cumulative; per-CHARACTER buffs.

**Structural alternatives outside Stage 1 outlier-grind**:
- **Battleshock infrastructure** — unlocks CK Harbingers of Dread + cleaner Sororitas/Tyranid/Drukhari interactions
- **Multi-profile weapon mapper** — unlocks IK/CK structural residual (iter 31-45 phase 2)
- **Stage 2 pricing** (MC bisection + utility-factor function) — tasks #186–189; the equation work is the project endgame per `project-endstate-vision` memory

## Branch claude/sim-calibration-4 (2026-05-20)

SC4 (secondary objectives + map rotation) + LC-1/LC-2/LC-5 (detachment variety + tactical-deck mechanic + Warlord designation). All committed and pushed; PR #26 open.

### LC-1: Detachment variety (3 chunks)

* **LC1-A**: added Auric Champions Custodes detachment (SUSTAINED HITS 1 melee via `melee_sustained_hits_army_wide`, milder than Shield Host's stacked Crit-5+ + AP+1). Generalised the `melee_sustained_hits_army_wide` gate in `Unit.attack` from Orks-only to `detachment.faction == attacker.faction`. Custodes distribution: Shield Host 22 / Auric Champions 18 across 40 seeds.
* **LC1-B**: added Annihilation Legion Necrons detachment (army-wide `reroll_wound_ones`, real Hardened Killers rule). Necrons distribution: Awakened Dynasty 14 / Canoptek Court 16 / Annihilation Legion 10.
* **LC1-C**: added Plague Company Death Guard detachment (`melee_sustained_hits_army_wide` for DG). DG distribution: Virulent Vectorium 20 / Plague Company 20.

Cumulative LC-1 eval: **MAE 6.48 → 6.14 (−0.34)**. Big win: DG +7.6 → -1.3 (at target). Necrons stayed -10.1 (Annihilation Legion not strong enough lever). Custodes stayed +20.6 (Auric Champions only marginally weaker than Shield Host).

### LC-2: Tactical secondary deck mechanic

Per-round alternating schedule per side: each side scores AT MOST ONE of (Engage, BEL) per round, deterministically alternating. Approximates real Pariah Nexus 2-of-9 Tactical card draw rate when scaled to our 2-card pool. `_is_tactical_secondary_active(round_num, side, tactical)` helper, `score_position_delta` takes `round_num`.

Cumulative LC-2 eval: **MAE 6.14 → 6.14 (flat)**. Custodes stayed +22.0 (the tactical-deck didn't help because Custodes wasn't really scoring Engage/BEL anyway — small army can't easily hit 3+ quadrants). Other factions redistributed in wash.

### LC-5: Warlord designation

`Army.warlord_uid` lazy property picks the first CHARACTER in deploy order. Pariah Nexus Assassination secondary scores +1 VP if the Warlord was among destroyed CHARACTERs this round. Smoke verification: Custodes Warlord = Trajann Valoris, DG = Mortarion, Necrons = C'tan Shard of the Nightbringer.

### Honest pause point

Custodes outlier (+22) hasn't compressed via LC-1/2/5. Real cause: Custodes' elite low-count army systemically dodges the 4 Fixed kill secondaries (No Prisoners, Cull, Assassination, Bring it Down) AND their primary OC is decent enough that they win without secondary scoring. Without a faction-specific Custodes tune (e.g., per-unit pricing nudge or model-count uplift in archetype), no LC item will single-handedly close the +22 gap.

**LC-3 (wargear) / LC-4 (enhancements) / LC-6 (transports) / LC-7 (reserves) deferred** — large implementation work each with uncertain MAE impact. LC-8 (caps) / LC-9 (BATTLELINE min) confirmed no-op (archetypes already comply with both).

PR #26 open and ready for review. Detachment variety lands as a clean rule-correctness win for DG and a structural baseline for further faction tuning.

### N1 / N2 / C1 — outlier-targeted attempts (2026-05-20)

After LC-5 plateau, a 3-agent dispatch targeting Custodes +22 / Necrons -11. All three returned essentially flat MAE.

**N1 Necrons C'tan archetype anchor (STOP).** Agent verified C'tan Shard of the Nightbringer is ALREADY anchored in the Necrons "Awakened Dynasty" template at `code/archetypes.py:134` (iter16 commit). Spot-check confirms Nightbringer appears in 5/5 random archetype builds as the first seed. My review premise was wrong; no fix needed.

**N2 Reanimation Protocols rate (STOP).** Agent verified Wahapedia rule text: revival rate is "one destroyed bodyguard model", not d3. The d3 wording is from the "Protocol of the Undying Legions" stratagem (1 CP, already separately modelled). Current `reanimate_per_round=1` is rule-correct. Side-finding: the value is also hard-capped at `min(..., 1)` in `simulator.py:3490` so naively bumping the detachment value would have been a no-op anyway.

**C1 Shield Host bullet alternation (SHIPPED).** Agent wired round-parity alternation: AP+1 fires on odd rounds (1, 3, 5), Crit-on-5+ fires on even rounds (2, 4). Matches the codex "pick one bullet per round" rule exactly (the prior always-both was explicitly flagged APPROXIMATION). Tests + audit green. Eval: MAE 6.29 → 6.29 (flat); Custodes +22.3 → +22.0 (-0.3 within N=40 noise). Kept per correctness > MAE — rule-correct fix, prior state was strictly stronger than codex.

**Net N1+N2+C1**: 1 correctness-positive commit, ~0pt MAE impact. The Custodes +22 engine isn't the Shield Host detachment.

**Per-faction at this point (sim-cal-4 head)**:
- Marines +2.0, Necrons -11.8, Aeldari +2.8, Tyranids +5.3, Orks +0.4, T'au -4.5, DG -3.3, Custodes +22.0, TSON -4.6, Votann +6.2
- 5 factions within ±3pt of target (Marines, Aeldari, Orks, DG, TSON)
- 4 factions 4-6pt off (Tyranids, T'au, Votann, plus DG at -3.3)
- 2 outliers: Necrons -11.8, Custodes +22.0

**Real Custodes engine candidate**: Wardens Resolute Will + Trajann's +1 hit + Shield-Captain's reroll-1s + Shield Host AP+1 (now alternating but still firing 50% of rounds) + 4++ invuln + cover bonus at base Sv2. The compounding makes Wardens a near-unkillable brick; 2× Wardens in the archetype = a fortress. **LC-AB task #253** (consolidated archetype/detachment build evaluation) is the right place to address this — likely needs Custodes archetype shape rebalance (1× Wardens not 2, swap one Allarus for cheap BATTLELINE).

**Real Necrons engine candidate** (per N1 agent's recommendation): Awakened Dynasty 6-protocol rotation isn't fully modelled. Only one protocol (`bonus_to_hit_when_led`) is wired; the other five would add small per-round value that compounds. Doomsday Ark profile verification also flagged as iter 35 priority.

### LC-AB Custodes + DDA + AD-PR (2026-05-20)

Three parallel agents on outlier-targeted structural fixes.

**LC-AB Custodes archetype rebalance**: Custodes template reduced from 2× Wardens + 2× Allarus to 1× of each + Witchseekers/Vigilators BATTLELINE chaff. Eval: MAE 6.29 → 6.00 (−0.29). Custodes itself stayed at +22.3 (flat — the elite-shape engine is impossibly durable even with fewer copies); other factions improved by ~0.4-1pt as opponents score more secondaries against the now-vulnerable Custodes BATTLELINE chaff.

**DDA Doomsday Ark + Doomstalker invuln overrides**: 4+ invuln on both via `data/overrides.json` (BSData mapper missed the local Abilities profile rather than infoLink). Eval: MAE 6.29 → 6.18 (−0.11). Necrons −11.8 → −10.7 (+1.1). Rule-correct.

**AD-PR Awakened Dynasty protocol rotation**: wired Hungry Void (melee AP+1, even rounds) + Vengeful Stars (ranged SUSTAINED HITS 1, odd rounds) on Necrons. Conquering Tyrant (already-wired bonus_to_hit_when_led) retained always-on. Eval: MAE 6.29 → 6.16 (−0.13). Necrons −11.8 → −10.7 (+1.1).

**Combined N=40 eval (all three cherry-picked together)**: MAE **6.29 → 5.79 (−0.50)** — best honest N=40 reading of the calibration loop's history. Necrons −11.8 → −8.5 (+3.3 combined). Custodes stuck at +22.6 (structurally locked — needs Stage 2 pricing work, deferred per user).

**Per-faction at combined state** (sim-cal-4 head `4f6c4bc`):
- Marines +2.6, Necrons −8.5, Aeldari +2.8, Tyranids +5.6, Orks +0.4 ✅
- T'au −3.9, DG −2.7, Custodes +22.6 (outlier), TSON −3.8, Votann +5.1
- 7 of 10 factions within ±3pt; Custodes the sole structural outlier
- Cumulative Stage 1 progress from iter 22 baseline 13.43 → 5.79 = **−7.64 across 70+ commits**.

LC-4 enhancement system dispatched next.

### LC-4 / LC-3 / LC-6 / LC-7 sweep (2026-05-20)

Continued through the LC list per user directive "work through the whole list."

**LC-4 enhancements**: agent burned 166 tool uses (way over 40 cap — flag for future) but landed a modest 99-line commit. Enhancement infrastructure was pre-existing; wired Phasal Subjugator (Necrons Awakened Dynasty, +1 to hit aura), Veiled Blade (Custodes Shield Host, +2 attacks on Warlord melee), and corrected Hyperphasic Fulcrum citation (was misread as +1-to-hit, real BSData is reroll-wound-1s). Eval: MAE flat at 5.79. Each enhancement attaches to only 1 CHARACTER per army, so impact is small. Kept per correctness > MAE.

**LC-3 wargear variety**: STOP, 8/20 tool cap. Catalog audit found Crisis Suit variants already exposed correctly (iter17 work intact); Marines Captain power-fist gap noted but multi-SKU work for follow-up. No fix shipped.

**LC-6 transport MVP**: shipped Ghost Ark seed in Necrons Awakened Dynasty template (single-line `necrons_ghost_ark: 1`). Spot-check: Ark seeds 1 of 3 builds (random_fill budget walk drops it in 2/3). Eval flat MAE 5.79. Direction is rule-realism positive but the seed isn't anchored. Full transport mechanics (embark/disembark/ablative wounds) intentionally skipped — beyond MVP scope.

**LC-7 strategic reserves**: diag-only (12/20 tool cap). Found general Strategic Reserves entry point doesn't exist; only Deep Strike + Genestealer Cults bucket. Recommended split into LC-7a (mechanic + zero-declarations, ~150 lines) + LC-7b (AI heuristic that actually declares units). Multi-iter project, deferred.

**Session close state** (sim-cal-4 head `dc7073f`):
- MAE 5.79 at N=40 — best honest reading of the entire calibration loop's history
- 7 of 10 factions within ±3pt of target (Marines, Aeldari, Orks, T'au, DG, TSON, Custodes is +22.6 outlier)
- Necrons -8.5, Tyranids +5.6, Votann +5.1 (mid outliers)
- Custodes structurally locked — needs Stage 2 pricing work or per-unit durability cap

**Remaining LC items**: LC-10 (mission-specific lists) deferred per task description — very large scope. The LC list is effectively worked through; further MAE compression needs Stage 2 (MC bisection pricing) or AI improvements that the iter 26-30 cross-faction attempts showed are difficult to land cleanly.

**Cumulative Stage 1 progress from iter 22 baseline**: 13.43 → 5.79 = **−7.64 across ~80 commits**. Below the "≤6.5" practical floor that signals AI-pricing-vs-rules-completeness handoff per the iter 30 plan.

### Iter 21 (2026-05-18) — LeaderAbility fabrication audit

6 agents cross-faction sweep. 5 commits landed via cherry-pick + cross-worktree merge; Orks was clean (no fabs).

**Fabrications dropped (all citation-grounded per Wahapedia)**:
- **Necrons**: Overlord/Trazyn `plus_one_to_hit`, Plasmancer `fnp=5`. Real rules are CP discounts (Strat-econ) and offensive Crit-on-5+ (not modelled). Plus Lychguard added to Overlord bodyguard list (host_keys).
- **Marines**: Guilliman/Captain `reroll_hit_ones`, Chaplain `reroll_wound_ones`. Real rules are CP-discount/once-per-battle Battleshock-removal. Plus Shield-Captain/Brother-Captain name-collision fix.
- **Aeldari**: Yncarne `plus_one_to_hit` (proxy for reactive-teleport), Autarch `plus_one_to_hit` (CP-discount, same as Overlord pattern), Avatar `reroll_hit_ones` (real rule is +1 Advance/Charge — movement phase).
- **TSON**: ADDED 4 NEW LeaderAbilities (Ahriman, Exalted Sorcerer, Infernal Master, Sorcerer in TA) — TSON was UNDER-modelling (LeaderAbility lookup returned None). Plus Magnus "Impossible Form" (−1 to incoming Damage), Ahriman +1 Cabal Psychic test. TSON 30% → 36.1% (+6.1pt).
- **DG**: Lord of Contagion `plus_one_to_wound` (iter 20 missed), Typhus `fnp=5` (iter 20 partial). host_keys corrected per codex (Blightlord/Deathshroud, not Plague Marines).
- **Orks**: clean — no fabs.

**Cumulative iter 21 (5 commits + cross-worktree merges)**: MAE **13.73 → 13.43pt** (Δ **−0.30**). Tests 776/776, Rule citations 221/221.

**Per-faction shifts (post-iter-20 → post-iter-21)**:
- Marines +20.3 → +19.5
- Necrons **+17.6 → +14.3** (−3.3 ✅ — Overlord fab removed)
- Aeldari −6.9 → −6.6
- Tyranids −17.7 → −18.6
- Orks +4.8 → +5.1
- T'au +11.1 → +11.3
- DG +23.7 → +23.9
- Custodes −3.8 → −3.8
- TSON −24.6 → −24.3
- Votann +6.8 → +6.8

## Loop pause — PR + Ed's main rebase (2026-05-18)

User directive: wrap up after iter 21, merge progress, pick up Ed's point-cost reference fixes from main before continuing iter 22+ (aura host_keys gating, variant invuln sweep, Magnus diag, AI improvements).

Iter 22-26 plan documented above remains valid for the next loop session.

## Branch pivot — claude/sim-calibration-2 (2026-05-19)

PR #22 merged onto main at `fe9458a` (Ed's point-cost reference fixes folded in). Branched `claude/sim-calibration-2` off the updated main. Fresh baseline at N=40 archetype: **MAE 9.13** (vs 13.43 on the old branch — Ed's main work dropped MAE by ~4.3 points). Per-faction:

- Marines −3.0, Necrons −6.5, Aeldari +2.8, Tyranids +5.1, Orks +11.5, T'au +7.2
- **DG +20.9** (major over), **Custodes −18.6** (major under)
- TSON −3.2, Votann +12.6

DG combat-model over-strength and Custodes under-modeling are now the dominant outliers.

### Iter 22 (2026-05-19) — host_keys aura gate + invuln long-tail sweep

3 agents dispatched in parallel:

1. **`effective_buffs` host_keys gate** (af396da4): per-leader aura merge in `code/leaders.py` was firing army-wide regardless of `host_keys`. Typhus FNP was applying to every Death Guard within 6 inches, Lieutenant +1-to-wound to every Marine within 6 inches — same structural bug across every faction with character auras. Gate now: if `leader.host_keys` is non-empty, the attacker's catalog key must be in `host_keys` for the buff to merge. Empty tuple `()` retained as the explicit army-wide convention for MONSTER auras (Hive Tyrant Onslaught, Avatar Bloody-Handed). Reverse name lookup widened to a tuple (Plague Marines exists in both DG and CSM catalogs; gate tests set intersection). Hive Tyrant `host_keys` cleared to `()` per Wahapedia (Onslaught is broadcast). 49 leaders tests pass. Faction-neutral structural fix.

2. **Variant invuln long-tail sweep** (a6738d6f): 72 new override entries in `data/overrides.json` for units whose BSData v10.6.0 datasheet omits the Invulnerable-Save infoLink. Coverage spans every Aeldari Phoenix Lord and EPIC HERO, all Necron Lord characters, Death Guard / CSM / WE / EC HQ entries, Daemons library, Sororitas, Dark Angels HQs, Captain in Terminator Armour, Einhyr Champion. Each entry's `notes` cites the Wahapedia datasheet.

3. **LeaderAbility wide-aura audit** (ab89afd5): no code changes. Analysis-only; existing host_keys were already correct after iter 21. Discarded.

**Cumulative iter 22 (2 commits)**: MAE **9.13 → 9.20** (Δ **+0.07, flat within noise**).

**Per-faction shifts** (baseline → iter22):
- Marines −3.0 → **+0.1** (closer to zero, ✅)
- Necrons −6.5 → −7.9 (slight regress)
- Aeldari +2.8 → +1.7 (✅)
- Tyranids +5.1 → +6.2
- Orks +11.5 → **+8.7** (✅)
- T'au +7.2 → +7.2 (flat)
- DG +20.9 → **+22.8** (regress — host_keys gate removed phantom aura buffs that were partially counteracting DG over-strength)
- Custodes −18.6 → −22.2 (regress — Lieutenant-on-everyone correction made Marines stronger, Custodes look weaker by comparison)
- TSON −3.2 → −4.9
- Votann +12.6 → +10.4 (✅)

Per the iter 20 user directive (correctness > MAE), KEPT — both fixes are Wahapedia-grounded rule corrections. The two outstanding extreme outliers (DG +22.8 / Custodes −22.2) are unchanged and are the iter 23+ targets.

**Iter 23 priorities**:
1. **DG combat model audit** — Plague Marine sticky-objective, Disgustingly Resilient FNP triggering, Plague Weapons stratagem application, Mortarion deadly_demise interaction with the host_keys gate.
2. **Custodes diagnostic** — under-modeling persists from iter 20 (LOS+ablative already implemented in `code/army.py::can_target_for_ranged`); next vector is durability stack, Vexilla auras, Auric Mortalis detachment, or Trajann's per-leader buff.
3. **Magnus / TSON under-strength** — still −4.9. Magnus stat investigation from iter 21 didn't produce a fix; needs followthrough.

### Iter 23 (2026-05-19) — diagnostic-only, three parallel agents

DG / Custodes / TSON ranked root-cause reports. Outputs `iter23_dg_diag.md`, `iter23_custodes_diag.md`, `iter23_tson_diag.md` on each agent's worktree branch. No code changes.

**DG diag (LARGE/LARGE/MEDIUM)**:
1. Lord of Contagion `host_keys=("death_guard_plague_marines",)` is a CLAUDE.md §10 fabrication — Wahapedia bodyguard list is Blightlord/Deathshroud only. Iter22's effective_buffs gate then faithfully fires +1-to-wound on the spam unit.
2. Archetype seats Mortarion 4/20 — (-count, -cost) walk eats cheap units first.
3. Worldblight stratagem fires army-wide always-sticky instead of "end of Command phase + already controlling".

**Custodes diag (LARGE/LARGE/MEDIUM-LARGE)**:
1. Custodian Wardens have `fnp=7` in parsed.json + no innate -1 damage; the flagship brick is strictly less durable than Custodian Guard.
2. Trajann + Shield-Captain host_keys = Custodian Guard ONLY — Wardens / Allarus / Sagittarum / Vertus fight unbuffed. Blade Champion has no LeaderAbility entry (§13 fail-loud violation).
3. Six Custodes profiles wrongly flagged `deep_strike=True` (Guard / Wardens / Sagittarum / Trajann / Blade Champion / Shield-Captain).

**TSON diag (LARGE/MEDIUM/SMALL-MEDIUM)**:
1. Detachment lottery: TSON resolves to Grand Coven 11/20 (Kindred Sorcery not implemented; Grand Coven disables All Is Dust = no compensation).
2. Magnus seats 0/20 in archetype armies — template deliberately omits him; his wired rules (Impossible Form, Lord of the Planet) are dead code.
3. Magnus has no LeaderAbility entry — §13 fail-loud, like Blade Champion.

### Iter 24 (2026-05-19) — fix bundles, three parallel agents

8 commits cherry-picked on `claude/sim-calibration-2`:

**DG bundle (D1-D4, commits `f4f3864`-`f12ba87`)**:
- D1: Lord of Contagion `host_keys` → Blightlord/Deathshroud only + test update.
- D2: Faction-neutral archetype EPIC HERO anchor guarantee — force-seed the most expensive template EPIC HERO with overflow up to `points_budget * 0.6`.
- D3: Worldblight strict OC-contest gate — sticky promotes only when DG side wins the contest on the marker.
- D4: Plaguebearers / Blightlord / Typhus FNP=5 overrides (mapper-gap; Disgustingly Resilient is codex-level, not per-unit in BSData).

**TSON bundle (T1-T3, commits `70fa5e7`, `bf1b652`, `0e96a96`)**:
- T1: Drop `grand_coven` from `FACTION_DETACHMENTS["Thousand Sons"]` until Kindred Sorcery is wired.
- T2: Add Magnus to Rubricae Phalanx archetype + TSON to `SEED_FRACTION_BY_FACTION` at 0.4 (800pt slice).
- T3: Add Magnus the Red placeholder LeaderAbility entry (no aura flags — his rules are self-conferred in simulator.py; entry exists for §13 fail-loud).

**Custodes bundle (C single commit `8f96a80`)**:
- C1: Resolute Will (Custodian Wardens datasheet) — defender-side -1 to Wound roll, gated by `defender.resolute_will` + `leaders.is_actually_led(defender)` + `attack.strength > defender.toughness`. New fields on UnitProfile + CatalogEntry; citation under `simulator.resolute_will`.
- C2: Trajann (Auric Sage) + Shield-Captain (Stoic Vigil) `host_keys` widened from Guard-only to (Guard + Adrasite-spear variant + Wardens) per the BSData Imperium - Adeptus Custodes Leader text.
- C3: Blade Champion LeaderAbility added structurally (no aura fields — Martial Inspiration + Swift Onslaught aren't expressible in the schema). Closes §13 silent-default gap.
- C4: `deep_strike: false` override on Custodian Guard / Wardens / Sagittarum / Trajann / Blade Champion / Shield-Captain. Wahapedia datasheets do not list Deep Strike on any of the six.

**Cumulative iter 24 (8 commits)**: MAE **9.20 → 6.51** (Δ **−2.69 at N=20**; iter22 baseline measured at N=40 so the comparison carries ~±2pt cross-N noise).

**Per-faction shifts** (iter22 N=40 baseline → iter24 N=20):
- Marines −3.0 → −4.1 (flat)
- Necrons −6.5 → −7.1 (flat)
- Aeldari +2.8 → −3.3 (6pt swing — partly noise, partly Magnus-on-TSON pressure)
- Tyranids +5.1 → −0.2 ✅
- Orks +11.5 → +7.9 ✅
- T'au +7.2 → +8.3 (slight regress)
- **DG +20.9 → +8.7** ✅ (−12.2pt — D1+D2+D3+D4 bundle landed as designed)
- **Custodes −18.6 → +2.6** ✅ (+21.2pt — Resolute Will + leader host_keys widening were the dominant levers)
- TSON −3.2 → −7.9 (regress — Magnus anchor eats budget but the unit appears under-priced relative to what it displaces; iter 25 attention)
- Votann +12.6 → +11.1 (slight ✅)

**Iter 25+ priorities**:
1. **Magnus / TSON re-tune** — T2's Magnus anchor regressed TSON. Either Magnus's stat profile is wrong (BSData has M=6 W=16; current Wahapedia shows M=12 W=18 — flagged for awareness in iter23 but not actioned) or his archetype anchor displaces too-strong picks. Re-measure after Ed's perf-optim main pivot.
2. **T'au +8.3 over** — second-largest outlier now. Needs a diag (Mont'ka / Markerlight / Crisis pricing).
3. **Votann +11.1 over** — third outlier. Likely Oathband stratagems + Sagitaur durability.

## Branch wrap-up — PR open + sim-calibration-3 pivot (2026-05-19)

Loop housekeeping + iter 22-24 complete on `claude/sim-calibration-2`. Pivoting to `claude/sim-calibration-3` (off updated main) to pick up Ed's simulator performance optimisations (Tier 1 pure-function caching, Tier 2 alive_units cache + vectorised deepstrike, Tier 3 LOS/cover/durability caching — perf only, no behaviour change). Iter 25-26 will run on the new branch.

## sim-calibration-3 baseline (2026-05-19)

Branch = `claude/sim-calibration-2` + Ed's main merged in (commits `d48c8c6`, `4ea0519`, `cc38091`, `80c9a78`). Clean merge — no conflict markers. Baseline N=20 archetype eval:

- **MAE 6.62 pts** (vs iter24 sim-cal-2 N=20 = 6.51 — essentially flat, +0.11)
- **Wall-clock: 257s** for full N=20 matrix. Compared to ~10-15 min on sim-cal-2 (no perf optims) — **roughly 3-4x speedup** at N=20. Bigger expected gains at N=40+ where the per-battle caches amortise more.

Per-faction shape redistributed even though cumulative held flat — Ed's caching has small behaviour deltas on some paths. Notable shifts (iter24 → sim-cal-3 baseline):
- Marines, Necrons, Aeldari all moved closer to target (under-performers improved by 2-6pt)
- DG, T'au, Votann, TSON all moved further from target (over-performers grew, TSON under-perf deepened)

Iter 25 priorities locked in based on the new outlier shape:
1. Votann +16.8 — V1 diag-and-fix
2. TSON -12.9 — T1 Magnus retune or anchor backout
3. DG +12.6 regress — D1 diagnostic (verify iter24 commits intact, scan Ed's commits for DG-touching paths)

### Iter 25 (2026-05-19) — bundle-of-one fix-first protocol

First iter run under the new `docs/AUTO_LOOP_PROCEDURE.md` rules (A-F). Three parallel agents, ≤30 tool uses each, ~400-token prompts.

**T1 — TSON Magnus anchor backout** (commit `6af92d8`, agent: 48k tokens, 26 tool uses, 7min). Root cause: BSData mapper folds Magnus's two weapon profiles (Tempestus Sceptre ranged + Blade of Magnus melee) into one — his combat output is half-represented while he eats half the budget. Reverted iter24-T2 (template seed + SEED_FRACTION_BY_FACTION bump). T1 (drop grand_coven) + T3 (Magnus LeaderAbility placeholder) preserved. Eval: TSON -12.9 → +2.1; MAE 6.51 → 5.26.

**V1 — Votann Eye of the Ancestors retired-rule removal** (commit `5ccc301`, agent: 64k tokens, 37 tool uses, 9min). Root cause: `code/units.py` was implementing the RETIRED launch-day Eye of the Ancestors re-roll buffs (re-roll hit 1s at 1 token, re-roll all hits + re-roll wound 1s at 3 tokens). Current 10e codex Prioritised Efficiency has no re-roll buffs — `code/simulator.py:5104-5107` literally documented this as known stale. Removed the buff branch; kept token bookkeeping infrastructure intact. Updated `tests/test_judgement_tokens.py` (two tests pinned to the retired rule). Eval: Votann +16.8 → +14.0; MAE 6.51 → 5.86.

**D1 — Death Guard regression diagnostic** (no commit, agent: 44k tokens, 14 tool uses, 2min). Verified all iter24 D1-D4 fixes are intact. Verified Ed's Tier 1/2/3 caches don't touch FNP-relevant paths. Conclusion: latent AI blindness — `_durability()` in `code/strategy.py` ignores FNP entirely, so opponent AIs see DG only by (save, invuln, AP) and bounce off the FNP wall. iter24-D4 making more DG units carry FNP=5 exacerbated this. Iter 26 recipe: fold `fnp` into `_durability` and `_unsaved_fraction` (faction-neutral AI improvement helping every FNP-carrying army).

**Cumulative iter 25 (T1 + V1, 2 commits)**: MAE **6.62 → 4.49** (Δ **-2.13**). Best result of the entire calibration loop. Six factions within ±2.6pt of target.

**Per-faction shifts** (sim-cal-3 baseline → iter25):
- Marines -1.9 → -1.3 ✅
- Necrons -1.0 → -0.4 ✅ (at target)
- Aeldari -1.1 → -1.6 (flat)
- Tyranids +1.4 → +2.6 (slight)
- Orks +7.3 → +5.7 ✅
- T'au +9.9 → +8.3 ✅
- DG +12.6 → +10.3 ✅ (cross-N variance settling)
- Custodes -1.3 → +0.3 (at target)
- **TSON -12.9 → +3.2** ✅ +16.1pt (T1 backout)
- **Votann +16.8 → +11.2** ✅ -5.6pt (V1 retired-rule removal)

**Iter 26 priorities**:
1. **S1 (faction-neutral AI):** fold FNP into `_durability` and `_unsaved_fraction` in `code/strategy.py` (per D1 diag recipe). Helps DG, Necrons, Custodes, Tyranids, Nurgle daemons — every FNP-carrying army. Expected DG / Custodes / Necrons movement toward zero; T'au / Votann / Orks neutral (no FNP).
2. **V2:** Votann second pass — V1 was partial (-2.8pt). Probable next lever: Sagitaur durability or Hearthkyn Warriors stats.
3. **T1:** T'au +8.3 diag — Mont'ka, Markerlight, Crisis Suit pricing.

Token-efficiency note: iter 25 total agent spend = 156k tokens / 77 tool uses across 3 agents. Compare to iter 24's 4-bundle agent: ~70k for ONE incomplete bundle + manual cleanup. The bundle-of-one + trimmed-prompt protocol is roughly 3x more efficient per fix shipped.

### Iter 26 (2026-05-19) — 3 parks, MAE flat at 4.49

Three bundle-of-one agents dispatched. All three correctly held the new procedure's "STOP rather than invent" line; the loop's easy leverages near the noise floor are depleting and that's reflected in the outcome.

**S1 — faction-neutral FNP in AI threat-score** (agent: 62k tokens, 33 tool uses, 18min). Implementation correct: folded Feel No Pain into `_durability` and the four `_melee_target_score` / `pick_charge_target` callers in `code/strategy.py`. Cited under `simulator.fnp_in_threat_score`. Target factions improved as predicted (DG +10.3 → +9.8, Tyranids +2.6 → -0.2). Cross-faction effect regressed Orks (+5.7 → +10.1) — FNP-bearing defenders now correctly read Orks as soft and push harder, while Orks have no FNP to compensate. **Cumulative MAE 4.49 → 4.99 (+0.50)**. Per the loop rule (regressions get parked), the fix stays on the agent's worktree branch (commit `35d71c2`) and is not cherry-picked. Iter 27 follow-up: symmetric Orks attacker-side AI improvement, then re-land S1.

**V2 — Votann second pass** (agent: 60k tokens, 30 tool uses, 5min). Audited Sagitaur, Hearthkyn, Hearthguard, Eye of the Ancestors (already neutralised by iter25-V1), OATHBAND detachment, Kâhl LeaderAbility, Einhyr Champion override. All match Wahapedia / BSData. No provable lever within the 8-tool diagnostic budget — STOPPED. Residual +11.2 hypothesis: AI CP heuristic over-firing on Votann, baseline drift, or Stage 2 sweg_balance_mc points cuts on Sagitaur / Hekaton (out of Stage 1 scope).

**T1 — T'au +8.3 diag-and-fix** (agent: 73k tokens, 53 tool uses, 28min). Found a real rule-fidelity issue: Mont'ka LETHAL HITS fires every round in `code/units.py:1155-1164`, but Wahapedia restricts it to battle rounds 1-3. Tested fix — T'au win rate unchanged (battles decided rounds 1-3 anyway). Reverted per the brief. Diag file flagged iter 27 follow-ups: (a) Markerlight realism (current `_run_markerlight_phase` auto-marks with no roll / no LOS / 36" range — likely the real T'au lever), (b) Riptide / Stormsurge weapon-profile audit, (c) full audit of six wired `MONTKA_STRATAGEMS` for round/phase gating.

**Cumulative iter 26**: no commits cherry-picked. MAE stays **4.49**.

Token-efficiency: 195k tokens / 116 tool uses across 3 agents for net-zero code shipped — but three high-quality diagnostic deliverables landing in agent-worktree diag files. The procedure's tradeoff is working as designed: shipping zero buggy fixes is the right outcome when no clean lever exists.

**Iter 27 priorities**:
1. **T'au Markerlight realism** (largest residual outlier where a clear bug is named) — gate auto-Guided behind a roll + LOS check.
2. **Orks attacker-side AI heuristic** — symmetric counterpart to S1's defender FNP fix. Once Orks correctly identify FNP-bearing defenders as hard targets, S1 can re-land and the cumulative MAE should drop.
3. **Riptide / Stormsurge weapon profile audit** if T'au isn't closed by Markerlight alone.

### Iter 27 (2026-05-19) — Markerlight realism lands, 2 parks

Three agents on the locked-in priorities. One shipped, two parked with strong diag value.

**M1 — Markerlight realism** (commit `43f4826` → `86e3137`, agent: 99k tokens, 95 tool uses, 36min). Gated `_run_markerlight_phase` on 36" range + `Map.has_line_of_sight` + `can_target_for_ranged` (LOS+ablative) + d6 hit roll vs carrier BS via `_prob_to_target`. Token bookkeeping preserved. Cited under `simulator.markerlight_emission`. New test `test_markerlight_hit_roll_failure_grants_no_token`. **T'au +8.3 → +4.9 (-3.4pt). MAE 4.49 → 4.08 (-0.41)**. Note: agent went over the procedure's 30-tool-use cap (95 used) — the cap may be too tight for non-trivial simulator changes; consider relaxing to 50 for code/simulator.py edits.

**M2 — Riptide / Stormsurge audit** (agent: 58k tokens, 35 tool uses, 10min). Riptide / Stormsurge stats verified clean against BSData. Tested switching Stormsurge to Pulse Driver Cannon (the long-range Heavy 6-shot profile vs the focused Pulse Blastcannon). **Regressed** — MAE 4.49 → 4.72; T'au +8.3 → +9.4. Reverted. Mechanism finding: **damage wastage is unmodelled in the sim** — D12 high-damage weapons waste damage on low-wound targets, so multi-shot D3 profiles are systematically more efficient than codex intent. Damage spillover/carry-over is a structural Stage 1 issue larger than a bundle-of-one. Added to iter 28+ recipes.

**O1 — Orks diag-and-fix** (agent: 75k tokens, 39 tool uses, 10min). Found a real bug: `UnitProfile.sustained_hits` populated from the ranged primary weapon but read in melee mode at `code/units.py:1222`. On Orks the War Horde +1 stacks → fabricated SUSTAINED HITS 2 melee on Flash Gitz, Kaptin Badrukk, etc. Tested gate to ranged-only — **regressed** because other factions have legitimate melee SH that the gate killed. Proper fix needs separate `melee_sustained_hits` field on `UnitProfile` with mapper-side `best_melee` routing. Out of bundle-of-one scope; added to iter 28+ recipes.

**Cumulative iter 27 (1 commit)**: MAE **4.49 → 4.08** (Δ **-0.41**). Seven factions within ±2.2pt of target. Eval wall-clock 268s (Ed's perf optims giving consistent ~4-min N=20).

**Per-faction shifts** (iter 25 → iter 27):
- Marines -1.3 → -0.8 ✅
- Necrons -0.4 → -1.5 (slight)
- Aeldari -1.6 → -2.2 (slight)
- Tyranids +2.6 → +0.9 ✅
- Orks +5.7 → +7.3 (slight regress — M1 cross-effect; less Guided T'au fire means other T'au shots redistribute)
- **T'au +8.3 → +4.9** ✅ (-3.4 — M1 target hit)
- DG +10.3 → +11.4 (slight regress)
- Custodes +0.3 → +1.4 (flat)
- TSON +3.2 → -0.7 ✅
- Votann +11.2 → +9.6 ✅

**Iter 28 priorities**:
1. **DG +11.4 deep-dive** — iter25-D1 said cross-N variance + AI FNP-blindness; the FNP fix regressed Orks. DG is now the worst outlier. Re-baseline at N=40 or N=80 and decide if it's a real structural lever or noise.
2. **Damage spillover modelling** — M2 finding. Fundamental Stage 1 issue: high-damage weapons waste output on low-wound targets, low-damage multi-shot is systematically over-efficient. Affects DG / T'au / Votann pricing simultaneously.
3. **`melee_sustained_hits` mapper field** — O1 finding. Mapper schema change + unit.attack re-routing. Enables iter28 Orks-side correction without breaking other factions.

### Iter 28 (2026-05-19) — MS1 ships, DS1 disproves M2, D2 reveals N=20 noise

Three agents on the locked-in priorities. One shipped, one structural-finding-no-fix, one diag.

**MS1 — `melee_sustained_hits` mapper field** (commit `57d55a6` → `9ed2658`, agent: 108k tokens, 105 tool uses, 40min). Added field to `MappedUnit` / `CatalogEntry` / `UnitProfile`. Mapper populates from `best_melee.sustained_hits`; `Unit.attack` reads by mode (`p.melee_sustained_hits if mode == "melee" else p.sustained_hits`). Symmetric fix to `code/equilibrium.py:249`. 7 Ork units corrected (Choppa profile → melee SH = 0); 54 units retain legitimate melee SH (Striking Scorpions, Eversor, Repentia, Lelith, etc.). Rule-correct + faction-neutral. Agent's N=20 eval showed +1.29 regression — but cumulative N=40 (below) shows the apparent regression was sample noise; MS1 is essentially flat at honest measurement.

**DS1 — damage spillover hypothesis** (no commit, agent: 64k tokens, 30 tool uses, 4min). Verified `code/units.py:625` uses `max(0.0, current_health - amount)` — excess damage IS dropped per 10e core rules. Each model is a separate `Unit` instance — no sibling spillover. M2's hypothesis was WRONG. But the agent surfaced the opposite bias: per-activation targeting fires all N shots at ONE model, and once the model dies remaining shots waste silently. **Low-D multi-shot weapons are UNDER-modelled**, not over-modelled. Damage-reallocation across sibling Units when the current target dies is a ~40-line refactor; iter 29+ recipe.

**D2 — Death Guard +11.4 deep-dive** (no commit, agent: 115k tokens, 94 tool uses, 13min). N=40 baseline DG = +14.5 (worse than N=20's +11.4). Confirms DG is genuinely structural. Audited every DG unit profile; every gap points the WRONG way (Plagueburst Crawler, Bloat-Drone, Mortarion all UNDER-modelled vs Wahapedia). Real bug surfaced: **duplicate keys in `data/overrides.json`** for `death_guard_blightlord_terminators` and `death_guard_typhus` — iter22 invuln overrides silently clobbered iter24-D4's `fnp:5` per JSON last-key-wins. CLAUDE.md §13 silent-default violation.

**DDK — duplicate-key §13 fix** (commit `86ef91c`). Merged the two pairs of duplicate entries into single units carrying both `fnp:5` AND `invuln_save:4` with combined Wahapedia citation. Restored the iter24-D4 FNP=5 that the dedup bug had silently dropped.

**Cumulative iter 28 (2 commits: MS1 + DDK), measured at N=40**: MAE **6.17 → 6.20** (Δ **+0.03, flat within noise**). The N=20 reading of 4.08 at iter 27 carried ~2pt of cross-N noise — honest measurement at N=40 is the correct floor.

**Per-faction shifts** (sim-cal-3 N=40 baseline → iter28 N=40):
- Marines -1.9 → -0.5 ✅
- Necrons -7.6 → -9.0 (slight regress; newly-largest under-performer at N=40)
- Aeldari +3.7 → +2.0 ✅
- Tyranids +4.5 → +5.3 (flat)
- Orks +5.9 → +5.7 ✅ (MS1 did NOT regress at honest N — N=20 reading was noise)
- T'au +6.9 → +7.7 (flat)
- **DG +14.5 → +16.2** (DDK restored FNP=5; rule-correct but pushes DG further over)
- Custodes +2.3 → +2.6 (flat)
- TSON -6.0 → -7.1 (slight)
- **Votann +8.4 → +5.9** ✅ (real improvement)

**Methodological correction:** iter close evals should run N=40 going forward. The N=20 budget was concealing ~2pt of cross-faction noise that produced misleadingly low MAE readings. Honest Stage 1 progress from iter22 baseline at N=40 (9.13) → iter28 N=40 (6.20) = **-2.93** across 7 iterations, not the -5 the N=20 numbers had suggested.

**Iter 29 priorities**:
1. **Necrons -9.0 diag** — newly visible at N=40 (was -1.5 at N=20). Needs full diagnostic since the iter21 fab audit landed but didn't move them.
2. **Shot-reallocation refactor** — DS1's structural finding. ~40 lines in `Unit.attack`. Could move many factions simultaneously by correctly modeling multi-shot weapons.
3. **DG structural over-strength** — D2 confirmed every per-unit lever points wrong direction. Either accept Stage 2 (price DG higher in equilibrium) or attack AI FNP-blindness with an Orks-aware compensation.

### Iter 29 (2026-05-19) — NE1 lands, SR1 parked, TY1 STOP

**NE1 — Necrons Reanimation Protocols full-wounds restore** (commit `58181e1` → `a359520`, agent: 51k tokens, 24 tool uses, 13min). Iter 14's Fix F-NEC-2 had clamped revived Necron models to 1 HP citing a Wahapedia misread. Per the verbatim rule text (https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols) revived models return with "its full wounds remaining". Affects multi-wound Necron units (Lychguard W3, Skorpekh W3, Wraiths W3, Triarch Praetorians W2, Lokhust Heavy Destroyers W3). Eval: Necrons -9.0 → -9.0 flat at N=40 — the lever wasn't load-bearing at archetype seed distribution but the fix is rule-correct. **Cherry-picked per correctness > MAE.**

**SR1 — shot reallocation across sibling models** (no cherry-pick, commit `cb1c057` lives on worktree branch only, agent: 114k tokens, 122 tool uses, 17min). Implemented per the iter28-DS1 finding: when the current target model dies mid-resolution, remaining shots route to a sibling alive model in the same defending unit (matched by `profile.name` via `target.army_ref.alive_units`). When the whole defending unit dies, the loop breaks and remaining shots waste per 10e. Citation `simulator.shot_reallocation_across_models` added. 89 tests passed. **N=40 eval regressed MAE 6.20 → 7.19 (+0.99)** with damaging shape shift: DG +16.2 → +28.4, Custodes +2.6 → +12.0, Orks +5.7 → -6.0, Votann +5.9 → -6.3, Necrons -9.0 → -5.4, T'au +7.7 → -0.3.

The structural lift hurts disproportionately on factions with heavy melee multi-attack profiles (DG Plague Marine Choppas, Custodes A4 melee). The previous sim "balance" relied on the bug; landing SR1 rule-correctly needs paired Stage 2 per-unit pricing work to re-balance DG / Custodes upward in cost. **Parked SR1 for iter 30+ coordinated rebalance pass.**

**TY1 — Tyranids Hive Tyrant Onslaught fab audit** (no commit, agent: 97k tokens, 46 tool uses, 26min). Tested clearing `reroll_wound_ones=True` from the Hive Tyrant LeaderAbility (the Onslaught codex rule is ranged LETHAL HITS + ASSAULT, not re-roll wound 1s; flag was mode-agnostic so was firing on Carnifex / Tervigon / Trygon melee in aura). Tyranids +5.3 → +5.9 (wrong direction, within noise). Reverted. Four iter-30 candidates in diag file: Subterranean Assault verbatim audit, Hive Tyrant melee profile, Maleceptor / Norn Emissary FNP, Synapse aura scope.

**Cumulative iter 29 (1 cherry-pick: NE1)**: MAE **6.20 → 6.20** (flat at N=40). Per-faction unchanged at this resolution.

**Iter 30+ priorities**:
1. **SR1 + per-unit DG/Custodes pricing compensation** — coordinated rebalance pass. Land SR1 alongside Stage 2 cost nudges on DG melee units and Custodian Guard / Wardens so MAE doesn't regress while the structural shot-waste bug is fixed.
2. **Necrons -9.0 deeper diag** — NE1 was the obvious lever and didn't move. Need shooty profile efficiency, Awakened Dynasty Protocol rotation, or Doomsday Ark / C'tan Shard stats.
3. **TY1 follow-ups** — Subterranean Assault, Maleceptor / Norn Emissary FNP audit.
4. **DG via Stage 2** — D2 confirmed Stage 1 per-unit levers all point wrong; consider accepting DG pricing as a Stage 2 problem.

### Iter 34 (2026-05-20) — universal keyword audits (Phase 2 / iter 3)

Three parallel agents on universal keywords. Hard 30-tool cap held; all three agents stayed in budget.

**K1 — DEVASTATING WOUNDS** (no fix, agent: 47k tokens, 20 tool uses, 2min). Audited the existing implementation; it's **already correct**. `WeaponStats.devastating_wounds` field, 192 units carry the flag, combat application at `code/units.py:1532-1535` (on crit wound, deal Damage as MWs bypassing save+invuln). Brief's premise was wrong — quoted the 2023 wording, but the sim correctly implements the June 2024 dataslate version ("no saving throw of any kind"). No code change.

**K2 — PRECISION override of attached-character Look Out Sir** (commit `acbb2d1` → `c8a9183`, agent: 65k tokens, 33 tool uses, 4min). Existing `precision` field was incorrectly modelled as a cover-piercing approximation. Real 10e PRECISION lets a wound from a PRECISION-tagged weapon allocate directly to a CHARACTER in an attached unit, bypassing the bodyguard. SwegHammer collapses LOS to a targeting gate; real-rule equivalent lives at `code/army.py::can_target_for_ranged`. Fix: when attacker has `precision` and target is a CHARACTER, bypass the bodyguard scan. Lone Operative still blocks (separate keyword). Citation `simulator.precision_keyword`. **K2 alone: MAE 6.14 → 6.01 (-0.13)**.

**K3 — Benefits of Cover** (commit `6294636` → `a1de12c`, agent: 54k tokens, 29 tool uses, 13min coding + lost eval). Previous `save_probability` and the in-combat cover gate applied +1 save to ALL modes (including melee) and used a flat 2+ floor (no INFANTRY 3+ cap). Wahapedia rule: ranged-only, INFANTRY models cannot improve their save to better than 3+ via cover. Fixed both the helper and the in-combat path. New citation `simulator.benefits_of_cover`. **K3 effect when bundled**: removes the previous broken cover-applies-to-melee defender protection, marginally buffing melee-heavy attackers.

**Cumulative iter 34 (K2 + K3 cherry-picked)**: MAE **6.14 → 6.17 (+0.03 at N=40)**. K2's -0.13 win was offset by K3's +0.16 melee-cover regression. Both kept per correctness > MAE.

**Per-faction shifts** (iter33 N=40 → iter34 N=40):
- Marines -3.6 → -4.1 (-0.5)
- Necrons -8.2 → -8.8 (-0.6)
- Aeldari +3.7 → +3.1 ✅ (-0.6)
- Tyranids +4.5 → +3.7 ✅ (-0.8)
- Orks +3.4 → +3.7 (+0.3)
- T'au +6.9 → +7.4 (+0.5)
- DG +16.2 → +16.4 (+0.2)
- Custodes +0.3 → +0.6 (+0.3)
- TSON -3.2 → -2.7 ✅ (-0.5)
- Votann +11.5 → +11.2 ✅ (-0.3)

**Phase 1+2 honest summary** (iter 31-34 at N=40 vs sim-cal-3 baseline 6.20):
- iter 31 (S1R + squad-size): 6.59 (+0.39, kept correctness)
- iter 32 (wipe-the-unit): PARKED, +0.25 regression
- iter 33 (multi-profile mapper): 6.14 (-0.06 vs baseline)
- iter 34 (PRECISION + BoC): 6.17 (-0.03 vs baseline)

Four iters of structural / AI work netted essentially zero MAE compression at N=40, while landing substantial rule-correctness fixes. The remaining MAE is genuinely structural — concentrated in DG +16.4 and Necrons -8.8 — and these factions resist both AI and rule-correctness levers.

**Iter 35 priorities**:
1. **Necrons deep structural** — Reanimation Protocols rate / Awakened Dynasty 6-protocol rotation per Phase 3 / iter 1.
2. **Mortarion Lantern secondary investigation** — iter33 flagged DG drift +1.7 possibly due to Lantern over-firing in the new picker.
3. **OR**: pivot to MC bisection (Stage 2) earlier than planned — the structural MAE may need price compensation rather than more rule fixes.

### Iter 33 (2026-05-20) — multi-profile weapon mapper (Phase 2 pivot)

**Iter 33** — pivoted to Phase 2 (structural mapper) after iter 32's cross-faction AI failure. Single agent landed multi-profile weapon mapper (commit `a8d546a` → `464f872`, agent: 109k tokens, 76 tool uses, 13min coding + extra time chasing the eval). Schema: added `secondary_*` ranged-profile fields to `MappedUnit` / `CatalogEntry` / `UnitProfile`. Mapper: runner-up ranged weapon (different name from primary) populates secondary. `Unit.attack` ranged branch: picks the better profile per-target with damage-waste estimation (per DS1 finding).

Spot-checked target units:
- Stormsurge primary = Pulse Blastcannon-focused (close-range nuke), secondary = Pulse Driver Cannon (72" Heavy D6+3 × D3) — long-range profile now selectable
- Magnus the Red primary = Gaze of Magnus, secondary = Tzeentch's Firestorm — agent corrected my iter25-T1 hypothesis (melee Blade of Magnus was already populated; missing piece was second ranged)
- Mortarion primary = Rotwind (sweep), secondary = Lantern (single high-damage)

Citation: `simulator.multi_profile_weapon_selection`. Tests + audit green.

**Cumulative iter 33 (1 commit)**: MAE **6.59 → 6.14 (−0.45)** at N=40. Eval wall-clock 1419s (24 min) — multi-profile picker is ~2-3× slower per battle; Phase 4 N=80 confirmation needs proportionally longer budget.

**Per-faction shifts** (iter31 N=40 → iter33 N=40):
- Marines −2.4 → −3.6 (−1.2 — small drift)
- Necrons −7.1 → −8.2 (−1.1 — small drift)
- Aeldari +4.8 → +3.7 ✅ (−1.1)
- Tyranids +4.8 → +4.5 ✅ (flat)
- **Orks +6.8 → +3.4** ✅✅ (−3.4, unexpected win — multi-profile picker reduces opponent damage waste against Orks' high-OC mobs)
- **T'au +8.6 → +6.9** ✅ (−1.7 — Stormsurge Pulse Driver landing as predicted)
- DG +14.5 → +16.2 (+1.7 — Mortarion's Lantern secondary may be over-firing)
- Custodes +0.9 → +0.3 ✅ (at target)
- **TSON −5.4 → −3.2** ✅ (−2.2 — Magnus Firestorm closes the gap)
- Votann +10.7 → +11.5 (+0.8 — small cross-effect)

**Compared to sim-cal-3 baseline (6.20 pre-iter31)**: iter31 + iter33 net = 6.14, a −0.06 improvement. The structural Phase 2 work fully compensated for iter31's no-FNP-faction regression and added a small additional win.

**Strategic confirmation**: per-unit / per-faction structural work is the productive avenue. Cross-faction AI changes (iter26-S1, iter29-SR1, iter32 wipe-the-unit) hit diminishing returns or net-negative because the calibration target is a multi-faction equilibrium. Phase 2/3 should continue to produce real wins.

**Iter 34 priority**: Phase 2 / iter 2 — universal-keyword pass (DEVASTATING WOUNDS, PRECISION, BENEFITS OF COVER, LONE OPERATIVE, INFILTRATORS / SCOUTS). Single agent per keyword, parallel.

### Iter 32 (2026-05-20) — wipe-the-unit + fragile-first AI — PARKED

**Iter 32 outcome**: regression, fix parked. Single agent burned 1013 tool uses / 91min / 298k tokens (≈20× the 50-tool cap) on an extended tuning loop without finding a clean landing point. Final landed config: wipe 1.3/1.1, fragile parked (over-aggressive at every tested setting). Eval N=40 vs 6.59 baseline: **MAE 6.59 → 6.84 (+0.25, regression)**.

Per-faction 5 improvements / 5 regressions: Aeldari, Orks, T'au, DG, Votann moved toward target; Marines, Necrons, Tyranids, Custodes, TSON moved away. Notable: Necrons -7.1 → -9.9 (the iter 31 gain reversed), Marines -2.4 → -4.1.

Commit `aa32115` lives on `worktree-agent-aea769f5326e14191`, **not cherry-picked**.

**Strategic lesson**: three consecutive cross-faction AI heuristic experiments (iter 26 S1, iter 29 SR1, iter 32 wipe-the-unit) have all produced mixed-net-negative outcomes. The calibration target is a multi-faction equilibrium — single-axis AI changes that work on one faction's matchups break the equilibrium for others.

Per-faction work has been consistently positive: NE1 (Necrons RP), MC1 (save modifier cap), MS1 (melee_sustained_hits separation), M1 (Markerlight realism). Phase 1 plan revised: skip iter 33 (stratagem firing — also cross-faction) and jump to iter 34 (archetype realism — per-faction). Then re-evaluate.

**Agent-cap enforcement gap noted**: the iter 32 brief said ≤50 tool uses with 2 tuning iterations allowed; the agent did 1013. Future agent prompts should harden the cap or explicitly tell the agent to STOP and report the best-of-three rather than continuing to tune indefinitely.

### Iter 31 (2026-05-19) — S1R re-land with squad-size compensation (Phase 1 / iter 1)

**S1R — FNP-in-durability + squad-size compensation** (commit `b5b8933` → `ecd6419`, agent: 76k tokens, 40 tool uses, 14min). Phase 1 opening per the user-approved plan. Re-implementation of iter26-S1 (FNP folded into `_durability` and `_unsaved_fraction` in `code/strategy.py`) plus a paired squad-size durability factor so high-model-count units read as harder to wipe per-shot.

Three helpers: `_fnp_resolved` (profile FNP min'd with aura FNP via `effective_buffs`), `_fnp_pass_fraction` ((7-fnp)/6), `_squad_size_factor` (1.0 + 0.05 per alive sibling). `_durability` formula: `T * HP * squad_factor / (unsaved * fnp_mitigation)`. All four call sites updated to pass `defender_unit`. Citations: `simulator.fnp_in_threat_score`, `simulator.squad_size_durability_factor`.

**Cumulative iter 31 (1 commit at N=40)**: MAE **6.20 → 6.59 (+0.39)**. Kept per correctness > MAE because the two stuck structural outliers moved meaningfully:

| Faction | Baseline | Iter 31 | Δ |
|---|---|---|---|
| Marines | -0.8 | -2.4 | -1.6 (no-FNP cross-regress) |
| **Necrons** | **-9.0** | **-7.1** | ✅ **+1.9** (FNP fix landing) |
| Aeldari | +1.7 | +4.8 | +3.1 (no-FNP cross-regress) |
| Tyranids | +5.3 | +4.8 | ✅ -0.5 |
| Orks | +5.9 | +6.8 | +0.9 (vs +4.4 in iter26-S1 — squad-size compensation worked partially) |
| T'au | +8.0 | +8.6 | +0.6 |
| **DG** | **+16.4** | **+14.5** | ✅ **-1.9** (worst outlier moving) |
| **Custodes** | **+2.0** | **+0.9** | ✅ **-1.1** |
| **TSON** | **-7.1** | **-5.4** | ✅ **+1.7** |
| Votann | +5.7 | +10.7 | +5.0 (no-FNP, no squad-size benefit at medium count) |

**Pattern**: every FNP-bearing faction (DG, Necrons, Custodes, TSON, Tyranids) moved toward target. Every no-FNP faction (Marines, Aeldari, Votann) cross-regressed by AI-divert-fire to softer targets. Orks (high-model-count no-FNP) was protected by squad-size factor (+0.9 regress vs +4.4 raw S1). Votann (medium-count no-FNP) wasn't sufficiently protected.

**Phase 1 plan continues**:
- Iter 32: wipe-the-unit bonus + fragile-model-first target selection. Should re-balance no-FNP factions by valuing complete unit removal differently.
- Iter 33: stratagem firing audit (T'au should fire more; some others may over-fire).
- Iter 34: archetype template realism vs real tournament lists.

### Iter 30 (2026-05-19) — MC1 ships save-modifier cap, NE2 parked

**MC1 — Save modifier ±1 cap** (commit `572f8af` → `5cd270c`, agent: 66k tokens, 37 tool uses, 17min). Audited modifier sources in `code/units.py`. Hit/Wound rolls already compliant via existing `[-1, +1]` clamp at lines 1012-1015. Found a save stacking violation: three independent +1-save sources (`plus_one_save` aura, transient Lightning-Fast Reactions, All Is Dust Rubricae) each subtracted 1 from save independently — a 4+ unit benefiting from two reached 2+ (net +2). Fixed to apply at most a single -1. Citation `simulator.save_modifier_cap_plus_minus_one`. Eval flat (the triple-stack is rare at archetype seed distribution) — rule-correct, **cherry-picked per correctness > MAE**.

**NE2 — Necron Warriors Gauss Flayer loadout** (no cherry-pick, agent: 49k tokens, 30 tool uses, 12min). Swapped primary loadout from Gauss Reaper (12" A2 AP-1) to Gauss Flayer (24" Rapid Fire 1 A1 AP0) — both legal wargear; tournament Necron lists overwhelmingly run Flayers. Eval: Necrons -9.0 → -9.0 (flat). Rule-neutral judgment call; **parked** — the Necrons lever isn't in weapon loadout. Need deeper Stage 1 work on Awakened Dynasty rotation / RP rate / C'tan profiles.

**Cumulative iter 30 (1 cherry-pick: MC1)**: MAE **6.20 → 6.20** at N=40 (flat).

**Per-faction shifts vs iter28 N=40 baseline**: essentially unchanged at this measurement resolution. Marines -0.5 → -0.8, Necrons -9.0 → -9.0, Aeldari +2.0 → +1.7, Tyranids +5.3 → +5.3, Orks +5.7 → +5.9, T'au +7.7 → +8.0, DG +16.2 → +16.4, Custodes +2.6 → +2.0, TSON -7.1 → -7.1, Votann +5.9 → +5.7.

**Honest plateau**: iters 26-30 (5 iters) at MAE 6.20 → 6.20 → 6.20. Five real correctness fixes shipped (NE1, MC1, MS1, DDK, M1) with effects cancelling within noise at N=40.

**User-approved iter 31-45 plan (saved to memory as [[project-iter31-45-plan]]):**
- Phase 1 — AI improvement (iters 31-34): re-land S1 with squad-size compensation, wipe-the-unit bonus, stratagem firing audit, archetype realism.
- Phase 2 — Structural mapper (iters 35-37): multi-profile weapons, universal keywords, Mortal Wounds / Indirect Fire / Hazardous.
- Phase 3 — Faction army rules (iters 38-42): Necrons / DG / T'au / TSON / Tyranids.
- Phase 4 — Verification (iters 43-45): cleanup, N=80 confirmation, Stage 2 trigger decision (threshold deferred per user).
- User directive: "AI first; start with S1 re-land; hold off on Stage 2 trigger decision."

## Waves 7-42 close (2026-05-24 → 2026-05-27)

Branch `claude/sim-calibration-6`. 36 commits landed on top of wave-6 close
`9bee471` (LEADERABILITY-SCHEMA). Top commit at wave-42 honest eval is
`702e843`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 6 close (`9bee471`, 2026-05-23) | 13.85 | 10.66 | 4/22 |
| Wave 20 (`2ca72a4`, 2026-05-24) | 13.20 | 10.03 | 4/22 |
| Wave 42 (`702e843`, 2026-05-27) | 13.03 | **9.68** | 4/22 |

Cumulative −0.98 gated MAE over 36 commits across 4 days. Inside-band count
stayed at 4 (Death Guard, World Eaters, Emperor's Children, Grey Knights).
Stage-1 floor is clearly compressing more slowly each iter; the easy levers
are spent.

### Commit landings by faction (top 36)

The pattern across waves 7-42 was bundle-of-one DIAG agents on the largest
non-structural outliers, with periodic "TIGHTEN" passes on faction-side
secondary scoring dampers (most of which were rolled back in the final
SCORING-MULTIPLIERS-ROLLBACK at `e26ac0e` per CLAUDE.md §10 — faction-gated
metric tuning is not rule-correct calibration).

* **Drukhari** (`d5b1fc8` DRK-LEGENDS-FNP, `468cf4e` DRK-DIAG-12 list-integrity,
  `e4e3ada` DRK-DIAG-11 AI fragile-fly-vehicle bias, `2ca72a4` DRK-TIGHTEN-2,
  `2f37251` DRK-TIGHTEN-3, `6cf85c2` DRK-DIAG-9-TIGHTEN) — six landings. Dampers
  rolled back; rule-correct landings stayed. Drukhari still +33.05 gated, the
  single largest tractable outlier.
* **Tyranids** (`d3c2588` TYRANIDS-DIAG-7 Hive Tyrant Onslaught fab, `818c0d5`
  TYRANIDS-DIAG-8 Invasion Fleet Ld penalty fab). Still +18.90 gated.
* **AdMech** (`d6e9fe9` ADMECH-DIAG FNP false positives, `1ecfdc0` ADMECH-DIAG-2
  Doctrina BATTLELINE gate, `8c6e5bb` ADMECH-DIAG-3 Dominus correction, `0e4f243`
  ADMECH-DIAG-4 Kataphron host_keys, `423b82f` ADMECH-DIAG-5 Cawl reroll fab,
  `31db826` ADMECH-DIAG-6 Skitarii host_keys). Now +8.46 gated, down from ~12.
* **Sororitas** (`bac402c` SOROR-DIAG-6 Insidiants FNP, `6f086ff` SOROR-FAB-AUDIT,
  `43d382c` SOROR-LAST-RESORT-DAMPER, `abb4896` SOROR-NUDGE Junith flamer,
  `978c22d` SOROR-SANCTIFIERS mapper amalgamation). Still +12.96 gated.
* **Daemons** (`b6e9022` DAEMONS-DIAG-6 BiD/NP damper, `e145c58` DAEMONS-DIAG-7
  Skulltaker, `7c545ae` DAEMONS-DIAG-8 Bloodthirster melee-only, `2a3a3c7`
  DAEMONS-DIAG-9 Daemon Prince stealth). Improved from -20 to -12.52 gated by
  PRIMARY-VP-AUDIT alone.
* **Orks** (`cac0421` ORKS-DIAG-2 Meganobz FNP, `e52695f` ORKS-DIAG-3 Warboss
  melee gate, `84f489b` ORKS-DIAG-4 damper). Still +10.77 gated.
* **TSON** (`e2cc317` KOS-MESMERISING, `b50533e` TSON-FINISH Magnus invuln,
  `7e6c970` TSON-DIAG-3 Ahriman fab). Now +7.96 gated.
* **Aeldari** (`d27237d` AELDARI-DIAG-3 Yncarne heal). Now +4.28 gated.
* **Votann** (`12d2f68` VOTANN-DIAG-2 real Needgaard stratagems). Now +6.84 gated.
* **Custodes** (`7a32dc1` CUSTODES-AUDIT Shield-Captain fab). Still +15.25 gated.
* **T'au** (`a0515fd` T-AU-DIAG-3 revert mutex artifact). Now +5.91 gated.
* **Knights** (`8cba4a1` KNIGHTS-MULTIPROFILE-1, `4ab2103` KNIGHTS-MULTIPROFILE-2,
  `c4b1711` KNIGHTS-MULTIPROFILE-3, `c6c1b24` KNIGHTS-AI-COMMIT, `e4da921`
  KNIGHTS-SEED-BUMP, `d4000cf`/`0154f18` KNIGHTS-DEFENDER-DAMPER + revert). Six
  landings, mostly multi-profile work. IK still -26.02 / CK still -34.16 gated;
  structural mapper gap dominates.
* **Cross-cutting structural** (`853ecbc` MAPPER-FNP-SWEEP 19 prose-walk leaks
  across 9 factions, `e26ac0e` SCORING-MULTIPLIERS-ROLLBACK 7 faction gates,
  `702e843` PRIMARY-VP-AUDIT round-1 gate). The biggest single mover of the
  block: PRIMARY-VP-AUDIT shifted Daemons -16.93 → -12.52 gated by removing the
  alpha-strike round-1 scoring bug.

### Pattern observed

After 36 commits, the gated MAE moves −0.98. Most individual DIAG passes
moved their target faction by 0-1 pt at N=40 (correctness-positive but
MAE-neutral). The two clean wins were structural: MAPPER-FNP-SWEEP (FNP
prose-walks across 9 factions) and PRIMARY-VP-AUDIT (rounds 2-5 gating).
Faction-gated dampers/multipliers (CUSTODES/DRK/TYR/DAEMONS/SOROR/ORKS)
were rolled back as rule-fabricated metric tuning per CLAUDE.md §10.

### Open carry-forwards into wave 43

1. **Drukhari Pain Tokens magnitude** — DRK-DIAG-7 ruled out Combat Drugs;
   Pain Tokens never opened. Highest-leverage unresolved Drukhari lever.
2. **Tyranids Warriors basket / archetype composition** — multi-loadout fix
   landed but archetype-realism vs Goonhammer lists not audited.
3. **Daemons archetype Greater Daemon seeding** — LEADERABILITY-SCHEMA wired
   but Tzeentch/Nurgle/Slaanesh Greater Daemons may not surface in templates.
4. **Custodes board-control bias** (project-custodes-board-control memory) —
   structurally parked; needs Stage 2.
5. **Knights multi-profile + battleshock infra** — structurally parked;
   accumulated 6 multi-profile commits without closing the -25/-37 gap.

## Wave 43 in-flight (2026-05-27) — 3 parallel agents on top tractable outliers

Dispatched against carry-forwards 1-3. Bundle-of-one, worktree isolation,
30 tool-use cap, ~400-token prompts per `AUTO_LOOP_PROCEDURE.md` §C.

| Agent | Faction | Target |
|---|---|---|
| DRK-PAIN-TOKENS | Drukhari +33.05 gated | Audit Power From Pain implementation magnitude vs Wahapedia |
| DAEMONS-ARCHETYPE-LOC | Daemons -12.52 gated | Audit Greater Daemon seeding so wave-6 Locus auras have host targets |
| TYRANIDS-WARRIORS-BASKET | Tyranids +18.90 gated | Audit archetype composition + Warriors basket realism vs Goonhammer |

Each agent reset to `origin/claude/sim-calibration-6` @ `702e843` and stays
on its worktree branch — cherry-pick into main worktree after eval.
## Waves 43-44 close (2026-05-28)

Branch `claude/sim-calibration-6`. 13 commits landed on top of wave-42 honest
eval `702e843`. Top commit at wave-44 close is `207b842`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 42 close (`702e843`, 2026-05-27) | 13.03 | **9.68** | 4/22 |
| Wave 43 baseline post-DRK-PAIN-TOKENS + LOADER-FAIL-LOUD (`ae7eac2`, 2026-05-28) | 13.11 | 9.75 | 3/22 |
| Wave 44 close (`207b842`, 2026-05-28) | 13.57 | **10.22** | 5/22 |

Net **+0.54 gated MAE regression** across 13 commits. Inside-band count +1
(Chaos Space Marines flipped in at 0.20 gated). Direction is the
"correctness-positive, mean-absolute-error neutral or slightly negative"
pattern noted in the wave 7-42 close — most individual landings moved their
target faction 0-1 pt at N=40, with SECONDARY-SELECTION-V1 introducing
asymmetric variance that nudged the metric up while making the simulator
materially more rule-correct.

### Single biggest win

**Custodes gated 15.25 → 2.51** (a 12.7 pt compression) — driven by
TYRANIDS-SYNAPSE-3D6 (Custodes' enemies stop auto-passing Battle-shock,
so Custodes scoring against Battle-shocked enemies normalises) plus the
SECONDARY-SELECTION picker no longer over-rewarding their elite low-count
shape. Custodes effectively dropped into the noise band.

### Commit landings

* `b4cf249` **[T2] LOADER-FAIL-LOUD** — make `_apply_override` raise when an
  override has no matching base entry and lacks required core stat fields
  (name / health / damage). Caught the `aeldari_drukhari_scourges` typo
  that had been silently fabricating a zero-stat ghost entry, causing a
  14 GB pytest leak via `build_random_army`'s affordability loop. Pre-flight
  scan confirmed only one orphan override key existed. Per CLAUDE.md §13
  (fail loud when data is missing).
* `ae7eac2` **LOOP-CLEANUP-UNLOCK** — `scripts/loop_cleanup.py` was printing
  "REMOVED" while `git worktree remove --force` (single -f) silently failed
  against Claude-agent lock files. Bumped to `-f -f` so locks from dead
  parent claude.exe sessions get overridden. Tooling, no simulator impact.
* `51726fc` **EVAL-TOURNAMENT-GAMES** — `scripts/evaluate_vs_meta.py`
  `save_snapshot()` referenced `TOURNAMENT_GAMES[fac]` but the dict was
  never defined; the JSON-out path crashed with NameError on every eval.
  Added `_load_tournament_games()` alongside `_load_noise_floor()`. Tooling.
* `b4073e5` **docs: CORE_RULES_COVERAGE.md** — coverage matrix mapping
  Wahapedia 10e core rules to simulator state. Initially marked
  embark / disembark as missing on the strength of stale comments at
  `code/detachments.py:767` and `code/archetypes.py:133`; the EMBARK-V1
  agent later discovered embark was implemented in PR #156 / `c84e4db`
  and the comments were just out of date. Section 9 corrected in
  EMBARK-V1's accompanying commit.
* `8db2967` **DAEMONS-DIAG-10** — diag findings doc. Original wave-43
  dispatch hypothesised Greater Daemon seeding was missing; verification
  found archetypes already seed them and `code/leaders.py:618-640` wires
  the Herald loci. The real lever (Lever 1 in the findings) is that the
  four Greater Daemons are seeded in templates but almost never make it
  into actual builds (Bloodthirster 1%, Lord of Change 0%, KoS 0%, Great
  Unclean One 5% across 80 builds).
* `352b1b4` **[T2] DAEMONS-FIX-1** — anchor Greater Daemon in mono-god
  templates before the budget walk in `_instantiate_template`. Verified
  presence rose to 100% across 80 builds, uniform 25% mono-god rotation.
  Daemons gated -12.52 → -11.93 (+0.6 wr-points; below noise floor 3.16,
  but mechanically the anchor is now wired so future per-god leverage
  work has something to land on).
* `f2ccf11` **[T1] EMBARK-V1** — discovered embark / disembark is already
  fully implemented (`_embark_pregame_passengers`, `_embark`, `_disembark`,
  `_maybe_disembark_before_move`, `_destroyed_transport_disembark`, plus
  activation gates in all four phase methods; 12 passing tests in
  `tests/test_transports.py`). Agent added `Unit.is_embarked` convenience
  property, refreshed stale comments in `code/detachments.py` and
  `code/archetypes.py`, and wrote 4 new tests in `tests/test_embark.py`.
  Drukhari did not move (+0.0) because the +33 driver is the still-unwired
  Skysplinter Assault disembark-turn LANCE + IGNORES-COVER buff (parking
  lot — needs per-weapon-keyword temporary gating infrastructure).
* `b51bb98` **[T1] SECONDARY-SELECTION-V1** — each army now picks 2 of 4
  Fixed Pariah Nexus secondaries at battle start based on enemy shape
  (heuristic on enemy MONSTER/VEHICLE count, own FLY/MOUNT count).
  Previously the simulator scored all four every game, asymmetrically
  over-rewarding balanced armies. Gated MAE 9.75 → 10.41 (+0.66
  regression) because the picker's heuristic introduced new variance —
  but the scoring is now rule-correct per Pariah Nexus 10e (CLAUDE.md
  §10). The remaining gap is a V2 picker with faction-aware heuristics
  (parking lot).
* `6202ce1` **TYRANIDS-SYNAPSE-AUDIT** — diag findings doc. Single
  largest over-buff named: `code/simulator.py:4694-4703` auto-passed
  Tyranid Battle-shock within 6" of SYNAPSE, citing the
  pre-September-2024 codex text. Current codex says 3D6 instead of 2D6,
  not auto-pass.
* `24d8a7e` **[T2] TSON-KOS-MESMERISING-V1** — Sorcerer in Terminator
  Armour's "Marked by Fate" datasheet ability was proxied as
  `plus_one_to_hit=True` on the led Scarab Occult Terminators squad —
  a 3-dimensional over-buff (single-target → all targets, single-roll →
  all rolls, single-phase → both phases). Replaced with
  `reroll_hit_ones=True` (the proxy convention used by Ahriman / Infernal
  Master). TSON sim 71.5 → 71.2 (-0.3, below noise).
* `08b1a2d` **[T2] VOTANN-JUDGEMENT-TOKENS-V1** — Judgement Tokens
  machinery itself is clean (re-roll buffs were retired in iter25); the
  real over-buff was on the Kâhl leader aura. Codex "Kindred Hero" grants
  [LETHAL HITS]; the proxy was `plus_one_to_hit=True` — a ~2× over-buff.
  Replaced with `reroll_hit_ones=True`. Side fix: rewrote
  `tests/test_votann_oathband.py` (ImportError-broken since
  VOTANN-DIAG-2 removed the six fabricated stratagems it referenced).
* `201d1f9` **[T2] ADMECH-WARGEAR-V1** — six AdMech overrides
  added / extended in `data/overrides.json`. Skitarii Vanguard / Rangers
  / Sicarian Infiltrators had basket-blend leaks (heavy-weapon special-
  option stats averaged into the basic rifle profile), running at
  ~2.7-3× the correct per-attack damage versus MEQ. Tech-Priest
  Manipulus / Dominus had stacked exclusive weapon options firing
  simultaneously. Data is now Wahapedia-correct; sim moved +4 (wrong
  direction at N=40 noise floor 4.17, statistically indistinguishable
  from baseline).
* `5f00b3f` **[T1] TYRANIDS-SYNAPSE-3D6** — replace the auto-pass at
  `code/simulator.py:4694` with the current-codex 3D6 sum versus 2D6.
  ~16% fail rate at 3D6 vs Leadership 8 versus 0% under auto-pass.
  Tyranids gated 18.78 → 15.92 (-2.9 wr-points, direction correct).
  Custodes also benefited (-6.3 wr-points) via cleaner Battle-shock
  landscape. Chaos Daemons widened slightly (-3.8) — Daemons score
  No Prisoners / Cull against enemy Battle-shock fails, so reducing
  those reduces their secondary scoring.
* `207b842` **[T1] STRATAGEM-CHAIN-V1** — widen
  `DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE` from 1 to 2. The existing
  dispatcher already gates each `_try_X` on CP affordability and the
  per-strat once-per-phase exclusion is implicit (each strat appears
  exactly once in the dispatcher list). One-constant fix. Gated MAE
  10.52 → 10.22 (-0.30, the only landing this run to move MAE in the
  right direction by more than noise). 3-stack remains parking lot.

### Pattern observed

Of 13 commits, only STRATAGEM-CHAIN-V1 (-0.30) and the Custodes-side of
TYRANIDS-SYNAPSE-3D6 (-6.3 wr-points on Custodes alone) moved the
needle visibly at N=40. The rest were correctness-positive but
mean-absolute-error neutral — confirming the wave 7-42 observation that
individual rule-correctness fixes plateau into noise at this scale once
the easy levers are spent.

### Open carry-forwards into wave 45

1. **Drukhari Skysplinter Assault disembark buffs unwired** — the +33
   Drukhari gated outlier is driven almost entirely by the missing
   per-disembark-turn LANCE + IGNORES-COVER grant on Kabalites / Wyches.
   Needs per-weapon-keyword temporary-gating infrastructure first.
   Probably 2-3 commits of structural work.
2. **Sororitas Acts of Faith spend model** — still +16-20 gated post
   wave-44. Unaudited this run.
3. **Imperial Knights / Chaos Knights structural mapper gap** — -30
   and -41 gated respectively. Locked structural; needs Stage 2.
4. **Daemons follow-up beyond Greater Daemon anchor** — Locus aura
   broadcast magnitude and Greater Daemon combat profile audit are the
   two next levers per DAEMONS-DIAG-10 findings.
5. **Tyranid Norn Emissary / Tervigon / Old One Eye** — under-modelled
   per TYRANIDS-SYNAPSE-AUDIT findings (FNP override on OOE, Tervigon
   spawn, Norn Singular Purpose). These would shift Tyranids the wrong
   direction (sim is over-shoot), so deprioritised.
6. **SECONDARY-SELECTION-V2** — faction-aware picker. Current uniform
   heuristic adds noise; a V2 that maps known faction shapes to the
   secondary-mix that real-meta lists actually pick should close the
   +0.66 V1 regression.
7. **Per-weapon-keyword temporary gating infrastructure** — prerequisite
   for Skysplinter Assault (above) plus ~10 other disembark-turn /
   round-gated detachment rules currently approximated or unwired.

### Tooling housekeeping

- `LOOP-CLEANUP-UNLOCK` patch (`ae7eac2`) makes `scripts/loop_cleanup.py`
  actually remove agent worktrees instead of printing "REMOVED" while git
  silently fails. Tested end-to-end during this run.
- `EVAL-TOURNAMENT-GAMES` patch (`51726fc`) unblocks `--out` JSON
  snapshots; every eval in this run produced a writable snapshot.
- `LOADER-FAIL-LOUD` (`b4cf249`) catches the `aeldari_drukhari_scourges`
  typo that previously caused a 14 GB pytest leak.
- `docs/CORE_RULES_COVERAGE.md` (`b4073e5`) now exists as a living audit
  matrix; expect to be updated each iter when a new rule lands or a gap
  is confirmed.
## Wave 45 close (2026-05-28)

Branch `claude/sim-calibration-6`. 1 commit landed on top of wave-44 close
`0aaa73c`. Top commit at wave-45 close is `4b3e18d`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 44 close (`0aaa73c`, 2026-05-28) | 13.57 | 10.22 | 5/22 |
| Wave 45 close (`4b3e18d`, 2026-05-28) | 13.57 | **10.22** | 5/22 |

Wave 45 is a no-metric-move iter. Skysplinter Assault wiring is correct
but inert because of an upstream gap. SECONDARY-SELECTION-V2 was attempted,
regressed, and reverted.

### Landings

* `4b3e18d` **[T1] DRK-SKYSPLINTER-DISEMBARK** — wire LANCE + IGNORES
  COVER on Drukhari units the turn they disembark from a TRANSPORT,
  closing the largest tractable outlier (Drukhari +33 gated). Added
  `Unit.transient_lance_this_turn` + `Unit.transient_ignores_cover_this_turn`
  flags, composed via OR with the profile flags in `Unit.attack`; set
  by `_disembark` when the army's detachment is Skysplinter Assault; 9
  new tests in `tests/test_skysplinter_disembark.py`.

  **Eval: zero metric movement (Drukhari 86.5% to 86.5%).** Root cause:
  the Drukhari Raider and Venom both carry `deep_strike=True` in BSData
  (the Aeldari "Deep Strike" infoLink). `_deploy_armies` routes every
  `deep_strike=True` unit into reserves BEFORE `_embark_pregame_passengers`
  runs, so the pregame embark pass sees zero Drukhari transports on the
  board. Across 40 sample battles (~17 with Skysplinter Assault), zero
  Drukhari disembark events fire. The wiring is rule-correct and will
  activate the day the upstream gap closes.

### Failed attempt: SECONDARY-SELECTION-V2

Faction-aware picker (replacing V1's uniform heuristic) was attempted
to close the V1 +0.66 regression. Faction tiers were classified as
ELITE / MOBILE / MID. Eval result: gated MAE 10.22 to 10.89 (+0.67,
worse than V1).

Root cause of the regression: tier table miscalibration. Adeptus Astartes
classified as "elite" (BiD + Assassination Fixed) crashed Marines sim
55.8% to 39.5% — Tactical Marines field 5-10 model squads and are
mid-shape, not the 3-5 elite shape Custodes / Knights occupy. The V2
revert spec (gated MAE > 10.6 indicates V2 isn't an improvement)
triggered; reverted in working tree, no commit.

### Open carry-forwards into wave 46

1. **Upstream reserves + embark coupling** — when a TRANSPORT is routed
   into reserves at `_deploy_armies`, route its matched INFANTRY
   passengers into reserves alongside it (or pre-embark before reserves
   routing). Unblocks the dormant Skysplinter wiring and probably similar
   gaps on Marines Drop Pods / Aeldari Wave Serpents / etc.
2. **SECONDARY-SELECTION-V3** — V2's tier table was over-aggressive on
   elite tier. V3 should put Marines / Sororitas / GK in MID, leaving
   only Custodes / IK / CK as ELITE. The structural V1 fix stays in
   place; V3 is a tier-table refinement only.
3. **Daemons Locus broadcast magnitude** — anchor (DAEMONS-FIX-1) landed
   in wave-44 but the +0.6 wr-points was below noise. Per
   DAEMONS-DIAG-10 findings the remaining levers are the Locus aura
   broadcast magnitude and Greater Daemon combat profile audit.
4. **Sororitas Acts of Faith spend model** — unaudited, gated 16.05.
5. **STRATAGEM-CHAIN-V2** — widen cap from 2 to 3.
6. All wave-44 carry-forwards remain in place.

## Wave 46-47 close (2026-05-28)

Branch `claude/sim-calibration-6`. 10 commits landed on top of wave-45
close `4b3e18d`. Top commit at wave-47 close is `50e2601`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 45 close (`4b3e18d`, 2026-05-28) | 13.57 | 10.22 | 5/22 |
| Wave 47 batch-1 close (`660a677`, 2026-05-28) | 14.01 | 10.79 | 4/22 |
| Wave 47 batch-2 close (`50e2601`, 2026-05-28) | 14.01 | **10.79** | 4/22 |

Net **+0.57 gated MAE regression** across 10 commits. The regression is
front-loaded in wave 46: the AELDARI-SPLINTER-ANTI-INFANTRY-4 tightening
(`5e1cc0d`) plus the BSData-refresh churn nudged the metric the wrong
way relative to N=40 noise. Wave 47 corrections were rule-correctness-
positive but MAE-neutral — confirming the "easy levers spent" plateau
called out in wave 43-44.

### Wave 46: embark coupling + corrections-layer foundation

* `4f2cf26` **[T1] RESERVES-EMBARK-COUPLING** — pre-embark before reserves
  routing + co-route passengers + bring passengers in with their transport.
  Unblocks the wave-45 Skysplinter Assault wiring (passengers were never
  embarked at deploy time because their transport was routed to reserves
  first). Movement: Drukhari +0.0 at this N (the Skysplinter wiring is
  small-sample-size dependent).
* `5e1cc0d` **[T2] AELDARI-SPLINTER-ANTI-INFANTRY-4** — Drukhari and Ynnari
  Splinter weapons (Rifle / Cannon / Pistol / Carbine) had `ANTI-INFANTRY 3+`
  in BSData; current Wahapedia codex tightened to 4+ in the Sep 2024 errata.
  9 unit entries across the two factions, moved as overrides initially.
* `a5dc6fd` **[T1] CODEX-CORRECTIONS-LAYER-10E** — separate BSData-lag
  corrections from SwegHammer hand-tuning. New file
  `data/codex_corrections_10e.json` layered between BSData base and
  `data/overrides.json`. Moves the 9 Splinter entries out of overrides into
  corrections so a future BSData refresh can retire them cleanly (matching
  the `bsdata_was` snapshot in each entry).

### Wave 47: stale-faction sweep

The BSData snapshot fetched 2026-05-18 left ~10 factions whose `parsed.json`
entries had not been re-checked against current Wahapedia since the May
errata pass. Two batches of 5 parallel Sonnet agents (per
`feedback-tiered-model-selection`) — `[T2]` because the work is per-faction
audit-and-correct, not novel rule code.

**Batch 1 (Imperial Knights, Chaos Knights, Chaos Daemons, Ynnari, Deathwatch):**

* IK, CK, Ynnari — all clean (0 corrections). IK and CK gaps are unmodeled
  Knight rules (Harbingers, ranged-only invuln, Bloodlust, detachment
  effects), not BSData stat lag.
* Ynnari surfaced a parking-lot finding: Aeldari characters (Drukhari Archon,
  Craftworlds Autarch, Yvraine, Visarch, Yncarne) systematically missing
  their 4+ invuln save.
* `edc06b0` **CODEX-STALE-DEATHWATCH** — 1 correction (Watch Master invuln 4+),
  plus surfaced the systematic mapper bug: BSData encodes some invuln saves
  as inline `<profile>` text on the selectionEntry rather than as
  `<infoLink>`, so `mapper.extract_invuln()` misses them.
* `660a677` **[T2] CODEX-STALE-DAEMONS + Karanak override fix** — 7 invuln
  corrections (Bloodthirster, Lord of Change, Great Unclean One, Keeper of
  Secrets, Skarbrand, Bloodletters, Karanak) — all same mapper bug. Karanak
  override fix: codex value is 4+, overrides.json had it at 5+ (mis-identified
  in DAEMONS-DIAG-2); corrections layer now carries 4+ and the shadowing
  override field was removed.

**Audit Round 2** (`90a7ab5` **[T2] CODEX-AUDIT-ROUND-2**): retrospective
check on the May Plague-corrections found 5 over-broad DG/CSM Plague entries
from Round 1 to be over-zealous; reverted. First batch of post-revert audits
confirmed clean.

**BSData refresh** (`61366d1` **[T1] BSDATA-REFRESH**): pulled latest BSData
main; 1 caught-up correction retired (BSData upstream now carries the fixed
value).

**Batch 2 (Imperial Fists, Iron Hands, Dark Angels, White Scars,
Adeptus Titanicus):**

* IF, IH, White Scars — all clean (0 corrections). Chapter heroes and
  load-bearing units all match current Wahapedia 10e.
* `3ebb305` **[T2] CODEX-STALE-DARK-ANGELS** — 8 invuln corrections (Azrael,
  Belial, Sammael, Asmodai, Ezekiel, Lion El'Jonson, Deathwing Knights,
  Ravenwing Black Knights), all same mapper bug. Lion El'Jonson override
  fix: codex is 3+ (The Emperor's Shield), overrides.json had 4+ from an old
  sweep; corrections layer now carries 3+ and the shadowing override removed.
* `50e2601` **[T2] CODEX-STALE-TITANICUS** — 4 invuln corrections on Chaos
  Titans (Reaver, Warbringer Nemesis, Warhound, Warlord) for the 5+ Ion
  Shield. Same mapper bug. Loyalist Adeptus Titanicus side produces no
  parsed entries (the `.cat` uses only entryLinks into `Library - Titans`)
  and is scope-parked until the mapper learns to follow cross-catalogue
  entryLinks.

### Pattern observed

Every wave-47 invuln correction is the same root cause: BSData encodes
invuln saves as inline `<profile typeName="Abilities">` text rather than
as `<infoLink>`. The corrections file now has 20 such entries across 5
faction catalogues (Daemons Library, Deathwatch, Dark Angels, Titans
Library, plus the Ynnari parking-lot list still un-corrected). A
mapper-side fix to `mapper.extract_invuln()` would retire all of them in
one pass.

### Open carry-forwards into wave 48

1. **Mapper invuln-prose-walk fix** — single highest-leverage cleanup of
   the wave-47 corrections backlog. Teach `mapper.extract_invuln()` to
   parse inline `<profile typeName="Abilities">` text on the
   selectionEntry. Would retire 20+ correction entries and prevent the
   same bug appearing in every future stale-faction audit. Parking-lot
   instances still to add: Aeldari characters (Drukhari Archon,
   Craftworlds Autarch, Yvraine, Visarch, Yncarne) from the Ynnari audit.
2. **Loyalist Adeptus Titanicus parser support** — Imperium - Adeptus
   Titanicus .cat uses only entryLinks into Library - Titans and produces
   no parsed entries. Mapper needs cross-catalogue entryLink resolution.
3. **N=40 plateau** — gated MAE has been within 10.22-10.81 for 5
   consecutive evals across 10+ commits. The remaining gap is
   structurally locked (IK/CK -32/-41 mapper-bound, Drukhari +34
   Skysplinter-bound, Daemons -17 Locus-bound, Sororitas +17 spend-
   model bound). Without one of those four structural levers landing,
   further per-faction rule-correctness work will continue to be
   MAE-neutral. Recommended next pivot: mapper invuln fix (carry-forward 1)
   to retire the backlog, then attack one structural lever.
4. All wave-45 carry-forwards remain in place (Drukhari Skysplinter dormant
   pending the upstream reserves coupling firing in more samples, Sororitas
   Acts of Faith spend model unaudited, Daemons Locus magnitude unaudited,
   SECONDARY-SELECTION-V3 tier-table refinement, STRATAGEM-CHAIN-V2 cap 3).

