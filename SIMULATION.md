# Simulation Engine Design

## Overview

The simulator is a stochastic 10th-edition Warhammer 40K combat engine
with movement, shooting, charge, fight, and morale phases over a 5-round
window on a 2D map. It models two armies fighting under SwegHammer's
unit-by-unit activation rules and emits a battle event stream that can
either be aggregated over thousands of battles for calibration sweeps or
rendered as a watchable replay for a single battle.

## Role in the two-stage pipeline

This document describes the **Stage 1** apparatus: the simulator whose
rules are being tuned until per-faction win rates match the May 2026
Warp Friends tournament aggregate (Goal A in `ROADMAP.md`). Stage 2's
points-equation fit (Goals C and D) runs on top of this engine once
Stage 1 has converged; the loop fits one master equation that prices
every unit from its stats plus small residuals, with the simulator
supplying the per-unit win rates that gate convergence. The
equation-fitting solvers live in `code/balancer.py` and
`code/equilibrium.py`; see `BASELINE.md` for the layer / track
breakdown. See `CLAUDE.md` "Project plan" for the full pipeline
framing.

## Architecture

```
code/
  units.py        — UnitProfile (frozen stats), Unit (mutable battle instance)
  army.py         — Army (collection of units + command points)
  simulator.py    — Battle (runs one engagement), BattleResult (output data)
  army_builder.py — Random army generation within a points budget
  calibration.py  — Batch simulation runner and win-rate analyser
  main.py         — Demo entry point
```

## Combat Model

### Stochastic Damage

Each attack is resolved against the full 10e hit / wound / save / Feel No
Pain chain with real dice rolls. The simulator is seedable so a single
matchup is reproducible; calibration sweeps re-seed per battle for an
honest distribution.

Deterministic average-case damage was used in the foundational 2025
prototype; the current engine has been stochastic since the Phase 1.5
foundation work (see `ROADMAP.md` "Foundation work").

### Activation Sequence

Each battle round proceeds as follows:

1. **First-player determination**: Randomised at the start of each round (50/50).
2. **Activation queue**: Both armies sort their alive units by Lanchester score (highest first),
   creating an ordered activation queue for the round.
3. **Alternating activations**: The first player activates their highest-priority unactivated
   unit; the second player responds with theirs. This repeats until one or both queues are
   exhausted.
4. **Surplus activations**: If one army has more units, its remaining units activate unopposed
   after the other army's queue is empty.
5. **Command point awards**: After each round (except Round 1), the player with fewer surviving
   units receives bonus CP: `bonus_CP = max(0, floor((opponent_count - own_count) / 2))`.

### Target Selection

Attackers target the enemy unit with the **lowest current health** (focus-fire heuristic). This
approximates optimal play and ensures units are eliminated rather than spread-damaged, producing
cleaner attrition dynamics.

### Victory Conditions

A battle ends when:
- One army has no surviving units → the other army wins.
- Both armies reach zero simultaneously → draw (mutual destruction).
- The round limit (30) is reached → the army with more surviving units wins; if equal, draw.

## Data Flow

```
BattleConfig
    │
    ▼
ArmyBuilder.build(points_budget, unit_pool)  →  Army A, Army B
    │
    ▼
Battle(army_a, army_b).run()  →  BattleResult
    │
    ▼
CalibrationSuite.run(n_battles)  →  WinRateReport
```

## Output Format

### BattleResult

```python
@dataclass
class BattleResult:
    winner: Optional[str]   # army name, or None for draw
    rounds: int             # number of rounds played
    a_survivors: int        # units surviving in army A
    b_survivors: int        # units surviving in army B
    a_start: int            # initial unit count for army A
    b_start: int            # initial unit count for army B
```

### CalibrationReport

```
Matchup: Marines vs Orks (1000 pts each, 1000 battles)
  Marine wins:  512 (51.2%)
  Ork wins:     471 (47.1%)
  Draws:         17  (1.7%)
  Avg rounds:   8.3
  Avg Marine survivors: 2.1
  Avg Ork survivors:    1.9
```

## Engine status (shipped)

The phase-based naming below ("Phase One / Two / Three") was retired in
the 2026-05 docs sweep — both because the original "planned" phases have
all shipped, and because reusing the word "Phase" inside this document
collided with the equilibrium solver's own Phase 1–6 ladder
(`code/equilibrium.py`). The current state of the engine:

- **Stochastic damage** — full 10e hit / wound / Armour Penetration / Feel
  No Pain chain with real dice rolls.
- **All five combat phases** — Command, Movement, Shooting, Charge, Fight,
  with Battleshock at round end.
