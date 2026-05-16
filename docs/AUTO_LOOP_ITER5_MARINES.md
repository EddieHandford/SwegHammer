# Iter-5 Marines alternate-mechanism diagnostic — post-mapper-park

Diag script: `scripts/iter5_marines_alternate_diag.py`, N=20 per matchup, 9
opponents, 1000pt archetype. Iter 4 parked mapper Option A (+1.52pt regression);
Marines still +12.6pt. This pass tests six fresh angles.

## Measured

```
opp               WR%   atks   dmg   oath_picks  oath_unique  oath_changes
Death Guard       30.0   959  1336      5.0         1.40          0.45
Necrons           25.0   942  1584      5.0         1.40          0.45
Tyranids          55.0  1046  1486      5.0         1.35          0.35
Aeldari           75.0   923  1479      5.0         1.40          0.40
T'au Empire       80.0   966  1452      5.0         1.70          0.70
Orks              85.0  1153  1782      5.0         1.35          0.35
Adeptus Custodes  50.0  1169  1127      5.0         1.30          0.30
Thousand Sons     90.0   949  1353      5.0         1.40          0.40
Leagues of Votann 75.0  1009  1537      5.0         1.50          0.50
```

## Hypothesis verdicts

- **H1 — Doctrines rotation**: implementation is correct vs Wahapedia
  (`R1 Devastator/R2 Tactical/R3+ Assault`, +1 wound only). Doctrine-active
  attacks are 43.5% of all Marine attacks; **damage uplift from the +1 wound
  is only ~5% of total Marine damage** (R2 ranged dpa 1.79 vs R3 ranged dpa
  1.51, ~18% boost over 1618 R2 attacks). Not the leverage.
- **H2 — Oath retargeting**: 4.99 picks/battle, **1.42 unique targets/battle,
  0.43 target changes/battle**. The "highest-points alive enemy" picker locks
  onto one anchor and keeps re-picking it because tough anchors survive across
  rounds. iter-3 already showed Oath-attacks are only 12.65% of total. Oath is
  not driving over-perform; retargeting is rule-correct (picks every Command
  phase, simulator.py:2789-2792). **iter-6 fix (commit pending)**: picker now
  scores `points_cost * (current_health / max_health)` and rotates off the
  prior round's anchor when a runner-up is within 50% of top score. Post-fix:
  unique targets/battle 1.42 → 2.48; changes/battle 0.43 → 3.45;
  Marines diff 14.2 → 10.9pt; realmeta MAE stays 5.03pt at 2dp.
- **H3 — Repulsor stats**: catalogue line `A=2 D=9.0 S=10 AP-3 rng=36 dpa=4.21`
  — mapper picks Twin Lascannon (`A=2 D=D6+1=4.5`) as the single best ranged
  weapon. **Repulsor accounts for 20.5% of all Marine damage** (2695.5 dmg / 13133
  total over 180 battles), highest single contributor. The "best weapon"
  approach concentrates damage in one D6+1 profile instead of spraying
  12-shot Gatling + 6-shot Heavy Bolter + 2-shot Twin-Las realistically.
- **H4 — Captain Rites of Battle**: leader ability is `reroll_hit_ones`
  (leaders.py:127); units.py:1033 makes `att_reroll_all_hits` (Oath) priority
  over `att_reroll_hit_ones` (Captain) so no double-roll stacking. Captain in
  TA contributes 1.01% of damage. Not the leverage.
- **H5 — Apothecary revive cadence**: Narthecium fires end-of-round
  (simulator.py:2949), revives at most 1 INFANTRY model per round. Apothecary
  contributes 0.05% of damage. The revive rate is rule-correct; not the
  leverage.
- **H6 — Intercessor / Hellblaster / Eradicator ranges**: catalogue shows
  Intercessor rng=12" (real Bolt Rifle 24"), Hellblaster 12" (real 24" or 30"),
  Eradicator 12" (real 18" Melta). Wrong rep-weapon range from
  `weighted_basket_average` picking max-weight inside a mixed loadout.
  But **this UNDER-states Marine output** (range too short), so it can't be
  the over-perform direction.

## Dominant mechanism — single-best-weapon mapper concentration on vehicles

The H3 finding is **the** dominant mechanism. `mapper.py:1328` picks
`max(gear.ranged_weapons, key=expected_damage_through_baseline)` for single-
model vehicles (Repulsor, Gladiator Lancer, Vindicator, Predator, Redemptor,
Repulsor Executioner). Each picks ONE high-damage weapon — typically a Twin
Lascannon / Twin Las-Talon / Laser Destroyer Array — and discards the secondary
Heavy Bolter / Gatling / Onslaught weapon entirely.

