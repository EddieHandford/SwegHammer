# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 59 close (2026-05-29)

Branch `claude/sim-calibration-6`. 2 commits landed on top of wave-58
close `f1d8aaf`. Top commit at wave-59 close is `f1c2825`. Third
agent (Sororitas) was killed mid-investigation by the user for a
clean session handoff before structural work.

Wave 59 attacked three persistent over-shooting factions with
targeted archetype-build audits + Wahapedia verbatim refresh on
Aeldari. **Aeldari Battle Focus fix was the biggest single-wave
faction win since SOROR-V1 wave 51 (-5.23).**

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 58 close (`f1d8aaf`, 2026-05-29) | 14.38 | 10.82 | 4/22 |
| Wave 59 close (`f1c2825`, 2026-05-29) | 14.28 | **10.73** | 4/22 |

**-0.09 gated MAE** — modest direction-correct headline, dominated
by Aeldari -5.23 and AdMech +1.54 (wrong direction). Other small
shifts within noise.

### Aeldari Battle Focus — wrong-keyword gate

AELDARI-BATTLE-FOCUS-V1 (`04895fe`) found a single-line keyword
gate bug. The current 10e codex Battle Focus rule (per fresh
Wahapedia fetch) reads:

> Star Engines: when an **ASURYANI VEHICLE** unit from your army
> Advances, you can spend one Battle Focus token; until the end of
> that turn, ranged weapons equipped by models in that unit have
> the [ASSAULT] ability.

The simulator at `code/simulator.py:6243` checked `"ASURYANI" in kw`
only — missing the VEHICLE requirement. **54 ASURYANI non-VEHICLE
units** (Wraithguard, Dark Reapers, Dire Avengers, Guardian
Defenders, Striking Scorpions, etc.) were getting free
shoot-after-Advance every turn they advanced. Only the 20 ASURYANI
VEHICLE units (Wave Serpent, Falcon, Fire Prism, War Walkers, etc.)
should qualify.

Single-line fix: `"ASURYANI" in kw and "VEHICLE" in kw`.

Agent N=20 prediction (62.9% → 58.8%, -4.1pt). **Measured N=40:
-5.23**. The N=20 prediction discipline UNDER-shot here — the full
22-faction matrix amplifies the effect because Aeldari infantry
running shoot-after-Advance is heavily over-represented across many
opponent matchups.

Aeldari now sits at +9.77 gated, the closest the faction has been
to in-band since wave 49.

### AdMech Kataphron heterogeneous AP averaging

ADMECH-ARCHETYPE-V1 (`f1c2825`) found Kataphron Destroyers'
heterogeneous loadout was mapper-averaged: 2 models with Heavy
Grav-Cannon (AP-1, D=2) + 2 models with Plasma Culverin Standard
(AP-2, D=1). The mapper averaged to AP=round(-1.5)=-2, D=1.5 — but
competitive Skitarii Hunter Cohort lists run ALL-grav per Wahapedia
(per Goonhammer 10e May 2026 Detachment Focus).

Fix: per-unit override `adeptus_mechanicus_kataphron_destroyers` →
ap=-1, weapon_damage_per_shot=2.0, anti_keyword_basket_fractions
{VEHICLE: 1.0}. Direction-correct per CLAUDE.md §10 — overriding to
the tournament-meta loadout that real GSC-style players choose,
within codex datasheet rules.

Agent N=20 prediction (62.1% → 57.2%, -4.9pt). **Measured N=40:
+1.54 wrong direction**. The N=40 22-faction matrix flipped the
sign of this fix. Likely because the AP-1 D2 grav profile is
stronger against tougher targets (Marines, Custodes) than the
basket average was against everything mixed. The agent's N=20
sample didn't capture this matchup-dependent effect.

### Sororitas agent killed mid-investigation (intentional)

SORORITAS-RECAL-V1 was stopped by the user before completing for a
clean session handoff. The agent's interrupted trace surfaced a
useful **diagnostic finding** worth carrying forward:

> Morvenn Vahl at 185pt is the most consistent top damage dealer in
> archetype builds (338 damage / 20 battles = 16.9 avg). Exorcist
> at 210pt: 6.7 damage / battle. Morvenn appears genuinely
> over-efficient at her current points cost.

This is a **Stage 2 (points equation) issue**, NOT Stage 1
(simulator accuracy). The Sororitas residual likely cannot be
closed by simulator-rule fixes alone — Morvenn's stat block matches
codex but the points cost may be the leverage point. Park for
Stage 2 work.

### N=20 prediction discipline — 6 datapoints, accuracy mixed

