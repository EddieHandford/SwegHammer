# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 51 close (2026-05-29)

Branch `claude/sim-calibration-6`. 3 commits landed on top of wave-50
close `8f34f63`. Top commit at wave-51 close is `c11a8c1`.

Wave 51 attacked three of the wave-50 carry-forwards with parallel
Sonnet agents (Daemons Greater Daemon combat profile, AdMech detachment
+ Tech-Priest sweep, Sororitas detachment + AoF dice generation). The
discipline lesson from wave 50 ("require fresh baseline measurement as
step 1") was wired into every prompt and produced a real headline win
on Sororitas.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 50 close (`8f34f63`, 2026-05-29) | 14.24 | 10.81 | 4/22 |
| Wave 51 close (`c11a8c1`, 2026-05-29) | 13.90 | **10.53** | 4/22 |

**-0.28 gated MAE** across 3 commits — first substantive headline move
since wave 49. Drove by the Sororitas finding (next section).

### Sororitas -8.09 wr-points — biggest single-wave faction win on the branch

Wave-49 SOROR-ACTS-OF-FAITH-V1 (`413d89b`) fixed the per-instance vs
per-codex-unit AoF spend gate (-4.28 wr-points). Wave-51 SOROR-
DETACHMENT-V1 (`c11a8c1`) found the matching generation-side bug, also
amplified by SwegHammer's one-Unit-per-model representation:

Agent baseline diagnostic (N=20 Sororitas vs Marines battles at the
wave-50 HEAD):
- Average Miracle dice generated per battle: **44.05** (codex expected ~13)
- Average Miracle dice spent per battle: 28.55
- Average sim-instance deaths: 41.0
- Average codex-unit deaths: 8.5
- Over-generation factor: **4.65×**

`_maybe_award_miracle_die` fired once per `Unit` instance destroyed;
a 25-model Repentia Squad dying model-by-model awarded 25 dice instead
of 1. Fix: added a last-instance gate — the die is only awarded when
no other alive sim instance with the same `profile.name` remains in
the army. Generation drops from 44.05 to 8.70 per battle (within +/-
of the codex 13 once other Sororitas-unit destruction is rolled in).

Second finding from the same audit: Sororitas TRANSPORT units
(Immolator, Sororitas Rhino, Repressor) don't carry the Acts of
Faith ability per their datasheets — only INFANTRY and WALKER units
do. The award path didn't have the TRANSPORT keyword exclusion.
Added the gate.

Sororitas eval: +19.12 → +11.03 gated. Still over noise floor 3.79
but close enough that one more lever (AoF dice selection refinement
or remaining detachment audit) should close into noise. **Combined
with wave 49**, Sororitas has dropped +23.05 → +11.03 (-12.02
wr-points across two waves) by addressing the same simulator-
representation amplification pattern on both spend and generation
sides.

### Daemons +1.07 wr-points (improvement direction)

DAEMONS-GREATER-COMBAT-V1 (`239c91d`) audited the 4 Greater Daemons +
Skarbrand combat profiles against BSData. Only Great Unclean One
surfaced corrections — 2 ranged attack-count fields off by 1 due to
Python's banker rounding (`round(6.5) → 6`, `round(4.5) → 4` for the
Putrid Vomit / Plague Flail D6+N profiles). Other 4 Greaters
parsed cleanly. Wahapedia DNS was unavailable from the agent session
so BSData v10.6.0 (fresh 2026-05-15) was used as the source per
CLAUDE.md §6 fallback.

Parked schema gaps (notes on the correction entry, no code change):
- GUO Bilesword carries LETHAL HITS in BSData; `UnitProfile` has no
  `melee_lethal_hits` field.
- KoS Snapping Claws (A4 S6 AP-2 D3 DEVASTATING WOUNDS, EXTRA
  ATTACKS) fires in addition to the Witstealer Sword; the
  `extra_melee_profiles` mapper pathway exists but is not populated.
  This is the biggest tractable Daemons lever still parked — a
  whole melee weapon profile not simulated at all. Mapper-structural
  follow-up, T3.

