# Sweghammer: Data-Driven Unit Costing for Warhammer 40K

> **v1.0 — Recalibrated.** Frozen prices dataset at [`data/sweg_points_v1.json`](data/sweg_points_v1.json).
> 1,479 units priced by a 111-feature regression (R² 0.96 vs Games Workshop,
> mean absolute error 17 pts/model). The first release is **equation-only**
> — the simulator is built but does not feed into these prices yet. A
> single-file playtester HTML reference lives at
> [`docs/sweghammer_points.html`](docs/sweghammer_points.html) — hero, the
> equation, family contribution breakdown, faction multipliers, methodology,
> and a searchable unit table. The Streamlit dashboard opens in **Player
> view** by default (sidebar toggle switches to the full **Calibration view**
> with the simulator and calibration tools). Player view tabs: Home, Unit
> Browser, Army Compare, Faction Overview, The Equation.


<img width="939" height="961" alt="image" src="https://github.com/user-attachments/assets/5f350602-b775-449b-a1de-a26387f56333" />









A project to derive fair, mathematically-grounded unit points costs for Warhammer 40K based on
Lanchester's Square Law and empirical simulation, whilst introducing minimal rule adjustments to
eliminate key feel-bad moments and restore balance.

## Problem Statement

Games Workshop's current points system is designed primarily to drive model sales, leading to
chronic power creep. New units are often undercosted to incentivise purchases, then left expensive
after the hype dies. Furthermore, the first-player advantage is statistically significant—data
shows going first yields a 58% win rate versus 42% for going second—creating a lottery that can
decide games before either side plays meaningfully.

This project seeks to:

1. Derive fair points costs using Lanchester's Square Law and empirical simulation against a
   baseline unit (standard Space Marine with bolter).
2. Introduce minimal rule changes to eliminate feel-bad moments, specifically first-player
   advantage.
3. Keep the ruleset light: players should experience switching from standard Warhammer 40K to
   Swaghammer as "one or two elegant tweaks," not a house-rules overhaul.

## Two-Stage Pipeline

SwegHammer is built as two sequenced feedback loops, not one:

1. **Stage 1 — Make the simulator play like reality.** Compare per-faction
   simulated win rates against the May 2026 Warp Friends ~10k-game
   tournament aggregate, and tune the simulator's rules and mechanics
   until the mean absolute error closes (target ≤ 2.0 pts; current
   reading is 7.01 pts at N=200).
2. **Stage 2 — Fit the points equation.** Once Stage 1 has converged,
   freeze the simulator's rules and fit one master equation that prices
   every unit from its stats (plus small per-unit residuals for the
   rough edges). Run the now-faithful simulator with equation-priced
   units, re-weight the stat coefficients and adjust the residuals, and
   repeat until the win-rate spread across the catalogue flattens. The
   final output is the equation, not a hand-tuned price list — per-unit
   costs fall out deterministically from the fitted formula.

The feedback signals are deliberately different — Stage 1 is gated by
tournament mean absolute error, Stage 2 by win-rate spread across all
units — and conflating them produces wrong answers. See
[`OVERVIEW.tex`](OVERVIEW.tex) for the picture, and [`CLAUDE.md`](CLAUDE.md)
"Project plan" for the rules-of-thumb.

## Core Rules Changes

### Unit-by-Unit Activation (Turn Structure)

Instead of the standard I-Go-You-Go model:

- Player A activates one unit.
- Player B activates one unit.
- Players alternate until all units are activated.
- End of round: check victory conditions, move to next round.

**Benefit:** Flattens the alpha-strike advantage of going first. Early trades happen gradually,
rather than one side getting a full turn of unopposed fire.

### Command Point Economy for Balanced Unit Counts

To prevent horde armies from gaining an unfair mini alpha-strike advantage (more unit activations
equals more actions):