| Wave | Agent | N=20 predicted | N=40 measured |
|---|---|---:|---:|
| 54 | T'au Markerlights | "substantial" | -1.31 |
| 55 | Drukhari Pain Tokens | no movement (inert) | +0.12 |
| 55 | Orks Tankbustas | -3 to -7 | +1.55 (wrong) |
| 55 | Tyranids Harpy+Warriors | -12 to -18 | -0.47 |
| 56 | AM Orders | 25%→40% pre/post vs Marines | **-4.64** (matched) |
| 56 | Votann Huntr's Mark | random_fill -7.8pt | -0.83 |
| 58 | Marines plasma Torrent | "-10ish" | -2.14 |
| 58 | Aeldari Strands hit/save | -0.7 | +0.11 |
| 58 | TSON cabal cap | negligible | -0.12 (matched) |
| 59 | Aeldari Battle Focus | -4.1pt | **-5.23** (under-shot, beat target) |
| 59 | AdMech Kataphron | -4.9pt | +1.54 (wrong sign) |

Pattern: predictions are **direction-correct ~70% of the time** but
magnitude is unreliable. Stratagem / unit-profile fixes especially
prone to wrong-sign outcomes at full-matrix N=40 due to matchup
asymmetries.

### Open carry-forwards into wave 60

1. **Drukhari activation count structural** (T3 architecture). Still
   +36.53 gated, largest residual. Multi-day branch — the user is
   pausing this session to do structural work via another agent,
   likely this lever.
2. **Sororitas Morvenn Vahl Stage 2 pricing audit** — surfaced by
   wave-59 killed agent. Park until Stage 2 work begins.
3. **TSON +20.64** — Cabal generation cap didn't move the needle.
   Magnus / Ahriman leader-aura tier may still be over-modeled.
   Top damage contributor: Rubric Marines (Bringers of Change
   parking-lot ability is "reroll wound 1s on ranged", currently
   unmodelled — adding it would worsen overshoot).
4. **AdMech +16.91** — Kataphron fix moved wrong way. Belisarius
   Cawl or Hastarii Fusiliers (S12 anti-tank at low cost) may be
   load-bearing. Agent flagged both as candidates.
5. **Sororitas +14.00** — pistol-basket ripple from wave 57. AoF
   selection refinement remains.
6. **Votann +18.08** — pistol-basket ripple from wave 57. Hearthkyn
   profile re-verify.
7. **Marines +13.00** — Plasma Incinerator fix landed -2.14. Top
   damage contributors past Hellblasters need profile verification.
8. **Per-model amplification sweep**: DG Plague Companies, GSC Cult
   Ambush, Custodes Ka'tah remaining.
9. **Daemons -16.40** — stratagem dispatcher firing instrumentation
   to verify wave-53 stratagem additions actually fire.
10. **IK -36.83 / CK -43.69 mapper-locked** — Stage 2 multi-profile
    weapon mapper. The user's structural-work pause may attack this
    instead of Drukhari activation count.

### Session handoff

User pausing this session for structural work via another agent.
`docs/CURRENT_STATE.md` updated with the new headline + the
structural lever ranking. Next session can resume cleanly by
reading that file first.

## Wave 58 close (2026-05-29)

Branch `claude/sim-calibration-6`. 4 commits landed on top of wave-57
close `0fdacd8`. Top commit at wave-58 close is `74f06ac`.

Wave 58 attacked the wave-57 Marines regression (now the largest
non-IK/CK residual after the pistol-basket fix) plus TSON Cabal
generation and a deeper Aeldari Strands extension. Plus a session-
resume protection commit (`26de965` `docs/CURRENT_STATE.md`).

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 57 close (`0fdacd8`, 2026-05-29) | 14.33 | 10.84 | 4/22 |
| Wave 58 close (`74f06ac`, 2026-05-29) | 14.38 | **10.82** | 4/22 |

**-0.02 gated MAE** — flat at headline. Marines moved -2.14 toward
zero (Plasma Incinerator Torrent fix), but other small drift offset
it.

### Marines plasma-Torrent fix

MARINES-AUDIT-V1 (`4eb490d`) found a substring fab in the BSData
mapper: `_TORRENT_NAME_TOKENS` contained `"incinerator"`, which
matched "Plasma Incinerator" and "Macro Plasma Incinerator" — both
are Heavy plasma weapons with normal 3+ hit, NOT Torrent auto-hit.
This wrongly set `torrent=True` on three units (Hellblaster Squad,
Redemptor Dreadnought, Fortis Kill Team), making their plasma shots
skip the hit roll. ~50% damage inflation on Hellblasters.

Fix: added `_PLASMA_INCINERATOR_RE` guard in `_torrent_from_name()` —
if the weapon name contains "plasma" alongside any torrent token,
returns False. Regenerated `parsed.json`.