### AdMech +0.72 wr-points (within noise — DW fix didn't close the gap)

ADMECH-SWEEP-V1 (`d8e3391`) found **10 units with Devastating Wounds
false positives** from the BSData mapper's basket-blend logic. None
of these units' BSData infoLinks reference Devastating Wounds; the
fabricated flag was inflating every crit-to-wound (~1-in-6 wound
rolls) into a save-bypassing critical hit across the AdMech core
roster.

Fixed units (override `devastating_wounds=false, basket_fraction=0.0`):
Skitarii Marshal, Fulgurite Electro-Priests, Cybernetica Datasmith,
Serberys Raiders, Serberys Sulphurhounds, Sicarian Ruststalkers,
Technoarcheologist, Tech-Priest Enginseer, Skitarii Rangers, Skitarii
Vanguard.

Predicted 4-8pt reduction in AdMech sim%; measured +0.72 (within
noise 4.17). The DW fix is rule-correct and definitely tightening
crit-wound math, but the residual +15.6 → +16.32 indicates other
load-bearing levers remain unaudited. Adjacent areas confirmed clean
by the agent:
- Skitarii Hunter Cohort detachment (verbatim defensive, no-flag is
  correct).
- Cohort Cybernetica detachment (Cyber-Psalm-Programming has no
  schema slot; no-flag is rule-correct).
- Tech-Priest Manipulus / Dominus wargear (ADMECH-WARGEAR-V1 cleanly
  stripped basket-blend; Transonic Cannon DW is legitimate).
- Doctrina magnitude and modifier cap (+1 BS/WS exactly, ±1 cap
  enforced).
- Added missing `simulator.doctrina_imperatives` citation to
  `data/rule_citations.json`.

### Pattern observed

The Sororitas win validates the wave-49 / wave-51 hypothesis that
"once per unit per phase" codex rules gated per-`Unit`-instance in
SwegHammer produce ~3-5× over-firing depending on squad shape. Two
distinct sites on the same army rule (spend in wave 49, generation
in wave 51) closed -12 wr-points together. The `[[project-one-unit-
per-model-amplification]]` memory entry captured this pattern; it
generalises directly to AdMech Doctrina (no-op per wave 50 audit),
Death Guard Plague Companies, any "once per battle per unit" stratagem,
and any on-death award path that fires per model.

The AdMech DW-fix shape was different — a mapper-side fabrication
sweep rather than a simulator-spend audit — and the per-unit
magnitude (~1/6 wound rolls × per-crit damage delta) was small
enough that even 10 units across the core roster only produced a
noise-floor-bounded movement. This is consistent with the wave-48
"FNP override sweep" experience: catalog-wide cleanup is
rule-correctness-positive but typically MAE-neutral.

### Open carry-forwards into wave 52

1. **Sororitas residual +11.03 gated** — still over noise 3.79.
   Remaining levers: AoF dice selection heuristic refinement
   (currently spends greedy-by-die-value; codex spend-before-roll
   gives optimal placement that the simulator can't perfectly
   approximate); Bringers of Flame / Hallowed Martyrs detachment-
   side audits (confirmed flag-clean by wave 51 but their unit-side
   weapon profiles haven't been re-verified post-recent mapper
   refresh).
2. **KoS Snapping Claws extra_melee_profiles** — the biggest single
   tractable Daemons lever per the wave-51 GREATER-COMBAT findings.
   Mapper needs to populate `extra_melee_profiles` from BSData's
   per-model multi-weapon entries; T3 mapper-structural work.
3. **GUO Bilesword LETHAL HITS** — needs a `melee_lethal_hits` field
   on UnitProfile. Schema gap, T2/T3.
4. **AdMech +16.32 gated** — DW fix closed only 0.72 of the gap.
   Other levers: re-audit Skitarii Strike Squad / Sicarian rule
   wording (the wave-49/51 lesson re: per-unit gating may apply),
   bionics-style FNP fabrications on Tech-Priests, Cawl / Belisarius
   leader entries past the wave-43 fab audit.
