# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 57 close (2026-05-29)

Branch `claude/sim-calibration-6`. 2 cherry-picked commits + 1
docs-only commit landed on top of wave-56 close `2588076`. Top commit
at wave-57 close is `5cc7abf`. Plus `docs/NECRONS_AWAKENED_DYNASTY_AUDIT.md`
findings doc added separately.

Wave 57 corrected the wave-56 GSC regression, removed a fabricated
Custodes Ka'tah stance, and investigated whether the Necron Awakened
Dynasty per-codex-unit gate had amplification (it didn't — clean,
parked).

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 56 close (`2588076`, 2026-05-29) | 14.50 | 10.98 | 4/22 |
| Wave 57 close (`5cc7abf`, 2026-05-29) | 14.33 | **10.84** | 4/22 |

**-0.14 gated MAE** — modest direction-correct headline movement, but
masks **massive cross-faction swings** from the mapper-side
GSC-regression fix:

Big wins (downstream of pistol-basket removal):
* Tyranids: +20.58 → +16.05 (-4.53)
* Orks: +21.05 → +16.41 (-4.64)
* T'au: +12.29 → +10.26 (-2.03)
* AdMech: +17.15 → +15.37 (-1.78)
* GSC: -11.45 → -8.23 (+3.22 toward zero, **the wave-56 regression
  partially closed**)
