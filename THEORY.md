# Theory: Lanchester's Square Law and Unit Costing

## 1. Lanchester's Square Law

Lanchester's Square Law models aimed-fire combat where each combatant targets a specific opponent
rather than firing into a mass. Under these conditions, the attrition differential equations are:

```
dA/dt = -β × B
dB/dt = -α × A
```

Where:
- `A`, `B` = number of surviving units on each side
- `α` = combat effectiveness of each A unit (damage rate against B)
- `β` = combat effectiveness of each B unit (damage rate against A)

### The Conservation Invariant

Solving this system yields the conserved quantity:

```
α × A² - β × B² = constant
```

Side A wins if and only if `α × A_initial² > β × B_initial²`.

This is Lanchester's Square Law: **combat power scales with the square of unit count** (for
equal-effectiveness units), or more generally with the product of effectiveness and the square of
count.

### Aggregate Force Strength

For a heterogeneous army with units of varying effectiveness `e_i`, the aggregate Lanchester score
is:

```
Score(army) = Σ e_i²
```

Where `e_i = health_i × damage_i × hit_probability_i` is the raw effectiveness of unit `i`. The
score for unit `i` is therefore `e_i²`.

Two armies are evenly matched when their aggregate scores are equal.

## 2. Unit Effectiveness Metric

The raw effectiveness `e` of a unit captures three factors:

```
e = health × damage × hit_probability
```

- **Health** (`H`): Total wounds. Determines how many hits the unit absorbs before being
  eliminated.
- **Damage** (`D`): Average damage dealt per attack action (pre-hit-roll). A bolter shot deals 1
  damage; a lascannon deals ~3.5.
- **Hit Probability** (`P`): Probability that an attack lands (Ballistic Skill roll, modifiers,
  cover). Baseline is 2/3 for a Space Marine's BS3+.

The unit's Lanchester score is `e² = (H × D × P)²`.

## 3. Points Calibration Strategy

The pricing work described below is **Stage 2** in the project's
two-stage pipeline (see `CLAUDE.md` "Project plan" and `ROADMAP.md`
"Pipeline structure"). Stage 2 assumes Stage 1 has converged — i.e. the
simulator plays like the real game — and freezes the simulator's rules
while iterating on prices. The naming "Stage 2, Layer 1" below avoids
collision with the equilibrium solver's internal Phase 1–6 ladder, which
is a separate concept living inside Stage 2.

### Stage 2, Layer 1: Linear Proportional Pricing

For initial calibration, unit costs are set proportional to raw effectiveness `e`:

```
points(unit) = BASELINE_POINTS × e(unit) / e(baseline)
```

Where the baseline is a single Space Marine with bolter (H=1, D=1, P=2/3), giving:
```
e(baseline) = 1 × 1 × 2/3 ≈ 0.667
points(baseline) = 15
```

This linear pricing means a unit twice as effective costs twice as many points.

**Why not price proportional to score (e²)?**

Pricing proportional to `e²` ensures that equal-points armies have equal aggregate Lanchester
scores, which is optimal for balance under the strict mathematical model. However, it makes elite
units extremely expensive (a unit 3× as effective in raw stats costs 9× as many points), leading
to implausibly large point totals and very small army sizes for powerful units.

Linear pricing is the practical starting point. The nonlinear surface fit
below replaces it. The simulation reveals the actual relationship between
cost and win rate, and the pricing formula is adjusted to achieve 50% win
rates across unit type pairings.

### Stage 2, beyond Layer 1: Nonlinear Surface Fit

The full cost model will incorporate:

- Base stat line (health, damage, accuracy) — primary drivers
- Movement — nonlinear (low mobility is a steep penalty; high mobility has diminishing returns)
- Toughness / saving throws — nonlinear (going from T3 to T4 vs T6 to T7 has different impact)
- Auras and synergies — modelled within a ±tolerance band
- Morale / leadership modifiers

The surface is fit to simulation data so that the expected win rate converges to 50% for all
equal-points matchups across the unit catalogue.

## 4. Nonlinear Attribute Scaling

Not all stats scale linearly with battlefield impact:

### Movement

| Movement | Effect |
|----------|--------|
| 3" | Unit often can't reach objectives or charge range in time — severe penalty |
| 6" | Baseline infantry — can usually reach midfield by round 3 |
| 12" | Cavalry / bikes — strong tactical flexibility |
| 16"+ | Diminishing returns; most boards are captured in 2–3 moves anyway |

A logarithmic or sigmoid scaling captures this: `move_factor = log(1 + move / M_ref)`.

### Toughness / Saves

Toughness interacts with weapon strength to set wound thresholds. The marginal value of +1
toughness depends heavily on the opponent's weapon strength distribution. Near-threshold changes
(e.g., T4→T5 against S4 weapons) have outsized impact.

Saving throws scale similarly: the jump from no save to a 6+ save is more impactful than 2+→1+.

### Accuracy Modifiers

Hit penalties are more damaging at lower base accuracy. A -1 to hit at BS3+ (67%→50%) reduces
output by 25%. A -1 to hit at BS5+ (33%→17%) reduces output by 49%.

The cost impact of accuracy modifiers must be evaluated relative to the unit's base BS, not in
isolation.

## 5. Synergies and the Tolerance Band

Some units derive significant value from army-level interactions: reroll auras, leadership buffs,
stratagems. These interactions resist per-unit calibration.

**Approach**: Accept a tolerance band of ±2–3 points for units with moderate synergy, widening
for aura-dependent units. The goal is balance across the realistic unit-composition space, not
perfection on every niche interaction.

Units with extreme aura dependence (e.g., characters that provide army-wide rerolls) are costed
conservatively and flagged for manual review.

## 6. Why Unit-by-Unit Activation Improves Balance

Under I-Go-You-Go, the first player effectively has an unbounded combat advantage in the opening
phase: all of their units act before any opponent unit responds. This maps to a brief period where
`B = 0` in the Lanchester equations — the first player's damage is uncontested.

Unit-by-unit activation restores the continuous-fire assumption underlying Lanchester's model.
Each activation alternates, so both sides take casualties concurrently. The aggregate score ratio
now governs outcomes rather than activation order.

The remaining first-mover advantage (who activates first within a round) is reduced to a single
unit's worth of unopposed fire — a tractable and statistically small effect.
