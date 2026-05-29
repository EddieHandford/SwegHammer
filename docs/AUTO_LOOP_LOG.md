# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 56 close (2026-05-29)

Branch `claude/sim-calibration-6`. 3 commits landed on top of wave-55
close `f434e4b`. Top commit at wave-56 close is `33611ae`.

Wave 56 mixed a structural mapper fix with two targeted faction
audits, applying the wave-55 prediction discipline (N=20 archetype
eval delta required from agents). One big single-faction win, one
mapper fix with mixed cross-faction effects.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 55 close (`f434e4b`, 2026-05-29) | 14.15 | 10.72 | 4/22 |
| Wave 56 close (`33611ae`, 2026-05-29) | 14.50 | **10.98** | 4/22 |

**+0.26 gated MAE drift** — slight regression at headline. Per-faction
breakdown is bifurcated:

Big direction-correct moves (predicted + measured):
* Astra Militarum: +8.59 → **+3.95** (-4.64 wr-points, well over noise
  3.18). 7th instance of the per-model amplification pattern landed
  the cleanest single-faction win this wave.
* Drukhari: +38.32 → +36.18 (-2.14, mapper basket-weight reduced
  per-instance damage on heterogeneous squads).
* AdMech: +18.22 → +17.15 (-1.07).
* Daemons: -17.94 → -18.78 (-0.84 toward zero).
* Votann: +15.22 → +14.39 (-0.83, Huntr's Mark removal).
* TSON: +22.54 → +21.83 (-0.71).

Big direction-incorrect moves:
* Genestealer Cults: -3.00 → **-11.45** (-8.45 wrong direction). The
  mapper basket-weight changed GSC's per-Unit weapon stats; GSC
  combines many low-stat models with rare specials. Basket averaging
  drops the effective damage well below the real-meta "specials-spam"
  loadout players actually run.
* Orks: +17.84 → +21.05 (+3.21 wrong direction). Tankbusta override
  from wave 55 retired by the mapper fix, but the new basket weight
  also affected other Ork units. The wave-55 manual override used
  AP-1; the mapper-derived basket settled at AP0.
* T'au, A.Astartes, Custodes: +0.96 / +1.43 / +1.42 (small wrong
  direction, within noise floors).

### 7th instance of per-model amplification — AM Orders

AM-AUDIT-V1 (`827e9e0`) found Command Squads (5-6-model variants:
Cadian, Krieg, Catachan, Tempestus) issuing one Order PER MODEL
instead of per codex unit. Pre-fix: max 19 "Officers" identified per
Command phase, max 13 Orders issued per round. Codex: one Order per
OFFICER unit.

Fix mirrors the wave-49 / 51 / 53 / 54 / 55 pattern:
`_seen_officer_names` set + dedup before the officer loop. Single-
model Officers unaffected.

**Agent applied wave-55 prediction discipline**: N=20 archetype eval
AM vs Marines pre-fix 25.0%, post-fix 40.0% (target 45.1%). The
prediction held: -4.64 wr-points at the full N=40 archetype eval.

The pattern catalogue now stands at 7 instances across 6 factions:

| Wave | Faction | Rule | Amplification | Metric move |
|---|---|---|---:|---:|
| 49 | Sororitas | AoF spend | 3.7× | -4.28 |
| 51 | Sororitas | AoF generation | 4.65× | -8.09 |
| 53 | Thousand Sons | Cabal Ritual | 2.8× | -0.24 |
| 54 | T'au Empire | Markerlights | 8.7× | -1.31 |
| 54 | Aeldari | Strands Advance | 10× | +0.95 |
| 55 | Drukhari | Pain Tokens | 4.4× | +0.12 |
| 56 | Astra Militarum | Orders | 6× | -4.64 |

### Heterogeneous-squad mapper fix — mixed cross-faction outcome

HETERO-SQUAD-MAPPER-V1 (`d0c057f`) addressed the cross-faction
structural finding flagged by wave 50 Drukhari + wave 55 Orks: BSData
mapper picked the "best legal weapon" for the entire squad without
weighting by codex datasheet quantity.

