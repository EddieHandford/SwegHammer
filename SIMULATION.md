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

One characteristic stayed deterministic after that work: a weapon's random
Damage characteristic (`D6`, `D3+3`, `2D6`, …) was applied at its
expected-value mean (a `D6` weapon always inflicted a flat 3.5). The
per-model weapon-loadout staging adds an opt-in gate, `SWEG_ROLLDMG`, that
rolls each weapon's real Damage dice once per shot instead (`code.units.roll_damage`).
Unset (the default) keeps the mean and draws no extra dice, so the engine's
output is byte-for-byte unchanged; set, it rolls the dice on the per-model
firing path (the profiles that carry a raw `damage_dice` string). Rolling
follows the 10e ordering — roll the Damage, then apply per-allocation
modifiers (Necrodermis halving, Rend and Tear, Melta) to the rolled value.
The rolled distribution's mean equals the legacy expected-value field, so the
change is a faithful variance model rather than a re-pricing: it tests whether
expected-value overkill on big single-shot guns (a `D6` "reliably" destroying
a 3-wound model where a real roll destroys it about two-thirds of the time)
inflates the elite / big-gun factions. Cited as `simulator.rolled_damage`.

### Damage Allocation (squad spillover)

The engine represents one `Unit` object per physical model, so a codex unit
of N models is N `Unit` instances that share a build-time `squad_id` (assigned
by `Army.add_squad`). When one attacker fires into such a unit, its whole
attack sequence is resolved against that unit, and damage is allocated per the
10e core rule: each unsaved wound is allocated to one model, which loses wounds
equal to the Damage characteristic; a wounded model must keep receiving further
attacks until it is destroyed before allocation moves on; and when a model is
destroyed, **the killing attack's excess damage is lost** — it does not carry
to another model. The allocation pointer in `Unit.attack` advances to the next
surviving same-`squad_id` model only after the current one dies, so the number
of models destroyed is bounded by the number of unsaved wounds, never by the
damage total (three unsaved wounds of Damage 6 destroy at most three one-wound
models). Devastating Wounds is treated as a save-bypassing normal hit under the
same rule (excess lost, no cross-model carry), not as a mortal wound. Cited as
`simulator.damage_allocation_spillover`. Before this rule landed, every shot in
a volley was dumped into a single model and the overkill was wasted, which
heavily under-rated high-volume anti-horde firepower (Knights) and over-rated
multi-model armies (Drukhari, Tyranids).

**Mortal wounds** follow the opposite spill rule and are handled separately by
`Battle._apply_mortal_wounds`: excess mortal-wound damage is **not** lost on a
model's death — it keeps allocating to the next model of the same unit until all
mortal wounds are spent or the unit is destroyed (Feel No Pain rolled per mortal
wound). Every "a unit suffers X mortal wounds" effect routes through it (Doombolt,
the psychic-detachment payload, Bloodthirster, Tank Shock, Dark Pact, Leechspore).
Cited as `simulator.mortal_wound_spillover`. Devastating Wounds is *not* a mortal
wound in the current edition — it is a save-bypassing normal hit and follows the
normal (excess-lost) allocation above. **Deadly Demise** hits each *unit* within
6″ once (not each model): nearby models are grouped by `squad_id` and the unit
takes its X mortal wounds a single time. **Blast** likewise counts the models in
the *targeted unit* (by `squad_id`), not every same-name model in the army.

### Activation Sequence

Each battle round proceeds as follows:

1. **First-player determination**: Randomised once at the start of the battle (50/50) and
   the same player goes first every round thereafter, matching the real mission sequence
   ("The players roll off. The winner declares whether they will take the first or second
   turn."). Default since wave 232; setting `SWEG_ROLLOFF_ONCE=0` restores the legacy
   per-round re-roll.
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
  Ruins block line of sight except when both endpoints carry an INFANTRY,
  BEAST, or SWARM keyword (10e core Ruins rule). When either endpoint carries
  the TOWERING keyword (Knights, Wraithknight, Daemon Primarchs, Titans),
  both Obscuring terrain and Ruin walls are bypassed for line-of-sight
  purposes (10e core TOWERING keyword rule).
- **Strategy layer** — units pick a per-activation intent (HOLD, CAPTURE,
  STEAL, ENGAGE, REPOSITION, FALL_BACK) based on objective state and role.
- **Catalogue** — ~1478 units from BSData WH40k 10e (`v10.6.0`), refined
  by `data/overrides.json`.
- **Additive melee weapon profiles** (`UnitProfile.extra_melee_profiles`) —
  the Fight phase resolves one extra attack pass per entry in this tuple,
  using that entry's own attacks / strength / armour penetration / damage /
  keyword flags. Populated by the BSData mapper for every non-heterogeneous
  unit whose gear contains a melee weapon tagged with the 10e core
  `[EXTRA ATTACKS]` keyword (fires in addition to the model's other melee
  weapons; distinct from the ranged `extra_ranged_profiles` picker, which
  is mutex / pick-one per group). 135 units populated in BSData v10.6.0.
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
  the ruin-pass boolean, and the towering boolean. ~46 000 distinct entries
  per 90 battles, ~40% hit rate, ~1.6× speedup vs uncached. Tier 3.
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
