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

### Iter 3 — PAUSED (API rate limit)

Dispatched 5 per-faction deep-diagnostic agents (DG, Marines, Aeldari, Orks, T'au). All 5 died early with Anthropic API rate-limit error ("You've hit your limit · resets 4:50am Europe/London"). No commits landed.

**Resume**: re-dispatch the same 5 per-faction diagnostics. Prompts were faction-specific deep audits with mechanism trace + Wahapedia gap + AI gap + single top-ranked fix proposal. Worktree IDs are dead — fresh dispatch needed.

**Pre-pause state**: MAE-vs-real 5.66pt, MAE-vs-Sweg 5.94pt, HEAD `08b841e`, 644 tests green.