5. **Daemons Lever 2 — stratagem parity**. Still unaudited.
6. **Drukhari structural carry-forwards** (activation count,
   heterogeneous squad weapon averaging).
7. **TSON +20.88 gated** — last audited in wave 44.
8. **Aeldari / T'au / Votann / Orks parallel sweep** — under-audited.
9. **Tyranids over-buff identification** — Tyranid sim is +20.93;
   prior Norn/Tervigon/OOE findings are UNDER-modelled, so finding
   the over-buff direction needs a different angle (maybe Synapse
   broadcast magnitude, or detachment audit).
10. **Add Nurgle Spoilpox Scrivener + Slaanesh Tormentbringer
    leader entries** — `25af977` schema is ready.
11. **IK -35.40 / CK -43.93 mapper-locked** — Stage 2 multi-profile
    weapon mapper.

### Process note

Wave 51 agent prompts that required fresh baseline measurements
produced higher-quality landings. The wave-50 lesson held. Continue
requiring fresh baselines in wave 52 dispatches.

## Wave 50 close (2026-05-29)

Branch `claude/sim-calibration-6`. 4 commits landed on top of wave-49
close `8e10e5b`. Top commit at wave-50 close is `25af977`.

Wave 50 attacked three named carry-forwards from wave 49 (Daemons Lever
1 Greater-Daemon seeding, AdMech Doctrina representation audit, Drukhari
non-Skysplinter outlier) plus the LeaderAbility sustained-hits schema
follow-up.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 49 close (`8e10e5b`, 2026-05-29) | 14.23 | 10.81 | 4/22 |
| Wave 50 close (`25af977`, 2026-05-29) | 14.24 | **10.81** | 4/22 |

**Flat at headline.** All per-faction movements within their noise
floors. Three landings were rule-correct fixes that targeted real bugs
but where the magnitude impact at N=40 was below noise:

* Drukhari Combat Drugs (5-round permanent grant fix): predicted -2 to
  -5 wr-points, measured +0.12. Adrenalight's +1 melee attack only
  applies to Wych Cult units, and the archetype-built Drukhari armies
  in this eval are predominantly Kabal-shape; the Wych Cult subset
  doesn't dominate enough for the 5x magnitude correction to ripple
  to the gated metric.
* AdMech Doctrina alive-units gate: predicted near-zero direct impact
  per agent report. Confirmed +0.23 (within noise 4.17). The fix is
  structurally correct but only fires after total army wipeout.
* LeaderAbility sustained-hits schema + Changecaster swap: predicted
  small Daemons-direction movement. Measured -0.47 (within noise 3.16,
  wrong direction at headline). The schema is forward-compatible
  infrastructure — its main value is unblocking Nurgle Spoilpox
  Scrivener and Slaanesh Tormentbringer leader entries, neither of
  which were added in this wave.

### Daemons Lever 1 verified closed

Agent diagnostic at the wave-49 baseline measured Greater Daemon
presence across N=200 archetype builds:

| Greater Daemon | Per-archetype presence | Overall presence |
|---|---|---|
| Bloodthirster (Khorne) | 100% | 29% |
| Lord of Change (Tzeentch) | 100% | 32% |
| Keeper of Secrets (Slaanesh) | 100% | 28% |
| Great Unclean One (Nurgle) | 100% | 23% |

The DAEMONS_DIAG_10 baseline of 1/0/0/5% was measured BEFORE commit
`352b1b4 DAEMONS-FIX-1` (wave 44) which anchors the Greater Daemon
in mono-god templates ahead of the budget walk. That commit closed
Lever 1; the wave-49 carry-forward was based on stale diagnostic
numbers. Remaining Daemons -20 deficit must come from elsewhere —
likely the Greater Daemon combat profile audit (Lever C in
DIAG-10) and/or stratagem parity (Lever 2).

### Commit landings

