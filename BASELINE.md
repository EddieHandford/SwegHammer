# Baseline Unit Definition and Calibration

## The Baseline Unit

All points costs and effectiveness scores are calibrated against:

**Standard Space Marine with Bolter** (single model)

| Stat | Value | Notes |
|------|-------|-------|
| Health | 1 wound | Dies to a single bolter hit |
| Damage | 1 | Bolter: one shot, one hit, one damage |
| Hit Probability | 2/3 | BS3+: rolls 3+ on a d6, so 4/6 = 2/3 |
| Movement | 6" | Standard infantry |
| Save | 3+ | Power armour |

**Raw effectiveness**: `e = 1 × 1 × 2/3 ≈ 0.667`

**Lanchester score**: `e² ≈ 0.444`

**Points cost**: `15 pts` (baseline anchor)

## Unit Catalogue

The following units are included in the Phase One catalogue. Stats represent a single model
(for single-model units) or the squad as a single activatable entity (for multi-wound units).

All costs use the Phase One linear formula:
```
points = 15 × (health × damage × hit_prob) / (2/3)
       = 22.5 × health × damage × hit_prob
```

### Space Marines

| Unit | Health | Damage | Hit Prob | Effectiveness | Points |
|------|--------|--------|----------|---------------|--------|
| Scout Marine | 1 | 1 | 0.50 | 0.50 | 11 |
| Space Marine | 1 | 1 | 0.667 | 0.667 | 15 |
| Veteran Marine | 2 | 1 | 0.667 | 1.333 | 30 |
| Terminator | 3 | 2 | 0.667 | 4.000 | 90 |
| Dreadnought | 8 | 3 | 0.667 | 16.00 | 360 |
| Predator Tank | 11 | 4 | 0.667 | 29.33 | 660 |

### Chaos Forces

| Unit | Health | Damage | Hit Prob | Effectiveness | Points |
|------|--------|--------|----------|---------------|--------|
| Cultist | 1 | 1 | 0.50 | 0.50 | 11 |
| Chaos Space Marine | 2 | 1 | 0.667 | 1.333 | 30 |
| Chaos Terminator | 3 | 2 | 0.667 | 4.000 | 90 |
| Chaos Dreadnought | 8 | 3 | 0.667 | 16.00 | 360 |

### Ork Forces

| Unit | Health | Damage | Hit Prob | Effectiveness | Points |
|------|--------|--------|----------|---------------|--------|
| Gretchin | 1 | 1 | 0.333 | 0.333 | 7 |
| Ork Boy | 2 | 1 | 0.500 | 1.000 | 22 |
| Ork Nob | 3 | 2 | 0.500 | 3.000 | 67 |
| Mek Gun | 5 | 3 | 0.500 | 7.500 | 169 |

### Tyranid Forces

| Unit | Health | Damage | Hit Prob | Effectiveness | Points |
|------|--------|--------|----------|---------------|--------|
| Termagant | 1 | 1 | 0.500 | 0.500 | 11 |
| Hormagaunt | 1 | 2 | 0.500 | 1.000 | 22 |
| Warrior | 3 | 2 | 0.667 | 4.000 | 90 |
| Carnifex | 10 | 4 | 0.667 | 26.67 | 600 |

## Calibration Methodology

### Phase One (Current)

Points costs are set using the linear formula above. This provides a reasonable starting point
where:
- A unit that deals twice as much damage per activation costs twice as many points.
- A unit with twice the health costs twice as many points.

This does **not** guarantee Lanchester balance (equal aggregate score for equal points), but
provides a well-understood baseline for the simulation to measure against.

### Phase Two (Planned)

After running the Phase One calibration suite, units that systematically over- or under-perform
will be identified. Points costs will be adjusted up or down for these outliers.

### Phase Three (Planned)

A multidimensional regression fit will replace the linear formula with a calibrated cost surface.
The target: for any pair of equal-points armies, the expected win rate converges to 50% ± 5%.

### Validation Criteria

A unit is considered "reasonably costed" when:
1. In 1000 equal-points battles against the baseline Marine army, it achieves a win rate of
   45–55%.
2. The result holds across at least three different random army compositions.
3. The cost is within the ±tolerance band of its synergy-adjusted value.

## Notes on Hit Probability

Hit probability `P` represents the net probability of a single attack dealing its full damage,
accounting for:
- Base Ballistic Skill (or Weapon Skill for melee)
- Reroll auras (adds ~8–16% to effective hit rate when available)
- Cover and -1 to hit modifiers
- Overwatch, snap shots, and similar penalties

For Phase One, hit probability is the raw BS/WS roll only. Modifiers are added as a tolerance
band adjustment in Phase Three.

| BS/WS | Roll Needed | Base Hit Probability |
|-------|-------------|----------------------|
| BS2+ | 2+ | 5/6 ≈ 0.833 |
| BS3+ | 3+ | 4/6 ≈ 0.667 |
| BS4+ | 4+ | 3/6 = 0.500 |
| BS5+ | 5+ | 2/6 ≈ 0.333 |
| BS6+ | 6+ | 1/6 ≈ 0.167 |