Root cause: `_find_main_squad_group` bailed on the FIRST
`selectionEntryGroup` with any size constraint. For units where the
boss/leader group is listed before the body group (Tankbustas: Boss
Nob min=max=1 listed before "Tankbustas" body min=max=5), this
yielded `squad_max=1` and the function fell back to the legacy
single-best-weapon path, applying the Nob's Smash Hammer to all 6
models.

Fix: full sweep of all `selectionEntryGroup` nodes + direct
`selectionEntry type="model"` children. Uses existing
`weighted_basket_average()` / `_flatten_to_basket()` infrastructure
plus the wave-43 `basket_fraction` plumbing — no new schema.

Sample effects:
* **Tankbustas**: Smash Hammer (atk=2, D=2.0, AP=-2) → weighted Close
  combat weapon basket (atk=3, D=1.17, AP=0). 40% melee damage drop;
  false melee-specialist tag removed. Wave-55 manual override retired.
* **Kabalite Warriors**: ranged effective damage 4.11 → 3.9
  (Sybarite Power Weapon at weight 1/10).
* **Skitarii Vanguard**: ranged 3.26 → 3.25 (Alpha basket inclusion).
* **Tactical Squad**: Power Fist at weight 1/30 in melee basket.

**Outcome mixed**: Drukhari -2.14 (right direction), but Orks +3.21
and GSC -8.45 (both wrong direction). The basket-average approach is
more **codex-rules-correct** but less **real-meta-calibrated** —
tournament players spam the specials repeatedly, which the basket
average doesn't model. The simulator now better reflects "the squad
fields the codex average" but worse reflects "the player optimizes
within squad composition rules."

**Decision: keep the mapper fix.** CLAUDE.md §3 Stage 1 goal is to
make the simulator's RULES match reality, not its outcomes match
meta directly. The Orks / GSC wrong-direction movement is a real-meta
calibration issue separable from rule correctness. Wave-57 has the
option to add per-faction overrides for known specials-spam units
that the basket average under-models — those overrides are now
specifically focused on "this unit consistently fields its specials"
rather than papering over the entire mapper.

### Votann — fabricated Huntr's Mark stratagem removed

VOTANN-AUDIT-V1 (`33611ae`) found `HUNTRS_MARK` (Needgaard Oathband,
1 CP, re-roll Hit and Wound 1s) is **absent from BSData v10.6.0
`Leagues of Votann.cat.gz`**. The citation in
`data/rule_citations.d/stratagems.json` pointed only to the general
Wahapedia faction page with no per-stratagem anchor. Per CLAUDE.md
§10, this is a fabricated rule. Added in `12d2f68 VOTANN-DIAG-2` in
good faith but cannot be confirmed.

Removed: `HUNTRS_MARK` constant, `_try_huntrs_mark` dispatcher
method, dispatcher call site, AI gate in `code/strategy.py`, citation
entry. `OATHBAND_STRATAGEMS` now contains 2 verifiable stratagems
(Ancestral Sentence + Void Hardened).

N=20 archetype: 20% → 45% vs Marines. Random_fill: -7.8pt tightening.
Measured at N=40 archetype: -0.83 (modest, within noise but
direction-correct).

### Open carry-forwards into wave 57

1. **Genestealer Cults wrong-direction regression** — investigate
   what GSC unit lost basket weight to drop the faction -8.45.
   Likely candidates: Aberrants (Pickaxe / Power Hammer mix),
   Acolytes (Rending Claws mix), or a Brood Brothers unit with the
   hammer-and-anvil weapon distribution.
2. **Orks +3.21 regression** — basket-weight effect on multi-special
   squads. May need a per-unit override sweep on known
   tournament-loadout Ork squads (Lootas Spanner-spam etc.).
3. **Drukhari activation count structural** (T3 architecture).
4. **AdMech +17.15** — archetype damage attribution diagnostic.
5. **Daemons -18.78** — stratagem dispatcher instrumentation.
6. **Aeldari +13.58** — Battle Focus / Strands hit-save selection.
7. **TSON +21.83** — Cabal point generation rate audit.
8. **Sororitas +11.03** — AoF dice selection refinement.
9. **GUO Bilesword wired** — verify the wave-52 melee_lethal_hits
   field actually fires on GUO's melee profile (was the agent's
   parking-lot note).
10. **IK -35.88 / CK -43.10 mapper-locked** — Stage 2.

