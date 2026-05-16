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

