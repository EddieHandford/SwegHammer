# Development Roadmap

## Status Overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Complete | Objectives + VP-based win condition |
| Phase 1 | ✅ Complete | Deterministic simulator, initial 18-unit hand-rolled catalogue |
| Phase 1.5 | ✅ Complete | Stochastic damage, armour saves, AP, cover |
| Phase 1.6 | ✅ Complete | BSData WH40k 10th-ed ingestion, override layer |
| Phase 2 | 🔲 Active | Override tuning — repair mapper artefacts, balance the BSData catalogue |
| Phase 3 | 🔲 Planned | Nonlinear cost surface fit |
| Phase 4 | 🔲 Planned | Rule variant testing, edge cases |
| Phase A2 / A3 | ✅ Complete | Ten weapon keywords + Feel No Pain |
| Phase B | ✅ Complete | Charge + Fight (melee) phases |
| Phase C | ✅ Complete | Battleshock + Ld/OC on UnitProfile |
| Phase D | ✅ Partial | Detachment scaffolding + 2 live effects (8 flags still unwired) |
| Phase E | ✅ Partial | Stratagems: 4 universals + 3 detachments (Cult of Magic, Plague Company, Battle Host) |
| Phase F | 🔲 Planned | Niche weapon / unit keywords |
| Phase G | 🔲 Planned | Leader / character abilities |

---

## Phase 0 — Objectives + VP win condition ✅

**Goal**: Move the simulator off "most surviving units wins" onto a 10e-flavoured
Primary VP system.

- [x] `Objective` dataclass on `code/map.py` — `(x, y, control_radius=3", vp_per_round=5)`
- [x] Every stock map ships a 5-objective quincunx (centre + four ~30% in from each corner)
- [x] End-of-round Primary VP scoring — strict OC majority within control radius banks the marker
- [x] Win condition: one-sided wipe → VP → remaining army points → draw (10% margin)
- [x] `BattleResult.a_vp`, `b_vp`, `a_points_remaining`, `b_points_remaining` exposed for the dashboard

**Foundation docs** (delivered earlier, retained as living references):

- README.md — problem statement and rules overview
- THEORY.md — Lanchester derivations and nonlinearity analysis
- BASELINE.md — baseline unit definition and initial unit catalogue
- SIMULATION.md — simulator design documentation
- ROADMAP.md — this file

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

**Goal**: Pull unit stats from the BSData WH40k 10th-edition project rather than
hand-rolling them, with an override layer for fine tuning.

- [x] `code/bsdata/fetch.py` — pinned-tag download + cache (45 .cat + .gst files)
- [x] `code/bsdata/parser.py` — XML registry across all files
- [x] `code/bsdata/mapper.py` — force-list walk, best-legal-loadout optimiser,
      SwegHammer mapping (10e schema: SV on unit, ranged-weapon A/BS/S/AP/D)
- [x] `code/bsdata/loader.py` — merge parsed.json + overrides.json at import time
- [x] `data/overrides.json` — hand-tuned modifications (starts empty)
- [x] Wire `UNIT_CATALOG` to load from the merged catalogue

**Delivered**: ~1100 BSData 10e-derived units replace the 18 hand-rolled ones.
Vehicles and Imperial Knights now have proper stat lines (T, SV, W on the unit
profile directly), eliminating the 2nd-ed vehicle-mapping bugs.

---

## Phase 2 — Override Tuning 🔲 (active)

**Goal**: Repair mapper artefacts and start balancing the BSData catalogue.

- [ ] Sweep `data/bsdata/parsed.json` for the ~260 currently-skipped entries
      (mostly characters/units with no ranged weapons — melee-only models) —
      fix the mapper to fall back to melee weapons, or formally disable
- [ ] Squad-level damage: 10e weapons have explicit A (attacks per model), but
      multi-model squads still emit per-model wounds. Decide whether `health`
      means per-model or per-squad-aggregate and apply consistently
