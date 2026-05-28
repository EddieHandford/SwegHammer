# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 45 close (2026-05-28)

Branch `claude/sim-calibration-6`. 1 commit landed on top of wave-44 close
`0aaa73c`. Top commit at wave-45 close is `4b3e18d`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 44 close (`0aaa73c`, 2026-05-28) | 13.57 | 10.22 | 5/22 |
| Wave 45 close (`4b3e18d`, 2026-05-28) | 13.57 | **10.22** | 5/22 |

Wave 45 is a no-metric-move iter. Skysplinter Assault wiring is correct
but inert because of an upstream gap. SECONDARY-SELECTION-V2 was attempted,
regressed, and reverted.

### Landings

* `4b3e18d` **[T1] DRK-SKYSPLINTER-DISEMBARK** — wire LANCE + IGNORES
  COVER on Drukhari units the turn they disembark from a TRANSPORT,
  closing the largest tractable outlier (Drukhari +33 gated). Added
  `Unit.transient_lance_this_turn` + `Unit.transient_ignores_cover_this_turn`
  flags, composed via OR with the profile flags in `Unit.attack`; set
  by `_disembark` when the army's detachment is Skysplinter Assault; 9
  new tests in `tests/test_skysplinter_disembark.py`.

  **Eval: zero metric movement (Drukhari 86.5% to 86.5%).** Root cause:
  the Drukhari Raider and Venom both carry `deep_strike=True` in BSData
  (the Aeldari "Deep Strike" infoLink). `_deploy_armies` routes every
  `deep_strike=True` unit into reserves BEFORE `_embark_pregame_passengers`
  runs, so the pregame embark pass sees zero Drukhari transports on the
  board. Across 40 sample battles (~17 with Skysplinter Assault), zero
  Drukhari disembark events fire. The wiring is rule-correct and will
  activate the day the upstream gap closes.

### Failed attempt: SECONDARY-SELECTION-V2