- At the end of each round (after both players' units are activated), the player with fewer units
  gains bonus command points.
- Formula (to be calibrated): `bonus_CP = max(0, floor((opponent_units - your_units) / 2))`
- Exclusions: Turn 1 is excluded to discourage list-building around unit count.
- Cap: Sensible ceiling per round (e.g., 1–2 CP per round maximum).

**Benefit:** Horde armies remain tactically viable without dominating the turn economy.

## Mathematical Foundation: Lanchester's Square Law

In aimed-fire, non-instantaneous combat, the outcome is governed by the square of each side's
combat power, not linearly. See [THEORY.md](THEORY.md) for full derivations.

### Unit Combat Effectiveness Score

Each unit's battlefield power is determined by three core factors:

1. **Health**: Total wounds or equivalent durability metric.
2. **Damage Output**: Average damage dealt per action (accounting for weapon profiles and rate of
   fire).
3. **Hit Probability**: Likelihood of successfully hitting a target (including modifiers, rerolls,
   accuracy penalties).

Combined metric: **Unit Score = (Health × Damage × Hit Probability)²**

*Example:* A Space Marine with 2 health, 1 damage per action, and 67% hit probability scores
(2 × 1 × 0.67)² ≈ 1.78.

### Points Calibration

The points calibration described here is **Stage 2** work — it only
becomes reliable once Stage 1 has converged. As a Stage 2 baseline, unit
costs are set proportional to the unit's raw combat effectiveness:

```
points = BASELINE_POINTS × (health × damage × hit_probability) / BASELINE_EFFECTIVENESS
```

This linear-in-raw-stats pricing is Layer 1 of Stage 2. Two empirical
solvers — `code/balancer.py` (Monte Carlo bisection) and
`code/equilibrium.py` (closed-form log-least-squares on the time-to-kill
matrix) — refine it, converging toward Lanchester-optimal pricing where
equal points implies equal expected battlefield score. See
[`BASELINE.md`](BASELINE.md) for the layer/track structure.

## Project Structure

| File | Purpose |
|------|---------|
| `README.md` | This file — overview and rules summary |
| `PROJECT.tex` / `PROJECT.pdf` | Living project handbook — vision, math, architecture, ownership-tagged checklist |
| `TODO.md` | Quick-reference remaining-work list pulled from PROJECT.tex |
| `CLAUDE.md` | Standing rules for Claude instances working on this repo |
| `THEORY.md` | Mathematical derivations (Lanchester equations, nonlinearity analysis) |
| `BASELINE.md` | Baseline unit definition, points formula, catalogue source |
| `SIMULATION.md` | Simulation engine design, activation mechanics, phase logic |
| `ROADMAP.md` | Development milestones organised around Goals A–D |
| `docs/CORE_RULES_AUDIT.md` | 10e core rules vs implementation coverage map |
| `code/` | Python simulation engine |
| `code/sim/` | Simulator package — modules extracted from `code/simulator.py` by pure code motion (constants, geometry so far), behaviour-identical; see [`docs/SIM_MODULARIZATION_PLAN.md`](docs/SIM_MODULARIZATION_PLAN.md) |
| `app.py` | Streamlit dashboard — 6 tabs (Statistics, Watch a battle, Efficiency, Equilibrium, Compare to SwegHammer, Convergence) |
| `run.py` | Cross-platform launcher (`python run.py` for the GUI menu, `python run.py --cli` to skip it) |
| `code/factions.py` | Codex → faction mapping + per-faction display colours; Marine umbrella detection |
| `code/archetypes.py` | Curated per-faction tournament list templates (opt-in via `use_archetype=True`) |
| `code/balancer.py` | Monte Carlo bisection to hit 50% win rate vs a baseline; writes `data/calibrated_points.json` |
| `code/equilibrium.py` | Analytic equilibrium solver — Phases 1 (shoot) / 2 (+melee) / 3 (defensive audit) / 4 (tactical utility) / 5 (meta-weight) / 6 (Nash mixed-strategy) |
| `code/detachments.py` | Army-wide passive Detachment rules (~26 detachments, 2 per major faction) |
| `code/enhancements.py` | Warlord enhancement upgrades (Champion of Humanity, Arcane Vortex, etc.) |
| `code/leaders.py` | Per-CHARACTER LeaderAbility registry + aura wiring |
| `code/stratagems.py` | Universal + faction-specific stratagems + CP economy |
| `code/strategy.py` | Per-unit move intent — HOLD / CAPTURE / STEAL / ENGAGE / REPOSITION / FALL_BACK |
| `code/roles.py` | Role classifier — SHOOTY / MELEE / DUAL / HORDE / HEAVY / SUPPORT |
| `code/compare_view.py` | Streamlit tab: GW points vs all equilibrium phases with mispricing % |
| `code/bsdata/` | BSData WH40k 10th-edition fetch / parse / map / load |
| `code/bsdata/audit.py` | Diff successive `parsed.json` runs, flag unmapped codices and stat drift |
| `scripts/audit_rules.py` | Citation coverage gate — every cite-able rule has a Wahapedia source |
| `scripts/bench_simulator.py` | Benchmark harness — reports per-battle wall time across three representative matchups |
| `scripts/sim_motion_proof.py` | Behaviour-identity fingerprint harness — proves a simulator code-motion refactor changes nothing, by hashing fixed-seed battle traces before and after |
| `scripts/evaluate_vs_meta.py` | Sim-vs-real-meta matchup matrix; reports raw MAE + noise-gated MAE against the 4-week rolling Warp Friends aggregate in `data/warpfriends_rolling.json` |
| `scripts/scrape_warpfriends.py` | Refresh `data/warpfriends_rolling.json` from the latest weekly posts at warpfriends.wordpress.com |
| `scripts/sweg_balance_mc.py` | MC-driven per-faction balance pass on top win-rate residuals |
| `scripts/cross_validate_pricing.py` | Compare Phase 5 equilibrium vs MC bisection signals |
| `scripts/export_bsdata_csv.py` | Export UNIT_CATALOG to `data/units.csv` for spreadsheet inspection |
| `data/bsdata/` | Pinned `.cat` cache and mapped `parsed.json` |
| `data/overrides.json` | Per-unit hand tuning on top of the BSData base |
| `data/rule_citations.d/` | Per-rule Wahapedia citations (army rules, stratagems, leaders, enhancements) — enforced by `audit_rules.py` |
| `data/equilibrium_points_phase{1,2,4,5,6}.json` | Per-phase equilibrium pricing outputs |
| `data/calibrated_points.json` | Bisected points costs produced by `code/balancer.py` |
| `data/units.csv` | Flat CSV export of the unit catalogue (regenerated by `export_bsdata_csv.py`) |

## Quickstart

```bash
# Launcher (GUI menu with web dashboard + CLI demo buttons)
python run.py

# CLI demo direct
python run.py --cli

# Streamlit dashboard directly (if you prefer)
python -m streamlit run app.py
```

Requires Python 3.9+. Dashboard needs Streamlit, matplotlib, Plotly, and
pandas; the core simulator has no external dependencies.
# Run a demo battle + quick calibration
python run.py

# Run the full calibration suite (1000 battles per matchup)
python -m code.calibration

# Streamlit UI
streamlit run app.py

# Refresh BSData base stats (pins to a release tag)
python -m code.bsdata.fetch --tag v10.6.0
python -m code.bsdata.mapper
```

Requires Python 3.9+. Streamlit, matplotlib, Plotly, and pandas for the
dashboard; the core simulator is standard-library only.

On Windows: prepend `PYTHONIOENCODING=utf-8` so the console doesn't crash on
the simulator's arrow character.

## Key Design Principles

1. **Minimal rule changes**: Only unit-by-unit activation plus command point economy.
2. **Lightweight simulation**: Start simple, add complexity only when needed.
3. **Empirical calibration**: Let data from thousands of matched battles guide points adjustments.
4. **Transparency**: All costs are derivable from the underlying unit stats.
5. **Player-friendly**: Switching to Swaghammer should feel like a small tweak, not a new game.

## Glossary

| Term | Definition |
|------|-----------|
| **Unit Score** | (Health × Damage × Hit Probability)², the Lanchester effectiveness metric |
| **Baseline Unit** | Standard Space Marine with bolter — reference for all cost calibration |
| **Alpha Strike** | Full turn of unopposed fire by one side |
| **Horde Army** | Army with many cheap, low-health units |
| **Command Points** | Resource pool granted at round end to players with fewer unit activations |
| **Lanchester's Square Law** | Combat outcome scales with the square of force strength |
| **Nonlinear Weighting** | Attribute value is not proportional to its stat |
| **Tolerance Band** | Acceptable variance in unit costing due to synergies and auras |
| **Unit-by-Unit Activation** | Players alternate activating single units each action |
