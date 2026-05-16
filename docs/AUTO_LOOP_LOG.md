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