* `6e8dfd4` **[T2] DRK-NON-SKYSPLINTER-V1** — Combat Drugs was applied
  once at `Battle.__init__` and the Adrenalight bonus (+1 melee attack
  on Wych Cult units) persisted for all 5 battle rounds, a 5×
  magnitude error. The codex rule is "at the start of your Command
  phase select which Combat Drugs will be active for your army until
  the start of your next Command phase. You cannot select the same
  Combat Drug more than once per battle." Fix in `code/simulator.py`:
  `_apply_combat_drugs(round_num)` gated to round 1 (Adrenalight is
  the picked drug); transient `combat_drug_extra_melee_attacks` cleared
  per round-start; called from `_run_round` after the transient clear.
  Stage A diagnostic measured Skysplinter ~90% / Kabalite Cartel ~80%
  pre-fix — both detachments overshoot, confirming the bug is in
  Drukhari core not detachment flags. Cited as
  `simulator.combat_drugs`. Side-finding from agent: Drukhari +38
  residual is dominated by activation-count advantage (49-unit
  Drukhari army vs ~20-unit Marine army at the same points) and
  heterogeneous squad weapon-stat averaging — both structural
  follow-ups for future waves.
* `898b023` **[T2] ADMECH-DOCTRINA-V1** — two fixes:
  - `code/simulator.py:5117` Doctrina pick used `army.units` (includes
    dead) instead of `army.alive_units`. Same shape as the wave-49
    SOROR fix; structural inconsistency cleaned up.
  - `code/army.py:235-236` and `tests/test_admech.py` carried stale
    references to the off-mode penalty rule that MR-D (claude/sim-
    calibration-5) removed. Two tests passed against a local
    `_effective_hit_target` helper that duplicated the OLD penalty
    behaviour, giving false confidence the removal was complete.
    Tests rewritten to verify the live `Unit.attack` semantics.
  Functionally near-zero win-rate move. AdMech +15.4 gated residual
  is NOT the Doctrina spend gate; remains an active diagnostic
  target for a future wave.
* `25af977` **[T3] LEADERABILITY-SUSTAINED-HITS** — schema fields
  `sustained_hits_ranged: int = 0` and `sustained_hits_melee: int = 0`
  added to LeaderAbility. Wired through `_NEUTRAL_BUFFS`,
  `effective_buffs` (additive merge via `_merge_add`), and the
  attack-resolution loop in `code/units.py` (mode-routed addition to
  `effective_sustained_hits`). Changecaster swapped from the
  `reroll_hit_ones=True` proxy (which doesn't compose with the
  SUSTAINED HITS extra-hit accumulator) to the rule-correct
  `sustained_hits_ranged=1`. Forward-compatible: Nurgle Spoilpox
  Scrivener and Slaanesh Tormentbringer can now be added to the
  registry without a follow-up dataclass change.

### Pattern observed

Three of four wave-50 commits were rule-correct fixes that targeted
real codex / structural bugs but where the per-unit magnitude was too
small (Combat Drugs limited to Wych Cult subset, Changecaster's
SUSTAINED HITS 1 swap is direction-neutral vs the reroll proxy, AdMech
alive-units gate only fires post-wipe) to ripple to the gated metric
at N=40. The DAEMONS-GREATER-SEEDING task confirmed Lever 1 was already
closed by a prior wave; the carry-forward was based on stale
diagnostic numbers.

**Implication for wave 51 dispatch discipline**: agent prompts that
quote pre-existing diagnostic numbers should require the agent's first
step to be a fresh baseline measurement before applying a fix. The
wave-49 SOROR fix (-4.28 wr-points) succeeded because it targeted a
freshly-measured representation amplification bug; the wave-50
DAEMONS-GREATER-SEEDING task wasted ~430k tokens on a gap that had
already closed.

### Open carry-forwards into wave 51

1. **Daemons Lever C — Greater Daemon combat profile audit**
   (DAEMONS_DIAG_10). Greater Daemons are now seeded at 100% per
   archetype but Daemons remain -20 gated. The combat profiles
   (M/T/Sv/W/Inv, melee stats) may carry approximations or stale
   BSData values. Predicted +5-10 wr-points if audit surfaces real
   stat lag.
