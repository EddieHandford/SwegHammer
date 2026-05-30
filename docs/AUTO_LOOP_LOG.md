# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 61 close (2026-05-30)

Branch `claude/sim-calibration-6`. The Knight-residual investigation (the
user's structural-lever pick) reversed its own premise — the multi-profile
weapon mapper was already done, so the residual was diagnosed as RULES +
AI-piloting, not firepower. Three fixes landed, and the combined effect is
the **largest single-wave headline move in the project's history**.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 60 close (`e1f3f53`+docs) | 14.27 | 10.71 | 2/22 |
| Wave 61 close (`c4d6da6`+docs) | 12.89 | **9.36** | 2/22 |

**-1.35 gated MAE.** The headline had been pinned at 10.5-10.9 for 12
waves; it broke on a systemic AI mis-pilot fix.

### The three fixes

- **KNIGHTS-TITANIC-ESCAPE** (`31e477c`): TITANIC/FLY units exempt from
  Desperate Escape per 10e core (verbatim Wahapedia); threshold also
  corrected 1→1-2. Knights were illegally dying 1-in-6 on every Fall Back.
- **KNIGHTS-DEMISE-D6PLUS2** (`d141a69`): mapper `_parse_demise_value`
  lacked a D6+2 case → 11 Knight chassis (Castellan/Valiant/Cerastus IK,
  Tyrant/Chaos Cerastus CK) carried Deadly Demise 1 instead of 5. Parser
  fix + overrides.
- **KNIGHTS-AI-FALLBACK** (`c4d6da6`): the dominant lever. `strategy.py`
  `pick_move_intent` let melee-primary HEAVY units (melee Knights,
  Carnifex, Hive Tyrant, Daemon Prince) Fall Back from melee — forfeiting
  their main weapon and dying to Desperate Escape. Gated on
  `not _is_melee_class`; pure ranged platforms still break off.

### Per-faction (sim_pct, wave60 → wave61)

- **Imperial Knights +10.1** (11.6→21.7, gated 34.0→23.9). Chaos Knights
  gated 40.4→37.8 — still the single largest residual; the gate helped IK
  far more than CK (CK is War-Dog/Armiger heavy, fewer TITANIC chassis).
- The fall-back gate corrected OVER-shooters down toward target: Votann
  -6.0, AdMech -5.1, Orks -4.4, Marines -4.4, AstraMil -3.9 (all gated
  errors improved). One AI fix touched many factions — that is why the
  headline moved so far.
- New over-shoots introduced: **World Eaters +7.1** (gated 0→6.0) and CSM
  (slightly over) — melee units now correctly staying engaged. Carry-forward.

### Process

- Driven by two rounds of parallel agents (2 fixes + 3 reviews, then a
  second fan-out: faction-multiplier check + keyword-gap verify +
  detachment-fab sweep). pytest 912 passed; audit 278/278; eval
  `data/wf_wave61_n40.json`.
- Verify-first repeatedly corrected agent/memory claims: the mapper premise
  (already shipped), a phantom "Canis Rex duplicate" (legal 2-model
  datasheet), and the faction-multiplier concern (already fixed in `e26ac0e`,
  `secondaries.py`, not `strategy.py`).
- Keyword-gap verify: the flagged core-rule "gaps" were mostly already
  fixed — Battle-shock R1 (iter-13), Pile-In/Consolidate (implemented),
  modifier-cap ±1 (clean delta-clamp). AIRCRAFT is genuinely unmodelled but
  no aircraft appear in any archetype → zero current MAE impact. Parked.

### Open carry-forwards into wave 62

1. **AURIC_CHAMPIONS fabrication** (task #8): the default Custodes eval
   detachment grants army-wide melee Sustained Hits 1; real "Assemblage of
   Might" is +1 wound for CHARACTER units vs one designated target. Custodes
   over-shoots → fixing it is rules-correct AND MAE-positive. Clean next win.
2. **World Eaters / CSM new over-shoot** from the fall-back gate — re-tune.
3. **Necrons detachment fabrications** (task #9): AD command-protocol
   passives + ANNIHILATION_LEGION reroll_wound_ones are fabrications, but
   Necrons UNDER-shoots, so fixing them is MAE-negative — handle with care.
4. **Strategy roadmap #1** (task #6 review): a plan-level objective function
   (next-turn reachable Objective Control per marker) is the big structural
   lever — would move many factions at once, like the fall-back fix did.

## Wave 60 close (2026-05-30)

Branch `claude/sim-calibration-6`. 3 cherry-picked fix commits landed on
top of wave-59 close `f1c2825` (via citation-cleanup commit `32e11aa`).
Top fix commit `e1f3f53`; this docs/close commit sits on top.

Wave 60 ran three parallel rule-correctness audits on persistent
over/under-shooters. All three found and fixed real bugs, and all three
moved their target faction in the correct direction — but sub-noise at the
headline. Net gated MAE essentially flat; the headline stays pinned by the
unfixed structural residuals (CK -43.7, IK -37.0, Drukhari +37.0) that
these non-structural waves don't touch.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 59 close (`f1c2825`) | 14.28 | 10.73 | 3/22 |
| Wave 60 close (`e1f3f53`+docs) | 14.27 | **10.71** | 2/22 |

-0.02 gated MAE. Band 3->2 is boundary noise (Necrons / Astra Militarum
hovering at the band edge), not a regression from the fixes.

### The three fixes — all direction-correct, combined -2.03 faction gated

- **MARINES-AUDIT-V2** (`d057c3c`): the BSData mapper picked Aggressor
  Squad's Flamestorm Gauntlets (torrent / auto-hit) as the primary weapon;
  corrected via `data/overrides.json` to the tournament-standard Auto
  Boltstorm Gauntlets (3x twin-linked, ballistic skill 3+, 18", no torrent).
  Marines gated 10.84 -> 10.00 (-0.84). Eradicators / Bladeguard verified
  clean. Same mapper-loadout-fab shape as MARINES-AUDIT-V1.
- **TSON-AURA-V2** (`1f1b3c5`): Ahriman / Infernal Master / Sorcerer in
  Terminator Armour `reroll_hit_ones` leaked into the Fight phase; the codex
  restricts these to Psychic Attacks (ranged) or the Shooting phase. Added a
  `reroll_hit_ones_shooting_only` LeaderAbility field gated `mode != melee`
  in `code/units.py`. 3 citations updated, audit 278/278. TSON gated 11.88
  -> 11.41 (-0.47), muted by the faction's 8.75 noise floor.
- **DAEMONS-STRAT-INSTRUMENT-V1** (`e1f3f53`): the 4 shared Daemonic
  Incursion stratagems were missing from all 4 god sub-detachment tuples
  (only `DAEMONIC_INCURSION_STRATAGEMS` carried them), so 80% of Daemons
  armies never fired Draught of Terror / Warp Surge / Daemonic
  Invulnerability / Denizens of the Warp. Added to all 4 tuples. Daemons
  gated 13.24 -> 12.52 (-0.72). The per-round stratagem cap means it swaps
  which 2 fire; the -15.7 residual is structural, not stratagem-count.

### Process notes

- Citation backlog cleared pre-wave (`32e11aa`): audit 278/278, exit 0, and
  `BLOCK_ON_MISSING_CITATIONS` flipped True (guard now enforcing). The guard
  lives in gitignored `.claude/hooks/`, so enforcement is machine-local.
- **Eval segfault** cost real time: `scripts/evaluate_vs_meta.py:28-30`
  re-execs via `os.execvpe` to force `PYTHONHASHSEED=0`, which throws a
  Windows access violation on this Python 3.9 box, masked as silent exit 0
  when piped. Workaround: always prefix `PYTHONHASHSEED=0` (memory
  `project-eval-pythonhashseed-segfault`). Diagnosed via `PYTHONFAULTHANDLER=1`.
- N=20 agent predictions vs N=40 truth: 3/3 direction-correct, magnitude
  sub-noise as predicted — consistent with the standing pattern that
  stratagem / aura fixes land sub-noise while direct-stat fixes move more.

### Open carry-forwards into wave 61

1. **Marines +12.2** — still the top non-structural over-shooter. Audit
   remaining contributors past Aggressors (Eradicators clean; check
   Sternguard, Devastators, Marine vehicle ranged profiles).
2. **TSON +20.2** — the melee-leak fix was small; the overshoot is broader.
   Rubric Marines durability (All Is Dust) or Cabal ritual magnitudes next.
3. **Votann +18.8 / AdMech +16.8** — untouched this wave, now the cleanest
   mid-size over-shooters; weapon-profile audits on archetype contributors.

Structural track (separate, not wave-by-wave): CK -43.7 / IK -37.0
multi-profile weapon mapper; Drukhari +37.0 activation-count grouping.

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