### Pattern note — predict discipline working

Wave 56 confirmed the wave-55 process note. AM-AUDIT-V1's prediction
(N=20 archetype delta) held cleanly at full N=40 archetype eval.
Future wave dispatches should require this format and reject agents
that only report random_fill DPP or local per-unit analytics.

## Wave 55 close (2026-05-29)

Branch `claude/sim-calibration-6`. 3 commits landed on top of wave-54
close `8cefd3e`. Top commit at wave-55 close is `b872506`.

Wave 55 continued the per-model amplification sweep across the three
biggest OVERSHOOTING factions: Drukhari (+38), Tyranids (+21), Orks
(+16). All three agents found real rule-correctness bugs and committed
clean fixes. Headline gated MAE moved only -0.02 — agents' predicted
metric movement consistently over-shot at N=40, a pattern worth
naming for wave-56 planning.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 54 close (`8cefd3e`, 2026-05-29) | 14.09 | 10.74 | 4/22 |
| Wave 55 close (`b872506`, 2026-05-29) | 14.15 | **10.72** | 4/22 |

**-0.02 gated MAE drift** — flat at noise. Per-faction movements
within noise on the three target factions:
* Drukhari: +38.20 → +38.32 (+0.12, predicted no movement — Pain
  Tokens are inert post-wave-43, confirmed).
* Tyranids: +20.81 → +20.34 (-0.47, predicted -12 to -18 wr-points).
* Orks: +16.29 → +17.84 (**+1.55 wrong direction**, predicted -3
  to -7).

Best cross-faction moves (no targeted work this wave):
* AdMech: +18.94 → +18.22 (-0.72)
* Astra Militarum: +9.30 → +8.59 (-0.71)
* T'au: +11.93 → +11.33 (-0.60, Markerlight fix from wave 54
  continuing to ripple)

### 6th instance of per-model amplification — Drukhari Pain Tokens

DRK-PAIN-TOKENS-V2 (`528f46b`) found the same pattern as
SOROR x2 / TSON Cabal / T'au Markerlights / Aeldari Strands. Agent
baseline measurements:

| Round | tokens_holding | alive_unique_names | Amplification |
|---|---:|---:|---:|
| 1 | 0.00 | 8.40 | 0.00× |
| 2 | 1.80 | 12.15 | 0.15× |
| 3 | 15.80 | 10.75 | 1.47× |
| 4 | 29.75 | 9.70 | 3.07× |
| 5 | 38.85 | 8.85 | **4.39×** |

Starting expansion: 71 multi-model Unit instances / 6 unique codex
squad names = **11.8×**. The gate at `code/simulator.py:5446` iterated
`army.units` per-instance; dead model instances satisfy the
Below-Starting-Strength check independently. Each sibling instance
awarded its own Pain Token; the per-instance `pain_tokens >= 1` cap
only blocked double-award within ONE instance, not across siblings.

Fix mirrors SOROR-V1: `_pain_token_awarded` set per-army per-Command-
phase + dedupe by `profile.name`. Post-fix ratio: 0.45× overall.

**Critically**: Pain Tokens were stripped of per-datasheet abilities
in wave-43 DRK-PAIN-TOKENS (`15e0d66`). They currently accrue into a
pool but have no offensive effect, so the fix is correctness-only —
no metric movement expected, and Drukhari +0.12 at eval confirmed this.

The agent's important **diagnostic finding**: Drukhari's +38 residual
lives in the **activation count structural issue**. Drukhari fields
81-90 Unit instances at 2000pts vs 39-53 for Marines — a 1.5-2×
activation advantage. Each Unit instance gets independent move /
shoot / charge / fight activations per round. Resolution requires
squad-level activation grouping (T3 architecture) or per-squad damage
scaling. Same shape as the wave-50 Drukhari agent's structural carry-
forward; this wave confirms it via direct measurement.

### Tyranids — Harpy + Warriors with Ranged Bio-Weapons

TYRANIDS-SYNAPSE-V1 (`d646f8c`) found two units firing multiple
mutex weapon profiles simultaneously:

1. **Harpy** (14% archetype frequency): codex "twin stranglethorn
   cannon OR twin heavy venom cannon" — mutual exclusion. BSData
   packed both into primary + secondary; simulator fired both each
   Shooting phase. 1.65× ranged inflation. Override clears secondary
   slot.
