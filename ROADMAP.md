# Development Roadmap

## Status Overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Complete | Project setup, documentation, baseline definition |
| Phase 1 | ✅ Complete | Deterministic simulator, initial unit catalogue |
| Phase 2 | 🔲 Planned | Stochastic damage, variance analysis |
| Phase 3 | 🔲 Planned | Nonlinear cost surface fit |
| Phase 4 | 🔲 Planned | Rule variant testing, edge cases |

---

## Phase 0 — Foundation ✅

**Goal**: Establish the project structure, mathematical framework, and baseline unit definition.

- [x] README.md — problem statement and rules overview
- [x] THEORY.md — Lanchester derivations and nonlinearity analysis
- [x] BASELINE.md — baseline unit definition and initial unit catalogue
- [x] SIMULATION.md — simulator design documentation
- [x] ROADMAP.md — this file

**Deliverables**: All documentation files, agreed baseline (Space Marine with bolter, 15 pts).

---

## Phase 1 — Deterministic Simulator ✅

**Goal**: Build a working simulation engine and run initial calibration battles.

- [x] `code/units.py` — UnitProfile, Unit, UNIT_CATALOG
- [x] `code/army.py` — Army class with CP tracking
- [x] `code/simulator.py` — Battle engine with unit-by-unit activation
- [x] `code/army_builder.py` — Random army generation within points budget
- [x] `code/calibration.py` — Batch runner and win-rate analysis
- [x] `code/main.py` — Demo entry point

**Deliverables**: Working simulator; initial win-rate report for all unit pairings.

**Acceptance criteria**:
- Baseline Marine vs Marine army yields 50% ± 1% win rate over 1000 battles.
- All unit types produce a result (no crashes, infinite loops, or degenerate outcomes).
- Output report is human-readable and shows win rate, draw rate, avg rounds.

---

## Phase 2 — Stochastic Damage and Variance Analysis 🔲

**Goal**: Add dice-roll variance and identify which unit matchups have high outcome volatility.

- [ ] Add stochastic damage mode (binomial hit distribution, randomised damage rolls)
- [ ] Compare deterministic vs stochastic win rates
- [ ] Identify high-variance matchups (e.g., low-count elite units vs horde)
- [ ] Measure "cliff-edge" matchups where a single roll determines the game

**Deliverables**: Stochastic simulator; variance report per matchup; list of high-risk matchups.

---

## Phase 3 — Nonlinear Cost Surface Fit 🔲

**Goal**: Replace the linear Phase One cost formula with an empirically derived surface.

- [ ] Run full sweep of unit-vs-unit pairings (homogeneous and mixed armies)
- [ ] Build regression dataset: (unit stats) → (win rate deviation from 50%)
- [ ] Fit cost surface using `scipy.optimize` or gradient descent
- [ ] Validate: all pairings within 45–55% win rate
- [ ] Produce updated `BASELINE.md` with calibrated costs
- [ ] Document attribute nonlinearities observed (movement, toughness, accuracy)

**Deliverables**: Calibrated cost formula; updated unit catalogue; validation report.

---

## Phase 4 — Rule Variants and Edge Cases 🔲

**Goal**: Test CP economy tuning, first-player advantage, and synergy handling.

- [ ] Measure first-player win rate with and without unit-by-unit activation
- [ ] Calibrate CP bonus formula (current: `floor(unit_diff / 2)`)
- [ ] Test CP cap values (1 CP/round, 2 CP/round, uncapped)
- [ ] Evaluate Turn 1 exclusion from CP awards
- [ ] Model simple aura effects (reroll hits within 6") and measure cost impact
- [ ] Identify units where synergy value exceeds the ±3 pt tolerance band

**Deliverables**: Final CP formula; aura tolerance band guidelines; recommended rule text for
players.

---

## Future Considerations

### Faction-Level Balance

Once individual units are well-priced, the next question is whether faction army special rules
create systemic advantages. This is deferred until Phase 4 is complete.

### Web Interface

A lightweight web UI to input an army list and receive a cost evaluation report. Deferred until
the cost model is stable.

### Community Calibration

Open simulation runs where community members can submit their own battle logs to feed into the
calibration dataset, replacing pure-simulation data with real-world outcomes.
