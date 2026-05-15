# Faction F1 — Tyranids Invasion Fleet over-performance diagnosis

Status: diagnosis only. No sim/AI code changes in this pass.

## TL;DR

The Tyranid Invasion Fleet archetype wins **79.6%** of seeded battles vs the
other nine archetypes (N=30/matchup, archetypes enabled, BSData main, 1000 pts,
PYTHONHASHSEED=0). Real Tyranid tournament WR is 48.0%, so the sim
**over-performs by +31.6pt** averaged across the field (and the headline
+38.1pt in the larger eval is consistent with this — the archetype-vs-archetype
matrix is tighter than the full random-pool eval).

**Root cause (ranked by evidence):**

1. **Objective control swarm dominates primary scoring** — H1, mostly correct
   but the gap opens R2-R5, not R1.
2. **Synapse Imperative auto-passes Battleshock for the entire swarm** — H2,
   confirmed strongly.
3. **Opposing AI cannot focus down the screen** — H3, partially confirmed.
4. **Hormagaunt charges are not the deciding factor** — H4, weak signal.

## Per-matchup WR (N=30, archetypes enabled, 1000 pts)

| Opponent              | Tyranid WR | vs real (48.0%) | Avg TYR/OPP final VP |
|-----------------------|-----------:|----------------:|----------------------:|
| Adeptus Astartes      |   43.3%    |         -4.7    | 51.5 / 51.2           |
| Necrons               |   76.7%    |        +28.7    | 59.8 / 42.2           |
| Aeldari               |   83.3%    |        +35.3    | 59.8 / 34.2           |
| Orks                  |   86.7%    |        +38.7    | 62.2 / 41.7           |
| **T'au Empire**       | **96.7%**  |       **+48.7** | 73.8 / 34.2           |
| Death Guard           |   80.0%    |        +32.0    | 60.5 / 44.7           |
| Adeptus Custodes      |   83.3%    |        +35.3    | 60.2 / 36.3           |
| **Thousand Sons**     | **90.0%**  |       **+42.0** | 64.0 / 34.3           |
| Leagues of Votann     |   76.7%    |        +28.7    | 62.0 / 37.5           |
| **Average**           | **79.6%**  |       **+31.6** | —                     |

Only Adeptus Astartes (chapter-tactics aren't archetype-modelled but Marines
have raw firepower per model and Oath of Moment) actually holds the swarm down.
**Three worst over-performers: T'au (+48.7pt), Thousand Sons (+42.0pt),
Orks (+38.7pt).** All three lack a way to efficiently clear ~30 single-model
1W chaff bodies per battle.

## Evidence pack

### 1. OC asymmetry on objectives (per-round, 10 battles avg)

| Opponent          | R1 TYR/OPP | R2 TYR/OPP | R3 TYR/OPP |    R4 TYR/OPP |
|-------------------|-----------:|-----------:|-----------:|---------------:|
| T'au Empire       |   6.9/4.1  |  16.7/3.7  |  11.9/1.3  |  **35.5/1.0**  |
| Thousand Sons     |   6.7/3.8  |  14.2/3.7  |  10.9/2.9  |  **27.8/2.3**  |
| Aeldari           |   6.9/2.6  |  10.8/2.0  |  10.1/1.1  |  **24.4/1.4**  |
| Adeptus Custodes  |   8.0/4.5  |  15.4/5.3  |  13.4/3.6  |  **25.4/3.2**  |
| Necrons           |   5.8/2.5  |  11.4/3.2  |  10.3/2.4  |    10.9/3.5    |

TYR OC on objectives is **3x-30x** opponent OC by R4. The Invasion Fleet
archetype instantiates **2 Termagant squads × 10 models + 1 Hormagaunt squad
× 10 models + 1 Gargoyle squad** plus random-fill chaff, which builds an
army of ~37-39 single-model Unit instances at **OC=80 total**. The average
non-Tyranid archetype carries OC ≈ 28-50 (Custodes 28, Marines 40, Aeldari
34) — Tyranids are 1.5-3x ahead before a single die is rolled.

### 2. Termagant + Hormagaunt screens are essentially invulnerable to BS

Across 30 vs-T'au battles: **0 Tyranid Battleshock failures**. Across 30
vs-Orks battles: 10 fails total, none on Termagants/Hormagaunts — they hit
Tyrannofex / Winged Hive Tyrant / Tyranid Warriors instead. Confirmed in
`code/simulator.py:1678-1691`: any Tyranid unit within 6" of any friendly
SYNAPSE model auto-passes. The Hive Tyrant + Zoanthropes pair (the archetype's
two SYNAPSE units) blanket the swarm because the swarm moves in a tight
cluster toward Tyranid-side objectives.

### 3. Opposing AI under-targets the screen

Traced vs-T'au battle (seed=1, TYR wins 75-35). T'au's whole-battle attack
distribution across Tyranid targets:

| Tyranid target          | Attacks taken | OC |
|-------------------------|--------------:|---:|
| Tyrant Guard            |       13      |  1 |
| Deathleaper             |       12      |  1 |
| Hormagaunts             |       12      |  2 |
| **Termagants**          |      **4**    |  2 |
| Gargoyles               |        1      |  2 |
| Node Organism (SYNAPSE) |        1      |  1 |