- **2D map and terrain** — continuous-coordinate map with Light /
  Heavy / Obscuring / Impassable terrain; Liang-Barsky parametric clipping
  for line of sight; objective markers with primary victory point scoring.
- **Strategy layer** — units pick a per-activation intent (HOLD, CAPTURE,
  STEAL, ENGAGE, REPOSITION, FALL_BACK) based on objective state and role.
- **Catalogue** — ~1294 units from BSData WH40k 10e (`v10.6.0`), refined
  by `data/overrides.json`.
- **Sweep coverage** — `scripts/evaluate_vs_meta.py` runs the per-faction
  matchup matrix and reports mean absolute error vs the May 2026 Warp
  Friends tournament aggregate. This is the Stage 1 success metric.
- **Two-track points-equation fit** (`code/balancer.py`, `code/equilibrium.py`)
  — Stage 2 work, runs on top of this engine once Stage 1 converges. The
  two tracks supply the equation's coefficients and per-unit residuals.
  See `BASELINE.md`.

For per-feature status and ownership, see `PROJECT.tex`.

## Performance

The simulator's hot path is `Battle.run()` — movement intent selection,
shooting, charge, and fight phases repeated for up to five rounds. Three tiers
of caching were added to reduce per-battle wall time from roughly 117 ms to
roughly 32 ms (73% reduction, measured by `scripts/bench_simulator.py` on a
30-battle benchmark across three matchups):

- **Save and wound probability cache** (`functools.lru_cache` on
  `save_probability` and `wound_probability` in `code/simulator.py`). Both
  functions are pure; there are only a few dozen distinct input combinations
  per battle. Tier 1.
- **Alive-units cache** — `Battle.run()` rebuilds alive-unit lists once per
  round rather than on every phase call. Tier 2.
- **Line-of-sight cache** (`_los_cache` in `code/map.py`). Keyed by a
  terrain-epoch integer (assigned per unique terrain tuple to avoid garbage-
  collector identifier reuse), the 0.5-inch-grid-discretised endpoint pair,
  and the ruin-pass boolean. ~46 000 distinct entries per 90 battles, ~40%
  hit rate, ~1.6× speedup vs uncached. Tier 3.
- **Cover-priority cache** (`_cover_prio_cache` in `code/strategy.py`). Keyed
  by terrain epoch and 0.5-inch-grid position; reused by both
  `_shimmy_target` and `_best_nearby_cover_point`. ~1 300 entries per 90
  battles — high hit rate because cover zones are large. Tier 3.
- **Unsaved-fraction cache** (`_unsaved_fraction` with `functools.lru_cache`
  in `code/strategy.py`). There are only ~200 distinct `(save, invuln_save,
  attacker_ap)` triples in the catalogue; near-100% hit rate after warm-up.
  Eliminates the save-probability calls that `_durability` was making on every
  one of ~56 000 invocations per benchmark run. Tier 3.
- **Cover-point search** (`_best_nearby_cover_point`). Precomputed
  trigonometric constants replace per-call `math.cos`/`math.sin`; a
  running-best comparison replaces the candidate list and `max()` call; the
  `is_blocked()` check is replaced by the cover-priority cache (impassable
  terrain is assigned priority −1). Tier 3.

The benchmark harness lives in `scripts/bench_simulator.py` and runs
`python -m scripts.bench_simulator` (pass `--battles N` or `--profile` for
cProfile output). Baseline numbers and per-tier deltas are in the commit
messages on branch `claude/add-visualization-graphs-Um9Eq`.

## Design Decisions and Trade-offs

### Why Stochastic Damage?

The 2025 prototype used deterministic average-case damage to surface
structural imbalances in ~100 battles per matchup. As soon as the
calibration target moved from "is this army composition balanced?" to
"do per-faction win rates match the real tournament aggregate?", real
dice rolls became necessary — tournament data is the sum of variance-
inclusive games, so the simulator has to match that distribution.
Calibration sample sizes are correspondingly larger (N=200 per pairing
for the honest reading).

### Why Focus-Fire Target Selection?

Focus-fire (targeting lowest-health enemy) eliminates units fastest, maximising the Lanchester
advantage of the attacking army. It approximates the play of an experienced player. Spread-damage
targeting would artificially suppress the score advantage of strong armies, masking imbalances.

### Why Randomise First-Player Each Round?

The goal is to measure structural balance, not first-player advantage. By randomising per round,
the first-player effect averages out over a large number of simulations. A separate experiment can
fix first player to measure the size of that advantage.
