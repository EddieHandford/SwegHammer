# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 62 close (2026-05-30)

Branch `claude/sim-calibration-6`. One fix — the first item from the
detachment-fabrication sweep. Recovered from a stalled background agent: its
work was already committed (`91e0e33`) and cherry-picked as `e1346a1`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 61 close (`c4d6da6`+docs) | 12.89 | 9.36 | 2/22 |
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |

Headline flat (within noise) — a single-detachment correctness fix, not a
systemic one like wave 61.

### CUSTODES-AURIC-CHAMPIONS (`e1346a1`)

The default Custodes eval detachment carried `melee_sustained_hits_army_wide
=True` citing "Trail of Glory" — a fabrication on two counts: the cited rule
name is wrong (the real rule is "Assemblage of Might"), AND an army-wide
Sustained Hits proxy doesn't match it. Assemblage of Might designates one
enemy unit per Command phase and grants +1 wound to ADEPTUS CUSTODES
CHARACTER units against only that target — a designate-one-target +
CHARACTER-only mechanic the Detachment schema cannot proxy without
fabricating. The flag was REMOVED (a no-op is more rules-correct than a
fabrication) and its citation deleted; the shared Orks War Horde consumer of
the same flag is untouched (its gate logic is unchanged).

Custodes over-shoots, so removing the buff is direction-correct AND
MAE-positive: Custodes sim 57.1 → 56.5 (target 52.1), gated 2.39 → 1.80 —
now near in-band. The headline didn't move because one faction's -0.59 gated
averages to ~-0.03 across 22 factions.

### Process

- Recovered a stalled async agent — its fix was committed but it never
  reported back. Cherry-picked the commit directly rather than re-running.
- pytest 912 passed; audit 277/277 (one fewer required key — the removed
  fabrication flag). Eval `data/wf_wave62_n40.json`.

### Open carry-forwards into wave 63

1. **World Eaters / CSM over-shoot** from the wave-61 fall-back gate — re-tune.
2. **Necrons detachment fabrications** (task #9) — rules-correct but
   MAE-negative (Necrons under-shoots); handle with care, don't blind-remove.
3. **Detachment citation/comment fixes** (task #10) — low-risk.
4. **Strategy roadmap #1** (task #6 review) — a plan-level objective function;
   the big systemic lever, like the wave-61 fall-back fix.

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