2. **Daemons Lever 2 — stratagem parity**. Unaudited. Predicted +3-6
   wr-points.
3. **AdMech +15.6 gated residual** — Doctrina was the wrong target.
   Candidates: detachment-side fabrications in Skitarii Hunter Cohort
   / Cohort Cybernetica, basket-blend weapon profiles on Tech-Priest
   variants, Doctrina buff magnitude (the +1 BS / WS modifier itself
   may be over-stated vs codex modifier-cap interaction).
4. **Sororitas +19.12 gated** — AoF spend gate alone closed ~1/5 of
   the gap. Remaining levers: AoF dice selection (which die gets
   banked to which roll), detachment-side audits (Bringers of Flame /
   Hallowed Martyrs), dice-pool generation rate (currently 1/round,
   codex grants 1 + 1 per destroyed Sororitas unit — verify the
   on-death award path).
5. **Drukhari activation-count advantage** (49-unit Drukhari vs
   ~20-unit Marine at same points). Surfaced by DRK-NON-SKYSPLINTER-V1
   agent. Structural — alternating activations amplify the unit-count
   disparity. Possible mitigation: list-building heuristic that biases
   Drukhari toward fewer, larger units; or alternating-activation
   rule adjustment for asymmetric-shape armies.
6. **Drukhari heterogeneous squad weapon-stat averaging** — surfaced
   by DRK-NON-SKYSPLINTER-V1 agent. Kabalite squads carry Splinter
   Rifle (most models) + Splinter Cannon / Blaster (1-2 models). The
   mapper averages the weapon profiles; this dilutes the heavy
   weapon's impact when the squad shoots together. Tractable mapper-
   structural follow-up if a multi-profile-per-squad shape lands.
7. **TSON +20.64 gated, noise 8.75** — under-audited recently. Last
   audit was `24d8a7e TSON-KOS-MESMERISING-V1` (wave 44). High
   noise floor means tractable lever may exist but at smaller gain.
8. **Aeldari +12.62 / T'au +12.52 / Votann +15.58 / Orks +15.46** —
   all under-audited in recent waves. Each likely carries 1-2 small
   rule-correctness or detachment-audit levers. Candidates for a
   parallel sweep wave.
9. **Tyranids +20.34** — partly audited (`5f00b3f SYNAPSE-3D6`, wave
   44 -2.9 wr-points). Wave-44 Norn/Tervigon/OOE under-modelling
   findings still parked because fixing them would shift Tyranids the
   wrong direction (sim already over). The over-buff side needs
   surfacing.
10. **Nurgle Spoilpox Scrivener + Slaanesh Tormentbringer leader
    entries** — `25af977` schema is ready; entries themselves need
    BSData verification + Wahapedia citation. Small predicted
    movement but rule-correct addition.
11. **IK -35.52 / CK -43.57 mapper-locked** — Stage 2 multi-profile
    weapon mapper. Long-day branch.

### Tooling housekeeping

* Drukhari Combat Drugs side effect on AUTO_LOOP_LOG.md (agent added
  80-line in-flight block prematurely) was overwritten by this close.
  Agent prompts should explicitly forbid AUTO_LOOP_LOG.md edits —
  the wave close is the orchestrator's job.

## Wave 49 close (2026-05-29)

Branch `claude/sim-calibration-6`. 4 commits landed on top of wave-48
close `d82fb5d`. Top commit at wave-49 close is `413d89b`.

User set a session goal: drive gated MAE below per-faction noise floor
while improving rule correctness of the sim. Wave 49 attacked the two
highest-ROI tractable outliers (Sororitas +20.9 unaudited, Daemons
-20.3 with the named Lever B carry-forward) in parallel, plus the
test-tooling `_classify_cache` flake from wave 48.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 48 close (`d82fb5d`, 2026-05-29) | 14.22 | 10.83 | 4/22 |
| Wave 49 close (`413d89b`, 2026-05-29) | 14.23 | **10.81** | 4/22 |

