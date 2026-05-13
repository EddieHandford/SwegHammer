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

## Points Formula (current)

Implemented in `code/units.py::points_for`. The cost combines two ratios against
the baseline Marine:

```
offensive_ratio = damage × hit_prob × (1 - baseline_save_after_AP)
                  ────────────────────────────────────────────────
                  baseline_damage × baseline_hit_prob × baseline_survival

defensive_ratio = (health / (1 - own_save_prob))
                  ──────────────────────────────
                  (baseline_health / baseline_survival)

points = 15 × (offensive_ratio + defensive_ratio) / 2
```

Averaging the two ratios (rather than multiplying) prevents runaway costs for
units that dominate on both axes — see `THEORY.md` for the Lanchester derivation.

## Unit Catalogue

The catalogue is derived from BSData's WH40k 2nd-edition data files. There are
~240 units in `UNIT_CATALOG`, built at import time from:

- `data/bsdata/parsed.json` — base stats produced by `code/bsdata/mapper.py`
  walking each unit's selectionEntry tree and picking the best legal weapon
  (the loadout that maximises damage through baseline-Marine armour).
- `data/overrides.json` — per-unit hand tuning. Any field listed here overrides
  the BSData base. Entries without a corresponding BSData entry become
  fully hand-rolled units.

Refresh the BSData base with:

```
python -m code.bsdata.fetch --tag v1.9.7   # current pinned release
python -m code.bsdata.mapper                # rebuild parsed.json
```

See `CLAUDE.md` for the rules around tuning vs editing the mapper output.

## Calibration Methodology

### Phase One (current)

Points costs are derived from the offensive/defensive-ratio formula above against
the baseline Marine. Stats come from BSData per the loadout-optimised mapper —
each unit's "best legal weapon" sets its damage and AP. Overrides correct
mapper artefacts (squad weapons mis-applied per-model, missing armour profiles
that fall outside the depth-3 wargear walk, etc.).

This does **not** guarantee Lanchester balance (equal aggregate score for equal
points), but provides a well-understood baseline for the simulation to measure
against.

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
