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
  walking each unit's selectionEntry tree. For multi-model squads the mapper
  builds a **weighted basket of per-model weapons** (e.g. 5 boltguns + 4
  multi-meltas + 1 sergeant for a Devastator Squad) and averages the per-shot
  stats (attacks / damage / AP / S / hit_prob) across the basket. Weapon
  keyword effects (Melta, Anti-X, etc.) take the union — the squad picks the
  right weapon for the right target in-game, but the scaled-down attack count
  prevents this from recovering the all-best cheese. Single-model units fall
  back to the legacy "best legal weapon in the tree" path.
  Squad **size** itself is extracted by `extract_squad_size`, which covers
  four BSData encoding shapes — outer `selectionEntryGroup` with explicit
  `selections` constraints, direct `selectionEntry type="model"` children on
  the unit (Aeldari shape), per-model `scope="parent"` constraints summed
  (Tomb Blades shape), and implicit-via-cost-tier (Jakhals, Neurogaunts).
  See `tests/test_mapper.py::SquadSizeShapeRegressionTests` for one pinned
  victim per shape.
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

All of the points calibration below is **Stage 2** work in the project's
two-stage pipeline — see `CLAUDE.md` "Project plan" and `ROADMAP.md`
"Pipeline structure" for the framing. Stage 2 only becomes reliable once
Stage 1 (the simulator matching reality, mean absolute error against the
Warp Friends tournament aggregate ≤ 2.0 pts) has converged. As of
2026-05-17 Stage 1 is at 7.01 pts at N=200, so every calibrated price in
this section is **provisional** and will need re-running once Stage 1
lands.

SwegHammer runs **three layers** of Stage 2 points calibration. The
analytic formula above produces a fast, well-understood baseline; two
empirical solvers refine it. See `ROADMAP.md` Goal C and `PROJECT.tex`
§"Two-track points calibration" for the full picture.

> **Naming note.** This section used to be titled "Phase One / Phase Two /
> Phase Three". The numbering was renamed to "Layer / Track" in the
> 2026-05 docs reorganisation to avoid colliding with the equilibrium
> solver's own Phase 1 / Phase 2 / Phase 3 ladder (which has different
> semantics — see `code/equilibrium.py`). The outer Stage 1 / Stage 2
> framing is the project-wide pipeline; "Layer 1" and "Track 1 / Track 2"
> below are all subdivisions of Stage 2.

### Layer 1 — Analytic baseline (current default)

Points costs are derived from the offensive/defensive-ratio formula above against
the baseline Marine. Stats come from BSData per the squad-aware mapper —
multi-model squads use a weighted-average loadout (so a Devastator Squad's
damage sits between bolter-only and multi-melta-only, not at the all-best
cheese), while single-model units fall back to the best legal weapon in the
tree. Overrides correct residual mapper artefacts (missing armour profiles
that fall outside the depth-3 wargear walk, units whose squad SEG fails to
parse, etc.).

This does **not** guarantee Lanchester balance (equal aggregate score for equal
points), but provides a well-understood baseline for the simulation to measure
against.

### Track 1 — Sweg-balancer (Monte Carlo bisection, implemented)

`code/balancer.py` runs Monte-Carlo bisection against a **role-stratified
baseline**: each candidate fights a same-role peer (SHOOTY → Intercessor,
MELEE → Assault Intercessor, HORDE → Boyz, HEAVY → Knight, SUPPORT →
Terminator Captain), with the role chosen by `code/roles.py::classify`. The
balanced cost is the points-per-model that lands a 50% ± 5% win rate.

Output: `data/calibrated_points.json`. Slow (1–10 minutes per unit) but
exercises **every** rule in the simulator — terrain, charge variance,
objective contest, CP economy. Captures emergent dynamics analytic models
can't see.

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

### Track 2 — Equilibrium solver (closed-form log-LSQ, implemented Phases 1+2)

`code/equilibrium.py` solves the symmetric zero-sum game over the
catalogue. Build a pairwise time-to-kill matrix `T[i,j] = wounds(j) / D[i,j]`,
derive the log advantage `R[i,j] = ½·log(T[j,i]/T[i,j])`, and solve the
fair-trade condition `log(p_i) − log(p_j) ≈ R[i,j]` in closed form
(row mean over valid entries, anchor pinned to Intercessor Squad at
16 pts/model). See file docstring for the derivation.

Output: `data/equilibrium_points.json` (Phase 1, shooting only) and
`data/equilibrium_points_phase2.json` (Phase 2, shoot+melee blend).
Fast (one analytic damage call per pair, no simulation) and exposes
the pairwise structure — best/worst matchups for every unit are
directly readable off `R`.

The two tracks **disagree on purpose**. Their divergence per unit is
the calibration signal:

- Balancer ≈ Equilibrium → high confidence in the price.
- Balancer ≪ Equilibrium → unit has good pairwise stats but loses to
  battlefield context (slow, no objective play, sim terrain counter).
- Balancer ≫ Equilibrium → unit gets value from non-damaging utility
  the analytic model doesn't see yet (the Goal D signal).

Equilibrium's planned Phases 3–6 (defensive integration audit,
tactical-utility term for non-damaging abilities, meta-weighting,
mixed-strategy zero-sum solve) are tracked under Goal C/D in
`ROADMAP.md`.

### Track 2b — Sim-driven equilibrium (closed-form, real win rates)

`code/equilibrium_simdriven.py` reuses the same row-mean log-LSQ solve,
but replaces the closed-form pairwise damage matrix with one MEASURED
from the simulator: for every ordered pair in a curated diagnostic set,
run `n_battles` full `Battle()` runs at equal points budget and feed
`R[i,j] = logit(observed_win_rate)` into the solver. This is the first
equilibrium phase that picks up faction army rules, detachment
passives, leader auras, movement, charges, and OC contests on
objectives — all the simulator work that closed-form Phases 1–6 cannot
see. Snapshot at `data/equilibrium_points_simdriven.json`; regenerate
with `python -m code.equilibrium_simdriven` (default: ~28-unit
diagnostic set, overnight-tractable). The Streamlit equilibrium tab
offers it as an alternative source via a radio toggle; units outside
the measured set inherit their Phase 1 value (`source="phase1_fallback"`).

### Validation Criteria

A unit is considered "reasonably costed" when:
1. In 1000 equal-points battles against the baseline Marine army, it achieves a win rate of
   45–55%.
2. The result holds across at least three different random army compositions.
3. The cost is within the ±tolerance band of its synergy-adjusted value.
4. The Sweg-balancer and Equilibrium prices agree within ±30% (significant
   divergence signals either a context-dependent unit or a non-damaging
   ability the equilibrium doesn't see yet). Note that this tolerance
   band is itself a Stage-1-dependent artefact: an un-converged simulator
   will exaggerate the divergence because the balancer (which exercises
   every rule) reflects sim drift while the equilibrium (analytic) does
   not. Tighten the tolerance only after Stage 1 lands.

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