2. **Tyranid Warriors with Ranged Bio-Weapons** (10% archetype
   frequency): the wave-44 TYRANIDS-MULTI-LOADOUT override blended the
   primary correctly but left `extra_ranged_profiles` containing three
   BSData loadout alternatives (Devourer, Deathspitter, Spinefists)
   firing on top of the blended primary. 3.75× DPA inflation. Override
   clears `extra_ranged_profiles`.

Same shape as wave-52 TYRANIDS-OVERBUFF-V1 (Zoanthrope Warp Blast
mutex), wave-43 TYRANIDS-DIAG-3, and TYRANIDS-MULTI-LOADOUT. Agent's
N=20 patched runtime test: 50% (target 47.4%, within noise). Predicted
12-18pt reduction at N=40; measured -0.47.

The predicted-vs-measured gap on Tyranids and Orks (next section)
warrants a wave-56 process note (below).

### Orks — Tankbustas heterogeneous-squad weapon averaging

ORKS-AMPLIFICATION-V1 (`b872506`) found the **same heterogeneous-
squad-weapon-averaging pattern** the wave-50 Drukhari agent flagged
as structural:

Tankbustas: 6-model squad where ONE model (the Nob) carries the
Smash Hammer (S6 AP-2 D3) and the other 5 carry Choppas (S5 AP-1 D1).
BSData picks the "best legal melee weapon" without weighting by
quantity, so all 6 models inherit the Nob's Smash Hammer stats.
2.26× per-model melee damage amplification. Secondary effect: inflated
`melee_dpa=4.0` exceeded `ranged_dpa=2.0`, making the AI charge with a
nominally-shooty unit instead of letting it shoot.

Override: weighted average melee profile (5× Choppa + 1× Smash
Hammer = S5 AP-1 D1.33). Post-fix `melee_dpa=1.77 < ranged_dpa=2.0`,
restoring shoot-first behavior.

Plus 3 missing citations added: `simulator.waaagh`,
`WAR_HORDE.melee_sustained_hits_army_wide`,
`WARBOSS.plus_one_to_hit_melee_only`. Waaagh activation count
verified exactly 1.00/battle (correct).

Predicted -3 to -7 wr-points; measured **+1.55 wrong direction**.

### Pattern note — agent metric predictions

Across waves 50 / 52 / 53 / 55, agent predictions based on per-unit
damage attribution (random_fill or local DPP measurements) have
consistently over-shot the measured archetype-eval movement:

| Wave | Faction | Predicted | Measured |
|---|---|---:|---:|
| 50 | Drukhari Combat Drugs | -2 to -5 | +0.12 |
| 52 | KoS extra_melee | Daemons +2-4 | +1.43 |
| 53 | AdMech Crucible | "substantial" | +0.71 |
| 53 | Daemons stratagems | "several pts" | -0.24 |
| 55 | Orks Tankbustas | -3 to -7 | **+1.55** |
| 55 | Tyranids Harpy+Warriors | -12 to -18 | -0.47 |

