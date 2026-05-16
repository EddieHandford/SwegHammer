# Iter-3 Marines deep diagnostic — root cause of +13.1pt over-perform

Diag script: `scripts/iter3_marines_deep_diag.py`, N=30 per matchup, 9 opponents, 1000pt archetype.

## Measured (9-opponent matrix)

```
opp               WR%   atk  oath%  doc%  cmp%  repS%  M_OC  O_OC  dpaO  dpaX  dpaC
Death Guard       33.3 39.5  11.64 41.23  4.86  23.8   1.1   0.8  2.34  2.38  1.88
Necrons           13.3 39.8   9.55 44.90  4.73  22.7   0.8   1.5  1.41  2.97  1.75
Tyranids          43.3 46.2  14.62 41.79  5.31  19.9   0.9   1.0  1.20  2.19  1.84
Aeldari           76.7 38.8  14.99 41.73  5.11  24.0   0.9   0.5  2.14  2.93  2.22
T'au Empire       43.3 37.5  15.88 43.04  4.80  28.1   0.8   0.6  1.59  2.57  1.20
Orks              60.0 49.2  10.21 41.46  3.88  20.6   1.1   1.0  1.91  2.38  1.98
Adeptus Custodes  50.0 44.5  10.25 43.03  5.22  19.4   0.9   0.8  1.22  1.54  1.14
Thousand Sons     90.0 45.4  18.33 40.05  6.17  23.2   1.2   0.4  1.29  2.32  1.63
Leagues of Votann 80.0 43.3   8.39 40.70  3.83  22.2   1.1   0.6  4.46  2.00  3.91
MEAN              54.4       12.65 41.99  4.88  22.7   1.0   0.8  1.95  2.36  1.95
```

## What's NOT driving over-perform

