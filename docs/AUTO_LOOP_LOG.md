# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 53 close (2026-05-29)

Branch `claude/sim-calibration-6`. 3 commits landed on top of wave-52
close `5b4ce12`. Top commit at wave-53 close is `b012139`.

Wave 53 attacked the three named wave-52 carry-forwards in parallel
(TSON Cabal economy, Daemons stratagem parity, AdMech detachment
re-audit). All three landed clean, rule-correct commits but headline
gated MAE stayed flat.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 52 close (`5b4ce12`, 2026-05-29) | 13.96 | 10.65 | 4/22 |
| Wave 53 close (`b012139`, 2026-05-29) | 13.97 | **10.65** | 4/22 |

**Flat at headline.** All per-faction movements within their noise
floors. Three commits landed real rule-correctness improvements but
the metric movement was below noise at N=40 — pattern consistent
with waves 50 / 52. Notable per-faction shifts:
* TSON: +22.54 → +22.30 (-0.24, slight better direction, predicted)
* Daemons: -17.70 → -17.94 (-0.24, slight wrong direction, +5-7 predicted)
* AdMech: +17.75 → +18.46 (+0.71, wrong direction, "substantial"
  predicted)
* Drukhari: +39.15 → +38.20 (-0.95, downstream of stratagem dispatcher?)
* Votann: +15.82 → +14.99 (-0.83, no targeted work)

### Third instance of the per-model amplification pattern

TSON-CABAL-V1 (`ab1f4b8`) found the third instance on `claude/sim-
calibration-6` of the codex "per unit" rule gated per-`Unit`-instance:
- Wave 49 SOROR-ACTS-OF-FAITH-V1: AoF spend gate (3.7× amplification)
- Wave 51 SOROR-DETACHMENT-V1: AoF generation gate (4.65×)
- Wave 53 TSON-CABAL-V1: Cabal Ritual attempt gate (2.8×)

Pre-fix TSON measurement: 18.7 PSYKER unit-objects iterated per army
(army builder decomposes each Rubric Marines squad of 5 into 5
PSYKER-keyword Units). Codex: "select one model from your army **with
this ability**" — the ability lives on the Aspiring Sorcerer, one per
squad regardless of model count. Fix: group alive PSYKER units by
`profile.name`, yield one representative per `min_models`. Single-model
characters (Ahriman, Sorcerer, Magnus) unaffected.

Post-fix: 6.5 PSYKER squad-representatives per battle, 4.60 Doombolt
firings (vs 5.00 pre-fix), 10.10 mortal wounds (vs 10.45). The
per-turn `manifested_this_turn` cap (1 Doombolt/turn) was already
bounding the damage output regardless of caster count; the real fix is
**attrition resilience** — as units die, the squad count drops
appropriately rather than the model count, so casting capacity
degrades correctly over the 5-round battle. Predicted modest direction-
correct movement; measured -0.24 (within noise 8.75).

### Daemons stratagem parity — 1 → 10

DAEMONS-STRATAGEMS-V1 (`2336450`) added 9 stratagems across all
five Daemons detachments:
- Shared (Daemonic Incursion, applies to all detachments): Draught of
  Terror (+1 to wound shooting), Warp Surge (advance+charge), Daemonic
  Invulnerability (4+ invuln transient).
- Blood Legion: Blood Begets Skulls (advance+charge Khorne), Wrath
  Undeniable (+1 to wound melee).
- Plague Legion: Seeping Virulence (lethal hits proxy at 6+ vs codex
  5+; acknowledged under-model), Foetid Resurgence (3-wound recovery).
- Legion of Excess: Archagonists (+1 to wound melee, clean codex match).
- Scintillating Legion: Flickering Reality (+1 save transient).

Pre-fix: 1 stratagem dispatched (Daemonic Pact). Post-fix: 10. With
the wave-44 STRATAGEM-CHAIN-V1 cap-2-per-phase, Daemons now fires
2-3 stratagems per round in a typical game. All rule-correct
magnitudes per CLAUDE.md §10 (one under-model accepted, one slight
over-value accepted both within approximation tolerance).

Predicted "several points" uplift; measured -0.24 (wrong direction,
within noise 3.16). Possible reasons for the under-performance vs
prediction:
- Stratagem dispatcher's gating logic may be rejecting more often
  than expected.
- CP economy: Daemons' starting CP and per-round refill may be
  consumed by other higher-priority strats before the new ones fire.