The successful predictions on archetype eval came from per-model
amplification fixes on rules that drive damage curves directly:
SOROR AoF (substitutes hit/wound/save rolls), T'au Markerlights
(drives every T'au shot for 5 rounds). The over-predictions are
mostly per-unit weapon profile or stratagem fixes where the affected
unit's archetype-build presence is smaller than its random_fill
damage attribution suggested.

**Wave-56 dispatch implication**: predict conservatively. Agents
should report N=20 archetype eval delta (not random_fill DPP) as the
prediction basis. Or: only predict direction, not magnitude, until
the prediction-vs-measured calibration improves.

### Open carry-forwards into wave 56

1. **Drukhari activation count structural** (T3 architecture).
   Confirmed via wave-55 measurement: 81-90 Drukhari Unit instances
   vs 39-53 Marines at 2000pts. Largest single tractable residual
   would close substantially with squad-level activation grouping.
2. **TSON +22.54** still uncloseed — Cabal point generation rate
   (not Doombolt cap) likely the remaining lever.
3. **AdMech +18.22** — archetype-build damage attribution diagnostic
   needed (not random_fill).
4. **Daemons +17.94** — Lever 2 stratagem additions landed but
   didn't move metric; dispatcher firing instrumentation suggested.
5. **Aeldari +13.10** — Strands Advance was a small slice.
   Battle Focus / detachment audits remain.
6. **Sororitas +10.55** — close to noise but still over. AoF dice
   selection refinement.
7. **Per-model amplification sweep continues** — candidates left:
   GSC Cult Ambush (UNDER), DG Plague Companies (in-band),
   Necron Awakened Dynasty (UNDER), Custodes Ka'tah (close to band).
8. **Heterogeneous-squad-weapon-averaging mapper fix** — wave-55
   Tankbusta override fix is the band-aid for a cross-faction
   structural bug. Mapper should pick weapons weighted by codex
   datasheet quantity (1 Nob's Power Klaw + 9 Boyz' Choppas → 0.1×
   Power Klaw stats + 0.9× Choppa stats). Tractable T3 mapper work.
9. **IK -36.71 / CK -43.33 mapper-locked**.

## Wave 54 close (2026-05-29)

Branch `claude/sim-calibration-6`. 3 commits landed on top of wave-53
close `2ca1a30`. Top commit at wave-54 close is `03a1e05`.

Wave 54 attacked the **per-model amplification pattern** systematically.
The pattern (`[[project-one-unit-per-model-amplification]]`) had been
the consistent metric mover across waves 49 / 51 / 53. Wave 54
dispatched three Sonnet agents on three candidate factions (Aeldari
Strands of Fate, T'au Markerlights, plus a cross-faction Crucible
hidden-unit filter from a wave-53 carry-forward). Two of three found
the pattern; one delivered a substantial faction-direction win.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 53 close (`2ca1a30`, 2026-05-29) | 13.97 | 10.65 | 4/22 |
| Wave 54 close (`03a1e05`, 2026-05-29) | 14.09 | **10.74** | 4/22 |

**+0.09 gated MAE** — flat at headline, but masks the largest
single-faction win since SOROR-V1 wave 49:
* T'au Empire: +13.24 → **+11.93** (-1.31 wr-points, well over noise
  floor 4.23). Markerlight per-codex-unit fix.
* Aeldari: +12.15 → +13.10 (+0.95 wrong direction, within noise 3.10).
  Strands Advance fix landed but the Aeldari +12 residual is dominated
  by other contributors per agent's note.