Net **-0.02 gated MAE** across 4 commits — flat at headline but masks a
real per-faction win. Sororitas dropped 4.28 wr-points (+23.05 → +18.77
gated, well over noise floor 3.79); the gain was offset at the headline
by ~+0.5 cross-faction drift, all within each faction's noise floor
and therefore not contributing to gated. The fix is rule-correct AND
direction-correct on its target faction — this is the cleanest result
shape we get below the structural-residual floor.

### Per-faction movements above noise

* **Adepta Sororitas**: 71.3% → 67.0% sim, +23.05 → +18.77 gated.
  Sole faction moving more than its noise floor (3.79). Driven by
  `413d89b` SOROR-ACTS-OF-FAITH-V1 — see below.

All other factions stayed within 1 wr-point of their wave-48 position
(±0.83 max delta). No regressions over the gated threshold.

### Commit landings

* `0e4acc2` **[T2] CLASSIFY-CACHE-HASH** — replace `code/roles.py`'s
  manual `Dict[int, str]` cache (keyed by `id(p)`) with
  `functools.lru_cache(maxsize=4096)`, matching the convention used by
  the adjacent `expected_ranged_dpa` / `expected_melee_dpa` helpers.
  Closes the order-dependent test flake documented as a wave-48
  carry-forward: transient `UnitProfile` instances in tests get
  garbage-collected, their `id()` slot is reused, and the cache returned
  the previously-cached role for an unrelated profile. `UnitProfile`
  is a frozen dataclass so it has a stable hash that doesn't collide on
  id-reuse. Full pytest sweep now 897 passed, 0 failed (was 897 passed
  + 2 order-dependent failures on the same HEAD pre-fix).
* `41f8029` **[T2] DAEMONS-LOCUS-V1** — narrow Locus magnitude
  correction surfaced by the wave-44 DAEMONS_DIAG_10 Lever B carry-
  forward. Tzeentch Changecaster's host_keys missed Blue Horrors (a
  separate `chaos_daemons_library_blue_horrors` catalog key); BSData
  Leader profile lists "PINK HORRORS, BLUE HORRORS" as legal
  attachments. Other Locus carriers reviewed without change:
  - Khorne Bloodmaster: already correct (`plus_one_to_wound` matches
    codex verbatim).
  - Nurgle Poxbringer: parked — `+1 critical Hit threshold` doesn't
    reduce to a static `LeaderAbility` flag; current `plus_one_to_wound`
    proxy is direction-correct.
  - Nurgle Sloppity Bilepiper: correctly absent from registry
    (Battle-shock + movement aura, no offensive flag).
  - Slaanesh Contorted Epitome: `fnp=4` is acceptable approximation
    (over-broad vs codex "FNP 4+ vs mortal + psychic" but
    direction-correct).
  Predicted metric move: small (Blue Horrors rarely seeded as
  battleline in current archetypes), and confirmed at eval — Daemons
  -19.85 → -19.73 (+0.12 wr-points, well below noise 3.16). Closes
  one of the verifiable Lever B errors; remaining Daemons deficit
  bottlenecks on Lever 1 (Greater Daemon seeding) + Lever 2
  (stratagem parity) per DAEMONS_DIAG_10.