Agent's N=20 archetype eval was very optimistic (Marines 69.2% →
52.5% combined vs Marines target 47.6%); measured at N=40 archetype
was **-2.14** (Marines +14.78 → +12.64). Still direction-correct
and the second-biggest single-faction win this run after AM-AUDIT-V1
last wave. The over-prediction at N=20 vs measured N=40 may be
because the agent's N=20 sample focused on matchups where Marines
heavily relied on Hellblasters; full N=40 averages across 22
opponents where Marines win-rate is dominated by other unit
contributions too.

### Aeldari Strands hit + save gate (per-codex-unit extension)

AELDARI-AUDIT-V1 (`b26c181`) extended the wave-54 per-codex-unit
gate from Advance-only to also cover Hit and Save substitutions.
Strands of Fate codex wording: "each time a unit is selected to make
a Hit Roll" — a unit-level event (one substitution per squad per
roll sequence), not per-Unit-instance.

New gates: `Army._fate_hit_names_used_this_round` and
`Army._fate_save_names_used_this_round`. Reset in `_run_round`.

Pre-fix Strands distribution (agent N=20): Hit 2.6, Save 1.4,
Advance 0.7, Charge 0.3 per battle. Total ~5/6 pool. Pool depletes
quickly regardless of per-squad gating.

Agent N=20: Aeldari 59.3% → 58.6% (-0.7pt). Measured N=40: **+0.11**
(within noise 3.10). The -0.7 didn't transfer.

### TSON Cabal-gen squad cap

TSON-CABAL-GEN-V1 (`74f06ac`) added a per-squad cap to the wave-53
deduplication. Random_fill can seat 3 Rubric Marines squads (15
model-units → 15//5 = 3 attempts), but BSData v10.6.0 says
Rubric Marines `max_models=10 min_models=5`, so a single datasheet
supports at most `10 // 5 = 2` squad instances. Fix:
`min(_n_squads, max_models // min_models)` for multi-model squads.

Characters (`min_models == 1`) remain uncapped — each separate
force-org slot legitimately gets its own attempt.

Agent N=20: TSON 70% → 70% (negligible movement; the 3-squad case
appears in ~4/20 seeds). Measured N=40: **-0.12** (within noise
8.75).

### Pattern note — N=20 prediction calibration is uneven

Three wave-58 agents applied the wave-55 prediction discipline
(N=20 archetype eval before/after). Of the three:
- TSON-CABAL-GEN-V1: predicted negligible, measured negligible. **Held.**
- AELDARI-AUDIT-V1: predicted -0.7, measured +0.11. Under-shot.
- MARINES-AUDIT-V1: predicted -10ish (from combined N=20), measured
  -2.14. Massive over-shot.

The Marines over-prediction suggests N=20-mixed-matchup is still
noisier than the full N=40 22-faction matrix. The standing
discipline ("N=20 archetype eval before/after as prediction basis")
is more reliable than random_fill DPP but should be treated as
**direction-correct with wide magnitude bounds**.

### Session-resume protection

`26de965` added `docs/CURRENT_STATE.md` as a fast-pickup point for
any continuation session (e.g. after a usage-limit auto-cut). It
carries the current wave #, headline metric, in-flight cherry-picks,
next 3 ranked levers, standing operational rules, and a wave-close
checklist with a step to update itself.

### Open carry-forwards into wave 59

1. **Drukhari activation count structural** (T3 architecture).
   +36.30 gated, largest single residual. Multi-day branch.
2. **AdMech +15.37** unchanged across wave-58 (no AdMech work).
   Archetype damage attribution diagnostic recommended.
3. **Sororitas +14.24** — drifted up. The pistol-basket wave-57
   ripple. AoF dice selection refinement remains a named lever.
4. **TSON +20.40** — Cabal generation cap fix small. Magnus / Ahriman
   leader-aura tier may still be over-modeled.
5. **Aeldari +15.00** — Strands hit-save extension didn't move the
   needle. Battle Focus pick magnitude is the next named candidate.
6. **Votann +18.08** — drifted up from pistol-basket ripple.
   Hearthkyn weapon profile re-verify.
7. **Marines +12.64** — Plasma Incinerator fix landed -2.14. Top
   damage contributors past Hellblasters: Eradicators, Heavy
   Intercessors — verify their profiles.
8. **Per-model amplification sweep continues** — DG Plague
   Companies, GSC Cult Ambush remain on the list.
9. **Daemons -16.51** — stratagem dispatcher instrumentation.
10. **IK -36.83 / CK -43.69 mapper-locked** — Stage 2.

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