- **Oath usage**: 12.65% of attacks land on oath_target — *below* real-meta ~30%, not above. The AI's "highest-points alive enemy" picker chooses anchors Marines weren't shooting anyway, so Oath under-fires and on the few attacks where it does fire, dpa_oath (1.95) is *lower* than dpa_other (2.36) because anchors are tougher. Oath is not the leverage.
- **Re-roll stacking**: `units.py:1033/1069` correctly uses `att_reroll_all_*` priority — a die re-rolled under Oath is not re-rolled again under reroll_wound_ones or Twin-Linked. Compound% = 4.88, dpa_compound = 1.95 = dpa_oath: no stacking artefact.
- **OC dominance (post-#179)**: Marine OC 1.0 vs opp OC 0.8 — small edge, not the bulk of the WR. Marines actually score FEWER objectives than opponents in DG/Necron/Custodes matchups.
- **Repulsor**: 22.7% of damage at 19.8% of points — proportional, not anomalous.

## Dominant mechanism — Aggressor mapper bug (BSData v10.6.0)

`code/bsdata/mapper.py:284` OR-aggregates Torrent across a unit's weapon basket:

```python
"torrent": any(x.torrent for _, x in basket),
```

Aggressor Squad has two mutually-exclusive weapon options in BSData:
- **Auto Boltstorm Gauntlets** — Range 18", A=3, BS=3+, S4, D1, **Twin-linked only**
- **Flamestorm Gauntlets** — Range 12", A=D6+1, BS=N/A, S4, D1, **Torrent + Twin-linked**

Mapper merges them into an averaged profile and ORs `torrent` from the Flamestorm variant onto the merged stat block. Result in catalogue:

```
space_marines_aggressor_squad  hit=1.0 (auto-hit, from Torrent)  twin=True  A=4  D=4.5  S=4
```

Real Aggressors are BS 3+ with Twin-Linked re-rolling wounds. The sim grants them **auto-hit AND wound re-rolls AND Doctrine +1-to-wound on 42% of attacks**. A 6-model squad becomes a wound-machine: 6×4 = 24 auto-hits/turn, wounding on 3+ (R1 Devastator), all infantry-dead.

Aggressor sits in the curated Marine archetype (`code/archetypes.py:60`) at count=1 → ~95pt of the 1000pt list. Damage contribution scales with `(auto-hit factor 1.0 / 0.667) × (twin re-roll factor ~1.4)` ≈ 2.1× over-tuned for ~10% of the army's points budget. Compounded by Doctrines and Repulsor support fire, this is the dominant driver of Marines' +13.1pt.

A second Marine entry — `space_marines_land_raider_redeemer` — also has `hit=1.0` via the same path (Flamestorm Cannons are real Torrent, so that one is correct; LR Redeemer isn't in the archetype).

## Top fix — repair Aggressor / weapon-basket Torrent aggregation

**Mechanism**: In `mapper.py:_unify_weapon_basket` (around L284), Torrent should propagate to the merged profile only if **all** weapons in the basket are Torrent — not any. Equivalent to changing `any(...)` to a guarded combination: if the unit has a non-Torrent BS-numeric option in the same basket, the merged profile keeps the numeric BS and drops `torrent`. The merged A / D / S average remains. Twin-linked stays (both variants are Twin-linked, so the wound re-roll is rule-correct).

Wahapedia citation: <https://wahapedia.ru/wh40k10ed/factions/space-marines/#Aggressor-Squad>
(Auto Boltstorm Gauntlets keyword line: "Twin-linked" only. Flamestorm Gauntlets keyword line: "Ignores Cover, Torrent, Twin-linked".)

**Why this fix and not the others**:
- It's a **rule-correction** (mapper fabricates auto-hit on a BS 3+ weapon) — not faction-biased AI.
- Faction-neutral by construction: the mapper change applies to every unit, fixing the same class of bug wherever it occurs (we found 1 other Marine case, LR Redeemer, where the propagation is correct because all variants are Torrent). I scanned all factions: only Aggressors in the archetype templates have a Torrent+non-Torrent mixed basket that the mapper currently mishandles.
- Anti-MEQ counter-tools (the alternative direction) would help vs Marines but bias the rest of the table — a fragile MEQ-light list shouldn't suddenly gain anti-INFANTRY 4+.
- Touching Doctrines or Oath is parked: both are real rules (`marines.json` citations check out), and our measured Oath usage is below real-meta — nerfing Oath would widen the gap, not close it.

**Expected MAE delta**:
- Aggressor's contribution to Marine damage is ~10% of total damage today (1 unit, ~95pt, plus the hit/wound buff stack). Removing the auto-hit factor drops its damage output by ~33% (going from hit=1.0 to hit=0.667). Net Marine damage drops ~3-4%.
- Past linear estimates from F5/iter-2 show ~3% damage swing ≈ 2-3 WR points in Marine-favoured matchups (Aeldari 76.7, TSons 90, Votann 80 — these get the biggest move because squishy lists are exactly where the Aggressor over-shoots).
- **Predicted Marines diff: +13.1 → +9 to +10** (MAE −1.0 to −1.5pt; secondary improvements on Aeldari/T'au/Orks because the AI's "Marines crush MEQ-light" pattern softens).
- Cross-faction: small positive shift for Aeldari/T'au/Votann (closer to real meta because they no longer get nuked in R1). DG/Necrons/Custodes/Tyranid matchups unaffected (Aggressor was already not breaking through tanky lists).

## Test plan for the fix author

1. `python -m unittest discover -s tests` — should pass after mapper change (no test directly asserts Aggressor hit=1.0; spot-check Aggressor's BS in `bsdata.mapper` round-trip test).
2. Re-run `scripts/iter3_marines_deep_diag.py` — Aggressor `hit_probability` should drop to 0.667 (3+ BS); Marines mean WR should drop ~2-3pt.
3. Full `evaluate_vs_meta.py` for the actual cumulative MAE delta.

## Gate

`python -m unittest discover -s tests` → **Ran 644 tests in 94.8s, OK (skipped=5)**.
