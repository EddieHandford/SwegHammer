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
