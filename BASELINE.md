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

The catalogue is derived from BSData's WH40k 10th-edition data files. There are
~1100 units in `UNIT_CATALOG`, built at import time from:

- `data/bsdata/parsed.json` — base stats produced by `code/bsdata/mapper.py`
  walking each unit's selectionEntry tree and picking the best legal weapon
  (the loadout that maximises damage through baseline-Marine armour).
- `data/overrides.json` — per-unit hand tuning. Any field listed here overrides
  the BSData base. Entries without a corresponding BSData entry become
  fully hand-rolled units.

Refresh the BSData base with:

```
python -m code.bsdata.fetch --tag v10.6.0   # current pinned release
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

### Phase Two — Empirical bisection (implemented)

`code/balancer.py` runs Monte-Carlo bisection against a **role-stratified
baseline**: each candidate fights a same-role peer (SHOOTY → Intercessor,
MELEE → Assault Intercessor, HORDE → Boyz, HEAVY → Knight, SUPPORT →
Terminator Captain), with the role chosen by `code/roles.py::classify`. The
balanced cost is the points-per-model that lands a 50% ± 5% win rate.

**Leader-attached mode** (`--leader-attached`): for `CHARACTER` units, the
candidate is built as `(host + leader)` pairs vs. a baseline of `host alone`
at equal points. This exercises the leader's aura on a real bodyguard squad
instead of fighting copies of itself. The host is the cheapest same-faction
INFANTRY unit by default, chosen by `code/roles.py::pick_host_for_leader`.
Only the leader's cost is bisected; the host's cost is held constant.

**Aura uplift mode** (`--aura-uplift`): for SUPPORT characters whose value
lives entirely in buffing a client unit (not in direct combat), bisection
against same-role peers stalls — both sides field copies of the SUPPORT
baseline (Terminator Captain) and the aura cancels out. Aura-uplift mode
runs two matched measurements: `wr_with` for (client + support) pairs vs
client alone, and `wr_without` for client alone vs client alone. The
DELTA `wr_with - wr_without` is the support unit's contribution. A single
linear-conversion constant `_UPLIFT_TO_POINTS_FACTOR = 100 / 0.10`
(10% win-rate uplift ≈ 100 pts at a 1000-pt budget) maps the delta to a
points-equivalent cost. Single-shot, no bisection — sufficient for v1.
CLI: `--aura-uplift` with optional `--client KEY` to override the client.

**Mobility covariates**: each `CalibrationResult` records the candidate's
movement, scout distance, and Deep Strike / Infiltrator flags. These are
diagnostic — used to spot whether the simulator's 5-round window is
under-rewarding speed (e.g. a MELEE@M=5 unit consistently calibrating
cheaper than a MELEE@M=8 unit). No effect on the bisection itself.

### Phase Three (Planned)

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