Faction-aware picker (replacing V1's uniform heuristic) was attempted
to close the V1 +0.66 regression. Faction tiers were classified as
ELITE / MOBILE / MID. Eval result: gated MAE 10.22 to 10.89 (+0.67,
worse than V1).

Root cause of the regression: tier table miscalibration. Adeptus Astartes
classified as "elite" (BiD + Assassination Fixed) crashed Marines sim
55.8% to 39.5% — Tactical Marines field 5-10 model squads and are
mid-shape, not the 3-5 elite shape Custodes / Knights occupy. The V2
revert spec (gated MAE > 10.6 indicates V2 isn't an improvement)
triggered; reverted in working tree, no commit.

### Open carry-forwards into wave 46

1. **Upstream reserves + embark coupling** — when a TRANSPORT is routed
   into reserves at `_deploy_armies`, route its matched INFANTRY
   passengers into reserves alongside it (or pre-embark before reserves
   routing). Unblocks the dormant Skysplinter wiring and probably similar
   gaps on Marines Drop Pods / Aeldari Wave Serpents / etc.
2. **SECONDARY-SELECTION-V3** — V2's tier table was over-aggressive on
   elite tier. V3 should put Marines / Sororitas / GK in MID, leaving
   only Custodes / IK / CK as ELITE. The structural V1 fix stays in
   place; V3 is a tier-table refinement only.
3. **Daemons Locus broadcast magnitude** — anchor (DAEMONS-FIX-1) landed
   in wave-44 but the +0.6 wr-points was below noise. Per
   DAEMONS-DIAG-10 findings the remaining levers are the Locus aura
   broadcast magnitude and Greater Daemon combat profile audit.
4. **Sororitas Acts of Faith spend model** — unaudited, gated 16.05.
5. **STRATAGEM-CHAIN-V2** — widen cap from 2 to 3.
6. All wave-44 carry-forwards remain in place.

## Waves 43-44 close (2026-05-28)

Branch `claude/sim-calibration-6`. 13 commits landed on top of wave-42 honest
eval `702e843`. Top commit at wave-44 close is `207b842`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 42 close (`702e843`, 2026-05-27) | 13.03 | **9.68** | 4/22 |
| Wave 43 baseline post-DRK-PAIN-TOKENS + LOADER-FAIL-LOUD (`ae7eac2`, 2026-05-28) | 13.11 | 9.75 | 3/22 |
| Wave 44 close (`207b842`, 2026-05-28) | 13.57 | **10.22** | 5/22 |

Net **+0.54 gated MAE regression** across 13 commits. Inside-band count +1
(Chaos Space Marines flipped in at 0.20 gated). Direction is the
"correctness-positive, mean-absolute-error neutral or slightly negative"
pattern noted in the wave 7-42 close — most individual landings moved their
target faction 0-1 pt at N=40, with SECONDARY-SELECTION-V1 introducing
asymmetric variance that nudged the metric up while making the simulator
materially more rule-correct.

### Single biggest win

**Custodes gated 15.25 → 2.51** (a 12.7 pt compression) — driven by
TYRANIDS-SYNAPSE-3D6 (Custodes' enemies stop auto-passing Battle-shock,
so Custodes scoring against Battle-shocked enemies normalises) plus the
SECONDARY-SELECTION picker no longer over-rewarding their elite low-count
shape. Custodes effectively dropped into the noise band.

### Commit landings

* `b4cf249` **[T2] LOADER-FAIL-LOUD** — make `_apply_override` raise when an
  override has no matching base entry and lacks required core stat fields
  (name / health / damage). Caught the `aeldari_drukhari_scourges` typo
  that had been silently fabricating a zero-stat ghost entry, causing a
  14 GB pytest leak via `build_random_army`'s affordability loop. Pre-flight
  scan confirmed only one orphan override key existed. Per CLAUDE.md §13
  (fail loud when data is missing).
* `ae7eac2` **LOOP-CLEANUP-UNLOCK** — `scripts/loop_cleanup.py` was printing
  "REMOVED" while `git worktree remove --force` (single -f) silently failed
  against Claude-agent lock files. Bumped to `-f -f` so locks from dead
  parent claude.exe sessions get overridden. Tooling, no simulator impact.
* `51726fc` **EVAL-TOURNAMENT-GAMES** — `scripts/evaluate_vs_meta.py`
  `save_snapshot()` referenced `TOURNAMENT_GAMES[fac]` but the dict was
  never defined; the JSON-out path crashed with NameError on every eval.
  Added `_load_tournament_games()` alongside `_load_noise_floor()`. Tooling.
* `b4073e5` **docs: CORE_RULES_COVERAGE.md** — coverage matrix mapping
  Wahapedia 10e core rules to simulator state. Initially marked
  embark / disembark as missing on the strength of stale comments at
  `code/detachments.py:767` and `code/archetypes.py:133`; the EMBARK-V1
  agent later discovered embark was implemented in PR #156 / `c84e4db`
  and the comments were just out of date. Section 9 corrected in
  EMBARK-V1's accompanying commit.
* `8db2967` **DAEMONS-DIAG-10** — diag findings doc. Original wave-43
  dispatch hypothesised Greater Daemon seeding was missing; verification
  found archetypes already seed them and `code/leaders.py:618-640` wires
  the Herald loci. The real lever (Lever 1 in the findings) is that the
  four Greater Daemons are seeded in templates but almost never make it
  into actual builds (Bloodthirster 1%, Lord of Change 0%, KoS 0%, Great
  Unclean One 5% across 80 builds).
* `352b1b4` **[T2] DAEMONS-FIX-1** — anchor Greater Daemon in mono-god
  templates before the budget walk in `_instantiate_template`. Verified
  presence rose to 100% across 80 builds, uniform 25% mono-god rotation.
  Daemons gated -12.52 → -11.93 (+0.6 wr-points; below noise floor 3.16,
  but mechanically the anchor is now wired so future per-god leverage
  work has something to land on).
* `f2ccf11` **[T1] EMBARK-V1** — discovered embark / disembark is already
  fully implemented (`_embark_pregame_passengers`, `_embark`, `_disembark`,
  `_maybe_disembark_before_move`, `_destroyed_transport_disembark`, plus
  activation gates in all four phase methods; 12 passing tests in
  `tests/test_transports.py`). Agent added `Unit.is_embarked` convenience
  property, refreshed stale comments in `code/detachments.py` and
  `code/archetypes.py`, and wrote 4 new tests in `tests/test_embark.py`.
  Drukhari did not move (+0.0) because the +33 driver is the still-unwired
  Skysplinter Assault disembark-turn LANCE + IGNORES-COVER buff (parking
  lot — needs per-weapon-keyword temporary gating infrastructure).
* `b51bb98` **[T1] SECONDARY-SELECTION-V1** — each army now picks 2 of 4
  Fixed Pariah Nexus secondaries at battle start based on enemy shape
  (heuristic on enemy MONSTER/VEHICLE count, own FLY/MOUNT count).
  Previously the simulator scored all four every game, asymmetrically
  over-rewarding balanced armies. Gated MAE 9.75 → 10.41 (+0.66
  regression) because the picker's heuristic introduced new variance —
  but the scoring is now rule-correct per Pariah Nexus 10e (CLAUDE.md
  §10). The remaining gap is a V2 picker with faction-aware heuristics
  (parking lot).
* `6202ce1` **TYRANIDS-SYNAPSE-AUDIT** — diag findings doc. Single
  largest over-buff named: `code/simulator.py:4694-4703` auto-passed
  Tyranid Battle-shock within 6" of SYNAPSE, citing the
  pre-September-2024 codex text. Current codex says 3D6 instead of 2D6,
  not auto-pass.
* `24d8a7e` **[T2] TSON-KOS-MESMERISING-V1** — Sorcerer in Terminator
  Armour's "Marked by Fate" datasheet ability was proxied as
  `plus_one_to_hit=True` on the led Scarab Occult Terminators squad —
  a 3-dimensional over-buff (single-target → all targets, single-roll →
  all rolls, single-phase → both phases). Replaced with
  `reroll_hit_ones=True` (the proxy convention used by Ahriman / Infernal
  Master). TSON sim 71.5 → 71.2 (-0.3, below noise).
* `08b1a2d` **[T2] VOTANN-JUDGEMENT-TOKENS-V1** — Judgement Tokens
  machinery itself is clean (re-roll buffs were retired in iter25); the
  real over-buff was on the Kâhl leader aura. Codex "Kindred Hero" grants
  [LETHAL HITS]; the proxy was `plus_one_to_hit=True` — a ~2× over-buff.
  Replaced with `reroll_hit_ones=True`. Side fix: rewrote
  `tests/test_votann_oathband.py` (ImportError-broken since
  VOTANN-DIAG-2 removed the six fabricated stratagems it referenced).
* `201d1f9` **[T2] ADMECH-WARGEAR-V1** — six AdMech overrides
  added / extended in `data/overrides.json`. Skitarii Vanguard / Rangers
  / Sicarian Infiltrators had basket-blend leaks (heavy-weapon special-
  option stats averaged into the basic rifle profile), running at
  ~2.7-3× the correct per-attack damage versus MEQ. Tech-Priest
  Manipulus / Dominus had stacked exclusive weapon options firing
  simultaneously. Data is now Wahapedia-correct; sim moved +4 (wrong
  direction at N=40 noise floor 4.17, statistically indistinguishable
  from baseline).
* `5f00b3f` **[T1] TYRANIDS-SYNAPSE-3D6** — replace the auto-pass at
  `code/simulator.py:4694` with the current-codex 3D6 sum versus 2D6.
  ~16% fail rate at 3D6 vs Leadership 8 versus 0% under auto-pass.
  Tyranids gated 18.78 → 15.92 (-2.9 wr-points, direction correct).
  Custodes also benefited (-6.3 wr-points) via cleaner Battle-shock
  landscape. Chaos Daemons widened slightly (-3.8) — Daemons score
  No Prisoners / Cull against enemy Battle-shock fails, so reducing
  those reduces their secondary scoring.
* `207b842` **[T1] STRATAGEM-CHAIN-V1** — widen
  `DETACHMENT_STRATAGEM_CAP_PER_COMMAND_PHASE` from 1 to 2. The existing
  dispatcher already gates each `_try_X` on CP affordability and the
  per-strat once-per-phase exclusion is implicit (each strat appears
  exactly once in the dispatcher list). One-constant fix. Gated MAE
  10.52 → 10.22 (-0.30, the only landing this run to move MAE in the
  right direction by more than noise). 3-stack remains parking lot.

### Pattern observed

Of 13 commits, only STRATAGEM-CHAIN-V1 (-0.30) and the Custodes-side of
TYRANIDS-SYNAPSE-3D6 (-6.3 wr-points on Custodes alone) moved the
needle visibly at N=40. The rest were correctness-positive but
mean-absolute-error neutral — confirming the wave 7-42 observation that
individual rule-correctness fixes plateau into noise at this scale once
the easy levers are spent.

### Open carry-forwards into wave 45

1. **Drukhari Skysplinter Assault disembark buffs unwired** — the +33
   Drukhari gated outlier is driven almost entirely by the missing
   per-disembark-turn LANCE + IGNORES-COVER grant on Kabalites / Wyches.
   Needs per-weapon-keyword temporary-gating infrastructure first.
   Probably 2-3 commits of structural work.
2. **Sororitas Acts of Faith spend model** — still +16-20 gated post
   wave-44. Unaudited this run.
3. **Imperial Knights / Chaos Knights structural mapper gap** — -30
   and -41 gated respectively. Locked structural; needs Stage 2.
4. **Daemons follow-up beyond Greater Daemon anchor** — Locus aura
   broadcast magnitude and Greater Daemon combat profile audit are the
   two next levers per DAEMONS-DIAG-10 findings.
5. **Tyranid Norn Emissary / Tervigon / Old One Eye** — under-modelled
   per TYRANIDS-SYNAPSE-AUDIT findings (FNP override on OOE, Tervigon
   spawn, Norn Singular Purpose). These would shift Tyranids the wrong
   direction (sim is over-shoot), so deprioritised.
6. **SECONDARY-SELECTION-V2** — faction-aware picker. Current uniform
   heuristic adds noise; a V2 that maps known faction shapes to the
   secondary-mix that real-meta lists actually pick should close the
   +0.66 V1 regression.
7. **Per-weapon-keyword temporary gating infrastructure** — prerequisite
   for Skysplinter Assault (above) plus ~10 other disembark-turn /
   round-gated detachment rules currently approximated or unwired.

### Tooling housekeeping

- `LOOP-CLEANUP-UNLOCK` patch (`ae7eac2`) makes `scripts/loop_cleanup.py`
  actually remove agent worktrees instead of printing "REMOVED" while git
  silently fails. Tested end-to-end during this run.
- `EVAL-TOURNAMENT-GAMES` patch (`51726fc`) unblocks `--out` JSON
  snapshots; every eval in this run produced a writable snapshot.
- `LOADER-FAIL-LOUD` (`b4cf249`) catches the `aeldari_drukhari_scourges`
  typo that previously caused a 14 GB pytest leak.
- `docs/CORE_RULES_COVERAGE.md` (`b4073e5`) now exists as a living audit
  matrix; expect to be updated each iter when a new rule lands or a gap
  is confirmed.

## Waves 7-42 close (2026-05-24 → 2026-05-27)

Branch `claude/sim-calibration-6`. 36 commits landed on top of wave-6 close
`9bee471` (LEADERABILITY-SCHEMA). Top commit at wave-42 honest eval is
`702e843`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 6 close (`9bee471`, 2026-05-23) | 13.85 | 10.66 | 4/22 |
| Wave 20 (`2ca72a4`, 2026-05-24) | 13.20 | 10.03 | 4/22 |
| Wave 42 (`702e843`, 2026-05-27) | 13.03 | **9.68** | 4/22 |

Cumulative −0.98 gated MAE over 36 commits across 4 days. Inside-band count
stayed at 4 (Death Guard, World Eaters, Emperor's Children, Grey Knights).
Stage-1 floor is clearly compressing more slowly each iter; the easy levers
are spent.

### Commit landings by faction (top 36)

The pattern across waves 7-42 was bundle-of-one DIAG agents on the largest
non-structural outliers, with periodic "TIGHTEN" passes on faction-side
secondary scoring dampers (most of which were rolled back in the final
SCORING-MULTIPLIERS-ROLLBACK at `e26ac0e` per CLAUDE.md §10 — faction-gated
metric tuning is not rule-correct calibration).

* **Drukhari** (`d5b1fc8` DRK-LEGENDS-FNP, `468cf4e` DRK-DIAG-12 list-integrity,
  `e4e3ada` DRK-DIAG-11 AI fragile-fly-vehicle bias, `2ca72a4` DRK-TIGHTEN-2,
  `2f37251` DRK-TIGHTEN-3, `6cf85c2` DRK-DIAG-9-TIGHTEN) — six landings. Dampers
  rolled back; rule-correct landings stayed. Drukhari still +33.05 gated, the
  single largest tractable outlier.
* **Tyranids** (`d3c2588` TYRANIDS-DIAG-7 Hive Tyrant Onslaught fab, `818c0d5`
  TYRANIDS-DIAG-8 Invasion Fleet Ld penalty fab). Still +18.90 gated.
* **AdMech** (`d6e9fe9` ADMECH-DIAG FNP false positives, `1ecfdc0` ADMECH-DIAG-2
  Doctrina BATTLELINE gate, `8c6e5bb` ADMECH-DIAG-3 Dominus correction, `0e4f243`
  ADMECH-DIAG-4 Kataphron host_keys, `423b82f` ADMECH-DIAG-5 Cawl reroll fab,
  `31db826` ADMECH-DIAG-6 Skitarii host_keys). Now +8.46 gated, down from ~12.
* **Sororitas** (`bac402c` SOROR-DIAG-6 Insidiants FNP, `6f086ff` SOROR-FAB-AUDIT,
  `43d382c` SOROR-LAST-RESORT-DAMPER, `abb4896` SOROR-NUDGE Junith flamer,
  `978c22d` SOROR-SANCTIFIERS mapper amalgamation). Still +12.96 gated.
* **Daemons** (`b6e9022` DAEMONS-DIAG-6 BiD/NP damper, `e145c58` DAEMONS-DIAG-7
  Skulltaker, `7c545ae` DAEMONS-DIAG-8 Bloodthirster melee-only, `2a3a3c7`
  DAEMONS-DIAG-9 Daemon Prince stealth). Improved from -20 to -12.52 gated by
  PRIMARY-VP-AUDIT alone.
* **Orks** (`cac0421` ORKS-DIAG-2 Meganobz FNP, `e52695f` ORKS-DIAG-3 Warboss
  melee gate, `84f489b` ORKS-DIAG-4 damper). Still +10.77 gated.
* **TSON** (`e2cc317` KOS-MESMERISING, `b50533e` TSON-FINISH Magnus invuln,
  `7e6c970` TSON-DIAG-3 Ahriman fab). Now +7.96 gated.
* **Aeldari** (`d27237d` AELDARI-DIAG-3 Yncarne heal). Now +4.28 gated.
* **Votann** (`12d2f68` VOTANN-DIAG-2 real Needgaard stratagems). Now +6.84 gated.
* **Custodes** (`7a32dc1` CUSTODES-AUDIT Shield-Captain fab). Still +15.25 gated.
* **T'au** (`a0515fd` T-AU-DIAG-3 revert mutex artifact). Now +5.91 gated.
* **Knights** (`8cba4a1` KNIGHTS-MULTIPROFILE-1, `4ab2103` KNIGHTS-MULTIPROFILE-2,
  `c4b1711` KNIGHTS-MULTIPROFILE-3, `c6c1b24` KNIGHTS-AI-COMMIT, `e4da921`
  KNIGHTS-SEED-BUMP, `d4000cf`/`0154f18` KNIGHTS-DEFENDER-DAMPER + revert). Six
  landings, mostly multi-profile work. IK still -26.02 / CK still -34.16 gated;
  structural mapper gap dominates.
* **Cross-cutting structural** (`853ecbc` MAPPER-FNP-SWEEP 19 prose-walk leaks
  across 9 factions, `e26ac0e` SCORING-MULTIPLIERS-ROLLBACK 7 faction gates,
  `702e843` PRIMARY-VP-AUDIT round-1 gate). The biggest single mover of the
  block: PRIMARY-VP-AUDIT shifted Daemons -16.93 → -12.52 gated by removing the
  alpha-strike round-1 scoring bug.

### Pattern observed

After 36 commits, the gated MAE moves −0.98. Most individual DIAG passes
moved their target faction by 0-1 pt at N=40 (correctness-positive but
MAE-neutral). The two clean wins were structural: MAPPER-FNP-SWEEP (FNP
prose-walks across 9 factions) and PRIMARY-VP-AUDIT (rounds 2-5 gating).
Faction-gated dampers/multipliers (CUSTODES/DRK/TYR/DAEMONS/SOROR/ORKS)
were rolled back as rule-fabricated metric tuning per CLAUDE.md §10.

### Open carry-forwards into wave 43

1. **Drukhari Pain Tokens magnitude** — DRK-DIAG-7 ruled out Combat Drugs;
   Pain Tokens never opened. Highest-leverage unresolved Drukhari lever.
2. **Tyranids Warriors basket / archetype composition** — multi-loadout fix
   landed but archetype-realism vs Goonhammer lists not audited.
3. **Daemons archetype Greater Daemon seeding** — LEADERABILITY-SCHEMA wired
   but Tzeentch/Nurgle/Slaanesh Greater Daemons may not surface in templates.
4. **Custodes board-control bias** (project-custodes-board-control memory) —
   structurally parked; needs Stage 2.
5. **Knights multi-profile + battleshock infra** — structurally parked;
   accumulated 6 multi-profile commits without closing the -25/-37 gap.

## Wave 43 in-flight (2026-05-27) — 3 parallel agents on top tractable outliers

Dispatched against carry-forwards 1-3. Bundle-of-one, worktree isolation,
30 tool-use cap, ~400-token prompts per `AUTO_LOOP_PROCEDURE.md` §C.

| Agent | Faction | Target |
|---|---|---|
| DRK-PAIN-TOKENS | Drukhari +33.05 gated | Audit Power From Pain implementation magnitude vs Wahapedia |
| DAEMONS-ARCHETYPE-LOC | Daemons -12.52 gated | Audit Greater Daemon seeding so wave-6 Locus auras have host targets |
| TYRANIDS-WARRIORS-BASKET | Tyranids +18.90 gated | Audit archetype composition + Warriors basket realism vs Goonhammer |

Each agent reset to `origin/claude/sim-calibration-6` @ `702e843` and stays
on its worktree branch — cherry-pick into main worktree after eval.