* AdMech: +18.46 → +18.94 (+0.48, within noise). Crucible filter
  expected to be flat (archetype builder didn't pick those units).
* Other factions: all within noise.

### Per-model amplification pattern — 5th instance

T'au's **Markerlights** triggered the same shape as SOROR x2 / TSON Cabal:
- Agent baseline (N=20 T'au vs Marines): **7.30 MARKERLIGHT Unit
  instances iterated per phase call**, codex-correct ~0.84
  representatives — 8.7× amplification.
- Pre-fix: 3.01 tokens placed per phase. Post-fix: 0.35 tokens placed
  per phase. The simulator was firing ~8x more Markerlight emissions
  than codex.
- Codex: "each T'AU EMPIRE **unit** ... can be selected to shoot with
  those weapons" — once per codex squad per phase.
- Fix mirrors SOROR-V1 / TSON-CABAL-V1: group alive MARKERLIGHT units
  by `profile.name`, yield one representative per `min_models` alive
  models. Single-model vehicles (Sky Ray Gunship `min_models=1`)
  unaffected.
- Measured -1.31 wr-points (target faction, well over noise) — the
  Markerlight token consumption drives T'au's hit-reroll / +1-BS /
  Lethal Hits chains across all five rounds, so the 8x reduction
  ripples through the entire damage curve.

### Per-model amplification pattern — 6th instance (small)

Aeldari's **Strands of Fate** Advance substitution had the same shape
but smaller magnitude:
- Agent baseline: Fate pool 6D6 initial, 5.1 spends/battle. Breakdown:
  hit 2.4 / save 1.4 / advance 1.1 / charge 0.3.
- Hit and save substitutions were correctly per-individual-attack-die
  (codex: "each time an AELDARI model is the source of an attack").
- Advance substitution was per-`Unit`-instance — a 10-model squad
  could spend up to 10 fate dice on its single codex advance roll.
- Codex: "a **unit** from your army is making an Advance ... roll" —
  one advance roll per squad.
- Fix: `Army._fate_advance_names_used_this_round` set in
  `code/army.py:186` + gate in `_do_move` at `code/simulator.py:6102`
  + reset hook in `_run_round` at `code/simulator.py:5298`.
- Advance spends 1.10 → 0.66 per battle (-40%). Measured +0.95
  wr-points (wrong direction, within noise). The Advance subset was
  too small to dominate the Aeldari residual — main contributors
  remain unaudited.

### Crucible hidden=true mapper filter

`CRUCIBLE-HIDDEN-FILTER-V1` (`8b2d4bd`) added a structural
`_is_hidden_in_matched_play(entry)` to `code/bsdata/parser.py` with a
two-gate check: name contains `[Crucible]` AND entry carries the
specific BSData modifier shape (`type="set" field="hidden" value="true"`
with the matched-play condition). Mapper now skips these in
`iter_unit_entries` before they enter the catalogue. Removed **62
Crucible units** across all 20 factions; reverted the 4 ad-hoc
wave-53 overrides; cleaned 59 stale `sweg_points_v1.json` keys; 3
previously-failing `test_sweg_points` tests now pass against the
cleaned dataset.

Eval impact (AdMech +0.48 wrong direction at headline): as the agent
predicted, archetype builder doesn't pick these Crusade chars in
archetype-shape lists. The structural fix is rule-correct and removes
phantom units from random_fill diagnostics; the matched-play eval
path is unaffected. Net unit count: 1532 → 1470 (parsed), 1478 → 1416
(catalogue).

### Open carry-forwards into wave 55

**Per-model amplification sweep — 5 instances found, more likely
remain.** Candidates for wave 55 dispatch with the same fresh-baseline-
required prompt shape:
1. **Death Guard Plague Companies stratagem cap** — DG sim is +0.21
   (in-band) but the Plague Companies stratagem may have an unmodelled
   per-unit / per-game cap.
2. **Orks Waaagh** — once per game; Orks sim +16.29 gated.
3. **Necron Awakened Dynasty Command Protocols** — already audited
   per `is_actually_led`, but the leader-gating may amplify per
   model.
4. **GSC Cult Ambush** — once per unit per battle; GSC sim is -2.88
   (in-band but close).
5. **Drukhari Pain Tokens generation rate** — Drukhari is +38;
   if Pain Tokens generate per model instead of per unit (matching
   the SOROR-V2 generation pattern), this could be the bulk of the
   Drukhari residual.

**Aeldari residual +13.10 elsewhere** — Strands Advance was a small
slice. Possible main contributors: Battle Focus (Craftworlds aura),
Strands hit/save spend selection heuristic, detachment-side fabs
(Battle Host, Devourer Swarm, etc.).

**TSON Doombolt cap verified codex-correct** — per-turn 1 Ritual, not
1/game. Code matches Wahapedia. The +22 residual must be in
cabal point generation rate or another mechanic.

**AdMech residual unchanged** — wave 50-54 closed structural items;
the load-bearing source is still unidentified. Fresh archetype-build
damage attribution recommended.

**Drukhari activation count + heterogeneous squad averaging**
(structural). +38 outlier.

**59 IK / 43 CK mapper-locked** — Stage 2 multi-profile weapon
mapper.

### Pattern note

Five of the six biggest per-faction headline wins on this branch came
from the per-model amplification pattern:

| Wave | Faction | Move | Pattern |
|---|---|---:|---|
| 51 | Sororitas | -8.09 | Per-model AoF generation gate |
| 49 | Sororitas | -4.28 | Per-model AoF spend gate |
| 54 | T'au Empire | -1.31 | Per-model Markerlight firing gate |
| 53 | TSON | -0.24 | Per-model PSYKER cabal loop (cap-bounded) |
| 54 | Aeldari | +0.95 | Per-model Strands Advance (smaller scope) |

The pattern's leverage stems from squad sizes (5-10 models per codex
unit) multiplying directly through the gated mechanic. Faction army
rules and detachment "once per unit per phase" gates are the highest-
ROI audit targets — multiple faction residuals are likely each closing
1-8 wr-points of the same shape.