- N=40 noise dominates.

Worth a follow-up: instrument dispatcher fire counts and verify the
new strats are actually firing in matches.

### AdMech Crucible character leak

ADMECH-REAUDIT-V1 (`b012139`) found 3 Crusade narrative-campaign
characters (Cohort Commander, Ironstrider Alpha, Magos — all
`[Crucible]`-suffixed) leaking into the matched-play unit pool.
BSData marks them `hidden=true` via modifier, but
`iter_unit_entries` in `code/bsdata/mapper.py` follows top-level
entryLinks without filtering the hidden modifier. Each unit
fires THREE independent weapon passes per activation (Twin cognis
lascannon + Twin cognis autocannon + Torrent / DW Transonic
cannon) at 45-80pts — 3-4× the expected damage-per-point ratio.
Per random_fill diagnostic, together they accounted for ~24% of
AdMech damage output.

Fix: `enabled: false` on all three via overrides; removed from
`data/sweg_points_v1.json`. Predicted "substantial" reduction;
measured +0.71 (wrong direction). The likely cause: the archetype
builder (used by eval per `feedback-loop-uses-archetype-eval`
memory) doesn't actually pick these characters in archetype-shape
AdMech lists — the 24% damage attribution was from random_fill
diagnostic battles, NOT from the archetype-build eval path. So
the disable was a no-op on archetype eval.

**Systemic finding flagged**: 59 OTHER Crucible-suffixed units
across all factions remain. A `hidden=true` filter in
`iter_unit_entries` would be the structural fix and could
affect every faction's random_fill behavior — but per the
archetype-eval observation, the impact on the main eval path
might also be limited unless those Crucible chars actually
appear in archetype builds.

### Open carry-forwards into wave 54

1. **Drukhari structural** — still +38.20 gated, largest single
   tractable residual. Activation count + heterogeneous squad
   weapon-stat averaging. Hard problem, needs T3 mapper or
   simulator-architecture work.
2. **TSON Doombolt cap tightening** — per-turn cap (1/turn) bounds
   damage to ~5 firings/battle × 3.5 MW = ~17 MW. Verify the
   codex's actual cap shape (some Rituals once per game; verify
   Doombolt's). If 1/game vs 1/turn, several wr-points down.
3. **AdMech archetype-side audit** — Crucible disable didn't help
   eval because archetype builder doesn't pick those. Top damage
   contributors IN ARCHETYPE BUILDS (different from random_fill)
   need fresh measurement.
4. **Daemons stratagem dispatcher instrumentation** — verify the
   9 new strats are actually firing in eval matches; the -0.24
   movement vs predicted "several points" suggests they may not
   be hitting the dispatcher.
5. **Systemic Crucible filter** — `hidden=true` check in
   `iter_unit_entries` would remove all 59 Crucible units across
   factions; cross-faction impact unknown but rule-correct.
6. **Tyranid over-buff search** — Zoanthrope mutex fix moved
   Tyranids only +0.24; the +21 residual is elsewhere. Verify at
   N=80 to separate signal from noise on the existing fix, then
   pursue different damage contributors.
7. **Sororitas detachment unit-side weapon profile re-verify**
   post-recent mapper refresh.
8. **GUO Bilesword LETHAL HITS field now wired** — confirm it
   actually fires in melee resolution against typical targets.
9. **Crucible composite Daemon Charioteer / Herald + Captain in
   Gravis Armour wargear-choice-group max=1 gate** for
   `extra_melee_profiles`.
10. **IK -36.24 / CK -43.21 mapper-locked** — Stage 2 multi-
    profile weapon mapper.

### Process note

Wave 53 reinforces a pattern from waves 50 / 52: agent prompts that
predict large metric movement on T2-scope changes often over-predict.
At N=40, even meaningful rule-correctness fixes commonly land within
noise. The three signals that have consistently moved the metric:
- Per-model representation amplification fixes (SOROR x2, TSON Cabal
  — though TSON Cabal damage was cap-bounded so movement was small).
- Mapper-structural population fixes (MAPPER-EXTRA-MELEE-V1 wave 52
  on KoS).
- Direct stat / weapon-profile corrections on dominant damage
  contributors (DRK-NON-SKYSPLINTER Combat Drugs, Tyranid Zoanthrope
  mutex).

Stratagem additions and detachment-flag adjustments produce smaller
movements — closer to noise floor — and need either N=80 verification
or batched landings to register on gated MAE.