* `413d89b` **[T2] SOROR-ACTS-OF-FAITH-V1** — the real wave-49 win.
  Acts of Faith spend gate was per-`Unit` instance, but SwegHammer's
  one-Unit-per-model representation expands an archetype Sororitas
  army to ~71 Unit instances (Battle Sisters x10 × 2 squads = 20,
  Celestian Insidiants x10 = 10, Seraphim x5, etc.) where the codex
  unit count is ~19. The army was getting **3.7× more AoF spend
  opportunities per round** than the codex allows. Codex wording:
  "each **unit** can perform one Act of Faith per phase" — one per
  codex squad, not one per model.
  Fix: added `_aof_squad_names_used_this_round: set` on Army with
  `aof_squad_available(profile.name)` / `aof_squad_mark_used` helpers;
  all instances sharing a `profile.name` collapse to one codex unit
  for AoF purposes. Three spend sites in `code/units.py` (hit, wound,
  defensive save) now gate on `aof_squad_available(p.name)`. Round
  reset hook in `code/simulator.py:_run_round` clears the squad set.
  Also tightened the round-start dice-generation gate from
  `army.units` to `army.alive_units` (rule: army must have at least
  one alive Sororitas unit to qualify), and the on-death dice award.
  Predicted UNDER-cut on Sororitas sim%; confirmed -4.28 wr-points
  at eval (+23.05 → +18.77 gated). First faction-targeted commit
  this branch to move its outlier by more than its noise floor in a
  single landing.

### Pattern observed

The SOROR fix is a clean example of the "simulator-representation
amplification" failure mode — not an explicit fabrication, but the
one-Unit-per-model abstraction silently amplified a per-codex-unit
spend budget into a per-simulator-instance one. The same shape may
exist on other faction army rules with "once per unit per phase"
spend models — worth a parking-lot sweep:
- AdMech Doctrina Imperatives (+15.4 gated; once-per-phase imperative
  pick).
- Necron Reanimation Protocols (already audited via `_initial_unit_
  counts` snapshot — robust).
- Death Guard Plague Companies stratagem cap (currently per-army).
- Custodes Ka'tah stance (already keyword-gated, low risk).

### Open carry-forwards into wave 50

1. **Daemons Lever 1 — Greater Daemon seeding gap**. The wave-44 anchor
   (`352b1b4 DAEMONS-FIX-1`) seeds Greater Daemons in mono-god templates
   but the diagnostic surfaced under-attendance even with the anchor.
   Predicted +5-8 wr-points if the seeding budget is fully realized.
2. **Daemons Lever 2 — stratagem parity**. Unaudited. Predicted +3-6
   wr-points.
3. **Sororitas residual +18.77 gated** — AoF fix closed about 1/5 of
   the gap. Remaining levers: Acts of Faith spend SELECTION (which die
   gets banked to which roll), detachment-side audits (Bringers of
   Flame / Hallowed Martyrs may carry fabricated proxy flags), Acts
   of Faith POOL size (currently 1/round, codex grants 1 + 1 per
   destroyed Sororitas unit — verify award fires on every Sororitas
   destruction, not just BATTLELINE).
4. **`LeaderAbility.sustained_hits_ranged` schema gap** — surfaced by
   DAEMONS-LOCUS-V1 audit. Three Daemons leaders (Tzeentch Changecaster,
   Nurgle Spoilpox Scrivener, Slaanesh Tormentbringer) need this for
   their Locus aura proxy to be rule-correct rather than "no-op
   approximation". Probably a follow-up `LeaderAbility` field + Unit.
   attack wiring + 3 leader updates.
5. **Once-per-unit-per-phase representation sweep** — see "Pattern
   observed" above. Probably AdMech Doctrina is the highest-leverage
   candidate.
6. **Drukhari +38 gated** — still the largest single tractable residual.
   Skysplinter wiring landed in wave 45 + wave 46 reserves-embark
   coupling but the +38 includes non-Skysplinter Drukhari behaviour
   that's never been independently audited. Bundle-of-one: separate
   Drukhari analytics by detachment to isolate where the overshoot
   comes from.
7. **IK -35.5 / CK -43.6 mapper-locked** — Stage 2 multi-profile weapon
   mapper. Long-day branch when one becomes available.
8. All wave-48 carry-forwards remain in place.

### Tooling housekeeping

* `0e4acc2` CLASSIFY-CACHE-HASH unblocks deterministic test ordering
  — future stale-test audits won't need to chase the order-dependent
  flake first.
* Memory entry `[[project-classify-cache-flakiness]]` retired (fix
  landed); the entry remains as historical context until the next
  memory sweep.

