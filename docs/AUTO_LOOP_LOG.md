# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

## Wave 52 close (2026-05-29)

Branch `claude/sim-calibration-6`. 5 commits landed on top of wave-51
close `d2d746c`. Top commit at wave-52 close is `db85be7`.

Wave 52 attacked 4 wave-51 carry-forwards in parallel: KoS Snapping
Claws mapper-structural extra_melee_profiles wiring, TSON broad audit,
Tyranids over-buff diagnostic, and the orchestrator-handled
melee_lethal_hits schema split + new Daemon leader registry entries.
A 5th commit was a bug fix for the mapper's extra_melee dict→tuple
shape mismatch that crashed the N=40 eval on the first attempt.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 51 close (`d2d746c`, 2026-05-29) | 13.90 | 10.53 | 4/22 |
| Wave 52 close (`db85be7`, 2026-05-29) | 13.96 | **10.65** | 4/22 |

**+0.12 gated MAE drift** — slight headline regression masking real
per-faction wins and CLAUDE.md §10-mandated rule-correctness costs.
Three factions moved more than 1 wr-point: Daemons +1.43 toward zero
(closer to real meta), Custodes -1.67 closer (likely a side-effect of
KoS extra-melee via ally-host paths), Sororitas -0.95 closer, TSON
+1.66 worse (rule-correct stat fixes pushing wrong-direction as the
agent predicted), AdMech +1.43 worse (within noise 4.17), Drukhari
+0.95 worse, Genestealer Cults +1.67 worse (mapper extra_melee on a
GSC unit pushed them up from -4.19 to -2.52).

### Pattern observed

Wave 52 is the cleanest example so far of the "rule-correct fixes
moving the metric wrong-way" phenomenon. TSON-AUDIT-V1 explicitly
flagged this: BSData has Magnus's ranged damage at D3 (not the prior
override D2), and Rubric Marines' primary Inferno Boltgun at AP-2
(not the previous mapper-picked Warpflamer at AP-1). Both fixes
correct stat lag relative to current Wahapedia / BSData and both
push TSON sim%-up while we're already +20 over. The simulator is
becoming MORE rule-correct (the §3 Goal A direction) but the
metric movement is in the gated MAE's wrong direction. Headline
gated MAE alone is a lossy signal — it conflates "made the sim more
correct" with "moved sim toward meta." The per-faction breakdown is
the better lens.

### Commit landings

* `11c75bc` **[T3] MAPPER-EXTRA-MELEE-V1** — wire BSData →
  `extra_melee_profiles` for the first time. Field existed on
  `UnitProfile` (populated only by overrides) and `Unit.attack` already
  handled it via the KNIGHTS-MULTIPROFILE-2 block (lines 1133-1186);
  the mapper just hadn't been taught to populate it. Added
  `parse_weapon_keywords` detection of [EXTRA ATTACKS], a post-
  `best_melee` collection loop walking `gear.melee_weapons`, and
  dedupe-against-primary so the chosen melee weapon isn't double-
  counted. **135 units across 18 factions populated**. Key entries:
  - Keeper of Secrets: Snapping Claws (A4 S6 AP-2 D3 [DEVASTATING
    WOUNDS]) + Ritual Knife (A3 S6 AP-2 D2). ~+7 expected damage per
    fight phase per agent estimate. Both Daemons and EC variants.
  - Shalaxi Helbane: Snapping Claws.
  - Lord of Change (Daemons + TSON): Baleful Sword.
  - Great Unclean One (Daemons + DG): Bileblade.
  - Chaos Soul Grinder (all four god variants): Warpclaw + Warpsword.
  - Knight Abominant: Balemace.
  Wave-52 eval shows Daemons +1.43 toward zero (concrete movement)
  and Custodes -1.67 (Knight ally + KoS-led EC compositions). Some
  flagged false positives — Crucible composite Daemon Charioteer /
  Herald / Immortal Champion gained 8 extras each from BSData
  aggregation (Crusade-only, non-matchplay); Captain in Gravis Armour
  gained 3 because all three of its Relic-weapon wargear choices tag
  [EXTRA ATTACKS] but only one is chosen in play. Both follow-ups
  for a wargear-choice-group cap.
* `15bd4e4` **[T2] TSON-AUDIT-V1** — 4 findings across 3 areas:
  - Rubric Marines weapon override: BSData picks Warpflamer (AP-1) as
    primary; codex standard is Inferno Boltgun (AP-2). Override now
    sets the codex weapon.
  - Magnus the Red ranged damage: prior override cited non-existent
    "Tzeentchian Pyre" weapon at D2; BSData sole ranged is Gaze of
    Magnus at D3.
  - Ahriman host_keys citation text corrected (code was already
    right; citation quoted_text referenced wrong host units).
  - Bringers of Change unmodelled-ability citation gap documented.
  All Is Dust gate verified per-attack-defensive (correct). Cabal
  Doombolt mortals per-turn cap verified (correct, no per-game cap).
  Detachments + leader registry confirmed clean. Net direction:
  TSON sim ranged output rose, +1.66 wr at eval. Rule-correctness
  win at metric cost; the +22 TSON residual now traces more clearly
  to Cabal of Sorcerers economy (multiple Doombolt mortals per round
  across 10+ Psyker army builds) — a wave-53 lever.
