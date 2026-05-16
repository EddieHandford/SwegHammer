# Faction T1 — Tyranids vanilla-10e residual over-performance re-diagnosis

Status: diagnosis only. No simulator/AI code changes in this pass.

## Context

After the simulator default flipped to vanilla WH40k 10e mode
(`Battle.__init__` now constructs `RulesConfig.vanilla_10e()` by default — see
commit `ddb44db`), Tyranids' headline over-performance dropped from +10.3pt
(SwegHammer mode) to +9.2pt (vanilla) in the full eval-vs-meta run. Real
tournament WR is 48.0%; sim reports 57.2%. The flip alone did not fix the
faction.

Prior mitigations already shipped:
- G1 anti-swarm AI: non-Tyranid attackers prefer SYNAPSE targets at +1.5x
  priority (`code/strategy.py:460`).
- Phase 5 / Phase 6 equilibrium repricing (Termagant / Hormagaunt / Hive
  Tyrant points adjusted).

Despite this the residual gap is large enough to warrant a re-diagnose.

## Method

`scripts/tyranids_vanilla_diag.py` — N=30/matchup, archetypes ON, 1000pt,
vanilla 10e rules, three opponents (Adeptus Astartes, T'au Empire, Aeldari).
The three opponents were chosen to cover the meta diversity that drove the
original F1 finding (Marines = the only matchup that previously held the
swarm down; T'au = worst over-performer; Aeldari = mid-tier reference).

## Headline numbers

| Opponent          | TYR WR | vs real (48%) | TYR VP / OPP VP |
|-------------------|-------:|--------------:|----------------:|
| Adeptus Astartes  |  63.3% |        +15.3  | 45.0 / 35.3     |
| T'au Empire       |  73.3% |        +25.3  | 56.7 / 29.2     |
| Aeldari           |  73.3% |        +25.3  | 46.7 / 35.8     |
| **Average**       |**70.0%**|     **+22.0**| 49.5 / 33.4     |

The 3-matchup slice over-performs by +22pt — much wider than the full-field
+9.2pt headline, which is the average across the whole 9-opponent matrix.
Tyranids still beat the "ranged glass-cannon" archetypes (T'au, Aeldari) by
huge margins; Marines remain their hardest matchup.

## Hypothesis test results

### H_SwarmKills — REJECTED

Tyranid model kills per battle vs opponent kills per battle:

| Opponent          | TYR kills | OPP kills | Ratio |
|-------------------|----------:|----------:|------:|
| Adeptus Astartes  |    8.67   |   15.13   | 0.57x |
| T'au Empire       |   12.33   |    9.70   | 1.27x |
| Aeldari           |   10.90   |   13.77   | 0.79x |
| **Average**       | **10.63** | **12.87** | **0.88x** |

Tyranids actually take MORE casualties than they inflict on average. The
swarm is NOT out-trading — it is getting cleared. The model-trade
hypothesis is rejected; vanilla turn order does not let Tyranids deliver a
disproportionate kill output.

### H_SynapseExploit — PARTIAL CONFIRM

Fraction of battles where every TYR-side SYNAPSE unit (Hive Tyrant +
Zoanthropes seed) is alive at end of game:

| Opponent          | All-SYNAPSE-survive frac |
|-------------------|-------------------------:|
| Adeptus Astartes  |                   30.0%  |
| T'au Empire       |                   60.0%  |
| Aeldari           |                   46.7%  |
| **Average**       |               **45.6%** |

Almost half the time Tyranids preserve their full Synapse umbrella through
all 5 rounds. The G1 +1.5x SYNAPSE target bonus is therefore being out-paced
by something — the Synapse units are simply too tough / too well screened
for ranged attackers to actually kill them once prioritised. Highest in the
T'au matchup (60%) where the over-performance is also worst, which is the
expected correlation if Synapse persistence drives the gap. But the metric
is moderate, not extreme.

### H_ChargeWave — PARTIAL CONFIRM (matchup-specific)

Tyranid melee strikes (UnitFought events) vs opponent strikes:

| Opponent          | TYR strikes | OPP strikes | Ratio  | TYR succ. charges | OPP succ. charges |
|-------------------|------------:|------------:|-------:|------------------:|------------------:|
| Adeptus Astartes  |        9.53 |       11.97 |  0.80x |              3.77 |              9.07 |
| T'au Empire       |        6.03 |        3.00 |  2.01x |              2.73 |              1.70 |
| Aeldari           |        4.63 |        3.60 |  1.29x |              2.33 |              2.27 |
| **Average**       |    **6.73** |    **6.19** |**1.36x**|         **2.94** |          **4.35** |

Average ratio is 1.36x — well below the 3x threshold proposed. Marines
out-melee Tyranids 1.25x by strike count (9.07 successful Marine charges vs
3.77 Tyranid charges per battle). The "coordinated charge wave" hypothesis
holds only against pure-ranged opponents like T'au, where any melee
presence trivially wins by default. Vanilla turn order is not the lever.

## Root cause

**It's still primary scoring through Objective Control, not combat — the
F1 diagnosis remains accurate under vanilla rules.**

TYR averages 49.5 VP vs OPP 33.4 VP per battle (1.48x). They lose the model
trade (0.88x kills), tie or lose the melee race against melee opponents
(0.80x vs Marines), yet score 50% more primary VP. This is mathematically
only possible via OC dominance — Termagant / Hormagaunt / Gargoyle squads
hold objectives even while dying, and the Synapse Imperative auto-pass
means the chaff that survives keeps full OC instead of being battleshocked
to OC 0. The G1 +1.5x SYNAPSE target bonus only matters if attackers can
actually finish the kill before the screen has scored R3/R4/R5 primary, and
the H_SynapseExploit 45.6% confirms attackers usually cannot.

The vanilla-10e flip did almost nothing for Tyranids (-1.1pt of the +10.3
SwegHammer over-performance) because Tyranid dominance is not driven by
either alternating-activation timing OR coordinated-army-plan scheduling —
both of those flipped off when the default changed. It is driven by the
raw OC arithmetic of the seeded archetype: 2x Termagants (10) + 1x
Hormagaunts (10) + 1x Gargoyles ≈ 30 OC2-cluster bodies × auto-pass
Battleshock = unkillable primary-scoring engine.

## One concrete fix proposal

**Re-tune the Invasion Fleet archetype seed to reduce raw chaff-OC.**

In `code/archetypes.py:89-99`, drop one of the two Termagant squad slots
and replace it with a higher-points, lower-model-count unit (e.g.
`tyranids_carnifexes` or `tyranids_warriors_with_ranged_bio_weapons`).
Current seed:

```python
"Invasion Fleet": {
    "tyranids_termagants": 2,         # → drop to 1
    "tyranids_hormagaunts": 1,
    "tyranids_hive_tyrant": 1,
    "tyranids_zoanthropes": 1,
    "tyranids_exocrine": 1,
    "tyranids_carnifexes": 1,         # → keep or bump to 2
    "tyranids_gargoyles": 1,
}
```

Rationale: the F1 evidence showed Tyranid OC was 1.5-3x opponent OC by R4,
driven by the dual-Termagant seed under the 30%-of-budget archetype anchor
slice. Removing one Termagant template entry reduces seeded chaff by ~10
single-model OC2 bodies (since each Termagant squad is 10 models) and
swaps that budget toward a unit that scores fewer-but-tougher OC, putting
Tyranid primary scoring in line with the other swarm-adjacent archetypes
(Necron Warriors, Death Guard Plague Marines).

This is the same lever the T'au G8 fix used (rebalance archetype
template to seed the actual-meta unit mix) and is consistent with real
tournament Tyranid lists, which run 1 squad of Termagants + 1 of
Hormagaunts at the 1000pt scale — not 2 squads of Termagants. Verify
post-fix with `python -m scripts.tyranids_vanilla_diag`; target average WR
≤ 55% across the 3 opponents.

**Out of scope for this pass:** do not change Synapse logic (it is
correctly implemented per Wahapedia), do not adjust the G1 +1.5x SYNAPSE
target priority bonus (it is doing the right thing but cannot overcome a
30-body OC wall), do not auto-write overrides.json.