- [x] Loadout optimiser currently uses *expected damage through baseline Marine
      armour* — review which weapons it picks for elite Knights and refine
      if the cheese is too cheesy. **Done (#76)**: multi-model squads now use a
      weighted basket of per-model weapons (e.g. 5 bolters + 4 multi-meltas +
      1 sergeant for Devastators), so per-model damage sits between bolter-
      only and all-best. Single-model units still use the legacy best-weapon
      path. ~210 squads use the new heterogeneous path.
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

## Phase A2 / A3 — Weapon keywords + Feel No Pain ✅

**Goal**: Wire ten 10e weapon keywords plus FNP into the combat resolver.

- [x] Mapper extracts: Rapid Fire N, Melta N, Ignores Cover, Anti-KEYWORD N+,
      Heavy, Assault, Torrent, Hazardous, Blast
- [x] `extract_unit_keywords()` scans `categoryLinks` for 10e tags (INFANTRY,
      VEHICLE, MONSTER, CHARACTER, FLY, TITANIC, etc.)
- [x] `extract_fnp()` sweeps profile + linked-rule text for "Feel No Pain N+"
- [x] `Unit.attack()` applies the keywords; `Unit.receive_damage` rolls per-point FNP
- [x] Heavy keyword parsed and stored — application deferred (needs a "did not
      move this turn" flag, which the sim doesn't yet expose meaningfully)

---

## Phase B — Charge + Fight (melee) ✅

**Goal**: Add the missing close-combat half of the game.

- [x] Mapper picks a best-legal melee weapon alongside the best ranged
- [x] `UnitProfile.melee_*` fields (attacks, damage, hit prob, strength, AP, weapon)
- [x] `Unit.attack(target, distance, mode="ranged"|"melee")` switches stat block
- [x] `Battle._do_charge` — declaration, 2d6 roll, move into 1" engagement
- [x] `Battle._do_fight` — units within 1.5" of an enemy fight; chargers first
- [x] Charge-desire heuristic: only charge when `melee_dpa >= max(ranged_dpa, 1.0)`
- [x] 191 previously-disabled melee-only units reactivated (Hormagaunts, Berzerkers,
      Bloodletters, Daemonettes, Skorpekh Destroyers, etc.)

---

## Phase C — Battleshock ✅

**Goal**: 10e-flavoured morale check on wounded units.

- [x] `UnitProfile` gains `leadership` (Ld) and `oc` (Objective Control)
- [x] Mapper extracts both from the unit profile
- [x] From Round 2, units below half HP roll 2d6 vs Ld
- [x] Failed test → Battleshocked for the round → OC counts as 0 for objective scoring

---

## Phase D — Detachments ✅ partial

**Goal**: Army-wide passive buffs (the always-on piece of a 10e detachment rule).

- [x] `Detachment` dataclass with ten modifier flags
- [x] Five canonical detachments registered (Gladius, Awakened Dynasty, Invasion
      Fleet, WAAAGH! Tribe, Noble Lance)
- [x] `DEFAULT_BY_FACTION` resolves a sensible default per primary faction
- [x] `Army.detachment` slot + `resolve_detachment()`

**Follow-ups (8-of-10-flag gap):** only `reanimate_per_round` and
`enemy_ld_penalty` are wired into the simulator. The remaining eight flags
(`reroll_hit_ones`, `reroll_wound_ones`, `plus_one_to_hit`, `plus_one_to_wound`,
`plus_one_attack`, `plus_one_save`, `extra_invuln`, `ld_bonus`) parse and store
but produce no in-game effect yet. Wiring needs to compose into the Phase A2/A3
keyword path in `Unit.attack()`.

---

## Phase E — Stratagems ✅ partial

CP-priced effects fire on triggers each round. Framework lives in
`code/stratagems.py` (`Stratagem` dataclass, four universal Core
Stratagems, and detachment tuples wired onto `Detachment.stratagems`).
The simulator dispatches via `Battle._fire_stratagem` (universals through
the existing hooks: failed wound roll, vehicle charge, enemy fight,
out-of-sequence retaliate) and `Battle._apply_detachment_stratagems`
(detachment-specific, fired at round start).

Implemented:
- **Universal Core Stratagems** (4): Command Re-Roll, Counter-Offensive,
  Tank Shock, Heroic Intervention.
- **Cult of Magic (Thousand Sons)**: Doombolt (D3 mortal wounds),
  Twist of Fate (+1 to wound shooting), Glamour of Tzeentch (transient 4++).
- **Plague Company (Death Guard)**: Disgustingly Resilient (-1 damage
  taken), Plague Weapons (+1 to wound shooting), Outbreak of Pestilence
  (+1 to wound melee).
- **Battle Host (Aeldari)**: Lightning-Fast Reactions (+1 save), Fire and
  Fade (re-roll 1s to hit shooting, approximating the canonical 6"
  reposition), Matchless Agility (transient Assault).

The remaining 18+ detachments still have empty `stratagems` tuples —
follow-up tasks will wire Awakened Dynasty, Gladius Task Force, etc.

---

## Phase F — Niche keywords 🔲 planned

The long tail of weapon and unit keywords that don't fall into the Phase A2/A3
ten: Lethal Hits, Sustained Hits, Lance, Twin-Linked, Precision, Indirect Fire,
Pistol, One Shot, etc. Mapper already stores raw keyword text on each weapon
profile; the work is the combat-side implementation.

---

## Phase G — Leader / character abilities 🔲 planned

Attachment to bodyguard units, ATTACHED → LEADER target redirection, aura
buffs within a radius, Look Out Sir wound redirection. Depends on Phase F
unit-keyword work (CHARACTER + INFANTRY + bodyguard-eligibility gating).

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