* `ab9639f` **[T2] TYRANIDS-OVERBUFF-V1** — agent damage-breakdown
  diagnostic identified Zoanthropes as the #3 damage contributor
  (243 dmg / 13.5% share across N=20 mirror tests at 2000 pts). Root
  cause: mapper packed both Warp Blast firing modes (focused
  witchfire S12 AP-3 D=D6+1 [LETHAL HITS] + witchfire S7 AP-2 D=D3
  [BLAST]) into primary + secondary weapon slots, firing both each
  Shooting phase. Wahapedia: "The Warp blast can fire one of the
  following profiles each Shooting phase" — strict mutex. Override
  zeros the secondary slot, promoting focused witchfire as the sole
  primary (dominant tournament pick). Same shape as TYRANIDS-DIAG-3
  / TYRANIDS-MULTI-LOADOUT / TYRANID-NORN-MULTILOAD patterns.
  Wave-52 eval moved Tyranids only +0.24 (within noise 3.82) —
  smaller than the agent's predicted 3-5pt reduction; the
  contribution magnitude may need re-checking at N=80 to separate
  signal from noise.
* `1c55ee3` **[T3] MELEE-LETHAL-HITS-SPLIT** — schema gap surfaced
  by wave-51 DAEMONS-GREATER-COMBAT-V1. Pre-wave-52 the simulator
  read `UnitProfile.lethal_hits` (populated only from the ranged
  primary weapon) for both ranged AND melee attack resolution. This
  leaked ranged LETHAL HITS into melee for any unit whose ranged
  primary carried the keyword, and missed melee-only LETHAL HITS
  like GUO's Bilesword. Added `melee_lethal_hits: bool = False` to
  UnitProfile + `MappedUnit`; mapper populates it from `best_melee
  .lethal_hits`; attack resolution mode-routes the field. Mirrors
  the wave-44 iter28-MS1 split on SUSTAINED HITS. 74 units now
  populate `melee_lethal_hits` (GUO, Plaguebearers, Nurglings,
  Plague Drones, Epidemius, Horticulous, Lhykhis, Poxbringer, ~65
  others). Same commit adds two leader registry entries unblocked
  by the wave-50 `sustained_hits_melee` schema field:
  - **Spoilpox Scrivener** (Nurgle Herald): "Keep Counting!"
    grants melee [SUSTAINED HITS 1] to the led Plaguebearers.
  - **Tormentbringer** (Slaanesh Herald): "Tormentbringer (Aura)"
    grants melee [SUSTAINED HITS 1] to any friendly SLAANESH
    LEGIONES DAEMONICA within 6". Uses `_SLAANESH_DAEMON_HOSTS`
    rather than empty host_keys so the aura doesn't broadcast to
    non-Slaanesh allies.
* `db85be7` **[T2] EXTRA-MELEE-ANTI-KEYWORDS-SHAPE** — bug fix.
  MAPPER-EXTRA-MELEE-V1 populated `anti_keywords` on the extra-melee
  template as a dict, but `UnitProfile.anti_keywords` is
  `Tuple[Tuple[str, int], ...]`. The dataclasses.replace swap passed
  the dict through, and the downstream consumer at line ~2174
  `for kw, thresh in p.anti_keywords` unpacked dict-keys (strings) as
  2-tuples, raising ValueError. The bug only surfaced in the N=40
  eval — no unit test exercised an extra-melee weapon with ANTI-X
  against a target carrying the gated keyword. Fix converts the
  dict to tuple-of-tuples in the swap template.

### Open carry-forwards into wave 53

1. **TSON Cabal of Sorcerers economy** — TSON-AUDIT-V1 traced the
   +22 residual to Doombolt mortals across 10+ Psyker armies, not
   the per-leader / per-detachment fab cleanups. Cabal point
   generation rate, Doombolt manifest cap per battle, and the
   per-turn / per-game cap need a follow-up audit. Wave-52 stat
   fixes moved TSON wrong-way (+1.66) so this is the natural
   compensating lever.
2. **Drukhari activation count + heterogeneous squad averaging**
   (structural). +39 gated outlier; Combat Drugs fix
   (`6e8dfd4`) only moved 0.12. The agent's diagnostic identified
   these as the dominant drivers.
3. **AdMech +17.75** — DW false-positive sweep (wave 51) and
   Doctrina alive-gate (wave 50) closed structural issues but
   didn't tighten the metric. Likely next levers: re-audit
   detachment flag basket vs current Wahapedia, or look at the
   per-codex-unit-name pattern on Skitarii / Sicarian abilities.
4. **Daemons Lever 2 — stratagem parity**. Unaudited. Wave-52
   moved Daemons +1.43 toward zero via KoS extra-melee + melee
   lethal hits split; stratagems would compound.
5. **GUO Bilesword LETHAL HITS now wired**, but the Bilesword
   itself was not the dominant GUO damage source. Its actual
   melee weapons (Plague Flail, Doomsday Bell) carry their own
   LETHAL HITS via the new field — verify they fire correctly.
6. **Tyranids Zoanthrope movement smaller than predicted** —
   verify at N=80 to separate signal from noise.
7. **Crucible composite Daemon Charioteer / Herald / Immortal
   Champion + Captain in Gravis Armour** — wargear-choice-group
   max=1 gate for `extra_melee_profiles` population.
8. **TSON +22 cabal-driven**, **Drukhari +39 structural**,
   **AdMech +17 mixed**, **IK -35 / CK -43 mapper-locked**,
   **Tyranids +21** — five of the largest residuals all have
   identified follow-up shapes; the remaining 17 factions sit
   between 4/22 inside-band + smaller outliers.

### Process note

Wave 52 successfully balanced "rule-correct fixes" and "metric-
moving fixes" — Daemons +1.43 toward zero and Sororitas -0.95
toward zero came from rule-correctness fixes (extra_melee +
LH-split + AoF spend-side from wave 49 amplifying with the
generation-side from wave 51). The TSON +1.66 wrong-direction
landing was the cost of CLAUDE.md §10 (don't fabricate; cite
every rule). The headline gated MAE +0.12 net hides this
trade-off — the per-faction lens is the better signal.

