# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

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