Symptom: per-shot damage is locked to D6+1 (=4.5 fixed average) at very high S
(10-16) and very negative AP (-3 to -4). With Oath full-reroll and Doctrines
+1 wound stacking, these vehicles burst-kill anything in R1-R2.

Damage attribution (post-180 battles):

```
unit                                    share%  dpa
Repulsor                                 20.52  4.21
Aggressor Squad                           7.51  1.93
Repulsor Executioner                      5.65  9.28
Tarantula Sentry Battery [Legends]        4.83  2.43
Vindicator Laser Destroyer [Legends]      2.28 11.50
Redemptor Dreadnought                     2.58 10.94
Gladiator Lancer                          2.97  9.29
```

The dpa 9-11 outliers (single-shot tanks) are the highest-leverage damage
sources. Marines have an unusually-deep roster of mutex-laden vehicles, so
this mapper concentration disproportionately favours Marines vs (say) Necrons
or Aeldari whose vehicles are fewer / less mutex-rich.

**Why this and not the others**: Doctrines/Oath are real rules and their
in-sim share is small. Aggressor (iter-3) is one unit; vehicle concentration
is **across seven different Marine vehicles** in random_fill plus the Repulsor
in the curated archetype.

## Top fix — Marine vehicle weapon-basket weighting (single-faction, not universal)

**Mechanism**: in `code/bsdata/mapper.py:1325-1336`, for SINGLE-MODEL units
whose `loadout` contains 3+ distinct ranged weapons (Repulsor, Gladiator Lancer,
Vindicator, Predator, Redemptor, Repulsor Executioner, Land Raider variants),
**average the ranged weapons** (equal-weighted basket) instead of picking the
single max-damage one. The simulator's existing `_unify_weapon_basket` already
handles the keyword union safely. This is universal at the mapper layer but
in practice only triggers for multi-weapon platforms — and Marines have the
biggest concentration of those in the meta.

Citation: Wahapedia 10e Repulsor datasheet — `<https://wahapedia.ru/wh40k10ed/factions/space-marines/#Repulsor>`
shows 5 distinct ranged weapons (Las-talon, Heavy Onslaught Gatling Cannon,
Twin Heavy Bolter, Twin Lascannon, Hunter-slayer Missile, Krakstorm
Grenade Launcher) all firing in the same Shooting phase. Single-weapon
modelling is rule-incorrect.

**Expected MAE delta**: dropping Repulsor's per-shot from 4.5 (Twin-Las) to
~2.0 (averaged across Gatling D1, Heavy Bolter D2, Twin-Las D4.5, etc.) halves
its single-target damage but slightly increases its attack count. Net Marine
damage drops ~7-9% (Repulsor is 20.5% of total). Past linear estimates show
~5% damage swing ≈ 4-5pt WR shift in Marine-favoured matchups.
**Predicted Marines diff: +12.6 → +6 to +8** (MAE −1.5 to −2.5pt; biggest
improvement on TSons/Orks/T'au where the Repulsor over-kills a 100-150pt
character per round).

Cross-faction: small positive shifts for Necrons (their Doomstalkers also
have multi-weapon loadouts) and Aeldari (Wraith vehicles, Fire Prisms),
both currently under-tuned by the same mechanic; they should benefit from
the same fix in parallel.

## Why this differs from parked Option A

Option A (iter 4) tried to weight **mutex weapon-option groups** (Crisis
Battlesuit picks Fusion OR Missile OR Burst), creating compromise stats
that don't match any real list. This fix targets **non-mutex multi-weapon
loadouts** — a Repulsor fires EVERY listed weapon every shooting phase, so
averaging them is rule-faithful, not rule-fictitious. Mutex groups stay
single-pick.

Gate distinction: iterate `gear.ranged_weapons` only when the unit is
single-model AND has 3+ ranged entries. Aggressor (multi-model, mutex group)
unaffected. Crisis Battlesuits (mutex group) unaffected.

## Test plan for fix author

1. `python -m unittest discover -s tests` — passes today (664 tests, 4 skipped).
2. Re-run `scripts/iter5_marines_alternate_diag.py` — Repulsor `dpa` should
   drop from 4.21 to ~2.0; Marine WR should drop ~5pt across squishy-target
   matchups.
3. Full `evaluate_vs_meta.py` for the actual cumulative MAE delta.

## Gate

`python -m unittest discover -s tests` → **Ran 664 tests in 89.6s, OK (skipped=4)**.