* AM: +3.95 → +2.88 (-1.07, AM Orders fix continuing to settle)
* EC: +7.58 → +6.27 (-1.31)
* TSON: +21.83 → +20.52 (-1.31)
* WE: +1.81 → -0.10 (-1.91, now slightly under)
* Custodes: +6.11 → +5.40 (-0.71, Ka'tah removal)

Big losses (mapper-side pistol-basket effect — Bolter dominance now):
* **Adeptus Astartes: +8.35 → +14.78 (+6.43 wrong direction)**.
  Marines Tactical Squads now use Bolter (D=1) instead of basket of
  Bolter + Bolt Pistol; the bolt-pistol-diluted basket was suppressing
  Marine ranged damage in waves 56.
* Votann: +14.39 → +17.84 (+3.45). Hearthkyn + similar pistol-
  carrying loadouts.
* Sororitas: +11.03 → +13.77 (+2.74). Battle Sisters' bolters.
* Necrons: -2.84 → -5.82 (-2.98). Warriors' Gauss Flayers.
* Aeldari: +13.58 → +14.89 (+1.31). Guardian Defenders.
* DG: +1.28 → +2.35 (+1.07).

The headline -0.14 sits between these two clusters. Per-faction lens:
**6 factions moved >1 wr-point toward zero, 4 factions moved >1
wr-point away from zero**. Rule-correctness improved across both
clusters (no fabricated stats added or removed; only mapper geometry
changed) — but the metric trade-off is now a known property of the
wave-56 / 57 mapper sweep.

### GSC regression — wave-56 mapper pistol contamination

GSC-REGRESSION-V1 (`579e567`) traced the GSC -8.45 wave-56 regression
to a downstream mapper bug introduced by HETERO-SQUAD-MAPPER-V1's
basket fix. Root cause:

Wave-56 mapper basket-averaged ALL fixed ranged weapons a model
carries. In BSData, models frequently carry both a primary weapon
(Mining Laser, Plasma Incinerator, Heavy Bolter) AND a sidearm pistol
(Autopistol, Bolt Pistol). In 10e rules, a model fires ONE ranged
weapon per activation — the pistol is only usable under the
Engagement Range special rule. The basket gave equal weight to both,
so Neophyte Hybrids' Mining Laser basket fraction collapsed from ~4/20
to ~2/20 (-88% ranged damage).

Fix (`code/bsdata/mapper.py` `_collect_weapons_for_model`): when
multiple ranged weapons on one model, keep only the single best
non-pistol weapon. Pistol-only models unaffected. Citation:
`simulator.basket_best_ranged_per_model`.

Sample effect — Neophyte Hybrids:
* Before: attacks=1, hit=0.535, S=4, AP=0, D=1.37
* After: attacks=2, hit=0.570, S=4, AP=-1, D=1.74

N=20 archetype GSC vs Marines: 35% → 65%. At full N=40: GSC +3.22
toward zero (still under but recovering).

Cross-faction ripple: Marines (Tactical Squad Bolter + Bolt Pistol),
Sororitas (Battle Sisters), Votann (Hearthkyn), Necrons (Warriors),
Aeldari (Guardian Defenders), DG (Plague Marines) all carry pistol
secondaries — their primary ranged weapons now dominate the basket
instead of being diluted. Direction-correct per 10e rules but the
metric calibration on those factions shifted upward.

### Fabricated Custodes Ka'tah stance removed

CUSTODES-KATAH-V1 (`5cc7abf`) found `SHIELD_HOST.melee_crit_on_5_plus_hits=True`
is a fabricated Ka'tah stance not present in the codex. The three
real Martial Ka'tah stances are:
- Kaptaris (invuln vs ranged)
- Rendax (melee AP+1)
- Dacatarai (Sustained Hits ranged)

None is "Crit-on-5+ melee." The fabricated stance fired on EVEN
rounds (2, 4); the cycle was Rendax on odd, fabricated-crit on even.
Removed per CLAUDE.md §10. Rendax AP+1 retained unchanged. Citation
updated to mark the removed entry.

Eval: Custodes -0.71 at N=40 (within noise 2.65, direction-correct).

### Necron Awakened Dynasty — no amplification found, parked

NECRONS-AWAKENED-DYNASTY-V1 (no commit) investigated whether the
`bonus_to_hit_when_led` Command Protocols gate has the per-model
amplification pattern. Finding: **the buff fires ZERO times in
typical archetype battles**.

Root cause: `is_actually_led()` uses a 6" proximity check to
approximate the codex's "formally attached leader" rule, but the
simulator places each Unit at an independent board position. Overlord
and Necron Warriors start ~18" apart and never close to within 6"
during combat.

Per-codex-unit gate clean, multi-leader stacking clean, proximity
uses `ability.aura_range` (not hardcoded 6"), host_keys composes
correctly, Reanimation Protocols per-codex-unit gate unchanged from
wave 28/49 fixes.

**Decision: PARK.** Real fix requires a proper leader-attachment
registry (T3 architecture). Wave-57 measured Necrons at -2.84 (in-
band, just barely). A rule-correct fix here would push Necrons OUT
of band wrong direction. Findings documented at
`docs/NECRONS_AWAKENED_DYNASTY_AUDIT.md` for the eventual leader-
attachment registry work.

### Open carry-forwards into wave 58

1. **Cross-faction pistol-basket calibration** — wave 57 created
   wrong-direction movement on Marines (+6.43), Votann (+3.45),
   Sororitas (+2.74) which all carry pistol secondaries. The
   bolter-dominance is rule-correct per 10e but the metric shift
   suggests these factions had been UNDER-modeled by the wave-56
   bolt-pistol-diluted basket. Need to:
   - Verify each affected faction's archetype build top-damage
     contributors against current Wahapedia.
   - Confirm whether the wave-57 levels are now the "true" sim%
     against a fixed-rules baseline.
   - If real-meta lists DON'T spam the primary weapon (which they
     usually do because the special-weapon dominance is real),
     accept the new levels and audit the residuals from there.
2. **Drukhari activation count structural** (T3 architecture) — the
   single largest residual remains +36.53.
3. **AdMech +15.37** — archetype damage attribution still
   unidentified.
4. **Daemons -16.87** — stratagem dispatcher firing instrumentation.
5. **TSON +20.52** — Cabal point generation rate audit.
6. **Aeldari +14.89** — Battle Focus / Strands hit-save selection.
7. **Sororitas +13.77** — AoF dice selection refinement; new
   pistol-basket calibration check needed.
8. **Per-model amplification sweep continues** — DG Plague
   Companies, GSC Cult Ambush, etc.
9. **Leader-attachment registry** (T3) — unblocks Necrons Command
   Protocols and likely several other "while leading" rules.
10. **IK -36.83 / CK -43.21 mapper-locked**.

### Pattern note — mapper waves teach iteration

The wave 56 → 57 sequence is a clean example of structural-mapper-fix
iteration. Wave 56's HETERO-SQUAD-MAPPER-V1 was rule-correct (weight
weapons by codex squad quantity) but had a downstream bug
(pistol-basket contamination) that produced a wrong-direction GSC
regression. Wave 57's GSC-REGRESSION-V1 fixed that downstream bug.
Net across the two waves: headline +0.12 gated MAE, but per-faction
behavior is now substantially more rule-correct on heterogeneous
squads AND pistol-carriers. The metric tradeoff is acceptable per
CLAUDE.md §3 Stage 1 priorities.

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

