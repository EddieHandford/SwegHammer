# Sweghammer: Data-Driven Unit Costing for Warhammer 40K

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

For Phase One, unit costs are set proportional to the unit's raw combat effectiveness:

```
points = BASELINE_POINTS × (health × damage × hit_probability) / BASELINE_EFFECTIVENESS
```

This linear-in-raw-stats pricing is the starting point. Phases Two and Three replace it with a
surface fit from simulation data, converging toward the Lanchester-optimal pricing where equal
points implies equal expected battlefield score.

## Project Structure

| File | Purpose |
|------|---------|
| `README.md` | This file — overview and rules summary |
| `CLAUDE.md` | Standing rules for Claude instances working on this repo |
| `THEORY.md` | Mathematical derivations (Lanchester equations, nonlinearity analysis) |
| `BASELINE.md` | Baseline unit definition, points formula, catalogue source |
| `SIMULATION.md` | Simulation engine design, activation mechanics, phase logic |
| `ROADMAP.md` | Development milestones and phase breakdown |
| `code/` | Python simulation engine |
| `code/bsdata/` | BSData WH40k 2nd-edition fetch / parse / map / load |
| `data/bsdata/` | Pinned `.cat` cache and mapped `parsed.json` |
| `data/overrides.json` | Per-unit hand tuning on top of the BSData base |

## Quickstart

```bash
# Run a demo battle + quick calibration
python run.py

# Run the full calibration suite (1000 battles per matchup)
python -m code.calibration

# Streamlit UI
streamlit run app.py

# Refresh BSData base stats (pins to a release tag)
python -m code.bsdata.fetch --tag v1.9.7
python -m code.bsdata.mapper
```

Requires Python 3.9+. Streamlit + matplotlib for the UI; the core simulator
is stdlib-only.

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
