# Simulation Engine Design

## Overview

The Phase One simulator is a deterministic, average-case combat engine. It models two armies
fighting under Swaghammer's unit-by-unit activation rules and outputs win/loss/draw results that
can be aggregated over thousands of battles to measure balance.

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

### Deterministic Damage

Each unit's attack deals deterministic (average-case) damage:

```
damage_dealt = unit.damage × unit.hit_probability
```

No dice are rolled. This eliminates variance and isolates the structural balance question: given
equal expected performance, which army composition wins?

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

## Simulation Phases

### Phase One (Implemented)

- Deterministic damage only.
- Homogeneous army compositions (one unit type per army) for clean comparison.
- Mixed armies with random composition from the unit catalogue.
- Target: identify systematic over/underperformers at ±5% win rate.

### Phase Two (Planned)

- Introduce stochastic damage (dice rolls) alongside the deterministic baseline.
- Compare variance profiles: do some unit types produce more volatile outcomes?
- Identify cliff-edge combinations (e.g., one hit kills) vs. attrition-stable matchups.

### Phase Three (Planned)

- Sweep all unit-vs-unit pairings and mixed compositions.
- Fit cost surface to simulation data.
- Validate: all pairings within 45–55% win rate at equal points.

## Design Decisions and Trade-offs

### Why Deterministic Damage?

Stochastic simulation requires many more runs to achieve statistical confidence. A deterministic
model reveals structural imbalances cleanly in ~100 battles per matchup rather than requiring
10,000+ for dice-variance to wash out.

The cost is realism: real games have variance that can let weaker lists win through luck. Phase Two
adds this layer once the structural balance is established.

### Why Focus-Fire Target Selection?

Focus-fire (targeting lowest-health enemy) eliminates units fastest, maximising the Lanchester
advantage of the attacking army. It approximates the play of an experienced player. Spread-damage
targeting would artificially suppress the score advantage of strong armies, masking imbalances.

### Why Randomise First-Player Each Round?

The goal is to measure structural balance, not first-player advantage. By randomising per round,
the first-player effect averages out over a large number of simulations. A separate experiment can
fix first player to measure the size of that advantage.
