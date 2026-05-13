# Development Roadmap

## Status Overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Complete | Project setup, documentation, baseline definition |
| Phase 1 | ✅ Complete | Deterministic simulator, initial 18-unit hand-rolled catalogue |
| Phase 1.5 | ✅ Complete | Stochastic damage, armour saves, AP, cover |
| Phase 1.6 | ✅ Complete | BSData WH40k 2nd-ed ingestion, override layer |
| Phase 2 | 🔲 Active | Override tuning — repair mapper artefacts, balance the BSData catalogue |
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

## Phase 1.5 — Stochastic Damage, AP, Armour Saves, Cover ✅

**Goal**: Replace the deterministic-damage placeholder with real dice rolls.

- [x] To-hit roll using `hit_probability`
- [x] Target armour save roll with AP modifier
- [x] Cover gives +1 to saves, capped at 2+
- [x] `UnitProfile` gains `ap` and `save` fields; `points_for` weighs both axes

**Delivered**: Combat resolution now matches the design in `SIMULATION.md`.

---

## Phase 1.6 — BSData Ingestion ✅

**Goal**: Pull unit stats from the BSData WH40k 2nd-edition project rather than
hand-rolling them, with an override layer for fine tuning.

- [x] `code/bsdata/fetch.py` — pinned-tag download + cache
- [x] `code/bsdata/parser.py` — XML registry across all 16 codex / GST files
- [x] `code/bsdata/mapper.py` — force-list walk, best-legal-loadout optimiser,
      SwegHammer mapping
- [x] `code/bsdata/loader.py` — merge parsed.json + overrides.json at import time
- [x] `data/overrides.json` — hand-tuned modifications (starts empty)
- [x] Wire `UNIT_CATALOG` to load from the merged catalogue

**Delivered**: ~240 BSData-derived units replace the 18 hand-rolled ones.

---

## Phase 2 — Override Tuning 🔲 (active)

**Goal**: Repair mapper artefacts and start balancing the BSData catalogue.

- [ ] Sweep `data/bsdata/parsed.json` for the 88 currently-skipped entries
      (mostly vehicles, characters without resolvable weapons) — fix or
      formally disable via overrides
- [ ] Cap or scale per-model damage where the loadout optimiser picked a
      squad-only weapon (Multi-Melta on every Tactical Marine = 13 dmg/model)
- [ ] Pin saves for heroes the depth-3 walk misses (Mephiston, Terminator
      Captain, etc.)
- [ ] Run calibration suite, identify systematic outliers, tune via overrides
- [ ] Document the override workflow with worked examples

**Deliverables**: A balanced BSData-derived catalogue with documented overrides.

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