T'au attacked the screen 17 times (Termagants + Hormagaunts + Gargoyles)
versus 35 times into named non-screen units. The simulator's shoot-target
picker (`code/simulator.py:2023-2036`) picks the **lowest-current-HP unit
that contests our objectives**, falling back to lowest-HP globally. But:

* The screen mostly sits on **TYR-side** objectives, not OPP objectives,
  so the "contests our objectives" path doesn't fire on them.
* Among targets in range, post-damage Tyrant Guard / Deathleaper drop below
  Termagant HP after a single salvo and become "lowest HP".
* Critically, the picker selects **one** target for the entire shooting
  activation — so a 5-shot Riptide salvo dumps everything into a single
  Tyrant Guard model rather than mowing through ten Termagants.

### 4. Attrition disparity confirms screen survival

Same vs-T'au trace: cumulative unit kills by round —

| Round | TYR units killed | OPP units killed |
|-------|------------------|------------------|
| R1    | 1                | 1                |
| R2    | 2                | 11               |
| R3    | 4                | 18               |
| R4    | 1                | 3                |
| R5    | 1                | 1                |

By R3, T'au is **down 18 units** while only managing 7 kills against TYR.
The Tyranid swarm reaches T'au lines in R2-R3 and the swarm's 37 melee/shot
events in R3 obliterate T'au infantry and Battlesuits.

### Hypotheses verdicts

| # | Hypothesis                                       | Verdict                         |
|---|--------------------------------------------------|---------------------------------|
| H1 | Termagant swarm OC opens primary VP gap on T1   | **Partial** — gap opens R2-R4, not R1; R1 OC is only 1.5x. |
| H2 | Synapse auto-passes BS, swarm stays cohesive    | **Confirmed strongly** — 0 BS fails vs T'au in 30 battles. |
| H3 | Opposing AI targets monsters, ignores screen    | **Confirmed** — only 4/65 attacks vs Termagants in traced battle. |
| H4 | Hormagaunt charges decide it                    | **Weak** — chrg succeeded 244/498 vs T'au (49% rate), part of the picture but the screen + monsters already win primary alone. |

## Recommended fixes (do NOT implement in this task — diagnosis only)

Ranked by expected MAE-closing impact:

### Fix 1 — Cap or down-rate the archetype's chaff allocation (highest impact)

The `tyranids_termagants: 2` + `tyranids_hormagaunts: 1` template, combined
with each squad spawning `min_models=10` separate Unit instances and the
random-fill stage piling on more Hormagaunts/Termagants from the random pool,
produces 30+ OC-2 bodies. **Drop the template to 1 Termagant squad** and add
a non-chaff entry (e.g. Tyranid Warriors) to prevent random-fill from
re-creating the swarm. Estimated impact: **-15 to -20pt MAE** on Tyranids
alone (this is the biggest lever).

Optional companion: lower `SEED_FRACTION` to 0.2 for Tyranids specifically,
or add a per-faction OC-cap pass in `build_archetype_army` that re-rolls
random fill if total army OC exceeds N × (battlefield_size/2k).

### Fix 2 — Make the shoot-target picker volume-aware (medium impact)

`Battle._do_shoot` currently picks ONE target via `min(current_health)`.
Real shooting splits unsaved wounds across the squad and the next model in
line absorbs leftover damage. Switch to:
* Prefer a target whose `current_health <= expected_damage_of_this_activation`
  (i.e. a model we can outright kill in one go).
* Among such targets, pick highest OC (or highest threat) — kills the screen
  body that's actually contesting.

This nudges T'au pulse rifles into Termagants (1W, killable in 1 shot) rather
than burning a full activation on a Tyrant Guard model they'll only chip.
Estimated impact: **-5 to -10pt MAE** on Tyranids (also helps Orks and
Death Guard which have similar chaff dynamics).

### Fix 3 — Synapse range tightening / aura cap (smaller impact)

`simulator.synapse_imperative` currently has zero failure mode: a Hive Tyrant
plus Zoanthropes pair covers the whole swarm because all units mass-march
together. Two options:
* Reduce auto-pass to a **+2 Ld bonus** (still strong, but not auto-pass) when
  the unit is below half-strength, with auto-pass only at full strength —
  matches the "synapse holds you together until you're hit hard" flavour
  without rewriting the rule.
* Or: require synapse-source to be ALIVE AND not in melee. Currently a HT
  brawling in melee still projects its 6" aura.

This is the smallest lever (BS isn't the binding constraint — primary OC is)
but it's a correctness fix worth queueing. Estimated impact: **-2 to -4pt
MAE** on Tyranids.

## Files referenced

- `code/archetypes.py:89-99` — Invasion Fleet template definition
- `code/archetypes.py:320-326` — squad → individual Unit instance loop
- `code/simulator.py:1625-1700` — Synapse Imperative implementation
- `code/simulator.py:2023-2036` — shoot-target picker (lowest-HP)
- `scripts/tyranid_diag.py` — per-matchup WR + event counts (this diagnosis)
- `scripts/tyranid_trace.py` — single-battle event trace
- `scripts/tyranid_oc_check.py` — per-round OC-on-objective measurement
